########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/load_neo4j.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter.
# Le script réel et « propre » (sans tous ces commentaires) est
# scripts/load_neo4j.py.
#
# Ce fichier suppose que vous avez déjà lu les scripts annotés précédents,
# en particulier check_connections.py (le pilote Neo4j, execute_query,
# NEO4J_PASSWORD) et load_postgres.py (le côté PostgreSQL du même travail,
# et time.perf_counter()). Ce fichier se concentre sur ce qui est NOUVEAU :
# le Cypher pour créer des nœuds et des arêtes (CREATE, MATCH, UNWIND,
# paramètres), les CONTRAINTES d'unicité, la lecture d'un CSV en dict avec
# csv.DictReader, et l'envoi des données par LOTS.
#
# NOUVEAUTÉS de cette version : comme dans load_postgres.py, on peut
# choisir DANS QUELLE base de données charger (--database, ou le
# paramètre `database` de load()). La valeur par défaut reste
# "gharchive", la base figée du benchmark ; le pipeline en direct sur 24
# heures (pipeline.py) charge plutôt dans "gharchive24h", et ne touche
# donc jamais aux données du benchmark.
#
# Lancez-le via run.sh (il a besoin de NEO4J_PASSWORD) :
#     ./run.sh scripts/load_neo4j.py
########################################################################

"""Load the extracted CSV files into the Neo4j "gharchive" database.

Creates (or re-creates) the benchmark graph from the CSV files written by
extract_csv.py, the same files PostgreSQL is loaded from:

    (:Actor {id, login})   one node per row of actors.csv      id is unique
    (:Repo  {id, name})    one node per row of repos.csv       id is unique
    (:Actor)-[:INTERACTED_WITH]->(:Repo)   one edge per row of actor_repo.csv

Every run starts from an empty database, so running it twice gives the same
result. At the end it checks that the node and edge counts match the CSV files.

Usage:
    ./run.sh scripts/load_neo4j.py
    ./run.sh scripts/load_neo4j.py --csv-dir data/csv
    ./run.sh scripts/load_neo4j.py --csv-dir data/live/csv --database gharchive24h
"""

# Tout est déjà expliqué dans les scripts précédents (csv dans
# extract_csv.py, time dans load_postgres.py, GraphDatabase et os dans
# check_connections.py).
import argparse
import csv
import os
import sys
import time
from pathlib import Path

from neo4j import GraphDatabase

# ---------------------------------------------------------------------
# Constantes
#
# DEFAULT_DATABASE = "gharchive" — la décision du projet : le benchmark
# travaille toujours dans la base de données appelée gharchive, des deux
# côtés. check_connections.py ne nommait pas de base de données, donc il
# utilisait celle par défaut de l'instance (« neo4j »). Ici, chaque
# requête passe database_=... explicitement.
#
# NOUVEAU : cette constante s'appelait auparavant NEO4J_DATABASE et était
# utilisée directement par chaque requête. Elle s'appelle désormais
# DEFAULT_DATABASE (le même nom que dans load_postgres.py) car ce n'est
# que la valeur PAR DÉFAUT : load() prend un paramètre `database`, et le
# pipeline en direct passe "gharchive24h".
#
# Pourquoi "gharchive24h" et pas "gharchive_24h" ? Les noms de bases de
# données Neo4j ne peuvent contenir que des lettres, des chiffres, des
# points (.) et des tirets (-) — PAS de tirets bas — donc "gharchive_24h"
# serait refusé. Le même nom est aussi utilisé côté PostgreSQL, pour que
# les deux correspondent.
#
# BATCH_SIZE = 5000 — combien de rangées partent dans chaque requête
# (voir run_in_batches()).
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
DEFAULT_DATABASE = "gharchive"
BATCH_SIZE = 5000

