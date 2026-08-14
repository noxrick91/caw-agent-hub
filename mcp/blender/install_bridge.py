#!/usr/bin/env python3
"""Install CawBlenderBridge into Blender's addons directory."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


def blender_addon_dirs() -> list[Path]:
    dirs: list[Path] = []
    home = Path.home()
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            base = Path(appdata) / "Blender Foundation" / "Blender"
            if base.is_dir():
                for ver in sorted(base.iterdir(), reverse=True):
                    scripts = ver / "scripts" / "addons"
                    if ver.is_dir():
                        dirs.append(scripts)
            else:
                dirs.append(base / "4.2" / "scripts" / "addons")
    elif sys.platform == "darwin":
        base = home / "Library" / "Application Support" / "Blender"
        if base.is_dir():
            for ver in sorted(base.iterdir(), reverse=True):
                if ver.is_dir():
                    dirs.append(ver / "scripts" / "addons")
    else:
        base = home / ".config" / "blender"
        if base.is_dir():
            for ver in sorted(base.iterdir(), reverse=True):
                if ver.is_dir():
                    dirs.append(ver / "scripts" / "addons")
    return dirs


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Blender MCP GUI bridge addon")
    parser.add_argument("--addons-dir", type=Path, help="Override Blender scripts/addons directory")
    args = parser.parse_args()

    src = Path(__file__).resolve().parent / "blender_addon" / "caw_blender_bridge"
    if not src.is_dir():
        print(f"addon source missing: {src}", file=sys.stderr)
        return 1

    targets = [args.addons_dir] if args.addons_dir else blender_addon_dirs()
    installed = []
    for addons in targets:
        if addons is None:
            continue
        addons.mkdir(parents=True, exist_ok=True)
        dest = addons / "caw_blender_bridge"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(src, dest)
        installed.append(dest)
        print(f"Installed: {dest}")
        # Prefer newest version only
        break

    if not installed:
        print("No Blender addons directory found. Pass --addons-dir.", file=sys.stderr)
        return 1

    print("\nNext:")
    print("1. Open Blender → Edit → Preferences → Add-ons → enable 'Caw Blender Bridge'")
    print("2. Bridge listens on 127.0.0.1:54322")
    print("3. /mcp install blender  (or add mcp/blender to .mcp.json)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
