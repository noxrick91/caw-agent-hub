#!/usr/bin/env python3
"""Smoke-test MCP initialize + tools/list + speech_status (no Whisper required)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def write_msg(proc: subprocess.Popen, msg: dict) -> None:
    body = json.dumps(msg).encode("utf-8")
    proc.stdin.write(f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body)
    proc.stdin.flush()


def read_msg(proc: subprocess.Popen) -> dict:
    content_length = None
    while True:
        line = proc.stdout.readline()
        if not line:
            err = proc.stderr.read().decode("utf-8", errors="replace") if proc.stderr else ""
            raise RuntimeError(f"EOF from server\n{err}")
        if line in (b"\r\n", b"\n"):
            break
        lower = line.decode("ascii", errors="replace").lower()
        if lower.startswith("content-length:"):
            content_length = int(lower.split(":", 1)[1].strip())
    assert content_length is not None
    data = proc.stdout.read(content_length)
    return json.loads(data.decode("utf-8"))


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
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "speech-mcp"
        write_msg(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        write_msg(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_msg(proc)
        tools = listed["result"]["tools"]
        names = [t["name"] for t in tools]
        required = {
            "speech_status",
            "list_speech_models",
            "transcribe_file",
            "list_input_devices",
            "record_and_transcribe",
            "speech_install_deps",
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
                "params": {"name": "speech_status", "arguments": {}},
            },
        )
        status = read_msg(proc)
        text = status["result"]["content"][0]["text"]
        print(f"ok: {len(names)} tools")
        for n in names:
            print(f"  - {n}")
        print("status:")
        print(text)
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
