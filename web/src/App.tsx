import { Link, NavLink, Outlet } from "react-router-dom";
import { MagiLockup } from "@tokyo3rdhq/magi-design-system";
import { UtilityBar } from "./components/UtilityBar";
import { useI18n } from "./I18nProvider";

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
 *
 * Strings here are routed through the i18n provider. The footer
 * "MAGI" column keeps its English caption in both languages (the
 * brand column reads as a single English voice on purpose).
 */
export function App() {
  const { ts } = useI18n();

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
              {ts("nav.start")}
            </NavLink>
            <NavLink to="/browse" className="tfi-nav-link">
              {ts("nav.browse")}
            </NavLink>
            <NavLink to="/generate" className="tfi-nav-link">
              {ts("nav.generate")}
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
            <h4>{ts("footer.columns.product")}</h4>
            <ul>
              <li><Link to="/">{ts("nav.start")}</Link></li>
              <li><Link to="/browse">{ts("nav.browse")}</Link></li>
              <li><Link to="/generate">{ts("nav.generate")}</Link></li>
            </ul>
          </div>
          <div className="tfi-footer-col">
            <h4>{ts("footer.columns.resources")}</h4>
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
            <h4>{ts("footer.columns.community")}</h4>
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
            <h4>{ts("footer.columns.magi")}</h4>
            <ul>
              <li className="magi-caption">{ts("footer.brandCaption")}</li>
            </ul>
          </div>
        </div>
        <div className="tfi-footer-meta">
          <span>{ts("footer.copyright")}</span>
          <span>{ts("footer.provenance")}</span>
        </div>
      </footer>
    </div>
  );
}