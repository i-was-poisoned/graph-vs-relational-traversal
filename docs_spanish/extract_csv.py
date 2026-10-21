########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/extract_csv.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive
# en docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script
# real y "limpio" (sin nada de este comentario) es scripts/extract_csv.py.
#
# Este archivo asume que ya has leído los scripts anotados anteriores —
# argparse, Path, json, los diccionarios, los conjuntos, los bucles,
# `continue`, las f-strings, main() y la protección __name__ NO se vuelven
# a explicar desde cero aquí. Este archivo se centra en lo que es NUEVO en
# extract_csv.py: escribir archivos CSV con el módulo csv, las tuplas como
# elementos de un conjunto y como valores de un diccionario, quedarse con
# el valor "más reciente" mientras se lee, ordenar para obtener una salida
# reproducible y crear carpetas con Path.mkdir().
#
# Su función en el proyecto: ser la ÚNICA FUENTE desde la que se cargan
# las dos bases de datos. PostgreSQL y Neo4j leerán cada una estos mismos
# tres archivos, así que no pueden acabar guardando datos distintos — un
# requisito para que el benchmark sea justo.
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
# NUEVO: el módulo de la biblioteca estándar para leer y escribir
# archivos CSV ("comma-separated values", valores separados por comas):
# tablas de texto plano en las que cada línea es una fila y las comas
# separan las columnas, p. ej.
#
#     id,login
#     19,brynary
#
# ¿Por qué no escribir nosotros mismos las comas con f"{a},{b}"? Porque si
# algún valor contuviera una coma o unas comillas, la tabla se rompería.
# El módulo csv se encarga de esos casos (añade comillas donde hace
# falta), y tanto PostgreSQL como Neo4j leen su salida sin problemas.
#
# argparse, json, Path: ya explicados en los scripts anotados anteriores.
# ---------------------------------------------------------------------
import argparse
import csv
import json
from pathlib import Path

# ---------------------------------------------------------------------
# PROJECT_DIR = Path(__file__).resolve().parent.parent
#
# La misma técnica que DEFAULT_FILE en los scripts anteriores (ver la
# copia anotada de peek_data.py), guardada en su propia constante porque
# de ella se construyen dos valores por defecto:
#   DEFAULT_FILE     data/2026-08-27-15.json   la entrada
#   DEFAULT_OUT_DIR  data/csv/                 donde van los CSV
#
# Los CSV van dentro de data/ a propósito: data/ ya está en .gitignore,
# porque todo lo que contiene se puede regenerar ejecutando de nuevo los
# scripts.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_FILE = PROJECT_DIR / "data" / "2026-08-27-15.json"
DEFAULT_OUT_DIR = PROJECT_DIR / "data" / "csv"

# La misma regla de bots que summarize_data.py (ver su copia anotada): los
# bots oficiales de GitHub tienen logins que terminan en "[bot]". El
# benchmark los excluye porque actúan como nodos centrales artificiales
# entre repos que no tienen relación entre sí.
BOT_SUFFIX = "[bot]"


def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# ---------------------------------------------------------------------
# def remember_latest(names, key, created_at, name) -> None:
#
# POR QUÉ EXISTE: en esta hora de datos, un usuario cambió su login
# (lucky521-png -> peitongshi) y dos repos cambiaron de nombre. Su id se
# mantiene, pero el nombre cambia de un evento a otro. Cada id debe
# aparecer UNA sola vez en el CSV, así que tenemos que elegir un nombre:
# el más reciente.
#
# CÓMO: `names` es un diccionario cuyas claves son ids y cuyos valores
# son TUPLAS de dos cosas, (created_at, name):
#
#     names[321725054] = ("2026-08-27T15:35:35Z", "peitongshi")
#
# Una tupla es como una lista pequeña que no se puede modificar; aquí se
# usa para mantener juntos dos valores relacionados. names[key][0] es la
# hora, names[key][1] es el nombre.
#
# El `if` guarda el nuevo nombre cuando:
#   key not in names           es la primera vez que vemos este id, o
#   created_at >= names[key][0] este evento es igual de reciente, o más
#                              reciente, que el que teníamos guardado.
#
# Comparar HORAS COMO TEXTO: created_at está escrito en formato ISO 8601
# ("2026-08-27T15:35:35Z": año, mes, día, hora, minuto, segundo, de mayor
# a menor, siempre con el mismo número de dígitos). En ese formato, el
# orden alfabético ES el orden temporal, así que `>=` sobre las cadenas
# funciona sin convertirlas en fechas.
#
# `-> None`: no devuelve nada; modifica el diccionario que recibe. Los
# diccionarios se pasan "por referencia": la función trabaja sobre el
# mismo diccionario que tiene quien la llama, no sobre una copia.
# ---------------------------------------------------------------------
def remember_latest(names: dict[int, tuple[str, str]], key: int, created_at: str, name: str) -> None:
    # Quedarse con el nombre del evento más reciente: los logins y los
    # nombres de los repos pueden cambiar. created_at es texto ISO 8601,
    # así que comparar las cadenas equivale a comparar las horas.
    if key not in names or created_at >= names[key][0]:
        names[key] = (created_at, name)


