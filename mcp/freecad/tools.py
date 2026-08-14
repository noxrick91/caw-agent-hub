"""MCP tool schemas and FreeCAD script builders."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Callable

from backend import FreeCADError, FreeCADSession


ToolHandler = Callable[[FreeCADSession, dict[str, Any]], dict[str, Any]]


def _vec(v: Any, default: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> tuple[float, float, float]:
    if v is None:
        return default
    if isinstance(v, (list, tuple)) and len(v) >= 3:
        return float(v[0]), float(v[1]), float(v[2])
    raise FreeCADError(f"expected [x,y,z], got {v!r}")


def _placement_code(placement: Any) -> str:
    if not placement:
        return ""
    base = _vec(placement.get("base") if isinstance(placement, dict) else None)
    rot = placement.get("rotation") if isinstance(placement, dict) else None
    if rot and isinstance(rot, dict):
        axis = _vec(rot.get("axis"), (0.0, 0.0, 1.0))
        angle = float(rot.get("angle", 0.0))
        return textwrap.dedent(
            f"""
            obj.Placement = FreeCAD.Placement(
                FreeCAD.Vector{base},
                FreeCAD.Rotation(FreeCAD.Vector{axis}, {angle})
            )
            """
        )
    return f"obj.Placement = FreeCAD.Placement(FreeCAD.Vector{base}, FreeCAD.Rotation())\n"


def _unique_name(preferred: str | None, fallback: str) -> str:
    name = (preferred or fallback).strip() or fallback
    # FreeCAD labels can be anything; object Name is alphanumeric-ish.
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return safe or fallback


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------


def tool_status(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    return session.status()


def tool_create_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name") or "Unnamed"
    code = textwrap.dedent(
        f"""
        if FreeCAD.ActiveDocument is not None:
            pass
        doc = FreeCAD.newDocument({name!r})
        __result__ = {{"ok": True, "document": doc.Name, "label": doc.Label}}
        """
    )
    return session.execute(code)


def tool_open_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.open({path!r})
        __result__ = {{"ok": True, "document": doc.Name, "label": doc.Label, "path": {path!r}}}
        """
    )
    return session.execute(code)


def tool_save_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path")
    if path:
        code = textwrap.dedent(
            f"""
            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise RuntimeError("no active document")
            doc.saveAs({path!r})
            __result__ = {{"ok": True, "document": doc.Name, "path": {path!r}}}
            """
        )
    else:
        code = textwrap.dedent(
            """
            doc = FreeCAD.ActiveDocument
            if doc is None:
                raise RuntimeError("no active document")
            if not doc.FileName:
                raise RuntimeError("document has no path; pass path=")
            doc.save()
            __result__ = {"ok": True, "document": doc.Name, "path": doc.FileName}
            """
        )
    return session.execute(code)


def tool_close_document(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument if {name!r} is None else FreeCAD.getDocument({name!r})
        if doc is None:
            raise RuntimeError("document not found")
        n = doc.Name
        FreeCAD.closeDocument(n)
        __result__ = {{"ok": True, "closed": n}}
        """
    )
    return session.execute(code)


def tool_list_documents(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        docs = []
        for d in FreeCAD.listDocuments().values():
            docs.append({
                "name": d.Name,
                "label": d.Label,
                "path": d.FileName or None,
                "active": FreeCAD.ActiveDocument is not None and d.Name == FreeCAD.ActiveDocument.Name,
                "objects": len(d.Objects),
            })
        __result__ = {"ok": True, "documents": docs}
        """
    )
    return session.execute(code)


