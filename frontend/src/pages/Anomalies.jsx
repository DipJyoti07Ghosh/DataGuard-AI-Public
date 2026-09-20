/**
 * DataGuard AI — Anomaly & Outlier Detection Dashboard (Phase 8)
 *
 * Dark glassmorphism interface displaying multi-method statistical, ML,
 * and categorical anomaly findings, severity scoring, and structured explainability.
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

  // Severity style helper
  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return { bg: 'bg-rose-500/20 text-rose-400 border-rose-500/40', dot: 'bg-rose-400' };
      case 'HIGH':
        return { bg: 'bg-amber-500/20 text-amber-400 border-amber-500/40', dot: 'bg-amber-400' };
      case 'MEDIUM':
        return { bg: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/40', dot: 'bg-yellow-400' };
      case 'LOW':
      default:
        return { bg: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40', dot: 'bg-emerald-400' };
    }
  };

  const getScoreColor = (score) => {
    if (score >= 80) return 'text-rose-400 from-rose-500 to-red-600';
    if (score >= 60) return 'text-amber-400 from-amber-500 to-orange-600';
    if (score >= 35) return 'text-yellow-400 from-yellow-500 to-amber-600';
    return 'text-emerald-400 from-emerald-500 to-teal-600';
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
      <div className="flex flex-col items-center justify-center min-h-[60vh] space-y-4">
        <div className="w-12 h-12 border-4 border-indigo-500/20 border-t-indigo-500 rounded-full animate-spin" />
        <p className="text-gray-400 font-medium animate-pulse">Running statistical & ML anomaly detection...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-4xl mx-auto my-12 p-8 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-center space-y-4">
        <div className="w-16 h-16 mx-auto bg-rose-500/20 text-rose-400 rounded-full flex items-center justify-center text-3xl font-bold">
          !
        </div>
        <h2 className="text-xl font-bold text-rose-200">Anomaly Detection Failed</h2>
        <p className="text-gray-400 max-w-lg mx-auto">{error}</p>
        <button
          onClick={() => fetchAnomalies(true)}
          className="px-6 py-2.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl font-medium transition shadow-lg shadow-rose-600/30"
        >
          Try Again
        </button>
      </div>
    );
  }

  const scoreBadge = getSeverityBadge(data?.overall_severity);

  return (
    <div className="space-y-8 pb-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* Navigation Top Bar */}
      <div className="flex flex-wrap items-center justify-between gap-4 pt-4 border-b border-gray-800/80 pb-4">
        <div className="flex items-center space-x-3">
          <Link
            to="/datasets"
            className="text-gray-400 hover:text-gray-200 transition text-sm flex items-center gap-1"
          >
            ← Datasets
          </Link>
          <span className="text-gray-600">/</span>
          <span className="text-gray-300 font-semibold">{data?.dataset_name || 'Dataset'}</span>
          <span className="px-2 py-0.5 text-xs font-mono rounded bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
            V{data?.version_number}
          </span>
        </div>

        {/* Phase Navigation Tabs */}
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/profile`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 transition border border-gray-700/50"
          >
            📊 Profiling
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/quality`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 transition border border-gray-700/50"
          >
            ✅ Quality
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/pii`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 transition border border-gray-700/50"
          >
            🔐 PII
          </Link>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/risk`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-gray-300 transition border border-gray-700/50"
          >
            🤖 ML Risk
          </Link>
          <span className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-amber-500/20 text-amber-300 border border-amber-500/40">
            ⚠ Anomalies
          </span>
          <Link
            to={`/datasets/${datasetId}/versions/${versionId}/issues`}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800/60 hover:bg-gray-700/60 text-cyan-300 transition border border-cyan-500/40"
          >
            🎯 Prioritization / Health
          </Link>
          <button
            onClick={() => fetchAnomalies(true)}
            disabled={recomputing}
            className="px-3 py-1.5 text-xs font-semibold rounded-lg bg-indigo-600/80 hover:bg-indigo-500 text-white transition disabled:opacity-50 border border-indigo-500/40 flex items-center gap-1.5 ml-2"
          >
            {recomputing ? (
              <>
                <span className="w-3 h-3 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                Re-analyzing...
              </>
            ) : (
              '⚡ Re-run Detection'
            )}
          </button>
        </div>
      </div>

      {/* Hero Banner: Dataset Anomaly Score & Executive KPI */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Overall Score Card */}
        <div className="lg:col-span-1 p-6 rounded-2xl bg-gradient-to-br from-gray-900/90 via-gray-900/60 to-gray-800/40 border border-gray-800 backdrop-blur-xl shadow-2xl flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-8 -mt-8 w-32 h-32 bg-amber-500/10 rounded-full blur-2xl" />
          <div>
            <div className="flex items-center justify-between">
              <span className="text-xs uppercase font-bold tracking-wider text-gray-400">
                Dataset Anomaly Index
              </span>
              <span className={`px-2.5 py-1 text-xs font-bold rounded-full border ${scoreBadge.bg}`}>
                <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${scoreBadge.dot}`} />
                {data?.overall_severity}
              </span>
            </div>
            <div className="mt-4 flex items-baseline gap-2">
              <span className={`text-5xl font-extrabold tracking-tight bg-gradient-to-r ${getScoreColor(data?.dataset_anomaly_score)} bg-clip-text text-transparent`}>
                {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
              </span>
              <span className="text-gray-500 font-semibold text-lg">/ 100</span>
            </div>
            <p className="mt-2 text-xs text-gray-400 leading-relaxed">
              Composite severity score weighted across statistical excursions, multi-detector agreement, and sensitive column context.
            </p>
          </div>

          <div className="mt-6 pt-4 border-t border-gray-800/80 flex items-center justify-between text-xs text-gray-400">
            <span>Analyzed at:</span>
            <span className="font-mono text-gray-300">
              {data?.analyzed_at ? new Date(data.analyzed_at).toLocaleString() : 'Just now'}
            </span>
          </div>
        </div>

        {/* Right: Metrics Grid */}
        <div className="lg:col-span-2 grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div className="p-5 rounded-2xl bg-gray-900/60 border border-gray-800/80 backdrop-blur-xl flex flex-col justify-between">
            <span className="text-xs font-semibold text-gray-400">Total Anomalies</span>
            <div className="my-2 text-3xl font-extrabold text-white">
              {data?.total_anomalies || 0}
            </div>
            <span className="text-[11px] text-gray-500">Across all columns</span>
          </div>

          <div className="p-5 rounded-2xl bg-gray-900/60 border border-gray-800/80 backdrop-blur-xl flex flex-col justify-between">
            <span className="text-xs font-semibold text-gray-400">Columns Flagged</span>
            <div className="my-2 text-3xl font-extrabold text-amber-300">
              {data?.columns_with_anomalies || 0}
              <span className="text-sm font-normal text-gray-500 ml-1">
                / {data?.total_columns_analyzed || 0}
              </span>
            </div>
            <span className="text-[11px] text-gray-500">Exhibiting outliers</span>
          </div>

          <div className="p-5 rounded-2xl bg-gray-900/60 border border-rose-500/20 backdrop-blur-xl flex flex-col justify-between">
            <span className="text-xs font-semibold text-rose-400">Critical / High</span>
            <div className="my-2 text-3xl font-extrabold text-rose-400">
              {(data?.critical_count || 0) + (data?.high_count || 0)}
            </div>
            <span className="text-[11px] text-gray-500">Requires review</span>
          </div>

          <div className="p-5 rounded-2xl bg-gray-900/60 border border-yellow-500/20 backdrop-blur-xl flex flex-col justify-between">
            <span className="text-xs font-semibold text-yellow-400">Medium / Low</span>
            <div className="my-2 text-3xl font-extrabold text-yellow-300">
              {(data?.medium_count || 0) + (data?.low_count || 0)}
            </div>
            <span className="text-[11px] text-gray-500">Mild deviations</span>
          </div>
        </div>
      </div>

      {/* Filter & Method Breakdown Controls */}
      <div className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          {/* Method Chips */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-gray-400 font-semibold mr-1">Method:</span>
            {[
              { id: 'ALL', label: 'All Methods' },
              { id: 'MULTI_METHOD_CONSENSUS', label: 'Consensus (2+)' },
              { id: 'IQR', label: 'IQR Outliers' },
              { id: 'Z_SCORE', label: 'Z-Score (|z|≥3)' },
              { id: 'ISOLATION_FOREST', label: 'Isolation Forest' },
              { id: 'CATEGORICAL_FREQUENCY', label: 'Rare Categories' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedMethod(m.id)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition border ${
                  selectedMethod === m.id
                    ? 'bg-indigo-600 text-white border-indigo-500 shadow-lg shadow-indigo-600/30'
                    : 'bg-gray-900/70 text-gray-400 border-gray-800 hover:text-gray-200 hover:bg-gray-800/60'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Severity Filters */}
          <div className="flex items-center gap-1 bg-gray-900/80 p-1 rounded-xl border border-gray-800">
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
              <button
                key={s}
                onClick={() => setSelectedSeverity(s)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition ${
                  selectedSeverity === s
                    ? 'bg-gray-800 text-white shadow'
                    : 'text-gray-400 hover:text-gray-200'
                }`}
              >
                {s}
              </button>
            ))}
          </div>
        </div>

        {/* Search Bar */}
        <div className="relative">
          <input
            type="text"
            value={searchCol}
            onChange={(e) => setSearchCol(e.target.value)}
            placeholder="Search column names..."
            className="w-full bg-gray-900/80 border border-gray-800 rounded-xl px-4 py-2.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:border-indigo-500 focus:ring-1 focus:ring-indigo-500 transition"
          />
          {searchCol && (
            <button
              onClick={() => setSearchCol('')}
              className="absolute right-3 top-2.5 text-xs text-gray-400 hover:text-gray-200"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Column Anomaly Scorecard Table */}
      <div className="bg-gray-900/70 rounded-2xl border border-gray-800 overflow-hidden shadow-2xl backdrop-blur-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-gray-300">
            <thead className="bg-gray-800/60 text-xs uppercase tracking-wider text-gray-400 border-b border-gray-800">
              <tr>
                <th className="px-6 py-4 font-semibold">Column & Phase 7 Context</th>
                <th className="px-6 py-4 font-semibold">Detection Methods</th>
                <th className="px-6 py-4 font-semibold">Anomalies Detected</th>
                <th className="px-6 py-4 font-semibold">Severity</th>
                <th className="px-6 py-4 font-semibold">Score</th>
                <th className="px-6 py-4 font-semibold text-right">Inspection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-800/60">
              {filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-gray-500">
                    No column findings match the selected filter criteria.
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
                      className="hover:bg-gray-800/40 transition cursor-pointer"
                      onClick={() => setSelectedFinding(f)}
                    >
                      {/* Column Name & Phase 7 info */}
                      <td className="px-6 py-4">
                        <div className="font-mono font-semibold text-white text-sm">
                          {f.column_name}
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          {p7Context?.predicted_domain && (
                            <span className="px-2 py-0.5 text-[11px] rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">
                              {p7Context.predicted_domain}
                            </span>
                          )}
                          {p7Context?.risk_level && (
                            <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-gray-800 text-gray-400 border border-gray-700">
                              Risk: {p7Context.risk_level}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Active Methods */}
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1.5">
                          {activeMethods.length === 0 ? (
                            <span className="text-xs text-gray-500 italic">None (Clean)</span>
                          ) : (
                            activeMethods.map((m) => (
                              <span
                                key={m}
                                className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-gray-800 text-gray-300 border border-gray-700"
                              >
                                {m}
                              </span>
                            ))
                          )}
                          {f.detection_method === 'MULTI_METHOD_CONSENSUS' && (
                            <span className="px-2 py-0.5 text-[11px] font-bold rounded-md bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">
                              ★ Consensus
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Anomaly Count & Rate */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-white">
                          {f.anomaly_count}{' '}
                          <span className="text-xs font-normal text-gray-400">
                            ({f.anomaly_rate}%)
                          </span>
                        </div>
                        <div className="w-24 bg-gray-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
                          <div
                            className={`h-full rounded-full bg-gradient-to-r ${getScoreColor(f.score)}`}
                            style={{ width: `${Math.min(100, f.anomaly_rate * 5)}%` }}
                          />
                        </div>
                      </td>

                      {/* Severity */}
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 text-xs font-bold rounded-full border inline-flex items-center gap-1.5 ${sBadge.bg}`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${sBadge.dot}`} />
                          {f.severity}
                        </span>
                      </td>

                      {/* Score Meter */}
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <span className={`font-mono font-bold text-sm ${getScoreColor(f.score).split(' ')[0]}`}>
                            {f.score.toFixed(1)}
                          </span>
                        </div>
                      </td>

                      {/* Inspection button */}
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFinding(f);
                          }}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-gray-800 hover:bg-gray-700 text-gray-200 transition border border-gray-700"
                        >
                          View Evidence →
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

      {/* Explainability / Evidence Slide-over Drawer */}
      {selectedFinding && (
        <div className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end transition-opacity">
          <div className="w-full max-w-2xl bg-gray-900 border-l border-gray-800 shadow-2xl p-8 overflow-y-auto space-y-6">
            {/* Header */}
            <div className="flex items-start justify-between border-b border-gray-800 pb-4">
              <div>
                <span className="text-xs uppercase font-bold tracking-wider text-indigo-400">
                  Anomaly Evidence & Statistical Bounds
                </span>
                <h3 className="text-2xl font-mono font-bold text-white mt-1">
                  {selectedFinding.column_name}
                </h3>
                <div className="mt-2 flex items-center gap-2">
                  <span className={`px-2.5 py-0.5 text-xs font-bold rounded-full border ${getSeverityBadge(selectedFinding.severity).bg}`}>
                    {selectedFinding.severity}
                  </span>
                  <span className="text-xs font-mono text-gray-400">
                    Score: {selectedFinding.score.toFixed(1)} / 100
                  </span>
                </div>
              </div>
              <button
                onClick={() => setSelectedFinding(null)}
                className="p-2 text-gray-400 hover:text-white rounded-lg bg-gray-800/60 hover:bg-gray-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Summary */}
            <div className="p-4 rounded-xl bg-gray-800/40 border border-gray-700/50 space-y-2">
              <span className="text-xs font-semibold uppercase text-gray-400">Finding Summary</span>
              <p className="text-sm text-gray-200 leading-relaxed font-medium">
                {selectedFinding.explanation?.summary || 'No summary available.'}
              </p>
            </div>

            {/* Evidence Drivers */}
            <div className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                Identified Outlier Drivers
              </span>
              <div className="space-y-2">
                {selectedFinding.explanation?.drivers?.length > 0 ? (
                  selectedFinding.explanation.drivers.map((d, i) => (
                    <div key={i} className="flex items-start gap-2 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200">
                      <span className="text-amber-400 font-bold">•</span>
                      <span>{d}</span>
                    </div>
                  ))
                ) : (
                  <p className="text-xs text-gray-500 italic">No positive outlier drivers triggered.</p>
                )}
              </div>
            </div>

            {/* Detector Breakdown Grid */}
            <div className="space-y-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-indigo-400">
                Detector Consensus Breakdown
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                {/* IQR Card */}
                <div className="p-3.5 rounded-xl bg-gray-800/60 border border-gray-700/50 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-gray-200">IQR Detector</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      selectedFinding.evidence?.iqr?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {selectedFinding.evidence?.iqr?.detected ? 'DETECTED' : 'CLEAN'}
                    </span>
                  </div>
                  {selectedFinding.evidence?.iqr?.executed ? (
                    <div className="text-[11px] text-gray-400 space-y-0.5 font-mono">
                      <div>Bounds: [{selectedFinding.evidence.iqr.lower_bound}, {selectedFinding.evidence.iqr.upper_bound}]</div>
                      <div>Q1: {selectedFinding.evidence.iqr.q1} | Q3: {selectedFinding.evidence.iqr.q3}</div>
                      <div>Outliers: {selectedFinding.evidence.iqr.anomaly_count} ({selectedFinding.evidence.iqr.anomaly_rate}%)</div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-gray-500 italic">{selectedFinding.evidence?.iqr?.reason || 'Not executed'}</div>
                  )}
                </div>

                {/* Z-Score Card */}
                <div className="p-3.5 rounded-xl bg-gray-800/60 border border-gray-700/50 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-gray-200">Z-Score Detector</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      selectedFinding.evidence?.zscore?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {selectedFinding.evidence?.zscore?.detected ? 'DETECTED' : 'CLEAN'}
                    </span>
                  </div>
                  {selectedFinding.evidence?.zscore?.executed ? (
                    <div className="text-[11px] text-gray-400 space-y-0.5 font-mono">
                      <div>Mean: {selectedFinding.evidence.zscore.mean} | Std: {selectedFinding.evidence.zscore.std}</div>
                      <div>Max |z|: {selectedFinding.evidence.zscore.max_abs_zscore} (threshold: 3.0)</div>
                      <div>Outliers: {selectedFinding.evidence.zscore.anomaly_count} ({selectedFinding.evidence.zscore.anomaly_rate}%)</div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-gray-500 italic">{selectedFinding.evidence?.zscore?.reason || 'Not executed'}</div>
                  )}
                </div>

                {/* Isolation Forest Card */}
                <div className="p-3.5 rounded-xl bg-gray-800/60 border border-gray-700/50 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-gray-200">Isolation Forest (ML)</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      selectedFinding.evidence?.isolation_forest?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {selectedFinding.evidence?.isolation_forest?.detected ? 'DETECTED' : 'CLEAN'}
                    </span>
                  </div>
                  {selectedFinding.evidence?.isolation_forest?.executed ? (
                    <div className="text-[11px] text-gray-400 space-y-0.5 font-mono">
                      <div>Strategy: {selectedFinding.evidence.isolation_forest.sampling_strategy}</div>
                      <div>Estimated Outliers: {selectedFinding.evidence.isolation_forest.anomaly_count} ({selectedFinding.evidence.isolation_forest.anomaly_rate}%)</div>
                      <div>Min Decision Score: {selectedFinding.evidence.isolation_forest.min_decision_score}</div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-gray-500 italic">{selectedFinding.evidence?.isolation_forest?.reason || 'Not executed'}</div>
                  )}
                </div>

                {/* Categorical Frequency Card */}
                <div className="p-3.5 rounded-xl bg-gray-800/60 border border-gray-700/50 space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-gray-200">Rare Categories (&lt;1%)</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                      selectedFinding.evidence?.categorical_frequency?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-gray-700 text-gray-400'
                    }`}>
                      {selectedFinding.evidence?.categorical_frequency?.detected ? 'DETECTED' : 'CLEAN'}
                    </span>
                  </div>
                  {selectedFinding.evidence?.categorical_frequency?.executed ? (
                    <div className="text-[11px] text-gray-400 space-y-0.5 font-mono">
                      <div>Unique Categories: {selectedFinding.evidence.categorical_frequency.unique_categories_count}</div>
                      <div>Rare Categories: {selectedFinding.evidence.categorical_frequency.rare_category_count}</div>
                      <div>Rare Observation Rate: {selectedFinding.evidence.categorical_frequency.rare_category_rate}%</div>
                    </div>
                  ) : (
                    <div className="text-[11px] text-gray-500 italic">{selectedFinding.evidence?.categorical_frequency?.reason || 'Not executed'}</div>
                  )}
                </div>
              </div>
            </div>

            {/* Caveats & Privacy Protection Banner */}
            <div className="p-4 rounded-xl bg-indigo-500/10 border border-indigo-500/30 space-y-2">
              <span className="text-xs font-semibold uppercase text-indigo-300">
                🛡️ Interpretation & Privacy Protection
              </span>
              <ul className="text-xs text-gray-300 list-disc list-inside space-y-1 leading-relaxed">
                <li>Anomalies represent statistical deviations; they are not proof of data corruption.</li>
                <li>Zero raw PII values are stored or exposed. Only safe statistical aggregates are preserved.</li>
              </ul>
            </div>

            <div className="pt-4 border-t border-gray-800">
              <button
                onClick={() => setSelectedFinding(null)}
                className="w-full py-2.5 bg-gray-800 hover:bg-gray-700 text-white rounded-xl font-medium transition"
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
