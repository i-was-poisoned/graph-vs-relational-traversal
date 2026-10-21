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
# Son rôle dans le projet : être la SOURCE UNIQUE à partir de laquelle les
# deux bases de données sont chargées. PostgreSQL et Neo4j liront chacune
# ces trois mêmes fichiers, donc elles ne peuvent pas finir par contenir des
# données différentes — une condition indispensable pour un benchmark
# équitable.
########################################################################

"""Extract the benchmark's actor/repo graph from a GH Archive file into CSV files.

Reads the JSON Lines file once, skips bot accounts (logins ending in "[bot]"),
and writes three CSV files that both databases are loaded from, so they always
hold exactly the same data:

    actors.csv       id, login             one row per actor (most recent login)
    repos.csv        id, name              one row per repo (most recent name)
    actor_repo.csv   actor_id, repo_id     one row per actor-repo pair, no repeats

Usage:
    python scripts/extract_csv.py
    python scripts/extract_csv.py --file data/2026-08-27-15.json --out-dir data/csv
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
# ---------------------------------------------------------------------
import argparse
import csv
import json
from pathlib import Path

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
# def extract(file_path) -> tuple[...]:
#
# Lit le fichier une seule fois et renvoie QUATRE choses en même temps,
# regroupées dans un tuple (main() les décompose en quatre variables) :
#
#   actors   dict  id -> (created_at, login)
#   repos    dict  id -> (created_at, name)
#   pairs    set   de tuples (actor_id, repo_id)
#   skipped_bot_events  int
#
# La longue annotation de type `-> tuple[...]` décrit simplement ces
# quatre types.
# ---------------------------------------------------------------------
def extract(file_path: Path) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
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

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            actor = event["actor"]
            repo = event["repo"]

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


# parse_args() : même schéma que dans les scripts précédents. --out-dir
# permet de choisir un autre dossier de sortie ; type=Path le convertit,
# comme pour --file.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # extract() renvoie un tuple de quatre valeurs ; cette ligne le DÉCOMPOSE
    # en quatre variables d'un coup (même idée que `for key, value in ...`).
    actors, repos, pairs, skipped_bot_events = extract(args.file)

    # -----------------------------------------------------------------
    # args.out_dir.mkdir(parents=True, exist_ok=True)
    #
    # Crée le dossier de sortie (data/csv/) s'il n'existe pas encore.
    #   parents=True   crée aussi les dossiers parents manquants.
    #   exist_ok=True  ne pas échouer si le dossier existe déjà (par
    #                  exemple lors de la deuxième exécution).
    # -----------------------------------------------------------------
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")

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
    write_csv(args.out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(args.out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(args.out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


# main() et la garde `if __name__ == "__main__":` : même rôle et même
# fonctionnement que dans les autres scripts — voir la copie annotée de
# download_gharchive.py pour l'explication complète.
if __name__ == "__main__":
    main()
