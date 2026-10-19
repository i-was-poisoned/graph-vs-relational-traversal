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

Chaque nouvel appel **naît de la boucle d'un appel précédent**. Quand la
fonction reçoit un dictionnaire, sa boucle est :

```python
for key, sub_value in value.items():
    refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
```

`value.items()` donne une paire *(clé, valeur)* à chaque tour, et chaque
tour lance **un appel**. Par exemple, dans l'appel 1 (`path = "payload"`,
`depth = 3`), le premier tour donne `key = "action"` et
`sub_value = "opened"`, et en remplaçant :

| Argument | Calcul | Résultat |
|---|---|---|
| `sub_value` | la valeur de la clé `"action"` | `"opened"` |
| `f"{path}.{key}"` | `"payload"` + `"."` + `"action"` | `"payload.action"` |
| `depth - 1` | `3 - 1` | `2` |

C'est ainsi que naît l'**appel 2** :
`find_actor_refs("opened", "payload.action", 2)`.

**Règle générale :**

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

Le pipeline global jusqu'à présent est : **download_gharchive.py →
peek_data.py → summarize_data.py → profile_schema.py** — d'abord récupérer
et décompresser l'heure fixe du jeu de données, puis inspecter une poignée
d'événements bruts, puis obtenir une lecture agrégée du volume et de la
connectivité, puis profiler la forme du payload et localiser les
références à un second acteur, avant de passer à l'extraction et au
chargement effectifs des enregistrements dans les modèles relationnel et
graphe comparés.
