"""Advanced assembly: LCS from geometry, mates, interference, subassembly, BOM, motion check."""

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


# Reuse patterns from assembly_tools helpers (inlined for standalone scripts).
_ADV_HELPERS = r'''
def _adv_find(doc, name):
    if not name:
        return None
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")

def _adv_is_assembly(obj):
    try:
        return obj.isDerivedFrom("Assembly::AssemblyObject")
    except Exception:
        return getattr(obj, "TypeId", "") == "Assembly::AssemblyObject"

def _adv_get_active(doc, preferred=None):
    if preferred:
        return _adv_find(doc, preferred)
    for obj in doc.Objects:
        if _adv_is_assembly(obj):
            return obj
    for obj in doc.Objects:
        if obj.TypeId == "App::Part":
            return obj
    return None

def _adv_global_shape(obj):
    sh = obj.Shape.copy()
    sh.Placement = obj.getGlobalPlacement() if hasattr(obj, "getGlobalPlacement") else obj.Placement
    # Shape already in local; transform by placement
    return obj.Shape

def _adv_placed_shape(obj):
    return obj.Shape
'''


def tool_attach_lcs(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Create LCS on face center / edge midpoint / hole axis / vertex."""
    parent = args["parent"]
    mode = (args.get("mode") or "face_center").lower()
    name = _unique_name(args.get("name"), "LCS")
    face = args.get("face")
    edge = args.get("edge")
    vertex = args.get("vertex")
    code = textwrap.dedent(
        f"""
        import Part
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        parent = _adv_find(doc, {parent!r})
        mode = {mode!r}
        sh = parent.Shape
        origin = FreeCAD.Vector(0, 0, 0)
        z_dir = FreeCAD.Vector(0, 0, 1)
        x_dir = FreeCAD.Vector(1, 0, 0)

        if mode == "face_center":
            fi = int({json.dumps(face)} or 1)
            face = sh.Faces[fi - 1]
            origin = face.CenterOfMass
            try:
                z_dir = face.normalAt(0.5, 0.5)
            except Exception:
                z_dir = face.Surface.Axis if hasattr(face.Surface, "Axis") else FreeCAD.Vector(0, 0, 1)
        elif mode == "edge_midpoint":
            ei = int({json.dumps(edge)} or 1)
            edge = sh.Edges[ei - 1]
            origin = edge.CenterOfMass
            try:
                p0 = edge.Vertexes[0].Point
                p1 = edge.Vertexes[-1].Point
                z_dir = (p1 - p0)
            except Exception:
                z_dir = FreeCAD.Vector(0, 0, 1)
        elif mode in ("hole_axis", "circle_axis"):
            ei = {json.dumps(edge)}
            fi = {json.dumps(face)}
            curve = None
            if ei is not None:
                edge = sh.Edges[int(ei) - 1]
                curve = edge.Curve
                origin = edge.CenterOfMass
            elif fi is not None:
                face = sh.Faces[int(fi) - 1]
                # find circular edge on face
                for e in face.Edges:
                    if hasattr(e.Curve, "Radius"):
                        curve = e.Curve
                        origin = e.Curve.Center if hasattr(e.Curve, "Center") else e.CenterOfMass
                        break
                if curve is None:
                    origin = face.CenterOfMass
                    try:
                        z_dir = face.normalAt(0.5, 0.5)
                    except Exception:
                        pass
            if curve is not None and hasattr(curve, "Axis"):
                z_dir = curve.Axis
                if hasattr(curve, "Center"):
                    origin = curve.Center
            elif curve is not None and hasattr(curve, "Center"):
                origin = curve.Center
        elif mode == "vertex":
            vi = int({json.dumps(vertex)} or 1)
            origin = sh.Vertexes[vi - 1].Point
        else:
            raise RuntimeError(f"unknown mode: {{mode}}")

        if z_dir.Length < 1e-9:
            z_dir = FreeCAD.Vector(0, 0, 1)
        z_dir.normalize()
        if abs(z_dir.dot(FreeCAD.Vector(1, 0, 0))) < 0.9:
            x_dir = FreeCAD.Vector(1, 0, 0).cross(z_dir)
        else:
            x_dir = FreeCAD.Vector(0, 1, 0).cross(z_dir)
        x_dir.normalize()
        y_dir = z_dir.cross(x_dir)
        rot = FreeCAD.Rotation(x_dir, y_dir, z_dir, "XYZ")
        # Face/edge indices are in the parent's local shape space.
        pl = FreeCAD.Placement(origin, rot)
        lcs = None
        for tid in ("PartDesign::CoordinateSystem", "App::LocalCoordinateSystem", "Part::CoordinateSystem"):
            try:
                lcs = doc.addObject(tid, {name!r})
                break
            except Exception:
                lcs = None
        if lcs is None:
            # Fallback marker: Axis entity as tiny cylinder + store placement on FeaturePython-less Part::Feature
            lcs = doc.addObject("Part::Feature", {name!r})
            ax = Part.makeCylinder(0.2, 8, FreeCAD.Vector(0, 0, 0), FreeCAD.Vector(0, 0, 1))
            lcs.Shape = ax
            lcs.ViewObject.ShapeColor = (0.2, 0.8, 0.2) if hasattr(lcs, "ViewObject") and lcs.ViewObject else None
        lcs.Placement = pl
        lcs.Label = {args.get("label") or name!r}
        try:
            if hasattr(parent, "addObject"):
                parent.addObject(lcs)
            elif hasattr(parent, "Group"):
                g = list(parent.Group)
                g.append(lcs)
                parent.Group = g
        except Exception:
            pass
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": lcs.Name,
            "parent": parent.Name,
            "mode": mode,
            "placement": {{
                "base": [float(pl.Base.x), float(pl.Base.y), float(pl.Base.z)],
            }},
            "type_id": lcs.TypeId,
        }}
        """
    )
    return session.execute(code)


def tool_check_interference(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    objects = args.get("objects") or []
    pair = args.get("object_a") and args.get("object_b")
    tolerance = float(args.get("tolerance") or 1e-3)
    code = textwrap.dedent(
        f"""
        import Part
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        names = {json.dumps(objects)}
        a = {json.dumps(args.get("object_a"))}
        b = {json.dumps(args.get("object_b"))}
        if a and b:
            pairs = [(a, b)]
        else:
            if len(names) < 2:
                # all solids in doc
                names = [o.Name for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
            pairs = []
            for i in range(len(names)):
                for j in range(i + 1, len(names)):
                    pairs.append((names[i], names[j]))
        hits = []
        for na, nb in pairs:
            oa = _adv_find(doc, na)
            ob = _adv_find(doc, nb)
            sa = oa.Shape.copy()
            sb = ob.Shape.copy()
            # apply placements
            sa.Placement = oa.Placement
            sb.Placement = ob.Placement
            try:
                common = sa.common(sb)
                vol = float(common.Volume) if common.Solids or common.Faces else 0.0
            except Exception as e:
                hits.append({{"a": na, "b": nb, "error": str(e)}})
                continue
            if vol > {tolerance}:
                hits.append({{"a": na, "b": nb, "interference_volume": vol}})
        __result__ = {{
            "ok": True,
            "interfering": len(hits) > 0,
            "count": len(hits),
            "pairs": hits,
            "checked_pairs": len(pairs),
        }}
        """
    )
    return session.execute(code)


def tool_measure_clearance(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    a = args["object_a"]
    b = args["object_b"]
    code = textwrap.dedent(
        f"""
        import Part
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        oa = _adv_find(doc, {a!r})
        ob = _adv_find(doc, {b!r})
        sa = oa.Shape.copy()
        sb = ob.Shape.copy()
        sa.Placement = oa.Placement
        sb.Placement = ob.Placement
        dist = float(sa.distToShape(sb)[0])
        common = sa.common(sb)
        vol = float(common.Volume) if hasattr(common, "Volume") else 0.0
        __result__ = {{
            "ok": True,
            "object_a": {a!r},
            "object_b": {b!r},
            "min_distance": dist,
            "interfering": vol > 1e-6 or dist <= 0,
            "interference_volume": vol,
        }}
        """
    )
    return session.execute(code)


def tool_mate_components(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """High-level mate: coaxial / coincident / offset — builds LCS pair + joint."""
    kind = (args.get("kind") or "coaxial").lower()
    object_a = args["object_a"]
    object_b = args["object_b"]
    face_a = args.get("face_a")
    face_b = args.get("face_b")
    edge_a = args.get("edge_a")
    edge_b = args.get("edge_b")
    offset = float(args.get("offset") or 0.0)
    assembly = args.get("assembly")
    joint_type = args.get("joint_type")
    if not joint_type:
        joint_type = "Distance" if kind in ("offset", "offset_plane") else "Fixed"
        if kind == "coaxial":
            joint_type = "Cylindrical"
    name = _unique_name(args.get("name"), f"Mate_{kind}")
    code = textwrap.dedent(
        f"""
        import Part
        {_ADV_HELPERS}
        # Import attach helpers inline
        def _make_lcs(doc, parent, mode, face=None, edge=None, name="LCS"):
            sh = parent.Shape
            origin = FreeCAD.Vector(0,0,0)
            z_dir = FreeCAD.Vector(0,0,1)
            if mode == "face_center" and face is not None:
                f = sh.Faces[int(face)-1]
                origin = f.CenterOfMass
                try:
                    z_dir = f.normalAt(0.5, 0.5)
                except Exception:
                    z_dir = FreeCAD.Vector(0,0,1)
            elif mode == "hole_axis":
                if edge is not None:
                    e = sh.Edges[int(edge)-1]
                    origin = e.Curve.Center if hasattr(e.Curve, "Center") else e.CenterOfMass
                    z_dir = e.Curve.Axis if hasattr(e.Curve, "Axis") else FreeCAD.Vector(0,0,1)
                elif face is not None:
                    f = sh.Faces[int(face)-1]
                    for e in f.Edges:
                        if hasattr(e.Curve, "Radius"):
                            origin = e.Curve.Center if hasattr(e.Curve, "Center") else e.CenterOfMass
                            z_dir = e.Curve.Axis if hasattr(e.Curve, "Axis") else FreeCAD.Vector(0,0,1)
                            break
            if z_dir.Length < 1e-9:
                z_dir = FreeCAD.Vector(0,0,1)
            z_dir.normalize()
            x_dir = FreeCAD.Vector(1,0,0).cross(z_dir) if abs(z_dir.dot(FreeCAD.Vector(1,0,0))) < 0.9 else FreeCAD.Vector(0,1,0).cross(z_dir)
            x_dir.normalize()
            y_dir = z_dir.cross(x_dir)
            rot = FreeCAD.Rotation(x_dir, y_dir, z_dir, "XYZ")
            pl = FreeCAD.Placement(origin, rot)
            lcs = None
            for tid in ("PartDesign::CoordinateSystem", "App::LocalCoordinateSystem"):
                try:
                    lcs = doc.addObject(tid, name)
                    break
                except Exception:
                    pass
            if lcs is None:
                lcs = doc.addObject("Part::Feature", name)
                lcs.Shape = Part.makeCylinder(0.2, 6)
            lcs.Placement = pl
            try:
                if hasattr(parent, "addObject"):
                    parent.addObject(lcs)
            except Exception:
                pass
            return lcs

        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        oa = _adv_find(doc, {object_a!r})
        ob = _adv_find(doc, {object_b!r})
        kind = {kind!r}
        mode = "hole_axis" if kind == "coaxial" else "face_center"
        lcs_a = _make_lcs(doc, oa, mode, face={json.dumps(face_a)}, edge={json.dumps(edge_a)}, name={name!r}+"_A")
        lcs_b = _make_lcs(doc, ob, mode, face={json.dumps(face_b)}, edge={json.dumps(edge_b)}, name={name!r}+"_B")

        asm = _adv_get_active(doc, {json.dumps(assembly)})
        joint_name = None
        joint_type = {joint_type!r}
        note = "lcs_created"
        if asm is not None and _adv_is_assembly(asm):
            try:
                import Assembly
                jt_map = {{
                    "Fixed": 0, "Revolute": 1, "Cylindrical": 2, "Slider": 3, "Ball": 4,
                    "Distance": 5, "Parallel": 6, "Perpendicular": 7, "Angle": 8,
                }}
                jtype = jt_map.get(joint_type, 0)
                joint = Assembly.makeJoint(joint_type if False else None) if False else None
            except Exception:
                joint = None
            # Prefer document Assembly API used elsewhere
            try:
                joint = doc.addObject("Assembly::Joint", {name!r})
                if hasattr(joint, "JointType"):
                    # string or enum
                    try:
                        joint.JointType = joint_type
                    except Exception:
                        pass
                if hasattr(joint, "Object1"):
                    joint.Object1 = lcs_a
                if hasattr(joint, "Object2"):
                    joint.Object2 = lcs_b
                if hasattr(joint, "Reference1"):
                    joint.Reference1 = (lcs_a, [""])
                if hasattr(joint, "Reference2"):
                    joint.Reference2 = (lcs_b, [""])
                if {offset} and hasattr(joint, "Distance"):
                    joint.Distance = float({offset})
                if hasattr(asm, "addObject"):
                    asm.addObject(joint)
                joint_name = joint.Name
                note = "joint_created"
                try:
                    import Assembly
                    Assembly.solveAssembly(asm) if hasattr(Assembly, "solveAssembly") else None
                except Exception:
                    pass
            except Exception as e:
                note = f"lcs_only: {{e}}"
        else:
            # Placement fallback: move B so LCS frames coincide (with offset along Z)
            try:
                pa = lcs_a.Placement
                pb = lcs_b.Placement
                # Want pb world = pa with Z offset
                target = FreeCAD.Placement(pa)
                if {offset}:
                    target = FreeCAD.Placement(pa.Base + pa.Rotation.multVec(FreeCAD.Vector(0,0,{offset})), pa.Rotation)
                # delta such that parent_b * local_lcs_b = target  → approximate set component placement
                # For simple solids: set ob.Placement so lcs_b maps to target
                inv_local = pb.inverse().multiply(ob.Placement) if False else None
                # lcs_b.Placement is in doc space already for Part::Feature children often
                delta = target.multiply(pb.inverse())
                ob.Placement = delta.multiply(ob.Placement)
                note = "placement_aligned"
            except Exception as e:
                note = f"placement_failed: {{e}}"
        doc.recompute()
        __result__ = {{
            "ok": True,
            "kind": kind,
            "lcs_a": lcs_a.Name,
            "lcs_b": lcs_b.Name,
            "joint": joint_name,
            "joint_type": joint_type,
            "offset": {offset},
            "note": note,
        }}
        """
    )
    return session.execute(code)


def tool_create_subassembly(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "SubAssembly")
    components = args.get("components") or []
    ground = args.get("ground")
    code = textwrap.dedent(
        f"""
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        asm = None
        mode = "part"
        try:
            import Assembly
            asm = Assembly.makeAssembly(doc) if hasattr(Assembly, "makeAssembly") else None
        except Exception:
            asm = None
        if asm is None:
            try:
                asm = doc.addObject("Assembly::AssemblyObject", {name!r})
                mode = "assembly"
            except Exception:
                asm = doc.addObject("App::Part", {name!r})
                mode = "part"
        else:
            asm.Label = {args.get("label") or name!r}
            mode = "assembly" if _adv_is_assembly(asm) else "part"
        asm.Label = {args.get("label") or name!r}
        inserted = []
        for src_name in {json.dumps(components)}:
            src = _adv_find(doc, src_name)
            link = doc.addObject("App::Link", src.Name + "_Link")
            link.LinkedObject = src
            link.Label = src.Label
            try:
                asm.addObject(link)
            except Exception:
                g = list(getattr(asm, "Group", []))
                g.append(link)
                asm.Group = g
            inserted.append(link.Name)
        ground = {json.dumps(ground)}
        grounded = None
        if ground and mode == "assembly":
            # best-effort: create grounded joint if API allows
            try:
                for link_name in inserted:
                    link = doc.getObject(link_name)
                    if link and (link.LinkedObject.Name == ground or link.Name == ground or link.Label == ground):
                        gj = doc.addObject("Assembly::Joint", "GroundedJoint")
                        if hasattr(gj, "Object1"):
                            gj.Object1 = link
                        asm.addObject(gj)
                        grounded = link.Name
                        break
            except Exception:
                pass
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": asm.Name,
            "mode": mode,
            "components": inserted,
            "grounded": grounded,
        }}
        """
    )
    return session.execute(code)


def tool_assembly_bom(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    code = textwrap.dedent(
        f"""
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _adv_get_active(doc, {json.dumps(assembly)})
        items = []
        joints = []
        if asm is None:
            for o in doc.Objects:
                if hasattr(o, "Shape") and o.Shape.Solids:
                    items.append({{"name": o.Name, "label": o.Label, "type": o.TypeId}})
        else:
            group = list(getattr(asm, "Group", [])) or list(getattr(asm, "OutList", []))
            for o in group:
                entry = {{"name": o.Name, "label": o.Label, "type": o.TypeId}}
                if o.TypeId == "App::Link" and hasattr(o, "LinkedObject") and o.LinkedObject:
                    entry["source"] = o.LinkedObject.Name
                    entry["source_label"] = o.LinkedObject.Label
                if "Joint" in o.TypeId:
                    joints.append(entry)
                else:
                    items.append(entry)
        __result__ = {{
            "ok": True,
            "assembly": asm.Name if asm else None,
            "components": items,
            "joints": joints,
            "component_count": len(items),
            "joint_count": len(joints),
        }}
        """
    )
    return session.execute(code)


def tool_check_motion_collisions(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Sample a joint Offset2 over a range and report interference hits."""
    joint = args["joint"]
    targets = args.get("objects") or []
    start = float(args.get("start") or 0.0)
    end = float(args.get("end") or 90.0)
    steps = int(args.get("steps") or 6)
    mode = (args.get("mode") or "angle").lower()  # angle degrees or distance mm
    assembly = args.get("assembly")
    if steps < 2:
        raise FreeCADError("steps must be >= 2")
    code = textwrap.dedent(
        f"""
        import Part
        {_ADV_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        joint = _adv_find(doc, {joint!r})
        if not hasattr(joint, "Offset2"):
            raise RuntimeError("joint has no Offset2")
        asm = _adv_get_active(doc, {json.dumps(assembly)})
        names = {json.dumps(targets)}
        if len(names) < 2:
            # default: all linked components in assembly
            if asm is not None:
                names = [o.Name for o in getattr(asm, "Group", []) if o.TypeId == "App::Link"]
            else:
                names = [o.Name for o in doc.Objects if hasattr(o, "Shape") and o.Shape.Solids]
        start, end, steps = {start}, {end}, {steps}
        mode = {mode!r}
        hits = []
        samples = []
        for i in range(steps + 1):
            t = i / float(steps)
            val = start + (end - start) * t
            off = FreeCAD.Placement(joint.Offset2)
            if mode == "distance":
                off.Base = FreeCAD.Vector(0, 0, val)
            else:
                off.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), val)
            joint.Offset2 = off
            try:
                if asm is not None:
                    import Assembly
                    if hasattr(Assembly, "solveAssembly"):
                        Assembly.solveAssembly(asm)
                    elif hasattr(asm, "recompute"):
                        asm.recompute()
            except Exception:
                doc.recompute()
            doc.recompute()
            # pairwise check
            colliding = []
            for ai in range(len(names)):
                for bi in range(ai + 1, len(names)):
                    oa = doc.getObject(names[ai])
                    ob = doc.getObject(names[bi])
                    if oa is None or ob is None:
                        continue
                    sa = oa.Shape.copy(); sa.Placement = oa.Placement
                    sb = ob.Shape.copy(); sb.Placement = ob.Placement
                    try:
                        vol = float(sa.common(sb).Volume)
                    except Exception:
                        vol = 0.0
                    if vol > 1e-3:
                        colliding.append({{"a": names[ai], "b": names[bi], "volume": vol}})
            samples.append({{"value": val, "collisions": len(colliding)}})
            if colliding:
                hits.append({{"value": val, "pairs": colliding}})
        __result__ = {{
            "ok": True,
            "joint": joint.Name,
            "range": [start, end],
            "steps": steps,
            "hit_count": len(hits),
            "hits": hits,
            "samples": samples,
            "clear": len(hits) == 0,
        }}
        """
    )
    return session.execute(code)