def tool_list_objects(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        objs = []
        for o in doc.Objects:
            info = {
                "name": o.Name,
                "label": o.Label,
                "type": o.TypeId,
                "visibility": bool(getattr(o, "Visibility", True)),
            }
            try:
                if hasattr(o, "Shape") and not o.Shape.isNull():
                    bb = o.Shape.BoundBox
                    info["bbox"] = {
                        "xmin": bb.XMin, "xmax": bb.XMax,
                        "ymin": bb.YMin, "ymax": bb.YMax,
                        "zmin": bb.ZMin, "zmax": bb.ZMax,
                        "xlength": bb.XLength, "ylength": bb.YLength, "zlength": bb.ZLength,
                    }
                    info["volume"] = float(o.Shape.Volume)
            except Exception:
                pass
            objs.append(info)
        __result__ = {"ok": True, "document": doc.Name, "objects": objs}
        """
    )
    return session.execute(code)


def tool_get_object(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        o = doc.getObject({name!r})
        if o is None:
            raise RuntimeError(f"object not found: {name}")
        props = {{}}
        for p in o.PropertiesList:
            try:
                v = getattr(o, p)
                if isinstance(v, (int, float, str, bool)) or v is None:
                    props[p] = v
                elif hasattr(v, "x") and hasattr(v, "y") and hasattr(v, "z"):
                    props[p] = [float(v.x), float(v.y), float(v.z)]
                else:
                    props[p] = str(v)
            except Exception:
                pass
        info = {{
            "name": o.Name,
            "label": o.Label,
            "type": o.TypeId,
            "properties": props,
        }}
        try:
            if hasattr(o, "Shape") and not o.Shape.isNull():
                bb = o.Shape.BoundBox
                info["bbox"] = {{
                    "xmin": bb.XMin, "xmax": bb.XMax,
                    "ymin": bb.YMin, "ymax": bb.YMax,
                    "zmin": bb.ZMin, "zmax": bb.ZMax,
                    "xlength": bb.XLength, "ylength": bb.YLength, "zlength": bb.ZLength,
                }}
                info["volume"] = float(o.Shape.Volume)
                info["area"] = float(o.Shape.Area)
        except Exception:
            pass
        __result__ = {{"ok": True, "object": info}}
        """
    )
    return session.execute(code)


def tool_delete_object(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    names = args.get("names")
    if not names:
        if not args.get("name"):
            raise FreeCADError("provide name or names")
        names = [args["name"]]
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        deleted = []
        for n in {names!r}:
            o = doc.getObject(n)
            if o is not None:
                doc.removeObject(n)
                deleted.append(n)
        doc.recompute()
        __result__ = {{"ok": True, "deleted": deleted}}
        """
    )
    return session.execute(code)


def tool_set_object_property(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    prop = args["property"]
    value = args["value"]
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        o = doc.getObject({name!r})
        if o is None:
            raise RuntimeError("object not found")
        val = {json.dumps(value)}
        if isinstance(val, list) and len(val) == 3 and all(isinstance(x, (int, float)) for x in val):
            cur = getattr(o, {prop!r}, None)
            if hasattr(cur, "x"):
                setattr(o, {prop!r}, FreeCAD.Vector(*val))
            else:
                setattr(o, {prop!r}, val)
        else:
            setattr(o, {prop!r}, val)
        doc.recompute()
        __result__ = {{"ok": True, "name": o.Name, "property": {prop!r}, "value": val}}
        """
    )
    return session.execute(code)


