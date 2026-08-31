"""Genera el arte ASCII del README a partir de la imagen fuente.

El banner del mapa NO se genera aqui, a proposito. Su version original usa
dithering, y de ahi le viene la textura fina de puntos irregulares; al
redibujarlo con circulos uniformes se pierde justo eso. Los archivos
assets/map*.png se conservan tal como estan y no deben regenerarse.

    python scripts/build_art.py --src <carpeta-de-imagenes>

Se corre a mano cuando cambia la fuente; no va en la Action.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageOps

# (fondo, tinta) — el fondo oscuro es el lienzo de GitHub, para que la
# imagen no se vea como un rectangulo pegado sobre la pagina
THEMES = {"": ((0x0D, 0x11, 0x17), (0xFF, 0xFF, 0xFF)),
          "-light": ((0xFF, 0xFF, 0xFF), (0x0D, 0x11, 0x17))}

SOURCE = "WhatsApp Image 2026-08-31 at 3.33.34 PM (1).jpeg"

# Se aplanan los tonos casi-negros y casi-blancos ANTES de ditherear: sin
# eso el dither lee los artefactos del JPEG como textura y ensucia el fondo.
# Y se deja a resolucion nativa, sin escalar: al ampliar, los glifos se
# vuelven bloques y se pierde el trazo fino que le da caracter al ASCII.
FLOOR, CEIL, CUTOFF, PAD = 48, 210, 2, 24


def glyphs(path: Path, bg, fg) -> Image.Image:
    g = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=CUTOFF)
    g = g.point(lambda v: 0 if v < FLOOR else (255 if v > CEIL else v))
    m = g.convert("1")                      # dithering Floyd-Steinberg
    b = m.getbbox()
    m = m.crop(b) if b else m

    canvas = Image.new("1", (m.width + PAD * 2, m.height + PAD * 2), 0)
    canvas.paste(m, (PAD, PAD))

    out = Image.new("P", canvas.size)
    out.putpalette(list(bg) + list(fg) + [0] * (256 * 3 - 6))
    src, dst = canvas.load(), out.load()
    for y in range(canvas.height):
        for x in range(canvas.width):
            dst[x, y] = 1 if src[x, y] else 0
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", default=Path("assets"), type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    for suffix, (bg, fg) in THEMES.items():
        p = a.out / f"ascii{suffix}.png"
        im = glyphs(a.src / SOURCE, bg, fg)
        im.save(p, optimize=True)
        print(f"  {p.name:20} {im.size}  {p.stat().st_size // 1024} KB")
