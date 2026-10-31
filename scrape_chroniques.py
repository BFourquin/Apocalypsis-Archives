#!/usr/bin/env python3
"""scrape_chroniques.py - capture le forum « Chroniques » (www.apocalypsis.org/assemblee/viewforum?c_forum=2038).

Les Chroniques ne dépendent d'aucune galaxie (RP privés) et le forum est encore actif : le script peut être relancé
autant de fois que nécessaire, seuls les sujets nouveaux ou modifiés (réponses / dernier message) sont retéléchargés.
Le forum n'est visible qu'une fois connecté : APOC_USER et APOC_PASS (jamais écrits dans le dépôt), comme pour
scrape_descriptions.py (page d'attente d'environ 8 s après la connexion).

Sorties :
  archive_raw/chroniques/raw/topic-<id>-p<n>.html, list-p<n>.html   pages brutes (permettent de relancer l'analyse : --reparse)
  archive_raw/json/chroniques/topics/<id>.json                      un sujet (messages par page, même forme que l'archive Gamma + « html »)
  archive_raw/json/chroniques/sujets.json                           liste des sujets (auteur, réponses, dernier message)
  archive_raw/raw/www.apocalypsis.org/avatars/...                   avatars absents de l'archive

Bibliothèque standard uniquement. Usage :
  APOC_USER=... APOC_PASS=... python scrape_chroniques.py [--delay 1.0] [--force] [--limit N]
  python scrape_chroniques.py --reparse        (sans réseau, depuis les pages brutes)
"""
import argparse
import html as html_lib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from archive_crawler import _date, _author, _decode, _parse_poll, _txt, local_path, normalize_url, parse_topic_page  # noqa: E402
from scrape_descriptions import Session, decode  # noqa: E402

BASE = "https://www.apocalypsis.org"
FORUM = 2038
ROOT = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(ROOT, "archive_raw", "chroniques", "raw")
JSON_DIR = os.path.join(ROOT, "archive_raw", "json", "chroniques")
AVATARS = os.path.join(ROOT, "archive_raw", "raw")

HREF_RE = re.compile(r"""href\s*=\s*(?:"([^"]*)"|'([^']*)')""", re.I)
TOPIC_ID_RE = re.compile(r"[?&;]c_topic=(\d+)")
ROW_RE = re.compile(r"<tr(?:\s[^>]*)?>(.*?)</tr>", re.S | re.I)
IMG_RE = re.compile(r"""<img\b[^>]*?src\s*=\s*["']([^"']*/avatars/[^"']+)["']""", re.I)


class Fetcher(Session):
    def get(self, url):
        """-> (octets, content-type) ; reconnexion automatique si la session est perdue."""
        for attempt in range(4):
            wait = self.last + self.delay - time.time()
            if wait > 0:
                time.sleep(wait)
            try:
                with self.opener.open(url, timeout=90) as r:
                    body, ctype = r.read(), r.headers.get("Content-Type", "")
            except urllib.error.HTTPError as e:
                if e.code in (403, 404):
                    return None, ""
                print(f"  ! {url}: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
                continue
            except (urllib.error.URLError, OSError) as e:
                print(f"  ! {url}: {e}", file=sys.stderr)
                time.sleep(5 * (attempt + 1))
                continue
            finally:
                self.last = time.time()
            if "html" in ctype and (b'name="e_nom"' in body or b"Apocalypsis needs you" in body):
                print("  session expirée, nouvelle connexion", file=sys.stderr)
                self.login()
                continue
            return body, ctype
        raise SystemExit(f"Impossible de charger {url}")


def links(page, base):
    out = []
    for m in HREF_RE.finditer(page):
        h = html_lib.unescape(m.group(1) or m.group(2) or "").strip()
        if h and not h.startswith(("#", "javascript:", "mailto:")):
            out.append(urllib.parse.urljoin(base, h))
    return out


def list_links(page, base):
    """Pages de la liste des sujets du forum (pagination)."""
    return {u for u in links(page, base) if re.search(r"/assemblee/viewforum\?", u) and re.search(rf"c_forum={FORUM}\b", u)}


def topic_links(page, base, topic):
    """Pages du même sujet (pagination)."""
    return {u for u in links(page, base) if re.search(r"/assemblee/viewtopic\?", u) and not re.search(r"delete|warn|newpost", u) and (TOPIC_ID_RE.search(u) or [None, ""])[1] == str(topic)}


def parse_list(page, base):
    """-> {id_sujet: {titre, auteur, reponses, supprimes, dernier, dernier_auteur, sondage}}"""
    topics = {}
    for row in ROW_RE.findall(page):
        href = next((u for u in links(row, base) if "viewtopic" in u and TOPIC_ID_RE.search(u)), None)
        if not href:
            continue
        tid = TOPIC_ID_RE.search(href).group(1)
        a = re.search(r"<a\b[^>]*viewtopic[^>]*>(.*?)</a>", row, re.S | re.I)
        d = {"titre": _txt(re.sub(r"<font[^>]*>\s*\[Vote\]\s*</font>", "", a.group(1) if a else ""))}
        if "[Vote]" in row:
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
        topics[tid] = d
    return topics


def page_number(url):
    m = re.search(r"[?&;](?:page|p|c_page|start)=(\d+)", url)
    return int(m.group(1)) if m else None


def write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode, **({} if mode == "wb" else {"encoding": "utf-8"})) as fh:
        fh.write(data)