def _create_primitive(session: FreeCADSession, kind: str, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), kind.capitalize())
    placement = args.get("placement")
    place_code = _placement_code(placement)

    if kind == "box":
        l, w, h = float(args.get("length", 10)), float(args.get("width", 10)), float(args.get("height", 10))
        shape = f"Part.makeBox({l}, {w}, {h})"
    elif kind == "cylinder":
        r, h = float(args.get("radius", 5)), float(args.get("height", 10))
        angle = float(args.get("angle", 360))
        shape = f"Part.makeCylinder({r}, {h}, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {angle})"
    elif kind == "sphere":
        r = float(args.get("radius", 5))
        shape = f"Part.makeSphere({r})"
    elif kind == "cone":
        r1 = float(args.get("radius1", 5))
        r2 = float(args.get("radius2", 0))
        h = float(args.get("height", 10))
        angle = float(args.get("angle", 360))
        shape = f"Part.makeCone({r1}, {r2}, {h}, FreeCAD.Vector(0,0,0), FreeCAD.Vector(0,0,1), {angle})"
    elif kind == "torus":
        r1 = float(args.get("radius1", 10))
        r2 = float(args.get("radius2", 2))
        shape = f"Part.makeTorus({r1}, {r2})"
    elif kind == "wedge":
        xsize = float(args.get("xsize", 10))
        ysize = float(args.get("ysize", 10))
        zsize = float(args.get("zsize", 10))
        shape = f"Part.makeWedge(0, 0, 0, {zsize}, 0, {xsize}, {zsize}, {xsize}, {ysize}, {zsize})"
    else:
        raise FreeCADError(f"unknown primitive: {kind}")

    label = args.get("label") or name
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        shape = {shape}
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Label = {label!r}
        obj.Shape = shape
        {place_code}
        doc.recompute()
        bb = obj.Shape.BoundBox
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "label": obj.Label,
            "type": obj.TypeId,
            "bbox": {{
                "xlength": bb.XLength, "ylength": bb.YLength, "zlength": bb.ZLength,
                "xmin": bb.XMin, "ymin": bb.YMin, "zmin": bb.ZMin,
            }},
            "volume": float(obj.Shape.Volume),
        }}
        """
    )
    return session.execute(code)


def tool_create_box(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "box", args)


def tool_create_cylinder(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "cylinder", args)


def tool_create_sphere(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "sphere", args)


def tool_create_cone(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "cone", args)


def tool_create_torus(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "torus", args)


def tool_create_wedge(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    return _create_primitive(session, "wedge", args)


def tool_boolean(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    op = args["operation"]  # fuse|cut|common
    a = args["object_a"]
    b = args["object_b"]
    name = _unique_name(args.get("name"), f"{op}_{a}_{b}")
    keep = bool(args.get("keep_originals", False))
    method = {"fuse": "fuse", "cut": "cut", "common": "common"}.get(op)
    if not method:
        raise FreeCADError("operation must be fuse|cut|common")
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        oa = doc.getObject({a!r})
        ob = doc.getObject({b!r})
        if oa is None or ob is None:
            raise RuntimeError("object_a or object_b not found")
        shape = oa.Shape.{method}(ob.Shape)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        if not {keep!r}:
            doc.removeObject(oa.Name)
            doc.removeObject(ob.Name)
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "operation": {op!r},
            "volume": float(obj.Shape.Volume),
        }}
        """
    )
    return session.execute(code)


def tool_fillet(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    radius = float(args["radius"])
    edges = args.get("edges")  # optional 1-based edge indices
    out_name = _unique_name(args.get("result_name"), f"{name}_fillet")
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = doc.getObject({name!r})
        if src is None:
            raise RuntimeError("object not found")
        edge_ids = {edges!r}
        if edge_ids:
            selected = [src.Shape.Edges[i-1] for i in edge_ids]
        else:
            selected = list(src.Shape.Edges)
        shape = src.Shape.makeFillet({radius}, selected)
        obj = doc.addObject("Part::Feature", {out_name!r})
        obj.Shape = shape
        doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "radius": {radius}, "edges": len(selected)}}
        """
    )
    return session.execute(code)


def tool_chamfer(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    dist = float(args.get("distance", args.get("size", 1.0)))
    edges = args.get("edges")
    out_name = _unique_name(args.get("result_name"), f"{name}_chamfer")
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = doc.getObject({name!r})
        if src is None:
            raise RuntimeError("object not found")
        edge_ids = {edges!r}
        if edge_ids:
            selected = [src.Shape.Edges[i-1] for i in edge_ids]
        else:
            selected = list(src.Shape.Edges)
        shape = src.Shape.makeChamfer({dist}, selected)
        obj = doc.addObject("Part::Feature", {out_name!r})
        obj.Shape = shape
        doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "distance": {dist}, "edges": len(selected)}}
        """
    )
    return session.execute(code)


