---
name: speech-to-text
description: Transcribe audio, video soundtracks, or microphone input with the speech MCP (faster-whisper, Whisper, OpenAI-compatible STT). Use when the user asks to transcribe, 语音转文字, subtitles, SRT/VTT, or record from the mic. Supports wav/mp3/m4a/flac/ogg/webm/mp4.
---

# Speech to text

Use `mcp__speech__*`. Do not invent transcripts.

Same MCP server is one-at-a-time. Several **different** files can be transcribed in one message only if they do not share a path (runtime still serializes this server).

## Tools

| Tool | When |
|------|------|
| `speech_status` | First step — backend, model, ffmpeg, API key |
| `list_speech_models` | Local Whisper ids vs API model names |
| `transcribe_file` | Existing audio/video path |
| `list_input_devices` | Microphones (needs sounddevice) |
| `record_and_transcribe` | Live mic for N seconds |
| `speech_install_deps` | Missing **Python** extras (faster-whisper, sounddevice, numpy) |

## File → text

1. `speech_status`.
2. `transcribe_file` `path` (workspace-relative).
   - `language=zh` / `en` / `ja` when known (empty = auto)
   - `translate=true` → English translation
   - `timestamps=true` (default) for timed segments
   - `write_sidecar=true` + `sidecar_format=txt|srt|vtt|json`
   - `model` override (`base`, `large-v3`, `whisper-1`, …)
   - `backend=auto|faster-whisper|whisper|openai`
3. Return `text` (and sidecar path if written).

m4a / mp4 / many compressed formats need **ffmpeg** on PATH.

## Live mic

`list_input_devices` → `record_and_transcribe` (`seconds=8`–`30`, optional `device` id). Same language/translate/model/backend args. No sidecar.

## Missing backends

| Gap | Fix |
|-----|-----|
| no faster-whisper / whisper / sounddevice | `speech_install_deps` |
| no ffmpeg (m4a/mp4 decode) | `install_program` method=`winget` package=`Gyan.FFmpeg` |
| no local model | set `SPEECH_API_KEY` (or `OPENAI_API_KEY`) and `backend=openai` |

Then retry. Do **not** use `install_program` for pip packages.
