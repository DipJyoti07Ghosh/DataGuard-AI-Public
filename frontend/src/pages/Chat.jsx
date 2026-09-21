/**
 * DataGuard AI — Phase 14 AI Chat & Conversational Intelligence Page
 *
 * Persistent, multi-turn, dataset-scoped conversational interface.
 * Built on top of Phase 11 pgvector RAG, Phase 12 Assistant Service,
 * Phase 12A 3-tier Provider Fallback, and Phase 12B AssistantResponse rendering.
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

  // URL Query Parameters for deep linking from Dashboard / Issues / Compare
  const queryScope = searchParams.get('scope');
  const queryVersionId = searchParams.get('versionId') || routeVersionId;
  const queryComparisonId = searchParams.get('comparisonId');
  const queryInitialPrompt = searchParams.get('initialQuery');

  // Datasets & Versions State
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(routeDatasetId || '');
  const [datasetDetail, setDatasetDetail] = useState(null);
  const [comparisons, setComparisons] = useState([]);

  // Chat Sessions & Active Session State
  const [sessions, setSessions] = useState([]);
  const [activeSessionId, setActiveSessionId] = useState(null);
  const [activeSession, setActiveSession] = useState(null);
  const [messages, setMessages] = useState([]);

  // UI States
  const [inputText, setInputText] = useState('');
  const [loading, setLoading] = useState(false);
  const [sendingMessage, setSendingMessage] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [canRetry, setCanRetry] = useState(false);

  // New Chat Modal State
  const [showNewChatModal, setShowNewChatModal] = useState(false);
  const [modalScope, setModalScope] = useState('VERSION');
  const [modalVersionId, setModalVersionId] = useState('');
  const [modalComparisonId, setModalComparisonId] = useState('');
  const [modalTitle, setModalTitle] = useState('');
  const [creatingSession, setCreatingSession] = useState(false);

  // Inline Rename State
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState('');

  const messagesEndRef = useRef(null);

  // Scroll to bottom helper
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, sendingMessage]);

  // 1. Initial Load: Fetch Datasets
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

  // 2. Load Dataset Details & Comparisons when selectedDatasetId changes
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadDatasetDetails() {
      try {
        const detail = await getDataset(selectedDatasetId);
        setDatasetDetail(detail);

        // Load comparisons for comparison scope options
        try {
          const comps = await getDatasetComparisons(selectedDatasetId);
          setComparisons(comps || []);
        } catch {
          setComparisons([]);
        }

        // Set default modal version ID
        if (detail?.versions && detail.versions.length > 0) {
          setModalVersionId(detail.versions[0].id);
        }
      } catch (err) {
        console.error('Error loading dataset detail:', err);
      }
    }
    loadDatasetDetails();
  }, [selectedDatasetId]);

  // 3. Load Chat Sessions for selected Dataset
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadSessions() {
      try {
        const sessionList = await getChatSessions(selectedDatasetId);
        setSessions(sessionList || []);

        // Check if we need to auto-create a session from query params
        if (queryScope && queryInitialPrompt) {
          await handleAutoCreateSessionFromQuery(selectedDatasetId);
          return;
        }

        // If sessions exist, select the first one; otherwise reset active
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

  // Handle deep-link query params auto-session creation
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

      // Clean search params
      setSearchParams({});

      // Send initial prompt automatically
      const res = await sendChatMessage(targetDatasetId, created.id, queryInitialPrompt);
      const refreshed = await getChatSession(targetDatasetId, created.id);
      setActiveSession(refreshed);
      setMessages(refreshed.messages || []);
    } catch (err) {
      setErrorMessage('Auto-session creation failed: ' + err.message);
    } finally {
      setSendingMessage(false);
    }
  };

  // 4. Load Active Chat Session Details & Messages
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

  // 5. Send User Message Handler
  const handleSendMessage = async (textToSend = null) => {
    const prompt = (textToSend || inputText).trim();
    if (!prompt || sendingMessage || !activeSessionId) return;

    setInputText('');
    setErrorMessage(null);
    setCanRetry(false);
    setSendingMessage(true);

    // Optimistic user message update in UI
    const tempUserMsg = {
      id: 'temp-' + Date.now(),
      role: 'user',
      content: prompt,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      const response = await sendChatMessage(selectedDatasetId, activeSessionId, prompt);

      // Fetch full session to get updated title and official message IDs
      const refreshed = await getChatSession(selectedDatasetId, activeSessionId);
      setActiveSession(refreshed);
      setMessages(refreshed.messages || []);

      // Update session title in sidebar list
      setSessions((prev) =>
        prev.map((s) => (s.id === activeSessionId ? { ...s, title: refreshed.title, updated_at: refreshed.updated_at } : s))
      );
    } catch (err) {
      setErrorMessage(err.message || 'AI Assistant is temporarily unavailable. Please try again.');
      setCanRetry(true);
    } finally {
      setSendingMessage(false);
    }
  };

  // 6. Retry Handler
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

  // 7. Create New Session Modal Submit
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
    } catch (err) {
      setErrorMessage('Failed to create chat: ' + err.message);
    } finally {
      setCreatingSession(false);
    }
  };

  // 8. Rename Session Submit
  const handleRenameSubmit = async () => {
    if (!renameValue.trim() || !activeSessionId) return;

    try {
      const updated = await updateChatSession(selectedDatasetId, activeSessionId, { title: renameValue.trim() });
      setActiveSession((prev) => ({ ...prev, title: updated.title }));
      setSessions((prev) => prev.map((s) => (s.id === activeSessionId ? { ...s, title: updated.title } : s)));
      setIsRenaming(false);
    } catch (err) {
      setErrorMessage('Failed to rename session: ' + err.message);
    }
  };

  // 9. Delete Session Handler
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

  // Group sessions by date: Today, Yesterday, Earlier
  const groupSessionsByDate = (sessionList) => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const groups = { Today: [], Yesterday: [], Earlier: [] };

    sessionList.forEach((s) => {
      const date = new Date(s.updated_at);
      if (date >= today) {
        groups.Today.push(s);
      } else if (date >= yesterday) {
        groups.Yesterday.push(s);
      } else {
        groups.Earlier.push(s);
      }
    });

    return groups;
  };

  const sessionGroups = groupSessionsByDate(sessions);

  // Active version number label helper
  const getActiveVersionLabel = () => {
    if (!activeSession) return '';
    if (activeSession.scope === 'VERSION') {
      const v = datasetDetail?.versions?.find((ver) => ver.id === activeSession.version_id);
      return v ? `Version V${v.version_number}` : 'Version';
    }
    if (activeSession.scope === 'COMPARISON') {
      const c = comparisons.find((comp) => comp.id === activeSession.comparison_id);
      return c ? `Comparison V${c.baseline_version?.version_number || 1} ➔ V${c.current_version?.version_number || 2}` : 'Comparison';
    }
    return 'Dataset Scope';
  };

  return (
    <div className="chat-page-container">
      {/* ----------------------------------------------------------------------
          Left Sidebar: Chat History & New Chat
      ---------------------------------------------------------------------- */}
      <aside className="chat-sidebar">
        <div className="chat-sidebar-header">
          <button
            className="new-chat-btn"
            onClick={() => {
              setShowNewChatModal(true);
              if (datasetDetail?.versions?.length > 0) {
                setModalVersionId(datasetDetail.versions[0].id);
              }
            }}
          >
            <span>+</span> New Chat
          </button>

          {/* Dataset Selector */}
          <select
            className="dataset-filter-select"
            value={selectedDatasetId}
            onChange={(e) => {
              setSelectedDatasetId(e.target.value);
              navigate(`/datasets/${e.target.value}/chat`);
            }}
          >
            {datasets.map((d) => (
              <option key={d.id} value={d.id}>
                🗃️ {d.name}
              </option>
            ))}
          </select>
        </div>

        <div className="chat-history-scroll">
          {Object.entries(sessionGroups).map(([groupName, items]) => {
            if (items.length === 0) return null;
            return (
              <div key={groupName} className="history-group">
                <div className="history-group-title">{groupName}</div>
                {items.map((sess) => {
                  const isActive = sess.id === activeSessionId;
                  return (
                    <div
                      key={sess.id}
                      className={`chat-history-item ${isActive ? 'active' : ''}`}
                      onClick={() => setActiveSessionId(sess.id)}
                    >
                      <div className="history-item-content">
                        <span className="history-item-title">{sess.title || 'New Chat'}</span>
                        <span className="history-item-meta">
                          <span>{sess.scope}</span>
                          <span>•</span>
                          <span>{sess.message_count} msgs</span>
                        </span>
                      </div>
                      <div className="history-item-actions">
                        <button
                          className="icon-btn-tiny delete"
                          title="Delete Chat"
                          onClick={(e) => handleDeleteSession(sess.id, e)}
                        >
                          ✕
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            );
          })}

          {sessions.length === 0 && (
            <div className="p-md text-center text-muted text-xs">
              No conversations yet. Start a new chat!
            </div>
          )}
        </div>
      </aside>

      {/* ----------------------------------------------------------------------
          Main Chat Conversation Area
      ---------------------------------------------------------------------- */}
      <main className="chat-main-area">
        {activeSession ? (
          <>
            {/* Header */}
            <header className="chat-header">
              <div className="chat-header-title-area">
                <div className="chat-header-top">
                  {isRenaming ? (
                    <div className="flex-row items-center gap-xs">
                      <input
                        type="text"
                        className="form-input text-xs"
                        value={renameValue}
                        onChange={(e) => setRenameValue(e.target.value)}
                        onKeyDown={(e) => e.key === 'Enter' && handleRenameSubmit()}
                        autoFocus
                      />
                      <button className="btn-primary text-xs py-xs" onClick={handleRenameSubmit}>
                        Save
                      </button>
                      <button className="btn-secondary text-xs py-xs" onClick={() => setIsRenaming(false)}>
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <h2 className="chat-title-text">{activeSession.title || 'Conversation'}</h2>
                      <button
                        className="icon-btn-tiny"
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
                  <span
                    className={`chat-scope-badge ${
                      activeSession.scope === 'COMPARISON'
                        ? 'comparison'
                        : activeSession.scope === 'DATASET'
                        ? 'dataset'
                        : ''
                    }`}
                  >
                    {activeSession.scope}
                  </span>
                </div>
                <div className="chat-header-sub">
                  <span>Dataset: <strong>{datasetDetail?.name || 'Loading...'}</strong></span>
                  <span>•</span>
                  <span>Scope: <strong>{getActiveVersionLabel()}</strong></span>
                </div>
              </div>

              <div>
                <button
                  className="icon-btn-tiny delete"
                  title="Delete Session"
                  onClick={(e) => handleDeleteSession(activeSession.id, e)}
                >
                  🗑️ Delete
                </button>
              </div>
            </header>

            {/* Conversation Stream */}
            <div className="chat-messages-container">
              {messages.length === 0 ? (
                /* Empty Chat Suggestions State */
                <div className="chat-empty-state">
                  <div className="chat-empty-icon">🛡️</div>
                  <h3 className="chat-empty-title">Ask anything about this dataset</h3>
                  <p className="chat-empty-sub">
                    Conversations are grounded in verified analytical evidence from Phase 11 RAG.
                    Zero raw PII is exposed.
                  </p>

                  <div className="suggestions-grid">
                    {activeSession.scope === 'COMPARISON' ? (
                      <>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('What changed between these versions?')}
                        >
                          <span className="suggestion-pill-icon">📊</span>
                          <span>What changed between these versions?</span>
                        </div>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('What are the biggest drift drivers?')}
                        >
                          <span className="suggestion-pill-icon">🌊</span>
                          <span>What are the biggest drift drivers?</span>
                        </div>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('Explain new anomalies detected in this version')}
                        >
                          <span className="suggestion-pill-icon">⚠️</span>
                          <span>Explain new anomalies detected in this version</span>
                        </div>
                      </>
                    ) : (
                      <>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('What are the biggest data quality problems in this dataset?')}
                        >
                          <span className="suggestion-pill-icon">🔍</span>
                          <span>What are the biggest quality problems?</span>
                        </div>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('Which columns have the highest risk and why?')}
                        >
                          <span className="suggestion-pill-icon">🚨</span>
                          <span>Which columns are highest risk?</span>
                        </div>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('Are there any privacy or PII concerns?')}
                        >
                          <span className="suggestion-pill-icon">🔒</span>
                          <span>Are there any privacy concerns?</span>
                        </div>
                        <div
                          className="suggestion-pill-card"
                          onClick={() => handleSendMessage('What should I investigate and remediate first?')}
                        >
                          <span className="suggestion-pill-icon">🛠️</span>
                          <span>What should I investigate first?</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>
              ) : (
                /* Message History */
                messages.map((msg, idx) => {
                  const isUser = msg.role === 'user';
                  const isLatestAssistant = !isUser && idx === messages.length - 1;

                  return (
                    <div key={msg.id || idx} className={`chat-message-row ${msg.role}`}>
                      {isUser ? (
                        <div className="user-bubble">
                          <div>{msg.content}</div>
                          <div className="user-bubble-time">
                            {new Date(msg.created_at).toLocaleTimeString([], {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}
                          </div>
                        </div>
                      ) : (
                        <div className="w-full">
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

                          {/* Quick Follow-up Suggestions for Latest Assistant Response */}
                          {isLatestAssistant && !sendingMessage && (
                            <div className="followup-suggestions">
                              <button
                                className="followup-pill"
                                onClick={() => handleSendMessage('Which columns are responsible for that?')}
                              >
                                <span>🔍</span> Which columns are responsible?
                              </button>
                              <button
                                className="followup-pill"
                                onClick={() => handleSendMessage('Explain the highest-risk column in detail')}
                              >
                                <span>🚨</span> Explain the highest-risk column
                              </button>
                              <button
                                className="followup-pill"
                                onClick={() => handleSendMessage('What about privacy and sensitive findings?')}
                              >
                                <span>🔒</span> Check privacy findings
                              </button>
                              <button
                                className="followup-pill"
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

              {/* Loading Indicator */}
              {sendingMessage && (
                <div className="chat-loading-indicator">
                  <div className="pulse-spinner" />
                  <span>Analyzing grounded Phase 11 analytical evidence...</span>
                </div>
              )}

              {/* Error Banner with Retry */}
              {errorMessage && (
                <div className="retry-banner">
                  <span>⚠️ {errorMessage}</span>
                  {canRetry && (
                    <button className="retry-btn" onClick={handleRetry}>
                      Retry
                    </button>
                  )}
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>

            {/* Input Bar */}
            <div className="chat-input-bar">
              <div className="chat-input-wrapper">
                <textarea
                  className="chat-textarea"
                  placeholder="Ask a grounded analytical question about this dataset..."
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
                  className="send-btn"
                  onClick={() => handleSendMessage()}
                  disabled={!inputText.trim() || sendingMessage}
                >
                  {sendingMessage ? '...' : 'Send ➤'}
                </button>
              </div>
              <div className="input-footer-hint">
                <span>Press Enter to send, Shift + Enter for newline</span>
                <span>{inputText.length} / 8000</span>
              </div>
            </div>
          </>
        ) : (
          /* No Active Session State */
          <div className="chat-empty-state">
            <div className="chat-empty-icon">💬</div>
            <h3 className="chat-empty-title">Select or start a chat session</h3>
            <p className="chat-empty-sub">
              Choose a conversation from the sidebar or start a new grounded chat session.
            </p>
            <button
              className="btn-primary"
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

      {/* ----------------------------------------------------------------------
          New Chat Modal
      ---------------------------------------------------------------------- */}
      {showNewChatModal && (
        <div className="modal-overlay" onClick={() => setShowNewChatModal(false)}>
          <div className="new-chat-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h3 className="modal-title">Start New AI Chat</h3>
              <button className="icon-btn-tiny" onClick={() => setShowNewChatModal(false)}>
                ✕
              </button>
            </div>

            <form onSubmit={handleCreateSessionSubmit}>
              <div className="form-group mb-sm">
                <label className="form-label">Dataset</label>
                <select
                  className="form-select"
                  value={selectedDatasetId}
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="form-group mb-sm">
                <label className="form-label">Operational Scope (Locked)</label>
                <select
                  className="form-select"
                  value={modalScope}
                  onChange={(e) => setModalScope(e.target.value)}
                >
                  <option value="VERSION">VERSION (Specific Dataset Version)</option>
                  <option value="COMPARISON">COMPARISON (Drift / Version Diff)</option>
                  <option value="DATASET">DATASET (Dataset Wide)</option>
                </select>
              </div>

              {modalScope === 'VERSION' && (
                <div className="form-group mb-sm">
                  <label className="form-label">Target Version</label>
                  <select
                    className="form-select"
                    value={modalVersionId}
                    onChange={(e) => setModalVersionId(e.target.value)}
                    required
                  >
                    {datasetDetail?.versions?.map((v) => (
                      <option key={v.id} value={v.id}>
                        Version V{v.version_number} ({new Date(v.created_at).toLocaleDateString()})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {modalScope === 'COMPARISON' && (
                <div className="form-group mb-sm">
                  <label className="form-label">Target Comparison</label>
                  {comparisons.length === 0 ? (
                    <div className="text-xs text-muted">
                      No version comparisons found. Please create a comparison first on the Compare page.
                    </div>
                  ) : (
                    <select
                      className="form-select"
                      value={modalComparisonId || (comparisons[0]?.id || '')}
                      onChange={(e) => setModalComparisonId(e.target.value)}
                      required
                    >
                      {comparisons.map((c) => (
                        <option key={c.id} value={c.id}>
                          V{c.baseline_version?.version_number || 1} ➔ V{c.current_version?.version_number || 2}
                        </option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              <div className="form-group mb-md">
                <label className="form-label">Conversation Title (Optional)</label>
                <input
                  type="text"
                  className="form-input"
                  placeholder="e.g. V2 Quality Analysis"
                  value={modalTitle}
                  onChange={(e) => setModalTitle(e.target.value)}
                  maxLength={60}
                />
              </div>

              <div className="modal-actions">
                <button
                  type="button"
                  className="btn-secondary"
                  onClick={() => setShowNewChatModal(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn-primary"
                  disabled={creatingSession || (modalScope === 'COMPARISON' && comparisons.length === 0)}
                >
                  {creatingSession ? 'Creating...' : 'Start Chat'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
