"""Edit-mode mesh tools for Blender MCP."""

from __future__ import annotations

import json
import textwrap
from typing import Any, Callable

from backend import BlenderError, BlenderSession

ToolHandler = Callable[[BlenderSession, dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


_EDIT_HELPERS = r'''
def _e_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    if o.type != "MESH":
        raise RuntimeError(f"{name} is not a MESH")
    return o

def _e_activate(obj):
    import bpy
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj

def _e_enter(obj, mode="EDIT"):
    import bpy
    _e_activate(obj)
    bpy.ops.object.mode_set(mode=mode)
    return obj

def _e_leave():
    import bpy
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

def _e_select(obj, domain="FACE", indices=None, all=False):
    """domain: VERT|EDGE|FACE. indices 0-based. all=True selects everything."""
    import bmesh
    import bpy
    _e_enter(obj, "EDIT")
    mesh = obj.data
    bm = bmesh.from_edit_mesh(mesh)
    bm.faces.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    bm.verts.ensure_lookup_table()
    for v in bm.verts:
        v.select = False
    for e in bm.edges:
        e.select = False
    for f in bm.faces:
        f.select = False
    domain = (domain or "FACE").upper()
    if all or not indices:
        if domain == "VERT":
            for v in bm.verts:
                v.select = True
        elif domain == "EDGE":
            for e in bm.edges:
                e.select = True
        else:
            for f in bm.faces:
                f.select = True
    else:
        idxs = [int(i) for i in indices]
        if domain == "VERT":
            for i in idxs:
                if 0 <= i < len(bm.verts):
                    bm.verts[i].select = True
        elif domain == "EDGE":
            for i in idxs:
                if 0 <= i < len(bm.edges):
                    bm.edges[i].select = True
        else:
            for i in idxs:
                if 0 <= i < len(bm.faces):
                    bm.faces[i].select = True
    bm.select_flush_mode()
    bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    # Set select mode
    if domain == "VERT":
        bpy.ops.mesh.select_mode(type="VERT")
    elif domain == "EDGE":
        bpy.ops.mesh.select_mode(type="EDGE")
    else:
        bpy.ops.mesh.select_mode(type="FACE")
    return bm

def _e_counts(obj):
    m = obj.data
    return {"vertices": len(m.vertices), "edges": len(m.edges), "faces": len(m.polygons)}
'''


def tool_mesh_info(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        obj = _e_obj({name!r})
        m = obj.data
        faces = []
        for i, p in enumerate(m.polygons[:40]):
            faces.append({{
                "index": i,
                "verts": list(p.vertices),
                "area": float(p.area),
                "normal": [round(p.normal.x, 4), round(p.normal.y, 4), round(p.normal.z, 4)],
            }})
        __result__ = {{
            "ok": True,
            "name": obj.name,
            **_e_counts(obj),
            "faces_sample": faces,
        }}
        """
    )
    return session.execute(code)


def tool_edit_extrude(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    amount = float(args.get("amount") or 0.1)
    domain = (args.get("domain") or "FACE").upper()
    indices = args.get("indices")
    select_all = bool(args.get("select_all", indices is None))
    direction = args.get("direction")  # optional [x,y,z]; default along normal via transform
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        from mathutils import Vector
        obj = _e_obj({name!r})
        _e_select(obj, domain={domain!r}, indices={json.dumps(indices)}, all={select_all!r})
        bpy.ops.mesh.extrude_region_move(
            TRANSFORM_OT_translate={{
                "value": (0, 0, 0),
                "orient_type": "NORMAL",
            }}
        )
        # After extrude, move selection along normal or direction
        direction = {json.dumps(direction)}
        amount = {amount}
        if direction is not None:
            vec = Vector((float(direction[0]), float(direction[1]), float(direction[2])))
            if vec.length > 1e-9:
                vec.normalize()
                vec *= amount
            bpy.ops.transform.translate(value=vec, orient_type="GLOBAL")
        else:
            bpy.ops.transform.translate(
                value=(0, 0, amount),
                orient_type="NORMAL",
                constraint_axis=(False, False, True),
            )
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "amount": amount, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_inset(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    thickness = float(args.get("thickness") or 0.1)
    depth = float(args.get("depth") or 0.0)
    indices = args.get("indices")
    select_all = bool(args.get("select_all", indices is None))
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain="FACE", indices={json.dumps(indices)}, all={select_all!r})
        bpy.ops.mesh.inset(thickness={thickness}, depth={depth})
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "thickness": {thickness}, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_bevel(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    offset = float(args.get("offset") or args.get("amount") or 0.05)
    segments = int(args.get("segments") or 2)
    domain = (args.get("domain") or "EDGE").upper()
    indices = args.get("indices")
    select_all = bool(args.get("select_all", indices is None))
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain={domain!r}, indices={json.dumps(indices)}, all={select_all!r})
        bpy.ops.mesh.bevel(offset={offset}, segments={segments}, affect='EDGES')
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "offset": {offset}, "segments": {segments}, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_subdivide(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    cuts = int(args.get("cuts") or 1)
    smoothness = float(args.get("smoothness") or 0.0)
    indices = args.get("indices")
    domain = (args.get("domain") or "FACE").upper()
    select_all = bool(args.get("select_all", indices is None))
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain={domain!r}, indices={json.dumps(indices)}, all={select_all!r})
        bpy.ops.mesh.subdivide(number_cuts={cuts}, smoothness={smoothness})
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "cuts": {cuts}, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_loop_cut(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Loop cut via edge ring — pass edge index as guide; falls back to subdivide if ops fail."""
    name = args["name"]
    cuts = int(args.get("cuts") or 1)
    edge = int(args.get("edge") or 0)
    smoothness = float(args.get("smoothness") or 0.0)
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain="EDGE", indices=[{edge}], all=False)
        try:
            bpy.ops.mesh.loopcut_slide(
                MESH_OT_loopcut={{
                    "number_cuts": {cuts},
                    "smoothness": {smoothness},
                    "falloff": "INVERSE_SQUARE",
                    "object_index": 0,
                    "edge_index": {edge},
                }},
                TRANSFORM_OT_edge_slide={{"value": 0.0}},
            )
            note = "loopcut"
        except Exception as e:
            # Fallback: subdivide selected edge ring-ish by subdividing all edges
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.subdivide(number_cuts={cuts}, smoothness={smoothness})
            note = f"subdivide_fallback: {{e}}"
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "cuts": {cuts}, "note": note, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_bridge(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    edge_indices = args.get("edges") or args.get("indices")
    if not edge_indices or len(edge_indices) < 2:
        raise BlenderError("bridge needs edges=[...] with at least 2 edge indices")
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain="EDGE", indices={json.dumps(edge_indices)}, all=False)
        bpy.ops.mesh.bridge_edge_loops()
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_edit_merge(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    distance = float(args.get("distance") or 0.001)
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_enter(obj, "EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        before = len(obj.data.vertices)
        bpy.ops.mesh.remove_doubles(threshold={distance})
        _e_leave()
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "distance": {distance},
            "vertices_before": before,
            **_e_counts(obj),
        }}
        """
    )
    return session.execute(code)


def tool_edit_delete(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    domain = (args.get("domain") or "FACE").upper()
    indices = args.get("indices")
    if not indices:
        raise BlenderError("indices required for edit_delete")
    typ = {"VERT": "VERT", "EDGE": "EDGE", "FACE": "FACE"}.get(domain, "FACE")
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_select(obj, domain={domain!r}, indices={json.dumps(indices)}, all=False)
        bpy.ops.mesh.delete(type={typ!r})
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "deleted": {json.dumps(indices)}, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


def tool_mesh_decimate(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    ratio = float(args.get("ratio") or 0.5)
    if not (0.0 < ratio <= 1.0):
        raise BlenderError("ratio must be in (0, 1]")
    apply = bool(args.get("apply", True))
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_activate(_e_obj({name!r}))
        before = _e_counts(obj)
        mod = obj.modifiers.new(name="Decimate", type="DECIMATE")
        mod.ratio = {ratio}
        if {apply!r}:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "ratio": {ratio},
            "applied": {apply!r},
            "before": before,
            "after": _e_counts(obj),
        }}
        """
    )
    return session.execute(code)


def tool_mesh_symmetrize(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    direction = (args.get("direction") or "POSITIVE_X").upper()
    code = textwrap.dedent(
        f"""
        {_EDIT_HELPERS}
        import bpy
        obj = _e_obj({name!r})
        _e_enter(obj, "EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        bpy.ops.mesh.symmetrize(direction={direction!r})
        _e_leave()
        __result__ = {{"ok": True, "name": obj.name, "direction": {direction!r}, **_e_counts(obj)}}
        """
    )
    return session.execute(code)


EDIT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "mesh_info",
        "description": "Mesh topology summary + sample face indices/normals (use before edit_* with indices).",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
        "handler": tool_mesh_info,
    },
    {
        "name": "edit_extrude",
        "description": "Edit-mode extrude faces/edges/verts. amount along normal, or direction=[x,y,z]. indices 0-based or select_all.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "amount": {"type": "number", "default": 0.1},
                "direction": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "domain": {"type": "string", "enum": ["FACE", "EDGE", "VERT"], "default": "FACE"},
                "indices": {"type": "array", "items": {"type": "integer"}},
                "select_all": {"type": "boolean"},
            },
            ["name"],
        ),
        "handler": tool_edit_extrude,
    },
    {
        "name": "edit_inset",
        "description": "Inset selected faces (thickness/depth). Default all faces if indices omitted.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "thickness": {"type": "number", "default": 0.1},
                "depth": {"type": "number", "default": 0},
                "indices": {"type": "array", "items": {"type": "integer"}},
                "select_all": {"type": "boolean"},
            },
            ["name"],
        ),
        "handler": tool_edit_inset,
    },
    {
        "name": "edit_bevel",
        "description": "Bevel selected edges/verts in edit mode.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "offset": {"type": "number", "default": 0.05},
                "amount": {"type": "number"},
                "segments": {"type": "integer", "default": 2},
                "domain": {"type": "string", "enum": ["EDGE", "VERT"], "default": "EDGE"},
                "indices": {"type": "array", "items": {"type": "integer"}},
                "select_all": {"type": "boolean"},
            },
            ["name"],
        ),
        "handler": tool_edit_bevel,
    },
    {
        "name": "edit_subdivide",
        "description": "Subdivide selected mesh elements (cuts, optional smoothness).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "cuts": {"type": "integer", "default": 1},
                "smoothness": {"type": "number", "default": 0},
                "domain": {"type": "string", "enum": ["FACE", "EDGE", "VERT"], "default": "FACE"},
                "indices": {"type": "array", "items": {"type": "integer"}},
                "select_all": {"type": "boolean"},
            },
            ["name"],
        ),
        "handler": tool_edit_subdivide,
    },
    {
        "name": "edit_loop_cut",
        "description": "Loop cut guided by edge index (falls back to subdivide if operator context fails).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "cuts": {"type": "integer", "default": 1},
                "edge": {"type": "integer", "default": 0},
                "smoothness": {"type": "number", "default": 0},
            },
            ["name"],
        ),
        "handler": tool_edit_loop_cut,
    },
    {
        "name": "edit_bridge",
        "description": "Bridge edge loops — pass edges=[index,...] spanning two loops.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "edges": {"type": "array", "items": {"type": "integer"}},
                "indices": {"type": "array", "items": {"type": "integer"}},
            },
            ["name"],
        ),
        "handler": tool_edit_bridge,
    },
    {
        "name": "edit_merge",
        "description": "Merge nearby vertices by distance (remove doubles).",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "distance": {"type": "number", "default": 0.001}},
            ["name"],
        ),
        "handler": tool_edit_merge,
    },
    {
        "name": "edit_delete",
        "description": "Delete faces/edges/verts by 0-based indices.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "domain": {"type": "string", "enum": ["FACE", "EDGE", "VERT"], "default": "FACE"},
                "indices": {"type": "array", "items": {"type": "integer"}},
            },
            ["name", "indices"],
        ),
        "handler": tool_edit_delete,
    },
    {
        "name": "mesh_decimate",
        "description": "Decimate mesh (ratio 0-1). apply=true bakes the modifier.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "ratio": {"type": "number", "default": 0.5},
                "apply": {"type": "boolean", "default": True},
            },
            ["name"],
        ),
        "handler": tool_mesh_decimate,
    },
    {
        "name": "mesh_symmetrize",
        "description": "Symmetrize mesh across an axis (POSITIVE_X, NEGATIVE_X, POSITIVE_Y, …).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "direction": {
                    "type": "string",
                    "enum": [
                        "POSITIVE_X",
                        "NEGATIVE_X",
                        "POSITIVE_Y",
                        "NEGATIVE_Y",
                        "POSITIVE_Z",
                        "NEGATIVE_Z",
                    ],
                    "default": "POSITIVE_X",
                },
            },
            ["name"],
        ),
        "handler": tool_mesh_symmetrize,
    },
]
