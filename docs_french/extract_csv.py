########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/extract_csv.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter.
# Le script réel et « propre » (sans tous ces commentaires) est
# scripts/extract_csv.py.
#
# Ce fichier suppose que vous avez déjà lu les scripts annotés précédents —
# argparse, Path, json, les dict, les ensembles, les boucles, `continue`,
# les f-strings, main() et la garde __name__ ne sont PAS réexpliqués depuis
# zéro ici. Ce fichier se concentre sur ce qui est NOUVEAU dans
# extract_csv.py : écrire des fichiers CSV avec le module csv, utiliser des
# tuples comme éléments d'un ensemble et comme valeurs d'un dict, garder la
# valeur « la plus récente » pendant la lecture, trier pour obtenir une
# sortie reproductible, et créer des dossiers avec Path.mkdir().
#
# NOUVEAUTÉS de cette version (ajoutées pour le pipeline en direct sur 24
# heures, pipeline.py) : il peut lire PLUSIEURS fichiers d'un coup, et il
# lit directement les fichiers compressés .json.gz (sans les décompresser
# d'abord sur le disque) ; il ignore les rares événements sans id d'acteur
# ou de dépôt et les signale avec le module `logging` ; et l'étape
# d'écriture des CSV vit désormais dans sa propre fonction, write_all(),
# pour que pipeline.py puisse la réutiliser. Pour l'heure du benchmark, les
# fichiers CSV produits sont identiques octet pour octet à ceux d'avant.
#
# Son rôle dans le projet : être la SOURCE UNIQUE à partir de laquelle les
# deux bases de données sont chargées. PostgreSQL et Neo4j liront chacune
# ces trois mêmes fichiers, donc elles ne peuvent pas finir par contenir des
# données différentes — une condition indispensable pour un benchmark
# équitable.
########################################################################

"""Extract the benchmark's actor/repo graph from GH Archive files into CSV files.

Reads one or more JSON Lines files (plain .json or compressed .json.gz) once,
skips bot accounts (logins ending in "[bot]"), and writes three CSV files that
both databases are loaded from, so they always hold exactly the same data:

    actors.csv       id, login             one row per actor (most recent login)
    repos.csv        id, name              one row per repo (most recent name)
    actor_repo.csv   actor_id, repo_id     one row per actor-repo pair, no repeats

Usage:
    python scripts/extract_csv.py
    python scripts/extract_csv.py --file data/2026-08-27-15.json --out-dir data/csv
    python scripts/extract_csv.py --file data/live/raw/*.json.gz --out-dir data/live/csv
"""

# ---------------------------------------------------------------------
# import csv
#
# NOUVEAU : le module de la bibliothèque standard pour lire et écrire des
# fichiers CSV (« comma-separated values », valeurs séparées par des
# virgules) : des tableaux en texte brut où chaque ligne est une rangée et
# où des virgules séparent les colonnes, par exemple
#
#     id,login
#     19,brynary
#
# Pourquoi ne pas écrire les virgules nous-mêmes avec f"{a},{b}" ? Parce
# que si une valeur contenait un jour une virgule ou un guillemet, le
# tableau serait cassé. Le module csv gère ces cas (il ajoute des
# guillemets là où c'est nécessaire), et PostgreSQL comme Neo4j lisent sa
# sortie sans problème.
#
# argparse, json, Path : déjà expliqués dans les scripts annotés précédents.
#
# gzip : déjà rencontré dans la copie annotée de download_gharchive.py.
# Ici, il est utilisé différemment : pour LIRE un fichier .json.gz comme
# du texte, en le décompressant à la volée (voir open_text() plus bas).
#
# logging : NOUVEAU — la façon standard de signaler des avertissements et
# d'autres messages. Expliqué là où `log` est créé, juste sous les
# constantes.
#
# from typing import TextIO : NOUVEAU — TextIO ne sert que dans une
# annotation de type. Il signifie « un fichier ouvert dont on lit du
# TEXTE » (par opposition à des octets bruts). Voir open_text() plus bas.
# ---------------------------------------------------------------------
import argparse
import csv
import gzip
import json
import logging
from pathlib import Path
from typing import TextIO

