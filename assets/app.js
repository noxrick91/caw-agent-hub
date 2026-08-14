const REPO = "noxrick91/caw-agent";
const API = `https://api.github.com/repos/${REPO}/releases/latest`;
const CACHE_KEY = "caw-release-latest";
const CACHE_MS = 10 * 60 * 1000;

const ASSETS = [
  { id: "linux-x64", label: "Linux x86_64", file: "caw-agent-x86_64-unknown-linux-gnu" },
  { id: "linux-arm64", label: "Linux aarch64", file: "caw-agent-aarch64-unknown-linux-gnu" },
  { id: "mac-arm64", label: "macOS Apple Silicon", file: "caw-agent-aarch64-apple-darwin" },
  { id: "mac-x64", label: "macOS Intel", file: "caw-agent-x86_64-apple-darwin" },
  { id: "win-x64", label: "Windows x64", file: "caw-agent-x86_64-pc-windows-msvc.exe" },
];

async function detectPlatform() {
  const uaData = navigator.userAgentData;
  if (uaData?.getHighEntropyValues) {
    try {
      const extra = await uaData.getHighEntropyValues(["architecture"]);
      const plat = `${uaData.platform || ""} ${extra.architecture || ""}`.toLowerCase();
      const arm = /arm/.test(plat);
      if (/win/.test(plat)) return "win-x64";
      if (/mac/.test(plat)) return arm ? "mac-arm64" : "mac-x64";
      if (/linux/.test(plat)) return arm ? "linux-arm64" : "linux-x64";
    } catch {
      /* fall through */
    }
  }
  const ua = navigator.userAgent;
  const plat = navigator.platform || "";
  const isWin = /Win/i.test(plat) || /Windows/i.test(ua);
  const isMac = /Mac/i.test(plat) || /Mac OS/i.test(ua);
  const isLinux = /Linux/i.test(plat) || /Linux/i.test(ua);
  const isArm = /aarch64|arm64/i.test(ua);
  if (isWin) return "win-x64";
  if (isMac) return isArm ? "mac-arm64" : "mac-arm64";
  if (isLinux) return isArm ? "linux-arm64" : "linux-x64";
  return "linux-x64";
}

function assetUrl(tag, file) {
  return `https://github.com/${REPO}/releases/download/${tag}/${file}`;
}

async function loadRelease() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
    if (cached && Date.now() - cached.at < CACHE_MS) return cached.data;
  } catch {
    /* ignore */
  }
  const res = await fetch(API, {
    headers: { Accept: "application/vnd.github+json" },
  });
  if (!res.ok) throw new Error(`GitHub ${res.status}`);
  const data = await res.json();
  sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
  return data;
}

function byName(release, name) {
  return (release.assets || []).find((a) => a.name === name);
}

async function renderHome(release) {
  const tag = release.tag_name || "latest";
  const date = release.published_at
    ? new Date(release.published_at).toLocaleDateString("zh-CN")
    : "";
  const platform = await detectPlatform();
  const rec = ASSETS.find((a) => a.id === platform) || ASSETS[0];
  const recAsset = byName(release, rec.file);
  const sums = byName(release, "SHA256SUMS");

  const recBtn = document.getElementById("dl-recommended");
  const recMeta = document.getElementById("dl-meta");
  recBtn.href = recAsset ? recAsset.browser_download_url : assetUrl(tag, rec.file);
  recBtn.textContent = `下载 ${rec.label}`;
  recBtn.removeAttribute("aria-disabled");
  recMeta.textContent = `${tag} · ${rec.file}${date ? ` · ${date}` : ""}`;

  document.getElementById("release-tag").textContent = tag;
  document.getElementById("install-cmd").textContent =
    "curl -fsSL https://raw.githubusercontent.com/noxrick91/caw-agent/master/scripts/install-release.sh | bash";

  const body = document.getElementById("asset-rows");
  body.replaceChildren();
  for (const item of ASSETS) {
    const a = byName(release, item.file);
    const tr = document.createElement("tr");
    const href = a ? a.browser_download_url : assetUrl(tag, item.file);
    const size = a ? `${(a.size / 1024 / 1024).toFixed(1)} MB` : "—";
    tr.innerHTML = `
      <td>${item.label}${item.id === platform ? " <span class='meta'>本机</span>" : ""}</td>
      <td><a href="${href}">${item.file}</a></td>
      <td class="meta">${size}</td>`;
    body.appendChild(tr);
  }
  if (sums) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>校验和</td><td><a href="${sums.browser_download_url}">SHA256SUMS</a></td><td class="meta">—</td>`;
    body.appendChild(tr);
  }

  const notes = document.getElementById("release-notes");
  if (notes && release.body) {
    notes.textContent = release.body.trim().slice(0, 800);
  }
}

function showError(err) {
  const recBtn = document.getElementById("dl-recommended");
  recBtn.href = `https://github.com/${REPO}/releases`;
  recBtn.textContent = "打开 GitHub Releases";
  recBtn.removeAttribute("aria-disabled");
  document.getElementById("dl-meta").innerHTML =
    `<span class="err">暂时读不到 latest（${err.message}）。请到 Releases 手动下载。</span>`;
}

document.getElementById("copy-install")?.addEventListener("click", async () => {
  const text = document.getElementById("install-cmd").textContent;
  try {
    await navigator.clipboard.writeText(text);
    document.getElementById("copy-install").textContent = "已复制";
    setTimeout(() => {
      document.getElementById("copy-install").textContent = "复制";
    }, 1400);
  } catch {
    /* ignore */
  }
});

loadRelease().then(renderHome).catch(showError);
