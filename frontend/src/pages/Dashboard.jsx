/**
 * DataGuard AI — Phase 13 Data Quality Dashboard & Visualization
 *
 * Polished enterprise presentation layer synthesizing Phase 4-10 stored analytical results.
 * Strictly read-only: does not recalculate analytics or expose raw PII / raw dataset cells.
 */

import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  Legend,
  PieChart,
  Pie,
} from 'recharts';

import { getDashboard, getDatasets } from '../api/client';
import './Dashboard.css';

export default function Dashboard() {
  const { datasetId: routeDatasetId, versionId: routeVersionId } = useParams();
  const navigate = useNavigate();

  const [datasetsList, setDatasetsList] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(routeDatasetId || '');
  const [selectedVersionId, setSelectedVersionId] = useState(routeVersionId || '');

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Set document title
  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) {
      titleEl.textContent = 'Data Quality Dashboard';
    }
  }, []);

  // Fetch available datasets for the selector if not already loaded
  useEffect(() => {
    async function loadDatasetOptions() {
      try {
        const list = await getDatasets();
        setDatasetsList(list || []);
        if (!routeDatasetId && list && list.length > 0) {
          setSelectedDatasetId(list[0].id);
          // Navigate to clean route
          navigate(`/datasets/${list[0].id}/dashboard`, { replace: true });
        }
      } catch (err) {
        console.error('Failed to load dataset list:', err);
      }
    }
    loadDatasetOptions();
  }, [routeDatasetId, navigate]);

  // Synchronize route parameters with state
  useEffect(() => {
    if (routeDatasetId) {
      setSelectedDatasetId(routeDatasetId);
    }
    if (routeVersionId) {
      setSelectedVersionId(routeVersionId);
    }
  }, [routeDatasetId, routeVersionId]);

  // Main fetch function (read-only)
  const fetchDashboardData = useCallback(async (isManualRefresh = false) => {
    if (!selectedDatasetId) return;

    if (isManualRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const data = await getDashboard(selectedDatasetId, selectedVersionId || null);
      setDashboardData(data);
      if (data && data.version && !selectedVersionId) {
        setSelectedVersionId(data.version.id);
      }
    } catch (err) {
      console.error('Failed to load dashboard data:', err);
      setError(err.message || 'Unable to load dataset dashboard data.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [selectedDatasetId, selectedVersionId]);

  useEffect(() => {
    if (selectedDatasetId) {
      fetchDashboardData(false);
    }
  }, [selectedDatasetId, selectedVersionId, fetchDashboardData]);

  // Handle Dataset change from selector
  const handleDatasetChange = (e) => {
    const newDsId = e.target.value;
    setSelectedDatasetId(newDsId);
    setSelectedVersionId('');
    navigate(`/datasets/${newDsId}/dashboard`);
  };

  // Handle Version change from selector
  const handleVersionChange = (e) => {
    const newVerId = e.target.value;
    setSelectedVersionId(newVerId);
    navigate(`/datasets/${selectedDatasetId}/versions/${newVerId}/dashboard`);
  };

  // Format timestamps nicely
  const formatTimestamp = (ts) => {
    if (!ts) return 'Not available';
    try {
      const d = new Date(ts);
      return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return ts;
    }
  };

  // Custom Recharts Tooltip
  const CustomTooltip = ({ active, payload, label, unit = '' }) => {
    if (active && payload && payload.length) {
      return (
        <div className="dq-chart-tooltip">
          {label && <div className="dq-chart-tooltip-label">{label}</div>}
          {payload.map((entry, index) => (
            <div key={`item-${index}`} className="dq-chart-tooltip-item" style={{ color: entry.color || '#f1f5f9' }}>
              <span>{entry.name || 'Value'}:</span>
              <span>{entry.value}{unit}</span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  // If no datasets exist at all
  if (!loading && datasetsList.length === 0 && !selectedDatasetId) {
    return (
      <div className="dq-dashboard">
        <div className="dq-card">
          <div className="dq-empty-state">
            <span className="dq-empty-icon">📁</span>
            <h3 className="dq-empty-title">No Datasets Available</h3>
            <p className="dq-empty-desc">
              Upload a dataset CSV or Excel file to automatically generate health, quality, risk, and anomaly profiles.
            </p>
            <Link to="/upload" className="dq-btn dq-btn-primary" style={{ marginTop: '1rem' }}>
              Upload Dataset
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // Loading Skeleton State
  if (loading && !dashboardData) {
    return (
      <div className="dq-dashboard">
        <div className="dq-header">
          <div className="dq-skeleton" style={{ height: '32px', width: '280px' }}></div>
          <div className="dq-skeleton" style={{ height: '24px', width: '450px' }}></div>
        </div>
        <div className="dq-health-card">
          <div className="dq-skeleton" style={{ height: '120px', width: '100%' }}></div>
          <div className="dq-skeleton" style={{ height: '120px', width: '100%' }}></div>
        </div>
        <div className="dq-grid-2">
          <div className="dq-card dq-skeleton" style={{ height: '280px' }}></div>
          <div className="dq-card dq-skeleton" style={{ height: '280px' }}></div>
        </div>
      </div>
    );
  }

  // Global Error State
  if (error && !dashboardData) {
    return (
      <div className="dq-dashboard">
        <div className="dq-error-box">
          <span>⚠️ {error}</span>
          <button className="dq-btn dq-btn-secondary" onClick={() => fetchDashboardData(false)}>
            Retry
          </button>
        </div>
      </div>
    );
  }

  const {
    dataset,
    version,
    all_versions = [],
    health = {},
    quality = {},
    risk = {},
    privacy = {},
    anomalies = {},
    issues = {},
    profiling = {},
    drift = {},
    trends = {},
    attention_columns = [],
    insights = [],
  } = dashboardData || {};

  const currentDatasetId = dataset?.id || selectedDatasetId;
  const currentVersionId = version?.id || selectedVersionId;
  const currentVersionNumber = version?.version_number || 1;

  // Colors for risk donut / charts
  const RISK_COLORS = {
    HIGH: '#ef4444',
    MEDIUM: '#f59e0b',
    LOW: '#10b981',
  };

  return (
    <div className="dq-dashboard">
      {/* =======================================================
          1. DASHBOARD HEADER & CONTEXT TOOLBAR
          ======================================================= */}
      <header className="dq-header">
        <div className="dq-header-top">
          <div className="dq-header-titles">
            <h1 className="dq-title">
              <span>🛡️</span> DataGuard AI Dashboard
            </h1>
            <p className="dq-subtitle">
              Comprehensive Health, Quality, Risk, Anomaly, and Drift Overview
            </p>
          </div>

          <div className="dq-header-actions">
            <button
              className="dq-btn dq-btn-secondary"
              onClick={() => fetchDashboardData(true)}
              disabled={refreshing}
              title="Refetch stored dashboard results without rerunning analysis"
            >
              <span>{refreshing ? '⏳' : '🔄'}</span>
              {refreshing ? 'Refreshing...' : 'Refresh'}
            </button>

            <Link
              to={`/datasets/${currentDatasetId}/compare`}
              className="dq-btn dq-btn-secondary"
            >
              <span>⚖️</span> Compare Versions
            </Link>

            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/issues`}
              className="dq-btn dq-btn-secondary"
            >
              <span>⚠️</span> View Issues
            </Link>

            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/assistant`}
              className="dq-btn dq-btn-primary"
            >
              <span>🤖</span> Ask AI Assistant
            </Link>
          </div>
        </div>

        <div className="dq-header-selectors">
          <div className="dq-selector-group">
            <label htmlFor="dq-select-dataset" className="dq-selector-label">Dataset:</label>
            <select
              id="dq-select-dataset"
              className="dq-select"
              value={currentDatasetId}
              onChange={handleDatasetChange}
            >
              {datasetsList.map((ds) => (
                <option key={ds.id} value={ds.id}>
                  {ds.name} ({ds.version_count || 1}v)
                </option>
              ))}
            </select>
          </div>

          <div className="dq-selector-group">
            <label htmlFor="dq-select-version" className="dq-selector-label">Version:</label>
            <select
              id="dq-select-version"
              className="dq-select"
              value={currentVersionId}
              onChange={handleVersionChange}
            >
              {all_versions.map((v) => (
                <option key={v.id} value={v.id}>
                  V{v.version_number} ({formatTimestamp(v.created_at)})
                </option>
              ))}
            </select>
          </div>

          <div className="dq-header-meta">
            <span>🕒 Last Analyzed:</span>
            <strong>{formatTimestamp(health.computed_at || version?.created_at)}</strong>
          </div>
        </div>
      </header>

      {/* =======================================================
          2. GROUNDED KEY INSIGHTS SUMMARY
          ======================================================= */}
      {insights && insights.length > 0 && (
        <section className="dq-insights-bar">
          <div className="dq-insights-title">
            <span>💡</span> Grounded Analytical Highlights
          </div>
          <div className="dq-insights-list">
            {insights.map((ins, idx) => (
              <span
                key={idx}
                className={`dq-insight-chip dq-insight-chip--${ins.severity || 'LOW'}`}
              >
                <strong>{ins.category}:</strong> {ins.message}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* =======================================================
          3. DATASET HEALTH OVERVIEW (PHASE 9)
          ======================================================= */}
      <section className="dq-health-card">
        <div className="dq-health-primary">
          <span className="dq-health-label">Dataset Holistic Health</span>
          {health.available && health.dataset_health_score !== null ? (
            <>
              <div className="dq-health-score-row">
                <span className="dq-health-score-val">{health.dataset_health_score}</span>
                <span className="dq-health-score-max">/ 100</span>
              </div>
              <span className={`dq-grade-badge dq-grade--${health.grade || 'UNKNOWN'}`}>
                {health.grade || 'UNKNOWN'}
              </span>
            </>
          ) : (
            <div className="dq-empty-state" style={{ padding: '0.5rem 0', alignItems: 'flex-start' }}>
              <span className="dq-pill dq-pill--NEUTRAL">NOT COMPUTED</span>
              <p style={{ fontSize: '0.82rem', marginTop: '0.4rem' }}>
                Run health evaluation in the Issues module to generate score.
              </p>
            </div>
          )}
        </div>

        <div className="dq-health-components">
          {/* Quality Health */}
          <div className="dq-comp-item">
            <div className="dq-comp-header">
              <span className="dq-comp-title">Data Quality</span>
              <span className="dq-comp-val">
                {health.available && health.quality_health !== null ? `${health.quality_health} / 100` : '—'}
              </span>
            </div>
            <div className="dq-progress-bg">
              <div
                className="dq-progress-fill dq-fill-quality"
                style={{ width: `${health.available ? health.quality_health || 0 : 0}%` }}
              ></div>
            </div>
          </div>

          {/* Risk Health */}
          <div className="dq-comp-item">
            <div className="dq-comp-header">
              <span className="dq-comp-title">Risk Health</span>
              <span className="dq-comp-val">
                {health.available && health.risk_health !== null ? `${health.risk_health} / 100` : '—'}
              </span>
            </div>
            <div className="dq-progress-bg">
              <div
                className="dq-progress-fill dq-fill-risk"
                style={{ width: `${health.available ? health.risk_health || 0 : 0}%` }}
              ></div>
            </div>
          </div>

          {/* Anomaly Health */}
          <div className="dq-comp-item">
            <div className="dq-comp-header">
              <span className="dq-comp-title">Anomaly Health</span>
              <span className="dq-comp-val">
                {health.available && health.anomaly_health !== null ? `${health.anomaly_health} / 100` : '—'}
              </span>
            </div>
            <div className="dq-progress-bg">
              <div
                className="dq-progress-fill dq-fill-anomaly"
                style={{ width: `${health.available ? health.anomaly_health || 0 : 0}%` }}
              ></div>
            </div>
          </div>

          {/* Privacy Health */}
          <div className="dq-comp-item">
            <div className="dq-comp-header">
              <span className="dq-comp-title">Privacy Health</span>
              <span className="dq-comp-val">
                {health.available && health.privacy_health !== null ? `${health.privacy_health} / 100` : '—'}
              </span>
            </div>
            <div className="dq-progress-bg">
              <div
                className="dq-progress-fill dq-fill-privacy"
                style={{ width: `${health.available ? health.privacy_health || 0 : 0}%` }}
              ></div>
            </div>
          </div>
        </div>
      </section>

      {/* =======================================================
          4. ROW: DATA QUALITY & PRIVACY EXPOSURE
          ======================================================= */}
      <div className="dq-grid-2">
        {/* Data Quality Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>✅</span> Data Quality
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/quality`}
              className="dq-card-action"
            >
              Explore Quality →
            </Link>
          </div>

          {!quality.available ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">📋</span>
              <span className="dq-empty-title">No Quality Rules Evaluated</span>
              <p className="dq-empty-desc">Run Great Expectations quality validation to populate rules.</p>
            </div>
          ) : quality.status === 'NOT_EVALUATED' || quality.total_rules_evaluated === 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <div className="dq-warning-banner">
                <span>ℹ️</span>
                <span>Quality validation has no evaluated rules for this dataset version.</span>
              </div>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{quality.quality_score ?? 100}</span>
                  <span className="dq-stat-box-lbl">Score</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-pill dq-pill--NEUTRAL">NOT EVALUATED</span>
                  <span className="dq-stat-box-lbl">Status</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">0</span>
                  <span className="dq-stat-box-lbl">Rules Evaluated</span>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{quality.quality_score}</span>
                  <span className="dq-stat-box-lbl">Quality Score</span>
                </div>
                <div className="dq-stat-box">
                  <span className={`dq-grade-badge dq-grade--${quality.grade || 'UNKNOWN'}`}>
                    {quality.grade}
                  </span>
                  <span className="dq-stat-box-lbl">Grade</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#10b981' }}>{quality.passed_rules}</span>
                  <span className="dq-stat-box-lbl">Passed</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: quality.failed_rules > 0 ? '#ef4444' : '#10b981' }}>
                    {quality.failed_rules}
                  </span>
                  <span className="dq-stat-box-lbl">Failed</span>
                </div>
              </div>

              {quality.failed_expectations && quality.failed_expectations.length > 0 ? (
                <div className="dq-table-container">
                  <table className="dq-table">
                    <thead>
                      <tr>
                        <th>Rule</th>
                        <th>Column</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {quality.failed_expectations.slice(0, 5).map((rule, idx) => (
                        <tr key={idx}>
                          <td title={rule.rule_name}>{rule.rule_name.replace('expect_', '')}</td>
                          <td className="dq-col-name">{rule.column_name || 'Dataset'}</td>
                          <td>
                            <span className="dq-pill dq-pill--FAILED">Failed</span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="dq-info-banner">
                  <span>✨</span>
                  <span>All {quality.total_rules_evaluated} evaluated quality expectations passed successfully.</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Privacy & PII Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>🔒</span> Privacy & PII Exposure
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/pii`}
              className="dq-card-action"
            >
              Explore PII →
            </Link>
          </div>

          {!privacy.available ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">🛡️</span>
              <span className="dq-empty-title">No PII Scan Performed</span>
              <p className="dq-empty-desc">Execute PII detection to inspect sensitive entities.</p>
            </div>
          ) : privacy.pii_columns_count === 0 ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">✨</span>
              <span className="dq-empty-title">No PII Findings Detected</span>
              <p className="dq-empty-desc">No sensitive personal identifiable information found in inspected columns.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{privacy.pii_columns_count}</span>
                  <span className="dq-stat-box-lbl">PII Columns</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{privacy.total_findings_count}</span>
                  <span className="dq-stat-box-lbl">Total Findings</span>
                </div>
                <div className="dq-stat-box">
                  <span className={`dq-pill dq-pill--${privacy.highest_severity || 'LOW'}`}>
                    {privacy.highest_severity}
                  </span>
                  <span className="dq-stat-box-lbl">Highest Risk</span>
                </div>
              </div>

              {privacy.detected_categories && privacy.detected_categories.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                  {privacy.detected_categories.map((cat, idx) => (
                    <span key={idx} className={`dq-pill dq-pill--${cat.severity}`}>
                      {cat.category} ({cat.count})
                    </span>
                  ))}
                </div>
              )}

              {privacy.columns && privacy.columns.length > 0 && (
                <div className="dq-table-container">
                  <table className="dq-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Detected Entities</th>
                        <th>Severity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {privacy.columns.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="dq-col-name">{col.column_name}</td>
                          <td>{col.entity_types.join(', ') || 'Sensitive Data'}</td>
                          <td>
                            <span className={`dq-pill dq-pill--${col.highest_severity}`}>
                              {col.highest_severity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          5. ROW: COLUMN RISK & ANOMALIES
          ======================================================= */}
      <div className="dq-grid-2">
        {/* Column Risk Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>⚖️</span> Column Risk Classification
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/risk`}
              className="dq-card-action"
            >
              Explore Risk →
            </Link>
          </div>

          {!risk.available ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">🎯</span>
              <span className="dq-empty-title">No Risk Predictions</span>
              <p className="dq-empty-desc">Run ML risk classification to predict domain and vulnerability.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{risk.columns_analyzed}</span>
                  <span className="dq-stat-box-lbl">Analyzed</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#ef4444' }}>{risk.high_count}</span>
                  <span className="dq-stat-box-lbl">High</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#f59e0b' }}>{risk.medium_count}</span>
                  <span className="dq-stat-box-lbl">Medium</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#10b981' }}>{risk.low_count}</span>
                  <span className="dq-stat-box-lbl">Low</span>
                </div>
              </div>

              {risk.column_risks && risk.column_risks.length > 0 && (
                <div className="dq-table-container">
                  <table className="dq-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Predicted Domain</th>
                        <th>Risk</th>
                        <th style={{ textAlign: 'right' }}>Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risk.column_risks.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="dq-col-name">{col.column_name}</td>
                          <td>{col.domain || 'General'}</td>
                          <td>
                            <span className={`dq-pill dq-pill--${col.risk_level}`}>
                              {col.risk_level}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{col.risk_score}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Anomaly Detection Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>📉</span> Potential Anomalies & Outliers
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/anomalies`}
              className="dq-card-action"
            >
              Explore Anomalies →
            </Link>
          </div>

          {!anomalies.available ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">📊</span>
              <span className="dq-empty-title">No Anomaly Detection Results</span>
              <p className="dq-empty-desc">Run IQR, Z-Score, and Isolation Forest detectors to identify outliers.</p>
            </div>
          ) : anomalies.anomalous_columns_count === 0 ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">✨</span>
              <span className="dq-empty-title">No Anomalies Detected</span>
              <p className="dq-empty-desc">No statistically unusual observations detected across analyzed columns.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{anomalies.anomalous_columns_count}</span>
                  <span className="dq-stat-box-lbl">Anomalous Cols</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{anomalies.total_anomalies_count}</span>
                  <span className="dq-stat-box-lbl">Outliers</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{anomalies.dataset_anomaly_score ?? 0}</span>
                  <span className="dq-stat-box-lbl">Anomaly Score</span>
                </div>
              </div>

              {anomalies.anomalous_columns && anomalies.anomalous_columns.length > 0 && (
                <div className="dq-table-container">
                  <table className="dq-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Detector</th>
                        <th>Severity</th>
                        <th style={{ textAlign: 'right' }}>Outlier %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {anomalies.anomalous_columns.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="dq-col-name">{col.column_name}</td>
                          <td>{col.detector_method}</td>
                          <td>
                            <span className={`dq-pill dq-pill--${col.severity}`}>
                              {col.severity}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right', fontWeight: 600 }}>{col.anomaly_rate}%</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          6. ROW: PRIORITIZED ISSUES & PROFILING / MISSINGNESS
          ======================================================= */}
      <div className="dq-grid-2">
        {/* Prioritized Issues Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>🚨</span> Highest-Priority Issues
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/issues`}
              className="dq-card-action"
            >
              View All Issues ({issues.total_issues || 0}) →
            </Link>
          </div>

          {!issues.available || issues.total_issues === 0 ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">🎉</span>
              <span className="dq-empty-title">No Prioritized Issues</span>
              <p className="dq-empty-desc">No active data quality or risk issues flagged for this version snapshot.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{issues.total_issues}</span>
                  <span className="dq-stat-box-lbl">Total Issues</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#ef4444' }}>{issues.high_priority_count}</span>
                  <span className="dq-stat-box-lbl">Critical / High</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num" style={{ color: '#f59e0b' }}>{issues.medium_priority_count}</span>
                  <span className="dq-stat-box-lbl">Medium</span>
                </div>
              </div>

              <div className="dq-table-container">
                <table className="dq-table">
                  <thead>
                    <tr>
                      <th>Issue</th>
                      <th>Severity</th>
                      <th style={{ textAlign: 'right' }}>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {issues.prioritized_issues.slice(0, 5).map((iss, idx) => (
                      <tr key={idx}>
                        <td>
                          <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{iss.title}</div>
                          {iss.affected_columns && iss.affected_columns.length > 0 && (
                            <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                              Cols: {iss.affected_columns.join(', ')}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className={`dq-pill dq-pill--${iss.severity}`}>
                            {iss.severity}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right', fontWeight: 700, color: 'var(--accent-hover)' }}>
                          {iss.priority_score}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>

        {/* Profiling & Missingness Card */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>📊</span> Statistical Profiling & Missingness
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/profile`}
              className="dq-card-action"
            >
              Explore Profile →
            </Link>
          </div>

          {!profiling.available ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">📈</span>
              <span className="dq-empty-title">No Profiling Data Available</span>
              <p className="dq-empty-desc">Generate profile to calculate column statistics and missingness.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{profiling.row_count?.toLocaleString()}</span>
                  <span className="dq-stat-box-lbl">Rows</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{profiling.column_count}</span>
                  <span className="dq-stat-box-lbl">Columns</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{profiling.missing_percentage}%</span>
                  <span className="dq-stat-box-lbl">Missing Cells</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{profiling.duplicate_rows}</span>
                  <span className="dq-stat-box-lbl">Duplicates</span>
                </div>
              </div>

              {profiling.top_missing_columns && profiling.top_missing_columns.length > 0 ? (
                <div>
                  <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)', marginBottom: '0.4rem', fontWeight: 600 }}>
                    TOP COLUMNS WITH MISSING DATA:
                  </div>
                  <div style={{ height: 160, width: '100%' }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={profiling.top_missing_columns.slice(0, 6)}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                      >
                        <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" horizontal={false} />
                        <XAxis type="number" domain={[0, 100]} unit="%" stroke="var(--text-muted)" fontSize={11} />
                        <YAxis dataKey="column_name" type="category" stroke="var(--text-secondary)" fontSize={11} width={80} />
                        <Tooltip content={<CustomTooltip unit="%" />} />
                        <Bar dataKey="missing_percentage" name="Missing %" fill="#f59e0b" radius={[0, 4, 4, 0]} />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="dq-info-banner">
                  <span>✨</span>
                  <span>Zero missing values detected across all columns.</span>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          7. ROW: VERSION DRIFT & HISTORICAL TRENDS
          ======================================================= */}
      <div className="dq-grid-2">
        {/* Version Comparison & Drift */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>🔄</span> Version Comparison & Drift
            </h3>
            <Link
              to={`/datasets/${currentDatasetId}/compare`}
              className="dq-card-action"
            >
              Compare Tool →
            </Link>
          </div>

          {!drift.has_comparison ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">🔀</span>
              <span className="dq-empty-title">No Version Comparison Available</span>
              <p className="dq-empty-desc">
                Compare this version against a previous baseline to track drift and schema shifts.
              </p>
              <Link
                to={`/datasets/${currentDatasetId}/compare`}
                className="dq-btn dq-btn-secondary"
                style={{ marginTop: '0.6rem' }}
              >
                Compare Versions
              </Link>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <div className="dq-stat-banner">
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">V{drift.baseline_version_number} → V{drift.current_version_number}</span>
                  <span className="dq-stat-box-lbl">Compared Versions</span>
                </div>
                <div className="dq-stat-box">
                  <span className={`dq-pill dq-pill--${drift.overall_drift_severity || 'LOW'}`}>
                    {drift.overall_drift_severity}
                  </span>
                  <span className="dq-stat-box-lbl">Overall Drift</span>
                </div>
                <div className="dq-stat-box">
                  <span className="dq-stat-box-num">{drift.drifted_columns_count}</span>
                  <span className="dq-stat-box-lbl">Drifted Columns</span>
                </div>
              </div>

              {drift.column_drifts && drift.column_drifts.length > 0 ? (
                <div className="dq-table-container">
                  <table className="dq-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Drift Type</th>
                        <th>Severity</th>
                      </tr>
                    </thead>
                    <tbody>
                      {drift.column_drifts.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="dq-col-name">{col.column_name}</td>
                          <td>{col.drift_type}</td>
                          <td>
                            <span className={`dq-pill dq-pill--${col.severity}`}>
                              {col.severity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="dq-info-banner">
                  <span>✨</span>
                  <span>No column-level drift detected against baseline.</span>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Historical Version Health Trend */}
        <div className="dq-card">
          <div className="dq-card-header">
            <h3 className="dq-card-title">
              <span>📈</span> Dataset Health Trend
            </h3>
            <span className="dq-card-action" style={{ cursor: 'default' }}>
              {trends.versions?.length || 0} Versions Logged
            </span>
          </div>

          {!trends.has_sufficient_history ? (
            <div className="dq-empty-state">
              <span className="dq-empty-icon">📉</span>
              <span className="dq-empty-title">Not Enough Version History</span>
              <p className="dq-empty-desc">
                Upload and analyze at least two dataset versions to unlock chronological trend analytics.
              </p>
            </div>
          ) : (
            <div style={{ height: 230, width: '100%', marginTop: '0.5rem' }}>
              <ResponsiveContainer width="100%" height="100%">
                <LineChart
                  data={trends.versions.map((v) => ({
                    name: `V${v.version_number}`,
                    Health: v.dataset_health,
                    Quality: v.quality_health,
                    Risk: v.risk_health,
                    Privacy: v.privacy_health,
                  }))}
                  margin={{ top: 10, right: 20, left: 0, bottom: 5 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                  <XAxis dataKey="name" stroke="var(--text-muted)" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="var(--text-muted)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend wrapperStyle={{ fontSize: '0.78rem', paddingTop: '8px' }} />
                  <Line type="monotone" dataKey="Health" stroke="#6366f1" strokeWidth={3} dot={{ r: 4 }} />
                  <Line type="monotone" dataKey="Quality" stroke="#3b82f6" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="Risk" stroke="#f59e0b" strokeWidth={2} dot={{ r: 3 }} />
                  <Line type="monotone" dataKey="Privacy" stroke="#10b981" strokeWidth={2} dot={{ r: 3 }} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          8. ROW: COLUMNS REQUIRING ATTENTION (CROSS-SIGNAL MATRIX)
          ======================================================= */}
      <section className="dq-card">
        <div className="dq-card-header">
          <h3 className="dq-card-title">
            <span>🎯</span> Columns Requiring Attention (Cross-Signal Synthesis)
          </h3>
          <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            Synthesized across Risk, Quality, Anomalies, and PII
          </span>
        </div>

        {attention_columns && attention_columns.length > 0 ? (
          <div className="dq-table-container">
            <table className="dq-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Risk Level</th>
                  <th>Quality Status</th>
                  <th>Anomaly Severity</th>
                  <th>PII Severity</th>
                  <th style={{ textAlign: 'right' }}>Active Issues</th>
                </tr>
              </thead>
              <tbody>
                {attention_columns.map((col, idx) => (
                  <tr key={idx}>
                    <td className="dq-col-name">{col.column_name}</td>
                    <td>
                      {col.risk_level ? (
                        <span className={`dq-pill dq-pill--${col.risk_level}`}>
                          {col.risk_level}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>
                      {col.quality_status ? (
                        <span className="dq-pill dq-pill--FAILED">
                          {col.quality_status}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>
                      {col.anomaly_severity ? (
                        <span className={`dq-pill dq-pill--${col.anomaly_severity}`}>
                          {col.anomaly_severity}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td>
                      {col.pii_severity ? (
                        <span className={`dq-pill dq-pill--${col.pii_severity}`}>
                          {col.pii_severity}
                        </span>
                      ) : (
                        <span style={{ color: 'var(--text-muted)' }}>—</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right', fontWeight: 700, color: col.issue_count > 0 ? 'var(--accent-hover)' : 'var(--text-muted)' }}>
                      {col.issue_count > 0 ? col.issue_count : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="dq-empty-state">
            <span className="dq-empty-icon">✨</span>
            <span className="dq-empty-title">No High-Risk Columns Flagged</span>
            <p className="dq-empty-desc">No columns currently exhibit elevated risk, quality failures, or anomalies.</p>
          </div>
        )}
      </section>
    </div>
  );
}
