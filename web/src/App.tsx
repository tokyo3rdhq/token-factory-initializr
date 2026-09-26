import { Link, NavLink, Outlet } from "react-router-dom";

/**
 * Top-level layout — MAGI parent-brand pattern.
 *
 *   MAGI / Token Factory Initializr
 *
 * Navigation uses tfi-topbar (translucent sticky). Footer uses the
 * 3-column MAGI structure. No token literals — colors come from
 * the design system's CSS custom properties via ProductTheme.
 */
export function App() {
  return (
    <div>
      <header className="tfi-topbar">
        <Link to="/" className="tfi-brand" aria-label="Token Factory Initializr — home">
          <span className="tfi-brand-parent">MAGI</span>
          <span className="tfi-brand-slash">/</span>
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
          <a
            className="tfi-nav-link"
            href="https://github.com/yw79641760/token-factory-initializr"
            target="_blank"
            rel="noreferrer"
          >
            GitHub
          </a>
        </nav>
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
              <li className="tfi-muted">Independent AI lab.</li>
              <li className="tfi-muted">AI infrastructure, built at the edge.</li>
              <li className="tfi-muted">Built for developers and agents.</li>
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
