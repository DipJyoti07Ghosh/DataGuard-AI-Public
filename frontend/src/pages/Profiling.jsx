/**
 * DataGuard AI — Automated Dataset Profiling Page
 *
 * Implements Phase 4 Automated Profiling:
 * - Dataset-level statistics (Memory, Missing Cells %, Duplicates, Feature breakdown)
 * - Column-level statistical profiles (Mean, Std, Quantiles, Skewness, Kurtosis)
 * - Interactive Recharts distribution histograms & top category bar charts
 * - Pearson feature correlation matrix
 * - All-columns comparison matrix
 */

import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
} from 'recharts';
import { getProfile, generateProfile, getDataset } from '../api/client';

export default function Profiling() {
  const { datasetId, versionId } = useParams();

  const [profile, setProfile] = useState(null);
  const [dataset, setDataset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState('columns'); // 'columns' | 'correlations' | 'table'
  const [selectedColName, setSelectedColName] = useState(null);
  const [colSearchQuery, setColSearchQuery] = useState('');

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
      // 1. Fetch parent dataset details for navigation context
      const ds = await getDataset(datasetId);
      setDataset(ds);

      // 2. Try fetching existing profile, or generate if not exists
      try {
        const prof = await getProfile(datasetId, versionId);
        setProfile(prof);
      } catch (err) {
        if (err.status === 404) {
          // Profile not yet generated -> auto-trigger generation
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
      case 'numeric':
        return 'dtype-numeric';
      case 'datetime':
        return 'dtype-datetime';
      case 'boolean':
        return 'dtype-bool';
      default:
        return 'dtype-object';
    }
  };

  const getCorrelationColor = (val) => {
    if (val === null || val === undefined) return 'rgba(148, 163, 184, 0.1)';
    if (val > 0.7) return 'rgba(99, 102, 241, 0.45)';
    if (val > 0.3) return 'rgba(99, 102, 241, 0.25)';
    if (val > -0.3) return 'rgba(148, 163, 184, 0.08)';
    if (val > -0.7) return 'rgba(239, 68, 68, 0.25)';
    return 'rgba(239, 68, 68, 0.45)';
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner-large"></div>
        <p className="loading-text">
          {generating
            ? 'Generating automated statistical profile, calculating quantiles and correlations...'
            : 'Loading profiling metadata...'}
        </p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="profiling-page">
        <div className="alert-box alert-box--error">
          <span className="alert-icon">⚠️</span>
          <div className="alert-content">
            <strong>Profiling Error</strong>
            <p>{error}</p>
          </div>
        </div>
        <div className="page-actions-row">
          <Link to="/datasets" className="btn btn--secondary">
            ← Back to Datasets
          </Link>
          <button className="btn btn--primary" onClick={handleRegenerate}>
            🔄 Try Generating Profile
          </button>
        </div>
      </div>
    );
  }

  if (!profile) return null;

  const colProfilesList = Object.values(profile.column_profiles);
  const filteredCols = colProfilesList.filter((col) =>
    col.name.toLowerCase().includes(colSearchQuery.toLowerCase())
  );
  const selectedCol = selectedColName ? profile.column_profiles[selectedColName] : null;
  const correlationKeys = profile.correlations ? Object.keys(profile.correlations) : [];

  return (
    <div className="profiling-page">
      {/* Header Block */}
      <div className="page-header-block">
        <div>
          <div className="breadcrumb-nav">
            <Link to="/datasets" className="breadcrumb-link">Datasets</Link>
            <span className="breadcrumb-sep">/</span>
            <span className="breadcrumb-current">{profile.dataset_name}</span>
            <span className="badge badge--accent ml-sm">V{profile.version_number}</span>
          </div>
          <h1 className="page-heading">
            Automated Statistical Profile: {profile.dataset_name}
          </h1>
          <p className="page-subheading">
            Detailed distribution analytics, quantiles, moments, correlations, and quality metrics for Version {profile.version_number}.
          </p>
        </div>

        <div className="header-action-group">
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="btn btn--primary"
            style={{ background: 'linear-gradient(135deg, #6366f1, #8b5cf6)' }}
          >
            🛡 Quality Scorecard
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="btn btn--primary"
            style={{ background: 'linear-gradient(135deg, #ec4899, #8b5cf6)' }}
          >
            🔐 Scan for PII
          </Link>
          <Link to="/datasets" className="btn btn--secondary">
            🗃️ All Datasets
          </Link>
          <button
            className="btn btn--secondary"
            onClick={handleRegenerate}
            disabled={generating}
            id="regenerate-profile-btn"
          >
            {generating ? (
              <>
                <span className="spinner-inline"></span> Computing...
              </>
            ) : (
              '🔄 Recompute Profile'
            )}
          </button>
        </div>
      </div>

      {/* Dataset Overview Stat Cards */}
      <div className="stat-cards-grid">
        <div className="stat-card">
          <span className="stat-card-icon">📊</span>
          <div className="stat-card-details">
            <span className="stat-label">Total Observations</span>
            <span className="stat-value">{profile.row_count.toLocaleString()} rows</span>
          </div>
        </div>

        <div className="stat-card">
          <span className="stat-card-icon">📐</span>
          <div className="stat-card-details">
            <span className="stat-label">Total Features</span>
            <span className="stat-value">{profile.column_count} columns</span>
          </div>
        </div>

        <div className="stat-card">
          <span className="stat-card-icon">
            {profile.missing_cells > 0 ? '⚠️' : '✅'}
          </span>
          <div className="stat-card-details">
            <span className="stat-label">Missing Cells</span>
            <span className={`stat-value ${profile.missing_cells > 0 ? 'text-warning' : 'text-success'}`}>
              {profile.missing_cells.toLocaleString()} ({profile.missing_cells_percentage}%)
            </span>
          </div>
        </div>

        <div className="stat-card">
          <span className="stat-card-icon">
            {profile.duplicate_rows > 0 ? '⚠️' : '✅'}
          </span>
          <div className="stat-card-details">
            <span className="stat-label">Duplicate Rows</span>
            <span className={`stat-value ${profile.duplicate_rows > 0 ? 'text-warning' : 'text-success'}`}>
              {profile.duplicate_rows.toLocaleString()} ({profile.duplicate_rows_percentage}%)
            </span>
          </div>
        </div>

        <div className="stat-card">
          <span className="stat-card-icon">💾</span>
          <div className="stat-card-details">
            <span className="stat-label">Memory Footprint</span>
            <span className="stat-value stat-value--small">{profile.memory_size_display}</span>
          </div>
        </div>
      </div>

      {/* Feature Breakdown Pill Bar */}
      <div className="feature-types-bar">
        <span className="feature-type-item">
          <span className="dtype-badge dtype-numeric">Numeric</span>
          <strong>{profile.numeric_columns_count}</strong>
        </span>
        <span className="feature-type-item">
          <span className="dtype-badge dtype-object">Categorical / Text</span>
          <strong>{profile.categorical_columns_count}</strong>
        </span>
        <span className="feature-type-item">
          <span className="dtype-badge dtype-datetime">Datetime</span>
          <strong>{profile.datetime_columns_count}</strong>
        </span>
        <span className="feature-type-item">
          <span className="dtype-badge dtype-bool">Boolean</span>
          <strong>{profile.boolean_columns_count}</strong>
        </span>
      </div>

      {/* Main Tab Navigation */}
      <div className="results-tab-bar">
        <button
          className={`tab-btn ${activeTab === 'columns' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('columns')}
          id="tab-col-explorer-btn"
        >
          🔍 Feature Explorer & Distributions
        </button>
        {correlationKeys.length > 1 && (
          <button
            className={`tab-btn ${activeTab === 'correlations' ? 'tab-btn--active' : ''}`}
            onClick={() => setActiveTab('correlations')}
            id="tab-correlations-btn"
          >
            📈 Feature Correlation Matrix ({correlationKeys.length}x{correlationKeys.length})
          </button>
        )}
        <button
          className={`tab-btn ${activeTab === 'table' ? 'tab-btn--active' : ''}`}
          onClick={() => setActiveTab('table')}
          id="tab-all-cols-btn"
        >
          📑 Full Summary Matrix ({profile.column_count} cols)
        </button>
      </div>

      {/* Tab 1: Column Deep-Dive Explorer */}
      {activeTab === 'columns' && (
        <div className="profile-explorer-layout">
          {/* Left Column Selector */}
          <div className="column-selector-panel">
            <div className="column-selector-header">
              <input
                type="text"
                placeholder="Filter features..."
                value={colSearchQuery}
                onChange={(e) => setColSearchQuery(e.target.value)}
                className="form-input col-search-input"
              />
            </div>
            <div className="column-items-list">
              {filteredCols.map((col) => {
                const isSelected = selectedColName === col.name;
                return (
                  <div
                    key={col.name}
                    className={`col-select-item ${isSelected ? 'col-select-item--active' : ''}`}
                    onClick={() => setSelectedColName(col.name)}
                    id={`col-item-${col.name}`}
                  >
                    <div className="col-item-title-row">
                      <span className="col-item-name">{col.name}</span>
                      <span className={`dtype-badge ${getDtypeBadgeClass(col.type_category)}`}>
                        {col.type_category}
                      </span>
                    </div>
                    <div className="col-item-sub">
                      <span>{col.missing_percentage > 0 ? `${col.missing_percentage}% null` : '100% complete'}</span>
                      <span>• {col.unique_count} unique</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right Column Deep-Dive Detail */}
          {selectedCol && (
            <div className="column-detail-panel" id="column-detail-view">
              <div className="col-detail-header">
                <div>
                  <div className="col-detail-title-group">
                    <h2 className="col-detail-name">{selectedCol.name}</h2>
                    <span className={`dtype-badge ${getDtypeBadgeClass(selectedCol.type_category)}`}>
                      {selectedCol.type_category.toUpperCase()} ({selectedCol.dtype})
                    </span>
                    {selectedCol.missing_count === 0 ? (
                      <span className="badge badge--success">Complete</span>
                    ) : (
                      <span className="badge badge--warning">{selectedCol.missing_count} Missing</span>
                    )}
                  </div>
                  <p className="col-detail-stats-sub">
                    <strong>{selectedCol.count.toLocaleString()}</strong> valid values •{' '}
                    <strong>{selectedCol.unique_count.toLocaleString()}</strong> distinct values ({selectedCol.unique_percentage}%)
                  </p>
                </div>
              </div>

              {/* Numeric Column Deep-Dive */}
              {selectedCol.type_category === 'numeric' && (
                <div className="metric-deepdive-grid">
                  {/* Moments & Basic Stats Card */}
                  <div className="card stat-card-inner">
                    <h4 className="card-subheading">📐 Descriptive Statistics</h4>
                    <div className="stats-metric-list">
                      <div className="stat-metric-row">
                        <span className="metric-name">Mean</span>
                        <span className="metric-val">{selectedCol.mean !== null ? selectedCol.mean.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Standard Deviation (σ)</span>
                        <span className="metric-val">{selectedCol.std !== null ? selectedCol.std.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Minimum</span>
                        <span className="metric-val">{selectedCol.min !== null ? selectedCol.min.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Maximum</span>
                        <span className="metric-val">{selectedCol.max !== null ? selectedCol.max.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Skewness</span>
                        <span className="metric-val">{selectedCol.skewness !== null ? selectedCol.skewness : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Kurtosis</span>
                        <span className="metric-val">{selectedCol.kurtosis !== null ? selectedCol.kurtosis : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Zero Values</span>
                        <span className="metric-val">{selectedCol.zeros_count}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Negative Values</span>
                        <span className="metric-val">{selectedCol.negative_count}</span>
                      </div>
                    </div>
                  </div>

                  {/* Quantiles & Percentiles Card */}
                  <div className="card stat-card-inner">
                    <h4 className="card-subheading">🎯 Quantiles & Percentiles</h4>
                    <div className="stats-metric-list">
                      <div className="stat-metric-row">
                        <span className="metric-name">25th Percentile (Q1)</span>
                        <span className="metric-val">{selectedCol.q25 !== null ? selectedCol.q25.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">50th Percentile (Median)</span>
                        <span className="metric-val font-bold">{selectedCol.q50 !== null ? selectedCol.q50.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">75th Percentile (Q3)</span>
                        <span className="metric-val">{selectedCol.q75 !== null ? selectedCol.q75.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">95th Percentile</span>
                        <span className="metric-val">{selectedCol.q95 !== null ? selectedCol.q95.toLocaleString() : 'N/A'}</span>
                      </div>
                      <div className="stat-metric-row">
                        <span className="metric-name">Interquartile Range (IQR)</span>
                        <span className="metric-val">
                          {selectedCol.q75 !== null && selectedCol.q25 !== null
                            ? (selectedCol.q75 - selectedCol.q25).toFixed(2)
                            : 'N/A'}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Distribution Histogram Chart */}
                  <div className="card stat-card-inner full-width-card">
                    <h4 className="card-subheading">📊 Frequency Distribution Histogram</h4>
                    {selectedCol.histogram && selectedCol.histogram.length > 0 ? (
                      <div className="chart-container-histogram">
                        <ResponsiveContainer width="100%" height={260}>
                          <BarChart
                            data={selectedCol.histogram}
                            margin={{ top: 15, right: 20, left: 10, bottom: 25 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
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
                                backgroundColor: '#111827',
                                borderColor: 'rgba(99, 102, 241, 0.3)',
                                borderRadius: '8px',
                                color: '#f1f5f9',
                                fontSize: '12px',
                              }}
                              formatter={(value) => [`${value} rows`, 'Frequency']}
                              labelFormatter={(label) => `Interval: ${label}`}
                            />
                            <Bar dataKey="count" fill="#6366f1" radius={[4, 4, 0, 0]}>
                              {selectedCol.histogram.map((entry, index) => (
                                <Cell
                                  key={`cell-${index}`}
                                  fill={index % 2 === 0 ? '#6366f1' : '#818cf8'}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <p className="text-muted p-md">No histogram data available.</p>
                    )}
                  </div>
                </div>
              )}

              {/* Categorical & Text Column Deep-Dive */}
              {(selectedCol.type_category === 'categorical' || selectedCol.type_category === 'text' || selectedCol.type_category === 'boolean') && (
                <div className="metric-deepdive-grid">
                  {/* Top Categories Bar Chart */}
                  <div className="card stat-card-inner full-width-card">
                    <h4 className="card-subheading">🏷️ Top Categories & Frequencies</h4>
                    {selectedCol.top_categories && selectedCol.top_categories.length > 0 ? (
                      <div className="chart-container-categories">
                        <ResponsiveContainer width="100%" height={260}>
                          <BarChart
                            data={selectedCol.top_categories}
                            layout="vertical"
                            margin={{ top: 10, right: 30, left: 60, bottom: 10 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.1)" />
                            <XAxis type="number" stroke="#94a3b8" fontSize={11} />
                            <YAxis
                              dataKey="value"
                              type="category"
                              stroke="#94a3b8"
                              fontSize={11}
                              width={100}
                              tickFormatter={(v) => (v.length > 14 ? `${v.slice(0, 14)}...` : v)}
                            />
                            <Tooltip
                              contentStyle={{
                                backgroundColor: '#111827',
                                borderColor: 'rgba(99, 102, 241, 0.3)',
                                borderRadius: '8px',
                                color: '#f1f5f9',
                                fontSize: '12px',
                              }}
                              formatter={(value, name, props) => [
                                `${value} rows (${props.payload.percentage}%)`,
                                'Frequency',
                              ]}
                            />
                            <Bar dataKey="count" fill="#8b5cf6" radius={[0, 4, 4, 0]}>
                              {selectedCol.top_categories.map((entry, index) => (
                                <Cell
                                  key={`cat-cell-${index}`}
                                  fill={index === 0 ? '#10b981' : '#8b5cf6'}
                                />
                              ))}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    ) : (
                      <p className="text-muted p-md">No category counts available.</p>
                    )}
                  </div>

                  {/* Text Length Stats if text */}
                  {selectedCol.type_category === 'text' && (
                    <div className="card stat-card-inner full-width-card">
                      <h4 className="card-subheading">📝 Text Character Lengths</h4>
                      <div className="stats-metric-list inline-stats">
                        <div className="stat-metric-row">
                          <span className="metric-name">Min Character Length</span>
                          <span className="metric-val">{selectedCol.min_length ?? 'N/A'}</span>
                        </div>
                        <div className="stat-metric-row">
                          <span className="metric-name">Max Character Length</span>
                          <span className="metric-val">{selectedCol.max_length ?? 'N/A'}</span>
                        </div>
                        <div className="stat-metric-row">
                          <span className="metric-name">Average Length</span>
                          <span className="metric-val">{selectedCol.avg_length ?? 'N/A'} chars</span>
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Datetime Column Deep-Dive */}
              {selectedCol.type_category === 'datetime' && (
                <div className="card stat-card-inner full-width-card">
                  <h4 className="card-subheading">📅 Temporal Span</h4>
                  <div className="stats-metric-list inline-stats">
                    <div className="stat-metric-row">
                      <span className="metric-name">Earliest Timestamp</span>
                      <span className="metric-val">{selectedCol.min_date ?? 'N/A'}</span>
                    </div>
                    <div className="stat-metric-row">
                      <span className="metric-name">Latest Timestamp</span>
                      <span className="metric-val">{selectedCol.max_date ?? 'N/A'}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab 2: Correlation Matrix */}
      {activeTab === 'correlations' && profile.correlations && (
        <div className="card results-table-card">
          <div className="p-lg">
            <h3 className="section-title">Pearson Correlation Matrix</h3>
            <p className="text-secondary text-sm">
              Values close to +1.0 indicate strong positive linear relationship; values close to -1.0 indicate strong negative relationship.
            </p>
          </div>
          <div className="table-responsive">
            <table className="data-table correlation-matrix-table">
              <thead>
                <tr>
                  <th className="corr-header-th">Feature</th>
                  {correlationKeys.map((colKey) => (
                    <th key={colKey} title={colKey} className="corr-th">
                      {colKey.length > 15 ? `${colKey.slice(0, 12)}...` : colKey}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {correlationKeys.map((rowKey) => (
                  <tr key={rowKey}>
                    <td className="corr-row-label">
                      <code>{rowKey}</code>
                    </td>
                    {correlationKeys.map((colKey) => {
                      const val = profile.correlations[rowKey]?.[colKey];
                      const isSelf = rowKey === colKey;
                      return (
                        <td
                          key={colKey}
                          className={`corr-cell ${isSelf ? 'corr-cell-self' : ''}`}
                          style={{
                            backgroundColor: isSelf ? 'rgba(99, 102, 241, 0.15)' : getCorrelationColor(val),
                          }}
                          title={`${rowKey} ↔ ${colKey}: ${val}`}
                        >
                          {val !== undefined && val !== null ? val.toFixed(2) : '-'}
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

      {/* Tab 3: All Columns Comparison Matrix Table */}
      {activeTab === 'table' && (
        <div className="card results-table-card">
          <div className="table-responsive">
            <table className="data-table">
              <thead>
                <tr>
                  <th style={{ width: '40px' }}>#</th>
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
                    <td className="text-muted">{idx + 1}</td>
                    <td>
                      <code className="column-name-code">{col.name}</code>
                    </td>
                    <td>
                      <span className={`dtype-badge ${getDtypeBadgeClass(col.type_category)}`}>
                        {col.type_category}
                      </span>
                    </td>
                    <td>{col.count.toLocaleString()}</td>
                    <td>
                      <span className={col.missing_percentage > 0 ? 'text-warning font-bold' : 'text-success'}>
                        {col.missing_percentage}%
                      </span>
                    </td>
                    <td>
                      {col.unique_count.toLocaleString()} ({col.unique_percentage}%)
                    </td>
                    <td>
                      {col.type_category === 'numeric' ? (
                        <span>μ = {col.mean ?? 'N/A'}</span>
                      ) : col.top_categories && col.top_categories[0] ? (
                        <span>
                          {col.top_categories[0].value} ({col.top_categories[0].percentage}%)
                        </span>
                      ) : (
                        <span className="text-muted">-</span>
                      )}
                    </td>
                    <td>
                      {col.type_category === 'numeric' && col.min !== null ? (
                        <span>[{col.min}, {col.max}]</span>
                      ) : col.min_date ? (
                        <span>[{col.min_date.slice(0, 10)}, {col.max_date.slice(0, 10)}]</span>
                      ) : (
                        <span className="text-muted">-</span>
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
