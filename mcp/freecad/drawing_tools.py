"""TechDraw / schematic (原理图·工程图) tools for FreeCAD MCP."""

from __future__ import annotations

import os
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


def _unique_name(preferred: str | None, fallback: str) -> str:
    name = (preferred or fallback).strip() or fallback
    safe = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in name)
    return safe or fallback


_TD_HELPERS = r'''
def _td_find(doc, name):
    if not name:
        return None
    o = doc.getObject(name)
    if o is not None:
        return o
    for obj in doc.Objects:
        if obj.Label == name:
            return obj
    raise RuntimeError(f"object not found: {name}")

def _td_ensure_import():
    try:
        import TechDraw
        return TechDraw
    except Exception as e:
        raise RuntimeError(f"TechDraw workbench unavailable: {e}")
'''


def tool_create_drawing_page(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    name = _unique_name(args.get("name"), "Page")
    template = args.get("template")  # optional path to .svg template
    code = textwrap.dedent(
        f"""
        {_TD_HELPERS}
        TD = _td_ensure_import()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        page = doc.addObject("TechDraw::DrawPage", {name!r})
        page.Label = {args.get("label") or name!r}
        tmpl_path = {template!r}
        template_obj = None
        if tmpl_path:
            template_obj = doc.addObject("TechDraw::DrawSVGTemplate", {name!r} + "_Template")
            template_obj.Template = tmpl_path
            page.Template = template_obj
        else:
            # Prefer bundled A4 template when available
            candidates = []
            try:
                import FreeCAD as FC
                home = FC.getResourceDir()
                candidates.append(home + "Mod/TechDraw/Templates/A4_LandscapeTD.svg")
                candidates.append(home + "Mod/TechDraw/Templates/A4_Portrait_blank.svg")
            except Exception:
                pass
            import os
            for c in candidates:
                if c and os.path.isfile(c):
                    template_obj = doc.addObject("TechDraw::DrawSVGTemplate", {name!r} + "_Template")
                    template_obj.Template = c
                    page.Template = template_obj
                    tmpl_path = c
                    break
        doc.recompute()
        __result__ = {{
            "ok": True,
            "page": page.Name,
            "label": page.Label,
            "template": tmpl_path,
        }}
        """
    )
    return session.execute(code)


def tool_add_drawing_view(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    page = args.get("page")
    source = args["source"]
    name = _unique_name(args.get("name"), "View")
    direction = args.get("direction") or "front"
    scale = float(args.get("scale") or 1.0)
    x = float(args.get("x") or 100)
    y = float(args.get("y") or 100)
    # Map common view names to FreeCAD Direction vectors
    dirs = {
        "front": (0, -1, 0),
        "rear": (0, 1, 0),
        "top": (0, 0, 1),
        "bottom": (0, 0, -1),
        "right": (1, 0, 0),
        "left": (-1, 0, 0),
        "isometric": (1, 1, 1),
    }
    if isinstance(direction, (list, tuple)) and len(direction) >= 3:
        dvec = (float(direction[0]), float(direction[1]), float(direction[2]))
    else:
        dvec = dirs.get(str(direction).lower(), (0, -1, 0))

    code = textwrap.dedent(
        f"""
        {_TD_HELPERS}
        _td_ensure_import()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        src = _td_find(doc, {source!r})
        page_name = {page!r}
        page = None
        if page_name:
            page = _td_find(doc, page_name)
        else:
            for o in doc.Objects:
                if o.TypeId == "TechDraw::DrawPage":
                    page = o
                    break
        if page is None:
            raise RuntimeError("no TechDraw page; call create_drawing_page first")
        view = doc.addObject("TechDraw::DrawViewPart", {name!r})
        view.Label = {args.get("label") or name!r}
        view.Source = [src]
        view.Direction = FreeCAD.Vector{dvec}
        view.Scale = {scale}
        view.X = {x}
        view.Y = {y}
        page.addView(view)
        doc.recompute()
        __result__ = {{
            "ok": True,
            "view": view.Name,
            "page": page.Name,
            "source": src.Name,
            "direction": {list(dvec)!r},
            "scale": {scale},
        }}
        """
    )
    return session.execute(code)


def tool_add_drawing_dimension(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    view = args["view"]
    kind = (args.get("kind") or "length").lower()
    refs = args.get("refs") or args.get("edges") or []
    if isinstance(refs, str):
        refs = [refs]
    name = _unique_name(args.get("name"), "Dim")
    code = textwrap.dedent(
        f"""
        {_TD_HELPERS}
        _td_ensure_import()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        view = _td_find(doc, {view!r})
        page = None
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawPage" and view in getattr(o, "Views", []):
                page = o
                break
        if page is None:
            # Fallback: first page
            for o in doc.Objects:
                if o.TypeId == "TechDraw::DrawPage":
                    page = o
                    break
        if page is None:
            raise RuntimeError("no TechDraw page found for view")
        refs = {list(refs)!r}
        kind = {kind!r}
        if kind in ("length", "distance", "horizontal", "vertical"):
            dim = doc.addObject("TechDraw::DrawViewDimension", {name!r})
            dim.Type = "Distance"
            if kind == "horizontal":
                try:
                    dim.Type = "DistanceX"
                except Exception:
                    pass
            if kind == "vertical":
                try:
                    dim.Type = "DistanceY"
                except Exception:
                    pass
        elif kind in ("radius", "diameter"):
            dim = doc.addObject("TechDraw::DrawViewDimension", {name!r})
            dim.Type = "Radius" if kind == "radius" else "Diameter"
        elif kind == "angle":
            dim = doc.addObject("TechDraw::DrawViewDimension", {name!r})
            dim.Type = "Angle"
        else:
            raise RuntimeError(f"unknown dimension kind: {{kind}}")
        dim.Refs2D = [(view, tuple(refs))] if refs else []
        try:
            dim.References2D = [(view, tuple(refs))] if refs else []
        except Exception:
            pass
        page.addView(dim)
        doc.recompute()
        __result__ = {{"ok": True, "dimension": dim.Name, "view": view.Name, "kind": kind, "refs": refs}}
        """
    )
    return session.execute(code)


def tool_export_drawing(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    page = args.get("page")
    path = args["path"]
    fmt = (args.get("format") or Path(path).suffix.lstrip(".") or "svg").lower()
    root = args.get("project_root") or os.environ.get("FREECAD_PROJECT_ROOT") or ""
    out = Path(path)
    if not out.is_absolute():
        base = Path(root).expanduser().resolve() if root else Path.cwd().resolve()
        # Prefer drawings/ when relative
        if (base / "drawings").is_dir() and "/" not in path.replace("\\", "/") and "\\" not in path:
            out = base / "drawings" / path
        else:
            out = base / path
    out.parent.mkdir(parents=True, exist_ok=True)
    code = textwrap.dedent(
        f"""
        {_TD_HELPERS}
        TD = _td_ensure_import()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        page_name = {page!r}
        page = _td_find(doc, page_name) if page_name else None
        if page is None:
            for o in doc.Objects:
                if o.TypeId == "TechDraw::DrawPage":
                    page = o
                    break
        if page is None:
            raise RuntimeError("no TechDraw page")
        path = {str(out)!r}
        fmt = {fmt!r}
        doc.recompute()
        if fmt in ("svg",):
            page.exportSvg(path)
        elif fmt in ("dxf",):
            # FreeCAD 0.21+/1.0 TechDraw DXF export
            try:
                import TechDraw
                TechDraw.writeDXFPage(page, path)
            except Exception:
                page.exportSvg(path.replace(".dxf", ".svg"))
                path = path.replace(".dxf", ".svg")
                fmt = "svg"
        elif fmt in ("pdf",):
            try:
                import TechDrawGui
                TechDrawGui.exportPageAsPdf(page, path)
            except Exception as e:
                # Fallback SVG
                alt = path.rsplit(".", 1)[0] + ".svg"
                page.exportSvg(alt)
                path = alt
                fmt = "svg"
                __result__ = {{"ok": True, "path": path, "format": fmt, "page": page.Name, "warning": str(e)}}
                raise SystemExit  # unreachable — use if/else instead
        else:
            page.exportSvg(path if path.lower().endswith(".svg") else path + ".svg")
            fmt = "svg"
        __result__ = {{"ok": True, "path": path, "format": fmt, "page": page.Name}}
        """
    )
    # Fix the awkward SystemExit in pdf branch — rewrite cleaner
    code = textwrap.dedent(
        f"""
        {_TD_HELPERS}
        TD = _td_ensure_import()
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        page_name = {page!r}
        page = _td_find(doc, page_name) if page_name else None
        if page is None:
            for o in doc.Objects:
                if o.TypeId == "TechDraw::DrawPage":
                    page = o
                    break
        if page is None:
            raise RuntimeError("no TechDraw page")
        path = {str(out)!r}
        fmt = {fmt!r}
        warning = None
        doc.recompute()
        if fmt == "svg":
            page.exportSvg(path)
        elif fmt == "dxf":
            try:
                import TechDraw
                TechDraw.writeDXFPage(page, path)
            except Exception as e:
                warning = str(e)
                path = path.rsplit(".", 1)[0] + ".svg"
                page.exportSvg(path)
                fmt = "svg"
        elif fmt == "pdf":
            try:
                import TechDrawGui
                TechDrawGui.exportPageAsPdf(page, path)
            except Exception as e:
                warning = str(e)
                path = path.rsplit(".", 1)[0] + ".svg"
                page.exportSvg(path)
                fmt = "svg"
        else:
            if not path.lower().endswith(".svg"):
                path = path + ".svg"
            page.exportSvg(path)
            fmt = "svg"
        __result__ = {{"ok": True, "path": path, "format": fmt, "page": page.Name, "warning": warning}}
        """
    )
    return session.execute(code)


def tool_create_schematic(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    """Create a 2D Draft schematic (原理图) with labeled nodes and connection lines."""
    name = _unique_name(args.get("name"), "Schematic")
    nodes = args.get("nodes") or []
    edges = args.get("edges") or args.get("connections") or []
    if not isinstance(nodes, list):
        raise FreeCADError("nodes must be a list of {id,x,y,label?}")
    code = textwrap.dedent(
        f"""
        import Draft
        doc = FreeCAD.ActiveDocument
        if doc is None:
            doc = FreeCAD.newDocument("Unnamed")
        try:
            grp = doc.addObject("App::DocumentObjectGroup", {name!r})
        except Exception:
            grp = doc.addObject("App::Part", {name!r})
        grp.Label = {args.get("label") or name!r}
        nodes = {nodes!r}
        edges = {edges!r}
        node_map = {{}}
        created = []
        for n in nodes:
            nid = str(n.get("id") or n.get("name") or f"N{{len(node_map)}}")
            x = float(n.get("x", 0))
            y = float(n.get("y", 0))
            label = str(n.get("label") or nid)
            # Marker: small circle + text
            circ = Draft.make_circle(float(n.get("radius") or 3.0))
            circ.Label = f"{{nid}}_mark"
            circ.Placement.Base = FreeCAD.Vector(x, y, 0)
            txt = Draft.make_text([label], FreeCAD.Vector(x + 4, y + 2, 0))
            txt.Label = f"{{nid}}_label"
            try:
                txt.ViewObject.FontSize = float(n.get("font_size") or 8)
            except Exception:
                pass
            node_map[nid] = {{"x": x, "y": y, "mark": circ.Name, "text": txt.Name}}
            for o in (circ, txt):
                try:
                    grp.addObject(o)
                except Exception:
                    pass
            created.append(nid)
        for e in edges:
            a = str(e.get("from") or e.get("a") or "")
            b = str(e.get("to") or e.get("b") or "")
            if a not in node_map or b not in node_map:
                continue
            pa = node_map[a]
            pb = node_map[b]
            pts = [FreeCAD.Vector(pa["x"], pa["y"], 0), FreeCAD.Vector(pb["x"], pb["y"], 0)]
            wire = Draft.make_wire(pts, closed=False)
            wire.Label = e.get("label") or f"{{a}}_{{b}}"
            try:
                grp.addObject(wire)
            except Exception:
                pass
        doc.recompute()
        __result__ = {{
            "ok": True,
            "group": grp.Name,
            "nodes": created,
            "edges": len(edges),
            "kind": "schematic",
            "note": "Draft 2D schematic (原理图). For manufacturing views use create_drawing_page + add_drawing_view.",
        }}
        """
    )
    return session.execute(code)


def tool_list_drawings(session: FreeCADSession, args: dict[str, Any]) -> dict[str, Any]:
    del args
    code = textwrap.dedent(
        """
        doc = FreeCAD.ActiveDocument
        if doc is None:
            raise RuntimeError("no active document")
        pages = []
        for o in doc.Objects:
            if o.TypeId == "TechDraw::DrawPage":
                views = []
                for v in getattr(o, "Views", []) or []:
                    views.append({
                        "name": v.Name,
                        "label": v.Label,
                        "type": v.TypeId,
                    })
                pages.append({
                    "name": o.Name,
                    "label": o.Label,
                    "views": views,
                })
        groups = []
        for o in doc.Objects:
            if "Schematic" in (o.Label or "") or "schematic" in (o.Name or "").lower():
                groups.append({"name": o.Name, "label": o.Label, "type": o.TypeId})
        __result__ = {"ok": True, "pages": pages, "schematics": groups}
        """
    )
    return session.execute(code)


DRAWING_TOOLS: list[dict[str, Any]] = [
    {
        "name": "create_drawing_page",
        "description": (
            "Create a TechDraw page (工程图) with optional SVG template. "
            "Use with add_drawing_view for orthographic/isometric views of parts."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "template": {"type": "string", "description": "Optional path to TechDraw SVG template"},
            }
        ),
        "handler": tool_create_drawing_page,
    },
    {
        "name": "add_drawing_view",
        "description": (
            "Add a TechDraw projected view of a 3D object onto a page. "
            "direction: front|top|right|left|rear|bottom|isometric or [x,y,z]."
        ),
        "inputSchema": _schema(
            {
                "source": {"type": "string", "description": "3D object name"},
                "page": {"type": "string"},
                "name": {"type": "string"},
                "label": {"type": "string"},
                "direction": {},
                "scale": {"type": "number", "default": 1},
                "x": {"type": "number", "default": 100, "description": "View position X on page"},
                "y": {"type": "number", "default": 100, "description": "View position Y on page"},
            },
            ["source"],
        ),
        "handler": tool_add_drawing_view,
    },
    {
        "name": "add_drawing_dimension",
        "description": "Add a TechDraw dimension on a view (length/radius/diameter/angle). refs = edge/vertex names.",
        "inputSchema": _schema(
            {
                "view": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": ["length", "distance", "horizontal", "vertical", "radius", "diameter", "angle"],
                    "default": "length",
                },
                "refs": {"type": "array", "items": {"type": "string"}},
                "edges": {"type": "array", "items": {"type": "string"}},
                "name": {"type": "string"},
            },
            ["view"],
        ),
        "handler": tool_add_drawing_dimension,
    },
    {
        "name": "export_drawing",
        "description": "Export a TechDraw page to SVG/DXF/PDF (PDF needs GUI). Relative paths go under project drawings/.",
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "page": {"type": "string"},
                "format": {"type": "string", "enum": ["svg", "dxf", "pdf"]},
                "project_root": {"type": "string"},
            },
            ["path"],
        ),
        "handler": tool_export_drawing,
    },
    {
        "name": "create_schematic",
        "description": (
            "Create a 2D Draft schematic / 原理图: nodes[{id,x,y,label}] and "
            "edges[{from,to,label}]. For manufacturing drawings use TechDraw tools instead."
        ),
        "inputSchema": _schema(
            {
                "name": {"type": "string"},
                "label": {"type": "string"},
                "nodes": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "[{id, x, y, label?, radius?, font_size?}]",
                },
                "edges": {
                    "type": "array",
                    "items": {"type": "object"},
                    "description": "[{from, to, label?}] or [{a,b}]",
                },
                "connections": {"type": "array", "items": {"type": "object"}},
            }
        ),
        "handler": tool_create_schematic,
    },
    {
        "name": "list_drawings",
        "description": "List TechDraw pages/views and schematic groups in the active document.",
        "inputSchema": _schema({}),
        "handler": tool_list_drawings,
    },
]
