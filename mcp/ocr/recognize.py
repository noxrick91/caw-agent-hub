"""OCR backends: Tesseract, EasyOCR, PaddleOCR, OpenAI-compatible vision."""

from __future__ import annotations

import base64
import io
import json
import os
import shutil
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff", ".gif"}


class OcrError(RuntimeError):
    pass


def which_tesseract() -> str | None:
    env = os.environ.get("TESSERACT_CMD", "").strip()
    if env and Path(env).is_file():
        return env
    found = shutil.which("tesseract") or shutil.which("tesseract.exe")
    if found:
        return found
    for cand in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if Path(cand).is_file():
            return cand
    return None


def api_key() -> str | None:
    for key in ("OCR_API_KEY", "OPENAI_API_KEY", "CAW_API_KEY"):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


def api_base() -> str:
    raw = (
        os.environ.get("OCR_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).strip()
    return raw.rstrip("/")


def api_model() -> str:
    return os.environ.get("OCR_MODEL", "").strip() or "gpt-4o-mini"


def backend_available(name: str) -> bool:
    if name == "tesseract":
        if not which_tesseract():
            return False
        try:
            import pytesseract  # noqa: F401

            return True
        except Exception:
            return False
    if name == "easyocr":
        try:
            import easyocr  # noqa: F401

            return True
        except Exception:
            return False
    if name == "paddleocr":
        try:
            from paddleocr import PaddleOCR  # noqa: F401

            return True
        except Exception:
            return False
    if name == "openai":
        return bool(api_key())
    return False


def detect_backend() -> str:
    forced = os.environ.get("OCR_BACKEND", "auto").strip().lower() or "auto"
    if forced != "auto":
        return forced
    for name in ("tesseract", "easyocr", "paddleocr", "openai"):
        if backend_available(name):
            return name
    return "none"


def resolve_image(path: str) -> Path:
    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        raise OcrError("path is required")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    if not p.is_file():
        raise OcrError(f"image not found: {p}")
    if p.suffix.lower() not in IMAGE_EXTS:
        raise OcrError(f"unsupported image type: {p.suffix or '(none)'}")
    return p


def _open_rgb(path: Path, box: list[float] | None):
    try:
        from PIL import Image, ImageOps
    except Exception as e:
        raise OcrError("Pillow is required. pip install Pillow") from e
    im = Image.open(path)
    if getattr(im, "n_frames", 1) > 1:
        im.seek(0)
        im = im.copy()
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass
    im = im.convert("RGB")
    if box:
        if len(box) != 4:
            raise OcrError("box must be [x, y, width, height]")
        x, y, w, h = (int(round(float(v))) for v in box)
        im = im.crop((x, y, x + max(1, w), y + max(1, h)))
    return im


def _tesseract_lang(lang: str | None) -> str:
    raw = (lang or os.environ.get("OCR_LANG") or "chi_sim+eng").strip()
    return raw or "chi_sim+eng"


def _run_tesseract(im, lang: str | None) -> dict[str, Any]:
    try:
        import pytesseract
    except Exception as e:
        raise OcrError("tesseract backend needs: pip install pytesseract") from e
    cmd = which_tesseract()
    if not cmd:
        raise OcrError("tesseract binary not on PATH. Install Tesseract-OCR.")
    pytesseract.pytesseract.tesseract_cmd = cmd
    code = _tesseract_lang(lang)
    try:
        data = pytesseract.image_to_data(im, lang=code, output_type=pytesseract.Output.DICT)
        text = pytesseract.image_to_string(im, lang=code)
    except Exception as e:
        raise OcrError(f"tesseract failed ({code}): {e}") from e
    blocks: list[dict[str, Any]] = []
    n = len(data.get("text") or [])
    for i in range(n):
        word = str(data["text"][i]).strip()
        if not word:
            continue
        try:
            conf = float(data["conf"][i])
        except Exception:
            conf = -1.0
        if conf < 0:
            continue
        blocks.append(
            {
                "text": word,
                "conf": round(conf, 1),
                "box": [
                    int(data["left"][i]),
                    int(data["top"][i]),
                    int(data["width"][i]),
                    int(data["height"][i]),
                ],
            }
        )
    return {"text": text.strip(), "blocks": blocks, "lang": code}


_easy_cache: Any = None


def _run_easyocr(im, lang: str | None) -> dict[str, Any]:
    global _easy_cache
    try:
        import easyocr
        import numpy as np
    except Exception as e:
        raise OcrError("easyocr backend needs: pip install easyocr") from e
    raw = (lang or os.environ.get("OCR_LANG") or "ch_sim,en").strip()
    langs = [p.strip() for p in raw.replace("+", ",").split(",") if p.strip()]
    # Tesseract ids → EasyOCR ids
    remap = {"chi_sim": "ch_sim", "chi_tra": "ch_tra", "eng": "en"}
    langs = [remap.get(x, x) for x in langs] or ["ch_sim", "en"]
    if _easy_cache is None or getattr(_easy_cache, "_caw_langs", None) != tuple(langs):
        reader = easyocr.Reader(langs, gpu=os.environ.get("OCR_GPU", "").lower() in {"1", "true"})
        reader._caw_langs = tuple(langs)  # type: ignore[attr-defined]
        _easy_cache = reader
    arr = np.array(im)
    hits = _easy_cache.readtext(arr)
    lines: list[str] = []
    blocks: list[dict[str, Any]] = []
    for box, word, conf in hits:
        word = str(word).strip()
        if not word:
            continue
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        lines.append(word)
        blocks.append(
            {
                "text": word,
                "conf": round(float(conf) * 100.0, 1),
                "box": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
            }
        )
    return {"text": "\n".join(lines).strip(), "blocks": blocks, "lang": ",".join(langs)}


_paddle_cache: Any = None


def _run_paddle(im, lang: str | None) -> dict[str, Any]:
    global _paddle_cache
    try:
        import numpy as np
        from paddleocr import PaddleOCR
    except Exception as e:
        raise OcrError("paddleocr backend needs: pip install paddleocr paddlepaddle") from e
    code = (lang or os.environ.get("OCR_LANG") or "ch").strip()
    if code in {"chi_sim", "ch_sim", "zh", "zh-cn"}:
        code = "ch"
    elif code in {"eng", "en"}:
        code = "en"
    if _paddle_cache is None or getattr(_paddle_cache, "_caw_lang", None) != code:
        ocr = PaddleOCR(use_angle_cls=True, lang=code, show_log=False)
        ocr._caw_lang = code  # type: ignore[attr-defined]
        _paddle_cache = ocr
    arr = np.array(im)
    result = _paddle_cache.ocr(arr, cls=True)
    lines: list[str] = []
    blocks: list[dict[str, Any]] = []
    pages = result or []
    if pages and pages[0]:
        for item in pages[0]:
            box, (word, conf) = item
            word = str(word).strip()
            if not word:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            lines.append(word)
            blocks.append(
                {
                    "text": word,
                    "conf": round(float(conf) * 100.0, 1),
                    "box": [int(x0), int(y0), int(x1 - x0), int(y1 - y0)],
                }
            )
    return {"text": "\n".join(lines).strip(), "blocks": blocks, "lang": code}


def _run_openai(im, lang: str | None) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise OcrError("openai OCR needs OCR_API_KEY / OPENAI_API_KEY / CAW_API_KEY")
    buf = io.BytesIO()
    im.save(buf, format="JPEG", quality=90)
    b64 = base64.standard_b64encode(buf.getvalue()).decode("ascii")
    hint = (lang or os.environ.get("OCR_LANG") or "").strip()
    prompt = "Extract every visible character from this image. Preserve line breaks. Output text only."
    if hint:
        prompt += f" The text is primarily `{hint}`."
    body = {
        "model": api_model(),
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
                    },
                ],
            }
        ],
    }
    req = urllib.request.Request(
        f"{api_base()}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")[-400:]
        raise OcrError(f"OCR API {e.code}: {err}") from e
    except Exception as e:
        raise OcrError(f"OCR API failed: {e}") from e
    text = (
        (((payload.get("choices") or [{}])[0].get("message") or {}).get("content")) or ""
    ).strip()
    return {"text": text, "blocks": [], "lang": hint or "auto"}


