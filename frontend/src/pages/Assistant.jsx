/**
 * DataGuard AI — Phase 12 AI Data Quality Assistant
 *
 * Interactive AI Assistant interface grounded in Phase 11 pgvector RAG context.
 * Queries the configured LLM provider with strict factual grounding,
 * authoritative server-side provenance, configurable relevance thresholds,
 * and zero raw cell-value leakage.
 *
 * Visual design: DATA GUARD AI workspace skin (.as-* classes).
 * Backend contract: UNCHANGED.
 *   - getDatasets() / getDataset() / getDatasetComparisons()
 *   - askAssistant() / getAssistantHealth() / indexDatasetRAG()
 *   - All field paths preserved.
 */

import React, { useState, useEffect, useRef } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  getDatasets,
  getDataset,
  getDatasetComparisons,
  askAssistant,
  getAssistantHealth,
  indexDatasetRAG,
} from '../api/client';
import AssistantResponse from '../components/assistant/AssistantResponse';
import './Assistant.css';

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
  'What are the critical data quality issues and failures detected?',
  'Which columns contain sensitive PII exposure and what are the risk levels?',
  'Why is this column classified as high ML risk and what are the recommendations?',
  'What anomalies, outliers, and distribution shifts were observed?',
  'What are the top prioritized remediation actions to fix the dataset?',
  'How did data quality and distributions drift between versions?',
];

