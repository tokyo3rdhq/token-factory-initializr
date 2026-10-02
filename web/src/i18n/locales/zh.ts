import type { TranslationTree } from "../types";

/**
 * 简体中文字典. Keys mirror the English dictionary exactly.
 *
 * Translation notes:
 *   - "Token工厂启动器" is the localized form of "Token Factory
 *     Initializr" — the product title in Chinese. "LiteLLM" and
 *     "MAGI" remain in English (third-party / parent-brand names).
 *   - Form labels are kept concise to fit the visual chips.
 */
const zh: TranslationTree = {
  nav: {
    start: "开始",
    browse: "浏览",
    generate: "生成",
  },

  utility: {
    currentLocaleLabel: "中",
    switchLanguageAria: "切换语言(当前: {name})",
    switchLanguageTitle: "语言",
    switchThemeAria: "切换主题(当前: {name})",
    switchThemeTitle: "切换主题",
    optionEnglish: "English",
    optionChinese: "中文",
  },

  footer: {
    columns: {
      product: "产品",
      resources: "资源",
      community: "社区",
      magi: "MAGI",
    },
    brandCaption: "独立 AI 实验室。AI 基础设施,构建在边缘。为开发者与 Agent 而生。",
    copyright: "© 2026 MAGI",
    provenance:
      "Endpoint 来源:NVIDIA NIM · AMD Radeon AI · Hugging Face Inference。生成的配置 5 分钟后过期 —— 这是设计如此。",
  },

  home: {
    eyebrow: "Token工厂启动器",
    headline: "初始化你的 token factory。",
    subhead:
      "挑选适合你项目的免费 AI endpoints。我们会生成开箱即用的 LiteLLM 配置。",
    ctaBrowse: "浏览模型 →",
    ctaReset: "重置",
    fields: {
      project: "项目",
      projectPlaceholder: "例:Coding assistant",
      context: "上下文",
      contextMin128k: "128K+",
      contextMin32k: "32K+",
      contextMin8k: "8K+",
      contextMinAny: "任意",
      toolCalling: "工具调用",
      toolCallingYes: "需要",
      toolCallingNo: "不需要",
      vision: "视觉",
      visionYes: "需要",
      visionNo: "不需要",
      cost: "成本",
      costFree: "仅免费",
      costAny: "任意",
      providers: "Provider",
      providersHelper: "勾选要包含的 provider。",
      maxModels: "最多模型数",
      maxModelsHelper: "推荐列表中要包含的模型数量(1–10)。",
    },
    summaryTemplate: (n, m) =>
      `我们会从 ${m} 个 provider 中匹配 ${n} 个模型。`,
  },

  browse: {
    eyebrow: "浏览",
    headingNoReq: "全部 endpoints",
    headingWithReq: "推荐模型",
    loading: "正在加载目录…",
    countNoReqTemplate: (n) =>
      `${n} 个模型匹配当前目录。`,
    countWithReqTemplate: (n) =>
      `${n} 个模型匹配你的需求。`,
    noReqBannerBefore: "尚未设置需求。",
    noReqBannerAfter:
      "返回设置你想构建的内容 —— 我们会为你挑选最合适的模型。",
    emptyBefore: "没有匹配的模型。试着放宽一些条件 —— ",
    emptyAfter: "编辑需求",
    sectionRecommended: "推荐",
    sectionOther: "其他匹配",
    hintRecommendedTemplate: (n) => `前 ${n} 个匹配`,
    hintOther: "匹配 —— 视情况选用",
    /** Template: "{n} selected" — bottom-row counter on Browse page. */
    selectedCountTemplate: (n: number) => `已选 ${n} 个`,
    fallbackPrefix: "无法加载 KV 目录:",
    fallbackFixture: "回退到内置 fixtures。",
    fallbackHelp: "设置 TFI_USE_LOCAL_FIXTURES=1 以离线浏览。",
  },

  generate: {
    eyebrow: "生成",
    headline: "Token工厂启动器",
    subheadNoSelection: "尚未选择模型。",
    subheadWithSelectionTemplate: (n) =>
      `${n} 个模型已就绪,可以生成配置。`,
    emptyBefore: "尚未选择。先到 ",
    emptyForm: " 填写需求,",
    emptyBrowse: " 浏览并勾选模型。",
    selectionHeader: "已选模型",
    fieldModel: "模型",
    fieldProvider: "Provider",
    fieldId: "ID",
    fieldFormat: "格式",
    optionLitellm: "LiteLLM",
    btnInitialize: "生成配置",
    btnInitializing: "生成中…",
    emptyClick: "点击「生成配置」以生成配置。",
    yamlReady: "就绪",
    yamlCopy: "复制",
    yamlCopied: "已复制",
    yamlDownload: "下载",
    yamlAgentPrompt: "Agent Prompt",
    fieldUrl: "URL",
    fieldTtl: "TTL",
    ttlValue: "5 分钟后过期 —— 这是设计如此",
  },

  initializr: {
    pickerHeading: "Token Factory",
    pickerDescription:
      "选择运行这些模型的网关。TFI 会生成它能识别的配置。",
    selectionCountTemplate: (n: number) => `已选 ${n} 个模型`,
    validation: {
      noModels:
        "尚未选择模型。先到「浏览」勾选模型,再回来选择 Token Factory 并生成配置。",
      noFactory: "请选择一个 Token Factory 以生成配置。",
    },
    errorPrefix: "无法生成配置:",
    formatLabelTemplate: (factoryName: string) => `${factoryName} 配置`,
    factories: {
      litellm: {
        name: "LiteLLM",
        description:
          "开源 Python SDK + 代理,统一 100+ LLM API,提供 OpenAI 兼容接口。",
      },
      newapi: {
        name: "NewAPI",
        description:
          "可自托管的 LLM 网关(one-api 兼容),在单一端点后汇聚多家上游 provider。",
      },
    },
  },
};

export default zh;