"""Finestra principale: coordina documento, firme, salvataggio e annulla/ripeti."""
import os
import threading

import pymupdf
from PyQt6.QtCore import pyqtSignal, QByteArray, QDate, QPointF, QSize, Qt, QUrl
from PyQt6.QtGui import QAction, QDesktopServices, QIcon, QKeySequence
from PyQt6.QtWidgets import (QApplication, QCheckBox, QDateEdit, QFileDialog, QFrame, QHBoxLayout, QInputDialog, QLabel,
                             QLineEdit, QMainWindow, QMenu, QMessageBox, QPushButton, QSizePolicy, QSpinBox,
                             QStackedWidget, QToolBar, QToolButton, QVBoxLayout, QWidget)

from sigla.aggiornamenti import nuova_versione, pagina_download
from sigla.config import APP_DIR, APP_NAME, copy_suffix, default_firma, fmt_data, import_firma, load_config, save_config
from sigla.pdf import auto_placements, find_sign_spots, output_path, placement_at, sigla_placements, write_signed
from sigla.ui.dialoghi import (AboutDialog, BatchDialog, CreatorDialog, DrawDialog, MyFirmeDialog, NewFirmaDialog,
                               SettingsDialog, SiglaDialog)
from sigla.ui.scena import DEFAULT_SIG_W, PAGE_GAP, PdfView, SignatureItem
from sigla.ui.tema import ACCENT, app_icon_pixmap, icon, stamp_cursor
from sigla.ui.widget import Coach, FirmeList, ThumbList, Toast, Welcome

