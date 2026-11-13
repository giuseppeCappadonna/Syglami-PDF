"""Vista del documento: pagine, firme posizionabili, zoom e trascinamento."""
import os

import pymupdf
from PyQt6.QtCore import QPointF, QRectF, QSize, Qt, QTimer
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QPixmap
from PyQt6.QtWidgets import QFrame, QGraphicsItem, QGraphicsObject, QGraphicsScene, QGraphicsView

from sigla.config import APP_DIR
from sigla.pdf import block_geom, CAP_COLOR
from sigla.ui.tema import ACCENT, firma_pixmap, MIME_FIRMA, stamp_cursor, to_qimage

PAGE_GAP = 28        # spazio tra le pagine (punti)


DEFAULT_SIG_W = 170  # larghezza firma appena posizionata (punti PDF)


class PageItem(QGraphicsItem):
    """Una pagina PDF: foglio bianco con ombra; l'immagine viene resa solo quando visibile."""

    def __init__(self, pno, w, h):
        super().__init__()
        self.pno, self.w, self.h = pno, w, h
        self.pix, self.scale_done = None, 0

    def boundingRect(self):
        return QRectF(-6, -6, self.w + 14, self.h + 16)

    def paint(self, p, opt, widget=None):
        p.setPen(Qt.PenStyle.NoPen)
        for i, a in enumerate((10, 16, 22)):  # ombra morbida
            p.setBrush(QColor(20, 30, 60, a))
            p.drawRoundedRect(QRectF(3 - i, 5 - i, self.w + 2 * i, self.h + 2 * i), 3 + i, 3 + i)
        p.setBrush(QColor("white"))
        p.drawRect(QRectF(0, 0, self.w, self.h))
        if self.pix:
            p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
            p.drawPixmap(QRectF(0, 0, self.w, self.h), self.pix, QRectF(self.pix.rect()))


