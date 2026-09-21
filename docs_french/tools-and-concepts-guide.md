# Guide des outils et des concepts : IA, Claude, VS Code, Python, et les fondamentaux qui les sous-tendent

Ce guide existe à des fins d'apprentissage : une explication approfondie et
partant des principes de base, des outils utilisés par ce projet (Claude,
VS Code, Python) et des concepts d'informatique qui se cachent derrière,
rédigée de façon à ce que vous puissiez plus tard expliquer n'importe
lequel de ces sujets à quelqu'un d'autre avec vos propres mots. Il est
destiné à être lu aux côtés de
[project-notes.md](project-notes.md) (le déroulement du travail et le
pourquoi) et de [gh-archive-guide.md](gh-archive-guide.md) (les
spécificités du jeu de données).

---

## Partie 1 — Intelligence artificielle et Claude

### 1.1 Qu'est-ce que l'intelligence artificielle (IA) ?

L'**intelligence artificielle** est le domaine général de la construction
de systèmes informatiques capables d'accomplir des tâches qui demandent
normalement une intelligence humaine : comprendre le langage, reconnaître
des images, prendre des décisions, résoudre des problèmes, apprendre de
l'expérience. « IA » est un terme générique très large, pas une seule
technologie — il couvre tout, depuis un simple programme d'échecs à
règles codées en dur, jusqu'aux grands modèles de langage (comme Claude)
qui rédigent et tiennent des conversations.

Une façon utile de se représenter le domaine est un ensemble de cercles
imbriqués, chacun étant une technique plus spécifique à l'intérieur du
précédent :

```
Intelligence Artificielle (IA)
  └── Machine Learning (apprentissage automatique, ML)
        └── Deep Learning (apprentissage profond)
              └── Grands modèles de langage (LLM)  <- Claude se trouve ici
```

- **Intelligence artificielle** — l'objectif le plus large : des machines
  qui se comportent intelligemment, par n'importe quelle méthode (règles,
  recherche, statistiques, apprentissage).
