"""Sculpt / organic shape helpers for Blender MCP (non-interactive)."""

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


_SCULPT_HELPERS = r'''
def _s_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    if o.type != "MESH":
        raise RuntimeError(f"{name} is not a MESH")
    return o

def _s_activate(obj):
    import bpy
    if bpy.context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    return obj
'''


def tool_sculpt_remesh(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    voxel_size = float(args.get("voxel_size") or 0.05)
    adaptivity = float(args.get("adaptivity") or 0.0)
    code = textwrap.dedent(
        f"""
        {_SCULPT_HELPERS}
        import bpy
        obj = _s_activate(_s_obj({name!r}))
        before = len(obj.data.vertices)
        # Prefer modifier remesh then apply for broader version support
        mod = obj.modifiers.new(name="Remesh", type="REMESH")
        mod.mode = "VOXEL"
        mod.voxel_size = {voxel_size}
        if hasattr(mod, "adaptivity"):
            mod.adaptivity = {adaptivity}
        bpy.ops.object.modifier_apply(modifier=mod.name)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "voxel_size": {voxel_size},
            "vertices_before": before,
            "vertices": len(obj.data.vertices),
        }}
        """
    )
    return session.execute(code)


def tool_sculpt_smooth(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    factor = float(args.get("factor") or 0.5)
    repeat = int(args.get("repeat") or 5)
    code = textwrap.dedent(
        f"""
        {_SCULPT_HELPERS}
        import bpy
        import bmesh
        obj = _s_activate(_s_obj({name!r}))
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        for _ in range({repeat}):
            bpy.ops.mesh.vertices_smooth(factor={factor})
        bpy.ops.object.mode_set(mode="OBJECT")
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "factor": {factor},
            "repeat": {repeat},
            "vertices": len(obj.data.vertices),
        }}
        """
    )
    return session.execute(code)


def tool_sculpt_inflate(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Move vertices along normals (inflate/deflate) — sculpt-like volume push."""
    name = args["name"]
    amount = float(args.get("amount") or 0.05)
    code = textwrap.dedent(
        f"""
        {_SCULPT_HELPERS}
        import bmesh
        import bpy
        obj = _s_activate(_s_obj({name!r}))
        mesh = obj.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        bm.normal_update()
        amount = {amount}
        for v in bm.verts:
            v.co += v.normal * amount
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        __result__ = {{"ok": True, "name": obj.name, "amount": amount, "vertices": len(mesh.vertices)}}
        """
    )
    return session.execute(code)


def tool_sculpt_displace(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Apply a displace modifier with CLOUDS/noise for organic variation."""
    name = args["name"]
    strength = float(args.get("strength") or 0.05)
    midlevel = float(args.get("mid_level") or 0.5)
    apply = bool(args.get("apply", True))
    noise_scale = float(args.get("noise_scale") or 1.0)
    code = textwrap.dedent(
        f"""
        {_SCULPT_HELPERS}
        import bpy
        obj = _s_activate(_s_obj({name!r}))
        tex = bpy.data.textures.new(f"{{obj.name}}_Clouds", type="CLOUDS")
        if hasattr(tex, "noise_scale"):
            tex.noise_scale = {noise_scale}
        mod = obj.modifiers.new(name="Displace", type="DISPLACE")
        mod.texture = tex
        mod.strength = {strength}
        mod.mid_level = {midlevel}
        if {apply!r}:
            bpy.ops.object.modifier_apply(modifier=mod.name)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "strength": {strength},
            "applied": {apply!r},
            "vertices": len(obj.data.vertices),
        }}
        """
    )
    return session.execute(code)


def tool_sculpt_snake_hook_approx(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Pull vertices near a point toward a target (simple grab/snake-hook approximation)."""
    name = args["name"]
    center = args.get("center") or [0, 0, 0]
    target = args.get("target") or [0, 0, 0.2]
    radius = float(args.get("radius") or 0.5)
    strength = float(args.get("strength") or 1.0)
    code = textwrap.dedent(
        f"""
        {_SCULPT_HELPERS}
        import bpy
        from mathutils import Vector
        obj = _s_activate(_s_obj({name!r}))
        center = Vector({json.dumps(center)})
        target = Vector({json.dumps(target)})
        delta = target - center
        radius = {radius}
        strength = {strength}
        mw = obj.matrix_world
        imw = mw.inverted()
        mesh = obj.data
        for v in mesh.vertices:
            world = mw @ v.co
            d = (world - center).length
            if d > radius or radius <= 0:
                continue
            w = (1.0 - d / radius) ** 2
            world = world + delta * (w * strength)
            v.co = imw @ world
        mesh.update()
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "radius": radius,
            "strength": strength,
            "vertices": len(mesh.vertices),
        }}
        """
    )
    return session.execute(code)


SCULPT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "sculpt_remesh",
        "description": "Voxel remesh for even topology before organic shaping (voxel_size in Blender units).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "voxel_size": {"type": "number", "default": 0.05},
                "adaptivity": {"type": "number", "default": 0},
            },
            ["name"],
        ),
        "handler": tool_sculpt_remesh,
    },
    {
        "name": "sculpt_smooth",
        "description": "Smooth all vertices (factor + repeat). Good after remesh/inflate.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "factor": {"type": "number", "default": 0.5},
                "repeat": {"type": "integer", "default": 5},
            },
            ["name"],
        ),
        "handler": tool_sculpt_smooth,
    },
    {
        "name": "sculpt_inflate",
        "description": "Inflate/deflate along normals (positive expands, negative shrinks).",
        "inputSchema": _schema(
            {"name": {"type": "string"}, "amount": {"type": "number", "default": 0.05}},
            ["name"],
        ),
        "handler": tool_sculpt_inflate,
    },
    {
        "name": "sculpt_displace",
        "description": "Clouds noise displace for organic surface variation.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "strength": {"type": "number", "default": 0.05},
                "mid_level": {"type": "number", "default": 0.5},
                "noise_scale": {"type": "number", "default": 1.0},
                "apply": {"type": "boolean", "default": True},
            },
            ["name"],
        ),
        "handler": tool_sculpt_displace,
    },
    {
        "name": "sculpt_grab",
        "description": (
            "Grab/snake-hook approximation: pull vertices near center toward target within radius."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "center": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "radius": {"type": "number", "default": 0.5},
                "strength": {"type": "number", "default": 1.0},
            },
            ["name"],
        ),
        "handler": tool_sculpt_snake_hook_approx,
    },
]
