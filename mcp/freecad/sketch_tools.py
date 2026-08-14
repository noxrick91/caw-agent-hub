"""Sketcher tools: create sketches, add geometry/constraints, pad/pocket/revolve."""

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


_XY = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 2,
    "maxItems": 2,
    "description": "Sketch-plane [x, y] in millimetres",
}

_CONSTRAINT_TYPES = [
    "coincident",
    "horizontal",
    "vertical",
    "parallel",
    "perpendicular",
    "tangent",
    "equal",
    "symmetric",
    "block",
    "distance",
    "distance_x",
    "distance_y",
    "radius",
    "diameter",
    "angle",
    "point_on_object",
]

_SK_HELPERS = r'''
def _sk_find(doc, name):
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError("object not found: %s" % name)

def _sk_sketch(doc, name):
    sk = _sk_find(doc, name)
    if "Sketcher" not in getattr(sk, "TypeId", ""):
        raise RuntimeError("%s is not a sketch (%s)" % (name, getattr(sk, "TypeId", "?")))
    return sk

def _sk_pos(pos):
    if pos is None or pos == "":
        return 0
    if isinstance(pos, (int, float)):
        return int(pos)
    key = str(pos).strip().lower()
    return {
        "none": 0, "edge": 0, "line": 0,
        "start": 1, "begin": 1, "p1": 1,
        "end": 2, "p2": 2,
        "center": 3, "mid": 3, "middle": 3, "p3": 3,
    }.get(key, 0)

def _sk_geo_ref(ref, default_pos=0):
    if ref is None:
        return None, default_pos
    if isinstance(ref, (int, float)):
        return int(ref), default_pos
    key = str(ref).strip().lower()
    if key in ("origin", "root", "root_point"):
        return -1, 1
    if key in ("x", "x_axis", "h_axis", "horizontal_axis"):
        return -1, 0
    if key in ("y", "y_axis", "v_axis", "vertical_axis"):
        return -2, 0
    try:
        return int(key), default_pos
    except ValueError:
        raise RuntimeError("bad geo ref: %r" % (ref,))

def _sk_ctype(kind):
    key = str(kind or "").strip().lower().replace("-", "_")
    return {
        "coincident": "Coincident",
        "horizontal": "Horizontal",
        "vertical": "Vertical",
        "parallel": "Parallel",
        "perpendicular": "Perpendicular",
        "tangent": "Tangent",
        "equal": "Equal",
        "symmetric": "Symmetric",
        "block": "Block",
        "fix": "Block",
        "lock": "Block",
        "distance": "Distance",
        "length": "Distance",
        "distance_x": "DistanceX",
        "dx": "DistanceX",
        "distance_y": "DistanceY",
        "dy": "DistanceY",
        "radius": "Radius",
        "diameter": "Diameter",
        "angle": "Angle",
        "point_on_object": "PointOnObject",
        "on": "PointOnObject",
        "pointonobject": "PointOnObject",
    }.get(key, None)

def _sk_status(sk):
    solve = None
    try:
        solve = int(sk.solve())
    except Exception:
        solve = None
    dof = None
    for attr in ("MissingDatum",):
        if hasattr(sk, attr):
            try:
                dof = int(getattr(sk, attr))
            except Exception:
                pass
    fully = None
    if hasattr(sk, "FullyConstrained"):
        try:
            fully = bool(sk.FullyConstrained)
        except Exception:
            fully = None
    return {"solve": solve, "dof": dof, "fully_constrained": fully}

def _sk_attach_face(sk, obj, face):
    face_s = face if isinstance(face, str) else ("Face%d" % int(face))
    support = [(obj, (face_s,))]
    if hasattr(sk, "AttachmentSupport"):
        sk.AttachmentSupport = support
    else:
        sk.Support = support
    sk.MapMode = "FlatFace"

def _sk_attach_plane(sk, body, plane):
    plane = (plane or "xy").lower()
    origin_name = {"xy": "XY_Plane", "xz": "XZ_Plane", "yz": "YZ_Plane"}.get(plane, "XY_Plane")
    if body is not None and hasattr(body, "Origin") and body.Origin is not None:
        for feat in getattr(body.Origin, "OriginFeatures", []) or []:
            nm = getattr(feat, "Name", "") + " " + getattr(feat, "Label", "")
            if origin_name.replace("_", "") in nm.replace("_", "").replace(" ", ""):
                if hasattr(sk, "AttachmentSupport"):
                    sk.AttachmentSupport = [(feat, ("",))]
                else:
                    sk.Support = [(feat, ("",))]
                sk.MapMode = "FlatFace"
                return plane
    if plane == "xz":
        sk.Placement = FreeCAD.Placement(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 90),
        )
    elif plane == "yz":
        sk.Placement = FreeCAD.Placement(
            FreeCAD.Vector(0, 0, 0),
            FreeCAD.Rotation(FreeCAD.Vector(0, 1, 0), 90),
        )
    return plane

def _sk_ensure_body(doc, sketch, body_name=None):
    parent = None
    if hasattr(sketch, "getParentGeoFeatureGroup"):
        try:
            parent = sketch.getParentGeoFeatureGroup()
        except Exception:
            parent = None
    if parent is not None and "PartDesign::Body" in getattr(parent, "TypeId", ""):
        return parent
    body = None
    if body_name:
        body = _sk_find(doc, body_name)
    else:
        for o in doc.Objects:
            if getattr(o, "TypeId", "") == "PartDesign::Body":
                body = o
                break
    if body is None:
        body = doc.addObject("PartDesign::Body", "Body")
    try:
        body.addObject(sketch)
    except Exception:
        try:
            if hasattr(sketch, "adjustRelativeLinks"):
                sketch.adjustRelativeLinks(body)
            if hasattr(body, "ViewObject") and hasattr(body.ViewObject, "dropObject"):
                body.ViewObject.dropObject(sketch)
        except Exception:
            pass
    return body

def _sk_geo_info(sk, gid):
    geos = list(sk.Geometry)
    if gid < 0 or gid >= len(geos) or geos[gid] is None:
        return None
    g = geos[gid]
    info = {
        "id": gid,
        "type": type(g).__name__,
        "construction": bool(sk.getConstruction(gid)) if hasattr(sk, "getConstruction") else False,
    }
    for attr, key in (("StartPoint", "start"), ("EndPoint", "end"), ("Center", "center")):
        if hasattr(g, attr):
            p = getattr(g, attr)
            info[key] = [round(float(p.x), 6), round(float(p.y), 6)]
    if hasattr(g, "Radius"):
        info["radius"] = float(g.Radius)
    if hasattr(g, "MajorRadius"):
        info["major_radius"] = float(g.MajorRadius)
    return info

def _sk_dump(sk):
    geos = []
    for i, g in enumerate(sk.Geometry):
        if g is None:
            continue
        item = _sk_geo_info(sk, i)
        if item:
            geos.append(item)
    cons = []
    for i, c in enumerate(sk.Constraints):
        item = {"id": i, "type": c.Type}
        if getattr(c, "First", -2000) > -2000:
            item["geo1"] = int(c.First)
        if getattr(c, "FirstPos", 0):
            item["pos1"] = int(c.FirstPos)
        if getattr(c, "Second", -2000) > -2000:
            item["geo2"] = int(c.Second)
        if getattr(c, "SecondPos", 0):
            item["pos2"] = int(c.SecondPos)
        if getattr(c, "Third", -2000) > -2000:
            item["geo3"] = int(c.Third)
        if c.Type in ("Distance", "DistanceX", "DistanceY", "Radius", "Diameter", "Angle"):
            try:
                val = float(c.Value)
                if c.Type == "Angle":
                    val = val * 180.0 / 3.141592653589793
                item["value"] = val
            except Exception:
                pass
        cons.append(item)
    st = _sk_status(sk)
    st.update({"geometry": geos, "constraints": cons, "geo_count": len(geos), "constraint_count": len(cons)})
    return st

def _sk_add_constraint(sk, kind, geo1, pos1, geo2, pos2, geo3, pos3, value):
    import math
    import Sketcher
    ctype = _sk_ctype(kind)
    if not ctype:
        raise RuntimeError("unknown constraint type: %s" % kind)
    g1, p1 = _sk_geo_ref(geo1, _sk_pos(pos1))
    g2, p2 = _sk_geo_ref(geo2, _sk_pos(pos2)) if geo2 is not None and geo2 != "" else (None, 0)
    g3, p3 = _sk_geo_ref(geo3, _sk_pos(pos3)) if geo3 is not None and geo3 != "" else (None, 0)
    if g2 is None and str(geo1).lower() in ("origin", "root", "root_point"):
        g1, p1 = -1, 1
    val = None if value is None else float(value)
    if ctype == "Angle" and val is not None:
        val = val * math.pi / 180.0
    args = []
    if ctype in ("Horizontal", "Vertical", "Block"):
        if g2 is None:
            args = [g1] if p1 == 0 else [g1, p1]
        else:
            args = [g1, p1 or 1, g2, p2 or 1]
    elif ctype in ("Parallel", "Perpendicular", "Equal"):
        args = [g1, g2]
    elif ctype == "Tangent":
        if p1 or p2:
            args = [g1, p1 or 0, g2] if p1 else [g1, g2, p2]
        else:
            args = [g1, g2]
    elif ctype == "Coincident":
        args = [g1, p1 or 1, g2, p2 or 1]
    elif ctype == "PointOnObject":
        args = [g1, p1 or 1, g2]
    elif ctype == "Symmetric":
        if g3 is None:
            args = [g1, p1 or 1, g2, p2 or 1, g3 if g3 is not None else -1]
        else:
            args = [g1, p1 or 1, g2, p2 or 1, g3] if p3 == 0 else [g1, p1 or 1, g2, p2 or 1, g3, p3]
    elif ctype in ("Radius", "Diameter"):
        args = [g1, val]
    elif ctype in ("Distance", "DistanceX", "DistanceY", "Angle"):
        if g2 is None:
            args = [g1, val] if p1 == 0 else [g1, p1, val]
        else:
            args = [g1, p1 or 1, g2, p2 or 1, val]
    else:
        raise RuntimeError("cannot build constraint %s" % ctype)
    cid = sk.addConstraint(Sketcher.Constraint(ctype, *args))
    return int(cid)

def _sk_extrude_fallback(doc, sketch, name, length, reversed=False, midplane=False):
    import Part
    wires = list(sketch.Shape.Wires) if sketch.Shape.Wires else []
    if not wires and sketch.Shape.Edges:
        wires = [Part.Wire(sketch.Shape.Edges)]
    if not wires:
        raise RuntimeError("sketch has no closed profile to extrude")
    face = Part.Face(wires)
    normal = sketch.Placement.Rotation.multVec(FreeCAD.Vector(0, 0, 1))
    if reversed:
        normal = normal.negative()
    if midplane:
        face = face.translated(normal * (-float(length) / 2.0))
    solid = face.extrude(normal * float(length))
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = solid
    return obj
'''


