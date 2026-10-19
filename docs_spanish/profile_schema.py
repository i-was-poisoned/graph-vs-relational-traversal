########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/profile_schema.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive en
# docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script real y "limpio"
# (sin nada de este comentario) es scripts/profile_schema.py.
#
# Este archivo asume que ya has leído docs_spanish/download_gharchive.py,
# docs_spanish/peek_data.py, y docs_spanish/summarize_data.py — argparse,
# Path, las f-strings, las búsquedas en dict anidados, Counter,
# .most_common(), main(), y la protección __name__ NO se vuelven a
# explicar desde cero aquí. Este archivo se centra en lo que es NUEVO en
# profile_schema.py: la RECURSIÓN — una función que se llama a sí misma
# para buscar en una estructura anidada de forma arbitraria y desconocida.
########################################################################

"""Profile the payload shape of a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, per event type, which `payload`
fields appear, how often, and what Python type they hold, plus any nested
"actor-like" references (dicts with a 'login' key, e.g. a PR's author or
reviewer, distinct from the event's top-level actor) found anywhere inside
the payload. This is ground truth for hand-designing the relational/graph
schema later, since payload shape varies a lot between event types (e.g.
PushEvent vs. PullRequestEvent), and multi-actor connectivity (needed for
an actor-repo-actor traversal) mostly lives in these nested references.

Usage:
    python scripts/profile_schema.py
    python scripts/profile_schema.py --file data/2026-08-27-15.json
    python scripts/profile_schema.py --type PushEvent
"""

# argparse, json, Counter, Path: ya explicados en las tres copias
# anotadas anteriores.
import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# ---------------------------------------------------------------------
# POR QUÉ existe un límite de profundidad
#
# find_actor_refs() (más abajo) es RECURSIVA: se llama a sí misma sobre
# lo que sea que encuentre anidado dentro de un dict o una list, y los
# datos JSON pueden anidarse arbitrariamente (un dict dentro de una list
# dentro de un dict dentro de una list...). Sin algún límite, una
# estructura suficientemente profunda o inesperadamente
# autorreferencial podría hacer que la función recurra
# indefinidamente, hasta fallar con un RecursionError. En la práctica,
# los payloads de GH Archive solo tienen unos pocos niveles de
# profundidad, pero MAX_SEARCH_DEPTH es una red de seguridad barata de
# todos modos, y también limita el trabajo desperdiciado buscando donde
# de todas formas no aparecería razonablemente una referencia a un
# actor.
# ---------------------------------------------------------------------
MAX_SEARCH_DEPTH = 3


