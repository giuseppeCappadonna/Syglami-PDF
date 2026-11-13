"""Generatore di firme vettoriali "scritte a mano".

Lo scheletro delle lettere viene dai tracciati a linea singola Hershey (dati da plotter);
tutto il resto simula una mano diversa per ogni seme: inclinazione, ritmo, compressione,
linea di base, tremolio, pressione della penna, degrado delle lettere finali, svolazzo.
Lo stile (STILI) sceglie il modo di firmare; dentro lo stile ogni seme resta una mano diversa.
"""
import math
import random

import numpy as np
from HersheyFonts import HersheyFonts

STILI = (("corsivo", "Corsivo"), ("calligrafico", "Calligrafico"), ("stampatello", "Stampatello"),
         ("professionale", "Professionale"), ("elegante", "Elegante"), ("frettolosa", "Frettolosa"),
         ("sigla", "Sigla"))
BASELINE = 9  # metrica Hershey: rigo a y=9 (y cresce verso il basso)
_fonts = {}


def _font(name):
    if name not in _fonts:
        _fonts[name] = HersheyFonts()
        _fonts[name].load_default_font(name)
    return _fonts[name]


WIDTH_LEVELS = 14  # livelli di spessore: ogni livello è un <path> con tratto rotondo

# Lettere ridisegnate (font cursive, x dal bordo sinistro del glifo originale).
# G: quella Hershey è la G americana (sembra una S); questa è la G della scuola italiana:
# occhiello aperto come una C, poi asta che scende sotto il rigo e risale verso la lettera dopo.
GLIFI = {"G": [[(16, -6), (18, -7), (18, -10), (16, -12), (12, -12), (8, -11), (5, -8), (3, -4), (2, 0), (2, 4),
                (3, 7), (5, 9), (8, 9), (11, 8), (14, 5), (16, 1), (17, -2), (17, 3), (16, 9), (15, 12), (13, 15),
                (10, 16), (8, 15), (7, 13), (8, 11), (11, 10), (15, 9), (19, 8)]]}


def _glyph_strokes(text, font="cursive"):
    """Tratti per ogni carattere (con la sua posizione orizzontale originale)."""
    out, prev = [], 0
    for i in range(len(text)):
        st = [np.array(s, float) for s in _font(font).strokes_for_text(text[:i + 1])]
        new = st[prev:]
        if font == "cursive" and text[i] in GLIFI and new:
            dx = np.vstack(new)[:, 0].min()
            new = [np.array(g, float) + [dx, 0] for g in GLIFI[text[i]]]
        out.append((text[i], new))
        prev = len(st)
    return out


def _resample(p, step):
    seg = np.linalg.norm(np.diff(p, axis=0), axis=1)
    s = np.concatenate([[0], np.cumsum(seg)])
    if s[-1] < 1e-6:
        return p[:1].repeat(2, axis=0)
    t = np.linspace(0, s[-1], max(int(s[-1] / step), 2) + 1)
    return np.column_stack([np.interp(t, s, p[:, 0]), np.interp(t, s, p[:, 1])])


def _smooth(p, k):
    if len(p) < 3 or k < 2:
        return p
    ker = np.ones(k) / k
    pad = np.pad(p, ((k, k), (0, 0)), mode="edge")
    return np.column_stack([np.convolve(pad[:, i], ker, "same")[k:-k] for i in range(2)])


def _noise(rng, n_terms=4, amp=1.0, wavelength=(6, 30)):
    """Rumore morbido 1D: somma di sinusoidi a frequenza bassa (tremolio della mano)."""
    terms = [(rng.uniform(*wavelength), rng.uniform(0, 2 * math.pi), rng.uniform(0.3, 1)) for _ in range(n_terms)]
    tot = sum(a for _, _, a in terms)
    return lambda s: amp * sum(a * np.sin(2 * math.pi * s / w + ph) for w, ph, a in terms) / tot


