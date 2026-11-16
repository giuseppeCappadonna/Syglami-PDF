"""Finestre di dialogo: creazione/gestione firme, impostazioni, sigla pagine, firma in blocco, info."""
import datetime
import os
import sys
import time

import pymupdf
from PyQt6.QtCore import PYQT_VERSION_STR, QPointF, QRectF, QSize, Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QFont, QIcon, QKeySequence, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QApplication, QButtonGroup, QCheckBox, QGridLayout, QSlider, QDialog,
                             QDialogButtonBox, QFileDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
                             QListWidgetItem, QMessageBox, QPushButton, QSizePolicy, QSpinBox, QProgressBar,
                             QRadioButton, QToolButton, QVBoxLayout, QWidget)

from sigla.config import (__version__, add_firma_svg, APP_DIR, APP_NAME, copy_suffix, default_firma, export_firme,
                          fmt_data, FORMATI_DATA, import_firme, INFO, SALVATAGGI, save_config, SUFFISSO)
from sigla.pdf import output_path, POSIZIONI, sign_file
from sigla.ui.scena import PdfView
from sigla.ui.tema import ACCENT, icon, icon_pixmap, to_qimage
from sigla.ui.widget import Combo, FirmaCombo, FirmeList

class CreatorDialog(QDialog):
    """Crea una firma vettoriale: ogni variante è una "mano" diversa (vedi generatore.py)."""
    N = 6
    COLORI = (("Nero", "#1a1a1a"), ("Blu penna", "#1b2f7a"), ("Blu brillante", "#2457d6"))  # il primo è il predefinito

    def __init__(self, parent, cfg):
        super().__init__(parent)
        import generatore
        self.gen = generatore
        self.cfg = cfg
        self.setWindowTitle("Crea firma")
        self.resize(860, 640)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(SettingsDialog._title("Crea una firma"))
        h = QLabel("Scrivi il nome: ogni variante è scritta da una «mano» diversa, unica e vettoriale. "
                   "Scegli quella che preferisci.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        lay.addWidget(h)
        self.testo = QLineEdit()
        self.testo.setPlaceholderText("Nome e cognome")
        self.testo.textChanged.connect(self.schedule)
        lay.addWidget(self.testo)

        row = QHBoxLayout()
        row.addWidget(QLabel("Stile"))
        self.stile = Combo()
        for key, nome in generatore.STILI:
            self.stile.addItem(nome, key)
        self.stile.setToolTip("Il modo di firmare: ogni variante qui sotto resta una mano diversa")
        self.stile.currentIndexChanged.connect(self.schedule)
        row.addWidget(self.stile)
        self.sottolineato = QCheckBox("Sottolineato")
        self.sottolineato.setToolTip("Aggiunge la riga o lo svolazzo sotto il nome")
        self.sottolineato.toggled.connect(self.schedule)
        row.addWidget(self.sottolineato)
        row.addStretch()
        lay.addLayout(row)

        ctrl = QGridLayout()
        self.sl = {}
        for col, (key, label, lo, hi, val) in enumerate((
                ("leggibilita", "Leggibilità", 0, 100, 70), ("inclinazione", "Inclinazione", 0, 100, 50),
                ("spessore", "Spessore", 50, 200, 100))):
            ctrl.addWidget(QLabel(label), 0, col)
            sl = QSlider(Qt.Orientation.Horizontal)
            sl.setMinimumHeight(26)  # spazio per il pallino intero (sporge sopra e sotto la barra)
            sl.setRange(lo, hi)
            sl.setValue(val)
            sl.valueChanged.connect(self.schedule)
            ctrl.addWidget(sl, 1, col)
            self.sl[key] = sl
        ctrl.addWidget(QLabel("Colore"), 0, 3)
        self.colore = Combo()
        for nome, c in self.COLORI:
            self.colore.addItem(nome, c)
        self.colore.currentIndexChanged.connect(self.schedule)
        ctrl.addWidget(self.colore, 1, 3)
        lay.addLayout(ctrl)

        grid = QGridLayout()
        grid.setSpacing(10)
        self.group = QButtonGroup(self)
        self.btns = []
        for i in range(self.N):
            b = QToolButton()
            b.setCheckable(True)
            b.setObjectName("variant")
            b.setIconSize(QSize(380, 110))
            b.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.group.addButton(b, i)
            grid.addWidget(b, i // 2, i % 2)
            self.btns.append(b)
        self.btns[0].setChecked(True)
        lay.addLayout(grid, 1)

        row = QHBoxLayout()
        b = QPushButton("Altre varianti")
        b.clicked.connect(self.new_seeds)
        row.addWidget(b)
        row.addStretch()
        b = QPushButton("Annulla")
        b.clicked.connect(self.reject)
        row.addWidget(b)
        self.ok = QPushButton("Salva firma")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.save)
        row.addWidget(self.ok)
        lay.addLayout(row)

        self.timer = QTimer(self, singleShot=True, interval=250, timeout=self.refresh)
        self.new_seeds()

    def params(self):
        return dict(leggibilita=self.sl["leggibilita"].value() / 100,
                    inclinazione=self.sl["inclinazione"].value() / 100,
                    spessore=self.sl["spessore"].value() / 100, colore=self.colore.currentData(),
                    stile=self.stile.currentData(), sottolineato=self.sottolineato.isChecked())

    def new_seeds(self):
        import random
        self.seeds = [random.randrange(2 ** 31) for _ in range(self.N)]
        self.refresh()

    def schedule(self):
        self.timer.start()

    def refresh(self):
        t = self.testo.text().strip()
        self.ok.setEnabled(bool(t))
        for b, seed in zip(self.btns, self.seeds):
            if not t:
                b.setIcon(QIcon())
                b.setText("Scrivi il nome qui sopra")
                continue
            try:
                svg = self.gen.generate(t, seed, **self.params())
            except ValueError:
                self.ok.setEnabled(False)
                b.setIcon(QIcon())
                b.setText("Nessuna lettera disegnabile: usa lettere senza accenti (a-z)")
                continue
            with pymupdf.open(stream=svg.encode(), filetype="svg") as d:
                z = 760 / d[0].rect.width
                pix = d[0].get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=True)
            b.setText("")
            b.setIcon(QIcon(QPixmap.fromImage(to_qimage(pix))))

    def save(self):
        t = self.testo.text().strip()
        if not t:
            return
        try:
            svg = self.gen.generate(t, self.seeds[self.group.checkedId()], **self.params())
        except ValueError as ex:
            QMessageBox.warning(self, "Crea firma", f"Impossibile generare la firma:\n{ex}")
            return
        add_firma_svg(self.cfg, t, svg)
        self.accept()


