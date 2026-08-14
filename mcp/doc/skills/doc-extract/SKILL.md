---
name: doc-extract
description: Extract text from PDF, Word, Excel, PowerPoint, ODT, EPUB, HTML, RTF, and CSV with the doc MCP. Use when the user asks to read a document, pull PDF pages, an Excel sheet, or when pasted/@ file text is missing or too long.
---

# Document extract

Use `mcp__doc__*`. Do not invent document contents.

Pasted / `@` documents are often already inlined by caw-agent — call this pack only when you need a **page range**, an **Excel sheet**, a sidecar, or the inline extract failed.

## Tools

| Tool | When |
|------|------|
| `doc_status` | First step — zip Office always on; PDF via pdftotext or pypdf; pandoc for legacy `.doc` |
| `doc_extract` | Document → text |
| `doc_install_deps` | Missing **Python** pypdf |

## Formats

| Kind | How |
|------|-----|
| `.docx` `.pptx` `.xlsx` (and `*m`) | Built-in zip + XML |
| `.odt` `.ods` `.odp` `.epub` | Built-in zip |
| `.html` `.rtf` `.csv` `.tsv` `.txt` `.md` | Built-in |
| `.pdf` | `pdftotext` (Poppler) or `pypdf` |
| `.doc` `.xls` `.ppt` | `pandoc` on PATH |

## Flow

1. `doc_status` if PDF/legacy and you are unsure of backends.
2. `doc_extract` `path`.
   - PDF pages → `pages=[1,2,3]` (1-based)
   - Excel → `sheet=Sheet1` or a 1-based index
   - persist → `write_sidecar=true` (`<file>.txt` next to the source)
3. Return the text (and sidecar path if written).

Same MCP server is one-at-a-time. Different documents can be requested together; overlapping `path` stays serial.

## Missing backends

| Gap | Fix |
|-----|-----|
| no pypdf | `doc_install_deps` |
| no `pdftotext` | `install_program` for Poppler |
| no pandoc (`.doc`/`.xls`/`.ppt`) | `install_program` for pandoc |

Do **not** use `install_program` for pypdf.

## Scanned PDFs

`doc_extract` returns little or no text. Render/export page images, then `/skill ocr-extract` (`ocr_image`).