# ---------------------------------------------------------------------
# ¿QUÉ ES LA RECURSIVIDAD? (una función que se llama a sí misma)
#
# find_actor_refs(), aquí abajo, llama a find_actor_refs() dentro de su
# propio cuerpo. Eso se llama RECURSIVIDAD (o recursión), y una función
# que lo hace es RECURSIVA. (No es "anidar" una función: anidar
# significa DEFINIR una función dentro de otra. Aquí solo hay una
# función, que simplemente SE LLAMA a sí misma.)
#
# Por qué se puede hacer: cada vez que se llama a una función, Python
# crea una copia nueva y separada de sus parámetros y variables para
# esa llamada. Así que cuando find_actor_refs() vuelve a llamar a
# find_actor_refs(), la nueva llamada tiene su propio `value`, su propio
# `path` y su propio `depth`, y no pisa los de la primera. La primera
# llamada simplemente espera, en pausa, hasta que la de dentro le
# devuelve su respuesta, y luego sigue donde lo había dejado.
#
# Una analogía: las muñecas rusas (matrioskas). Para encontrar una nota
# escondida en algún lugar de un juego de muñecas, las instrucciones
# son las mismas en cada nivel:
#   "Abre la muñeca. Si la nota está aquí, cógela. Si no, a cada muñeca
#    que encuentres dentro, aplícale ESTAS MISMAS INSTRUCCIONES."
# Las instrucciones se refieren a sí mismas: eso es la recursividad.
#
# Por qué la necesitamos AQUÍ: un payload es un diccionario que puede
# contener diccionarios, que pueden contener listas de diccionarios, y
# así sucesivamente, y no sabemos de antemano cuántos niveles tiene. Un
# bucle `for` normal solo mira UN nivel. Para mirar todos los niveles,
# sin saber cuántos hay, la función se ocupa de un nivel y se pide a sí
# misma que se ocupe del siguiente.
#
# Las dos reglas que necesita toda función recursiva:
#   1. Un CASO BASE: una situación en la que responde SIN llamarse a sí
#      misma (aquí: ha encontrado un usuario, ha llegado a un valor
#      simple como un texto, o se ha quedado sin profundidad). Sin él,
#      se llamaría a sí misma para siempre.
#   2. Cada llamada a sí misma tiene que ACERCARSE a un caso base (aquí:
#      cada llamada baja un nivel más en los datos, con depth - 1).
#
# Paso a paso, con un payload pequeño:
#
#     payload = {"action": "created",
#                "issue": {"user": {"login": "luis"}}}
#
#   llamada 1: find_actor_refs(payload, "payload", 3)
#              un dict sin "login" -> mira cada uno de sus valores:
#     llamada 2: find_actor_refs("created", "payload.action", 2)
#                un texto -> no hay nada dentro -> devuelve []
#     llamada 3: find_actor_refs({"user": {...}}, "payload.issue", 2)
#                un dict sin "login" -> mira cada uno de sus valores:
#       llamada 4: find_actor_refs({"login": "luis"}, "payload.issue.user", 1)
#                  un dict CON "login" -> devuelve ["payload.issue.user"]
#                la llamada 3 lo recoge y devuelve ["payload.issue.user"]
#   la llamada 1 junta [] + ["payload.issue.user"] y devuelve
#   ["payload.issue.user"]
#
# Cada llamada solo se ocupa de UN nivel; las respuestas van subiendo,
# de llamada en llamada, hasta que la primera tiene la lista completa.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
#
# `value: object` — el tipo declarado del parámetro es `object`, el
# tipo más general en Python (todo es un `object`). Esto es
# deliberado: esta función recibe fragmentos de JSON ya analizado, que
# pueden ser un dict, una list, un str, un int, un bool, o None según
# en qué parte de la estructura se encuentre en ese momento — no hay un
# tipo más específico único que cubra todos esos casos, así que
# `object` es la anotación de tipo honesta aquí.
#
# `path: str` — un rastro legible de cómo se llegó hasta aquí, p. ej.
# "payload.pull_request.user". Se construye un `.atributo` a la vez a
# medida que la función recurre más profundo, únicamente para el
# reporte impreso final — no juega ningún papel en la lógica de
# búsqueda en sí.
#
# `depth: int` — cuántos niveles más puede recurrir esta llamada antes
# de rendirse. Cada llamada recursiva pasa `depth - 1`, contando hacia
# atrás hasta el límite de profundidad explicado arriba.
#
# `-> list[str]` — esta función siempre devuelve una lista de cadenas
# de ruta (posiblemente vacía), sin importar cuál de las ramas de abajo
# se ejecute realmente.
# ---------------------------------------------------------------------
def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    # ---------------------------------------------------------------
    # EL CASO BASE
    #
    # Toda función recursiva necesita al menos una condición que
    # detenga la recursión por completo, sin hacer ninguna llamada
    # recursiva adicional — de lo contrario sí recurriría
    # indefinidamente. Aquí, una vez que se ha bajado más profundo de
    # lo que permite MAX_SEARCH_DEPTH, se devuelve inmediatamente una
    # lista vacía (no se encontró nada) en lugar de seguir buscando.
    # ---------------------------------------------------------------
    if depth < 0:
        return []

    # ---------------------------------------------------------------
    # isinstance(value, dict)
    #
    # Comprueba si `value` es (una instancia) del tipo dict. Así es
    # como la función distingue los tres casos que le interesan, ya
    # que el tipo real de `value` varía de una llamada a otra (ver la
    # nota sobre `object` arriba): ¿es un dict en el que hay que mirar
    # dentro, una list en la que hay que mirar dentro, o alguna otra
    # cosa (un str/int/bool/None) sin nada más que buscar?
    # ---------------------------------------------------------------
    if isinstance(value, dict):
        # ---------------------------------------------------------------
        # value.get("login")
        #
        # `.get(key)` es una búsqueda en un dict que devuelve None en
        # lugar de lanzar un error cuando falta la clave — a
        # diferencia de value["login"], que fallaría con un KeyError en
        # cualquier dict que no tenga una clave "login" (la mayoría de
        # ellos, aquí). Esta es la herramienta correcta siempre que la
        # ausencia de una clave sea una posibilidad normal y esperada,
        # no un error.
        #
        # isinstance(..., str) sobre el resultado comprueba entonces que
        # el valor de login es realmente una cadena (un nombre de
        # usuario real) y no, por ejemplo, None proveniente de una
        # clave ausente, u otro tipo que no reconoceríamos como un
        # nombre de usuario.
        #
        # gh-archive-guide.md documenta que toda referencia a un
        # usuario de GitHub (el campo `actor` de nivel superior del
        # evento, pero también autores de PR, revisores, autores de
        # comentarios, etc.) tiene la forma
        # {"id": ..., "login": "some-user"}. Entonces: "¿tiene este
        # dict un campo 'login' de tipo cadena?" es una prueba
        # razonable y general para "¿es este dict una referencia a un
        # usuario de GitHub?" — sin necesidad de codificar cada posible
        # nombre de campo (user/author/assignee/reviewer/owner/...)
        # bajo el que podría almacenarse una referencia de usuario.
        # ---------------------------------------------------------------
        if isinstance(value.get("login"), str):
            # Se encontró una. Se devuelve de inmediato — un dict que
            # parece una referencia de usuario es una "hoja" para
            # nuestros propósitos; no tiene sentido seguir recurriendo
            # DENTRO de un objeto de usuario buscando aún más usuarios
            # anidados.
            return [path]

        # ---------------------------------------------------------------
        # Este dict en sí no era una referencia de usuario, así que se
        # explora cada uno de sus valores en su lugar, por si ALGUNO DE
        # ELLOS lo fuera (o lo contuviera).
        #
        # `refs = []` y luego `refs.extend(...)` dentro de un bucle, en
        # lugar de `return find_actor_refs(...)` directamente dentro del
        # bucle: un dict puede tener muchas claves, y una referencia de
        # actor podría esconderse bajo más de una de ellas (p. ej.
        # "assignee" Y "assignees" en el mismo payload) — así que hay
        # que comprobar cada clave y combinar todos sus resultados, no
        # solo devolver la primera coincidencia encontrada.
        #
        # `f"{path}.{key}"` extiende el rastro con el nombre de esta
        # clave antes de recurrir sobre su valor — así que si se
        # encuentra una coincidencia tres niveles más abajo, la ruta
        # devuelta registra todo el trayecto hasta allí, no solo el
        # último paso.
        #
        # `depth - 1` — un nivel más profundo, un margen menos
        # disponible.
        # ---------------------------------------------------------------
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    # ---------------------------------------------------------------
    # isinstance(value, list)
    #
    # Las list aparecen aquí para campos como "assignees" (una lista de
    # dict de usuario) o "requested_reviewers". Nótese que la ruta NO
    # se extiende con un índice (sin ".0", ".1", ...) al recurrir sobre
    # los elementos de una list — cada elemento de, digamos,
    # "assignees" es conceptualmente el mismo tipo de cosa (un
    # asignado), así que se reportan bajo una única ruta compartida en
    # lugar de como rutas numeradas separadas.
    # ---------------------------------------------------------------
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    # ---------------------------------------------------------------
    # Cualquier otra cosa (str, int, float, bool, None, ...) no tiene
    # nada dentro que explorar — es el otro caso base, alcanzado una
    # vez que la recursión ha llegado a un valor simple en lugar de un
    # contenedor.
    # ---------------------------------------------------------------
    return []


