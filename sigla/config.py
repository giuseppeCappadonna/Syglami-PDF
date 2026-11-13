"""Configurazione utente, archivio firme e dati dell'app (app.json). Niente Qt."""
import datetime
import json
import os
import shutil
import sys
import tempfile
import uuid

import pymupdf

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # cartella del progetto (app.json, icone)


CONF_DIR = os.path.expanduser("~/.config/firma_pdf")


FIRME_DIR = os.path.join(CONF_DIR, "firme")


CONF_FILE = os.path.join(CONF_DIR, "config.json")


with open(os.path.join(APP_DIR, "app.json"), encoding="utf-8") as _f:
    INFO = json.load(_f)  # versioni, autore, link: unica fonte, mostrata nella finestra Info


APP_NAME = INFO["nome"]  # il nome dell'app si cambia solo in app.json
APP_ID = APP_NAME.lower().replace(" ", "-")  # nome del lanciatore (.desktop), del pacchetto e del comando
__version__ = INFO["versione"]  # SemVer: si cambia in app.json, poi CHANGELOG.md


def load_config():
    cfg = {"firme": [], "cartella": os.path.expanduser("~"),
           "mostra_data": False, "mostra_luogo": False, "luogo": ""}
    try:
        with open(CONF_FILE) as f:
            cfg.update(json.load(f))
    except FileNotFoundError:
        save_config(cfg)
    except (json.JSONDecodeError, OSError) as ex:
        print("Config illeggibile, uso i default:", ex, file=sys.stderr)
        try:  # non perdere l'elenco firme: il prossimo salvataggio sovrascriverebbe il file
            shutil.copyfile(CONF_FILE, CONF_FILE + ".danneggiato")
        except OSError:
            pass
    cfg["firme"] = [f for f in cfg["firme"] if isinstance(f, dict) and os.path.exists(f.get("file", ""))]
    return cfg


def cleanup_firme(cfg):
    """Cancella le copie interne di firme rimosse (fatto all'avvio: durante la sessione possono essere ancora sulla pagina)."""
    used = {os.path.abspath(f["file"]) for f in cfg["firme"]}
    if os.path.isdir(FIRME_DIR):
        for name in os.listdir(FIRME_DIR):
            p = os.path.abspath(os.path.join(FIRME_DIR, name))
            if p not in used:
                try:
                    os.remove(p)
                except OSError:
                    pass


def save_config(cfg):
    os.makedirs(CONF_DIR, exist_ok=True)
    tmp = CONF_FILE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(cfg, f, indent=2, ensure_ascii=False)
    os.replace(tmp, CONF_FILE)


def new_firma_path(ext):
    """Percorso nuovo e univoco per una copia interna di firma: chi crea firme non conosce le cartelle della config."""
    os.makedirs(FIRME_DIR, exist_ok=True)
    return os.path.join(FIRME_DIR, uuid.uuid4().hex + ext)


def add_firma_svg(cfg, nome, svg):
    """Salva una firma SVG generata o disegnata, la aggiunge all'elenco e salva la config."""
    dst = new_firma_path(".svg")
    with open(dst, "w") as f:
        f.write(svg)
    cfg["firme"].append({"nome": nome, "file": dst})
    save_config(cfg)


def import_firma(cfg, src, nome, vettorizza):
    """Copia (o vettorizza) la firma nella cartella dell'app, così non dipende dal file originale."""
    ext = os.path.splitext(src)[1].lower()
    if ext != ".svg" and vettorizza:
        from vettorizza import png_to_svg
        dst = png_to_svg(src, new_firma_path(".svg"))
    else:
        dst = new_firma_path(ext)
        shutil.copyfile(src, dst)
    pymupdf.open(dst).close()  # verifica che sia leggibile
    cfg["firme"].append({"nome": nome, "file": dst})


