########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/drop_databases.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su propósito
# es enseñar, no ejecutarse. El script real y "limpio" (sin nada de este
# comentario) es scripts/drop_databases.py.
#
# Este archivo asume que ya has leído las copias anotadas anteriores,
# sobre todo check_connections.py (psycopg, el driver de Neo4j,
# execute_query, os.environ, sys.exit, try/except) y pipeline.py
# (autocommit=True, el catálogo pg_database, sql.SQL + sql.Identifier,
# la base de datos "system" donde Neo4j gestiona las bases de datos,
# CREATE DATABASE ... WAIT). Todo eso NO se vuelve a explicar desde cero
# aquí.
#
# Lo que es NUEVO en este archivo:
#   - la operación PELIGROSA, DROP DATABASE, en ambos lados, y las
#     REGLAS DE SEGURIDAD que la rodean: una lista explícita de permitidos
#     ("gharchive*") y una lista de prohibidos (las bases de datos propias
#     de los servidores), comprobadas DENTRO de las propias funciones de
#     borrado, antes de que nada se conecte;
#   - pedir al usuario que CONFIRME escribiendo una palabra, con input();
#   - DROP DATABASE ... WITH (FORCE) (PostgreSQL) y
#     DROP DATABASE `x` IF EXISTS DESTROY DATA WAIT (Neo4j);
#   - COMPROBAR después que no queda nada, en lugar de fiarse de que los
#     borrados han funcionado.
#
# POR QUÉ EXISTE: cada volumen de datos de la investigación (1 hora,
# 6 horas, 12 horas, 1 día, ...) es su propio par de bases de datos,
# llamadas "gharchive-<fecha>-<hora>-<n>h", que construye build_hours.py.
# Se van acumulando. Este script las elimina todas de una vez, para volver
# a empezar las mediciones desde un estado limpio. Los archivos descargados
# en data/ se conservan, así que reconstruir una base de datos nunca exige
# una nueva descarga.
#
# Ejecútalo a través de run.sh (necesita PGPASSWORD y NEO4J_PASSWORD):
#     ./run.sh scripts/drop_databases.py
########################################################################

"""Delete every database this project created, in PostgreSQL and in Neo4j.

A project database is one called "gharchive" or whose name starts with
"gharchive": gharchive, gharchive24h, gharchive-<date>-<hour>..., gharchivetest.
The databases that come with the servers ("postgres" in PostgreSQL, "neo4j"
and "system" in Neo4j) are never touched, and neither are the downloaded
files in data/ (so nothing has to be downloaded again to rebuild a database).

It shows what it found and asks you to type "delete" before deleting
anything. Afterwards it checks that no project database is left on either side.
This can't be undone.

Usage:
    ./run.sh scripts/drop_databases.py
"""

# ---------------------------------------------------------------------
# os, sys, psycopg, GraphDatabase: explicados en check_connections.py.
# `from psycopg import sql`: las herramientas para construir texto SQL de
# forma segura (sql.SQL, sql.Identifier), explicadas en pipeline.py
# (ensure_databases).
#
# `import load_neo4j` / `import pipeline`: nuestros PROPIOS scripts
# importados como módulos (explicado en pipeline.py). De load_neo4j solo
# reutilizamos las constantes NEO4J_URI y NEO4J_USER (para que la
# dirección esté escrita en UN solo sitio), y de pipeline la función
# auxiliar servers_not_ready() (ver main()).
# ---------------------------------------------------------------------
import os
import sys

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import load_neo4j
import pipeline

# ---------------------------------------------------------------------
# SERVER_DATABASES — una LISTA DE PROHIBIDOS, escrita como un CONJUNTO
# (set, {...}).
#
# Son las bases de datos que vienen con los propios servidores:
#   PostgreSQL  postgres (la de por defecto, a la que te conectas),
#               template0 y template1 (los "moldes" de los que se copia
#               cada base de datos nueva). Borrar una plantilla rompe
#               CREATE DATABASE.
#   Neo4j       neo4j (la base de datos por defecto) y system (donde Neo4j
#               guarda sus usuarios y la lista de bases de datos — borrarla
#               rompería el servidor entero).
#
# Ninguna empieza por "gharchive", así que la prueba del nombre de más
# abajo ya las descartaría. La lista de prohibidos es una SEGUNDA red de
# seguridad, independiente: "defensa en profundidad". Con una operación
# destructiva conviene tener dos cerrojos, para que un solo error en una
# regla no baste para provocar un desastre.
#
# Se usa un conjunto porque la única pregunta que se le hace es "¿está
# este nombre DENTRO?", y un conjunto la responde al instante.
# ---------------------------------------------------------------------
# Names that may never be deleted, whatever they look like.
SERVER_DATABASES = {"postgres", "template0", "template1", "neo4j", "system"}


