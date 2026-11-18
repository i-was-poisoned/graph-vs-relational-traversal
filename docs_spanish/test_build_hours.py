########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_build_hours.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar, no ejecutarse (pytest solo busca pruebas en
# tests/, como indica pytest.ini). El archivo real y "limpio" (sin nada de
# este comentario) es tests/test_build_hours.py.
#
# Lee primero estos archivos; lo que explican NO se repite aquí:
#   docs_spanish/test_extract_csv.py   lo básico de pytest (nombres test_,
#                                      assert, fixtures como tmp_path y
#                                      caplog)
#   docs_spanish/test_pipeline.py      la función auxiliar utc(), comparar
#                                      datetimes, `assert not`
#   docs_spanish/build_hours.py        las funciones que se prueban aquí
#
# Lo que es NUEVO aquí:
#   - pytest.raises: comprobar que una función LANZA un error (y con qué
#     mensaje);
#   - la fixture capsys: capturar lo que una función IMPRIME;
#   - SIMULAR EL TECLADO: una función que devuelve respuestas preparadas
#     (con iter(), next() y una lambda), que se pasa a ask_hours() en
#     lugar de input();
#   - *replies: una función que acepta cualquier número de argumentos.
#
# Su papel en el proyecto: build_hours.py hace preguntas y BORRA bases de
# datos, así que sus reglas tienen que cumplirse: las respuestas no
# válidas se rechazan, la fecha y la hora nunca se eligen por ti, las
# horas no publicadas se rechazan, los nombres nunca chocan con las otras
# bases de datos, y la comprobación de seguridad se niega a vaciar nada
# que no se llame "gharchive-...". Todo se prueba SIN red, sin bases de
# datos y sin que nadie escriba nada.
#
# Cómo ejecutar las pruebas reales (desde la carpeta del proyecto):
#     python -m pytest
########################################################################

"""Unit tests for the pure functions of scripts/build_hours.py (no network, no databases).

Run with:  python -m pytest
"""

from datetime import date, datetime, timezone

# Esta vez sí se importa el propio pytest, para pytest.raises (ver más
# abajo). (Las pruebas normales con assert no necesitan importarlo, y las
# fixtures tampoco.)
import pytest

# Un import largo, partido en dos líneas: dentro de ( ) Python deja que
# una línea continúe en la siguiente. Estas son las funciones que se
# prueban.
from build_hours import (ask_hours, chosen_hours, database_name, hours_are_published, may_be_emptied, parse_count,
                         parse_date, parse_hour, recreate_databases)

# ---------------------------------------------------------------------
# NOW — una "hora actual" FIJA para todas las pruebas: 2026-11-12 15:20
# UTC. build_hours.py recibe `now` como parámetro precisamente para que
# las pruebas puedan hacer esto. Con el reloj real, una prueba sobre
# "horas recientes" pasaría hoy y fallaría mañana. Se escribe en
# MAYÚSCULAS: es una constante.
# Con NOW, la hora actual es 15:00, así que el rango de horas más tardío
# que se acepta tiene que TERMINAR como muy tarde a las 14:00 (ver
# hours_are_published() en build_hours.py).
# ---------------------------------------------------------------------
NOW = datetime(2026, 11, 12, 15, 20, tzinfo=timezone.utc)


# La misma función auxiliar que en test_pipeline.py, sin minutos (aquí no
# hacen falta).
def utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


# ---------------------------------------------------------------------
# def answers(*replies): — el TECLADO SIMULADO.
#
# *replies — el asterisco reúne CUALQUIER NÚMERO de argumentos en una
#   sola tupla:
#   answers("2026-08-27", "15", "", "y")  ->  replies = ("2026-08-27", "15", "", "y")
#
# iter(replies) — convierte la tupla en un ITERADOR: un objeto que va
#   entregando los elementos DE UNO EN UNO y recuerda por dónde va.
# next(remaining) — da el siguiente elemento; la primera llamada da
#   "2026-08-27", la segunda "15", y así sucesivamente. (Si se acaban las
#   respuestas, next() lanza StopIteration y la prueba falla — señal de
#   que la función ha hecho más preguntas de las esperadas.)
#
# lambda prompt: next(remaining) — una LAMBDA es una función diminuta sin
#   nombre, escrita en una sola expresión. Es lo mismo que:
#       def fake_input(prompt):
#           return next(remaining)
#   Recibe `prompt` (el texto de la pregunta), como hace input(), lo
#   ignora y devuelve la siguiente respuesta preparada.
#
# answers(...) DEVUELVE esa función; las pruebas se la pasan como ask=...
# a ask_hours(), que la llama en lugar de input(). La lambda sigue usando
# `remaining` después de que answers() haya terminado: una función
# recuerda las variables del sitio donde se creó.
# ---------------------------------------------------------------------
def answers(*replies):
    # Stands in for the keyboard: each call returns the next ready-made answer.
    remaining = iter(replies)
    return lambda prompt: next(remaining)


