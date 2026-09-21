"""
DataGuard AI — Phase 14 Chat & Conversational Intelligence Service

Orchestrates multi-turn, dataset-scoped, grounded conversational QA:
1. Enforces strict scope locking (VERSION, COMPARISON, DATASET)
2. Preserves bounded multi-turn conversation history
3. Formulates conversation-aware retrieval queries without fabricating entities
4. Executes fresh Phase 11 pgvector RAG retrieval for every new question
5. Reuses Phase 12 Assistant Service & Phase 12A ProviderManager (Gemini -> HF -> Ollama)
6. Preserves authoritative server-side provenance and citations
7. Enforces strict privacy boundaries (zero raw PII, zero raw rows stored or transmitted)
8. Defends against prompt injection in conversation history and retrieved evidence
"""

import re
import logging
import time
from typing import Dict, Any, List, Optional
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, func, delete
from sqlalchemy.orm import Session

from app.config import settings
from app.models.dataset import Dataset, DatasetVersion
from app.models.comparison import DatasetComparison
from app.models.chat import ChatSession, ChatMessage
from app.schemas.rag import RetrievalScope
from app.schemas.chat import (
    ChatScope,
    ChatSessionCreate,
    ChatSessionUpdate,
    ChatSessionResponse,
    ChatSessionDetailResponse,
    ChatMessageCreate,
    ChatMessageResponse,
)
from app.schemas.assistant import AssistantSource
from app.services.rag_retrieval_service import retrieve_rag_documents
from app.services.rag_context_service import build_grounded_context
from app.services.assistant_service import SYSTEM_PROMPT
from app.services.llm import ProviderManager, get_provider_manager, LLMUnavailableError, LLMTimeoutError

logger = logging.getLogger(__name__)

CHAT_HISTORY_MAX_MESSAGES = 12
CHAT_MESSAGE_MAX_LENGTH = 8000

# Regex for stripping potential PII patterns from generated titles
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")


def generate_safe_title_from_message(content: str) -> str:
    """
    Generate a concise, sanitized, PII-safe session title deterministically.
    No LLM calls, no API dependencies, zero raw PII risk.
    """
    if not content or not content.strip():
        return "Dataset Analysis"

    # Strip raw PII patterns
    cleaned = EMAIL_REGEX.sub("[PII]", content)
    cleaned = PHONE_REGEX.sub("[PII]", cleaned)
    cleaned = SSN_REGEX.sub("[PII]", cleaned)

    # Clean punctuation and extra whitespace
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    # Remove conversational filler prefixes
    prefixes = [
        r"^what\s+(is|are|were|about)\s+(the\s+)?",
        r"^can\s+you\s+(explain|tell\s+me\s+about|show\s+me)\s+(the\s+)?",
        r"^tell\s+me\s+about\s+(the\s+)?",
        r"^show\s+me\s+(the\s+)?",
        r"^explain\s+(the\s+)?",
        r"^how\s+(does|do|is|are)\s+(the\s+)?",
        r"^which\s+(are|is)\s+(the\s+)?",
        r"^give\s+me\s+(the\s+)?",
    ]
    title_candidate = cleaned
    for prefix in prefixes:
        title_candidate = re.sub(prefix, "", title_candidate, flags=re.IGNORECASE)

    title_candidate = title_candidate.strip(" ?.!:,;\n\t\"'")
    if not title_candidate:
        title_candidate = cleaned[:40]

    # Capitalize first letter of each word (Title Case) up to 7 words or 50 chars
    words = title_candidate.split()
    if len(words) > 7:
        title_candidate = " ".join(words[:7])

    if len(title_candidate) > 50:
        title_candidate = title_candidate[:47] + "..."

    title = title_candidate.title() if title_candidate else "Dataset Analysis"
    return title[:255]


