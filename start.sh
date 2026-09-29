#!/usr/bin/env bash
# FILMIUM ćelija — univerzalni pokretač (Linux ulaz). Ako NIJE Linux, predaje start.bat.
set -e
cd "$(dirname "$0")"
OS="$(uname -s 2>/dev/null || echo Unknown)"
case "$OS" in
  Linux) : ;;
  *) echo "Detektovan '$OS' (nije Linux) -> predajem start.bat i gasim se."
     if command -v cmd.exe >/dev/null 2>&1; then cmd.exe /c start.bat; else cmd /c start.bat 2>/dev/null || ./start.bat; fi
     exit 0 ;;
esac
# Chromium (Electron) frameless prozor — isti engine kao Windows WebView2,
# ~4x brži od WebKitGTK na teškim CSS efektima (blur/glass) uz NVIDIA.
# Deljeni AI runtime — razreši (i bootstrap-uj ako fali) preko bundlovane skripte:
_D="$(dirname "$(readlink -f "$0")")"
RUNTIME="$(sh "$_D/bootstrap-ai-runtime.sh")" || { echo "AI runtime nije obezbedjen (v. dependencies.json)."; exit 1; }
SHELL_DIR="$RUNTIME/cell-shell"
if [ -x "$SHELL_DIR/node_modules/.bin/electron" ]; then
  exec "$SHELL_DIR/node_modules/.bin/electron" "$SHELL_DIR" "$PWD" --no-sandbox
fi
# Fallback 1: WebKit2GTK prozor
if python3 -c 'import gi; gi.require_version("Gtk","3.0"); gi.require_version("WebKit2","4.1"); from gi.repository import Gtk, WebKit2' 2>/dev/null; then
  exec python3 cell_window.py
fi
# Fallback 2: server + browser
echo "UPOZORENJE: nema Electron ni WebKit2 — otvaram u browseru."
if [ -x ".venv-linux/bin/python" ]; then PY=".venv-linux/bin/python"; else PY="python3"; fi
PORT="$(python3 -c 'import json;print(json.load(open("cell.json")).get("port",4801))' 2>/dev/null || echo 4801)"
HOST="127.0.0.1"; URL="http://$HOST:$PORT"
( for i in $(seq 1 40); do command -v curl >/dev/null 2>&1 && curl -sf "$URL" >/dev/null 2>&1 && break; sleep 0.25; done
  command -v xdg-open >/dev/null 2>&1 && xdg-open "$URL" >/dev/null 2>&1 || true ) &
exec "$PY" -m uvicorn cell_app:app --host "$HOST" --port "$PORT"
