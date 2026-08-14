"""Export FreeCAD assemblies to URDF (+ mesh package) for ROS / simulators."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
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


# Joint type mapping FreeCAD Assembly WB → URDF
# (string names and numeric enums vary by FC version; handle both in script)


def tool_export_urdf(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Export active assembly to a URDF package: robot.urdf + meshes/*.stl."""
    out_dir = args.get("path") or args.get("output_dir") or "exports/urdf_robot"
    robot_name = args.get("robot_name") or "caw_robot"
    assembly = args.get("assembly")
    mesh_format = (args.get("mesh_format") or "stl").lower()
    if mesh_format not in {"stl"}:
        raise FreeCADError("mesh_format currently supports stl only")
    package_name = args.get("package_name") or robot_name
    base_link = args.get("base_link")  # optional override grounded link name
    linear_deflection = float(args.get("linear_deflection") or 0.1)
    # ROS package:// vs relative file:// meshes
    mesh_uri_mode = (args.get("mesh_uri") or "package").lower()  # package|relative

    code = textwrap.dedent(
        f"""
        import os, re, json, math
        import FreeCAD
        import Mesh

        def _safe(name):
            s = re.sub(r"[^0-9A-Za-z_]+", "_", name.strip()) or "link"
            if s[0].isdigit():
                s = "l_" + s
            return s.lower()

        def _find(doc, name):
            if not name:
                return None
            o = doc.getObject(name)
            if o is not None:
                return o
            for obj in doc.Objects:
                if obj.Label == name:
                    return obj
            raise RuntimeError(f"object not found: {{name}}")

        def _is_asm(obj):
            try:
                return obj.isDerivedFrom("Assembly::AssemblyObject")
            except Exception:
                return getattr(obj, "TypeId", "") == "Assembly::AssemblyObject"

        def _get_asm(doc, preferred=None):
            if preferred:
                return _find(doc, preferred)
            for obj in doc.Objects:
                if _is_asm(obj):
                    return obj
            for obj in doc.Objects:
                if obj.TypeId == "App::Part":
                    return obj
            return None

        def _mesh_from_obj(obj, deflection={linear_deflection}):
            # Resolve App::Link → LinkedObject shape/mesh
            src = obj
            try:
                if hasattr(obj, "LinkedObject") and obj.LinkedObject is not None:
                    src = obj.LinkedObject
            except Exception:
                pass
            if src.isDerivedFrom("Mesh::Feature"):
                return src.Mesh.copy()
            if hasattr(src, "Shape") and not src.Shape.isNull():
                try:
                    import MeshPart
                    return MeshPart.meshFromShape(
                        Shape=src.Shape,
                        LinearDeflection=deflection,
                        AngularDeflection=0.5,
                    )
                except Exception:
                    verts, facets = src.Shape.tessellate(deflection)
                    return Mesh.Mesh([tuple(v) for v in verts], facets)
            raise RuntimeError(f"no meshable geometry on {{obj.Name}}")

        def _placement_xyz_rpy(pl):
            # FreeCAD Placement → URDF xyz (m) + rpy
            # FreeCAD lengths are mm → convert to meters for ROS URDF convention
            b = pl.Base
            # Rotation as yaw-pitch-roll from matrix (ZYX)
            m = pl.Rotation.toMatrix()
            # Extract RPY from rotation matrix
            sy = math.sqrt(m.A11 * m.A11 + m.A21 * m.A21)
            if sy > 1e-6:
                roll = math.atan2(m.A32, m.A33)
                pitch = math.atan2(-m.A31, sy)
                yaw = math.atan2(m.A21, m.A11)
            else:
                roll = math.atan2(-m.A23, m.A22)
                pitch = math.atan2(-m.A31, sy)
                yaw = 0.0
            return (
                [b.x / 1000.0, b.y / 1000.0, b.z / 1000.0],
                [roll, pitch, yaw],
            )

        def _joint_type_urdf(j):
            jt = getattr(j, "JointType", None)
            # string or int
            name = None
            if isinstance(jt, str):
                name = jt
            elif jt is not None:
                # try enum name
                name = str(jt)
                for cand in (
                    "Fixed", "Revolute", "Cylindrical", "Slider", "Ball",
                    "Distance", "Parallel", "Grounded",
                ):
                    if cand.lower() in name.lower():
                        name = cand
                        break
            # Grounded joints
            if hasattr(j, "ObjectToGround") and getattr(j, "ObjectToGround", None) is not None:
                return "fixed", "grounded"
            mapping = {{
                "Fixed": "fixed",
                "Revolute": "revolute",
                "Slider": "prismatic",
                "Cylindrical": "continuous",  # approx: rotation DOF; translation ignored
                "Ball": "floating",  # approx
                "Distance": "fixed",
                "Parallel": "fixed",
                "Grounded": "fixed",
            }}
            if name in mapping:
                return mapping[name], name
            # fallback by TypeId
            tid = getattr(j, "TypeId", "")
            if "Grounded" in tid:
                return "fixed", "Grounded"
            return "fixed", name or "unknown"

        def _joint_refs(j):
            # Try common FreeCAD 1.0 joint reference properties
            a = b = None
            for pa, pb in (
                ("Object1", "Object2"),
                ("Reference1", "Reference2"),
                ("Part1", "Part2"),
            ):
                if hasattr(j, pa) and hasattr(j, pb):
                    ra, rb = getattr(j, pa), getattr(j, pb)
                    # may be (obj, sub) tuples
                    if isinstance(ra, (list, tuple)):
                        a = ra[0]
                    else:
                        a = ra
                    if isinstance(rb, (list, tuple)):
                        b = rb[0]
                    else:
                        b = rb
                    break
            def _name(x):
                if x is None:
                    return None
                return getattr(x, "Name", str(x))
            return _name(a), _name(b)

        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        asm = _get_asm(doc, {assembly!r})
        if asm is None:
            raise RuntimeError("no assembly found; create_assembly + insert_component first")

        out_dir = {out_dir!r}
        robot_name = _safe({robot_name!r})
        package_name = _safe({package_name!r})
        mesh_uri_mode = {mesh_uri_mode!r}
        os.makedirs(os.path.join(out_dir, "meshes"), exist_ok=True)

        # Collect links (App::Link components preferred)
        components = []
        for o in asm.OutList:
            if o.TypeId == "App::Link" or hasattr(o, "LinkedObject"):
                components.append(o)
            elif o.TypeId == "App::Part" and o is not asm:
                components.append(o)
        if not components:
            # fallback: all meshable objects in doc except assembly container
            for o in doc.Objects:
                if o is asm:
                    continue
                try:
                    _mesh_from_obj(o)
                    components.append(o)
                except Exception:
                    pass
        if not components:
            raise RuntimeError("no components to export as URDF links")

        # Collect joints
        joints = []
        grounded = set()
        for o in asm.OutList:
            if o.TypeId == "Assembly::JointGroup":
                for j in o.Group:
                    joints.append(j)
                    if hasattr(j, "ObjectToGround") and j.ObjectToGround is not None:
                        grounded.add(j.ObjectToGround.Name)
            elif "Joint" in o.TypeId:
                joints.append(o)
        if hasattr(asm, "Joints"):
            for j in asm.Joints:
                if j not in joints:
                    joints.append(j)

        base_override = {json.dumps(base_link)}
        if base_override:
            base_name = _safe(base_override)
        elif grounded:
            # first grounded component
            g = next(c for c in components if c.Name in grounded)
            base_name = _safe(g.Label or g.Name)
        else:
            base_name = _safe(components[0].Label or components[0].Name)

        # Export meshes + build link map: component Name → link name
        link_of = {{}}
        mesh_files = {{}}
        used_names = set()
        for o in components:
            raw = _safe(o.Label or o.Name)
            link = raw
            n = 2
            while link in used_names:
                link = f"{{raw}}_{{n}}"
                n += 1
            used_names.add(link)
            link_of[o.Name] = link
            mesh = _mesh_from_obj(o)
            # Bake link placement into mesh so URDF link origin can be identity
            # relative to assembly — actually keep mesh in local coords and put
            # origin on joint; for simplicity export mesh in object local space
            # (Link placement handled via joint origins / world pose).
            fname = f"{{link}}.stl"
            fpath = os.path.join(out_dir, "meshes", fname)
            tmp = doc.addObject("Mesh::Feature", "CawUrdfMesh")
            tmp.Mesh = mesh
            Mesh.export([tmp], fpath)
            doc.removeObject(tmp.Name)
            mesh_files[link] = fname

        def mesh_uri(fname):
            if mesh_uri_mode == "relative":
                return f"meshes/{{fname}}"
            return f"package://{{package_name}}/meshes/{{fname}}"

        # World poses for components (mm → used for fixed joint origins vs base)
        world_pl = {{}}
        for o in components:
            world_pl[o.Name] = o.Placement

        lines = []
        lines.append('<?xml version="1.0"?>')
        lines.append(f'<robot name="{{robot_name}}">')
        lines.append("  <!-- Generated by FreeCAD MCP export_urdf (units: meters) -->")

        # Links
        for o in components:
            link = link_of[o.Name]
            fname = mesh_files[link]
            uri = mesh_uri(fname)
            lines.append(f'  <link name="{{link}}">')
            lines.append("    <visual>")
            lines.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
            lines.append("      <geometry>")
            lines.append(f'        <mesh filename="{{uri}}" scale="0.001 0.001 0.001"/>')
            lines.append("      </geometry>")
            lines.append("    </visual>")
            lines.append("    <collision>")
            lines.append('      <origin xyz="0 0 0" rpy="0 0 0"/>')
            lines.append("      <geometry>")
            lines.append(f'        <mesh filename="{{uri}}" scale="0.001 0.001 0.001"/>')
            lines.append("      </geometry>")
            lines.append("    </collision>")
            # crude inertial from bbox
            try:
                bb = o.Shape.BoundBox if hasattr(o, "Shape") and not o.Shape.isNull() else None
                if bb is None and hasattr(o, "LinkedObject") and o.LinkedObject is not None:
                    lo = o.LinkedObject
                    if hasattr(lo, "Shape") and not lo.Shape.isNull():
                        bb = lo.Shape.BoundBox
                if bb is not None:
                    mass = max(bb.XLength * bb.YLength * bb.ZLength / 1e9 * 500.0, 1e-3)  # density~0.5g/cm3 guess → kg
                    lines.append(f'    <inertial>')
                    lines.append(f'      <mass value="{{mass:.6f}}"/>')
                    lines.append('      <inertia ixx="1e-3" ixy="0" ixz="0" iyy="1e-3" iyz="0" izz="1e-3"/>')
                    lines.append("    </inertial>")
            except Exception:
                lines.append('    <inertial><mass value="0.1"/><inertia ixx="1e-3" ixy="0" ixz="0" iyy="1e-3" iyz="0" izz="1e-3"/></inertial>')
            lines.append("  </link>")

        # Joints from assembly
        emitted = set()
        joint_exports = []
        for j in joints:
            urdf_type, src_type = _joint_type_urdf(j)
            if src_type == "grounded" or (hasattr(j, "ObjectToGround") and j.ObjectToGround is not None):
                # grounded: no joint needed; that link is base
                continue
            a_name, b_name = _joint_refs(j)
            if not a_name or not b_name:
                continue
            if a_name not in link_of or b_name not in link_of:
                continue
            parent = link_of[a_name]
            child = link_of[b_name]
            # Prefer base as parent when possible
            if child == base_name and parent != base_name:
                parent, child = child, parent
                a_name, b_name = b_name, a_name
            jname = _safe(j.Label or j.Name)
            # Origin: child world relative to parent world
            try:
                rel = world_pl[a_name].inverse().multiply(world_pl[b_name])
            except Exception:
                rel = FreeCAD.Placement()
            xyz, rpy = _placement_xyz_rpy(rel)
            lines.append(f'  <joint name="{{jname}}" type="{{urdf_type}}">')
            lines.append(f'    <parent link="{{parent}}"/>')
            lines.append(f'    <child link="{{child}}"/>')
            lines.append(
                f'    <origin xyz="{{xyz[0]:.6f}} {{xyz[1]:.6f}} {{xyz[2]:.6f}}" '
                f'rpy="{{rpy[0]:.6f}} {{rpy[1]:.6f}} {{rpy[2]:.6f}}"/>'
            )
            if urdf_type in ("revolute", "continuous", "prismatic"):
                # Default Z axis in joint frame
                lines.append('    <axis xyz="0 0 1"/>')
            if urdf_type == "revolute":
                lines.append('    <limit lower="-3.1416" upper="3.1416" effort="10" velocity="1.0"/>')
            if urdf_type == "prismatic":
                lines.append('    <limit lower="-0.1" upper="0.1" effort="10" velocity="0.1"/>')
            lines.append("  </joint>")
            emitted.add(child)
            joint_exports.append({{"name": jname, "type": urdf_type, "parent": parent, "child": child, "source": src_type}})

        # Connect any dangling links to base with fixed joints (placement-relative)
        base_comp = None
        for o in components:
            if link_of[o.Name] == base_name:
                base_comp = o
                break
        if base_comp is None:
            base_comp = components[0]
            base_name = link_of[base_comp.Name]

        for o in components:
            link = link_of[o.Name]
            if link == base_name or link in emitted:
                continue
            try:
                rel = world_pl[base_comp.Name].inverse().multiply(world_pl[o.Name])
            except Exception:
                rel = FreeCAD.Placement()
            xyz, rpy = _placement_xyz_rpy(rel)
            jname = f"fixed_{{base_name}}_to_{{link}}"
            lines.append(f'  <joint name="{{jname}}" type="fixed">')
            lines.append(f'    <parent link="{{base_name}}"/>')
            lines.append(f'    <child link="{{link}}"/>')
            lines.append(
                f'    <origin xyz="{{xyz[0]:.6f}} {{xyz[1]:.6f}} {{xyz[2]:.6f}}" '
                f'rpy="{{rpy[0]:.6f}} {{rpy[1]:.6f}} {{rpy[2]:.6f}}"/>'
            )
            lines.append("  </joint>")
            joint_exports.append({{"name": jname, "type": "fixed", "parent": base_name, "child": link, "source": "auto_fixed"}})

        lines.append("</robot>")
        urdf_path = os.path.join(out_dir, f"{{robot_name}}.urdf")
        with open(urdf_path, "w", encoding="utf-8") as f:
            f.write("\\n".join(lines) + "\\n")

        meta = {{
            "robot_name": robot_name,
            "package_name": package_name,
            "base_link": base_name,
            "urdf": urdf_path,
            "meshes_dir": os.path.join(out_dir, "meshes"),
            "links": list(mesh_files.keys()),
            "joints": joint_exports,
            "units": "URDF meters; mesh files in mm with scale 0.001 on mesh tags",
            "mesh_uri": mesh_uri_mode,
        }}
        with open(os.path.join(out_dir, "caw-urdf.json"), "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

        __result__ = {{"ok": True, **meta}}
        """
    )
    return session.execute(code)


