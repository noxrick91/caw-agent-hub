---
name: blender-modeling
description: Drive Blender through mcp__blender__* for organic mesh, edit/sculpt, curves, lookdev, animation, and renders. Use when the user asks to model a mesh, sculpt, bevel a tube, keyframe, or beauty-render in Blender.
---

# Blender modeling

Use `mcp__blender__*`. Prefer structured tools over `execute_python` unless you need niche ops.

Same MCP server is one-at-a-time.

## When vs FreeCAD

- **Blender**: organic shapes, curves, edit/sculpt, animation, beauty renders.
- **FreeCAD**: parametric solids, manufacturing features, mates, interference, STEP.
- Pipeline: `/skill cad-blender-handoff`. Set `set_units` `mode=mm` early if the mesh will go to CAD.

## Session

1. `blender_status` — prefer the GUI **bridge**.
2. `new_file` / `open_file` / `save_file` as needed.
3. `list_objects` / `get_object` before editing; `delete_object` / `duplicate_object` / `join_objects` to manage the scene.

## Shell / fairing workflow

1. Block-out: `add_mesh` (cube/uv_sphere/cylinder/cone/torus/plane/monkey) or `create_curve` + `curve_set_bevel` / `curve_extrude` / `curve_to_mesh`
2. Place: `set_transform`, `set_origin`
3. Organic: `sculpt_remesh` → `sculpt_inflate` / `sculpt_grab` / `sculpt_displace` → `sculpt_smooth`
4. Detail (`mesh_info` first; **0-based** vert/edge/face ids):
   - `edit_extrude` / `edit_inset` / `edit_bevel` / `edit_subdivide` / `edit_loop_cut` / `edit_bridge`
   - `edit_merge` / `edit_delete` / `mesh_decimate` / `mesh_symmetrize`
5. Modifiers: `add_modifier` (`SUBSURF` / `SOLIDIFY` / `MIRROR` / `BEVEL` / `ARRAY` / `BOOLEAN`) → `apply_modifier` or `boolean`
6. `shade_smooth`
7. Lookdev: `setup_lookdev` or `add_camera` / `add_light` / `set_hdri` → `set_material` → optional `setup_compositor`
8. `render_image` path=`renders/beauty.png` (or `render` / `screenshot`)
9. `export_model` (glb/gltf/fbx/obj/stl/ply) for CAD handoff — prefer `export_for_freecad` when going to FreeCAD

## Animation

1. `animation_setup` fps=24 frame_start=1 frame_end=72
2. Pose with `set_transform` then `animation_keyframe` (or pass values on the keyframe call)
3. `animation_parent` for hinges/limbs
4. Inspect: `animation_timeline` / `animation_list` / `animation_set_frame`
5. `animation_play` / `animation_render`; `animation_clear` to wipe keys

## Conventions

- Face/edge/vert **indices are 0-based** (`mesh_info`).
- Object `name` is Blender's object name — reuse it.
- Units are scene units; `set_units` `mm` before CAD export.
- Interactive brush sculpting is approximated (`sculpt_grab` / inflate / displace).

## Example: soft earcup

1. `add_mesh` type=uv_sphere name=EarCup
2. `sculpt_remesh` voxel_size=0.04 → `sculpt_inflate` amount=0.02 → `sculpt_smooth`
3. `edit_inset` thickness=0.05 → `edit_extrude` amount=-0.08
4. `set_material` color=`[0.15,0.15,0.16]` roughness=0.55
5. `setup_lookdev` → `render_image` path=`renders/earcup.png`
6. `export_for_freecad` path=`exports/earcup.stl` (or `export_model`)
