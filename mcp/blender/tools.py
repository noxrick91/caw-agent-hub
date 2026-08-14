"""MCP tool schemas and Blender script builders."""

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


def _unique_name(preferred: str | None, fallback: str) -> str:
    name = (preferred or fallback).strip() or fallback
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
    return safe or fallback


_HELPERS = r'''
def _b_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    return o

def _b_activate(obj):
    import bpy
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj

def _b_ensure_object_mode():
    import bpy
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
'''


def tool_blender_status(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    return session.status()


def tool_new_file(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    clear = bool(args.get("clear_default", True))
    code = textwrap.dedent(
        f"""
        import bpy
        bpy.ops.wm.read_homefile(use_empty=True)
        if {clear!r}:
            # empty scene already; ensure one camera+light optional later
            pass
        __result__ = {{"ok": True, "objects": [o.name for o in bpy.context.scene.objects]}}
        """
    )
    return session.execute(code)


def tool_open_file(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
    code = textwrap.dedent(
        f"""
        import bpy
        bpy.ops.wm.open_mainfile(filepath={path!r})
        __result__ = {{
            "ok": True,
            "path": bpy.data.filepath,
            "objects": [o.name for o in bpy.context.scene.objects],
        }}
        """
    )
    return session.execute(code)


def tool_save_file(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args.get("path")
    code = textwrap.dedent(
        f"""
        import bpy
        path = {json.dumps(path)}
        if path:
            bpy.ops.wm.save_as_mainfile(filepath=path)
        else:
            if not bpy.data.filepath:
                raise RuntimeError("no path set; pass path=")
            bpy.ops.wm.save_mainfile()
        __result__ = {{"ok": True, "path": bpy.data.filepath}}
        """
    )
    return session.execute(code)


def tool_list_objects(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        import bpy
        items = []
        for o in bpy.context.scene.objects:
            entry = {
                "name": o.name,
                "type": o.type,
                "location": [round(o.location.x, 4), round(o.location.y, 4), round(o.location.z, 4)],
                "rotation_euler_deg": [round(o.rotation_euler.x * 57.2958, 2),
                                       round(o.rotation_euler.y * 57.2958, 2),
                                       round(o.rotation_euler.z * 57.2958, 2)],
                "scale": [round(o.scale.x, 4), round(o.scale.y, 4), round(o.scale.z, 4)],
                "vertices": len(o.data.vertices) if o.type == "MESH" and o.data else None,
                "modifiers": [m.name + ":" + m.type for m in o.modifiers] if hasattr(o, "modifiers") else [],
            }
            items.append(entry)
        __result__ = {"ok": True, "objects": items, "count": len(items)}
        """
    )
    return session.execute(code)


def tool_get_object(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        o = _b_obj({name!r})
        dims = list(o.dimensions) if hasattr(o, "dimensions") else None
        __result__ = {{
            "ok": True,
            "name": o.name,
            "type": o.type,
            "location": list(o.location),
            "rotation_euler": list(o.rotation_euler),
            "scale": list(o.scale),
            "dimensions": dims,
            "modifiers": [{{"name": m.name, "type": m.type, "show_viewport": m.show_viewport}} for m in getattr(o, "modifiers", [])],
            "materials": [s.material.name if s.material else None for s in getattr(o, "material_slots", [])],
        }}
        """
    )
    return session.execute(code)


def tool_delete_object(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    names = args.get("names") or ([args["name"]] if args.get("name") else [])
    if not names:
        raise BlenderError("name or names required")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        deleted = []
        for n in {json.dumps(names)}:
            o = bpy.data.objects.get(n)
            if o is None:
                continue
            bpy.data.objects.remove(o, do_unlink=True)
            deleted.append(n)
        __result__ = {{"ok": True, "deleted": deleted}}
        """
    )
    return session.execute(code)


def tool_add_mesh(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    kind = (args.get("type") or "cube").lower()
    name = _unique_name(args.get("name"), kind.capitalize())
    size = float(args.get("size") or 2.0)
    radius = float(args.get("radius") or 1.0)
    depth = float(args.get("depth") or 2.0)
    location = args.get("location") or [0, 0, 0]
    subdivisions = int(args.get("subdivisions") or 2)
    vertices = int(args.get("vertices") or 32)
    ops = {
        "cube": f"bpy.ops.mesh.primitive_cube_add(size={size}, location=loc)",
        "uv_sphere": f"bpy.ops.mesh.primitive_uv_sphere_add(radius={radius}, segments={vertices}, ring_count={max(vertices//2, 8)}, location=loc)",
        "ico_sphere": f"bpy.ops.mesh.primitive_ico_sphere_add(radius={radius}, subdivisions={subdivisions}, location=loc)",
        "cylinder": f"bpy.ops.mesh.primitive_cylinder_add(radius={radius}, depth={depth}, vertices={vertices}, location=loc)",
        "cone": f"bpy.ops.mesh.primitive_cone_add(radius1={radius}, depth={depth}, vertices={vertices}, location=loc)",
        "torus": f"bpy.ops.mesh.primitive_torus_add(major_radius={radius}, minor_radius={radius*0.25}, location=loc)",
        "plane": f"bpy.ops.mesh.primitive_plane_add(size={size}, location=loc)",
        "monkey": f"bpy.ops.mesh.primitive_monkey_add(size={size}, location=loc)",
    }
    if kind not in ops:
        raise BlenderError(f"unknown mesh type: {kind}; choose from {sorted(ops)}")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        loc = ({float(location[0])}, {float(location[1])}, {float(location[2])})
        {ops[kind]}
        obj = bpy.context.active_object
        obj.name = {name!r}
        if obj.data:
            obj.data.name = {name!r}
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "type": {kind!r},
            "location": list(obj.location),
            "vertices": len(obj.data.vertices) if obj.type == "MESH" else 0,
        }}
        """
    )
    return session.execute(code)


def tool_set_transform(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    location = args.get("location")
    rotation_deg = args.get("rotation_deg") or args.get("rotation")
    scale = args.get("scale")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import math
        o = _b_obj({name!r})
        loc = {json.dumps(location)}
        rot = {json.dumps(rotation_deg)}
        sc = {json.dumps(scale)}
        if loc is not None:
            o.location = loc
        if rot is not None:
            o.rotation_euler = [math.radians(float(a)) for a in rot]
        if sc is not None:
            if isinstance(sc, (int, float)):
                o.scale = (float(sc), float(sc), float(sc))
            else:
                o.scale = sc
        __result__ = {{
            "ok": True,
            "name": o.name,
            "location": list(o.location),
            "rotation_euler_deg": [round(a * 57.2958, 3) for a in o.rotation_euler],
            "scale": list(o.scale),
        }}
        """
    )
    return session.execute(code)


def tool_duplicate_object(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    new_name = args.get("result_name")
    linked = bool(args.get("linked", False))
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        _b_ensure_object_mode()
        src = _b_activate(_b_obj({name!r}))
        bpy.ops.object.duplicate(linked={linked!r})
        obj = bpy.context.active_object
        if {json.dumps(new_name)}:
            obj.name = {json.dumps(new_name)}
        __result__ = {{"ok": True, "name": obj.name, "source": {name!r}}}
        """
    )
    return session.execute(code)


def tool_join_objects(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    names = args["names"]
    if len(names) < 2:
        raise BlenderError("names needs at least 2 objects")
    target = args.get("target") or names[0]
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        _b_ensure_object_mode()
        bpy.ops.object.select_all(action="DESELECT")
        objs = []
        for n in {json.dumps(names)}:
            o = _b_obj(n)
            o.select_set(True)
            objs.append(o)
        active = _b_obj({target!r})
        bpy.context.view_layer.objects.active = active
        bpy.ops.object.join()
        obj = bpy.context.active_object
        __result__ = {{"ok": True, "name": obj.name, "joined": {json.dumps(names)}}}
        """
    )
    return session.execute(code)


def tool_add_modifier(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    mod_type = (args.get("modifier") or args.get("type") or "SUBSURF").upper()
    mod_name = args.get("modifier_name") or mod_type.title()
    levels = int(args.get("levels") or 2)
    thickness = float(args.get("thickness") or 0.05)
    axis = (args.get("axis") or "X").upper()
    offset = float(args.get("offset") or 0.0)
    segments = int(args.get("segments") or 1)
    count = int(args.get("count") or 2)
    width = float(args.get("width") or 0.1)
    operand = args.get("operand")
    operation = (args.get("operation") or "DIFFERENCE").upper()
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        o = _b_obj({name!r})
        mt = {mod_type!r}
        mod = o.modifiers.new(name={mod_name!r}, type=mt)
        if mt == "SUBSURF":
            mod.levels = {levels}
            mod.render_levels = {levels}
        elif mt == "SOLIDIFY":
            mod.thickness = {thickness}
            mod.offset = {offset}
        elif mt == "MIRROR":
            mod.use_axis[0] = {axis!r} == "X"
            mod.use_axis[1] = {axis!r} == "Y"
            mod.use_axis[2] = {axis!r} == "Z"
        elif mt == "BEVEL":
            mod.width = {width}
            mod.segments = {segments}
        elif mt == "ARRAY":
            mod.count = {count}
            mod.relative_offset_displace[0] = 1.2
        elif mt == "BOOLEAN":
            op = {json.dumps(operand)}
            if not op:
                raise RuntimeError("BOOLEAN modifier needs operand= object name")
            mod.object = _b_obj(op)
            mod.operation = {operation!r}
        __result__ = {{
            "ok": True,
            "object": o.name,
            "modifier": mod.name,
            "type": mod.type,
        }}
        """
    )
    return session.execute(code)


def tool_apply_modifier(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    modifier = args.get("modifier")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        _b_ensure_object_mode()
        o = _b_activate(_b_obj({name!r}))
        mod_name = {json.dumps(modifier)}
        if mod_name is None:
            if not o.modifiers:
                raise RuntimeError("no modifiers")
            mod_name = o.modifiers[0].name
        bpy.ops.object.modifier_apply(modifier=mod_name)
        __result__ = {{
            "ok": True,
            "name": o.name,
            "applied": mod_name,
            "vertices": len(o.data.vertices) if o.type == "MESH" else None,
            "remaining_modifiers": [m.name for m in o.modifiers],
        }}
        """
    )
    return session.execute(code)


def tool_boolean(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Boolean via modifier + optional apply."""
    object_a = args["object_a"]
    object_b = args["object_b"]
    operation = (args.get("operation") or "DIFFERENCE").upper()
    apply = bool(args.get("apply", True))
    keep_operand = bool(args.get("keep_operand", False))
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        _b_ensure_object_mode()
        a = _b_obj({object_a!r})
        b = _b_obj({object_b!r})
        mod = a.modifiers.new(name="Boolean", type="BOOLEAN")
        mod.operation = {operation!r}
        mod.object = b
        if {apply!r}:
            _b_activate(a)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            if not {keep_operand!r}:
                bpy.data.objects.remove(b, do_unlink=True)
        __result__ = {{
            "ok": True,
            "name": a.name,
            "operation": {operation!r},
            "applied": {apply!r},
            "vertices": len(a.data.vertices) if a.type == "MESH" else None,
        }}
        """
    )
    return session.execute(code)


def tool_shade_smooth(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    smooth = bool(args.get("smooth", True))
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        o = _b_activate(_b_obj({name!r}))
        if {smooth!r}:
            bpy.ops.object.shade_smooth()
        else:
            bpy.ops.object.shade_flat()
        __result__ = {{"ok": True, "name": o.name, "smooth": {smooth!r}}}
        """
    )
    return session.execute(code)


def tool_set_origin(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    typ = (args.get("type") or "ORIGIN_GEOMETRY").upper()
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        o = _b_activate(_b_obj({name!r}))
        bpy.ops.object.origin_set(type={typ!r}, center="MEDIAN")
        __result__ = {{"ok": True, "name": o.name, "location": list(o.location)}}
        """
    )
    return session.execute(code)


def tool_export_model(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
    fmt = (args.get("format") or "").lower()
    if not fmt:
        fmt = path.rsplit(".", 1)[-1].lower() if "." in path else "glb"
    selected = args.get("objects")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        path = {path!r}
        fmt = {fmt!r}
        names = {json.dumps(selected)}
        if names:
            bpy.ops.object.select_all(action="DESELECT")
            for n in names:
                _b_obj(n).select_set(True)
            use_selection = True
        else:
            use_selection = False
        if fmt in ("glb", "gltf"):
            bpy.ops.export_scene.gltf(filepath=path, use_selection=use_selection, export_format="GLB" if path.lower().endswith(".glb") else "GLTF_SEPARATE")
        elif fmt == "fbx":
            bpy.ops.export_scene.fbx(filepath=path, use_selection=use_selection)
        elif fmt == "obj":
            if hasattr(bpy.ops.wm, "obj_export"):
                bpy.ops.wm.obj_export(filepath=path, export_selected_objects=use_selection)
            else:
                bpy.ops.export_scene.obj(filepath=path, use_selection=use_selection)
        elif fmt == "stl":
            if hasattr(bpy.ops.wm, "stl_export"):
                bpy.ops.wm.stl_export(filepath=path, export_selected_objects=use_selection)
            else:
                bpy.ops.export_mesh.stl(filepath=path, use_selection=use_selection)
        elif fmt == "ply":
            bpy.ops.wm.ply_export(filepath=path) if hasattr(bpy.ops.wm, "ply_export") else bpy.ops.export_mesh.ply(filepath=path, use_selection=use_selection)
        else:
            raise RuntimeError(f"unsupported format: {{fmt}}")
        __result__ = {{"ok": True, "path": path, "format": fmt, "selection": names}}
        """
    )
    return session.execute(code)


def tool_import_model(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    path = args["path"]
    code = textwrap.dedent(
        f"""
        import bpy
        path = {path!r}
        lower = path.lower()
        before = set(o.name for o in bpy.context.scene.objects)
        if lower.endswith((".glb", ".gltf")):
            bpy.ops.import_scene.gltf(filepath=path)
        elif lower.endswith(".fbx"):
            bpy.ops.import_scene.fbx(filepath=path)
        elif lower.endswith(".obj"):
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(filepath=path)
            else:
                bpy.ops.import_scene.obj(filepath=path)
        elif lower.endswith(".stl"):
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=path)
            else:
                bpy.ops.import_mesh.stl(filepath=path)
        elif lower.endswith(".ply"):
            bpy.ops.wm.ply_import(filepath=path) if hasattr(bpy.ops.wm, "ply_import") else bpy.ops.import_mesh.ply(filepath=path)
        else:
            raise RuntimeError("unsupported import type")
        after = [o.name for o in bpy.context.scene.objects if o.name not in before]
        __result__ = {{"ok": True, "path": path, "imported": after}}
        """
    )
    return session.execute(code)


def tool_render(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Backward-compatible still render — delegates to render_image with auto_setup."""
    from render_tools import tool_render_image

    merged = {
        "path": args.get("path") or "render.png",
        "engine": args.get("engine") or "EEVEE",
        "resolution": args.get("resolution") or [1280, 720],
        "auto_setup": args.get("auto_setup", True),
        "transparent": args.get("transparent", False),
        "samples": args.get("samples"),
        "target_object": args.get("target_object"),
        "format": args.get("format") or "PNG",
        "timeout": args.get("timeout"),
    }
    return tool_render_image(session, {k: v for k, v in merged.items() if v is not None})


def tool_screenshot(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """OpenGL viewport screenshot when GUI/bridge available; else falls back to render."""
    path = args.get("path") or "viewport.png"
    code = textwrap.dedent(
        f"""
        import bpy
        path = {path!r}
        try:
            bpy.ops.screen.screenshot_area(filepath=path)
            __result__ = {{"ok": True, "path": path, "mode": "viewport"}}
        except Exception:
            scene = bpy.context.scene
            scene.render.filepath = path
            bpy.ops.render.render(write_still=True)
            __result__ = {{"ok": True, "path": path, "mode": "render_fallback"}}
        """
    )
    return session.execute(code)


def tool_execute_python(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    code = args["code"]
    return session.execute(code)


from animation_tools import ANIMATION_TOOLS  # noqa: E402
from curve_tools import CURVE_TOOLS  # noqa: E402
from edit_tools import EDIT_TOOLS  # noqa: E402
from handoff_tools import HANDOFF_TOOLS  # noqa: E402
from render_tools import RENDER_TOOLS  # noqa: E402
from sculpt_tools import SCULPT_TOOLS  # noqa: E402

TOOLS: list[dict[str, Any]] = [
    {
        "name": "blender_status",
        "description": "PREFERRED first step: check Blender backend (bridge/cmd), version, open file, object count.",
        "inputSchema": _schema({}),
        "handler": tool_blender_status,
    },
    {
        "name": "new_file",
        "description": "Start a new empty Blender file (clears current scene).",
        "inputSchema": _schema({"clear_default": {"type": "boolean", "default": True}}),
        "handler": tool_new_file,
    },
    {
        "name": "open_file",
        "description": "Open a .blend file.",
        "inputSchema": _schema({"path": {"type": "string"}}, ["path"]),
        "handler": tool_open_file,
    },
    {
        "name": "save_file",
        "description": "Save the current .blend (pass path for save-as).",
        "inputSchema": _schema({"path": {"type": "string"}}),
        "handler": tool_save_file,
    },
    {
        "name": "list_objects",
        "description": "List scene objects with transforms, vertex counts, modifiers.",
        "inputSchema": _schema({}),
        "handler": tool_list_objects,
    },
    {
        "name": "get_object",
        "description": "Detailed info for one object.",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
        "handler": tool_get_object,
    },
    {
        "name": "delete_object",
        "description": "Delete object(s) by name.",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "names": {"type": "array", "items": {"type": "string"}}}
        ),
        "handler": tool_delete_object,
    },
    {
        "name": "add_mesh",
        "description": "Add a mesh primitive: cube|uv_sphere|ico_sphere|cylinder|cone|torus|plane|monkey.",
        "inputSchema": _schema(
            {
                "type": {
                    "type": "string",
                    "enum": ["cube", "uv_sphere", "ico_sphere", "cylinder", "cone", "torus", "plane", "monkey"],
                    "default": "cube",
                },
                "name": {"type": "string"},
                "size": {"type": "number"},
                "radius": {"type": "number"},
                "depth": {"type": "number"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "subdivisions": {"type": "integer"},
                "vertices": {"type": "integer"},
            }
        ),
        "handler": tool_add_mesh,
    },
    {
        "name": "set_transform",
        "description": "Set location / rotation_deg [rx,ry,rz] / scale on an object.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotation_deg": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "scale": {
                    "oneOf": [
                        {"type": "number"},
                        {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    ]
                },
            },
            ["name"],
        ),
        "handler": tool_set_transform,
    },
    {
        "name": "duplicate_object",
        "description": "Duplicate an object (optionally linked data).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "result_name": {"type": "string"},
                "linked": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        "handler": tool_duplicate_object,
    },
    {
        "name": "join_objects",
        "description": "Join multiple mesh objects into target (default first).",
        "inputSchema": _schema(
            {
                "names": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                "target": {"type": "string"},
            },
            ["names"],
        ),
        "handler": tool_join_objects,
    },
    {
        "name": "add_modifier",
        "description": (
            "Add a modifier: SUBSURF, SOLIDIFY, MIRROR, BEVEL, ARRAY, BOOLEAN. "
            "For BOOLEAN pass operand= and operation=UNION|DIFFERENCE|INTERSECT."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "modifier": {
                    "type": "string",
                    "enum": ["SUBSURF", "SOLIDIFY", "MIRROR", "BEVEL", "ARRAY", "BOOLEAN"],
                },
                "type": {"type": "string"},
                "modifier_name": {"type": "string"},
                "levels": {"type": "integer", "default": 2},
                "thickness": {"type": "number", "default": 0.05},
                "offset": {"type": "number", "default": 0},
                "axis": {"type": "string", "enum": ["X", "Y", "Z"], "default": "X"},
                "width": {"type": "number", "default": 0.1},
                "segments": {"type": "integer", "default": 1},
                "count": {"type": "integer", "default": 2},
                "operand": {"type": "string"},
                "operation": {"type": "string", "enum": ["UNION", "DIFFERENCE", "INTERSECT"]},
            },
            ["name"],
        ),
        "handler": tool_add_modifier,
    },
    {
        "name": "apply_modifier",
        "description": "Apply a modifier by name (default: first modifier).",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "modifier": {"type": "string"}},
            ["name"],
        ),
        "handler": tool_apply_modifier,
    },
    {
        "name": "boolean",
        "description": "Boolean DIFFERENCE|UNION|INTERSECT of object_a with object_b (applies by default).",
        "inputSchema": _schema(
            {
                "object_a": {"type": "string"},
                "object_b": {"type": "string"},
                "operation": {
                    "type": "string",
                    "enum": ["DIFFERENCE", "UNION", "INTERSECT"],
                    "default": "DIFFERENCE",
                },
                "apply": {"type": "boolean", "default": True},
                "keep_operand": {"type": "boolean", "default": False},
            },
            ["object_a", "object_b"],
        ),
        "handler": tool_boolean,
    },
    {
        "name": "shade_smooth",
        "description": "Shade smooth or flat.",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "smooth": {"type": "boolean", "default": True}},
            ["name"],
        ),
        "handler": tool_shade_smooth,
    },
    {
        "name": "set_origin",
        "description": "Set object origin (ORIGIN_GEOMETRY, ORIGIN_CURSOR, ORIGIN_CENTER_OF_MASS, …).",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "type": {"type": "string", "default": "ORIGIN_GEOMETRY"}},
            ["name"],
        ),
        "handler": tool_set_origin,
    },
    {
        "name": "export_model",
        "description": "Export to glb/gltf/fbx/obj/stl/ply. Optional objects=[] selection.",
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "format": {"type": "string"},
                "objects": {"type": "array", "items": {"type": "string"}},
            },
            ["path"],
        ),
        "handler": tool_export_model,
    },
    {
        "name": "import_model",
        "description": "Import glb/gltf/fbx/obj/stl/ply into the scene.",
        "inputSchema": _schema({"path": {"type": "string"}}, ["path"]),
        "handler": tool_import_model,
    },
    {
        "name": "render",
        "description": (
            "Render a still image (alias of render_image). auto_setup camera+lights by default. "
            "Prefer render_image for new workflows."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string", "default": "render.png"},
                "engine": {"type": "string", "default": "EEVEE"},
                "resolution": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                "samples": {"type": "integer"},
                "transparent": {"type": "boolean", "default": False},
                "auto_setup": {"type": "boolean", "default": True},
                "target_object": {"type": "string"},
                "format": {"type": "string", "default": "PNG"},
                "timeout": {"type": "number"},
            }
        ),
        "handler": tool_render,
    },
    {
        "name": "screenshot",
        "description": "Capture viewport (GUI/bridge) or fall back to render.",
        "inputSchema": _schema({"path": {"type": "string", "default": "viewport.png"}}),
        "handler": tool_screenshot,
    },
    {
        "name": "execute_python",
        "description": (
            "Execute arbitrary Blender Python (bpy available). Set __result__ for structured return. "
            "Use for sculpt/edit-mode ops not covered by structured tools."
        ),
        "inputSchema": _schema({"code": {"type": "string"}}, ["code"]),
        "handler": tool_execute_python,
    },
]

TOOLS.extend(ANIMATION_TOOLS)
TOOLS.extend(RENDER_TOOLS)
TOOLS.extend(EDIT_TOOLS)
TOOLS.extend(CURVE_TOOLS)
TOOLS.extend(SCULPT_TOOLS)
TOOLS.extend(HANDOFF_TOOLS)


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in TOOLS
    ]


HANDLERS: dict[str, ToolHandler] = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(session: BlenderSession, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in HANDLERS:
        raise BlenderError(f"unknown tool: {name}")
    return HANDLERS[name](session, arguments or {})
