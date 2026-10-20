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

`scripts/peek_data.py` ([copie annotée](peek_data.py)) lit les premiers événements du fichier et affiche
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

`scripts/summarize_data.py` ([copie annotée](summarize_data.py)) lit le fichier JSON Lines entier une seule fois
et affiche trois sections :

1. **Général :** le total d'événements, d'acteurs uniques et de dépôts
   uniques, chacun réparti entre bots et non bots (y compris combien de
   dépôts n'ont eu des événements *que* de bots).
2. **Analyse avec bots :** tous les événements.
3. **Analyse sans bots :** la même analyse, en retirant tous les comptes
   dont le login finit par `[bot]`.

Les sections 2 et 3 montrent exactement les mêmes choses, pour pouvoir les
comparer côte à côte :

- la répartition par type d'événement (décompte et pourcentage, du plus
  fréquent au moins fréquent)
- les N acteurs et dépôts les plus actifs par nombre d'événements
- la connectivité : combien de dépôts ont 2 acteurs différents ou plus,
  combien d'acteurs ont fait des événements dans 2 dépôts ou plus, et
  combien d'acteurs partagent un dépôt avec au moins un autre acteur
- les N acteurs ayant fait des événements dans le plus de dépôts
  *différents*, et les N dépôts ayant le plus d'acteurs *différents*

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

**Uniques vs. total — comment lire ces chiffres.** « Acteurs uniques » et
« total d'événements » répondent à des questions différentes. Si `ana` fait
3 événements et `luis` en fait 2, il y a 5 événements mais seulement 2
acteurs uniques. Le script tient un `Counter` pour chaque chose qu'il
compte — un dictionnaire *nom → nombre d'événements* — et `len()` de ce
dictionnaire donne le nombre de noms *distincts*, alors qu'additionner
toutes ses valeurs redonnerait simplement le total d'événements (la
[copie annotée](summarize_data.py) le détaille avec un exemple concret).
Cette distinction compte pour ce projet, car les acteurs uniques et les
dépôts uniques sont ce qui deviendra les **nœuds** du graphe (et les lignes
des tables Actor et Repo) — environ 14,7k + 16,5k ≈ 31k nœuds pour cette
heure — tandis que les événements sont ce qui les *relie*. En moyenne,
chaque acteur a produit environ 4,7 événements (69 429 ÷ 14 728), mais
cette moyenne cache une répartition très inégale, avec des bots en tête de
liste ; c'est pourquoi la décision de filtrage des bots ci-dessus influe
directement sur le degré de connexion du graphe.

### Résultats de connectivité : avec et sans bots

Compter les événements et les noms uniques ne suffit pas pour savoir si les
données permettent le benchmark. Le benchmark parcourt
`acteur → dépôt → acteur → dépôt`, et chaque pas d'un dépôt vers un *autre*
acteur n'est possible que si ce dépôt a été touché par au moins deux
acteurs différents. `summarize_data.py` mesure donc aussi la connectivité,
une fois avec tous les événements et une fois sans les comptes dont le
login finit par `[bot]` :

| Mesure | Tous les événements | Sans bots |
|---|---|---|
| Événements | 69 429 | 67 459 (1 970 événements de bots retirés, 2,8 %) |
| Acteurs uniques | 14 728 | 14 515 (213 acteurs bots retirés, 1,4 %) |
| Dépôts uniques | 16 497 | 14 995 (1 502 dépôts n'ayant eu que des événements de bots retirés, 9,1 %) |
| Dépôts avec 2+ acteurs distincts | 145 (0,9 % des dépôts) | 49 (0,3 %) |
| Acteurs ayant touché 2+ dépôts | 256 (1,7 % des acteurs) | 211 (1,5 %) |
| Acteurs partageant un dépôt avec un autre acteur | 234 (1,6 % des acteurs) | 101 (0,7 %) |

**Conclusions :**

1. **Les push dominent.** `PushEvent` représente 95,3 % de tous les
   événements (96,3 % sans bots). Les types d'événements qui *pourraient*
   relier directement deux personnes (commentaires, revues, issues) font
   environ 1 % au total, et seuls 0,26 % des événements nomment vraiment
   une seconde personne, différente de l'acteur. Les connexions entre acteurs viendront donc presque
   entièrement des *dépôts partagés*, ce qui concorde avec ce qu'a trouvé
   `profile_schema.py` (voir l'étape de conception du schéma plus bas).
2. **Plus de dépôts que d'acteurs signifie que certains acteurs touchent
   plusieurs dépôts.** Si chaque acteur n'avait touché qu'un seul dépôt,
   il y aurait au plus autant de dépôts que d'acteurs. Il y a plus de
   dépôts (16 497 contre 14 728), donc certains acteurs ont forcément
   travaillé sur plusieurs — mais seulement 1,7 % d'entre eux.
3. **Le graphe est extrêmement fragmenté.** 99 % des dépôts ont été touchés
   par un seul acteur, et environ 98 % des acteurs ne partagent aucun dépôt
   avec qui que ce soit. L'événement typique est une personne qui pousse
   vers son propre dépôt. Le dépôt le plus « partagé » compte 12 acteurs
   distincts avec les bots, et seulement 4 sans. Pour un benchmark de
   parcours, c'est le résultat clé : la plupart des parcours s'arrêteraient
   après le premier saut.
4. **Les bots pèsent peu en volume mais beaucoup en connectivité.** Les bots
   ne représentent que 2,8 % des événements, mais `github-actions[bot]` à
   lui seul touche 785 dépôts différents. Retirer les bots supprime environ
   deux tiers des dépôts partagés (145 → 49) et plus de la moitié des
   acteurs connectés (234 → 101) : la plupart des connexions de cette heure
   viennent des bots. Ils
   agissent comme des centres artificiels, reliant des dépôts qui n'ont
   rien à voir entre eux. Un benchmark lancé sur ces données mesurerait
   surtout « tout se connecte via github-actions » ; les bots doivent donc
   être exclus des données du benchmark.
5. **Le filtre `[bot]` n'est pas complet.** Certains comptes automatisés
   n'utilisent pas ce suffixe : `Copilot` touche 41 dépôts. Et une fois les
   bots retirés, les comptes les plus actifs ont des noms qui semblent
   générés (`beckjulie09`, `hayeshenry6`, ...), chacun poussant 35 à 39
   fois vers son propre dépôt au nom aléatoire (`hpmxym`, `eznfko`, ...) —
   probablement des comptes automatisés ou du spam. Ils n'ajoutent pas de
   connexions (chacun ne touche que son propre dépôt), mais ils gonflent
   le volume d'événements.

**Ce que cela implique pour le projet :**

- **Une heure de données ne suffit pas pour un benchmark multi-sauts.** Avec
  seulement une centaine d'acteurs connectés une fois les bots retirés, un
  parcours de 3 ou 4 sauts n'a presque nulle part où aller. L'étape
  suivante est de télécharger plus d'heures (par ex. une journée complète,
  ou plusieurs jours) et de relancer `summarize_data.py` pour voir si le
  nombre de dépôts partagés augmente. La question de recherche porte aussi
  sur le *volume* de données, donc il faudra de toute façon plusieurs
  tailles de jeu de données.
- **Politique sur les bots :** exclure les comptes `[bot]` des données du
  benchmark, et envisager une liste d'exclusion explicite pour les comptes
  automatisés connus sans ce suffixe (comme `Copilot`).
- **Vérifier la connectivité avant chaque benchmark.** Relancer ces mesures
  sur chaque taille de jeu de données avant de chronométrer une requête,
  pour ne jamais lancer le benchmark sur un graphe où il n'y a rien à
  parcourir.

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

**D'où vient cette section.** Jusqu'ici, toutes les étapes ont servi à
*connaître les données* : ce que contient un événement (`peek_data.py`),
combien d'événements, d'acteurs et de dépôts il y a et comment ils sont
reliés (`summarize_data.py`). L'étape suivante du projet est de *concevoir
les schémas* : les tables de la base de données relationnelle et les nœuds
et arêtes de la base de données graphe. Avant de dessiner une seule table,
il faut décider **selon quel critère** on va les concevoir, et cette
section fixe ce critère.

Elle découle directement de la section précédente sur ce qu'est un
benchmark : un test équitable où tout est contrôlé sauf ce qu'on mesure.
Le schéma fait partie de ce « tout le reste » qu'il faut contrôler. Si les
deux schémas ne sont pas équivalents, le benchmark ne compare plus un
modèle relationnel à un modèle graphe, mais deux conceptions différentes.

**Deux termes clés**

- **Schéma :** la « forme » des données dans la base. En relationnel :
  quelles tables, quelles colonnes, quelles clés. En graphe : quels types
  de nœud, quels types d'arête et quelles propriétés.
- **Requête :** la question précise posée à la base de données, et dont
  on mesure le temps. Par exemple : « en partant de l'acteur X, quels
  dépôts peut-on atteindre en 3 sauts ? ».

**Deux façons de concevoir un schéma**

| | Champs d'abord | Requête d'abord |
|---|---|---|
| Point de départ | Regarder le JSON de GH Archive | Écrire la requête du benchmark |
| Question posée | « Quels champs existent ? » | « De quoi cette requête a-t-elle besoin pour fonctionner ? » |
| Résultat | Des dizaines de tables ou de types de nœud (commits, messages, PR, commentaires, labels...), la plupart jamais interrogés | Seulement le minimum : Acteur, Dépôt, et la connexion entre eux |

« Champs d'abord » est tentant parce que cela semble plus complet : GH
Archive fournit des messages de commit, des titres de PR, le texte des
revues, des labels d'issue... et on a l'impression que plus on modélise,
mieux c'est. Mais le benchmark de parcours ne lit jamais rien de tout
cela. Tout ce détail serait construit, chargé et maintenu sans influencer
la mesure — ou pire, en l'influençant d'une façon non voulue (voir plus
bas).

**Exemple avec ce projet.** La requête du benchmark est un parcours
`acteur → dépôt → acteur → dépôt`. Pour y répondre, il suffit de savoir
trois choses : qui est chaque acteur, ce qu'est chaque dépôt, et quel
acteur a fait des événements dans quel dépôt. Le schéma minimal est donc
le même des deux côtés :

| Concept | Relationnel | Graphe |
|---|---|---|
| Acteur | table `actor` (id, login) | nœud `Actor` (id, login) |
| Dépôt | table `repo` (id, name) | nœud `Repo` (id, name) |
| Connexion | table `actor_repo` (actor_id, repo_id) | arête `Actor → Repo` |

Pourquoi le parcours doit-il passer par les dépôts, au lieu d'aller
directement d'un acteur à un autre ? Parce que les données ne relient
presque jamais deux personnes directement. `PushEvent` (95,3 % des
événements) ne nomme aucun second acteur (voir l'étape de conception du
schéma plus bas), et la connectivité mesurée par `summarize_data.py`
montre que les connexions entre acteurs viennent des *dépôts partagés*.

**Pourquoi il est important de suivre ce principe**

1. **On mesure ce qu'on veut mesurer.** Le temps d'une requête dépend de
   la quantité de données que la base doit lire. Si chaque ligne traîne
   des colonnes que la requête n'utilise pas (par exemple de longs
   messages de commit), la base lit plus de données sur le disque, et le
   temps mesuré inclut ce bruit en plus du coût réel du parcours.