- **Machine Learning (ML)** — une *approche* spécifique de l'IA : au lieu
  qu'un développeur écrive des règles explicites pour chaque situation
  (« si l'e-mail contient 'argent gratuit', le marquer comme spam »), le
  système reçoit de nombreux exemples (des milliers d'e-mails déjà
  étiquetés spam ou non-spam) et apprend lui-même le schéma. Le programme
  qui en résulte s'appelle un **modèle**.
- **Deep Learning (apprentissage profond)** — une famille de techniques
  de ML basées sur des **réseaux de neurones** : des structures
  mathématiques en couches, vaguement inspirées de la façon dont les
  neurones se connectent dans un cerveau. « Profond » fait référence au
  fait d'avoir de nombreuses couches empilées les unes sur les autres. Le
  deep learning est ce qui a rendu praticables la reconnaissance d'image,
  la reconnaissance vocale, et les modèles de langage modernes.
- **Grands modèles de langage (LLM)** — des modèles de deep learning
  entraînés sur d'énormes quantités de texte, dont la compétence centrale
  est de prédire quel texte vient ensuite, étant donné le texte déjà
  écrit. Cette seule compétence — « prédire le prochain morceau de texte »
  — s'avère assez puissante, à une échelle suffisamment grande, pour
  produire quelque chose capable de répondre à des questions, d'écrire du
  code, de raisonner sur des problèmes, et de tenir une conversation.
  Claude est un LLM.

### 1.2 Entraînement (training) vs. inférence — deux phases très différentes

- L'**entraînement** (*training*) est le processus (extrêmement coûteux,
  effectué une fois par Anthropic sur d'énormes clusters de calcul) qui
  consiste à montrer au modèle d'énormes quantités de texte et à ajuster
  des millions/milliards de nombres internes (appelés **paramètres** ou
  **poids**, *weights*) pour que ses prédictions s'améliorent de plus en
  plus. C'est là que le modèle « apprend ».
- L'**inférence** (*inference*) est ce qui se produit à chaque fois que
  vous *utilisez* réellement le modèle déjà entraîné — comme cette
  conversation. Aucun apprentissage n'a lieu pendant l'inférence au sens
  habituel ; les poids du modèle sont fixes, et il ne fait qu'exécuter sa
  fonction mathématique (très grande) fixe sur votre entrée pour produire
  une sortie. Chaque message que vous envoyez à Claude est une exécution
  d'inférence, pas un nouveau cycle d'entraînement.

### 1.3 Qu'est-ce qu'un « modèle », un « prompt », et un « token » ?

- **Modèle** — le réseau de neurones entraîné lui-même : un ensemble
  énorme et fixe de nombres (les poids) plus le code qui les exécute.
  « Claude » désigne une famille de tels modèles (il y a eu plusieurs
  générations/tailles).
- **Prompt** — le texte que vous fournissez en entrée au modèle. Dans une
  conversation, le « prompt » finit par inclure effectivement tout
  l'historique de la conversation à chaque fois, ce qui explique pourquoi
  un modèle peut faire référence à quelque chose dit plus tôt.
- **Token** — le modèle ne traite pas le texte caractère par caractère ni
  mot par mot ; il découpe le texte en morceaux appelés tokens (souvent
  proches de la taille d'un mot, parfois un mot entier, parfois un
  fragment de mot, ou un simple signe de ponctuation). Les « tokens »
  sont l'unité que le modèle prédit réellement un par un en générant une
  réponse, et l'unité utilisée pour mesurer combien de texte tient dans
  la **fenêtre de contexte** du modèle (le montant maximal de
  conversation/texte antérieur que le modèle peut « voir » à la fois). (Ne
  confondez pas ceci avec un *jeton d'accès* ou *token API*, un sens
  totalement différent, lié à la sécurité, du mot « token » utilisé pour
  l'authentification — voir §5.10.)

### 1.4 Qu'est-ce que Claude, précisément ?

**Claude** est la famille de grands modèles de langage construits par
**Anthropic**, une entreprise centrée sur la sécurité de l'IA. On accède
à Claude de plusieurs façons différentes, ce qui compte pour comprendre ce
qui se passe réellement dans ce projet :

- **claude.ai** — un site web/une application de chat, dans l'esprit
  d'une application de messagerie, où vous tapez des messages et Claude
  répond par du texte.
- **L'API Claude** — un moyen pour les *développeurs* d'envoyer des
  prompts à Claude de façon programmatique depuis leur propre code/leurs
  propres applications, plutôt que via un site de chat. C'est ainsi que
  les entreprises intègrent Claude dans leurs propres produits.
- **Claude Code** — un outil en ligne de commande *agentique* (et, tel
  qu'utilisé dans ce projet, une extension VS Code construite par-dessus)
  qui ne se contente pas de discuter avec vous en texte brut — il peut
  lire et écrire de vrais fichiers sur votre ordinateur, exécuter de
  vraies commandes de terminal, parcourir votre code, etc., afin
  d'accomplir réellement des tâches d'ingénierie logicielle. C'est ce qui
  a écrit et exécuté chaque script du dossier `scripts/` de ce projet.

### 1.5 « Agentique » — ce qui différencie Claude Code d'un simple chatbot

Une IA de chat classique prend votre message et renvoie une réponse
textuelle — elle n'a aucun moyen d'*agir* réellement dans le monde. Un
**agent** (dans ce sens) est un système d'IA auquel on a donné accès à des
**outils** (*tools*) — des actions concrètes qu'il est autorisé à
effectuer, comme « lire ce fichier », « exécuter cette commande shell »,
« chercher ce texte dans tout le projet » — et qui peut décider, étape
par étape, quel outil utiliser ensuite en fonction de ce qu'il apprend du
résultat du précédent. « Agentique » décrit cette boucle
observer → décider → agir → observer le résultat → décider à nouveau.
Chaque fois qu'une commande a effectivement été exécutée sur ce dépôt
dans ce projet (télécharger des données, exécuter `peek_data.py`, modifier
un fichier `.md`), c'était Claude Code utilisant un outil dans le cadre de
cette boucle agentique — pas seulement décrire ce qu'il faudrait faire,
mais le faire réellement.

---

## Partie 2 — Les IDE, VS Code, et les extensions

### 2.1 Qu'est-ce qu'un IDE ?

**IDE** signifie **Integrated Development Environment** (environnement de
développement intégré). C'est une seule application qui regroupe les
outils dont un programmeur a besoin, au lieu d'utiliser des programmes
séparés et déconnectés pour chacun :

- un **éditeur de code** (pour écrire et lire du code source, généralement
  avec une coloration syntaxique — colorer le code selon son rôle
  grammatical — et l'autocomplétion)
- un **terminal** (une ligne de commande textuelle, voir §5.8) intégré
  directement
- des **outils de débogage** (exécuter le code pas à pas, inspecter les
  variables, pour trouver des bugs)
- une **intégration du contrôle de version** (git — voir
  [git-commands-guide.md](git-commands-guide.md) — intégré, plutôt que de
  nécessiter un programme séparé)
- souvent, des **outils de build/compilation**, la gestion de
  projets/fichiers, et des systèmes d'extensions

Le mot « Intégré » est la partie clé : tout cela vit au même endroit, donc
vous ne passez pas constamment d'un éditeur de texte à une fenêtre de
terminal séparée, puis à un outil git séparé. D'autres IDE bien connus
incluent PyCharm (orienté Python), IntelliJ IDEA (orienté Java), et Xcode
(plateformes Apple).

Un IDE est une étape au-dessus d'un simple **éditeur de texte** (comme le
Bloc-notes, ou même un éditeur de code plus simple sans fonctionnalités
d'IDE) — un simple éditeur de texte vous laisse seulement taper et
enregistrer du texte, sans aucun des outils intégrés ci-dessus.

### 2.2 Qu'est-ce que VS Code ?

**VS Code** (Visual Studio Code) est un éditeur de code de type IDE,
gratuit et populaire, créé par Microsoft. Malgré le nom similaire, c'est
un *produit différent* de « Visual Studio » (un IDE beaucoup plus ancien,
plus lourd, centré sur Windows, surtout pour C#/.NET) — VS Code est plus
léger, multiplateforme (fonctionne de la même façon sur Windows, macOS et
Linux), et son cœur est open source.

Les propriétés clés qui expliquent pourquoi il est devenu si largement
utilisé :

- **Léger mais puissant** — démarre rapidement, ne demande pas beaucoup
  de ressources à l'ordinateur, et pourtant dispose d'un vrai débogueur,
  d'une intégration git, et d'un terminal intégré.
- **Multiplateforme** — exactement le même éditeur, les mêmes raccourcis,
  les mêmes extensions, que vous soyez sous Windows, macOS, ou Linux.
- **Extensible** — voir §2.3. Presque chaque fonctionnalité spécialisée
  (le support de Python, cette intégration Claude elle-même, etc.) est
  ajoutée via des extensions plutôt que d'être intégrée en dur de façon
  permanente au programme de base.
- **Construit sur Electron** — un framework qui permet aux développeurs de
  construire des applications de bureau en utilisant des technologies web
  (le même HTML/CSS/JavaScript utilisé pour construire des sites web).
  C'est *pourquoi* VS Code peut avoir le même aspect et la même
  sensation sur chaque système d'exploitation, et pourquoi son interface
  peut être personnalisée en profondeur — c'est fondamentalement une
  application spécialisée, ressemblant à une page web, qui s'exécute dans
  sa propre fenêtre à la place d'un onglet de navigateur.

### 2.3 Qu'est-ce qu'une « extension » ?

Une **extension** (aussi appelée plugin ou module complémentaire, selon le
logiciel) est un morceau de logiciel séparé et plus petit qui se branche
sur une application « hôte » plus grande pour lui ajouter une capacité
spécifique, sans que les développeurs d'origine de l'application hôte
aient dû construire eux-mêmes cette capacité. C'est un schéma logiciel
extrêmement courant, pas propre à VS Code — les navigateurs web ont des
extensions (bloqueurs de publicité, gestionnaires de mots de passe), et
beaucoup d'IDE en ont aussi.

VS Code a été délibérément conçu autour de cette idée : son cœur ne fait
que le strict minimum (ouvrir des fichiers, éditer du texte, afficher une
arborescence de fichiers), et pratiquement tout le reste — le support
complet du langage Python, les correcteurs orthographiques, les thèmes,
les linters, les assistants de codage par IA — est fourni sous forme
d'extension, installée depuis la **marketplace d'extensions** publique de
Microsoft. Cela garde le programme de base petit et rapide pour les
personnes qui n'ont pas besoin de chaque fonctionnalité, tout en lui
permettant de faire presque n'importe quoi pour les personnes qui
installent les extensions qu'elles souhaitent.

### 2.4 Comment Claude fonctionne-t-il *à l'intérieur* de VS Code, précisément ?

La configuration de ce projet est un exemple concret d'extension en
action : l'agent Claude Code (§1.5) est disponible comme **extension VS
Code**. Une fois installée, elle ajoute un panneau/une interface
spécifique à Claude directement à l'intérieur de la fenêtre de VS Code,
donc au lieu de basculer vers une fenêtre de terminal séparée pour
exécuter Claude Code comme un programme en ligne de commande autonome,
vous interagissez avec lui juste à côté des fichiers qu'il modifie — et
il peut voir du contexte spécifique à l'IDE, comme quel fichier vous avez
actuellement ouvert (vous avez probablement remarqué des messages dans ce
projet notant « The user opened the file... »). Sous le capot,
l'extension est toujours le même outil agentique décrit en §1.5 — lisant
et écrivant des fichiers, exécutant des commandes de terminal —
l'extension est simplement la « porte d'entrée » intégrée à VS Code vers
cet outil, au lieu d'une fenêtre de terminal séparée.

---

## Partie 3 — Python et les concepts de langage de programmation

### 3.1 Qu'est-ce que Python ?

**Python** est un langage de programmation de haut niveau et à usage
général, créé par Guido van Rossum et publié pour la première fois en
1991. Chaque script du dossier `scripts/` de ce projet est écrit en
Python.

Ce que signifient précisément « haut niveau » et « à usage général » :

- **Haut niveau** — le code Python se lit presque comme de l'anglais/des
  mathématiques ordinaires, et gère automatiquement beaucoup de détails
  de bas niveau (la gestion de la mémoire, par exemple) pour que le
  programmeur n'ait pas à y penser. C'est l'opposé d'un **langage de bas
  niveau** (comme le C ou l'assembleur), qui vous donne un contrôle
  explicite et fin sur le matériel de l'ordinateur, au prix de
  beaucoup plus de code et de complexité pour la même tâche.
- **À usage général** — il n'est pas construit pour une seule tâche
  étroite (contrairement, par exemple, à un langage conçu uniquement pour
  styliser des pages web). Python est utilisé pour les backends web, la
  data science, l'automatisation/les scripts (comme les scripts de ce
  projet), l'IA/le ML, le calcul scientifique, et plus encore.

### 3.2 Pourquoi Python est (selon de nombreuses mesures) le langage le plus utilisé aujourd'hui

Quelques raisons concrètes et qui se renforcent mutuellement, plutôt que
juste « il est populaire » :

1. **La lisibilité dès la conception** — le créateur de Python a
   délibérément optimisé la syntaxe du langage pour être facile à lire,
   allant jusqu'à imposer une indentation cohérente comme partie
   intégrante de la grammaire réelle du langage (la plupart des langages
   traitent l'indentation comme une simple préférence de style ; Python
   l'exige).
2. **Un immense écosystème de bibliothèques déjà construites** — pour
   presque n'importe quelle tâche (télécharger un fichier, analyser du
   JSON, construire un réseau de neurones), quelqu'un a presque
   certainement déjà publié une bibliothèque Python bien testée pour
   cela (voir §3.7), donc on part rarement de zéro.
3. **Une courbe d'apprentissage douce, un plafond élevé** — vraiment
   facile à prendre en main comme premier langage, mais assez puissant
   pour être le langage dominant dans la recherche et les systèmes de
   production en IA/ML aujourd'hui.
4. **Interprété, donc rapide à itérer** — voir §3.3 ; vous pouvez exécuter
   un script et voir immédiatement le résultat, sans étape de
   « compilation » séparée et lente.

### 3.3 Langages compilés vs. interprétés

C'est une distinction fondamentale dans la façon dont le code écrit par un
humain est réellement transformé en quelque chose que le processeur de
l'ordinateur peut exécuter :

- **Langages compilés** (par ex. C, C++, Rust, Go) — avant de pouvoir
  exécuter le programme, un outil séparé appelé **compilateur** traduit
  tout le code source en **code machine** (des instructions brutes que le
  processeur comprend directement) à l'avance, produisant un fichier
  exécutable. Cette étape supplémentaire (« compiler » ou « builder »)
  peut prendre un vrai temps, mais le programme résultant tend alors à
  s'exécuter très vite, puisque le travail de traduction est déjà fait.
- **Langages interprétés** (par ex. Python, JavaScript, Ruby) — il n'y a
  pas d'étape séparée de compilation vers du code machine que vous
  exécutez vous-même. À la place, un programme **interpréteur** (pour
  Python, c'est littéralement ce qui est invoqué quand vous tapez
  `python scripts/peek_data.py`) lit et exécute le code source
  directement, le traduisant et l'exécutant à la volée, ligne par ligne,
  à chaque exécution du programme. Cela rend la boucle
  écrire → exécuter → voir le résultat plus rapide (pas d'attente d'une
  étape de build), au prix d'une certaine vitesse d'exécution brute par
  rapport à un langage compilé.

(En réalité, l'interpréteur de Python compile discrètement le code vers
une forme intermédiaire appelée **bytecode** en premier, mise en cache
dans ces fichiers `__pycache__/*.pyc` que vous avez peut-être remarqué
être générés localement — mais ce bytecode n'est toujours pas du code
machine, et il est toujours exécuté par l'interpréteur Python plutôt que
directement par le processeur, donc Python reste correctement décrit
comme interprété du point de vue de l'utilisateur.)

### 3.4 Langages à typage statique vs. dynamique

Un **type** est la *sorte* de valeur qu'est une chose — un nombre entier
(`int`), du texte (`str`), une liste, etc. (vous avez déjà vu ce concept
directement dans les scripts de ce projet, par ex. `Counter[str]`,
`type=Path` dans `argparse`).

- Les **langages à typage statique** (par ex. Java, C, Rust) exigent que
  vous déclariez le type d'une variable dès le départ, et le compilateur
  vérifie — avant même que le programme s'exécute — que vous n'essayez
  jamais, par exemple, d'ajouter un nombre à un morceau de texte.
- Les **langages à typage dynamique** (par ex. Python, JavaScript)
  déterminent automatiquement le type d'une variable au moment où le code
  s'exécute réellement, et le même nom de variable peut même contenir un
  type de valeur différent à différents moments d'un programme. C'est
  plus flexible et plus rapide à écrire, au prix de certaines erreurs qui
  n'apparaissent que lorsque cette ligne de code précise s'exécute
  finalement, au lieu d'être détectées plus tôt.

Python est à typage dynamique par défaut, mais prend en charge des
**annotations de type** (*type hints*) optionnelles (comme
`def peek(file_path: Path, num_lines: int) -> None:` dans le
`peek_data.py` de ce projet lui-même) qui ne changent pas la façon dont
le code s'exécute, mais permettent aux outils/éditeurs (et aux lecteurs
humains) de repérer des erreurs de type avant d'exécuter le code, et
servent de documentation intégrée de ce qu'une fonction attend.

### 3.5 Qu'est-ce que la programmation orientée objet (POO) ?

La **programmation orientée objet** (POO, ou OOP en anglais) est une
façon d'organiser le code autour d'**objets** — des ensembles qui
combinent des données et les actions qui opèrent sur ces données en une
seule unité — plutôt qu'autour d'une simple suite d'instructions. Le
vocabulaire central :

- **Classe** (*class*) — un plan/modèle qui définit quel genre de données
  un objet de ce type contient, et quelles actions (méthodes) il peut
  effectuer. Pensez-y comme à un emporte-pièce.
- **Objet** (ou **instance**) — une chose réelle fabriquée à partir de ce
  plan. Si `Actor` était une classe, `github-actions[bot]` en serait une
  *instance*. Pensez-y comme à un biscuit réel découpé avec
  l'emporte-pièce.
- **Attribut** (ou propriété/champ) — une donnée stockée sur un objet, par
  ex. un objet `Actor` pourrait avoir un attribut `.login`.
- **Méthode** — une fonction qui appartient à une classe, décrivant
  quelque chose que les objets de cette classe peuvent *faire*, par ex.
  un objet `Actor` pourrait avoir une méthode `.push(repo)`.
- **Encapsulation** — regrouper les données d'un objet avec les méthodes
  qui opèrent dessus, et cacher ses détails internes au reste du
  programme afin que le reste du code interagisse avec lui via une
  interface propre.
- **Héritage** (*inheritance*) — permettre à une classe d'être définie
  comme une version plus spécifique d'une autre (par ex. une classe `Bot`
  pourrait *hériter* de `Actor`, récupérant automatiquement tout ce que
  possède `Actor`, plus ses propres ajouts). Vous avez en fait déjà vu
  l'héritage utilisé directement dans le code de ce projet :
  `Counter[str]` dans `summarize_data.py` / `profile_schema.py` est une
  classe qui **hérite** de la classe `dict` intégrée à Python, ce qui
  explique pourquoi elle prend en charge les fonctionnalités normales
  d'un dict (comme `len()` et les recherches par clé) tout en ajoutant
  son propre comportement supplémentaire (incrémentation automatique des
  clés manquantes, `.most_common()`).
- **Polymorphisme** — différentes classes qui répondent au « même » appel
  de méthode chacune à sa manière appropriée (par ex. plusieurs classes
  différentes pourraient chacune définir leur propre méthode
  `.describe()` qui se comporte différemment selon la classe, mais
  toutes peuvent être appelées de la même façon depuis un code externe
  qui n'a pas besoin de savoir à quelle classe exacte il a affaire).

**Une remarque honnête et utile pour votre propre apprentissage :** aucun
des quatre scripts Python écrits pour ce projet jusqu'à présent
(`download_gharchive.py`, `peek_data.py`, `summarize_data.py`,
`profile_schema.py`) ne définit en réalité la moindre classe — ils sont
écrits sous forme de simples fonctions opérant sur des types intégrés
ordinaires (`dict`, `list`, `str`, `Counter`). C'était un choix
délibéré et raisonnable pour des scripts de cette taille et de cet
objectif (voir §3.6) — pas un signe que la POO serait évitée parce
qu'elle serait « fausse ». Si ce projet évolue vers quelque chose avec de
vrais concepts persistants à modéliser — un `Actor`, un `Repo`, un `Node`
de graphe — c'est généralement le moment où introduire de véritables
classes commence à devenir rentable.

### 3.6 Les autres paradigmes de programmation (la POO n'est qu'une option parmi d'autres)

Un **paradigme** est un style/une philosophie général pour structurer le
code. La POO en est un ; voici les autres à connaître absolument :

- **Programmation procédurale** — du code organisé comme une suite
  directe d'instructions et d'appels de fonctions qui opèrent sur des
  données passées entre elles, sans regrouper données et comportement
  dans des objets. C'est en fait le style dans lequel les scripts de ce
  projet sont écrits jusqu'à présent : de simples fonctions (`peek()`,
  `summarize()`, `profile()`) appelées les unes après les autres depuis
  `main()`, chacune recevant des données en paramètres et renvoyant des
  résultats, sans aucune classe impliquée.
- **Programmation fonctionnelle** (par ex. Haskell, et un style
  utilisable aussi au sein de Python/JavaScript) — du code construit
  autour de l'appel de fonctions pures (des fonctions dont la sortie ne
  dépend que de leur entrée, sans état caché modifié ailleurs) et
  évitant les données mutables autant que possible.
- **Programmation déclarative** — vous décrivez *quel résultat vous
  voulez*, et vous laissez le système sous-jacent déterminer *comment*
  y arriver, plutôt que d'expliciter chaque étape vous-même. SQL (le
  langage de requête de bases de données) en est un exemple classique :
  `SELECT * FROM actors WHERE login = 'octocat'` décrit le résultat
  souhaité ; le moteur de base de données décide comment aller
  réellement le trouver. Cela s'oppose à la **programmation impérative**
  (Python, y compris les scripts de ce projet, est normalement
  impératif), où vous écrivez explicitement le « comment » étape par
  étape.
- Python est réellement un langage **multi-paradigme** — il prend en
  charge les styles procédural, orienté objet, et (dans une bonne
  mesure) fonctionnel, et permet à un projet de choisir celui qui
  convient le mieux à un morceau de code donné, plutôt que d'imposer un
  seul paradigme partout.

### 3.7 Bibliothèque, module, package, et framework — liés mais distincts

Ces quatre mots sont souvent utilisés de façon interchangeable, mais ont
une vraie distinction :

- **Module** — un seul fichier de code Python qui peut être importé et
  réutilisé ailleurs, par ex. les propres `json` et `pathlib` de ce
  projet proviennent des modules intégrés de Python.
- **Bibliothèque** (*library*) — une collection de modules, généralement
  construite et publiée par quelqu'un d'autre, qui fournit une
  fonctionnalité réutilisable pour une catégorie générale de tâche (par
  ex. une bibliothèque pour communiquer avec des bases de données).
  `Counter` dans les scripts de ce projet provient de `collections`, une
  bibliothèque livrée intégrée à Python lui-même (elle fait partie de ce
  qu'on appelle la **bibliothèque standard**, *standard library* — le
  vaste ensemble de bibliothèques livrées automatiquement avec Python,
  sans installation nécessaire).
- **Package** — techniquement, une façon spécifique d'organiser plusieurs
  modules liés ensemble (un dossier avec un fichier `__init__.py`, dans
  le cas de Python) — mais dans la conversation courante, « package » est
  souvent utilisé de façon interchangeable avec « bibliothèque », en
  particulier en parlant d'en installer un (voir §5.6, les gestionnaires
  de paquets).
- **Framework** — un logiciel réutilisable plus grand et plus directif,
  qui ne se contente pas de fournir des outils que *votre* code appelle,
  mais structure en fait toute l'application et appelle *votre* code aux
  endroits où il en a besoin (parfois résumé par « une bibliothèque, vous
  l'appelez ; un framework vous appelle »). Django (pour les applications
  web Python) en est un exemple bien connu. Aucun des scripts de ce
  projet n'utilise de framework — ils sont assez petits pour qu'une
  poignée de modules de la bibliothèque standard suffisent.

---

## Partie 4 — JSON : impression formatée (pretty-printed) vs. JSON Lines

Le jeu de données de ce projet
([gh-archive-guide.md](gh-archive-guide.md)) est livré spécifiquement au
format JSON Lines, ce qui rend cette comparaison directement pertinente,
et pas seulement théorique.

### 4.1 Qu'est-ce que JSON, brièvement pour rappel

**JSON** (JavaScript Object Notation) est un format léger, à base de
texte, pour représenter des données structurées — des objets (comme les
dict Python, avec `{ "clé": valeur }`), des tableaux/listes
(`[valeur, valeur]`), des chaînes, des nombres, des booléens
(`true`/`false`), et `null` — que les humains et les machines peuvent
tous deux lire raisonnablement facilement. Malgré son nom, il est
désormais utilisé par pratiquement tous les langages de programmation, pas
seulement JavaScript, comme moyen universel d'échanger des données
structurées entre programmes, fichiers, et sur internet.

### 4.2 Le JSON « pretty-printed » (formaté pour l'humain)

Le JSON **pretty-printed** (ou « formaté »/« indenté ») est du texte JSON
qui a été mis en page pour la lisibilité humaine : chaque clé a sa propre
ligne, les objets imbriqués sont indentés plus profondément que leur
parent, et l'espacement est cohérent. Exemple — un seul événement,
pretty-printed :

```json
{
  "id": "40123456789",
  "type": "PushEvent",
  "actor": {
    "id": 987654,
    "login": "some-user"
  },
  "repo": {
    "id": 111222,
    "name": "someorg/somerepo"
  },
  "created_at": "2026-08-27T15:03:11Z"
}
```

C'est exactement ainsi que l'exemple « Anatomie d'un événement » de
[gh-archive-guide.md](gh-archive-guide.md) est présenté — délibérément,
puisque le but entier de cette section est qu'un humain lise et comprenne
la forme d'un événement. L'espace blanc (retours à la ligne, indentation)
n'a *aucune* signification pour un programme qui analyse ce texte —
`json.loads()` (voir la copie annotée de `peek_data.py`) analyse le JSON
pretty-printed et le JSON sur une seule ligne exactement de la même
manière, produisant le même dict Python dans les deux cas. Le pretty-print
existe purement pour les humains, pas pour l'analyseur syntaxique
(*parser*).

### 4.3 JSON Lines (JSONL / NDJSON)

**JSON Lines** (parfois appelé **JSONL** ou **NDJSON**, pour
« Newline-Delimited JSON », JSON délimité par des retours à la ligne) est
une convention différente, au niveau du *fichier* : au lieu d'une seule
grande structure JSON, potentiellement pretty-printed, couvrant tout le
fichier, le fichier contient de nombreux objets JSON *séparés et
indépendants*, chacun écrit entièrement sur sa propre ligne unique, sans
virgules ni crochets `[ ]` englobants pour les relier entre eux. C'est
exactement le format utilisé par les dumps horaires de GH Archive — voir
le style compact, sur une seule ligne, du fichier brut si vous regardez
directement `data/2026-08-27-15.json`, par opposition à l'exemple
illustratif délibérément pretty-printed ci-dessus.

### 4.4 Côte à côte : les trois mêmes événements, des deux façons

**JSON pretty-printed, sous forme d'un tableau (CE N'EST PAS comme GH
Archive le stocke) :**

