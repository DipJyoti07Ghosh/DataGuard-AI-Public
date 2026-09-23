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
 *
 * Visual design: DATA GUARD AI workspace skin (.du-* classes)
 * Backend contract: UNCHANGED.
 *   - uploadDataset(file, datasetName, description)  ← same 3 args
 *   - Reads ?dataset= from the URL for deep-linking
 *   - Every field path from the metadata response is preserved.
 */

import { useState, useEffect, useRef } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { uploadDataset } from '../api/client';
import './Upload.css';

const MAX_SIZE_MB = 100;
const ALLOWED_EXTS = ['.csv', '.xlsx'];

/**
 * Human-readable file size that handles sub-KB values gracefully.
 */
function formatFileSize(bytes) {
  if (!Number.isFinite(bytes) || bytes < 0) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

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
  const [pendingFile, setPendingFile] = useState(null);   // for replace confirm
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

    // If a file is already loaded, ask for confirmation before replacing it
    if (file) {
      setPendingFile(selectedFile);
      return;
    }

    setFile(selectedFile);

    // If datasetName is empty, auto-populate from file stem
    if (!datasetName) {
      const stem = selectedFile.name
        .replace(/\.[^/.]+$/, '')
        .replace(/[_\-\.]+/g, ' ');
      setDatasetName(stem);
    }
  };

  const confirmReplace = () => {
    if (!pendingFile) return;
    const next = pendingFile;
    setPendingFile(null);
    setFile(next);
    if (!datasetName) {
      const stem = next.name.replace(/\.[^/.]+$/, '').replace(/[_\-\.]+/g, ' ');
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
      // SAME API call, SAME 3 args, SAME order.
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

  // Compute the ingest-status badge.
  const ingestBadge = error
    ? { className: 'badge badge--warning', label: 'Upload Failed — Retry' }
    : { className: 'badge badge--success', label: 'Ready to Ingest' };

  return (
    <div className="du-page">
      {/* ================= HERO ================= */}
      <header className="du-hero">
        <div>
          <nav>
            DATA GUARD AI <i>›</i> Ingestion
          </nav>
          <div className="du-title">
            <h1>DATA GUARD AI - Data Ingestion Workspace</h1>
            <span>Development</span>
          </div>
          <h2>Dataset Upload &amp; Ingestion</h2>
          <p>
            Securely add CSV or Excel files. Schema discovery, validation, and
            version storage use the existing connected backend.
          </p>
        </div>

        {metadata && (
          <div className="du-hero-actions">
            {metadata.dataset_id && metadata.version_id && (
              <>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/profile`}
                  className="btn btn--secondary btn--sm"
                >
                  📊 Profile
                </Link>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/quality`}
                  className="btn btn--secondary btn--sm"
                >
                  🛡 Quality
                </Link>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/pii`}
                  className="btn btn--secondary btn--sm"
                >
                  🔐 PII
                </Link>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/risk`}
                  className="btn btn--secondary btn--sm"
                >
                  🤖 Risk
                </Link>
                <Link
                  to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/anomalies`}
                  className="btn btn--secondary btn--sm"
                >
                  ⚠ Anomalies
                </Link>
              </>
            )}
            <Link to="/datasets" className="btn btn--secondary btn--sm">
              🗃️ Repository
            </Link>
            <button
              type="button"
              className="btn btn--secondary btn--sm"
              onClick={handleReset}
            >
              ➕ New Version
            </button>
          </div>
        )}

        {!metadata && (
          <div className="du-orbit" aria-hidden="true">
            <b>↑</b>
            <i>CSV<br />XLSX</i>
            <em>DATA</em>
          </div>
        )}
      </header>

      {/* ================= ERROR ================= */}
      {error && (
        <div className="du-error" role="alert">
          <strong>Upload needs attention</strong>
          <span>{error}</span>
          <button type="button" onClick={() => setError(null)}>Dismiss</button>
        </div>
      )}

      {/* ================= STAGE 1: DROPZONE ================= */}
      {!metadata && (
        <>
          {/* Logical dataset metadata inputs */}
          <section className="du-config">
            <label>
              Dataset label
              <input
                type="text"
                value={datasetName}
                onChange={(e) => setDatasetName(e.target.value)}
                placeholder="e.g. Customer Data, Sales Transactions…"
              />
            </label>
            <label>
              Description
              <input
                type="text"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Optional description"
              />
            </label>
            <span className="du-hint">
              Files uploaded with the same dataset name are grouped as sequential
              versions (V1, V2, V3…).
            </span>
          </section>

          <section
            className={`du-drop ${isDragging ? 'drag' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
          >
            <strong>⇧</strong>
            <h3>Drop a dataset to begin</h3>
            <p>Drag and drop a CSV or Excel file, or choose one from your device.</p>

            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
            >
              {file ? 'Change file' : 'Choose file'}
            </button>

            <small>CSV · XLSX · Maximum {MAX_SIZE_MB} MB</small>

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
            />
          </section>

          {file && (
            <section className="du-file">
              <b>▤</b>
              <span>
                <strong>{file.name}</strong>
                <small>
                  {formatFileSize(file.size)} · {datasetName || 'Auto label'}
                </small>
              </span>
              <span className={ingestBadge.className}>{ingestBadge.label}</span>
              <button
                type="button"
                onClick={() => {
                  setFile(null);
                  if (fileInputRef.current) fileInputRef.current.value = '';
                }}
              >
                Remove
              </button>
              <button
                type="button"
                className="du-primary"
                onClick={handleUpload}
                disabled={uploading}
              >
                {uploading ? (
                  <>
                    <span className="spinner-inline" /> Ingesting…
                  </>
                ) : (
                  'Ingest and save version →'
                )}
              </button>
            </section>
          )}

          {uploading && (
            <div className="du-pipeline">
              <b>✓ Verifying integrity</b>
              <i />
              <b>● Computing column statistics</b>
              <i />
              <b>Persisting to PostgreSQL</b>
            </div>
          )}

          {/* Guidelines */}
          <section className="du-guidelines">
            <div>
              <span className="guideline-dot" />
              Supported formats: <strong>CSV (.csv)</strong>, <strong>Excel (.xlsx)</strong>
            </div>
            <div>
              <span className="guideline-dot" />
              Maximum file size: <strong>{MAX_SIZE_MB} MB</strong>
            </div>
            <div>
              <span className="guideline-dot" />
              Automatic sequential version assignment
            </div>
          </section>
        </>
      )}

      {/* ================= REPLACE CONFIRM MODAL ================= */}
      {pendingFile && (
        <div className="du-modal-backdrop" onClick={() => setPendingFile(null)}>
          <section
            className="du-modal"
            role="dialog"
            aria-modal="true"
            onClick={(e) => e.stopPropagation()}
          >
            <h2>Replace selected dataset?</h2>
            <p>
              You already have <strong>{file?.name}</strong> selected. Replacing it will
              switch to <strong>{pendingFile.name}</strong> before ingestion.
            </p>
            <div>
              <button type="button" onClick={() => setPendingFile(null)}>Cancel</button>
              <button type="button" className="confirm" onClick={confirmReplace}>
                Replace file
              </button>
            </div>
          </section>
        </div>
      )}

      {/* ================= STAGE 2: METADATA ================= */}
      {metadata && (
        <>
          {/* File summary card */}
          <section className="du-filecard">
            <b>▤</b>
            <span>
              <small>FILE</small>
              <strong>{metadata.original_filename}</strong>
              <em>
                {metadata.file_size_display || formatFileSize(metadata.file_size_bytes)} ·
                uploaded successfully
              </em>
            </span>
            <div>
              <label>FORMAT<b>{metadata.file_type?.toUpperCase()}</b></label>
              <label>ROWS<b>{metadata.row_count?.toLocaleString()}</b></label>
              <label>COLUMNS<b>{metadata.column_count}</b></label>
              <label>STATUS<b>● Persisted</b></label>
            </div>
          </section>

          {/* Pipeline strip */}
          <section className="du-pipeline">
            <b>✓ Uploaded</b>
            <i />
            <b>✓ Parsed</b>
            <i />
            <b>✓ Validated</b>
            <i />
            <b>✓ Persisted</b>
          </section>

          {/* Success banner */}
          <section className="du-success">
            <span>
              <b>✓</b>
              <strong>
                Dataset version persisted successfully
                <small>
                  Version V{metadata.version_number || 1} is ready for analysis.
                </small>
              </strong>
            </span>
            <div>
              <Link to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/profile`}>
                Profile
              </Link>
              <Link to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/quality`}>
                Quality
              </Link>
              <Link to={`/datasets/${metadata.dataset_id}/versions/${metadata.version_id}/anomalies`}>
                Anomalies
              </Link>
              <Link to="/datasets">Repository</Link>
            </div>
          </section>

          {/* Metrics grid */}
          <section className="du-metrics">
            <Metric label="TOTAL ROWS" value={metadata.row_count?.toLocaleString()} />
            <Metric label="COLUMNS" value={metadata.column_count} />
            <Metric
              label="FILE SIZE"
              value={metadata.file_size_display || formatFileSize(metadata.file_size_bytes)}
            />
            <Metric
              label="DUPLICATE ROWS"
              value={metadata.duplicate_row_count ?? 0}
            />
            <Metric label="SOURCE" value={metadata.file_type?.toUpperCase()} />
          </section>

          {/* Stored file banner */}
          <section className="du-meta">
            FORMAT <b>{metadata.file_type?.toUpperCase()}</b>
            {metadata.encoding ? <> · ENCODING <b>{metadata.encoding}</b></> : null}
            {metadata.sheet_name ? <> · SHEET <b>{metadata.sheet_name}</b></> : null}
            <i />
            ORIGINAL <b>{metadata.original_filename}</b>
            <i />
            SAFE STORAGE <b>{metadata.stored_filename || 'Managed storage'}</b>
          </section>

          {/* Schema explorer */}
          <section className="du-schema">
            <header>
              <span>
                <h2>Dataset Schema</h2>
                <small>{metadata.columns.length} columns detected</small>
              </span>
              <div>
                <button
                  type="button"
                  className={activeTab === 'columns' ? 'active' : ''}
                  onClick={() => setActiveTab('columns')}
                >
                  Column Metadata
                </button>
                <button
                  type="button"
                  className={activeTab === 'preview' ? 'active' : ''}
                  onClick={() => setActiveTab('preview')}
                >
                  Sample Preview ({metadata.sample_rows.length})
                </button>
              </div>
            </header>

            {activeTab === 'columns' && (
              <div className="du-table">
                <table>
                  <thead>
                    <tr>
                      <th style={{ width: '40px' }}>#</th>
                      <th>COLUMN NAME</th>
                      <th>DATA TYPE</th>
                      <th>NULLABILITY</th>
                      <th>MISSING</th>
                      <th>UNIQUE</th>
                      <th>SAMPLE VALUES</th>
                    </tr>
                  </thead>
                  <tbody>
                    {metadata.columns.map((col, idx) => (
                      <tr key={col.name}>
                        <td>{idx + 1}</td>
                        <td>
                          <b className="column-name-code">{col.name}</b>
                        </td>
                        <td>
                          <span className={`dtype-badge ${getDtypeBadgeClass(col.dtype)}`}>
                            {col.dtype}
                          </span>
                        </td>
                        <td>
                          {col.nullable ? (
                            <em className="badge badge--warning">NULLABLE</em>
                          ) : (
                            <em className="badge badge--success">NON-NULL</em>
                          )}
                        </td>
                        <td>
                          <span className={col.missing_percentage > 10 ? 'text-warning' : ''}>
                            {col.missing_count} ({col.missing_percentage}%)
                          </span>
                        </td>
                        <td>
                          {col.unique_count.toLocaleString()} ({col.unique_percentage}%)
                        </td>
                        <td>
                          <div className="sample-chips-container">
                            {col.sample_values?.length > 0 ? (
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
                              <span className="dash-muted">No samples</span>
                            )}
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {activeTab === 'preview' && (
              <pre className="du-preview">
                {JSON.stringify(metadata.sample_rows || [], null, 2)}
              </pre>
            )}
          </section>
        </>
      )}
    </div>
  );
}

/* --------- Small helper component --------- */
function Metric({ label, value }) {
  return (
    <article>
      <i>◈</i>
      <small>{label}</small>
      <strong>{value ?? '—'}</strong>
      <em>Dataset insight</em>
    </article>
  );
}