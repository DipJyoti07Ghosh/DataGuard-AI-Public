/**
 * DataGuard AI — Data Quality Scorecard
 *
 * Renders the quality evaluation for a dataset version:
 * - Overall score + grade ring
 * - Pass / fail KPI counters
 * - Major quality problems banner
 * - Category breakdown with click-to-filter
 * - Failed rules table
 * - Collapsible passed rules table
 *
 * Visual design: DATA GUARD AI workspace skin (.ql-* classes).
 * Backend contract: UNCHANGED.
 *   - getQuality() / generateQuality()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getQuality, generateQuality } from '../api/client';
import './Quality.css';

export default function Quality() {
  const { datasetId, versionId } = useParams();
  const [quality, setQuality] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState(null);
  const [selectedCategory, setSelectedCategory] = useState('ALL');
  const [showPassed, setShowPassed] = useState(false);

  useEffect(() => {
    fetchQuality();
  }, [datasetId, versionId]);

  async function fetchQuality(force = false) {
    if (force) {
      setRecomputing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      let data;
      if (force) {
        data = await generateQuality(datasetId, versionId, true);
      } else {
        data = await getQuality(datasetId, versionId);
      }
      setQuality(data);
    } catch (err) {
      console.error('Failed to load quality results:', err);
      setError(err.message || 'Failed to load data quality validation results.');
    } finally {
      setLoading(false);
      setRecomputing(false);
    }
  }

  function getGradeColor(score) {
    if (score >= 90) return { bg: 'rgba(16, 185, 129, 0.15)', text: '#34d399', border: 'rgba(16, 185, 129, 0.4)' };
    if (score >= 75) return { bg: 'rgba(59, 130, 246, 0.15)', text: '#60a5fa', border: 'rgba(59, 130, 246, 0.4)' };
    if (score >= 50) return { bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.4)' };
    return { bg: 'rgba(244, 63, 94, 0.15)', text: '#f43f5e', border: 'rgba(244, 63, 94, 0.4)' };
  }

  function getCategoryIcon(cat) {
    switch (cat) {
      case 'Missing Data': return '🔍';
      case 'Schema / Type': return '📐';
      case 'Range / Distribution': return '📊';
      case 'Uniqueness': return '🔑';
      case 'Duplicate Data': return '👥';
      case 'Categorical Consistency': return '🔤';
      default: return '🛡';
    }
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="ql-page">
        <div className="ql-loading">
          <span className="ql-spinner" aria-hidden="true" />
          <p>Running Quality Engine…</p>
        </div>
      </div>
    );
  }

  // ---------- Error ----------
  if (error || !quality) {
    return (
      <div className="ql-page">
        <div className="ql-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>Quality Evaluation Error</strong>
            <p>{error || 'Unable to load quality scorecard.'}</p>
          </div>
        </div>
        <div className="ql-error-actions">
          <button
            className="ql-btn ql-btn--primary"
            onClick={() => fetchQuality(true)}
            disabled={recomputing}
          >
            Retry Quality Check
          </button>
          <Link to="/datasets" className="ql-btn ql-btn--ghost">
            Back to Datasets
          </Link>
        </div>
      </div>
    );
  }

  const {
    overall_score,
    grade,
    total_expectations,
    passed_expectations,
    failed_expectations,
    summary,
    failed_rules,
    passed_rules,
  } = quality;

  const gradeColors = getGradeColor(overall_score);
  const categories = summary?.categories || {};
  const majorProblems = summary?.major_quality_problems || [];

  const displayedFailed =
    selectedCategory === 'ALL'
      ? failed_rules
      : failed_rules.filter((r) => r.category === selectedCategory);

  const displayedPassed =
    selectedCategory === 'ALL'
      ? passed_rules
      : passed_rules.filter((r) => r.category === selectedCategory);

  const passRate =
    total_expectations > 0
      ? Math.round((passed_expectations / total_expectations) * 100)
      : 100;

  return (
    <div className="ql-page">
      {/* ================= HERO ================= */}
      <header className="ql-hero">
        <div className="ql-hero-info">
          <div className="ql-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{quality.dataset_name}</span>
            <span className="ql-version-pill">V{quality.version_number}</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>Data Quality Scorecard</h1>
          <p>
            Evaluated on {new Date(quality.evaluated_at).toLocaleString()}
          </p>
        </div>

        <div className="ql-hero-actions">
          <button
            className="ql-btn ql-btn--ghost"
            onClick={() => fetchQuality(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <span className="ql-spinner ql-spinner--sm" /> Evaluating…
              </>
            ) : (
              '🔄 Re-evaluate'
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/profile`}
            className="ql-btn ql-btn--ghost"
          >
            📊 View Profile
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="ql-btn ql-btn--ghost"
          >
            🔐 Scan for PII
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/risk`}
            className="ql-btn ql-btn--ghost"
          >
            🤖 ML Risk
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
            className="ql-btn ql-btn--ghost ql-btn--amber"
          >
            ⚠ Anomalies
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="ql-btn ql-btn--primary"
          >
            🎯 Prioritization
          </Link>
        </div>
      </header>

      {/* ================= SCORE RING + KPI ================= */}
      <section className="ql-score-panel">
        <div className="ql-score-ring-wrap">
          <div
            className="ql-score-ring"
            style={{
              background: `conic-gradient(${gradeColors.text} ${overall_score * 3.6}deg, rgba(148,163,184,0.12) 0deg)`,
            }}
          >
            <div className="ql-score-inner">
              <strong style={{ color: gradeColors.text }}>{overall_score}</strong>
              <small>/ 100</small>
            </div>
          </div>
          <span
            className="ql-grade-pill"
            style={{
              background: gradeColors.bg,
              color: gradeColors.text,
              borderColor: gradeColors.border,
            }}
          >
            {grade}
          </span>
        </div>

        <div className="ql-kpi-grid">
          <Kpi
            tone="success"
            label="Passed Checks"
            value={passed_expectations}
            sub="Rules verified clean"
          />
          <Kpi
            tone={failed_expectations > 0 ? 'danger' : 'success'}
            label="Failed Checks"
            value={failed_expectations}
            sub={failed_expectations > 0 ? 'Action required' : 'No issues'}
          />
          <Kpi
            tone="info"
            label="Total Rules"
            value={total_expectations}
            sub="Automated checks"
          />
          <Kpi
            tone={passRate >= 90 ? 'success' : passRate >= 70 ? 'warning' : 'danger'}
            label="Pass Rate"
            value={`${passRate}%`}
            sub="Overall integrity"
          />
        </div>
      </section>

      {/* ================= MAJOR PROBLEMS ================= */}
      {majorProblems.length > 0 && (
        <section className="ql-problems">
          <div className="ql-problems-head">
            <span>🚨</span>
            <h3>
              Action Required: {majorProblems.length} High-Priority Quality Issue
              {majorProblems.length > 1 ? 's' : ''} Detected
            </h3>
          </div>
          <ul>
            {majorProblems.map((prob, idx) => (
              <li key={idx}>{prob}</li>
            ))}
          </ul>
        </section>
      )}

      {/* ================= CATEGORY BREAKDOWN ================= */}
      {Object.keys(categories).length > 0 && (
        <section className="ql-cat-section">
          <div className="ql-section-head">
            <h2>Quality Category Breakdown</h2>
            {selectedCategory !== 'ALL' && (
              <button
                className="ql-btn ql-btn--ghost ql-btn--xs"
                onClick={() => setSelectedCategory('ALL')}
              >
                Clear Filter ({selectedCategory})
              </button>
            )}
          </div>

          <div className="ql-cat-grid">
            {Object.entries(categories).map(([catName, catStats]) => {
              const isSelected = selectedCategory === catName;
              const isPassed = catStats.status === 'PASSED';
              const statusColor = isPassed
                ? '#34d399'
                : catStats.pass_rate >= 70
                ? '#fbbf24'
                : '#f43f5e';
              const statusBg = isPassed
                ? 'rgba(16,185,129,.1)'
                : catStats.pass_rate >= 70
                ? 'rgba(245,158,11,.1)'
                : 'rgba(244,63,94,.1)';

              return (
                <button
                  key={catName}
                  type="button"
                  className={`ql-cat-card ${isSelected ? 'ql-cat-card--active' : ''}`}
                  onClick={() => setSelectedCategory(isSelected ? 'ALL' : catName)}
                >
                  <div className="ql-cat-head">
                    <span className="ql-cat-icon">{getCategoryIcon(catName)}</span>
                    <span
                      className="ql-cat-status"
                      style={{
                        background: statusBg,
                        color: statusColor,
                        borderColor: statusColor,
                      }}
                    >
                      {catStats.status}
                    </span>
                  </div>
                  <div className="ql-cat-name">{catName}</div>
                  <div className="ql-cat-meta">
                    <span>
                      {catStats.passed} / {catStats.total} Passed
                    </span>
                    <span style={{ color: statusColor, fontWeight: 800 }}>
                      {catStats.pass_rate}%
                    </span>
                  </div>
                  <div className="ql-cat-track">
                    <div
                      className="ql-cat-fill"
                      style={{ width: `${catStats.pass_rate}%`, background: statusColor }}
                    />
                  </div>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* ================= FAILED RULES ================= */}
      <section className="ql-panel">
        <div className="ql-panel-head">
          <h3>
            ❌ Failed Quality Rules ({displayedFailed.length})
          </h3>
          {selectedCategory !== 'ALL' && (
            <span className="ql-badge ql-badge--accent">Filtered: {selectedCategory}</span>
          )}
        </div>

        {displayedFailed.length === 0 ? (
          <div className="ql-empty">
            <span className="ql-empty-icon">🎉</span>
            <h4>No Failed Rules in this Scope!</h4>
            <p>All evaluated quality expectations met or exceeded integrity baselines.</p>
          </div>
        ) : (
          <div className="ql-table-wrap">
            <table className="ql-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Target Column</th>
                  <th>Rule Evaluated</th>
                  <th>Observed</th>
                  <th>Expected</th>
                  <th>Diagnosis</th>
                </tr>
              </thead>
              <tbody>
                {displayedFailed.map((rule, idx) => (
                  <tr key={idx} className="ql-row-failed">
                    <td>
                      <span className="ql-badge ql-badge--neutral">
                        {getCategoryIcon(rule.category)} {rule.category}
                      </span>
                    </td>
                    <td>
                      <code className="ql-col-code">
                        {rule.column_name || '(Dataset Level)'}
                      </code>
                    </td>
                    <td>
                      <code className="ql-expect">{rule.expectation_type}</code>
                    </td>
                    <td className="ql-observed">{rule.observed_value}</td>
                    <td className="ql-muted">{rule.expected_value}</td>
                    <td className="ql-diag">
                      {rule.failure_message || 'Quality threshold violation.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ================= PASSED RULES (collapsible) ================= */}
      <section className="ql-panel">
        <button
          type="button"
          className="ql-collapse-head"
          onClick={() => setShowPassed(!showPassed)}
        >
          <span className="ql-collapse-title">
            ✅ Passed Quality Rules ({displayedPassed.length})
          </span>
          <span className="ql-collapse-toggle">
            {showPassed ? '▲ Hide' : '▼ Show'}
          </span>
        </button>

        {showPassed && (
          <div className="ql-table-wrap ql-table-wrap--mt">
            <table className="ql-table">
              <thead>
                <tr>
                  <th>Category</th>
                  <th>Target Column</th>
                  <th>Rule Evaluated</th>
                  <th>Observed</th>
                  <th>Expected</th>
                  <th>Status</th>
                </tr>
              </thead>
              <tbody>
                {displayedPassed.map((rule, idx) => (
                  <tr key={idx}>
                    <td>
                      <span className="ql-badge ql-badge--neutral">
                        {getCategoryIcon(rule.category)} {rule.category}
                      </span>
                    </td>
                    <td>
                      <code className="ql-col-code">
                        {rule.column_name || '(Dataset Level)'}
                      </code>
                    </td>
                    <td>
                      <code className="ql-expect ql-expect--muted">
                        {rule.expectation_type}
                      </code>
                    </td>
                    <td>{rule.observed_value}</td>
                    <td className="ql-muted">{rule.expected_value}</td>
                    <td>
                      <span className="ql-badge ql-badge--success">PASS</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}

/* ---------- Helper ---------- */
function Kpi({ tone, label, value, sub }) {
  return (
    <div className={`ql-kpi${tone ? ` ql-kpi--${tone}` : ''}`}>
      <small>{label}</small>
      <strong>{value ?? '—'}</strong>
      <em>{sub}</em>
    </div>
  );
}