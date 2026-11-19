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
#     RECURSIVE) y en DOS versiones de Cypher: "paths" (un PATRÓN DE
#     CAMINO CUANTIFICADO ( ... ){1,N}) y "levels" (nivel a nivel, como el
#     SQL, con CALL { ... }, UNWIND, collect() y listas);
#   - sql_joins() / cypher_hops(): cuántos joins / relaciones supone una
#     profundidad en cada lado;
#   - un LÍMITE DE TIEMPO en cada consulta (statement_timeout /
#     Query(timeout=));
#   - una @dataclass (Outcome) para devolver un resultado en un único
#     objeto ordenado;
#   - preguntar a cada base de datos CUÁNTO TRABAJO ha hecho: EXPLAIN
#     (ANALYZE, BUFFERS) en PostgreSQL y PROFILE en Neo4j, convertido en
#     cifras que se pueden comparar: MB de páginas de 8 KB procesadas, y
#     MB de memoria usada.
#
# La pregunta de la investigación: ¿a partir de qué PROFUNDIDAD de
# recorrido, y con cuántos DATOS, empieza Neo4j (una base de datos de
# grafos) a ganar a PostgreSQL (una relacional)? Este archivo contiene la
# única pregunta que se hace a las dos, escrita una sola vez, para que los
# dos scripts que la usan pregunten exactamente lo mismo.
#
# Cómo se usa el archivo real (nunca directamente: lo importa measure.py,
# y también choose_starts.py, al que llama measure.py):
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
# bases de datos grandes — por eso solo se ejecuta cuando se ELIGEN los
# actores de partida. Los actores elegidos se escriben en cada línea del
# archivo CSV de la medición en results/, y las mediciones posteriores de
# la misma base de datos los reutilizan a partir del último (ver
# previous_starts en docs_spanish/measure.py).
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
# DOS VERSIONES EN CYPHER DE LA MISMA PREGUNTA — ¿POR QUÉ?
#
# Las primeras mediciones usaban solo la versión "paths" de más abajo, y
# con 24 horas de datos SE DISPARÓ a profundidad 5-6 (se quedó sin
# tiempo) mientras que el SQL no. ¿Era por la BASE DE DATOS, o por CÓMO
# estaba ESCRITA la consulta Cypher? Para distinguir las dos cosas, la
# misma pregunta se hace también de una segunda forma, "levels", que
# sigue la estrategia del SQL:
#   paths    la forma natural de Neo4j: describir el recorrido como un
#            patrón.
#   levels   la estrategia nivel a nivel del SQL, escrita en Cypher.
# Si "levels" sigue siendo rápida donde "paths" se dispara, el problema
# era la forma de escribir la consulta, no el propio Neo4j. measure.py
# mide las dos (o una, con --cypher) y escribe una línea del CSV de
# resultados por versión; las dos deben dar exactamente el recuento del
# SQL.
#
# CYPHER_VERSIONS = ("paths", "levels"): los dos nombres, en una tupla,
# que usa measure.py (las opciones de --cypher) y que comprueba
# cypher_reach().
# ---------------------------------------------------------------------
# Two ways of asking the same question in Cypher (both must give the SQL's count):
#
# "paths"   A quantified path pattern: the group in brackets (one hop, actor -> repo ->
#           actor) is repeated from 1 to N times. Neo4j follows every PATH and removes
#           repeated actors only at the end, so the work grows with the number of paths.
# "levels"  Level by level, like the SQL: each step starts from the actors found in the
#           step before (the "frontier") and keeps only actors never seen before.
#
# N can't be a query parameter, so it's written into the text.
CYPHER_VERSIONS = ("paths", "levels")

# ---------------------------------------------------------------------
# CYPHER_REACH_PATHS — "paths": un PATRÓN DE CAMINO CUANTIFICADO (Neo4j 5.9 y posteriores)
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
# el mismo conjunto de actores, pero aquí el trabajo crece con el número
# de CAMINOS, y ese número se multiplica en cada salto (cada repo popular
# abre decenas de caminos nuevos): eso es lo que se disparó a profundidad
# 5-6 con 24 horas de datos.
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
CYPHER_REACH_PATHS = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""