class NewFirmaDialog(QDialog):
    """Nuova firma: tre riquadri, Importa / Genera / Disegna. Il risultato è in self.choice."""

    def __init__(self, parent):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle("Nuova firma")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(24, 20, 24, 18)
        lay.setSpacing(12)
        lay.addWidget(SettingsDialog._title("Nuova firma"))
        h = QLabel("Come vuoi creare la tua firma?")
        h.setObjectName("hint")
        lay.addWidget(h)
        row = QHBoxLayout()
        row.setSpacing(12)
        for key, ic, title, sub in (("importa", "upload", "Importa", "da un'immagine\nPNG, JPG o SVG"),
                                    ("genera", "wand", "Genera", "scritta da una\n«mano» unica"),
                                    ("disegna", "signature", "Disegna", "col mouse o\nla tavoletta")):
            b = QPushButton()
            b.setObjectName("tile")
            b.setAutoDefault(False)
            b.setMinimumSize(176, 176)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            tl = QVBoxLayout(b)
            tl.setContentsMargins(12, 18, 12, 14)
            tl.setSpacing(4)
            ic_l, t_l, s_l = QLabel(), QLabel(title), QLabel(sub)
            for wdg in (ic_l, t_l, s_l):
                wdg.setAlignment(Qt.AlignmentFlag.AlignCenter)
                wdg.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)  # il clic arriva al riquadro
                tl.addWidget(wdg)
            ic_l.setPixmap(icon_pixmap(ic, ACCENT, 40, 1.6))
            tl.insertSpacing(1, 6)
            t_l.setObjectName("tiletitle")
            s_l.setObjectName("hint")
            tl.addStretch()
            b.clicked.connect(lambda _, k=key: self.pick(k))
            row.addWidget(b)
        lay.addLayout(row)
        bb = QDialogButtonBox()
        bb.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole).setAutoDefault(False)  # la scelta è nei riquadri
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)

    def pick(self, key):
        self.choice = key
        self.accept()


