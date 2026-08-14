"""Animation tools — keyframe placements / joint offsets and export frame sequences."""

from __future__ import annotations

import json
import os
import textwrap
from pathlib import Path
from typing import Any, Callable

from backend import FreeCADSession

ToolHandler = Callable[[FreeCADSession, dict[str, Any]], dict[str, Any]]

ANIM_PROP = "CawAnimation"


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def _project_anim_dir(args: dict[str, Any]) -> Path:
    root = args.get("project_root") or os.environ.get("FREECAD_PROJECT_ROOT") or ""
    base = Path(root).expanduser().resolve() if root else Path.cwd().resolve()
    out = base / (args.get("subdir") or "animations")
    out.mkdir(parents=True, exist_ok=True)
    return out


_ANIM_HELPERS = r'''
def _anim_find(doc, name):
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")

def _anim_ensure(doc):
    if not hasattr(doc, "''' + ANIM_PROP + r'''"):
        try:
            doc.addProperty("App::PropertyString", "''' + ANIM_PROP + r'''", "Caw", "JSON animation tracks")
        except Exception:
            pass
    raw = getattr(doc, "''' + ANIM_PROP + r'''", "") or ""
    if not raw:
        return {"fps": 24, "duration": 1.0, "tracks": {}}
    import json
    try:
        data = json.loads(raw)
    except Exception:
        data = {"fps": 24, "duration": 1.0, "tracks": {}}
    data.setdefault("fps", 24)
    data.setdefault("duration", 1.0)
    data.setdefault("tracks", {})
    return data

def _anim_save(doc, data):
    import json
    if not hasattr(doc, "''' + ANIM_PROP + r'''"):
        try:
            doc.addProperty("App::PropertyString", "''' + ANIM_PROP + r'''", "Caw", "JSON animation tracks")
        except Exception:
            pass
    setattr(doc, "''' + ANIM_PROP + r'''", json.dumps(data))

def _anim_lerp(a, b, t):
    return a + (b - a) * t

def _anim_placement_at(keys, t):
    # keys: list of {t, base:[x,y,z], axis:[x,y,z], angle:deg}
    if not keys:
        return None
    keys = sorted(keys, key=lambda k: float(k.get("t", 0)))
    if t <= float(keys[0].get("t", 0)):
        k = keys[0]
    elif t >= float(keys[-1].get("t", 0)):
        k = keys[-1]
    else:
        k = keys[0]
        for i in range(len(keys) - 1):
            t0 = float(keys[i].get("t", 0))
            t1 = float(keys[i + 1].get("t", 0))
            if t0 <= t <= t1:
                u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                a, b = keys[i], keys[i + 1]
                base0 = a.get("base") or [0, 0, 0]
                base1 = b.get("base") or base0
                axis0 = a.get("axis") or [0, 0, 1]
                axis1 = b.get("axis") or axis0
                ang0 = float(a.get("angle", 0))
                ang1 = float(b.get("angle", ang0))
                return {
                    "base": [_anim_lerp(float(base0[j]), float(base1[j]), u) for j in range(3)],
                    "axis": [_anim_lerp(float(axis0[j]), float(axis1[j]), u) for j in range(3)],
                    "angle": _anim_lerp(ang0, ang1, u),
                }
        k = keys[-1]
    return {
        "base": list(k.get("base") or [0, 0, 0]),
        "axis": list(k.get("axis") or [0, 0, 1]),
        "angle": float(k.get("angle", 0)),
    }

def _anim_apply_placement(obj, pose):
    import FreeCAD
    base = pose.get("base") or [0, 0, 0]
    axis = pose.get("axis") or [0, 0, 1]
    angle = float(pose.get("angle", 0))
    obj.Placement = FreeCAD.Placement(
        FreeCAD.Vector(float(base[0]), float(base[1]), float(base[2])),
        FreeCAD.Rotation(FreeCAD.Vector(float(axis[0]), float(axis[1]), float(axis[2])), angle),
    )

def _anim_apply_joint(obj, value, mode="angle"):
    # Drive Assembly joint Offset2
    import FreeCAD
    if not hasattr(obj, "Offset2"):
        raise RuntimeError(f"{obj.Name} has no Offset2 (not a joint?)")
    off = FreeCAD.Placement(obj.Offset2)
    if mode == "angle":
        off.Rotation = FreeCAD.Rotation(FreeCAD.Vector(0, 0, 1), float(value))
    elif mode == "distance":
        off.Base = FreeCAD.Vector(float(value), 0, 0)
    else:
        raise RuntimeError(f"unknown joint drive mode: {mode}")
    obj.Offset2 = off

def _anim_apply_time(doc, data, t, solve=True):
    applied = []
    for track_name, track in (data.get("tracks") or {}).items():
        kind = track.get("kind") or "placement"
        target = track.get("target")
        if not target:
            continue
        obj = _anim_find(doc, target)
        keys = track.get("keys") or []
        if kind == "placement":
            pose = _anim_placement_at(keys, t)
            if pose:
                _anim_apply_placement(obj, pose)
                applied.append({"target": target, "kind": kind, "t": t})
        elif kind == "joint":
            # keys: {t, value}
            if not keys:
                continue
            keys = sorted(keys, key=lambda k: float(k.get("t", 0)))
            if t <= float(keys[0].get("t", 0)):
                val = float(keys[0].get("value", 0))
            elif t >= float(keys[-1].get("t", 0)):
                val = float(keys[-1].get("value", 0))
            else:
                val = float(keys[0].get("value", 0))
                for i in range(len(keys) - 1):
                    t0 = float(keys[i].get("t", 0))
                    t1 = float(keys[i + 1].get("t", 0))
                    if t0 <= t <= t1:
                        u = 0.0 if t1 <= t0 else (t - t0) / (t1 - t0)
                        v0 = float(keys[i].get("value", 0))
                        v1 = float(keys[i + 1].get("value", v0))
                        val = _anim_lerp(v0, v1, u)
                        break
            mode = track.get("mode") or "angle"
            _anim_apply_joint(obj, val, mode)
            applied.append({"target": target, "kind": kind, "value": val, "t": t})
    if solve:
        for obj in doc.Objects:
            try:
                if obj.isDerivedFrom("Assembly::AssemblyObject"):
                    obj.solve()
            except Exception:
                pass
    doc.recompute()
    return applied
'''


