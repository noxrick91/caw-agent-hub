---
name: cad-blender-handoff
description: Bidirectional FreeCAD ↔ Blender exchange for render and assembly workflows. Use when handing a CAD solid to Blender for beauty render, or a Blender shell to FreeCAD for mates, interference, or STEP.
---

# FreeCAD ↔ Blender handoff

Both directions are supported. **Canonical unit is millimeters.**

Keep a **shared workdir** so both MCPs see the same `exports/` paths. Different servers can run in one wave; do not overlap the same `path` (export then import is two turns, or sequential calls).

## Convention

| App | Units |
|-----|--------|
| FreeCAD | mm (native) |
| Blender | `set_units` mode=`mm` so 1 BU = 1 mm |

Formats: **STL** (preferred) or **OBJ**. STEP stays FreeCAD-internal (Blender will not import it without extra addons). Both are Z-up — no STL flip.

## A) FreeCAD → Blender (CAD → render)

1. Finish the part/assembly in FreeCAD.
2. `mcp__freecad__export_for_blender` path=`exports/part.stl` (optional `objects=[...]` for multi-body)
3. `mcp__blender__import_from_freecad` path=`exports/part.stl`
4. Optional `set_material` / `set_hdri` / `setup_lookdev`
5. `mcp__blender__render_image` path=`renders/beauty.png`

## B) Blender → FreeCAD (shell → assemble)

1. Blender: `set_units` mode=`mm` **early**
2. Model the shell (mesh / curve / sculpt)
3. `mcp__blender__export_for_freecad` path=`exports/shell.stl`
4. `mcp__freecad__import_from_blender` path=`exports/shell.stl` scale=`1`
5. `create_assembly` / `insert_component` / `mate_components` / `check_interference`

If Blender stayed in **meters** and you used a raw export, FreeCAD import may need `scale=1000`. Prefer `export_for_freecad` so scale is already mm.

## Checklist

- [ ] Same path visible to both apps
- [ ] After import, `measure` / bbox sanity (earcup ~50–80 mm, not 0.05 m)
- [ ] Named parts: export `objects=[...]` when multi-body

## Do not

- Expect editable FreeCAD feature history from a Blender mesh (mesh-in is a dumb solid/mesh).
- Use GLB as the CAD assembly source of truth — fine for viz, not for mates.
