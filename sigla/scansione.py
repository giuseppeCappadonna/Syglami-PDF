"""Effetto «stampato, firmato e scansionato»: ogni pagina diventa un'immagine in grigio con difetti casuali e lievi. Niente Qt."""
import numpy as np
import pymupdf

DPI = 150  # come una scansione d'ufficio: leggibile, ~200 KB a pagina


def _strisce(rng, w, h):
    """Aloni verticali grigi che partono dal bordo alto o basso e svaniscono nel margine (mai sul testo centrale)."""
    ombra = np.zeros((h, w), np.float32)
    x = np.arange(w, dtype=np.float32)
    d = np.arange(h, dtype=np.float32)
    for _ in range(rng.integers(1, 4)):
        cx = rng.uniform(0, w)
        prof = np.zeros(w, np.float32)
        for _ in range(rng.integers(2, 7)):
            c, s = cx + rng.normal(0, 0.04 * w), rng.uniform(1, 0.012 * w)
            prof += rng.uniform(0.05, 0.3) * np.exp(-((x - c) / s) ** 2)
        dist = d if rng.random() < 0.3 else d[::-1]  # più spesso dal basso
        sfuma = np.clip(1 - dist / (rng.uniform(0.04, 0.11) * h), 0, 1) ** 1.5
        ombra += np.clip(prof, 0, 0.4)[None, :] * sfuma[:, None]
    return np.clip(ombra, 0, 0.45)


def pagina_scansionata(page, rng, dpi=DPI):
    """JPEG in grigio della pagina come uscirebbe da uno scanner; ogni difetto è estratto da `rng`."""
    z = dpi / 72
    w, h = round(page.rect.width * z), round(page.rect.height * z)
    # foglio appoggiato un po' storto: la rotazione la fa MuPDF, fuori dal foglio resta bianco
    pix = page.get_pixmap(matrix=pymupdf.Matrix(z, z).prerotate(rng.uniform(-0.5, 0.5)),
                          colorspace=pymupdf.csGRAY, alpha=False)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
    w, h = min(w, pix.width), min(h, pix.height)
    x0 = int(np.clip((pix.width - w) // 2 + rng.integers(-4, 5), 0, pix.width - w))
    y0 = int(np.clip((pix.height - h) // 2 + rng.integers(-4, 5), 0, pix.height - h))
    a = a[y0:y0 + h, x0:x0 + w].astype(np.float32) / 255

    p = np.pad(a, 1, mode="edge")  # ottica: bordi appena morbidi
    a = (4 * a + p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:]) / 8
    lo, hi = rng.uniform(0.22, 0.30), rng.uniform(0.78, 0.86)  # contrasto duro: inchiostro pieno, grigi chiari persi
    a = np.clip((a - lo) / (hi - lo), 0, 1) ** 1.3

    gx, gy = rng.uniform(-0.02, 0.02, 2)  # luce della lampada non uniforme
    carta = (rng.uniform(0.965, 0.995) + gx * (np.linspace(-0.5, 0.5, w, dtype=np.float32))[None, :]
             + gy * (np.linspace(-0.5, 0.5, h, dtype=np.float32))[:, None])
    nero = rng.uniform(0.04, 0.10)
    a = nero + a * (carta - nero)
    a *= 1 - _strisce(rng, w, h)
    a += rng.normal(0, 0.012, a.shape).astype(np.float32)  # grana del sensore
    n = rng.integers(3, 12)  # granelli di polvere sul vetro
    ys, xs = rng.integers(0, h - 1, n), rng.integers(0, w - 1, n)
    k = rng.uniform(0.3, 0.8, n)
    a[ys, xs] *= k
    a[ys + rng.integers(0, 2, n), xs + rng.integers(0, 2, n)] *= k

    out = (np.clip(a, 0, 1) * 255).astype(np.uint8)
    return pymupdf.Pixmap(pymupdf.csGRAY, w, h, out.tobytes(), False).tobytes("jpeg", jpg_quality=int(rng.integers(72, 88)))


def scansiona(doc, seme=None, dpi=DPI):
    """Sostituisce sul posto ogni pagina con la sua «scansione» (stesso formato; testo e link non restano).
    Sul posto, così un PDF protetto resta protetto al salvataggio. `seme` serve solo ai test: di norma è casuale."""
    rng = np.random.default_rng(seme)
    for i in range(len(doc)):
        r = doc[i].rect  # formato visualizzato: la rotazione della pagina finisce nell'immagine
        jpg = pagina_scansionata(doc[i], rng, dpi)
        doc.delete_page(i)
        p = doc.new_page(i, width=r.width, height=r.height)
        p.insert_image(p.rect, stream=jpg)
