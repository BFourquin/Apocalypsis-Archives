#!/usr/bin/env python3
"""scrape_descriptions.py - récupère les descriptions publiques des commandants (www.apocalypsis.org/showuser).

La page d'un commandant (https://www.apocalypsis.org/showuser?e_cap=<nom>) n'est visible qu'une fois connecté.
Le compte est passé par les variables d'environnement APOC_USER et APOC_PASS (jamais écrit dans le dépôt).
Le site impose une page d'attente (~8 s) après la connexion pour les comptes gratuits.

Noms interrogés : les commandants vus dans les archives Gamma 2 (archive_raw/json/commandants.json).
Résultat : archive_raw/json/descriptions.json (reprise possible : les noms déjà traités sont ignorés).

    {"<nom>": {"o": <galaxie d'origine>, "s": [[titre, html nettoyé], ...]}}

Seules les informations réellement saisies par le joueur sont conservées : les textes par défaut
(« Information indisponible ») ne sont pas stockés. Un commandant sans aucune information est noté {"o": N, "s": []}.
Les sections sont regroupées par rubrique (« Description publique », « Civilisation », « Gouvernement »)
avec le titre `Rubrique · Champ`. Le HTML des textes est assaini : balises de mise en forme uniquement, correctement imbriquées.

Bibliothèque standard uniquement. Usage : APOC_USER=... APOC_PASS=... python scrape_descriptions.py [--delay 1.0] [--limit N]
"""
import argparse
import html
import http.cookiejar
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser

BASE = "https://www.apocalypsis.org"
ROOT = os.path.dirname(os.path.abspath(__file__))
COMMANDANTS = os.path.join(ROOT, "archive_raw", "json", "commandants.json")
OUT = os.path.join(ROOT, "archive_raw", "json", "descriptions.json")
DEFAULT_TEXTS = {"information indisponible"}

ALLOWED = {"strong", "b", "em", "i", "u", "s", "del", "font", "a", "img", "ul", "ol", "li", "blockquote", "div", "span", "sub", "sup", "h1", "h2", "h3", "h4", "p", "center", "table", "tr", "td", "th", "tbody", "thead"}
VOID = {"br", "img", "hr"}
COLOR_RE = re.compile(r"^(#[0-9a-f]{3,8}|[a-z]{3,20}|rgb\([0-9 ,%.]+\))$", re.I)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)