```json
[
  {
    "type": "PushEvent",
    "actor": { "login": "alice" },
    "repo": { "name": "alice/project" }
  },
  {
    "type": "WatchEvent",
    "actor": { "login": "bob" },
    "repo": { "name": "alice/project" }
  },
  {
    "type": "ForkEvent",
    "actor": { "login": "carol" },
    "repo": { "name": "alice/project" }
  }
]
```

**Les trois mêmes événements en JSON Lines (c'est BIEN ainsi que GH
Archive les stocke) :**

```
{"type": "PushEvent", "actor": {"login": "alice"}, "repo": {"name": "alice/project"}}
{"type": "WatchEvent", "actor": {"login": "bob"}, "repo": {"name": "alice/project"}}
{"type": "ForkEvent", "actor": {"login": "carol"}, "repo": {"name": "alice/project"}}
```

### 4.5 Pourquoi JSON Lines est le bon choix pour un jeu de données comme celui-ci

Ce n'est pas un choix de style arbitraire — JSON Lines a de vrais
avantages pratiques pour exactement le genre de données que publie GH
Archive :

1. **Diffusable en flux, un enregistrement à la fois** (*streamable*). Un
   unique tableau JSON pretty-printed contenant 69 429 événements est,
   techniquement, *une seule* valeur JSON — beaucoup d'analyseurs
   syntaxiques doivent lire le fichier *entier* en mémoire avant de
   pouvoir vous donner ne serait-ce que le premier événement, car ils
   doivent trouver le `]` fermant correspondant pour savoir si la
   structure est même valide. JSON Lines peut être lu et traité une
   ligne — un événement — à la fois, ce qui est exactement ce que fait
   chaque script de ce projet (`for line in f:` dans `peek_data.py`,
   `summarize_data.py`, et `profile_schema.py`), sans jamais avoir besoin
   du fichier entier de plus de 47 Mo en mémoire simultanément.
