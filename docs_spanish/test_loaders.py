########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_loaders.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar. El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_loaders.py, y es ese el que ejecuta pytest.
#
# Este archivo asume que ya has leído docs_spanish/test_extract_csv.py
# (qué es una prueba de pytest, `assert`, la fixture tmp_path, las
# funciones auxiliares) y los dos cargadores anotados
# (docs_spanish/load_neo4j.py y docs_spanish/load_postgres.py).
#
# Solo se prueban las funciones de los cargadores que trabajan con
# ARCHIVOS: read_csv (Neo4j) y count_csv_rows (PostgreSQL). Cargar los
# datos en una base de datos real es trabajo de la prueba de integración,
# no de una prueba unitaria.
########################################################################

"""Unit tests for the CSV-reading helpers of the two loaders.

Only the parts that work on files are tested here; loading into a real
PostgreSQL or Neo4j database belongs to the integration test.

Run with:  python -m pytest
"""

from pathlib import Path

# Se importan funciones de DOS scripts distintos. Importar un cargador NO
# se conecta a ninguna base de datos: solo define sus funciones y
# constantes. Por eso estas pruebas no necesitan contraseñas ni que
# PostgreSQL o Neo4j estén en marcha.
from load_neo4j import read_csv
from load_postgres import count_csv_rows


# Función auxiliar: escribe un texto en un archivo y devuelve la ruta,
# para poder crear un CSV de prueba en una sola línea.
def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------- load_neo4j.read_csv ----------
# En los textos de abajo, "\n" es un salto de línea. Así
# "id,login\n1,ana\n2,bea\n" es un CSV de tres líneas:
#     id,login
#     1,ana
#     2,bea

def test_read_csv_converts_id_columns_to_int(tmp_path):
    file = write_text(tmp_path / "actors.csv", "id,login\n1,ana\n2,bea\n")
    # ("id",) es una tupla de UN elemento: la coma es la que la convierte
    # en tupla. Sin ella, ("id") sería solo el texto "id" entre paréntesis.
    rows = read_csv(file, ("id",))
    # Numbers, not text: in Neo4j, 1 and "1" are different values and would never match.
    # Fíjate: 1 sin comillas (número) pero "ana" con comillas (texto).
    assert rows == [{"id": 1, "login": "ana"}, {"id": 2, "login": "bea"}]


def test_read_csv_leaves_other_columns_as_text(tmp_path):
    # A login made of digits must stay text: only the columns we name are converted.
    file = write_text(tmp_path / "actors.csv", "id,login\n3,12345\n")
    rows = read_csv(file, ("id",))
    # "12345" sigue entre comillas: es texto, aunque parezca un número.
    assert rows == [{"id": 3, "login": "12345"}]


def test_read_csv_converts_both_columns_of_connections(tmp_path):
    # El archivo de conexiones tiene DOS columnas de ids, y las dos tienen
    # que ser números para que el MATCH de Neo4j encuentre los nodos.
    file = write_text(tmp_path / "actor_repo.csv", "actor_id,repo_id\n1,10\n")
    rows = read_csv(file, ("actor_id", "repo_id"))
    assert rows == [{"actor_id": 1, "repo_id": 10}]


# ---------- load_postgres.count_csv_rows ----------
# count_csv_rows es la cifra con la que load_postgres.py comprueba, al
# final, que cada tabla tiene tantas filas como su CSV. Si contara la
# cabecera, esa comprobación fallaría siempre por una fila.

def test_count_csv_rows_excludes_header(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n10,ana/project\n20,bea/tool\n")
    # Tres líneas en el archivo, pero solo dos filas de datos.
    assert count_csv_rows(file) == 2


def test_count_csv_rows_header_only_is_zero(tmp_path):
    # El caso límite: un CSV sin datos, solo con la cabecera (por ejemplo,
    # una hora en la que todos los eventos fueran de bots).
    file = write_text(tmp_path / "repos.csv", "id,name\n")
    assert count_csv_rows(file) == 0