class Sanitizer(HTMLParser):
    """Ne garde que des balises de mise en forme, avec une imbrication correcte (les balises mal fermées de la source sont corrigées)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out, self.stack = [], []

    def _attrs(self, tag, attrs):
        a = dict(attrs)
        keep = []
        if tag == "font":
            if a.get("color") and COLOR_RE.match(a["color"].strip()):
                keep.append(("color", a["color"].strip()))
            if a.get("size") and re.fullmatch(r"[+-]?\d", a["size"].strip()):
                keep.append(("size", a["size"].strip()))
        elif tag in ("div", "p", "td", "th") and a.get("align") in ("left", "center", "right", "justify"):
            keep.append(("align", a["align"]))
        elif tag == "a" and re.match(r"https?://", a.get("href") or "", re.I):
            keep.append(("href", a["href"]))
            keep.append(("target", "_blank"))
            keep.append(("rel", "nofollow noopener"))
        elif tag == "img" and re.match(r"https?://", a.get("src") or "", re.I):
            keep.append(("src", a["src"]))
            keep.append(("alt", ""))
            keep.append(("loading", "lazy"))
        return "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in keep)

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            self.out.append("<br>")
        elif tag == "img":
            at = self._attrs(tag, attrs)
            if "src=" in at:
                self.out.append(f"<img{at}>")
        elif tag in ALLOWED:
            self.out.append(f"<{tag}{self._attrs(tag, attrs)}>")
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in self.stack:
            while self.stack:
                t = self.stack.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data):
        self.out.append(linkify(html.escape(data, quote=False)) if "a" not in self.stack else html.escape(data, quote=False))

    def result(self):
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def linkify(text):
    def sub(m):
        url = m.group(0).rstrip(".,;:!?)")
        tail = m.group(0)[len(url):]
        return f'<a href="{url}" target="_blank" rel="nofollow noopener">{url}</a>{tail}'
    return URL_RE.sub(sub, text)


def clean(fragment):
    s = Sanitizer()
    s.feed(fragment)
    s.close()
    out = s.result()
    out = re.sub(r"(<div>\s*</div>\s*){2,}", "<div></div>", out)  # lignes vides consécutives
    out = re.sub(r"^(\s*<div>\s*</div>)+|(<div>\s*</div>\s*)+$", "", out.strip())
    return out.strip()


def plain(fragment):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", fragment))).strip()


def decode(b):
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace")  # les libellés statiques du site sont en ISO-8859-1


MARK = re.compile(r'<div class="(title|name)[^"]*">(.*?)</div>|<h4[^>]*>(.*?)</h4>|<div class="contents">', re.S)


def parse_profile(page):
    """-> {"o": galaxie d'origine ou None, "s": [[titre, html], ...]} ou None si la page n'est pas un profil."""
    i = page.find('<div class="right description">')
    if "showuser" not in page or '<div class="profile">' not in page:
        return None
    m = re.search(r"Galaxie d(?:'|&#039;)origine\s*:\s*</b>\s*(\d+)", page)
    origin = int(m.group(1)) if m else None
    seg = page[i:] if i >= 0 else ""
    ends = [e for e in (seg.find('<p align="center"><a href="/diplomatie/conversation/new'), seg.find('<form method="get" action="/showuser"')) if e > 0]
    if ends:
        seg = seg[: min(ends)]
    sections, rubrique, label = [], "", None
    marks = list(MARK.finditer(seg))
    for n, t in enumerate(marks):
        kind = t.group(1)
        nxt = marks[n + 1].start() if n + 1 < len(marks) else len(seg)
        if t.group(3) is not None:
            rubrique = plain(t.group(3))
        elif kind == "title":
            label = plain(t.group(2))
        elif kind == "name":
            name = plain(t.group(2)).split(":", 1)[-1].strip()
            if name and name.lower() not in DEFAULT_TEXTS:
                sections.append([f"{rubrique} · Nom", html.escape(name, quote=False)])
        elif t.group(0).startswith('<div class="contents">'):
            body = seg[t.end():nxt]
            body = re.sub(r"</div>\s*(</div>\s*)*$", "", body.rstrip())
            c = clean(body)
            txt = plain(c)
            filler = len(txt) <= 3 and not re.search(r"\w", txt)  # « . », « - », « / » : champ rempli pour rien
            if c and txt.lower() not in DEFAULT_TEXTS and not (filler and "<img" not in c):
                sections.append([f"{rubrique} · {label}" if rubrique else (label or ""), c])
    return {"o": origin, "s": sections}


class Session:
    def __init__(self, user, pwd, delay):
        self.user, self.pwd, self.delay = user, pwd, delay
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.opener.addheaders = [("User-Agent", "Apocalypsis-Archives/1.0 (archivage communautaire)")]
        self.last = 0.0

    def _open(self, url, data=None):
        wait = self.last + self.delay - time.time()
        if wait > 0:
            time.sleep(wait)
        try:
            with self.opener.open(url, data, timeout=90) as r:
                return decode(r.read())
        finally:
            self.last = time.time()

    def login(self):
        self._open(BASE + "/")
        self._open(BASE + "/connexion", urllib.parse.urlencode({"e_nom": self.user, "d_mdp": self.pwd, "ok": "Entrer"}).encode())
        time.sleep(10)  # page d'attente imposée aux comptes gratuits (bouton « Jouer » activé après 8 s)
        self._open(BASE + "/strategie?button=Jouer")

    def profile(self, name):
        url = f"{BASE}/showuser?e_cap={urllib.parse.quote(name, safe='')}"
        for attempt in range(3):
            try:
                page = self._open(url)
            except urllib.error.HTTPError as e:
                if e.code in (404, 500):  # nom inconnu : le site répond par une erreur serveur
                    return ""
                print(f"  ! {name}: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
                continue
            except (urllib.error.URLError, OSError) as e:
                print(f"  ! {name}: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
                continue
            if "Apocalypsis needs you" in page or 'name="e_nom"' in page:  # session perdue ou page d'attente
                print("  session expirée, nouvelle connexion", file=sys.stderr)
                self.login()
                continue
            return page
        return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delay", type=float, default=1.0, help="secondes entre deux requêtes")
    ap.add_argument("--limit", type=int, default=0, help="nombre maximal de noms à traiter (essais)")
    ap.add_argument("--part", default="gamma2", help="préfixe des galaxies dont on prend les noms")
    ap.add_argument("--names", nargs="*", help="noms explicites (essais), au lieu de la liste des archives")
    args = ap.parse_args()
    user, pwd = os.environ.get("APOC_USER"), os.environ.get("APOC_PASS")
    if not user or not pwd:
        sys.exit("Définir APOC_USER et APOC_PASS.")
    if args.names:
        names = args.names
    else:
        with open(COMMANDANTS, encoding="utf-8") as fh:
            cmd = json.load(fh)["commandants"]
        names = [k for k, v in cmd.items() if k and any(g.startswith(args.part) for g in v["galaxies"])]
    done = {}
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as fh:
            done = json.load(fh)
    todo = [n for n in names if n not in done]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(names)} noms, {len(todo)} à traiter")
    s = Session(user, pwd, args.delay)
    s.login()
    t0, found, missing = time.time(), 0, 0
    for k, name in enumerate(todo, 1):
        page = s.profile(name)
        if page == "":
            done[name] = {"o": None, "s": []}  # nom inconnu du site : rien à afficher
            missing += 1
            continue
        res = parse_profile(page) if page else None
        if res is None:
            missing += 1  # page illisible : non mémorisé, sera retenté à la prochaine exécution
        else:
            done[name] = res
            found += bool(res["s"])
        if k % 50 == 0 or k == len(todo):
            with open(OUT, "w", encoding="utf-8") as fh:
                json.dump(done, fh, ensure_ascii=False, separators=(",", ":"))
            print(f"{k}/{len(todo)} · {found} avec description · {missing} introuvables · {time.time() - t0:.0f}s", flush=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(done, fh, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
