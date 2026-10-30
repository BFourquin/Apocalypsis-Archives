"""Tests du crawler contre un faux site servi en local (pages d'exemple réelles)."""
import hashlib
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.dirname(HERE))
import archive_crawler as ac  # noqa: E402

FIX = os.path.join(HERE, "fixtures")


def fx(name):
    with open(os.path.join(FIX, name), "rb") as f:
        return f.read()


class Site:
    """Deux serveurs : « gamma » (archives + index) et « beta » (pages statiques)."""

    def __init__(self):
        self.hits = []
        self.gamma_port = self.beta_port = None
        site = self

        beta_topic = fx("beta2_topic.html").decode("utf-8", "replace").encode("iso-8859-1", "replace") + "<p>Résumé diplomatique</p>".encode("iso-8859-1")  # vrais octets iso-8859-1
        self.beta_topic = beta_topic

        def gamma(path):
            P = "http://127.0.0.1:%d" % site.beta_port
            if path == "/archives":
                return 200, "text/html; charset=UTF-8", (
                    b'<a href="/archives/gamma2/galaxie2/forums">g2</a>'
                    b'<a href="/archives/gamma2/galaxie99/forums">interdit</a>'
                    b'<a href="/archives/beta2/galaxie0">b2</a>'
                    b'<a href="/archives/gamma2/galaxie3/forums">autre</a>'
                    b'<a href="http://forum.apocalypsis.org/x">hrp</a>')
            if path == "/archives/gamma2/galaxie2/forums":
                return 200, "text/html; charset=UTF-8", b'<a href="/archives/gamma2/galaxie2/forums/186/page1">AG</a>'
            if path == "/archives/gamma2/galaxie3/forums":
                return 200, "text/html; charset=UTF-8", b'<a href="/archives/gamma2/galaxie3/forums/9/page1">AG</a>'
            m = re.match(r"^/archives/gamma2/galaxie2/forums/186/page(\d+)$", path)
            if m:
                return (200, "text/html; charset=UTF-8", fx("gamma2_forum_list.html")) if int(m.group(1)) <= 3 else (404, "text/html", b"nope")
            if re.match(r"^/archives/gamma2/galaxie2/forums/186/topics/\d+/page\d+$", path):
                return 200, "text/html; charset=UTF-8", fx("gamma2_topic.html")
            if re.match(r"^/archives/gamma2/galaxie11/forums/1583/topics/12693/page\d+$", path):
                return 200, "text/html; charset=UTF-8", fx("gamma2_topic.html")
            if path == "/archives/beta2/galaxie0":
                return 200, "text/html; charset=UTF-8", (
                    '<a href="%s/beta2/galaxie_0/forums_galactiques/">forums</a>'
                    '<a href="%s/beta2/galaxie_0/top_view.php?o=3">tri</a>' % (P, P)).encode()
            if path == "/archives/gamma2/old":
                return 301, "", b""
            if path == "/css/definitive.css":
                return 200, "text/css", fx("definitive.css")
            if path == "/css/theme_retro.css":
                return 200, "text/css", fx("theme_retro.css")
            if path == "/js/common.js":
                return 200, "application/javascript", fx("common.js")
            if path.startswith(("/images/", "/avatars/")):
                return 200, "image/jpeg", b"\xff\xd8fake" + path.encode()
            return 404, "text/html", b"nope"

        def beta(path):
            base = "/beta2/galaxie_0/forums_galactiques/"
            if path == base:
                return 200, "text/html; charset=iso-8859-1", b'<a href="viewforum-1-1.html">cat</a>'
            if path == base + "viewforum-1-1.html":
                return 200, "text/html; charset=iso-8859-1", b'<a href="1/viewtopic-4257-1.html">t</a>'
            m = re.match(r"^" + base + r"1/viewtopic-4257-(\d)\.html$", path)
            if m:
                return 200, "text/html; charset=iso-8859-1", site.beta_topic
            if path == base + "1/viewforum-1-1.html":
                return 200, "text/html; charset=iso-8859-1", b"x"
            if path.startswith(base + "images/") or path.startswith(base[:-len("forums_galactiques/")] + "avatars/"):
                return 200, "image/jpeg", b"\xff\xd8beta"
            return 404, "text/html", b"nope"

        def make(handler_fn, who):
            class H(BaseHTTPRequestHandler):
                def log_message(self, *a):
                    pass

                def do_GET(self):
                    site.hits.append((who, self.path, self.headers.get("User-Agent")))
                    path = self.path.split("?")[0]
                    if path == "/robots.txt":
                        body = b"User-agent: *\nDisallow: /archives/gamma2/galaxie99/\n"
                        self.send_response(200); self.send_header("Content-Type", "text/plain")
                        self.send_header("Content-Length", str(len(body))); self.end_headers()
                        self.wfile.write(body); return
                    if who == "gamma" and path == "/archives/gamma2/old":
                        self.send_response(301); self.send_header("Location", "/archives/gamma2/galaxie2/forums")
                        self.end_headers(); return
                    code, ct, body = handler_fn(path)
                    self.send_response(code); self.send_header("Content-Type", ct)
                    self.send_header("Content-Length", str(len(body))); self.end_headers()
                    self.wfile.write(body)
            return H

        self.g = ThreadingHTTPServer(("127.0.0.1", 0), make(gamma, "gamma"))
        self.b = ThreadingHTTPServer(("127.0.0.1", 0), make(beta, "beta"))
        self.gamma_port, self.beta_port = self.g.server_address[1], self.b.server_address[1]
        for s in (self.g, self.b):
            threading.Thread(target=s.serve_forever, daemon=True).start()

    @property
    def gamma_base(self): return "http://127.0.0.1:%d" % self.gamma_port
    @property
    def beta_base(self): return "http://127.0.0.1:%d" % self.beta_port

    def close(self):
        self.g.shutdown(); self.b.shutdown()


