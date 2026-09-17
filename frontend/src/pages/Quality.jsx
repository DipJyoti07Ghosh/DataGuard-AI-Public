import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getQuality, generateQuality } from '../api/client';

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
    if (score >= 90) return { bg: 'rgba(16, 185, 129, 0.15)', text: '#10b981', border: 'rgba(16, 185, 129, 0.3)' };
    if (score >= 75) return { bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' };
    if (score >= 50) return { bg: 'rgba(245, 158, 11, 0.15)', text: '#f59e0b', border: 'rgba(245, 158, 11, 0.3)' };
    return { bg: 'rgba(244, 63, 94, 0.15)', text: '#f43f5e', border: 'rgba(244, 63, 94, 0.3)' };
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

  if (loading) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '48px', maxWidth: '450px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', marginBottom: '20px' }}></div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem' }}>Running Quality Engine...</h2>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            Evaluating Great Expectations quality rules against dataset profiling baseline.
          </p>
        </div>
      </div>
    );
  }

  if (error || !quality) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '40px', maxWidth: '500px', textAlign: 'center' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>⚠️</div>
          <h2 style={{ margin: '0 0 8px 0', color: 'var(--danger-color)' }}>Quality Evaluation Error</h2>
          <p className="text-muted" style={{ marginBottom: '24px' }}>{error || 'Unable to load quality scorecard.'}</p>
          <div className="flex-row" style={{ gap: '12px' }}>
            <button className="btn btn-primary" onClick={() => fetchQuality(true)}>
              Retry Quality Check
            </button>
            <Link to="/datasets" className="btn btn-secondary">
              Back to Datasets
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const { overall_score, grade, total_expectations, passed_expectations, failed_expectations, summary, failed_rules, passed_rules } = quality;
  const gradeColors = getGradeColor(overall_score);
  const categories = summary?.categories || {};
  const majorProblems = summary?.major_quality_problems || [];

  // Filter rules based on category selection
  const displayedFailed = selectedCategory === 'ALL'
    ? failed_rules
    : failed_rules.filter(r => r.category === selectedCategory);

  const displayedPassed = selectedCategory === 'ALL'
    ? passed_rules
    : passed_rules.filter(r => r.category === selectedCategory);

  return (
    <div className="page-container" style={{ paddingBottom: '60px' }}>
      {/* Top Header */}
      <div className="flex-row justify-between align-center" style={{ marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="flex-row align-center" style={{ gap: '12px', marginBottom: '6px' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>
              🛡 Data Quality Scorecard
            </h1>
            <span className="badge badge-primary" style={{ fontSize: '0.85rem', padding: '4px 10px' }}>
              V{quality.version_number}
            </span>
          </div>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.95rem' }}>
            Dataset: <strong style={{ color: 'var(--text-color)' }}>{quality.dataset_name}</strong> • Evaluated on {new Date(quality.evaluated_at).toLocaleString()}
          </p>
        </div>

        <div className="flex-row" style={{ gap: '12px', alignItems: 'center' }}>
          <button
            className="btn btn-secondary flex-row align-center"
            style={{ gap: '8px' }}
            onClick={() => fetchQuality(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <div className="spinner-sm"></div>
                <span>Evaluating...</span>
              </>
            ) : (
              <>
                <span>🔄</span>
                <span>Re-evaluate</span>
              </>
            )}
          </button>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/profile`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>📊</span>
            <span>View Profile</span>
          </Link>
          <Link to="/datasets" className="btn btn-secondary">
            📁 Datasets
          </Link>
        </div>
      </div>

      {/* Main Score & Metrics Hero Banner */}
      <div className="glass-card" style={{ padding: '28px', marginBottom: '28px' }}>
        <div className="grid-responsive" style={{ gridTemplateColumns: 'auto 1fr', gap: '32px', alignItems: 'center' }}>
          {/* Big Score Gauge / Circle */}
          <div
            className="flex-col flex-center"
            style={{
              width: '160px',
              height: '160px',
              borderRadius: '50%',
              background: gradeColors.bg,
              border: `3px solid ${gradeColors.border}`,
              padding: '16px',
              textAlign: 'center',
              boxShadow: `0 0 24px ${gradeColors.bg}`,
            }}
          >
            <span style={{ fontSize: '2.4rem', fontWeight: '800', color: gradeColors.text, lineHeight: 1 }}>
              {overall_score}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '4px' }}>
              / 100
            </span>
            <span
              style={{
                fontSize: '0.75rem',
                fontWeight: '700',
                color: gradeColors.text,
                textTransform: 'uppercase',
                letterSpacing: '1px',
                marginTop: '6px',
                background: 'rgba(0,0,0,0.3)',
                padding: '2px 8px',
                borderRadius: '12px',
              }}
            >
              {grade}
            </span>
          </div>

          {/* KPI Cards Grid */}
          <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '16px' }}>
            <div className="stat-card" style={{ background: 'rgba(16, 185, 129, 0.08)', borderColor: 'rgba(16, 185, 129, 0.2)' }}>
              <span className="stat-label">Passed Checks</span>
              <span className="stat-value" style={{ color: '#10b981' }}>{passed_expectations}</span>
              <span className="stat-sub">Rules verified clean</span>
            </div>

            <div className="stat-card" style={{ background: failed_expectations > 0 ? 'rgba(244, 63, 94, 0.08)' : 'rgba(255, 255, 255, 0.03)', borderColor: failed_expectations > 0 ? 'rgba(244, 63, 94, 0.25)' : 'var(--glass-border)' }}>
              <span className="stat-label">Failed Checks</span>
              <span className="stat-value" style={{ color: failed_expectations > 0 ? '#f43f5e' : 'var(--text-muted)' }}>
                {failed_expectations}
              </span>
              <span className="stat-sub">{failed_expectations > 0 ? 'Action required' : 'No issues'}</span>
            </div>

            <div className="stat-card">
              <span className="stat-label">Total Rules</span>
              <span className="stat-value">{total_expectations}</span>
              <span className="stat-sub">Automated checks</span>
            </div>

            <div className="stat-card">
              <span className="stat-label">Pass Rate</span>
              <span className="stat-value">
                {total_expectations > 0 ? `${Math.round((passed_expectations / total_expectations) * 100)}%` : '100%'}
              </span>
              <span className="stat-sub">Overall integrity</span>
            </div>
          </div>
        </div>
      </div>

      {/* Major Quality Problems Alert Banner */}
      {majorProblems.length > 0 && (
        <div
          className="glass-card"
          style={{
            padding: '20px 24px',
            marginBottom: '28px',
            background: 'rgba(244, 63, 94, 0.08)',
            border: '1px solid rgba(244, 63, 94, 0.3)',
          }}
        >
          <div className="flex-row align-center" style={{ gap: '10px', marginBottom: '12px' }}>
            <span style={{ fontSize: '1.3rem' }}>🚨</span>
            <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#f43f5e', fontWeight: '700' }}>
              Action Required: {majorProblems.length} High-Priority Quality Issue{majorProblems.length > 1 ? 's' : ''} Detected
            </h3>
          </div>
          <div className="flex-col" style={{ gap: '8px' }}>
            {majorProblems.map((prob, idx) => (
              <div
                key={idx}
                className="flex-row align-center"
                style={{
                  gap: '8px',
                  background: 'rgba(0, 0, 0, 0.3)',
                  padding: '10px 14px',
                  borderRadius: '6px',
                  fontSize: '0.9rem',
                }}
              >
                <span style={{ color: '#f43f5e', fontWeight: 'bold' }}>•</span>
                <span>{prob}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quality Breakdown by Category */}
      <div style={{ marginBottom: '28px' }}>
        <div className="flex-row justify-between align-center" style={{ marginBottom: '14px' }}>
          <h2 style={{ margin: 0, fontSize: '1.2rem', fontWeight: '600' }}>
            Quality Category Breakdown
          </h2>
          {selectedCategory !== 'ALL' && (
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => setSelectedCategory('ALL')}
            >
              Clear Filter ({selectedCategory})
            </button>
          )}
        </div>

        <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
          {Object.entries(categories).map(([catName, catStats]) => {
            const isSelected = selectedCategory === catName;
            const isPassed = catStats.status === 'PASSED';
            const statusColor = isPassed ? '#10b981' : catStats.pass_rate >= 70 ? '#f59e0b' : '#f43f5e';
            const statusBg = isPassed ? 'rgba(16, 185, 129, 0.1)' : catStats.pass_rate >= 70 ? 'rgba(245, 158, 11, 0.1)' : 'rgba(244, 63, 94, 0.1)';

            return (
              <div
                key={catName}
                className="glass-card"
                onClick={() => setSelectedCategory(isSelected ? 'ALL' : catName)}
                style={{
                  padding: '16px 18px',
                  cursor: 'pointer',
                  border: isSelected ? `2px solid var(--primary-color)` : `1px solid ${statusBg}`,
                  background: isSelected ? 'rgba(99, 102, 241, 0.12)' : 'var(--glass-bg)',
                  transition: 'all 0.2s ease',
                }}
              >
                <div className="flex-row justify-between align-center" style={{ marginBottom: '10px' }}>
                  <span style={{ fontSize: '1.2rem' }}>{getCategoryIcon(catName)}</span>
                  <span
                    style={{
                      fontSize: '0.75rem',
                      fontWeight: '700',
                      padding: '2px 8px',
                      borderRadius: '10px',
                      background: statusBg,
                      color: statusColor,
                    }}
                  >
                    {catStats.status}
                  </span>
                </div>

                <div style={{ fontWeight: '600', fontSize: '0.95rem', marginBottom: '6px' }}>
                  {catName}
                </div>

                <div className="flex-row justify-between align-center" style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '8px' }}>
                  <span>{catStats.passed} / {catStats.total} Passed</span>
                  <span style={{ color: statusColor, fontWeight: '600' }}>{catStats.pass_rate}%</span>
                </div>

                {/* Progress bar */}
                <div style={{ width: '100%', height: '4px', background: 'rgba(255, 255, 255, 0.1)', borderRadius: '2px', overflow: 'hidden' }}>
                  <div style={{ width: `${catStats.pass_rate}%`, height: '100%', background: statusColor, transition: 'width 0.3s ease' }}></div>
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Failed Quality Rules Section */}
      <div className="glass-card" style={{ padding: '24px', marginBottom: '28px' }}>
        <div className="flex-row justify-between align-center" style={{ marginBottom: '16px' }}>
          <div className="flex-row align-center" style={{ gap: '10px' }}>
            <span style={{ fontSize: '1.2rem' }}>❌</span>
            <h3 style={{ margin: 0, fontSize: '1.15rem', fontWeight: '700' }}>
              Failed Quality Rules ({displayedFailed.length})
            </h3>
          </div>
          {selectedCategory !== 'ALL' && (
            <span className="badge badge-primary">Filtered: {selectedCategory}</span>
          )}
        </div>

        {displayedFailed.length === 0 ? (
          <div className="flex-col flex-center" style={{ padding: '36px', textAlign: 'center' }}>
            <span style={{ fontSize: '2.2rem', marginBottom: '10px' }}>🎉</span>
            <h4 style={{ margin: '0 0 6px 0', color: '#10b981' }}>No Failed Rules in this Scope!</h4>
            <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
              All evaluated quality expectations met or exceeded integrity baselines.
            </p>
          </div>
        ) : (
          <div className="table-container" style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th style={{ width: '140px' }}>Category</th>
                  <th style={{ width: '150px' }}>Target Column</th>
                  <th style={{ minWidth: '220px' }}>Rule Evaluated</th>
                  <th style={{ minWidth: '150px' }}>Observed</th>
                  <th style={{ minWidth: '150px' }}>Expected</th>
                  <th style={{ minWidth: '250px' }}>Diagnosis / Explanation</th>
                </tr>
              </thead>
              <tbody>
                {displayedFailed.map((rule, idx) => (
                  <tr key={idx} style={{ background: 'rgba(244, 63, 94, 0.03)' }}>
                    <td>
                      <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.06)', fontSize: '0.75rem' }}>
                        {getCategoryIcon(rule.category)} {rule.category}
                      </span>
                    </td>
                    <td>
                      <strong style={{ color: 'var(--text-color)', fontFamily: 'monospace' }}>
                        {rule.column_name || '(Dataset Level)'}
                      </strong>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: '#38bdf8' }}>
                      {rule.expectation_type}
                    </td>
                    <td style={{ color: '#f43f5e', fontWeight: '600', fontSize: '0.85rem' }}>
                      {rule.observed_value}
                    </td>
                    <td style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
                      {rule.expected_value}
                    </td>
                    <td style={{ fontSize: '0.85rem', color: '#fca5a5' }}>
                      {rule.failure_message || 'Quality threshold violation.'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Passed Rules Section (Collapsible) */}
      <div className="glass-card" style={{ padding: '20px 24px' }}>
        <div
          className="flex-row justify-between align-center"
          style={{ cursor: 'pointer' }}
          onClick={() => setShowPassed(!showPassed)}
        >
          <div className="flex-row align-center" style={{ gap: '10px' }}>
            <span style={{ fontSize: '1.2rem' }}>✅</span>
            <h3 style={{ margin: 0, fontSize: '1.1rem', fontWeight: '600' }}>
              Passed Quality Rules ({displayedPassed.length})
            </h3>
          </div>
          <button className="btn btn-sm btn-secondary">
            {showPassed ? '▲ Hide Passed Rules' : '▼ Show Passed Rules'}
          </button>
        </div>

        {showPassed && (
          <div className="table-container" style={{ marginTop: '16px', overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th style={{ width: '140px' }}>Category</th>
                  <th style={{ width: '150px' }}>Target Column</th>
                  <th style={{ minWidth: '220px' }}>Rule Evaluated</th>
                  <th style={{ minWidth: '150px' }}>Observed</th>
                  <th style={{ minWidth: '150px' }}>Expected</th>
                  <th style={{ width: '90px' }}>Status</th>
                </tr>
              </thead>
              <tbody>
                {displayedPassed.map((rule, idx) => (
                  <tr key={idx}>
                    <td>
                      <span className="badge" style={{ background: 'rgba(255, 255, 255, 0.06)', fontSize: '0.75rem' }}>
                        {getCategoryIcon(rule.category)} {rule.category}
                      </span>
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.85rem' }}>
                      {rule.column_name || '(Dataset Level)'}
                    </td>
                    <td style={{ fontFamily: 'monospace', fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                      {rule.expectation_type}
                    </td>
                    <td style={{ fontSize: '0.85rem' }}>
                      {rule.observed_value}
                    </td>
                    <td style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                      {rule.expected_value}
                    </td>
                    <td>
                      <span className="badge badge-success" style={{ fontSize: '0.75rem' }}>
                        PASS
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