2. **La comparaison est équitable.** Si un côté a plus de détail que
   l'autre, le résultat reflète la différence de conception, pas la
   différence entre les modèles. Par exemple : si le côté relationnel
   stocke une ligne par événement (69 429 lignes) et le côté graphe une
   seule arête par paire acteur–dépôt (beaucoup moins), le graphe
   « gagne » parce qu'il contient moins de données, pas parce qu'il
   parcourt mieux. Cela répondrait mal à la question de recherche.
3. **On peut prouver que les deux côtés sont équivalents.** Avec un petit
   schéma, il est facile de vérifier que les deux bases contiennent
   exactement la même chose : le même nombre d'acteurs, de dépôts et de
   connexions. Avec des dizaines de tables, cette vérification devient
   difficile.
4. **Moins de travail et moins d'erreurs.** Moins de tables, c'est moins
   de code de chargement, des chargements plus rapides et moins d'endroits
   où se tromper. Le temps gagné peut servir à l'essentiel : répéter les
   mesures avec différentes tailles de données.
5. **C'est reproductible et facile à expliquer.** Dans le rapport final,
   le schéma tient en trois lignes, et n'importe qui peut le reconstruire
   et refaire l'expérience.

**Mesures concrètes à suivre**

1. **Écrire d'abord la requête** (ou les requêtes) du benchmark, en mots,
   avant de créer la moindre table ou le moindre nœud.
2. **Lister les données que lit cette requête.** Seules celles-ci entrent
   dans le schéma. Si un champ n'apparaît pas dans la requête, il reste
   dehors.
3. **Construire le même modèle des deux côtés**, comme dans le tableau
   ci-dessus : les mêmes entités et la même connexion.
4. **Charger les deux côtés à partir des mêmes données sources** (les mêmes
   fichiers et le même filtre de bots) et vérifier que les décomptes
   correspondent avant de mesurer quoi que ce soit.
5. **Décider une seule fois comment la connexion est stockée** (une par
   événement, ou une par paire acteur–dépôt) et appliquer cette même
   décision des deux côtés.
6. **Donner à chaque côté ses aides normales, ni plus ni moins.** Côté
   relationnel, cela veut dire des index sur les colonnes utilisées pour
   joindre les tables (`actor_id`, `repo_id`) ; le graphe stocke déjà les
   connexions directement. Mesurer le relationnel sans index reviendrait à
   le comparer à une version délibérément lente.
7. **Si on ajoute quelque chose, l'ajouter des deux côtés à la fois, ou
   d'aucun.** Une nouvelle propriété, un index ou un autre type de
   connexion : toujours des deux côtés, pour que la comparaison reste
   équivalente.

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
`scripts/profile_schema.py` ([copie annotée](profile_schema.py)) lit le fichier entier et rapporte, par type
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

### Nouveau concept : la récursivité (une fonction qui s'appelle elle-même)

`profile_schema.py` introduit une idée de programmation qui n'apparaissait
pas dans les scripts précédents : la **récursivité** (ou récursion). Sa
fonction `find_actor_refs()` s'appelle *elle-même* dans son propre corps.
(Ce n'est pas « imbriquer » une fonction : imbriquer veut dire *définir*
une fonction à l'intérieur d'une autre. Ici, il y a une seule fonction qui
s'*appelle* elle-même.)

**Pourquoi c'est possible.** À chaque appel d'une fonction, Python crée
une copie neuve et séparée de ses paramètres et de ses variables pour cet
appel. Le nouvel appel travaille avec ses propres valeurs, et l'appel qui
l'a lancé attend, en pause, de recevoir la réponse, puis continue.

**Une analogie.** Les poupées russes (matriochkas) : pour trouver un mot
caché quelque part dans un jeu de poupées, les instructions sont les mêmes
à chaque niveau : *« ouvre la poupée ; si le mot est là, prends-le ;
sinon, applique ces mêmes instructions à chaque poupée qui se trouve
dedans »*. Les instructions font référence à elles-mêmes.

**Pourquoi ce script en a besoin.** Le `payload` d'un événement est un
dictionnaire qui peut contenir des dictionnaires, qui peuvent contenir des
listes de dictionnaires, et ainsi de suite — et on ne sait pas à l'avance
combien de niveaux il y a. Une boucle `for` ordinaire ne regarde qu'un
niveau. Une fonction récursive s'occupe d'un niveau, puis se demande *à
elle-même* de s'occuper du suivant, quel que soit leur nombre :

```
payload = {"action": "created", "issue": {"user": {"login": "luis"}}}

find_actor_refs(payload)               -> un dict sans "login" : regarde dedans
  find_actor_refs("created")           -> un texte : rien dedans -> []
  find_actor_refs({"user": {...}})     -> un dict sans "login" : regarde dedans
    find_actor_refs({"login": "luis"}) -> un utilisateur ! -> ["payload.issue.user"]
résultat : ["payload.issue.user"]
```

**Les deux règles dont a besoin toute fonction récursive :**

1. **Un cas de base :** une situation où elle répond *sans* s'appeler
   elle-même (ici : elle a trouvé un utilisateur, atteint une valeur
   simple, ou atteint la limite de profondeur). Sans cela, elle
   s'appellerait elle-même à l'infini.
2. **Chaque appel doit se rapprocher d'un cas de base** (ici : chaque
   appel descend d'un niveau dans les données, et le compteur `depth`
   diminue de 1, avec `MAX_SEARCH_DEPTH = 3` comme limite).

La récursivité est l'outil naturel dès que les données ressemblent à des
*boîtes dans des boîtes* : des dossiers dans des dossiers, du JSON dans du
JSON et, plus tard dans ce projet, l'exploration d'un graphe saut par
saut. La [copie annotée](profile_schema.py) détaille `find_actor_refs()`
ligne par ligne, et la partie suivante suit un exemple complet appel
par appel.

### Exemple complet : le déroulé de `find_actor_refs()` pas à pas

Cet exemple passe par **toutes** les branches de la fonction : un
dictionnaire sans `login`, un dictionnaire avec `login`, une liste, des
valeurs simples et la limite de profondeur. Vous pouvez le lire avec le
code de la fonction à côté :

```python
def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    if depth < 0:
        return []

    if isinstance(value, dict):
        if isinstance(value.get("login"), str):
            return [path]
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    return []
```

#### 1. Les données d'exemple

Un `payload` semblable à celui d'un `IssuesEvent` :

```python
payload = {
    "action": "opened",
    "issue": {
        "number": 7,
        "user": {"login": "luis", "id": 1},
        "assignees": [{"login": "ana"}, {"login": "marta"}],
        "milestone": {"creator": {"login": "pedro"}}
    }
}
```

`profile()` lance tout avec un seul appel :
`find_actor_refs(payload, "payload", 3)`.

#### 2. La règle qui crée les appels suivants

Chaque nouvel appel **naît de la boucle d'un appel précédent**. Pour
comprendre comment, il faut d'abord cinq notions de base de Python.
Ensuite, on les assemble.

##### 2.1 Notions de base

**a) Un dictionnaire stocke des paires *clé → valeur*.**
C'est comme un carnet d'adresses : on cherche par le nom (la **clé**) et on
obtient l'information (la **valeur**). Notre `payload` est un dictionnaire
à **deux** clés :

```python
payload = {
    "action": "opened",       # clé "action" → valeur "opened"
    "issue":  {...}           # clé "issue"  → valeur : un autre dictionnaire
}

payload["action"]   # → "opened"
payload["issue"]    # → {...} (le dictionnaire de l'issue)
```

**b) `.items()` donne toutes les paires, l'une après l'autre.**
Pour parcourir un dictionnaire en entier, `.items()` donne chaque entrée
sous forme de **paire** `(clé, valeur)` :

```python
list(payload.items())
# → [("action", "opened"), ("issue", {...})]
#      └─ 1re paire ─┘     └── 2e paire ──┘
```

**c) Le `for` prend une paire à chaque tour et la répartit dans deux
variables.**
Quand on écrit deux noms séparés par une virgule après `for`, Python prend
chaque paire et met sa première partie dans la première variable et sa
seconde partie dans la seconde :

