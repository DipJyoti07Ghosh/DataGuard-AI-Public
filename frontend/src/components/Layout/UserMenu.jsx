import { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

export default function UserMenu() {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    function onDocClick(e) {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) {
        setOpen(false);
      }
    }

    document.addEventListener('mousedown', onDocClick);

    return () => {
      document.removeEventListener('mousedown', onDocClick);
    };
  }, []);

  // Not signed in → show Login/Register buttons
  if (!user) {
    return (
      <div className="user-menu-guest">
        <button
          className="btn btn--secondary btn--sm"
          onClick={() => navigate('/login')}
        >
          Sign In
        </button>

        <button
          className="btn btn--primary btn--sm"
          onClick={() => navigate('/register')}
        >
          Sign Up
        </button>
      </div>
    );
  }

  // Get user's initials for avatar
  const initials = (user.name || user.email || '?')
    .split(' ')
    .map((s) => s[0])
    .slice(0, 2)
    .join('')
    .toUpperCase();

  return (
    <div className="user-menu" ref={wrapRef}>

      {/* User menu button */}
      <button
        className="user-menu-trigger"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="user-avatar">
          {initials}
        </span>

        <span className="user-name">
          {user.name}
        </span>

        <span className="user-caret">
          {open ? '▲' : '▼'}
        </span>
      </button>

      {/* Dropdown */}
      {open && (
        <div className="user-menu-dropdown">

          <div className="user-menu-header">
            <div className="user-menu-name">
              {user.name}
            </div>

            <div className="user-menu-email">
              {user.email}
            </div>

            <div className="user-menu-provider">
              {user.auth_provider === 'google'
                ? '🔗 Google account'
                : '✉️ Email account'}
            </div>
          </div>

          <div className="user-menu-divider" />

          {/* My Datasets */}
          <button
            className="user-menu-item"
            onClick={() => {
              setOpen(false);
              navigate('/datasets');
            }}
          >
            📁 My Datasets
          </button>

          {/* Sign Out */}
          <button
            className="user-menu-item user-menu-item--danger"
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
