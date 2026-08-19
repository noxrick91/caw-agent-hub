const LANGS = ["zh", "en"];
const I18N = {
  zh: {
    meta: {
      title: "Cawki — 终端里的编程助手",
      desc: "在终端里读代码、改文件、跑测试。默认在写入文件或执行命令前请求确认，支持多模型、MCP、会话与自动化。",
      docsTitle: "文档 — Cawki",
      docsDesc: "安装、升级、斜杠命令、权限，以及无头模式。",
    },
    nav: { home: "首页", download: "下载", docs: "文档", github: "GitHub" },
    hero: {
      kicker: "你的终端里",
      title: "多了一个\n会改代码的搭档",
      lede: "在终端里读代码、改文件、跑测试。文件操作默认限制在工作区，写入或执行命令前默认请求你的确认。",
      install: "立即安装",
      quickStart: "快速开始",
      manual: "手动下载",
      downloading: "加载中…",
      docs: "文档",
      waiting: "正在加载最新版",
    },
    install: {
      unix: "Linux / macOS",
      linux: "Linux",
      mac: "macOS",
      win: "Windows",
      copy: "复制",
      copied: "已复制",
    },
    howto: {
      install: "安装",
      update: "更新",
      uninstall: "卸载",
      docs: "安装说明",
      installHint: "装到 ~/.cawki/bin。装完请新开一个终端。",
      updateHint: "重新下载最新包。先关掉正在跑的 Cawki，装完请新开终端再看版本。",
      uninstallHint: "删掉安装目录，配置和密钥会一起去掉。",
      macUnavailable: "macOS 预编译包暂未开放",
      macHint: "当前公开版本仅提供 Linux 与 Windows 安装包。",
    },
    proof: {
      checksum: "安装器自动校验下载文件",
      platformsT: "跨平台",
      platforms: "Linux 与 Windows，支持 x64 / ARM64",
      modelsT: "模型自由",
      models: "云端 API、兼容网关或本地 Ollama",
    },
    sec: {
      install: "安装",
      howto: "安装",
      why: "为什么用它",
      download: "手动下载",
    },
    cards: {
      capT: "动手干活",
      cap: "它在你的项目里读代码、改文件、跑测试。不只是聊天，是真正干活的搭档。",
      safeT: "安全可控",
      safe: "文件工具默认限制在工作区；写入和命令默认先询问。权限可以按项目收紧或放宽。",
      seeT: "过程透明",
      see: "读、改、跑，每一步都实时显示在眼前。想介入或叫停，随时都可以。",
      modelT: "选择你的模型",
      model: "支持 OpenAI、Anthropic、DeepSeek、Qwen、OpenAI 兼容网关和本地 Ollama。",
      extendT: "连接更多工具",
      extend: "通过 MCP 和技能接入浏览器、文档、图像、CAD，以及你自己的工具链。",
      automateT: "交互与自动化",
      automate: "既能在 TUI 里协作，也支持 headless、结构化输出和本地 REST / SSE。",
    },
    docs: {
      loading: "正在加载文档…",
      fail: "文档加载失败。请用本地 HTTP 服务打开，不要用 file://。",
      toc: "目录",
      onpage: "本页目录",
      search: "搜索文档…",
      searchTitle: "搜索文档",
      product: "Cawki",
      prev: "上一页",
      next: "下一页",
      nohits: "没有匹配的页面。",
      contents: "目录",
    },
    table: {
      platform: "平台",
      build: "版本",
      size: "大小",
      this: "本版",
      total: "累计",
      here: "本机",
      checksum: "校验和",
      caption: "各平台最新版本下载",
      loading: "加载中…",
      stats: (a, b, n) => `本版 ${a} 次，一共 ${b} 次 · ${n} 个版本`,
      meta: (tag, label, date, a, b) =>
        `${tag} · ${label}${date ? ` · ${date}` : ""}`,
    },
    dl: {
      prefix: "下载",
      unavailable: "暂无可用版本",
      error: "最新版暂时读不到，用上面的命令安装即可。",
      releases: "用安装命令",
      unsupported: "macOS 预编译包暂未开放",
    },
    footer: {
      tagline: "Cawki · 让终端真正动手干活",
      docs: "安装文档",
      releases: "Releases",
      changelog: "更新记录",
      feedback: "反馈问题",
    },
    stage: {
      title: "Cawki · ~/ledger",
      sandbox: "sandbox",
      ask: "先询问",
      files: "文件",
      allow: "允许一次",
      deny: "拒绝",
      statusWrite: "写入 src/auth.rs · 等待确认",
      statusOk: "已写入 src/auth.rs",
      statusTest: "运行 cargo test -p ledger -- auth",
      statusPass: "测试通过 · 3 passed",
      placeholder: "输入消息 · @ 文件 · 粘贴 · / 命令",
    },
    notfound: { title: "没有这一页。", back: "回首页" },
  },
  en: {
    meta: {
      title: "Cawki — a coding agent for your terminal",
      desc: "Read code, edit files, and run tests from your terminal. Writes and commands ask by default, with multi-model, MCP, sessions, and automation support.",
      docsTitle: "Docs — Cawki",
      docsDesc: "Install, upgrade, slash commands, permissions, and headless mode.",
    },
    nav: { home: "Home", download: "Download", docs: "Docs", github: "GitHub" },
    hero: {
      kicker: "In your terminal",
      title: "A new partner\nthat edits your code",
      lede: "Read code, edit files, and run tests from your terminal. File tools stay in the workspace by default, and writes or commands ask for your OK by default.",
      install: "Install now",
      quickStart: "Quick start",
      manual: "Manual downloads",
      downloading: "Loading…",
      docs: "Docs",
      waiting: "Loading the latest build",
    },
    install: {
      unix: "Linux / macOS",
      linux: "Linux",
      mac: "macOS",
      win: "Windows",
      copy: "Copy",
      copied: "Copied",
    },
    howto: {
      install: "Install",
      update: "Update",
      uninstall: "Uninstall",
      docs: "Install docs",
      installHint: "Installs into ~/.cawki/bin. Open a new terminal afterwards.",
      updateHint: "Re-downloads the latest build. Close running Cawki first, then open a new terminal to check the version.",
      uninstallHint: "Deletes the install directory, including config and keys.",
      macUnavailable: "macOS prebuilt packages are temporarily unavailable",
      macHint: "The current public release only provides Linux and Windows builds.",
    },
    proof: {
      checksum: "The installer verifies every download",
      platformsT: "Cross-platform",
      platforms: "Linux and Windows on x64 / ARM64",
      modelsT: "Model freedom",
      models: "Cloud APIs, compatible gateways, or local Ollama",
    },
    sec: {
      install: "Install",
      howto: "Install",
      why: "Why use it",
      download: "Manual downloads",
    },
    cards: {
      capT: "Gets things done",
      cap: "It reads code, edits files, and runs tests in your project. Not just a chat companion — a partner that actually gets things done.",
      safeT: "Safe by design",
      safe: "File tools stay in the workspace by default, while writes and commands ask first. Permissions can be tightened or relaxed per project.",
      seeT: "Everything in plain sight",
      see: "Reads, edits, and runs happen live on screen. Jump in or stop it whenever you want.",
      modelT: "Choose your model",
      model: "Works with OpenAI, Anthropic, DeepSeek, Qwen, OpenAI-compatible gateways, and local Ollama.",
      extendT: "Connect more tools",
      extend: "Use MCP and skills for browsers, documents, images, CAD, and your own toolchain.",
      automateT: "Interactive or automated",
      automate: "Collaborate in the TUI, or use headless mode, structured output, and local REST / SSE.",
    },
    docs: {
      loading: "Loading docs…",
      fail: "Could not load the docs. Serve this site over HTTP, not file://.",
      toc: "Contents",
      onpage: "On this page",
      search: "Search the docs…",
      searchTitle: "Search documentation",
      product: "Cawki",
      prev: "Previous",
      next: "Next",
      nohits: "No matching pages.",
      contents: "Contents",
    },
    table: {
      platform: "Platform",
      build: "Version",
      size: "Size",
      this: "This build",
      total: "All time",
      here: "yours",
      checksum: "Checksums",
      caption: "Latest downloads for each platform",
      loading: "Loading…",
      stats: (a, b, n) => `${a} this build · ${b} all time · ${n} versions`,
      meta: (tag, label, date, a, b) =>
        `${tag} · ${label}${date ? ` · ${date}` : ""}`,
    },
    dl: {
      prefix: "Download",
      unavailable: "No build yet",
      error: "Could not load the latest build. Use the install command above.",
      releases: "Use the install command",
      unsupported: "macOS prebuilt packages are temporarily unavailable",
    },
    footer: {
      tagline: "Cawki · put your terminal to work",
      docs: "Install docs",
      releases: "Releases",
      changelog: "Changelog",
      feedback: "Report an issue",
    },
    stage: {
      title: "Cawki · ~/ledger",
      sandbox: "sandbox",
      ask: "ask first",
      files: "files",
      allow: "allow once",
      deny: "deny",
      statusWrite: "write src/auth.rs · waiting",
      statusOk: "wrote src/auth.rs",
      statusTest: "run cargo test -p ledger -- auth",
      statusPass: "tests passed · 3 passed",
      placeholder: "Message · @ file · paste · / commands",
    },
    notfound: { title: "This page is not here.", back: "Home" },
  },
};

