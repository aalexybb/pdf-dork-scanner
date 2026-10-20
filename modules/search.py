"""Búsqueda de PDFs asociados a un dominio mediante motores de búsqueda."""

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
            href = a.get("href", "")
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


ENGINES = {
    "google": search_google,
    "bing": search_bing,
    "duckduckgo": search_duckduckgo,
}


def search_all(domain: str, engines: List[str], max_results: int = 50, delay: float = 1.0) -> Set[str]:
    out: Set[str] = set()
    for eng in engines:
        fn = ENGINES.get(eng.lower())
        if not fn:
            continue
        try:
            res = fn(domain, max_results=max_results, delay=delay)
            out |= res
        except Exception as e:
            print(f"[!] Error en {eng}: {e}")
    return out
