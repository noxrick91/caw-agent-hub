"""Assembly tools for FreeCAD MCP (Assembly WB + Placement fallback)."""

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


def _unique_name(preferred: str | None, fallback: str) -> str:
    name = (preferred or fallback).strip() or fallback
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return safe or fallback


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


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


JOINT_TYPES = [
    "Fixed",
    "Revolute",
    "Cylindrical",
    "Slider",
    "Ball",
    "Distance",
    "Parallel",
    "Perpendicular",
    "Angle",
    "RackPinion",
    "Screw",
    "Gears",
    "Belt",
]

JOINT_TYPE_INDEX = {name: i for i, name in enumerate(JOINT_TYPES)}


# Shared FreeCAD-side helpers injected into executed scripts.
_ASM_HELPERS = r'''
def _asm_find(doc, name):
    if not name:
        return None
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")

def _asm_is_assembly(obj):
    try:
        return obj.isDerivedFrom("Assembly::AssemblyObject")
    except Exception:
        return obj.TypeId == "Assembly::AssemblyObject"

def _asm_get_active(doc, preferred=None):
    if preferred:
        asm = _asm_find(doc, preferred)
        return asm
    for obj in doc.Objects:
        if _asm_is_assembly(obj) or obj.TypeId == "App::Part":
            # Prefer true Assembly objects
            if _asm_is_assembly(obj):
                return obj
    for obj in doc.Objects:
        if obj.TypeId == "App::Part":
            return obj
    return None

def _asm_mode(asm):
    return "assembly" if _asm_is_assembly(asm) else "part"

def _asm_placement(placement):
    if not placement:
        return FreeCAD.Placement()
    base = placement.get("base") or [0, 0, 0]
    rot = placement.get("rotation") or {}
    axis = rot.get("axis") or [0, 0, 1]
    angle = float(rot.get("angle", 0))
    return FreeCAD.Placement(
        FreeCAD.Vector(float(base[0]), float(base[1]), float(base[2])),
        FreeCAD.Rotation(FreeCAD.Vector(float(axis[0]), float(axis[1]), float(axis[2])), angle),
    )

def _asm_ref(doc, object_name, element=None, lcs=None):
    """Build a joint reference (obj, subnames)."""
    if lcs:
        lcs_obj = _asm_find(doc, lcs)
        return (lcs_obj, [""])
    obj = _asm_find(doc, object_name)
    if element:
        if isinstance(element, str):
            return (obj, [element])
        return (obj, list(element))
    return (obj, [""])
'''


def tool_create_assembly(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Assembly")
    label = args.get("label") or name
    mode = (args.get("mode") or "auto").lower()  # auto|assembly|part
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        mode = {mode!r}
        name = {name!r}
        label = {label!r}
        asm = None
        used = None
        if mode in ("auto", "assembly"):
            try:
                asm = doc.addObject("Assembly::AssemblyObject", name)
                used = "assembly"
            except Exception as e:
                if mode == "assembly":
                    raise RuntimeError(f"Assembly workbench unavailable: {{e}}")
        if asm is None:
            asm = doc.addObject("App::Part", name)
            used = "part"
        asm.Label = label
        doc.recompute()
        __result__ = {{
            "ok": True,
            "name": asm.Name,
            "label": asm.Label,
            "type": asm.TypeId,
            "mode": used,
            "note": (
                "Full kinematic joints require FreeCAD 1.0+ Assembly workbench (mode=assembly). "
                "mode=part supports placement-based composition only."
                if used == "part" else
                "Assembly workbench container ready for components and joints."
            ),
        }}
        """
    )
    return session.execute(code)


def tool_insert_component(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    source = args["source"]
    name = _unique_name(args.get("name"), f"{source}_link")
    label = args.get("label") or name
    ground = bool(args.get("ground", False))
    placement = args.get("placement")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None:
            raise RuntimeError("no assembly/App::Part found; call create_assembly first")
        src = _asm_find(doc, {source!r})
        # Prefer linking so source geometry stays editable
        link = asm.newObject("App::Link", {name!r})
        link.LinkedObject = src
        link.Label = {label!r}
        link.Placement = _asm_placement({json.dumps(placement)})
        grounded = None
        if {ground!r} and _asm_is_assembly(asm):
            import UtilsAssembly
            import JointObject
            joint_group = UtilsAssembly.getJointGroup(asm)
            grounded = joint_group.newObject("App::FeaturePython", "GroundedJoint")
            JointObject.GroundedJoint(grounded, link)
            try:
                import FreeCADGui
                JointObject.ViewProviderGroundedJoint(grounded.ViewObject)
            except Exception:
                pass
        doc.recompute()
        __result__ = {{
            "ok": True,
            "assembly": asm.Name,
            "mode": _asm_mode(asm),
            "name": link.Name,
            "label": link.Label,
            "source": src.Name,
            "grounded_joint": None if grounded is None else grounded.Name,
            "placement_base": [link.Placement.Base.x, link.Placement.Base.y, link.Placement.Base.z],
        }}
        """
    )
    return session.execute(code)


