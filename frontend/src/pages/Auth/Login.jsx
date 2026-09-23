/**
 * DataGuard AI — Sign In Page
 *
 * Email/password login + Google sign-in.
 * Handles post-login redirects and reason banners when users are bounced
 * from a protected route.
 *
 * Visual design: DATA GUARD AI workspace skin (.au-* classes).
 * Backend contract: UNCHANGED.
 *   - login(email, password) via useAuth
 *   - googleLogin(idToken) via useAuth
 *   - Uses existing routes: /, /register
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import GoogleButton from '../../components/Auth/GoogleButton';

const REASON_MESSAGES = {
  upload_requires_signin:
    'Sign in required. You need an account to upload and version your datasets.',
  signin_required: 'Please sign in to continue.',
};

export default function Login() {
  const { login, googleLogin, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = location.state?.from || '/';
  const reason = location.state?.reason;
  const notice = reason
    ? REASON_MESSAGES[reason] || REASON_MESSAGES.signin_required
    : null;

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = 'Sign In';
  }, []);

  useEffect(() => {
    if (isAuthenticated) navigate(redirectTo, { replace: true });
  }, [isAuthenticated, navigate, redirectTo]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email.trim(), password);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle(idToken) {
    setError(null);
    setSubmitting(true);
    try {
      await googleLogin(idToken);
      navigate(redirectTo, { replace: true });
    } catch (err) {
      setError(err.message || 'Google sign-in failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="au-page">
      <div className="au-card">
        {/* Brand */}
        <div className="au-header">
          <div className="au-logo">DG</div>
          <h1 className="au-title">Welcome back</h1>
          <p className="au-subtitle">Sign in to continue to DATA GUARD AI</p>
        </div>

        {/* Reason banner (redirect from protected route) */}
        {notice && (
          <div className="au-notice" role="status">
            <span>🔒</span>
            <span>{notice}</span>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="au-error" role="alert">
            <span>⚠️</span>
            <span>{error}</span>
          </div>
        )}

        {/* Form */}
        <form onSubmit={handleSubmit} className="au-form">
          <label className="au-field">
            <span>Email</span>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              autoComplete="email"
            />
          </label>

          <label className="au-field">
            <span>Password</span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Your password"
              required
              autoComplete="current-password"
            />
          </label>

          <button
            type="submit"
            className="au-submit"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="au-spinner" /> Signing in…
              </>
            ) : (
              'Sign In'
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="au-divider">
          <span>or</span>
        </div>

        {/* Google */}
        <div className="au-google">
          <GoogleButton onCredential={handleGoogle} label="continue_with" />
        </div>

        {/* Switch to Sign Up */}
        <p className="au-switch">
          Don't have an account? <Link to="/register">Create one</Link>
        </p>

        <p className="au-switch au-switch--muted">
          <Link to="/">← Continue as guest</Link>
        </p>
      </div>
    </div>
  );
}