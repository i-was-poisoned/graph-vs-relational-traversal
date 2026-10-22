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

#### 4.1 L'idée : les variables d'environnement

Les mots de passe ne sont pas écrits dans le code Python. Ils sont gardés
dans des **variables d'environnement** : des valeurs qui vivent dans le
terminal tant qu'il est ouvert, en dehors du code. Le projet en utilise
deux :

| Variable | Mot de passe de | Qui la lit |
|---|---|---|
| `PGPASSWORD` | l'utilisateur `postgres` de PostgreSQL | PostgreSQL et `psycopg`, **automatiquement** : c'est un nom standard, donc le code ne la mentionne même pas |
| `NEO4J_PASSWORD` | l'utilisateur `neo4j` de Neo4j | Nos scripts, avec `os.environ["NEO4J_PASSWORD"]` |

On pourrait les définir à la main avec `export` à chaque ouverture de
terminal, mais c'est fastidieux et facile à oublier. À la place, on les
garde dans un petit script bash qu'on charge en une seule commande.

#### 4.2 Pourquoi cela marche : les variables sont héritées

Quand un programme en lance un autre, le nouveau **reçoit une copie des
variables d'environnement** de celui qui l'a lancé. Si le terminal a
`NEO4J_PASSWORD` définie, tout script Python lancé depuis ce terminal en
hérite et peut la lire.

Mais il faut charger le script de la bonne façon :

| Commande | Ce qui se passe |
|---|---|
| `source secrets.sh` | Le script s'exécute **dans votre terminal**. Les variables y restent définies, et tout ce que vous lancez ensuite en hérite, jusqu'à la fermeture du terminal. **C'est la bonne façon.** |
| `bash secrets.sh` | Le script s'exécute dans **un autre bash, à part**, qui définit les variables et se termine aussitôt. Votre terminal ne les voit pas, et Python non plus. |

#### 4.3 Les deux fichiers

| Fichier | Ce qu'il contient | Envoyé sur GitHub ? |
|---|---|---|
| `secrets.example.sh` | Un **modèle** avec les deux variables et des valeurs d'exemple, sans vrais mots de passe | **Oui** : pour savoir quelles variables sont nécessaires |
| `secrets.sh` | Les **vrais mots de passe** | **Jamais** : il est dans le `.gitignore` |

#### 4.4 Créer votre `secrets.sh` (une seule fois)

1. Copiez le modèle :

   ```bash
   cp secrets.example.sh secrets.sh
   ```

   > ⚠️ **Ne modifiez pas et ne renommez pas `secrets.example.sh`.** C'est
   > le modèle, et il est envoyé sur GitHub exprès, sans mots de passe, pour
   > qu'on sache quelles variables sont nécessaires. Les vrais mots de passe
   > vont **uniquement dans la copie**, `secrets.sh`. Le `.gitignore` bloque
   > exactement ce nom (`/secrets.sh`), pas tout ce qui commence par
   > `secrets` : c'est pourquoi le modèle est envoyé et la copie ne l'est
   > pas.

2. Ouvrez `secrets.sh` dans VS Code et remplacez les deux valeurs
   d'exemple par vos vrais mots de passe, en gardant les guillemets
   simples :

   ```bash
   export PGPASSWORD='...'
   export NEO4J_PASSWORD='...'
   ```

3. Vérifiez que git l'ignore :

   ```bash
   git check-ignore -v secrets.sh
   ```

   Il devrait répondre avec la ligne du `.gitignore` qui l'ignore
   (`/secrets.sh`). Et `git status` ne devrait **pas** afficher
   `secrets.sh` comme nouveau fichier.

#### 4.5 Précautions avec les mots de passe

- **Tapez-les directement dans `secrets.sh`.** Ne les collez pas dans des
  chats, des e-mails, des notes ni dans aucun autre fichier du projet. Un
  mot de passe qui a été écrit ailleurs ne doit plus être considéré comme
  secret : si cela arrive, changez-le.
- **Utilisez un mot de passe différent pour chaque base de données**, long
  et difficile à deviner, et gardez-les dans un gestionnaire de mots de
  passe.
- **Si `secrets.sh` était un jour envoyé sur GitHub,** il resterait dans
  l'historique git même après suppression. Dans ce cas, changez les deux
  mots de passe.
- **Pour les changer :** dans PostgreSQL, depuis pgAdmin
  (**Login/Group Roles** → **postgres** → **Properties** → **Definition**) ;
  dans Neo4j, depuis Neo4j Browser, avec `:use system` puis
  `ALTER CURRENT USER SET PASSWORD FROM '...' TO '...';`. Mettez ensuite
  `secrets.sh` à jour.

#### 4.6 La routine complète de chaque jour

Chaque fois que vous ouvrez un terminal pour travailler sur le projet :

```bash
cd /c/dev/Research
source .venv/Scripts/activate     # le Python du projet
source secrets.sh                 # les mots de passe
```

Pour vérifier que les mots de passe sont chargés **sans les afficher à
l'écran** :

```bash
[ -n "$PGPASSWORD" ] && echo "PGPASSWORD chargée"
[ -n "$NEO4J_PASSWORD" ] && echo "NEO4J_PASSWORD chargée"
```

(`-n` vérifie que la variable n'est pas vide ; ainsi, sa valeur n'est
jamais écrite dans le terminal.)

#### 4.7 Un raccourci : `run.sh`, qui prépare tout et lance Python

La routine du point 4.6 fonctionne, mais ce sont trois commandes à chaque
fois, et si on en oublie une (activer `.venv` ou charger `secrets.sh`), le
script Python échoue avec une erreur peu claire. C'est pourquoi le projet a
un petit script bash, **`run.sh`**, à la racine, qui fait tout d'un coup :

```bash
./run.sh scripts/check_connections.py
```

À l'intérieur, `run.sh` fait ceci, dans l'ordre :

1. **Il se place dans le dossier du projet**, d'où que vous l'appeliez.
2. **Il vérifie que tout est en place** et, sinon, s'arrête avec un
   message clair :
   - si vous n'avez pas indiqué quel script lancer, il montre comment
     l'utiliser ;
   - si `.venv` n'existe pas, il indique comment le créer (étape 3) ;
   - si `secrets.sh` n'existe pas, il indique comment le créer
     (point 4.4) ;
   - si `secrets.sh` contient encore les mots de passe d'exemple du
     modèle, il prévient qu'il faut les remplacer.
3. **Il active l'environnement virtuel** (`source .venv/Scripts/activate`).
4. **Il charge les mots de passe** (`source secrets.sh`).
5. **Il lance Python** avec le script que vous lui avez passé et ses
   options éventuelles. Python **hérite** des mots de passe de `run.sh`
   (point 4.2).

**Pourquoi c'est mieux que de charger les mots de passe dans votre
terminal :**

| | Routine du point 4.6 | `./run.sh` |
|---|---|---|
| Commandes à chaque fois | 3 | 1 |
| Si on oublie quelque chose | Python échoue avec une erreur confuse | `run.sh` s'arrête et explique ce qui manque |
| Où vivent les mots de passe | Dans votre terminal, jusqu'à sa fermeture | Seulement pendant l'exécution du script ; ils disparaissent à la fin |

**Comment les mots de passe arrivent à Python sans passer par votre
terminal.** Ce dernier point, c'est l'idée de départ : les mots de passe
restent **en dehors du code Python**, dans un script bash, et Python en
**hérite** parce qu'il est lancé depuis ce script. Pour bien le comprendre,
il faut voir quels programmes démarrent, et dans quel ordre, quand vous
tapez `./run.sh scripts/check_connections.py` :

```
Votre terminal (Git Bash)               ← n'a jamais les mots de passe, ni avant ni après
 └── lance run.sh  → un NOUVEAU bash, enfant de votre terminal
       ├── source .venv/Scripts/activate  → active l'environnement DANS ce bash enfant
       ├── source secrets.sh              → charge les mots de passe DANS ce bash enfant
       └── exec python scripts/check_connections.py
             └── Python prend la place du bash enfant et HÉRITE de ses variables :
                 l'environnement activé et les deux mots de passe
                       ↓
             Python se termine → le processus disparaît, et les mots de passe avec lui
```

Pas à pas :

1. **Votre terminal lance `run.sh` comme un nouveau programme**, un bash
   *enfant*. L'enfant reçoit une copie des variables de votre terminal
   (point 4.2), mais votre terminal ne reçoit jamais rien en retour :
   l'héritage va seulement du parent vers l'enfant, jamais dans l'autre
   sens.
2. **Dans l'enfant, `run.sh` utilise bien `source`**, deux fois : pour
   activer `.venv` et pour charger `secrets.sh`. Avec `source`, ces scripts
   s'exécutent *dans* le bash enfant ; les mots de passe y restent donc
   définis (et pas dans un bash à part qui se ferme aussitôt).
3. **À la fin, `run.sh` lance Python avec `exec`.** `exec` fait que Python
   **prend la place** du bash enfant, au lieu de créer un processus de
   plus. Python hérite de tout ce que l'enfant avait défini :
   l'environnement virtuel activé et les deux mots de passe. C'est pour
   cela que `psycopg` trouve `PGPASSWORD` et que le script trouve
   `NEO4J_PASSWORD`.
4. **Quand Python se termine, son processus disparaît**, et les mots de
   passe avec lui. Votre terminal est exactement comme avant : si vous
   tapez `echo "$NEO4J_PASSWORD"`, rien ne s'affiche.

**Pourquoi il n'est pas nécessaire de taper `source run.sh` ici.** Au
point 4.2, on a vu que `bash secrets.sh` ne fonctionne pas : le bash à part
charge les mots de passe et se ferme **sans rien lancer**, donc personne ne
peut s'en servir. Avec `run.sh`, c'est exactement l'inverse : le bash à
part charge les mots de passe **puis lance Python depuis l'intérieur** ;
Python en hérite donc avant que ce bash ne se termine. Le `source` est
toujours là, mais *dans* `run.sh`, pas dans votre terminal.

**Pourquoi c'est l'option la plus sûre parmi celles vues :** les mots de
passe n'existent en mémoire **que pendant l'exécution du script**, et
seulement dans ce processus. Aucune autre commande lancée dans votre
terminal ne peut les voir, et ils ne restent pas chargés une fois le
travail terminé.

**Il sert pour n'importe quel script du projet,** actuel ou futur. Ce que
vous écrivez après le nom du script lui est transmis tel quel :

```bash
./run.sh scripts/check_connections.py
./run.sh scripts/summarize_data.py --top 10
```

(Les anciens scripts n'ont pas besoin des mots de passe, mais ils
fonctionnent de la même façon via `run.sh`.)

**Si `./run.sh` ne fonctionne pas :** dans Git Bash, un fichier qui
commence par `#!/usr/bin/env bash` peut être lancé directement. S'il
affiche quand même *Permission denied*, utilisez
`bash run.sh scripts/check_connections.py`, qui fait exactement la même
chose.

#### 4.8 Et pourquoi ne pas garder les mots de passe dans `.venv` ?

L'idée paraît logique : si le projet a déjà son propre environnement
virtuel, pourquoi ne pas y mettre aussi les mots de passe ? Par exemple, en
ajoutant les deux lignes `export` à la fin de `.venv/Scripts/activate`,
pour qu'ils soient chargés à l'activation de l'environnement. Cela
fonctionnerait, mais c'est moins bien que ce que nous avons, pour deux
raisons.

**1. Un environnement virtuel isole des paquets, pas des secrets.**
`.venv` sert à donner au projet ses propres versions de `psycopg` et
`neo4j`. Il ne protège rien : c'est un dossier de fichiers ordinaires sur
votre disque, lisible par n'importe quel programme lancé avec votre
utilisateur Windows, exactement comme `secrets.sh`. Y déplacer les mots de
passe ne les rend pas plus sûrs ; cela change seulement le fichier où ils
se trouvent.

**2. Cela a des inconvénients pratiques :**

| | Mots de passe dans `.venv/Scripts/activate` | Ce que nous utilisons (`secrets.sh` + `run.sh`) |
|---|---|---|
| Hors de GitHub ? | Oui (`.venv` est dans le `.gitignore`) | Oui (`secrets.sh` est dans le `.gitignore`) |
| Survivent-ils si on recrée l'environnement ? | **Non.** L'environnement est jetable (point 3.8 : « supprimez `.venv` et recréez-le »), et les mots de passe partiraient avec lui | **Oui.** `secrets.sh` ne dépend pas de l'environnement |
| Combien de temps sont-ils chargés ? | Tant que l'environnement est actif dans le terminal, à la portée de **n'importe quelle** commande lancée dedans | **Seulement pendant l'exécution d'un script :** `run.sh` les charge, Python en hérite, et ils disparaissent à la fin |
| Faciles à trouver et à comprendre ? | Non : cachés dans un fichier généré que personne ne touche d'habitude | Oui : un fichier évident, avec un modèle qui le documente |

