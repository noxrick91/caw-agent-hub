"""Blender execution backends: GUI bridge and Blender CLI (--background)."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any


DEFAULT_BRIDGE_HOST = os.environ.get("BLENDER_BRIDGE_HOST", "127.0.0.1")
DEFAULT_BRIDGE_PORT = int(os.environ.get("BLENDER_BRIDGE_PORT", "54322"))


class BlenderError(RuntimeError):
    pass


class BridgeBackend:
    """Talk to the Blender addon over TCP (JSON lines)."""

    name = "bridge"

    def __init__(self, host: str = DEFAULT_BRIDGE_HOST, port: int = DEFAULT_BRIDGE_PORT) -> None:
        self.host = host
        self.port = port

    def ping(self) -> bool:
        try:
            resp = self._request({"cmd": "ping"}, timeout=2.0)
            return bool(resp.get("ok"))
        except Exception:
            return False

    def execute(self, code: str, *, timeout: float = 120.0) -> dict[str, Any]:
        resp = self._request({"cmd": "exec", "code": code}, timeout=timeout)
        if not resp.get("ok", False):
            raise BlenderError(resp.get("error", "bridge exec failed"))
        result = resp.get("result")
        if result is None:
            return {"ok": True}
        if not isinstance(result, dict):
            return {"ok": True, "result": result}
        return result

    def _request(self, payload: dict[str, Any], *, timeout: float) -> dict[str, Any]:
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        with socket.create_connection((self.host, self.port), timeout=min(timeout, 10.0)) as sock:
            sock.settimeout(timeout)
            sock.sendall(data)
            buf = b""
            while b"\n" not in buf:
                chunk = sock.recv(65536)
                if not chunk:
                    break
                buf += chunk
        if not buf:
            raise BlenderError("empty response from Blender bridge")
        line = buf.split(b"\n", 1)[0].decode("utf-8")
        return json.loads(line)


class CmdBackend:
    """Spawn Blender --background per call with a persistent .blend session file."""

    name = "cmd"

    def __init__(self, blender: str | None = None, workdir: Path | None = None) -> None:
        self.blender = blender or find_blender()
        if not self.blender:
            raise BlenderError(
                "Blender executable not found. Set BLENDER_PATH or install Blender, "
                "or enable the GUI bridge addon."
            )
        self.workdir = workdir or Path(tempfile.gettempdir()) / "caw-blender-mcp"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.blend_path = self.workdir / "session.blend"
        self.result_path = self.workdir / "result.json"
        self.script_path = self.workdir / "run_once.py"

    def execute(self, code: str, *, timeout: float = 120.0) -> dict[str, Any]:
        if self.result_path.exists():
            try:
                self.result_path.unlink()
            except Exception:
                pass

        script = textwrap.dedent(
            f"""
            import bpy
            import json
            from pathlib import Path

            blend = Path({str(self.blend_path)!r})
            result_path = Path({str(self.result_path)!r})
            code_path = Path({str(self.workdir / "user_code.py")!r})

            if blend.is_file():
                bpy.ops.wm.open_mainfile(filepath=str(blend))

            __result__ = None
            ns = {{"bpy": bpy, "__result__": None}}
            try:
                exec(code_path.read_text(encoding="utf-8"), ns, ns)
            except Exception as e:
                result_path.write_text(
                    json.dumps({{"ok": False, "error": f"{{type(e).__name__}}: {{e}}"}}, ensure_ascii=False),
                    encoding="utf-8",
                )
                raise SystemExit(1)

            bpy.ops.wm.save_as_mainfile(filepath=str(blend))
            out = ns.get("__result__")
            if out is None:
                out = {{"ok": True}}
            if not isinstance(out, dict):
                out = {{"ok": True, "result": out}}
            result_path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
            """
        )
        user_code_path = self.workdir / "user_code.py"
        user_code_path.write_text(code, encoding="utf-8")
        self.script_path.write_text(script, encoding="utf-8")
        cmd = [self.blender, "--background", "--python", str(self.script_path)]
        try:
            kwargs: dict[str, Any] = {
                "capture_output": True,
                "text": True,
                "timeout": timeout,
                "cwd": str(self.workdir),
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.run(cmd, **kwargs)
        except subprocess.TimeoutExpired as e:
            raise BlenderError(f"Blender timed out after {timeout}s") from e

        if not self.result_path.is_file():
            err = (proc.stderr or proc.stdout or "").strip()[-2000:]
            raise BlenderError(f"Blender produced no result.json (exit={proc.returncode}): {err}")

        data = json.loads(self.result_path.read_text(encoding="utf-8"))
        if data.get("ok") is False and "error" in data:
            raise BlenderError(data["error"])
        return data


def find_blender() -> str | None:
    env = os.environ.get("BLENDER_PATH") or os.environ.get("BLENDER")
    if env and Path(env).is_file():
        return env
    which = shutil.which("blender")
    if which:
        return which
    candidates: list[Path] = []
    if sys.platform == "win32":
        pf = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        pf86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
        for root in (pf, pf86):
            candidates.extend(root.glob("Blender Foundation/Blender */blender.exe"))
            direct = root / "Blender" / "blender.exe"
            if direct.is_file():
                candidates.append(direct)
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/Blender.app/Contents/MacOS/Blender"))
    else:
        for p in (Path("/usr/bin/blender"), Path("/usr/local/bin/blender")):
            if p.is_file():
                candidates.append(p)
    for p in sorted(candidates, key=lambda x: str(x), reverse=True):
        if p.is_file():
            return str(p)
    return None


class BlenderSession:
    """Auto-select bridge (preferred) or Blender CLI backend."""

    def __init__(self) -> None:
        self._backend = self._select_backend()

    def _select_backend(self):
        mode = (os.environ.get("BLENDER_BACKEND") or "auto").lower()
        if mode == "bridge":
            b = BridgeBackend()
            if not b.ping():
                raise BlenderError(
                    f"Blender bridge not reachable at {DEFAULT_BRIDGE_HOST}:{DEFAULT_BRIDGE_PORT}. "
                    "Install/enable CawBlenderBridge and start Blender."
                )
            return b
        if mode == "cmd":
            return CmdBackend()
        b = BridgeBackend()
        if b.ping():
            return b
        return CmdBackend()

    @property
    def backend_name(self) -> str:
        return self._backend.name

    def execute(self, code: str, *, timeout: float | None = None) -> dict[str, Any]:
        t = timeout if timeout is not None else float(os.environ.get("BLENDER_TIMEOUT", "120"))
        return self._backend.execute(code, timeout=t)

    def status(self) -> dict[str, Any]:
        code = textwrap.dedent(
            """
            import bpy
            objs = [o.name for o in bpy.context.scene.objects]
            __result__ = {
                "ok": True,
                "blender": bpy.app.version_string,
                "file": bpy.data.filepath or None,
                "objects": len(objs),
                "object_names": objs[:40],
            }
            """
        )
        try:
            info = self.execute(code, timeout=60.0)
        except Exception as e:
            info = {"ok": False, "error": str(e)}
        info["backend"] = self.backend_name
        info["bridge"] = f"{DEFAULT_BRIDGE_HOST}:{DEFAULT_BRIDGE_PORT}"
        return info
