/**
 * DataGuard AI — Phase 11 RAG Knowledge Explorer
 *
 * Developer & Audit inspection interface for testing semantic vector retrieval,
 * verifying privacy sanitization, inspecting source traceability, and previewing
 * the assembled grounded context payload for Phase 12 LLMs.
 *
 * Visual design: DATA GUARD AI workspace skin (.rag-* classes).
 * Backend contract: UNCHANGED.
 *   - getDatasets() / getDataset() / getDatasetComparisons()
 *   - indexVersionRAG() / indexDatasetRAG() / indexComparisonRAG()
 *   - retrieveRAG() / getRAGDocuments()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion';
import { useParams } from 'react-router-dom';
import {
  getDatasets,
  getDataset,
  getDatasetComparisons,
  indexVersionRAG,
  indexDatasetRAG,
  indexComparisonRAG,
  retrieveRAG,
  getRAGDocuments,
} from '../api/client';
import './RAGExplorer.css';

const PHASE_OPTIONS = [
  { id: 'PHASE_4_PROFILING', label: 'Profiling', icon: '📊' },
  { id: 'PHASE_5_QUALITY', label: 'Quality', icon: '🛡️' },
  { id: 'PHASE_6_PII', label: 'Privacy/PII', icon: '🔒' },
  { id: 'PHASE_7_RISK', label: 'ML Risk', icon: '🤖' },
  { id: 'PHASE_8_ANOMALY', label: 'Anomalies', icon: '⚠️' },
  { id: 'PHASE_9_HEALTH', label: 'Health/Remediation', icon: '🩺' },
  { id: 'PHASE_10_DRIFT', label: 'Drift/Comparison', icon: '⚖️' },
];

const QUICK_QUERIES = [
  'What data quality issues were detected?',
  'Which columns contain sensitive PII exposure?',
  'Why is income classified as high ML risk?',
  'What anomalies or outlier rates were found?',
  'What changed between dataset versions?',
  'What are the highest priority remediation suggestions?',
];

export default function RAGExplorer() {
  const reduceMotion = useReducedMotion();
  const { datasetId: paramDatasetId, versionId: paramVersionId } = useParams();

  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(paramDatasetId || '');
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [scope, setScope] = useState('VERSION');
  const [selectedVersionId, setSelectedVersionId] = useState(paramVersionId || '');
  const [comparisons, setComparisons] = useState([]);
  const [selectedComparisonId, setSelectedComparisonId] = useState('');

  const [query, setQuery] = useState(
    'What data quality and sensitive data issues were detected?',
  );
  const [topK, setTopK] = useState(5);
  const [selectedPhases, setSelectedPhases] = useState([]);
  const [includeComparisons, setIncludeComparisons] = useState(false);

  const [activeTab, setActiveTab] = useState('retrieved');
  const [loadingDatasets, setLoadingDatasets] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [retrieving, setRetrieving] = useState(false);
  const [retrievalResult, setRetrievalResult] = useState(null);
  const [indexedDocs, setIndexedDocs] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [indexSummary, setIndexSummary] = useState(null);
  const [errorMessage, setErrorMessage] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const [expandedTraceId, setExpandedTraceId] = useState(null);

  // 1. Initial dataset list
  useEffect(() => {
    async function loadDatasetsList() {
      setLoadingDatasets(true);
      try {
        const res = await getDatasets();
        const list = Array.isArray(res) ? res : res?.datasets || [];
        setDatasets(list);
        if (list.length > 0 && !selectedDatasetId) {
          setSelectedDatasetId(list[0].id);
        }
      } catch (err) {
        setErrorMessage(`Failed to load datasets: ${err.message}`);
      } finally {
        setLoadingDatasets(false);
      }
    }
    loadDatasetsList();
  }, []);

  // 2. Dataset details + comparisons
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadDatasetDetails() {
      try {
        const d = await getDataset(selectedDatasetId);
        setSelectedDataset(d);
        if (d.versions?.length > 0) {
          if (!selectedVersionId || !d.versions.some((v) => v.id === selectedVersionId)) {
            setSelectedVersionId(d.versions[0].id);
          }
        } else {
          setSelectedVersionId('');
        }

        const compRes = await getDatasetComparisons(selectedDatasetId);
        const compList = Array.isArray(compRes) ? compRes : compRes?.comparisons || [];
        setComparisons(compList);
        if (compList.length > 0) {
          setSelectedComparisonId(compList[0].id);
        } else {
          setSelectedComparisonId('');
        }
      } catch (err) {
        setErrorMessage(`Failed to load dataset details: ${err.message}`);
      }
    }

    loadDatasetDetails();
  }, [selectedDatasetId]);

  // 3. Document inventory
  useEffect(() => {
    if (!selectedDatasetId) return;
    loadInventory();
  }, [selectedDatasetId, selectedVersionId, scope, selectedComparisonId]);

  async function loadInventory() {
    setLoadingDocs(true);
    try {
      const params = {};
      if (scope === 'VERSION' && selectedVersionId) {
        params.version_id = selectedVersionId;
      }
      const res = await getRAGDocuments(selectedDatasetId, params);
      setIndexedDocs(res?.documents || []);
    } catch (err) {
      console.warn('Failed to fetch document inventory:', err);
    } finally {
      setLoadingDocs(false);
    }
  }

  async function handleIndex(force = false) {
    if (!selectedDatasetId) return;
    setIndexing(true);
    setErrorMessage('');
    setSuccessMessage('');

    try {
      let res;
      if (scope === 'VERSION' && selectedVersionId) {
        res = await indexVersionRAG(selectedDatasetId, selectedVersionId, force);
      } else if (scope === 'COMPARISON' && selectedComparisonId) {
        res = await indexComparisonRAG(selectedDatasetId, selectedComparisonId, force);
      } else {
        res = await indexDatasetRAG(selectedDatasetId, force);
      }
      setIndexSummary(res);
      setSuccessMessage(
        `Successfully indexed ${res.total_indexed} documents (${res.new_documents} new, ${res.updated_documents} updated, ${res.skipped_unchanged} skipped).`,
      );
      loadInventory();
    } catch (err) {
      setErrorMessage(`Indexing failed: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  }

  async function handleRetrieve(e) {
    if (e) e.preventDefault();
    if (!selectedDatasetId || !query.trim()) return;

    setRetrieving(true);
    setErrorMessage('');

    try {
      const req = {
        query: query.trim(),
        scope,
        top_k: Number(topK),
        phases: selectedPhases.length > 0 ? selectedPhases : null,
      };

      if (scope === 'VERSION') {
        if (!selectedVersionId) throw new Error('Please select a dataset version.');
        req.version_id = selectedVersionId;
        req.include_comparisons = includeComparisons;
      } else if (scope === 'COMPARISON') {
        if (!selectedComparisonId)
          throw new Error('Please select a version comparison.');
        req.comparison_id = selectedComparisonId;
      }

      const res = await retrieveRAG(selectedDatasetId, req);
      setRetrievalResult(res);
    } catch (err) {
      setErrorMessage(`Retrieval failed: ${err.message}`);
    } finally {
      setRetrieving(false);
    }
  }

  const togglePhase = (phaseId) => {
    setSelectedPhases((prev) =>
      prev.includes(phaseId) ? prev.filter((p) => p !== phaseId) : [...prev, phaseId],
    );
  };

  const getPhaseBadgeColor = (phase) => {
    switch (phase) {
      case 'PHASE_4_PROFILING': return '#3b82f6';
      case 'PHASE_5_QUALITY': return '#10b981';
      case 'PHASE_6_PII': return '#ef4444';
      case 'PHASE_7_RISK': return '#f59e0b';
      case 'PHASE_8_ANOMALY': return '#8b5cf6';
      case 'PHASE_9_HEALTH': return '#ec4899';
      case 'PHASE_10_DRIFT': return '#06b6d4';
      default: return '#64748b';
    }
  };

  return (
    <div className="rag-page">
      {/* ================= HERO ================= */}
      <header className="rag-hero">
        <div className="rag-hero-info">
          <div className="rag-crumbs">
            <span>Workspace</span>
            <span>›</span>
            <span>Intelligence</span>
            <span>›</span>
            <span className="rag-crumb-accent">RAG Knowledge Explorer</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>🧠 RAG Knowledge Explorer</h1>
          <p>
            Inspect semantic vector retrieval, verify privacy sanitization, and
            test grounded factual context assembly.
          </p>
        </div>

        <div className="rag-hero-actions">
          <span className="rag-badge">Phase 11 Native pgvector</span>
          <button
            type="button"
            className="rag-btn rag-btn--ghost"
            onClick={() => handleIndex(false)}
            disabled={indexing || !selectedDatasetId}
          >
            {indexing ? '⚡ Indexing…' : '⚡ Index Scope'}
          </button>
          <button
            type="button"
            className="rag-btn rag-btn--ghost"
            onClick={() => handleIndex(true)}
            disabled={indexing || !selectedDatasetId}
            title="Bypass cache and force re-embed all documents"
          >
            🔄 Force Re-index
          </button>
        </div>
      </header>

      {/* ================= ALERTS ================= */}
      {errorMessage && (
        <div className="rag-alert rag-alert--error" role="alert">
          <span>⚠️</span>
          <span>{errorMessage}</span>
          <button type="button" onClick={() => setErrorMessage('')} aria-label="Dismiss">✕</button>
        </div>
      )}
      {successMessage && (
        <div className="rag-alert rag-alert--success">
          <span>✅</span>
          <span>{successMessage}</span>
          <button type="button" onClick={() => setSuccessMessage('')} aria-label="Dismiss">✕</button>
        </div>
      )}

      {/* ================= LAYOUT: MAIN + SIDEBAR ================= */}
      <div className="rag-layout">
        <div className="rag-main">
          {/* Scope card */}
          <section className="rag-scope-panel">
            <div className="rag-panel-head">
              <h3>Scope &amp; Context Selection</h3>
              <span className="rag-panel-tag">VECTOR-GROUNDED</span>
            </div>

            <div className="rag-scope-grid">
              <label className="rag-field">
                <span>Dataset</span>
                <select
                  value={selectedDatasetId}
                  onChange={(e) => setSelectedDatasetId(e.target.value)}
                >
                  {datasets.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} ({d.versions?.length || 0} versions)
                    </option>
                  ))}
                </select>
              </label>

              <label className="rag-field">
                <span>Retrieval Scope</span>
                <select value={scope} onChange={(e) => setScope(e.target.value)}>
                  <option value="VERSION">VERSION (Specific Snapshot)</option>
                  <option value="COMPARISON">COMPARISON (Drift Snapshot)</option>
                  <option value="DATASET">DATASET (Cross-Version Overview)</option>
                </select>
              </label>

              <div className="rag-field">
                {scope === 'VERSION' && (
                  <>
                    <span>Dataset Version</span>
                    <select
                      value={selectedVersionId}
                      onChange={(e) => setSelectedVersionId(e.target.value)}
                    >
                      {(selectedDataset?.versions || []).map((v) => (
                        <option key={v.id} value={v.id}>
                          Version V{v.version_number} ({v.row_count} rows, {v.column_count} cols)
                        </option>
                      ))}
                    </select>
                  </>
                )}

                {scope === 'COMPARISON' && (
                  <>
                    <span>Version Comparison</span>
                    <select
                      value={selectedComparisonId}
                      onChange={(e) => setSelectedComparisonId(e.target.value)}
                    >
                      {comparisons.length === 0 && (
                        <option value="">No comparisons yet</option>
                      )}
                      {comparisons.map((c) => (
                        <option key={c.id} value={c.id}>
                          V{c.baseline_version?.version_number} ➔ V
                          {c.current_version?.version_number} ({c.overall_drift_status})
                        </option>
                      ))}
                    </select>
                  </>
                )}

                {scope === 'DATASET' && (
                  <>
                    <span>Inventory Status</span>
                    <div className="rag-static-field">
                      {indexedDocs.length} total indexed chunks across all versions
                    </div>
                  </>
                )}
              </div>
            </div>
          </section>

          {/* Query card */}
          <section className="rag-query-panel">
            <form onSubmit={handleRetrieve}>
              <label className="rag-query-label">🔍 Semantic Retrieval Query</label>
              <div className="rag-query-row">
                <input
                  type="text"
                  className="rag-input"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="e.g. What data quality issues or sensitive PII exposures were found?"
                />
                <button
                  type="submit"
                  className="rag-btn rag-btn--primary"
                  disabled={retrieving || !query.trim()}
                >
                  {retrieving ? '🔎 Searching…' : '🔎 Retrieve'}
                </button>
              </div>

              <div className="rag-quick-row">
                <span className="rag-quick-label">Quick Queries:</span>
                {QUICK_QUERIES.slice(0, 3).map((qText, i) => (
                  <button
                    key={i}
                    type="button"
                    className="rag-quick-pill"
                    onClick={() => setQuery(qText)}
                  >
                    {qText}
                  </button>
                ))}
              </div>

              <div className="rag-query-footer">
                <div className="rag-phase-filter">
                  <span className="rag-filter-label">Phase Filter:</span>
                  {PHASE_OPTIONS.map((p) => {
                    const active = selectedPhases.includes(p.id);
                    return (
                      <button
                        key={p.id}
                        type="button"
                        className={`rag-phase-pill ${active ? 'rag-phase-pill--active' : ''}`}
                        style={
                          active
                            ? { background: getPhaseBadgeColor(p.id), borderColor: getPhaseBadgeColor(p.id) }
                            : undefined
                        }
                        onClick={() => togglePhase(p.id)}
                      >
                        {p.icon} {p.label}
                      </button>
                    );
                  })}
                  {selectedPhases.length > 0 && (
                    <button
                      type="button"
                      className="rag-clear"
                      onClick={() => setSelectedPhases([])}
                    >
                      Clear
                    </button>
                  )}
                </div>

                <div className="rag-controls">
                  {scope === 'VERSION' && (
                    <label className="rag-check">
                      <input
                        type="checkbox"
                        checked={includeComparisons}
                        onChange={(e) => setIncludeComparisons(e.target.checked)}
                      />
                      Include Version Drift
                    </label>
                  )}
                  <div className="rag-topk">
                    <span className="rag-filter-label">Top-K Chunks:</span>
                    <input
                      type="range"
                      min="1"
                      max="15"
                      value={topK}
                      onChange={(e) => setTopK(e.target.value)}
                    />
                    <span className="rag-topk-value">{topK}</span>
                  </div>
                </div>
              </div>
            </form>
          </section>

          {/* Tabs */}
          <nav className="rag-tabs">
            <button
              type="button"
              className={`rag-tab ${activeTab === 'retrieved' ? 'rag-tab--active' : ''}`}
              onClick={() => setActiveTab('retrieved')}
            >
              📑 Retrieved Chunks ({retrievalResult?.sources?.length || 0})
            </button>
            <button
              type="button"
              className={`rag-tab ${activeTab === 'context' ? 'rag-tab--active' : ''}`}
              onClick={() => setActiveTab('context')}
            >
              🧩 Grounded Context (Phase 12 Preview)
            </button>
            <button
              type="button"
              className={`rag-tab ${activeTab === 'inventory' ? 'rag-tab--active' : ''}`}
              onClick={() => setActiveTab('inventory')}
            >
              🗂️ Indexed Documents ({indexedDocs.length})
            </button>
          </nav>

          {/* ================= TAB 1: RETRIEVED ================= */}
          {activeTab === 'retrieved' && (
            <section className="rag-tab-content">
              {retrieving ? (
                <div className="rag-empty">
                  <span className="rag-spinner" aria-hidden="true" />
                  <p>Executing vector cosine similarity search via pgvector…</p>
                </div>
              ) : !retrievalResult ? (
                <div className="rag-empty">
                  <span className="rag-empty-icon">💡</span>
                  <p>
                    Enter a query above and click <strong>Retrieve</strong> to search
                    the RAG knowledge layer.
                  </p>
                </div>
              ) : retrievalResult.sources.length === 0 ? (
                <div className="rag-empty">
                  <span className="rag-empty-icon">🔍</span>
                  <p>
                    No matching knowledge chunks found. Ensure the dataset version is
                    indexed by clicking <strong>⚡ Index Scope</strong>.
                  </p>
                </div>
              ) : (
                <div className="rag-chunk-list">
                  {retrievalResult.warnings?.length > 0 && (
                    <div className="rag-warning">
                      {retrievalResult.warnings.map((w, i) => (
                        <div key={i}>⚠️ {w}</div>
                      ))}
                    </div>
                  )}

                  {retrievalResult.sources.map((src, i) => {
                    const color = getPhaseBadgeColor(src.source_phase);
                    const isExpanded = expandedTraceId === src.document_id;
                    return (
                      <article
                        key={src.document_id || i}
                        className="rag-chunk"
                        style={{ borderLeftColor: color }}
                      >
                        <div className="rag-chunk-head">
                          <div className="rag-chunk-tags">
                            <span
                              className="rag-chunk-phase"
                              style={{ background: color, borderColor: color }}
                            >
                              {src.source_phase.replace('_', ' ')}
                            </span>
                            <span className="rag-chunk-tag">{src.document_type}</span>
                            {src.column_name && (
                              <span className="rag-chunk-tag">
                                Column: {src.column_name}
                              </span>
                            )}
                          </div>

                          <span
                            className={`rag-similarity ${
                              src.similarity >= 0.7
                                ? 'rag-similarity--high'
                                : 'rag-similarity--medium'
                            }`}
                          >
                            {(src.similarity * 100).toFixed(1)}% Relevance (
                            {src.similarity.toFixed(4)})
                          </span>
                        </div>

                        <div className="rag-chunk-content">{src.content}</div>

                        <div className="rag-chunk-foot">
                          <button
                            type="button"
                            className="rag-trace-toggle"
                            onClick={() =>
                              setExpandedTraceId(isExpanded ? null : src.document_id)
                            }
                          >
                            {isExpanded
                              ? '▲ Hide Traceability Metadata'
                              : '▼ Show Source Traceability'}
                          </button>
                          <span className="rag-chunk-id">
                            Source ID: {src.document_id?.slice(0, 8)}…
                          </span>
                        </div>

                        <AnimatePresence initial={false}>
                          {isExpanded && (
                            <motion.div
                              initial={reduceMotion ? false : { opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={reduceMotion ? undefined : { opacity: 0, height: 0 }}
                              transition={{ duration: 0.2 }}
                              style={{ overflow: 'hidden' }}
                            >
                              <div className="rag-trace-block">
                                <div>
                                  <strong>Document ID:</strong> {src.document_id}
                                </div>
                                <div>
                                  <strong>Source Phase:</strong> {src.source_phase}
                                </div>
                                <div>
                                  <strong>Embedding Provider:</strong> fastembed
                                </div>
                                <div>
                                  <strong>Embedding Model:</strong>{' '}
                                  BAAI/bge-small-en-v1.5 (384-d)
                                </div>
                                <div>
                                  <strong>Metadata:</strong> {JSON.stringify(src.metadata)}
                                </div>
                              </div>
                            </motion.div>
                          )}
                        </AnimatePresence>
                      </article>
                    );
                  })}
                </div>
              )}
            </section>
          )}

          {/* ================= TAB 2: CONTEXT ================= */}
          {activeTab === 'context' && (
            <section className="rag-tab-content">
              <div className="rag-context-panel">
                <div className="rag-context-head">
                  <div>
                    <h3>Phase 12 Grounded Context Payload</h3>
                    <p className="rag-muted">
                      The exact sanitized factual markdown context assembled for LLM
                      prompt injection.
                    </p>
                  </div>
                  {retrievalResult?.grounded_context_text && (
                    <button
                      type="button"
                      className="rag-btn rag-btn--ghost rag-btn--sm"
                      onClick={() => {
                        navigator.clipboard.writeText(
                          retrievalResult.grounded_context_text,
                        );
                        setSuccessMessage('Grounded context copied to clipboard!');
                      }}
                    >
                      📋 Copy Markdown
                    </button>
                  )}
                </div>

                <pre className="rag-context-block">
                  {retrievalResult?.grounded_context_text ||
                    'No grounded context assembled yet. Execute a query to generate context.'}
                </pre>
              </div>
            </section>
          )}

          {/* ================= TAB 3: INVENTORY ================= */}
          {activeTab === 'inventory' && (
            <section className="rag-tab-content">
              <div className="rag-inventory-panel">
                <div className="rag-inventory-head">
                  <h3>Indexed RAG Documents ({indexedDocs.length})</h3>
                  <button
                    type="button"
                    className="rag-btn rag-btn--ghost rag-btn--sm"
                    onClick={loadInventory}
                    disabled={loadingDocs}
                  >
                    🔄 Refresh
                  </button>
                </div>

                {loadingDocs ? (
                  <div className="rag-empty">
                    <span className="rag-spinner" aria-hidden="true" />
                    <p>Loading document inventory…</p>
                  </div>
                ) : indexedDocs.length === 0 ? (
                  <div className="rag-empty">
                    <span className="rag-empty-icon">🗂️</span>
                    <p>
                      No RAG documents indexed for this selection. Click{' '}
                      <strong>⚡ Index Scope</strong> to build the vector knowledge
                      layer.
                    </p>
                  </div>
                ) : (
                  <div className="rag-inventory-wrap">
                    <table className="rag-inventory-table">
                      <thead>
                        <tr>
                          <th>Phase</th>
                          <th>Type</th>
                          <th>Title</th>
                          <th>Logical ID</th>
                          <th>Content Hash</th>
                          <th>Created</th>
                        </tr>
                      </thead>
                      <tbody>
                        {indexedDocs.map((d) => (
                          <tr key={d.id}>
                            <td>
                              <span
                                className="rag-inventory-phase"
                                style={{ background: getPhaseBadgeColor(d.source_phase) }}
                              >
                                {d.source_phase.replace('_', ' ')}
                              </span>
                            </td>
                            <td>{d.document_type}</td>
                            <td>
                              <strong>{d.title}</strong>
                            </td>
                            <td className="rag-mono">{d.logical_document_id}</td>
                            <td className="rag-mono">
                              {d.content_hash?.slice(0, 12)}…
                            </td>
                            <td>{new Date(d.created_at).toLocaleString()}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </section>
          )}
        </div>

        {/* ================= SIDEBAR ================= */}
        <aside className="rag-sidebar">
          <div className="rag-sidebar-head">
            <span>⌁</span> Filters
          </div>

          <div className="rag-sidebar-section">
            <span className="rag-sidebar-label">Quick queries</span>
            {QUICK_QUERIES.map((qText) => (
              <button
                key={qText}
                type="button"
                className="rag-sidebar-query"
                onClick={() => setQuery(qText)}
              >
                {qText}
              </button>
            ))}
          </div>

          <div className="rag-sidebar-section">
            <span className="rag-sidebar-label">Phase filter</span>
            <div className="rag-sidebar-chips">
              {PHASE_OPTIONS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className={`rag-sidebar-chip ${
                    selectedPhases.includes(p.id) ? 'rag-sidebar-chip--active' : ''
                  }`}
                  onClick={() => togglePhase(p.id)}
                >
                  {p.label}
                </button>
              ))}
            </div>
          </div>

          <div className="rag-sidebar-section">
            <div className="rag-slider-row">
              <span className="rag-sidebar-label">Top-K chunks</span>
              <b className="rag-slider-value">{topK}</b>
            </div>
            <input
              type="range"
              min="1"
              max="15"
              value={topK}
              onChange={(e) => setTopK(e.target.value)}
              className="rag-slider"
            />
          </div>

          <div className="rag-sidebar-section">
            <span className="rag-sidebar-label">Categories</span>
            <div className="rag-category-grid">
              {PHASE_OPTIONS.slice(0, 6).map((p) => (
                <button
                  key={p.id}
                  type="button"
                  className="rag-category-card"
                  onClick={() => togglePhase(p.id)}
                >
                  <span>{p.icon}</span>
                  <small>{p.label}</small>
                </button>
              ))}
            </div>
          </div>
        </aside>
      </div>
    </div>
  );
}