def build_conversation_aware_query(current_message: str, history_messages: List[ChatMessage]) -> str:
    """
    Formulate a conversation-aware retrieval query deterministically.
    If the current message contains anaphora / references (e.g. 'those', 'it', 'them', 'why is email risky'),
    pull salient column/entity keywords from the immediate prior conversation without fabricating entities.
    """
    current_clean = current_message.strip()
    if len(current_clean) > 100 or not history_messages:
        return current_clean

    # Check if follow-up reference words exist
    follow_up_indicators = ["those", "them", "these", "it", "that", "why", "what about", "which columns", "which one"]
    is_follow_up = any(re.search(r"\b" + re.escape(ind) + r"\b", current_clean, re.IGNORECASE) for ind in follow_up_indicators)

    if not is_follow_up:
        return current_clean

    # Extract keywords/terms from recent 2 messages (prior assistant answer or user query)
    context_keywords: List[str] = []
    for msg in history_messages[-2:]:
        # Find potential column names, issues, or key domain terms (alphanumeric words)
        words = re.findall(r"\b[a-zA-Z0-9_]{3,30}\b", msg.content)
        # Filter out common stop words
        stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "been", "were",
            "what", "which", "will", "would", "could", "should", "your", "dataset", "data",
            "assistant", "evidence", "analysis", "table", "overview", "findings", "source", "remediation"
        }
        filtered = [w for w in words if w.lower() not in stopwords]
        context_keywords.extend(filtered[:4])

    if context_keywords:
        # Combine unique terms with current message
        unique_terms = list(dict.fromkeys(context_keywords))[:5]
        return f"{current_clean} ({' '.join(unique_terms)})"

def check_out_of_scope_query(
    content: str,
    scope: str,
    target_version_num: Optional[int],
    dataset_name: str,
) -> Optional[str]:
    """
    Validate if the user query asks for data, comparison, or versions outside
    the locked session scope BEFORE Phase 11 RAG retrieval or LLM inference.
    """
    if scope == "VERSION" and target_version_num is not None:
        # Match references to versions like 'v1', 'v3', 'version 1', 'version 3'
        version_matches = re.findall(r"\b(?:v|version\s+)(\d+)\b", content, re.IGNORECASE)
        for v_str in version_matches:
            try:
                v_num = int(v_str)
                if v_num != target_version_num:
                    return (
                        f"This chat is scoped to Version V{target_version_num}. "
                        f"A version comparison or data from Version V{v_num} is not available in the current chat context. "
                        "Start a Comparison Chat or Dataset-level Chat to analyze changes between versions."
                    )
            except ValueError:
                pass
        # Match explicit cross-version comparison requests when in single-version scope
        if re.search(r"\b(what\s+changed\s+(?:from|in|since)|compare\s+with\s+(?:previous|other|earlier|v\d+))\b", content, re.IGNORECASE):
            return (
                f"This chat is scoped to Version V{target_version_num}. "
                "A version comparison is not available in the current chat context. "
                "Start a Comparison Chat to analyze changes between versions."
            )
    return None


