########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/check_connections.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive en
# docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script real y "limpio"
# (sin nada de este comentario) es scripts/check_connections.py.
#
# Este archivo asume que ya has leído las copias anotadas anteriores —
# los imports, las funciones, las f-strings, `with`, main() y la
# protección __name__ NO se vuelven a explicar desde cero aquí. Este
# archivo se centra en lo que es NUEVO en check_connections.py: los
# primeros paquetes EXTERNOS del proyecto (psycopg y neo4j), leer
# contraseñas desde VARIABLES DE ENTORNO, conectarse a un servidor de
# base de datos, y gestionar errores con try/except para que un fallo
# no oculte la otra comprobación.
#
# Cómo está pensado para ejecutarse — siempre a través de run.sh:
#     ./run.sh scripts/check_connections.py
# run.sh activa .venv (para que `import psycopg` / `import neo4j`
# funcionen) y carga secrets.sh (para que existan PGPASSWORD /
# NEO4J_PASSWORD). Este script hereda ambas cosas. Consulta
# project-notes.md, el paso 4 de "Instalación del software".
########################################################################

"""Check that Python can reach both of the project's databases.

Connects to PostgreSQL and to Neo4j with the passwords taken from the
environment (PGPASSWORD and NEO4J_PASSWORD, loaded from secrets.sh by run.sh)
and prints each server's version. Exits with an error if either one fails.

Usage:
    ./run.sh scripts/check_connections.py
"""

# ---------------------------------------------------------------------
# import os, import sys
#
# Ambos son módulos de la biblioteca estándar (vienen con Python).
#   os   — "operating system" (sistema operativo). Aquí solo usamos
#          os.environ: un objeto parecido a un dict que contiene las
#          VARIABLES DE ENTORNO que este proceso heredó de la terminal
#          (o de run.sh). Así es como las contraseñas llegan a Python
#          sin estar escritas nunca en el código.
#   sys  — "system" (sistema). Aquí solo usamos sys.exit(), que detiene
#          el programa e indica a quien lo ejecutó si ha tenido éxito
#          (ver main()).
# ---------------------------------------------------------------------
import os
import sys

# ---------------------------------------------------------------------
# import psycopg / from neo4j import GraphDatabase
#
# Estos son los primeros paquetes EXTERNOS del proyecto: no vienen con
# Python, se instalaron en .venv con `pip install -r
# requirements.txt`. Si .venv no está activado, estas dos líneas fallan
# con "ModuleNotFoundError" — una de las razones para pasar siempre por
# run.sh.
#
# La línea en blanco entre los dos grupos de imports es una convención:
# primero los imports de la biblioteca estándar, después los paquetes
# externos.
#
#   psycopg         — el conector de PostgreSQL.
#   GraphDatabase   — el punto de entrada del conector de Neo4j; solo
#                     necesitamos este nombre del paquete `neo4j`, de ahí
#                     `from neo4j import ...` en lugar de `import neo4j`.
# ---------------------------------------------------------------------
import psycopg
from neo4j import GraphDatabase

# ---------------------------------------------------------------------
# Ajustes de conexión, como constantes al principio (la misma idea que
# DEFAULT_FILE en los scripts anteriores): un único sitio donde mirar si
# algo cambia alguna vez.
#
# POSTGRES_SETTINGS es un diccionario cuyas claves son exactamente los
# nombres que espera connect() de psycopg:
#   host="localhost"     la base de datos corre en este mismo ordenador
#   dbname="gharchive"   la base de datos creada en el paso 1
#   user="postgres"      el superusuario creado por el instalador
# Aquí NO hay contraseña, a propósito: ver check_postgres().
#
# NEO4J_URI = "neo4j://localhost:7687"
#   La dirección del servidor Neo4j: protocolo neo4j://, este ordenador,
#   puerto 7687 (el puerto "Bolt", para programas; el 7474 es para el
#   navegador).
# NEO4J_USER = "neo4j" — el usuario por defecto de Neo4j.
# ---------------------------------------------------------------------
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"


# ---------------------------------------------------------------------
# def check_postgres() -> None:
#
# psycopg.connect(**POSTGRES_SETTINGS)
#   `**` DESEMPAQUETA un diccionario en argumentos con nombre, así que
#   esto es exactamente lo mismo que escribir:
#       psycopg.connect(host="localhost", dbname="gharchive", user="postgres")
#
# ¿Dónde está la contraseña? PGPASSWORD es un nombre estándar de
# variable de entorno que la biblioteca cliente de PostgreSQL (la que
# psycopg usa por debajo) busca por sí sola. Como run.sh la cargó desde
# secrets.sh, ya está en el entorno de este proceso — el código nunca la
# toca.
#
# `with ... as conn:` — el mismo patrón que `with open(...) as f:` en
# los scripts anteriores: la conexión se cierra automáticamente cuando
# termina el bloque, aunque algo salga mal dentro de él.
#
# conn.execute("SELECT version();") envía una consulta SQL al servidor.
# .fetchone() obtiene la primera (aquí, la única) fila de la respuesta,
# como una tupla; [0] toma su primera (única) columna — el texto de la
# versión.
# ---------------------------------------------------------------------
def check_postgres() -> None:
    # psycopg lee la contraseña de PGPASSWORD por sí solo.
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        version = conn.execute("SELECT version();").fetchone()[0]
    print(f"PostgreSQL OK: {version}")


