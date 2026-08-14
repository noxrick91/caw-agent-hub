# FreeCAD MCP for caw-agent

stdio MCP server that lets **caw-agent** drive FreeCAD for 3D modeling.

Uses **Content-Length** JSON-RPC framing (same as caw-agent’s MCP client).

## Features

| Area | Tools |
|------|--------|
| Session | `freecad_status`, `create_document`, `open_document`, `save_document`, `close_document`, `list_documents`, `recompute` |
| Project | `create_project`, `project_status`, `set_project_root`, `list_project_files`, `new_part_document`, `new_assembly_document`, `open_project_document`, `save_project_document` |
| Objects | `list_objects`, `get_object`, `delete_object`, `set_object_property`, `set_visibility`, `copy_object` |
| Primitives | `create_box`, `create_cylinder`, `create_sphere`, `create_cone`, `create_torus`, `create_wedge` |
| Part library | `list_part_library`, `generate_part_plate`, `generate_part_shaft`, `generate_part_flange`, `generate_part_bushing`, `generate_part_l_bracket`, `generate_part_spur_gear`, `generate_part_hex_bolt` |
| Shell / organic | `create_profile`, `loft`, `sweep`, `revolve`, `shell_solid`, `list_topology`, `fillet_smart` |
| Structure | `pattern_linear`, `pattern_polar`, `add_mounting_boss`, `add_rib` |
| Ops | `boolean_op`, `fillet`, `chamfer`, `transform`, `mirror` |
| Features | `extrude_profile`, `pocket` |
| Sketcher | `create_sketch`, `sketch_add_line`, `sketch_add_polyline`, `sketch_add_rectangle`, `sketch_add_circle`, `sketch_add_arc`, `sketch_add_point`, `sketch_add_slot`, `sketch_add_bspline`, `sketch_constraint`, `sketch_toggle_construction`, `sketch_external`, `sketch_fillet`, `sketch_info`, `sketch_delete`, `sketch_set_constraint`, `sketch_pad`, `sketch_pocket`, `sketch_revolve` |
| Assembly | `create_assembly`, `insert_component`, `ground_component`, `unground_component`, `create_lcs`, `create_joint`, `set_joint_offset`, `set_component_placement`, `list_assembly`, `solve_assembly`, `delete_joint` |
| Assembly+ | `attach_lcs`, `mate_components`, `check_interference`, `measure_clearance`, `check_motion_collisions`, `create_subassembly`, `assembly_bom` |
| Drawings | `create_drawing_page`, `add_drawing_view`, `add_drawing_dimension`, `export_drawing`, `create_schematic`, `list_drawings` |
| Animation | `animation_init`, `animation_add_keyframe`, `animation_list`, `animation_set_time`, `animation_play`, `animation_clear` |
| Blender handoff | `export_for_blender`, `import_from_blender` |
| Robotics | `export_urdf` (assembly → URDF + STL meshes) |
| I/O | `export_model` (STEP/STL/BREP/FCStd), `import_model`, `measure`, `screenshot` |
| Escape | `execute_python` |

### Project layout

`create_project` makes a workspace with:

```text
parts/  assemblies/  drawings/  exports/  animations/  docs/
.freecad-project.json
```

Set `FREECAD_PROJECT_ROOT` (or call `set_project_root`) so relative saves/exports land in the right folders.

### Drawings vs 原理图

- **TechDraw** (`create_drawing_page` + `add_drawing_view`) — manufacturing / engineering views from 3D.
- **Schematic** (`create_schematic`) — Draft 2D node/edge diagram for mechanism or block diagrams.

### Animation

1. `animation_init` (fps / duration)
2. `animation_add_keyframe` on a part (`kind=placement`) or joint (`kind=joint`, drive `Offset2`)
3. `animation_set_time` to scrub, or `animation_play` (`capture=true` writes PNGs under `animations/`, needs GUI bridge)

### Assembly notes

- **FreeCAD 1.0+ Assembly workbench** → full kinematics (Fixed / Revolute / Cylindrical / Slider / Ball / Distance / Parallel / …).
- If Assembly WB is missing, `create_assembly` falls back to `App::Part` + `App::Link` **placement composition** (no solver).
- Recommended mate workflow:
  1. `list_topology` → `attach_lcs` on mate faces/holes, **or** `mate_components` (coaxial / coincident / offset)
  2. `create_joint` with `lcs_a` / `lcs_b` → `solve_assembly`
- Validate: `check_interference` / `measure_clearance`, then `check_motion_collisions` while driving a joint.
- Modules: `create_subassembly` for earcup/leg packs; `assembly_bom` for instance list.
- Drive motion with `set_joint_offset` (`Offset2` rotation/translation) then solve.

### Sketch workflow (Sketcher)

