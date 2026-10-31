"use strict";
const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString("fr-FR", {maximumFractionDigits: 1});
const div = (a, b) => (b ? a / b : 0);
// [galaxie, sujets, messages, commandants, mots] -> colonnes affichées
// [libellé, valeur, unité]
const METRICS = [
  ["Sujets", r => r[1], "sujets"],
  ["Messages", r => r[2], "messages"],
  ["Commandants", r => r[3], "commandants"],
  ["Messages par commandant", r => div(r[2], r[3]), "messages / commandant"],
  ["Mots", r => r[4], "mots"],
  ["Mots par commandant", r => div(r[4], r[3]), "mots / commandant"],
];
const SVGNS = "http://www.w3.org/2000/svg";
const el = (n, a, txt) => { const e = document.createElementNS(SVGNS, n); for (const k in a) e.setAttribute(k, a[k]); if (txt != null) e.textContent = txt; return e; };

function drawChart(rows, mi) {
  const svg = $("chart"); svg.replaceChildren();
  const W = 860, H = 340, L = 70, R = 14, T = 14, B = 80;
  const vals = rows.map(METRICS[mi][1]);
  const max = Math.max(...vals, 1);
  const x = i => L + (rows.length > 1 ? i * (W - L - R) / (rows.length - 1) : 0);
  const y = v => T + (H - T - B) * (1 - v / max);
  for (let k = 0; k <= 4; k++) {
    const v = max * k / 4, yy = y(v);
    svg.append(el("line", {x1: L, x2: W - R, y1: yy, y2: yy, stroke: "rgba(70,140,230,.28)"}));
    svg.append(el("text", {x: L - 6, y: yy + 4, "text-anchor": "end", fill: "#9db0cf", "font-size": 11}, fmt(v)));
  }
  svg.append(el("polyline", {points: vals.map((v, i) => `${x(i)},${y(v)}`).join(" "), fill: "none", stroke: "#ffc21a", "stroke-width": 2}));
  const pts = [];
  rows.forEach((r, i) => {
    const c = el("circle", {cx: x(i), cy: y(vals[i]), r: 3.5, fill: "#ffc21a"});
    svg.append(c); pts.push(c);
    const lab = el("text", {transform: `translate(${x(i)},${H - B + 12}) rotate(-60)`, "text-anchor": "end", fill: "#9db0cf", "font-size": 10}, r[0].replace(" · Galaxie ", " G").replace(" · ", " "));
    svg.append(lab);
  });
  // étiquette : galaxie, valeur et unité du point le plus proche du pointeur
  const tip = el("g", {"pointer-events": "none", visibility: "hidden"});
  const box = el("rect", {rx: 3, fill: "rgba(4,9,22,.95)", stroke: "#ffc21a"});
  const l1 = el("text", {fill: "#9db0cf", "font-size": 12});
  const l2 = el("text", {fill: "#ffc21a", "font-size": 14, "font-weight": 700});
  tip.append(box, l1, l2); svg.append(tip);
  let cur = -1;
  const show = i => {
    if (cur >= 0) pts[cur].setAttribute("r", 3.5);
    cur = i; pts[i].setAttribute("r", 6);
    l1.textContent = rows[i][0];
    l2.textContent = `${fmt(vals[i])} ${METRICS[mi][2]}`;
    const w = Math.max(l1.getComputedTextLength(), l2.getComputedTextLength()) + 16;
    const bx = Math.min(Math.max(x(i) - w / 2, 2), W - w - 2), by = Math.max(y(vals[i]) - 54, 2);
    box.setAttribute("x", bx); box.setAttribute("y", by); box.setAttribute("width", w); box.setAttribute("height", 42);
    l1.setAttribute("x", bx + 8); l1.setAttribute("y", by + 16); l2.setAttribute("x", bx + 8); l2.setAttribute("y", by + 34);
    tip.setAttribute("visibility", "visible");
  };
  svg.onpointermove = e => {
    const k = W / svg.getBoundingClientRect().width, px = (e.clientX - svg.getBoundingClientRect().left) * k;
    let best = 0;
    for (let i = 1; i < rows.length; i++) if (Math.abs(x(i) - px) < Math.abs(x(best) - px)) best = i;
    show(best);
  };
  svg.onpointerleave = () => { tip.setAttribute("visibility", "hidden"); if (cur >= 0) pts[cur].setAttribute("r", 3.5); cur = -1; };
}

fetch("stats.json").then(r => r.json()).then(rows => {
  const tb = document.querySelector("#t tbody");
  tb.innerHTML = rows.map(r => `<tr><td style="white-space:nowrap">${r[0]}</td><td class="n">${fmt(r[1])}</td><td class="n">${fmt(r[2])}</td><td class="n">${fmt(r[3])}</td><td class="n">${fmt(div(r[2], r[3]))}</td><td class="n">${fmt(r[4])}</td><td class="n">${fmt(div(r[4], r[3]))}</td></tr>`).join("");
  $("t").hidden = false; $("status").remove();
  const sel = $("metric");
  METRICS.forEach((m, i) => sel.append(new Option(m[0], i)));
  sel.onchange = () => drawChart(rows, +sel.value);
  drawChart(rows, 0);
}).catch(e => { $("status").textContent = "Statistiques indisponibles : " + e.message; });