2. **Naturellement extensible en ajout** (*appendable*). Un nouvel
   événement peut être ajouté à un fichier JSON Lines simplement en
   écrivant une ligne de plus à la fin — pas besoin de trouver et de
   réécrire un crochet fermant, ni de se soucier d'une virgule
   manquante/en trop entre les éléments d'un tableau, deux vrais risques
   lors de l'ajout à un tableau JSON pretty-printed.
3. **Une seule ligne défectueuse ne casse pas tout le fichier.** Si une
   ligne est corrompue, toutes les autres lignes restent analysables
   indépendamment ; une seule erreur de syntaxe dans un immense tableau
   JSON pretty-printed peut rendre le fichier *entier* inanalysable,
   puisqu'il s'agit techniquement d'une seule valeur JSON.
4. **Une taille de fichier plus petite.** Pas d'espace blanc
   d'indentation à stocker pour des millions d'enregistrements — cela
   compte à l'échelle de GH Archive (chaque heure, chaque jour, pour
   toujours).

Le compromis est exactement l'inverse du §4.2 : un fichier JSON Lines brut
est nettement plus difficile à lire directement à l'œil nu pour un
*humain* qu'une version pretty-printed, puisque tout est entassé sur des
lignes uniques, souvent très longues — ce qui explique précisément
pourquoi `peek_data.py` et la section « Anatomie d'un événement » de ce
guide existent : pour montrer une *vue* pretty-printed et conviviale pour
l'humain de ce qui est structurellement la même donnée.

