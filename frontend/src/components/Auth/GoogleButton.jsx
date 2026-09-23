/**
 * Google Sign-In button — uses Google Identity Services (GIS).
 * Renders Google's own button and calls onCredential(idToken) on success.
 */

import { useEffect, useRef } from 'react';

const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '';

export default function GoogleButton({ onCredential, label = 'continue_with' }) {
  const divRef = useRef(null);

  useEffect(() => {
    if (!CLIENT_ID) return;

    let cancelled = false;

    function init() {
      if (cancelled || !window.google?.accounts?.id) return;
      window.google.accounts.id.initialize({
        client_id: CLIENT_ID,
        callback: (response) => {
          if (response?.credential && onCredential) {
            onCredential(response.credential);
          }
        },
      });
      window.google.accounts.id.renderButton(divRef.current, {
        theme: 'outline',
        size: 'large',
        width: 320,
        text: label,       // 'signin_with' | 'signup_with' | 'continue_with'
        shape: 'rectangular',
      });
    }

    // Wait for the GIS script if it hasn't loaded yet
    if (window.google?.accounts?.id) init();
    else {
      const iv = setInterval(() => {
        if (window.google?.accounts?.id) {
          clearInterval(iv);
          init();
        }
      }, 150);
      return () => { cancelled = true; clearInterval(iv); };
    }

    return () => { cancelled = true; };
  }, [onCredential, label]);

  if (!CLIENT_ID) {
    return (
      <div style={{
        padding: '10px 14px',
        border: '1px dashed rgba(148,163,184,0.3)',
        borderRadius: '10px',
        fontSize: '0.85rem',
        color: 'var(--text-muted)',
        textAlign: 'center',
      }}>
        Google Sign-In not configured (set VITE_GOOGLE_CLIENT_ID)
      </div>
    );
  }

  return <div ref={divRef} style={{ display: 'flex', justifyContent: 'center' }} />;
}