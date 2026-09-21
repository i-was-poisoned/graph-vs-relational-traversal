########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/summarize_data.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive en
# docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script real y "limpio"
# (sin nada de este comentario) es scripts/summarize_data.py.
#
# Este archivo asume que ya has leído docs_spanish/download_gharchive.py y
# docs_spanish/peek_data.py — argparse, Path, las f-strings, las búsquedas
# en dict anidados, main() y la protección __name__ NO se vuelven a
# explicar desde cero aquí. Este archivo se centra en lo que es NUEVO en
# summarize_data.py: leer un archivo completo en lugar de un puñado de
# líneas, y contar/agregar con collections.Counter.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, and unique actor/repo counts — a first read on data volume and
connectivity before modeling the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
"""

# argparse, Path, json: ya explicados en docs_spanish/download_gharchive.py
# y docs_spanish/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter
#
# `collections` es un módulo de la biblioteca estándar con tipos de
# contenedor especializados, construidos sobre los dict/list/tuple
# integrados. `Counter` es una subclase de dict creada específicamente
# para contar cosas: cada clave vale 0 por defecto la primera vez que se
# toca, así que `counter[key] += 1` funciona incluso con una clave nunca
# vista antes — sin necesidad de escribir
#     if key not in counter:
#         counter[key] = 0
#     counter[key] += 1
# cada vez, como habría que hacer con un dict normal.
#
# Lo necesitamos tres veces en este script: para contar cuántos eventos
# hay de cada `type`, cuántos eventos produjo cada actor, y cuántos
# eventos recibió cada repo.
# ---------------------------------------------------------------------
from collections import Counter
from pathlib import Path

# La misma técnica de construcción de Path que DEFAULT_FILE en
# peek_data.py — ver la copia anotada de ese archivo para la explicación
# completa.
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# Cuántos actores/repos más activos mostrar si no se especifica --top. 5
# es suficiente para detectar patrones (p. ej. "las cuentas más activas
# son todas bots") sin saturar la terminal.
DEFAULT_TOP = 5


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# La misma forma de dos parámetros obligatorios que peek() (file_path,
# num_lines).
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    # Un simple int, incrementado una vez por línea. Más simple que
    # hacer len() sobre una lista con todos los eventos, y evita
    # mantener en memoria los más de 69.000 eventos solo para contarlos.
    total_events = 0

    # ---------------------------------------------------------------
    # Counter[str]: la anotación de tipo se lee como "un Counter cuyas
    # claves son cadenas" (los valores son siempre los conteos, es decir
    # int — Counter no necesita que se indique por separado).
    #
    # Tres contadores distintos, uno por cada cosa que se está contando:
    #   event_type_counts   clave = event["type"], p. ej. "PushEvent"
    #   actor_event_counts  clave = event["actor"]["login"], p. ej. "octocat"
    #   repo_event_counts   clave = event["repo"]["name"], p. ej. "octocat/Hello-World"
    # ---------------------------------------------------------------
    event_type_counts: Counter[str] = Counter()
    actor_event_counts: Counter[str] = Counter()
    repo_event_counts: Counter[str] = Counter()

    # ---------------------------------------------------------------
    # El mismo patrón `with open(..., "r", encoding="utf-8") as f:` que
    # peek() — ver la copia anotada de peek_data.py para entender por qué
    # el modo texto y el UTF-8 explícito son las decisiones correctas
    # aquí.
    #
    # La diferencia clave con peek(): aquí NO hay ningún `if i >=
    # num_lines: break`. peek() se detiene deliberadamente pronto porque
    # solo quiere un puñado de eventos de muestra; summarize() lee
    # deliberadamente cada línea, una por una, porque un conteo o
    # porcentaje calculado solo con los primeros cientos de eventos no
    # representaría el archivo completo.
    # ---------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # No hace falta enumerate() aquí — a diferencia de peek(),
        # summarize() nunca imprime un índice de línea, así que la
        # posición en el bucle no sirve para nada, solo importa el
        # evento ya analizado.
        for line in f:
            event = json.loads(line)
            total_events += 1

            # ---------------------------------------------------------
            # counter[key] += 1
            #
            # Aquí es donde Counter se paga frente a un dict normal: la
            # primera vez que se ve un determinado tipo de evento /
            # actor / repo, Counter trata silenciosamente la clave
            # ausente como 0, así que `+= 1` la lleva a 1. Cada
            # aparición posterior simplemente suma 1 a lo que ya tenía.
            # Al terminar el bucle, cada Counter contiene el conteo
            # completo de cada clave distinta que llegó a ver.
            # ---------------------------------------------------------
            event_type_counts[event["type"]] += 1
            actor_event_counts[event["actor"]["login"]] += 1
            repo_event_counts[event["repo"]["name"]] += 1

    print(f"Total events: {total_events}")

    # ---------------------------------------------------------------
    # len(actor_event_counts)
    #
    # Como Counter es una subclase de dict, len() sobre él devuelve el
    # número de claves DISTINTAS, no la suma de los conteos. Así que
    # esto es exactamente "cuántos actores/repos únicos aparecieron en
    # el archivo" — la suma de todos los valores volvería a dar
    # total_events, que no es lo que queremos aquí.
    # ---------------------------------------------------------------
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    # ---------------------------------------------------------------
    # .most_common()
    #
    # Un método que solo tiene Counter (los dict normales no lo tienen).
    # Llamado sin argumentos, devuelve CADA par (clave, conteo) como una
    # lista de tuplas, ordenada de más frecuente a menos frecuente —
    # exactamente el orden que se quiere para detectar de un vistazo "qué
    # domina este conjunto de datos". Llamado como .most_common(n)
    # (usado más abajo para actores/repos), devuelve solo los n primeros
    # pares, lo cual es más eficiente que ordenarlo todo y luego recortar
    # cuando solo se necesitan unos pocos resultados.
    # ---------------------------------------------------------------
    for event_type, count in event_type_counts.most_common():
        pct = 100 * count / total_events

        # ---------------------------------------------------------------
        # f"{event_type:<25} {count:>7} ({pct:5.1f}%)"
        #
        # La parte después de los dos puntos dentro de {} es una
        # ESPECIFICACIÓN DE FORMATO — controla cómo se rellena/alinea el
        # valor al convertirlo a texto, no solo cuál es el valor.
        #   <25   alineado a la izquierda, rellenado con espacios hasta
        #         al menos 25 caracteres de ancho. Se usa para
        #         event_type para que los números que siguen queden
        #         alineados en columna sin importar la longitud del
        #         nombre del tipo de evento.
        #   >7    alineado a la derecha, rellenado hasta al menos 7
        #         caracteres de ancho. Se usa para count para que los
        #         dígitos se alineen por su borde derecho, tal como se
        #         alinean convencionalmente los números en una tabla.
        #   5.1f  un float de PUNTO FIJO, de al menos 5 caracteres de
        #         ancho en total, con exactamente 1 dígito después del
        #         punto decimal (p. ej. " 95.3" o "  0.1"). Se usa para
        #         el porcentaje para que cada fila muestre el mismo
        #         número de decimales.
        # Nada de esto cambia el valor subyacente — solo cómo se
        # representa como texto.
        # ---------------------------------------------------------------
        print(f"  {event_type:<25} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")


# ---------------------------------------------------------------------
# parse_args(): mismo esquema general que la versión de peek_data.py. Lo
# único destacable es que --top cumple el mismo papel que cumplía --lines
# allí (un simple entero positivo, sin restricción `choices=`) — solo que
# aplicado a "cuántos actores/repos más activos mostrar" en lugar de
# "cuántos eventos de muestra imprimir".
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    return parser.parse_args()


# main() y la protección `if __name__ == "__main__":`: propósito y
# mecánica idénticos a los otros dos scripts — ver la copia anotada de
# download_gharchive.py para la explicación completa.
def main() -> None:
    args = parse_args()
    summarize(args.file, args.top)


if __name__ == "__main__":
    main()