```python
for key, sub_value in payload.items():
    print(key, "→", sub_value)

# 1er tour :  key = "action"   sub_value = "opened"
# 2e tour  :  key = "issue"    sub_value = {...}
```

`key` et `sub_value` ne sont que des noms qu'on a choisis. Ils changent de
valeur à chaque tour : d'abord ceux de la 1re paire, puis ceux de la 2e.

**d) Quand on appelle une fonction, chaque argument va à son paramètre,
dans l'ordre.**
La fonction est définie avec trois paramètres :

```python
def find_actor_refs(value, path, depth):
```

Donc, dans un appel comme celui-ci :

```python
find_actor_refs("opened", "payload.action", 2)
#               │         │                 │
#               ▼         ▼                 ▼
#             value     path              depth
```

à l'intérieur de cet appel, `value` vaut `"opened"`, `path` vaut
`"payload.action"` et `depth` vaut `2`. La **première** valeur va au
**premier** paramètre, la deuxième au deuxième et la troisième au
troisième. Et chaque appel a **ses propres** copies de ces variables (voir
la partie sur la récursivité).

**e) Une f-string construit un texte à partir de variables.**
Un texte précédé d'un `f` peut contenir des variables entre accolades
`{}`, et Python les remplace par leur valeur :

```python
path = "payload"
key = "action"
f"{path}.{key}"     # → "payload" + "." + "action" → "payload.action"
```

Le point du milieu est un point ordinaire, qui fait partie du texte. C'est
pour cela que le résultat ressemble à une « adresse » dans les données :
`payload.action` veut dire « la clé `action` dans le `payload` ».

##### 2.2 Assembler les morceaux

Voici maintenant la ligne de la boucle de la fonction :

```python
for key, sub_value in value.items():
    refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
```

> **Boucle, itération et tour.** Une **boucle** (en anglais *loop*) est le
> bloc de code qui se répète en entier : le `for ...:` avec tout ce qu'il
> contient. Chacune de ses répétitions est une **itération** (en anglais
> *iteration*), ou, de façon plus familière, un **tour** : dans ces notes,
> « tour » et « itération » veulent dire la même chose. Le verbe
> **itérer** (*to iterate*) signifie parcourir quelque chose élément par
> élément, ce que fait justement une boucle. Par exemple, l'`issue` a 4
> clés, donc la boucle de l'appel 3 fait **4 itérations** (`number`,
> `user`, `assignees` et `milestone`).

Suivons-la dans l'**appel 1**. Au début de cet appel, ses trois paramètres
valent (notion *d*) :

| Paramètre | Valeur dans l'appel 1 |
|---|---|
| `value` | tout le `payload` |
| `path` | `"payload"` |
| `depth` | `3` |

`value` est un dictionnaire à deux clés, donc `value.items()` donne deux
paires (notion *b*) et la boucle fait **deux tours** (notion *c*). À chaque
tour, Python calcule les trois arguments du nouvel appel :

| | 1er tour | 2e tour |
|---|---|---|
| `key` (notion *c*) | `"action"` | `"issue"` |
| `sub_value` (notion *c*) | `"opened"` | le dictionnaire de l'`issue` |
| 1er argument : `sub_value` | `"opened"` | le dictionnaire de l'`issue` |
| 2e argument : `f"{path}.{key}"` (notion *e*) | `"payload" + "." + "action"` = `"payload.action"` | `"payload" + "." + "issue"` = `"payload.issue"` |
| 3e argument : `depth - 1` | `3 - 1` = `2` | `3 - 1` = `2` |
| **Appel qui naît** | `find_actor_refs("opened", "payload.action", 2)` → **appel 2** | `find_actor_refs({...issue...}, "payload.issue", 2)` → **appel 3** |

Et quand l'appel 2 commence, ses paramètres reçoivent ces trois valeurs
dans l'ordre (notion *d*) : `value = "opened"`, `path = "payload.action"`
et `depth = 2`. **Ce qui, dans l'appel 1, était `sub_value`, le texte
construit et `depth - 1` devient `value`, `path` et `depth` dans
l'appel 2.**

Ce que fait `refs.extend(...)` avec la réponse de chaque appel est expliqué
plus bas, dans la partie 6.

##### 2.3 La règle générale

La même chose se produit dans tous les appels de l'exemple :

- **Dictionnaire →** un appel par clé. La **valeur** devient le nouveau
  `value`, la **clé** est ajoutée au `path`, et `depth` baisse de 1.
- **Liste →** un appel par élément. L'élément devient le nouveau `value` ;
  comme il n'y a pas de clé, le `path` **ne change pas**, et `depth`
  baisse de 1.
- **Utilisateur** (dictionnaire avec `login`) **ou valeur simple →** plus
  aucun appel : la fonction répond directement. Ce sont les **cas de
  base**.

C'est pour cela qu'il y a autant d'appels : **chaque conteneur génère un
appel pour chaque chose qu'il contient**.

#### 3. L'arbre des appels

```
APPEL 1   payload (dict à 2 clés)
├── APPEL 2   action    → "opened", un texte          → []
└── APPEL 3   issue     → dict à 4 clés
    ├── APPEL 4   number    → 7, un nombre            → []
    ├── APPEL 5   user      → utilisateur luis !      → ["payload.issue.user"]
    ├── APPEL 6   assignees → liste à 2 éléments
    │   ├── APPEL 7   ana    → utilisateur !          → ["payload.issue.assignees"]
    │   └── APPEL 8   marta  → utilisateur !          → ["payload.issue.assignees"]
    └── APPEL 9   milestone → dict à 1 clé
        └── APPEL 10  creator → utilisateur pedro !   → ["payload.issue.milestone.creator"]
```

Chaque branche se termine quand elle atteint un **utilisateur** ou une
**valeur simple**.

#### 4. Tous les appels, un par un

| Appel | Vient de | `value` | `path` | `depth` | Ce qu'il fait | Renvoie |
|---|---|---|---|---|---|---|
| 1 | `profile()` | tout le `payload` | `"payload"` | 3 | dict sans `login` → regarde ses 2 clés | 4 chemins |
| 2 | appel 1, tour 1 (`action`) | `"opened"` | `"payload.action"` | 2 | texte, rien dedans | `[]` |
| 3 | appel 1, tour 2 (`issue`) | l'`issue` | `"payload.issue"` | 2 | dict sans `login` → regarde ses 4 clés | 4 chemins |
| 4 | appel 3, tour 1 (`number`) | `7` | `"payload.issue.number"` | 1 | nombre, rien dedans | `[]` |
| 5 | appel 3, tour 2 (`user`) | `{"login": "luis", "id": 1}` | `"payload.issue.user"` | 1 | utilisateur ! | `["payload.issue.user"]` |
| 6 | appel 3, tour 3 (`assignees`) | la liste `[ana, marta]` | `"payload.issue.assignees"` | 1 | liste → regarde ses 2 éléments | 2 chemins |
| 7 | appel 6, élément 1 | `{"login": "ana"}` | `"payload.issue.assignees"` (le même) | 0 | utilisateur ! | `["payload.issue.assignees"]` |
| 8 | appel 6, élément 2 | `{"login": "marta"}` | `"payload.issue.assignees"` (le même) | 0 | utilisateur ! | `["payload.issue.assignees"]` |
| 9 | appel 3, tour 4 (`milestone`) | `{"creator": {...}}` | `"payload.issue.milestone"` | 1 | dict sans `login` → regarde son unique clé | 1 chemin |
| 10 | appel 9, tour 1 (`creator`) | `{"login": "pedro"}` | `"payload.issue.milestone.creator"` | 0 | utilisateur ! | `["payload.issue.milestone.creator"]` |

Regardez la colonne `depth` : elle baisse de 1 à chaque niveau
(3 → 2 → 1 → 0). Les appels 7, 8 et 10 arrivent avec `depth = 0`, ce qui
est encore permis car la vérification est `depth < 0`, et zéro n'est pas
inférieur à zéro.

#### 5. L'ordre dans le temps : pourquoi 6, 7, 8 puis 9

Les appels sont numérotés dans l'ordre où ils **se produisent**, et Python
**termine complètement un appel, avec tous ses « enfants », avant de
revenir au précédent**. L'appel extérieur reste en pause pendant ce temps :

1. L'appel 1 lance l'**appel 2** (clé `action`). L'appel 2 renvoie `[]`
   tout de suite.
2. L'appel 1 lance l'**appel 3** (clé `issue`) et se met en pause.
3. L'appel 3 lance l'**appel 4** (`number`), qui renvoie `[]`, puis
   l'**appel 5** (`user`), qui trouve luis.
4. L'appel 3 lance l'**appel 6** (`assignees`) et se met en pause.
5. L'appel 6 lance l'**appel 7** (ana) puis l'**appel 8** (marta). Quand
   l'appel 8 se termine, l'appel 6 a parcouru toute sa liste et **renvoie**
   son résultat à l'appel 3.
6. **Seulement alors** l'appel 3 reprend et fait son dernier tour : il
   lance l'**appel 9** (`milestone`), qui lance à son tour l'**appel 10**
   (`creator`).
7. L'appel 10 répond à l'appel 9, le 9 au 3, et le 3, qui a fini sa
   boucle, répond au 1.

C'est comme ouvrir des poupées russes : avant de passer à la poupée
suivante du même niveau, on ouvre complètement celle qu'on a en main et
toutes celles qu'elle contient.

#### 6. Comment la liste `refs` se remplit

Chaque appel a **sa propre** liste `refs`, et la remplit avec ce que lui
renvoient ses appels enfants, grâce à `refs.extend(...)`. Voici comment
grandit la `refs` de l'**appel 3** :

