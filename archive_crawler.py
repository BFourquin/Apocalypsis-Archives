#!/usr/bin/env python3
"""
archive_crawler.py - capture brute (octet pour octet) des archives du forum d'Apocalypsis.

Bibliothèque standard uniquement (Python 3.9+). Aucune installation nécessaire.

Principes
---------
* On enregistre les octets reçus, sans les décoder ni les modifier (les pages Beta
  sont en iso-8859-1, les pages Gamma en UTF-8 : le décodage se fait au parsing).
* Tout est reprenable : la file d'attente, le manifeste et la dernière page consultée
  vivent dans SQLite (<sortie>/manifest.sqlite). Chaque page est enregistrée avec les
  liens qu'elle contient dans une seule transaction : une coupure (site, réseau, Ctrl+C,
  fenêtre fermée) ne perd rien. Il suffit de relancer la même commande pour repartir
  de la page où l'on s'était arrêté.
* Poli : un seul fil, délai entre requêtes, respect de robots.txt, User-Agent clair,
  nouvelle tentative avec temporisation, arrêt propre si le serveur se fâche (429/503).
* Les liens sont suivis, jamais devinés (le sens du sous-dossier {n} des URL Beta
  est inconnu).

Phases
------
  inventory : parcourt seulement les pages « structure » (index, pages de galaxies,
              listes de forums) pour mesurer le volume réel. Les pages de topics et
              les ressources sont notées dans la file mais pas téléchargées.
  full      : télécharge tout (topics, CSS/JS, images, avatars...).

Exemples
--------
  python archive_crawler.py                                   # sans argument : full, html + json
  python archive_crawler.py inventory --out archive
  python archive_crawler.py report    --out archive
  python archive_crawler.py full      --out archive --delay 0.25
  python archive_crawler.py json      --out archive   # (re)génère le JSON depuis la capture brute
  python archive_crawler.py full      --out archive --only gamma2/galaxie1   # essai ciblé
"""
from __future__ import annotations

import argparse
import hashlib
import html as html_lib
import json
import os
import re
import signal
import sqlite3
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from collections import defaultdict
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit, quote, unquote

DEFAULT_GAMMA = "https://www.apocalypsis.org"
DEFAULT_BETA = "https://archivesbeta.apocalypsis.org"
USER_AGENT = "ApoArchiveBot/1.0 (archivage non commercial du forum ; contact: benoit.fourquin@gmail.com)"

# Types de pages
STRUCT, TOPIC, ASSET = "struct", "topic", "asset"

RE_GAMMA_TOPIC = re.compile(r"^/archives/[^/]+/[^/]+/forums/\d+/topics/\d+/page\d+$")
RE_GAMMA_ARCHIVES = re.compile(r"^/archives(/|$)")
RE_BETA_TOPIC = re.compile(r"viewtopic-\d+-\d+\.html$")
RE_ASSET_EXT = re.compile(
    r"\.(css|js|gif|jpe?g|png|ico|svg|webp|bmp|tiff?|woff2?|ttf|otf|eot|swf|mp3|ogg|wav|mp4|webm|pdf|zip|txt|xml|json)$", re.I)
# liens à ne jamais suivre
RE_SKIP = re.compile(r"(top_view\.php|/warn/|/logout|/login|/admin|mailto:|javascript:|tel:)", re.I)

HREF_RE = re.compile(r"""(?:href|src)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""", re.I)
CSS_URL_RE = re.compile(r"""url\(\s*['"]?([^'")\s]+)['"]?\s*\)""", re.I)
CSS_IMPORT_RE = re.compile(r"""@import\s+(?:url\(\s*)?['"]?([^'")\s;]+)""", re.I)
# ressources chargées par la page (src=..., <link href=...>) : conservées quelle que soit l'extension
ASSET_ATTR_RE = re.compile(
    r"""<(?:img|script|source|embed|audio|video|input|link)\b[^>]*?\b(?:src|href)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>"']+))""",
    re.I)


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url)
    p = urlsplit(url)
    path = re.sub(r"/{2,}", "/", p.path) or "/"
    return urlunsplit((p.scheme, p.netloc, path, p.query, ""))


