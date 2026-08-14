"""JSON-RPC over stdio: NDJSON (MCP spec) with Content-Length fallback."""

from __future__ import annotations

import json
import sys
from typing import Any, Iterator, TextIO


def write_message(msg: dict[str, Any], stream: TextIO | None = None) -> None:
    stream = stream or sys.stdout
    body = json.dumps(msg, ensure_ascii=False, separators=(",", ":"))
    stream.buffer.write(body.encode("utf-8"))
    stream.buffer.write(b"\n")
    stream.buffer.flush()


def read_message(stream: TextIO | None = None) -> dict[str, Any] | None:
    stream = stream or sys.stdin
    buf = stream.buffer
    line = buf.readline()
    if not line:
        return None
    stripped = line.lstrip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return json.loads(line.decode("utf-8"))
    content_length: int | None = None
    while True:
        if line in (b"\r\n", b"\n"):
            break
        lower = line.decode("ascii", errors="replace").lower()
        if lower.startswith("content-length:"):
            content_length = int(lower.split(":", 1)[1].strip())
        line = buf.readline()
        if not line:
            return None
    if content_length is None:
        raise ValueError("missing Content-Length header")
    data = buf.read(content_length)
    if len(data) < content_length:
        return None
    return json.loads(data.decode("utf-8"))


def iter_messages(stream: TextIO | None = None) -> Iterator[dict[str, Any]]:
    while True:
        msg = read_message(stream)
        if msg is None:
            break
        yield msg


def ok_result(id_: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result}


def err_result(id_: Any, code: int, message: str, data: Any = None) -> dict[str, Any]:
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": id_, "error": err}


def tool_text(text: str, *, is_error: bool = False) -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": text}],
        "isError": is_error,
    }


def tool_json(payload: Any, *, is_error: bool = False) -> dict[str, Any]:
    return tool_text(json.dumps(payload, ensure_ascii=False, indent=2), is_error=is_error)
