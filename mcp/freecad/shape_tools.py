"""Advanced shape tools: profiles, loft/sweep/revolve, shell, topology, smart fillet."""

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


def _placement_code(placement: Any) -> str:
    if not placement:
        return ""
    base = placement.get("base") if isinstance(placement, dict) else None
    if not base or not isinstance(base, (list, tuple)) or len(base) < 3:
        base = (0.0, 0.0, 0.0)
    else:
        base = (float(base[0]), float(base[1]), float(base[2]))
    rot = placement.get("rotation") if isinstance(placement, dict) else None
    if rot and isinstance(rot, dict):
        axis = rot.get("axis") or [0, 0, 1]
        angle = float(rot.get("angle", 0.0))
        return textwrap.dedent(
            f"""
            obj.Placement = FreeCAD.Placement(
                FreeCAD.Vector{base},
                FreeCAD.Rotation(FreeCAD.Vector({float(axis[0])}, {float(axis[1])}, {float(axis[2])}), {angle})
            )
            """
        )
    return f"obj.Placement = FreeCAD.Placement(FreeCAD.Vector{base}, FreeCAD.Rotation())\n"


_SHAPE_HELPERS = r'''
def _sh_find(doc, name):
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")

def _sh_points(pts):
    out = []
    for p in pts:
        out.append(FreeCAD.Vector(float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0))
    return out

def _sh_wire_from_points(pts, kind="polyline", closed=True):
    vecs = _sh_points(pts)
    if len(vecs) < 2:
        raise RuntimeError("need at least 2 points")
    k = (kind or "polyline").lower()
    if k in ("bspline", "spline"):
        if closed and vecs[0].distanceToPoint(vecs[-1]) > 1e-7:
            vecs = list(vecs) + [vecs[0]]
        bs = Part.BSplineCurve()
        bs.interpolate(vecs, PeriodicFlag=bool(closed))
        edge = bs.toShape()
        wire = Part.Wire([edge])
    else:
        if closed and vecs[0].distanceToPoint(vecs[-1]) > 1e-7:
            vecs = list(vecs) + [vecs[0]]
        wire = Part.makePolygon(vecs)
    return wire

def _sh_profile_shape(obj):
    sh = obj.Shape
    if sh.ShapeType == "Wire":
        return sh
    if sh.Wires:
        return sh.Wires[0]
    if sh.Edges:
        return Part.Wire(sh.Edges)
    raise RuntimeError(f"{obj.Name} has no wire/profile")
'''


def tool_create_profile(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Create a planar or 3D wire profile from points (polyline or B-spline)."""
    name = _unique_name(args.get("name"), "Profile")
    points = args.get("points") or []
    if len(points) < 2:
        raise FreeCADError("points must have at least 2 [x,y] or [x,y,z] entries")
    kind = (args.get("kind") or "polyline").lower()
    closed = bool(args.get("closed", True))
    make_face = bool(args.get("make_face", False))
    place = _placement_code(args.get("placement"))
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        wire = _sh_wire_from_points({json.dumps(points)}, kind={kind!r}, closed={closed!r})
        shape = wire
        face_ok = False
        if {make_face!r}:
            try:
                face = Part.Face(wire)
                if face.isValid():
                    shape = face
                    face_ok = True
            except Exception:
                face_ok = False
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        obj.Label = {args.get("label") or name!r}
        {place}
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "kind": {kind!r},
            "closed": {closed!r},
            "make_face": face_ok,
            "is_wire": obj.Shape.ShapeType == "Wire",
            "is_face": obj.Shape.ShapeType == "Face",
        }}
        """
    )
    return session.execute(code)


