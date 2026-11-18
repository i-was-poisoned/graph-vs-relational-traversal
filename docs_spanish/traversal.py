########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/traversal.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su propósito
# es enseñar, no ejecutarse. El archivo real y "limpio" (sin nada de este
# comentario) es scripts/traversal.py. (El archivo real tampoco se ejecuta
# por sí solo: es un MÓDULO de consultas compartidas, que importan
# choose_starts.py y measure.py.)
#
# Este archivo asume que ya has leído las copias anotadas anteriores:
#   check_connections.py   psycopg, el driver de Neo4j, os.environ,
#                          try/except
#   load_postgres.py       las tablas actor, repo, actor_repo, sus
#                          índices, time.perf_counter()
#   load_neo4j.py          lo básico de Cypher (MATCH, patrones,
#                          $parámetros), database_=
#   test_integration.py    el recorrido de 2 saltos escrito como un
#                          SELF-JOIN de SQL y como un patrón de Cypher
#   pipeline.py            sql.SQL / sql.Identifier, autocommit=True
#   profile_schema.py      la RECURSIÓN (una función que se llama a sí
#                          misma)
#   drop_databases.py      la copia más reciente, con el mismo estilo
#
# Lo que es NUEVO aquí — esto es el CORAZÓN de la investigación:
#   - los recuentos de "un salto" de cada actor (que sirven para elegir
#     desde quién empezar), en SQL (un self-join + GROUP BY) y en Cypher;
#   - el recorrido MEDIDO: "¿a cuántos actores se puede llegar en como
#     máximo N saltos?", escrito como una CTE RECURSIVA de SQL (WITH
#     RECURSIVE) y como un PATRÓN DE CAMINO CUANTIFICADO de Cypher
#     ( ... ){1,N};
#   - un LÍMITE DE TIEMPO en cada consulta (statement_timeout /
#     Query(timeout=));
#   - una @dataclass (Outcome) para devolver un resultado en un único
#     objeto ordenado;
#   - preguntar a cada base de datos CUÁNTO TRABAJO ha hecho: EXPLAIN
#     (ANALYZE, BUFFERS) en PostgreSQL y PROFILE en Neo4j;
#   - la diferencia entre el tiempo que informa el SERVIDOR y el tiempo
#     que mide Python.
#
# La pregunta de la investigación: ¿a partir de qué PROFUNDIDAD de
# recorrido, y con cuántos DATOS, empieza Neo4j (una base de datos de
# grafos) a ganar a PostgreSQL (una relacional)? Este archivo contiene la
# única pregunta que se hace a las dos, escrita una sola vez, para que los
# dos scripts que la usan pregunten exactamente lo mismo.
#
# Cómo se usa el archivo real (nunca directamente):
#     ./run.sh scripts/choose_starts.py --database <nombre>
#     ./run.sh scripts/measure.py --database <nombre> ...
########################################################################

"""The research queries, the same question asked to PostgreSQL (SQL) and to Neo4j (Cypher).

Used by choose_starts.py and measure.py; it isn't run by itself.

Two questions:

* ONE_HOP: for every actor, how many distinct OTHER actors share at least one
  repo with it ("reached in one hop"), and how many distinct repos it touched.
  This chooses the starting actors.

* REACH: from one starting actor, how many distinct other actors can be
  reached in at most N hops, one hop being actor -> repo -> actor. This is the
  traversal that is measured.

Both databases must give exactly the same numbers; measure.py checks it every time.
"""

# ---------------------------------------------------------------------
# os, time, psycopg, GraphDatabase, sql, load_neo4j: todos vistos antes.
#
# NUEVO:
#   from dataclasses import dataclass
#       un DECORADOR que escribe por ti las partes aburridas de una clase
#       pequeña (ver Outcome más abajo).
#   from neo4j import ... Query
#       un envoltorio alrededor de un texto Cypher que puede llevar
#       OPCIONES consigo; aquí la opción es un límite de tiempo (ver
#       run_neo4j_reach()).
# ---------------------------------------------------------------------
import os
import time
from dataclasses import dataclass

