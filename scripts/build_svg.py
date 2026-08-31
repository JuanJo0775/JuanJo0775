"""Genera los dos SVG animados del README.

GitHub no ejecuta <script> en un README, pero si anima SVG servido por camo
(es como funciona el typing-svg). Asi que el efecto scramble se arma con
animaciones CSS puras dentro del propio SVG.

  tagline.svg        frases que se revelan letra por letra desde caracteres
                     aleatorios, en bucle

No se dibuja aqui una grilla de contribuciones: cualquier version propia
tendria que animar una capa encima del dato real, y en un visor que no
ejecute las animaciones esa capa se queda fija mostrando valores que no
son los reales. La grilla nativa de GitHub, que sale bajo el README, no
es personalizable, asi que se usa esa.

    python scripts/build_svg.py

Sin dependencias externas: corre en la Action con python puro.
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets"

GLYPHS = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#%&$@?!/\\<>[]{}=+*-_·^~"
MONO = "ui-monospace,SFMono-Regular,Menlo,Consolas,'DejaVu Sans Mono',monospace"

# (fondo, tinta, tinta tenue, acento de la grilla)
THEMES = {
    "":       ("#0D1117", "#E6EDF3", "#8A939D", "#FFFFFF"),
    "-light": ("#FFFFFF", "#1F2328", "#6E7781", "#0D1117"),
}


def esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


# --------------------------------------------------------------------------
# 1. tagline: scramble en bucle
# --------------------------------------------------------------------------
def tagline_svg(phrases: list[str], theme: str, width=620, size=15,
                steps=6, seed=11) -> str:
    """Cada posicion pasa por varios glifos al azar y despues fija el real.

    Todas las animaciones duran lo mismo (el ciclo completo) y se colocan en
    el tiempo con animation-delay; asi el SVG no necesita un @keyframes por
    elemento. Los tiempos de fijado se agrupan en buckets, de modo que hacen
    falta solo unas decenas de reglas para cientos de glifos.
    """
    bg, ink, dim, _ = THEMES[theme]
    rng = random.Random(seed)
    adv = size * 0.6                       # avance monoespaciado

    # linea de tiempo de cada frase, en segundos desde que entra
    hold_end = 2.60                        # cuando empieza a borrarse
    ex_span, ex_len = 0.35, 0.42           # escalonado y duracion del borrado
    slot = hold_end + ex_span + ex_len + 0.23
    total = slot * len(phrases)
    height = int(size * 2.6)
    cy = height / 2

    buckets, lo, span = 10, 0.22, 0.95     # el fijado va de 0.22 s a 1.17 s
    ex_steps = 3
    css = [
        # opacity:0 de base es imprescindible: un elemento con
        # animation-delay positivo se dibuja con su estilo base mientras
        # espera, y sin esto las frases siguientes se ven encima de la actual
        f".c{{font:{size}px {MONO};fill:{ink};text-anchor:middle;"
        f"dominant-baseline:middle;opacity:0}}",
        f".n{{fill:{dim}}}",
        # el ruido de salida dura siempre lo mismo, asi que le basta una regla
        f"@keyframes nx{{0%,49.99%{{opacity:0}}"
        f"50%,{50 + ex_len / ex_steps / total * 100:.3f}%{{opacity:1}}"
        f"{50 + ex_len / ex_steps / total * 100 + 0.01:.3f}%,100%{{opacity:0}}}}",
    ]
    # el de entrada si depende del bucket: la rebanada visible es rb/steps
    for b in range(buckets):
        rb = lo + (b + 0.5) / buckets * span
        pct = rb / steps / total * 100
        css.append(
            f"@keyframes n{b}{{0%,49.99%{{opacity:0}}"
            f"50%,{50 + pct:.3f}%{{opacity:1}}"
            f"{50 + pct + 0.01:.3f}%,100%{{opacity:0}}}}")

    def noise(x, cls, dur_key, at):
        """La ventana visible del keyframe cae al 50% del ciclo; el delay la
        corre hasta el instante que toca."""
        return (f'<text class="c n" x="{x:.1f}" y="{cy:.1f}" '
                f'style="animation:{dur_key} {total:.2f}s steps(1) infinite;'
                f'animation-delay:{at - total / 2:.3f}s">'
                f'{esc(rng.choice(GLYPHS))}</text>')

    body = []
    for p, text in enumerate(phrases):
        t0 = p * slot
        chars = list(text)
        x0 = width / 2 - (len(chars) - 1) * adv / 2
        last = max(1, len(chars) - 1)
        seen = set()
        for i, ch in enumerate(chars):
            if ch == " ":
                continue
            x = x0 + i * adv
            # entra de izquierda a derecha...
            b = min(buckets - 1, int(i / last * buckets))
            rb = lo + (b + 0.5) / buckets * span
            # ...y se borra de derecha a izquierda, para que no se sienta
            # la misma animacion dos veces
            ex = (1 - i / last) * ex_span
            slice_ = rb / steps

            for s in range(steps):
                body.append(noise(x, "n", f"n{b}", t0 + slice_ * s))
            for s in range(ex_steps):
                body.append(noise(x, "n", "nx",
                                  t0 + hold_end + ex + ex_len * s / ex_steps))

            eb = round(ex, 3)
            key = f"k{p}_{b}_{int(eb * 1000)}"
            if key not in seen:
                seen.add(key)
                a = (t0 + rb) / total * 100
                z = (t0 + hold_end + eb) / total * 100
                css.append(
                    f"@keyframes {key}{{0%,{a:.3f}%{{opacity:0}}"
                    f"{a + 0.01:.3f}%,{z:.3f}%{{opacity:1}}"
                    f"{z + 0.01:.3f}%,100%{{opacity:0}}}}")
            body.append(
                f'<text class="c" x="{x:.1f}" y="{cy:.1f}" '
                f'style="animation:{key} {total:.2f}s linear infinite">'
                f'{esc(ch)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
            f'height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="{esc(" · ".join(phrases))}">'
            f'<style>{"".join(css)}</style>'
            f'<rect width="100%" height="100%" fill="{bg}"/>'
            f'{"".join(body)}</svg>')


if __name__ == "__main__":
    profile = json.loads((ROOT / "data/profile.json").read_text(encoding="utf-8"))
    user = profile["username"]
    phrases = profile["tagline_lines"]

    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        p = OUT / f"tagline{theme}.svg"
        p.write_text(tagline_svg(phrases, theme), encoding="utf-8")
        print(f"  {p.name}  {p.stat().st_size // 1024} KB")
