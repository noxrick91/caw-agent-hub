const REPO = "noxrick91/caw-agent-hub";
const API = `https://api.github.com/repos/${REPO}/releases?per_page=100`;
const LOCAL_LATEST = "./latest.json";
const CACHE_KEY = "caw-releases-v2";
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

function isReleaseList(data) {
  return Array.isArray(data) && data.length > 0 && data[0] && data[0].tag_name;
}

function cacheReleases(data) {
  try {
    sessionStorage.setItem(CACHE_KEY, JSON.stringify({ at: Date.now(), data }));
  } catch {
    /* ignore quota / private mode */
  }
}

async function loadLocalLatest() {
  const res = await fetch(LOCAL_LATEST, { cache: "no-cache" });
  if (!res.ok) return null;
  const one = await res.json();
  if (!one || !one.tag_name) return null;
  return [one];
}

async function loadGithubReleases() {
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
    if (cached && Date.now() - cached.at < CACHE_MS && isReleaseList(cached.data)) {
      return cached.data;
    }
  } catch {
    /* ignore */
  }
  const res = await fetch(API);
  if (!res.ok) return null;
  const data = await res.json();
  if (!isReleaseList(data)) return null;
  cacheReleases(data);
  return data;
}

function embeddedLatest() {
  const tag = "v0.1.2";
  return [
    {
      tag_name: tag,
      published_at: "2026-08-14T06:47:38Z",
      assets: [
        ...ASSETS.map((a) => ({
          name: a.file,
          size: 0,
          browser_download_url: assetUrl(tag, a.file),
          download_count: 0,
        })),
        {
          name: "SHA256SUMS",
          size: 0,
          browser_download_url: assetUrl(tag, "SHA256SUMS"),
          download_count: 0,
        },
      ],
    },
  ];
}

async function loadRelease() {
  const local = await loadLocalLatest().catch(() => null);
  if (isReleaseList(local)) {
    loadGithubReleases()
      .then((remote) => {
        if (isReleaseList(remote)) renderHome(remote);
      })
      .catch(() => {});
    return local;
  }
  const remote = await loadGithubReleases().catch(() => null);
  if (isReleaseList(remote)) return remote;
  return embeddedLatest();
}

function byName(release, name) {
  return (release.assets || []).find((a) => a.name === name);
}

function fmtCount(n) {
  if (n == null) return "—";
  const loc = (typeof getLang === "function" && getLang() === "zh") ? "zh-CN" : "en-US";
  return n.toLocaleString(loc);
}

function assetDownloads(releases, name) {
  let n = 0;
  for (const r of releases) {
    const a = byName(r, name);
    if (a) n += a.download_count || 0;
  }
  return n;
}

function binaryTotal(releases) {
  const names = new Set(ASSETS.map((a) => a.file));
  let n = 0;
  for (const r of releases) {
    for (const a of r.assets || []) {
      if (names.has(a.name)) n += a.download_count || 0;
    }
  }
  return n;
}

function pickLatest(releases) {
  return (
    releases.find((r) => !r.draft && !r.prerelease) ||
    releases.find((r) => !r.draft) ||
    releases[0]
  );
}

let lastReleases = null;

function claimDynamic(el) {
  if (!el) return;
  el.removeAttribute("data-i18n");
  el.removeAttribute("data-i18n-html");
}

