"""FreeCAD execution backends: in-process, GUI bridge, FreeCADCmd."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import textwrap
import time
from pathlib import Path
from typing import Any


DEFAULT_BRIDGE_HOST = os.environ.get("FREECAD_BRIDGE_HOST", "127.0.0.1")
DEFAULT_BRIDGE_PORT = int(os.environ.get("FREECAD_BRIDGE_PORT", "54321"))


class FreeCADError(RuntimeError):
    pass


def _try_import_freecad() -> bool:
    try:
        import FreeCAD  # noqa: F401

        return True
    except Exception:
        return False


class InProcessBackend:
    """Run FreeCAD API inside this interpreter (FreeCAD's python.exe)."""

    name = "inprocess"

    def __init__(self) -> None:
        import FreeCAD
        import Part  # noqa: F401

        self.FreeCAD = FreeCAD
        self._ensure_doc("Unnamed")

    def _ensure_doc(self, name: str = "Unnamed"):
        if self.FreeCAD.ActiveDocument is None:
            return self.FreeCAD.newDocument(name)
        return self.FreeCAD.ActiveDocument

    def execute(self, code: str, *, timeout: float = 120.0) -> dict[str, Any]:
        del timeout
        ns: dict[str, Any] = {
            "FreeCAD": self.FreeCAD,
            "__result__": None,
        }
        try:
            import Part

            ns["Part"] = Part
        except Exception:
            pass
        try:
            import Draft

            ns["Draft"] = Draft
        except Exception:
            pass
        try:
            import Sketcher

            ns["Sketcher"] = Sketcher
        except Exception:
            pass
        try:
            import PartDesign

            ns["PartDesign"] = PartDesign
        except Exception:
            pass
        try:
            import Mesh

            ns["Mesh"] = Mesh
        except Exception:
            pass
        try:
            import Import

            ns["Import"] = Import
        except Exception:
            pass
        try:
            import FreeCADGui

            ns["FreeCADGui"] = FreeCADGui
        except Exception:
            pass
        for mod_name in ("UtilsAssembly", "JointObject", "CommandCreateJoint"):
            try:
                ns[mod_name] = __import__(mod_name)
            except Exception:
                pass

        try:
            exec(code, ns, ns)  # noqa: S102 — intentional CAD scripting surface
        except Exception as e:
            raise FreeCADError(f"{type(e).__name__}: {e}") from e

        doc = self.FreeCAD.ActiveDocument
        if doc is not None:
            try:
                doc.recompute()
            except Exception:
                pass

        result = ns.get("__result__")
        if result is None:
            result = {"ok": True}
        if not isinstance(result, dict):
            result = {"ok": True, "result": result}
        return result


class BridgeBackend:
    """Talk to the FreeCAD GUI addon over TCP (JSON lines)."""

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
            raise FreeCADError(resp.get("error", "bridge exec failed"))
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
            raise FreeCADError("empty response from FreeCAD bridge")
        line = buf.split(b"\n", 1)[0].decode("utf-8")
        return json.loads(line)


class CmdBackend:
    """Spawn FreeCADCmd per call with a persistent document file."""

    name = "cmd"

    def __init__(self, freecadcmd: str | None = None, workdir: Path | None = None) -> None:
        self.freecadcmd = freecadcmd or find_freecadcmd()
        if not self.freecadcmd:
            raise FreeCADError(
                "FreeCADCmd not found. Set FREECADCMD or install FreeCAD, "
                "or run the GUI bridge addon."
            )
        self.workdir = workdir or Path(tempfile.gettempdir()) / "caw-freecad-mcp"
        self.workdir.mkdir(parents=True, exist_ok=True)
        self.doc_path = self.workdir / "session.FCStd"
        self.result_path = self.workdir / "result.json"

    def execute(self, code: str, *, timeout: float = 120.0) -> dict[str, Any]:
        wrapper = textwrap.dedent(
            f"""
            import json, os, traceback
            import FreeCAD
            try:
                import Part
            except Exception:
                Part = None
            try:
                import Draft
            except Exception:
                Draft = None
            try:
                import Sketcher
            except Exception:
                Sketcher = None
            try:
                import PartDesign
            except Exception:
                PartDesign = None
            try:
                import Mesh
            except Exception:
                Mesh = None
            try:
                import Import
            except Exception:
                Import = None
            try:
                import UtilsAssembly
            except Exception:
                UtilsAssembly = None
            try:
                import JointObject
            except Exception:
                JointObject = None

            DOC_PATH = {str(self.doc_path)!r}
            RESULT_PATH = {str(self.result_path)!r}
            __result__ = None

            if os.path.exists(DOC_PATH):
                FreeCAD.open(DOC_PATH)
            elif FreeCAD.ActiveDocument is None:
                FreeCAD.newDocument("Unnamed")

            try:
                {textwrap.indent(code, "                ").lstrip()}
                doc = FreeCAD.ActiveDocument
                if doc is not None:
                    doc.recompute()
                    doc.saveAs(DOC_PATH)
                out = __result__ if __result__ is not None else {{"ok": True}}
                if not isinstance(out, dict):
                    out = {{"ok": True, "result": out}}
                with open(RESULT_PATH, "w", encoding="utf-8") as f:
                    json.dump(out, f, ensure_ascii=False, indent=2)
            except Exception as e:
                with open(RESULT_PATH, "w", encoding="utf-8") as f:
                    json.dump({{"ok": False, "error": f"{{type(e).__name__}}: {{e}}",
                               "traceback": traceback.format_exc()}}, f, ensure_ascii=False)
                raise
            """
        )
        script = self.workdir / f"job_{int(time.time() * 1000)}.py"
        script.write_text(wrapper, encoding="utf-8")
        if self.result_path.exists():
            self.result_path.unlink()
        try:
            kwargs: dict = {
                "capture_output": True,
                "text": True,
                "timeout": timeout,
                "cwd": str(self.workdir),
            }
            if sys.platform == "win32":
                kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
            proc = subprocess.run(
                [self.freecadcmd, str(script)],
                **kwargs,
            )
        except subprocess.TimeoutExpired as e:
            raise FreeCADError(f"FreeCADCmd timed out after {timeout}s") from e
        finally:
            try:
                script.unlink(missing_ok=True)
            except Exception:
                pass

        if not self.result_path.exists():
            err = (proc.stderr or proc.stdout or "").strip()
            raise FreeCADError(
                f"FreeCADCmd failed (exit {proc.returncode}): {err or 'no result file'}"
            )
        payload = json.loads(self.result_path.read_text(encoding="utf-8"))
        if payload.get("ok") is False and "error" in payload:
            raise FreeCADError(payload["error"])
        return payload


def find_freecadcmd() -> str | None:
    env = os.environ.get("FREECADCMD") or os.environ.get("FREECAD_CMD")
    if env and Path(env).exists():
        return env
    candidates: list[Path] = []
    for key in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        root = os.environ.get(key)
        if not root:
            continue
        base = Path(root)
        candidates.extend(base.glob("FreeCAD*/bin/FreeCADCmd.exe"))
        candidates.extend(base.glob("FreeCAD*/bin/freecadcmd.exe"))
    # Linux / macOS common paths
    candidates.extend(
        [
            Path("/usr/bin/freecadcmd"),
            Path("/usr/bin/FreeCADCmd"),
            Path("/Applications/FreeCAD.app/Contents/Resources/bin/freecadcmd"),
        ]
    )
    which = _which("freecadcmd") or _which("FreeCADCmd")
    if which:
        candidates.append(Path(which))
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def find_freecad_python() -> str | None:
    env = os.environ.get("FREECAD_PYTHON")
    if env and Path(env).exists():
        return env
    cmd = find_freecadcmd()
    if cmd:
        p = Path(cmd).with_name("python.exe")
        if p.exists():
            return str(p)
        p2 = Path(cmd).with_name("python")
        if p2.exists():
            return str(p2)
    return None


def _which(name: str) -> str | None:
    from shutil import which

    return which(name)


class FreeCADSession:
    """Prefer bridge → in-process → FreeCADCmd."""

    def __init__(self) -> None:
        self.backend = self._select_backend()

    def _select_backend(self):
        prefer = (os.environ.get("FREECAD_BACKEND") or "auto").lower()
        if prefer in ("bridge", "auto"):
            bridge = BridgeBackend()
            if bridge.ping():
                return bridge
            if prefer == "bridge":
                raise FreeCADError(
                    f"FreeCAD bridge not reachable at {DEFAULT_BRIDGE_HOST}:{DEFAULT_BRIDGE_PORT}. "
                    "Start FreeCAD and enable the CawFreeCADBridge addon."
                )
        if prefer in ("inprocess", "auto") and _try_import_freecad():
            return InProcessBackend()
        if prefer in ("cmd", "auto"):
            return CmdBackend()
        raise FreeCADError(
            "No FreeCAD backend available. Options:\n"
            "1) Start FreeCAD with CawFreeCADBridge addon\n"
            "2) Run this server with FreeCAD's python.exe\n"
            "3) Set FREECADCMD to FreeCADCmd.exe"
        )

    @property
    def backend_name(self) -> str:
        return self.backend.name

    def execute(self, code: str, *, timeout: float | None = None) -> dict[str, Any]:
        t = timeout if timeout is not None else float(os.environ.get("FREECAD_TIMEOUT", "120"))
        return self.backend.execute(code, timeout=t)

    def status(self) -> dict[str, Any]:
        info: dict[str, Any] = {
            "backend": self.backend_name,
            "bridge_host": DEFAULT_BRIDGE_HOST,
            "bridge_port": DEFAULT_BRIDGE_PORT,
            "freecadcmd": find_freecadcmd(),
            "freecad_python": find_freecad_python(),
            "inprocess_available": _try_import_freecad(),
        }
        try:
            result = self.execute(
                textwrap.dedent(
                    """
                    doc = FreeCAD.ActiveDocument
                    __result__ = {
                        "ok": True,
                        "version": getattr(FreeCAD, "Version", lambda: [])(),
                        "active_document": None if doc is None else doc.Name,
                        "object_count": 0 if doc is None else len(doc.Objects),
                    }
                    """
                ),
                timeout=30.0,
            )
            info["freecad"] = result
            info["ok"] = True
        except Exception as e:
            info["ok"] = False
            info["error"] = str(e)
        return info
