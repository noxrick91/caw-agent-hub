const SRC_ZH = "./content/README.md";
const SRC_EN = "./content/README.en.md";
const NAV_SRC = "./content/nav.json";

function slug(text) {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]+/g, "-")
    .replace(/^-|-$/g, "");
}

function t(key, fallback) {
  const d = typeof dict === "function" ? dict() : null;
  const val = key.split(".").reduce((o, k) => (o == null ? o : o[k]), d);
  return val != null ? val : fallback;
}

let forcedLang = null;

function lang() {
  if (forcedLang === "zh" || forcedLang === "en") return forcedLang;
  return typeof getLang === "function" ? getLang() : "zh";
}

function renderMarkdown(md) {
  if (window.marked) {
    window.marked.setOptions({ gfm: true, breaks: false });
    return window.marked.parse(md);
  }
  return `<pre>${md.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>`;
}

function navEntry(raw) {
  if (raw && typeof raw === "object") return raw;
  const title = String(raw || "");
  return { key: slug(title), zh: title, en: title };
}

function displayTitle(entry, code = lang()) {
  const e = navEntry(entry);
  return e[code] || e.zh || e.en || e.key;
}

function groupTitle(group, code = lang()) {
  const t = group && group.title;
  if (t && typeof t === "object") return t[code] || t.zh || t.en || "";
  return String(t || "");
}

function liveTitle(page) {
  if (page && page.label) return page.label[lang()] || page.title;
  return page ? page.title : "";
}

function liveGroup(page) {
  if (page && page.groups) return page.groups[lang()] || page.group || "";
  return page ? page.group || "" : "";
}

