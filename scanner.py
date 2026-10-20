#!/usr/bin/env python3
"""PDF Dork Metadata Scanner - herramienta educativa de OSINT sobre metadatos de PDFs."""

import argparse
import json
import os
import sys
import time
from pathlib import Path

# allow running from any cwd
BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from modules.search import search_all
from modules.downloader import download_pdf
from modules.exif import run_exiftool, flatten_tags, get_text_pdf
from modules.analyzer import analyze_metadata, analyze_text, sort_findings
from modules.report import print_summary, print_findings, save_json, save_text

BANNER = r"""
 ____  ____  ____    ____  ____  ____  ____  ____  ____
|  _ \|  _ \|  _ \  |  _ \|  _ \|  _ \|  _ \|  _ \|  _ \
| |_) | |_) | | | | | |_) | | | | | | | | | | | | | |_) |
|  __/|  __/| |_| | |  __/| |_| | |_| | |_| | |_| |  __/
|_|   |_|   |____/  |_|   |____/|____/|____/|____/|_|

  PDF Dork Metadata Scanner  (educativo)
"""


def parse_args():
    p = argparse.ArgumentParser(
        description="Descarga PDFs asociados a un dominio (Google dorks), extrae metadatos con exiftool y filtra info sensible."
    )
    p.add_argument("domain", nargs="?", help="Dominio objetivo (ej: example.com)")
    p.add_argument("-o", "--output", default="./results", help="Directorio de salida (default: ./results)")
    p.add_argument("--urls-file", help="Archivo con lista de URLs de PDFs (una por línea)")
    p.add_argument("--engines", default="google,bing,duckduckgo", help="Motores separados por coma")
    p.add_argument("--max-results", type=int, default=50, help="Máximo de URLs por motor")
    p.add_argument("--max-size", type=int, default=50, help="Tamaño máximo de PDF en MB")
    p.add_argument("--delay", type=float, default=1.0, help="Delay entre requests (s)")
    p.add_argument("--timeout", type=int, default=30, help="Timeout de descarga (s)")
    p.add_argument("--analyze-text", action="store_true", help="También analizar texto del PDF (requiere pdftotext)")
    p.add_argument("--no-download", action="store_true", help="Solo buscar URLs, no descargar")
    p.add_argument("--min-severity", choices=["high", "medium", "low", "info"], default="low",
                   help="Severidad mínima a mostrar (default: low)")
    p.add_argument("--json-only", action="store_true", help="No imprimir tabla, solo guardar JSON")
    return p.parse_args()


SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2, "info": 3}


def main():
    args = parse_args()
    print(BANNER)

    if not args.domain and not args.urls_file:
        print("Error: indica un dominio o --urls-file")
        sys.exit(1)

    outdir = os.path.abspath(args.output)
    pdf_dir = os.path.join(outdir, "pdfs")
    os.makedirs(outdir, exist_ok=True)

    urls: set = set()
    if args.urls_file:
        with open(args.urls_file, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    urls.add(line)
        print(f"[*] Cargadas {len(urls)} URLs desde archivo")

    if args.domain:
        engines = [e.strip() for e in args.engines.split(",") if e.strip()]
        print(f"[*] Buscando PDFs para dominio: {args.domain}")
        print(f"    Motores: {', '.join(engines)}")
        found = search_all(args.domain, engines, max_results=args.max_results, delay=args.delay)
        print(f"[*] URLs encontradas: {len(found)}")
        urls |= found

    if not urls:
        print("[!] No se encontraron URLs de PDF.")
        sys.exit(0)

    # Save URL list
    with open(os.path.join(outdir, "urls.txt"), "w", encoding="utf-8") as fh:
        for u in sorted(urls):
            fh.write(u + "\n")

    if args.no_download:
        print("[*] Modo --no-download: terminado.")
        sys.exit(0)

    # Download
    downloaded = []  # list of (url, path)
    failed = []
    print(f"[*] Descargando {len(urls)} PDFs...")
    for i, u in enumerate(sorted(urls), 1):
        print(f"  [{i}/{len(urls)}] {u}")
        path, err = download_pdf(u, pdf_dir, timeout=args.timeout, max_size_mb=args.max_size, delay=args.delay)
        if path:
            downloaded.append((u, path))
        else:
            failed.append((u, err))
            print(f"     -> fallo: {err}")
        time.sleep(args.delay)

    # Analyze
    all_findings = []
    all_meta = []
    print(f"[*] Analizando metadatos con exiftool ({len(downloaded)} archivos)...")
    for url, path in downloaded:
        meta = run_exiftool(path)
        flat = flatten_tags(meta.get("tags", {}))
        all_meta.append({"url": url, "file": path, "tags": meta.get("tags", {}), "error": meta.get("error")})
        if meta.get("error"):
            print(f"  [!] {os.path.basename(path)}: {meta['error']}")
            continue
        fnds = analyze_metadata(flat, path)
        if args.analyze_text:
            txt = get_text_pdf(path)
            if txt:
                fnds += analyze_text(txt, path)
        all_findings.extend(fnds)

    # Filter by severity
    min_rank = SEVERITY_RANK[args.min_severity]
    filtered = [f for f in all_findings if SEVERITY_RANK.get(f["severity"], 9) <= min_rank]
    filtered = sort_findings(filtered)

    # Report
    print_summary(urls, downloaded, failed, filtered)
    if not args.json_only:
        print_findings(filtered)

    report_data = {
        "domain": args.domain,
        "urls": sorted(urls),
        "downloaded": [{"url": u, "path": p} for u, p in downloaded],
        "failed": [{"url": u, "error": e} for u, e in failed],
        "findings": filtered,
        "metadata": all_meta,
    }
    jpath = save_json(outdir, report_data)
    tpath = save_text(outdir, filtered)
    print(f"\n[*] Reporte JSON: {jpath}")
    print(f"[*] Hallazgos TXT: {tpath}")


if __name__ == "__main__":
    main()
