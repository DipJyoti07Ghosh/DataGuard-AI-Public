/**
 * DataGuard AI — Phase 11 RAG Knowledge Explorer
 * 
 * Developer & Audit inspection interface for testing semantic vector retrieval,
 * verifying privacy sanitization, inspecting source traceability, and previewing
 * the assembled grounded context payload for Phase 12 LLMs.
 */

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
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
  "What data quality issues were detected?",
  "Which columns contain sensitive PII exposure?",
  "Why is income classified as high ML risk?",
  "What anomalies or outlier rates were found?",
  "What changed between dataset versions?",
  "What are the highest priority remediation suggestions?",
];

export default function RAGExplorer() {
  const { datasetId: paramDatasetId, versionId: paramVersionId } = useParams();
  const navigate = useNavigate();

  // Dataset & Scope state
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(paramDatasetId || '');
  const [selectedDataset, setSelectedDataset] = useState(null);
  const [scope, setScope] = useState(paramVersionId ? 'VERSION' : 'VERSION');
  const [selectedVersionId, setSelectedVersionId] = useState(paramVersionId || '');
  const [comparisons, setComparisons] = useState([]);
  const [selectedComparisonId, setSelectedComparisonId] = useState('');

  // Query state
  const [query, setQuery] = useState('What data quality and sensitive data issues were detected?');
  const [topK, setTopK] = useState(5);
  const [selectedPhases, setSelectedPhases] = useState([]);
  const [includeComparisons, setIncludeComparisons] = useState(false);

  // Results & UI state
  const [activeTab, setActiveTab] = useState('retrieved'); // 'retrieved' | 'context' | 'inventory'
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

  // 1. Initial Load: Fetch all datasets
  useEffect(() => {
    async function loadDatasetsList() {
      setLoadingDatasets(true);
      try {
        const res = await getDatasets();
        const list = res?.datasets || [];
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

  // 2. When selected dataset changes, load full dataset details and comparisons
  useEffect(() => {
    if (!selectedDatasetId) return;

    async function loadDatasetDetails() {
      try {
        const d = await getDataset(selectedDatasetId);
        setSelectedDataset(d);
        if (d.versions?.length > 0) {
          if (!selectedVersionId || !d.versions.some(v => v.id === selectedVersionId)) {
            setSelectedVersionId(d.versions[0].id);
          }
        } else {
          setSelectedVersionId('');
        }

        // Load comparisons
        const compRes = await getDatasetComparisons(selectedDatasetId);
        const compList = compRes?.comparisons || [];
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

  // 3. Load indexed document inventory
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

  // Handle Indexing
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
        `Successfully indexed ${res.total_indexed} documents (${res.new_documents} new, ${res.updated_documents} updated, ${res.skipped_unchanged} skipped).`
      );
      loadInventory();
    } catch (err) {
      setErrorMessage(`Indexing failed: ${err.message}`);
    } finally {
      setIndexing(false);
    }
  }

  // Handle Semantic Retrieval
  async function handleRetrieve(e) {
    if (e) e.preventDefault();
    if (!selectedDatasetId || !query.trim()) return;

    setRetrieving(true);
    setErrorMessage('');

    try {
      const req = {
        query: query.trim(),
        scope: scope,
        top_k: Number(topK),
        phases: selectedPhases.length > 0 ? selectedPhases : null,
      };

      if (scope === 'VERSION') {
        if (!selectedVersionId) {
          throw new Error("Please select a dataset version.");
        }
        req.version_id = selectedVersionId;
        req.include_comparisons = includeComparisons;
      } else if (scope === 'COMPARISON') {
        if (!selectedComparisonId) {
          throw new Error("Please select a version comparison.");
        }
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
    setSelectedPhases(prev =>
      prev.includes(phaseId) ? prev.filter(p => p !== phaseId) : [...prev, phaseId]
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
    <div className="page-container" style={{ padding: '2rem', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Page Header */}
      <div className="flex-between" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="flex-row" style={{ gap: '0.75rem', alignItems: 'center', marginBottom: '0.25rem' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: 700 }}>
              🧠 RAG Knowledge Explorer
            </h1>
            <span className="badge badge--primary" style={{ fontSize: '0.8rem' }}>Phase 11 Native pgvector</span>
          </div>
          <p className="text-secondary" style={{ margin: 0, fontSize: '0.9rem' }}>
            Inspect semantic vector retrieval, verify privacy sanitization, and test grounded factual context assembly.
          </p>
        </div>

        {/* Global Controls */}
        <div className="flex-row" style={{ gap: '0.75rem', alignItems: 'center' }}>
          <button
            className="btn btn--secondary"
            onClick={() => handleIndex(false)}
            disabled={indexing || !selectedDatasetId}
          >
            {indexing ? '⚡ Indexing...' : '⚡ Index Scope'}
          </button>
          <button
            className="btn btn--outline"
            onClick={() => handleIndex(true)}
            disabled={indexing || !selectedDatasetId}
            title="Bypass cache and force re-embed all documents"
          >
            Force Re-index
          </button>
        </div>
      </div>

      {/* Alerts */}
      {errorMessage && (
        <div className="glass-card" style={{ padding: '0.85rem 1.25rem', marginBottom: '1rem', borderLeft: '4px solid #ef4444', color: '#f87171' }}>
          ⚠️ {errorMessage}
        </div>
      )}
      {successMessage && (
        <div className="glass-card" style={{ padding: '0.85rem 1.25rem', marginBottom: '1rem', borderLeft: '4px solid #10b981', color: '#34d399' }}>
          ✅ {successMessage}
        </div>
      )}

      {/* Top Scope & Selector Glass Card */}
      <div className="glass-card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <div className="grid-3" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
          {/* Dataset Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.35rem' }}>
              DATASET
            </label>
            <select
              className="select-input"
              value={selectedDatasetId}
              onChange={(e) => setSelectedDatasetId(e.target.value)}
              style={{ width: '100%' }}
            >
              {datasets.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.name} ({d.versions?.length || 0} versions)
                </option>
              ))}
            </select>
          </div>

          {/* Scope Selector */}
          <div>
            <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.35rem' }}>
              RETRIEVAL SCOPE
            </label>
            <select
              className="select-input"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
              style={{ width: '100%' }}
            >
              <option value="VERSION">VERSION (Specific Snapshot)</option>
              <option value="COMPARISON">COMPARISON (Drift Snapshot)</option>
              <option value="DATASET">DATASET (Cross-Version Overview)</option>
            </select>
          </div>

          {/* Version or Comparison Target Selector */}
          <div>
            {scope === 'VERSION' && (
              <>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.35rem' }}>
                  DATASET VERSION
                </label>
                <select
                  className="select-input"
                  value={selectedVersionId}
                  onChange={(e) => setSelectedVersionId(e.target.value)}
                  style={{ width: '100%' }}
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
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.35rem' }}>
                  VERSION COMPARISON
                </label>
                <select
                  className="select-input"
                  value={selectedComparisonId}
                  onChange={(e) => setSelectedComparisonId(e.target.value)}
                  style={{ width: '100%' }}
                >
                  {comparisons.length === 0 && <option value="">No comparisons yet</option>}
                  {comparisons.map((c) => (
                    <option key={c.id} value={c.id}>
                      V{c.baseline_version?.version_number} ➔ V{c.current_version?.version_number} ({c.overall_drift_status})
                    </option>
                  ))}
                </select>
              </>
            )}

            {scope === 'DATASET' && (
              <>
                <label style={{ display: 'block', fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', marginBottom: '0.35rem' }}>
                  INVENTORY STATUS
                </label>
                <div style={{ paddingTop: '0.5rem', fontSize: '0.85rem', color: '#94a3b8' }}>
                  {indexedDocs.length} total indexed chunks across all versions
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {/* Main Grid: Query & Search on Left/Top, Results on Bottom */}
      <div className="glass-card" style={{ padding: '1.25rem', marginBottom: '1.5rem' }}>
        <form onSubmit={handleRetrieve}>
          {/* Query Bar */}
          <label style={{ display: 'block', fontSize: '0.85rem', fontWeight: 600, color: '#e2e8f0', marginBottom: '0.5rem' }}>
            🔍 SEMANTIC RETRIEVAL QUERY
          </label>
          <div className="flex-row" style={{ gap: '0.75rem', marginBottom: '0.75rem' }}>
            <input
              type="text"
              className="text-input"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="e.g. What data quality issues or sensitive PII exposures were found?"
              style={{ flex: 1, padding: '0.75rem 1rem', fontSize: '0.95rem' }}
            />
            <button
              type="submit"
              className="btn btn--primary"
              disabled={retrieving || !query.trim()}
              style={{ padding: '0.75rem 1.5rem', fontWeight: 600 }}
            >
              {retrieving ? '🔎 Searching...' : '🔎 Retrieve'}
            </button>
          </div>

          {/* Quick Query Recommendation Pills */}
          <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
            <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', alignSelf: 'center' }}>
              Quick Queries:
            </span>
            {QUICK_QUERIES.map((qText, i) => (
              <button
                key={i}
                type="button"
                className="badge badge--neutral"
                style={{ cursor: 'pointer', border: '1px solid rgba(148, 163, 184, 0.2)', padding: '0.3rem 0.6rem' }}
                onClick={() => setQuery(qText)}
              >
                {qText}
              </button>
            ))}
          </div>

          {/* Filtering & Parameters Row */}
          <div className="flex-between" style={{ flexWrap: 'wrap', gap: '1rem', paddingTop: '0.75rem', borderTop: '1px solid rgba(148, 163, 184, 0.1)' }}>
            {/* Phase Filters */}
            <div className="flex-row" style={{ gap: '0.5rem', flexWrap: 'wrap', alignItems: 'center' }}>
              <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', marginRight: '0.25rem' }}>
                Phase Filter:
              </span>
              {PHASE_OPTIONS.map((p) => {
                const active = selectedPhases.includes(p.id);
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => togglePhase(p.id)}
                    className={`badge ${active ? 'badge--primary' : 'badge--neutral'}`}
                    style={{
                      cursor: 'pointer',
                      padding: '0.3rem 0.65rem',
                      background: active ? getPhaseBadgeColor(p.id) : undefined,
                      color: active ? '#fff' : undefined,
                    }}
                  >
                    {p.icon} {p.label}
                  </button>
                );
              })}
              {selectedPhases.length > 0 && (
                <button
                  type="button"
                  className="btn btn--sm btn--text"
                  onClick={() => setSelectedPhases([])}
                  style={{ fontSize: '0.75rem', color: '#94a3b8' }}
                >
                  Clear
                </button>
              )}
            </div>

            {/* Top-K Slider & Option */}
            <div className="flex-row" style={{ gap: '1.25rem', alignItems: 'center' }}>
              {scope === 'VERSION' && (
                <label className="flex-row" style={{ gap: '0.4rem', fontSize: '0.8rem', color: '#94a3b8', cursor: 'pointer' }}>
                  <input
                    type="checkbox"
                    checked={includeComparisons}
                    onChange={(e) => setIncludeComparisons(e.target.checked)}
                  />
                  Include Version Drift
                </label>
              )}
              <div className="flex-row" style={{ gap: '0.5rem', alignItems: 'center' }}>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase' }}>
                  Top-K Chunks:
                </span>
                <input
                  type="range"
                  min="1"
                  max="15"
                  value={topK}
                  onChange={(e) => setTopK(e.target.value)}
                  style={{ width: '80px' }}
                />
                <span style={{ fontWeight: 700, fontSize: '0.85rem' }}>{topK}</span>
              </div>
            </div>
          </div>
        </form>
      </div>

      {/* Navigation Tabs */}
      <div className="flex-row" style={{ gap: '1rem', borderBottom: '1px solid rgba(148, 163, 184, 0.2)', marginBottom: '1.5rem' }}>
        <button
          className={`tab-btn ${activeTab === 'retrieved' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('retrieved')}
          style={{ padding: '0.75rem 1.25rem', background: 'none', border: 'none', color: activeTab === 'retrieved' ? '#38bdf8' : '#94a3b8', borderBottom: activeTab === 'retrieved' ? '2px solid #38bdf8' : 'none', fontWeight: 600, cursor: 'pointer' }}
        >
          📑 Retrieved Chunks ({retrievalResult?.sources?.length || 0})
        </button>
        <button
          className={`tab-btn ${activeTab === 'context' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('context')}
          style={{ padding: '0.75rem 1.25rem', background: 'none', border: 'none', color: activeTab === 'context' ? '#38bdf8' : '#94a3b8', borderBottom: activeTab === 'context' ? '2px solid #38bdf8' : 'none', fontWeight: 600, cursor: 'pointer' }}
        >
          🧩 Grounded Context Payload (Phase 12 Preview)
        </button>
        <button
          className={`tab-btn ${activeTab === 'inventory' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('inventory')}
          style={{ padding: '0.75rem 1.25rem', background: 'none', border: 'none', color: activeTab === 'inventory' ? '#38bdf8' : '#94a3b8', borderBottom: activeTab === 'inventory' ? '2px solid #38bdf8' : 'none', fontWeight: 600, cursor: 'pointer' }}
        >
          🗂️ Indexed Document Inventory ({indexedDocs.length})
        </button>
      </div>

      {/* Tab 1: Retrieved Chunks */}
      {activeTab === 'retrieved' && (
        <div>
          {retrieving ? (
            <div style={{ textAlign: 'center', padding: '3rem' }}>
              <span className="spinner-inline"></span> Executing vector cosine similarity search via pgvector...
            </div>
          ) : !retrievalResult ? (
            <div className="glass-card" style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>
              💡 Enter a query above and click <strong>Retrieve</strong> to search the RAG knowledge layer.
            </div>
          ) : retrievalResult.sources.length === 0 ? (
            <div className="glass-card" style={{ padding: '2rem', textAlign: 'center', color: '#94a3b8' }}>
              No matching knowledge chunks found. Ensure the dataset version is indexed by clicking <strong>⚡ Index Scope</strong>.
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {retrievalResult.warnings?.length > 0 && (
                <div className="glass-card" style={{ padding: '0.75rem 1rem', borderLeft: '4px solid #f59e0b', color: '#fbbf24', fontSize: '0.85rem' }}>
                  {retrievalResult.warnings.map((w, i) => (
                    <div key={i}>⚠️ {w}</div>
                  ))}
                </div>
              )}

              {retrievalResult.sources.map((src, i) => (
                <div
                  key={src.document_id || i}
                  className="glass-card"
                  style={{
                    padding: '1.25rem',
                    borderLeft: `4px solid ${getPhaseBadgeColor(src.source_phase)}`,
                  }}
                >
                  {/* Card Header */}
                  <div className="flex-between" style={{ marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <div className="flex-row" style={{ gap: '0.5rem', alignItems: 'center' }}>
                      <span
                        className="badge"
                        style={{
                          background: getPhaseBadgeColor(src.source_phase),
                          color: '#fff',
                          fontWeight: 600,
                          fontSize: '0.75rem',
                        }}
                      >
                        {src.source_phase.replace('_', ' ')}
                      </span>
                      <span className="badge badge--neutral" style={{ fontSize: '0.75rem' }}>
                        {src.document_type}
                      </span>
                      {src.column_name && (
                        <span className="badge badge--neutral" style={{ fontSize: '0.75rem', fontWeight: 600 }}>
                          Column: {src.column_name}
                        </span>
                      )}
                    </div>

                    {/* Similarity Metric Badge */}
                    <div className="flex-row" style={{ gap: '0.5rem', alignItems: 'center' }}>
                      <span
                        className="badge"
                        style={{
                          background: src.similarity >= 0.7 ? 'rgba(16, 185, 129, 0.2)' : 'rgba(59, 130, 246, 0.2)',
                          color: src.similarity >= 0.7 ? '#34d399' : '#60a5fa',
                          border: `1px solid ${src.similarity >= 0.7 ? '#10b981' : '#3b82f6'}`,
                          fontWeight: 700,
                          fontSize: '0.8rem',
                        }}
                      >
                        {(src.similarity * 100).toFixed(1)}% Relevance ({src.similarity.toFixed(4)})
                      </span>
                    </div>
                  </div>

                  {/* Card Content */}
                  <div style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem', lineHeight: '1.5', color: '#f1f5f9', marginBottom: '0.75rem' }}>
                    {src.content}
                  </div>

                  {/* Traceability Toggle */}
                  <div className="flex-between" style={{ borderTop: '1px solid rgba(148, 163, 184, 0.1)', paddingTop: '0.5rem' }}>
                    <button
                      type="button"
                      className="btn btn--sm btn--text"
                      onClick={() => setExpandedTraceId(expandedTraceId === src.document_id ? null : src.document_id)}
                      style={{ fontSize: '0.75rem', color: '#94a3b8' }}
                    >
                      {expandedTraceId === src.document_id ? '▲ Hide Traceability Metadata' : '▼ Show Source Traceability'}
                    </button>
                    <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                      Source ID: {src.document_id?.slice(0, 8)}...
                    </span>
                  </div>

                  {/* Traceability Details Panel */}
                  {expandedTraceId === src.document_id && (
                    <div style={{ marginTop: '0.75rem', padding: '0.75rem', background: 'rgba(0,0,0,0.3)', borderRadius: '6px', fontSize: '0.75rem', color: '#cbd5e1' }}>
                      <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                        <div><strong>Document ID:</strong> {src.document_id}</div>
                        <div><strong>Source Phase:</strong> {src.source_phase}</div>
                        <div><strong>Embedding Provider:</strong> fastembed</div>
                        <div><strong>Embedding Model:</strong> BAAI/bge-small-en-v1.5 (384-d)</div>
                        <div><strong>Metadata:</strong> {JSON.stringify(src.metadata)}</div>
                      </div>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Grounded Context Payload */}
      {activeTab === 'context' && (
        <div className="glass-card" style={{ padding: '1.5rem' }}>
          <div className="flex-between" style={{ marginBottom: '1rem' }}>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
                Phase 12 Grounded Context Payload
              </h3>
              <p className="text-secondary" style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem' }}>
                This is the exact, sanitized factual markdown context assembled for future LLM prompt injection.
              </p>
            </div>
            {retrievalResult?.grounded_context_text && (
              <button
                className="btn btn--secondary btn--sm"
                onClick={() => {
                  navigator.clipboard.writeText(retrievalResult.grounded_context_text);
                  setSuccessMessage('Grounded context copied to clipboard!');
                }}
              >
                📋 Copy Markdown
              </button>
            )}
          </div>

          <pre
            style={{
              background: 'rgba(15, 23, 42, 0.8)',
              padding: '1.25rem',
              borderRadius: '8px',
              border: '1px solid rgba(148, 163, 184, 0.2)',
              fontSize: '0.825rem',
              lineHeight: '1.6',
              whiteSpace: 'pre-wrap',
              wordBreak: 'break-word',
              color: '#e2e8f0',
              maxHeight: '600px',
              overflowY: 'auto',
            }}
          >
            {retrievalResult?.grounded_context_text || "No grounded context assembled yet. Execute a query to generate context."}
          </pre>
        </div>
      )}

      {/* Tab 3: Indexed Document Inventory */}
      {activeTab === 'inventory' && (
        <div className="glass-card" style={{ padding: '1.25rem' }}>
          <div className="flex-between" style={{ marginBottom: '1rem' }}>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 600 }}>
              Indexed RAG Documents ({indexedDocs.length})
            </h3>
            <button
              className="btn btn--secondary btn--sm"
              onClick={loadInventory}
              disabled={loadingDocs}
            >
              🔄 Refresh Inventory
            </button>
          </div>

          {loadingDocs ? (
            <div style={{ textAlign: 'center', padding: '2rem' }}>
              <span className="spinner-inline"></span> Loading document inventory...
            </div>
          ) : indexedDocs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#94a3b8' }}>
              No RAG documents indexed for this selection. Click <strong>⚡ Index Scope</strong> to build the vector knowledge layer.
            </div>
          ) : (
            <table className="data-table" style={{ width: '100%', fontSize: '0.8rem' }}>
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
                        className="badge"
                        style={{
                          background: getPhaseBadgeColor(d.source_phase),
                          color: '#fff',
                          fontSize: '0.7rem',
                        }}
                      >
                        {d.source_phase.replace('_', ' ')}
                      </span>
                    </td>
                    <td>{d.document_type}</td>
                    <td style={{ fontWeight: 600 }}>{d.title}</td>
                    <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>{d.logical_document_id}</td>
                    <td style={{ fontFamily: 'monospace', color: '#94a3b8' }}>{d.content_hash?.slice(0, 12)}...</td>
                    <td>{new Date(d.created_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
