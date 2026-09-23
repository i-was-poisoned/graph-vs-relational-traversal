# Notes de projet : bases de données graphes vs. relationnelles

## Sujet

Ce projet examine une question pratique : **à quelle profondeur de traversée, et à
quel volume de données, un modèle de graphe de propriétés surpasse-t-il un modèle
relationnel normalisé équivalent, pour une même requête ?**

Les bases de données relationnelles (par ex. PostgreSQL, MySQL) stockent les
données dans des tables et expriment les relations via des clés étrangères.
Interroger une relation implique d'effectuer une `JOIN`, et le moteur de base de
données doit calculer cette jointure au moment de la requête — en associant les
lignes entre tables sur la base de l'égalité des clés. Pour une seule relation
(par ex. « trouver les commandes d'un utilisateur »), c'est rapide et bien
optimisé grâce à des décennies de planification de requêtes relationnelles. Le
problème apparaît avec les **requêtes de relations à plusieurs sauts** — par ex.
« trouver les amis des amis des amis qui suivent une personne ayant aimé une
publication que j'ai aimée ». Chaque saut supplémentaire signifie une `JOIN` de
plus, et chaque `JOIN` multiplie le nombre de lignes que le moteur doit parcourir
et associer, si bien que le coût tend à croître rapidement avec la profondeur de
traversée.

Les bases de données graphes (par ex. Neo4j, ArangoDB) stockent les relations
comme des pointeurs de première classe, pré-matérialisés entre les nœuds
(« adjacence sans index »). Traverser une relation revient à suivre un pointeur
direct plutôt qu'à recalculer une jointure, si bien que le coût d'une traversée à
plusieurs sauts tend à évoluer avec la taille du *sous-graphe traversé*, et non
avec la taille de l'ensemble du jeu de données. C'est le fondement théorique de
l'affirmation selon laquelle les bases de données graphes « l'emportent » sur les
requêtes profondes et riches en relations, tandis que les bases de données
relationnelles tendent à l'emporter (ou à faire jeu égal) sur les requêtes peu
profondes, les agrégations, et les charges de travail naturellement tabulaires.

La question ouverte, propre à ce projet, est de savoir *où se situe réellement le
point de bascule* — à quelle profondeur de jointure et à quel volume de données le
coût de l'approche relationnelle commence-t-il à dépasser celui de l'approche
graphe, pour un schéma et une requête comparables. C'est ce point de bascule, plutôt
qu'une affirmation générale du type « les graphes sont meilleurs », que ce projet
vise à mesurer empiriquement.

## Ressources utilisées

- **Claude AI** — utilisé comme assistant de recherche et de rédaction :
  exploration de la littérature et des concepts autour des performances
  graphe vs. relationnel, rédaction et relecture de code, et aide à la
  structuration de la documentation.
- **GitHub** — hébergement distant du dépôt du projet. Fournit un historique
  des versions, une sauvegarde, et (plus tard) un espace pour collaborer ou
  partager le travail.
- **VS Code** — l'éditeur de code local utilisé pour écrire et exécuter le
  code du projet et gérer le dépôt git au quotidien.
- **Overleaf** — utilisé pour la rédaction du projet en LaTeX (par ex. un
  rapport ou un article), séparément du dépôt de code.
- **GH Archive** — la source du jeu de données. Publie des extractions
  horaires de chaque événement GitHub public sous forme de fichiers JSON
  Lines compressés en gzip, avec des relations naturellement en forme de
  graphe (acteur → dépôt → événement). La date/heure spécifique utilisée par
  ce projet est enregistrée dans le [README](../README.md) (conservée là-bas,
  et non ici, car il s'agit d'une configuration de projet critique pour la
  reproductibilité plutôt que d'une note d'apprentissage). Voir
  [gh-archive-guide.md](gh-archive-guide.md) pour une explication complète de
  ce qu'est GH Archive et de son fonctionnement.

Pour une explication approfondie et partant des principes de base de ce
que sont réellement l'IA/Claude/un « agent », ce que sont un IDE/VS
Code/une « extension », ce qu'est Python et comment il se compare aux
autres langages, et le JSON pretty-printed vs. JSON Lines, voir
[tools-and-concepts-guide.md](tools-and-concepts-guide.md).

## Pourquoi `.gitignore` et `README.md` sont importants

### `README.md` : la porte d'entrée du projet

Un fichier `README.md` est, au fond, un simple document texte mis en
forme — et le `.md` est la clé pour comprendre ce que c'est vraiment.
`.md` veut dire **Markdown** : un langage de balisage léger (ce n'est pas
un langage de programmation) qui permet d'écrire du texte mis en forme —
titres, **gras**, *italique*, listes, liens, blocs de code — avec de
simples symboles du clavier (`#` pour un titre, `**...**` pour le gras,
`` `...` `` pour du code en ligne), sans avoir besoin d'un éditeur visuel
façon Word. On écrit du texte brut parsemé de ces symboles, et n'importe
quel programme qui « comprend » le Markdown (GitHub, VS Code, ce document
lui-même) l'affiche ensuite comme du texte proprement mis en forme. Tous
les fichiers `.md` de ce projet (ce `project-notes.md`, le `README.md`,
`gh-archive-guide.md`) sont écrits en Markdown précisément pour cette
raison : c'est lisible même en texte brut, non rendu, et ça s'affiche
proprement partout où c'est compris.

`README` (en majuscules, sans extension, ou en `.md`/`.txt`) est aussi
une **convention** très ancienne dans le monde du logiciel : par
tradition, c'est le tout premier fichier que quiconque découvre un
projet est censé lire. GitHub (ainsi que GitLab, Bitbucket, et presque
tous les autres hébergeurs de dépôts) construit automatiquement là-dessus :
si un dépôt contient un fichier littéralement nommé `README.md` (ou
`README`, `README.txt`, etc.) à sa racine, la plateforme le détecte et
l'affiche déjà mis en forme, juste en dessous de la liste des fichiers,
sur la page principale du dépôt. Ce n'est pas un comportement spécial de
git lui-même — git ne traite aucun fichier nommé `README` de façon
particulière ; c'est purement un comportement que GitHub (et les
plateformes similaires) ajoutent par-dessus git, en se basant sur ce nom
de fichier conventionnel. C'est exactement pour cela qu'un `README.md`
bien écrit est si précieux : c'est littéralement la première chose que
tout le monde voit (y compris vous-même, dans six mois, sans souvenir
frais du projet) en arrivant sur le dépôt — il doit donc répondre
immédiatement à « qu'est-ce que c'est, pourquoi ça existe, et à quelle
question ça essaie de répondre ? », exactement ce que fait le
`README.md` de ce projet en commençant par sa question de recherche.

