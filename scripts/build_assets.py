"""Genera los assets del perfil a 1 bit, parametrizados por paleta.

Todas las piezas (banner, nombre, plates, gif) salen del mismo pipeline de
dithering, para que se vean como un solo sistema visual y no como imagenes
sueltas pegadas. Se ejecuta a mano cuando cambian las fuentes:

    python scripts/build_assets.py --src <carpeta-de-imagenes>
"""
from __future__ import annotations

import argparse
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageEnhance, ImageOps

# --- paletas -----------------------------------------------------------------
# cada variante define (fondo, tinta). "terminal" ademas trae variante clara,
# porque es la unica que se adapta al tema del lector.
PALETTES = {
    "terminal":       ((0x0D, 0x11, 0x17), (0xFF, 0xFF, 0xFF)),
    "terminal-light": ((0xFF, 0xFF, 0xFF), (0x0D, 0x11, 0x17)),
    "zine":           ((0xF2, 0xEE, 0xE4), (0x1A, 0x1A, 0x1A)),
    "crt":            ((0x05, 0x06, 0x08), (0x7D, 0xF9, 0xFF)),
}

SOURCES = {
    "map":    "WhatsApp Image 2026-08-31 at 3.31.39 PM.jpeg",
    "moon":   "WhatsApp Image 2026-08-31 at 3.33.34 PM.jpeg",
    "window": "WhatsApp Image 2026-08-31 at 3.23.40 PM.jpeg",
    "bridge": "WhatsApp Image 2026-08-31 at 3.33.34 PM (2).jpeg",
    "cloud":  "WhatsApp Image 2026-08-31 at 3.30.07 PM.jpeg",
    "video":  "WhatsApp Video 2026-08-31 at 3.23.40 PM.mp4",
}

FONT = {
    "A": [" ### ", "#   #", "#####", "#   #", "#   #"],
    "J": ["    #", "    #", "    #", "#   #", " ### "],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", " ### "],
    "U": ["#   #", "#   #", "#   #", "#   #", " ### "],
    "S": [" ####", "#    ", " ### ", "    #", "#### "],
    "R": ["#### ", "#   #", "#### ", "#  # ", "#   #"],
}


def paint(mask: Image.Image, bg, fg) -> Image.Image:
    """Convierte una mascara 1-bit a imagen indexada con la paleta dada.

    Se usa modo P (2 colores) en vez de RGB: mantiene los PNG en pocos KB.
    """
    out = Image.new("P", mask.size)
    out.putpalette(list(bg) + list(fg) + [0] * (256 * 3 - 6))
    src, dst = mask.load(), out.load()
    for y in range(mask.height):
        for x in range(mask.width):
            dst[x, y] = 1 if src[x, y] else 0
    return out


def flatten(path: Path, floor=48, ceil=210, cutoff=2) -> Image.Image:
    """Aplana artefactos JPEG antes de ditherear.

    Sin esto el dither interpreta el ruido de compresion como textura y
    ensucia las zonas que deberian ser negro plano.
    """
    im = ImageOps.autocontrast(Image.open(path).convert("L"), cutoff=cutoff)
    im = im.point(lambda v: 0 if v < floor else (255 if v > ceil else v))
    return im.convert("1")


def band(mask: Image.Image, ratio=3.4, scale=2, anchor="center") -> Image.Image:
    w, h = mask.size
    th = min(int(w / ratio), h)
    top = 0 if anchor == "top" else (h - th) // 2
    m = mask.crop((0, top, w, top + th))
    return m.resize((m.width * scale, m.height * scale), Image.NEAREST)


def trim(mask: Image.Image, pad=24) -> Image.Image:
    b = mask.getbbox()
    m = mask.crop(b) if b else mask
    out = Image.new("1", (m.width + pad * 2, m.height + pad * 2), 0)
    out.paste(m, (pad, pad))
    return out


