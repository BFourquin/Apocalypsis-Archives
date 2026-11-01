#!/usr/bin/env python3
"""build_site.py - assemble le site statique (GitHub Pages) dans _site/.

Le site est un miroir des pages d'origine (archive_raw/raw), à l'identique visuellement :
  archive_raw/raw/<hôte>/...   -> _site/<hôte>/...   (HTML nettoyé, ressources copiées telles quelles)
  viewer/*                     -> _site/             (page d'accueil et recherche)
  archive_raw/json/**          -> _site/search/      (index de recherche, généré)
  wiki/*                       -> _site/wiki/        (copie statique du wiki du jeu, générée par build_wiki.py)

Modifications apportées aux pages d'origine (voir CONTEXT.md, 2.6 et 2.9) :
  * Google Analytics retiré ;
  * lien « Prévenir Dieu » retiré (Gamma) ;
  * libellés Halloween de la notation remplacés par les libellés d'origine (Gamma) ;
  * liens absolus (/archives/..., /css/...) réécrits en liens relatifs pour fonctionner sous
    un sous-dossier (https://<compte>.github.io/<dépôt>/) ;
  * pages réencodées en UTF-8 (Beta : ISO-8859-1). Les dates Beta (JJ/MM ETU HH:MM) sont intactes.

Forum « Chroniques » (RP privés, hors galaxie ; scrape_chroniques.py -> archive_raw/json/chroniques) : pages regénérées
dans le gabarit Gamma sous archives/chroniques*, lien dans un premier tableau de la page des archives, participations
ajoutées aux fiches des commandants ; exclu des statistiques ; dans la recherche, option « Chroniques » du menu des galaxies.

Les ressources absentes de la capture (CSS, images... pas encore téléchargées) sont simplement
absentes du site ; relancer la construction une fois la capture terminée.

Bibliothèque standard uniquement. Usage : python build_site.py [--raw ...] [--json ...] [--out _site]
"""
import argparse
import html
import json
import os
import posixpath
import re
import shutil
import sys
import unicodedata
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive_crawler import local_path, normalize_url  # noqa: E402

GAMMA, BETA = "www.apocalypsis.org", "archivesbeta.apocalypsis.org"
BETA_HOST = BETA
ASSET_EXT = re.compile(r"\.(css|js|gif|jpe?g|png|ico|svg|woff2?|ttf|eot)$", re.I)
SCOPE_PREFIX = ("/archives", "/css/", "/js/", "/images/", "/avatars/", "/vendor/", "/pub/")
URL_RE = re.compile(r"^(?:https?://(www\.apocalypsis\.org|archivesbeta\.apocalypsis\.org))?(/(?!/)[^#]*)?(#.*)?$", re.I)
ATTR_RE = re.compile(r"""\b(href|src|action)\s*=\s*(["'])(.*?)\2""", re.I | re.S)
CSS_URL_RE = re.compile(r"""url\(\s*(['"]?)(/[^)'"]*)\1\s*\)""", re.I)
GA_RE = re.compile(r"<script[^>]*>\s*var _gaq\b.*?</script>", re.I | re.S)
WARN_RE = re.compile(r"""<a\s+href="javascript:popup\('[^']*/warn/[^']*'[^>]*>.*?</a>""", re.I | re.S)
# libellés Halloween -> libellés d'origine (CONTEXT.md 2.9)
LABELS = [("torture adapté", "message adapté"), ("supplice répugnant", "message remarquable"),
          ("rire glaçant", "humour décapant"), ("présence maléfique", "role play intéressant"),
          ("Cauchemards provoqués", "Respect diplomatique")]
LABEL_ENT = [(a.replace("é", "&eacute;").replace("ç", "&ccedil;"), b) for a, b in LABELS]


def decode(body, gamma):
    if gamma:
        try:
            return body.decode("utf-8")
        except UnicodeDecodeError:
            pass
    try:
        return body.decode("cp1252")
    except UnicodeDecodeError:
        return body.decode("latin-1")


CHRON_TABLE = ""  # tableau d'accès aux Chroniques, renseigné par main() quand des sujets ont été capturés
KNOWN = None  # chemins (relatifs à raw) des pages présentes dans le site ; None : pas de contrôle
ARCHIVES_HOME = f"{GAMMA}/archives.html"
REFRESH_RE = re.compile(r"""(<meta[^>]*http-equiv=["']?refresh["']?[^>]*content=["'][^"']*URL=)([^"']+)""", re.I)


def rel(target, page_rel):
    return posixpath.relpath(target, posixpath.dirname(page_rel))


def rewrite_url(val, page_rel, page_host):
    v = val.strip()
    m = URL_RE.match(v)
    if not m or not (m.group(1) or m.group(2)):
        return val
    host = (m.group(1) or page_host).lower()
    path_q, frag = m.group(2) or "/", m.group(3) or ""
    path = path_q.split("?")[0]
    if path == "/" and host == GAMMA:
        return rel("index.html", page_rel) + frag
    if host == GAMMA and not (path.startswith(SCOPE_PREFIX) or ASSET_EXT.search(path)):
        return "https://" + host + path_q + frag  # hors archive : on garde le lien vers le site d'origine
    target = local_path(normalize_url("https://" + host + path_q))
    # Beta : « …/forums_galactiques » redirigeait vers « …/forums_galactiques/ » ; seule la copie du dossier
    # (index.html) résout correctement default.css et images/
    if host == BETA_HOST and target.endswith("/forums_galactiques.html"):
        target = target[:-5] + "/index.html"
    if KNOWN is not None and target.endswith(".html") and target not in KNOWN:
        target = ARCHIVES_HOME  # page absente de l'archive : on renvoie vers l'index des archives
    return rel(target, page_rel) + frag


