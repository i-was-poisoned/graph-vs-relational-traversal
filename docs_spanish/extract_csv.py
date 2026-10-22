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
# QUÉ HAY DE NUEVO en esta versión (añadido para el pipeline en vivo de
# 24 horas, pipeline.py): puede leer VARIOS archivos de una vez, y lee
# directamente archivos comprimidos .json.gz (sin descomprimirlos antes
# en disco); se salta el raro evento que no tiene id de actor/repo y lo
# avisa con el módulo `logging`; y el paso de escribir los CSV vive ahora
# en su propia función, write_all(), para que pipeline.py pueda
# reutilizarlo. Para la hora del benchmark, los archivos CSV que produce
# son idénticos byte a byte a los de antes.
#
# Su función en el proyecto: ser la ÚNICA FUENTE desde la que se cargan
# las dos bases de datos. PostgreSQL y Neo4j leerán cada una estos mismos
# tres archivos, así que no pueden acabar guardando datos distintos — un
# requisito para que el benchmark sea justo.
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
#
# gzip: ya lo vimos en la copia anotada de download_gharchive.py. Aquí se
# usa de otra forma: para LEER un archivo .json.gz como texto,
# descomprimiéndolo sobre la marcha (ver open_text() más abajo).
#
# logging: NUEVO — la forma de la biblioteca estándar de avisar de
# advertencias y otros mensajes. Se explica donde se crea `log`, justo
# debajo de las constantes.
#
# from typing import TextIO: NUEVO — TextIO solo se usa en una anotación
# de tipo. Significa "un archivo abierto del que lees TEXTO" (en vez de
# bytes crudos). Ver open_text() más abajo.
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

# ---------------------------------------------------------------------
# log = logging.getLogger(__name__)
#
# NUEVO: un "logger" — un objeto para emitir mensajes, una alternativa
# más flexible a print(). getLogger(nombre) te da el logger con ese
# nombre; __name__ es el nombre de este mismo módulo (p. ej.
# "extract_csv"), así que cada mensaje lleva la etiqueta de dónde viene.
#
# ¿Por qué no simplemente print()? Porque DÓNDE acaban los mensajes lo
# decide quien ejecuta el programa, no este archivo:
#   - Ejecutado solo (python scripts/extract_csv.py), nadie ha
#     configurado logging, y lo que Python hace por defecto es mostrar
#     las advertencias (y lo que sea más grave) en pantalla. Así que la
#     advertencia de abajo sigue apareciendo en la terminal.
#   - Ejecutado desde pipeline.py, que SÍ configura logging al empezar:
#     la misma advertencia va entonces también a logs/pipeline.log, para
#     que puedas leerla más tarde aunque el pipeline funcione sin
#     supervisión.
# Este archivo no necesita saber ni preocuparse por cuál de los dos
# casos está ocurriendo.
#
# Los mensajes tienen niveles — debug, info, warning, error, critical —
# de menos a más grave. Abajo usamos log.warning(...).
# ---------------------------------------------------------------------
log = logging.getLogger(__name__)


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
# def open_text(path) -> TextIO:
#
# NUEVO: abre un archivo para leer texto, esté comprimido o no.
#
#   path.suffix
#     La ÚLTIMA extensión de la ruta: para "2026-08-27-15.json.gz" es
#     ".gz"; para "2026-08-27-15.json" es ".json".
#
#   gzip.open(path, "rt", encoding="utf-8")
#     "rt" = Read, Text (lectura, modo texto). gzip descomprime los bytes
#     a medida que los leemos y el modo texto los convierte en cadenas
#     normales, así que quien llama puede recorrerlo con `for line in f:`
#     exactamente igual que con un archivo normal. No se descomprime
#     nada en disco: una ventana de 24 horas son 24 archivos comprimidos,
#     y mantenerlos comprimidos ahorra MUCHO espacio en disco (cada hora
#     ocupa varias veces más una vez descomprimida).
#
#   open(path, "r", encoding="utf-8")
#     El caso normal, como antes, para un archivo .json ya descomprimido
#     (como la hora del benchmark, data/2026-08-27-15.json).
#
# -> TextIO: las dos ramas devuelven "un archivo de texto abierto", así
# que la función se puede usar en una sentencia `with` igual que el
# propio open():
#     with open_text(file_path) as f:
# Quien llama no necesita saber qué tipo de archivo era.
# ---------------------------------------------------------------------
def open_text(path: Path) -> TextIO:
    # Los archivos .json.gz se leen comprimidos, sin descomprimirlos antes en disco.
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8")
    return open(path, "r", encoding="utf-8")