async function renderHome(releases) {
  lastReleases = releases;
  const release = pickLatest(releases);
  if (!release) throw new Error("no releases");
  const tag = release.tag_name || "latest";
  const date = release.published_at
    ? new Date(release.published_at).toLocaleDateString(
        typeof getLang === "function" && getLang() === "en" ? "en-US" : "zh-CN"
      )
    : "";
  const platform = await detectPlatform();
  const rec = ASSETS.find((a) => a.id === platform) || ASSETS[0];
  const recAsset = byName(release, rec.file);
  const sums = byName(release, "SHA256SUMS");

  const d = typeof dict === "function" ? dict() : null;
  const recBtn = document.getElementById("dl-recommended");
  const recMeta = document.getElementById("dl-meta");
  claimDynamic(recBtn);
  claimDynamic(recMeta);
  recBtn.href = recAsset ? recAsset.browser_download_url : assetUrl(tag, rec.file);
  recBtn.textContent = `${(d?.dl?.prefix) || "下载"} ${rec.label}`;
  recBtn.removeAttribute("aria-disabled");
  const latestBin = binaryTotal([release]);
  const allBin = binaryTotal(releases);
  recMeta.textContent = d?.table?.meta
    ? d.table.meta(tag, rec.file, date, fmtCount(latestBin), fmtCount(allBin))
    : `${tag} · ${rec.file}${date ? ` · ${date}` : ""} · ${fmtCount(latestBin)} · ${fmtCount(allBin)}`;
  const stats = document.getElementById("dl-stats");
  if (stats) {
    const versions = releases.filter((r) => !r.draft).length;
    stats.textContent = d?.table?.stats
      ? d.table.stats(fmtCount(latestBin), fmtCount(allBin), versions)
      : `${fmtCount(latestBin)} / ${fmtCount(allBin)} (${versions})`;
  }

  document.getElementById("release-tag").textContent = tag;
  detectedPlatform = platform;
  applyInstall(platform);

  const hereLabel = d?.table?.here || "本机";
  const checksumLabel = d?.table?.checksum || "校验和";
  const body = document.getElementById("asset-rows");
  body.replaceChildren();
  for (const item of ASSETS) {
    const a = byName(release, item.file);
    const tr = document.createElement("tr");
    const href = a ? a.browser_download_url : assetUrl(tag, item.file);
    const size = a && a.size ? `${(a.size / 1024 / 1024).toFixed(1)} MB` : "—";
    const latest = a ? a.download_count || 0 : null;
    const all = assetDownloads(releases, item.file);
    tr.innerHTML = `
      <td>${item.label}${item.id === platform ? ` <span class='meta'>${hereLabel}</span>` : ""}</td>
      <td><a href="${href}">${item.file}</a></td>
      <td class="meta">${size}</td>
      <td class="num">${fmtCount(latest)}</td>
      <td class="num">${fmtCount(all)}</td>`;
    body.appendChild(tr);
  }
  if (sums) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${checksumLabel}</td>
      <td><a href="${sums.browser_download_url}">SHA256SUMS</a></td>
      <td class="meta">—</td>
      <td class="num">${fmtCount(sums.download_count || 0)}</td>
      <td class="num">${fmtCount(assetDownloads(releases, "SHA256SUMS"))}</td>`;
    body.appendChild(tr);
  }

  const notes = document.getElementById("release-notes");
  if (notes && release.body) {
    notes.textContent = release.body.trim().slice(0, 800);
  }
}

function showError(err) {
  const d = typeof dict === "function" ? dict() : null;
  const recBtn = document.getElementById("dl-recommended");
  const recMeta = document.getElementById("dl-meta");
  claimDynamic(recBtn);
  claimDynamic(recMeta);
  recBtn.href = "#install";
  recBtn.textContent = d?.dl?.releases || "用安装命令";
  recBtn.removeAttribute("aria-disabled");
  recMeta.innerHTML =
    `<span class="err">${d?.dl?.error || "暂时读不到 latest。请到 Releases 手动下载。"}</span>`;
}

const INSTALL_UNIX = "curl -fsS https://agent.noxcaw.com/install | bash";
const INSTALL_WIN = "irm https://agent.noxcaw.com/install.ps1 | iex";

function installLabel(platform) {
  const d = typeof dict === "function" ? dict().install : null;
  if (platform === "win-x64") return d?.win || "Windows";
  if (platform === "mac-arm64" || platform === "mac-x64") return d?.mac || "macOS";
  if (platform === "linux-x64" || platform === "linux-arm64") return d?.linux || "Linux";
  return d?.unix || "Linux / macOS";
}

function applyInstall(platform) {
  const win = platform === "win-x64";
  const cmd = document.getElementById("install-cmd");
  if (cmd) cmd.textContent = win ? INSTALL_WIN : INSTALL_UNIX;
  const label = document.getElementById("install-label");
  if (label) label.textContent = installLabel(platform);
}

function bindCopy(btnId, preId) {
  document.getElementById(btnId)?.addEventListener("click", async () => {
    const text = document.getElementById(preId)?.textContent;
    if (!text) return;
    const d = typeof dict === "function" ? dict().install : null;
    try {
      await navigator.clipboard.writeText(text);
      document.getElementById(btnId).textContent = d?.copied || "已复制";
      setTimeout(() => {
        document.getElementById(btnId).textContent = d?.copy || "复制";
      }, 1400);
    } catch {
      /* ignore */
    }
  });
}
bindCopy("copy-install", "install-cmd");

let detectedPlatform = "linux-x64";
detectPlatform().then((p) => {
  detectedPlatform = p;
  applyInstall(p);
});
document.addEventListener("caw-lang", () => {
  applyInstall(detectedPlatform);
  if (lastReleases) renderHome(lastReleases);
});

loadRelease().then(renderHome).catch(showError);
