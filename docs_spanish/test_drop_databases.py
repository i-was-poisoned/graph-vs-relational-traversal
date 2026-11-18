########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_drop_databases.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar, no ejecutarse (pytest solo busca pruebas en tests/,
# como indica pytest.ini). El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_drop_databases.py.
#
# Lee primero docs_spanish/test_extract_csv.py (lo básico de pytest: los
# nombres test_, assert, cómo ejecutar las pruebas) y
# docs_spanish/drop_databases.py (el script que se prueba). Eso NO se
# repite aquí. Este archivo se centra en lo que es NUEVO: comprobar que
# una función LANZA un error, con pytest.raises(), y probar REGLAS DE
# SEGURIDAD — lo que NUNCA debe ocurrir — en lugar de lo que sí debería
# ocurrir.
#
# Su papel en el proyecto: drop_databases.py borra bases de datos para
# siempre. Estas pruebas demuestran, sin ningún servidor en marcha, que su
# regla de nombres acepta todos los tipos de bases de datos del proyecto,
# rechaza las bases de datos propias de los servidores (y las que se les
# parecen), y que las funciones de borrado rechazan una base de datos del
# servidor ANTES siquiera de intentar conectarse.
#
# Las pruebas reales se ejecutan con:
#     python -m pytest
########################################################################

"""Unit tests for the safety rules of scripts/drop_databases.py (no network, no databases).

Run with:  python -m pytest
"""

# `import pytest`: aquí hace falta (a diferencia de algunos archivos de
# pruebas anteriores) porque usamos directamente una de sus herramientas:
# pytest.raises (ver la última prueba).
import pytest

# Las cuatro funciones que se prueban. is_project_database y
# project_databases son puras. drop_postgres y drop_neo4j normalmente
# tocarían un servidor — pero solo DESPUÉS de su guarda, y la guarda es lo
# que se prueba aquí.
from drop_databases import drop_neo4j, drop_postgres, is_project_database, project_databases


# ---------------------------------------------------------------------
# Una prueba por cada LADO de la regla: lo que se debe aceptar y lo que se
# debe rechazar. Un bucle sobre una tupla de nombres comprueba varios
# casos en una sola prueba. (La tupla está partida en dos líneas; dentro
# de paréntesis o corchetes Python deja que una línea continúe libremente.)
# Los nombres cubren todas las formas que usa el proyecto: la base de datos
# del benchmark, la de 24 horas en vivo, una por hora, una por volumen
# ("-6h") y la de la prueba de integración.
# ---------------------------------------------------------------------
def test_project_databases_are_recognised():
    for name in ("gharchive", "gharchive24h", "gharchive-2026-08-27-15", "gharchive-2026-08-27-15-6h",
                 "gharchivetest"):
        assert is_project_database(name)


# Las bases de datos propias de los servidores, más dos que SE LES PARECEN:
# "myothers" (un nombre sin relación) y "archive" (contiene parte de la
# palabra pero no empieza por "gharchive"). `assert not ...` afirma que el
# resultado es False.
def test_server_databases_are_never_project_databases():
    for name in ("postgres", "template0", "template1", "neo4j", "system", "myothers", "archive"):
        assert not is_project_database(name)


# Una lista mezclada, tal como la daría un servidor, sin ningún orden en
# particular. Compararla con == con la LISTA esperada comprueba el filtrado
# Y el orden a la vez. Fíjate en que el orden es ALFABÉTICO, carácter a
# carácter: "-" va antes que "2" en la tabla de caracteres, así que
# "gharchive-2026..." queda antes que "gharchive24h".
def test_project_databases_picks_only_the_project_ones_sorted():
    names = ["postgres", "gharchive24h", "template1", "gharchive", "neo4j", "gharchive-2026-11-09-9-5h"]
    assert project_databases(names) == ["gharchive", "gharchive-2026-11-09-9-5h", "gharchive24h"]


# ---------------------------------------------------------------------
# NUEVO: pytest.raises — probar que algo FALLA
#
#     with pytest.raises(ValueError, match="Refusing to delete"):
#         drop_postgres("postgres")
#
# se lee: "el código dentro de este bloque `with` DEBE lanzar un
# ValueError cuyo mensaje contenga 'Refusing to delete'".
#   - Si lo hace, el error se captura y la prueba sigue adelante (pasa).
#   - Si NO se lanza ningún error, la prueba FALLA ("DID NOT RAISE").
#   - Si se lanza un error DISTINTO, o el mensaje no coincide, la prueba
#     también falla.
# match= es una expresión regular que se busca en el mensaje; unas
# palabras normales como estas significan simplemente "contiene este
# texto".
#
# Por qué esto demuestra que la guarda va PRIMERO: durante las pruebas
# unitarias no hay ningún servidor en marcha. Si drop_postgres intentara
# conectarse antes de comprobar el nombre, lanzaría en su lugar un error
# de conexión de psycopg — un error distinto, así que la prueba fallaría.
# Y a drop_neo4j se le pasa None en lugar de un driver: si alguna vez
# llegara a driver.execute_query(...), fallaría con un AttributeError.
# Obtener exactamente ValueError demuestra que no se ejecutó nada de lo
# que hay después de la guarda.
# ---------------------------------------------------------------------
def test_drop_refuses_server_databases_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running.
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_postgres("postgres")
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_neo4j(None, "neo4j")
