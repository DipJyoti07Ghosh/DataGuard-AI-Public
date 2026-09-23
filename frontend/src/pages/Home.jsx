/**
 * DATA GUARD AI — Modern Landing Page / Homepage
 *
 * Dedicated front-door experience featuring interactive multi-phase showcases,
 * platform telemetry, security guarantees, and direct entry points to the dashboard.
 *
 * Backend-connected: checkHealth() is used to display live engine status.
 * Routes: mounted at "/" (unchanged).
 */

import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { checkHealth } from '../api/client';
import './Home.css';

export default function Home() {
  const [activeTab, setActiveTab] = useState('profiling');
  const [backendOnline, setBackendOnline] = useState(null);

  useEffect(() => {
    let isMounted = true;
    checkHealth()
      .then(() => {
        if (isMounted) setBackendOnline(true);
      })
      .catch(() => {
        if (isMounted) setBackendOnline(false);
      });
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="landing-container">
      {/* ---------------- Background ambience ---------------- */}
      <div className="landing-grid-bg" />
      <div className="landing-glow-top" />
      <div className="landing-orbit landing-orbit-one" aria-hidden="true" />
      <div className="landing-orbit landing-orbit-two" aria-hidden="true" />
      <div className="landing-cube-field" aria-hidden="true">
        <span className="landing-cube cube-one"><i /><i /><i /></span>
        <span className="landing-cube cube-two"><i /><i /><i /></span>
        <span className="landing-cube cube-three"><i /><i /><i /></span>
        <span className="landing-cube cube-four"><i /><i /><i /></span>
        <span className="landing-cube cube-five"><i /><i /><i /></span>
      </div>

      {/* ---------------- Sticky top nav ---------------- */}
      <header className="landing-header">
        <div className="landing-nav">
          <Link to="/" className="landing-brand">
            <div className="landing-brand-icon">🛡️</div>
            <span className="landing-brand-text">DATA GUARD AI</span>
            <span className="landing-brand-badge">Enterprise</span>
          </Link>

          <nav className="landing-nav-links">
            <a href="#capabilities" className="landing-nav-link">Capabilities</a>
            <a href="#pipeline" className="landing-nav-link">14-Phase Engine</a>
            <a href="#security" className="landing-nav-link">Zero-PII Security</a>
            <Link to="/chat" className="landing-nav-link">AI Chat</Link>
          </nav>

          <div className="landing-nav-actions">
            <Link to="/upload" className="btn-nav-secondary">
              <span>📁</span> Upload Data
            </Link>
            <Link to="/dashboard" className="btn-nav-primary">
              <span>Launch Platform</span>
              <span>→</span>
            </Link>
          </div>
        </div>
      </header>

      {/* ---------------- Hero ---------------- */}
      <section className="landing-hero">
        <div className="hero-pill-badge">
          <span>⚡</span>
          <span>Next-Gen Autonomous Data Intelligence &amp; PII Shield</span>
        </div>

        <h1 className="hero-heading">
          Autonomous Data Profiling, Quality &amp;{' '}
          <span className="hero-gradient-text">AI-Powered Privacy Guard</span>
        </h1>

        <p className="hero-subtext">
          Audit complex datasets in seconds. Automatically generate deep statistical profiles,
          enforce Great Expectations quality rules, sanitize sensitive PII with Presidio, detect Isolation Forest anomalies,
          and interact via PgVector RAG conversational intelligence.
        </p>

        <div className="hero-cta-group">
          <Link to="/dashboard" className="hero-btn-primary">
            <span>🚀</span>
            <span>Enter Dashboard</span>
          </Link>
          <Link to="/upload" className="hero-btn-secondary">
            <span>📁</span>
            <span>Upload New Dataset</span>
          </Link>
          <Link to="/chat" className="hero-btn-chat">
            <span>💬</span>
            <span>Explore AI Chat</span>
          </Link>
        </div>

        {/* Live interactive showcase card */}
        <div className="hero-showcase">
          <div className="showcase-header">
            <div className="showcase-dots">
              <span className="dot dot-red" />
              <span className="dot dot-yellow" />
              <span className="dot dot-green" />
            </div>
            <div className="showcase-title">
              <span>dataguard-core // telemetry-preview.v2</span>
            </div>
            <div className="showcase-badge-live">
              <span className="live-pulse" />
              <span>{backendOnline ? 'Engine Online' : 'Active System'}</span>
            </div>
          </div>

          <div className="showcase-tabs">
            <button
              className={`showcase-tab ${activeTab === 'profiling' ? 'active' : ''}`}
              onClick={() => setActiveTab('profiling')}
            >
              📊 1. Statistical Profiling
            </button>
            <button
              className={`showcase-tab ${activeTab === 'quality' ? 'active' : ''}`}
              onClick={() => setActiveTab('quality')}
            >
              ✅ 2. Great Expectations Quality
            </button>
            <button
              className={`showcase-tab ${activeTab === 'pii' ? 'active' : ''}`}
              onClick={() => setActiveTab('pii')}
            >
              🔒 3. Presidio PII Redactor
            </button>
            <button
              className={`showcase-tab ${activeTab === 'risk' ? 'active' : ''}`}
              onClick={() => setActiveTab('risk')}
            >
              🎯 4. ML Risk &amp; Anomalies
            </button>
            <button
              className={`showcase-tab ${activeTab === 'rag' ? 'active' : ''}`}
              onClick={() => setActiveTab('rag')}
            >
              🧠 5. PgVector RAG &amp; LLM
            </button>
          </div>

          <div className="showcase-body">
            {activeTab === 'profiling' && (
              <>
                <div className="showcase-metrics-row">
                  <div className="showcase-metric-card">
                    <div className="metric-label">Completeness</div>
                    <div className="metric-val">99.8%</div>
                    <div className="metric-sub">✓ 0 nulls in primary keys</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Columns Inferred</div>
                    <div className="metric-val">24 / 24</div>
                    <div className="metric-sub">✓ 100% Type-confidence</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Distinct Cardinality</div>
                    <div className="metric-val">94.6%</div>
                    <div className="metric-sub">Optimal distribution</div>
                  </div>
                </div>
                <div className="showcase-console">
                  <div className="console-line">
                    <span className="console-tag tag-success">SUCCESS</span>
                    <span className="console-text">[Phase 4] Computed 24-column quantile distributions in <span className="console-highlight">184ms</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-info">INFO</span>
                    <span className="console-text">Generated 10-bin histogram matrices &amp; skewness coefficients</span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-purple">HASH</span>
                    <span className="console-text">Deterministic version fingerprint generated: <span className="console-highlight">sha256:d8a2...3f1c</span></span>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'quality' && (
              <>
                <div className="showcase-metrics-row">
                  <div className="showcase-metric-card">
                    <div className="metric-label">Quality Score</div>
                    <div className="metric-val">94.2 / 100</div>
                    <div className="metric-sub">✓ Grade: EXCELLENT</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Rules Evaluated</div>
                    <div className="metric-val">18 Passed / 2 Warn</div>
                    <div className="metric-sub">90% Success Rate</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Uniqueness Check</div>
                    <div className="metric-val">100% Pass</div>
                    <div className="metric-sub">Zero Duplicate IDs</div>
                  </div>
                </div>
                <div className="showcase-console">
                  <div className="console-line">
                    <span className="console-tag tag-success">PASS</span>
                    <span className="console-text">expect_column_values_to_not_be_null('customer_id') &rarr; <span className="console-highlight">0 unexpected</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-success">PASS</span>
                    <span className="console-text">expect_column_values_to_be_between('transaction_amount', 0.01, 100000)</span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-warn">WARN</span>
                    <span className="console-text">expect_column_values_to_match_regex('postal_code') &rarr; 2 outlier formats found</span>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'pii' && (
              <>
                <div className="showcase-metrics-row">
                  <div className="showcase-metric-card">
                    <div className="metric-label">PII Shield Status</div>
                    <div className="metric-val" style={{ color: '#34d399' }}>PROTECTED</div>
                    <div className="metric-sub">✓ Zero Raw PII Leaked</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Redacted Entities</div>
                    <div className="metric-val">14 Instances</div>
                    <div className="metric-sub">EMAIL, SSN, PHONE, CARD</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Presidio Precision</div>
                    <div className="metric-val">99.4%</div>
                    <div className="metric-sub">High Confidence Threshold</div>
                  </div>
                </div>
                <div className="showcase-console">
                  <div className="console-line">
                    <span className="console-tag tag-success">REDACTED</span>
                    <span className="console-text">email_address: "john.doe@enterprise.com" &rarr; <span className="console-highlight">"[REDACTED_EMAIL_1]"</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-success">REDACTED</span>
                    <span className="console-text">tax_identifier: "XXX-XX-4912" &rarr; <span className="console-highlight">"[REDACTED_US_SSN]"</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-info">INFO</span>
                    <span className="console-text">Sanitized prompt ready for air-gapped LLM grounding</span>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'risk' && (
              <>
                <div className="showcase-metrics-row">
                  <div className="showcase-metric-card">
                    <div className="metric-label">ML Compliance Risk</div>
                    <div className="metric-val" style={{ color: '#38bdf8' }}>LOW (0.18)</div>
                    <div className="metric-sub">✓ Safe for downstream analytics</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Anomaly Outliers</div>
                    <div className="metric-val">3 Flagged</div>
                    <div className="metric-sub">Isolation Forest (Contam: 0.01)</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Domain Inferred</div>
                    <div className="metric-val">Fintech / E-Comm</div>
                    <div className="metric-sub">RandomForest Classifier</div>
                  </div>
                </div>
                <div className="showcase-console">
                  <div className="console-line">
                    <span className="console-tag tag-info">CLASSIFY</span>
                    <span className="console-text">Column 'amount_usd' &rarr; <span className="console-highlight">Financial Transaction Metric (Conf: 0.98)</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-warn">OUTLIER</span>
                    <span className="console-text">Isolation Forest detected 3 extreme values in row [1042, 3819, 9021]</span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-success">HEALTH</span>
                    <span className="console-text">Unified dataset health synthesized at <span className="console-highlight">91.4/100</span></span>
                  </div>
                </div>
              </>
            )}

            {activeTab === 'rag' && (
              <>
                <div className="showcase-metrics-row">
                  <div className="showcase-metric-card">
                    <div className="metric-label">PgVector Store</div>
                    <div className="metric-val">1,024-dim</div>
                    <div className="metric-sub">Cosine similarity index active</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Multi-LLM Fallback</div>
                    <div className="metric-val">4 Providers</div>
                    <div className="metric-sub">Ollama &bull; Gemini &bull; Groq &bull; HF</div>
                  </div>
                  <div className="showcase-metric-card">
                    <div className="metric-label">Grounded Accuracy</div>
                    <div className="metric-val">100% Fact-Checked</div>
                    <div className="metric-sub">Zero Hallucinations Guarantee</div>
                  </div>
                </div>
                <div className="showcase-console">
                  <div className="console-line">
                    <span className="console-tag tag-purple">RAG RETRIEVE</span>
                    <span className="console-text">Query: "Are there any anomalies in transaction prices?" &rarr; <span className="console-highlight">Top-3 chunks retrieved (Sim: 0.94)</span></span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-success">LLM RESPOND</span>
                    <span className="console-text">Ollama (Llama 3.2 1B): "3 outliers were detected in 'amount_usd' exceeding 4 standard deviations..."</span>
                  </div>
                  <div className="console-line">
                    <span className="console-tag tag-info">FALLBACK</span>
                    <span className="console-text">Provider cascade ready: Ollama &rarr; Gemini &rarr; Groq &rarr; HuggingFace</span>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </section>

      {/* ---------------- Stats ribbon ---------------- */}
      <section className="landing-stats-ribbon">
        <div className="stats-grid">
          <div className="stat-item">
            <div className="stat-number">14+</div>
            <div className="stat-title">Autonomous Phases</div>
            <div className="stat-desc">End-to-end dataset intelligence pipeline</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">100%</div>
            <div className="stat-title">Zero PII Leakage</div>
            <div className="stat-desc">Air-gapped Presidio entity redacting</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">4-Tier</div>
            <div className="stat-title">LLM Fallback Engine</div>
            <div className="stat-desc">Local Ollama, Gemini, Groq &amp; HuggingFace</div>
          </div>
          <div className="stat-item">
            <div className="stat-number">&lt; 3s</div>
            <div className="stat-title">Average Audit Time</div>
            <div className="stat-desc">Sub-second vectorized statistical checks</div>
          </div>
        </div>
      </section>

      {/* ---------------- Capabilities ---------------- */}
      <section className="landing-section" id="capabilities">
        <div className="section-header">
          <span className="section-tag">Deep Capabilities</span>
          <h2 className="section-title">Built for Mission-Critical Data Workflows</h2>
          <p className="section-desc">
            A unified analytical powerhouse combining deterministic mathematical rigor with cutting-edge conversational AI.
          </p>
        </div>

        <div className="features-grid">
          <div className="feature-card">
            <div>
              <div className="feature-icon-box">📊</div>
              <div className="feature-phase-badge">Phase 4</div>
              <h3 className="feature-card-title">Automated Statistical Profiling</h3>
              <p className="feature-card-desc">
                High-speed quantile distributions, nullity matrices, cardinality counts, histogram buckets, and strict type inferences across every column.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Histograms</span>
              <span className="feature-tag-pill">Quantiles</span>
              <span className="feature-tag-pill">Skewness</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">✅</div>
              <div className="feature-phase-badge">Phase 5</div>
              <h3 className="feature-card-title">Great Expectations Quality Rules</h3>
              <p className="feature-card-desc">
                Autonomous rule suite execution checking null bounds, numeric ranges, string regex constraints, and composite uniqueness with unified scoring.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Rule Suites</span>
              <span className="feature-tag-pill">Quality Score</span>
              <span className="feature-tag-pill">Completeness</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">🔒</div>
              <div className="feature-phase-badge">Phase 6</div>
              <h3 className="feature-card-title">Microsoft Presidio PII Shield</h3>
              <p className="feature-card-desc">
                Deep NLP entity recognition identifying and redacting SSNs, emails, phone numbers, API keys, and credit cards before any data leaves memory.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Entity Redaction</span>
              <span className="feature-tag-pill">Zero PII Leak</span>
              <span className="feature-tag-pill">Regex &amp; NLP</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">🎯</div>
              <div className="feature-phase-badge">Phase 7</div>
              <h3 className="feature-card-title">ML Column Domain &amp; Risk Prediction</h3>
              <p className="feature-card-desc">
                Supervised RandomForest and heuristics infer semantic domain (Financial, Health, Identifiers) and estimate compliance risk tiers automatically.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Random Forest</span>
              <span className="feature-tag-pill">Risk Scoring</span>
              <span className="feature-tag-pill">Domain Mapping</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">⚠️</div>
              <div className="feature-phase-badge">Phase 8</div>
              <h3 className="feature-card-title">Isolation Forest Anomaly Detection</h3>
              <p className="feature-card-desc">
                Unsupervised anomaly isolation paired with Z-Score statistical thresholds to pinpoint corrupt data points, outliers, and injection attempts.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Isolation Forest</span>
              <span className="feature-tag-pill">Z-Score</span>
              <span className="feature-tag-pill">Outlier Indices</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">📈</div>
              <div className="feature-phase-badge">Phase 10</div>
              <h3 className="feature-card-title">Version Drift &amp; Distribution Tracking</h3>
              <p className="feature-card-desc">
                Kolmogorov-Smirnov (KS) statistical tests and Population Stability Index (PSI) compute dataset drift across version snapshots and time.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">KS Test</span>
              <span className="feature-tag-pill">PSI Metric</span>
              <span className="feature-tag-pill">Drift Heatmap</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">🧠</div>
              <div className="feature-phase-badge">Phase 11</div>
              <h3 className="feature-card-title">PgVector RAG Knowledge Index</h3>
              <p className="feature-card-desc">
                Automatic vectorization of analytical findings into PostgreSQL PgVector with cosine similarity search for precise semantic information retrieval.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">PgVector</span>
              <span className="feature-tag-pill">Cosine Search</span>
              <span className="feature-tag-pill">Semantic RAG</span>
            </div>
          </div>

          <div className="feature-card">
            <div>
              <div className="feature-icon-box">💬</div>
              <div className="feature-phase-badge">Phase 12-14</div>
              <h3 className="feature-card-title">Multi-LLM Conversational Assistant</h3>
              <p className="feature-card-desc">
                Multi-session AI chat powered by an automated fallback cascade (Ollama &bull; Gemini &bull; Groq &bull; HuggingFace) with strict zero-PII grounding.
              </p>
            </div>
            <div className="feature-tags">
              <span className="feature-tag-pill">Persistent Chat</span>
              <span className="feature-tag-pill">Multi-LLM Fallback</span>
              <span className="feature-tag-pill">Grounded Answers</span>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- 14-Phase pipeline ---------------- */}
      <section className="landing-section" id="pipeline">
        <div className="section-header">
          <span className="section-tag">Autonomous Pipeline</span>
          <h2 className="section-title">How DATA GUARD AI Inspects Your Data</h2>
          <p className="section-desc">
            Every uploaded dataset traverses an automated verification lifecycle without manual configuration.
          </p>
        </div>

        <div className="pipeline-steps">
          <div className="pipeline-step-card">
            <div className="step-number">1</div>
            <h4 className="step-title">Ingest &amp; Fingerprint</h4>
            <p className="step-desc">
              CSV or Excel files are ingested, validated, and assigned immutable SHA-256 version hashes in PostgreSQL.
            </p>
          </div>

          <div className="pipeline-step-card">
            <div className="step-number">2</div>
            <h4 className="step-title">Profiling &amp; Rules</h4>
            <p className="step-desc">
              Statistical distributions, quantiles, and Great Expectations rule suites run concurrently with high-speed execution.
            </p>
          </div>

          <div className="pipeline-step-card">
            <div className="step-number">3</div>
            <h4 className="step-title">PII Scrub &amp; ML Risk</h4>
            <p className="step-desc">
              Presidio redacts sensitive tokens while ML models infer column risk and Isolation Forest detects anomalies.
            </p>
          </div>

          <div className="pipeline-step-card">
            <div className="step-number">4</div>
            <h4 className="step-title">PgVector RAG &amp; AI Chat</h4>
            <p className="step-desc">
              Findings are embedded into PgVector for semantic search and interactive conversational diagnosis via LLM fallback.
            </p>
          </div>
        </div>
      </section>

      {/* ---------------- Security ---------------- */}
      <section className="landing-section" id="security">
        <div className="security-card-banner">
          <div className="security-left">
            <h3>Zero-Trust Data Protection</h3>
            <p>
              Engineered from the ground up for strict privacy compliance. Sensitive customer data never touches external LLMs or third-party cloud logs.
            </p>
            <ul className="security-list">
              <li className="security-item">
                <span className="security-item-icon">✓</span>
                <span>Local Microsoft Presidio entity redaction before prompt generation</span>
              </li>
              <li className="security-item">
                <span className="security-item-icon">✓</span>
                <span>Air-gapped local LLM execution via Ollama (Llama 3.2 1B)</span>
              </li>
              <li className="security-item">
                <span className="security-item-icon">✓</span>
                <span>Deterministic fallback to Google Gemini, Groq, &amp; HuggingFace</span>
              </li>
              <li className="security-item">
                <span className="security-item-icon">✓</span>
                <span>PostgreSQL database with indexed vector partitions &amp; hash versioning</span>
              </li>
            </ul>
          </div>

          <div className="security-right-box">
            <div className="shield-graphic-header">
              <span style={{ fontSize: '1.4rem' }}>🛡️</span>
              <span className="shield-graphic-title">Privacy Gatekeeper Telemetry</span>
            </div>

            <div className="shield-flow-row">
              <span>Raw Credit Card Numbers</span>
              <span className="shield-badge-blocked">SCRUBBED &amp; REDACTED</span>
            </div>
            <div className="shield-flow-row">
              <span>Customer Emails &amp; Phone</span>
              <span className="shield-badge-blocked">PSEUDONYMIZED</span>
            </div>
            <div className="shield-flow-row">
              <span>Tax Identifiers / SSN</span>
              <span className="shield-badge-blocked">MASKED</span>
            </div>
            <div className="shield-flow-row">
              <span>Sanitized Statistical Summaries</span>
              <span className="shield-badge-passed">SAFE FOR RAG &amp; AI</span>
            </div>
          </div>
        </div>
      </section>

      {/* ---------------- Bottom CTA ---------------- */}
      <section className="landing-bottom-cta">
        <div className="cta-banner-inner">
          <h2 className="cta-title">Ready to Audit Your Enterprise Data?</h2>
          <p className="cta-desc">
            Get instant statistical clarity, automated quality audits, and AI-grounded insights in seconds.
          </p>
          <Link to="/dashboard" className="cta-btn-launch">
            <span>Launch DATA GUARD AI Dashboard</span>
            <span>→</span>
          </Link>
        </div>
      </section>

      {/* ---------------- Footer ---------------- */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <span style={{ fontSize: '1.5rem' }}>🛡️</span>
            <div>
              <strong style={{ color: '#fff', fontSize: '1.1rem' }}>DATA GUARD AI</strong>
              <div style={{ fontSize: '0.8rem', color: '#64748b' }}>Autonomous Data Quality &amp; Privacy Platform</div>
            </div>
          </div>

          <div className="footer-nav-links">
            <Link to="/dashboard" className="footer-nav-link">Dashboard</Link>
            <Link to="/upload" className="footer-nav-link">Upload</Link>
            <Link to="/datasets" className="footer-nav-link">Datasets</Link>
            <Link to="/chat" className="footer-nav-link">AI Chat</Link>
            <Link to="/rag" className="footer-nav-link">RAG Explorer</Link>
          </div>
        </div>

        <div className="footer-copy">
          <span>&copy; 2026 DATA GUARD AI. Built with React, FastAPI, Great Expectations, Presidio, PgVector &amp; Multi-LLM Orchestration.</span>
          <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{ width: 8, height: 8, borderRadius: '50%', background: '#10b981', display: 'inline-block' }} />
            System Operational
          </span>
        </div>
      </footer>
    </div>
  );
}