URDF_TOOLS: list[dict[str, Any]] = [
    {
        "name": "export_urdf",
        "description": (
            "Export the active FreeCAD assembly to a URDF package (robot.urdf + meshes/*.stl). "
            "Maps Fixed/Revolute/Slider(/Cylindrical≈continuous) joints; unconnected links get fixed "
            "joints to the grounded base. Lengths in URDF are meters (meshes stored in mm with scale=0.001). "
            "Use for ROS / Gazebo / Isaac after assemble + solve."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Output directory (default exports/urdf_robot)",
                    "default": "exports/urdf_robot",
                },
                "output_dir": {"type": "string"},
                "robot_name": {"type": "string", "default": "caw_robot"},
                "package_name": {
                    "type": "string",
                    "description": "ROS package name for package:// mesh URIs",
                },
                "assembly": {"type": "string"},
                "base_link": {"type": "string", "description": "Override base link (default: grounded component)"},
                "mesh_format": {"type": "string", "enum": ["stl"], "default": "stl"},
                "mesh_uri": {
                    "type": "string",
                    "enum": ["package", "relative"],
                    "default": "package",
                    "description": "package://name/meshes/... or relative meshes/...",
                },
                "linear_deflection": {"type": "number", "default": 0.1},
            }
        ),
        "handler": tool_export_urdf,
    },
]
