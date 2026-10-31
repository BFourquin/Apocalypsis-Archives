"use strict";
const norm = s => Array.from(s, ch => ch.toLowerCase().normalize("NFD")[0] || ch).join("");
const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
const $ = id => document.getElementById(id);
const POS = {efforts: "Efforts visibles", adapte: "Message adapté", remarquable: "Message remarquable", humour: "Humour décapant", roleplay: "Role play intéressant"};
const NEG = {orthographe: "Orthographe insuffisante", presentation: "Présentation bâclée", hors_sujet: "Hors sujet", hors_roleplay: "Hors role play", insultant: "Message insultant"};
const SHOW = 100;
const pl = (n, one, many) => (n > 1 ? many : one); // 0 et 1 : singulier
let liste = null, names = [], docs = null, prof = null, curId = -1, rows = [], shownRows = 0;

async function getJson(url) { const r = await fetch(url); if (!r.ok) throw new Error(url + " : " + r.status); return r.json(); }

function results() {
  const q = norm($("q").value).trim();
  if (!q) { $("list").hidden = true; $("status").textContent = `${liste.a.length} commandants et coalitions référencés`; return; }
  const found = [];
  liste.a.forEach((p, i) => {
    const k = names[i].indexOf(q);
    if (k >= 0) found.push([p, i, k === 0 ? 0 : 1]);
  });
  found.sort((a, b) => a[2] - b[2] || b[0][1] - a[0][1]);
  $("status").textContent = `${found.length} résultat(s)`;
  $("list").hidden = !found.length;
  $("list").innerHTML = found.slice(0, 100).map(([p, i]) =>
    `<div class="r"><a href="?id=${i}">${esc(p[0])}</a>
     <small>${p[1]} message(s) · ${p[2]} galaxie(s)${p[3] ? ` · ${p[3]} en Chroniques` : ""}</small></div>`).join("") + (found.length > 100 ? "<small>Affinez la recherche pour voir la suite.</small>" : "");
}

async function showProfile(i) {
  $("find").hidden = true; $("profile").hidden = false;
  $("profile").innerHTML = "<p>Chargement…</p>";
  const [sh, d] = await Promise.all([getJson(`auteurs/${Math.floor(i / liste.shard)}.json`), docs || getJson("search/docs.json")]);
  docs = d; prof = sh[i]; curId = i;
  if (!prof) { $("profile").innerHTML = "<p>Fiche introuvable.</p>"; return; }
  const created = prof.top.reduce((s, t) => s + t[4], 0);
  const badges = (o, L) => Object.entries(o).map(([k, v]) => `<span>${L[k] || k} : ${v}</span>`).join("");
  $("profile").innerHTML = `<p class="shade"><a href="commandants.html">‹ Nouvelle recherche</a></p>
    <div class="panel prof"><div class="av${prof.av ? "" : " empty"}">${prof.av ? `<img src="${esc(prof.av)}" alt="" onerror="this.parentNode.classList.add('empty');this.remove()">` : ""}</div>
    <div><h1>${esc(prof.n)}</h1>
    <div class="stats">${prof.rd != null ? `<div><b>${prof.rd}</b>Respect diplomatique</div>` : ""}<div><b>${prof.m}</b>${pl(prof.m, "Message", "Messages")}</div><div><b>${prof.top.length}</b>${pl(prof.top.length, "Sujet participé", "Sujets participés")}</div><div><b>${created}</b>${pl(created, "Sujet créé", "Sujets créés")}</div>
    </div>
    <details><summary>Votes reçus en assemblée</summary>
      <div class="badges">${badges(prof.p, POS)}${badges(prof.q, NEG)}</div></details></div></div>
    ${prof.gal.length ? `<div class="panel"><b>Par galaxie</b><table><tr><th>Galaxie</th><th class="n">Messages</th><th class="n">Sujets</th><th>Premier message</th><th>Dernier message</th></tr>` +
    prof.gal.map(g => `<tr><td>${esc(g[0])}</td><td class="n">${g[1]}</td><td class="n">${g[2]}</td><td>${esc(g[3])}</td><td>${esc(g[4])}</td></tr>`).join("") +
    `</table></div>` : ""}
    <p class="tabs wide" id="tabs"><a href="#description" id="tab-d" data-tab="d"${prof.d ? "" : ' class="off" aria-disabled="true" tabindex="-1"'}>Description publique</a><a href="#interventions" id="tab-i" data-tab="i"${prof.m ? "" : ' class="off" aria-disabled="true" tabindex="-1"'}>Interventions</a><a href="#chroniques" id="tab-c" data-tab="c"${prof.ch ? "" : ' class="off" aria-disabled="true" tabindex="-1"'}>Chroniques</a></p>
    <div class="panel desc" id="desc" hidden></div>
    <div class="panel" id="inter"><b>Participations</b> <select id="gf"><option value="">Toutes les galaxies</option>${prof.gal.map((g, j) => `<option value="${j}">${esc(g[0])}</option>`).join("")}</select>
    <div id="rows"></div><button id="more" hidden>Suite</button></div>
    <div class="panel" id="chro" hidden><b>Participations aux Chroniques</b> <small>(forum hors galaxie)</small>${chroRows(prof.ch || [])}</div>`;
  $("tabs").addEventListener("click", e => {
    const a = e.target.closest("a[data-tab]");
    if (!a) return;
    e.preventDefault();
    if (!a.classList.contains("off")) showTab(a.dataset.tab);
  });
  showTab(prof.d ? "d" : prof.m ? "i" : "c");
  $("gf").addEventListener("change", fillRows);
  $("more").addEventListener("click", moreRows);
  document.title = prof.n + " - Archives Apocalypsis";
  fillRows();
}

