# Blender MCP for caw-agent

stdio MCP server that lets **caw-agent** drive **Blender** for organic mesh modeling (headphones, creature shells, robot fairings).

Uses **Content-Length** JSON-RPC framing (same as FreeCAD MCP / caw-agent).

## Features

| Area | Tools |
|------|--------|
| Session | `blender_status`, `new_file`, `open_file`, `save_file` |
| Objects | `list_objects`, `get_object`, `delete_object`, `duplicate_object`, `join_objects`, `set_transform`, `set_origin`, `shade_smooth` |
| Mesh | `add_mesh` (cube/sphere/cylinder/cone/torus/plane/monkey) |
| Edit mode | `mesh_info`, `edit_extrude`, `edit_inset`, `edit_bevel`, `edit_subdivide`, `edit_loop_cut`, `edit_bridge`, `edit_merge`, `edit_delete`, `mesh_decimate`, `mesh_symmetrize` |
| Curves | `create_curve`, `curve_set_bevel`, `curve_extrude`, `curve_to_mesh` |
| Sculpt-ish | `sculpt_remesh`, `sculpt_smooth`, `sculpt_inflate`, `sculpt_displace`, `sculpt_grab` |
| Modifiers | `add_modifier` (SUBSURF/SOLIDIFY/MIRROR/BEVEL/ARRAY/BOOLEAN), `apply_modifier`, `boolean` |
| Animation | `animation_setup`, `animation_set_frame`, `animation_timeline`, `animation_keyframe`, `animation_list`, `animation_clear`, `animation_parent`, `animation_play`, `animation_render` |
| Look-dev / render | `setup_lookdev`, `add_camera`, `add_light`, `set_material`, `set_hdri`, `setup_compositor`, `render_image`, `render`, `screenshot` |
| CAD handoff | `set_units`, `export_for_freecad`, `import_from_freecad` |
| I/O | `export_model` (glb/gltf/fbx/obj/stl/ply), `import_model` |
| Escape | `execute_python` |

## Backends (auto)

1. **bridge** — Blender GUI + `Caw Blender Bridge` addon on `127.0.0.1:54322` (recommended for live viewport)
2. **cmd** — spawn `blender --background` per call with a persistent session `.blend`

Override with `BLENDER_BACKEND=bridge|cmd|auto`.

## Setup

### 1. Install the GUI bridge (recommended)

```powershell
python mcp/blender/install_bridge.py
```

In Blender: **Edit → Preferences → Add-ons → enable "Caw Blender Bridge"**.  
Console should show: `CawBlenderBridge listening on 127.0.0.1:54322`.

### 2. Register with caw-agent

```text
/mcp install blender
```

Or copy `mcp/blender/mcp.json.example` into workspace `.mcp.json` (merge with freecad if needed).

Optional env:

| Variable | Meaning |
|----------|---------|
| `BLENDER_PATH` | Path to `blender.exe` / Blender binary |
| `BLENDER_BRIDGE_PORT` | Default `54322` |
| `BLENDER_TIMEOUT` | Per-call timeout seconds (default `120`) |
| `BLENDER_MCP_LOG` | Log file (stdout reserved for MCP) |

### 3. Run

```powershell
cargo run -p caw-agent -- --workdir .
```

In the TUI: `/mcp` → browse `blender` tools.

## Typical product shell

1. `add_mesh` / `create_curve` (+ `curve_set_bevel` for tubes)  
2. Organic: `sculpt_remesh` → `sculpt_inflate` / `sculpt_grab` → `sculpt_smooth`  
3. Detail: `edit_extrude` / `edit_inset` / `edit_bevel` / `mesh_decimate`  
4. `setup_lookdev` or `set_hdri` → `set_material` → `setup_compositor` → `render_image`  
5. Optional animation keyframes → `animation_render`  
6. `export_model` → FreeCAD for engineering  

## Animation

1. `animation_setup` (fps / frame range)
2. Pose via `set_transform` or values on `animation_keyframe`
3. `animation_keyframe` at each beat
4. Optional `animation_parent`
5. `animation_play` / `animation_render`

## Still renders

```text
setup_lookdev
# or: set_hdri path=C:/hdris/studio.exr strength=1.2
set_material name=… color=[0.9,0.9,0.92] roughness=0.35
setup_compositor glare=true
render_image path=renders/beauty.png engine=EEVEE resolution=[1920,1080]
```

`render_image` with `auto_setup=true` (default) creates camera+lights if missing.

## With FreeCAD (bidirectional)

Skill: `mcp/blender/skills/cad-blender-handoff` (discovered automatically; `/skill cad-blender-handoff`)

- **FreeCAD → Blender (render):** `export_for_blender` → Blender `import_from_freecad` → `render_image`
- **Blender → FreeCAD (assemble):** `set_units` mm → `export_for_freecad` → FreeCAD `import_from_blender`

Canonical unit: **mm**. Formats: STL/OBJ.

## Smoke test

```powershell
python mcp/blender/smoke_test.py
```
