"""Parametric part generators for FreeCAD MCP."""

from __future__ import annotations

import textwrap
from typing import Any, Callable

from backend import FreeCADSession

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


def _placement_code(placement: Any) -> str:
    if not placement:
        return ""
    base = placement.get("base") if isinstance(placement, dict) else None
    if isinstance(base, (list, tuple)) and len(base) >= 3:
        b = (float(base[0]), float(base[1]), float(base[2]))
    else:
        b = (0.0, 0.0, 0.0)
    rot = placement.get("rotation") if isinstance(placement, dict) else None
    if rot and isinstance(rot, dict):
        axis = rot.get("axis") or [0, 0, 1]
        a = (float(axis[0]), float(axis[1]), float(axis[2]))
        angle = float(rot.get("angle", 0.0))
        return textwrap.dedent(
            f"""
            obj.Placement = FreeCAD.Placement(
                FreeCAD.Vector{b},
                FreeCAD.Rotation(FreeCAD.Vector{a}, {angle})
            )
            """
        )
    return f"obj.Placement = FreeCAD.Placement(FreeCAD.Vector{b}, FreeCAD.Rotation())\n"


PLACEMENT_PROP = {
    "type": "object",
    "description": "Optional placement: {base:[x,y,z], rotation:{axis:[x,y,z], angle:degrees}}",
    "properties": {
        "base": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
        "rotation": {
            "type": "object",
            "properties": {
                "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "angle": {"type": "number"},
            },
        },
    },
}


def tool_generate_part_plate(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Plate")
    length = float(args.get("length") or 100)
    width = float(args.get("width") or 60)
    thickness = float(args.get("thickness") or 5)
    hole_d = float(args.get("hole_diameter") or 0)
    hole_count = int(args.get("hole_count") or 0)
    margin = float(args.get("hole_margin") or 10)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        plate = Part.makeBox({length}, {width}, {thickness})
        if {hole_d} > 0 and {hole_count} > 0:
            import math
            r = {hole_d} / 2.0
            n = {hole_count}
            mx, my = {margin}, {margin}
            # Distribute holes along a rectangle inset
            pts = []
            if n == 1:
                pts = [({length}/2, {width}/2)]
            elif n == 2:
                pts = [(mx, {width}/2), ({length}-mx, {width}/2)]
            elif n == 4:
                pts = [(mx, my), ({length}-mx, my), (mx, {width}-my), ({length}-mx, {width}-my)]
            else:
                for i in range(n):
                    t = i / max(n - 1, 1)
                    pts.append((mx + t * ({length} - 2*mx), {width}/2))
            for x, y in pts:
                cyl = Part.makeCylinder(r, {thickness} + 2, FreeCAD.Vector(x, y, -1))
                plate = plate.cut(cyl)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = plate
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": "plate",
            "size": [{length}, {width}, {thickness}],
            "holes": {hole_count if hole_d > 0 else 0},
        }}
        """
    )
    return session.execute(code)


def tool_generate_part_shaft(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Shaft")
    diameter = float(args.get("diameter") or 20)
    length = float(args.get("length") or 80)
    shoulder_d = float(args.get("shoulder_diameter") or 0)
    shoulder_len = float(args.get("shoulder_length") or 0)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        r = {diameter} / 2.0
        shaft = Part.makeCylinder(r, {length})
        if {shoulder_d} > {diameter} and {shoulder_len} > 0:
            sr = {shoulder_d} / 2.0
            shoulder = Part.makeCylinder(sr, {shoulder_len})
            shaft = shaft.fuse(shoulder)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shaft
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": "shaft",
            "diameter": {diameter},
            "length": {length},
        }}
        """
    )
    return session.execute(code)


