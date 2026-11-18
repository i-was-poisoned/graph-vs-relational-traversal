########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/build_hours.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive
# en docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script
# real y "limpio" (sin nada de este comentario) es scripts/build_hours.py.
#
# Lee primero estas copias anotadas; lo que explican NO se repite aquí:
#   download_gharchive.py   fetch_gz(), try/except, `raise ... from`
#   extract_csv.py          extract(), write_all()
#   load_postgres.py,
#   load_neo4j.py           load(), y las comprobaciones de recuentos
#                           (OK / MISMATCH)
#   check_connections.py    conectarse a los dos servidores, las
#                           contraseñas
#   pipeline.py             importar nuestros propios scripts como
#                           módulos, hour_file_name(), sql.Identifier,
#                           CREATE DATABASE ... WAIT, servers_not_ready()
#   test_integration.py     `while True:`, los records de Neo4j
#
# QUÉ ES — el PROCESO MANUAL. La investigación quiere saber a partir de
# qué profundidad de recorrido y qué volumen de datos Neo4j empieza a
# ganar a PostgreSQL, así que necesita los MISMOS datos fijos en las dos
# bases de datos, con varios tamaños (1 hora, 3 horas, 24 horas...). Este
# script construye uno de esos conjuntos de datos cuando se lo pides: TÚ
# eliges las horas, y él las pone en una base de datos propia, en los dos
# lados. (El pipeline automático de 24 horas, pipeline.py, queda aplazado
# por ahora: la fase de investigación usa datos construidos con este
# script.)
#
# Lo que es NUEVO aquí:
#   - hacer preguntas por teclado con input(), y VALIDAR las respuestas
#     (volver a preguntar hasta que sean válidas);
#   - lanzar nuestros propios errores (raise ValueError) con mensajes
#     legibles;
#   - leer una fecha a partir de un texto (datetime.strptime);
#   - pasar una FUNCIÓN como parámetro para que los tests puedan
#     sustituir el teclado;
#   - borrar y volver a crear una base de datos entera (DROP DATABASE ...
#     WITH (FORCE), CREATE OR REPLACE DATABASE), detrás de una
#     COMPROBACIÓN DE SEGURIDAD sobre el nombre, y después DEMOSTRAR que
#     está vacía antes de cargar;
#   - EOFError / KeyboardInterrupt (no hay teclado, o se pulsa Ctrl+C).
# Sus mensajes son VERBOSOS a propósito: cada paso dice lo que va a hacer
# y lo que ha hecho, para que puedas seguirlo sin abrir el código.
#
# Cómo se ejecuta el script real (el resto lo pregunta él):
#     ./run.sh scripts/build_hours.py
# run.sh activa .venv y carga las contraseñas desde secrets.sh; este
# script nunca contiene ni pide una contraseña.
########################################################################

"""Build a database from GH Archive hours that you choose, on both sides.

The benchmark's fixed hour lives in the "gharchive" databases and never
changes. This script lets you load other data to compare with it: it asks
which date, starting hour and number of consecutive hours you want, then

    1. downloads those hours to data/hours/ (hours already there are reused);
    2. extracts the CSV files from them (extract_csv.py), into
       data/hours/csv/<database name>/;
    3. empties the database named after the hours, in PostgreSQL and in Neo4j:
       it deletes it (if it exists) and creates it again, then checks that both
       sides really are empty, and stops if they aren't;
           1 hour  from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15"
           3 hours from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15-3h"
    4. loads the CSVs into both (load_postgres.py, load_neo4j.py).

Each choice gets its own database, so "gharchive" and "gharchive24h" are never
touched. Loading the same choice again empties and rebuilds only its own databases.

Usage (it asks the rest; press Enter to keep the value in brackets):
    ./run.sh scripts/build_hours.py
"""

# ---------------------------------------------------------------------
# Importaciones: todas ya vistas. `date` (un día sin hora) se explica en
# la copia anotada de pipeline.py, igual que datetime/timedelta/timezone.
# Fíjate: aquí no hay argparse — este script PREGUNTA en lugar de recibir
# opciones.
# ---------------------------------------------------------------------
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# Nuestros propios scripts, importados como MÓDULOS (ver la copia anotada
# de pipeline.py). Reutiliza el descargador, el extractor y los dos
# cargadores — exactamente el mismo código que el benchmark y el
# pipeline, así que todos los conjuntos de datos se construyen igual — y
# dos funciones del propio pipeline.py: hour_file_name() y
# servers_not_ready().
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres
import pipeline

