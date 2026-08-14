"""MCP tool schemas for image cutout, resize, and super-resolution."""

from __future__ import annotations

from typing import Any, Callable

from process import (
    ImageError,
    cutout,
    image_info,
    install_deps,
    resize,
    status,
    super_resolve,
)

ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": properties,
        "required": required or [],
        "additionalProperties": False,
    }


def tool_image_status(args: dict[str, Any]) -> dict[str, Any]:
    del args
    return status()


def tool_image_install_deps(args: dict[str, Any]) -> dict[str, Any]:
    pkgs = args.get("packages")
    if pkgs is not None:
        pkgs = [str(p) for p in pkgs]
    return install_deps(pkgs)


def tool_image_info(args: dict[str, Any]) -> dict[str, Any]:
    return image_info(args["path"])


def tool_image_cutout(args: dict[str, Any]) -> dict[str, Any]:
    scale = args.get("scale")
    return cutout(
        args["path"],
        method=args.get("method"),
        prompt=args.get("prompt"),
        box=args.get("box"),
        box_mode=str(args.get("box_mode") or "xywh"),
        point=args.get("point"),
        color=args.get("color"),
        tolerance=int(args.get("tolerance") if args.get("tolerance") is not None else 30),
        threshold=float(args.get("threshold") if args.get("threshold") is not None else 0.4),
        feather=float(args.get("feather") or 0),
        invert=bool(args.get("invert", False)),
        trim=bool(args.get("trim", True)),
        scale=float(scale) if scale is not None else None,
        super_resolve=bool(args.get("super_resolve", False)),
        sr_backend=args.get("sr_backend"),
        output=args.get("output"),
    )


def tool_image_resize(args: dict[str, Any]) -> dict[str, Any]:
    scale = args.get("scale")
    width = args.get("width")
    height = args.get("height")
    return resize(
        args["path"],
        scale=float(scale) if scale is not None else None,
        width=int(width) if width is not None else None,
        height=int(height) if height is not None else None,
        fit=str(args.get("fit") or "contain"),
        resample=args.get("resample"),
        output=args.get("output"),
    )


def tool_image_super_resolve(args: dict[str, Any]) -> dict[str, Any]:
    return super_resolve(
        args["path"],
        scale=int(args.get("scale") or 4),
        backend=args.get("backend"),
        model=args.get("model"),
        output=args.get("output"),
    )


