"""Blender ↔ FreeCAD handoff helpers (mm mesh exchange)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import Any, Callable

from backend import FreeCADError, FreeCADSession

ToolHandler = Callable[[FreeCADSession, dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_export_for_blender(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Export solids/meshes as STL/OBJ for Blender rendering (dimensions in mm)."""
    path = args["path"]
    fmt = (args.get("format") or Path(path).suffix.lstrip(".") or "stl").lower()
    if fmt not in {"stl", "obj"}:
        raise FreeCADError("export_for_blender supports stl|obj for mesh handoff to Blender")
    names = args.get("objects")
    # Optional: also write a tiny sidecar note
    write_note = bool(args.get("write_note", True))
    code = textwrap.dedent(
        f"""
        import os, json
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        path = {path!r}
        fmt = {fmt!r}
        names = {json.dumps(names)}
        objs = []
        if names:
            for n in names:
                o = doc.getObject(n)
                if o is None:
                    raise RuntimeError(f"object not found: {{n}}")
                objs.append(o)
        else:
            objs = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
            if not objs:
                raise RuntimeError("no solids to export")
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        import Mesh
        # Tessellate Part shapes into a compound mesh when needed
        meshes = []
        for o in objs:
            if o.isDerivedFrom("Mesh::Feature"):
                meshes.append(o.Mesh)
            elif hasattr(o, "Shape") and not o.Shape.isNull():
                m = None
                try:
                    import MeshPart
                    m = MeshPart.meshFromShape(
                        Shape=o.Shape, LinearDeflection=0.1, AngularDeflection=0.5
                    )
                except Exception:
                    m = None
                if m is None:
                    verts, facets = o.Shape.tessellate(0.1)
                    m = Mesh.Mesh([tuple(v) for v in verts], facets)
                meshes.append(m)
            else:
                continue
        if not meshes:
            raise RuntimeError("nothing meshable to export")
        out = meshes[0]
        for m in meshes[1:]:
            out.addMesh(m)
        # Write via temporary Mesh::Feature
        tmp = doc.addObject("Mesh::Feature", "CawHandoffMesh")
        tmp.Mesh = out
        Mesh.export([tmp], path)
        doc.removeObject(tmp.Name)
        note_path = None
        if {write_note!r}:
            note_path = path + ".caw-handoff.json"
            with open(note_path, "w", encoding="utf-8") as f:
                json.dump({{
                    "source": "freecad",
                    "units": "mm",
                    "format": fmt,
                    "objects": [o.Name for o in objs],
                    "blender": "import_from_freecad with set_mm_units=true",
                }}, f, indent=2)
        __result__ = {{
            "ok": True,
            "path": path,
            "format": fmt,
            "units": "mm",
            "objects": [o.Name for o in objs],
            "note_path": note_path,
            "handoff": "blender",
            "next": "Blender import_from_freecad path=… then setup_lookdev + render_image",
        }}
        """
    )
    return session.execute(code)


def tool_import_from_blender(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Import Blender mesh (STL/OBJ). scale=1 if Blender used export_for_freecad; else pass scale."""
    path = args["path"]
    scale = float(args.get("scale") or 1.0)
    label = args.get("label") or "FromBlender"
    code = textwrap.dedent(
        f"""
        import os
        path = {path!r}
        if not os.path.exists(path):
            raise RuntimeError(f"file not found: {{path}}")
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        before = set(o.Name for o in doc.Objects)
        lower = path.lower()
        if lower.endswith(".stl"):
            import Mesh
            Mesh.insert(path, doc.Name)
        elif lower.endswith(".obj"):
            import Mesh
            try:
                Mesh.insert(path, doc.Name)
            except Exception:
                # Some builds want Import
                import Import
                Import.insert(path, doc.Name)
        else:
            raise RuntimeError("import_from_blender supports stl|obj")
        imported = [o for o in doc.Objects if o.Name not in before]
        scale = float({scale})
        label = {label!r}
        names = []
        for o in imported:
            o.Label = label if len(imported) == 1 else f"{{label}}_{{o.Name}}"
            if abs(scale - 1.0) > 1e-12 and hasattr(o, "Mesh"):
                m = o.Mesh.copy()
                m.scale(scale, scale, scale)
                o.Mesh = m
            names.append(o.Name)
        doc.recompute()
        __result__ = {{
            "ok": True,
            "path": path,
            "imported": names,
            "scale": scale,
            "units": "mm (FreeCAD)",
            "handoff": "from_blender",
            "next": "create_assembly / insert_component / mate_components as needed",
        }}
        """
    )
    return session.execute(code)


HANDOFF_TOOLS: list[dict[str, Any]] = [
    {
        "name": "export_for_blender",
        "description": (
            "Export solids as STL/OBJ for Blender rendering (mm). "
            "Then Blender: import_from_freecad → setup_lookdev → render_image."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "format": {"type": "string", "enum": ["stl", "obj"]},
                "objects": {"type": "array", "items": {"type": "string"}},
                "write_note": {"type": "boolean", "default": True},
            },
            ["path"],
        ),
        "handler": tool_export_for_blender,
    },
    {
        "name": "import_from_blender",
        "description": (
            "Import Blender STL/OBJ for assembly. If Blender used export_for_freecad, keep scale=1. "
            "If Blender exported raw meters STL, use scale=1000."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "scale": {"type": "number", "default": 1},
                "label": {"type": "string"},
            },
            ["path"],
        ),
        "handler": tool_import_from_blender,
    },
]