Les deux dernières lignes sont les plus importantes. `run.sh` offre déjà
l'**exposition minimale** : les mots de passe n'existent que pendant
l'exécution d'un script.

**Règle :** chaque outil pour son rôle. `.venv` pour les paquets ;
`secrets.sh` + `run.sh` pour les mots de passe.

**Et dans les vrais projets ?** Dans les projets professionnels, ou avec
des données sensibles, on va en général plus loin avec un **gestionnaire
de secrets** (*secret manager*) : un service qui garde les mots de passe
**chiffrés** et ne les remet qu'au programme autorisé, sans qu'ils se
trouvent dans un fichier lisible. Windows en a un intégré, le
**Gestionnaire d'identification**, auquel Python peut accéder avec le
paquet `keyring` ; les fournisseurs cloud proposent les leurs. Ce n'est pas
nécessaire ici : c'est un projet personnel, avec des données publiques, et
les deux bases n'acceptent que des connexions venant de votre propre
ordinateur. Mais c'est l'option à envisager si le projet devait un jour
manipuler quelque chose de sensible.

### Étape 5 : vérifier que Python atteint les deux bases de données

Le projet a un script pour cela : **`scripts/check_connections.py`** (avec
son explication ligne par ligne dans [check_connections.py](check_connections.py),
la copie annotée). Il se connecte à PostgreSQL et à Neo4j avec les mots de
passe des variables d'environnement et affiche la version de chaque
serveur.

**Comment le lancer**, avec les deux bases démarrées et votre `secrets.sh`
déjà rempli :

```bash
./run.sh scripts/check_connections.py
```

**Si tout va bien**, vous verrez quelque chose comme ceci (c'est la
sortie réelle de ce projet) :

```
PostgreSQL OK: PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit
Neo4j OK: Neo4j Kernel 2026.10.0 (enterprise edition)
Neo4j OK: Cypher 5 ( edition)
Both databases are reachable.
```

Neo4j affiche **deux lignes** car, dans ses versions récentes, la requête
de version renvoie deux composants : le moteur de la base de données
(*Neo4j Kernel*) et la version du langage de requêtes (*Cypher 5*). Ce
second n'a pas d'édition, d'où les parenthèses vides. Ce n'est pas une
erreur.

**Comment fonctionne le script, en bref :**

1. Il vérifie que `PGPASSWORD` et `NEO4J_PASSWORD` existent. S'il en
   manque une, il s'arrête et indique qu'il faut le lancer via `run.sh`.
2. **PostgreSQL :** il se connecte à la base `gharchive` en tant que
   `postgres` et exécute `SELECT version();`. `psycopg` lit le mot de passe
   tout seul dans `PGPASSWORD`.
3. **Neo4j :** il lit `NEO4J_PASSWORD`, se connecte à
   `neo4j://localhost:7687` en tant que `neo4j`, et exécute la même requête
   de version que dans Neo4j Browser (`CALL dbms.components() ...`).
4. Il fait **les deux vérifications même si l'une échoue** (avec
   `try`/`except`), pour qu'une erreur dans l'une ne cache pas le résultat
   de l'autre.

**Si quelque chose ne va pas**, le script indique laquelle et pourquoi :

| Message | Cause probable | Solution |
|---|---|---|
| `Missing environment variable(s): ...` | Il a été lancé directement avec `python`, sans `run.sh` | Lancez-le avec `./run.sh scripts/check_connections.py` |
| `PostgreSQL FAILED: ... password authentication failed` | Le mot de passe de `secrets.sh` n'est pas celui de `postgres` | Corrigez `PGPASSWORD` dans `secrets.sh` |
| `PostgreSQL FAILED: ... Connection refused` | Le service PostgreSQL est arrêté | Démarrez-le depuis les *Services* de Windows (voir la partie sur pgAdmin) |
| `PostgreSQL FAILED: ... database "gharchive" does not exist` | La base du projet n'a pas été créée | Créez-la (étape 1, point 5, ou depuis pgAdmin) |
| `Neo4j FAILED: ... Unauthorized` | Le mot de passe de `secrets.sh` n'est pas celui de `neo4j` | Corrigez `NEO4J_PASSWORD` dans `secrets.sh` |
| `Neo4j FAILED: ... Couldn't connect` / `Unable to retrieve routing information` | L'instance Neo4j n'est pas démarrée | Démarrez-la dans Neo4j Desktop (*Start*) |
| `ModuleNotFoundError: No module named 'psycopg'` | L'environnement virtuel ou ses paquets manquent | Revoyez l'étape 3 (`run.sh` active déjà `.venv`) |

Quand `Both databases are reachable.` apparaît, **toute la chaîne
fonctionne** : l'environnement virtuel, les mots de passe, les connecteurs
et les deux bases de données. C'est le point de départ pour créer les
tables et les nœuds.

### Comment Python sait où se trouve chaque base de données

Quand `check_connections.py` fonctionne, une question naturelle se pose :
comment Python sait-il où se trouve chaque base ? Les cherche-t-il tout
seul sur l'ordinateur ? Comment distingue-t-il PostgreSQL de Neo4j ?

**La réponse courte : il ne cherche rien. C'est nous qui le lui disons**,
avec une adresse exacte pour chacune, écrite en haut du script :

```python
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
```

#### Les trois parties d'une adresse

Pour se connecter à une base de données, il faut trois choses, comme pour
trouver une boutique dans un centre commercial :

| Partie | Dans le centre commercial | Pour la base de données | PostgreSQL | Neo4j |
|---|---|---|---|---|
| **Machine** (*host*) | Le bâtiment | L'ordinateur où tourne le serveur | `localhost` | `localhost` |
| **Port** | Le numéro de la boutique | La « porte » sur laquelle écoute ce serveur | `5432` | `7687` |
| **Protocole** | La langue parlée à l'intérieur | La « langue » dans laquelle client et serveur communiquent | Celle de PostgreSQL | *Bolt* (celle de Neo4j) |

**1. La machine : `localhost`.** C'est un nom spécial qui signifie
toujours **« ce même ordinateur »** (son adresse numérique est
`127.0.0.1`, celle qui apparaît dans Neo4j Desktop comme *Connection URI*).
C'est pourquoi la connexion ne sort jamais sur internet : Python et les
deux bases de données sont sur votre ordinateur portable.

**2. Le port : le numéro de la porte.** Un ordinateur peut avoir de
nombreux programmes qui attendent des connexions en même temps ; chacun
« écoute » sur un numéro de port différent, pour ne pas se mélanger. À
l'installation, chaque serveur a pris le sien :

