########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/load_neo4j.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive
# en docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script
# real y "limpio" (sin nada de este comentario) es scripts/load_neo4j.py.
#
# Este archivo asume que ya has leído los scripts anotados anteriores,
# sobre todo check_connections.py (el driver de Neo4j, execute_query,
# NEO4J_PASSWORD) y load_postgres.py (el lado PostgreSQL del mismo
# trabajo, y time.perf_counter()). Este archivo se centra en lo que es
# NUEVO: Cypher para crear nodos y aristas (CREATE, MATCH, UNWIND,
# parámetros), las RESTRICCIONES de unicidad, leer un CSV como
# diccionarios con csv.DictReader, y enviar los datos por LOTES.
#
# QUÉ HAY DE NUEVO en esta versión: igual que en load_postgres.py, puedes
# elegir EN QUÉ base de datos cargar (--database, o el parámetro
# `database` de load()). La de por defecto sigue siendo "gharchive", la
# base de datos congelada del benchmark; el pipeline en vivo de 24 horas
# (pipeline.py) carga en "gharchive24h", así que nunca toca los datos
# del benchmark.
#
# Ejecútalo a través de run.sh (necesita NEO4J_PASSWORD):
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

# Todo ya explicado en los scripts anteriores (csv en extract_csv.py, time
# en load_postgres.py, GraphDatabase y os en check_connections.py).
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
# DEFAULT_DATABASE = "gharchive" — la decisión del proyecto: el
# benchmark trabaja siempre en la base de datos llamada gharchive, en los
# dos lados. check_connections.py no indicaba ninguna base de datos, así
# que usaba la predeterminada de la instancia ("neo4j"). Aquí cada
# consulta pasa database_=... de forma explícita.
#
# NUEVO: esta constante antes se llamaba NEO4J_DATABASE y la usaban
# directamente todas las consultas. Ahora es DEFAULT_DATABASE (el mismo
# nombre que en load_postgres.py) porque solo es el valor POR DEFECTO:
# load() recibe un parámetro `database`, y el pipeline en vivo pasa
# "gharchive24h".
#
# ¿Por qué "gharchive24h" y no "gharchive_24h"? Los nombres de base de
# datos de Neo4j solo pueden contener letras, dígitos, puntos (.) y
# guiones (-) — NADA de guiones bajos —, así que "gharchive_24h" sería
# rechazado. En el lado de PostgreSQL se usa también el mismo nombre,
# para que los dos coincidan.
#
# BATCH_SIZE = 5000 — cuántas filas van en cada petición (ver
# run_in_batches()).
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"
DEFAULT_DATABASE = "gharchive"
BATCH_SIZE = 5000

# ---------------------------------------------------------------------
# CONSTRAINTS — el equivalente en Neo4j de la PRIMARY KEY de PostgreSQL
#
# CREATE CONSTRAINT actor_id_unique IF NOT EXISTS
#     FOR (a:Actor) REQUIRE a.id IS UNIQUE
#
#   "Para cada nodo con la etiqueta Actor, la propiedad id tiene que ser
#   única." Igual que una clave primaria, también crea un ÍNDICE sobre
#   esa propiedad, así que encontrar un actor por su id es instantáneo —
#   algo en lo que se apoya el paso de las aristas, más abajo.
#   IF NOT EXISTS: en una segunda ejecución la restricción ya existe, y
#   esto simplemente no hace nada (en lugar de fallar).
#
# Fíjate en que NO hay ningún índice para las aristas: en un grafo, cada
# nodo ya guarda enlaces directos a sus propias aristas ("index-free
# adjacency", adyacencia sin índices). Esa es justo la ventaja que el
# benchmark quiere medir frente a los índices de actor_repo de
# PostgreSQL.
# ---------------------------------------------------------------------
CONSTRAINTS = [
    "CREATE CONSTRAINT actor_id_unique IF NOT EXISTS FOR (a:Actor) REQUIRE a.id IS UNIQUE",
    "CREATE CONSTRAINT repo_id_unique IF NOT EXISTS FOR (r:Repo) REQUIRE r.id IS UNIQUE",
]

