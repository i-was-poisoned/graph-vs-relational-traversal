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
# líneas, contar/agregar con collections.Counter, registrar los
# compañeros DISTINTOS con conjuntos (set) y collections.defaultdict,
# agrupar todos esos conteos en una CLASE para poder hacer el mismo
# análisis dos veces (con y sin bots), y medir lo conectados que están
# los actores y los repos entre sí.
#
# La salida tiene tres secciones:
#   1. GENERAL                 totales, separados en bots y no bots
#   2. ANALYSIS WITH BOTS      todos los eventos
#   3. ANALYSIS WITHOUT BOTS   el mismo análisis, sin los eventos de bots
# Las secciones 2 y 3 imprimen exactamente lo mismo, así que se pueden
# comparar una al lado de la otra.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, in three sections: general totals
(split into bot and non-bot), then the same analysis twice — with bots and
without bots — covering the event type breakdown, the most active actors and
repos, and how connected actors and repos are to each other. A first read on
data volume and connectivity before modeling the data relationally or as a
graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
"""

# argparse, Path, json: ya explicados en docs_spanish/download_gharchive.py
# y docs_spanish/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter, defaultdict
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
# Lo necesitamos tres veces en cada análisis: para contar cuántos
# eventos hay de cada `type`, cuántos eventos produjo cada actor, y
# cuántos eventos recibió cada repo.
#
# `defaultdict` es la misma idea, pero generalizada: un diccionario en el
# que una clave que no existe se crea automáticamente con el valor
# inicial que tú elijas. Aquí usamos defaultdict(set), así que una clave
# nueva empieza como un CONJUNTO VACÍO (ver actor_repos / repo_actors en
# la clase Stats para entender por qué necesitamos conjuntos).
# ---------------------------------------------------------------------
from collections import Counter, defaultdict
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
# BOT_SUFFIX = "[bot]"
#
# En GitHub, las cuentas automáticas creadas como "GitHub Apps" siempre
# tienen un login que termina en "[bot]" (github-actions[bot],
# dependabot[bot], ...). Ese sufijo es la forma más sencilla y fiable de
# reconocerlas. NO es un filtro perfecto: algunas cuentas automáticas no
# lo usan (p. ej. el login "Copilot"), así que el análisis "sin bots"
# elimina los bots oficiales, no todas las cuentas automáticas.
# ---------------------------------------------------------------------
BOT_SUFFIX = "[bot]"


# ---------------------------------------------------------------------
# def is_bot(login: str) -> bool:
#
# Una función auxiliar diminuta que responde a una sola pregunta de sí o
# no. `-> bool` significa que devuelve True o False. str.endswith()
# comprueba si el texto termina con el sufijo indicado:
# "dependabot[bot]".endswith("[bot]") es True,
# "octocat".endswith("[bot]") es False. Ponerlo en su propia función le
# da un nombre a la regla, así que si algún día cambia la definición de
# "bot", solo hay que cambiarla aquí.
# ---------------------------------------------------------------------
def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# ---------------------------------------------------------------------
# class Stats:
#
# Queremos hacer el MISMO análisis dos veces: una con todos los eventos,
# y otra solo con los eventos que no son de bots. Para eso hacen falta
# dos juegos de contadores completos y separados. En lugar de crear seis
# contadores con nombres "_all" y otros seis con nombres "_non_bot",
# definimos una CLASE: una plantilla que dice "un objeto Stats guarda
# estos seis contadores y sabe cómo añadirles un evento". Después
# creamos dos objetos a partir de la misma plantilla:
#
#     all_events = Stats()     # un juego completo de contadores
#     non_bot = Stats()        # otro juego, totalmente independiente
#
# Piensa en la clase como un formulario en blanco, y en cada objeto como
# una copia rellenada de ese formulario.
#
# La línea """...""" debajo de `class Stats:` es un DOCSTRING — el mismo
# tipo de descripción que el que hay al principio de este archivo, pero
# para la clase.
# ---------------------------------------------------------------------
class Stats:
    """All the counts for one group of events (e.g. all events, or non-bot events only)."""

    # -----------------------------------------------------------------
    # def __init__(self) -> None:
    #
    # __init__ es un método especial que Python ejecuta automáticamente
    # cada vez que se crea un objeto nuevo con Stats(). Su trabajo es
    # preparar los valores iniciales del objeto.
    #
    # `self` es el objeto que se está preparando. `self.total_events = 0`
    # significa "este objeto tiene su propio total_events, que empieza
    # en 0". Como cada objeto tiene su propio `self`,
    # all_events.total_events y non_bot.total_events son dos números
    # distintos.
    # -----------------------------------------------------------------
    def __init__(self) -> None:
        # Un simple int, incrementado una vez por evento. Más simple que
        # hacer len() sobre una lista con todos los eventos, y evita
        # mantener en memoria los más de 69.000 eventos solo para
        # contarlos.
        self.total_events = 0

        # -------------------------------------------------------------
        # Counter[str]: la anotación de tipo se lee como "un Counter
        # cuyas claves son cadenas" (los valores son siempre los
        # conteos, es decir int — Counter no necesita que se indique por
        # separado).
        #
        # Tres contadores distintos, uno por cada cosa que se está contando:
        #   event_type_counts   clave = event["type"], p. ej. "PushEvent"
        #   actor_event_counts  clave = event["actor"]["login"], p. ej. "octocat"
        #   repo_event_counts   clave = event["repo"]["name"], p. ej. "octocat/Hello-World"
        # -------------------------------------------------------------
        self.event_type_counts: Counter[str] = Counter()
        self.actor_event_counts: Counter[str] = Counter()
        self.repo_event_counts: Counter[str] = Counter()

        # -------------------------------------------------------------
        # actor_repos / repo_actors: defaultdict(set)
        #
        # Los Counter de arriba cuentan EVENTOS. Pero para un grafo, la
        # pregunta es otra: "¿en cuántos repos DISTINTOS ha hecho
        # eventos este actor?" y "¿cuántos actores DISTINTOS han hecho
        # eventos en este repo?". Si ana hace 10 push al mismo repo, son
        # 10 eventos pero sigue siendo un solo repo.
        #
        # Un CONJUNTO (set) es una colección que guarda cada elemento una
        # sola vez: añadir algo que ya está no hace nada. Así que:
        #
        #     s = set()
        #     s.add("ana/app"); s.add("ana/app"); s.add("luis/web")
        #     s        # {"ana/app", "luis/web"}  -> len(s) == 2
        #
        #   actor_repos  clave = login del actor, valor = conjunto de nombres de repo
        #   repo_actors  clave = nombre del repo, valor = conjunto de logins de actor
        #
        # Estos dos diccionarios SON el grafo actor <-> repo, visto desde
        # cada lado. defaultdict(set) significa que la primera vez que
        # aparece un actor/repo, su conjunto vacío se crea
        # automáticamente (la misma comodidad que Counter empezando en 0).
        # -------------------------------------------------------------
        self.actor_repos: defaultdict[str, set[str]] = defaultdict(set)
        self.repo_actors: defaultdict[str, set[str]] = defaultdict(set)

    # -----------------------------------------------------------------
    # def add(self, event_type, actor, repo) -> None:
    #
    # Un MÉTODO: una función que pertenece a la clase y trabaja con los
    # contadores propios de un objeto (a través de `self`). Llamar a
    # all_events.add("PushEvent", "ana", "ana/app") actualiza solo los
    # contadores de all_events; los de non_bot no se tocan.
    # -----------------------------------------------------------------
    def add(self, event_type: str, actor: str, repo: str) -> None:
        self.total_events += 1

        # -------------------------------------------------------------
        # counter[key] += 1
        #
        # Aquí es donde Counter se paga frente a un dict normal: la
        # primera vez que se ve un determinado tipo de evento / actor /
        # repo, Counter trata silenciosamente la clave ausente como 0,
        # así que `+= 1` la lleva a 1. Cada aparición posterior
        # simplemente suma 1 a lo que ya tenía. Al terminar el bucle,
        # cada Counter contiene el conteo completo de cada clave distinta
        # que llegó a ver.
        # -------------------------------------------------------------
        self.event_type_counts[event_type] += 1
        self.actor_event_counts[actor] += 1
        self.repo_event_counts[repo] += 1

        # Registramos la conexión en los dos sentidos. Como son
        # conjuntos, los eventos repetidos entre el mismo actor y el
        # mismo repo no añaden duplicados — solo los compañeros NUEVOS
        # hacen crecer el conjunto.
        self.actor_repos[actor].add(repo)
        self.repo_actors[repo].add(actor)


# ---------------------------------------------------------------------
# def pct(part: int, whole: int) -> str:
#
# Convierte "part de un total whole" en un porcentaje, ya formateado como
# texto (p. ej. pct(1970, 69429) -> "  2.8%"). El script imprime
# porcentajes en muchos sitios; escribir la fórmula una sola vez aquí
# hace que todos los porcentajes se calculen y se formateen de la misma
# manera. `5.1f` se explica más abajo, en el bucle de tipos de evento.
# ---------------------------------------------------------------------
def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f}%"


# ---------------------------------------------------------------------
# def print_header(title: str) -> None:
#
# Imprime el título de una sección entre dos líneas de signos "=", para
# que las tres secciones se distingan fácilmente en la terminal.
# "=" * 70 repite el carácter "=" 70 veces; "\n" es un salto de línea,
# que deja una línea en blanco antes de cada sección.
# ---------------------------------------------------------------------
def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------
# def print_general(all_events: Stats, non_bot: Stats) -> None:
#
# SECCIÓN 1: la visión de conjunto. No necesita un conteo aparte de los
# bots — los obtiene RESTANDO: todo menos los no bots = los bots.
#   eventos de bots = todos los eventos - eventos de no bots
#   actores bot     = todos los actores - actores no bot
#   repos solo bots = todos los repos - repos donde al menos 1 no bot
#                     hizo un evento (repos que SOLO tocaron bots)
#
# `:>7` alinea cada número a la derecha en una columna de 7 caracteres
# para que los números queden alineados (la misma idea de
# especificación de formato que en el bucle de tipos de evento de más
# abajo).
# ---------------------------------------------------------------------
def print_general(all_events: Stats, non_bot: Stats) -> None:
    total = all_events.total_events
    bot_events = total - non_bot.total_events

    # -----------------------------------------------------------------
    # len(all_events.actor_event_counts)
    #
    # Como Counter es una subclase de dict, len() sobre él devuelve el
    # número de claves DISTINTAS, no la suma de los conteos. Así que
    # esto es exactamente "cuántos actores/repos únicos aparecieron en
    # el archivo" — la suma de todos los valores volvería a dar
    # total_events, que no es lo que queremos aquí.
    #
    # Ejemplo concreto: si el archivo solo tuviera 6 eventos, hechos por
    # los actores ana, luis, ana, marta, ana, luis (en ese orden), el
    # bucle dejaría
    #
    #     actor_event_counts == Counter({"ana": 3, "luis": 2, "marta": 1})
    #
    # Cada entrada tiene una CLAVE (el nombre) y un VALOR (cuántas veces
    # apareció ese nombre). Entonces:
    #
    #     len(actor_event_counts)            # 3 -> ana, luis, marta
    #     sum(actor_event_counts.values())   # 6 -> 3 + 2 + 1
    #
    # len() responde a "¿cuántos actores DISTINTOS hay?" (ana cuenta una
    # sola vez, aunque tenga 3 eventos). La suma responde a "¿cuántos
    # eventos hay?" — y como cada evento tiene exactamente un actor,
    # siempre coincide con total_events, así que no nos diría nada nuevo.
    #
    # "Subclase de dict" simplemente significa que Counter ES un
    # diccionario con funciones extra (.most_common(), claves que
    # empiezan en 0 si no existen). Así que todo lo que funciona con un
    # dict normal — como len() contando sus claves — funciona
    # exactamente igual con un Counter.
    # -----------------------------------------------------------------
    num_actors = len(all_events.actor_event_counts)
    non_bot_actors = len(non_bot.actor_event_counts)
    num_repos = len(all_events.repo_event_counts)
    non_bot_repos = len(non_bot.repo_event_counts)

    print_header("GENERAL")
    print(f"Total events:     {total:>7}")
    print(f"  Bot events:     {bot_events:>7} ({pct(bot_events, total)})")
    print(f"  Non-bot events: {non_bot.total_events:>7} ({pct(non_bot.total_events, total)})")
    print(f"Unique actors:    {num_actors:>7}")
    print(f"  Bot actors:     {num_actors - non_bot_actors:>7} "
          f"({pct(num_actors - non_bot_actors, num_actors)})")
    print(f"  Non-bot actors: {non_bot_actors:>7} ({pct(non_bot_actors, num_actors)})")
    print(f"Unique repos:     {num_repos:>7}")
    print(f"  Only bots made events in it:     {num_repos - non_bot_repos:>7} "
          f"({pct(num_repos - non_bot_repos, num_repos)})")
    print(f"  At least 1 non-bot made events:  {non_bot_repos:>7} "
          f"({pct(non_bot_repos, num_repos)})")


# ---------------------------------------------------------------------
# def print_analysis(title: str, stats: Stats, top_n: int) -> None:
#
# SECCIONES 2 y 3. Esta única función imprime el análisis completo del
# objeto Stats que reciba. summarize() la llama dos veces: una con
# all_events y otra con non_bot. Como es el mismo código las dos veces,
# está garantizado que las dos secciones muestran exactamente las mismas
# cosas en el mismo orden — que es justo lo que permite compararlas.
# ---------------------------------------------------------------------
def print_analysis(title: str, stats: Stats, top_n: int) -> None:
    print_header(title)

    print("Event types:")
    # -----------------------------------------------------------------
    # type_width = max(len(event_type) for event_type in stats.event_type_counts)
    #
    # El ancho de la columna de tipos de evento, calculado a partir de
    # los datos en lugar de ser fijo. Una versión anterior usaba un
    # ancho fijo de 25, y "PullRequestReviewCommentEvent" (29
    # caracteres) no cabía, lo que desplazaba sus números y los
    # desalineaba. Aquí medimos la longitud del nombre de cada tipo de
    # evento y nos quedamos con el más largo (max), así que la columna
    # siempre tiene exactamente el ancho necesario.
    # -----------------------------------------------------------------
    type_width = max(len(event_type) for event_type in stats.event_type_counts)

    # -----------------------------------------------------------------
    # .most_common()
    #
    # Un método que solo tiene Counter (los dict normales no lo tienen).
    # Llamado sin argumentos, devuelve CADA par (clave, conteo) como una
    # lista de tuplas, ordenada de más frecuente a menos frecuente —
    # exactamente el orden que se quiere para detectar de un vistazo
    # "qué domina este conjunto de datos". Llamado como .most_common(n)
    # (usado más abajo para actores/repos), devuelve solo los n primeros
    # pares, lo cual es más eficiente que ordenarlo todo y luego
    # recortar cuando solo se necesitan unos pocos resultados.
    # -----------------------------------------------------------------
    for event_type, count in stats.event_type_counts.most_common():
        # -------------------------------------------------------------
        # f"{event_type:<{type_width}} {count:>7} ({pct(...)})"
        #
        # La parte después de los dos puntos dentro de {} es una
        # ESPECIFICACIÓN DE FORMATO — controla cómo se rellena/alinea el
        # valor al convertirlo a texto, no solo cuál es el valor.
        #   <{type_width}  alineado a la izquierda, rellenado con
        #         espacios hasta type_width caracteres. El {type_width}
        #         interior se sustituye primero por su valor (p. ej.
        #         29), así que esto se convierte en <29. Se usa para
        #         event_type para que los números que siguen queden
        #         alineados en columna sin importar la longitud del
        #         nombre del tipo de evento.
        #   >7    alineado a la derecha, rellenado hasta al menos 7
        #         caracteres de ancho. Se usa para count para que los
        #         dígitos se alineen por su borde derecho, tal como se
        #         alinean convencionalmente los números en una tabla.
        #   5.1f  (dentro de pct()) un float de PUNTO FIJO, de al menos
        #         5 caracteres de ancho en total, con exactamente 1
        #         dígito después del punto decimal (p. ej. " 95.3" o
        #         "  0.1"). Se usa para el porcentaje para que cada fila
        #         muestre el mismo número de decimales.
        # Nada de esto cambia el valor subyacente — solo cómo se
        # representa como texto.
        # -------------------------------------------------------------
        print(f"  {event_type:<{type_width}} {count:>7} ({pct(count, stats.total_events)})")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in stats.actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in stats.repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    # -----------------------------------------------------------------
    # Conectividad: ¿se puede RECORRER de verdad este grafo?
    #
    # El benchmark recorre actor -> repo -> actor -> repo. Cada paso de
    # un repo a "otro actor" solo funciona si en ese repo han hecho
    # eventos al menos 2 actores distintos; si no, el recorrido se queda
    # atascado. Estos tres números miden con qué frecuencia es posible:
    #
    #   shared_repos       repos con 2 o más actores distintos — los
    #                      únicos "puentes" de un actor a otro.
    #   multi_repo_actors  actores que han hecho eventos en 2 o más
    #                      repos — los únicos actores desde los que un
    #                      recorrido puede ramificarse hacia otro repo.
    #   connected_actors   todos los actores que aparecen en al menos un
    #                      repo compartido, es decir, que tienen al
    #                      menos un actor vecino. El resto son islas.
    #
    # Sintaxis utilizada:
    #   [x for x, y in d.items() if cond]   una LIST COMPREHENSION
    #       (comprensión de lista): un bucle en una sola línea que
    #       construye una lista, quedándose solo con los elementos para
    #       los que cond es True. .items() da pares (clave, valor).
    #   {a for r in shared_repos for a in repo_actors[r]}   una SET
    #       COMPREHENSION (comprensión de conjunto) con dos bucles: para
    #       cada repo compartido, toma cada actor que hay en él. Al ser
    #       un conjunto, un actor que está en varios repos compartidos
    #       solo se cuenta una vez.
    # -----------------------------------------------------------------
    shared_repos = [repo for repo, actors in stats.repo_actors.items() if len(actors) >= 2]
    multi_repo_actors = [actor for actor, repos in stats.actor_repos.items() if len(repos) >= 2]
    connected_actors = {actor for repo in shared_repos for actor in stats.repo_actors[repo]}
    num_actors = len(stats.actor_repos)
    num_repos = len(stats.repo_actors)

    print("\nConnectivity:")
    print(f"  Repos with 2+ different actors:           {len(shared_repos):>6} "
          f"({pct(len(shared_repos), num_repos)} of repos)")
    print(f"  Actors who made events in 2+ repos:       {len(multi_repo_actors):>6} "
          f"({pct(len(multi_repo_actors), num_actors)} of actors)")
    print(f"  Actors sharing a repo with another actor: {len(connected_actors):>6} "
          f"({pct(len(connected_actors), num_actors)} of actors)")

    # -----------------------------------------------------------------
    # repos_per_actor = Counter({actor: len(repos) for ...})
    #
    # {k: v for ...} es una DICT COMPREHENSION (comprensión de
    # diccionario): un bucle en una sola línea que construye un
    # diccionario. Aquí convierte "actor -> conjunto de repos" en
    # "actor -> CUÁNTOS repos distintos". Envolverlo en Counter(...)
    # sirve simplemente para poder reutilizar .most_common(top_n) y
    # obtener los primeros, ya ordenados.
    #
    # Este ranking importa más que "más eventos": una cuenta que hace
    # eventos en cientos de repos DISTINTOS actúa como un nodo central
    # (hub) que une partes del grafo que de otro modo no tendrían
    # relación — que es justo lo que resultan hacer bots como
    # github-actions[bot].
    # -----------------------------------------------------------------
    repos_per_actor = Counter({actor: len(repos) for actor, repos in stats.actor_repos.items()})
    print(f"\nTop {top_n} actors by number of different repos they made events in:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} different repos")

    # La misma idea desde el lado del repo: los repos con más actores
    # distintos son los "puntos de encuentro" más concurridos del grafo.
    actors_per_repo = Counter({repo: len(actors) for repo, actors in stats.repo_actors.items()})
    print(f"\nTop {top_n} repos by number of different actors who made events in them:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} different actors")


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# La misma forma con dos parámetros obligatorios que peek()
# (file_path, num_lines). Lee el archivo UNA sola vez, rellena dos
# objetos Stats a la vez y después imprime las tres secciones.
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    all_events = Stats()
    non_bot = Stats()

    # -----------------------------------------------------------------
    # El mismo patrón `with open(..., "r", encoding="utf-8") as f:` que
    # peek() — ver la copia anotada de peek_data.py para entender por
    # qué el modo texto y el UTF-8 explícito son las decisiones
    # correctas aquí.
    #
    # La diferencia clave con peek(): aquí NO hay ningún `if i >=
    # num_lines: break`. peek() se detiene deliberadamente pronto porque
    # solo quiere un puñado de eventos de muestra; summarize() lee
    # deliberadamente cada línea, una por una, porque un conteo o
    # porcentaje calculado solo con los primeros cientos de eventos no
    # representaría el archivo completo.
    # -----------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # for line in f:
        #
        # Esto es un BUCLE: un bloque de código que SE REPITE. Se lee
        # como "para cada línea del archivo f, haz las líneas con
        # sangría de abajo". Esas líneas con sangría se escriben una
        # sola vez, pero se ejecutan una vez POR CADA LÍNEA del archivo
        # — 69.429 veces para la hora de este proyecto, una por evento.
        # Piensa en el recuento de votos de una urna: sacas una
        # papeleta, apuntas una rayita junto a su nombre, vuelves a
        # sacar la siguiente, hasta que la urna queda vacía. Cuando el
        # archivo se queda sin líneas, el bucle termina y Python sigue
        # con la primera línea sin sangría que viene después (las
        # llamadas a print_...() de abajo).
        #
        # No hace falta enumerate() aquí — a diferencia de peek(),
        # summarize() nunca imprime un índice de línea, así que la
        # posición en el bucle no sirve para nada, solo importa el
        # evento ya analizado.
        for line in f:
            event = json.loads(line)

            # Sacamos los tres valores una sola vez y les damos nombres
            # de variable cortos, ya que cada uno se usa dos veces abajo.
            event_type = event["type"]
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]

            # ---------------------------------------------------------
            # Todos los eventos van a all_events. Solo los eventos que
            # no son de bots van TAMBIÉN a non_bot. Así que, al terminar
            # el bucle:
            #   all_events  = los conteos CON bots
            #   non_bot     = los conteos SIN bots
            # Los dos salen de una sola pasada por el archivo — no hace
            # falta leer las más de 69.000 líneas dos veces.
            # ---------------------------------------------------------
            all_events.add(event_type, actor, repo)
            if not is_bot(actor):
                non_bot.add(event_type, actor, repo)

    print_general(all_events, non_bot)
    print_analysis("ANALYSIS WITH BOTS (all events)", all_events, top_n)
    print_analysis(f"ANALYSIS WITHOUT BOTS (logins ending in '{BOT_SUFFIX}' removed)",
                   non_bot, top_n)


# ---------------------------------------------------------------------
# parse_args(): mismo esquema general que la versión de peek_data.py. Lo
# único que vale la pena destacar es que --top cumple el mismo papel que
# cumplía --lines allí (un simple entero positivo, sin restricción
# `choices=`) — solo que aplicado a "cuántos actores/repos más activos
# mostrar" en lugar de "cuántos eventos de muestra imprimir".
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
