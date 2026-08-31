"""Arma la tabla de proyectos del README leyendo la API de GitHub.

La descripcion, el enlace y el demo de cada proyecto salen del repo real
cada vez que corre la Action, en vez de estar escritos dentro del README.

Lo que SI queda curado en data/profile.json, a proposito:
  - cuales repos se muestran y en que orden (es criterio, no dato);
  - el titulo visible (los nombres de repo tienen guiones bajos);
  - las etiquetas de tecnologia. La API devuelve lenguajes por bytes de
    archivo ("Python · CSS · Dockerfile"), que dice menos que "Django ·
    DRF · React"; el framework es una decision editorial, no un dato.

    python scripts/build_readme.py            # reescribe README.md
    python scripts/build_readme.py --check    # sale 1 si quedaria distinto

Sin dependencias externas: corre en la Action con python puro.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent


def api(path: str) -> dict:
    req = urllib.request.Request(f"{API}{path}", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "perfil-readme-builder",
    })
    # Opcional: sin token la API da 60 req/h, de sobra para correrlo a mano.
    # La Action si lo pasa y sube el limite a 5000.
    if token := os.environ.get("GITHUB_TOKEN"):
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch(user: str, repo: str) -> dict | None:
    try:
        d = api(f"/repos/{user}/{repo}")
    except urllib.error.HTTPError as e:
        print(f"  aviso: {repo} -> HTTP {e.code}, se omite", file=sys.stderr)
        return None
    return {
        "url": d["html_url"],
        "description": (d.get("description") or "").strip(),
        "homepage": (d.get("homepage") or "").strip(),
    }


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def links_cell(main: dict, pair: dict | None, width: str) -> list[str]:
    """La celda de enlaces: una linea si es un solo repo, bloque si son dos."""
    demo = main["homepage"] or (pair["homepage"] if pair else "")
    if not pair and not demo:
        return [f'  <td{width} align="right">'
                f'<sub><a href="{main["url"]}">repo</a></sub></td>']

    parts = ([f'<a href="{main["url"]}">backend</a>',
              f'<a href="{pair["url"]}">frontend</a>'] if pair
             else [f'<a href="{main["url"]}">repo</a>'])
    if demo:
        parts.append(f'<a href="{demo}">demo</a>')
    body = " ·\n    ".join(parts)
    return [f'  <td{width} align="right">', "    <sub>", f"    {body}",
            "    </sub>", "  </td>"]


def table(items: list[tuple[dict, dict, dict | None]]) -> str:
    """Tabla HTML. Se usa <table> y no un bloque de codigo porque hay que
    poder hacer clic en los enlaces; GitHub la deja pasar tal cual."""
    out = ['<table width="100%">']
    for i, (spec, main, pair) in enumerate(items, 1):
        # solo la primera fila lleva los anchos; las demas los heredan
        w = (' width="6%"', ' width="40%"', ' width="30%"', ' width="24%"') \
            if i == 1 else ("", "", "", "")
        out += [
            '<tr valign="top">',
            f'  <td{w[0]}><code>{i:02d}</code></td>',
            f'  <td{w[1]}>',
            f'    <b>{esc(spec["title"])}</b><br>',
            f'    <sub>{esc(main["description"])}</sub>',
            '  </td>',
            f'  <td{w[2]}><sub><code>{esc(spec["tech"])}</code></sub></td>',
        ]
        out += links_cell(main, pair, w[3])
        out.append('</tr>')
    out.append('</table>')
    return "\n".join(out)


def build(profile: dict) -> str:
    user = profile["username"]
    print(f"leyendo datos en vivo de {user}...")
    items = []
    for spec in profile["projects"]:
        main = fetch(user, spec["repo"])
        if not main:
            continue
        pair = fetch(user, spec["pair"]) if spec.get("pair") else None
        items.append((spec, main, pair))
        flag = "" if main["description"] else "   <- sin description en GitHub"
        print(f"  {spec['title']}{flag}")

    md = (ROOT / "templates/terminal.md").read_text(encoding="utf-8")
    md = md.replace("{{PROJECTS}}", table(items)).replace("{{USER}}", user)
    if "{{" in md:
        print("aviso: quedaron placeholders sin resolver", file=sys.stderr)
    return md


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=ROOT / "data/profile.json", type=Path)
    ap.add_argument("--out", default=ROOT / "README.md", type=Path)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()

    md = build(json.loads(a.profile.read_text(encoding="utf-8")))
    if a.check:
        cur = a.out.read_text(encoding="utf-8") if a.out.exists() else ""
        if cur != md:
            print("README desactualizado", file=sys.stderr)
            sys.exit(1)
        print("README al dia")
    else:
        a.out.write_text(md, encoding="utf-8")
        print(f"escrito {a.out} ({len(md)} bytes)")
