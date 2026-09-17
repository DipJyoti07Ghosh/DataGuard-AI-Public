/**
 * DataGuard AI — Main Layout Component
 *
 * Wraps all pages with sidebar navigation and top header.
 */

import { Outlet } from 'react-router-dom';
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
          <div className="header-right">
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