import psycopg
from neo4j import GraphDatabase, Query
from psycopg import sql

import load_neo4j

# ---------- ONE_HOP: used to choose the starting actors ----------

# ---------------------------------------------------------------------
# SQL_ONE_HOP — para CADA actor: a cuántos otros llega en un salto
# ("reached"), y cuántos repos ha tocado ("repos").
#
# ¿QUÉ ES UN SALTO? actor -> repo -> otro actor. Dos actores están a un
# salto si comparten al menos un repo. (En test_integration.py el mismo
# recorrido se llamaba "2 saltos" porque contaba cada flecha; en la
# investigación, UN SALTO = un paso de actor a actor = dos flechas.)
#
# WITH nombre AS (...)  — una CTE ("Common Table Expression", expresión
# de tabla común): un resultado temporal con nombre que luego puedes usar
# como una tabla en el resto de la consulta. Aquí hay dos, separadas por
# una coma: reach y degree. Es solo una forma de escribir una consulta
# grande en trozos legibles.
#
# reach — el SELF-JOIN (explicado en test_integration.py):
#   actor_repo aparece dos veces, como a1 ("el actor para el que
#   contamos") y a2 ("los demás"). `a2.repo_id = a1.repo_id` empareja cada
#   fila de a1 con todas las filas del mismo repo; `a2.actor_id <>
#   a1.actor_id` (<> significa "distinto de") quita al propio actor.
#   GROUP BY a1.actor_id produce UNA fila de salida por actor; el recuento
#   se calcula dentro de cada grupo.
#   count(DISTINCT a2.actor_id): alguien que comparte TRES repos con a1
#   aparece en tres filas del join, pero debe contarse una sola vez.
#
#   Ejemplo pequeño. actor_repo contiene (1,R), (2,R), (2,S), (3,S):
#     actor 1: comparte R con 2                     -> reached 1
#     actor 2: comparte R con 1, S con 3            -> reached 2
#     actor 3: comparte S con 2                     -> reached 1
#
# degree — el número de repos del actor ("degree", grado, es la palabra de
#   grafos para "cuántas aristas tocan este nodo"). Basta con count(*) por
#   actor: la clave primaria (actor_id, repo_id) garantiza que cada par
#   aparece una sola vez.
#
# El SELECT final pone los trozos uno al lado del otro:
#   JOIN degree d USING (actor_id)   USING (col) = "unir por la columna que
#                                    se llama así en las dos tablas".
#   JOIN actor a ON a.id = ...       para obtener el login, para mostrarlo.
#
# Nota: un actor que no comparte ningún repo con nadie no tiene fila en
# `reach` (el self-join no encuentra nada para él), así que simplemente no
# aparece en la respuesta. La versión en Cypher se comporta igual.
#
# Esta consulta se ejecuta sobre la tabla ENTERA, así que es pesada en
# bases de datos grandes — por eso choose_starts.py la ejecuta una sola
# vez y guarda el resultado.
# ---------------------------------------------------------------------
SQL_ONE_HOP = """
WITH reach AS (
    SELECT a1.actor_id, count(DISTINCT a2.actor_id) AS reached
    FROM actor_repo a1
    JOIN actor_repo a2 ON a2.repo_id = a1.repo_id AND a2.actor_id <> a1.actor_id
    GROUP BY a1.actor_id
), degree AS (
    SELECT actor_id, count(*) AS repos FROM actor_repo GROUP BY actor_id
)
SELECT r.actor_id, a.login, r.reached, d.repos
FROM reach r
JOIN degree d USING (actor_id)
JOIN actor a ON a.id = r.actor_id
"""

