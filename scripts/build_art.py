"""Genera el arte ASCII del README a partir de la imagen fuente.

El banner del mapa NO se genera aqui, a proposito. Su version original usa
dithering, y de ahi le viene la textura fina de puntos irregulares; al
redibujarlo con circulos uniformes se pierde justo eso. Los archivos
assets/banner*.png se conservan tal como estan y no deben regenerarse.

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

# El ASCII no es una reticula de puntos sino texto: el umbral simple conserva
# los glifos, que es justo lo que le da caracter. Ditherearlo o redibujarlo
# con circulos los destruiria.
SOURCE = "WhatsApp Image 2026-08-31 at 3.33.34 PM (1).jpeg"
CUT, SCALE, PAD = 120, 2, 26


def glyphs(path: Path, bg, fg) -> Image.Image:
    g = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=1)
    m = g.point(lambda v: 255 if v > CUT else 0)
    b = m.convert("1").getbbox()
    m = m.crop(b) if b else m
    m = m.resize((m.width * SCALE, m.height * SCALE), Image.NEAREST)
    im = Image.new("RGB", (m.width + PAD * 2, m.height + PAD * 2), bg)
    im.paste(Image.new("RGB", m.size, fg), (PAD, PAD), m.convert("1"))
    return im


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", default=Path("assets"), type=Path)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    for suffix, (bg, fg) in THEMES.items():
        p = a.out / f"glyphs{suffix}.png"
        glyphs(a.src / SOURCE, bg, fg).quantize(colors=2).save(p, optimize=True)
        print(f"  {p.name:20} {p.stat().st_size // 1024} KB")