def save_json(path, doc):
    write(path + ".part", json.dumps(doc, ensure_ascii=False, separators=(",", ":")))
    os.replace(path + ".part", path)


def parse_post(left, right, base):
    """Un message du forum (gabarit en ligne, différent des archives : « Prestige de chroniqueur », critères propres)."""
    p = {}
    name = _txt(re.split(r"<br", left, 1, flags=re.I)[0])
    grade, name = _author(name, True)
    p["auteur"] = name
    if grade:
        p["grade"] = grade
    m = re.search(r"<br>([^<]*?)(?:&nbsp;|\s)*:\s*(\d+)<br", left)
    if m:
        p["compteur"], p["compteur_label"] = int(m.group(2)), _txt(m.group(1))
    m = IMG_RE.search(left)
    if m:
        p["avatar"] = local_path(normalize_url(urllib.parse.urljoin(base, html_lib.unescape(m.group(1)))))
        st = re.search(r'style\s*=\s*"([^"]*)"', left[m.start():left.find(">", m.end())])
        if st:
            p["avatar_style"] = st.group(1)
    p["date"], _ = _date(left)
    if not p["date"]:
        del p["date"]
    n = left.count("registered.gif")
    if n:
        p["soutien"] = n
    cal = re.search(r'<div id="cal(\d+)" class="vote">', right)
    if cal:
        p["id"] = int(cal.group(1))
        end = re.search(r"</center>[\s ]*</div></div></div>", right[cal.end():])
        head, body = right[:cal.end() + (end.end() if end else 0)], right[cal.end() + (end.end() if end else 0):]
    else:
        k = right.find("</div>")
        head, body = right[:k + 6], right[k + 6:]
    if "Message édité" in head:
        p["edite"] = True
    m = re.search(r"Score(?:&nbsp;|\s)*:\s*(-?\d+)", head)
    if m:
        p["score"] = int(m.group(1))
    cells = "".join(re.findall(r'<td class="vote2?">(.*?)</td>', head, re.S))
    votes = [[m.group(1).strip(), int(m.group(2))] for m in
             (re.match(r"(.*?)\s*:\s*(\d+)\s*$", _txt(x)) for x in re.split(r"<br\s*/?>", cells)) if m]
    if votes:
        p["votes"] = votes
    body = re.sub(r"\s*</td>\s*</tr>\s*(?:<tr>\s*)?(?:</table>\s*)?$", "", body.strip())
    p["html"] = body.strip()
    p["texte"] = _body_text(p["html"])
    return p


def _body_text(h):
    s = re.sub(r"<br\s*/?>", "\n", h, flags=re.I).replace('<div class="post_line">', "\n")
    s = html_lib.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def parse_topic_files(tid):
    """Assemble le JSON d'un sujet depuis les pages brutes topic-<id>-p<n>.html."""
    doc = {"partie": "chroniques", "galaxie": "", "forum": FORUM, "topic": int(tid), "titre": "", "forum_nom": "", "messages": {}}
    pages = sorted(int(m.group(1)) for fn in os.listdir(RAW) if (m := re.fullmatch(rf"topic-{tid}-p(\d+)\.html", fn)))
    doc["forum_nom"] = "Chroniques"
    doc["pages"] = len(pages)
    for i, n in enumerate(pages, 1):  # pages renumérotées 1, 2, 3... (le numéro d'origine peut être un décalage)
        with open(os.path.join(RAW, f"topic-{tid}-p{n}.html"), "rb") as fh:
            page = _decode(fh.read(), "text/html; charset=utf-8")
        base = f"{BASE}/assemblee/viewtopic?c_topic={tid}"
        h2 = re.search(r"<h2>(.*?)</h2>", page, re.S)
        posts = []
        chunks = re.split(r'<td class="post_left">', page)[1:]
        for k, chunk in enumerate(chunks):
            left, _, right = chunk.partition('<td class="post_right">')
            if k == len(chunks) - 1:
                right = re.split(r"<p>Pages", right, 1)[0]  # fin du dernier message : avant la pagination et le formulaire de réponse
            posts.append(parse_post(left, right, base))
        if i == 1:
            doc["titre"] = _txt(h2.group(1)) if h2 else ""
            poll = _parse_poll(page)
            if poll:
                doc["sondage"] = poll
        doc["messages"][str(i)] = posts
    return doc


