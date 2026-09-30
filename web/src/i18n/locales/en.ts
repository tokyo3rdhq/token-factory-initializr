import type { TranslationTree } from "../types";

/**
 * English dictionary — the canonical fallback. Keys missing here
 * must not exist (the type system enforces it); keys present in
 * other locales but absent here will fall back to whatever the
 * `t()` function decides at lookup time (currently the string
 * "key.<missing>" so the breakage is loud).
 */
const en: TranslationTree = {
  nav: {
    start: "Start",
    browse: "Browse",
    generate: "Generate",
  },

  utility: {
    currentLocaleLabel: "EN",
    switchLanguageAria: "Switch language (current: {name})",
    switchLanguageTitle: "Language",
    switchThemeAria: "Switch theme (current: {name})",
    switchThemeTitle: "Switch theme",
    optionEnglish: "English",
    optionChinese: "中文",
  },

  footer: {
    columns: {
      product: "Product",
      resources: "Resources",
      community: "Community",
      magi: "MAGI",
    },
    brandCaption: "Independent AI lab. AI infrastructure, built at the edge. Built for developers and agents.",
    copyright: "© 2026 MAGI",
    provenance:
      "Endpoints from NVIDIA NIM · AMD Radeon AI · Hugging Face Inference. Generated configs expire in 5 minutes — by design.",
  },

  home: {
    eyebrow: "Token Factory Initializr",
    headline: "Initialize your token factory.",
    subhead:
      "Pick the free AI endpoints that fit your project. We generate ready-to-use configuration for LiteLLM.",
    ctaBrowse: "Browse models →",
    ctaReset: "Reset",
    fields: {
      project: "Project",
      projectPlaceholder: "e.g. Coding assistant",
      context: "Context",
      contextMin128k: "128K+",
      contextMin32k: "32K+",
      contextMin8k: "8K+",
      contextMinAny: "Any",
      toolCalling: "Tool calling",
      toolCallingYes: "Yes",
      toolCallingNo: "No",
      vision: "Vision",
      visionYes: "Yes",
      visionNo: "No",
      cost: "Cost",
      costFree: "Free only",
      costAny: "Any",
      providers: "Providers",
      providersHelper:
        "Tick the providers whose endpoints you want included.",
      maxModels: "Max models",
      maxModelsHelper:
        "How many models to include in the recommended bucket (1–10).",
    },
    summaryTemplate: (n, m) =>
      `We'll match ${n} model${n === 1 ? "" : "s"} from ${m} provider${m === 1 ? "" : "s"}.`,
  },

  browse: {
    eyebrow: "Browse",
    headingNoReq: "All endpoints",
    headingWithReq: "Recommended models",
    loading: "Loading catalog…",
    countNoReqTemplate: (n) =>
      `${n} model${n === 1 ? "" : "s"} match the catalog.`,
    countWithReqTemplate: (n) =>
      `${n} model${n === 1 ? "" : "s"} match your requirements.`,
    noReqBannerBefore: "No requirements set. ",
    noReqBannerAfter:
      " to specify what you're building — we'll pick the right models for you.",
    emptyBefore: "No models match. Try loosening the constraints — ",
    emptyAfter: "edit requirements",
    sectionRecommended: "Recommended",
    sectionOther: "Other matching",
    hintRecommendedTemplate: (n) => `Top ${n} matching`,
    hintOther: "match — pick if useful",
    fallbackPrefix: "Could not load KV catalog: ",
    fallbackFixture: "Falling back to bundled fixtures.",
    fallbackHelp: "Set TFI_USE_LOCAL_FIXTURES=1 to browse offline.",
  },

  generate: {
    eyebrow: "Generate",
    headline: "Token Factory",
    subheadNoSelection: "No models selected yet.",
    subheadWithSelectionTemplate: (n) =>
      `${n} model${n === 1 ? "" : "s"} ready to initialize.`,
    emptyBefore: "Nothing selected. Head to ",
    emptyForm: ", then ",
    emptyBrowse: " to pick models.",
    selectionHeader: "Selection",
    fieldModel: "Model",
    fieldProvider: "Provider",
    fieldId: "ID",
    fieldFormat: "Format",
    optionLitellm: "LiteLLM",
    btnInitialize: "Initialize",
    btnInitializing: "Initializing…",
    emptyClick: "Click Initialize to generate the config.",
    yamlReady: "Ready",
    yamlCopy: "Copy",
    yamlCopied: "Copied",
    yamlDownload: "Download",
    yamlAgentPrompt: "Agent Prompt",
    fieldUrl: "URL",
    fieldTtl: "TTL",
    ttlValue: "5 minutes — by design",
  },
};

export default en;