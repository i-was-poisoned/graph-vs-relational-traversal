########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/choose_starts.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su propósito
# es enseñar, no ejecutarse. El script real y "limpio" (sin nada de este
# comentario) es scripts/choose_starts.py.
#
# Lee primero estas copias anotadas; lo que explican NO se repite aquí:
#   - download_gharchive.py   argparse, Path, main() y la protección
#                             __name__, lanzar un error
#   - extract_csv.py          sorted(...)
#   - load_neo4j.py           database_=
#   - summarize_data.py       las dict comprehensions, los anchos de
#                             columna en las f-strings
#   - pipeline.py             RawDescriptionHelpFormatter
#   - drop_databases.py       neo4j_databases() / postgres_databases()
#   - traversal.py            SQL_ONE_HOP / CYPHER_ONE_HOP (qué significan
#                             "reached" y "repos"), connect_postgres/neo4j
#
# Lo que es NUEVO aquí:
#   - POR QUÉ los actores de partida se ELIGEN CON UNA REGLA, y cuál es esa
#     regla;
#   - ordenar con una función KEY (clave) que devuelve una TUPLA, y usar
#     números negativos para ordenar algunas partes de mayor a menor;
#   - statistics.median() y "lo más cerca posible de la mediana";
#   - lambda (una función de una línea sin nombre);
#   - hacer la elección en LAS DOS bases de datos y negarse a seguir si no
#     coinciden (choose_in_both(), raise RuntimeError);
#   - las opciones con action="store_true" y parser.error().
#
# Este archivo es ahora sobre todo una BIBLIOTECA: measure.py lo importa
# y llama a choose_in_both() cuando necesita actores de partida. Los
# actores elegidos ya no se guardan en un archivo propio: se escriben en
# cada línea del archivo CSV de la medición en results/, y una medición
# posterior de la misma base de datos los reutiliza a partir de su último
# CSV (ver previous_starts en docs_spanish/measure.py).
#
# ¿POR QUÉ HAY QUE ELEGIR LOS ACTORES DE PARTIDA? El recorrido medido
# (REACH en traversal.py) parte de UN actor. Quién sea ese actor lo
# cambia todo: desde un actor muy conectado, la profundidad 2 ya puede
# alcanzar una gran parte del grafo; desde uno poco activo, casi nada. Si
# eligiéramos los actores a mano ("este parece interesante"), los
# resultados podrían quedar sesgados — incluso sin querer. Por eso la
# elección se hace con una REGLA fija, escrita aquí, que da la misma
# respuesta siempre:
#   - 10 actores "top": los más conectados (el caso más difícil);
#   - 10 actores "median": actores típicos (el caso habitual).
#
# Cómo se ejecuta por sí solo (research.sh lo hace así para construir su
# menú de bases de datos):
#     ./run.sh scripts/choose_starts.py --list-databases
########################################################################

"""Choose the starting actors for the measurements, the same on both sides.

For every actor it counts, in PostgreSQL and in Neo4j:
    reached = distinct other actors that share at least one repo with it (one hop)
    repos   = distinct repos it touched
and then picks two groups of 10:

    top     the 10 that reach the most actors in one hop
    median  the 10 whose "reached" is closest to the median, among the actors
            that reach at least one other actor (those that reach nobody are
            only a single JOIN, and tell nothing about traversals)

Ties are broken by more repos, then by the smaller id, so the choice never
changes. Both databases must give exactly the same 20 actors (with the same
numbers); otherwise the measurement doesn't start.

measure.py uses choose_in_both(). The chosen actors are saved as part of every
line of the measurement's CSV in results/, so a measurement repeated another
day reuses them.

Usage (only to list the databases that can be measured; research.sh uses it):
    ./run.sh scripts/choose_starts.py --list-databases
"""

# ---------------------------------------------------------------------
# NUEVO: `import statistics` — un módulo de la biblioteca estándar con
# las medidas resumen habituales (media, mediana, ...). Solo se usa
# statistics.median().
#
# `import drop_databases` / `import traversal`: nuestros propios scripts,
# usados como módulos. drop_databases aporta las funciones que listan las
# bases de datos del proyecto; traversal aporta las consultas y las
# conexiones.
# (csv, sys y Path ya no hacen falta: aquí no se guarda nada en ningún
# archivo, y un desacuerdo se LANZA como un error para measure.py.)
# ---------------------------------------------------------------------
import argparse
import statistics
import time

import drop_databases
import traversal

# GROUP_SIZE = 10: el tamaño de cada grupo (top, median).
GROUP_SIZE = 10