POSTER_GAMMA_RE = re.compile(r'(<td class="post_left">\s*)([^<]*?\S)(\s*<br)')
POSTER_BETA_RE = re.compile(r'(<td class="posts">)([^<]+)(<br>)')
GRADE_RE = re.compile(r"^\S+\.\s+(?=\S)")


def link_posters(t, page_rel, gamma):
    """Le nom de l'auteur de chaque message renvoie à sa fiche (commandants.html?n=nom, résolu par commandants.js)."""
    def sub(m):
        name = GRADE_RE.sub("", html.unescape(m.group(2)).strip()) if gamma else html.unescape(m.group(2)).strip()
        if not name:
            return m.group(0)
        href = rel("commandants.html", page_rel) + "?n=" + urllib.parse.quote(name, safe="")
        return f'{m.group(1)}<a href="{href}" title="Fiche du commandant">{m.group(2).strip()}</a>{m.group(3)}'
    return (POSTER_GAMMA_RE if gamma else POSTER_BETA_RE).sub(sub, t)


def transform_html(body, page_rel):
    host = page_rel.split("/", 1)[0]
    gamma = host == GAMMA
    t = decode(body, gamma)
    t = GA_RE.sub("", t)
    if CHRON_TABLE and page_rel == ARCHIVES_HOME:  # premier tableau de la page des archives : accès aux Chroniques
        # le <br> d'origine après le titre est consommé : l'espace avec le tableau Gamma est celui qui sépare Gamma et Beta
        t = re.sub(r"(<h3>Archives des parties précédentes</h3>)\s*<br>", lambda m: m.group(1) + "\n<br>\n" + CHRON_TABLE, t, 1)
    if gamma:
        t = WARN_RE.sub("", t)
        for a, b in LABELS + LABEL_ENT:
            t = t.replace(a, b)
    # pages de redirection Beta (meta refresh vers l'ancien site)
    t = REFRESH_RE.sub(lambda m: m.group(1) + rewrite_url(m.group(2), page_rel, host), t)
    t = ATTR_RE.sub(lambda m: f"{m.group(1)}={m.group(2)}{rewrite_url(m.group(3), page_rel, host)}{m.group(2)}", t)
    t = re.sub(r"(charset\s*=\s*)iso-8859-1", r"\1utf-8", t, flags=re.I)
    if "viewtopic" in page_rel or "/topics/" in page_rel:
        t = link_posters(t, page_rel, gamma)
    if gamma and "subtabs_nie" in t and 'id="login"' not in t and 'class="mainarea"' not in t:
        # les pages d'archives n'ont pas le conteneur des forums du jeu : sans lui, pas de largeur maximale (90em, centré)
        t = re.sub(r"(<body[^>]*>)", r'\1<div class="mainarea" style="margin-top:0">', t, 1, flags=re.I)
        t = re.sub(r"</body>", "</div></body>", t, 1, flags=re.I)
    if gamma and 'id="login"' in t:  # pages d'index (archives, parties, galaxies) : gabarit du site public
        t = simplify_public_page(t)
        # onglet Wiki : copie statique du wiki (wiki/, build_wiki.py) au lieu du site d'origine
        t = t.replace('<a href="https://histoire.apocalypsis.org" target="_blank">Wiki</a>',
                      f'<a href="{rel("wiki/index.html", page_rel)}">Wiki</a>')
    return t.encode("utf-8")


def simplify_public_page(t):
    """Pages d'index des archives : on ne garde que le logo et les onglets Accueil (-> notre accueil), Forum, Discord, Wiki, Archives."""
    a, b = t.index('<div class="span4">'), t.index('<div class="span8">')
    t = t[:a] + t[b:].replace('<div class="span8">', '<div class="span12">', 1)  # connexion et actualités
    c = t.rindex('<div class="row">')
    d = t.index("</div>\n\n</body>", c)
    t = t[:c] + t[d:]  # bandeau Facebook et sites de notation
    return re.sub(r'<span class="subtab_other" id="id_subtabbar_(?:presentation|charte)">.*?</span>', "", t)


def transform_css(body, page_rel):
    t = body.decode("utf-8", "replace")
    host = page_rel.split("/", 1)[0]
    return CSS_URL_RE.sub(lambda m: f"url({rewrite_url(m.group(2), page_rel, host)})", t).encode("utf-8")


