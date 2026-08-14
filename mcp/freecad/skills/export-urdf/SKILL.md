---
name: export-urdf
description: Export a FreeCAD assembly to URDF plus STL meshes for ROS, Gazebo, or Isaac. Use when the user asks for URDF, ROS robot description, Gazebo/Isaac import, or link/joint export from an assembly.
---

# Export assembly as URDF

Use `mcp__freecad__*` after the mechanism is assembled. Modeling steps: `/skill freecad-modeling`.

## Steps

1. `freecad_status`
2. Parts + `create_assembly` → `insert_component` (ground the base) → joints (`attach_lcs` / `create_lcs` + `create_joint`, or `mate_components`)
3. `list_assembly` then `solve_assembly`
4. `export_urdf` path=`exports/robot_name` robot_name=`robot_name` package_name=`robot_name`
5. Copy the folder into a ROS package (or point Isaac/Gazebo at the `.urdf`)

## Options

- `base_link` — force which link is root (default: grounded component)
- `mesh_uri=package` → `package://name/meshes/...` (ROS); `relative` → `meshes/...`
- `linear_deflection` — tessellation quality (smaller = finer STL)

## Limits

- Ball/Cylindrical joints are approximated (floating / continuous)
- Inertias are crude bbox estimates — replace for real control
- `App::Part` placement assemblies without Joint objects get **fixed** joints only (poses preserved)