- **PostgreSQL** écoute sur le **5432** (celui accepté dans
  l'installateur).
- **Neo4j** écoute sur le **7687** pour les programmes (protocole *Bolt*)
  et sur le **7474** pour le navigateur (Neo4j Browser).

Les réglages de PostgreSQL ne mentionnent pas le `5432` : quand aucun port
n'est indiqué, `psycopg` utilise celui-là par défaut. Celui de Neo4j, lui,
apparaît dans l'adresse `neo4j://localhost:7687`.

**3. Le protocole : chaque connecteur ne parle qu'une langue.** Voici la
réponse à « comment sait-il si c'est PostgreSQL ou Neo4j ? » : **c'est le
connecteur utilisé qui en décide**.

- `psycopg.connect(...)` ne parle que la langue de PostgreSQL ; il ne peut
  donc se connecter qu'à un serveur PostgreSQL.
- `GraphDatabase.driver(...)` ne parle que *Bolt*, la langue de Neo4j. Le
  `neo4j://` au début de l'adresse l'indique.

Si on dirigeait `psycopg` par erreur vers le port de Neo4j, il ne
« trouverait » pas autre chose : la connexion échouerait, car le serveur
en face ne comprend pas la langue.

#### Ce qui doit fonctionner sur votre ordinateur

Pour que la connexion marche, **le serveur doit être démarré et écouter
sur son port** :

| Serveur | Ce qui le maintient en marche | S'il n'est pas démarré |
|---|---|---|
| PostgreSQL | Un **service Windows**, qui démarre tout seul à l'allumage de l'ordinateur | `Connection refused` (personne ne répond sur le 5432) |
| Neo4j | L'instance `gharchive`, démarrée dans **Neo4j Desktop** | `Couldn't connect` (personne ne répond sur le 7687) |

#### Le reste des informations de connexion

Une fois dans le serveur, il manque deux informations :

- **Avec quel utilisateur** on entre : `postgres` dans PostgreSQL et
  `neo4j` dans Neo4j. Le mot de passe de chacun arrive par les variables
  d'environnement (étape 4).
- **Quelle base de données** on utilise, car un serveur peut en avoir
  plusieurs :
  - Dans PostgreSQL, c'est `dbname="gharchive"` qui l'indique.
  - Dans Neo4j, le script ne l'indique pas encore ; c'est donc la base par
    défaut de l'instance (`neo4j`) qui est utilisée. Votre instance a aussi
    une base `gharchive` ; quand on aura décidé dans laquelle travailler,
    on l'indiquera dans les scripts qui chargeront les données.

#### Si un jour les bases de données étaient ailleurs

Il suffirait de changer l'adresse : par exemple, mettre le nom d'un autre
ordinateur à la place de `localhost`, ou le port utilisé par ce serveur.
Rien d'autre dans le code ne changerait. C'est pour cela que les adresses
sont regroupées, sous forme de constantes, en haut du script.

La sortie de `check_connections.py` confirme tout cela : la ligne de
PostgreSQL indique `on x86_64-windows` (c'est votre ordinateur Windows), et
celle de Neo4j affiche la version de l'instance démarrée dans Neo4j
Desktop.

### Liste de vérification

| Vérification | Comment | Résultat attendu |
|---|---|---|
| PostgreSQL installé | `psql -U postgres -c "SELECT version();"`, ou `SELECT version();` dans le Query Tool de pgAdmin | La version de PostgreSQL |
| Base `gharchive` créée | `psql -U postgres -d gharchive -c "SELECT 1;"`, ou `SELECT 1;` dans le Query Tool de pgAdmin avec `gharchive` sélectionnée | Un tableau avec un `1` |
| Neo4j en marche | `RETURN 1;` dans Neo4j Browser | `1` |
| Environnement virtuel actif | La ligne de Git Bash commence par `(.venv)` | — |
| Connecteurs installés | `python -m pip show psycopg neo4j` | Les informations des deux paquets |
| Python atteint les deux | `./run.sh scripts/check_connections.py` | `PostgreSQL OK: ...`, `Neo4j OK: ...` et `Both databases are reachable.` |

**Notez les versions installées** (de PostgreSQL, de Neo4j et des deux
paquets Python). Elles font partie des conditions du benchmark : pour que
quelqu'un puisse refaire l'expérience, il doit savoir avec quelles
versions elle a été faite.


## Étape d'extraction (extract_csv.py)

Avec les deux bases de données installées et vérifiées, l'étape suivante
est de les remplir. Avant de charger quoi que ce soit, il faut préparer les
données qu'elles vont recevoir.

### Deux décisions prises avant de commencer

1. **Les deux bases de données s'appellent `gharchive` :** la base
   PostgreSQL et, dans l'instance Neo4j, la base `gharchive` (pas la base
   `neo4j` fournie par défaut). Ainsi, on sait toujours où se trouvent les
   données du projet, des deux côtés.
2. **Une seule connexion par paire acteur–dépôt, sans répétition.** Si ana
   fait 10 push vers le même dépôt, la table des connexions contient **une
   seule ligne** avec l'`id` d'ana et celui du dépôt. Ce qui compte pour
   parcourir le graphe, c'est *si* ana est reliée à ce dépôt, pas *combien
   de fois*. Cette décision s'applique de la même façon des deux côtés
   (voir le principe de conception « la requête d'abord »).

### Pourquoi une étape d'extraction à part : une seule source pour les deux côtés

Le travail se répartit en trois scripts :

| Script | Ce qu'il fait |
|---|---|
| `extract_csv.py` (celui-ci) | Lit le JSON **une seule fois** et écrit trois fichiers CSV |
| `load_postgres.py` (suivant) | Charge ces CSV dans PostgreSQL |
| `load_neo4j.py` (suivant) | Charge **les mêmes** CSV dans Neo4j |

L'extraction est à part parce que c'est elle qui garantit une comparaison
équitable : **les deux bases sont chargées à partir des mêmes fichiers**,
donc aucune ne peut se retrouver avec des données différentes de l'autre.
Si chaque chargement lisait le JSON de son côté, la moindre différence
entre les deux scripts (un autre filtre de bots, un cas particulier traité
autrement) changerait les données d'un seul côté.

### Ce qu'est un fichier CSV

**CSV** (*comma-separated values*, « valeurs séparées par des virgules »)
est un tableau en texte brut : chaque ligne est une ligne du tableau, les
virgules séparent les colonnes, et la première ligne (l'**en-tête**) donne
le nom des colonnes :

```
id,login
19,brynary
452,yrashk
```

C'est le format le plus simple pour faire passer des tableaux d'un
programme à l'autre, et PostgreSQL (avec `COPY`) comme Neo4j (avec
`LOAD CSV`) le chargent directement.

### Les trois fichiers

| Fichier | Colonnes | Une ligne par | Deviendra |
|---|---|---|---|
| `actors.csv` | `id`, `login` | acteur | la table `actor` / les nœuds `:Actor` |
| `repos.csv` | `id`, `name` | dépôt | la table `repo` / les nœuds `:Repo` |
| `actor_repo.csv` | `actor_id`, `repo_id` | paire acteur–dépôt, sans répétition | la table `actor_repo` / les arêtes entre `:Actor` et `:Repo` |

Ils sont enregistrés dans `data/csv/`. Comme tout ce qui se trouve dans
`data/`, ils **ne sont pas envoyés sur GitHub** (`data/` est dans le
`.gitignore`) : on peut les régénérer à tout moment en relançant le script.

### Ce que fait le script

1. **Il lit chaque événement** du fichier JSON, une ligne à la fois.
2. **Il écarte les bots** (logins qui finissent par `[bot]`), avec la même
   règle que `summarize_data.py`.
3. **Il garde chaque acteur et chaque dépôt une seule fois, par son
   `id`**, avec son nom le plus récent (voir plus bas).
4. **Il garde chaque paire `(actor_id, repo_id)` dans un ensemble
   (`set`)**. Un ensemble n'accepte pas de doublons ; la même paire
   ajoutée dix fois n'est donc gardée qu'une fois : c'est ainsi qu'on
   respecte la décision de ne pas répéter les connexions.
5. **Il écrit les trois CSV triés par `id`**, pour que le même JSON
   produise toujours exactement les mêmes fichiers.

### Ce que l'on a trouvé dans les données : pourquoi les `id` et pas les noms

Avant d'écrire le script, on a vérifié si un `id` apparaissait avec plus
d'un nom. Cela arrive dans trois cas, et un même nom apparaît avec deux
`id` :

| Cas | Ce qui se passe | Ce que fait le script |
|---|---|---|
| Acteur `321725054` | A changé de login pendant cette heure : `lucky521-png` → `peitongshi` | Une seule ligne, avec le nom le plus récent : `peitongshi` |
| Dépôt `1348625135` | Renommé en même temps que son propriétaire : `lucky521-png/niulai-chinese` → `peitongshi/niulai-chinese` | Une seule ligne : `peitongshi/niulai-chinese` |
| Dépôt `1348068959` | Renommé : `xuange520/HyperArmor` → `xuange520/HyperArmor-skill` | Une seule ligne : `xuange520/HyperArmor-skill` |
| Login `Copilot` | Deux comptes différents avec le même nom (`175728472` et `198982749`) | Deux lignes, une par `id` |

Si on utilisait les noms comme clés, le premier cas compterait pour deux
personnes, chaque dépôt renommé pour deux dépôts, et les deux comptes
`Copilot` seraient fusionnés en un seul. Avec les `id`, les quatre cas sont
traités correctement. Pour la même raison, **le `login` ne peut pas être
unique** dans la table `actor` : deux lignes peuvent le partager.

### Comment le lancer

```bash
./run.sh scripts/extract_csv.py
```

(Ce script n'utilise ni les bases de données ni les mots de passe ;
`python scripts/extract_csv.py` avec l'environnement virtuel actif
fonctionne donc aussi. Passer par `run.sh` est le plus simple : toujours
pareil.)

Résultat pour l'heure fixe du projet :

```
Skipped 1970 bot events. Writing to C:\dev\Research\data\csv:
  actors.csv         14515 rows
  repos.csv          14995 rows
  actor_repo.csv     15053 rows
```

### Ce que disent ces chiffres

- **Les acteurs (14 515) et les dépôts (14 995) correspondent exactement**
  à l'« analyse sans bots » de `summarize_data.py`. C'est une bonne
  vérification : les deux scripts appliquent la même règle et arrivent au
  même résultat.
- **67 459 événements sans bots deviennent seulement 15 053 connexions.**
  La plupart des événements sont la même personne qui pousse plusieurs
  fois vers son propre dépôt ; comme on ne répète pas les connexions, tous
  ces événements comptent pour un seul. Ce sont les données dont le
  benchmark a vraiment besoin.
- **Il y a à peine plus de connexions que d'acteurs** (15 053 contre
  14 515) : presque chaque acteur est relié à un seul dépôt. C'est la
  fragmentation déjà vue dans « Résultats de connectivité », maintenant
  sous forme de données prêtes à charger.

**Vérifications faites :** les chiffres ci-dessus ; les noms les plus
récents pour les cas particuliers ; les deux lignes `Copilot` ; que lancer
le script deux fois produit des fichiers **identiques octet par octet** ;
et que git ignore le dossier `data/csv/`.

L'explication ligne par ligne se trouve dans la
[copie annotée](extract_csv.py). Nouveautés de ce script : le module
`csv`, les tuples dans des ensembles et des dictionnaires, comment garder
la valeur la plus récente pendant la lecture, et pourquoi la sortie est
triée.

### Nouveau concept : les tuples, et comment ils se combinent avec les dictionnaires et les ensembles

`extract_csv.py` utilise pour la première fois des **tuples**, et les met
dans des dictionnaires, des ensembles et un autre tuple. Son annotation de
type (`tuple[dict[int, tuple[str, str]], ...]`) ressemble à un casse-tête,
mais ce ne sont que trois petites pièces.

**Ce qu'est un tuple.** Un groupe fixe de valeurs qui vont ensemble, entre
parenthèses. On peut le voir comme une **fiche à cases** : le nombre de
cases ne change pas, et chaque case a un sens selon sa **position** :

```python
fiche = ("2026-08-27T15:35:35Z", "peitongshi")
fiche[0]    # "2026-08-27T15:35:35Z"  ← la date
fiche[1]    # "peitongshi"            ← le nom
```

Cela ressemble à une liste, mais on **ne peut plus le modifier** une fois
créé.

**Les trois structures du script, avec des données réelles :**

| Structure | Ce que c'est | Exemple | Annotation de type |
|---|---|---|---|
| `actors` | Dictionnaire : `id` → fiche *(date, nom)* | `{321725054: ("2026-08-27T15:35:35Z", "peitongshi"), ...}` | `dict[int, tuple[str, str]]` |
| `repos` | Pareil qu'`actors`, pour les dépôts | `{1348625135: ("...", "peitongshi/niulai-chinese"), ...}` | `dict[int, tuple[str, str]]` |
| `pairs` | Ensemble de fiches *(actor_id, repo_id)* : **une fiche = une connexion** | `{(321725054, 1348625135), (19, 1310070394), ...}` | `set[tuple[int, int]]` |

- Dans `actors` et `repos`, la **date** est gardée à côté du nom pour
  pouvoir choisir le nom le plus récent.
- Dans `pairs`, c'est l'**ensemble** qui empêche de répéter les
  connexions : si on ajoute dix fois la même fiche, elle n'est gardée
  qu'une fois.
- Pourquoi des fiches-tuples et pas des listes dans l'ensemble ? Un
  ensemble n'accepte que des éléments qui **ne peuvent pas changer** (s'ils
  changeaient après y être entrés, il ne saurait plus dire s'ils sont en
  double). Les tuples ne changent pas ; les listes, si. C'est pour cela
  que `(19, 1310070394)` fonctionne et pas `[19, 1310070394]`.

**La grande fiche.** Une fonction ne peut renvoyer qu'**une** chose. Pour
en renvoyer quatre, `extract()` les met dans un tuple à quatre cases, et
`main()` l'ouvre et répartit les cases dans quatre variables :

```python
return actors, repos, pairs, skipped_bot_events                    # dans extract()
actors, repos, pairs, skipped_bot_events = extract(args.file)      # dans main()
```

**L'annotation de type, lue morceau par morceau :**

```python
-> tuple[                               # renvoie une fiche à 4 cases :
    dict[int, tuple[str, str]],         #   1. actors : id → (date, nom)
    dict[int, tuple[str, str]],         #   2. repos :  id → (date, nom)
    set[tuple[int, int]],               #   3. pairs :  ensemble de (actor_id, repo_id)
    int,                                #   4. skipped_bot_events : un nombre
]
```

En résumé : il n'y a que **deux sortes de petites fiches**, *(date, nom)*
et *(acteur, dépôt)*, et **une grande fiche** qui regroupe les quatre
choses pour les renvoyer ensemble. La [copie annotée](extract_csv.py)
contient le même schéma juste au-dessus d'`extract()`.


## Étape de chargement (load_postgres.py et load_neo4j.py)

Avec les trois CSV préparés par `extract_csv.py`, l'étape suivante est de
**remplir les deux bases de données** avec eux. Deux scripts s'en
chargent, un par base, qui lisent **exactement les mêmes fichiers** :

| Script | Charge les CSV dans | Avec quel langage |
|---|---|---|
| `load_postgres.py` | PostgreSQL, base `gharchive` | SQL |
| `load_neo4j.py` | Neo4j, base `gharchive` | Cypher |

Ils sont séparés car chaque base de données a son propre langage et sa
propre façon de charger des données, et pour que, si un chargement échoue,
on puisse ne refaire que celui-là.

### Ce qui est créé dans chaque base de données

| Concept | PostgreSQL | Neo4j |
|---|---|---|
| Acteur | table `actor` (`id` BIGINT, `login` TEXT) | nœuds `:Actor` (`id`, `login`) |
| Dépôt | table `repo` (`id` BIGINT, `name` TEXT) | nœuds `:Repo` (`id`, `name`) |
| Connexion | table `actor_repo` (`actor_id`, `repo_id`) | arêtes `(:Actor)-[:INTERACTED_WITH]->(:Repo)` |
| Identifiant unique | `PRIMARY KEY` sur `actor.id` et `repo.id` | contrainte `UNIQUE` sur `Actor.id` et `Repo.id` |
| Pas de connexions répétées | `PRIMARY KEY (actor_id, repo_id)` | Garanti par le CSV, qui n'a déjà plus de paires répétées |
| Les connexions pointent vers quelque chose qui existe | `REFERENCES` (clés étrangères) | Chaque arête est créée en **cherchant** d'abord ses deux nœuds |

Quelques détails :

- **Les `id` sont des nombres des deux côtés :** `BIGINT` dans PostgreSQL
  et des entiers dans Neo4j. Un CSV est du texte ; `load_neo4j.py`
  convertit donc les `id` en nombres avant de les envoyer. Si un côté les
  stockait en texte et l'autre en nombres, les données ne seraient pas
  vraiment identiques.
- **`BIGINT` et pas `INTEGER` :** un `INTEGER` va jusqu'à environ 2 100
  millions, et certains `id` de GitHub dépassent déjà ce chiffre.
- **Le `login` n'est pas unique**, à cause des deux comptes `Copilot` vus
  à l'étape d'extraction.
- **Pourquoi l'arête s'appelle `INTERACTED_WITH`** (« a interagi avec ») et
  pas quelque chose comme « a contribué à » : les connexions viennent de
  tous les types d'événements (push, commentaires, étoiles...), et mettre
  une étoile ou commenter n'est pas contribuer. Un nom neutre est plus
  exact.

### Les index : les « aides normales » de chaque côté

**Ce qu'est un index.** Un index est une structure supplémentaire que la
base de données garde **à côté** d'une table, pour trouver des lignes
**sans avoir à toutes les lire**. Il fonctionne comme l'index alphabétique
à la fin d'un livre : pour trouver le mot « récursivité » dans un livre de
800 pages, au lieu de lire les 800 pages, on le cherche dans l'index (trié
par ordre alphabétique, donc on le trouve tout de suite) et on voit qu'il
est à la page 312. L'index ne contient pas le livre : il contient **chaque
mot et l'endroit où le trouver**.

Dans une base de données, c'est pareil. Par exemple, l'index sur
`actor.id` garde **chaque `id`, trié, et l'endroit où se trouve sa ligne**
sur le disque :

- **Sans index**, pour trouver l'acteur `321725054`, PostgreSQL devrait lire
  les 14 515 lignes d'`actor` une par une et comparer chaque `id`. On
  appelle cela un **parcours séquentiel** (*sequential scan*).
- **Avec un index**, il va directement à la ligne. On appelle cela un
  **parcours par index** (*index scan*).

En interne, PostgreSQL organise ses index en **arbre B** (*B-tree*) : les
valeurs, triées et réparties sur quelques niveaux, comme un dictionnaire
qu'on ouvre au milieu, puis au quart, etc. Grâce à cela, trouver une
valeur demande **très peu d'étapes**, même si la table compte des millions
de lignes.

**Ce que coûte un index :** il occupe de la place sur le disque, et à
chaque insertion d'une ligne il faut aussi mettre à jour les index de la
table ; les chargements sont donc un peu plus lents. C'est pourquoi on ne
met pas un index sur chaque colonne, seulement sur celles qui servent à
**chercher** ou à **joindre des tables**. (La partie « Concepts clés », juste
en dessous, l'explique plus en détail, avec des exemples
d'`EXPLAIN`.)

Le principe de conception (« la requête d'abord ») a fixé une règle :
donner à chaque côté **ses aides normales, ni plus ni moins**. Pour
PostgreSQL, ce sont ces index :

| Index | Comment il est créé | À quoi il sert dans le parcours |
|---|---|---|
| `actor.id` | Automatiquement, par la `PRIMARY KEY` | Trouver un acteur par son `id` instantanément |
| `repo.id` | Automatiquement, par la `PRIMARY KEY` | Trouver un dépôt par son `id` instantanément |
| `(actor_id, repo_id)` | Automatiquement, par la `PRIMARY KEY` d'`actor_repo` | **Acteur → ses dépôts** : comme `actor_id` vient en premier, il sert à chercher par acteur |
| `repo_id` | À la main : `CREATE INDEX actor_repo_repo_id_idx` | **Dépôt → ses acteurs** : le sens inverse, que l'index précédent ne couvre pas |

**Les deux derniers sont les plus importants, et il faut les deux.** Le
parcours du benchmark, `acteur → dépôt → acteur → dépôt`, utilise la table
`actor_repo` dans **deux sens différents**, en les alternant à chaque
saut :

| Saut | Question | Recherche dans `actor_repo` | Index qui la rend rapide |
|---|---|---|---|
| acteur → dépôt | « Dans quels dépôts **cet acteur** a-t-il fait des événements ? » | Lignes avec `actor_id = X` | `(actor_id, repo_id)`, celui de la clé primaire |
| dépôt → acteur | « Quels acteurs ont fait des événements dans **ce dépôt** ? » | Lignes avec `repo_id = Y` | `repo_id`, celui créé à la main |

Le second saut parcourt la connexion **dans le sens inverse** de celui où
elle a été enregistrée : la connexion va de l'acteur au dépôt (la flèche de
Neo4j pointe d'`Actor` vers `Repo`), et ici on va du dépôt vers ses
acteurs.

**Pourquoi un seul index ne suffit pas pour les deux sens.** L'index de la
clé primaire est trié **d'abord par `actor_id`**, comme un annuaire trié
par nom de famille. Trouver toutes les lignes d'un acteur est rapide, car
elles sont regroupées (comme tous les « García » de l'annuaire). Mais
trouver toutes les lignes d'un dépôt avec cet index, c'est comme chercher
toutes les personnes prénommées « Ana » dans un annuaire trié par nom de
famille : elles sont **éparpillées dans tout l'annuaire**, et il faudrait
le lire en entier. C'est pourquoi il faut un **second index, trié par
`repo_id`**.

**Ce qui se passerait sans lui :** à chaque saut dépôt → acteur, PostgreSQL
devrait lire **toute** la table `actor_repo` (15 053 lignes dans le
benchmark), et le faire **une fois pour chaque dépôt** venant du saut
précédent. Neo4j n'a pas ce problème, car chaque nœud `Repo` sait déjà
quelles arêtes arrivent jusqu'à lui. Mesurer ainsi reviendrait à comparer
un PostgreSQL privé de son aide normale à un Neo4j complet : la
comparaison serait **injuste** pour PostgreSQL.

**Dans Neo4j**, les contraintes d'unicité sur `Actor.id` et `Repo.id`
créent leur index, comme les clés primaires. Les arêtes, elles, **n'ont pas
besoin d'index** : dans un graphe, chaque nœud garde déjà des liens directs
vers ses propres arêtes (*index-free adjacency*, « adjacence sans index »).
Cette différence — des index pour joindre des tables contre des liens
directs entre nœuds — est exactement ce que le benchmark veut mesurer.

**`ANALYZE`.** À la fin du chargement, `load_postgres.py` exécute `ANALYZE`
sur les trois tables. Avant d'exécuter chaque requête, PostgreSQL décide
*comment* la faire (utiliser un index ou lire toute la table ? quelle
table d'abord ?), et pour bien décider il utilise des statistiques sur les
données. Juste après un chargement massif, ces statistiques ne sont pas à
jour, et `ANALYZE` les rafraîchit. Cela fait aussi partie des aides
normales du côté relationnel.

### Concepts clés : index, clés primaires, clés étrangères, et pourquoi un graphe n'en a pas besoin

Cette partie développe le tableau **« Ce qui est créé dans chaque base
de données »** et l'explication des index juste au-dessus : ce qu'est
exactement chaque chose, s'il y a des index ou non, et pourquoi le graphe
fonctionne autrement. Ce sont les concepts centraux du projet, car la
question de recherche porte justement sur **la façon dont chaque base de
données trouve les connexions**.

#### D'abord, la réponse courte : y a-t-il des index, ou les clés primaires suffisent-elles ?

**Il y a des index.** Une `PRIMARY KEY` n'est pas une alternative à un
index : **PostgreSQL crée automatiquement un index** pour chaque clé
primaire, car il en a besoin pour vérifier, à chaque insertion, que la
valeur n'est pas répétée. Mais les clés primaires **ne couvrent pas toutes
les recherches**, et les clés étrangères **ne créent aucun index** dans
PostgreSQL. C'est pourquoi il y a un index de plus, créé à la main.

Voici tout ce qui existe dans chaque base de données (c'est pareil dans
`gharchive` et dans `gharchive24h`) :

| Structure | Base | Comment elle est créée | Crée-t-elle un index ? | À quoi elle sert |
|---|---|---|---|---|
| `PRIMARY KEY` d'`actor` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Oui, automatiquement :** `actor_pkey` | Qu'il n'y ait pas deux acteurs avec le même `id`, et trouver un acteur par son `id` instantanément |
| `PRIMARY KEY` de `repo` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Oui, automatiquement :** `repo_pkey` | La même chose, pour les dépôts |
| `PRIMARY KEY` d'`actor_repo` (`actor_id`, `repo_id`) | PostgreSQL | `PRIMARY KEY (actor_id, repo_id)` | **Oui, automatiquement :** `actor_repo_pkey` (composé, sur deux colonnes) | Qu'aucune paire ne se répète, et chercher **les dépôts d'un acteur** |
| Clé étrangère `actor_repo.actor_id` → `actor.id` | PostgreSQL | `REFERENCES actor (id)` | **Non** | Que chaque connexion pointe vers un acteur qui existe |
| Clé étrangère `actor_repo.repo_id` → `repo.id` | PostgreSQL | `REFERENCES repo (id)` | **Non** | Que chaque connexion pointe vers un dépôt qui existe |
| Index sur `actor_repo.repo_id` | PostgreSQL | `CREATE INDEX actor_repo_repo_id_idx` (à la main) | **Oui :** c'est l'index lui-même | Chercher **les acteurs d'un dépôt** : le sens que la clé primaire ne couvre pas |
| Contrainte `UNIQUE` sur `Actor.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE a.id IS UNIQUE` | **Oui, automatiquement** | Qu'il n'y ait pas deux acteurs avec le même `id`, et trouver un acteur par son `id` instantanément |
| Contrainte `UNIQUE` sur `Repo.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE r.id IS UNIQUE` | **Oui, automatiquement** | La même chose, pour les dépôts |
| Les arêtes `INTERACTED_WITH` | Neo4j | `CREATE (a)-[:INTERACTED_WITH]->(r)` | **N'ont pas besoin d'index** | Chaque nœud garde des liens directs vers ses arêtes (voir plus bas) |

**En résumé :** PostgreSQL a **4 index** (trois automatiques pour les clés
primaires et un à la main), et Neo4j en a **2** (ceux des contraintes). Les
connexions du graphe n'ont pas d'index parce qu'elles n'en ont pas besoin :
cette différence est le cœur du benchmark.

**Comment le vérifier vous-même :**

```sql
-- PostgreSQL (Query Tool de pgAdmin, base gharchive) : les index des trois tables
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('actor', 'repo', 'actor_repo')
ORDER BY tablename, indexname;
```

```cypher
// Neo4j (Query, base gharchive) : les contraintes et les index
SHOW CONSTRAINTS;
SHOW INDEXES;
```

Dans pgAdmin, on les voit aussi dans l'arborescence : dans chaque table,
**Indexes** (les index) et **Constraints** (les clés primaires et
étrangères). Dans Neo4j, `SHOW INDEXES` affiche en plus deux index que
Neo4j crée toujours de lui-même (de type `LOOKUP`), qui servent à trouver
rapidement « tous les nœuds ayant une étiquette » ou « toutes les arêtes
d'un type ».

#### Ce qu'est un index, plus en détail

Les bases (l'analogie du livre, et le parcours séquentiel face au parcours
par index) sont expliquées juste au-dessus, dans « Les index ». Ici, on va
un peu plus loin : comment un index est construit à l'intérieur, ce qu'il
coûte et comment PostgreSQL décide de l'utiliser.

**Comment il est fait à l'intérieur : l'arbre B (*B-tree*).** Le type
d'index que PostgreSQL utilise par défaut est un **arbre B** : les valeurs
sont triées et réparties en niveaux, comme un arbre à l'envers. Pour
chercher une valeur, on descend depuis la racine en choisissant à chaque
niveau la bonne branche, comme quand on cherche un mot dans un dictionnaire
en l'ouvrant au milieu, puis au quart, etc. C'est pourquoi le nombre
d'étapes augmente très lentement avec la taille de la table :

| Lignes dans la table | Toutes les lire (sans index) | Étapes approximatives avec un arbre B |
|---|---|---|
| 14 515 (benchmark) | 14 515 | environ 3 ou 4 niveaux |
| 424 098 (24 heures) | 424 098 | environ 3 ou 4 niveaux |
| 100 millions | 100 millions | environ 4 ou 5 niveaux |

(Chaque « niveau » de l'arbre couvre des centaines de valeurs, donc même des
tables énormes ont très peu de niveaux.)

**Ce que coûte un index.** Ce n'est pas gratuit :

- **De l'espace :** c'est une structure de plus, stockée sur le disque.
- **Des écritures plus lentes :** chaque fois qu'une ligne est insérée, la
  base de données doit aussi mettre à jour tous les index de cette table.
  C'est pourquoi, dans la pipeline de 24 heures (plus loin dans ces notes), charger `actor_repo` (avec
  deux index et deux clés étrangères) a pris 27 secondes, et `actor` ou
  `repo` (avec un seul index) à peine une.

C'est pourquoi on ne met pas un index sur chaque colonne : seulement sur
celles qui servent à **chercher** ou à **joindre des tables**. C'est le
principe de « la requête d'abord » appliqué aux index : `login` et `name`
n'ont pas d'index parce que les requêtes du benchmark ne cherchent pas par
ces colonnes.

**Le planificateur décide s'il utilise l'index.** Qu'un index existe
n'oblige pas à l'utiliser. Avant d'exécuter chaque requête, PostgreSQL
calcule ce qui est le moins coûteux (d'où l'importance d'`ANALYZE`, qui lui
fournit les statistiques pour le calculer). Pour voir ce qu'il a décidé, on
met `EXPLAIN` devant la requête :

```sql
EXPLAIN SELECT * FROM actor WHERE id = 321725054;
-- Index Scan using actor_pkey on actor ...     <- utilise l'index de la clé primaire

EXPLAIN SELECT * FROM actor WHERE login = 'peitongshi';
-- Seq Scan on actor ... Filter: (login = ...)  <- pas d'index : lit toute la table
```

(Dans Neo4j, l'équivalent est de mettre `EXPLAIN` ou `PROFILE` devant une
requête Cypher.)

#### Ce qu'est une clé primaire (*primary key*)

La **clé primaire** est la colonne (ou le groupe de colonnes) qui
**identifie chaque ligne de façon unique**, comme le numéro de la carte
d'identité d'une personne. Elle a trois règles que la base de données
elle-même fait respecter :

1. **Unique :** il ne peut pas y avoir deux lignes avec la même valeur.
2. **Jamais vide** (`NOT NULL`) : chaque ligne doit en avoir une.
3. **Une seule par table**, même si elle peut être formée de plusieurs
   colonnes.

**Dans ce projet :**

- Dans `actor` et `repo`, la clé primaire est l'`id` de GitHub. C'est une
  **clé naturelle** : un identifiant qui vient déjà dans les données, et
  non un identifiant inventé par nous (ce serait une *clé de
  substitution*, comme un numéro séquentiel 1, 2, 3...). On a choisi l'`id`
  et pas le nom parce que le nom peut changer (le cas `lucky521-png` →
  `peitongshi`) et n'est pas unique (les deux comptes `Copilot`).
- Dans `actor_repo`, la clé primaire est **composée** : la **paire**
  `(actor_id, repo_id)`. Aucune des deux colonnes n'est unique séparément
  (un acteur peut être dans beaucoup de dépôts, et un dépôt peut avoir
  beaucoup d'acteurs), mais la paire, si. C'est la base de données
  elle-même qui fait respecter la décision « une seule connexion par paire
  acteur–dépôt ».

**Pourquoi c'est important :**

- **Identité :** chaque ligne peut être désignée sans ambiguïté.
- **Pas de doublons :** la base de données rejette toute insertion qui
  répète une clé, même si l'erreur vient de notre code.
- **Cible des clés étrangères :** c'est la valeur vers laquelle pointent
  les connexions (voir plus bas).
- **Recherche rapide :** son index automatique permet de trouver une ligne
  par sa clé instantanément.

**L'index composé** d'`actor_repo` est trié d'abord par `actor_id`, puis
par `repo_id`. C'est pourquoi il sert à trouver les dépôts d'un acteur,
mais pas les acteurs d'un dépôt, et qu'il a fallu l'index supplémentaire
sur `repo_id` (voir, plus haut, le tableau des deux sens du parcours et
l'analogie de l'annuaire).

#### Ce qu'est une clé étrangère (*foreign key*)

Une **clé étrangère** est une colonne qui **pointe vers la clé primaire
d'une autre table**. Dans `actor_repo` :

- `actor_id` pointe vers `actor.id` ;
- `repo_id` pointe vers `repo.id`.

C'est ainsi qu'une base de données relationnelle **représente les
relations** : `actor_repo` ne garde ni l'acteur ni le dépôt, seulement leurs
`id`, comme des « références ». C'est une **table de jonction** (*junction
table*), la façon standard de représenter une relation **plusieurs à
plusieurs** (un acteur peut avoir beaucoup de dépôts, et un dépôt beaucoup
d'acteurs).

**À quoi elle sert : l'intégrité référentielle.** La base de données
garantit que **toute référence pointe vers quelque chose qui existe** :

- On ne peut pas insérer dans `actor_repo` une connexion avec un
  `actor_id` qui n'est pas dans `actor` : PostgreSQL la rejette. (C'est
  pourquoi `load_postgres.py` charge `actor` et `repo` **avant**
  `actor_repo`.)
- On ne peut pas supprimer un acteur d'`actor` tant qu'une connexion le
  désigne, sauf si l'on dit explicitement quoi faire de ces connexions (par
  exemple, `ON DELETE CASCADE`, qui les supprimerait aussi). C'est pourquoi
  `load_postgres.py` supprime `actor_repo` **avant** les deux autres.

Sans clés étrangères, une erreur dans le code pourrait laisser des
connexions « orphelines », qui pointent vers des acteurs ou des dépôts
inexistants, et les parcours donneraient des résultats faux sans que
personne ne s'en aperçoive.

**Ce qu'elle coûte :** à chaque insertion dans `actor_repo`, PostgreSQL
vérifie que l'acteur **et** le dépôt existent, c'est-à-dire **deux
recherches par ligne**. C'est une autre des raisons pour lesquelles cette
table met plus de temps à se charger.

**Attention : une clé étrangère ne crée pas d'index** (dans PostgreSQL).
C'est une erreur très courante de croire le contraire. La clé étrangère
vérifie que la référence existe, mais elle **n'accélère pas** les
recherches sur cette colonne. Si une colonne sert à joindre des tables, il
faut l'indexer à part, comme nous l'avons fait avec `repo_id`. (`actor_id`
n'en a pas besoin, car elle vient déjà en premier dans l'index de la clé
primaire composée.)

#### Comment on parcourt une relation dans une base relationnelle : le JOIN

Dans une base relationnelle, les connexions **ne sont pas stockées comme
des chemins** : elles sont **calculées au moment de la requête**, avec un
**JOIN** (« jointure »), qui associe les lignes de deux tables ayant une
valeur égale.

Pour un saut (les dépôts d'un acteur), la requête est :

```sql
SELECT r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id     -- 1re jointure
JOIN repo r        ON r.id = ar.repo_id      -- 2e jointure
WHERE a.id = 321725054;
```

Ce que fait PostgreSQL, étape par étape (grâce aux index) :

1. Il cherche l'acteur `321725054` dans l'index `actor_pkey`.
2. Il cherche dans l'index `actor_repo_pkey` toutes les lignes avec cet
   `actor_id` : il obtient leurs `repo_id`.
3. Pour chaque `repo_id`, il cherche le dépôt dans l'index `repo_pkey`.

Chaque flèche du parcours est une **recherche dans un index**, et chaque
recherche a un coût qui dépend (un peu seulement, grâce à l'arbre B) de la
taille totale de la table. Pour le parcours du benchmark
(`acteur → dépôt → acteur → dépôt`), chaque saut ajoute **plus de JOIN**,
et chaque JOIN est fait pour **toutes** les lignes qui arrivent du saut
précédent. Si le nombre de lignes augmente à chaque saut, le travail
augmente très vite.

#### Pourquoi un graphe n'a ni clés primaires ni clés étrangères

Une base de données graphe stocke les choses autrement :

| Concept relationnel | Équivalent dans le graphe de Neo4j |
|---|---|
| Table (`actor`, `repo`) | **Étiquette** (*label*) : `:Actor`, `:Repo`. Regroupe les nœuds du même type |
| Ligne | **Nœud** |
| Colonne | **Propriété** (`id`, `login`, `name`) |
| Table de jonction + clés étrangères (`actor_repo`) | **Arête** (*relationship*) : `-[:INTERACTED_WITH]->`, stockée comme un objet à part entière qui relie les deux nœuds |
| Clé primaire | N'existe pas en tant que telle. On crée une **contrainte d'unicité** sur une propriété (`id`) |
| JOIN | **Suivre l'arête** : aller d'un nœud à ses voisins |

**Pourquoi les clés étrangères ne sont pas nécessaires :** dans le graphe,
la connexion **n'est pas une valeur qui pointe vers une autre valeur** (un
`actor_id` qu'il faut chercher dans une autre table). **C'est un objet à
part entière qui relie directement les deux nœuds**. Une arête ne peut pas
exister sans ses deux extrémités : Neo4j ne permet ni de créer une arête
« dans le vide » ni de supprimer un nœud qui a encore des arêtes (d'où le
`DETACH DELETE` de `load_neo4j.py`, qui supprime d'abord les arêtes).
Autrement dit, **l'intégrité référentielle est incluse dans la structure
elle-même**, sans avoir besoin de la déclarer.

**Pourquoi il n'y a pas de « vraie » clé primaire :** Neo4j identifie
chaque nœud en interne avec son propre identifiant (l'*element id*), qui
**n'est pas** une de nos données et qu'il vaut mieux ne pas utiliser comme
clé métier, car il peut être réutilisé si des nœuds sont supprimés. C'est
pourquoi nous avons ajouté la **contrainte d'unicité** sur notre propriété
`id` : elle joue le rôle de la clé primaire (pas de doublons, recherche
rapide par index), mais elle est facultative et c'est nous qui la
décidons.

**Et le plus important : dans le graphe, l'index ne sert qu'à trouver le
point de départ.** Une fois le premier nœud trouvé (par exemple, l'acteur
`321725054`, grâce à la contrainte d'unicité), **plus aucun index n'est
utilisé** : le parcours suit directement les arêtes.

#### Ce qu'il y a à la place : l'adjacence sans index (*index-free adjacency*)

Dans Neo4j, **chaque nœud garde l'endroit où se trouvent ses propres
arêtes**, et chaque arête garde **l'endroit où se trouvent ses deux
nœuds**. Conceptuellement :

- l'enregistrement d'un nœud pointe vers ses arêtes ;
- l'enregistrement d'une arête pointe vers son nœud de départ, son nœud
  d'arrivée et l'arête suivante de chacun d'eux.

(Les versions récentes de Neo4j organisent physiquement les données
autrement, en regroupant les arêtes de chaque nœud, mais l'idée est la
même : les connexions d'un nœud sont stockées **avec le nœud**.)

Ainsi, aller d'un acteur à ses dépôts, ce n'est pas « chercher dans une
table toutes les lignes dont l'`actor_id` vaut X », mais **« lire la liste
des arêtes que le nœud a déjà »**. C'est comme la différence entre :

- **Relationnel :** chercher les amis d'Ana dans l'annuaire de toute la
  ville (une recherche, même rapide, dans une liste de tout le monde).
- **Graphe :** ouvrir le carnet d'adresses d'Ana, où ses amis sont déjà
  notés (suivre des liens qui sont déjà là).

#### Pourquoi cela optimise (et pourquoi il faut le mesurer)

| | PostgreSQL (relationnel) | Neo4j (graphe) |
|---|---|---|
| Trouver le point de départ | Une recherche dans un index (arbre B) | Une recherche dans un index (la contrainte) |
| Chaque saut | Un JOIN : une **recherche dans un index** pour chaque ligne qui arrive | **Suivre des pointeurs** que le nœud a déjà |
| Le coût d'un saut dépend-il de la taille **totale** de la base ? | Un peu : l'index grandit avec la table (même si c'est très lentement) | Non : il dépend seulement du **nombre d'arêtes de ce nœud** |
| Ce qui augmente quand on ajoute des sauts | Le nombre de JOIN et de recherches dans les index | Le nombre d'arêtes suivies |

**La théorie :** sur des parcours **courts** (un ou deux sauts), PostgreSQL
est très rapide, car ses index sont très efficaces et il optimise les JOIN
depuis des décennies. Sur des parcours **longs**, le graphe devrait gagner,
car son coût ne dépend que de la partie du graphe parcourue, et non de la
taille totale des tables.

**Mais ce n'est qu'une hypothèse.** L'arbre B demande très peu d'étapes,
même sur des tables énormes, les deux bases gardent en mémoire les données
les plus utilisées, et le planificateur de PostgreSQL est très bon. **À
partir de combien de sauts et avec quel volume de données le gagnant
change**, c'est exactement ce que ce projet veut **mesurer**, au lieu de le
tenir pour acquis.

#### Autres concepts utiles à connaître

**La normalisation.** C'est la façon d'organiser les tables pour ne pas
stocker deux fois la même donnée. Par exemple, le `login` d'un acteur se
trouve **uniquement** dans `actor`, et n'est pas répété dans chaque ligne
d'`actor_repo`. S'il changeait, il suffirait de le modifier à un seul
endroit. C'est pourquoi la question de recherche parle d'un modèle
relationnel **normalisé** : c'est la façon « correcte » de concevoir le
côté relationnel, celle qu'on utiliserait en pratique.

**La cardinalité d'une relation.** Combien d'éléments d'un côté peuvent
être liés à combien de l'autre :

| Type | Exemple | Comment on le stocke en relationnel |
|---|---|---|
| Un à un | Une personne et sa carte d'identité | Une clé étrangère unique |
| Un à plusieurs | Un dépôt et ses *issues* (chaque issue appartient à un seul dépôt) | Une clé étrangère du côté « plusieurs » |
| **Plusieurs à plusieurs** | **Acteurs et dépôts (ce projet)** | **Une table de jonction** (`actor_repo`) avec deux clés étrangères |

Dans le graphe, les trois types se stockent de la même façon : avec des
arêtes.

**Contrainte ou index.** Une **contrainte** (*constraint*) est une
**règle** que la base de données fait respecter (unique, non vide, la
référence existe). Un **index** est une **structure pour chercher
rapidement**. Ils vont souvent ensemble (une clé primaire ou une contrainte
d'unicité crée un index pour pouvoir être vérifiée), mais ce sont des
choses différentes : une clé étrangère est une contrainte **sans** index,
et `actor_repo_repo_id_idx` est un index **sans** contrainte.

**Transactions et ACID.** Une **transaction** est un groupe de
modifications qui s'appliquent **toutes ou aucune**. Les deux bases de
données respectent les propriétés **ACID** : *Atomicité* (tout ou rien),
*Cohérence* (les règles sont toujours respectées), *Isolation* (les
transactions ne se marchent pas dessus) et *Durabilité* (ce qui est
enregistré n'est pas perdu, même si l'ordinateur s'éteint). C'est pourquoi
le chargement de PostgreSQL, qui est une seule transaction, ne laisse
jamais des données à moitié chargées.

**Le schéma dans chaque base de données.** PostgreSQL exige de définir les
tables, les colonnes et les types **avant** de stocker des données
(*schema-on-write*). Neo4j est plus souple : on peut créer des nœuds avec
n'importe quelle propriété sans la déclarer avant ; les contraintes sont
facultatives et nous les ajoutons nous-mêmes pour garantir la qualité des
données et la rapidité des recherches.

**`EXPLAIN` et `PROFILE` : voir comment une requête s'exécute.** Ils seront
importants dans le benchmark : il ne suffit pas de savoir **combien de
temps** prend une requête, il faut aussi savoir **pourquoi**.

- PostgreSQL : `EXPLAIN` affiche le plan sans l'exécuter ;
  `EXPLAIN ANALYZE` l'exécute et affiche le temps réel de chaque étape (par
  exemple, s'il a utilisé un `Index Scan` ou un `Seq Scan`).
- Neo4j : `EXPLAIN` affiche le plan ; `PROFILE` l'exécute et compte, étape
  par étape, combien de données ont été touchées (*db hits*).

### Comment chaque script charge

**`load_postgres.py` :**

1. **Il supprime et recrée les tables** (`DROP TABLE IF EXISTS` et
   `CREATE TABLE`). Ainsi chaque exécution part de zéro, et le lancer deux
   fois donne le même résultat. L'ordre compte : `actor_repo` est supprimée
   en premier et créée en dernier, car elle dépend des deux autres.
2. **Il charge chaque CSV avec `COPY`**, le mécanisme de **chargement
   massif** de PostgreSQL : bien plus rapide que d'insérer ligne par ligne,
   car les données entrent comme un flux continu. Avec
   `COPY ... FROM STDIN`, Python envoie le contenu du fichier par la
   connexion ; le serveur n'a donc pas besoin d'accéder à vos fichiers.
   D'abord `actor` et `repo`, puis `actor_repo`, à cause des clés
   étrangères.
3. **Il exécute `ANALYZE`** (voir plus haut).
4. **Il enregistre tout avec `COMMIT`.** Tout ce qui précède forme une
   seule **transaction** : un groupe de modifications appliquées toutes
   ensemble ou pas du tout. Si le script échouait en cours de route,
   PostgreSQL annulerait tout ; un chargement à moitié fait ne peut donc
   jamais rester.
5. **Il vérifie les décomptes** : il compte les lignes de chaque table et
   les compare à celles du CSV.

**`load_neo4j.py` :**

1. **Il lit les trois CSV dans Python** et convertit les `id` en nombres.
2. **Il vide la base de données** (`MATCH (n) DETACH DELETE n` : supprime
   chaque nœud avec ses arêtes) et crée les **contraintes d'unicité**, si
   elles n'existent pas.
3. **Il crée les nœuds, puis les arêtes, par lots de 5 000 lignes.** Au
   lieu d'envoyer les 15 053 connexions en une seule énorme requête, il
   les envoie par morceaux. Chaque lot utilise `UNWIND`, qui transforme la
   liste en une ligne par élément dans la base elle-même, comme une boucle
   `for`. Pour chaque arête, Neo4j **cherche** l'acteur et le dépôt par
   leur `id` (rapide, grâce aux contraintes) et crée l'arête entre eux.
   C'est pourquoi les nœuds doivent exister avant les arêtes.
4. **Il vérifie les décomptes** de nœuds et d'arêtes par rapport aux CSV.

Les explications ligne par ligne se trouvent dans les copies annotées :
[load_postgres.py](load_postgres.py) et [load_neo4j.py](load_neo4j.py).

### Comment les lancer

Avec les deux bases démarrées et après `extract_csv.py` :

```bash
./run.sh scripts/extract_csv.py      # si les CSV n'existent pas encore
./run.sh scripts/load_postgres.py
./run.sh scripts/load_neo4j.py
```

Les deux passent par `run.sh`, car ils ont besoin des mots de passe.

### Résultat

Les deux chargements ont fonctionné du premier coup, et **les six
vérifications indiquent OK** :

```
Rows loaded (database vs. CSV file):
  actor          14515   actors.csv         14515   OK
  repo           14995   repos.csv          14995   OK
  actor_repo     15053   actor_repo.csv     15053   OK

Loaded (database vs. CSV file):
  Actor nodes              14515   actors.csv         14515   OK
  Repo nodes               14995   repos.csv          14995   OK
  INTERACTED_WITH edges    15053   actor_repo.csv     15053   OK
```

Les deux bases contiennent maintenant **exactement les mêmes données** :
14 515 acteurs, 14 995 dépôts et 15 053 connexions. C'est la condition
nécessaire pour commencer à comparer des requêtes.

### Le chronomètre du chargement

Les deux scripts affichent combien de temps prend **chaque étape** et le
**total du chargement**, mesurés avec `time.perf_counter()` : l'horloge de
Python faite pour mesurer des durées, la plus précise, et qui n'est pas
affectée si l'heure de l'ordinateur change.

- **Compté dans le total :** tout ce qui écrit dans la base, de la création
  ou du vidage jusqu'à l'enregistrement (dans PostgreSQL, le `COMMIT` est
  fait juste avant d'arrêter l'horloge).
- **Pas compté :** la connexion, la vérification finale des décomptes et,
  dans Neo4j, la lecture des CSV dans Python (affichée à part).

**Important : ces temps ne comparent pas les deux bases de données.** Ils
indiquent combien de temps prend le processus (par exemple, combien
attendre quand on chargera plus d'heures de données), mais ce **ne sont
pas des résultats du benchmark**, pour trois raisons :

1. **Chacune charge différemment :** PostgreSQL avec `COPY`, son mécanisme
   de chargement massif ; Neo4j par lots via le driver, en cherchant les
   deux nœuds de chaque arête.
2. **C'est une seule exécution.** Un benchmark sérieux répète chaque mesure
   plusieurs fois et écarte la première, car au début la base n'a encore
   rien en mémoire.
3. **Ce n'est pas la question du projet.** La question de recherche porte
   sur les **parcours multi-sauts**, pas sur la durée du chargement.

### Voir les données chargées

**Dans pgAdmin 4**, les tables se trouvent dans : **gharchive** →
**Schemas** → **public** → **Tables**. (`public` est le schéma par défaut :
une sorte de dossier dans la base où les tables sont créées si on n'en
indique pas d'autre.) Les **Catalogs** affichés plus haut sont les tables
internes de PostgreSQL, pas les données du projet.

- Si les tables n'apparaissent pas, c'est qu'elles ont été créées après
  l'ouverture de pgAdmin : clic droit sur **Tables** → **Refresh**.
- **Voir les données :** clic droit sur une table → **View/Edit Data** →
  **First 100 Rows**, ou une requête dans le Query Tool. L'en-tête de la
  colonne `id` affiche **`[PK] bigint`** : `[PK]` indique que c'est la clé
  primaire.
- **Voir les index :** dans chaque table, **Indexes**. `actor_repo` en a
  deux : `actor_repo_pkey` (celui de la clé primaire) et
  `actor_repo_repo_id_idx`.

Requêtes utiles dans le Query Tool :

```sql
-- Combien de lignes contient chaque table
SELECT (SELECT count(*) FROM actor)      AS actors,
       (SELECT count(*) FROM repo)       AS repos,
       (SELECT count(*) FROM actor_repo) AS connections;

-- Les dépôts d'un acteur : un « saut » du parcours
SELECT a.login, r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id
JOIN repo r        ON r.id = ar.repo_id
WHERE a.login = 'peitongshi';
```

**Dans Neo4j**, depuis **Query** dans Neo4j Desktop, dans la base
`gharchive` (avec le sélecteur de base ou `:use gharchive`) :

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

Le résultat apparaît **dessiné** : un cercle pour l'acteur, un autre pour
son dépôt et une flèche entre les deux. C'est la même requête que la
seconde de PostgreSQL, écrite dans le langage du graphe : en SQL, il faut
deux `JOIN` pour aller de l'acteur au dépôt en passant par `actor_repo` ;
en Cypher, la flèche *est* la connexion.


## Voir et interroger le graphe dans Neo4j Desktop (Query)

PostgreSQL a pgAdmin pour regarder ses tables. L'équivalent pour Neo4j est
l'outil **Query** de Neo4j Desktop : un éditeur où l'on écrit des requêtes
Cypher et où l'on voit les résultats, même **dessinés** sous forme de
nœuds et de flèches. Cette section explique comment l'utiliser avec la
version installée dans ce projet (Neo4j Desktop 2.2.1), y compris les
pièges rencontrés en chemin.

### Étape 1 : vérifier que l'instance est démarrée

Dans le menu de gauche, **Local instances**. La carte `gharchive` doit
afficher **RUNNING** ; sinon, cliquez sur **Start**.

En dessous apparaît la liste **Databases**, qui devrait en afficher
trois : `gharchive`, `neo4j` et `system`.

- **S'il est écrit *Databases (0)* et *Refreshing...* :** Neo4j Desktop
  n'a pas pu lire la liste. Cela arrive souvent juste après le démarrage,
  ou après avoir **changé le mot de passe** de Neo4j, si Desktop a gardé
  l'ancien. Attendez quelques secondes ou cliquez sur le bouton de
  rafraîchissement (⟳) ; si rien ne change, reconnectez-vous avec le
  nouveau mot de passe. **Les données ne sont pas perdues** : c'est
  seulement la liste qui ne s'est pas chargée.

### Étape 2 : ouvrir Query et le connecter à l'instance

1. Dans le menu de gauche, sous **Studio**, cliquez sur **Query**.
2. S'il est écrit **No instance connected** en haut, cliquez sur **Connect
   to instance** (au centre) ou sur le menu déroulant **No instance
   connected ∨** (en haut à gauche), et choisissez l'instance
   **`gharchive`**.
3. S'il demande des identifiants : utilisateur **`neo4j`** et le mot de
   passe de `secrets.sh` (`NEO4J_PASSWORD`).

Trois indicateurs apparaissent en haut, à vérifier à chaque fois :

| Indicateur | Ce qu'il doit afficher | Ce que cela signifie |
|---|---|---|
| **Instance** | `gharchive`, avec un point vert | L'instance (le « serveur ») à laquelle vous êtes connecté |
| **Database** | **`gharchive`** | La base de données de l'instance où s'exécutent les requêtes |
| **User** | `neo4j` | L'utilisateur avec lequel vous êtes connecté |

### Étape 3 : choisir la base `gharchive` (le piège le plus fréquent)

À la connexion, Query ouvre la base **`neo4j`**, celle par défaut. Cette
base est **vide** : les données du projet ont été chargées dans
`gharchive`. Le signe que vous êtes dans la mauvaise base, c'est que le
panneau de gauche indique **Nodes (0)** et **Relationships (0)**.

Pour changer de base, utilisez le menu déroulant **Database ∨** en haut,
ou tapez ceci dans la barre de requêtes et appuyez sur **Ctrl + Entrée** :

```cypher
:use gharchive
```

La barre passe de `neo4j$` à **`gharchive$`**. Les commandes qui
commencent par `:` (comme `:use`) ne sont pas du Cypher : ce sont des
commandes de l'outil lui-même.

### Étape 4 : le panneau « Database information »

Avec `gharchive` sélectionnée, le panneau de gauche résume le contenu de la
base, et c'est le moyen le plus rapide de vérifier le chargement :

| Dans le panneau | Valeur | D'où cela vient |
|---|---|---|
| **Nodes** | 29 510 | 14 515 `Actor` + 14 995 `Repo` |
| **Relationships** | 15 053 | Les connexions `INTERACTED_WITH` |
| **Étiquettes** | `Actor`, `Repo` | Les deux types de nœuds |
| **Type de relation** | `INTERACTED_WITH` | Le type d'arête |
| **Property keys** | `id`, `login`, `name`... | Les propriétés des nœuds |

Les chiffres correspondent exactement à ceux vérifiés par
`load_neo4j.py`. Dans *Property keys* apparaissent aussi d'autres noms
(`data`, `nodes`, `relationships`, `style`, `visualisation`) : ce sont des
noms que Neo4j a enregistrés en interne, pas des propriétés de nos nœuds.

**Si vous cliquez sur une étiquette** (par exemple `Actor`), Query exécute
une requête qui affiche quelques nœuds de ce type.

### Étape 5 : écrire des requêtes et lire le résultat

Les requêtes s'écrivent dans la barre du haut (`gharchive$`) et s'exécutent
avec **Ctrl + Entrée** ou le bouton ▶. Chaque résultat apparaît en dessous,
dans son propre cadre, et les précédents restent plus bas.

**La première requête du projet :** un acteur et son dépôt.

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

Elle se lit presque comme un dessin : « cherche (`MATCH`) un nœud `Actor`
avec le login `peitongshi`, relié par une flèche `INTERACTED_WITH` à un
nœud `Repo`, et renvoie (`RETURN`) les trois ». `a`, `e` et `r` sont des
noms qu'on leur donne pour pouvoir les renvoyer.

**Ce que l'on voit :**

- **Deux cercles :** l'acteur (vert) et le dépôt (bleu). Chaque étiquette
  a sa couleur.
- **Une flèche** de l'acteur vers le dépôt, avec le texte
  `INTERACTED_WITH`. Le sens de la flèche est celui défini au chargement :
  d'`Actor` vers `Repo`.
- **Le texte dans chaque cercle** est l'une de ses propriétés, que Neo4j
  choisit d'afficher. L'acteur montre son `id` (`321725054`) et le dépôt
  son `name` (`peitongshi/niulai-chinese`). En cliquant sur un nœud, on
  voit toutes ses propriétés.
- **Results overview**, à droite : combien de nœuds et de relations
  contient le résultat, par type (ici, 1 `Actor`, 1 `Repo` et 1
  `INTERACTED_WITH`).

Cet acteur est l'un des cas particuliers de l'étape d'extraction : celui
qui a changé de login pendant cette heure (de `lucky521-png` à
`peitongshi`). Comme le script a gardé le nom le plus récent, il apparaît
ici sous le nom `peitongshi`.

**Les trois onglets du résultat :**

| Onglet | Ce qu'il affiche |
|---|---|
| **Graph** | Le dessin des nœuds et des flèches |
| **Table** | Les mêmes résultats sous forme de tableau, ligne par ligne |
| **Raw** | La réponse telle que le serveur l'envoie (texte JSON) |

Sous le cadre se trouvent des commandes pour zoomer, recadrer le dessin et
sélectionner ou déplacer des nœuds.

**Le temps affiché en bas** (par exemple *Started streaming 1 record after
388 ms and completed after 550 ms*) est la durée de cette requête. Comme
pour les temps de chargement, **ce n'est pas une mesure du benchmark** :
c'est une seule exécution, la première (rien encore en mémoire), et elle
inclut le travail de l'outil. De plus, cette requête cherche par `login`,
et `login` **n'a pas d'index** (seul `id` en a un) ; Neo4j a donc dû
examiner les acteurs un par un pour le trouver. Les requêtes du benchmark
chercheront toujours par `id`.

### D'autres requêtes utiles

```cypher
// Combien de nœuds et de relations (14515, 14995 et 15053)
MATCH (a:Actor) WITH count(a) AS actors
MATCH (r:Repo)  WITH actors, count(r) AS repos
MATCH ()-[e:INTERACTED_WITH]->() RETURN actors, repos, count(e) AS connections;
```

```cypher
// Quelques dépôts (toujours avec LIMIT pour dessiner)
MATCH (r:Repo) RETURN r LIMIT 25;
```

```cypher
// Le dépôt avec le plus d'acteurs différents : un « point de rencontre » du graphe
MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo)
WITH r, count(a) AS actors ORDER BY actors DESC LIMIT 1
MATCH (a:Actor)-[e:INTERACTED_WITH]->(r)
RETURN a, e, r;
```

Le dernier résultat vaut le coup d'œil : un dépôt au centre avec
plusieurs flèches qui arrivent de ses acteurs. C'est justement l'un des
rares points par lesquels un parcours multi-sauts peut passer d'un acteur
à un autre.

**Mettez toujours un `LIMIT` quand vous dessinez.** Dessiner les quelque
30 000 nœuds d'un coup rendrait l'outil très lent, et on ne verrait rien.

### Ce qu'il faut éviter dans Neo4j Desktop

En cherchant comment ouvrir Query, on est tombé sur des menus avec des
options dangereuses ou qui ne servent pas à cela :

| Où | Option | Attention |
|---|---|---|
| `···` d'une **base de données** dans la liste *Databases* | **Delete** | **Supprime la base avec toutes ses données.** Ce menu sert seulement à gérer la base (l'exporter, la supprimer...), pas à la consulter |
| `···` de l'**instance** (la carte) | **Upgrade** | Met Neo4j à jour vers une autre version : cela changerait les conditions du benchmark. **À ne pas utiliser** |
| `···` de l'**instance** | **Open ›** | N'ouvre que des fichiers (le dossier de l'instance, le journal et la configuration), pas des outils de requête |

**Si la base `gharchive` était un jour supprimée par erreur,** on la
récupère en un instant : **Create database** avec le nom `gharchive`, puis
`./run.sh scripts/load_neo4j.py`. C'est un autre avantage d'avoir les CSV
et les scripts : les bases peuvent toujours être reconstruites à partir de
zéro.

### Résumé : les étapes à chaque fois

1. **Local instances** → `gharchive` en **RUNNING**.
2. **Query** → **Connect to instance** → `gharchive` → utilisateur `neo4j`.
3. **Database** → **`gharchive`** (ou `:use gharchive`). Vérifier que le
   panneau affiche **Nodes (29,510)**.
4. Taper la requête dans la barre `gharchive$` → **Ctrl + Entrée**.


## La pipeline de 24 heures (pipeline.py) : une perspective d'ingénierie des données

Jusqu'ici, tout le projet travaillait avec **une seule heure choisie à la
main** (2026-08-27, 15:00 UTC). Elle est parfaite pour le benchmark, car
elle ne change jamais, mais ce n'est pas ainsi qu'on travaille avec de
vraies données : en ingénierie des données, les données arrivent en
continu, et ce qui compte, c'est d'avoir un **processus reproductible**.
Cette étape ajoute ce processus : une **pipeline** (une chaîne d'étapes
automatique) qui reconstruit une base de données avec les **dernières 24
heures** de GH Archive.

### Deux processus, chacun avec sa base de données

Désormais, le projet a **deux processus séparés** :

| | Benchmark | Pipeline de 24 heures |
|---|---|---|
| **Données** | Une heure fixe : 2026-08-27, 15:00 UTC | Les dernières 24 heures, avec un jour de retard |
| **Base de données** (dans PostgreSQL et dans Neo4j) | `gharchive` | `gharchive24h` |
| **Comment elle est chargée** | À la main : `extract_csv.py`, `load_postgres.py`, `load_neo4j.py` | Automatiquement : `pipeline.py` |
| **Change-t-elle ?** | **Jamais.** Elle est figée | Elle est reconstruite à chaque exécution |
| **À quoi elle sert** | Mesurer et comparer des requêtes dans des conditions reproductibles | Avoir des données récentes et abondantes, avec un processus d'ingénierie des données |

Au total, il y a **quatre bases de données**, deux sur chaque serveur :

```
PostgreSQL (port 5432)                 Neo4j (instance "gharchive", port 7687)
├── gharchive      ← benchmark          ├── gharchive      ← benchmark
└── gharchive24h   ← pipeline           └── gharchive24h   ← pipeline
```

**Pourquoi séparées :** si la pipeline utilisait `gharchive`, chaque
exécution effacerait les données du benchmark, et les mesures ne seraient
plus reproductibles. C'est pourquoi `pipeline.py` **refuse** de travailler
sur `gharchive`, même si on le lui demande par erreur.

**Pourquoi `gharchive24h` et pas `gharchive_24h` :** Neo4j n'accepte pas
le tiret bas dans les noms de bases de données (seulement des lettres, des
chiffres, des points et des tirets). Pour que le nom soit le même des deux
côtés, on utilise `gharchive24h`.

### La fenêtre : 24 heures glissantes, avec un jour de retard, en UTC

À chaque exécution, la pipeline calcule quelles 24 heures charger :

1. Elle prend l'heure actuelle **en UTC** et l'arrondit à l'heure pile
   inférieure.
2. Elle retire **24 heures de retard** : c'est là que la fenêtre se
   **termine**.
3. Elle retire encore **24 heures** : c'est là qu'elle **commence**.

**Exemple :** le 22 octobre à 11:15 UTC, la fenêtre va du **20/10 à 11:00
au 21/10 à 11:00**. Cela fait 24 fichiers de GH Archive, de
`2026-10-20-11.json.gz` à `2026-10-21-10.json.gz` (le dernier couvre de
10:00 à 11:00).

- **Pourquoi UTC :** GH Archive nomme ses fichiers en heure UTC. Au
  Portugal, l'heure est en avance sur UTC (d'une heure en été), donc
  utiliser l'heure locale décalerait la fenêtre.
- **Pourquoi le jour de retard :** GH Archive publie chaque heure peu après
  sa fin, mais parfois avec du retard. Avec un jour de marge, toutes les
  heures de la fenêtre sont publiées à coup sûr. Le retard est un paramètre
  (`--lag-hours`), on peut donc le réduire plus tard.
- **« Glissante » :** chaque heure, la fenêtre avance d'une heure. La plus
  ancienne sort et une nouvelle entre.

### Tout reconstruire à chaque exécution

À chaque exécution, la pipeline **vide et remplit à nouveau** les deux
bases `gharchive24h` à partir des 24 heures. Cela paraît beaucoup de
travail, mais c'est plus simple et plus fiable que d'ajouter la nouvelle
heure et de retirer l'ancienne : avec le schéma actuel (une connexion par
paire acteur–dépôt, sans date), on ne saurait pas quelles connexions
apparaissaient *seulement* dans l'heure qui sort.

Ce qui se fait bien de façon incrémentale, c'est le **téléchargement** :
les fichiers sont gardés dans `data/live/raw/`, et à chaque exécution on ne
télécharge que la nouvelle heure et on supprime celle qui est sortie de la
fenêtre.

### Une tâche planifiée toutes les heures, pas un processus qui tourne en permanence

| | Processus qui tourne en permanence | Tâche planifiée toutes les heures |
|---|---|---|
| Comment ça marche | Un programme qui ne se termine jamais : il traite, attend une heure, recommence | Un programme normal qui fait son travail et **se termine** ; le système le lance toutes les heures |
| S'il échoue une fois | Il reste arrêté jusqu'à ce que quelqu'un le relance | L'heure suivante, il réessaie tout seul |
| Où on l'utilise | Le *streaming* (par exemple, Kafka) | Les processus *batch* (cron, Airflow, le Planificateur de tâches de Windows) |

Comme GH Archive publie les données **par heure**, le choix naturel est un
processus *batch* planifié. Sous Windows, c'est le **Planificateur de
tâches** (*Task Scheduler*) qui le lance. Tant que la pipeline vit sur le
portable, elle ne s'exécutera que si l'ordinateur est allumé et **Neo4j
Desktop ouvert** (PostgreSQL démarre tout seul, en tant que service). Pour
qu'elle fonctionne sans le portable, il faudrait la déplacer sur un serveur
toujours allumé ; les options sont à la fin de cette section.

### Ce que fait chaque exécution

1. **Calcule la fenêtre** (voir plus haut).
2. **Synchronise les fichiers :** supprime de `data/live/raw/` ceux qui
   sont sortis de la fenêtre et télécharge seulement ceux qui manquent.
3. **Extrait les CSV** des 24 heures dans `data/live/csv/`, avec le même
   code que le benchmark (`extract_csv.py`) : sans bots, sans connexions
   répétées et avec le nom le plus récent de chaque `id`.
4. **Vérifie les serveurs et crée les bases si elles n'existent pas :** si
   l'un d'eux ne répond pas, elle s'arrête là, **avant de vider quoi que ce
   soit**.
5. **Reconstruit PostgreSQL puis Neo4j** avec les mêmes scripts de
   chargement que le benchmark, mais dans `gharchive24h`, et compare les
   comptages avec les CSV.
6. **Note le résultat :** dans `logs/pipeline.log`, tout ce qui s'est
   passé ; et, si tout s'est bien passé, la fenêtre chargée dans
   `data/live/current_window.txt`.

| Dossier ou fichier | Ce qu'il contient | Sur GitHub ? |
|---|---|---|
| `data/live/raw/` | Les 24 fichiers `.json.gz` de la fenêtre | Non (`data/` est dans le `.gitignore`) |
| `data/live/csv/` | Les trois CSV de la fenêtre | Non |
| `data/live/current_window.txt` | La dernière fenêtre chargée avec succès, avec ses comptages | Non |
| `data/live/pipeline.lock` | N'existe que pendant qu'une exécution est en cours | Non |
| `logs/pipeline.log` | L'historique de toutes les exécutions | Non (`logs/` est dans le `.gitignore`) |

### Les pratiques d'ingénierie des données utilisées par la pipeline

| Pratique | Ce que cela signifie | Comment c'est appliqué ici |
|---|---|---|
| **Idempotence** | Exécuter quelque chose une fois ou dix fois donne le même résultat | Les bases ne sont créées que si elles n'existent pas (`IF NOT EXISTS`) ; le contenu est toujours reconstruit de la même façon à partir de la même fenêtre |
| **Vérification préalable** (*pre-flight check*) | Vérifier que tout est prêt avant de modifier quoi que ce soit | Téléchargements, extraction et connexion aux deux serveurs passent **avant** de vider la moindre base |
| **Écriture atomique** | Un fichier est complet ou n'existe pas ; jamais à moitié | Les téléchargements sont enregistrés en `.part` et ne sont renommés qu'une fois terminés |
| **Nouvelles tentatives** | Une panne réseau passagère ne doit pas faire tomber le processus | Chaque téléchargement est tenté jusqu'à 3 fois, en attendant un peu plus à chaque fois |
| **Échouer clairement** | Un vrai problème se remarque, il n'est pas caché | Si une heure n'existe pas (erreur 404), la pipeline le dit et ne charge pas de données incomplètes |
| **Verrou** (*lock*) | Deux exécutions ne peuvent pas se marcher dessus | Un fichier `pipeline.lock` ; si une exécution dure plus d'une heure, la suivante est sautée |
| **Journalisation** (*logging*) | Chaque exécution laisse une trace, avec date et niveau | `logs/pipeline.log`, avec l'heure en UTC, pour la comparer directement à la fenêtre |
| **Codes de sortie** | Le programme indique s'il s'est bien terminé (0) ou mal (1) | Le Planificateur de tâches affiche ce code comme résultat de la dernière exécution |
| **Qualité des données** | Ne pas écarter de données en silence | Les événements sans `id` sont comptés et signalés dans le journal |
| **Réutiliser, pas copier** | Une seule version de chaque logique | La pipeline **importe** les scripts du benchmark (`import extract_csv`...) au lieu de copier leur code |
| **Protection** | Impossible de casser l'essentiel par erreur | La pipeline refuse de toucher à la base `gharchive` du benchmark |

### Les scripts de cette étape

| Script | Ce qu'il fait maintenant | Changements de cette étape |
|---|---|---|
| **`pipeline.py`** (nouveau) | Coordonne toute la pipeline : fenêtre, téléchargements, extraction, chargements, journal | Nouveau. [Copie annotée](pipeline.py) |
| `download_gharchive.py` | Télécharge des heures de GH Archive | Nouvelle fonction `fetch_gz()` : télécharge sans décompresser, avec nouvelles tentatives, écriture atomique et avertissement clair si l'heure n'existe pas. Par défaut, elle fait la même chose qu'avant. [Copie annotée](download_gharchive.py) |
| `extract_csv.py` | Crée les trois CSV | Accepte **plusieurs fichiers**, y compris des `.json.gz` non décompressés ; écarte et compte les événements sans `id` ; l'écriture des CSV passe dans une fonction (`write_all()`) que la pipeline réutilise. [Copie annotée](extract_csv.py) |
| `load_postgres.py` | Charge les CSV dans PostgreSQL | Nouvelle option `--database` (par défaut, `gharchive`). [Copie annotée](load_postgres.py) |
| `load_neo4j.py` | Charge les CSV dans Neo4j | Nouvelle option `--database` (par défaut, `gharchive`). [Copie annotée](load_neo4j.py) |

**Le benchmark n'a pas changé :** on a vérifié que `extract_csv.py`
produit des CSV du benchmark **identiques octet par octet** à ceux
d'avant, et les chargements utilisent toujours `gharchive` par défaut.

**Comment fonctionne `import` entre nos scripts :** chaque fichier `.py`
est aussi un **module** qu'un autre script peut importer. L'importer charge
ses fonctions, mais n'exécute **pas** son `main()`, grâce à la protection
`if __name__ == "__main__":` qu'ils ont tous. Ainsi, `pipeline.py` peut
appeler `extract_csv.extract()` ou `load_postgres.load()` comme si
c'étaient les siennes.

### Comment l'exécuter

Avec PostgreSQL et Neo4j en marche :

```bash
./run.sh scripts/pipeline.py --dry-run    # affiche la fenêtre et ce qu'elle téléchargerait ; ne change rien
./run.sh scripts/pipeline.py              # l'exécution réelle
```

Options (toutes ont une valeur par défaut) :

| Option | Par défaut | À quoi elle sert |
|---|---|---|
| `--window-hours` | 24 | Taille de la fenêtre (par exemple, 6 pour un test rapide) |
| `--lag-hours` | 24 | Combien de temps en arrière se termine la fenêtre |
| `--database` | `gharchive24h` | Quelle base reconstruire des deux côtés (jamais `gharchive`) |
| `--dry-run` | — | Seulement montrer le plan |

### La première exécution réelle : un problème de qualité des données

La première exécution a téléchargé les 24 heures (environ 240 Mo) en **28
secondes**, mais a échoué à l'extraction :

```
KeyError: 'id'
    remember_latest(repos, repo["id"], ...)
