import en from "./locales/en";
import zh from "./locales/zh";
import type { Locale, TranslationTree } from "./types";

/**
 * Translation registry — keyed by locale. The first entry is the
 * default fallback (English) used when a key is missing in the
 * current dictionary.
 */
export const translations: Record<Locale, TranslationTree> = { en, zh };

export type { Locale, TranslationTree };