# ---------------------------------------------------------------------
# CYPHER_ONE_HOP — la misma pregunta en Cypher.
#
# MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
#   El recorrido de un salto DIBUJADO como un patrón (visto en
#   test_integration.py): a apunta a un repo, y b apunta al mismo repo.
#   Sin un inicio fijo, Neo4j busca este patrón para CADA actor a.
# WHERE a <> b       lo mismo que el "no el propio actor" del SQL.
#
# WITH a, count(DISTINCT b) AS reached
#   En Cypher, WITH es una "tubería" entre dos partes de una consulta: solo
#   continúa lo que se enumera. Poner una agregación (count) junto a `a`
#   AGRUPA por a — Cypher no tiene la palabra clave GROUP BY: todo lo que
#   no es una agregación es la clave de agrupación. Así que: una fila por
#   actor, con su recuento.
#
# MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
#   Segundo paso, empezando de nuevo desde cada a: sus repos.
# RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
#   Otra vez, una agregación (count(r)) agrupa por todo lo demás del
#   RETURN. count(r) cuenta aristas; el cargador creó una arista por cada
#   par actor-repo, así que es el número de repos. Los nombres de AS son
#   los MISMOS que los nombres de columna del SQL, para que
#   choose_starts.py pueda comparar las dos respuestas clave por clave.
# ---------------------------------------------------------------------
CYPHER_ONE_HOP = """
MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
WHERE a <> b
WITH a, count(DISTINCT b) AS reached
MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
"""

# ---------- REACH: the measured traversal ----------

# ---------------------------------------------------------------------
# SQL_REACH — una CTE RECURSIVA
#
# La pregunta: partiendo de UN actor, ¿a cuántos otros actores distintos
# se puede llegar en COMO MÁXIMO N saltos? Con JOIN normales harían falta
# un par de JOIN más por cada salto, así que una consulta distinta para
# cada profundidad. Una CTE RECURSIVA escribe "un salto más" UNA sola vez
# y deja que PostgreSQL lo repita.
#
# WITH RECURSIVE reach(actor_id, depth) AS ( <ancla> UNION <parte recursiva> )
#   reach es una tabla que PostgreSQL construye paso a paso; cada fila es
#   (un actor encontrado, a qué profundidad).
#
#   1. EL ANCLA (la parte antes de UNION) se ejecuta UNA vez y da la fila
#      de partida:
#          SELECT %(start)s::bigint, 0      -> (actor de partida, profundidad 0)
#      %(start)s es un PARÁMETRO CON NOMBRE: psycopg lo rellena a partir
#      del diccionario {"start": ..., "depth": ...} que se pasa con la
#      consulta, de forma segura (sin pegar texto). ::bigint es una
#      CONVERSIÓN de tipo, un "cast" ("trata esto como un BIGINT"), para
#      que la columna del ancla tenga el mismo tipo que
#      actor_repo.actor_id.
#
#   2. LA PARTE RECURSIVA (después de UNION) se refiere a la PROPIA
#      reach. Se ejecuta solo sobre las filas producidas en el paso
#      ANTERIOR, y sus filas nuevas pasan a ser la entrada del paso
#      siguiente:
#          FROM reach r                                     los actores hallados en el último paso
#          JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id sus repos
#          JOIN actor_repo ar2 ON ar2.repo_id = ar1.repo_id todos los de esos repos
#          SELECT ar2.actor_id, r.depth + 1                 = hallados un salto más allá
#      (Estos dos joins son exactamente el self-join de un salto de más
#      arriba; los dos índices que crea load_postgres.py — uno empezando
#      por actor_id, y otro por repo_id — sirven a las dos direcciones.)
#
#   3. SE DETIENE cuando un paso no produce filas nuevas.
#
#   Ejemplo, start = 1, con (1,R), (2,R), (2,S), (3,S) y N = 2:
#     ancla   -> (1, 0)
#     paso 1  -> (1, 1), (2, 1)              el repo R de 1 tiene a los actores 1 y 2
#     paso 2  -> (1, 2), (2, 2), (3, 2)      desde 1 y 2: repos R, S
#     fin (profundidad 2 = N)
#   Recuento final: actores distintos salvo el 1 -> {2, 3} -> 2.
#
# ¿POR QUÉ UNION Y NO UNION ALL? UNION descarta cualquier fila que sea un
# DUPLICADO exacto de una fila ya encontrada. Como una fila es (actor,
# profundidad), un actor al que se llega por 50 caminos distintos a
# profundidad 2 se guarda UNA sola vez a profundidad 2. Por tanto, cada
# nivel contiene como mucho una fila por actor — nunca una fila por
# CAMINO. Eso importa: el número de caminos se dispara con la profundidad
# (cada repo popular los multiplica); el número de actores, no.
# (NO quita de la profundidad 2 a un actor hallado a profundidad 1,
# porque (2, 1) y (2, 2) son filas distintas. Por eso el SELECT final usa
# DISTINCT.)
#
# ¿POR QUÉ EL LÍMITE DE PROFUNDIDAD (WHERE r.depth < %(depth)s)? Por dos
# razones:
#   - es la N de la pregunta ("en como máximo N saltos");
#   - sin él la consulta NO TERMINARÍA NUNCA: cada paso suma depth + 1,
#     así que cada fila es nueva (otra profundidad), y el grafo tiene
#     ciclos (A -> repo -> B -> repo -> A...). El límite es lo que la
#     detiene.
#
# La última línea: count(DISTINCT actor_id) sobre todos los niveles, sin
# contar al propio actor de partida (<> %(start)s).
# ---------------------------------------------------------------------
# Level by level: each row is (actor, depth). UNION drops a row already found at that
# depth, so every level holds at most one row per actor, never one row per path.
SQL_REACH = """
WITH RECURSIVE reach(actor_id, depth) AS (
    SELECT %(start)s::bigint, 0
    UNION
    SELECT ar2.actor_id, r.depth + 1
    FROM reach r
    JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id
    JOIN actor_repo ar2 ON ar2.repo_id  = ar1.repo_id
    WHERE r.depth < %(depth)s
)
SELECT count(DISTINCT actor_id) FROM reach WHERE actor_id <> %(start)s
"""

