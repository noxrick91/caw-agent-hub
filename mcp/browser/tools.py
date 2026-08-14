"""MCP tool schemas for browser automation."""

from __future__ import annotations

from typing import Any, Callable

from browser import (
    BrowserError,
    click,
    close,
    goto,
    install_deps,
    open_browser,
    press,
    screenshot,
    snapshot,
    status,
    type_text,
)

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_browser_status(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return status()


def tool_browser_install_deps(args: dict[str, Any]) -> dict[str, Any]:
    pkgs = args.get("packages")
    if pkgs is not None:
        pkgs = [str(p) for p in pkgs]
    return install_deps(pkgs)


def tool_browser_open(args: dict[str, Any]) -> dict[str, Any]:
    return open_browser(args.get("url"), args.get("headed"))


def tool_browser_goto(args: dict[str, Any]) -> dict[str, Any]:
    return goto(args["url"])


def tool_browser_snapshot(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return snapshot()


def tool_browser_click(args: dict[str, Any]) -> dict[str, Any]:
    return click(args.get("ref"), args.get("selector"))


def tool_browser_type(args: dict[str, Any]) -> dict[str, Any]:
    return type_text(
        args.get("text"),
        args.get("ref"),
        args.get("selector"),
        bool(args.get("submit", False)),
    )


def tool_browser_press(args: dict[str, Any]) -> dict[str, Any]:
    return press(args["key"])


def tool_browser_screenshot(args: dict[str, Any]) -> dict[str, Any]:
    return screenshot(args.get("path"), bool(args.get("full_page", False)))


def tool_browser_close(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return close()


TOOLS: list[dict[str, Any]] = [
    {
        "name": "browser_status",
        "description": (
            "PREFERRED first step: report Playwright install + whether a page is open. "
            "Does not launch a browser."
        ),
        "inputSchema": _schema({}),
        "handler": tool_browser_status,
    },
    {
        "name": "browser_install_deps",
        "description": (
            "Install Playwright into THIS MCP server's interpreter and download Chromium. "
            "Call when browser_status.playwright is false or launch fails."
        ),
        "inputSchema": _schema(
            {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Only `playwright` is allowed (default).",
                }
            }
        ),
        "handler": tool_browser_install_deps,
    },
    {
        "name": "browser_open",
        "description": (
            "Launch headless Chromium (reuse if already open). Optional url (http/https only). "
            "headed=true or BROWSER_HEADED=1 shows a window. No JavaScript evaluate."
        ),
        "inputSchema": _schema(
            {
                "url": {
                    "type": "string",
                    "description": "Optional http(s) URL to open.",
                },
                "headed": {
                    "type": "boolean",
                    "description": "Show a browser window (default headless).",
                },
            }
        ),
        "handler": tool_browser_open,
    },
    {
        "name": "browser_goto",
        "description": "Navigate the current page to an http(s) URL. Requires browser_open first.",
        "inputSchema": _schema(
            {
                "url": {
                    "type": "string",
                    "description": "http(s) URL.",
                }
            },
            ["url"],
        ),
        "handler": tool_browser_goto,
    },
    {
        "name": "browser_snapshot",
        "description": (
            "Accessibility tree with numbered refs ([e1], [e2], …). "
            "Use those refs with browser_click / browser_type. Prefer this over screenshots."
        ),
        "inputSchema": _schema({}),
        "handler": tool_browser_snapshot,
    },
    {
        "name": "browser_click",
        "description": "Click a snapshot ref (preferred) or a CSS selector.",
        "inputSchema": _schema(
            {
                "ref": {
                    "type": "string",
                    "description": "Ref from the last browser_snapshot (e.g. e3).",
                },
                "selector": {
                    "type": "string",
                    "description": "CSS selector fallback when no ref.",
                },
            }
        ),
        "handler": tool_browser_click,
    },
    {
        "name": "browser_type",
        "description": "Fill/type into a snapshot ref or selector. submit=true presses Enter after.",
        "inputSchema": _schema(
            {
                "text": {"type": "string", "description": "Text to type (may be empty to clear)."},
                "ref": {"type": "string", "description": "Ref from browser_snapshot."},
                "selector": {"type": "string", "description": "CSS selector fallback."},
                "submit": {
                    "type": "boolean",
                    "description": "Press Enter after typing (default false).",
                    "default": False,
                },
            },
            ["text"],
        ),
        "handler": tool_browser_type,
    },
    {
        "name": "browser_press",
        "description": "Press a key on the page (Enter, Tab, Escape, Control+a, ArrowDown, …).",
        "inputSchema": _schema(
            {
                "key": {
                    "type": "string",
                    "description": "Playwright key name, optional Modifier+key.",
                }
            },
            ["key"],
        ),
        "handler": tool_browser_press,
    },
    {
        "name": "browser_screenshot",
        "description": (
            "PNG of the current page under the workspace (default `.caw-agent/media/browser-*.png`). "
            "Then read_file the PNG if you need pixels. Prefer browser_snapshot for forms."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Optional workspace-relative PNG path.",
                },
                "full_page": {
                    "type": "boolean",
                    "description": "Capture the full scrollable page (default false).",
                    "default": False,
                },
            }
        ),
        "handler": tool_browser_screenshot,
    },
    {
        "name": "browser_close",
        "description": "Close the Chromium session and drop snapshot refs.",
        "inputSchema": _schema({}),
        "handler": tool_browser_close,
    },
]


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in TOOLS
    ]


HANDLERS: dict[str, ToolHandler] = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in HANDLERS:
        raise BrowserError(f"unknown tool: {name}")
    return HANDLERS[name](arguments or {})
