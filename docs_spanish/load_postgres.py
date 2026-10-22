########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/load_postgres.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive
# en docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script
# real y "limpio" (sin nada de este comentario) es scripts/load_postgres.py.
#
# Este archivo asume que ya has leído los scripts anotados anteriores,
# sobre todo check_connections.py (psycopg, la conexión, `with`,
# PGPASSWORD) y extract_csv.py (los archivos CSV que carga este script).
# Este archivo se centra en lo que es NUEVO: SQL para crear tablas
# (CREATE TABLE, PRIMARY KEY, REFERENCES, CREATE INDEX), cargar archivos
# CSV con COPY, las TRANSACCIONES y COMMIT, ANALYZE, y medir el tiempo
# con time.perf_counter().
#
# QUÉ HAY DE NUEVO en esta versión: puedes elegir EN QUÉ base de datos
# cargar (--database en la línea de comandos, o el parámetro `database`
# de load()). Ahora se usan dos bases de datos:
#   gharchive     la base de datos del benchmark — la de por defecto, y
#                 CONGELADA: siempre contiene la hora fija del benchmark.
#   gharchive24h  la base de datos del pipeline en vivo de 24 horas
#                 (pipeline.py), que se recarga una y otra vez con las
#                 últimas 24 horas.
# Mantenerlas separadas significa que el pipeline en vivo nunca puede
# sobreescribir los datos del benchmark.
#
# Ejecútalo a través de run.sh (necesita PGPASSWORD):
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
    ./run.sh scripts/load_postgres.py --csv-dir data/live/csv --database gharchive24h
