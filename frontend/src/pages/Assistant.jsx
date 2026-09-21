/**
 * DataGuard AI — Phase 12 AI Data Quality Assistant
 * 
 * Interactive AI Assistant interface grounded in Phase 11 pgvector RAG context.
 * Queries local Ollama with strict factual grounding, authoritative server-side provenance,
 * configurable relevance thresholds, and zero raw cell-value leakage.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  getDatasets,
  getDataset,
  getDatasetComparisons,
  askAssistant,
  getAssistantHealth,
  indexDatasetRAG,
} from '../api/client';
import AssistantResponse from '../components/assistant/AssistantResponse';

const PHASE_OPTIONS = [
  { id: 'PHASE_4_PROFILING', label: 'Profiling', icon: '📊' },
  { id: 'PHASE_5_QUALITY', label: 'Quality', icon: '🛡️' },
  { id: 'PHASE_6_PII', label: 'Privacy/PII', icon: '🔒' },
  { id: 'PHASE_7_RISK', label: 'ML Risk', icon: '🤖' },
  { id: 'PHASE_8_ANOMALY', label: 'Anomalies', icon: '⚠️' },
  { id: 'PHASE_9_HEALTH', label: 'Health/Remediation', icon: '🩺' },
  { id: 'PHASE_10_DRIFT', label: 'Drift/Comparison', icon: '⚖️' },
];

const SUGGESTED_QUESTIONS = [
  "What are the critical data quality issues and failures detected?",
  "Which columns contain sensitive PII exposure and what are the risk levels?",
  "Why is this column classified as high ML risk and what are the recommendations?",
  "What anomalies, outliers, and distribution shifts were observed?",
  "What are the top prioritized remediation actions to fix the dataset?",
  "How did data quality and distributions drift between versions?",
];

export default function Assistant() {
  const { datasetId: paramDatasetId, versionId: paramVersionId } = useParams();
  const navigate = useNavigate();

  // Dataset & Scope State
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(paramDatasetId || '');
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [scope, setScope] = useState(paramVersionId ? 'VERSION' : 'VERSION');
  const [selectedVersionId, setSelectedVersionId] = useState(paramVersionId || '');
  const [comparisons, setComparisons] = useState([]);
  const [selectedComparisonId, setSelectedComparisonId] = useState('');

  // Assistant Query State
  const [question, setQuestion] = useState('What are the critical data quality issues and failures detected?');
  const [topK, setTopK] = useState(8);
  const [minSimilarity, setMinSimilarity] = useState(0.35);
  const [selectedPhases, setSelectedPhases] = useState([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Health State
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  // Response & UI State
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState(null);
  const [showEvidence, setShowEvidence] = useState(false);

  const responseRef = useRef(null);

  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = 'AI Assistant';
    loadDatasets();
    checkAssistantHealthStatus();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      loadDatasetDetails(selectedDatasetId);
      loadComparisons(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  async function checkAssistantHealthStatus() {
    try {
      setHealthLoading(true);
      const res = await getAssistantHealth();
      setHealthStatus(res);
    } catch (err) {
      setHealthStatus({
        status: 'UNAVAILABLE',
        primary_provider: 'gemini',
        active_fallback: null,
        available_providers: [],
        provider_details: {},
        message: err.message || 'Failed to connect to assistant service',
      });
    } finally {
      setHealthLoading(false);
    }
  }

  async function loadDatasets() {
    try {
      const data = await getDatasets();
      const list = data.items || data || [];
      setDatasets(list);
      if (!selectedDatasetId && list.length > 0) {
        setSelectedDatasetId(list[0].id);
      }
    } catch (err) {
      setError('Failed to load dataset list: ' + err.message);
    }
  }

  async function loadDatasetDetails(id) {
    try {
      const ds = await getDataset(id);
      setSelectedDataset(ds);
      if (ds.versions && ds.versions.length > 0) {
        if (!selectedVersionId || !ds.versions.find((v) => v.id === selectedVersionId)) {
          setSelectedVersionId(ds.versions[0].id);
        }
      } else {
        setSelectedVersionId('');
      }
    } catch (err) {
      console.error('Failed to load dataset details:', err);
    }
  }

  async function loadComparisons(id) {
    try {
      const compList = await getDatasetComparisons(id);
      setComparisons(compList || []);
      if (compList && compList.length > 0 && !selectedComparisonId) {
        setSelectedComparisonId(compList[0].id);
      }
    } catch (err) {
      console.error('Failed to load comparisons:', err);
    }
  }

  function handlePhaseToggle(phaseId) {
    setSelectedPhases((prev) =>
      prev.includes(phaseId) ? prev.filter((p) => p !== phaseId) : [...prev, phaseId]
    );
  }

  async function handleAsk(e) {
    if (e) e.preventDefault();
    if (!selectedDatasetId) {
      setError('Please select a dataset first.');
      return;
    }
    if (!question.trim()) {
      setError('Please enter a question.');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setResponse(null);

      const payload = {
        question: question.trim(),
        scope: scope,
        top_k: Number(topK),
        min_similarity: Number(minSimilarity),
        phases: selectedPhases.length > 0 ? selectedPhases : null,
      };

      if (scope === 'VERSION') {
        payload.version_id = selectedVersionId || undefined;
      } else if (scope === 'COMPARISON') {
        payload.comparison_id = selectedComparisonId || undefined;
      }

      const res = await askAssistant(selectedDatasetId, payload);
      setResponse(res);

      setTimeout(() => {
        if (responseRef.current) {
          responseRef.current.scrollIntoView({ behavior: 'smooth' });
        }
      }, 100);
    } catch (err) {
      setError(err.message || 'Failed to query AI Assistant');
    } finally {
      setLoading(false);
    }
  }

  async function handleReindexDataset() {
    if (!selectedDatasetId) return;
    try {
      setIndexing(true);
      setIndexMessage(null);
      const res = await indexDatasetRAG(selectedDatasetId, true);
      setIndexMessage(`Indexed ${res.indexed_count} knowledge documents across ${res.version_count} versions.`);
    } catch (err) {
      setError('Failed to index RAG documents: ' + err.message);
    } finally {
      setIndexing(false);
    }
  }

  const formatProviderName = (provider) => {
    if (!provider) return 'None';
    if (provider === 'gemini') return 'Hosted Gemini API';
    if (provider === 'huggingface') return 'Hosted Hugging Face API';
    if (provider === 'ollama') return 'Local Ollama';
    return provider;
  };

  const versions = selectedDataset?.versions || [];

  return (
    <div className="assistant-page page-content">
      {/* Header Bar */}
      <div className="page-header flex-between flex-wrap gap-md mb-lg">
        <div>
          <h1 className="page-title flex-row items-center gap-sm">
            <span style={{ fontSize: '1.8rem' }}>🤖</span> AI Quality Assistant
          </h1>
          <p className="page-subtitle">
            Ground-truth conversational analytics over dataset quality profiles, sensitive data detections, drift metrics, and transformation rules.
          </p>
        </div>

        <div className="flex-row items-center gap-sm">
          <button
            className="btn btn--secondary btn--sm"
            onClick={checkAssistantHealthStatus}
            disabled={healthLoading}
            title="Refresh assistant provider status"
          >
            {healthLoading ? 'Checking...' : '🔄 Provider Health'}
          </button>
          <button
            className="btn btn--secondary btn--sm"
            onClick={handleReindexDataset}
            disabled={indexing || !selectedDatasetId}
            title="Index dataset analytical findings into RAG vector space"
          >
            {indexing ? 'Indexing RAG...' : '⚡ Reindex RAG'}
          </button>
          {selectedDatasetId && (
            <Link to={`/datasets/${selectedDatasetId}/rag`} className="btn btn--secondary btn--sm">
              🧠 RAG Explorer
            </Link>
          )}
        </div>
      </div>

      {/* LLM Provider Health Banner */}
      <div className="mb-lg">
        {healthLoading ? (
          <div className="alert-box alert-box--info" style={{ padding: '8px 16px' }}>
            <span className="spinner-inline"></span> Checking AI Assistant provider health...
          </div>
        ) : healthStatus?.status === 'HEALTHY' ? (
          <div className="alert-box alert-box--success flex-between" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--healthy"></span>
              <span>
                <strong>AI Assistant Available:</strong> Primary provider <code>{formatProviderName(healthStatus.primary_provider)}</code> is configured and ready.
              </span>
            </div>
            <span className="badge badge--success">Ready</span>
          </div>
        ) : healthStatus?.status === 'DEGRADED' ? (
          <div className="alert-box alert-box--warning flex-between" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--warning"></span>
              <div>
                <strong>AI Assistant Degraded:</strong> Primary provider (<code>{formatProviderName(healthStatus.primary_provider)}</code>) unavailable. Active fallback: <code>{formatProviderName(healthStatus.active_fallback)}</code>.
              </div>
            </div>
            <span className="badge badge--warning">Fallback Active</span>
          </div>
        ) : (
          <div className="alert-box alert-box--error" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--error"></span>
              <div>
                <strong>AI Assistant Unavailable:</strong> No configured LLM providers are currently accessible.
                <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                  {healthStatus?.message || 'Set GEMINI_API_KEY / HUGGINGFACE_API_TOKEN in backend/.env or start Ollama locally via `ollama serve`.'}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Indexing Message */}
      {indexMessage && (
        <div className="alert-box alert-box--success mb-md">
          <span>✅ {indexMessage}</span>
          <button className="alert-close-btn" onClick={() => setIndexMessage(null)}>✕</button>
        </div>
      )}

      {/* Error Alert */}
      {error && (
        <div className="alert-box alert-box--error mb-lg">
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            <strong>Assistant Query Error</strong>
            <p>{error}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Scope and Context Configuration Card */}
      <div className="card mb-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
        <div className="card-header flex-between">
          <h3 className="card-title flex-row items-center gap-xs">
            <span>🎯</span> Scope & Context Selection
          </h3>
          <span className="badge badge--neutral">Phase 11 Vector Store</span>
        </div>

        <div className="card-body">
          <div className="grid-responsive-3 gap-md mb-md">
            {/* Dataset Picker */}
            <div className="form-group">
              <label className="form-label">Dataset Repository</label>
              <select
                className="form-select"
                value={selectedDatasetId}
                onChange={(e) => {
                  setSelectedDatasetId(e.target.value);
                  setSelectedVersionId('');
                  setSelectedComparisonId('');
                }}
              >
                {datasets.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.version_count} versions)
                  </option>
                ))}
              </select>
            </div>

            {/* Scope Selector */}
            <div className="form-group">
              <label className="form-label">Retrieval Scope</label>
              <div className="scope-segmented-control flex-row gap-xs">
                <button
                  type="button"
                  className={`btn btn--sm flex-1 ${scope === 'VERSION' ? 'btn--primary' : 'btn--secondary'}`}
                  onClick={() => setScope('VERSION')}
                >
                  📌 Version
                </button>
                <button
                  type="button"
                  className={`btn btn--sm flex-1 ${scope === 'COMPARISON' ? 'btn--primary' : 'btn--secondary'}`}
                  onClick={() => setScope('COMPARISON')}
                >
                  ⚖️ Comparison
                </button>
                <button
                  type="button"
                  className={`btn btn--sm flex-1 ${scope === 'DATASET' ? 'btn--primary' : 'btn--secondary'}`}
                  onClick={() => setScope('DATASET')}
                >
                  🌐 Dataset
                </button>
              </div>
            </div>

            {/* Specific Target Picker */}
            <div className="form-group">
              {scope === 'VERSION' && (
                <>
                  <label className="form-label">Target Snapshot Version</label>
                  <select
                    className="form-select"
                    value={selectedVersionId}
                    onChange={(e) => setSelectedVersionId(e.target.value)}
                  >
                    {versions.map((v) => (
                      <option key={v.id} value={v.id}>
                        V{v.version_number} — {v.original_filename} ({v.row_count} rows)
                      </option>
                    ))}
                  </select>
                </>
              )}

              {scope === 'COMPARISON' && (
                <>
                  <label className="form-label">Comparison Record</label>
                  <select
                    className="form-select"
                    value={selectedComparisonId}
                    onChange={(e) => setSelectedComparisonId(e.target.value)}
                    disabled={comparisons.length === 0}
                  >
                    {comparisons.length === 0 ? (
                      <option value="">No comparisons found</option>
                    ) : (
                      comparisons.map((c) => (
                        <option key={c.id} value={c.id}>
                          V{c.baseline_version_number} ➔ V{c.current_version_number} (Drift: {c.drift_status})
                        </option>
                      ))
                    )}
                  </select>
                </>
              )}

              {scope === 'DATASET' && (
                <>
                  <label className="form-label">Cross-Version Scope</label>
                  <div className="text-muted text-sm pt-xs">
                    Cross-version retrieval querying all version summaries and comparisons with version tag tracking.
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Quick Prompts */}
          <div className="quick-prompts mb-md">
            <span className="text-xs text-muted font-bold block mb-xs">SUGGESTED QUESTIONS:</span>
            <div className="flex-row gap-xs flex-wrap">
              {SUGGESTED_QUESTIONS.map((q, idx) => (
                <button
                  key={idx}
                  type="button"
                  className="quick-chip"
                  onClick={() => setQuestion(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>

          {/* Question Input Form */}
          <form onSubmit={handleAsk} className="assistant-input-container">
            <div className="flex-row gap-sm items-center">
              <textarea
                className="form-textarea flex-1"
                rows={2}
                placeholder="Ask anything about dataset health, quality failures, PII, ML risk, anomalies, or drift..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    handleAsk();
                  }
                }}
              />
              <button
                type="submit"
                className="btn btn--primary"
                style={{ height: '60px', padding: '0 24px', fontSize: '1rem' }}
                disabled={loading || !selectedDatasetId}
                id="ask-assistant-btn"
              >
                {loading ? (
                  <span className="flex-row items-center gap-xs">
                    <span className="spinner-inline"></span> Thinking...
                  </span>
                ) : (
                  <span className="flex-row items-center gap-xs">
                    <span>✨</span> Ask Assistant
                  </span>
                )}
              </button>
            </div>
          </form>

          {/* Advanced RAG Filters Accordion */}
          <div className="mt-sm">
            <button
              type="button"
              className="btn-text text-sm flex-row items-center gap-xs"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span>{showAdvanced ? '▼' : '▶'}</span>
              <span>Advanced Retrieval & Grounding Controls</span>
            </button>

            {showAdvanced && (
              <div className="advanced-controls-panel mt-sm p-md bg-secondary rounded-md border-subtle">
                <div className="grid-responsive-2 gap-md mb-sm">
                  <div>
                    <label className="form-label flex-between">
                      <span>Top-K Documents (3 - 15)</span>
                      <span className="font-mono text-accent font-bold">{topK}</span>
                    </label>
                    <input
                      type="range"
                      min={3}
                      max={15}
                      step={1}
                      value={topK}
                      onChange={(e) => setTopK(Number(e.target.value))}
                      className="form-range"
                    />
                  </div>

                  <div>
                    <label className="form-label flex-between">
                      <span>Min Grounding Similarity (0.10 - 0.90)</span>
                      <span className="font-mono text-accent font-bold">{minSimilarity.toFixed(2)}</span>
                    </label>
                    <input
                      type="range"
                      min={0.1}
                      max={0.9}
                      step={0.05}
                      value={minSimilarity}
                      onChange={(e) => setMinSimilarity(Number(e.target.value))}
                      className="form-range"
                    />
                    <div className="text-xs text-muted mt-xs">
                      Documents below this cosine similarity threshold are treated as insufficient evidence.
                    </div>
                  </div>
                </div>

                <div className="phase-filters">
                  <label className="form-label mb-xs">Source Phase Filter (Optional)</label>
                  <div className="flex-row gap-xs flex-wrap">
                    {PHASE_OPTIONS.map((p) => (
                      <label
                        key={p.id}
                        className={`phase-checkbox-chip ${selectedPhases.includes(p.id) ? 'active' : ''}`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedPhases.includes(p.id)}
                          onChange={() => handlePhaseToggle(p.id)}
                          style={{ display: 'none' }}
                        />
                        <span>{p.icon}</span>
                        <span>{p.label}</span>
                      </label>
                    ))}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Response Display */}
      {response && (
        <div ref={responseRef}>
          <AssistantResponse response={response} onReindex={handleReindexDataset} />
        </div>
      )}
    </div>
  );
}
