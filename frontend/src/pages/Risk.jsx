/**
 * DataGuard AI — ML Column Risk & Domain Classification
 *
 * Renders the ML risk scoring for a dataset version:
 * - Overall dataset risk index + level
 * - Risk breakdown KPIs
 * - Domain classification breakdown
 * - Predictions table with confidence / score bars
 * - Sticky explainability panel (score decomposition + factors + snapshot)
 *
 * Visual design: DATA GUARD AI workspace skin (.rk-* classes).
 * Backend contract: UNCHANGED.
 *   - getRiskPredictions() / predictRisk()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRiskPredictions, predictRisk } from '../api/client';
import './Risk.css';

export default function Risk() {
  const { datasetId, versionId } = useParams();
  const [riskData, setRiskData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRiskLevel, setSelectedRiskLevel] = useState('ALL');
  const [selectedDomain, setSelectedDomain] = useState('ALL');

  // Selected column for explainability panel
  const [selectedColumn, setSelectedColumn] = useState(null);

  useEffect(() => {
    fetchRiskData();
  }, [datasetId, versionId]);

  async function fetchRiskData(force = false) {
    if (force) setRecomputing(true);
    else setLoading(true);
    setError(null);

    try {
      const data = force
        ? await predictRisk(datasetId, versionId, true)
        : await getRiskPredictions(datasetId, versionId);
      setRiskData(data);
      if (data.predictions?.length > 0 && !selectedColumn) {
        setSelectedColumn(data.predictions[0]);
      }
    } catch (err) {
      console.error('Failed to load ML risk predictions:', err);
      setError(err.message || 'Failed to compute ML column classification & risk.');
    } finally {
      setLoading(false);
      setRecomputing(false);
    }
  }

  function getRiskBadge(level) {
    const l = (level || 'LOW').toUpperCase();
    if (l === 'CRITICAL') return { label: 'CRITICAL', icon: '🚨', color: '#f43f5e' };
    if (l === 'HIGH')     return { label: 'HIGH',     icon: '🔴', color: '#fb923c' };
    if (l === 'MEDIUM')   return { label: 'MEDIUM',   icon: '🟡', color: '#fbbf24' };
    return                       { label: 'LOW',      icon: '🟢', color: '#34d399' };
  }

  function getDomainIcon(domain) {
    const d = (domain || '').toLowerCase();
    if (d.includes('financial')) return '💳';
    if (d.includes('contact')) return '✉️';
    if (d.includes('personal')) return '👤';
    if (d.includes('identifier')) return '🔑';
    if (d.includes('location')) return '📍';
    if (d.includes('temporal')) return '🕒';
    if (d.includes('demographic')) return '👥';
    if (d.includes('technical') || d.includes('system')) return '💻';
    if (d.includes('measurement') || d.includes('numerical')) return '📊';
    if (d.includes('categorical')) return '🏷️';
    if (d.includes('text')) return '📝';
    return '📁';
  }

  function getScoreColor(score) {
    if (score >= 80) return '#f43f5e';
    if (score >= 60) return '#fb923c';
    if (score >= 35) return '#fbbf24';
    return '#34d399';
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="rk-page">
        <div className="rk-loading">
          <span className="rk-spinner" aria-hidden="true" />
          <p>Running ML Risk Pipeline…</p>
          <small>Extracting feature vectors and classifying column domains.</small>
        </div>
      </div>
    );
  }

  // ---------- Error ----------
  if (error || !riskData) {
    return (
      <div className="rk-page">
        <div className="rk-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>ML Prediction Error</strong>
            <p>{error || 'Unable to load column risk predictions.'}</p>
          </div>
        </div>
        <div className="rk-error-actions">
          <button
            className="rk-btn rk-btn--primary"
            onClick={() => fetchRiskData(true)}
            disabled={recomputing}
          >
            Retry ML Risk Analysis
          </button>
          <Link to="/datasets" className="rk-btn rk-btn--ghost">
            Back to Datasets
          </Link>
        </div>
      </div>
    );
  }

  const {
    dataset_name,
    version_number,
    total_columns,
    dataset_risk_index,
    overall_risk_level,
    risk_breakdown = {},
    domain_breakdown = {},
    mean_model_confidence,
    model_version,
    predicted_at,
    predictions = [],
  } = riskData;

  const filteredPredictions = predictions.filter((p) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchCol = p.column_name.toLowerCase().includes(q);
      const matchDom = p.predicted_domain.toLowerCase().includes(q);
      if (!matchCol && !matchDom) return false;
    }
    if (selectedRiskLevel !== 'ALL' && p.risk_level.toUpperCase() !== selectedRiskLevel) {
      return false;
    }
    if (selectedDomain !== 'ALL' && p.predicted_domain !== selectedDomain) {
      return false;
    }
    return true;
  });

  const overall = getRiskBadge(overall_risk_level);

  return (
    <div className="rk-page">
      {/* ================= HERO ================= */}
      <header className="rk-hero">
        <div className="rk-hero-info">
          <div className="rk-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{dataset_name}</span>
            <span className="rk-version-pill">V{version_number}</span>
            <span className="rk-model-pill">{model_version}</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>ML Column Risk &amp; Domain Classification</h1>
          <p>Predicted on {new Date(predicted_at).toLocaleString()}</p>
        </div>

        <div className="rk-hero-actions">
          <button
            className="rk-btn rk-btn--ghost"
            onClick={() => fetchRiskData(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <span className="rk-spinner rk-spinner--sm" /> Predicting…
              </>
            ) : (
              '🔄 Re-predict'
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/profile`}
            className="rk-btn rk-btn--ghost"
          >
            📊 Profile
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="rk-btn rk-btn--ghost"
          >
            🛡 Quality
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="rk-btn rk-btn--ghost"
          >
            🔐 PII
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
            className="rk-btn rk-btn--ghost rk-btn--amber"
          >
            ⚠ Anomalies
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="rk-btn rk-btn--primary"
          >
            🎯 Prioritization
          </Link>
        </div>
      </header>

      {/* ================= OVERVIEW BANNER ================= */}
      <section
        className="rk-overview"
        style={{ borderLeftColor: overall.color }}
      >
        <div
          className="rk-overview-score"
          style={{ borderColor: overall.color, color: overall.color }}
        >
          <strong>{dataset_risk_index}</strong>
          <small>/ 100</small>
        </div>

        <div className="rk-overview-info">
          <div className="rk-overview-title-row">
            <h3>Dataset Risk Index: {dataset_risk_index} / 100</h3>
            <span
              className="rk-overview-pill"
              style={{
                color: overall.color,
                borderColor: overall.color,
                background: `${overall.color}22`,
              }}
            >
              {overall.icon} {overall.label} RISK
            </span>
          </div>
          <p>
            Analyzed {total_columns} columns using scikit-learn domain classification
            &amp; multi-factor risk fusion. Average model inference confidence:{" "}
            <strong>{Math.round(mean_model_confidence * 100)}%</strong>.
          </p>
        </div>
      </section>

      {/* ================= KPI GRID ================= */}
      <section className="rk-kpi-grid">
        <div className="rk-kpi rk-kpi--info">
          <small>Total Columns</small>
          <strong>{total_columns}</strong>
          <em>Evaluated features</em>
        </div>
        <div className={`rk-kpi ${risk_breakdown.CRITICAL > 0 ? 'rk-kpi--danger' : 'rk-kpi--muted'}`}>
          <small>Critical Risk (≥80)</small>
          <strong>{risk_breakdown.CRITICAL || 0}</strong>
          <em>Immediate attention</em>
        </div>
        <div className={`rk-kpi ${risk_breakdown.HIGH > 0 ? 'rk-kpi--orange' : 'rk-kpi--muted'}`}>
          <small>High Risk (60–79)</small>
          <strong>{risk_breakdown.HIGH || 0}</strong>
          <em>Sensitive PII / Finance</em>
        </div>
        <div className={`rk-kpi ${risk_breakdown.MEDIUM > 0 ? 'rk-kpi--warning' : 'rk-kpi--muted'}`}>
          <small>Medium Risk (35–59)</small>
          <strong>{risk_breakdown.MEDIUM || 0}</strong>
          <em>Demographic / IP / Location</em>
        </div>
        <div className={`rk-kpi ${risk_breakdown.LOW > 0 ? 'rk-kpi--success' : 'rk-kpi--muted'}`}>
          <small>Low Risk (&lt;35)</small>
          <strong>{risk_breakdown.LOW || 0}</strong>
          <em>Operational / Metrics</em>
        </div>
        <div className="rk-kpi rk-kpi--accent">
          <small>Mean Confidence</small>
          <strong>{Math.round(mean_model_confidence * 100)}%</strong>
          <em>Model calibration</em>
        </div>
      </section>

      {/* ================= DOMAIN BREAKDOWN ================= */}
      {Object.keys(domain_breakdown).length > 0 && (
        <section className="rk-domain-section">
          <div className="rk-section-head">
            <h2>Predicted Semantic Domains</h2>
            {selectedDomain !== 'ALL' && (
              <button
                className="rk-btn rk-btn--ghost rk-btn--xs"
                onClick={() => setSelectedDomain('ALL')}
              >
                Clear filter ({selectedDomain})
              </button>
            )}
          </div>

          <div className="rk-domain-grid">
            {Object.entries(domain_breakdown).map(([domain, count]) => {
              const icon = getDomainIcon(domain);
              const isSelected = selectedDomain === domain;
              return (
                <button
                  key={domain}
                  type="button"
                  className={`rk-domain-btn ${isSelected ? 'rk-domain-btn--active' : ''}`}
                  onClick={() => setSelectedDomain(isSelected ? 'ALL' : domain)}
                >
                  <span className="rk-domain-icon">{icon}</span>
                  <span className="rk-domain-name">{domain}</span>
                  <span className="rk-domain-count">{count}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* ================= MAIN LAYOUT: TABLE + PANEL ================= */}
      <div className={`rk-layout ${selectedColumn ? 'rk-layout--with-panel' : ''}`}>
        {/* Table */}
        <section className="rk-panel">
          <div className="rk-panel-head">
            <h3>Column Risk Predictions</h3>
            <div className="rk-filter-row">
              <input
                type="text"
                className="rk-input"
                placeholder="Search column or domain…"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <div className="rk-risk-filters">
                {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((lvl) => (
                  <button
                    key={lvl}
                    type="button"
                    className={`rk-risk-btn ${
                      selectedRiskLevel === lvl ? 'rk-risk-btn--active' : ''
                    }`}
                    onClick={() => setSelectedRiskLevel(lvl)}
                  >
                    {lvl}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {filteredPredictions.length === 0 ? (
            <div className="rk-empty">
              <span className="rk-empty-icon">🔍</span>
              <h4>No Matching Columns</h4>
              <p>Try adjusting your search query or domain/risk filters.</p>
            </div>
          ) : (
            <div className="rk-table-wrap">
              <table className="rk-table">
                <thead>
                  <tr>
                    <th>Column</th>
                    <th>Domain</th>
                    <th>Confidence</th>
                    <th>Risk Score</th>
                    <th>Level</th>
                    <th style={{ textAlign: 'right' }}>Explain</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPredictions.map((p) => {
                    const risk = getRiskBadge(p.risk_level);
                    const domainIcon = getDomainIcon(p.predicted_domain);
                    const isSelected = selectedColumn?.column_name === p.column_name;
                    const confPct = Math.round(p.model_confidence * 100);
                    const scoreColor = getScoreColor(p.risk_score);

                    return (
                      <tr
                        key={p.id}
                        className={isSelected ? 'rk-row-selected' : ''}
                        onClick={() => setSelectedColumn(p)}
                      >
                        <td>
                          <div className="rk-col-cell">
                            <code className="rk-col-code">{p.column_name}</code>
                            {p.pii_signal && (
                              <span title="PII Detected" className="rk-signal">🔒</span>
                            )}
                            {p.quality_failure_count > 0 && (
                              <span
                                title={`${p.quality_failure_count} Quality Rule Failures`}
                                className="rk-signal"
                              >
                                ⚠️
                              </span>
                            )}
                          </div>
                        </td>
                        <td>
                          <span className="rk-domain-tag">
                            {domainIcon} {p.predicted_domain}
                          </span>
                        </td>
                        <td>
                          <div className="rk-bar">
                            <span className="rk-bar-value">{confPct}%</span>
                            <div className="rk-bar-track">
                              <div
                                className="rk-bar-fill rk-bar-fill--cyan"
                                style={{ width: `${confPct}%` }}
                              />
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="rk-bar">
                            <span className="rk-bar-value" style={{ color: scoreColor }}>
                              {p.risk_score}
                            </span>
                            <div className="rk-bar-track">
                              <div
                                className="rk-bar-fill"
                                style={{ width: `${p.risk_score}%`, background: scoreColor }}
                              />
                            </div>
                          </div>
                        </td>
                        <td>
                          <span
                            className="rk-risk-pill"
                            style={{
                              color: risk.color,
                              borderColor: risk.color,
                              background: `${risk.color}22`,
                            }}
                          >
                            {risk.icon} {risk.label}
                          </span>
                        </td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="rk-btn rk-btn--ghost rk-btn--xs"
                            onClick={(e) => {
                              e.stopPropagation();
                              setSelectedColumn(p);
                            }}
                          >
                            Explain
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

        {/* Explainability panel */}
        {selectedColumn && (
          <aside className="rk-drawer">
            <div className="rk-drawer-head">
              <div>
                <small>COLUMN EXPLAINABILITY</small>
                <h3>
                  <code>{selectedColumn.column_name}</code>
                </h3>
              </div>
              <span
                className="rk-risk-pill"
                style={(() => {
                  const risk = getRiskBadge(selectedColumn.risk_level);
                  return {
                    color: risk.color,
                    borderColor: risk.color,
                    background: `${risk.color}22`,
                  };
                })()}
              >
                {selectedColumn.risk_level} ({selectedColumn.risk_score}/100)
              </span>
            </div>

            {/* Prediction info */}
            <div className="rk-snapshot">
              <div className="rk-snapshot-row">
                <span>ML Domain</span>
                <strong>
                  {getDomainIcon(selectedColumn.predicted_domain)}{' '}
                  {selectedColumn.predicted_domain}
                </strong>
              </div>
              <div className="rk-snapshot-row">
                <span>Model Confidence</span>
                <strong style={{ color: '#67e8f9' }}>
                  {Math.round(selectedColumn.model_confidence * 100)}%
                </strong>
              </div>
              <div className="rk-snapshot-row">
                <span>Model Pipeline</span>
                <code>{selectedColumn.model_version}</code>
              </div>
            </div>

            {/* Score decomposition */}
            {selectedColumn.explanation?.score_components && (
              <div className="rk-section">
                <h4 className="rk-section-title">Score Components</h4>
                <div className="rk-score-grid">
                  <ScoreCard
                    label="PII Weight"
                    value={selectedColumn.explanation.score_components.pii_contribution}
                    tone="rose"
                  />
                  <ScoreCard
                    label="Domain Sensitivity"
                    value={selectedColumn.explanation.score_components.domain_contribution}
                    tone="orange"
                  />
                  <ScoreCard
                    label="Uniqueness"
                    value={selectedColumn.explanation.score_components.uniqueness_contribution}
                    tone="amber"
                  />
                  <ScoreCard
                    label="Quality Anomalies"
                    value={selectedColumn.explanation.score_components.quality_contribution}
                    tone="cyan"
                  />
                </div>
              </div>
            )}

            {/* Risk factors */}
            <div className="rk-section">
              <h4 className="rk-section-title rk-section-title--danger">
                ⚠️ Risk Factors
              </h4>
              {selectedColumn.explanation?.risk_factors?.length > 0 ? (
                <ul className="rk-factor-list rk-factor-list--danger">
                  {selectedColumn.explanation.risk_factors.map((factor, idx) => (
                    <li key={idx}>{factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="rk-muted">No critical risk factors identified.</p>
              )}
            </div>

            {/* Protective factors */}
            <div className="rk-section">
              <h4 className="rk-section-title rk-section-title--success">
                🛡 Protective Factors
              </h4>
              {selectedColumn.explanation?.protective_factors?.length > 0 ? (
                <ul className="rk-factor-list rk-factor-list--success">
                  {selectedColumn.explanation.protective_factors.map((factor, idx) => (
                    <li key={idx}>{factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="rk-muted">No protective factors identified.</p>
              )}
            </div>

            {/* Feature snapshot */}
            {selectedColumn.feature_snapshot && (
              <div className="rk-section">
                <h4 className="rk-section-title">Feature Snapshot</h4>
                <div className="rk-code-block">
                  <div>Missingness: {selectedColumn.feature_snapshot.missing_pct}%</div>
                  <div>Uniqueness: {selectedColumn.feature_snapshot.unique_pct}%</div>
                  <div>Cardinality: {selectedColumn.feature_snapshot.cardinality}</div>
                  <div>Numeric: {selectedColumn.feature_snapshot.is_numeric ? 'True' : 'False'}</div>
                  <div>String: {selectedColumn.feature_snapshot.is_string ? 'True' : 'False'}</div>
                  {selectedColumn.feature_snapshot.has_pii && (
                    <div className="rk-snapshot-danger">
                      PII Signal: Present (
                      {Math.round((selectedColumn.feature_snapshot.pii_confidence || 0) * 100)}%
                      conf)
                    </div>
                  )}
                </div>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}

/* ---------- Helpers ---------- */
function ScoreCard({ label, value, tone }) {
  return (
    <div className={`rk-score-card rk-score-card--${tone}`}>
      <small>{label}</small>
      <strong>+{value}</strong>
    </div>
  );
}