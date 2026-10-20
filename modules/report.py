"""Generación de informes."""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()


def print_summary(urls_found, downloaded, failed, findings):
    console.print(Panel.fit(
        f"URLs encontradas: {len(urls_found)}\n"
        f"PDFs descargados: {len(downloaded)}\n"
        f"Descargas fallidas: {len(failed)}\n"
        f"Hallazgos: {len(findings)}",
        title="Resumen",
    ))


def print_findings(findings: List[Dict[str, Any]]):
    if not findings:
        console.print("[green]No se encontró información sensible.[/green]")
        return
    table = Table(title="Hallazgos sensibles", show_lines=True)
    table.add_column("Sev", style="bold")
    table.add_column("Archivo")
    table.add_column("Campo")
    table.add_column("Valor")
    table.add_column("Motivo")
    sev_color = {"high": "red", "medium": "yellow", "low": "cyan", "info": "dim"}
    for f in findings:
        table.add_row(
            f"[{sev_color.get(f['severity'],'white')}]{f['severity']}[/]",
            os.path.basename(f["file"]),
            f["field"],
            str(f["value"])[:80],
            f["reason"],
        )
    console.print(table)


def save_json(outdir: str, data: Dict[str, Any]) -> str:
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(outdir, f"report_{ts}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
    return path


def save_text(outdir: str, findings: List[Dict[str, Any]]) -> str:
    os.makedirs(outdir, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(outdir, f"findings_{ts}.txt")
    with open(path, "w", encoding="utf-8") as fh:
        for f in findings:
            fh.write(f"[{f['severity'].upper()}] {os.path.basename(f['file'])} | {f['field']} = {f['value']}  ({f['reason']})\n")
    return path
