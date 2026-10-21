########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/load_postgres.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter.
# Le script réel et « propre » (sans tous ces commentaires) est
# scripts/load_postgres.py.
#
# Ce fichier suppose que vous avez déjà lu les scripts annotés précédents,
# en particulier check_connections.py (psycopg, la connexion, `with`,
# PGPASSWORD) et extract_csv.py (les fichiers CSV que ce script charge). Ce
# fichier se concentre sur ce qui est NOUVEAU : le SQL pour créer des tables
# (CREATE TABLE, PRIMARY KEY, REFERENCES, CREATE INDEX), le chargement de
# fichiers CSV avec COPY, les TRANSACTIONS et COMMIT, ANALYZE, et la mesure
# du temps avec time.perf_counter().
#
# Lancez-le via run.sh (il a besoin de PGPASSWORD) :
#     ./run.sh scripts/load_postgres.py
########################################################################

"""Load the extracted CSV files into the PostgreSQL "gharchive" database.

Creates (or re-creates) the three benchmark tables and fills them from the CSV
files written by extract_csv.py:

    actor        (id PRIMARY KEY, login)
    repo         (id PRIMARY KEY, name)
    actor_repo   (actor_id -> actor.id, repo_id -> repo.id,
                  PRIMARY KEY (actor_id, repo_id)), plus an index on repo_id

Every run starts from empty tables, so running it twice gives the same result.
At the end it checks that each table has exactly as many rows as its CSV file.

Usage:
    ./run.sh scripts/load_postgres.py
    ./run.sh scripts/load_postgres.py --csv-dir data/csv
"""

# ---------------------------------------------------------------------
# import time — NOUVEAU : le module de la bibliothèque standard pour les
# horloges. On n'utilise que time.perf_counter() (voir seconds_since()
# plus bas).
# argparse, sys, Path, psycopg : déjà expliqués dans les scripts précédents.
# ---------------------------------------------------------------------
import argparse
import sys
import time
from pathlib import Path

import psycopg

# Mêmes constantes que dans extract_csv.py (où se trouvent les CSV) et
# check_connections.py (comment joindre PostgreSQL).
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}

# ---------------------------------------------------------------------
# SCHEMA — le SQL qui construit les trois tables
#
# Une chaîne Python écrite entre triples guillemets ("""...""") peut
# s'étendre sur plusieurs lignes. Celle-ci contient du SQL, le langage de
# PostgreSQL, qui est envoyé au serveur tel quel.
#
# DROP TABLE IF EXISTS ...
#   Supprime la table si elle existe déjà (d'une exécution précédente), et
#   ne fait rien sinon. C'est ce qui rend le script REPRODUCTIBLE : chaque
#   exécution repart de zéro. L'ORDRE compte : actor_repo pointe vers
#   actor et repo, donc elle est supprimée EN PREMIER (on ne peut pas
#   supprimer une table dont une autre dépend encore).
#
# CREATE TABLE actor ( id BIGINT PRIMARY KEY, login TEXT NOT NULL );
#   BIGINT       un nombre entier assez grand pour les ids de GitHub (un
#                INTEGER ordinaire s'arrête vers 2 100 millions ; certains
#                ids dépassent déjà cette limite, et BIGINT est le choix sûr).
#   TEXT         du texte de n'importe quelle longueur.
#   NOT NULL     la valeur ne peut jamais être absente.
#   PRIMARY KEY  la colonne qui identifie chaque rangée (la clé primaire) :
#                elle doit être unique, ne peut pas être absente, et
#                PostgreSQL construit automatiquement un INDEX dessus, donc
#                retrouver une rangée par son id est instantané.
#   (login n'est PAS unique : souvenez-vous des deux comptes « Copilot ».)
#
# CREATE TABLE actor_repo (... REFERENCES actor (id) ...)
#   REFERENCES crée une CLÉ ÉTRANGÈRE : chaque actor_id doit exister dans
#   actor.id, et chaque repo_id dans repo.id. La base de données refuse
#   elle-même une connexion qui pointe vers un acteur ou un dépôt
#   inexistant.
#
#   PRIMARY KEY (actor_id, repo_id) — une clé primaire composée de DEUX
#   colonnes : c'est la PAIRE qui doit être unique. C'est la base de
#   données qui impose « une connexion par paire acteur-dépôt, sans
#   doublons », la même règle qu'extract_csv.py appliquait avec son
#   ensemble.
#
# CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
#   Un INDEX est comme l'index à la fin d'un livre : au lieu de lire
#   chaque page pour trouver un mot, on le cherche et on va directement à
#   la bonne page. La clé primaire à deux colonnes est triée d'abord par
#   actor_id, donc elle est idéale pour « les dépôts d'un acteur » mais pas
#   pour « les acteurs d'un dépôt ». Cet index supplémentaire couvre
#   l'autre sens. Le parcours du benchmark
#   (acteur -> dépôt -> acteur -> dépôt) a besoin des DEUX, à chaque saut.
#
# Les lignes qui commencent par -- dans le SQL sont des commentaires SQL
# (comme # en Python) ; PostgreSQL les ignore.
# ---------------------------------------------------------------------
# Supprimées enfant d'abord (actor_repo pointe vers actor et repo), créées parents d'abord.
SCHEMA = """
DROP TABLE IF EXISTS actor_repo;
DROP TABLE IF EXISTS repo;
DROP TABLE IF EXISTS actor;

CREATE TABLE actor (
    id    BIGINT PRIMARY KEY,
    login TEXT   NOT NULL
);

CREATE TABLE repo (
    id   BIGINT PRIMARY KEY,
    name TEXT   NOT NULL
);

CREATE TABLE actor_repo (
    actor_id BIGINT NOT NULL REFERENCES actor (id),
    repo_id  BIGINT NOT NULL REFERENCES repo (id),
    PRIMARY KEY (actor_id, repo_id)
);

-- The primary key already finds an actor's repos quickly (actor_id comes first).
-- This index does the same in the other direction: a repo's actors.
CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
"""

