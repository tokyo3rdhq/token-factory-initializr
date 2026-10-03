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
    sectionAll: "All matching",
    hintRecommendedTemplate: (n: number) => `Top ${n} matching`,
    hintOther: "match — pick if useful",
    hintAllTemplate: (n: number) => `All ${n} matching`,
    selectedCountTemplate: (n: number) =>
      n === 1 ? "1 selected" : `${n} selected`,
    selectAllVisibleTemplate: (n: number) =>
      n === 1 ? "Select 1 visible model" : `Select all ${n} visible`,
    clearAllTemplate: (n: number) =>
      n === 1 ? "Clear 1 selected" : `Clear ${n} selected`,
    countFilteredTemplate: (matching: number, visible: number) =>
      `${matching} match out of ${visible} visible.`,
    /** Shown when the user has filters active (tag / search) and no
     *  models match. Distinct from emptyBefore which is shown when
     *  the requirement filter is the only thing filtering. */
    emptyFiltered:
      "No models match the current filter — try clearing a tag or relaxing the search.",
    /** Tag filter taxonomy. Each tag has a label (chip text) and a
     *  description (title attribute on the chip for accessibility). */
    tags: {
      chat: {
        label: "Chat",
        description: "Models with chat-style conversation capability.",
      },
      vision: {
        label: "Vision",
        description: "Models that accept image inputs.",
      },
      tools: {
        label: "Tools",
        description: "Models that support tool / function calling.",
      },
      free: {
        label: "Free",
        description: "Endpoints with confirmed free pricing.",
      },
      longCtx: {
        label: "128K+",
        description: "Models with a 128,000+ token context window.",
      },
    },
    /** Filter row strings. */
    filters: {
      searchPlaceholder: "Search by name, provider, or id",
      reset: "Reset filters",
    },
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

  initializr: {
    pickerHeading: "Token Factory",
    pickerDescription:
      "Choose the gateway that runs your models. TFI will produce a config it understands.",
    selectionCountTemplate: (n: number) =>
      n === 1 ? "1 model selected" : `${n} models selected`,
    validation: {
      noModels:
        "No models selected yet. Pick one or more from Browse, then come back to choose Token Factory and generate.",
      noFactory:
        "Choose a Token Factory to generate the configuration.",
    },
    errorPrefix: "Unable to generate configuration:",
    formatLabelTemplate: (factoryName: string) =>
      `${factoryName} configuration`,
    factories: {
      litellm: {
        name: "LiteLLM",
        description:
          "Open-source Python SDK + proxy that unifies 100+ LLM APIs behind the OpenAI interface.",
      },
      newapi: {
        name: "NewAPI",
        description:
          "Self-hostable LLM gateway (one-api compatible) that channels many upstream providers behind a single endpoint.",
      },
    },
  },
};

export default en;