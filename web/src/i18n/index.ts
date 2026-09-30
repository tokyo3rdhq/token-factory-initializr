/**
 * Public API of the i18n module:
 *   - Locale + TranslationTree types
 *   - translations registry
 *   - locales display labels (for the switcher)
 *
 * Runtime helpers (the React provider + hook) live in
 * `./I18nProvider.tsx`. React components consume them via the
 * `useI18n()` hook rather than this module directly.
 */
export type { Locale, TranslationTree } from "./types";
export { translations } from "./translations";
export { locales } from "./locales-meta";