# ---------------------------------------------------------------------
# "levels": TRES PIEZAS, UNIDAS POR cypher_reach()
#
# La idea es la del SQL: llevar dos LISTAS de actores y avanzar de nivel
# en nivel.
#   seen       todos los actores encontrados hasta ahora (incluido el de
#              partida)
#   frontier   los actores encontrados SOLO en el ÚLTIMO nivel: el salto
#              siguiente parte de ellos, no otra vez de todos
# Para la profundidad 3 la consulta es START + STEP + STEP + STEP + END.
#
# CYPHER_LEVELS_START
#   MATCH (start:Actor {id: $start})     busca el actor de partida.
#   WITH [start] AS seen, [start] AS frontier
#       [x] es una LISTA de Cypher con un solo elemento. WITH pasa las dos
#       listas al resto de la consulta (WITH: ver CYPHER_ONE_HOP más
#       arriba).
#   Esta pieza no pasa por .format(), así que las llaves siguen siendo
#   simples.
# ---------------------------------------------------------------------
CYPHER_LEVELS_START = """
MATCH (start:Actor {id: $start})
WITH [start] AS seen, [start] AS frontier
"""

# ---------------------------------------------------------------------
# CYPHER_LEVELS_STEP — UN salto, repetido una vez por nivel
#
# CALL (seen, frontier) { ... }
#   Una SUBCONSULTA: una consulta pequeña que se ejecuta dentro de la
#   grande. Los paréntesis tras CALL indican qué variables de fuera puede
#   usar (aquí, las dos listas). Su RETURN devuelve su resultado a la
#   consulta exterior. (Es un uso de CALL distinto del de
#   `CALL dbms.components()` en check_connections.py, que llama a un
#   procedimiento incorporado.)
#
# Dentro:
#   UNWIND frontier AS a      una fila por cada actor de la frontera
#                             (UNWIND: docs_spanish/load_neo4j.py).
#   MATCH (a)-...->(:Repo)<-...-(b:Actor)
#                             el salto, desde cada uno de esos actores.
#   WITH DISTINCT b           se queda con cada actor encontrado UNA sola
#                             vez, por muchos caminos que lleven a él —
#                             como el UNION del SQL. Esta es LA diferencia
#                             con "paths": las repeticiones se quitan en
#                             cada nivel, no solo al final.
#   WHERE NOT b IN seen       `x IN lista` es True si x está en la lista:
#                             descarta los actores ya encontrados en un
#                             nivel anterior.
#   RETURN collect(b) AS next collect() es una agregación (como count) que
#                             reúne los valores de todas las filas en UNA
#                             sola lista: los actores nuevos de este
#                             nivel.
#
# Después de la subconsulta:
#   WITH seen + next AS seen, next AS frontier
#       `+` entre dos listas las UNE: seen crece con los actores nuevos, y
#       los actores nuevos pasan a ser la frontera siguiente.
#
# Python repite después este texto `depth` veces (ver cypher_reach()). Si
# un nivel no encuentra a nadie nuevo, next es una lista vacía y los pasos
# siguientes simplemente no añaden nada.
# ---------------------------------------------------------------------
CYPHER_LEVELS_STEP = """
CALL (seen, frontier) {
    UNWIND frontier AS a
    MATCH (a)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
    WITH DISTINCT b
    WHERE NOT b IN seen
    RETURN collect(b) AS next
}
WITH seen + next AS seen, next AS frontier
"""

# CYPHER_LEVELS_END — size(lista) es su número de elementos. `seen`
# contiene todos los actores alcanzados, MÁS el propio actor de partida,
# de ahí el - 1: el mismo número que el recuento del SQL (que deja fuera
# el de partida con <> %(start)s).
CYPHER_LEVELS_END = """
RETURN size(seen) - 1
"""


