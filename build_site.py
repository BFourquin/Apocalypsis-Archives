#!/usr/bin/env python3
"""build_site.py - assemble le site statique (GitHub Pages) dans _site/.

Le site est un miroir des pages d'origine (archive_raw/raw), à l'identique visuellement :
  archive_raw/raw/<hôte>/...   -> _site/<hôte>/...   (HTML nettoyé, ressources copiées telles quelles)
  viewer/*                     -> _site/             (page d'accueil et recherche)
  archive_raw/json/**          -> _site/search/      (index de recherche, généré)

Modifications apportées aux pages d'origine (voir CONTEXT.md, 2.6 et 2.9) :
  * Google Analytics retiré ;
  * lien « Prévenir Dieu » retiré (Gamma) ;
  * libellés Halloween de la notation remplacés par les libellés d'origine (Gamma) ;
  * liens absolus (/archives/..., /css/...) réécrits en liens relatifs pour fonctionner sous
    un sous-dossier (https://<compte>.github.io/<dépôt>/) ;
  * pages réencodées en UTF-8 (Beta : ISO-8859-1). Les dates Beta (JJ/MM ETU HH:MM) sont intactes.

Les ressources absentes de la capture (CSS, images... pas encore téléchargées) sont simplement
absentes du site ; relancer la construction une fois la capture terminée.

Bibliothèque standard uniquement. Usage : python build_site.py [--raw ...] [--json ...] [--out _site]
"""
import argparse
import json
import os
import posixpath
import re
import shutil
import sys
import unicodedata

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


def transform_html(body, page_rel):
    host = page_rel.split("/", 1)[0]
    gamma = host == GAMMA
    t = decode(body, gamma)
    t = GA_RE.sub("", t)
    if gamma:
        t = WARN_RE.sub("", t)
        for a, b in LABELS + LABEL_ENT:
            t = t.replace(a, b)
    # pages de redirection Beta (meta refresh vers l'ancien site)
    t = REFRESH_RE.sub(lambda m: m.group(1) + rewrite_url(m.group(2), page_rel, host), t)
    t = ATTR_RE.sub(lambda m: f"{m.group(1)}={m.group(2)}{rewrite_url(m.group(3), page_rel, host)}{m.group(2)}", t)
    t = re.sub(r"(charset\s*=\s*)iso-8859-1", r"\1utf-8", t, flags=re.I)
    if gamma and 'id="login"' in t:  # pages d'index (archives, parties, galaxies) : gabarit du site public
        t = simplify_public_page(t)
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


def build_search(json_root, files, out):
    groups, gidx, docs, dkeys, gkeys = [], {}, [], [], []
    fields = {"t": {}, "c": {}, "a": {}}  # titre, contenu, auteurs (commandants et coalitions)
    authors = {}
    stats = {}  # galaxie -> sujets, posts, mots, commandants (hors floodeur en Gamma 2 · Galaxie 5)
    n_json = 0
    for root, _, fns in os.walk(json_root):
        if os.path.basename(root) != "topics":
            continue
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

    # fiches commandants / coalitions
    adir = os.path.join(out, "auteurs")
    os.makedirs(adir, exist_ok=True)
    order = sorted(authors.values(), key=lambda a: norm(a["n"]))
    listing, shard = [], {}
    for i, A in enumerate(order):
        gals = sorted(A["gal"], key=galaxy_order, reverse=True)
        gi = {g: j for j, g in enumerate(gals)}
        listing.append([A["n"], A["m"], len(gals)])
        top = sorted(A["top"].values(), key=lambda T: (galaxy_order(T["gal"]), T["id"]), reverse=True)
        shard.setdefault(i // AUTHOR_SHARD, {})[str(i)] = {
            "n": A["n"], "m": A["m"], "s": A["s"], "p": A["p"], "q": A["q"], "av": A["av"], "rd": A["rd"],
            "gal": [[g, A["gal"][g]["m"], len(A["gal"][g]["tp"]), A["gal"][g]["first"][1], A["gal"][g]["last"][1]] for g in gals],
            "top": [[T["docs"], T["n"], T["first"], T["last"], T["cr"], gi[T["gal"]]] for T in top],
        }
    with open(os.path.join(adir, "liste.json"), "w", encoding="utf-8") as fh:
        json.dump({"shard": AUTHOR_SHARD, "a": listing}, fh, ensure_ascii=False, separators=(",", ":"))
    for k, v in shard.items():
        with open(os.path.join(adir, f"{k}.json"), "w", encoding="utf-8") as fh:
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
            shutil.copy(os.path.join(a.viewer, fn), a.out)
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
    open(os.path.join(a.out, ".nojekyll"), "w").close()
    print(f"{n_html} pages HTML, {n_other} autres fichiers")
    build_search(a.json, files, a.out)


if __name__ == "__main__":
    main()
