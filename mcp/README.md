# MCP packs

Official packs for caw-agent. Install from the agent:

```text
/mcp install browser
/mcp install doc
```

That downloads `mcp/<name>` from this site into `~/.caw-agent/mcp/<name>/` and registers `~/.caw-agent/.mcp.json`.

You can also point at any GitHub repo that looks like a pack (`server.py` or `mcp.json`):

```text
/mcp install owner/repo
/mcp install https://github.com/owner/repo
```

| Pack | What it does |
|------|----------------|
| `browser` | Headless Chromium (Playwright) |
| `doc` | Extract text from documents |
| `image` | Cutout and basic image edits |
| `ocr` | Read text from images |
| `speech` | Speech to text |
| `freecad` | FreeCAD modeling and export |
| `blender` | Blender modeling and render |