// description publique : une rubrique par titre (« Description publique », « Civilisation », « Gouvernement »), chargée à la demande
async function showTab(t) {
  $("tab-d").classList.toggle("cur", t === "d");
  $("tab-i").classList.toggle("cur", t === "i");
  $("tab-c").classList.toggle("cur", t === "c");
  $("desc").hidden = t !== "d";
  $("inter").hidden = t !== "i";
  $("chro").hidden = t !== "c";
  if (t !== "d" || $("desc").dataset.ready) return;
  $("desc").dataset.ready = "1";
  $("desc").innerHTML = "<p>Chargement…</p>";
  try {
    const all = await getJson(`auteurs/d${Math.floor(curId / liste.shard)}.json`);
    let last = null, out = "";
    for (const [titre, html] of all[curId] || []) {
      const [rub, champ] = titre.split(" · ");
      if (rub !== last) { out += `<h3>${esc(rub)}</h3>`; last = rub; }
      out += champ === "Nom" ? `<p class="dtitle">Nom : <span>${html}</span></p>` : `<div class="dtitle">${esc(champ || "")}</div><div class="dbody">${html}</div>`;
    }
    $("desc").innerHTML = out || "<p>Aucune description.</p>";
  } catch (e) { $("desc").textContent = "Erreur : " + e.message; delete $("desc").dataset.ready; }
}

// sujets des Chroniques (hors galaxie) : [id, titre, messages, premier, dernier, créateur, pages]
const chroRows = ch => ch.map(([id, titre, n, first, last, cr, pages]) =>
  `<div class="r"><a href="www.apocalypsis.org/archives/chroniques/topics/${id}/page${pages[0]}.html">${esc(titre)}</a>${cr ? '<span class="tag">auteur</span>' : ""}
   <small>Chroniques · ${n} message(s) · ${esc(first)}${last !== first ? " → " + esc(last) : ""} · ${pages.map(p => `<a href="www.apocalypsis.org/archives/chroniques/topics/${id}/page${p}.html">p.${p}</a>`).join(" ")}</small></div>`).join("");

function fillRows() {
  const g = $("gf").value;
  rows = prof.top.filter(t => g === "" || t[5] === +g); shownRows = 0; $("rows").innerHTML = ""; moreRows();
}
function moreRows() {
  const batch = rows.slice(shownRows, shownRows + SHOW); shownRows += batch.length;
  $("rows").insertAdjacentHTML("beforeend", batch.map(([ds, n, first, last, cr]) => {
    const [path, titre, gi] = docs.docs[ds[0]];
    const pages = ds.map(d => `<a href="${esc(docs.docs[d][0])}">p.${docs.docs[d][3]}</a>`).join(" ");
    return `<div class="r"><a href="${esc(path)}">${esc(titre)}</a>${cr ? '<span class="tag">auteur</span>' : ""}
      <small>${esc(docs.groups[gi])} · ${n} message(s) · ${esc(first)}${last !== first ? " → " + esc(last) : ""} · ${pages}</small></div>`;
  }).join(""));
  $("more").hidden = shownRows >= rows.length;
  if (!rows.length) $("rows").textContent = "Aucune participation.";
}

async function init() {
  liste = await getJson("auteurs/liste.json");
  names = liste.a.map(p => norm(p[0]));
  const qs = new URLSearchParams(location.search);
  const who = qs.get("n"); // lien depuis un message d'archive : recherche par nom
  let id = qs.get("id");
  if (who !== null) { const k = names.indexOf(norm(who).trim()); if (k >= 0) id = String(k); else { $("q").value = who; } }
  if (id !== null && liste.a[+id]) return showProfile(+id);
  $("q").addEventListener("input", results);
  results();
}
init().catch(e => { $("status").textContent = "Erreur : " + e.message; });
