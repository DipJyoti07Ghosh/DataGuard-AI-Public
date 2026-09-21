/**
 * DataGuard AI — Dataset Version Comparison & Drift Detection (Phase 10)
 *
 * Provides deterministic, explainable comparison between two snapshot versions
 * of the same dataset. Evaluates schema evolution, missingness shifts, uniqueness
 * shifts, real KS/PSI distribution drift, and cross-subsystem deltas (Phases 5–9).
 */

import React, { useState, useEffect } from 'react';
import { useParams, useSearchParams, Link, useNavigate } from 'react-router-dom';
import {
  getDataset,
  getDatasetComparisons,
  compareDatasetVersions,
  getColumnDriftDetail,
} from '../api/client';

export default function Compare() {
  const { datasetId, versionId } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  // URL / Query Params
  const queryBaseline = searchParams.get('baseline');
  const queryCurrent = searchParams.get('current');

  // State
  const [dataset, setDataset] = useState(null);
  const [versions, setVersions] = useState([]);
  const [baselineVersionId, setBaselineVersionId] = useState(queryBaseline || '');
  const [currentVersionId, setCurrentVersionId] = useState(queryCurrent || versionId || '');
  const [comparison, setComparison] = useState(null);
  const [loading, setLoading] = useState(true);
  const [comparing, setComparing] = useState(false);
  const [error, setError] = useState(null);

  // Filters & Search
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [driftFilter, setDriftFilter] = useState('ALL');

  // Slide-out Drawer
  const [selectedColumn, setSelectedColumn] = useState(null);
  const [columnDetail, setColumnDetail] = useState(null);
  const [loadingColDetail, setLoadingColDetail] = useState(false);

  // 1. Initial Load: Fetch Dataset & Versions
  useEffect(() => {
    loadDatasetAndVersions();
  }, [datasetId]);

  async function loadDatasetAndVersions() {
    try {
      setLoading(true);
      setError(null);

      const dData = await getDataset(datasetId);
      setDataset(dData);

      const vList = (dData.versions || []).sort((a, b) => a.version_number - b.version_number);
      setVersions(vList);

      if (vList.length >= 2) {
        const baseId = queryBaseline || (vList.length >= 2 ? vList[vList.length - 2].id : vList[0].id);
        const currId = queryCurrent || versionId || vList[vList.length - 1].id;
        setBaselineVersionId(baseId);
        setCurrentVersionId(currId);
        await runComparison(baseId, currId, false);
      } else if (vList.length === 1) {
        setError('Dataset only has 1 version. Upload at least 2 snapshot versions to compare drift.');
      } else {
        setError('No snapshot versions found for this dataset.');
      }
    } catch (err) {
      setError(err.message || 'Failed to load dataset metadata for comparison.');
    } finally {
      setLoading(false);
    }
  }

  // 2. Run / Trigger Comparison
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
      // If drawer is open, refresh column detail
      if (selectedColumn) {
        loadColumnDetail(res.id, selectedColumn.column_name);
      }
    } catch (err) {
      setError(err.message || 'Comparison calculation failed.');
    } finally {
      setComparing(false);
    }
  }

  // 3. Handle Column Inspection Drawer
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

  // Helper: Format status badge classes
  const getDriftBadgeClass = (status) => {
    switch (status) {
      case 'HIGH_DRIFT':
        return 'badge--error';
      case 'MEDIUM_DRIFT':
        return 'badge--warning';
      case 'LOW_DRIFT':
        return 'badge--info';
      case 'NO_DRIFT':
      case 'NO_DRIFT (IMPROVED)':
        return 'badge--success';
      default:
        return 'badge--neutral';
    }
  };

  const getSchemaBadgeClass = (status) => {
    switch (status) {
      case 'ADDED':
        return 'badge--info';
      case 'REMOVED':
        return 'badge--error';
      case 'TYPE_CHANGED':
        return 'badge--warning';
      case 'UNCHANGED':
        return 'badge--neutral';
      default:
        return 'badge--neutral';
    }
  };

  // Filter column rows
  const filteredColumns = (comparison?.columns || []).filter((col) => {
    // Search
    if (searchQuery && !col.column_name.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    // Category Filter
    if (categoryFilter !== 'ALL' && col.type_category !== categoryFilter) {
      return false;
    }
    // Drift Filter
    if (driftFilter === 'DRIFTED') {
      return ['HIGH_DRIFT', 'MEDIUM_DRIFT', 'LOW_DRIFT'].includes(col.drift_status);
    }
    if (driftFilter === 'SCHEMA_CHANGED') {
      return col.schema_status !== 'UNCHANGED';
    }
    if (driftFilter === 'HIGH_DRIFT') {
      return col.drift_status === 'HIGH_DRIFT';
    }
    if (driftFilter === 'MEDIUM_DRIFT') {
      return col.drift_status === 'MEDIUM_DRIFT';
    }
    if (driftFilter === 'NO_DRIFT') {
      return col.drift_status === 'NO_DRIFT';
    }
    return true;
  });

  return (
    <div className="compare-page page-container" style={{ padding: '2rem' }}>
      {/* Header & Breadcrumbs */}
      <div className="page-header-block flex-between" style={{ marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
        <div>
          <div className="breadcrumbs text-muted flex-row" style={{ gap: '6px', fontSize: '0.875rem', marginBottom: '0.4rem' }}>
            <Link to="/datasets">Datasets</Link>
            <span>/</span>
            <span className="text-primary">{dataset?.name || 'Dataset'}</span>
            <span>/</span>
            <span className="text-accent">Version Comparison & Drift</span>
          </div>
          <h1 className="page-heading" style={{ fontSize: '1.75rem', fontWeight: 700, margin: 0 }}>
            ⚖️ Version Comparison & Drift Analysis
          </h1>
          <p className="page-subheading text-secondary" style={{ marginTop: '0.25rem' }}>
            Explainable comparison of schema evolution, distribution drift, and cross-phase metrics.
          </p>
        </div>

        {/* Version Selector Bar */}
        <div className="glass-card flex-row" style={{ padding: '0.75rem 1.25rem', gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
          <div className="flex-row" style={{ gap: '0.5rem', alignItems: 'center' }}>
            <span className="text-muted" style={{ fontSize: '0.875rem', fontWeight: 600 }}>Baseline (V_A):</span>
            <select
              className="form-input"
              style={{ width: '130px', padding: '0.35rem 0.6rem', fontSize: '0.875rem' }}
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
          </div>

          <span className="text-muted" style={{ fontWeight: 700 }}>➔</span>

          <div className="flex-row" style={{ gap: '0.5rem', alignItems: 'center' }}>
            <span className="text-muted" style={{ fontSize: '0.875rem', fontWeight: 600 }}>Current (V_B):</span>
            <select
              className="form-input"
              style={{ width: '130px', padding: '0.35rem 0.6rem', fontSize: '0.875rem' }}
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
          </div>

          <button
            className="btn btn--primary btn--sm"
            onClick={() => runComparison(baselineVersionId, currentVersionId, false)}
            disabled={comparing || baselineVersionId === currentVersionId}
            style={{ minWidth: '100px' }}
          >
            {comparing ? 'Comparing...' : '⚖️ Compare'}
          </button>

          <button
            className="btn btn--secondary btn--sm"
            onClick={() => runComparison(baselineVersionId, currentVersionId, true)}
            disabled={comparing || !comparison}
            title="Force recomputation of statistical KS and PSI tests"
          >
            🔄 Recompute
          </button>

          {comparison?.id && (
            <Link
              to={`/datasets/${datasetId}/chat?scope=COMPARISON&comparisonId=${comparison.id}&initialQuery=Explain the main changes between these versions`}
              className="btn btn--primary btn--sm flex-row align-center"
              style={{ textDecoration: 'none', gap: '4px' }}
            >
              <span>💬</span> Ask AI
            </Link>
          )}
        </div>
      </div>

      {/* Error Alert */}
      {error && (
        <div className="alert-box alert-box--error" style={{ marginBottom: '1.5rem' }}>
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            <strong>Comparison Error</strong>
            <p>{error}</p>
          </div>
          <button className="alert-close-btn" onClick={() => setError(null)}>✕</button>
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="glass-card" style={{ padding: '3rem', textAlign: 'center' }}>
          <span className="spinner-inline" style={{ width: '24px', height: '24px', display: 'inline-block' }}></span>
          <p className="text-muted" style={{ marginTop: '1rem' }}>Loading dataset versions and comparison...</p>
        </div>
      )}

      {!loading && comparison && (
        <>
          {/* Top Hero Banner: Overall Drift Status */}
          <div
            className="glass-card"
            style={{
              padding: '1.5rem',
              marginBottom: '1.5rem',
              borderLeft: `4px solid ${
                comparison.overall_drift_status === 'HIGH_DRIFT'
                  ? '#ef4444'
                  : comparison.overall_drift_status === 'MEDIUM_DRIFT'
                  ? '#f59e0b'
                  : comparison.overall_drift_status === 'LOW_DRIFT'
                  ? '#3b82f6'
                  : '#10b981'
              }`,
            }}
          >
            <div className="flex-between" style={{ alignItems: 'flex-start', flexWrap: 'wrap', gap: '1rem' }}>
              <div>
                <div className="flex-row" style={{ gap: '0.75rem', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <span className="text-muted" style={{ fontSize: '0.85rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Overall Comparison Status
                  </span>
                  <span className={`badge ${getDriftBadgeClass(comparison.overall_drift_status)}`} style={{ fontSize: '0.9rem', padding: '0.35rem 0.75rem' }}>
                    {comparison.overall_drift_status.replace('_', ' ')}
                  </span>
                </div>
                <h3 style={{ margin: '0 0 0.5rem 0', fontSize: '1.25rem', fontWeight: 600 }}>
                  Comparing Version V{comparison.baseline_version.version_number} ➔ Version V{comparison.current_version.version_number}
                </h3>
                <p className="text-secondary" style={{ fontSize: '0.875rem', margin: 0 }}>
                  Baseline: {comparison.baseline_version.row_count} rows × {comparison.baseline_version.column_count} cols | Current: {comparison.current_version.row_count} rows × {comparison.current_version.column_count} cols | Evaluated: {new Date(comparison.compared_at).toLocaleString()}
                </p>
              </div>

              {/* Quick Driver Summary */}
              <div style={{ maxWidth: '500px', background: 'rgba(0, 0, 0, 0.2)', padding: '0.75rem 1rem', borderRadius: '8px' }}>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', fontWeight: 700, display: 'block', marginBottom: '0.25rem' }}>
                  Primary Drift Drivers ({comparison.drift_drivers.length})
                </span>
                <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.825rem', color: '#cbd5e1' }}>
                  {comparison.drift_drivers.slice(0, 3).map((driver, i) => (
                    <li key={i}>{driver}</li>
                  ))}
                  {comparison.drift_drivers.length > 3 && (
                    <li className="text-muted">+{comparison.drift_drivers.length - 3} more driver signals</li>
                  )}
                </ul>
              </div>
            </div>
          </div>

          {/* 4 Subsystem Impact Metric Cards */}
          <div
            className="grid-4"
            style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))',
              gap: '1rem',
              marginBottom: '1.5rem',
            }}
          >
            {/* 1. Schema Evolution */}
            <div className="glass-card stat-card" style={{ padding: '1.25rem' }}>
              <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                <span className="stat-label text-muted" style={{ fontSize: '0.8rem', fontWeight: 600 }}>🏗️ Schema Evolution</span>
                <span className={`badge ${comparison.schema_summary.total_changes > 0 ? 'badge--warning' : 'badge--success'}`}>
                  {comparison.schema_summary.total_changes} Changes
                </span>
              </div>
              <div className="stat-value" style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                +{comparison.schema_summary.added_columns.length} / -{comparison.schema_summary.removed_columns.length}
              </div>
              <div className="text-secondary" style={{ fontSize: '0.8rem' }}>
                Added: {comparison.schema_summary.added_columns.length} | Removed: {comparison.schema_summary.removed_columns.length} | Type: {comparison.schema_summary.type_changed_columns.length}
              </div>
            </div>

            {/* 2. Data Quality Shift */}
            <div className="glass-card stat-card" style={{ padding: '1.25rem' }}>
              <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                <span className="stat-label text-muted" style={{ fontSize: '0.8rem', fontWeight: 600 }}>🛡️ Quality Score Delta</span>
                <span className={`badge ${
                  comparison.subsystem_deltas.quality_drift.score_delta < -5.0
                    ? 'badge--error'
                    : comparison.subsystem_deltas.quality_drift.score_delta >= 0
                    ? 'badge--success'
                    : 'badge--neutral'
                }`}>
                  {comparison.subsystem_deltas.quality_drift.score_delta !== null
                    ? `${comparison.subsystem_deltas.quality_drift.score_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.quality_drift.score_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="stat-value" style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {comparison.subsystem_deltas.quality_drift.baseline_score ?? '—'} ➔ {comparison.subsystem_deltas.quality_drift.current_score ?? '—'}
              </div>
              <div className="text-secondary" style={{ fontSize: '0.8rem' }}>
                New Violations: {comparison.subsystem_deltas.quality_drift.new_violations_count} | Resolved: {comparison.subsystem_deltas.quality_drift.resolved_violations_count}
              </div>
            </div>

            {/* 3. ML Risk Index Delta */}
            <div className="glass-card stat-card" style={{ padding: '1.25rem' }}>
              <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                <span className="stat-label text-muted" style={{ fontSize: '0.8rem', fontWeight: 600 }}>🤖 ML Risk Index Delta</span>
                <span className={`badge ${
                  (comparison.subsystem_deltas.risk_drift.risk_delta || 0) > 10.0 ? 'badge--warning' : 'badge--neutral'
                }`}>
                  {comparison.subsystem_deltas.risk_drift.risk_delta !== null
                    ? `${comparison.subsystem_deltas.risk_drift.risk_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.risk_drift.risk_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="stat-value" style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {comparison.subsystem_deltas.risk_drift.baseline_risk_index ?? '—'} ➔ {comparison.subsystem_deltas.risk_drift.current_risk_index ?? '—'}
              </div>
              <div className="text-secondary" style={{ fontSize: '0.8rem' }}>
                Elevated: {comparison.subsystem_deltas.risk_drift.newly_elevated_risk_columns.length} cols | Domain shifts: {comparison.subsystem_deltas.risk_drift.domain_changed_columns.length}
              </div>
            </div>

            {/* 4. Anomaly Exposure Delta */}
            <div className="glass-card stat-card" style={{ padding: '1.25rem' }}>
              <div className="flex-between" style={{ marginBottom: '0.5rem' }}>
                <span className="stat-label text-muted" style={{ fontSize: '0.8rem', fontWeight: 600 }}>⚠ Anomaly Score Delta</span>
                <span className={`badge ${
                  (comparison.subsystem_deltas.anomaly_drift.anomaly_delta || 0) > 10.0 ? 'badge--error' : 'badge--neutral'
                }`}>
                  {comparison.subsystem_deltas.anomaly_drift.anomaly_delta !== null
                    ? `${comparison.subsystem_deltas.anomaly_drift.anomaly_delta >= 0 ? '+' : ''}${comparison.subsystem_deltas.anomaly_drift.anomaly_delta} pts`
                    : 'N/A'}
                </span>
              </div>
              <div className="stat-value" style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
                {comparison.subsystem_deltas.anomaly_drift.baseline_anomaly_score ?? '—'} ➔ {comparison.subsystem_deltas.anomaly_drift.current_anomaly_score ?? '—'}
              </div>
              <div className="text-secondary" style={{ fontSize: '0.8rem' }}>
                Newly Flagged Cols: {comparison.subsystem_deltas.anomaly_drift.newly_anomalous_columns.length}
              </div>
            </div>
          </div>

          {/* Statistical Distribution Summary Banner */}
          <div className="glass-card flex-row flex-between" style={{ padding: '1rem 1.5rem', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
            <div className="flex-row" style={{ gap: '2rem', flexWrap: 'wrap' }}>
              <div>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'block' }}>
                  Numerical KS Tests
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                  {comparison.numerical_summary.ks_executed_count} Executed | {comparison.numerical_summary.drifted_columns.length} Diverged
                </span>
              </div>
              <div>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'block' }}>
                  Categorical PSI Tests
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                  {comparison.categorical_summary.psi_executed_count} Executed | {comparison.categorical_summary.drifted_columns.length} Shifted
                </span>
              </div>
              <div>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', display: 'block' }}>
                  Missingness Spikes
                </span>
                <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>
                  {comparison.missingness_summary.columns_with_increased_missingness.length} Columns (Max +{comparison.missingness_summary.max_pp_increase} pp)
                </span>
              </div>
            </div>

            <div className="text-muted" style={{ fontSize: '0.8rem' }}>
              🔒 Privacy-Safe: Zero raw PII values are compared or displayed.
            </div>
          </div>

          {/* Column Drift Table Section */}
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            {/* Toolbar */}
            <div className="flex-between" style={{ marginBottom: '1rem', flexWrap: 'wrap', gap: '1rem' }}>
              <div className="flex-row" style={{ gap: '1rem', alignItems: 'center', flexWrap: 'wrap' }}>
                <input
                  type="text"
                  placeholder="🔍 Search columns..."
                  className="form-input"
                  style={{ width: '220px', padding: '0.4rem 0.8rem', fontSize: '0.875rem' }}
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />

                {/* Filter Pills */}
                <div className="flex-row" style={{ gap: '0.4rem' }}>
                  {['ALL', 'DRIFTED', 'SCHEMA_CHANGED', 'HIGH_DRIFT', 'MEDIUM_DRIFT', 'NO_DRIFT'].map((f) => (
                    <button
                      key={f}
                      className={`btn btn--sm ${driftFilter === f ? 'btn--primary' : 'btn--secondary'}`}
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem' }}
                      onClick={() => setDriftFilter(f)}
                    >
                      {f.replace('_', ' ')}
                    </button>
                  ))}
                </div>
              </div>

              <span className="text-muted" style={{ fontSize: '0.875rem' }}>
                Showing <strong>{filteredColumns.length}</strong> of {comparison.columns.length} columns
              </span>
            </div>

            {/* Table */}
            <div className="table-responsive">
              <table className="data-table" style={{ width: '100%', fontSize: '0.875rem' }}>
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Category</th>
                    <th>Schema Status</th>
                    <th>Drift Status</th>
                    <th>Missingness Δ</th>
                    <th>Statistical Test</th>
                    <th>Cross-Phase Signals</th>
                    <th>Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredColumns.map((col) => {
                    const stat = col.statistical_drift || {};
                    const isKs = stat.test_type === 'KOLMOGOROV_SMIRNOV';
                    const isPsi = stat.test_type === 'POPULATION_STABILITY_INDEX';

                    return (
                      <tr
                        key={col.column_name}
                        onClick={() => handleInspectColumn(col)}
                        style={{
                          cursor: 'pointer',
                          background: selectedColumn?.column_name === col.column_name ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                        }}
                      >
                        <td>
                          <strong>{col.column_name}</strong>
                          {col.current_type && (
                            <span className="text-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                              {col.current_type}
                            </span>
                          )}
                        </td>
                        <td>
                          <span className="badge badge--neutral" style={{ fontSize: '0.75rem' }}>
                            {col.type_category}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${getSchemaBadgeClass(col.schema_status)}`} style={{ fontSize: '0.75rem' }}>
                            {col.schema_status}
                          </span>
                        </td>
                        <td>
                          <span className={`badge ${getDriftBadgeClass(col.drift_status)}`} style={{ fontSize: '0.75rem' }}>
                            {col.drift_status.replace('_', ' ')}
                          </span>
                        </td>
                        <td>
                          {col.missingness?.percentage_point_change !== undefined ? (
                            <span
                              style={{
                                color:
                                  col.missingness.percentage_point_change >= 5.0
                                    ? '#ef4444'
                                    : col.missingness.percentage_point_change > 0
                                    ? '#f59e0b'
                                    : '#94a3b8',
                              }}
                            >
                              {col.missingness.percentage_point_change > 0 ? '+' : ''}
                              {col.missingness.percentage_point_change} pp
                            </span>
                          ) : (
                            '—'
                          )}
                        </td>
                        <td>
                          {stat.status === 'EXECUTED' ? (
                            <span style={{ fontSize: '0.8rem' }}>
                              {isKs && `KS=${stat.statistic?.toFixed(3)} (p=${stat.p_value?.toFixed(4)})`}
                              {isPsi && `PSI=${stat.statistic?.toFixed(3)}`}
                            </span>
                          ) : (
                            <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                              {stat.status === 'UNAVAILABLE' ? 'Disk series unavailable' : '—'}
                            </span>
                          )}
                        </td>
                        <td>
                          <div className="flex-row" style={{ gap: '0.3rem', flexWrap: 'wrap' }}>
                            {col.quality_impact?.new_violations?.length > 0 && (
                              <span className="badge badge--error" style={{ fontSize: '0.7rem' }}>
                                +{col.quality_impact.new_violations.length} Quality Failures
                              </span>
                            )}
                            {col.risk_impact?.risk_delta >= 10.0 && (
                              <span className="badge badge--warning" style={{ fontSize: '0.7rem' }}>
                                ML Risk +{col.risk_impact.risk_delta}
                              </span>
                            )}
                            {col.privacy_impact?.newly_detected_entities?.length > 0 && (
                              <span className="badge badge--error" style={{ fontSize: '0.7rem' }}>
                                New PII: {col.privacy_impact.newly_detected_entities.join(', ')}
                              </span>
                            )}
                            {!col.quality_impact?.new_violations?.length &&
                              !(col.risk_impact?.risk_delta >= 10.0) &&
                              !col.privacy_impact?.newly_detected_entities?.length && (
                                <span className="text-muted" style={{ fontSize: '0.75rem' }}>Stable</span>
                              )}
                          </div>
                        </td>
                        <td>
                          <button
                            className="btn btn--secondary btn--sm"
                            style={{ fontSize: '0.75rem', padding: '0.25rem 0.5rem' }}
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
          </div>
        </>
      )}

      {/* Slide-out Drilldown Drawer */}
      {selectedColumn && (
        <div
          className="drawer-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(4px)',
            display: 'flex',
            justifyContent: 'flex-end',
            zIndex: 1000,
          }}
          onClick={() => setSelectedColumn(null)}
        >
          <div
            className="drawer-content"
            style={{
              width: '600px',
              maxWidth: '90vw',
              background: '#111827',
              height: '100%',
              padding: '2rem',
              overflowY: 'auto',
              boxShadow: '-4px 0 24px rgba(0,0,0,0.5)',
              borderLeft: '1px solid rgba(148, 163, 184, 0.2)',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {/* Drawer Header */}
            <div className="flex-between" style={{ marginBottom: '1.5rem' }}>
              <div>
                <span className="text-muted" style={{ fontSize: '0.8rem', textTransform: 'uppercase' }}>
                  Column Drift Deep Dive
                </span>
                <h2 style={{ margin: '0.25rem 0 0 0', fontSize: '1.5rem', fontWeight: 700 }}>
                  {selectedColumn.column_name}
                </h2>
                <div className="flex-row" style={{ gap: '0.5rem', marginTop: '0.5rem' }}>
                  <span className={`badge ${getSchemaBadgeClass(selectedColumn.schema_status)}`}>
                    {selectedColumn.schema_status}
                  </span>
                  <span className={`badge ${getDriftBadgeClass(selectedColumn.drift_status)}`}>
                    {selectedColumn.drift_status.replace('_', ' ')}
                  </span>
                  <span className="badge badge--neutral">
                    {selectedColumn.type_category}
                  </span>
                </div>
              </div>
              <button
                className="btn btn--secondary btn--sm"
                onClick={() => setSelectedColumn(null)}
                style={{ fontSize: '1.1rem', padding: '0.25rem 0.6rem' }}
              >
                ✕
              </button>
            </div>

            {loadingColDetail ? (
              <div style={{ textAlign: 'center', padding: '2rem' }}>
                <span className="spinner-inline"></span> Loading details...
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
                {/* 1. Evidence List */}
                {selectedColumn.drift_evidence?.length > 0 && (
                  <div className="glass-card" style={{ padding: '1rem' }}>
                    <h4 style={{ margin: '0 0 0.5rem 0', fontSize: '0.9rem', color: '#f1f5f9' }}>
                      📋 Documented Drift Evidence
                    </h4>
                    <ul style={{ margin: 0, paddingLeft: '1.2rem', fontSize: '0.85rem', color: '#cbd5e1' }}>
                      {selectedColumn.drift_evidence.map((ev, i) => (
                        <li key={i} style={{ marginBottom: '0.25rem' }}>{ev}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* 2. Statistical Distribution Test Details */}
                <div className="glass-card" style={{ padding: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#f1f5f9' }}>
                    📈 Statistical Distribution Drift
                  </h4>
                  {selectedColumn.statistical_drift?.status === 'EXECUTED' ? (
                    <div style={{ fontSize: '0.85rem' }}>
                      {selectedColumn.statistical_drift.test_type === 'KOLMOGOROV_SMIRNOV' && (
                        <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                          <div>
                            <span className="text-muted">Test Method:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>Kolmogorov-Smirnov (2-sample)</p>
                          </div>
                          <div>
                            <span className="text-muted">Data Scope:</span>
                            <p style={{ margin: 0, fontWeight: 600, color: '#10b981' }}>
                              {selectedColumn.statistical_drift.sampling_used ? 'Sampled' : 'Full Dataset (Non-sampled)'}
                              {selectedColumn.statistical_drift.baseline_rows_evaluated && (
                                <span className="text-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                                  {selectedColumn.statistical_drift.baseline_rows_evaluated} (V_A) vs {selectedColumn.statistical_drift.current_rows_evaluated} (V_B) rows
                                </span>
                              )}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted">KS Statistic:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.statistic}</p>
                          </div>
                          <div>
                            <span className="text-muted">p-value:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.p_value}</p>
                          </div>
                          <div>
                            <span className="text-muted">Wasserstein Distance:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.wasserstein_distance ?? '—'}</p>
                          </div>
                        </div>
                      )}

                      {selectedColumn.statistical_drift.test_type === 'POPULATION_STABILITY_INDEX' && (
                        <div className="grid-2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                          <div>
                            <span className="text-muted">Test Method:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>Population Stability Index (PSI)</p>
                          </div>
                          <div>
                            <span className="text-muted">Data Scope:</span>
                            <p style={{ margin: 0, fontWeight: 600, color: '#10b981' }}>
                              {selectedColumn.statistical_drift.sampling_used ? 'Sampled' : 'Full Dataset (Non-sampled)'}
                              {selectedColumn.statistical_drift.baseline_rows_evaluated && (
                                <span className="text-muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                                  {selectedColumn.statistical_drift.baseline_rows_evaluated} (V_A) vs {selectedColumn.statistical_drift.current_rows_evaluated} (V_B) rows
                                </span>
                              )}
                            </p>
                          </div>
                          <div>
                            <span className="text-muted">PSI Statistic:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.statistic}</p>
                          </div>
                          <div>
                            <span className="text-muted">Categories Evaluated:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.unique_categories_count} unique categories</p>
                          </div>
                          <div>
                            <span className="text-muted">Classification:</span>
                            <p style={{ margin: 0, fontWeight: 600 }}>{selectedColumn.statistical_drift.classification}</p>
                          </div>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                      {selectedColumn.statistical_drift?.reason || 'Series data was not stored on disk for continuous distribution test.'}
                    </p>
                  )}
                </div>

                {/* 3. Missingness & Uniqueness Table */}
                <div className="glass-card" style={{ padding: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#f1f5f9' }}>
                    📊 Missingness & Uniqueness Comparison
                  </h4>
                  <table className="data-table" style={{ width: '100%', fontSize: '0.8rem' }}>
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
                        <td>{selectedColumn.missingness?.baseline_count} ({selectedColumn.missingness?.baseline_pct}%)</td>
                        <td>{selectedColumn.missingness?.current_count} ({selectedColumn.missingness?.current_pct}%)</td>
                        <td style={{ fontWeight: 600 }}>{selectedColumn.missingness?.percentage_point_change > 0 ? '+' : ''}{selectedColumn.missingness?.percentage_point_change} pp</td>
                      </tr>
                      <tr>
                        <td>Unique Count / Pct</td>
                        <td>{selectedColumn.uniqueness?.baseline_count} ({selectedColumn.uniqueness?.baseline_pct}%)</td>
                        <td>{selectedColumn.uniqueness?.current_count} ({selectedColumn.uniqueness?.current_pct}%)</td>
                        <td style={{ fontWeight: 600 }}>{selectedColumn.uniqueness?.percentage_point_change > 0 ? '+' : ''}{selectedColumn.uniqueness?.percentage_point_change} pp</td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                {/* 4. Cross-Subsystem Impacts */}
                <div className="glass-card" style={{ padding: '1rem' }}>
                  <h4 style={{ margin: '0 0 0.75rem 0', fontSize: '0.9rem', color: '#f1f5f9' }}>
                    🔍 Cross-Phase Subsystem Findings
                  </h4>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', fontSize: '0.85rem' }}>
                    {/* Quality */}
                    <div>
                      <span className="text-muted" style={{ fontWeight: 600 }}>Quality Rule Failures:</span>
                      <p style={{ margin: '0.2rem 0 0 0' }}>
                        Baseline: {selectedColumn.quality_impact?.baseline_violations_count} failures | Current: {selectedColumn.quality_impact?.current_violations_count} failures
                      </p>
                      {selectedColumn.quality_impact?.new_violations?.length > 0 && (
                        <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', color: '#ef4444' }}>
                          {selectedColumn.quality_impact.new_violations.map((nv, i) => (
                            <li key={i}>New Failure: {nv}</li>
                          ))}
                        </ul>
                      )}
                    </div>

                    {/* ML Risk */}
                    <div>
                      <span className="text-muted" style={{ fontWeight: 600 }}>ML Risk Classification:</span>
                      <p style={{ margin: '0.2rem 0 0 0' }}>
                        Level: {selectedColumn.risk_impact?.baseline_risk_level} ➔ {selectedColumn.risk_impact?.current_risk_level} (Score: {selectedColumn.risk_impact?.baseline_risk_score} ➔ {selectedColumn.risk_impact?.current_risk_score}, Δ {selectedColumn.risk_impact?.risk_delta > 0 ? '+' : ''}{selectedColumn.risk_impact?.risk_delta} pts)
                      </p>
                      {selectedColumn.risk_impact?.domain_shifted && (
                        <p style={{ margin: '0.2rem 0 0 0', color: '#f59e0b' }}>
                          Domain shifted: '{selectedColumn.risk_impact.baseline_domain}' ➔ '{selectedColumn.risk_impact.current_domain}'
                        </p>
                      )}
                    </div>

                    {/* Anomaly */}
                    <div>
                      <span className="text-muted" style={{ fontWeight: 600 }}>Outlier & Anomaly Severity:</span>
                      <p style={{ margin: '0.2rem 0 0 0' }}>
                        Severity: {selectedColumn.anomaly_impact?.baseline_severity} ➔ {selectedColumn.anomaly_impact?.current_severity} (Anomaly rate: {((selectedColumn.anomaly_impact?.current_rate || 0) * 100).toFixed(1)}%)
                      </p>
                    </div>

                    {/* PII */}
                    <div>
                      <span className="text-muted" style={{ fontWeight: 600 }}>PII Detection:</span>
                      <p style={{ margin: '0.2rem 0 0 0' }}>
                        {selectedColumn.privacy_impact?.newly_detected_entities?.length > 0 ? (
                          <span style={{ color: '#ef4444' }}>
                            Newly Detected Sensitive Entities: {selectedColumn.privacy_impact.newly_detected_entities.join(', ')}
                          </span>
                        ) : (
                          'No new PII entities introduced.'
                        )}
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
