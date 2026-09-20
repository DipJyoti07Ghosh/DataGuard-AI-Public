/**
 * DataGuard AI — Anomaly & Outlier Detection Dashboard (Phase 8)
 *
 * Enterprise Data Observability & Statistical Anomaly Dashboard
 * Displays multi-method statistical (IQR, Z-Score), ML (Isolation Forest),
 * and categorical frequency anomaly findings with rich explainability.
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

  // Severity styling tokens
  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return {
          bg: 'bg-rose-500/15 text-rose-300 border-rose-500/40 shadow-rose-950/30',
          dot: 'bg-rose-400',
          badgeText: 'text-rose-300',
        };
      case 'HIGH':
        return {
          bg: 'bg-orange-500/15 text-orange-300 border-orange-500/40 shadow-orange-950/30',
          dot: 'bg-orange-400',
          badgeText: 'text-orange-300',
        };
      case 'MEDIUM':
        return {
          bg: 'bg-amber-500/15 text-amber-300 border-amber-500/40 shadow-amber-950/30',
          dot: 'bg-amber-400',
          badgeText: 'text-amber-300',
        };
      case 'LOW':
      default:
        return {
          bg: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/40 shadow-emerald-950/30',
          dot: 'bg-emerald-400',
          badgeText: 'text-emerald-300',
        };
    }
  };

  const getScoreColor = (score) => {
    if (score >= 75) return 'text-rose-400 from-rose-500 to-red-600';
    if (score >= 50) return 'text-orange-400 from-orange-500 to-amber-600';
    if (score >= 25) return 'text-amber-400 from-amber-500 to-yellow-600';
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
        <div className="w-12 h-12 border-4 border-amber-500/20 border-t-amber-500 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium animate-pulse">
          Running statistical & ML anomaly detection engine...
        </p>
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
        <p className="text-slate-400 max-w-lg mx-auto">{error}</p>
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
  const totalRowsAnalyzed = data?.total_rows || data?.total_rows_analyzed || (findings.length > 0 ? findings[0].explanation?.phase7_context?.total_rows : null) || 0;

  return (
    <div className="space-y-8 pb-16 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      {/* 1. Header & Breadcrumb Context */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pt-4 border-b border-slate-800 pb-5">
        <div>
          <div className="flex items-center space-x-3 text-xs text-slate-400 mb-1.5">
            <Link
              to="/datasets"
              className="hover:text-cyan-400 transition flex items-center gap-1 font-medium"
            >
              ← Datasets
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-slate-200 font-semibold">{data?.dataset_name || 'Dataset'}</span>
            <span className="px-2 py-0.5 text-xs font-mono rounded bg-amber-500/20 text-amber-300 border border-amber-500/30">
              V{data?.version_number}
            </span>
            <span className="text-slate-600">•</span>
            <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Statistical & ML Engine Active
            </span>
          </div>

          <div className="flex items-center gap-3">
            <span className="text-3xl">⚠️</span>
            <div>
              <h1 className="text-2xl font-bold bg-gradient-to-r from-amber-400 via-orange-300 to-yellow-200 bg-clip-text text-transparent">
                Anomaly Detection
              </h1>
              <p className="text-slate-400 text-sm mt-0.5">
                Identify statistically unusual patterns across your dataset.
              </p>
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-3">
          <button
            onClick={() => fetchAnomalies(true)}
            disabled={recomputing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-amber-500 to-orange-600 hover:from-amber-400 hover:to-orange-500 text-white font-medium text-sm shadow-lg shadow-amber-500/20 transition-all duration-200 disabled:opacity-50"
          >
            {recomputing ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>Re-analyzing...</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Re-run Detection</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Navigation Sub-Tabs */}
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-800 pb-3">
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/profile`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
        >
          📊 Profiling
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/quality`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
        >
          ✅ Data Quality
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/pii`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
        >
          🔒 PII Scan
        </Link>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/risk`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
        >
          🧠 ML Risk
        </Link>
        <span className="px-4 py-2 rounded-lg text-sm font-semibold text-amber-300 bg-amber-950/60 border border-amber-500/40 shadow-sm">
          ⚠️ Anomalies
        </span>
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/issues`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-cyan-300 hover:text-white hover:bg-slate-800/50 transition-colors border border-cyan-500/30"
        >
          🎯 Prioritization / Health
        </Link>
      </div>

      {/* 2. Top KPI Section: 4 Compact Aligned Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Anomalies Detected */}
        <div className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800/80 backdrop-blur-xl shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Anomalies Detected
            </span>
            <span className="text-xl">🔍</span>
          </div>
          <div className="my-2 text-3xl font-extrabold text-white">
            {data?.total_anomalies || 0}
          </div>
          <span className="text-xs text-slate-500">Across all analyzed columns</span>
        </div>

        {/* Card 2: Columns Affected */}
        <div className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800/80 backdrop-blur-xl shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
              Columns Affected
            </span>
            <span className="text-xl">📐</span>
          </div>
          <div className="my-2 text-3xl font-extrabold text-amber-300">
            {data?.columns_with_anomalies || 0}
            <span className="text-sm font-normal text-slate-500 ml-1">
              / {data?.total_columns_analyzed || 0}
            </span>
          </div>
          <span className="text-xs text-slate-500">Columns with outlier observations</span>
        </div>

        {/* Card 3: Rows Analyzed */}
        <div className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800/80 backdrop-blur-xl shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
              Rows Analyzed
            </span>
            <span className="text-xl">📊</span>
          </div>
          <div className="my-2 text-3xl font-extrabold text-cyan-300">
            {totalRowsAnalyzed ? totalRowsAnalyzed.toLocaleString() : '100%'}
          </div>
          <span className="text-xs text-slate-500">Dataset population evaluated</span>
        </div>

        {/* Card 4: Dataset Anomaly Score */}
        <div className="p-5 rounded-2xl bg-slate-900/70 border border-slate-800/80 backdrop-blur-xl shadow-lg flex flex-col justify-between">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Dataset Anomaly Score
            </span>
            <span className={`px-2 py-0.5 text-[11px] font-bold rounded-full border ${scoreBadge.bg}`}>
              {data?.overall_severity || 'LOW'}
            </span>
          </div>
          <div className="my-2 flex items-baseline gap-1.5">
            <span className={`text-3xl font-extrabold bg-gradient-to-r ${getScoreColor(data?.dataset_anomaly_score)} bg-clip-text text-transparent`}>
              {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
            </span>
            <span className="text-slate-500 text-sm font-medium">/ 100</span>
          </div>
          <span className="text-xs text-slate-500">Composite anomaly index</span>
        </div>
      </div>

      {/* 3. Anomaly Overview & Severity Distribution */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Hero Card: Anomaly Score Meter */}
        <div className="lg:col-span-4 p-6 rounded-2xl bg-gradient-to-br from-slate-900/90 via-slate-900/70 to-slate-800/50 border border-slate-800/80 backdrop-blur-xl shadow-xl flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 -mr-6 -mt-6 w-28 h-28 bg-amber-500/10 rounded-full blur-2xl" />
          <div>
            <div className="flex items-center justify-between mb-4">
              <span className="text-xs uppercase font-bold tracking-wider text-slate-400">
                Composite Anomaly Index
              </span>
              <span className={`px-2.5 py-1 text-xs font-bold rounded-full border shadow-sm ${scoreBadge.bg}`}>
                <span className={`inline-block w-1.5 h-1.5 rounded-full mr-1.5 ${scoreBadge.dot}`} />
                {data?.overall_severity}
              </span>
            </div>

            <div className="my-3 flex items-baseline gap-2">
              <span className={`text-5xl font-extrabold tracking-tight bg-gradient-to-r ${getScoreColor(data?.dataset_anomaly_score)} bg-clip-text text-transparent`}>
                {data?.dataset_anomaly_score?.toFixed(1) || '0.0'}
              </span>
              <span className="text-slate-500 font-semibold text-lg">/ 100</span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed mt-2">
              Consensus score weighted across multi-detector agreement (IQR, Z-Score, Isolation Forest), statistical excursion rates, and sensitive column context.
            </p>
          </div>

          <div className="mt-6 pt-4 border-t border-slate-800/80 flex items-center justify-between text-xs text-slate-400">
            <span>Last Analyzed:</span>
            <span className="font-mono text-slate-300">
              {data?.analyzed_at ? new Date(data.analyzed_at).toLocaleTimeString() : 'Just now'}
            </span>
          </div>
        </div>

        {/* Right Card: Severity Distribution & Consensus Breakdown */}
        <div className="lg:col-span-8 p-6 rounded-2xl bg-slate-900/70 border border-slate-800/80 backdrop-blur-xl shadow-xl flex flex-col justify-between space-y-5">
          <div>
            <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
              <span>📊</span> Severity Distribution & Detector Consensus
            </h3>

            {/* Severity Bars */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-5">
              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-rose-500/20">
                <div className="flex items-center justify-between text-xs text-rose-300 font-semibold">
                  <span>CRITICAL</span>
                  <span className="font-mono font-bold">{data?.critical_count || 0}</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-rose-500 h-full rounded-full"
                    style={{
                      width: `${data?.total_anomalies ? ((data.critical_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-orange-500/20">
                <div className="flex items-center justify-between text-xs text-orange-300 font-semibold">
                  <span>HIGH</span>
                  <span className="font-mono font-bold">{data?.high_count || 0}</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-orange-500 h-full rounded-full"
                    style={{
                      width: `${data?.total_anomalies ? ((data.high_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-amber-500/20">
                <div className="flex items-center justify-between text-xs text-amber-300 font-semibold">
                  <span>MEDIUM</span>
                  <span className="font-mono font-bold">{data?.medium_count || 0}</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-amber-500 h-full rounded-full"
                    style={{
                      width: `${data?.total_anomalies ? ((data.medium_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>

              <div className="p-3.5 rounded-xl bg-slate-950/60 border border-emerald-500/20">
                <div className="flex items-center justify-between text-xs text-emerald-300 font-semibold">
                  <span>LOW</span>
                  <span className="font-mono font-bold">{data?.low_count || 0}</span>
                </div>
                <div className="w-full bg-slate-800 h-1.5 rounded-full mt-2 overflow-hidden">
                  <div
                    className="bg-emerald-500 h-full rounded-full"
                    style={{
                      width: `${data?.total_anomalies ? ((data.low_count || 0) / data.total_anomalies) * 100 : 0}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {/* Explanatory note */}
            <div className="p-3.5 rounded-xl bg-indigo-950/30 border border-indigo-500/20 text-xs text-slate-300 flex items-start gap-2.5">
              <span className="text-base">💡</span>
              <span className="leading-relaxed">
                <strong className="text-indigo-300 font-semibold">Multi-Method Consensus:</strong> High-confidence anomalies trigger multiple independent detectors (IQR + Z-Score + ML Isolation Forest). Single-detector anomalies indicate potential tail events or skewed distributions.
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* 4. Filter & Search Controls */}
      <div className="space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          {/* Method Filter Chips */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-xs text-slate-400 font-semibold mr-1">Method:</span>
            {[
              { id: 'ALL', label: 'All Methods' },
              { id: 'MULTI_METHOD_CONSENSUS', label: 'Consensus (2+)' },
              { id: 'IQR', label: 'IQR Outliers' },
              { id: 'Z_SCORE', label: 'Z-Score (|z|≥3)' },
              { id: 'ISOLATION_FOREST', label: 'Isolation Forest (ML)' },
              { id: 'CATEGORICAL_FREQUENCY', label: 'Rare Categories' },
            ].map((m) => (
              <button
                key={m.id}
                onClick={() => setSelectedMethod(m.id)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-xl transition border ${
                  selectedMethod === m.id
                    ? 'bg-amber-500 text-white border-amber-400 shadow-md shadow-amber-500/20'
                    : 'bg-slate-900/70 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800/60'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>

          {/* Severity Filters */}
          <div className="flex items-center gap-1 bg-slate-900/80 p-1 rounded-xl border border-slate-800">
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
              <button
                key={s}
                onClick={() => setSelectedSeverity(s)}
                className={`px-2.5 py-1 text-xs font-semibold rounded-lg transition ${
                  selectedSeverity === s
                    ? 'bg-slate-800 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
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
            className="w-full bg-slate-900/80 border border-slate-800 rounded-xl px-4 py-2.5 text-sm text-slate-200 placeholder-slate-500 focus:outline-none focus:border-amber-500 focus:ring-1 focus:ring-amber-500 transition"
          />
          {searchCol && (
            <button
              onClick={() => setSearchCol('')}
              className="absolute right-3 top-2.5 text-xs text-slate-400 hover:text-slate-200"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* 5. Anomaly Findings Table */}
      <div className="bg-slate-900/70 rounded-2xl border border-slate-800 overflow-hidden shadow-2xl backdrop-blur-xl">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300 border-collapse">
            <thead className="bg-slate-800/60 text-xs uppercase tracking-wider text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-6 py-4 font-semibold">Column & Phase 7 Context</th>
                <th className="px-6 py-4 font-semibold">Detection Methods</th>
                <th className="px-6 py-4 font-semibold">Anomalies Detected</th>
                <th className="px-6 py-4 font-semibold">Severity</th>
                <th className="px-6 py-4 font-semibold">Anomaly Score</th>
                <th className="px-6 py-4 font-semibold text-right">Inspection</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredFindings.length === 0 ? (
                <tr>
                  <td colSpan="6" className="px-6 py-12 text-center text-slate-500">
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
                      className="hover:bg-slate-800/40 transition cursor-pointer group"
                      onClick={() => setSelectedFinding(f)}
                    >
                      {/* Column Name & Phase 7 info */}
                      <td className="px-6 py-4">
                        <div className="font-mono font-semibold text-white text-sm group-hover:text-amber-300 transition-colors">
                          {f.column_name}
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          {p7Context?.predicted_domain && (
                            <span className="px-2 py-0.5 text-[11px] rounded bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">
                              {p7Context.predicted_domain}
                            </span>
                          )}
                          {p7Context?.risk_level && (
                            <span className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-800 text-slate-400 border border-slate-700">
                              Risk: {p7Context.risk_level}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Active Methods */}
                      <td className="px-6 py-4">
                        <div className="flex flex-wrap gap-1.5">
                          {activeMethods.length === 0 ? (
                            <span className="text-xs text-slate-500 italic">None (Clean)</span>
                          ) : (
                            activeMethods.map((m) => (
                              <span
                                key={m}
                                className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-slate-800 text-slate-300 border border-slate-700"
                              >
                                {m}
                              </span>
                            ))
                          )}
                          {f.detection_method === 'MULTI_METHOD_CONSENSUS' && (
                            <span className="px-2 py-0.5 text-[11px] font-bold rounded-md bg-amber-500/20 text-amber-300 border border-amber-500/30">
                              ★ Consensus
                            </span>
                          )}
                        </div>
                      </td>

                      {/* Anomaly Count & Rate */}
                      <td className="px-6 py-4">
                        <div className="font-semibold text-white">
                          {f.anomaly_count}{' '}
                          <span className="text-xs font-normal text-slate-400">
                            ({f.anomaly_rate}%)
                          </span>
                        </div>
                        <div className="w-24 bg-slate-800 rounded-full h-1.5 mt-1.5 overflow-hidden">
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
                        <span className={`font-mono font-bold text-sm ${getScoreColor(f.score).split(' ')[0]}`}>
                          {f.score.toFixed(1)}
                        </span>
                      </td>

                      {/* Inspection button */}
                      <td className="px-6 py-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFinding(f);
                          }}
                          className="px-3 py-1.5 text-xs font-medium rounded-lg bg-slate-800 group-hover:bg-amber-600 text-slate-200 group-hover:text-white transition border border-slate-700"
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

      {/* 6. Detail Panel / Drawer */}
      {selectedFinding && (
        <div
          className="fixed inset-0 z-50 overflow-hidden bg-black/60 backdrop-blur-sm flex justify-end animate-fade-in"
          onClick={() => setSelectedFinding(null)}
        >
          <div
            className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 shadow-2xl p-6 overflow-y-auto space-y-6 flex flex-col justify-between"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-6">
              {/* Drawer Header */}
              <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2.5 py-1 text-xs font-bold rounded-full border ${getSeverityBadge(selectedFinding.severity).bg}`}>
                      {selectedFinding.severity} Severity
                    </span>
                    <span className="font-mono text-xs text-amber-300 bg-amber-950/60 px-2 py-0.5 rounded border border-amber-500/30">
                      Score: {selectedFinding.score.toFixed(1)} / 100
                    </span>
                  </div>
                  <h2 className="text-xl font-mono font-bold text-white">
                    {selectedFinding.column_name}
                  </h2>
                  <p className="text-xs text-slate-400 mt-1">
                    Detection Method: <span className="font-mono text-slate-300">{selectedFinding.detection_method}</span>
                  </p>
                </div>
                <button
                  onClick={() => setSelectedFinding(null)}
                  className="p-2 text-slate-400 hover:text-white rounded-lg bg-slate-800/60 hover:bg-slate-800 transition"
                >
                  ✕
                </button>
              </div>

              {/* 1. Overview */}
              <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                <span className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                  Finding Summary
                </span>
                <p className="text-sm text-slate-200 leading-relaxed font-medium">
                  {selectedFinding.explanation?.summary || 'No summary available.'}
                </p>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-400 pt-1">
                  <span>Anomalies: {selectedFinding.anomaly_count} rows</span>
                  <span>•</span>
                  <span>Anomaly Rate: {selectedFinding.anomaly_rate}%</span>
                </div>
              </div>

              {/* 2. Detection Evidence / Outlier Drivers */}
              <div className="space-y-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-amber-400">
                  Identified Outlier Drivers
                </span>
                <div className="space-y-2">
                  {selectedFinding.explanation?.drivers?.length > 0 ? (
                    selectedFinding.explanation.drivers.map((d, i) => (
                      <div key={i} className="flex items-start gap-2.5 p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs text-amber-200">
                        <span className="text-amber-400 font-bold">•</span>
                        <span className="leading-relaxed">{d}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-xs text-slate-500 italic">No specific driver conditions flagged.</p>
                  )}
                </div>
              </div>

              {/* 3. Detector Results Grid */}
              <div className="space-y-3">
                <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">
                  Detector Results & Evidence Breakdown
                </span>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-xs">
                  {/* IQR Card */}
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-200">IQR Detector</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        selectedFinding.evidence?.iqr?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {selectedFinding.evidence?.iqr?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.iqr?.executed ? (
                      <div className="text-[11px] text-slate-400 space-y-0.5 font-mono">
                        <div>Bounds: [{selectedFinding.evidence.iqr.lower_bound}, {selectedFinding.evidence.iqr.upper_bound}]</div>
                        <div>Q1: {selectedFinding.evidence.iqr.q1} | Q3: {selectedFinding.evidence.iqr.q3}</div>
                        <div>Outliers: {selectedFinding.evidence.iqr.anomaly_count} ({selectedFinding.evidence.iqr.anomaly_rate}%)</div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">{selectedFinding.evidence?.iqr?.reason || 'Not executed'}</div>
                    )}
                  </div>

                  {/* Z-Score Card */}
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-200">Z-Score (|z|≥3)</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        selectedFinding.evidence?.zscore?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {selectedFinding.evidence?.zscore?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.zscore?.executed ? (
                      <div className="text-[11px] text-slate-400 space-y-0.5 font-mono">
                        <div>Mean: {selectedFinding.evidence.zscore.mean} | Std: {selectedFinding.evidence.zscore.std}</div>
                        <div>Max |z|: {selectedFinding.evidence.zscore.max_abs_zscore}</div>
                        <div>Outliers: {selectedFinding.evidence.zscore.anomaly_count} ({selectedFinding.evidence.zscore.anomaly_rate}%)</div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">{selectedFinding.evidence?.zscore?.reason || 'Not executed'}</div>
                    )}
                  </div>

                  {/* Isolation Forest Card */}
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-200">Isolation Forest (ML)</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        selectedFinding.evidence?.isolation_forest?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {selectedFinding.evidence?.isolation_forest?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.isolation_forest?.executed ? (
                      <div className="text-[11px] text-slate-400 space-y-0.5 font-mono">
                        <div>Strategy: {selectedFinding.evidence.isolation_forest.sampling_strategy}</div>
                        <div>Outliers: {selectedFinding.evidence.isolation_forest.anomaly_count} ({selectedFinding.evidence.isolation_forest.anomaly_rate}%)</div>
                        <div>Min Score: {selectedFinding.evidence.isolation_forest.min_decision_score}</div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">{selectedFinding.evidence?.isolation_forest?.reason || 'Not executed'}</div>
                    )}
                  </div>

                  {/* Categorical Frequency Card */}
                  <div className="p-3.5 rounded-xl bg-slate-950/60 border border-slate-800 space-y-1.5">
                    <div className="flex items-center justify-between">
                      <span className="font-bold text-slate-200">Rare Categories (&lt;1%)</span>
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-semibold ${
                        selectedFinding.evidence?.categorical_frequency?.detected ? 'bg-amber-500/20 text-amber-300' : 'bg-slate-800 text-slate-400'
                      }`}>
                        {selectedFinding.evidence?.categorical_frequency?.detected ? 'DETECTED' : 'CLEAN'}
                      </span>
                    </div>
                    {selectedFinding.evidence?.categorical_frequency?.executed ? (
                      <div className="text-[11px] text-slate-400 space-y-0.5 font-mono">
                        <div>Unique: {selectedFinding.evidence.categorical_frequency.unique_categories_count}</div>
                        <div>Rare Count: {selectedFinding.evidence.categorical_frequency.rare_category_count}</div>
                        <div>Rare Rate: {selectedFinding.evidence.categorical_frequency.rare_category_rate}%</div>
                      </div>
                    ) : (
                      <div className="text-[11px] text-slate-500 italic">{selectedFinding.evidence?.categorical_frequency?.reason || 'Not executed'}</div>
                    )}
                  </div>
                </div>
              </div>

              {/* 4. Interpretation & Privacy Protection Callouts */}
              <div className="p-4 rounded-xl bg-indigo-950/40 border border-indigo-500/30 space-y-2">
                <span className="text-xs font-semibold uppercase text-indigo-300 flex items-center gap-1.5">
                  <span>🛡️</span> Statistical Interpretation & Privacy Guard
                </span>
                <ul className="text-xs text-slate-300 list-disc list-inside space-y-1 leading-relaxed">
                  <li>
                    <strong className="text-white">Interpretation Notice:</strong> An anomaly indicates a statistically unusual pattern; it does not automatically mean the data is incorrect.
                  </li>
                  <li>
                    <strong className="text-white">Privacy Guarantee:</strong> Zero raw PII values are stored in anomaly records. Only safe statistical distribution metrics are preserved.
                  </li>
                </ul>
              </div>

              {/* Raw Evidence JSON Snippet */}
              {selectedFinding.evidence && (
                <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                      Detector Evidence Payload
                    </span>
                    <button
                      onClick={() => copyToClipboard(JSON.stringify(selectedFinding.evidence, null, 2), 'evidence')}
                      className="text-xs text-cyan-400 hover:text-cyan-300 font-medium"
                    >
                      {copiedKey === 'evidence' ? '✓ Copied' : 'Copy JSON'}
                    </button>
                  </div>
                  <pre className="text-xs font-mono text-slate-400 bg-slate-900 p-3 rounded-lg overflow-x-auto max-h-40 border border-slate-800">
                    {JSON.stringify(selectedFinding.evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedFinding(null)}
                className="px-5 py-2 bg-slate-800 hover:bg-slate-700 text-white rounded-xl font-medium text-xs transition"
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
