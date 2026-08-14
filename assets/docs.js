const SRC = "./content/README.md";
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

function lang() {
  return typeof getLang === "function" ? getLang() : "zh";
}

function renderMarkdown(md) {
  if (window.marked) {
    window.marked.setOptions({ gfm: true, breaks: false });
    return window.marked.parse(md);
  }
  return `<pre>${md.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>`;
}

function splitPages(md) {
  const pages = [];
  const intro = md.split(/^## /m)[0].trim();
  if (intro) {
    pages.push({
      title: "介绍",
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

function pageByHash(pages) {
  const raw = decodeURIComponent((location.hash || "").replace(/^#\/?/, ""));
  return pages.find((p) => p.id === raw) || pages.find((p) => p.title === "安装") || pages[1] || pages[0];
}

function flattenNav(nav, pages) {
  const byTitle = new Map(pages.map((p) => [p.title, p]));
  const out = [];
  for (const g of nav.groups) {
    for (const title of g.pages) {
      const p = byTitle.get(title);
      if (p) out.push({ ...p, group: g.title[lang()] || g.title.zh });
    }
  }
  for (const p of pages) {
    if (!out.some((x) => x.id === p.id)) out.push({ ...p, group: "" });
  }
  return out;
}

function renderNav(nav, pages, current) {
  const box = document.getElementById("docs-nav");
  box.replaceChildren();
  const byTitle = new Map(pages.map((p) => [p.title, p]));
  for (const g of nav.groups) {
    const wrap = document.createElement("div");
    wrap.className = "docs-group";
    const h = document.createElement("p");
    h.className = "docs-group-title";
    h.textContent = g.title[lang()] || g.title.zh;
    wrap.append(h);
    for (const title of g.pages) {
      const p = byTitle.get(title);
      if (!p) continue;
      const a = document.createElement("a");
      a.href = `#/${p.id}`;
      a.textContent = p.title;
      if (p.id === current.id) a.className = "active";
      wrap.append(a);
    }
    box.append(wrap);
  }
}

function renderPage(page, ordered) {
  const prose = document.getElementById("prose");
  prose.innerHTML = renderMarkdown(`# ${page.title}\n\n${page.md}`);

  const toc = document.getElementById("toc-list");
  const right = document.getElementById("docs-right");
  toc.replaceChildren();
  prose.querySelectorAll("h2, h3").forEach((h) => {
    const id = slug(h.textContent);
    h.id = id;
    const a = document.createElement("a");
    a.href = `#/${page.id}`;
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
  crumb.innerHTML = page.group
    ? `${page.group} <span class="sep">/</span> <span>${page.title}</span>`
    : `<span>${page.title}</span>`;

  const idx = ordered.findIndex((p) => p.id === page.id);
  const pager = document.getElementById("docs-pager");
  pager.replaceChildren();
  const prev = ordered[idx - 1];
  const next = ordered[idx + 1];
  if (prev) {
    const a = document.createElement("a");
    a.href = `#/${prev.id}`;
    a.innerHTML = `<span class="dir">${t("docs.prev", "上一页")}</span>${prev.title}`;
    pager.append(a);
  } else {
    pager.append(document.createElement("span"));
  }
  if (next) {
    const a = document.createElement("a");
    a.className = "next";
    a.href = `#/${next.id}`;
    a.innerHTML = `<span class="dir">${t("docs.next", "下一页")}</span>${next.title}`;
    pager.append(a);
  }

  document.title = `${page.title} — caw-agent`;
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
    const found = pages.filter((p) => {
      if (!q) return true;
      return (p.title + "\n" + p.md).toLowerCase().includes(q);
    }).slice(0, 12);
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
      a.href = `#/${p.id}`;
      a.innerHTML = `${p.title}<small>${(p.group || "").trim()}</small>`;
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

const state = { pages: [], nav: null, ordered: [] };

function showCurrent() {
  if (!state.ordered.length) return;
  const page = pageByHash(state.ordered);
  renderNav(state.nav, state.pages, page);
  renderPage(page, state.ordered);
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

async function main() {
  const prose = document.getElementById("prose");
  const kbd = document.getElementById("docs-search-kbd");
  if (kbd && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent)) {
    kbd.textContent = "⌘K";
  }
  try {
    const [mdRes, navRes] = await Promise.all([fetch(SRC), fetch(NAV_SRC)]);
    if (!mdRes.ok) throw new Error(String(mdRes.status));
    const md = await mdRes.text();
    state.nav = navRes.ok ? await navRes.json() : { groups: [] };
    state.pages = splitPages(md);
    state.ordered = flattenNav(state.nav, state.pages);
    if (!location.hash) {
      const first = state.ordered.find((p) => p.title === "安装") || state.ordered[0];
      location.hash = `#/${first.id}`;
    }
    showCurrent();
  } catch (err) {
    prose.innerHTML = `<p class="err">${t("docs.fail", "文档加载失败。")}（${err.message}）</p>
      <p><a href="${SRC}">Markdown</a></p>`;
  }
}

window.addEventListener("hashchange", showCurrent);
document.addEventListener("caw-lang", () => {
  state.ordered = flattenNav(state.nav || { groups: [] }, state.pages);
  showCurrent();
});

function bindSearch(id) {
  document.getElementById(id)?.addEventListener("click", () => openSearch(state.ordered));
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
    openSearch(state.ordered);
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
