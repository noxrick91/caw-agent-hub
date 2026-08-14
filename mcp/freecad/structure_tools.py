"""Structure helpers: patterns, mounting bosses, ribs for shell parts."""

from __future__ import annotations

import json
import textwrap
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


def _unique_name(preferred: str | None, fallback: str) -> str:
    name = (preferred or fallback).strip() or fallback
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return safe or fallback


_ST_HELPERS = r'''
def _st_find(doc, name):
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")
'''


def tool_pattern_linear(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    count = int(args.get("count") or 2)
    if count < 2:
        raise FreeCADError("count must be >= 2")
    spacing = args.get("spacing") or [10, 0, 0]
    if not (isinstance(spacing, (list, tuple)) and len(spacing) >= 3):
        raise FreeCADError("spacing must be [dx,dy,dz]")
    fuse = bool(args.get("fuse", True))
    out_name = _unique_name(args.get("result_name"), f"{name}_pattern")
    keep = bool(args.get("keep_original", False))
    code = textwrap.dedent(
        f"""
        import Part
        {_ST_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _st_find(doc, {name!r})
        base = src.Shape
        shapes = [base]
        dx, dy, dz = {float(spacing[0])}, {float(spacing[1])}, {float(spacing[2])}
        for i in range(1, {count}):
            s = base.copy()
            s.translate(FreeCAD.Vector(dx * i, dy * i, dz * i))
            shapes.append(s)
        if {fuse!r}:
            result = shapes[0]
            for s in shapes[1:]:
                result = result.fuse(s)
            obj = doc.addObject("Part::Feature", {out_name!r})
            obj.Shape = result.removeSplitter()
            names = [obj.Name]
        else:
            names = []
            for i, s in enumerate(shapes):
                o = doc.addObject("Part::Feature", f"{out_name}_{{i}}")
                o.Shape = s
                names.append(o.Name)
        if not {keep!r}:
            doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{"ok": True, "names": names, "count": {count}, "fused": {fuse!r}}}
        """
    )
    return session.execute(code)


def tool_pattern_polar(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    count = int(args.get("count") or 4)
    if count < 2:
        raise FreeCADError("count must be >= 2")
    angle = float(args.get("angle", 360.0))
    center = args.get("center") or [0, 0, 0]
    axis = args.get("axis") or [0, 0, 1]
    fuse = bool(args.get("fuse", True))
    out_name = _unique_name(args.get("result_name"), f"{name}_polar")
    keep = bool(args.get("keep_original", False))
    code = textwrap.dedent(
        f"""
        import Part
        {_ST_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _st_find(doc, {name!r})
        base = src.Shape
        shapes = [base]
        cen = FreeCAD.Vector({float(center[0])}, {float(center[1])}, {float(center[2])})
        ax = FreeCAD.Vector({float(axis[0])}, {float(axis[1])}, {float(axis[2])})
        step = {angle} / float({count} if abs({angle} - 360.0) < 1e-6 else max({count} - 1, 1))
        # Full circle: count instances evenly; partial arc: count includes original
        n_extra = {count} - 1
        if abs({angle} - 360.0) < 1e-6:
            step = 360.0 / {count}
            n_extra = {count} - 1
        for i in range(1, n_extra + 1):
            s = base.copy()
            s.rotate(cen, ax, step * i)
            shapes.append(s)
        if {fuse!r}:
            result = shapes[0]
            for s in shapes[1:]:
                result = result.fuse(s)
            obj = doc.addObject("Part::Feature", {out_name!r})
            obj.Shape = result.removeSplitter()
            names = [obj.Name]
        else:
            names = []
            for i, s in enumerate(shapes):
                o = doc.addObject("Part::Feature", f"{out_name}_{{i}}")
                o.Shape = s
                names.append(o.Name)
        if not {keep!r}:
            doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{"ok": True, "names": names, "count": len(shapes), "fused": {fuse!r}}}
        """
    )
    return session.execute(code)


def tool_add_mounting_boss(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Cylindrical boss with optional through-hole — screw posts inside shells."""
    name = _unique_name(args.get("name"), "Boss")
    outer_d = float(args.get("outer_diameter") or args.get("diameter") or 8.0)
    height = float(args.get("height") or 6.0)
    hole_d = float(args.get("hole_diameter") or 0.0)
    base = args.get("base") or [0, 0, 0]
    direction = args.get("direction") or [0, 0, 1]
    target = args.get("fuse_with")
    code = textwrap.dedent(
        f"""
        import Part
        {_ST_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        origin = FreeCAD.Vector({float(base[0])}, {float(base[1])}, {float(base[2])})
        direction = FreeCAD.Vector({float(direction[0])}, {float(direction[1])}, {float(direction[2])})
        if direction.Length < 1e-9:
            direction = FreeCAD.Vector(0, 0, 1)
        direction.normalize()
        boss = Part.makeCylinder({outer_d}/2.0, {height}, origin, direction)
        if {hole_d} > 0:
            hole = Part.makeCylinder({hole_d}/2.0, {height} + 2, origin - direction, direction)
            boss = boss.cut(hole)
        fuse_with = {json.dumps(target)}
        if fuse_with:
            src = _st_find(doc, fuse_with)
            shape = src.Shape.fuse(boss).removeSplitter()
            obj = doc.addObject("Part::Feature", {name!r})
            obj.Shape = shape
            doc.removeObject(src.Name)
        else:
            obj = doc.addObject("Part::Feature", {name!r})
            obj.Shape = boss
        obj.Label = {args.get("label") or name!r}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "outer_diameter": {outer_d},
            "hole_diameter": {hole_d},
            "height": {height},
            "fused_with": fuse_with,
        }}
        """
    )
    return session.execute(code)


def tool_add_rib(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Rectangular stiffening rib box, optionally fused onto a shell."""
    name = _unique_name(args.get("name"), "Rib")
    length = float(args.get("length") or 20)
    height = float(args.get("height") or 8)
    thickness = float(args.get("thickness") or 1.5)
    base = args.get("base") or [0, 0, 0]
    # Rib extruded along +Z by default, length along X
    target = args.get("fuse_with")
    code = textwrap.dedent(
        f"""
        import Part
        {_ST_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        rib = Part.makeBox({length}, {thickness}, {height})
        rib.translate(FreeCAD.Vector({float(base[0])}, {float(base[1])}, {float(base[2])}))
        fuse_with = {json.dumps(target)}
        if fuse_with:
            src = _st_find(doc, fuse_with)
            shape = src.Shape.fuse(rib).removeSplitter()
            obj = doc.addObject("Part::Feature", {name!r})
            obj.Shape = shape
            doc.removeObject(src.Name)
        else:
            obj = doc.addObject("Part::Feature", {name!r})
            obj.Shape = rib
        obj.Label = {args.get("label") or name!r}
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "size": [{length}, {thickness}, {height}], "fused_with": fuse_with}}
        """
    )
    return session.execute(code)


STRUCTURE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "pattern_linear",
        "description": "Linear pattern of a solid (vent slots, screw posts grid). spacing=[dx,dy,dz].",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "count": {"type": "integer", "default": 2},
                "spacing": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "fuse": {"type": "boolean", "default": True},
                "result_name": {"type": "string"},
                "keep_original": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        "handler": tool_pattern_linear,
    },
    {
        "name": "pattern_polar",
        "description": "Polar pattern around center/axis (speaker grill holes, bolt circles).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "count": {"type": "integer", "default": 4},
                "angle": {"type": "number", "default": 360},
                "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "fuse": {"type": "boolean", "default": True},
                "result_name": {"type": "string"},
                "keep_original": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        "handler": tool_pattern_polar,
    },
    {
        "name": "add_mounting_boss",
        "description": "Add a cylindrical screw boss (optional hole). Optionally fuse_with an existing shell solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "outer_diameter": {"type": "number", "default": 8},
                "hole_diameter": {"type": "number", "default": 0},
                "height": {"type": "number", "default": 6},
                "base": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "direction": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "fuse_with": {"type": "string"},
            }
        ),
        "handler": tool_add_mounting_boss,
    },
    {
        "name": "add_rib",
        "description": "Add a rectangular stiffening rib; optionally fuse_with a shell.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "length": {"type": "number", "default": 20},
                "height": {"type": "number", "default": 8},
                "thickness": {"type": "number", "default": 1.5},
                "base": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "fuse_with": {"type": "string"},
            }
        ),
        "handler": tool_add_rib,
    },
]