def _exec(session: FreeCADSession, prefix: str, body: str) -> dict[str, Any]:
    code = (
        "import math\nimport Part\nimport Sketcher\n"
        + _SK_HELPERS
        + textwrap.dedent(prefix)
        + textwrap.dedent(body)
    )
    return session.execute(code)


def tool_create_sketch(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Sketch")
    plane = (args.get("plane") or "xy").lower()
    if plane not in ("xy", "xz", "yz"):
        raise FreeCADError("plane must be xy, xz, or yz")
    support = args.get("support")
    face = args.get("face")
    body_name = args.get("body")
    label = args.get("label") or name
    origin = args.get("origin") or [0, 0, 0]
    if not (isinstance(origin, (list, tuple)) and len(origin) >= 3):
        origin = [0, 0, 0]
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        body = None
        body_name = {json.dumps(body_name)}
        if body_name:
            body = _sk_find(doc, body_name)
        else:
            try:
                body = doc.addObject("PartDesign::Body", "Body")
            except Exception:
                body = None
        if body is not None:
            try:
                sk = body.newObject("Sketcher::SketchObject", {name!r})
            except Exception:
                sk = doc.addObject("Sketcher::SketchObject", {name!r})
                _sk_ensure_body(doc, sk, body.Name)
        else:
            sk = doc.addObject("Sketcher::SketchObject", {name!r})
        sk.Label = {label!r}
        support = {json.dumps(support)}
        face = {json.dumps(face)}
        plane = {plane!r}
        if support:
            obj = _sk_find(doc, support)
            _sk_attach_face(sk, obj, face if face is not None else 1)
            used_plane = "face"
        else:
            used_plane = _sk_attach_plane(sk, body if body is not None else None, plane)
        ox, oy, oz = {float(origin[0])}, {float(origin[1])}, {float(origin[2])}
        if ox or oy or oz:
            base = sk.Placement.Base + FreeCAD.Vector(ox, oy, oz)
            sk.Placement = FreeCAD.Placement(base, sk.Placement.Rotation)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{
            "ok": True,
            "name": sk.Name,
            "label": sk.Label,
            "body": body.Name if body is not None else None,
            "plane": used_plane,
            "support": support,
            "face": face,
        }}
        __result__.update(st)
        """,
    )


def tool_sketch_add_line(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    start = args.get("start") or [0, 0]
    end = args.get("end") or [10, 0]
    if len(start) < 2 or len(end) < 2:
        raise FreeCADError("start and end must be [x, y]")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        g = Part.LineSegment(
            FreeCAD.Vector({float(start[0])}, {float(start[1])}, 0),
            FreeCAD.Vector({float(end[0])}, {float(end[1])}, 0),
        )
        gid = int(sk.addGeometry(g, {bool(args.get("construction"))!r}))
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_id": gid, "geo_ids": [gid]}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_polyline(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    points = args.get("points") or []
    if len(points) < 2:
        raise FreeCADError("points needs at least 2 [x,y] entries")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        pts = {json.dumps([[float(p[0]), float(p[1])] for p in points])}
        closed = {bool(args.get("closed"))!r}
        construction = {bool(args.get("construction"))!r}
        ids = []
        n = len(pts)
        last = n if closed else n - 1
        for i in range(last):
            a = pts[i]
            b = pts[(i + 1) % n]
            gid = int(sk.addGeometry(
                Part.LineSegment(FreeCAD.Vector(a[0], a[1], 0), FreeCAD.Vector(b[0], b[1], 0)),
                construction,
            ))
            ids.append(gid)
        for i in range(len(ids) - 1):
            _sk_add_constraint(sk, "coincident", ids[i], "end", ids[i + 1], "start", None, None, None)
        if closed and len(ids) > 1:
            _sk_add_constraint(sk, "coincident", ids[-1], "end", ids[0], "start", None, None, None)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_ids": ids}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_rectangle(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    if args.get("p1") and args.get("p2"):
        p1, p2 = args["p1"], args["p2"]
        x = min(float(p1[0]), float(p2[0]))
        y = min(float(p1[1]), float(p2[1]))
        w = abs(float(p2[0]) - float(p1[0]))
        h = abs(float(p2[1]) - float(p1[1]))
    else:
        x = float(args.get("x") or 0)
        y = float(args.get("y") or 0)
        w = float(args.get("width") or 20)
        h = float(args.get("height") or 10)
        if args.get("centered"):
            x -= w / 2.0
            y -= h / 2.0
    if w <= 0 or h <= 0:
        raise FreeCADError("width and height must be > 0")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        x, y, w, h = {x}, {y}, {w}, {h}
        construction = {bool(args.get("construction"))!r}
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        ids = []
        for i in range(4):
            a = pts[i]
            b = pts[(i + 1) % 4]
            ids.append(int(sk.addGeometry(
                Part.LineSegment(FreeCAD.Vector(a[0], a[1], 0), FreeCAD.Vector(b[0], b[1], 0)),
                construction,
            )))
        for i in range(4):
            _sk_add_constraint(sk, "coincident", ids[i], "end", ids[(i + 1) % 4], "start", None, None, None)
        _sk_add_constraint(sk, "horizontal", ids[0], None, None, None, None, None, None)
        _sk_add_constraint(sk, "vertical", ids[1], None, None, None, None, None, None)
        _sk_add_constraint(sk, "horizontal", ids[2], None, None, None, None, None, None)
        _sk_add_constraint(sk, "vertical", ids[3], None, None, None, None, None, None)
        constrain = {bool(args.get("constrain", True))!r}
        cids = []
        if constrain:
            cids.append(_sk_add_constraint(sk, "distance", ids[0], None, None, None, None, None, w))
            cids.append(_sk_add_constraint(sk, "distance", ids[3], None, None, None, None, None, h))
        if {bool(args.get("lock_origin"))!r}:
            _sk_add_constraint(sk, "coincident", ids[0], "start", "origin", "start", None, None, None)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{
            "ok": True,
            "sketch": sk.Name,
            "geo_ids": ids,
            "constraint_ids": cids,
            "width": w,
            "height": h,
        }}
        __result__.update(st)
        """,
    )


