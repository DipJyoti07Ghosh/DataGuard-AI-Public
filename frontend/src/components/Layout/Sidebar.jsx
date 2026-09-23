/**
 * DataGuard AI — Sidebar Navigation
 *
 * Renders the two-group workspace navigation with the active-state
 * gradient pill and the backend status indicator.
 *
 * Design system: .dg2-* (see src/styles/ui-migration.css)
 *
 * NOTE: This component is purely presentational.
 * - It does not fetch data.
 * - It does not call any API.
 * - It only navigates via react-router <Link>.
 */

import { Link, useLocation } from 'react-router-dom';

const workspace = [
  ['/dashboard',  'D', 'Dashboard'],
  ['/upload',     'U', 'Upload'],
  ['/datasets',   'S', 'Datasets'],
];

const intelligence = [
  ['/assistant',  'A', 'AI Assistant'],
  ['/chat',       'C', 'AI Chat'],
  ['/rag',        'K', 'RAG Knowledge'],
];

export default function Sidebar() {
  const { pathname } = useLocation();

  const isActive = (path, label) => {
    // Dashboard: matches /dashboard and any /datasets/.../dashboard
    // (the "/" landing page is NOT the dashboard)
    if (label === 'Dashboard') {
      return (
        pathname === '/dashboard' ||
        pathname.endsWith('/dashboard')
      );
    }

    // Datasets: matches /datasets and /datasets/:id
    // but NOT /datasets/.../dashboard (that's a Dashboard view)
    if (label === 'Datasets') {
      if (pathname === '/datasets') return true;
      if (pathname.startsWith('/datasets/') && !pathname.endsWith('/dashboard')) {
        return true;
      }
      return false;
    }

    // Everything else: exact match
    return pathname === path;
  };

  const renderGroup = (title, items) => (
    <section className="dg2-nav-group" key={title}>
      <p>{title}</p>
      <nav>
        {items.map(([path, icon, label]) => {
          const active = isActive(path, label);
          return (
            <Link
              key={label}
              to={path}
              className={active ? 'active' : ''}
            >
              {active && <span className="dg2-active-pill" aria-hidden="true" />}
              <i>{icon}</i>
              <span>{label}</span>
            </Link>
          );
        })}
      </nav>
    </section>
  );

  return (
    <aside className="dg2-sidebar">
      <Link className="dg2-brand" to="/" aria-label="DATA GUARD AI home">
        <span className="dg2-logo" aria-hidden="true">DG</span>
        <span>
          <b>DATA GUARD <em>AI</em></b>
          <small>Data Quality Assistant</small>
        </span>
      </Link>

      {renderGroup('WORKSPACE', workspace)}
      {renderGroup('INTELLIGENCE', intelligence)}

      <div className="dg2-bottom">
        <div className="dg2-backend">
          <span className="dg2-live-dot"><i /></span>
          <span>
            <b>Backend</b>
            <small>Connected</small>
          </span>
        </div>
      </div>
    </aside>
  );
}