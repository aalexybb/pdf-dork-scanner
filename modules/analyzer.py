"""Análisis de metadatos para detectar información sensible."""

import re
from typing import Dict, List, Any

# Cada hallazgo: {category, severity, field, value, pattern}
FINDINGS: List[Dict[str, Any]] = []

PATTERNS = [
    # (nombre, severidad, regex, categoría)
    ("email", "high", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "PII"),
    ("ipv4", "medium", re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b"), "network"),
    ("ipv6", "medium", re.compile(r"\b(?:[A-Fa-f0-9]{1,4}:){7}[A-Fa-f0-9]{1,4}\b"), "network"),
    ("win_path", "medium", re.compile(r"[A-Za-z]:\\[^\r\n\"']{3,}"), "paths"),
    ("unix_path", "medium", re.compile(r"(?:/home|/Users|/root|/var|/etc|/opt|/tmp|/mnt|/usr)/[^\s\"']{3,}"), "paths"),
    ("phone", "medium", re.compile(r"(?:\+?\d{1,3}[\s-]?)?(?:\(?\d{2,4}\)?[\s-]?)?\d{3,4}[\s-]?\d{3,4}"), "PII"),
    ("url_internal", "low", re.compile(r"https?://(?:localhost|127\.|10\.|192\.168\.|172\.(?:1[6-9]|2\d|3[01])\.)[^\s\"']*"), "network"),
]

# Campos de metadatos que suelen contener info sensible directamente
SENSITIVE_FIELDS = {
    "Author": "high",
    "Creator": "medium",
    "Producer": "low",
    "Software": "low",
    "Company": "medium",
    "Manager": "medium",
    "LastModifiedBy": "medium",
    "Title": "low",
    "Subject": "low",
    "Keywords": "low",
    "CreatorTool": "low",
    "XMP:CreatorTool": "low",
}

# Campos GPS
GPS_FIELDS = {"GPSLatitude", "GPSLongitude", "GPSPosition", "GPSAltitude"}


# Grupos de exiftool que son ruido local (no metadatos del documento original)
SKIP_PREFIXES = ("System.", "ExifTool.", "SourceFile", "File.")


def _skip(k: str) -> bool:
    return any(k == p.rstrip(".") or k.startswith(p) for p in SKIP_PREFIXES)


def analyze_metadata(flat_tags: Dict[str, str], file_path: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    # 1. Campos sensibles directos
    for field, sev in SENSITIVE_FIELDS.items():
        for k, v in flat_tags.items():
            if _skip(k):
                continue
            if k == field or k.endswith("." + field) or k.lower().endswith(field.lower()):
                if v and v.strip() and v.strip().lower() not in ("", "none", "n/a"):
                    findings.append({
                        "file": file_path,
                        "category": "metadata",
                        "severity": sev,
                        "field": k,
                        "value": v.strip(),
                        "reason": f"Campo sensible '{field}' presente",
                    })

    # 2. GPS
    for k, v in flat_tags.items():
        if _skip(k):
            continue
        if "ref" in k.lower():
            continue
        if any(g.lower() in k.lower() for g in GPS_FIELDS):
            if v and v.strip():
                findings.append({
                    "file": file_path,
                    "category": "gps",
                    "severity": "high",
                    "field": k,
                    "value": v.strip(),
                    "reason": "Coordenadas GPS en metadatos",
                })

    # 3. Patrones regex sobre todos los valores
    seen = set()
    for k, v in flat_tags.items():
        if _skip(k) or not v:
            continue
        for name, sev, regex, cat in PATTERNS:
            for m in regex.finditer(v):
                val = m.group(0)
                key = (k, name, val)
                if key in seen:
                    continue
                seen.add(key)
                findings.append({
                    "file": file_path,
                    "category": cat,
                    "severity": sev,
                    "field": k,
                    "value": val,
                    "reason": f"Patrón '{name}' detectado",
                })

    # 4. Fechas (informativo)
    for k, v in flat_tags.items():
        if _skip(k):
            continue
        if "date" in k.lower() or "time" in k.lower():
            if v and v.strip():
                findings.append({
                    "file": file_path,
                    "category": "dates",
                    "severity": "info",
                    "field": k,
                    "value": v.strip(),
                    "reason": "Fecha/hora en metadatos",
                })

    return findings


def analyze_text(text: str, file_path: str) -> List[Dict[str, Any]]:
    """Analiza texto extraído del PDF (opcional)."""
    findings: List[Dict[str, Any]] = []
    if not text:
        return findings
    seen = set()
    for name, sev, regex, cat in PATTERNS:
        for m in regex.finditer(text):
            val = m.group(0)
            if (name, val) in seen:
                continue
            seen.add((name, val))
            findings.append({
                "file": file_path,
                "category": cat,
                "severity": sev,
                "field": "body_text",
                "value": val,
                "reason": f"Patrón '{name}' en texto del PDF",
            })
    # emails already covered; add a few extra keywords
    kw_regex = re.compile(r"\b(?:password|passwd|secret|token|api[_-]?key|confidential|internal use only)\b", re.I)
    for m in kw_regex.finditer(text):
        findings.append({
            "file": file_path,
            "category": "keywords",
            "severity": "medium",
            "field": "body_text",
            "value": m.group(0),
            "reason": "Palabra clave sensible en texto",
        })
    return findings


SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2, "info": 3}


def sort_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(findings, key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["category"], f["file"]))