| Après la réponse de... | Ce qu'il renvoie | `refs` de l'appel 3 |
|---|---|---|
| (au départ) | — | `[]` |
| l'appel 4 | `[]` | `[]` (inchangée) |
| l'appel 5 | `["payload.issue.user"]` | `["payload.issue.user"]` |
| l'appel 6 | `["payload.issue.assignees", "payload.issue.assignees"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees"]` |
| l'appel 9 | `["payload.issue.milestone.creator"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees", "payload.issue.milestone.creator"]` |

**Quand un appel ne trouve rien,** il renvoie une liste vide (`[]`).
`.extend([])` ajoute à `refs` tous les éléments de cette liste, c'est-à-dire
aucun, donc **il n'y a rien à ajouter et la liste reste comme avant**. C'est
le cas des appels 2 et 4. Seuls les appels qui trouvent *vraiment* un
utilisateur (5, 7, 8 et 10) font grandir les listes.

La `refs` de l'**appel 1** reçoit `[]` de l'appel 2 et les 4 chemins de
l'appel 3 ; le résultat final est donc :

```python
['payload.issue.user',
 'payload.issue.assignees',
 'payload.issue.assignees',
 'payload.issue.milestone.creator']
```

#### 7. Deux détails de plus

**La limite de profondeur en action.** Si un utilisateur se trouvait un
niveau plus bas que ce que permet `MAX_SEARCH_DEPTH = 3` :

```python
deep = {"a": {"b": {"c": {"d": {"login": "x"}}}}}
find_actor_refs(deep, "payload", 3)   # -> []
```

en arrivant à `{"login": "x"}`, `depth` vaudrait déjà **-1**, et la
première vérification (`if depth < 0: return []`) s'arrêterait là : il **ne
le trouve pas**. C'est le prix du filet de sécurité ; comme les payloads de
GH Archive sont peu profonds, on ne perd rien en pratique.

**Pourquoi `profile()` utilise `set(...)` ensuite.** Le résultat contient
`payload.issue.assignees` **deux fois**, une pour ana et une pour marta.
`profile()` fait `set(...)`, qui ne garde chaque chemin qu'une fois :

```python
{'payload.issue.user', 'payload.issue.assignees', 'payload.issue.milestone.creator'}
```

Ainsi cet événement compte comme **un** événement qui a des personnes
assignées, pas deux : ce qu'on compte, c'est *dans combien d'événements*
apparaît chaque chemin, pas combien d'utilisateurs il y a.

### À quoi sert le résultat