def profile(file_path: Path, type_filter: str | None) -> None:
    event_type_totals: Counter[str] = Counter()
    # Para cada tipo de evento, para cada nombre de campo de payload, un
    # Counter de cuántas veces se vio cada tipo de Python (dict/list/
    # str/int/bool/NoneType) en ese campo. La misma idea de Counter
    # anidado que summarize_data.py, solo con un nivel de clave
    # adicional (tipo de evento -> nombre de campo -> nombre de tipo).
    payload_field_types: dict[str, dict[str, Counter[str]]] = {}
    # Para cada tipo de evento, un Counter de cuántos eventos contenían
    # una referencia de tipo actor en cada ruta anidada (p. ej.
    # "payload.pull_request.user").
    actor_ref_counts: dict[str, Counter[str]] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            event_type = event["type"]

            # ---------------------------------------------------------
            # --type permite centrar el reporte (potencialmente largo)
            # en un solo tipo de evento a la vez. `continue` salta el
            # resto de ESTA iteración del bucle y pasa directamente a
            # la siguiente línea, sin tocar ninguno de los contadores
            # de abajo — así que los eventos filtrados no contribuyen
            # en nada a los totales ni a los reportes.
            # ---------------------------------------------------------
            if type_filter is not None and event_type != type_filter:
                continue

            event_type_totals[event_type] += 1
            fields = payload_field_types.setdefault(event_type, {})
            payload = event.get("payload", {})

            for key, value in payload.items():
                type_counts = fields.setdefault(key, Counter())
                type_counts[type(value).__name__] += 1

            # ---------------------------------------------------------
            # set(find_actor_refs(...))
            #
            # find_actor_refs puede devolver la MISMA ruta más de una
            # vez para un solo evento — p. ej. tres revisores
            # solicitados bajo "payload.requested_reviewers" volverían
            # como esa ruta tres veces, una por cada revisor. Envolver
            # el resultado en set(...) elimina los duplicados, lo cual
            # coincide con cómo funcionan los contadores de tipo de
            # campo de arriba: contar cuántos EVENTOS tienen una
            # referencia en esa ruta, no cuántas referencias existen en
            # total.
            # ---------------------------------------------------------
            ref_paths = set(find_actor_refs(payload, "payload", MAX_SEARCH_DEPTH))
            ref_counts = actor_ref_counts.setdefault(event_type, Counter())
            for ref_path in ref_paths:
                ref_counts[ref_path] += 1

    # ---------------------------------------------------------------
    # Cómo leer la salida
    #
    # Un ejemplo real de la hora fija de este proyecto:
    #
    #   IssueCommentEvent (194 events)
    #     payload.action               present in 100.0% (194/194) - types: str x194
    #     payload.issue                present in 100.0% (194/194) - types: dict x194
    #     payload.comment              present in 100.0% (194/194) - types: dict x194
    #     actor references (nested 'login' fields):
    #       payload.issue.user                  present in 100.0% (194/194)
    #       payload.comment.user                present in 100.0% (194/194)
    #
    # - Línea 1: el tipo de evento, y cuántos eventos de ese tipo
    #   contiene el archivo.
    # - Cada línea de payload: el nombre del campo, y luego "present
    #   in X%" — en cuántos de ESOS eventos existe el campo. 100 %
    #   significa que siempre está (fiable); un % bajo significa que
    #   solo a veces, así que sería una columna opcional/nullable.
    #   "types" dice qué tipo de valor tenía (str, int, dict, list,
    #   NoneType) y cuántas veces. NoneType significa que el campo a
    #   veces está vacío — p. ej. la description de CreateEvent es
    #   None en 633 de 1290 eventos.
    # - "actor references": rutas a objetos de usuario anidados
    #   (cualquier cosa con un "login"), y en qué % de los eventos
    #   aparece cada una.
    #
    # IMPORTANTE: esto solo comprueba que un objeto de usuario EXISTE
    # en esa ruta, no QUIÉN es. payload.comment.user es quien
    # comenta — es decir, el propio actor (el 100 % de las veces).
    # payload.issue.user es el autor de la issue, una persona
    # distinta en el 66 % de los casos. Consulta project-notes.md
    # ("Etapa de diseño del esquema") para la comparación con el
    # actor del evento.
    # ---------------------------------------------------------------
    for event_type, total in event_type_totals.most_common():
        print(f"{event_type} ({total} events)")
        fields = payload_field_types[event_type]
        if not fields:
            print("  (empty payload)")
        for field_name, type_counts in fields.items():
            presence = sum(type_counts.values())
            pct = 100 * presence / total
            types = ", ".join(f"{t} x{c}" for t, c in type_counts.most_common())
            print(f"  payload.{field_name:<20} present in {pct:5.1f}% ({presence}/{total}) - types: {types}")

        print("  actor references (nested 'login' fields):")
        refs = actor_ref_counts[event_type]
        if not refs:
            print("    (none found)")
        for ref_path, count in refs.most_common():
            pct = 100 * count / total
            print(f"    {ref_path:<35} present in {pct:5.1f}% ({count}/{total})")
        print()


# parse_args(): mismo esquema general que los otros tres scripts —
# --file y --type siguen el mismo estilo que --file/--lines en
# peek_data.py y --file/--top en summarize_data.py.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--type", type=str, default=None,
                         help="Only profile this event type (default: all types)")
    return parser.parse_args()


# main() y la protección `if __name__ == "__main__":`: propósito y
# mecánica idénticos a los otros tres scripts.
def main() -> None:
    args = parse_args()
    profile(args.file, args.type)


if __name__ == "__main__":
    main()