def tool_loft(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    profiles = args.get("profiles") or []
    if len(profiles) < 2:
        raise FreeCADError("loft needs at least 2 profile object names")
    name = _unique_name(args.get("name"), "Loft")
    solid = bool(args.get("solid", True))
    ruled = bool(args.get("ruled", False))
    closed = bool(args.get("closed", False))
    keep = bool(args.get("keep_profiles", True))
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        names = {json.dumps(profiles)}
        sections = []
        for n in names:
            o = _sh_find(doc, n)
            sh = o.Shape
            if sh.ShapeType == "Face":
                sections.append(sh)
            else:
                sections.append(_sh_profile_shape(o))
        loft = Part.makeLoft(sections, {solid!r}, {ruled!r}, {closed!r})
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = loft
        obj.Label = {args.get("label") or name!r}
        if not {keep!r}:
            for n in names:
                try:
                    doc.removeObject(_sh_find(doc, n).Name)
                except Exception:
                    pass
        doc.recompute()
        vol = float(obj.Shape.Volume) if hasattr(obj.Shape, "Volume") else 0.0
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "profiles": names,
            "solid": {solid!r},
            "volume": vol,
        }}
        """
    )
    return session.execute(code)


def tool_sweep(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    profile = args["profile"]
    path = args["path"]
    name = _unique_name(args.get("name"), "Sweep")
    solid = bool(args.get("solid", True))
    frenet = bool(args.get("frenet", True))
    keep = bool(args.get("keep_inputs", True))
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        prof = _sh_find(doc, {profile!r})
        path_obj = _sh_find(doc, {path!r})
        section = _sh_profile_shape(prof)
        if path_obj.Shape.ShapeType == "Edge":
            spine = Part.Wire([path_obj.Shape])
        elif path_obj.Shape.Wires:
            spine = path_obj.Shape.Wires[0]
        elif path_obj.Shape.Edges:
            spine = Part.Wire(Part.__sortEdges__(path_obj.Shape.Edges))
        else:
            raise RuntimeError("path has no edges")
        try:
            swept = section.makePipeShell([spine], {solid!r}, {frenet!r})
        except Exception:
            swept = Part.makePipe(section, spine)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = swept
        obj.Label = {args.get("label") or name!r}
        if not {keep!r}:
            for n in ({profile!r}, {path!r}):
                try:
                    doc.removeObject(_sh_find(doc, n).Name)
                except Exception:
                    pass
        doc.recompute()
        vol = float(obj.Shape.Volume) if hasattr(obj.Shape, "Volume") else 0.0
        __result__ = {{"ok": True, "name": obj.Name, "profile": {profile!r}, "path": {path!r}, "volume": vol}}
        """
    )
    return session.execute(code)


def tool_revolve(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    profile = args["profile"]
    name = _unique_name(args.get("name"), "Revolve")
    angle = float(args.get("angle", 360.0))
    axis = args.get("axis") or [0, 0, 1]
    origin = args.get("origin") or [0, 0, 0]
    solid = bool(args.get("solid", True))
    keep = bool(args.get("keep_profile", True))
    if not (isinstance(axis, (list, tuple)) and len(axis) >= 3):
        raise FreeCADError("axis must be [x,y,z]")
    if not (isinstance(origin, (list, tuple)) and len(origin) >= 3):
        raise FreeCADError("origin must be [x,y,z]")
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _sh_find(doc, {profile!r})
        sh = src.Shape
        if sh.ShapeType == "Face":
            base = sh
        else:
            wire = _sh_profile_shape(src)
            base = Part.Face(wire) if {solid!r} else wire
        axis_dir = FreeCAD.Vector({float(axis[0])}, {float(axis[1])}, {float(axis[2])})
        center = FreeCAD.Vector({float(origin[0])}, {float(origin[1])}, {float(origin[2])})
        revolved = base.revolve(center, axis_dir, {angle})
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = revolved
        obj.Label = {args.get("label") or name!r}
        if not {keep!r}:
            doc.removeObject(src.Name)
        doc.recompute()
        vol = float(obj.Shape.Volume) if hasattr(obj.Shape, "Volume") else 0.0
        __result__ = {{"ok": True, "name": obj.Name, "angle": {angle}, "volume": vol}}
        """
    )
    return session.execute(code)


def tool_shell_solid(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    thickness = float(args.get("thickness", 2.0))
    if thickness == 0:
        raise FreeCADError("thickness must be non-zero")
    open_faces = args.get("open_faces") or []  # 1-based face indices removed before shell
    out_name = _unique_name(args.get("result_name"), f"{name}_shell")
    keep = bool(args.get("keep_original", False))
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _sh_find(doc, {name!r})
        shape = src.Shape
        if not shape.Solids:
            raise RuntimeError("shell requires a solid")
        solid = shape.Solids[0]
        face_ids = {json.dumps(open_faces)}
        faces = []
        for i in face_ids:
            faces.append(solid.Faces[int(i) - 1])
        shelled = solid.makeThickness(faces, {thickness}, 1e-3)
        obj = doc.addObject("Part::Feature", {out_name!r})
        obj.Shape = shelled
        obj.Label = {args.get("label") or out_name!r}
        if not {keep!r}:
            doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "thickness": {thickness},
            "open_faces": face_ids,
            "volume": float(obj.Shape.Volume),
        }}
        """
    )
    return session.execute(code)


