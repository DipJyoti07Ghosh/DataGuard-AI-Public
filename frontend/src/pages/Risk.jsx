import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getRiskPredictions, predictRisk } from '../api/client';

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

  // Selected column for explainability drawer / modal
  const [selectedColumn, setSelectedColumn] = useState(null);

  useEffect(() => {
    fetchRiskData();
  }, [datasetId, versionId]);

  async function fetchRiskData(force = false) {
    if (force) {
      setRecomputing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      const data = force
        ? await predictRisk(datasetId, versionId, true)
        : await getRiskPredictions(datasetId, versionId);
      setRiskData(data);
      // Preselect first column if available
      if (data.predictions && data.predictions.length > 0 && !selectedColumn) {
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
    if (l === 'CRITICAL') {
      return {
        label: 'CRITICAL',
        icon: '🚨',
        color: '#f43f5e',
        bg: 'rgba(244, 63, 94, 0.15)',
        border: 'rgba(244, 63, 94, 0.4)',
      };
    }
    if (l === 'HIGH') {
      return {
        label: 'HIGH',
        icon: '🔴',
        color: '#f97316',
        bg: 'rgba(249, 115, 22, 0.15)',
        border: 'rgba(249, 115, 22, 0.4)',
      };
    }
    if (l === 'MEDIUM') {
      return {
        label: 'MEDIUM',
        icon: '🟡',
        color: '#eab308',
        bg: 'rgba(234, 179, 8, 0.15)',
        border: 'rgba(234, 179, 8, 0.4)',
      };
    }
    return {
      label: 'LOW',
      icon: '🟢',
      color: '#10b981',
      bg: 'rgba(16, 185, 129, 0.15)',
      border: 'rgba(16, 185, 129, 0.4)',
    };
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
    if (score >= 60) return '#f97316';
    if (score >= 35) return '#eab308';
    return '#10b981';
  }

  if (loading) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '48px', maxWidth: '450px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', marginBottom: '20px' }}></div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem' }}>Running ML Risk Pipeline...</h2>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            Extracting feature vectors and classifying column domains with scikit-learn model.
          </p>
        </div>
      </div>
    );
  }

  if (error || !riskData) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '40px', maxWidth: '500px', textAlign: 'center' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>⚠️</div>
          <h2 style={{ margin: '0 0 8px 0', color: 'var(--danger-color)' }}>ML Prediction Error</h2>
          <p className="text-muted" style={{ marginBottom: '24px' }}>{error || 'Unable to load column risk predictions.'}</p>
          <div className="flex-row" style={{ gap: '12px' }}>
            <button className="btn btn-primary" onClick={() => fetchRiskData(true)}>
              Retry ML Risk Analysis
            </button>
            <Link to="/datasets" className="btn btn-secondary">
              Back to Datasets
            </Link>
          </div>
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

  const filteredPredictions = predictions.filter(p => {
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

  const overallRiskBadge = getRiskBadge(overall_risk_level);

  return (
    <div className="page-container" style={{ paddingBottom: '60px' }}>
      {/* Top Header */}
      <div className="flex-row justify-between align-center" style={{ marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="flex-row align-center" style={{ gap: '12px', marginBottom: '6px' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>
              🤖 ML Column Risk & Domain Classification
            </h1>
            <span className="badge badge-primary" style={{ fontSize: '0.85rem', padding: '4px 10px' }}>
              V{version_number}
            </span>
            <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)', background: 'rgba(255,255,255,0.06)', padding: '2px 8px', borderRadius: '6px' }}>
              {model_version}
            </span>
          </div>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.95rem' }}>
            Dataset: <strong style={{ color: 'var(--text-color)' }}>{dataset_name}</strong> • Predicted on {new Date(predicted_at).toLocaleString()}
          </p>
        </div>

        <div className="flex-row" style={{ gap: '12px', alignItems: 'center' }}>
          <button
            className="btn btn-secondary flex-row align-center"
            style={{ gap: '8px' }}
            onClick={() => fetchRiskData(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <div className="spinner-sm"></div>
                <span>Predicting...</span>
              </>
            ) : (
              <>
                <span>🔄</span>
                <span>Re-predict</span>
              </>
            )}
          </button>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/profile`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>📊</span>
            <span>Profile</span>
          </Link>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/quality`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>🛡</span>
            <span>Quality</span>
          </Link>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/pii`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>🔐</span>
            <span>PII Scan</span>
          </Link>
          <Link to="/datasets" className="btn btn-secondary">
            📁 Datasets
          </Link>
        </div>
      </div>

      {/* Hero Overview Status Banner */}
      <div
        className="glass-card flex-row justify-between align-center"
        style={{
          padding: '24px 28px',
          marginBottom: '24px',
          borderLeft: `5px solid ${overallRiskBadge.color}`,
        }}
      >
        <div className="flex-row align-center" style={{ gap: '20px' }}>
          <div
            style={{
              width: '64px',
              height: '64px',
              borderRadius: '16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: overallRiskBadge.bg,
              border: `1px solid ${overallRiskBadge.border}`,
              color: overallRiskBadge.color,
            }}
          >
            <span style={{ fontSize: '1.4rem', fontWeight: '800', lineHeight: 1 }}>
              {dataset_risk_index}
            </span>
            <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>/ 100</span>
          </div>
          <div>
            <div className="flex-row align-center" style={{ gap: '10px', marginBottom: '4px' }}>
              <h3 style={{ margin: 0, fontSize: '1.25rem', fontWeight: '600' }}>
                Dataset Risk Index: {dataset_risk_index} / 100
              </h3>
              <span
                style={{
                  padding: '2px 10px',
                  borderRadius: '12px',
                  fontWeight: '700',
                  fontSize: '0.75rem',
                  background: overallRiskBadge.bg,
                  color: overallRiskBadge.color,
                  border: `1px solid ${overallRiskBadge.border}`,
                }}
              >
                {overallRiskBadge.icon} {overall_risk_level} RISK
              </span>
            </div>
            <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
              Analyzed {total_columns} columns using scikit-learn domain classification & multi-factor risk fusion.
              Average model inference confidence: <strong>{Math.round(mean_model_confidence * 100)}%</strong>.
            </p>
          </div>
        </div>
      </div>

      {/* Summary KPI Cards Grid */}
      <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            TOTAL COLUMNS
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800' }}>{total_columns}</span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Evaluated features</span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            CRITICAL RISK (≥80)
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800', color: risk_breakdown.CRITICAL > 0 ? '#f43f5e' : 'var(--text-muted)' }}>
            {risk_breakdown.CRITICAL || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Immediate attention</span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            HIGH RISK (60–79)
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800', color: risk_breakdown.HIGH > 0 ? '#f97316' : 'var(--text-muted)' }}>
            {risk_breakdown.HIGH || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Sensitive PII / Finance</span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            MEDIUM RISK (35–59)
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800', color: risk_breakdown.MEDIUM > 0 ? '#eab308' : 'var(--text-muted)' }}>
            {risk_breakdown.MEDIUM || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Demographic / IP / Loc</span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            LOW RISK (&lt;35)
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800', color: risk_breakdown.LOW > 0 ? '#10b981' : 'var(--text-muted)' }}>
            {risk_breakdown.LOW || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Operational / Metrics</span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.8rem', fontWeight: '500', marginBottom: '4px' }}>
            MEAN CONFIDENCE
          </span>
          <span style={{ fontSize: '1.8rem', fontWeight: '800', color: '#38bdf8' }}>
            {Math.round(mean_model_confidence * 100)}%
          </span>
          <span className="text-muted" style={{ fontSize: '0.75rem', marginTop: '4px' }}>Model calibration</span>
        </div>
      </div>

      {/* Domain Breakdown Filter Chips */}
      {Object.keys(domain_breakdown).length > 0 && (
        <div className="glass-card" style={{ padding: '20px 24px', marginBottom: '24px' }}>
          <h3 style={{ margin: '0 0 12px 0', fontSize: '1rem', fontWeight: '600' }}>
            🏷️ Predicted Semantic Domains
          </h3>
          <div className="flex-row" style={{ flexWrap: 'wrap', gap: '10px' }}>
            {Object.entries(domain_breakdown).map(([domain, count]) => {
              const icon = getDomainIcon(domain);
              const isSelected = selectedDomain === domain;
              return (
                <button
                  key={domain}
                  className="flex-row align-center"
                  onClick={() => setSelectedDomain(isSelected ? 'ALL' : domain)}
                  style={{
                    padding: '6px 14px',
                    borderRadius: '8px',
                    background: isSelected ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                    border: `1px solid ${isSelected ? '#38bdf8' : 'rgba(255, 255, 255, 0.08)'}`,
                    color: isSelected ? '#38bdf8' : 'var(--text-color)',
                    cursor: 'pointer',
                    fontSize: '0.85rem',
                    gap: '6px',
                  }}
                >
                  <span>{icon}</span>
                  <span>{domain}</span>
                  <span style={{ background: 'rgba(255,255,255,0.1)', padding: '1px 6px', borderRadius: '10px', fontSize: '0.75rem', fontWeight: '700' }}>
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Main Content Area: Table + Explainability Drawer */}
      <div className="grid-responsive" style={{ gridTemplateColumns: selectedColumn ? '1.5fr 1fr' : '1fr', gap: '24px', alignItems: 'start' }}>
        {/* Table Panel */}
        <div className="glass-card" style={{ padding: '24px' }}>
          {/* Search & Filter Toolbar */}
          <div className="flex-row justify-between align-center" style={{ marginBottom: '20px', flexWrap: 'wrap', gap: '12px' }}>
            <input
              type="text"
              placeholder="Search column or domain..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              style={{
                width: '100%',
                maxWidth: '260px',
                padding: '8px 12px',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'rgba(0, 0, 0, 0.2)',
                color: 'var(--text-color)',
                fontSize: '0.85rem',
              }}
            />

            <div className="flex-row align-center" style={{ gap: '6px', flexWrap: 'wrap' }}>
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(lvl => (
                <button
                  key={lvl}
                  className={`btn btn-sm ${selectedRiskLevel === lvl ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setSelectedRiskLevel(lvl)}
                  style={{ fontSize: '0.75rem', padding: '4px 10px' }}
                >
                  {lvl}
                </button>
              ))}
            </div>
          </div>

          {/* Table */}
          {filteredPredictions.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px' }}>
              <span style={{ fontSize: '2rem' }}>🔍</span>
              <h3 style={{ margin: '10px 0 4px 0', fontSize: '1rem' }}>No Matching Columns</h3>
              <p className="text-muted" style={{ margin: 0, fontSize: '0.85rem' }}>
                Try adjusting your search query or domain/risk filters.
              </p>
            </div>
          ) : (
            <div style={{ overflowX: 'auto' }}>
              <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left' }}>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>COLUMN</th>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>DOMAIN</th>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>CONFIDENCE</th>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>RISK SCORE</th>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>LEVEL</th>
                    <th style={{ padding: '10px 12px', fontSize: '0.8rem', color: 'var(--text-muted)' }}>ACTION</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPredictions.map(p => {
                    const riskStyle = getRiskBadge(p.risk_level);
                    const domainIcon = getDomainIcon(p.predicted_domain);
                    const isSelected = selectedColumn?.column_name === p.column_name;
                    const confPct = Math.round(p.model_confidence * 100);
                    const scoreColor = getScoreColor(p.risk_score);

                    return (
                      <tr
                        key={p.id}
                        onClick={() => setSelectedColumn(p)}
                        style={{
                          borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                          cursor: 'pointer',
                          background: isSelected ? 'rgba(56, 189, 248, 0.08)' : 'transparent',
                          transition: 'background 0.2s',
                        }}
                      >
                        {/* Column Name */}
                        <td style={{ padding: '12px', fontWeight: '600' }}>
                          <div className="flex-row align-center" style={{ gap: '6px' }}>
                            <code style={{ background: 'rgba(255,255,255,0.08)', padding: '2px 6px', borderRadius: '4px', fontSize: '0.85rem' }}>
                              {p.column_name}
                            </code>
                            {p.pii_signal && (
                              <span title="PII Detected" style={{ fontSize: '0.8rem' }}>🔒</span>
                            )}
                            {p.quality_failure_count > 0 && (
                              <span title={`${p.quality_failure_count} Quality Rule Failures`} style={{ fontSize: '0.8rem' }}>⚠️</span>
                            )}
                          </div>
                        </td>

                        {/* Domain */}
                        <td style={{ padding: '12px' }}>
                          <div className="flex-row align-center" style={{ gap: '6px' }}>
                            <span>{domainIcon}</span>
                            <span style={{ fontSize: '0.85rem', fontWeight: '500' }}>{p.predicted_domain}</span>
                          </div>
                        </td>

                        {/* Model Confidence */}
                        <td style={{ padding: '12px' }}>
                          <div style={{ width: '80px' }}>
                            <span style={{ fontSize: '0.75rem', fontWeight: '700', color: '#38bdf8' }}>
                              {confPct}%
                            </span>
                            <div style={{ height: '4px', width: '100%', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden', marginTop: '2px' }}>
                              <div style={{ height: '100%', width: `${confPct}%`, background: '#38bdf8' }}></div>
                            </div>
                          </div>
                        </td>

                        {/* Risk Score */}
                        <td style={{ padding: '12px' }}>
                          <div style={{ width: '90px' }}>
                            <span style={{ fontSize: '0.85rem', fontWeight: '800', color: scoreColor }}>
                              {p.risk_score}
                            </span>
                            <div style={{ height: '4px', width: '100%', background: 'rgba(255,255,255,0.1)', borderRadius: '2px', overflow: 'hidden', marginTop: '2px' }}>
                              <div style={{ height: '100%', width: `${p.risk_score}%`, background: scoreColor }}></div>
                            </div>
                          </div>
                        </td>

                        {/* Risk Level */}
                        <td style={{ padding: '12px' }}>
                          <span
                            style={{
                              padding: '3px 8px',
                              borderRadius: '6px',
                              fontSize: '0.75rem',
                              fontWeight: '700',
                              background: riskStyle.bg,
                              color: riskStyle.color,
                              border: `1px solid ${riskStyle.border}`,
                            }}
                          >
                            {riskStyle.icon} {p.risk_level}
                          </span>
                        </td>

                        {/* Action */}
                        <td style={{ padding: '12px' }}>
                          <button
                            className="btn btn-sm btn-secondary"
                            style={{ padding: '4px 8px', fontSize: '0.75rem' }}
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
        </div>

        {/* Column Explainability Drawer Panel */}
        {selectedColumn && (
          <div className="glass-card" style={{ padding: '24px', position: 'sticky', top: '24px' }}>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '16px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px' }}>
              <div>
                <span className="text-muted" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px' }}>
                  Column Explainability
                </span>
                <h3 style={{ margin: '2px 0 0 0', fontSize: '1.2rem', fontWeight: '700' }}>
                  <code>{selectedColumn.column_name}</code>
                </h3>
              </div>
              <span
                style={{
                  padding: '4px 10px',
                  borderRadius: '6px',
                  fontWeight: '700',
                  fontSize: '0.8rem',
                  ...getRiskBadge(selectedColumn.risk_level),
                }}
              >
                {selectedColumn.risk_level} ({selectedColumn.risk_score}/100)
              </span>
            </div>

            {/* Prediction Info */}
            <div style={{ background: 'rgba(255,255,255,0.03)', padding: '14px', borderRadius: '10px', marginBottom: '16px', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="flex-row justify-between" style={{ fontSize: '0.85rem', marginBottom: '6px' }}>
                <span className="text-muted">ML Domain:</span>
                <strong>{getDomainIcon(selectedColumn.predicted_domain)} {selectedColumn.predicted_domain}</strong>
              </div>
              <div className="flex-row justify-between" style={{ fontSize: '0.85rem', marginBottom: '6px' }}>
                <span className="text-muted">Model Confidence:</span>
                <strong style={{ color: '#38bdf8' }}>{Math.round(selectedColumn.model_confidence * 100)}%</strong>
              </div>
              <div className="flex-row justify-between" style={{ fontSize: '0.85rem' }}>
                <span className="text-muted">Model Pipeline:</span>
                <code style={{ fontSize: '0.75rem' }}>{selectedColumn.model_version}</code>
              </div>
            </div>

            {/* Score Decomposition */}
            {selectedColumn.explanation?.score_components && (
              <div style={{ marginBottom: '16px' }}>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Score Components
                </h4>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.8rem' }}>
                  <div style={{ background: 'rgba(244,63,94,0.08)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(244,63,94,0.2)' }}>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>PII WEIGHT</div>
                    <strong style={{ color: '#f43f5e', fontSize: '1rem' }}>+{selectedColumn.explanation.score_components.pii_contribution}</strong>
                  </div>
                  <div style={{ background: 'rgba(249,115,22,0.08)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(249,115,22,0.2)' }}>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>DOMAIN SENSITIVITY</div>
                    <strong style={{ color: '#f97316', fontSize: '1rem' }}>+{selectedColumn.explanation.score_components.domain_contribution}</strong>
                  </div>
                  <div style={{ background: 'rgba(234,179,8,0.08)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(234,179,8,0.2)' }}>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>UNIQUENESS</div>
                    <strong style={{ color: '#eab308', fontSize: '1rem' }}>+{selectedColumn.explanation.score_components.uniqueness_contribution}</strong>
                  </div>
                  <div style={{ background: 'rgba(56,189,248,0.08)', padding: '8px', borderRadius: '6px', border: '1px solid rgba(56,189,248,0.2)' }}>
                    <div className="text-muted" style={{ fontSize: '0.7rem' }}>QUALITY ANOMALIES</div>
                    <strong style={{ color: '#38bdf8', fontSize: '1rem' }}>+{selectedColumn.explanation.score_components.quality_contribution}</strong>
                  </div>
                </div>
              </div>
            )}

            {/* Risk Factors */}
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: '#f43f5e', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>⚠️</span> Risk Factors
              </h4>
              {selectedColumn.explanation?.risk_factors && selectedColumn.explanation.risk_factors.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.85rem', lineHeight: '1.5' }}>
                  {selectedColumn.explanation.risk_factors.map((factor, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>{factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>No critical risk factors identified.</p>
              )}
            </div>

            {/* Protective Factors */}
            <div style={{ marginBottom: '16px' }}>
              <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: '#10b981', textTransform: 'uppercase', display: 'flex', alignItems: 'center', gap: '4px' }}>
                <span>🛡</span> Protective Factors
              </h4>
              {selectedColumn.explanation?.protective_factors && selectedColumn.explanation.protective_factors.length > 0 ? (
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.85rem', lineHeight: '1.5' }}>
                  {selectedColumn.explanation.protective_factors.map((factor, idx) => (
                    <li key={idx} style={{ marginBottom: '4px' }}>{factor}</li>
                  ))}
                </ul>
              ) : (
                <p className="text-muted" style={{ fontSize: '0.8rem', margin: 0 }}>No protective factors identified.</p>
              )}
            </div>

            {/* Feature Snapshot */}
            {selectedColumn.feature_snapshot && (
              <div>
                <h4 style={{ margin: '0 0 8px 0', fontSize: '0.85rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>
                  Feature Snapshot
                </h4>
                <div style={{ background: 'rgba(0,0,0,0.25)', padding: '10px', borderRadius: '6px', fontSize: '0.75rem', fontFamily: 'monospace' }}>
                  <div>Missingness: {selectedColumn.feature_snapshot.missing_pct}%</div>
                  <div>Uniqueness: {selectedColumn.feature_snapshot.unique_pct}%</div>
                  <div>Cardinality: {selectedColumn.feature_snapshot.cardinality}</div>
                  <div>Numeric: {selectedColumn.feature_snapshot.is_numeric ? 'True' : 'False'}</div>
                  <div>String: {selectedColumn.feature_snapshot.is_string ? 'True' : 'False'}</div>
                  {selectedColumn.feature_snapshot.has_pii ? (
                    <div style={{ color: '#f43f5e' }}>PII Signal: Present ({Math.round((selectedColumn.feature_snapshot.pii_confidence || 0) * 100)}% conf)</div>
                  ) : null}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
