#!/usr/bin/env python3
"""Install CawFreeCADBridge into the user's FreeCAD Mod directory."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def freecad_mod_dirs() -> list[Path]:
    dirs: list[Path] = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            dirs.append(Path(appdata) / "FreeCAD" / "Mod")
    elif sys.platform == "darwin":
        dirs.append(Path.home() / "Library" / "Application Support" / "FreeCAD" / "Mod")
    else:
        dirs.append(Path.home() / ".local" / "share" / "FreeCAD" / "Mod")
        dirs.append(Path.home() / ".FreeCAD" / "Mod")
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Install FreeCAD MCP GUI bridge addon")
    parser.add_argument("--mod-dir", type=Path, help="Override FreeCAD Mod directory")
    args = parser.parse_args()

    src = Path(__file__).resolve().parent / "freecad_addon" / "CawFreeCADBridge"
    if not src.is_dir():
        print(f"addon source missing: {src}", file=sys.stderr)
        return 1

    targets = [args.mod_dir] if args.mod_dir else freecad_mod_dirs()
    installed = []
    for mod in targets:
        if mod is None:
            continue
        mod.mkdir(parents=True, exist_ok=True)
        dest = mod / "CawFreeCADBridge"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        installed.append(dest)
        print(f"Installed: {dest}")

    if not installed:
        print("No FreeCAD Mod directory found. Pass --mod-dir.", file=sys.stderr)
        return 1

    print("\nNext: restart FreeCAD. Bridge listens on 127.0.0.1:54321")
    print("Then start caw-agent with mcp/freecad configured in .mcp.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