# ---------------------------------------------------------------------
# def ranking_key(actor) -> tuple:  — CÓMO ORDENAR, Y POR QUÉ UNA TUPLA
#
# Cada actor es un diccionario como
#     {"actor_id": 19, "login": "brynary", "reached": 340, "repos": 12}
# sorted(..., key=ranking_key) llama a ranking_key con cada actor y ordena
# los actores según lo que devuelve.
#
# Python compara las TUPLAS elemento a elemento, de izquierda a derecha,
# como las palabras en un diccionario: deciden los primeros elementos;
# solo si son IGUALES deciden los segundos; y así sucesivamente. Así, una
# sola tupla expresa "ordena por esto, luego por aquello, luego por lo
# otro".
#
# sorted() siempre ordena de MENOR a MAYOR. Para tener "los que MÁS
# alcanzan primero", el truco es un signo MENOS: -340 es menor que -12,
# así que el actor que alcanza 340 va antes que el que alcanza 12. Lo
# mismo con repos. El id NO se niega: gana el id MÁS PEQUEÑO.
#
# Ejemplo, tres actores:
#     A: reached 50, repos 3, id 7   -> clave (-50, -3, 7)
#     B: reached 50, repos 5, id 9   -> clave (-50, -5, 9)
#     C: reached 80, repos 1, id 4   -> clave (-80, -1, 4)
#   orden resultante: C (-80 es el menor), luego B (empate en -50, y
#   -5 < -3), luego A.
#
# ¿POR QUÉ ESTOS DESEMPATES? Muchos actores tienen el mismo recuento
# "reached". Sin un desempate, cuál de ellos entra en el top 10 podría
# depender del orden en que la base de datos devolviera las filas por
# casualidad — y PostgreSQL y Neo4j las devuelven en órdenes distintos.
# Con el desempate, el orden es TOTAL: dos actores distintos nunca pueden
# tener la misma clave (los ids son únicos), así que el resultado es
# siempre el mismo. "Más repos" va primero porque es un número con
# significado (más puntos de partida para el recorrido); el id es la regla
# final, arbitraria pero fija. (Un desempate natural sería "más eventos",
# pero los recuentos de eventos no se guardan en las bases de datos —
# solo los pares actor-repo.)
# ---------------------------------------------------------------------
def ranking_key(actor: dict) -> tuple:
    # Most reached first; ties: more repos first; then the smaller id.
    return (-actor["reached"], -actor["repos"], actor["actor_id"])


# El grupo top: ordenar todo por la clave y quedarse con los `size`
# primeros. [:size] es un slice (una porción): los elementos de 0 a
# size-1. `size: int = GROUP_SIZE` es un valor por defecto, para que las
# pruebas puedan pedir un grupo más pequeño.
def pick_top(actors: list[dict], size: int = GROUP_SIZE) -> list[dict]:
    return sorted(actors, key=ranking_key)[:size]


# ---------------------------------------------------------------------
# def pick_median(actors, exclude, size) -> list[dict]:  — LOS ACTORES TÍPICOS
#
# 1. reaching = solo los actores con reached >= 1. Un actor que no
#    alcanza a nadie da un recorrido que se detiene de inmediato (una
#    sola búsqueda): no mediría nada interesante. (En la práctica las
#    consultas ONE_HOP ya dejan fuera a esos actores; esta línea hace la
#    regla explícita y segura sea cual sea la entrada.)
#    Si no queda nadie (una base de datos vacía), no hay mediana: se
#    devuelve [].
#
# 2. statistics.median(...): ordena los números y toma el del MEDIO (con
#    una cantidad par, la media de los dos del medio, así que puede ser
#    p. ej. 3.5). ¿Por qué la mediana y no la media? Los datos están muy
#    SESGADOS: la mayoría de los actores alcanzan a un puñado de otros, y
#    unos pocos bots y proyectos populares alcanzan a miles. Esos pocos
#    tiran mucho de la media hacia arriba, así que la "media" no
#    describiría a nadie; la mediana es el actor que está en el centro de
#    la fila — uno realmente típico.
#
# 3. candidates = todos los de `reaching` EXCEPTO los actores de
#    `exclude` (el grupo top). En una base de datos pequeña los dos grupos
#    podrían solaparse; un actor medido dos veces con dos etiquetas
#    distorsionaría los dos grupos. `exclude` es un conjunto, así que
#    `not in exclude` es instantáneo.
#
# 4. La clave de ordenación, con una LAMBDA:
#        lambda a: (abs(a["reached"] - median),) + ranking_key(a)
#    `lambda a: <expresión>` es una función diminuta sin nombre: recibe a
#    y devuelve la expresión. Práctica cuando la función se usa una sola
#    vez, justo aquí. Lo que devuelve:
#      abs(...)            la DISTANCIA a la mediana (abs = valor
#                          absoluto: 3 por encima y 3 por debajo cuentan
#                          los dos como 3).
#      (x,)                una tupla con UN elemento (la coma es lo que la
#                          convierte en tupla).
#      + ranking_key(a)    `+` entre tuplas las UNE:
#                          (2,) + (-5, -3, 7) -> (2, -5, -3, 7).
#    Así: primero los más cercanos a la mediana; a igual distancia, los
#    mismos desempates que en el grupo top (más reached, más repos, id más
#    pequeño). Después [:size] se queda con los 10 más cercanos.
# ---------------------------------------------------------------------
def pick_median(actors: list[dict], exclude: set[int], size: int = GROUP_SIZE) -> list[dict]:
    # Only actors that reach someone; the median of their "reached"; then the closest ones,
    # with the same tie-break. Actors already in the top group are left out.
    reaching = [a for a in actors if a["reached"] >= 1]
    if not reaching:
        return []
    median = statistics.median(a["reached"] for a in reaching)
    candidates = [a for a in reaching if a["actor_id"] not in exclude]
    return sorted(candidates, key=lambda a: (abs(a["reached"] - median),) + ranking_key(a))[:size]


