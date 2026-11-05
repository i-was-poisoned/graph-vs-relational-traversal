########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_extract_csv.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar. El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_extract_csv.py, y es ese el que ejecuta pytest.
#
# Este archivo asume que ya has leído docs_spanish/extract_csv.py — lo que
# hacen is_bot, remember_latest, extract y write_all NO se vuelve a
# explicar aquí. Este archivo se centra en lo que es NUEVO: qué es una
# prueba de pytest, `assert`, las "fixtures" tmp_path y caplog, y las
# funciones auxiliares que fabrican datos de prueba diminutos.
#
# QUÉ ES UNA PRUEBA DE PYTEST. Es una función normal de Python con dos
# reglas:
#   1. su nombre empieza por `test_`, y vive en un archivo cuyo nombre
#      también empieza por `test_`. Así pytest la encuentra solo: no hay
#      que registrarla en ningún sitio ni llamarla nosotros;
#   2. dentro usa `assert` ("afirmo que..."): si lo que sigue es verdad,
#      no pasa nada; si es falso, la prueba FALLA y pytest muestra los
#      valores que no coincidían.
#
# Se ejecutan todas, desde la carpeta del proyecto, con:
#     python -m pytest
########################################################################

"""Unit tests for scripts/extract_csv.py.

Each test builds a tiny GH Archive-like file (two or three made-up events) in a
temporary folder, so the tests run in milliseconds and need no downloaded data.

Run with:  python -m pytest
"""

# csv: para LEER los CSV que escribe write_all y comprobar su contenido.
import csv

# gzip: para CREAR un archivo .json.gz de prueba, igual que los de GH
# Archive, y así comprobar que extract también lee archivos comprimidos.
import gzip

# json: para convertir los eventos inventados (dicts de Python) en texto
# JSON, que es lo que hay en cada línea de un archivo de GH Archive.
import json
from pathlib import Path

# Importamos las funciones que vamos a probar directamente desde el
# script. ¿Cómo encuentra Python "extract_csv", si está en scripts/ y no
# en tests/? Gracias a la línea `pythonpath = scripts` de pytest.ini, que
# añade la carpeta scripts/ a los sitios donde Python busca módulos.
from extract_csv import extract, is_bot, remember_latest, write_all


# ---------------------------------------------------------------------
# FUNCIONES AUXILIARES (no son pruebas: su nombre NO empieza por test_,
# así que pytest no las ejecuta solas). Sirven para que cada prueba
# fabrique sus datos en una sola línea, en vez de repetir el mismo
# diccionario largo una y otra vez.
# ---------------------------------------------------------------------

# make_event: fabrica UN evento inventado. Solo lleva los campos que
# extract_csv.py lee de verdad (actor, repo, created_at); los eventos
# reales tienen muchos más, pero aquí no hacen falta.
#
# `created_at: str = "2026-08-27T15:00:00Z"` es un parámetro con valor por
# defecto: si la prueba no lo da, se usa esa fecha. Solo las pruebas que
# trabajan con fechas distintas (la del login renombrado) lo cambian.
def make_event(actor_id: int, login: str, repo_id: int, repo_name: str,
               created_at: str = "2026-08-27T15:00:00Z") -> dict:
    # Only the fields extract_csv.py reads; real events have many more.
    return {
        "actor": {"id": actor_id, "login": login},
        "repo": {"id": repo_id, "name": repo_name},
        "created_at": created_at,
    }


# write_events: escribe una lista de eventos en un archivo, en formato
# JSON Lines (un objeto JSON por línea), como GH Archive.
def write_events(path: Path, events: list[dict]) -> Path:
    # One JSON object per line (JSON Lines), like GH Archive; compressed if the name ends in .gz.
    #
    # json.dumps ("dump string") es lo contrario de json.loads: convierte
    # un dict de Python en texto JSON. A cada uno le añadimos "\n" (salto
    # de línea), y "".join(...) los pega todos en un solo texto.
    text = "".join(json.dumps(event) + "\n" for event in events)
    # Si el nombre termina en .gz, se escribe comprimido. gzip.open con
    # "wt" significa "write text": escribir (w) texto (t); gzip se encarga
    # de comprimirlo por el camino. Es el espejo del "rt" que usa
    # open_text() en extract_csv.py para leerlo.
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        # path.write_text: abre, escribe y cierra el archivo en una línea.
        path.write_text(text, encoding="utf-8")
    # Devolvemos la ruta para poder escribir, en las pruebas,
    # `file = write_events(...)` y usar `file` en la línea siguiente.
    return path