# ---------------------------------------------------------------------
# def extract(file_paths) -> tuple[...]:
#
# NUEVO: ahora recibe una LISTA de archivos (file_paths: list[Path]) en
# lugar de uno solo, y los lee uno detrás de otro sobre los MISMOS
# diccionarios y el MISMO conjunto. Así, un actor que aparece en la hora
# 3 y otra vez en la hora 17 sigue acabando como UNA sola fila, con su
# login más reciente (remember_latest() compara las horas de los
# eventos, vengan del archivo que vengan). Para el benchmark, la lista
# contiene solo un archivo.
#
# Lee los archivos una vez y devuelve CUATRO cosas a la vez. La anotación
# de tipo parece un trabalenguas, pero son solo dos tipos de TUPLA
# pequeña y una grande. Vamos de dentro afuera, con datos reales.
#
# 1. QUÉ ES UNA TUPLA
#    Un grupo fijo de valores que van juntos, entre paréntesis. Piénsala
#    como una FICHA CON CASILLAS: el número de casillas no cambia, y cada
#    casilla significa algo por su POSICIÓN. [0] lee la primera casilla,
#    [1] la segunda:
#
#        ficha = ("2026-08-27T15:35:35Z", "peitongshi")
#        ficha[0]   # "2026-08-27T15:35:35Z"  <- la fecha
#        ficha[1]   # "peitongshi"            <- el nombre
#
#    Se parece a una lista, pero NO se puede cambiar después de crearla.
#
# 2. LAS DOS FICHAS PEQUEÑAS
#    (fecha, nombre)       se usa en actors y repos
#    (actor_id, repo_id)   se usa en pairs = UNA conexión
#
# 3. DÓNDE VAN
#    actors: un diccionario cuyos VALORES son fichas (fecha, nombre)
#        actors = {321725054: ("2026-08-27T15:35:35Z", "peitongshi"),
#                  19:        ("2026-08-27T15:02:11Z", "brynary"), ...}
#        -> dict[int, tuple[str, str]]  "número -> ficha de dos textos"
#    repos: exactamente igual, con repos.
#    pairs: un CONJUNTO de fichas (actor_id, repo_id)
#        pairs = {(321725054, 1348625135), (19, 1310070394), ...}
#        -> set[tuple[int, int]]  "conjunto de fichas de dos números"
#
# 4. LA FICHA GRANDE: LO QUE DEVUELVE extract()
#    Una función solo puede devolver UNA cosa. Para devolver cuatro, se
#    meten en una ficha de CUATRO casillas:
#
#        return actors, repos, pairs, skipped_bot_events
#
#    y main() la abre y reparte las cuatro casillas en cuatro variables:
#
#        actors, repos, pairs, skipped_bot_events = extract(args.file)
#
# EL DIBUJO COMPLETO
#
#    extract() devuelve UNA tupla de 4 casillas:
#    |-- casilla 1: actors   diccionario   321725054 -> ("2026-08-27T15:35:35Z", "peitongshi")
#    |                                                   '-- ficha pequeña: fecha, nombre --'
#    |-- casilla 2: repos    diccionario   (igual que actors, con repos)
#    |-- casilla 3: pairs    conjunto      {(321725054, 1348625135), (19, 1310070394), ...}
#    |                                       '-- ficha pequeña: actor, repo = 1 conexión --'
#    '-- casilla 4: skipped_bot_events     un número: 1970
#
# LA ANOTACIÓN DE TIPO, LEÍDA POR PARTES
#
#    -> tuple[                          una ficha de 4 casillas:
#        dict[int, tuple[str, str]],      1. actors: id -> (fecha, nombre)
#        dict[int, tuple[str, str]],      2. repos:  id -> (fecha, nombre)
#        set[tuple[int, int]],            3. pairs:  conjunto de (actor_id, repo_id)
#        int,                             4. skipped_bot_events: un número
#    ]
# ---------------------------------------------------------------------
def extract(file_paths: list[Path]) -> tuple[dict[int, tuple[str, str]], dict[int, tuple[str, str]], set[tuple[int, int]], int]:
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
    # NUEVO: cuenta los eventos descartados porque no tenían id de
    # actor/repo (se explica más abajo, en la línea `if "id" not in ...`).
    skipped_without_id = 0

    # NUEVO: un bucle exterior que recorre los archivos. Todo lo de dentro
    # es el mismo trabajo por línea de antes, solo que con un nivel más de
    # sangría. Cada archivo se abre con open_text(), así que funcionan
    # tanto .json como .json.gz.
    for file_path in file_paths:
        with open_text(file_path) as f:
            for line in f:
                event = json.loads(line)
                actor = event["actor"]
                repo = event["repo"]
                # ---------------------------------------------------
                # NUEVO: saltar los eventos cuyo actor o repo no tiene id.
                #
                # Encontrado en datos REALES: en una ventana de 24 horas
                # con 1,250,059 eventos, 2 ForkEvents tenían un repo
                # VACÍO:
                #     "repo": {}
                # seguramente forks de repos que se han borrado desde
                # entonces. Sin id no hay nodo que crear ni conexión que
                # dibujar, y repo["id"] haría fallar toda la ejecución
                # con un KeyError.
                #
                # `"id" not in actor` comprueba si el diccionario tiene
                # esa clave en absoluto (la misma prueba `in` sobre
                # diccionarios que se usa en remember_latest). Contamos
                # estos eventos y seguimos con `continue`, igual que con
                # los eventos de bots de abajo. El total se avisa una
                # sola vez, después de leer todos los archivos.
                #
                # (La hora del benchmark no tiene eventos así, por eso
                # su salida CSV no cambia.)
                # ---------------------------------------------------
                # Algunos eventos llegan con un repo vacío ({}), p. ej. forks de repos
                # borrados después: sin ids no hay nodo ni conexión que crear.
                if "id" not in actor or "id" not in repo:
                    skipped_without_id += 1
                    continue

                # El mismo patrón de saltar y contar de antes: `continue`
                # salta a la siguiente línea sin llegar al código de abajo.
                if is_bot(actor["login"]):
                    skipped_bot_events += 1
                    continue

                # Los ids (actor["id"], repo["id"]) son las claves en
                # todas partes — nunca los nombres, que pueden cambiar
                # (ver remember_latest).
                remember_latest(actors, actor["id"], event["created_at"], actor["login"])
                remember_latest(repos, repo["id"], event["created_at"], repo["name"])
                pairs.add((actor["id"], repo["id"]))

    # -----------------------------------------------------------------
    # NUEVO: avisar de los eventos saltados, pero solo si hubo alguno.
    #
    # `if skipped_without_id:` — un número cuenta como False cuando es 0
    # y como True en cualquier otro caso, así que esto se lee "si se
    # saltó alguno".
    #
    # log.warning("Skipped %d event(s) ...", skipped_without_id)
    #   Ojo: NO es una f-string. logging tiene su propio estilo de
    #   huecos: %d significa "aquí va un número entero", y el valor se
    #   pasa como un argumento aparte. logging lo rellena él mismo, p. ej.
    #       Skipped 2 event(s) without an actor or repo id
    #   (Es la convención en las llamadas a logging: el texto solo se
    #   construye si el mensaje de verdad se va a mostrar en algún sitio.)
    #
    # Dónde aparece: en pantalla cuando se ejecuta solo; en pantalla Y en
    # logs/pipeline.log cuando se ejecuta desde pipeline.py (ver `log`
    # arriba).
    #
    # Es una advertencia y no un valor de retorno más, así que la línea
    # del return (y todos los que llaman a la función) se queda
    # exactamente como estaba.
    # -----------------------------------------------------------------
    if skipped_without_id:
        log.warning("Skipped %d event(s) without an actor or repo id", skipped_without_id)
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


