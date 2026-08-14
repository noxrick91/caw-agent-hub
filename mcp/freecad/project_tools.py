"""Project management tools for FreeCAD MCP workspaces."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any, Callable

from backend import FreeCADError, FreeCADSession

ToolHandler = Callable[[FreeCADSession, dict[str, Any]], dict[str, Any]]

PROJECT_MARK = ".freecad-project.json"
DEFAULT_LAYOUT = ("parts", "assemblies", "drawings", "exports", "animations", "docs")


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _project_root(args: dict[str, Any] | None = None) -> Path:
    args = args or {}
    raw = args.get("project_root") or os.environ.get("FREECAD_PROJECT_ROOT") or ""
    if raw:
        return Path(raw).expanduser().resolve()
    return Path.cwd().resolve()


def _read_meta(root: Path) -> dict[str, Any] | None:
    mark = root / PROJECT_MARK
    if not mark.is_file():
        return None
    try:
        return json.loads(mark.read_text(encoding="utf-8"))
    except Exception:
        return {"name": root.name, "corrupt": True}


def _write_meta(root: Path, meta: dict[str, Any]) -> None:
    mark = root / PROJECT_MARK
    mark.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def tool_create_project(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del session
    if args.get("path"):
        root = Path(args["path"]).expanduser().resolve()
    else:
        name = (args.get("name") or "freecad-project").strip() or "freecad-project"
        root = Path.cwd().resolve() / name

    if (root / PROJECT_MARK).is_file() and not args.get("force"):
        raise FreeCADError(f"project already exists at {root} (pass force=true)")

    root.mkdir(parents=True, exist_ok=True)
    folders = list(args.get("folders") or DEFAULT_LAYOUT)
    created = []
    for folder in folders:
        p = root / str(folder)
        p.mkdir(parents=True, exist_ok=True)
        created.append(str(p))

    meta = {
        "name": args.get("label") or root.name,
        "version": 1,
        "folders": folders,
        "units": args.get("units") or "mm",
        "description": args.get("description") or "",
    }
    _write_meta(root, meta)
    readme = root / "docs" / "README.md"
    if not readme.exists():
        readme.parent.mkdir(parents=True, exist_ok=True)
        readme.write_text(
            f"# {meta['name']}\n\nFreeCAD project managed via caw-agent MCP.\n"
            f"- parts/ — part documents (.FCStd)\n"
            f"- assemblies/ — assembly documents\n"
            f"- drawings/ — TechDraw / schematics\n"
            f"- exports/ — STEP/STL/SVG\n"
            f"- animations/ — frame sequences\n",
            encoding="utf-8",
        )
    os.environ["FREECAD_PROJECT_ROOT"] = str(root)
    return {
        "ok": True,
        "project_root": str(root),
        "meta": meta,
        "folders": created,
        "hint": "FREECAD_PROJECT_ROOT set for this MCP process",
    }


def tool_project_status(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del session
    root = _project_root(args)
    meta = _read_meta(root)
    files: list[dict[str, Any]] = []
    if root.is_dir():
        for p in sorted(root.rglob("*.FCStd")):
            rel = str(p.relative_to(root)).replace("\\", "/")
            files.append({"path": rel, "abs": str(p), "size": p.stat().st_size})
    return {
        "ok": True,
        "project_root": str(root),
        "is_project": meta is not None,
        "meta": meta,
        "fcstd_count": len(files),
        "documents": files[:200],
    }


def tool_list_project_files(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del session
    root = _project_root(args)
    if not root.is_dir():
        raise FreeCADError(f"project root not found: {root}")
    pattern = (args.get("glob") or "**/*").strip() or "**/*"
    exts = args.get("extensions")
    if isinstance(exts, str):
        exts = [exts]
    out = []
    for p in sorted(root.glob(pattern)):
        if not p.is_file():
            continue
        if exts and p.suffix.lstrip(".").lower() not in {e.lstrip(".").lower() for e in exts}:
            continue
        rel = str(p.relative_to(root)).replace("\\", "/")
        out.append({"path": rel, "abs": str(p), "size": p.stat().st_size})
        if len(out) >= int(args.get("max_results") or 200):
            break
    return {"ok": True, "project_root": str(root), "files": out, "count": len(out)}


def tool_set_project_root(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del session
    root = Path(args["path"]).expanduser().resolve()
    if not root.is_dir():
        raise FreeCADError(f"not a directory: {root}")
    os.environ["FREECAD_PROJECT_ROOT"] = str(root)
    meta = _read_meta(root)
    return {"ok": True, "project_root": str(root), "is_project": meta is not None, "meta": meta}


def tool_new_part_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    root = _project_root(args)
    name = (args.get("name") or "Part").strip() or "Part"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    folder = root / (args.get("folder") or "parts")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{safe}.FCStd"
    if path.exists() and not args.get("overwrite"):
        raise FreeCADError(f"exists: {path} (pass overwrite=true)")
    label = args.get("label") or name
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.newDocument({safe!r})
        doc.Label = {label!r}
        doc.saveAs({str(path)!r})
        __result__ = {{
            "ok": True,
            "document": doc.Name,
            "label": doc.Label,
            "path": {str(path)!r},
            "kind": "part",
        }}
        """
    )
    return session.execute(code)