"""

# ---------------------------------------------------------------------
# import time — NUEVO: el módulo de la biblioteca estándar para los
# relojes. Solo usamos time.perf_counter() (ver seconds_since() más abajo).
# argparse, sys, Path, psycopg: ya explicados en los scripts anteriores.
# ---------------------------------------------------------------------
import argparse
import sys
import time
from pathlib import Path

import psycopg

# Las mismas constantes que extract_csv.py (dónde están los CSV) y
# check_connections.py (cómo llegar a PostgreSQL).
#
# NUEVO: el nombre de la base de datos ("dbname") ya no está dentro de
# POSTGRES_SETTINGS. Ahora tiene su propia constante, DEFAULT_DATABASE,
# y se pasa por separado al conectar (ver load() más abajo), para poder
# cambiarlo por otro — p. ej. "gharchive24h" para el pipeline en vivo —
# mientras el host y el usuario siguen siendo los mismos.
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_DIR = PROJECT_DIR / "data" / "csv"
DEFAULT_DATABASE = "gharchive"
POSTGRES_SETTINGS = {"host": "localhost", "user": "postgres"}

# ---------------------------------------------------------------------
# SCHEMA — el SQL que construye las tres tablas
#
# Un string de Python escrito con comillas triples ("""...""") puede
# ocupar muchas líneas. Este contiene SQL, el lenguaje de PostgreSQL, que
# se envía al servidor tal cual.
#
# DROP TABLE IF EXISTS ...
#   Borra la tabla si ya existe (de una ejecución anterior), y no hace
#   nada si no existe. Eso es lo que hace que el script sea REPETIBLE:
#   cada ejecución empieza de cero. El ORDEN importa: actor_repo apunta
#   a actor y a repo, así que se borra PRIMERO (no se puede borrar una
#   tabla de la que otra todavía depende).
#
# CREATE TABLE actor ( id BIGINT PRIMARY KEY, login TEXT NOT NULL );
#   BIGINT       un número entero lo bastante grande para los ids de
#                GitHub (un INTEGER normal se queda en unos 2.100
#                millones; algunos ids ya superan esa cifra, y BIGINT es
#                la opción segura).
#   TEXT         texto de cualquier longitud.
#   NOT NULL     el valor nunca puede faltar.
#   PRIMARY KEY  la clave primaria: la columna que identifica cada fila.
#                Tiene que ser única, no puede faltar, y PostgreSQL crea
#                automáticamente un ÍNDICE sobre ella, así que encontrar
#                una fila por su id es instantáneo.
#   (login NO es único: recuerda las dos cuentas "Copilot").
#
# CREATE TABLE actor_repo (... REFERENCES actor (id) ...)
#   REFERENCES crea una CLAVE FORÁNEA: cada actor_id tiene que existir
#   en actor.id, y cada repo_id en repo.id. La propia base de datos
#   rechaza una conexión que apunte a un actor o un repo que no existe.
#
#   PRIMARY KEY (actor_id, repo_id) — una clave primaria formada por DOS
#   columnas: lo que tiene que ser único es la PAREJA. Así la base de
#   datos impone "una conexión por cada pareja actor-repo, sin
#   repeticiones", la misma regla que extract_csv.py aplicaba con su
#   conjunto.
#
# CREATE INDEX actor_repo_repo_id_idx ON actor_repo (repo_id);
#   Un ÍNDICE es como el índice al final de un libro: en vez de leer
#   todas las páginas para encontrar una palabra, la buscas y saltas
#   directamente a ella. La clave primaria de dos columnas está ordenada
#   primero por actor_id, así que va muy bien para "los repos de un
#   actor" pero no para "los actores de un repo". Este índice extra
#   cubre esa otra dirección. El recorrido del benchmark
#   (actor -> repo -> actor -> repo) necesita AMBOS, en cada salto.
#
# Las líneas que empiezan por -- dentro del SQL son comentarios de SQL
# (como # en Python); PostgreSQL las ignora.
# ---------------------------------------------------------------------
# Se borran empezando por la hija (actor_repo apunta a actor y a repo) y
# se crean empezando por las padres.
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
# TABLES — una lista de tuplas (tabla, columnas, archivo CSV), una por
# tabla. Tenerlo todo en una sola lista permite que el mismo bucle cargue
# y compruebe las tres. El ORDEN es el orden de carga: actor y repo antes
# que actor_repo, por las claves foráneas (una conexión solo se puede
# cargar cuando ya existen su actor y su repo).
# ---------------------------------------------------------------------
# (tabla, columnas, archivo CSV) en orden de carga: las padres antes que
# actor_repo.
TABLES = [
    ("actor", "id, login", "actors.csv"),
    ("repo", "id, name", "repos.csv"),
    ("actor_repo", "actor_id, repo_id", "actor_repo.csv"),
]


# ---------------------------------------------------------------------
# def count_csv_rows(path) -> int:
#
# Cuenta las filas de datos de un archivo CSV, para compararlas después
# con la tabla. sum(1 for _ in f) suma 1 por cada línea del archivo (una
# forma compacta de contar líneas); el - 1 quita la línea de cabecera
# (id,login), que no es un dato.
# ---------------------------------------------------------------------
def count_csv_rows(path: Path) -> int:
    with open(path, "r", encoding="utf-8") as f:
        return sum(1 for _ in f) - 1  # minus the header line


# ---------------------------------------------------------------------
# def copy_csv(cur, table, columns, path) -> None:
#
# COPY es el comando de CARGA MASIVA de PostgreSQL: mucho más rápido que
# un INSERT por cada fila, porque los datos entran como un único flujo
# continuo.
#
#   COPY actor (id, login) FROM STDIN WITH (FORMAT csv, HEADER true)
#     FROM STDIN    los datos llegan a través de la conexión ("entrada
#                   estándar"), enviados por Python, en lugar de leerse
#                   de un archivo en el servidor. El servidor nunca
#                   necesita acceso a tus archivos.
#     FORMAT csv    los datos están en CSV.
#     HEADER true   salta la primera línea (los nombres de las columnas).
#
# cur.copy(...) abre ese flujo; copy.write(chunk) le envía datos.
#
# `with A as f, B as copy:` — dos `with` en una misma línea; la barra
# invertida \ al final de la línea solo significa "la instrucción sigue
# en la línea siguiente".
#
# while chunk := f.read(1024 * 1024):
#   f.read(1024 * 1024) lee hasta 1 MB del archivo cada vez, así que ni
#   siquiera un archivo enorme tiene que caber entero en memoria.
#   `:=` (el "operador morsa") asigna Y comprueba de una vez: "lee un
#   trozo, guárdalo en `chunk` y sigue en el bucle mientras no esté
#   vacío". Al final del archivo, f.read() devuelve "" (vacío), y el
#   bucle se detiene.
# ---------------------------------------------------------------------
def copy_csv(cur: psycopg.Cursor, table: str, columns: str, path: Path) -> None:
    # COPY ... FROM STDIN: Python envía el contenido del archivo por la
    # conexión, así que el servidor PostgreSQL nunca necesita acceder al
    # archivo en sí.
    with open(path, "r", encoding="utf-8") as f, \
         cur.copy(f"COPY {table} ({columns}) FROM STDIN WITH (FORMAT csv, HEADER true)") as copy:
        while chunk := f.read(1024 * 1024):
            copy.write(chunk)


# ---------------------------------------------------------------------
# def seconds_since(start) -> str:
#
# time.perf_counter() devuelve un número de segundos contados desde un
# punto de partida arbitrario. Por sí solo no significa nada, pero la
# DIFERENCIA entre dos llamadas es exactamente el tiempo que ha pasado
# entre ellas. Es el reloj pensado para medir duraciones: el más preciso,
# y no le afecta que cambie la hora del ordenador.
#
#     start = time.perf_counter()
#     ...something...
#     seconds_since(start)   # e.g. "  0.12 s"
#
# :6.2f — un número de 6 caracteres de ancho con 2 decimales, para que
# los tiempos queden alineados en columna.
# ---------------------------------------------------------------------
def seconds_since(start: float) -> str:
    return f"{time.perf_counter() - start:6.2f} s"


# ---------------------------------------------------------------------
# def load(csv_dir, database=DEFAULT_DATABASE) -> bool:
#
# Hace todo el trabajo y devuelve True si cada tabla ha acabado con
# exactamente tantas filas como su archivo CSV.
#
# NUEVO: el parámetro `database` indica en qué base de datos cargar. Por
# defecto vale DEFAULT_DATABASE ("gharchive"), así que load(csv_dir)
# sigue cargando la base de datos del benchmark exactamente como antes;
# pipeline.py, en cambio, llama a load(csv_dir, "gharchive24h").
#
# psycopg.connect(**POSTGRES_SETTINGS, dbname=database)
#   `**POSTGRES_SETTINGS` DESEMPAQUETA el diccionario en argumentos con
#   nombre: cada clave se convierte en el nombre de un argumento y cada
#   valor en su valor. Así que, para el pipeline en vivo, esta línea
#   equivale a escribir
#       psycopg.connect(host="localhost", user="postgres",
#                       dbname="gharchive24h")
#   El diccionario aporta los ajustes que nunca cambian; dbname=database
#   añade el que sí cambia.
#
# conn.cursor() — un CURSOR es el objeto que se usa para enviar SQL por
# la conexión y leer las respuestas (check_connections.py usaba el atajo
# conn.execute(), que crea uno por detrás).
#
# TRANSACCIONES: con psycopg, todo lo que se envía por una conexión forma
# parte de una TRANSACCIÓN, un grupo de cambios que o bien ocurren TODOS
# o bien NINGUNO. Hasta que se llama a conn.commit(), no se guarda nada
# de forma permanente: si el script fallara a medias, PostgreSQL
# desharía todo y las tablas quedarían como antes. Por eso nunca puede
# quedar una carga a medio hacer.
# ---------------------------------------------------------------------
def load(csv_dir: Path, database: str = DEFAULT_DATABASE) -> bool:
    all_match = True
    with psycopg.connect(**POSTGRES_SETTINGS, dbname=database) as conn:
        with conn.cursor() as cur:
            # El total empieza aquí, una vez conectados: conectarse no
            # forma parte de la carga.
            load_start = time.perf_counter()

            # Cada paso se cronometra por separado: se toma la hora, se
            # hace el paso y se muestra cuánto ha tardado.
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
            # Antes de ejecutar una consulta, el PLANIFICADOR de
            # PostgreSQL decide CÓMO ejecutarla (¿usar un índice o leer
            # la tabla entera? ¿qué tabla primero?). Para decidir bien,
            # se basa en ESTADÍSTICAS sobre los datos: cuántas filas hay,
            # cómo se reparten los valores. Justo después de una carga
            # masiva esas estadísticas están desactualizadas, así que
            # ANALYZE las refresca. Para el benchmark, esto significa que
            # el lado relacional se mide con consultas bien planificadas
            # — parte de dar a cada lado sus ayudas habituales.
            # ---------------------------------------------------------
            # Refresca las estadísticas del planificador para que las
            # consultas se planifiquen con los datos reales.
            step = time.perf_counter()
            cur.execute("ANALYZE actor; ANALYZE repo; ANALYZE actor_repo;")
            print(f"Statistics refreshed (ANALYZE)                 {seconds_since(step)}")

            # COMMIT guarda la transacción de forma permanente. Se hace
            # aquí, antes de parar el reloj, para que el total incluya el
            # guardado de los datos, pero no las comprobaciones que
            # vienen después.
            # Commit aquí, para que el total cubra el guardado de los
            # datos pero no las comprobaciones de abajo.
            conn.commit()
            print(f"Total load time                                {seconds_since(load_start)}")

            # ---------------------------------------------------------
            # La comprobación: contar las filas de cada tabla y
            # compararlas con el CSV. SELECT count(*) FROM actor cuenta
            # las filas; .fetchone()[0] toma el único número de la
            # respuesta.
            #
            # all_match = all_match and in_db == in_csv
            #   all_match empieza en True y pasa a False en cuanto una
            #   tabla no coincide (y se queda en False: False and
            #   cualquier cosa es False).
            # ---------------------------------------------------------
            print("\nRows loaded (database vs. CSV file):")
            for table, _, csv_name in TABLES:
                in_db = cur.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                in_csv = count_csv_rows(csv_dir / csv_name)
                status = "OK" if in_db == in_csv else "MISMATCH"
                all_match = all_match and in_db == in_csv
                print(f"  {table:<12} {in_db:>7}   {csv_name:<16} {in_csv:>7}   {status}")
    return all_match


# parse_args(): el mismo patrón que extract_csv.py; --csv-dir permite
# cargar desde otra carpeta.
#
# NUEVO: --database permite cargar en otra base de datos, p. ej.
#     --csv-dir data/live/csv --database gharchive24h
# No se indica ningún type=, así que el valor se queda como una cadena de
# texto simple (un nombre). Sin el indicador, vale DEFAULT_DATABASE
# ("gharchive"), la del benchmark.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, default=DEFAULT_CSV_DIR,
                         help=f"Folder with the CSV files from extract_csv.py (default: {DEFAULT_CSV_DIR})")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                         help=f"PostgreSQL database to load into (default: {DEFAULT_DATABASE})")
    return parser.parse_args()


# main(): si los recuentos no coinciden, sys.exit("...") muestra el
# mensaje y termina con un código de salida de error (ver
# check_connections.py).
def main() -> None:
    args = parse_args()
    if not load(args.csv_dir, args.database):
        sys.exit("Some row counts don't match their CSV file.")
    print("\nPostgreSQL load complete.")


# main() y la protección `if __name__ == "__main__":`: ver la copia
# anotada de download_gharchive.py.
if __name__ == "__main__":
    main()