# ---------- is_bot ----------
# Tres casos: el que SÍ es un bot, el que claramente no, y la trampa:
# logins que contienen "bot" pero no terminan en "[bot]".

def test_is_bot_true_for_bot_suffix():
    # `assert algo`: la prueba pasa si `algo` es verdadero.
    assert is_bot("dependabot[bot]")


def test_is_bot_false_for_normal_login():
    # `assert not algo`: la prueba pasa si `algo` es FALSO.
    assert not is_bot("pedro")


def test_is_bot_false_when_bot_is_not_the_suffix():
    # Only the "[bot]" ending counts, not the word "bot" somewhere in the login.
    # Una prueba puede tener varios assert: tienen que cumplirse todos.
    assert not is_bot("robot")
    assert not is_bot("bot-builder")


# ---------- remember_latest ----------
# Los mismos tres pasos del ejemplo comentado en extract_csv.py: guardar
# un id nuevo, sustituir por un nombre más reciente, e IGNORAR uno más
# antiguo.

def test_remember_latest_stores_new_key():
    # Empezamos con un diccionario vacío...
    names = {}
    remember_latest(names, 7, "2026-08-27T15:10:00Z", "ana")
    # ...y comprobamos el diccionario ENTERO con `==`: tiene que contener
    # exactamente esto, ni más ni menos.
    assert names == {7: ("2026-08-27T15:10:00Z", "ana")}


def test_remember_latest_newer_name_replaces_older():
    # Aquí el diccionario ya empieza con un nombre guardado.
    names = {7: ("2026-08-27T15:10:00Z", "ana")}
    remember_latest(names, 7, "2026-08-27T15:30:00Z", "ana-dev")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


def test_remember_latest_older_name_is_ignored():
    # Events can arrive out of order: an older event must not undo a newer name.
    names = {7: ("2026-08-27T15:30:00Z", "ana-dev")}
    remember_latest(names, 7, "2026-08-27T15:20:00Z", "ana")
    # Nada ha cambiado: sigue el nombre de las 15:30.
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


# ---------- extract ----------
# LA FIXTURE tmp_path. Fíjate en que estas pruebas reciben un parámetro,
# `tmp_path`, que nadie les pasa a mano. Es una "fixture": una
# herramienta que pytest prepara y entrega sola cuando ve ese NOMBRE en
# los parámetros. tmp_path es una carpeta temporal NUEVA y VACÍA (un
# objeto Path), distinta para cada prueba. Así cada prueba escribe sus
# archivos sin pisar los de otra, y nadie tiene que borrarlos después.

def test_extract_normal_event(tmp_path):
    # `tmp_path / "hour.json"`: la misma barra de Path que en los scripts.
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")])
    # extract recibe una LISTA de archivos (aquí, de uno solo) y devuelve
    # cuatro cosas; las recibimos en cuatro variables a la vez.
    actors, repos, pairs, skipped_bots = extract([file])
    assert actors == {1: ("2026-08-27T15:00:00Z", "ana")}
    assert repos == {10: ("2026-08-27T15:00:00Z", "ana/project")}
    assert pairs == {(1, 10)}
    assert skipped_bots == 0


def test_extract_skips_bots(tmp_path):
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana", 10, "ana/project"),
        make_event(2, "dependabot[bot]", 10, "ana/project"),
    ])
    actors, repos, pairs, skipped_bots = extract([file])
    # set(actors) da el conjunto de las CLAVES del diccionario (los ids):
    # así comprobamos que solo está el actor 1, sin mirar sus nombres.
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert skipped_bots == 1