def tool_animation_init(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    fps = float(args.get("fps") or 24)
    duration = float(args.get("duration") or 2.0)
    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        data["fps"] = {fps}
        data["duration"] = {duration}
        if {bool(args.get('clear'))!r}:
            data["tracks"] = {{}}
        _anim_save(doc, data)
        __result__ = {{"ok": True, "document": doc.Name, "animation": data}}
        """
    )
    return session.execute(code)


def tool_animation_add_keyframe(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    target = args["target"]
    t = float(args.get("t") if args.get("t") is not None else args.get("time") or 0.0)
    kind = (args.get("kind") or "placement").lower()
    track = args.get("track") or target
    payload = {
        "t": t,
        "base": args.get("base"),
        "axis": args.get("axis") or [0, 0, 1],
        "angle": args.get("angle"),
        "value": args.get("value"),
    }
    mode = args.get("mode") or "angle"
    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        import json
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        tracks = data.setdefault("tracks", {{}})
        tr = tracks.setdefault({track!r}, {{"kind": {kind!r}, "target": {target!r}, "keys": [], "mode": {mode!r}}})
        tr["kind"] = {kind!r}
        tr["target"] = {target!r}
        tr["mode"] = {mode!r}
        key = json.loads({json.dumps(payload)!r})
        # Drop null fields
        key = {{k: v for k, v in key.items() if v is not None}}
        # Replace existing key at same t
        keys = [k for k in tr.get("keys", []) if abs(float(k.get("t", 0)) - {t}) > 1e-9]
        keys.append(key)
        keys.sort(key=lambda k: float(k.get("t", 0)))
        tr["keys"] = keys
        data["duration"] = max(float(data.get("duration", 0)), {t})
        _anim_save(doc, data)
        __result__ = {{"ok": True, "track": {track!r}, "key": key, "keys": len(keys), "animation": data}}
        """
    )
    return session.execute(code)


def tool_animation_list(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        __result__ = {{"ok": True, "document": doc.Name, "animation": data}}
        """
    )
    return session.execute(code)


def tool_animation_set_time(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    t = float(args.get("t") if args.get("t") is not None else args.get("time") or 0.0)
    solve = bool(args.get("solve", True))
    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        applied = _anim_apply_time(doc, data, {t}, solve={solve!r})
        __result__ = {{"ok": True, "t": {t}, "applied": applied}}
        """
    )
    return session.execute(code)


