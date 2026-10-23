"""Búsqueda de PDFs asociados a un dominio mediante motores de búsqueda."""

import base64
import re
import time
import urllib.parse
from typing import Set, List, Optional

import requests
from bs4 import BeautifulSoup


DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def _normalize_url(u: str) -> Optional[str]:
    if not u:
        return None
    u = u.strip()
    # Google redirect wrapper
    m = re.search(r"[?&]q=(https?://[^&]+)", u)
    if m:
        u = urllib.parse.unquote(m.group(1))
    if u.startswith("/url?"):
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(u).query)
        if "q" in qs:
            u = qs["q"][0]
    if not u.startswith("http"):
        return None
    # keep pdf-ish urls
    path = urllib.parse.urlparse(u).path.lower()
    if not (path.endswith(".pdf") or "pdf" in path):
        # allow if query suggests pdf? be permissive but filter later
        pass
    return u.split("#")[0]


def _decode_bing_redirect(href: str) -> str:
    """Bing envuelve los resultados en /ck/a?...&u=a1<base64>."""
    if "bing.com/ck/a" not in href:
        return href
    qs = urllib.parse.parse_qs(urllib.parse.urlparse(href).query)
    encoded = qs.get("u", [None])[0]
    if not encoded:
        return href
    if encoded.startswith("a1"):
        encoded = encoded[2:]
    encoded = encoded.replace("-", "+").replace("_", "/")
    encoded += "=" * (-len(encoded) % 4)
    try:
        decoded = base64.urlsafe_b64decode(encoded).decode("utf-8")
    except Exception:
        return href
    return decoded if decoded.startswith("http") else href


def _is_pdf_url(u: str) -> bool:
    p = urllib.parse.urlparse(u).path.lower()
    return p.endswith(".pdf") or ".pdf" in p


def search_google(domain: str, max_results: int = 50, delay: float = 1.0) -> Set[str]:
    urls: Set[str] = set()
    q = f"site:{domain} filetype:pdf"
    start = 0
    while len(urls) < max_results and start < max_results:
        params = {"q": q, "num": 100, "start": start}
        headers = {"User-Agent": DEFAULT_UA, "Accept-Language": "es,en;q=0.9"}
        try:
            r = requests.get("https://www.google.com/search", params=params, headers=headers, timeout=20)
        except Exception:
            break
        if r.status_code != 200:
            break
        if "enablejs" in r.text or "consent.google.com" in r.text:
            print("[!] Google requiere JavaScript/consentimiento; se omite este motor.")
            break
        soup = BeautifulSoup(r.text, "lxml")
        found_this_page = 0
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            nu = _normalize_url(href)
            if nu and _is_pdf_url(nu) and domain in urllib.parse.urlparse(nu).netloc:
                if nu not in urls:
                    urls.add(nu)
                    found_this_page += 1
        if found_this_page == 0:
            break
        start += 10
        time.sleep(delay)
    return urls


def search_bing(domain: str, max_results: int = 50, delay: float = 1.0) -> Set[str]:
    urls: Set[str] = set()
    q = f"site:{domain} filetype:pdf"
    page = 1
    while len(urls) < max_results:
        params = {"q": q, "count": 50, "first": (page - 1) * 50 + 1}
        headers = {"User-Agent": DEFAULT_UA}
        try:
            r = requests.get("https://www.bing.com/search", params=params, headers=headers, timeout=20)
        except Exception:
            break
        if r.status_code != 200:
            break
        soup = BeautifulSoup(r.text, "lxml")
        found_this_page = 0
        for a in soup.select("li.b_algo h2 a, a[href]"):
            href = _decode_bing_redirect(a.get("href", ""))
            if not href.startswith("http"):
                continue
            if _is_pdf_url(href) and domain in urllib.parse.urlparse(href).netloc:
                if href not in urls:
                    urls.add(href)
                    found_this_page += 1
        if found_this_page == 0:
            break
        page += 1
        time.sleep(delay)
    return urls