# ---------------------------------------------------------------------
# Constantes:
#   HOURS_DIR   data/hours/ — donde van las descargas y los CSV de este
#               script (git los ignora, como el resto de data/). Aparte
#               de los archivos del benchmark y de data/live/ (los del
#               pipeline).
#   FIRST_DATE  la fecha más antigua que acepta. date(2015, 1, 1) es un
#               objeto `date`: año, mes, día.
#   MAX_HOURS   el máximo de horas que acepta de una vez: 168 = 7 x 24,
#               una semana.
# ---------------------------------------------------------------------
HOURS_DIR = Path(__file__).resolve().parent.parent / "data" / "hours"
# GH Archive's events have had today's format since 2015; older files use another one.
FIRST_DATE = date(2015, 1, 1)
# A week. More would take very long to load and need a lot of memory in Neo4j.
MAX_HOURS = 168


# ---------------------------------------------------------------------
# def parse_date(text) -> date:
#
# La primera de tres pequeñas funciones de VALIDACIÓN: cada una convierte
# lo que has escrito (un str) en un valor como es debido, o LANZA un
# ValueError con un mensaje que una persona puede entender.
#
# raise ValueError("...")
#   NUEVO: lanzar NUESTRO PROPIO error. Hasta ahora solo capturábamos
#   errores lanzados por otros. ValueError es el tipo habitual de Python
#   para "tipo correcto, valor incorrecto". El texto se convierte en el
#   mensaje del error, y ask_hours() simplemente lo imprime (ver más
#   abajo). Una función, dos trabajos: decir si la respuesta es válida Y
#   por qué no lo es.
#
# text.strip() quita los espacios y el salto de línea alrededor del
# texto, así que una respuesta "   " cuenta como vacía. `not ""` es True
# (una cadena vacía es "falsy", es decir, cuenta como falso), así que
# `if not text.strip():` significa "si no se ha escrito nada".
#
# datetime.strptime(text, "%Y-%m-%d")
#   "STRing Parse TIME" (leer una hora a partir de un texto): lo
#   contrario del formato f"{day:%Y-%m-%d}" visto en pipeline.py — LEE
#   una fecha escrita con ese patrón. Si el texto no encaja (orden
#   equivocado, mes 13...), lanza ValueError. Devuelve un datetime (a
#   medianoche); .date() se queda solo con el día.
#
# except ValueError: raise ValueError(...) from None
#   El mensaje propio de strptime ("time data '27/08/2026' does not
#   match format '%Y-%m-%d'") es correcto pero críptico, así que lo
#   capturamos y lanzamos uno más claro. `from None` oculta el error
#   original: a diferencia de `from error` (ver download_gharchive.py),
#   no contiene nada útil que conservar, y el usuario solo debe ver
#   nuestro mensaje.
#
# day < FIRST_DATE — las fechas se pueden comparar como números: la
# anterior < la posterior.
# ---------------------------------------------------------------------
def parse_date(text: str) -> date:
    # "2026-08-27" -> date(2026, 8, 27); anything else raises ValueError with a readable message.
    if not text.strip():
        raise ValueError("Please type a date, like 2026-08-27 (year-month-day)")
    try:
        day = datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{text}' isn't a date like 2026-08-27 (year-month-day)") from None
    if day < FIRST_DATE:
        raise ValueError(f"Dates before {FIRST_DATE} use an older GH Archive format; choose a later one")
    return day