---

## Partie 5 — Plus de concepts fondamentaux à connaître

Un ensemble d'autres concepts qui reviennent constamment dès qu'on
travaille avec l'un des outils ci-dessus, regroupés vaguement par thème.

### 5.1 Code source, programme, script, et application

- **Code source** — le texte écrit/lisible par un humain d'un programme,
  avant toute compilation/interprétation.
- **Programme** — le terme général pour un ensemble d'instructions
  exécutées par un ordinateur.
- **Script** — désigne généralement un programme plus petit, souvent à
  usage unique, typiquement exécuté via un langage interprété, destiné à
  automatiser une tâche (exactement ce que sont les quatre fichiers
  `scripts/*.py` de ce projet).
- **Application** (ou « app ») — implique généralement quelque chose de
  plus grand, plus complet, et souvent avec une interface utilisateur,
  destiné à un usage répété et général (VS Code lui-même est une
  application ; `peek_data.py` est un script).

### 5.2 CLI vs. GUI

- **CLI (Command-Line Interface, interface en ligne de commande)** — vous
  interagissez avec le logiciel en tapant des commandes textuelles dans un
  terminal et en lisant une sortie textuelle (par ex. exécuter
  `python scripts/peek_data.py`, ou utiliser des commandes `git`).
- **GUI (Graphical User Interface, interface graphique)** — vous
  interagissez avec le logiciel visuellement, via des fenêtres, des
  boutons, et une souris/un écran tactile (par ex. la fenêtre de
  l'éditeur de VS Code elle-même, ou cliquer sur un site web).
De nombreux outils, y compris la propre chaîne d'outils de ce projet,
proposent les deux : vous pouvez utiliser `git` entièrement depuis la
ligne de commande, ou via le panneau git graphique intégré de VS Code ;
Claude Code lui-même est utilisable comme un pur outil CLI *ou* via le
panneau graphique de l'extension VS Code (§2.4) — le même agent sous-jacent,
deux interfaces différentes vers lui.

### 5.3 Terminal, shell, et ligne de commande

- **Terminal** — la fenêtre/le programme qui vous permet de taper des
  commandes textuelles et de voir une sortie textuelle (ce projet utilise
  Git Bash sous Windows, d'après les notes d'environnement que vous avez
  pu voir).
- **Shell** — le programme réel *à l'intérieur* du terminal qui lit les
  commandes que vous tapez, les interprète, et les exécute (par ex.
  `bash`, ou `cmd`/PowerShell sous Windows). « Terminal » et « shell »
  sont souvent utilisés de façon interchangeable dans la conversation
  courante, mais strictement, le terminal est la fenêtre/l'interface, et
  le shell est le programme s'exécutant à l'intérieur qui fait
  l'interprétation réelle.
- **Ligne de commande** — le terme général pour interagir avec un shell
  en tapant des commandes individuelles (comme `python
  scripts/peek_data.py` ou `git status`).

### 5.4 Dépôt, répertoire de travail, et bases du système de fichiers

- **Dépôt (« repo »)** — comme couvert dans
  [gh-archive-guide.md](gh-archive-guide.md) au sens GitHub, et utilisé
  tout au long de [project-notes.md](project-notes.md) au sens git : un
  dossier dont git suit l'historique (ce dossier `Research` tout entier
  en est un).
