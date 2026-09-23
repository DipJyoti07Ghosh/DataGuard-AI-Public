/**
 * DataGuard AI — Phase 14 AI Chat & Conversational Intelligence Page
 *
 * Persistent, multi-turn, dataset-scoped conversational interface.
 * Built on top of Phase 11 pgvector RAG, Phase 12 Assistant Service,
 * Phase 12A 3-tier Provider Fallback, and Phase 12B AssistantResponse rendering.
 *
 * Visual design: DATA GUARD AI workspace skin (.ch-* classes).
 * Backend contract: UNCHANGED.
 *   - getDatasets() / getDataset() / getDatasetComparisons()
 *   - getChatSessions() / getChatSession() / createChatSession() / updateChatSession() / deleteChatSession()
 *   - sendChatMessage() / retryChatMessage()
 *   - All field paths preserved.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import {
  getDatasets,
  getDataset,
  getDatasetComparisons,
  getChatSessions,
  getChatSession,
  createChatSession,
  updateChatSession,
  deleteChatSession,
  sendChatMessage,
  retryChatMessage,
} from '../api/client';
import AssistantResponse from '../components/assistant/AssistantResponse';
import './Chat.css';

export default function Chat() {
  const { datasetId: routeDatasetId, versionId: routeVersionId } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

  // Query parameters for deep linking
  const queryScope = searchParams.get('scope');
  const queryVersionId = searchParams.get('versionId') || routeVersionId;
  const queryComparisonId = searchParams.get('comparisonId');
  const queryInitialPrompt = searchParams.get('initialQuery');

  // Datasets & versions
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(routeDatasetId || '');
  const [datasetDetail, setDatasetDetail] = useState(null);
  const [comparisons, setComparisons] = useState([]);

  // Chat state
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);

  // UI state
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [canRetry, setCanRetry] = useState(false);

  // New chat modal
  const [showNewChatModal, setShowNewChatModal] = useState(false);
  const [modalScope, setModalScope] = useState('VERSION');
  const [modalVersionId, setModalVersionId] = useState('');
  const [modalComparisonId, setModalComparisonId] = useState('');
  const [modalTitle, setModalTitle] = useState('');
  const [creatingSession, setCreatingSession] = useState(false);

  // Rename
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  // Mobile drawer
  const [drawerOpen, setDrawerOpen] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sendingMessage]);

  // 1. Initial dataset load
  useEffect(() => {
    async function loadDatasets() {
      try {
        setLoading(true);
        const data = await getDatasets();
        setDatasets(data || []);
        if (data && data.length > 0) {
          const defaultId = routeDatasetId || data[0].id;
          setSelectedDatasetId(defaultId);
        }
      } catch (err) {
        setErrorMessage('Failed to load datasets: ' + err.message);
      } finally {
        setLoading(false);
      }
    }
    loadDatasets();
  }, [routeDatasetId]);

  // 2. Load dataset details + comparisons
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadDatasetDetails() {
      try {
        const detail = await getDataset(selectedDatasetId);
        setDatasetDetail(detail);

        try {
          const comps = await getDatasetComparisons(selectedDatasetId);
          setComparisons(comps || []);
        } catch {
          setComparisons([]);
        }

        if (detail?.versions && detail.versions.length > 0) {
          setModalVersionId(detail.versions[0].id);
        }
      } catch (err) {
        console.error('Error loading dataset detail:', err);
      }
    }
    loadDatasetDetails();
  }, [selectedDatasetId]);

  // 3. Load chat sessions
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadSessions() {
      try {
        const sessionList = await getChatSessions(selectedDatasetId);
        setSessions(sessionList || []);

        if (queryScope && queryInitialPrompt) {
          await handleAutoCreateSessionFromQuery(selectedDatasetId);
          return;
        }

        if (sessionList && sessionList.length > 0) {
          setActiveSessionId(sessionList[0].id);
        } else {
          setActiveSessionId(null);
          setActiveSession(null);
          setMessages([]);
        }
      } catch (err) {
        console.error('Error loading sessions:', err);
      }
    }
    loadSessions();
  }, [selectedDatasetId]);

  const handleAutoCreateSessionFromQuery = async (targetDatasetId) => {
    try {
      setSendingMessage(true);
      const payload = {
        scope: queryScope,
        version_id: queryScope === 'VERSION' ? queryVersionId : null,
        comparison_id: queryScope === 'COMPARISON' ? queryComparisonId : null,
        title: queryInitialPrompt.slice(0, 40),
      };
      const created = await createChatSession(targetDatasetId, payload);
      setSessions((prev) => [created, ...prev]);
      setActiveSessionId(created.id);
      setActiveSession(created);

      setSearchParams({});

      await sendChatMessage(targetDatasetId, created.id, queryInitialPrompt);
      const refreshed = await getChatSession(targetDatasetId, created.id);
      setActiveSession(refreshed);
      setMessages(refreshed.messages || []);
    } catch (err) {
      setErrorMessage('Auto-session creation failed: ' + err.message);
    } finally {
      setSendingMessage(false);
    }
  };

  // 4. Load active session
  useEffect(() => {
    if (!selectedDatasetId || !activeSessionId) {
      setActiveSession(null);
      setMessages([]);
      return;
    }

    async function loadActiveSession() {
      try {
        setErrorMessage(null);
        setCanRetry(false);
        const detail = await getChatSession(selectedDatasetId, activeSessionId);
        setActiveSession(detail);
        setMessages(detail.messages || []);
        setRenameValue(detail.title || '');
      } catch (err) {
        setErrorMessage('Failed to load conversation: ' + err.message);
      }
    }
    loadActiveSession();
  }, [selectedDatasetId, activeSessionId]);

  // 5. Send message
  const handleSendMessage = async (textToSend = null) => {
    const prompt = (textToSend || inputText).trim();
    if (!prompt || sendingMessage || !activeSessionId) return;

    setInputText('');
    setErrorMessage(null);
    setCanRetry(false);
    setSendingMessage(true);

    const tempUserMsg = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: prompt,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      await sendChatMessage(selectedDatasetId, activeSessionId, prompt);

      const refreshed = await getChatSession(selectedDatasetId, activeSessionId);
      setActiveSession(refreshed);
      setMessages(refreshed.messages || []);

      setSessions((prev) =>
        prev.map((s) =>
          s.id === activeSessionId
            ? { ...s, title: refreshed.title, updated_at: refreshed.updated_at }
            : s,
        ),
      );
    } catch (err) {
      setErrorMessage(
        err.message || 'AI Assistant is temporarily unavailable. Please try again.',
      );
      setCanRetry(true);
    } finally {
      setSendingMessage(false);
    }
  };

  // 6. Retry
  const handleRetry = async () => {
    if (!activeSessionId || sendingMessage) return;

    setErrorMessage(null);
    setCanRetry(false);
    setSendingMessage(true);

    try {
      await retryChatMessage(selectedDatasetId, activeSessionId);
      const refreshed = await getChatSession(selectedDatasetId, activeSessionId);
      setActiveSession(refreshed);
      setMessages(refreshed.messages || []);
    } catch (err) {
      setErrorMessage('Retry failed: ' + err.message);
      setCanRetry(true);
    } finally {
      setSendingMessage(false);
    }
  };

  // 7. Create new session
  const handleCreateSessionSubmit = async (e) => {
    e.preventDefault();
    if (!selectedDatasetId || creatingSession) return;

    setCreatingSession(true);
    setErrorMessage(null);

    try {
      const payload = {
        scope: modalScope,
        version_id: modalScope === 'VERSION' ? modalVersionId : null,
        comparison_id: modalScope === 'COMPARISON' ? modalComparisonId : null,
        title: modalTitle.trim() || 'New Chat',
      };

      const created = await createChatSession(selectedDatasetId, payload);
      setSessions((prev) => [created, ...prev]);
      setActiveSessionId(created.id);
      setActiveSession(created);
      setMessages([]);
      setShowNewChatModal(false);
      setModalTitle('');
      setDrawerOpen(false);
    } catch (err) {
      setErrorMessage('Failed to create chat: ' + err.message);
    } finally {
      setCreatingSession(false);
    }
  };

  // 8. Rename
  const handleRenameSubmit = async () => {
    if (!renameValue.trim() || !activeSessionId) return;

    try {
      const updated = await updateChatSession(selectedDatasetId, activeSessionId, {
        title: renameValue.trim(),
      });
      setActiveSession((prev) => ({ ...prev, title: updated.title }));
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSessionId ? { ...s, title: updated.title } : s)),
      );
      setIsRenaming(false);
    } catch (err) {
      setErrorMessage('Failed to rename session: ' + err.message);
    }
  };

  // 9. Delete
  const handleDeleteSession = async (sessionIdToDelete, e) => {
    if (e) e.stopPropagation();
    if (!window.confirm('Are you sure you want to delete this conversation?')) return;

    try {
      await deleteChatSession(selectedDatasetId, sessionIdToDelete);
      const remaining = sessions.filter((s) => s.id !== sessionIdToDelete);
      setSessions(remaining);
      if (activeSessionId === sessionIdToDelete) {
        if (remaining.length > 0) {
          setActiveSessionId(remaining[0].id);
        } else {
          setActiveSessionId(null);
          setActiveSession(null);
          setMessages([]);
        }
      }
    } catch (err) {
      setErrorMessage('Failed to delete chat session: ' + err.message);
    }
  };

  const groupSessionsByDate = (sessionList) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const groups = { Today: [], Yesterday: [], Earlier: [] };

    sessionList.forEach((s) => {
      const date = new Date(s.updated_at);
      if (date >= today) groups.Today.push(s);
      else if (date >= yesterday) groups.Yesterday.push(s);
      else groups.Earlier.push(s);
    });

    return groups;
  };

  const sessionGroups = groupSessionsByDate(sessions);

  const getActiveVersionLabel = () => {
    if (!activeSession) return '';
    if (activeSession.scope === 'VERSION') {
      const v = datasetDetail?.versions?.find((ver) => ver.id === activeSession.version_id);
      return v ? `Version V${v.version_number}` : 'Version';
    }
    if (activeSession.scope === 'COMPARISON') {
      const c = comparisons.find((comp) => comp.id === activeSession.comparison_id);
      return c
        ? `Comparison V${c.baseline_version?.version_number || 1} ➔ V${c.current_version?.version_number || 2}`
        : 'Comparison';
    }
    return 'Dataset Scope';
  };

  const getScopeClass = (scope) => {
    if (scope === 'COMPARISON') return 'ch-scope ch-scope--comparison';
    if (scope === 'DATASET') return 'ch-scope ch-scope--dataset';
    return 'ch-scope ch-scope--version';
  };

  return (
    <div className="ch-page">
      {/* Mobile drawer toggle */}
      <button
        type="button"
        className="ch-drawer-toggle"
        onClick={() => setDrawerOpen((v) => !v)}
        aria-label="Toggle conversations"
      >
        ☰
      </button>

      {/* ================= SIDEBAR ================= */}
      <aside className={`ch-sidebar ${drawerOpen ? 'ch-sidebar--open' : ''}`}>
        <div className="ch-sidebar-head">
          <button
            type="button"
            className="ch-new-btn"
            onClick={() => {
              setShowNewChatModal(true);
              if (datasetDetail?.versions?.length > 0) {
                setModalVersionId(datasetDetail.versions[0].id);
              }
            }}
          >
            <span>+</span> New Chat
          </button>

          <select
            className="ch-dataset-select"
            value={selectedDatasetId}
            onChange={(e) => {
              setSelectedDatasetId(e.target.value);
              navigate(`/datasets/${e.target.value}/chat`);
              setDrawerOpen(false);
            }}
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                🗃️ {d.name}
              </option>
            ))}
          </select>
        </div>

        <div className="ch-history">
          {Object.entries(sessionGroups).map(([groupName, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={groupName} className="ch-history-group">
                <div className="ch-history-title">{groupName}</div>
                {items.map((sess) => {
                  const isActive = sess.id === activeSessionId;
                  return (
                    <div
                      key={sess.id}
                      className={`ch-session ${isActive ? 'ch-session--active' : ''}`}
                      onClick={() => {
                        setActiveSessionId(sess.id);
                        setDrawerOpen(false);
                      }}
                    >
                      <div className="ch-session-content">
                        <span className="ch-session-title">
                          {sess.title || 'New Chat'}
                        </span>
                        <span className="ch-session-meta">
                          <span>{sess.scope}</span>
                          <span>•</span>
                          <span>{sess.message_count} msgs</span>
                        </span>
                      </div>
                      <button
                        type="button"
                        className="ch-session-delete"
                        title="Delete Chat"
                        onClick={(e) => handleDeleteSession(sess.id, e)}
                      >
                        ✕
                      </button>
                    </div>
                  );
                })}
              </div>
            );
          })}

          {sessions.length === 0 && (
            <div className="ch-history-empty">
              No conversations yet. Start a new chat!
            </div>
          )}
        </div>
      </aside>

      {/* ================= MAIN AREA ================= */}
      <main className="ch-main">
        {activeSession ? (
          <>
            {/* Header */}
            <header className="ch-header">
              <div className="ch-header-info">
                <div className="ch-header-top">
                  {isRenaming ? (
                    <div className="ch-rename-row">
                      <input
                        type="text"
                        className="ch-rename-input"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleRenameSubmit()}
                        autoFocus
                      />
                      <button type="button" className="ch-btn ch-btn--primary ch-btn--xs" onClick={handleRenameSubmit}>
                        Save
                      </button>
                      <button type="button" className="ch-btn ch-btn--ghost ch-btn--xs" onClick={() => setIsRenaming(false)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <h2 className="ch-title">{activeSession.title || 'Conversation'}</h2>
                      <button
                        type="button"
                        className="ch-icon-btn"
                        title="Rename Chat"
                        onClick={() => {
                          setRenameValue(activeSession.title || '');
                          setIsRenaming(true);
                        }}
                      >
                        ✏️
                      </button>
                    </>
                  )}
                  <span className={getScopeClass(activeSession.scope)}>
                    {activeSession.scope}
                  </span>
                </div>
                <div className="ch-header-sub">
                  <span>
                    Dataset: <strong>{datasetDetail?.name || 'Loading…'}</strong>
                  </span>
                  <span>•</span>
                  <span>
                    Scope: <strong>{getActiveVersionLabel()}</strong>
                  </span>
                </div>
              </div>

              <button
                type="button"
                className="ch-icon-btn ch-icon-btn--danger"
                title="Delete Session"
                onClick={(e) => handleDeleteSession(activeSession.id, e)}
              >
                🗑️ Delete
              </button>
            </header>

            {/* Messages */}
            <div className="ch-messages">
              {messages.length === 0 ? (
                <div className="ch-empty">
                  <div className="ch-empty-icon">🛡️</div>
                  <h3>Ask anything about this dataset</h3>
                  <p>
                    Conversations are grounded in verified analytical evidence from
                    Phase 11 RAG. Zero raw PII is exposed.
                  </p>

                  <div className="ch-suggest-grid">
                    {activeSession.scope === 'COMPARISON' ? (
                      <>
                        <SuggestBtn
                          icon="📊"
                          label="What changed between these versions?"
                          onClick={() => handleSendMessage('What changed between these versions?')}
                        />
                        <SuggestBtn
                          icon="🌊"
                          label="What are the biggest drift drivers?"
                          onClick={() => handleSendMessage('What are the biggest drift drivers?')}
                        />
                        <SuggestBtn
                          icon="⚠️"
                          label="Explain new anomalies detected"
                          onClick={() => handleSendMessage('Explain new anomalies detected in this version')}
                        />
                      </>
                    ) : (
                      <>
                        <SuggestBtn
                          icon="🔍"
                          label="What are the biggest quality problems?"
                          onClick={() => handleSendMessage('What are the biggest data quality problems in this dataset?')}
                        />
                        <SuggestBtn
                          icon="🚨"
                          label="Which columns are highest risk?"
                          onClick={() => handleSendMessage('Which columns have the highest risk and why?')}
                        />
                        <SuggestBtn
                          icon="🔒"
                          label="Are there any privacy concerns?"
                          onClick={() => handleSendMessage('Are there any privacy or PII concerns?')}
                        />
                        <SuggestBtn
                          icon="🛠️"
                          label="What should I investigate first?"
                          onClick={() => handleSendMessage('What should I investigate and remediate first?')}
                        />
                      </>
                    )}
                  </div>
                </div>
              ) : (
                messages.map((msg, idx) => {
                  const isUser = msg.role === 'user';
                  const isLatestAssistant = !isUser && idx === messages.length - 1;

                  return (
                    <div key={msg.id || idx} className={`ch-message ch-message--${msg.role}`}>
                      {isUser ? (
                        <div className="ch-user-bubble">
                          <div>{msg.content}</div>
                          <div className="ch-user-time">
                            {new Date(msg.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="ch-assistant-wrap">
                          <AssistantResponse
                            response={{
                              answer: msg.content,
                              sources: msg.sources || [],
                              warnings: msg.warnings || [],
                              grounded: msg.grounded !== false,
                              provider: msg.provider || 'gemini',
                              model: msg.model || 'gemini-3.6-flash',
                              fallback_occurred: msg.fallback_occurred || false,
                            }}
                          />

                          {isLatestAssistant && !sendingMessage && (
                            <div className="ch-followups">
                              <button
                                type="button"
                                className="ch-followup"
                                onClick={() => handleSendMessage('Which columns are responsible for that?')}
                              >
                                <span>🔍</span> Which columns are responsible?
                              </button>
                              <button
                                type="button"
                                className="ch-followup"
                                onClick={() => handleSendMessage('Explain the highest-risk column in detail')}
                              >
                                <span>🚨</span> Explain the highest-risk column
                              </button>
                              <button
                                type="button"
                                className="ch-followup"
                                onClick={() => handleSendMessage('What about privacy and sensitive findings?')}
                              >
                                <span>🔒</span> Check privacy findings
                              </button>
                              <button
                                type="button"
                                className="ch-followup"
                                onClick={() => handleSendMessage('What should I investigate and fix first?')}
                              >
                                <span>🛠️</span> What should I fix first?
                              </button>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })
              )}

              {sendingMessage && (
                <div className="ch-loading">
                  <span className="ch-loading-pulse" />
                  <span>Analyzing grounded Phase 11 analytical evidence…</span>
                </div>
              )}

              {errorMessage && (
                <div className="ch-retry">
                  <span>⚠️ {errorMessage}</span>
                  {canRetry && (
                    <button type="button" className="ch-btn ch-btn--danger ch-btn--xs" onClick={handleRetry}>
                      Retry
                    </button>
                  )}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Composer */}
            <div className="ch-composer">
              <div className="ch-composer-input">
                <textarea
                  className="ch-textarea"
                  placeholder="Ask a grounded analytical question about this dataset…"
                  rows={1}
                  value={inputText}
                  onChange={(e) => setInputText(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault();
                      handleSendMessage();
                    }
                  }}
                  disabled={sendingMessage}
                />
                <button
                  type="button"
                  className="ch-send"
                  onClick={() => handleSendMessage()}
                  disabled={!inputText.trim() || sendingMessage}
                >
                  {sendingMessage ? '…' : 'Send ➤'}
                </button>
              </div>
              <div className="ch-composer-hint">
                <span>Press Enter to send, Shift + Enter for newline</span>
                <span>{inputText.length} / 8000</span>
              </div>
            </div>
          </>
        ) : (
          <div className="ch-empty ch-empty--full">
            <div className="ch-empty-icon">💬</div>
            <h3>Select or start a chat session</h3>
            <p>
              Choose a conversation from the sidebar or start a new grounded chat
              session.
            </p>
            <button
              type="button"
              className="ch-btn ch-btn--primary"
              onClick={() => {
                setShowNewChatModal(true);
                if (datasetDetail?.versions?.length > 0) {
                  setModalVersionId(datasetDetail.versions[0].id);
                }
              }}
            >
              + Create New Chat Session
            </button>
          </div>
        )}
      </main>

      {/* ================= NEW CHAT MODAL ================= */}
      {showNewChatModal && (
        <div className="ch-modal-backdrop" onClick={() => setShowNewChatModal(false)}>
          <div className="ch-modal" onClick={(e) => e.stopPropagation()}>
            <div className="ch-modal-head">
              <h3>Start New AI Chat</h3>
              <button
                type="button"
                className="ch-icon-btn"
                onClick={() => setShowNewChatModal(false)}
                aria-label="Close"
              >
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSessionSubmit} className="ch-modal-form">
              <label className="ch-field">
                <span>Dataset</span>
                <select
                  value={selectedDatasetId}
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>

              <label className="ch-field">
                <span>Operational Scope (Locked)</span>
                <select
                  value={modalScope}
                  onChange={(e) => setModalScope(e.target.value)}
                >
                  <option value="VERSION">VERSION (Specific Dataset Version)</option>
                  <option value="COMPARISON">COMPARISON (Drift / Version Diff)</option>
                  <option value="DATASET">DATASET (Dataset Wide)</option>
                </select>
              </label>

              {modalScope === 'VERSION' && (
                <label className="ch-field">
                  <span>Target Version</span>
                  <select
                    value={modalVersionId}
                    onChange={(e) => setModalVersionId(e.target.value)}
                    required
                  >
                    {datasetDetail?.versions?.map((v) => (
                      <option key={v.id} value={v.id}>
                        Version V{v.version_number} (
                        {new Date(v.created_at).toLocaleDateString()})
                      </option>
                    ))}
                  </select>
                </label>
              )}

              {modalScope === 'COMPARISON' && (
                <label className="ch-field">
                  <span>Target Comparison</span>
                  {comparisons.length === 0 ? (
                    <div className="ch-muted">
                      No version comparisons found. Create a comparison first on the
                      Compare page.
                    </div>
                  ) : (
                    <select
                      value={modalComparisonId || comparisons[0]?.id || ''}
                      onChange={(e) => setModalComparisonId(e.target.value)}
                      required
                    >
                      {comparisons.map((c) => (
                        <option key={c.id} value={c.id}>
                          V{c.baseline_version?.version_number || 1} ➔ V
                          {c.current_version?.version_number || 2}
                        </option>
                      ))}
                    </select>
                  )}
                </label>
              )}

              <label className="ch-field">
                <span>Conversation Title (Optional)</span>
                <input
                  type="text"
                  value={modalTitle}
                  onChange={(e) => setModalTitle(e.target.value)}
                  placeholder="e.g. V2 Quality Analysis"
                  maxLength={60}
                />
              </label>

              <div className="ch-modal-actions">
                <button
                  type="button"
                  className="ch-btn ch-btn--ghost"
                  onClick={() => setShowNewChatModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ch-btn ch-btn--primary"
                  disabled={creatingSession || (modalScope === 'COMPARISON' && comparisons.length === 0)}
                >
                  {creatingSession ? 'Creating…' : 'Start Chat'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Helper ---------- */
function SuggestBtn({ icon, label, onClick }) {
  return (
    <button type="button" className="ch-suggest" onClick={onClick}>
      <span className="ch-suggest-icon">{icon}</span>
      <span>{label}</span>
    </button>
  );
}