class Scope:
    """Décide ce qui est dans le périmètre et de quel type."""

    def __init__(self, gamma_base: str, beta_base: str, only: list[str] | None = None):
        self.gamma = urlsplit(gamma_base)
        self.beta = urlsplit(beta_base)
        self.only = [o.strip("/").lower() for o in (only or [])]

    def _host_kind(self, parts):
        if parts.netloc == self.gamma.netloc:
            return "gamma"
        if parts.netloc == self.beta.netloc:
            return "beta"
        return None

    def normalize(self, url: str) -> str:
        return normalize_url(url)

    def classify(self, url: str, asset_hint: bool = False):
        """Retourne STRUCT/TOPIC/ASSET, ou None si hors périmètre. `asset_hint` : le lien est une
        ressource chargée par une page ou une CSS (src, <link>, url()) : toujours conservée."""
        p = urlsplit(url)
        if p.scheme not in ("http", "https"):
            return None
        host = self._host_kind(p)
        if host is None:
            return None  # forum.apocalypsis.org, CDN externes, etc. : exclus
        if RE_SKIP.search(url):
            return None
        if asset_hint:
            return ASSET
        path = unquote(p.path)
        if self.only and not self._matches_only(host, path):
            # on garde quand même les ressources partagées et les index
            if not (RE_ASSET_EXT.search(path) or path.startswith(("/avatars/", "/images/"))):
                if not self._is_ancestor(host, path):
                    return None
        if RE_ASSET_EXT.search(path) or path.startswith(("/avatars/", "/images/", "/css/", "/js/")):
            return ASSET
        if host == "gamma":
            if not RE_GAMMA_ARCHIVES.match(path):
                return None
            return TOPIC if RE_GAMMA_TOPIC.match(path) else STRUCT
        # beta
        return TOPIC if RE_BETA_TOPIC.search(path) else STRUCT

    def _key(self, host, path):
        """Clé « partie/galaxie » comparable à --only (ex. gamma2/galaxie1)."""
        low = path.lower()
        m = re.match(r"^/archives/([^/]+)/([^/]+)", low)
        if host == "gamma" and m:
            return f"{m.group(1)}/{m.group(2)}"
        m = re.match(r"^/([^/]+)/(galaxie_?(\d+))", low)
        if host == "beta" and m:
            return f"{m.group(1)}/galaxie{m.group(3)}"
        return None

    def _matches_only(self, host, path):
        k = self._key(host, path)
        return k is not None and any(k == o or k.startswith(o + "/") for o in self.only)

    def _is_ancestor(self, host, path):
        # index des archives, page de partie... pour pouvoir descendre jusqu'à la cible
        low = path.lower().rstrip("/")
        if host == "gamma":
            return low in ("/archives",) or re.match(r"^/archives/[^/]+$", low) is not None
        return low in ("", "/index.html") or re.match(r"^/[^/]+$", low) is not None


# --------------------------------------------------------------------------
# Stockage
# --------------------------------------------------------------------------
SCHEMA = """
CREATE TABLE IF NOT EXISTS urls (
  url TEXT PRIMARY KEY,
  kind TEXT NOT NULL,
  status INTEGER,            -- code HTTP, NULL = à faire, -1 = erreur réseau
  content_type TEXT,
  final_url TEXT,
  path TEXT,                 -- chemin relatif du fichier brut
  size INTEGER,
  sha256 TEXT,
  fetched_at TEXT,
  error TEXT,
  found_on TEXT,
  tries INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS urls_todo ON urls(status, kind);
CREATE TABLE IF NOT EXISTS state (
  key TEXT PRIMARY KEY,      -- last_url, last_at, current_url
  value TEXT
);
"""


def local_path(url: str) -> str:
    """URL -> chemin de fichier relatif, sans collision et sans sortir du dossier."""
    p = urlsplit(url)
    host = p.netloc.replace(":", "_")
    path = unquote(p.path)
    if path.endswith("/") or path == "":
        path += "index.html"
    parts = [seg for seg in path.split("/") if seg not in ("", ".", "..")]
    name = parts[-1] if parts else "index.html"
    if p.query:
        h = hashlib.sha1(p.query.encode()).hexdigest()[:10]
        base, dot, ext = name.rpartition(".")
        name = f"{base}__q{h}.{ext}" if dot else f"{name}__q{h}"
    safe = [re.sub(r'[<>:"\\|?*\x00-\x1f]', "_", s) for s in parts[:-1] + [name]]
    # une page « /a/b » et une page « /a/b/c » ne doivent pas entrer en conflit
    return "/".join([host] + safe) + (".html" if "." not in name else "")


