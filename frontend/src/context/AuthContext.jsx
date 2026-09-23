
import { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  authApi,
  setAuth as persistAuth,
  clearAuth as persistClear,
  getToken,
  getStoredUser,
} from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());
  const [token, setToken] = useState(getToken());
  const [loading, setLoading] = useState(true);

  // On mount, validate token by hitting /me
  useEffect(() => {
    let cancelled = false;
    async function bootstrap() {
      const stored = getToken();
      if (!stored) {
        setLoading(false);
        return;
      }
      try {
        const me = await authApi.me();
        if (!cancelled) {
          setUser(me);
          persistAuth(stored, me);
        }
      } catch {
        if (!cancelled) {
          persistClear();
          setUser(null);
          setToken(null);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    bootstrap();
    return () => { cancelled = true; };
  }, []);

  const login = useCallback(async (email, password) => {
    const res = await authApi.login(email, password);
    setToken(res.access_token);
    setUser(res.user);
    persistAuth(res.access_token, res.user);
    return res.user;
  }, []);

  const register = useCallback(async (name, email, password) => {
    const res = await authApi.register(name, email, password);
    setToken(res.access_token);
    setUser(res.user);
    persistAuth(res.access_token, res.user);
    return res.user;
  }, []);

  const googleLogin = useCallback(async (idToken) => {
    const res = await authApi.googleLogin(idToken);
    setToken(res.access_token);
    setUser(res.user);
    persistAuth(res.access_token, res.user);
    return res.user;
  }, []);

  const logout = useCallback(() => {
    persistClear();
    setToken(null);
    setUser(null);
  }, []);

  const value = {
    user,
    token,
    loading,
    isAuthenticated: !!user,
    login,
    register,
    googleLogin,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}