def tool_transform(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    translate = args.get("translate")
    rotate = args.get("rotate")  # {axis:[x,y,z], angle:deg}
    scale = args.get("scale")
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        obj = doc.getObject({name!r})
        if obj is None:
            raise RuntimeError("object not found")
        shape = obj.Shape.copy()
        t = {json.dumps(translate)}
        r = {json.dumps(rotate)}
        s = {json.dumps(scale)}
        if t:
            shape.translate(FreeCAD.Vector(float(t[0]), float(t[1]), float(t[2])))
        if r:
            axis = r.get("axis", [0,0,1])
            angle = float(r.get("angle", 0))
            shape.rotate(FreeCAD.Vector(0,0,0), FreeCAD.Vector(*axis), angle)
        if s is not None:
            if isinstance(s, (int, float)):
                sx = sy = sz = float(s)
            else:
                sx, sy, sz = float(s[0]), float(s[1]), float(s[2])
            m = FreeCAD.Matrix()
            m.scale(sx, sy, sz)
            shape = shape.transformGeometry(m)
        obj.Shape = shape
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name}}
        """
    )
    return session.execute(code)


def tool_mirror(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    axis = (args.get("axis") or "x").lower()
    out_name = _unique_name(args.get("result_name"), f"{name}_mirror")
    normals = {"x": (1, 0, 0), "y": (0, 1, 0), "z": (0, 0, 1)}
    if axis not in normals:
        raise FreeCADError("axis must be x|y|z")
    n = normals[axis]
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = doc.getObject({name!r})
        if src is None:
            raise RuntimeError("object not found")
        shape = src.Shape.mirror(FreeCAD.Vector(0,0,0), FreeCAD.Vector{n})
        obj = doc.addObject("Part::Feature", {out_name!r})
        obj.Shape = shape
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "axis": {axis!r}}}
        """
    )
    return session.execute(code)


def tool_copy_object(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    out_name = _unique_name(args.get("result_name"), f"{name}_copy")
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = doc.getObject({name!r})
        if src is None:
            raise RuntimeError("object not found")
        obj = doc.copyObject(src)
        obj.Label = {out_name!r}
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "label": obj.Label, "source": {name!r}}}
        """
    )
    return session.execute(code)


def tool_create_sketch_pad(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Create a simple rectangular/circular pad via Part extrusion (no full Sketcher dependency)."""
    profile = (args.get("profile") or "rectangle").lower()
    length = float(args.get("length", 20))
    width = float(args.get("width", 10))
    radius = float(args.get("radius", 5))
    height = float(args.get("height", 5))
    name = _unique_name(args.get("name"), "Pad")
    if profile == "circle":
        face = f"Part.Face(Part.Wire(Part.makeCircle({radius})))"
    else:
        face = (
            f"Part.Face(Part.makePolygon(["
            f"FreeCAD.Vector(0,0,0), FreeCAD.Vector({length},0,0), "
            f"FreeCAD.Vector({length},{width},0), FreeCAD.Vector(0,{width},0), FreeCAD.Vector(0,0,0)]))"
        )
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        face = {face}
        solid = face.extrude(FreeCAD.Vector(0, 0, {height}))
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = solid
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "profile": {profile!r},
            "height": {height},
            "volume": float(obj.Shape.Volume),
        }}
        """
    )
    return session.execute(code)


def tool_pocket(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Cut a rectangular or circular pocket from an object."""
    target = args["target"]
    profile = (args.get("profile") or "rectangle").lower()
    depth = float(args.get("depth", 5))
    length = float(args.get("length", 10))
    width = float(args.get("width", 10))
    radius = float(args.get("radius", 3))
    origin = _vec(args.get("origin"), (0.0, 0.0, 0.0))
    name = _unique_name(args.get("name"), f"{target}_pocket")
    if profile == "circle":
        tool_shape = (
            f"Part.Face(Part.Wire(Part.makeCircle({radius}, FreeCAD.Vector{origin}, "
            f"FreeCAD.Vector(0,0,1)))).extrude(FreeCAD.Vector(0,0,-{depth}))"
        )
    else:
        x, y, z = origin
        tool_shape = (
            f"Part.Face(Part.makePolygon(["
            f"FreeCAD.Vector({x},{y},{z}), FreeCAD.Vector({x}+{length},{y},{z}), "
            f"FreeCAD.Vector({x}+{length},{y}+{width},{z}), FreeCAD.Vector({x},{y}+{width},{z}), "
            f"FreeCAD.Vector({x},{y},{z})])).extrude(FreeCAD.Vector(0,0,-{depth}))"
        )
    code = textwrap.dedent(
        f"""
        import Part
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = doc.getObject({target!r})
        if src is None:
            raise RuntimeError("target not found")
        cutter = {tool_shape}
        shape = src.Shape.cut(cutter)
        obj = doc.addObject("Part::Feature", {name!r})
        obj.Shape = shape
        doc.removeObject(src.Name)
        doc.recompute()
        __result__ = {{"ok": True, "name": obj.Name, "volume": float(obj.Shape.Volume)}}
        """
    )
    return session.execute(code)


