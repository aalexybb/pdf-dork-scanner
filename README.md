# PDF Dork Scanner

Herramienta educativa de ciberseguridad/OSINT. Busca PDFs asociados a un
dominio, los descarga, extrae sus metadatos con exiftool y senala la
informacion que podria ser sensible (autores, emails, rutas internas,
software, versiones, coordenadas GPS, fechas, etc.).

Uso pensado para auditorias propias, CTFs y aprendizaje. No la uses contra
dominios sobre los que no tengas autorizacion.

## Requisitos

- Python 3.10 o superior
- exiftool instalado en el sistema
- (Opcional) pdftotext, si quieres analizar tambien el texto del PDF

En Debian/Ubuntu:

    sudo apt install libimage-exiftool-perl poppler-utils
    pip install -r requirements.txt

## Instalacion rapida

    wget -qO- https://raw.githubusercontent.com/aalexybb/pdf-dork-scanner/main/install.sh | bash

El script clona el repositorio en ~/pdf-dork-scanner, instala las
dependencias de Python y comprueba que exiftool este disponible.

## Uso

Buscar por dominio:

    python3 scanner.py example.com -o ./results

Solo algunos motores:

    python3 scanner.py example.com --engines google,bing --max-results 30

Usar solo el archivo Wayback (util si los buscadores bloquean):

    python3 scanner.py example.com --engines wayback --max-results 30

Analizar tambien el texto del PDF:

    python3 scanner.py example.com --analyze-text

A partir de una lista de URLs:

    python3 scanner.py --urls-file urls.txt -o ./results

Solo listar URLs, sin descargar:

    python3 scanner.py example.com --no-download

Filtrar por severidad minima:

    python3 scanner.py example.com --min-severity medium

## Que produce

En el directorio de salida:

- urls.txt: URLs encontradas
- pdfs/: PDFs descargados
- report_<fecha>.json: reporte completo con metadatos y hallazgos
- findings_<fecha>.txt: hallazgos en texto plano

## Como funciona

1. Busqueda. Usa dorks del tipo `site:dominio filetype:pdf` contra Google,
   con respaldo en Bing y DuckDuckGo. Si los tres devuelven CAPTCHA, exigen
   JavaScript o no dan resultados, usa Wayback CDX para descubrir PDFs
   archivados del dominio.
2. Descarga. Valida que el archivo sea un PDF real (cabecera %PDF), limita
   el tamano y sanea los nombres de archivo.
3. Metadatos. Ejecuta exiftool con salida JSON y aplana los grupos.
4. Analisis. Aplica patrones y heurísticas sobre los campos: emails, IPs,
   rutas Windows/Unix, telefonos, coordenadas GPS, fechas, y campos conocidos
   como Author, Creator, Producer, Title, etc.
5. Informe. Muestra una tabla en consola y guarda JSON y texto.

## Estructura del proyecto

    pdf-dork-scanner/
    ├── scanner.py
    ├── modules/
    │   ├── search.py
    │   ├── downloader.py
    │   ├── exif.py
    │   ├── analyzer.py
    │   └── report.py
    ├── install.sh
    ├── requirements.txt
    └── README.md

## Notas

- Google puede devolver CAPTCHA; por eso se incluyen Bing y DuckDuckGo.
- Los metadatos se extraen del archivo descargado, no del original en el
  servidor.
- La deteccion es heuristica: puede haber falsos positivos, sobre todo en
  numeros y fechas. Revisa siempre el JSON completo.