class CrawlTest(unittest.TestCase):
    def setUp(self):
        self.site = Site()
        self.out = tempfile.mkdtemp()

    def tearDown(self):
        self.site.close(); shutil.rmtree(self.out, ignore_errors=True)

    def run_cmd(self, cmd, *extra):
        ac.main([cmd, "--out", self.out, "--delay", "0", "--retries", "2",
                 "--gamma-base", self.site.gamma_base, "--beta-base", self.site.beta_base, *extra])

    def rows(self, where="1"):
        db = sqlite3.connect(os.path.join(self.out, "manifest.sqlite"))
        return db.execute("SELECT url, kind, status, path, sha256 FROM urls WHERE " + where).fetchall()

    def test_inventory_does_not_download_topics_or_assets(self):
        self.run_cmd("inventory")
        topics = self.rows("kind='topic'")
        self.assertTrue(topics, "des topics doivent être découverts")
        self.assertTrue(all(r[2] is None for r in topics), "mais pas téléchargés")
        self.assertTrue(all(r[2] is None for r in self.rows("kind='asset'")))
        # listes parcourues : page1..3 OK, page4+ en 404 enregistrées
        st = {r[0].rsplit("/", 1)[1]: r[2] for r in self.rows("url LIKE '%/186/page%'")}
        self.assertEqual(st["page1"], 200)
        self.assertEqual(st["page24"], 404)

    def test_scope_excludes_hrp_robots_and_skip_patterns(self):
        self.run_cmd("full")
        urls = [r[0] for r in self.rows()]
        self.assertFalse(any("forum.apocalypsis.org" in u for u in urls))
        self.assertFalse(any("top_view.php" in u for u in urls))
        self.assertFalse(any("/warn/" in u for u in urls))
        self.assertFalse(any("ajax.googleapis" in u for u in urls))
        hit_paths = [p for _, p, _ in self.site.hits]
        self.assertFalse(any("galaxie99/forums" in p and "robots" not in p for p in hit_paths),
                         "robots.txt doit être respecté")
        r = self.rows("url LIKE '%galaxie99%'")
        self.assertTrue(r and r[0][2] == -2)

    def test_user_agent_sent(self):
        self.run_cmd("inventory")
        self.assertTrue(all("ApoArchiveBot" in (ua or "") for _, _, ua in self.site.hits))

    def test_raw_bytes_identical_including_latin1(self):
        self.run_cmd("full")
        rows = self.rows("url LIKE '%viewtopic-4257-1.html'")
        self.assertEqual(len(rows), 1)
        with open(os.path.join(self.out, "raw", rows[0][3]), "rb") as fh:
            saved = fh.read()
        self.assertEqual(saved, self.site.beta_topic)
        self.assertEqual(hashlib.sha256(saved).hexdigest(), rows[0][4])
        # le contenu iso-8859-1 n'est pas de l'UTF-8 valide : preuve qu'on n'a rien ré-encodé
        with self.assertRaises(UnicodeDecodeError):
            saved.decode("utf-8")

    def test_beta_pagination_followed_not_guessed(self):
        self.run_cmd("full")
        got = {r[0].rsplit("/", 1)[1]: r[2] for r in self.rows("url LIKE '%viewtopic-4257-%'")}
        self.assertEqual(got, {"viewtopic-4257-1.html": 200, "viewtopic-4257-2.html": 200, "viewtopic-4257-3.html": 200})

    def test_css_urls_and_assets_followed(self):
        self.run_cmd("full")
        urls = [r[0] for r in self.rows("kind='asset'")]
        self.assertTrue(any(u.endswith("/css/definitive.css?v=55") for u in urls))
        self.assertTrue(any("assemblee_assemblee.jpg" in u for u in urls), "url() des CSS suivies")
        self.assertTrue(any("/avatars/8577.jpg" in u for u in urls))

    def test_resume_makes_no_new_requests(self):
        self.run_cmd("full")
        n = len(self.site.hits)
        self.run_cmd("full")
        # seul robots.txt peut être redemandé ; aucune page déjà prise ne l'est à nouveau
        self.assertTrue(all(p.endswith("robots.txt") for _, p, _ in self.site.hits[n:]), self.site.hits[n:])

    def test_resume_after_interruption(self):
        self.run_cmd("full", "--only", "gamma2/galaxie2")
        db = sqlite3.connect(os.path.join(self.out, "manifest.sqlite"))
        db.execute("UPDATE urls SET status=NULL, path=NULL WHERE kind='topic'")
        db.commit(); db.close()
        self.run_cmd("full", "--only", "gamma2/galaxie2")
        self.assertTrue(all(r[2] == 200 for r in self.rows("kind='topic' AND url LIKE '%gamma2%'")))

    def test_resume_starts_with_interrupted_page(self):
        self.run_cmd("inventory")
        db = sqlite3.connect(os.path.join(self.out, "manifest.sqlite"))
        self.assertTrue(db.execute("SELECT value FROM state WHERE key='last_url'").fetchone())
        # coupure simulée en plein téléchargement d'une page de topic
        target = db.execute("SELECT url FROM urls WHERE kind='topic' ORDER BY rowid DESC LIMIT 1").fetchone()[0]
        db.execute("INSERT OR REPLACE INTO state(key, value) VALUES ('current_url', ?)", (target,))
        db.commit(); db.close()
        n = len(self.site.hits)
        self.run_cmd("full")
        pages = [p for _, p, _ in self.site.hits[n:] if not p.endswith("robots.txt")]
        self.assertTrue(target.endswith(pages[0]), (target, pages[:3]))

    def test_outage_pages_retried_on_next_launch(self):
        # le site « coupe » : erreur réseau, compteur d'essais épuisé
        self.run_cmd("inventory")
        db = sqlite3.connect(os.path.join(self.out, "manifest.sqlite"))
        db.execute("UPDATE urls SET status=-1, tries=9, path=NULL WHERE url LIKE '%/186/page2'")
        db.commit(); db.close()
        self.run_cmd("inventory")
        self.assertEqual(self.rows("url LIKE '%/186/page2'")[0][2], 200)

    def test_only_filter(self):
        self.run_cmd("full", "--only", "gamma2/galaxie2")
        urls = [r[0] for r in self.rows()]
        self.assertFalse(any("galaxie3" in u for u in urls if "/forums/9" in u and r_status(self, u) == 200))
        self.assertFalse(any("/beta2/" in u and r_status(self, u) == 200 for u in urls))

    def load_json(self, rel):
        with open(os.path.join(self.out, "json", rel), encoding="utf-8") as f:
            return json.load(f)

    def test_json_archive_written_alongside_html(self):
        self.run_cmd("full")
        g = self.load_json("gamma2/galaxie11/forums/1583/topics/12693.json")
        self.assertEqual(g["titre"], "Non mais en fait on veut vraiment !")
        self.assertEqual(g["forum_nom"], "Assemblée Galactique")
        self.assertEqual(g["pages"], 2)
        self.assertEqual(g["sondage"]["total"], 26)
        self.assertEqual(g["sondage"]["options"][0]["votes"], 18)
        self.assertEqual(g["sondage"]["fin"], "2018-02-01 21:46")
        posts = g["messages"]["1"]
        self.assertEqual(len(posts), 10)
        self.assertEqual((posts[0]["id"], posts[0]["grade"], posts[0]["auteur"]), (244405, "Cdt.", "vakarm"))
        self.assertEqual(posts[0]["date"], "2018-01-30 21:46")
        self.assertEqual(posts[0]["compteur"], 62)
        self.assertEqual(posts[0]["soutien"], 2)
        self.assertEqual(posts[1]["positifs"], {"efforts": 1, "adapte": 1})  # libellés d'origine
        self.assertIn("Rebelote", posts[0]["texte"])
        self.assertNotIn("<", posts[0]["texte"])
        self.assertTrue(any(p.get("edite") for p in posts))
        # le score affiché = positifs - négatifs, sur chaque message
        for p in posts:
            self.assertEqual(p["score"], sum(p.get("positifs", {}).values()) - sum(p.get("negatifs", {}).values()))
        # page 2 fusionnée dans le même fichier
        self.assertEqual(sorted(g["messages"]), ["1", "2"])

    def test_json_beta_and_list(self):
        self.run_cmd("full")
        b = self.load_json("beta2/galaxie0/forums/1/topics/4257.json")
        self.assertEqual(b["titre"], "Gouvernement")
        self.assertEqual(b["sondage"]["total"], 66)
        p = b["messages"]["1"]
        self.assertEqual(len(p), 20)
        self.assertEqual((p[0]["auteur"], p[0]["id"], p[0]["date_sans_annee"]), ("Largo", 91666, "02/05 23:17"))
        self.assertNotIn("grade", p[0])
        self.assertEqual(p[0]["negatifs"], {"hors_sujet": 1})
        self.assertEqual(p[0]["positifs"], {"adapte": 4})
        self.assertIn("Voilà", p[0]["texte"])  # accents décodés depuis l'iso-8859-1
        lst = self.load_json("gamma2/galaxie2/forums/186/sujets.json")
        self.assertEqual(lst["nom"], "Assemblée Galactique d'ESPOIR")
        t = lst["sujets"]["4543"]
        self.assertEqual((t["titre"], t["reponses"], t["dernier"]), ("ET IN ARCADIA EGO", 9, "2013-11-28 19:38"))
        self.assertEqual(t["dernier_auteur"], "Cdt. Lantesh")
        self.assertTrue(any(s.get("supprimes") for s in lst["sujets"].values()))
        self.assertTrue(any(s.get("sondage") for s in lst["sujets"].values()))

    def test_commandants_directory(self):
        self.run_cmd("full")
        c = self.load_json("commandants.json")["commandants"]
        v = c["vakarm"]
        self.assertEqual(v["respect_max"], 62)
        self.assertIn("gamma2/galaxie11", v["galaxies"])
        self.assertEqual(v["respect_par_galaxie"]["gamma2/galaxie11"], 62)
        self.assertEqual(v["sujets_crees"][0]["ref"], "gamma2/galaxie11/1583/12693")
        self.assertTrue(all(s["messages"] >= 1 for s in v["sujets_participes"]))
        largo = c["Largo"]  # Beta : pseudo sans grade
        self.assertEqual(largo["respect_max"], 442)
        self.assertEqual(largo["galaxies"], ["beta2/galaxie0"])
        self.assertEqual(largo["sujets_crees"][0]["titre"], "Gouvernement")
        # avatars reliés au commandant et réellement présents dans la capture
        for name, gal in (("vakarm", "gamma2/galaxie11"), ("Largo", "beta2/galaxie0")):
            av = c[name]["avatars_par_galaxie"][gal]
            self.assertTrue(av)
            for rel in av:
                self.assertTrue(os.path.isfile(os.path.join(self.out, "raw", rel)), rel)
        self.assertTrue(c["vakarm"]["avatars_par_galaxie"]["gamma2/galaxie11"][0].endswith("/avatars/8577.jpg"))
        self.assertTrue(c["Largo"]["avatars_par_galaxie"]["beta2/galaxie0"][0].endswith("/beta2/galaxie_0/avatars/1340.jpg"))
        self.assertEqual(len(c["gOlstein"]["sujets_crees"]), 0)
        self.assertEqual(c["gOlstein"]["sujets_participes"][0]["messages"], 3 * 2)  # 2 messages par page, 3 pages

    def test_json_rebuilt_from_raw_and_formats(self):
        self.run_cmd("full", "--formats", "html")
        self.assertFalse(os.path.exists(os.path.join(self.out, "json")))
        self.run_cmd("json")
        self.assertTrue(os.path.exists(os.path.join(self.out, "json", "gamma2/galaxie11/forums/1583/topics/12693.json")))

    def test_json_only_keeps_no_raw_html(self):
        self.run_cmd("full", "--formats", "json")
        self.assertFalse(os.path.exists(os.path.join(self.out, "raw", "127.0.0.1_%d" % self.site.gamma_port, "archives")))
        self.assertTrue(os.path.exists(os.path.join(self.out, "json", "gamma2/galaxie11/forums/1583/topics/12693.json")))
        # les ressources (avatars, CSS) restent conservées même sans le format html
        host = "127.0.0.1_%d" % self.site.gamma_port
        self.assertTrue(os.path.isfile(os.path.join(self.out, "raw", host, "avatars", "8577.jpg")))
        self.assertTrue(any(f.startswith("definitive") for f in os.listdir(os.path.join(self.out, "raw", host, "css"))))

    def test_report_runs(self):
        self.run_cmd("inventory")
        import io, contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.run_cmd("report")
        txt = buf.getvalue()
        self.assertIn("topics", txt)
        self.assertIn("gamma2/galaxie2", txt)


