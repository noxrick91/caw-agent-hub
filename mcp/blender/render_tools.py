"""Look-dev / still render helpers for Blender MCP."""

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


_RENDER_HELPERS = r'''
def _r_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    return o

def _r_scene_bbox():
    import bpy
    from mathutils import Vector
    coords = []
    for o in bpy.context.scene.objects:
        if o.type not in {"MESH", "CURVE", "SURFACE", "META", "FONT"}:
            continue
        for corner in o.bound_box:
            coords.append(o.matrix_world @ Vector(corner))
    if not coords:
        return Vector((0, 0, 0)), 2.0
    mn = Vector((min(v.x for v in coords), min(v.y for v in coords), min(v.z for v in coords)))
    mx = Vector((max(v.x for v in coords), max(v.y for v in coords), max(v.z for v in coords)))
    center = (mn + mx) * 0.5
    size = (mx - mn).length
    return center, max(size, 0.5)

def _r_aim(obj, target):
    import math
    from mathutils import Vector
    direction = Vector(target) - obj.location
    if direction.length < 1e-8:
        return
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

def _r_ensure_camera(name="Camera", target=None, location=None, lens=50):
    import bpy
    from mathutils import Vector
    cam_obj = bpy.data.objects.get(name) if name else None
    if cam_obj is None or cam_obj.type != "CAMERA":
        # reuse first camera if present
        for o in bpy.data.objects:
            if o.type == "CAMERA":
                cam_obj = o
                break
    if cam_obj is None:
        data = bpy.data.cameras.new(name or "Camera")
        cam_obj = bpy.data.objects.new(data.name, data)
        bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.data.lens = float(lens)
    center, size = _r_scene_bbox()
    tgt = Vector(target) if target is not None else center
    if location is not None:
        cam_obj.location = location
    else:
        dist = size * 1.8
        cam_obj.location = (tgt.x + dist * 0.7, tgt.y - dist * 0.9, tgt.z + dist * 0.55)
    _r_aim(cam_obj, tgt)
    bpy.context.scene.camera = cam_obj
    return cam_obj

def _r_ensure_lights():
    import bpy
    lights = [o for o in bpy.context.scene.objects if o.type == "LIGHT"]
    if lights:
        return [o.name for o in lights]
    center, size = _r_scene_bbox()
    created = []
    # Key (sun)
    sun = bpy.data.lights.new("KeySun", type="SUN")
    sun.energy = 3.0
    sun_obj = bpy.data.objects.new("KeySun", sun)
    sun_obj.location = (center.x + size, center.y - size, center.z + size * 1.5)
    _r_aim(sun_obj, center)
    bpy.context.scene.collection.objects.link(sun_obj)
    created.append(sun_obj.name)
    # Fill (area)
    area = bpy.data.lights.new("FillArea", type="AREA")
    area.energy = 80.0
    area.size = max(size, 1.0)
    area_obj = bpy.data.objects.new("FillArea", area)
    area_obj.location = (center.x - size, center.y - size * 0.3, center.z + size * 0.8)
    _r_aim(area_obj, center)
    bpy.context.scene.collection.objects.link(area_obj)
    created.append(area_obj.name)
    # Rim
    rim = bpy.data.lights.new("RimPoint", type="POINT")
    rim.energy = 120.0
    rim_obj = bpy.data.objects.new("RimPoint", rim)
    rim_obj.location = (center.x, center.y + size, center.z + size * 0.6)
    bpy.context.scene.collection.objects.link(rim_obj)
    created.append(rim_obj.name)
    return created

def _r_set_engine(scene, engine):
    eng = (engine or "BLENDER_EEVEE").upper()
    aliases = {
        "EEVEE": "BLENDER_EEVEE",
        "EEVEE_NEXT": "BLENDER_EEVEE_NEXT",
        "CYCLES": "CYCLES",
        "WORKBENCH": "BLENDER_WORKBENCH",
    }
    eng = aliases.get(eng, eng)
    # Blender 4.2+ often uses EEVEE_NEXT
    candidates = [eng]
    if eng == "BLENDER_EEVEE":
        candidates = ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]
    elif eng == "BLENDER_EEVEE_NEXT":
        candidates = ["BLENDER_EEVEE_NEXT", "BLENDER_EEVEE"]
    for c in candidates:
        try:
            scene.render.engine = c
            return scene.render.engine
        except Exception:
            continue
    return scene.render.engine
'''


