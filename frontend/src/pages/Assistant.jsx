/**
 * DataGuard AI — AI Assistant Page (Placeholder)
 * Will be implemented in Phase 14.
 */

import { useEffect } from 'react';

export default function Assistant() {
  useEffect(() => {
    document.getElementById('page-title').textContent = 'AI Assistant';
  }, []);

  return (
    <div className="placeholder-page">
      <div className="placeholder-card">
        <span className="placeholder-icon">🤖</span>
        <h2>AI Data Quality Assistant</h2>
        <p className="placeholder-text">
          Ask natural-language questions about your datasets,
          quality issues, drift, and get AI-powered recommendations.
        </p>
        <span className="placeholder-phase">Coming in Phase 14</span>
      </div>
    </div>
  );
}