def tool_ground_component(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    component = args["component"]
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None or not _asm_is_assembly(asm):
            raise RuntimeError("grounding requires an Assembly::AssemblyObject (FreeCAD 1.0+)")
        comp = _asm_find(doc, {component!r})
        import UtilsAssembly
        import JointObject
        joint_group = UtilsAssembly.getJointGroup(asm)
        # Remove existing grounded joint for this component
        removed = []
        for j in list(joint_group.Group):
            if hasattr(j, "ObjectToGround") and j.ObjectToGround == comp:
                removed.append(j.Name)
                doc.removeObject(j.Name)
        ground = joint_group.newObject("App::FeaturePython", "GroundedJoint")
        JointObject.GroundedJoint(ground, comp)
        try:
            import FreeCADGui
            JointObject.ViewProviderGroundedJoint(ground.ViewObject)
        except Exception:
            pass
        doc.recompute()
        try:
            asm.solve()
        except Exception:
            pass
        __result__ = {{
            "ok": True,
            "assembly": asm.Name,
            "component": comp.Name,
            "grounded_joint": ground.Name,
            "removed": removed,
        }}
        """
    )
    return session.execute(code)


def tool_create_joint(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    joint_type = args.get("joint_type") or args.get("type") or "Fixed"
    if joint_type not in JOINT_TYPE_INDEX:
        raise FreeCADError(f"joint_type must be one of {JOINT_TYPES}")
    type_index = JOINT_TYPE_INDEX[joint_type]
    assembly = args.get("assembly")
    name = _unique_name(args.get("name"), f"{joint_type}Joint")
    object_a = args["object_a"]
    object_b = args["object_b"]
    element_a = args.get("element_a")
    element_b = args.get("element_b")
    lcs_a = args.get("lcs_a")
    lcs_b = args.get("lcs_b")
    distance = args.get("distance")
    angle = args.get("angle")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None or not _asm_is_assembly(asm):
            raise RuntimeError(
                "create_joint requires Assembly::AssemblyObject. "
                "Use create_assembly(mode='assembly') on FreeCAD 1.0+, "
                "or set_component_placement for App::Part composition."
            )
        import UtilsAssembly
        import JointObject
        joint_group = UtilsAssembly.getJointGroup(asm)
        joint = joint_group.newObject("App::FeaturePython", {name!r})
        proxy = JointObject.Joint(joint, {type_index})
        try:
            import FreeCADGui
            JointObject.ViewProviderJoint(joint.ViewObject)
        except Exception:
            pass
        ref1 = _asm_ref(doc, {object_a!r}, {element_a!r}, {lcs_a!r})
        ref2 = _asm_ref(doc, {object_b!r}, {element_b!r}, {lcs_b!r})
        # Prefer setter when available; fall back to properties
        try:
            proxy.setJointConnectors(joint, [ref1, ref2])
        except Exception:
            joint.Reference1 = ref1
            joint.Reference2 = ref2
        distance = {json.dumps(distance)}
        angle = {json.dumps(angle)}
        if distance is not None and hasattr(joint, "Distance"):
            joint.Distance = float(distance)
        if angle is not None and hasattr(joint, "Angle"):
            joint.Angle = float(angle)
        joint.recompute()
        doc.recompute()
        try:
            asm.solve()
        except Exception as e:
            solve_error = str(e)
        else:
            solve_error = None
        __result__ = {{
            "ok": True,
            "assembly": asm.Name,
            "name": joint.Name,
            "label": joint.Label,
            "joint_type": joint.JointType if hasattr(joint, "JointType") else {joint_type!r},
            "object_a": {object_a!r},
            "object_b": {object_b!r},
            "solve_error": solve_error,
        }}
        """
    )
    return session.execute(code)