def tool_animation_play(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Scrub through the timeline (applies frames in FreeCAD; optional screenshots)."""
    frames = int(args.get("frames") or 0)
    start = float(args.get("start") or 0.0)
    end = args.get("end")
    capture = bool(args.get("capture", False))
    view = args.get("view") or "isometric"
    out_dir = None
    if capture:
        out_dir = _project_anim_dir(args) / (args.get("name") or "clip")
        out_dir.mkdir(parents=True, exist_ok=True)

    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        import os
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        duration = float(data.get("duration") or 1.0)
        fps = float(data.get("fps") or 24)
        t0 = {start}
        t1 = {float(end) if end is not None else -1.0}
        if t1 < 0:
            t1 = duration
        n = {frames}
        if n <= 0:
            n = max(2, int(round((t1 - t0) * fps)) + 1)
        paths = []
        for i in range(n):
            u = 0.0 if n <= 1 else i / (n - 1)
            t = t0 + (t1 - t0) * u
            _anim_apply_time(doc, data, t, solve=True)
            if {capture!r}:
                try:
                    import FreeCADGui
                    gui = FreeCADGui
                    if hasattr(gui, "ActiveDocument") and gui.ActiveDocument:
                        av = gui.ActiveDocument.ActiveView
                        view = {view!r}
                        if view == "isometric" and hasattr(av, "viewIsometric"):
                            av.viewIsometric()
                        elif view == "front" and hasattr(av, "viewFront"):
                            av.viewFront()
                        elif view == "top" and hasattr(av, "viewTop"):
                            av.viewTop()
                        if hasattr(av, "fitAll"):
                            av.fitAll()
                        path = os.path.join({str(out_dir)!r}, f"frame_{{i:04d}}.png")
                        av.saveImage(path)
                        paths.append(path)
                except Exception as e:
                    paths.append({{"error": str(e), "frame": i}})
        __result__ = {{
            "ok": True,
            "frames": n,
            "start": t0,
            "end": t1,
            "fps": fps,
            "captured": {capture!r},
            "paths": paths[:50],
            "path_count": len(paths),
            "out_dir": {str(out_dir) if out_dir else None!r},
        }}
        """
    )
    return session.execute(code)


def tool_animation_clear(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    track = args.get("track")
    code = textwrap.dedent(
        f"""
        {_ANIM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        data = _anim_ensure(doc)
        if {track!r}:
            data.get("tracks", {{}}).pop({track!r}, None)
        else:
            data["tracks"] = {{}}
        _anim_save(doc, data)
        __result__ = {{"ok": True, "animation": data}}
        """
    )
    return session.execute(code)


ANIMATION_TOOLS: list[dict[str, Any]] = [
    {
        "name": "animation_init",
        "description": (
            "Initialize (or reset) a document animation timeline stored on the document. "
            "Tracks drive Placement or Assembly joint Offset2 over time."
        ),
        "inputSchema": _schema(
            {
                "fps": {"type": "number", "default": 24},
                "duration": {"type": "number", "default": 2},
                "clear": {"type": "boolean", "default": False},
            }
        ),
        "handler": tool_animation_init,
    },
    {
        "name": "animation_add_keyframe",
        "description": (
            "Add/replace a keyframe. kind=placement uses base/axis/angle; "
            "kind=joint uses value (degrees for Revolute, mm for Slider) on Offset2."
        ),
        "inputSchema": _schema(
            {
                "target": {"type": "string", "description": "Object or joint name"},
                "t": {"type": "number", "description": "Time in seconds"},
                "time": {"type": "number"},
                "kind": {"type": "string", "enum": ["placement", "joint"], "default": "placement"},
                "track": {"type": "string", "description": "Track id (default: target name)"},
                "base": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "axis": {"type": "array", "items": {"type": "number"}, "minItems": 3, "maxItems": 3},
                "angle": {"type": "number"},
                "value": {"type": "number", "description": "Joint drive value"},
                "mode": {"type": "string", "enum": ["angle", "distance"], "default": "angle"},
            },
            ["target"],
        ),
        "handler": tool_animation_add_keyframe,
    },
    {
        "name": "animation_list",
        "description": "List animation tracks and keyframes on the active document.",
        "inputSchema": _schema({}),
        "handler": tool_animation_list,
    },
    {
        "name": "animation_set_time",
        "description": "Scrub the animation to time t (seconds) and optionally solve assemblies.",
        "inputSchema": _schema(
            {
                "t": {"type": "number"},
                "time": {"type": "number"},
                "solve": {"type": "boolean", "default": True},
            }
        ),
        "handler": tool_animation_set_time,
    },
    {
        "name": "animation_play",
        "description": (
            "Play/scrub the full timeline across N frames. "
            "capture=true saves PNGs under project animations/ (needs GUI bridge)."
        ),
        "inputSchema": _schema(
            {
                "frames": {"type": "integer", "description": "Frame count (default from fps*duration)"},
                "start": {"type": "number", "default": 0},
                "end": {"type": "number"},
                "capture": {"type": "boolean", "default": False},
                "name": {"type": "string", "description": "Output folder name under animations/"},
                "subdir": {"type": "string", "default": "animations"},
                "project_root": {"type": "string"},
                "view": {
                    "type": "string",
                    "enum": ["isometric", "front", "top", "right", "left", "rear", "bottom"],
                    "default": "isometric",
                },
            }
        ),
        "handler": tool_animation_play,
    },
    {
        "name": "animation_clear",
        "description": "Clear one animation track or all tracks.",
        "inputSchema": _schema({"track": {"type": "string"}}),
        "handler": tool_animation_clear,
    },
]
