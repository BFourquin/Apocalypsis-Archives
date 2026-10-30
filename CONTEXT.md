# Archivage du forum d'Apocalypsis — Fichier de contexte

> Document de cadrage. Il décrit le besoin, ce que l'on sait de la source, les contraintes et les questions ouvertes. **Aucun choix de technologie ni d'hébergement n'est arrêté ici** : les options sont listées à titre de comparaison.

## 1. Objectif

Apocalypsis est un jeu en ligne de rôle et de conquête spatiale dont l'intérêt principal est son forum, où se joue la diplomatie entre joueurs. Le jeu risque de disparaître. Le projet vise à **préserver l'intégralité du contenu des forums des archives** (environ 21 ans) sous une forme pérenne, consultable sans le site d'origine.

### Exigences
1. **Extraction complète** du contenu des forums des archives (messages, sondages, métadonnées).
2. **Reproduction de l'interface existante.** Les archives les plus anciennes utilisent une ancienne interface, qui doit aussi être conservée.
3. **Sondages** : à conserver (certains topics en contiennent).
3 bis. **Classements** des anciennes galaxies (Beta) : fichiers de classement des joueurs à conserver (voir 2.10).

### Souhaits
4. **Recherche** dans l'ensemble des archives.
5. **Statistiques** sur la vie du jeu au fil des années.
6. **Hébergement gratuit** (GitHub Pages cité en exemple), **sans nuisance visuelle ajoutée** (pas de publicité, pas de bandeau, pas de ralentissement imposé).

### Hors périmètre
- `forum.apocalypsis.org` : forum HRP (hors role play), **explicitement exclu**.
- Le jeu lui-même (mécaniques, comptes, base de jeu).

## 2. Source

- Index des archives : <https://www.apocalypsis.org/archives>
- Exemple de topic : <https://www.apocalypsis.org/archives/gamma2/galaxie1/forums/2/topics/2343/page1>
- Exemple de topic avec sondage : <https://www.apocalypsis.org/archives/gamma2/galaxie11/forums/1583/topics/12199/page1>

### 2.1 Arborescence des archives (relevée le 28/10/2026)

| Niveau | Contenu |
|---|---|
| Gamma 1 | Galaxies 0 à 6 (2007 → juin 2012) |
| Gamma 2 | Galaxies 0 à 23 archivées (2012 → 2025) ; **Galaxie 24 active depuis le 26/10/2025** (non archivée à ce jour) |
| Beta 1 | Galaxies 0 (la 1 et la 2 n'existent pas), 2005 |
| Beta 2 | Galaxies 0 et 1 (2005 → mai 2006) |
| Beta 3 | Galaxies 0 à 2 (2006 → 2007 ; la Galaxie 2 débute le 22/01/2006, avant les deux autres) |

Soit 37 galaxies archivées (7 + 24 + 1 + 2 + 3), plus la Galaxie 24 encore active. Remarque : l'index affiche le lien de `beta3/galaxie2` dans la colonne « Beta 2 » ; la page elle-même (fil d'Ariane `beta3 › Galaxie 2`) confirme qu'elle appartient à Beta 3, il s'agit d'un défaut de présentation de l'index. Les dates exactes de début et de fin de chaque galaxie figurent sur la page d'index (utile pour les statistiques et le contrôle de cohérence).

### 2.2 Schéma d'URL observé

```
/archives/{partie}/{galaxie}/forums
/archives/{partie}/{galaxie}/forums/{id_forum}/page{n}
/archives/{partie}/{galaxie}/forums/{id_forum}/topics/{id_topic}/page{n}
```

- Les identifiants de topics croissent dans le temps au sein de Gamma 2 (2343 en Galaxie 1, 12199 et 12693 en Galaxie 11), sans repartir de zéro par galaxie. En revanche **la numérotation n'est pas commune à toutes les parties** : un topic de Beta 2 (2006) porte le n° 4257, supérieur à celui de Gamma 2 Galaxie 1 (2013). Idem pour les messages (91666 → 92413 en Beta 2, 244405 → 244662 en Gamma 2). Clé à retenir : `(partie, id)` et non `id` seul.
- **Gamma : un seul forum public par galaxie**, l'Assemblée Galactique (forum 2 en Galaxie 1, 186 en Galaxie 2, 1583 en Galaxie 11). **Beta : plusieurs catégories par galaxie** (3 en Beta 1 Galaxie 0), plus un classement (voir 2.10).
- En Beta, les pages sont des fichiers statiques sur un autre hôte, `archivesbeta.apocalypsis.org`, avec un schéma d'URL différent (liens relatifs, `viewforum-{id_forum}-{page}.html`, `viewtopic-{id_topic}-{page}.html`) ; détail en 2.10.
- Fil d'Ariane : Archives › partie › galaxie › Forums › forum › topic.
- Pagination : « Pages : 1 2 … » en haut et en bas de chaque topic.

### 2.3 Structure d'un message (topic)