class SignatureItem(QGraphicsObject):
    HANDLE = 9

    def __init__(self, path, w, caption=""):
        super().__init__()
        self.path = path
        self.pix, self.ratio = firma_pixmap(path)
        self.w = w  # larghezza della sola firma
        self.caption = caption
        self.mode = None
        self.hover = False
        self.ghost = False  # anteprima che segue il cursore durante il posizionamento
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
                      | QGraphicsItem.GraphicsItemFlag.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self.setZValue(10)

    def geom(self):
        return block_geom(self.w, self.ratio, self.caption)

    @property
    def bw(self):
        return self.geom()[2]

    @property
    def bh(self):
        return self.geom()[3]

    def set_caption(self, caption):
        self.prepareGeometryChange()
        self.caption = caption
        self.update()

    def _k(self):  # dimensione maniglie costante a schermo, indipendente dallo zoom
        v = self.scene().views()[0] if self.scene() and self.scene().views() else None
        return 1 / v.transform().m11() if v else 1

    def boundingRect(self):
        m = self.HANDLE * 2 * self._k()
        return QRectF(-m, -m, self.bw + 2 * m, self.bh + 2 * m)

    def resize_handle(self):
        s = self.HANDLE * self._k()
        return QRectF(self.bw - s, self.bh - s, 2 * s, 2 * s)

    def delete_handle(self):
        s = self.HANDLE * self._k()
        return QRectF(self.bw - s, -s, 2 * s, 2 * s)

    def paint(self, p, opt, widget=None):
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        fs, ch, bw, bh = self.geom()
        p.drawPixmap(QRectF(0, ch, self.w, bh - ch), self.pix, QRectF(self.pix.rect()))
        if self.caption:
            p.save()
            f = QFont("Helvetica")
            f.setPixelSize(100)  # disegno a 100px e scalo: i font Qt non accettano dimensioni frazionarie
            p.setFont(f)
            p.setPen(QColor.fromRgbF(*CAP_COLOR))
            p.translate(0, fs * 1.05)
            p.scale(fs / 100, fs / 100)
            p.drawText(QPointF(0, 0), self.caption)
            p.restore()
        k = self._k()
        if not self.isSelected():
            if self.hover and not self.ghost:  # suggerisce che la firma si può prendere
                p.setPen(QPen(QColor(52, 97, 240, 140), 1 * k, Qt.PenStyle.DashLine))
                p.setBrush(Qt.BrushStyle.NoBrush)
                p.drawRect(QRectF(0, 0, bw, bh))
            return
        pen = QPen(QColor(ACCENT), 1.5 * k, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.setBrush(QColor(52, 97, 240, 18))
        p.drawRect(QRectF(0, 0, bw, bh))
        p.setPen(QPen(QColor("white"), 2 * k))
        p.setBrush(QColor(ACCENT))
        p.drawEllipse(self.resize_handle())
        p.setBrush(QColor("#e5484d"))
        d = self.delete_handle()
        p.drawEllipse(d)
        c, s = d.center(), d.width() * 0.22
        p.drawLine(QPointF(c.x() - s, c.y() - s), QPointF(c.x() + s, c.y() + s))
        p.drawLine(QPointF(c.x() - s, c.y() + s), QPointF(c.x() + s, c.y() - s))

    def hoverEnterEvent(self, e):
        self.hover = True
        self.update()

    def hoverLeaveEvent(self, e):
        self.hover = False
        self.update()

    def hoverMoveEvent(self, e):
        if self.scene().views()[0].place_path:  # in modalità firma il cursore resta il timbro
            self.setCursor(stamp_cursor())
        elif self.isSelected() and self.resize_handle().contains(e.pos()):
            self.setCursor(Qt.CursorShape.SizeFDiagCursor)
        elif self.isSelected() and self.delete_handle().contains(e.pos()):
            self.setCursor(Qt.CursorShape.PointingHandCursor)
        else:
            self.setCursor(Qt.CursorShape.SizeAllCursor)

    def mousePressEvent(self, e):
        if self.isSelected() and self.delete_handle().contains(e.pos()):
            e.accept()
            QTimer.singleShot(0, self.remove_self)  # non distruggere l'oggetto mentre Qt gestisce il suo clic
            return
        if self.isSelected() and self.resize_handle().contains(e.pos()):
            self.mode = "resize"
            e.accept()
            return
        super().mousePressEvent(e)

    def remove_self(self):
        sc = self.scene()
        if sc:
            view = sc.views()[0]
            sc.removeItem(self)
            view.win.changed()

    def mouseMoveEvent(self, e):
        if self.mode == "resize":
            self.prepareGeometryChange()
            # la maniglia è sul bordo del blocco (che può essere più largo della firma per luogo/data)
            self.w = max(30.0, min(self.w * max(e.pos().x(), 1.0) / self.bw, 1200.0))
            self.update()
            return
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.mode = None
        super().mouseReleaseEvent(e)


class PdfView(QGraphicsView):
    def __init__(self, win):
        super().__init__()
        self.win = win
        self.setScene(QGraphicsScene(self))
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor("#e8ebf2"))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAcceptDrops(True)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self.pages = []
        self.drag_hover = False
        self.place_path = None  # firma in attesa di clic per essere posizionata
        self.ghost = None
        self.viewport().setMouseTracking(True)
        self._t = QTimer(self, singleShot=True, interval=60, timeout=self.render_visible)
        self.verticalScrollBar().valueChanged.connect(lambda: self._t.start())

    # --- documento
    def load(self, doc):
        # prima si svuotano i riferimenti: clear() fa scattare segnali (scroll -> stato) che leggerebbero pagine distrutte
        self.pages = []
        self.ghost = None
        self.scene().clear()
        y = PAGE_GAP
        maxw = max((p.rect.width for p in doc), default=600)
        for pno, page in enumerate(doc):
            it = PageItem(pno, page.rect.width, page.rect.height)
            it.setPos((maxw - page.rect.width) / 2, y)
            self.scene().addItem(it)
            self.pages.append(it)
            y += page.rect.height + PAGE_GAP
        self.scene().setSceneRect(QRectF(-PAGE_GAP, 0, maxw + 2 * PAGE_GAP, y))
        self.fit_width()
        self.verticalScrollBar().setValue(0)

    def render_visible(self):
        doc = self.win.doc
        if not doc:
            return
        area = self.mapToScene(self.viewport().rect()).boundingRect()
        z = min(max(self.transform().m11() * self.devicePixelRatioF(), 1.0), 4.0)
        for it in self.pages:
            want = min(z, (24e6 / (it.w * it.h)) ** 0.5)  # max ~24 Mpx per pagina (i grandi formati pesano molto)
            if it.sceneBoundingRect().intersects(area) and it.scale_done < want * 0.9:
                pix = doc[it.pno].get_pixmap(matrix=pymupdf.Matrix(want, want))
                it.pix, it.scale_done = QPixmap.fromImage(to_qimage(pix)), want
                it.update()
        # shortcut: le pagine già rese restano in memoria; per PDF di centinaia di pagine scaricare quelle lontane

    def signatures(self):
        return [i for i in self.scene().items() if isinstance(i, SignatureItem) and not i.ghost]

    def page_at(self, scene_pt):
        for it in self.pages:
            if it.sceneBoundingRect().adjusted(6, 6, -8, -10).contains(scene_pt):
                return it
        return None

    def current_page(self):
        c = self.mapToScene(self.viewport().rect().center())
        return min(self.pages, key=lambda it: abs(it.sceneBoundingRect().center().y() - c.y()), default=None)

    def show_ghost(self, path):
        self.hide_ghost()
        if path:
            self.ghost = SignatureItem(path, self.win.sig_width(), self.win.caption())
            self.ghost.ghost = True
            self.ghost.setOpacity(0.5)
            self.ghost.setFlags(QGraphicsItem.GraphicsItemFlag(0))
            self.ghost.setAcceptHoverEvents(False)
            self.ghost.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.ghost.setZValue(20)
            self.ghost.setVisible(False)
            self.scene().addItem(self.ghost)

    def hide_ghost(self):
        if self.ghost:
            self.scene().removeItem(self.ghost)
            self.ghost = None

    def mouseMoveEvent(self, e):
        if self.ghost:
            pt = self.mapToScene(e.position().toPoint())
            self.ghost.setPos(pt - QPointF(self.ghost.bw / 2, self.ghost.bh / 2))
            self.ghost.setVisible(bool(self.page_at(pt)))
        super().mouseMoveEvent(e)

    def leaveEvent(self, e):
        if self.ghost:
            self.ghost.setVisible(False)
        super().leaveEvent(e)

    def add_signature(self, path, scene_pt):
        if not self.page_at(scene_pt):
            pg = self.current_page()
            if not pg:
                return
            scene_pt = pg.sceneBoundingRect().center()
        it = SignatureItem(path, self.win.sig_width(), self.win.caption())
        it.setPos(scene_pt - QPointF(it.bw / 2, it.bh / 2))
        self.scene().addItem(it)
        self.keep_inside(it)
        self.scene().clearSelection()
        it.setSelected(True)
        self.win.changed()

    # --- zoom
    def set_zoom(self, z):
        z = min(max(z, 0.2), 6.0)
        self.setTransform(self.transform().fromScale(z, z))
        self.win.zoom_label.setText(f"{round(z * 100)}%")
        self._t.start()

    def zoom_by(self, f, under_mouse=False):
        self.auto_fit = False  # zoom scelto a mano: non riadattare più al ridimensionamento
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse if under_mouse
                                     else QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.set_zoom(self.transform().m11() * f)

    def fit_width(self):
        self.auto_fit = True
        if self.scene().sceneRect().width():
            self.set_zoom((self.viewport().width() - 30) / self.scene().sceneRect().width())

    def wheelEvent(self, e):
        if e.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.zoom_by(1.15 if e.angleDelta().y() > 0 else 1 / 1.15, under_mouse=True)
        else:
            super().wheelEvent(e)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        if getattr(self, "auto_fit", True) and self.pages:
            self.fit_width()
        self._t.start()

    # --- mouse / tastiera
    def mousePressEvent(self, e):
        if self.place_path and e.button() == Qt.MouseButton.LeftButton:
            pt = self.mapToScene(e.position().toPoint())
            if self.page_at(pt):  # fuori dal foglio il clic non fa nulla: resta in modalità firma
                self.add_signature(self.place_path, pt)
                self.win.end_place_mode()
            return
        if self.place_path and e.button() == Qt.MouseButton.RightButton:
            self.win.end_place_mode()
            return
        super().mousePressEvent(e)

    def keep_inside(self, it):
        """Riporta la firma dentro la pagina su cui si trova (altrimenti verrebbe salvata tagliata)."""
        box = QRectF(it.pos(), QSize(int(it.bw) + 1, int(it.bh) + 1).toSizeF())

        def overlap(p):
            i = p.sceneBoundingRect().intersected(box)
            return i.width() * i.height()
        pg = max(self.pages, key=overlap, default=None)  # la pagina che la firma copre di più
        if pg and overlap(pg) > 0:
            r = pg.sceneBoundingRect().adjusted(6, 6, -8, -10)  # area del foglio, senza ombra
            x = min(max(it.pos().x(), r.left()), max(r.left(), r.right() - it.bw))
            y = min(max(it.pos().y(), r.top()), max(r.top(), r.bottom() - it.bh))
            it.setPos(x, y)

    def mouseReleaseEvent(self, e):
        super().mouseReleaseEvent(e)
        for it in self.scene().selectedItems():
            if isinstance(it, SignatureItem):
                self.keep_inside(it)
                self.win.cfg["larghezza"] = round(it.w, 1)  # ricorda la larghezza per le prossime firme
        self.win.changed()

    def keyPressEvent(self, e):
        if e.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            for it in self.scene().selectedItems():
                self.scene().removeItem(it)
            self.win.changed()
        elif e.key() == Qt.Key.Key_Escape:
            self.win.end_place_mode()
            self.scene().clearSelection()
        elif e.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down) \
                and self.scene().selectedItems():
            step = 10 if e.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx = {Qt.Key.Key_Left: -step, Qt.Key.Key_Right: step}.get(e.key(), 0)
            dy = {Qt.Key.Key_Up: -step, Qt.Key.Key_Down: step}.get(e.key(), 0)
            for it in self.scene().selectedItems():
                it.moveBy(dx, dy)
                self.keep_inside(it)
            self.win.changed()
        else:
            super().keyPressEvent(e)

    # --- drag & drop: PDF dal file manager, firme dalla barra laterale
    @staticmethod
    def _pdf_from(mime):
        pdfs = PdfView._pdfs_from(mime)
        return pdfs[0] if pdfs else None

    @staticmethod
    def _pdfs_from(mime):
        return [u.toLocalFile() for u in mime.urls() if u.isLocalFile() and u.toLocalFile().lower().endswith(".pdf")]

    def dragEnterEvent(self, e):
        if self._pdf_from(e.mimeData()) or (e.mimeData().hasFormat(MIME_FIRMA) and self.win.doc):
            self.drag_hover = bool(self._pdf_from(e.mimeData()))
            self.viewport().update()
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        e.acceptProposedAction()

    def dragLeaveEvent(self, e):
        self.drag_hover = False
        self.viewport().update()

    def dropEvent(self, e):
        self.drag_hover = False
        self.viewport().update()
        if e.mimeData().hasFormat(MIME_FIRMA):
            path = bytes(e.mimeData().data(MIME_FIRMA)).decode()
            self.add_signature(path, self.mapToScene(e.position().toPoint()))
            self.setFocus()
        elif pdfs := self._pdfs_from(e.mimeData()):
            self.win.open_or_batch(pdfs)
        e.acceptProposedAction()

    def drawForeground(self, p, rect):
        if not self.drag_hover:
            return
        p.save()
        p.resetTransform()
        vr = QRectF(self.viewport().rect()).adjusted(40, 40, -40, -40)
        if self.drag_hover:
            p.fillRect(QRectF(self.viewport().rect()), QColor(52, 97, 240, 40))
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor(ACCENT if self.drag_hover else "#a9b3c9"), 2, Qt.PenStyle.DashLine))
        p.setBrush(QColor(255, 255, 255, 200 if self.drag_hover else 120))
        p.drawRoundedRect(vr, 18, 18)
        ic = QPixmap(os.path.join(APP_DIR, "icona.png"))
        if not ic.isNull():
            p.drawPixmap(int(vr.center().x() - 48), int(vr.center().y() - 110), 96, 96, ic)
        f = QFont(self.font())
        f.setPointSize(16)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#1f2a44"))
        t = "Rilascia per aprire il PDF"
        p.drawText(QRectF(vr.left(), vr.center().y() + 2, vr.width(), 30), Qt.AlignmentFlag.AlignCenter, t)
        f.setPointSize(11)
        f.setBold(False)
        p.setFont(f)
        p.setPen(QColor("#5b6680"))
        p.drawText(QRectF(vr.left(), vr.center().y() + 36, vr.width(), 24), Qt.AlignmentFlag.AlignCenter,
                   "le firme non salvate del documento attuale andranno perse" if self.win.dirty else "")
        p.restore()
