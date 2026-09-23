/**
 * DataGuard AI — PII & Sensitive Data Detection
 *
 * Renders the Microsoft Presidio scan results:
 * - Overall risk banner
 * - 5 KPI counters
 * - Entity type breakdown (click to filter)
 * - Findings table with confidence bars and masked previews
 *
 * Visual design: DATA GUARD AI workspace skin (.pi-* classes).
 * Backend contract: UNCHANGED.
 *   - getPIIScan() / scanPII() / getDatasetVersion()
 *   - All field paths preserved.
 */

import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getPIIScan, scanPII, getDatasetVersion } from '../api/client';
import './PII.css';

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
      // Parallel fetch of version info & PII scan (unchanged behavior)
      const [scanData, vMeta] = await Promise.all([
        force
          ? scanPII(datasetId, versionId, true)
          : getPIIScan(datasetId, versionId),
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
      return { label: 'HIGH', icon: '🔴', color: '#f43f5e' };
    }
    if (level === 'MEDIUM') {
      return { label: 'MEDIUM', icon: '🟠', color: '#fbbf24' };
    }
    return { label: 'LOW', icon: '🟡', color: '#eab308' };
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
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
      .join(' ');
  }

  function getSourceLabel(source) {
    if (source === 'COLUMN_AND_VALUE') return 'Column + Sample';
    if (source === 'VALUE') return 'Sample Value';
    return 'Column Name';
  }

  function getSourceTone(source) {
    if (source === 'COLUMN_AND_VALUE') return 'source--both';
    if (source === 'VALUE') return 'source--value';
    return 'source--col';
  }

  // ---------- Loading ----------
  if (loading) {
    return (
      <div className="pi-page">
        <div className="pi-loading">
          <span className="pi-spinner" aria-hidden="true" />
          <p>Scanning for PII & Sensitive Data…</p>
          <small>Analyzing column headers and sample values with Microsoft Presidio.</small>
        </div>
      </div>
    );
  }

  // ---------- Error ----------
  if (error || !scanResult) {
    return (
      <div className="pi-page">
        <div className="pi-error" role="alert">
          <span>⚠️</span>
          <div>
            <strong>PII Detection Error</strong>
            <p>{error || 'Unable to load PII scan results.'}</p>
          </div>
        </div>
        <div className="pi-error-actions">
          <button
            className="pi-btn pi-btn--primary"
            onClick={() => fetchPIIData(true)}
            disabled={recomputing}
          >
            Retry PII Scan
          </button>
          <Link to="/datasets" className="pi-btn pi-btn--ghost">
            Back to Datasets
          </Link>
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

  const filteredFindings = findings.filter((f) => {
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const colMatch = f.column_name.toLowerCase().includes(q);
      const entityMatch = f.entity_type.toLowerCase().includes(q);
      if (!colMatch && !entityMatch) return false;
    }
    if (selectedRisk !== 'ALL' && f.risk_level.toUpperCase() !== selectedRisk) {
      return false;
    }
    if (selectedEntity !== 'ALL' && f.entity_type.toUpperCase() !== selectedEntity) {
      return false;
    }
    return true;
  });

  const datasetName =
    versionMeta?.dataset_name || versionMeta?.original_filename || 'Dataset';
  const versionNumber = versionMeta?.version_number || 1;

  const overallMeta =
    overallRisk === 'HIGH'
      ? { icon: '🚨', title: 'High-Risk Sensitive Data Identified', tone: 'danger' }
      : overallRisk === 'MEDIUM'
      ? { icon: '⚠️', title: 'Personal / Contact Data Identified', tone: 'warning' }
      : overallRisk === 'LOW'
      ? { icon: '🔍', title: 'Low-Risk Sensitive Signals', tone: 'info' }
      : { icon: '✅', title: 'No PII or Sensitive Data Detected', tone: 'success' };

  return (
    <div className="pi-page">
      {/* ================= HERO ================= */}
      <header className="pi-hero">
        <div className="pi-hero-info">
          <div className="pi-crumbs">
            <Link to="/datasets">Datasets</Link>
            <span>›</span>
            <span>{datasetName}</span>
            <span className="pi-version-pill">V{versionNumber}</span>
          </div>
          <small>DATA QUALITY WORKSPACE</small>
          <h1>PII &amp; Sensitive Data Detection</h1>
          <p>Scanned on {new Date(scanned_at).toLocaleString()}</p>
        </div>

        <div className="pi-hero-actions">
          <button
            className="pi-btn pi-btn--ghost"
            onClick={() => fetchPIIData(true)}
            disabled={recomputing}
          >
            {recomputing ? (
              <>
                <span className="pi-spinner pi-spinner--sm" /> Scanning…
              </>
            ) : (
              '🔄 Re-scan'
            )}
          </button>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/profile`}
            className="pi-btn pi-btn--ghost"
          >
            📊 Profile
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="pi-btn pi-btn--ghost"
          >
            🛡 Quality
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/risk`}
            className="pi-btn pi-btn--ghost"
          >
            🤖 ML Risk
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
            className="pi-btn pi-btn--ghost pi-btn--amber"
          >
            ⚠ Anomalies
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="pi-btn pi-btn--primary"
          >
            🎯 Prioritization
          </Link>
        </div>
      </header>

      {/* ================= OVERVIEW BANNER ================= */}
      <section className={`pi-overview pi-overview--${overallMeta.tone}`}>
        <span className="pi-overview-icon">{overallMeta.icon}</span>
        <div className="pi-overview-info">
          <h3>{overallMeta.title}</h3>
          <p>
            {overallRisk === 'NONE'
              ? `Inspected ${total_columns_scanned} columns across sampled records. No sensitive entities discovered.`
              : `Detected ${total_findings} sensitive findings across ${pii_columns_count} of ${total_columns_scanned} columns scanned.`}
          </p>
        </div>
        <span className={`pi-overview-pill pi-overview-pill--${overallMeta.tone}`}>
          OVERALL RISK: {overallRisk}
        </span>
      </section>

      {/* ================= KPI GRID ================= */}
      <section className="pi-kpi-grid">
        <div className="pi-kpi pi-kpi--info">
          <small>PII Columns</small>
          <strong>{pii_columns_count}</strong>
          <em>of {total_columns_scanned} total columns</em>
        </div>
        <div className="pi-kpi pi-kpi--accent">
          <small>Total Findings</small>
          <strong>{total_findings}</strong>
          <em>Across all entity recognizers</em>
        </div>
        <div className={`pi-kpi ${riskBreakdown.HIGH > 0 ? 'pi-kpi--danger' : 'pi-kpi--muted'}`}>
          <small>High Risk</small>
          <strong>{riskBreakdown.HIGH || 0}</strong>
          <em>Financial / Government ID</em>
        </div>
        <div className={`pi-kpi ${riskBreakdown.MEDIUM > 0 ? 'pi-kpi--warning' : 'pi-kpi--muted'}`}>
          <small>Medium Risk</small>
          <strong>{riskBreakdown.MEDIUM || 0}</strong>
          <em>Contact / Identity details</em>
        </div>
        <div className={`pi-kpi ${riskBreakdown.LOW > 0 ? 'pi-kpi--amber' : 'pi-kpi--muted'}`}>
          <small>Low Risk</small>
          <strong>{riskBreakdown.LOW || 0}</strong>
          <em>Weak / Generic matches</em>
        </div>
      </section>

      {/* ================= ENTITY BREAKDOWN ================= */}
      {Object.keys(entityBreakdown).length > 0 && (
        <section className="pi-entity-section">
          <div className="pi-section-head">
            <h2>Entity Type Breakdown</h2>
            {selectedEntity !== 'ALL' && (
              <button
                className="pi-btn pi-btn--ghost pi-btn--xs"
                onClick={() => setSelectedEntity('ALL')}
              >
                Clear filter ({formatEntityName(selectedEntity)})
              </button>
            )}
          </div>

          <div className="pi-entity-grid">
            {Object.entries(entityBreakdown).map(([entity, count]) => {
              const isSelected = selectedEntity === entity;
              return (
                <button
                  key={entity}
                  type="button"
                  className={`pi-entity-btn ${isSelected ? 'pi-entity-btn--active' : ''}`}
                  onClick={() => setSelectedEntity(isSelected ? 'ALL' : entity)}
                >
                  <span className="pi-entity-icon">{getEntityIcon(entity)}</span>
                  <span className="pi-entity-name">{formatEntityName(entity)}</span>
                  <span className="pi-entity-count">{count}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* ================= FINDINGS ================= */}
      <section className="pi-panel">
        <div className="pi-panel-head">
          <h3>Detection Findings</h3>
          <div className="pi-filter-row">
            <input
              type="text"
              className="pi-input"
              placeholder="Search by column or entity…"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <div className="pi-risk-filters">
              {['ALL', 'HIGH', 'MEDIUM', 'LOW'].map((r) => (
                <button
                  key={r}
                  type="button"
                  className={`pi-risk-btn ${
                    selectedRisk === r ? 'pi-risk-btn--active' : ''
                  }`}
                  onClick={() => setSelectedRisk(r)}
                >
                  {r}
                </button>
              ))}
            </div>
          </div>
        </div>

        {filteredFindings.length === 0 ? (
          <div className="pi-empty">
            <span className="pi-empty-icon">🎉</span>
            <h4>No Matching PII Findings</h4>
            <p>
              {findings.length === 0
                ? 'No sensitive data or PII entities were discovered in this dataset version.'
                : 'No findings match the current filter selection.'}
            </p>
          </div>
        ) : (
          <div className="pi-table-wrap">
            <table className="pi-table">
              <thead>
                <tr>
                  <th>Column</th>
                  <th>Entity Type</th>
                  <th>Detection Source</th>
                  <th>Confidence</th>
                  <th>Sample Match Rate</th>
                  <th>Risk Level</th>
                  <th>Masked Preview</th>
                </tr>
              </thead>
              <tbody>
                {filteredFindings.map((finding, idx) => {
                  const risk = getRiskBadge(finding.risk_level);
                  const icon = getEntityIcon(finding.entity_type);
                  const confPct = Math.round(finding.confidence * 100);
                  const confTone =
                    confPct >= 80 ? 'high' : confPct >= 50 ? 'medium' : 'low';

                  return (
                    <tr
                      key={finding.id || idx}
                      className={finding.risk_level === 'HIGH' ? 'pi-row-high' : ''}
                    >
                      <td>
                        <code className="pi-col-code">{finding.column_name}</code>
                      </td>
                      <td>
                        <span className="pi-entity-pill">
                          <span>{icon}</span>
                          <span>{finding.entity_type}</span>
                        </span>
                      </td>
                      <td>
                        <span className={`pi-source ${getSourceTone(finding.detection_source)}`}>
                          {getSourceLabel(finding.detection_source)}
                        </span>
                      </td>
                      <td>
                        <div className="pi-conf">
                          <span className={`pi-conf-value pi-conf-value--${confTone}`}>
                            {confPct}%
                          </span>
                          <div className="pi-conf-track">
                            <div
                              className={`pi-conf-fill pi-conf-fill--${confTone}`}
                              style={{ width: `${confPct}%` }}
                            />
                          </div>
                        </div>
                      </td>
                      <td>
                        {finding.sampled_count > 0 ? (
                          <span className="pi-rate">
                            {finding.detected_count} / {finding.sampled_count}{' '}
                            <span className="pi-muted">
                              ({Math.round(finding.detection_rate * 100)}%)
                            </span>
                          </span>
                        ) : (
                          <span className="pi-muted">Heuristic only</span>
                        )}
                      </td>
                      <td>
                        <span
                          className="pi-risk"
                          style={{
                            color: risk.color,
                            borderColor: risk.color,
                            background: `${risk.color}22`,
                          }}
                        >
                          {risk.icon} {risk.label}
                        </span>
                      </td>
                      <td>
                        <code className="pi-masked">
                          {finding.masked_preview || '[MASKED]'}
                        </code>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ================= PRIVACY GUARANTEE ================= */}
      <section className="pi-privacy">
        <span className="pi-privacy-icon">🛡</span>
        <div>
          <h4>Data Privacy &amp; Compliance Assurance</h4>
          <p>
            Microsoft Presidio Analyzer performs deterministic, bounded sampling on
            string candidates without storing full records. All sample representations
            undergo one-way cryptographic masking before database persistence and API
            transport.
          </p>
        </div>
      </section>
    </div>
  );
}