- Titre du topic
- Auteur : grade + nom du commandant (ex. « Cdt. … »)
- Compteur « Cauchemards provoqués : N »
- Avatar (`/avatars/{id}.gif|png|jpg`)
- Date/heure de publication au format `JJ/MM/AAAA ETU HH:MM`
- Mention éventuelle « Message édité »
- Icônes/badges de statut (ex. `images/registered.gif`)
- **Score du message** et bloc de **détail de notation** : 5 critères négatifs (orthographe insuffisante, présentation bâclée, hors sujet, hors role play, message insultant) et 5 critères positifs (efforts visibles, torture adapté, supplice répugnant, rire glaçant, présence maléfique — **libellés alternatifs (easter egg Halloween), à remplacer par les libellés d'origine, voir 2.9**), chacun avec un compteur
- Lien « Prévenir Dieu » (signalement) : **supprimé dans la copie d'archive** (décision utilisateur) ; conservé dans la capture brute
- Corps du message : texte mis en forme (gras, italique, listes), liens externes (YouTube, hébergeurs d'images, etc.), images

### 2.4 Structure d'un sondage

- Affiché **en haut de la page 1 du topic**, entre le titre et le premier message.
- Question (sous-titre), puis tableau d'options : texte, nombre de votes, et une colonne qui semble contenir la barre de résultat.
- Ligne « Total : N vote(s) » et « Ce vote a pris fin le : … ».
- **Pas de détail des votants** visible : uniquement des totaux.
- Choix unique dans les deux exemples observés (la somme des options égale le total) ; à vérifier sur d'autres cas.
- **HTML brut (topic 12693, Galaxie 11)** : `<div class="poll"><h2>question</h2><table class="listing">…</table>Ce vote a pris fin le&nbsp;: …</div>`. Chaque option est une ligne `<tr><td>texte</td><td>votes</td><td><div style="height: 9px; width: Npx; background-color:#81F0FF" /></td></tr>`. La barre est un simple `div` coloré (pas d'image) : sa largeur est proportionnelle à l'option la plus votée, qui vaut toujours 100 px (18 votes → 100 px ; 8 votes → 44 px). La largeur est donc redondante avec les votes, et le `div` auto-fermé (`/>`) est du HTML invalide que les navigateurs tolèrent.

### 2.5 Dates

**Gamma 2 : confirmé** (par l'utilisateur) — l'année « ETU » est l'année réelle plus 1000 (ex. `27/09/1017 ETU` ↔ 27/09/2017, `30/01/1018 ETU` ↔ 30/01/2018 en Galaxie 11).

**Beta : l'année n'est pas affichée.** Les messages portent seulement `JJ/MM ETU HH:MM` (ex. `02/05 ETU 23:17`). L'année doit être déduite des dates de début et de fin de la galaxie de l'index : en Beta 1 Galaxie 0 (10/05/2005 → 31/08/2005), `31/08` ↔ 2005 ; en Beta 2 Galaxie 0 (01/09/2005 → 07/05/2006), `02/05` ↔ 2006. Pour les galaxies qui durent plus d'un an (Beta 3 : 15/05/2006 → 17/09/2007 ; Gamma 1, déclarée de même interface que Gamma 2, affiche probablement l'année, à vérifier), il faut reconstituer l'année en parcourant les messages dans l'ordre (identifiant croissant) et en comptant les retours en arrière du calendrier (ex. `31/12` → `01/01`). À valider sur ces galaxies, et à vérifier si Gamma 1 affiche l'année. Cela conditionne les statistiques chronologiques.

### 2.6 HTML brut observé (page de topic, Galaxie 11)

Fichier de 43 Ko pour une page de 10 messages (≈ 4 Ko/message, hors ressources).

- **Squelette** : HTML 4.01 Transitional, UTF-8, généré par PHP. Commentaire d'en-tête : webmaster Matthieu Robin, scénario/règles Hugo Bertillot, graphismes Ilane Schroetter, « Tous droits réservés », **contact : contact@apocalypsis.org** (point d'entrée pour la demande d'accord).
- **`<title>` générique** (« Archives ») sur toutes les pages : le titre du topic n'est que dans le `<h2>` et le fil d'Ariane.
- **Ressources** : `/css/definitive.css?v=55`, `/css/theme_retro.css?v=55`, `/js/common.js?v=55` (fournit `toggle_bloc()` et `popup()`), jQuery 1.12.4 chargé depuis le CDN de Google, `<body class="backgroundimg bg-assemblee_assemblee">` (image de fond définie dans le CSS). `theme_retro.css` ne contient que des images de fond (voir 2.11).
- **Script Google Analytics** (ancien `ga.js`, compte `UA-…`) présent sur chaque page : à retirer de la copie (suivi inutile, ralentissement, vie privée).
- **Tous les liens internes sont absolus depuis la racine** (`/archives/...`, `/avatars/...`, `/images/...`) : il faudra les réécrire pour un hébergement sous un sous-répertoire (ex. GitHub Pages de projet) ou conserver la racine du domaine.
- **Message** : une ligne `<tr>` avec `<td class="post_left">` (auteur, compteur, avatar, date, badges `div.support`) et `<td class="post_right">` (en-tête `div.posthead`, bloc de détail `div#cal{id_message}.vote`, puis des `<div class="post_line">`). 10 messages par page de topic.
- **Identifiant de message** : `{id_message}` dans `toggle_bloc('cal244405')` et dans l'URL de signalement `/archives/gamma2/warn/244405` (ex. 244405 à 244662, croissants, probablement globaux). C'est une clé naturelle pour la base de données.
- **Score** : vérifié sur les 10 messages, le score affiché est égal à la somme des 5 critères positifs moins la somme des 5 critères négatifs.
- **Champs facultatifs** : avatar absent (1 message sur 10), badges « soutient Apocalypsis » présents sur certains auteurs seulement, mention « Message édité », avatars de tailles variables (dimensions inline).
- **Interactions JavaScript** : « Détails » ouvre/ferme le bloc des critères (`toggle_bloc`) ; « Prévenir Dieu » ouvre un popup vers `/archives/gamma2/warn/{id}`. Ce popup est un formulaire de signalement, sans valeur d'archive : **liens et popup retirés de la copie** (décision utilisateur) ; le crawler ne suit pas `/warn/`.
- **Corps de message : HTML approximatif** rendu depuis du BBCode. Les balises `<font>`, `<strong>`, `<em>` sont souvent mal imbriquées et chevauchent des `</div>` (ex. `<font size="+2"></div><div class="post_line"><strong></div>…`). Les comptes d'ouvertures et de fermetures coïncident (47/47 et 15/15), mais leur position est incorrecte. Conséquence : la copie brute doit rester **telle quelle octet pour octet**, car un parseur qui « répare » le HTML changerait l'affichage ; le parsing structuré doit extraire le texte sans réécrire la page d'origine. Couleurs en attributs `color="red|yellow|green|orange|#5593BD"`.
- **Entités HTML** (`&eacute;`, `&#039;`, `&quot;`, `&nbsp;`) à décoder pour la recherche et les statistiques.
- **Liens externes** : les liens sont des `<a href="http://…" target="_blank" rel="nofollow">`, y compris vers l'ancien forum du jeu (`apocalypsis.org/assemblee/viewtopic?c_topic=…`, périmés avec l'ancienne architecture).

### 2.7 Anciennes interfaces (Beta) — pages d'exemple fournies

Inventaire connu des interfaces (à compléter) :

| Interface | Parties | État de nos connaissances |
|---|---|---|
| Récente (`theme_retro.css`, PHP, URL `/topics/{id}/page{n}`) | Gamma 2 et Gamma 1 (Gamma 1 : même interface d'après l'utilisateur, aucun exemple vu) | HTML brut vu pour Gamma 2 (2.6, 2.8) |
| Beta « classique » (pages statiques, `default.css`) | Beta 2 (page d'exemple : Galaxie 0, topic 4257), probablement Beta 3 | HTML brut vu (ci-dessous) |
| Première interface Beta | Début de Beta 1 / Beta 2 (page d'exemple : Beta 1 Galaxie 0) | Même gabarit HTML, mais **sans scores ni compteurs** ; l'utilisateur pense que seule l'image de fond diffère de l'interface Beta suivante (hypothèse à vérifier en comparant les feuilles CSS) |
| (Gamma 1 : voir ligne « Récente ») | Gamma 1 (2007 → 2012) | Déclarée identique à Gamma 2 ; à vérifier sur une page réelle (notamment l'année affichée dans les dates) |

Constats sur les deux pages Beta :

- **Pages statiques, liens relatifs** (`../../default.css`, `../../avatars/1340.jpg`, `../../images/registered.gif`, `../../index.html`, `../viewforum-1-1.html`, `viewtopic-4257-2.html`). Le miroir est donc utilisable tel quel, sans réécriture des liens ; il faut vérifier si `default.css`, `avatars/` et `images/` sont propres à chaque galaxie ou partagés (ce qui change la façon d'organiser la copie).
- **Gabarit** : HTML 4.01 Transitional généré avec « Quanta Plus », `charset=iso-8859-1`, une fonction `basculer()` en ligne pour afficher les détails de notation. Pas de jQuery, pas de Google Analytics, aucun script externe.
- **Encodage — point critique** : dans la copie enregistrée depuis un navigateur, **160 caractères accentués des libellés statiques** (« Détails », « présentation bâclée », « message adapté »…) ont été remplacés par le caractère de substitution U+FFFD et sont irrécupérables dans ce fichier. Le contenu des messages, lui, utilise des entités HTML (`&eacute;`) et n'est pas touché. Conséquence : **ne jamais enregistrer les pages avec un navigateur** ; capturer les **octets bruts** (curl/wget) et décoder selon le jeu de caractères réel de chaque page (probablement ISO-8859-1/cp1252 en Beta, UTF-8 en Gamma 2).
- **Message** : deux `<td class="posts">` par `<tr>`. À gauche : pseudonyme **sans grade** (pas de « Cdt. »), « **Respect diplomatique : N** » (au lieu de « Cauchemards provoqués »), avatar `128×128`, date dans `<pre>JJ/MM ETU HH:MM</pre>`, badges `registered.gif` avec un autre libellé (« Ce commandant soutient beaucoup la galaxie »). À droite : `div.posthead` (score + lien « Détails » + bloc `cal{id_message}`), puis le texte avec des `<br />` (pas de `<div class="post_line">`).
- **Critères de notation différents selon l'époque.** Négatifs identiques (orthographe insuffisante, présentation bâclée, hors sujet, hors role play, message insultant). Positifs en Beta : *efforts visibles, message adapté, message remarquable, humour décapant, role play intéressant* ; en Gamma 2 : *efforts visibles, torture adapté, supplice répugnant, rire glaçant, présence maléfique* (libellés de l'easter egg Halloween, qui correspondent un à un aux libellés Beta, voir 2.9). Vérifié sur 20 messages Beta : score = positifs − négatifs. → Stocker les critères dans une table (message, code, libellé, valeur, signe) plutôt qu'en colonnes fixes.
- **Pas de « Message édité »**, pas de lien « Prévenir Dieu » dans les pages Beta observées.
- **Sondage Beta** : `<h3>Vote&nbsp;: question</h3>` suivi d'un `<table align="center">` sans classe (texte des options dans des `<p>`, barres `div` correctement fermées). Pas de date de fin. Somme des options = total (18 + 38 + 10 = 66). La largeur de barre vaut **le pourcentage du total** (27, 58 et 15 px), alors qu'en Gamma 2 elle est proportionnelle à l'option la plus votée (100 px) : ne pas déduire les votes des barres, lire les nombres.
- **Corps des messages** : entités HTML et `<br />`, aucune balise `<font>` ou `<strong>` dans l'échantillon ; des rapports de jeu collés en clair.
- **Page de la première interface** (Beta 1 Galaxie 0, topic « Classement final », 2 messages) : `div.posthead` vide (aucun score), pas de compteur de respect, avatar absent pour certains messages ; le reste du gabarit est identique à la page Beta 2.

### 2.8 Page de liste des sujets d'un forum (Gamma 2, Galaxie 2, forum 186 « Assemblée Galactique d'ESPOIR »)

URL : `/archives/gamma2/galaxie2/forums/186/page{n}`. Page de 15 sujets, encodage UTF-8 (aucun caractère perdu), même gabarit et mêmes feuilles de style que les pages de topic (2.6).

- **En-tête** : `<h2>` nom du forum, puis `<h3>` « Planète Pourfendeur du Mal (2.0.14.2.2) » (nom de planète et coordonnées, vraisemblablement lié au forum ; à conserver comme sous-titre).
- **Pagination** : « Pages : 1 2 … 23 24 » (deux premières et deux dernières pages, « … » entre les deux), répétée en haut et en bas. 24 pages ici, donc environ 360 sujets (dernière page partielle).
- **Tableau** `table.listing`, colonnes *Sujet, Auteur, Réponses, Dernier message*. Une ligne par sujet : lien `/topics/{id}/page1` ; mini-pagination du sujet « [1 2 3] » (avec « … » pour les longs sujets), donc le nombre de pages de chaque sujet est connu dès la liste ; auteur (écrit `cdt.` / `cdte.` en minuscules, contre `Cdt.` dans les messages : à normaliser) ; nombre de réponses ; date et auteur du dernier message.
- **Marqueur de sondage** : le titre commence par `<font color="#FFC525">[Vote]</font>` (ex. topic 4330) : un passage sur les listes permet donc de repérer les topics à sondage. À vérifier qu'aucun sondage n'échappe au marqueur.
- **Messages supprimés** : « 20 (dont 1 supprimée(s)) » : des messages ont été supprimés et ne sont plus dans l'archive (6 sur 216 réponses sur cette page). Information utile pour les statistiques, et **contrôle d'intégrité possible** : nombre de messages archivés d'un sujet ≈ réponses + 1 − supprimés (formule à valider empiriquement).
- **Tri** : par date du dernier message décroissante. Le premier sujet date du 28/11/1013 ETU, soit la fin de la Galaxie 2 (28/11/2013) : les archives sont figées à la clôture de la galaxie.
- **HTML invalide** : la cellule `<td class="wrap_allowed">` n'est jamais fermée (suivie directement d'un `<td class="title">`). Les navigateurs tolèrent ; l'extraction doit utiliser un parseur permissif, pas des hypothèses de balisage strict. Tableau testé : 15 lignes extraites correctement.
- **Identifiants** : sujets 3108 à 4543 dans cette galaxie, contre 4257 en Beta 2 : les plages de numéros de topics se recouvrent entre parties (voir 2.2).

**Ordre de grandeur du volume (provisoire, extrapolé de très peu de pages).**
- Ce forum : environ 360 sujets × 14,4 réponses (moyenne de cette page, qui contient les sujets les plus récents) ≈ 5 000 messages ; avec environ 4 Ko de HTML par message (43 Ko pour 10 messages en 2.6) ≈ 20 Mo.
- Gamma 2 : les identifiants de messages atteignent déjà 244 662 en 2018 (Galaxie 11), soit au moins plusieurs centaines de milliers de messages sur Gamma 2 au total (identifiants possiblement partagés avec des messages non publics : ordre de grandeur plutôt qu'une mesure). À ~4 Ko par message, cela représente **de l'ordre de 1 Go de HTML brut pour Gamma 2 seul**, avant Gamma 1, Beta et les images. Le bloc de notation, répété sur chaque message (plus d'1 Ko, beaucoup d'espaces), pèse lourd.
- Conséquence probable : un miroir brut complet risque de dépasser les limites de taille d'un hébergement statique gratuit (de l'ordre de 1 Go, à revérifier). Cela rend plus sérieuse l'option de régénérer les pages depuis des données compactes (5.2, option B), ou de répartir sur plusieurs dépôts. À trancher après un inventaire réel (étape 3 du plan).

**Premier inventaire réel (`inventory`, interrompu avant la fin : 71 pages de structure restaient à faire).** Ces chiffres révisent l'estimation ci-dessus, mais restent provisoires :
- **Gamma** : environ 3 300 topics et 5 300 pages de topics vus dans les listes (Gamma 1 : 7 galaxies, ≈ 1 500 pages ; Gamma 2 : 24 galaxies, ≈ 3 800 pages), soit **≈ 0,23 Go** de HTML avec 40 Ko par page. C'est nettement moins que le Go supposé plus haut. Les listes de certaines galaxies étaient incomplètes (ex. `gamma2/galaxie21` : 2 listes), donc le total va encore monter.
- **Beta** : 7 888 pages de topics (liens `viewtopic-*`) découvertes, plus que supposé en 2.10. Le volume Beta n'est pas à négliger.
- **Mesure de taille réelle** : à faire avec `full --only` sur une galaxie, la taille moyenne de 40 Ko restant une extrapolation.
- **Erreurs observées** : les 67 erreurs 404 étaient de faux liens, tirés du script Google Analytics de chaque page (`ga.src = ('https:' == …`) ; corrigé dans `extract_links`. Cinq pages de structure ont répondu 500 (à examiner dans le manifeste).

### 2.9 Easter egg Halloween sur la notation : libellés à remplacer

Selon l'utilisateur, il s'agit d'un simple easter egg limité à la notation (libellés des critères positifs et compteur « Cauchemards provoqués »), sans autre cas particulier à rechercher. Les pages Gamma affichent ces libellés alternatifs ; l'archive doit restituer les libellés traditionnels, identiques à ceux de Beta.

| Libellé affiché (Halloween) | Libellé d'origine | Statut |
|---|---|---|
| torture adapté | message adapté | indiqué par l'utilisateur |
| supplice répugnant | message remarquable | indiqué par l'utilisateur |
| rire glaçant | humour décapant | indiqué par l'utilisateur (voir note) |
| présence maléfique | role play intéressant | indiqué par l'utilisateur |
| efforts visibles | efforts visibles | inchangé (identique en Beta) |
| les 5 critères négatifs | identiques | inchangés (identiques en Beta) |
| Cauchemards provoqués | Respect diplomatique | indiqué par l'utilisateur |

Note : l'utilisateur a écrit « humour décapant > rire glaçant », dans le sens inverse des trois autres lignes. Les cinq critères positifs apparaissent dans le même ordre en Beta et en Gamma 2 (le 4ᵉ est « humour décapant » en Beta, « rire glaçant » en Gamma 2), ce qui confirme l'appariement par position : hypothèse retenue, rire glaçant → humour décapant.

Règles de mise en œuvre :
- Stocker un **code canonique** par critère (effort, adapté, remarquable, humour, roleplay, plus les 5 négatifs) et le libellé d'origine ; appliquer la table de correspondance au parsing ou à la génération, jamais dans la capture brute, qui reste telle que servie.
- Les autres libellés des pages Gamma (texte des badges, grades « Cdt. ») sont conservés tels quels : d'après l'utilisateur, l'easter egg se limite à la notation.
- La table de correspondance est définitive : aucune recapture après Halloween n'est nécessaire.

### 2.10 Archives Beta : site, catégories, classement (Beta 1 Galaxie 0 exploré)

- **Deux hôtes.** La page de galaxie est sur le site principal (`https://www.apocalypsis.org/archives/beta1/galaxie0` : tableau de dates et deux liens, « Dernier classement » et « Forums galactiques publics »). Le contenu est sur un site de pages statiques distinct, **`https://archivesbeta.apocalypsis.org/`**. Le crawler doit couvrir les deux hôtes. Nommage : `galaxie0` sur le site principal, **`galaxie_0`** (avec tiret bas) sur `archivesbeta`.
- **Plusieurs catégories par galaxie** (alors qu'en Gamma il n'y a qu'une assemblée). Index : `/beta1/galaxie_0/forums_galactiques/` (aucun compteur, aucune pagination). Le libellé « Forums galactiques **publics** » laisse penser que d'autres forums existaient mais n'ont pas été archivés.

| Id | Catégorie (Beta 1 Galaxie 0) | Dernier message |
|---|---|---|
| 1 | Assemblée Galactique : diplomatie officielle | 31/08 ETU 23:04, juju_01 |
| 12 | Taverne galactique : lieu de discussion informel | 31/08 ETU 23:03, juju_01 |
| 37 | Journal Officiel et Divin de la Galaxie. | 29/08 ETU 23:00, Morcar Baughlir |

- **Schéma d'URL Beta (observé)** :
  - index des forums : `/beta1/galaxie_0/forums_galactiques/`
  - liste des sujets : `/beta1/galaxie_0/forums_galactiques/{id_forum}/viewforum-{id_forum}-{page}.html`
  - topic : `/beta1/galaxie_0/forums_galactiques/{id_forum}/{n}/viewtopic-{id_topic}-{page}.html` (le sous-dossier `{n}` vaut 1 pour les trois topics vus sur la page 1 de la liste ; sa signification reste à établir, vraisemblablement la page de liste ou un regroupement : à découvrir en suivant les liens, pas à deviner)
  - images : `/beta1/galaxie_0/forums_galactiques/images/…` (ex. `logo_petit.jpg`), donc **propres à chaque galaxie** ; `default.css` et `avatars/` sont très probablement au même niveau (déduit des liens relatifs `../../default.css`, `../../avatars/…`), non vérifié.
- **Liste des sujets Beta** (forum 1) : 40 sujets par page, au moins 9 pages (soit environ 360 sujets) ; colonnes *Sujet, Auteur, Réponses, Dernier message* (pas de colonne de vues) ; tri par dernier message décroissant ; mini-pagination des sujets longs ; aucun marqueur de sondage vu sur cette page. Le topic « Classement final » de l'échantillon Beta 1 est le n° 1531, l'un des derniers topics de Beta 1 : les identifiants de topics de Beta 1 sont donc au plus de l'ordre de 1 500, très en dessous de Gamma 2 (le volume Beta est vraisemblablement faible).
- **Classement** : fichier statique `/beta1/galaxie_0/dernier_classement_2005_08_31.html` (date de clôture dans le nom), HTML brut sans mise en forme. 491 lignes de la forme `rang pseudo (id, faction) + 6 scores` (éco, politique, militaire, commercial, scientifique, global) ; factions Fédération, Alliance, Guilde. Cohérent avec le topic « Classement final » (« 2 / 491 », L'Atlante en tête à 47,11). L'en-tête contient des liens de tri vers `top_view.php?o=N` (N de 0 à 6), un script dynamique absent de l'archive : liens morts, qu'un tri côté navigateur pourrait remplacer sans modifier le fichier. Données utilisables pour les statistiques (répartition par faction, distribution des scores ; jointure pseudo ↔ auteurs de messages à valider). Encodage à vérifier sur les octets bruts. Chaque galaxie Beta a son propre classement daté (table ci-dessous).

Pages de galaxie Beta (site principal, préfixe `https://www.apocalypsis.org/archives/`) et contenu associé (préfixe `https://archivesbeta.apocalypsis.org/`) — adresses relevées sur les pages elles-mêmes :

| Galaxie | Dates | Page de galaxie | Classement | Forums publics |
|---|---|---|---|---|
| Beta 1 G0 | 10/05/2005 → 31/08/2005 | `beta1/galaxie0` | `beta1/galaxie_0/dernier_classement_2005_08_31.html` | `beta1/galaxie_0/forums_galactiques/` |
| Beta 2 G0 | 01/09/2005 → 07/05/2006 | `beta2/galaxie0` | `beta2/galaxie_0/dernier_classement_2006_05_07.html` | `beta2/galaxie_0/forums_galactiques` |
| Beta 2 G1 | 29/11/2005 → 07/05/2006 | `beta2/galaxie1` | `beta2/galaxie_1/dernier_classement_2006_05_07.html` | `beta2/galaxie_1/forums_galactiques` |
| Beta 3 G0 | 15/05/2006 → 17/09/2007 | `beta3/galaxie0` | `beta3/galaxie_0/dernier_classement_2007_09_17.html` | `beta3/galaxie_0/forums_galactiques` |
| Beta 3 G1 | 15/05/2006 → 17/09/2007 | `beta3/galaxie1` | `beta3/galaxie_1/dernier_classement_2007_09_17.html` | `beta3/galaxie_1/forums_galactiques` |
| Beta 3 G2 | 22/01/2006 → 17/09/2007 | `beta3/galaxie2` | `beta3/galaxie_2/dernier_classement_2007_09_17.html` | `beta3/galaxie_2/forums_galactiques` |

Le nom du classement contient la date de fin de la galaxie (`AAAA_MM_JJ`). Les nombres de catégories de forums de Beta 2 et Beta 3 restent à relever (index `forums_galactiques/` de chacune). Les trois galaxies de Beta 3 durent de 16 à 20 mois : reconstruction de l'année nécessaire (2.5).

### 2.11 Feuilles de style et scripts (fichiers fournis)

**Gamma (interface moderne, site principal, préfixe `https://www.apocalypsis.org`)**
- `definitive.css` (45 Ko, ≈ 2 500 lignes, UTF-8) : feuille générale du jeu. Seules quelques règles servent aux archives : `.backgroundimg` (fond fixe, centré en bas, sur noir), `div.subtabs_nie` (conteneur noir à 95 % d'opacité), `table.viewtopic` (messages : colonne gauche de 160 px, colonne droite), `.post_line`, `.posthead`, `div.vote` (bloc de détail masqué par défaut), `td.vote` / `td.vote2`, `table.listing` (listes de sujets), `.support` et `.poll`. Le reste (carte de l'univers, arbre technologique, conversations, barre de navigation…) concerne le jeu et n'a aucun effet sur les archives : à conserver tel quel ou à élaguer à la construction.
- Une règle `.deleted td` (bordure orange) existe pour `table.listing` et `table.viewtopic` : des lignes `class="deleted"` peuvent exister ; aucune vue dans les échantillons.
- `theme_retro.css` (15 Ko, 143 lignes) : uniquement des images de fond par classe `bg-*` (90 règles, trois tailles selon la fenêtre). Les pages d'archives vues portent `bg-assemblee_assemblee` :
  - par défaut : `/images/backgrounds/page/retro/1024x819/assemblee_assemblee.jpg`
  - fenêtre ≤ 912 px de large ou ≤ 730 px de haut : `/images/backgrounds/page/retro/800x640/assemblee_assemblee.jpg`
  - fenêtre ≥ 1152 × 921 px : `/images/backgrounds/page/retro/1280x1024/assemblee_assemblee.jpg`
  
  (chemins déduits des `url(../images/…)` relatifs au dossier `/css/`, non vérifiés). Les autres classes `bg-*` (bâtiments, ordres…) appartiennent au jeu. La classe `bg-` des pages d'archives non encore vues (index des archives, page de galaxie, liste des forums) reste à vérifier.
- `common.js` (4,7 Ko) : seules `toggle_bloc()` (affiche ou masque le bloc de détails) et `popup()` (ouvre la fenêtre « Prévenir Dieu ») servent aux archives ; le reste (barre d'outils BBCode, infobulles, conversations, AutoNumeric…) concerne le jeu. Le fichier appelle `$(document).ready(…)`, donc jQuery doit être défini pour éviter une erreur JavaScript sans conséquence sur `toggle_bloc`. Le test `AutoNumeric !== undefined` n'est évalué que s'il existe un élément `.autonumeric`.
- `jquery.min.js` : jQuery 1.12.4 (97 Ko), fourni. Les archives n'en ont pas réellement besoin (voir décisions en attente).
- Le lien « Prévenir Dieu » ouvre `/archives/{partie}/warn/{id_message}` dans une fenêtre pop-up : formulaire de signalement, sans valeur archivistique. **Décision : retiré** de la copie (lien et popup), à la construction, jamais dans la capture brute. `popup()` devient inutile.
- Images utiles aux archives, hors fonds d'écran : `/images/public/logo_petit.jpg`, `/images/registered.gif`, `/images/warning.gif`, `/avatars/{id}.{gif|jpg|png}`.

**Beta (`default.css`, un seul exemplaire fourni, galaxie d'origine non précisée)**
- 1,3 Ko, 96 lignes : fond noir, texte blanc, tableaux à bordures blanches (`td.posts`), détails de notation en jaune `#FFFF80` masqués par `div.vote` jusqu'au clic (la fonction `basculer()` est dans la page elle-même).
- **Aucune image de fond** : le fichier ne contient aucun `url(`. Confirmé par l'utilisateur : c'est le **thème Beta le plus ancien, sans image de fond**. Un thème suivant, avec image de fond, a été introduit « à partir de la Beta 2 Galaxie 2 » jusqu'à la fin des Betas. **À clarifier** : l'index ne montre que les galaxies 0 et 1 pour Beta 2 ; il s'agit sans doute de la Beta 3 Galaxie 2 (début 22/01/2006) ou de la première galaxie de Beta 2 postérieure au changement. Il faut le `default.css` d'une galaxie récente (ex. Beta 3 Galaxie 0) pour voir l'image de fond et son chemin. Conséquence : deux thèmes Beta à restituer, plus le thème Gamma.

## 3. Ce qui n'est pas encore connu

- Les **images** : fonds d'écran Gamma (trois tailles, 2.11), logo, icônes, avatars, et le contenu des dossiers `images/` et `avatars/` de chaque galaxie Beta. Les CSS et JS de Gamma et un `default.css` Beta ont été fournis (2.11) ; le `default.css` fourni ne définit aucune image de fond, et ceux des autres galaxies Beta n'ont pas été vus.
- **Gamma 1** : déclarée identique à Gamma 2 mais jamais vue (format des dates, présence de l'année). Le HTML brut de Gamma 2 (2.6, 2.8) et de Beta 1 / Beta 2 (2.7, 2.10) est connu, pas celui de Beta 3 ni de Gamma 1.
- **Beta** : les index de catégories de Beta 2 et Beta 3 (nombre et noms des catégories), le contenu des classements autres que celui de Beta 1 Galaxie 0, la signification du sous-dossier `{n}` des topics, et le `default.css` du second thème Beta (avec image de fond). Les pages de galaxie du site principal sont connues (2.10).
- **Beta 3 et les galaxies de plus d'un an** : méthode de reconstruction de l'année des messages (2.5) à valider.
- Les **autres types de pages** : la liste des sujets d'un forum n'est connue qu'en Gamma 2 (2.8). Restent inconnues : la page « Forums » d'une galaxie (liste des forums), les pages d'index d'une partie ou d'une galaxie (`/archives/gamma2/galaxie2`), les listes de sujets Beta (`viewforum-…html`) et Gamma 1, et l'index « Forums galactiques » Beta (`index.html`).
- Le **volume total** : nombre de forums, topics, pages, messages, taille du HTML et des images.
- Les **variantes de structure** entre périodes (champs absents, sondages à choix multiples, pièces jointes, citations, émoticônes, BBCode).
- La présence d'**éléments dynamiques** (JavaScript, appels réseau) sur les pages d'archives.
- Les règles d'accès : `robots.txt`, limites de débit, conditions d'utilisation.
- Les **droits et accords** : accord de l'administrateur du site, et position vis-à-vis des auteurs des messages (pseudonymes, contenus parfois crus ou sensibles). À clarifier avant diffusion publique.
- L'existence d'une **sauvegarde ou d'un export de base de données** auprès de l'administrateur : ce serait la source la plus fiable.

## 4. Contraintes techniques identifiées

- L'environnement de travail de l'assistant **n'a pas accès** à apocalypsis.org depuis le shell (liste d'autorisation réseau). L'extraction devra être exécutée **sur une machine de l'utilisateur** ; les scripts peuvent être écrits et testés sur des pages d'exemple fournies.
- Le site peut disparaître à court terme : privilégier une **capture brute d'abord**, un traitement ensuite, de façon à pouvoir refaire le parsing sans retélécharger.
- Les **liens externes** (vidéos, images hébergées ailleurs) sont fragiles. Les images sont archivables ; le reste ne l'est pas toujours.
- **Capturer les octets bruts, jamais via « Enregistrer sous » d'un navigateur** : une copie enregistrée de page Beta a perdu définitivement les accents de ses libellés (voir 2.7). Le script de capture doit conserver la réponse HTTP telle quelle (et noter l'en-tête `Content-Type`), puis décoder au moment du parsing.

## 5. Axes de conception (sans décision)

### 5.1 Capture
- Copie brute des pages HTML et des ressources statiques (CSS, images, avatars, icônes), conservée telle quelle.
- Extraction structurée (messages, auteurs, scores, sondages, dates) vers un format de données (base ou fichiers).
- Les deux peuvent coexister : la copie brute comme source de vérité visuelle, les données structurées pour la recherche et les statistiques.

### 5.2 Restitution de l'interface
- **Option A :** servir les pages brutes réécrites (liens relatifs, ressources locales), ce qui conserve les deux interfaces à l'identique.
- **Option B :** regénérer les pages à partir des données structurées avec des gabarits reproduisant chaque interface (plus flexible, plus de travail, risque d'écart visuel).

### 5.3 Recherche
- Index statique chargé à la demande côté navigateur.
- Recherche côté serveur (nécessite un hébergement avec exécution de code).
- Critères souhaitables : texte intégral en français, filtres par galaxie, auteur et période.

### 5.4 Statistiques
- Précalculées au moment de la construction, ou calculées à la volée si un serveur est disponible.
- Idées : messages par mois, auteurs actifs, durée de vie et activité par galaxie, topics les plus longs, évolution des scores de messages, sondages (participation, résultats).

### 5.5 Hébergement
Pistes à comparer, sans préférence arrêtée :
- Hébergement statique gratuit (GitHub Pages, Cloudflare Pages, etc.) : pérenne et sans serveur, mais limité en taille et sans exécution de code.
- Offres gratuites avec exécution de code (PythonAnywhere, Render, etc.) : possibles mais contraintes (disque, mise en veille, expirations, conditions qui évoluent).
- Petit serveur payant (VPS) : plus de liberté, mais ce n'est pas gratuit.
- Hébergement complémentaire de sauvegarde (dépôt de données, archive publique).

Points de comparaison : coût, limite de taille, durabilité, besoin de maintenance, recherche dynamique ou statique, absence de publicité.

## 6. Risques

| Risque | Atténuation possible |
|---|---|
| Volume supérieur aux limites d'un hébergement gratuit | Mesurer avant de choisir ; prévoir une stratégie de répartition ou de compression |
| Disparition du site pendant l'extraction | Capture brute prioritaire, reprise après interruption |
| Variantes de structure entre vingt ans d'archives | Échantillonner chaque galaxie avant le parsing complet |
| Perte des liens et images externes | Archiver les images, accepter la perte du reste |
| Aspects juridiques et vie privée | Contacter l'administrateur, décider du niveau de publicité de l'archive |
| Fragilité des offres gratuites | Conserver les données dans un format indépendant de l'hébergeur |
| Miroir brut trop volumineux (premier inventaire : ≈ 0,23 Go de HTML pour Gamma, Beta et images non mesurés, voir 2.8) | Terminer l'inventaire et mesurer les images ; régénération depuis des données compactes ou répartition sur plusieurs dépôts si besoin |
| Libellés de notation alternatifs (easter egg) sur les pages Gamma | Table de correspondance (2.9) et codes canoniques |
| Messages supprimés, absents de l'archive | Les compter via les listes de sujets (« dont N supprimée(s) ») et l'indiquer dans les statistiques |

## 7. Étapes proposées (indépendantes des choix techniques)

1. Contacter l'administrateur (accord, export éventuel de la base).
2. Récupérer le HTML brut d'un échantillon : un topic ordinaire, un topic avec sondage, une archive ancienne (Beta), une archive de Gamma 1.
3. Inventorier le volume : nombre de forums, topics et pages par galaxie.
4. Valider l'hypothèse sur les dates.
5. Écrire l'extraction (capture brute puis parsing) et la tester sur l'échantillon.
6. Exécuter la capture complète sur la machine de l'utilisateur.
7. Choisir la restitution et l'hébergement à partir des mesures réelles.
8. Ajouter la recherche, puis les statistiques.

## 8. Décisions en attente

- [ ] Méthode de restitution : pages brutes ou pages regénérées
- [ ] Hébergement
- [ ] Technologie de recherche
- [ ] Format de stockage des données structurées
- [ ] Périmètre de diffusion (public ou restreint)
- [ ] Traitement des images et liens externes
- [ ] Inclusion éventuelle de la Galaxie 24 à sa clôture
- [x] Libellés de notation : appliquer la table de correspondance (2.9)
- [ ] Périmètre Beta : inclure les trois catégories (Assemblée Galactique, Taverne galactique, Journal Officiel et Divin), ce qui semble découler de « intégralité des forums des archives » ; à confirmer pour la Taverne (discussion informelle)
- [ ] JavaScript des archives : conserver `common.js` et jQuery 1.12.4 en copie locale tels quels, ou les remplacer par un script minimal (`toggle_bloc`, fenêtre de signalement neutralisée) ; voir 2.11
- [ ] Fonds d'écran Gamma : télécharger les trois tailles de `assemblee_assemblee.jpg` (2.11) et vérifier la classe `bg-` des pages d'archives non vues

## 9. Outils

### 9.1 `archive_crawler.py` — capture brute

Script Python (bibliothèque standard uniquement, **Python 3.9+**, aucune installation) qui capture les octets bruts des deux sites (`www.apocalypsis.org` et `archivesbeta.apocalypsis.org`). Octets conservés tels quels (Content-Type enregistré), `robots.txt` respecté, un seul fil avec délai entre requêtes. Les liens `/warn/`, `top_view.php`, `forum.apocalypsis.org` ne sont pas suivis. Testé sur un faux site local (`tests/test_crawl.py`).

**Lancer le script** (depuis le dossier du projet, dans un terminal) :

```
python archive_crawler.py inventory --out archive
python archive_crawler.py report    --out archive
python archive_crawler.py full      --out archive --delay 0.5
```

Sous Windows, si `python` n'est pas reconnu, utiliser `py archive_crawler.py ...`. Le script doit tourner **sur la machine de l'utilisateur** (voir section 4).

**Commandes**

| Commande | Effet |
|---|---|
| `inventory` | Parcourt seulement les pages « structure » (index, pages de galaxies, listes de forums) pour mesurer le volume réel. Les topics et ressources sont notés dans la file mais pas téléchargés. À lancer en premier. |
| `report` | Affiche un rapport depuis le manifeste : pages par type et statut, topics et pages estimés par galaxie Gamma, volume extrapolé en Go, ressources connues, premières erreurs. Ne fait aucune requête. |
| `full` | Télécharge tout : structure, topics, CSS/JS, images, avatars. |

**Options**

| Option | Défaut | Rôle |
|---|---|---|
| `--out DOSSIER` | `archive` | Dossier de sortie |
| `--delay S` | `0.25` | Secondes entre deux requêtes (augmenter pour ménager le serveur) |
| `--timeout S` | `30` | Délai maximal d'une requête |
| `--retries N` | `4` | Tentatives avant d'abandonner une page (erreurs 429/503/réseau) |
| `--only GALAXIE` | (tout) | Limite à une galaxie, ex. `gamma2/galaxie1` ou `beta1/galaxie0` ; répétable. Les index et ressources partagées restent suivis. |

**Parcours conseillé**
1. Essai ciblé : `python archive_crawler.py full --out archive --only beta1/galaxie0` (petit volume).
2. `inventory`, puis `report` pour mesurer le volume avant de tout télécharger (étape 3 du plan).
3. `full` complet, éventuellement en plusieurs sessions.

**Sortie**
- `archive/raw/<hôte>/<chemin>` : les fichiers bruts (un par URL, ex. `raw/www.apocalypsis.org/archives/gamma2/galaxie1/forums/2/topics/2343/page1.html`).
- `archive/manifest.sqlite` : une ligne par URL (type, code HTTP, Content-Type, chemin, taille, SHA-256, date, erreur, page d'origine) et l'état de reprise. Consultable avec n'importe quel outil SQLite.

**Interruption et reprise.** Ctrl+C arrête proprement après la requête en cours. Relancer **la même commande** reprend à la page interrompue : file d'attente, manifeste et dernière page vivent dans SQLite, chaque page étant enregistrée avec ses liens en une seule transaction. Les erreurs réseau ou temporaires (-1, 429, 500, 502, 503, 504) d'une session précédente sont réessayées. Si le serveur renvoie 429/503, le script fait une pause croissante (jusqu'à 300 s) et s'arrête après 12 échecs consécutifs : relancer plus tard.

**Tests** (aucun accès réseau, faux site local) :

```
python tests/test_crawl.py -v
```
### 9.2 Archive JSON (écrite avec la capture)

Pendant `full` (option `--formats html,json`, défaut), chaque page de topic Gamma/Beta et chaque liste de sujets Gamma est aussi versée dans `archive/json/<partie>/<galaxie>/forums/<forum>/` : `topics/<id>.json` (titre, sondage, messages groupés par page) et `sujets.json` (sujets, réponses, supprimés, marqueur de sondage). Le JSON écarte le gabarit répété ; critères de notation en codes canoniques (valeurs non nulles seulement, libellés d'origine, voir 2.9) ; date ISO pour Gamma (année ETU + 1000), `date_sans_annee` pour Beta (2.5). `--formats json` ne garde pas le HTML brut. `python archive_crawler.py json` régénère le JSON depuis la capture brute, sans réseau. Les listes de sujets Beta (`viewforum-*`) ne sont pas encore traitées (aucun exemple brut). Le HTML brut reste la source de vérité.

### 9.3 Parsing vers SQLite

- Non écrit (après l'inventaire et la décision de restitution).
