bl_info = {
    "name": "Caw Blender Bridge",
    "author": "caw-agent",
    "version": (1, 0, 0),
    "blender": (3, 6, 0),
    "location": "Preferences > Add-ons",
    "description": "TCP bridge for caw-agent Blender MCP (127.0.0.1:54322)",
    "category": "Development",
}

from . import bridge_server


def register():
    bridge_server.start_bridge_background()


def unregister():
    pass
