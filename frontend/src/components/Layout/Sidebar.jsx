/**
 * DataGuard AI — Sidebar Navigation Component
 */

import { NavLink } from 'react-router-dom';

const navItems = [
  { path: '/', label: 'Dashboard', icon: '📊' },
  { path: '/upload', label: 'Upload', icon: '📁' },
  { path: '/datasets', label: 'Datasets', icon: '🗃️' },
  { path: '/chat', label: 'AI Chat', icon: '💬' },
  { path: '/rag', label: 'RAG Knowledge', icon: '🧠' },
  { path: '/assistant', label: 'AI Assistant', icon: '🤖' },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <span className="logo-icon">🛡️</span>
          <span className="logo-text">DataGuard AI</span>
        </div>
        <p className="sidebar-tagline">Data Quality Assistant</p>
      </div>

      <nav className="sidebar-nav">
        {navItems.map((item) => (
          <NavLink
            key={item.path}
            to={item.path}
            className={({ isActive }) =>
              `sidebar-link ${isActive ? 'sidebar-link--active' : ''}`
            }
            end={item.path === '/'}
          >
            <span className="sidebar-link-icon">{item.icon}</span>
            <span className="sidebar-link-label">{item.label}</span>
          </NavLink>
        ))}
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
