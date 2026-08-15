/* Homepage "What's new" — English only, not i18n'd. */
(function () {
  const SRC = "./whats-new.json";

  function injectStyle() {
    if (document.getElementById("whats-new-style")) return;
    const s = document.createElement("style");
    s.id = "whats-new-style";
    s.textContent = `
      #whats-new[hidden] { display: none; }
      #whats-new:not([hidden]) { display: block; }
      .whats-new-panel { margin: 0 0 8px; }
      .whats-new-panel ul {
        margin: 0;
        padding: 16px 16px 8px 36px;
        color: var(--ivory, #f3efe6);
        font-size: 14px;
        line-height: 1.55;
      }
      .whats-new-panel li { margin: 0 0 8px; }
      .whats-new-panel .meta {
        padding: 0 16px 16px;
        margin: 0;
      }
      .whats-new-panel .meta a { color: var(--egg, #e8c872); }
    `;
    document.head.appendChild(s);
  }

  function mount() {
    let el = document.getElementById("whats-new");
    if (el) return el;
    el = document.createElement("section");
    el.id = "whats-new";
    el.className = "whats-new";
    const install = document.getElementById("install");
    const after = install && (install.closest(".panel") || install);
    if (after && after.parentNode) {
      after.insertAdjacentElement("afterend", el);
      return el;
    }
    const why = [...document.querySelectorAll(".sec")].find((n) =>
      /为什么|Why/.test(n.textContent || "")
    );
    if (why && why.parentNode) {
      why.parentNode.insertBefore(el, why);
      return el;
    }
    const wrap = document.querySelectorAll(".wrap")[1] || document.querySelector(".wrap");
    if (wrap) wrap.appendChild(el);
    else document.body.appendChild(el);
    return el;
  }

  function render(data) {
    const notes = Array.isArray(data.notes) ? data.notes.filter(Boolean) : [];
    if (!notes.length && !data.body) return;
    injectStyle();
    const el = mount();
    const h = document.createElement("h2");
    h.className = "sec";
    h.textContent = data.title || "What's new";
    const panel = document.createElement("div");
    panel.className = "panel whats-new-panel";
    const ul = document.createElement("ul");
    (notes.length ? notes : [data.body]).slice(0, 10).forEach((n) => {
      const li = document.createElement("li");
      li.textContent = n;
      ul.appendChild(li);
    });
    const more = document.createElement("p");
    more.className = "meta";
    const log = document.createElement("a");
    log.href = data.url || "./CHANGELOG.md";
    log.textContent = "Full changelog";
    const sep = document.createTextNode(" · ");
    const docs = document.createElement("a");
    docs.setAttribute("data-keep-lang", "");
    docs.href = "./docs.html#/whats-new";
    docs.textContent = "Release notes";
    if (typeof applyI18n === "function") applyI18n(more);
    more.append(log, sep, docs);
    panel.append(ul, more);
    el.replaceChildren(h, panel);
    el.hidden = false;
    el.removeAttribute("hidden");
  }

  fetch(SRC, { cache: "no-cache" })
    .then((res) => (res.ok ? res.json() : null))
    .then((data) => {
      if (data) render(data);
    })
    .catch(() => {});
})();