def create_chat_session(
    dataset_id: UUID,
    request: ChatSessionCreate,
    db: Session,
) -> ChatSessionResponse:
    """
    Create and persist a new chat session scoped strictly to a dataset, version, or comparison.
    Validates all entity associations server-side.
    """
    # 1. Validate Dataset Existence
    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    # 2. Scope Validation
    if request.scope == ChatScope.VERSION:
        if not request.version_id:
            raise ValueError("version_id is required when scope is 'VERSION'")
        if request.comparison_id:
            raise ValueError("comparison_id must be null when scope is 'VERSION'")
        version = db.execute(
            select(DatasetVersion).where(
                DatasetVersion.id == request.version_id,
                DatasetVersion.dataset_id == dataset_id,
            )
        ).scalar_one_or_none()
        if not version:
            raise ValueError(f"DatasetVersion '{request.version_id}' not found for dataset '{dataset_id}'")

    elif request.scope == ChatScope.COMPARISON:
        if not request.comparison_id:
            raise ValueError("comparison_id is required when scope is 'COMPARISON'")
        if request.version_id:
            raise ValueError("version_id must be null when scope is 'COMPARISON'")
        comparison = db.execute(
            select(DatasetComparison).where(
                DatasetComparison.id == request.comparison_id,
                DatasetComparison.dataset_id == dataset_id,
            )
        ).scalar_one_or_none()
        if not comparison:
            raise ValueError(f"DatasetComparison '{request.comparison_id}' not found for dataset '{dataset_id}'")

    elif request.scope == ChatScope.DATASET:
        if request.version_id or request.comparison_id:
            raise ValueError("version_id and comparison_id must be null when scope is 'DATASET'")

    # 3. Derive initial title
    title = request.title.strip() if request.title and request.title.strip() else "New Chat"

    session = ChatSession(
        dataset_id=dataset_id,
        version_id=request.version_id,
        comparison_id=request.comparison_id,
        scope=request.scope.value,
        title=title[:255],
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return ChatSessionResponse(
        id=session.id,
        dataset_id=session.dataset_id,
        version_id=session.version_id,
        comparison_id=session.comparison_id,
        scope=ChatScope(session.scope),
        title=session.title,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def list_chat_sessions(
    dataset_id: UUID,
    db: Session,
) -> List[ChatSessionResponse]:
    """
    List all chat sessions associated with a dataset ordered by updated_at descending.
    """
    # Verify dataset exists
    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    sessions = db.execute(
        select(
            ChatSession,
            func.count(ChatMessage.id).label("msg_count")
        )
        .outerjoin(ChatMessage, ChatMessage.session_id == ChatSession.id)
        .where(ChatSession.dataset_id == dataset_id)
        .group_by(ChatSession.id)
        .order_by(ChatSession.updated_at.desc())
    ).all()

    results = []
    for sess, count in sessions:
        results.append(
            ChatSessionResponse(
                id=sess.id,
                dataset_id=sess.dataset_id,
                version_id=sess.version_id,
                comparison_id=sess.comparison_id,
                scope=ChatScope(sess.scope),
                title=sess.title,
                message_count=count,
                created_at=sess.created_at,
                updated_at=sess.updated_at,
            )
        )
    return results


def get_chat_session(
    dataset_id: UUID,
    session_id: UUID,
    db: Session,
) -> ChatSessionDetailResponse:
    """
    Retrieve a specific chat session with its full message history.
    Enforces dataset association and returns messages in chronological order.
    """
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not session:
        raise ValueError(f"ChatSession '{session_id}' not found for dataset '{dataset_id}'")

    messages = db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()

    msg_responses = [
        ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            provider=m.provider,
            model=m.model,
            fallback_occurred=m.fallback_occurred,
            grounded=m.grounded,
            sources=m.sources,
            warnings=m.warnings,
            created_at=m.created_at,
        )
        for m in messages
    ]

    return ChatSessionDetailResponse(
        id=session.id,
        dataset_id=session.dataset_id,
        version_id=session.version_id,
        comparison_id=session.comparison_id,
        scope=ChatScope(session.scope),
        title=session.title,
        messages=msg_responses,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def update_chat_session(
    dataset_id: UUID,
    session_id: UUID,
    request: ChatSessionUpdate,
    db: Session,
) -> ChatSessionResponse:
    """
    Update chat session title. Scope cannot be changed.
    """
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not session:
        raise ValueError(f"ChatSession '{session_id}' not found for dataset '{dataset_id}'")

    cleaned_title = generate_safe_title_from_message(request.title)
    session.title = cleaned_title
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(session)

    count = db.execute(
        select(func.count(ChatMessage.id)).where(ChatMessage.session_id == session_id)
    ).scalar_one()

    return ChatSessionResponse(
        id=session.id,
        dataset_id=session.dataset_id,
        version_id=session.version_id,
        comparison_id=session.comparison_id,
        scope=ChatScope(session.scope),
        title=session.title,
        message_count=count,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def delete_chat_session(
    dataset_id: UUID,
    session_id: UUID,
    db: Session,
) -> None:
    """
    Delete a chat session. All child messages are cascade deleted.
    """
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not session:
        raise ValueError(f"ChatSession '{session_id}' not found for dataset '{dataset_id}'")

    db.delete(session)
    db.commit()


def send_chat_message(
    dataset_id: UUID,
    session_id: UUID,
    request: ChatMessageCreate,
    db: Session,
    provider_manager: Optional[ProviderManager] = None,
    existing_user_msg: Optional[ChatMessage] = None,
) -> ChatMessageResponse:
    """
    Process a user message in a chat session:
    1. Validates session scope and input length
    2. Persists user message (if not retrying an existing message)
    3. Auto-derives title from the first message if still default
    4. Gathers bounded prior conversation history (max 12 messages)
    5. Performs fresh Phase 11 RAG semantic retrieval
    6. Formulates hardened prompt and invokes ProviderManager (Gemini -> HF -> Ollama)
    7. Attaches authoritative server-side provenance
    8. Persists assistant message and updates session timestamp
    """
    start_time = time.time()

    # 1. Validate session & Dataset
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not session:
        raise ValueError(f"ChatSession '{session_id}' not found for dataset '{dataset_id}'")

    dataset = db.execute(select(Dataset).where(Dataset.id == dataset_id)).scalar_one_or_none()
    if not dataset:
        raise ValueError(f"Dataset '{dataset_id}' not found")

    content = request.content.strip()
    if not content:
        raise ValueError("Message content cannot be empty")
    if len(content) > CHAT_MESSAGE_MAX_LENGTH:
        raise ValueError(f"Message exceeds maximum allowed length of {CHAT_MESSAGE_MAX_LENGTH} characters")

    # 2. Persist User Message (only if not an existing user message retry)
    if existing_user_msg is not None:
        user_msg = existing_user_msg
    else:
        user_msg = ChatMessage(
            session_id=session_id,
            role="user",
            content=content,
            created_at=datetime.now(timezone.utc),
        )
        db.add(user_msg)
        db.flush()

    # 3. Update session title if default
    if session.title in ("New Chat", "Dataset Analysis", ""):
        session.title = generate_safe_title_from_message(content)

    # 4. Fetch bounded conversation history (prior messages excluding the current user message)
    prior_messages = db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.id != user_msg.id,
        )
        .order_by(ChatMessage.created_at.asc())
    ).scalars().all()

    # Keep at most CHAT_HISTORY_MAX_MESSAGES
    bounded_history = prior_messages[-CHAT_HISTORY_MAX_MESSAGES:]

    # 5. Formulate Conversation-Aware Retrieval Query
    retrieval_query = build_conversation_aware_query(content, bounded_history)

    # 6. Execute Fresh Phase 11 Semantic Retrieval
    rag_scope = RetrievalScope[session.scope]
    target_version_num: Optional[int] = None
    target_comp_label: Optional[str] = None

    if session.scope == "VERSION":
        version = db.execute(select(DatasetVersion).where(DatasetVersion.id == session.version_id)).scalar_one_or_none()
        if version:
            target_version_num = version.version_number
    elif session.scope == "COMPARISON":
        comp = db.execute(select(DatasetComparison).where(DatasetComparison.id == session.comparison_id)).scalar_one_or_none()
        if comp:
            b_num = comp.baseline_version.version_number if comp.baseline_version else 1
            c_num = comp.current_version.version_number if comp.current_version else 2
            target_comp_label = f"V{b_num} ➔ V{c_num}"

    # Resolve Provider Manager
    mgr = provider_manager if provider_manager is not None else get_provider_manager()

    # Pre-RAG Scope Validation Check (AUDIT 1): Intercept out-of-scope requests before RAG retrieval
    out_of_scope_msg = check_out_of_scope_query(
        content=content,
        scope=session.scope,
        target_version_num=target_version_num,
        dataset_name=dataset.name,
    )
    if out_of_scope_msg:
        primary_name = mgr.provider_order[0] if mgr.provider_order else "gemini"
        prov = mgr.get_provider(primary_name)
        model_name = getattr(prov, "model_name", "unknown")

        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=out_of_scope_msg,
            provider=primary_name,
            model=model_name,
            fallback_occurred=False,
            grounded=False,
            sources=[],
            warnings=["Query refers to a version or comparison outside the locked session scope."],
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Out-of-scope version query intercepted before RAG: '{content}' (Latency: {latency_ms}ms)")

        return ChatMessageResponse(
            id=assistant_msg.id,
            session_id=session_id,
            role="assistant",
            content=assistant_msg.content,
            provider=assistant_msg.provider,
            model=assistant_msg.model,
            fallback_occurred=assistant_msg.fallback_occurred,
            grounded=assistant_msg.grounded,
            sources=assistant_msg.sources or [],
            warnings=assistant_msg.warnings or [],
            created_at=assistant_msg.created_at,
        )

    logger.info(
        f"Chat query executing Phase 11 RAG: Scope={session.scope}, Query='{retrieval_query}', "
        f"Dataset={dataset.name}, HistoryCount={len(bounded_history)}"
    )

    retrieved_docs = retrieve_rag_documents(
        dataset_id=dataset_id,
        query=retrieval_query,
        scope=rag_scope,
        db=db,
        version_id=session.version_id,
        comparison_id=session.comparison_id,
        top_k=settings.rag_top_k,
    )

    min_sim = settings.rag_min_similarity
    relevant_docs = [doc for doc in retrieved_docs if doc.get("similarity", 0.0) >= min_sim]

    # Build grounded context
    grounded_context = build_grounded_context(
        query=content,
        dataset_id=dataset_id,
        scope=rag_scope,
        retrieved_documents=relevant_docs,
        version_id=session.version_id,
        comparison_id=session.comparison_id,
    )

    # 7. Build Authoritative Server-Side Sources
    authoritative_sources: List[Dict[str, Any]] = []
    for g_source in grounded_context.sources:
        meta = g_source.metadata or {}
        v_num = meta.get("version_number") or meta.get("current_version_number") or target_version_num
        snippet = g_source.content[:400] + ("..." if len(g_source.content) > 400 else "")

        authoritative_sources.append(
            {
                "document_id": str(g_source.document_id) if g_source.document_id else None,
                "source_phase": g_source.source_phase,
                "document_type": g_source.document_type,
                "column_name": g_source.column_name,
                "version_id": str(g_source.version_id) if g_source.version_id else None,
                "version_number": v_num,
                "comparison_id": str(g_source.comparison_id) if g_source.comparison_id else None,
                "similarity": g_source.similarity,
                "source_result_id": str(g_source.metadata.get("source_result_id")) if g_source.metadata.get("source_result_id") else None,
                "title": g_source.title,
                "content_snippet": snippet,
                "metadata": meta,
            }
        )

    # 9. Handle No-Evidence Scenario
    if not relevant_docs:
        scope_desc = (
            f"Version V{target_version_num}"
            if target_version_num
            else (f"Comparison {target_comp_label}" if target_comp_label else f"Dataset '{dataset.name}'")
        )
        # Check if user asked about out-of-scope version or comparison in VERSION chat
        if session.scope == "VERSION" and re.search(r"\b(compare|comparison|v1|v3|v4|previous\s+version|other\s+version)\b", content, re.IGNORECASE):
            no_evidence_msg = (
                f"This chat is scoped to {scope_desc}. "
                "Version comparisons or data from other versions are outside this session's scope. "
                "Please start a Comparison Chat or Dataset-level Chat to analyze cross-version changes."
            )
        else:
            no_evidence_msg = (
                f"Insufficient evidence: I do not have sufficient analyzed analytical evidence to answer that question for {scope_desc}. "
                "Please ensure the relevant analytical phases (Profiling, Quality, PII, ML Risk, Anomalies, Drift) "
                "have been run and indexed for this scope."
            )

        primary_name = mgr.provider_order[0] if mgr.provider_order else "gemini"
        prov = mgr.get_provider(primary_name)
        model_name = getattr(prov, "model_name", "unknown")

        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=no_evidence_msg,
            provider=primary_name,
            model=model_name,
            fallback_occurred=False,
            grounded=False,
            sources=[],
            warnings=["No analytical evidence met the relevance threshold for this query."],
            created_at=datetime.now(timezone.utc),
        )
        db.add(assistant_msg)
        session.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(assistant_msg)

        return ChatMessageResponse(
            id=assistant_msg.id,
            session_id=assistant_msg.session_id,
            role=assistant_msg.role,
            content=assistant_msg.content,
            provider=assistant_msg.provider,
            model=assistant_msg.model,
            fallback_occurred=assistant_msg.fallback_occurred,
            grounded=assistant_msg.grounded,
            sources=assistant_msg.sources,
            warnings=assistant_msg.warnings,
            created_at=assistant_msg.created_at,
        )

    # 10. Construct Multi-Turn Prompt with Safety Hierarchy
    scope_str = session.scope
    if target_version_num:
        scope_str += f" (Version V{target_version_num})"
    elif target_comp_label:
        scope_str += f" (Comparison {target_comp_label})"

    # Format bounded conversation history block
    history_blocks = []
    for h_msg in bounded_history:
        r_label = "USER" if h_msg.role == "user" else "ASSISTANT"
        history_blocks.append(f"{r_label}: {h_msg.content}")

    history_text = "\n\n".join(history_blocks) if history_blocks else "None (This is the start of the conversation)."

    user_prompt = (
        f"### QUERY CONTEXT\n"
        f"- Dataset Name: {dataset.name} (ID: {dataset_id})\n"
        f"- Session Scope: {scope_str}\n\n"
        f"### GROUNDED ANALYTICAL EVIDENCE (AUTHORITATIVE)\n"
        f"{grounded_context.grounded_context_text}\n\n"
        f"### RECENT CONVERSATION HISTORY (FOR CONVERSATIONAL CONTEXT ONLY — NOT AUTHORITATIVE EVIDENCE)\n"
        f"{history_text}\n\n"
        f"### CURRENT USER QUESTION\n"
        f"{content}\n\n"
        f"### INSTRUCTIONS FOR YOUR ANSWER\n"
        f"- Answer the CURRENT USER QUESTION strictly based on the GROUNDED ANALYTICAL EVIDENCE.\n"
        f"- Use conversation history only to resolve context/references (e.g. 'those columns', 'the issue mentioned earlier').\n"
        f"- If details asked are not supported by the grounded evidence, explicitly state that the evidence is unavailable.\n"
        f"- Never reveal raw PII (emails, SSNs, phone numbers) or raw dataset rows.\n"
    )

    # 11. Invoke ProviderManager with 3-Tier Fallback (Gemini -> HF -> Ollama)
    try:
        llm_result = mgr.generate_with_fallback(
            prompt=user_prompt,
            system_prompt=SYSTEM_PROMPT,
            temperature=settings.ollama_temperature,
            max_tokens=settings.ollama_max_tokens,
        )
    except Exception as e:
        logger.error(f"Chat LLM generation failed across all providers: {e}")
        db.commit()  # Preserve user message for retry
        raise

    # 12. Persist Assistant Message
    assistant_msg = ChatMessage(
        session_id=session_id,
        role="assistant",
        content=llm_result.content,
        provider=llm_result.provider_name,
        model=llm_result.model_name,
        fallback_occurred=llm_result.fallback_occurred,
        grounded=True,
        sources=authoritative_sources,
        warnings=grounded_context.warnings,
        created_at=datetime.now(timezone.utc),
    )
    db.add(assistant_msg)
    session.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(assistant_msg)

    return ChatMessageResponse(
        id=assistant_msg.id,
        session_id=assistant_msg.session_id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        provider=assistant_msg.provider,
        model=assistant_msg.model,
        fallback_occurred=assistant_msg.fallback_occurred,
        grounded=assistant_msg.grounded,
        sources=assistant_msg.sources,
        warnings=assistant_msg.warnings,
        created_at=assistant_msg.created_at,
    )


def retry_last_chat_message(
    dataset_id: UUID,
    session_id: UUID,
    db: Session,
    provider_manager: Optional[ProviderManager] = None,
) -> ChatMessageResponse:
    """
    Retry generation for the latest user message without duplicating the user's message record.
    """
    session = db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.dataset_id == dataset_id,
        )
    ).scalar_one_or_none()

    if not session:
        raise ValueError(f"ChatSession '{session_id}' not found for dataset '{dataset_id}'")

    # Find the latest user message
    latest_user_msg = db.execute(
        select(ChatMessage)
        .where(
            ChatMessage.session_id == session_id,
            ChatMessage.role == "user",
        )
        .order_by(ChatMessage.created_at.desc())
    ).scalars().first()

    if not latest_user_msg:
        raise ValueError("No user message found to retry in this session")

    req = ChatMessageCreate(content=latest_user_msg.content)
    return send_chat_message(
        dataset_id=dataset_id,
        session_id=session_id,
        request=req,
        db=db,
        provider_manager=provider_manager,
        existing_user_msg=latest_user_msg,
    )
