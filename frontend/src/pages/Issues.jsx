/**
 * DataGuard AI — Prioritization & Dataset Health Dashboard (Phase 9)
 *
 * Enterprise Data Observability, Holistic Dataset Health Scoring (0–100),
 * Cross-Signal Issue Prioritization, and Non-Destructive Remediation Engine.
 *
 * Visual design: DATA GUARD AI workspace skin (.is-* classes).
 * Backend contract: UNCHANGED.
 *   - analyzeIssues() / getIssuesSummary() / getIssues() / getDataset() / getDatasetVersion()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  analyzeIssues,
  getIssuesSummary,
  getIssues,
  getDataset,
  getDatasetVersion,
} from '../api/client';
import './Issues.css';

export default function Issues() {
  const { datasetId, versionId } = useParams();

  const [dataset, setDataset] = useState(null);
  const [version, setVersion] = useState(null);
  const [summary, setSummary] = useState(null);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [searchColumn, setSearchColumn] = useState('');

  const [selectedIssue, setSelectedIssue] = useState(null);

  useEffect(() => {
    loadData();
  }, [datasetId, versionId]);

  async function loadData() {
    try {
      setLoading(true);
      setError(null);

      const [dData, vData] = await Promise.all([
        getDataset(datasetId),
        getDatasetVersion(datasetId, versionId),
      ]);
      setDataset(dData);
      setVersion(vData);

      try {
        const sumData = await getIssuesSummary(datasetId, versionId);
        setSummary(sumData);
        setIssues(sumData.top_issues || []);
      } catch (err) {
        const sumData = await analyzeIssues(datasetId, versionId, false);
        setSummary(sumData);
        setIssues(sumData.top_issues || []);
      }

      const issuesData = await getIssues(datasetId, versionId);
      if (issuesData && issuesData.issues) {
        setIssues(issuesData.issues);
      }
    } catch (err) {
      setError(err.message || 'Failed to load dataset prioritization & health scorecard');
    } finally {
      setLoading(false);
    }
  }

  async function handleReanalyze() {
    try {
      setAnalyzing(true);
      setError(null);
      const sumData = await analyzeIssues(datasetId, versionId, true);
      setSummary(sumData);

      const issuesData = await getIssues(datasetId, versionId);
      if (issuesData && issuesData.issues) {
        setIssues(issuesData.issues);
      }
    } catch (err) {
      setError(err.message || 'Failed to recompute dataset health & prioritization');
    } finally {
      setAnalyzing(false);
    }
  }

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const filteredIssues = issues.filter((iss) => {
    if (severityFilter !== 'ALL' && iss.severity?.toUpperCase() !== severityFilter) {
      return false;
    }
    if (sourceFilter !== 'ALL' && iss.source?.toUpperCase() !== sourceFilter) {
      return false;
    }
    if (
      searchColumn &&
      !((iss.column_name || 'dataset').toLowerCase().includes(searchColumn.toLowerCase()))
    ) {
      return false;
    }
    return true;
  });

  function getGradeBadge(grade) {
    switch (grade) {
      case 'EXCELLENT': return { color: '#34d399' };
      case 'GOOD':      return { color: '#60a5fa' };
      case 'NEEDS ATTENTION': return { color: '#fbbf24' };
      case 'POOR':      return { color: '#fb923c' };
      case 'CRITICAL':
      default:          return { color: '#f43f5e' };
    }
  }

  function getSeverityBadge(sev) {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL': return { color: '#f43f5e', icon: '🚨' };
      case 'HIGH':     return { color: '#fb923c', icon: '🔴' };
      case 'MEDIUM':   return { color: '#fbbf24', icon: '🟡' };
      case 'LOW':
      default:         return { color: '#34d399', icon: '🟢' };
    }
  }

  function getSourceBadge(src) {
    switch (src?.toUpperCase()) {
      case 'QUALITY': return { color: '#a855f7' };
      case 'PII':     return { color: '#22d3ee' };
      case 'RISK':    return { color: '#f43f5e' };
      case 'ANOMALY': return { color: '#fbbf24' };
      default:        return { color: '#94a3b8' };
    }
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="is-page">
        <div className="is-loading">
          <span className="is-spinner" aria-hidden="true" />
          <p>Synthesizing Health &amp; Prioritizing Issues…</p>
          <small>
            Aggregating multi-phase signals (Quality, ML Risk, Anomalies, PII) into
            deterministic priority rankings.
          </small>
        </div>
      </div>
    );
  }

  // Calculate circumference for SVG circular gauge
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const healthScoreVal = summary?.health_score || 0;
  const strokeDashoffset = circumference - (healthScoreVal / 100) * circumference;
  const gradeInfo = getGradeBadge(summary?.health_grade);

  return (
    <div className="is-page">
      {/* ================= HERO ================= */}
      <header className="is-hero">
        <div className="is-hero-info">
          <div className="is-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{dataset?.name || 'Dataset'}</span>
            <span className="is-version-pill">V{version?.version_number}</span>
            <span className="is-dims-pill">
              {version?.row_count?.toLocaleString()} rows × {version?.column_count} cols
            </span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Prioritization &amp; Dataset Health</h1>
          <p>Understand overall dataset health and prioritize the issues that require attention.</p>
        </div>

        <div className="is-hero-actions">
          <button
            className="is-btn is-btn--ghost"
            onClick={handleReanalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <>
                <span className="is-spinner is-spinner--sm" /> Re-analyzing…
              </>
            ) : (
              '🔄 Recompute Health & Priorities'
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/chat?scope=VERSION&versionId=${versionId}&initialQuery=Explain the highest-priority issues in this version`}
            className="is-btn is-btn--primary"
          >
            💬 Ask AI About Issues
          </Link>
        </div>
      </header>

      {/* ================= SUB-TABS ================= */}
      <nav className="is-subtabs">
        <Link to={`/datasets/${datasetId}/versions/${versionId}/profile`} className="is-subtab">
          📊 Profile
        </Link>
        <Link to={`/datasets/${datasetId}/versions/${versionId}/quality`} className="is-subtab">
          🛡 Quality
        </Link>
        <Link to={`/datasets/${datasetId}/versions/${versionId}/pii`} className="is-subtab">
          🔐 PII Scan
        </Link>
        <Link to={`/datasets/${datasetId}/versions/${versionId}/risk`} className="is-subtab">
          🤖 ML Risk
        </Link>
        <Link to={`/datasets/${datasetId}/versions/${versionId}/anomalies`} className="is-subtab">
          ⚠️ Anomalies
        </Link>
        <span className="is-subtab is-subtab--active">🎯 Prioritization</span>
        <Link to="/datasets" className="is-subtab">
          📁 Datasets
        </Link>
      </nav>

      {error && (
        <div className="is-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Prioritization Error</strong>
            <p>{error}</p>
          </div>
          <button type="button" onClick={loadData} className="is-btn is-btn--ghost is-btn--xs">
            Retry
          </button>
        </div>
      )}

      {/* ================= HEALTH HERO ================= */}
      {summary && (
        <section className="is-health-hero">
          {/* Left: radial gauge */}
          <div className="is-gauge-card" style={{ borderLeftColor: gradeInfo.color }}>
            <small className="is-gauge-label">Dataset Health Score</small>
            <p className="is-gauge-sub">Overall dataset integrity &amp; posture</p>

            <div className="is-gauge">
              <svg width="150" height="150" viewBox="0 0 150 150">
                <circle
                  cx="75"
                  cy="75"
                  r={radius}
                  stroke="rgba(148,163,184,0.18)"
                  strokeWidth="12"
                  fill="transparent"
                />
                <circle
                  cx="75"
                  cy="75"
                  r={radius}
                  stroke={gradeInfo.color}
                  strokeWidth="12"
                  strokeDasharray={circumference}
                  strokeDashoffset={strokeDashoffset}
                  strokeLinecap="round"
                  fill="transparent"
                  style={{
                    transition: 'stroke-dashoffset 900ms cubic-bezier(.22, 1, .36, 1)',
                    transform: 'rotate(-90deg)',
                    transformOrigin: '75px 75px',
                  }}
                />
              </svg>
              <div className="is-gauge-value">
                <strong>{summary.health_score.toFixed(1)}</strong>
                <small>/ 100</small>
              </div>
            </div>

            <span
              className="is-grade-pill"
              style={{
                color: gradeInfo.color,
                borderColor: gradeInfo.color,
                background: `${gradeInfo.color}22`,
              }}
            >
              ● {summary.health_grade}
            </span>

            <p className="is-gauge-note">
              Deterministic synthesis: Quality (60%), Risk (15%), Anomaly (15%), Privacy (10%).
            </p>
          </div>

          {/* Right: 4 subsystem cards */}
          <div className="is-subsystem-panel">
            <div className="is-panel-head">
              <h3>📊 Subsystem Health Breakdown</h3>
              <span className="is-panel-meta">
                Calculated: {new Date(summary.calculated_at).toLocaleTimeString()}
              </span>
            </div>

            <div className="is-subsystem-grid">
              <SubsystemCard
                icon="✅"
                label="QUALITY"
                value={summary.quality_health}
                weight="60% weight"
                gradient="linear-gradient(90deg, #a855f7, #22d3ee)"
              />
              <SubsystemCard
                icon="🧠"
                label="RISK"
                value={summary.risk_health}
                weight="15% weight"
                gradient="linear-gradient(90deg, #f43f5e, #f59e0b)"
              />
              <SubsystemCard
                icon="⚠️"
                label="ANOMALY"
                value={summary.anomaly_health}
                weight="15% weight"
                gradient="linear-gradient(90deg, #f59e0b, #10b981)"
              />
              <SubsystemCard
                icon="🔒"
                label="PRIVACY"
                value={summary.privacy_health}
                weight="10% weight"
                gradient="linear-gradient(90deg, #3b82f6, #6366f1)"
              />
            </div>

            <p className="is-subsystem-note">
              Each subsystem remains separately identifiable without conflating exposure
              with data corruption.
            </p>
          </div>
        </section>
      )}

      {/* ================= ISSUE SUMMARY KPIs ================= */}
      {summary && (
        <section className="is-kpi-grid">
          <Kpi label="Total Issues" value={summary.total_issues} tone="accent" sub="Deduplicated" />
          <Kpi label="Critical" value={summary.critical_issues} tone="danger" sub="Immediate action" />
          <Kpi label="High" value={summary.high_issues} tone="orange" sub="Elevated impact" />
          <Kpi label="Medium" value={summary.medium_issues} tone="warning" sub="Moderate impact" />
          <Kpi label="Low" value={summary.low_issues} tone="success" sub="Minor deviation" />
          <Kpi
            label="Cols Affected"
            value={`${summary.columns_affected_count} / ${summary.total_columns_evaluated}`}
            tone="info"
            sub="With signals"
          />
        </section>
      )}

      {/* ================= COLUMN HEALTH MATRIX ================= */}
      {summary?.column_health_matrix?.length > 0 && (
        <section className="is-panel">
          <div className="is-panel-head">
            <h3>🏛️ Column Cross-Signal Matrix</h3>
            <span className="is-panel-meta">
              Sorted by highest priority &amp; cross-signal consensus
            </span>
          </div>

          <div className="is-table-wrap">
            <table className="is-table">
              <thead>
                <tr>
                  <th>Column Name</th>
                  <th>Type</th>
                  <th>Quality</th>
                  <th>ML Domain / Risk</th>
                  <th>Anomalies</th>
                  <th>PII Exposure</th>
                  <th>Cross-Signals</th>
                  <th style={{ textAlign: 'right' }}>Max Priority</th>
                </tr>
              </thead>
              <tbody>
                {summary.column_health_matrix.map((col) => (
                  <tr key={col.column_name}>
                    <td>
                      <code className="is-col-code">{col.column_name}</code>
                    </td>
                    <td>
                      <span className="is-dtype">{col.data_type}</span>
                    </td>
                    <td>
                      {col.quality_status === 'VIOLATION' ? (
                        <span className="is-tag is-tag--danger">
                          {col.quality_issues_count} Violation(s)
                        </span>
                      ) : (
                        <span className="is-muted">Clean</span>
                      )}
                    </td>
                    <td>
                      <span className="is-domain">
                        {col.domain}{' '}
                        <span className="is-mono">({col.risk_score.toFixed(0)})</span>
                      </span>
                    </td>
                    <td>
                      {col.anomaly_detected ? (
                        <span
                          className="is-sev-pill"
                          style={(() => {
                            const sb = getSeverityBadge(col.anomaly_severity);
                            return {
                              color: sb.color,
                              borderColor: sb.color,
                              background: `${sb.color}22`,
                            };
                          })()}
                        >
                          {col.anomaly_severity}
                        </span>
                      ) : (
                        <span className="is-muted">None</span>
                      )}
                    </td>
                    <td>
                      {col.pii_detected ? (
                        <span className="is-tag is-tag--cyan">
                          {col.pii_entities.join(', ')}
                        </span>
                      ) : (
                        <span className="is-muted">None</span>
                      )}
                    </td>
                    <td>
                      {col.cross_signal_count > 1 ? (
                        <span className="is-tag is-tag--accent">
                          {col.cross_signal_count} Subsystems
                        </span>
                      ) : col.cross_signal_count === 1 ? (
                        <span className="is-muted is-mono">1 Subsystem</span>
                      ) : (
                        <span className="is-muted is-mono">0</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <span className="is-mono is-priority-value">
                        {col.highest_priority > 0 ? col.highest_priority.toFixed(1) : '—'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {/* ================= PRIORITIZED ISSUE BACKLOG ================= */}
      <section className="is-panel">
        <div className="is-panel-head">
          <div>
            <h3>📑 Prioritized Issue Backlog</h3>
            <p className="is-panel-sub">
              Ranked by deterministic multi-factor priority score: Severity (30%),
              Data Impact (25%), Sensitivity (20%), Confidence (15%), Evidence (10%).
            </p>
          </div>

          <div className="is-filter-bar">
            <input
              type="text"
              className="is-input"
              placeholder="Filter by column…"
              value={searchColumn}
              onChange={(e) => setSearchColumn(e.target.value)}
            />

            <div className="is-seg">
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
                <button
                  key={s}
                  type="button"
                  className={`is-seg-btn ${severityFilter === s ? 'is-seg-btn--active' : ''}`}
                  onClick={() => setSeverityFilter(s)}
                >
                  {s}
                </button>
              ))}
            </div>

            <div className="is-seg">
              {['ALL', 'QUALITY', 'PII', 'RISK', 'ANOMALY'].map((src) => (
                <button
                  key={src}
                  type="button"
                  className={`is-seg-btn ${sourceFilter === src ? 'is-seg-btn--active' : ''}`}
                  onClick={() => setSourceFilter(src)}
                >
                  {src}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="is-table-wrap">
          <table className="is-table">
            <thead>
              <tr>
                <th>Priority</th>
                <th>Severity</th>
                <th>Issue Title</th>
                <th>Column / Scope</th>
                <th>Source</th>
                <th>Affected Data</th>
                <th>Remediation Action</th>
                <th style={{ textAlign: 'right' }}>Action</th>
              </tr>
            </thead>
            <tbody>
              {filteredIssues.length === 0 ? (
                <tr>
                  <td colSpan={8}>
                    <div className="is-empty">
                      {issues.length === 0 ? (
                        <>
                          <span className="is-empty-icon">✨</span>
                          <h4>No Issues Detected</h4>
                          <p>
                            This dataset version is healthy with zero data quality
                            violations, sensitive PII exposures, or high-risk anomalies.
                          </p>
                        </>
                      ) : (
                        <>
                          <p>No issues match the selected filter criteria.</p>
                          <button
                            type="button"
                            className="is-btn is-btn--ghost is-btn--xs"
                            onClick={() => {
                              setSeverityFilter('ALL');
                              setSourceFilter('ALL');
                              setSearchColumn('');
                            }}
                          >
                            Reset Filters
                          </button>
                        </>
                      )}
                    </div>
                  </td>
                </tr>
              ) : (
                filteredIssues.map((iss) => {
                  const sBadge = getSeverityBadge(iss.severity);
                  const srcBadge = getSourceBadge(iss.source);
                  return (
                    <tr key={iss.id} onClick={() => setSelectedIssue(iss)}>
                      <td>
                        <span className="is-priority-badge">
                          {iss.priority_score.toFixed(1)}
                        </span>
                      </td>
                      <td>
                        <span
                          className="is-sev-pill"
                          style={{
                            color: sBadge.color,
                            borderColor: sBadge.color,
                            background: `${sBadge.color}22`,
                          }}
                        >
                          {iss.severity}
                        </span>
                      </td>
                      <td>
                        <span className="is-issue-title">{iss.title}</span>
                      </td>
                      <td>
                        <code className="is-col-code">
                          {iss.column_name || <em className="is-muted">Dataset-wide</em>}
                        </code>
                      </td>
                      <td>
                        <span
                          className="is-source-tag"
                          style={{
                            color: srcBadge.color,
                            borderColor: srcBadge.color,
                            background: `${srcBadge.color}22`,
                          }}
                        >
                          {iss.source}
                        </span>
                      </td>
                      <td>
                        <span className="is-mono">
                          {iss.affected_percentage.toFixed(1)}%{' '}
                          <span className="is-muted">({iss.affected_rows}r)</span>
                        </span>
                      </td>
                      <td className="is-remediation-cell">
                        {iss.recommendation?.summary || 'Investigate issue details'}
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button type="button" className="is-btn is-btn--ghost is-btn--xs">
                          Inspect →
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </section>

      {/* ================= DETAIL DRAWER ================= */}
      {selectedIssue && (
        <div className="is-drawer-backdrop" onClick={() => setSelectedIssue(null)}>
          <aside className="is-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Header */}
            <div className="is-drawer-head">
              <div>
                <div className="is-drawer-tags">
                  <span
                    className="is-sev-pill"
                    style={(() => {
                      const sb = getSeverityBadge(selectedIssue.severity);
                      return { color: sb.color, borderColor: sb.color, background: `${sb.color}22` };
                    })()}
                  >
                    {selectedIssue.severity} Severity
                  </span>
                  <span
                    className="is-source-tag"
                    style={(() => {
                      const sb = getSourceBadge(selectedIssue.source);
                      return { color: sb.color, borderColor: sb.color, background: `${sb.color}22` };
                    })()}
                  >
                    {selectedIssue.source} Signal
                  </span>
                  <span className="is-priority-badge">
                    Priority: {selectedIssue.priority_score.toFixed(1)} / 100
                  </span>
                </div>
                <h2>{selectedIssue.title}</h2>
                <p className="is-muted is-mono">
                  Target: {selectedIssue.column_name || 'Dataset-Wide'} • Category:{' '}
                  {selectedIssue.issue_type}
                </p>
              </div>
              <button
                type="button"
                className="is-btn is-btn--ghost"
                onClick={() => setSelectedIssue(null)}
              >
                ✕
              </button>
            </div>

            {/* Overview */}
            <section className="is-drawer-section">
              <h4 className="is-drawer-label">Issue Overview &amp; Impact</h4>
              <p className="is-drawer-body">{selectedIssue.description}</p>
              <div className="is-drawer-meta">
                <span>
                  Affected Rows: <strong>{selectedIssue.affected_rows}</strong>
                </span>
                <span>
                  Affected Data:{' '}
                  <strong>{selectedIssue.affected_percentage.toFixed(2)}%</strong>
                </span>
              </div>
            </section>

            {/* Priority breakdown */}
            <section className="is-drawer-section">
              <h4 className="is-drawer-label is-drawer-label--cyan">
                Priority Score Component Breakdown
              </h4>
              <div className="is-priority-breakdown">
                <PriorityBar
                  label="Severity (30% weight)"
                  value={selectedIssue.severity}
                  pct={
                    selectedIssue.severity === 'CRITICAL'
                      ? 100
                      : selectedIssue.severity === 'HIGH'
                      ? 75
                      : selectedIssue.severity === 'MEDIUM'
                      ? 50
                      : 25
                  }
                  color="#f43f5e"
                />
                <PriorityBar
                  label="Affected Data Impact (25% weight)"
                  value={`${selectedIssue.affected_percentage.toFixed(1)}%`}
                  pct={Math.min(100, selectedIssue.affected_percentage)}
                  color="#fb923c"
                />
                <PriorityBar
                  label="Data Sensitivity Heuristic (20% weight)"
                  value={`${selectedIssue.sensitivity_score.toFixed(1)} / 100`}
                  pct={selectedIssue.sensitivity_score}
                  color="#fbbf24"
                />
                <PriorityBar
                  label="Confidence Heuristic (15% weight)"
                  value={`${selectedIssue.confidence_score.toFixed(1)} / 100`}
                  pct={selectedIssue.confidence_score}
                  color="#22d3ee"
                />
                <PriorityBar
                  label="Cross-Signal Evidence Score (10% weight)"
                  value={`${selectedIssue.evidence_score.toFixed(1)} / 100`}
                  pct={selectedIssue.evidence_score}
                  color="#818cf8"
                />
              </div>
            </section>

            {/* Remediation */}
            {selectedIssue.recommendation && (
              <section className="is-drawer-section is-remediation">
                <h4 className="is-drawer-label is-drawer-label--cyan">
                  🛠️ Recommended Remediation Plan
                </h4>

                <div className="is-rem-block">
                  <span className="is-rem-label">Why This Matters</span>
                  <p>{selectedIssue.recommendation.summary}</p>
                </div>

                {selectedIssue.recommendation.investigation_steps?.length > 0 && (
                  <div className="is-rem-block">
                    <span className="is-rem-label">Investigation Steps</span>
                    <ul>
                      {selectedIssue.recommendation.investigation_steps.map((step, i) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {selectedIssue.recommendation.preventive_measures?.length > 0 && (
                  <div className="is-rem-block">
                    <span className="is-rem-label">Preventive &amp; Safeguard Measures</span>
                    <ul>
                      {selectedIssue.recommendation.preventive_measures.map((p, i) => (
                        <li key={i}>{p}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {selectedIssue.recommendation.caution_note && (
                  <div className="is-caution">
                    <span>⚠️</span>
                    <span>{selectedIssue.recommendation.caution_note}</span>
                  </div>
                )}
              </section>
            )}

            {/* Evidence JSON */}
            {selectedIssue.evidence && Object.keys(selectedIssue.evidence).length > 0 && (
              <section className="is-drawer-section">
                <div className="is-drawer-label-row">
                  <h4 className="is-drawer-label">Underlying Diagnostic Evidence</h4>
                  <button
                    type="button"
                    className="is-btn is-btn--ghost is-btn--xs"
                    onClick={() =>
                      copyToClipboard(JSON.stringify(selectedIssue.evidence, null, 2), 'evidence')
                    }
                  >
                    {copiedKey === 'evidence' ? '✓ Copied' : 'Copy Evidence JSON'}
                  </button>
                </div>
                <pre className="is-code-block">
                  {JSON.stringify(selectedIssue.evidence, null, 2)}
                </pre>
              </section>
            )}

            {/* Footer */}
            <div className="is-drawer-foot">
              <span className="is-muted">DATA GUARD AI Prioritization Engine</span>
              <button
                type="button"
                className="is-btn is-btn--primary"
                onClick={() => setSelectedIssue(null)}
              >
                Close Inspector
              </button>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

/* ---------- Helpers ---------- */
function SubsystemCard({ icon, label, value, weight, gradient }) {
  const pct = Math.max(0, Math.min(100, value || 0));
  return (
    <div className="is-subsystem-card">
      <div className="is-subsystem-head">
        <span className="is-subsystem-name">
          {icon} {label}
        </span>
        <span className="is-subsystem-value">
          {value.toFixed(1)} <small>/ 100</small>
        </span>
      </div>
      <div className="is-subsystem-track">
        <div
          className="is-subsystem-fill"
          style={{ width: `${pct}%`, background: gradient }}
        />
      </div>
      <span className="is-subsystem-weight">{weight}</span>
    </div>
  );
}

function Kpi({ label, value, tone, sub }) {
  return (
    <div className={`is-kpi is-kpi--${tone}`}>
      <small>{label}</small>
      <strong>{value ?? '—'}</strong>
      <em>{sub}</em>
    </div>
  );
}

function PriorityBar({ label, value, pct, color }) {
  return (
    <div className="is-priority-bar">
      <div className="is-priority-bar-head">
        <span>{label}</span>
        <span className="is-mono" style={{ color }}>
          {value}
        </span>
      </div>
      <div className="is-priority-bar-track">
        <div
          className="is-priority-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
    </div>
  );
}