# ---------------------------------------------------------------------
# CYPHER_REACH — un PATRÓN DE CAMINO CUANTIFICADO (Neo4j 5.9 y posteriores)
#
# Una vez aplicado el formateo de Python de más abajo, la consulta queda
# así (para N = 3):
#
#   MATCH (a:Actor {id: $start})
#         ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){1,3}
#         (b:Actor)
#   WHERE b <> a
#   RETURN count(DISTINCT b)
#
#   (a:Actor {id: $start})   el inicio: el nodo Actor cuya propiedad id
#                            es igual al parámetro $start.
#   ( ...un salto... ){1,3}  la parte entre paréntesis es UN salto
#                            (actor -> repo <- actor), y {1,3} es un
#                            CUANTIFICADOR: "repite esto de 1 a 3 veces",
#                            como {1,3} en una expresión regular. El
#                            último actor de una repetición es el primero
#                            de la siguiente, y el primero de todos es la
#                            propia `a`.
#   (b:Actor)                el actor donde termina el camino.
#   count(DISTINCT b)        cuántos actores finales distintos hay.
#
# Compáralo con SQL: el salto se dibuja una vez y se repite, igual que la
# parte recursiva de la CTE — pero la forma de pensar es distinta. El
# MATCH de Cypher busca CAMINOS (en un mismo camino no se puede usar dos
# veces la misma arista) y DISTINCT quita los actores finales repetidos
# solo AL FINAL; el SQL quita las repeticiones en CADA nivel. Las dos dan
# el mismo conjunto de actores; cuánto trabajo necesita cada una para
# llegar a él es exactamente lo que mide la investigación.
#
# POR QUÉ LA PROFUNDIDAD SE ESCRIBE EN EL TEXTO: Cypher solo acepta un
# número literal dentro de {1,N}, no un $parámetro. Así que la consulta
# es una PLANTILLA, y str.format() de Python escribe el número (ver
# cypher_reach()). En una plantilla de format, {depth} es un hueco que
# rellenar, y una llave DOBLE {{ o }} significa "una llave de verdad, no
# un hueco". Así:
#   {{id: $start}}      se convierte en   {id: $start}
#   {{1,{depth}}}       se convierte en   {1,3}       (con depth=3)
# $start sigue siendo un parámetro normal, que rellena el driver.
# ---------------------------------------------------------------------
# A quantified path pattern: the group in brackets (one hop, actor -> repo -> actor) is
# repeated from 1 to N times. N can't be a query parameter, so it's written into the text.
CYPHER_REACH = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""