# ---------------------------------------------------------------------
# def write_all(out_dir, actors, repos, pairs) -> None:
#
# NUEVO: los pasos de "crear la carpeta y escribir los tres archivos
# CSV" que antes estaban dentro de main(), trasladados a su propia
# función. No ha cambiado nada en ellos — se han MOVIDO, para que
# pipeline.py pueda llamar a extract() y después a write_all() por su
# cuenta, sin pasar por main() ni por sus argumentos de línea de
# comandos.
#
# La firma es larga, así que se parte en dos líneas: Python permite un
# salto de línea en cualquier punto dentro de paréntesis ( ), y la
# segunda línea se sangra para alinearse con el primer parámetro, solo
# por legibilidad.
# ---------------------------------------------------------------------
def write_all(out_dir: Path, actors: dict[int, tuple[str, str]], repos: dict[int, tuple[str, str]],
              pairs: set[tuple[int, int]]) -> None:
    # -----------------------------------------------------------------
    # out_dir.mkdir(parents=True, exist_ok=True)
    #
    # Crea la carpeta de salida (data/csv/) si todavía no existe.
    #   parents=True   crea también las carpetas superiores que falten.
    #   exist_ok=True  no falla si la carpeta ya existe (p. ej. en la
    #                  segunda ejecución).
    # -----------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)

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
    write_csv(out_dir / "actors.csv", ["id", "login"],
              [(actor_id, login) for actor_id, (_, login) in sorted(actors.items())])
    write_csv(out_dir / "repos.csv", ["id", "name"],
              [(repo_id, name) for repo_id, (_, name) in sorted(repos.items())])
    write_csv(out_dir / "actor_repo.csv", ["actor_id", "repo_id"], sorted(pairs))


