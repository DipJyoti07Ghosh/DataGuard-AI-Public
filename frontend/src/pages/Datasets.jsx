/**
 * DataGuard AI — Dataset Browser Page
 *
 * Phase 3 Dataset & Version Explorer:
 * - List all logical datasets with version counts and latest stats
 * - Expandable version history timeline per dataset
 * - Quick search and filtering
 * - Dataset deletion with cascade cleanup
 *
 * Auth-aware:
 * - Authenticated users see their own datasets.
 * - Anonymous users see a sign-in prompt.
 *
 * Visual design: DATA GUARD AI workspace skin (.ds-* classes).
 * Backend contract: UNCHANGED.
 *   - getDatasets() / getDataset(id) / deleteDataset(id)
 *   - Every field path preserved.
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDatasets, getDataset, deleteDataset } from '../api/client';
import { useAuth } from '../context/AuthContext';
import './Datasets.css';

export default function Datasets() {
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [datasets, setDatasets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedDatasetId, setExpandedDatasetId] = useState(null);
  const [datasetDetails, setDatasetDetails] = useState({});
  const [loadingDetailId, setLoadingDetailId] = useState(null);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = 'Dataset Repository';

    if (isAuthenticated) {
      fetchDatasets();
    } else {
      setLoading(false);
    }
  }, [isAuthenticated]);

  async function fetchDatasets() {
    setLoading(true);
    setError(null);
    try {
      const data = await getDatasets();
      setDatasets(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleExpand(datasetId) {
    if (expandedDatasetId === datasetId) {
      setExpandedDatasetId(null);
      return;
    }

    setExpandedDatasetId(datasetId);

    if (!datasetDetails[datasetId]) {
      setLoadingDetailId(datasetId);
      try {
        const detail = await getDataset(datasetId);
        setDatasetDetails((prev) => ({ ...prev, [datasetId]: detail }));
      } catch (err) {
        console.error('Failed to load dataset versions:', err);
      } finally {
        setLoadingDetailId(null);
      }
    }
  }

  async function handleDelete(datasetId, datasetName, e) {
    e.stopPropagation();
    if (
      !window.confirm(
        `Are you sure you want to delete dataset "${datasetName}" and all its versions?`,
      )
    ) {
      return;
    }

    setDeletingId(datasetId);
    try {
      await deleteDataset(datasetId);
      setDatasets((prev) => prev.filter((d) => d.id !== datasetId));
      if (expandedDatasetId === datasetId) {
        setExpandedDatasetId(null);
      }
    } catch (err) {
      alert(`Delete failed: ${err.message}`);
    } finally {
      setDeletingId(null);
    }
  }

  const filteredDatasets = datasets.filter((d) =>
    d.name.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  return (
    <div className="ds-page">
      {/* ================= HERO ================= */}
      <header className="ds-hero">
        <div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Dataset Repository &amp; Versions</h1>
          <p>
            Manage logical datasets and their snapshot version history for
            quality tracking and future drift analysis.
          </p>
        </div>

        {isAuthenticated && (
          <Link to="/upload" className="ds-btn ds-btn--primary">
            ➕ Upload New Version
          </Link>
        )}
      </header>

      {/* ================= ANONYMOUS GATE ================= */}
      {!authLoading && !isAuthenticated && (
        <div className="ds-empty" id="anon-datasets-card">
          <span className="ds-empty-icon">🔒</span>
          <h2>Sign in to see your datasets</h2>
          <p className="ds-empty-desc">
            DataGuard AI keeps every user's datasets private. Sign in to
            upload, analyze, and chat about your own data — no other user can
            see your work.
          </p>
          <div className="ds-empty-actions">
            <Link to="/login" className="ds-btn ds-btn--primary">Sign In</Link>
            <Link to="/register" className="ds-btn ds-btn--ghost">Create Account</Link>
          </div>
        </div>
      )}

      {/* ================= AUTHENTICATED CONTENT ================= */}
      {isAuthenticated && (
        <>
          {/* Error banner */}
          {error && (
            <div className="ds-alert" role="alert">
              <span>⚠️</span>
              <div>
                <strong>Database Error</strong>
                <p>{error}</p>
              </div>
              <button onClick={() => setError(null)} aria-label="Dismiss">✕</button>
            </div>
          )}

          {/* Toolbar */}
          <div className="ds-toolbar">
            <label className="ds-search">
              <span aria-hidden="true">🔍</span>
              <input
                type="text"
                placeholder="Search datasets by name…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                id="dataset-search-input"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="ds-search-clear"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search"
                >
                  ✕
                </button>
              )}
            </label>

            <button
              type="button"
              className="ds-btn ds-btn--ghost"
              onClick={fetchDatasets}
              disabled={loading}
              id="refresh-datasets-btn"
            >
              🔄 Refresh
            </button>
          </div>

          {/* Loading */}
          {loading && (
            <div className="ds-loading">
              <span className="ds-spinner" aria-hidden="true" />
              <p>Loading datasets from PostgreSQL…</p>
            </div>
          )}

          {/* Empty */}
          {!loading && datasets.length === 0 && !error && (
            <div className="ds-empty" id="empty-datasets-card">
              <span className="ds-empty-icon">🗃️</span>
              <h2>No Datasets Found</h2>
              <p className="ds-empty-desc">
                No datasets have been ingested yet. Upload your first CSV or
                Excel file to start tracking schema and version history.
              </p>
              <Link to="/upload" className="ds-btn ds-btn--primary">
                🚀 Ingest Your First Dataset
              </Link>
            </div>
          )}

          {/* List */}
          {!loading && filteredDatasets.length > 0 && (
            <div className="ds-list" id="datasets-container">
              {filteredDatasets.map((ds) => {
                const isExpanded = expandedDatasetId === ds.id;
                const details = datasetDetails[ds.id];

                return (
                  <article
                    key={ds.id}
                    className={`ds-card ${isExpanded ? 'ds-card--expanded' : ''}`}
                    id={`dataset-card-${ds.id}`}
                  >
                    {/* Card main row */}
                    <div
                      className="ds-card-head"
                      onClick={() => toggleExpand(ds.id)}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          toggleExpand(ds.id);
                        }
                      }}
                    >
                      <div className="ds-card-info">
                        <div className="ds-title-row">
                          <span className="ds-icon">📁</span>
                          <h3 className="ds-name">{ds.name}</h3>
                          <span className="ds-badge ds-badge--accent">
                            {ds.version_count}{' '}
                            {ds.version_count === 1 ? 'version' : 'versions'}
                          </span>
                          <span className="ds-badge ds-badge--success">
                            Latest: V{ds.latest_version_number}
                          </span>
                        </div>

                        {ds.description && (
                          <p className="ds-desc">{ds.description}</p>
                        )}

                        <div className="ds-meta-chips">
                          <span className="ds-chip">
                            📊 <strong>{ds.latest_row_count.toLocaleString()}</strong> rows
                          </span>
                          <span className="ds-chip">
                            📐 <strong>{ds.latest_column_count}</strong> columns
                          </span>
                          <span className="ds-chip">
                            🕒 Updated {new Date(ds.latest_upload_time).toLocaleString()}
                          </span>
                        </div>
                      </div>

                      <div className="ds-card-actions">
                        <Link
                          to={`/datasets/${ds.id}/rag`}
                          className="ds-btn ds-btn--ghost ds-btn--sm ds-btn--cyan"
                          onClick={(e) => e.stopPropagation()}
                          id={`rag-dataset-${ds.id}`}
                        >
                          🧠 RAG Knowledge
                        </Link>

                        {ds.version_count >= 2 && (
                          <Link
                            to={`/datasets/${ds.id}/compare`}
                            className="ds-btn ds-btn--primary ds-btn--sm"
                            onClick={(e) => e.stopPropagation()}
                            id={`compare-dataset-${ds.id}`}
                          >
                            ⚖️ Compare Drift
                          </Link>
                        )}

                        <button
                          type="button"
                          className="ds-btn ds-btn--ghost ds-btn--sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            toggleExpand(ds.id);
                          }}
                          id={`toggle-versions-${ds.id}`}
                        >
                          {isExpanded ? '▲ Hide Versions' : '▼ Version History'}
                        </button>

                        <button
                          type="button"
                          className="ds-btn ds-btn--danger ds-btn--sm"
                          onClick={(e) => handleDelete(ds.id, ds.name, e)}
                          disabled={deletingId === ds.id}
                          title="Delete dataset"
                          id={`delete-dataset-${ds.id}`}
                        >
                          {deletingId === ds.id ? 'Deleting…' : '🗑️ Delete'}
                        </button>
                      </div>
                    </div>

                    {/* Expanded version history drawer */}
                    {isExpanded && (
                      <div className="ds-drawer" id={`versions-drawer-${ds.id}`}>
                        <div className="ds-drawer-head">
                          <h4>
                            📜 Snapshot Version History (
                            {details?.versions?.length || ds.version_count})
                          </h4>
                          <div className="ds-drawer-actions">
                            <Link
                              to={`/datasets/${ds.id}/assistant`}
                              className="ds-btn ds-btn--ghost ds-btn--sm"
                            >
                              🤖 Ask AI
                            </Link>

                            {details?.versions?.length >= 2 && (
                              <Link
                                to={`/datasets/${ds.id}/compare`}
                                className="ds-btn ds-btn--ghost ds-btn--sm"
                              >
                                ⚖️ Compare Versions
                              </Link>
                            )}

                            <Link
                              to={`/upload?dataset=${encodeURIComponent(ds.name)}`}
                              className="ds-btn ds-btn--primary ds-btn--sm"
                            >
                              ➕ Upload V{(ds.latest_version_number || 0) + 1}
                            </Link>
                          </div>
                        </div>

                        {loadingDetailId === ds.id ? (
                          <div className="ds-drawer-loading">
                            <span className="ds-spinner ds-spinner--sm" aria-hidden="true" />
                            Loading version records…
                          </div>
                        ) : details?.versions ? (
                          <div className="ds-table-wrap">
                            <table className="ds-version-table">
                              <thead>
                                <tr>
                                  <th>Version</th>
                                  <th>Source File</th>
                                  <th>Format</th>
                                  <th>Dimensions</th>
                                  <th>File Size</th>
                                  <th>Uploaded At</th>
                                  <th>Actions</th>
                                </tr>
                              </thead>
                              <tbody>
                                {details.versions.map((v) => (
                                  <tr
                                    key={v.id}
                                    className={
                                      v.version_number === ds.latest_version_number
                                        ? 'ds-row-latest'
                                        : ''
                                    }
                                  >
                                    <td>
                                      <div className="ds-version-badge-cell">
                                        <span
                                          className={`ds-version-pill ${
                                            v.version_number === ds.latest_version_number
                                              ? 'ds-version-pill--latest'
                                              : ''
                                          }`}
                                        >
                                          V{v.version_number}
                                        </span>
                                        {v.version_number === ds.latest_version_number && (
                                          <span className="ds-latest-tag">Latest</span>
                                        )}
                                      </div>
                                    </td>
                                    <td>
                                      <span className="ds-file-name">{v.original_filename}</span>
                                    </td>
                                    <td>
                                      <span className="ds-badge ds-badge--neutral">
                                        {v.file_type.toUpperCase()}
                                      </span>
                                      {v.sheet_name && (
                                        <span className="ds-sheet-tag">• {v.sheet_name}</span>
                                      )}
                                    </td>
                                    <td>
                                      <strong>{v.row_count.toLocaleString()}</strong> rows ×{' '}
                                      <strong>{v.column_count}</strong> cols
                                    </td>
                                    <td className="ds-muted">
                                      {(v.file_size_bytes / 1024).toFixed(1)} KB
                                    </td>
                                    <td className="ds-muted">
                                      {new Date(v.uploaded_at).toLocaleString()}
                                    </td>
                                    <td>
                                      <div className="ds-row-actions">
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/profile`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          📊 Profile
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/quality`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🛡 Quality
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/pii`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🔐 PII
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/risk`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🤖 Risk
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/anomalies`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          ⚠ Anomalies
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/issues`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🩺 Health
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/compare`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          ⚖️ Compare
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/rag`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🧠 RAG
                                        </Link>
                                        <Link
                                          to={`/datasets/${ds.id}/versions/${v.id}/assistant`}
                                          className="ds-btn ds-btn--ghost ds-btn--xs"
                                        >
                                          🤖 Ask AI
                                        </Link>
                                      </div>
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        ) : (
                          <p className="ds-muted ds-pad">No versions found.</p>
                        )}
                      </div>
                    )}
                  </article>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}