# ---------------------------------------------------------------------
# def choose(actors) -> list[dict]:  — los dos grupos, como una lista de filas
#
# exclude={a["actor_id"] for a in top}: una SET COMPREHENSION (llaves, sin
# clave: valor) — el conjunto de los ids del grupo top.
#
# El doble bucle construye una fila por cada actor elegido:
#   for group, members in (("top", top), ("median", median)):
#       recorre dos pares (nombre, lista), así que el mismo código sirve
#       para los dos.
#   for rank, actor in enumerate(members, start=1):
#       enumerate (peek_data.py) con start=1: posiciones 1..10, no 0..9.
#
# La fila en sí:
#   {"group": group, "rank": rank, **{k: actor[k] for k in (...)}}
#   {k: actor[k] for k in (...)} es una dict comprehension
#   (summarize_data.py) que copia esas cuatro claves del actor. `**`
#   DENTRO de un diccionario literal desempaqueta las claves y valores de
#   ese diccionario en el nuevo (el mismo `**` que para los argumentos
#   con nombre en check_connections.py). Resultado, p. ej.:
#   {"group": "top", "rank": 1, "actor_id": 19, "login": "...",
#    "reached": 340, "repos": 12}. measure.py copia estos valores en las
#   columnas start_... del CSV de resultados (start_group, start_rank,
#   start_actor_id, start_login, start_reach_1_hop).
# ---------------------------------------------------------------------
def choose(actors: list[dict]) -> list[dict]:
    top = pick_top(actors)
    median = pick_median(actors, exclude={a["actor_id"] for a in top})
    rows = []
    for group, members in (("top", top), ("median", median)):
        for rank, actor in enumerate(members, start=1):
            rows.append({"group": group, "rank": rank, **{k: actor[k] for k in ("actor_id", "login", "reached", "repos")}})
    return rows


# ---------------------------------------------------------------------
# Obtener los recuentos de cada base de datos, con la MISMA forma: una
# lista de diccionarios con las claves actor_id, login, reached, repos.
#
# postgres_actors: fetchall() da tuplas en el orden de columnas del
# SELECT (actor_id, login, reached, repos), que se convierten en
# diccionarios por posición.
#
# neo4j_actors: un record de Neo4j ya conoce los nombres de sus columnas
# (los nombres de AS de CYPHER_ONE_HOP, elegidos idénticos a los del
# SQL), así que dict(r) da directamente el mismo diccionario.
#
# Las filas llegan SIN ningún orden en particular en los dos lados — lo
# cual no es problema, porque choose() las ordena con un orden total (ver
# ranking_key).
# ---------------------------------------------------------------------
def postgres_actors(database: str) -> list[dict]:
    with traversal.connect_postgres(database) as conn:
        rows = conn.execute(traversal.SQL_ONE_HOP).fetchall()
    return [{"actor_id": r[0], "login": r[1], "reached": r[2], "repos": r[3]} for r in rows]


def neo4j_actors(database: str) -> list[dict]:
    with traversal.connect_neo4j() as driver:
        records = driver.execute_query(traversal.CYPHER_ONE_HOP, database_=database).records
    return [dict(r) for r in records]