# ---------------------------------------------------------------------
# def parse_hour(text) -> int:
#
# text.strip().isdigit()
#   True solo si el texto está formado por dígitos 0-9 y nada más. "15"
#   pasa; "-1", "3pm" y "1.5" no. Se comprueba ANTES de int(text), así
#   que int() nunca recibe un texto que no pueda convertir.
#
# 0 <= int(text) <= 23
#   Una comparación ENCADENADA: Python la lee como
#   "0 <= int(text) and int(text) <= 23" — la notación habitual de
#   matemáticas.
#
# `A or B` en la condición: si el texto no son dígitos, `or` ya sabe que
# la respuesta es True y ni siquiera evalúa la segunda parte.
#
# Las horas son UTC porque GH Archive nombra sus archivos en UTC (ver la
# copia anotada de pipeline.py, compute_window()).
# ---------------------------------------------------------------------
def parse_hour(text: str) -> int:
    # "15" -> 15. GH Archive hours are UTC, 0 to 23.
    if not text.strip():
        raise ValueError("Please type an hour from 0 to 23 (UTC)")
    if not text.strip().isdigit() or not 0 <= int(text) <= 23:
        raise ValueError(f"'{text}' isn't an hour from 0 to 23 (UTC)")
    return int(text)


# La misma idea para el número de horas: de 1 a MAX_HOURS. Aquí no se
# comprueba si está "vacío", porque una respuesta vacía nunca llega a
# esta función: ask_hours() la sustituye por "1" (la única pregunta con
# valor por defecto).
def parse_count(text: str) -> int:
    # "3" -> 3 consecutive hours, from 1 to MAX_HOURS.
    if not text.strip().isdigit() or not 1 <= int(text) <= MAX_HOURS:
        raise ValueError(f"'{text}' isn't a number of hours from 1 to {MAX_HOURS}")
    return int(text)


# ---------------------------------------------------------------------
# def chosen_hours(day, hour, count) -> list[datetime]:
#
# Convierte las tres respuestas en la lista de horas, con la misma forma
# que compute_window() en pipeline.py: un datetime UTC por cada archivo
# por hora. Construye el primero a partir del año/mes/día del día más la
# hora, y después le suma 0, 1, 2... horas con timedelta. Como es
# aritmética de datetime, pasar de las 23:00 cambia al día siguiente (y
# al mes, y al año) por sí solo.
# ---------------------------------------------------------------------
def chosen_hours(day: date, hour: int, count: int) -> list[datetime]:
    # Example: 2026-08-27, 23, 2 -> 2026-08-27 23:00 and 2026-08-28 00:00 (crossing midnight is fine).
    first = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return [first + timedelta(hours=i) for i in range(count)]


# ---------------------------------------------------------------------
# def hours_are_published(hours, now) -> bool:
#
# Rechaza las horas que GH Archive todavía no puede tener (horas
# recientes, o el futuro), ANTES de intentar descargarlas. Con now =
# 15:20 UTC:
#   la hora actual empieza       15:00
#   menos una hora completa   -> 14:00   el FINAL más tardío permitido
#   12:00 + 2 horas termina a    14:00   -> aceptado
#   13:00 + 2 horas termina a    15:00   -> rechazado (demasiado reciente)
# last_end = el inicio de la última hora + 1 hora (como en run() de
# pipeline.py). `now` es un parámetro, así que los tests pueden usar una
# hora fija (ver docs_spanish/test_build_hours.py).
# ---------------------------------------------------------------------
def hours_are_published(hours: list[datetime], now: datetime) -> bool:
    # GH Archive publishes each hour's file a little after the hour ends. Accept the hours only
    # if the last one ended at least one full hour before the current hour began.
    last_end = hours[-1] + timedelta(hours=1)
    return last_end <= now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


# ---------------------------------------------------------------------
# def database_name(hours) -> str:
#
# Cada elección de horas tiene su PROPIA base de datos, con el nombre de
# las horas, para que los conjuntos de datos nunca se mezclen y puedas
# saber por el nombre lo que hay dentro:
#   1 hora   -> "gharchive-2026-08-27-15"
#   3 horas  -> "gharchive-2026-08-27-15-3h"
# Siempre empieza por "gharchive-" (con guion): ese prefijo es lo que
# comprueba may_be_emptied(), y nunca puede ser igual a "gharchive" ni a
# "gharchive24h". Guiones, no guiones bajos: Neo4j prohíbe "_" en los
# nombres de base de datos (ver DEFAULT_DATABASE en pipeline.py).
#
# `X if condición else Y` (ya visto): el nombre sin más para 1 hora, y el
# nombre más "-<count>h" en otro caso.
# ---------------------------------------------------------------------
def database_name(hours: list[datetime]) -> str:
    # Neo4j allows letters, digits, dots and dashes in database names (not "_"), so dashes it is.
    # The hour has no leading zero, like GH Archive's file names.
    name = f"gharchive-{hours[0]:%Y-%m-%d}-{hours[0].hour}"
    return name if len(hours) == 1 else f"{name}-{len(hours)}h"


