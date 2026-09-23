/**
 * DataGuard AI — Automated Dataset Profiling Page
 *
 * Phase 4 Automated Profiling:
 * - Dataset-level statistics (Memory, Missing Cells %, Duplicates, Feature breakdown)
 * - Column-level statistical profiles (Mean, Std, Quantiles, Skewness, Kurtosis)
 * - Interactive Recharts distribution histograms & top category bar charts
 * - Pearson feature correlation matrix
 * - All-columns comparison matrix
 *
 * Visual design: DATA GUARD AI workspace skin (.pr-* classes).
 * Backend contract: UNCHANGED.
 *   - getProfile() / generateProfile() / getDataset()
 *   - All field paths preserved.
 */

import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from "recharts";
import { getProfile, generateProfile, getDataset } from "../api/client";
import "./Profiling.css";

export default function Profiling() {
  const { datasetId, versionId } = useParams();

  const [profile, setProfile] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState("columns");
  const [selectedColName, setSelectedColName] = useState(null);
  const [colSearchQuery, setColSearchQuery] = useState("");

  useEffect(() => {
    fetchDatasetAndProfile();
  }, [datasetId, versionId]);

  useEffect(() => {
    if (profile && !selectedColName) {
      const firstCol = Object.keys(profile.column_profiles)[0];
      if (firstCol) setSelectedColName(firstCol);
    }
  }, [profile, selectedColName]);

  async function fetchDatasetAndProfile() {
    setLoading(true);
    setError(null);
    try {
      const ds = await getDataset(datasetId);
      setDataset(ds);

      try {
        const prof = await getProfile(datasetId, versionId);
        setProfile(prof);
      } catch (err) {
        if (err.status === 404) {
          setGenerating(true);
          const prof = await generateProfile(datasetId, versionId, false);
          setProfile(prof);
        } else {
          throw err;
        }
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
      setGenerating(false);
    }
  }

  async function handleRegenerate() {
    setGenerating(true);
    setError(null);
    try {
      const prof = await generateProfile(datasetId, versionId, true);
      setProfile(prof);
    } catch (err) {
      setError(`Failed to recompute profile: ${err.message}`);
    } finally {
      setGenerating(false);
    }
  }

  const getDtypeBadgeClass = (category) => {
    switch (category) {
      case "int":
      case "float":
      case "numeric":
        return "pr-dtype pr-dtype--numeric";
      case "date":
      case "datetime":
        return "pr-dtype pr-dtype--datetime";
      case "bool":
      case "boolean":
        return "pr-dtype pr-dtype--bool";
      case "string":
      case "categorical":
      case "text":
      default:
        return "pr-dtype pr-dtype--object";
    }
  };

  const getCorrelationColor = (val) => {
    if (val === null || val === undefined) return "rgba(148, 163, 184, 0.08)";
    if (val > 0.7) return "rgba(59, 130, 246, 0.55)";
    if (val > 0.3) return "rgba(59, 130, 246, 0.28)";
    if (val > -0.3) return "rgba(148, 163, 184, 0.08)";
    if (val > -0.7) return "rgba(244, 63, 94, 0.28)";
    return "rgba(244, 63, 94, 0.55)";
  };

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="pr-page">
        <div className="pr-loading">
          <span className="pr-spinner" aria-hidden="true" />
          <p>
            {generating
              ? "Generating automated statistical profile…"
              : "Loading profiling metadata…"}
          </p>
        </div>
      </div>
    );
  }

  // ---------- Error ----------
  if (error) {
    return (
      <div className="pr-page">
        <div className="pr-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Profiling Error</strong>
            <p>{error}</p>
          </div>
        </div>
        <div className="pr-error-actions">
          <Link to="/datasets" className="pr-btn pr-btn--ghost">
            ← Back to Datasets
          </Link>
          <button
            className="pr-btn pr-btn--primary"
            onClick={handleRegenerate}
            disabled={generating}
          >
            🔄 Try Generating Profile
          </button>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const colProfilesList = Object.values(profile.column_profiles);
  const filteredCols = colProfilesList.filter((col) =>
    col.name.toLowerCase().includes(colSearchQuery.toLowerCase()),
  );
  const selectedCol = selectedColName
    ? profile.column_profiles[selectedColName]
    : null;
  const correlationKeys = profile.correlations
    ? Object.keys(profile.correlations)
    : [];

  return (
    <div className="pr-page">
      {/* ================= HERO ================= */}
      <header className="pr-hero">
        <div className="pr-hero-info">
          <div className="pr-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{profile.dataset_name}</span>
            <span className="pr-version-pill">V{profile.version_number}</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Automated Statistical Profile</h1>
          <p>
            Detailed distribution analytics, quantiles, moments, correlations,
            and quality metrics for Version {profile.version_number}.
          </p>
        </div>

        <div className="pr-hero-actions">
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="pr-btn pr-btn--primary"
          >
            🛡 Quality Scorecard
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="pr-btn pr-btn--primary"
            style={{ background: "linear-gradient(135deg,#ec4899,#8b5cf6)", borderColor: "rgba(236,72,153,.5)" }}
          >
            🔐 Scan for PII
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/risk`}
            className="pr-btn pr-btn--primary"
            style={{ background: "linear-gradient(135deg,#10b981,#06b6d4)", borderColor: "rgba(6,182,212,.5)" }}
          >
            🤖 ML Risk
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
            className="pr-btn pr-btn--ghost pr-btn--amber"
          >
            ⚠ Anomalies
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="pr-btn pr-btn--primary"
            style={{ background: "linear-gradient(135deg,#06b6d4,#3b82f6)", borderColor: "rgba(6,182,212,.5)" }}
          >
            🎯 Prioritization
          </Link>
          <Link to="/datasets" className="pr-btn pr-btn--ghost">
            🗃️ All Datasets
          </Link>
          <button
            className="pr-btn pr-btn--ghost"
            onClick={handleRegenerate}
            disabled={generating}
          >
            {generating ? (
              <>
                <span className="pr-spinner pr-spinner--sm" /> Computing…
              </>
            ) : (
              "🔄 Recompute Profile"
            )}
          </button>
        </div>
      </header>

      {/* ================= KPI GRID ================= */}
      <div className="pr-kpi-grid">
        <Kpi icon="📊" label="Total Observations" value={`${profile.row_count.toLocaleString()} rows`} />
        <Kpi icon="📐" label="Total Features" value={`${profile.column_count} columns`} />
        <Kpi
          icon={profile.missing_cells > 0 ? "⚠️" : "✅"}
          label="Missing Cells"
          value={`${profile.missing_cells.toLocaleString()} (${profile.missing_cells_percentage}%)`}
          tone={profile.missing_cells > 0 ? "warning" : "success"}
        />
        <Kpi
          icon={profile.duplicate_rows > 0 ? "⚠️" : "✅"}
          label="Duplicate Rows"
          value={`${profile.duplicate_rows.toLocaleString()} (${profile.duplicate_rows_percentage}%)`}
          tone={profile.duplicate_rows > 0 ? "warning" : "success"}
        />
        <Kpi icon="💾" label="Memory Footprint" value={profile.memory_size_display} />
      </div>

      {/* ================= FEATURE BAR ================= */}
      <div className="pr-feature-bar">
        <span className="pr-feature">
          <span className="pr-dtype pr-dtype--numeric">Numeric</span>
          <strong>{profile.numeric_columns_count}</strong>
        </span>
        <span className="pr-feature">
          <span className="pr-dtype pr-dtype--object">Categorical / Text</span>
          <strong>{profile.categorical_columns_count}</strong>
        </span>
        <span className="pr-feature">
          <span className="pr-dtype pr-dtype--datetime">Datetime</span>
          <strong>{profile.datetime_columns_count}</strong>
        </span>
        <span className="pr-feature">
          <span className="pr-dtype pr-dtype--bool">Boolean</span>
          <strong>{profile.boolean_columns_count}</strong>
        </span>
      </div>

      {/* ================= TABS ================= */}
      <div className="pr-tabs">
        <button
          className={`pr-tab ${activeTab === "columns" ? "pr-tab--active" : ""}`}
          onClick={() => setActiveTab("columns")}
        >
          🔍 Feature Explorer & Distributions
        </button>
        {correlationKeys.length > 1 && (
          <button
            className={`pr-tab ${activeTab === "correlations" ? "pr-tab--active" : ""}`}
            onClick={() => setActiveTab("correlations")}
          >
            📈 Correlation Matrix ({correlationKeys.length}×{correlationKeys.length})
          </button>
        )}
        <button
          className={`pr-tab ${activeTab === "table" ? "pr-tab--active" : ""}`}
          onClick={() => setActiveTab("table")}
        >
          📑 Full Summary ({profile.column_count} cols)
        </button>
      </div>

      {/* ================= TAB 1 — COLUMN EXPLORER ================= */}
      {activeTab === "columns" && (
        <div className="pr-explorer">
          {/* Left panel */}
          <aside className="pr-col-panel">
            <div className="pr-col-head">
              <input
                type="text"
                placeholder="Filter features…"
                value={colSearchQuery}
                onChange={(e) => setColSearchQuery(e.target.value)}
                className="pr-input"
              />
            </div>
            <div className="pr-col-list">
              {filteredCols.map((col) => {
                const isSelected = selectedColName === col.name;
                return (
                  <button
                    key={col.name}
                    type="button"
                    className={`pr-col-item ${isSelected ? "pr-col-item--active" : ""}`}
                    onClick={() => setSelectedColName(col.name)}
                  >
                    <div className="pr-col-item-top">
                      <span className="pr-col-name">{col.name}</span>
                      <span className={getDtypeBadgeClass(col.type_category)}>
                        {col.type_category}
                      </span>
                    </div>
                    <div className="pr-col-item-sub">
                      <span>
                        {col.missing_percentage > 0
                          ? `${col.missing_percentage}% null`
                          : "100% complete"}
                      </span>
                      <span>• {col.unique_count} unique</span>
                    </div>
                  </button>
                );
              })}
              {filteredCols.length === 0 && (
                <p className="pr-empty-inline">No features match "{colSearchQuery}".</p>
              )}
            </div>
          </aside>

          {/* Right panel */}
          {selectedCol && (
            <section className="pr-detail">
              <div className="pr-detail-head">
                <div className="pr-detail-title">
                  <h2>{selectedCol.name}</h2>
                  <span className={getDtypeBadgeClass(selectedCol.type_category)}>
                    {selectedCol.type_category.toUpperCase()} ({selectedCol.dtype})
                  </span>
                  {selectedCol.missing_count === 0 ? (
                    <span className="pr-pill pr-pill--success">Complete</span>
                  ) : (
                    <span className="pr-pill pr-pill--warning">
                      {selectedCol.missing_count} Missing
                    </span>
                  )}
                </div>
                <p className="pr-detail-sub">
                  <strong>{selectedCol.count.toLocaleString()}</strong> valid values •{" "}
                  <strong>{selectedCol.unique_count.toLocaleString()}</strong> distinct (
                  {selectedCol.unique_percentage}%)
                </p>
              </div>

              {/* Numeric */}
              {selectedCol.type_category === "numeric" && (
                <div className="pr-metric-grid">
                  <div className="pr-panel">
                    <h4 className="pr-panel-title">📐 Descriptive Statistics</h4>
                    <MetricRow label="Mean" value={fmt(selectedCol.mean)} />
                    <MetricRow label="Std Dev (σ)" value={fmt(selectedCol.std)} />
                    <MetricRow label="Minimum" value={fmt(selectedCol.min)} />
                    <MetricRow label="Maximum" value={fmt(selectedCol.max)} />
                    <MetricRow label="Skewness" value={selectedCol.skewness ?? "N/A"} />
                    <MetricRow label="Kurtosis" value={selectedCol.kurtosis ?? "N/A"} />
                    <MetricRow label="Zero Values" value={selectedCol.zeros_count} />
                    <MetricRow label="Negative Values" value={selectedCol.negative_count} />
                  </div>

                  <div className="pr-panel">
                    <h4 className="pr-panel-title">🎯 Quantiles & Percentiles</h4>
                    <MetricRow label="Q1 (25th)" value={fmt(selectedCol.q25)} />
                    <MetricRow label="Median (50th)" value={fmt(selectedCol.q50)} highlight />
                    <MetricRow label="Q3 (75th)" value={fmt(selectedCol.q75)} />
                    <MetricRow label="95th" value={fmt(selectedCol.q95)} />
                    <MetricRow
                      label="IQR"
                      value={
                        selectedCol.q75 !== null && selectedCol.q25 !== null
                          ? (selectedCol.q75 - selectedCol.q25).toFixed(2)
                          : "N/A"
                      }
                    />
                  </div>

                  <div className="pr-panel pr-panel--wide">
                    <h4 className="pr-panel-title">📊 Frequency Distribution</h4>
                    {selectedCol.histogram?.length > 0 ? (
                      <div style={{ width: "100%", height: 260 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={selectedCol.histogram}
                            margin={{ top: 15, right: 20, left: 10, bottom: 25 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                            <XAxis
                              dataKey="label"
                              stroke="#94a3b8"
                              fontSize={11}
                              angle={-25}
                              textAnchor="end"
                              height={45}
                            />
                            <YAxis stroke="#94a3b8" fontSize={11} />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#0f172a",
                                borderColor: "rgba(96,165,250,0.35)",
                                borderRadius: "8px",
                                color: "#f1f5f9",
                                fontSize: "12px",
                              }}
                              formatter={(value) => [`${value} rows`, "Frequency"]}
                              labelFormatter={(label) => `Interval: ${label}`}
                            />
                            <Bar dataKey="count" fill="#22d3ee" radius={[4, 4, 0, 0]}>
                              {selectedCol.histogram.map((entry, index) => (
                                <Cell
                                  key={`cell-${index}`}
                                  fill={index % 2 === 0 ? "#22d3ee" : "#3b82f6"}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <p className="pr-muted">No histogram data available.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Categorical / Text / Boolean */}
              {(selectedCol.type_category === "categorical" ||
                selectedCol.type_category === "text" ||
                selectedCol.type_category === "boolean") && (
                <div className="pr-metric-grid">
                  <div className="pr-panel pr-panel--wide">
                    <h4 className="pr-panel-title">🏷️ Top Categories & Frequencies</h4>
                    {selectedCol.top_categories?.length > 0 ? (
                      <div style={{ width: "100%", height: 260 }}>
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={selectedCol.top_categories}
                            layout="vertical"
                            margin={{ top: 10, right: 30, left: 60, bottom: 10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148,163,184,0.1)" />
                            <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                            <YAxis
                              dataKey="value"
                              type="category"
                              stroke="#94a3b8"
                              fontSize={11}
                              width={100}
                              tickFormatter={(v) =>
                                v.length > 14 ? `${v.slice(0, 14)}…` : v
                              }
                            />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: "#0f172a",
                                borderColor: "rgba(96,165,250,0.35)",
                                borderRadius: "8px",
                                color: "#f1f5f9",
                                fontSize: "12px",
                              }}
                              formatter={(value, name, props) => [
                                `${value} rows (${props.payload.percentage}%)`,
                                "Frequency",
                              ]}
                            />
                            <Bar dataKey="count" fill="#a855f7" radius={[0, 4, 4, 0]}>
                              {selectedCol.top_categories.map((entry, index) => (
                                <Cell
                                  key={`cat-cell-${index}`}
                                  fill={index === 0 ? "#22d3ee" : "#a855f7"}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <p className="pr-muted">No category counts available.</p>
                    )}
                  </div>

                  {selectedCol.type_category === "text" && (
                    <div className="pr-panel pr-panel--wide">
                      <h4 className="pr-panel-title">📝 Text Character Lengths</h4>
                      <div className="pr-inline-stats">
                        <MetricRow label="Min Length" value={selectedCol.min_length ?? "N/A"} />
                        <MetricRow label="Max Length" value={selectedCol.max_length ?? "N/A"} />
                        <MetricRow
                          label="Average Length"
                          value={`${selectedCol.avg_length ?? "N/A"} chars`}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Datetime */}
              {selectedCol.type_category === "datetime" && (
                <div className="pr-panel pr-panel--wide">
                  <h4 className="pr-panel-title">📅 Temporal Span</h4>
                  <div className="pr-inline-stats">
                    <MetricRow label="Earliest Timestamp" value={selectedCol.min_date ?? "N/A"} />
                    <MetricRow label="Latest Timestamp" value={selectedCol.max_date ?? "N/A"} />
                  </div>
                </div>
              )}
            </section>
          )}
        </div>
      )}

      {/* ================= TAB 2 — CORRELATION MATRIX ================= */}
      {activeTab === "correlations" && profile.correlations && (
        <div className="pr-table-card">
          <div className="pr-table-head">
            <h3>Pearson Correlation Matrix</h3>
            <p>
              Values near +1.0 indicate strong positive linear relationship; near
              −1.0, strong negative.
            </p>
          </div>
          <div className="pr-table-wrap">
            <table className="pr-corr-table">
              <thead>
                <tr>
                  <th className="pr-corr-head">Feature</th>
                  {correlationKeys.map((k) => (
                    <th key={k} title={k} className="pr-corr-th">
                      {k.length > 15 ? `${k.slice(0, 12)}…` : k}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {correlationKeys.map((rowKey) => (
                  <tr key={rowKey}>
                    <td className="pr-corr-row-label">
                      <code>{rowKey}</code>
                    </td>
                    {correlationKeys.map((colKey) => {
                      const val = profile.correlations[rowKey]?.[colKey];
                      const isSelf = rowKey === colKey;
                      return (
                        <td
                          key={colKey}
                          className={`pr-corr-cell ${isSelf ? "pr-corr-cell--self" : ""}`}
                          style={{
                            backgroundColor: isSelf
                              ? "rgba(34,211,238,0.15)"
                              : getCorrelationColor(val),
                          }}
                          title={`${rowKey} ↔ ${colKey}: ${val}`}
                        >
                          {val !== undefined && val !== null ? val.toFixed(2) : "—"}
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

      {/* ================= TAB 3 — FULL SUMMARY TABLE ================= */}
      {activeTab === "table" && (
        <div className="pr-table-card">
          <div className="pr-table-wrap">
            <table className="pr-table">
              <thead>
                <tr>
                  <th style={{ width: 40 }}>#</th>
                  <th>Feature Name</th>
                  <th>Type</th>
                  <th>Valid Rows</th>
                  <th>Missing %</th>
                  <th>Distinct Values</th>
                  <th>Mean / Top Category</th>
                  <th>Min / Max</th>
                </tr>
              </thead>
              <tbody>
                {colProfilesList.map((col, idx) => (
                  <tr key={col.name}>
                    <td className="pr-muted">{idx + 1}</td>
                    <td>
                      <code className="pr-col-name">{col.name}</code>
                    </td>
                    <td>
                      <span className={getDtypeBadgeClass(col.type_category)}>
                        {col.type_category}
                      </span>
                    </td>
                    <td>{col.count.toLocaleString()}</td>
                    <td>
                      <span className={col.missing_percentage > 0 ? "pr-warn" : "pr-success"}>
                        {col.missing_percentage}%
                      </span>
                    </td>
                    <td>
                      {col.unique_count.toLocaleString()} ({col.unique_percentage}%)
                    </td>
                    <td>
                      {col.type_category === "numeric" ? (
                        <span>μ = {col.mean ?? "N/A"}</span>
                      ) : col.top_categories?.[0] ? (
                        <span>
                          {col.top_categories[0].value} ({col.top_categories[0].percentage}%)
                        </span>
                      ) : (
                        <span className="pr-muted">—</span>
                      )}
                    </td>
                    <td>
                      {col.type_category === "numeric" && col.min !== null ? (
                        <span>[{col.min}, {col.max}]</span>
                      ) : col.min_date ? (
                        <span>[{col.min_date.slice(0, 10)}, {col.max_date.slice(0, 10)}]</span>
                      ) : (
                        <span className="pr-muted">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

/* ---------- Helpers ---------- */

function fmt(n) {
  if (n === null || n === undefined) return "N/A";
  if (typeof n === "number") return n.toLocaleString();
  return n;
}

function Kpi({ icon, label, value, tone }) {
  return (
    <div className={`pr-kpi${tone ? ` pr-kpi--${tone}` : ""}`}>
      <span className="pr-kpi-icon">{icon}</span>
      <div>
        <small>{label}</small>
        <strong>{value ?? "—"}</strong>
      </div>
    </div>
  );
}

function MetricRow({ label, value, highlight }) {
  return (
    <div className="pr-metric-row">
      <span className="pr-metric-name">{label}</span>
      <span className={`pr-metric-value${highlight ? " pr-metric-value--hl" : ""}`}>
        {value}
      </span>
    </div>
  );
}