# parse_args(): el mismo patrón que en los scripts anteriores. --out-dir
# permite elegir otra carpeta de salida; type=Path la convierte, igual
# que con --file.
#
# NUEVO en --file:
#   nargs="+"              "uno o más valores". Ahora puedes escribir
#                            --file a.json.gz b.json.gz c.json.gz
#                          y args.file pasa a ser una LISTA de tres Path
#                          (type=Path se aplica a cada uno). En una
#                          shell como Git Bash, data/live/raw/*.json.gz
#                          se expande en todos los nombres de archivo que
#                          coinciden antes incluso de que Python los vea.
#   default=[DEFAULT_FILE] el valor por defecto también tiene que ser
#                          ahora una lista (de un archivo), para que
#                          extract() reciba siempre una lista, se haya
#                          pasado --file o no.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, nargs="+", default=[DEFAULT_FILE],
                         help=f"One or more .json or .json.gz files (default: {DEFAULT_FILE})")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR,
                         help=f"Folder to write the CSV files to (default: {DEFAULT_OUT_DIR})")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # extract() devuelve una tupla de cuatro valores; esta línea la
    # DESEMPAQUETA en cuatro variables a la vez (la misma idea que
    # `for key, value in ...`).
    # (args.file es ahora una lista de Path — ver parse_args() arriba.)
    actors, repos, pairs, skipped_bot_events = extract(args.file)

    # len(args.file) = cuántos archivos se han leído, p. ej.
    #     Read 1 file(s). Skipped 1970 bot events. Writing to ...\data\csv:
    # La creación de la carpeta y la escritura de los CSV que antes
    # venían aquí viven ahora en write_all() (ver arriba).
    print(f"Read {len(args.file)} file(s). Skipped {skipped_bot_events} bot events. Writing to {args.out_dir}:")
    write_all(args.out_dir, actors, repos, pairs)


# main() y la protección `if __name__ == "__main__":`: el mismo propósito
# y funcionamiento que en los otros scripts — ver la copia anotada de
# download_gharchive.py para la explicación completa.
if __name__ == "__main__":
    main()