# ---------------------------------------------------------------------
# def describe(hours) -> str:
#
# Un resumen legible para los mensajes. El pequeño truco del final:
#   's' * (len(hours) > 1)
# Una comparación da True o False, y en aritmética True cuenta como 1 y
# False como 0. Una cadena multiplicada por 1 es ella misma, y por 0 es
# "". Así que añade la "s" del plural solo cuando hay más de una hora:
# "1 hour", "3 hours".
# ---------------------------------------------------------------------
def describe(hours: list[datetime]) -> str:
    # e.g. "2026-08-27 15:00 -> 2026-08-27 18:00 UTC (3 hours)"
    end = hours[-1] + timedelta(hours=1)
    return f"{hours[0]:%Y-%m-%d %H:00} -> {end:%Y-%m-%d %H:00} UTC ({len(hours)} hour{'s' * (len(hours) > 1)})"


# ---------------------------------------------------------------------
# def ask_hours(now, ask=input) -> list[datetime] | None:
#
# input("pregunta") — NUEVO: muestra la pregunta, espera a que escribas
# algo y pulses Enter, y devuelve lo que has escrito como un str (sin el
# Enter). Pulsar solo Enter devuelve "".
#
# ask=input — una FUNCIÓN como valor por defecto de un parámetro. Las
# funciones son valores como cualquier otro (ver el bucle (name, check)
# de check_connections.py), así que la función se llama a través del
# nombre `ask`. Normalmente ask ES input (el teclado). Un test le pasa en
# su lugar su propia función, que devuelve respuestas preparadas — así
# ask_hours() se puede probar sin que nadie escriba nada (ver
# docs_spanish/test_build_hours.py).
# Fíjate: `input`, no `input()` — pasamos la función en sí, no la
# llamamos.
#
# El bucle de preguntas (`while True:` se explica en test_integration.py):
#   - cada respuesta pasa directamente por su función parse_...; la
#     primera que lanza ValueError salta a `except`;
#   - `except ValueError as error: print(error)` muestra el mensaje
#     legible que escribimos en la función parse_;
#   - `continue` — vuelve al PRINCIPIO del bucle: se hacen otra vez las
#     tres preguntas;
#   - lo mismo pasa si las horas todavía no están publicadas.
#
# ask("How many consecutive hours [1]: ") or "1"
#   EL ÚNICO VALOR POR DEFECTO. `A or B` da A si A es "truthy" (cuenta
#   como verdadero), y si no, B. Una respuesta vacía "" es falsy, así que
#   pulsar Enter da "1". El "[1]" de la pregunta es la forma habitual de
#   mostrar el valor por defecto.
#
# La FECHA y la HORA NO tienen valor por defecto, a propósito: pulsar
# solo Enter simplemente vuelve a preguntar ("Please type a date...").
# Una fecha por defecto permitiría cargar, pulsando Enter, datos que en
# realidad nadie ha elegido — y luego medir lo que no es sin darse
# cuenta.
#
# La CONFIRMACIÓN: muestra exactamente qué se va a cargar y en qué base
# de datos, y avisa de que una base de datos existente con ese nombre se
# vacía primero. La respuesta se limpia con .strip().lower() (sin
# espacios, en minúsculas, así que " Y " es "y") y se compara con `in`
# con una TUPLA de respuestas aceptadas: solo Enter (""), y/yes, y
# s/si/sí para quien responda en portugués o en español. Cualquier otra
# cosa (p. ej. "n") devuelve None, que le dice a main() "no hay nada que
# hacer".
#
# El tipo de retorno `list[datetime] | None`: una lista de horas, O None
# (la anotación con `|` se explica en la copia anotada de pipeline.py).
# ---------------------------------------------------------------------
def ask_hours(now: datetime, ask=input) -> list[datetime] | None:
    # Asks for the date, the first hour and how many hours until all are valid, then asks for
    # confirmation. Returns None if the answer to the confirmation is "n".
    # "ask" is input() unless a test replaces it.
    # The date and the hour have no default: they must always be typed, so data is never
    # loaded for a date nobody chose. Only the number of hours has one (Enter = 1).
    while True:
        try:
            day = parse_date(ask("Date (UTC, e.g. 2026-08-27): "))
            hour = parse_hour(ask("First hour (UTC, 0-23): "))
            count = parse_count(ask("How many consecutive hours [1]: ") or "1")
        except ValueError as error:
            print(error)
            continue
        hours = chosen_hours(day, hour, count)
        if not hours_are_published(hours, now):
            print("GH Archive hasn't published all those hours yet: "
                  "the last one must end at least an hour before the current hour.")
            continue

        answer = ask(f'Load {describe(hours)} into "{database_name(hours)}"? '
                     "(if that database already exists, it's emptied first) [Y/n]: ")
        return hours if answer.strip().lower() in ("", "y", "yes", "s", "si", "sí") else None