def name_mask(word: str, px=12, gap=1, pad=3) -> Image.Image:
    """Dibuja el nombre como bloques de pixeles reales.

    Va como imagen y no como ASCII en un bloque de codigo a proposito:
    GitHub aplica line-height a los <pre> y eso parte los caracteres de
    bloque en franjas, que era como se veia roto en la primera version.
    """
    cols = sum(len(FONT[c][0]) + gap for c in word) - gap
    im = Image.new("1", ((cols + pad * 2) * px, (5 + pad * 2) * px), 0)
    d = ImageDraw.Draw(im)
    x0 = pad
    for ch in word:
        for r, line in enumerate(FONT[ch]):
            for c, v in enumerate(line):
                if v == "#":
                    d.rectangle([(x0 + c) * px, (pad + r) * px,
                                 (x0 + c) * px + px - 1, (pad + r) * px + px - 1],
                                fill=1)
        x0 += len(FONT[ch][0]) + gap
    return im


def sphere_frames(src: Path, side=200, n=48):
    """Frames de la esfera de digitos girando, ya dithered a 1 bit."""
    cap = cv2.VideoCapture(str(src))
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    out = []
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(total * i / n))
        ok, fr = cap.read()
        if not ok:
            continue
        g = Image.fromarray(cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY))
        g = ImageOps.autocontrast(g.resize((side, side), Image.LANCZOS), cutoff=1)
        out.append(g.point(lambda v: 0 if v < 60 else v).convert("1"))
    cap.release()
    return out


def subpixel_strip(path: Path, w=1200, h=110) -> Image.Image:
    """Franja de subpixel RGB sacada de la macro del CRT (solo variante crt).

    Se recorta por el centro vertical de la nube, que es donde los subpixeles
    encienden mas parejo; mas arriba o mas abajo la franja sale casi negra.
    """
    im = Image.open(path).convert("RGB")
    cy = int(im.height * 0.46)
    half = int(im.height * 0.055)
    im = im.crop((int(im.width * 0.12), cy - half, int(im.width * 0.88), cy + half))
    im = ImageEnhance.Color(im).enhance(1.5)
    im = ImageEnhance.Brightness(im).enhance(1.25)
    return im.resize((w, h), Image.LANCZOS)


def build(src_dir: Path, out_root: Path, word: str, plates: tuple[str, str],
          banner_key: str, banner_anchor: str) -> None:
    masks = {
        "banner":  band(flatten(src_dir / SOURCES[banner_key]), anchor=banner_anchor),
        "name":    name_mask(word),
        "plate-a": trim(flatten(src_dir / SOURCES[plates[0]])),
        "plate-b": trim(flatten(src_dir / SOURCES[plates[1]]), pad=14),
    }
    frames = sphere_frames(src_dir / SOURCES["video"])

    for pal, (bg, fg) in PALETTES.items():
        d = out_root / pal
        d.mkdir(parents=True, exist_ok=True)
        for stem, mask in masks.items():
            p = d / f"{stem}.png"
            paint(mask, bg, fg).save(p, optimize=True)
        gif = [paint(f, bg, fg) for f in frames]
        gp = d / "sphere.gif"
        gif[0].save(gp, save_all=True, append_images=gif[1:],
                    duration=70, loop=0, optimize=True, disposal=2)
        total = sum(f.stat().st_size for f in d.iterdir()) // 1024
        print(f"  {pal:<15} {len(list(d.iterdir()))} archivos  {total} KB")

    # va en JPEG y no PNG: es una foto, en PNG pesa 6x mas sin verse mejor
    strip = subpixel_strip(src_dir / SOURCES["cloud"])
    sp = out_root / "crt" / "subpixel.jpg"
    strip.save(sp, quality=86, optimize=True)
    print(f"  crt/subpixel.jpg  {strip.size}  {sp.stat().st_size//1024} KB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, type=Path)
    ap.add_argument("--out", default=Path("assets"), type=Path)
    ap.add_argument("--word", default="JUANJO")
    ap.add_argument("--banner", default="map", choices=list(SOURCES))
    ap.add_argument("--banner-anchor", default="center", choices=["center", "top"])
    ap.add_argument("--plates", default="moon,window")
    a = ap.parse_args()
    p = tuple(a.plates.split(","))
    print(f"generando assets para '{a.word}':")
    build(a.src, a.out, a.word, p, a.banner, a.banner_anchor)
