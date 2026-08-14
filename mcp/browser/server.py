#!/usr/bin/env python3
"""Browser MCP server for caw-agent (NDJSON / Content-Length JSON-RPC)."""

from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from browser import BrowserError  # noqa: E402
from protocol import err_result, ok_result, read_message, tool_json, tool_text, write_message  # noqa: E402
from tools import call_tool, list_tool_specs  # noqa: E402

SERVER_NAME = "browser-mcp"
SERVER_VERSION = "1.0.0"
PROTOCOL_VERSION = "2024-11-05"


def log(msg: str) -> None:
    path = os.environ.get("BROWSER_MCP_LOG")
    line = f"[browser-mcp] {msg}\n"
    if path:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line)
            return
        except Exception:
            pass
    try:
        sys.stderr.write(line)
        sys.stderr.flush()
    except Exception:
        pass


class Server:
    def __init__(self) -> None:
        self.initialized = False

    def handle(self, msg: dict) -> dict | None:
        if "method" not in msg:
            return None
        method = msg["method"]
        id_ = msg.get("id")
        params = msg.get("params") or {}

        if id_ is None:
            if method == "notifications/initialized":
                self.initialized = True
            return None

        try:
            if method == "initialize":
                return ok_result(
                    id_,
                    {
                        "protocolVersion": PROTOCOL_VERSION,
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    },
                )
            if method == "ping":
                return ok_result(id_, {})
            if method == "tools/list":
                return ok_result(id_, {"tools": list_tool_specs()})
            if method == "tools/call":
                name = params.get("name")
                arguments = params.get("arguments") or {}
                if not name:
                    return err_result(id_, -32602, "missing tool name")
                try:
                    result = call_tool(name, arguments)
                    return ok_result(id_, tool_json(result))
                except BrowserError as e:
                    return ok_result(id_, tool_text(str(e), is_error=True))
                except Exception as e:
                    log(traceback.format_exc())
                    return ok_result(
                        id_,
                        tool_text(f"{type(e).__name__}: {e}", is_error=True),
                    )
            return err_result(id_, -32601, f"method not found: {method}")
        except Exception as e:
            log(traceback.format_exc())
            return err_result(id_, -32603, f"internal error: {e}")


def main() -> int:
    try:
        sys.stdin.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    log("starting")
    server = Server()
    while True:
        try:
            msg = read_message(sys.stdin)
        except Exception as e:
            log(f"read error: {e}")
            break
        if msg is None:
            break
        resp = server.handle(msg)
        if resp is not None:
            write_message(resp, sys.stdout)
    try:
        from browser import close

        close()
    except Exception:
        pass
    log("exit")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