# ---------------------------------------------------------------------
# def may_be_emptied(name) -> bool:
#
# La COMPROBACIÓN DE SEGURIDAD antes de borrar nada. Este script borra
# bases de datos enteras, así que tiene que ser imposible que borre la
# equivocada. La regla es una sola línea: solo los nombres que empiezan
# por "gharchive-". str.startswith(prefijo) es True si el texto empieza
# por ese prefijo.
#   "gharchive"             -> False (sin guion)   el benchmark congelado
#   "gharchive24h"          -> False               la del pipeline en vivo
#   "gharchivetest"         -> False               la de los tests de
#                                                  integración
#   "neo4j", "postgres", "system" -> False         las de los propios
#                                                  servidores
#   "gharchive-2026-08-27-15" -> True              creada por este script
# Se deja como una función aparte y diminuta para poder probarla por
# separado.
# ---------------------------------------------------------------------
def may_be_emptied(name: str) -> bool:
    # Only databases made by this script may be deleted: never "gharchive" (the frozen
    # benchmark), "gharchive24h" (the pipeline's) or anything else on the servers.
    return name.startswith("gharchive-")


# ---------------------------------------------------------------------
# def recreate_databases(name) -> None:
#
# Vacía la base de datos en los dos lados BORRÁNDOLA y CREÁNDOLA de
# nuevo. Los cargadores ya vacían sus propias tablas y nodos (ver
# load_postgres.py y load_neo4j.py), pero volver a crear la base de datos
# entera es más seguro: no sobrevive nada de antes, ni siquiera algo que
# los cargadores no conozcan.
#
# PRIMERA LÍNEA: la comprobación de seguridad, ANTES de conectarse a
# nada. Si el nombre no está permitido, lanza ValueError y no pasa
# absolutamente nada.
#
# PostgreSQL (la conexión a la base de datos "postgres" con
# autocommit=True, la consulta a pg_database y sql.Identifier: todo como
# en ensure_databases() en la copia anotada de pipeline.py):
#   - `exists` es True o False: `... is not None` convierte "una fila, o
#     None" en un sí/no.
#   - DROP DATABASE "name" WITH (FORCE) — NUEVO: borra la base de datos
#     y TODOS sus datos. PostgreSQL se niega a borrar una base de datos a
#     la que hay alguien conectado (pgAdmin, por ejemplo); WITH (FORCE)
#     cierra antes esas conexiones.
#   - CREATE DATABASE "name" — una base de datos nueva y vacía.
#   - Los mensajes se escriben f'...' (con comillas simples) para que
#     puedan llevar "comillas dobles" alrededor del nombre. Para meter un
#     apóstrofo, como en doesn\'t, se escribe \' — una comilla ESCAPADA:
#     forma parte del texto, no es el final de la cadena.
#
# Neo4j (en la base de datos "system", donde se gestionan las bases de
# datos):
#   - SHOW DATABASES YIELD name WHERE name = $name RETURN name
#     lista las bases de datos con ese nombre: una fila si existe,
#     ninguna si no. $name es un PARÁMETRO de la consulta (ver
#     load_neo4j.py), que se rellena con name=name. Lo que se pasa es un
#     VALOR, así que aquí un parámetro sirve.
#   - .records — el resultado tiene las filas en su atributo .records; es
#     la misma lista que `records, _, _ = ...` desempaqueta en otros
#     sitios. Una lista vacía es falsy, así que `if records:` significa
#     "existe".
#   - CREATE OR REPLACE DATABASE `name` WAIT — NUEVO: un solo comando
#     que borra la base de datos si existe y la vuelve a crear
#     (Enterprise Edition, la que incluye Neo4j Desktop). WAIT solo
#     vuelve cuando está en línea. Aquí el nombre no puede ser un
#     parámetro (es un NOMBRE, no un valor), así que se mete en el texto
#     entre comillas invertidas (backticks) — algo aceptable solo porque
#     may_be_emptied() ya lo ha comprobado.
# Los `if records:` de antes y de después solo eligen los mensajes
# adecuados.
# ---------------------------------------------------------------------
def recreate_databases(name: str) -> None:
    # Deleting the whole database and creating it again is the surest way to empty it:
    # nothing from before survives (tables, rows, nodes, relationships, constraints).
    if not may_be_emptied(name):
        raise ValueError(f'Refusing to empty "{name}": build_hours.py only empties databases named gharchive-...')

    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None
        if exists:
            print(f'Deleting the PostgreSQL database "{name}" and all its data ...')
            # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print(f'The PostgreSQL database "{name}" has been deleted.')
        else:
            print(f'The PostgreSQL database "{name}" doesn\'t exist yet: nothing to delete.')
        print(f'Creating the PostgreSQL database "{name}" (empty) ...')
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print(f'The PostgreSQL database "{name}" has been created.')

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        records = driver.execute_query("SHOW DATABASES YIELD name WHERE name = $name RETURN name",
                                       name=name, database_="system").records
        if records:
            print(f'Deleting the Neo4j database "{name}" and all its data, then creating it again (empty) ...')
        else:
            print(f'The Neo4j database "{name}" doesn\'t exist yet: nothing to delete. Creating it (empty) ...')
        # CREATE OR REPLACE = delete it if it exists, then create it (Enterprise Edition only).
        # WAIT: don't return until the new database is online.
        driver.execute_query(f"CREATE OR REPLACE DATABASE `{name}` WAIT", database_="system")
        if records:
            print(f'The Neo4j database "{name}" has been deleted and created again.')
        else:
            print(f'The Neo4j database "{name}" has been created.')


