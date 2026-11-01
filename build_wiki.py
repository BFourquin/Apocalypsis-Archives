#!/usr/bin/env python3
"""build_wiki.py - génère la copie statique du wiki (https://histoire.apocalypsis.org) dans wiki/.

Entrée : une sauvegarde du wiki (dossier Wiki-Backup : titles.json, html/, images/, images.json, logo.png).
Barre latérale réduite au logo (retour à la racine du site) et à quatre liens (SIDEBAR).
Sortie : wiki/*.html (une page par article, index.html = Accueil, pages.html = liste des pages) et wiki/images/.
Le dossier wiki/ est versionné ; build_site.py le recopie dans _site/wiki/.

Réécritures : liens internes -> pages locales ; vignettes -> images originales ; liens d'édition,
d'historique et pages spéciales retirés (le wiki n'est plus modifiable).

Bibliothèque standard uniquement. Usage : python build_wiki.py <dossier_sauvegarde> [--out wiki]
"""
import argparse
import html
import json
import os
import re
import shutil
import unicodedata
import urllib.parse
import urllib.request

HOST = "https://histoire.apocalypsis.org"
ATTR_RE = re.compile(r"""\b(href|src)\s*=\s*(["'])(.*?)\2""", re.I | re.S)
SRCSET_RE = re.compile(r"""\s+srcset\s*=\s*(["']).*?\1""", re.I | re.S)
SIDEBAR = [("Accueil", "Accueil"), ("Plan du wiki", "Aide:Plan du wiki"),
           ("Mécanismes du jeu", "Portail:Mécanismes"), ("Histoire universelle", "Portail:Histoire")]
NS_ORDER =["", "Fichier", "Catégorie", "Modèle", "Aide", "Commandant", "Utilisateur", "Discussion"]