class DrawPad(QWidget):
    """Foglio per firmare a mano: il tratto si assottiglia con la velocità (o segue la pressione della tavoletta)."""

    def __init__(self):
        super().__init__()
        self.setMinimumSize(680, 250)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.strokes = []      # ogni tratto: lista di (x, y, t, pressione o None)
        self.base = 2.6        # spessore di base in pixel
        self.color = "#1a1a1a"
        self.on_change = lambda: None

    # --- input
    def _add(self, pos, pressure=None, new=False):
        if new:
            self.strokes.append([])
        if self.strokes:
            self.strokes[-1].append((pos.x(), pos.y(), time.monotonic(), pressure))
            self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._add(e.position(), new=True)

    def mouseMoveEvent(self, e):
        if e.buttons() & Qt.MouseButton.LeftButton:
            self._add(e.position())

    def mouseReleaseEvent(self, e):
        self.on_change()

    def tabletEvent(self, e):
        t = e.type()
        if t == e.Type.TabletPress:
            self._add(e.position(), e.pressure(), new=True)
        elif t == e.Type.TabletMove and e.pressure() > 0:
            self._add(e.position(), e.pressure())
        elif t == e.Type.TabletRelease:
            self.on_change()
        e.accept()  # niente eventi mouse duplicati

    def undo(self):
        if self.strokes:
            self.strokes.pop()
            self.update()
            self.on_change()

    def clear(self):
        self.strokes = []
        self.update()
        self.on_change()

    # --- geometria del tratto (usata sia a schermo sia nell'SVG)
    def geometry(self, stroke):
        import numpy as np
        a = np.array([(x, y) for x, y, _, _ in stroke], float)
        if len(a) >= 5:  # leviga il tremolio del mouse, estremi fermi
            k = np.ones(3) / 3
            a[1:-1] = np.column_stack([np.convolve(a[:, i], k, "valid") for i in range(2)])
        if stroke[0][3] is not None:  # tavoletta: pressione
            w = np.array([self.base * (0.35 + 1.1 * (p or 0.5)) for *_, p in stroke])
        else:  # mouse: più veloce = più sottile
            t = np.array([s[2] for s in stroke])
            d = np.r_[0, np.linalg.norm(np.diff(a, axis=0), axis=1)]
            v = d / np.maximum(np.r_[1, np.diff(t)], 1e-3)
            v = np.convolve(v, np.ones(5) / 5, "same")
            w = self.base * (0.5 + 0.8 / (1 + v / 700))
        n = len(w)
        if n > 4:  # attacco e uscita più sottili
            w[:2] *= (0.6, 0.8)
            w[-2:] *= (0.8, 0.6)
        return a, w

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor("#d5dbe8"), 1))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(r, 12, 12)
        y = r.top() + r.height() * 0.72
        p.setPen(QPen(QColor("#c3cad9"), 1.2, Qt.PenStyle.DashLine))
        p.drawLine(QPointF(r.left() + 40, y), QPointF(r.right() - 30, y))
        p.setPen(QColor("#a9b3c9"))
        f = QFont(self.font())
        f.setPointSize(15)
        p.setFont(f)
        p.drawText(QPointF(r.left() + 18, y + 6), "×")
        if not self.strokes:
            f.setPointSize(11)
            p.setFont(f)
            p.drawText(r, Qt.AlignmentFlag.AlignCenter, "Firma qui, tenendo premuto il tasto sinistro del mouse")
        col = QColor(self.color)
        for st in self.strokes:
            a, w = self.geometry(st)
            if len(a) == 1:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
                p.drawEllipse(QPointF(*a[0]), w[0] / 2, w[0] / 2)
                continue
            for i in range(len(a) - 1):
                pen = QPen(col, (w[i] + w[i + 1]) / 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
                p.setPen(pen)
                p.drawLine(QPointF(*a[i]), QPointF(*a[i + 1]))

    def to_svg(self):
        """SVG ritagliato sul disegno: segmenti raggruppati per spessore, estremi rotondi."""
        if not self.strokes:
            return None
        parts, allp = [], []
        for st in self.strokes:
            a, w = self.geometry(st)
            allp.append(a)
            if len(a) == 1:
                parts.append(("dot", a[0], w[0]))
                continue
            lev = [round(x * 4) / 4 for x in w]  # livelli di 0.25 px
            i = 0
            while i < len(a) - 1:
                j = i + 1
                while j < len(a) - 1 and lev[j] == lev[i]:
                    j += 1
                parts.append(("line", a[i:j + 1], lev[i]))
                i = j
        import numpy as np
        pts = np.vstack(allp)
        m = self.base * 2
        x0, y0 = pts.min(axis=0) - m
        x1, y1 = pts.max(axis=0) + m
        out = []
        for kind, a, w in parts:
            if kind == "dot":
                out.append(f'<circle cx="{a[0] - x0:.2f}" cy="{a[1] - y0:.2f}" r="{w / 2:.2f}" fill="{self.color}"/>')
            else:
                d = " ".join(f"{x - x0:.2f},{y - y0:.2f}" for x, y in a)
                out.append(f'<path d="M{d}" stroke-width="{w:.2f}"/>')
        W, H = x1 - x0, y1 - y0
        return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.2f} {H:.2f}" width="{W:.0f}" height="{H:.0f}">'
                f'<g fill="none" stroke="{self.color}" stroke-linecap="round" stroke-linejoin="round">'
                + "".join(out) + "</g></svg>\n")


