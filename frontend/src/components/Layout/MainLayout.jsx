/**
 * DataGuard AI — Main Layout
 *
 * The application shell. Owns:
 *   - Sidebar (rendered as <Sidebar />)
 *   - Top bar with page title, Home link, theme toggle, user menu
 *   - Aurora background glow
 *   - Mobile top strip
 *   - Route transitions (Framer Motion, respects prefers-reduced-motion)
 *   - Theme persistence (localStorage key: datalens-theme)
 *
 * Presents the Outlet in the same position as before, so every page
 * continues to render unchanged.
 *
 * Presents <h1 id="page-title" /> so pages that do
 *   document.getElementById('page-title').textContent = '...'
 * keep working without modification.
 *
 * No API calls. No backend contract changes.
 */

import { Outlet, Link, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import Sidebar from "./Sidebar";
import UserMenu from "./UserMenu";

/**
 * Derive the visible top-bar title from the current path.
 * Matches every route in App.jsx.
 */
function deriveTitle(pathname) {
  if (pathname === "/" || pathname === "/dashboard") return "Dashboard";
  if (pathname.includes("/assistant")) return "AI Assistant";
  if (pathname.includes("/rag")) return "RAG Knowledge Explorer";
  if (pathname.includes("/chat")) return "AI Chat";
  if (pathname.includes("/risk")) return "Risk Scoring";
  if (pathname.includes("/pii")) return "PII Detection";
  if (pathname.includes("/quality")) return "Quality Scorecard";
  if (pathname.includes("/anomalies")) return "Anomaly Detection";
  if (pathname.includes("/issues")) return "Prioritization & Health";
  if (pathname.includes("/profile")) return "Data Profiling";
  if (pathname.includes("/compare")) return "Version Comparison";
  if (pathname.includes("/upload")) return "Dataset Upload";
  if (pathname.includes("/datasets")) return "Datasets";
  if (pathname.includes("/login")) return "Sign In";
  if (pathname.includes("/register")) return "Create Account";
  return "DATA GUARD AI";
}

const THEME_KEY = "datalens-theme";

function getInitialTheme() {
  const stored = localStorage.getItem(THEME_KEY);
  if (stored === "light" || stored === "dark") return stored;
  return window.matchMedia("(prefers-color-scheme: light)").matches
    ? "light"
    : "dark";
}

export default function MainLayout() {
  const { pathname } = useLocation();
  const reduceMotion = useReducedMotion();
  const [theme, setTheme] = useState(getInitialTheme);
  const title = deriveTitle(pathname);

  // Apply theme to <html data-theme="..."> and persist it.
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
  }, [theme]);

  // Reflect the visible title in the document <title> tag.
  useEffect(() => {
    document.title = `DATA GUARD AI - ${title}`;
  }, [title]);

  const toggleTheme = () =>
    setTheme((current) => (current === "dark" ? "light" : "dark"));

  const pageMotion = reduceMotion
    ? {}
    : {
        initial: { opacity: 0, y: 16 },
        animate: { opacity: 1, y: 0 },
        exit: { opacity: 0, y: -8 },
        transition: { type: "spring", stiffness: 280, damping: 26, mass: 0.9 },
      };

  return (
    <div className="dg2-app">
      <div className="dg2-aurora" aria-hidden="true" />

      <Sidebar />

      <main className="dg2-main">
        {/* ---------------- Top bar ---------------- */}
        <header className="dg2-topbar">
          <div>
            <b id="page-title">{title}</b>
          </div>

          <div>
            <Link to="/">Home</Link>

            <span>DEVELOPMENT</span>

            <button
              className="dg2-header-theme"
              aria-label="Toggle DATA GUARD AI color theme"
              onClick={toggleTheme}
              type="button"
            >
              {theme === "dark" ? "☀" : "◐"}
            </button>

            <UserMenu />
          </div>
        </header>

        {/* ---------------- Mobile strip ---------------- */}
        {/* ============ Mobile strip (hidden on desktop) ============ */}
        <div className="dg-mobile-bar">
          <b id="page-title-mobile">{title}</b>
          <div>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label="Toggle theme"
            >
              Theme
            </button>
          </div>
        </div>

        {/* ---------------- Page content ---------------- */}
        <AnimatePresence mode="wait">
          <motion.div key={pathname} className="dg-route" {...pageMotion}>
            <Outlet />
          </motion.div>
        </AnimatePresence>
      </main>
    </div>
  );
}
