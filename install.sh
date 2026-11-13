#!/bin/sh
# Installa l'app (nome da app.json) per l'utente corrente: venv con dipendenze, lanciatore in "Mostra applicazioni", icona.
set -e
DIR="$(cd "$(dirname "$0")" && pwd)"
[ -x "$DIR/venv/bin/python" ] || python3 -m venv --system-site-packages "$DIR/venv"
"$DIR/venv/bin/python" -m pip install -q -r "$DIR/requirements.txt"
NAME="$("$DIR/venv/bin/python" -c 'import json, sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["nome"])' "$DIR/app.json")"
ID="$(printf %s "$NAME" | tr 'A-Z ' 'a-z-')"   # come APP_ID in sigla/config.py
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor"
mkdir -p "$APPS"
# il lanciatore delle versioni precedenti si chiamava sigla.desktop
rm -f "$APPS/sigla.desktop"
# l'icona è indicata col percorso del file: quella copiata nel tema (versioni precedenti) restava vecchia o
# assente in «Mostra applicazioni» finché non si riavviava la sessione
rm -f "$ICONS/scalable/apps/sigla.svg" "$ICONS/256x256/apps/sigla.png"
# scritto a parte e poi rinominato: GNOME si accorge subito del lanciatore cambiato (es. nuovo nome)
cat > "$APPS/$ID.desktop.tmp" <<DESK
[Desktop Entry]
Type=Application
Name=$NAME
GenericName=Firma PDF
Comment=Firma i tuoi PDF trascinando la tua firma sulla pagina
Keywords=firma;pdf;sign;signature;
Exec=$DIR/firma.sh %f
Icon=$DIR/icona.svg
Terminal=false
Categories=Office;
MimeType=application/pdf;
StartupWMClass=$NAME
DESK
mv "$APPS/$ID.desktop.tmp" "$APPS/$ID.desktop"
update-desktop-database "$APPS" 2>/dev/null || true
# lo script Nautilus «Firma con Sigla» non esiste più: rimuove quello delle versioni precedenti
rm -f "$HOME/.local/share/nautilus/scripts/Firma con Sigla"
gtk-update-icon-cache -f -t "$ICONS" 2>/dev/null || true
echo "$NAME installata."
