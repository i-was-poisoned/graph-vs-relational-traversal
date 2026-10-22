########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de scripts/download_gharchive.py.
# NO está pensado para ejecutarse como parte del pipeline del proyecto — vive en
# docs_spanish/ porque su propósito es enseñar, no ejecutarse. El script real y "limpio"
# (sin nada de este comentario) es scripts/download_gharchive.py.
#
# Léelo de arriba a abajo — cada concepto se construye sobre el anterior.
########################################################################


########################################################################
# EL DOCSTRING DEL MÓDULO (la cadena de texto entre comillas triples de abajo)
#
# En Python, si lo primero que hay en un archivo es un literal de cadena
# de texto (no asignado a ninguna variable, simplemente ahí solo), Python
# lo trata de forma especial: se convierte en el "docstring" del archivo,
# almacenado en un atributo oculto llamado __doc__.
#
# ¿Por qué molestarse? Porque las herramientas pueden leerlo automáticamente:
#   - Ejecutar `python scripts/download_gharchive.py --help` imprime este
#     texto como parte de la salida de ayuda (lo conectamos más adelante
#     mediante `argparse.ArgumentParser(description=__doc__)`).
#   - Si alguien `import`a este archivo como un módulo y ejecuta
#     `help(download_gharchive)` en una shell de Python, se muestra este
#     texto.
#
# Está escrito en texto plano (no como un comentario que empieza con #)
# precisamente para que pueda ser extraído y mostrado por otros programas,
# no solo leído por un humano mirando el código fuente.
#
# QUÉ HAY DE NUEVO en esta versión: una función aparte, fetch_gz(), que
# SOLO descarga el archivo comprimido .json.gz (con reintentos, un tiempo
# máximo de espera (timeout) y un truco de seguridad: "escribir en .part
# y luego renombrar"). El pipeline en vivo de 24 horas (pipeline.py) usa
# fetch_gz() directamente, porque no necesita los enormes archivos .json
# descomprimidos en disco. download() ahora simplemente llama a
# fetch_gz() y después descomprime, exactamente igual que antes.
########################################################################
"""Download GH Archive hourly dataset files.

Defaults to this project's fixed benchmark hour (see README.md): downloads it
and decompresses it to plain JSON Lines. Any date/hour can be requested for
exploration. The live pipeline (pipeline.py) uses fetch_gz() to download
hours without decompressing them.

Usage:
    python scripts/download_gharchive.py
    python scripts/download_gharchive.py --date 2026-08-27 --hour 15
"""


########################################################################
# IMPORTACIONES (IMPORTS)
#
# La biblioteca estándar de Python viene con una enorme colección de
# módulos ya hechos (archivos llenos de código previamente escrito) que
# puedes traer a tu propio script con la palabra clave `import`, en lugar
# de escribir esa funcionalidad tú mismo desde cero. Todas las
# importaciones de abajo son de "biblioteca estándar" — es decir, vienen
# incluidas con el propio Python. No hace falta instalar nada por
# separado (p. ej. no se necesita `pip install`) para ejecutar este
# script.
#
# `import x` hace que todo lo que hay dentro del módulo `x` sea accesible
# como `x.algo`. `from x import y` entra dentro del módulo `x` y extrae
# solo `y`, haciéndolo accesible directamente como `y` (sin necesidad del
# prefijo `x.`).
########################################################################

# argparse: convierte los indicadores (flags) de línea de comandos (como
# `--date 2026-08-27`) escritos después de
# `python scripts/download_gharchive.py` en valores de Python
# estructurados, en lugar de tener que analizar tú mismo sys.argv (la
# lista cruda de palabras de la línea de comandos) manualmente.
import argparse

# gzip: permite a Python leer archivos comprimidos con el algoritmo gzip
# (la misma compresión detrás de la extensión de archivo `.gz`) sin que
# tengas que implementar la descompresión tú mismo.
import gzip

# shutil ("utilidades de shell"): un conjunto variado de operaciones de
# archivo de alto nivel. Usamos una función de él: copyfileobj, que copia
# datos de un archivo ya abierto a otro en fragmentos pequeños.
import shutil

# time: funciones relacionadas con el tiempo. Usamos solo una:
# time.sleep(segundos), que pausa el script durante esos segundos.
# fetch_gz() la usa para esperar un poco antes de reintentar una
# descarga que ha fallado.
import time

# urllib.error: los tipos de excepción (error) que lanza urllib cuando
# una petición sale mal — p. ej. HTTPError ("el servidor respondió, pero
# con un código de error como 404 o 503") y URLError ("no se pudo llegar
# al servidor en absoluto"). Lo importamos para que fetch_gz() pueda
# capturar estos errores POR SU NOMBRE y reaccionar de forma distinta a
# cada tipo.
import urllib.error