# ---------------------------------------------------------------------
# def extract(file_path) -> tuple[...]:
#
# Lee el archivo una vez y devuelve CUATRO cosas a la vez, empaquetadas
# en una tupla (main() las desempaqueta en cuatro variables):
#
#   actors   diccionario  id -> (created_at, login)
#   repos    diccionario  id -> (created_at, name)
#   pairs    conjunto     de tuplas (actor_id, repo_id)
#   skipped_bot_events  int
#
# La larga anotación de tipo `-> tuple[...]` solo describe esos cuatro
# tipos.
# ---------------------------------------------------------------------
def extract(file_path: Path) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
    actors: dict[int, tuple[str, str]] = {}
    repos: dict[int, tuple[str, str]] = {}

    # -----------------------------------------------------------------
    # pairs: set[tuple[int, int]] = set()
    #
    # ASÍ es como se consigue "una conexión por par actor-repo, sin
    # repeticiones". Cada conexión es una tupla (actor_id, repo_id), y un
    # CONJUNTO guarda cada elemento una sola vez (ver la copia anotada de
    # summarize_data.py). Si ana hace push 10 veces al mismo repo,
    # pairs.add((ana_id, repo_id)) se ejecuta 10 veces, pero el conjunto
    # guarda una sola copia. Por eso 67,459 eventos que no son de bots se
    # convierten en solo 15,053 conexiones.
    #
    # (Las tuplas pueden ir en un conjunto; las listas no, porque un
    # conjunto necesita elementos que no puedan cambiar nunca — y las
    # tuplas no se pueden modificar.)
    # -----------------------------------------------------------------
    pairs: set[tuple[int, int]] = set()
    skipped_bot_events = 0

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            actor = event["actor"]
            repo = event["repo"]

            # El mismo patrón de saltar y contar de antes: `continue` salta
            # a la siguiente línea sin llegar al código de abajo.
            if is_bot(actor["login"]):
                skipped_bot_events += 1
                continue

            # Los ids (actor["id"], repo["id"]) son las claves en todas
            # partes — nunca los nombres, que pueden cambiar (ver
            # remember_latest).
            remember_latest(actors, actor["id"], event["created_at"], actor["login"])
            remember_latest(repos, repo["id"], event["created_at"], repo["name"])
            pairs.add((actor["id"], repo["id"]))

    return actors, repos, pairs, skipped_bot_events


# ---------------------------------------------------------------------
# def write_csv(path, header, rows) -> None:
#
# Escribe un archivo CSV: una línea de cabecera con los nombres de las
# columnas y después una línea por fila. Se usa tres veces, una por
# archivo.
#
# open(path, "w", encoding="utf-8", newline="")
#   "w"         modo ESCRITURA: crea el archivo, o lo vacía si ya existe.
#   newline=""  obligatorio para el módulo csv: él mismo escribe los
#               finales de línea y, sin esto, Windows añadiría una línea
#               en blanco de más entre las filas.
#
# csv.writer(f)          un objeto que convierte filas en líneas CSV.
# writer.writerow(...)   escribe UNA fila (aquí, la cabecera).
# writer.writerows(...)  escribe MUCHAS filas de golpe (todos los datos).
#
# rows: list[tuple]  cada fila es una tupla, p. ej. (19, "brynary"), y
# cada valor de la tupla se convierte en una columna.
#
# {path.name:<16}  path.name es solo el nombre del archivo ("actors.csv"),
# sin las carpetas; :<16 lo rellena hasta 16 caracteres para que los
# conteos queden alineados.
# ---------------------------------------------------------------------
def write_csv(path: Path, header: list[str], rows: list[tuple]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    print(f"  {path.name:<16} {len(rows):>7} rows")


# parse_args(): el mismo patrón que en los scripts anteriores. --out-dir
# permite elegir otra carpeta de salida; type=Path la convierte, igual
# que con --file.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # extract() devuelve una tupla de cuatro valores; esta línea la
    # DESEMPAQUETA en cuatro variables a la vez (la misma idea que
    # `for key, value in ...`).
    actors, repos, pairs, skipped_bot_events = extract(args.file)

    # -----------------------------------------------------------------
    # args.out_dir.mkdir(parents=True, exist_ok=True)
    #
    # Crea la carpeta de salida (data/csv/) si todavía no existe.
    #   parents=True   crea también las carpetas superiores que falten.
    #   exist_ok=True  no falla si la carpeta ya existe (p. ej. en la
    #                  segunda ejecución).
    # -----------------------------------------------------------------
    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")

    # -----------------------------------------------------------------
    # Construir las filas: sorted(...) + una list comprehension
    #
    # sorted(actors.items()) da los pares (id, (created_at, login))
    # ORDENADOS POR ID. Después, la comprehension se queda solo con lo que
    # va en el archivo:
    #     for actor_id, (_, login) in ...
    # desempaqueta cada par, y también la tupla interior: `_` es el
    # created_at, que ya no necesitamos ("un valor que no necesito", como
    # en check_connections.py). Cada fila pasa a ser (actor_id, login).
    #
    # Para actor_repo.csv, sorted(pairs) convierte el conjunto en una lista
    # de tuplas ordenadas por actor_id y, después, por repo_id.
    #
    # POR QUÉ ORDENAR: ni un conjunto ni el orden en que llegan los eventos
    # dan un orden fijo. Ordenar hace que la misma entrada produzca SIEMPRE
    # exactamente los mismos archivos, byte a byte — así es fácil comprobar
    # que una ejecución posterior no ha cambiado nada. Reproducibilidad,
    # otra vez.
    # -----------------------------------------------------------------
    # Ordenado por id para que la misma entrada produzca siempre los mismos
    # archivos, byte a byte.
    write_csv(args.out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(args.out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(args.out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


# main() y la protección `if __name__ == "__main__":`: el mismo propósito
# y funcionamiento que en los otros scripts — ver la copia anotada de
# download_gharchive.py para la explicación completa.
if __name__ == "__main__":
    main()