# --------------------------------------------------------------------------
# Chroniques : forum hors galaxie, regénéré dans le gabarit des pages Gamma
# --------------------------------------------------------------------------
CHRON_DIR = "chroniques"
CHRON_GROUP = "Chroniques"  # groupe de la recherche (hors galaxie)
CHRON_LIST = f"{GAMMA}/archives/{CHRON_DIR}.html"
NEG_LABELS = ["orthographe insuffisante", "présentation bâclée", "hors sujet", "hors role play", "message insultant"]
POS_LABELS = ["efforts visibles", "message adapté", "message remarquable", "humour décapant", "role play intéressant"]
NEG_CODES = ("orthographe", "presentation", "hors_sujet", "hors_roleplay", "insultant")
POS_CODES = ("efforts", "adapte", "remarquable", "humour", "roleplay")
SUPPORT = ('<img src="/images/registered.gif" alt="Ce(tte) commandant(e) soutient beaucoup Apocalypsis." '
           'title="Ce(tte) commandant(e) soutient beaucoup Apocalypsis." border="0">')
CHRON_HEAD = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01 Transitional//EN" "http://www.w3.org/TR/html4/loose.dtd">
<html>
<head>
  <title>Archives</title>
  <meta http-equiv="Content-Type" content="text/html; charset=utf-8">
  <link rel="stylesheet" type="text/css" href="/css/definitive.css?v=55">
  <link href="/css/theme_retro.css?v=55" rel="stylesheet" type="text/css" />
  <script type="text/javascript" src="https://ajax.googleapis.com/ajax/libs/jquery/1.12.4/jquery.min.js"></script>  <script type="text/javascript" src="/js/common.js?v=55"></script>
</head>
<body class="backgroundimg bg-assemblee_assemblee">
<div align="left">
\t<a href="/">
\t\t<img src="/images/public/logo_petit.jpg" alt="Apocalypsis">
\t</a>
\t<a href="/archives">Archives</a>
 &gt; <a href="/archives/%(d)s">Chroniques</a>%(crumb)s
