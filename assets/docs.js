const SRC = "./content/README.md";

function slug(text) {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\w\u4e00-\u9fff]+/g, "-")
    .replace(/^-|-$/g, "");
}

function renderMarkdown(md) {
  if (window.marked) {
    window.marked.setOptions({ gfm: true, breaks: false });
    return window.marked.parse(md);
  }
  return `<pre>${md.replace(/[&<>]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[c]))}</pre>`;
}

function decorate(root) {
  const toc = document.getElementById("toc");
  toc.replaceChildren();
  root.querySelectorAll("h2, h3").forEach((h) => {
    const id = slug(h.textContent);
    h.id = id;
    const a = document.createElement("a");
    a.href = `#${id}`;
    a.textContent = h.textContent;
    a.className = h.tagName === "H3" ? "h3" : "h2";
    toc.appendChild(a);
  });
}

function watchHeadings() {
  const links = [...document.querySelectorAll("#toc a")];
  const map = new Map(
    links.map((a) => [a.getAttribute("href").slice(1), a])
  );
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        links.forEach((l) => l.classList.remove("active"));
        map.get(e.target.id)?.classList.add("active");
      }
    },
    { rootMargin: "-20% 0px -70% 0px", threshold: 0 }
  );
  document.querySelectorAll(".prose h2, .prose h3").forEach((h) => io.observe(h));
}

async function main() {
  const prose = document.getElementById("prose");
  try {
    const res = await fetch(SRC);
    if (!res.ok) throw new Error(String(res.status));
    prose.innerHTML = renderMarkdown(await res.text());
    decorate(prose);
    watchHeadings();
    if (location.hash) {
      document.getElementById(location.hash.slice(1))?.scrollIntoView();
    }
  } catch (err) {
    prose.innerHTML = `<p class="err">文档加载失败（${err.message}）。请用本地 HTTP 服务打开本站，不要用 file://。</p>
      <p><a href="${SRC}">直接打开 Markdown</a></p>`;
  }
}

main();
