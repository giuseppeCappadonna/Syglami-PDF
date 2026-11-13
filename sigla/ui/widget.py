"""Widget riusabili: elenchi firme e miniature, menu a tendina, schermata iniziale, avvisi."""
import os

import pymupdf
from PyQt6.QtCore import QMimeData, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QDrag, QIcon, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import (QAbstractItemView, QComboBox, QFrame, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
                             QPushButton, QStyledItemDelegate, QVBoxLayout, QWidget)

from sigla.config import APP_DIR, default_firma
from sigla.ui.scena import PdfView
from sigla.ui.tema import ACCENT, firma_pixmap, icon, icon_pixmap, MIME_FIRMA, stamp_cursor, to_qimage

class FirmeList(QListWidget):
    """Elenco firme: si trascinano sulla pagina, oppure clic e poi clic sulla pagina."""

    def __init__(self):
        super().__init__()
        self.setObjectName("firme")
        self.setDragEnabled(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)
        self.setViewMode(QListWidget.ViewMode.IconMode)  # anteprima sopra, nome sotto
        self.setFlow(QListWidget.Flow.TopToBottom)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Static)
        self.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.setIconSize(QSize(196, 52))
        self.setUniformItemSizes(True)
        self.setSpacing(5)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)

    def fill(self, firme, default=None):
        self.clear()
        for f in firme:
            pix, _ = firma_pixmap(f["file"], 400)
            it = QListWidgetItem(QIcon(pix), ("★ " if f["file"] == default and len(firme) > 1 else "") + f["nome"])
            it.setData(Qt.ItemDataRole.UserRole, f["file"])
            it.setToolTip("Trascina sulla pagina, oppure clicca e poi clicca sulla pagina\n"
                          "Clic destro: rinomina, imposta come predefinita, rimuovi")
            self.addItem(it)

    def startDrag(self, actions):
        it = self.currentItem()
        if not it:
            return
        mime = QMimeData()
        mime.setData(MIME_FIRMA, it.data(Qt.ItemDataRole.UserRole).encode())
        drag = QDrag(self)
        drag.setMimeData(mime)
        pix = it.icon().pixmap(QSize(196, 52))
        drag.setPixmap(pix)
        drag.setHotSpot(pix.rect().center())
        drag.setDragCursor(stamp_cursor().pixmap(), Qt.DropAction.CopyAction)
        drag.exec(Qt.DropAction.CopyAction)


class Combo(QComboBox):
    """Menu a tendina che rispetta lo stile (il disegnatore predefinito ignora le regole ::item del QSS)."""

    def __init__(self, *a):
        super().__init__(*a)
        self.setItemDelegate(QStyledItemDelegate(self))


class FirmaCombo(Combo):
    def __init__(self, cfg):
        super().__init__()
        self.setIconSize(QSize(90, 24))
        for f in cfg["firme"]:
            self.addItem(QIcon(firma_pixmap(f["file"], 300)[0]), f["nome"], f["file"])
        i = self.findData(default_firma(cfg))
        self.setCurrentIndex(max(i, 0))


class ThumbList(QListWidget):
    """Miniature delle pagine, rese poche alla volta per non bloccare l'interfaccia."""
    W = 104

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setObjectName("thumbs")
        self.setViewMode(QListWidget.ViewMode.IconMode)
        self.setFlow(QListWidget.Flow.TopToBottom)
        self.setWrapping(False)
        self.setMovement(QListWidget.Movement.Static)
        self.setIconSize(QSize(self.W, int(self.W * 1.45)))
        self.setSpacing(4)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.todo = []
        self.timer = QTimer(self, interval=0, timeout=self.render_next)
        self.itemClicked.connect(lambda it: win.goto_page(self.row(it)))

    def load(self, doc):
        self.clear()
        for page in doc:
            pm = QPixmap(self.W, max(1, int(self.W * page.rect.height / page.rect.width)))
            pm.fill(QColor("white"))
            self.addItem(QListWidgetItem(QIcon(pm), str(page.number + 1)))
        self.todo = list(range(len(doc)))
        self.timer.start()

    def render_next(self):
        doc = self.win.doc
        for _ in range(3):
            if not self.todo or doc is None:
                self.timer.stop()
                return
            i = self.todo.pop(0)
            page = doc[i]
            z = self.W * 2 / page.rect.width  # x2: nitide su schermi HiDPI
            pm = QPixmap.fromImage(to_qimage(page.get_pixmap(matrix=pymupdf.Matrix(z, z))))
            pm.setDevicePixelRatio(2)
            ic = QIcon(pm)
            ic.addPixmap(pm, QIcon.Mode.Selected)  # niente velo colorato sulla pagina selezionata
            self.item(i).setIcon(ic)


