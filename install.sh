#!/usr/bin/env bash
# Instalador de pdf-dork-scanner
set -e

REPO="https://github.com/aalexybb/pdf-dork-scanner.git"
DEST="${DEST:-$HOME/pdf-dork-scanner}"

echo "[*] Instalando pdf-dork-scanner..."

if ! command -v git >/dev/null 2>&1; then
    echo "[!] git no esta instalado. Instalalo primero (apt install git)."
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "[!] python3 no esta instalado."
    exit 1
fi

if [ -d "$DEST/.git" ]; then
    echo "[*] El repositorio ya existe en $DEST, actualizando..."
    git -C "$DEST" pull --ff-only
else
    echo "[*] Clonando en $DEST..."
    git clone "$REPO" "$DEST"
fi

cd "$DEST"

if ! command -v exiftool >/dev/null 2>&1; then
    echo "[!] exiftool no esta instalado."
    echo "    En Debian/Ubuntu: sudo apt install libimage-exiftool-perl"
    echo "    La herramienta seguira funcionando para busqueda/descarga, pero no podra leer metadatos."
fi

echo "[*] Instalando dependencias de Python..."
python3 -m pip install --user -r requirements.txt

echo ""
echo "[OK] Instalacion completa."
echo "     Ejecuta: cd $DEST && python3 scanner.py --help"