# ---------- parse_date ----------

def test_parse_date_valid():
    assert parse_date("2026-08-27") == date(2026, 8, 27)


# ---------------------------------------------------------------------
# with pytest.raises(ValueError):
#     parse_date(bad)
#
# NUEVO: una prueba que ESPERA un error. Normalmente, un error dentro de
# una prueba hace que falle. Dentro de `with pytest.raises(ValueError):`
# es al revés: la prueba solo pasa si el código del bloque lanza un
# ValueError, y FALLA si se ejecuta sin lanzarlo.
#
# Las tres fechas incorrectas: el orden equivocado (día/mes/año), un mes
# que no existe (13) y una palabra. El bucle comprueba cada una; cada una
# tiene su propio `with`, porque el bloque se detiene en el primer error.
# ---------------------------------------------------------------------
def test_parse_date_rejects_other_formats():
    for bad in ("27/08/2026", "2026-13-01", "yesterday"):
        with pytest.raises(ValueError):
            parse_date(bad)


# match="older GH Archive format" — el error TAMBIÉN tiene que contener
# este texto en su mensaje. Así la prueba comprueba que es el error
# CORRECTO (el de "antes de 2015"), y no otro ValueError cualquiera.
# (En realidad match= es una expresión regular, un patrón de búsqueda,
# pero unas palabras normales como estas significan simplemente
# "contiene este texto".)
def test_parse_date_rejects_dates_before_2015():
    with pytest.raises(ValueError, match="older GH Archive format"):
        parse_date("2014-12-31")


# ---------- parse_hour and parse_count ----------

# CASOS LÍMITE: los dos extremos, 0 y 23, tienen que aceptarse; justo
# fuera de ellos (24, -1), y lo que no son números ("3pm", vacío), se
# rechazan. Los límites son donde aparecen los errores de uno (< en lugar
# de <=).
def test_parse_hour_valid_limits():
    assert parse_hour("0") == 0
    assert parse_hour("23") == 23


def test_parse_hour_rejects_out_of_range():
    for bad in ("24", "-1", "3pm", ""):
        with pytest.raises(ValueError):
            parse_hour(bad)


# Lo mismo para la cantidad: 1 y 168 (una semana, MAX_HOURS) se aceptan;
# 0, 169 y una palabra se rechazan.
def test_parse_count_limits():
    assert parse_count("1") == 1
    assert parse_count("168") == 168
    for bad in ("0", "169", "two"):
        with pytest.raises(ValueError):
            parse_count(bad)


# ---------- chosen_hours ----------

def test_chosen_hours_one_hour():
    assert chosen_hours(date(2026, 8, 27), 15, 1) == [utc(2026, 8, 27, 15)]


# Las 23:00 más una hora tienen que ser las 00:00 del día SIGUIENTE, no
# una hora 24.
def test_chosen_hours_cross_midnight():
    assert chosen_hours(date(2026, 8, 27), 23, 2) == [utc(2026, 8, 27, 23), utc(2026, 8, 28, 0)]


# ---------- hours_are_published ----------

# Tres casos alrededor de la regla, con NOW = 15:20 (final más tardío
# permitido: 14:00): las horas antiguas (agosto) están bien; las que
# terminan exactamente a las 14:00 están bien (el propio límite); las que
# terminan a las 15:00, o mañana, se rechazan.
# Los comentarios al final de algunas líneas son notas del propio
# original.
def test_old_hours_are_published():
    assert hours_are_published(chosen_hours(date(2026, 8, 27), 15, 3), NOW)


def test_hours_ending_one_hour_before_the_current_hour_are_published():
    # now 15:20 -> current hour 15:00; 12:00-14:00 is accepted
    assert hours_are_published(chosen_hours(date(2026, 11, 12), 12, 2), NOW)


def test_recent_or_future_hours_are_not_published():
    assert not hours_are_published(chosen_hours(date(2026, 11, 12), 13, 2), NOW)   # ends 15:00, too recent
    assert not hours_are_published(chosen_hours(date(2026, 11, 13), 0, 1), NOW)    # tomorrow


# ---------- database_name ----------

def test_database_name_one_hour_has_no_leading_zero_like_gh_archive():
    assert database_name(chosen_hours(date(2026, 8, 27), 5, 1)) == "gharchive-2026-08-27-5"


def test_database_name_several_hours_says_how_many():
    assert database_name(chosen_hours(date(2026, 8, 27), 15, 3)) == "gharchive-2026-08-27-15-3h"