def tool_generate_part_flange(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Flange")
    od = float(args.get("outer_diameter") or 80)
    id_ = float(args.get("inner_diameter") or 30)
    thickness = float(args.get("thickness") or 10)
    bolt_circle = float(args.get("bolt_circle") or 60)
    bolt_d = float(args.get("bolt_diameter") or 8)
    bolt_count = int(args.get("bolt_count") or 4)
    hub_d = float(args.get("hub_diameter") or 0)
    hub_len = float(args.get("hub_length") or 0)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part, math
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        outer = Part.makeCylinder({od}/2.0, {thickness})
        if {id_} > 0:
            outer = outer.cut(Part.makeCylinder({id_}/2.0, {thickness} + 2, FreeCAD.Vector(0, 0, -1)))
        bc = {bolt_circle} / 2.0
        br = {bolt_d} / 2.0
        for i in range({bolt_count}):
            ang = 2 * math.pi * i / {bolt_count}
            x = bc * math.cos(ang)
            y = bc * math.sin(ang)
            hole = Part.makeCylinder(br, {thickness} + 2, FreeCAD.Vector(x, y, -1))
            outer = outer.cut(hole)
        if {hub_d} > {id_} and {hub_len} > 0:
            hub = Part.makeCylinder({hub_d}/2.0, {hub_len})
            if {id_} > 0:
                hub = hub.cut(Part.makeCylinder({id_}/2.0, {hub_len} + 2, FreeCAD.Vector(0, 0, -1)))
            hub.translate(FreeCAD.Vector(0, 0, {thickness}))
            outer = outer.fuse(hub)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = outer
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": "flange",
            "outer_diameter": {od},
            "inner_diameter": {id_},
            "bolt_count": {bolt_count},
        }}
        """
    )
    return session.execute(code)


def tool_generate_part_bushing(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Bushing")
    od = float(args.get("outer_diameter") or 30)
    id_ = float(args.get("inner_diameter") or 20)
    length = float(args.get("length") or 25)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        shape = Part.makeCylinder({od}/2.0, {length})
        if {id_} > 0:
            shape = shape.cut(Part.makeCylinder({id_}/2.0, {length} + 2, FreeCAD.Vector(0, 0, -1)))
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "label": obj.Label, "kind": "bushing"}}
        """
    )
    return session.execute(code)


def tool_generate_part_l_bracket(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "LBracket")
    base_l = float(args.get("base_length") or 40)
    base_w = float(args.get("base_width") or 40)
    height = float(args.get("height") or 30)
    thickness = float(args.get("thickness") or 4)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        base = Part.makeBox({base_l}, {base_w}, {thickness})
        wall = Part.makeBox({base_l}, {thickness}, {height})
        wall.translate(FreeCAD.Vector(0, 0, 0))
        shape = base.fuse(wall)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": "l_bracket",
            "size": [{base_l}, {base_w}, {height}, {thickness}],
        }}
        """
    )
    return session.execute(code)


def tool_generate_part_spur_gear(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Approximate spur gear as extruded involute-ish polygon (practical blank)."""
    name = _unique_name(args.get("name"), "SpurGear")
    teeth = int(args.get("teeth") or 20)
    module = float(args.get("module") or 2.0)
    thickness = float(args.get("thickness") or 10)
    bore = float(args.get("bore") or 10)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part, math
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        z = max(6, int({teeth}))
        m = float({module})
        pitch_r = m * z / 2.0
        addendum = m
        dedendum = 1.25 * m
        tip_r = pitch_r + addendum
        root_r = max(pitch_r - dedendum, m * 0.5)
        # Build a simple tooth outline by alternating tip/root arcs approximated as lines
        pts = []
        for i in range(z * 2):
            a = math.pi * i / z
            r = tip_r if (i % 2 == 0) else root_r
            # slight tooth thickness via angular offset
            if i % 2 == 0:
                a0 = a - math.pi / (z * 4)
                a1 = a + math.pi / (z * 4)
                pts.append(FreeCAD.Vector(tip_r * math.cos(a0), tip_r * math.sin(a0), 0))
                pts.append(FreeCAD.Vector(tip_r * math.cos(a1), tip_r * math.sin(a1), 0))
            else:
                pts.append(FreeCAD.Vector(root_r * math.cos(a), root_r * math.sin(a), 0))
        pts.append(pts[0])
        wire = Part.makePolygon(pts)
        face = Part.Face(wire)
        solid = face.extrude(FreeCAD.Vector(0, 0, {thickness}))
        if {bore} > 0:
            solid = solid.cut(Part.makeCylinder({bore}/2.0, {thickness} + 2, FreeCAD.Vector(0, 0, -1)))
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = solid
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": "spur_gear",
            "teeth": z,
            "module": m,
            "pitch_diameter": pitch_r * 2,
            "note": "approximate blank for layout/animation; refine with FCGear if needed",
        }}
        """
    )
    return session.execute(code)


def tool_generate_part_hex_bolt(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "HexBolt")
    diameter = float(args.get("diameter") or 8)
    length = float(args.get("length") or 30)
    head_af = float(args.get("head_across_flats") or diameter * 1.5)
    head_h = float(args.get("head_height") or diameter * 0.6)
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part, math
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        # Hex head
        af = {head_af}
        r = af / math.sqrt(3)
        pts = []
        for i in range(6):
            a = math.pi / 6 + i * math.pi / 3
            pts.append(FreeCAD.Vector(r * math.cos(a), r * math.sin(a), 0))
        pts.append(pts[0])
        head = Part.Face(Part.makePolygon(pts)).extrude(FreeCAD.Vector(0, 0, {head_h}))
        shank = Part.makeCylinder({diameter}/2.0, {length})
        shank.translate(FreeCAD.Vector(0, 0, {head_h}))
        shape = head.fuse(shank)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "label": obj.Label, "kind": "hex_bolt"}}
        """
    )
    return session.execute(code)


