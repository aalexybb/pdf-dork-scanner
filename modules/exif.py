"""Wrapper de exiftool para extraer metadatos de PDFs."""

import json
import os
import subprocess
from typing import Dict, Any, Optional


def run_exiftool(path: str, timeout: int = 60) -> Dict[str, Any]:
    """Ejecuta exiftool y devuelve dict con metadatos (o error)."""
    result = {"file": path, "tags": {}, "error": None, "raw": None}
    try:
        proc = subprocess.run(
            ["exiftool", "-json", "-a", "-u", "-g1", path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        result["error"] = "exiftool no encontrado en PATH"
        return result
    except subprocess.TimeoutExpired:
        result["error"] = "timeout exiftool"
        return result
    if proc.returncode != 0 and not proc.stdout:
        result["error"] = proc.stderr.strip() or "exiftool error"
        return result
    try:
        parsed = json.loads(proc.stdout)
        if isinstance(parsed, list) and parsed:
            result["tags"] = parsed[0]
            result["raw"] = parsed[0]
        else:
            result["tags"] = {}
    except json.JSONDecodeError as e:
        result["error"] = f"json parse error: {e}"
        result["raw"] = proc.stdout
    return result


def flatten_tags(tags: Dict[str, Any], prefix: str = "") -> Dict[str, str]:
    """Aplana tags anidados (grupos exiftool) a clave->valor string."""
    out: Dict[str, str] = {}
    for k, v in (tags or {}).items():
        key = f"{prefix}{k}" if not prefix else f"{prefix}.{k}"
        if isinstance(v, dict):
            out.update(flatten_tags(v, key))
        elif isinstance(v, list):
            out[key] = ", ".join(str(x) for x in v)
        else:
            out[key] = "" if v is None else str(v)
    return out


def get_text_pdf(path: str) -> Optional[str]:
    """Extrae texto del PDF si pdftotext está disponible."""
    try:
        proc = subprocess.run(
            ["pdftotext", "-layout", path, "-"],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout
