"""Arma el README del perfil leyendo los datos en vivo desde la API de GitHub.

Nada del contenido de los repos vive en el README: nombre, descripcion,
lenguajes, estrellas y fecha de ultimo push salen de la API cada vez que corre
la Action. Lo unico que se decide a mano es CUALES repos mostrar, que es
curaduria y no dato.

    python scripts/build_readme.py                 # usa data/profile.json
    python scripts/build_readme.py --check         # falla si el README cambiaria

Sin dependencias externas a proposito: corre en la Action con python puro.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parent.parent

# La API de lenguajes cuenta por bytes y mete archivos de infraestructura al
# mismo nivel que el lenguaje real del proyecto. Mostrar "Python · Dockerfile ·
# Shell" no dice nada util, asi que estos no entran en la lista.
NOT_A_LANGUAGE = {
    "Dockerfile", "Shell", "Procfile", "Makefile", "Batchfile",
    "CMake", "Bru", "Roff", "PowerShell",
}


def api(path: str) -> dict | list:
    req = urllib.request.Request(f"{API}{path}", headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "perfil-readme-builder",
    })
    # El token es opcional: sin el la API da 60 req/h, suficiente para correr
    # esto a mano; la Action si lo pasa y sube el limite a 5000.
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def fetch_repo(user: str, repo: str) -> dict | None:
    try:
        d = api(f"/repos/{user}/{repo}")
        langs = api(f"/repos/{user}/{repo}/languages")
    except urllib.error.HTTPError as e:
        print(f"  aviso: {repo} -> HTTP {e.code}, se omite", file=sys.stderr)
        return None
    return {
        "name": d["name"],
        "url": d["html_url"],
        "description": (d.get("description") or "").strip(),
        "homepage": (d.get("homepage") or "").strip(),
        "stars": d.get("stargazers_count", 0),
        "pushed": d.get("pushed_at", "")[:10],
        "langs": [l for l in langs if l not in NOT_A_LANGUAGE][:3],
    }


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def stack_block(stack: dict, width: int = 17, dot: str = "·") -> str:
    """Arbol del stack con guias de puntos alineadas al caracter."""
    out = []
    for k, v in stack.items():
        pad = dot * max(1, width - len(k) - 1)
        out.append(f"  {k} {pad}  {'   '.join(v)}")
    return "\n".join(out)


def stack_list(stack: dict) -> str:
    """Version tipografica del stack, para plantillas sin bloques de codigo."""
    return "\n".join(
        f'  **{k}** &nbsp;{"&nbsp;·&nbsp; ".join(f"`{i}`" for i in v)}  '
        for k, v in stack.items()
    )


def _links(p: dict, main: dict, pair: dict | None) -> str:
    parts = []
    if pair:
        parts.append(f'<a href="{main["url"]}">backend</a>')
        parts.append(f'<a href="{pair["url"]}">frontend</a>')
    else:
        parts.append(f'<a href="{main["url"]}">repo</a>')
    if main["homepage"]:
        parts.append(f'<a href="{main["homepage"]}">demo</a>')
    elif pair and pair["homepage"]:
        parts.append(f'<a href="{pair["homepage"]}">demo</a>')
    return " ·\n    ".join(parts)


def projects_table(items: list[tuple[dict, dict, dict | None]]) -> str:
    """Tabla HTML: el <table> sobrevive el saneamiento de GitHub y deja
    los enlaces clicables, cosa que un bloque de codigo no permite."""
    rows = ['<table width="100%">']
    for i, (spec, main, pair) in enumerate(items, 1):
        title = spec.get("title") or main["name"].replace("_", " ").replace("-", " ")
        desc = main["description"] or pair and pair["description"] or ""
        langs = main["langs"] + [l for l in (pair["langs"] if pair else []) if l not in main["langs"]]
        w = ' width="6%"' if i == 1 else ""
        w2 = ' width="40%"' if i == 1 else ""
        w3 = ' width="30%"' if i == 1 else ""
        w4 = ' width="24%"' if i == 1 else ""
        rows += [
            '<tr valign="top">',
            f'  <td{w}><code>{i:02d}</code></td>',
            f'  <td{w2}>',
            f'    <b>{esc(title)}</b><br>',
            f'    <sub>{esc(desc) or "<i>sin descripción</i>"}</sub>',
            '  </td>',
            f'  <td{w3}><sub><code>{esc(" · ".join(langs[:4]))}</code></sub></td>',
            f'  <td{w4} align="right"><sub>\n    {_links(spec, main, pair)}\n    </sub></td>',
            '</tr>',
        ]
    rows.append("</table>")
    return "\n".join(rows)


def projects_list(items: list[tuple[dict, dict, dict | None]]) -> str:
    """Version tipografica, para la plantilla zine."""
    out = []
    for i, (spec, main, pair) in enumerate(items, 1):
        title = spec.get("title") or main["name"].replace("_", " ").replace("-", " ")
        desc = main["description"] or (pair["description"] if pair else "") or ""
        url = main["url"]
        dots = "·" * max(3, 34 - len(title))
        out.append(f'  **N.º {i:02d}** {dots} [{esc(title)}]({url})  ')
        if desc:
            out.append(f'  {esc(desc)}  ')
        out.append(f'  <sub><code>{esc(" · ".join(main["langs"][:3]))}</code></sub>')
        out.append("")
    return "\n".join(out).rstrip()


def build(profile: dict) -> str:
    user = profile["username"]
    print(f"leyendo datos en vivo de {user}...")

    me = api(f"/users/{user}")
    items = []
    for spec in profile["projects"]:
        main = fetch_repo(user, spec["repo"])
        if not main:
            continue
        pair = fetch_repo(user, spec["pair"]) if spec.get("pair") else None
        items.append((spec, main, pair))
        n = spec.get("title") or main["name"]
        flag = "" if main["description"] else "   <- sin description en GitHub"
        print(f"  {n}{flag}")

    tpl_name = profile.get("template", "terminal")
    tpl = (ROOT / "templates" / f"{tpl_name}.md").read_text(encoding="utf-8")

    badges = " ".join(
        f'[![{c["label"]}](https://img.shields.io/badge/{c["label"]}-'
        f'{profile.get("badge_bg", "000000")}?style=for-the-badge'
        f'&logo={c["logo"]}&logoColor={profile.get("badge_fg", "white")})]({c["url"]})'
        for c in profile["contact"]
    )

    values = {
        "USER": user,
        "FULL_NAME": profile["full_name"],
        "TAGLINE": profile["tagline"],
        "WHOAMI": "\n".join(f"> {l}" for l in profile["whoami"]),
        "NOW": "\n".join(f"> {l}" for l in profile["now"]),
        "STACK": stack_block(profile["stack"]),
        "STACK_LIST": stack_list(profile["stack"]),
        "WHOAMI_TEXT": "  \n".join(profile["whoami"]),
        "NOW_TEXT": "  \n".join(profile["now"]),
        "PROJECTS_TABLE": projects_table(items),
        "PROJECTS_LIST": projects_list(items),
        "CONTACT": badges,
        "REPO_COUNT": str(me.get("public_repos", "")),
        "SINCE": me.get("created_at", "")[:7],
        "UPDATED": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    }
    for k, v in values.items():
        tpl = tpl.replace("{{" + k + "}}", v)

    left = [w for w in ("{{",) if w in tpl]
    if left:
        print("aviso: quedaron placeholders sin resolver en la plantilla", file=sys.stderr)
    return tpl


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", default=ROOT / "data/profile.json", type=Path)
    ap.add_argument("--out", default=ROOT / "README.md", type=Path)
    ap.add_argument("--check", action="store_true",
                    help="no escribe; sale 1 si el README quedaria distinto")
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
