# OCR MCP for caw-agent

stdio MCP server that extracts **text from images**.

Uses **Content-Length** JSON-RPC framing (same as speech / image MCP).

## Tools

| Tool | What it does |
|------|----------------|
| `ocr_status` | Backend, Tesseract path, API key |
| `ocr_languages` | Common language ids |
| `ocr_image` | Image → text (+ optional word boxes) |

## Backends (auto)

1. **tesseract** — `pip install pytesseract` + [Tesseract-OCR](https://github.com/tesseract-ocr/tesseract) on PATH (`chi_sim` + `eng` recommended)
2. **easyocr** — `pip install easyocr`
3. **paddleocr** — `pip install paddleocr paddlepaddle` (strong Chinese)
4. **openai** — vision chat API when `OCR_API_KEY` / `OPENAI_API_KEY` / `CAW_API_KEY` is set

Override with `OCR_BACKEND=tesseract|easyocr|paddleocr|openai|auto`.

## Setup

```text
/mcp install ocr
pip install Pillow pytesseract
```

Install Tesseract itself (Windows scoop example):

```powershell
scoop install tesseract
# Chinese traineddata if missing:
# copy chi_sim.traineddata into TESSDATA_PREFIX
```

Or skip the local engine and use a vision model:

```text
OCR_API_KEY=sk-…
OCR_BASE_URL=https://api.openai.com/v1
OCR_MODEL=gpt-4o-mini
```

Reload: `/mcp reload`.

## Typical agent flow

1. `ocr_status`
2. `ocr_image` with a workspace-relative `path`
   - `lang=chi_sim+eng` for mixed Chinese/English
   - `box=[x,y,w,h]` to read one region
   - `write_sidecar=true` to save `.ocr.txt`

## Skills

`mcp/ocr/skills/ocr-extract` — discovered automatically.

## Env

| Variable | Meaning |
|----------|---------|
| `OCR_BACKEND` | `auto` (default) / `tesseract` / `easyocr` / `paddleocr` / `openai` |
| `OCR_LANG` | Default language (`chi_sim+eng`, `ch_sim,en`, `ch`, …) |
| `OCR_API_KEY` | Vision API token |
| `OCR_BASE_URL` | OpenAI-compatible root |
| `OCR_MODEL` | Vision model id (default `gpt-4o-mini`) |
| `TESSERACT_CMD` | Full path to `tesseract.exe` if not on PATH |
| `OCR_MCP_LOG` | Log file |
