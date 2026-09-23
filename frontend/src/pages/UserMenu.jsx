/**
 * DataGuard AI — User Menu
 *
 * Two states:
 *   1. Guest  → shows Sign In + Sign Up buttons
 *   2. Signed in → shows avatar + name + dropdown
 *
 * The dropdown exposes:
 *   - Account header (name, email, provider)
 *   - My Datasets → /datasets
 *   - Sign Out    → clears auth + navigates to /login
 *
 * Backend contract: UNCHANGED.
 *   - Reads user from useAuth()
 *   - Calls logout() from useAuth()
 *   - Uses existing routes: /login, /register, /datasets
 */

import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();

  // Close dropdown on outside click
  useEffect(() => {
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', onDocClick);
    return () => document.removeEventListener('mousedown', onDocClick);
  }, []);

  // ============================================================
  // GUEST STATE — Sign In + Sign Up
  // ============================================================
  if (!user) {
    return (
      <div className="um-guest">
        <button
          type="button"
          className="um-btn um-btn--ghost"
          onClick={() => navigate('/login')}
        >
          Sign In
        </button>
        <button
          type="button"
          className="um-btn um-btn--primary"
          onClick={() => navigate('/register')}
        >
          Sign Up
        </button>
      </div>
    );
  }

  // ============================================================
  // SIGNED-IN STATE — avatar + dropdown
  // ============================================================
  const initials = (user.name || user.email || '?')
    .split(' ')
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="um-wrap" ref={wrapRef}>
      <button
        type="button"
        className="um-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <span className="um-avatar">{initials}</span>
        <span className="um-name">{user.name}</span>
        <span className="um-caret">{open ? '▲' : '▼'}</span>
      </button>

      {open && (
        <div className="um-dropdown" role="menu">
          <div className="um-dropdown-head">
            <div className="um-dropdown-name">{user.name}</div>
            <div className="um-dropdown-email">{user.email}</div>
            <div className="um-dropdown-provider">
              {user.auth_provider === 'google'
                ? '🔗 Google account'
                : '✉️ Email account'}
            </div>
          </div>

          <div className="um-dropdown-sep" />

          <button
            type="button"
            className="um-dropdown-item"
            onClick={() => {
              setOpen(false);
              navigate('/datasets');
            }}
          >
            📁 My Datasets
          </button>

          <button
            type="button"
            className="um-dropdown-item um-dropdown-item--danger"
            onClick={() => {
              setOpen(false);
              logout();
              navigate('/login');
            }}
          >
            🚪 Sign Out
          </button>
        </div>
      )}
    </div>
  );
}