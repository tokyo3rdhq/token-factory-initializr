import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { translations, locales, type Locale, type TranslationTree } from "./i18n";

/**
 * Storage key for the user's explicit locale preference. Survives
 * across visits; the very first visit (no key) falls back to OS
 * language via {@link resolveInitialLocale}. The same key is read
 * by the inline FOUC script in `index.html` so first paint and
 * React's initial state agree.
 */
const STORAGE_KEY = "tfi:locale";

/**
 * Default locale — used when no preference is stored AND the OS
 * language doesn't match a known locale. English is the canonical
 * default (per docs/guidelines.md §5.1).
 */
const DEFAULT_LOCALE: Locale = "en";

/**
 * Resolve the locale to use on first paint.
 *
 * Resolution order (mirrors the inline FOUC script in index.html so
 * React's first render matches what the user already saw):
 *
 *   1. <html data-tfi-locale> set by the FOUC script. Always
 *      present in production; this is the canonical signal.
 *   2. localStorage `tfi:locale` — explicit user preference.
 *   3. navigator.language — auto-detect `zh` / `en`.
 *   4. DEFAULT_LOCALE (`en`) — final fallback.
 *
 * The FOUC script writes to *before paint* based on localStorage or
 * browser language; React reads it back here for the first render
 * so there's no swap-on-hydration.
 */
function resolveInitialLocale(): Locale {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  // 1. FOUC attribute — already resolved before paint.
  const attr = document.documentElement.getAttribute("data-tfi-locale");
  if (attr === "en" || attr === "zh") return attr;
  // 2. localStorage preference — explicit user choice.
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY);
    if (stored === "en" || stored === "zh") return stored;
  } catch {
    // localStorage blocked.
  }
  // 3. Browser language → `zh` if it starts with "zh", else `en`.
  const navLang = window.navigator?.language?.toLowerCase() ?? "";
  if (navLang.startsWith("zh")) return "zh";
  if (navLang.startsWith("en")) return "en";
  // 4. Fallback.
  return DEFAULT_LOCALE;
}

interface I18nContextValue {
  locale: Locale;
  /** Switch the active locale and persist the choice. */
  setLocale: (next: Locale) => void;
  /** Lookup a string by dot-path. Returns whatever the key resolves
   *  to (string for plain keys, function for templates). Missing
   *  keys fall back to the English dictionary. */
  t: (key: string) => unknown;
  /** Type-safe string lookup — common case. Returns the string or
   *  ``[non-string:key]`` if the resolved value isn't a string. */
  ts: (key: string) => string;
  /** Full translation dictionary for the current locale (rarely
   *  needed — most consumers prefer `ts(key)` / `t(key)`). */
  dict: TranslationTree;
}

const I18nContext = createContext<I18nContextValue | null>(null);

/**
 * Provider — wrap the app once at the root. The provider also
 * mirrors the active locale onto `<html lang>` and `<html
 * data-tfi-locale>` so non-JS consumers (screen readers, browser
 * translation prompts, design-system CSS hooks) can pick up the
 * choice.
 */
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(resolveInitialLocale);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage blocked — DOM mutation below is still applied;
      // we just lose persistence across visits.
    }
    // Mirror onto <html> so screen readers, browser translation
    // prompts, and CSS hooks all see the change immediately. The
    // FOUC script in index.html writes these same attributes on
    // first paint; this keeps them in sync after every explicit
    // choice made by the user.
    document.documentElement.lang = next === "zh" ? "zh-CN" : "en";
    document.documentElement.setAttribute("data-tfi-locale", next);
  }, []);

  // No useEffect needed — the FOUC script wrote the right attribute
  // before React mounted, and `setLocale` keeps it in sync on every
  // change. Avoiding an effect also keeps the first React render
  // flicker-free.

  // Lookup walks the active dictionary by dot-path. Function-valued
  // keys (e.g. ``home.summaryTemplate``) are returned as-is — the
  // consumer is responsible for invoking them. Plain string keys
  // come back as strings; missing keys fall back to the English
  // dictionary and finally emit a loud ``[missing:key]`` marker.
  const dict = translations[locale];
  const t = useCallback(
    (key: string): unknown => {
      const parts = key.split(".");
      const walk = (tree: unknown): unknown => {
        let cur: unknown = tree;
        for (const p of parts) {
          if (cur && typeof cur === "object" && p in (cur as Record<string, unknown>)) {
            cur = (cur as Record<string, unknown>)[p];
          } else {
            return undefined;
          }
        }
        return cur;
      };
      const value = walk(dict);
      if (value !== undefined) return value;
      // Fallback to English so the user sees SOMETHING meaningful.
      const enValue = walk(translations.en);
      if (enValue !== undefined) return enValue;
      return `[missing:${key}]`;
    },
    [dict],
  );

// Type-safe lookup overload — the most common case (plain string).
  const ts = useCallback(
    (key: string): string => {
      const v = t(key);
      return typeof v === "string" ? v : `[non-string:${key}]`;
    },
    [t],
  );

  const value = useMemo<I18nContextValue>(
    () => ({ locale, setLocale, t, ts, dict }),
    [locale, setLocale, t, ts, dict],
  );

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

/**
 * Hook — must be called inside an `<I18nProvider>`. Throws on
 * misuse (which would happen at startup, so it's a hard error to
 * catch in tests).
 */
export function useI18n(): I18nContextValue {
  const ctx = useContext(I18nContext);
  if (!ctx) {
    throw new Error("useI18n must be used inside <I18nProvider>");
  }
  return ctx;
}

/**
 * Convenience for non-React consumers — returns the current locale
 * without subscribing. Pair with `<I18nProvider>` so the locale is
 * initialized before this is called.
 */
export function displayLocaleName(locale: Locale): string {
  return locales[locale];
}