# ---------------------------------------------------------------------
# def is_project_database(name) -> bool:
#
# LA regla de todo el script, en una línea: un nombre es una base de datos
# del proyecto si EMPIEZA POR "gharchive" (una LISTA DE PERMITIDOS por
# prefijo) Y no está en la lista de prohibidos. str.startswith() devuelve
# True o False.
#
# ¿Por qué un prefijo y no una lista fija de nombres? Porque las bases de
# datos por volumen tienen nombres que cambian con la fecha y el tamaño,
# p. ej. "gharchive-2026-08-27-15-6h"; un prefijo las atrapa todas, y nada
# más. Fíjate en que es "empieza por", no "contiene": "mygharchive" NO
# coincidiría, así que una base de datos que solo menciona la palabra está
# a salvo.
#
# Es una función PURA (no interviene ningún servidor), así que se puede
# probar con pruebas unitarias sin ninguna base de datos: eso es lo que
# hace tests/test_drop_databases.py.
# ---------------------------------------------------------------------
def is_project_database(name: str) -> bool:
    # gharchive, gharchive24h, gharchive-..., gharchivetest; nothing else.
    return name.startswith("gharchive") and name not in SERVER_DATABASES


# ---------------------------------------------------------------------
# def project_databases(names) -> list[str]:
#
# Filtra una lista de nombres para quedarse con los del proyecto y los
# ordena. `name for name in names if ...` es una EXPRESIÓN GENERADORA:
# una list comprehension sin los corchetes, que se pasa directamente a
# sorted(), que devuelve una LISTA nueva ordenada. Ordenarla hace que la
# lista impresa sea fácil de leer e idéntica de una ejecución a otra.
#
# También es pura: tanto postgres_databases() como neo4j_databases()
# pasan su respuesta en bruto por ella, así que la MISMA regla decide en
# ambos lados.
# ---------------------------------------------------------------------
def project_databases(names: list[str]) -> list[str]:
    # The project's databases among all the names a server reports, sorted.
    return sorted(name for name in names if is_project_database(name))


# ---------------------------------------------------------------------
# def postgres_databases() -> list[str]:
#
# Pregunta a PostgreSQL por todas las bases de datos que tiene. Se conecta
# a "postgres" (que siempre existe) y lee pg_database, el catálogo de
# bases de datos de PostgreSQL (visto en pipeline.py); la columna datname
# es el nombre. fetchall() devuelve una lista de tuplas de una columna,
# p. ej. [("postgres",), ("gharchive",), ...]; row[0] saca el nombre de
# cada una.
#
# Fíjate en que el `return` está FUERA del `with`: la conexión ya está
# cerrada cuando se hace el filtrado. Ya nada la necesita.
# ---------------------------------------------------------------------
def postgres_databases() -> list[str]:
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres") as conn:
        rows = conn.execute("SELECT datname FROM pg_database").fetchall()
    return project_databases([row[0] for row in rows])


# ---------------------------------------------------------------------
# def neo4j_databases(driver) -> list[str]:
#
# La misma pregunta para Neo4j, hecha a la base de datos "system"
# (database_= se explica en load_neo4j.py):
#   SHOW DATABASES          el comando de Neo4j que lista sus bases de
#                           datos.
#   YIELD name              se queda solo con la columna "name" de ese
#                           listado (tiene muchas: status, address,
#                           role...).
#   RETURN DISTINCT name    una fila por nombre. En un clúster la misma
#                           base de datos puede aparecer una vez por
#                           servidor; DISTINCT deja una sola copia.
# .records es la lista de filas de la respuesta; record["name"] lee una
# columna por su nombre, como en un diccionario.
#
# A diferencia de postgres_databases(), recibe el driver como PARÁMETRO
# en lugar de crear el suyo: main() abre UN solo driver y lo reutiliza en
# cada paso de Neo4j (un driver cuesta más de crear que una conexión de
# psycopg).
# ---------------------------------------------------------------------
def neo4j_databases(driver) -> list[str]:
    records = driver.execute_query("SHOW DATABASES YIELD name RETURN DISTINCT name", database_="system").records
    return project_databases([record["name"] for record in records])