### `.gitignore` : ce que « suivre » signifie vraiment pour git, et pourquoi il faut lui dire quoi ignorer

Pour comprendre `.gitignore`, il faut d'abord comprendre que git ne
considère pas automatiquement chaque fichier de votre dossier comme
« faisant partie du projet ». Pendant que vous travaillez dans un dépôt,
chaque fichier se trouve dans l'un de ces états :

- **Non suivi (untracked)** — git voit que le fichier existe dans le
  dossier, mais on ne lui a jamais demandé de le surveiller ; il ne fait
  pas partie de l'historique du projet, et `git status` le signale comme
  « nouveau ».
- **Indexé (staged)** — exécuter `git add` dit à git « je veux que ce
  fichier, dans son état actuel, fasse partie du prochain commit ».
- **Commité (committed)** — exécuter `git commit` fige définitivement cet
  état indexé dans l'historique du dépôt.

Sans `.gitignore`, chaque nouveau fichier apparaissant dans le dossier —
y compris ceux que Python génère tout seul, comme les caches
`__pycache__/`, ou les données téléchargées dans `data/` — apparaîtrait
comme « non suivi » dans `git status`, et un `git add .` fait sans faire
attention l'embarquerait dans le prochain commit sans que vous ne vous en
rendiez compte. `.gitignore` est, littéralement, une liste de motifs de
noms de fichiers/dossiers qui dit à git « ne me montre même pas ces
fichiers comme 'non suivis' ; ignore-les complètement ». Il utilise des
motifs de type joker (*wildcard*) — par exemple, dans le `.gitignore`
réel de ce projet :

