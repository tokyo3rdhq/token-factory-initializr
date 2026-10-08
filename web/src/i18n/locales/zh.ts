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
      "挑选适合你项目的免费 AI endpoints，生成 LiteLLM、NewAPI 或 Bifrost 的开箱即用配置。",
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
      reasoning: "推理",
      reasoningYes: "需要",
      reasoningNo: "不限制",
      speech: "语音",
      speechYes: "需要",
      speechNo: "不限制",
      structuredOutput: "结构化输出",
      structuredOutputYes: "需要",
      structuredOutputNo: "不限制",
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
    // ----- Agent Access (docs/tfi_homepage_agent_access.md) -----
    ctaAgent: "我是 Agent",
    agentHeading: "把 TFI 接入你的 AI Agent",
    agentBlurb: "让 AI Agent 读取 TFI 模型目录,并协助你完成 Token Factory 配置。",
    agentCopy: "复制 Prompt",
    agentCopied: "已复制",
    agentReadGuide: "查看 Agent 指南",
    agentClose: "关闭",
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
    /** Shown when the user has tag filters or a non-empty search and
     *  no models match. */
    emptyFiltered: "当前过滤条件下没有匹配的模型 —— 试着取消某个 tag 或清空搜索。",
    /** 每行外部链接的可访问性标签。接收 model_id 以便 i18n 字符串
     *  自由组合 —— 参见 docs/tfi_model_source_url.md §7。 */
    viewSourceLabel: (modelId: string) => `查看 ${modelId} 的源页面`,
    sectionRecommended: "推荐",
    sectionOther: "其他匹配",
    sectionAll: "全部匹配",
    hintRecommendedTemplate: (n: number) => `前 ${n} 个匹配`,
    hintOther: "匹配 —— 视情况选用",
    hintAllTemplate: (n: number) => `共 ${n} 个匹配`,
    countFilteredTemplate: (matching: number, visible: number) =>
      `${visible} 个中匹配 ${matching} 个。`,
    /** 每个 provider 上次采集时间，按当前 locale + 时区格式化。 */
    providerTimestampsSeparator: " · ",
    providerTimestampsTitle: "每个 provider 最近一次成功采集时间",
    /** Browse 页 hero 上每个 provider count badge 的 tooltip。
     *  count 是 pipeline 写入该 provider 的 endpoint 数。 */
    providerCountTitle: (count: number, label: string) =>
      `当前 ${label} 目录中 ${count.toLocaleString("zh-CN")} 个 endpoint`,
    selectAllVisibleTemplate: (n: number) =>
      n === 1 ? "选择 1 个可见模型" : `全选可见 ${n} 个`,
    clearAllTemplate: (n: number) =>
      n === 1 ? "清空 1 个已选" : `清空 ${n} 个已选`,
    tags: {
      chat: { label: "对话", description: "具备对话式对话能力的模型。" },
      vision: { label: "视觉", description: "支持图像输入的模型。" },
      tools: { label: "工具", description: "支持 tool / function calling 的模型。" },
      reasoning: {
        label: "推理",
        description: "具备显式链式思考 / 推理能力的模型。",
      },
      speech: {
        label: "语音",
        description: "可输出语音 / 音频的模型（TTS 或支持音频的对话模型）。",
      },
      structured_output: {
        label: "结构化输出",
        description: "能可靠输出 JSON / 受 schema 约束内容的模型。",
      },
      free: { label: "免费", description: "确认免费的 endpoint。" },
      longCtx: { label: "128K+", description: "上下文窗口 ≥ 128 000 token 的模型。" },
    },
    filters: {
      searchPlaceholder: "按名称、provider、id 搜索",
      reset: "重置筛选",
    },
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
    yamlAgentPromptHelp: "一键复制生成的 URL 以及针对本次选择的 agent prompt。",
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
      bifrost: {
        name: "Bifrost",
        description:
          "高性能 LLM 网关,在 OpenAI 兼容接口背后路由并服务多家上游 provider。",
      },
    },
  },
};

export default zh;