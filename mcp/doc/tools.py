"""MCP tool schemas for document extract."""

from __future__ import annotations

from typing import Any, Callable

from extract import DocError, extract_text, install_deps, status

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_doc_status(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return status()


def tool_doc_install_deps(args: dict[str, Any]) -> dict[str, Any]:
    pkgs = args.get("packages")
    if pkgs is not None:
        pkgs = [str(p) for p in pkgs]
    return install_deps(pkgs)


def tool_doc_extract(args: dict[str, Any]) -> dict[str, Any]:
    pages = args.get("pages")
    if pages is not None:
        pages = [int(p) for p in pages]
    return extract_text(
        args["path"],
        pages=pages,
        sheet=args.get("sheet"),
        write_sidecar=bool(args.get("write_sidecar", False)),
    )


TOOLS: list[dict[str, Any]] = [
    {
        "name": "doc_status",
        "description": (
            "PREFERRED first step: report document backends (zip Office always on; "
            "PDF via pdftotext or pypdf; pandoc for legacy .doc)."
        ),
        "inputSchema": _schema({}),
        "handler": tool_doc_status,
    },
    {
        "name": "doc_install_deps",
        "description": (
            "Install Python packages into THIS MCP server's interpreter (pypdf by default). "
            "pdftotext is a system CLI — use install_program for Poppler."
        ),
        "inputSchema": _schema(
            {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            }
        ),
        "handler": tool_doc_install_deps,
    },
    {
        "name": "doc_extract",
        "description": (
            "Extract text from a local document (pdf/docx/xlsx/pptx/odt/epub/html/rtf/csv). "
            "Optional pages=[1,2] for PDF, sheet=Name for Excel. "
            "Set write_sidecar=true to save <file>.txt next to the document."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Workspace-relative or absolute document path.",
                },
                "pages": {
                    "type": "array",
                    "items": {"type": "integer"},
                    "description": "Optional 1-based PDF page numbers.",
                },
                "sheet": {
                    "type": "string",
                    "description": "Optional Excel sheet name or 1-based index.",
                },
                "write_sidecar": {
                    "type": "boolean",
                    "description": "Write extracted text next to the file.",
                    "default": False,
                },
            },
            ["path"],
        ),
        "handler": tool_doc_extract,
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
        raise DocError(f"unknown tool: {name}")
    return HANDLERS[name](arguments or {})