def tool_sketch_add_circle(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    center = args.get("center") or [0, 0]
    radius = float(args.get("radius") or 5)
    if radius <= 0:
        raise FreeCADError("radius must be > 0")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        g = Part.Circle(
            FreeCAD.Vector({float(center[0])}, {float(center[1])}, 0),
            FreeCAD.Vector(0, 0, 1),
            {radius},
        )
        gid = int(sk.addGeometry(g, {bool(args.get("construction"))!r}))
        cids = []
        if {bool(args.get("constrain", True))!r}:
            cids.append(_sk_add_constraint(sk, "radius", gid, None, None, None, None, None, {radius}))
        if {bool(args.get("lock_center"))!r}:
            _sk_add_constraint(sk, "coincident", gid, "center", "origin", "start", None, None, None)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_id": gid, "geo_ids": [gid], "constraint_ids": cids}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_arc(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    center = args.get("center") or [0, 0]
    radius = float(args.get("radius") or 5)
    start_deg = float(args.get("start_deg") or 0)
    end_deg = float(args.get("end_deg") or 90)
    if radius <= 0:
        raise FreeCADError("radius must be > 0")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        import math
        circle = Part.Circle(
            FreeCAD.Vector({float(center[0])}, {float(center[1])}, 0),
            FreeCAD.Vector(0, 0, 1),
            {radius},
        )
        g = Part.ArcOfCircle(circle, math.radians({start_deg}), math.radians({end_deg}))
        gid = int(sk.addGeometry(g, {bool(args.get("construction"))!r}))
        cids = []
        if {bool(args.get("constrain", True))!r}:
            cids.append(_sk_add_constraint(sk, "radius", gid, None, None, None, None, None, {radius}))
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_id": gid, "geo_ids": [gid], "constraint_ids": cids}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_point(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    at = args.get("at") or [0, 0]
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        gid = int(sk.addGeometry(
            Part.Point(FreeCAD.Vector({float(at[0])}, {float(at[1])}, 0)),
            {bool(args.get("construction", True))!r},
        ))
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_id": gid, "geo_ids": [gid]}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_slot(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    start = args.get("start") or [0, 0]
    end = args.get("end") or [20, 0]
    radius = float(args.get("radius") or 4)
    if radius <= 0:
        raise FreeCADError("radius must be > 0")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        import math
        x1, y1 = {float(start[0])}, {float(start[1])}
        x2, y2 = {float(end[0])}, {float(end[1])}
        r = {radius}
        dx, dy = x2 - x1, y2 - y1
        length = math.hypot(dx, dy)
        if length < 1e-9:
            raise RuntimeError("slot start and end are the same point")
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        a1 = (x1 + nx * r, y1 + ny * r)
        a2 = (x2 + nx * r, y2 + ny * r)
        b2 = (x2 - nx * r, y2 - ny * r)
        b1 = (x1 - nx * r, y1 - ny * r)
        construction = {bool(args.get("construction"))!r}
        l1 = int(sk.addGeometry(Part.LineSegment(
            FreeCAD.Vector(a1[0], a1[1], 0), FreeCAD.Vector(a2[0], a2[1], 0)), construction))
        l2 = int(sk.addGeometry(Part.LineSegment(
            FreeCAD.Vector(b2[0], b2[1], 0), FreeCAD.Vector(b1[0], b1[1], 0)), construction))
        ang_n = math.atan2(ny, nx)
        c2 = Part.Circle(FreeCAD.Vector(x2, y2, 0), FreeCAD.Vector(0, 0, 1), r)
        c1 = Part.Circle(FreeCAD.Vector(x1, y1, 0), FreeCAD.Vector(0, 0, 1), r)
        arc2 = int(sk.addGeometry(Part.ArcOfCircle(c2, ang_n - math.pi, ang_n), construction))
        arc1 = int(sk.addGeometry(Part.ArcOfCircle(c1, ang_n, ang_n + math.pi), construction))
        ids = [l1, arc2, l2, arc1]
        _sk_add_constraint(sk, "coincident", l1, "end", arc2, "start", None, None, None)
        _sk_add_constraint(sk, "coincident", arc2, "end", l2, "start", None, None, None)
        _sk_add_constraint(sk, "coincident", l2, "end", arc1, "start", None, None, None)
        _sk_add_constraint(sk, "coincident", arc1, "end", l1, "start", None, None, None)
        _sk_add_constraint(sk, "tangent", l1, None, arc2, None, None, None, None)
        _sk_add_constraint(sk, "tangent", l2, None, arc2, None, None, None, None)
        _sk_add_constraint(sk, "tangent", l2, None, arc1, None, None, None, None)
        _sk_add_constraint(sk, "tangent", l1, None, arc1, None, None, None, None)
        _sk_add_constraint(sk, "equal", arc1, None, arc2, None, None, None, None)
        if {bool(args.get("constrain", True))!r}:
            _sk_add_constraint(sk, "radius", arc1, None, None, None, None, None, r)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_ids": ids, "radius": r}}
        __result__.update(st)
        """,
    )


def tool_sketch_add_bspline(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    points = args.get("points") or []
    if len(points) < 2:
        raise FreeCADError("points needs at least 2 [x,y] entries")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        pts = {json.dumps([[float(p[0]), float(p[1])] for p in points])}
        vecs = [FreeCAD.Vector(p[0], p[1], 0) for p in pts]
        closed = {bool(args.get("closed"))!r}
        if closed and vecs[0].distanceToPoint(vecs[-1]) > 1e-7:
            vecs = list(vecs) + [vecs[0]]
        bs = Part.BSplineCurve()
        bs.interpolate(vecs, PeriodicFlag=closed)
        gid = int(sk.addGeometry(bs, {bool(args.get("construction"))!r}))
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo_id": gid, "geo_ids": [gid]}}
        __result__.update(st)
        """,
    )


