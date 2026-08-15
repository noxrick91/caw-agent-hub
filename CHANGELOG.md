# Changelog

All notable changes to caw-agent are documented here in English.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versions match `crates/caw-agent/Cargo.toml` and Git tags (`vX.Y.Z`).

When cutting a release, move items from `[Unreleased]` into a dated `## [X.Y.Z]`
section before tagging. CI publishes this file to [caw-agent-hub](https://github.com/noxrick91/caw-agent-hub)
and shows the current version on https://agent.noxcaw.com.

## [Unreleased]

### Fixed

- Docs language switch now updates sidebar page titles, crumbs, and pager. Those labels were frozen in the language from the first page load.

## [0.1.8] - 2026-08-15

### Changed

- Code blocks use a deeper well on every theme, with 1-cell side inset and a single row of air under the language header (no extra top/bottom pad).
- Diff cards share that well, use a 1-cell inset, and put one row of air between the path header and hunks. Sign and hunk labels are tighter.
- Tasks / agents chrome headers use a dedicated `chrome_bg` bar so they no longer look like code panels.
- Public docs ship a full English manual. The 中文 / EN control switches sidebar titles, page bodies, and hashes (`#/install` works in both languages; old `#/安装` links still resolve).
- Docs intro now explains what the agent does, where models come from (including third-party gateways), and how to read the manual. The models page has a dedicated gateway section.
- Docs page scrollbars match the site: thin, warm, rounded; sidebars fade until hover.
- Third-party OpenAI-compatible gateways are documented as a separate named provider (`/model add <name> <url> [model]`), not by rewriting official preset URLs.

### Fixed

- `/model key` no longer treats the in-memory keyring mock as a real store. Linux/macOS/Windows now compile a platform backend, and a mock write cannot wipe `~/.caw-agent/secrets.json`. Saving a key also rebinds the client immediately so the next turn does not race the disk write.
- Missing-key errors name the provider's real env var (`OPENROUTER_API_KEY` for OpenRouter, not `OPENAI_API_KEY`). `CAW_API_KEY` is accepted as a last-resort fallback for every provider.
- Native Anthropic Messages API is used only for `api.anthropic.com`. A provider named `anthropic` / `claude` pointed at another host uses `/v1/chat/completions` (typical third-party relays). OpenAI org/project headers are sent only to `api.openai.com`.

## [0.1.7] - 2026-08-15

### Added

- Local model router (`/router`): send simple turns to a fast model and harder work to a stronger one (`heuristic`, `hybrid`, or `llm` classifier; pin / unpin a provider).
- `caw-agent serve`: localhost REST/SSE control plane (`127.0.0.1:4150`) for health, models, sessions, prompt, and cancel. Non-loopback listen requires `--token` or `CAW_SERVE_TOKEN`.
- Infra tools: `db` (sqlite / postgres / mysql), `docker` (compose-aware), `ssh` (allowlisted hosts), `cloud` (`aws` / `gcloud` / `az` / `kubectl`).
- Hugging Face tool (`hf`): whoami, download, upload, repo create, cache scan/rm. Tokens stay in `HF_TOKEN` / `hf auth login`.
- Broader GitHub tool (`gh`): issues, releases, workflow runs, and `repo_view`, in addition to PR inspect/create/comment. Still no merge, close, delete, force-push, or raw `gh api`.
- Tasks and agents chrome above the prompt: independent expand/collapse, content-sized height, shared scrollbars, newest-first agents, top-to-bottom todos.
- Verify gate after writes, hung-watch for stuck tools, and clearer todo ownership (the model writes the list; the agent marks items done with `todo_complete`).

### Changed

- `/help` and `caw-agent --help` document serve, router, tasks/agents chrome, and the newer tools.
- Public usage manual on caw-agent-hub covers the same surface.
- Terminal image thumbs use half-block pixels (Linux/macOS) and a larger default size so screenshots stay readable.

### Fixed

- The plan ready sheet body scrolls (PageUp/PageDown, wheel, Alt+↑↓) so long plans are no longer clipped.

## [0.1.6] - 2026-08-15

### Fixed

- Ollama works without an API key.
- An empty `config.json` no longer blocks startup.

## [0.1.5] - 2026-08-15

### Added

- Windows ARM64 install assets (`caw-agent-aarch64-pc-windows-msvc.exe`). The installer falls back to x64 when the native build is missing.
- Live Ollama model picker in `/model`.

## [0.1.4] - 2026-08-14

### Changed

- Installer writes `~/.caw-agent/bin` into the shell rc and `~/.caw-agent/env`.
- `--help` and `/help` document upgrade, rewind, and independent MCP catalog checks.

## [0.1.3] - 2026-08-14

### Added

- Upgrade checks hub MCP packs even when the binary is already current.
- `/mcp list` shows catalog install status (not installed / installed / update available).

### Changed

- Rewind records more file operations so conversation restore and on-disk files stay aligned.

### Removed

- Local LoRA trainer (`/train`). Session export remains; training is no longer built in.

## [0.1.2] - 2026-08-14

### Added

- Official MCP packs install from the public hub (`/mcp install <name>`).
- One-line installer and upgrade default to `noxrick91/caw-agent-hub` releases.

### Changed

- Owner/repo zipballs stay inside the extract root.

## [0.1.1] - 2026-08-14

### Fixed

- macOS ScreenCaptureKit builds with objc2 0.6 (retained SCK objects are no longer treated as `Send`).

### Changed

- Release jobs restore rust-cache from `master` instead of reusing tag caches.

## [0.1.0] - 2026-08-14

First public release.

### Added

- Sandboxed TUI coding agent with permission broker, MCP, and sessions.
- Git worktree isolation for subagent tasks.
- First-class `gh`, browser MCP, and Anthropic Messages API support.
- Session cost tracking and redacted export.
- Git stash and conflict helpers.
- SHA256-verified upgrade from GitHub Releases.
