# Comprendre les commandes Git

Ce guide part des principes fondamentaux : ce qu'est réellement Git, comment
un commit passe de votre ordinateur portable à GitHub, et ce que fait
réellement, en coulisses, chacune des commandes que vous avez utilisées
jusqu'à présent (`add`, `commit`, `push`, `pull`, `remote`, et d'autres) — y
compris le véritable problème d'identifiants que vous avez rencontré
aujourd'hui et la façon dont il a été résolu.

## 1. Ce qu'est réellement Git

Git est un **système de contrôle de version** : il prend des instantanés des
fichiers de votre projet au fil du temps, ce qui vous permet de consulter
l'historique, d'annuler des erreurs et — ce qui est crucial pour ce projet —
de synchroniser ces instantanés entre votre ordinateur portable et un
serveur distant (GitHub). Git lui-même s'exécute entièrement sur votre
machine ; GitHub n'est qu'un endroit où vous pouvez *également* stocker une
copie de votre historique Git, afin de le sauvegarder, de le partager, ou de
l'ouvrir depuis un autre ordinateur.

## 2. Le modèle en trois étapes : répertoire de travail, zone de staging, dépôt

C'est le modèle mental le plus important pour comprendre toutes les
commandes ci-dessous. Un fichier de votre projet peut se trouver dans l'un
de trois « emplacements » du point de vue de Git :

```
Working Directory  --git add-->  Staging Area  --git commit-->  Repository (local history)
(your actual files                (files marked                  (permanent snapshots,
 on disk, as you                   ready for the                  each one identified
 edit them)                        next commit)                   by a commit hash)
```

- **Répertoire de travail** (*working directory*) — les fichiers réels sur
  votre disque, exactement tels que vous les voyez actuellement dans VS
  Code. Modifier un fichier ne change que cette étape.