Le résultat de `profile_schema.py` est long et, à première vue, ressemble à
une liste de champs techniques. Mais il répond à une question très précise
du projet : **en plus de l'acteur qui a fait l'événement, l'événement
nomme-t-il une autre personne ?** Si la réponse était « oui, souvent », le
graphe pourrait avoir des connexions directes personne → personne (par
exemple « Ana a commenté l'issue de Luis »), et les parcours du benchmark
pourraient les utiliser. Si la réponse est « presque jamais », les
personnes ne sont reliées qu'à travers les dépôts qu'elles partagent, et
le schéma doit le refléter.

En plus de cela, le résultat sert à trois choses pratiques pour concevoir
le schéma :

1. **Savoir quelles données contient chaque type d'événement.** Chaque
   type d'événement stocke des choses différentes dans son `payload`. Un
   `PushEvent` stocke la branche et les commits ; un `IssueCommentEvent`
   stocke l'issue et le commentaire.
2. **Savoir si un champ est fiable.** « present in 100% » signifie que le
   champ est toujours là ; un pourcentage faible signifie qu'il n'apparaît
   que parfois. Dans une table, ce serait une colonne facultative (qui
   peut rester vide).
3. **Savoir de quel type de donnée il s'agit.** `str` (texte), `int`
   (nombre), `dict` (un objet contenant d'autres champs), `list` (une
   liste) ou `NoneType` (vide). Par exemple, dans `CreateEvent`, le champ
   `description` est vide (`NoneType`) dans 633 événements sur 1 290 : si
   on le stockait, il faudrait une colonne qui accepte les valeurs vides.

### Comment lire un bloc du résultat

```
IssueCommentEvent (194 events)
  payload.action               present in 100.0% (194/194) - types: str x194
  payload.issue                present in 100.0% (194/194) - types: dict x194
  payload.comment              present in 100.0% (194/194) - types: dict x194
  actor references (nested 'login' fields):
    payload.issue.user                  present in 100.0% (194/194)
    payload.comment.user                present in 100.0% (194/194)
```

- **Première ligne :** le type d'événement et combien d'événements de ce
  type il y a (194 commentaires sur des issues).
- **Lignes `payload.…` :** chaque champ du `payload`, dans quel
  pourcentage de ces événements il apparaît et quel type de donnée il
  contient. Ici, les trois champs sont toujours présents : `action` est du
  texte, et `issue` et `comment` sont des objets contenant d'autres
  données.
- **`actor references` :** les chemins dans le `payload` où se trouve un
  objet en forme d'utilisateur GitHub (un dictionnaire avec `login`), et
  dans quel pourcentage d'événements il apparaît. `payload.issue.user` est
  la personne qui a ouvert l'issue ; `payload.comment.user` est la
  personne qui a écrit le commentaire.

### Deuxième vérification : est-ce vraiment une autre personne ?

Il y a un piège. `profile_schema.py` vérifie seulement qu'un utilisateur
**existe** à ce chemin, pas **qui** il est. Et souvent, c'est l'acteur
lui-même : dans un `IssueCommentEvent`, la personne qui écrit le
commentaire (`comment.user`) est exactement celle qui a fait l'événement.
Pour le savoir, il faut comparer chaque utilisateur trouvé avec l'`actor`
de l'événement. Cette comparaison, faite sur les données de ce projet,
donne ceci :

| Type d'événement et chemin | Qui c'est | Est-ce l'acteur lui-même ? |
|---|---|---|
| `IssueCommentEvent` `comment.user` | l'auteur du commentaire | Oui, 100 % |
| `IssueCommentEvent` `issue.user` | la personne qui a ouvert l'issue | Seulement 34 % : **dans 66 % des cas, c'est quelqu'un d'autre** |
| `IssuesEvent` `issue.user` | la personne qui a ouvert l'issue | 87 % (chacun gère en général sa propre issue) |
| `PullRequestReviewEvent` `review.user` | l'auteur de la revue | 99 % |
| `PullRequestReviewCommentEvent` `comment.user` | l'auteur du commentaire | 100 % |
| `ReleaseEvent` `release.author` | l'auteur de la release | 100 % |
| `ForkEvent` `forkee.owner` | propriétaire de la nouvelle copie (le fork) | 100 % : celui qui fait le fork possède la copie |
| `assignee` / `assignees` (plusieurs types) | personnes assignées | Entre 30 % et 70 %, selon le cas |
| `performed_via_github_app.owner` | propriétaire de l'application qui a publié l'événement | Jamais, mais ce n'est pas non plus un participant : en général une organisation |

**Résultat :** sur les 69 429 événements, seuls **178 (0,26 %)** nomment
une personne réellement différente de l'acteur (sans compter les
propriétaires d'applications), et seuls **76** d'entre eux viennent
d'acteurs qui ne sont pas des bots. Presque tous sont des commentaires sur
l'issue de quelqu'un d'autre (`IssueCommentEvent`, 131) ou des actions sur
l'issue de quelqu'un d'autre (`IssuesEvent`, 35).

**Découverte clé :** `PushEvent` — 95,3 % de tous les événements — ne
nomme aucune autre personne dans son `payload` : il n'a que `ref`,
`before`/`head` (identifiants de commits) et `repository_id`. Le
`payload.pull_request` de `PullRequestEvent` est en outre une référence
tronquée qui omet l'auteur de la PR (contrairement à la réponse complète
de l'API REST de GitHub). Et dans les autres événements, la plupart des
utilisateurs imbriqués sont l'acteur lui-même. Une version précédente de
ces notes disait que les références à un second acteur se trouvaient dans
les ~4,7 % d'événements qui ne sont pas des `PushEvent` ; ce n'était
qu'une borne supérieure. Le chiffre réel, après comparaison avec
l'acteur, est de **0,26 %** (détail dans
[gh-archive-guide.md](gh-archive-guide.md#où-apparaît-un-second-acteur-références-imbriquées)).

**Ce que cela implique pour le schéma :** les connexions directes
personne → personne sont pratiquement inexistantes dans ces données. Avec
76 connexions entre personnes (sans bots), on ne peut construire aucun
parcours multi-sauts. C'est pourquoi le schéma du benchmark est **Acteur,
Dépôt et la connexion entre eux**, sans arête acteur → acteur : les
personnes sont reliées à travers les dépôts qu'elles partagent, comme le
mesure `summarize_data.py`. Et une leçon générale : un champ qui
*ressemble* à une autre personne n'en est pas forcément une ; il faut
toujours le vérifier par rapport à l'acteur.

### Synthèse : ce que l'on sait des données de cette heure

Cette partie rassemble en un seul endroit ce qu'ont découvert
`peek_data.py`, `summarize_data.py` et `profile_schema.py` sur l'heure fixe
du projet (2026-08-27, 15h00 UTC, 69 429 événements).

#### 1. Comment lire les données d'un événement

Chaque ligne du fichier est un JSON indépendant. `json.loads(line)` le
transforme en **dictionnaire** Python, et à partir de là on accède à chaque
donnée par sa clé. Certaines données se trouvent dans un **dictionnaire à
l'intérieur d'un autre dictionnaire**, d'où les **deux paires de
crochets** : la première entre dans le dictionnaire intérieur, la seconde
prend la valeur.

| Ce qu'on veut savoir | Comment l'obtenir | Exemple |
|---|---|---|
| Qui a fait l'action | `event["actor"]["login"]` | `"octocat"` |
| Son identifiant numérique | `event["actor"]["id"]` | `583231` |
| Dans quel dépôt | `event["repo"]["name"]` | `"octocat/Hello-World"` |
| L'identifiant numérique du dépôt | `event["repo"]["id"]` | `1296269` |
| Quel type d'action | `event["type"]` | `"PushEvent"` |
| Quand | `event["created_at"]` | `"2026-08-27T15:00:01Z"` |
| Les détails de l'action | `event["payload"]` | dépend du type d'événement |

Par exemple, `event["actor"]["login"]` se lit ainsi : « dans l'événement,
prends le dictionnaire `actor` ; dans celui-ci, prends la valeur de
`login` ».

Les cinq premières données sont présentes dans **tous** les événements
(vérifié : les 69 429 ont `actor.id` et `repo.id`). C'est exactement ce dont
a besoin le schéma minimal du benchmark : qui (Acteur), où (Dépôt) et la
connexion entre les deux. Pour les clés des tables et des nœuds, mieux vaut
utiliser les `id` numériques plutôt que les noms : un utilisateur peut
changer de `login`, mais son `id` ne change jamais.

#### 2. D'autres personnes dans le `payload`

Le `payload` peut contenir d'autres utilisateurs, de même forme que
l'acteur (un dictionnaire avec `login`). `profile_schema.py` les trouve en
cherchant `login` à n'importe quel niveau du `payload`, grâce à la
récursivité.

Mais **trouver un utilisateur ne veut pas dire trouver une autre
personne**. En comparant chaque utilisateur trouvé avec l'acteur de
l'événement, la plupart s'avèrent être l'acteur lui-même (voir « Deuxième
vérification » plus haut). Seuls **178 événements sur 69 429 (0,26 %)**
nomment vraiment une personne différente, et seulement **76** une fois les
bots retirés.

#### 3. Ce que contient chaque type d'événement dans cette heure

| Type d'événement | Événements | % du total | Ce que contient le `payload` | Utilisateurs dans le `payload` | Nomme-t-il une autre personne ? |
|---|---|---|---|---|---|
| `PushEvent` | 66 174 | 95,3 % | La branche (`ref`), le commit avant et après le push (`before`, `head`), `push_id` et `repository_id` | Aucun | Non |
| `CreateEvent` | 1 290 | 1,9 % | Ce qui a été créé : dans cette heure, toujours une branche (`ref_type = "branch"`). Aussi la branche principale et une `description`, vide dans 633 cas sur 1 290 | Aucun | Non |
| `DeleteEvent` | 615 | 0,9 % | Ce qui a été supprimé : 586 branches et 29 tags | Aucun | Non |
| `PullRequestEvent` | 532 | 0,8 % | L'action (`opened`, `closed`...), le numéro de la PR, un `pull_request` tronqué **sans son auteur**, et parfois des labels (25 %) | `assignee`/`assignees` (2,1 %) | Très rarement : 7 événements |
| `IssueCommentEvent` | 194 | 0,3 % | L'issue commentée et le commentaire | `comment.user` (100 %), `issue.user` (100 %), propriétaire de l'application (63 %), personnes assignées (16,5 %), créateur du milestone (3,6 %) | **Oui, le plus souvent :** `issue.user` est quelqu'un d'autre dans 66 % des cas (131 événements) |
| `IssuesEvent` | 189 | 0,3 % | L'issue et son action ; parfois des labels (45 %) et des personnes assignées (7,4 %) | `issue.user` (100 %), personnes assignées (20 %), propriétaire de l'application (11 %) et autres | Parfois : 35 événements (`issue.user` est l'acteur dans 87 % des cas) |
| `PullRequestReviewCommentEvent` | 134 | 0,2 % | Le commentaire et la PR | `comment.user` (100 %) | Non : c'est l'acteur |
| `PullRequestReviewEvent` | 131 | 0,2 % | La revue et la PR | `review.user` (100 %) | Presque jamais : 1 événement |
| `WatchEvent` | 96 | 0,1 % | Seulement l'action : toujours `started`, c'est-à-dire que quelqu'un a **mis une étoile** au dépôt | Aucun | Non |
| `ReleaseEvent` | 44 | 0,1 % | La release publiée | `release.author` (100 %), mentions (6,8 %) | Presque jamais : 2 événements |
| `ForkEvent` | 18 | 0,03 % | La nouvelle copie du dépôt (`forkee`) | `forkee.owner` (100 %) | Non : le propriétaire du fork est celui qui le crée |
| `CommitCommentEvent` | 7 | 0,01 % | Le commentaire sur un commit | `comment.user` (100 %) | Non : c'est l'acteur |
| `MemberEvent` | 5 | 0,01 % | La personne ajoutée au dépôt (`member`) | `member` (100 %) | Parfois : 2 événements |

Comment lire le tableau : la colonne « Utilisateurs dans le `payload` » est
ce qu'affiche `profile_schema.py`, et la dernière colonne est le résultat
de la comparaison de ces utilisateurs avec l'acteur.

#### 4. Ce que cela implique pour le projet

- **L'essentiel est dans tous les événements et facile à lire :**
  `actor.id`/`actor.login`, `repo.id`/`repo.name`, `type` et
  `created_at`. Cela suffit pour construire le schéma minimal (Acteur,
  Dépôt et la connexion entre eux).
- **Presque tout est un push (95,3 %), et un push ne nomme personne
  d'autre.** Les personnes sont reliées entre elles à travers les **dépôts
  qu'elles partagent**, pas directement.
- **Les connexions directes personne → personne sont presque
  inexistantes** (0,26 % des événements, 76 sans bots) ; le benchmark ne
  peut donc pas s'appuyer dessus. C'est pourquoi le schéma n'a pas d'arête
  acteur → acteur.
- **Un champ qui ressemble à une autre personne n'en est pas forcément
  une.** Avant d'utiliser un utilisateur du `payload`, il faut le vérifier
  par rapport à l'acteur, et écarter des chemins comme
  `performed_via_github_app.owner`, qui est le propriétaire d'une
  application et non un participant.
- **Cette heure seule est petite et fragmentée** (voir « Résultats de
  connectivité » dans l'étape de synthèse). L'étape suivante est de
  télécharger plus d'heures et de mesurer à nouveau.

Le pipeline global jusqu'à présent est : **download_gharchive.py →
peek_data.py → summarize_data.py → profile_schema.py** — d'abord récupérer
et décompresser l'heure fixe du jeu de données, puis inspecter une poignée
d'événements bruts, puis obtenir une lecture agrégée du volume et de la
connectivité, puis profiler la forme du payload et localiser les
références à un second acteur, avant de passer à l'extraction et au
chargement effectifs des enregistrements dans les modèles relationnel et
graphe comparés.


## Installation des logiciels (PostgreSQL, Neo4j et les connecteurs Python)

Une fois le schéma minimal décidé (tables `actor`, `repo` et `actor_repo`
dans la base relationnelle ; nœuds `Actor` et `Repo` reliés par une arête
dans la base graphe), l'étape suivante est d'installer les deux bases de
données et ce dont Python a besoin pour communiquer avec elles.

### Avant de commencer

**Ce que nous allons installer** (tout est gratuit) :

| Logiciel | À quoi il sert | Coût |
|---|---|---|
| **PostgreSQL** (avec **pgAdmin**) | La base de données relationnelle. pgAdmin est une interface graphique pour la consulter et lancer des requêtes | Gratuit, logiciel libre |
| **Neo4j Desktop** | Gère des bases de données graphe Neo4j sur votre ordinateur, avec une interface graphique | Gratuit pour un usage local de développement |
| **`psycopg`** (paquet Python) | Le connecteur qui permet à Python de communiquer avec PostgreSQL | Gratuit |
| **`neo4j`** (paquet Python) | Le connecteur officiel qui permet à Python de communiquer avec Neo4j | Gratuit |

**Les deux bases de données vont sur le même ordinateur.** Ainsi, aucune
n'a d'avantage parce qu'elle serait sur une autre machine ou derrière un
réseau : cela fait partie du principe « tout contrôler sauf ce qu'on
mesure » (voir la section sur ce qu'est un benchmark).

**Si vous utilisez un ordinateur portable d'entreprise :** installer des
logiciels peut nécessiter l'autorisation du service informatique ou être
limité par les règles de l'entreprise. Vérifiez-le avant de commencer.

**Les mots de passe ne vont jamais dans le dépôt.** Pendant l'installation,
vous choisirez deux mots de passe : un pour PostgreSQL et un pour Neo4j.
Gardez-les dans un gestionnaire de mots de passe. Ne les écrivez ni dans le
code, ni dans ces notes, ni dans aucun fichier envoyé sur GitHub. Plus bas,
on explique comment les transmettre à Python de façon sûre.

### Étape 1 : installer PostgreSQL

1. **Télécharger l'installateur.** Allez sur
   <https://www.postgresql.org/download/windows/> et cliquez sur *Download
   the installer*. Choisissez la **version la plus récente** pour
   **Windows x86-64**.
2. **Lancer l'installateur** et accepter les options par défaut, avec ces
   précisions :
   - **Composants :** laissez cochés *PostgreSQL Server*, *pgAdmin 4* et
     *Command Line Tools*. *Stack Builder* n'est pas nécessaire (vous
     pouvez le décocher).
   - **Mot de passe :** il vous demandera un mot de passe pour le
     superutilisateur `postgres`. Choisissez-le et enregistrez-le dans
     votre gestionnaire de mots de passe.
   - **Port :** gardez celui proposé, **5432**.
   - **Locale :** gardez celle par défaut.
   - À la fin, s'il propose de lancer *Stack Builder*, décochez-le.
3. **Ajouter `psql` au PATH** (pour pouvoir l'utiliser depuis Git Bash).
   `psql` est le programme en ligne de commande de PostgreSQL.
   L'installateur ne l'ajoute pas au PATH, donc :
   - Cherchez dans Windows *« Modifier les variables d'environnement pour
     votre compte »*.
   - Dans *Path*, cliquez sur *Modifier* → *Nouveau* et ajoutez
     `C:\Program Files\PostgreSQL\<version>\bin` (remplacez `<version>` par
     le numéro du dossier créé, par exemple `18`).
   - Fermez puis rouvrez Git Bash pour qu'il le prenne en compte.
   - Si vous préférez ne pas modifier le PATH, vous pouvez utiliser *SQL
     Shell (psql)* depuis le menu Démarrer, qui fait la même chose.
4. **Vérifier que cela fonctionne** (avec Git Bash ; pour le faire avec
   pgAdmin 4, voir la partie suivante) :

   ```bash
   psql -U postgres -c "SELECT version();"
   ```

   Il vous demandera le mot de passe de `postgres` et devrait afficher la
   version installée.
5. **Créer la base de données du projet** (avec Git Bash ; avec
   pgAdmin 4, voir la partie suivante) :

   ```bash
   psql -U postgres -c "CREATE DATABASE gharchive;"
   psql -U postgres -d gharchive -c "SELECT 1;"
   ```

   La seconde commande vérifie que vous pouvez vous connecter à la nouvelle
   base : elle devrait afficher un petit tableau avec un `1`.

PostgreSQL s'installe comme un **service Windows** : il démarre tout seul à
l'allumage de l'ordinateur et reste actif en arrière-plan. Si vous voulez
l'arrêter quand vous ne l'utilisez pas, cherchez *Services* dans Windows et
arrêtez le service `postgresql-x64-<version>`.

### Deux façons de travailler avec PostgreSQL : Git Bash (`psql`) ou pgAdmin 4

Tout ce qu'on fait avec `psql` dans Git Bash peut aussi se faire avec
**pgAdmin 4**, l'interface graphique installée avec PostgreSQL. **Vous
pouvez utiliser celle que vous préférez, ou les deux** : elles travaillent
sur la même base de données, donc ce que vous créez avec l'une, vous le
verrez avec l'autre.

| Tâche | Avec Git Bash (`psql`) | Avec pgAdmin 4 |
|---|---|---|
| Ouvrir | Un terminal Git Bash (avec `psql` dans le PATH, étape 1.3) | Chercher **pgAdmin 4** dans le menu Démarrer |
| Se connecter | Chaque commande contient `-U postgres` et demande le mot de passe (ou le lit dans `PGPASSWORD`) | Panneau de gauche : **Servers** → **PostgreSQL** → saisir le mot de passe de `postgres` |
| Voir la version | `psql -U postgres -c "SELECT version();"` | Ouvrir le Query Tool (voir plus bas), taper `SELECT version();` et appuyer sur **F5** |
| Créer la base `gharchive` | `psql -U postgres -c "CREATE DATABASE gharchive;"` | Clic droit sur **Databases** → **Create** → **Database...** → nom `gharchive` → **Save** |
| Exécuter une requête | `psql -U postgres -d gharchive -c "..."` | Sélectionner `gharchive` dans l'arbre → menu **Tools** → **Query Tool** → taper la requête → **F5** (ou ▶) |
| Voir les tables | `psql -U postgres -d gharchive -c "\dt"` | Arbre : **gharchive** → **Schemas** → **public** → **Tables** |
| Voir les données d'une table | `psql -U postgres -d gharchive -c "SELECT * FROM actor LIMIT 10;"` | Clic droit sur la table → **View/Edit Data** |

**Vérifier que PostgreSQL fonctionne avec pgAdmin 4 (sans Git Bash) :**

1. **Ouvrir pgAdmin 4** depuis le menu Démarrer de Windows. La première
   fois, il demandera un *master password* : un mot de passe propre à
   pgAdmin, qui protège les mots de passe qu'il enregistre. Choisissez-le
   et gardez-le dans votre gestionnaire de mots de passe.
2. **Se connecter au serveur :** dans le panneau de gauche, dépliez
   **Servers** (la petite flèche) et cliquez sur **PostgreSQL** (affiché
   avec son numéro de version, par exemple *PostgreSQL 18*). Il demandera
   le mot de passe de l'utilisateur **`postgres`**, celui choisi à
   l'installation.

   ✅ **Première vérification :** si le serveur se déplie et que vous voyez
   en dessous **Databases**, **Login/Group Roles** et **Tablespaces**,
   PostgreSQL fonctionne et accepte les connexions.
3. **Vérifier la version avec une requête :** dépliez **Databases** et
   cliquez sur **postgres** (la base fournie par défaut). Allez dans le
   menu **Tools** → **Query Tool**, tapez `SELECT version();` et appuyez
   sur **F5** (ou le bouton ▶ *Execute*).

   ✅ **Deuxième vérification :** en bas, dans *Data Output*, une ligne
   apparaît avec un texte du type `PostgreSQL 18.x on x86_64-windows...`.
4. **Créer la base du projet :** clic droit sur **Databases** → **Create**
   → **Database...**, tapez `gharchive` dans **Database** et cliquez sur
   **Save**.

   ✅ **Troisième vérification :** `gharchive` apparaît dans la liste
   **Databases**. Sélectionnez-la, rouvrez **Tools** → **Query Tool**,
   exécutez `SELECT 1;`, et vous devriez obtenir un `1`.

**Si quelque chose ne va pas :**

- **Erreur de mot de passe :** utilisez celui de l'utilisateur `postgres`
  (celui de l'installation), pas le *master password* de pgAdmin. Ce sont
  deux mots de passe différents.
- **« Could not connect to server » ou une erreur de connexion :** le
  service PostgreSQL n'est pas démarré. Cherchez **Services** dans
  Windows, trouvez `postgresql-x64-<version>` et cliquez sur
  **Démarrer**.

**Quand utiliser l'une ou l'autre :**

- **pgAdmin 4** est plus confortable pour **explorer** : voir quelles
  tables existent, regarder leurs données et essayer des requêtes
  tranquillement. Si vous l'utilisez, l'étape 1.3 (ajouter `psql` au PATH)
  est facultative.
- **Git Bash** reste nécessaire pour **exécuter les scripts Python** du
  projet (ceux qui créeront les CSV, chargeront les données et mesureront
  les temps). Et `psql` est pratique quand on veut répéter une commande
  toujours de la même façon, en la copiant depuis ces notes.

Autre option, si on préfère ne pas quitter l'éditeur : l'extension
**PostgreSQL** de Microsoft pour VS Code, qui permet aussi de se connecter
et d'exécuter des requêtes.

### Étape 2 : installer Neo4j Desktop

1. **Télécharger Neo4j Desktop.** Allez sur <https://neo4j.com/download/>.
   Un formulaire vous demandera quelques informations avant le
   téléchargement. Si la page affiche une **clé d'activation**, copiez-la :
   Neo4j Desktop vous la demandera à la première ouverture.
2. **L'installer et l'ouvrir.**
3. **Créer une base de données locale** (Neo4j Desktop l'appelle
   *instance* ou *DBMS*, selon la version) :
   - **Nom :** `gharchive`.
   - **Version :** la plus récente proposée.
   - **Mot de passe :** choisissez-en un pour l'utilisateur `neo4j` et
     enregistrez-le dans votre gestionnaire de mots de passe.
4. **La démarrer** avec le bouton *Start*. Neo4j écoute sur deux ports :
   - **7474**, pour le navigateur (Neo4j Browser) ;
   - **7687**, pour les programmes, dont Python (le protocole *Bolt*).
5. **Vérifier que cela fonctionne** (vérification rapide ; la complète
   est dans la partie suivante). Ouvrez Neo4j Browser (bouton *Open*,
   ou <http://localhost:7474> dans votre navigateur), connectez-vous avec
   l'utilisateur `neo4j` et votre mot de passe, et exécutez :

   ```cypher
   RETURN 1;
   ```

   Cela devrait renvoyer `1`.

Contrairement à PostgreSQL, la base Neo4j **ne fonctionne que tant qu'elle
est démarrée** dans Neo4j Desktop. Avant de travailler avec, ouvrez Neo4j
Desktop et vérifiez qu'elle est en marche.

### Vérifier que Neo4j fonctionne depuis l'interface

Neo4j se manipule presque toujours avec une interface graphique, donc pour
le vérifier **Git Bash n'est pas nécessaire**. Il y a deux outils
visuels :

| Outil | À quoi il sert | Équivalent dans PostgreSQL |
|---|---|---|
| **Neo4j Desktop** | Créer, démarrer et arrêter les bases de données | Le panneau **Servers** de pgAdmin |
| **Neo4j Browser** | Écrire des requêtes et voir les résultats, même dessinés sous forme de nœuds et d'arêtes | Le **Query Tool** de pgAdmin |

**Pas à pas :**

1. **Ouvrir Neo4j Desktop** et trouver la base de données `gharchive`.
   Selon la version de Desktop, elle apparaît dans la liste des
   *Instances* ou dans un *Project*.

   ✅ **Première vérification :** son état indique **Running** ou
   **Active** (en général avec un point vert). Si elle indique *Stopped*,
   cliquez sur **Start** et attendez quelques secondes.
2. **Ouvrir Neo4j Browser :** cliquez sur **Open** (ou *Query*, selon la
   version) à côté de la base, ou allez sur <http://localhost:7474> dans
   votre navigateur. S'il demande de se connecter :
   - **Connect URL :** `neo4j://localhost:7687`
   - **Username :** `neo4j`
   - **Password :** celui choisi à la création de la base

   ✅ **Deuxième vérification :** la connexion est acceptée et une barre
   pour taper des requêtes apparaît en haut, avec l'invite `neo4j$`.
3. **Vérifier la version.** Tapez ceci dans la barre du haut et appuyez sur
   **Ctrl + Entrée** (ou le bouton ▶) :

   ```cypher
   CALL dbms.components() YIELD name, versions, edition
   RETURN name, versions, edition;
   ```

   ✅ **Troisième vérification :** une ligne apparaît avec
   `Neo4j Kernel`, le numéro de version et l'édition.
4. **Essayer d'écrire et de lire**, pour confirmer qu'elle peut vraiment
   enregistrer des données :

   ```cypher
   CREATE (p:Test {message: "bonjour"}) RETURN p;
   ```

   ✅ **Quatrième vérification :** un **cercle** apparaît dans le
   résultat : c'est un nœud, dans la vue graphe de Neo4j. Si vous cliquez
   dessus, vous verrez sa propriété `message: "bonjour"`.

   Supprimez-le ensuite, pour laisser la base vide :

   ```cypher
   MATCH (p:Test) DELETE p;
   ```

   Cela devrait afficher *Deleted 1 node*.

**Le nom de la base de données.** Dans Neo4j Desktop, `gharchive` est le
nom de l'**instance** (le « serveur »). À l'intérieur, la base de données
dans laquelle on travaille s'appelle **`neo4j`** : c'est celle fournie par
défaut, et c'est celle que nous utiliserons. Inutile d'en créer une
autre ; le `neo4j$` de la barre de requêtes indique justement que vous y
êtes.

**Si quelque chose ne va pas :**

| Problème | Cause probable | Solution |
|---|---|---|
| La base ne passe pas à *Running* | Un autre programme utilise le port 7474 ou 7687 | Lisez le message d'erreur dans Desktop ; fermez l'autre programme ou changez le port dans la configuration |
| *Authentication failure* | Mauvais mot de passe | Utilisez celui choisi à la **création de la base** dans Neo4j Desktop (pas celui de PostgreSQL) |
| Neo4j Browser ne se connecte pas | La base est arrêtée | Revenez dans Desktop et cliquez sur **Start** |
| La vue graphe n'affiche rien | La requête ne renvoie aucun nœud | C'est normal pour des requêtes comme `RETURN 1` ; essayez celle du point 4 |

**Et depuis le terminal ?** Neo4j fournit **`cypher-shell`**, l'équivalent
de `psql`, et Neo4j Desktop peut ouvrir un terminal déjà prêt à l'utiliser.
Pour ce projet, Neo4j Browser suffit.

### Point d'étape : les deux bases de données sont prêtes

À ce stade, les deux bases de données du projet sont **installées,
démarrées et vérifiées** :

| Base de données | Où on la gère | Ce qu'elle contient maintenant | Comment on l'a vérifiée |
|---|---|---|---|
| **PostgreSQL** (relationnelle) | pgAdmin 4 ou `psql` | La base `gharchive`, vide : pas encore de tables | Connexion acceptée, version visible et `SELECT 1;` dans `gharchive` |
| **Neo4j** (graphe) | Neo4j Desktop et Neo4j Browser | L'instance `gharchive`, avec sa base `neo4j` vide : pas encore de nœuds | État *Running*, connexion acceptée, version visible et test d'écriture et de lecture |

Les deux sont **vides exprès**. Les tables (`actor`, `repo`, `actor_repo`)
et les nœuds (`Actor`, `Repo`) seront créés plus tard, depuis des scripts
Python, à partir des mêmes fichiers de données pour les deux côtés. Pour
cela, il faut d'abord préparer l'endroit où ces scripts vont fonctionner :
un petit environnement Python propre au projet.

### Étape 3 : préparer Python (un environnement virtuel pour le projet)

#### 3.1 Le problème que résout un environnement virtuel

Jusqu'ici, les scripts du projet (`download_gharchive.py`, `peek_data.py`,
`summarize_data.py`, `profile_schema.py`) n'utilisaient que la
**bibliothèque standard** de Python : des modules comme `json`, `argparse`
ou `collections`, fournis avec Python. C'est pour cela qu'ils
fonctionnaient sans rien installer.

Désormais, Python doit communiquer avec PostgreSQL et Neo4j, et pour cela
il a besoin de deux **paquets externes**, qui ne sont pas fournis avec
Python et qu'il faut installer : `psycopg` et `neo4j`. La question est
*où* les installer.

Si on les installe « dans le Python de l'ordinateur » (l'installation
générale, partagée par tous les projets), trois problèmes apparaissent :

1. **Des conflits entre projets.** Si un autre projet a besoin d'une
   version différente du même paquet, une seule peut être installée à la
   fois, et l'un des deux projets ne marche plus.
2. **On ne sait plus ce dont le projet a besoin.** Avec le temps,
   l'installation générale accumule des paquets de nombreux projets, et on
   ne sait plus lesquels sont nécessaires à celui-ci.
3. **Ce n'est pas reproductible.** Pour refaire l'expérience sur un autre
   ordinateur, il faut savoir exactement quels paquets et quelles versions
   ont été utilisés. Dans un benchmark, cela fait partie des conditions de
   l'expérience, tout comme les versions des bases de données.

Un **environnement virtuel** résout les trois : c'est un **Python isolé
rien que pour ce projet**, avec ses propres paquets.

#### 3.2 Ce qu'est, concrètement, un environnement virtuel

C'est simplement un **dossier** dans le projet, que nous appellerons
`.venv`. Il contient :

```
.venv/
├── Scripts/
│   ├── python.exe        ← un Python qui n'utilise que les paquets de .venv
│   ├── pip.exe           ← l'installateur de paquets de cet environnement
│   └── activate          ← le script qui « active » l'environnement dans Git Bash
└── Lib/
    └── site-packages/    ← là où sont rangés les paquets installés
```

Une analogie : le Python général de l'ordinateur est la **cuisine commune**
d'une colocation, où chacun laisse ses affaires et où tout finit par se
mélanger. L'environnement virtuel est **une boîte à votre nom** dans cette
cuisine : ce que vous y mettez n'est qu'à vous, vous savez exactement ce
qu'il y a dedans, et si un jour vous voulez repartir de zéro, vous jetez la
boîte et en faites une autre.

Quelques détails importants :

- **Il ne contient pas une copie complète de Python.** Il utilise le
  Python 3.14 déjà installé, mais avec son propre dossier de paquets.
- **Il ne contient pas votre code.** Les scripts restent dans `scripts/`,
  comme toujours ; l'environnement fournit seulement le Python et les
  paquets avec lesquels ils s'exécutent.
- **Il n'est pas envoyé sur GitHub.** Le dossier `.venv` est déjà dans le
  `.gitignore`. Ce qui est envoyé, c'est la *liste* des paquets
  (`requirements.txt`, au point 3.6), pour que n'importe qui puisse
  recréer l'environnement.
- **On peut le supprimer sans crainte.** Si quelque chose ne va pas, on
  supprime le dossier `.venv` et on le recrée en une minute.

#### 3.3 Créer l'environnement (une seule fois)

```bash
cd /c/dev/Research
python -m venv .venv
```

- `cd /c/dev/Research` vous place dans le dossier du projet.
  L'environnement est créé dans le dossier où vous vous trouvez.
- `python -m venv .venv` signifie : « Python, exécute ton module `venv` et
  crée un environnement virtuel dans un dossier appelé `.venv` ». Le point
  au début du nom est une convention : sur beaucoup de systèmes, les
  dossiers qui commencent par un point sont considérés comme des dossiers
  « de configuration ».

Cela prend quelques secondes et n'affiche rien si tout va bien. Vous pouvez
vérifier qu'il a été créé avec `ls -a`, qui devrait lister `.venv` parmi
les dossiers.

**Cela ne se fait qu'une fois.** L'environnement reste enregistré dans le
dossier et sert pour toujours (ou jusqu'à ce que vous le supprimiez).

#### 3.4 Activer l'environnement (à chaque fois que vous ouvrez un terminal)

```bash
source .venv/Scripts/activate
```

**Ce que fait « activer » :** cela change, dans ce terminal seulement, le
Python désigné par le mot `python`. Avant l'activation, `python` est le
Python général de l'ordinateur ; après, c'est celui de `.venv`. Même chose
pour `pip`. Ainsi, tout ce que vous installez ou exécutez va dans
l'environnement du projet.

**Comment savoir qu'il est actif :**

- La ligne de Git Bash commence par `(.venv)` :

  ```
  (.venv) NB30006@LT301102 MINGW64 /c/dev/Research (main)
  ```

- Et cette commande affiche le chemin du Python utilisé, qui doit se
  trouver dans `.venv` :

  ```bash
  which python
  # → /c/dev/Research/.venv/Scripts/python
  ```

**L'activation ne dure que le temps du terminal.** Si vous fermez Git Bash
et en ouvrez un autre, l'environnement n'est plus actif et il faut relancer
`source .venv/Scripts/activate`. L'environnement existe toujours (le
dossier n'est pas supprimé) ; il faut juste « y rentrer » à nouveau.

**Désactiver :** pour revenir au Python général sans fermer le terminal,
tapez `deactivate`.

**Si vous utilisez un autre terminal** (la commande dépend du type) :

| Terminal | Commande pour activer |
|---|---|
| Git Bash | `source .venv/Scripts/activate` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Invite de commandes (CMD) | `.venv\Scripts\activate.bat` |

Dans PowerShell, Windows peut bloquer l'activation à cause de sa politique
d'exécution des scripts, et sur un ordinateur d'entreprise vous n'aurez
peut-être pas le droit de la modifier. Cela n'arrive pas avec Git Bash,
qui est donc l'option recommandée.

#### 3.5 Faire utiliser l'environnement par VS Code

VS Code doit aussi savoir quel Python utiliser, pour que son terminal et sa
détection d'erreurs travaillent avec les paquets de l'environnement :

1. Ouvrez le dossier `c:\dev\Research` dans VS Code.
2. Appuyez sur **Ctrl + Maj + P**, tapez **Python: Select Interpreter** et
   choisissez-le.
3. Dans la liste, choisissez celui dont le chemin est
   `.\.venv\Scripts\python.exe` (il est en général marqué *Recommended*).

À partir de là, les nouveaux terminaux ouverts dans VS Code activent en
général l'environnement tout seuls : vous verrez `(.venv)` au début de la
ligne. S'il n'apparaît pas, activez-le à la main avec la commande du
point 3.4.

#### 3.6 Installer les paquets du projet

Avec l'environnement **actif** (vérifiez le `(.venv)`) :

```bash
python -m pip install "psycopg[binary]" neo4j
```

Ce que signifie chaque partie :

- `python -m pip` utilise le `pip` du Python actif, c'est-à-dire celui de
  l'environnement. C'est plus sûr que de taper seulement `pip`, car cela
  garantit que les paquets vont dans le même Python que celui qui
  exécutera les scripts.
- `install` télécharge les paquets depuis **PyPI** (le dépôt public de
  paquets Python) et les range dans `.venv/Lib/site-packages`.
- `psycopg` est le connecteur pour **PostgreSQL**. Le `[binary]` est un
  *extra* : il demande la version qui inclut déjà les éléments compilés
  nécessaires, pour ne rien avoir à installer d'autre sous Windows. Il est
  entre guillemets car Git Bash pourrait sinon interpréter les crochets.
- `neo4j` est le connecteur officiel pour **Neo4j**.

`pip` installe aussi automatiquement les **dépendances** de ces paquets
(d'autres paquets dont ils ont besoin) ; vous verrez donc plus de noms dans
la sortie que ceux que vous avez demandés. C'est normal.

**Noter les dépendances.** À la racine du projet se trouve un fichier
`requirements.txt` avec les deux paquets et **leur version exacte** :

```
psycopg[binary]==3.3.6
neo4j==6.4.1
```

(Les lignes qui commencent par `#` dans le vrai fichier sont des
commentaires, et `pip` les ignore.)

C'est la « liste de courses » du projet : elle indique les paquets dont il
a besoin. Ce fichier, lui, **est** envoyé sur GitHub. Sur un autre
ordinateur (ou si un jour vous recréez l'environnement), il suffit de :

```bash
python -m pip install -r requirements.txt
```

Les dépendances de ces deux paquets (`psycopg-binary`, `tzdata` et `pytz`)
n'ont pas besoin d'être écrites : `pip` les installe tout seul.

**Pourquoi `==` : dans un benchmark, les conditions doivent toujours être
les mêmes.** `==` signifie « exactement cette version ». Sans lui, `pip`
installe la version **la plus récente** disponible au moment de
l'installation ; le même `requirements.txt` donnerait donc des versions
différentes aujourd'hui et dans six mois.

Dans un projet ordinaire, cela n'a souvent pas d'importance. Dans
celui-ci, si, car le but est de **comparer deux outils**, et une
comparaison n'est équitable que si la seule chose qui change est ce qu'on
mesure (voir « Ce que signifie *benchmark* pour ce projet »). Les
connecteurs font partie du chemin que parcourt chaque requête :
Python → connecteur → base de données → connecteur → Python. Si une
nouvelle version d'un connecteur est plus rapide ou plus lente, les temps
changent, et ce n'est dû ni à PostgreSQL ni à Neo4j. Fixer les versions
évite trois problèmes :

1. **Des comparaisons faussées.** Si on met à jour le connecteur de Neo4j
   en cours de projet mais pas celui de PostgreSQL, les mesures suivantes
   ne comparent plus la même chose que les précédentes.
2. **Des résultats impossibles à refaire.** Quiconque veut vérifier les
   résultats, ou vous-même dans quelques mois, doit reconstruire
   exactement le même environnement. Avec `==`, `pip install -r
   requirements.txt` y parvient toujours.
3. **Des changements qui passent inaperçus.** Si un temps change d'une
   mesure à l'autre, il faut pouvoir écarter une mise à jour comme cause.
   Avec des versions fixées, on sait que ce n'en est pas une.

Pour la même raison, il faut noter **toutes** les versions en jeu, pas
seulement celles de Python : celle de PostgreSQL, celle de Neo4j, celle de
Python (3.14) et celles des connecteurs. Cette commande affiche les
versions exactes de tous les paquets de l'environnement, dépendances
comprises :

```bash
python -m pip freeze
```

Si un jour on décide de mettre à jour un connecteur, on change sa version
dans `requirements.txt`, on note le changement, et **on refait toutes les
mesures** avec la nouvelle version, pour que tous les résultats aient été
obtenus dans les mêmes conditions.

#### 3.7 Vérifier que l'environnement est correct

```bash
python -m pip list
```

devrait afficher `psycopg`, `psycopg-binary` et `neo4j` (entre autres). Et
cette commande confirme que Python peut les **importer** et affiche leurs
versions :

```bash
python -c "import psycopg, neo4j; print('psycopg', psycopg.__version__); print('neo4j', neo4j.__version__)"
```

Si les deux versions s'affichent, l'environnement est prêt.

#### 3.8 Si quelque chose ne va pas

| Problème | Cause probable | Solution |
|---|---|---|
| `bash: .venv/Scripts/activate: No such file or directory` | Vous n'êtes pas dans le dossier du projet, ou l'environnement n'a pas été créé | Lancez `cd /c/dev/Research` et vérifiez avec `ls -a` que `.venv` existe ; sinon, créez-le (point 3.3) |
| `ModuleNotFoundError: No module named 'psycopg'` (ou `'neo4j'`) | L'environnement n'est pas actif, ou les paquets ont été installés dans un autre Python | Activez l'environnement (point 3.4), vérifiez avec `which python`, et réinstallez (point 3.6) |
| Pas de `(.venv)` dans VS Code | VS Code n'utilise pas l'environnement | Choisissez l'interpréteur de `.venv` (point 3.5) et ouvrez un nouveau terminal |
| PowerShell refuse d'activer l'environnement | La politique d'exécution des scripts de Windows | Utilisez Git Bash (point 3.4) |
| L'environnement est abîmé | Des paquets en mauvais état ou mélangés | Désactivez-le (`deactivate`), supprimez le dossier (`rm -rf .venv`) et recommencez au point 3.3 |

#### 3.9 Résumé : la routine de chaque jour

**Une seule fois** (déjà fait si vous avez suivi les points précédents) :

```bash
cd /c/dev/Research
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

**Chaque fois que vous ouvrez un terminal pour travailler sur le projet :**

```bash
cd /c/dev/Research
source .venv/Scripts/activate
```

Et vérifiez que la ligne commence par `(.venv)` avant de lancer un script.
Les anciens scripts, qui n'utilisent que la bibliothèque standard,
fonctionnent de la même façon dans l'environnement ; vous pouvez donc
toujours travailler avec lui actif.

### Étape 4 : transmettre les mots de passe à Python sans les écrire dans le code

Les mots de passe vont dans des **variables d'environnement** : des valeurs
qui vivent dans le terminal tant qu'il est ouvert, en dehors de tout
fichier. Dans Git Bash :

```bash
export PGPASSWORD='le-mot-de-passe-postgres'
export NEO4J_PASSWORD='le-mot-de-passe-neo4j'
```

- `PGPASSWORD` est un nom standard : PostgreSQL (et `psycopg`) le lisent
  automatiquement, donc le code n'a même pas besoin de le mentionner.
- `NEO4J_PASSWORD`, c'est nous qui le lirons depuis Python avec
  `os.environ["NEO4J_PASSWORD"]`.
- Ces variables disparaissent à la fermeture du terminal. Il faut les
  définir à nouveau à chaque fois, comme on active l'environnement virtuel.

### Étape 5 : vérifier que Python atteint les deux bases de données

Avec l'environnement virtuel actif, les deux bases démarrées et les
variables d'environnement définies, ce code devrait afficher la version de
PostgreSQL et un `1` venant de Neo4j :

```python
import os

import psycopg
from neo4j import GraphDatabase

# PostgreSQL : le mot de passe est lu automatiquement dans PGPASSWORD
with psycopg.connect(host="localhost", dbname="gharchive", user="postgres") as conn:
    print(conn.execute("SELECT version();").fetchone()[0])

# Neo4j : le mot de passe est lu dans NEO4J_PASSWORD
driver = GraphDatabase.driver("neo4j://localhost:7687",
                              auth=("neo4j", os.environ["NEO4J_PASSWORD"]))
with driver.session() as session:
    print(session.run("RETURN 1 AS ok").single()["ok"])
driver.close()
```

Ce code peut être enregistré sous `scripts/check_connections.py` et lancé
avec `python scripts/check_connections.py`.

### Liste de vérification

| Vérification | Comment | Résultat attendu |
|---|---|---|
| PostgreSQL installé | `psql -U postgres -c "SELECT version();"`, ou `SELECT version();` dans le Query Tool de pgAdmin | La version de PostgreSQL |
| Base `gharchive` créée | `psql -U postgres -d gharchive -c "SELECT 1;"`, ou `SELECT 1;` dans le Query Tool de pgAdmin avec `gharchive` sélectionnée | Un tableau avec un `1` |
| Neo4j en marche | `RETURN 1;` dans Neo4j Browser | `1` |
| Environnement virtuel actif | La ligne de Git Bash commence par `(.venv)` | — |
| Connecteurs installés | `python -m pip show psycopg neo4j` | Les informations des deux paquets |
| Python atteint les deux | `python scripts/check_connections.py` | La version de PostgreSQL et un `1` |

**Notez les versions installées** (de PostgreSQL, de Neo4j et des deux
paquets Python). Elles font partie des conditions du benchmark : pour que
quelqu'un puisse refaire l'expérience, il doit savoir avec quelles
versions elle a été faite.
