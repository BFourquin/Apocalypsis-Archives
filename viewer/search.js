"use strict";
// Même normalisation que build_site.py (norm / tokens).
const norm = s => Array.from(s, ch => ch.toLowerCase().normalize("NFD")[0] || ch).join("");
const tokens = s => norm(s).match(/[a-z0-9]+/g) || [];
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const $ = id => document.getElementById(id);
const PER_PAGE = 20;
const FIELDS = {all: ["t", "c", "a"], t: ["t"], c: ["c"], a: ["a"]};
const WEIGHT = {t: 3, c: 1, a: 2};
let chron = -1, meta = null, hits = [], shown = 0, terms = [], people = null;
const shards = {};

async function getJson(url) { const r = await fetch(url); if (!r.ok) throw new Error(url + " : " + r.status); return r.json(); }
function shard(field, key) {
  const k = field + "/" + key;
  if (!shards[k]) shards[k] = getJson("search/" + k + ".json").catch(() => ({}));
  return shards[k];
}
function decode(s) { // "d,d.tf,..." (base 36, deltas) -> Map(doc -> tf)
  const m = new Map(); let prev = 0;
  for (const e of s.split(",")) { const [d, tf] = e.split("."); prev += parseInt(d, 36); m.set(prev, +tf || 1); }
  return m;
}
async function postings(tok, prefix, fields) {
  const out = new Map();
  await Promise.all(fields.map(async f => {
    const sh = await shard(f, tok.slice(0, 2));
    for (const t of prefix ? Object.keys(sh).filter(k => k.startsWith(tok)) : (sh[tok] ? [tok] : []))
      for (const [d, tf] of decode(sh[t])) out.set(d, (out.get(d) || 0) + tf * WEIGHT[f]);
  }));
  return out;
}

async function search(q, mode, group) {
  terms = tokens(q).filter(t => t.length >= 2);
  $("out").innerHTML = ""; $("out").hidden = true; $("more").hidden = true; $("who").hidden = true; hits = []; shown = 0;
  if (!terms.length) { $("status").textContent = q.trim() ? "Saisissez au moins un mot de 2 lettres." : ""; return; }
  $("status").textContent = "Recherche…";
  const fields = FIELDS[mode];
  const lists = await Promise.all(terms.map((t, i) => postings(t, i === terms.length - 1, fields)));
  let acc = null;
  for (const l of lists) {
    if (!acc) acc = new Map(l);
    else for (const d of [...acc.keys()]) l.has(d) ? acc.set(d, acc.get(d) + l.get(d)) : acc.delete(d);
  }
  hits = [...acc].filter(([d]) => group === "" ? meta.docs[d][2] !== chron : meta.docs[d][2] === +group).sort((a, b) => b[0] - a[0]); // du plus récent au plus ancien
  $("status").textContent = `${hits.length} page(s) de sujet trouvée(s)`;
  if (mode === "a") showPeople(q);
  more();
}

async function showPeople(q) { // fiches correspondantes, avec lien vers la liste de leurs participations
  if (!people) people = (await getJson("auteurs/liste.json")).a;
  const qn = norm(q).trim();
  const found = people.map((p, i) => [p, i]).filter(([p]) => norm(p[0]).includes(qn))
    .sort((a, b) => b[0][1] - a[0][1]).slice(0, 8);
  if (!found.length) return;
  $("who").hidden = false;
  $("who").innerHTML = `<b>Fiches correspondantes</b><br>` + found.map(([p, i]) =>
    `<a href="commandants.html?id=${i}">${esc(p[0])}</a> <small>${p[1]} message(s)</small>`).join(" · ");
}

async function more() {
  const batch = hits.slice(shown, shown + PER_PAGE); shown += batch.length;
  if (batch.length) $("out").hidden = false;
  const nodes = batch.map(([d]) => {
    const [path, titre, gi, page] = meta.docs[d];
    const div = document.createElement("div"); div.className = "r";
    div.innerHTML = `<a href="${esc(path)}">${esc(titre)}</a> <small>${esc(meta.groups[gi])} · page ${page}</small><p>…</p>`;
    $("out").appendChild(div);
    return [div.querySelector("p"), path];
  });
  $("more").hidden = shown >= hits.length;
  await Promise.all(nodes.map(([p, path]) => snippet(p, path)));
}

async function snippet(p, path) {
  try {
    const html = await (await fetch(path)).text();
    const dom = new DOMParser().parseFromString(html, "text/html");
    // texte des messages d'abord (Gamma : post_left/post_right, Beta : posts), sinon toute la page
    const cells = [...dom.querySelectorAll("td.post_left, td.post_right, td.posts")].map(c => c.textContent).join(" ¶ ");
    const text = (cells || dom.body.textContent).replace(/\s+/g, " ");
    const n = norm(text);
    let pos = -1;
    for (const t of terms) { const m = new RegExp("(^|[^a-z0-9])" + t).exec(n); if (m) { pos = m.index + m[1].length; break; } }
    if (pos < 0) { p.textContent = ""; return; }
    const s = Math.max(0, pos - 80), e = Math.min(text.length, pos + 160);
    p.innerHTML = (s ? "…" : "") + esc(text.slice(s, e)) + (e < text.length ? "…" : "");
    // surlignage : les mots sont comparés par leur forme normalisée (accents conservés à l'affichage)
    p.innerHTML = p.innerHTML.replace(/[^\s<>&;]+/g, w => terms.some(t => norm(w).startsWith(t)) ? `<mark>${w}</mark>` : w);
  } catch (e) { p.textContent = ""; }
}

async function init() {
  meta = await getJson("search/docs.json");
  const sel = $("g");
  chron = meta.groups.indexOf("Chroniques"); // forum hors galaxie : cherché seulement quand on le choisit, jamais dans « Toutes les galaxies »
  if (chron >= 0) sel.add(new Option("Chroniques (hors galaxie)", chron));
  meta.groups.forEach((g, i) => { if (i !== chron) sel.add(new Option(g, i)); }); // déjà du plus récent au plus ancien
  const u = new URLSearchParams(location.search);
  $("q").value = u.get("q") || ""; sel.value = u.get("g") || ""; $("m").value = u.get("m") || "all";
  const go = () => search($("q").value, $("m").value, sel.value);
  $("f").addEventListener("submit", ev => {
    ev.preventDefault();
    history.replaceState(null, "", `?q=${encodeURIComponent($("q").value)}&m=${$("m").value}&g=${sel.value}`);
    go();
  });
  $("m").addEventListener("change", () => $("f").requestSubmit());
  sel.addEventListener("change", () => $("f").requestSubmit());
  $("more").addEventListener("click", more);
  if ($("q").value) go();
}
init().catch(e => { $("status").textContent = "Erreur : " + e.message; });