# ---------------------------------------------------------------------
# CONSTRAINTS — l'équivalent Neo4j de la PRIMARY KEY (clé primaire) de
# PostgreSQL
#
# CREATE CONSTRAINT actor_id_unique IF NOT EXISTS
#     FOR (a:Actor) REQUIRE a.id IS UNIQUE
#
#   « Pour chaque nœud portant l'étiquette Actor, la propriété id doit
#   être unique. » Comme une clé primaire, elle construit aussi un INDEX
#   sur cette propriété, donc retrouver un acteur par son id est
#   instantané — ce dont l'étape des arêtes plus bas a besoin.
#   IF NOT EXISTS : lors d'une deuxième exécution, la contrainte existe
#   déjà, et cette instruction ne fait simplement rien (au lieu
#   d'échouer).
#
# Remarquez qu'il n'y a AUCUN index pour les arêtes : dans un graphe,
# chaque nœud stocke déjà des liens directs vers ses propres arêtes
# (« index-free adjacency », adjacence sans index). C'est exactement
# l'avantage que le benchmark veut mesurer face aux index de actor_repo
# dans PostgreSQL.
# ---------------------------------------------------------------------
CONSTRAINTS = [
    "CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repo) REQUIRE r.id IS UNIQUE",
]

# ---------------------------------------------------------------------
# Les requêtes Cypher qui créent les données
#
# Cypher est le langage de requête de Neo4j. Il « dessine » le graphe
# avec des symboles :
#   (a:Actor {id: 19})        un NŒUD : parenthèses, une étiquette
#                             (:Actor) et des propriétés entre accolades
#   -[:INTERACTED_WITH]->     une ARÊTE : crochets, un type, et une
#                             flèche qui indique son sens
#
# $rows est un PARAMÈTRE : un emplacement réservé dont Python envoie la
# valeur à part (ici, une liste de dict). Envoyer les données en
# paramètres, au lieu de les coller dans le texte de la requête, est plus
# sûr et permet à Neo4j de réutiliser le même plan de requête pour chaque
# lot.
#
# UNWIND $rows AS row
#   Prend la LISTE et la transforme en une rangée par élément, pour que
#   le reste de la requête s'exécute une fois par élément — comme une
#   boucle `for row in rows:`, mais à l'intérieur de la base de données,
#   en une seule requête.
#
# CREATE (:Actor {id: row.id, login: row.login})
#   Crée un nœud par rangée. row.id lit la clé "id" du dict.
#
# CREATE_EDGES fait plus de travail par rangée :
#   MATCH (a:Actor {id: row.actor_id})   TROUVER l'acteur avec cet id
#   MATCH (r:Repo {id: row.repo_id})     TROUVER le dépôt avec cet id
#   CREATE (a)-[:INTERACTED_WITH]->(r)   créer l'arête entre les deux
# Les deux MATCH sont instantanés grâce aux index des contraintes.
#
# Pourquoi le nom INTERACTED_WITH ? Les connexions viennent de tous les
# types d'événements (pushes, commentaires, étoiles...), et mettre une
# étoile ou commenter n'est pas « contribuer », donc un nom neutre est
# plus exact.
# ---------------------------------------------------------------------
CREATE_ACTORS = "UNWIND $rows AS row CREATE (:Actor {id: row.id, login: row.login})"
CREATE_REPOS = "UNWIND $rows AS row CREATE (:Repo {id: row.id, name: row.name})"
CREATE_EDGES = """
UNWIND $rows AS row
MATCH (a:Actor {id: row.actor_id})
MATCH (r:Repo {id: row.repo_id})
CREATE (a)-[:INTERACTED_WITH]->(r)
"""

