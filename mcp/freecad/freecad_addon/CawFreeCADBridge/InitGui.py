# GUI init — start TCP bridge when FreeCAD GUI loads.

import os
import sys

import FreeCAD

FreeCAD.Console.PrintMessage("CawFreeCADBridge: loading...\n")

_addon_dir = os.path.dirname(__file__)
if _addon_dir not in sys.path:
    sys.path.insert(0, _addon_dir)

try:
    import bridge_server

    bridge_server.start_bridge_background()
    FreeCAD.Console.PrintMessage("CawFreeCADBridge: TCP bridge started\n")
except Exception as e:
    FreeCAD.Console.PrintError(f"CawFreeCADBridge failed to start: {e}\n")
