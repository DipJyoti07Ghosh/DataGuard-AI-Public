/**
 * DataGuard AI — Protected Route
 *
 * Wraps routes that require authentication.
 * - If user is logged in → renders children normally.
 * - If user is a guest → redirects to /login and remembers where they were
 *   plus an optional `reason` used by the login page to explain why.
 */

import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function ProtectedRoute({ children, reason = 'signin_required' }) {
  const { isAuthenticated, loading } = useAuth();
  const location = useLocation();

  // While checking localStorage / verifying token, don't flash the login page
  if (loading) {
    return (
      <div className="loading-container" style={{ minHeight: '60vh' }}>
        <div className="spinner-large"></div>
        <p className="loading-text">Verifying session…</p>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          from: location.pathname,
          reason,
        }}
      />
    );
  }

  return children;
}