# urllib.request: la herramienta integrada de la biblioteca estándar para
# hacer peticiones HTTP(S) — en nuestro caso, simplemente obtener un
# archivo desde una URL, como lo que hace un navegador web cuando haces
# clic en un enlace de descarga.
import urllib.request

# `from pathlib import Path` extrae la clase Path del módulo pathlib.
# Path representa una ruta del sistema de archivos (la ubicación de un
# archivo o carpeta) como un objeto con métodos útiles, en lugar de como
# una simple cadena de texto que tendrías que trocear y unir tú mismo.
from pathlib import Path


########################################################################
# CONSTANTES
#
# Estas son simplemente variables normales de Python, pero escritas en
# MAYÚSCULAS por convención. Python no tiene ninguna palabra clave ni
# mecanismo especial de "constante" — las MAYÚSCULAS son puramente una
# convención humana que significa "por acuerdo, no se pretende que este
# valor se reasigne en ningún otro lugar del código." Señala una
# intención, nada más.
########################################################################

# La fecha y hora específicas que este proyecto ha elegido como su
# conjunto de datos fijo y reproducible (ver README.md para saber por qué
# se eligió exactamente esta hora). Guardarlas aquí significa que
# cualquier otra parte del script puede referirse a DEFAULT_DATE /
# DEFAULT_HOUR en lugar de repetir los valores literales.
DEFAULT_DATE = "2026-08-27"
DEFAULT_HOUR = 15

# ---------------------------------------------------------------------
# Construyendo DATA_DIR, pieza por pieza:
#
#   __file__
#     Una variable especial que Python fija automáticamente dentro de
#     cada módulo, con la ruta del propio archivo fuente de ese módulo.
#     Aquí sería algo como:
#       C:\dev\Research\scripts\download_gharchive.py
#
#   Path(__file__)
#     Envuelve esa cadena de texto en un objeto Path, desbloqueando
#     métodos relacionados con rutas (como los usados a continuación) en
#     lugar de tener que manipular la cadena cruda a mano.
#
#   .resolve()
#     Convierte la ruta en una ruta absoluta (empezando desde la raíz de
#     la unidad, p. ej. `C:\...`) y limpia cualquier segmento tipo `..`.
#     Esto importa porque __file__ a veces puede ser una ruta relativa,
#     dependiendo de cómo se lanzó el script — .resolve() garantiza que
#     siempre obtengamos la ubicación completa y sin ambigüedades.
#
#   .parent
#     Los objetos Path entienden la jerarquía de carpetas. `.parent` de
#     `C:\dev\Research\scripts\download_gharchive.py` es
#     `C:\dev\Research\scripts` (la carpeta que contiene el archivo).
#
#   .parent.parent
#     Subiendo un nivel más: el padre de `C:\dev\Research\scripts` es
#     `C:\dev\Research` — la raíz del proyecto.
#
#   / "data"
#     Los objetos Path sobrecargan el operador `/` para significar "unir
#     un segmento de ruta a esta ruta" — esta es la alternativa legible
#     de pathlib a os.path.join(). El resultado es `C:\dev\Research\data`.
#
# ¿Por qué calcular esto a partir de __file__ en lugar de simplemente
# escribir "data" como ruta relativa? Porque una ruta relativa como
# "data" se interpreta en relación con el lugar en el que te encuentres
# en la terminal (tu "directorio de trabajo actual") cuando ejecutas el
# script — que podría ser cualquiera. Construir la ruta a partir de
# __file__ en cambio garantiza que la carpeta data/ siempre termina justo
# al lado del proyecto, sin importar en qué directorio estuvieras cuando
# escribiste el comando `python ...`.
# ---------------------------------------------------------------------
DATA_DIR = Path(__file__).resolve().parent.parent / "data"


########################################################################
# FUNCIONES — ¿POR QUÉ MOLESTARSE?
#
# Una función es un bloque de código con nombre y reutilizable. En lugar
# de escribir la lógica de descarga en línea al final del archivo,
# envolverla en una función llamada `download` significa que:
#   1. Se puede llamar varias veces con distintos argumentos (p. ej.
#      distintas fechas/horas) sin duplicar código.
#   2. Más adelante podría importarse y reutilizarse desde otros scripts
#      (p. ej. un futuro script que descargue varias horas en un bucle).
#   3. Le da un nombre al bloque de lógica, lo que documenta la
#      intención.
#
# Este archivo tiene ahora DOS funciones así, repartidas por tarea:
#   fetch_gz()   solo DESCARGA el archivo comprimido .json.gz.
#   download()   llama a fetch_gz() y después DESCOMPRIME el resultado.
# El pipeline en vivo (pipeline.py) importa y llama a fetch_gz() por su
# cuenta — el punto 2 de arriba, en la vida real.
########################################################################

