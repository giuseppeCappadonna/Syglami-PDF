"""Avvio dell'applicazione Qt."""
import os
import sys

from PyQt6.QtWidgets import QApplication, QMessageBox

from sigla.config import __version__, APP_ID, APP_NAME, cleanup_firme, load_config
from sigla.ui.finestra import MainWindow
from sigla.ui.tema import light_palette, STYLE, style_assets, style_extra

def main():
    QApplication.setDesktopFileName(APP_ID)  # raggruppa la finestra sotto l'icona del lanciatore
    try:
        cleanup_firme(load_config())
    except OSError:
        pass
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(__version__)
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setStyleSheet(STYLE + style_extra(style_assets()))
    def on_error(etype, value, tb):
        # PyQt6 chiude l'app su un'eccezione non gestita in uno slot: meglio un messaggio
        import traceback
        traceback.print_exception(etype, value, tb)
        QMessageBox.critical(None, APP_NAME, f"Si è verificato un errore imprevisto:\n{value}\n\n"
                             "L'operazione è stata interrotta; il PDF su disco non è stato modificato.")
    sys.excepthook = on_error
    w = MainWindow()
    w.show()
    if w.cfg.get("controlla_aggiornamenti", True):
        w.check_updates()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        w.open_pdf(sys.argv[1])
    sys.exit(app.exec())