class MainWindow(QMainWindow):
    update_found = pyqtSignal(str)  # emesso dal thread del controllo aggiornamenti

    def __init__(self):
        super().__init__()
        self.new_version = None  # versione più nuova trovata su GitHub (la mostra anche la finestra Info)
        self.update_found.connect(self.show_update)
        self.cfg = load_config()
        self.doc = None
        self.path = None
        self.password = None
        self.dirty = False
        self.resize(1200, 900)
        self.setMinimumSize(720, 480)
        if self.cfg.get("finestra"):
            self.restoreGeometry(QByteArray.fromBase64(self.cfg["finestra"].encode()))
        self.setWindowIcon(QIcon(os.path.join(APP_DIR, "icona.png")))

        self.view = PdfView(self)
        self.view.scene().selectionChanged.connect(self.update_status)
        self.view.verticalScrollBar().valueChanged.connect(self.update_status)

        # barra strumenti
        tb = self.tb = QToolBar()
        tb.setMovable(False)
        tb.setIconSize(QSize(18, 18))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.addToolBar(tb)

        def act(text, ic, fn, key=None, tip=None, only_icon=False, color="#1f2a44"):
            a = QAction(icon(ic, color), text, self)
            a.triggered.connect(fn)
            if key:
                a.setShortcut(key)
            a.setToolTip(f"{tip or text}  ({QKeySequence(key).toString()})" if key else (tip or text))
            tb.addAction(a)
            if only_icon:
                tb.widgetForAction(a).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            return a

        self.a_open = act("Apri", "open", self.open_dialog, "Ctrl+O", "Apri un PDF")
        self.recent_menu = QMenu(self)
        self.a_open.setMenu(self.recent_menu)
        tb.widgetForAction(self.a_open).setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        self.a_save = act("Salva", "save", self.save, "Ctrl+S", "Applica le firme e salva", color="#ffffff")
        tb.widgetForAction(self.a_save).setObjectName("primary")
        tb.addSeparator()
        self.a_undo = act("Annulla", "undo", self.undo, "Ctrl+Z", only_icon=True)
        self.a_redo = act("Ripeti", "redo", self.redo, "Ctrl+Shift+Z", only_icon=True)
        tb.addSeparator()
        self.a_find = act("Trova dove firmare", "target", self.find_spots, "Ctrl+F",
                          "Cerca «Firma», «Il dichiarante»… e mette lì la firma predefinita")
        self.a_sigla = act("Sigla pagine", "layers", self.sigla_pages, "Ctrl+Shift+S",
                           "Aggiunge una sigla a margine di ogni pagina")
        tb.addSeparator()
        self.a_thumbs = act("Miniature", "panel", self.toggle_thumbs, "F4", "Mostra/nascondi le miniature",
                            only_icon=True)
        self.a_thumbs.setCheckable(True)
        self.a_thumbs.setChecked(self.cfg.get("miniature", True))
        self.a_prev = act("Pagina precedente", "prev", lambda: self.goto_page(self.page_spin.value() - 2),
                          "PgUp", only_icon=True)
        self.page_spin = QSpinBox()
        self.page_spin.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        self.page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.page_spin.setKeyboardTracking(False)
        self.page_spin.setFixedWidth(46)
        self.page_spin.valueChanged.connect(lambda v: self.goto_page(v - 1))
        tb.addWidget(self.page_spin)
        self.page_total = QLabel("/ 0")
        self.page_total.setObjectName("zoom")
        self.page_total_act = tb.addWidget(self.page_total)
        self.a_next = act("Pagina successiva", "next", lambda: self.goto_page(self.page_spin.value()),
                          "PgDown", only_icon=True)
        self.sep_zoom = tb.addSeparator()
        self.a_zout = act("Riduci", "zoom-out", lambda: self.view.zoom_by(1 / 1.2), "Ctrl+-",
                          "Riduci (anche Ctrl + rotella)", only_icon=True)
        self.zoom_label = QLabel("100%")
        self.zoom_label.setObjectName("zoom")
        self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_label_act = tb.addWidget(self.zoom_label)
        self.a_zin = act("Ingrandisci", "zoom-in", lambda: self.view.zoom_by(1.2), "Ctrl++",
                         "Ingrandisci (anche Ctrl + rotella)", only_icon=True)
        self.a_fit = act("Adatta alla larghezza", "fit", self.view.fit_width, "Ctrl+0", only_icon=True)
        self.addAction(QAction(self, shortcut=QKeySequence("Ctrl+="), triggered=lambda: self.view.zoom_by(1.2)))
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        self.a_settings = act("Impostazioni", "settings", self.settings, "Ctrl+,")
        # «Altro»: compare solo a finestra stretta e raccoglie zoom e impostazioni (vedi apply_responsive).
        # Le scorciatoie stanno sulla finestra: un'azione nascosta non risponde ai tasti.
        self.more_menu = QMenu(self)
        for a in (self.a_zin, self.a_zout, self.a_fit, None, self.a_settings):
            if a is None:
                self.more_menu.addSeparator()
                continue
            key = a.shortcut()
            a.setShortcut(QKeySequence())
            self.addAction(QAction(self, shortcut=key, triggered=a.trigger))
            m = self.more_menu.addAction(a.icon(), a.text(), a.trigger)
            m.setShortcut(key)  # mostrata nel menu
            m.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)  # ma attiva solo sulla finestra
            if a is not self.a_settings:
                self.doc_actions_menu = getattr(self, "doc_actions_menu", []) + [m]
        self.a_more = QAction(icon("more"), "Altro", self)
        self.a_more.setToolTip("Zoom e impostazioni")
        self.a_more.setMenu(self.more_menu)
        tb.addAction(self.a_more)
        tb.widgetForAction(self.a_more).setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        tb.widgetForAction(self.a_more).setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.a_more.setVisible(False)
        self.doc_actions = [self.a_save, self.a_prev, self.a_next, self.a_zout, self.a_zin, self.a_fit,
                            self.a_find, self.a_sigla, self.a_thumbs]

        # barra laterale firme
        side = QWidget()
        side.setObjectName("side")
        side.setFixedWidth(260)
        self.side = side
        sl = QVBoxLayout(side)
        sl.setContentsMargins(14, 16, 14, 14)
        sl.addWidget(SettingsDialog._title("Firme"))
        h = QLabel("Trascina una firma sulla pagina, oppure cliccala e poi clicca dove vuoi firmare. "
                   "Clic destro per rinominarla o rimuoverla.")
        h.setWordWrap(True)
        h.setObjectName("hint")
        sl.addWidget(h)
        self.firme = FirmeList()
        self.firme.itemClicked.connect(self.start_place_mode)
        self.firme.itemDoubleClicked.connect(self.place_center)
        self.firme.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.firme.customContextMenuRequested.connect(self.firma_menu)
        sl.addWidget(self.firme, 1)
        self.cta = QPushButton("  Crea la tua prima firma")
        self.cta.setObjectName("cta")
        self.cta.setIcon(icon("pen", ACCENT))
        self.cta.clicked.connect(self.new_firma)
        sl.addWidget(self.cta)
        self.cta_space = QWidget()
        sl.addWidget(self.cta_space, 1)

        opt = QFrame()
        opt.setObjectName("opts")
        ol = QVBoxLayout(opt)
        ol.setContentsMargins(12, 10, 12, 12)
        ol.setSpacing(6)
        t = QLabel("Aggiungi alla firma")
        t.setObjectName("subsection")
        ol.addWidget(t)
        self.chk_luogo = QCheckBox("Luogo")
        self.chk_luogo.setChecked(self.cfg["mostra_luogo"])
        self.luogo = QLineEdit(self.cfg["luogo"])
        self.luogo.setPlaceholderText("es. Palermo")
        self.chk_data = QCheckBox("Data")
        self.chk_data.setChecked(self.cfg["mostra_data"])
        self.data = QDateEdit(QDate.currentDate())
        self.data.setCalendarPopup(True)
        self.data.setDisplayFormat("dd/MM/yyyy")
        for w in (self.chk_luogo, self.luogo, self.chk_data, self.data):
            ol.addWidget(w)
        self.anteprima = QLabel()
        self.anteprima.setWordWrap(True)
        self.anteprima.setObjectName("hint")
        ol.addWidget(self.anteprima)
        self.chk_luogo.toggled.connect(self.options_changed)
        self.chk_data.toggled.connect(self.options_changed)
        self.luogo.textChanged.connect(self.options_changed)
        self.data.dateChanged.connect(self.options_changed)
        sl.addWidget(opt)

        row = QHBoxLayout()
        b = QPushButton(" Nuova")
        b.setObjectName("soft")  # evidenziato con discrezione: il blu pieno resta a Salva
        b.setIcon(icon("pen", ACCENT))
        b.setToolTip("Importa, genera o disegna una nuova firma")
        b.clicked.connect(self.new_firma)
        row.addWidget(b)
        b = QPushButton(" Gestisci")
        b.setIcon(icon("list"))
        b.setToolTip("Le mie firme: rinomina, predefinita, rimuovi")
        b.clicked.connect(self.manage_firme)
        row.addWidget(b)
        sl.addLayout(row)
        self.refresh_firme()

        self.welcome = Welcome(self)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.welcome)
        self.stack.addWidget(self.view)
        central = QWidget()
        cl = QHBoxLayout(central)
        cl.setContentsMargins(0, 0, 0, 0)
        cl.setSpacing(0)
        self.thumbs = ThumbList(self)
        self.thumbs_panel = QWidget()
        self.thumbs_panel.setObjectName("thumbs_panel")
        self.thumbs_panel.setFixedWidth(140)
        tl = QVBoxLayout(self.thumbs_panel)
        tl.setContentsMargins(4, 8, 4, 8)
        tl.addWidget(self.thumbs)
        cl.addWidget(self.thumbs_panel)
        cl.addWidget(self.stack, 1)
        cl.addWidget(side)
        self.setCentralWidget(central)
        self.toast = Toast(self.stack)
        self.coach = Coach(self)
        self.history, self.hpos = [[]], 0
        self.refresh_recent()

        self.options_changed()
        self.status = QLabel()
        self.statusBar().addWidget(self.status, 1)
        info = QToolButton()
        info.setObjectName("info")
        info.setIcon(icon("info", "#8a93a8"))
        info.setIconSize(QSize(15, 15))
        info.setAutoRaise(True)
        info.setToolTip(f"Informazioni su {APP_NAME}  (F1)")
        info.setCursor(Qt.CursorShape.PointingHandCursor)
        info.clicked.connect(self.about)
        self.statusBar().addPermanentWidget(info)
        self.addAction(QAction(self, shortcut=QKeySequence("F1"), triggered=self.about))
        self.update_title()
        self.update_status()

    # --- stato
    def snapshot(self):
        return sorted((s.path, round(s.pos().x(), 2), round(s.pos().y(), 2), round(s.w, 2), s.caption)
                      for s in self.view.signatures())

    def changed(self):
        snap = self.snapshot()
        if snap != self.history[self.hpos]:  # nuovo passo nella cronologia annulla/ripeti
            self.history = self.history[:self.hpos + 1] + [snap]
            self.hpos += 1
        self.dirty = bool(snap)
        self.update_title()
        self.update_status()

    def restore(self, snap):
        for s in self.view.signatures():
            self.view.scene().removeItem(s)
        for path, x, y, w, cap in snap:
            it = SignatureItem(path, w, cap)
            it.setPos(x, y)
            self.view.scene().addItem(it)
        self.dirty = bool(snap)
        self.update_title()
        self.update_status()

    def undo(self):
        if self.hpos > 0:
            self.hpos -= 1
            self.restore(self.history[self.hpos])

    def redo(self):
        if self.hpos < len(self.history) - 1:
            self.hpos += 1
            self.restore(self.history[self.hpos])

    def goto_page(self, i):
        if self.view.pages and 0 <= i < len(self.view.pages):
            r = self.view.pages[i].sceneBoundingRect()
            self.view.verticalScrollBar().setValue(int(self.view.mapFromScene(QPointF(0, r.top() - PAGE_GAP / 2)).y()
                                                       + self.view.verticalScrollBar().value()))

    def toggle_thumbs(self):
        self.cfg["miniature"] = self.a_thumbs.isChecked()
        save_config(self.cfg)
        self.update_title()

    def open_or_batch(self, pdfs):
        if len(pdfs) > 1:
            self.batch(pdfs)
        else:
            self.open_pdf(pdfs[0])

    def batch(self, files=()):
        if not self.cfg["firme"]:
            self.toast.show_msg("Crea prima una firma", "Nuova firma", self.new_firma)
            return
        BatchDialog(self, files).exec()

    def add_placed(self, placed):
        """Aggiunge firme già calcolate (pagina, Rect PDF, file, didascalia, larghezza) come un solo passo annullabile."""
        sc = self.view.scene()
        sc.clearSelection()
        items = []
        for pno, rect, path, caption, w in placed:
            it = SignatureItem(path, w, caption)
            it.setPos(self.view.pages[pno].pos() + QPointF(rect.x0, rect.y0))
            sc.addItem(it)
            it.setSelected(True)
            items.append(it)
        if items:
            self.view.centerOn(items[-1])
            self.changed()
            self.view.setFocus()

    def find_spots(self):
        path = default_firma(self.cfg)
        if not path:
            self.toast.show_msg("Crea prima una firma", "Nuova firma", self.new_firma)
            return
        cap, w = self.caption(), self.sig_width()
        spots = find_sign_spots(self.doc)
        if len(spots) <= 1:
            placed, where = auto_placements(self.doc, path, cap, w)
            self.add_placed(placed)
            msg = "Firma aggiunta " + where if spots else "Nessuna dicitura di firma trovata: firma " + where
            self.toast.show_msg(msg)
            return
        menu = QMenu(self)
        menu.setToolTipsVisible(True)
        title = menu.addAction(f"Trovati {len(spots)} punti di firma: scegli dove firmare")
        title.setEnabled(False)
        for pno, hit, line in spots:
            a = menu.addAction(icon("target", ACCENT), f"Pag. {pno + 1} — {line}")
            a.triggered.connect(lambda _, p=pno, h=hit: self.add_placed([placement_at(self.doc, p, h, path, cap, w)]))
        menu.addSeparator()
        menu.addAction("In fondo all'ultima pagina").triggered.connect(
            lambda: self.add_placed([placement_at(self.doc, len(self.doc) - 1, None, path, cap, w)]))
        btn = self.findChild(QToolBar).widgetForAction(self.a_find)
        menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))

    def sigla_pages(self):
        if not self.cfg["firme"]:
            self.toast.show_msg("Crea prima una firma", "Nuova firma", self.new_firma)
            return
        d = SiglaDialog(self, self.cfg, len(self.doc))
        if d.exec():
            path, w, pos, skip = d.values()
            placed = sigla_placements(self.doc, path, w, pos, skip)
            self.add_placed(placed)
            self.view.scene().clearSelection()
            self.toast.show_msg(f"Sigla aggiunta a {len(placed)} pagin{'a' if len(placed) == 1 else 'e'} "
                                "(Ctrl+Z per annullare)")

    def sig_width(self):
        return self.cfg.get("larghezza", DEFAULT_SIG_W)

    def refresh_firme(self):
        self.firme.fill(self.cfg["firme"], default_firma(self.cfg))
        has = bool(self.cfg["firme"])
        self.firme.setVisible(has)
        self.cta.setVisible(not has)
        self.cta_space.setVisible(not has)

    def firma_menu(self, pos):
        it = self.firme.itemAt(pos)
        if not it:
            return
        r = self.firme.row(it)
        menu = QMenu(self)
        menu.addAction(icon("pen"), "Rinomina…", lambda: self.rename_firma(r))
        a = menu.addAction(icon("star"), "Imposta come predefinita", lambda: self.set_default_firma(r))
        a.setToolTip("Usata da «Trova dove firmare» e dalla firma di più PDF")
        a.setEnabled(self.cfg["firme"][r]["file"] != default_firma(self.cfg))
        menu.setToolTipsVisible(True)
        menu.addSeparator()
        menu.addAction(icon("info", "#e5484d"), "Rimuovi…", lambda: self.remove_firma(r))
        menu.exec(self.firme.viewport().mapToGlobal(pos))

    def rename_firma(self, r):
        nome, ok = QInputDialog.getText(self, "Rinomina firma", "Nome:", text=self.cfg["firme"][r]["nome"])
        if ok and nome.strip():
            self.cfg["firme"][r]["nome"] = nome.strip()
            save_config(self.cfg)
            self.refresh_firme()

    def set_default_firma(self, r):
        self.cfg["predefinita"] = self.cfg["firme"][r]["file"]
        save_config(self.cfg)
        self.refresh_firme()

    def remove_firma(self, r):
        f = self.cfg["firme"][r]
        if QMessageBox.question(self, "Rimuovi firma", f"Rimuovere la firma «{f['nome']}»?\n"
                                "Le firme già salvate nei PDF non cambiano.") != QMessageBox.StandardButton.Yes:
            return
        del self.cfg["firme"][r]
        save_config(self.cfg)  # il file resta finché l'app è aperta (può essere sulla pagina): lo pulisce cleanup_firme
        self.refresh_firme()

    def import_firma_dialog(self):
        src, _ = QFileDialog.getOpenFileName(self, "Scegli l'immagine della tua firma", os.path.expanduser("~"),
                                             "Firme (*.png *.jpg *.jpeg *.svg)")
        if not src:
            return
        nome, ok = QInputDialog.getText(self, "Nome firma", "Nome:",
                                        text=os.path.splitext(os.path.basename(src))[0])
        if not ok:
            return
        vett = False
        if not src.lower().endswith(".svg"):
            vett = QMessageBox.question(
                self, "Converti in SVG", "Convertire l'immagine in SVG vettoriale?\n"
                "(consigliato: tratti nitidi e sfondo trasparente)") == QMessageBox.StandardButton.Yes
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            import_firma(self.cfg, src, nome.strip() or "Firma", vett)
            save_config(self.cfg)
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Errore", f"Impossibile importare la firma:\n{ex}")
            return
        QApplication.restoreOverrideCursor()
        self.refresh_firme()

    def create_firma(self):
        if CreatorDialog(self, self.cfg).exec():
            self.refresh_firme()

    def draw_firma(self):
        if DrawDialog(self, self.cfg).exec():
            self.refresh_firme()

    def new_firma(self):
        d = NewFirmaDialog(self)
        if d.exec():
            {"importa": self.import_firma_dialog, "genera": self.create_firma, "disegna": self.draw_firma}[d.choice]()

    def manage_firme(self):
        MyFirmeDialog(self).exec()
        self.refresh_firme()

    def refresh_recent(self):
        rec = [p for p in self.cfg.get("recenti", []) if os.path.exists(p)]
        self.recent_menu.clear()
        self.recent_menu.addAction(icon("files"), "Firma più PDF insieme…", lambda: self.batch())
        self.recent_menu.addSeparator()
        for p in rec[:8]:
            self.recent_menu.addAction(icon("file", "#5b6680"), os.path.basename(p),
                                       lambda p=p: self.open_pdf(p)).setToolTip(p)
        if not rec:
            self.recent_menu.addAction("Nessun file recente").setEnabled(False)
        self.welcome.refresh(rec)

    def add_recent(self, path):
        if not self.cfg.get("ricorda_recenti", True):
            return
        path = os.path.abspath(path)
        self.cfg["recenti"] = [path] + [p for p in self.cfg.get("recenti", []) if p != path][:9]
        save_config(self.cfg)
        self.refresh_recent()

    def update_title(self):
        name = os.path.basename(self.path) if self.path else APP_NAME
        self.setWindowTitle(("● " if self.dirty else "") + name + (f" — {APP_NAME}" if self.path else ""))
        for a in self.doc_actions + getattr(self, "doc_actions_menu", []):
            a.setEnabled(bool(self.doc))
        self.a_save.setEnabled(bool(self.doc) and self.dirty)
        self.a_save.setToolTip("Applica le firme e salva  (Ctrl+S)" if self.dirty
                               else "Aggiungi almeno una firma per poter salvare")
        self.page_spin.setEnabled(bool(self.doc))
        if not self.doc:
            self.page_spin.setSpecialValueText(" ")  # niente "0" senza documento
            self.page_spin.setRange(0, 0)
            self.page_total.setText("")
        self.a_undo.setEnabled(self.hpos > 0)
        self.a_redo.setEnabled(self.hpos < len(self.history) - 1)
        self.stack.setCurrentWidget(self.view if self.doc else self.welcome)
        self.thumbs_panel.setVisible(bool(self.doc) and self.a_thumbs.isChecked()
                                     and not getattr(self, "thumbs_auto_hidden", False))
        if getattr(self, "coach", None):
            self.coach.refresh()  # dopo setCurrentWidget, che porta la vista sopra la guida

    def update_status(self):
        if not self.doc:
            self.status.setText("Nessun documento aperto")
            return
        n = len(self.view.signatures())
        pg = self.view.current_page()
        self.page_spin.blockSignals(True)
        self.page_spin.setSpecialValueText("")  # il testo speciale vale solo senza documento (altrimenti nasconde «1»)
        self.page_spin.setRange(1, len(self.doc))
        self.page_spin.setValue(pg.pno + 1 if pg else 1)
        self.page_spin.blockSignals(False)
        self.page_total.setText(f"/ {len(self.doc)}")
        if pg and self.thumbs.currentRow() != pg.pno and pg.pno < self.thumbs.count():
            self.thumbs.setCurrentRow(pg.pno)
        if self.view.place_path:
            return
        if self.view.scene().selectedItems():
            txt = "Trascina per spostare  ·  frecce per i ritocchi (Maiusc = 10 pt)  ·  pallino blu per ridimensionare  ·  Canc per eliminare"
        elif n:
            txt = f"{n} firm{'a' if n == 1 else 'e'} da applicare  ·  premi Salva per scriverle nel PDF"
        else:
            txt = "Trascina una firma dalla colonna a destra sulla pagina"
        self.status.setText(txt)

    def caption(self):
        parts = []
        if self.chk_luogo.isChecked() and self.luogo.text().strip():
            parts.append(self.luogo.text().strip())
        if self.chk_data.isChecked():
            parts.append(fmt_data(self.data.date().toPyDate(), self.cfg.get("formato_data", "num")))
        return ", ".join(parts)

    def options_changed(self):
        self.luogo.setEnabled(self.chk_luogo.isChecked())
        self.data.setEnabled(self.chk_data.isChecked())
        c = self.caption()
        self.anteprima.setText(f"Anteprima: «{c}»" if c else "Solo firma")
        self.cfg.update(mostra_luogo=self.chk_luogo.isChecked(), mostra_data=self.chk_data.isChecked(),
                        luogo=self.luogo.text().strip())
        save_config(self.cfg)
        for it in self.view.scene().selectedItems():  # aggiorna anche le firme selezionate
            if isinstance(it, SignatureItem):
                it.set_caption(c)
        if hasattr(self, "history") and self.doc:
            self.changed()
        if self.view.ghost:
            self.view.ghost.set_caption(c)

    def start_place_mode(self, item):
        if not self.doc:
            self.statusBar().showMessage("Apri prima un PDF", 3000)
            return
        self.view.place_path = item.data(Qt.ItemDataRole.UserRole)
        self.view.viewport().setCursor(stamp_cursor())
        self.view.scene().clearSelection()
        self.view.show_ghost(self.view.place_path)
        self.coach.refresh()
        self.status.setText(f"Clicca sulla pagina per apporre «{item.text().removeprefix('★ ')}»  ·  "
                            "Esc o clic destro per annullare")
        self.view.setFocus()

    def end_place_mode(self):
        self.view.place_path = None
        self.view.hide_ghost()
        self.coach.refresh()
        self.view.viewport().unsetCursor()
        self.firme.clearSelection()
        self.update_status()

    def place_center(self, item):
        """Doppio clic su una firma: la mette al centro della pagina visibile."""
        self.end_place_mode()
        pg = self.view.current_page()
        if pg:
            self.view.add_signature(item.data(Qt.ItemDataRole.UserRole), pg.sceneBoundingRect().center())
            self.view.setFocus()

    def confirm_discard(self):
        if not self.dirty:
            return True
        box = QMessageBox(self)
        box.setWindowTitle("Firme non salvate")
        box.setIconPixmap(app_icon_pixmap(48))
        box.setText("Ci sono firme non ancora salvate nel PDF.")
        box.setInformativeText("Vuoi salvarle prima di continuare?")
        b_save = box.addButton("Salva…", QMessageBox.ButtonRole.AcceptRole)
        b_drop = box.addButton("Non salvare", QMessageBox.ButtonRole.DestructiveRole)
        box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(b_save)
        box.exec()
        if box.clickedButton() == b_save:
            self.save()
            return not self.dirty  # salvato davvero (non annullato a metà)
        return box.clickedButton() == b_drop

    # --- apri
    def open_dialog(self):
        start = self.cfg["cartella"] if os.path.isdir(self.cfg["cartella"]) else os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(self, "Apri PDF", start, "PDF (*.pdf)")
        if path:
            self.open_pdf(path)

    def open_pdf(self, path, keep_view=False):
        if not keep_view and not self.confirm_discard():
            return
        doc, password = None, None
        try:
            doc = pymupdf.open(path)
            if not doc.is_pdf:
                raise ValueError("il file non è un PDF")
            if doc.needs_pass and keep_view and self.password and doc.authenticate(self.password):
                password = self.password
            elif doc.needs_pass:
                pw, ok = QInputDialog.getText(self, "PDF protetto", f"Password di «{os.path.basename(path)}»:",
                                              QLineEdit.EchoMode.Password)
                if not ok:
                    doc.close()
                    return
                if not doc.authenticate(pw):
                    raise ValueError("password errata")
                password = pw
        except Exception as ex:
            if doc:
                doc.close()
            QMessageBox.critical(self, "Errore", f"Impossibile aprire il PDF:\n{ex}")
            return
        if self.doc:
            self.doc.close()
        scroll = self.view.verticalScrollBar().value()
        zoom = self.view.transform().m11()
        auto_before = getattr(self.view, "auto_fit", True)
        self.doc, self.path, self.dirty, self.password = doc, path, False, password
        self.history, self.hpos = [[]], 0
        self.view.load(doc)
        self.thumbs.load(doc)
        self.add_recent(path)
        if keep_view:
            self.view.set_zoom(zoom)
            self.view.auto_fit = auto_before  # load() riattiva l'adattamento: rimetti la scelta di prima
            self.view.verticalScrollBar().setValue(scroll)
        self.view.render_visible()
        self.update_title()
        self.update_status()

    # --- salva
    def save(self):
        sigs = self.view.signatures()
        if not self.doc:
            return
        if not sigs:
            QMessageBox.information(self, "Salva", "Non ci sono firme da applicare.\n"
                                    "Trascina una firma dalla barra a destra sulla pagina.")
            return
        placed = self.placements()
        if placed is None:
            return

        mode = self.cfg.get("salvataggio", "chiedi")
        if mode == "sovrascrivi":
            target = self.path
        elif mode == "copia":
            target = output_path(self.path, copy_suffix(self.cfg))
        else:
            target = self.ask_target(len(placed))
        if not target:
            return
        self.write(placed, target)

    def ask_target(self, n):
        """Finestra «copia o sovrascrivi»; restituisce il percorso scelto o None."""
        box = QMessageBox(self)
        box.setWindowTitle("Salva PDF firmato")
        box.setIconPixmap(app_icon_pixmap(48))
        box.setText(f"Applicare {n} firm{'a' if n == 1 else 'e'} al documento?")
        box.setInformativeText("Una copia firmata lascia intatto l'originale. "
                               "Sovrascrivendo, l'originale viene sostituito dalla versione firmata.")
        b_over = box.addButton("Sovrascrivi l'originale", QMessageBox.ButtonRole.DestructiveRole)
        b_new = box.addButton("Salva una copia firmata…", QMessageBox.ButtonRole.AcceptRole)
        box.addButton("Annulla", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(b_new)
        box.exec()
        if box.clickedButton() == b_over:
            return self.path
        if box.clickedButton() == b_new:
            target, _ = QFileDialog.getSaveFileName(self, "Salva come", output_path(self.path, copy_suffix(self.cfg)),
                                                    "PDF (*.pdf)")
            if target and not target.lower().endswith(".pdf"):
                target += ".pdf"
            return target or None
        return None

    def write(self, placed, target):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            write_signed(self.doc, placed, target, self.password)
        except Exception as ex:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Errore", f"Salvataggio fallito, il file originale non è stato modificato:\n{ex}")
            return
        QApplication.restoreOverrideCursor()
        self.dirty = False
        self.open_pdf(target, keep_view=True)  # ricarica: le firme ora fanno parte del PDF
        self.toast.show_msg(f"PDF firmato salvato: {os.path.basename(target)}", "Apri cartella",
                            lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.dirname(target))))

    def placements(self, quiet=False):
        """Firme posizionate come (pagina, rettangolo PDF, file, didascalia, larghezza); None se una è fuori pagina."""
        placed = []
        for s in self.view.signatures():
            pg = self.view.page_at(s.sceneBoundingRect().center())
            if not pg:
                if quiet:
                    return None
                self.view.scene().clearSelection()
                s.setSelected(True)
                self.view.centerOn(s)
                QMessageBox.warning(self, "Salva", "Una firma è fuori dalla pagina: spostala sul foglio.")
                return None
            p = s.pos() - pg.pos()
            placed.append((pg.pno, pymupdf.Rect(p.x(), p.y(), p.x() + s.bw, p.y() + s.bh), s.path, s.caption, s.w))
        return placed

    def about(self):
        AboutDialog(self).exec()

    def check_updates(self):
        """Chiede a GitHub se c'è una versione più nuova, in un thread: l'avvio non aspetta la rete."""
        def work():
            v = nuova_versione()
            if v:
                try:
                    self.update_found.emit(v)
                except RuntimeError:  # finestra già chiusa
                    pass
        threading.Thread(target=work, daemon=True).start()

    def show_update(self, v):
        self.new_version = v
        self.toast.show_msg(f"È disponibile {APP_NAME} {v}", "Scarica",
                            lambda: QDesktopServices.openUrl(QUrl(pagina_download())))

    def settings(self):
        SettingsDialog(self, self.cfg).exec()
        self.refresh_firme()
        self.refresh_recent()
        self.options_changed()  # il formato della data cambia l'anteprima di luogo e data

    def apply_responsive(self):
        """Adatta la barra e le colonne alla larghezza: prima toglie i testi, poi stringe, mai nasconde comandi."""
        tb = getattr(self, "tb", None)
        if tb is None or not hasattr(self, "side"):
            return
        icon_only, text = Qt.ToolButtonStyle.ToolButtonIconOnly, Qt.ToolButtonStyle.ToolButtonTextBesideIcon
        level = 0
        # 0: tutto col testo · 1: testo solo su Salva · 2: solo icone · 3: zoom e impostazioni nel menu «Altro»
        for level in (0, 1, 2, 3):
            for a in (self.a_open, self.a_find, self.a_sigla, self.a_settings):
                if tb.widgetForAction(a):
                    tb.widgetForAction(a).setToolButtonStyle(icon_only if level >= 1 else text)
            tb.widgetForAction(self.a_save).setToolButtonStyle(icon_only if level >= 2 else text)
            for a in (self.sep_zoom, self.a_zout, self.a_zin, self.a_fit, self.a_settings, self.page_total_act):
                a.setVisible(level < 3)
            self.zoom_label_act.setVisible(level < 2)
            self.a_more.setVisible(level == 3)
            if tb.sizeHint().width() <= self.width():  # misura reale: dipende anche dal carattere di sistema
                break
        # miniature nascoste da sole se la pagina resterebbe troppo stretta (la preferenza resta com'è)
        self.thumbs_auto_hidden = self.width() - self.side.width() - self.thumbs_panel.width() < 560
        self.thumbs_panel.setVisible(bool(self.doc) and self.a_thumbs.isChecked() and not self.thumbs_auto_hidden)

    def showEvent(self, e):
        super().showEvent(e)
        self.apply_responsive()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.apply_responsive()
        if getattr(self, "coach", None):
            self.coach.refresh()
        if getattr(self, "toast", None) and self.toast.isVisible():
            self.toast.place()

    def closeEvent(self, e):
        if self.confirm_discard():
            self.cfg["finestra"] = bytes(self.saveGeometry().toBase64()).decode()
            save_config(self.cfg)
            e.accept()
        else:
            e.ignore()