# ---------------------------------------------------------------------
# Leyendo la firma de la función:
#
#   def fetch_gz(date: str, hour: int, data_dir: Path = DATA_DIR,
#                retries: int = 3) -> Path:
#
#   `def`            palabra clave que inicia la definición de una función.
#   `fetch_gz`       el nombre de la función — cómo la llamarás más adelante.
#   `date: str`      un parámetro llamado `date`. El `: str` que le sigue
#                    es una "anotación de tipo" (type hint) — una nota
#                    (¡no impuesta por Python en tiempo de ejecución!) que
#                    le dice a quien lea el código y a las herramientas
#                    del editor "se espera que esto sea una cadena de
#                    texto." Es documentación, no una garantía — Python
#                    no te impedirá pasar otra cosa.
#   `hour: int`      otro parámetro, anotado como un entero.
#   `data_dir: Path = DATA_DIR`
#                    un parámetro anotado como un objeto Path, con un
#                    VALOR POR DEFECTO de DATA_DIR. Los valores por
#                    defecto significan que quien llama a la función
#                    puede omitir este argumento por completo y caerá de
#                    forma automática en DATA_DIR. Esto es lo que permite
#                    que pruebas o código futuro sobreescriban dónde se
#                    guardan los archivos sin cambiar la función en sí.
#   `retries: int = 3`
#                    cuántas veces INTENTAR la descarga antes de rendirse.
#                    También tiene un valor por defecto, así que normalmente
#                    quien llama escribe simplemente
#                    fetch_gz("2026-08-27", 15).
#   `-> Path`        una anotación de tipo de retorno: se espera que esta
#                    función devuelva un objeto Path cuando termine (aquí:
#                    la ruta del archivo .json.gz descargado).
# ---------------------------------------------------------------------
def fetch_gz(date: str, hour: int, data_dir: Path = DATA_DIR, retries: int = 3) -> Path:
    # ---------------------------------------------------------------
    # UN DOCSTRING DE FUNCIÓN
    #
    # La misma idea que el docstring del módulo al principio del
    # archivo, pero para una función: una cadena de texto que es lo
    # primero dentro del `def` se convierte en el __doc__ de esa
    # función. En una shell de Python, `help(fetch_gz)` la imprimiría.
    # Resume las dos medidas de seguridad explicadas en detalle más
    # abajo (archivo .part + reintentos).
    # ---------------------------------------------------------------
    """Download one hour's .json.gz file into data_dir and return its path.

    The file is written to a temporary ".part" name and only renamed once the
    download has finished, so an interrupted download never leaves a broken file
    that looks complete. Network errors are retried; a missing hour (HTTP 404,
    e.g. not published yet) is not.
    """
    # ---------------------------------------------------------------
    # Asegurarse de que la carpeta de destino existe antes de intentar
    # guardar nada en ella.
    #
    #   .mkdir(...)        "make directory" (crear directorio) — crea la
    #                        carpeta.
    #   parents=True         también crea cualquier carpeta padre que
    #                        falte por el camino (no hace falta aquí ya
    #                        que la raíz del proyecto ya existe, pero es
    #                        un valor por defecto seguro).
    #   exist_ok=True         NO lanzar un error si la carpeta ya existe
    #                        — simplemente continuar en silencio. Sin
    #                        esto, volver a ejecutar el script una
    #                        segunda vez fallaría en esta línea.
    # ---------------------------------------------------------------
    data_dir.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------
    # f-strings: un literal de cadena de texto con el prefijo `f` te deja
    # incrustar valores de variables directamente dentro de `{llaves}`.
    # Esta línea construye un nombre de archivo como
    # "2026-08-27-15.json.gz" sustituyendo los valores reales de `date`
    # y `hour` en la plantilla.
    #
    # Ojo: GH Archive escribe la hora SIN cero a la izquierda: la hora 5
    # da "2026-08-27-5.json.gz", no "2026-08-27-05.json.gz". Como `hour`
    # es un int, {hour} se imprime como "5" — justo lo que necesitamos.
    # ---------------------------------------------------------------
    filename = f"{date}-{hour}.json.gz"

    # La misma técnica de f-string, construyendo la URL completa de
    # descarga insertando el nombre de archivo en el patrón de URL
    # conocido de GH Archive.
    url = f"https://data.gharchive.org/{filename}"

    # De nuevo el operador `/` (de pathlib): une el Path data_dir con la
    # cadena de texto filename, produciendo una ruta completa como
    # C:\dev\Research\data\2026-08-27-15.json.gz — aquí es donde se
    # guardará el archivo descargado (todavía comprimido).
    gz_path = data_dir / filename

    # ---------------------------------------------------------------
    # EL TRUCO DEL ARCHIVO ".part"
    #
    # part_path es un nombre TEMPORAL junto al real, p. ej.
    #   C:\dev\Research\data\2026-08-27-15.json.gz.part
    # (filename + ".part" es simplemente pegar cadenas de texto: los
    # paréntesis extra aseguran que las cadenas se unan PRIMERO, y solo
    # después el resultado se une a data_dir con `/`.)
    #
    # ¿Por qué? Imagina que escribiéramos directamente en
    # 2026-08-27-15.json.gz y el Wi-Fi se cayera a mitad. Nos quedaría
    # un archivo escrito a medias que tiene el nombre final CORRECTO. El
    # código posterior (o tú) vería "2026-08-27-15.json.gz existe" y
    # supondría que está completo — y luego fallaría o, peor aún,
    # cargaría en silencio media hora de datos.
    #
    # En su lugar descargamos en el archivo .part, y solo cuando la
    # descarga ha terminado DEL TODO lo renombramos al nombre real (ver
    # part_path.replace(...) más abajo). Así que: si existe un archivo
    # con el nombre real, está garantizado que está completo. Los
    # navegadores hacen lo mismo (".crdownload" en Chrome, ".part" en
    # Firefox).
    # ---------------------------------------------------------------
    part_path = data_dir / (filename + ".part")

    # ---------------------------------------------------------------
    # EL BUCLE DE REINTENTOS
    #
    # Las redes son poco fiables: una descarga puede fallar una vez y
    # funcionar un minuto después. Así que en lugar de intentarlo solo
    # una vez, lo intentamos hasta `retries` veces (3 por defecto).
    #
    #   range(1, retries + 1)
    #     range() se detiene ANTES de su valor final, así que
    #     range(1, 4) da 1, 2, 3. Empezar en 1 (no en 0) hace que
    #     `attempt` se lea de forma natural en el mensaje: "attempt 1/3",
    #     "attempt 2/3", "attempt 3/3".
    #
    # Cómo termina el bucle — solo hay tres salidas:
    #   1. ÉXITO: el `return gz_path` dentro del `try` sale de toda la
    #      función inmediatamente, bucle incluido.
    #   2. RENDIRSE: en el último intento, `raise` vuelve a lanzar el
    #      error, lo que también sale de la función (quien llama ve el
    #      error).
    #   3. 404: lanza FileNotFoundError de inmediato (sin reintentar).
    # Si no ocurre ninguna de esas, el bucle da otra vuelta tras una
    # pausa.
    # ---------------------------------------------------------------
    for attempt in range(1, retries + 1):
        # print() escribe texto en la terminal para que un humano que
        # ejecute el script pueda ver qué está pasando, ya que la propia
        # descarga puede tardar unos segundos sin ninguna
        # retroalimentación visible en caso contrario. Ahora también
        # muestra qué intento es, p. ej.
        #   Downloading https://data.gharchive.org/2026-08-27-15.json.gz (attempt 1/3) ...
        print(f"Downloading {url} (attempt {attempt}/{retries}) ...")

        # -----------------------------------------------------------
        # try / except: "intenta este bloque; si dentro ocurre un tipo
        # concreto de error, no te caigas — salta al bloque `except`
        # correspondiente." Cada `except` nombra los tipos de error que
        # gestiona; cualquier OTRO error sigue haciendo fallar el
        # programa como siempre (que es lo que queremos para bugs
        # realmente inesperados).
        # -----------------------------------------------------------
        try:
            # -------------------------------------------------------
            # ¿Por qué no el más simple urllib.request.urlretrieve(url, gz_path)?
            #
            # Ese era el enfoque original, y parece correcto — pero falla
            # contra el servidor de GH Archive con "HTTP Error 403:
            # Forbidden". Toda petición HTTP lleva un encabezado llamado
            # User-Agent, que identifica qué tipo de cliente está
            # haciendo la petición (un navegador, un script, etc.).
            # urlretrieve envía un User-Agent por defecto que
            # literalmente dice "Python-urllib/3.14" — y el servidor de
            # GH Archive rechaza peticiones que no parezcan venir de un
            # navegador real, como medida básica anti-bots. 403 significa
            # específicamente "entendí tu petición y me niego a
            # cumplirla" (a diferencia de 404, que significaría "ese
            # archivo no existe").
            #
            # La solución: construir la petición manualmente para poder
            # fijar nuestro propio encabezado User-Agent, haciéndonos
            # pasar por un navegador.
            #
            #   urllib.request.Request(url, headers={...})
            #     Crea un OBJETO Request — describiendo qué obtener y con
            #     qué encabezados — sin enviar nada todavía. Esta es la
            #     versión "manual" de lo que urlretrieve hacía
            #     automáticamente (y de forma poco flexible) por debajo.
            #
            #   urllib.request.urlopen(request, timeout=120)
            #     Realmente envía la petición por la red y devuelve un
            #     objeto de respuesta, que se comporta como un archivo
            #     legible: puedes ir extrayendo bytes de él igual que al
            #     leer de un archivo abierto. Se usa aquí dentro del
            #     MISMO `with` que el archivo de salida, así que tanto la
            #     respuesta de red como el archivo de destino se cierran
            #     correctamente después.
            #     NUEVO: `timeout=120` significa "si el servidor se queda
            #     callado durante 120 segundos, abandona este intento con
            #     un error" (TimeoutError — se captura más abajo y se
            #     reintenta). Sin un timeout, una conexión atascada
            #     podría dejar el script colgado para siempre, algo malo
            #     para un pipeline que funciona sin supervisión.
            #
            #   open(part_path, "wb")
            #     NUEVO: escribimos en el archivo temporal .part, NO en
            #     el gz_path final (ver "EL TRUCO DEL ARCHIVO .part"
            #     arriba).
            #
            #   shutil.copyfileobj(response, f_out)
            #     La misma idea de copia en flujo (streaming) explicada
            #     más adelante en este archivo para el paso de
            #     descompresión: leer de `response` y escribir en `f_out`
            #     en fragmentos pequeños, en lugar de traer toda la
            #     descarga a memoria primero.
            # -------------------------------------------------------
            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(request, timeout=120) as response, open(part_path, "wb") as f_out:
                shutil.copyfileobj(response, f_out)

            # -------------------------------------------------------
            # Solo llegamos a esta línea si la descarga terminó sin
            # ningún error. AHORA renombramos el archivo .part a su
            # nombre real.
            #
            #   part_path.replace(gz_path)
            #     Renombra (mueve) el archivo de part_path a gz_path. Si
            #     ya existe un archivo llamado gz_path, se sobreescribe.
            #     (Path también tiene .rename(), pero en Windows
            #     .rename() FALLA si el destino ya existe; .replace()
            #     funciona igual en todos los sistemas operativos.)
            #
            # Un renombrado en el mismo disco es casi instantáneo y o
            # bien ocurre del todo o no ocurre en absoluto, así que nunca
            # hay un momento en el que gz_path exista pero esté escrito
            # solo a medias.
            # -------------------------------------------------------
            part_path.replace(gz_path)
            print(f"Saved to {gz_path}")

            # Éxito: devolvemos la ruta y salimos de la función (y por
            # tanto del bucle de reintentos) de inmediato.
            return gz_path

        # -----------------------------------------------------------
        # CASO DE ERROR 1: el servidor RESPONDIÓ, pero con un estado de
        # error.
        #
        #   except urllib.error.HTTPError as error:
        #     Se ejecuta si algo dentro del `try` lanzó un HTTPError. La
        #     parte `as error` guarda el objeto de error en una variable
        #     para que podamos inspeccionarlo — p. ej. error.code es el
        #     número de estado HTTP (404, 403, 503, ...).
        #
        #   part_path.unlink(missing_ok=True)
        #     "unlink" es el nombre tradicional (de Unix) para "borrar un
        #     archivo". Tiramos cualquier archivo .part escrito a medias
        #     para que no se quede en data/. missing_ok=True significa
        #     "no te quejes si el archivo no está" — p. ej. si el error
        #     ocurrió antes de que open() llegara a crearlo.
        #
        #   if error.code == 404:
        #     404 = "Not Found" (no encontrado). En GH Archive esto suele
        #     significar que la hora AÚN NO SE HA PUBLICADO (los archivos
        #     aparecen un rato después de que termine la hora) — o que la
        #     fecha simplemente está mal. Reintentar 10 o 20 segundos
        #     después no servirá de nada, así que paramos de inmediato y
        #     lanzamos FileNotFoundError, un tipo de error más claro que
        #     quien llama (p. ej. pipeline.py) puede capturar con el
        #     significado de "esta hora no está disponible, inténtalo más
        #     tarde".
        #
        #   raise ... from error
        #     Lanza nuestro error NUEVO pero lo enlaza con el ORIGINAL.
        #     Si el programa falla, Python imprime ambos, unidos por "The
        #     above exception was the direct cause of the following
        #     exception" — así no se pierde información de depuración.
        #
        #   if attempt == retries: raise
        #     Cualquier otro error HTTP (p. ej. 503 "Service
        #     Unavailable") podría ser temporal, así que lo reintentamos...
        #     salvo que este FUERA el último intento. Un `raise` a secas
        #     (sin nombrar ningún error detrás) significa "vuelve a
        #     lanzar el error que estoy gestionando ahora, sin cambios" —
        #     es decir, rendirse y dejar que quien llama vea el error
        #     real.
        # -----------------------------------------------------------
        except urllib.error.HTTPError as error:
            part_path.unlink(missing_ok=True)
            if error.code == 404:
                raise FileNotFoundError(f"{url} does not exist (not published yet?)") from error
            if attempt == retries:
                raise

        # -----------------------------------------------------------
        # CASO DE ERROR 2: no pudimos hablar bien con el servidor en
        # absoluto.
        #
        # Poner varios tipos de error en una tupla, (A, B, C), significa
        # "captura cualquiera de estos":
        #   urllib.error.URLError  p. ej. sin internet, falló la búsqueda DNS
        #   TimeoutError           se agotó el timeout de 120 segundos de arriba
        #   ConnectionError        p. ej. la conexión se cortó a mitad
        #
        # (El orden importa: HTTPError es en realidad un TIPO especial de
        # URLError, así que el `except` de HTTPError tiene que ir
        # primero — Python usa el primer `except` que encaja.)
        #
        # Mismo tratamiento que arriba: borrar el archivo parcial, y solo
        # rendirse (volver a lanzar) si este era el último intento.
        # -----------------------------------------------------------
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            part_path.unlink(missing_ok=True)
            if attempt == retries:
                raise

        # -----------------------------------------------------------
        # ESPERA PROGRESIVA (BACKOFF): si llegamos aquí, un intento ha
        # fallado pero vamos a reintentar. Primero esperamos —
        # reintentar al instante probablemente toparía con el mismo
        # problema. La espera crece cada vez ("backoff"):
        #   tras fallar el intento 1: dormir 10 * 1 = 10 segundos
        #   tras fallar el intento 2: dormir 10 * 2 = 20 segundos
        # (Tras el intento 3 nunca llegamos aquí: el `raise` de arriba ya
        # ha salido de la función.)
        # -----------------------------------------------------------
        time.sleep(10 * attempt)  # esperar un poco más tras cada intento fallido

    # ---------------------------------------------------------------
    # raise RuntimeError("unreachable")
    #
    # Como se explica antes del bucle, todo camino a través de él
    # termina en `return` o en `raise`, así que esta línea nunca puede
    # ejecutarse de verdad. Entonces, ¿por qué escribirla?
    #   - Los comprobadores de tipos / editores ven "la función promete
    #     `-> Path`, pero llegar al final devolvería None" y avisarían.
    #     Esta línea deja explícito que nunca se llega al final.
    #   - Si alguien edita más tarde el bucle y rompe esa garantía (p.
    #     ej. pone retries=0, ¡y el cuerpo del bucle nunca se ejecuta!),
    #     el programa falla de forma ruidosa aquí en lugar de devolver
    #     None en silencio.
    # ---------------------------------------------------------------
    raise RuntimeError("unreachable")


