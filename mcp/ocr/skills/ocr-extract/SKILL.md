---
name: ocr-extract
description: Extract printed or handwritten-ish text from images with the OCR MCP (Tesseract, EasyOCR, Paddle, vision API). Use when the user asks to OCR, read text from a screenshot/photo, 识别文字, or extract captions from an image.
---

# OCR extract

Use `mcp__ocr__*`. Do not invent the text — always call `ocr_image`.

Same MCP server is one-at-a-time. OCR on **different** images can share one assistant message with other packs (e.g. image cutout of another file).

## Tools

| Tool | When |
|------|------|
| `ocr_status` | First step — backend + Tesseract path + API key |
| `ocr_languages` | Language ids per backend |
| `ocr_image` | Image → text |
| `ocr_install_deps` | Missing **Python** extras (Pillow, pytesseract, easyocr, paddleocr) |

## Flow

1. `ocr_status` (can share a turn with `ocr_languages` if the lang id is unclear).
2. `ocr_image` with a workspace-relative `path`.
   - mixed Chinese/English → Tesseract `lang=chi_sim+eng` (default); EasyOCR `ch_sim,en`; Paddle `ch`
   - Traditional Chinese → `chi_tra` / `ch_tra` / `chinese_cht`
   - one region → `box=[x,y,w,h]`
   - persist → `write_sidecar=true` (writes `<stem>.ocr.txt`)
   - force engine → `backend=tesseract|easyocr|paddleocr|openai`
3. Return `text` (and sidecar path if written).

## Missing backends

| Gap | Fix |
|-----|-----|
| no pytesseract / Pillow | `ocr_install_deps` (same Python as this MCP) |
| want EasyOCR / Paddle | `ocr_install_deps` `packages=["easyocr"]` or `["paddleocr","paddlepaddle"]` |
| no `tesseract` **binary** | `install_program` method=`winget` package=`UB-Mannheim.TesseractOCR` (Windows) or brew/apt `tesseract` |
| no local engine | set `OCR_API_KEY` and `backend=openai` |

Then retry `ocr_image`. Do **not** use `install_program` for pip packages.

## Related

Scanned PDF pages: render/export page images, then this skill — `doc_extract` returns empty on image-only PDFs.
