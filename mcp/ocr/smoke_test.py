#!/usr/bin/env python3
"""Smoke-test MCP initialize + tools + optional local OCR (no engine required)."""

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
    from PIL import Image, ImageDraw, ImageFont

    im = Image.new("RGB", (280, 80), (255, 255, 255))
    d = ImageDraw.Draw(im)
    try:
        font = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
    d.text((12, 18), "HELLO OCR", fill=(0, 0, 0), font=font)
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
    tmp = Path(tempfile.mkdtemp(prefix="caw-ocr-smoke-"))
    src = tmp / "hello.png"
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
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "ocr-mcp"
        write_msg(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        write_msg(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_msg(proc)
        tools = listed["result"]["tools"]
        names = [t["name"] for t in tools]
        required = {"ocr_status", "ocr_languages", "ocr_image", "ocr_install_deps"}
        missing = required - set(names)
        if missing:
            raise SystemExit(f"missing tools: {sorted(missing)}")
        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "ocr_status", "arguments": {}},
            },
        )
        status = payload(read_msg(proc))
        print(f"ok: {len(names)} tools")
        for n in names:
            print(f"  - {n}")
        print("status:", json.dumps(status.get("available"), ensure_ascii=False))

        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "ocr_languages", "arguments": {}},
            },
        )
        langs = payload(read_msg(proc))
        assert langs.get("ok")

        try:
            make_sample(src)
        except Exception as e:
            print(f"Pillow missing — protocol-only smoke passed ({e})")
            return 0

        write_msg(
            proc,
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "ocr_image",
                    "arguments": {
                        "path": str(src),
                        "lang": "eng",
                        "write_sidecar": True,
                    },
                },
            },
        )
        ocr_msg = read_msg(proc)
        text = ocr_msg["result"]["content"][0]["text"]
        if ocr_msg["result"].get("isError"):
            print("ocr_image (no backend):", text.splitlines()[0])
            return 0
        result = json.loads(text)
        extracted = (result.get("text") or "").upper()
        print(f"backend={result.get('backend')} text={result.get('text')!r}")
        if result.get("backend") != "openai" and "HELLO" not in extracted:
            print("warning: expected HELLO in OCR text (font/engine variance ok)")
        if result.get("sidecar"):
            assert Path(result["sidecar"]).is_file()
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