def generate(text, seed, leggibilita=0.7, inclinazione=0.5, spessore=1.0, colore="#1b2f7a",
             stile="corsivo", iniziale=False, sottolineato=True):
    """Restituisce l'SVG (stringa) di una firma. Stesso seme = stessa mano.

    stile: una chiave di STILI. iniziale: "Mario Rossi" -> "M. Rossi".
    sottolineato=False toglie la riga/lo svolazzo sotto il nome; il resto della mano non cambia.
    """
    words = text.split()
    if not words:
        raise ValueError("Testo vuoto")
    if stile not in dict(STILI):
        raise ValueError(f"Stile sconosciuto: {stile}")
    if iniziale:
        words = [w[0].upper() + "." for w in words[:-1]] + words[-1:]
    if stile == "sigla":
        words = ["".join(w[0].upper() for w in words)]
    text = " ".join(words)
    stampatello = stile == "stampatello"
    xh = 14 if stampatello else 9  # altezza delle minuscole nel font
    rng = random.Random(seed)

    # --- carattere della mano (dipende solo dal seme)
    slant = 0.12 + 0.45 * inclinazione + rng.uniform(-0.08, 0.08)
    slant_n = _noise(rng, 2, rng.uniform(0.01, 0.06), (30, 90))  # l'inclinazione oscilla lungo la firma
    xcomp = rng.uniform(0.72, 1.05)              # compressione orizzontale
    cap_k = rng.uniform(1.15, 1.75)              # enfasi delle maiuscole
    gap_k = rng.uniform(0.35, 0.8)               # spazio tra le parole
    tilt = math.radians(rng.uniform(-2, 6))      # le firme tendono a salire
    base = _noise(rng, 3, rng.uniform(0.5, 2.5), (25, 80))
    tremor = _noise(rng, 4, rng.uniform(0.03, 0.12), (8, 25))
    tremor2 = _noise(rng, 4, rng.uniform(0.03, 0.12), (8, 25))
    yscale = rng.uniform(0.8, 1.25)              # altezza delle lettere minuscole
    asta_k = rng.uniform(0.85, 1.45)             # aste e code (l, d, p, g) più o meno lunghe
    shrink = rng.uniform(0, 0.25)                # la scrittura rimpicciolisce verso la fine
    warp = _noise(rng, 2, rng.uniform(0.4, 1.4), (14, 40))  # aste curve: forma delle lettere propria della mano
    dot_dx, dot_up = rng.uniform(-1, 1.5), rng.uniform(-1.5, 1)  # il puntino arriva in ritardo, spostato
    dot_len, dot_ang = rng.uniform(0.8, 2.5), rng.uniform(-0.6, 0.9)
    press = _noise(rng, 4, 1.0, (8, 35))
    contrasto = rng.uniform(0.1, 0.8)            # biro (tratto uniforme) ... stilografica (pieni e filetti)
    t_in, t_out = rng.uniform(1, 2.5), rng.uniform(2, 5)  # attacco e stacco della penna
    w0 = rng.uniform(1.3, 2.1) * spessore
    smooth_k = round(3 + (1 - leggibilita) * 6 + rng.uniform(0, 4))  # mano veloce = angoli tagliati
    degrado = (1 - leggibilita) * rng.uniform(0.7, 1.0)
    base_k = 1.0

    # --- lo stile sposta il carattere della mano, senza toglierle la sua variabilità
    if stile == "calligrafico":      # pennino: pieni e filetti marcati, aste lunghe, tutto leggibile
        contrasto, asta_k, degrado = rng.uniform(0.85, 1), max(asta_k, 1.25), 0
        slant += 0.08
        shrink *= 0.4
    elif stampatello:                # lettere staccate e quasi dritte
        slant *= 0.35
        cap_k, contrasto = min(cap_k, 1.2), min(contrasto, 0.35)
    elif stile == "professionale":   # ordinata: rigo fermo, proporzioni regolari, biro, riga sotto
        cap_k, yscale, xcomp = rng.uniform(1.3, 1.5), rng.uniform(0.9, 1.05), rng.uniform(0.8, 0.95)
        contrasto, tilt, degrado = rng.uniform(0.15, 0.4), math.radians(rng.uniform(0, 3)), 0
        shrink, base_k = min(shrink, 0.08), 0.3
    elif stile == "elegante":        # maiuscole ampie e svolazzo
        cap_k, contrasto = rng.uniform(1.8, 2.2), max(contrasto, 0.6)
        slant += 0.05
        degrado *= 0.5
    elif stile == "frettolosa":      # resta leggibile solo l'inizio di ogni parola
        smooth_k += 3
        tilt += math.radians(2)
    elif stile == "sigla":           # solo iniziali, grandi e accavallate
        cap_k = rng.uniform(1.6, 2.1)

    # --- lettere: posizione, scala e forma variano un po' a ogni lettera, come a mano libera
    strokes, x_shift, letters = [], 0.0, _glyph_strokes(text, "futural" if stampatello else "cursive")
    n = max(sum(1 for c, _ in letters if c != " "), 1)
    k = wi = wn = 0  # lettera nella firma, lettera nella parola, parola
    word_start = True
    for ch, sts in letters:
        if ch == " " or not sts:
            if ch == " ":
                x_shift -= 16 * (1 - gap_k)
                word_start = True
                wi, wn = 0, wn + 1
            continue
        f = k / max(n - 1, 1)  # posizione relativa nella firma
        crng = random.Random(f"{seed}|{ch}")  # ogni mano fa la stessa lettera sempre allo stesso modo
        wk, hk, shear = crng.uniform(0.82, 1.22), crng.uniform(0.9, 1.12), crng.uniform(-0.08, 0.08)
        cap = ch.isupper() and (word_start or stile == "sigla")
        sc = rng.uniform(0.94, 1.06) * (cap_k if cap else 1 - shrink * f)
        dy = rng.uniform(-0.8, 0.8)
        flat = min(degrado * (f ** 1.3) * 1.4, 0.75) if not ch.isupper() else 0
        allg = np.vstack(sts)
        cx, gw = allg[:, 0].min(), np.ptp(allg[:, 0])
        hx = sc * wk
        if stile == "frettolosa" and wi:  # dopo l'iniziale la parola si schiaccia in un'onda sempre più piatta
            fw = wi / max(len(words[wn]) - 1, 1)
            flat = min(0.4 + 0.55 * fw, 0.93)
            hx *= 1 - 0.45 * fw
        for s in sts:
            dot = ch in "ij" and np.ptp(s, axis=0).max() <= 2
            if dot and stile == "frettolosa":
                continue
            if ch == ".":
                s = s + [0, 3]  # nel font il punto galleggia sopra il rigo
            if dot:  # il puntino diventa un trattino veloce
                c = s.mean(axis=0) + [dot_dx, -dot_up]
                s = np.array([c, c + [dot_len * math.cos(dot_ang), -dot_len * math.sin(dot_ang)]])
            h = BASELINE - s[:, 1]  # altezza sopra il rigo
            # corpo centrale scalato con yscale, aste e code con asta_k
            h = np.where(dot, h + xh * (yscale - 1), np.where(h > xh, xh * yscale + (h - xh) * asta_k, np.where(h < 0, h * asta_k, h * yscale)))
            h = h * sc * hk
            if flat and not dot:  # le ultime lettere si appiattiscono verso la linea mediana
                mid = xh * yscale * sc / 2
                h = mid + (h - mid) * (1 - flat)
            x = cx + (s[:, 0] - cx) * hx + warp(h) + shear * h + x_shift
            strokes.append(np.column_stack([x * xcomp, BASELINE - h + dy]))
        x_shift += (hx - 1) * gw + rng.uniform(-1.2, 0.6) - (rng.uniform(2, 6) if stile == "sigla" else 0)
        word_start = False
        k += 1
        wi += 1

    # --- unisci i tratti che si toccano: la penna non si stacca tra lettere collegate
    merged = []
    for s in strokes:
        if merged and np.linalg.norm(merged[-1][-1] - s[0]) < 1.6:
            merged[-1] = np.vstack([merged[-1], s[1:]])
        else:
            merged.append(s)

    # --- svolazzo finale (o niente), diverso per ogni mano
    allp = np.vstack(merged)
    x0, x1 = allp[:, 0].min(), allp[:, 0].max()
    y_base = BASELINE
    kind = {"sigla": 0, "elegante": 0, "frettolosa": 0.6, "professionale": 2}.get(stile, rng.random())
    if stampatello:  # lettere staccate: niente svolazzo legato all'ultima lettera, al più una riga
        kind = 2 if kind < 0.45 else 1
    if kind < 0.45:  # sottolineatura che torna indietro sotto il nome
        e = merged[-1][-1]
        t = np.linspace(0, 1, 60)[:, None]
        P = [e, e + [rng.uniform(4, 10), rng.uniform(4, 9)],
             [x0 + (x1 - x0) * rng.uniform(0.3, 0.6), y_base + rng.uniform(4, 10)],
             [x0 - rng.uniform(0, 8), y_base + rng.uniform(2, 7)]]
        P = [np.array(p, float) for p in P]
        curve = (1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t ** 2 * P[2] + t ** 3 * P[3]
        if sottolineato:  # la curva si calcola comunque: il flag non deve cambiare il resto della mano
            merged[-1] = np.vstack([merged[-1], curve[1:]])
    elif kind < 0.75:  # coda che si allunga dall'ultima lettera
        e = merged[-1][-1]
        L = rng.uniform(8, 22)
        t = np.linspace(0, 1, 30)[:, None]
        tail = e + np.hstack([t * L, -np.sin(t * math.pi) * rng.uniform(1, 4) + t * rng.uniform(-3, 3)])
        merged[-1] = np.vstack([merged[-1], tail[1:]])
    elif kind == 2:  # riga netta sotto il nome, tirata da sinistra a destra
        t = np.linspace(0, 1, 40)
        riga = np.column_stack([x0 - 2 + (x1 - x0 + 5) * t,
                                y_base + rng.uniform(4, 6) + np.sin(t * math.pi) * rng.uniform(-1, 1)])
        if sottolineato:
            merged.append(riga)

    # --- traccia: ricampiona, tremolio, levigatura, inclinazione, linea di base
    paths = []
    s_off = 0.0
    for s in merged:
        p = _resample(s, 0.35)
        arc = s_off + np.arange(len(p)) * 0.35
        s_off = arc[-1] + rng.uniform(5, 20)
        p[:, 0] += tremor(arc)
        p[:, 1] += tremor2(arc + 50)
        p = _smooth(p, smooth_k)
        p[:, 0] = p[:, 0] - (p[:, 1] - BASELINE) * (slant + slant_n(p[:, 0]))
        p[:, 1] = p[:, 1] + base(p[:, 0]) * base_k
        c, si = math.cos(tilt), math.sin(tilt)
        p = np.column_stack([p[:, 0] * c + p[:, 1] * si, -p[:, 0] * si + p[:, 1] * c])

        # pressione: piena nei tratti discendenti e dove la penna rallenta (curve), filetto in salita
        d = np.gradient(p, axis=0)
        dd = np.gradient(d, axis=0)
        v = np.linalg.norm(d, axis=1) + 1e-6
        curv = np.abs(d[:, 0] * dd[:, 1] - d[:, 1] * dd[:, 0]) / v ** 3
        down = np.clip(d[:, 1] / v, 0, 1)
        w = 0.8 - 0.3 * contrasto + 0.6 * contrasto * down + 0.15 * np.tanh(curv * 2) + 0.12 * press(arc)
        w = _smooth(np.column_stack([w, w]), 15)[:, 0]
        a = arc - arc[0]
        if a[-1] > t_in + t_out:  # attacco e stacco sfumati; i tratti brevi (puntini) restano pieni
            w = w * np.clip(np.minimum(a / t_in, (a[-1] - a) / t_out), 0.45, 1)
        paths.append((p, np.clip(w0 * w, 0.15, None)))

    # --- SVG: segmenti raggruppati per spessore, estremi rotondi -> nessun buco negli incroci
    allp = np.vstack([p for p, _ in paths])
    m = 3 * w0
    mnx, mny = allp.min(axis=0) - m
    mxx, mxy = allp.max(axis=0) + m
    wmax = max(w.max() for _, w in paths)
    out = []
    for p, w in paths:
        lev = np.minimum((w / wmax * WIDTH_LEVELS).astype(int), WIDTH_LEVELS - 1)
        i = 0
        while i < len(p) - 1:
            j = i + 1
            while j < len(p) - 1 and lev[j] == lev[i]:
                j += 1
            pts = " ".join(f"{x - mnx:.2f},{y - mny:.2f}" for x, y in p[i:j + 1])
            out.append(f'<path d="M{pts}" stroke-width="{(lev[i] + 0.5) / WIDTH_LEVELS * wmax:.3f}"/>')
            i = j
    W, Hh = mxx - mnx, mxy - mny
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.2f} {Hh:.2f}" '
            f'width="{W * 4:.0f}" height="{Hh * 4:.0f}">'
            f'<g fill="none" stroke="{colore}" stroke-linecap="round" stroke-linejoin="round">'
            + "".join(out) + "</g></svg>\n")