# ---------------------------------------------------------------------
# TABLES — une liste de tuples (table, colonnes, fichier CSV), un par
# table. Tout garder dans une seule liste permet à la même boucle de
# charger et de vérifier les trois. L'ORDRE est l'ordre de chargement :
# actor et repo avant actor_repo, à cause des clés étrangères (une
# connexion ne peut être chargée qu'une fois que son acteur et son dépôt
# existent).
# ---------------------------------------------------------------------
# (table, colonnes, fichier CSV) dans l'ordre de chargement : parents avant actor_repo.
TABLES = [
    ("actor", "id, login", "actors.csv"),
    ("repo", "id, name", "repos.csv"),
    ("actor_repo", "actor_id, repo_id", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def count_csv_rows(path) -> int:
#
# Compte les rangées de données d'un fichier CSV, pour les comparer
# ensuite avec la table. sum(1 for _ in f) ajoute 1 pour chaque ligne du
# fichier (une façon compacte de compter les lignes) ; - 1 retire la
# ligne d'en-tête (id,login), qui n'est pas une donnée.
# ---------------------------------------------------------------------
def count_csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # moins la ligne d'en-tête


# ---------------------------------------------------------------------
# def copy_csv(cur, table, columns, path) -> None:
#
# COPY est la commande de CHARGEMENT EN MASSE de PostgreSQL : bien plus
# rapide qu'un INSERT par rangée, car les données arrivent en un seul flux
# continu.
#
#   COPY actor (id, login) FROM STDIN WITH (FORMAT csv, HEADER true)
#     FROM STDIN    les données arrivent par la connexion (« entrée
#                   standard »), envoyées par Python, au lieu d'être lues
#                   dans un fichier sur le serveur. Le serveur n'a jamais
#                   besoin d'accéder à vos fichiers.
#     FORMAT csv    les données sont au format CSV.
#     HEADER true   ignorer la première ligne (les noms des colonnes).
#
# cur.copy(...) ouvre ce flux ; copy.write(chunk) y envoie des données.
#
# `with A as f, B as copy:` — deux `with` sur une seule ligne ; la barre
# oblique inverse \ en fin de ligne signifie simplement « l'instruction
# continue à la ligne suivante ».
#
# while chunk := f.read(1024 * 1024):
#   f.read(1024 * 1024) lit jusqu'à 1 Mo du fichier à la fois, donc même
#   un fichier énorme n'a jamais besoin de tenir en mémoire d'un seul coup.
#   `:=` (l'« opérateur morse ») affecte ET teste en une seule fois :
#   « lire un morceau, le ranger dans `chunk`, et continuer la boucle tant
#   qu'il n'est pas vide ». À la fin du fichier, f.read() renvoie ""
#   (vide), et la boucle s'arrête.
# ---------------------------------------------------------------------
def copy_csv(cur: psycopg.Cursor, table: str, columns: str, path: Path) -> None:
    # COPY ... FROM STDIN : Python envoie le contenu du fichier par la connexion,
    # donc le serveur PostgreSQL n'a jamais besoin d'accéder au fichier lui-même.
    with open(path, "r", encoding="utf-8") as f, \
         cur.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
        while chunk := f.read(1024 * 1024):
            copy.write(chunk)


# ---------------------------------------------------------------------
# def seconds_since(start) -> str:
#
# time.perf_counter() renvoie un nombre de secondes depuis un point de
# départ arbitraire. Seul, il ne veut rien dire, mais la DIFFÉRENCE entre
# deux appels est exactement le temps écoulé entre les deux. C'est
# l'horloge faite pour mesurer des durées : la plus précise, et elle n'est
# pas affectée si l'heure de l'ordinateur change.
#
#     start = time.perf_counter()
#     ...something...
#     seconds_since(start)   # e.g. "  0.12 s"
#
# :6.2f — un nombre de 6 caractères de large avec 2 décimales, pour que
# les durées soient alignées en colonne.
# ---------------------------------------------------------------------
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir) -> bool:
#
# Fait tout le travail et renvoie True si chaque table a fini avec
# exactement autant de rangées que son fichier CSV.
#
# conn.cursor() — un CURSEUR est l'objet qui sert à envoyer du SQL par la
# connexion et à lire les réponses (check_connections.py utilisait le
# raccourci conn.execute(), qui en crée un en coulisses).
#
# TRANSACTIONS : avec psycopg, tout ce qui est envoyé par une connexion
# fait partie d'une seule TRANSACTION, un groupe de modifications qui ont
# TOUTES lieu ou AUCUNE. Tant que conn.commit() n'est pas appelé, rien
# n'est enregistré définitivement : si le script plantait à mi-chemin,
# PostgreSQL annulerait tout et les tables seraient comme avant. C'est
# pourquoi un chargement à moitié fini ne peut jamais rester en place.
# ---------------------------------------------------------------------
def load(csv_dir: Path) -> bool:
    all_match = True
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        with conn.cursor() as cur:
            # Le total commence ici, une fois connecté : la connexion ne
            # fait pas partie du chargement.
            load_start = time.perf_counter()

            # Chaque étape est chronométrée séparément : prendre l'heure,
            # faire l'étape, afficher combien de temps elle a pris.
            step = time.perf_counter()
            cur.execute(SCHEMA)
            print(f"Tables created: actor, repo, actor_repo        {seconds_since(step)}")

            for table, columns, csv_name in TABLES:
                step = time.perf_counter()
                copy_csv(cur, table, columns, csv_dir / csv_name)
                print(f"Loaded {table:<12} from {csv_name:<16}  {seconds_since(step)}")

            # ---------------------------------------------------------
            # ANALYZE
            #
            # Avant d'exécuter une requête, le PLANIFICATEUR de PostgreSQL
            # décide COMMENT l'exécuter (utiliser un index ou lire toute
            # la table ? quelle table d'abord ?). Pour bien décider, il
            # s'appuie sur des STATISTIQUES sur les données : combien de
            # rangées, comment les valeurs sont réparties. Juste après un
            # chargement en masse, ces statistiques sont périmées, donc
            # ANALYZE les rafraîchit. Pour le benchmark, cela signifie
            # que le côté relationnel est mesuré sur des requêtes bien
            # planifiées — cela fait partie du fait de donner à chaque
            # côté ses aides habituelles.
            # ---------------------------------------------------------
            # Rafraîchir les statistiques du planificateur pour planifier les requêtes sur les vraies données.
            step = time.perf_counter()
            cur.execute("ANALYZE actor; ANALYZE repo; ANALYZE actor_repo;")
            print(f"Statistics refreshed (ANALYZE)                 {seconds_since(step)}")

            # COMMIT enregistre la transaction définitivement. Il est fait
            # ici, avant d'arrêter le chronomètre, pour que le total
            # inclue l'enregistrement des données, mais pas les
            # vérifications qui suivent.
            # Valider ici, pour que le total couvre l'enregistrement des données mais pas les vérifications.
            conn.commit()
            print(f"Total load time                                {seconds_since(load_start)}")

            # ---------------------------------------------------------
            # La vérification : compter les rangées de chaque table et
            # les comparer avec le CSV. SELECT count(*) FROM actor
            # compte les rangées ; .fetchone()[0] prend l'unique nombre
            # de la réponse.
            #
            # all_match = all_match and in_db == in_csv
            #   all_match commence à True et devient False dès qu'une
            #   table ne correspond pas (et reste False : False and
            #   n'importe quoi vaut False).
            # ---------------------------------------------------------
            print("\nRows loaded (database vs. CSV file):")
            for table, _, csv_name in TABLES:
                in_db = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                in_csv = count_csv_rows(csv_dir / csv_name)
                status = "OK" if in_db == in_csv else "MISMATCH"
                all_match = all_match and in_db == in_csv
                print(f"  {table:<12} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args() : même schéma que dans extract_csv.py ; --csv-dir permet
# de charger depuis un autre dossier.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    return parser.parse_args()


# main() : si les décomptes ne correspondent pas, sys.exit("...") affiche
# le message et termine avec un code de sortie d'échec (voir
# check_connections.py).
def main() -> None:
    args = parse_args()
    if not load(args.csv_dir):
        sys.exit("Some row counts don't match their CSV file.")
    print("\nPostgreSQL load complete.")


# main() et la garde `if __name__ == "__main__":` : voir la copie annotée
# de download_gharchive.py.
if __name__ == "__main__":
    main()
