"""TCP JSON-line bridge that runs inside FreeCAD GUI.

Protocol (one JSON object per line):
  request:  {"cmd":"ping"} | {"cmd":"exec","code":"..."}
  response: {"ok":true,"result":{...}} | {"ok":false,"error":"..."}

Exec runs on the FreeCAD main thread via QTimer so GUI APIs are safe.
Set __result__ in code to return structured data.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import traceback
from queue import Empty, Queue

HOST = os.environ.get("FREECAD_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("FREECAD_BRIDGE_PORT", "54321"))

_request_q: Queue = Queue()
_started = False


def _exec_on_main(code: str) -> dict:
    import FreeCAD

    ns = {
        "FreeCAD": FreeCAD,
        "__result__": None,
    }
    for mod_name in (
        "Part",
        "Draft",
        "Sketcher",
        "PartDesign",
        "Mesh",
        "Import",
        "FreeCADGui",
        "UtilsAssembly",
        "JointObject",
        "CommandCreateJoint",
    ):
        try:
            ns[mod_name] = __import__(mod_name)
        except Exception:
            pass

    exec(code, ns, ns)  # noqa: S102
    doc = FreeCAD.ActiveDocument
    if doc is not None:
        try:
            doc.recompute()
        except Exception:
            pass
        try:
            import FreeCADGui

            FreeCADGui.updateGui()
        except Exception:
            pass

    result = ns.get("__result__")
    if result is None:
        result = {"ok": True}
    if not isinstance(result, dict):
        result = {"ok": True, "result": result}
    return result


def _pump_queue():
    """Called periodically on the GUI thread."""
    try:
        while True:
            item = _request_q.get_nowait()
            code = item["code"]
            reply_q = item["reply"]
            try:
                result = _exec_on_main(code)
                reply_q.put({"ok": True, "result": result})
            except Exception as e:
                reply_q.put(
                    {
                        "ok": False,
                        "error": f"{type(e).__name__}: {e}",
                        "traceback": traceback.format_exc(),
                    }
                )
    except Empty:
        pass
    return True  # keep timer alive


def _handle_client(conn: socket.socket) -> None:
    with conn:
        buf = b""
        while True:
            chunk = conn.recv(65536)
            if not chunk:
                break
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                if not line.strip():
                    continue
                try:
                    req = json.loads(line.decode("utf-8"))
                except Exception as e:
                    resp = {"ok": False, "error": f"bad json: {e}"}
                    conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))
                    continue

                cmd = req.get("cmd")
                if cmd == "ping":
                    resp = {"ok": True, "pong": True, "port": PORT}
                elif cmd == "exec":
                    reply_q: Queue = Queue()
                    _request_q.put({"code": req.get("code", ""), "reply": reply_q})
                    try:
                        resp = reply_q.get(timeout=float(req.get("timeout", 120)))
                    except Empty:
                        resp = {"ok": False, "error": "timed out waiting for FreeCAD main thread"}
                else:
                    resp = {"ok": False, "error": f"unknown cmd: {cmd}"}
                conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))


def _serve() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(8)
    try:
        import FreeCAD

        FreeCAD.Console.PrintMessage(f"CawFreeCADBridge listening on {HOST}:{PORT}\n")
    except Exception:
        pass
    while True:
        conn, _addr = srv.accept()
        threading.Thread(target=_handle_client, args=(conn,), daemon=True).start()


def start_bridge_background() -> None:
    global _started
    if _started:
        return
    _started = True

    # Pump exec queue on GUI thread
    try:
        from PySide import QtCore  # FreeCAD 0.21
    except ImportError:
        try:
            from PySide2 import QtCore
        except ImportError:
            from PySide6 import QtCore

    timer = QtCore.QTimer()
    timer.setInterval(50)
    timer.timeout.connect(_pump_queue)
    timer.start()
    # Keep a reference so GC won't collect the timer
    start_bridge_background._timer = timer  # type: ignore[attr-defined]

    threading.Thread(target=_serve, name="caw-freecad-bridge", daemon=True).start()