- **Zone de staging** (*staging area*, aussi appelée « l'index ») — une zone
  d'attente pour les modifications dont vous avez décidé qu'elles
  *devraient* faire partie du prochain commit. Vous construisez la zone de
  staging avec `git add`.
- **Dépôt** (*repository*) — l'historique permanent et nommé des instantanés
  (« commits »). `git commit` prend tout ce qui est actuellement staged et
  le scelle en un nouvel instantané permanent dans cet historique.

Pourquoi cette étape de staging supplémentaire, plutôt que de tout commiter
directement ? Elle permet de ne commiter qu'*une partie* de vos
modifications à la fois — par ex. vous avez modifié trois fichiers, mais
seuls deux d'entre eux sont liés à ce que ce commit est censé représenter.
`git add` choisit ce qui est inclus ; `git commit` scelle ce choix.

## 3. `git status` — où en est-on ?

Avant de faire quoi que ce soit d'autre, `git status` vous indique : quels
fichiers sont staged, lesquels sont modifiés mais non staged, et lesquels
sont untracked (nouveaux fichiers que Git ne connaît pas encore). Elle est
en lecture seule — elle ne change rien, donc il est toujours sûr de
l'exécuter, et il vaut la peine de le faire souvent, surtout avant
`add`/`commit`/`push`.

## 4. `git add` — déplacer des modifications vers la zone de staging

```bash
git add .
```

`git add <path>` stage un fichier ou un dossier spécifique. `git add .`
stage *tout* ce qui a changé ou est nouveau dans le répertoire actuel et en
dessous — ce que vous avez exécuté, et c'est tout à fait adapté pour un
petit projet personnel où vous relisez tout vous-même. Sur des projets plus
grands ou partagés, stager des fichiers spécifiques par leur nom est plus
sûr, car `.` peut accidentellement inclure des fichiers que vous ne vouliez
pas commiter.

Cette étape est purement locale — rien ne quitte encore votre machine.

## 5. `git commit` — sceller un instantané

```bash
git commit -m "Exploration stage set up"
```

Prend tout ce qui se trouve actuellement dans la zone de staging et
l'enregistre de façon permanente comme un nouvel instantané dans
l'historique de votre dépôt local, étiqueté avec le message fourni après
`-m`. Chaque commit reçoit un identifiant unique (un « hash ») et conserve
la trace exacte de ce qui a changé et quand. Cela reste entièrement local —
un commit n'existe que sur votre ordinateur portable jusqu'à ce que vous le
poussiez quelque part.

Un bon message de commit indique en un coup d'œil *pourquoi*/*ce qui* a
changé — c'est pourquoi nous avons opté plus tôt pour quelque chose comme
`"Exploration stage set up"`, plutôt que pour quelque chose de vague comme
`"updates"`.

## 6. `git remote` — que veut dire « ailleurs » au juste ?

Un **remote** (dépôt distant) est simplement un surnom enregistré pour une
autre copie du dépôt se trouvant ailleurs — presque toujours une URL
pointant vers un dépôt GitHub (ou similaire). Le surnom par défaut utilisé
par Git est `origin`, mais ce n'est qu'une convention, pas une obligation.

```bash
git remote -v
```

Liste tous les remotes que ce dépôt local connaît, avec leurs URLs, pour les
deux directions `fetch` (téléchargement) et `push` (envoi) — normalement
identiques. C'est une commande en lecture seule, purement informative. C'est
en l'exécutant qu'on a découvert aujourd'hui que `origin` pointait vers
`https://github.com/Winteroc18pedro/graph-vs-relational-traversal.git`.

### `git remote set-url` — changer la cible d'un remote

```bash
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

Modifie l'URL enregistrée sous un surnom de remote existant (`origin`), sans
toucher en rien à votre historique de commits — cela affecte uniquement la
destination des futures commandes `push`/`pull`. Ceci est stocké dans le
fichier local `.git/config` propre à ce dépôt, donc cela n'affecte que *ce*
dépôt, jamais un autre dépôt sur votre machine.

**Pourquoi c'était nécessaire aujourd'hui :** votre machine Windows avait
une connexion GitHub mise en cache dans le Gestionnaire d'identifiants pour
votre compte professionnel Celfocus (`NB30006_celfocus`), et `git push`
utilisait silencieusement cette connexion mise en cache, car l'URL du
remote (`https://github.com/...`) ne précisait pas *quel* compte utiliser
pour s'authentifier. GitHub a correctement refusé le push avec une erreur
403, car ce compte professionnel n'a aucune permission sur votre dépôt
personnel.

Intégrer votre nom d'utilisateur réel directement dans l'URL
(`https://i-was-poisoned@github.com/...`) indique au gestionnaire
d'identifiants de Git de rechercher (et de mettre en cache) les identifiants
sous une clé *distincte*, spécifique à ce nom d'utilisateur, plutôt que de
réutiliser ce qui avait été mis en cache en dernier pour `github.com` seul.
C'est ce qui a permis au `git push` suivant de redemander une connexion pour
le bon compte, sans perturber l'identifiant professionnel mis en cache
utilisé par vos dépôts Celfocus.

## 7. `git push` — envoyer les commits locaux vers un remote

```bash
git push
```

Envoie tous les commits qui existent dans votre dépôt local mais pas encore
dans la copie du remote, pour la branche actuelle. C'est l'étape qui
nécessite réellement une authentification, puisque vous écrivez sur le
serveur de quelqu'un d'autre (GitHub) — c'est pourquoi c'est là que l'erreur
de permission est apparue.

### `git push -u origin main` (alias `--set-upstream`)

```bash
git push -u origin main
```

`-u` (abréviation de `--set-upstream`) fait une chose de plus qu'un push
normal : elle indique à votre branche locale `main` de « suivre » (*track*)
la branche `main` du remote `origin`, en mémorisant cette association. Une
fois cette commande exécutée **une fois**, un simple `git push` ou `git
pull` (sans argument supplémentaire) sait automatiquement quel remote et
quelle branche utiliser, puisque ce lien est désormais mémorisé. Sans cela,
Git vous demanderait de préciser le remote et la branche par leur nom à
chaque fois.

Vous avez besoin de `-u` la *première* fois que vous poussez une branche
locale donnée vers une branche distante donnée ; ensuite, un simple `git
push` suffit.

## 8. `git pull` — rapatrier les commits distants

```bash
git pull
```

L'opération inverse de `git push` : elle récupère tous les commits qui
existent sur le remote mais pas encore dans votre dépôt local, et les
fusionne dans votre branche actuelle. Pas encore utilisée dans ce projet
(puisque vous en êtes le seul contributeur jusqu'à présent et que rien
n'existe sur le remote qui ne soit déjà en local), mais c'est ce que vous
exécuteriez avant de commencer un nouveau travail si vous collaboriez avec
quelqu'un d'autre, ou si vous travailliez depuis une seconde machine, afin
de vous assurer de partir de la dernière version.

## 9. `git clone` — récupérer un dépôt distant pour la première fois

```bash
git clone https://github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

C'est ainsi que la copie locale `C:\dev\Research` a été créée au départ
(comme décrit dans la section « Déroulement du dépôt jusqu'à présent » de
[project-notes.md](project-notes.md)) : elle télécharge l'intégralité de
l'historique d'un dépôt distant et le met en place comme nouveau dépôt
local, en configurant automatiquement `origin` pour qu'il pointe vers l'URL
depuis laquelle vous avez cloné. Vous n'exécutez cela qu'une seule fois,
tout au début — ensuite, `pull`/`push` se chargent de garder les deux
synchronisés.

## 10. Autres commandes utiles à connaître

- **`git log`** — affiche l'historique des commits (message, auteur, date,
  hash) pour la branche actuelle. Ajoutez `--oneline` pour une vue compacte
  d'une ligne par commit.
- **`git diff`** — affiche les modifications exactes, ligne par ligne, qui
  sont staged ou non staged mais pas encore commitées. Utile pour vérifier
  précisément ce que vous vous apprêtez à `add`/`commit` avant de le faire.
- **`git branch`** — liste les branches locales (ce projet n'a utilisé que
  `main` jusqu'à présent) ; sert aussi à en créer de nouvelles (`git branch
  <name>`) lorsque vous voulez travailler sur quelque chose sans affecter
  directement `main`.

## 11. Référence rapide

| Commande | Ce qu'elle fait | Touche le remote ? |
|---|---|---|
| `git status` | Affiche ce qui a changé / est staged | Non |
| `git add .` | Stage toutes les modifications | Non |
| `git commit -m "..."` | Enregistre un instantané localement | Non |
| `git remote -v` | Liste les remotes configurés | Non (lecture seule) |
| `git remote set-url origin <url>` | Change la cible d'un remote | Non |
| `git push` | Envoie les commits locaux | Oui |
| `git push -u origin main` | Envoie + lie les branches locale/distante (première fois seulement) | Oui |
| `git pull` | Télécharge + fusionne les commits distants | Oui |
| `git clone <url>` | Récupère une copie complète d'un dépôt distant (une seule fois) | Oui |
</content>
