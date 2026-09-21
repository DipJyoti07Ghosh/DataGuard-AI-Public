/**
 * DataGuard AI — Sidebar Navigation Component
 */

import { Link, useLocation } from 'react-router-dom';

const navItems = [
  { id: 'home', path: '/', label: 'Home', icon: '🏠' },
  { id: 'dashboard', path: '/dashboard', label: 'Dashboard', icon: '📊' },
  { id: 'upload', path: '/upload', label: 'Upload', icon: '📁' },
  { id: 'datasets', path: '/datasets', label: 'Datasets', icon: '🗃️' },
  { id: 'chat', path: '/chat', label: 'AI Chat', icon: '💬' },
  { id: 'rag', path: '/rag', label: 'RAG Knowledge', icon: '🧠' },
  { id: 'assistant', path: '/assistant', label: 'AI Assistant', icon: '🤖' },
];

export default function Sidebar() {
  const location = useLocation();
  const pathname = location.pathname;

  const isNavActive = (item) => {
    if (item.id === 'home') {
      return pathname === '/';
    }
    if (item.id === 'dashboard') {
      return pathname === '/dashboard' || pathname.endsWith('/dashboard');
    }
    if (item.id === 'upload') {
      return pathname === '/upload' || pathname.startsWith('/upload/');
    }
    if (item.id === 'chat') {
      return pathname === '/chat' || pathname.endsWith('/chat');
    }
    if (item.id === 'rag') {
      return pathname === '/rag' || pathname.endsWith('/rag');
    }
    if (item.id === 'assistant') {
      return pathname === '/assistant' || pathname.endsWith('/assistant');
    }
    if (item.id === 'datasets') {
      if (pathname === '/datasets') return true;
      if (
        pathname.startsWith('/datasets') &&
        !pathname.endsWith('/dashboard') &&
        !pathname.endsWith('/chat') &&
        !pathname.endsWith('/rag') &&
        !pathname.endsWith('/assistant')
      ) {
        return true;
      }
      return false;
    }
    return false;
  };

  return (
    <aside className="sidebar">
      <Link to="/" className="sidebar-brand" style={{ textDecoration: 'none', cursor: 'pointer' }} title="Return to Homepage">
        <div className="sidebar-logo">
          <span className="logo-icon">🛡️</span>
          <span className="logo-text">DataGuard AI</span>
        </div>
        <p className="sidebar-tagline">Data Quality Assistant</p>
      </Link>

      <nav className="sidebar-nav">
        {navItems.map((item) => {
          const active = isNavActive(item);
          return (
            <Link
              key={item.id}
              to={item.path}
              className={`sidebar-link ${active ? 'sidebar-link--active' : ''}`}
            >
              <span className="sidebar-link-icon">{item.icon}</span>
              <span className="sidebar-link-label">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status" id="backend-status">
          <span className="status-dot status-dot--unknown"></span>
          <span className="status-text">Checking...</span>
        </div>
      </div>
    </aside>
  );
}
