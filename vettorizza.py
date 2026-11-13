"""Converte un'immagine di firma (PNG/JPG) in SVG vettoriale con potrace."""
import numpy as np
import potrace
from PIL import Image, ImageFilter

UPSCALE = 4  # ingrandisce prima del trace: curve più morbide


def png_to_svg(src, dst):
    im = Image.open(src).convert("RGBA")
    a = np.asarray(im).astype(np.float32) / 255
    # copertura d'inchiostro 0..1: opaco e scuro (vale per PNG trasparenti e per scansioni su bianco)
    cov = a[..., 3] * (1 - a[..., :3].mean(axis=2))
    strong = cov > 0.6
    if not strong.any():
        raise ValueError("Nessun tratto di firma trovato nell'immagine")
    r, g, b = (int(c * 255) for c in a[strong][:, :3].mean(axis=0))
    color = f"#{r:02x}{g:02x}{b:02x}"
    # ingrandisci la copertura (non la soglia) e sfuma: bordi lisci invece che a scalini
    c = Image.fromarray((cov * 255).astype(np.uint8), "L")
    c = c.resize((c.width * UPSCALE, c.height * UPSCALE), Image.BICUBIC)
    c = c.filter(ImageFilter.GaussianBlur(UPSCALE * 0.4))
    ink = np.asarray(c) > 60  # soglia bassa: salva i tratti sottili

    ys, xs = np.nonzero(ink)
    pad = 4
    x0, y0 = max(xs.min() - pad, 0), max(ys.min() - pad, 0)
    x1, y1 = min(xs.max() + pad, ink.shape[1]), min(ys.max() + pad, ink.shape[0])
    ink = ink[y0:y1, x0:x1]

    path = potrace.Bitmap(~ink).trace(turdsize=8, alphamax=1.0, opticurve=True, opttolerance=0.2)
    d = []
    for curve in path:
        sp = curve.start_point
        d.append(f"M{sp.x:.2f},{sp.y:.2f}")
        for seg in curve.segments:
            if seg.is_corner:
                d.append(f"L{seg.c.x:.2f},{seg.c.y:.2f}L{seg.end_point.x:.2f},{seg.end_point.y:.2f}")
            else:
                d.append(f"C{seg.c1.x:.2f},{seg.c1.y:.2f} {seg.c2.x:.2f},{seg.c2.y:.2f} "
                         f"{seg.end_point.x:.2f},{seg.end_point.y:.2f}")
        d.append("Z")
    w, h = ink.shape[1], ink.shape[0]
    with open(dst, "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
                f'width="{w}" height="{h}"><path fill="{color}" fill-rule="evenodd" '
                f'd="{"".join(d)}"/></svg>\n')
    return dst
