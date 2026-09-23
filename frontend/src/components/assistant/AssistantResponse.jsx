import React, { useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './AssistantResponse.css';

/**
 * Enterprise Markdown & Provenance Renderer for DataGuard AI Assistant
 */
export default function AssistantResponse({ response, onReindex }) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [highlightedSourceIdx, setHighlightedSourceIdx] = useState(null);
  const [copied, setCopied] = useState(false);
  const evidenceRef = useRef(null);

  if (!response) return null;

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(response.answer || '');
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
    }
  };

  const handleSourceClick = (sourceNum) => {
    setShowEvidence(true);
    setHighlightedSourceIdx(sourceNum - 1);
    setTimeout(() => {
      const el = document.getElementById(`source-chunk-${sourceNum - 1}`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }, 150);
  };

  const formatProviderLabel = (provider) => {
    if (!provider) return 'Hosted AI';
    if (provider === 'gemini') return 'Hosted Gemini API';
    if (provider === 'huggingface') return 'Hosted Hugging Face API';
    if (provider === 'ollama') return 'Local Ollama';
    return provider;
  };

  // Custom component mappings for ReactMarkdown
  const markdownComponents = {
    // Tables
    table: ({ children, ...props }) => (
      <div className="assistant-table-wrapper">
        <table className="assistant-markdown-table" {...props}>
          {children}
        </table>
      </div>
    ),
    th: ({ children, ...props }) => (
      <th {...props}>{children}</th>
    ),
    td: ({ children, ...props }) => {
      // If cell content is a plain string matching risk keywords, style it as a risk pill
      if (typeof children === 'string') {
        const trimmed = children.trim().toUpperCase();
        if (['CRITICAL', 'CRITICAL RISK'].includes(trimmed)) {
          return <td><span className="risk-pill risk-pill--critical">🚨 {children}</span></td>;
        }
        if (['HIGH', 'HIGH RISK'].includes(trimmed)) {
          return <td><span className="risk-pill risk-pill--high">🔴 {children}</span></td>;
        }
        if (['MEDIUM', 'MEDIUM RISK', 'MODERATE'].includes(trimmed)) {
          return <td><span className="risk-pill risk-pill--medium">🟠 {children}</span></td>;
        }
        if (['LOW', 'LOW RISK', 'GOOD'].includes(trimmed)) {
          return <td><span className="risk-pill risk-pill--low">🟢 {children}</span></td>;
        }
        if (['NONE', 'NO RISK', 'SAFE'].includes(trimmed)) {
          return <td><span className="risk-pill risk-pill--none">⚪ {children}</span></td>;
        }
      }
      return <td {...props}>{children}</td>;
    },

    // Headings
    h1: ({ children, ...props }) => (
      <h1 {...props}>
        <span>📌</span>
        <span>{children}</span>
      </h1>
    ),
    h2: ({ children, ...props }) => {
      const text = String(children || '');
      let icon = '📊';
      if (/direct answer|answer/i.test(text)) icon = '💡';
      else if (/key findings|findings|overview/i.test(text)) icon = '🔍';
      else if (/recommendation|suggested|action/i.test(text)) icon = '🛠️';
      else if (/risk|threat/i.test(text)) icon = '🛡️';
      else if (/quality|health/i.test(text)) icon = '✨';
      else if (/limitation|unavailable|warning/i.test(text)) icon = '⚠️';
      else if (/column/i.test(text)) icon = '📋';
      else if (/comparison|drift|version/i.test(text)) icon = '🔄';

      return (
        <h2 {...props}>
          <span style={{ fontSize: '1.05em' }}>{icon}</span>
          <span>{children}</span>
        </h2>
      );
    },
    h3: ({ children, ...props }) => (
      <h3 {...props}>
        <span style={{ color: 'var(--accent-primary, #6366f1)' }}>▸</span>
        <span>{children}</span>
      </h3>
    ),

    // Blockquotes (Callout boxes)
    blockquote: ({ children, ...props }) => {
      const text = String(children || '');
      const isWarning = /limitation|unavailable|warning|caution|note|missing/i.test(text);
      const isDanger = /critical|danger|severe/i.test(text);
      const calloutClass = isDanger ? 'callout-danger' : isWarning ? 'callout-limitation' : '';

      return (
        <blockquote className={calloutClass} {...props}>
          {children}
        </blockquote>
      );
    },

    // Bold text (Risk Pill detection)
    strong: ({ children, ...props }) => {
      if (typeof children === 'string') {
        const upper = children.trim().toUpperCase();
        if (['CRITICAL', 'CRITICAL RISK'].includes(upper)) {
          return <span className="risk-pill risk-pill--critical">🚨 {children}</span>;
        }
        if (['HIGH', 'HIGH RISK'].includes(upper)) {
          return <span className="risk-pill risk-pill--high">🔴 {children}</span>;
        }
        if (['MEDIUM', 'MEDIUM RISK', 'MODERATE'].includes(upper)) {
          return <span className="risk-pill risk-pill--medium">🟠 {children}</span>;
        }
        if (['LOW', 'LOW RISK'].includes(upper)) {
          return <span className="risk-pill risk-pill--low">🟢 {children}</span>;
        }
      }
      return <strong {...props}>{children}</strong>;
    },

    // Paragraphs with Citation Chip Detection
    p: ({ children, ...props }) => {
      // If plain string, parse [Source X] or [X] citations into clickable chips
      if (typeof children === 'string') {
        const citationRegex = /\[(?:Source\s*)?(\d+)\]/gi;
        const parts = [];
        let lastIndex = 0;
        let match;

        while ((match = citationRegex.exec(children)) !== null) {
          if (match.index > lastIndex) {
            parts.push(children.slice(lastIndex, match.index));
          }
          const sourceNum = parseInt(match[1], 10);
          parts.push(
            <button
              key={match.index}
              type="button"
              className="source-citation-chip"
              onClick={() => handleSourceClick(sourceNum)}
              title={`Jump to Grounded Evidence #${sourceNum}`}
            >
              📑 Source {sourceNum}
            </button>
          );
          lastIndex = citationRegex.lastIndex;
        }

        if (lastIndex < children.length) {
          parts.push(children.slice(lastIndex));
        }

        return <p {...props}>{parts}</p>;
      }
      return <p {...props}>{children}</p>;
    },
  };

  const sources = response.sources || [];
  const latencyMs = response.response_time_ms || response.latency_ms || 0;
  const isGrounded = response.grounded ?? response.is_grounded ?? true;

  return (
    <div className="assistant-response-wrapper mb-2xl">
      {/* Main Answer Card */}
      <div className="assistant-response-card">
        {/* Card Header */}
        <div className="assistant-response-header flex-between flex-wrap gap-sm">
          <div className="assistant-response-title-area">
            <div className="assistant-avatar-icon">💡</div>
            <div>
              <h3 className="assistant-title-text">AI Quality Assistant Analysis</h3>
              <div className="assistant-meta-row">
                <span>Generated by:</span>
                <span className="font-semibold" style={{ color: 'var(--text-primary)' }}>
                  {formatProviderLabel(response.provider)}
                </span>
                {response.fallback_occurred && (
                  <span className="badge badge--warning" style={{ fontSize: '0.7rem', padding: '1px 6px' }}>
                    Fallback
                  </span>
                )}
                <span className="assistant-meta-pill">
                  {response.model || response.model_name || 'Standard Model'}
                </span>
                <span>•</span>
                <span>Latency: {latencyMs.toFixed(0)} ms</span>
              </div>
            </div>
          </div>

          <div className="flex-row items-center gap-xs flex-wrap">
            <button
              type="button"
              className="copy-answer-btn"
              onClick={handleCopy}
              title="Copy answer markdown to clipboard"
            >
              {copied ? '✅ Copied' : '📋 Copy Answer'}
            </button>
            {isGrounded ? (
              <span className="badge badge--success flex-row items-center gap-xs">
                <span>🎯</span> Grounded in Evidence
              </span>
            ) : (
              <span className="badge badge--warning flex-row items-center gap-xs">
                <span>⚠️</span> Insufficient Evidence
              </span>
            )}
            <span className="badge badge--neutral">
              {sources.length} Grounded {sources.length === 1 ? 'Source' : 'Sources'}
            </span>
          </div>
        </div>

        {/* Card Body — Clean Rendered Markdown */}
        <div className="assistant-response-body">
          <div className="assistant-markdown-content">
            <ReactMarkdown
              remarkPlugins={[remarkGfm]}
              components={markdownComponents}
            >
              {response.answer || 'No answer generated.'}
            </ReactMarkdown>
          </div>

          {/* Privacy & Provenance Footer */}
          <div className="assistant-response-footer">
            <div className="flex-row items-center gap-xs">
              <span>🔒</span>
              <span>
                <strong>Privacy Guarded:</strong> Synthesized purely from sanitized Phase 11 analytical context. Zero raw dataset cell values or raw PII were supplied to the LLM.
              </span>
            </div>
            <div className="font-mono text-xs">
              Authoritative Server-side Provenance Tracking Active
            </div>
          </div>
        </div>
      </div>

      {/* Grounded Evidence Drawer (Secondary) */}
      <div className="evidence-drawer-card mt-lg" ref={evidenceRef}>
        <div
          className="evidence-drawer-header"
          onClick={() => setShowEvidence(!showEvidence)}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setShowEvidence(!showEvidence); }}
        >
          <div className="flex-row items-center gap-sm">
            <span style={{ fontSize: '1.1rem' }}>📑</span>
            <div>
              <strong style={{ color: 'var(--text-primary)', fontSize: '0.95rem' }}>
                Grounded Analytical Evidence ({sources.length} {sources.length === 1 ? 'source' : 'sources'})
              </strong>
              <div className="text-xs text-muted">
                Authoritative source chunks retrieved via pgvector cosine similarity
              </div>
            </div>
          </div>
          <button
            type="button"
            className="btn btn--secondary btn--sm"
            onClick={(e) => {
              e.stopPropagation();
              setShowEvidence(!showEvidence);
            }}
          >
            {showEvidence ? '▲ Hide Evidence' : '▼ View Evidence'}
          </button>
        </div>

        {showEvidence && (
          <div className="p-md" style={{ background: 'rgba(11, 15, 26, 0.6)' }}>
            {sources.length === 0 ? (
              <div className="p-lg text-center text-muted rounded-md bg-secondary border-subtle">
                No retrieved documents met the similarity threshold.
              </div>
            ) : (
              <div className="grid-responsive-1 gap-md">
                {sources.map((src, idx) => {
                  const isHighlighted = highlightedSourceIdx === idx;
                  const phaseLabel = (src.source_phase || 'PHASE')
                    .replace('PHASE_', 'P')
                    .replace('_', ' ');

                  return (
                    <div
                      key={src.document_id || idx}
                      id={`source-chunk-${idx}`}
                      className={`evidence-source-card ${isHighlighted ? 'highlighted-source' : ''}`}
                    >
                      <div className="flex-between flex-wrap gap-xs mb-sm">
                        <div className="flex-row items-center gap-xs flex-wrap">
                          <span className="badge badge--primary font-semibold">
                            Source #{idx + 1}
                          </span>
                          <span className="badge badge--info">
                            {phaseLabel}
                          </span>
                          <span className="badge badge--neutral font-mono">
                            {src.document_type}
                          </span>
                          {src.column_name && (
                            <span className="badge badge--secondary font-mono">
                              col: {src.column_name}
                            </span>
                          )}
                          {src.version_number != null && (
                            <span className="badge badge--warning">
                              V{src.version_number}
                            </span>
                          )}
                        </div>

                        <div className="flex-row items-center gap-xs font-mono text-xs text-muted">
                          <span>Similarity:</span>
                          <strong style={{ color: 'var(--accent-hover, #818cf8)' }}>
                            {(src.similarity || 0).toFixed(3)}
                          </strong>
                        </div>
                      </div>

                      {/* Content Snippet */}
                      <div
                        className="p-sm rounded-sm font-mono text-xs mb-xs"
                        style={{
                          background: 'rgba(15, 23, 42, 0.85)',
                          border: '1px solid rgba(148, 163, 184, 0.1)',
                          whiteSpace: 'pre-wrap',
                          color: '#e2e8f0',
                          lineHeight: '1.55',
                          maxHeight: '260px',
                          overflowY: 'auto',
                        }}
                      >
                        {src.content_snippet}
                      </div>

                      {/* Metadata Footer */}
                      <div className="flex-between text-xs text-muted mt-xs">
                        <span className="font-mono">
                          doc_id: <code>{String(src.document_id || '').slice(0, 12)}...</code>
                        </span>
                        {src.source_result_id && (
                          <span className="font-mono">
                            src_id: <code>{String(src.source_result_id || '').slice(0, 12)}...</code>
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
