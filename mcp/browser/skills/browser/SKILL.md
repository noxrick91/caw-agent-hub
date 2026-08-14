---
name: browser
description: Drive a headless Chromium page (open, snapshot, click, type, screenshot) with the browser MCP. Use when the user asks to open a URL, fill a form, check a web UI, or when computer-use blocks a desktop browser as view_only.
---

# Browser

Use `mcp__browser__*`. Do not invent page contents. Computer-use cannot type into Chrome/Firefox — this pack can.

## Tools

| Tool | When |
|------|------|
| `browser_status` | First step — is Playwright installed? is a page open? |
| `browser_install_deps` | `playwright` missing or Chromium launch failed |
| `browser_open` | Launch / reuse; optional `url`, `headed` |
| `browser_goto` | Navigate (http/https only) |
| `browser_snapshot` | A11y tree + `[eN]` refs — prefer this over screenshots |
| `browser_click` / `browser_type` | `ref` from the last snapshot (CSS `selector` only as fallback) |
| `browser_press` | Enter, Tab, Escape, Control+a, ArrowDown, … |
| `browser_screenshot` | PNG under `.caw-agent/media/` then `read_file` if you need pixels |
| `browser_close` | Done with the session |

## Flow

1. `browser_status`. If `playwright` is false, `browser_install_deps`.
2. `browser_open` with the URL (or `browser_goto` if already open).
3. `browser_snapshot`. Act with `ref=e3` etc. Snapshot again after navigation.
4. `browser_screenshot` only when the user needs a picture or the tree is not enough.
5. `browser_close` when finished.

Same MCP server is one-at-a-time. No `evaluate` / raw JS. No `file://` or `javascript:` URLs.

## Missing pieces

| Gap | Fix |
|-----|-----|
| no playwright / no chromium | `browser_install_deps` |
| Linux shared-library errors | `install_program` will not help — tell the user to run `python -m playwright install --with-deps chromium` |
