#!/bin/sh
# Crea il pacchetto .deb in build/. Nome, versione, descrizione e link vengono da app.json.
# Uso: script/build-deb.sh   →   build/<nome>_<versione>_<arch>.deb   (sudo apt install ./build/*.deb)
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PY="$ROOT/venv/bin/python"; [ -x "$PY" ] || PY=python3
j() {  # j autore.nome → valore in app.json
    "$PY" -c 'import functools, json, sys
print(functools.reduce(dict.__getitem__, sys.argv[2].split("."), json.load(open(sys.argv[1], encoding="utf-8"))))' \
        "$ROOT/app.json" "$1"
}
NAME="$(j nome)"; VER="$(j versione)"
PKG="$(printf %s "$NAME" | tr 'A-Z ' 'a-z-')"   # nome del pacchetto e del comando: syglami-pdf
ARCH="$(dpkg --print-architecture)"
STAGE="$ROOT/build/pkg"; APP="$STAGE/opt/$PKG"; ICONS="$STAGE/usr/share/icons/hicolor"

rm -rf "$STAGE"
mkdir -p "$APP" "$STAGE/DEBIAN" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/doc/$PKG" \
         "$ICONS/scalable/apps" "$ICONS/256x256/apps"

cd "$ROOT"
cp -r app.json firma_pdf.py generatore.py vettorizza.py icona.png icona.svg timbro.svg LICENSE sigla "$APP/"
# PyMuPDF, potracer e Hershey-Fonts non sono nei repository di Ubuntu: viaggiano nel pacchetto.
# --no-deps: numpy arriva da python3-numpy, gli extra di PyMuPDF (layout, OCR) non servono.
"$PY" -m pip install -q --no-deps --target "$APP/vendor" -r requirements.txt
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
cp icona.svg "$ICONS/scalable/apps/$PKG.svg"
cp icona.png "$ICONS/256x256/apps/$PKG.png"

cat > "$STAGE/usr/bin/$PKG" <<RUN
#!/bin/sh
PYTHONPATH="/opt/$PKG/vendor\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 /opt/$PKG/firma_pdf.py "\$@"
RUN
chmod 755 "$STAGE/usr/bin/$PKG"

# stesso lanciatore di install.sh (il nome del file è APP_ID di sigla/config.py), ma col comando di sistema
cat > "$STAGE/usr/share/applications/$PKG.desktop" <<DESK
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Firma PDF
Comment=$(j descrizione)
Keywords=firma;pdf;sign;signature;
Exec=$PKG %f
Icon=$PKG
Terminal=false
Categories=Office;
MimeType=application/pdf;
StartupWMClass=$NAME
DESK

cat > "$STAGE/usr/share/doc/$PKG/copyright" <<COPY
$NAME — Copyright (C) $(j anno) $(j autore.nome)
Licenza: $(j licenza.nome), senza alcuna garanzia. Testo completo: /opt/$PKG/LICENSE
Sorgente: $(j autore.github)

Componenti inclusi in /opt/$PKG/vendor (licenze nelle rispettive cartelle *.dist-info):
  PyMuPDF (AGPL-3.0), potracer (GPL-2.0-or-later), Hershey-Fonts (MIT)
Icone derivate da Lucide (ISC): Copyright (c) Lucide Contributors 2022;
  parti Copyright (c) Cole Bemis 2013-2022 (Feather, MIT). https://lucide.dev/license
COPY

# il pacchetto deve funzionare col python di sistema e i soli moduli inclusi: se manca qualcosa, fallisce qui
PYTHONPATH="$APP/vendor" /usr/bin/python3 -c "import sys; sys.path.insert(0, '$APP')
import pymupdf, potrace, HersheyFonts, sigla.config, sigla.pdf, generatore, vettorizza"

chmod -R u=rwX,go=rX "$STAGE"
cat > "$STAGE/DEBIAN/control" <<CTRL
Package: $PKG
Version: $VER
Architecture: $ARCH
Maintainer: $(j autore.nome) <giuseppeCappadonna@users.noreply.github.com>
Depends: python3 (>= 3.10), python3-pyqt6, python3-numpy
Section: utils
Priority: optional
Homepage: $(j autore.github)
Installed-Size: $(du -sk --exclude=DEBIAN "$STAGE" | cut -f1)
Description: $(j descrizione)
CTRL

DEB="$ROOT/build/${PKG}_${VER}_${ARCH}.deb"
dpkg-deb --root-owner-group --build "$STAGE" "$DEB" >/dev/null
rm -rf "$STAGE"
echo "Creato: $DEB"
