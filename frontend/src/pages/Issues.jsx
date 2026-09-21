/**
 * DataGuard AI — Prioritization & Dataset Health Dashboard (Phase 9)
 *
 * Enterprise Data Observability, Holistic Dataset Health Scoring (0–100),
 * Cross-Signal Issue Prioritization, and Non-Destructive Remediation Engine.
 * Matches the core DataGuard AI design system and styling tokens.
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

export default function Issues() {
  const { datasetId, versionId } = useParams();

  // State
  const [dataset, setDataset] = useState(null);
  const [version, setVersion] = useState(null);
  const [summary, setSummary] = useState(null);
  const [issues, setIssues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  // Filters
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [searchColumn, setSearchColumn] = useState('');

  // Slide-out Drawer State
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

      // Fetch or analyze summary
      try {
        const sumData = await getIssuesSummary(datasetId, versionId);
        setSummary(sumData);
        setIssues(sumData.top_issues || []);
      } catch (err) {
        // If not yet synthesized, trigger initial analysis
        const sumData = await analyzeIssues(datasetId, versionId, false);
        setSummary(sumData);
        setIssues(sumData.top_issues || []);
      }

      // Fetch full issues list
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

  // Filtered issues
  const filteredIssues = issues.filter((iss) => {
    if (severityFilter !== 'ALL' && iss.severity?.toUpperCase() !== severityFilter) {
      return false;
    }
    if (sourceFilter !== 'ALL' && iss.source?.toUpperCase() !== sourceFilter) {
      return false;
    }
    if (searchColumn && !((iss.column_name || 'dataset').toLowerCase().includes(searchColumn.toLowerCase()))) {
      return false;
    }
    return true;
  });

  const getGradeBadge = (grade) => {
    switch (grade) {
      case 'EXCELLENT':
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: 'rgba(16, 185, 129, 0.35)',
        };
      case 'GOOD':
        return {
          bg: 'rgba(56, 189, 248, 0.15)',
          color: '#38bdf8',
          border: 'rgba(56, 189, 248, 0.35)',
        };
      case 'NEEDS ATTENTION':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: 'rgba(245, 158, 11, 0.35)',
        };
      case 'POOR':
        return {
          bg: 'rgba(249, 115, 22, 0.15)',
          color: '#f97316',
          border: 'rgba(249, 115, 22, 0.35)',
        };
      case 'CRITICAL':
      default:
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          color: '#f43f5e',
          border: 'rgba(244, 63, 94, 0.35)',
        };
    }
  };

  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          color: '#f43f5e',
          border: 'rgba(244, 63, 94, 0.35)',
        };
      case 'HIGH':
        return {
          bg: 'rgba(249, 115, 22, 0.15)',
          color: '#f97316',
          border: 'rgba(249, 115, 22, 0.35)',
        };
      case 'MEDIUM':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: 'rgba(245, 158, 11, 0.35)',
        };
      case 'LOW':
      default:
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: 'rgba(16, 185, 129, 0.35)',
        };
    }
  };

  const getSourceBadge = (src) => {
    switch (src?.toUpperCase()) {
      case 'QUALITY':
        return {
          bg: 'rgba(168, 85, 247, 0.15)',
          color: '#c084fc',
          border: 'rgba(168, 85, 247, 0.35)',
        };
      case 'PII':
        return {
          bg: 'rgba(56, 189, 248, 0.15)',
          color: '#38bdf8',
          border: 'rgba(56, 189, 248, 0.35)',
        };
      case 'RISK':
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          color: '#f43f5e',
          border: 'rgba(244, 63, 94, 0.35)',
        };
      case 'ANOMALY':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          color: '#fbbf24',
          border: 'rgba(245, 158, 11, 0.35)',
        };
      default:
        return {
          bg: 'rgba(148, 163, 184, 0.15)',
          color: '#94a3b8',
          border: 'rgba(148, 163, 184, 0.3)',
        };
    }
  };

  if (loading) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '48px', maxWidth: '480px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', marginBottom: '20px' }}></div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem' }}>Synthesizing Health & Prioritizing Issues...</h2>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            Aggregating multi-phase signals (Quality, ML Risk, Anomalies, PII) into deterministic priority rankings.
          </p>
        </div>
      </div>
    );
  }

  // Calculate circumference for SVG circular gauge
  const radius = 54;
  const circumference = 2 * Math.PI * radius;
  const healthScoreVal = summary?.health_score || 0;
  const strokeDashoffset = circumference - (healthScoreVal / 100) * circumference;
  const gradeBadgeInfo = getGradeBadge(summary?.health_grade);

  return (
    <div className="page-container" style={{ paddingBottom: '60px' }}>
      {/* 1. Top Header & Context */}
      <div className="flex-row justify-between align-center" style={{ marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="flex-row align-center" style={{ gap: '10px', marginBottom: '6px', flexWrap: 'wrap' }}>
            <Link to="/datasets" className="text-muted" style={{ fontSize: '0.88rem', textDecoration: 'none' }}>
              ← Datasets
            </Link>
            <span className="text-muted" style={{ opacity: 0.6 }}>/</span>
            <span style={{ fontWeight: '600', fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              {dataset?.name || 'Dataset'}
            </span>
            <span className="badge badge-primary" style={{ fontSize: '0.8rem', padding: '3px 8px' }}>
              V{version?.version_number}
            </span>
            <span className="text-muted" style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>
              • {version?.row_count?.toLocaleString()} rows × {version?.column_count} cols
            </span>
          </div>

          <div className="flex-row align-center" style={{ gap: '10px' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>
              🎯 Prioritization & Dataset Health
            </h1>
          </div>
          <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.92rem' }}>
            Understand overall dataset health and prioritize the issues that require attention.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex-row align-center" style={{ gap: '10px' }}>
          <button
            className="btn btn-secondary flex-row align-center"
            style={{ gap: '8px' }}
            onClick={handleReanalyze}
            disabled={analyzing}
          >
            {analyzing ? (
              <>
                <div className="spinner-sm"></div>
                <span>Re-analyzing...</span>
              </>
            ) : (
              <>
                <span>🔄</span>
                <span>Recompute Health & Priorities</span>
              </>
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/chat?scope=VERSION&versionId=${versionId}&initialQuery=Explain the highest-priority issues in this version`}
            className="btn btn-primary flex-row align-center"
            style={{ gap: '8px', textDecoration: 'none' }}
          >
            <span>💬</span>
            <span>Ask AI About Issues</span>
          </Link>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex-row align-center" style={{ gap: '8px', marginBottom: '24px', flexWrap: 'wrap', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '12px' }}>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/profile`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem' }}
        >
          <span>📊</span>
          <span>Profile</span>
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/quality`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem' }}
        >
          <span>🛡</span>
          <span>Quality</span>
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/pii`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem' }}
        >
          <span>🔐</span>
          <span>PII Scan</span>
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/risk`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem' }}
        >
          <span>🤖</span>
          <span>ML Risk</span>
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem' }}
        >
          <span>⚠️</span>
          <span>Anomalies</span>
        </Link>
        <span
          className="btn btn-secondary flex-row align-center"
          style={{
            gap: '6px',
            fontSize: '0.85rem',
            borderColor: 'rgba(6, 182, 212, 0.5)',
            color: '#38bdf8',
            background: 'rgba(6, 182, 212, 0.12)',
            fontWeight: '700',
          }}
        >
          <span>🎯</span>
          <span>Prioritization</span>
        </span>
        <Link to="/datasets" className="btn btn-secondary" style={{ fontSize: '0.85rem' }}>
          📁 Datasets
        </Link>
      </div>

      {error && (
        <div className="alert-box alert-box--error" style={{ marginBottom: '20px' }}>
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            <strong>Prioritization Error</strong>
            <p>{error}</p>
          </div>
          <button onClick={loadData} className="btn btn--sm btn--secondary" style={{ alignSelf: 'center' }}>
            Retry
          </button>
        </div>
      )}

      {/* 2. Health Score Hero & 4-Way Breakdown Grid */}
      {summary && (
        <div className="grid-responsive" style={{ gridTemplateColumns: 'minmax(280px, 1fr) 2fr', gap: '20px', marginBottom: '24px' }}>
          {/* Left: Health Score Hero Section */}
          <div
            className="glass-card flex-col items-center justify-between"
            style={{
              padding: '24px',
              textAlign: 'center',
              borderLeft: `5px solid ${gradeBadgeInfo.color}`,
              background: 'var(--bg-card)',
            }}
          >
            <div>
              <span className="stat-label" style={{ display: 'block', marginBottom: '4px' }}>
                Dataset Health Score
              </span>
              <span className="text-muted" style={{ fontSize: '0.78rem', display: 'block', marginBottom: '12px' }}>
                Overall dataset integrity & posture
              </span>

              {/* Circular Radial Gauge */}
              <div style={{ position: 'relative', width: '130px', height: '130px', margin: '0 auto' }}>
                <svg width="130" height="130" style={{ transform: 'rotate(-90deg)' }}>
                  <circle
                    cx="65"
                    cy="65"
                    r={radius}
                    stroke="var(--bg-input)"
                    strokeWidth="10"
                    fill="transparent"
                  />
                  <circle
                    cx="65"
                    cy="65"
                    r={radius}
                    stroke={gradeBadgeInfo.color}
                    strokeWidth="10"
                    strokeDasharray={circumference}
                    strokeDashoffset={strokeDashoffset}
                    strokeLinecap="round"
                    fill="transparent"
                    style={{ transition: 'stroke-dashoffset 0.8s ease' }}
                  />
                </svg>
                <div
                  style={{
                    position: 'absolute',
                    inset: 0,
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <span style={{ fontSize: '2rem', fontWeight: '800', color: 'var(--text-primary)', lineHeight: 1 }}>
                    {summary.health_score.toFixed(1)}
                  </span>
                  <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '2px' }}>/ 100</span>
                </div>
              </div>

              {/* Health Grade Badge */}
              <div
                style={{
                  marginTop: '14px',
                  padding: '4px 14px',
                  borderRadius: '12px',
                  background: gradeBadgeInfo.bg,
                  color: gradeBadgeInfo.color,
                  border: `1px solid ${gradeBadgeInfo.border}`,
                  fontSize: '0.8rem',
                  fontWeight: '700',
                  letterSpacing: '0.05em',
                  display: 'inline-block',
                }}
              >
                ● {summary.health_grade}
              </div>
            </div>

            <div
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '0.75rem',
                color: 'var(--text-muted)',
                lineHeight: '1.4',
              }}
            >
              Deterministic synthesis: Quality (60%), Risk (15%), Anomaly (15%), Privacy (10%).
            </div>
          </div>

          {/* Right: 4-Way Health Breakdown Grid (4 Component Cards) */}
          <div className="glass-card flex-col justify-between" style={{ padding: '24px', background: 'var(--bg-card)' }}>
            <div>
              <div className="flex-row justify-between align-center" style={{ marginBottom: '16px' }}>
                <h3 style={{ margin: 0, fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
                  📊 Subsystem Health Breakdown
                </h3>
                <span style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
                  Calculated: {new Date(summary.calculated_at).toLocaleTimeString()}
                </span>
              </div>

              <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '14px' }}>
                {/* 1. Quality Health Card */}
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                      ✅ QUALITY
                    </span>
                    <span style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38bdf8' }}>
                      {summary.quality_health.toFixed(1)} <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>/ 100</span>
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', borderRadius: '3px', background: 'var(--bg-input)', overflow: 'hidden', margin: '8px 0' }}>
                    <div
                      style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #a855f7, #38bdf8)',
                        width: `${summary.quality_health}%`,
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                    Data validation health (60% weight)
                  </span>
                </div>

                {/* 2. Risk Health Card */}
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                      🧠 RISK
                    </span>
                    <span style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38bdf8' }}>
                      {summary.risk_health.toFixed(1)} <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>/ 100</span>
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', borderRadius: '3px', background: 'var(--bg-input)', overflow: 'hidden', margin: '8px 0' }}>
                    <div
                      style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #f43f5e, #f59e0b)',
                        width: `${summary.risk_health}%`,
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                    Column risk exposure (15% weight)
                  </span>
                </div>

                {/* 3. Anomaly Health Card */}
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                      ⚠️ ANOMALY
                    </span>
                    <span style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38bdf8' }}>
                      {summary.anomaly_health.toFixed(1)} <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>/ 100</span>
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', borderRadius: '3px', background: 'var(--bg-input)', overflow: 'hidden', margin: '8px 0' }}>
                    <div
                      style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #f59e0b, #10b981)',
                        width: `${summary.anomaly_health}%`,
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                    Statistical anomaly health (15% weight)
                  </span>
                </div>

                {/* 4. Privacy Health Card */}
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-glass)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                    <span style={{ fontSize: '0.82rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                      🔒 PRIVACY
                    </span>
                    <span style={{ fontSize: '0.85rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38bdf8' }}>
                      {summary.privacy_health.toFixed(1)} <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>/ 100</span>
                    </span>
                  </div>
                  <div style={{ width: '100%', height: '6px', borderRadius: '3px', background: 'var(--bg-input)', overflow: 'hidden', margin: '8px 0' }}>
                    <div
                      style={{
                        height: '100%',
                        background: 'linear-gradient(90deg, #3b82f6, #6366f1)',
                        width: `${summary.privacy_health}%`,
                        transition: 'width 0.5s ease',
                      }}
                    />
                  </div>
                  <span className="text-muted" style={{ fontSize: '0.75rem' }}>
                    PII exposure health (10% weight)
                  </span>
                </div>
              </div>
            </div>

            <div
              style={{
                marginTop: '16px',
                paddingTop: '12px',
                borderTop: '1px solid var(--border-subtle)',
                fontSize: '0.78rem',
                color: 'var(--text-muted)',
              }}
            >
              Each subsystem remains separately identifiable without conflating exposure with data corruption.
            </div>
          </div>
        </div>
      )}

      {/* 3. Issue Summary KPIs */}
      {summary && (
        <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '12px', marginBottom: '24px' }}>
          <div className="stat-card" style={{ padding: '14px' }}>
            <div className="flex-col">
              <span className="stat-label">Total Issues</span>
              <div className="stat-value" style={{ fontSize: '1.4rem' }}>{summary.total_issues}</div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>Deduplicated</span>
            </div>
          </div>

          <div className="stat-card" style={{ padding: '14px', borderLeft: '3px solid #f43f5e' }}>
            <div className="flex-col">
              <span className="stat-label" style={{ color: '#f43f5e' }}>Critical</span>
              <div className="stat-value" style={{ fontSize: '1.4rem', color: '#f43f5e' }}>{summary.critical_issues}</div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>Immediate action</span>
            </div>
          </div>

          <div className="stat-card" style={{ padding: '14px', borderLeft: '3px solid #f97316' }}>
            <div className="flex-col">
              <span className="stat-label" style={{ color: '#f97316' }}>High</span>
              <div className="stat-value" style={{ fontSize: '1.4rem', color: '#f97316' }}>{summary.high_issues}</div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>Elevated impact</span>
            </div>
          </div>

          <div className="stat-card" style={{ padding: '14px', borderLeft: '3px solid #f59e0b' }}>
            <div className="flex-col">
              <span className="stat-label" style={{ color: '#fbbf24' }}>Medium</span>
              <div className="stat-value" style={{ fontSize: '1.4rem', color: '#fbbf24' }}>{summary.medium_issues}</div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>Moderate impact</span>
            </div>
          </div>

          <div className="stat-card" style={{ padding: '14px', borderLeft: '3px solid #10b981' }}>
            <div className="flex-col">
              <span className="stat-label" style={{ color: '#10b981' }}>Low</span>
              <div className="stat-value" style={{ fontSize: '1.4rem', color: '#10b981' }}>{summary.low_issues}</div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>Minor deviation</span>
            </div>
          </div>

          <div className="stat-card" style={{ padding: '14px', borderLeft: '3px solid #38bdf8' }}>
            <div className="flex-col">
              <span className="stat-label" style={{ color: '#38bdf8' }}>Cols Affected</span>
              <div className="stat-value" style={{ fontSize: '1.4rem', color: '#38bdf8' }}>
                {summary.columns_affected_count}{' '}
                <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', fontWeight: 'normal' }}>
                  / {summary.total_columns_evaluated}
                </span>
              </div>
              <span className="text-muted" style={{ fontSize: '0.72rem' }}>With signals</span>
            </div>
          </div>
        </div>
      )}

      {/* 4. Column Health Cross-Signal Matrix */}
      {summary?.column_health_matrix?.length > 0 && (
        <div className="results-table-card" style={{ marginBottom: '28px' }}>
          <div style={{ padding: '16px 20px', borderBottom: '1px solid var(--border-subtle)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '10px' }}>
            <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: '700', color: 'var(--text-primary)' }}>
              🏛️ Column Cross-Signal Matrix
            </h3>
            <span className="text-muted" style={{ fontSize: '0.78rem' }}>
              Sorted by highest priority & cross-signal consensus
            </span>
          </div>

          <div className="table-responsive">
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ minWidth: '150px' }}>Column Name</th>
                  <th style={{ minWidth: '90px' }}>Type</th>
                  <th style={{ minWidth: '120px' }}>Quality</th>
                  <th style={{ minWidth: '140px' }}>ML Domain / Risk</th>
                  <th style={{ minWidth: '110px' }}>Anomalies</th>
                  <th style={{ minWidth: '120px' }}>PII Exposure</th>
                  <th style={{ minWidth: '120px' }}>Cross-Signals</th>
                  <th style={{ minWidth: '100px', textAlign: 'right' }}>Max Priority</th>
                </tr>
              </thead>
              <tbody>
                {summary.column_health_matrix.map((col) => (
                  <tr key={col.column_name}>
                    <td className="column-name-code" style={{ fontSize: '0.85rem' }}>{col.column_name}</td>
                    <td>
                      <span className="dtype-badge dtype-object" style={{ fontSize: '0.7rem' }}>
                        {col.data_type}
                      </span>
                    </td>
                    <td>
                      {col.quality_status === 'VIOLATION' ? (
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: '600',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'rgba(244, 63, 94, 0.15)',
                            color: '#f43f5e',
                            border: '1px solid rgba(244, 63, 94, 0.3)',
                          }}
                        >
                          {col.quality_issues_count} Violation(s)
                        </span>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '0.78rem' }}>Clean</span>
                      )}
                    </td>
                    <td>
                      <span style={{ color: 'var(--text-primary)', fontWeight: '500', fontSize: '0.82rem' }}>{col.domain}</span>{' '}
                      <span style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>({col.risk_score.toFixed(0)})</span>
                    </td>
                    <td>
                      {col.anomaly_detected ? (
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: '700',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: getSeverityBadge(col.anomaly_severity).bg,
                            color: getSeverityBadge(col.anomaly_severity).color,
                            border: `1px solid ${getSeverityBadge(col.anomaly_severity).border}`,
                          }}
                        >
                          {col.anomaly_severity}
                        </span>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '0.78rem' }}>None</span>
                      )}
                    </td>
                    <td>
                      {col.pii_detected ? (
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: '600',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'rgba(56, 189, 248, 0.15)',
                            color: '#38bdf8',
                            border: '1px solid rgba(56, 189, 248, 0.3)',
                          }}
                        >
                          {col.pii_entities.join(', ')}
                        </span>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '0.78rem' }}>None</span>
                      )}
                    </td>
                    <td>
                      {col.cross_signal_count > 1 ? (
                        <span
                          style={{
                            fontSize: '0.72rem',
                            fontWeight: '700',
                            padding: '2px 6px',
                            borderRadius: '4px',
                            background: 'rgba(99, 102, 241, 0.15)',
                            color: '#a5b4fc',
                            border: '1px solid rgba(99, 102, 241, 0.3)',
                          }}
                        >
                          {col.cross_signal_count} Subsystems
                        </span>
                      ) : col.cross_signal_count === 1 ? (
                        <span className="text-muted" style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>1 Subsystem</span>
                      ) : (
                        <span className="text-muted" style={{ fontSize: '0.78rem', fontFamily: 'var(--font-mono)' }}>0</span>
                      )}
                    </td>
                    <td style={{ textAlign: 'right', fontFamily: 'var(--font-mono)', fontWeight: '700', color: '#38bdf8' }}>
                      {col.highest_priority > 0 ? col.highest_priority.toFixed(1) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Prioritized Issue Table */}
      <div className="glass-card" style={{ padding: '20px', marginBottom: '28px', background: 'var(--bg-card)' }}>
        <div className="flex-row justify-between align-center" style={{ marginBottom: '16px', flexWrap: 'wrap', gap: '12px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.05rem', fontWeight: '700', color: 'var(--text-primary)' }}>
              📑 Prioritized Issue Backlog
            </h2>
            <p className="text-muted" style={{ margin: '3px 0 0 0', fontSize: '0.8rem' }}>
              Ranked by deterministic multi-factor priority score: Severity (30%), Data Impact (25%), Sensitivity (20%), Confidence (15%), Evidence (10%).
            </p>
          </div>

          <div className="flex-row align-center" style={{ gap: '10px', flexWrap: 'wrap' }}>
            {/* Search Input */}
            <input
              type="text"
              placeholder="Filter by column..."
              value={searchColumn}
              onChange={(e) => setSearchColumn(e.target.value)}
              className="form-input"
              style={{ width: '160px', padding: '6px 10px', fontSize: '0.8rem' }}
            />

            {/* Severity Filter */}
            <div className="flex-row align-center" style={{ gap: '2px', background: 'rgba(0,0,0,0.25)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => {
                const active = severityFilter === s;
                return (
                  <button
                    key={s}
                    onClick={() => setSeverityFilter(s)}
                    style={{
                      background: active ? 'var(--bg-card-hover)' : 'transparent',
                      color: active ? '#38bdf8' : 'var(--text-muted)',
                      border: 'none',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      fontWeight: active ? '700' : '500',
                      cursor: 'pointer',
                    }}
                  >
                    {s}
                  </button>
                );
              })}
            </div>

            {/* Source Filter */}
            <div className="flex-row align-center" style={{ gap: '2px', background: 'rgba(0,0,0,0.25)', padding: '2px', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
              {['ALL', 'QUALITY', 'PII', 'RISK', 'ANOMALY'].map((src) => {
                const active = sourceFilter === src;
                return (
                  <button
                    key={src}
                    onClick={() => setSourceFilter(src)}
                    style={{
                      background: active ? 'var(--bg-card-hover)' : 'transparent',
                      color: active ? '#38bdf8' : 'var(--text-muted)',
                      border: 'none',
                      padding: '3px 8px',
                      borderRadius: '4px',
                      fontSize: '0.72rem',
                      fontWeight: active ? '700' : '500',
                      cursor: 'pointer',
                    }}
                  >
                    {src}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Issue Table */}
        <div className="results-table-card" style={{ border: 'none', boxShadow: 'none' }}>
          <div className="table-responsive">
            <table className="data-table" style={{ width: '100%' }}>
              <thead>
                <tr>
                  <th style={{ minWidth: '90px' }}>Priority</th>
                  <th style={{ minWidth: '100px' }}>Severity</th>
                  <th style={{ minWidth: '220px' }}>Issue Title</th>
                  <th style={{ minWidth: '130px' }}>Column / Scope</th>
                  <th style={{ minWidth: '90px' }}>Source</th>
                  <th style={{ minWidth: '120px' }}>Affected Data</th>
                  <th style={{ minWidth: '220px' }}>Remediation Action</th>
                  <th style={{ minWidth: '90px', textAlign: 'right' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {filteredIssues.length === 0 ? (
                  <tr>
                    <td colSpan={8} style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
                      {issues.length === 0 ? (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                          <span style={{ fontSize: '1.4rem' }}>✨</span>
                          <span style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '0.95rem' }}>No Issues Detected</span>
                          <span style={{ fontSize: '0.82rem', color: 'var(--text-muted)' }}>
                            This dataset version is healthy with zero data quality violations, sensitive PII exposures, or high-risk anomalies.
                          </span>
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px' }}>
                          <span>No issues match the selected filter criteria.</span>
                          <button
                            onClick={() => {
                              setSeverityFilter('ALL');
                              setSourceFilter('ALL');
                              setSearchColumn('');
                            }}
                            className="btn btn-secondary"
                            style={{ padding: '4px 10px', fontSize: '0.75rem', marginTop: '4px' }}
                          >
                            Reset Filters
                          </button>
                        </div>
                      )}
                    </td>
                  </tr>
                ) : (
                  filteredIssues.map((iss) => {
                    const sBadge = getSeverityBadge(iss.severity);
                    const srcBadge = getSourceBadge(iss.source);
                    return (
                      <tr
                        key={iss.id}
                        onClick={() => setSelectedIssue(iss)}
                        style={{ cursor: 'pointer', transition: 'background 0.15s ease' }}
                      >
                        {/* Priority Score prominent numeric badge */}
                        <td>
                          <span
                            style={{
                              fontFamily: 'var(--font-mono)',
                              fontWeight: '800',
                              fontSize: '0.82rem',
                              padding: '2px 8px',
                              borderRadius: '6px',
                              background: 'rgba(6, 182, 212, 0.15)',
                              color: '#38bdf8',
                              border: '1px solid rgba(6, 182, 212, 0.35)',
                            }}
                          >
                            {iss.priority_score.toFixed(1)}
                          </span>
                        </td>

                        {/* Severity Badge */}
                        <td>
                          <span
                            style={{
                              fontSize: '0.72rem',
                              fontWeight: '700',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: sBadge.bg,
                              color: sBadge.color,
                              border: `1px solid ${sBadge.border}`,
                            }}
                          >
                            {iss.severity}
                          </span>
                        </td>

                        {/* Issue Title */}
                        <td>
                          <span style={{ fontWeight: '600', color: 'var(--text-primary)', fontSize: '0.85rem' }}>
                            {iss.title}
                          </span>
                        </td>

                        {/* Column / Scope */}
                        <td>
                          <span className="column-name-code" style={{ fontSize: '0.82rem' }}>
                            {iss.column_name || <span className="text-muted" style={{ fontStyle: 'italic' }}>Dataset-wide</span>}
                          </span>
                        </td>

                        {/* Source Tag */}
                        <td>
                          <span
                            style={{
                              fontSize: '0.7rem',
                              fontWeight: '600',
                              padding: '2px 6px',
                              borderRadius: '4px',
                              background: srcBadge.bg,
                              color: srcBadge.color,
                              border: `1px solid ${srcBadge.border}`,
                            }}
                          >
                            {iss.source}
                          </span>
                        </td>

                        {/* Affected Data */}
                        <td>
                          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                            {iss.affected_percentage.toFixed(1)}% <span className="text-muted">({iss.affected_rows}r)</span>
                          </span>
                        </td>

                        {/* Remediation Action Summary */}
                        <td style={{ maxWidth: '240px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                          {iss.recommendation?.summary || 'Investigate issue details'}
                        </td>

                        {/* Action button */}
                        <td style={{ textAlign: 'right' }}>
                          <button className="btn btn--sm btn--secondary">
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
        </div>
      </div>

      {/* 6. Slide-Out Issue Detail Drawer */}
      {selectedIssue && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 1000,
            background: 'rgba(0, 0, 0, 0.65)',
            backdropFilter: 'blur(8px)',
            display: 'flex',
            justifyContent: 'flex-end',
          }}
          onClick={() => setSelectedIssue(null)}
        >
          <div
            style={{
              width: '100%',
              maxWidth: '680px',
              height: '100%',
              background: 'var(--bg-secondary)',
              borderLeft: '1px solid var(--border-medium)',
              boxShadow: 'var(--shadow-lg)',
              padding: '24px',
              overflowY: 'auto',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'space-between',
              gap: '20px',
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex-col" style={{ gap: '20px' }}>
              {/* Drawer Header */}
              <div className="flex-row justify-between align-center" style={{ borderBottom: '1px solid var(--border-subtle)', paddingBottom: '16px' }}>
                <div>
                  <div className="flex-row align-center" style={{ gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: '700',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: getSeverityBadge(selectedIssue.severity).bg,
                        color: getSeverityBadge(selectedIssue.severity).color,
                        border: `1px solid ${getSeverityBadge(selectedIssue.severity).border}`,
                      }}
                    >
                      {selectedIssue.severity} Severity
                    </span>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: '600',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        background: getSourceBadge(selectedIssue.source).bg,
                        color: getSourceBadge(selectedIssue.source).color,
                        border: `1px solid ${getSourceBadge(selectedIssue.source).border}`,
                      }}
                    >
                      {selectedIssue.source} Signal
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.75rem',
                        color: '#38bdf8',
                        background: 'rgba(6, 182, 212, 0.15)',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(6, 182, 212, 0.35)',
                      }}
                    >
                      Priority: {selectedIssue.priority_score.toFixed(1)} / 100
                    </span>
                  </div>
                  <h2 style={{ margin: 0, fontSize: '1.3rem', fontWeight: '700', color: 'var(--text-primary)' }}>
                    {selectedIssue.title}
                  </h2>
                  <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.8rem', fontFamily: 'var(--font-mono)' }}>
                    Target: {selectedIssue.column_name || 'Dataset-Wide'} • Category: {selectedIssue.issue_type}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedIssue(null)}
                  className="btn btn--sm btn--secondary"
                  style={{ fontSize: '1rem', padding: '6px 12px' }}
                >
                  ✕
                </button>
              </div>

              {/* 1. Issue Overview & Affected Data */}
              <div className="glass-card" style={{ padding: '16px', background: 'var(--bg-card)' }}>
                <span className="stat-label" style={{ display: 'block', marginBottom: '6px' }}>
                  Issue Overview & Impact
                </span>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: '1.6', margin: 0 }}>
                  {selectedIssue.description}
                </p>
                <div className="flex-row align-center" style={{ gap: '12px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed var(--border-subtle)' }}>
                  <span>Affected Rows: <strong style={{ color: 'var(--text-primary)' }}>{selectedIssue.affected_rows}</strong></span>
                  <span>•</span>
                  <span>Affected Data: <strong style={{ color: 'var(--text-primary)' }}>{selectedIssue.affected_percentage.toFixed(2)}%</strong></span>
                </div>
              </div>

              {/* 2. Priority Score Component Breakdown with Visual Progress Bars */}
              <div style={{ padding: '16px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                <span className="stat-label" style={{ display: 'block', marginBottom: '12px', color: '#38bdf8' }}>
                  Priority Score Component Breakdown
                </span>
                <div className="flex-col" style={{ gap: '10px' }}>
                  {/* Severity Factor */}
                  <div>
                    <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                      <span>Severity (30% weight)</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedIssue.severity}</span>
                    </div>
                    <div style={{ width: '100%', height: '5px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          background: '#f43f5e',
                          width: `${
                            selectedIssue.severity === 'CRITICAL'
                              ? 100
                              : selectedIssue.severity === 'HIGH'
                              ? 75
                              : selectedIssue.severity === 'MEDIUM'
                              ? 50
                              : 25
                          }%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Affected Data */}
                  <div>
                    <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                      <span>Affected Data Impact (25% weight)</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedIssue.affected_percentage.toFixed(1)}%</span>
                    </div>
                    <div style={{ width: '100%', height: '5px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          background: '#f97316',
                          width: `${Math.min(100, selectedIssue.affected_percentage)}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Sensitivity */}
                  <div>
                    <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                      <span>Data Sensitivity Heuristic (20% weight)</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedIssue.sensitivity_score.toFixed(1)} / 100</span>
                    </div>
                    <div style={{ width: '100%', height: '5px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          background: '#fbbf24',
                          width: `${selectedIssue.sensitivity_score}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Confidence */}
                  <div>
                    <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                      <span>Confidence Heuristic (15% weight)</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedIssue.confidence_score.toFixed(1)} / 100</span>
                    </div>
                    <div style={{ width: '100%', height: '5px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          background: '#38bdf8',
                          width: `${selectedIssue.confidence_score}%`,
                        }}
                      />
                    </div>
                  </div>

                  {/* Cross-Signal Evidence */}
                  <div>
                    <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '3px' }}>
                      <span>Cross-Signal Evidence Score (10% weight)</span>
                      <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>{selectedIssue.evidence_score.toFixed(1)} / 100</span>
                    </div>
                    <div style={{ width: '100%', height: '5px', background: 'var(--bg-input)', borderRadius: '3px', overflow: 'hidden' }}>
                      <div
                        style={{
                          height: '100%',
                          background: '#818cf8',
                          width: `${selectedIssue.evidence_score}%`,
                        }}
                      />
                    </div>
                  </div>
                </div>
              </div>

              {/* 3. Actionable Remediation Guidance */}
              {selectedIssue.recommendation && (
                <div
                  style={{
                    padding: '16px',
                    borderRadius: '8px',
                    background: 'rgba(6, 182, 212, 0.06)',
                    border: '1px solid rgba(6, 182, 212, 0.25)',
                  }}
                >
                  <div className="flex-row align-center" style={{ gap: '8px', marginBottom: '12px' }}>
                    <span style={{ fontSize: '1.1rem' }}>🛠️</span>
                    <h3 style={{ margin: 0, fontSize: '0.92rem', fontWeight: '700', color: '#38bdf8', textTransform: 'uppercase' }}>
                      Recommended Remediation Plan
                    </h3>
                  </div>

                  {/* Why this matters */}
                  <div style={{ marginBottom: '12px' }}>
                    <span className="stat-label" style={{ display: 'block', marginBottom: '4px' }}>
                      Why This Matters:
                    </span>
                    <p style={{ fontSize: '0.82rem', color: 'var(--text-primary)', margin: 0, lineHeight: '1.5' }}>
                      {selectedIssue.recommendation.summary}
                    </p>
                  </div>

                  {/* Investigation Steps */}
                  {selectedIssue.recommendation.investigation_steps?.length > 0 && (
                    <div style={{ marginBottom: '12px' }}>
                      <span className="stat-label" style={{ display: 'block', marginBottom: '4px', color: '#38bdf8' }}>
                        Recommended Investigation Steps:
                      </span>
                      <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                        {selectedIssue.recommendation.investigation_steps.map((step, idx) => (
                          <li key={idx}>{step}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Preventive Measures */}
                  {selectedIssue.recommendation.preventive_measures?.length > 0 && (
                    <div style={{ marginBottom: '12px' }}>
                      <span className="stat-label" style={{ display: 'block', marginBottom: '4px', color: '#38bdf8' }}>
                        Preventive & Safeguard Measures:
                      </span>
                      <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                        {selectedIssue.recommendation.preventive_measures.map((prev, idx) => (
                          <li key={idx}>{prev}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Caution Warning Box */}
                  {selectedIssue.recommendation.caution_note && (
                    <div
                      style={{
                        padding: '10px 12px',
                        borderRadius: '6px',
                        background: 'rgba(245, 158, 11, 0.1)',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                        fontSize: '0.78rem',
                        color: '#fde68a',
                        display: 'flex',
                        alignItems: 'flex-start',
                        gap: '6px',
                      }}
                    >
                      <span>⚠️</span>
                      <span style={{ lineHeight: '1.5' }}>{selectedIssue.recommendation.caution_note}</span>
                    </div>
                  )}
                </div>
              )}

              {/* 4. Diagnostic Evidence Details */}
              {selectedIssue.evidence && Object.keys(selectedIssue.evidence).length > 0 && (
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '8px' }}>
                    <span className="stat-label">Underlying Diagnostic Evidence</span>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(selectedIssue.evidence, null, 2), 'evidence')}
                      className="btn btn--sm btn--secondary"
                      style={{ fontSize: '0.75rem' }}
                    >
                      {copiedKey === 'evidence' ? '✓ Copied' : 'Copy Evidence JSON'}
                    </button>
                  </div>
                  <pre
                    style={{
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.78rem',
                      color: 'var(--text-muted)',
                      background: 'rgba(0,0,0,0.3)',
                      padding: '10px',
                      borderRadius: '6px',
                      overflowX: 'auto',
                      maxHeight: '160px',
                      margin: 0,
                    }}
                  >
                    {JSON.stringify(selectedIssue.evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="flex-row justify-between align-center" style={{ paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
              <span className="text-muted" style={{ fontSize: '0.78rem' }}>DataGuard AI Prioritization Engine</span>
              <button
                onClick={() => setSelectedIssue(null)}
                className="btn btn--primary"
              >
                Close Inspector
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
