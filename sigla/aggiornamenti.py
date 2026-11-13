"""Controllo della versione pubblicata su GitHub. Senza Qt."""
import json
import re
import urllib.request

from sigla.config import __version__, INFO


def parse_versione(v):
    """'1.2.0' → (1, 2, 0). None se non è fatta di soli numeri: il testo arriva dalla rete, non ci si fida."""
    if isinstance(v, str) and re.fullmatch(r"\d{1,6}(\.\d{1,6}){0,3}", v):
        return tuple(int(x) for x in v.split("."))
    return None


def pagina_download():
    """Pagina del progetto su GitHub (da app.json), o "" se non è un indirizzo GitHub."""
    repo = INFO.get("autore", {}).get("github", "").rstrip("/")
    return repo if repo.startswith("https://github.com/") else ""


def nuova_versione(timeout=5):
    """La versione su GitHub (app.json del ramo main) se è più nuova di questa; None altrimenti o se non si sa.

    Legge soltanto: non invia dati. Senza rete o con una risposta strana non dice nulla.
    """
    repo = pagina_download()
    if not repo:
        return None
    url = repo.replace("https://github.com/", "https://raw.githubusercontent.com/", 1) + "/main/app.json"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            v = json.loads(r.read(65536)).get("versione")
    except (OSError, ValueError, AttributeError):  # rete assente, JSON non valido o che non è un oggetto
        return None
    return v if (parse_versione(v) or ()) > parse_versione(__version__) else None
