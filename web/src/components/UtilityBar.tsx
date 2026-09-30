import { useEffect, useState } from "react";
import { Languages, Moon, Sun } from "lucide-react";
import { useI18n } from "../I18nProvider";
import { locales, type Locale } from "../i18n";

/**
 * Top-right utility bar (mirrors magi-portal Layout.astro).
 *
 * Per DS Experience Guidelines §11 (Header utility area):
 *   - Avoid the icon dump. Group + prioritize.
 *   - Operational controls (i18n, theme) belong top-right.
 *   - Conventional actions (theme switch) → icon-only is allowed.
 *
 * Per DS Iconography contract: generic UI icons come from Lucide.
 *
 * The two controls here:
 *
 *   1. Language — first paint shows the current locale's short
 *      label (EN / 中). Tap reveals a tiny popover listing every
 *      available locale with its native name (endonym).
 *
 *   2. Theme toggle — Sun (when dark) / Moon (when light). Flips
 *      `<html data-magi-theme>` between "dark" and "light". The DS
 *      already exposes both palettes via the
 *      [data-magi-theme="…"] CSS selectors in tokens/colors.css, so
 *      the flip cascades to every token without any per-component
 *      JS.
 */
const LOCALES: Locale[] = ["en", "zh"];

export function UtilityBar() {
  const { locale, setLocale, ts } = useI18n();

  // Theme state mirrors the live `<html data-magi-theme>` attribute.
  const [theme, setTheme] = useState<"dark" | "light">(() => {
    if (typeof document === "undefined") return "dark";
    const attr = document.documentElement.getAttribute("data-magi-theme");
    return attr === "light" ? "light" : "dark";
  });

  const [langOpen, setLangOpen] = useState(false);

  useEffect(() => {
    // Keep the icon in sync if the theme attribute flips from
    // elsewhere (e.g. system color-scheme via a future bridge).
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

  // Close the dropdown when the user clicks outside or hits Escape.
  useEffect(() => {
    if (!langOpen) return;
    const onClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement | null;
      if (target && !target.closest(".tfi-lang-wrap")) setLangOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setLangOpen(false);
    };
    document.addEventListener("mousedown", onClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [langOpen]);

  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.setAttribute("data-magi-theme", next);
    try {
      localStorage.setItem("tfi:theme", next);
    } catch {
      // localStorage may be blocked; the DOM mutation above is the
      // authoritative flip — we simply lose persistence.
    }
  };

  const currentLocaleName = locales[locale];

  return (
    <div className="tfi-topbar-utility">
      <div className="tfi-lang-wrap">
        <button
          type="button"
          className="tfi-icon-btn tfi-icon-btn-with-label"
          aria-label={ts("utility.switchLanguageAria").replace("{name}", currentLocaleName)}
          aria-haspopup="listbox"
          aria-expanded={langOpen}
          title={ts("utility.switchLanguageTitle")}
          onClick={() => setLangOpen((v) => !v)}
        >
          <Languages size={14} strokeWidth={1.75} aria-hidden="true" />
          <span className="tfi-icon-btn-label">{ts("utility.currentLocaleLabel")}</span>
        </button>
        {langOpen && (
          <div
            role="listbox"
            aria-label={ts("utility.switchLanguageTitle")}
            className="tfi-lang-dropdown"
          >
            {LOCALES.map((code) => (
              <button
                key={code}
                role="option"
                aria-selected={code === locale}
                data-locale={code}
                className="tfi-lang-option"
                onClick={() => {
                  setLocale(code);
                  setLangOpen(false);
                }}
              >
                {locales[code]}
              </button>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        className="tfi-icon-btn"
        aria-label={ts("utility.switchThemeAria").replace("{name}", theme)}
        title={ts("utility.switchThemeTitle")}
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