/* zoom au clic sur les images de la galerie (Échap, clic ou flèches pour naviguer) */
(() => {
  const links = [...document.querySelectorAll(".gal a")];
  if (!links.length) return;
  const box = document.createElement("div");
  box.className = "zoom";
  box.hidden = true;
  box.innerHTML = '<img alt=""><p class="cap"></p><button class="x" aria-label="Fermer">×</button><button class="nav prev" aria-label="Précédente">‹</button><button class="nav next" aria-label="Suivante">›</button><a class="orig" target="_blank" rel="noopener">Ouvrir l\'image seule</a>';
  document.body.appendChild(box);
  const img = box.querySelector("img"), cap = box.querySelector(".cap"), orig = box.querySelector(".orig");
  let i = 0;
  const show = n => {
    i = (n + links.length) % links.length;
    const a = links[i], f = a.closest("figure").querySelector("figcaption");
    img.src = a.href;
    img.alt = a.querySelector("img").alt;
    cap.textContent = f ? f.textContent : "";
    orig.href = a.href;
    box.hidden = false;
    document.body.style.overflow = "hidden";
  };
  const close = () => { box.hidden = true; img.removeAttribute("src"); document.body.style.overflow = ""; };
  links.forEach((a, n) => a.addEventListener("click", e => {
    if (e.ctrlKey || e.metaKey || e.shiftKey) return;
    e.preventDefault();
    show(n);
  }));
  box.addEventListener("click", e => {
    if (e.target.closest(".prev")) show(i - 1);
    else if (e.target.closest(".next")) show(i + 1);
    else if (!e.target.closest(".orig")) close();
  });
  document.addEventListener("keydown", e => {
    if (box.hidden) return;
    if (e.key === "Escape") close();
    else if (e.key === "ArrowLeft") show(i - 1);
    else if (e.key === "ArrowRight") show(i + 1);
  });
})();
