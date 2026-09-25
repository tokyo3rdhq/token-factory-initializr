import { Link, NavLink, Outlet } from "react-router-dom";

/**
 * Top-level layout: header (logo + nav) + Outlet for child route content.
 *
 * The Pages Functions serve this as the SPA shell. Static assets are
 * uploaded via ``wrangler pages deploy``; routes under ``/api/*`` and
 * ``/generated/*`` are handled by Functions; everything else falls
 * through to this SPA.
 */
export function App() {
  return (
    <div className="app">
      <header className="topbar">
        <Link to="/" className="brand">
          <span className="brand-mark">⌘</span>
          <span className="brand-text">Token Factory Initializr</span>
        </Link>
        <nav className="nav">
          <NavLink to="/" end className="nav-link">
            Start
          </NavLink>
          <NavLink to="/browse" className="nav-link">
            Browse
          </NavLink>
          <NavLink to="/generate" className="nav-link">
            Generate
          </NavLink>
          <a
            className="nav-link"
            href="https://github.com/yw79641760/token-factory-initializr"
            target="_blank"
            rel="noreferrer"
          >
            Repo
          </a>
        </nav>
      </header>
      <main className="main">
        <Outlet />
      </main>
      <footer className="footer">
        <span>
          Free endpoints from NVIDIA NIM · AMD Radeon AI · Hugging Face
          Inference.
        </span>
        <span>
          Generated configs expire in 5 minutes — by design, not by bug.
        </span>
      </footer>
    </div>
  );
}