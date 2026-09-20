/**
 * DataGuard AI — Anomaly & Outlier Detection Dashboard (Phase 8)
 *
 * Enterprise Data Observability & Statistical Anomaly Dashboard.
 * Displays multi-method statistical (IQR, Z-Score), ML (Isolation Forest),
 * and categorical frequency anomaly findings matching the DataGuard AI design language.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getAnomalies, detectAnomalies } from '../api/client';

export default function Anomalies() {
  const { datasetId, versionId } = useParams();

  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  // Filters & State
  const [selectedSeverity, setSelectedSeverity] = useState('ALL');
  const [selectedMethod, setSelectedMethod] = useState('ALL');
  const [searchCol, setSearchCol] = useState('');
  const [selectedFinding, setSelectedFinding] = useState(null);
  const [copiedKey, setCopiedKey] = useState(null);

  useEffect(() => {
    fetchAnomalies(false);
  }, [datasetId, versionId]);

  async function fetchAnomalies(force = false) {
    if (force) setRecomputing(true);
    else setLoading(true);
    setError(null);

    try {
      let res;
      if (force) {
        res = await detectAnomalies(datasetId, versionId, true);
      } else {
        res = await getAnomalies(datasetId, versionId);
      }
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load anomaly detection results');
    } finally {
      setLoading(false);
      setRecomputing(false);
    }
  }

  const copyToClipboard = (text, key) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  // Severity styling tokens matching DataGuard AI palette
  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return {
          bg: 'rgba(244, 63, 94, 0.15)',
          color: '#f43f5e',
          border: 'rgba(244, 63, 94, 0.35)',
          dot: '#f43f5e',
        };
      case 'HIGH':
        return {
          bg: 'rgba(249, 115, 22, 0.15)',
          color: '#f97316',
          border: 'rgba(249, 115, 22, 0.35)',
          dot: '#f97316',
        };
      case 'MEDIUM':
        return {
          bg: 'rgba(245, 158, 11, 0.15)',
          color: '#f59e0b',
          border: 'rgba(245, 158, 11, 0.35)',
          dot: '#f59e0b',
        };
      case 'LOW':
      default:
        return {
          bg: 'rgba(16, 185, 129, 0.15)',
          color: '#10b981',
          border: 'rgba(16, 185, 129, 0.35)',
          dot: '#10b981',
        };
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return '#f43f5e';
    if (score >= 50) return '#f97316';
    if (score >= 25) return '#f59e0b';
    return '#10b981';
  };

  // Filtered findings
  const findings = data?.findings || [];
  const filteredFindings = findings.filter((f) => {
    if (selectedSeverity !== 'ALL' && f.severity?.toUpperCase() !== selectedSeverity) {
      return false;
    }
    if (selectedMethod !== 'ALL') {
      const activeMethods = f.evidence?.detected_methods || [];
      if (selectedMethod === 'MULTI_METHOD_CONSENSUS') {
        if (f.detection_method !== 'MULTI_METHOD_CONSENSUS') return false;
      } else if (!activeMethods.includes(selectedMethod) && f.detection_method !== selectedMethod) {
        return false;
      }
    }
    if (searchCol.trim()) {
      if (!f.column_name.toLowerCase().includes(searchCol.toLowerCase())) {
        return false;
      }
    }
    return true;
  });

  if (loading) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '48px', maxWidth: '480px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', marginBottom: '20px' }}></div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem' }}>Running Anomaly Detection Engine...</h2>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            Evaluating multi-method statistical (IQR, Z-Score), ML Isolation Forest, and rare categorical distributions.
          </p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '40px', maxWidth: '500px', textAlign: 'center' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>⚠️</div>
          <h2 style={{ margin: '0 0 8px 0', color: 'var(--danger-color, #ef4444)' }}>Anomaly Detection Failed</h2>
          <p className="text-muted" style={{ marginBottom: '24px' }}>{error}</p>
          <div className="flex-row" style={{ gap: '12px' }}>
            <button className="btn btn-primary" onClick={() => fetchAnomalies(true)}>
              Retry Anomaly Detection
            </button>
            <Link to="/datasets" className="btn btn-secondary">
              Back to Datasets
            </Link>
          </div>
        </div>
      </div>
    );
  }

  const scoreBadge = getSeverityBadge(data?.overall_severity);
  const totalRowsAnalyzed = data?.total_rows || data?.total_rows_analyzed || (findings.length > 0 ? findings[0].explanation?.phase7_context?.total_rows : null) || 0;

  return (
    <div className="page-container" style={{ paddingBottom: '60px' }}>
      {/* 1. Header & Navigation Context */}
      <div className="flex-row justify-between align-center" style={{ marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="flex-row align-center" style={{ gap: '10px', marginBottom: '6px', flexWrap: 'wrap' }}>
            <Link to="/datasets" className="text-muted" style={{ fontSize: '0.88rem', textDecoration: 'none' }}>
              ← Datasets
            </Link>
            <span className="text-muted" style={{ opacity: 0.6 }}>/</span>
            <span style={{ fontWeight: '600', fontSize: '0.95rem', color: 'var(--text-primary)' }}>
              {data?.dataset_name || 'Dataset'}
            </span>
            <span className="badge badge-primary" style={{ fontSize: '0.8rem', padding: '3px 8px' }}>
              V{data?.version_number}
            </span>
            <span style={{ fontSize: '0.75rem', color: '#10b981', background: 'rgba(16, 185, 129, 0.12)', border: '1px solid rgba(16, 185, 129, 0.25)', padding: '2px 8px', borderRadius: '12px', fontWeight: '600' }}>
              ● Statistical & ML Engine Active
            </span>
          </div>

          <div className="flex-row align-center" style={{ gap: '10px' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>
              ⚠️ Anomaly & Outlier Detection
            </h1>
          </div>
          <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.92rem' }}>
            Identify statistically unusual patterns and multi-method outliers across your dataset.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex-row align-center" style={{ gap: '10px' }}>
          <button
            className="btn btn-secondary flex-row align-center"
            style={{ gap: '8px' }}
            onClick={() => fetchAnomalies(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <div className="spinner-sm"></div>
                <span>Re-analyzing...</span>
              </>
            ) : (
              <>
                <span>🔄</span>
                <span>Re-run Detection</span>
              </>
            )}
          </button>
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
        <span
          className="btn btn-secondary flex-row align-center"
          style={{
            gap: '6px',
            fontSize: '0.85rem',
            borderColor: 'rgba(245, 158, 11, 0.5)',
            color: '#fbbf24',
            background: 'rgba(245, 158, 11, 0.12)',
            fontWeight: '700',
          }}
        >
          <span>⚠️</span>
          <span>Anomalies</span>
        </span>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/issues`}
          className="btn btn-secondary flex-row align-center"
          style={{ gap: '6px', fontSize: '0.85rem', borderColor: 'rgba(6, 182, 212, 0.4)', color: '#38bdf8' }}
        >
          <span>🎯</span>
          <span>Prioritization</span>
        </Link>
        <Link to="/datasets" className="btn btn-secondary" style={{ fontSize: '0.85rem' }}>
          📁 Datasets
        </Link>
      </div>

      {/* 2. Top KPI Section: 4 Compact Aligned Cards */}
      <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
        {/* Card 1: Anomalies Detected */}
        <div className="stat-card">
          <div className="flex-col" style={{ width: '100%' }}>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '4px' }}>
              <span className="stat-label">Anomalies Detected</span>
              <span style={{ fontSize: '1.2rem' }}>🔍</span>
            </div>
            <div className="stat-value" style={{ color: '#f1f5f9' }}>
              {data?.total_anomalies || 0}
            </div>
            <span className="text-muted" style={{ fontSize: '0.78rem', marginTop: '2px' }}>
              Across all analyzed columns
            </span>
          </div>
        </div>

        {/* Card 2: Columns Affected */}
        <div className="stat-card">
          <div className="flex-col" style={{ width: '100%' }}>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '4px' }}>
              <span className="stat-label" style={{ color: '#fbbf24' }}>Columns Affected</span>
              <span style={{ fontSize: '1.2rem' }}>📐</span>
            </div>
            <div className="stat-value" style={{ color: '#fbbf24' }}>
              {data?.columns_with_anomalies || 0}
              <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)', fontWeight: 'normal', marginLeft: '4px' }}>
                / {data?.total_columns_analyzed || 0}
              </span>
            </div>
            <span className="text-muted" style={{ fontSize: '0.78rem', marginTop: '2px' }}>
              Columns with outlier observations
            </span>
          </div>
        </div>

        {/* Card 3: Rows Analyzed */}
        <div className="stat-card">
          <div className="flex-col" style={{ width: '100%' }}>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '4px' }}>
              <span className="stat-label" style={{ color: '#38bdf8' }}>Rows Analyzed</span>
              <span style={{ fontSize: '1.2rem' }}>📊</span>
            </div>
            <div className="stat-value" style={{ color: '#38bdf8' }}>
              {totalRowsAnalyzed ? totalRowsAnalyzed.toLocaleString() : '100%'}
            </div>
            <span className="text-muted" style={{ fontSize: '0.78rem', marginTop: '2px' }}>
              Dataset population evaluated
            </span>
          </div>
        </div>

        {/* Card 4: Dataset Anomaly Score */}
        <div className="stat-card" style={{ borderLeft: `4px solid ${scoreBadge.color}` }}>
          <div className="flex-col" style={{ width: '100%' }}>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '4px' }}>
              <span className="stat-label">Anomaly Score</span>
              <span
                style={{
                  fontSize: '0.72rem',
                  fontWeight: '700',
                  padding: '2px 8px',
                  borderRadius: '6px',
                  background: scoreBadge.bg,
                  color: scoreBadge.color,
                  border: `1px solid ${scoreBadge.border}`,
                }}
              >
                {data?.overall_severity || 'LOW'}
              </span>
            </div>
            <div className="flex-row align-center" style={{ gap: '6px' }}>
              <span className="stat-value" style={{ color: getScoreColor(data?.dataset_anomaly_score) }}>
                {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
              </span>
              <span className="text-muted" style={{ fontSize: '0.85rem' }}>/ 100</span>
            </div>
            <span className="text-muted" style={{ fontSize: '0.78rem', marginTop: '2px' }}>
              Composite anomaly index
            </span>
          </div>
        </div>
      </div>

      {/* 3. Anomaly Overview & Severity Distribution */}
      <div className="grid-responsive" style={{ gridTemplateColumns: 'minmax(280px, 1fr) 2fr', gap: '20px', marginBottom: '24px' }}>
        {/* Left Hero Card: Composite Anomaly Score Meter */}
        <div
          className="glass-card flex-col justify-between"
          style={{
            padding: '24px',
            borderLeft: `5px solid ${scoreBadge.color}`,
            background: 'var(--bg-card)',
          }}
        >
          <div>
            <div className="flex-row justify-between align-center" style={{ marginBottom: '12px' }}>
              <span className="stat-label">Composite Anomaly Index</span>
              <span
                style={{
                  fontSize: '0.75rem',
                  fontWeight: '700',
                  padding: '2px 8px',
                  borderRadius: '12px',
                  background: scoreBadge.bg,
                  color: scoreBadge.color,
                  border: `1px solid ${scoreBadge.border}`,
                  letterSpacing: '0.05em',
                }}
              >
                ● {data?.overall_severity}
              </span>
            </div>

            <div className="flex-row align-center" style={{ gap: '8px', margin: '12px 0' }}>
              <span style={{ fontSize: '2.8rem', fontWeight: '800', color: getScoreColor(data?.dataset_anomaly_score), lineHeight: 1 }}>
                {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
              </span>
              <span className="text-muted" style={{ fontSize: '1.1rem', fontWeight: '600' }}>/ 100</span>
            </div>

            <p className="text-muted" style={{ fontSize: '0.85rem', lineHeight: '1.5', margin: '8px 0 0 0' }}>
              Consensus score weighted across multi-detector agreement (IQR, Z-Score, Isolation Forest), statistical excursion rates, and sensitive column context.
            </p>
          </div>

          <div
            className="flex-row justify-between align-center"
            style={{
              marginTop: '20px',
              paddingTop: '12px',
              borderTop: '1px solid var(--border-subtle)',
              fontSize: '0.8rem',
              color: 'var(--text-muted)',
            }}
          >
            <span>Last Analyzed:</span>
            <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
              {data?.analyzed_at ? new Date(data.analyzed_at).toLocaleString() : 'Just now'}
            </span>
          </div>
        </div>

        {/* Right Card: Severity Distribution & Multi-Method Consensus Note */}
        <div className="glass-card flex-col justify-between" style={{ padding: '24px', background: 'var(--bg-card)' }}>
          <div>
            <h3 style={{ margin: '0 0 16px 0', fontSize: '1rem', fontWeight: '600', color: 'var(--text-primary)' }}>
              📊 Severity Distribution & Detector Consensus
            </h3>

            {/* Severity Bars */}
            <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(110px, 1fr))', gap: '12px', marginBottom: '16px' }}>
              <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(244, 63, 94, 0.08)', border: '1px solid rgba(244, 63, 94, 0.25)' }}>
                <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: '#f43f5e', fontWeight: '700' }}>
                  <span>CRITICAL</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{data?.critical_count || 0}</span>
                </div>
                <div style={{ width: '100%', height: '5px', background: 'rgba(0,0,0,0.3)', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      background: '#f43f5e',
                      width: `${data?.total_anomalies ? ((data.critical_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(249, 115, 22, 0.08)', border: '1px solid rgba(249, 115, 22, 0.25)' }}>
                <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: '#f97316', fontWeight: '700' }}>
                  <span>HIGH</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{data?.high_count || 0}</span>
                </div>
                <div style={{ width: '100%', height: '5px', background: 'rgba(0,0,0,0.3)', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      background: '#f97316',
                      width: `${data?.total_anomalies ? ((data.high_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(245, 158, 11, 0.08)', border: '1px solid rgba(245, 158, 11, 0.25)' }}>
                <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: '#fbbf24', fontWeight: '700' }}>
                  <span>MEDIUM</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{data?.medium_count || 0}</span>
                </div>
                <div style={{ width: '100%', height: '5px', background: 'rgba(0,0,0,0.3)', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      background: '#f59e0b',
                      width: `${data?.total_anomalies ? ((data.medium_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(16, 185, 129, 0.08)', border: '1px solid rgba(16, 185, 129, 0.25)' }}>
                <div className="flex-row justify-between align-center" style={{ fontSize: '0.78rem', color: '#10b981', fontWeight: '700' }}>
                  <span>LOW</span>
                  <span style={{ fontFamily: 'var(--font-mono)' }}>{data?.low_count || 0}</span>
                </div>
                <div style={{ width: '100%', height: '5px', background: 'rgba(0,0,0,0.3)', borderRadius: '3px', marginTop: '8px', overflow: 'hidden' }}>
                  <div
                    style={{
                      height: '100%',
                      background: '#10b981',
                      width: `${data?.total_anomalies ? ((data.low_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Explanatory note */}
            <div
              style={{
                padding: '12px 14px',
                borderRadius: '8px',
                background: 'rgba(99, 102, 241, 0.08)',
                border: '1px solid rgba(99, 102, 241, 0.25)',
                fontSize: '0.82rem',
                color: 'var(--text-secondary)',
                lineHeight: 1.5,
              }}
            >
              <strong style={{ color: '#a5b4fc' }}>💡 Multi-Method Consensus:</strong> High-confidence anomalies trigger multiple independent detectors (IQR + Z-Score + ML Isolation Forest). Single-detector anomalies indicate potential tail events or skewed distributions.
            </div>
          </div>
        </div>
      </div>

      {/* 4. Filter & Search Controls */}
      <div className="glass-card" style={{ padding: '18px 20px', marginBottom: '20px' }}>
        <div className="flex-row justify-between align-center" style={{ flexWrap: 'wrap', gap: '14px' }}>
          {/* Method Filter Chips */}
          <div className="flex-row align-center" style={{ gap: '6px', flexWrap: 'wrap' }}>
            <span className="stat-label" style={{ marginRight: '4px' }}>Method:</span>
            {[
              { id: 'ALL', label: 'All Methods' },
              { id: 'MULTI_METHOD_CONSENSUS', label: 'Consensus (2+)' },
              { id: 'IQR', label: 'IQR Outliers' },
              { id: 'Z_SCORE', label: 'Z-Score (|z|≥3)' },
              { id: 'ISOLATION_FOREST', label: 'Isolation Forest (ML)' },
              { id: 'CATEGORICAL_FREQUENCY', label: 'Rare Categories' },
            ].map((m) => {
              const active = selectedMethod === m.id;
              return (
                <button
                  key={m.id}
                  onClick={() => setSelectedMethod(m.id)}
                  className="btn btn--sm"
                  style={{
                    background: active ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-glass)',
                    color: active ? '#fbbf24' : 'var(--text-secondary)',
                    border: active ? '1px solid rgba(245, 158, 11, 0.5)' : '1px solid var(--border-subtle)',
                    fontWeight: active ? '700' : '500',
                  }}
                >
                  {m.label}
                </button>
              );
            })}
          </div>

          {/* Severity Filters */}
          <div className="flex-row align-center" style={{ gap: '4px', background: 'rgba(0, 0, 0, 0.25)', padding: '3px', borderRadius: '8px', border: '1px solid var(--border-subtle)' }}>
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => {
              const active = selectedSeverity === s;
              return (
                <button
                  key={s}
                  onClick={() => setSelectedSeverity(s)}
                  style={{
                    background: active ? 'var(--bg-card-hover)' : 'transparent',
                    color: active ? 'var(--text-primary)' : 'var(--text-muted)',
                    border: 'none',
                    padding: '4px 10px',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    fontWeight: active ? '700' : '500',
                    cursor: 'pointer',
                    transition: 'all 0.15s ease',
                  }}
                >
                  {s}
                </button>
              );
            })}
          </div>
        </div>

        {/* Search Bar */}
        <div style={{ marginTop: '14px', position: 'relative' }}>
          <input
            type="text"
            value={searchCol}
            onChange={(e) => setSearchCol(e.target.value)}
            placeholder="Search column names..."
            className="form-input"
            style={{ paddingRight: '60px' }}
          />
          {searchCol && (
            <button
              onClick={() => setSearchCol('')}
              style={{
                position: 'absolute',
                right: '12px',
                top: '50%',
                transform: 'translateY(-50%)',
                background: 'transparent',
                border: 'none',
                color: 'var(--text-muted)',
                cursor: 'pointer',
                fontSize: '0.78rem',
              }}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* 5. Anomaly Findings Table */}
      <div className="results-table-card" style={{ marginBottom: '28px' }}>
        <div className="table-responsive">
          <table className="data-table" style={{ width: '100%' }}>
            <thead>
              <tr>
                <th style={{ minWidth: '200px' }}>Column & ML Context</th>
                <th style={{ minWidth: '220px' }}>Detection Methods</th>
                <th style={{ minWidth: '160px' }}>Anomalies Detected</th>
                <th style={{ minWidth: '120px' }}>Severity</th>
                <th style={{ minWidth: '110px' }}>Score</th>
                <th style={{ minWidth: '100px', textAlign: 'right' }}>Inspection</th>
              </tr>
            </thead>
            <tbody>
              {filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan="6" style={{ padding: '36px', textAlign: 'center', color: 'var(--text-muted)' }}>
                    No anomaly findings match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                filteredFindings.map((f) => {
                  const sBadge = getSeverityBadge(f.severity);
                  const activeMethods = f.evidence?.detected_methods || [];
                  const p7Context = f.explanation?.phase7_context;

                  return (
                    <tr
                      key={f.id}
                      onClick={() => setSelectedFinding(f)}
                      style={{ cursor: 'pointer', transition: 'background 0.15s ease' }}
                    >
                      {/* Column Name & Phase 7 info */}
                      <td>
                        <div className="column-name-code" style={{ fontSize: '0.9rem' }}>
                          {f.column_name}
                        </div>
                        <div className="flex-row align-center" style={{ gap: '6px', marginTop: '4px' }}>
                          {p7Context?.predicted_domain && (
                            <span
                              style={{
                                fontSize: '0.72rem',
                                padding: '1px 6px',
                                borderRadius: '4px',
                                background: 'rgba(99, 102, 241, 0.15)',
                                color: '#a5b4fc',
                                border: '1px solid rgba(99, 102, 241, 0.3)',
                              }}
                            >
                              {p7Context.predicted_domain}
                            </span>
                          )}
                          {p7Context?.risk_level && (
                            <span
                              style={{
                                fontSize: '0.7rem',
                                fontFamily: 'var(--font-mono)',
                                padding: '1px 5px',
                                borderRadius: '4px',
                                background: 'var(--bg-glass)',
                                color: 'var(--text-muted)',
                                border: '1px solid var(--border-subtle)',
                              }}
                            >
                              Risk: {p7Context.risk_level}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Active Methods */}
                      <td>
                        <div className="flex-row" style={{ gap: '4px', flexWrap: 'wrap' }}>
                          {activeMethods.length === 0 ? (
                            <span className="text-muted" style={{ fontSize: '0.78rem', fontStyle: 'italic' }}>None (Clean)</span>
                          ) : (
                            activeMethods.map((m) => (
                              <span
                                key={m}
                                style={{
                                  fontSize: '0.72rem',
                                  fontWeight: '600',
                                  padding: '2px 6px',
                                  borderRadius: '4px',
                                  background: 'var(--bg-glass)',
                                  color: 'var(--text-secondary)',
                                  border: '1px solid var(--border-subtle)',
                                }}
                              >
                                {m}
                              </span>
                            ))
                          )}
                          {f.detection_method === 'MULTI_METHOD_CONSENSUS' && (
                            <span
                              style={{
                                fontSize: '0.72rem',
                                fontWeight: '700',
                                padding: '2px 6px',
                                borderRadius: '4px',
                                background: 'rgba(245, 158, 11, 0.15)',
                                color: '#fbbf24',
                                border: '1px solid rgba(245, 158, 11, 0.35)',
                              }}
                            >
                              ★ Consensus
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Anomaly Count & Rate */}
                      <td>
                        <div style={{ fontWeight: '600', color: 'var(--text-primary)' }}>
                          {f.anomaly_count}{' '}
                          <span className="text-muted" style={{ fontSize: '0.78rem', fontWeight: 'normal' }}>
                            ({f.anomaly_rate}%)
                          </span>
                        </div>
                        <div style={{ width: '100px', height: '4px', background: 'rgba(0,0,0,0.3)', borderRadius: '2px', marginTop: '6px', overflow: 'hidden' }}>
                          <div
                            style={{
                              height: '100%',
                              background: getScoreColor(f.score),
                              width: `${Math.min(100, f.anomaly_rate * 5)}%`,
                            }}
                          />
                        </div>
                      </td>

                      {/* Severity */}
                      <td>
                        <span
                          style={{
                            fontSize: '0.75rem',
                            fontWeight: '700',
                            padding: '3px 8px',
                            borderRadius: '12px',
                            background: sBadge.bg,
                            color: sBadge.color,
                            border: `1px solid ${sBadge.border}`,
                            display: 'inline-flex',
                            alignItems: 'center',
                            gap: '4px',
                          }}
                        >
                          ● {f.severity}
                        </span>
                      </td>

                      {/* Score Meter */}
                      <td>
                        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: '700', fontSize: '0.9rem', color: getScoreColor(f.score) }}>
                          {f.score.toFixed(1)}
                        </span>
                      </td>

                      {/* Inspection button */}
                      <td style={{ textAlign: 'right' }}>
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFinding(f);
                          }}
                          className="btn btn--sm btn--secondary"
                        >
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

      {/* 6. Detail Panel / Slide-out Drawer */}
      {selectedFinding && (
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
          onClick={() => setSelectedFinding(null)}
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
                  <div className="flex-row align-center" style={{ gap: '8px', marginBottom: '8px' }}>
                    <span
                      style={{
                        fontSize: '0.75rem',
                        fontWeight: '700',
                        padding: '2px 8px',
                        borderRadius: '10px',
                        background: getSeverityBadge(selectedFinding.severity).bg,
                        color: getSeverityBadge(selectedFinding.severity).color,
                        border: `1px solid ${getSeverityBadge(selectedFinding.severity).border}`,
                      }}
                    >
                      {selectedFinding.severity} Severity
                    </span>
                    <span
                      style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.75rem',
                        color: '#fbbf24',
                        background: 'rgba(245, 158, 11, 0.15)',
                        padding: '2px 8px',
                        borderRadius: '4px',
                        border: '1px solid rgba(245, 158, 11, 0.3)',
                      }}
                    >
                      Score: {selectedFinding.score.toFixed(1)} / 100
                    </span>
                  </div>
                  <h2 style={{ margin: 0, fontSize: '1.35rem', fontFamily: 'var(--font-mono)', fontWeight: '700', color: 'var(--text-primary)' }}>
                    {selectedFinding.column_name}
                  </h2>
                  <p className="text-muted" style={{ margin: '4px 0 0 0', fontSize: '0.8rem' }}>
                    Detection Method: <strong style={{ color: 'var(--text-secondary)' }}>{selectedFinding.detection_method}</strong>
                  </p>
                </div>
                <button
                  onClick={() => setSelectedFinding(null)}
                  className="btn btn--sm btn--secondary"
                  style={{ fontSize: '1rem', padding: '6px 12px' }}
                >
                  ✕
                </button>
              </div>

              {/* 1. Overview */}
              <div className="glass-card" style={{ padding: '16px', background: 'var(--bg-card)' }}>
                <span className="stat-label" style={{ display: 'block', marginBottom: '6px' }}>
                  Finding Summary
                </span>
                <p style={{ fontSize: '0.88rem', color: 'var(--text-primary)', lineHeight: '1.6', margin: 0 }}>
                  {selectedFinding.explanation?.summary || 'No summary available.'}
                </p>
                <div className="flex-row align-center" style={{ gap: '12px', fontSize: '0.8rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', marginTop: '10px', paddingTop: '8px', borderTop: '1px dashed var(--border-subtle)' }}>
                  <span>Anomalies: <strong style={{ color: 'var(--text-primary)' }}>{selectedFinding.anomaly_count}</strong> rows</span>
                  <span>•</span>
                  <span>Anomaly Rate: <strong style={{ color: 'var(--text-primary)' }}>{selectedFinding.anomaly_rate}%</strong></span>
                </div>
              </div>

              {/* 2. Detection Evidence / Outlier Drivers */}
              <div>
                <span className="stat-label" style={{ display: 'block', marginBottom: '8px', color: '#fbbf24' }}>
                  Identified Outlier Drivers
                </span>
                <div className="flex-col" style={{ gap: '8px' }}>
                  {selectedFinding.explanation?.drivers?.length > 0 ? (
                    selectedFinding.explanation.drivers.map((d, i) => (
                      <div
                        key={i}
                        className="flex-row align-center"
                        style={{
                          gap: '8px',
                          padding: '10px 14px',
                          borderRadius: '8px',
                          background: 'rgba(245, 158, 11, 0.08)',
                          border: '1px solid rgba(245, 158, 11, 0.25)',
                          fontSize: '0.82rem',
                          color: '#fde68a',
                        }}
                      >
                        <span style={{ color: '#fbbf24', fontWeight: 'bold' }}>•</span>
                        <span>{d}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-muted" style={{ fontSize: '0.82rem', fontStyle: 'italic', margin: 0 }}>
                      No specific driver conditions flagged.
                    </p>
                  )}
                </div>
              </div>

              {/* 3. Detector Results Grid */}
              <div>
                <span className="stat-label" style={{ display: 'block', marginBottom: '8px', color: '#38bdf8' }}>
                  Detector Results & Evidence Breakdown
                </span>
                <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '12px' }}>
                  {/* IQR Card */}
                  <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>IQR Detector</span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: '700',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: selectedFinding.evidence?.iqr?.detected ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-glass)',
                          color: selectedFinding.evidence?.iqr?.detected ? '#fbbf24' : 'var(--text-muted)',
                        }}
                      >
                        {selectedFinding.evidence?.iqr?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.iqr?.executed ? (
                      <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div>Bounds: [{selectedFinding.evidence.iqr.lower_bound}, {selectedFinding.evidence.iqr.upper_bound}]</div>
                        <div>Q1: {selectedFinding.evidence.iqr.q1} | Q3: {selectedFinding.evidence.iqr.q3}</div>
                        <div>Outliers: {selectedFinding.evidence.iqr.anomaly_count} ({selectedFinding.evidence.iqr.anomaly_rate}%)</div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        {selectedFinding.evidence?.iqr?.reason || 'Not executed'}
                      </div>
                    )}
                  </div>

                  {/* Z-Score Card */}
                  <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>Z-Score (|z|≥3)</span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: '700',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: selectedFinding.evidence?.zscore?.detected ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-glass)',
                          color: selectedFinding.evidence?.zscore?.detected ? '#fbbf24' : 'var(--text-muted)',
                        }}
                      >
                        {selectedFinding.evidence?.zscore?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.zscore?.executed ? (
                      <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div>Mean: {selectedFinding.evidence.zscore.mean} | Std: {selectedFinding.evidence.zscore.std}</div>
                        <div>Max |z|: {selectedFinding.evidence.zscore.max_abs_zscore}</div>
                        <div>Outliers: {selectedFinding.evidence.zscore.anomaly_count} ({selectedFinding.evidence.zscore.anomaly_rate}%)</div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        {selectedFinding.evidence?.zscore?.reason || 'Not executed'}
                      </div>
                    )}
                  </div>

                  {/* Isolation Forest Card */}
                  <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>Isolation Forest (ML)</span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: '700',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: selectedFinding.evidence?.isolation_forest?.detected ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-glass)',
                          color: selectedFinding.evidence?.isolation_forest?.detected ? '#fbbf24' : 'var(--text-muted)',
                        }}
                      >
                        {selectedFinding.evidence?.isolation_forest?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.isolation_forest?.executed ? (
                      <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div>Strategy: {selectedFinding.evidence.isolation_forest.sampling_strategy}</div>
                        <div>Outliers: {selectedFinding.evidence.isolation_forest.anomaly_count} ({selectedFinding.evidence.isolation_forest.anomaly_rate}%)</div>
                        <div>Min Score: {selectedFinding.evidence.isolation_forest.min_decision_score}</div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        {selectedFinding.evidence?.isolation_forest?.reason || 'Not executed'}
                      </div>
                    )}
                  </div>

                  {/* Categorical Frequency Card */}
                  <div style={{ padding: '12px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                    <div className="flex-row justify-between align-center" style={{ marginBottom: '6px' }}>
                      <span style={{ fontWeight: '600', fontSize: '0.85rem' }}>Rare Categories (&lt;1%)</span>
                      <span
                        style={{
                          fontSize: '0.68rem',
                          fontWeight: '700',
                          padding: '1px 6px',
                          borderRadius: '4px',
                          background: selectedFinding.evidence?.categorical_frequency?.detected ? 'rgba(245, 158, 11, 0.2)' : 'var(--bg-glass)',
                          color: selectedFinding.evidence?.categorical_frequency?.detected ? '#fbbf24' : 'var(--text-muted)',
                        }}
                      >
                        {selectedFinding.evidence?.categorical_frequency?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.categorical_frequency?.executed ? (
                      <div style={{ fontSize: '0.75rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)', display: 'flex', flexDirection: 'column', gap: '2px' }}>
                        <div>Unique: {selectedFinding.evidence.categorical_frequency.unique_categories_count}</div>
                        <div>Rare Count: {selectedFinding.evidence.categorical_frequency.rare_category_count}</div>
                        <div>Rare Rate: {selectedFinding.evidence.categorical_frequency.rare_category_rate}%</div>
                      </div>
                    ) : (
                      <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic' }}>
                        {selectedFinding.evidence?.categorical_frequency?.reason || 'Not executed'}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* 4. Interpretation & Privacy Protection Callouts */}
              <div
                style={{
                  padding: '14px 16px',
                  borderRadius: '8px',
                  background: 'rgba(99, 102, 241, 0.08)',
                  border: '1px solid rgba(99, 102, 241, 0.25)',
                }}
              >
                <span className="stat-label" style={{ color: '#a5b4fc', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '6px' }}>
                  🛡️ Statistical Interpretation & Privacy Guard
                </span>
                <ul style={{ margin: 0, paddingLeft: '18px', fontSize: '0.82rem', color: 'var(--text-secondary)', lineHeight: '1.6' }}>
                  <li>
                    <strong style={{ color: 'var(--text-primary)' }}>Interpretation Notice:</strong> An anomaly indicates a statistically unusual pattern; it does not automatically mean the data is incorrect.
                  </li>
                  <li>
                    <strong style={{ color: 'var(--text-primary)' }}>Privacy Guarantee:</strong> Zero raw PII values are stored in anomaly records. Only safe statistical distribution metrics are preserved.
                  </li>
                </ul>
              </div>

              {/* Raw Evidence JSON Snippet */}
              {selectedFinding.evidence && (
                <div style={{ padding: '14px', borderRadius: '8px', background: 'var(--bg-card)', border: '1px solid var(--border-subtle)' }}>
                  <div className="flex-row justify-between align-center" style={{ marginBottom: '8px' }}>
                    <span className="stat-label">Detector Evidence Payload</span>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(selectedFinding.evidence, null, 2), 'evidence')}
                      className="btn btn--sm btn--secondary"
                      style={{ fontSize: '0.75rem' }}
                    >
                      {copiedKey === 'evidence' ? '✓ Copied' : 'Copy JSON'}
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
                    {JSON.stringify(selectedFinding.evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="flex-row justify-between align-center" style={{ paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
              <span className="text-muted" style={{ fontSize: '0.78rem' }}>DataGuard AI Anomaly Engine</span>
              <button
                onClick={() => setSelectedFinding(null)}
                className="btn btn--primary"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
