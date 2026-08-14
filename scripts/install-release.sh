#!/usr/bin/env bash
# caw-agent one-line installer.
#   curl -fsS https://agent.noxcaw.com/install | bash
#   curl -fsS https://agent.noxcaw.com/install | bash -s -- v0.1.1
# Env: CAW_TAG  CAW_GITHUB  PREFIX  BIN_DIR  GH_TOKEN  CAW_GITHUB_TOKEN  NO_COLOR
set -euo pipefail

REPO="${CAW_GITHUB:-noxrick91/caw-agent-hub}"
PREFIX="${PREFIX:-${HOME}/.caw-agent}"
BIN_DIR="${BIN_DIR:-${PREFIX}/bin}"
TAG="${CAW_TAG:-latest}"

if [ -n "${NO_COLOR:-}" ] || [ ! -t 1 ]; then
  C0="" C1="" C2="" C3="" CD=""
else
  C0=$'\033[0m'
  C1=$'\033[1m'
  C2=$'\033[32m'
  C3=$'\033[31m'
  CD=$'\033[2m'
fi

step() { printf '%s▸%s %s\n' "$CD" "$C0" "$1"; }
ok() { printf '%s✓%s %s\n' "$C2" "$C0" "$1"; }
die() { printf '%s✗%s %s\n' "$C3" "$C0" "$1" >&2; exit 1; }

if [ $# -gt 1 ]; then
  die "Usage: install [latest|now|vX.Y.Z]"
fi
if [ $# -eq 1 ]; then
  TAG="$1"
fi
case "${TAG}" in
  latest | now) TAG="latest" ;;
  v*) ;;
  [0-9]*) TAG="v${TAG}" ;;
  *) die "invalid version \`${TAG}\` (want latest|now|vX.Y.Z)" ;;
esac

command -v curl >/dev/null 2>&1 || die "missing curl"
command -v uname >/dev/null 2>&1 || die "missing uname"

printf '\n%s caw-agent installer%s\n\n' "$C1" "$C0"

step "Detecting platform…"
os="$(uname -s | tr '[:upper:]' '[:lower:]')"
arch="$(uname -m)"
bin_name="caw-agent"
case "${os}-${arch}" in
  linux-x86_64 | linux-amd64)
    asset="caw-agent-x86_64-unknown-linux-gnu"
    ;;
  linux-aarch64 | linux-arm64)
    asset="caw-agent-aarch64-unknown-linux-gnu"
    ;;
  darwin-arm64)
    asset="caw-agent-aarch64-apple-darwin"
    ;;
  darwin-x86_64)
    asset="caw-agent-x86_64-apple-darwin"
    ;;
  mingw* | msys* | cygwin* | windows*)
    asset="caw-agent-x86_64-pc-windows-msvc.exe"
    bin_name="caw-agent.exe"
    ;;
  *)
    die "unsupported platform ${os}-${arch}. See https://github.com/${REPO}/releases"
    ;;
esac
ok "Detected ${os}/${arch} → ${asset}"

dest="${BIN_DIR}/${bin_name}"
if [ -x "${dest}" ] && [ "${TAG}" = "latest" ]; then
  step "Existing install found — running caw-agent upgrade now"
  exec "${dest}" upgrade now
fi

if [ "${TAG}" = "latest" ]; then
  base="https://github.com/${REPO}/releases/latest/download"
else
  base="https://github.com/${REPO}/releases/download/${TAG}"
fi

auth=()
token="${CAW_GITHUB_TOKEN:-${GH_TOKEN:-}}"
if [ -n "${token}" ]; then
  auth=(-H "Authorization: Bearer ${token}")
fi

download() {
  local url="$1" out="$2" label="$3"
  step "${label}"
  local code
  code="$(curl -L --progress-bar "${auth[@]}" -o "${out}" -w "%{http_code}" "${url}" || true)"
  if [ "${code}" = "404" ]; then
    die "not found: ${url}
  no public Release yet — https://github.com/${REPO}/releases"
  fi
  if [ "${code}" = "403" ] || [ "${code}" = "429" ]; then
    die "GitHub HTTP ${code}. Set GH_TOKEN or CAW_GITHUB_TOKEN and retry."
  fi
  if [ "${code}" != "200" ]; then
    die "HTTP ${code} for ${url}"
  fi
}

sha256_of() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  else
    die "missing sha256sum/shasum"
  fi
}

tmp="$(mktemp -d)"
cleanup() { rm -rf "${tmp}"; }
trap cleanup EXIT

mkdir -p "${BIN_DIR}"
download "${base}/SHA256SUMS" "${tmp}/SHA256SUMS" "Fetching SHA256SUMS…"
download "${base}/${asset}" "${tmp}/${asset}" "Downloading ${asset}…"

expect="$(awk -v a="${asset}" '$NF==a || $NF=="*"a {print $1; exit}' "${tmp}/SHA256SUMS")"
[ -n "${expect}" ] || die "SHA256SUMS has no entry for ${asset}"
got="$(sha256_of "${tmp}/${asset}")"
if [ "${expect}" != "${got}" ]; then
  die "SHA256 mismatch for ${asset}
  expected ${expect}
  got      ${got}"
fi
ok "Checksum verified"

if [ -e "${dest}" ]; then
  cp -f "${dest}" "${dest}.bak" 2>/dev/null || true
fi
chmod +x "${tmp}/${asset}"
mv "${tmp}/${asset}" "${dest}"
ok "Installed ${dest}"

ver="$("${dest}" --version 2>/dev/null || true)"
if [ -n "${ver}" ] && [ "${TAG}" != "latest" ]; then
  expect_ver="${TAG#v}"
  ver_num="${ver##* }"
  ver_num="${ver_num#v}"
  if [ "${ver_num}" != "${expect_ver}" ]; then
    if [ -e "${dest}.bak" ]; then
      mv -f "${dest}.bak" "${dest}"
    fi
    die "${dest} --version is \`${ver}\`, expected ${expect_ver}"
  fi
fi

printf '\n%sInstallation complete.%s\n' "$C1" "$C0"
if [ -n "${ver}" ]; then
  printf '  version  %s\n' "${ver}"
fi
printf '  binary   %s\n' "${dest}"
printf '  sha256   %s\n' "${got}"

case ":${PATH}:" in
  *":${BIN_DIR}:"*) ;;
  *)
    printf '\n%sAdd to PATH:%s\n' "$C1" "$C0"
    printf '  echo '\''export PATH="%s:$PATH"'\'' >> ~/.bashrc && source ~/.bashrc\n' "${BIN_DIR}"
    if [ -f "${HOME}/.zshrc" ]; then
      printf '  echo '\''export PATH="%s:$PATH"'\'' >> ~/.zshrc && source ~/.zshrc\n' "${BIN_DIR}"
    fi
    ;;
esac

printf '\n  caw-agent --help\n  caw-agent upgrade --check\n\n'
