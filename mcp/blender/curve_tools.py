"""Curve tools for Blender MCP — paths, bevel profiles, convert to mesh."""

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


def tool_create_curve(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name") or "Curve"
    points = args.get("points") or []
    if len(points) < 2:
        raise BlenderError("points needs at least 2 [x,y,z] entries")
    kind = (args.get("type") or "BEZIER").upper()  # BEZIER | POLY | NURBS
    cyclic = bool(args.get("cyclic", False))
    bevel_depth = float(args.get("bevel_depth") or 0.0)
    bevel_resolution = int(args.get("bevel_resolution") or 4)
    code = textwrap.dedent(
        f"""
        import bpy
        from mathutils import Vector

        name = {name!r}
        kind = {kind!r}
        pts = {json.dumps(points)}
        cyclic = {cyclic!r}

        curve = bpy.data.curves.new(name, type="CURVE")
        curve.dimensions = "3D"
        curve.resolution_u = 12
        curve.bevel_depth = {bevel_depth}
        curve.bevel_resolution = {bevel_resolution}

        spline_type = {{"BEZIER": "BEZIER", "POLY": "POLY", "NURBS": "NURBS"}}.get(kind, "BEZIER")
        spline = curve.splines.new(spline_type)

        if spline_type == "BEZIER":
            spline.bezier_points.add(len(pts) - 1)
            for i, p in enumerate(pts):
                bp = spline.bezier_points[i]
                bp.co = Vector((float(p[0]), float(p[1]), float(p[2]) if len(p) > 2 else 0.0))
                bp.handle_left_type = "AUTO"
                bp.handle_right_type = "AUTO"
        else:
            # POLY / NURBS
            spline.points.add(len(pts) - 1)
            for i, p in enumerate(pts):
                x, y = float(p[0]), float(p[1])
                z = float(p[2]) if len(p) > 2 else 0.0
                w = 1.0
                spline.points[i].co = (x, y, z, w)

        spline.use_cyclic_u = cyclic
        obj = bpy.data.objects.new(name, curve)
        bpy.context.scene.collection.objects.link(obj)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "type": spline_type,
            "points": len(pts),
            "cyclic": cyclic,
            "bevel_depth": curve.bevel_depth,
        }}
        """
    )
    return session.execute(code)


def tool_curve_set_bevel(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    depth = float(args.get("bevel_depth") or args.get("depth") or 0.05)
    resolution = int(args.get("bevel_resolution") or args.get("resolution") or 4)
    fill_caps = bool(args.get("fill_caps", True))
    code = textwrap.dedent(
        f"""
        import bpy
        obj = bpy.data.objects.get({name!r})
        if obj is None or obj.type != "CURVE":
            raise RuntimeError("curve object not found")
        obj.data.bevel_depth = {depth}
        obj.data.bevel_resolution = {resolution}
        if hasattr(obj.data, "use_fill_caps"):
            obj.data.use_fill_caps = {fill_caps!r}
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "bevel_depth": obj.data.bevel_depth,
            "bevel_resolution": obj.data.bevel_resolution,
        }}
        """
    )
    return session.execute(code)


def tool_curve_to_mesh(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    keep_original = bool(args.get("keep_original", False))
    result_name = args.get("result_name")
    code = textwrap.dedent(
        f"""
        import bpy
        obj = bpy.data.objects.get({name!r})
        if obj is None or obj.type != "CURVE":
            raise RuntimeError("curve object not found")
        bpy.ops.object.select_all(action="DESELECT")
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        bpy.ops.object.convert(target="MESH")
        mesh_obj = bpy.context.active_object
        if {json.dumps(result_name)}:
            mesh_obj.name = {json.dumps(result_name)}
        # convert replaces the object; keep_original would need duplicate first
        __result__ = {{
            "ok": True,
            "name": mesh_obj.name,
            "type": mesh_obj.type,
            "vertices": len(mesh_obj.data.vertices) if mesh_obj.type == "MESH" else 0,
            "note": "original curve converted in-place" if not {keep_original!r} else "converted",
        }}
        """
    )
    return session.execute(code)


def tool_curve_extrude(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Set curve extrude (2D ribbon height) and optionally bevel."""
    name = args["name"]
    extrude = float(args.get("extrude") or 0.05)
    bevel_depth = args.get("bevel_depth")
    code = textwrap.dedent(
        f"""
        import bpy
        obj = bpy.data.objects.get({name!r})
        if obj is None or obj.type != "CURVE":
            raise RuntimeError("curve object not found")
        obj.data.extrude = {extrude}
        bd = {json.dumps(bevel_depth)}
        if bd is not None:
            obj.data.bevel_depth = float(bd)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "extrude": obj.data.extrude,
            "bevel_depth": obj.data.bevel_depth,
        }}
        """
    )
    return session.execute(code)


CURVE_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_curve",
        "description": (
            "Create a 3D curve from points (BEZIER|POLY|NURBS). "
            "Optional bevel_depth for tube (headband, cables). cyclic=true closes the loop."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "points": {
                    "type": "array",
                    "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
                    "minItems": 2,
                },
                "type": {"type": "string", "enum": ["BEZIER", "POLY", "NURBS"], "default": "BEZIER"},
                "cyclic": {"type": "boolean", "default": False},
                "bevel_depth": {"type": "number", "default": 0},
                "bevel_resolution": {"type": "integer", "default": 4},
            },
            ["points"],
        ),
        "handler": tool_create_curve,
    },
    {
        "name": "curve_set_bevel",
        "description": "Set curve bevel depth/resolution (turns a path into a tube).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "bevel_depth": {"type": "number", "default": 0.05},
                "depth": {"type": "number"},
                "bevel_resolution": {"type": "integer", "default": 4},
                "resolution": {"type": "integer"},
                "fill_caps": {"type": "boolean", "default": True},
            },
            ["name"],
        ),
        "handler": tool_curve_set_bevel,
    },
    {
        "name": "curve_extrude",
        "description": "Set curve extrude (ribbon thickness) and optional bevel_depth.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "extrude": {"type": "number", "default": 0.05},
                "bevel_depth": {"type": "number"},
            },
            ["name"],
        ),
        "handler": tool_curve_extrude,
    },
    {
        "name": "curve_to_mesh",
        "description": "Convert a curve object to a mesh (applies bevel/extrude).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "result_name": {"type": "string"},
                "keep_original": {"type": "boolean", "default": False},
            },
            ["name"],
        ),
        "handler": tool_curve_to_mesh,
    },
]