# Los nombres nunca deben ser el de una de las otras dos bases de datos,
# ni contener "_" (Neo4j lo rechazaría). `not in (...)`: distinto de
# todos los elementos de la tupla. `"_" not in name`: con cadenas, `in`
# busca un texto.
def test_database_name_never_clashes_with_the_other_databases():
    for count in (1, 24):
        name = database_name(chosen_hours(date(2026, 8, 27), 15, count))
        assert name not in ("gharchive", "gharchive24h")
        assert "_" not in name   # Neo4j doesn't allow "_" in database names


# ---------- ask_hours ----------

# ---------------------------------------------------------------------
# capsys — fixture NUEVA ("capture system output", capturar la salida del
# sistema). Como caplog (ver test_extract_csv.py), pero para print(): todo
# lo que se imprime durante la prueba se captura en lugar de mostrarse.
# capsys.readouterr().out lo devuelve como una sola cadena, así que la
# prueba puede comprobar que los mensajes aparecieron de verdad.
#
# Esta prueba demuestra la regla "la fecha y la hora NO tienen valor por
# defecto": el teclado simulado pulsa Enter ("") en la fecha, luego en la
# hora, y ask_hours() tiene que volver a preguntar cada vez (imprimiendo
# "Please type ...") en lugar de elegir un valor. Cada línea de answers()
# es una ronda de preguntas; los comentarios dicen qué significa cada
# respuesta. Solo en la tercera ronda lo recibe todo, con Enter en la
# cantidad (= 1 hora) y Enter en la confirmación (= sí).
# ---------------------------------------------------------------------
def test_ask_hours_has_no_default_date_or_hour(capsys):
    # Pressing Enter at the date or the hour doesn't pick one: it asks again.
    reply = answers("",                      # no date
                    "2026-08-27", "",        # no hour
                    "2026-08-27", "15", "", "")   # Enter at the count = 1 hour; Enter to confirm
    assert ask_hours(NOW, ask=reply) == [utc(2026, 8, 27, 15)]
    printed = capsys.readouterr().out
    assert "Please type a date" in printed and "Please type an hour" in printed


# El caso normal: fecha, hora 9, 3 horas, "y" -> tres horas seguidas.
def test_ask_hours_chosen_date_hour_and_count():
    hours = ask_hours(NOW, ask=answers("2026-11-10", "9", "3", "y"))
    assert hours == [utc(2026, 11, 10, 9), utc(2026, 11, 10, 10), utc(2026, 11, 10, 11)]


# Todas las formas de responder mal, una ronda cada una, y al final una
# ronda correcta. La última comprobación recorre los cuatro mensajes
# esperados: cada uno tiene que aparecer en lo impreso, lo que demuestra
# que cada error se detectó y se explicó.
def test_ask_hours_asks_again_after_bad_answers(capsys):
    # a wrong date; a wrong hour; a wrong count; hours not published yet; then a good answer
    reply = answers("10/11/2026",
                    "2026-11-10", "25",
                    "2026-11-10", "9", "0",
                    "2026-11-12", "13", "2",
                    "2026-11-10", "9", "", "")
    assert ask_hours(NOW, ask=reply) == [utc(2026, 11, 10, 9)]
    printed = capsys.readouterr().out
    for message in ("isn't a date", "isn't an hour", "isn't a number of hours", "hasn't published"):
        assert message in printed


# Responder "n" a la confirmación devuelve None: no se hará nada.
# `is None` (no == None) es la forma habitual de comprobar si algo es
# None.
def test_ask_hours_no_means_nothing_is_done():
    assert ask_hours(NOW, ask=answers("2026-08-27", "15", "", "n")) is None


# ---------- may_be_emptied / recreate_databases (the safety check before deleting) ----------

# Los nombres que crea este script están permitidos...
def test_databases_made_by_this_script_may_be_emptied():
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 1)))
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 3)))


# ...y todas las demás bases de datos de los dos servidores se rechazan:
# el benchmark congelado, la del pipeline en vivo, la de los tests de
# integración y las que traen los propios servidores.
def test_the_other_databases_may_never_be_emptied():
    for name in ("gharchive", "gharchive24h", "gharchivetest", "neo4j", "postgres", "system"):
        assert not may_be_emptied(name)


# ---------------------------------------------------------------------
# La prueba más importante del archivo: recreate_databases("gharchive")
# tiene que lanzar "Refusing to empty" ANTES de conectarse a nada. Esta
# prueba se puede ejecutar sin ningún servidor de bases de datos y sin
# contraseña: si la comprobación fuera después de la conexión, la prueba
# fallaría con un error de conexión — así que, si pasa, demuestra que el
# orden es el correcto, y que este script no puede borrar el benchmark
# congelado.
# ---------------------------------------------------------------------
def test_recreate_refuses_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running and no password.
    with pytest.raises(ValueError, match="Refusing to empty"):
        recreate_databases("gharchive")