# ---------------------------------------------------------------------
# def cypher_reach(depth) -> str:
#
# Rellena la plantilla. Como la profundidad va en el TEXTO de la consulta
# (no en un parámetro seguro), primero se comprueba: {1,0} no tendría
# sentido, así que una profundidad menor que 1 lanza un ValueError en
# lugar de enviar una consulta rota.
# ---------------------------------------------------------------------
def cypher_reach(depth: int) -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    return CYPHER_REACH.format(depth=depth)


# ---------- running a query, with a time limit, on either side ----------

# ---------------------------------------------------------------------
# @dataclass  class Outcome — el resultado de UNA ejecución cronometrada.
#
# Una clase (explicada en summarize_data.py) normalmente necesita un
# método __init__ que copie cada argumento en self. @dataclass es un
# DECORADOR (la línea con @ justo encima de una clase o función, que le
# añade comportamiento): a partir de la lista de campos anotados de abajo,
# ESCRIBE ese __init__ por ti, además de una representación legible al
# imprimir (__repr__) y una comparación con ==.
# Así, Outcome("ok", 0.42, 1234) crea un objeto con .status = "ok",
# .seconds = 0.42, .count = 1234 y .error = "".
#
# Los campos:
#   status   "ok", "timeout" o "error" — una sola palabra, fácil de contar
#            después.
#   seconds  el tiempo medido desde Python (ver run_postgres_reach()).
#   count    la respuesta; `int | None` = un int, o None cuando la
#            consulta no terminó (así que no hay respuesta — None, no 0,
#            porque 0 sería una respuesta real, y errónea).
#   error    = "" es un valor POR DEFECTO: se puede omitir, como cuando
#            todo va bien. Los campos con valor por defecto deben ir
#            después de los que no lo tienen.
#
# ¿Por qué una dataclass y no una tupla? outcome.status se lee mejor que
# outcome[0], y un error en el nombre de un campo da un error, no una
# posición equivocada en silencio.
# ---------------------------------------------------------------------
@dataclass
class Outcome:
    status: str            # "ok", "timeout" or "error"
    seconds: float         # wall-clock time seen from Python
    count: int | None      # the answer (None if it didn't finish)
    error: str = ""        # the error message, if any


# ---------------------------------------------------------------------
# Dos funciones auxiliares de conexión, para que los datos de conexión
# estén en un solo sitio.
#
# connect_postgres: autocommit=True (visto en pipeline.py), aquí por un
# motivo nuevo: cada consulta es su propia transacción. Si el límite de
# tiempo cancela una, una transacción normal se quedaría "abortada" y
# rechazaría todos los comandos posteriores en esa conexión; con
# autocommit la siguiente medición puede seguir sin más. La anotación
# `-> psycopg.Connection` indica el tipo que se devuelve.
#
# connect_neo4j: el mismo driver que en check_connections.py, con la
# dirección y el usuario reutilizados de load_neo4j.py.
# ---------------------------------------------------------------------
def connect_postgres(database: str) -> psycopg.Connection:
    return psycopg.connect(host="localhost", user="postgres", dbname=database, autocommit=True)


