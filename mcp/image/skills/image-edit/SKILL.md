---
name: image-edit
description: Cut out subjects, resize, and super-resolve images with the image MCP. Use when the user asks to 抠图, cut out, isolate, remove background, resize, enlarge, upscale, or super-resolve a picture.
---

# Image edit

Use `mcp__image__*` only. Always write a file — do not invent pixels.

Same MCP server is **one-at-a-time**. Same-file pipelines stay in **one** tool call.

## Tools

| Tool | When |
|------|------|
| `image_status` | First step — Pillow / rembg / CLIPSeg / OpenCV / realesrgan |
| `image_info` | Size, mode, alpha of a path |
| `image_cutout` | Isolate a subject onto a transparent PNG |
| `image_resize` | Scale down, or exact `width`/`height` |
| `image_super_resolve` | Enlarge an **existing** file 2×/3×/4× |
| `image_install_deps` | Missing **Python** extras (Pillow, rembg, opencv-contrib-python) |

## Same image: cutout then enlarge

One `image_cutout` with `super_resolve=true` and `scale=2|3|4`.

Do **not** follow with `image_super_resolve`. Do **not** spawn Task for that pipeline.

## Independent work

Several **different** images (or image + OCR on another file): emit multiple tool calls in one message. Same file / same server stays sequential.

## Cutout methods

`method` default `auto` (picks from the other args):

| method | Args | Needs |
|--------|------|--------|
| `rembg` | — | rembg (whole subject) |
| `prompt` | `prompt` e.g. `the red car` / `人物` | transformers + torch |
| `box` | `box=[x,y,w,h]` (`box_mode=xywh` default, or `xyxy`) | — |
| `chroma` | `color="#00FF00"` or `[0,255,0]`, `tolerance` 0–255 | — |
| `flood` | `point=[x,y]`, `tolerance` | — |

Useful flags: `feather` (px), `invert` (keep background), `trim` (default true), `output`.

Plain shrink after cutout (no SR): `scale=0.5` on the same `image_cutout` (ignored if `super_resolve`).

## Resize vs super-resolve

- Downscale / fit a box → `image_resize` (`scale`, or `width`/`height` + `fit=contain|cover|stretch`, `resample=lanczos`).
- Quality enlarge of a file already cut out → `image_super_resolve` (`scale=2|3|4`, `backend=auto|realesrgan|opencv|lanczos`).
- Enlarge **while** cutting out → `image_cutout` `super_resolve=true`.

## Missing backends

1. `image_status`.
2. Python extras (`rembg` / Pillow / OpenCV / `transformers`) → `image_install_deps` (optional `packages=[...]`). **Not** `install_program`.
3. Super-res already works with LANCZOS if OpenCV/realesrgan are absent — do not stop.
4. Return the output `path`.
