"""TCP JSON-line bridge that runs inside Blender GUI.

Protocol (one JSON object per line):
  request:  {"cmd":"ping"} | {"cmd":"exec","code":"..."}
  response: {"ok":true,"result":{...}} | {"ok":false,"error":"..."}

Exec is scheduled on Blender's main thread via bpy.app.timers.
Set __result__ in code to return structured data.
"""

from __future__ import annotations

import json
import os
import socket
import threading
import traceback
from queue import Empty, Queue

HOST = os.environ.get("BLENDER_BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("BLENDER_BRIDGE_PORT", "54322"))

_request_q: Queue = Queue()
_started = False


def _exec_on_main(code: str) -> dict:
    import bpy

    ns = {"bpy": bpy, "__result__": None}
    try:
        import mathutils

        ns["mathutils"] = mathutils
    except Exception:
        pass
    exec(code, ns, ns)  # noqa: S102
    result = ns.get("__result__")
    if result is None:
        result = {"ok": True}
    if not isinstance(result, dict):
        result = {"ok": True, "result": result}
    return result


def _pump_queue() -> float | None:
    """Blender timer callback — returns seconds until next call."""
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
    return 0.05


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
                        resp = {"ok": False, "error": "timed out waiting for Blender main thread"}
                else:
                    resp = {"ok": False, "error": f"unknown cmd: {cmd}"}
                conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))


def _serve() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((HOST, PORT))
    srv.listen(8)
    try:
        import bpy

        print(f"CawBlenderBridge listening on {HOST}:{PORT}")
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
    import bpy

    if not bpy.app.timers.is_registered(_pump_queue):
        bpy.app.timers.register(_pump_queue, first_interval=0.1, persistent=True)
    threading.Thread(target=_serve, daemon=True).start()
