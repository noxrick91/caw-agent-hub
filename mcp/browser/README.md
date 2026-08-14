# Browser MCP for caw-agent

stdio MCP that drives **headless Chromium** (Playwright) so the model can open pages, read an accessibility tree, click/type, and screenshot.

Computer-use treats real desktop browsers as **view_only**. Use this pack for navigation and forms instead of `computer` clicks on Chrome/Firefox.

There is **no JavaScript evaluate**. Only `http` / `https` URLs.

## Tools

| Tool | What it does |
|------|----------------|
| `browser_status` | Playwright installed? page open? |
| `browser_install_deps` | `pip install playwright` + `playwright install chromium` |
| `browser_open` | Launch (or reuse) Chromium; optional URL |
| `browser_goto` | Navigate |
| `browser_snapshot` | A11y tree with `[e1]` refs |
| `browser_click` / `browser_type` | Act by ref (or CSS selector) |
| `browser_press` | Key (Enter, Tab, Control+a, …) |
| `browser_screenshot` | PNG under `.caw-agent/media/` |
| `browser_close` | Drop the session |

## Setup

```text
/mcp install browser
```

Then in a turn: `browser_status` → `browser_install_deps` if needed → `browser_open`.

Reload: `/mcp reload`.

Headed window: `headed=true` on `browser_open`, or `BROWSER_HEADED=1` in the server env.

Linux missing system libs: `python -m playwright install --with-deps chromium` (may need sudo).

## Skills

`mcp/browser/skills/browser` — discovered automatically.