# ---------------------------------------------------------------------
# PROJECT_DIR = Path(__file__).resolve().parent.parent
#
# La même technique que DEFAULT_FILE dans les scripts précédents (voir la
# copie annotée de peek_data.py), enregistrée dans sa propre constante car
# deux valeurs par défaut sont construites à partir d'elle :
#   DEFAULT_FILE     data/2026-08-27-15.json   l'entrée
#   DEFAULT_OUT_DIR  data/csv/                 où vont les CSV
#
# Les CSV vont dans data/ exprès : data/ est déjà dans .gitignore, car tout
# ce qu'il contient peut être régénéré en relançant les scripts.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PROJECT_DIR / "data" / "2026-08-27-15.json"
DEFAULT_OUT_DIR = PROJECT_DIR / "data" / "csv"

# Même règle pour les bots que dans summarize_data.py (voir sa copie
# annotée) : les bots officiels de GitHub ont des logins qui se terminent
# par "[bot]". Le benchmark les exclut car ils servent de plaques
# tournantes artificielles entre des dépôts sans rapport.
BOT_SUFFIX = "[bot]"

# ---------------------------------------------------------------------
# log = logging.getLogger(__name__)
#
# NOUVEAU : un « logger » (journaliseur) — un objet pour signaler des
# messages, une alternative plus souple à print(). getLogger(nom) donne le
# logger portant ce nom ; __name__ est le nom de ce module lui-même (par
# ex. "extract_csv"), donc chaque message est étiqueté avec son origine.
#
# Pourquoi pas simplement print() ? Parce que l'endroit OÙ les messages
# aboutissent est décidé par celui qui exécute le programme, pas par ce
# fichier :
#   - Exécuté seul (python scripts/extract_csv.py), personne n'a
#     configuré logging, et le comportement par défaut de Python est
#     d'afficher à l'écran les avertissements (et ce qui est plus grave).
#     L'avertissement ci-dessous apparaît donc quand même dans le
#     terminal.
#   - Exécuté depuis pipeline.py, qui CONFIGURE logging au démarrage : le
#     même avertissement va alors aussi dans logs/pipeline.log, pour
#     qu'on puisse le lire plus tard même si le pipeline tourne sans
#     surveillance.
# Ce fichier n'a pas besoin de savoir lequel des deux cas se produit.
#
# Les messages ont des niveaux — debug, info, warning, error, critical —
# du moins grave au plus grave. On utilise log.warning(...) plus bas.
# ---------------------------------------------------------------------
log = logging.getLogger(__name__)


def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# ---------------------------------------------------------------------
# def remember_latest(names, key, created_at, name) -> None:
#
# POURQUOI ELLE EXISTE : dans cette heure de données, un utilisateur a
# changé de login (lucky521-png -> peitongshi) et deux dépôts ont été
# renommés. Leur id reste le même, mais le nom change d'un événement à
# l'autre. Chaque id ne doit apparaître qu'UNE SEULE fois dans le CSV, donc
# il faut choisir un nom : le plus récent.
#
# COMMENT : `names` est un dictionnaire dont les clés sont des ids et dont
# les valeurs sont des TUPLES de deux éléments, (created_at, name) :
#
#     names[321725054] = ("2026-08-27T15:35:35Z", "peitongshi")
#
# Un tuple est comme une petite liste qu'on ne peut pas modifier, utilisé
# ici pour garder ensemble deux valeurs liées. names[key][0] est l'heure,
# names[key][1] est le nom.
#
# Le `if` enregistre le nouveau nom quand :
#   key not in names           c'est la première fois qu'on voit cet id, ou
#   created_at >= names[key][0] cet événement est aussi récent, ou plus
#                              récent, que celui qu'on avait enregistré.
#
# Comparer des HEURES SOUS FORME DE TEXTE : created_at est écrit au format
# ISO 8601 ("2026-08-27T15:35:35Z" : année, mois, jour, heure, minute,
# seconde, du plus grand au plus petit, toujours avec le même nombre de
# chiffres). Dans ce format, l'ordre alphabétique EST l'ordre chronologique,
# donc `>=` sur les chaînes fonctionne sans les convertir en dates.
#
# `-> None` : elle ne renvoie rien ; elle modifie le dictionnaire qu'on lui
# a donné. Les dict sont passés « par référence » : la fonction travaille
# sur le même dictionnaire que celui de l'appelant, pas sur une copie.
# ---------------------------------------------------------------------
def remember_latest(names: dict[int, tuple[str, str]], key: int, created_at: str, name: str) -> None:
    # Garder le nom de l'événement le plus récent : logins et noms de dépôts peuvent changer.
    # created_at est du texte ISO 8601, donc comparer les chaînes revient à comparer les heures.
    if key not in names or created_at >= names[key][0]:
        names[key] = (created_at, name)


