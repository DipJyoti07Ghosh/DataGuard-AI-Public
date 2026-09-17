/**
 * DataGuard AI — Dashboard Page
 *
 * Main landing page showing system status and overview.
 * In Phase 1, this displays backend connectivity status.
 * Will be expanded with profiling/quality summaries in later phases.
 */

import { useState, useEffect } from 'react';
import { checkHealth } from '../api/client';

export default function Dashboard() {
  const [health, setHealth] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    document.getElementById('page-title').textContent = 'Dashboard';
    fetchHealth();
  }, []);

  async function fetchHealth() {
    setLoading(true);
    setError(null);
    try {
      const data = await checkHealth();
      setHealth(data);

      // Update sidebar status indicator
      const statusDot = document.querySelector('.status-dot');
      const statusText = document.querySelector('.status-text');
      if (statusDot && statusText) {
        statusDot.className = 'status-dot status-dot--healthy';
        statusText.textContent = 'Backend Connected';
      }
    } catch (err) {
      setError(err.message);
      const statusDot = document.querySelector('.status-dot');
      const statusText = document.querySelector('.status-text');
      if (statusDot && statusText) {
        statusDot.className = 'status-dot status-dot--error';
        statusText.textContent = 'Backend Offline';
      }
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="dashboard">
      {/* System Status Cards */}
      <section className="status-section">
        <h2 className="section-title">System Status</h2>
        <div className="status-grid">

          {/* API Status */}
          <div className="status-card" id="api-status-card">
            <div className="status-card-header">
              <span className="status-card-icon">⚡</span>
              <h3>API Server</h3>
            </div>
            <div className="status-card-body">
              {loading && <span className="status-loading">Checking...</span>}
              {error && (
                <div className="status-error">
                  <span className="status-badge status-badge--error">Offline</span>
                  <p className="status-message">{error}</p>
                </div>
              )}
              {health && (
                <div className="status-healthy">
                  <span className="status-badge status-badge--success">
                    {health.status}
                  </span>
                  <p className="status-detail">
                    {health.application} v0.1.0
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Database Status */}
          <div className="status-card" id="db-status-card">
            <div className="status-card-header">
              <span className="status-card-icon">🗄️</span>
              <h3>PostgreSQL</h3>
            </div>
            <div className="status-card-body">
              {loading && <span className="status-loading">Checking...</span>}
              {health && (
                <div>
                  <span className={`status-badge status-badge--${
                    health.components.database === 'connected' ? 'success' : 'warning'
                  }`}>
                    {health.components.database}
                  </span>
                  {health.components.database !== 'connected' && (
                    <p className="status-hint">Will be configured in Phase 3</p>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Ollama Status */}
          <div className="status-card" id="ollama-status-card">
            <div className="status-card-header">
              <span className="status-card-icon">🧠</span>
              <h3>Ollama LLM</h3>
            </div>
            <div className="status-card-body">
              {loading && <span className="status-loading">Checking...</span>}
              {health && (
                <div>
                  <span className={`status-badge status-badge--${
                    health.components.ollama === 'connected' ? 'success' : 'warning'
                  }`}>
                    {health.components.ollama}
                  </span>
                  {health.components.ollama !== 'connected' && (
                    <p className="status-hint">Will be configured in Phase 12</p>
                  )}
                </div>
              )}
            </div>
          </div>

        </div>
      </section>

      {/* Quick Actions */}
      <section className="actions-section">
        <h2 className="section-title">Quick Actions</h2>
        <div className="actions-grid">
          <a href="/upload" className="action-card" id="action-upload">
            <span className="action-icon">📁</span>
            <span className="action-label">Upload Dataset</span>
            <span className="action-desc">CSV or Excel files</span>
          </a>
          <a href="/datasets" className="action-card" id="action-datasets">
            <span className="action-icon">🗃️</span>
            <span className="action-label">View Datasets</span>
            <span className="action-desc">Browse uploaded data</span>
          </a>
          <a href="/assistant" className="action-card" id="action-assistant">
            <span className="action-icon">🤖</span>
            <span className="action-label">AI Assistant</span>
            <span className="action-desc">Ask about your data</span>
          </a>
        </div>
      </section>

      {/* Health Details */}
      {health && (
        <section className="details-section">
          <h2 className="section-title">Health Details</h2>
          <div className="details-card">
            <pre className="health-json">
              {JSON.stringify(health, null, 2)}
            </pre>
          </div>
        </section>
      )}

      {/* Refresh */}
      <button
        className="btn btn--primary refresh-btn"
        onClick={fetchHealth}
        disabled={loading}
        id="refresh-health-btn"
      >
        {loading ? 'Checking...' : '🔄 Refresh Status'}
      </button>
    </div>
  );
}