```

Autrement dit : un événement avait un `repo` **sans la clé `id`**. En
cherchant dans les données : **2 événements sur 1 250 059** avaient
`"repo": {}`, un dépôt complètement vide. Les deux étaient des
`ForkEvent` ; probablement des forks de dépôts supprimés ou passés en privé
par la suite, dont GH Archive n'a pas pu enregistrer les données. Dans
l'heure du benchmark (69 429 événements), il n'y en avait aucun.

**Leçon :** un cas rare qui n'apparaît pas dans un petit échantillon
apparaît quand on traite des données réelles et abondantes. C'est pour cela
qu'on teste les pipelines avec des données réelles.

**Solution :** l'extraction **écarte les événements sans `id` d'acteur ou
de dépôt** (sans `id`, on ne peut créer ni le nœud ni la connexion), mais
**les compte et le signale**, et l'avertissement reste dans le journal :

```
WARNING  Skipped 2 event(s) without an actor or repo id
```

### Résultat de la première exécution complète

`Status: SUCCESS` en **160 secondes** au total, et les **six vérifications
à OK** :

| Étape | Temps |
|---|---|
| Téléchargement (les 24 heures étaient déjà là) | 0,0 s (la première fois : 28 s) |
| Extraction de 1 250 059 événements | 25,3 s |
| Chargement dans PostgreSQL | 31,5 s |
| Chargement dans Neo4j | 90,0 s |

**Les 24 heures face à l'heure du benchmark :**

| | Heure du benchmark (27/08, 15:00) | 24 heures (20/10 12:00 → 21/10 12:00) |
|---|---|---|
| Événements | 69 429 | **1 250 059** |
| Événements de bots écartés | 1 970 (**2,8 %**) | 297 733 (**23,8 %**) |
| Événements sans `id` écartés | 0 | 2 |
| Acteurs | 14 515 | **362 730** |
| Dépôts | 14 995 | **406 603** |
| Connexions | 15 053 | **424 098** |
| Nœuds dans Neo4j | 29 510 | **769 333** |

**Ce que disent ces chiffres :**

- **Les bots pèsent beaucoup plus sur ces 24 heures :** presque un quart
  des événements, contre 2,8 % dans l'heure du benchmark. Une seule heure
  choisie à la main peut donner une image trompeuse : c'est justement la
  raison d'être de cette pipeline.
- **Le volume est environ 26 fois plus grand :** utile pour l'axe
  « volume de données » de la question de recherche.
- **Il y a toujours à peine plus d'une connexion par acteur** (424 098 pour
  362 730 acteurs) : le graphe reste très fragmenté, même s'il y aura plus
  de dépôts partagés que sur une heure. On pourra le mesurer avec
  `summarize_data.py`.

**À propos des temps de chargement** (qui, comme ceux du benchmark, sont
indicatifs et ne sont pas des résultats du benchmark) :

- Dans PostgreSQL, `actor_repo` a pris **27 secondes**, contre 1 seconde
  pour `actor` et `repo`. C'est attendu : pour chaque ligne, PostgreSQL
  vérifie les deux **clés étrangères** (que l'acteur et le dépôt existent)
  et met à jour **deux index**.
- Dans Neo4j, créer les arêtes (45 s) est le plus lent, car chaque arête
  **cherche** d'abord ses deux nœuds.

**Un message qui n'est pas une erreur :** pendant cette exécution, une
longue ligne de Neo4j est apparue à l'écran, `Received notification from
DBMS server ... has caught up`, juste après la création de la base
`gharchive24h`. C'est un avis **informatif** du driver : la nouvelle base
est prête. Pour ne pas encombrer le journal, la pipeline n'enregistre
désormais que les avertissements et les erreurs du driver de Neo4j.

### Voir les données de `gharchive24h`

- **pgAdmin 4 :** dans **Databases**, `gharchive24h` apparaît à côté de
  `gharchive` (sinon, clic droit → **Refresh**). Les tables sont dans
  **gharchive24h** → **Schemas** → **public** → **Tables**.
- **Neo4j Desktop (Query) :** dans le sélecteur **Database**, choisissez
  **`gharchive24h`** (ou `:use gharchive24h`). Le panneau devrait afficher
  **Nodes (769,333)** et **Relationships (424,098)**. Avec autant de nœuds,
  il est encore plus important d'utiliser `LIMIT` pour dessiner.
- **Le journal :** `logs/pipeline.log` garde toutes les exécutions, et
  `data/live/current_window.txt` la dernière fenêtre chargée avec succès.

### Ce qui reste à faire

1. **La planifier toutes les heures** dans le Planificateur de tâches de
   Windows.
2. **Qu'elle fonctionne sans que le portable soit allumé.** Il faudrait
   déplacer la pipeline et les deux bases `gharchive24h` vers un endroit
   toujours allumé :

   | Option | Ce que c'est | Coût | À prendre en compte |
   |---|---|---|---|
   | Serveur dans le cloud | Une machine Linux toujours allumée, avec PostgreSQL, Neo4j et la pipeline planifiée avec cron | Gratuit (Oracle Cloud *Always Free*) ou environ 5 €/mois | Il faut l'entretenir et le sécuriser ; c'est ce qui ressemble le plus à un vrai travail |
   | GitHub Actions + bases dans le cloud | GitHub exécute la pipeline toutes les heures ; PostgreSQL sur Neon ou Supabase | En grande partie gratuit | Neo4j AuraDB Free accepte environ 200 000 nœuds, et ces 24 heures en ont **769 333** : ce n'est pas suffisant |
   | Rester sur le portable | Le Planificateur de tâches | Gratuit | Ne fonctionne que si le portable est allumé et Neo4j Desktop ouvert |

   Le benchmark resterait sur le portable dans tous les cas, car pour
   mesurer des temps, il vaut mieux une machine contrôlée et sans réseau
   entre les deux.
3. **Une amélioration possible : la bascule *blue-green*.** Actuellement,
   pendant la reconstruction, PostgreSQL affiche les données précédentes
   jusqu'à la fin (car le chargement est une seule transaction), mais Neo4j
   apparaît à moitié rempli pendant une minute et demie. Dans les systèmes
   réels, on charge dans une nouvelle base et, une fois terminé, on bascule
   de l'une à l'autre d'un seul coup.