# ---------------------------------------------------------------------
# def open_text(path) -> TextIO:
#
# NOUVEAU : ouvre un fichier pour y lire du texte, qu'il soit compressé ou
# non.
#
#   path.suffix
#     La DERNIÈRE extension du chemin : pour "2026-08-27-15.json.gz",
#     c'est ".gz" ; pour "2026-08-27-15.json", c'est ".json".
#
#   gzip.open(path, "rt", encoding="utf-8")
#     "rt" = lecture (Read), mode Texte. gzip décompresse les octets au
#     fur et à mesure de la lecture et le mode texte les transforme en
#     chaînes normales, donc l'appelant peut boucler avec `for line in f:`
#     exactement comme avec un fichier ordinaire. Rien n'est décompressé
#     sur le disque : une fenêtre de 24 heures, ce sont 24 fichiers
#     compressés, et les garder compressés économise BEAUCOUP d'espace
#     disque (chaque heure est plusieurs fois plus grosse une fois
#     décompressée).
#
#   open(path, "r", encoding="utf-8")
#     Le cas normal, comme avant, pour un fichier .json déjà décompressé
#     (comme l'heure du benchmark, data/2026-08-27-15.json).
#
# -> TextIO : les deux branches renvoient « un fichier texte ouvert », donc
# la fonction peut s'utiliser dans une instruction `with` exactement comme
# open() lui-même :
#     with open_text(file_path) as f:
# L'appelant n'a pas besoin de savoir de quel type de fichier il
# s'agissait.
# ---------------------------------------------------------------------
def open_text(path: Path) -> TextIO:
    # Les fichiers .json.gz sont lus compressés, sans les décompresser d'abord sur le disque.
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


