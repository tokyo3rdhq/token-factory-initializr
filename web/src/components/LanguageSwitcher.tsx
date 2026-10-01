import { useState } from "react";
import { Languages } from "lucide-react";
import { useI18n } from "../I18nProvider";
import { locales, type Locale } from "../i18n";

/**
 * LanguageSwitcher — Lucide Languages icon + locale dropdown.
 *
 * Mirrors magi-portal Layout.astro lines 218-261 (the language
 * dropdown pattern). Per DS Experience Guidelines §11: a single
 * icon is preferred over stacking an icon + a label.
 *
 * The current locale is exposed via `aria-label` ("Switch language
 * (current: 中文)") + a visually-hidden live region. The visible
 * icon never carries a label, so the right-utility stays at one
 * per icon — clean IA per §11 ("avoid the icon dump").
 *
 * Close behavior:
 *   - click outside → closes
 *   - Escape key   → closes
 *   - selecting a locale → closes
 * Mirrors the menu semantics React was planning against.
 */
const LOCALES: Locale[] = ["en", "zh"];

export function LanguageSwitcher() {
  const { locale, setLocale } = useI18n();
  const [open, setOpen] = useState(false);

  const currentLocaleName = locales[locale];

  return (
    <div
      className="tfi-lang-wrap"
      onKeyDown={(e) => {
        if (e.key === "Escape") setOpen(false);
      }}
    >
      <button
        type="button"
        className="tfi-icon-btn"
        aria-label={`Switch language (current: ${currentLocaleName})`}
        aria-haspopup="listbox"
        aria-expanded={open}
        title={`Language: ${currentLocaleName}`}
        onClick={() => setOpen((v) => !v)}
        onMouseDown={(e) => e.stopPropagation()}
      >
        <Languages size={14} strokeWidth={1.75} aria-hidden="true" />
      </button>
      {/* Visually-hidden live region — keeps screen readers informed
          of the currently active language so they don't have to open
          the dropdown to find out. magi-portal Layout.astro:222-223. */}
      <span className="tfi-sr-only" aria-live="polite">
        {currentLocaleName}
      </span>
      {open && (
        <div
          role="listbox"
          aria-label="Language"
          className="tfi-lang-dropdown"
          onMouseDown={(e) => e.stopPropagation()}
        >
          {LOCALES.map((code) => {
            const selected = code === locale;
            return (
              <button
                key={code}
                role="option"
                aria-selected={selected}
                data-locale={code}
                className={`tfi-lang-option${selected ? " selected" : ""}`}
                onClick={() => {
                  setLocale(code);
                  setOpen(false);
                }}
              >
                <span className="tfi-lang-option-name">{locales[code]}</span>
                {selected && (
                  <span aria-hidden="true" className="tfi-lang-option-mark">
                    ✓
                  </span>
                )}
              </button>
            );
          })}
        </div>
      )}
      {open && (
        <ClickAwayListener onAway={() => setOpen(false)} />
      )}
    </div>
  );
}

/**
 * Lightweight click-away handler — attaches a one-shot mousedown
 * listener that calls onAway if the click wasn't inside the listbox
 * (already guarded via stopPropagation on the dropdown's own
 * mousedown). Kept inline so the parent component stays small.
 */
function ClickAwayListener({ onAway }: { onAway: () => void }) {
  // The dropdown's onMouseDown stops propagation, so any mousedown
  // that reaches this listener is necessarily outside the menu.
  // Attach a one-shot to clean up after one fire.
  if (typeof window !== "undefined") {
    requestAnimationFrame(() => {
      const handler = () => {
        window.removeEventListener("mousedown", handler);
        onAway();
      };
      window.addEventListener("mousedown", handler);
    });
  }
  return null;
}