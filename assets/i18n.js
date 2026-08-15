const LANGS = ["zh", "en"];
const I18N = {
  zh: {
    meta: {
      title: "caw-agent",
      desc: "在终端里改代码：你的终端里多了一个会改代码的搭档。读、改、测试都在项目内完成，写盘和命令前先征求你的同意。",
      docsTitle: "文档 — caw-agent",
      docsDesc: "安装、升级、斜杠命令、权限，以及无头模式。",
    },
    nav: { download: "下载", docs: "文档" },
    hero: {
      kicker: "你的终端里",
      title: "多了一个\n会改代码的搭档",
      lede: "读代码、改文件、跑测试，都在你打开的这个项目里完成。每次写盘或执行命令前，它都会停下来等你确认。",
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
    sec: {
      install: "安装",
      why: "为什么用它",
      download: "下载",
    },
    cards: {
      capT: "动手干活",
      cap: "它在你的项目里读代码、改文件、跑测试。不只是聊天，是真正干活的搭档。",
      safeT: "安全可控",
      safe: "它只访问你打开的这个目录。每次写盘、每条命令，都会先停下来征求你的同意。",
      seeT: "过程透明",
      see: "读、改、跑，每一步都实时显示在眼前。想介入或叫停，随时都可以。",
    },
    docs: {
      loading: "正在加载文档…",
      fail: "文档加载失败。请用本地 HTTP 服务打开，不要用 file://。",
      toc: "目录",
      onpage: "本页目录",
      search: "搜索文档…",
      product: "caw-agent",
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
    },
    footer: "",
    stage: {
      title: "caw-agent · ~/ledger",
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
      title: "caw-agent",
      desc: "Edit code in your terminal: your terminal just gained a partner that edits code. Reads, edits, and tests stay inside your project, and every write or command waits for your OK.",
      docsTitle: "Docs — caw-agent",
      docsDesc: "Install, upgrade, slash commands, permissions, and headless mode.",
    },
    nav: { download: "Download", docs: "Docs" },
    hero: {
      kicker: "In your terminal",
      title: "A new partner\nthat edits your code",
      lede: "It reads code, edits files, and runs tests in the project you opened. Before every write or command, it stops and waits for your OK.",
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
    sec: {
      install: "Install",
      why: "Why use it",
      download: "Download",
    },
    cards: {
      capT: "Gets things done",
      cap: "It reads code, edits files, and runs tests in your project. Not just a chat companion — a partner that actually gets things done.",
      safeT: "Safe by design",
      safe: "It only touches the folder you opened. Every write and every command stops and asks for your OK first.",
      seeT: "Everything in plain sight",
      see: "Reads, edits, and runs happen live on screen. Jump in or stop it whenever you want.",
    },
    docs: {
      loading: "Loading docs…",
      fail: "Could not load the docs. Serve this site over HTTP, not file://.",
      toc: "Contents",
      onpage: "On this page",
      search: "Search the docs…",
      product: "caw-agent",
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
    },
    footer: "",
    stage: {
      title: "caw-agent · ~/ledger",
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
    if (btn.getAttribute("data-lang") === getLang()) btn.setAttribute("aria-current", "true");
    else btn.removeAttribute("aria-current");
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
