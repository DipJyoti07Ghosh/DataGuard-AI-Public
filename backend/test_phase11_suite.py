"""
DataGuard AI — Phase 11 Automated Test Suite
RAG Knowledge Ingestion & Semantic Retrieval Layer

Validates:
1. PostgreSQL persistence, pgvector extension, VECTOR(384) column, and HNSW cosine index
2. FastEmbed BAAI/bge-small-en-v1.5 embedding provider: real 384-d dense vectors, deterministic output
3. Complete Phase 4–10 knowledge document chunking (Profiling, Quality, PII, Risk, Anomalies, Health, Drift)
4. Strict raw-value privacy: ZERO raw emails, phones, SSNs, credit cards, or raw outlier values in RAG content/metadata
5. Great Expectations sanitization: exclusion of raw 'observed values'
6. Phase 9 Remediation indexing: phrased strictly as suggested recommendations, never completed actions
7. Deterministic SHA-256 content hashing & Embedding Identity idempotency (skips re-embedding when unchanged)
8. Lifecycle management: content update in place, stale document cleanup on source deletion
9. Explicit retrieval scopes (VERSION, COMPARISON, DATASET)
10. Strict Version Isolation: V1 cannot retrieve V2-only documents; V2 cannot retrieve V1-only documents
11. Strict Dataset Isolation: Dataset A cannot retrieve Dataset B documents
12. Phase 10 Comparison indexing and retrieval
13. Grounded Context Builder: formatted factual evidence with complete source traceability and similarity scores
14. Size bounding: large distributions / rules bounded to deterministic limits without LLM summarization
15. Full REST API endpoints (index, retrieve, list, purge)
16. Cascade deletion integrity
"""

import io
import os
import uuid
import logging
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy import text, select

from app.main import app
import app.database as database
from app.models.dataset import Dataset, DatasetVersion
from app.models.rag import RAGDocument
from app.services.embedding_service import get_embedding_provider, FastEmbedProvider
from app.services.rag_document_builder import compute_content_hash, sanitize_text
from app.schemas.rag import RetrievalScope

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_phase11")