def tool_set_joint_offset(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    which = (args.get("which") or "Offset2").lower()
    prop = "Offset1" if which in ("1", "offset1") else "Offset2"
    placement = args.get("placement") or {}
    base = _vec(placement.get("base"), (0.0, 0.0, 0.0))
    rot = placement.get("rotation") or {}
    axis = _vec(rot.get("axis"), (0.0, 0.0, 1.0))
    angle = float(rot.get("angle", 0.0))
    solve = bool(args.get("solve", True))
    assembly = args.get("assembly")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        joint = _asm_find(doc, {name!r})
        if not hasattr(joint, {prop!r}):
            raise RuntimeError(f"joint has no property {{{prop}}}")
        joint.{prop} = FreeCAD.Placement(
            FreeCAD.Vector{base},
            FreeCAD.Rotation(FreeCAD.Vector{axis}, {angle})
        )
        doc.recompute()
        asm = _asm_get_active(doc, {assembly!r})
        solve_error = None
        if {solve!r} and asm is not None and _asm_is_assembly(asm):
            try:
                asm.solve()
            except Exception as e:
                solve_error = str(e)
        __result__ = {{
            "ok": True,
            "name": joint.Name,
            "property": {prop!r},
            "solve_error": solve_error,
        }}
        """
    )
    return session.execute(code)


def tool_list_assembly(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None:
            raise RuntimeError("no assembly found")
        components = []
        joints = []
        for o in asm.OutList:
            info = {{
                "name": o.Name,
                "label": o.Label,
                "type": o.TypeId,
            }}
            if o.TypeId == "App::Link" or hasattr(o, "LinkedObject"):
                try:
                    linked = o.LinkedObject
                    info["linked"] = None if linked is None else getattr(linked, "Name", str(linked))
                except Exception:
                    info["linked"] = None
                try:
                    b = o.Placement.Base
                    info["placement_base"] = [b.x, b.y, b.z]
                except Exception:
                    pass
                components.append(info)
            elif o.TypeId == "Assembly::JointGroup":
                for j in o.Group:
                    jinfo = {{
                        "name": j.Name,
                        "label": j.Label,
                        "type": j.TypeId,
                    }}
                    if hasattr(j, "JointType"):
                        jinfo["joint_type"] = j.JointType
                    if hasattr(j, "ObjectToGround") and j.ObjectToGround is not None:
                        jinfo["grounded"] = j.ObjectToGround.Name
                        jinfo["joint_type"] = "Grounded"
                    joints.append(jinfo)
            elif o.TypeId not in ("App::Origin", "Assembly::BomGroup"):
                # nested parts / other children
                if "Origin" not in o.TypeId:
                    components.append(info)
        # Also surface asm.Joints if available
        if hasattr(asm, "Joints"):
            known = {{j["name"] for j in joints}}
            for j in asm.Joints:
                if j.Name in known:
                    continue
                jinfo = {{"name": j.Name, "label": j.Label, "type": j.TypeId}}
                if hasattr(j, "JointType"):
                    jinfo["joint_type"] = j.JointType
                joints.append(jinfo)
        __result__ = {{
            "ok": True,
            "assembly": asm.Name,
            "label": asm.Label,
            "type": asm.TypeId,
            "mode": _asm_mode(asm),
            "components": components,
            "joints": joints,
        }}
        """
    )
    return session.execute(code)