def tool_sketch_constraint(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    kind = args.get("type") or args.get("kind")
    if not kind:
        raise FreeCADError("type is required")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        cid = _sk_add_constraint(
            sk,
            {json.dumps(kind)},
            {json.dumps(args.get("geo1"))},
            {json.dumps(args.get("pos1"))},
            {json.dumps(args.get("geo2"))},
            {json.dumps(args.get("pos2"))},
            {json.dumps(args.get("geo3"))},
            {json.dumps(args.get("pos3"))},
            {json.dumps(args.get("value"))},
        )
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "constraint_id": cid}}
        __result__.update(st)
        """,
    )


def tool_sketch_toggle_construction(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    geo_ids = args.get("geo_ids") or args.get("geo_id")
    if geo_ids is None:
        raise FreeCADError("geo_id or geo_ids is required")
    if isinstance(geo_ids, (int, float)):
        geo_ids = [int(geo_ids)]
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        ids = {json.dumps([int(i) for i in geo_ids])}
        states = []
        for gid in ids:
            sk.toggleConstruction(int(gid))
            states.append({{"geo_id": int(gid), "construction": bool(sk.getConstruction(int(gid)))}})
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "items": states}}
        __result__.update(st)
        """,
    )


def tool_sketch_external(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    sub = args.get("sub") or args.get("edge") or args.get("face")
    if sub is None:
        raise FreeCADError("sub/edge/face is required, e.g. Edge1 or Face1")
    if isinstance(sub, int):
        kind = args.get("kind") or "edge"
        sub = ("Face%d" if str(kind).lower().startswith("f") else "Edge%d") % int(sub)
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        src = _sk_find(doc, {args["target"]!r})
        before = len(sk.ExternalGeometry) if hasattr(sk, "ExternalGeometry") else 0
        sk.addExternal(src.Name, {json.dumps(str(sub))})
        doc.recompute()
        after = len(sk.ExternalGeometry) if hasattr(sk, "ExternalGeometry") else before
        st = _sk_status(sk)
        __result__ = {{
            "ok": True,
            "sketch": sk.Name,
            "target": src.Name,
            "sub": {json.dumps(str(sub))},
            "external_count": after,
        }}
        __result__.update(st)
        """,
    )


def tool_sketch_fillet(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    radius = float(args.get("radius") or 1)
    if radius <= 0:
        raise FreeCADError("radius must be > 0")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        g1 = int({int(args["geo1"])})
        g2 = int({int(args["geo2"])})
        r = {radius}
        try:
            sk.fillet(g1, g2, r)
        except Exception:
            p1 = _sk_pos({json.dumps(args.get("pos1") or "end")})
            p2 = _sk_pos({json.dumps(args.get("pos2") or "start")})
            sk.fillet(g1, p1, g2, p2, r, True, True)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "geo1": g1, "geo2": g2, "radius": r}}
        __result__.update(st)
        """,
    )


