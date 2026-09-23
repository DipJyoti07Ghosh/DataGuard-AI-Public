/**
 * DataGuard AI — Anomaly & Outlier Detection Dashboard (Phase 8)
 *
 * Multi-method statistical (IQR, Z-Score), ML (Isolation Forest),
 * and categorical frequency anomaly findings.
 *
 * Visual design: DATA GUARD AI workspace skin (.an-* classes).
 * Backend contract: UNCHANGED.
 *   - getAnomalies() / detectAnomalies()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnomalies, detectAnomalies } from '../api/client';
import './Anomalies.css';

export default function Anomalies() {
  const { datasetId, versionId } = useParams();

  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Filters & state
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedMethod, setSelectedMethod] = useState('ALL');
  const [searchCol, setSearchCol] = useState('');
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  useEffect(() => {
    fetchAnomalies(false);
  }, [datasetId, versionId]);

  async function fetchAnomalies(force = false) {
    if (force) setRecomputing(true);
    else setLoading(true);
    setError(null);

    try {
      let res;
      if (force) {
        res = await detectAnomalies(datasetId, versionId, true);
      } else {
        res = await getAnomalies(datasetId, versionId);
      }
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load anomaly detection results');
    } finally {
      setLoading(false);
      setRecomputing(false);
    }
  }

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  function getSeverityBadge(sev) {
    const s = (sev || 'LOW').toUpperCase();
    if (s === 'CRITICAL') return { color: '#f43f5e', icon: '🚨' };
    if (s === 'HIGH')     return { color: '#fb923c', icon: '🔴' };
    if (s === 'MEDIUM')   return { color: '#fbbf24', icon: '🟡' };
    return                       { color: '#34d399', icon: '🟢' };
  }

  function getScoreColor(score) {
    if (score >= 75) return '#f43f5e';
    if (score >= 50) return '#fb923c';
    if (score >= 25) return '#fbbf24';
    return '#34d399';
  }

  // Filtered findings
  const findings = data?.findings || [];
  const filteredFindings = findings.filter((f) => {
    if (selectedSeverity !== 'ALL' && f.severity?.toUpperCase() !== selectedSeverity) {
      return false;
    }
    if (selectedMethod !== 'ALL') {
      const activeMethods = f.evidence?.detected_methods || [];
      if (selectedMethod === 'MULTI_METHOD_CONSENSUS') {
        if (f.detection_method !== 'MULTI_METHOD_CONSENSUS') return false;
      } else if (
        !activeMethods.includes(selectedMethod) &&
        f.detection_method !== selectedMethod
      ) {
        return false;
      }
    }
    if (searchCol.trim()) {
      if (!f.column_name.toLowerCase().includes(searchCol.toLowerCase())) {
        return false;
      }
    }
    return true;
  });

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="an-page">
        <div className="an-loading">
          <span className="an-spinner" aria-hidden="true" />
          <p>Running Anomaly Detection Engine…</p>
          <small>
            Evaluating IQR, Z-Score, Isolation Forest, and rare categorical distributions.
          </small>
        </div>
      </div>
    );
  }

  // ---------- Error ----------
  if (error) {
    return (
      <div className="an-page">
        <div className="an-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Anomaly Detection Failed</strong>
            <p>{error}</p>
          </div>
        </div>
        <div className="an-error-actions">
          <button
            className="an-btn an-btn--primary"
            onClick={() => fetchAnomalies(true)}
            disabled={recomputing}
          >
            Retry Anomaly Detection
          </button>
          <Link to="/datasets" className="an-btn an-btn--ghost">
            Back to Datasets
          </Link>
        </div>
      </div>
    );
  }

  const scoreBadge = getSeverityBadge(data?.overall_severity);
  const totalRowsAnalyzed =
    data?.total_rows ||
    data?.total_rows_analyzed ||
    (findings.length > 0 ? findings[0].explanation?.phase7_context?.total_rows : null) ||
    0;

  return (
    <div className="an-page">
      {/* ================= HERO ================= */}
      <header className="an-hero">
        <div className="an-hero-info">
          <div className="an-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{data?.dataset_name || 'Dataset'}</span>
            <span className="an-version-pill">V{data?.version_number}</span>
            <span className="an-engine-pill">● Multi-Method Engine Active</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Anomaly &amp; Outlier Detection</h1>
          <p>Identify statistically unusual patterns and multi-method outliers across your dataset.</p>
        </div>

        <div className="an-hero-actions">
          <button
            className="an-btn an-btn--ghost"
            onClick={() => fetchAnomalies(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <span className="an-spinner an-spinner--sm" /> Re-analyzing…
              </>
            ) : (
              '🔄 Re-run Detection'
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/profile`}
            className="an-btn an-btn--ghost"
          >
            📊 Profile
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="an-btn an-btn--ghost"
          >
            🛡 Quality
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="an-btn an-btn--ghost"
          >
            🔐 PII
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/risk`}
            className="an-btn an-btn--ghost"
          >
            🤖 Risk
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="an-btn an-btn--primary"
          >
            🎯 Prioritization
          </Link>
        </div>
      </header>

      {/* ================= KPI GRID ================= */}
      <section className="an-kpi-grid">
        <div className="an-kpi an-kpi--accent">
          <small>Anomalies Detected</small>
          <strong>{data?.total_anomalies || 0}</strong>
          <em>Across all analyzed columns</em>
        </div>
        <div className="an-kpi an-kpi--warning">
          <small>Columns Affected</small>
          <strong>
            {data?.columns_with_anomalies || 0}
            <span className="an-kpi-suffix"> / {data?.total_columns_analyzed || 0}</span>
          </strong>
          <em>Columns with outlier observations</em>
        </div>
        <div className="an-kpi an-kpi--info">
          <small>Rows Analyzed</small>
          <strong>{totalRowsAnalyzed ? totalRowsAnalyzed.toLocaleString() : '100%'}</strong>
          <em>Dataset population evaluated</em>
        </div>
        <div className="an-kpi" style={{ borderLeftColor: scoreBadge.color }}>
          <small>Anomaly Score</small>
          <strong style={{ color: getScoreColor(data?.dataset_anomaly_score) }}>
            {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
            <span className="an-kpi-suffix"> / 100</span>
          </strong>
          <em>Composite anomaly index</em>
        </div>
      </section>

      {/* ================= SCORE + SEVERITY DISTRIBUTION ================= */}
      <section className="an-overview">
        {/* Left: composite score */}
        <div className="an-score-card" style={{ borderLeftColor: scoreBadge.color }}>
          <div className="an-score-head">
            <span className="an-score-label">Composite Anomaly Index</span>
            <span
              className="an-score-pill"
              style={{
                color: scoreBadge.color,
                borderColor: scoreBadge.color,
                background: `${scoreBadge.color}22`,
              }}
            >
              ● {data?.overall_severity}
            </span>
          </div>

          <div className="an-score-value" style={{ color: getScoreColor(data?.dataset_anomaly_score) }}>
            {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
            <small>/ 100</small>
          </div>

          <p className="an-score-note">
            Consensus score weighted across multi-detector agreement (IQR, Z-Score,
            Isolation Forest), statistical excursion rates, and sensitive column context.
          </p>

          <div className="an-score-foot">
            <span>Last Analyzed:</span>
            <code>
              {data?.analyzed_at ? new Date(data.analyzed_at).toLocaleString() : 'Just now'}
            </code>
          </div>
        </div>

        {/* Right: severity distribution */}
        <div className="an-sev-panel">
          <h3>Severity Distribution &amp; Detector Consensus</h3>

          <div className="an-sev-grid">
            <SeverityCard label="CRITICAL" count={data?.critical_count || 0} total={data?.total_anomalies || 0} tone="danger" />
            <SeverityCard label="HIGH"     count={data?.high_count || 0}     total={data?.total_anomalies || 0} tone="orange" />
            <SeverityCard label="MEDIUM"   count={data?.medium_count || 0}   total={data?.total_anomalies || 0} tone="warning" />
            <SeverityCard label="LOW"      count={data?.low_count || 0}      total={data?.total_anomalies || 0} tone="success" />
          </div>

          <div className="an-consensus-note">
            <strong>💡 Multi-Method Consensus:</strong> High-confidence anomalies
            trigger multiple independent detectors (IQR + Z-Score + ML Isolation Forest).
            Single-detector anomalies indicate potential tail events or skewed distributions.
          </div>
        </div>
      </section>

      {/* ================= FILTERS ================= */}
      <section className="an-filter-bar">
        <div className="an-filter-row">
          <span className="an-filter-label">Method:</span>
          <div className="an-filter-chips">
            {[
              { id: 'ALL', label: 'All Methods' },
              { id: 'MULTI_METHOD_CONSENSUS', label: 'Consensus (2+)' },
              { id: 'IQR', label: 'IQR Outliers' },
              { id: 'Z_SCORE', label: 'Z-Score (|z|≥3)' },
              { id: 'ISOLATION_FOREST', label: 'Isolation Forest (ML)' },
              { id: 'CATEGORICAL_FREQUENCY', label: 'Rare Categories' },
            ].map((m) => {
              const active = selectedMethod === m.id;
              return (
                <button
                  key={m.id}
                  type="button"
                  className={`an-chip ${active ? 'an-chip--active' : ''}`}
                  onClick={() => setSelectedMethod(m.id)}
                >
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>

        <div className="an-filter-row">
          <span className="an-filter-label">Severity:</span>
          <div className="an-sev-filters">
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
              <button
                key={s}
                type="button"
                className={`an-sev-btn ${selectedSeverity === s ? 'an-sev-btn--active' : ''}`}
                onClick={() => setSelectedSeverity(s)}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        <input
          type="text"
          className="an-input"
          placeholder="Search column names…"
          value={searchCol}
          onChange={(e) => setSearchCol(e.target.value)}
        />
      </section>

      {/* ================= FINDINGS TABLE ================= */}
      <section className="an-panel">
        <div className="an-panel-head">
          <h3>Anomaly Findings</h3>
          <span className="an-panel-count">
            {filteredFindings.length} of {findings.length} columns
          </span>
        </div>

        {filteredFindings.length === 0 ? (
          <div className="an-empty">
            <span className="an-empty-icon">✨</span>
            <h4>No anomaly findings match the selected filter criteria</h4>
            <p>Try adjusting the method or severity filters, or clear the search.</p>
          </div>
        ) : (
          <div className="an-table-wrap">
            <table className="an-table">
              <thead>
                <tr>
                  <th>Column &amp; ML Context</th>
                  <th>Detection Methods</th>
                  <th>Anomalies</th>
                  <th>Severity</th>
                  <th>Score</th>
                  <th style={{ textAlign: 'right' }}>Inspect</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((f) => {
                  const sBadge = getSeverityBadge(f.severity);
                  const activeMethods = f.evidence?.detected_methods || [];
                  const p7 = f.explanation?.phase7_context;

                  return (
                    <tr key={f.id} onClick={() => setSelectedFinding(f)}>
                      <td>
                        <code className="an-col-code">{f.column_name}</code>
                        <div className="an-context-row">
                          {p7?.predicted_domain && (
                            <span className="an-context-tag">{p7.predicted_domain}</span>
                          )}
                          {p7?.risk_level && (
                            <span className="an-context-tag an-context-tag--mono">
                              Risk: {p7.risk_level}
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="an-method-row">
                          {activeMethods.length === 0 ? (
                            <span className="an-muted">None (Clean)</span>
                          ) : (
                            activeMethods.map((m) => (
                              <span key={m} className="an-method-tag">{m}</span>
                            ))
                          )}
                          {f.detection_method === 'MULTI_METHOD_CONSENSUS' && (
                            <span className="an-method-tag an-method-tag--consensus">
                              ★ Consensus
                            </span>
                          )}
                        </div>
                      </td>
                      <td>
                        <div className="an-rate">
                          <span className="an-rate-value">
                            {f.anomaly_count}{' '}
                            <span className="an-muted">({f.anomaly_rate}%)</span>
                          </span>
                          <div className="an-rate-track">
                            <div
                              className="an-rate-fill"
                              style={{
                                width: `${Math.min(100, f.anomaly_rate * 5)}%`,
                                background: getScoreColor(f.score),
                              }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        <span
                          className="an-sev-pill"
                          style={{
                            color: sBadge.color,
                            borderColor: sBadge.color,
                            background: `${sBadge.color}22`,
                          }}
                        >
                          ● {f.severity}
                        </span>
                      </td>
                      <td>
                        <span
                          className="an-score-cell"
                          style={{ color: getScoreColor(f.score) }}
                        >
                          {f.score.toFixed(1)}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="an-btn an-btn--ghost an-btn--xs"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFinding(f);
                          }}
                        >
                          Inspect →
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ================= DETAIL DRAWER ================= */}
      {selectedFinding && (
        <div className="an-drawer-backdrop" onClick={() => setSelectedFinding(null)}>
          <aside className="an-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="an-drawer-head">
              <div>
                <div className="an-drawer-tags">
                  <span
                    className="an-sev-pill"
                    style={(() => {
                      const sb = getSeverityBadge(selectedFinding.severity);
                      return { color: sb.color, borderColor: sb.color, background: `${sb.color}22` };
                    })()}
                  >
                    {selectedFinding.severity} Severity
                  </span>
                  <span
                    className="an-score-pill"
                    style={{
                      color: getScoreColor(selectedFinding.score),
                      borderColor: getScoreColor(selectedFinding.score),
                      background: `${getScoreColor(selectedFinding.score)}22`,
                    }}
                  >
                    Score: {selectedFinding.score.toFixed(1)} / 100
                  </span>
                </div>
                <h2>
                  <code>{selectedFinding.column_name}</code>
                </h2>
                <p className="an-muted">
                  Detection Method: <strong>{selectedFinding.detection_method}</strong>
                </p>
              </div>
              <button
                type="button"
                className="an-btn an-btn--ghost"
                onClick={() => setSelectedFinding(null)}
              >
                ✕
              </button>
            </div>

            {/* Summary */}
            <div className="an-drawer-section">
              <h4 className="an-drawer-label">Finding Summary</h4>
              <p className="an-drawer-body">
                {selectedFinding.explanation?.summary || 'No summary available.'}
              </p>
              <div className="an-drawer-meta">
                <span>
                  Anomalies: <strong>{selectedFinding.anomaly_count}</strong> rows
                </span>
                <span>
                  Rate: <strong>{selectedFinding.anomaly_rate}%</strong>
                </span>
              </div>
            </div>

            {/* Drivers */}
            <div className="an-drawer-section">
              <h4 className="an-drawer-label an-drawer-label--amber">
                Identified Outlier Drivers
              </h4>
              <div className="an-driver-list">
                {selectedFinding.explanation?.drivers?.length > 0 ? (
                  selectedFinding.explanation.drivers.map((d, i) => (
                    <div key={i} className="an-driver">
                      <span>•</span>
                      <span>{d}</span>
                    </div>
                  ))
                ) : (
                  <p className="an-muted">No specific driver conditions flagged.</p>
                )}
              </div>
            </div>

            {/* Detector evidence */}
            <div className="an-drawer-section">
              <h4 className="an-drawer-label an-drawer-label--cyan">
                Detector Results &amp; Evidence Breakdown
              </h4>
              <div className="an-detector-grid">
                <Detector
                  name="IQR Detector"
                  detected={selectedFinding.evidence?.iqr?.detected}
                  executed={selectedFinding.evidence?.iqr?.executed}
                  reason={selectedFinding.evidence?.iqr?.reason}
                  rows={
                    selectedFinding.evidence?.iqr?.executed
                      ? [
                          `Bounds: [${selectedFinding.evidence.iqr.lower_bound}, ${selectedFinding.evidence.iqr.upper_bound}]`,
                          `Q1: ${selectedFinding.evidence.iqr.q1} | Q3: ${selectedFinding.evidence.iqr.q3}`,
                          `Outliers: ${selectedFinding.evidence.iqr.anomaly_count} (${selectedFinding.evidence.iqr.anomaly_rate}%)`,
                        ]
                      : null
                  }
                />
                <Detector
                  name="Z-Score (|z|≥3)"
                  detected={selectedFinding.evidence?.zscore?.detected}
                  executed={selectedFinding.evidence?.zscore?.executed}
                  reason={selectedFinding.evidence?.zscore?.reason}
                  rows={
                    selectedFinding.evidence?.zscore?.executed
                      ? [
                          `Mean: ${selectedFinding.evidence.zscore.mean} | Std: ${selectedFinding.evidence.zscore.std}`,
                          `Max |z|: ${selectedFinding.evidence.zscore.max_abs_zscore}`,
                          `Outliers: ${selectedFinding.evidence.zscore.anomaly_count} (${selectedFinding.evidence.zscore.anomaly_rate}%)`,
                        ]
                      : null
                  }
                />
                <Detector
                  name="Isolation Forest (ML)"
                  detected={selectedFinding.evidence?.isolation_forest?.detected}
                  executed={selectedFinding.evidence?.isolation_forest?.executed}
                  reason={selectedFinding.evidence?.isolation_forest?.reason}
                  rows={
                    selectedFinding.evidence?.isolation_forest?.executed
                      ? [
                          `Strategy: ${selectedFinding.evidence.isolation_forest.sampling_strategy}`,
                          `Outliers: ${selectedFinding.evidence.isolation_forest.anomaly_count} (${selectedFinding.evidence.isolation_forest.anomaly_rate}%)`,
                          `Min Score: ${selectedFinding.evidence.isolation_forest.min_decision_score}`,
                        ]
                      : null
                  }
                />
                <Detector
                  name="Rare Categories (<1%)"
                  detected={selectedFinding.evidence?.categorical_frequency?.detected}
                  executed={selectedFinding.evidence?.categorical_frequency?.executed}
                  reason={selectedFinding.evidence?.categorical_frequency?.reason}
                  rows={
                    selectedFinding.evidence?.categorical_frequency?.executed
                      ? [
                          `Unique: ${selectedFinding.evidence.categorical_frequency.unique_categories_count}`,
                          `Rare Count: ${selectedFinding.evidence.categorical_frequency.rare_category_count}`,
                          `Rare Rate: ${selectedFinding.evidence.categorical_frequency.rare_category_rate}%`,
                        ]
                      : null
                  }
                />
              </div>
            </div>

            {/* Interpretation */}
            <div className="an-drawer-section an-drawer-interpret">
              <h4>🛡️ Statistical Interpretation &amp; Privacy Guard</h4>
              <ul>
                <li>
                  <strong>Interpretation Notice:</strong> An anomaly indicates a
                  statistically unusual pattern; it does not automatically mean the
                  data is incorrect.
                </li>
                <li>
                  <strong>Privacy Guarantee:</strong> Zero raw PII values are stored
                  in anomaly records. Only safe statistical distribution metrics are
                  preserved.
                </li>
              </ul>
            </div>

            {/* Raw evidence JSON */}
            {selectedFinding.evidence && (
              <div className="an-drawer-section">
                <div className="an-drawer-label-row">
                  <h4 className="an-drawer-label">Detector Evidence Payload</h4>
                  <button
                    type="button"
                    className="an-btn an-btn--ghost an-btn--xs"
                    onClick={() =>
                      copyToClipboard(
                        JSON.stringify(selectedFinding.evidence, null, 2),
                        'evidence',
                      )
                    }
                  >
                    {copiedKey === 'evidence' ? '✓ Copied' : 'Copy JSON'}
                  </button>
                </div>
                <pre className="an-code-block">
                  {JSON.stringify(selectedFinding.evidence, null, 2)}
                </pre>
              </div>
            )}

            {/* Footer */}
            <div className="an-drawer-foot">
              <span className="an-muted">DATA GUARD AI Anomaly Engine</span>
              <button
                type="button"
                className="an-btn an-btn--primary"
                onClick={() => setSelectedFinding(null)}
              >
                Close Drawer
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

/* ---------- Helpers ---------- */
function SeverityCard({ label, count, total, tone }) {
  const pct = total > 0 ? (count / total) * 100 : 0;
  return (
    <div className={`an-sev-card an-sev-card--${tone}`}>
      <div className="an-sev-card-head">
        <span>{label}</span>
        <span className="an-sev-card-count">{count}</span>
      </div>
      <div className="an-sev-card-track">
        <div className="an-sev-card-fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function Detector({ name, detected, executed, reason, rows }) {
  return (
    <div className="an-detector">
      <div className="an-detector-head">
        <span className="an-detector-name">{name}</span>
        <span
          className={`an-detector-status ${
            detected ? 'an-detector-status--detected' : 'an-detector-status--clean'
          }`}
        >
          {detected ? 'DETECTED' : 'CLEAN'}
        </span>
      </div>
      {executed && rows ? (
        <div className="an-detector-body">
          {rows.map((r, i) => (
            <div key={i}>{r}</div>
          ))}
        </div>
      ) : (
        <div className="an-detector-skip">{reason || 'Not executed'}</div>
      )}
    </div>
  );
}