- **Répertoire de travail** (ou « répertoire courant ») — le dossier dans
  lequel un terminal ou un programme se « trouve » actuellement, ce qui
  compte car de nombreuses commandes (comme `python
  scripts/peek_data.py`, exécutée en tant que chemin *relatif*) ne
  fonctionnent correctement que si elles sont exécutées depuis le bon
  répertoire de travail — voir l'explication déjà présente dans la
  section « Testing Phase » de [project-notes.md](project-notes.md).
- **Chemin (path)** — l'adresse d'un fichier ou d'un dossier dans le
  système de fichiers, soit **absolu** (le trajet complet depuis tout en
  haut, par ex. `C:\dev\Research\scripts\peek_data.py`), soit **relatif**
  (le trajet depuis l'endroit où vous vous trouvez actuellement, par ex.
  simplement `scripts/peek_data.py` en se trouvant dans `C:\dev\Research`).
  Les scripts de ce projet utilisent le `pathlib.Path` de Python (voir la
  copie annotée de `download_gharchive.py`) spécifiquement pour gérer
  correctement et de façon portable les deux types de chemins, sur tous
  les systèmes d'exploitation.

### 5.5 Structures de données utilisées constamment dans ce projet

- **Chaîne de caractères (`str`)** — du texte.
- **Entier (`int`)** / **Flottant (float)** — des nombres entiers / des
  nombres décimaux.