def tool_add_camera(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name") or "Camera"
    location = args.get("location")
    target = args.get("target")  # [x,y,z] or object name via target_object
    target_object = args.get("target_object")
    lens = float(args.get("lens") or 50)
    make_active = bool(args.get("make_active", True))
    code = textwrap.dedent(
        f"""
        {_RENDER_HELPERS}
        import bpy
        from mathutils import Vector
        target = {json.dumps(target)}
        target_object = {json.dumps(target_object)}
        if target_object:
            o = _r_obj(target_object)
            target = list(o.location)
        loc = {json.dumps(location)}
        cam = _r_ensure_camera(
            name={name!r},
            target=target,
            location=loc,
            lens={lens},
        )
        if {make_active!r}:
            bpy.context.scene.camera = cam
        __result__ = {{
            "ok": True,
            "name": cam.name,
            "location": list(cam.location),
            "lens": float(cam.data.lens),
            "active": bpy.context.scene.camera.name if bpy.context.scene.camera else None,
        }}
        """
    )
    return session.execute(code)


def tool_add_light(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    kind = (args.get("type") or "SUN").upper()
    if kind not in {"SUN", "POINT", "SPOT", "AREA"}:
        raise BlenderError("type must be SUN|POINT|SPOT|AREA")
    name = args.get("name") or kind.title()
    energy = float(args.get("energy") or (3.0 if kind == "SUN" else 100.0))
    location = args.get("location") or [3, -3, 5]
    target = args.get("target")
    target_object = args.get("target_object")
    size = float(args.get("size") or 1.0)
    code = textwrap.dedent(
        f"""
        {_RENDER_HELPERS}
        import bpy
        name = {name!r}
        kind = {kind!r}
        data = bpy.data.lights.new(name, type=kind)
        data.energy = {energy}
        if kind == "AREA" and hasattr(data, "size"):
            data.size = {size}
        obj = bpy.data.objects.new(name, data)
        obj.location = {json.dumps(location)}
        bpy.context.scene.collection.objects.link(obj)
        target = {json.dumps(target)}
        target_object = {json.dumps(target_object)}
        if target_object:
            target = list(_r_obj(target_object).location)
        if target is not None and kind in ("SUN", "SPOT", "AREA"):
            _r_aim(obj, target)
        __result__ = {{
            "ok": True,
            "name": obj.name,
            "type": kind,
            "energy": float(data.energy),
            "location": list(obj.location),
        }}
        """
    )
    return session.execute(code)


def tool_setup_lookdev(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """One-shot: camera framed on scene + 3-point lights + soft world color."""
    target_object = args.get("target_object")
    world_color = args.get("world_color") or [0.05, 0.05, 0.06]
    strength = float(args.get("world_strength") or 0.4)
    code = textwrap.dedent(
        f"""
        {_RENDER_HELPERS}
        import bpy
        target_object = {json.dumps(target_object)}
        target = None
        if target_object:
            target = list(_r_obj(target_object).location)
        cam = _r_ensure_camera(target=target)
        lights = _r_ensure_lights()
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        bg = None
        for n in nt.nodes:
            if n.type == "BACKGROUND":
                bg = n
                break
        if bg is None:
            bg = nt.nodes.new("ShaderNodeBackground")
        color = {json.dumps(world_color)}
        bg.inputs[0].default_value = (float(color[0]), float(color[1]), float(color[2]), 1.0)
        bg.inputs[1].default_value = {strength}
        __result__ = {{
            "ok": True,
            "camera": cam.name,
            "lights": lights,
            "world_strength": {strength},
        }}
        """
    )
    return session.execute(code)


def tool_set_material(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Assign a simple Principled BSDF material (base color / metallic / roughness)."""
    name = args["name"]
    material = args.get("material") or f"{name}_Mat"
    color = args.get("color") or [0.8, 0.8, 0.8]
    metallic = float(args.get("metallic") or 0.0)
    roughness = float(args.get("roughness") or 0.4)
    code = textwrap.dedent(
        f"""
        {_RENDER_HELPERS}
        import bpy
        obj = _r_obj({name!r})
        if obj.type != "MESH":
            raise RuntimeError("set_material requires a MESH object")
        mat_name = {material!r}
        mat = bpy.data.materials.get(mat_name)
        if mat is None:
            mat = bpy.data.materials.new(mat_name)
        mat.use_nodes = True
        nt = mat.node_tree
        bsdf = None
        for n in nt.nodes:
            if n.type == "BSDF_PRINCIPLED":
                bsdf = n
                break
        if bsdf is None:
            bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        color = {json.dumps(color)}
        bsdf.inputs["Base Color"].default_value = (float(color[0]), float(color[1]), float(color[2]), 1.0)
        if "Metallic" in bsdf.inputs:
            bsdf.inputs["Metallic"].default_value = {metallic}
        if "Roughness" in bsdf.inputs:
            bsdf.inputs["Roughness"].default_value = {roughness}
        if obj.data.materials:
            obj.data.materials[0] = mat
        else:
            obj.data.materials.append(mat)
        __result__ = {{
            "ok": True,
            "object": obj.name,
            "material": mat.name,
            "color": color,
            "metallic": {metallic},
            "roughness": {roughness},
        }}
        """
    )
    return session.execute(code)


def tool_render_image(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Render a still image with optional auto lookdev (camera + lights)."""
    path = args.get("path") or "renders/beauty.png"
    engine = args.get("engine") or "EEVEE"
    resolution = args.get("resolution") or [1280, 720]
    samples = args.get("samples")
    transparent = bool(args.get("transparent", False))
    auto_setup = bool(args.get("auto_setup", True))
    target_object = args.get("target_object")
    file_format = (args.get("format") or "PNG").upper()
    if file_format not in {"PNG", "JPEG", "OPEN_EXR", "TIFF"}:
        raise BlenderError("format must be PNG|JPEG|OPEN_EXR|TIFF")
    # Ensure parent dir exists on host side when relative
    try:
        Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    timeout = float(args.get("timeout") or 180)
    code = textwrap.dedent(
        f"""
        {_RENDER_HELPERS}
        import bpy
        from pathlib import Path

        scene = bpy.context.scene
        path = {path!r}
        Path(path).parent.mkdir(parents=True, exist_ok=True)

        if {auto_setup!r}:
            target = None
            to = {json.dumps(target_object)}
            if to:
                target = list(_r_obj(to).location)
            _r_ensure_camera(target=target)
            _r_ensure_lights()
            if scene.world is None:
                scene.world = bpy.data.worlds.new("World")

        engine = _r_set_engine(scene, {engine!r})
        scene.render.resolution_x = int({int(resolution[0])})
        scene.render.resolution_y = int({int(resolution[1])})
        scene.render.resolution_percentage = 100
        scene.render.filepath = path
        scene.render.image_settings.file_format = {file_format!r}
        scene.render.film_transparent = {transparent!r}

        samples = {json.dumps(samples)}
        if samples is not None:
            samples = int(samples)
            if engine == "CYCLES":
                scene.cycles.samples = samples
            else:
                # Eevee / Eevee Next
                if hasattr(scene, "eevee"):
                    if hasattr(scene.eevee, "taa_render_samples"):
                        scene.eevee.taa_render_samples = samples
                    elif hasattr(scene.eevee, "taa_samples"):
                        scene.eevee.taa_samples = samples

        if scene.camera is None:
            raise RuntimeError("no camera in scene; call setup_lookdev or add_camera first")

        bpy.ops.render.render(write_still=True)

        # Resolve written file (Blender may append extension)
        written = path
        p = Path(path)
        if not p.is_file():
            # try with extension
            ext_map = {{"PNG": ".png", "JPEG": ".jpg", "OPEN_EXR": ".exr", "TIFF": ".tif"}}
            ext = ext_map.get({file_format!r}, ".png")
            cand = Path(str(path) + ext) if not str(path).lower().endswith(ext) else p
            if cand.is_file():
                written = str(cand)
            else:
                # search folder
                stem = p.name
                hits = list(p.parent.glob(stem + ".*")) if p.parent.exists() else []
                if hits:
                    written = str(hits[0])

        __result__ = {{
            "ok": True,
            "path": written,
            "engine": engine,
            "resolution": [scene.render.resolution_x, scene.render.resolution_y],
            "transparent": {transparent!r},
            "camera": scene.camera.name if scene.camera else None,
            "format": {file_format!r},
            "auto_setup": {auto_setup!r},
        }}
        """
    )
    return session.execute(code, timeout=timeout)


def tool_set_hdri(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Load an HDRI/EXR/JPEG environment texture onto the world."""
    path = args["path"]
    strength = float(args.get("strength") or 1.0)
    rotation_z = float(args.get("rotation_z") or 0.0)
    code = textwrap.dedent(
        f"""
        import bpy
        import math
        path = {path!r}
        world = bpy.context.scene.world
        if world is None:
            world = bpy.data.worlds.new("World")
            bpy.context.scene.world = world
        world.use_nodes = True
        nt = world.node_tree
        nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputWorld")
        bg = nt.nodes.new("ShaderNodeBackground")
        tex = nt.nodes.new("ShaderNodeTexEnvironment")
        tex.image = bpy.data.images.load(path)
        mapping = nt.nodes.new("ShaderNodeMapping")
        texcoord = nt.nodes.new("ShaderNodeTexCoord")
        mapping.inputs["Rotation"].default_value[2] = math.radians({rotation_z})
        bg.inputs["Strength"].default_value = {strength}
        nt.links.new(texcoord.outputs["Generated"], mapping.inputs["Vector"])
        nt.links.new(mapping.outputs["Vector"], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], bg.inputs["Color"])
        nt.links.new(bg.outputs["Background"], out.inputs["Surface"])
        __result__ = {{
            "ok": True,
            "path": path,
            "strength": {strength},
            "rotation_z": {rotation_z},
            "image": tex.image.name if tex.image else None,
        }}
        """
    )
    return session.execute(code)


def tool_setup_compositor(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Enable compositor with optional glare/bloom and exposure."""
    glare = bool(args.get("glare", True))
    glare_type = (args.get("glare_type") or "FOG_GLOW").upper()
    threshold = float(args.get("threshold") or 0.8)
    mix = float(args.get("mix") or 0.2)
    exposure = float(args.get("exposure") or 0.0)
    code = textwrap.dedent(
        f"""
        import bpy
        scene = bpy.context.scene
        scene.use_nodes = True
        # Blender 4+ uses compositing_node_group; keep classic tree when present
        nt = getattr(scene, "node_tree", None)
        if nt is None and hasattr(scene, "compositing_node_group"):
            # Create a minimal compositor setup via scene.node_tree if available
            pass
        if scene.node_tree is None:
            # Older API always has node_tree when use_nodes True
            pass
        nt = scene.node_tree
        if nt is None:
            raise RuntimeError("compositor node tree unavailable in this Blender build")
        nt.nodes.clear()
        rl = nt.nodes.new("CompositorNodeRLayers")
        comp = nt.nodes.new("CompositorNodeComposite")
        viewer = None
        try:
            viewer = nt.nodes.new("CompositorNodeViewer")
        except Exception:
            viewer = None
        last = rl.outputs["Image"]
        note = []
        if {glare!r}:
            try:
                glare = nt.nodes.new("CompositorNodeGlare")
                glare.glare_type = {glare_type!r}
                if hasattr(glare, "threshold"):
                    glare.threshold = {threshold}
                if hasattr(glare, "mix"):
                    glare.mix = {mix}
                nt.links.new(last, glare.inputs["Image"])
                last = glare.outputs["Image"]
                note.append("glare")
            except Exception as e:
                note.append(f"glare_skip:{{e}}")
        if abs({exposure}) > 1e-6:
            try:
                exp = nt.nodes.new("CompositorNodeExposure")
                exp.inputs["Exposure"].default_value = {exposure}
                nt.links.new(last, exp.inputs["Image"])
                last = exp.outputs["Image"]
                note.append("exposure")
            except Exception as e:
                note.append(f"exposure_skip:{{e}}")
        nt.links.new(last, comp.inputs["Image"])
        if viewer is not None:
            try:
                nt.links.new(last, viewer.inputs["Image"])
            except Exception:
                pass
        __result__ = {{"ok": True, "glare": {glare!r}, "exposure": {exposure}, "nodes": note}}
        """
    )
    return session.execute(code)


RENDER_TOOLS: list[dict[str, Any]] = [
    {
        "name": "add_camera",
        "description": (
            "Create/update a camera. Auto-frames the scene (or target_object / target=[x,y,z]). "
            "Sets it as the active render camera by default."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string", "default": "Camera"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target_object": {"type": "string"},
                "lens": {"type": "number", "default": 50},
                "make_active": {"type": "boolean", "default": True},
            }
        ),
        "handler": tool_add_camera,
    },
    {
        "name": "add_light",
        "description": "Add a SUN|POINT|SPOT|AREA light. Optional target / target_object to aim it.",
        "inputSchema": _schema(
            {
                "type": {"type": "string", "enum": ["SUN", "POINT", "SPOT", "AREA"], "default": "SUN"},
                "name": {"type": "string"},
                "energy": {"type": "number"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "target_object": {"type": "string"},
                "size": {"type": "number", "default": 1.0},
            }
        ),
        "handler": tool_add_light,
    },
    {
        "name": "setup_lookdev",
        "description": (
            "One-shot lookdev: frame camera on scene (or target_object), add 3-point lights if missing, "
            "set a dark world background. Call before render_image for product shots."
        ),
        "inputSchema": _schema(
            {
                "target_object": {"type": "string"},
                "world_color": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "world_strength": {"type": "number", "default": 0.4},
            }
        ),
        "handler": tool_setup_lookdev,
    },
    {
        "name": "set_material",
        "description": "Assign a Principled BSDF material (color RGB 0-1, metallic, roughness) to a mesh.",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "material": {"type": "string"},
                "color": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "metallic": {"type": "number", "default": 0},
                "roughness": {"type": "number", "default": 0.4},
            },
            ["name"],
        ),
        "handler": tool_set_material,
    },
    {
        "name": "render_image",
        "description": (
            "PREFERRED still render: writes PNG/JPEG/EXR to path. auto_setup=true (default) creates "
            "camera+lights if missing. engine=EEVEE|CYCLES|WORKBENCH. Use for product beauty shots."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string", "default": "renders/beauty.png"},
                "engine": {
                    "type": "string",
                    "enum": ["EEVEE", "EEVEE_NEXT", "CYCLES", "WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"],
                    "default": "EEVEE",
                },
                "resolution": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                "samples": {"type": "integer"},
                "transparent": {"type": "boolean", "default": False},
                "auto_setup": {"type": "boolean", "default": True},
                "target_object": {"type": "string"},
                "format": {"type": "string", "enum": ["PNG", "JPEG", "OPEN_EXR", "TIFF"], "default": "PNG"},
                "timeout": {"type": "number"},
            }
        ),
        "handler": tool_render_image,
    },
    {
        "name": "set_hdri",
        "description": (
            "Load an HDRI/EXR/image as the world environment texture (path on disk). "
            "strength and rotation_z (degrees) supported."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "strength": {"type": "number", "default": 1.0},
                "rotation_z": {"type": "number", "default": 0},
            },
            ["path"],
        ),
        "handler": tool_set_hdri,
    },
    {
        "name": "setup_compositor",
        "description": "Enable compositor nodes with optional glare/bloom and exposure for beauty renders.",
        "inputSchema": _schema(
            {
                "glare": {"type": "boolean", "default": True},
                "glare_type": {
                    "type": "string",
                    "enum": ["FOG_GLOW", "STREAKS", "GHOSTS", "SIMPLE_STAR"],
                    "default": "FOG_GLOW",
                },
                "threshold": {"type": "number", "default": 0.8},
                "mix": {"type": "number", "default": 0.2},
                "exposure": {"type": "number", "default": 0},
            }
        ),
        "handler": tool_setup_compositor,
    },
]