TOOLS: list[dict[str, Any]] = [
    {
        "name": "image_status",
        "description": (
            "PREFERRED first step: report image backends (Pillow / rembg / CLIPSeg / "
            "OpenCV SR / realesrgan-ncnn) and install hints."
        ),
        "inputSchema": _schema({}),
        "handler": tool_image_status,
    },
    {
        "name": "image_install_deps",
        "description": (
            "Install Python packages into THIS MCP server's interpreter "
            "(Pillow, rembg, opencv-contrib-python by default). "
            "Call this when image_status shows a missing backend — do not use "
            "install_program for rembg/Pillow. Super-res can use LANCZOS without OpenCV."
        ),
        "inputSchema": _schema(
            {
                "packages": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Override the default set, e.g. [\"transformers\", \"torch\"].",
                }
            }
        ),
        "handler": tool_image_install_deps,
    },
    {
        "name": "image_info",
        "description": "Read width, height, mode, format, and alpha for a local image.",
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Workspace-relative or absolute image path.",
                }
            },
            ["path"],
        ),
        "handler": tool_image_info,
    },
    {
        "name": "image_cutout",
        "description": (
            "Cut a subject out of an image onto a transparent PNG. "
            "Specify the region with prompt (text, needs CLIPSeg), box [x,y,w,h], "
            "color chroma-key, or point flood-fill. method=rembg extracts the main subject. "
            "Optional scale / super_resolve after the cutout. "
            "If the user wants 抠图 and 超分 on the SAME image, set super_resolve=true "
            "here (scale 2/3/4). Do not follow with a separate image_super_resolve."
        ),
        "inputSchema": _schema(
            {
                "path": {
                    "type": "string",
                    "description": "Source image path.",
                },
                "method": {
                    "type": "string",
                    "enum": ["auto", "rembg", "prompt", "box", "chroma", "flood"],
                    "description": (
                        "auto picks rembg / prompt / box / chroma / flood from the other args. "
                        "rembg = neural subject matting. prompt = text (CLIPSeg). "
                        "box = crop. chroma = color key. flood = magic-wand from point."
                    ),
                },
                "prompt": {
                    "type": "string",
                    "description": "What to keep, e.g. 'the red car' or '人物'. Needs transformers+torch.",
                },
                "box": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 4,
                    "maxItems": 4,
                    "description": "Region [x, y, width, height] (or xyxy if box_mode=xyxy).",
                },
                "box_mode": {
                    "type": "string",
                    "enum": ["xywh", "xyxy"],
                    "default": "xywh",
                },
                "point": {
                    "type": "array",
                    "items": {"type": "number"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": "[x, y] seed for flood / magic-wand.",
                },
                "color": {
                    "description": "Chroma key: '#00FF00' or [0,255,0].",
                },
                "tolerance": {
                    "type": "integer",
                    "description": "Color distance 0–255 for chroma / flood. Default 30.",
                    "default": 30,
                },
                "threshold": {
                    "type": "number",
                    "description": "CLIPSeg keep threshold 0–1. Default 0.4.",
                    "default": 0.4,
                },
                "feather": {
                    "type": "number",
                    "description": "Blur alpha edge in pixels. Default 0.",
                    "default": 0,
                },
                "invert": {
                    "type": "boolean",
                    "description": "Keep the background instead of the subject.",
                    "default": False,
                },
                "trim": {
                    "type": "boolean",
                    "description": "Crop to opaque bounds after cutout. Default true.",
                    "default": True,
                },
                "scale": {
                    "type": "number",
                    "description": "Resize the cutout (e.g. 0.5 shrink, 2 enlarge). Ignored if super_resolve.",
                },
                "super_resolve": {
                    "type": "boolean",
                    "description": "Run neural / LANCZOS super-res after cutout (scale 2/3/4, default 4).",
                    "default": False,
                },
                "sr_backend": {
                    "type": "string",
                    "enum": ["auto", "realesrgan", "opencv", "lanczos"],
                },
                "output": {
                    "type": "string",
                    "description": "Destination path. Default: <stem>_cutout.png next to the source.",
                },
            },
            ["path"],
        ),
        "handler": tool_image_cutout,
    },
    {
        "name": "image_resize",
        "description": (
            "Scale an image up or down. Pass scale (0.5, 2, …) or target width / height. "
            "Uses LANCZOS by default. For quality enlargement prefer image_super_resolve."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "scale": {
                    "type": "number",
                    "description": "Multiplier. 0.5 = half, 2 = double.",
                },
                "width": {"type": "integer", "description": "Target width in pixels."},
                "height": {"type": "integer", "description": "Target height in pixels."},
                "fit": {
                    "type": "string",
                    "enum": ["contain", "cover", "stretch"],
                    "default": "contain",
                    "description": "How to use width+height together.",
                },
                "resample": {
                    "type": "string",
                    "enum": ["lanczos", "bicubic", "bilinear", "nearest", "box"],
                    "default": "lanczos",
                },
                "output": {"type": "string"},
            },
            ["path"],
        ),
        "handler": tool_image_resize,
    },
    {
        "name": "image_super_resolve",
        "description": (
            "Upscale an image with super-resolution (2x / 3x / 4x). "
            "Backends: realesrgan-ncnn-vulkan (best if installed), OpenCV FSRCNN/ESPCN/EDSR, "
            "or LANCZOS+unsharp fallback. Use this instead of image_resize when enlarging photos."
        ),
        "inputSchema": _schema(
            {
                "path": {"type": "string"},
                "scale": {
                    "type": "integer",
                    "enum": [2, 3, 4],
                    "default": 4,
                },
                "backend": {
                    "type": "string",
                    "enum": ["auto", "realesrgan", "opencv", "lanczos"],
                    "description": "auto picks realesrgan → opencv → lanczos.",
                },
                "model": {
                    "type": "string",
                    "enum": ["fsrcnn", "espcn", "lapsrn", "edsr"],
                    "description": "OpenCV network when backend is opencv/auto. Default fsrcnn.",
                },
                "output": {"type": "string"},
            },
            ["path"],
        ),
        "handler": tool_image_super_resolve,
    },
]


def list_tool_specs() -> list[dict[str, Any]]:
    return [
        {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
        for t in TOOLS
    ]


HANDLERS: dict[str, ToolHandler] = {t["name"]: t["handler"] for t in TOOLS}


def call_tool(name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
    if name not in HANDLERS:
        raise ImageError(f"unknown tool: {name}")
    return HANDLERS[name](arguments or {})
