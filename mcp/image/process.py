"""Image cutout, resize, and super-resolution backends."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from typing import Any

IMAGE_EXTS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
    ".gif",
    ".avif",
}

MAX_SIDE_DEFAULT = 8192


class ImageError(RuntimeError):
    pass


def _require_pil():
    try:
        from PIL import Image, ImageChops, ImageFilter, ImageOps  # noqa: F401
    except Exception as e:
        raise ImageError(
            "Pillow is required. Install with: pip install Pillow"
        ) from e
    from PIL import Image, ImageChops, ImageFilter, ImageOps

    return Image, ImageChops, ImageFilter, ImageOps


def which_realesrgan() -> str | None:
    return shutil.which("realesrgan-ncnn-vulkan") or shutil.which(
        "realesrgan-ncnn-vulkan.exe"
    )


def backend_available(name: str) -> bool:
    if name == "pillow":
        try:
            import PIL  # noqa: F401

            return True
        except Exception:
            return False
    if name == "rembg":
        try:
            import rembg  # noqa: F401

            return True
        except Exception:
            return False
    if name == "clipseg":
        try:
            import torch  # noqa: F401
            import transformers  # noqa: F401

            return True
        except Exception:
            return False
    if name == "opencv":
        try:
            import cv2

            return hasattr(cv2, "dnn_superres")
        except Exception:
            return False
    if name == "realesrgan":
        return bool(which_realesrgan())
    return False


def detect_cutout_backend() -> str:
    forced = os.environ.get("IMAGE_CUTOUT_BACKEND", "auto").strip().lower() or "auto"
    if forced != "auto":
        return forced
    if backend_available("rembg"):
        return "rembg"
    if backend_available("clipseg"):
        return "clipseg"
    if backend_available("pillow"):
        return "pillow"
    return "none"


def detect_sr_backend() -> str:
    forced = os.environ.get("IMAGE_SR_BACKEND", "auto").strip().lower() or "auto"
    if forced != "auto":
        return forced
    if backend_available("realesrgan"):
        return "realesrgan"
    if backend_available("opencv"):
        return "opencv"
    if backend_available("pillow"):
        return "lanczos"
    return "none"


def model_dir() -> Path:
    raw = os.environ.get("IMAGE_MODEL_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    home = Path(os.environ.get("CAW_HOME") or Path.home() / ".caw-agent")
    return home / "image-models"


def max_side() -> int:
    raw = os.environ.get("IMAGE_MAX_SIDE", "").strip()
    if not raw:
        return MAX_SIDE_DEFAULT
    try:
        return max(64, int(raw))
    except ValueError:
        return MAX_SIDE_DEFAULT


def resolve_image(path: str) -> Path:
    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        raise ImageError("path is required")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    if not p.is_file():
        raise ImageError(f"image not found: {p}")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise ImageError(f"unsupported image type: {p.suffix or '(none)'}")
    return p


def default_output(src: Path, suffix: str, ext: str | None = None) -> Path:
    out_ext = ext if ext else src.suffix.lower() or ".png"
    if out_ext == ".jpeg":
        out_ext = ".jpg"
    return src.with_name(f"{src.stem}{suffix}{out_ext}")


def resolve_output(src: Path, output: str | None, suffix: str, *, prefer_png: bool) -> Path:
    if output:
        p = Path(output.strip().strip('"').strip("'")).expanduser()
        if not p.is_absolute():
            p = Path.cwd() / p
        return p.resolve()
    ext = ".png" if prefer_png else None
    return default_output(src, suffix, ext)


def open_image(path: Path):
    Image, _, _, ImageOps = _require_pil()
    im = Image.open(path)
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
        im = im.copy()
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    return im


def image_info(path: str) -> dict[str, Any]:
    src = resolve_image(path)
    im = open_image(src)
    w, h = im.size
    return {
        "ok": True,
        "path": str(src),
        "width": w,
        "height": h,
        "mode": im.mode,
        "format": im.format or src.suffix.lstrip(".").upper(),
        "has_alpha": im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info,
        "bytes": src.stat().st_size,
    }


def _guard_size(w: int, h: int) -> None:
    cap = max_side()
    if max(w, h) > cap:
        raise ImageError(f"image too large ({w}x{h}); max side is {cap} (IMAGE_MAX_SIDE)")


def _parse_box(
    box: Any, w: int, h: int, *, mode: str = "xywh"
) -> tuple[int, int, int, int]:
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ImageError("box must be four numbers: xywh [x,y,w,h] or xyxy [x1,y1,x2,y2]")
    vals = [int(round(float(v))) for v in box]
    kind = (mode or "xywh").strip().lower()
    if kind == "xyxy":
        x0, y0, x1, y1 = vals
    else:
        x0, y0, bw, bh = vals
        x1, y1 = x0 + bw, y0 + bh
    x0 = max(0, min(w - 1, x0))
    y0 = max(0, min(h - 1, y0))
    x1 = max(x0 + 1, min(w, x1))
    y1 = max(y0 + 1, min(h, y1))
    return x0, y0, x1, y1


def _parse_point(point: Any, w: int, h: int) -> tuple[int, int]:
    if not isinstance(point, (list, tuple)) or len(point) != 2:
        raise ImageError("point must be [x, y]")
    x = int(round(float(point[0])))
    y = int(round(float(point[1])))
    if x < 0 or y < 0 or x >= w or y >= h:
        raise ImageError(f"point ({x},{y}) outside image {w}x{h}")
    return x, y


def _parse_color(color: Any) -> tuple[int, int, int]:
    if color is None:
        raise ImageError("color is required for chroma cutout")
    if isinstance(color, (list, tuple)) and len(color) >= 3:
        return tuple(max(0, min(255, int(c))) for c in color[:3])  # type: ignore[return-value]
    s = str(color).strip()
    if s.startswith("#"):
        s = s[1:]
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) == 6:
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            pass
    parts = [p for p in s.replace(",", " ").split() if p]
    if len(parts) == 3:
        return tuple(max(0, min(255, int(p))) for p in parts)  # type: ignore[return-value]
    raise ImageError(f"bad color `{color}` (use #00FF00 or 0,255,0)")


def _apply_alpha(im, mask, *, invert: bool = False):
    Image, _, ImageFilter, _ = _require_pil()
    rgba = im.convert("RGBA")
    if mask.size != rgba.size:
        mask = mask.resize(rgba.size)
    mask = mask.convert("L")
    if invert:
        mask = mask.point(lambda p: 255 - p)
    r, g, b, _ = rgba.split()
    return Image.merge("RGBA", (r, g, b, mask))


def _feather(im, radius: float):
    if radius <= 0:
        return im
    _, _, ImageFilter, _ = _require_pil()
    rgba = im.convert("RGBA")
    r, g, b, a = rgba.split()
    a = a.filter(ImageFilter.GaussianBlur(radius=float(radius)))
    from PIL import Image

    return Image.merge("RGBA", (r, g, b, a))


def _trim(im):
    bbox = im.getbbox()
    if bbox:
        return im.crop(bbox)
    return im


def _save(im, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ext = dest.suffix.lower()
    save_im = im
    fmt = None
    if ext in {".jpg", ".jpeg"}:
        if im.mode in ("RGBA", "LA"):
            Image, *_ = _require_pil()
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1])
            save_im = bg
        else:
            save_im = im.convert("RGB")
        fmt = "JPEG"
    elif ext == ".webp":
        fmt = "WEBP"
    elif ext in {".tif", ".tiff"}:
        fmt = "TIFF"
    else:
        if ext != ".png":
            dest = dest.with_suffix(".png")
        fmt = "PNG"
        if save_im.mode not in ("RGB", "RGBA", "L", "LA"):
            save_im = save_im.convert("RGBA")
    kwargs: dict[str, Any] = {}
    if fmt == "JPEG":
        kwargs["quality"] = 92
        kwargs["optimize"] = True
    elif fmt == "PNG":
        kwargs["optimize"] = True
    save_im.save(dest, format=fmt, **kwargs)
    return dest


def _cutout_rembg(im):
    try:
        from rembg import new_session, remove
    except Exception as e:
        raise ImageError("rembg is not installed. pip install rembg") from e
    model = os.environ.get("IMAGE_REMBG_MODEL", "u2net").strip() or "u2net"
    session = new_session(model)
    out = remove(im.convert("RGBA"), session=session)
    from PIL import Image

    if not isinstance(out, Image.Image):
        from io import BytesIO

        out = Image.open(BytesIO(out)).convert("RGBA")
    return out.convert("RGBA")


_clipseg_cache: tuple[Any, Any] | None = None


def _cutout_prompt(im, prompt: str, threshold: float):
    global _clipseg_cache
    if not prompt.strip():
        raise ImageError("prompt is required for prompt cutout")
    try:
        import numpy as np
        import torch
        from transformers import CLIPSegForImageSegmentation, CLIPSegProcessor
    except Exception as e:
        raise ImageError(
            "prompt cutout needs: pip install transformers torch"
        ) from e
    if _clipseg_cache is None:
        name = (
            os.environ.get("IMAGE_CLIPSEG_MODEL", "CIDAS/clipseg-rd64-refined").strip()
            or "CIDAS/clipseg-rd64-refined"
        )
        processor = CLIPSegProcessor.from_pretrained(name)
        model = CLIPSegForImageSegmentation.from_pretrained(name)
        model.eval()
        _clipseg_cache = (processor, model)
    processor, model = _clipseg_cache
    rgb = im.convert("RGB")
    inputs = processor(
        text=[prompt], images=[rgb], padding=True, return_tensors="pt"
    )
    with torch.no_grad():
        logits = model(**inputs).logits
    pred = torch.sigmoid(logits)
    if pred.ndim == 3:
        pred = pred[0]
    arr = (pred.detach().cpu().numpy() * 255.0).clip(0, 255).astype("uint8")
    from PIL import Image

    mask = Image.fromarray(arr, mode="L").resize(rgb.size, Image.Resampling.BILINEAR)
    cut = int(max(0.0, min(1.0, threshold)) * 255)
    mask = mask.point(lambda p, c=cut: p if p >= c else 0)
    return _apply_alpha(im, mask)


def _cutout_chroma(im, color: Any, tolerance: int):
    Image, ImageChops, _, _ = _require_pil()
    rgb = im.convert("RGB")
    key = _parse_color(color)
    solid = Image.new("RGB", rgb.size, key)
    diff = ImageChops.difference(rgb, solid).convert("L")
    # Keep pixels that are NOT the key color.
    mask = diff.point(lambda p, t=tolerance: 255 if p > t else 0)
    return _apply_alpha(im, mask)


def _cutout_flood(im, point: Any, tolerance: int):
    from collections import deque

    rgb = im.convert("RGB")
    w, h = rgb.size
    x, y = _parse_point(point, w, h)
    px = rgb.load()
    target = px[x, y]
    tol2 = (max(0, tolerance) ** 2) * 3
    from PIL import Image

    mask = Image.new("L", (w, h), 0)
    mp = mask.load()
    seen = bytearray(w * h)
    q = deque([(x, y)])
    while q:
        cx, cy = q.popleft()
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            continue
        i = cy * w + cx
        if seen[i]:
            continue
        seen[i] = 1
        c = px[cx, cy]
        d = (c[0] - target[0]) ** 2 + (c[1] - target[1]) ** 2 + (c[2] - target[2]) ** 2
        if d > tol2:
            continue
        mp[cx, cy] = 255
        q.extend(((cx + 1, cy), (cx - 1, cy), (cx, cy + 1), (cx, cy - 1)))
    return _apply_alpha(im, mask)


def cutout(
    path: str,
    *,
    method: str | None = None,
    prompt: str | None = None,
    box: Any = None,
    box_mode: str = "xywh",
    point: Any = None,
    color: Any = None,
    tolerance: int = 30,
    threshold: float = 0.4,
    feather: float = 0.0,
    invert: bool = False,
    trim: bool = True,
    scale: float | None = None,
    super_resolve: bool = False,
    sr_backend: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    src = resolve_image(path)
    im = open_image(src)
    w, h = im.size
    _guard_size(w, h)
    method = (method or "auto").strip().lower() or "auto"
    used = method
    notes: list[str] = []

    if method == "auto":
        if prompt:
            if backend_available("clipseg"):
                used = "prompt"
            elif box is not None:
                used = "box"
                notes.append("CLIPSeg missing — used box")
            elif backend_available("rembg"):
                used = "rembg"
                notes.append("CLIPSeg missing — rembg subject (prompt ignored)")
            else:
                raise ImageError(
                    "prompt cutout needs `pip install transformers torch`, "
                    "or pass box=[x,y,w,h]"
                )
        elif box is not None and not backend_available("rembg"):
            used = "box"
        elif backend_available("rembg"):
            used = "rembg"
        elif box is not None:
            used = "box"
        elif color is not None:
            used = "chroma"
        elif point is not None:
            used = "flood"
        else:
            raise ImageError(
                "auto cutout needs rembg (`pip install rembg`) or a selector: "
                "prompt / box / color / point"
            )

    work = im
    if box is not None and used in {"box", "rembg", "prompt", "auto"}:
        x0, y0, x1, y1 = _parse_box(box, w, h, mode=box_mode)
        work = im.crop((x0, y0, x1, y1))
        notes.append(f"cropped {x0},{y0}-{x1},{y1}")

    if used == "rembg":
        out = _cutout_rembg(work)
    elif used == "prompt":
        out = _cutout_prompt(work, prompt or "", threshold)
    elif used == "box":
        out = work.convert("RGBA")
    elif used == "chroma":
        out = _cutout_chroma(work, color, int(tolerance))
    elif used == "flood":
        out = _cutout_flood(work, point, int(tolerance))
    else:
        raise ImageError(f"unknown cutout method `{method}`")

    if invert and used != "box":
        r, g, b, a = out.split()
        from PIL import Image

        out = Image.merge("RGBA", (r, g, b, a.point(lambda p: 255 - p)))

    if feather:
        out = _feather(out, float(feather))
    if trim:
        before = out.size
        out = _trim(out)
        if out.size != before:
            notes.append(f"trimmed to {out.size[0]}x{out.size[1]}")

    sr_used = None
    if super_resolve:
        factor = int(round(float(scale or 4)))
        if factor not in (2, 3, 4):
            factor = 4 if factor >= 4 else 2
        out, sr_used = _super_resolve_image(out, factor, sr_backend or "auto")
        notes.append(f"super-resolve x{factor} via {sr_used}")
    elif scale and float(scale) != 1.0:
        out = _resize_image(out, scale=float(scale))
        notes.append(f"scaled x{float(scale):g} → {out.size[0]}x{out.size[1]}")

    dest = resolve_output(src, output, "_cutout", prefer_png=True)
    dest = _save(out, dest)
    return {
        "ok": True,
        "path": str(dest),
        "source": str(src),
        "method": used,
        "width": out.size[0],
        "height": out.size[1],
        "has_alpha": True,
        "super_resolve": sr_used,
        "notes": notes,
    }


def _resample(name: str | None):
    from PIL import Image

    key = (name or "lanczos").strip().lower()
    table = {
        "lanczos": Image.Resampling.LANCZOS,
        "bicubic": Image.Resampling.BICUBIC,
        "bilinear": Image.Resampling.BILINEAR,
        "nearest": Image.Resampling.NEAREST,
        "box": Image.Resampling.BOX,
    }
    if key not in table:
        raise ImageError(f"unknown resample `{name}`")
    return table[key]


def _resize_image(
    im,
    *,
    scale: float | None = None,
    width: int | None = None,
    height: int | None = None,
    fit: str = "contain",
    resample: str | None = None,
):
    w, h = im.size
    if scale and scale > 0:
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
    elif width and height:
        mode = (fit or "contain").strip().lower()
        if mode == "stretch":
            nw, nh = int(width), int(height)
        else:
            sx = width / w
            sy = height / h
            s = max(sx, sy) if mode == "cover" else min(sx, sy)
            nw = max(1, int(round(w * s)))
            nh = max(1, int(round(h * s)))
    elif width:
        nw = int(width)
        nh = max(1, int(round(h * (nw / w))))
    elif height:
        nh = int(height)
        nw = max(1, int(round(w * (nh / h))))
    else:
        raise ImageError("pass scale, or width / height")
    _guard_size(nw, nh)
    return im.resize((nw, nh), _resample(resample))


def resize(
    path: str,
    *,
    scale: float | None = None,
    width: int | None = None,
    height: int | None = None,
    fit: str = "contain",
    resample: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    src = resolve_image(path)
    im = open_image(src)
    _guard_size(*im.size)
    out = _resize_image(
        im,
        scale=scale,
        width=width,
        height=height,
        fit=fit,
        resample=resample,
    )
    tag = f"_x{scale:g}" if scale else f"_{out.size[0]}x{out.size[1]}"
    dest = resolve_output(src, output, tag, prefer_png=im.mode in ("RGBA", "LA"))
    dest = _save(out, dest)
    return {
        "ok": True,
        "path": str(dest),
        "source": str(src),
        "width": out.size[0],
        "height": out.size[1],
        "resample": (resample or "lanczos"),
    }


def _download(url: str, dest: Path) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.is_file() and dest.stat().st_size > 1000:
        return dest
    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        urllib.request.urlretrieve(url, tmp)
        tmp.replace(dest)
    except Exception as e:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
        raise ImageError(f"failed to download SR model: {e}") from e
    return dest


# OpenCV dnn_superres checkpoints (small .pb graphs).
_CV_MODELS = {
    ("fsrcnn", 2): (
        "FSRCNN_x2.pb",
        "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x2.pb",
    ),
    ("fsrcnn", 3): (
        "FSRCNN_x3.pb",
        "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x3.pb",
    ),
    ("fsrcnn", 4): (
        "FSRCNN_x4.pb",
        "https://github.com/Saafke/FSRCNN_Tensorflow/raw/master/models/FSRCNN_x4.pb",
    ),
    ("espcn", 2): (
        "ESPCN_x2.pb",
        "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x2.pb",
    ),
    ("espcn", 3): (
        "ESPCN_x3.pb",
        "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x3.pb",
    ),
    ("espcn", 4): (
        "ESPCN_x4.pb",
        "https://github.com/fannymonori/TF-ESPCN/raw/master/export/ESPCN_x4.pb",
    ),
    ("lapsrn", 2): (
        "LapSRN_x2.pb",
        "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x2.pb",
    ),
    ("lapsrn", 4): (
        "LapSRN_x4.pb",
        "https://github.com/fannymonori/TF-LapSRN/raw/master/export/LapSRN_x4.pb",
    ),
    ("edsr", 2): (
        "EDSR_x2.pb",
        "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x2.pb",
    ),
    ("edsr", 3): (
        "EDSR_x3.pb",
        "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x3.pb",
    ),
    ("edsr", 4): (
        "EDSR_x4.pb",
        "https://github.com/Saafke/EDSR_Tensorflow/raw/master/models/EDSR_x4.pb",
    ),
}


def _super_resolve_opencv(im, scale: int, model_name: str):
    try:
        import cv2
        import numpy as np
    except Exception as e:
        raise ImageError("opencv SR needs: pip install opencv-contrib-python") from e
    if not hasattr(cv2, "dnn_superres"):
        raise ImageError("opencv-contrib-python is required (cv2.dnn_superres missing)")
    key = (model_name.lower(), scale)
    if key not in _CV_MODELS:
        raise ImageError(
            f"opencv model `{model_name}` x{scale} not available "
            f"(try fsrcnn/espcn/lapsrn/edsr)"
        )
    fname, url = _CV_MODELS[key]
    weights = _download(url, model_dir() / fname)
    rgba = im.convert("RGBA")
    arr = np.array(rgba)
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGR)
    sr = cv2.dnn_superres.DnnSuperResImpl_create()
    sr.readModel(str(weights))
    sr.setModel(model_name.lower(), scale)
    up = sr.upsample(bgr)
    alpha = np.array(rgba.split()[-1])
    if alpha.shape[:2] != up.shape[:2]:
        alpha = cv2.resize(alpha, (up.shape[1], up.shape[0]), interpolation=cv2.INTER_LINEAR)
    up_rgba = cv2.cvtColor(up, cv2.COLOR_BGR2RGBA)
    up_rgba[:, :, 3] = alpha
    from PIL import Image

    return Image.fromarray(up_rgba)


def _super_resolve_realesrgan(im, scale: int):
    exe = which_realesrgan()
    if not exe:
        raise ImageError(
            "realesrgan-ncnn-vulkan not on PATH. "
            "Install the release binary or use backend=opencv / lanczos."
        )
    if scale not in (2, 3, 4):
        scale = 4
    with tempfile.TemporaryDirectory(prefix="caw-sr-") as td:
        src = Path(td) / "in.png"
        dest = Path(td) / "out.png"
        im.convert("RGBA").save(src, "PNG")
        cmd = [exe, "-i", str(src), "-o", str(dest), "-s", str(scale), "-n", "realesrgan-x4plus"]
        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300, check=False
            )
        except Exception as e:
            raise ImageError(f"realesrgan failed to start: {e}") from e
        if proc.returncode != 0 or not dest.is_file():
            err = (proc.stderr or proc.stdout or "").strip() or f"exit {proc.returncode}"
            raise ImageError(f"realesrgan failed: {err}")
        from PIL import Image

        return Image.open(dest).convert("RGBA")


def _super_resolve_lanczos(im, scale: int):
    _, _, ImageFilter, _ = _require_pil()
    w, h = im.size
    out = im.resize((max(1, w * scale), max(1, h * scale)), _resample("lanczos"))
    return out.filter(ImageFilter.UnsharpMask(radius=1.4, percent=140, threshold=2))


def _super_resolve_image(im, scale: int, backend: str):
    if scale not in (2, 3, 4):
        raise ImageError("super-resolve scale must be 2, 3, or 4")
    _guard_size(im.size[0] * scale, im.size[1] * scale)
    name = (backend or "auto").strip().lower() or "auto"
    if name == "auto":
        name = detect_sr_backend()
        if name == "none":
            raise ImageError("no super-resolve backend (install Pillow)")
        if name == "lanczos":
            pass
    if name == "realesrgan":
        return _super_resolve_realesrgan(im, scale), "realesrgan"
    if name == "opencv":
        model = os.environ.get("IMAGE_SR_MODEL", "fsrcnn").strip().lower() or "fsrcnn"
        if (model, scale) not in _CV_MODELS:
            model = "fsrcnn"
        return _super_resolve_opencv(im, scale, model), f"opencv:{model}"
    if name in {"lanczos", "pillow"}:
        return _super_resolve_lanczos(im, scale), "lanczos"
    raise ImageError(f"unknown SR backend `{backend}`")


def super_resolve(
    path: str,
    *,
    scale: int = 4,
    backend: str | None = None,
    model: str | None = None,
    output: str | None = None,
) -> dict[str, Any]:
    src = resolve_image(path)
    im = open_image(src)
    _guard_size(*im.size)
    factor = int(scale)
    if model:
        os.environ["IMAGE_SR_MODEL"] = str(model)
    out, used = _super_resolve_image(im, factor, backend or "auto")
    dest = resolve_output(
        src, output, f"_sr{factor}x", prefer_png=im.mode in ("RGBA", "LA")
    )
    dest = _save(out, dest)
    return {
        "ok": True,
        "path": str(dest),
        "source": str(src),
        "backend": used,
        "scale": factor,
        "width": out.size[0],
        "height": out.size[1],
    }


DEFAULT_PIP = ["Pillow", "rembg", "opencv-contrib-python"]


def install_deps(packages: list[str] | None = None) -> dict[str, Any]:
    """Install Python extras into *this* interpreter (the MCP server)."""
    import subprocess
    import sys

    pkgs = [p.strip() for p in (packages or DEFAULT_PIP) if str(p).strip()]
    if not pkgs:
        raise ImageError("packages is empty")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *pkgs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        raise ImageError(f"pip failed to start: {e}") from e
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise ImageError(f"pip install failed ({proc.returncode}):\n{out[-4000:]}")
    return {
        "ok": True,
        "python": sys.executable,
        "packages": pkgs,
        "log": out[-4000:],
        "available": {
            "pillow": backend_available("pillow"),
            "rembg": backend_available("rembg"),
            "clipseg": backend_available("clipseg"),
            "opencv": backend_available("opencv"),
        },
        "next": (
            "Retry the image tool. Super-res works with Pillow LANCZOS even without OpenCV. "
            "Subject cutout needs rembg. Prompt cutout needs: pip install transformers torch"
        ),
    }


def status() -> dict[str, Any]:
    cut = detect_cutout_backend()
    sr = detect_sr_backend()
    return {
        "ok": True,
        "cutout": cut,
        "super_resolve": sr,
        "available": {
            "pillow": backend_available("pillow"),
            "rembg": backend_available("rembg"),
            "clipseg": backend_available("clipseg"),
            "opencv": backend_available("opencv"),
            "realesrgan": backend_available("realesrgan"),
        },
        "realesrgan": which_realesrgan(),
        "model_dir": str(model_dir()),
        "max_side": max_side(),
        "cwd": str(Path.cwd()),
        "env": {
            "IMAGE_CUTOUT_BACKEND": os.environ.get("IMAGE_CUTOUT_BACKEND", "auto"),
            "IMAGE_SR_BACKEND": os.environ.get("IMAGE_SR_BACKEND", "auto"),
            "IMAGE_SR_MODEL": os.environ.get("IMAGE_SR_MODEL") or None,
            "IMAGE_REMBG_MODEL": os.environ.get("IMAGE_REMBG_MODEL") or None,
        },
        "hint": (
            "Missing Python extras: call image_install_deps (installs into this Python).\n"
            "Super-res already works via LANCZOS when Pillow is present — do not treat "
            "missing OpenCV/realesrgan as fatal.\n"
            "Prompt cutout extra: image_install_deps packages=[\"transformers\",\"torch\"]"
        ),
    }


if __name__ == "__main__":
    from PIL import Image, ImageDraw

    td = Path(tempfile.mkdtemp(prefix="caw-image-self-"))
    src = td / "in.png"
    im = Image.new("RGB", (40, 40), (10, 10, 200))
    ImageDraw.Draw(im).rectangle((8, 8, 24, 24), fill=(240, 200, 20))
    im.save(src)
    info = image_info(str(src))
    assert info["width"] == 40
    box = cutout(str(src), method="box", box=[8, 8, 16, 16], output=str(td / "box.png"))
    assert box["width"] == 16 and box["height"] == 16
    chroma = cutout(
        str(src), method="chroma", color="#0A0AC8", tolerance=20, output=str(td / "ch.png")
    )
    assert chroma["ok"]
    half = resize(str(src), scale=0.5, output=str(td / "half.png"))
    assert half["width"] == 20
    sr = super_resolve(str(src), scale=2, backend="lanczos", output=str(td / "sr.png"))
    assert sr["width"] == 80
    print("process helpers ok", td)
