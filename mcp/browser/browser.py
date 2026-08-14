"""Headless Chromium session for the browser MCP (Playwright).

No arbitrary JavaScript evaluate. Navigation is http(s) only.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

SKIP_ROLES = frozenset({"generic", "none", "inlinetextbox", "ignored", "presentation"})
MAX_REFS = 200
MAX_TYPE_CHARS = 8000
KEY_RE = re.compile(r"^[A-Za-z0-9]+(?:\+[A-Za-z0-9]+)*$")
DEFAULT_TIMEOUT_MS = 30_000


class BrowserError(Exception):
    pass


def _timeout_ms() -> int:
    raw = os.environ.get("BROWSER_TIMEOUT_MS", "").strip()
    if raw.isdigit():
        return max(1_000, min(int(raw), 120_000))
    return DEFAULT_TIMEOUT_MS


def _want_headed(explicit: bool | None) -> bool:
    if explicit is not None:
        return bool(explicit)
    return os.environ.get("BROWSER_HEADED", "").strip().lower() in ("1", "true", "yes")


def validate_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        raise BrowserError("missing url")
    parsed = urlparse(u)
    if parsed.scheme in ("file", "javascript", "data", "about"):
        raise BrowserError(f"refusing {parsed.scheme or 'empty'} URL")
    if parsed.scheme not in ("http", "https"):
        raise BrowserError("only http/https URLs are allowed")
    if not parsed.netloc:
        raise BrowserError("URL missing host")
    return u


def _validate_key(key: str) -> str:
    k = (key or "").strip()
    if not k or len(k) > 40 or not KEY_RE.fullmatch(k):
        raise BrowserError(
            "invalid key (use Enter, Tab, Escape, Control+a, ArrowDown, …)"
        )
    return k


def _workspace_root() -> Path:
    return Path.cwd().resolve()


def resolve_media_path(user: str | None) -> Path:
    root = _workspace_root()
    if user and str(user).strip():
        raw = Path(str(user).strip())
        if ".." in raw.parts:
            raise BrowserError("screenshot path escapes workspace")
        dest = raw.resolve() if raw.is_absolute() else (root / raw).resolve()
    else:
        dest = root / ".caw-agent" / "media" / f"browser-{int(time.time())}.png"
    try:
        dest.relative_to(root)
    except ValueError as e:
        raise BrowserError("screenshot path must stay in the workspace") from e
    if dest.name in {"secrets.json", "config.json"} and ".caw-agent" in dest.parts:
        raise BrowserError("refusing to write secrets/config")
    dest.parent.mkdir(parents=True, exist_ok=True)
    return dest


def playwright_imported() -> bool:
    try:
        import playwright  # noqa: F401

        return True
    except Exception:
        return False


@dataclass
class BrowserSession:
    playwright: Any = None
    browser: Any = None
    context: Any = None
    page: Any = None
    refs: dict[str, dict[str, Any]] = field(default_factory=dict)
    headed: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


SESSION = BrowserSession()


def status() -> dict[str, Any]:
    open_ = SESSION.page is not None
    url = None
    title = None
    if open_:
        try:
            url = SESSION.page.url
            title = SESSION.page.title()
        except Exception:
            url = None
            title = None
    return {
        "ok": True,
        "playwright": playwright_imported(),
        "session": "open" if open_ else "closed",
        "url": url,
        "title": title,
        "headed": SESSION.headed if open_ else _want_headed(None),
        "refs": len(SESSION.refs),
        "hint": (
            None
            if playwright_imported()
            else "call browser_install_deps (pip playwright + chromium), then retry"
        ),
    }


def install_deps(packages: list[str] | None = None) -> dict[str, Any]:
    allowed = {"playwright"}
    pkgs = [p.strip() for p in (packages or ["playwright"]) if str(p).strip()]
    extra = [p for p in pkgs if p.split("==")[0].split(">=")[0].lower() not in allowed]
    if extra:
        raise BrowserError(f"refusing packages {extra} (only playwright)")
    cmd = [sys.executable, "-m", "pip", "install", "--upgrade", "playwright"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except Exception as e:
        raise BrowserError(f"pip failed to start: {e}") from e
    out = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        raise BrowserError(f"pip install failed ({proc.returncode}):\n{out[-4000:]}")
    inst = [
        sys.executable,
        "-m",
        "playwright",
        "install",
        "chromium",
    ]
    try:
        proc2 = subprocess.run(inst, capture_output=True, text=True, timeout=600)
    except Exception as e:
        raise BrowserError(f"playwright install failed to start: {e}") from e
    out2 = ((proc2.stdout or "") + "\n" + (proc2.stderr or "")).strip()
    if proc2.returncode != 0:
        raise BrowserError(
            f"playwright install chromium failed ({proc2.returncode}):\n{out2[-4000:]}"
        )
    return {
        "ok": True,
        "python": sys.executable,
        "packages": ["playwright"],
        "browser": "chromium",
        "log": (out + "\n" + out2)[-4000:],
        "available": status(),
        "next": "browser_open (optionally with url). Linux missing libs: playwright install --with-deps chromium",
    }


def _import_sync_playwright() -> Any:
    try:
        from playwright.sync_api import sync_playwright

        return sync_playwright
    except Exception as e:
        raise BrowserError(
            f"playwright is not installed ({e}). Call browser_install_deps."
        ) from e


def _page() -> Any:
    if SESSION.page is None:
        raise BrowserError("no open page — call browser_open first")
    return SESSION.page


def close() -> dict[str, Any]:
    with SESSION.lock:
        return _close_unlocked()


def _close_unlocked() -> dict[str, Any]:
    errors: list[str] = []
    for attr in ("context", "browser"):
        obj = getattr(SESSION, attr)
        if obj is not None:
            try:
                obj.close()
            except Exception as e:
                errors.append(f"{attr}: {e}")
            setattr(SESSION, attr, None)
    SESSION.page = None
    SESSION.refs.clear()
    pw = SESSION.playwright
    SESSION.playwright = None
    SESSION.headed = False
    if pw is not None:
        try:
            pw.stop()
        except Exception as e:
            errors.append(f"playwright: {e}")
    return {"ok": True, "closed": True, "warnings": errors or None}


def open_browser(url: str | None = None, headed: bool | None = None) -> dict[str, Any]:
    target = validate_url(url) if url else None
    with SESSION.lock:
        if SESSION.page is not None:
            if target:
                SESSION.page.goto(target, wait_until="domcontentloaded", timeout=_timeout_ms())
            return _page_info("reused")
        sync_playwright = _import_sync_playwright()
        want_headed = _want_headed(headed)
        try:
            pw = sync_playwright().start()
            browser = pw.chromium.launch(headless=not want_headed)
            context = browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_default_timeout(_timeout_ms())
        except Exception as e:
            raise BrowserError(
                f"failed to launch chromium: {e}. "
                "Call browser_install_deps, or on Linux: playwright install --with-deps chromium"
            ) from e
        SESSION.playwright = pw
        SESSION.browser = browser
        SESSION.context = context
        SESSION.page = page
        SESSION.headed = want_headed
        SESSION.refs.clear()
        if target:
            page.goto(target, wait_until="domcontentloaded", timeout=_timeout_ms())
        return _page_info("opened")


def goto(url: str) -> dict[str, Any]:
    target = validate_url(url)
    with SESSION.lock:
        page = _page()
        page.goto(target, wait_until="domcontentloaded", timeout=_timeout_ms())
        SESSION.refs.clear()
        return _page_info("navigated")


def _page_info(action: str) -> dict[str, Any]:
    page = _page()
    return {
        "ok": True,
        "action": action,
        "url": page.url,
        "title": page.title(),
        "headed": SESSION.headed,
    }


def _walk_ax(node: dict[str, Any], acc: list[dict[str, Any]], depth: int) -> None:
    if len(acc) >= MAX_REFS:
        return
    role = str(node.get("role") or "").strip()
    name = str(node.get("name") or "").strip()
    if role and role.lower() not in SKIP_ROLES:
        acc.append({"role": role, "name": name, "depth": depth})
    for child in node.get("children") or []:
        if isinstance(child, dict):
            _walk_ax(child, acc, depth + 1)


def snapshot() -> dict[str, Any]:
    with SESSION.lock:
        page = _page()
        try:
            tree = page.accessibility.snapshot()
        except Exception as e:
            raise BrowserError(f"accessibility snapshot failed: {e}") from e
        items: list[dict[str, Any]] = []
        if isinstance(tree, dict):
            _walk_ax(tree, items, 0)
        seen: dict[tuple[str, str], int] = {}
        SESSION.refs.clear()
        lines: list[str] = []
        for i, item in enumerate(items, start=1):
            ref = f"e{i}"
            key = (item["role"], item["name"])
            nth = seen.get(key, 0)
            seen[key] = nth + 1
            SESSION.refs[ref] = {
                "role": item["role"],
                "name": item["name"],
                "nth": nth,
            }
            label = item["name"] or "(no name)"
            if len(label) > 80:
                label = label[:77] + "..."
            indent = "  " * min(item["depth"], 8)
            lines.append(f"{indent}[{ref}] {item['role']} {label!r}")
        return {
            "ok": True,
            "url": page.url,
            "title": page.title(),
            "refs": len(SESSION.refs),
            "tree": "\n".join(lines) if lines else "(empty)",
        }


def _locator(page: Any, ref: str | None, selector: str | None) -> Any:
    if ref:
        item = SESSION.refs.get(ref)
        if item is None:
            raise BrowserError(f"unknown ref `{ref}` — call browser_snapshot first")
        name = item["name"] or None
        loc = page.get_by_role(item["role"], name=name)
        return loc.nth(int(item.get("nth") or 0))
    sel = (selector or "").strip()
    if not sel:
        raise BrowserError("provide `ref` (from browser_snapshot) or `selector`")
    if sel.lower().startswith("javascript:"):
        raise BrowserError("refusing javascript: selector")
    if len(sel) > 500:
        raise BrowserError("selector too long")
    return page.locator(sel).first


def click(ref: str | None = None, selector: str | None = None) -> dict[str, Any]:
    with SESSION.lock:
        page = _page()
        loc = _locator(page, ref, selector)
        loc.click(timeout=_timeout_ms())
        return {"ok": True, "action": "click", "url": page.url, "title": page.title()}


def type_text(
    text: str,
    ref: str | None = None,
    selector: str | None = None,
    submit: bool = False,
) -> dict[str, Any]:
    if text is None:
        raise BrowserError("missing text")
    if len(text) > MAX_TYPE_CHARS:
        raise BrowserError(f"text longer than {MAX_TYPE_CHARS} characters")
    with SESSION.lock:
        page = _page()
        loc = _locator(page, ref, selector)
        try:
            loc.fill(text, timeout=_timeout_ms())
        except Exception:
            loc.click(timeout=_timeout_ms())
            page.keyboard.type(text, delay=10)
        if submit:
            page.keyboard.press("Enter")
        return {"ok": True, "action": "type", "url": page.url, "title": page.title()}


def press(key: str) -> dict[str, Any]:
    k = _validate_key(key)
    with SESSION.lock:
        page = _page()
        page.keyboard.press(k)
        return {"ok": True, "action": "press", "key": k, "url": page.url}


def screenshot(path: str | None = None, full_page: bool = False) -> dict[str, Any]:
    dest = resolve_media_path(path)
    with SESSION.lock:
        page = _page()
        page.screenshot(path=str(dest), full_page=bool(full_page))
        rel = dest.relative_to(_workspace_root()).as_posix()
        return {
            "ok": True,
            "action": "screenshot",
            "path": rel,
            "url": page.url,
            "title": page.title(),
        }
