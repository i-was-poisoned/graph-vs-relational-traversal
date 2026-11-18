########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_pipeline.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar, no ejecutarse (pytest solo busca pruebas en
# tests/, como indica pytest.ini). El archivo real y "limpio" (sin nada de
# este comentario) es tests/test_pipeline.py.
#
# Lee primero docs_spanish/test_extract_csv.py: lo básico de pytest (los
# nombres test_, assert, cómo ejecutar las pruebas) se explica allí y NO
# se repite aquí. Este archivo se centra en lo que es NUEVO: construir
# fechas UTC con datetime, compararlas, timedelta, y zip() para recorrer
# parejas de vecinos en una lista. NOVEDADES DE ESTA VERSIÓN: tres pruebas
# para already_ran_today(), la comprobación de "una vez al día" del modo
# --scheduled, usando `date` (un día sin hora) y `assert not`.
#
# Su papel en el proyecto: comprobar las funciones puras de pipeline.py —
# las que deciden QUÉ horas descarga el pipeline en vivo, CÓMO se llaman
# sus archivos, y SI la tarea programada todavía tiene que ejecutarse
# hoy. Si alguna estuviera mal, el pipeline cargaría la ventana
# equivocada, pediría a GH Archive archivos que no existen, o se
# ejecutaría varias veces al día (o nunca).
#
# Cómo ejecutar las pruebas reales (desde la carpeta del proyecto):
#     python -m pytest
########################################################################

"""Unit tests for the pure functions of scripts/pipeline.py (no network, no databases).

Run with:  python -m pytest
"""

# date: un DÍA del calendario, sin hora, p. ej. date(2026, 11, 12). NUEVO
#   aquí, para las pruebas de already_ran_today() del final.
# datetime: una fecha Y una hora en un solo objeto, p. ej. 2026-10-22 11:15.
# timedelta: una DURACIÓN, p. ej. "1 hora". Restar dos datetime da un
#   timedelta; sumar un timedelta a un datetime da otro datetime.
# timezone: timezone.utc marca un datetime como UTC. GH Archive nombra sus
#   archivos en UTC, así que el pipeline (y estas pruebas) trabajan
#   siempre en UTC.
from datetime import date, datetime, timedelta, timezone

# Las tres funciones que se prueban. "Pura" significa: misma entrada ->
# misma salida, sin archivos, red ni reloj de por medio. Eso es lo que las
# hace tan fáciles de probar — les damos un "ahora" fijo (o un "hoy" fijo)
# en lugar de la hora real.
from pipeline import already_ran_today, compute_window, hour_file_name


# ---------------------------------------------------------------------
# Una pequeña función auxiliar (NO es una prueba: su nombre no empieza
# por test_, así que pytest no la ejecuta por sí sola). Solo ahorra
# escribir: en lugar de
#     datetime(2026, 10, 22, 11, 15, tzinfo=timezone.utc)
# las pruebas escriben
#     utc(2026, 10, 22, 11, 15)
# `minute: int = 0` es un valor por defecto: si lo omites, vale 0, así
# que utc(2026, 10, 20, 11) significa las 11:00 en punto.
# ---------------------------------------------------------------------
def utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------- compute_window ----------

# El ejemplo que se usa en el README y en las notas del proyecto,
# convertido en una prueba: si alguna vez falla, o el código o la
# documentación está mal.
def test_compute_window_readme_example():
    # At 2026-10-22 11:15 UTC the window is 2026-10-20 11:00 -> 2026-10-21 11:00:
    # 24 hour files, the first starting at 11:00 and the last at 10:00 the next day.
    # `window_hours=24, lag_hours=24`: argumentos con nombre
    # (nombre=valor). Hacen la llamada fácil de leer: se ve qué 24 es cuál.
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # Tres comprobaciones: cuántas horas hay, la primera y la última.
    # hours[-1]: un índice negativo cuenta desde el final, así que -1 es
    # el último elemento.
    # ¿Por qué la última hora EMPIEZA a las 10:00? Cada elemento es el
    # inicio de un archivo de una hora: el archivo que empieza a las 10:00
    # cubre de 10:00 a 11:00, así que la ventana termina a las 11:00.
    assert len(hours) == 24
    assert hours[0] == utc(2026, 10, 20, 11)
    assert hours[-1] == utc(2026, 10, 21, 10)


