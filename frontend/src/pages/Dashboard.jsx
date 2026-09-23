/**
 * DataGuard AI — Phase 13 Data Quality Dashboard
 *
 * Polished enterprise presentation layer synthesizing Phase 4-10 stored analytical results.
 * Strictly read-only: does not recalculate analytics or expose raw PII / raw dataset cells.
 *
 * Redesigned to match the DATA GUARD AI workspace aesthetic.
 * NO API CHANGES: still calls getDashboard() / getDatasets() exactly as before.
 */

import { useState, useEffect, useCallback } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  LineChart,
  Line,
  CartesianGrid,
  Legend,
} from "recharts";

import { getDashboard, getDatasets } from "../api/client";
import "./Dashboard.css";
import { useAuth } from "../context/AuthContext";

export default function Dashboard() {
  const { datasetId: routeDatasetId, versionId: routeVersionId } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated, loading: authLoading } = useAuth();

  const [datasetsList, setDatasetsList] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(
    routeDatasetId || "",
  );
  const [selectedVersionId, setSelectedVersionId] = useState(
    routeVersionId || "",
  );

  const [dashboardData, setDashboardData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Set document title
  useEffect(() => {
    const titleEl = document.getElementById("page-title");
    if (titleEl) {
      titleEl.textContent = "Data Quality Dashboard";
    }
  }, []);

  // Fetch available datasets
  useEffect(() => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }

    async function loadDatasetOptions() {
      try {
        const list = await getDatasets();
        setDatasetsList(list || []);
        if (!routeDatasetId && list && list.length > 0) {
          setSelectedDatasetId(list[0].id);
          navigate(`/datasets/${list[0].id}/dashboard`, { replace: true });
        }
      } catch (err) {
        console.error("Failed to load dataset list:", err);
      }
    }
    loadDatasetOptions();
  }, [routeDatasetId, navigate, isAuthenticated]);

  // Sync route params with state
  useEffect(() => {
    if (routeDatasetId) {
      setSelectedDatasetId(routeDatasetId);
    }
    if (routeVersionId) {
      setSelectedVersionId(routeVersionId);
    }
  }, [routeDatasetId, routeVersionId]);

  // Main fetch (read-only)
  const fetchDashboardData = useCallback(
    async (isManualRefresh = false) => {
      if (!selectedDatasetId) return;

      if (isManualRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      setError(null);

      try {
        const data = await getDashboard(
          selectedDatasetId,
          selectedVersionId || null,
        );
        setDashboardData(data);
        if (data && data.version && !selectedVersionId) {
          setSelectedVersionId(data.version.id);
        }
      } catch (err) {
        console.error("Failed to load dashboard data:", err);
        setError(err.message || "Unable to load dataset dashboard data.");
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [selectedDatasetId, selectedVersionId],
  );

  useEffect(() => {
    if (selectedDatasetId) {
      fetchDashboardData(false);
    }
  }, [selectedDatasetId, selectedVersionId, fetchDashboardData]);

  // Auto-refresh while PII is pending (unchanged logic)
  useEffect(() => {
    if (!dashboardData) return;
    if (dashboardData.privacy?.available) return;
    if (!selectedDatasetId || !selectedVersionId) return;

    const iv = setInterval(() => {
      fetchDashboardData(true);
    }, 10000);

    const stop = setTimeout(() => clearInterval(iv), 3 * 60 * 1000);

    return () => {
      clearInterval(iv);
      clearTimeout(stop);
    };
  }, [
    dashboardData?.privacy?.available,
    selectedDatasetId,
    selectedVersionId,
    fetchDashboardData,
  ]);

  const handleDatasetChange = (e) => {
    const newDsId = e.target.value;
    setSelectedDatasetId(newDsId);
    setSelectedVersionId("");
    navigate(`/datasets/${newDsId}/dashboard`);
  };

  const handleVersionChange = (e) => {
    const newVerId = e.target.value;
    setSelectedVersionId(newVerId);
    navigate(`/datasets/${selectedDatasetId}/versions/${newVerId}/dashboard`);
  };

  const formatTimestamp = (ts) => {
    if (!ts) return "Not available";
    try {
      const d = new Date(ts);
      return (
        d.toLocaleDateString() +
        " " +
        d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
      );
    } catch {
      return ts;
    }
  };

  const CustomTooltip = ({ active, payload, label, unit = "" }) => {
    if (active && payload && payload.length) {
      return (
        <div className="dash-tooltip">
          {label && <div className="dash-tooltip-label">{label}</div>}
          {payload.map((entry, index) => (
            <div
              key={`item-${index}`}
              className="dash-tooltip-item"
              style={{ color: entry.color || "#f1f5f9" }}
            >
              <span>{entry.name || "Value"}:</span>
              <span>
                {entry.value}
                {unit}
              </span>
            </div>
          ))}
        </div>
      );
    }
    return null;
  };

  // ---------- Empty dataset list state ----------
  if (!loading && datasetsList.length === 0 && !selectedDatasetId) {
    return (
      <div className="dash-page">
        <div className="dash-panel">
          <div className="dash-empty">
            <span className="dash-empty-icon">📁</span>
            <h3 className="dash-empty-title">No Datasets Available</h3>
            <p className="dash-empty-desc">
              Upload a dataset CSV or Excel file to automatically generate
              health, quality, risk, and anomaly profiles.
            </p>
            <Link to="/upload" className="btn--primary" style={{ marginTop: "1rem" }}>
              Upload Dataset
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ---------- Anonymous user state ----------
  if (!authLoading && !isAuthenticated) {
    return (
      <div className="dash-page">
        <header className="dash-hero">
          <div>
            <small>DATA QUALITY WORKSPACE</small>
            <h1>🛡️ DataGuard AI Dashboard</h1>
            <p>Comprehensive Health, Quality, Risk, Anomaly, and Drift Overview</p>
          </div>
        </header>

        <div className="dash-panel">
          <div className="dash-empty" style={{ minHeight: "300px" }}>
            <span className="dash-empty-icon" style={{ fontSize: "3rem" }}>🔒</span>
            <h3 className="dash-empty-title" style={{ fontSize: "1.3rem" }}>
              Sign in to view your dashboard
            </h3>
            <p className="dash-empty-desc" style={{ maxWidth: "420px" }}>
              DataGuard AI profiles, validates, and secures each user's datasets
              privately. Sign in to see your own health, quality, privacy, and
              drift analytics.
            </p>
            <div className="dash-actions-row" style={{ marginTop: "1.5rem" }}>
              <Link to="/login" className="btn--primary">Sign In</Link>
              <Link to="/register" className="btn--secondary">Create Account</Link>
            </div>
          </div>
        </div>

        <div className="dash-grid-2">
          {[
            { icon: "📊", title: "Data Quality" },
            { icon: "🔒", title: "Privacy & PII Exposure" },
            { icon: "⚖️", title: "Column Risk Classification" },
            { icon: "📉", title: "Anomalies & Outliers" },
          ].map((item) => (
            <div className="dash-panel" key={item.title}>
              <div className="dash-panel-head">
                <h3>{item.icon} {item.title}</h3>
              </div>
              <div className="dash-empty">
                <span className="dash-empty-icon">🔒</span>
                <span className="dash-empty-title">Sign in to see your results</span>
              </div>
            </div>
          ))}
        </div>

        <div className="dash-panel" style={{ marginTop: "1rem" }}>
          <div className="dash-empty">
            <span className="dash-empty-icon">🧠</span>
            <span className="dash-empty-title">AI Assistant & RAG Search</span>
            <p className="dash-empty-desc">
              Ask grounded questions about your datasets. Sign in to start a chat.
            </p>
            <div className="dash-actions-row" style={{ marginTop: "1.25rem" }}>
              <Link to="/login" className="btn--primary">💬 Sign in to chat</Link>
              <Link to="/" className="btn--secondary">Back to Home</Link>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---------- Loading skeleton ----------
  if (loading && !dashboardData) {
    return (
      <div className="dash-page">
        <div className="dash-hero">
          <div className="dash-skeleton" style={{ height: 32, width: 280 }} />
          <div className="dash-skeleton" style={{ height: 24, width: 450 }} />
        </div>
        <div className="dash-health-card">
          <div className="dash-skeleton" style={{ height: 120, width: "100%" }} />
          <div className="dash-skeleton" style={{ height: 120, width: "100%" }} />
        </div>
        <div className="dash-grid-2">
          <div className="dash-panel dash-skeleton" style={{ height: 280 }} />
          <div className="dash-panel dash-skeleton" style={{ height: 280 }} />
        </div>
      </div>
    );
  }

  // ---------- Error state ----------
  if (error && !dashboardData) {
    return (
      <div className="dash-page">
        <div className="dash-error">
          <span>⚠️ {error}</span>
          <button
            className="btn--secondary"
            onClick={() => fetchDashboardData(false)}
          >
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

  // ---- Real-derived quality KPI values (option a) ----
  const passRate =
    quality.total_rules_evaluated > 0
      ? Math.round(
          (quality.passed_rules / quality.total_rules_evaluated) * 100,
        )
      : 100;

  return (
    <div className="dash-page">
      {/* =======================================================
          1. HERO / TOOLBAR
          ======================================================= */}
      <header className="dash-hero">
        <div className="dash-hero-titles">
          <small>DATA QUALITY WORKSPACE</small>
          <h1>
            <span>🛡️</span> DataGuard AI Dashboard
          </h1>
          <p>Comprehensive Health, Quality, Risk, Anomaly, and Drift Overview</p>
        </div>

        <div className="dash-hero-actions">
          <button
            className="btn--secondary"
            onClick={() => fetchDashboardData(true)}
            disabled={refreshing}
            title="Refetch stored dashboard results"
          >
            {refreshing ? "⏳ Refreshing…" : "🔄 Refresh"}
          </button>

          <Link
            to={`/datasets/${currentDatasetId}/compare`}
            className="btn--secondary"
          >
            ⚖️ Compare
          </Link>

          <Link
            to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/issues`}
            className="btn--secondary"
          >
            ⚠️ Issues
          </Link>

          <Link
            to={`/datasets/${currentDatasetId}/chat?scope=VERSION&versionId=${currentVersionId}`}
            className="btn--primary"
          >
            💬 AI Chat
          </Link>
        </div>
      </header>

      {/* Selector bar */}
      <div className="dash-selector-bar">
        <label className="dash-selector">
          <span>Dataset</span>
          <select value={currentDatasetId} onChange={handleDatasetChange}>
            {datasetsList.map((ds) => (
              <option key={ds.id} value={ds.id}>
                {ds.name} ({ds.version_count || 1}v)
              </option>
            ))}
          </select>
        </label>

        <label className="dash-selector">
          <span>Version</span>
          <select value={currentVersionId} onChange={handleVersionChange}>
            {all_versions.map((v) => (
              <option key={v.id} value={v.id}>
                V{v.version_number} ({formatTimestamp(v.created_at)})
              </option>
            ))}
          </select>
        </label>

        <div className="dash-hero-meta">
          🕒 Last Analyzed:{" "}
          <strong>{formatTimestamp(health.computed_at || version?.created_at)}</strong>
        </div>
      </div>

      {/* =======================================================
          2. GROUNDED INSIGHTS
          ======================================================= */}
      {insights.length > 0 && (
        <section className="dash-insights">
          <div className="dash-insights-title">💡 Grounded Analytical Highlights</div>
          <div className="dash-insights-list">
            {insights.map((ins, idx) => (
              <span
                key={idx}
                className={`dash-insight dash-insight--${ins.severity || "LOW"}`}
              >
                <strong>{ins.category}:</strong> {ins.message}
              </span>
            ))}
          </div>
        </section>
      )}

      {/* =======================================================
          3. HEALTH OVERVIEW
          ======================================================= */}
      <section className="dash-health-card">
        <div className="dash-health-primary">
          <span className="dash-health-label">Dataset Holistic Health</span>
          {health.available && health.dataset_health_score !== null ? (
            <>
              <div className="dash-donut dash-donut--health">
                <div>
                  <strong>{health.dataset_health_score}</strong>
                  <small>/ 100</small>
                </div>
              </div>
              <span
                className={`dash-grade dash-grade--${health.grade || "UNKNOWN"}`}
              >
                {health.grade || "UNKNOWN"}
              </span>
            </>
          ) : (
            <div className="dash-empty dash-empty--inline">
              <span className="dash-pill dash-pill--NEUTRAL">NOT COMPUTED</span>
              <p className="dash-empty-desc">
                Run health evaluation in the Issues module to generate score.
              </p>
            </div>
          )}
        </div>

        <div className="dash-health-components">
          <ComponentBar
            title="Data Quality"
            value={health.available ? health.quality_health : null}
            tone="quality"
          />
          <ComponentBar
            title="Risk Health"
            value={health.available ? health.risk_health : null}
            tone="risk"
          />
          <ComponentBar
            title="Anomaly Health"
            value={health.available ? health.anomaly_health : null}
            tone="anomaly"
          />
          <ComponentBar
            title="Privacy Health"
            value={health.available ? health.privacy_health : null}
            tone="privacy"
          />
        </div>
      </section>

      {/* =======================================================
          4. QUALITY + PRIVACY ROW
          ======================================================= */}
      <div className="dash-grid-2">
        {/* Quality card */}
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>✅ Data Quality</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/quality`}
            >
              Explore Quality →
            </Link>
          </div>

          {!quality.available ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">📋</span>
              <span className="dash-empty-title">No Quality Rules Evaluated</span>
              <p className="dash-empty-desc">
                Run Great Expectations quality validation to populate rules.
              </p>
            </div>
          ) : quality.status === "NOT_EVALUATED" ||
            quality.total_rules_evaluated === 0 ? (
            <>
              <div className="dash-info">
                ℹ️ Quality validation has no evaluated rules for this version.
              </div>
              <div className="dash-kpi-grid">
                <Kpi label="Score" value={quality.quality_score ?? 100} />
                <Kpi label="Status" value="NOT EVALUATED" muted />
                <Kpi label="Rules Evaluated" value={0} />
              </div>
            </>
          ) : (
            <>
              {/* Real quality KPIs (option a) */}
              <div className="dash-kpi-grid">
                <Kpi
                  label="Quality Score"
                  value={quality.quality_score}
                  tone={
                    quality.quality_score >= 90
                      ? "success"
                      : quality.quality_score >= 75
                      ? "info"
                      : "warning"
                  }
                />
                <Kpi label="Grade" value={quality.grade} tone="info" />
                <Kpi
                  label="Pass Rate"
                  value={`${passRate}%`}
                  tone={passRate >= 90 ? "success" : "warning"}
                />
                <Kpi
                  label="Passed"
                  value={quality.passed_rules}
                  tone="success"
                />
                <Kpi
                  label="Failed"
                  value={quality.failed_rules}
                  tone={quality.failed_rules > 0 ? "danger" : "success"}
                />
                <Kpi label="Total Rules" value={quality.total_rules_evaluated} />
              </div>

              {quality.failed_expectations &&
              quality.failed_expectations.length > 0 ? (
                <div className="dash-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Rule</th>
                        <th>Column</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {quality.failed_expectations
                        .slice(0, 5)
                        .map((rule, idx) => (
                          <tr key={idx}>
                            <td title={rule.rule_name}>
                              {rule.rule_name.replace("expect_", "")}
                            </td>
                            <td className="column-name-code">
                              {rule.column_name || "Dataset"}
                            </td>
                            <td>
                              <span className="dash-pill dash-pill--FAILED">
                                Failed
                              </span>
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="dash-info dash-info--success">
                  ✨ All {quality.total_rules_evaluated} evaluated quality
                  expectations passed successfully.
                </div>
              )}
            </>
          )}
        </div>

        {/* Privacy card */}
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>🔒 Privacy & PII Exposure</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/pii`}
            >
              Explore PII →
            </Link>
          </div>

          {!privacy.available ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">🛡️</span>
              <span className="dash-empty-title">PII Scan Not Run Yet</span>
              <p className="dash-empty-desc">
                PII detection uses deep NLP. Typical scans complete in under 20
                seconds.
              </p>
              <div className="dash-actions-row" style={{ marginTop: "1rem" }}>
                <Link
                  to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/pii`}
                  className="btn--primary"
                >
                  🔐 Run PII Scan Now
                </Link>
                <button
                  type="button"
                  className="btn--secondary"
                  onClick={() => fetchDashboardData(true)}
                >
                  🔄 Refresh
                </button>
              </div>
            </div>
          ) : privacy.pii_columns_count === 0 ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">✨</span>
              <span className="dash-empty-title">No PII Findings Detected</span>
              <p className="dash-empty-desc">
                No sensitive personal identifiable information found in
                inspected columns.
              </p>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi label="PII Columns" value={privacy.pii_columns_count} tone="info" />
                <Kpi label="Total Findings" value={privacy.total_findings_count} />
                <Kpi
                  label="Highest Risk"
                  value={privacy.highest_severity}
                  tone={
                    privacy.highest_severity === "HIGH"
                      ? "danger"
                      : privacy.highest_severity === "MEDIUM"
                      ? "warning"
                      : "success"
                  }
                />
              </div>

              {privacy.detected_categories?.length > 0 && (
                <div className="dash-pill-row">
                  {privacy.detected_categories.map((cat, idx) => (
                    <span key={idx} className={`dash-pill dash-pill--${cat.severity}`}>
                      {cat.category} ({cat.count})
                    </span>
                  ))}
                </div>
              )}

              {privacy.columns?.length > 0 && (
                <div className="dash-table-wrap">
                  <table className="data-table">
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
                          <td className="column-name-code">{col.column_name}</td>
                          <td>{col.entity_types.join(", ") || "Sensitive Data"}</td>
                          <td>
                            <span
                              className={`dash-pill dash-pill--${col.highest_severity}`}
                            >
                              {col.highest_severity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* =======================================================
          5. RISK + ANOMALIES ROW
          ======================================================= */}
      <div className="dash-grid-2">
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>⚖️ Column Risk Classification</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/risk`}
            >
              Explore Risk →
            </Link>
          </div>

          {!risk.available ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">🎯</span>
              <span className="dash-empty-title">No Risk Predictions</span>
              <p className="dash-empty-desc">
                Run ML risk classification to predict domain and vulnerability.
              </p>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi label="Analyzed" value={risk.columns_analyzed} />
                <Kpi label="High" value={risk.high_count} tone="danger" />
                <Kpi label="Medium" value={risk.medium_count} tone="warning" />
                <Kpi label="Low" value={risk.low_count} tone="success" />
              </div>

              {risk.column_risks?.length > 0 && (
                <div className="dash-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Domain</th>
                        <th>Risk</th>
                        <th style={{ textAlign: "right" }}>Score</th>
                      </tr>
                    </thead>
                    <tbody>
                      {risk.column_risks.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="column-name-code">{col.column_name}</td>
                          <td>{col.domain || "General"}</td>
                          <td>
                            <span
                              className={`dash-pill dash-pill--${col.risk_level}`}
                            >
                              {col.risk_level}
                            </span>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {col.risk_score}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>

        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>📉 Potential Anomalies & Outliers</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/anomalies`}
            >
              Explore Anomalies →
            </Link>
          </div>

          {!anomalies.available ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">📊</span>
              <span className="dash-empty-title">No Anomaly Detection Results</span>
              <p className="dash-empty-desc">
                Run IQR, Z-Score, and Isolation Forest detectors to identify
                outliers.
              </p>
            </div>
          ) : anomalies.anomalous_columns_count === 0 ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">✨</span>
              <span className="dash-empty-title">No Anomalies Detected</span>
              <p className="dash-empty-desc">
                No statistically unusual observations detected across analyzed
                columns.
              </p>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi label="Anomalous Cols" value={anomalies.anomalous_columns_count} />
                <Kpi label="Outliers" value={anomalies.total_anomalies_count} />
                <Kpi
                  label="Anomaly Score"
                  value={anomalies.dataset_anomaly_score ?? 0}
                />
              </div>

              {anomalies.anomalous_columns?.length > 0 && (
                <div className="dash-table-wrap">
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>Column</th>
                        <th>Detector</th>
                        <th>Severity</th>
                        <th style={{ textAlign: "right" }}>Outlier %</th>
                      </tr>
                    </thead>
                    <tbody>
                      {anomalies.anomalous_columns.slice(0, 5).map((col, idx) => (
                        <tr key={idx}>
                          <td className="column-name-code">{col.column_name}</td>
                          <td>{col.detector_method}</td>
                          <td>
                            <span
                              className={`dash-pill dash-pill--${col.severity}`}
                            >
                              {col.severity}
                            </span>
                          </td>
                          <td style={{ textAlign: "right", fontWeight: 600 }}>
                            {col.anomaly_rate}%
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* =======================================================
          6. ISSUES + PROFILING ROW
          ======================================================= */}
      <div className="dash-grid-2">
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>🚨 Highest-Priority Issues</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/issues`}
            >
              View All Issues ({issues.total_issues || 0}) →
            </Link>
          </div>

          {!issues.available || issues.total_issues === 0 ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">🎉</span>
              <span className="dash-empty-title">No Prioritized Issues</span>
              <p className="dash-empty-desc">
                No active data quality or risk issues flagged for this version.
              </p>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi label="Total Issues" value={issues.total_issues} />
                <Kpi
                  label="Critical / High"
                  value={issues.high_priority_count}
                  tone="danger"
                />
                <Kpi
                  label="Medium"
                  value={issues.medium_priority_count}
                  tone="warning"
                />
              </div>

              <div className="dash-table-wrap">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>Issue</th>
                      <th>Severity</th>
                      <th style={{ textAlign: "right" }}>Priority</th>
                    </tr>
                  </thead>
                  <tbody>
                    {issues.prioritized_issues.slice(0, 5).map((iss, idx) => (
                      <tr key={idx}>
                        <td>
                          <div style={{ fontWeight: 600 }}>{iss.title}</div>
                          {iss.affected_columns?.length > 0 && (
                            <div className="dash-subtext">
                              Cols: {iss.affected_columns.join(", ")}
                            </div>
                          )}
                        </td>
                        <td>
                          <span className={`dash-pill dash-pill--${iss.severity}`}>
                            {iss.severity}
                          </span>
                        </td>
                        <td
                          style={{
                            textAlign: "right",
                            fontWeight: 700,
                            color: "#38bdf8",
                          }}
                        >
                          {iss.priority_score}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </div>

        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>📊 Statistical Profiling & Missingness</h3>
            <Link
              to={`/datasets/${currentDatasetId}/versions/${currentVersionId}/profile`}
            >
              Explore Profile →
            </Link>
          </div>

          {!profiling.available ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">📈</span>
              <span className="dash-empty-title">No Profiling Data Available</span>
              <p className="dash-empty-desc">
                Generate profile to calculate column statistics and missingness.
              </p>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi
                  label="Rows"
                  value={profiling.row_count?.toLocaleString()}
                />
                <Kpi label="Columns" value={profiling.column_count} />
                <Kpi
                  label="Missing Cells"
                  value={`${profiling.missing_percentage}%`}
                  tone={profiling.missing_percentage > 5 ? "warning" : "success"}
                />
                <Kpi label="Duplicates" value={profiling.duplicate_rows} />
              </div>

              {profiling.top_missing_columns?.length > 0 ? (
                <div>
                  <div className="dash-subtext" style={{ marginBottom: "0.4rem" }}>
                    TOP COLUMNS WITH MISSING DATA:
                  </div>
                  <div style={{ height: 160, width: "100%" }}>
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart
                        data={profiling.top_missing_columns.slice(0, 6)}
                        layout="vertical"
                        margin={{ top: 5, right: 20, left: 40, bottom: 5 }}
                      >
                        <CartesianGrid
                          strokeDasharray="3 3"
                          stroke="rgba(148, 163, 184, 0.1)"
                          horizontal={false}
                        />
                        <XAxis
                          type="number"
                          domain={[0, 100]}
                          unit="%"
                          stroke="var(--dg2-muted)"
                          fontSize={11}
                        />
                        <YAxis
                          dataKey="column_name"
                          type="category"
                          stroke="var(--dg2-muted)"
                          fontSize={11}
                          width={80}
                        />
                        <Tooltip content={<CustomTooltip unit="%" />} />
                        <Bar
                          dataKey="missing_percentage"
                          name="Missing %"
                          fill="#f59e0b"
                          radius={[0, 4, 4, 0]}
                        />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>
              ) : (
                <div className="dash-info dash-info--success">
                  ✨ Zero missing values detected across all columns.
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* =======================================================
          7. DRIFT + TREND ROW
          ======================================================= */}
      <div className="dash-grid-2">
        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>🔄 Version Comparison & Drift</h3>
            <Link to={`/datasets/${currentDatasetId}/compare`}>
              Compare Tool →
            </Link>
          </div>

          {!drift.has_comparison ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">🔀</span>
              <span className="dash-empty-title">
                No Version Comparison Available
              </span>
              <p className="dash-empty-desc">
                Compare this version against a previous baseline to track drift
                and schema shifts.
              </p>
              <Link
                to={`/datasets/${currentDatasetId}/compare`}
                className="btn--secondary"
                style={{ marginTop: "0.6rem" }}
              >
                Compare Versions
              </Link>
            </div>
          ) : (
            <>
              <div className="dash-kpi-grid">
                <Kpi
                  label="Compared"
                  value={`V${drift.baseline_version_number} → V${drift.current_version_number}`}
                />
                <Kpi
                  label="Overall Drift"
                  value={drift.overall_drift_severity}
                  tone={
                    drift.overall_drift_severity === "HIGH"
                      ? "danger"
                      : drift.overall_drift_severity === "MEDIUM"
                      ? "warning"
                      : "success"
                  }
                />
                <Kpi label="Drifted Columns" value={drift.drifted_columns_count} />
              </div>

              {drift.column_drifts?.length > 0 ? (
                <div className="dash-table-wrap">
                  <table className="data-table">
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
                          <td className="column-name-code">{col.column_name}</td>
                          <td>{col.drift_type}</td>
                          <td>
                            <span className={`dash-pill dash-pill--${col.severity}`}>
                              {col.severity}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="dash-info dash-info--success">
                  ✨ No column-level drift detected against baseline.
                </div>
              )}
            </>
          )}
        </div>

        <div className="dash-panel">
          <div className="dash-panel-head">
            <h3>📈 Dataset Health Trend</h3>
            <span className="dash-muted">
              {trends.versions?.length || 0} Versions Logged
            </span>
          </div>

          {!trends.has_sufficient_history ? (
            <div className="dash-empty">
              <span className="dash-empty-icon">📉</span>
              <span className="dash-empty-title">Not Enough Version History</span>
              <p className="dash-empty-desc">
                Upload and analyze at least two dataset versions to unlock
                chronological trend analytics.
              </p>
            </div>
          ) : (
            <div className="dash-trend">
              <ResponsiveContainer width="100%" height={230}>
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
                  <CartesianGrid
                    strokeDasharray="3 3"
                    stroke="rgba(148, 163, 184, 0.1)"
                  />
                  <XAxis dataKey="name" stroke="var(--dg2-muted)" fontSize={12} />
                  <YAxis domain={[0, 100]} stroke="var(--dg2-muted)" fontSize={12} />
                  <Tooltip content={<CustomTooltip />} />
                  <Legend
                    wrapperStyle={{ fontSize: "0.78rem", paddingTop: "8px" }}
                  />
                  <Line
                    type="monotone"
                    dataKey="Health"
                    stroke="#22d3ee"
                    strokeWidth={3}
                    dot={{ r: 4 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="Quality"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="Risk"
                    stroke="#f59e0b"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="Privacy"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* =======================================================
          8. ATTENTION COLUMNS MATRIX
          ======================================================= */}
      <section className="dash-panel">
        <div className="dash-panel-head">
          <h3>🎯 Columns Requiring Attention</h3>
          <span className="dash-muted">
            Synthesized across Risk, Quality, Anomalies, and PII
          </span>
        </div>

        {attention_columns.length > 0 ? (
          <div className="dash-table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Risk Level</th>
                  <th>Quality Status</th>
                  <th>Anomaly Severity</th>
                  <th>PII Severity</th>
                  <th style={{ textAlign: "right" }}>Active Issues</th>
                </tr>
              </thead>
              <tbody>
                {attention_columns.map((col, idx) => (
                  <tr key={idx}>
                    <td className="column-name-code">{col.column_name}</td>
                    <td>
                      {col.risk_level ? (
                        <span className={`dash-pill dash-pill--${col.risk_level}`}>
                          {col.risk_level}
                        </span>
                      ) : (
                        <span className="dash-muted">—</span>
                      )}
                    </td>
                    <td>
                      {col.quality_status ? (
                        <span className="dash-pill dash-pill--FAILED">
                          {col.quality_status}
                        </span>
                      ) : (
                        <span className="dash-muted">—</span>
                      )}
                    </td>
                    <td>
                      {col.anomaly_severity ? (
                        <span
                          className={`dash-pill dash-pill--${col.anomaly_severity}`}
                        >
                          {col.anomaly_severity}
                        </span>
                      ) : (
                        <span className="dash-muted">—</span>
                      )}
                    </td>
                    <td>
                      {col.pii_severity ? (
                        <span className={`dash-pill dash-pill--${col.pii_severity}`}>
                          {col.pii_severity}
                        </span>
                      ) : (
                        <span className="dash-muted">—</span>
                      )}
                    </td>
                    <td
                      style={{
                        textAlign: "right",
                        fontWeight: 700,
                        color:
                          col.issue_count > 0 ? "#38bdf8" : "var(--dg2-muted)",
                      }}
                    >
                      {col.issue_count > 0 ? col.issue_count : "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="dash-empty">
            <span className="dash-empty-icon">✨</span>
            <span className="dash-empty-title">No High-Risk Columns Flagged</span>
            <p className="dash-empty-desc">
              No columns currently exhibit elevated risk, quality failures, or
              anomalies.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}

/* --------- Small helper components --------- */

function ComponentBar({ title, value, tone }) {
  const width = value != null ? `${Math.max(0, Math.min(100, value))}%` : "0%";
  return (
    <div className="dash-comp">
      <div className="dash-comp-head">
        <span>{title}</span>
        <span>{value != null ? `${value} / 100` : "—"}</span>
      </div>
      <div className="dash-comp-track">
        <div className={`dash-comp-fill dash-comp-fill--${tone}`} style={{ width }} />
      </div>
    </div>
  );
}

function Kpi({ label, value, tone, muted }) {
  return (
    <div className={`dash-kpi${tone ? ` dash-kpi--${tone}` : ""}${muted ? " dash-kpi--muted" : ""}`}>
      <small>{label}</small>
      <strong>{value ?? "—"}</strong>
    </div>
  );
}