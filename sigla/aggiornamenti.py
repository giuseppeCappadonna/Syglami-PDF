"""Aggiornamenti da GitHub: controllo dell'ultima release e, per chi usa il pacchetto .deb, download verificato e
installazione. Senza Qt. Tutto ciò che arriva dalla rete è input non fidato."""
import hashlib
import json
import os
import re
import subprocess
import tempfile
import urllib.request

from sigla.config import __version__, APP_DIR, APP_ID, INFO

MAX_DEB = 500 << 20  # nessun pacchetto vero è così grande: oltre, la risposta è sospetta


def parse_versione(v):
    """'1.2.0' → (1, 2, 0). None se non è fatta di soli numeri: il testo arriva dalla rete, non ci si fida."""
    if isinstance(v, str) and re.fullmatch(r"\d{1,6}(\.\d{1,6}){0,3}", v):
        return tuple(int(x) for x in v.split("."))
    return None


def repo():
    """Indirizzo del progetto su GitHub (da app.json), o "" se non è un indirizzo GitHub."""
    r = INFO.get("autore", {}).get("github", "").rstrip("/")
    return r if r.startswith("https://github.com/") else ""


def pagina_download():
    """Pagina dell'ultima release, dove c'è il pacchetto da scaricare."""
    return repo() + "/releases/latest" if repo() else ""


def da_pacchetto():
    """True se l'app gira dal pacchetto .deb: solo così si aggiorna da sola.
    Una cartella sorgente (install.sh) non si tocca: potrebbe contenere modifiche di chi ci lavora."""
    return APP_DIR == f"/opt/{APP_ID}"


def architettura():
    try:
        return subprocess.run(["dpkg", "--print-architecture"], capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def nuova_versione(timeout=5):
    """L'ultima release su GitHub, se è più nuova di questa: {"versione", "pagina", "deb"}; None altrimenti o se non si sa.
    "deb" = {"url", "size", "sha256"} del pacchetto per questo computer, o None se la release non lo contiene.
    Legge soltanto: non invia dati."""
    r = repo()
    if not r:
        return None
    api = r.replace("https://github.com/", "https://api.github.com/repos/", 1) + "/releases/latest"
    try:
        with urllib.request.urlopen(api, timeout=timeout) as f:
            rel = json.loads(f.read(1 << 20))
        tag = rel["tag_name"]
        v = tag.removeprefix("v")
        assets = rel.get("assets") or []
    except (OSError, ValueError, KeyError, TypeError, AttributeError):  # rete assente o risposta strana
        return None
    if not (parse_versione(v) or ()) > parse_versione(__version__):
        return None
    nome = f"{APP_ID}_{v}_{architettura()}.deb"
    deb = None
    for a in assets if isinstance(assets, list) else ():
        if not isinstance(a, dict) or a.get("name") != nome:
            continue
        size, sha = a.get("size"), str(a.get("digest") or "").removeprefix("sha256:")
        # solo un file della release di questo progetto: niente indirizzi altrove
        if a.get("browser_download_url") == f"{r}/releases/download/{tag}/{nome}" \
                and isinstance(size, int) and 0 < size <= MAX_DEB:
            deb = {"url": a["browser_download_url"], "size": size,
                   "sha256": sha if re.fullmatch(r"[0-9a-f]{64}", sha) else None}
    return {"versione": v, "pagina": pagina_download(), "deb": deb}


def controlla_pacchetto(path, versione):
    """ValueError se il file non è il pacchetto di questa app nella versione attesa."""
    try:
        out = subprocess.run(["dpkg-deb", "-f", path, "Package", "Version"], capture_output=True, text=True,
                             timeout=30).stdout.split()
    except (OSError, subprocess.SubprocessError) as ex:
        raise ValueError(f"pacchetto illeggibile: {ex}") from ex
    if out != ["Package:", APP_ID, "Version:", versione]:
        raise ValueError("il file scaricato non è il pacchetto atteso")


def scarica(deb, versione, progresso=None, timeout=30):
    """Scarica il pacchetto in un file temporaneo e lo verifica (dimensione, SHA-256 dichiarato da GitHub, nome e
    versione). `progresso(byte)` che restituisce False annulla. Restituisce il percorso; il chiamante lo cancella."""
    fd, path = tempfile.mkstemp(prefix=f"{APP_ID}-", suffix=".deb")
    try:
        h, n = hashlib.sha256(), 0
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(deb["url"], timeout=timeout) as f:
            while blocco := f.read(1 << 16):
                n += len(blocco)
                if n > deb["size"]:
                    raise ValueError("il pacchetto è più grande del previsto")
                h.update(blocco)
                out.write(blocco)
                if progresso and progresso(n) is False:
                    raise InterruptedError("download annullato")
        if n != deb["size"]:
            raise ValueError("download incompleto")
        if deb["sha256"] and h.hexdigest() != deb["sha256"]:
            raise ValueError("il pacchetto non corrisponde a quello pubblicato (SHA-256 diverso)")
        controlla_pacchetto(path, versione)
        os.chmod(path, 0o644)  # apt lo legge con un suo utente senza privilegi
        return path
    except BaseException:
        os.remove(path)
        raise


def installa(path):
    """Installa il pacchetto da amministratore: pkexec chiede la password in una finestra di sistema.
    Restituisce "" se è riuscito, altrimenti il motivo."""
    try:
        r = subprocess.run(["pkexec", "apt-get", "install", "-y", path], capture_output=True, text=True)
    except OSError as ex:
        return str(ex)
    if r.returncode in (126, 127):
        return "password non inserita o autorizzazione negata"
    return "" if r.returncode == 0 else (r.stderr.strip().splitlines() or ["apt-get non è riuscito"])[-1]
