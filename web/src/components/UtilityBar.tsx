import { LanguageSwitcher } from "./LanguageSwitcher";
import { ThemeToggle } from "./ThemeToggle";

/**
 * Top-right utility bar — operational controls per DS Experience
 * Guidelines §11.
 *
 *   [🌐 Language]  [☀️ / 🌙 / 🖥 Theme]
 *
 * Order matches magi-portal: language first, theme last. Each control
 * is icon-only — Sun / Moon / Monitor for theme, Lucide Languages
 * for i18n. No label is rendered next to either icon; the active
 * state is conveyed through `aria-label` and the dropdown's
 * `aria-selected`.
 *
 *   - LanguageSwitcher: dropdown listing zh / en endonyms.
 *     Default = navigator.language (en fallback). Persists to
 *     localStorage on explicit choice.
 *   - ThemeToggle: 3-state cycle (system → dark → light → system).
 *     Default = system (follows prefers-color-scheme). Persists to
 *     localStorage on explicit choice.
 *
 * Both files inline-FOUC their state on <html> before the React tree
 * mounts (see web/index.html), so the first frame is correct — no
 * flicker, no theme swap on hydration.
 */
export function UtilityBar() {
  return (
    <div className="tfi-topbar-utility">
      <LanguageSwitcher />
      <ThemeToggle />
    </div>
  );
}