# ---------------------------------------------------------------------
# def cypher_reach(depth, version="paths") -> str:
#
# Construye el texto Cypher para una profundidad y una versión.
#   version: str = "paths"   un valor POR DEFECTO: cypher_reach(3) sigue
#                            significando la versión "paths".
#
# Como la profundidad va en el TEXTO de la consulta (no en un parámetro
# seguro), primero se comprueba: {1,0} no tendría sentido, así que una
# profundidad menor que 1 lanza un ValueError en lugar de enviar una
# consulta rota.
#
#   "paths"    rellena la plantilla con str.format() (ver más arriba).
#   "levels"   une las piezas: START, después STEP `depth` veces, y
#              después END. `texto * 3` REPITE un texto:
#              "ab" * 3 == "ababab".
#   cualquier otra cosa: un ValueError. {version!r} en una f-string
#              muestra el valor con repr(), es decir, CON sus comillas
#              ('shortcut'), para que el mensaje deje claro qué se ha
#              recibido.
# tests/test_research.py comprueba los tres casos.
# ---------------------------------------------------------------------
def cypher_reach(depth: int, version: str = "paths") -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if version == "paths":
        return CYPHER_REACH_PATHS.format(depth=depth)
    if version == "levels":
        return CYPHER_LEVELS_START + CYPHER_LEVELS_STEP * depth + CYPHER_LEVELS_END
    raise ValueError(f"unknown Cypher version {version!r}: use one of {CYPHER_VERSIONS}")


# ---------------------------------------------------------------------
# sql_joins(depth) / cypher_hops(depth) — "CUÁNTO CAMINO" SUPONE UNA PROFUNDIDAD
#
# Dos números pequeños que se escriben en cada línea del CSV de
# resultados, para que quien lo lea vea qué significa una profundidad en
# cada lado:
#   sql_joins     un salto = actor_repo unida dos veces (actor -> sus
#                 repos, repo -> sus actores); la parte recursiva se
#                 ejecuta una vez por salto. Profundidad 3 -> 6 joins.
#   cypher_hops   un salto = dos relaciones INTERACTED_WITH recorridas
#                 (actor -> repo, repo <- actor). Profundidad 3 -> 6.
# Los dos valen 2 x profundidad: el mismo recorrido, contado en las
# unidades propias de cada base de datos. (Se comprueba en
# tests/test_research.py.)
# ---------------------------------------------------------------------
def sql_joins(depth: int) -> int:
    # Each hop of the recursive part joins actor_repo twice (actor -> repo, repo -> actor),
    # and the recursive part runs once per hop.
    return 2 * depth


