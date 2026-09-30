import { Link, NavLink, Outlet } from "react-router-dom";
import { MagiLockup } from "@tokyo3rdhq/magi-design-system";

/**
 * Top-level layout — MAGI parent-brand pattern (matches magi-portal).
 *
 *   [MAGI / Product]  [centered nav]  [external links]
 *
 * Inner wrapper is constrained to 1200px (magi-portal's `max-w-page`)
 * so the nav content matches the main site's container. The topbar
 * itself stays full-width so the blurred backdrop extends across the
 * viewport.
 *
 * External destinations get:
 *   - the GitHub SVG icon (matches magi-portal)
 *   - the ↗ indicator + sr-only "(opens in new tab)" announcement
 *
 * Colors come from the design system via <AppTheme>. The MAGI mark uses
 * currentColor — the wrapper's `color` token controls it.
 */
export function App() {
  return (
    <div>
      <header className="tfi-topbar">
        <div className="tfi-topbar-inner">
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
              <svg
                className="tfi-icon"
                fill="currentColor"
                viewBox="0 0 24 24"
                aria-hidden="true"
              >
                <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"></path>
              </svg>
              GitHub<span aria-hidden="true">↗</span>
            </a>
            <a
              className="tfi-nav-link tfi-nav-link-external"
              href="https://discord.gg/gTGnvTdyec"
              target="_blank"
              rel="noreferrer"
            >
              Discord<span aria-hidden="true">↗</span>
            </a>
          </div>
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
                <a href="https://discord.gg/gTGnvTdyec" target="_blank" rel="noreferrer">
                  Discord
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