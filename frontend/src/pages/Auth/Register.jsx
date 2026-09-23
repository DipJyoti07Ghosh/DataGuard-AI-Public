/**
 * DataGuard AI — Create Account Page
 *
 * Email/password registration + Google sign-up.
 *
 * Visual design: DATA GUARD AI workspace skin (.au-* classes, shared with Login).
 * Backend contract: UNCHANGED.
 *   - register(name, email, password) via useAuth
 *   - googleLogin(idToken) via useAuth
 *   - Uses existing routes: /, /login
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import GoogleButton from '../../components/Auth/GoogleButton';

export default function Register() {
  const { register, googleLogin, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    const titleEl = document.getElementById('page-title');
    if (titleEl) titleEl.textContent = 'Create Account';
  }, []);

  useEffect(() => {
    if (isAuthenticated) navigate('/', { replace: true });
  }, [isAuthenticated, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError('Password must be at least 8 characters long.');
      return;
    }

    setSubmitting(true);
    try {
      await register(name.trim(), email.trim(), password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Registration failed.');
    } finally {
      setSubmitting(false);
    }
  }

  async function handleGoogle(idToken) {
    setError(null);
    setSubmitting(true);
    try {
      await googleLogin(idToken);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Google sign-up failed.');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="au-page">
      <div className="au-card">
        {/* Brand */}
        <div className="au-header">
          <div className="au-logo au-logo--alt">DG</div>
          <h1 className="au-title">Create your account</h1>
          <p className="au-subtitle">Start protecting your data with DATA GUARD AI</p>
        </div>

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
            <span>Full Name</span>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Jane Doe"
              required
              minLength={2}
              autoComplete="name"
            />
          </label>

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
              placeholder="At least 8 characters"
              required
              minLength={8}
              autoComplete="new-password"
            />
            <span className="au-hint">Minimum 8 characters.</span>
          </label>

          <button
            type="submit"
            className="au-submit"
            disabled={submitting}
          >
            {submitting ? (
              <>
                <span className="au-spinner" /> Creating account…
              </>
            ) : (
              'Create Account'
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="au-divider">
          <span>or</span>
        </div>

        {/* Google */}
        <div className="au-google">
          <GoogleButton onCredential={handleGoogle} label="signup_with" />
        </div>

        {/* Switch to Sign In */}
        <p className="au-switch">
          Already have an account? <Link to="/login">Sign in</Link>
        </p>

        <p className="au-switch au-switch--muted">
          <Link to="/">← Continue as guest</Link>
        </p>
      </div>
    </div>
  );
}