class Store:
    def __init__(self, out: str, keep_html: bool = True):
        self.out = out
        self.keep_html = keep_html
        self.raw = os.path.join(out, "raw")
        os.makedirs(self.raw, exist_ok=True)
        self.db = sqlite3.connect(os.path.join(out, "manifest.sqlite"))
        self.db.executescript(SCHEMA)
        self.db.commit()

    def add(self, url, kind, found_on):
        self.db.execute(
            "INSERT OR IGNORE INTO urls(url, kind, found_on) VALUES (?,?,?)", (url, kind, found_on)
        )

    def next_todo(self, kinds, assets_first=False):
        q = ",".join("?" * len(kinds))
        # la page en cours lors de la coupure précédente passe en premier
        cur = self.get_state("current_url")
        if cur:
            r = self.db.execute(
                f"SELECT url, kind, tries FROM urls WHERE url=? AND status IS NULL AND kind IN ({q})",
                (cur, *kinds),
            ).fetchone()
            if r:
                return r
        # les pages structure d'abord, puis topics, puis ressources (ressources avant topics si assets_first) ; ordre stable
        rang = "WHEN 'struct' THEN 0 WHEN 'topic' THEN 2 ELSE 1" if assets_first else "WHEN 'struct' THEN 0 WHEN 'topic' THEN 1 ELSE 2"
        return self.db.execute(
            f"""SELECT url, kind, tries FROM urls
                WHERE status IS NULL AND kind IN ({q})
                ORDER BY CASE kind {rang} END, rowid
                LIMIT 1""",
            kinds,
        ).fetchone()

    def save(self, url, status, ctype, final_url, body, error=None, kind=ASSET):
        path = size = sha = None
        # le format « html » ne concerne que les pages ; les ressources (avatars, CSS, images...) sont
        # toujours conservées, sans elles ni le JSON ni la copie brute ne peuvent être réaffichés
        if body is not None and status == 200 and (self.keep_html or kind == ASSET):
            rel = local_path(url)
            full = os.path.join(self.raw, rel)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            # un fichier ne peut pas être à la fois dossier et page
            if os.path.isdir(full):
                full = os.path.join(full, "index.html")
                rel = os.path.relpath(full, self.raw)
            tmp = full + ".part"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, full)
            path, size, sha = rel.replace(os.sep, "/"), len(body), hashlib.sha256(body).hexdigest()
        self.db.execute(
            """UPDATE urls SET status=?, content_type=?, final_url=?, path=?, size=?, sha256=?,
               fetched_at=?, error=?, tries=tries+1 WHERE url=?""",
            (status, ctype, final_url, path, size, sha, time.strftime("%Y-%m-%dT%H:%M:%S"), error, url),
        )
        self.set_state("last_url", url)
        self.set_state("last_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
        # pas de commit ici : l'appelant valide la page et ses liens d'un seul coup

    def set_state(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO state(key, value) VALUES (?,?)", (key, value))

    def get_state(self, key):
        r = self.db.execute("SELECT value FROM state WHERE key=?", (key,)).fetchone()
        return r[0] if r else None

    def mark_skipped(self, url, reason):
        self.db.execute("UPDATE urls SET status=-2, error=? WHERE url=?", (reason, url))

    def bump_retry(self, url, error):
        self.db.execute("UPDATE urls SET tries=tries+1, error=? WHERE url=?", (error, url))
        self.db.commit()


# --------------------------------------------------------------------------
# Réseau
# --------------------------------------------------------------------------
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


class Fetcher:
    def __init__(self, delay: float, timeout: float, scope: Scope):
        self.delay, self.timeout, self.scope = delay, timeout, scope
        self.last = 0.0
        self.opener = urllib.request.build_opener(NoRedirect)
        self.robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _wait(self):
        dt = time.monotonic() - self.last
        if dt < self.delay:
            time.sleep(self.delay - dt)
        self.last = time.monotonic()

    def allowed(self, url: str) -> bool:
        p = urlsplit(url)
        origin = f"{p.scheme}://{p.netloc}"
        if origin not in self.robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait()
                req = urllib.request.Request(origin + "/robots.txt", headers={"User-Agent": USER_AGENT})
                with self.opener.open(req, timeout=self.timeout) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
                self.robots[origin] = rp
            except urllib.error.HTTPError as e:
                # 404 & co : pas de restriction. 401/403 : on considère tout interdit.
                if e.code in (401, 403):
                    rp.parse(["User-agent: *", "Disallow: /"])
                    self.robots[origin] = rp
                else:
                    self.robots[origin] = None
            except Exception:
                self.robots[origin] = None
        rp = self.robots[origin]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str, max_redirects: int = 5):
        """Retourne (status, content_type, final_url, body). Suit les redirections à la main
        pour pouvoir refuser celles qui sortent du périmètre."""
        cur = url
        for _ in range(max_redirects + 1):
            self._wait()
            req = urllib.request.Request(cur, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"})
            try:
                with self.opener.open(req, timeout=self.timeout) as r:
                    return r.status, r.headers.get("Content-Type"), cur, r.read()
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    loc = e.headers.get("Location")
                    if not loc:
                        return e.code, None, cur, None
                    nxt = self.scope.normalize(urljoin(cur, loc))
                    if self.scope.classify(nxt) is None:
                        return e.code, e.headers.get("Content-Type"), nxt, None  # hors périmètre
                    cur = nxt
                    continue
                return e.code, e.headers.get("Content-Type"), cur, None
        return 310, None, cur, None  # trop de redirections


# --------------------------------------------------------------------------
# Extraction de liens
# --------------------------------------------------------------------------
def charset_of(ctype: str | None, head: bytes) -> str:
    m = re.search(r"charset=([\w-]+)", ctype or "", re.I) or re.search(
        rb"charset=['\"]?([\w-]+)", head[:2048], re.I
    )
    if m:
        v = m.group(1)
        return v.decode() if isinstance(v, bytes) else v
    return "utf-8"


def extract_links(body: bytes, ctype: str | None, base: str):
    cs = charset_of(ctype, body)
    try:
        text = body.decode(cs, "replace")
    except LookupError:
        text = body.decode("latin-1")
    out = set()
    if ctype and "css" in ctype.lower() or base.lower().split("?")[0].endswith(".css"):
        for m in CSS_URL_RE.finditer(text):
            if not m.group(1).startswith("data:"):
                out.add(urljoin(base, m.group(1)))
        for m in CSS_IMPORT_RE.finditer(text):
            out.add(urljoin(base, m.group(1)))
        return out
    if not (ctype and "html" in ctype.lower()):
        return out
    for m in HREF_RE.finditer(text):
        raw = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        # "(" : faux lien tiré d'un script (ex. `ga.src = ('https:' == …` de Google Analytics)
        if not raw or raw.startswith(("#", "javascript:", "mailto:", "data:", "(")):
            continue
        out.add(urljoin(base, raw.replace("&amp;", "&")))
    return out


# --------------------------------------------------------------------------
# Archive JSON : seulement l'information utile, sans le gabarit répété
# --------------------------------------------------------------------------
# Une archive HTML brute (source de vérité visuelle) et une archive JSON sont produites
# ensemble. Le JSON écarte tout ce qui se répète d'une page à l'autre (en-têtes, CSS/JS,
# fil d'Ariane, libellés des critères, mise en page) : il reste les titres, auteurs, dates,
# scores, sondages et textes. Un fichier par topic (pages fusionnées) et un par forum
# (listes de sujets fusionnées) : json/<partie>/<galaxie>/forums/<forum>/...
NEG_CODES = ("orthographe", "presentation", "hors_sujet", "hors_roleplay", "insultant")
POS_CODES = ("efforts", "adapte", "remarquable", "humour", "roleplay")  # libellés d'origine (2.9)

RE_J_GAMMA_TOPIC = re.compile(r"/archives/([^/]+)/([^/]+)/forums/(\d+)/topics/(\d+)/page(\d+)$")
RE_J_GAMMA_LIST = re.compile(r"/archives/([^/]+)/([^/]+)/forums/(\d+)/page(\d+)$")
RE_J_BETA_TOPIC = re.compile(r"^/([^/]+)/galaxie_?(\d+)/forums_galactiques/(\d+)/(?:\d+/)?viewtopic-(\d+)-(\d+)\.html$")
RE_TAG = re.compile(r"<[^>]+>")
RE_DATE = re.compile(r"(\d\d)/(\d\d)(?:/(\d{4}))? ETU (\d\d:\d\d)")
RE_J_ROW = re.compile(r'<tr>\s*<td class="wrap_allowed">(.*?)</tr>', re.S)
RE_J_SUPPRIME = re.compile(r'<div class="red">\s*<img[^>]*trashcan_full[^>]*>\s*Ce message a été supprimé durant la partie\.\s*</div>\s*(?:<hr\s*/?>)?')


def _txt(s: str) -> str:
    return re.sub(r"\s+", " ", html_lib.unescape(RE_TAG.sub("", s))).strip()


def _decode(body: bytes, ctype: str | None) -> str:
    cs = charset_of(ctype, body).lower()
    if cs in ("iso-8859-1", "latin-1", "latin1"):
        cs = "cp1252"  # comme les navigateurs
    try:
        return body.decode(cs, "replace")
    except LookupError:
        return body.decode("latin-1")


def _date(raw: str | None):
    """-> (date ISO ou None, « JJ/MM HH:MM » si l'année est absente). Gamma : année réelle = année ETU + 1000 (1018 -> 2018)."""
    m = RE_DATE.search(raw or "")
    if not m:
        return None, None
    d, mo, y, hm = m.groups()
    if y:
        return f"{int(y) + 1000:04d}-{mo}-{d} {hm}", None
    return None, f"{d}/{mo} {hm}"


def _author(raw: str, gamma: bool):
    name = _txt(raw)
    m = re.match(r"^(\S+\.)\s+(.+)$", name) if gamma else None
    return (m.group(1)[0].upper() + m.group(1)[1:], m.group(2)) if m else (None, name)


def _body(html: str):
    liens = [h.replace("&amp;", "&") for h in re.findall(r'<a\b[^>]*?href\s*=\s*"([^"]*)"', html, re.I)]
    images = re.findall(r'<img\b[^>]*?src\s*=\s*"([^"]*)"', html, re.I)
    s = re.sub(r"<br\s*/?>\r?\n?", "\n", html, flags=re.I)
    s = re.sub(r'<div class="post_line">', "\n", s)
    s = html_lib.unescape(RE_TAG.sub("", s))
    s = re.sub(r"[ \t]+\n", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s, [h for h in liens if h not in s], images  # un lien déjà lisible dans le texte n'est pas répété


def _parse_poll(text: str):
    m = re.search(r'<div class="poll">(.*?)</div>', text, re.S)
    if m:
        block, fin = m.group(1), re.search(r"pris fin le(?:&nbsp;|\s)*:\s*([^<]+)", text[m.start():])
        q = re.search(r"<h2>(.*?)</h2>", block, re.S)
        question = q.group(1) if q else ""
    else:
        m = re.search(r"<h3>Vote(?:&nbsp;|\s)*:\s*(.*?)</h3>\s*(<table.*?</table>)", text, re.S)
        if not m:
            return None
        block, fin, question = m.group(2), None, m.group(1)
    options = [{"texte": _txt(t), "votes": int(v)}
               for t, v in re.findall(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(\d+)</td>", block, re.S)]
    tot = re.search(r"Total(?:&nbsp;|\s)*:\s*(\d+)", block)
    poll = {"question": _txt(question), "options": options}
    if tot:
        poll["total"] = int(tot.group(1))
    if fin:
        poll["fin"], _ = _date(fin.group(1))
        poll["fin"] = poll["fin"] or _txt(fin.group(1))
    return poll


def _cut_post(right: str) -> str:
    """Le message finit au dernier `</td></tr>` (les premiers appartiennent au tableau des critères)."""
    ends = list(re.finditer(r"</td>\s*</tr>", right))
    return right[:ends[-1].start()] if ends else right


def _post(left: str, right: str, gamma: bool, base: str):
    right = _cut_post(right)
    p = {}
    grade, name = _author(re.split(r"<br", left, 1, flags=re.I)[0], gamma)
    p["auteur"] = name
    if grade:
        p["grade"] = grade
    m = re.search(r"(?:Cauchemards provoqu\S+|Respect diplomatique)(?:&nbsp;|\s)*:\s*(\d+)", left)
    if m:
        p["compteur"] = int(m.group(1))
    m = re.search(r"""<img\b[^>]*?src\s*=\s*["']([^"']*/avatars/[^"']+)["']""", left, re.I)
    if m:
        # chemin du fichier local sous raw/ (les avatars Beta sont propres à chaque galaxie)
        p["avatar"] = local_path(normalize_url(urljoin(base, html_lib.unescape(m.group(1)))))
    iso, sans_annee = _date(left)
    if iso:
        p["date"] = iso
    elif sans_annee:
        p["date_sans_annee"] = sans_annee
    n = left.count("registered.gif")
    if n:
        p["soutien"] = n
    head = right.split('id="cal')[0] if 'id="cal' in right else right[:right.find("</div>")]
    if "Message édité" in head or "Message &eacute;dit&eacute;" in head:
        p["edite"] = True
    m = re.search(r"Score(?:&nbsp;|\s)*:\s*(-?\d+)", head)
    if m:
        p["score"] = int(m.group(1))
    m = re.search(r"id=\"cal(\d+)\"", right)
    if m:
        p["id"] = int(m.group(1))
    neg = re.search(r'<td class="vote">(.*?)</td>', right, re.S)
    pos = re.search(r'<td class="vote2">(.*?)</td>', right, re.S)
    if neg:
        v = re.findall(r"(\d+)\s*:", _txt(RE_TAG.sub(" ", neg.group(1))))
        crit = {c: int(x) for c, x in zip(NEG_CODES, v) if int(x)}
        if crit:
            p["negatifs"] = crit
    if pos:
        v = re.findall(r":\s*(\d+)", _txt(RE_TAG.sub(" ", pos.group(1))))
        crit = {c: int(x) for c, x in zip(POS_CODES, v) if int(x)}
        if crit:
            p["positifs"] = crit
    m = re.search(r"</table>[^<]*</div>\s*</div>", right) or re.search(r'<div class="posthead">\s*</div>', right)
    corps = right[m.end():] if m else right
    corps, n = RE_J_SUPPRIME.subn("", corps)
    if n:
        p["supprime"] = True  # bannière « supprimé durant la partie » : le message est conservé, la bannière retirée du texte
    text, liens, images = _body(corps)
    p["texte"] = text
    if liens:
        p["liens"] = liens
    if images:
        p["images"] = images
    return p


def parse_topic_page(html: str, partie: str, galaxie: str, forum: str, topic: str, page: int, gamma: bool,
                     base: str = "http://localhost/"):
    h2 = re.search(r"<h2>(.*?)</h2>", html, re.S)
    fm = re.search(r'forums/\d+/page\d+">(.*?)</a>' if gamma else r'viewforum-\d+-\d+\.html">(.*?)</a>', html, re.S)
    posts = []
    if gamma:
        for chunk in re.split(r'<td class="post_left">', html)[1:]:
            left, _, right = chunk.partition('<td class="post_right">')
            posts.append(_post(left, right, True, base))
    else:
        for chunk in re.split(r'<tr>\s*<td class="posts">', html)[1:]:
            left, _, right = chunk.partition('</td><td class="posts">')
            posts.append(_post(left, right, False, base))
    nums = [int(n) for n in re.findall(r"/page(\d+)\"" if gamma else r"viewtopic-\d+-(\d+)\.html", html)]
    meta = {"partie": partie, "galaxie": galaxie, "forum": int(forum), "topic": int(topic),
            "titre": _txt(h2.group(1)) if h2 else "", "forum_nom": _txt(fm.group(1)) if fm else "",
            "pages": max(nums + [page])}
    return meta, _parse_poll(html), posts


def parse_list_page(html: str, partie: str, galaxie: str, forum: str, page: int):
    h2 = re.search(r"<h2>(.*?)</h2>", html, re.S)
    h3 = re.search(r"<h3>(.*?)</h3>", html, re.S)
    topics = {}
    for row in RE_J_ROW.findall(html):
        t = re.search(r'/topics/(\d+)/page1"[^>]*>(.*?)</a>', row, re.S)
        if not t:
            continue
        d = {"titre": _txt(re.sub(r'<font color="#FFC525">\[Vote\]</font>', "", t.group(2)))}
        if "[Vote]" in t.group(2):
            d["sondage"] = True
        cells = re.findall(r'<td class="title">(.*?)</td>', row, re.S)
        if len(cells) >= 3:
            grade, name = _author(cells[0], True)
            d["auteur"] = (grade + " " if grade else "") + name
            r = re.match(r"\s*(\d+)(?:\s*\(dont\s+(\d+))?", _txt(cells[1]))
            if r:
                d["reponses"] = int(r.group(1))
                if r.group(2):
                    d["supprimes"] = int(r.group(2))
            last = re.split(r"<br\s*/?>", cells[2], 1)
            d["dernier"], _ = _date(last[0])
            if len(last) > 1:
                grade, name = _author(last[1], True)
                d["dernier_auteur"] = (grade + " " if grade else "") + name
        topics[t.group(1)] = d
    meta = {"partie": partie, "galaxie": galaxie, "forum": int(forum), "nom": _txt(h2.group(1)) if h2 else ""}
    if h3:
        meta["sous_titre"] = _txt(h3.group(1))
    return meta, topics


def _json_write(path: str, doc) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def _json_merge(path: str, update) -> None:
    doc = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            doc = json.load(f)
    update(doc)
    _json_write(path, doc)


def write_json(out: str, url: str, ctype: str | None, body: bytes) -> str | None:
    """Fusionne la page dans l'archive JSON ; retourne le fichier écrit, ou None si la page n'est pas gérée
    (index, listes Beta, ressources). Idempotent : rejouer une page remplace ses données."""
    p = urlsplit(url)
    if not (ctype and "html" in ctype.lower()):
        return None
    path = unquote(p.path)
    root = os.path.join(out, "json")
    m = RE_J_GAMMA_TOPIC.search(path)
    gamma = bool(m)
    if gamma:
        partie, gal, forum, topic, page = m.group(1), m.group(2), m.group(3), m.group(4), int(m.group(5))
    else:
        m = RE_J_BETA_TOPIC.match(path)
        if m:
            partie, gal, forum, topic, page = m.group(1), "galaxie" + m.group(2), m.group(3), m.group(4), int(m.group(5))
    if m:
        meta, poll, posts = parse_topic_page(_decode(body, ctype), partie, gal, forum, topic, page, gamma, url)
        target = os.path.join(root, partie, gal, "forums", forum, "topics", topic + ".json")

        def upd(doc):
            if page == 1 or "titre" not in doc:
                doc.update(meta)
            else:
                doc["pages"] = max(doc.get("pages", 1), meta["pages"])
            if poll:
                doc["sondage"] = poll
            doc.setdefault("messages", {})[str(page)] = posts
        _json_merge(target, upd)
        return target
    m = RE_J_GAMMA_LIST.search(path)
    if m:
        partie, gal, forum, page = m.group(1), m.group(2), m.group(3), int(m.group(4))
        meta, topics = parse_list_page(_decode(body, ctype), partie, gal, forum, page)
        target = os.path.join(root, partie, gal, "forums", forum, "sujets.json")

        def upd_list(doc):
            doc.update(meta)
            doc.setdefault("sujets", {}).update(topics)
        _json_merge(target, upd_list)
        return target
    return None


def build_commandants(out: str) -> str:
    """Répertoire des commandants, construit depuis les topics de l'archive JSON (aucune requête).
    Un commandant = un pseudo (les identifiants de joueurs ne figurent pas dans les pages).
    Écrit json/commandants.json. Créateur d'un sujet = auteur du premier message de sa page 1."""
    root = os.path.join(out, "json")
    cmds: dict[str, dict] = {}
    for dirpath, _, files in os.walk(root):
        if os.path.basename(dirpath) != "topics":
            continue
        for fn in sorted(files):
            if not fn.endswith(".json"):
                continue
            with open(os.path.join(dirpath, fn), encoding="utf-8") as f:
                t = json.load(f)
            if "titre" not in t:
                continue
            gal = f"{t['partie']}/{t['galaxie']}"
            ref = f"{gal}/{t['forum']}/{t['topic']}"
            counts: dict[str, int] = {}
            for page in t.get("messages", {}).values():
                for p in page:
                    name = p["auteur"]
                    c = cmds.setdefault(name, {"respect_max": 0, "respect_par_galaxie": {}, "_last": {}, "_avatars": {},
                                               "galaxies": set(), "sujets_crees": [], "sujets_participes": []})
                    counts[name] = counts.get(name, 0) + 1
                    c["galaxies"].add(gal)
                    if "avatar" in p:
                        c["_avatars"].setdefault(gal, {}).setdefault(p["avatar"], p.get("id", -1))
                    if "compteur" in p:
                        c["respect_max"] = max(c["respect_max"], p["compteur"])
                        # valeur au dernier message connu de la galaxie (identifiants croissants)
                        if p.get("id", -1) >= c["_last"].get(gal, -2):
                            c["_last"][gal] = p.get("id", -1)
                            c["respect_par_galaxie"][gal] = p["compteur"]
            first = t.get("messages", {}).get("1")
            if first:
                cmds[first[0]["auteur"]]["sujets_crees"].append({"ref": ref, "titre": t["titre"]})
            for name, n in counts.items():
                cmds[name]["sujets_participes"].append({"ref": ref, "titre": t["titre"], "messages": n})
    result = {}
    for name in sorted(cmds, key=str.lower):
        c = cmds[name]
        result[name] = {"respect_max": c["respect_max"],
                        "respect_par_galaxie": dict(sorted(c["respect_par_galaxie"].items())),
                        "galaxies": sorted(c["galaxies"]),
                        # fichiers sous raw/, dans l'ordre de première utilisation (identifiant de message)
                        "avatars_par_galaxie": {g: sorted(a, key=a.get) for g, a in sorted(c["_avatars"].items())},
                        "sujets_crees": c["sujets_crees"],
                        "sujets_participes": c["sujets_participes"]}
    target = os.path.join(root, "commandants.json")
    _json_write(target, {"commandants": result})
    return target


def build_json(args):
    """Régénère l'archive JSON depuis la capture brute déjà faite (aucune requête réseau)."""
    store = Store(args.out)
    n = bad = 0
    rows = store.db.execute(
        "SELECT url, content_type, path FROM urls WHERE status=200 AND path IS NOT NULL AND kind IN ('topic','struct')"
    ).fetchall()
    for url, ctype, path in rows:
        try:
            with open(os.path.join(store.raw, path), "rb") as f:
                n += bool(write_json(args.out, url, ctype, f.read()))
        except Exception as e:
            bad += 1
            print(f"  ! JSON impossible pour {url} : {type(e).__name__}: {e}", file=sys.stderr)
    print(f"JSON : {n} pages intégrées, {bad} erreurs, dossier {os.path.join(args.out, 'json')}")
    print(f"Commandants : {build_commandants(args.out)}")


def extract_asset_links(body: bytes, ctype: str | None, base: str):
    """Ressources chargées par une page HTML (img/script/link...), même sans extension reconnaissable."""
    if not (ctype and "html" in ctype.lower()):
        return set()
    text = _decode(body, ctype)
    out = set()
    for m in ASSET_ATTR_RE.finditer(text):
        raw = (m.group(1) or m.group(2) or m.group(3) or "").strip()
        if raw and not raw.startswith(("#", "javascript:", "mailto:", "data:", "(")):
            out.add(urljoin(base, raw.replace("&amp;", "&")))
    return out


# --------------------------------------------------------------------------
# Moteur
# --------------------------------------------------------------------------
class Crawler:
    def __init__(self, args):
        self.args = args
        self.scope = Scope(args.gamma_base, args.beta_base, args.only)
        self.formats = {f.strip() for f in args.formats.split(",")}
        self.store = Store(args.out, keep_html="html" in self.formats)
        self.fetch = Fetcher(args.delay, args.timeout, self.scope)
        self.stop = False
        self.bad_streak = 0

    def seed(self):
        seeds = [self.args.gamma_base.rstrip("/") + "/archives"]
        for s in seeds:
            u = self.scope.normalize(s)
            k = self.scope.classify(u)
            if k:
                self.store.add(u, k, None)
        # relance des erreurs réseau/temporaires d'une session précédente : si le site a
        # coupé, ces pages n'y sont pour rien, elles repartent avec un compteur à zéro
        self.store.db.execute(
            "UPDATE urls SET status=NULL, tries=0 WHERE status IN (-1,429,500,502,503,504)"
        )
        self.store.db.commit()
        last, at = self.store.get_state("last_url"), self.store.get_state("last_at")
        cur = self.store.get_state("current_url")
        if last:
            print(f"Reprise : dernière page enregistrée ({at}) : {last}")
        if cur and cur != last:
            print(f"          page interrompue, reprise en premier : {cur}")

    def _sleep(self, seconds):
        """Pause interruptible par Ctrl+C."""
        end = time.monotonic() + seconds
        while not self.stop and time.monotonic() < end:
            time.sleep(min(0.5, end - time.monotonic()))

    def run(self):
        phase = self.args.cmd
        kinds = [STRUCT] if phase == "inventory" else [STRUCT, TOPIC, ASSET]
        signal.signal(signal.SIGINT, lambda *_: setattr(self, "stop", True))
        self.seed()
        n = 0
        t0 = time.time()
        while not self.stop:
            row = self.store.next_todo(kinds, self.args.assets_first)
            if row is None:
                break
            url, kind, tries = row
            self.store.set_state("current_url", url)
            self.store.db.commit()
            if not self.fetch.allowed(url):
                self.store.mark_skipped(url, "robots.txt")
                self.store.db.commit()
                continue
            try:
                status, ctype, final, body = self.fetch.get(url)
                err = None
            except Exception as e:  # réseau, timeout, SSL...
                status, ctype, final, body, err = -1, None, url, None, f"{type(e).__name__}: {e}"
            if status in (429, 503) or status == -1:
                self.bad_streak += 1
                self.store.bump_retry(url, err or f"HTTP {status}")
                if tries + 1 >= self.args.retries:
                    self.store.save(url, status, ctype, final, None, err)  # abandon (marqué)
                    self.store.db.commit()
                wait = min(300, 5 * 2 ** min(self.bad_streak, 6))
                print(f"  ! {status} sur {url} - pause {wait}s", file=sys.stderr)
                self._sleep(wait)
                if self.bad_streak >= 12:
                    print("Trop d'échecs consécutifs : le site semble coupé. Arrêt ; relancez plus tard,"
                          " la collecte reprendra à cette page.", file=sys.stderr)
                    break
                continue
            self.bad_streak = 0
            self.store.save(url, status, ctype, final, body, err, kind)
            if status == 200 and body is not None and "json" in self.formats and kind != ASSET:
                try:
                    write_json(self.args.out, final, ctype, body)
                except Exception as e:  # un parsing raté ne doit jamais arrêter la capture
                    print(f"  ! JSON impossible pour {url} : {type(e).__name__}: {e}"
                          " (refaire avec la commande `json`)", file=sys.stderr)
            if status == 200 and body is not None:
                is_css = "css" in (ctype or "").lower() or final.lower().split("?")[0].endswith(".css")
                for link in extract_links(body, ctype, final):
                    nl = self.scope.normalize(link)
                    k = self.scope.classify(nl, is_css)
                    if k:
                        self.store.add(nl, k, url)
                for link in extract_asset_links(body, ctype, final):
                    nl = self.scope.normalize(link)
                    k = self.scope.classify(nl, True)
                    if k:
                        self.store.add(nl, k, url)
            self.store.db.commit()  # page + liens découverts : tout ou rien
            n += 1
            if n % 25 == 0:
                self.progress(n, t0)
        self.store.db.commit()
        self.progress(n, t0)
        if "json" in self.formats and os.path.isdir(os.path.join(self.args.out, "json")):
            try:
                print(f"Commandants : {build_commandants(self.args.out)}")
            except Exception as e:
                print(f"  ! répertoire des commandants impossible : {type(e).__name__}: {e}", file=sys.stderr)
        print("Interrompu - relancez la même commande pour reprendre." if self.stop else "Terminé.")

    def progress(self, n, t0):
        c = self.store.db.execute(
            "SELECT SUM(status IS NULL), SUM(status=200), SUM(status>=400 OR status=-1) FROM urls"
        ).fetchone()
        print(f"[{n} requêtes, {int(time.time()-t0)}s] à faire={c[0] or 0} ok={c[1] or 0} erreurs={c[2] or 0}")


# --------------------------------------------------------------------------
# Rapport de volume
# --------------------------------------------------------------------------
RE_GAMMA_FORUM_LIST = re.compile(r"/archives/([^/]+)/([^/]+)/forums/(\d+)/page\d+$")
RE_ROW = re.compile(r'<tr>\s*<td class="wrap_allowed">(.*?)</tr>', re.S)
RE_TOPIC_HREF = re.compile(r'/topics/(\d+)/page1"')
RE_REPLIES = re.compile(r"<td[^>]*>\s*(\d+)\s*(?:\(dont[^<]*\))?\s*</td>")
MSG_PER_PAGE_GAMMA = 10


def report(args):
    store = Store(args.out)
    db = store.db
    print("=== Pages par type et statut ===")
    for kind, st, n, sz in db.execute(
        "SELECT kind, COALESCE(status,'à faire'), COUNT(*), COALESCE(SUM(size),0) FROM urls GROUP BY 1,2 ORDER BY 1,2"
    ):
        print(f"  {kind:7} {str(st):8} {n:8} pages  {sz/1e6:9.1f} Mo")

    topics = defaultdict(set)         # (partie, galaxie) -> ids de topics vus dans les listes
    est_pages = defaultdict(int)      # estimation du nombre de pages de topics (Gamma)
    list_pages = defaultdict(int)
    for url, path, in db.execute("SELECT url, path FROM urls WHERE kind='struct' AND status=200 AND path IS NOT NULL"):
        m = RE_GAMMA_FORUM_LIST.search(urlsplit(url).path)
        if not m:
            continue
        key = (m.group(1), m.group(2))
        list_pages[key] += 1
        with open(os.path.join(store.raw, path), "rb") as fh:
            html = fh.read().decode("utf-8", "replace")
        for row in RE_ROW.findall(html):
            t = RE_TOPIC_HREF.search(row)
            if not t or t.group(1) in topics[key]:
                continue
            topics[key].add(t.group(1))
            r = RE_REPLIES.findall(row)
            replies = int(r[0]) if r else 0
            est_pages[key] += -(-(replies + 1) // MSG_PER_PAGE_GAMMA)
    if topics:
        print("\n=== Gamma : topics vus dans les listes (estimation du nombre de pages de topics) ===")
        tot_t = tot_p = 0
        for key in sorted(topics, key=lambda k: (k[0], int(re.sub(r'\D', '', k[1]) or 0))):
            print(f"  {key[0]}/{key[1]:11} listes={list_pages[key]:4} topics={len(topics[key]):6} pages≈{est_pages[key]:7}")
            tot_t += len(topics[key]); tot_p += est_pages[key]
        print(f"  TOTAL                    topics={tot_t:6} pages≈{tot_p:7}")
        # extrapolation en volume si on a de vrais topics téléchargés
        r = db.execute("SELECT COUNT(*), AVG(size) FROM urls WHERE kind='topic' AND status=200 AND url LIKE '%/archives/%'").fetchone()
        if r[0]:
            print(f"  Taille moyenne mesurée d'une page de topic : {r[1]/1024:.1f} Ko -> ≈ {tot_p*r[1]/1e9:.2f} Go")
        else:
            print("  (taille moyenne d'une page de topic Gamma ≈ 40 Ko d'après l'échantillon -> "
                  f"≈ {tot_p*43e3/1e9:.2f} Go, à confirmer avec `full --only`)")

    beta = db.execute(
        "SELECT COUNT(*) FROM urls WHERE kind='topic' AND url NOT LIKE '%/archives/%'"
    ).fetchone()[0]
    if beta:
        print(f"\n=== Beta : {beta} pages de topics découvertes (liens viewtopic-*) ===")
    todo_assets = db.execute("SELECT COUNT(*) FROM urls WHERE kind='asset'").fetchone()[0]
    print(f"\nRessources (CSS/JS/images/avatars) connues : {todo_assets}")
    errs = db.execute("SELECT url, status, error FROM urls WHERE status>=400 OR status=-1 LIMIT 20").fetchall()
    if errs:
        print("\n=== Erreurs (20 premières) ===")
        for e in errs:
            print("  ", e)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", nargs="?", default="full", choices=["inventory", "full", "report", "json", "commandants"],
                    help="défaut sans argument : full (crawl intégral, formats html et json)")
    ap.add_argument("--formats", default="html,json",
                    help="archives produites pendant la capture : html (octets bruts), json (infos utiles "
                         "seulement) ou html,json (défaut)")
    ap.add_argument("--out", default="archive", help="dossier de sortie (défaut: archive)")
    ap.add_argument("--delay", type=float, default=0.25, help="secondes entre deux requêtes (défaut 0.25)")
    ap.add_argument("--assets-first", action="store_true",
                    help="récupérer les ressources déjà connues (images, CSS, JS) avant les topics restants")
    ap.add_argument("--timeout", type=float, default=30.0)
    ap.add_argument("--retries", type=int, default=4)
    ap.add_argument("--only", action="append", help="limiter à une galaxie, ex. gamma2/galaxie1 ou beta1/galaxie0 (répétable)")
    ap.add_argument("--gamma-base", default=DEFAULT_GAMMA, help=argparse.SUPPRESS)
    ap.add_argument("--beta-base", default=DEFAULT_BETA, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    if args.cmd == "report":
        report(args)
    elif args.cmd == "json":
        build_json(args)
    elif args.cmd == "commandants":
        print(f"Commandants : {build_commandants(args.out)}")
    else:
        Crawler(args).run()


if __name__ == "__main__":
    main()
