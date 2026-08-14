"""Extract text from PDF / Office / HTML / RTF / EPUB.

Used by the doc MCP and as a CLI fallback from caw-agent:

    python extract.py --text report.pdf
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

DOC_EXTS = {
    ".pdf",
    ".docx",
    ".docm",
    ".dotx",
    ".xlsx",
    ".xlsm",
    ".pptx",
    ".pptm",
    ".ppsx",
    ".odt",
    ".ods",
    ".odp",
    ".epub",
    ".rtf",
    ".html",
    ".htm",
    ".xhtml",
    ".csv",
    ".tsv",
    ".txt",
    ".md",
    ".doc",
    ".xls",
    ".ppt",
}


class DocError(RuntimeError):
    pass


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    if ":" in tag:
        return tag.rsplit(":", 1)[-1]
    return tag


def resolve_doc(path: str) -> Path:
    raw = (path or "").strip().strip('"').strip("'")
    if not raw:
        raise DocError("path is required")
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = Path.cwd() / p
    p = p.resolve()
    if not p.is_file():
        raise DocError(f"document not found: {p}")
    if p.suffix.lower() not in DOC_EXTS:
        raise DocError(f"unsupported document type: {p.suffix or '(none)'}")
    return p


def which_any(*names: str) -> str | None:
    for n in names:
        found = shutil.which(n)
        if found:
            return found
    return None


def _xml_texts(root: ET.Element, local: str) -> list[str]:
    out: list[str] = []
    for el in root.iter():
        if _local(el.tag) == local and el.text:
            out.append(el.text)
        if el.tail and _local(el.tag) == local:
            pass
    return out


def _zip_read(z: zipfile.ZipFile, name: str) -> str:
    try:
        return z.read(name).decode("utf-8", errors="replace")
    except KeyError as e:
        raise DocError(f"missing {name}") from e


def extract_docx(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        xml = _zip_read(z, "word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for p in root.iter():
        if _local(p.tag) != "p":
            continue
        parts = [t.text or "" for t in p.iter() if _local(t.tag) == "t"]
        line = "".join(parts).strip()
        if line:
            lines.append(line)
    return {"kind": "docx", "text": "\n".join(lines), "pages": None, "sheets": []}


def extract_pptx(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        slides = sorted(
            (n for n in z.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")),
            key=lambda n: n,
        )
        chunks: list[str] = []
        for i, name in enumerate(slides, 1):
            root = ET.fromstring(z.read(name))
            parts = [t.text or "" for t in root.iter() if _local(t.tag) == "t"]
            body = " ".join(p.strip() for p in parts if p and p.strip())
            if body:
                chunks.append(f"## Slide {i}\n{body}")
    return {"kind": "pptx", "text": "\n\n".join(chunks), "pages": len(slides), "sheets": []}


def extract_xlsx(path: Path, sheet: str | None = None) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        shared: list[str] = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(z.read("xl/sharedStrings.xml"))
            for si in root.iter():
                if _local(si.tag) != "si":
                    continue
                shared.append("".join(t.text or "" for t in si.iter() if _local(t.tag) == "t"))
        titles: list[str] = []
        if "xl/workbook.xml" in names:
            wb = ET.fromstring(z.read("xl/workbook.xml"))
            for el in wb.iter():
                if _local(el.tag) == "sheet":
                    titles.append(el.attrib.get("name") or f"Sheet{len(titles) + 1}")
        sheet_files = sorted(
            n for n in names if n.startswith("xl/worksheets/sheet") and n.endswith(".xml")
        )
        chunks: list[str] = []
        used: list[str] = []
        for i, name in enumerate(sheet_files):
            title = titles[i] if i < len(titles) else f"Sheet{i + 1}"
            if sheet and sheet.lower() not in {title.lower(), str(i + 1), f"sheet{i + 1}"}:
                continue
            root = ET.fromstring(z.read(name))
            rows: dict[int, dict[int, str]] = {}
            for c in root.iter():
                if _local(c.tag) != "c":
                    continue
                ref = c.attrib.get("r") or ""
                col, row = _a1(ref)
                if not col or not row:
                    continue
                kind = c.attrib.get("t", "")
                val = ""
                for child in c:
                    loc = _local(child.tag)
                    if loc == "v" and child.text:
                        val = child.text
                    elif loc == "is":
                        val = "".join(t.text or "" for t in child.iter() if _local(t.tag) == "t")
                if kind == "s":
                    try:
                        val = shared[int(val)]
                    except Exception:
                        pass
                if val:
                    rows.setdefault(row, {})[col] = val
            lines: list[str] = []
            for r in sorted(rows):
                cols = rows[r]
                width = max(cols) if cols else 0
                line = "\t".join(cols.get(c, "") for c in range(1, width + 1))
                if line.strip():
                    lines.append(line)
            if lines:
                chunks.append(f"## {title}\n" + "\n".join(lines))
                used.append(title)
    return {"kind": "xlsx", "text": "\n\n".join(chunks), "pages": None, "sheets": used or titles}


def _a1(ref: str) -> tuple[int, int]:
    col = 0
    row = 0
    for ch in ref:
        if ch.isalpha():
            col = col * 26 + (ord(ch.upper()) - 64)
        elif ch.isdigit():
            row = row * 10 + int(ch)
    return col, row


def extract_odf(path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(path) as z:
        xml = _zip_read(z, "content.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    for el in root.iter():
        if _local(el.tag) in {"p", "h"}:
            text = "".join(el.itertext()).strip()
            if text:
                lines.append(text)
    return {"kind": path.suffix.lower().lstrip("."), "text": "\n".join(lines), "pages": None, "sheets": []}


def extract_pdf(path: Path, pages: list[int] | None = None) -> dict[str, Any]:
    text = ""
    count = None
    bin_ = which_any("pdftotext")
    if bin_:
        cmd = [bin_, "-layout", "-enc", "UTF-8", "-q"]
        if pages:
            cmd += ["-f", str(min(pages)), "-l", str(max(pages))]
        cmd += [str(path), "-"]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            if proc.returncode == 0:
                text = proc.stdout or ""
        except Exception:
            text = ""
    if not text.strip():
        try:
            from pypdf import PdfReader

            reader = PdfReader(str(path))
            count = len(reader.pages)
            picked = pages or list(range(1, count + 1))
            chunks = []
            for n in picked:
                if 1 <= n <= count:
                    chunks.append(reader.pages[n - 1].extract_text() or "")
            text = "\n".join(chunks)
        except Exception:
            try:
                from PyPDF2 import PdfReader as Legacy

                reader = Legacy(str(path))
                count = len(reader.pages)
                picked = pages or list(range(1, count + 1))
                chunks = []
                for n in picked:
                    if 1 <= n <= count:
                        chunks.append(reader.pages[n - 1].extract_text() or "")
                text = "\n".join(chunks)
            except Exception as e:
                raise DocError(
                    "PDF extract needs poppler `pdftotext` or `pip install pypdf`"
                ) from e
    return {"kind": "pdf", "text": text.strip(), "pages": count, "sheets": []}


def extract_html(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"(?is)<(script|style|noscript)\b[^>]*>.*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>", "\n", raw)
    raw = re.sub(r"(?i)</(p|div|tr|h[1-6])>", "\n", raw)
    text = re.sub(r"<[^>]+>", " ", raw)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return {"kind": "html", "text": text.strip(), "pages": None, "sheets": []}


def extract_rtf(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="latin-1", errors="replace")
    out: list[str] = []
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "\\":
            i += 1
            if i >= len(raw):
                break
            nxt = raw[i]
            if nxt in "\\{}":
                out.append(nxt)
                i += 1
            elif nxt == "'":
                hexv = raw[i + 1 : i + 3]
                try:
                    out.append(chr(int(hexv, 16)))
                except Exception:
                    pass
                i += 3
            elif nxt.isalpha():
                while i < len(raw) and raw[i].isalpha():
                    i += 1
                if i < len(raw) and raw[i] == "-":
                    i += 1
                while i < len(raw) and raw[i].isdigit():
                    i += 1
                if i < len(raw) and raw[i] == " ":
                    i += 1
            else:
                i += 1
        elif ch in "{}":
            i += 1
        elif ch in "\r\n":
            i += 1
        else:
            out.append(ch)
            i += 1
    return {"kind": "rtf", "text": "".join(out).strip(), "pages": None, "sheets": []}


def extract_text(
    path: str,
    *,
    pages: list[int] | None = None,
    sheet: str | None = None,
    write_sidecar: bool = False,
) -> dict[str, Any]:
    src = resolve_doc(path)
    ext = src.suffix.lower()
    if ext == ".pdf":
        result = extract_pdf(src, pages)
    elif ext in {".docx", ".docm", ".dotx"}:
        result = extract_docx(src)
    elif ext in {".xlsx", ".xlsm"}:
        result = extract_xlsx(src, sheet)
    elif ext in {".pptx", ".pptm", ".ppsx"}:
        result = extract_pptx(src)
    elif ext in {".odt", ".ods", ".odp"}:
        result = extract_odf(src)
    elif ext in {".html", ".htm", ".xhtml"}:
        result = extract_html(src)
    elif ext == ".rtf":
        result = extract_rtf(src)
    elif ext in {".csv", ".tsv", ".txt", ".md"}:
        result = {
            "kind": ext.lstrip("."),
            "text": src.read_text(encoding="utf-8", errors="replace"),
            "pages": None,
            "sheets": [],
        }
    else:
        raise DocError(f"legacy {ext} needs pandoc on PATH")
    result["ok"] = True
    result["path"] = str(src)
    if write_sidecar:
        dest = src.with_suffix(src.suffix + ".txt")
        dest.write_text(str(result.get("text") or ""), encoding="utf-8")
        result["sidecar"] = str(dest)
    return result


def status() -> dict[str, Any]:
    pypdf = False
    try:
        import pypdf  # noqa: F401

        pypdf = True
    except Exception:
        try:
            import PyPDF2  # noqa: F401

            pypdf = True
        except Exception:
            pypdf = False
    return {
        "ok": True,
        "available": {
            "pdftotext": bool(which_any("pdftotext")),
            "pandoc": bool(which_any("pandoc")),
            "pypdf": pypdf,
            "zip_office": True,
        },
        "cwd": str(Path.cwd()),
        "hint": (
            "Office/ODF/HTML/RTF need no extras. "
            "PDF: doc_install_deps (pypdf) or install_program for pdftotext/poppler."
        ),
    }


DEFAULT_PIP = ["pypdf"]


def install_deps(packages: list[str] | None = None) -> dict[str, Any]:
    pkgs = [p.strip() for p in (packages or DEFAULT_PIP) if str(p).strip()]
    if not pkgs:
        raise DocError("packages is empty")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", *pkgs]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        raise DocError(f"pip failed to start: {e}") from e
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise DocError(f"pip install failed ({proc.returncode}):\n{out[-4000:]}")
    return {
        "ok": True,
        "python": sys.executable,
        "packages": pkgs,
        "log": out[-4000:],
        "available": status()["available"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Extract document text")
    parser.add_argument("path", nargs="?")
    parser.add_argument("--text", action="store_true", help="print plain text (for caw-agent)")
    parser.add_argument("--sheet")
    args = parser.parse_args(argv)
    if not args.path:
        print(status())
        return 0
    try:
        result = extract_text(args.path, sheet=args.sheet)
    except DocError as e:
        sys.stderr.write(f"{e}\n")
        return 1
    if args.text:
        sys.stdout.write(str(result.get("text") or ""))
        return 0
    import json

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