# ---------------------------------------------------------------------
# def drop_postgres(name) -> None:
#
# 1. LA GUARDA va primero, antes de cualquier conexión:
#      if not is_project_database(name): raise ValueError(...)
#    `raise` detiene la función con un error (raise se explicó en
#    download_gharchive.py). ValueError es el error estándar de Python
#    para "el tipo es correcto pero el VALOR no es aceptable". Como la
#    comprobación está dentro de la propia función de borrado, ningún
#    código que la llame — el main() de hoy o algún script futuro — puede
#    borrar nunca "postgres" a través de ella, ni siquiera por error. El
#    archivo de pruebas comprueba exactamente esto.
#    En el mensaje, \' es una comilla ESCAPADA: la cadena está escrita
#    con comillas simples '...', así que el apóstrofo de "isn't" necesita
#    una barra invertida.
#
# 2. La conexión usa autocommit=True porque DROP DATABASE, igual que
#    CREATE DATABASE, no se puede ejecutar dentro de una transacción (ver
#    pipeline.py). Se conecta a "postgres": no puedes borrar la base de
#    datos a la que estás conectado.
#
# 3. El SQL:  DROP DATABASE IF EXISTS "name" WITH (FORCE)
#      DROP DATABASE   borra la base de datos y todos sus archivos.
#      IF EXISTS       sin error si ya no existe (solo un aviso).
#      WITH (FORCE)    (PostgreSQL 13+) primero cierra todas las demás
#                      conexiones a ella. Sin esto, una pestaña de pgAdmin
#                      abierta sobre esa base de datos hace que el DROP
#                      falle con "database is being accessed by other
#                      users".
#    sql.Identifier(name) pone el nombre entre comillas dobles: aquí hace
#    falta porque nombres como "gharchive-2026-08-27-15" contienen
#    guiones, que SQL leería si no como signos de resta.
# ---------------------------------------------------------------------
def drop_postgres(name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the PostgreSQL database "{name}" ...')
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    print(f'The PostgreSQL database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def drop_neo4j(driver, name) -> None:
#
# Primero la misma guarda, y después el comando de administración de
# Cypher, enviado a la base de datos "system":
#   DROP DATABASE `name`   las COMILLAS INVERTIDAS `...` delimitan un
#                          nombre en Cypher (el mismo papel que las
#                          comillas dobles en SQL); hacen falta por los
#                          guiones de los nombres.
#   IF EXISTS              sin error si ya no existe.
#   DESTROY DATA           borra también sus archivos de datos. (La otra
#                          opción, DUMP DATA, guardaría antes una copia —
#                          no la queremos: los datos siempre se pueden
#                          reconstruir a partir de data/.)
#   WAIT                   no vuelve hasta que el borrado ha terminado,
#                          para que la comprobación del paso 3 de main()
#                          vea el estado final (el mismo WAIT que en
#                          CREATE DATABASE).
#
# Aquí el nombre se pega en el texto con una f-string, porque Cypher
# tampoco acepta un nombre de base de datos como $parámetro. Eso solo es
# aceptable porque la guarda de arriba acaba de comprobar el nombre.
# ---------------------------------------------------------------------
def drop_neo4j(driver, name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the Neo4j database "{name}" ...')
    # DESTROY DATA: delete its files too. WAIT: don't return until it's gone.
    driver.execute_query(f"DROP DATABASE `{name}` IF EXISTS DESTROY DATA WAIT", database_="system")
    print(f'The Neo4j database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def main() -> None:
#
# Cuatro pasos numerados, cada uno anunciado con "== n." para que la
# salida se lea como una lista de comprobación:
#   0. ¿responden los dos servidores?    (si no, parar sin haber cambiado nada)
#   1. buscar las bases de datos del proyecto  (y mostrarlas)
#      -> confirmación: el usuario debe escribir "delete"
#   2. borrarlas
#   3. comprobar que no queda ninguna    (código de salida 1 si queda alguna)
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # Paso 0. pipeline.servers_not_ready() intenta una conexión rápida a
    # cada servidor (con un límite de 5 segundos) y devuelve None si los
    # dos responden, o una frase corta que dice cuál no lo hace.
    # `str | None` en su firma significa "una cadena, o None".
    #
    # Comprobar LOS DOS antes de tocar NINGUNO evita un trabajo a medias:
    # p. ej. borrar las bases de datos de PostgreSQL y luego fallar porque
    # Neo4j Desktop no está abierto, dejando los dos lados descompensados.
    # `is not None` es la forma correcta de comprobar None (no `!= None`).
    # -----------------------------------------------------------------
    print("== 0. Check that both servers are answering")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was deleted.")
        sys.exit(1)
    print("Both servers are answering.")

    # Un solo driver de Neo4j para toda la ejecución (ver neo4j_databases()).
    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        # -------------------------------------------------------------
        # Paso 1. `a, b = x(), y()` asigna dos variables en una sola
        # línea (desempaquetado de tuplas). El "\n" al principio de la
        # cadena imprime antes una línea vacía, para separar los pasos.
        #
        # ', '.join(lista) une los nombres en una sola cadena con ", "
        # entre ellos. Si la lista está vacía, join da "" — y
        # `"" or 'none'` da 'none', porque `or` devuelve su lado derecho
        # cuando el izquierdo está "vacío/es falso". Una forma corta de
        # imprimir "none" en lugar de nada.
        #
        # `not in_postgres`: una lista vacía cuenta como False, así que
        # esto significa "la lista está vacía". Si las dos están vacías no
        # hay nada que hacer, y `return` termina main() con normalidad
        # (código de salida 0).
        # -------------------------------------------------------------
        print("\n== 1. Find the project's databases")
        in_postgres, in_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL ({len(in_postgres)}): {', '.join(in_postgres) or 'none'}")
        print(f"Neo4j      ({len(in_neo4j)}): {', '.join(in_neo4j) or 'none'}")
        if not in_postgres and not in_neo4j:
            print("\nThere's nothing to delete: both servers are already clean.")
            return

        # -------------------------------------------------------------
        # LA CONFIRMACIÓN
        #
        # input(prompt) imprime el texto de petición y ESPERA a que el
        # usuario escriba una línea y pulse Intro; devuelve lo que se ha
        # escrito (como str).
        #
        # Dos formas en que input() puede fallar en lugar de devolver algo:
        #   EOFError           no hay teclado en absoluto — p. ej. el
        #                      script lo ejecutó un programador de tareas,
        #                      o con su entrada redirigida desde un
        #                      archivo vacío.
        #   KeyboardInterrupt  el usuario pulsó Ctrl+C.
        # Las dos se capturan y se tratan como una respuesta vacía, es
        # decir, "no". (`except (A, B):` captura cualquiera de los dos
        # tipos, como en download_gharchive.py.)
        #
        # answer.strip().lower(): strip() quita los espacios y el fin de
        # línea alrededor del texto, lower() lo pasa a minúsculas, así que
        # " Delete " también se acepta. CUALQUIER otra cosa — "y", "yes",
        # Intro sin más — se detiene.
        #
        # ¿Por qué una palabra entera y no "s/n"? Escribir "delete" es un
        # acto deliberado: no se puede hacer por reflejo. Lo seguro por
        # defecto es NO borrar nunca: solo una respuesta exacta sigue
        # adelante.
        # -------------------------------------------------------------
        print("\nThese databases and ALL their data will be deleted. This can't be undone.")
        print("(The server databases postgres, neo4j and system, and the files in data/, are kept.)")
        try:
            answer = input('Type "delete" to delete them, or anything else to stop: ')
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() != "delete":
            print("\nNothing was deleted.")
            return

        # Paso 2. Una base de datos cada vez; cada función de borrado vuelve
        # a comprobar el nombre (la guarda), aunque estas listas ya estén
        # filtradas.
        print("\n== 2. Delete them")
        for name in in_postgres:
            drop_postgres(name)
        for name in in_neo4j:
            drop_neo4j(driver, name)

        # -------------------------------------------------------------
        # Paso 3. CONFÍA, PERO COMPRUEBA: se vuelve a preguntar a los dos
        # servidores, con las mismas funciones que en el paso 1. Que un
        # comando "haya terminado sin error" no demuestra que el resultado
        # sea el que querías; volver a preguntar al servidor, sí. Si queda
        # algo, el código de salida 1 indica a quien ejecutó el script que
        # no ha tenido éxito del todo (códigos de salida:
        # check_connections.py).
        # -------------------------------------------------------------
        print("\n== 3. Check that none is left")
        left_postgres, left_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL: {', '.join(left_postgres) or 'no project database left'}")
        print(f"Neo4j:      {', '.join(left_neo4j) or 'no project database left'}")
        if left_postgres or left_neo4j:
            print("\nSome databases are still there (see above).")
            sys.exit(1)
        print("\nDone: both servers are clean.")


# main() y la protección `if __name__ == "__main__":`: el mismo propósito
# y la misma forma que en download_gharchive.py. Aquí la protección
# importa de verdad: el archivo de pruebas IMPORTA este módulo, e
# importarlo nunca debe ponerse a borrar nada.
if __name__ == "__main__":
    main()
