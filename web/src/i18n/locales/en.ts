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
      "Pick the free AI endpoints that fit your project. Generate ready-to-use configuration for LiteLLM, NewAPI, or Bifrost.",
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
    // ----- Agent Access (docs/tfi_homepage_agent_access.md) -----
    ctaAgent: "I'm an Agent",
    agentHeading: "Use TFI with an AI Agent",
    agentBlurb:
      "Let your AI agent discover TFI's model catalog and help you configure your Token Factory.",
    agentCopy: "Copy Prompt",
    agentCopied: "Copied",
    agentReadGuide: "Read Agent Guide",
    agentClose: "Close",
    agentPrompt: `I want to use Token Factory Initializr (TFI) to select models and configure my Token Factory.

Start by reading:
https://start.magi.website/agents.md

Use TFI's public model catalog to discover and inspect available models:
https://start.magi.website/api/v1/models

Help me choose suitable models based on my requirements, then use TFI's configuration workflow at:
https://start.magi.website/

If I provide a generated TFI configuration URL, fetch it and help me safely apply the generated configuration to my existing Token Factory configuration.

Do not expose or modify secrets. Preserve my existing configuration unless I explicitly ask you to replace it.`,
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
    /** Per-provider last-updated line shown under the catalog count.
     *  Each entry is `{provider, timestamp}` formatted in the user's
     *  locale + time zone by ``utils/datetime.ts``. The separator
     *  string sits between entries (default: bullet). */
    providerTimestampsSeparator: " · ",
    /** Tooltip for the timestamps line; explains the values come from
     *  the data pipeline's publish stage. */
    providerTimestampsTitle: "Last successful catalog fetch per provider",
    /** Tooltip for each provider count badge on the Browse hero.
     *  The count is the number of endpoints the pipeline last
     *  wrote for that provider. ``{count}`` and ``{label}`` are
     *  interpolated by the caller. */
    providerCountTitle: (count: number, label: string) =>
      `${count.toLocaleString("en-US")} endpoints in the current ${label} catalog`,
    /** Shown when the user has filters active (tag / search) and no
     *  models match. Distinct from emptyBefore which is shown when
     *  the requirement filter is the only thing filtering. */
    emptyFiltered:
      "No models match the current filter — try clearing a tag or relaxing the search.",
    /** Accessible label for the per-row external-link affordance.
     *  Receives the model_id so the i18n string can compose it
     *  naturally — see docs/tfi_model_source_url.md §7. */
    viewSourceLabel: (modelId: string) => `View source for ${modelId}`,
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
    yamlAgentPromptHelp: "Copy the generated URL and a per-selection agent prompt to your clipboard in one go.",
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
      bifrost: {
        name: "Bifrost",
        description:
          "A high-performance LLM gateway for routing and serving multiple model providers behind an OpenAI-compatible API.",
      },
    },
  },
};

export default en;