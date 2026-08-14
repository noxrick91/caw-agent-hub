#!/usr/bin/env python3
"""Smoke-test MCP initialize + tools/list against server.py (no Blender required)."""

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
            raise RuntimeError("EOF from server")
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
        cwd=str(ROOT.parent.parent),
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
        assert init.get("result", {}).get("serverInfo", {}).get("name") == "blender-mcp"
        write_msg(proc, {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        write_msg(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        listed = read_msg(proc)
        tools = listed["result"]["tools"]
        names = [t["name"] for t in tools]
        print(f"ok: {len(names)} tools")
        for n in names:
            print(f"  - {n}")
        required = {
            "blender_status",
            "add_mesh",
            "add_modifier",
            "boolean",
            "export_model",
            "import_model",
            "execute_python",
            "list_objects",
            "set_transform",
            "animation_setup",
            "animation_keyframe",
            "animation_play",
            "animation_render",
            "animation_parent",
            "render_image",
            "setup_lookdev",
            "add_camera",
            "add_light",
            "set_material",
            "set_hdri",
            "setup_compositor",
            "mesh_info",
            "edit_extrude",
            "edit_inset",
            "edit_bevel",
            "create_curve",
            "curve_to_mesh",
            "sculpt_remesh",
            "sculpt_inflate",
            "sculpt_grab",
            "mesh_decimate",
            "set_units",
            "export_for_freecad",
            "import_from_freecad",
        }
        missing = required - set(names)
        if missing:
            print(f"MISSING: {missing}", file=sys.stderr)
            return 1
        return 0
    finally:
        proc.kill()
        proc.wait(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
