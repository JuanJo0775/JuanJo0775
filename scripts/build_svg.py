"""Genera los dos SVG animados del README.

GitHub no ejecuta <script> en un README, pero si anima SVG servido por camo
(es como funciona el typing-svg). Asi que el efecto scramble se arma con
animaciones CSS puras dentro del propio SVG.

  tagline.svg        frases que se revelan letra por letra desde caracteres
                     aleatorios, en bucle
  contributions.svg  el ano de contribuciones con datos reales de la API,
                     con un decodificado de una sola pasada al cargar

    python scripts/build_svg.py           # necesita GITHUB_TOKEN

Sin dependencias externas: corre en la Action con python puro.
"""
from __future__ import annotations

import json
import os
import random
import sys
import urllib.request
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


def gql(query: str, **vars) -> dict:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("falta GITHUB_TOKEN")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": vars}).encode(),
        headers={"Authorization": f"Bearer {token}",
                 "User-Agent": "perfil-svg-builder",
                 "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.load(r)
    if "errors" in d:
        sys.exit(f"GraphQL: {d['errors']}")
    return d["data"]


def contributions(login: str) -> dict:
    d = gql("""
      query($login:String!){
        user(login:$login){
          contributionsCollection{
            contributionCalendar{
              totalContributions
              weeks{ contributionDays{ date contributionCount weekday } }
            }
          }
        }
      }""", login=login)
    return d["user"]["contributionsCollection"]["contributionCalendar"]


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
    hold, gap = 2.8, 0.25                  # segundos visible / en blanco
    slot = hold + gap
    total = slot * len(phrases)
    height = int(size * 2.6)
    cy = height / 2

    buckets, lo, span = 10, 0.22, 0.95     # el fijado va de 0.22 s a 1.17 s
    css = [
        # opacity:0 de base es imprescindible: un elemento con
        # animation-delay positivo se dibuja con su estilo base mientras
        # espera, y sin esto las frases siguientes se ven encima de la actual
        f".c{{font:{size}px {MONO};fill:{ink};text-anchor:middle;"
        f"dominant-baseline:middle;opacity:0}}",
        f".n{{fill:{dim}}}",
    ]
    # una regla de ruido por bucket: la rebanada visible es rb/steps
    for b in range(buckets):
        rb = lo + (b + 0.5) / buckets * span
        pct = rb / steps / total * 100
        css.append(
            f"@keyframes n{b}{{0%,49.99%{{opacity:0}}"
            f"50%,{50 + pct:.3f}%{{opacity:1}}"
            f"{50 + pct + 0.01:.3f}%,100%{{opacity:0}}}}")

    body = []
    for p, text in enumerate(phrases):
        t0 = p * slot
        chars = list(text)
        x0 = width / 2 - (len(chars) - 1) * adv / 2
        seen = set()
        for i, ch in enumerate(chars):
            if ch == " ":
                continue
            x = x0 + i * adv
            # cada letra se fija un poco despues que la anterior
            b = min(buckets - 1, int(i / max(1, len(chars) - 1) * buckets))
            rb = lo + (b + 0.5) / buckets * span
            slice_ = rb / steps

            for s in range(steps):
                # la ventana visible del keyframe empieza al 50% del ciclo,
                # asi que el delay coloca ese instante donde toca
                delay = (t0 + slice_ * s) - total / 2
                body.append(
                    f'<text class="c n" x="{x:.1f}" y="{cy:.1f}" '
                    f'style="animation:n{b} {total:.2f}s steps(1) infinite;'
                    f'animation-delay:{delay:.3f}s">'
                    f'{esc(rng.choice(GLYPHS))}</text>')

            key = f"k{p}_{b}"
            if key not in seen:
                seen.add(key)
                a, z = (t0 + rb) / total * 100, (t0 + hold) / total * 100
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


# --------------------------------------------------------------------------
# 2. contribuciones: datos reales, decodificado de una pasada
# --------------------------------------------------------------------------
def contributions_svg(cal: dict, theme: str, seed=5) -> str:
    """Grilla real del ano. El estado final es siempre el dato correcto:
    encima se pinta una capa de ruido que se desvanece de izquierda a
    derecha, asi que el 'decodificado' nunca miente sobre la informacion.
    """
    bg, ink, dim, accent = THEMES[theme]
    rng = random.Random(seed)
    weeks = cal["weeks"]
    days = [d for w in weeks for d in w["contributionDays"]]
    total = cal["totalContributions"]
    active = sum(1 for d in days if d["contributionCount"])
    peak = max(d["contributionCount"] for d in days)

    cell, gap = 11, 3
    pitch = cell + gap
    pad_x, top = 14, 54
    w = pad_x * 2 + len(weeks) * pitch
    h = top + 7 * pitch + 26

    # 5 niveles, como el grid de GitHub pero monocromo
    def level(c: int) -> int:
        if c == 0:
            return 0
        return min(4, 1 + int(c / max(1, peak) * 3.99))
    op = [0.055, 0.30, 0.52, 0.76, 1.0]

    css = [
        f".t{{font:600 13px {MONO};fill:{ink}}}",
        f".s{{font:11px {MONO};fill:{dim}}}",
        # una sola pasada: al terminar se queda el dato real a la vista
        "@keyframes dec{0%{opacity:1}70%{opacity:1}100%{opacity:0}}",
        ".nz{animation:dec 1s ease-out forwards}",
    ]
    body = [
        f'<text class="t" x="{pad_x}" y="22">{total} contribuciones '
        f'en el último año</text>',
        f'<text class="s" x="{pad_x}" y="40">{active} días activos '
        f'· máximo {peak} en un día</text>',
    ]

    for wi, week in enumerate(weeks):
        x = pad_x + wi * pitch
        for d in week["contributionDays"]:
            y = top + d["weekday"] * pitch
            o = op[level(d["contributionCount"])]
            body.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="2" '
                f'fill="{accent}" opacity="{o}"/>')
            # ruido encima, se va antes en las semanas de la izquierda
            delay = 0.15 + wi / len(weeks) * 1.5 + rng.random() * 0.18
            body.append(
                f'<rect class="nz" x="{x}" y="{y}" width="{cell}" '
                f'height="{cell}" rx="2" fill="{accent}" '
                f'opacity="{rng.choice(op):.3f}" '
                f'style="animation-delay:{delay:.2f}s"/>')

    body.append(
        f'<text class="s" x="{w - pad_x}" y="{h - 8}" text-anchor="end">'
        f'{days[0]["date"]} → {days[-1]["date"]}</text>')

    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
            f'viewBox="0 0 {w} {h}" role="img" '
            f'aria-label="{total} contribuciones en el último año">'
            f'<style>{"".join(css)}</style>'
            f'<rect width="100%" height="100%" fill="{bg}"/>'
            f'{"".join(body)}</svg>')


if __name__ == "__main__":
    profile = json.loads((ROOT / "data/profile.json").read_text(encoding="utf-8"))
    user = profile["username"]
    phrases = profile["tagline_lines"]

    cal = contributions(user)
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        for name, svg in (("tagline", tagline_svg(phrases, theme)),
                          ("contributions", contributions_svg(cal, theme))):
            p = OUT / f"{name}{theme}.svg"
            p.write_text(svg, encoding="utf-8")
            print(f"  {p.name}  {p.stat().st_size // 1024} KB")