- `/data/` — ignore tout le dossier `data/` (la barre oblique au début le
  fixe à la racine du projet, pas à n'importe quel dossier `data/` à
  n'importe quel niveau).
- `__pycache__/` — ignore tout dossier portant exactement ce nom,
  n'importe où dans le projet (sans barre oblique au début, ça
  s'applique à tous les niveaux).
- `*.py[codz]` — `*` est un joker qui signifie « n'importe quel texte
  ici » ; ceci ignore des fichiers comme `quelquechose.pyc`,
  `quelquechose.pyo`, etc.
- Les lignes commençant par `#` sont des commentaires, uniquement pour
  les humains — git les ignore complètement en lisant le fichier.

Pourquoi se donner la peine d'exclure ces fichiers plutôt que de
simplement ne jamais faire `git add` dessus à la main à chaque fois ?
Parce que sans `.gitignore`, ces fichiers **régénérables** ou
**spécifiques à la machine** (caches de build, environnements virtuels,
identifiants, configuration propre au système d'exploitation ou à
l'éditeur) encombreraient l'historique des commits, gonfleraient la
taille du dépôt avec du contenu inutile pour quiconque d'autre, et — le
risque le plus sérieux — pourraient divulguer accidentellement des
chemins propres à votre machine ou, pire, des secrets comme des mots de
passe ou des clés d'API si l'un d'eux finit par se retrouver, par erreur,
dans un fichier commité. `.gitignore` automatise cette discipline une
bonne fois pour toutes, plutôt que de compter sur le fait qu'un humain
n'oubliera jamais de faire cette erreur.

### La compilation : du code source au code machine

Pour comprendre pourquoi tant de lignes du `.gitignore` de ce projet
concernent des « artefacts de build », il faut d'abord comprendre ce
qu'est réellement **compiler**.

Le processeur d'un ordinateur (le CPU) ne comprend ni Python, ni le C, ni
aucun autre langage de programmation tel qu'un humain l'écrit — il ne
comprend qu'un ensemble très restreint et très spécifique d'instructions
binaires (des suites de zéros et de uns) appelé **code machine**, propre
à chaque architecture de processeur. Le **code source** lisible par un
humain que l'on écrit (avec des noms de variables clairs, des
commentaires, une structure) existe uniquement pour que les humains
puissent le lire et le comprendre ; l'ordinateur, tel quel, ne peut pas
l'exécuter directement.

Un **compilateur** est un programme dont le seul travail est de traduire
du code source, écrit dans un langage de haut niveau, en code machine
(ou en une autre représentation intermédiaire) avant même que le
programme ne s'exécute. Ce processus de traduction s'appelle **compiler**
(ou « builder »), et le résultat — le ou les fichiers déjà traduits —
est ce qu'on appelle généralement un **artefact de build** (voir la
section suivante). Dans les langages compilés comme le C ou Rust, cette
étape a lieu explicitement, une seule fois, avant que le programme ne
soit jamais exécuté ; le résultat est un fichier exécutable autonome.

