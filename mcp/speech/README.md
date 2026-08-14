# Speech MCP for caw-agent

stdio MCP server that gives **caw-agent** speech-to-text tools.

Uses **Content-Length** JSON-RPC framing (same as FreeCAD / Blender MCP).

## Tools

| Tool | What it does |
|------|----------------|
| `speech_status` | Backend, model, ffmpeg, API key |
| `list_speech_models` | Common Whisper / API model ids |
| `transcribe_file` | Audio/video file → text (+ optional SRT/VTT) |
| `list_input_devices` | Microphones (`sounddevice`) |
| `record_and_transcribe` | Record N seconds from the mic, then STT |

## Backends (auto)

1. **faster-whisper** — local, recommended (`pip install faster-whisper`)
2. **openai-whisper** — official Whisper package
3. **openai** — HTTP `POST /v1/audio/transcriptions` when `SPEECH_API_KEY` / `OPENAI_API_KEY` / `CAW_API_KEY` is set

Override with `SPEECH_BACKEND=faster-whisper|whisper|openai|auto`.

ffmpeg on `PATH` helps decode mp3 / m4a / mp4.

## Setup

```text
/mcp install speech
```

Then install a backend (once):

```powershell
pip install faster-whisper
# optional mic:
pip install sounddevice numpy
```

Or use a hosted Whisper API:

```text
SPEECH_API_KEY=sk-…
SPEECH_BASE_URL=https://api.openai.com/v1
SPEECH_MODEL=whisper-1
```

Groq example: `SPEECH_BASE_URL=https://api.groq.com/openai/v1` and `SPEECH_MODEL=whisper-large-v3`.

Reload MCP after install: `/mcp reload`.

## Typical agent flow

1. `speech_status`
2. `transcribe_file` with `path` (workspace-relative is fine)
3. Optional `write_sidecar=true`, `sidecar_format=srt` for subtitles
4. Live mic: `list_input_devices` → `record_and_transcribe` (`seconds=10`, `language=zh`)

## Skills

`mcp/speech/skills/speech-to-text` — discovered automatically.

## Env

| Variable | Meaning |
|----------|---------|
| `SPEECH_BACKEND` | `auto` (default) / `faster-whisper` / `whisper` / `openai` |
| `SPEECH_MODEL` | `base`, `large-v3`, `whisper-1`, … |
| `SPEECH_LANGUAGE` | Default language hint (`zh`, `en`, …) |
| `SPEECH_API_KEY` | API token (falls back to `OPENAI_API_KEY` / `CAW_API_KEY`) |
| `SPEECH_BASE_URL` | OpenAI-compatible root (default `https://api.openai.com/v1`) |
| `SPEECH_DEVICE` | faster-whisper device (`cpu` / `cuda` / `auto`) |
| `SPEECH_COMPUTE_TYPE` | faster-whisper compute type |
| `SPEECH_MCP_LOG` | Log file (stderr if unset) |
