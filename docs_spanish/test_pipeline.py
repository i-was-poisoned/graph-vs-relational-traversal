########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de tests/test_pipeline.py.
# NO está pensado para ejecutarse — vive en docs_spanish/ porque su
# propósito es enseñar. El archivo real y "limpio" (sin nada de este
# comentario) es tests/test_pipeline.py, y es ese el que ejecuta pytest.
#
# Este archivo asume que ya has leído docs_spanish/test_extract_csv.py
# (qué es una prueba de pytest, los nombres test_, `assert`) y
# docs_spanish/pipeline.py (qué hacen compute_window y hour_file_name).
# Aquí lo nuevo es trabajar con fechas: datetime, timezone y timedelta.
#
# Solo se prueban las dos funciones "puras" de pipeline.py: reciben unos
# valores y devuelven un resultado, sin tocar internet, archivos ni bases
# de datos. Las demás necesitan el mundo exterior y se prueban de otra
# manera (ver project-notes.md, "Qué funciones probar y cuáles no").
########################################################################

"""Unit tests for the pure functions of scripts/pipeline.py (no network, no databases).

Run with:  python -m pytest
"""

# datetime: un momento concreto (fecha y hora). timedelta: una DURACIÓN
# (por ejemplo, "1 hora"); restar dos datetime da un timedelta. timezone:
# para decir que una hora está en UTC, como las de GH Archive.
from datetime import datetime, timedelta, timezone

# Como en test_extract_csv.py: pytest.ini añade scripts/ a la búsqueda de
# módulos, así que "pipeline" se encuentra. Importar pipeline.py no
# ejecuta la pipeline: solo define sus funciones (la ejecución está
# protegida por `if __name__ == "__main__":`).
from pipeline import compute_window, hour_file_name


# Función auxiliar (no es una prueba: no empieza por test_). Escribir
# `datetime(2026, 10, 22, 11, 15, tzinfo=timezone.utc)` en cada prueba
# sería largo; con esto basta `utc(2026, 10, 22, 11, 15)`. Los minutos
# son opcionales (por defecto, 0).
def utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------- compute_window ----------

def test_compute_window_readme_example():
    # At 2026-10-22 11:15 UTC the window is 2026-10-20 11:00 -> 2026-10-21 11:00:
    # 24 hour files, the first starting at 11:00 and the last at 10:00 the next day.
    #
    # `window_hours=24, lag_hours=24`: argumentos con nombre. Hacen la
    # llamada más fácil de leer que `compute_window(..., 24, 24)`.
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # len(): cuántas horas tiene la lista.
    assert len(hours) == 24
    # hours[0] es la primera; hours[-1], la ÚLTIMA (los índices negativos
    # cuentan desde el final).
    assert hours[0] == utc(2026, 10, 20, 11)
    assert hours[-1] == utc(2026, 10, 21, 10)


def test_compute_window_hours_are_consecutive():
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    # zip(hours, hours[1:]) forma PAREJAS de horas vecinas. hours[1:] es la
    # misma lista sin la primera hora, así que zip junta la 1.ª con la
    # 2.ª, la 2.ª con la 3.ª, y así hasta el final. Con 3 horas sería:
    #     zip([h0, h1, h2], [h1, h2])  ->  (h0, h1), (h1, h2)
    for earlier, later in zip(hours, hours[1:]):
        # Entre cada pareja tiene que haber exactamente una hora: ni huecos
        # (una hora que faltaría descargar) ni repeticiones.
        assert later - earlier == timedelta(hours=1)


def test_compute_window_exactly_on_the_hour():
    # 12:00:00 sharp, 6-hour window, 2-hour lag -> ends at 10:00, so hours 04:00 ... 09:00.
    # Otro tamaño de ventana y otro retraso, para comprobar que la función
    # no funciona "solo" con los valores por defecto (24 y 24).
    hours = compute_window(utc(2026, 10, 22, 12), window_hours=6, lag_hours=2)
    # Lista por comprensión: la lista esperada se construye con un bucle
    # en una línea. range(4, 10) da 4, 5, 6, 7, 8, 9 (el 10 NO entra).
    assert hours == [utc(2026, 10, 22, h) for h in range(4, 10)]


# ---------- hour_file_name ----------

def test_hour_file_name_has_no_leading_zero():
    # GH Archive writes "-5", not "-05": a wrong name would mean a 404 on every early hour.
    # `==` entre textos: tienen que ser idénticos, carácter a carácter.
    assert hour_file_name(utc(2026, 10, 20, 5)) == "2026-10-20-5.json.gz"


def test_hour_file_name_two_digit_hour():
    assert hour_file_name(utc(2026, 10, 20, 23)) == "2026-10-20-23.json.gz"


def test_hour_file_name_midnight():
    # La medianoche es la hora 0: "-0", ni vacío ni "-00".
    assert hour_file_name(utc(2026, 10, 21, 0)) == "2026-10-21-0.json.gz"