def cypher_hops(depth: int) -> int:
    # Each hop follows two relationships: (actor)-[:INTERACTED_WITH]->(repo)<-[:INTERACTED_WITH]-(actor).
    return 2 * depth


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
# de la respuesta — el tiempo que esperaría un USUARIO de la base de
# datos. measure.py toma la MEDIANA de varios de esos tiempos (las
# columnas time_s del CSV de resultados).
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
# def run_neo4j_reach(driver, database, start, depth, timeout_s, version="paths") -> Outcome:
#
# El mismo trabajo en el lado de Neo4j. `version` indica qué versión de
# Cypher ejecutar ("paths" o "levels", ver cypher_reach()); measure.py la
# pasa.
#
# driver.session(database=database)
#   Hasta ahora usábamos driver.execute_query(), un atajo de una sola
#   llamada. Una SESIÓN es la forma larga: una "conversación" con una base
#   de datos, abierta con `with` (para que se cierre después), en la que
#   session.run() envía una consulta. La necesitamos por el punto
#   siguiente.
#
# Query(cypher_reach(depth, version), timeout=timeout_s)
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
def run_neo4j_reach(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> Outcome:
    begin = time.perf_counter()
    try:
        with driver.session(database=database) as session:
            count = session.run(Query(cypher_reach(depth, version), timeout=timeout_s), start=start).single()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except Exception as error:   # the driver raises different classes for a timeout
        status = "timeout" if "timeout" in str(error).lower() or "timed out" in str(error).lower() else "error"
        return Outcome(status, time.perf_counter() - begin, None, str(error).strip()[:300])


# ---------- the work done inside each database ----------

# ---------------------------------------------------------------------
# PAGE_MB — UNA PÁGINA, EN MEGABYTES
#
# Las dos bases de datos guardan sus datos en PÁGINAS de tamaño fijo de
# 8 KB (8192 bytes) y mantienen en memoria las páginas usadas
# recientemente: PostgreSQL las llama "blocks" (bloques) en sus "shared
# buffers", Neo4j "pages" (páginas) en su "page cache". Como el tamaño de
# página es el MISMO, el número de páginas que tocó cada lado se puede
# comparar directamente — y convertir en megabytes, que son más fáciles
# de imaginar: páginas x 8192 / 1024**2 (1 MB = 1024 x 1024 bytes; `**`
# es "elevado a"). 8192 / 1048576 = 0.0078125 MB.
# ---------------------------------------------------------------------
PAGE_MB = 8192 / 1024 ** 2   # both databases read and cache data in pages of 8 KB


# ---------------------------------------------------------------------
# def _postgres_memory_kb(node) -> float:  — LA MEMORIA DE LA CONSULTA, lado PostgreSQL
#
# Un plan de PostgreSQL es un ÁRBOL de pasos; cada nodo puede informar de
# cuánta memoria reservó su paso para sí mismo (PostgreSQL 18 da estas
# cifras en kB):
#   "Maximum Storage"     la UNION recursiva y el recorrido de la CTE (las
#                         filas de `reach` guardadas mientras se
#                         construye);
#   "Sort Space Used"     una ordenación;
#   "Peak Memory Usage"   una tabla hash (que se usa para joins y
#                         DISTINCT).
# Un paso que se quedó sin la memoria que tiene permitida (work_mem)
# sigue en DISCO: entonces "Storage" / "Sort Space Type" dice "Disk", y
# esa cantidad NO es memoria — se cuenta aparte, como temp_disk_mb (ver
# postgres_work()). `node.get("Storage", "Memory") == "Memory"`: si falta
# la clave, se supone que es memoria.
#
# `node.get(...) or 0` convierte un valor que falta (None) en 0, y la
# función recorre el árbol de forma RECURSIVA, como _sum_profile() más
# abajo: la memoria de este nodo + la suma sobre sus "Plans" (la palabra
# de PostgreSQL para los hijos). El resultado es la memoria total que
# usaron los pasos, en kB.
# ---------------------------------------------------------------------
def _postgres_memory_kb(node: dict) -> float:
    # The memory each step of the plan kept for itself (PostgreSQL 18 reports it in kB):
    # "Maximum Storage" (recursive union, CTE scan), "Sort Space Used", "Peak Memory Usage"
    # (hash tables). Only what stayed in memory; what went to disk is counted as temp.
    own = 0.0
    if node.get("Storage", "Memory") == "Memory":
        own += node.get("Maximum Storage") or 0
    if node.get("Sort Space Type", "Memory") == "Memory":
        own += node.get("Sort Space Used") or 0
    own += node.get("Peak Memory Usage") or 0
    return own + sum(_postgres_memory_kb(child) for child in node.get("Plans", []))


# ---------------------------------------------------------------------
# def postgres_work(conn, start, depth, timeout_s) -> dict:
#
# El TIEMPO no es lo único que merece la pena medir: depende del
# ordenador y de qué más se esté ejecutando. CUÁNTO TRABAJO hizo la base
# de datos (cuántos datos recorrió, cuánta memoria necesitó) explica POR
# QUÉ un lado es más rápido. measure.py llama a esta función una vez por
# profundidad, como una ejecución extra DESPUÉS de las cronometradas,
# porque medir el trabajo ralentiza un poco la consulta y no debe
# estropear los tiempos.
#
# EXPLAIN muestra el PLAN que eligió PostgreSQL para una consulta (qué
# índice, qué método de join...). Las opciones entre paréntesis:
#   ANALYZE      EJECUTA de verdad la consulta, e informa de números
#                reales en lugar de estimaciones. (No es lo mismo que el
#                comando ANALYZE de load_postgres.py, que actualiza las
#                estadísticas.)
#   BUFFERS      informa también de los BLOQUES (páginas de 8 KB) usados.
#   FORMAT JSON  da el informe como JSON, para que Python pueda leer las
#                cifras por su nombre en lugar de analizar texto.
#
# .fetchone()[0][0]: el informe es una fila con una columna que contiene
# una LISTA JSON (psycopg la convierte en una lista de Python); [0] es su
# único elemento, un diccionario. plan["Plan"] es el nodo SUPERIOR del
# árbol del plan, es decir, el último paso, cuyos números de BUFFERS ya
# incluyen todos los pasos que tiene debajo (no hace falta sumarlos — a
# diferencia de Neo4j, más abajo, y a diferencia de la memoria, de la que
# cada paso informa por su cuenta).
#
# from_memory, from_disk = A, B — dos variables asignadas en una línea.
#   "Shared Hit Blocks"    bloques que ya estaban en memoria.
#   "Shared Read Blocks"   bloques que PostgreSQL tuvo que leer de un
#                          archivo (del disco — o de la propia caché de
#                          archivos de Windows, que PostgreSQL no puede
#                          distinguir).
#
# Las cifras que se devuelven, todas en MB (pasan a ser las columnas
# pg_... del CSV de resultados, ver docs_spanish/measure.py):
#   data_processed_mb   (hits + reads) x PAGE_MB: todos los datos que
#                       recorrió la consulta. Una página usada dos veces
#                       cuenta dos veces: es una medida de TRABAJO, no
#                       del tamaño de los datos.
#   data_from_disk_mb   la parte que hubo que leer de un archivo.
#   memory_mb           _postgres_memory_kb(top) / 1024 (kB -> MB).
#   temp_disk_mb        "Temp Written Blocks": bloques escritos en
#                       archivos TEMPORALES porque el trabajo no cabía en
#                       la memoria permitida para un paso (el ajuste
#                       work_mem) — p. ej. un resultado intermedio enorme
#                       de la CTE recursiva. Una señal de que la consulta
#                       se está quedando sin memoria. (Neo4j no tiene una
#                       cifra así, por eso el CSV de resultados no tiene
#                       columna neo4j_temp_disk_mb.)
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
    from_memory, from_disk = top.get("Shared Hit Blocks") or 0, top.get("Shared Read Blocks") or 0
    return {
        "data_processed_mb": (from_memory + from_disk) * PAGE_MB,
        "data_from_disk_mb": from_disk * PAGE_MB,
        "memory_mb": _postgres_memory_kb(top) / 1024,
        "temp_disk_mb": (top.get("Temp Written Blocks") or 0) * PAGE_MB,
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
# def neo4j_work(driver, database, start, depth, timeout_s, version="paths") -> dict:
#
# PROFILE delante de una consulta Cypher = el EXPLAIN ANALYZE de Neo4j:
# EJECUTA la consulta y registra, para cada paso de su plan, lo que hizo.
# `version` elige la versión de Cypher que se perfila (ver
# cypher_reach()).
#
# result.consume() lee el resultado hasta el final y devuelve su RESUMEN
# (los metadatos, no las filas). summary.profile es el árbol del plan
# como diccionario (o None si no lo hay, de ahí el `or {}`).
#
#   hits, misses       la PAGE CACHE (caché de páginas) de Neo4j es su
#                      equivalente de los shared buffers de PostgreSQL,
#                      con las mismas páginas de 8 KB: un hit (acierto) =
#                      la página estaba en memoria, un miss (fallo) = hubo
#                      que leerla del disco. Sumados sobre el árbol.
#   memory             "GlobalMemory": la memoria que usó la consulta
#                      ENTERA, en BYTES, que está en los argumentos del
#                      paso superior. La clave que guarda los argumentos
#                      es "args" en algunas versiones del driver y
#                      "arguments" en otras, así que se prueban las dos
#                      (`A or B or {}` = el primero que no esté vacío).
#
# Las cifras que se devuelven — con los MISMOS nombres que las de
# postgres_work(), para que measure.py pueda tratar los dos lados igual
# (las columnas neo4j_...):
#   data_processed_mb   (hits + misses) x PAGE_MB — directamente
#                       comparable con la de PostgreSQL, porque las
#                       páginas tienen el mismo tamaño. Una página usada
#                       dos veces cuenta dos veces.
#   data_from_disk_mb   misses x PAGE_MB.
#   memory_mb           bytes / 1024**2 -> MB; None si Neo4j no informó
#                       de ella (`X if condición else None`, una expresión
#                       condicional).
# ---------------------------------------------------------------------
def neo4j_work(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> dict:
    # PROFILE runs the query and reports, for every step of its plan, the page cache
    # hits/misses; they're added up over the whole plan. GlobalMemory is the memory the
    # whole query used.
    with driver.session(database=database) as session:
        result = session.run(Query("PROFILE " + cypher_reach(depth, version), timeout=timeout_s), start=start)
        summary = result.consume()
    profile = summary.profile or {}
    arguments = profile.get("args") or profile.get("arguments") or {}
    hits, misses = _sum_profile(profile, "pageCacheHits"), _sum_profile(profile, "pageCacheMisses")
    memory = arguments.get("GlobalMemory")
    return {
        "data_processed_mb": (hits + misses) * PAGE_MB,
        "data_from_disk_mb": misses * PAGE_MB,
        "memory_mb": memory / 1024 ** 2 if memory is not None else None,
    }
