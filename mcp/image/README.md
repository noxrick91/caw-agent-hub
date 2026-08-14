# Image MCP for caw-agent

stdio MCP server for **cutout / 抠图**, **resize**, and **super-resolution**.

Uses **Content-Length** JSON-RPC framing (same as FreeCAD / speech MCP).

## Tools

| Tool | What it does |
|------|----------------|
| `image_status` | Backends: Pillow, rembg, CLIPSeg, OpenCV SR, realesrgan |
| `image_info` | Width / height / mode / alpha |
| `image_cutout` | Extract specified content onto a transparent PNG |
| `image_resize` | Scale up or down (`scale` or `width`/`height`) |
| `image_super_resolve` | 2× / 3× / 4× SR (neural if available, else LANCZOS) |

## Cutout methods

| `method` | How you specify the subject |
|----------|-----------------------------|
| `rembg` | Neural subject / background removal |
| `prompt` | Text, e.g. `the cat` / `人物` (needs `transformers` + `torch`) |
| `box` | `[x, y, width, height]` crop (optional rembg refine via `auto`) |
| `chroma` | Color key (`color="#00FF00"`, `tolerance`) |
| `flood` | Magic-wand from `point=[x,y]` |
| `auto` | Picks from the args you passed |

`image_cutout` can also `scale=2` or `super_resolve=true` in the same call.

## Skills

`mcp/image/skills/image-edit` — cutout then super-resolve in one `image_cutout` call. Discovered automatically.

## Setup

```text
/mcp install image
pip install Pillow
```

Optional quality upgrades:

```powershell
pip install rembg                      # subject cutout
pip install transformers torch         # text-prompt cutout
pip install opencv-contrib-python      # FSRCNN / ESPCN / EDSR
```

Or put [`realesrgan-ncnn-vulkan`](https://github.com/xinntao/Real-ESRGAN-ncnn-vulkan/releases) on `PATH` for the best 4× upscale.

Reload: `/mcp reload`.

## Typical agent flow

1. `image_status`
2. `image_info` on the source
3. `image_cutout` with `prompt` / `box` / `color` / `point`
4. `image_resize` (`scale=0.5`) or `image_super_resolve` (`scale=4`)

## Env

| Variable | Meaning |
|----------|---------|
| `IMAGE_CUTOUT_BACKEND` | `auto` / `rembg` / `clipseg` / `pillow` |
| `IMAGE_SR_BACKEND` | `auto` / `realesrgan` / `opencv` / `lanczos` |
| `IMAGE_SR_MODEL` | OpenCV net: `fsrcnn` (default), `espcn`, `lapsrn`, `edsr` |
| `IMAGE_REMBG_MODEL` | rembg session, default `u2net` |
| `IMAGE_CLIPSEG_MODEL` | Hugging Face id, default `CIDAS/clipseg-rd64-refined` |
| `IMAGE_MODEL_DIR` | Where OpenCV `.pb` weights are cached |
| `IMAGE_MAX_SIDE` | Reject / cap (default 8192) |
| `IMAGE_MCP_LOG` | Log file (stderr if unset) |