PAGE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} - Wiki Apocalypsis</title>
<link rel="stylesheet" href="wiki.css">
</head>
<body>
<nav class="side">
<a href="../index.html" title="Retour aux archives"><img src="logo.png" alt="Archives Apocalypsis" width="135" height="135"></a>
<ul>
{nav}</ul>
</nav>
<main>
{heading}<div class="content">
{body}
</div>
</main>
</body>
</html>
"""

CSS = """body{margin:0;font:15px/1.5 sans-serif;color:#202122;background:#fff}
body{display:flex;align-items:flex-start}
.side{flex:none;width:11em;padding:1em .8em;font-size:.9em}.side img{display:block;margin-bottom:1em}
.side ul{list-style:none;margin:0;padding:0}.side li{margin:.4em 0}.side a{text-decoration:none}
main{flex:1;min-width:0;max-width:1100px;padding:1em 1.5em;border-left:1px solid #a7d7f9;min-height:100vh}
@media(max-width:700px){body{display:block}.side{width:auto}.side ul{display:flex;flex-wrap:wrap;gap:.2em 1.2em}main{border-left:0}}
h1{font:normal 1.8em Georgia,serif;border-bottom:1px solid #a2a9b1;margin:.2em 0 .6em}
.content{position:relative;overflow-x:auto}.content img{max-width:100%;height:auto}
a{color:#0645ad}a:visited{color:#0b0080}
table{max-width:100%}.pages{columns:3 15em}.pages li{break-inside:avoid}
"""


def safe_name(title):  # même règle que la sauvegarde (nom des fichiers html/)
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in title)[:120]


def ascii_slug(title):
    s = unicodedata.normalize("NFKD", title).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_") or "page"


def ns_of(title):
    return title.split(":", 1)[0] if ":" in title else ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("backup")
    ap.add_argument("--out", default="wiki")
    a = ap.parse_args()

    titles = json.load(open(os.path.join(a.backup, "titles.json"), encoding="utf-8"))
    shutil.rmtree(a.out, ignore_errors=True)
    os.makedirs(os.path.join(a.out, "images"))

    # images : chemin d'origine (/images/c/c6/Nom.png) -> fichier local ; les noms ne différant que par la casse
    # sont distingués (Windows ne les sépare pas dans la sauvegarde)
    img_map, used = {}, set()
    for i in json.load(open(os.path.join(a.backup, "images.json"), encoding="utf-8")):
        path = urllib.parse.unquote(urllib.parse.urlparse(i["url"]).path)
        local = i["name"]
        if local.lower() in used:
            stem, ext = os.path.splitext(local)
            local = f"{stem}__{i['sha1'][:6]}{ext}"
        used.add(local.lower())
        img_map[path] = local
        dst = os.path.join(a.out, "images", local)
        src = os.path.join(a.backup, "images", i["name"])
        if os.path.exists(src) and local == i["name"] and os.path.getsize(src) == i["size"]:
            shutil.copy(src, dst)
        else:
            urllib.request.urlretrieve(i["url"], dst)

    # pages : titre -> nom de fichier
    slugs, taken = {}, {"index", "pages", "wiki"}
    for pid, t in titles:
        s = "index" if t == "Accueil" else ascii_slug(t)
        if s.lower() in taken and t != "Accueil":
            s = f"{s}_{pid}"
        taken.add(s.lower())
        slugs[t] = s + ".html"
    norm = {t.replace("_", " "): s for t, s in slugs.items()}

    nav = "".join(f'<li><a href="{norm[t]}">{label}</a></li>\n' for label, t in SIDEBAR)
    shutil.copy(os.path.join(a.backup, "logo.png"), os.path.join(a.out, "logo.png"))

    def local_page(title):
        title = urllib.parse.unquote(title).replace("_", " ").strip()
        return norm.get(title)

    def rewrite(m):
        attr, q, val = m.group(1), m.group(2), html.unescape(m.group(3))
        v = val
        if v.startswith(HOST):
            v = v[len(HOST):]
        if attr.lower() == "src" or v.startswith("/images/"):
            p = urllib.parse.unquote(v.split("?")[0])
            mt = re.match(r"/images/thumb/(.+?)/[^/]+$", p)
            if mt:
                p = "/images/" + mt.group(1)
            if p in img_map:
                return f"{attr}={q}images/{urllib.parse.quote(img_map[p])}{q}"
            return f"{attr}={q}{HOST}{v}{q}" if v.startswith("/") else m.group(0)
        frag = ""
        if "#" in v:
            v, frag = v.split("#", 1)
            frag = "#" + frag
        if v.startswith("/index.php/"):
            page = local_page(v[len("/index.php/"):].split("?")[0])
            return f'{attr}={q}{page + frag if page else "pages.html"}{q}'
        if v.startswith("/index.php"):  # édition, historique, liens rouges... : sans objet dans une copie statique
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(v).query)
            page = local_page(qs["title"][0]) if "title" in qs and "action" not in qs else None
            return f'{attr}={q}{page + frag if page else "pages.html"}{q}'
        if v.startswith("#") or re.match(r"[a-z][a-z0-9+.-]*:", v, re.I):
            return m.group(0)
        if v.startswith("/"):
            return f"{attr}={q}{HOST}{v}{frag}{q}"
        return m.group(0)

    ordered = {}
    for pid, t in titles:
        src = os.path.join(a.backup, "html", f"{pid}_{safe_name(t)}.html")
        if not os.path.exists(src):
            continue
        body = open(src, encoding="utf-8").read()
        body = SRCSET_RE.sub("", body)
        body = ATTR_RE.sub(rewrite, body)
        heading = "" if t == "Accueil" else f"<h1>{html.escape(t)}</h1>\n"
        with open(os.path.join(a.out, slugs[t]), "w", encoding="utf-8") as fh:
            fh.write(PAGE.format(title=html.escape(t), heading=heading, body=body, nav=nav))
        ordered.setdefault(ns_of(t), []).append(t)

    parts = []
    for ns in sorted(ordered, key=lambda n: (NS_ORDER.index(n) if n in NS_ORDER else len(NS_ORDER), n)):
        items = "\n".join(f'<li><a href="{slugs[t]}">{html.escape(t)}</a></li>' for t in sorted(ordered[ns], key=str.casefold))
        parts.append(f"<h2>{html.escape(ns or 'Articles')} ({len(ordered[ns])})</h2>\n<ul class=\"pages\">\n{items}\n</ul>")
    with open(os.path.join(a.out, "pages.html"), "w", encoding="utf-8") as fh:
        fh.write(PAGE.format(title="Toutes les pages", heading="<h1>Toutes les pages</h1>\n", body="\n".join(parts), nav=nav))
    with open(os.path.join(a.out, "wiki.css"), "w", encoding="utf-8") as fh:
        fh.write(CSS)
    print(sum(len(v) for v in ordered.values()), "pages,", len(img_map), "images")


if __name__ == "__main__":
    main()