# LA FIXTURE caplog ("capture log"): otra herramienta de pytest, pedida
# igual, por su nombre. Recoge todo lo que se escribe en el log durante la
# prueba; caplog.text es ese texto. Sirve para comprobar que extract AVISA
# del evento saltado, no solo que lo salta.
def test_extract_skips_event_with_empty_repo(tmp_path, caplog):
    # The real case found on 2026-10-22: a ForkEvent whose repo was {} (no id, no name).
    # Este evento no lo fabrica make_event, porque necesitamos un repo
    # VACÍO, así que se escribe el diccionario a mano.
    empty_repo = {"actor": {"id": 2, "login": "bea"}, "repo": {}, "created_at": "2026-08-27T15:05:00Z"}
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project"), empty_repo])
    # `_` es un nombre de variable para "esto no me interesa": aquí, el
    # contador de bots.
    actors, repos, pairs, _ = extract([file])
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    # `in` con textos: ¿aparece esta frase DENTRO del texto del log?
    assert "Skipped 1 event(s) without an actor or repo id" in caplog.text


def test_extract_repeated_pair_counted_once(tmp_path):
    # Three events by the same actor on the same repo -> one connection.
    # `[algo] * 3` crea una lista con ese mismo elemento repetido 3 veces:
    # [evento, evento, evento].
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")] * 3)
    _, _, pairs, _ = extract([file])
    assert pairs == {(1, 10)}


def test_extract_keeps_latest_login(tmp_path):
    # El evento más reciente (15:30) va PRIMERO en el archivo, a propósito:
    # así comprobamos que gana por su fecha, no por llegar el último.
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana-dev", 10, "ana/project", "2026-08-27T15:30:00Z"),
        make_event(1, "ana", 10, "ana/project", "2026-08-27T15:10:00Z"),
    ])
    actors, _, _, _ = extract([file])
    # actors[1] es la tupla (fecha, login); [1] toma el segundo elemento,
    # el login.
    assert actors[1][1] == "ana-dev"


def test_extract_reads_several_files_plain_and_gz(tmp_path):
    # Dos archivos, como dos horas de la pipeline: uno normal y otro
    # comprimido (write_events lo comprime porque el nombre acaba en .gz).
    plain = write_events(tmp_path / "2026-10-20-5.json", [make_event(1, "ana", 10, "ana/project")])
    compressed = write_events(tmp_path / "2026-10-20-6.json.gz", [make_event(2, "bea", 20, "bea/tool")])
    actors, repos, pairs, _ = extract([plain, compressed])
    # Si se hubiera leído solo uno de los dos, faltaría un actor, un repo
    # y una conexión.
    assert set(actors) == {1, 2}
    assert set(repos) == {10, 20}
    assert pairs == {(1, 10), (2, 20)}


# ---------- write_all / write_csv ----------

def test_write_all_writes_headers_and_sorted_rows(tmp_path):
    # Los datos se dan DESORDENADOS a propósito (2 antes que 1), para
    # comprobar que write_all los ordena por id. "t" es una fecha de
    # relleno: write_all no la escribe, así que su valor no importa.
    actors = {2: ("t", "bea"), 1: ("t", "ana")}
    repos = {10: ("t", "ana/project")}
    pairs = {(2, 10), (1, 10)}
    write_all(tmp_path, actors, repos, pairs)

    # UNA FUNCIÓN DENTRO DE OTRA (función anidada). read() solo existe
    # dentro de esta prueba, y puede usar tmp_path porque lo "ve" desde
    # la función que la contiene. Lee un CSV y lo devuelve como una lista
    # de filas, y cada fila es una lista de textos. Así los tres assert
    # de abajo quedan cortos.
    def read(name: str) -> list[list[str]]:
        with open(tmp_path / name, encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    # Primero la cabecera, luego las filas ya ordenadas. Los números salen
    # como TEXTO ("1", no 1) porque un CSV es solo texto.
    assert read("actors.csv") == [["id", "login"], ["1", "ana"], ["2", "bea"]]
    assert read("repos.csv") == [["id", "name"], ["10", "ana/project"]]
    assert read("actor_repo.csv") == [["actor_id", "repo_id"], ["1", "10"], ["2", "10"]]
