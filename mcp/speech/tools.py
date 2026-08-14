"""MCP tool schemas for speech-to-text."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable

from transcribe import (
    SpeechError,
    api_base,
    api_key,
    backend_available,
    configured_model,
    detect_backend,
    install_deps,
    list_input_devices,
    record_and_transcribe,
    transcribe_file,
    which_ffmpeg,
)

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_speech_status(args: dict[str, Any]) -> dict[str, Any]:
    del args
    backend = detect_backend()
    return {
        "ok": True,
        "backend": backend,
        "available": {
            "faster-whisper": backend_available("faster-whisper"),
            "whisper": backend_available("whisper"),
            "openai": backend_available("openai"),
        },
        "model": configured_model(backend if backend != "none" else "faster-whisper"),
        "api_base": api_base() if backend_available("openai") else None,
        "api_key_set": bool(api_key()),
        "ffmpeg": which_ffmpeg(),
        "cwd": str(Path.cwd()),
        "env": {
            "SPEECH_BACKEND": os.environ.get("SPEECH_BACKEND", "auto"),
            "SPEECH_MODEL": os.environ.get("SPEECH_MODEL") or None,
            "SPEECH_LANGUAGE": os.environ.get("SPEECH_LANGUAGE") or None,
        },
        "hint": (
            "Python extras: speech_install_deps. "
            "ffmpeg CLI: install_program method=winget package=Gyan.FFmpeg"
        ),
    }


def tool_speech_install_deps(args: dict[str, Any]) -> dict[str, Any]:
    pkgs = args.get("packages")
    if pkgs is not None:
        pkgs = [str(p) for p in pkgs]
    return install_deps(pkgs)


def tool_list_models(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return {
        "ok": True,
        "local": [
            "tiny",
            "tiny.en",
            "base",
            "base.en",
            "small",
            "small.en",
            "medium",
            "medium.en",
            "large-v2",
            "large-v3",
            "distil-large-v3",
        ],
        "api": ["whisper-1", "whisper-large-v3", "whisper-large-v3-turbo"],
        "note": "Local ids are for faster-whisper / openai-whisper. API ids depend on SPEECH_BASE_URL.",
    }


def tool_transcribe_file(args: dict[str, Any]) -> dict[str, Any]:
    return transcribe_file(
        args["path"],
        language=args.get("language"),
        translate=bool(args.get("translate", False)),
        timestamps=bool(args.get("timestamps", True)),
        write_sidecar=bool(args.get("write_sidecar", False)),
        sidecar_format=str(args.get("sidecar_format") or "txt"),
        model=args.get("model"),
        backend=args.get("backend"),
    )


def tool_list_input_devices(args: dict[str, Any]) -> dict[str, Any]:
    del args
    devices = list_input_devices()
    return {"ok": True, "devices": devices, "count": len(devices)}


def tool_record_and_transcribe(args: dict[str, Any]) -> dict[str, Any]:
    seconds = float(args.get("seconds") or 8)
    device = args.get("device")
    return record_and_transcribe(
        seconds,
        device=int(device) if device is not None else None,
        language=args.get("language"),
        translate=bool(args.get("translate", False)),
        timestamps=bool(args.get("timestamps", True)),
        write_sidecar=False,
        model=args.get("model"),
        backend=args.get("backend"),
    )


TOOLS: list[dict[str, Any]] = [
    {
        "name": "speech_status",
        "description": (
            "PREFERRED first step: report STT backend (faster-whisper / whisper / OpenAI API), "
            "model, ffmpeg, and whether an API key is set."
        ),
        "inputSchema": _schema({}),
        "handler": tool_speech_status,
    },
    {
        "name": "speech_install_deps",
        "description": (
            "Install Python packages into THIS MCP server's interpreter "
            "(faster-whisper + sounddevice + numpy by default). "
            "ffmpeg is a system CLI — use install_program, not this tool."
        ),
        "inputSchema": _schema(
            {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            }
        ),
        "handler": tool_speech_install_deps,
    },
    {
        "name": "list_speech_models",
        "description": "List common local Whisper model ids and API model names.",
        "inputSchema": _schema({}),
        "handler": tool_list_models,
    },
    {
        "name": "transcribe_file",
        "description": (
            "Speech-to-text from a local audio or video file (wav/mp3/m4a/flac/ogg/webm/mp4…). "
            "Returns transcript text and optional timestamped segments. "
            "Set write_sidecar=true to save .txt/.srt/.vtt next to the file."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Workspace-relative or absolute path to the audio/video file.",
                },
                "language": {
                    "type": "string",
                    "description": "Hint such as zh, en, ja. Empty = auto-detect.",
                },
                "translate": {
                    "type": "boolean",
                    "description": "If true, translate speech into English.",
                    "default": False,
                },
                "timestamps": {
                    "type": "boolean",
                    "description": "Include segment start/end times.",
                    "default": True,
                },
                "write_sidecar": {
                    "type": "boolean",
                    "description": "Write transcript next to the source file.",
                    "default": False,
                },
                "sidecar_format": {
                    "type": "string",
                    "enum": ["txt", "srt", "vtt", "json"],
                    "default": "txt",
                },
                "model": {
                    "type": "string",
                    "description": "Override SPEECH_MODEL (e.g. base, large-v3, whisper-1).",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "faster-whisper", "whisper", "openai"],
                    "description": "Force a backend. Default auto.",
                },
            },
            ["path"],
        ),
        "handler": tool_transcribe_file,
    },
    {
        "name": "list_input_devices",
        "description": "List microphone / input devices for record_and_transcribe (needs sounddevice).",
        "inputSchema": _schema({}),
        "handler": tool_list_input_devices,
    },
    {
        "name": "record_and_transcribe",
        "description": (
            "Record from the default (or given) microphone for N seconds, then transcribe. "
            "Needs: pip install sounddevice numpy"
        ),
        "inputSchema": _schema(
            {
                "seconds": {
                    "type": "number",
                    "description": "How long to record (1–600). Default 8.",
                    "default": 8,
                },
                "device": {
                    "type": "integer",
                    "description": "Device id from list_input_devices. Default = system default mic.",
                },
                "language": {"type": "string"},
                "translate": {"type": "boolean", "default": False},
                "timestamps": {"type": "boolean", "default": True},
                "model": {"type": "string"},
                "backend": {
                    "type": "string",
                    "enum": ["auto", "faster-whisper", "whisper", "openai"],
                },
            }
        ),
        "handler": tool_record_and_transcribe,
    },
]


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in TOOLS
    ]


HANDLERS: dict[str, ToolHandler] = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in HANDLERS:
        raise SpeechError(f"unknown tool: {name}")
    return HANDLERS[name](arguments or {})
