"""Operazioni sui PDF senza interfaccia: blocco firma, scrittura atomica, posizionamento automatico. Niente Qt."""
import os
import shutil
import tempfile

import pymupdf

from sigla.config import SUFFISSO

CAP_K = 0.065         # dimensione testo luogo/data rispetto alla larghezza della firma


CAP_COLOR = (0.12, 0.13, 0.18)


def block_geom(w, ratio, caption):
    """Blocco = didascalia (luogo, data) sopra la firma. Restituisce fs, altezza didascalia, larghezza, altezza."""
    if not caption:
        return 0, 0, w, w * ratio
    fs = w * CAP_K
    ch = fs * 2.4  # riga + spazio prima della firma
    return fs, ch, max(w, pymupdf.get_text_length(caption, "helv", fs)), ch + w * ratio


def stamp_doc(path, caption, w):
    """PDF di una pagina con didascalia + firma, tutto vettoriale: si incolla poi in un colpo solo."""
    with pymupdf.open(path) as src:
        ratio = src[0].rect.height / src[0].rect.width
        sig = pymupdf.open("pdf", src.convert_to_pdf()) if path.lower().endswith(".svg") else None
    fs, ch, bw, bh = block_geom(w, ratio, caption)
    d = pymupdf.open()
    p = d.new_page(width=bw, height=bh)
    if caption:
        p.insert_text((0, fs * 1.05), caption, fontname="helv", fontsize=fs, color=CAP_COLOR)
    r = pymupdf.Rect(0, ch, w, bh)
    if sig:
        p.show_pdf_page(r, sig, 0)
    else:
        p.insert_image(r, filename=path)
    return d


def stampa_firma(page, rect, path, caption, w):
    """Disegna firma (+ didascalia) nel rettangolo `rect` (coordinate visualizzate della pagina)."""
    page.show_pdf_page(rect * page.derotation_matrix, stamp_doc(path, caption, w), 0, rotate=page.rotation)


