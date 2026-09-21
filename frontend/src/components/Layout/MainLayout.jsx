/**
 * DataGuard AI — Main Layout Component
 *
 * Wraps all pages with sidebar navigation and top header.
 */

import { Outlet, Link } from 'react-router-dom';
import Sidebar from './Sidebar';

export default function MainLayout() {
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        <header className="top-header">
          <div className="header-left">
            <h1 className="page-title" id="page-title">Dashboard</h1>
          </div>
          <div className="header-right" style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <Link
              to="/"
              className="btn-header-home"
              title="Return to Homepage"
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: '0.4rem',
                padding: '0.35rem 0.85rem',
                borderRadius: '8px',
                fontSize: '0.85rem',
                fontWeight: 500,
                color: '#cbd5e1',
                background: 'rgba(30, 41, 59, 0.7)',
                border: '1px solid rgba(148, 163, 184, 0.25)',
                textDecoration: 'none',
                transition: 'all 0.2s ease',
              }}
            >
              <span>🏠</span>
              <span>Home</span>
            </Link>
            <span className="header-env-badge">Development</span>
          </div>
        </header>
        <main className="page-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
