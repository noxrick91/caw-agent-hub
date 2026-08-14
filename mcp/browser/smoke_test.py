#!/usr/bin/env python3
"""Smoke-test MCP initialize + tools/list + browser_status (no Playwright required)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_msg(proc: subprocess.Popen, msg: dict) -> None:
    body = json.dumps(msg, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    proc.stdin.write(body + b"\n")
    proc.stdin.flush()


def read_msg(proc: subprocess.Popen) -> dict:
    line = proc.stdout.readline()
    if not line:
        err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
        raise RuntimeError(f"EOF from server\n{err}")
    stripped = line.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return json.loads(line.decode("utf-8"))
    content_length = None
    while True:
        if line in (b"\r\n", b"\n"):
            break
        lower = line.decode("ascii", errors="replace").lower()
        if lower.startswith("content-length:"):
            content_length = int(lower.split(":", 1)[1].strip())
        line = proc.stdout.readline()
        if not line:
            raise RuntimeError("EOF while reading headers")
    assert content_length is not None
    data = proc.stdout.read(content_length)
    return json.loads(data.decode("utf-8"))


def payload(msg: dict) -> dict:
    text = msg["result"]["content"][0]["text"]
    if msg["result"].get("isError"):
        raise RuntimeError(text)
    return json.loads(text)


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
    )
    assert proc.stdin and proc.stdout
    try:
        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "smoke", "version": "0"},
                },
            },
        )
        init = read_msg(proc)
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "browser-mcp"
        write_msg(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        write_msg(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_msg(proc)
        names = [t["name"] for t in listed["result"]["tools"]]
        required = {
            "browser_status",
            "browser_install_deps",
            "browser_open",
            "browser_goto",
            "browser_snapshot",
            "browser_click",
            "browser_type",
            "browser_press",
            "browser_screenshot",
            "browser_close",
        }
        missing = required - set(names)
        if missing:
            raise SystemExit(f"missing tools: {sorted(missing)}")
        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "browser_status", "arguments": {}},
            },
        )
        status = payload(read_msg(proc))
        assert status.get("ok") is True
        assert status.get("session") == "closed"
        print(f"ok: {len(names)} tools")
        for n in names:
            print(f"  - {n}")
        print("status:", json.dumps(status, ensure_ascii=False))

        from browser import validate_url, BrowserError

        validate_url("https://example.com")
        try:
            validate_url("file:///etc/passwd")
            raise SystemExit("file URL should be rejected")
        except BrowserError:
            pass
        print("url guard: ok")
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