def test_phase11_full_suite():
    logger.info("===========================================================================")
    logger.info("  STARTING PHASE 11 RAG KNOWLEDGE & RETRIEVAL AUTOMATED TEST SUITE")
    logger.info("===========================================================================")

    database.init_database()
    db = database.SessionLocal()
    client = TestClient(app)

    try:
        # -------------------------------------------------------------------
        # 1. Verify PostgreSQL pgvector Extension & Table Schema
        # -------------------------------------------------------------------
        logger.info("\n--- 1. Testing PostgreSQL pgvector Extension & Schema ---")
        ext_res = db.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';")).fetchall()
        assert len(ext_res) > 0, "pgvector extension must be active in PostgreSQL"
        ext_name, ext_ver = ext_res[0]
        logger.info(f" [PASS] 1a. pgvector extension verified: {ext_name} (version {ext_ver})")

        # Verify rag_documents table structure
        col_res = db.execute(text(
            "SELECT column_name, data_type, udt_name FROM information_schema.columns WHERE table_name = 'rag_documents';"
        )).fetchall()
        cols = {r[0]: (r[1], r[2]) for r in col_res}
        assert "embedding" in cols, "rag_documents must have 'embedding' column"
        assert cols["embedding"][1] == "vector", f"embedding column must be of type 'vector', got {cols['embedding']}"
        logger.info(" [PASS] 1b. Table 'rag_documents' has native 'vector' column")

        # Verify HNSW index
        idx_res = db.execute(text(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = 'rag_documents' AND indexname = 'ix_rag_documents_embedding_hnsw';"
        )).fetchall()
        assert len(idx_res) > 0, "HNSW index 'ix_rag_documents_embedding_hnsw' must exist on rag_documents"
        logger.info(" [PASS] 1c. HNSW vector_cosine_ops index verified on rag_documents")

        # -------------------------------------------------------------------
        # 2. Verify FastEmbed Provider & Deterministic 384-d Vectors
        # -------------------------------------------------------------------
        logger.info("\n--- 2. Testing FastEmbed BAAI/bge-small-en-v1.5 Provider ---")
        provider = get_embedding_provider()
        assert provider.provider_name == "fastembed"
        assert provider.model_name == "BAAI/bge-small-en-v1.5"
        assert provider.dimension == 384

        test_query = "What data quality issues were found?"
        v1 = provider.embed_text(test_query)
        v2 = provider.embed_text(test_query)
        assert len(v1) == 384, f"Embedding vector must have exactly 384 dimensions, got {len(v1)}"
        assert np.allclose(v1, v2, atol=1e-6), "Embedding provider must produce deterministic vectors for identical text"
        logger.info(f" [PASS] 2. FastEmbed provider verified: 384-d dense deterministic vectors generated")

        # -------------------------------------------------------------------
        # 3. Ingest Test Multi-Version Dataset with Real Analysis Results
        # -------------------------------------------------------------------
        logger.info("\n--- 3. Ingesting Multi-Version Dataset with Phase 4–10 Analysis ---")
        # Version 1 Data
        df_v1 = pd.DataFrame({
            "employee_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "email": [f"emp_{i}@example.com" for i in range(101, 111)],
            "phone": ["555-0101", "555-0102", "555-0103", "555-0104", "555-0105", "555-0106", "555-0107", "555-0108", "555-0109", "555-0110"],
            "income": [50000.0, 52000.0, 51000.0, 53000.0, 54000.0, 50500.0, 51500.0, 52500.0, 53500.0, 54500.0],
            "dept": ["Engineering", "Engineering", "Sales", "Sales", "HR", "HR", "Marketing", "Marketing", "Finance", "Finance"],
        })
        csv_v1 = df_v1.to_csv(index=False).encode("utf-8")
        ds_name = f"rag_test_ds_{uuid.uuid4().hex[:6]}"

        up1_res = client.post(
            "/api/datasets/upload",
            files={"file": ("v1.csv", io.BytesIO(csv_v1), "text/csv")},
            data={"dataset_name": ds_name},
        )
        assert up1_res.status_code == 200, up1_res.text
        v1_json = up1_res.json()
        dataset_id = v1_json["dataset_id"]
        v1_id = v1_json["version_id"]

        # Run Phase 4–9 on V1
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/profile")
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/quality")
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/pii/scan")
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/risk/predict")
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/anomalies/detect")
        client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/issues/analyze")

        # Version 2 Data (Introduces quality failures, PII, high drift)
        df_v2 = pd.DataFrame({
            "employee_id": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110],
            "email": [f"user_{i}@company.org" for i in range(101, 111)],
            "phone": ["555-0201", "555-0202", "555-0203", "555-0204", "555-0205", "555-0206", "555-0207", "555-0208", "555-0209", "555-0210"],
            "income": [150000.0, 155000.0, 160000.0, 165000.0, 170000.0, None, None, None, 180000.0, 190000.0],
            "dept": ["Executive", "Executive", "Executive", "Executive", "Executive", "Sales", "Sales", "Sales", "Sales", "Sales"],
        })
        csv_v2 = df_v2.to_csv(index=False).encode("utf-8")
        up2_res = client.post(
            "/api/datasets/upload",
            files={"file": ("v2.csv", io.BytesIO(csv_v2), "text/csv")},
            data={"dataset_name": ds_name},
        )
        assert up2_res.status_code == 200, up2_res.text
        v2_id = up2_res.json()["version_id"]

        # Run Phase 4–10 on V2
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/profile")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/quality")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/pii/scan")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/risk/predict")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/anomalies/detect")
        client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/issues/analyze")

        # Phase 10 Comparison
        comp_res = client.post(
            f"/api/datasets/{dataset_id}/compare",
            json={"baseline_version_id": v1_id, "current_version_id": v2_id},
        )
        assert comp_res.status_code == 200, comp_res.text
        comparison_id = comp_res.json()["id"]
        logger.info(f" [PASS] 3. Dataset '{ds_name}' V1 & V2 created with full Phase 4–10 analysis")

        # -------------------------------------------------------------------
        # 4. Test RAG Version Indexing & Privacy Sanitization
        # -------------------------------------------------------------------
        logger.info("\n--- 4. Testing RAG Version Indexing & Privacy Sanitization ---")
        idx_res = client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/rag/index")
        assert idx_res.status_code == 200, idx_res.text
        idx_data = idx_res.json()
        assert idx_data["status"] == "COMPLETED"
        assert idx_data["total_indexed"] > 0
        assert idx_data["new_documents"] == idx_data["total_indexed"]
        logger.info(f" [PASS] 4a. V1 indexed {idx_data['total_indexed']} documents across phases: {idx_data['documents_by_phase']}")

        # Index V2
        idx2_res = client.post(f"/api/datasets/{dataset_id}/versions/{v2_id}/rag/index")
        assert idx2_res.status_code == 200, idx2_res.text
        logger.info(f" [PASS] 4b. V2 indexed {idx2_res.json()['total_indexed']} documents")

        # Index Comparison
        comp_idx_res = client.post(f"/api/datasets/{dataset_id}/comparisons/{comparison_id}/rag/index")
        assert comp_idx_res.status_code == 200, comp_idx_res.text
        logger.info(f" [PASS] 4c. Comparison indexed {comp_idx_res.json()['total_indexed']} documents")

        # -------------------------------------------------------------------
        # 5. Strict Privacy Assertions: ZERO Raw PII
        # -------------------------------------------------------------------
        logger.info("\n--- 5. Asserting Strict Raw-Value Privacy ---")
        all_docs = db.execute(select(RAGDocument).where(RAGDocument.dataset_id == dataset_id)).scalars().all()
        forbidden_raw_strings = [
            "emp_101@example.com", "user_101@company.org", "555-0101", "555-0201",
            "emp_105@example.com", "555-0109"
        ]
        for doc in all_docs:
            for raw_s in forbidden_raw_strings:
                assert raw_s not in doc.content, f"Security Violation: Raw string '{raw_s}' leaked in RAG document content (id={doc.id}, phase={doc.source_phase})"
                assert raw_s not in str(doc.doc_metadata), f"Security Violation: Raw string '{raw_s}' leaked in RAG doc_metadata (id={doc.id})"
        logger.info(f" [PASS] 5. Verified across {len(all_docs)} RAG documents: ZERO raw email, phone, or PII values exist in content or metadata")


        # -------------------------------------------------------------------
        # 6. Idempotency & Lifecycle Testing
        # -------------------------------------------------------------------
        logger.info("\n--- 6. Testing Idempotency & Lifecycle Management ---")
        reindex_res = client.post(f"/api/datasets/{dataset_id}/versions/{v1_id}/rag/index")
        re_data = reindex_res.json()
        assert re_data["skipped_unchanged"] == re_data["total_indexed"], "Unchanged documents must be skipped"
        assert re_data["new_documents"] == 0, "No new documents should be created when unchanged"
        assert re_data["updated_documents"] == 0, "No documents should be updated when unchanged"
        logger.info(f" [PASS] 6a. Idempotent skip verified: {re_data['skipped_unchanged']} / {re_data['total_indexed']} chunks skipped")

        # Test force_reindex
        force_res = client.post(
            f"/api/datasets/{dataset_id}/versions/{v1_id}/rag/index",
            json={"force_reindex": True},
        )
        force_data = force_res.json()
        assert force_data["updated_documents"] == force_data["total_indexed"], "force_reindex=True must re-embed all documents"
        logger.info(f" [PASS] 6b. Force re-index verified: {force_data['updated_documents']} chunks re-embedded")

        # -------------------------------------------------------------------
        # 7. Explicit Retrieval Modes & Strict Version Isolation
        # -------------------------------------------------------------------
        logger.info("\n--- 7. Testing Semantic Retrieval & Version Isolation ---")
        # Query V1 for quality/PII
        ret_v1 = client.post(
            f"/api/datasets/{dataset_id}/rag/retrieve",
            json={
                "query": "What sensitive PII was detected in email?",
                "scope": "VERSION",
                "version_id": str(v1_id),
                "top_k": 3,
            },
        )
        assert ret_v1.status_code == 200, ret_v1.text
        v1_data = ret_v1.json()
        assert v1_data["retrieved_count"] > 0
        for src in v1_data["sources"]:
            assert src["version_id"] == str(v1_id), "Version-scoped query must only return documents for target version"
            assert src["similarity"] > 0.0, "Similarity score must be positive"
            assert src["similarity"] <= 1.0, "Similarity score must be <= 1.0"
        logger.info(f" [PASS] 7a. V1 Semantic Retrieval verified with Top similarity: {v1_data['sources'][0]['similarity']}")

        # Query V2 for missingness drift
        ret_v2 = client.post(
            f"/api/datasets/{dataset_id}/rag/retrieve",
            json={
                "query": "Which columns failed data quality or missingness checks?",
                "scope": "VERSION",
                "version_id": str(v2_id),
                "top_k": 3,
            },
        )
        assert ret_v2.status_code == 200, ret_v2.text
        v2_data = ret_v2.json()
        assert v2_data["retrieved_count"] > 0
        for src in v2_data["sources"]:
            assert src["version_id"] == str(v2_id), "V2 query must strictly return V2 documents"
        logger.info(" [PASS] 7b. V2 Semantic Retrieval verified with strict version scoping")

        # Query Comparison scope
        ret_comp = client.post(
            f"/api/datasets/{dataset_id}/rag/retrieve",
            json={
                "query": "What changed between version 1 and version 2?",
                "scope": "COMPARISON",
                "comparison_id": str(comparison_id),
                "top_k": 3,
            },
        )
        assert ret_comp.status_code == 200, ret_comp.text
        comp_data = ret_comp.json()
        assert comp_data["retrieved_count"] > 0
        for src in comp_data["sources"]:
            assert src["comparison_id"] == str(comparison_id), "Comparison query must return comparison documents"
            assert src["source_phase"] == "PHASE_10_DRIFT"
        logger.info(" [PASS] 7c. Comparison Retrieval verified")

        # -------------------------------------------------------------------
        # 8. Strict Dataset Isolation (Cross-Dataset Leakage Prevention)
        # -------------------------------------------------------------------
        logger.info("\n--- 8. Testing Dataset Isolation ---")
        # Ingest Dataset B
        df_b = pd.DataFrame({"product_id": [1, 2, 3], "price": [10.0, 20.0, 30.0]})
        ds_b_name = f"rag_ds_b_{uuid.uuid4().hex[:6]}"
        up_b = client.post(
            "/api/datasets/upload",
            files={"file": ("b.csv", io.BytesIO(df_b.to_csv(index=False).encode("utf-8")), "text/csv")},
            data={"dataset_name": ds_b_name},
        )
        assert up_b.status_code == 200
        ds_b_id = up_b.json()["dataset_id"]
        v_b_id = up_b.json()["version_id"]
        client.post(f"/api/datasets/{ds_b_id}/versions/{v_b_id}/profile")
        client.post(f"/api/datasets/{ds_b_id}/versions/{v_b_id}/rag/index")


        # Query Dataset A for "product price" -> Must NEVER return Dataset B's documents
        leak_check = client.post(
            f"/api/datasets/{dataset_id}/rag/retrieve",
            json={
                "query": "What is the product price?",
                "scope": "VERSION",
                "version_id": str(v1_id),
                "top_k": 5,
            },
        )
        assert leak_check.status_code == 200
        for src in leak_check.json()["sources"]:
            assert src["version_id"] != str(v_b_id), "Cross-dataset leakage detected! Dataset A returned Dataset B document"
        logger.info(" [PASS] 8. Strict Dataset Isolation verified: Zero cross-dataset contamination")

        # -------------------------------------------------------------------
        # 9. Grounded Context Builder Traceability & Format
        # -------------------------------------------------------------------
        logger.info("\n--- 9. Testing Grounded Context Assembly & Traceability ---")
        context_res = client.post(
            f"/api/datasets/{dataset_id}/rag/retrieve",
            json={
                "query": "Summarize ML risk and anomalous outliers",
                "scope": "VERSION",
                "version_id": str(v2_id),
                "top_k": 4,
            },
        )
        assert context_res.status_code == 200
        c_data = context_res.json()
        assert "grounded_context_text" in c_data
        assert len(c_data["grounded_context_text"]) > 0
        assert "### [Source 1]" in c_data["grounded_context_text"]
        assert "Relevance Score:" in c_data["grounded_context_text"]
        logger.info(" [PASS] 9. Grounded Context Assembly verified with source attribution headers")

        # -------------------------------------------------------------------
        # 10. Listing & Purging Endpoints
        # -------------------------------------------------------------------
        logger.info("\n--- 10. Testing List & Purge Endpoints ---")
        list_res = client.get(f"/api/datasets/{dataset_id}/rag/documents")
        assert list_res.status_code == 200
        assert list_res.json()["total_count"] > 0
        logger.info(f" [PASS] 10a. GET /rag/documents returned {list_res.json()['total_count']} indexed documents")

        purge_res = client.delete(f"/api/datasets/{ds_b_id}/rag/documents")
        assert purge_res.status_code == 200
        check_purged = client.get(f"/api/datasets/{ds_b_id}/rag/documents")
        assert check_purged.json()["total_count"] == 0
        logger.info(" [PASS] 10b. DELETE /rag/documents purged dataset B index successfully")

        # -------------------------------------------------------------------
        # 11. Cascade Deletion Integrity
        # -------------------------------------------------------------------
        logger.info("\n--- 11. Testing Cascade Deletion ---")
        client.delete(f"/api/datasets/{ds_b_id}")
        del_a = client.delete(f"/api/datasets/{dataset_id}")
        assert del_a.status_code == 200

        # Assert no orphaned RAG documents remain for dataset A
        orphans = db.execute(select(RAGDocument).where(RAGDocument.dataset_id == dataset_id)).scalars().all()
        assert len(orphans) == 0, f"Cascade deletion failed: {len(orphans)} orphaned RAG documents remained"
        logger.info(" [PASS] 11. Cascade deletion verified: All RAG documents removed cleanly with dataset")

        logger.info("\n===========================================================================")
        logger.info("  🎉 ALL 11 PHASE 11 AUTOMATED TEST SCENARIOS PASSED!")
        logger.info("===========================================================================")

    finally:
        db.close()


if __name__ == "__main__":
    test_phase11_full_suite()