def tool_solve_assembly(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None or not _asm_is_assembly(asm):
            raise RuntimeError("solve_assembly requires Assembly::AssemblyObject")
        asm.solve()
        doc.recompute()
        placements = []
        for o in asm.OutList:
            if o.TypeId == "App::Link" or hasattr(o, "LinkedObject"):
                b = o.Placement.Base
                r = o.Placement.Rotation
                placements.append({{
                    "name": o.Name,
                    "base": [b.x, b.y, b.z],
                    "rotation_axis_angle": list(r.Axis) + [r.Angle],
                }})
        __result__ = {{
            "ok": True,
            "assembly": asm.Name,
            "component_placements": placements,
        }}
        """
    )
    return session.execute(code)


def tool_set_component_placement(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    placement = args.get("placement") or {}
    solve = bool(args.get("solve", False))
    assembly = args.get("assembly")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        obj = _asm_find(doc, {name!r})
        obj.Placement = _asm_placement({json.dumps(placement)})
        doc.recompute()
        solve_error = None
        if {solve!r}:
            asm = _asm_get_active(doc, {assembly!r})
            if asm is not None and _asm_is_assembly(asm):
                try:
                    asm.solve()
                except Exception as e:
                    solve_error = str(e)
        b = obj.Placement.Base
        __result__ = {{
            "ok": True,
            "name": obj.Name,
            "placement_base": [b.x, b.y, b.z],
            "solve_error": solve_error,
        }}
        """
    )
    return session.execute(code)


def tool_create_lcs(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Create a local coordinate system for joint attachment."""
    parent = args.get("parent")  # component / body / part
    name = _unique_name(args.get("name"), "LCS")
    placement = args.get("placement")
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        parent_name = {parent!r}
        parent = _asm_find(doc, parent_name) if parent_name else None
        lcs = None
        # Prefer PartDesign coordinate system when parent is a Body
        try:
            if parent is not None and parent.TypeId == "PartDesign::Body":
                lcs = parent.newObject("PartDesign::CoordinateSystem", {name!r})
            elif parent is not None and hasattr(parent, "newObject"):
                try:
                    lcs = parent.newObject("App::LocalCoordinateSystem", {name!r})
                except Exception:
                    lcs = parent.newObject("PartDesign::CoordinateSystem", {name!r})
        except Exception:
            lcs = None
        if lcs is None:
            try:
                lcs = doc.addObject("App::LocalCoordinateSystem", {name!r})
            except Exception:
                try:
                    lcs = doc.addObject("PartDesign::CoordinateSystem", {name!r})
                except Exception as e:
                    raise RuntimeError(f"cannot create LCS: {{e}}")
            if parent is not None and hasattr(parent, "addObject"):
                try:
                    parent.addObject(lcs)
                except Exception:
                    pass
        lcs.Placement = _asm_placement({json.dumps(placement)})
        doc.recompute()
        b = lcs.Placement.Base
        __result__ = {{
            "ok": True,
            "name": lcs.Name,
            "label": lcs.Label,
            "type": lcs.TypeId,
            "parent": None if parent is None else parent.Name,
            "placement_base": [b.x, b.y, b.z],
        }}
        """
    )
    return session.execute(code)