class DrawDialog(QDialog):
    """Disegna la firma a mano e salvala come SVG."""
    COLORI = (("Nero", "#1a1a1a"), ("Blu penna", "#1b2f7a"))

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Disegna la firma")
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(SettingsDialog._title("Disegna la tua firma"))
        h = QLabel("Firma sul foglio come faresti su carta: con la tavoletta grafica il tratto segue la pressione.")
        h.setObjectName("hint")
        h.setWordWrap(True)
        lay.addWidget(h)
        self.pad = DrawPad()
        self.pad.on_change = self.update_ok
        lay.addWidget(self.pad, 1)

        row = QHBoxLayout()
        b = QPushButton(" Annulla tratto")
        b.setIcon(icon("undo"))
        b.setShortcut(QKeySequence("Ctrl+Z"))
        b.setToolTip("Ctrl+Z")
        b.setAutoDefault(False)  # Invio deve salvare, non cancellare tratti
        b.clicked.connect(self.pad.undo)
        row.addWidget(b)
        b = QPushButton("Cancella tutto")
        b.setAutoDefault(False)
        b.clicked.connect(self.pad.clear)
        row.addWidget(b)
        row.addStretch()
        row.addWidget(QLabel("Spessore"))
        self.spess = QSlider(Qt.Orientation.Horizontal)
        self.spess.setMinimumHeight(26)
        self.spess.setRange(10, 60)
        self.spess.setValue(26)
        self.spess.setFixedWidth(140)
        self.spess.valueChanged.connect(self.restyle)
        row.addWidget(self.spess)
        row.addWidget(QLabel("Colore"))
        self.colore = Combo()
        for n, c in self.COLORI:
            self.colore.addItem(n, c)
        self.colore.currentIndexChanged.connect(self.restyle)
        row.addWidget(self.colore)
        lay.addLayout(row)

        row = QHBoxLayout()
        row.addWidget(QLabel("Nome"))
        self.nome = QLineEdit("Firma disegnata")
        row.addWidget(self.nome, 1)
        b = QPushButton("Annulla")
        b.setAutoDefault(False)
        b.clicked.connect(self.reject)
        row.addWidget(b)
        self.ok = QPushButton("Salva firma")
        self.ok.setObjectName("primary")
        self.ok.setDefault(True)
        self.ok.clicked.connect(self.save)
        row.addWidget(self.ok)
        lay.addLayout(row)
        self.update_ok()

    def restyle(self):
        self.pad.base = self.spess.value() / 10
        self.pad.color = self.colore.currentData()
        self.pad.update()

    def update_ok(self):
        self.ok.setEnabled(bool(self.pad.strokes))

    def save(self):
        svg = self.pad.to_svg()
        if not svg:
            return
        add_firma_svg(self.cfg, self.nome.text().strip() or "Firma disegnata", svg)
        self.accept()


