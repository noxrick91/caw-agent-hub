"""Blender animation tools — timeline, keyframes, playback, frame export."""

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


_HELPERS = r'''
def _b_obj(name):
    import bpy
    o = bpy.data.objects.get(name)
    if o is None:
        raise RuntimeError(f"object not found: {name}")
    return o

def _b_deg_to_rad(v):
    import math
    return [math.radians(float(a)) for a in v]

def _b_ensure_action(obj):
    import bpy
    if obj.animation_data is None:
        obj.animation_data_create()
    if obj.animation_data.action is None:
        action = bpy.data.actions.new(name=f"{obj.name}Action")
        obj.animation_data.action = action
    return obj.animation_data.action
'''


def tool_animation_setup(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    fps = int(args.get("fps") or 24)
    frame_start = int(args.get("frame_start") or 1)
    frame_end = int(args.get("frame_end") or 120)
    if frame_end < frame_start:
        raise BlenderError("frame_end must be >= frame_start")
    code = textwrap.dedent(
        f"""
        import bpy
        scene = bpy.context.scene
        scene.render.fps = {fps}
        scene.frame_start = {frame_start}
        scene.frame_end = {frame_end}
        scene.frame_current = {frame_start}
        __result__ = {{
            "ok": True,
            "fps": scene.render.fps,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
        }}
        """
    )
    return session.execute(code)


def tool_animation_set_frame(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    frame = int(args["frame"])
    code = textwrap.dedent(
        f"""
        import bpy
        scene = bpy.context.scene
        scene.frame_set({frame})
        __result__ = {{
            "ok": True,
            "frame": scene.frame_current,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
        }}
        """
    )
    return session.execute(code)


def tool_animation_timeline(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        import bpy
        scene = bpy.context.scene
        animated = []
        for o in bpy.context.scene.objects:
            ad = o.animation_data
            if ad and ad.action and ad.action.fcurves:
                animated.append({
                    "name": o.name,
                    "action": ad.action.name,
                    "fcurves": len(ad.action.fcurves),
                })
        __result__ = {
            "ok": True,
            "fps": scene.render.fps,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "frame_current": scene.frame_current,
            "animated_objects": animated,
        }
        """
    )
    return session.execute(code)


def tool_animation_keyframe(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Insert keyframes for location / rotation_deg / scale at a frame (optional set values first)."""
    name = args["name"]
    frame = args.get("frame")
    location = args.get("location")
    rotation_deg = args.get("rotation_deg") or args.get("rotation")
    scale = args.get("scale")
    channels = args.get("channels")  # location|rotation|scale|all or list
    if channels is None:
        channels = "all"
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy, math
        o = _b_obj({name!r})
        scene = bpy.context.scene
        frame = {json.dumps(frame)}
        if frame is None:
            frame = scene.frame_current
        else:
            frame = int(frame)
            scene.frame_set(frame)

        loc = {json.dumps(location)}
        rot = {json.dumps(rotation_deg)}
        sc = {json.dumps(scale)}
        if loc is not None:
            o.location = loc
        if rot is not None:
            o.rotation_euler = _b_deg_to_rad(rot)
        if sc is not None:
            if isinstance(sc, (int, float)):
                o.scale = (float(sc), float(sc), float(sc))
            else:
                o.scale = sc

        ch = {json.dumps(channels)}
        if isinstance(ch, str):
            ch = ch.lower()
            if ch == "all":
                keys = ["location", "rotation_euler", "scale"]
            elif ch in ("location", "loc"):
                keys = ["location"]
            elif ch in ("rotation", "rot", "rotation_euler"):
                keys = ["rotation_euler"]
            elif ch == "scale":
                keys = ["scale"]
            else:
                raise RuntimeError(f"unknown channels: {{ch}}")
        else:
            keys = []
            for c in ch:
                c = str(c).lower()
                if c in ("location", "loc"):
                    keys.append("location")
                elif c in ("rotation", "rot", "rotation_euler"):
                    keys.append("rotation_euler")
                elif c == "scale":
                    keys.append("scale")
        inserted = []
        for data_path in keys:
            o.keyframe_insert(data_path=data_path, frame=frame)
            inserted.append(data_path)
        _b_ensure_action(o)
        __result__ = {{
            "ok": True,
            "name": o.name,
            "frame": frame,
            "channels": inserted,
            "location": list(o.location),
            "rotation_euler_deg": [round(a * 57.2958, 3) for a in o.rotation_euler],
            "scale": list(o.scale),
        }}
        """
    )
    return session.execute(code)


def tool_animation_list(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        names = {json.dumps([name] if name else None)}
        objs = []
        if names:
            objs = [_b_obj(names[0])]
        else:
            objs = [o for o in bpy.context.scene.objects if o.animation_data and o.animation_data.action]

        out = []
        for o in objs:
            ad = o.animation_data
            if not ad or not ad.action:
                out.append({{"name": o.name, "keyframes": []}})
                continue
            action = ad.action
            # Collect unique frames per data_path
            by_path = {{}}
            for fc in action.fcurves:
                path = fc.data_path
                frames = sorted({{int(kp.co[0]) for kp in fc.keyframe_points}})
                by_path.setdefault(path, set()).update(frames)
            tracks = []
            for path, frames in sorted(by_path.items()):
                tracks.append({{"data_path": path, "frames": sorted(frames)}})
            out.append({{
                "name": o.name,
                "action": action.name,
                "tracks": tracks,
            }})
        __result__ = {{"ok": True, "objects": out}}
        """
    )
    return session.execute(code)


def tool_animation_clear(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args.get("name")
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        target = {json.dumps(name)}
        cleared = []
        if target:
            objs = [_b_obj(target)]
        else:
            objs = list(bpy.context.scene.objects)
        for o in objs:
            if o.animation_data:
                if o.animation_data.action:
                    action = o.animation_data.action
                    o.animation_data.action = None
                    if action.users == 0:
                        bpy.data.actions.remove(action)
                o.animation_data_clear()
                cleared.append(o.name)
        __result__ = {{"ok": True, "cleared": cleared}}
        """
    )
    return session.execute(code)


def tool_animation_parent(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Parent object to another (useful for hinged shells / limbs)."""
    child = args["child"]
    parent = args.get("parent")  # None / "" to clear
    keep_transform = bool(args.get("keep_transform", True))
    code = textwrap.dedent(
        f"""
        {_HELPERS}
        import bpy
        child = _b_obj({child!r})
        parent_name = {json.dumps(parent)}
        if not parent_name:
            if {keep_transform!r}:
                mw = child.matrix_world.copy()
                child.parent = None
                child.matrix_world = mw
            else:
                child.parent = None
            __result__ = {{"ok": True, "child": child.name, "parent": None}}
        else:
            parent = _b_obj(parent_name)
            if {keep_transform!r}:
                mw = child.matrix_world.copy()
                child.parent = parent
                child.matrix_world = mw
            else:
                child.parent = parent
            __result__ = {{"ok": True, "child": child.name, "parent": parent.name}}
        """
    )
    return session.execute(code)


def tool_animation_play(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Scrub timeline and optionally render/export each frame to an image sequence."""
    frame_start = args.get("frame_start")
    frame_end = args.get("frame_end")
    step = max(1, int(args.get("step") or 1))
    capture = bool(args.get("capture", False))
    output_dir = args.get("output_dir") or args.get("path") or "animations"
    prefix = args.get("prefix") or "frame"
    file_format = (args.get("format") or "PNG").upper()
    code = textwrap.dedent(
        f"""
        import bpy
        import os
        from pathlib import Path

        scene = bpy.context.scene
        start = {json.dumps(frame_start)}
        end = {json.dumps(frame_end)}
        if start is None:
            start = scene.frame_start
        if end is None:
            end = scene.frame_end
        start, end = int(start), int(end)
        step = {step}
        capture = {capture!r}
        out_dir = Path({output_dir!r})
        prefix = {prefix!r}
        fmt = {file_format!r}
        frames = list(range(start, end + 1, step))
        paths = []

        if capture:
            out_dir.mkdir(parents=True, exist_ok=True)
            scene.render.image_settings.file_format = fmt if fmt in ("PNG", "JPEG", "OPEN_EXR") else "PNG"

        for f in frames:
            scene.frame_set(f)
            if capture:
                fp = out_dir / f"{{prefix}}_{{f:04d}}"
                scene.render.filepath = str(fp)
                bpy.ops.render.render(write_still=True)
                # Blender appends extension
                ext = ".png" if scene.render.image_settings.file_format == "PNG" else ".jpg"
                written = str(fp) + ext
                if not Path(written).is_file():
                    # try without guessing
                    candidates = list(out_dir.glob(f"{{prefix}}_{{f:04d}}.*"))
                    written = str(candidates[0]) if candidates else written
                paths.append(written)

        scene.frame_set(end)
        __result__ = {{
            "ok": True,
            "frames": frames,
            "count": len(frames),
            "capture": capture,
            "output_dir": str(out_dir) if capture else None,
            "paths": paths[:20],
            "paths_total": len(paths),
            "frame_current": scene.frame_current,
        }}
        """
    )
    # Rendering many frames can be slow
    timeout = float(args.get("timeout") or (300 if capture else 120))
    return session.execute(code, timeout=timeout)


def tool_animation_render(session: BlenderSession, args: dict[str, Any]) -> dict[str, Any]:
    """Render the full animation range to a video or image sequence via Blender's anim render."""
    output = args.get("path") or "animations/anim"
    file_format = (args.get("format") or "FFMPEG").upper()  # FFMPEG | PNG | JPEG
    fps = args.get("fps")
    code = textwrap.dedent(
        f"""
        import bpy
        from pathlib import Path

        scene = bpy.context.scene
        path = {output!r}
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        scene.render.filepath = path
        fmt = {file_format!r}
        if fmt == "FFMPEG":
            scene.render.image_settings.file_format = "FFMPEG"
            scene.render.ffmpeg.format = "MPEG4"
            scene.render.ffmpeg.codec = "H264"
        elif fmt in ("PNG", "JPEG", "OPEN_EXR"):
            scene.render.image_settings.file_format = fmt
        else:
            raise RuntimeError(f"unsupported format: {{fmt}}")
        fps = {json.dumps(fps)}
        if fps is not None:
            scene.render.fps = int(fps)
        bpy.ops.render.render(animation=True)
        __result__ = {{
            "ok": True,
            "path": scene.render.filepath,
            "format": scene.render.image_settings.file_format,
            "frame_start": scene.frame_start,
            "frame_end": scene.frame_end,
            "fps": scene.render.fps,
        }}
        """
    )
    timeout = float(args.get("timeout") or 600)
    return session.execute(code, timeout=timeout)


ANIMATION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "animation_setup",
        "description": "Set scene fps and frame_start/frame_end for animation.",
        "inputSchema": _schema(
            {
                "fps": {"type": "integer", "default": 24},
                "frame_start": {"type": "integer", "default": 1},
                "frame_end": {"type": "integer", "default": 120},
            }
        ),
        "handler": tool_animation_setup,
    },
    {
        "name": "animation_set_frame",
        "description": "Jump the timeline to a frame (updates driven transforms).",
        "inputSchema": _schema({"frame": {"type": "integer"}}, ["frame"]),
        "handler": tool_animation_set_frame,
    },
    {
        "name": "animation_timeline",
        "description": "Report fps, frame range, current frame, and objects that have actions.",
        "inputSchema": _schema({}),
        "handler": tool_animation_timeline,
    },
    {
        "name": "animation_keyframe",
        "description": (
            "Insert keyframes on an object. Optionally set location / rotation_deg / scale first. "
            "channels=all|location|rotation|scale (or list). frame defaults to current."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "frame": {"type": "integer"},
                "location": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotation_deg": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "rotation": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "scale": {
                    "oneOf": [
                        {"type": "number"},
                        {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                    ]
                },
                "channels": {
                    "oneOf": [
                        {"type": "string"},
                        {"type": "array", "items": {"type": "string"}},
                    ],
                    "description": "all | location | rotation | scale, or a list thereof",
                },
            },
            ["name"],
        ),
        "handler": tool_animation_keyframe,
    },
    {
        "name": "animation_list",
        "description": "List keyframe tracks/frames for one object or all animated objects.",
        "inputSchema": _schema({"name": {"type": "string"}}),
        "handler": tool_animation_list,
    },
    {
        "name": "animation_clear",
        "description": "Clear animation data on one object (or all if name omitted).",
        "inputSchema": _schema({"name": {"type": "string"}}),
        "handler": tool_animation_clear,
    },
    {
        "name": "animation_parent",
        "description": "Parent child object to parent (or clear parent if parent omitted). keep_transform default true.",
        "inputSchema": _schema(
            {
                "child": {"type": "string"},
                "parent": {"type": "string"},
                "keep_transform": {"type": "boolean", "default": True},
            },
            ["child"],
        ),
        "handler": tool_animation_parent,
    },
    {
        "name": "animation_play",
        "description": (
            "Scrub from frame_start→frame_end (step). capture=true renders each frame to "
            "output_dir/prefix_####.png (needs camera; slow on cmd backend)."
        ),
        "inputSchema": _schema(
            {
                "frame_start": {"type": "integer"},
                "frame_end": {"type": "integer"},
                "step": {"type": "integer", "default": 1},
                "capture": {"type": "boolean", "default": False},
                "output_dir": {"type": "string", "default": "animations"},
                "path": {"type": "string"},
                "prefix": {"type": "string", "default": "frame"},
                "format": {"type": "string", "enum": ["PNG", "JPEG"], "default": "PNG"},
                "timeout": {"type": "number"},
            }
        ),
        "handler": tool_animation_play,
    },
    {
        "name": "animation_render",
        "description": "Render the scene animation range to video (FFMPEG/mp4) or image sequence.",
        "inputSchema": _schema(
            {
                "path": {"type": "string", "default": "animations/anim"},
                "format": {"type": "string", "enum": ["FFMPEG", "PNG", "JPEG"], "default": "FFMPEG"},
                "fps": {"type": "integer"},
                "timeout": {"type": "number"},
            }
        ),
        "handler": tool_animation_render,
    },
]