def r_status(t, u):
    rows = t.rows("url=?".replace("?", "'%s'" % u))
    return rows[0][2] if rows else None


class UnitTests(unittest.TestCase):
    def test_local_path_safe_and_unique(self):
        a = ac.local_path("https://www.apocalypsis.org/archives/gamma2/galaxie1/forums/2/page1")
        b = ac.local_path("https://www.apocalypsis.org/archives/gamma2/galaxie1/forums/2/topics/2343/page1")
        c = ac.local_path("https://www.apocalypsis.org/css/definitive.css?v=55")
        d = ac.local_path("https://www.apocalypsis.org/css/definitive.css?v=56")
        self.assertEqual(len({a, b, c, d}), 4)
        for p in (a, b, c, d, ac.local_path("https://x.org/a/../../etc/passwd")):
            self.assertFalse(p.startswith("/") or ".." in p.split("/"))

    def test_default_delay_is_half_second(self):
        import unittest.mock as um
        with um.patch.object(ac.Crawler, "run", lambda self: setattr(ac, "_last_delay", self.args.delay)):
            ac.main(["inventory", "--out", tempfile.mkdtemp()])
        self.assertEqual(ac._last_delay, 0.5)

    def test_fetcher_waits_between_requests(self):
        import time
        f = ac.Fetcher(0.5, 1, None)
        f._wait()
        t = time.monotonic(); f._wait()
        self.assertGreaterEqual(time.monotonic() - t, 0.45)

    def test_classify(self):
        s = ac.Scope("https://www.apocalypsis.org", "https://archivesbeta.apocalypsis.org")
        g = "https://www.apocalypsis.org"
        self.assertEqual(s.classify(g + "/archives/gamma2/galaxie1/forums/2/topics/2343/page1"), ac.TOPIC)
        self.assertEqual(s.classify(g + "/archives/gamma2/galaxie1/forums/2/page3"), ac.STRUCT)
        self.assertEqual(s.classify(g + "/avatars/12.jpg"), ac.ASSET)
        self.assertIsNone(s.classify(g + "/archives/gamma2/warn/244662"))
        self.assertIsNone(s.classify("https://forum.apocalypsis.org/"))
        self.assertIsNone(s.classify(g + "/boutique"))
        self.assertEqual(s.classify("https://archivesbeta.apocalypsis.org/beta1/galaxie_0/forums_galactiques/1/1/viewtopic-1531-1.html"), ac.TOPIC)

    def test_asset_links_kept_without_known_extension(self):
        html = b'<img src="/gen/img.php?id=3"><link rel=stylesheet href="/css/x"><a href="/archives/gamma2">p</a>'
        got = ac.extract_asset_links(html, "text/html", "http://h/a/")
        self.assertEqual(got, {"http://h/gen/img.php?id=3", "http://h/css/x"})
        s = ac.Scope("http://h", "http://b")
        self.assertEqual(s.classify("http://h/gen/img.php?id=3", True), ac.ASSET)
        self.assertIsNone(s.classify("https://ajax.googleapis.com/x.js", True))
        css = b"@import 'more.css'; a{background:url(i/a.png)}"
        self.assertEqual(ac.extract_links(css, "text/css", "http://h/css/a.css"),
                         {"http://h/css/i/a.png", "http://h/css/more.css"})

    def test_extract_links_handles_quotes_and_entities(self):
        html = b'<a href="a.html?x=1&amp;y=2">x</a><img src=b.png><a href=\'c.html\'>'
        got = ac.extract_links(html, "text/html", "http://h/dir/")
        self.assertEqual(got, {"http://h/dir/a.html?x=1&y=2", "http://h/dir/b.png", "http://h/dir/c.html"})


if __name__ == "__main__":
    unittest.main()