def ocr_image(
    path: str,
    *,
    lang: str | None = None,
    box: list[float] | None = None,
    backend: str | None = None,
    write_sidecar: bool = False,
) -> dict[str, Any]:
    src = resolve_image(path)
    used = (backend or detect_backend()).strip().lower() or "auto"
    if used in {"auto", "none", ""}:
        used = detect_backend()
    if used == "none" or not backend_available(used):
        raise OcrError(
            "no OCR backend. Install one of:\n"
            "  pip install pytesseract   # plus Tesseract-OCR on PATH (chi_sim+eng)\n"
            "  pip install easyocr\n"
            "  pip install paddleocr paddlepaddle\n"
            "or set OCR_API_KEY / OPENAI_API_KEY and use a vision model (OCR_MODEL=gpt-4o-mini)."
        )
    im = _open_rgb(src, box)
    if used == "tesseract":
        result = _run_tesseract(im, lang)
    elif used == "easyocr":
        result = _run_easyocr(im, lang)
    elif used == "paddleocr":
        result = _run_paddle(im, lang)
    elif used == "openai":
        result = _run_openai(im, lang)
    else:
        raise OcrError(f"unknown backend `{used}`")
    result["ok"] = True
    result["path"] = str(src)
    result["backend"] = used
    result["width"], result["height"] = im.size
    if write_sidecar:
        dest = src.with_suffix(".ocr.txt")
        dest.write_text(str(result.get("text") or ""), encoding="utf-8")
        result["sidecar"] = str(dest)
    return result


