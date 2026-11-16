"""Test end-to-end senza schermo. Esegui:  QT_QPA_PLATFORM=offscreen venv/bin/python tests/test_app.py"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pymupdf
from PyQt6.QtCore import QPointF, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtGui import QPalette
from PyQt6.QtWidgets import QApplication, QComboBox, QDialogButtonBox, QLabel, QStyledItemDelegate, QToolButton

from sigla import aggiornamenti as A, config as C
from sigla.config import __version__, default_firma, export_firme, import_firme, INFO, load_config, MESI, save_config
from sigla.pdf import auto_placements, find_sign_spots, output_path, sigla_placements, sign_file, write_signed
from sigla.ui.dialoghi import (AboutDialog, BatchDialog, CreatorDialog, DrawDialog, MyFirmeDialog, NewFirmaDialog,
                               SettingsDialog, SiglaDialog)
from sigla.ui.finestra import MainWindow
from sigla.ui.scena import SignatureItem
from sigla.ui.tema import light_palette, STYLE
from sigla.ui.widget import FirmeList

import generatore

T = tempfile.mkdtemp(prefix="sigla-test-")
C.CONF_DIR, C.FIRME_DIR, C.CONF_FILE = T + "/conf", T + "/conf/firme", T + "/conf/config.json"  # mai la config vera

app = QApplication([])
app.setStyle("Fusion")
app.setStyleSheet(STYLE)

# generatore: deterministico per seme, diverso tra semi
assert generatore.generate("Mario Rossi", 1) == generatore.generate("Mario Rossi", 1)
assert generatore.generate("Mario Rossi", 1) != generatore.generate("Mario Rossi", 2)
svgs = {generatore.generate("Mario Rossi", 1, stile=k) for k, _ in generatore.STILI}
assert len(svgs) == len(generatore.STILI)  # ogni stile produce una firma diversa
assert generatore.generate("Mario Rossi", 1, iniziale=True) == generatore.generate("M. Rossi", 1)

# PDF di prova: pagina normale + pagina ruotata
src = T + "/doc.pdf"
d = pymupdf.open()
d.new_page().insert_text((72, 100), "Pagina 1", fontsize=20)
p = d.new_page()
p.set_rotation(90)
p.insert_text((72, 100), "Pagina ruotata", fontsize=20)
d.save(src)

w = MainWindow()
w.resize(1200, 850)
w.show()
if not w.cfg["firme"]:  # su macchine senza la firma iniziale ne creo una col generatore
    svg = T + "/f.svg"
    open(svg, "w").write(generatore.generate("Test", 3))
    w.cfg["firme"].append({"nome": "Test", "file": svg})
    w.refresh_firme()
w.open_pdf(src)
app.processEvents()
path = w.cfg["firme"][0]["file"]
pg0, pg1 = w.view.pages

# luogo/data + posizionamento con anteprima
w.chk_luogo.setChecked(True)
w.luogo.setText("Palermo")
w.chk_data.setChecked(True)
w.start_place_mode(w.firme.item(0))
assert w.view.ghost is not None
w.end_place_mode()
assert w.view.ghost is None
w.view.add_signature(path, pg0.pos() + QPointF(300, 600))
w.view.add_signature(path, pg1.pos() + QPointF(200, 150))
assert len(w.view.signatures()) == 2

# annulla / ripeti / frecce
w.undo(); assert len(w.view.signatures()) == 1
w.redo(); assert len(w.view.signatures()) == 2
it = w.view.signatures()[0]
w.view.scene().clearSelection(); it.setSelected(True); w.view.setFocus()
x0 = it.pos().x()
QTest.keyClick(w.view, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
assert it.pos().x() == x0 + 10
w.undo(); assert {round(s.pos().x(), 2) for s in w.view.signatures()} >= {round(x0, 2)}

# salvataggio su nuovo file: firma vettoriale + testo, anche sulla pagina ruotata
out = T + "/firmato.pdf"
write_signed(w.doc, w.placements(), out)
o = pymupdf.open(out)
for pg in o:
    assert len(pg.get_drawings()) >= 1, "firma non vettoriale"
    assert "Palermo, " in pg.get_text(), pg.get_text()
assert o[1].rotation == 90

# creatore: lo stile arriva fino alla firma salvata; colore predefinito nero
d = CreatorDialog(w, w.cfg)
assert d.colore.currentText() == "Nero"
d.testo.setText("Mario Rossi")
d.stile.setCurrentIndex(d.stile.findData("sigla"))
d.refresh()
assert d.params()["stile"] == "sigla" and "iniziale" not in d.params()
assert d.params()["sottolineato"] is False  # niente riga sotto il nome se non richiesta
if os.environ.get("SIGLA_SHOT"):
    d.grab().save(os.environ["SIGLA_SHOT"])
d.save()
assert open(w.cfg["firme"][-1]["file"]).read() == generatore.generate("Mario Rossi", d.seeds[0], **d.params())

# --- automazione: diciture di firma, sigle, firma in blocco
contratto = T + "/contratto.pdf"
d = pymupdf.open()
for i in range(3):
    pg = d.new_page()
    pg.insert_text((72, 100), f"Articolo {i + 1}. La firma del presente contratto avviene alla consegna dei beni.", fontsize=9)
d[2].insert_text((350, 600), "Firma del dichiarante", fontsize=11)
d.save(contratto)
cd = pymupdf.open(contratto)
spots = find_sign_spots(cd)
assert [(s[0], s[2]) for s in spots] == [(2, "Firma del dichiarante")], spots  # la frase lunga è ignorata
placed, where = auto_placements(cd, path, "", 150)
assert placed[0][0] == 2 and placed[0][1].y0 > spots[0][1].y1 and "pag. 3" in where, (placed, where)
_, where = auto_placements(cd, path, "", 150, mode="ultima")
assert where == "in fondo all'ultima pagina"
assert len(sigla_placements(cd, path, 60)) == 3 and len(sigla_placements(cd, path, 60, skip_last=True)) == 2
cd.close()
dst = output_path(contratto)
assert dst.endswith("contratto_firmato.pdf")
sign_file(contratto, dst, path, "Palermo", 150)
assert output_path(contratto).endswith("contratto_firmato (2).pdf")  # mai sovrascrivere
assert "Palermo" in pymupdf.open(dst)[2].get_text()
sign_file(contratto, output_path(contratto), path, "", 150, mode="ultima")
assert os.path.exists(T + "/contratto_firmato (2).pdf")

# --- interfaccia: miniature, trova dove firmare, sigle, firma in blocco
w.dirty = False  # altrimenti open_pdf chiede se scartare le firme (dialogo modale)
w.open_pdf(contratto)
app.processEvents()
assert w.thumbs.count() == 3
while w.thumbs.todo:
    w.thumbs.render_next()
w.find_spots()  # una sola dicitura: firma messa direttamente
assert len(w.view.signatures()) == 1
w.add_placed(sigla_placements(w.doc, path, 60))
assert len(w.view.signatures()) == 4
w.undo()
assert len(w.view.signatures()) == 1  # le sigle si annullano in un colpo solo
bd = BatchDialog(w, [contratto, src])
assert bd.list.count() == 2
bd.run()
assert os.path.exists(T + "/contratto_firmato (3).pdf") and os.path.exists(T + "/doc_firmato.pdf")
if os.environ.get("SIGLA_SHOT_NEW"):
    o = os.environ["SIGLA_SHOT_NEW"]
    w.update_status(); app.processEvents(); w.grab().save(o + "_main.png")
    bd.show(); app.processEvents(); bd.grab().save(o + "_batch.png")
    sd = SiglaDialog(w, w.cfg, 3); sd.show(); app.processEvents(); sd.grab().save(o + "_sigla.png")

# --- regressioni del giro di bugfix
w.dirty = False
w.open_pdf(src)
app.processEvents()
pg0 = w.view.pages[0]
# firma trascinata fuori dal foglio: viene riportata dentro
it = SignatureItem(path, 150, "")
w.view.scene().addItem(it)
it.setPos(pg0.pos() + QPointF(pg0.w - 20, 10))
w.view.keep_inside(it)
assert it.pos().x() + it.bw <= pg0.pos().x() + pg0.w, "firma fuori dal foglio"
# ✕ sulla firma: rimozione differita (niente distruzione durante il clic) e registrata nell'annulla
w.changed()
n = len(w.view.signatures())
it.remove_self()
assert len(w.view.signatures()) == n - 1
w.undo()
assert len(w.view.signatures()) == n
# ridimensionamento con didascalia più larga della firma: niente salto di misura
big = SignatureItem(path, 40, "San Giovanni la Punta di Sopra e di Sotto, provincia, 11/11/2026")
assert big.bw > big.w
w0 = big.w
big.mode = "resize"
class _E:  # evento finto: il mouse è esattamente sul bordo attuale del blocco
    def pos(self):
        return QPointF(big.bw, big.bh)
big.mouseMoveEvent(_E())
assert abs(big.w - w0) < 0.01, (big.w, w0)
# creatore: testo con soli caratteri non disegnabili -> messaggio, non crash
cdlg = CreatorDialog(w, w.cfg)
cdlg.testo.setText("ò")
cdlg.refresh()
assert not cdlg.ok.isEnabled() and "Nessuna lettera" in cdlg.btns[0].text()
# PDF protetto: la firma non toglie la password
enc = T + "/protetto.pdf"
d = pymupdf.open()
d.new_page().insert_text((72, 100), "riservato")
d.save(enc, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="pw", owner_pw="own")
ed = pymupdf.open(enc)
ed.authenticate("pw")
write_signed(ed, [(0, pymupdf.Rect(100, 100, 250, 150), path, "", 150)], T + "/protetto_firmato.pdf", "pw")
r = pymupdf.open(T + "/protetto_firmato.pdf")
assert r.needs_pass and r.authenticate("pw") and r[0].get_drawings()
# effetto scansione: stesse pagine e formato, solo immagini, difetti diversi a ogni seme, protezione mantenuta
from sigla.scansione import scansiona
sc = [pymupdf.open(contratto) for _ in range(3)]
for d_, seme in zip(sc, (1, 1, 2)):
    scansiona(d_, seme)
orig = pymupdf.open(contratto)
assert len(sc[0]) == len(orig) and sc[0][0].rect == orig[0].rect
assert not sc[0][0].get_text().strip() and len(sc[0][0].get_images()) == 1
px = [d_[0].get_pixmap(dpi=40).samples for d_ in sc]
assert px[0] == px[1] != px[2]
assert sum(px[0]) > 0.9 * sum(orig[0].get_pixmap(dpi=40).samples)  # non invasivo: la pagina resta chiara
write_signed(ed, [(0, pymupdf.Rect(100, 100, 250, 150), path, "", 150)], T + "/protetto_scan.pdf", "pw", scan=True)
r = pymupdf.open(T + "/protetto_scan.pdf")
assert r.needs_pass and r.authenticate("pw") and r[0].get_images() and not r[0].get_text().strip()
w.chk_scan.setChecked(True)
assert load_config()["scansione"] is True
w.chk_scan.setChecked(False)
# config danneggiata: copia di sicurezza prima di sovrascriverla
open(C.CONF_FILE, "w").write("{ non è json")
load_config()
assert os.path.exists(C.CONF_FILE + ".danneggiato")
save_config(w.cfg)

# --- UX: guida e pulsante Salva seguono lo stato del documento
w.dirty = False
w.open_pdf(src)
app.processEvents()
assert w.page_spin.text() == "1", repr(w.page_spin.text())  # il numero di pagina non deve sparire
assert w.coach.isVisible() and not w.a_save.isEnabled()
w.view.add_signature(path, w.view.pages[0].sceneBoundingRect().center())
assert not w.coach.isVisible() and w.a_save.isEnabled()
w.undo()
assert w.coach.isVisible() and not w.a_save.isEnabled()

# --- gestione firme dalla colonna Firme (le Impostazioni non hanno più l'elenco)
sd = SettingsDialog(w, w.cfg)
assert not sd.findChildren(FirmeList)
if len(w.cfg["firme"]) > 1:
    w.set_default_firma(1)
    assert default_firma(w.cfg) == w.cfg["firme"][1]["file"]
    assert w.firme.item(1).text().startswith("★")
if os.environ.get("SIGLA_SHOT_SET"):
    sd.show(); app.processEvents(); sd.grab().save(os.environ["SIGLA_SHOT_SET"])
    w.grab().save(os.environ["SIGLA_SHOT_SET"] + ".main.png")

# --- Nuova firma (Importa / Genera / Disegna) e Le mie firme
import math
nd = NewFirmaDialog(w)
nd.pick("disegna")
assert nd.choice == "disegna" and nd.result() == 1
dd = DrawDialog(w, w.cfg)
dd.resize(760, 380)
assert not dd.ok.isEnabled()  # niente da salvare finché non si disegna
t0 = 0.0
for k in range(3):  # tre tratti finti, con velocità variabile
    dd.pad.strokes.append([(80 + k * 200 + i * 6, 140 + 40 * math.sin(i / 4), t0 + i * 0.008 * (1 + (i % 7)), None)
                           for i in range(30)])
dd.pad.strokes.append([(650, 90, 1.0, None)])  # un puntino
dd.update_ok()
assert dd.ok.isEnabled()
svg = dd.pad.to_svg()
sd_doc = pymupdf.open(stream=svg.encode(), filetype="svg")
assert sd_doc[0].get_pixmap().width > 0
n = len(w.cfg["firme"])
if os.environ.get("SIGLA_SHOT_NEWF"):
    o = os.environ["SIGLA_SHOT_NEWF"]
    nd.show(); app.processEvents(); nd.grab().save(o + "_tiles.png")
    dd.show(); app.processEvents(); dd.grab().save(o + "_draw.png")
dd.save()
assert len(w.cfg["firme"]) == n + 1 and w.cfg["firme"][-1]["file"].endswith(".svg")
mf = MyFirmeDialog(w)
assert mf.list.count() == n + 1
mf.list.setCurrentRow(n)
mf.on_selected(w.set_default_firma)
assert default_firma(w.cfg) == w.cfg["firme"][n]["file"]
if os.environ.get("SIGLA_SHOT_NEWF"):
    mf.show(); app.processEvents(); mf.grab().save(os.environ["SIGLA_SHOT_NEWF"] + "_mie.png")

# --- Impostazioni: salvataggio, nome copia, formato data, recenti, esporta/importa firme
import datetime
import zipfile
st = SettingsDialog(w, w.cfg)
st.salva.setCurrentIndex(st.salva.findData("copia"))
st.suffix.setText("_ok_{data}")
st.fdata.setCurrentIndex(st.fdata.findData("esteso"))
assert w.cfg["salvataggio"] == "copia" and w.cfg["formato_data"] == "esteso"
assert "contratto_ok_" in st.suffix_preview.text()
w.settings  # (il metodo esiste; il dialogo vero è modale)
w.options_changed()
oggi = datetime.date.today()
assert f"{oggi.day} {MESI[oggi.month - 1]} {oggi.year}" in w.caption()
# Salva con «crea sempre una copia»: nessuna finestra, copia accanto all'originale col suffisso
w.dirty = False
w.open_pdf(src)
app.processEvents()
w.view.add_signature(path, w.view.pages[0].sceneBoundingRect().center())
w.save()
copia = T + f"/doc_ok_{oggi.isoformat()}.pdf"
assert os.path.exists(copia) and w.path == copia and not w.dirty
# recenti disattivati: elenco svuotato e niente nuove voci
st.recenti.setChecked(False)
assert w.cfg["recenti"] == []
w.dirty = False
w.open_pdf(src)
assert w.cfg["recenti"] == []
st.recenti.setChecked(True)
if os.environ.get("SIGLA_SHOT_SETTINGS"):
    st.show(); app.processEvents(); st.grab().save(os.environ["SIGLA_SHOT_SETTINGS"])
st.salva.setCurrentIndex(st.salva.findData("chiedi"))
st.suffix.setText("_firmato")
# «Salva e chiudi» salva anche la cartella scritta senza premere Invio
assert st.findChild(QDialogButtonBox).buttons()[0].text() == "Salva e chiudi"
st.dir.setText(T)
st.save_and_close()
assert w.cfg["cartella"] == T
# esporta e reimporta: i duplicati vengono saltati
zp = T + "/firme.zip"
n = export_firme(w.cfg, zp)
assert n == len(w.cfg["firme"]) and n > 0
cfg2 = {"firme": []}
assert import_firme(cfg2, zp) == (n, 0)
assert import_firme(cfg2, zp) == (0, n)
# zip malevolo: percorsi fuori cartella, estensioni sbagliate, file non immagine -> ignorati
evil = T + "/evil.zip"
with zipfile.ZipFile(evil, "w") as z:
    z.writestr("sigla-firme.json", '{"firme": [{"nome": "x", "file": "../../evil.svg"}, '
                                   '{"nome": "y", "file": "run.sh"}, {"nome": "z", "file": "finto.svg"}]}')
    z.writestr("../../evil.svg", "<svg/>")
    z.writestr("run.sh", "rm -rf ~")
    z.writestr("finto.svg", "non è un svg")
before = set(os.listdir(C.FIRME_DIR))
assert import_firme({"firme": []}, evil) == (0, 0)
assert set(os.listdir(C.FIRME_DIR)) == before and not os.path.exists(os.path.join(T, "evil.svg"))
try:
    with zipfile.ZipFile(T + "/altro.zip", "w") as z:
        z.writestr("a.txt", "x")
    import_firme({"firme": []}, T + "/altro.zip")
    raise AssertionError("uno zip qualsiasi deve essere rifiutato")
except ValueError:
    pass

# --- responsive: nessun comando finisce nella freccina «»» della barra, a nessuna larghezza
w.dirty = False
w.open_pdf(src)
for width in (1400, 1000, 800, 720):
    w.resize(width, 640)
    app.processEvents()
    w.apply_responsive()
    app.processEvents()
    ext = w.tb.findChild(QToolButton, "qt_toolbar_ext_button")
    assert not (ext and ext.isVisible()), f"comandi nascosti a {width}px"
assert w.a_more.isVisible() and not w.a_zin.isVisible()  # zoom e impostazioni nel menu «Altro»
z0 = w.view.transform().m11()
w.a_zin.trigger()
assert w.view.transform().m11() > z0 and not w.view.auto_fit  # funziona anche da nascosto
w.resize(1400, 640)
app.processEvents()
w.apply_responsive()
assert w.a_zin.isVisible() and not w.a_more.isVisible()

# --- menu a tendina: tutti con il disegnatore che rispetta lo stile (niente bianco su bianco col tema scuro)
for dlg in (SettingsDialog(w, w.cfg), CreatorDialog(w, w.cfg), DrawDialog(w, w.cfg),
            SiglaDialog(w, w.cfg, 1), BatchDialog(w)):
    for cb in dlg.findChildren(QComboBox):
        assert isinstance(cb.itemDelegate(), QStyledItemDelegate), f"{type(dlg).__name__}: usa Combo"
pal = light_palette()
assert pal.color(QPalette.ColorRole.HighlightedText) != pal.color(QPalette.ColorRole.Highlight)

# finestra Info: dimensioni fisse, non ridimensionabile
ab = AboutDialog(w)
ab.show()
app.processEvents()
assert ab.minimumSize() == ab.maximumSize() and ab.width() >= AboutDialog.WIDTH
ab.close()

# aggiornamenti: ultima release su GitHub, download verificato (finti: i test non usano la rete né installano)
import hashlib, io, json, subprocess
import sigla.ui.finestra as F
assert A.parse_versione("1.10.0") > A.parse_versione("1.9.3") and A.parse_versione("1.2<b>") is None
REPO, ARCH = A.repo(), A.architettura()
def finta(risposta):
    A.urllib.request.urlopen = lambda url, timeout: (
        (_ for _ in ()).throw(OSError("senza rete")) if risposta is None else io.BytesIO(risposta.encode()))
    return A.nuova_versione()
def release(tag, url=None, nome=None, size=1000, digest="sha256:" + "a" * 64):
    nome = nome or f"{C.APP_ID}_{tag[1:]}_{ARCH}.deb"
    return json.dumps({"tag_name": tag, "assets": [{"name": nome, "size": size, "digest": digest,
                       "browser_download_url": url or f"{REPO}/releases/download/{tag}/{nome}"}]})
r = finta(release("v99.0.0"))
assert r["versione"] == "99.0.0" and r["pagina"] == REPO + "/releases/latest"
assert r["deb"]["size"] == 1000 and r["deb"]["sha256"] == "a" * 64 and r["deb"]["url"].startswith(REPO + "/releases/")
assert finta(release("v99.0.0", url="https://altrove.example/x.deb"))["deb"] is None  # mai file fuori dalla release
assert finta(release("v99.0.0", nome="altro.deb"))["deb"] is None and finta(release("v99.0.0", size=10**10))["deb"] is None
assert finta(release("v99.0.0", digest="md5:x"))["deb"]["sha256"] is None
assert finta(release("v" + __version__)) is None and finta(release("v0.0.1")) is None and finta(release("v<b>9")) is None
assert finta(None) is None and finta("non json") is None and finta("[1]") is None and finta('{"tag_name": 9}') is None
# pacchetto finto: download e controlli di dimensione, SHA-256, nome e versione
pk = T + "/pk"
os.makedirs(pk + "/DEBIAN")
open(pk + "/DEBIAN/control", "w").write(f"Package: {C.APP_ID}\nVersion: 99.0.0\nArchitecture: all\n"
                                        "Maintainer: test <t@example.com>\nDescription: test\n")
subprocess.run(["dpkg-deb", "--root-owner-group", "--build", pk, T + "/pk.deb"], check=True, capture_output=True)
dati = open(T + "/pk.deb", "rb").read()
A.urllib.request.urlopen = lambda url, timeout: io.BytesIO(dati)
deb = {"url": "x", "size": len(dati), "sha256": hashlib.sha256(dati).hexdigest()}
visti = []
p_ = A.scarica(deb, "99.0.0", visti.append)
assert open(p_, "rb").read() == dati and visti[-1] == len(dati)
os.remove(p_)
def rifiutato(deb, versione="99.0.0", progresso=None, errore=ValueError):
    prima = set(os.listdir(tempfile.gettempdir()))
    try:
        A.scarica(deb, versione, progresso)
    except errore:
        assert set(os.listdir(tempfile.gettempdir())) <= prima  # niente file lasciati in giro
        return True
assert rifiutato(dict(deb, sha256="0" * 64)) and rifiutato(dict(deb, size=len(dati) - 1))
assert rifiutato(dict(deb, size=len(dati) + 1)) and rifiutato(deb, "98.0.0")
assert rifiutato(dict(deb, sha256=None), progresso=lambda n: False, errore=InterruptedError)
A.urllib.request.urlopen = lambda url, timeout: io.BytesIO(b"non sono un pacchetto")
assert rifiutato({"url": "x", "size": 21, "sha256": None})
# impostazioni e avviso: dai sorgenti si apre la pagina, dal pacchetto si aggiorna dall'app
st2 = SettingsDialog(w, w.cfg)
st2.aggiorna.setChecked(False)
assert w.cfg["controlla_aggiornamenti"] is False
st2.aggiorna.setChecked(True)
assert not A.da_pacchetto()
w.update_found.emit(r)
app.processEvents()
assert "99.0.0" in w.toast.text.text() and w.toast.btn.text() == "Scarica" and w.new_version == "99.0.0"
assert "disponibile la 99.0.0" in " ".join(l.text() for l in AboutDialog(w).findChildren(QLabel))
F.da_pacchetto = lambda: True
w.update_found.emit(r)
app.processEvents()
assert w.toast.btn.text() == "Aggiorna" and w.toast.action == w.install_update
w.update_found.emit(dict(r, deb=None))  # release senza pacchetto per questo computer
app.processEvents()
assert w.toast.btn.text() == "Scarica"
F.da_pacchetto = A.da_pacchetto
w.new_version = w.release = None

# finestra Info: i dati vengono da app.json
assert __version__ == INFO["versione"]
info = AboutDialog(w)
testi = " ".join(l.text() for l in info.findChildren(QLabel))
assert INFO["versione"] in testi and INFO["algoritmo_firma"]["versione"] in testi, testi
assert INFO["licenza"]["nome"] in testi and "senza alcuna garanzia" in testi, testi
if os.environ.get("SIGLA_SHOT_INFO"):
    info.show()
    app.processEvents()
    info.grab().save(os.environ["SIGLA_SHOT_INFO"])
    w.grab().save(os.environ["SIGLA_SHOT_INFO"] + ".main.png")

w.dirty = False
w.close()
print("OK -", T)
