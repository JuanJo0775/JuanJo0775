"""Redibuja el arte de puntos del README a partir de las imagenes fuente.

Las fuentes son fotos de arte hecho con reticulas de puntos. Ditherearlas
solo les agrega ruido encima: en vez de eso se mide el paso de la grilla por
autocorrelacion, se promedia cada celda y se vuelve a dibujar como circulo
limpio. El resultado tiene mas resolucion que la foto original y las tres
piezas comparten el mismo sistema de puntos.

    python scripts/build_art.py --src <carpeta-de-imagenes>

Se corre a mano cuando cambian las fuentes; no va en la Action.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageOps

# (fondo, tinta) — el fondo oscuro es el lienzo de GitHub, para que la
# imagen no se vea como un rectangulo pegado sobre la pagina
THEMES = {"": ((0x0D, 0x11, 0x17), (0xFF, 0xFF, 0xFF)),
          "-light": ((0xFF, 0xFF, 0xFF), (0x0D, 0x11, 0x17))}

# Cada pieza con su grilla medida. cols/rows salen de dividir el recorte
# util por el paso detectado; px/py son el paso al redibujar y r el radio.
PIECES = {
    "banner": dict(
        file="WhatsApp Image 2026-08-31 at 3.31.39 PM.jpeg",
        cols=176, rows=23, px=12, py=22, r=4.6, thr=22, cut=110),
}

# El ASCII no es una reticula de puntos sino texto: ahi el umbral simple
# conserva los glifos, que es justo lo que le da caracter.
GLYPH_ART = dict(file="WhatsApp Image 2026-08-31 at 3.33.34 PM (1).jpeg",
                 cut=120, scale=2, pad=26)


def crop_art(path: Path, cut: int) -> Image.Image:
    g = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=1)
    m = g.point(lambda v: 255 if v > cut else 0)
    b = m.convert("1").getbbox()
    return m.crop(b) if b else m


def redraw(path: Path, cols: int, rows: int, px: int, py: int, r: float,
           thr: int, cut: int, bg, fg) -> Image.Image:
    """Promedia cada celda de la grilla y la redibuja como circulo."""
    grid = crop_art(path, cut).resize((cols, rows), Image.BOX)
    src = grid.load()
    pad_x, pad_y = px, py
    im = Image.new("RGB", (cols * px + pad_x * 2, rows * py + pad_y * 2), bg)
    d = ImageDraw.Draw(im)
    for y in range(rows):
        for x in range(cols):
            if src[x, y] > thr:
                cx, cy = pad_x + x * px + px / 2, pad_y + y * py + py / 2
                d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fg)
    return im


def glyphs(path: Path, cut: int, scale: int, pad: int, bg, fg) -> Image.Image:
    m = crop_art(path, cut)
    m = m.resize((m.width * scale, m.height * scale), Image.NEAREST)
    im = Image.new("RGB", (m.width + pad * 2, m.height + pad * 2), bg)
    ink = Image.new("RGB", m.size, fg)
    im.paste(ink, (pad, pad), m.convert("1"))
    return im


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", default=Path("assets"), type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    for suffix, (bg, fg) in THEMES.items():
        for name, cfg in PIECES.items():
            cfg = dict(cfg)
            im = redraw(a.src / cfg.pop("file"), bg=bg, fg=fg, **cfg)
            p = a.out / f"{name}{suffix}.png"
            im.quantize(colors=2).save(p, optimize=True)
            print(f"  {p.name:22} {im.size}  {p.stat().st_size // 1024} KB")

        cfg = dict(GLYPH_ART)
        im = glyphs(a.src / cfg.pop("file"), bg=bg, fg=fg, **cfg)
        p = a.out / f"glyphs{suffix}.png"
        im.quantize(colors=2).save(p, optimize=True)
        print(f"  {p.name:22} {im.size}  {p.stat().st_size // 1024} KB")
