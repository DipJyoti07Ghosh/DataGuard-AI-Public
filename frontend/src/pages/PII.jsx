import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPIIScan, scanPII, getDatasetVersion } from '../api/client';

export default function PII() {
  const { datasetId, versionId } = useParams();
  const [scanResult, setScanResult] = useState(null);
  const [versionMeta, setVersionMeta] = useState(null);
  const [loading, setLoading] = useState(true);
  const [recomputing, setRecomputing] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRisk, setSelectedRisk] = useState('ALL');
  const [selectedEntity, setSelectedEntity] = useState('ALL');

  useEffect(() => {
    fetchPIIData();
  }, [datasetId, versionId]);

  async function fetchPIIData(force = false) {
    if (force) {
      setRecomputing(true);
    } else {
      setLoading(true);
    }
    setError(null);

    try {
      // Parallel fetch of version info & PII scan
      const [scanData, vMeta] = await Promise.all([
        force ? scanPII(datasetId, versionId, true) : getPIIScan(datasetId, versionId),
        getDatasetVersion(datasetId, versionId).catch(() => null),
      ]);
      setScanResult(scanData);
      setVersionMeta(vMeta);
    } catch (err) {
      console.error('Failed to load PII detection results:', err);
      setError(err.message || 'Failed to execute or load PII detection scan.');
    } finally {
      setLoading(false);
      setRecomputing(false);
    }
  }

  function getRiskBadge(risk) {
    const level = (risk || 'LOW').toUpperCase();
    if (level === 'HIGH') {
      return {
        label: 'HIGH RISK',
        icon: '🔴',
        color: '#f43f5e',
        bg: 'rgba(244, 63, 94, 0.15)',
        border: 'rgba(244, 63, 94, 0.35)',
      };
    }
    if (level === 'MEDIUM') {
      return {
        label: 'MEDIUM RISK',
        icon: '🟠',
        color: '#f59e0b',
        bg: 'rgba(245, 158, 11, 0.15)',
        border: 'rgba(245, 158, 11, 0.35)',
      };
    }
    return {
      label: 'LOW RISK',
      icon: '🟡',
      color: '#eab308',
      bg: 'rgba(234, 179, 8, 0.15)',
      border: 'rgba(234, 179, 8, 0.35)',
    };
  }

  function getEntityIcon(type) {
    const ent = (type || '').toUpperCase();
    if (ent.includes('EMAIL')) return '✉️';
    if (ent.includes('PHONE')) return '📞';
    if (ent.includes('PERSON')) return '👤';
    if (ent.includes('IP')) return '🌐';
    if (ent.includes('CREDIT') || ent.includes('CARD') || ent.includes('IBAN')) return '💳';
    if (ent.includes('SSN') || ent.includes('PASSPORT') || ent.includes('LICENSE')) return '🪪';
    if (ent.includes('LOCATION') || ent.includes('ADDRESS')) return '📍';
    if (ent.includes('URL')) return '🔗';
    return '🔒';
  }

  function formatEntityName(type) {
    if (!type) return 'Unknown';
    return type
      .split('_')
      .map(w => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  }

  function getSourceBadge(source) {
    if (source === 'COLUMN_AND_VALUE') {
      return { label: 'Column + Sample Value', bg: 'rgba(139, 92, 246, 0.15)', text: '#a78bfa', border: 'rgba(139, 92, 246, 0.3)' };
    }
    if (source === 'VALUE') {
      return { label: 'Sample Value', bg: 'rgba(56, 189, 248, 0.15)', text: '#38bdf8', border: 'rgba(56, 189, 248, 0.3)' };
    }
    return { label: 'Column Name', bg: 'rgba(245, 158, 11, 0.15)', text: '#fbbf24', border: 'rgba(245, 158, 11, 0.3)' };
  }

  if (loading) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '48px', maxWidth: '450px', textAlign: 'center' }}>
          <div className="spinner" style={{ width: '40px', height: '40px', marginBottom: '20px' }}></div>
          <h2 style={{ margin: '0 0 8px 0', fontSize: '1.25rem' }}>Scanning for PII & Sensitive Data...</h2>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
            Analyzing column headers and sample values with Microsoft Presidio Analyzer.
          </p>
        </div>
      </div>
    );
  }

  if (error || !scanResult) {
    return (
      <div className="page-container flex-center" style={{ minHeight: '60vh' }}>
        <div className="glass-card flex-col flex-center" style={{ padding: '40px', maxWidth: '500px', textAlign: 'center' }}>
          <div style={{ fontSize: '2.5rem', marginBottom: '16px' }}>⚠️</div>
          <h2 style={{ margin: '0 0 8px 0', color: 'var(--danger-color)' }}>PII Detection Error</h2>
          <p className="text-muted" style={{ marginBottom: '24px' }}>{error || 'Unable to load PII scan results.'}</p>
          <div className="flex-row" style={{ gap: '12px' }}>
            <button className="btn btn-primary" onClick={() => fetchPIIData(true)}>
              Retry PII Scan
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
    total_columns_scanned,
    pii_columns_count,
    total_findings,
    scanned_at,
    summary = {},
    findings = [],
  } = scanResult;

  const riskBreakdown = summary.risk_breakdown || { HIGH: 0, MEDIUM: 0, LOW: 0 };
  const entityBreakdown = summary.entity_breakdown || {};
  const overallRisk = summary.overall_risk || 'NONE';

  // Apply frontend filters
  const filteredFindings = findings.filter(f => {
    // Search query filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const colMatch = f.column_name.toLowerCase().includes(q);
      const entityMatch = f.entity_type.toLowerCase().includes(q);
      if (!colMatch && !entityMatch) return false;
    }
    // Risk filter
    if (selectedRisk !== 'ALL' && f.risk_level.toUpperCase() !== selectedRisk) {
      return false;
    }
    // Entity filter
    if (selectedEntity !== 'ALL' && f.entity_type.toUpperCase() !== selectedEntity) {
      return false;
    }
    return true;
  });

  const datasetName = versionMeta?.dataset_name || versionMeta?.original_filename || 'Dataset';
  const versionNumber = versionMeta?.version_number || 1;

  return (
    <div className="page-container" style={{ paddingBottom: '60px' }}>
      {/* Top Header */}
      <div className="flex-row justify-between align-center" style={{ marginBottom: '24px', flexWrap: 'wrap', gap: '16px' }}>
        <div>
          <div className="flex-row align-center" style={{ gap: '12px', marginBottom: '6px' }}>
            <h1 style={{ margin: 0, fontSize: '1.75rem', fontWeight: '700' }}>
              🔐 PII & Sensitive Data Detection
            </h1>
            <span className="badge badge-primary" style={{ fontSize: '0.85rem', padding: '4px 10px' }}>
              V{versionNumber}
            </span>
          </div>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.95rem' }}>
            Dataset: <strong style={{ color: 'var(--text-color)' }}>{datasetName}</strong> • Scanned on {new Date(scanned_at).toLocaleString()}
          </p>
        </div>

        <div className="flex-row" style={{ gap: '12px', alignItems: 'center' }}>
          <button
            className="btn btn-secondary flex-row align-center"
            style={{ gap: '8px' }}
            onClick={() => fetchPIIData(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <div className="spinner-sm"></div>
                <span>Scanning...</span>
              </>
            ) : (
              <>
                <span>🔄</span>
                <span>Re-scan</span>
              </>
            )}
          </button>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/profile`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>📊</span>
            <span>View Profile</span>
          </Link>
          <Link to={`/datasets/${datasetId}/versions/${versionId}/quality`} className="btn btn-secondary flex-row align-center" style={{ gap: '8px' }}>
            <span>🛡</span>
            <span>Quality Check</span>
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
          borderLeft: `5px solid ${
            overallRisk === 'HIGH'
              ? '#f43f5e'
              : overallRisk === 'MEDIUM'
              ? '#f59e0b'
              : overallRisk === 'LOW'
              ? '#eab308'
              : '#10b981'
          }`,
        }}
      >
        <div className="flex-row align-center" style={{ gap: '20px' }}>
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '1.8rem',
              background:
                overallRisk === 'HIGH'
                  ? 'rgba(244, 63, 94, 0.15)'
                  : overallRisk === 'MEDIUM'
                  ? 'rgba(245, 158, 11, 0.15)'
                  : overallRisk === 'LOW'
                  ? 'rgba(234, 179, 8, 0.15)'
                  : 'rgba(16, 185, 129, 0.15)',
              border: `1px solid ${
                overallRisk === 'HIGH'
                  ? 'rgba(244, 63, 94, 0.3)'
                  : overallRisk === 'MEDIUM'
                  ? 'rgba(245, 158, 11, 0.3)'
                  : overallRisk === 'LOW'
                  ? 'rgba(234, 179, 8, 0.3)'
                  : 'rgba(16, 185, 129, 0.3)'
              }`,
            }}
          >
            {overallRisk === 'HIGH' ? '🚨' : overallRisk === 'MEDIUM' ? '⚠️' : overallRisk === 'LOW' ? '🔍' : '✅'}
          </div>
          <div>
            <h3 style={{ margin: '0 0 4px 0', fontSize: '1.25rem', fontWeight: '600' }}>
              {overallRisk === 'HIGH'
                ? 'High-Risk Sensitive Data Identified'
                : overallRisk === 'MEDIUM'
                ? 'Personal / Contact Data Identified'
                : overallRisk === 'LOW'
                ? 'Low-Risk or Ambiguous Sensitive Signals'
                : 'No PII or Sensitive Data Detected'}
            </h3>
            <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
              {overallRisk === 'NONE'
                ? `Inspected ${total_columns_scanned} columns across sampled records. No sensitive entities were discovered.`
                : `Detected ${total_findings} sensitive findings across ${pii_columns_count} out of ${total_columns_scanned} columns scanned.`}
            </p>
          </div>
        </div>

        <div className="flex-row" style={{ gap: '16px', alignItems: 'center' }}>
          <span
            style={{
              padding: '6px 16px',
              borderRadius: '20px',
              fontWeight: '700',
              fontSize: '0.9rem',
              letterSpacing: '0.5px',
              background:
                overallRisk === 'HIGH'
                  ? 'rgba(244, 63, 94, 0.2)'
                  : overallRisk === 'MEDIUM'
                  ? 'rgba(245, 158, 11, 0.2)'
                  : overallRisk === 'LOW'
                  ? 'rgba(234, 179, 8, 0.2)'
                  : 'rgba(16, 185, 129, 0.2)',
              color:
                overallRisk === 'HIGH'
                  ? '#f43f5e'
                  : overallRisk === 'MEDIUM'
                  ? '#f59e0b'
                  : overallRisk === 'LOW'
                  ? '#eab308'
                  : '#10b981',
              border: `1px solid ${
                overallRisk === 'HIGH'
                  ? 'rgba(244, 63, 94, 0.4)'
                  : overallRisk === 'MEDIUM'
                  ? 'rgba(245, 158, 11, 0.4)'
                  : overallRisk === 'LOW'
                  ? 'rgba(234, 179, 8, 0.4)'
                  : 'rgba(16, 185, 129, 0.4)'
              }`,
            }}
          >
            OVERALL RISK: {overallRisk}
          </span>
        </div>
      </div>

      {/* Summary KPI Cards Grid */}
      <div className="grid-responsive" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginBottom: '28px' }}>
        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '6px', fontWeight: '500' }}>
            PII COLUMNS
          </span>
          <span style={{ fontSize: '2rem', fontWeight: '800', color: pii_columns_count > 0 ? '#38bdf8' : 'var(--text-color)' }}>
            {pii_columns_count}
          </span>
          <span className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            of {total_columns_scanned} total columns
          </span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '6px', fontWeight: '500' }}>
            TOTAL FINDINGS
          </span>
          <span style={{ fontSize: '2rem', fontWeight: '800', color: '#a78bfa' }}>
            {total_findings}
          </span>
          <span className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            Across all entity recognizers
          </span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '6px', fontWeight: '500' }}>
            HIGH RISK
          </span>
          <span style={{ fontSize: '2rem', fontWeight: '800', color: riskBreakdown.HIGH > 0 ? '#f43f5e' : 'var(--text-muted)' }}>
            {riskBreakdown.HIGH || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            Financial / Government ID
          </span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '6px', fontWeight: '500' }}>
            MEDIUM RISK
          </span>
          <span style={{ fontSize: '2rem', fontWeight: '800', color: riskBreakdown.MEDIUM > 0 ? '#f59e0b' : 'var(--text-muted)' }}>
            {riskBreakdown.MEDIUM || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            Contact / Identity details
          </span>
        </div>

        <div className="glass-card flex-col" style={{ padding: '20px' }}>
          <span className="text-muted" style={{ fontSize: '0.85rem', marginBottom: '6px', fontWeight: '500' }}>
            LOW RISK
          </span>
          <span style={{ fontSize: '2rem', fontWeight: '800', color: riskBreakdown.LOW > 0 ? '#eab308' : 'var(--text-muted)' }}>
            {riskBreakdown.LOW || 0}
          </span>
          <span className="text-muted" style={{ fontSize: '0.8rem', marginTop: '4px' }}>
            Weak / Generic matches
          </span>
        </div>
      </div>

      {/* Entity Breakdown Section */}
      {Object.keys(entityBreakdown).length > 0 && (
        <div className="glass-card" style={{ padding: '24px', marginBottom: '28px' }}>
          <h3 style={{ margin: '0 0 16px 0', fontSize: '1.1rem', fontWeight: '600' }}>
            📊 Entity Type Breakdown
          </h3>
          <div className="flex-row" style={{ flexWrap: 'wrap', gap: '12px' }}>
            {Object.entries(entityBreakdown).map(([entity, count]) => {
              const icon = getEntityIcon(entity);
              const label = formatEntityName(entity);
              const isSelected = selectedEntity === entity;
              return (
                <button
                  key={entity}
                  className="flex-row align-center"
                  onClick={() => setSelectedEntity(isSelected ? 'ALL' : entity)}
                  style={{
                    padding: '8px 16px',
                    borderRadius: '10px',
                    background: isSelected ? 'rgba(56, 189, 248, 0.2)' : 'rgba(255, 255, 255, 0.04)',
                    border: `1px solid ${isSelected ? '#38bdf8' : 'rgba(255, 255, 255, 0.08)'}`,
                    color: isSelected ? '#38bdf8' : 'var(--text-color)',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    gap: '8px',
                    fontSize: '0.9rem',
                  }}
                >
                  <span>{icon}</span>
                  <span style={{ fontWeight: '500' }}>{label}</span>
                  <span
                    style={{
                      background: 'rgba(255, 255, 255, 0.1)',
                      padding: '2px 8px',
                      borderRadius: '12px',
                      fontSize: '0.8rem',
                      fontWeight: '700',
                    }}
                  >
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Interactive Findings Section */}
      <div className="glass-card" style={{ padding: '24px', marginBottom: '28px' }}>
        {/* Controls and Search Bar */}
        <div className="flex-row justify-between align-center" style={{ marginBottom: '20px', flexWrap: 'wrap', gap: '16px' }}>
          <div className="flex-row align-center" style={{ gap: '12px', flex: '1', minWidth: '280px' }}>
            <input
              type="text"
              placeholder="Search by column or entity name..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
              className="input-field"
              style={{
                width: '100%',
                maxWidth: '360px',
                padding: '10px 14px',
                borderRadius: '8px',
                border: '1px solid rgba(255, 255, 255, 0.1)',
                background: 'rgba(0, 0, 0, 0.2)',
                color: 'var(--text-color)',
              }}
            />
          </div>

          <div className="flex-row align-center" style={{ gap: '10px', flexWrap: 'wrap' }}>
            <span className="text-muted" style={{ fontSize: '0.85rem' }}>Risk Filter:</span>
            {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map(r => (
              <button
                key={r}
                className={`btn btn-sm ${selectedRisk === r ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setSelectedRisk(r)}
                style={{ fontSize: '0.8rem', padding: '6px 12px' }}
              >
                {r}
              </button>
            ))}
          </div>
        </div>

        {/* Findings Table */}
        {filteredFindings.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '40px 20px' }}>
            <span style={{ fontSize: '2.5rem' }}>🎉</span>
            <h3 style={{ margin: '12px 0 6px 0', fontSize: '1.1rem' }}>No Matching PII Findings</h3>
            <p className="text-muted" style={{ margin: 0, fontSize: '0.9rem' }}>
              {findings.length === 0
                ? 'No sensitive data or PII entities were discovered in this dataset version.'
                : 'No findings match the current filter selection.'}
            </p>
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="data-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'left' }}>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>COLUMN</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>ENTITY TYPE</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>DETECTION SOURCE</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>CONFIDENCE</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>SAMPLE MATCH RATE</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>RISK LEVEL</th>
                  <th style={{ padding: '12px 16px', fontSize: '0.85rem', color: 'var(--text-muted)' }}>MASKED SAMPLE PREVIEW</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((finding, idx) => {
                  const riskStyle = getRiskBadge(finding.risk_level);
                  const sourceStyle = getSourceBadge(finding.detection_source);
                  const icon = getEntityIcon(finding.entity_type);
                  const confPct = Math.round(finding.confidence * 100);

                  return (
                    <tr
                      key={finding.id || idx}
                      style={{
                        borderBottom: '1px solid rgba(255, 255, 255, 0.05)',
                        transition: 'background 0.2s',
                      }}
                    >
                      {/* Column Name */}
                      <td style={{ padding: '14px 16px', fontWeight: '600' }}>
                        <code style={{ background: 'rgba(255,255,255,0.08)', padding: '3px 8px', borderRadius: '6px' }}>
                          {finding.column_name}
                        </code>
                      </td>

                      {/* Entity Type */}
                      <td style={{ padding: '14px 16px' }}>
                        <div className="flex-row align-center" style={{ gap: '8px' }}>
                          <span>{icon}</span>
                          <span style={{ fontWeight: '500', fontSize: '0.9rem' }}>
                            {finding.entity_type}
                          </span>
                        </div>
                      </td>

                      {/* Detection Source */}
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            padding: '3px 10px',
                            borderRadius: '6px',
                            fontSize: '0.8rem',
                            fontWeight: '600',
                            background: sourceStyle.bg,
                            color: sourceStyle.text,
                            border: `1px solid ${sourceStyle.border}`,
                          }}
                        >
                          {sourceStyle.label}
                        </span>
                      </td>

                      {/* Confidence */}
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ width: '100px' }}>
                          <div className="flex-row justify-between" style={{ fontSize: '0.8rem', marginBottom: '4px' }}>
                            <span style={{ fontWeight: '700', color: confPct >= 80 ? '#10b981' : confPct >= 50 ? '#f59e0b' : '#f43f5e' }}>
                              {confPct}%
                            </span>
                          </div>
                          <div style={{ height: '6px', width: '100%', background: 'rgba(255,255,255,0.1)', borderRadius: '3px', overflow: 'hidden' }}>
                            <div
                              style={{
                                height: '100%',
                                width: `${confPct}%`,
                                background: confPct >= 80 ? '#10b981' : confPct >= 50 ? '#f59e0b' : '#f43f5e',
                                borderRadius: '3px',
                              }}
                            ></div>
                          </div>
                        </div>
                      </td>

                      {/* Sample Match Rate */}
                      <td style={{ padding: '14px 16px', fontSize: '0.85rem' }}>
                        {finding.sampled_count > 0 ? (
                          <span>
                            {finding.detected_count} / {finding.sampled_count}{' '}
                            <span className="text-muted">({Math.round(finding.detection_rate * 100)}%)</span>
                          </span>
                        ) : (
                          <span className="text-muted">Heuristic only</span>
                        )}
                      </td>

                      {/* Risk Level */}
                      <td style={{ padding: '14px 16px' }}>
                        <span
                          style={{
                            padding: '4px 10px',
                            borderRadius: '6px',
                            fontSize: '0.8rem',
                            fontWeight: '700',
                            background: riskStyle.bg,
                            color: riskStyle.color,
                            border: `1px solid ${riskStyle.border}`,
                          }}
                        >
                          {riskStyle.icon} {finding.risk_level}
                        </span>
                      </td>

                      {/* Masked Preview */}
                      <td style={{ padding: '14px 16px' }}>
                        <div
                          style={{
                            fontFamily: 'monospace',
                            fontSize: '0.85rem',
                            background: 'rgba(0, 0, 0, 0.3)',
                            padding: '4px 10px',
                            borderRadius: '6px',
                            border: '1px solid rgba(255, 255, 255, 0.08)',
                            color: '#94a3b8',
                            display: 'inline-block',
                          }}
                        >
                          {finding.masked_preview || '[MASKED]'}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Privacy Guarantee & Architecture Callout */}
      <div className="glass-card flex-row align-center" style={{ padding: '20px 24px', gap: '16px', background: 'rgba(16, 185, 129, 0.04)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
        <span style={{ fontSize: '1.8rem' }}>🛡</span>
        <div style={{ flex: 1 }}>
          <h4 style={{ margin: '0 0 4px 0', fontSize: '0.95rem', color: '#10b981', fontWeight: '600' }}>
            Data Privacy & Compliance Assurance
          </h4>
          <p className="text-muted" style={{ margin: 0, fontSize: '0.85rem', lineHeight: '1.4' }}>
            Microsoft Presidio Analyzer performs deterministic, bounded sampling on string candidates without storing full records.
            All sample representations undergo one-way cryptographic masking before database persistence and API transport.
          </p>
        </div>
      </div>
    </div>
  );
}
