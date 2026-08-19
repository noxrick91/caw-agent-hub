# Cawki user guide

Cawki is a coding partner that lives in your terminal. It reads code, edits files, and runs tests in the current workspace. File tools stay in the workspace by default; writes and commands ask by default, and permissions can be tightened or relaxed per project. The UI provides a permission broker, sandbox, MCP, sessions, and memory.

Prebuilt binaries install from this site’s [GitHub Releases](https://github.com/noxrick91/cawki-hub/releases) into `~/.cawki/bin`. The source repo is private.

### What it does

- Keeps file tools in the workspace by default; every read, edit, and run shows up in the terminal
- Asks before writing files or running commands; you can tighten or loosen permissions per project
- Remembers project habits across sessions; MCP servers and skills plug in when you need them
- Works with official APIs, local Ollama, and third-party OpenAI-compatible gateways

### Where models come from

Official providers are `/model add <preset>` — `openai`, `anthropic`, `deepseek`, `qwen`, and the others in the menu. Local models are `/model add ollama`; no cloud key.

Relays (NewAPI, OneAPI, and other “OpenAI-compatible” hosts) should **not** overwrite an official preset URL. Add a separate named provider with the gateway’s base URL, key, and model id. See [Models and keys](#/models).

### How to read this guide

Start with [Install](#/install) and [Quick start](#/quick-start). Slash commands, permissions, sessions, and MCP come later. The **中文 / EN** control switches the whole manual and keeps you on the same page.

---

## What's new

This page lists changes in the **current public release**.

**What's new in v0.1.19** — 2026-08-19

- Published the complete Cawki distribution under the `cawki` command, package, release-asset, data-directory, and Hub names.
- Serialized Windows ARM64 SDK downloads and added visible heartbeats, hard timeouts, and cache-preserving retries for the China-hosted release runner.

Full history: [CHANGELOG.md](./CHANGELOG.md).

## Install

### One-line install

Linux / macOS / Git Bash:

```bash
curl -fsS https://agent.noxcaw.com/install | bash
```

Pin a version:

```bash
curl -fsS https://agent.noxcaw.com/install | bash -s -- v0.1.1
# or
CAW_TAG=v0.1.1 curl -fsS https://agent.noxcaw.com/install | bash
```

Windows PowerShell:

```powershell
irm https://agent.noxcaw.com/install.txt | iex
```

Do not use `irm …/install.ps1`: GitHub Pages serves `.ps1` as `application/octet-stream`, and Windows PowerShell 5.1 `irm` cannot treat that as a script. `.txt` is `text/plain`. To fetch the `.ps1` file anyway:

```powershell
iex ((New-Object Net.WebClient).DownloadString('https://agent.noxcaw.com/install.ps1'))
```

The script picks the asset for your OS/ARCH (Linux x64/arm64 or Windows x64/ARM64), checks `SHA256SUMS` from the same Release, and installs into `~/.cawki/bin`. Windows ARM64 prefers the native build and falls back to x64 emulation for older Releases without an ARM64 asset. macOS prebuilt packages are temporarily unavailable. Running the installer again re-downloads and replaces the current file (on Windows it renames a running exe to `.bak` first). The installer writes `~/.cawki/env` and adds a hook in `.bashrc` / `.zshrc` / `.bash_profile` / fish `config.fish`, then `source`s that env. `curl | bash` cannot update the shell you already have open — open a new terminal, or run `source ~/.cawki/env`. Set `CAW_NO_PATH=1` to skip the rc hook.

If Pages is not live yet:

```bash
curl -fsS https://raw.githubusercontent.com/noxrick91/cawki-hub/master/install | bash
```

```powershell
irm https://raw.githubusercontent.com/noxrick91/cawki-hub/master/install.ps1 | iex
```

### Website / manual download

Open the homepage, download the latest asset for your platform, put it in `~/.cawki/bin` (Windows: `%USERPROFILE%\.cawki\bin\cawki.exe`), and check `SHA256SUMS`. The homepage “this build / all time” counts come from each GitHub Release asset’s `download_count`: one-line install, `cawki upgrade`, and browser downloads all increment it. Fetching the `install` script from Pages does not; `SHA256SUMS` is counted separately (each install downloads the checksum file first). `upgrade --check` only hits the API.

| Platform | Asset |
|----------|--------|
| Linux x86_64 | `cawki-x86_64-unknown-linux-gnu` |
| Linux aarch64 | `cawki-aarch64-unknown-linux-gnu` |
| Windows x64 | `cawki-x86_64-pc-windows-gnu.exe` |
| Windows ARM64 | `cawki-aarch64-pc-windows-msvc.exe` |

Unsupported combos (Linux musl, 32-bit Windows) have no prebuilt — build from source.

### Upgrade after install

A bare command **only checks**; it does not download:

```text
/upgrade
cawki upgrade
cawki upgrade --check
```

Install latest (only when newer than the current binary):

```text
/upgrade now
cawki upgrade now
```

Pin a tag (can install an older build):

```text
/upgrade v0.1.1
cawki upgrade v0.1.1
```

Downloads show bytes and percent, verify SHA256, then run `--version`. A mismatch restores the `.bak`. Default hub is `noxrick91/cawki-hub`. Override with `CAW_GITHUB=owner/name`.

On Windows the installer renames a running `cawki.exe` to `.bak` and then writes the new file. If the rename fails, it writes beside the exe and asks you to close every window. Open a new terminal and run `cawki --version`. If PATH still points at another copy, use `%USERPROFILE%\.cawki\bin\cawki.exe`.

### Uninstall

There is no separate uninstaller. Delete the install directory; that also removes config, keys, and MCP packs:

```bash
rm -rf ~/.cawki
```

```powershell
Remove-Item -Recurse -Force $HOME\.cawki
```

Then clean PATH by hand: on Linux / macOS remove the `# >>> cawki >>>` … `# <<< cawki <<<` block from `.bashrc` / `.zshrc` / `.bash_profile` / fish `config.fish`; on Windows remove `%USERPROFILE%\.cawki\bin` from the user PATH. Per-project `.cawki/` folders are left alone.

### Install from source

The source repo is not public. Developers with access, in the private `cawki` repo:

```bash
./scripts/install.sh          # cargo install → ~/.cawki/bin
cargo run -p cawki -- --workdir .
```

**Linux build deps:** `pkg-config`, `libxcb1-dev`, `libxrandr-dev` (X11 screenshots). Wayland screenshots prefer `grim`; computer-use prefers `ydotool`.

**Windows:** MSVC. Native Windows has **no** exec OS jail — use WSL2 for sandboxed `run`.

**macOS:** screenshot / computer-use need Screen Recording and Accessibility; `cliclick` is recommended.

---

## Quick start

```bash
cawki --workdir .
# short
cawki -w .
```

The first visit to a workspace that has not finished onboarding opens a wizard: pick a theme, confirm the workspace. Change the theme later with `/theme`.

Configure a model (any one):

```text
/model add openai
/model key openai sk-...

/model add anthropic
/model key anthropic sk-ant-...

/model add ollama
```

Or env vars: `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENROUTER_API_KEY` / `CAW_API_KEY`. Local Ollama models **do not** need an API key.

Without a cloud key you can still try the demo heuristics (`read Cargo.toml`, `grep fn `, `git status`).

With several models, `/router` sends simple turns to fast and harder work to default / strong. `/help` lists every slash command.

---

## CLI

```text
cawki [options] [--print prompt…]
cawki upgrade [--check] [now|latest|vX.Y.Z]
cawki rewind
cawki serve [--listen 127.0.0.1:4150] [--token TOKEN] [--workdir DIR]
```

| Option | Meaning |
|--------|---------|
| `-w, --workdir` | Workspace root (default: current directory) |
| `--add-dir` | Extra work directory (repeatable) |
| `--no-mcp` | Do not auto-start MCP |
| `--base-url` / `CAW_BASE_URL` | OpenAI-compatible API |
| `--model` / `CAW_MODEL` | Model id |
| `--api-key` / `CAW_API_KEY` | Key for this process |
| `-c, --continue` | Resume the last session in this workspace (skips the crash prompt) |
| `-r, --resume <id>` | Resume by full UUID or unique prefix (skips the crash prompt) |
| `--permission-mode` | `default` \| `acceptEdits` \| `plan` \| `auto` \| `bypassPermissions` |
| `--dangerously-skip-permissions` | Enter full access |
| `-p, --print` | No TUI; assistant reply on stdout |
| `--output-format` | `text` (default) \| `json` \| `stream-json` |
| `--on-approval` | Permission prompt: `fail` (default, exit 2) \| `deny` \| `allow` |
| `--on-ask` | `AskUserQuestion`: `fail` \| `skip` \| `first` \| `all` |
| `--on-plan` | `ExitPlanMode`: `fail` \| `approve` \| `revise` |
| `--allowed-tools` / `--allowed-tools-file` | Tool globs auto-approved in `--print` |
| `--deny-tools` | Tool globs always denied |
| `--max-turns` | Max LLM rounds in `--print` |
| `-V, --version` | Print `cawki x.y.z` |

`--print` defaults to permission mode **auto** so unattended runs are not stuck on every write. Pass `--permission-mode default` when you want the gate. Network, screen, and MCP still fail closed unless `--dangerously-skip-permissions`.

```bash
cawki --print -w . "summarize this repo"
cawki --print --output-format stream-json --on-approval deny -w . "list public API"
cawki --print --on-ask first --on-plan approve -w . "propose a plan then implement"
cawki --print --continue -w . "keep going"
```

`--print` writes the session under `.cawki/sessions/` (including token totals for `/cost`) and prints a resume id on stderr. Ctrl+C / SIGTERM save first, then exit 130. `--continue` errors if this workspace has no stored session.

### `cawki serve`

Local REST / SSE control plane, default `http://127.0.0.1:4150`. A non-loopback listen requires `--token` or `CAW_SERVE_TOKEN` (`Authorization: Bearer …`).

| Path | Meaning |
|------|---------|
| `GET /v1/health` | Liveness |
| `GET /v1/models` | Configured providers and router |
| `GET /v1/sessions` | Session list |
| `POST /v1/sessions` | New session |
| `GET /v1/sessions/{id}` | Session summary |
| `POST /v1/sessions/{id}/prompt` | Submit a prompt (`{"prompt":"…","stream":true}` for SSE) |
| `POST /v1/sessions/{id}/cancel` | Cancel the in-flight turn |

`--on-approval` / `--on-ask` / `--on-plan` match `--print`. Permission prompts fail closed when nobody is there.

---

## Slash commands

`/help` lists built-in commands. Common ones:

```text
/settings · /config      control panel
/permissions             mode and grant summary
/model                   providers and keys
/router                  pick a model by complexity (on|off|pin|heuristic|hybrid|llm|fast|…)
/theme                   theme (dark light midnight forest ember ocean noir dusk dawn ansi)
/compact [focus]         compact older turns
/context                 context-use estimate
/cost                    estimated spend this session (persisted)
/cost limit <usd>|off    stop before the next LLM call at the cap
/export [md|json] [path] redacted transcript (default .cawki/exports/)
/upgrade [now|vX.Y.Z]    check or install a GitHub Release + hub MCP
/notify on|off           desktop toast when a background tab or --print finishes
/copy [N]                copy the Nth last assistant reply
/diff                    git diff --stat
/goal <cond>|clear       keep going until the condition
/loop [5m] <prompt>      re-queue when idle
/doctor                  dependency and setup checkup
/hooks                   loaded plugin hooks
/btw <q>                 side question (not in the main history; Esc cancels)
/about                   author and pixel animation
/memory                  memory on/off / list / open the folder
/dream                   consolidate memory now
/continue                resume the last session
/load <id>               resume by id
/pause [note]            pause and print a resume id
/new · /clear            new session
/save · /sessions        save / list
/cd [path]               switch workspace (creates the dir if missing)
/add-dir [path]          extra work directory
/rewind                  file checkpoints (undo · last · redo)
/plan [task]             enter plan mode; with a task, start that plan (/plan off leaves)
/debug                   debugger session
/init                    detect the stack and write CAW.md
/skills · /skill <name>  skills
/mcp                     MCP packs (list / install NAME)
/plugin enable|disable   plugins
/worktrees               Task worktree list
/todos [expand|collapse|id] task list · click a row or `/todos <id>` for detail
/agents · /tasks         subagents and background tasks · click a row for detail
/exit                    save and quit (exit / quit work too)
```

Saying quit, leave, or goodbye in any language in chat makes the agent call `exit` — same as `/exit`. To pause without closing the app, use `/pause`.

After an unclean exit (kill, power loss, panic), the next launch asks **continue the last session** or **start a new one**. Choosing continue restores the chat and open todos, then the agent resumes that work immediately. A normal quit or closing the Windows console saves first and clears the lock, so the prompt does not appear. `--continue` / `--resume` restore immediately.

Cycle permission modes with **Shift+Tab** (or **Alt+M** / **Alt+Shift+M**): default → accept edits → plan → auto → full access.

Tasks and agents share a row above the prompt: side by side when both are open and the terminal is wide, stacked when it is narrow. Click a row for that item's detail; click `▾` / `▸` on a title to fold that panel. `Tab` moves keyboard focus between the composer, tasks, and agents; `↑↓` scrolls the focused panel; `← →` switches main / subagent when agents have focus; `Esc` returns to the composer.

---

## Models and keys

The default provider is `openai` → `https://api.openai.com/v1` (`gpt-5.6`).

```text
/model                         open the menu
/model list                    list and key status
/model <name>                  switch a saved provider
/model add openai              official GPT (aliases gpt / chatgpt)
/model add anthropic           native Messages API
/model add deepseek            also qwen, qwen-intl, glm, glm-coding, ollama
/model add myapi https://…/v1 mid    third-party / OpenAI-compatible gateway
/model key openai sk-...       write ~/.cawki/secrets.json (all workspaces)
/model key <provider> clear
/model url https://.../v1
/model name gpt-4o-mini
/model env CAW_API_KEY
/model remove ollama
```

In the menu: Enter switches, → manages, Esc / ← goes back.

### Third-party / OpenAI-compatible gateways

NewAPI, OneAPI, and other “OpenAI-compatible” relays should be a **separate named provider**. Do not rewrite `openai` / `anthropic` preset URLs. Copy three things from the gateway console:

| Field | Where to get it |
|-------|-----------------|
| Base URL | OpenAI-compatible root, usually ending in `/v1` |
| Key | The `sk-…` the gateway issued — not an official Anthropic / OpenAI key |
| Model id | Whatever the provider lists (for example, `gpt-4o` or a provider-prefixed id) |

```text
/model add relay https://your-gateway.example/v1 gpt-4o
/model key relay sk-...
```

Gateway traffic uses `/v1/chat/completions`. The native Messages protocol is used only with its official endpoint; pointing a saved profile at a gateway automatically selects the compatible API. Add OpenRouter with `/model add openrouter` and use `OPENROUTER_API_KEY`.

**Native Messages:** `/v1/messages` is used only with the official endpoint; every other address uses the compatible API. `/chat/completions` gateways are supported, and keys can be configured through an environment variable or `/model key`.

Lookup order (active provider): env (`api_key_env` for that provider — OpenRouter is `OPENROUTER_API_KEY`; `CAW_API_KEY` is a last resort) → optional project `.cawki/secrets.json` → **`~/.cawki/secrets.json`** → inline key in config. When `use_keyring` is true (the global default), the OS keyring is tried first. If the keyring backend is not durable, the key stays in `secrets.json` instead of being wiped by an in-memory mock.

Optional: `OPENAI_ORG_ID`, `OPENAI_PROJECT_ID`.

**Ollama:** after `/model add ollama`, pick a pulled model in the menu. **No API key.** An empty `config.json` does not block startup.

**Router:** `/router on` picks fast / default / strong from turn complexity. Classifier: `heuristic` (rules), `llm` (a short extra call), or `hybrid`. `/router pin` freezes the current `/model`. Set a tier with `/router fast|default|strong [provider] [model]`.

---

## Workspace and home

Each project has its own `.cawki/`; cross-project data lives in `~/.cawki/`.

### `~/.cawki/`

| Path | Use |
|------|-----|
| `config.json` | Global defaults (e.g. theme for new workspaces) |
| `secrets.json` | API keys (`/model key` writes here) |
| `rules/*.md` | Global rules you write |
| `memory/` | Global auto memory (OS / toolchain pitfalls) |
| `hf/` | Default download dir for the `hf` tool |
| `skills/` | Skill overrides (default skills are baked into the binary) |
| `tools/` | Portable installs and winget `--location` |
| `bin/` | Released binaries and shims (prepended to `run` / debug PATH) |
| `downloads/` | Default dir for `download_file` |
| `scoop/` | Isolated Scoop root on Windows |
| `mcp/` | Installed MCP packs |
| `languages.toml` | Extra stack / LSP / debug maps (still the built-in `analyze` / `lsp` / `debug` tools) |

### Project `.cawki/`

| Path | Use |
|------|-----|
| `config.json` | Model, permissions, MCP, `last_session_id`, memory flags |
| `secrets.json` | Optional project key override (do not commit) |
| `memory/` | Project auto memory |
| `sessions/` | Sessions |
| `runtime.lock` | TUI-running marker; used to offer restore after a crash |
| `exports/` | Redacted `/export` transcripts |
| `checkpoints/` | `/rewind` file snapshots |
| `audit.log` | Tool allow/deny audit |
| `input_history.json` | Prompt history |
| `rules/*.md` | Project rules |
| `worktrees/` | Isolated trees for `Task worktree: true` |
| `media/` | Screenshot output (still inside the jail) |
| `plan.md` | Plan-mode draft |
| `languages.toml` | Per-repo language detection overlay (wins over the global file) |

Write project notes in `CAW.md` at the workspace root. Workspace MCP servers may go in `.mcp.json`, but repository config can launch local processes and is not loaded by default; use `/settings mcp-workspace` only after you trust the repository. Add long-tail languages in `languages.toml` — do not install one MCP per language.

`/cd` switches workspace mid-session: saves the old session, loads config / skills / trusted MCP for the new root, rebinds the file jail, and opens a new session id (on-screen chat text stays). You cannot switch during a turn or a permission prompt.

---

## Permissions and sandbox

### Modes

| Mode | Behavior |
|------|----------|
| `default` | Reads may auto-allow; write / exec / MCP / network / screenshot ask |
| `acceptEdits` | File writes and safe filesystem commands auto-pass; MCP / network / other `run` still ask |
| `plan` | Research only. After writing `.cawki/plan.md`, `ExitPlanMode`; architecture plans include diagrams; approve to implement in auto (or ask first). Plan itself is not the startup default |
| `auto` | accept-edits + `analyze` / check-test-lint + git **read-only checks**. Mutating git, bare `make`, network, screen, MCP, and installs still ask |
| `bypassPermissions` (UI: **full access**) | Skip every prompt (including screenshots). Leaving full access clears session grants |

Hard denies (`permissions.deny`, `/settings deny exec:rm *`) apply in every mode, including full access. `/settings clear-grants` clears grants and deny rules.

The first time you enter full access, it confirms and writes `"allow_bypass": true`.

**Full access only skips prompts. It does not turn off the OS jail.**

Permission sheet: `1` / Enter once · `2` this session · `3` write to config · Esc deny.

### File jail

`read_file` / `write_file` / `delete_file` / `list_dir` / `glob` / `grep` / `apply_patch` must land inside the canonicalized workspace. Escaping through intermediate symlinks is denied. `delete_file` only deletes files. `.ipynb` is edited as a cell view.

### OS jail for `run`

| System | Backend | Notes |
|--------|---------|-------|
| Linux / WSL2 | bubblewrap + proxy bridge | Needs `bwrap` + `socat`. Blocks `*.exe` / `/mnt/...` |
| macOS | Seatbelt (`sandbox-exec`) | Built in. Denies `~/.ssh` |
| Native Windows | **Unavailable** (fail closed) | Default `sandbox: false`; use WSL2 |

Defaults: jail **on** (except Windows), exec network **off**, timeout 120s. `/settings sandbox` turns the jail off. Every sandboxed `run` that fails attaches `<sandbox_violations>`. `dangerouslyDisableSandbox: true` is a one-shot escape (`/settings unsandbox`).

Hard blocks include fork-bombs, `rm -rf /`, piping into a shell, and reading or writing `.cawki/secrets.json` / `config.json`.

### Dedicated LSP jail

Language servers persist per workspace and server id, but use a separate OS-jail policy: network is denied and workspace source is read-only by default, while only `.cawki/lsp/<server>/` is writable. Toolchain/package caches are read-only; SSH, cloud credentials, keyrings, and Cawki secrets stay hidden. Changing policy or shutting down terminates the complete server process tree, and the LSP message queue is bounded.

A server defined by project `.cawki/languages.toml` is repository-controlled executable code. Before every new process, Cawki previews the resolved program, arguments, isolation policy, and configuration fingerprint and requires **Start server / Cancel**. Auto, Full access, and remembered grants cannot bypass this boundary. A command or configuration change produces a new fingerprint.

Use `/settings lsp-sandbox` for the jail, `/settings lsp-writes` for full-workspace writes, and `/settings lsp-network` for host networking. Changing any option first stops running servers. Native Windows still has no OS jail, so WSL2 is recommended; workspace-defined servers still require confirmation.

---

## Sessions, memory, and export

| Layer | Path | Who writes | Use |
|-------|------|------------|-----|
| Global rules | `~/.cawki/rules/*.md` | you | Fixed notes for every workspace |
| Global memory | `~/.cawki/memory/` | agent + you | Machine-level pitfalls across repos |
| Project rules | `CAW.md` | you | This repo |
| Project memory | `.cawki/memory/` | agent + you | Architecture, build commands, quirks |
| Session handoff | session JSON `handoff` | `/pause` or a tool | Where you left off |

After a failed recovery with no memory write, the turn end nags once. Two failures in the same turn without reading memory interrupt and ask you to open the index / `debugging.md` first. Idle loops trip a breaker: after the same error enough times, `run` / edit / install stop and you get continue / change approach / change model.

`/dream` consolidates memory with the current LLM. It also runs when `auto_dream_enabled` and writes since the last dream ≥ `auto_dream_min_writes`.

`/cost` reads persisted tokens; resuming a session **does not** reset spend. `/export md|json` writes a redacted transcript and does not change the on-disk session file. Auto-compact prefers `prompt_tokens` from the API, otherwise chars/4.

`/rewind` or **Esc Esc** on an empty prompt opens checkpoints: restore code, chat, or both. It does not undo `run` / MCP / hand edits — use git for those.

If background tasks or unfinished todos are still open, the first `/exit`, Ctrl+C, or in-chat `exit` asks you to confirm.

---

## Tools

| Tool | Meaning | Permission |
|------|---------|------------|
| File read/write / glob / grep / apply_patch | Workspace jail | Read may auto; write asks |
| `run` | Command at the workspace root | Exec + optional OS jail |
| `analyze` | Run checks/tests and parse `file:line` (built-in, not MCP) | Exec |
| `lsp` | Language server: hover / definition / references / symbols / diagnostics (built-in) | First query may launch a process and needs Exec; status / shutdown are reads |
| `debug` | gdb / lldb / cdb / pdb / node / dlv / jdb / … (built-in) | Exec |
| `git_*` | status / diff / log / commit / fetch / pull / push / conflicts / stash | Checks are read-only; mutations need Exec. commits do not add third-party attribution. push never uses `--force` |
| `gh` | PR / issue / release / run / `repo_view`; create and comment | No merge / close / `gh api` |
| `hf` | Hugging Face: whoami / download / upload / cache | Download uses network; upload needs Exec. Token: `HF_TOKEN` |
| `db` | sqlite (workspace path) or postgres / mysql (DSN) | Read-only query; `exec` asks. Non-localhost needs an allowlist |
| `docker` | `ps` / images / logs / build / compose | No `--privileged`. Unsandbox if the jail blocks the socket |
| `ssh` | Allowlisted host `exec` / upload / download | New hosts need approval; no `ssh-copy-id` |
| `cloud` | `aws` / `gcloud` / `az` / `kubectl` | Read-only checks auto; mutations ask. No destroy / login |
| `web_search` / `web_fetch` / `download_file` | Search and download | Network; no localhost / private nets |
| `screenshot` / `computer` | Screenshot and mouse/keyboard | Screen. computer-use is **off** by default; `/settings computer-use` |
| `extract_archive` | zip / tar / gz… | Write |
| `install_program` | Auto-detect host package manager; winget/choco/scoop/apt/dnf/pacman/brew/pip/portable | Every install shows Install / Cancel |
| `Task` | Subagent. `worktree: true` jails to `.cawki/worktrees/<id>/` | — |
| `Worktree` | `list` / `merge` / `abandon` | — |
| `exit` | Leave the process when the user says goodbye or asks to quit (parent only) | Auto |

Under `auto`, git is **check-only**: `git_status` / `git_conflicts` / `git status|diff|log|show` / `git stash list|show`. Rebase still goes through `run`.

Screenshots write inside the jail (default `.cawki/media/`). Full-screen capture tries to hide this terminal. macOS uses ScreenCaptureKit, then CoreGraphics.

Computer-use has a machine-level lock, an app allowlist, and hard denies for password managers / banks. For the browser, `/mcp install browser` — do not click the web with `computer`.

---

## MCP and skills

`.mcp.json` supports stdio or a remote URL (HTTP / SSE):

```json
{
  "mcpServers": {
    "local": { "command": "npx", "args": ["-y", "@modelcontextprotocol/server-filesystem", "."] },
    "remote": { "url": "https://example.com/mcp", "headers": { "Authorization": "Bearer …" } }
  }
}
```

Global installed packs and enabled plugins are user-managed and load normally. A repository's `.mcp.json` is ignored as untrusted by default; enable `/settings mcp-workspace` only for a repository you trust. Turning it off unloads those workspace servers immediately.

Official packs live in the public repo under `mcp/` ([catalog](https://github.com/noxrick91/cawki-hub/tree/master/mcp)): browser, doc, image, ocr, speech, freecad, blender. `/mcp install <name>` downloads from GitHub into `~/.cawki/mcp/<name>/`. Any GitHub pack works: `/mcp install owner/repo` or a repo URL. Workspace `./mcp/<name>`, a folder, or a zip still work. After `/mcp install browser`, use `mcp__browser__*`.

Attached audio is only a path — it is **not** transcribed automatically. Use the speech pack when the user asks.

Default skills are baked in: `review`, `fix`, `commit`, `doctor`, `verify`, `code-review`, `simplify`, `batch`, `pr`. Override with `~/.cawki/skills/` or workspace `skills/`. `/mcp install` copies that pack’s skills into global skills (stamped `.mcp-pack`); uninstall removes only stamped copies.

```text
/skills
/skill review [args]
/review
/plugin enable <name>
```

---

## UI and shortcuts

Multi-tab: each tab has its own turn and queue. `ctrl+t` new tab, `ctrl+tab` switch, `ctrl+w` close. A background tab that finished is marked `•`.

Above the prompt: **tasks / agents**. It appears when there are todos or subagents. Side by side and equal height when both are expanded and the terminal is wide; stacked and content-sized when it is narrow. Click a row for detail (`how` / accept / last check, or the subagent transcript). Click `▾` / `▸` to fold one side. Todos follow document order, top to bottom; agents are newest-first (`main` pinned at the top).

`Tab` cycles keyboard focus across the composer and any expanded tasks / agents panel. With a panel focused, `↑↓` scrolls it and `← →` switches main / sub. Click a tasks or agents row (or `/todos <id>`) for that item's how / accept / last check or live transcript. `/todos expand|collapse` folds tasks. The wheel scrolls the panel under the pointer; `Alt+↑↓` still scrolls the focused region. `/worktrees` manages isolated trees.

While busy, Enter **queues** and does not interrupt. Esc: clear the draft first; if empty and busy, cancel. **Ctrl+C** quits (confirms if background tasks are running). **Ctrl+Shift+C** copies a dragged transcript selection.

`@` opens the file picker. A long paste collapses to `[Pasted text #N]`. The composer grows to about 8 rows, then scrolls with the wheel, `Shift+↑↓`, or `Shift+PgUp/PgDn` (caret and queue stay put). Drafts cap at 4000 characters. `PageUp` / `PageDown` page the transcript.

---

## Config snippets

Common keys in `.cawki/config.json`:

```json
{
  "auto_memory_enabled": true,
  "auto_dream_enabled": true,
  "auto_dream_min_writes": 3,
  "auto_compact_enabled": true,
  "compact_token_threshold": 80000,
  "cost_limit_usd": 5.0,
  "notify_on_idle": false,
  "permissions": {
    "lsp": {
      "sandbox": true,
      "allow_network": false,
      "allow_workspace_writes": false
    }
  },
  "router": {
    "enabled": false,
    "classifier": "heuristic",
    "fast": { "provider": "ollama", "model": "qwen2.5-coder:7b" }
  }
}
```

`languages.toml` example (`~/.cawki/` or project `.cawki/`):

The global file is user-managed. A project file's `commands` trigger a fingerprinted launch confirmation whenever Cawki creates a server process.

```toml
[[stack]]
name = "Acme"
manifests = ["acme.lock"]
check = "acme check"
test = "acme test"

[[lsp]]
id = "acme"
extensions = ["acme"]
commands = [["acme-lsp", "--stdio"]]

[[debug]]
backend = "native"
extensions = ["acme"]
```

`/settings notify-on-idle` or `/notify on`: desktop toast when a background tab finishes or `--print` completes (off by default).

---

## Troubleshooting

| Symptom | What to do |
|---------|------------|
| Upgrade HTTP 404 | That tag has no Release yet, or the private repo has not pushed artifacts to the hub. See [Releases](https://github.com/noxrick91/cawki-hub/releases) |
| No asset for this platform | The matrix is only the targets in the table above |
| GitHub 403 / 429 | Set `GH_TOKEN` or `CAW_GITHUB_TOKEN` |
| SHA256 mismatch | Download again; do not mix sums and binaries from different tags |
| `--version` mismatch | The installer tries to restore the `.bak` |
| Native Windows `run` sandbox fails | Expected; use WSL2 or `/settings sandbox` to turn the jail off |
| macOS screenshot is black / empty | Grant the terminal Screen Recording, then restart the terminal |
| `--print` exit code 2 | Default `fail`: a permission / question / plan needs a human. Change `--on-approval` / `--on-ask` / `--on-plan` |
| Windows `irm …/install.ps1` errors or does nothing | GitHub Pages serves `.ps1` as binary. Use `irm https://agent.noxcaw.com/install.txt \| iex`, or `iex ((New-Object Net.WebClient).DownloadString('https://agent.noxcaw.com/install.ps1'))` |
| Windows TLS / secure channel error | Use Windows PowerShell 5.1+ or PowerShell 7; the installer forces TLS 1.2 |
| Broken leftover `cawki.exe` blocks reinstall | Close every Cawki window and run the installer again, or delete `%USERPROFILE%\.cawki\bin\cawki.exe` |
| Windows reinstall/update still shows an old version | Older installers handed an existing install to `cawki upgrade now`, which can leave 0.1.6 in place if the exe is locked or the GitHub API fails. Close every window, run `irm https://agent.noxcaw.com/install.txt \| iex` again, then open a new terminal and run `cawki --version`. Use `Get-Command cawki` to make sure PATH is not another old exe |
| Command not found | `source ~/.cawki/env` or open a new terminal; the installer writes an rc hook. On Windows, open a new terminal so the user PATH reloads |
| `serve` refuses to listen | Anything other than `127.0.0.1` / `::1` needs `--token` or `CAW_SERVE_TOKEN` |
| Ollama still asks for a key | Use `/model add ollama`, not an OpenAI-compatible gateway that requires a key |
| Gateway 401 / unknown model | Use the relay’s own base URL, key, and model id; do not rewrite `openai` / `anthropic` presets. See [Models and keys](#/models) |

This manual is the only public usage doc. Implementation notes stay in the private source repo.
