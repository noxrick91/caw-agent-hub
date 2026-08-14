#!/usr/bin/env python3
"""Smoke-test MCP initialize + tools + Pillow cutout/resize/SR (no rembg required)."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
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


def payload(msg: dict) -> dict:
    text = msg["result"]["content"][0]["text"]
    if msg["result"].get("isError"):
        raise RuntimeError(text)
    return json.loads(text)


def make_sample(path: Path) -> None:
    from PIL import Image, ImageDraw

    im = Image.new("RGB", (64, 48), (0, 200, 0))
    d = ImageDraw.Draw(im)
    d.ellipse((16, 8, 48, 40), fill=(200, 30, 30))
    im.save(path)


def main() -> int:
    proc = subprocess.Popen(
        [sys.executable, str(ROOT / "server.py")],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=str(ROOT),
    )
    assert proc.stdin and proc.stdout
    tmp = Path(tempfile.mkdtemp(prefix="caw-image-smoke-"))
    src = tmp / "sample.png"
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
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "image-mcp"
        write_msg(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        write_msg(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_msg(proc)
        tools = listed["result"]["tools"]
        names = [t["name"] for t in tools]
        required = {
            "image_status",
            "image_info",
            "image_cutout",
            "image_resize",
            "image_super_resolve",
            "image_install_deps",
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
                "params": {"name": "image_status", "arguments": {}},
            },
        )
        status = payload(read_msg(proc))
        print(f"ok: {len(names)} tools")
        for n in names:
            print(f"  - {n}")
        print("status:", json.dumps(status["available"], ensure_ascii=False))
        if not status["available"].get("pillow"):
            print("Pillow missing — protocol-only smoke passed")
            return 0

        make_sample(src)
        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "image_info", "arguments": {"path": str(src)}},
            },
        )
        info = payload(read_msg(proc))
        assert info["width"] == 64 and info["height"] == 48

        cut = tmp / "cut.png"
        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "image_cutout",
                    "arguments": {
                        "path": str(src),
                        "method": "chroma",
                        "color": "#00C800",
                        "tolerance": 40,
                        "output": str(cut),
                    },
                },
            },
        )
        cut_r = payload(read_msg(proc))
        assert Path(cut_r["path"]).is_file()

        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "image_resize",
                    "arguments": {"path": str(cut), "scale": 0.5, "output": str(tmp / "half.png")},
                },
            },
        )
        half = payload(read_msg(proc))
        assert half["width"] < cut_r["width"]

        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "image_super_resolve",
                    "arguments": {
                        "path": str(cut),
                        "scale": 2,
                        "backend": "lanczos",
                        "output": str(tmp / "sr.png"),
                    },
                },
            },
        )
        sr = payload(read_msg(proc))
        assert sr["width"] == cut_r["width"] * 2
        print(f"cutout {cut_r['width']}x{cut_r['height']} -> resize {half['width']} / sr {sr['width']}")
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