# ---------------------------------------------------------------------
# def extract(file_paths) -> tuple[...]:
#
# NOUVEAU : elle prend désormais une LISTE de fichiers (file_paths:
# list[Path]) au lieu d'un seul, et les lit l'un après l'autre dans les
# MÊMES dictionnaires et le MÊME ensemble. Ainsi, un acteur vu à l'heure 3
# puis de nouveau à l'heure 17 finit quand même en UNE seule rangée, avec
# son login le plus récent (remember_latest() compare les heures des
# événements, quel que soit le fichier d'où ils viennent). Pour le
# benchmark, la liste ne contient qu'un seul fichier.
#
# Lit les fichiers une fois et renvoie QUATRE choses à la fois.
# L'annotation de type ressemble à un casse-tête, mais ce ne sont que
# deux sortes de petits TUPLES et un grand. Allons de l'intérieur vers
# l'extérieur, avec des données réelles.
#
# 1. CE QU'EST UN TUPLE
#    Un groupe fixe de valeurs qui vont ensemble, entre parenthèses.
#    Voyez-le comme une FICHE À CASES : le nombre de cases ne change pas,
#    et chaque case a un sens selon sa POSITION. [0] lit la première
#    case, [1] la deuxième :
#
#        fiche = ("2026-08-27T15:35:35Z", "peitongshi")
#        fiche[0]   # "2026-08-27T15:35:35Z"  <- la date
#        fiche[1]   # "peitongshi"            <- le nom
#
#    Cela ressemble à une liste, mais on ne peut PLUS le modifier une
#    fois créé.
#
# 2. LES DEUX PETITES FICHES
#    (date, nom)           utilisée dans actors et repos
#    (actor_id, repo_id)   utilisée dans pairs = UNE connexion
#
# 3. OÙ ELLES VONT
#    actors : un dictionnaire dont les VALEURS sont des fiches (date, nom)
#        actors = {321725054: ("2026-08-27T15:35:35Z", "peitongshi"),
#                  19:        ("2026-08-27T15:02:11Z", "brynary"), ...}
#        -> dict[int, tuple[str, str]]  « nombre -> fiche de deux textes »
#    repos : exactement pareil, pour les dépôts.
#    pairs : un ENSEMBLE de fiches (actor_id, repo_id)
#        pairs = {(321725054, 1348625135), (19, 1310070394), ...}
#        -> set[tuple[int, int]]  « ensemble de fiches de deux nombres »
#
# 4. LA GRANDE FICHE : CE QUE RENVOIE extract()
#    Une fonction ne peut renvoyer qu'UNE chose. Pour en renvoyer quatre,
#    on les met dans une fiche à QUATRE cases :
#
#        return actors, repos, pairs, skipped_bot_events
#
#    et main() l'ouvre et répartit les quatre cases dans quatre
#    variables :
#
#        actors, repos, pairs, skipped_bot_events = extract(args.file)
#
# LE SCHÉMA COMPLET
#
#    extract() renvoie UN tuple à 4 cases :
#    |-- case 1 : actors   dictionnaire   321725054 -> ("2026-08-27T15:35:35Z", "peitongshi")
#    |                                                  '-- petite fiche : date, nom --'
#    |-- case 2 : repos    dictionnaire   (pareil qu'actors, pour les dépôts)
#    |-- case 3 : pairs    ensemble       {(321725054, 1348625135), (19, 1310070394), ...}
#    |                                      '-- petite fiche : acteur, dépôt = 1 connexion --'
#    '-- case 4 : skipped_bot_events      un nombre : 1970
#
# L'ANNOTATION DE TYPE, LUE MORCEAU PAR MORCEAU
#
#    -> tuple[                          une fiche à 4 cases :
#        dict[int, tuple[str, str]],      1. actors : id -> (date, nom)
#        dict[int, tuple[str, str]],      2. repos :  id -> (date, nom)
#        set[tuple[int, int]],            3. pairs :  ensemble de (actor_id, repo_id)
#        int,                             4. skipped_bot_events : un nombre
#    ]
# ---------------------------------------------------------------------
def extract(file_paths: list[Path]) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
    actors: dict[int, tuple[str, str]] = {}
    repos: dict[int, tuple[str, str]] = {}

    # -----------------------------------------------------------------
    # pairs: set[tuple[int, int]] = set()
    #
    # C'EST ICI que se fait « une connexion par paire acteur-dépôt, sans
    # doublons ». Chaque connexion est un tuple (actor_id, repo_id), et un
    # ENSEMBLE ne garde chaque élément qu'une seule fois (voir la copie
    # annotée de summarize_data.py). Si ana pousse 10 fois vers le même
    # dépôt, pairs.add((ana_id, repo_id)) s'exécute 10 fois, mais
    # l'ensemble n'en garde qu'un seul exemplaire. C'est pour cela que
    # 67,459 événements non-bots ne donnent que 15,053 connexions.
    #
    # (Les tuples peuvent aller dans un ensemble ; les listes non, car un
    # ensemble a besoin d'éléments qui ne peuvent jamais changer — et les
    # tuples ne peuvent pas être modifiés.)
    # -----------------------------------------------------------------
    pairs: set[tuple[int, int]] = set()
    skipped_bot_events = 0
    # NOUVEAU : compte les événements écartés parce qu'ils n'avaient pas
    # d'id d'acteur ou de dépôt (expliqué à la ligne `if "id" not in ...`
    # plus bas).
    skipped_without_id = 0

    # NOUVEAU : une boucle extérieure sur les fichiers. Tout ce qui est à
    # l'intérieur est le même travail ligne par ligne qu'avant, simplement
    # indenté d'un niveau de plus. Chaque fichier est ouvert avec
    # open_text(), donc .json et .json.gz fonctionnent tous les deux.
    for file_path in file_paths:
        with open_text(file_path) as f:
            for line in f:
                event = json.loads(line)
                actor = event["actor"]
                repo = event["repo"]
                # ---------------------------------------------------
                # NOUVEAU : ignorer les événements dont l'acteur ou le
                # dépôt n'a pas d'id.
                #
                # Trouvé dans des données RÉELLES : dans une fenêtre de
                # 24 heures de 1,250,059 événements, 2 ForkEvents
                # avaient un dépôt VIDE :
                #     "repo": {}
                # très probablement des forks de dépôts supprimés depuis.
                # Sans id, il n'y a ni nœud à créer ni connexion à
                # tracer, et repo["id"] ferait planter toute l'exécution
                # avec une KeyError.
                #
                # `"id" not in actor` vérifie si le dictionnaire possède
                # cette clé (le même test `in` sur les dict que dans
                # remember_latest). On compte ces événements et on passe
                # au suivant avec `continue`, comme pour les événements
                # de bots plus bas. Le total est signalé une seule fois,
                # après la lecture de tous les fichiers.
                #
                # (L'heure du benchmark ne contient aucun événement de
                # ce genre, c'est pourquoi sa sortie CSV est inchangée.)
                # ---------------------------------------------------
                # Quelques événements arrivent avec un dépôt vide ({}), par ex. des forks de
                # dépôts supprimés depuis : sans ids, il n'y a ni nœud ni connexion à créer.
                if "id" not in actor or "id" not in repo:
                    skipped_without_id += 1
                    continue

                # Même schéma « ignorer et compter » qu'avant : `continue` passe
                # à la ligne suivante sans atteindre le code ci-dessous.
                if is_bot(actor["login"]):
                    skipped_bot_events += 1
                    continue

                # Les ids (actor["id"], repo["id"]) servent de clés partout —
                # jamais les noms, qui peuvent changer (voir remember_latest).
                remember_latest(actors, actor["id"], event["created_at"], actor["login"])
                remember_latest(repos, repo["id"], event["created_at"], repo["name"])
                pairs.add((actor["id"], repo["id"]))

    # -----------------------------------------------------------------
    # NOUVEAU : signaler les événements ignorés, mais seulement s'il y en
    # a eu.
    #
    # `if skipped_without_id:` — un nombre compte comme False quand il
    # vaut 0 et comme True sinon, donc cela se lit « s'il y en a eu
    # d'ignorés ».
    #
    # log.warning("Skipped %d event(s) ...", skipped_without_id)
    #   Attention : ce n'est PAS une f-string. logging a son propre style
    #   d'emplacements : %d signifie « un nombre entier va ici », et la
    #   valeur est passée comme argument séparé. logging la remplit
    #   lui-même, par ex.
    #       Skipped 2 event(s) without an actor or repo id
    #   (C'est la convention pour les appels de logging : le texte n'est
    #   construit que si le message va réellement être affiché quelque
    #   part.)
    #
    # Où il apparaît : à l'écran quand le script est exécuté seul ; à
    # l'écran ET dans logs/pipeline.log quand il est exécuté depuis
    # pipeline.py (voir `log` plus haut).
    #
    # C'est un avertissement plutôt qu'une valeur de retour
    # supplémentaire, donc la ligne de retour (et chaque appelant) reste
    # exactement comme avant.
    # -----------------------------------------------------------------
    if skipped_without_id:
        log.warning("Skipped %d event(s) without an actor or repo id", skipped_without_id)
    return actors, repos, pairs, skipped_bot_events