########################################################################
# download(): descargar, Y DESPUÉS descomprimir
#
# La misma firma que fetch_gz(), solo que sin `retries` (se usa el valor
# por defecto de 3 de fetch_gz()). Todo el trabajo de descarga de arriba
# lo hace ahora una sola llamada a fetch_gz(); lo que queda aquí es el
# paso de descompresión, que no ha cambiado respecto a la versión
# anterior.
########################################################################
def download(date: str, hour: int, data_dir: Path = DATA_DIR) -> Path:
    # Descargar el archivo comprimido (con reintentos y el truco del
    # .part) y obtener su ruta, p. ej.
    # C:\dev\Research\data\2026-08-27-15.json.gz
    gz_path = fetch_gz(date, hour, data_dir)

    # ---------------------------------------------------------------
    # gz_path.with_suffix(""):
    # Los objetos Path entienden las extensiones de archivo ("sufijos").
    # `with_suffix` devuelve un Path NUEVO con la extensión reemplazada —
    # pasar una cadena vacía la elimina por completo. Así:
    #   C:\...\2026-08-27-15.json.gz   -->   C:\...\2026-08-27-15.json
    # Esto se convierte en el nombre de archivo de destino para la salida
    # descomprimida.
    # (El gz_path original queda intacto — los objetos Path son
    # inmutables; esto crea un objeto nuevo en lugar de modificar gz_path
    # en el sitio.)
    # ---------------------------------------------------------------
    json_path = gz_path.with_suffix("")
    print(f"Decompressing to {json_path} ...")

    # ---------------------------------------------------------------
    # LA SENTENCIA `with` (un "gestor de contexto")
    #
    # Abrir un archivo te da una conexión activa a él que debería cerrarse
    # de nuevo una vez que termines — de lo contrario puedes filtrar
    # recursos (un bug sutil que empeora cuanto más archivos se abren a
    # lo largo de la vida de un programa) o dejar datos parcialmente
    # escritos sin volcar (flush) a disco. `with ... as ...:` garantiza
    # que el archivo se cierre correctamente una vez que termine el
    # bloque indentado que hay debajo — incluso si ocurre un error a
    # mitad de camino. Esta es la forma estándar e idiomática de trabajar
    # con archivos en Python; la verás constantemente.
    #
    # Esta línea abre DOS archivos a la vez dentro de un único `with`,
    # usando una coma para combinarlos:
    #
    #   gzip.open(gz_path, "rb") as f_in
    #     Abre el archivo .gz descargado, pero usando la propia función
    #     open() de gzip en lugar del open() integrado normal de Python.
    #     Esto significa que las lecturas desde f_in se descomprimen
    #     automáticamente sobre la marcha — nunca ves los bytes
    #     comprimidos crudos, solo el contenido descomprimido, como si el
    #     archivo nunca hubiera estado comprimido. "rb" significa "read,
    #     binary mode" (lectura, modo binario; bytes crudos, no texto —
    #     importante porque los datos de JSON Lines deben manejarse aquí
    #     como bytes; no estamos intentando interpretarlos/decodificarlos
    #     todavía, solo moverlos a otro archivo).
    #
    #   open(json_path, "wb") as f_out
    #     Abre (creándolo si es necesario) el archivo .json de texto
    #     plano de destino para escritura. "wb" significa "write, binary
    #     mode" (escritura, modo binario) — coincidiendo con el modo
    #     binario de f_in, ya que estamos copiando bytes crudos, no texto.
    # ---------------------------------------------------------------
    with gzip.open(gz_path, "rb") as f_in, open(json_path, "wb") as f_out:
        # ---------------------------------------------------------------
        # shutil.copyfileobj(f_in, f_out):
        # Lee de f_in y escribe en f_out en fragmentos pequeños (un
        # tamaño de búfer interno por defecto), repitiendo el bucle hasta
        # que f_in se agota. El beneficio clave frente a algo como
        # `f_out.write(f_in.read())` es el uso de memoria:
        # `f_in.read()` cargaría el archivo descomprimido ENTERO en
        # memoria de una sola vez antes de escribir nada de él. Para un
        # archivo enorme, eso podría usar una gran cantidad de RAM de
        # golpe. copyfileobj, en cambio, lo transmite (streaming) en
        # pequeños fragmentos, manteniendo bajo el uso de memoria sin
        # importar el tamaño total del archivo.
        # ---------------------------------------------------------------
        shutil.copyfileobj(f_in, f_out)

    # Una vez que termina el bloque `with` de arriba, ambos archivos se
    # han cerrado automáticamente. Ahora le decimos al usuario que hemos
    # terminado.
    print(f"Done: {json_path}")

    # Devolvemos la ruta al archivo final, descomprimido, para que el
    # código que llama a esta función (ver main(), más abajo) — o
    # cualquiera que importe esta función desde otro script — pueda
    # saber de inmediato dónde terminó el dato utilizable, sin tener que
    # reconstruir la ruta por su cuenta.
    return json_path