# ---------------------------------------------------------------------
# def databases_are_empty(name) -> bool:
#
# No suponer, COMPROBAR: después de volver a crearla, contar lo que hay
# dentro en los dos lados. Todo tiene que ser 0.
#
# PostgreSQL: information_schema.tables — NUEVO: un catálogo estándar
#   (toda base de datos SQL lo tiene) que lista todas las tablas.
#   table_schema = 'public' se queda solo con NUESTRAS tablas (las del
#   propio PostgreSQL viven en otro sitio). Esta vez nos conectamos a la
#   propia base de datos nueva (dbname=name).
#
# Neo4j: tres recuentos, en la base de datos nueva (database_=name):
#   MATCH (n) RETURN count(n)            todos los nodos
#   MATCH ()-[r]->() RETURN count(r)     todas las relaciones
#   SHOW CONSTRAINTS ... count(name)     todas las restricciones
#                                        (load_neo4j.py crea dos; una
#                                        base de datos vacía no tiene
#                                        ninguna)
#
# def count(query) dentro del bloque `with`: una función ANIDADA (ver
# test_extract_csv.py). Puede usar `driver` porque está definida donde
# driver existe. Ahorra escribir tres veces la misma línea larga.
# .records[0][0]: la primera fila, su primera columna — el número.
#
# El informe: un dict {qué: cuántos}, recorrido con .items() (pares de
# clave y valor). En la f-string, :<20 rellena el texto hasta 20
# caracteres, alineado a la izquierda, y :>3 alinea el número a la
# derecha en 3 (ver summarize_data.py), así que las líneas forman
# columnas ordenadas:
#   PostgreSQL tables      0   empty
#
# all(how_many == 0 for how_many in found.values())
#   all(...) es True solo si TODOS los elementos son True (aquí: todos
#   los recuentos son 0). Lo de dentro es una expresión GENERADORA —
#   como una list comprehension, pero sin los corchetes.
# ---------------------------------------------------------------------
def databases_are_empty(name: str) -> bool:
    # Checks both sides and prints what it finds; True only if everything is 0.
    print(f'Checking that the database "{name}" is empty on both sides ...')
    with psycopg.connect(host="localhost", user="postgres", dbname=name) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0]

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        def count(query: str) -> int:
            return driver.execute_query(query, database_=name).records[0][0]
        nodes = count("MATCH (n) RETURN count(n)")
        relationships = count("MATCH ()-[r]->() RETURN count(r)")
        constraints = count("SHOW CONSTRAINTS YIELD name RETURN count(name)")

    found = {"PostgreSQL tables": tables, "Neo4j nodes": nodes,
             "Neo4j relationships": relationships, "Neo4j constraints": constraints}
    for what, how_many in found.items():
        print(f"  {what:<20} {how_many:>3}   {'empty' if how_many == 0 else 'NOT EMPTY'}")
    empty = all(how_many == 0 for how_many in found.values())
    if empty:
        print(f'The database "{name}" is empty in PostgreSQL and in Neo4j: ready to load.')
    return empty