def tool_list_topology(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    what = (args.get("what") or "both").lower()
    max_items = int(args.get("max_items") or 80)
    min_area = args.get("min_area")
    code = textwrap.dedent(
        f"""
        import Part, math
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _sh_find(doc, {name!r})
        sh = src.Shape
        what = {what!r}
        max_items = {max_items}
        min_area = {json.dumps(min_area)}
        faces = []
        edges = []
        if what in ("faces", "both"):
            for i, f in enumerate(sh.Faces, 1):
                area = float(f.Area)
                if min_area is not None and area < float(min_area):
                    continue
                c = f.CenterOfMass
                n = f.normalAt(0.5, 0.5) if hasattr(f, "normalAt") else FreeCAD.Vector(0,0,1)
                try:
                    n = f.normalAt(0.5, 0.5)
                except Exception:
                    try:
                        u = f.ParameterRange[0]
                        v = f.ParameterRange[2]
                        n = f.normalAt(u, v)
                    except Exception:
                        n = FreeCAD.Vector(0, 0, 1)
                faces.append({{
                    "index": i,
                    "area": area,
                    "center": [float(c.x), float(c.y), float(c.z)],
                    "normal": [float(n.x), float(n.y), float(n.z)],
                }})
                if len(faces) >= max_items:
                    break
        if what in ("edges", "both"):
            for i, e in enumerate(sh.Edges, 1):
                length = float(e.Length)
                c = e.CenterOfMass
                circ = None
                try:
                    if hasattr(e.Curve, "Radius"):
                        circ = float(e.Curve.Radius)
                except Exception:
                    circ = None
                edges.append({{
                    "index": i,
                    "length": length,
                    "center": [float(c.x), float(c.y), float(c.z)],
                    "radius": circ,
                }})
                if len(edges) >= max_items:
                    break
        __result__ = {{
            "ok": True,
            "name": src.Name,
            "face_count": len(sh.Faces),
            "edge_count": len(sh.Edges),
            "faces": faces,
            "edges": edges,
        }}
        """
    )
    return session.execute(code)


def tool_fillet_smart(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Fillet by edge indices, face indices (all edges of faces), with excludes and optional keep."""
    name = args["name"]
    radius = float(args["radius"])
    edges = args.get("edges") or []
    faces = args.get("faces") or []
    exclude_edges = set(int(x) for x in (args.get("exclude_edges") or []))
    out_name = _unique_name(args.get("result_name"), f"{name}_fillet")
    keep = bool(args.get("keep_original", False))
    code = textwrap.dedent(
        f"""
        import Part
        {_SHAPE_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _sh_find(doc, {name!r})
        sh = src.Shape
        edge_ids = {json.dumps([int(x) for x in edges])}
        face_ids = {json.dumps([int(x) for x in faces])}
        exclude = {json.dumps(sorted(exclude_edges))}
        selected = []
        seen = set()
        def add_edge(idx, edge):
            if idx in exclude or idx in seen:
                return
            seen.add(idx)
            selected.append(edge)
        if edge_ids:
            for i in edge_ids:
                add_edge(int(i), sh.Edges[int(i) - 1])
        if face_ids:
            for fi in face_ids:
                face = sh.Faces[int(fi) - 1]
                for e in face.Edges:
                    # map edge back to shape index
                    for j, se in enumerate(sh.Edges, 1):
                        if se.isSame(e):
                            add_edge(j, se)
                            break
        if not selected:
            selected = [e for j, e in enumerate(sh.Edges, 1) if j not in exclude]
        shape = sh.makeFillet({radius}, selected)
        obj = doc.addObject("Part::Feature", {out_name!r})
        obj.Shape = shape
        if not {keep!r}:
            doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "radius": {radius},
            "edges_filleted": len(selected),
        }}
        """
    )
    return session.execute(code)


SHAPE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_profile",
        "description": (
            "Create a wire/face profile from points for loft/sweep/revolve. "
            "kind=polyline|bspline; closed=true for sections; make_face=true when planar."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
                    "minItems": 2,
                },
                "kind": {"type": "string", "enum": ["polyline", "bspline", "spline"], "default": "polyline"},
                "closed": {"type": "boolean", "default": True},
                "make_face": {"type": "boolean", "default": False},
                "placement": {
                    "type": "object",
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
                },
            },
            ["points"],
        ),
        "handler": tool_create_profile,
    },
    {
        "name": "loft",
        "description": "Loft through 2+ profile wires/faces into a solid or shell (earcup, armor panels).",
        "inputSchema": _schema(
            {
                "profiles": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "solid": {"type": "boolean", "default": True},
                "ruled": {"type": "boolean", "default": False},
                "closed": {"type": "boolean", "default": False},
                "keep_profiles": {"type": "boolean", "default": True},
            },
            ["profiles"],
        ),
        "handler": tool_loft,
    },
    {
        "name": "sweep",
        "description": "Sweep a profile wire along a path wire (headband, tubes, cable channels).",
        "inputSchema": _schema(
            {
                "profile": {"type": "string"},
                "path": {"type": "string"},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "solid": {"type": "boolean", "default": True},
                "frenet": {"type": "boolean", "default": True},
                "keep_inputs": {"type": "boolean", "default": True},
            },
            ["profile", "path"],
        ),
        "handler": tool_sweep,
    },
    {
        "name": "revolve",
        "description": "Revolve a profile face/wire around an axis (cups, rings, covers).",
        "inputSchema": _schema(
            {
                "profile": {"type": "string"},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "angle": {"type": "number", "default": 360},
                "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "origin": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "solid": {"type": "boolean", "default": True},
                "keep_profile": {"type": "boolean", "default": True},
            },
            ["profile"],
        ),
        "handler": tool_revolve,
    },
    {
        "name": "shell_solid",
        "description": (
            "Hollow a solid into a thin-wall shell. open_faces = 1-based face indices to leave open "
            "(typical: bottom face for an earcup). thickness>0 offsets inward."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "thickness": {"type": "number", "default": 2.0},
                "open_faces": {"type": "array", "items": {"type": "integer"}},
                "result_name": {"type": "string"},
                "label": {"type": "string"},
                "keep_original": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        "handler": tool_shell_solid,
    },
    {
        "name": "list_topology",
        "description": (
            "List faces/edges with index, area/length, center, normal/radius — "
            "use before shell open_faces, fillet_smart, or attach_lcs."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "what": {"type": "string", "enum": ["faces", "edges", "both"], "default": "both"},
                "max_items": {"type": "integer", "default": 80},
                "min_area": {"type": "number"},
            },
            ["name"],
        ),
        "handler": tool_list_topology,
    },
    {
        "name": "fillet_smart",
        "description": (
            "Fillet by edge indices and/or all edges of given faces; exclude_edges supported. "
            "Prefer list_topology first for refined consumer shells."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius": {"type": "number"},
                "edges": {"type": "array", "items": {"type": "integer"}},
                "faces": {"type": "array", "items": {"type": "integer"}},
                "exclude_edges": {"type": "array", "items": {"type": "integer"}},
                "result_name": {"type": "string"},
                "keep_original": {"type": "boolean", "default": False},
            },
            ["name", "radius"],
        ),
        "handler": tool_fillet_smart,
    },
]