def test_compute_window_hours_are_consecutive():
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # zip(hours, hours[1:]) recorre los VECINOS de dos en dos:
    #   hours      = [h0, h1, h2, ..., h23]
    #   hours[1:]  = [h1, h2, h3, ..., h23]      (la misma lista, sin el primer elemento)
    #   zip(...)   -> (h0, h1), (h1, h2), ..., (h22, h23)
    # zip se para cuando se acaba la lista más corta, así que hay 23
    # parejas. En cada pareja, la hora posterior tiene que ir exactamente
    # 1 hora después de la anterior: ni huecos, ni repeticiones, ni nada
    # fuera de orden.
    for earlier, later in zip(hours, hours[1:]):
        assert later - earlier == timedelta(hours=1)


def test_compute_window_exactly_on_the_hour():
    # 12:00:00 sharp, 6-hour window, 2-hour lag -> ends at 10:00, so hours 04:00 ... 09:00.
    # Números distintos de los 24/24 por defecto, a propósito: la función
    # tiene que funcionar con cualquier ventana y retraso, no solo con los
    # que usamos normalmente.
    hours = compute_window(utc(2026, 10, 22, 12), window_hours=6, lag_hours=2)
    # La lista esperada se construye con una lista por comprensión:
    # range(4, 10) da 4, 5, 6, 7, 8, 9 (el 10 NO entra), así que esto es
    # [utc(..., 4), utc(..., 5), ..., utc(..., 9)]. Comparar la lista
    # entera con == comprueba todos los elementos Y su orden de una vez.
    assert hours == [utc(2026, 10, 22, h) for h in range(4, 10)]


# ---------- hour_file_name ----------

def test_hour_file_name_has_no_leading_zero():
    # GH Archive writes "-5", not "-05": a wrong name would mean a 404 on every early hour.
    # (Las notas del proyecto muestran lo que imprime pytest cuando esta
    # comprobación falla.)
    assert hour_file_name(utc(2026, 10, 20, 5)) == "2026-10-20-5.json.gz"


# Dos casos límite más para la misma regla: una hora de dos cifras (tiene
# que quedarse en "23") y la medianoche (tiene que ser "0", ni "00" ni un
# texto vacío).
def test_hour_file_name_two_digit_hour():
    assert hour_file_name(utc(2026, 10, 20, 23)) == "2026-10-20-23.json.gz"


def test_hour_file_name_midnight():
    assert hour_file_name(utc(2026, 10, 21, 0)) == "2026-10-21-0.json.gz"


# ---------------------------------------------------------------------
# already_ran_today(last_success, today) — ver docs_spanish/pipeline.py.
# Recibe el TEXTO de last_success_date.txt (o None si ese archivo no
# existe) y la fecha de hoy, y dice si la ejecución de hoy ya ha salido
# bien. Como los dos son parámetros, las pruebas no necesitan ningún
# archivo ni el reloj real: pasan un texto preparado y una fecha fija.
#
# Las tres situaciones que se puede encontrar la tarea programada:
#   nunca se ha ejecutado         (sin archivo: None)   -> debe ejecutarse
#   ya ha salido bien hoy         (el archivo dice hoy) -> NO debe volver
#                                                          a ejecutarse
#   el último éxito fue ayer      (el archivo dice ayer) -> debe ejecutarse
#
# `assert not X` afirma que X es False. Es la forma de comprobar que una
# función responde "no".
#
# Los textos terminan en "\n" a propósito: así es como pipeline.py
# escribe el archivo, de modo que las pruebas también demuestran que el
# final de línea no confunde a la comparación (already_ran_today() lo
# quita).
# ---------------------------------------------------------------------

# ---------- already_ran_today (--scheduled: once a day) ----------

def test_never_ran_before():
    assert not already_ran_today(None, date(2026, 11, 12))


def test_already_ran_today():
    assert already_ran_today("2026-11-12\n", date(2026, 11, 12))


def test_ran_yesterday_so_runs_again_today():
    assert not already_ran_today("2026-11-11\n", date(2026, 11, 12))