def tool_sketch_info(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        info = _sk_dump(sk)
        info["ok"] = True
        info["name"] = sk.Name
        info["label"] = sk.Label
        parent = None
        if hasattr(sk, "getParentGeoFeatureGroup"):
            try:
                p = sk.getParentGeoFeatureGroup()
                parent = p.Name if p is not None else None
            except Exception:
                parent = None
        info["body"] = parent
        __result__ = info
        """,
    )


def tool_sketch_delete(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    geos = args.get("geo_ids") or []
    cons = args.get("constraint_ids") or []
    if isinstance(geos, (int, float)):
        geos = [int(geos)]
    if isinstance(cons, (int, float)):
        cons = [int(cons)]
    if not geos and not cons:
        raise FreeCADError("provide geo_ids and/or constraint_ids")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        cons = sorted({json.dumps([int(i) for i in cons])}, reverse=True)
        geos = sorted({json.dumps([int(i) for i in geos])}, reverse=True)
        for cid in cons:
            sk.delConstraint(int(cid))
        for gid in geos:
            sk.delGeometry(int(gid))
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{
            "ok": True,
            "sketch": sk.Name,
            "deleted_geo_ids": list(reversed(geos)),
            "deleted_constraint_ids": list(reversed(cons)),
        }}
        __result__.update(st)
        """,
    )