# ---------------------------------------------------------------------
# COUNTS — les requêtes de la vérification finale : (étiquette, requête,
# fichier CSV).
#   MATCH (a:Actor) RETURN count(a) AS n           combien de nœuds Actor
#   MATCH ()-[e:INTERACTED_WITH]->() RETURN ...    combien d'arêtes ; ()
#                                                  signifie « n'importe
#                                                  quel nœud »
# `AS n` nomme la colonne du résultat, pour que Python puisse la lire
# avec record["n"].
# ---------------------------------------------------------------------
COUNTS = [
    ("Actor nodes", "MATCH (a:Actor) RETURN count(a) AS n", "actors.csv"),
    ("Repo nodes", "MATCH (r:Repo) RETURN count(r) AS n", "repos.csv"),
    ("INTERACTED_WITH edges", "MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e) AS n", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def read_csv(path, int_columns) -> list[dict]:
#
# csv.DictReader lit un fichier CSV et donne chaque rangée sous forme de
# DICT dont les clés sont les noms des colonnes de l'en-tête :
#
#     id,login            ->   {"id": "19", "login": "brynary"}
#     19,brynary
#
# Un CSV n'est que du texte, donc chaque valeur sort sous forme de CHAÎNE
# ("19"). La boucle convertit ensuite les colonnes d'id en nombres avec
# int(), pour que Neo4j les stocke comme des entiers, exactement comme le
# BIGINT de PostgreSQL. Si un côté stockait les ids en texte et l'autre en
# nombres, les données ne seraient pas vraiment identiques.
#
# int_columns: tuple[str, ...] — un tuple de noms de colonnes de
# n'importe quelle longueur ; le `...` signifie « n'importe quel nombre de
# str ». ("id",) avec une virgule finale est un tuple à UN élément (sans
# la virgule, ("id") serait simplement la chaîne "id").
# ---------------------------------------------------------------------
def read_csv(path: Path, int_columns: tuple[str, ...]) -> list[dict]:
    # csv.DictReader donne chaque rangée sous forme de dict dont les clés sont les noms de colonnes de l'en-tête.
    # Les ids sont convertis en int, pour être stockés comme des nombres, comme dans PostgreSQL.
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for column in int_columns:
            row[column] = int(row[column])
    return rows


# ---------------------------------------------------------------------
# def run_in_batches(driver, query, rows, database) -> None:
#
# Au lieu d'envoyer 15,053 rangées en une seule requête énorme, elle les
# envoie par LOTS de BATCH_SIZE (5,000) : des requêtes plus petites
# utilisent moins de mémoire des deux côtés et ne risquent pas d'atteindre
# une limite de taille.
#
# range(0, len(rows), BATCH_SIZE) compte par pas de 5,000 :
#     0, 5000, 10000, 15000
# rows[start:start + BATCH_SIZE] est une TRANCHE de 5,000 rangées (la
# dernière peut être plus courte) : rows[0:5000], rows[5000:10000], ...
#
# rows=... est envoyé comme paramètre $rows de la requête.
# database_= a un tiret bas final pour ne pas être confondu avec un
# paramètre de requête qui s'appellerait justement « database ».
#
# NOUVEAU : `database` est désormais un paramètre (transmis par load())
# au lieu de la constante fixe, donc les lots vont dans la base de
# données que load() a été chargée de remplir. Notez les deux noms
# différents sur cette ligne :
#   database_=database   l'option du pilote (avec _) = notre variable.
#
# Le COPY de PostgreSQL envoie tout en un seul flux continu ; Neo4j le
# reçoit par lots. Les deux sont la façon habituelle de charger en masse
# chaque base de données.
# ---------------------------------------------------------------------
def run_in_batches(driver, query: str, rows: list[dict], database: str) -> None:
    # Envoyer les rangées quelques milliers à la fois plutôt que toutes dans une seule requête énorme.
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=database)


# Même fonction de chronométrage que dans load_postgres.py — voir sa copie annotée.
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir, database=DEFAULT_DATABASE) -> bool:
#
# NOUVEAU : le paramètre `database`, même idée que dans load_postgres.py.
# Sa valeur par défaut est DEFAULT_DATABASE ("gharchive"), donc
# load(csv_dir) se comporte exactement comme avant. Chaque requête
# ci-dessous utilise désormais database_=database, et run_in_batches()
# reçoit le même nom, donc TOUT le travail (vidage, contraintes,
# chargement, décomptes) se fait dans la base de données choisie.
#
# Une différence avec PostgreSQL : ici, le pilote se connecte au SERVEUR
# Neo4j (NEO4J_URI) et la base de données est choisie à chaque requête,
# avec database_=... ; avec psycopg, la base de données est choisie une
# seule fois, à la connexion.
# ---------------------------------------------------------------------
def load(csv_dir: Path, database: str = DEFAULT_DATABASE) -> bool:
    # La lecture des CSV dans Python est chronométrée séparément et
    # laissée EN DEHORS du total : c'est de la préparation, pas du
    # chargement dans la base de données.
    step = time.perf_counter()
    actors = read_csv(csv_dir / "actors.csv", ("id",))
    repos = read_csv(csv_dir / "repos.csv", ("id",))
    edges = read_csv(csv_dir / "actor_repo.csv", ("actor_id", "repo_id"))
    print(f"CSV files read into Python                      {seconds_since(step)}")

    password = os.environ["NEO4J_PASSWORD"]
    all_match = True
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password)) as driver:
        driver.verify_connectivity()
        load_start = time.perf_counter()

        # -------------------------------------------------------------
        # MATCH (n) DETACH DELETE n
        #   MATCH (n)   chaque nœud de la base de données
        #   DETACH      d'abord retirer les arêtes de chaque nœud...
        #   DELETE n    ...puis le nœud lui-même (Neo4j refuse de
        #               supprimer un nœud qui a encore des arêtes).
        # L'équivalent Neo4j du DROP TABLE de PostgreSQL : chaque
        # exécution repart d'une base de données vide.
        # -------------------------------------------------------------
        step = time.perf_counter()
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=database)
        for constraint in CONSTRAINTS:
            driver.execute_query(constraint, database_=database)
        print(f"Database emptied; unique constraints in place   {seconds_since(step)}")

        # -------------------------------------------------------------
        # Les trois chargements, dans une boucle sur des tuples
        # (étiquette, requête, rangées). L'ORDRE compte, comme dans
        # PostgreSQL : les nœuds d'abord, car chaque arête doit TROUVER
        # son acteur et son dépôt (les MATCH de CREATE_EDGES). Chaque
        # étape est chronométrée séparément.
        # -------------------------------------------------------------
        # Les nœuds d'abord : l'étape des arêtes recherche chaque acteur et dépôt par son id.
        for label, query, rows in (("Actor nodes", CREATE_ACTORS, actors),
                                   ("Repo nodes", CREATE_REPOS, repos),
                                   ("INTERACTED_WITH edges", CREATE_EDGES, edges)):
            step = time.perf_counter()
            run_in_batches(driver, query, rows, database)
            print(f"Created {label:<22}                  {seconds_since(step)}")

        # Pas de commit explicite ici : execute_query() valide chaque
        # requête séparément, donc les données sont déjà enregistrées.
        print(f"Total load time                                 {seconds_since(load_start)}")

        # -------------------------------------------------------------
        # La vérification, même idée que dans load_postgres.py : compter
        # dans la base de données, comparer avec le CSV. records[0]["n"]
        # lit la colonne "n" de la première (et unique) rangée du
        # résultat.
        # -------------------------------------------------------------
        print("\nLoaded (database vs. CSV file):")
        csv_counts = {"actors.csv": len(actors), "repos.csv": len(repos), "actor_repo.csv": len(edges)}
        for label, query, csv_name in COUNTS:
            records, _, _ = driver.execute_query(query, database_=database)
            in_db = records[0]["n"]
            in_csv = csv_counts[csv_name]
            status = "OK" if in_db == in_csv else "MISMATCH"
            all_match = all_match and in_db == in_csv
            print(f"  {label:<22} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args() et main() : comme dans load_postgres.py, y compris la
# NOUVELLE option --database (par ex. --database gharchive24h).
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                         help=f"Neo4j database to load into (default: {DEFAULT_DATABASE})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not load(args.csv_dir, args.database):
        sys.exit("Some counts don't match their CSV file.")
    print("\nNeo4j load complete.")


# Voir la copie annotée de download_gharchive.py pour la garde __name__.
if __name__ == "__main__":
    main()