- **Booléen (`bool`)** — `True` ou `False`.
- **Liste / tableau** — une collection ordonnée de valeurs (Python appelle
  cela une `list` ; JSON appelle l'équivalent un *tableau* (*array*),
  écrit `[ ]`).
- **Dictionnaire / map / table de hachage / objet** — une collection de
  paires `clé : valeur`, permettant de rechercher une valeur par sa clé
  plutôt que par sa position (Python appelle cela un `dict` ; JSON
  appelle l'équivalent un *objet*, écrit `{ }`). Les événements de ce
  projet sont, une fois analysés, exactement cela : des dict Python,
  consultés par clé (`event["type"]`, `event["actor"]["login"]`).
- **`None` / `null`** — l'absence explicite de valeur (Python l'écrit
  `None` ; JSON écrit le même concept `null` — vous avez vu cela
  directement dans la propre sortie de `profile_schema.py` de ce projet,
  par ex.
  `payload.description ... types: str x657, NoneType x633`).

### 5.6 Gestionnaires de paquets et environnements virtuels

- **Gestionnaire de paquets** (*package manager*) — un outil qui
  automatise la recherche, le téléchargement, et l'installation de
  bibliothèques publiées par d'autres personnes (et leurs propres
  dépendances, récursivement), au lieu que vous le fassiez à la main.
  L'outil standard de Python est **pip** ; il télécharge les paquets
  depuis un index public appelé **PyPI** (le Python Package Index). Ce
  projet n'a pas encore eu besoin de pip, puisque chaque import utilisé
  jusqu'ici (`argparse`, `json`, `collections`, `pathlib`) fait partie
  de la bibliothèque standard intégrée à Python — aucune installation
  requise.