def tool_list_part_library(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del session, args
    return {
        "ok": True,
        "parts": [
            {"tool": "generate_part_plate", "kind": "plate", "desc": "Rectangular plate with optional holes"},
            {"tool": "generate_part_shaft", "kind": "shaft", "desc": "Cylinder shaft with optional shoulder"},
            {"tool": "generate_part_flange", "kind": "flange", "desc": "Bolt-circle flange with optional hub"},
            {"tool": "generate_part_bushing", "kind": "bushing", "desc": "Simple bushing / spacer"},
            {"tool": "generate_part_l_bracket", "kind": "l_bracket", "desc": "L-shaped bracket"},
            {"tool": "generate_part_spur_gear", "kind": "spur_gear", "desc": "Approximate spur gear blank"},
            {"tool": "generate_part_hex_bolt", "kind": "hex_bolt", "desc": "Simplified hex bolt solid"},
        ],
    }


PART_TOOLS: list[dict[str, Any]] = [
    {
        "name": "list_part_library",
        "description": "List parametric part generators available in this MCP server.",
        "inputSchema": _schema({}),
        "handler": tool_list_part_library,
    },
    {
        "name": "generate_part_plate",
        "description": "Generate a rectangular plate; optional bolt holes (1/2/4 or spaced).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "length": {"type": "number", "default": 100},
                "width": {"type": "number", "default": 60},
                "thickness": {"type": "number", "default": 5},
                "hole_diameter": {"type": "number", "default": 0},
                "hole_count": {"type": "integer", "default": 0},
                "hole_margin": {"type": "number", "default": 10},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_plate,
    },
    {
        "name": "generate_part_shaft",
        "description": "Generate a cylindrical shaft, optional larger shoulder at Z=0.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "diameter": {"type": "number", "default": 20},
                "length": {"type": "number", "default": 80},
                "shoulder_diameter": {"type": "number", "default": 0},
                "shoulder_length": {"type": "number", "default": 0},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_shaft,
    },
    {
        "name": "generate_part_flange",
        "description": "Generate a circular flange with bolt circle and optional hub.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "outer_diameter": {"type": "number", "default": 80},
                "inner_diameter": {"type": "number", "default": 30},
                "thickness": {"type": "number", "default": 10},
                "bolt_circle": {"type": "number", "default": 60},
                "bolt_diameter": {"type": "number", "default": 8},
                "bolt_count": {"type": "integer", "default": 4},
                "hub_diameter": {"type": "number", "default": 0},
                "hub_length": {"type": "number", "default": 0},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_flange,
    },
    {
        "name": "generate_part_bushing",
        "description": "Generate a hollow cylinder bushing/spacer.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "outer_diameter": {"type": "number", "default": 30},
                "inner_diameter": {"type": "number", "default": 20},
                "length": {"type": "number", "default": 25},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_bushing,
    },
    {
        "name": "generate_part_l_bracket",
        "description": "Generate an L-bracket from base plate + vertical wall.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "base_length": {"type": "number", "default": 40},
                "base_width": {"type": "number", "default": 40},
                "height": {"type": "number", "default": 30},
                "thickness": {"type": "number", "default": 4},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_l_bracket,
    },
    {
        "name": "generate_part_spur_gear",
        "description": "Generate an approximate spur-gear blank (layout/animation; not precision involute).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "teeth": {"type": "integer", "default": 20},
                "module": {"type": "number", "default": 2},
                "thickness": {"type": "number", "default": 10},
                "bore": {"type": "number", "default": 10},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_spur_gear,
    },
    {
        "name": "generate_part_hex_bolt",
        "description": "Generate a simplified hex-head bolt solid (no thread helix).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "diameter": {"type": "number", "default": 8},
                "length": {"type": "number", "default": 30},
                "head_across_flats": {"type": "number"},
                "head_height": {"type": "number"},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_generate_part_hex_bolt,
    },
]