def write_signed(doc, placed, target, password=None, scan=False):
    """Applica le firme a una copia del documento e la scrive su `target` in modo atomico.
    I PDF protetti restano protetti: si riparte dal file originale con la sua password.
    `scan`: le pagine escono come immagini, con l'aspetto di un foglio stampato e scansionato."""
    if password is not None:
        out = pymupdf.open(doc.name)
        if not out.authenticate(password):
            raise ValueError("password non più valida per il file su disco")
    else:
        out = pymupdf.open("pdf", doc.tobytes())  # copia: il documento aperto resta intatto se qualcosa fallisce
    for pno, rect, path, caption, w in placed:
        stampa_firma(out[pno], rect, path, caption, w)
    if scan:
        from sigla.scansione import scansiona  # numpy si carica solo se serve
        scansiona(out)
    fd, tmp = tempfile.mkstemp(suffix=".pdf", dir=os.path.dirname(os.path.abspath(target)))
    os.close(fd)
    try:
        out.save(tmp, garbage=3, deflate=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
        out.close()
        if os.path.exists(target):
            shutil.copymode(target, tmp)
        os.replace(tmp, target)
    except BaseException:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


PAROLE_FIRMA = ("firma", "il dichiarante", "il richiedente", "letto e sottoscritto", "letto, confermato e sottoscritto",
                "in fede", "il legale rappresentante", "per accettazione", "il cliente", "il contraente",
                "l'interessato", "il sottoscritto", "signature")


POSIZIONI = (("basso-destra", "In basso a destra"), ("basso-sinistra", "In basso a sinistra"),
             ("margine-destro", "Margine destro, a metà pagina"), ("alto-destra", "In alto a destra"))


_ratio = {}


def sig_ratio(path):
    if path not in _ratio:
        with pymupdf.open(path) as d:
            _ratio[path] = d[0].rect.height / d[0].rect.width
    return _ratio[path]


def find_sign_spots(doc):
    """Diciture di firma nel testo: [(pagina, rettangolo visualizzato, riga)], in ordine di lettura."""
    spots = []
    for page in doc:
        seen = []
        for kw in PAROLE_FIRMA:
            for r in page.search_for(kw):
                if any(r.intersects(x) for x in seen):
                    continue
                seen.append(r)
                line = " ".join(page.get_text("text", clip=pymupdf.Rect(-1e4, r.y0 - 1, 1e4, r.y1 + 1)).split())
                if len(line) <= 70:  # le diciture di firma sono righe brevi; le frasi lunghe sono testo normale
                    spots.append((page.number, r * page.rotation_matrix, line or kw))
    return sorted(spots, key=lambda s: (s[0], s[1].y0, s[1].x0))


def spot_rect(page_rect, hit, bw, bh):
    """Blocco firma sotto la dicitura (a destra se sotto non c'è spazio), dentro la pagina."""
    x, y = hit.x0 + hit.width / 2 - bw / 2, hit.y1 + 6
    if y + bh > page_rect.y1 - 8:
        x, y = hit.x1 + 10, hit.y0 + hit.height / 2 - bh / 2
    x = min(max(x, 8), page_rect.width - bw - 8)
    y = min(max(y, 8), page_rect.height - bh - 8)
    return pymupdf.Rect(x, y, x + bw, y + bh)


def corner_rect(page_rect, bw, bh, pos="basso-destra", margin=48):
    W, H = page_rect.width, page_rect.height
    x, y = {"basso-destra": (W - margin - bw, H - margin - bh), "basso-sinistra": (margin, H - margin - bh),
            "alto-destra": (W - margin - bw, margin), "margine-destro": (W - margin / 2 - bw, H / 2 - bh / 2)}[pos]
    return pymupdf.Rect(x, y, x + bw, y + bh)


def placement_at(doc, pno, hit, path, caption, w):
    _, _, bw, bh = block_geom(w, sig_ratio(path), caption)
    rect = spot_rect(doc[pno].rect, hit, bw, bh) if hit else corner_rect(doc[pno].rect, bw, bh)
    return (pno, rect, path, caption, w)


def auto_placements(doc, path, caption, w, mode="auto"):
    """Una firma: sotto l'ultima dicitura di firma trovata, altrimenti in fondo all'ultima pagina.
    Restituisce (posizionamenti, descrizione per l'utente)."""
    spots = find_sign_spots(doc) if mode == "auto" else []
    if spots:
        pno, hit, line = spots[-1]  # l'ultima: di solito lo spazio firma è in fondo al documento
        return [placement_at(doc, pno, hit, path, caption, w)], f"pag. {pno + 1}, sotto «{line}»"
    return [placement_at(doc, len(doc) - 1, None, path, caption, w)], "in fondo all'ultima pagina"


def sigla_placements(doc, path, w, pos="basso-destra", skip_last=False):
    bh = w * sig_ratio(path)
    return [(p.number, corner_rect(p.rect, w, bh, pos, margin=24), path, "", w)
            for p in doc if not (skip_last and p.number == len(doc) - 1)]


def output_path(src, suffix=SUFFISSO):
    """nome_firmato.pdf accanto all'originale, senza mai sovrascrivere un file esistente."""
    base = os.path.splitext(src)[0] + suffix
    dst, n = base + ".pdf", 2
    while os.path.exists(dst):
        dst, n = f"{base} ({n}).pdf", n + 1
    return dst


def sign_file(src, dst, path, caption, w, mode="auto", ref=None, scan=False):
    """Firma `src` e scrive `dst`. mode: auto | ultima | come (usa i posizionamenti `ref`)."""
    with pymupdf.open(src) as doc:
        if not doc.is_pdf or not len(doc):
            raise ValueError("non è un PDF valido")
        if doc.needs_pass:
            raise ValueError("PDF protetto da password")
        if mode == "come":
            placed, where = [p for p in ref if p[0] < len(doc)], "come nel documento di riferimento"
            if not placed:
                raise ValueError("il documento ha meno pagine del riferimento")
        else:
            placed, where = auto_placements(doc, path, caption, w, mode)
        write_signed(doc, placed, dst, scan=scan)
    return where
