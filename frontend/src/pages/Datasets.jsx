/**
 * DataGuard AI — Dataset Browser Page
 *
 * Implements Phase 3 Dataset & Version Explorer:
 * - List all logical datasets with version counts and latest stats
 * - Expandable version history timeline per dataset
 * - Quick search and filtering
 * - Dataset deletion with cascade cleanup
 */

import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getDatasets, getDataset, deleteDataset } from '../api/client';

export default function Datasets() {
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
    fetchDatasets();
  }, []);

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

    // Fetch full version history if not already cached
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
    if (!window.confirm(`Are you sure you want to delete dataset "${datasetName}" and all its versions?`)) {
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
    d.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="datasets-page">
      {/* Header Block */}
      <div className="page-header-block">
        <div>
          <h1 className="page-heading">Dataset Repository & Versions</h1>
          <p className="page-subheading">
            Manage logical datasets and their snapshot version history for quality tracking and future drift analysis.
          </p>
        </div>
        <Link to="/upload" className="btn btn--primary" id="upload-nav-btn">
          ➕ Upload New Version
        </Link>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert-box alert-box--error">
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            <strong>Database Error</strong>
            <p>{error}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Filter / Search Bar */}
      <div className="dataset-toolbar">
        <div className="search-box">
          <span className="search-icon">🔍</span>
          <input
            type="text"
            placeholder="Search datasets by name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="search-input"
            id="dataset-search-input"
          />
          {searchQuery && (
            <button className="search-clear" onClick={() => setSearchQuery('')}>✕</button>
          )}
        </div>
        <button
          className="btn btn--secondary"
          onClick={fetchDatasets}
          disabled={loading}
          title="Refresh repository"
          id="refresh-datasets-btn"
        >
          🔄 Refresh
        </button>
      </div>

      {/* Loading State */}
      {loading && (
        <div className="loading-container">
          <div className="spinner-large"></div>
          <p className="loading-text">Loading datasets from PostgreSQL...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && datasets.length === 0 && !error && (
        <div className="placeholder-card placeholder-card--spacious" id="empty-datasets-card">
          <span className="placeholder-icon">🗃️</span>
          <h2>No Datasets Found</h2>
          <p className="placeholder-text">
            No datasets have been ingested yet. Upload your first CSV or Excel file to start tracking schema and version history.
          </p>
          <Link to="/upload" className="btn btn--primary">
            🚀 Ingest Your First Dataset
          </Link>
        </div>
      )}

      {/* Datasets List / Grid */}
      {!loading && filteredDatasets.length > 0 && (
        <div className="datasets-list" id="datasets-container">
          {filteredDatasets.map((ds) => {
            const isExpanded = expandedDatasetId === ds.id;
            const details = datasetDetails[ds.id];

            return (
              <div
                key={ds.id}
                className={`dataset-card ${isExpanded ? 'dataset-card--expanded' : ''}`}
                id={`dataset-card-${ds.id}`}
              >
                {/* Card Main Row */}
                <div className="dataset-card-header" onClick={() => toggleExpand(ds.id)}>
                  <div className="dataset-main-info">
                    <div className="dataset-title-row">
                      <span className="dataset-icon">📁</span>
                      <h3 className="dataset-name">{ds.name}</h3>
                      <span className="badge badge--accent">
                        {ds.version_count} {ds.version_count === 1 ? 'version' : 'versions'}
                      </span>
                      <span className="badge badge--success">
                        Latest: V{ds.latest_version_number}
                      </span>
                    </div>
                    {ds.description && (
                      <p className="dataset-desc">{ds.description}</p>
                    )}
                    <div className="dataset-meta-chips">
                      <span className="meta-chip">
                        📊 <strong>{ds.latest_row_count.toLocaleString()}</strong> rows
                      </span>
                      <span className="meta-chip">
                        📐 <strong>{ds.latest_column_count}</strong> columns
                      </span>
                      <span className="meta-chip">
                        🕒 Updated {new Date(ds.latest_upload_time).toLocaleString()}
                      </span>
                    </div>
                  </div>

                  <div className="dataset-card-actions">
                    <button
                      className="btn btn--secondary btn--sm"
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleExpand(ds.id);
                      }}
                      id={`toggle-versions-${ds.id}`}
                    >
                      {isExpanded ? '▲ Hide Versions' : '▼ Version History'}
                    </button>
                    <button
                      className="btn btn--danger-outline btn--sm"
                      onClick={(e) => handleDelete(ds.id, ds.name, e)}
                      disabled={deletingId === ds.id}
                      title="Delete dataset"
                      id={`delete-dataset-${ds.id}`}
                    >
                      {deletingId === ds.id ? 'Deleting...' : '🗑️ Delete'}
                    </button>
                  </div>
                </div>

                {/* Expanded Version History Drawer */}
                {isExpanded && (
                  <div className="version-timeline-drawer" id={`versions-drawer-${ds.id}`}>
                    <div className="drawer-header">
                      <h4 className="drawer-title">
                        📜 Snapshot Version History ({details?.versions?.length || ds.version_count})
                      </h4>
                      <Link
                        to={`/upload?dataset=${encodeURIComponent(ds.name)}`}
                        className="btn btn--primary btn--sm"
                      >
                        ➕ Upload V{(ds.latest_version_number || 0) + 1}
                      </Link>
                    </div>

                    {loadingDetailId === ds.id ? (
                      <div className="drawer-loading">
                        <span className="spinner-inline"></span> Loading version records...
                      </div>
                    ) : details?.versions ? (
                      <div className="table-responsive">
                        <table className="data-table version-table">
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
                              <tr key={v.id} className={v.version_number === ds.latest_version_number ? 'row-latest' : ''}>
                                <td>
                                  <div className="version-badge-cell">
                                    <span className={`version-pill ${v.version_number === ds.latest_version_number ? 'version-pill--latest' : ''}`}>
                                      V{v.version_number}
                                    </span>
                                    {v.version_number === ds.latest_version_number && (
                                      <span className="latest-tag">Latest</span>
                                    )}
                                  </div>
                                </td>
                                <td>
                                  <span className="file-name-cell">{v.original_filename}</span>
                                </td>
                                <td>
                                  <span className="badge badge--neutral">{v.file_type.toUpperCase()}</span>
                                  {v.sheet_name && <span className="sheet-tag">• {v.sheet_name}</span>}
                                </td>
                                <td>
                                  <strong>{v.row_count.toLocaleString()}</strong> rows × <strong>{v.column_count}</strong> cols
                                </td>
                                <td className="text-muted">
                                  {(v.file_size_bytes / 1024).toFixed(1)} KB
                                </td>
                                <td className="text-muted">
                                  {new Date(v.uploaded_at).toLocaleString()}
                                </td>
                                <td>
                                    <div className="flex-row" style={{ gap: '8px' }}>
                                      <Link
                                        to={`/datasets/${ds.id}/versions/${v.id}/profile`}
                                        className="btn btn--secondary btn--sm"
                                        id={`view-profile-${v.id}`}
                                      >
                                        📊 Profile
                                      </Link>
                                      <Link
                                        to={`/datasets/${ds.id}/versions/${v.id}/quality`}
                                        className="btn btn--secondary btn--sm"
                                        id={`view-quality-${v.id}`}
                                        style={{ borderColor: 'rgba(99, 102, 241, 0.4)' }}
                                      >
                                        🛡 Quality
                                      </Link>
                                      <Link
                                        to={`/datasets/${ds.id}/versions/${v.id}/pii`}
                                        className="btn btn--secondary btn--sm"
                                        id={`view-pii-${v.id}`}
                                        style={{ borderColor: 'rgba(236, 72, 153, 0.4)' }}
                                      >
                                        🔐 PII
                                      </Link>
                                    </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <p className="text-muted p-md">No versions found.</p>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
