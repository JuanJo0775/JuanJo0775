"""Paneles tipograficos para la variante zine.

Los bloques de codigo de GitHub siempre traen su propio fondo, asi que la
estetica de papel no se puede lograr con markdown: estos paneles se rinden
como imagen para tener control real del color y de las cenefas.

    python scripts/build_zine.py
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "zine"

PAPER = (0xF2, 0xEE, 0xE4)
INK = (0x1A, 0x1A, 0x1A)
FADE = (0x6B, 0x66, 0x5C)

FONT_PATH = r"C:\Windows\Fonts\cour.ttf"
FONT_BOLD = r"C:\Windows\Fonts\courbd.ttf"

# glifos de la cenefa, tomados del poster de referencia
GLYPHS = ["|", "||", "|=|", "~~", "::", "==", ":|:", "//", "\\\\", "o o",
          "+ +", "---", "###", "( )", "[ ]", "* *", "<>", "^^", "~*~", "'''"]


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_PATH, size)


def ornament_row(d: ImageDraw.ImageDraw, y: int, w: int, rng: random.Random,
                 size: int = 22) -> None:
    """Fila de glifos de maquina de escribir separados por barras verticales."""
    f = font(size, bold=True)
    x = 14
    while x < w - 30:
        g = rng.choice(GLYPHS)
        d.text((x, y), g, font=f, fill=INK)
        x += int(d.textlength(g, font=f)) + 10
        d.text((x, y - 3), "|", font=f, fill=INK)
        x += 14


def rule(d: ImageDraw.ImageDraw, y: int, w: int, pad: int = 14,
         weight: int = 3, color=INK) -> None:
    d.rectangle([pad, y, w - pad, y + weight], fill=color)


def fit_font(d: ImageDraw.ImageDraw, text: str, max_w: int,
             start: int, bold: bool = True, floor: int = 14):
    """Baja el cuerpo hasta que el texto entre en max_w.

    Hace falta porque el nombre va con letter-spacing manual: un apellido
    largo desborda el panel si el cuerpo es fijo.
    """
    size = start
    while size > floor:
        f = font(size, bold=bold)
        if d.textlength(text, font=f) <= max_w:
            return f
        size -= 2
    return font(floor, bold=bold)


def header_panel(name_lines: list[str], sub_lines: list[str],
                 w: int = 1200, seed: int = 7) -> Image.Image:
    rng = random.Random(seed)
    margin = 60
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    spaced = ["  ".join(l) for l in name_lines]
    fonts = [fit_font(probe, s, w - margin * 2, 58) for s in spaced]
    name_h = sum(f.size + 22 for f in fonts)

    # la altura sale del contenido, no de un numero fijo, para que la ultima
    # linea nunca quede debajo de la cenefa
    h = 96 + 62 + name_h + 46 + len(sub_lines) * 36 + 86
    im = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(im)

    ornament_row(d, 18, w, rng)
    rule(d, 58, w)
    rule(d, 68, w, weight=1)

    fmark = font(30, bold=True)
    mark = "~~~ * ~~~"
    y = 100
    d.text(((w - d.textlength(mark, font=fmark)) / 2, y), mark, font=fmark, fill=FADE)

    y = 162
    for s, f in zip(spaced, fonts):
        d.text(((w - d.textlength(s, font=f)) / 2, y), s, font=f, fill=INK)
        y += f.size + 22

    y += 14
    d.rectangle([w // 2 - 190, y, w // 2 + 190, y + 2], fill=FADE)
    y += 26

    fsub = font(26)
    for line in sub_lines:
        d.text(((w - d.textlength(line, font=fsub)) / 2, y), line,
               font=fsub, fill=FADE)
        y += 36

    rule(d, h - 62, w, weight=1)
    rule(d, h - 52, w)
    ornament_row(d, h - 34, w, rng)
    return im


def rule_strip(w: int = 1200, seed: int = 21, label: str = "") -> Image.Image:
    """Cenefa corta para separar secciones."""
    rng = random.Random(seed)
    h = 86 if label else 56
    im = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(im)
    rule(d, 6, w, weight=2)
    ornament_row(d, 18, w, rng, size=18)
    if label:
        f = font(24, bold=True)
        t = f"  {label.upper()}  "
        tw = d.textlength(t, font=f)
        d.rectangle([(w - tw) / 2 - 6, 50, (w + tw) / 2 + 6, 82], fill=PAPER)
        d.text(((w - tw) / 2, 52), t, font=f, fill=INK)
    rule(d, h - 6, w, weight=2)
    return im


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    profile = json.loads((ROOT / "data/profile.json").read_text(encoding="utf-8"))

    parts = profile["full_name"].split()
    lines = [" ".join(parts[:2]), " ".join(parts[2:])] if len(parts) > 2 else [profile["full_name"]]
    sub = [profile["tagline"].replace("·", "-"), profile["location"]]

    header_panel(lines, sub).save(OUT / "header.png", optimize=True)
    for i, lab in enumerate(["quien soy", "el stack", "los proyectos",
                             "los numeros", "el contacto"]):
        rule_strip(seed=30 + i * 5, label=lab).save(OUT / f"rule-{i}.png", optimize=True)

    for p in sorted(OUT.glob("header.png")) + sorted(OUT.glob("rule-*.png")):
        print(f"  {p.name}  {Image.open(p).size}  {p.stat().st_size//1024} KB")