def search_duckduckgo(domain: str, max_results: int = 50, delay: float = 1.0) -> Set[str]:
    urls: Set[str] = set()
    q = f"site:{domain} filetype:pdf"
    headers = {"User-Agent": DEFAULT_UA}
    try:
        r = requests.post(
            "https://html.duckduckgo.com/html/",
            data={"q": q},
            headers=headers,
            timeout=20,
        )
    except Exception:
        return urls
    if r.status_code != 200:
        return urls
    soup = BeautifulSoup(r.text, "lxml")
    for a in soup.select("a.result__a, a[href]"):
        href = a.get("href", "")
        # DDG wraps in redirect
        m = re.search(r"uddg=([^&]+)", href)
        if m:
            href = urllib.parse.unquote(m.group(1))
        if href.startswith("http") and _is_pdf_url(href) and domain in urllib.parse.urlparse(href).netloc:
            urls.add(href)
    return urls


def search_wayback(domain: str, max_results: int = 50, delay: float = 1.0) -> Set[str]:
    """Respaldo: descubre PDFs archivados por Wayback CDX.

    Sirve cuando Google/Bing/DDG devuelven CAPTCHA, JavaScript o resultados
    vacíos. No sustituye a un buscador, pero encuentra URLs PDF del dominio.
    """
    urls: Set[str] = set()
    from_year = int(time.strftime("%Y")) - 2
    params = {
        "url": f"{domain}/*",
        "output": "json",
        "filter": "urlkey:.*pdf.*",
        "collapse": "urlkey",
        "fl": "original,timestamp,statuscode,mimetype",
        "limit": str(max(100, max_results * 5)),
        "from": str(from_year),
    }
    headers = {"User-Agent": DEFAULT_UA}
    try:
        r = requests.get(
            "https://web.archive.org/cdx/search/cdx",
            params=params,
            headers=headers,
            timeout=40,
        )
    except Exception as e:
        print(f"[!] Wayback CDX: {e}")
        return urls
    if r.status_code != 200:
        print(f"[!] Wayback CDX: HTTP {r.status_code}")
        return urls
    try:
        rows = r.json()
    except Exception as e:
        print(f"[!] Wayback CDX: respuesta no JSON ({e})")
        return urls
    if not rows:
        return urls

    parsed = []
    for row in rows[1:]:
        if len(row) < 4:
            continue
        original, timestamp, status, mimetype = row[:4]
        p = urllib.parse.urlparse(original)
        if domain not in p.netloc:
            continue
        if not p.path.lower().endswith(".pdf"):
            continue
        if status not in ("200", "-", ""):
            continue
        parsed.append((timestamp or "", original.split("#")[0]))

    # Quedarse con las capturas más recientes.
    parsed.sort(key=lambda x: x[0], reverse=True)
    for _, original in parsed:
        urls.add(original)
        if len(urls) >= max_results:
            break
    return urls


ENGINES = {
    "google": search_google,
    "bing": search_bing,
    "duckduckgo": search_duckduckgo,
    "wayback": search_wayback,
}


def search_all(domain: str, engines: List[str], max_results: int = 50, delay: float = 1.0) -> Set[str]:
    out: Set[str] = set()
    requested = {e.strip().lower() for e in engines}
    for eng in engines:
        fn = ENGINES.get(eng.lower())
        if not fn:
            continue
        try:
            res = fn(domain, max_results=max_results, delay=delay)
            out |= res
        except Exception as e:
            print(f"[!] Error en {eng}: {e}")

    # Si los buscadores están bloqueados o no devuelven nada, usar el archivo.
    if not out and "wayback" not in requested:
        print("[*] Sin resultados en los motores; probando Wayback CDX como respaldo...")
        try:
            out |= search_wayback(domain, max_results=max_results, delay=delay)
        except Exception as e:
            print(f"[!] Error en Wayback CDX: {e}")
    return out