def tool_unground_component(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    assembly = args.get("assembly")
    component = args["component"]
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _asm_get_active(doc, {assembly!r})
        if asm is None or not _asm_is_assembly(asm):
            raise RuntimeError("unground requires Assembly::AssemblyObject")
        comp = _asm_find(doc, {component!r})
        import UtilsAssembly
        joint_group = UtilsAssembly.getJointGroup(asm)
        removed = []
        for j in list(joint_group.Group):
            if hasattr(j, "ObjectToGround") and j.ObjectToGround == comp:
                removed.append(j.Name)
                doc.removeObject(j.Name)
        doc.recompute()
        __result__ = {{"ok": True, "assembly": asm.Name, "component": comp.Name, "removed": removed}}
        """
    )
    return session.execute(code)


def tool_delete_joint(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = args["name"]
    code = textwrap.dedent(
        f"""
        {_ASM_HELPERS}
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        joint = _asm_find(doc, {name!r})
        n = joint.Name
        doc.removeObject(n)
        doc.recompute()
        __result__ = {{"ok": True, "deleted": n}}
        """
    )
    return session.execute(code)


ASSEMBLY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_assembly",
        "description": (
            "Create an assembly container. Prefers FreeCAD 1.0+ Assembly::AssemblyObject "
            "(kinematic joints). Falls back to App::Part for placement-only composition."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "mode": {
                    "type": "string",
                    "enum": ["auto", "assembly", "part"],
                    "default": "auto",
                    "description": "auto tries Assembly WB then App::Part; assembly forces WB; part forces App::Part",
                },
            }
        ),
        "handler": tool_create_assembly,
    },
    {
        "name": "insert_component",
        "description": (
            "Insert a part/body/solid into an assembly as App::Link. "
            "Optional ground=true locks the first component (Assembly WB only)."
        ),
        "inputSchema": _schema(
            {
                "source": {"type": "string", "description": "Name of object to link into the assembly"},
                "assembly": {"type": "string", "description": "Target assembly name (default: active/first)"},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "ground": {"type": "boolean", "default": False},
                "placement": PLACEMENT_PROP,
            },
            ["source"],
        ),
        "handler": tool_insert_component,
    },
    {
        "name": "ground_component",
        "description": "Ground (fix in place) a component in an Assembly::AssemblyObject.",
        "inputSchema": _schema(
            {
                "component": {"type": "string"},
                "assembly": {"type": "string"},
            },
            ["component"],
        ),
        "handler": tool_ground_component,
    },
    {
        "name": "unground_component",
        "description": "Remove grounding joint from a component.",
        "inputSchema": _schema(
            {
                "component": {"type": "string"},
                "assembly": {"type": "string"},
            },
            ["component"],
        ),
        "handler": tool_unground_component,
    },
    {
        "name": "create_joint",
        "description": (
            "Create an Assembly joint between two components. "
            f"Types: {', '.join(JOINT_TYPES)}. "
            "Prefer pairing LCS markers (lcs_a/lcs_b) created with create_lcs; "
            "or pass element_a/element_b subnames like Face1/Edge1."
        ),
        "inputSchema": _schema(
            {
                "joint_type": {"type": "string", "enum": JOINT_TYPES, "default": "Fixed"},
                "object_a": {"type": "string"},
                "object_b": {"type": "string"},
                "element_a": {"type": "string", "description": "Sub-element on A, e.g. Face1"},
                "element_b": {"type": "string", "description": "Sub-element on B, e.g. Face1"},
                "lcs_a": {"type": "string", "description": "LCS object name for connector A"},
                "lcs_b": {"type": "string", "description": "LCS object name for connector B"},
                "name": {"type": "string"},
                "assembly": {"type": "string"},
                "distance": {"type": "number", "description": "For Distance/RackPinion/Screw/Gears/Belt"},
                "angle": {"type": "number", "description": "For Angle joint (degrees)"},
            },
            ["object_a", "object_b"],
        ),
        "handler": tool_create_joint,
    },
    {
        "name": "set_joint_offset",
        "description": (
            "Set Offset1/Offset2 on a joint (useful to drive Revolute/Slider pose via Offset2 rotation/translation)."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "which": {"type": "string", "enum": ["Offset1", "Offset2", "1", "2"], "default": "Offset2"},
                "placement": PLACEMENT_PROP,
                "solve": {"type": "boolean", "default": True},
                "assembly": {"type": "string"},
            },
            ["name"],
        ),
        "handler": tool_set_joint_offset,
    },
    {
        "name": "list_assembly",
        "description": "List assembly components (links) and joints.",
        "inputSchema": _schema({"assembly": {"type": "string"}}),
        "handler": tool_list_assembly,
    },
    {
        "name": "solve_assembly",
        "description": "Run the Assembly kinematic solver and return updated component placements.",
        "inputSchema": _schema({"assembly": {"type": "string"}}),
        "handler": tool_solve_assembly,
    },
    {
        "name": "set_component_placement",
        "description": "Set Placement of an assembly component/link (also works for App::Part composition).",
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "placement": PLACEMENT_PROP,
                "solve": {"type": "boolean", "default": False},
                "assembly": {"type": "string"},
            },
            ["name"],
        ),
        "handler": tool_set_component_placement,
    },
    {
        "name": "create_lcs",
        "description": (
            "Create a Local Coordinate System for joint attachment. "
            "Place LCS on each mate feature, then create_joint with lcs_a/lcs_b."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "parent": {"type": "string", "description": "Optional parent Body/Part/Link"},
                "placement": PLACEMENT_PROP,
            }
        ),
        "handler": tool_create_lcs,
    },
    {
        "name": "delete_joint",
        "description": "Delete a joint or grounded joint by name.",
        "inputSchema": _schema({"name": {"type": "string"}}, ["name"]),
        "handler": tool_delete_joint,
    },
]