if __name__ == "__main__":  # autoverifica: stesso seme = stessa firma, semi diversi = firme diverse
    a, b, c = generate("Mario Rossi", 1), generate("Mario Rossi", 1), generate("Mario Rossi", 2)
    assert a == b and a != c and a.startswith("<svg") and "nan" not in a
    for s in range(70):  # nessun seme/parametro/stile deve rompere il tracciato
        assert "nan" not in generate("Jürgen d'Ippolito-Jij", s, leggibilita=s % 3 / 2, inclinazione=s % 5 / 4,
                                     stile=STILI[s % len(STILI)][0], iniziale=s % 2 == 0)
    assert generate("Mario Rossi", 1, stile="sigla") == generate("Marco Ricci", 1, stile="sigla")  # solo iniziali
    assert generate("i", 1, stile="frettolosa").startswith("<svg")  # una sola lettera
    for st, _ in STILI:  # senza sottolineato restano gli stessi tratti, meno la riga
        con, senza = generate("Mario Rossi", 5, stile=st), generate("Mario Rossi", 5, stile=st, sottolineato=False)
        assert senza.count("<path") <= con.count("<path") and "nan" not in senza
    assert generate("Mario Rossi", 1, stile="professionale") != generate("Mario Rossi", 1, stile="professionale", sottolineato=False)
    print("ok")
