/**
 * DataGuard AI — Dataset Upload & Ingestion Page
 *
 * Implements Phase 2 & Phase 3 Upload:
 * - Dataset name specification (auto-populates from file or URL query param)
 * - Drag-and-drop file upload zone
 * - Extension and size validation
 * - PostgreSQL persistence of Dataset and sequential DatasetVersion
 * - Metadata inspection view & sample preview
 * - Direct link to view full version history in Dataset Browser
 */

import { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { uploadDataset } from '../api/client';

const MAX_SIZE_MB = 100;
const ALLOWED_EXTS = ['.csv', '.xlsx'];

export default function Upload() {
  const [searchParams] = useSearchParams();
  const [datasetName, setDatasetName] = useState(searchParams.get('dataset') || '');
  const [description, setDescription] = useState('');
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [metadata, setMetadata] = useState(null);
  const [activeTab, setActiveTab] = useState('columns'); // 'columns' | 'preview'
  const fileInputRef = useRef(null);

  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) {
      titleEl.textContent = metadata
        ? `Dataset: ${metadata.dataset_name} (V${metadata.version_number || 1})`
        : 'Upload Dataset';
    }
  }, [metadata]);

  const validateLocalFile = (selectedFile) => {
    if (!selectedFile) return 'No file selected.';

    const ext = '.' + selectedFile.name.split('.').pop().toLowerCase();
    if (!ALLOWED_EXTS.includes(ext)) {
      return `Invalid file format (${ext}). Supported formats: ${ALLOWED_EXTS.join(', ')}`;
    }

    if (selectedFile.size === 0) {
      return 'Selected file is empty (0 bytes).';
    }

    if (selectedFile.size > MAX_SIZE_MB * 1024 * 1024) {
      return `File size (${(selectedFile.size / (1024 * 1024)).toFixed(1)} MB) exceeds the ${MAX_SIZE_MB} MB limit.`;
    }

    return null;
  };

  const handleFileSelect = (selectedFile) => {
    setError(null);
    const validationError = validateLocalFile(selectedFile);
    if (validationError) {
      setError(validationError);
      setFile(null);
      return;
    }
    setFile(selectedFile);

    // If datasetName is empty, auto-populate from file stem
    if (!datasetName) {
      const stem = selectedFile.name.replace(/\.[^/.]+$/, '').replace(/[_\-\.]+/g, ' ');
      setDatasetName(stem);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileSelect(e.dataTransfer.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      const response = await uploadDataset(file, datasetName, description);
      setMetadata(response);
    } catch (err) {
      setError(err.message || 'An error occurred while uploading the dataset.');
    } finally {
      setUploading(false);
    }
  };

  const handleReset = () => {
    setFile(null);
    setMetadata(null);
    setError(null);
    setDatasetName('');
    setDescription('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const getDtypeBadgeClass = (dtype) => {
    if (dtype.includes('int') || dtype.includes('float')) return 'dtype-numeric';
    if (dtype.includes('datetime') || dtype.includes('date')) return 'dtype-datetime';
    if (dtype.includes('bool')) return 'dtype-bool';
    return 'dtype-object';
  };

  return (
    <div className="upload-page">
      {/* Upload Header */}
      <div className="page-header-block">
        <div>
          <h1 className="page-heading">Dataset Upload & Ingestion</h1>
          <p className="page-subheading">
            Upload CSV or Excel spreadsheets to parse schema, calculate column statistics, and persist version history in PostgreSQL.
          </p>
        </div>
        {metadata && (
          <div className="header-action-group">
            {metadata.dataset_id && metadata.version_id && (
              <Link
                to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/profile`}
                className="btn btn--primary"
                id="view-profile-btn"
              >
                📊 View Automated Profile
              </Link>
            )}
            <Link to="/datasets" className="btn btn--secondary" id="view-datasets-btn">
              🗃️ View in Repository
            </Link>
            <button className="btn btn--secondary" onClick={handleReset} id="upload-new-btn">
              ➕ Upload Another Version
            </button>
          </div>
        )}
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert-box alert-box--error" id="upload-error-alert">
          <div className="alert-icon">⚠️</div>
          <div className="alert-content">
            <strong>Upload Error</strong>
            <p>{error}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Drag & Drop Upload Zone + Dataset Name (Shown when no metadata is loaded) */}
      {!metadata && (
        <div className="upload-container">
          {/* Logical Dataset Metadata Inputs */}
          <div className="card upload-config-card">
            <div className="form-group">
              <label className="form-label" htmlFor="dataset-name-input">
                Logical Dataset Name <span className="label-required">*</span>
              </label>
              <input
                type="text"
                id="dataset-name-input"
                className="form-input"
                placeholder="e.g. Customer Data, Sales Transactions, Inventory Q3..."
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
              />
              <span className="form-hint">
                Files uploaded with the same dataset name will be automatically grouped as sequential versions (V1, V2, V3...).
              </span>
            </div>
          </div>

          <div
            className={`dropzone ${isDragging ? 'dropzone--active' : ''} ${file ? 'dropzone--has-file' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
            id="dataset-dropzone"
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              accept=".csv,.xlsx"
              onChange={(e) => {
                if (e.target.files && e.target.files.length > 0) {
                  handleFileSelect(e.target.files[0]);
                }
              }}
              id="dataset-file-input"
            />

            <div className="dropzone-inner">
              <div className="dropzone-icon">
                {file ? '📄' : isDragging ? '📥' : '☁️'}
              </div>

              {file ? (
                <div className="file-preview-card">
                  <div className="file-info-primary">
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">({(file.size / 1024).toFixed(1)} KB)</span>
                  </div>
                  <div className="file-meta-pills">
                    <span className="badge badge--neutral">{file.name.split('.').pop().toUpperCase()}</span>
                    <span className="badge badge--accent">Target Dataset: {datasetName || 'Auto'}</span>
                    <span className="badge badge--success">Ready to Ingest</span>
                  </div>
                </div>
              ) : (
                <>
                  <h3 className="dropzone-title">
                    {isDragging ? 'Drop your dataset here' : 'Drag & drop your dataset file here'}
                  </h3>
                  <p className="dropzone-subtitle">or click browse to select a file from your computer</p>
                </>
              )}

              <div className="dropzone-actions">
                <button
                  type="button"
                  className="btn btn--secondary"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading}
                  id="browse-files-btn"
                >
                  {file ? 'Change File' : 'Browse Files'}
                </button>

                {file && (
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={handleUpload}
                    disabled={uploading}
                    id="submit-upload-btn"
                  >
                    {uploading ? (
                      <>
                        <span className="spinner-inline"></span> Ingesting & Persisting...
                      </>
                    ) : (
                      '🚀 Ingest & Save Version'
                    )}
                  </button>
                )}
              </div>

              {uploading && (
                <div className="upload-progress-container">
                  <div className="progress-bar-track">
                    <div className="progress-bar-fill indeterminate"></div>
                  </div>
                  <span className="progress-text">
                    Verifying integrity, calculating column statistics, and persisting version to PostgreSQL...
                  </span>
                </div>
              )}

              <div className="dropzone-guidelines">
                <div className="guideline-item">
                  <span className="guideline-dot"></span>
                  <span>Supported formats: <strong>CSV (.csv)</strong>, <strong>Excel (.xlsx)</strong></span>
                </div>
                <div className="guideline-item">
                  <span className="guideline-dot"></span>
                  <span>Maximum file size: <strong>{MAX_SIZE_MB} MB</strong></span>
                </div>
                <div className="guideline-item">
                  <span className="guideline-dot"></span>
                  <span>Automatic sequential version assignment</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Uploaded Metadata Results View */}
      {metadata && (
        <div className="dataset-results-view" id="dataset-results">
          {/* Persistence Success Banner */}
          <div className="persistence-banner" id="persistence-success-banner">
            <div className="persistence-main">
              <span className="persistence-icon">✅</span>
              <div>
                <h3 className="persistence-title">
                  Dataset Version Persisted Successfully
                </h3>
                <p className="persistence-subtitle">
                  Dataset: <strong>{metadata.dataset_name}</strong> • Assigned Version: <strong>V{metadata.version_number || 1}</strong>
                </p>
              </div>
            </div>
            <div className="persistence-ids" style={{ display: 'flex', flexDirection: 'column', gap: '8px', alignItems: 'flex-end' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <span className="id-tag">Dataset ID: <code>{metadata.dataset_id ? String(metadata.dataset_id).slice(0, 8) : 'N/A'}...</code></span>
                <span className="id-tag">Version ID: <code>{metadata.version_id ? String(metadata.version_id).slice(0, 8) : 'N/A'}...</code></span>
              </div>
              <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/profile`}
                  className="btn btn--secondary btn--sm"
                  id="view-automated-profile-btn"
                >
                  📊 View Automated Profile
                </Link>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/quality`}
                  className="btn btn--primary btn--sm"
                  id="run-quality-check-btn"
                  style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
                >
                  🛡 Run Quality Check
                </Link>
                <Link
                  to="/datasets"
                  className="btn btn--secondary btn--sm"
                >
                  📁 Repository
                </Link>
              </div>
            </div>
          </div>

          {/* Summary Overview Cards */}
          <div className="stat-cards-grid">
            <div className="stat-card">
              <span className="stat-card-icon">📊</span>
              <div className="stat-card-details">
                <span className="stat-label">Total Rows</span>
                <span className="stat-value">{metadata.row_count.toLocaleString()}</span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-card-icon">📐</span>
              <div className="stat-card-details">
                <span className="stat-label">Total Columns</span>
                <span className="stat-value">{metadata.column_count}</span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-card-icon">📦</span>
              <div className="stat-card-details">
                <span className="stat-label">File Size</span>
                <span className="stat-value">{metadata.file_size_display}</span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-card-icon">
                {metadata.duplicate_row_count > 0 ? '⚠️' : '✅'}
              </span>
              <div className="stat-card-details">
                <span className="stat-label">Duplicate Rows</span>
                <span className={`stat-value ${metadata.duplicate_row_count > 0 ? 'text-warning' : 'text-success'}`}>
                  {metadata.duplicate_row_count}
                </span>
              </div>
            </div>

            <div className="stat-card">
              <span className="stat-card-icon">⚙️</span>
              <div className="stat-card-details">
                <span className="stat-label">Format / Source</span>
                <span className="stat-value stat-value--small">
                  {metadata.file_type.toUpperCase()}
                  {metadata.encoding ? ` (${metadata.encoding})` : ''}
                  {metadata.sheet_name ? ` • ${metadata.sheet_name}` : ''}
                </span>
              </div>
            </div>
          </div>

          {/* Stored File Banner */}
          <div className="stored-file-banner">
            <div className="stored-file-info">
              <span className="badge badge--accent">{metadata.file_type.toUpperCase()}</span>
              <span className="stored-file-name"><strong>Original:</strong> {metadata.original_filename}</span>
              <span className="stored-file-sep">•</span>
              <span className="stored-file-safe"><strong>Safe Stored:</strong> {metadata.stored_filename}</span>
            </div>
            <span className="timestamp-text">
              Uploaded: {new Date(metadata.uploaded_at).toLocaleTimeString()}
            </span>
          </div>

          {/* Section Navigation Tabs */}
          <div className="results-tab-bar">
            <button
              className={`tab-btn ${activeTab === 'columns' ? 'tab-btn--active' : ''}`}
              onClick={() => setActiveTab('columns')}
              id="tab-columns-btn"
            >
              📑 Column Metadata & Statistics ({metadata.columns.length})
            </button>
            <button
              className={`tab-btn ${activeTab === 'preview' ? 'tab-btn--active' : ''}`}
              onClick={() => setActiveTab('preview')}
              id="tab-preview-btn"
            >
              👁️ Sample Data Preview ({metadata.sample_rows.length} rows)
            </button>
          </div>

          {/* Tab 1: Column Metadata Table */}
          {activeTab === 'columns' && (
            <div className="card results-table-card" id="column-metadata-section">
              <div className="table-responsive">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>#</th>
                      <th>Column Name</th>
                      <th>Data Type</th>
                      <th>Nullability</th>
                      <th>Missing Values</th>
                      <th>Unique Values</th>
                      <th>Sample Values</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metadata.columns.map((col, idx) => (
                      <tr key={col.name}>
                        <td className="text-muted">{idx + 1}</td>
                        <td>
                          <code className="column-name-code">{col.name}</code>
                        </td>
                        <td>
                          <span className={`dtype-badge ${getDtypeBadgeClass(col.dtype)}`}>
                            {col.dtype}
                          </span>
                        </td>
                        <td>
                          {col.nullable ? (
                            <span className="badge badge--warning">Nullable</span>
                          ) : (
                            <span className="badge badge--success">Non-Null</span>
                          )}
                        </td>
                        <td>
                          <div className="metric-bar-cell">
                            <div className="metric-bar-track">
                              <div
                                className={`metric-bar-fill ${col.missing_percentage > 10 ? 'fill-warning' : 'fill-primary'}`}
                                style={{ width: `${Math.min(col.missing_percentage, 100)}%` }}
                              ></div>
                            </div>
                            <span className="metric-bar-label">
                              {col.missing_count} ({col.missing_percentage}%)
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="metric-unique">
                            {col.unique_count.toLocaleString()} ({col.unique_percentage}%)
                          </span>
                        </td>
                        <td>
                          <div className="sample-chips-container">
                            {col.sample_values && col.sample_values.length > 0 ? (
                              col.sample_values.map((v, i) => (
                                <span
                                  key={i}
                                  className={`sample-chip ${v === '***MASKED***' ? 'sample-chip--masked' : ''}`}
                                  title={String(v)}
                                >
                                  {v === null ? <em>null</em> : String(v)}
                                </span>
                              ))
                            ) : (
                              <span className="text-muted">No samples</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Tab 2: Sample Data Preview Table */}
          {activeTab === 'preview' && (
            <div className="card results-table-card" id="data-preview-section">
              <div className="table-responsive">
                <table className="data-table data-table--preview">
                  <thead>
                    <tr>
                      <th style={{ width: '50px' }}>Row</th>
                      {metadata.column_names.map((colName) => (
                        <th key={colName}>
                          <div className="preview-th">
                            <span>{colName}</span>
                            <span className="preview-th-dtype">{metadata.column_dtypes[colName]}</span>
                          </div>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {metadata.sample_rows.map((row, rowIdx) => (
                      <tr key={rowIdx}>
                        <td className="text-muted font-mono">{rowIdx + 1}</td>
                        {metadata.column_names.map((colName) => {
                          const val = row[colName];
                          const isMasked = val === '***MASKED***';
                          const isNull = val === null || val === undefined;

                          return (
                            <td key={colName} className={isMasked ? 'cell-masked' : isNull ? 'cell-null' : ''}>
                              {isNull ? (
                                <span className="null-indicator">null</span>
                              ) : isMasked ? (
                                <span className="masked-indicator">***MASKED***</span>
                              ) : (
                                String(val)
                              )}
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