def tool_export(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
    fmt = (args.get("format") or Path_suffix(path)).lower().lstrip(".")
    names = args.get("objects")
    code = textwrap.dedent(
        f"""
        import os
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        path = {path!r}
        fmt = {fmt!r}
        names = {names!r}
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
                objs = list(doc.Objects)
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        if fmt in ("step", "stp"):
            import Import
            Import.export(objs, path)
        elif fmt == "stl":
            import Mesh
            Mesh.export(objs, path)
        elif fmt in ("brep", "brp"):
            shape = objs[0].Shape
            for o in objs[1:]:
                shape = shape.fuse(o.Shape)
            shape.exportBrep(path)
        elif fmt == "fcstd":
            doc.saveAs(path)
        else:
            raise RuntimeError(f"unsupported format: {{fmt}}")
        __result__ = {{"ok": True, "path": path, "format": fmt, "objects": [o.Name for o in objs]}}
        """
    )
    return session.execute(code)


def Path_suffix(path: str) -> str:
    from pathlib import Path

    return Path(path).suffix or "step"


def tool_import(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
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
        if lower.endswith((".step", ".stp", ".iges", ".igs", ".brep", ".brp")):
            import Import
            Import.insert(path, doc.Name)
        elif lower.endswith(".stl"):
            import Mesh
            Mesh.insert(path, doc.Name)
        elif lower.endswith(".fcstd"):
            FreeCAD.open(path)
            doc = FreeCAD.ActiveDocument
            before = set()
        else:
            raise RuntimeError("unsupported import type")
        doc.recompute()
        added = [o.Name for o in doc.Objects if o.Name not in before]
        __result__ = {{"ok": True, "path": path, "added": added, "document": doc.Name}}
        """
    )
    return session.execute(code)


def tool_measure(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        name = {name!r}
        if name:
            objs = [doc.getObject(name)]
            if objs[0] is None:
                raise RuntimeError("object not found")
        else:
            objs = [o for o in doc.Objects if hasattr(o, "Shape") and not o.Shape.isNull()]
        items = []
        for o in objs:
            bb = o.Shape.BoundBox
            items.append({{
                "name": o.Name,
                "volume": float(o.Shape.Volume),
                "area": float(o.Shape.Area),
                "bbox": {{
                    "xmin": bb.XMin, "xmax": bb.XMax,
                    "ymin": bb.YMin, "ymax": bb.YMax,
                    "zmin": bb.ZMin, "zmax": bb.ZMax,
                    "xlength": bb.XLength, "ylength": bb.YLength, "zlength": bb.ZLength,
                }},
            }})
        __result__ = {{"ok": True, "measurements": items}}
        """
    )
    return session.execute(code)


def tool_execute_python(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    # Ensure __result__ can be set by user code
    wrapped = code
    if "__result__" not in code:
        wrapped = code + "\n\nif '__result__' not in dir() and '__result__' not in globals():\n    __result__ = {'ok': True}\n"
    return session.execute(wrapped)


def tool_screenshot(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path") or "freecad_view.png"
    view = args.get("view") or "isometric"
    code = textwrap.dedent(
        f"""
        import os
        path = {path!r}
        view = {view!r}
        try:
            import FreeCADGui
        except Exception as e:
            raise RuntimeError(f"GUI not available for screenshot: {{e}}")
        if FreeCAD.ActiveDocument is None:
            raise RuntimeError("no active document")
        FreeCADGui.ActiveDocument.ActiveView.fitAll()
        views = {{
            "isometric": "viewIsometric",
            "front": "viewFront",
            "top": "viewTop",
            "right": "viewRight",
            "left": "viewLeft",
            "rear": "viewRear",
            "bottom": "viewBottom",
        }}
        fn = views.get(view)
        av = FreeCADGui.ActiveDocument.ActiveView
        if fn and hasattr(av, fn):
            getattr(av, fn)()
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        av.saveImage(path, 1280, 720, "Current")
        __result__ = {{"ok": True, "path": path, "view": view}}
        """
    )
    return session.execute(code)


def tool_recompute(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        doc.recompute()
        __result__ = {"ok": True, "document": doc.Name, "objects": len(doc.Objects)}
        """
    )
    return session.execute(code)


def tool_set_visibility(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    visible = bool(args.get("visible", True))
    code = textwrap.dedent(
        f"""
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        o = doc.getObject({name!r})
        if o is None:
            raise RuntimeError("object not found")
        o.Visibility = {visible!r}
        __result__ = {{"ok": True, "name": o.Name, "visible": {visible!r}}}
        """
    )
    return session.execute(code)


# ---------------------------------------------------------------------------
# Registry / schemas
# ---------------------------------------------------------------------------

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


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


TOOLS: list[dict[str, Any]] = [
    {
        "name": "freecad_status",
        "description": "PREFERRED first step for any 3D/CAD task: check FreeCAD backend (bridge / in-process / FreeCADCmd) and active document. Call this before modeling.",
        "inputSchema": _schema({}),
        "handler": tool_status,
    },
    {
        "name": "create_document",
        "description": "Create a new FreeCAD document.",
        "inputSchema": _schema({"name": {"type": "string", "description": "Document name"}}),
        "handler": tool_create_document,
    },
    {
        "name": "open_document",
        "description": "Open an existing .FCStd (or supported) document from disk.",
        "inputSchema": _schema({"path": {"type": "string"}}, ["path"]),
        "handler": tool_open_document,
    },
    {
        "name": "save_document",
        "description": "Save the active document. Pass path for saveAs.",
        "inputSchema": _schema({"path": {"type": "string", "description": "Optional save path"}}),
        "handler": tool_save_document,
    },
    {
        "name": "close_document",
        "description": "Close a document by name (default: active).",
        "inputSchema": _schema({"name": {"type": "string"}}),
        "handler": tool_close_document,
    },
    {
        "name": "list_documents",
        "description": "List open FreeCAD documents.",
        "inputSchema": _schema({}),
        "handler": tool_list_documents,
    },
    {
        "name": "list_objects",
        "description": "List objects in the active document with bbox/volume when available.",
        "inputSchema": _schema({}),
        "handler": tool_list_objects,
    },
    {
        "name": "get_object",
        "description": "Get detailed info and properties for one object.",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
        "handler": tool_get_object,
    },
    {
        "name": "delete_object",
        "description": "Delete one or more objects by name.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "names": {"type": "array", "items": {"type": "string"}},
            }
        ),
        "handler": tool_delete_object,
    },
    {
        "name": "set_object_property",
        "description": "Set a FreeCAD object property (Length, Radius, Label, Placement vector props, etc.).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "property": {"type": "string"},
                "value": {},
            },
            ["name", "property", "value"],
        ),
        "handler": tool_set_object_property,
    },
    {
        "name": "set_visibility",
        "description": "Show or hide an object.",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "visible": {"type": "boolean"}},
            ["name"],
        ),
        "handler": tool_set_visibility,
    },
    {
        "name": "create_box",
        "description": "Create a box solid (Part::Feature).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "length": {"type": "number", "default": 10},
                "width": {"type": "number", "default": 10},
                "height": {"type": "number", "default": 10},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_box,
    },
    {
        "name": "create_cylinder",
        "description": "Create a cylinder solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius": {"type": "number", "default": 5},
                "height": {"type": "number", "default": 10},
                "angle": {"type": "number", "default": 360},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_cylinder,
    },
    {
        "name": "create_sphere",
        "description": "Create a sphere solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius": {"type": "number", "default": 5},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_sphere,
    },
    {
        "name": "create_cone",
        "description": "Create a cone solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius1": {"type": "number", "default": 5},
                "radius2": {"type": "number", "default": 0},
                "height": {"type": "number", "default": 10},
                "angle": {"type": "number", "default": 360},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_cone,
    },
    {
        "name": "create_torus",
        "description": "Create a torus solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius1": {"type": "number", "default": 10},
                "radius2": {"type": "number", "default": 2},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_torus,
    },
    {
        "name": "create_wedge",
        "description": "Create a wedge solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "xsize": {"type": "number", "default": 10},
                "ysize": {"type": "number", "default": 10},
                "zsize": {"type": "number", "default": 10},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_wedge,
    },
    {
        "name": "boolean_op",
        "description": "Boolean fuse / cut / common between two objects. Removes originals unless keep_originals=true.",
        "inputSchema": _schema(
            {
                "operation": {"type": "string", "enum": ["fuse", "cut", "common"]},
                "object_a": {"type": "string"},
                "object_b": {"type": "string"},
                "name": {"type": "string"},
                "keep_originals": {"type": "boolean", "default": False},
            },
            ["operation", "object_a", "object_b"],
        ),
        "handler": tool_boolean,
    },
    {
        "name": "fillet",
        "description": "Fillet edges of a solid. edges is optional 1-based edge indices; default all edges.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "radius": {"type": "number"},
                "edges": {"type": "array", "items": {"type": "integer"}},
                "result_name": {"type": "string"},
            },
            ["name", "radius"],
        ),
        "handler": tool_fillet,
    },
    {
        "name": "chamfer",
        "description": "Chamfer edges of a solid.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "distance": {"type": "number"},
                "edges": {"type": "array", "items": {"type": "integer"}},
                "result_name": {"type": "string"},
            },
            ["name"],
        ),
        "handler": tool_chamfer,
    },
    {
        "name": "transform",
        "description": "Translate / rotate / scale an object's shape.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "translate": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotate": {
                    "type": "object",
                    "properties": {
                        "axis": {"type": "array", "items": {"type": "number"}},
                        "angle": {"type": "number", "description": "degrees"},
                    },
                },
                "scale": {
                    "description": "Uniform number or [sx,sy,sz]",
                },
            },
            ["name"],
        ),
        "handler": tool_transform,
    },
    {
        "name": "mirror",
        "description": "Mirror an object across XY/YZ/ZX plane through origin (axis=x|y|z is the normal).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "axis": {"type": "string", "enum": ["x", "y", "z"], "default": "x"},
                "result_name": {"type": "string"},
            },
            ["name"],
        ),
        "handler": tool_mirror,
    },
    {
        "name": "copy_object",
        "description": "Duplicate an object in the active document.",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "result_name": {"type": "string"}},
            ["name"],
        ),
        "handler": tool_copy_object,
    },
    {
        "name": "extrude_profile",
        "description": "Extrude a rectangle or circle profile into a solid (simple pad).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "profile": {"type": "string", "enum": ["rectangle", "circle"], "default": "rectangle"},
                "length": {"type": "number", "default": 20},
                "width": {"type": "number", "default": 10},
                "radius": {"type": "number", "default": 5},
                "height": {"type": "number", "default": 5},
            }
        ),
        "handler": tool_create_sketch_pad,
    },
    {
        "name": "pocket",
        "description": "Cut a rectangular or circular pocket from a target solid.",
        "inputSchema": _schema(
            {
                "target": {"type": "string"},
                "name": {"type": "string"},
                "profile": {"type": "string", "enum": ["rectangle", "circle"], "default": "rectangle"},
                "depth": {"type": "number", "default": 5},
                "length": {"type": "number"},
                "width": {"type": "number"},
                "radius": {"type": "number"},
                "origin": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
            },
            ["target"],
        ),
        "handler": tool_pocket,
    },
    {
        "name": "export_model",
        "description": "Export active document objects to STEP/STL/BREP/FCStd.",
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "format": {"type": "string", "enum": ["step", "stl", "brep", "fcstd"]},
                "objects": {"type": "array", "items": {"type": "string"}},
            },
            ["path"],
        ),
        "handler": tool_export,
    },
    {
        "name": "import_model",
        "description": "Import STEP/IGES/BREP/STL/FCStd into the active document.",
        "inputSchema": _schema({"path": {"type": "string"}}, ["path"]),
        "handler": tool_import,
    },
    {
        "name": "measure",
        "description": "Measure volume/area/bbox for one object or all solids.",
        "inputSchema": _schema({"name": {"type": "string"}}),
        "handler": tool_measure,
    },
    {
        "name": "recompute",
        "description": "Force recompute of the active document.",
        "inputSchema": _schema({}),
        "handler": tool_recompute,
    },
    {
        "name": "screenshot",
        "description": "Capture the 3D view to a PNG (requires FreeCAD GUI / bridge).",
        "inputSchema": _schema(
            {
                "path": {"type": "string", "default": "freecad_view.png"},
                "view": {
                    "type": "string",
                    "enum": ["isometric", "front", "top", "right", "left", "rear", "bottom"],
                    "default": "isometric",
                },
            }
        ),
        "handler": tool_screenshot,
    },
    {
        "name": "execute_python",
        "description": (
            "Execute arbitrary FreeCAD Python. Available: FreeCAD, Part, Draft, Sketcher, Mesh, Import, "
            "Assembly helpers, and FreeCADGui when in GUI. Set __result__ to return structured data."
        ),
        "inputSchema": _schema({"code": {"type": "string"}}, ["code"]),
        "handler": tool_execute_python,
    },
]

# Assembly / kinematics tools (FreeCAD 1.0 Assembly WB + App::Part fallback)
from assembly_tools import ASSEMBLY_TOOLS  # noqa: E402
from assembly_advanced_tools import ASSEMBLY_ADVANCED_TOOLS  # noqa: E402
from animation_tools import ANIMATION_TOOLS  # noqa: E402
from drawing_tools import DRAWING_TOOLS  # noqa: E402
from part_tools import PART_TOOLS  # noqa: E402
from project_tools import PROJECT_TOOLS  # noqa: E402
from shape_tools import SHAPE_TOOLS  # noqa: E402
from structure_tools import STRUCTURE_TOOLS  # noqa: E402
from handoff_tools import HANDOFF_TOOLS  # noqa: E402
from urdf_tools import URDF_TOOLS  # noqa: E402
from sketch_tools import SKETCH_TOOLS  # noqa: E402

TOOLS.extend(SKETCH_TOOLS)
TOOLS.extend(ASSEMBLY_TOOLS)
TOOLS.extend(ASSEMBLY_ADVANCED_TOOLS)
TOOLS.extend(PROJECT_TOOLS)
TOOLS.extend(PART_TOOLS)
TOOLS.extend(SHAPE_TOOLS)
TOOLS.extend(STRUCTURE_TOOLS)
TOOLS.extend(DRAWING_TOOLS)
TOOLS.extend(ANIMATION_TOOLS)
TOOLS.extend(HANDOFF_TOOLS)
TOOLS.extend(URDF_TOOLS)


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in TOOLS
    ]


HANDLERS: dict[str, ToolHandler] = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(session: FreeCADSession, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in HANDLERS:
        raise FreeCADError(f"unknown tool: {name}")
    return HANDLERS[name](session, arguments or {})