def connect_neo4j():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# def run_postgres_reach(conn, start, depth, timeout_s) -> Outcome:
#
# EL LÍMITE DE TIEMPO: SET statement_timeout = '60s'
#   Un ajuste de PostgreSQL para esta conexión: cualquier sentencia que
#   siga ejecutándose pasado ese tiempo la CANCELA el propio servidor. Los
#   recorridos profundos pueden tardar horas; la investigación necesita
#   poder decir "no terminó dentro del límite" en lugar de esperar
#   eternamente.
#   SET no acepta un parámetro %s, así que el valor se construye con
#   sql.Literal(...), que lo entrecomilla correctamente como '60s' (la
#   familia sql.SQL se explicó en pipeline.py). f"{timeout_s}s" convierte
#   60 en el texto "60s".
#
# EL CRONOMETRAJE: begin = time.perf_counter() justo antes de la
# consulta; la diferencia de después es el tiempo REAL (de reloj) visto
# desde Python: enviar la consulta, el trabajo del servidor y la vuelta
# de la respuesta. (El tiempo que el SERVIDOR dice haber empleado se
# recoge aparte, en postgres_work().)
#
# LA CONSULTA: conn.execute(SQL_REACH, {"start": ..., "depth": ...})
# rellena los huecos %(start)s y %(depth)s a partir del diccionario.
# fetchone()[0]: la única fila, su única columna — el recuento.
#
# TRES FINALES, un Outcome para cada uno:
#   ok        el recuento y el tiempo.
#   timeout   psycopg.errors.QueryCanceled es el error que envía
#             PostgreSQL cuando statement_timeout cancela la consulta.
#   error     cualquier otro error de la base de datos (psycopg.Error es
#             el padre de todos los errores de psycopg, QueryCanceled
#             incluido).
#   El ORDEN de las líneas `except` importa: Python usa la primera que
#   coincide, así que el QueryCanceled concreto debe ir antes que su padre
#   psycopg.Error, o un timeout acabaría etiquetado como "error".
#   str(error).strip(): el mensaje como texto, sin el salto de línea final.
# ---------------------------------------------------------------------
def run_postgres_reach(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> Outcome:
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    begin = time.perf_counter()
    try:
        count = conn.execute(SQL_REACH, {"start": start, "depth": depth}).fetchone()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except psycopg.errors.QueryCanceled as error:
        return Outcome("timeout", time.perf_counter() - begin, None, str(error).strip())
    except psycopg.Error as error:
        return Outcome("error", time.perf_counter() - begin, None, str(error).strip())


# ---------------------------------------------------------------------
# def run_neo4j_reach(driver, database, start, depth, timeout_s) -> Outcome:
#
# El mismo trabajo en el lado de Neo4j.
#
# driver.session(database=database)
#   Hasta ahora usábamos driver.execute_query(), un atajo de una sola
#   llamada. Una SESIÓN es la forma larga: una "conversación" con una base
#   de datos, abierta con `with` (para que se cierre después), en la que
#   session.run() envía una consulta. La necesitamos por el punto
#   siguiente.
#
# Query(cypher_reach(depth), timeout=timeout_s)
#   Envuelve el texto de la consulta junto con un LÍMITE DE TIEMPO en
#   segundos. El SERVIDOR Neo4j detiene la transacción de la consulta en
#   cuanto se supera el límite — el equivalente de statement_timeout.
#   start=start es el valor de $start.
#
# .single()[0]: la respuesta debe ser exactamente UN registro (single()
# se queja si no); [0] es su primera columna, el recuento.
#
# El `except` es amplio (Exception) a propósito, como dice el comentario:
# según el momento y la versión del driver, un timeout llega como clases
# de error distintas. Así que la decisión se toma por el MENSAJE:
#   "timeout" in str(error).lower()   ¿está la palabra en el mensaje?
#                                     (lower() para que "Timeout" y
#                                     "TIMEOUT" también coincidan)
#   X if condición else Y             una EXPRESIÓN CONDICIONAL: un
#                                     if/else de una línea que da un valor.
# [:300] se queda solo con los primeros 300 caracteres de un mensaje que
# puede ser enorme.
# ---------------------------------------------------------------------
def run_neo4j_reach(driver, database: str, start: int, depth: int, timeout_s: int) -> Outcome:
    begin = time.perf_counter()
    try:
        with driver.session(database=database) as session:
            count = session.run(Query(cypher_reach(depth), timeout=timeout_s), start=start).single()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except Exception as error:   # the driver raises different classes for a timeout
        status = "timeout" if "timeout" in str(error).lower() or "timed out" in str(error).lower() else "error"
        return Outcome(status, time.perf_counter() - begin, None, str(error).strip()[:300])


# ---------- the work done inside each database ----------

# ---------------------------------------------------------------------
# def postgres_work(conn, start, depth, timeout_s) -> dict:
#
# El TIEMPO no es lo único que merece la pena medir: depende del
# ordenador y de qué más se esté ejecutando. CUÁNTO TRABAJO hizo la base
# de datos (cuántos trozos de datos tocó, desde memoria o desde disco)
# explica POR QUÉ un lado es más rápido. measure.py llama a esta función
# una vez por profundidad, como una ejecución extra DESPUÉS de las
# cronometradas, porque medir el trabajo ralentiza un poco la consulta y
# no debe estropear los tiempos.
#
# EXPLAIN muestra el PLAN que eligió PostgreSQL para una consulta (qué
# índice, qué método de join...). Las opciones entre paréntesis:
#   ANALYZE      EJECUTA de verdad la consulta, e informa de números
#                reales en lugar de estimaciones. (No es lo mismo que el
#                comando ANALYZE de load_postgres.py, que actualiza las
#                estadísticas.)
#   BUFFERS      informa también de los BLOQUES usados. PostgreSQL guarda
#                tablas e índices en bloques de 8 kB, y mantiene en
#                memoria los bloques usados recientemente ("shared
#                buffers").
#   FORMAT JSON  da el informe como JSON, para que Python pueda leer las
#                cifras por su nombre en lugar de analizar texto.
#
# .fetchone()[0][0]: el informe es una fila con una columna que contiene
# una LISTA JSON (psycopg la convierte en una lista de Python); [0] es su
# único elemento, un diccionario. plan["Plan"] es el nodo SUPERIOR del
# árbol del plan, es decir, el último paso, cuyos números ya incluyen
# todos los pasos que tiene debajo (no hace falta sumarlos — a diferencia
# de Neo4j, más abajo).
#
# Las cifras que se guardan (dict.get() devuelve None si falta una clave):
#   server_ms            "Execution Time": milisegundos pasados dentro del
#                        servidor ejecutando la consulta (sin la
#                        planificación, y sin enviar la respuesta a Python).
#   blocks_from_memory   "Shared Hit Blocks": bloques que ya estaban en
#                        memoria.
#   blocks_from_disk     "Shared Read Blocks": bloques que PostgreSQL tuvo
#                        que leer de un archivo (del disco — o de la propia
#                        caché de archivos de Windows, que PostgreSQL no
#                        puede distinguir).
#   temp_blocks_written  "Temp Written Blocks": bloques escritos en
#                        archivos TEMPORALES porque el trabajo no cabía en
#                        la memoria permitida para un paso (el ajuste
#                        work_mem) — p. ej. un resultado intermedio enorme
#                        de la CTE recursiva. Una señal de que la consulta
#                        se está quedando sin memoria.
# Primero se fija el mismo límite de tiempo, ya que esto es una ejecución
# completa de la consulta.
# ---------------------------------------------------------------------
def postgres_work(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> dict:
    # EXPLAIN (ANALYZE, BUFFERS) runs the query and reports what it did. The top node's
    # buffer numbers include everything below it.
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    query = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + SQL_REACH
    plan = conn.execute(query, {"start": start, "depth": depth}).fetchone()[0][0]
    top = plan["Plan"]
    return {
        "server_ms": plan.get("Execution Time"),
        "blocks_from_memory": top.get("Shared Hit Blocks"),
        "blocks_from_disk": top.get("Shared Read Blocks"),
        "temp_blocks_written": top.get("Temp Written Blocks"),
    }


# ---------------------------------------------------------------------
# def _sum_profile(node, key) -> int:
#
# Un plan de Neo4j es un ÁRBOL de pasos ("operadores"), cada uno un
# diccionario con sus propias cifras y una lista de "children" (hijos: los
# pasos que lo alimentan). A diferencia de los de PostgreSQL, cada paso de
# Neo4j informa solo de SU PROPIO trabajo, así que el total es la suma
# sobre todo el árbol. Esta función lo recorre de forma RECURSIVA
# (recursión: profile_schema.py):
#   el valor de este nodo  +  la suma de _sum_profile(hijo) para cada hijo
# Un nodo sin hijos: node.get("children", []) da una lista vacía, la suma
# de nada es 0, y la recursión se detiene ahí.
# `node.get(key) or 0` convierte un valor que falta (None) en 0.
# El guion bajo al principio del nombre es una convención: "función
# auxiliar interna, no pensada para usarse desde otros archivos".
# ---------------------------------------------------------------------
def _sum_profile(node: dict, key: str) -> int:
    return (node.get(key) or 0) + sum(_sum_profile(child, key) for child in node.get("children", []))


# ---------------------------------------------------------------------
# def neo4j_work(driver, database, start, depth, timeout_s) -> dict:
#
# PROFILE delante de una consulta Cypher = el EXPLAIN ANALYZE de Neo4j:
# EJECUTA la consulta y registra, para cada paso de su plan, lo que hizo.
#
# result.consume() lee el resultado hasta el final y devuelve su RESUMEN
# (los metadatos, no las filas). summary.profile es el árbol del plan
# como diccionario (o None si no lo hay, de ahí el `or {}`).
#
# Las cifras que se guardan:
#   server_ms          result_available_after (ms hasta que el primer
#                      registro estuvo listo) + result_consumed_after (ms
#                      para entregar el resto): el tiempo pasado dentro
#                      del servidor.
#   db_hits            "database hits" (accesos a la base de datos): la
#                      unidad de trabajo de almacenamiento de Neo4j —
#                      aproximadamente uno por cada nodo, relación o
#                      propiedad consultada. Lo más parecido a "filas
#                      tocadas".
#   page_cache_hits    la PAGE CACHE (caché de páginas) de Neo4j es su
#   page_cache_misses  equivalente de los shared buffers de PostgreSQL: un
#                      hit (acierto) = la página de datos estaba en
#                      memoria, un miss (fallo) = hubo que leerla del
#                      disco.
#   memory_bytes       "GlobalMemory": el pico de memoria que necesitó la
#                      consulta, que está en los argumentos del paso
#                      superior. La clave que guarda los argumentos es
#                      "args" en algunas versiones del driver y
#                      "arguments" en otras, así que se prueban las dos
#                      (`A or B or {}` = el primero que no esté vacío).
#
# TIEMPO DEL SERVIDOR frente a TIEMPO DE PYTHON — se registran los dos a
# propósito:
#   - los `seconds` del Outcome (medidos en Python) son lo que esperaría
#     un USUARIO de la base de datos: incluyen la red, el driver y la
#     conversión de la respuesta a objetos de Python;
#   - server_ms es solo el trabajo propio de la base de datos.
#   La diferencia entre ambos es una sobrecarga que no tiene nada que ver
#   con el modelo de datos; comparar los tiempos del servidor deja esa
#   sobrecarga fuera de la comparación PostgreSQL contra Neo4j.
# ---------------------------------------------------------------------
def neo4j_work(driver, database: str, start: int, depth: int, timeout_s: int) -> dict:
    # PROFILE runs the query and reports, for every step of its plan, the database hits
    # and the page cache hits/misses; they're added up over the whole plan.
    with driver.session(database=database) as session:
        result = session.run(Query("PROFILE " + cypher_reach(depth), timeout=timeout_s), start=start)
        summary = result.consume()
    profile = summary.profile or {}
    arguments = profile.get("args") or profile.get("arguments") or {}
    return {
        "server_ms": summary.result_available_after + summary.result_consumed_after,
        "db_hits": _sum_profile(profile, "dbHits"),
        "page_cache_hits": _sum_profile(profile, "pageCacheHits"),
        "page_cache_misses": _sum_profile(profile, "pageCacheMisses"),
        "memory_bytes": arguments.get("GlobalMemory"),
    }