########################################################################
# parse_args(): convertir los indicadores de línea de comandos en un
# objeto estructurado
########################################################################
def parse_args() -> argparse.Namespace:
    # ---------------------------------------------------------------
    # argparse.ArgumentParser(...) crea un objeto "parser" que sabe cómo
    # leer la lista de palabras escritas después de
    # `python scripts/download_gharchive.py` en la línea de comandos
    # (p. ej. `--date 2026-08-27 --hour 15`) y convertirlas en valores
    # de Python.
    #
    # `description=__doc__` reutiliza el docstring del módulo de este
    # archivo (la cadena de texto entre comillas triples al principio del
    # todo del archivo) como el texto descriptivo que se muestra cuando
    # alguien ejecuta el script con `--help`. Esto es exactamente la idea
    # de "las herramientas pueden leer de vuelta los docstrings"
    # mencionada al principio de este archivo, en acción.
    # ---------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__)

    # ---------------------------------------------------------------
    # Registrando el indicador `--date`:
    #   "--date"              el nombre del indicador tal como se escribe
    #                          en la línea de comandos (p. ej.
    #                          `--date 2026-08-27`).
    #   default=DEFAULT_DATE   si el usuario no pasa `--date` en
    #                          absoluto, usar este valor en su lugar —
    #                          esto es lo que hace que ejecutar el script
    #                          SIN argumentos siga funcionando, usando la
    #                          fecha fija del conjunto de datos del
    #                          proyecto.
    #   help=...               se muestra en la salida de `--help`,
    #                          explicando qué hace este indicador y cuál
    #                          es su valor por defecto actual.
    # (No se indica ningún `type=` aquí, así que argparse trata el valor
    # como una cadena de texto simple por defecto — que es lo que
    # queremos para una fecha escrita como "YYYY-MM-DD".)
    # ---------------------------------------------------------------
    parser.add_argument(
        "--date",
        default=DEFAULT_DATE,
        help=f"Date in YYYY-MM-DD format (default: {DEFAULT_DATE})",
    )

    # ---------------------------------------------------------------
    # Registrando el indicador `--hour`:
    #   type=int               a diferencia de --date, aquí SÍ
    #                          especificamos un tipo. La entrada de línea
    #                          de comandos siempre llega como texto
    #                          (p. ej. los caracteres "1", "5"), así que
    #                          `type=int` le dice a argparse que la
    #                          convierta en un entero real de Python (15)
    #                          antes de devolvérnoslo — y que lance un
    #                          error claro automáticamente si el usuario
    #                          escribe algo que no sea un entero válido
    #                          (p. ej. `--hour fifteen`).
    #   default=DEFAULT_HOUR    misma idea que antes: recurrir a la hora
    #                          fija del proyecto si no se especifica.
    #   choices=range(0, 24)    restringe los valores válidos a de 0 a 23
    #                          inclusive (range(0, 24) genera
    #                          0,1,2,...,23). Si el usuario pasa algo
    #                          fuera de ese rango, argparse lo rechaza
    #                          automáticamente con un mensaje de error,
    #                          antes de que nuestro propio código llegue
    #                          a ejecutarse — no necesitamos escribir esa
    #                          validación nosotros mismos.
    #   metavar="[0-23]"        puramente cosmético: controla cómo se
    #                          muestra el argumento en el texto de
    #                          `--help`, mostrando "[0-23]" en lugar del
    #                          valor por defecto de argparse (que
    #                          intentaría listar las 24 opciones
    #                          individuales).
    # ---------------------------------------------------------------
    parser.add_argument(
        "--hour",
        type=int,
        default=DEFAULT_HOUR,
        choices=range(0, 24),
        metavar="[0-23]",
        help=f"UTC hour, 0-23 (default: {DEFAULT_HOUR})",
    )

    # ---------------------------------------------------------------
    # parser.parse_args():
    # Lee realmente los argumentos de línea de comandos con los que se
    # lanzó el script (Python los expone internamente vía sys.argv) y
    # devuelve un objeto "Namespace" — piénsalo como un contenedor simple
    # donde cada indicador se convierte en un atributo. Después de esta
    # línea, puedes acceder a `args.date` y `args.hour` como valores
    # normales de Python (un str y un int respectivamente), completamente
    # analizados y validados.
    # ---------------------------------------------------------------
    return parser.parse_args()