let chosenLang = null;

function getLang() {
  if (LANGS.includes(chosenLang)) return chosenLang;
  const q = new URLSearchParams(location.search).get("lang");
  if (LANGS.includes(q)) return q;
  try {
    const saved = localStorage.getItem("caw-lang");
    if (LANGS.includes(saved)) return saved;
  } catch {
    /* ignore */
  }
  return (navigator.language || "").toLowerCase().startsWith("zh") ? "zh" : "en";
}

function dict() {
  return I18N[getLang()] || I18N.zh;
}

function setLang(lang) {
  if (!LANGS.includes(lang)) return;
  chosenLang = lang;
  try {
    localStorage.setItem("caw-lang", lang);
  } catch {
    /* ignore */
  }
  const url = new URL(location.href);
  url.searchParams.set("lang", lang);
  history.replaceState(null, "", url);
  applyI18n();
  document.dispatchEvent(new CustomEvent("caw-lang", { detail: lang }));
}

function applyI18n(root = document) {
  const d = dict();
  document.documentElement.lang = getLang() === "zh" ? "zh-CN" : "en";
  const title = document.querySelector("title");
  if (title && title.dataset.i18nTitle) {
    const key = title.dataset.i18nTitle;
    title.textContent = key === "docs" ? d.meta.docsTitle : d.meta.title;
  }
  const desc = document.querySelector('meta[name="description"]');
  if (desc && desc.dataset.i18nDesc) {
    desc.content = desc.dataset.i18nDesc === "docs" ? d.meta.docsDesc : d.meta.desc;
  }
  root.querySelectorAll("[data-i18n]").forEach((el) => {
    const val = lookup(d, el.getAttribute("data-i18n"));
    if (val != null) el.textContent = val;
  });
  root.querySelectorAll("[data-i18n-html]").forEach((el) => {
    const val = lookup(d, el.getAttribute("data-i18n-html"));
    if (val != null) el.innerHTML = String(val).replace(/\n/g, "<br>");
  });
  root.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
    const val = lookup(d, el.getAttribute("data-i18n-placeholder"));
    if (val != null) el.setAttribute("placeholder", val);
  });
  root.querySelectorAll("[data-lang]").forEach((btn) => {
    btn.setAttribute("aria-pressed", String(btn.getAttribute("data-lang") === getLang()));
  });
  root.querySelectorAll("a[data-keep-lang]").forEach((a) => {
    const href = a.getAttribute("href") || "./";
    const hashAt = href.indexOf("#");
    const hash = hashAt >= 0 ? href.slice(hashAt) : "";
    const before = hashAt >= 0 ? href.slice(0, hashAt) : href;
    const path = before.split("?")[0];
    a.setAttribute("href", `${path}?lang=${getLang()}${hash}`);
  });
}

function lookup(obj, path) {
  return path.split(".").reduce((o, k) => (o == null ? o : o[k]), obj);
}

function bindLangSwitch(root = document) {
  root.querySelectorAll("[data-lang]").forEach((btn) => {
    btn.addEventListener("click", () => setLang(btn.getAttribute("data-lang")));
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applyI18n();
  bindLangSwitch();
});