- **Environnement virtuel** (*virtual environment*) — une copie isolée et
  autonome d'une installation Python et de ses paquets installés, gardée
  séparée par projet, afin que le Projet A ayant besoin de la version 1
  d'une bibliothèque et le Projet B ayant besoin de la version 2 de la
  même bibliothèque n'entrent pas en conflit l'un avec l'autre sur le
  même ordinateur. Cela vaut la peine de le connaître même si ce projet
  n'en a pas encore eu besoin (précisément parce qu'il n'a utilisé que la
  bibliothèque standard jusqu'ici) — cela devient nécessaire dès qu'un
  projet a besoin de son premier paquet *externe*.

### 5.7 API, HTTP, et URL

- **API (Application Programming Interface, interface de programmation
  applicative)** — au sens large, toute façon définie pour qu'un morceau
  de logiciel communique avec un autre. C'est un terme général — le
  module `json` de Python a une API (les fonctions/le comportement
  qu'il expose pour que d'autre code les appelle) ; Claude a aussi une
  API (§1.4).
- **API web / API HTTP** — le cas spécifique, extrêmement courant, d'une
  API accessible sur internet via **HTTP** (HyperText Transfer Protocol —
  le même protocole sous-jacent que les navigateurs web utilisent pour
  charger des pages web), identifiée par une **URL** (l'adresse web). Le
  `download_gharchive.py` de ce projet en est un exemple concret : il
  fait une requête HTTP vers
  `https://data.gharchive.org/2026-08-27-15.json.gz` — exactement le même
  genre de requête qu'un navigateur fait quand vous visitez une page,
  simplement faite par un script Python plutôt qu'en cliquant sur un
  lien.

### 5.8 Logiciel open source vs. propriétaire

- **Open source** — le code source du logiciel est publiquement
  disponible pour que quiconque puisse le lire, le modifier, et souvent
  le redistribuer, généralement sous une licence spécifique (ce projet
  lui-même utilise la **licence MIT**, enregistrée dans
  [LICENSE](../LICENSE) — l'une des licences open source les plus
  permissives et les plus courantes). Python lui-même, le cœur de VS
  Code, et une grande partie de ce dont dépend ce projet, sont open
  source.
- **Logiciel propriétaire** — le code source est gardé privé par son
  propriétaire ; vous ne pouvez généralement utiliser que le programme
  fini et compilé, sans pouvoir voir ni modifier son fonctionnement
  interne.
Ces catégories ne sont pas strictement opposées en pratique — par ex. le
cœur de l'éditeur VS Code est open source, mais la version officielle
construite par Microsoft regroupe aussi de la télémétrie/du branding
propriétaire par-dessus ce cœur open source.

### 5.9 Syntaxe vs. sémantique

- **Syntaxe** — les *règles* grammaticales de la façon dont le code doit
  être écrit pour être ne serait-ce que valide (par ex. Python exige un
  deux-points `:` avant un bloc indenté, comme dans
  `def peek(file_path: Path, num_lines: int) -> None:`). Une erreur de
  syntaxe signifie que le code n'est même pas structuré d'une façon que
  le langage peut analyser, quel que soit ce qu'il essayait de faire.
- **Sémantique** — le *sens*/comportement réel du code correctement
  écrit. Du code peut être parfaitement valide syntaxiquement et faire
  quand même la mauvaise chose (une « erreur logique » ou « erreur
  sémantique ») — par ex. compter accidentellement `event["repo"]
  ["name"]` alors que vous vouliez compter `event["actor"]["login"]`
  s'exécuterait sans planter, mais produirait une mauvaise réponse.

### 5.10 Une remarque sur le mot « token » (pour éviter de confondre deux sens sans rapport)

Ce mot est réutilisé pour deux concepts réellement différents, tous deux
pertinents pour ce projet :

- Le **token LLM** décrit en §1.3 — un morceau de texte (une partie de la
  façon dont Claude lit et génère du langage).
- Un **jeton d'accès** / **token API** / **identifiant** (*credential*) —
  une chaîne secrète utilisée pour prouver *qui vous êtes* auprès d'un
  service (par ex. ce qui authentifie réellement un `git push` vers
  GitHub, ou un appel à l'API de Claude). Ceux-ci sont sensibles et ne
  doivent jamais être commités dans un dépôt git ni partagés — un sens
  notablement différent du sens LLM ci-dessus, malgré le nom partagé.