def default_firma(cfg):
    """File della firma predefinita (o la prima), None se non ce ne sono."""
    files = [f["file"] for f in cfg["firme"]]
    return cfg.get("predefinita") if cfg.get("predefinita") in files else (files[0] if files else None)


MESI = ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre",
        "ottobre", "novembre", "dicembre")


FORMATI_DATA = (("num", "11/11/2026"), ("esteso", "11 novembre 2026"), ("punti", "11.11.2026"), ("iso", "2026-11-11"))


SALVATAGGI = (("chiedi", "Chiedi ogni volta"), ("copia", "Crea sempre una copia firmata"),
              ("sovrascrivi", "Sovrascrivi sempre l'originale"))


SUFFISSO = "_firmato"


def fmt_data(d, fmt="num"):
    return {"esteso": f"{d.day} {MESI[d.month - 1]} {d.year}", "punti": f"{d:%d.%m.%Y}",
            "iso": d.isoformat()}.get(fmt, f"{d:%d/%m/%Y}")


def copy_suffix(cfg):
    """Suffisso del nome delle copie firmate; {data} diventa la data di oggi (AAAA-MM-GG)."""
    s = cfg.get("suffisso", SUFFISSO).replace("{data}", datetime.date.today().isoformat())
    s = "".join(c for c in s if c not in '/\\\0:*?"<>|').strip()  # niente separatori o caratteri vietati
    return s or SUFFISSO


ZIP_MANIFEST = "sigla-firme.json"


ZIP_MAX = 10 * 1024 * 1024  # una firma non pesa più di qualche centinaio di KB


def export_firme(cfg, dst):
    """Salva tutte le firme in uno .zip (immagini + elenco con nomi e predefinita)."""
    import zipfile
    man = {"app": APP_NAME, "formato": 1, "firme": []}
    fd, tmp = tempfile.mkstemp(suffix=".zip", dir=os.path.dirname(os.path.abspath(dst)))
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for i, f in enumerate(cfg["firme"]):
                name = f"firma-{i + 1:02d}{os.path.splitext(f['file'])[1].lower()}"
                z.write(f["file"], name)
                man["firme"].append({"nome": f["nome"], "file": name, "predefinita": f["file"] == default_firma(cfg)})
            z.writestr(ZIP_MANIFEST, json.dumps(man, ensure_ascii=False, indent=2))
        os.replace(tmp, dst)
    except BaseException:
        os.remove(tmp)
        raise
    return len(man["firme"])


def import_firme(cfg, src):
    """Aggiunge le firme di uno .zip esportato dall'app. Il file può venire da chiunque: tutto viene controllato.
    Restituisce (aggiunte, già presenti)."""
    import hashlib
    import zipfile

    def digest(data):
        return hashlib.sha256(data).hexdigest()
    have = set()
    for f in cfg["firme"]:
        with open(f["file"], "rb") as fh:
            have.add(digest(fh.read()))
    added = dup = 0
    with zipfile.ZipFile(src) as z:
        try:
            man = json.loads(z.read(ZIP_MANIFEST))
        except KeyError:
            raise ValueError(f"il file non è un'esportazione di firme di {APP_NAME}")
        for e in man.get("firme", []):
            name = os.path.basename(str(e.get("file", "")))  # mai percorsi: solo file nella radice dello zip
            ext = os.path.splitext(name)[1].lower()
            if ext not in (".svg", ".png", ".jpg", ".jpeg") or name not in z.namelist() or z.getinfo(name).file_size > ZIP_MAX:
                continue
            data = z.read(name)
            if digest(data) in have:
                dup += 1
                continue
            dst = new_firma_path(ext)
            with open(dst, "wb") as fh:
                fh.write(data)
            try:
                pymupdf.open(dst).close()  # deve essere un'immagine leggibile
            except Exception:
                os.remove(dst)
                continue
            have.add(digest(data))
            cfg["firme"].append({"nome": str(e.get("nome") or "Firma importata")[:80], "file": dst})
            added += 1
    return added, dup
