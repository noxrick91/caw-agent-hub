"""CAD ↔ Blender handoff helpers (units, scaled import/export)."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
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


_HANDOFF_HELPERS = r'''
def _h_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    return o

def _h_unit_mode(scene):
    # Return "mm" if unit_scale ~= 0.001, else "m"
    scale = float(getattr(scene.unit_settings, "scale_length", 1.0) or 1.0)
    if abs(scale - 0.001) < 1e-6:
        return "mm"
    if abs(scale - 1.0) < 1e-6:
        return "m"
    return f"custom:{scale}"

def _h_set_mm(scene):
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 0.001
    scene.unit_settings.length_unit = "MILLIMETERS"

def _h_set_m(scene):
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    scene.unit_settings.length_unit = "METERS"
'''


def tool_set_units(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Set Blender scene units. Prefer mode=mm for FreeCAD handoff (1 BU = 1 mm)."""
    mode = (args.get("mode") or "mm").lower()
    if mode not in {"mm", "m", "meters", "millimeters"}:
        raise BlenderError("mode must be mm or m")
    code = textwrap.dedent(
        f"""
        {_HANDOFF_HELPERS}
        import bpy
        scene = bpy.context.scene
        mode = {mode!r}
        if mode in ("mm", "millimeters"):
            _h_set_mm(scene)
        else:
            _h_set_m(scene)
        __result__ = {{
            "ok": True,
            "mode": _h_unit_mode(scene),
            "scale_length": float(scene.unit_settings.scale_length),
            "length_unit": scene.unit_settings.length_unit,
            "note": "With mode=mm, model in millimeters; STL to FreeCAD is 1:1",
        }}
        """
    )
    return session.execute(code)