</div>
<div class="subtabs subtabs_nie">
"""
CHRON_HELP_TITLE = 'Forum Chroniques'
CHRON_HELP = '<p class="texte">Le forum Chroniques est un espace dédié aux textes RP personnels et non politiques. Histoire de votre civilisation, récit de faits marquants pour votre commandant, RP privés entre plusieurs joueurs... sont quelques exemples de textes que vous pouvez poster sur ce forum. Tous les messages politiques, débats... doivent être postés à l\'assemblée galactique. Tout message ne respectant pas les règles du forum Chroniques pourra être supprimé.</p><p class="texte warning">Avant d\'intervenir dans un sujet dont vous n\'êtes pas l\'auteur sur le forum Chroniques, assurez vous d\'avoir la permission de l\'auteur avant de poster votre message.</p><p class="texte warning">Tous les messages postés dans le forum chroniques sont considérés comme privés ! Vous ne pouvez donc pas citer ni utiliser le contenu des chroniques : votre personnage n\'en a pas connaissance.</p>'
# texte de présentation du forum (page d'origine), puis style de l'infobulle [?] (reprend celui du site, sans Bootstrap)
CHRON_INTRO = '<p><div class="post_line"><em>Apr&egrave;s avoir re&ccedil;u un &eacute;trange signal &eacute;manant d&#039;une r&eacute;gion d&eacute;serte de l&#039;univers, tr&egrave;s loin de votre galaxie, vous &ecirc;tes parvenu &agrave; d&eacute;coder une suite de symboles.</em></div><div class="post_line"></div><div class="post_line"><font size="4"><strong>ӾՖ⎤ใಶỘಭ┆</strong></font></div><div class="post_line"></div><div class="post_line"><em>Sans plus d&#039;information sur la signification ou la provenance de ce signal, vous pointez vos antennes vers le cadran d&#039;origine et vous pr&eacute;parez &agrave; transmettre une r&eacute;ponse, toutefois conscient que ce que vous vous appr&ecirc;tez &agrave; envoyer ne sera surement jamais lu par quiconque...</div><div class="post_line"></div><div class="post_line">Personne dans cette galaxie ne pourra intercepter cette transmission, et quand bien m&ecirc;me elle venait &agrave; atteindre sa destination, des millions de cycles se seront &eacute;coul&eacute;s pour vous et il en faudrait tout autant pour esp&eacute;rer une quelconque r&eacute;ponse.</em></div></p>'
CHRON_STYLE = """<style>
.help-btn { cursor: help; position: relative; }
.help-pop { display: none; position: absolute; z-index: 10; left: 50%; transform: translateX(-50%); top: 1.6em; width: 500px; max-width: 90vw;
  border: 1px solid #555555; border-bottom: 3px solid orange; background: black; text-align: left; font-weight: normal; }
.help-btn:focus .help-pop { display: block; }
.help-pop h4 { margin: 0; padding: 8px 14px; color: orange; font-size: 18px; border-bottom: 1px solid #555555; }
.help-pop div { max-height: 400px; overflow: auto; padding: 9px 14px; }
.help-pop p { text-align: justify; margin: 0 0 10px; }
</style>
"""
CHRON_TAIL = "</div>\n\n</body>\n</html>\n"


def etu_date(m):
    """Date d'un message au format d'origine Gamma : JJ/MM/AAAA ETU HH:MM (année réelle - 1000)."""
    mm = re.match(r"(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)", m.get("date") or "")
    return f"{mm[3]}/{mm[2]}/{int(mm[1]) - 1000} ETU {mm[4]}" if mm else ""


def load_chroniques(json_root):
    """Sujets du forum Chroniques (scrape_chroniques.py), du plus récemment actif au plus ancien."""
    d = os.path.join(json_root, CHRON_DIR, "topics")
    topics = []
    if os.path.isdir(d):
        for fn in os.listdir(d):
            if fn.endswith(".json"):
                with open(os.path.join(d, fn), encoding="utf-8") as fh:
                    t = json.load(fh)
                if any(t.get("messages", {}).values()):
                    topics.append(t)

    def last(t):
        return max((m.get("date") or "" for ms in t["messages"].values() for m in ms), default="")
    return sorted(topics, key=lambda t: (last(t), t["topic"]), reverse=True)


def chron_pages(t):
    return sorted(int(p) for p in t["messages"])


def chron_url(t, page=1):
    return f"/archives/{CHRON_DIR}/topics/{t['topic']}/page{page}"


def full_name(m):
    return (m.get("grade", "") + " " + m["auteur"]).strip()


def render_chron_post(m):
    e = html.escape
    left = e(full_name(m))
    if m.get("compteur") is not None:
        left += f"<br>{e(m.get('compteur_label', 'Prestige de chroniqueur'))}&nbsp;: {m['compteur']}"
    if m.get("avatar"):
        style = f' style="{e(m["avatar_style"])}"' if m.get("avatar_style") else ""
        left += f'<br /><br /><img src="/{e(m["avatar"].split("/", 1)[1])}"{style} alt="Avatar" />'
    left += f"<br />{etu_date(m)}"
    if m.get("soutien"):
        left += '<div align="center">' + "&nbsp;".join([SUPPORT] * m["soutien"]) + "</div>"
    head = "Message édité - " if m.get("edite") else ""
    if m.get("score") is not None:
        head += f"Score&nbsp;: {m['score']}"
        if m.get("id") is not None and m.get("votes"):
            votes = "<br />".join(f"{e(l)} : {n}" for l, n in m["votes"])
            head += (f""" <a href="javascript:toggle_bloc('cal{m['id']}')">Détails</a><div id="cal{m['id']}" class="vote">"""
                     f'<table align="center"><tr><td class="vote2">{votes}</td></tr></table></div>')
    body = m.get("html")
    if body is None:  # texte seul
        body = "".join(f'<div class="post_line">{e(l)}</div>' for l in m.get("texte", "").split("\n"))
    return f'<tr><td class="post_left">{left}</td><td class="post_right"><div class="posthead">{head}</div>{body}</td></tr>'


def render_chron_pagination(t, page):
    pages = chron_pages(t)
    if len(pages) < 2:
        return ""
    return "<p>Pages&nbsp;: " + " ".join(str(p) if p == page else f'<a href="{chron_url(t, p)}">{p}</a>' for p in pages) + "</p>"


def render_chron_poll(t):
    s = t.get("sondage")
    if not s:
        return ""
    top = max([o["votes"] for o in s["options"]] + [1])
    rows = "".join(f'<tr><td>{html.escape(o["texte"])}</td><td>{o["votes"]}</td><td><div style="height: 9px; width: {round(100 * o["votes"] / top)}px; background-color:#81F0FF"></div></td></tr>'
                   for o in s["options"])
    total = s.get("total", sum(o["votes"] for o in s["options"]))
    fin = f" Ce vote a pris fin le&nbsp;: {html.escape(etu_date({'date': s['fin']}) or s['fin'])}" if s.get("fin") else ""
    return (f'<div class="poll"><h2>{html.escape(s["question"])}</h2><table class="listing"><tbody>{rows}</tbody></table>'
            f"Total&nbsp;: {total} vote(s){fin}</div>")


def render_chroniques(topics):
    """-> {chemin relatif à raw: HTML} : la liste des sujets et une page par page de sujet."""
    out, rows, e = {}, [], html.escape
    for t in topics:
        ms = [m for p in chron_pages(t) for m in t["messages"][str(p)]]
        lastm = max(ms, key=lambda m: m.get("date") or "")
        rows.append(
            f'<tr><td class="wrap_allowed"><a href="{chron_url(t)}">{e(t["titre"])}</a></td>'
            f'<td class="title">{e(full_name(ms[0]))}</td><td class="title">{len(ms) - 1}</td>'
            f'<td class="title">{etu_date(lastm)}<br />{e(full_name(lastm))}</td></tr>')
        for page in chron_pages(t):
            out[f"{GAMMA}{chron_url(t, page)}.html"] = (
                CHRON_HEAD % {"d": CHRON_DIR, "crumb": f' &gt; <a href="{chron_url(t)}">{e(t["titre"])}</a>'}
                + f'<h2>{e(t["titre"])}</h2>' + (render_chron_poll(t) if page == 1 else "")
                + render_chron_pagination(t, page)
                + '<table class="viewtopic">' + "".join(render_chron_post(m) for m in t["messages"][str(page)]) + "</table>"
                + render_chron_pagination(t, page) + CHRON_TAIL)
    out[CHRON_LIST] = (CHRON_HEAD % {"d": CHRON_DIR, "crumb": ""} + "<h2>Chroniques</h2>" + CHRON_STYLE
                       + f'<a class="help-btn" tabindex="0"><b>[?]</b><span class="help-pop"><h4>{CHRON_HELP_TITLE}</h4><div>{CHRON_HELP}</div></span></a>'
                       + CHRON_INTRO + "<br>"
                       + '<table class="listing"><tr><th>Sujet</th><th>Auteur</th><th>Réponses</th><th>Dernier message</th></tr>'
                       + "".join(rows) + "</table>" + CHRON_TAIL)
    return out


def chron_table(n_topics):
    """Premier tableau de la page des archives : accès au forum Chroniques."""
    return ('<table align="center" class="listing"><tbody><tr><th>Hors galaxie</th></tr><tr><td class="title wrap_allowed">'
            f'<a href="/archives/{CHRON_DIR}">Chroniques · {n_topics} sujet(s)</a>'
            "</td></tr></tbody></table>\n")


# --------------------------------------------------------------------------
# Recherche : mêmes règles de normalisation que viewer/search.js
# --------------------------------------------------------------------------
def norm(s):
    out = []
    for ch in s:
        d = unicodedata.normalize("NFD", ch.lower())
        out.append(d[0] if d else ch)
    return "".join(out)


def tokens(s):
    return re.findall(r"[a-z0-9]+", norm(s))


TOPIC_G = re.compile(r"/archives/(gamma\d)/(galaxie\d+)/forums/(\d+)/topics/(\d+)/page(\d+)\.html$")
TOPIC_B = re.compile(r"^(beta\d)/galaxie_(\d+)/forums_galactiques/(\d+)/[^/]+/viewtopic-(\d+)-(\d+)\.html$")
PARTIE = {"beta1": "Beta 1", "beta2": "Beta 2", "beta3": "Beta 3", "gamma1": "Gamma 1", "gamma2": "Gamma 2"}


# noms des galaxies Gamma (https://www.apocalypsis.org/archives)
NOMS = {
    "gamma1": ["Éveil", "Devenir", "Espoir", "Éternité", "Songe", "Aurore", "Firmament"],
    "gamma2": ["Éveil", "Devenir", "Espoir", "Sagesse", "Rédemption", "Utopie", "Décadence", "Renaissance",
               "Révolution", "Catharsis", "Clairvoyance", "Corruption", "Paradoxe", "Crépuscule", "Résurgence",
               "Unité", "Odyssée", "Entropie", "Souvenir", "Mélodie", "Vindicte", "Harmonie", "Délivrance",
               "Déclin", "Transcendance"],
}


def galaxy_label(partie, galaxie):
    """« Gamma 2 · Galaxie 5 », suivi du nom de la galaxie quand il existe (« · Utopie »)."""
    n = int(galaxie[7:])
    label = f'{PARTIE.get(partie, partie)} · Galaxie {n}'
    noms = NOMS.get(partie, [])
    return f"{label} · {noms[n]}" if n < len(noms) else label


def b36(n):
    s = ""
    while True:
        n, r = divmod(n, 36)
        s = "0123456789abcdefghijklmnopqrstuvwxyz"[r] + s
        if not n:
            return s


def disp_date(m):
    d = m.get("date")
    if d:
        mm = re.match(r"(\d{4})-(\d\d)-(\d\d) (\d\d:\d\d)", d)
        return f"{mm[3]}/{mm[2]}/{mm[1]} {mm[4]}" if mm else d
    ds = m.get("date_sans_annee")
    return ds + " ETU" if ds else ""  # Beta : date telle qu'affichée à l'origine


def write_postings(base, postings, n):
    """postings : terme -> [(doc, tf)] ; un fichier par préfixe de 2 lettres."""
    shards = {}
    for tok, plist in postings.items():
        if not 2 <= len(tok) <= 30 or (n > 200 and len(plist) > 0.5 * n):
            continue  # trop court, ou mot présent dans presque toutes les pages
        prev, enc = 0, []
        for d, c in plist:
            enc.append(b36(d - prev) + ("." + str(min(c, 99)) if c > 1 else ""))
            prev = d
        shards.setdefault(tok[:2], {})[tok] = ",".join(enc)
    os.makedirs(base, exist_ok=True)
    for k, v in shards.items():
        with open(os.path.join(base, k + ".json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, separators=(",", ":"))
    return len(shards)


def galaxy_order(label):
    m = re.match(r"(\w+) (\d) · Galaxie (\d+)", label)
    return (m[1], int(m[2]), int(m[3])) if m else (label, 0, 0)


AUTHOR_SHARD = 100


def load_descriptions(json_root):
    """Descriptions publiques (scrape_descriptions.py) : {norm(nom): {"o": galaxie d'origine, "s": [[titre, html], ...]}}."""
    path = os.path.join(json_root, "descriptions.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return {norm(k): v for k, v in json.load(fh).items()}


def description_for(desc, name, gals):
    """Sections de la description d'un commandant, si elle date d'une galaxie où ce nom a joué (le nom a pu être
    repris par un autre joueur plus tard) ; liste vide si le joueur n'a rien renseigné (textes par défaut ignorés)."""
    d = desc.get(norm(name))
    # champs remplis pour rien (« . », « - ») écartés, comme les textes par défaut
    sections = [sec for sec in (d or {"s": []})["s"] if re.search(r"\w", re.sub(r"<[^>]*>", "", sec[1])) or "<img" in sec[1] or len(re.sub(r"<[^>]*>", "", sec[1]).strip()) > 3]
    if not sections:
        return []
    if d["o"] is not None and not any(re.match(rf"Gamma 2 · Galaxie {d['o']}(?: ·|$)", g) for g in gals):
        return []
    return sections


def build_search(json_root, files, out):
    groups, gidx, docs, dkeys, gkeys = [], {}, [], [], []
    fields = {"t": {}, "c": {}, "a": {}}  # titre, contenu, auteurs (commandants et coalitions)
    authors = {}
    stats = {}  # galaxie -> sujets, posts, mots, commandants (hors floodeur en Gamma 2 · Galaxie 5)
    n_json = 0
    for root, _, fns in os.walk(json_root):
        if os.path.basename(root) != "topics" or os.path.relpath(root, json_root).split(os.sep)[0] == CHRON_DIR:
            continue  # les Chroniques (hors galaxie) sont exclues des statistiques et de la recherche
        for fn in sorted(fns, key=lambda s: (len(s), s)):
            with open(os.path.join(root, fn), encoding="utf-8") as fh:
                t = json.load(fh)
            n_json += 1
            tkey = (t["partie"], t["galaxie"], t["forum"], t["topic"])
            gal = galaxy_label(t["partie"], t["galaxie"])
            S = stats.setdefault(gal, {"t": set(), "p": 0, "w": 0, "a": set()})
            # Beta : seules les assemblées galactiques sont comparables aux forums Gamma (hors taverne, marché, journal...)
            in_stats = not t["partie"].startswith("beta") or t.get("forum_nom", "").startswith("Assembl")
            if in_stats:
                S["t"].add((t["forum"], t["topic"]))
            for page, msgs in sorted(t["messages"].items(), key=lambda kv: int(kv[0])):
                for m in (msgs if in_stats else ()):
                    who = norm(m["auteur"].strip())
                    if gal.startswith("Gamma 2 · Galaxie 5 ·") and who in ("floodeur", "cdt. floodeur", "cdte. floodeur"):
                        continue
                    S["p"] += 1
                    S["w"] += len(re.findall(r"\w+", m["texte"]))
                    S["a"].add(who)
                path = files.get((t["partie"], t["galaxie"], str(t["forum"]), str(t["topic"]), int(page)))
                if not path:
                    continue
                g = f'{gal} · {t.get("forum_nom", "")}'
                if g not in gidx:
                    gidx[g] = len(groups)
                    groups.append(g)
                    gkeys.append((galaxy_order(gal), t.get("forum_nom", "")))
                d = len(docs)
                docs.append([path, t["titre"], gidx[g], int(page)])
                dkeys.append((galaxy_order(gal), t["topic"], -int(page)))
                tf = {"t": {}, "c": {}, "a": {}}

                def add(field, text):
                    for tok in tokens(text):
                        tf[field][tok] = tf[field].get(tok, 0) + 1

                add("t", t["titre"])
                for i, m in enumerate(msgs):
                    name = m["auteur"].strip()
                    add("a", name)
                    add("c", m["texte"])
                    # fiche du commandant / de la coalition
                    A = authors.setdefault(norm(name), {"n": name, "m": 0, "s": 0, "p": {}, "q": {},
                                                               "av": "", "rd": None, "gal": {}, "top": {}})
                    A["m"] += 1
                    if m.get("score") is not None:
                        A["s"] += m["score"]
                    for k, v in m.get("positifs", {}).items():
                        A["p"][k] = A["p"].get(k, 0) + v
                    for k, v in m.get("negatifs", {}).items():
                        A["q"][k] = A["q"].get(k, 0) + v
                    if m.get("avatar"):
                        A["av"] = m["avatar"]
                    sk, dd = (t["topic"], int(page), i), disp_date(m)
                    G = A["gal"].setdefault(gal, {"m": 0, "tp": set(), "first": None, "last": None})
                    G["m"] += 1
                    G["tp"].add(t["topic"])
                    if G["first"] is None or sk < G["first"][0]:
                        G["first"] = (sk, dd)
                    if G["last"] is None or sk > G["last"][0]:
                        G["last"] = (sk, dd)
                    if m.get("compteur") is not None:
                        A["rd"] = max(A["rd"] or 0, m["compteur"])
                    T = A["top"].setdefault(tkey, {"docs": [], "n": 0, "first": dd, "last": dd, "cr": 0, "gal": gal, "id": t["topic"]})
                    if d not in T["docs"]:
                        T["docs"].append(d)
                    T["n"] += 1
                    T["last"] = dd
                    if page == "1" and i == 0:
                        T["cr"] = 1
                if page == "1" and t.get("sondage"):
                    s = t["sondage"]
                    add("c", s.get("question", "") + " " + " ".join(o["texte"] for o in s.get("options", [])))
                for f, counts in tf.items():
                    for tok, c in counts.items():
                        fields[f].setdefault(tok, []).append((d, c))
    # Chroniques : pages indexées dans un groupe à part (proposé dans le menu de la recherche, hors « toutes les galaxies »)
    for t in load_chroniques(json_root):
        g = CHRON_GROUP
        if g not in gidx:
            gidx[g] = len(groups)
            groups.append(g)
            gkeys.append((galaxy_order(g), ""))
        for page in chron_pages(t):
            d = len(docs)
            docs.append([f"{GAMMA}/archives/{CHRON_DIR}/topics/{t['topic']}/page{page}.html", t["titre"], gidx[g], page])
            dkeys.append((galaxy_order(g), t["topic"], -page))
            tf = {"t": {}, "c": {}, "a": {}}
            texts = {"t": [t["titre"]], "a": [m["auteur"] for m in t["messages"][str(page)]],
                     "c": [m["texte"] for m in t["messages"][str(page)]]}
            if page == chron_pages(t)[0] and t.get("sondage"):
                texts["c"].append(t["sondage"].get("question", "") + " " + " ".join(o["texte"] for o in t["sondage"].get("options", [])))
            for f, parts in texts.items():
                for tok in tokens(" ".join(parts)):
                    tf[f][tok] = tf[f].get(tok, 0) + 1
            for f, counts in tf.items():
                for tok, c in counts.items():
                    fields[f].setdefault(tok, []).append((d, c))
    n = len(docs)
    # numéros de pages dans l'ordre chronologique (galaxie, sujet, page) : la recherche trie du plus grand
    # au plus petit numéro, donc du plus récent au plus ancien ; groupes (galaxie + forum) du plus récent au plus ancien
    by_time = sorted(range(n), key=lambda i: dkeys[i])
    newid = [0] * n
    for pos, old in enumerate(by_time):
        newid[old] = pos
    docs = [docs[old] for old in by_time]
    gorder = sorted(range(len(groups)), key=lambda i: gkeys[i][1])
    gorder.sort(key=lambda i: gkeys[i][0], reverse=True)
    gnew = {old: pos for pos, old in enumerate(gorder)}
    groups = [groups[old] for old in gorder]
    for dd in docs:
        dd[2] = gnew[dd[2]]
    for f in fields:
        for tok, plist in fields[f].items():
            fields[f][tok] = sorted((newid[d], c) for d, c in plist)
    for A in authors.values():
        for T in A["top"].values():
            T["docs"] = sorted((newid[d] for d in T["docs"]), key=lambda d: docs[d][3])
    sdir = os.path.join(out, "search")
    os.makedirs(sdir, exist_ok=True)
    with open(os.path.join(sdir, "docs.json"), "w", encoding="utf-8") as fh:
        json.dump({"groups": groups, "docs": docs}, fh, ensure_ascii=False, separators=(",", ":"))
    nfiles = sum(write_postings(os.path.join(sdir, f), p, n) for f, p in fields.items())

    rows = []
    for gal in sorted(stats, key=galaxy_order):
        S = stats[gal]
        rows.append([gal, len(S["t"]), S["p"], len(S["a"]), S["w"]])
    with open(os.path.join(out, "stats.json"), "w", encoding="utf-8") as fh:
        json.dump(rows, fh, ensure_ascii=False, separators=(",", ":"))

    # participations aux Chroniques : ajoutées aux fiches, sans effet sur les totaux des galaxies
    for t in load_chroniques(json_root):
        pages = chron_pages(t)
        for page in pages:
            for i, m in enumerate(t["messages"][str(page)]):
                name = m["auteur"].strip()
                A = authors.setdefault(norm(name), {"n": name, "m": 0, "s": 0, "p": {}, "q": {},
                                                           "av": "", "rd": None, "gal": {}, "top": {}})
                if m.get("avatar") and not A["av"]:
                    A["av"] = m["avatar"]
                C = A.setdefault("ch", {}).setdefault(t["topic"], {"t": t["titre"], "n": 0, "pages": set(), "first": None, "last": None,
                                                                     "cr": int(page == pages[0] and i == 0)})
                C["n"] += 1
                C["pages"].add(page)
                iso = m.get("date") or ""
                if C["first"] is None or iso < C["first"][0]:
                    C["first"] = (iso, disp_date(m))
                if C["last"] is None or iso >= C["last"][0]:
                    C["last"] = (iso, disp_date(m))

    # fiches commandants / coalitions
    adir = os.path.join(out, "auteurs")
    os.makedirs(adir, exist_ok=True)
    order = sorted(authors.values(), key=lambda a: norm(a["n"]))
    desc = load_descriptions(json_root)
    listing, shard, dshard = [], {}, {}
    for i, A in enumerate(order):
        gals = sorted(A["gal"], key=galaxy_order, reverse=True)
        gi = {g: j for j, g in enumerate(gals)}
        chron = sorted(A.get("ch", {}).items(), key=lambda kv: (kv[1]["last"][0], kv[0]), reverse=True)
        listing.append([A["n"], A["m"], len(gals)] + ([sum(c["n"] for _, c in chron)] if chron else []))
        top = sorted(A["top"].values(), key=lambda T: (galaxy_order(T["gal"]), T["id"]), reverse=True)
        sections = description_for(desc, A["n"], gals)
        if sections:
            dshard.setdefault(i // AUTHOR_SHARD, {})[str(i)] = sections
        shard.setdefault(i // AUTHOR_SHARD, {})[str(i)] = {
            "n": A["n"], "m": A["m"], "s": A["s"], "p": A["p"], "q": A["q"], "av": A["av"], "rd": A["rd"],
            "gal": [[g, A["gal"][g]["m"], len(A["gal"][g]["tp"]), A["gal"][g]["first"][1], A["gal"][g]["last"][1]] for g in gals],
            "top": [[T["docs"], T["n"], T["first"], T["last"], T["cr"], gi[T["gal"]]] for T in top],
            **({"d": 1} if sections else {}),
            **({"ch": [[tid, c["t"], c["n"], c["first"][1], c["last"][1], c["cr"], sorted(c["pages"])] for tid, c in chron]} if chron else {}),
        }
    with open(os.path.join(adir, "liste.json"), "w", encoding="utf-8") as fh:
        json.dump({"shard": AUTHOR_SHARD, "a": listing}, fh, ensure_ascii=False, separators=(",", ":"))
    for k, v in shard.items():
        with open(os.path.join(adir, f"{k}.json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False, separators=(",", ":"))
    for k, v in dshard.items():
        with open(os.path.join(adir, f"d{k}.json"), "w", encoding="utf-8") as fh:
            json.dump(v, fh, ensure_ascii=False, separators=(",", ":"))
    print(f"recherche : {n_json} topics JSON, {n} pages indexées, {nfiles} fichiers d'index, {len(order)} auteurs")


def register_topic(files, page_rel):
    """Associe (partie, galaxie, forum, topic, page) au fichier HTML correspondant."""
    if page_rel.startswith(GAMMA):
        m = TOPIC_G.search("/" + page_rel)
        if m:
            files[(m[1], m[2], m[3], m[4], int(m[5]))] = page_rel
    elif page_rel.startswith(BETA):
        m = TOPIC_B.match(page_rel.split("/", 1)[1])
        if m:
            files[(m[1], "galaxie" + m[2], m[3], m[4], int(m[5]))] = page_rel


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default="archive_raw/raw")
    ap.add_argument("--json", default="archive_raw/json")
    ap.add_argument("--out", default="_site")
    ap.add_argument("--viewer", default="viewer")
    ap.add_argument("--wiki", default="wiki", help="copie statique du wiki (build_wiki.py)")
    ap.add_argument("--search-only", action="store_true", help="ne régénère que search/ et auteurs/ dans un _site existant")
    ap.add_argument("--overlay", help="dossier de ressources (même arborescence que raw) à ajouter s'il manque (essais)")
    a = ap.parse_args()

    if a.search_only:
        files = {}
        for root, _, fns in os.walk(a.raw):
            for fn in fns:
                page_rel = os.path.relpath(os.path.join(root, fn), a.raw).replace(os.sep, "/")
                register_topic(files, page_rel)
        for d in ("search", "auteurs"):
            shutil.rmtree(os.path.join(a.out, d), ignore_errors=True)
        for fn in os.listdir(a.viewer):
            src = os.path.join(a.viewer, fn)
            if os.path.isdir(src):
                shutil.copytree(src, os.path.join(a.out, fn), dirs_exist_ok=True)
            else:
                shutil.copy(src, a.out)
        build_search(a.json, files, a.out)
        return
    if os.path.isdir(a.out):
        shutil.rmtree(a.out)
    shutil.copytree(a.viewer, a.out)
    global KNOWN
    KNOWN = set()
    for base in [a.raw] + ([a.overlay] if a.overlay else []):
        for root, _, fns in os.walk(base):
            for fn in fns:
                KNOWN.add(os.path.relpath(os.path.join(root, fn), base).replace(os.sep, "/"))
    for k in [k for k in KNOWN if k.startswith(BETA) and k.endswith("/forums_galactiques.html")]:
        KNOWN.discard(k)
    chron_pages_html = render_chroniques(load_chroniques(a.json))
    if chron_pages_html:
        global CHRON_TABLE
        CHRON_TABLE = chron_table(len(load_chroniques(a.json)))
        KNOWN.update(chron_pages_html)
    files, n_html, n_other = {}, 0, 0
    for base in [a.raw] + ([a.overlay] if a.overlay else []):
        for root, _, fns in os.walk(base):
            for fn in fns:
                src = os.path.join(root, fn)
                page_rel = os.path.relpath(src, base).replace(os.sep, "/")
                if page_rel.split("/", 1)[0] not in (GAMMA, BETA):
                    continue
                if page_rel.startswith(BETA) and page_rel.endswith("/forums_galactiques.html"):
                    continue  # doublon de forums_galactiques/index.html, aux liens relatifs décalés
                dst = os.path.join(a.out, page_rel)
                if base != a.raw and os.path.exists(dst):
                    continue
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(src, "rb") as fh:
                    body = fh.read()
                low = fn.lower()
                if low.endswith(".html"):
                    body = transform_html(body, page_rel)
                    n_html += 1
                    register_topic(files, page_rel)
                elif low.endswith(".css") and page_rel.startswith(GAMMA):
                    body = transform_css(body, page_rel)
                    n_other += 1
                else:
                    n_other += 1
                with open(dst, "wb") as fh:
                    fh.write(body)
    for page_rel, page in chron_pages_html.items():
        dst = os.path.join(a.out, page_rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, "wb") as fh:
            fh.write(transform_html(page.encode("utf-8"), page_rel))
        n_html += 1
    if os.path.isdir(a.wiki):
        shutil.copytree(a.wiki, os.path.join(a.out, "wiki"))
    open(os.path.join(a.out, ".nojekyll"), "w").close()
    print(f"{n_html} pages HTML, {n_other} autres fichiers")
    build_search(a.json, files, a.out)


if __name__ == "__main__":
    main()
