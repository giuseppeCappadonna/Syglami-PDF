#!/bin/sh
# Crea l'app per macOS in build/: <nome>-<versione>-macos-<arch>.zip con dentro <nome>.app. Nome e versione da app.json.
# Va eseguito su un Mac, con Python 3, le dipendenze e PyInstaller:
#   python3 -m pip install -r requirements.txt PyQt6 numpy pyinstaller pillow && script/build-mac.sh
# Lo fa da solo il workflow .github/workflows/macos.yml a ogni release pubblicata su GitHub.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
j() { python3 -c 'import json, sys; print(json.load(open("app.json", encoding="utf-8"))[sys.argv[1]])' "$1"; }
NAME="$(j nome)"; VER="$(j versione)"
ID="$(printf %s "$NAME" | tr 'A-Z ' 'a-z-')"
ARCH="$(uname -m)"
OUT="$ROOT/build/mac"
rm -rf "$OUT"
# Pillow serve a PyInstaller per convertire icona.png nel formato icns del Mac
python3 -m PyInstaller --noconfirm --windowed --name "$NAME" --icon "$ROOT/icona.png" \
    --osx-bundle-identifier "io.github.giuseppecappadonna.$ID" \
    --add-data "$ROOT/app.json:." --add-data "$ROOT/icona.png:." --add-data "$ROOT/icona.svg:." \
    --add-data "$ROOT/timbro.svg:." --add-data "$ROOT/LICENSE:." \
    --collect-data HersheyFonts --hidden-import sigla.scansione \
    --distpath "$OUT" --workpath "$OUT/work" --specpath "$OUT" "$ROOT/firma_pdf.py"
APP="$OUT/$NAME.app"
# prova di avvio senza schermo: l'app deve restare aperta qualche secondo senza errori
QT_QPA_PLATFORM=offscreen "$APP/Contents/MacOS/$NAME" 2> "$OUT/avvio.log" &
PID=$!
sleep 10
if ! kill -0 "$PID" 2>/dev/null; then cat "$OUT/avvio.log"; echo "L'app non si avvia"; exit 1; fi
kill "$PID"
if grep -i -E "error|traceback" "$OUT/avvio.log"; then echo "Errori all'avvio"; exit 1; fi
ZIP="$ROOT/build/$NAME-$VER-macos-$ARCH.zip"
ditto -c -k --keepParent "$APP" "$ZIP"   # ditto conserva firma e attributi dell'app
echo "Creato: $ZIP"