function splitPages(md, introTitle) {
  const pages = [];
  const intro = md.split(/^## /m)[0].trim();
  if (intro) {
    pages.push({
      title: introTitle,
      md: intro.replace(/^#\s+.+\n+/, ""),
    });
  }
  const rest = md.replace(/^[\s\S]*?(?=^## )/m, "");
  for (const block of rest.split(/^## /m)) {
    const trimmed = block.trim();
    if (!trimmed) continue;
    const nl = trimmed.indexOf("\n");
    const title = (nl === -1 ? trimmed : trimmed.slice(0, nl)).trim();
    const body = nl === -1 ? "" : trimmed.slice(nl + 1).replace(/^---\n+/, "").trim();
    pages.push({ title, md: body });
  }
  return pages.map((p) => ({ ...p, id: slug(p.title) }));
}

function matchPage(pages, entry) {
  const e = navEntry(entry);
  const titles = [e.zh, e.en, e.key].filter(Boolean);
  return (
    pages.find((p) => titles.includes(p.title)) ||
    pages.find((p) => p.id === e.key || p.id === slug(e.zh || "") || p.id === slug(e.en || ""))
  );
}

function aliasMap(nav) {
  const map = Object.create(null);
  const add = (from, key) => {
    if (!from || !key) return;
    map[from] = key;
    map[slug(from)] = key;
  };
  for (const g of nav.groups || []) {
    for (const raw of g.pages || []) {
      const e = navEntry(raw);
      add(e.key, e.key);
      add(e.zh, e.key);
      add(e.en, e.key);
    }
  }
  add("what-s-new", "whats-new");
  add("what's-new", "whats-new");
  return map;
}

function flattenNav(nav, pages, code = lang()) {
  const aliases = aliasMap(nav);
  const out = [];
  const seen = new Set();
  for (const g of nav.groups || []) {
    for (const raw of g.pages || []) {
      const e = navEntry(raw);
      const p = matchPage(pages, e);
      if (!p) continue;
      const key = e.key || p.id;
      out.push({
        ...p,
        key,
        title: displayTitle(e, code),
        label: { zh: e.zh || p.title, en: e.en || p.title },
        group: groupTitle(g, code),
        groups: { zh: groupTitle(g, "zh"), en: groupTitle(g, "en") },
      });
      seen.add(p.id);
      aliases[p.id] = key;
    }
  }
  for (const p of pages) {
    if (seen.has(p.id)) continue;
    out.push({
      ...p,
      key: p.id,
      title: p.title,
      label: { zh: p.title, en: p.title },
      group: "",
      groups: { zh: "", en: "" },
    });
  }
  return { ordered: out, aliases };
}

function pageByHash(ordered, aliases) {
  const raw = decodeURIComponent((location.hash || "").replace(/^#\/?/, ""));
  const key = aliases[raw] || aliases[slug(raw)] || raw;
  return (
    ordered.find((p) => p.key === key || p.id === raw || p.id === key) ||
    ordered.find((p) => p.key === "install") ||
    ordered[1] ||
    ordered[0]
  );
}

function renderNav(nav, ordered, current) {
  const box = document.getElementById("docs-nav");
  box.replaceChildren();
  const byKey = new Map(ordered.map((p) => [p.key, p]));
  for (const g of nav.groups || []) {
    const wrap = document.createElement("div");
    wrap.className = "docs-group";
    const h = document.createElement("p");
    h.className = "docs-group-title";
    h.textContent = groupTitle(g);
    wrap.append(h);
    for (const raw of g.pages || []) {
      const e = navEntry(raw);
      const p = byKey.get(e.key);
      if (!p) continue;
      const a = document.createElement("a");
      a.href = `#/${p.key}`;
      a.textContent = displayTitle(e);
      if (p.key === current.key) a.className = "active";
      wrap.append(a);
    }
    box.append(wrap);
  }
}

function renderPage(page, ordered) {
  const title = liveTitle(page);
  const group = liveGroup(page);
  const prose = document.getElementById("prose");
  prose.innerHTML = renderMarkdown(`# ${title}\n\n${page.md}`);

  const toc = document.getElementById("toc-list");
  const right = document.getElementById("docs-right");
  toc.replaceChildren();
  prose.querySelectorAll("h2, h3").forEach((h) => {
    const id = slug(h.textContent);
    h.id = id;
    const a = document.createElement("a");
    a.href = `#/${page.key}`;
    a.dataset.jump = id;
    a.className = h.tagName === "H3" ? "h3" : "";
    a.textContent = h.textContent;
    a.addEventListener("click", (e) => {
      e.preventDefault();
      document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    });
    toc.append(a);
  });
  right.classList.toggle("empty", !toc.childElementCount);

  const crumb = document.getElementById("docs-crumb");
  crumb.innerHTML = group
    ? `${group} <span class="sep">/</span> <span>${title}</span>`
    : `<span>${title}</span>`;

  const idx = ordered.findIndex((p) => p.key === page.key);
  const pager = document.getElementById("docs-pager");
  pager.replaceChildren();
  const prev = ordered[idx - 1];
  const next = ordered[idx + 1];
  if (prev) {
    const a = document.createElement("a");
    a.href = `#/${prev.key}`;
    a.innerHTML = `<span class="dir">${t("docs.prev", "上一页")}</span>${liveTitle(prev)}`;
    pager.append(a);
  } else {
    pager.append(document.createElement("span"));
  }
  if (next) {
    const a = document.createElement("a");
    a.className = "next";
    a.href = `#/${next.key}`;
    a.innerHTML = `<span class="dir">${t("docs.next", "下一页")}</span>${liveTitle(next)}`;
    pager.append(a);
  }

  document.title = `${title} — caw-agent`;
  watchHeadings();
  window.scrollTo(0, 0);
}

let headingIo = null;
function watchHeadings() {
  headingIo?.disconnect();
  const links = [...document.querySelectorAll("#toc-list a")];
  if (!links.length) return;
  const map = new Map(links.map((a) => [a.dataset.jump, a]));
  headingIo = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((l) => l.classList.remove("active"));
        map.get(e.target.id)?.classList.add("active");
      }
    },
    { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
  );
  document.querySelectorAll(".prose h2, .prose h3").forEach((h) => headingIo.observe(h));
}

function closeSearch() {
  const modal = document.getElementById("docs-modal");
  if (modal) modal.hidden = true;
}

function openSearch(pages) {
  const modal = document.getElementById("docs-modal");
  const input = document.getElementById("docs-search-input");
  const hits = document.getElementById("docs-search-hits");
  modal.hidden = false;
  input.placeholder = t("docs.search", "搜索文档…");
  input.value = "";
  input.focus();

  const render = () => {
    const q = input.value.trim().toLowerCase();
    hits.replaceChildren();
    const found = pages
      .filter((p) => {
        if (!q) return true;
        return (liveTitle(p) + "\n" + p.md).toLowerCase().includes(q);
      })
      .slice(0, 12);
    if (!found.length) {
      const empty = document.createElement("p");
      empty.className = "docs-empty";
      empty.textContent = t("docs.nohits", "没有匹配的页面。");
      hits.append(empty);
      return;
    }
    found.forEach((p, i) => {
      const a = document.createElement("a");
      a.className = "docs-hit" + (i === 0 ? " on" : "");
      a.href = `#/${p.key}`;
      a.innerHTML = `${liveTitle(p)}<small>${liveGroup(p).trim()}</small>`;
      a.addEventListener("click", closeSearch);
      hits.append(a);
    });
  };
  input.oninput = render;
  render();
}

function moveHit(delta) {
  const items = [...document.querySelectorAll(".docs-hit")];
  if (!items.length) return;
  const i = items.findIndex((el) => el.classList.contains("on"));
  const next = items[Math.max(0, Math.min(items.length - 1, (i < 0 ? 0 : i) + delta))];
  items.forEach((el) => el.classList.remove("on"));
  next.classList.add("on");
  next.scrollIntoView({ block: "nearest" });
}

const state = { nav: null, byLang: {}, aliases: {} };

function bundle() {
  return state.byLang[lang()] || state.byLang.zh || { pages: [], ordered: [] };
}

function showCurrent() {
  const { ordered } = bundle();
  if (!ordered.length) return;
  const page = pageByHash(ordered, state.aliases);
  if (page && location.hash !== `#/${page.key}`) {
    history.replaceState(null, "", `${location.pathname}${location.search}#/${page.key}`);
  }
  renderNav(state.nav, ordered, page);
  renderPage(page, ordered);
  closeNav();
}

function closeNav() {
  document.getElementById("docs-side")?.classList.remove("open");
  const back = document.getElementById("docs-backdrop");
  if (back) back.hidden = true;
}

function toggleNav() {
  const side = document.getElementById("docs-side");
  const back = document.getElementById("docs-backdrop");
  if (!side) return;
  const open = !side.classList.contains("open");
  side.classList.toggle("open", open);
  if (back) back.hidden = !open;
}

function buildLang(md, nav, introTitle, code) {
  const pages = splitPages(md, introTitle);
  const { ordered, aliases } = flattenNav(nav, pages, code);
  return { pages, ordered, aliases };
}

async function main() {
  const prose = document.getElementById("prose");
  const kbd = document.getElementById("docs-search-kbd");
  if (kbd && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
    kbd.textContent = "⌘K";
  }
  try {
    const fetchOpts = { cache: "no-store" };
    const [zhRes, enRes, navRes] = await Promise.all([
      fetch(SRC_ZH, fetchOpts),
      fetch(SRC_EN, fetchOpts),
      fetch(NAV_SRC, fetchOpts),
    ]);
    if (!zhRes.ok) throw new Error(String(zhRes.status));
    const zhMd = await zhRes.text();
    const enMd = enRes.ok ? await enRes.text() : zhMd;
    state.nav = navRes.ok ? await navRes.json() : { groups: [] };
    state.byLang.zh = buildLang(zhMd, state.nav, "介绍", "zh");
    state.byLang.en = buildLang(enMd, state.nav, "Introduction", "en");
    state.aliases = { ...state.byLang.zh.aliases, ...state.byLang.en.aliases };
    if (!location.hash) {
      location.hash = "#/install";
    }
    showCurrent();
  } catch (err) {
    prose.innerHTML = `<p class="err">${t("docs.fail", "文档加载失败。")}（${err.message}）</p>
      <p><a href="${SRC_ZH}">Markdown</a></p>`;
  }
}

window.addEventListener("hashchange", showCurrent);
document.addEventListener("caw-lang", (e) => {
  const next = e && e.detail;
  if (next === "zh" || next === "en") forcedLang = next;
  showCurrent();
});

function bindSearch(id) {
  document.getElementById(id)?.addEventListener("click", () => openSearch(bundle().ordered));
}
bindSearch("docs-search-btn");
bindSearch("docs-search-btn-mobile");

document.getElementById("docs-contents-btn")?.addEventListener("click", toggleNav);
document.getElementById("docs-backdrop")?.addEventListener("click", closeNav);
document.getElementById("docs-modal")?.addEventListener("click", (e) => {
  if (e.target.id === "docs-modal") closeSearch();
});
document.addEventListener("keydown", (e) => {
  const modal = document.getElementById("docs-modal");
  const open = modal && !modal.hidden;
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
    e.preventDefault();
    openSearch(bundle().ordered);
  }
  if (!open) return;
  if (e.key === "Escape") closeSearch();
  if (e.key === "ArrowDown") {
    e.preventDefault();
    moveHit(1);
  }
  if (e.key === "ArrowUp") {
    e.preventDefault();
    moveHit(-1);
  }
  if (e.key === "Enter") {
    const hit = document.querySelector(".docs-hit.on");
    if (hit) {
      e.preventDefault();
      hit.click();
    }
  }
});

main();