class MyFirmeDialog(QDialog):
    """Le mie firme: elenco con rinomina, predefinita, rimuovi e nuova firma."""

    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Le mie firme")
        self.resize(560, 500)
        lay = QVBoxLayout(self)
        lay.setSpacing(10)
        lay.addWidget(SettingsDialog._title("Le mie firme"))
        h = QLabel("La firma con ★ è la predefinita: la usano «Trova dove firmare» e la firma di più PDF.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        lay.addWidget(h)
        self.list = FirmeList()
        self.list.setDragEnabled(False)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        b = QPushButton(" Nuova firma…")
        b.setObjectName("primary")
        b.setIcon(icon("pen", "#ffffff"))
        b.clicked.connect(self.new)
        row.addWidget(b)
        self.sel_btns = []
        for txt, ic, fn in (("Rinomina…", "pen", win.rename_firma), ("Predefinita", "star", win.set_default_firma),
                            ("Rimuovi…", None, win.remove_firma)):
            b = QPushButton(txt)
            if ic:
                b.setIcon(icon(ic))
            b.clicked.connect(lambda _, fn=fn: self.on_selected(fn))
            b.setEnabled(False)
            row.addWidget(b)
            self.sel_btns.append(b)
        row.addStretch()
        lay.addLayout(row)
        self.list.itemSelectionChanged.connect(
            lambda: [b.setEnabled(bool(self.list.selectedItems())) for b in self.sel_btns])
        self.list.itemDoubleClicked.connect(lambda _: self.on_selected(win.rename_firma))
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Chiudi")
        bb.rejected.connect(self.accept)
        lay.addWidget(bb)
        self.refill()

    def refill(self):
        self.list.fill(self.win.cfg["firme"], default_firma(self.win.cfg))

    def on_selected(self, fn):
        r = self.list.currentRow()
        if r >= 0:
            fn(r)
            self.refill()

    def new(self):
        self.win.new_firma()
        self.refill()


class SettingsDialog(QDialog):
    """Impostazioni: salvataggio, luogo e data, apertura dei file, le mie firme. Si applicano subito."""

    def __init__(self, parent, cfg):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Impostazioni")
        self.setMinimumWidth(560)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(22, 18, 22, 16)
        lay.setSpacing(6)

        def hint(t):
            l = QLabel(t)
            l.setObjectName("hint")
            l.setWordWrap(True)
            return l

        def section(t):
            lay.addSpacing(10)
            lay.addWidget(self._title(t))

        def btn(t, fn):
            b = QPushButton(t)
            b.setAutoDefault(False)  # il pulsante principale resta «Chiudi»
            b.clicked.connect(fn)
            return b

        # --- salvataggio
        section("Salvataggio")
        g = QGridLayout()
        g.setHorizontalSpacing(12)
        g.setVerticalSpacing(8)
        self.salva = Combo()
        for k, t in SALVATAGGI:
            self.salva.addItem(t, k)
        self.salva.setCurrentIndex(max(self.salva.findData(cfg.get("salvataggio", "chiedi")), 0))
        self.salva.currentIndexChanged.connect(self.store)
        g.addWidget(QLabel("Quando premi Salva"), 0, 0)
        g.addWidget(self.salva, 0, 1)
        self.suffix = QLineEdit(cfg.get("suffisso", SUFFISSO))
        self.suffix.setPlaceholderText(SUFFISSO)
        self.suffix.setToolTip("Scrivi {data} per aggiungere la data di oggi, es. _firmato_{data}")
        self.suffix.textChanged.connect(self.store)
        g.addWidget(QLabel("Nome della copia"), 1, 0)
        g.addWidget(self.suffix, 1, 1)
        g.setColumnStretch(1, 1)
        lay.addLayout(g)
        self.suffix_preview = hint("")
        lay.addWidget(self.suffix_preview)

        # --- luogo e data
        section("Luogo e data")
        row = QHBoxLayout()
        row.addWidget(QLabel("Formato della data"))
        self.fdata = Combo()
        oggi = datetime.date.today()
        for k, _ in FORMATI_DATA:
            self.fdata.addItem(fmt_data(oggi, k), k)
        self.fdata.setCurrentIndex(max(self.fdata.findData(cfg.get("formato_data", "num")), 0))
        self.fdata.currentIndexChanged.connect(self.store)
        row.addWidget(self.fdata, 1)
        lay.addLayout(row)

        # --- apertura dei file
        section("Apertura dei file")
        lay.addWidget(hint("Cartella proposta quando apri un PDF o scegli i PDF da firmare insieme."))
        row = QHBoxLayout()
        self.dir = QLineEdit(cfg["cartella"])
        self.dir.editingFinished.connect(self.save_dir)
        row.addWidget(self.dir, 1)
        row.addWidget(btn("Sfoglia…", self.browse))
        lay.addLayout(row)
        row = QHBoxLayout()
        self.recenti = QCheckBox("Ricorda i file aperti di recente")
        self.recenti.setChecked(cfg.get("ricorda_recenti", True))
        self.recenti.toggled.connect(self.store)
        row.addWidget(self.recenti)
        row.addStretch()
        self.svuota = btn("Svuota elenco", self.clear_recent)
        row.addWidget(self.svuota)
        lay.addLayout(row)

        # --- aggiornamenti
        section("Aggiornamenti")
        self.aggiorna = QCheckBox("Controlla all'avvio se c'è una nuova versione")
        self.aggiorna.setChecked(cfg.get("controlla_aggiornamenti", True))
        self.aggiorna.toggled.connect(self.store)
        lay.addWidget(self.aggiorna)
        lay.addWidget(hint("Legge da GitHub il numero dell'ultima versione: non invia documenti, firme né altri dati. "
                           "Con il pacchetto .deb l'aggiornamento si installa dall'app, dopo la tua conferma e la password."))

        # --- le mie firme
        section("Le mie firme")
        lay.addWidget(hint("Esporta le tue firme in un file per fare un backup o usarle su un altro computer. "
                           "Custodiscilo con cura: contiene la tua firma."))
        row = QHBoxLayout()
        self.exp = btn(" Esporta firme…", self.export)
        self.exp.setIcon(icon("upload"))
        row.addWidget(self.exp)
        b = btn(" Importa firme…", self.import_)
        b.setIcon(icon("open"))
        row.addWidget(b)
        row.addStretch()
        lay.addLayout(row)

        lay.addSpacing(12)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Salva e chiudi")
        bb.rejected.connect(self.save_and_close)
        ver = QLabel(f"{APP_NAME} {__version__}")
        ver.setObjectName("hint")
        row = QHBoxLayout()
        row.addWidget(ver)
        row.addWidget(bb, 1)
        lay.addLayout(row)
        self.update_state()

    @staticmethod
    def _title(t):
        l = QLabel(t)
        l.setObjectName("section")
        return l

    def showEvent(self, e):
        super().showEvent(e)
        # le righe che vanno a capo non entrano nel calcolo dell'altezza minima: la calcolo per la larghezza reale
        w = max(self.width(), self.minimumWidth())
        h = self.layout().totalHeightForWidth(w)
        self.setMinimumHeight(h)
        self.resize(w, h)

    def update_state(self):
        self.suffix_preview.setText(f"Esempio: contratto.pdf → contratto{copy_suffix(self.cfg)}.pdf")
        self.suffix_preview.setVisible(self.salva.currentData() != "sovrascrivi")
        self.suffix.setEnabled(self.salva.currentData() != "sovrascrivi")
        self.svuota.setEnabled(bool(self.cfg.get("recenti")))
        self.exp.setEnabled(bool(self.cfg["firme"]))

    def store(self):
        self.cfg.update(salvataggio=self.salva.currentData(), suffisso=self.suffix.text().strip() or SUFFISSO,
                        formato_data=self.fdata.currentData(), ricorda_recenti=self.recenti.isChecked(),
                        controlla_aggiornamenti=self.aggiorna.isChecked())
        if not self.recenti.isChecked():
            self.cfg["recenti"] = []  # chi non vuole i recenti non vuole nemmeno quelli vecchi
        save_config(self.cfg)
        self.update_state()

    def save_and_close(self):
        self.save_dir()  # la cartella scritta a mano senza Invio non è ancora salvata
        self.store()
        self.accept()

    def clear_recent(self):
        self.cfg["recenti"] = []
        save_config(self.cfg)
        self.update_state()

    def export(self):
        dst, _ = QFileDialog.getSaveFileName(self, "Esporta firme", os.path.expanduser(f"~/firme-{APP_NAME.lower()}.zip"),
                                             f"Firme di {APP_NAME} (*.zip)")
        if not dst:
            return
        if not dst.lower().endswith(".zip"):
            dst += ".zip"
        try:
            n = export_firme(self.cfg, dst)
        except Exception as ex:
            QMessageBox.critical(self, "Esporta firme", f"Esportazione non riuscita:\n{ex}")
            return
        QMessageBox.information(self, "Esporta firme", f"Esportat{'a' if n == 1 else 'e'} {n} firm{'a' if n == 1 else 'e'} in:\n{dst}")

    def import_(self):
        src, _ = QFileDialog.getOpenFileName(self, "Importa firme", os.path.expanduser("~"), f"Firme di {APP_NAME} (*.zip)")
        if not src:
            return
        try:
            added, dup = import_firme(self.cfg, src)
            save_config(self.cfg)
        except Exception as ex:
            QMessageBox.critical(self, "Importa firme", f"Importazione non riuscita:\n{ex}")
            return
        msg = f"Aggiunt{'a' if added == 1 else 'e'} {added} firm{'a' if added == 1 else 'e'}."
        if dup:
            msg += f"\n{dup} erano già presenti e sono state saltate."
        QMessageBox.information(self, "Importa firme", msg)
        self.update_state()

    def browse(self):
        d = QFileDialog.getExistingDirectory(self, "Cartella predefinita", self.dir.text())
        if d:
            self.dir.setText(d)
            self.save_dir()

    def save_dir(self):
        d = os.path.expanduser(self.dir.text().strip())
        if os.path.isdir(d):
            self.cfg["cartella"] = d
            save_config(self.cfg)


class SiglaDialog(QDialog):
    """Sigla (firma piccola) a margine di ogni pagina."""

    def __init__(self, parent, cfg, n_pages):
        super().__init__(parent)
        self.cfg = cfg
        self.setWindowTitle("Sigla tutte le pagine")
        self.setMinimumWidth(420)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.addWidget(SettingsDialog._title("Sigla tutte le pagine"))
        h = QLabel(f"Aggiunge una firma piccola a margine di ognuna delle {n_pages} pagine, come si fa con i "
                   "contratti. Le sigle restano modificabili prima di salvare.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        lay.addWidget(h)
        g = QGridLayout()
        g.setVerticalSpacing(8)
        self.firma = FirmaCombo(cfg)
        self.larg = QSpinBox()
        self.larg.setRange(20, 200)
        self.larg.setSuffix(" pt")
        self.larg.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)  # le frecce non rispettano lo stile; resta la rotella
        self.larg.setToolTip("Scrivi il valore o usa la rotella del mouse")
        self.larg.setValue(cfg.get("sigla_larghezza", 70))
        self.pos = Combo()
        for k, t in POSIZIONI:
            self.pos.addItem(t, k)
        self.pos.setCurrentIndex(max(self.pos.findData(cfg.get("sigla_posizione", "basso-destra")), 0))
        self.skip = QCheckBox("Escludi l'ultima pagina (dove metti la firma completa)")
        self.skip.setChecked(cfg.get("sigla_no_ultima", False))
        for r, (lbl, wdg) in enumerate((("Firma", self.firma), ("Larghezza", self.larg), ("Posizione", self.pos))):
            l = QLabel(lbl)
            l.setObjectName("hint")
            g.addWidget(l, r, 0)
            g.addWidget(wdg, r, 1)
        lay.addLayout(g)
        lay.addWidget(self.skip)
        bb = QDialogButtonBox()
        ok = bb.addButton("Aggiungi sigle", QDialogButtonBox.ButtonRole.AcceptRole)
        ok.setObjectName("primary")
        bb.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addSpacing(6)
        lay.addWidget(bb)

    def values(self):
        self.cfg.update(sigla_larghezza=self.larg.value(), sigla_posizione=self.pos.currentData(),
                        sigla_no_ultima=self.skip.isChecked())
        save_config(self.cfg)
        return self.firma.currentData(), self.larg.value(), self.pos.currentData(), self.skip.isChecked()


class BatchDialog(QDialog):
    """Firma in blocco: stessa firma su molti PDF."""

    def __init__(self, win, files=()):
        super().__init__(win)
        self.win, self.cfg = win, win.cfg
        self.setWindowTitle("Firma più PDF")
        self.resize(620, 600)
        self.setAcceptDrops(True)
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.addWidget(SettingsDialog._title("Firma più PDF insieme"))
        h = QLabel("Aggiungi i PDF (anche trascinandoli qui): a ognuno viene applicata la stessa firma.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        lay.addWidget(h)
        self.list = QListWidget()
        self.list.setObjectName("files")
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        lay.addWidget(self.list, 1)
        row = QHBoxLayout()
        self.edit_btns = []
        for txt, fn in (("Aggiungi PDF…", self.add_dialog), ("Rimuovi", self.remove), ("Svuota", self.list.clear)):
            b = QPushButton(txt)
            b.clicked.connect(fn)
            row.addWidget(b)
            self.edit_btns.append(b)
        row.addStretch()
        lay.addLayout(row)

        g = QGridLayout()
        g.setVerticalSpacing(8)
        self.firma = FirmaCombo(self.cfg)
        self.mode = Combo()
        self.mode.addItem("Automatica: sotto «Firma», «Il dichiarante»… (altrimenti in fondo all'ultima pagina)", "auto")
        self.mode.addItem("In fondo all'ultima pagina", "ultima")
        self.ref = win.placements(quiet=True) if win.doc else None
        if self.ref:
            self.mode.addItem(f"Come nel documento aperto ({len(self.ref)} firme)", "come")
        self.mode.currentIndexChanged.connect(lambda: self.firma.setEnabled(self.mode.currentData() != "come"))
        cap = win.caption()
        self.cap = QCheckBox(f"Aggiungi luogo e data: «{cap}»" if cap else "Luogo e data: nessuno (impostali nella colonna firme)")
        self.cap.setChecked(bool(cap))
        self.cap.setEnabled(bool(cap))
        for r, (lbl, wdg) in enumerate((("Firma", self.firma), ("Posizione", self.mode))):
            l = QLabel(lbl)
            l.setObjectName("hint")
            g.addWidget(l, r, 0)
            g.addWidget(wdg, r, 1)
        lay.addLayout(g)
        lay.addWidget(self.cap)
        self.new = QRadioButton(f"Crea nuovi file  (nome{copy_suffix(self.cfg)}.pdf accanto all'originale)")
        self.over = QRadioButton("Sovrascrivi gli originali")
        self.new.setChecked(True)
        lay.addWidget(self.new)
        lay.addWidget(self.over)
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        lay.addWidget(self.bar)
        bb = QDialogButtonBox()
        self.ok = bb.addButton("Firma", QDialogButtonBox.ButtonRole.AcceptRole)
        self.ok.setObjectName("primary")
        self.close_btn = bb.addButton("Annulla", QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.run)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        self.list.model().rowsInserted.connect(self.update_ok)
        self.list.model().rowsRemoved.connect(self.update_ok)
        self.add_files(files)
        self.update_ok()

    def update_ok(self):
        n = self.list.count()
        self.ok.setText(f"Firma {n} PDF" if n else "Firma")
        self.ok.setEnabled(bool(n) and bool(self.cfg["firme"]))

    def add_files(self, files):
        have = {self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())}
        for f in files:
            f = os.path.abspath(f)
            if f not in have and f.lower().endswith(".pdf"):
                it = QListWidgetItem(icon("file", "#5b6680"), os.path.basename(f))
                it.setData(Qt.ItemDataRole.UserRole, f)
                it.setToolTip(f)
                self.list.addItem(it)
                have.add(f)

    def add_dialog(self):
        start = self.cfg["cartella"] if os.path.isdir(self.cfg["cartella"]) else os.path.expanduser("~")
        files, _ = QFileDialog.getOpenFileNames(self, "Scegli i PDF da firmare", start, "PDF (*.pdf)")
        self.add_files(files)

    def remove(self):
        for it in self.list.selectedItems():
            self.list.takeItem(self.list.row(it))

    def dragEnterEvent(self, e):
        if PdfView._pdfs_from(e.mimeData()):
            e.acceptProposedAction()

    def dropEvent(self, e):
        self.add_files(PdfView._pdfs_from(e.mimeData()))

    def run(self):
        if self.over.isChecked() and QMessageBox.question(
                self, "Sovrascrivi", f"Sovrascrivere {self.list.count()} PDF originali?") != QMessageBox.StandardButton.Yes:
            return
        path, mode = self.firma.currentData(), self.mode.currentData()
        caption = self.win.caption() if self.cap.isChecked() else ""
        self.ok.setEnabled(False)
        self.setAcceptDrops(False)
        for wdg in self.edit_btns + [self.close_btn, self.firma, self.mode, self.cap, self.new, self.over]:
            wdg.setEnabled(False)  # durante il lavoro l'elenco non deve cambiare
        self.bar.setVisible(True)
        self.bar.setRange(0, self.list.count())
        ok = 0
        for i in range(self.list.count()):
            it = self.list.item(i)
            src = it.data(Qt.ItemDataRole.UserRole)
            try:
                dst = src if self.over.isChecked() else output_path(src, copy_suffix(self.cfg))
                where = sign_file(src, dst, path, caption, self.win.sig_width(), mode, self.ref,
                                  self.cfg.get("scansione", False))
                it.setIcon(icon("check", "#16a34a"))
                it.setText(f"{os.path.basename(src)}   →   {os.path.basename(dst)}  ·  {where}")
                it.setData(Qt.ItemDataRole.UserRole + 1, dst)
                ok += 1
            except Exception as ex:
                it.setIcon(icon("info", "#e5484d"))
                it.setText(f"{os.path.basename(src)}   ✗  {ex}")
            self.bar.setValue(i + 1)
            QApplication.processEvents()
        self.close_btn.setText("Chiudi")
        self.close_btn.setEnabled(True)
        self.ok.setVisible(False)
        done = [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).data(Qt.ItemDataRole.UserRole + 1)]
        if self.over.isChecked() and self.win.path and os.path.abspath(self.win.path) in done:
            # il PDF aperto è stato riscritto: ricaricarlo evita di salvarci sopra la versione vecchia
            if not self.win.dirty or QMessageBox.question(
                    self, "Documento aperto", "Il PDF aperto è stato appena firmato e sovrascritto.\n"
                    "Ricaricarlo? Le firme non ancora salvate nella finestra principale andranno perse.") \
                    == QMessageBox.StandardButton.Yes:
                self.win.dirty = False
                self.win.open_pdf(self.win.path, keep_view=True)
        if ok:
            folder = os.path.dirname(self.list.item(0).data(Qt.ItemDataRole.UserRole))
            self.win.toast.show_msg(f"Firmati {ok} PDF su {self.list.count()}", "Apri cartella",
                                    lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(folder)))