def tool_new_assembly_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    root = _project_root(args)
    name = (args.get("name") or "Assembly").strip() or "Assembly"
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in name)
    folder = root / (args.get("folder") or "assemblies")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{safe}.FCStd"
    if path.exists() and not args.get("overwrite"):
        raise FreeCADError(f"exists: {path} (pass overwrite=true)")
    label = args.get("label") or name
    create_asm = bool(args.get("create_assembly", True))
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.newDocument({safe!r})
        doc.Label = {label!r}
        asm_name = None
        mode = None
        if {create_asm!r}:
            try:
                import Assembly
                asm = doc.addObject("Assembly::AssemblyObject", "Assembly")
                asm.Label = {label!r}
                asm_name = asm.Name
                mode = "assembly"
            except Exception:
                asm = doc.addObject("App::Part", "Assembly")
                asm.Label = {label!r}
                asm_name = asm.Name
                mode = "part"
        doc.recompute()
        doc.saveAs({str(path)!r})
        __result__ = {{
            "ok": True,
            "document": doc.Name,
            "label": doc.Label,
            "path": {str(path)!r},
            "kind": "assembly",
            "assembly": asm_name,
            "mode": mode,
        }}
        """
    )
    return session.execute(code)


def tool_open_project_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    root = _project_root(args)
    rel = args["path"]
    path = Path(rel)
    if not path.is_absolute():
        path = (root / rel).resolve()
    if not path.is_file():
        raise FreeCADError(f"file not found: {path}")
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.open({str(path)!r})
        __result__ = {{
            "ok": True,
            "document": doc.Name,
            "label": doc.Label,
            "path": {str(path)!r},
        }}
        """
    )
    return session.execute(code)


def tool_save_project_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    root = _project_root(args)
    path = args.get("path")
    sub = args.get("subdir")
    name = args.get("filename")
    if path:
        out = Path(path)
        if not out.is_absolute():
            out = root / out
    elif name:
        folder = root / (sub or "parts")
        folder.mkdir(parents=True, exist_ok=True)
        out = folder / name
        if out.suffix.lower() != ".fcstd":
            out = out.with_suffix(".FCStd")
    else:
        out = None

    if out is None:
        code = textwrap.dedent(
            """
            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise RuntimeError("no active document")
            if not doc.FileName:
                raise RuntimeError("document has no path; pass path= or filename=")
            doc.save()
            __result__ = {"ok": True, "document": doc.Name, "path": doc.FileName}
            """
        )
    else:
        out.parent.mkdir(parents=True, exist_ok=True)
        code = textwrap.dedent(
            f"""
            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise RuntimeError("no active document")
            doc.saveAs({str(out)!r})
            __result__ = {{"ok": True, "document": doc.Name, "path": {str(out)!r}}}
            """
        )
    return session.execute(code)


PROJECT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_project",
        "description": (
            "Create a FreeCAD project folder (parts/assemblies/drawings/exports/animations) "
            "with .freecad-project.json and set FREECAD_PROJECT_ROOT for this MCP process."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string", "description": "Project folder name (when path omitted)"},
                "path": {"type": "string", "description": "Absolute/relative project root to create"},
                "label": {"type": "string"},
                "description": {"type": "string"},
                "units": {"type": "string", "default": "mm"},
                "folders": {"type": "array", "items": {"type": "string"}},
                "force": {"type": "boolean", "default": False},
            }
        ),
        "handler": tool_create_project,
    },
    {
        "name": "project_status",
        "description": "Show current FreeCAD project root, metadata, and .FCStd inventory.",
        "inputSchema": _schema({"project_root": {"type": "string"}}),
        "handler": tool_project_status,
    },
    {
        "name": "set_project_root",
        "description": "Set FREECAD_PROJECT_ROOT for subsequent project-relative tools.",
        "inputSchema": _schema({"path": {"type": "string"}}, ["path"]),
        "handler": tool_set_project_root,
    },
    {
        "name": "list_project_files",
        "description": "List files under the project root (optional glob / extensions filter).",
        "inputSchema": _schema(
            {
                "project_root": {"type": "string"},
                "glob": {"type": "string", "default": "**/*"},
                "extensions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g. [\"FCStd\",\"step\",\"svg\"]",
                },
                "max_results": {"type": "integer", "default": 200},
            }
        ),
        "handler": tool_list_project_files,
    },
    {
        "name": "new_part_document",
        "description": "Create and save a new part document under project parts/ (or folder=).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "folder": {"type": "string", "default": "parts"},
                "project_root": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            }
        ),
        "handler": tool_new_part_document,
    },
    {
        "name": "new_assembly_document",
        "description": "Create and save a new assembly document under assemblies/, optionally with an Assembly container.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "folder": {"type": "string", "default": "assemblies"},
                "create_assembly": {"type": "boolean", "default": True},
                "project_root": {"type": "string"},
                "overwrite": {"type": "boolean", "default": False},
            }
        ),
        "handler": tool_new_assembly_document,
    },
    {
        "name": "open_project_document",
        "description": "Open a project-relative or absolute .FCStd document.",
        "inputSchema": _schema(
            {"path": {"type": "string"}, "project_root": {"type": "string"}},
            ["path"],
        ),
        "handler": tool_open_project_document,
    },
    {
        "name": "save_project_document",
        "description": "Save active document into the project (path= or filename= under subdir).",
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "filename": {"type": "string"},
                "subdir": {"type": "string", "default": "parts"},
                "project_root": {"type": "string"},
            }
        ),
        "handler": tool_save_project_document,
    },
]