class Welcome(QWidget):
    """Schermata senza documento: apri, trascina, recenti."""

    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setAcceptDrops(True)
        self.setObjectName("welcome")
        self.hover = False
        outer = QVBoxLayout(self)
        outer.addStretch(2)
        card = QFrame()
        card.setObjectName("card")
        card.setFixedWidth(460)
        lay = QVBoxLayout(card)
        lay.setContentsMargins(36, 32, 36, 28)
        lay.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(QPixmap(os.path.join(APP_DIR, "icona.png")).scaled(
            84, 84, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
        ic.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(ic)
        t = QLabel("Firma un PDF")
        t.setObjectName("hero")
        t.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(t)
        h = QLabel("Trascina qui un PDF (o più PDF per firmarli insieme), oppure aprilo.")
        h.setObjectName("hint")
        h.setWordWrap(True)  # con caratteri di sistema grandi la riga non ci sta
        h.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(h)
        b = QPushButton("  Apri PDF…")
        b.setObjectName("primary")
        b.setIcon(icon("open", "#ffffff"))
        b.setMinimumHeight(40)
        b.clicked.connect(win.open_dialog)
        lay.addSpacing(6)
        lay.addWidget(b)
        b = QPushButton("  Firma più PDF insieme…")
        b.setIcon(icon("files"))
        b.setToolTip("Applica la firma a molti PDF in un colpo solo (anche trascinandoli qui)")
        b.clicked.connect(lambda: win.batch())
        lay.addWidget(b)
        self.rec_title = QLabel("Recenti")
        self.rec_title.setObjectName("subsection")
        lay.addSpacing(10)
        lay.addWidget(self.rec_title)
        self.rec_box = QVBoxLayout()
        self.rec_box.setSpacing(2)
        lay.addLayout(self.rec_box)
        row = QHBoxLayout()
        row.addStretch()
        row.addWidget(card)
        row.addStretch()
        outer.addLayout(row)
        outer.addStretch(3)

    def refresh(self, recenti):
        while self.rec_box.count():
            self.rec_box.takeAt(0).widget().deleteLater()
        for p in recenti[:5]:
            txt = f"{os.path.basename(p)}    —    {os.path.dirname(p).replace(os.path.expanduser('~'), '~')}"
            b = QPushButton(self.fontMetrics().elidedText(txt, Qt.TextElideMode.ElideRight, 340))  # nomi lunghi: «…» (percorso intero nel tooltip)
            b.setObjectName("recent")
            b.setIcon(icon("file", "#5b6680"))
            b.setToolTip(p)
            b.clicked.connect(lambda _, p=p: self.win.open_pdf(p))
            self.rec_box.addWidget(b)
        self.rec_title.setVisible(bool(recenti))

    def dragEnterEvent(self, e):
        if PdfView._pdf_from(e.mimeData()):
            self.hover = True
            self.update()
            e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.hover = False
        self.update()

    def dropEvent(self, e):
        self.hover = False
        self.update()
        if pdfs := PdfView._pdfs_from(e.mimeData()):
            self.win.open_or_batch(pdfs)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#e8ebf2"))
        r = QRectF(self.rect()).adjusted(24, 24, -24, -24)
        p.setPen(QPen(QColor(ACCENT if self.hover else "#b9c1d3"), 2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(52, 97, 240, 30) if self.hover else Qt.BrushStyle.NoBrush)
        p.drawRoundedRect(r, 18, 18)


class Toast(QFrame):
    """Avviso temporaneo in basso, con un'azione opzionale."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setObjectName("toast")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 10, 10, 10)
        lay.setSpacing(12)
        self.ic = QLabel()
        self.ic.setPixmap(icon_pixmap("check", "#4ade80", 18, 2.6))
        self.text = QLabel()
        self.btn = QPushButton()
        self.btn.setObjectName("toastbtn")
        lay.addWidget(self.ic)
        lay.addWidget(self.text)
        lay.addWidget(self.btn)
        self.timer = QTimer(self, singleShot=True, interval=7000, timeout=self.hide)
        self.action = None
        self.btn.clicked.connect(lambda: (self.action and self.action(), self.hide()))
        self.hide()

    def show_msg(self, text, btn=None, action=None):
        self.text.setText(text)
        self.btn.setVisible(bool(btn))
        self.btn.setText(btn or "")
        self.action = action
        self.adjustSize()
        self.place()
        self.show()
        self.raise_()
        self.timer.start()

    def place(self):
        p = self.parentWidget()
        self.move((p.width() - self.width()) // 2, p.height() - self.height() - 28)


class Coach(QFrame):
    """Guida rapida in alto sulla pagina, finché non c'è almeno una firma."""
    LONG = ("<b>1</b>&nbsp; Trascina la tua firma dalla colonna a destra sul foglio"
            "&nbsp;&nbsp;·&nbsp;&nbsp;<b>2</b>&nbsp; Premi <b>Salva</b>")
    SHORT = "<b>1</b>&nbsp; Trascina la firma sul foglio&nbsp;&nbsp;·&nbsp;&nbsp;<b>2</b>&nbsp; <b>Salva</b>"

    def __init__(self, win):
        super().__init__(win.stack)
        self.win = win
        self.setObjectName("coach")
        lay = QHBoxLayout(self)
        lay.setContentsMargins(16, 8, 8, 8)
        lay.setSpacing(12)
        self.text = QLabel(self.LONG)
        lay.addWidget(self.text)
        b = self.btn = QPushButton(" Trova dove firmare")
        b.setObjectName("coachbtn")
        b.setIcon(icon("target", "#ffffff"))
        b.setToolTip("Cerca «Firma», «Il dichiarante»… nel testo e mette lì la firma")
        b.clicked.connect(win.find_spots)
        lay.addWidget(b)
        self.hide()

    def refresh(self):
        w = self.win
        show = bool(w.doc) and not w.view.signatures() and not w.view.place_path and bool(w.cfg["firme"])
        if show:
            p = self.parentWidget()
            for long_text, btn_text in ((True, " Trova dove firmare"), (False, " Trova dove firmare"), (False, "")):
                self.text.setText(self.LONG if long_text else self.SHORT)
                self.btn.setText(btn_text)
                self.adjustSize()
                if self.width() <= p.width() - 24:  # sta nella pagina: altrimenti versione più corta
                    break
            self.move((p.width() - self.width()) // 2, 14)
            self.raise_()
        self.setVisible(show)
