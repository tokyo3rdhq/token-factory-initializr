import { useEffect, useState } from "react";
import { Languages, Moon, Sun } from "lucide-react";

/**
 * Top-right utility bar (mirrors magi-portal Layout.astro).
 *
 * Per DS Experience Guidelines §11 (Header utility area):
 *   - Avoid the icon dump. Group + prioritize.
 *   - Operational controls (i18n, theme) belong top-right.
 *   - Conventional actions (theme switch) → icon-only is allowed.
 *
 * Per DS Iconography contract: generic UI icons come from Lucide.
 * The DS declares `lucide-react@^0.460.0` as a peer dependency and
 * tfi's web package now installs it to match.
 *
 * The two controls here:
 *
 *   1. Language — first paint. Tap reveals a tiny popover with the
 *      available locales (English only today; the dropdown shape is
 *      here so adding more locales is a one-line change). The DS
 *      doesn't ship a language primitive yet.
 *
 *   2. Theme toggle — switches `<html data-magi-theme>` between
 *      "dark" and "light". The DS already exposes both palettes
 *      via the [data-magi-theme="…"] CSS selectors in
 *      tokens/colors.css — flipping the attribute cascades to every
 *      token without any per-component JS.
 *
 * Persistence follows magi-portal ThemeToggle: localStorage wins
 * after the first explicit toggle; the OS prefers-color-scheme media
 * query seeds the initial choice for fresh visitors.
 */
export function UtilityBar() {
  // Theme state mirrors the live `<html data-magi-theme>` attribute.
  // Read once on mount; the toggle below flips both.
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof document === "undefined") return "dark";
    const attr = document.documentElement.getAttribute("data-magi-theme");
    return attr === "light" ? "light" : "dark";
  });

  const [langOpen, setLangOpen] = useState(false);

  useEffect(() => {
    // Re-read on every render — keeps the icon in sync if the theme
    // is changed from elsewhere (e.g. system color-scheme change).
    const observer = new MutationObserver(() => {
      const attr = document.documentElement.getAttribute("data-magi-theme");
      setTheme(attr === "light" ? "light" : "dark");
    });
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-magi-theme"],
    });
    return () => observer.disconnect();
  }, []);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-magi-theme", next);
    try {
      localStorage.setItem("tfi:theme", next);
    } catch {
      // localStorage may be blocked (private mode, sandboxed iframe).
      // The DOM mutation above is what actually flips the theme; we
      // simply lose persistence — acceptable fallback.
    }
  };

  return (
    <div className="tfi-topbar-utility">
      <div className="tfi-lang-wrap">
        <button
          type="button"
          className="tfi-icon-btn"
          aria-label="Switch language (current: English)"
          aria-haspopup="listbox"
          aria-expanded={langOpen}
          title="Language: English"
          onClick={() => setLangOpen((v) => !v)}
        >
          <Languages size={14} strokeWidth={1.75} aria-hidden="true" />
          <span className="tfi-sr-only">English</span>
        </button>
        {langOpen && (
          <div
            role="listbox"
            aria-label="Language"
            className="tfi-lang-dropdown"
          >
            <button
              role="option"
              aria-selected="true"
              data-locale="en"
              className="tfi-lang-option"
              onClick={() => setLangOpen(false)}
            >
              English
            </button>
          </div>
        )}
      </div>

      <button
        type="button"
        className="tfi-icon-btn"
        aria-label={`Switch theme (current: ${theme})`}
        title={`Switch theme — currently ${theme}`}
        onClick={toggleTheme}
      >
        {theme === "dark" ? (
          <Sun size={14} strokeWidth={1.75} aria-hidden="true" />
        ) : (
          <Moon size={14} strokeWidth={1.75} aria-hidden="true" />
        )}
      </button>
    </div>
  );
}