def tool_sketch_set_constraint(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    cid = int(args["constraint_id"])
    value = float(args["value"])
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        cid = {cid}
        val = {value}
        ctype = sk.Constraints[cid].Type
        if ctype == "Angle":
            import math
            val = math.radians(val)
        sk.setDatum(cid, val)
        doc.recompute()
        st = _sk_status(sk)
        __result__ = {{"ok": True, "sketch": sk.Name, "constraint_id": cid, "value": {value}, "type": ctype}}
        __result__.update(st)
        """,
    )


def _feature_type_code(kind: str) -> str:
    key = (kind or "length").lower().replace("-", "_")
    mapping = {
        "length": ("Length", 0),
        "dimension": ("Length", 0),
        "two_lengths": ("TwoLengths", 1),
        "up_to_last": ("UpToLast", 2),
        "up_to_first": ("UpToFirst", 3),
        "up_to_face": ("UpToFace", 4),
        "through_all": ("ThroughAll", 1),
        "two_sides": ("TwoSides", 5),
    }
    name, idx = mapping.get(key, ("Length", 0))
    return json.dumps([name, idx])


def tool_sketch_pad(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    length = float(args.get("length") or args.get("height") or 10)
    name = _unique_name(args.get("name"), "Pad")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        length = {length}
        midplane = {bool(args.get("midplane"))!r}
        reversed = {bool(args.get("reversed"))!r}
        type_pair = {_feature_type_code(str(args.get("type") or "length"))}
        feat_name = {name!r}
        body = _sk_ensure_body(doc, sk, {json.dumps(args.get("body"))})
        obj = None
        err = None
        try:
            obj = body.newObject("PartDesign::Pad", feat_name)
            obj.Profile = sk
            try:
                obj.Type = type_pair[0]
            except Exception:
                obj.Type = type_pair[1]
            if hasattr(obj, "Length"):
                obj.Length = length
            if hasattr(obj, "Midplane"):
                obj.Midplane = midplane
            if hasattr(obj, "Reversed"):
                obj.Reversed = reversed
            doc.recompute()
        except Exception as e:
            err = str(e)
            obj = None
        if obj is None:
            obj = _sk_extrude_fallback(doc, sk, feat_name, length, reversed, midplane)
            doc.recompute()
        vol = None
        try:
            vol = float(obj.Shape.Volume)
        except Exception:
            vol = None
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "sketch": sk.Name,
            "body": body.Name if body is not None else None,
            "length": length,
            "midplane": midplane,
            "reversed": reversed,
            "volume": vol,
            "fallback": err,
        }}
        """,
    )


def tool_sketch_pocket(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    length = float(args.get("length") or args.get("depth") or 5)
    name = _unique_name(args.get("name"), "Pocket")
    through = bool(args.get("through_all"))
    ftype = "through_all" if through else (args.get("type") or "length")
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        length = {length}
        reversed = {bool(args.get("reversed"))!r}
        type_pair = {_feature_type_code(ftype)}
        feat_name = {name!r}
        body = _sk_ensure_body(doc, sk, {json.dumps(args.get("body"))})
        obj = body.newObject("PartDesign::Pocket", feat_name)
        obj.Profile = sk
        try:
            obj.Type = type_pair[0]
        except Exception:
            obj.Type = type_pair[1]
        if hasattr(obj, "Length"):
            obj.Length = length
        if hasattr(obj, "Reversed"):
            obj.Reversed = reversed
        doc.recompute()
        vol = None
        try:
            vol = float(obj.Shape.Volume)
        except Exception:
            vol = None
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "sketch": sk.Name,
            "body": body.Name,
            "length": length,
            "through_all": {through!r},
            "volume": vol,
        }}
        """,
    )


def tool_sketch_revolve(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    angle = float(args.get("angle") or 360)
    name = _unique_name(args.get("name"), "Revolution")
    axis = (args.get("axis") or "y").lower()
    return _exec(
        session,
        "",
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        sk = _sk_sketch(doc, {args["sketch"]!r})
        angle = {angle}
        axis = {axis!r}
        feat_name = {name!r}
        axis_name = "V_Axis" if axis in ("y", "v", "v_axis") else "H_Axis"
        body = _sk_ensure_body(doc, sk, {json.dumps(args.get("body"))})
        obj = None
        err = None
        try:
            obj = body.newObject("PartDesign::Revolution", feat_name)
            obj.Profile = sk
            if hasattr(obj, "Angle"):
                obj.Angle = angle
            if hasattr(obj, "ReferenceAxis"):
                obj.ReferenceAxis = (sk, [axis_name])
            doc.recompute()
        except Exception as e:
            err = str(e)
            obj = None
        if obj is None:
            import Part
            wires = list(sk.Shape.Wires)
            if not wires:
                raise RuntimeError("sketch has no profile to revolve: %s" % err)
            face = Part.Face(wires)
            origin = sk.Placement.Base
            direction = sk.Placement.Rotation.multVec(
                FreeCAD.Vector(0, 1, 0) if axis_name == "V_Axis" else FreeCAD.Vector(1, 0, 0)
            )
            solid = face.revolve(origin, direction, angle)
            obj = doc.addObject("Part::Feature", feat_name)
            obj.Shape = solid
            doc.recompute()
        vol = None
        try:
            vol = float(obj.Shape.Volume)
        except Exception:
            vol = None
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "sketch": sk.Name,
            "body": body.Name if body is not None else None,
            "angle": angle,
            "axis": axis,
            "volume": vol,
            "fallback": err,
        }}
        """,
    )


