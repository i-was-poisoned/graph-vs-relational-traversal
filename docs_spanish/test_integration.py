########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_integration.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar. El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_integration.py, y es ese el que ejecuta pytest.
#
# Este archivo asume que ya has leído docs_spanish/test_extract_csv.py
# (qué es una prueba de pytest, `assert`, las fixtures) y los cargadores
# docs_spanish/load_postgres.py y docs_spanish/load_neo4j.py. Aquí se
# explica lo NUEVO.
#
# UNITARIA FRENTE A INTEGRACIÓN. Las pruebas unitarias comprueban cada
# pieza por separado, sin bases de datos. Estas comprueban que las piezas
# funcionan JUNTAS y con bases de datos DE VERDAD:
#     eventos -> extract_csv -> CSV -> load_postgres y load_neo4j
#             -> PostgreSQL y Neo4j
# Se escriben con pytest igual que las unitarias (funciones test_...,
# assert); lo que cambia es que dentro se conectan a servidores reales.
#
# Se ejecutan aparte, con:
#     ./run.sh -m pytest -m integration    (contra tus servidores)
#     ./simulate_ci.sh                     (en contenedores Docker)
########################################################################

"""Integration tests: load the same tiny data set into real PostgreSQL and Neo4j databases.

These tests need both servers running, so they're kept apart from the unit tests
(marker "integration") and don't run with a plain "python -m pytest".

Run with:
    ./run.sh -m pytest -m integration      # locally (passwords from secrets.sh)

The databases used are a separate test database on each side, never the
benchmark's "gharchive" or the pipeline's "gharchive24h":
    TEST_POSTGRES_DATABASE   default "gharchivetest" (created if missing)
    TEST_NEO4J_DATABASE      default "gharchivetest" (created if missing; in CI
                             "neo4j", the only database Neo4j Community allows)
"""

# json: para escribir los eventos de prueba como texto JSON (json.dumps),
# un evento por línea, igual que los archivos de GH Archive.
import json

# os: para leer variables de entorno (os.environ), como en los cargadores.
import os

# time: para medir cuánto llevamos esperando a Neo4j y para hacer pausas
# (time.sleep) entre intentos.
import time

from pathlib import Path

# psycopg: el conector de PostgreSQL. Aquí lo usamos directamente para
# crear la base de datos de prueba y para CONSULTAR lo que se ha cargado.
import psycopg

# pytest: lo importamos porque usamos dos cosas suyas explícitamente:
# las marcas (pytest.mark) y el decorador de fixtures (@pytest.fixture).
import pytest

# GraphDatabase: el conector de Neo4j, el mismo que usa load_neo4j.py.
from neo4j import GraphDatabase

# sql: la parte de psycopg que construye SQL de forma SEGURA cuando un
# NOMBRE (de una base de datos, de una tabla) va dentro de la consulta.
from psycopg import sql

# Los tres scripts del proyecto que se prueban juntos. Se importan por su
# nombre gracias a `pythonpath = scripts` de pytest.ini.
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# pytestmark: un nombre ESPECIAL. Si un archivo de pruebas define una
# variable llamada exactamente `pytestmark`, pytest aplica esa marca a
# TODAS las pruebas del archivo de una vez. Así no hay que escribir
# @pytest.mark.integration encima de cada una de las seis.
#
# La marca `integration` está registrada en pytest.ini, y allí
# `addopts = -m "not integration"` hace que `python -m pytest` se las
# salte. Con `python -m pytest -m integration` se ejecutan solo estas.
# ---------------------------------------------------------------------
pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------
# os.environ.get("NOMBRE", "valor por defecto"): lee una variable de
# entorno, y si NO existe, devuelve el segundo argumento en lugar de dar
# error. (Compara con os.environ["NOMBRE"], con corchetes, que da un
# KeyError si la variable no existe.)
#
# Así, en tu ordenador se usa "gharchivetest" sin configurar nada, y el
# CI puede elegir otra (TEST_NEO4J_DATABASE=neo4j) sin cambiar el código.
# ---------------------------------------------------------------------
POSTGRES_DATABASE = os.environ.get("TEST_POSTGRES_DATABASE", "gharchivetest")
NEO4J_DATABASE = os.environ.get("TEST_NEO4J_DATABASE", "gharchivetest")