# ---------------------------------------------------------------------
# def write_csv(path, header, rows) -> None:
#
# Écrit un fichier CSV : une ligne d'en-tête avec les noms des colonnes,
# puis une ligne par rangée. Utilisée trois fois, une par fichier.
#
# open(path, "w", encoding="utf-8", newline="")
#   "w"         mode ÉCRITURE : crée le fichier, ou le vide s'il existe.
#   newline=""  exigé par le module csv : il écrit lui-même les fins de
#               ligne, et sans cela, Windows ajouterait une ligne vide
#               supplémentaire entre les rangées.
#
# csv.writer(f)          un objet qui transforme des rangées en lignes CSV.
# writer.writerow(...)   écrit UNE rangée (ici, l'en-tête).
# writer.writerows(...)  écrit PLUSIEURS rangées d'un coup (toutes les données).
#
# rows: list[tuple]  chaque rangée est un tuple, par exemple (19, "brynary"),
# et chaque valeur du tuple devient une colonne.
#
# {path.name:<16}  path.name est juste le nom du fichier ("actors.csv"),
# sans les dossiers ; :<16 le complète jusqu'à 16 caractères pour que les
# décomptes soient alignés.
# ---------------------------------------------------------------------
def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {path.name:<16} {len(rows):>7} rows")