class AboutDialog(QDialog):
    """Finestra Info: tutto viene da app.json. Dimensioni fisse, non ridimensionabile."""
    WIDTH = 460  # larghezza minima

    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle(f"Informazioni su {INFO['nome']}")
        self.setMinimumWidth(self.WIDTH)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(28, 24, 28, 18)
        lay.setSpacing(6)
        ic = QLabel()
        ic.setPixmap(QPixmap(os.path.join(APP_DIR, "icona.png")).scaled(
            72, 72, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        t = QLabel(INFO["nome"])
        t.setObjectName("hero")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        d = QLabel(INFO.get("descrizione", ""))
        d.setObjectName("hint")
        d.setWordWrap(True)
        d.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(d)
        lay.addSpacing(10)

        alg = INFO.get("algoritmo_firma", {})
        aut = INFO.get("autore", {})
        gh = aut.get("github", "")
        lic = INFO.get("licenza", {})

        def link(url, testo):
            return f'<a href="{url}" style="color:{ACCENT}; text-decoration:none">{testo}</a>'
        nuova = getattr(parent, "new_version", None)  # trovata all'avvio dal controllo aggiornamenti
        rows = [("Versione", INFO["versione"] + (f' · {link(gh + "/releases/latest", f"disponibile la {nuova}")}' if nuova and gh else "")),
                ("Algoritmo firma", f"{alg.get('nome', '')} {alg.get('versione', '')}".strip()),
                ("Autore", aut.get("nome", "")),
                ("GitHub", link(gh, gh.removeprefix("https://")) if gh else ""),
                # AGPL §5d: l'interfaccia deve mostrare licenza e assenza di garanzia
                ("Licenza", f'{link(lic.get("url", ""), lic["nome"])} · senza alcuna garanzia' if lic.get("nome") else ""),
                ("Componenti", f"PyQt {PYQT_VERSION_STR} · PyMuPDF {pymupdf.VersionBind} · "
                               f"Python {sys.version.split()[0]}")]
        grid = QGridLayout()
        grid.setHorizontalSpacing(14)
        grid.setVerticalSpacing(7)
        for r, (k, v) in enumerate((k, v) for k, v in rows if v):  # le voci vuote in app.json non compaiono
            kl = QLabel(k)
            kl.setObjectName("hint")
            vl = QLabel(v)
            vl.setWordWrap(k in ("Componenti", "Licenza"))  # le altre voci sono brevi: a capo spezzerebbe link e nomi
            vl.setOpenExternalLinks(True)
            vl.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            if k == "Algoritmo firma" and alg.get("descrizione"):
                vl.setToolTip(alg["descrizione"])
            grid.addWidget(kl, r, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)
            grid.addWidget(vl, r, 1)
        lay.addLayout(grid)
        lay.addSpacing(12)
        if INFO.get("anno"):
            c = QLabel(f"© {INFO['anno']} {aut.get('nome', '')}")
            c.setObjectName("hint")
            c.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(c)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        bb.button(QDialogButtonBox.StandardButton.Close).setText("Chiudi")
        bb.rejected.connect(self.accept)
        lay.addWidget(bb)

    def showEvent(self, e):
        super().showEvent(e)
        # misura fissa calcolata col contenuto vero (righe a capo comprese): niente ridimensionamento
        w = max(self.WIDTH, self.layout().minimumSize().width())  # un link lungo non va a capo: allarga
        self.setFixedSize(w, self.layout().totalHeightForWidth(w))