# ---------------------------------------------------------------------
# def check_neo4j() -> None:
#
# os.environ["NEO4J_PASSWORD"]
#   A diferencia de PostgreSQL, el conector de Neo4j no busca una
#   contraseña por sí solo, así que la leemos nosotros del entorno y se
#   la pasamos. os.environ funciona como un diccionario: ["NOMBRE"] da
#   el valor de la variable.
#
# GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password))
#   Crea un DRIVER: el objeto que gestiona las conexiones con el
#   servidor Neo4j. auth= recibe una tupla (usuario, contraseña).
#   `with ... as driver:` lo cierra automáticamente al final.
#
# driver.verify_connectivity()
#   Crear un driver todavía no conecta de verdad. Esta línea fuerza una
#   conexión e inicio de sesión reales, así que una contraseña incorrecta
#   o una base de datos parada se notifica justo aquí, con un error
#   claro.
#
# driver.execute_query("CALL dbms.components() ...")
#   Envía una consulta Cypher (el lenguaje de consultas de Neo4j) — la
#   misma que se usa en Neo4j Browser en las notas para ver la versión.
#   Devuelve tres cosas; `records, _, _ = ...` se queda con la primera
#   (las filas del resultado) y descarta las otras dos. `_` es el nombre
#   convencional para "un valor que no necesito".
#
# Cada record se comporta como un diccionario: record['name'],
# record['versions'], record['edition']. 'versions' es una lista, así
# que [0] toma su primer elemento.
# ---------------------------------------------------------------------
def check_neo4j() -> None:
    password = os.environ["NEO4J_PASSWORD"]
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password)) as driver:
        driver.verify_connectivity()
        records, _, _ = driver.execute_query(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        )
    for record in records:
        print(f"Neo4j OK: {record['name']} {record['versions'][0]} ({record['edition']} edition)")


# ---------------------------------------------------------------------
# def main() -> None:
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # Primero, comprobar que las contraseñas están realmente ahí.
    #
    # os.environ.get(nombre) devuelve None (en lugar de un error) cuando
    # la variable no existe — la misma idea que dict.get() en
    # profile_schema.py. `not ...` es True cuando falta O está vacía.
    # La list comprehension recoge los nombres de las que faltan.
    #
    # sys.exit("algún texto") detiene el programa, imprime el texto e
    # informa de un FALLO a quien lo ejecutó. Comprobarlo de entrada da
    # un mensaje claro ("ejecútalo a través de run.sh") en lugar de un
    # error de autenticación confuso más adelante.
    # -----------------------------------------------------------------
    missing = [name for name in ("PGPASSWORD", "NEO4J_PASSWORD") if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. "
                 "Run this script through run.sh, which loads them from secrets.sh.")

    # -----------------------------------------------------------------
    # try / except — gestionar errores sin detenerlo todo
    #
    # Normalmente, un error (una EXCEPCIÓN) detiene el programa en el
    # acto. Si PostgreSQL fallara, nunca sabríamos si Neo4j funciona. Por
    # eso cada comprobación se ejecuta dentro de `try:`; si lanza una
    # excepción, Python salta a `except Exception as error:` en lugar de
    # detenerse, imprime cuál ha fallado y por qué, recuerda que algo ha
    # fallado, y el bucle sigue con la siguiente comprobación.
    #
    # El bucle recorre pares (nombre, función). `check` es la propia
    # función (sin paréntesis), y `check()` la llama — las funciones se
    # pueden guardar en variables y tuplas como cualquier otro valor.
    # -----------------------------------------------------------------
    failed = False
    for name, check in (("PostgreSQL", check_postgres), ("Neo4j", check_neo4j)):
        try:
            check()
        except Exception as error:
            print(f"{name} FAILED: {error}")
            failed = True

    # -----------------------------------------------------------------
    # sys.exit(1) — el CÓDIGO DE SALIDA
    #
    # Todo programa termina con un número que indica a quien lo ejecutó
    # cómo ha ido: 0 significa éxito, cualquier otro significa fallo.
    # Llegar al final del script con normalidad da 0; sys.exit(1) da 1.
    # Otros scripts (o run.sh) pueden usarlo para saber si la
    # comprobación ha pasado.
    # -----------------------------------------------------------------
    if failed:
        sys.exit(1)
    print("Both databases are reachable.")


# main() y la protección `if __name__ == "__main__":`: el mismo propósito
# y funcionamiento que en los otros scripts — consulta la copia anotada
# de download_gharchive.py para la explicación completa.
if __name__ == "__main__":
    main()