export default function Assistant() {
  const { datasetId: paramDatasetId, versionId: paramVersionId } = useParams();

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(paramDatasetId || '');
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [scope, setScope] = useState(paramVersionId ? 'VERSION' : 'VERSION');
  const [selectedVersionId, setSelectedVersionId] = useState(paramVersionId || '');
  const [comparisons, setComparisons] = useState([]);
  const [selectedComparisonId, setSelectedComparisonId] = useState('');

  const [question, setQuestion] = useState(
    'What are the critical data quality issues and failures detected?',
  );
  const [topK, setTopK] = useState(8);
  const [minSimilarity, setMinSimilarity] = useState(0.35);
  const [selectedPhases, setSelectedPhases] = useState([]);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [healthStatus, setHealthStatus] = useState(null);
  const [healthLoading, setHealthLoading] = useState(true);

  const [loading, setLoading] = useState(false);
  const [response, setResponse] = useState(null);
  const [error, setError] = useState(null);
  const [indexing, setIndexing] = useState(false);
  const [indexMessage, setIndexMessage] = useState(null);

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
        message:
          err.message ||
          'Failed to connect to assistant service',
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
      prev.includes(phaseId) ? prev.filter((p) => p !== phaseId) : [...prev, phaseId],
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
      setIndexMessage(
        `Indexed ${res.indexed_count} knowledge documents across ${res.version_count} versions.`,
      );
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

  // Provider health tone
  const healthTone = healthLoading
    ? 'loading'
    : healthStatus?.status === 'HEALTHY'
    ? 'healthy'
    : healthStatus?.status === 'DEGRADED'
    ? 'degraded'
    : 'unavailable';

  return (
    <div className="as-page">
      {/* ================= HERO ================= */}
      <header className="as-hero">
        <div className="as-hero-info">
          <div className="as-crumbs">
            <span>Workspace</span>
            <span>›</span>
            <span>Intelligence</span>
            <span>›</span>
            <span className="as-crumb-accent">AI Assistant</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>
            <span className="as-title-icon">✦</span> AI Quality Assistant
          </h1>
          <p>
            Ground-truth conversational analytics over dataset quality profiles,
            sensitive data detections, drift metrics, and transformation rules.
          </p>
        </div>

        <div className="as-hero-actions">
          <button
            type="button"
            className="as-btn as-btn--ghost"
            onClick={checkAssistantHealthStatus}
            disabled={healthLoading}
            title="Refresh assistant provider status"
          >
            {healthLoading ? 'Checking…' : '🔄 Provider Health'}
          </button>
          <button
            type="button"
            className="as-btn as-btn--ghost"
            onClick={handleReindexDataset}
            disabled={indexing || !selectedDatasetId}
            title="Index dataset analytical findings into RAG vector space"
          >
            {indexing ? 'Indexing RAG…' : '⚡ Reindex RAG'}
          </button>
          {selectedDatasetId && (
            <Link to={`/datasets/${selectedDatasetId}/rag`} className="as-btn as-btn--ghost">
              🧠 RAG Explorer
            </Link>
          )}
        </div>
      </header>

      {/* ================= PROVIDER BANNER ================= */}
      <section className={`as-provider as-provider--${healthTone}`}>
        {healthLoading ? (
          <>
            <span className="as-provider-spinner" />
            <span>Checking AI Assistant provider health…</span>
          </>
        ) : healthStatus?.status === 'HEALTHY' ? (
          <>
            <span className="as-provider-dot" />
            <span className="as-provider-text">
              <strong>AI Assistant Available:</strong> Primary provider{' '}
              <code>{formatProviderName(healthStatus.primary_provider)}</code> is
              configured and ready.
            </span>
            <span className="as-provider-badge as-provider-badge--healthy">Ready</span>
          </>
        ) : healthStatus?.status === 'DEGRADED' ? (
          <>
            <span className="as-provider-dot" />
            <span className="as-provider-text">
              <strong>AI Assistant Degraded:</strong> Primary provider (
              <code>{formatProviderName(healthStatus.primary_provider)}</code>)
              unavailable. Active fallback:{' '}
              <code>{formatProviderName(healthStatus.active_fallback)}</code>.
            </span>
            <span className="as-provider-badge as-provider-badge--degraded">
              Fallback Active
            </span>
          </>
        ) : (
          <>
            <span className="as-provider-dot" />
            <span className="as-provider-text">
              <strong>AI Assistant Unavailable:</strong> No configured LLM providers
              are currently accessible.
              <small>
                {healthStatus?.message ||
                  'Set GEMINI_API_KEY / HUGGINGFACE_API_TOKEN in backend/.env or start Ollama locally.'}
              </small>
            </span>
          </>
        )}
      </section>

      {/* ================= INDEXING MESSAGE ================= */}
      {indexMessage && (
        <div className="as-index-msg">
          <span>✅ {indexMessage}</span>
          <button type="button" onClick={() => setIndexMessage(null)} aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* ================= ERROR ================= */}
      {error && (
        <div className="as-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Assistant Query Error</strong>
            <p>{error}</p>
          </div>
          <button type="button" onClick={() => setError(null)} aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* ================= SCOPE PANEL ================= */}
      <section className="as-scope-panel">
        <div className="as-panel-head">
          <h3>🎯 Scope &amp; Context Selection</h3>
          <span className="as-panel-tag">Phase 11 Vector Store</span>
        </div>

        <div className="as-scope-grid">
          <label className="as-field">
            <span>Dataset Repository</span>
            <select
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
          </label>

          <div className="as-field">
            <span>Retrieval Scope</span>
            <div className="as-seg">
              <button
                type="button"
                className={`as-seg-btn ${scope === 'VERSION' ? 'as-seg-btn--active' : ''}`}
                onClick={() => setScope('VERSION')}
              >
                📌 Version
              </button>
              <button
                type="button"
                className={`as-seg-btn ${scope === 'COMPARISON' ? 'as-seg-btn--active' : ''}`}
                onClick={() => setScope('COMPARISON')}
              >
                ⚖️ Comparison
              </button>
              <button
                type="button"
                className={`as-seg-btn ${scope === 'DATASET' ? 'as-seg-btn--active' : ''}`}
                onClick={() => setScope('DATASET')}
              >
                🌐 Dataset
              </button>
            </div>
          </div>

          <div className="as-field">
            {scope === 'VERSION' && (
              <>
                <span>Target Snapshot Version</span>
                <select
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
                <span>Comparison Record</span>
                <select
                  value={selectedComparisonId}
                  onChange={(e) => setSelectedComparisonId(e.target.value)}
                  disabled={comparisons.length === 0}
                >
                  {comparisons.length === 0 ? (
                    <option value="">No comparisons found</option>
                  ) : (
                    comparisons.map((c) => (
                      <option key={c.id} value={c.id}>
                        V{c.baseline_version_number} ➔ V{c.current_version_number} (
                        {c.drift_status})
                      </option>
                    ))
                  )}
                </select>
              </>
            )}

            {scope === 'DATASET' && (
              <>
                <span>Cross-Version Scope</span>
                <div className="as-static-field">
                  Cross-version retrieval querying all version summaries and
                  comparisons with version tag tracking.
                </div>
              </>
            )}
          </div>
        </div>

        {/* Suggested questions */}
        <div className="as-suggest">
          <span className="as-suggest-label">SUGGESTED QUESTIONS</span>
          <div className="as-suggest-list">
            {SUGGESTED_QUESTIONS.map((q, idx) => (
              <button
                key={idx}
                type="button"
                className="as-suggest-chip"
                onClick={() => setQuestion(q)}
              >
                {q}
              </button>
            ))}
          </div>
        </div>
      </section>

      {/* ================= ASK PANEL ================= */}
      <section className="as-ask-panel">
        <form onSubmit={handleAsk}>
          <div className="as-ask-row">
            <textarea
              className="as-textarea"
              rows={2}
              placeholder="Ask anything about dataset health, quality failures, PII, ML risk, anomalies, or drift…"
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
              className="as-btn as-btn--primary as-btn--ask"
              disabled={loading || !selectedDatasetId}
            >
              {loading ? (
                <>
                  <span className="as-spinner as-spinner--sm" /> Thinking…
                </>
              ) : (
                <>
                  <span>✦</span> Ask Assistant
                </>
              )}
            </button>
          </div>

          <div className="as-ask-foot">
            <button
              type="button"
              className="as-advanced-toggle"
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              <span>{showAdvanced ? '▼' : '▶'}</span>
              <span>Advanced Retrieval &amp; Grounding Controls</span>
            </button>
          </div>

          {showAdvanced && (
            <div className="as-advanced">
              <div className="as-advanced-row">
                <label className="as-slider">
                  <div className="as-slider-head">
                    <span>Top-K Documents (3 – 15)</span>
                    <span className="as-slider-value">{topK}</span>
                  </div>
                  <input
                    type="range"
                    min={3}
                    max={15}
                    step={1}
                    value={topK}
                    onChange={(e) => setTopK(Number(e.target.value))}
                  />
                </label>

                <label className="as-slider">
                  <div className="as-slider-head">
                    <span>Min Grounding Similarity (0.10 – 0.90)</span>
                    <span className="as-slider-value">{minSimilarity.toFixed(2)}</span>
                  </div>
                  <input
                    type="range"
                    min={0.1}
                    max={0.9}
                    step={0.05}
                    value={minSimilarity}
                    onChange={(e) => setMinSimilarity(Number(e.target.value))}
                  />
                  <span className="as-slider-hint">
                    Documents below this cosine similarity threshold are treated as
                    insufficient evidence.
                  </span>
                </label>
              </div>

              <div className="as-phase-filter">
                <span className="as-phase-label">Source Phase Filter (Optional)</span>
                <div className="as-phase-chips">
                  {PHASE_OPTIONS.map((p) => (
                    <label
                      key={p.id}
                      className={`as-phase-chip ${
                        selectedPhases.includes(p.id) ? 'as-phase-chip--active' : ''
                      }`}
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
        </form>
      </section>

      {/* ================= RESPONSE ================= */}
      {response && (
        <div ref={responseRef} className="as-response-wrap">
          <AssistantResponse response={response} onReindex={handleReindexDataset} />
        </div>
      )}
    </div>
  );
}