/**
 * DataGuard AI — Dataset Version Comparison & Drift Detection (Phase 10)
 *
 * Deterministic, explainable comparison between two snapshot versions
 * of the same dataset. Evaluates schema evolution, missingness shifts,
 * uniqueness shifts, real KS/PSI distribution drift, and cross-subsystem
 * deltas (Phases 5–9).
 *
 * Visual design: DATA GUARD AI workspace skin (.cm-* classes).
 * Backend contract: UNCHANGED.
 *   - getDataset() / getDatasetComparisons() / compareDatasetVersions() / getColumnDriftDetail()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  getDataset,
  getDatasetComparisons,
  compareDatasetVersions,
  getColumnDriftDetail,
} from '../api/client';
import './Compare.css';

export default function Compare() {
  const { datasetId, versionId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const queryBaseline = searchParams.get('baseline');
  const queryCurrent = searchParams.get('current');

  const [dataset, setDataset] = useState(null);
  const [versions, setVersions] = useState([]);
  const [baselineVersionId, setBaselineVersionId] = useState(queryBaseline || '');
  const [currentVersionId, setCurrentVersionId] = useState(queryCurrent || versionId || '');
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [driftFilter, setDriftFilter] = useState('ALL');

  const [selectedColumn, setSelectedColumn] = useState(null);
  const [columnDetail, setColumnDetail] = useState(null);
  const [loadingColDetail, setLoadingColDetail] = useState(false);

  useEffect(() => {
    loadDatasetAndVersions();
  }, [datasetId]);

  async function loadDatasetAndVersions() {
    try {
      setLoading(true);
      setError(null);

      const dData = await getDataset(datasetId);
      setDataset(dData);

      const vList = (dData.versions || []).sort(
        (a, b) => a.version_number - b.version_number,
      );
      setVersions(vList);

      if (vList.length >= 2) {
        const baseId =
          queryBaseline ||
          (vList.length >= 2 ? vList[vList.length - 2].id : vList[0].id);
        const currId = queryCurrent || versionId || vList[vList.length - 1].id;
        setBaselineVersionId(baseId);
        setCurrentVersionId(currId);
        await runComparison(baseId, currId, false);
      } else if (vList.length === 1) {
        setError(
          'Dataset only has 1 version. Upload at least 2 snapshot versions to compare drift.',
        );
      } else {
        setError('No snapshot versions found for this dataset.');
      }
    } catch (err) {
      setError(err.message || 'Failed to load dataset metadata for comparison.');
    } finally {
      setLoading(false);
    }
  }

  async function runComparison(baseId, currId, force = false) {
    if (!baseId || !currId) return;
    if (baseId === currId) {
      setError('Baseline version and Current version must be different.');
      return;
    }

    try {
      setComparing(true);
      setError(null);
      const res = await compareDatasetVersions(datasetId, baseId, currId, force);
      setComparison(res);
      if (selectedColumn) {
        loadColumnDetail(res.id, selectedColumn.column_name);
      }
    } catch (err) {
      setError(err.message || 'Comparison calculation failed.');
    } finally {
      setComparing(false);
    }
  }

  async function handleInspectColumn(col) {
    setSelectedColumn(col);
    if (comparison?.id) {
      await loadColumnDetail(comparison.id, col.column_name);
    }
  }

  async function loadColumnDetail(compId, colName) {
    try {
      setLoadingColDetail(true);
      const detail = await getColumnDriftDetail(datasetId, compId, colName);
      setColumnDetail(detail);
    } catch (err) {
      console.error('Failed to load column detail:', err);
    } finally {
      setLoadingColDetail(false);
    }
  }

  function getDriftBadgeClass(status) {
    switch (status) {
      case 'HIGH_DRIFT': return { color: '#f43f5e', label: 'HIGH DRIFT' };
      case 'MEDIUM_DRIFT': return { color: '#fb923c', label: 'MEDIUM DRIFT' };
      case 'LOW_DRIFT': return { color: '#60a5fa', label: 'LOW DRIFT' };
      case 'NO_DRIFT':
      case 'NO_DRIFT (IMPROVED)': return { color: '#34d399', label: 'NO DRIFT' };
      default: return { color: '#94a3b8', label: status || 'UNKNOWN' };
    }
  }

  function getSchemaBadgeClass(status) {
    switch (status) {
      case 'ADDED': return { color: '#22d3ee' };
      case 'REMOVED': return { color: '#f43f5e' };
      case 'TYPE_CHANGED': return { color: '#fbbf24' };
      case 'UNCHANGED':
      default: return { color: '#94a3b8' };
    }
  }

  function getOverallTone(status) {
    switch (status) {
      case 'HIGH_DRIFT': return { color: '#f43f5e', label: 'HIGH DRIFT' };
      case 'MEDIUM_DRIFT': return { color: '#fb923c', label: 'MEDIUM DRIFT' };
      case 'LOW_DRIFT': return { color: '#60a5fa', label: 'LOW DRIFT' };
      default: return { color: '#34d399', label: 'NO DRIFT' };
    }
  }

  const filteredColumns = (comparison?.columns || []).filter((col) => {
    if (searchQuery && !col.column_name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    if (categoryFilter !== 'ALL' && col.type_category !== categoryFilter) {
      return false;
    }
    if (driftFilter === 'DRIFTED') {
      return ['HIGH_DRIFT', 'MEDIUM_DRIFT', 'LOW_DRIFT'].includes(col.drift_status);
    }
    if (driftFilter === 'SCHEMA_CHANGED') return col.schema_status !== 'UNCHANGED';
    if (driftFilter === 'HIGH_DRIFT') return col.drift_status === 'HIGH_DRIFT';
    if (driftFilter === 'MEDIUM_DRIFT') return col.drift_status === 'MEDIUM_DRIFT';
    if (driftFilter === 'NO_DRIFT') return col.drift_status === 'NO_DRIFT';
    return true;
  });

  return (
    <div className="cm-page">
      {/* ================= HERO ================= */}
      <header className="cm-hero">
        <div className="cm-hero-info">
          <div className="cm-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{dataset?.name || 'Dataset'}</span>
            <span>›</span>
            <span className="cm-crumb-accent">Version Comparison &amp; Drift</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Version Comparison &amp; Drift Analysis</h1>
          <p>Explainable comparison of schema evolution, distribution drift, and cross-phase metrics.</p>
        </div>
      </header>

      {/* ================= VERSION SELECTOR ================= */}
      <section className="cm-selector">
        <label className="cm-selector-field">
          <span>Baseline (V_A)</span>
          <select
            value={baselineVersionId}
            onChange={(e) => setBaselineVersionId(e.target.value)}
            disabled={comparing}
          >
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                V{v.version_number} ({v.row_count} rows)
              </option>
            ))}
          </select>
        </label>

        <span className="cm-selector-arrow">→</span>

        <label className="cm-selector-field">
          <span>Current (V_B)</span>
          <select
            value={currentVersionId}
            onChange={(e) => setCurrentVersionId(e.target.value)}
            disabled={comparing}
          >
            {versions.map((v) => (
              <option key={v.id} value={v.id}>
                V{v.version_number} ({v.row_count} rows)
              </option>
            ))}
          </select>
        </label>

        <button
          className="cm-btn cm-btn--primary"
          onClick={() => runComparison(baselineVersionId, currentVersionId, false)}
          disabled={comparing || baselineVersionId === currentVersionId}
        >
          {comparing ? 'Comparing…' : '⚖️ Compare'}
        </button>

        <button
          className="cm-btn cm-btn--ghost"
          onClick={() => runComparison(baselineVersionId, currentVersionId, true)}
          disabled={comparing || !comparison}
          title="Force recomputation of statistical KS and PSI tests"
        >
          🔄 Recompute
        </button>

        {comparison?.id && (
          <Link
            to={`/datasets/${datasetId}/chat?scope=COMPARISON&comparisonId=${comparison.id}&initialQuery=Explain the main changes between these versions`}
            className="cm-btn cm-btn--primary"
          >
            💬 Ask AI
          </Link>
        )}
      </section>

      {/* ================= ERROR ================= */}
      {error && (
        <div className="cm-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Comparison Error</strong>
            <p>{error}</p>
          </div>
          <button type="button" className="cm-btn cm-btn--ghost cm-btn--xs" onClick={() => setError(null)}>
            ✕
          </button>
        </div>
      )}

      {/* ================= LOADING ================= */}
      {loading && (
        <div className="cm-loading">
          <span className="cm-spinner" aria-hidden="true" />
          <p>Loading dataset versions and comparison…</p>
        </div>
      )}

      {!loading && comparison && (
        <>
          {/* ================= OVERALL DRIFT BANNER ================= */}
          <section
            className="cm-overview"
            style={{ borderLeftColor: getOverallTone(comparison.overall_drift_status).color }}
          >
            <div className="cm-overview-main">
              <div className="cm-overview-head">
                <span className="cm-overview-label">Overall Comparison Status</span>
                <span
                  className="cm-overview-pill"
                  style={(() => {
                    const t = getOverallTone(comparison.overall_drift_status);
                    return { color: t.color, borderColor: t.color, background: `${t.color}22` };
                  })()}
                >
                  {getOverallTone(comparison.overall_drift_status).label}
                </span>
              </div>

              <h2>
                Comparing Version V{comparison.baseline_version.version_number} ➔ Version V
                {comparison.current_version.version_number}
              </h2>

              <p className="cm-overview-meta">
                Baseline: <strong>{comparison.baseline_version.row_count} rows × {comparison.baseline_version.column_count} cols</strong>
                {' • '}
                Current: <strong>{comparison.current_version.row_count} rows × {comparison.current_version.column_count} cols</strong>
                {' • '}
                Evaluated: <strong>{new Date(comparison.compared_at).toLocaleString()}</strong>
              </p>
            </div>

            <div className="cm-drivers">
              <span className="cm-drivers-label">
                Primary Drift Drivers ({comparison.drift_drivers.length})
              </span>
              <ul>
                {comparison.drift_drivers.slice(0, 3).map((driver, i) => (
                  <li key={i}>{driver}</li>
                ))}
                {comparison.drift_drivers.length > 3 && (
                  <li className="cm-muted">
                    +{comparison.drift_drivers.length - 3} more driver signals
                  </li>
                )}
              </ul>
            </div>
          </section>

          {/* ================= SUBSYSTEM IMPACT CARDS ================= */}
          <section className="cm-subsystem-grid">
            {/* Schema */}
            <div className="cm-subsystem-card">
              <div className="cm-subsystem-head">
                <span className="cm-subsystem-title">🏗️ Schema Evolution</span>
                <span
                  className="cm-subsystem-badge"
                  style={{
                    color: comparison.schema_summary.total_changes > 0 ? '#fbbf24' : '#34d399',
                    borderColor: comparison.schema_summary.total_changes > 0 ? '#fbbf24' : '#34d399',
                    background: comparison.schema_summary.total_changes > 0 ? 'rgba(245,158,11,.12)' : 'rgba(16,185,129,.12)',
                  }}
                >
                  {comparison.schema_summary.total_changes} Changes
                </span>
              </div>
              <div className="cm-subsystem-value">
                +{comparison.schema_summary.added_columns.length} / -{comparison.schema_summary.removed_columns.length}
              </div>
              <div className="cm-subsystem-meta">
                Added: {comparison.schema_summary.added_columns.length} • Removed:{' '}
                {comparison.schema_summary.removed_columns.length} • Type:{' '}
                {comparison.schema_summary.type_changed_columns.length}
              </div>
            </div>

            {/* Quality */}
            <div className="cm-subsystem-card">
              <div className="cm-subsystem-head">
                <span className="cm-subsystem-title">🛡️ Quality Score Delta</span>
                <span
                  className="cm-subsystem-badge"
                  style={(() => {
                    const d = comparison.subsystem_deltas.quality_drift.score_delta;
                    const color = d < -5 ? '#f43f5e' : d >= 0 ? '#34d399' : '#94a3b8';
                    return { color, borderColor: color, background: `${color}22` };
                  })()}
                >
                  {comparison.subsystem_deltas.quality_drift.score_delta !== null
                    ? `${comparison.subsystem_deltas.quality_drift.score_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.quality_drift.score_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="cm-subsystem-value">
                {comparison.subsystem_deltas.quality_drift.baseline_score ?? '—'} ➔{' '}
                {comparison.subsystem_deltas.quality_drift.current_score ?? '—'}
              </div>
              <div className="cm-subsystem-meta">
                New: {comparison.subsystem_deltas.quality_drift.new_violations_count} • Resolved:{' '}
                {comparison.subsystem_deltas.quality_drift.resolved_violations_count}
              </div>
            </div>

            {/* Risk */}
            <div className="cm-subsystem-card">
              <div className="cm-subsystem-head">
                <span className="cm-subsystem-title">🤖 ML Risk Index Delta</span>
                <span
                  className="cm-subsystem-badge"
                  style={(() => {
                    const d = comparison.subsystem_deltas.risk_drift.risk_delta;
                    const color = d > 10 ? '#fbbf24' : '#94a3b8';
                    return { color, borderColor: color, background: `${color}22` };
                  })()}
                >
                  {comparison.subsystem_deltas.risk_drift.risk_delta !== null
                    ? `${comparison.subsystem_deltas.risk_drift.risk_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.risk_drift.risk_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="cm-subsystem-value">
                {comparison.subsystem_deltas.risk_drift.baseline_risk_index ?? '—'} ➔{' '}
                {comparison.subsystem_deltas.risk_drift.current_risk_index ?? '—'}
              </div>
              <div className="cm-subsystem-meta">
                Elevated: {comparison.subsystem_deltas.risk_drift.newly_elevated_risk_columns.length} • Domain:{' '}
                {comparison.subsystem_deltas.risk_drift.domain_changed_columns.length}
              </div>
            </div>

            {/* Anomaly */}
            <div className="cm-subsystem-card">
              <div className="cm-subsystem-head">
                <span className="cm-subsystem-title">⚠ Anomaly Score Delta</span>
                <span
                  className="cm-subsystem-badge"
                  style={(() => {
                    const d = comparison.subsystem_deltas.anomaly_drift.anomaly_delta;
                    const color = d > 10 ? '#f43f5e' : '#94a3b8';
                    return { color, borderColor: color, background: `${color}22` };
                  })()}
                >
                  {comparison.subsystem_deltas.anomaly_drift.anomaly_delta !== null
                    ? `${comparison.subsystem_deltas.anomaly_drift.anomaly_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.anomaly_drift.anomaly_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="cm-subsystem-value">
                {comparison.subsystem_deltas.anomaly_drift.baseline_anomaly_score ?? '—'} ➔{' '}
                {comparison.subsystem_deltas.anomaly_drift.current_anomaly_score ?? '—'}
              </div>
              <div className="cm-subsystem-meta">
                Newly Flagged: {comparison.subsystem_deltas.anomaly_drift.newly_anomalous_columns.length} cols
              </div>
            </div>
          </section>

          {/* ================= STAT SUMMARY BANNER ================= */}
          <section className="cm-stat-summary">
            <div className="cm-stat-item">
              <span className="cm-stat-label">Numerical KS Tests</span>
              <span className="cm-stat-value">
                {comparison.numerical_summary.ks_executed_count} Executed •{' '}
                {comparison.numerical_summary.drifted_columns.length} Diverged
              </span>
            </div>
            <div className="cm-stat-item">
              <span className="cm-stat-label">Categorical PSI Tests</span>
              <span className="cm-stat-value">
                {comparison.categorical_summary.psi_executed_count} Executed •{' '}
                {comparison.categorical_summary.drifted_columns.length} Shifted
              </span>
            </div>
            <div className="cm-stat-item">
              <span className="cm-stat-label">Missingness Spikes</span>
              <span className="cm-stat-value">
                {comparison.missingness_summary.columns_with_increased_missingness.length} cols • Max +
                {comparison.missingness_summary.max_pp_increase} pp
              </span>
            </div>
            <span className="cm-stat-privacy">
              🔒 Privacy-Safe: Zero raw PII values are compared or displayed.
            </span>
          </section>

          {/* ================= COLUMN DRIFT TABLE ================= */}
          <section className="cm-panel">
            <div className="cm-panel-head">
              <div>
                <h3>Column Drift Analysis</h3>
                <p className="cm-panel-sub">
                  Showing <strong>{filteredColumns.length}</strong> of {comparison.columns.length} columns
                </p>
              </div>

              <div className="cm-filter-row">
                <input
                  type="text"
                  className="cm-input"
                  placeholder="🔍 Search columns…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
                <div className="cm-chip-row">
                  {['ALL', 'DRIFTED', 'SCHEMA_CHANGED', 'HIGH_DRIFT', 'MEDIUM_DRIFT', 'NO_DRIFT'].map((f) => (
                    <button
                      key={f}
                      type="button"
                      className={`cm-chip ${driftFilter === f ? 'cm-chip--active' : ''}`}
                      onClick={() => setDriftFilter(f)}
                    >
                      {f.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="cm-table-wrap">
              <table className="cm-table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Category</th>
                    <th>Schema Status</th>
                    <th>Drift Status</th>
                    <th>Missingness Δ</th>
                    <th>Statistical Test</th>
                    <th>Cross-Phase Signals</th>
                    <th style={{ textAlign: 'right' }}>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredColumns.map((col) => {
                    const stat = col.statistical_drift || {};
                    const isKs = stat.test_type === 'KOLMOGOROV_SMIRNOV';
                    const isPsi = stat.test_type === 'POPULATION_STABILITY_INDEX';
                    const drift = getDriftBadgeClass(col.drift_status);
                    const schema = getSchemaBadgeClass(col.schema_status);
                    const isSelected = selectedColumn?.column_name === col.column_name;

                    return (
                      <tr
                        key={col.column_name}
                        className={isSelected ? 'cm-row-selected' : ''}
                        onClick={() => handleInspectColumn(col)}
                      >
                        <td>
                          <code className="cm-col-code">{col.column_name}</code>
                          {col.current_type && (
                            <div className="cm-muted cm-mono">{col.current_type}</div>
                          )}
                        </td>
                        <td>
                          <span className="cm-tag cm-tag--neutral">{col.type_category}</span>
                        </td>
                        <td>
                          <span
                            className="cm-tag"
                            style={{
                              color: schema.color,
                              borderColor: schema.color,
                              background: `${schema.color}1a`,
                            }}
                          >
                            {col.schema_status}
                          </span>
                        </td>
                        <td>
                          <span
                            className="cm-tag"
                            style={{
                              color: drift.color,
                              borderColor: drift.color,
                              background: `${drift.color}1a`,
                            }}
                          >
                            {drift.label}
                          </span>
                        </td>
                        <td>
                          {col.missingness?.percentage_point_change !== undefined ? (
                            <span
                              className="cm-mono"
                              style={{
                                color:
                                  col.missingness.percentage_point_change >= 5
                                    ? '#f43f5e'
                                    : col.missingness.percentage_point_change > 0
                                    ? '#fbbf24'
                                    : '#94a3b8',
                                fontWeight: 700,
                              }}
                            >
                              {col.missingness.percentage_point_change > 0 ? '+' : ''}
                              {col.missingness.percentage_point_change} pp
                            </span>
                          ) : (
                            <span className="cm-muted">—</span>
                          )}
                        </td>
                        <td>
                          {stat.status === 'EXECUTED' ? (
                            <span className="cm-mono">
                              {isKs && `KS=${stat.statistic?.toFixed(3)} (p=${stat.p_value?.toFixed(4)})`}
                              {isPsi && `PSI=${stat.statistic?.toFixed(3)}`}
                            </span>
                          ) : (
                            <span className="cm-muted cm-mono">
                              {stat.status === 'UNAVAILABLE' ? 'Disk series unavailable' : '—'}
                            </span>
                          )}
                        </td>
                        <td>
                          <div className="cm-signal-row">
                            {col.quality_impact?.new_violations?.length > 0 && (
                              <span className="cm-signal cm-signal--danger">
                                +{col.quality_impact.new_violations.length} Quality
                              </span>
                            )}
                            {col.risk_impact?.risk_delta >= 10 && (
                              <span className="cm-signal cm-signal--warning">
                                ML Risk +{col.risk_impact.risk_delta}
                              </span>
                            )}
                            {col.privacy_impact?.newly_detected_entities?.length > 0 && (
                              <span className="cm-signal cm-signal--danger">
                                New PII: {col.privacy_impact.newly_detected_entities.join(', ')}
                              </span>
                            )}
                            {!col.quality_impact?.new_violations?.length &&
                              !(col.risk_impact?.risk_delta >= 10) &&
                              !col.privacy_impact?.newly_detected_entities?.length && (
                                <span className="cm-muted">Stable</span>
                              )}
                          </div>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="cm-btn cm-btn--ghost cm-btn--xs"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleInspectColumn(col);
                            }}
                          >
                            🔍 Inspect
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </>
      )}

      {/* ================= DRILLDOWN DRAWER ================= */}
      {selectedColumn && (
        <div className="cm-drawer-backdrop" onClick={() => setSelectedColumn(null)}>
          <aside className="cm-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="cm-drawer-head">
              <div>
                <span className="cm-drawer-label">Column Drift Deep Dive</span>
                <h2>
                  <code>{selectedColumn.column_name}</code>
                </h2>
                <div className="cm-drawer-tags">
                  <span
                    className="cm-tag"
                    style={(() => {
                      const s = getSchemaBadgeClass(selectedColumn.schema_status);
                      return { color: s.color, borderColor: s.color, background: `${s.color}1a` };
                    })()}
                  >
                    {selectedColumn.schema_status}
                  </span>
                  <span
                    className="cm-tag"
                    style={(() => {
                      const d = getDriftBadgeClass(selectedColumn.drift_status);
                      return { color: d.color, borderColor: d.color, background: `${d.color}1a` };
                    })()}
                  >
                    {getDriftBadgeClass(selectedColumn.drift_status).label}
                  </span>
                  <span className="cm-tag cm-tag--neutral">{selectedColumn.type_category}</span>
                </div>
              </div>
              <button
                type="button"
                className="cm-btn cm-btn--ghost"
                onClick={() => setSelectedColumn(null)}
              >
                ✕
              </button>
            </div>

            {loadingColDetail ? (
              <div className="cm-drawer-loading">
                <span className="cm-spinner cm-spinner--sm" /> Loading details…
              </div>
            ) : (
              <div className="cm-drawer-body">
                {/* Drift evidence */}
                {selectedColumn.drift_evidence?.length > 0 && (
                  <section className="cm-drawer-section">
                    <h4 className="cm-drawer-section-title">📋 Documented Drift Evidence</h4>
                    <ul className="cm-evidence-list">
                      {selectedColumn.drift_evidence.map((ev, i) => (
                        <li key={i}>{ev}</li>
                      ))}
                    </ul>
                  </section>
                )}

                {/* Statistical test details */}
                <section className="cm-drawer-section">
                  <h4 className="cm-drawer-section-title">📈 Statistical Distribution Drift</h4>
                  {selectedColumn.statistical_drift?.status === 'EXECUTED' ? (
                    <>
                      {selectedColumn.statistical_drift.test_type === 'KOLMOGOROV_SMIRNOV' && (
                        <div className="cm-stat-block">
                          <StatRow label="Test Method" value="Kolmogorov-Smirnov (2-sample)" />
                          <StatRow
                            label="Data Scope"
                            value={
                              <>
                                {selectedColumn.statistical_drift.sampling_used ? 'Sampled' : 'Full Dataset'}
                                {selectedColumn.statistical_drift.baseline_rows_evaluated && (
                                  <div className="cm-stat-sub">
                                    {selectedColumn.statistical_drift.baseline_rows_evaluated} (V_A) vs{' '}
                                    {selectedColumn.statistical_drift.current_rows_evaluated} (V_B) rows
                                  </div>
                                )}
                              </>
                            }
                            tone="success"
                          />
                          <StatRow label="KS Statistic" value={selectedColumn.statistical_drift.statistic} />
                          <StatRow label="p-value" value={selectedColumn.statistical_drift.p_value} />
                          <StatRow
                            label="Wasserstein Distance"
                            value={selectedColumn.statistical_drift.wasserstein_distance ?? '—'}
                          />
                        </div>
                      )}

                      {selectedColumn.statistical_drift.test_type === 'POPULATION_STABILITY_INDEX' && (
                        <div className="cm-stat-block">
                          <StatRow label="Test Method" value="Population Stability Index (PSI)" />
                          <StatRow
                            label="Data Scope"
                            value={
                              <>
                                {selectedColumn.statistical_drift.sampling_used ? 'Sampled' : 'Full Dataset'}
                                {selectedColumn.statistical_drift.baseline_rows_evaluated && (
                                  <div className="cm-stat-sub">
                                    {selectedColumn.statistical_drift.baseline_rows_evaluated} (V_A) vs{' '}
                                    {selectedColumn.statistical_drift.current_rows_evaluated} (V_B) rows
                                  </div>
                                )}
                              </>
                            }
                            tone="success"
                          />
                          <StatRow label="PSI Statistic" value={selectedColumn.statistical_drift.statistic} />
                          <StatRow
                            label="Categories Evaluated"
                            value={`${selectedColumn.statistical_drift.unique_categories_count} unique`}
                          />
                          <StatRow
                            label="Classification"
                            value={selectedColumn.statistical_drift.classification}
                          />
                        </div>
                      )}
                    </>
                  ) : (
                    <p className="cm-muted">
                      {selectedColumn.statistical_drift?.reason ||
                        'Series data was not stored on disk for continuous distribution test.'}
                    </p>
                  )}
                </section>

                {/* Missingness & uniqueness */}
                <section className="cm-drawer-section">
                  <h4 className="cm-drawer-section-title">📊 Missingness &amp; Uniqueness</h4>
                  <table className="cm-mini-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>Baseline (V{comparison.baseline_version.version_number})</th>
                        <th>Current (V{comparison.current_version.version_number})</th>
                        <th>Shift (Δ)</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td>Missing Count / Pct</td>
                        <td>
                          {selectedColumn.missingness?.baseline_count} (
                          {selectedColumn.missingness?.baseline_pct}%)
                        </td>
                        <td>
                          {selectedColumn.missingness?.current_count} (
                          {selectedColumn.missingness?.current_pct}%)
                        </td>
                        <td className="cm-mono">
                          {selectedColumn.missingness?.percentage_point_change > 0 ? '+' : ''}
                          {selectedColumn.missingness?.percentage_point_change} pp
                        </td>
                      </tr>
                      <tr>
                        <td>Unique Count / Pct</td>
                        <td>
                          {selectedColumn.uniqueness?.baseline_count} (
                          {selectedColumn.uniqueness?.baseline_pct}%)
                        </td>
                        <td>
                          {selectedColumn.uniqueness?.current_count} (
                          {selectedColumn.uniqueness?.current_pct}%)
                        </td>
                        <td className="cm-mono">
                          {selectedColumn.uniqueness?.percentage_point_change > 0 ? '+' : ''}
                          {selectedColumn.uniqueness?.percentage_point_change} pp
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </section>

                {/* Cross-subsystem impacts */}
                <section className="cm-drawer-section">
                  <h4 className="cm-drawer-section-title">🔍 Cross-Phase Subsystem Findings</h4>

                  <div className="cm-impact-block">
                    <span className="cm-impact-label">Quality Rule Failures</span>
                    <p>
                      Baseline: {selectedColumn.quality_impact?.baseline_violations_count} failures •
                      Current: {selectedColumn.quality_impact?.current_violations_count} failures
                    </p>
                    {selectedColumn.quality_impact?.new_violations?.length > 0 && (
                      <ul className="cm-impact-list cm-impact-list--danger">
                        {selectedColumn.quality_impact.new_violations.map((nv, i) => (
                          <li key={i}>New Failure: {nv}</li>
                        ))}
                      </ul>
                    )}
                  </div>

                  <div className="cm-impact-block">
                    <span className="cm-impact-label">ML Risk Classification</span>
                    <p>
                      Level: {selectedColumn.risk_impact?.baseline_risk_level} ➔{' '}
                      {selectedColumn.risk_impact?.current_risk_level} • Score:{' '}
                      {selectedColumn.risk_impact?.baseline_risk_score} ➔{' '}
                      {selectedColumn.risk_impact?.current_risk_score} (Δ{' '}
                      {selectedColumn.risk_impact?.risk_delta > 0 ? '+' : ''}
                      {selectedColumn.risk_impact?.risk_delta} pts)
                    </p>
                    {selectedColumn.risk_impact?.domain_shifted && (
                      <p className="cm-impact-warn">
                        Domain shifted: '{selectedColumn.risk_impact.baseline_domain}' ➔{' '}
                        '{selectedColumn.risk_impact.current_domain}'
                      </p>
                    )}
                  </div>

                  <div className="cm-impact-block">
                    <span className="cm-impact-label">Outlier &amp; Anomaly Severity</span>
                    <p>
                      Severity: {selectedColumn.anomaly_impact?.baseline_severity} ➔{' '}
                      {selectedColumn.anomaly_impact?.current_severity} • Anomaly rate:{' '}
                      {((selectedColumn.anomaly_impact?.current_rate || 0) * 100).toFixed(1)}%
                    </p>
                  </div>

                  <div className="cm-impact-block">
                    <span className="cm-impact-label">PII Detection</span>
                    <p>
                      {selectedColumn.privacy_impact?.newly_detected_entities?.length > 0 ? (
                        <span className="cm-impact-danger">
                          Newly Detected: {selectedColumn.privacy_impact.newly_detected_entities.join(', ')}
                        </span>
                      ) : (
                        'No new PII entities introduced.'
                      )}
                    </p>
                  </div>
                </section>
              </div>
            )}
          </aside>
        </div>
      )}
    </div>
  );
}

/* ---------- Helpers ---------- */
function StatRow({ label, value, tone }) {
  return (
    <div className="cm-stat-row">
      <span className="cm-stat-row-label">{label}</span>
      <span className={`cm-stat-row-value${tone ? ` cm-stat-row-value--${tone}` : ''}`}>
        {value}
      </span>
    </div>
  );
}