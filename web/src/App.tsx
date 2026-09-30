import { Link, NavLink, Outlet } from "react-router-dom";
import { MagiLockup } from "@tokyo3rdhq/magi-design-system";
import { UtilityBar } from "./components/UtilityBar";

/**
 * Top-level layout — matches magi-portal topbar.
 *
 *   [MAGI / Product]  [centered nav]  [i18n + theme]
 *
 * Outer .tfi-topbar is sticky and full-width so the backdrop-blur
 * spans the viewport (magi-portal pattern). The inner
 * .tfi-topbar-inner is a 3-column grid constrained to ~1200px with
 * brand on the left, primary nav centered, and the utility area
 * (language + theme) on the right.
 *
 * The previous GitHub / Discord external links have moved to a new
 * "Community" column in the footer per DS Experience Guidelines §11
 * — operational controls belong top-right, external destinations
 * belong in the footer's Community / Resources columns.
 *
 * Heights match magi-portal (`h-11` = 44px); the previous ~12px taller
 * spacing is gone.
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
          <UtilityBar />
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
            <h4>Community</h4>
            <ul>
              <li>
                <a
                  className="tfi-footer-ext"
                  href="https://github.com/yw79641760/token-factory-initializr"
                  target="_blank"
                  rel="noreferrer"
                >
                  GitHub
                  <span aria-hidden="true">↗</span>
                  <span className="tfi-sr-only">(opens in new tab)</span>
                </a>
              </li>
              <li>
                <a
                  className="tfi-footer-ext"
                  href="https://discord.gg/gTGnvTdyec"
                  target="_blank"
                  rel="noreferrer"
                >
                  Discord
                  <span aria-hidden="true">↗</span>
                  <span className="tfi-sr-only">(opens in new tab)</span>
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