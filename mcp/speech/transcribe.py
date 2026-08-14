"""Speech-to-text backends: faster-whisper, openai-whisper, OpenAI-compatible HTTP."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


AUDIO_EXTS = {
    ".wav",
    ".mp3",
    ".m4a",
    ".aac",
    ".flac",
    ".ogg",
    ".oga",
    ".opus",
    ".webm",
    ".wma",
    ".mp4",
    ".mkv",
    ".mov",
    ".avi",
}


class SpeechError(RuntimeError):
    pass


def which_ffmpeg() -> str | None:
    return shutil.which("ffmpeg")


def api_key() -> str | None:
    for key in (
        "SPEECH_API_KEY",
        "OPENAI_API_KEY",
        "CAW_API_KEY",
        "GROQ_API_KEY",
    ):
        val = os.environ.get(key, "").strip()
        if val:
            return val
    return None


def api_base() -> str:
    raw = (
        os.environ.get("SPEECH_BASE_URL")
        or os.environ.get("OPENAI_BASE_URL")
        or "https://api.openai.com/v1"
    ).strip()
    return raw.rstrip("/")


def configured_model(backend: str) -> str:
    env = os.environ.get("SPEECH_MODEL", "").strip()
    if env:
        return env
    if backend == "openai":
        return "whisper-1"
    return os.environ.get("SPEECH_LOCAL_MODEL", "base").strip() or "base"


def detect_backend() -> str:
    forced = os.environ.get("SPEECH_BACKEND", "auto").strip().lower() or "auto"
    if forced != "auto":
        return forced
    try:
        import faster_whisper  # noqa: F401

        return "faster-whisper"
    except Exception:
        pass
    try:
        import whisper  # noqa: F401

        return "whisper"
    except Exception:
        pass
    if api_key():
        return "openai"
    return "none"


def backend_available(name: str) -> bool:
    if name == "faster-whisper":
        try:
            import faster_whisper  # noqa: F401

            return True
        except Exception:
            return False
    if name == "whisper":
        try:
            import whisper  # noqa: F401

            return True
        except Exception:
            return False
    if name == "openai":
        return bool(api_key())
    return False


DEFAULT_PIP = ["faster-whisper", "sounddevice", "numpy"]


def install_deps(packages: list[str] | None = None) -> dict[str, Any]:
    import sys

    pkgs = [p.strip() for p in (packages or DEFAULT_PIP) if str(p).strip()]
    if not pkgs:
        raise SpeechError("packages is empty")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *pkgs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except Exception as e:
        raise SpeechError(f"pip failed to start: {e}") from e
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise SpeechError(f"pip install failed ({proc.returncode}):\n{out[-4000:]}")
    return {
        "ok": True,
        "python": sys.executable,
        "packages": pkgs,
        "log": out[-4000:],
        "available": {
            "faster-whisper": backend_available("faster-whisper"),
            "whisper": backend_available("whisper"),
            "openai": backend_available("openai"),
        },
        "ffmpeg": which_ffmpeg(),
        "next": (
            "If ffmpeg is null, install_program method=winget package=Gyan.FFmpeg "
            "(needed for m4a/mp4). Then retry transcribe_file."
        ),
    }


def resolve_audio(path: str) -> Path:
    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        raise SpeechError("path is required")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        p = p.resolve()
    except OSError as e:
        raise SpeechError(f"cannot resolve path: {e}") from e
    if not p.is_file():
        raise SpeechError(f"audio/video not found: {p}")
    return p


def looks_like_audio(path: Path) -> bool:
    return path.suffix.lower() in AUDIO_EXTS


# Containers that Whisper often cannot open without an explicit ffmpeg decode.
_NEEDS_FFMPEG = {".m4a", ".aac", ".mp4", ".mkv", ".mov", ".avi", ".wma", ".webm"}


def ensure_decodable(path: Path) -> tuple[Path, Path | None]:
    """Return `(audio_path, temp_dir)`. temp_dir is cleaned up by the caller."""
    suffix = path.suffix.lower()
    if suffix not in _NEEDS_FFMPEG:
        return path, None
    ff = which_ffmpeg()
    if not ff:
        raise SpeechError(
            f"`{suffix}` needs ffmpeg on PATH to decode (install ffmpeg, then retry)."
        )
    tmp = Path(tempfile.mkdtemp(prefix="caw-speech-dec-"))
    wav = tmp / (path.stem + ".wav")
    cmd = [
        ff,
        "-y",
        "-i",
        str(path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "pcm_s16le",
        str(wav),
    ]
    try:
        subprocess.run(
            cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=600,
        )
    except subprocess.CalledProcessError as e:
        err = (e.stderr or b"").decode("utf-8", errors="replace")[-400:]
        shutil.rmtree(tmp, ignore_errors=True)
        raise SpeechError(f"ffmpeg failed to decode {path.name}: {err}") from e
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    if not wav.is_file():
        shutil.rmtree(tmp, ignore_errors=True)
        raise SpeechError(f"ffmpeg produced no wav for {path.name}")
    return wav, tmp


def fmt_ts(seconds: float, *, srt: bool) -> str:
    if seconds < 0:
        seconds = 0.0
    ms = int(round(seconds * 1000))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    sep = "," if srt else "."
    return f"{h:02d}:{m:02d}:{s:02d}{sep}{milli:03d}"


def segments_to_srt(segments: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        start = float(seg.get("start") or 0)
        end = float(seg.get("end") or start)
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        lines.append(str(i))
        lines.append(f"{fmt_ts(start, srt=True)} --> {fmt_ts(end, srt=True)}")
        lines.append(text)
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def segments_to_vtt(segments: list[dict[str, Any]]) -> str:
    out = ["WEBVTT", ""]
    for seg in segments:
        start = float(seg.get("start") or 0)
        end = float(seg.get("end") or start)
        text = str(seg.get("text") or "").strip()
        if not text:
            continue
        out.append(f"{fmt_ts(start, srt=False)} --> {fmt_ts(end, srt=False)}")
        out.append(text)
        out.append("")
    return "\n".join(out)


def write_sidecar(src: Path, text: str, fmt: str) -> str | None:
    ext = {"": ".txt", "text": ".txt", "txt": ".txt", "srt": ".srt", "vtt": ".vtt", "json": ".json"}.get(
        fmt.lower(), ".txt"
    )
    dest = src.with_suffix(ext)
    dest.write_text(text, encoding="utf-8")
    return str(dest)


def probe_duration(path: Path) -> float | None:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return None
    try:
        out = subprocess.check_output(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=30,
        )
        return float(out.strip())
    except Exception:
        return None


def transcribe_file(
    path: str,
    *,
    language: str | None = None,
    translate: bool = False,
    timestamps: bool = True,
    write_sidecar: bool = False,
    sidecar_format: str = "txt",
    model: str | None = None,
    backend: str | None = None,
) -> dict[str, Any]:
    src = resolve_audio(path)
    backend = (backend or detect_backend()).strip().lower()
    if backend in ("auto", "none", ""):
        backend = detect_backend()
    if backend == "none" or not backend_available(backend):
        raise SpeechError(
            "no speech backend. Install one of:\n"
            "  pip install faster-whisper   # recommended local\n"
            "  pip install openai-whisper   # official whisper\n"
            "or set SPEECH_API_KEY / OPENAI_API_KEY and use the OpenAI-compatible API "
            "(optional SPEECH_BASE_URL, e.g. https://api.groq.com/openai/v1)."
        )
    model_id = (model or configured_model(backend)).strip()
    lang = (language or os.environ.get("SPEECH_LANGUAGE") or "").strip() or None

    if backend == "openai":
        result = _run_openai_api(src, model_id, lang, translate, timestamps)
    elif backend in ("faster-whisper", "whisper"):
        audio, tmp = ensure_decodable(src)
        try:
            if backend == "faster-whisper":
                result = _run_faster_whisper(audio, model_id, lang, translate, timestamps)
            else:
                result = _run_openai_whisper(audio, model_id, lang, translate, timestamps)
        finally:
            if tmp is not None:
                shutil.rmtree(tmp, ignore_errors=True)
    else:
        raise SpeechError(f"unknown backend `{backend}` (faster-whisper|whisper|openai)")

    result["ok"] = True
    result["path"] = str(src)
    result["backend"] = backend
    result["model"] = model_id
    if result.get("duration") is None:
        result["duration"] = probe_duration(src)

    if write_sidecar:
        fmt = (sidecar_format or "txt").lower()
        if fmt in ("srt",) and result.get("segments"):
            body = segments_to_srt(result["segments"])
        elif fmt in ("vtt",) and result.get("segments"):
            body = segments_to_vtt(result["segments"])
        elif fmt == "json":
            body = json.dumps(result, ensure_ascii=False, indent=2)
        else:
            body = str(result.get("text") or "")
        result["sidecar"] = write_sidecar(src, body, fmt)
    return result


def _run_faster_whisper(
    src: Path,
    model_id: str,
    language: str | None,
    translate: bool,
    timestamps: bool,
) -> dict[str, Any]:
    from faster_whisper import WhisperModel

    device = os.environ.get("SPEECH_DEVICE", "auto").strip() or "auto"
    compute = os.environ.get("SPEECH_COMPUTE_TYPE", "default").strip() or "default"
    kwargs: dict[str, Any] = {}
    if device != "auto":
        kwargs["device"] = device
    if compute != "default":
        kwargs["compute_type"] = compute
    model = WhisperModel(model_id, **kwargs)
    segments_iter, info = model.transcribe(
        str(src),
        language=language,
        task="translate" if translate else "transcribe",
        vad_filter=True,
    )
    segments: list[dict[str, Any]] = []
    texts: list[str] = []
    for seg in segments_iter:
        text = (seg.text or "").strip()
        item = {"start": float(seg.start), "end": float(seg.end), "text": text}
        segments.append(item)
        if text:
            texts.append(text)
    out: dict[str, Any] = {
        "text": " ".join(texts).strip(),
        "language": getattr(info, "language", language),
        "duration": getattr(info, "duration", None),
    }
    if timestamps:
        out["segments"] = segments
    return out


def _run_openai_whisper(
    src: Path,
    model_id: str,
    language: str | None,
    translate: bool,
    timestamps: bool,
) -> dict[str, Any]:
    import whisper

    model = whisper.load_model(model_id)
    kwargs: dict[str, Any] = {
        "task": "translate" if translate else "transcribe",
        "fp16": False,
    }
    if language:
        kwargs["language"] = language
    result = model.transcribe(str(src), **kwargs)
    segments = []
    for seg in result.get("segments") or []:
        segments.append(
            {
                "start": float(seg.get("start") or 0),
                "end": float(seg.get("end") or 0),
                "text": str(seg.get("text") or "").strip(),
            }
        )
    out: dict[str, Any] = {
        "text": str(result.get("text") or "").strip(),
        "language": result.get("language") or language,
    }
    if timestamps:
        out["segments"] = segments
    return out


def _run_openai_api(
    src: Path,
    model_id: str,
    language: str | None,
    translate: bool,
    timestamps: bool,
) -> dict[str, Any]:
    key = api_key()
    if not key:
        raise SpeechError("SPEECH_API_KEY / OPENAI_API_KEY is not set")
    url = api_base() + ("/audio/translations" if translate else "/audio/transcriptions")
    resp_fmt = "verbose_json" if timestamps else "json"
    fields: list[tuple[str, str]] = [
        ("model", model_id),
        ("response_format", resp_fmt),
    ]
    if language and not translate:
        fields.append(("language", language))
    body, content_type = _multipart(src, fields)
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": content_type,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            raw = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SpeechError(f"API {e.code} from {url}: {detail[:800]}") from e
    except urllib.error.URLError as e:
        raise SpeechError(f"API request failed: {e}") from e
    data = json.loads(raw)
    if isinstance(data, str):
        return {"text": data.strip()}
    segments = []
    for seg in data.get("segments") or []:
        segments.append(
            {
                "start": float(seg.get("start") or 0),
                "end": float(seg.get("end") or 0),
                "text": str(seg.get("text") or "").strip(),
            }
        )
    out: dict[str, Any] = {
        "text": str(data.get("text") or "").strip(),
        "language": data.get("language") or language,
        "duration": data.get("duration"),
    }
    if timestamps and segments:
        out["segments"] = segments
    return out


def _multipart(path: Path, fields: list[tuple[str, str]]) -> tuple[bytes, str]:
    boundary = "----cawSpeechBoundary7MA4YWxkTrZu0gW"
    chunks: list[bytes] = []
    for name, value in fields:
        chunks.append(f"--{boundary}\r\n".encode("ascii"))
        chunks.append(
            f'Content-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8")
        )
    filename = path.name
    mime = "application/octet-stream"
    chunks.append(f"--{boundary}\r\n".encode("ascii"))
    chunks.append(
        (
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("utf-8")
    )
    chunks.append(path.read_bytes())
    chunks.append(b"\r\n")
    chunks.append(f"--{boundary}--\r\n".encode("ascii"))
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def list_input_devices() -> list[dict[str, Any]]:
    try:
        import sounddevice as sd
    except Exception as e:
        raise SpeechError(
            f"sounddevice is not installed ({e}). pip install sounddevice numpy"
        ) from e
    out: list[dict[str, Any]] = []
    for i, dev in enumerate(sd.query_devices()):
        if int(dev.get("max_input_channels") or 0) <= 0:
            continue
        out.append(
            {
                "id": i,
                "name": dev.get("name"),
                "channels": dev.get("max_input_channels"),
                "default_samplerate": dev.get("default_samplerate"),
            }
        )
    return out


def record_wav(seconds: float, device: int | None, dest: Path) -> Path:
    try:
        import numpy as np
        import sounddevice as sd
        import wave
    except Exception as e:
        raise SpeechError(
            f"recording needs sounddevice + numpy ({e}). pip install sounddevice numpy"
        ) from e
    if seconds <= 0 or seconds > 600:
        raise SpeechError("seconds must be between 0 and 600")
    sr = 16_000
    frames = int(seconds * sr)
    rec = sd.rec(frames, samplerate=sr, channels=1, dtype="int16", device=device)
    sd.wait()
    dest.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(dest), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(np.asarray(rec).tobytes())
    return dest


def record_and_transcribe(
    seconds: float,
    *,
    device: int | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    tmp = Path(tempfile.mkdtemp(prefix="caw-speech-"))
    wav = tmp / "clip.wav"
    try:
        record_wav(seconds, device, wav)
        result = transcribe_file(str(wav), **kwargs)
        result["recording"] = str(wav)
        return result
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


if __name__ == "__main__":
    import argparse
    import sys

    if len(sys.argv) == 1:
        segs = [
            {"start": 0.0, "end": 1.2, "text": "hello"},
            {"start": 1.2, "end": 2.0, "text": "world"},
        ]
        srt = segments_to_srt(segs)
        assert "00:00:00,000 --> 00:00:01,200" in srt
        assert "hello" in srt
        print("transcribe helpers ok")
        raise SystemExit(0)

    parser = argparse.ArgumentParser(description="Transcribe an audio/video file")
    parser.add_argument("path")
    parser.add_argument("--text", action="store_true", help="print transcript only")
    args = parser.parse_args()
    try:
        result = transcribe_file(args.path)
    except SpeechError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(2) from e
    if args.text:
        print(result.get("text") or "")
    else:
        print(json.dumps(result, ensure_ascii=False))
