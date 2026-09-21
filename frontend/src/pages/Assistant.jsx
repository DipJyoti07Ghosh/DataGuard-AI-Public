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

  // Ollama Health State
  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  // Response & UI State
  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState(null);

  const responseRef = useRef(null);

  useEffect(() => {
    document.getElementById('page-title').textContent = 'AI Assistant';
    loadDatasets();
    checkOllamaHealth();
  }, []);

  useEffect(() => {
    if (selectedDatasetId) {
      loadDatasetDetails(selectedDatasetId);
      loadComparisons(selectedDatasetId);
    }
  }, [selectedDatasetId]);

  async function checkOllamaHealth() {
    try {
      setHealthLoading(true);
      const res = await getAssistantHealth();
      setHealthStatus(res);
    } catch (err) {
      setHealthStatus({
        status: 'UNAVAILABLE',
        error_detail: err.message || 'Failed to connect to assistant service',
        model_configured: 'llama3.1:8b',
        model_available: false,
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

  const versions = selectedDataset?.versions || [];

  return (
    <div className="assistant-page page-content">
      {/* Header Bar */}
      <div className="page-header flex-between flex-wrap gap-md">
        <div>
          <h1 className="page-title flex-row items-center gap-sm">
            <span style={{ fontSize: '1.8rem' }}>🤖</span> AI Data Quality Assistant
          </h1>
          <p className="page-subtitle">
            Local LLM analytical assistant grounded with pgvector semantic retrieval and privacy isolation.
          </p>
        </div>

        <div className="flex-row items-center gap-sm">
          <button
            className="btn btn--secondary btn--sm"
            onClick={checkOllamaHealth}
            disabled={healthLoading}
            title="Refresh Ollama status"
          >
            {healthLoading ? 'Checking...' : '🔄 Check Ollama'}
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

      {/* Ollama Health Banner */}
      <div className="mb-lg">
        {healthLoading ? (
          <div className="alert-box alert-box--info" style={{ padding: '8px 16px' }}>
            <span className="spinner-inline"></span> Checking Ollama LLM service health...
          </div>
        ) : healthStatus?.status === 'HEALTHY' ? (
          <div className="alert-box alert-box--success flex-between" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--healthy"></span>
              <span>
                <strong>Ollama Connected:</strong> Model <code>{healthStatus.model_configured}</code> is loaded and ready.
              </span>
            </div>
            <span className="badge badge--success">Ready</span>
          </div>
        ) : healthStatus?.status === 'MODEL_UNAVAILABLE' ? (
          <div className="alert-box alert-box--warning" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--warning"></span>
              <div>
                <strong>Model Unavailable:</strong> Ollama is running at <code>{healthStatus.base_url}</code>, but configured model <code>{healthStatus.model_configured}</code> is not pulled.
                <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                  Run: <code>ollama pull {healthStatus.model_configured}</code>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="alert-box alert-box--error" style={{ padding: '10px 16px' }}>
            <div className="flex-row items-center gap-sm">
              <span className="status-dot status-dot--error"></span>
              <div>
                <strong>Ollama Unavailable:</strong> Could not connect to Ollama at <code>{healthStatus?.base_url || 'http://localhost:11434'}</code>.
                <div style={{ fontSize: '0.82rem', marginTop: '4px' }}>
                  Ensure Ollama is running locally: <code>ollama serve</code>
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
        <div ref={responseRef} className="assistant-response-wrapper mb-2xl">
          {/* Main Answer Card */}
          <div className="card mb-lg" style={{ background: 'var(--bg-card)', border: '1px solid var(--border-medium)' }}>
            <div className="card-header flex-between flex-wrap gap-sm">
              <div className="flex-row items-center gap-sm">
                <span style={{ fontSize: '1.4rem' }}>💡</span>
                <div>
                  <h3 className="card-title">AI Assistant Analysis</h3>
                  <div className="text-xs text-muted">
                    Generated via <code>{response.model_name}</code> • Latency: {response.latency_ms.toFixed(0)} ms
                  </div>
                </div>
              </div>

              <div className="flex-row items-center gap-xs">
                {response.is_grounded ? (
                  <span className="badge badge--success flex-row items-center gap-xs">
                    <span>🎯</span> Grounded in Evidence
                  </span>
                ) : (
                  <span className="badge badge--warning flex-row items-center gap-xs">
                    <span>⚠️</span> Insufficient Evidence
                  </span>
                )}
                <span className="badge badge--neutral">
                  {response.sources.length} Grounded Sources
                </span>
              </div>
            </div>

            <div className="card-body">
              {/* Grounded AI Answer Content */}
              <div className="assistant-answer-text">
                {response.answer.split('\n\n').map((para, i) => (
                  <p key={i} className="mb-sm" style={{ lineHeight: '1.7', fontSize: '0.96rem' }}>
                    {para}
                  </p>
                ))}
              </div>

              {/* Security & Grounding Policy Notice */}
              <div className="privacy-assurance-footer mt-lg pt-md border-top-subtle flex-between flex-wrap text-xs text-muted">
                <span className="flex-row items-center gap-xs">
                  <span>🔒</span> <strong>Privacy Guarded:</strong> Synthesized purely from sanitized Phase 11 analytical context. Zero raw dataset cell values or raw PII were supplied to the LLM.
                </span>
                <span>
                  Authoritative Server-side Provenance Tracking Active
                </span>
              </div>
            </div>
          </div>

          {/* Grounded Evidence Section (Authoritative Provenance) */}
          <div className="evidence-section">
            <div className="section-header flex-between mb-md">
              <h3 className="section-title flex-row items-center gap-xs" style={{ fontSize: '1.15rem' }}>
                <span>📑</span> Sanitized Grounded Evidence ({response.sources.length})
              </h3>
              <span className="text-xs text-muted">
                Authoritative source chunks retrieved via pgvector cosine distance
              </span>
            </div>

            {response.sources.length === 0 ? (
              <div className="empty-evidence-card p-lg text-center bg-card rounded-md border-subtle">
                <p className="text-muted">
                  No retrieved documents met the similarity threshold (<code>&gt;= {minSimilarity.toFixed(2)}</code>).
                </p>
              </div>
            ) : (
              <div className="evidence-cards-list grid-responsive-1 gap-md">
                {response.sources.map((src, idx) => (
                  <div
                    key={src.document_id || idx}
                    className="evidence-card p-md rounded-md"
                    style={{
                      background: 'rgba(17, 24, 39, 0.85)',
                      border: '1px solid var(--border-subtle)',
                      borderLeft: '4px solid var(--accent-primary)',
                    }}
                  >
                    <div className="evidence-card-header flex-between flex-wrap gap-xs mb-sm">
                      <div className="flex-row items-center gap-xs flex-wrap">
                        <span className="badge badge--primary">
                          {src.source_phase.replace('PHASE_', 'P').replace('_', ' ')}
                        </span>
                        <span className="badge badge--neutral font-mono">
                          {src.document_type}
                        </span>
                        {src.column_name && (
                          <span className="badge badge--info font-mono">
                            col: {src.column_name}
                          </span>
                        )}
                        {src.version_number != null && (
                          <span className="badge badge--warning">
                            V{src.version_number}
                          </span>
                        )}
                      </div>

                      <div className="flex-row items-center gap-xs">
                        <span className="text-xs text-muted font-mono">
                          Sim: <strong style={{ color: 'var(--accent-hover)' }}>{src.similarity.toFixed(3)}</strong>
                        </span>
                      </div>
                    </div>

                    {/* Sanitized Evidence Snippet */}
                    <div
                      className="evidence-content-box p-sm rounded-sm font-mono text-sm mb-xs"
                      style={{
                        background: 'rgba(11, 15, 26, 0.7)',
                        border: '1px solid rgba(148, 163, 184, 0.08)',
                        whiteSpace: 'pre-wrap',
                        color: 'var(--text-primary)',
                        lineHeight: '1.5',
                      }}
                    >
                      {src.content_snippet}
                    </div>

                    {/* Authoritative Metadata Footer */}
                    <div className="evidence-card-footer flex-between text-xs text-muted mt-xs">
                      <span className="font-mono">
                        doc_id: <code>{src.document_id.slice(0, 12)}...</code>
                      </span>
                      {src.source_result_id && (
                        <span className="font-mono">
                          src_id: <code>{src.source_result_id.slice(0, 12)}...</code>
                        </span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