DEFAULT_PIP = ["Pillow", "pytesseract"]


def install_deps(packages: list[str] | None = None) -> dict[str, Any]:
    """Install Python extras into *this* interpreter (the MCP server)."""
    import subprocess
    import sys

    pkgs = [p.strip() for p in (packages or DEFAULT_PIP) if str(p).strip()]
    if not pkgs:
        raise OcrError("packages is empty")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *pkgs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        raise OcrError(f"pip failed to start: {e}") from e
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise OcrError(f"pip install failed ({proc.returncode}):\n{out[-4000:]}")
    return {
        "ok": True,
        "python": sys.executable,
        "packages": pkgs,
        "log": out[-4000:],
        "available": {
            "tesseract": backend_available("tesseract"),
            "easyocr": backend_available("easyocr"),
            "paddleocr": backend_available("paddleocr"),
            "openai": backend_available("openai"),
        },
        "tesseract_bin": which_tesseract(),
        "next": (
            "If tesseract_bin is null, install the Tesseract-OCR *program* "
            "(install_program method=winget package=UB-Mannheim.TesseractOCR on Windows, "
            "or brew/apt tesseract). Then retry ocr_image. "
            "Heavier engines: ocr_install_deps packages=[\"easyocr\"]"
        ),
    }


def status() -> dict[str, Any]:
    backend = detect_backend()
    return {
        "ok": True,
        "backend": backend,
        "available": {
            "tesseract": backend_available("tesseract"),
            "easyocr": backend_available("easyocr"),
            "paddleocr": backend_available("paddleocr"),
            "openai": backend_available("openai"),
        },
        "tesseract": which_tesseract(),
        "api_base": api_base() if backend_available("openai") else None,
        "api_model": api_model() if backend_available("openai") else None,
        "api_key_set": bool(api_key()),
        "cwd": str(Path.cwd()),
        "env": {
            "OCR_BACKEND": os.environ.get("OCR_BACKEND", "auto"),
            "OCR_LANG": os.environ.get("OCR_LANG") or None,
            "OCR_MODEL": os.environ.get("OCR_MODEL") or None,
        },
        "hint": (
            "Python extras: call ocr_install_deps (Pillow + pytesseract into this Python).\n"
            "Tesseract *binary* is a system app — install_program "
            "method=winget package=UB-Mannheim.TesseractOCR (Windows) "
            "or brew/apt tesseract. chi_sim traineddata needed for Chinese.\n"
            "Or set OCR_API_KEY and use backend=openai."
        ),
    }