# ---------------------------------------------------------------------
# def choose_in_both(database) -> list[dict]:  — LA MISMA ELECCIÓN, HECHA DOS VECES
#
# Esta es la función a la que llama measure.py. La elección se hace DOS
# VECES, de forma independiente: una con los recuentos de PostgreSQL y
# otra con los de Neo4j. Cada una tarda un rato en una base de datos
# grande, así que se imprime el tiempo (perf_counter: load_postgres.py;
# :.1f = un decimal). La primera f-string usa comillas simples '...' para
# poder contener comillas "dobles"; dos textos escritos uno junto a otro
# se unen en uno solo.
#
# LAS DOS BASES DE DATOS DEBEN COINCIDIR
#
# in_postgres != in_neo4j compara las dos LISTAS de diccionarios
# elemento a elemento: misma longitud, mismo orden, y cada diccionario
# igual (mismas claves, mismos valores). Cualquier diferencia — otro
# actor, o el mismo actor con otro recuento — significa que las dos
# bases de datos no contienen los mismos datos, y comparar sus
# velocidades no tendría sentido. Así que no se mide nada.
#
# differences: una list comprehension que se queda solo con los pares
# distintos (zip: test_pipeline.py), cada uno escrito en dos líneas, la
# de PostgreSQL encima de la de Neo4j ("\n" es un salto de línea dentro
# del texto).
#
# raise RuntimeError(...) — en lugar de imprimir y llamar ella misma a
# sys.exit(1), la función LANZA un error (raise: download_gharchive.py).
# RuntimeError es el error general de Python para "algo ha salido mal
# durante la ejecución". Una función de biblioteca no debería terminar
# todo el programa por su cuenta: informa del problema, y quien la llama
# decide. measure.py captura RuntimeError al final del todo, imprime el
# mensaje (las diferencias se le añaden con "\n".join) y sale con 1.
#
# Coinciden: se devuelve la lista de PostgreSQL (igual a la de Neo4j de
# todos modos).
# ---------------------------------------------------------------------
def choose_in_both(database: str) -> list[dict]:
    # The same choice made in each database; they must agree, or nothing is measured.
    print(f'Choosing the starting actors: counting, for every actor of "{database}", '
          "how many actors it reaches in one hop ...")
    begin = time.perf_counter()
    in_postgres = choose(postgres_actors(database))
    print(f"  PostgreSQL done in {time.perf_counter() - begin:.1f} s.")
    begin = time.perf_counter()
    in_neo4j = choose(neo4j_actors(database))
    print(f"  Neo4j done in {time.perf_counter() - begin:.1f} s.")
    if in_postgres != in_neo4j:
        differences = [f"  PostgreSQL {p}\n  Neo4j      {n}" for p, n in zip(in_postgres, in_neo4j) if p != n]
        raise RuntimeError("The two databases DON'T choose the same actors; nothing was measured.\n"
                           + "\n".join(differences))
    return in_postgres


# ---------------------------------------------------------------------
# def existing_databases() -> list[str]:
#
# Una base de datos solo se puede medir si existe en LOS DOS servidores
# (una construcción podría haber fallado a medias). Esto se queda con los
# nombres de PostgreSQL (ya filtrados y ordenados por drop_databases) que
# TAMBIÉN están en el conjunto de Neo4j: una INTERSECCIÓN, escrita como
# una list comprehension para que se mantenga el orden. La usa
# --list-databases (research.sh lee esa lista).
# ---------------------------------------------------------------------
def existing_databases() -> list[str]:
    # Project databases that exist on BOTH servers (the only ones that can be measured).
    with traversal.connect_neo4j() as driver:
        in_neo4j = set(drop_databases.neo4j_databases(driver))
    return [name for name in drop_databases.postgres_databases() if name in in_neo4j]


def main() -> None:
    # -----------------------------------------------------------------
    # Las opciones de la línea de comandos: solo queda una.
    #   --list-databases   action="store_true" crea un INTERRUPTOR de
    #                      encendido/apagado que no recibe ningún valor:
    #                      False si no aparece, True si se escribe.
    #                      (argparse convierte el guion en un guion bajo:
    #                      args.list_databases.)
    # El texto de ayuda está partido en dos líneas dentro de los
    # paréntesis, cosa que Python permite.
    #
    # Sin --list-databases no hay nada que hacer (elegir los actores es
    # ahora tarea de measure.py), así que parser.error("...") imprime la
    # línea de uso y el mensaje, y detiene el programa con el código de
    # salida 2 — igual que los propios errores de argparse.
    #
    # Con ella: se imprimen los nombres, uno por línea ("\n".join).
    # research.sh lee esta salida para construir su menú (ver
    # docs_spanish/research.sh).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-databases", action="store_true",
                        help="Print the project databases that exist on both servers, one per line")
    args = parser.parse_args()
    if not args.list_databases:
        parser.error("the only option is --list-databases (measure.py chooses the actors)")
    print("\n".join(existing_databases()))


# La protección __name__: download_gharchive.py.
if __name__ == "__main__":
    main()