# ---------------------------------------------------------------------
# def write_all(out_dir, actors, repos, pairs) -> None:
#
# NOUVEAU : les étapes « créer le dossier et écrire les trois fichiers
# CSV » qui se trouvaient auparavant dans main(), déplacées dans leur
# propre fonction. Rien n'y a changé — elles ont été DÉPLACÉES, pour que
# pipeline.py puisse appeler extract() puis write_all() lui-même, sans
# passer par main() et ses arguments de ligne de commande.
#
# La signature est longue, elle est donc répartie sur deux lignes :
# Python autorise un saut de ligne n'importe où entre parenthèses ( ), et
# la deuxième ligne est indentée pour s'aligner sur le premier paramètre,
# simplement pour la lisibilité.
# ---------------------------------------------------------------------
def write_all(out_dir: Path, actors: dict[int, tuple[str, str]], repos: dict[int, tuple[str, str]],
              pairs: set[tuple[int, int]]) -> None:
    # -----------------------------------------------------------------
    # out_dir.mkdir(parents=True, exist_ok=True)
    #
    # Crée le dossier de sortie (data/csv/) s'il n'existe pas encore.
    #   parents=True   crée aussi les dossiers parents manquants.
    #   exist_ok=True  ne pas échouer si le dossier existe déjà (par
    #                  exemple lors de la deuxième exécution).
    # -----------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)

    # -----------------------------------------------------------------
    # Construire les rangées : sorted(...) + une compréhension de liste
    #
    # sorted(actors.items()) donne les paires (id, (created_at, login))
    # TRIÉES PAR ID. La compréhension ne garde ensuite que ce qui va dans
    # le fichier :
    #     for actor_id, (_, login) in ...
    # décompose chaque paire, et aussi le tuple intérieur : `_` est le
    # created_at, dont on n'a plus besoin (« une valeur dont je n'ai pas
    # besoin », comme dans check_connections.py). Chaque rangée devient
    # (actor_id, login).
    #
    # Pour actor_repo.csv, sorted(pairs) transforme l'ensemble en une liste
    # de tuples triés par actor_id, puis par repo_id.
    #
    # POURQUOI TRIER : ni un ensemble ni l'ordre d'arrivée des événements ne
    # garantissent un ordre fixe. Trier signifie que la même entrée produit
    # TOUJOURS exactement les mêmes fichiers, octet pour octet — il est donc
    # facile de vérifier qu'une exécution ultérieure n'a rien changé. Encore
    # une question de reproductibilité.
    # -----------------------------------------------------------------
    # Trié par id pour que la même entrée produise toujours des fichiers identiques octet pour octet.
    write_csv(out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


# parse_args() : même schéma que dans les scripts précédents. --out-dir
# permet de choisir un autre dossier de sortie ; type=Path le convertit,
# comme pour --file.
#
# NOUVEAU pour --file :
#   nargs="+"              « une ou plusieurs valeurs ». On peut
#                          désormais écrire
#                            --file a.json.gz b.json.gz c.json.gz
#                          et args.file devient une LISTE de trois Path
#                          (type=Path est appliqué à chacun). Dans un
#                          shell comme Git Bash, data/live/raw/*.json.gz
#                          est développé en tous les noms de fichiers
#                          correspondants avant même que Python ne les
#                          voie.
#   default=[DEFAULT_FILE] la valeur par défaut doit maintenant être elle
#                          aussi une liste (d'un seul fichier), pour
#                          qu'extract() reçoive toujours une liste, que
#                          --file ait été fourni ou non.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, nargs="+", default=[DEFAULT_FILE],
                         help=f"One or more .json or .json.gz files (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # extract() renvoie un tuple de quatre valeurs ; cette ligne le DÉCOMPOSE
    # en quatre variables d'un coup (même idée que `for key, value in ...`).
    # (args.file est maintenant une liste de Path — voir parse_args()
    # ci-dessus.)
    actors, repos, pairs, skipped_bot_events = extract(args.file)

    # len(args.file) = le nombre de fichiers lus, par ex.
    #     Read 1 file(s). Skipped 1970 bot events. Writing to ...\data\csv:
    # La création du dossier et l'écriture des CSV qui suivaient ici
    # vivent désormais dans write_all() (voir ci-dessus).
    print(f"Read {len(args.file)} file(s). Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")
    write_all(args.out_dir, actors, repos, pairs)


# main() et la garde `if __name__ == "__main__":` : même rôle et même
# fonctionnement que dans les autres scripts — voir la copie annotée de
# download_gharchive.py pour l'explication complète.
if __name__ == "__main__":
    main()