def tool_export_for_freecad(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Export mesh for FreeCAD assembly (STL/OBJ), applying mm scale when scene is meters."""
    path = args["path"]
    fmt = (args.get("format") or Path(path).suffix.lstrip(".") or "stl").lower()
    if fmt not in {"stl", "obj"}:
        raise BlenderError("export_for_freecad supports stl|obj (mesh). Use STEP from FreeCAD side.")
    objects = args.get("objects")
    # auto: if scene meters → scale 1000; if mm → 1
    scale = args.get("scale")
    apply_modifiers = bool(args.get("apply_modifiers", True))
    try:
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    code = textwrap.dedent(
        f"""
        {_HANDOFF_HELPERS}
        import bpy
        from pathlib import Path

        scene = bpy.context.scene
        path = {path!r}
        fmt = {fmt!r}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        mode = _h_unit_mode(scene)
        scale = {json.dumps(scale)}
        if scale is None:
            scale = 1000.0 if mode == "m" else 1.0
        else:
            scale = float(scale)

        names = {json.dumps(objects)}
        bpy.ops.object.select_all(action="DESELECT")
        if names:
            for n in names:
                _h_obj(n).select_set(True)
            use_selection = True
        else:
            for o in scene.objects:
                if o.type == "MESH":
                    o.select_set(True)
            use_selection = True

        # Blender STL exporter global_scale (4.x) / scale
        if fmt == "stl":
            kwargs = {{"filepath": path}}
            if hasattr(bpy.ops.wm, "stl_export"):
                kwargs.update({{
                    "export_selected_objects": use_selection,
                    "global_scale": scale,
                    "apply_modifiers": {apply_modifiers!r},
                }})
                try:
                    bpy.ops.wm.stl_export(**kwargs)
                except TypeError:
                    kwargs.pop("apply_modifiers", None)
                    bpy.ops.wm.stl_export(**kwargs)
            else:
                bpy.ops.export_mesh.stl(
                    filepath=path,
                    use_selection=use_selection,
                    global_scale=scale,
                )
        else:
            if hasattr(bpy.ops.wm, "obj_export"):
                try:
                    bpy.ops.wm.obj_export(
                        filepath=path,
                        export_selected_objects=use_selection,
                        global_scale=scale,
                        apply_modifiers={apply_modifiers!r},
                    )
                except TypeError:
                    bpy.ops.wm.obj_export(filepath=path, export_selected_objects=use_selection)
            else:
                bpy.ops.export_scene.obj(filepath=path, use_selection=use_selection, global_scale=scale)

        __result__ = {{
            "ok": True,
            "path": path,
            "format": fmt,
            "scene_units": mode,
            "export_scale": scale,
            "objects": names,
            "handoff": "freecad",
            "note": "Import in FreeCAD with import_from_blender (scale=1 if export_scale already applied)",
        }}
        """
    )
    return session.execute(code)


def tool_import_from_freecad(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Import FreeCAD mesh (STL/OBJ). Sets mm units by default; scales if scene stays in meters."""
    path = args["path"]
    set_mm = bool(args.get("set_mm_units", True))
    scale = args.get("scale")  # None = auto
    code = textwrap.dedent(
        f"""
        {_HANDOFF_HELPERS}
        import bpy
        from mathutils import Vector

        scene = bpy.context.scene
        path = {path!r}
        if {set_mm!r}:
            _h_set_mm(scene)

        before = set(o.name for o in scene.objects)
        lower = path.lower()
        if lower.endswith(".stl"):
            if hasattr(bpy.ops.wm, "stl_import"):
                bpy.ops.wm.stl_import(filepath=path)
            else:
                bpy.ops.import_mesh.stl(filepath=path)
        elif lower.endswith(".obj"):
            if hasattr(bpy.ops.wm, "obj_import"):
                bpy.ops.wm.obj_import(filepath=path)
            else:
                bpy.ops.import_scene.obj(filepath=path)
        elif lower.endswith((".glb", ".gltf")):
            bpy.ops.import_scene.gltf(filepath=path)
        else:
            raise RuntimeError("import_from_freecad supports stl|obj|glb/gltf")

        imported = [o for o in scene.objects if o.name not in before]
        mode = _h_unit_mode(scene)
        scale = {json.dumps(scale)}
        if scale is None:
            # FreeCAD files are mm. If Blender is meters, shrink 1000x; if mm units, leave 1:1.
            scale = 0.001 if mode == "m" else 1.0
        else:
            scale = float(scale)

        if abs(scale - 1.0) > 1e-12:
            for o in imported:
                o.scale = Vector((o.scale.x * scale, o.scale.y * scale, o.scale.z * scale))
                bpy.context.view_layer.objects.active = o
                o.select_set(True)
                try:
                    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
                except Exception:
                    pass

        __result__ = {{
            "ok": True,
            "path": path,
            "imported": [o.name for o in imported],
            "scene_units": mode,
            "applied_scale": scale,
            "handoff": "from_freecad",
            "next": "setup_lookdev + render_image for beauty shots",
        }}
        """
    )
    return session.execute(code)


HANDOFF_TOOLS: list[dict[str, Any]] = [
    {
        "name": "set_units",
        "description": (
            "Set scene units for CAD handoff. Prefer mode=mm so 1 Blender unit = 1 mm "
            "(matches FreeCAD). mode=m keeps Blender default meters."
        ),
        "inputSchema": _schema(
            {"mode": {"type": "string", "enum": ["mm", "m", "millimeters", "meters"], "default": "mm"}}
        ),
        "handler": tool_set_units,
    },
    {
        "name": "export_for_freecad",
        "description": (
            "Export mesh to FreeCAD for assembly (stl|obj). Auto scale: meters scene → ×1000 to mm; "
            "mm scene → ×1. Then use FreeCAD import_from_blender."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "format": {"type": "string", "enum": ["stl", "obj"]},
                "objects": {"type": "array", "items": {"type": "string"}},
                "scale": {"type": "number", "description": "Override auto scale"},
                "apply_modifiers": {"type": "boolean", "default": True},
            },
            ["path"],
        ),
        "handler": tool_export_for_freecad,
    },
    {
        "name": "import_from_freecad",
        "description": (
            "Import FreeCAD STL/OBJ/GLB for rendering. Default set_mm_units=true (1:1 mm). "
            "If scene stays meters, auto-scales ×0.001."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "set_mm_units": {"type": "boolean", "default": True},
                "scale": {"type": "number"},
            },
            ["path"],
        ),
        "handler": tool_import_from_freecad,
    },
]