Python, comme expliqué plus en détail dans
[tools-and-concepts-guide.md](tools-and-concepts-guide.md#33-langages-compilés-vs-interprétés),
est un langage **interprété** — vous ne compilez pas manuellement les
scripts de ce projet avant de les exécuter ; ils s'exécutent directement
via `python scripts/peek_data.py`. Mais en coulisses, l'interpréteur de
Python compile quand même chaque fichier `.py` vers une forme
intermédiaire appelée **bytecode** (des instructions plus simples que le
code Python d'origine, mais toujours pas du code machine brut) la
première fois qu'il est importé ou exécuté, et met ce bytecode en cache
dans des fichiers `.pyc` à l'intérieur d'un dossier `__pycache__/`, pour
ne pas avoir à refaire ce travail de traduction à chaque exécution
future si le fichier source n'a pas changé. Ces fichiers `.pyc` sont
exactement un artefact de build — simplement généré automatiquement par
Python lui-même, en arrière-plan, plutôt que par une étape de build
manuelle.

### Qu'est-ce qu'un « artefact » (*build artifact*) ?

Un **artefact de build** (ou simplement « artefact », *build artifact*
ou *build output*) est tout fichier **généré** à partir du code source
par un processus automatisé — compilation, packaging, minification,
rendu — plutôt qu'écrit à la main par une personne. La distinction clé
pour ce projet :

- Le **code source** (les fichiers `.py` dans `scripts/`, les fichiers
  `.md` dans `docs_*/`) est la **seule source de vérité** — ce qu'une
  personne a réellement écrit, et la seule chose qui doit véritablement
  vivre dans l'historique du projet.
- Un **artefact** est *dérivé* de ce code source — il peut toujours être
  régénéré en relançant le même processus sur le même code source, ce
  qui rend son commit dans git redondant au mieux, et activement nuisible
  au pire.

Exemples d'artefacts de build au-delà des fichiers `.pyc` de Python déjà
mentionnés (pour généraliser complètement le concept, pas seulement dans
le cadre de ce projet) : un `.exe` ou une `.dll` compilé à partir de
code C/C++ ; un `.jar` compilé à partir de code Java ; le HTML/CSS/
JavaScript final, minifié et « empaqueté » (*bundled*) que produit
l'outil de build d'une application web moderne à partir de son code
source ; un fichier `.whl` (*wheel*) empaquetant une bibliothèque Python
prête à installer ; même une documentation HTML générée automatiquement
à partir de commentaires dans le code source.

Pourquoi les artefacts de build ne sont presque jamais commités dans un
dépôt git (et pourquoi le `.gitignore` de ce projet lui-même en exclut
autant — `__pycache__/`, `*.py[codz]`, `build/`, `dist/`,
`*.egg-info/`, entre autres) :

1. **Ils sont régénérables.** Si le code source est dans le dépôt,
   n'importe qui peut régénérer exactement le même artefact à tout
   moment — le stocker aussi ne ferait que dupliquer de l'information
   sans aucun bénéfice.
2. **Ils sont souvent spécifiques à l'environnement.** Un `.pyc` compilé
   avec la version de Python installée sur cette machine (Python 3.14,
   d'après les chemins `__pycache__/` observés dans ce projet) pourrait
   ne pas fonctionner de la même façon, voire ne pas se charger du tout,
   sur la machine de quelqu'un d'autre utilisant une version différente
   de Python.
3. **Ils encombrent l'historique et les diffs.** Les artefacts sont
   généralement des fichiers binaires (pas du texte lisible ligne par
   ligne), donc git ne peut pas en afficher un diff utile ligne par
   ligne comme il le fait pour du code source — chaque changement
   apparaît simplement comme « le fichier entier a changé », sans
   aucune information sur ce qui a réellement changé.
4. **Ils gonflent la taille du dépôt** avec du contenu qui n'ajoute rien
   à la compréhension du projet — personne n'a besoin de lire un `.pyc`
   pour comprendre ce que fait `peek_data.py` ; le fichier `.py` le dit
   déjà.

(Une nuance à connaître, pour être complet : il existe des exceptions
délibérées à cette règle générale — par exemple, quand un projet
*publie* un artefact terminé, comme joindre un exécutable compilé à une
« Release » GitHub pour que les gens puissent le télécharger directement
sans compiler le code source eux-mêmes. C'est différent de commiter
l'artefact dans l'*historique des commits* du dépôt, ce que `.gitignore`
empêche ici.)

## Déroulement du dépôt jusqu'à présent

1. Le dépôt a d'abord été créé sur GitHub (distant).
2. Il a été cloné localement avec `git clone` dans `C:\dev\Research` —
   délibérément **en dehors** de tout dossier synchronisé par OneDrive (par
   ex. en évitant un chemin contenant `OneDrive - Pedro`), car la
   synchronisation par OneDrive d'un dossier géré par git peut provoquer des
   conflits de verrouillage de fichiers, atteindre les limites de longueur
   de chemin de Windows, et ralentir à la fois git et OneDrive. GitHub
   (distant) et OneDrive (synchronisation locale) sont des systèmes
   indépendants, mais tous deux se disputeraient les mêmes fichiers locaux
   si le dépôt se trouvait dans un dossier OneDrive.
3. À ce stade, le code est écrit et commité localement ; la publication vers
   le dépôt distant GitHub est reportée à plus tard.

## Phase de test

Commençons par nous placer à la racine du projet et par examiner le jeu de
données pour l'heure spécifique en exécutant :

```bash
python scripts/download_gharchive.py
```

Points importants avant d'exécuter cette commande :

- **Vous devez vous trouver à la racine du projet** (`C:\dev\Research`)
  lorsque vous exécutez cette commande. Elle est lancée en tant que
  `scripts/download_gharchive.py` (un chemin relatif), donc le shell doit se
  trouver dans le dossier qui contient le répertoire `scripts/` — sinon il
  ne trouvera pas le fichier.
- **Python doit être présent dans le PATH.** Cela signifie que votre système
  sait où se trouve le programme `python`, afin de pouvoir l'exécuter par
  son nom depuis n'importe quel terminal, sans avoir à taper le chemin
  d'installation complet à chaque fois. Si l'exécution de `python
  scripts/download_gharchive.py` renvoie une erreur du type « commande
  introuvable », essayez `python3` à la place — certaines installations
  n'enregistrent que ce nom. (Ceci est différent de la variable
  d'environnement `PYTHONPATH`, qui concerne l'endroit où Python cherche les
  modules importables, et non la manière de trouver l'exécutable `python`
  lui-même — ce dont ce script n'a pas besoin.)
- Le script crée automatiquement un dossier `data/` lors de la première
  exécution — inutile de le créer vous-même. Il est exclu de git via
  `.gitignore` puisqu'il s'agit de données brutes et régénérables, et non de
  code du projet.
- Une exécution réussie affiche la progression du téléchargement et de la
  décompression, se terminant par une ligne du type
  `Done: data/2026-08-27-15.json` — ce fichier est le jeu de données
  décompressé, prêt à être lu ligne par ligne (voir
  [gh-archive-guide.md](gh-archive-guide.md), section 8).

Remarque : la première exécution a provoqué une erreur `HTTP Error 403:
Forbidden` de la part du serveur de GH Archive, causée par l'en-tête
`User-Agent` par défaut d'`urllib`, qui ressemble à celui d'un script plutôt
qu'à celui d'un navigateur. Corrigé en construisant la requête manuellement
avec un en-tête `User-Agent` imitant un navigateur, plutôt qu'en utilisant
directement `urlretrieve` (voir le script pour le correctif, et
[download_gharchive.py](download_gharchive.py), la copie annotée, pour
l'explication complète).

## Gestion de version (git add → commit → push)

Une fois les scripts de téléchargement/exploration et la documentation en
place, l'étape courante suivante consistait à commiter et pousser ce travail
vers GitHub. Les commandes utilisées, dans l'ordre :

```bash
git add .
git commit -m "Exploration stage set up"
git push
```

Ce premier push a échoué avec une erreur HTTP 403, car la connexion GitHub
mise en cache par Windows appartenait à un compte différent (un compte
professionnel) de celui qui possède ce dépôt. Corrigé en repointant le
remote vers le bon compte, sans toucher à l'identifiant professionnel mis en
cache :

```bash
git remote -v
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
git push -u origin main
```

Voir [git-commands-guide.md](git-commands-guide.md) pour une explication
complète de ce que fait réellement chacune de ces commandes, du concept de
zone de staging derrière `add`/`commit`, et de la raison de cette confusion
de compte.

## Étape d'exploration (download_gharchive.py --> peek_data.py)

Maintenant que nous disposons d'un jeu de données téléchargé et décompressé
au format JSON Lines (`data/2026-08-27-15.json`), l'étape suivante consiste
à examiner réellement son contenu, avant d'essayer de le modéliser sous
forme relationnelle ou de graphe.

`scripts/peek_data.py` lit les premiers événements du fichier et affiche
leurs champs clés (`type`, `actor`, `repo`, `created_at`) — une vérification
rapide de cohérence pour s'assurer que les données correspondent à ce que
décrit [gh-archive-guide.md](gh-archive-guide.md), avant d'écrire une
véritable logique d'analyse/chargement.

Exécutez-le avec :

```bash
python scripts/peek_data.py
```

Cela affiche les 5 premiers événements par défaut. Variantes utiles :

```bash
# Print more events
python scripts/peek_data.py --lines 20

# Point at a different downloaded file
python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
```

## Étape de synthèse (summarize_data.py)

Une fois la forme d'un seul événement confirmée par `peek_data.py`, l'étape
suivante consiste à se faire une idée du *volume et de la connectivité* sur
l'ensemble de l'heure téléchargée, avant de choisir un schéma : combien
d'événements, comment ils se répartissent par type, et combien d'acteurs/dépôts
distincts sont impliqués.

`scripts/summarize_data.py` lit le fichier JSON Lines entier une seule fois
et rapporte :

- le nombre total d'événements
- la répartition par type d'événement (décompte et pourcentage, du plus
  fréquent au moins fréquent)
- le nombre d'acteurs et de dépôts uniques
- les N acteurs et dépôts les plus actifs par nombre d'événements

Exécutez-le avec :

```bash
python scripts/summarize_data.py

# Afficher plus d'acteurs/dépôts les plus actifs
python scripts/summarize_data.py --top 10
```

Pour l'heure fixe du 2026-08-27 15h00 UTC, cela a montré 69 429 événements
répartis entre 14 728 acteurs uniques et 16 497 dépôts uniques, avec
`PushEvent` représentant à lui seul 95,3 % de tous les événements. Les
acteurs les plus actifs sont tous des bots (`github-actions[bot]`,
`dependabot[bot]`, `pull[bot]`, `renovate[bot]`, `cursor[bot]`) — il vaut la
peine de décider d'une politique de filtrage des bots avant d'utiliser ces
données pour construire les modèles relationnel/graphe, car les
`PushEvent` générés par des bots domineraient sinon la connectivité mesurée.

## Ce que signifie « benchmark » pour ce projet

Avant d'aller plus loin, il vaut la peine d'être précis sur un mot que ce
projet utilise constamment. Un **benchmark** est un test équitable,
reproductible, et *chronométré*, utilisé pour comparer deux choses ou plus
dans les mêmes conditions — pas seulement « on l'exécute une fois et on
regarde », mais un contrôle délibéré de tout sauf de la seule chose
mesurée, afin que le résultat soit une comparaison véritable et non un
hasard causé, par exemple, par le fait que l'ordinateur portable faisait
autre chose en arrière-plan pendant l'une des deux exécutions.

Pour ce projet en particulier : un run de benchmark consiste à prendre la
*même* requête à plusieurs sauts (par ex. « en partant de l'acteur X,
trouver tous les dépôts atteignables en 3 sauts ») et à l'exécuter contre
la base de données relationnelle et contre la base de données graphe, sur
les *mêmes* données sous-jacentes, en chronométrant la durée de chacune.
Cela se répète pour différentes profondeurs de saut et différents volumes
de données afin de trouver le point de bascule évoqué dans le README.

## Principe de conception du schéma : la requête d'abord, pas les champs

Un raccourci tentant serait de regarder chaque champ fourni par GH Archive
et de construire une table ou un type de nœud pour chacun d'eux. C'est le
mauvais ordre. La conception du schéma pour un benchmark doit être guidée
par la *requête* testée, pas par « les champs qui se trouvent exister » :

- **Champs d'abord** signifie parcourir les données, voir des champs comme
  les messages de commit, le texte des revues de PR, et les labels
  d'issue, et tout modéliser. Cela produit un schéma vaste et détaillé —
  dont la majeure partie n'est en réalité jamais touchée par le benchmark
  de parcours.
- **Requête d'abord** signifie décider *d'abord* exactement ce qui est
  mesuré (pour ce projet : un parcours `acteur → dépôt → acteur → dépôt` —
  voir ci-dessous pourquoi cette forme est nécessaire, plutôt qu'une
  arête acteur-à-acteur directe), puis ne construire que la structure
  minimale dont ce parcours a besoin : une chose Acteur, une chose Dépôt,
  et une connexion entre les deux.

Pourquoi cela compte au-delà de la simple propreté : des tables/colonnes
(ou types de nœud/arête) supplémentaires et inutilisées ne rendent aucun
des deux côtés de la comparaison « plus correct » — elles ajoutent
seulement de la complexité qui ne fait pas partie de la mesure. Pire, si
ce détail supplémentaire est construit de façon inégale (plus côté
relationnel que côté graphe, ou l'inverse), la comparaison cesse d'être
équitable, ce qui est pourtant tout l'enjeu de la question de recherche de
ce projet.

## Étape de conception du schéma (profile_schema.py)

Les données sont intrinsèquement **bipartites** : chaque événement relie
un `actor` à un `repo` (voir
[gh-archive-guide.md](gh-archive-guide.md#acteurs-dépôts-et-événements)
pour la distinction complète acteur/dépôt/événement). Cela signifie qu'un
« parcours à plusieurs sauts » ici ne peut pas être l'exemple classique
des amis-des-amis de la question de recherche initiale de ce projet — il
n'y a pas d'arête directe acteur-à-acteur dans les données brutes par
défaut. Un parcours doit alterner `acteur → dépôt → acteur → dépôt`, en
sautant via des *dépôts partagés* (ou, quand c'est disponible, via un
second acteur nommé à l'intérieur du `payload` d'un événement).

Pour bien concevoir ce schéma — en suivant le principe « requête d'abord »
ci-dessus — l'étape suivante consistait à découvrir *où dans les données
un second acteur apparaît réellement*, car sans cela, il n'y a nulle part
où sauter au-delà de « un autre dépôt touché par ce même acteur ».
`scripts/profile_schema.py` lit le fichier entier et rapporte, par type
d'événement :

- quels champs de `payload` existent, à quelle fréquence, et de quel type
  ils sont
- tout objet imbriqué ayant la forme d'une référence à un utilisateur
  GitHub (`{"id": ..., "login": "..."}`) trouvé n'importe où à l'intérieur
  de `payload`, et le chemin pour y accéder (par ex.
  `payload.pull_request.user`)

Exécutez-le avec :

```bash
python scripts/profile_schema.py

# Se concentrer sur un seul type d'événement
python scripts/profile_schema.py --type PushEvent
```

**Découverte clé :** `PushEvent` — 95,3 % de tous les événements de
l'heure fixe de ce projet — ne porte aucun second acteur nulle part dans
son payload ; il n'a que `ref`, `before`/`head` (des SHA de commit), et
`repository_id`. Le `payload.pull_request` de `PullRequestEvent` est
également une référence tronquée qui omet l'auteur de la PR (contrairement
à la réponse complète de l'API REST de GitHub). Les véritables références
à un second acteur vivent presque entièrement dans les ~4,7 % d'événements
restants — commentaires, revues, issues, releases, forks, et changements
d'adhésion (répartition complète dans
[gh-archive-guide.md](gh-archive-guide.md#où-apparaît-un-second-acteur-références-imbriquées)).
Cela façonne directement la décision de schéma : une arête acteur-à-acteur,
si elle est modélisée, sera éparse et provenant d'une petite tranche des
types d'événements — l'essentiel de la connectivité du graphe viendra des
arêtes acteur→dépôt elles-mêmes (de nombreux acteurs partageant un dépôt),
pas de liens directs acteur→acteur.

Le pipeline global jusqu'à présent est : **download_gharchive.py →
peek_data.py → summarize_data.py → profile_schema.py** — d'abord récupérer
et décompresser l'heure fixe du jeu de données, puis inspecter une poignée
d'événements bruts, puis obtenir une lecture agrégée du volume et de la
connectivité, puis profiler la forme du payload et localiser les
références à un second acteur, avant de passer à l'extraction et au
chargement effectifs des enregistrements dans les modèles relationnel et
graphe comparés.
