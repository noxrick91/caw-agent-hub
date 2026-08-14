# Document MCP for caw-agent

stdio MCP that extracts **text from common documents** so the model can analyze them.

caw-agent also extracts these formats automatically when you paste / `@`-mention a file. This pack is for page/sheet control and when the built-in extract needs a Python PDF engine.

## Tools

| Tool | What it does |
|------|----------------|
| `doc_status` | Backends (zip Office, pdftotext, pypdf, pandoc) |
| `doc_extract` | Document → text (optional PDF pages / Excel sheet) |

## Formats

| Kind | How |
|------|-----|
| `.docx` `.pptx` `.xlsx` | Built-in (zip + XML) |
| `.odt` `.ods` `.odp` `.epub` | Built-in (zip) |
| `.html` `.rtf` `.csv` | Built-in |
| `.pdf` | `pdftotext` (poppler) or `pip install pypdf` |
| `.doc` `.xls` `.ppt` | `pandoc` on PATH |

## Setup

```text
/mcp install doc
pip install pypdf
```

Reload: `/mcp reload`.

## Skills

`mcp/doc/skills/doc-extract` — discovered automatically.

Scanned PDFs have no text — use OCR MCP on page images instead.