########################################################################
# main(): el punto de entrada del script
#
# Por convención, los scripts de Python suelen agrupar su lógica de nivel
# superior en una función llamada `main`, en lugar de escribir esa lógica
# suelta al final del archivo. No es un nombre especial/mágico para el
# propio Python — es simplemente una convención fuerte — pero mantiene la
# lógica de "qué pasa cuando ejecutas este archivo" organizada en un
# único lugar claramente identificado.
########################################################################
def main() -> None:
    # `-> None` en la firma es una anotación de tipo que significa "esta
    # función no devuelve un valor significativo" (solo realiza acciones).

    # Pedirle a parse_args() (definida arriba) que lea y valide los
    # indicadores de línea de comandos, devolviéndonos un Namespace con
    # .date y .hour ya rellenados (ya sea con lo que escribió el usuario,
    # o con los valores por defecto).
    args = parse_args()

    # Llamar a la función download() definida antes, pasándole la fecha y
    # la hora ya analizadas. Nótese que `data_dir` NO se pasa aquí — el
    # valor por defecto de ese parámetro (DATA_DIR) se usa
    # automáticamente, ya que no necesitamos sobreescribirlo en el uso
    # normal.
    download(args.date, args.hour)


########################################################################
# LA PROTECCIÓN `if __name__ == "__main__":`
#
# Todo módulo (archivo) de Python obtiene automáticamente una variable
# integrada llamada `__name__`. Su valor depende de CÓMO se esté usando
# el archivo:
#
#   - Si ejecutas el archivo directamente desde la línea de comandos
#     (`python scripts/download_gharchive.py`), Python fija `__name__` a
#     la cadena "__main__" para ese archivo.
#
#   - Si, en cambio, este archivo se importa desde otro lugar
#     (`import download_gharchive` dentro de otro script), Python fija
#     `__name__` al propio nombre del módulo ("download_gharchive") en
#     lugar de "__main__".
#
# Esta comprobación `if` significa entonces: "solo llamar realmente a
# main() — es decir, solo realizar realmente una descarga — cuando este
# archivo se ejecuta directamente, no cuando simplemente se importa."
#
# ¿Por qué importa esa distinción? Significa que alguien podría escribir
# más adelante un script diferente que haga:
#
#   from download_gharchive import download
#   download("2026-08-20", 9)
#
# ...y reutilizar la función download() para una hora diferente, SIN
# desencadenar la descarga por defecto propia del archivo como efecto
# secundario solo por importarlo. Sin esta protección, importar el
# archivo ejecutaría también main() de inmediato, algo que casi nunca es
# lo que se quiere al importar.
########################################################################
if __name__ == "__main__":
    main()
