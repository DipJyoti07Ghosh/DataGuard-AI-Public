/**
 * DataGuard AI — Phase 9 Dataset Health & Issue Prioritization Dashboard
 *
 * Provides:
 * 1. Holistic 0-100 Dataset Health Score & Grade
 * 2. 4-Way Health Breakdown: Quality (60%), Risk (15%), Anomaly (15%), Privacy (10%)
 * 3. 4 Top-level KPI Cards (Critical, High, Total Issues, Columns Affected)
 * 4. Column Health Cross-Signal Matrix
 * 5. Prioritized Data Quality Issues Table with Multi-Filter Chips
 * 6. Interactive Slide-Out Drawer disclosing:
 *    - Score component breakdown (Severity, Affected, Sensitivity, Confidence, Cross-Signal)
 *    - Structured upstream evidence & context (Zero raw PII)
 *    - Safe, non-destructive actionable remediation guidance
 */

import { useState, useEffect } from 'react';
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

  // Filters
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [searchColumn, setSearchColumn] = useState('');

  // Slide-out Drawer State
  const [selectedIssue, setSelectedIssue] = useState(null);

  // Load initial data
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

  // Filtered issues
  const filteredIssues = issues.filter((iss) => {
    if (severityFilter !== 'ALL' && iss.severity.toUpperCase() !== severityFilter) {
      return false;
    }
    if (sourceFilter !== 'ALL' && iss.source.toUpperCase() !== sourceFilter) {
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
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/40 shadow-emerald-900/20';
      case 'GOOD':
        return 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40 shadow-cyan-900/20';
      case 'NEEDS ATTENTION':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/40 shadow-amber-900/20';
      case 'POOR':
        return 'bg-orange-500/20 text-orange-300 border-orange-500/40 shadow-orange-900/20';
      case 'CRITICAL':
      default:
        return 'bg-rose-500/20 text-rose-300 border-rose-500/40 shadow-rose-900/20';
    }
  };

  const getSeverityBadge = (sev) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      case 'HIGH':
        return 'bg-orange-500/20 text-orange-300 border-orange-500/30';
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      case 'LOW':
      default:
        return 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30';
    }
  };

  const getSourceBadge = (src) => {
    switch (src?.toUpperCase()) {
      case 'QUALITY':
        return 'bg-purple-500/20 text-purple-300 border-purple-500/30';
      case 'PII':
        return 'bg-blue-500/20 text-blue-300 border-blue-500/30';
      case 'RISK':
        return 'bg-rose-500/20 text-rose-300 border-rose-500/30';
      case 'ANOMALY':
        return 'bg-amber-500/20 text-amber-300 border-amber-500/30';
      default:
        return 'bg-slate-500/20 text-slate-300 border-slate-500/30';
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-12 h-12 border-4 border-cyan-500/20 border-t-cyan-500 rounded-full animate-spin" />
        <p className="text-slate-400 font-medium animate-pulse">
          Synthesizing multi-phase signals & prioritizing dataset issues...
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-8 pb-16">
      {/* 1. Header & Navigation */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800/80 backdrop-blur-xl shadow-2xl">
        <div>
          <div className="flex items-center gap-3">
            <span className="text-3xl">🎯</span>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
              Quality Scoring & Issue Prioritization
            </h1>
          </div>
          <p className="text-slate-400 text-sm mt-1">
            Dataset: <span className="text-white font-medium">{dataset?.name}</span> • Version:{' '}
            <span className="text-cyan-400 font-mono">V{version?.version_number}</span> •{' '}
            {version?.row_count} rows × {version?.column_count} cols
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={handleReanalyze}
            disabled={analyzing}
            className="flex items-center gap-2 px-4 py-2.5 rounded-xl bg-gradient-to-r from-cyan-500 to-blue-600 hover:from-cyan-400 hover:to-blue-500 text-white font-medium text-sm shadow-lg shadow-cyan-500/20 transition-all duration-200 disabled:opacity-50"
          >
            {analyzing ? (
              <>
                <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                <span>Re-analyzing...</span>
              </>
            ) : (
              <>
                <span>⚡</span>
                <span>Recompute Health & Priorities</span>
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
        <Link
          to={`/datasets/${datasetId}/versions/${versionId}/anomalies`}
          className="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800/50 transition-colors"
        >
          ⚠️ Anomalies
        </Link>
        <span className="px-4 py-2 rounded-lg text-sm font-semibold text-cyan-300 bg-cyan-950/60 border border-cyan-500/30">
          🎯 Prioritization / Health
        </span>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-950/40 border border-rose-500/40 text-rose-300 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button onClick={loadData} className="underline text-xs hover:text-rose-200">
            Retry
          </button>
        </div>
      )}

      {/* 2. Top Section: Dataset Health Scorecard & 4-Way Breakdown */}
      {summary && (
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Health Gauge */}
          <div className="lg:col-span-4 bg-slate-900/60 p-6 rounded-2xl border border-slate-800/80 backdrop-blur-xl flex flex-col items-center justify-center text-center shadow-xl">
            <span className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-2">
              Holistic Dataset Health Score
            </span>
            <div className="relative flex items-center justify-center my-3">
              <div className="w-36 h-36 rounded-full border-8 border-slate-800 flex items-center justify-center relative">
                <div
                  className="absolute inset-0 rounded-full border-8 border-cyan-400 transition-all duration-1000"
                  style={{
                    clipPath: `polygon(0 0, 100% 0, 100% ${summary.health_score}%, 0 ${summary.health_score}%)`,
                  }}
                />
                <div className="flex flex-col items-center">
                  <span className="text-4xl font-extrabold text-white tracking-tight">
                    {summary.health_score.toFixed(1)}
                  </span>
                  <span className="text-xs text-slate-400 font-medium">/ 100</span>
                </div>
              </div>
            </div>
            <div
              className={`px-4 py-1.5 rounded-full border text-xs font-bold tracking-wide uppercase shadow-lg mt-2 ${getGradeBadge(
                summary.health_grade
              )}`}
            >
              Grade: {summary.health_grade}
            </div>
            <p className="text-xs text-slate-500 mt-3 max-w-xs">
              Deterministic weighted synthesis: Quality (60%), Risk (15%), Anomaly (15%), Privacy (10%).
            </p>
          </div>

          {/* 4-Way Health Breakdown Components */}
          <div className="lg:col-span-8 bg-slate-900/60 p-6 rounded-2xl border border-slate-800/80 backdrop-blur-xl shadow-xl flex flex-col justify-between">
            <div>
              <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider mb-4 flex items-center gap-2">
                <span>📊</span> 4-Way Subsystem Health Breakdown
              </h3>
              <div className="space-y-4">
                {/* Quality Health */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <span>✅</span> Quality Health (Phase 5 — 60% weight)
                    </span>
                    <span className="font-mono text-cyan-400">{summary.quality_health.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-purple-500 to-cyan-400 rounded-full transition-all duration-700"
                      style={{ width: `${summary.quality_health}%` }}
                    />
                  </div>
                </div>

                {/* Risk Health */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <span>🧠</span> Risk Health (Phase 7 — 15% weight)
                    </span>
                    <span className="font-mono text-cyan-400">{summary.risk_health.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-rose-500 to-amber-400 rounded-full transition-all duration-700"
                      style={{ width: `${summary.risk_health}%` }}
                    />
                  </div>
                </div>

                {/* Anomaly Health */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <span>⚠️</span> Anomaly Health (Phase 8 — 15% weight)
                    </span>
                    <span className="font-mono text-cyan-400">{summary.anomaly_health.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-amber-500 to-emerald-400 rounded-full transition-all duration-700"
                      style={{ width: `${summary.anomaly_health}%` }}
                    />
                  </div>
                </div>

                {/* Privacy Health */}
                <div>
                  <div className="flex justify-between text-xs font-medium mb-1">
                    <span className="text-slate-300 flex items-center gap-1.5">
                      <span>🔒</span> Privacy Health (Phase 6 — 10% weight)
                    </span>
                    <span className="font-mono text-cyan-400">{summary.privacy_health.toFixed(1)} / 100</span>
                  </div>
                  <div className="w-full h-2.5 rounded-full bg-slate-800 overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-indigo-400 rounded-full transition-all duration-700"
                      style={{ width: `${summary.privacy_health}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="pt-4 border-t border-slate-800/80 text-xs text-slate-400 flex flex-wrap items-center justify-between gap-2">
              <span>Each subsystem remains separately identifiable without conflating exposure with data corruption.</span>
              <span className="text-slate-500">
                Calculated at: {new Date(summary.calculated_at).toLocaleTimeString()}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* 3. KPI Cards */}
      {summary && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 backdrop-blur-xl shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-rose-400">Critical Priority</span>
              <span className="text-xl">🚨</span>
            </div>
            <div className="text-3xl font-extrabold text-white mt-2">{summary.critical_issues}</div>
            <span className="text-xs text-slate-500">Requires immediate attention</span>
          </div>

          <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 backdrop-blur-xl shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-orange-400">High Priority</span>
              <span className="text-xl">🔥</span>
            </div>
            <div className="text-3xl font-extrabold text-white mt-2">{summary.high_issues}</div>
            <span className="text-xs text-slate-500">High impact on dataset</span>
          </div>

          <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 backdrop-blur-xl shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">Total Issues</span>
              <span className="text-xl">📋</span>
            </div>
            <div className="text-3xl font-extrabold text-white mt-2">{summary.total_issues}</div>
            <span className="text-xs text-slate-500">Deduplicated logical findings</span>
          </div>

          <div className="bg-slate-900/60 p-5 rounded-xl border border-slate-800 backdrop-blur-xl shadow-lg">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-cyan-400">Columns Affected</span>
              <span className="text-xl">📐</span>
            </div>
            <div className="text-3xl font-extrabold text-white mt-2">
              {summary.columns_affected_count}{' '}
              <span className="text-xs text-slate-500 font-normal">/ {summary.total_columns_evaluated}</span>
            </div>
            <span className="text-xs text-slate-500">Columns with quality or risk signals</span>
          </div>
        </div>
      )}

      {/* 4. Column Health Cross-Signal Matrix */}
      {summary?.column_health_matrix?.length > 0 && (
        <div className="bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-xl shadow-xl space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-bold text-white flex items-center gap-2">
              <span>🏛️</span> Columns Requiring Attention (Cross-Signal Matrix)
            </h3>
            <span className="text-xs text-slate-500">Sorted by highest priority & cross-signal agreement</span>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs text-slate-300 border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
                  <th className="py-3 px-4">Column Name</th>
                  <th className="py-3 px-3">Type</th>
                  <th className="py-3 px-3">Quality</th>
                  <th className="py-3 px-3">ML Domain / Risk</th>
                  <th className="py-3 px-3">Anomalies</th>
                  <th className="py-3 px-3">PII Exposure</th>
                  <th className="py-3 px-3">Cross-Signals</th>
                  <th className="py-3 px-4 text-right">Max Priority</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {summary.column_health_matrix.map((col) => (
                  <tr key={col.column_name} className="hover:bg-slate-800/40 transition-colors">
                    <td className="py-3 px-4 font-mono font-medium text-white">{col.column_name}</td>
                    <td className="py-3 px-3 font-mono text-slate-400">{col.data_type}</td>
                    <td className="py-3 px-3">
                      {col.quality_status === 'VIOLATION' ? (
                        <span className="px-2 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30 font-medium">
                          {col.quality_issues_count} Failed Rule(s)
                        </span>
                      ) : (
                        <span className="text-slate-500">Clean</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      <span className="text-slate-300 font-medium">{col.domain}</span>{' '}
                      <span className="text-xs font-mono text-slate-500">({col.risk_score.toFixed(0)})</span>
                    </td>
                    <td className="py-3 px-3">
                      {col.anomaly_detected ? (
                        <span className={`px-2 py-0.5 rounded font-medium border ${getSeverityBadge(col.anomaly_severity)}`}>
                          {col.anomaly_severity}
                        </span>
                      ) : (
                        <span className="text-slate-500">None</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {col.pii_detected ? (
                        <span className="px-2 py-0.5 rounded bg-blue-500/20 text-blue-300 border border-blue-500/30 font-medium">
                          {col.pii_entities.join(', ')}
                        </span>
                      ) : (
                        <span className="text-slate-500">None</span>
                      )}
                    </td>
                    <td className="py-3 px-3">
                      {col.cross_signal_count > 1 ? (
                        <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-300 font-bold border border-indigo-500/30">
                          {col.cross_signal_count} Subsystems
                        </span>
                      ) : col.cross_signal_count === 1 ? (
                        <span className="text-slate-400 font-mono">1 Subsystem</span>
                      ) : (
                        <span className="text-slate-600 font-mono">0</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold text-cyan-400">
                      {col.highest_priority > 0 ? col.highest_priority.toFixed(1) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* 5. Prioritized Data Quality Issues Table */}
      <div className="bg-slate-900/60 p-6 rounded-2xl border border-slate-800 backdrop-blur-xl shadow-xl space-y-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <h2 className="text-lg font-bold text-white flex items-center gap-2">
              <span>📑</span> Deduplicated & Prioritized Issue Backlog
            </h2>
            <p className="text-slate-400 text-xs mt-0.5">
              Ranked by deterministic multi-factor priority score (Severity 30%, Data Impact 25%, Sensitivity 20%, Confidence 15%, Evidence 10%)
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Search Input */}
            <input
              type="text"
              placeholder="Filter by column..."
              value={searchColumn}
              onChange={(e) => setSearchColumn(e.target.value)}
              className="px-3 py-1.5 rounded-lg bg-slate-800 border border-slate-700 text-xs text-white placeholder-slate-500 focus:outline-none focus:border-cyan-500"
            />

            {/* Severity Filter */}
            <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700">
              {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map((s) => (
                <button
                  key={s}
                  onClick={() => setSeverityFilter(s)}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    severityFilter === s
                      ? 'bg-cyan-500 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {s}
                </button>
              ))}
            </div>

            {/* Source Filter */}
            <div className="flex items-center gap-1 bg-slate-800/80 p-1 rounded-lg border border-slate-700">
              {['ALL', 'QUALITY', 'PII', 'RISK', 'ANOMALY'].map((src) => (
                <button
                  key={src}
                  onClick={() => setSourceFilter(src)}
                  className={`px-2.5 py-1 rounded text-xs font-semibold transition-all ${
                    sourceFilter === src
                      ? 'bg-cyan-500 text-white shadow'
                      : 'text-slate-400 hover:text-white'
                  }`}
                >
                  {src}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm text-slate-300 border-collapse">
            <thead>
              <tr className="border-b border-slate-800 text-slate-400 font-semibold uppercase text-xs tracking-wider">
                <th className="py-3 px-4">Priority</th>
                <th className="py-3 px-3">Severity</th>
                <th className="py-3 px-4">Column / Scope</th>
                <th className="py-3 px-4">Issue Title</th>
                <th className="py-3 px-3">Source</th>
                <th className="py-3 px-3">Affected %</th>
                <th className="py-3 px-4">Remediation Action</th>
                <th className="py-3 px-4 text-right">Inspect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {filteredIssues.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-slate-500 text-sm">
                    No issues match the selected filter criteria.
                  </td>
                </tr>
              ) : (
                filteredIssues.map((iss) => (
                  <tr
                    key={iss.id}
                    onClick={() => setSelectedIssue(iss)}
                    className="hover:bg-slate-800/40 cursor-pointer transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-mono font-extrabold text-cyan-400">
                      {iss.priority_score.toFixed(1)}
                    </td>
                    <td className="py-3.5 px-3">
                      <span className={`px-2.5 py-1 rounded-md text-xs font-bold border ${getSeverityBadge(iss.severity)}`}>
                        {iss.severity}
                      </span>
                    </td>
                    <td className="py-3.5 px-4 font-mono text-white font-medium">
                      {iss.column_name || <span className="text-slate-500 italic">Dataset-wide</span>}
                    </td>
                    <td className="py-3.5 px-4 font-medium text-slate-200 group-hover:text-cyan-300 transition-colors">
                      {iss.title}
                    </td>
                    <td className="py-3.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-xs font-semibold border ${getSourceBadge(iss.source)}`}>
                        {iss.source}
                      </span>
                    </td>
                    <td className="py-3.5 px-3 font-mono text-slate-400">
                      {iss.affected_percentage.toFixed(1)}%
                    </td>
                    <td className="py-3.5 px-4 text-xs text-slate-400 max-w-xs truncate">
                      {iss.recommendation?.summary || 'Investigate issue details'}
                    </td>
                    <td className="py-3.5 px-4 text-right">
                      <button className="px-3 py-1 rounded-lg bg-slate-800 group-hover:bg-cyan-600 text-xs font-medium text-slate-300 group-hover:text-white transition-colors">
                        Inspect →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* 6. Slide-Out Issue Detail Drawer */}
      {selectedIssue && (
        <div className="fixed inset-0 z-50 flex justify-end bg-black/60 backdrop-blur-sm animate-fade-in">
          <div
            className="w-full max-w-2xl bg-slate-900 border-l border-slate-800 h-full p-6 overflow-y-auto space-y-6 shadow-2xl flex flex-col justify-between"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="space-y-6">
              {/* Drawer Header */}
              <div className="flex items-start justify-between border-b border-slate-800 pb-4">
                <div>
                  <div className="flex items-center gap-2 mb-2">
                    <span className={`px-2.5 py-1 rounded-md text-xs font-bold border ${getSeverityBadge(selectedIssue.severity)}`}>
                      {selectedIssue.severity} Severity
                    </span>
                    <span className={`px-2.5 py-1 rounded-md text-xs font-semibold border ${getSourceBadge(selectedIssue.source)}`}>
                      {selectedIssue.source} Signal
                    </span>
                    <span className="font-mono text-xs text-cyan-400 bg-cyan-950/60 px-2 py-0.5 rounded border border-cyan-500/30">
                      Priority: {selectedIssue.priority_score.toFixed(1)} / 100
                    </span>
                  </div>
                  <h2 className="text-xl font-bold text-white">{selectedIssue.title}</h2>
                  <p className="text-xs text-slate-400 font-mono mt-1">
                    Target: {selectedIssue.column_name || 'Dataset-Wide'} • Type: {selectedIssue.issue_type}
                  </p>
                </div>
                <button
                  onClick={() => setSelectedIssue(null)}
                  className="p-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-white transition-colors"
                >
                  ✕
                </button>
              </div>

              {/* Description */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-2">
                <span className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                  Issue Summary & Impact
                </span>
                <p className="text-sm text-slate-200 leading-relaxed">{selectedIssue.description}</p>
                <div className="flex items-center gap-4 text-xs font-mono text-slate-400 pt-1">
                  <span>Affected Rows: {selectedIssue.affected_rows}</span>
                  <span>•</span>
                  <span>Affected Data: {selectedIssue.affected_percentage.toFixed(2)}%</span>
                </div>
              </div>

              {/* Priority Score Component Breakdown */}
              <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-3">
                <span className="text-xs font-semibold uppercase text-cyan-400 tracking-wider">
                  Deterministic Priority Breakdown (0–100)
                </span>
                <div className="grid grid-cols-2 gap-3 text-xs">
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400 block">Severity (30% weight)</span>
                    <span className="font-mono text-white font-bold">{selectedIssue.severity}</span>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400 block">Affected Data (25% weight)</span>
                    <span className="font-mono text-white font-bold">{selectedIssue.affected_percentage.toFixed(1)}%</span>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400 block">Data Sensitivity (20% weight)</span>
                    <span className="font-mono text-white font-bold">{selectedIssue.sensitivity_score.toFixed(1)} / 100</span>
                  </div>
                  <div className="bg-slate-900 p-2.5 rounded-lg border border-slate-800">
                    <span className="text-slate-400 block">Confidence Heuristic (15% weight)</span>
                    <span className="font-mono text-white font-bold">{selectedIssue.confidence_score.toFixed(1)} / 100</span>
                  </div>
                </div>
                <div className="text-xs text-slate-400 flex items-center justify-between pt-1">
                  <span>Cross-Signal Evidence Score:</span>
                  <span className="font-mono text-cyan-300 font-bold">{selectedIssue.evidence_score.toFixed(1)} / 100</span>
                </div>
              </div>

              {/* Actionable Remediation Guidance */}
              {selectedIssue.recommendation && (
                <div className="bg-gradient-to-br from-slate-950 to-cyan-950/30 p-5 rounded-xl border border-cyan-500/30 space-y-4">
                  <div className="flex items-center gap-2">
                    <span className="text-lg">🛠️</span>
                    <h3 className="text-sm font-bold text-white uppercase tracking-wide">
                      Recommended Remediation Plan
                    </h3>
                  </div>

                  <p className="text-xs text-slate-300 font-medium">
                    {selectedIssue.recommendation.summary}
                  </p>

                  {/* Investigation Steps */}
                  {selectedIssue.recommendation.investigation_steps?.length > 0 && (
                    <div>
                      <span className="text-xs font-semibold text-cyan-300 uppercase tracking-wider block mb-2">
                        Diagnostic & Investigation Steps:
                      </span>
                      <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
                        {selectedIssue.recommendation.investigation_steps.map((step, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {step}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Preventive Measures */}
                  {selectedIssue.recommendation.preventive_measures?.length > 0 && (
                    <div>
                      <span className="text-xs font-semibold text-cyan-300 uppercase tracking-wider block mb-2">
                        Preventive & Safeguard Measures:
                      </span>
                      <ul className="space-y-1.5 text-xs text-slate-300 list-disc list-inside">
                        {selectedIssue.recommendation.preventive_measures.map((prev, idx) => (
                          <li key={idx} className="leading-relaxed">
                            {prev}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Caution Warning Box */}
                  {selectedIssue.recommendation.caution_note && (
                    <div className="p-3 rounded-lg bg-amber-950/40 border border-amber-500/40 text-xs text-amber-200 flex items-start gap-2">
                      <span className="text-base">⚠️</span>
                      <span className="leading-relaxed">{selectedIssue.recommendation.caution_note}</span>
                    </div>
                  )}
                </div>
              )}

              {/* Diagnostic Evidence Details */}
              {selectedIssue.evidence && Object.keys(selectedIssue.evidence).length > 0 && (
                <div className="bg-slate-950/60 p-4 rounded-xl border border-slate-800 space-y-2">
                  <span className="text-xs font-semibold uppercase text-slate-400 tracking-wider">
                    Underlying Diagnostic Evidence
                  </span>
                  <pre className="text-xs font-mono text-slate-400 bg-slate-900 p-3 rounded-lg overflow-x-auto max-h-48 border border-slate-800">
                    {JSON.stringify(selectedIssue.evidence, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Drawer Footer */}
            <div className="pt-4 border-t border-slate-800 flex justify-end">
              <button
                onClick={() => setSelectedIssue(null)}
                className="px-5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-xs font-medium text-white transition-colors"
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