# ---------------------------------------------------------------------
# def build(hours) -> bool:
#
# El trabajo completo, en pasos numerados que se imprimen como títulos
# ("== 0. ...", "== 1. ..."); el "\n" al principio de cada uno imprime
# antes una línea vacía, para separar los pasos en pantalla. Devuelve
# True solo si los recuentos de las dos cargas coinciden con sus CSV.
#
# Paso 0 — PRIMERO, LOS DOS SERVIDORES. pipeline.servers_not_ready() (ver
#   la copia anotada de pipeline.py) da None o el motivo. Se comprueba
#   antes de descargar o borrar nada: si Neo4j estuviera caído, el paso 3
#   vaciaría PostgreSQL y luego fallaría en Neo4j, dejando los dos lados
#   DISTINTOS — lo único que una comparación no se puede permitir.
#
# Paso 1 — DESCARGAR solo lo que falta: un archivo por hora que ya está
#   en data/hours/ se reutiliza (los conjuntos de datos que comparten
#   horas comparten archivos). download_gharchive.fetch_gz() es el
#   descargador de siempre, con sus reintentos; lanza un error si GH
#   Archive no tiene una hora. files.append(path) va reuniendo las rutas
#   para el paso 2.
#
# Paso 2 — EXTRAER con extract_csv.extract() y write_all() (dejando
#   fuera los bots), en data/hours/csv/<nombre de la base de datos>/:
#   cada conjunto de datos guarda sus propios CSV.
#
# Paso 3 — VACIAR: volver a crear la base de datos en los dos lados, y
#   después DEMOSTRAR que está vacía. Si no lo está, parar con False: no
#   se carga nada encima de datos antiguos.
#
# Pasos 4 y 5 — CARGAR con los mismos cargadores que el benchmark,
#   pasándoles el nombre de la base de datos. Cada uno devuelve True si
#   sus recuentos coinciden con los CSV (OK) y False si no (MISMATCH; el
#   cargador ya ha impreso qué recuento no cuadra).
#
# El RESUMEN repite lo esencial en una línea: qué horas, cuántos actores
#   / repos / conexiones, y OK o MISMATCH en cada lado. (Varias f-strings
#   seguidas se unen en una sola, como se vio en parse_args() de
#   pipeline.py.)
# ---------------------------------------------------------------------
def build(hours: list[datetime]) -> bool:
    name = database_name(hours)
    csv_dir = HOURS_DIR / "csv" / name

    # Before changing anything: if one server isn't answering, stop now. Otherwise one side
    # could be emptied while the other can't be, leaving the two databases different.
    print("\n== 0. Check that both servers are answering")
    print("Connecting to PostgreSQL (localhost:5432) and Neo4j (localhost:7687) ...")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was changed.")
        return False
    print("Both servers are answering.")

    print(f"\n== 1. Download {len(hours)} hour file(s) from GH Archive to {HOURS_DIR}")
    files = []
    for hour in hours:
        path = HOURS_DIR / pipeline.hour_file_name(hour)
        if path.exists():
            print(f"{path.name} is already on this computer: no need to download it again.")
        else:
            download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, HOURS_DIR)
        files.append(path)
    print(f"All {len(files)} hour file(s) are ready.")

    print("\n== 2. Extract actors, repos and connections into CSV files")
    print(f"Reading the events in {len(files)} file(s) (bots are left out) ...")
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    print(f"Found {len(actors)} actors, {len(repos)} repos and {len(pairs)} connections "
          f"({skipped_bot_events} bot events skipped).")
    print(f"Writing actors.csv, repos.csv and actor_repo.csv to {csv_dir} ...")
    extract_csv.write_all(csv_dir, actors, repos, pairs)
    print("The CSV files have been written.")

    print(f'\n== 3. Empty the database "{name}" on both sides, and check that it is empty')
    recreate_databases(name)
    if not databases_are_empty(name):
        print(f'The database "{name}" isn\'t empty after being recreated; nothing was loaded.')
        return False

    print(f'\n== 4. Load the data into the PostgreSQL database "{name}"')
    print(f'The data is being loaded into the PostgreSQL database "{name}" ...')
    postgres_ok = load_postgres.load(csv_dir, name)
    if postgres_ok:
        print(f'The data has been loaded into the PostgreSQL database "{name}", and every count matches its CSV file.')
    else:
        print(f'The PostgreSQL database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\n== 5. Load the data into the Neo4j database "{name}"')
    print(f'The data is being loaded into the Neo4j database "{name}" ...')
    neo4j_ok = load_neo4j.load(csv_dir, name)
    if neo4j_ok:
        print(f'The data has been loaded into the Neo4j database "{name}", and every count matches its CSV file.')
    else:
        print(f'The Neo4j database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\nSummary: "{name}" holds {describe(hours)}: {len(actors)} actors, {len(repos)} repos '
          f"and {len(pairs)} connections, in PostgreSQL ({'OK' if postgres_ok else 'MISMATCH'}) "
          f"and in Neo4j ({'OK' if neo4j_ok else 'MISMATCH'}).")
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# def main() -> None:
#
# 1. PREGUNTAR. Se capturan dos excepciones a la vez (una tupla en
#    `except`):
#      EOFError           input() no encontró ningún teclado del que
#                         leer ("End Of File", fin de archivo) — p. ej.
#                         el script lo lanzó un programador de tareas o
#                         con la entrada redirigida. Está pensado para
#                         ejecutarse a mano, así que se detiene.
#      KeyboardInterrupt  has pulsado Ctrl+C durante una pregunta.
#    En los dos casos: un mensaje corto y código de salida 1, en lugar de
#    un traceback largo.
#    Si respondiste "n" a la confirmación, ask_hours() devolvió None:
#    "Nothing done." con código de salida 0 — lo has elegido tú, así que
#    no es un fallo.
# 2. CONSTRUIR, dentro de try / except Exception: una hora que falta en
#    GH Archive, no tener internet, un error de la base de datos... se
#    informan todos en una línea legible ("Stopped by an error: ...") en
#    lugar de con un traceback.
# 3. Una línea final que dice Done o NOT done, y el CÓDIGO DE SALIDA
#    (0 / 1, ver check_connections.py).
# ---------------------------------------------------------------------
def main() -> None:
    try:
        hours = ask_hours(datetime.now(timezone.utc))
    except (EOFError, KeyboardInterrupt):
        # EOFError: there's no keyboard to answer (this script is meant to be run by hand).
        print("\nNo hours chosen; nothing done.")
        sys.exit(1)
    if hours is None:
        print("Nothing done.")
        sys.exit(0)

    name = database_name(hours)
    try:
        ok = build(hours)
    except Exception as error:
        # e.g. an hour GH Archive doesn't have, no internet, a database error
        print(f"\nStopped by an error: {error}")
        ok = False
    print(f'\n{"Done" if ok else "NOT done (see the messages above)"}: database "{name}".')
    sys.exit(0 if ok else 1)


# La protección __name__: ver la copia anotada de download_gharchive.py
# (y la de pipeline.py, para saber por qué también permite que los tests
# importen las funciones de este archivo sin ejecutar main()).
if __name__ == "__main__":
    main()
