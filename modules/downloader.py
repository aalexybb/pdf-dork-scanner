"""Descarga segura de PDFs."""

import hashlib
import os
import re
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple

import requests

DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _safe_filename(url: str) -> str:
    name = os.path.basename(urllib.parse.urlparse(url).path)
    if not name:
        name = "document.pdf"
    # sanitize
    name = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    # avoid overly long
    if len(name) > 120:
        name = name[:100] + ".pdf"
    return name


def download_pdf(
    url: str,
    outdir: str,
    timeout: int = 30,
    max_size_mb: int = 50,
    delay: float = 0.0,
) -> Tuple[Optional[str], Optional[str]]:
    """Descarga un PDF. Devuelve (path, error)."""
    Path(outdir).mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": DEFAULT_UA, "Accept": "application/pdf,*/*"}
    try:
        r = requests.get(url, headers=headers, timeout=timeout, stream=True, allow_redirects=True)
    except Exception as e:
        return None, f"request error: {e}"
    if r.status_code != 200:
        return None, f"HTTP {r.status_code}"
    ctype = r.headers.get("Content-Type", "").lower()
    if "pdf" not in ctype and not url.lower().endswith(".pdf"):
        # still try if content starts with %PDF
        pass
    # size check
    cl = r.headers.get("Content-Length")
    if cl and int(cl) > max_size_mb * 1024 * 1024:
        return None, f"too large ({cl} bytes)"
    data = bytearray()
    for chunk in r.iter_content(chunk_size=8192):
        if chunk:
            data.extend(chunk)
            if len(data) > max_size_mb * 1024 * 1024:
                return None, "too large (stream)"
    if len(data) < 100:
        return None, "empty response"
    if not data.startswith(b"%PDF"):
        return None, "not a PDF (magic bytes)"
    h = hashlib.sha256(bytes(data)).hexdigest()[:12]
    base = _safe_filename(url)
    stem, ext = os.path.splitext(base)
    fname = f"{stem}_{h}{ext}"
    path = os.path.join(outdir, fname)
    # avoid overwrite collision by hash already unique
    with open(path, "wb") as f:
        f.write(data)
    return path, None