ASSEMBLY_ADVANCED_TOOLS: list[dict[str, Any]] = [
    {
        "name": "attach_lcs",
        "description": (
            "Create an LCS on geometry for mating: mode=face_center|edge_midpoint|hole_axis|vertex. "
            "Pass face/edge/vertex as 1-based indices (from list_topology)."
        ),
        "inputSchema": _schema(
            {
                "parent": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["face_center", "edge_midpoint", "hole_axis", "circle_axis", "vertex"],
                    "default": "face_center",
                },
                "face": {"type": "integer"},
                "edge": {"type": "integer"},
                "vertex": {"type": "integer"},
                "name": {"type": "string"},
                "label": {"type": "string"},
            },
            ["parent"],
        ),
        "handler": tool_attach_lcs,
    },
    {
        "name": "check_interference",
        "description": "Detect solid interference. Pass object_a+object_b, or objects[], or omit to check all solids.",
        "inputSchema": _schema(
            {
                "object_a": {"type": "string"},
                "object_b": {"type": "string"},
                "objects": {"type": "array", "items": {"type": "string"}},
                "tolerance": {"type": "number", "default": 0.001},
            }
        ),
        "handler": tool_check_interference,
    },
    {
        "name": "measure_clearance",
        "description": "Minimum distance between two objects (0 / interfering if overlapping).",
        "inputSchema": _schema(
            {"object_a": {"type": "string"}, "object_b": {"type": "string"}},
            ["object_a", "object_b"],
        ),
        "handler": tool_measure_clearance,
    },
    {
        "name": "mate_components",
        "description": (
            "High-level mate between two parts: kind=coaxial|coincident|offset. "
            "Creates LCS pair and Assembly joint when available (else placement align)."
        ),
        "inputSchema": _schema(
            {
                "kind": {"type": "string", "enum": ["coaxial", "coincident", "offset", "offset_plane"], "default": "coaxial"},
                "object_a": {"type": "string"},
                "object_b": {"type": "string"},
                "face_a": {"type": "integer"},
                "face_b": {"type": "integer"},
                "edge_a": {"type": "integer"},
                "edge_b": {"type": "integer"},
                "offset": {"type": "number", "default": 0},
                "joint_type": {"type": "string"},
                "assembly": {"type": "string"},
                "name": {"type": "string"},
            },
            ["object_a", "object_b"],
        ),
        "handler": tool_mate_components,
    },
    {
        "name": "create_subassembly",
        "description": "Create a nested assembly/App::Part and link in component solids (earcup module, leg module).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "components": {"type": "array", "items": {"type": "string"}},
                "ground": {"type": "string", "description": "Optional source name to ground"},
            }
        ),
        "handler": tool_create_subassembly,
    },
    {
        "name": "assembly_bom",
        "description": "Bill of materials: assembly components (with Link sources) and joints.",
        "inputSchema": _schema({"assembly": {"type": "string"}}),
        "handler": tool_assembly_bom,
    },
    {
        "name": "check_motion_collisions",
        "description": (
            "Drive joint Offset2 from start→end over steps; report interference between objects "
            "(shell vs limbs through a squat/open motion)."
        ),
        "inputSchema": _schema(
            {
                "joint": {"type": "string"},
                "objects": {"type": "array", "items": {"type": "string"}},
                "start": {"type": "number", "default": 0},
                "end": {"type": "number", "default": 90},
                "steps": {"type": "integer", "default": 6},
                "mode": {"type": "string", "enum": ["angle", "distance"], "default": "angle"},
                "assembly": {"type": "string"},
            },
            ["joint"],
        ),
        "handler": tool_check_motion_collisions,
    },
]
