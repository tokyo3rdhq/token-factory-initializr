/**
 * Canonical locale identifier — every translation key in the app is
 * keyed by one of these. Adding a new language means:
 *
 *   1. extend the `Locale` union below
 *   2. add a translation dictionary under `locales/<code>.ts`
 *   3. register it in `translations.ts`
 *   4. add the display label in `locales-meta.ts`
 *
 * Per docs/guidelines.md §5.1 (Internationalization), native-language
 * names (endonyms) are used in the switcher — never country flags.
 */
import type { InitializrTranslations } from "../types";

export type Locale = "en" | "zh";

/**
 * Translation tree. The shape is structural — adding a new key only
 * requires updating the union type, all locales' dictionaries, and
 * any consumers. A key that is missing in a locale falls back to the
 * English string (see `useI18n().t`), so we never have to ship
 * 100% translations.
 */
export interface TranslationTree {
  /** Top-level nav (Start / Browse / Generate). */
  nav: {
    start: string;
    browse: string;
    generate: string;
  };

  /** Top-right utility bar (Language + Theme). */
  utility: {
    /** Display label for the current locale (shown in the switcher when closed). */
    currentLocaleLabel: string;
    /** Aria label, template: "Switch language (current: {name})". */
    switchLanguageAria: string;
    /** Title attribute shown on hover. */
    switchLanguageTitle: string;
    /** Aria label, template: "Switch theme (current: {name})". */
    switchThemeAria: string;
    /** Title attribute. */
    switchThemeTitle: string;
    /** Label used in the dropdown row for English. */
    optionEnglish: string;
    /** Label used in the dropdown row for Chinese. */
    optionChinese: string;
  };

  /** Footer (4-column layout). */
  footer: {
    columns: {
      product: string;
      resources: string;
      community: string;
      magi: string;
    };
    /** Brand-side caption. */
    brandCaption: string;
    /** "© 2026 MAGI". */
    copyright: string;
    /** Endpoint source + 5-min TTL note. */
    provenance: string;
  };

  /** Home page. */
  home: {
    eyebrow: string;
    headline: string;
    subhead: string;
    ctaBrowse: string;
    ctaReset: string;
    fields: {
      project: string;
      projectPlaceholder: string;
      context: string;
      contextMin128k: string;
      contextMin32k: string;
      contextMin8k: string;
      contextMinAny: string;
      toolCalling: string;
      toolCallingYes: string;
      toolCallingNo: string;
      vision: string;
      visionYes: string;
      visionNo: string;
      cost: string;
      costFree: string;
      costAny: string;
      providers: string;
      providersHelper: string;
      maxModels: string;
      maxModelsHelper: string;
    };
    /** Template: "We'll match {n} model(s) from {m} provider(s)." */
    summaryTemplate: (n: number, m: number) => string;
  };

  /** Browse page. */
  browse: {
    eyebrow: string;
    headingNoReq: string;
    headingWithReq: string;
    /** "Loading catalog…" */
    loading: string;
    /** Template: "{n} model(s) match the catalog." */
    countNoReqTemplate: (n: number) => string;
    /** Template: "{n} model(s) match your requirements." */
    countWithReqTemplate: (n: number) => string;
    /** Template: "{matching} match out of {visible} visible" — shown
     *  when filters are active so the user sees how many models the
     *  filter excluded. */
    countFilteredTemplate: (matching: number, visible: number) => string;
    noReqBannerBefore: string;
    noReqBannerAfter: string;
    emptyBefore: string;
    emptyAfter: string;
    /** Shown when the user has tag filters / search active and no
     *  models match. Distinct from emptyBefore (which fires when
     *  the requirement filter alone produces an empty result). */
    emptyFiltered: string;
    sectionRecommended: string;
    sectionOther: string;
    /** Template: "Top {n} matching" */
    hintRecommendedTemplate: (n: number) => string;
    hintOther: string;
    /** Template: "{n} selected" — bottom-row counter. */
    selectedCountTemplate: (n: number) => string;
    /** Template: "Select all {n} visible" — primary filter action. */
    selectAllVisibleTemplate: (n: number) => string;
    /** Template: "Clear {n} selected" — secondary action. */
    clearAllTemplate: (n: number) => string;
    /** Banner shown when KV is unreachable. */
    fallbackPrefix: string;
    fallbackFixture: string;
    fallbackHelp: string;
    /** Tag filter taxonomy. Each tag has a label (chip text) and a
     *  description (title attribute on the chip for accessibility). */
    tags: {
      chat: { label: string; description: string };
      vision: { label: string; description: string };
      tools: { label: string; description: string };
      free: { label: string; description: string };
      longCtx: { label: string; description: string };
    };
    /** Filter row strings. */
    filters: {
      searchPlaceholder: string;
      reset: string;
    };
  };

  /** Generate page. */
  generate: {
    eyebrow: string;
    headline: string;
    subheadNoSelection: string;
    /** Template: "{n} model(s) ready to initialize." */
    subheadWithSelectionTemplate: (n: number) => string;
    emptyBefore: string;
    emptyForm: string;
    emptyBrowse: string;
    selectionHeader: string;
    fieldModel: string;
    fieldProvider: string;
    fieldId: string;
    fieldFormat: string;
    optionLitellm: string;
    btnInitialize: string;
    btnInitializing: string;
    emptyClick: string;
    yamlReady: string;
    yamlCopy: string;
    yamlCopied: string;
    yamlDownload: string;
    yamlAgentPrompt: string;
    fieldUrl: string;
    fieldTtl: string;
    /** "5 minutes — by design" */
    ttlValue: string;
  }

  /** Phase-1 Initializr — picker, validation, factory descriptions. */
  initializr: InitializrTranslations;
}