# Las bases de datos que estas pruebas NUNCA deben tocar: el benchmark
# congelado y la pipeline de 24 horas. Es un conjunto (set, con llaves):
# solo nos interesa preguntar "¿está este nombre dentro?" con `in`.
PROTECTED_DATABASES = {"gharchive", "gharchive24h"}

# ---------------------------------------------------------------------
# Los datos de prueba: 8 eventos inventados, con SOLO los campos que lee
# extract_csv.py. Están elegidos para que aparezcan a la vez todos los
# casos difíciles conocidos:
#   - Ana (1) y Bea (2) en el mismo repo 10 -> quedan a 2 saltos;
#   - Bea en el repo 20 DOS veces -> par repetido, una sola conexión;
#   - Carl (3) primero como "carl" y después como "carl-dev" -> login
#     renombrado, se queda el más reciente;
#   - dependabot[bot] -> bot, no se carga;
#   - Dan (4) con "repo": {} -> repo vacío, no se carga.
# ---------------------------------------------------------------------
# Ana (1) and Bea (2) both work on repo 10; Bea also on 20; Carl (3) only on 30.
# Plus the known hard cases: a bot, an empty repo, a repeated pair and a renamed login.
EVENTS = [
    {"actor": {"id": 1, "login": "ana"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:00:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:01:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:02:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:03:00Z"},
    {"actor": {"id": 3, "login": "carl"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:04:00Z"},
    {"actor": {"id": 3, "login": "carl-dev"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:05:00Z"},
    {"actor": {"id": 9, "login": "dependabot[bot]"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:06:00Z"},
    {"actor": {"id": 4, "login": "dan"}, "repo": {}, "created_at": "2026-08-27T15:07:00Z"},
]

# Lo que DEBE haber en las dos bases de datos después de cargar esos 8
# eventos. Son conjuntos de TUPLAS: cada tupla es una fila, por ejemplo
# (1, "ana") = (id, login). Se usan conjuntos porque una base de datos no
# garantiza el ORDEN de las filas: comparando conjuntos, el orden da igual
# y solo importa QUÉ filas hay.
EXPECTED_ACTORS = {(1, "ana"), (2, "bea"), (3, "carl-dev")}
EXPECTED_REPOS = {(10, "ana/project"), (20, "bea/tool"), (30, "carl/notes")}
EXPECTED_PAIRS = {(1, 10), (2, 10), (2, 20), (3, 30)}


# ---------------------------------------------------------------------
# Una función auxiliar que crea un "driver" (la conexión de Neo4j) con la
# misma dirección y el mismo usuario que load_neo4j.py: así las pruebas
# hablan con el MISMO servidor que el cargador. La contraseña se lee de
# NEO4J_PASSWORD (con corchetes: si falta, error inmediato y claro).
# ---------------------------------------------------------------------
def neo4j_driver():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# wait_for_neo4j: un BUCLE DE REINTENTOS. En el CI, el contenedor de
# Neo4j tarda unos segundos en arrancar; si la prueba intentara
# conectarse enseguida, fallaría aunque todo esté bien. Así que lo
# intentamos cada 2 segundos, hasta un máximo de 90.
#
# time.monotonic(): un reloj que SOLO avanza (nunca salta hacia atrás,
# aunque alguien cambie la hora del ordenador). Es el adecuado para medir
# "cuánto tiempo ha pasado". `deadline` es el momento límite.
#
# try / except / raise:
#   - try: intentamos conectarnos. Si funciona, `return` sale de la
#     función: Neo4j está listo.
#   - except Exception: si falla (cualquier error), no nos rendimos
#     todavía...
#   - ...salvo que ya se haya pasado el límite: entonces `raise`, SIN
#     nada detrás, vuelve a lanzar EL MISMO error que acabamos de
#     capturar. Así la prueba falla mostrando el error real de Neo4j, y
#     no uno inventado por nosotros.
#   - si aún queda tiempo, time.sleep(2) espera 2 segundos y el
#     `while True` vuelve a empezar.
# ---------------------------------------------------------------------
def wait_for_neo4j(timeout_seconds: int = 90) -> None:
    # In CI the Neo4j container takes a few seconds to start accepting connections.
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            with neo4j_driver() as driver:
                driver.verify_connectivity()
            return
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(2)


# ---------------------------------------------------------------------
# ensure_test_databases: crea las bases de datos de prueba si no existen.
# Es la misma técnica que ensure_databases de pipeline.py.
#
# PostgreSQL:
#   - Nos conectamos a la base "postgres" (la que existe siempre), porque
#     no podemos conectarnos a una base que aún no existe.
#   - autocommit=True: normalmente psycopg agrupa las órdenes en una
#     TRANSACCIÓN; pero PostgreSQL NO permite CREATE DATABASE dentro de
#     una transacción. Con autocommit, cada orden se aplica sola, al
#     momento.
#   - Preguntamos al catálogo pg_database si ya hay una con ese nombre.
#     El %s es un PARÁMETRO: psycopg mete el valor de forma segura.
#   - fetchone() devuelve una fila o None si no hay ninguna: None = no
#     existe, así que la creamos.
#   - ¿Por qué sql.SQL(...).format(sql.Identifier(...)) y no %s? Porque
#     %s sirve para VALORES (un texto, un número), no para NOMBRES de
#     bases de datos o tablas. sql.Identifier pone el nombre entre
#     comillas dobles y lo escapa, de forma segura.
#
# Neo4j:
#   - La base "neo4j" existe siempre. Cualquier otro nombre hay que
#     crearlo con CREATE DATABASE, que se envía a la base "system" (la que
#     administra las demás). Solo funciona en la Enterprise Edition (la de
#     Neo4j Desktop); en el CI (Community) usamos "neo4j", así que este
#     paso se salta.
#   - IF NOT EXISTS: no da error si ya existe. WAIT: espera a que esté
#     lista antes de seguir.
# ---------------------------------------------------------------------
def ensure_test_databases() -> None:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname="postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DATABASE,)).fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(POSTGRES_DATABASE)))
    # "neo4j" always exists; any other name needs CREATE DATABASE (Enterprise Edition only).
    if NEO4J_DATABASE != "neo4j":
        with neo4j_driver() as driver:
            driver.execute_query(f"CREATE DATABASE `{NEO4J_DATABASE}` IF NOT EXISTS WAIT", database_="system")


# Carga la misma carpeta de CSV en las dos bases de datos, con las
# funciones load() de los cargadores REALES, y devuelve una tupla con lo
# que devuelve cada una: True si sus conteos coinciden con los CSV.
def load_both(csv_dir: Path) -> tuple[bool, bool]:
    return load_postgres.load(csv_dir, POSTGRES_DATABASE), load_neo4j.load(csv_dir, NEO4J_DATABASE)


# Ejecuta una consulta SQL en la base de prueba y devuelve las filas como
# un CONJUNTO de tuplas. fetchall() da una lista de tuplas; set(...) la
# convierte en conjunto, para comparar sin importar el orden.
def postgres_rows(query: str) -> set[tuple]:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname=POSTGRES_DATABASE) as conn:
        return set(conn.execute(query).fetchall())


# Lo mismo para Neo4j. `**params` recoge parámetros con nombre (por
# ejemplo id=1) en un diccionario, que se envía junto a la consulta
# Cypher ($id dentro de la consulta).
# Cada `record` es una fila de resultado; record.values() da sus valores
# en orden, y tuple(...) los convierte en una tupla. Así el resultado
# tiene EXACTAMENTE la misma forma que el de postgres_rows, y los dos se
# pueden comparar con ==.
def neo4j_rows(query: str, **params) -> set[tuple]:
    with neo4j_driver() as driver:
        records, _, _ = driver.execute_query(query, params, database_=NEO4J_DATABASE)
    return {tuple(record.values()) for record in records}


# ---------------------------------------------------------------------
# FIXTURE CON scope="module". Las fixtures de las pruebas unitarias
# (tmp_path) se preparan DE NUEVO para cada prueba. Aquí eso sería lento:
# cargar las dos bases de datos seis veces. Con scope="module", la
# fixture se prepara UNA SOLA VEZ para todo el archivo (un "módulo" de
# Python = un archivo .py), y todas las pruebas reciben el mismo valor.
#
# tmp_path_factory: la "fábrica" de carpetas temporales. tmp_path solo
# vale para una prueba; para una fixture de módulo hay que pedir la
# fábrica y crear la carpeta con mktemp("nombre").
#
# Qué hace csv_dir, en orden:
#   1. la PROTECCIÓN: si alguien configurara gharchive o gharchive24h
#      como base de prueba, el assert falla ANTES de tocar nada. El texto
#      después de la coma es el mensaje que se mostraría. {...!r} muestra
#      el valor con sus comillas, para que se vea exactamente cuál era;
#   2. escribe los 8 eventos en events.json (un JSON por línea);
#   3. ejecuta el extract_csv REAL y escribe los tres CSV;
#   4. espera a Neo4j y crea las bases de prueba si hace falta;
#   5. devuelve la carpeta, que reciben las fixtures/pruebas que la pidan.
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory) -> Path:
    # Safety guard: these tests empty the databases they load into.
    assert POSTGRES_DATABASE not in PROTECTED_DATABASES, f"refusing to use {POSTGRES_DATABASE!r}"
    assert NEO4J_DATABASE not in PROTECTED_DATABASES, f"refusing to use {NEO4J_DATABASE!r}"

    folder = tmp_path_factory.mktemp("integration")
    events_file = folder / "events.json"
    events_file.write_text("".join(json.dumps(event) + "\n" for event in EVENTS), encoding="utf-8")
    actors, repos, pairs, _ = extract_csv.extract([events_file])
    extract_csv.write_all(folder, actors, repos, pairs)

    wait_for_neo4j()
    ensure_test_databases()
    return folder


# ---------------------------------------------------------------------
# UNA FIXTURE QUE DEPENDE DE OTRA. `loaded` pide `csv_dir` poniéndolo
# como parámetro, igual que una prueba pide tmp_path. pytest prepara
# primero csv_dir y luego se lo pasa a loaded. Las dos son de módulo: se
# carga UNA vez, y las pruebas que piden `loaded` reciben la tupla
# (postgres_ok, neo4j_ok).
# Funciona porque las pruebas de abajo SOLO LEEN (la última vuelve a
# cargar, pero los mismos datos: el resultado no cambia).
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def loaded(csv_dir) -> tuple[bool, bool]:
    # Loaded once and shared by the tests below, which only read.
    return load_both(csv_dir)


# Prueba 1. load() de cada cargador ya compara sus conteos con los CSV y
# devuelve True/False: aquí comprobamos que las DOS cargas dijeron True.
# `postgres_ok, neo4j_ok = loaded` "desempaqueta" la tupla en dos nombres.
def test_both_loads_match_their_csv_files(loaded):
    postgres_ok, neo4j_ok = loaded
    assert postgres_ok
    assert neo4j_ok


# Pruebas 2, 3 y 4. Las dos bases de datos tienen EXACTAMENTE las mismas
# filas, y son las esperadas. Fíjate en que el resultado de SQL y el de
# Cypher tienen la misma forma (conjunto de tuplas), así que se comparan
# con el mismo EXPECTED_... Estas pruebas reciben `loaded` aunque no lo
# usen dentro: pedirlo GARANTIZA que la carga ya se ha hecho.
def test_both_databases_hold_the_same_actors(loaded):
    assert postgres_rows("SELECT id, login FROM actor") == EXPECTED_ACTORS
    assert neo4j_rows("MATCH (a:Actor) RETURN a.id, a.login") == EXPECTED_ACTORS


def test_both_databases_hold_the_same_repos(loaded):
    assert postgres_rows("SELECT id, name FROM repo") == EXPECTED_REPOS
    assert neo4j_rows("MATCH (r:Repo) RETURN r.id, r.name") == EXPECTED_REPOS


def test_both_databases_hold_the_same_connections(loaded):
    assert postgres_rows("SELECT actor_id, repo_id FROM actor_repo") == EXPECTED_PAIRS
    assert neo4j_rows("MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo) RETURN a.id, r.id") == EXPECTED_PAIRS


# ---------------------------------------------------------------------
# Prueba 5: LA MISMA PREGUNTA EN LOS DOS MODELOS. "¿Quién trabajó en un
# repo donde también trabajó Ana (1)?" Son 2 saltos: actor -> repo ->
# otro actor. Es un anticipo del benchmark: antes de medir cuánto tarda
# cada uno, hay que estar seguro de que los dos responden LO MISMO.
#
# En SQL: un SELF-JOIN, la tabla actor_repo unida CONSIGO MISMA. Le damos
# dos alias, `mine` (las filas de Ana) y `other` (las de los demás), y
# las unimos por el repo en común (other.repo_id = mine.repo_id).
# `other.actor_id <> 1` quita a la propia Ana. DISTINCT evita repetir a
# alguien que coincida con Ana en varios repos.
#
# En Cypher: el mismo recorrido se DIBUJA como un patrón:
#   (:Actor {id: $id})-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(other:Actor)
#   Ana ------------------ trabajó en ---> repo <--- trabajó en ---- otro
# La flecha de la derecha va hacia la IZQUIERDA (<-) porque la relación
# va del otro actor al repo. $id es un parámetro (id=1).
#
# `assert a == b == {(2,)}` es una comparación ENCADENADA: Python la lee
# como `a == b and b == {(2,)}`. Las dos respuestas son iguales entre sí
# Y son exactamente Bea. {(2,)} es un conjunto con una tupla de UN
# elemento: la coma de (2,) es lo que la convierte en tupla.
# ---------------------------------------------------------------------
def test_same_traversal_answer_on_both_sides(loaded):
    # Who worked on a repo that Ana (1) also worked on? Two hops: actor -> repo -> actor.
    postgres_answer = postgres_rows("""
        SELECT DISTINCT other.actor_id
        FROM actor_repo AS mine
        JOIN actor_repo AS other ON other.repo_id = mine.repo_id
        WHERE mine.actor_id = 1 AND other.actor_id <> 1
    """)
    neo4j_answer = neo4j_rows("""
        MATCH (:Actor {id: $id})-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(other:Actor)
        WHERE other.id <> $id
        RETURN DISTINCT other.id
    """, id=1)
    assert postgres_answer == neo4j_answer == {(2,)}


# ---------------------------------------------------------------------
# Prueba 6: IDEMPOTENCIA. Una operación es idempotente si hacerla dos
# veces da el mismo resultado que hacerla una. Los cargadores empiezan
# siempre desde cero (PostgreSQL borra y crea las tablas; Neo4j borra
# todos los nodos), así que una segunda carga no debe DUPLICAR nada.
# Es importante para la pipeline, que vuelve a cargar cada hora.
# Esta prueba pide `loaded` (la primera carga) y `csv_dir` (para cargar
# otra vez), y después cuenta las conexiones en los dos lados: deben
# seguir siendo 4. {(4,)}: count(*) devuelve una fila con un solo valor.
# ---------------------------------------------------------------------
def test_loading_twice_gives_the_same_result(loaded, csv_dir):
    # Each load starts from empty tables/graph, so a second run must not duplicate anything.
    assert load_both(csv_dir) == (True, True)
    assert postgres_rows("SELECT count(*) FROM actor_repo") == {(len(EXPECTED_PAIRS),)}
    assert neo4j_rows("MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e)") == {(len(EXPECTED_PAIRS),)}