1. `create_sketch` (`plane=xy|xz|yz`, or `support` + `face` on a solid)
2. Add geometry: `sketch_add_rectangle` / `sketch_add_circle` / `sketch_add_line` / `sketch_add_polyline` / `sketch_add_arc` / `sketch_add_slot` / `sketch_add_bspline`
3. Constrain: `sketch_constraint` (`coincident`, `horizontal`, `distance`, `radius`, …). `geo1`/`geo2` are 0-based ids from the add tools, or `origin` / `x` / `y`
4. `sketch_info` — check DOF / `fully_constrained`; `sketch_set_constraint` to change a dimension
5. `sketch_pad` / `sketch_pocket` / `sketch_revolve` (PartDesign, with Part fallback)

`extrude_profile` remains a no-sketch shortcut for a simple rectangle/circle pad.

### Thin-wall / product shell workflow

1. `create_profile` (polyline or bspline sections) → `loft` / `sweep` / `revolve`
2. `list_topology` → `shell_solid` (open bottom face) → `fillet_smart`
3. `add_mounting_boss` / `add_rib` / `pattern_polar` for posts & vents
4. Assemble + interference / motion checks as above
5. `export_model` STEP/STL

### Blender handoff (render ↔ assemble)

Skill: `mcp/freecad/skills/cad-blender-handoff` · units **mm** · formats **STL/OBJ**

- **→ Blender render:** `export_for_blender` → Blender `import_from_freecad` → `render_image`
- **← Blender shell:** Blender `export_for_freecad` → `import_from_blender` → assembly tools

### URDF export (ROS / sim)

After assembling with joints (and preferably grounding a base):

```text
export_urdf path=exports/my_robot robot_name=my_robot
```

Writes `exports/my_robot/my_robot.urdf` + `meshes/*.stl` (+ `caw-urdf.json`).  
Joint map: Fixed→fixed, Revolute→revolute, Slider→prismatic, Cylindrical≈continuous; other links auto-fixed to base.  
URDF lengths are **meters**; STL files stay in **mm** with `scale="0.001 …"` on mesh tags.

## Backends (auto)

1. **bridge** — FreeCAD GUI + `CawFreeCADBridge` addon on `127.0.0.1:54321` (recommended)
2. **inprocess** — server started with FreeCAD’s `python.exe` (`import FreeCAD` works)
3. **cmd** — spawn `FreeCADCmd` per call with a persistent session file

Override with `FREECAD_BACKEND=bridge|inprocess|cmd|auto`.

## Setup

### 1. Install the GUI bridge (recommended)

```powershell
python mcp/freecad/install_bridge.py
```

Restart FreeCAD. Report view should show: `CawFreeCADBridge listening on 127.0.0.1:54321`.

### 2. Point caw-agent at the server

Copy example config into the workspace root (or merge), **or** install into the user home via caw-agent:

```text
/mcp install freecad
```

This copies the pack to `~/.caw-agent/mcp/freecad/` and registers it in `~/.caw-agent/.mcp.json`.

Manual copy:

```powershell
Copy-Item mcp/freecad/mcp.json.example .mcp.json
```

Or set FreeCAD’s Python explicitly for in-process mode:

```json
{
  "mcpServers": {
    "freecad": {
      "command": "C:\\Program Files\\FreeCAD 1.0\\bin\\python.exe",
      "args": ["mcp/freecad/server.py"],
      "env": {
        "FREECAD_BACKEND": "inprocess",
        "FREECAD_MCP_LOG": ".caw-agent/freecad-mcp.log"
      }
    }
  }
}
```

Optional env:

| Variable | Meaning |
|----------|---------|
| `FREECADCMD` | Path to `FreeCADCmd.exe` |
| `FREECAD_PYTHON` | Path to FreeCAD’s Python |
| `FREECAD_BRIDGE_PORT` | Default `54321` |
| `FREECAD_TIMEOUT` | Per-call timeout seconds (default `120`) |
| `FREECAD_MCP_LOG` | Log file (stdout is reserved for MCP) |
| `FREECAD_PROJECT_ROOT` | Default project folder for relative paths |

### 3. Run caw-agent

```powershell
cargo run -p caw-agent -- --workdir .
```

In the TUI: `/mcp` should list `mcp__freecad__*` tools.

### 4. Skills

Pack skills live in `mcp/freecad/skills/` (`freecad-modeling`, `export-urdf`, `cad-blender-handoff`). caw-agent discovers them automatically — no copy into workspace `skills/`.

## Quick test without FreeCAD GUI

Protocol smoke test (no FreeCAD required for initialize/tools/list):

```powershell
python mcp/freecad/smoke_test.py
```

With FreeCAD bridge running:

> create a 20×20×10 box, cut a cylinder hole, fillet, export bracket.step

## Architecture

```text
caw-agent  --stdio MCP-->  server.py  --auto-->  bridge | inprocess | FreeCADCmd
                                ^
                         Content-Length JSON-RPC
```

## Notes

- `screenshot` needs the GUI bridge.
- `execute_python` can run any FreeCAD API; only use in trusted workspaces.
- Headless `cmd` mode is slower (process per call) but works without the GUI.
