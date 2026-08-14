"""MCP tool schemas for OCR."""

from __future__ import annotations

from typing import Any, Callable

from recognize import OcrError, install_deps, ocr_image, status

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_ocr_status(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return status()


def tool_ocr_install_deps(args: dict[str, Any]) -> dict[str, Any]:
    pkgs = args.get("packages")
    if pkgs is not None:
        pkgs = [str(p) for p in pkgs]
    return install_deps(pkgs)


def tool_ocr_languages(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return {
        "ok": True,
        "tesseract": [
            "eng",
            "chi_sim",
            "chi_tra",
            "chi_sim+eng",
            "jpn",
            "kor",
            "fra",
            "deu",
        ],
        "easyocr": ["ch_sim", "ch_tra", "en", "ja", "ko"],
        "paddleocr": ["ch", "en", "chinese_cht", "japan", "korean"],
        "note": "Tesseract needs the matching traineddata installed (e.g. chi_sim).",
    }


def tool_ocr_image(args: dict[str, Any]) -> dict[str, Any]:
    return ocr_image(
        args["path"],
        lang=args.get("lang"),
        box=args.get("box"),
        backend=args.get("backend"),
        write_sidecar=bool(args.get("write_sidecar", False)),
    )


TOOLS: list[dict[str, Any]] = [
    {
        "name": "ocr_status",
        "description": (
            "PREFERRED first step: report OCR backend (tesseract / easyocr / paddleocr / "
            "OpenAI-compatible vision) and install hints."
        ),
        "inputSchema": _schema({}),
        "handler": tool_ocr_status,
    },
    {
        "name": "ocr_install_deps",
        "description": (
            "Install Python packages into THIS MCP server's interpreter "
            "(Pillow + pytesseract by default). "
            "Does not install the Tesseract-OCR binary — use install_program for that. "
            "Call this when ocr_status shows pytesseract missing."
        ),
        "inputSchema": _schema(
            {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Override defaults, e.g. [\"easyocr\"] or [\"paddleocr\",\"paddlepaddle\"].",
                }
            }
        ),
        "handler": tool_ocr_install_deps,
    },
    {
        "name": "ocr_languages",
        "description": "List common language ids for each OCR backend.",
        "inputSchema": _schema({}),
        "handler": tool_ocr_languages,
    },
    {
        "name": "ocr_image",
        "description": (
            "Extract printed or handwritten-ish text from a local image (png/jpg/webp/tiff…). "
            "Optional box=[x,y,w,h] to read only a region. "
            "Set write_sidecar=true to save <stem>.ocr.txt next to the image."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Workspace-relative or absolute image path.",
                },
                "lang": {
                    "type": "string",
                    "description": (
                        "Language hint. Tesseract: chi_sim+eng (default). "
                        "EasyOCR: ch_sim,en. Paddle: ch / en."
                    ),
                },
                "box": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Optional crop [x, y, width, height] before OCR.",
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "tesseract", "easyocr", "paddleocr", "openai"],
                    "description": "Force a backend. Default auto.",
                },
                "write_sidecar": {
                    "type": "boolean",
                    "description": "Write extracted text next to the image as .ocr.txt.",
                    "default": False,
                },
            },
            ["path"],
        ),
        "handler": tool_ocr_image,
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
        raise OcrError(f"unknown tool: {name}")
    return HANDLERS[name](arguments or {})