def fetch_avatars(fetcher, doc):
    for posts in doc["messages"].values():
        for p in posts:
            # avatar, puis images du site utilisées dans le texte (émoticônes...) : /chemin -> raw/<hôte>/chemin
            wanted = ([f"/{p['avatar'].split('/', 1)[1]}"] if p.get("avatar") else []) + \
                re.findall(r"""<img\b[^>]*?src\s*=\s*["'](/(?!/)[^"'?#]+)""", p.get("html", ""), re.I)
            for path in wanted:
                dst = os.path.join(AVATARS, local_path(normalize_url(BASE + path)))
                if os.path.exists(dst):
                    continue
                body, _ = fetcher.get(BASE + path)
                if body:
                    write(dst, body)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--delay", type=float, default=1.0, help="secondes entre deux requêtes")
    ap.add_argument("--force", action="store_true", help="retélécharge tous les sujets")
    ap.add_argument("--limit", type=int, default=0, help="nombre maximal de sujets traités (essais)")
    ap.add_argument("--reparse", action="store_true", help="réanalyse les pages brutes déjà capturées, sans réseau")
    args = ap.parse_args()
    sujets_path = os.path.join(JSON_DIR, "sujets.json")
    old = {}
    if os.path.exists(sujets_path):
        with open(sujets_path, encoding="utf-8") as fh:
            old = json.load(fh)["sujets"]

    if args.reparse:
        ids = sorted({m.group(1) for fn in os.listdir(RAW) if (m := re.match(r"topic-(\d+)-p\d+\.html", fn))})
        for tid in ids:
            save_json(os.path.join(JSON_DIR, "topics", f"{tid}.json"), parse_topic_files(tid))
        print(f"{len(ids)} sujets réanalysés")
        return

    user, pwd = os.environ.get("APOC_USER"), os.environ.get("APOC_PASS")
    if not user or not pwd:
        sys.exit("Définir APOC_USER et APOC_PASS.")
    f = Fetcher(user, pwd, args.delay)
    f.login()

    # 1. liste des sujets (toutes les pages)
    start = f"{BASE}/assemblee/viewforum?c_forum={FORUM}"
    todo, seen, sujets, n = [start], set(), {}, 0
    while todo:
        url = todo.pop(0)
        if url in seen:
            continue
        seen.add(url)
        body, _ = f.get(url)
        if body is None:
            continue
        n += 1
        page = decode(body)
        write(os.path.join(RAW, f"list-p{n}.html"), body)
        sujets.update(parse_list(page, url))
        todo.extend(sorted(list_links(page, url) - seen))
    if not sujets:
        sys.exit("Aucun sujet trouvé : vérifier la connexion (voir archive_raw/chroniques/raw/list-p1.html).")
    print(f"{n} pages de liste, {len(sujets)} sujets")

    # 2. sujets nouveaux ou modifiés
    changed = [t for t in sujets if args.force or old.get(t) != sujets[t] or not os.path.exists(os.path.join(JSON_DIR, "topics", f"{t}.json"))]
    if args.limit:
        changed = changed[: args.limit]
    print(f"{len(changed)} sujets à (re)télécharger")
    for k, tid in enumerate(changed, 1):
        first = f"{BASE}/assemblee/viewtopic?c_topic={tid}"
        todo, seen, got, nums = [first], set(), 0, set()
        while todo:
            url = todo.pop(0)
            if url in seen:
                continue
            seen.add(url)
            body, _ = f.get(url)
            if body is None:
                continue
            page = decode(body)
            num = page_number(url) or 1  # la page 1 est celle sans numéro
            if num in nums:
                continue
            nums.add(num)
            got += 1
            write(os.path.join(RAW, f"topic-{tid}-p{num}.html"), body)
            todo.extend(sorted(topic_links(page, url, tid) - seen))
        doc = parse_topic_files(tid)
        fetch_avatars(f, doc)
        save_json(os.path.join(JSON_DIR, "topics", f"{tid}.json"), doc)
        old[tid] = sujets[tid]
        save_json(sujets_path, {"sujets": {**old}})
        print(f"{k}/{len(changed)} · sujet {tid} · {got} page(s) · {sum(len(v) for v in doc['messages'].values())} message(s)", flush=True)
    save_json(sujets_path, {"sujets": sujets})


if __name__ == "__main__":
    main()
