import { Link, NavLink, Outlet } from "react-router-dom";
import { MagiLockup } from "@tokyo3rdhq/magi-design-system";

/**
 * Top-level layout — MAGI parent-brand pattern (matches magi-portal).
 *
 *   [MAGI / Product] [centered nav] [external links]
 *
 * Three-section topbar mirrors the main site structure. Centered nav
 * keeps internal routes visually grouped; external links (GitHub, etc.)
 * sit on the right with arrow indicators. The product name lives in the
 * topbar so the user's product context is visible across all routes.
 *
 * Colors come from the design system via <AppTheme>. The MAGI mark uses
 * currentColor — the wrapper's `color` token controls it.
 */
export function App() {
  return (
    <div>
      <header className="tfi-topbar">
        <Link
          to="/"
          className="tfi-brand"
          aria-label="Token Factory Initializr — home"
        >
          <MagiLockup size="sm" className="tfi-brand-mark" />
          <span className="tfi-brand-sep" aria-hidden="true">
            /
          </span>
          <span className="tfi-brand-product">Token Factory Initializr</span>
        </Link>
        <nav className="tfi-nav" aria-label="primary">
          <NavLink to="/" end className="tfi-nav-link">
            Start
          </NavLink>
          <NavLink to="/browse" className="tfi-nav-link">
            Browse
          </NavLink>
          <NavLink to="/generate" className="tfi-nav-link">
            Generate
          </NavLink>
        </nav>
        <div className="tfi-topbar-external">
          <a
            className="tfi-nav-link tfi-nav-link-external"
            href="https://github.com/yw79641760/token-factory-initializr"
            target="_blank"
            rel="noreferrer"
          >
            GitHub<span aria-hidden="true">↗</span>
          </a>
        </div>
      </header>

      <main>
        <Outlet />
      </main>

      <footer className="tfi-footer">
        <div className="tfi-footer-cols">
          <div className="tfi-footer-col">
            <h4>Product</h4>
            <ul>
              <li><Link to="/">Start</Link></li>
              <li><Link to="/browse">Browse</Link></li>
              <li><Link to="/generate">Generate</Link></li>
            </ul>
          </div>
          <div className="tfi-footer-col">
            <h4>Resources</h4>
            <ul>
              <li>
                <a href="https://github.com/yw79641760/token-factory-initializr" target="_blank" rel="noreferrer">
                  GitHub
                </a>
              </li>
              <li>
                <a href="/api/manifest" target="_blank" rel="noreferrer">
                  Catalog manifest
                </a>
              </li>
              <li>
                <a href="/api/providers" target="_blank" rel="noreferrer">
                  Providers
                </a>
              </li>
            </ul>
          </div>
          <div className="tfi-footer-col">
            <h4>MAGI</h4>
            <ul>
              <li className="magi-caption">Independent AI lab.</li>
              <li className="magi-caption">AI infrastructure, built at the edge.</li>
              <li className="magi-caption">Built for developers and agents.</li>
            </ul>
          </div>
        </div>
        <div className="tfi-footer-meta">
          <span>© 2026 MAGI</span>
          <span>
            Endpoints from NVIDIA NIM · AMD Radeon AI · Hugging Face Inference.
            Generated configs expire in 5 minutes — by design.
          </span>
        </div>
      </footer>
    </div>
  );
}
