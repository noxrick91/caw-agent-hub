---
name: freecad-modeling
description: Drive FreeCAD through mcp__freecad__* for parametric solids, Sketcher, product shells, assemblies, drawings, animation, and STEP/STL export. Use when the user asks to model a part, sketch, pad/pocket, assemble, mate, interfere, or export CAD.
---

# FreeCAD modeling

Use `mcp__freecad__*`. Prefer structured tools over `execute_python` unless you need custom geometry.

Same MCP server is one-at-a-time. Reads (`freecad_status`, `list_*`, `measure`, `sketch_info`) can share a wave with **other** packs, not with another FreeCAD write.

## When vs Blender

- **FreeCAD**: parametric solids, sketches, manufacturing features, mates, interference, STEP.
- **Blender**: organic mesh, sculpt, curves, beauty render, animation.
- Pipeline: `/skill cad-blender-handoff`. Robotics: `/skill export-urdf`.

## Session / project

1. `freecad_status` — prefer the GUI **bridge**.
2. Optional `create_project` (makes `parts/ assemblies/ drawings/ exports/ …`) then `new_part_document` / `new_assembly_document`.
3. Or `create_document` / `open_document`. Save with `save_document` / `save_project_document`.

## Typical hard-surface part

Prefer a sketch when the profile matters:

1. `create_sketch` (`plane=xy|xz|yz`, or `support` + `face` 1-based from `list_topology`)
2. Geometry (sketch-plane **[x, y] mm**):
   - `sketch_add_rectangle` / `sketch_add_circle` / `sketch_add_slot`
   - `sketch_add_line` / `sketch_add_polyline` / `sketch_add_arc` / `sketch_add_point` / `sketch_add_bspline`
   - `construction=true` for references; `sketch_toggle_construction` later
3. `sketch_constraint` (`coincident|horizontal|vertical|parallel|perpendicular|tangent|equal|symmetric|block|distance|distance_x|distance_y|radius|diameter|angle|point_on_object`)
   - `geo1`/`geo2` = 0-based ids from add tools, or `origin` / `x` / `y`
   - `pos1`/`pos2` = `start` / `end` / `center` / `edge`
   - `value` is mm, or **degrees** for `angle`
4. `sketch_external` to project an edge/face; `sketch_fillet` for 2D corners; `sketch_delete` / `sketch_set_constraint` to edit
5. `sketch_info` — aim for `fully_constrained`
6. `sketch_pad` / `sketch_pocket` (`through_all`) / `sketch_revolve` (`axis=x|y`)
7. Or skip sketch: primitives (`create_box` …) / `list_part_library` / `generate_part_*` / `extrude_profile`
8. `boolean_op` → `fillet` / `chamfer` / `transform` / `mirror`
9. `measure` → `export_model` (STEP/STL)

## Product shell (headphones / armor / fairings)

1. `create_profile` section `points` (`kind=polyline|bspline`, `closed=true`)
2. `loft` / `sweep` / `revolve`
3. `list_topology` → `shell_solid` (`thickness`, `open_faces`)
4. `fillet_smart` (`faces` / `edges` / `exclude_edges`)
5. `add_mounting_boss` (`fuse_with`), `add_rib`, `pattern_linear` / `pattern_polar`
6. Optional `mirror` for left/right. Then `export_model`.

## Assembly (FreeCAD 1.0+)

1. Model or import parts.
2. Optional `create_subassembly` for modules.
3. `create_assembly` → `insert_component` (`ground=true` on the frame) — or `ground_component` later.
4. Mate: `list_topology` → `attach_lcs` (`face_center` / `hole_axis`) → `create_joint`  
   or `mate_components` (`coaxial` / `coincident` / `offset`)
5. `solve_assembly`. Validate: `check_interference`, `measure_clearance`.
6. Motion: `set_joint_offset` → `check_motion_collisions`. Optional `animation_*`.
7. `assembly_bom` → `export_model`.

If Assembly WB is missing, `create_assembly(mode=part)` is links + `set_component_placement` (no kinematic solve).

## Drawings / animation

- Engineering views: `create_drawing_page` → `add_drawing_view` → `add_drawing_dimension` → `export_drawing`. `list_drawings` to inspect.
- Block schematic: `create_schematic` (`nodes` + `edges`).
- Motion film: `animation_init` → `animation_add_keyframe` (`kind=placement|joint`) → `animation_set_time` / `animation_play` (`capture=true` needs GUI bridge).

## Conventions

- Units: millimetres unless the document says otherwise.
- Object `name` is FreeCAD internal Name — reuse it.
- Face/edge indices from `list_topology` are **1-based**. Sketch geo ids are **0-based**.
- After boolean/fillet/shell, originals may be removed; use the returned `name`.
- Escape hatch: `execute_python` and set `__result__`.

## Example: sketched plate with hole

1. `create_sketch` plane=`xy` name=`PlateSketch`
2. `sketch_add_rectangle` sketch=`PlateSketch` width=40 height=30 lock_origin=`true`
3. `sketch_add_circle` sketch=`PlateSketch` center=`[20,15]` radius=4
4. `sketch_info` → `sketch_pad` length=4 → `export_model`
