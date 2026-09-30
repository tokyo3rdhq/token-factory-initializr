import type { Locale } from "./types";

/**
 * Display labels for the language switcher — native script (endonym)
 * per docs/guidelines.md §5.1. Never use country flags: a flag
 * represents a country, not a language.
 */
export const locales: Record<Locale, string> = {
  en: "English",
  zh: "中文",
};