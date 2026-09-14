#!/usr/bin/env bash
# Lanzador para macOS y Linux: levanta el servidor local y abre el navegador.
# El sistema solo necesita servirse por http://; sirve cualquier servidor
# estático, así que se usa Node si está instalado y Python si no.

set -e
cd "$(dirname "$0")"
PUERTO=8123

if command -v node >/dev/null 2>&1; then
  echo "Iniciando el sistema con Node en http://localhost:$PUERTO"
  node herramientas/servidor.mjs "$PUERTO" &
elif command -v python3 >/dev/null 2>&1; then
  echo "Node no está instalado. Se usa Python, que también alcanza."
  python3 -m http.server "$PUERTO" &
else
  echo "No se encontró ni Node ni Python en esta computadora."
  echo "Instale Node desde https://nodejs.org (versión LTS) o use la versión publicada en línea."
  exit 1
fi

SERVIDOR=$!
trap 'kill $SERVIDOR 2>/dev/null' EXIT
sleep 1.5
open "http://localhost:$PUERTO" 2>/dev/null || xdg-open "http://localhost:$PUERTO" 2>/dev/null || true
echo "Listo. Abra http://localhost:$PUERTO — para detenerlo, presione Ctrl+C."
wait $SERVIDOR