# ---------------------------------------------------------------------
# Las consultas Cypher que crean los datos
#
# Cypher es el lenguaje de consultas de Neo4j. "Dibuja" el grafo con
# símbolos:
#   (a:Actor {id: 19})        un NODO: paréntesis, una etiqueta (:Actor)
#                             y propiedades entre llaves
#   -[:INTERACTED_WITH]->     una ARISTA: corchetes, un tipo y una
#                             flecha que indica su dirección
#
# $rows es un PARÁMETRO: un hueco cuyo valor Python envía por separado
# (aquí, una lista de diccionarios). Enviar los datos como parámetros, en
# lugar de pegarlos en el texto de la consulta, es más seguro y permite
# que Neo4j reutilice el mismo plan de consulta para cada lote.
#
# UNWIND $rows AS row
#   Toma la LISTA y la convierte en una fila por elemento, así que el
#   resto de la consulta se ejecuta una vez por elemento — como un bucle
#   `for row in rows:`, pero dentro de la base de datos, en una sola
#   petición.
#
# CREATE (:Actor {id: row.id, login: row.login})
#   Crea un nodo por fila. row.id lee la clave "id" del diccionario.
#
# CREATE_EDGES hace más trabajo por cada fila:
#   MATCH (a:Actor {id: row.actor_id})   BUSCA el actor con ese id
#   MATCH (r:Repo {id: row.repo_id})     BUSCA el repo con ese id
#   CREATE (a)-[:INTERACTED_WITH]->(r)   crea la arista entre ellos
# Los dos MATCH son instantáneos gracias a los índices de las
# restricciones.
#
# ¿Por qué el nombre INTERACTED_WITH ("interactuó con")? Las conexiones
# vienen de todo tipo de eventos (pushes, comentarios, estrellas...), y
# dar una estrella o comentar no es "contribuir", así que un nombre
# neutro es más exacto.
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
# COUNTS — las consultas para la comprobación final: (etiqueta, consulta,
# archivo CSV).
#   MATCH (a:Actor) RETURN count(a) AS n           cuántos nodos Actor
#   MATCH ()-[e:INTERACTED_WITH]->() RETURN ...    cuántas aristas; ()
#                                                  es "cualquier nodo"
# `AS n` da nombre a la columna del resultado, para que Python pueda
# leerla como record["n"].
# ---------------------------------------------------------------------
COUNTS = [
    ("Actor nodes", "MATCH (a:Actor) RETURN count(a) AS n", "actors.csv"),
    ("Repo nodes", "MATCH (r:Repo) RETURN count(r) AS n", "repos.csv"),
    ("INTERACTED_WITH edges", "MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e) AS n", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def read_csv(path, int_columns) -> list[dict]:
#
# csv.DictReader lee un archivo CSV y devuelve cada fila como un
# DICCIONARIO cuyas claves son los nombres de columna de la cabecera:
#
#     id,login            ->   {"id": "19", "login": "brynary"}
#     19,brynary
#
# Un CSV es solo texto, así que cada valor sale como un STRING ("19").
# Después, el bucle convierte las columnas de id en números con int(),
# para que Neo4j los guarde como enteros, exactamente igual que el
# BIGINT de PostgreSQL. Si un lado guardara los ids como texto y el otro
# como números, los datos no serían realmente idénticos.
#
# int_columns: tuple[str, ...] — una tupla de nombres de columna de
# cualquier longitud; los `...` significan "cualquier cantidad de str".
# ("id",) con una coma al final es una tupla con UN solo elemento (sin
# la coma, ("id") sería simplemente el string "id").
# ---------------------------------------------------------------------
def read_csv(path: Path, int_columns: tuple[str, ...]) -> list[dict]:
    # csv.DictReader devuelve cada fila como un diccionario con los
    # nombres de columna de la cabecera como claves. Los ids se convierten
    # a int, para que se guarden como números, igual que en PostgreSQL.
    with open(path, "r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for column in int_columns:
            row[column] = int(row[column])
    return rows


# ---------------------------------------------------------------------
# def run_in_batches(driver, query, rows, database) -> None:
#
# En lugar de enviar 15.053 filas en una sola petición enorme, las envía
# en LOTES de BATCH_SIZE (5.000): las peticiones más pequeñas usan menos
# memoria en los dos lados y no corren el riesgo de superar un límite de
# tamaño.
#
# range(0, len(rows), BATCH_SIZE) cuenta de 5.000 en 5.000:
#     0, 5000, 10000, 15000
# rows[start:start + BATCH_SIZE] es un TROZO (slice) de 5.000 filas (el
# último puede ser más corto): rows[0:5000], rows[5000:10000], ...
#
# rows=... se envía como el parámetro $rows de la consulta.
# database_= lleva un guion bajo al final para que no se confunda con un
# parámetro de la consulta que casualmente se llamara "database".
#
# NUEVO: `database` es ahora un parámetro (lo pasa load()) en lugar de
# la constante fija, así que los lotes van a la base de datos que se le
# haya pedido llenar a load(). Fíjate en los dos nombres distintos de esa
# línea:
#   database_=database   la opción del driver (con _) = nuestra variable.
#
# El COPY de PostgreSQL lo envía todo como un único flujo continuo; Neo4j
# lo recibe por lotes. Las dos son la forma habitual de hacer una carga
# masiva en cada base de datos.
# ---------------------------------------------------------------------
def run_in_batches(driver, query: str, rows: list[dict], database: str) -> None:
    # Envía las filas unos pocos miles cada vez, en lugar de todas en una
    # sola petición enorme.
    for start in range(0, len(rows), BATCH_SIZE):
        driver.execute_query(query, rows=rows[start:start + BATCH_SIZE], database_=database)


# La misma función auxiliar de tiempo que en load_postgres.py — ver su
# copia anotada.
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir, database=DEFAULT_DATABASE) -> bool:
#
# NUEVO: el parámetro `database`, con la misma idea que en
# load_postgres.py. Por defecto vale DEFAULT_DATABASE ("gharchive"), así
# que load(csv_dir) se comporta exactamente como antes. Todas las
# consultas de abajo usan ahora database_=database, y a run_in_batches()
# se le pasa el mismo nombre, así que TODO el trabajo (vaciar,
# restricciones, cargar, contar) ocurre en la base de datos elegida.
#
# Una diferencia con PostgreSQL: aquí el driver se conecta al SERVIDOR
# de Neo4j (NEO4J_URI) y la base de datos se elige en cada consulta, con
# database_=...; en psycopg la base de datos se elige una sola vez, al
# conectar.
# ---------------------------------------------------------------------
def load(csv_dir: Path, database: str = DEFAULT_DATABASE) -> bool:
    # La lectura de los CSV en Python se cronometra por separado y se deja
    # FUERA del total: es preparación, no carga en la base de datos.
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
        #   MATCH (n)   todos los nodos de la base de datos
        #   DETACH      primero quita las aristas de cada nodo...
        #   DELETE n    ...y después el propio nodo (Neo4j no borra un
        #               nodo que todavía tiene aristas).
        # El equivalente en Neo4j del DROP TABLE de PostgreSQL: cada
        # ejecución empieza con la base de datos vacía.
        # -------------------------------------------------------------
        step = time.perf_counter()
        driver.execute_query("MATCH (n) DETACH DELETE n", database_=database)
        for constraint in CONSTRAINTS:
            driver.execute_query(constraint, database_=database)
        print(f"Database emptied; unique constraints in place   {seconds_since(step)}")

        # -------------------------------------------------------------
        # Las tres cargas, en un bucle sobre tuplas (etiqueta, consulta,
        # filas). El ORDEN importa, igual que en PostgreSQL: primero los
        # nodos, porque cada arista necesita ENCONTRAR su actor y su repo
        # (los MATCH de CREATE_EDGES). Cada paso se cronometra por
        # separado.
        # -------------------------------------------------------------
        # Primero los nodos: el paso de las aristas busca cada actor y
        # cada repo por su id.
        for label, query, rows in (("Actor nodes", CREATE_ACTORS, actors),
                                   ("Repo nodes", CREATE_REPOS, repos),
                                   ("INTERACTED_WITH edges", CREATE_EDGES, edges)):
            step = time.perf_counter()
            run_in_batches(driver, query, rows, database)
            print(f"Created {label:<22}                  {seconds_since(step)}")

        # Aquí no hay commit explícito: execute_query() confirma cada
        # petición por su cuenta, así que los datos ya están guardados.
        print(f"Total load time                                 {seconds_since(load_start)}")

        # -------------------------------------------------------------
        # La comprobación, con la misma idea que load_postgres.py:
        # contar en la base de datos y comparar con el CSV.
        # records[0]["n"] lee la columna "n" de la primera (y única)
        # fila del resultado.
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


# parse_args() y main(): igual que en load_postgres.py, incluida la NUEVA
# opción --database (p. ej. --database gharchive24h).
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


# Ver la copia anotada de download_gharchive.py para la protección
# __name__.
if __name__ == "__main__":
    main()
