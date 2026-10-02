import { Link, NavLink, Outlet } from "react-router-dom";
import { MagiLockup } from "@tokyo3rdhq/magi-design-system";
import { UtilityBar } from "./components/UtilityBar";
import { useI18n } from "./I18nProvider";

/**
 * Top-level layout — matches magi-portal topbar.
 *
 *   [MAGI] / [Product]      [centered nav]      [i18n + theme]
 *   └─parent brand          └─this product       └─ops controls
 *     magi.website             /                    lang + theme
 *
 * The MAGI lockup itself is a parent-brand asset; clicking it
 * escapes to magi.website (per docs/UX §2 — the secondary product
 * title must remain in place, just not anchor the navigation).
 * The product-name portion (Token Factory Initializr / Token工厂启动器)
 * is the in-site home link.
 *
 * Outer .tfi-topbar is sticky and full-width so the backdrop-blur
 * spans the viewport (magi-portal pattern). The inner
 * .tfi-topbar-inner is the content container.
 *
 * External destinations (GitHub, Discord) live in the footer
 * Community column per DS Experience Guidelines §11.
 *
 * The footer "MAGI" column header is also a link to the parent brand
 * site — matches the navbar so visitors can always find the way
 * back to MAGI.
 */
export function App() {
  const { ts } = useI18n();
  const brandLabel = ts("home.eyebrow"); // "Token Factory Initializr" / "Token工厂启动器"

  return (
    <div>
      <header className="tfi-topbar">
        <div className="tfi-topbar-inner">
          {/*
            Two-link brand: the parent-brand lockup escapes to
            magi.website; the product-name portion goes to TFI's
            home. Splitting them keeps the parent-brand asset clickable
            without forcing the product link off-center.
          */}
          <div className="tfi-brand">
            <a
              href="https://magi.website"
              className="tfi-brand-mark-link"
              aria-label="MAGI — parent brand"
              target="_blank"
              rel="noreferrer"
            >
              <MagiLockup size="sm" className="tfi-brand-mark" />
              <span className="tfi-sr-only">(opens in new tab)</span>
            </a>
            <span className="tfi-brand-sep" aria-hidden="true">
              /
            </span>
            <Link to="/" className="tfi-brand-product-link">
              {brandLabel}
            </Link>
          </div>
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
            {/* MAGI column header is a link to the parent brand site,
                matching the navbar's two-link split. No ↗ indicator
                (brand-mark convention — destinations like GitHub /
                Discord get the indicator; brand links don't). */}
            <h4>
              <a
                href="https://magi.website"
                target="_blank"
                rel="noreferrer"
                className="tfi-footer-magi-link"
              >
                {ts("footer.columns.magi")}
              </a>
            </h4>
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