_SKETCH_PROP = {"type": "string", "description": "Sketch object Name (from create_sketch)"}
_CONSTRUCTION = {"type": "boolean", "default": False, "description": "Construction (reference) geometry"}
_CONSTRAIN = {"type": "boolean", "default": True, "description": "Add driving dimensions"}
_GEO_REF = {
    "description": "Geometry id (0-based) or origin|x|y for sketch axes",
}
_POS_REF = {
    "description": "Point on geometry: start|end|center|edge (or 1|2|3|0)",
}


SKETCH_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_sketch",
        "description": (
            "Create a Sketcher sketch on XY/XZ/YZ or on a solid face. "
            "Returns the sketch name for later sketch_* tools. Prefers a PartDesign Body."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "plane": {"type": "string", "enum": ["xy", "xz", "yz"], "default": "xy"},
                "support": {"type": "string", "description": "Object to attach the sketch to"},
                "face": {"description": "Face index (1-based) or FaceN when support is set"},
                "body": {"type": "string", "description": "Existing PartDesign Body name"},
                "origin": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 3,
                    "maxItems": 3,
                    "description": "World offset [x,y,z]",
                },
            }
        ),
        "handler": tool_create_sketch,
    },
    {
        "name": "sketch_add_line",
        "description": "Add a line segment to a sketch (sketch-plane [x,y] endpoints).",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "start": _XY,
                "end": _XY,
                "construction": _CONSTRUCTION,
            },
            ["sketch", "start", "end"],
        ),
        "handler": tool_sketch_add_line,
    },
    {
        "name": "sketch_add_polyline",
        "description": "Add connected line segments; coincident at joints; closed=true to loop.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "points": {"type": "array", "items": _XY, "minItems": 2},
                "closed": {"type": "boolean", "default": False},
                "construction": _CONSTRUCTION,
            },
            ["sketch", "points"],
        ),
        "handler": tool_sketch_add_polyline,
    },
    {
        "name": "sketch_add_rectangle",
        "description": (
            "Add a rectangle with H/V + optional width/height constraints. "
            "Use x,y,width,height or p1/p2 corners. centered=true around x,y."
        ),
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "x": {"type": "number", "default": 0},
                "y": {"type": "number", "default": 0},
                "width": {"type": "number", "default": 20},
                "height": {"type": "number", "default": 10},
                "p1": _XY,
                "p2": _XY,
                "centered": {"type": "boolean", "default": False},
                "constrain": _CONSTRAIN,
                "lock_origin": {"type": "boolean", "default": False},
                "construction": _CONSTRUCTION,
            },
            ["sketch"],
        ),
        "handler": tool_sketch_add_rectangle,
    },
    {
        "name": "sketch_add_circle",
        "description": "Add a circle; optional radius constraint and lock_center to origin.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "center": _XY,
                "radius": {"type": "number", "default": 5},
                "constrain": _CONSTRAIN,
                "lock_center": {"type": "boolean", "default": False},
                "construction": _CONSTRUCTION,
            },
            ["sketch", "center", "radius"],
        ),
        "handler": tool_sketch_add_circle,
    },
    {
        "name": "sketch_add_arc",
        "description": "Add a circular arc. Angles are degrees CCW from +X on the sketch plane.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "center": _XY,
                "radius": {"type": "number", "default": 5},
                "start_deg": {"type": "number", "default": 0},
                "end_deg": {"type": "number", "default": 90},
                "constrain": _CONSTRAIN,
                "construction": _CONSTRUCTION,
            },
            ["sketch", "center", "radius"],
        ),
        "handler": tool_sketch_add_arc,
    },
    {
        "name": "sketch_add_point",
        "description": "Add a sketch point (construction by default).",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "at": _XY,
                "construction": {"type": "boolean", "default": True},
            },
            ["sketch", "at"],
        ),
        "handler": tool_sketch_add_point,
    },
    {
        "name": "sketch_add_slot",
        "description": "Add an oblong slot (two lines + two semicircles) between start and end.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "start": _XY,
                "end": _XY,
                "radius": {"type": "number", "default": 4},
                "constrain": _CONSTRAIN,
                "construction": _CONSTRUCTION,
            },
            ["sketch", "start", "end", "radius"],
        ),
        "handler": tool_sketch_add_slot,
    },
    {
        "name": "sketch_add_bspline",
        "description": "Add an interpolated B-spline through sketch-plane points.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "points": {"type": "array", "items": _XY, "minItems": 2},
                "closed": {"type": "boolean", "default": False},
                "construction": _CONSTRUCTION,
            },
            ["sketch", "points"],
        ),
        "handler": tool_sketch_add_bspline,
    },
    {
        "name": "sketch_constraint",
        "description": (
            "Add a Sketcher constraint. type=coincident|horizontal|vertical|parallel|"
            "perpendicular|tangent|equal|symmetric|block|distance|distance_x|distance_y|"
            "radius|diameter|angle|point_on_object. geo1/geo2 are geo ids or origin|x|y. "
            "pos1/pos2=start|end|center|edge. value is mm or degrees (angle)."
        ),
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "type": {"type": "string", "enum": _CONSTRAINT_TYPES},
                "kind": {"type": "string", "description": "Alias of type"},
                "geo1": _GEO_REF,
                "pos1": _POS_REF,
                "geo2": _GEO_REF,
                "pos2": _POS_REF,
                "geo3": _GEO_REF,
                "pos3": _POS_REF,
                "value": {"type": "number"},
            },
            ["sketch"],
        ),
        "handler": tool_sketch_constraint,
    },
    {
        "name": "sketch_toggle_construction",
        "description": "Toggle construction (dashed reference) on one or more sketch geometries.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "geo_id": {"type": "integer"},
                "geo_ids": {"type": "array", "items": {"type": "integer"}},
            },
            ["sketch"],
        ),
        "handler": tool_sketch_toggle_construction,
    },
    {
        "name": "sketch_external",
        "description": "Project an edge or face from another object into the sketch as external geometry.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "target": {"type": "string"},
                "sub": {"description": "Edge1 / Face1 or 1-based index"},
                "edge": {"description": "Alias of sub"},
                "face": {"description": "Alias of sub"},
                "kind": {"type": "string", "enum": ["edge", "face"], "default": "edge"},
            },
            ["sketch", "target"],
        ),
        "handler": tool_sketch_external,
    },
    {
        "name": "sketch_fillet",
        "description": "Fillet the corner between two sketch edges.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "geo1": {"type": "integer"},
                "geo2": {"type": "integer"},
                "pos1": _POS_REF,
                "pos2": _POS_REF,
                "radius": {"type": "number", "default": 1},
            },
            ["sketch", "geo1", "geo2"],
        ),
        "handler": tool_sketch_fillet,
    },
    {
        "name": "sketch_info",
        "description": "List sketch geometry, constraints, solve status, and degrees of freedom.",
        "inputSchema": _schema({"sketch": _SKETCH_PROP}, ["sketch"]),
        "handler": tool_sketch_info,
    },
    {
        "name": "sketch_delete",
        "description": "Delete sketch geometries and/or constraints by id (highest ids first).",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "geo_ids": {"type": "array", "items": {"type": "integer"}},
                "constraint_ids": {"type": "array", "items": {"type": "integer"}},
            },
            ["sketch"],
        ),
        "handler": tool_sketch_delete,
    },
    {
        "name": "sketch_set_constraint",
        "description": "Change a driving constraint value (mm, or degrees for angle).",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "constraint_id": {"type": "integer"},
                "value": {"type": "number"},
            },
            ["sketch", "constraint_id", "value"],
        ),
        "handler": tool_sketch_set_constraint,
    },
    {
        "name": "sketch_pad",
        "description": (
            "Pad (extrude) a sketch into a solid via PartDesign, with Part extrude fallback. "
            "type=length|two_lengths|up_to_last|up_to_first|up_to_face|two_sides."
        ),
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "name": {"type": "string"},
                "body": {"type": "string"},
                "length": {"type": "number", "default": 10},
                "height": {"type": "number", "description": "Alias of length"},
                "midplane": {"type": "boolean", "default": False},
                "reversed": {"type": "boolean", "default": False},
                "type": {
                    "type": "string",
                    "enum": [
                        "length",
                        "dimension",
                        "two_lengths",
                        "up_to_last",
                        "up_to_first",
                        "up_to_face",
                        "two_sides",
                    ],
                    "default": "length",
                },
            },
            ["sketch"],
        ),
        "handler": tool_sketch_pad,
    },
    {
        "name": "sketch_pocket",
        "description": "Pocket (cut) a sketch from the active PartDesign body. through_all=true for a through cut.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "name": {"type": "string"},
                "body": {"type": "string"},
                "length": {"type": "number", "default": 5},
                "depth": {"type": "number", "description": "Alias of length"},
                "through_all": {"type": "boolean", "default": False},
                "reversed": {"type": "boolean", "default": False},
                "type": {
                    "type": "string",
                    "enum": ["length", "through_all", "up_to_first", "up_to_last", "up_to_face"],
                    "default": "length",
                },
            },
            ["sketch"],
        ),
        "handler": tool_sketch_pocket,
    },
    {
        "name": "sketch_revolve",
        "description": "Revolve a sketch around the sketch X (H) or Y (V) axis. angle in degrees.",
        "inputSchema": _schema(
            {
                "sketch": _SKETCH_PROP,
                "name": {"type": "string"},
                "body": {"type": "string"},
                "angle": {"type": "number", "default": 360},
                "axis": {"type": "string", "enum": ["x", "y", "h", "v"], "default": "y"},
            },
            ["sketch"],
        ),
        "handler": tool_sketch_revolve,
    },
]
