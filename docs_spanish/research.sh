#!/usr/bin/env bash
########################################################################
# COPIA ANOTADA — solo con fines de aprendizaje.
#
# Este es un duplicado explicado línea por línea de research.sh (en la
# carpeta del proyecto). NO está pensado para ejecutarse — vive en
# docs_spanish/ porque su propósito es enseñar, no ejecutarse. (Ni
# siquiera funcionaría desde aquí: busca run.sh y scripts/ junto a sí
# mismo.) El archivo real y "limpio" (sin nada de este comentario) es
# research.sh.
#
# La línea de encima de este recuadro es la primera línea del original,
# que se mantiene la primera a propósito (ver "el shebang" justo debajo).
# Aparte de estas líneas de comentario añadidas, todas las líneas son
# idénticas a las del original.
#
# Qué leer antes: research.sh llama a run.sh, que no tiene copia anotada
# pero es corto y está comentado — lee el propio run.sh. Es útil comparar
# los dos (ver "research.sh frente a run.sh" más abajo). Para lo que
# hacen los pasos de Python, ver docs_spanish/check_connections.py,
# docs_spanish/measure.py (la medición en sí) y
# docs_spanish/choose_starts.py (la lista de bases de datos, y cómo se
# eligen los actores de partida).
#
# Lo que es NUEVO aquí: este es el primer script de BASH del proyecto
# explicado línea por línea. Es el único punto de entrada de la
# investigación: un solo comando comprueba los servidores, pregunta qué
# base de datos medir y ejecuta measure.py sobre ella, deteniéndose en el
# primer paso que falle. Cada medición escribe UN archivo CSV propio en
# results/, cuyo nombre lleva la base de datos y el momento en que
# empezó. Conceptos de bash que se explican: el shebang,
# set -eo pipefail, cd "$(dirname "$0")", un bucle sobre los argumentos
# con case / shift, los arrays, mapfile con sustitución de procesos,
# tr -d '\r', read -p, y una comprobación con una expresión regular con
# [[ =~ ]].
#
# Toda la investigación, en tres comandos:
#     ./run.sh scripts/drop_databases.py   (opcional: empezar desde cero)
#     ./run.sh scripts/build_hours.py      (una base de datos por volumen de datos)
#     ./research.sh                        (este archivo: medir una de ellas)
#
# Cómo ejecutar el archivo real (desde Git Bash, en la carpeta del
# proyecto, con PostgreSQL en marcha y Neo4j Desktop abierto):
#     ./research.sh
#     ./research.sh --database gharchive-2026-10-08-9-24h
#     ./research.sh --new-starts
########################################################################

# ---------------------------------------------------------------------
# El shebang: #!/usr/bin/env bash  (la primerísima línea del archivo)
#
# "#!" justo al principio de un archivo le dice al sistema QUÉ PROGRAMA
# debe leer el resto cuando ejecutas el archivo directamente como
# ./research.sh. /usr/bin/env bash significa "busca bash donde esté
# instalado y úsalo". Para el propio bash es solo un comentario (empieza
# por #).
#
# research.sh frente a run.sh
#   run.sh       un LANZADOR genérico: prepara el entorno (.venv, las
#                contraseñas de secrets.sh) y después se convierte en
#                `python <script>`. Ejecuta UN script de Python.
#   research.sh  un ORQUESTADOR: nunca toca .venv ni las contraseñas por
#                sí mismo. Llama a ./run.sh una vez por paso (y una vez
#                para la lista de bases de datos); cada llamada tiene su
#                propio entorno, que desaparece cuando termina ese paso.
# Los dos empiezan con las mismas tres líneas: shebang, set -eo pipefail,
# cd.
# ---------------------------------------------------------------------
# Run the research for one database:
#     0. check that both servers answer
#     1. ask which database to measure (unless --database is given)
#     2. measure.py: choose (or reuse) the starting actors, measure the traversal in
#        PostgreSQL and Neo4j, and write the results to one CSV file in results/
#
# Usage (from Git Bash, with PostgreSQL running and Neo4j Desktop open):
#     ./research.sh                                     # asks which database to measure
#     ./research.sh --database gharchive-2026-10-08-9-24h
#     ./research.sh --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
#     ./research.sh --new-starts                        # choose the starting actors again
#
# The work is done by the Python scripts; this file only runs them in order,
# asks the one question, and stops at the first step that fails.

# ---------------------------------------------------------------------
# set -eo pipefail — PARAR EN EL PRIMER FALLO
#
# Por defecto, bash sigue con la línea siguiente aunque un comando falle.
# Aquí eso sería malo: si los servidores no respondieran, el script
# seguiría adelante igualmente, haría una pregunta y después intentaría
# medir.
#   -e         salir en cuanto un comando falle (termine con un código de
#              salida distinto de cero — p. ej. un script de Python que
#              llama a sys.exit(1), ver docs_spanish/check_connections.py).
#   -o pipefail
#              en una TUBERÍA (pipe) `a | b`, la tubería cuenta como
#              fallida si falla CUALQUIERA de sus partes. Sin esto, solo
#              cuenta el resultado del último comando, así que
#              `comando_que_falla | tr ...` parecería un éxito.
#
# cd "$(dirname "$0")" — TRABAJAR DESDE LA CARPETA DEL PROYECTO
#   $0             la ruta con la que se arrancó este script, p. ej.
#                  ./research.sh o /c/dev/Research/research.sh
#   dirname ...    se queda solo con la parte de la carpeta: . o
#                  /c/dev/Research
#   $( ... )       SUSTITUCIÓN DE COMANDOS: ejecuta el comando de dentro y
#                  pone su salida en su lugar.
#   las comillas   mantienen en una sola pieza un nombre de carpeta con
#                  espacios.
# Así, estés en la carpeta que estés al arrancarlo, el script se mueve a
# su propia carpeta, y las rutas como ./run.sh y scripts/... funcionan.
# ---------------------------------------------------------------------
set -eo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------
# Variables y un ARRAY
#
# DATABASE=""          una variable, vacía por ahora. En bash NO puede
#                      haber espacios alrededor del = (DATABASE = ""
#                      fallaría).
# MEASURE_OPTIONS=()   un ARRAY: una lista de textos separados, vacía por
#                      ahora. Irá recogiendo las opciones destinadas a
#                      measure.py, p. ej. (--max-depth 4 --timeout 60).
# ¿Por qué un array y no un solo texto? Cada elemento sigue siendo un
# argumento separado cuando se pasa, aunque contenga espacios.
# ---------------------------------------------------------------------
DATABASE=""
MEASURE_OPTIONS=()
# ---------------------------------------------------------------------
# EL BUCLE DE ARGUMENTOS: while / case / shift
#
# $#  el número de argumentos que quedan; $1, $2 el primero y el segundo.
#   ./research.sh --database X --repeats 5
#     -> $# = 4, $1 = --database, $2 = X
#
# while [ $# -gt 0 ]; do ... done
#   repetir mientras queden argumentos (-gt: "greater than", mayor que;
#   [ ] es una comprobación, y necesita los espacios dentro de los
#   corchetes).
#
# case "$1" in ... esac — compara $1 con varios patrones, como una cadena
# de if/elif. Cada rama es `patrón) comandos ;;`
#   --database)        guarda el argumento siguiente como nombre de la
#                      base de datos.
#   --max-depth|--repeats|--timeout|--cypher)
#                      `|` significa O. Estas cuatro no las usa el propio
#                      research.sh: se añaden al array, la opción Y su
#                      valor, para pasárselas más tarde a measure.py.
#                      += ( ... ) añade elementos a un array.
#                      (--cypher elige qué versión o versiones de Cypher
#                      medir: paths, levels o both; ver
#                      docs_spanish/traversal.py.)
#   --new-starts)      un INTERRUPTOR: una opción SIN valor. Solo la
#                      propia opción entra en el array, y `shift`
#                      (= shift 1) descarta solo ese argumento. Le dice a
#                      measure.py que vuelva a elegir los actores de
#                      partida en lugar de reutilizar los de la última
#                      medición de esa base de datos
#                      (ver docs_spanish/measure.py, previous_starts).
#   *)                 `*` coincide con cualquier otra cosa: una opción
#                      desconocida. El mensaje va a la salida de ERRORES
#                      (>&2: "envía esto al flujo 2", stderr) y exit 1 se
#                      detiene con un fallo.
#
# shift 2 — descarta los dos primeros argumentos ($1 y $2): lo que era $3
# pasa a ser $1, y $# baja en 2. Así es como avanza el bucle, de dos en
# dos (una opción y su valor) — o de uno en uno en el caso de un
# interruptor.
# ---------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --database) DATABASE="$2"; shift 2 ;;
        --max-depth|--repeats|--timeout|--cypher) MEASURE_OPTIONS+=("$1" "$2"); shift 2 ;;
        --new-starts) MEASURE_OPTIONS+=("$1"); shift ;;
        *) echo "Unknown option: $1 (see the top of research.sh)" >&2; exit 1 ;;
    esac
done

# Paso 0: check_connections.py (docs_spanish/check_connections.py). Si un
# servidor no está en marcha, sale con 1 y, gracias a set -e, la
# investigación se detiene aquí — antes de preguntar nada o de medir nada.
echo "== 0. Check that both servers are answering"
./run.sh scripts/check_connections.py

# ---------------------------------------------------------------------
# NO SE HA INDICADO --database: PREGUNTAR CUÁL
#
# [ -z "$DATABASE" ] — verdadero si la variable está vacía (-z: "zero
# length", longitud cero).
# ---------------------------------------------------------------------
if [ -z "$DATABASE" ]; then
    # -----------------------------------------------------------------
    # mapfile -t DATABASES < <( ... )
    #
    # choose_starts.py --list-databases imprime las bases de datos que
    # existen en LOS DOS lados, una por línea (ver
    # docs_spanish/choose_starts.py). Esta línea mete esas líneas en un
    # array:
    #   mapfile -t NOMBRE  lee líneas de su entrada y las guarda en el
    #                      array NOMBRE, un elemento por línea; -t quita
    #                      el salto de línea del final de cada una.
    #   < <( comando )     SUSTITUCIÓN DE PROCESOS: <( comando ) ejecuta
    #                      el comando y hace que su salida parezca un
    #                      archivo; el primer < le pasa ese "archivo" a
    #                      mapfile. (¿Por qué no `comando | mapfile`? Cada
    #                      lado de una tubería se ejecuta en una copia
    #                      aparte del shell, así que el array
    #                      desaparecería al terminar la tubería.)
    #
    # | tr -d '\r' — FINALES DE LÍNEA DE WINDOWS
    #   En Windows, Python termina las líneas que imprime con "\r\n"
    #   (retorno de carro + salto de línea), mientras que bash espera solo
    #   "\n". mapfile -t quita el \n, pero el \r invisible se quedaría
    #   pegado a cada nombre, y "gharchive-...-6h\r" no es una base de
    #   datos que exista. tr -d '\r' ("translate: delete", traducir:
    #   borrar) elimina todos los caracteres \r.
    # -----------------------------------------------------------------
    mapfile -t DATABASES < <(./run.sh scripts/choose_starts.py --list-databases | tr -d '\r')
    # ${#DATABASES[@]} — el número de elementos del array. -eq: "equals",
    # igual a. Ninguno: no hay nada que medir; decir qué ejecutar antes.
    if [ ${#DATABASES[@]} -eq 0 ]; then
        echo "There's no database to measure yet. Load one first: ./run.sh scripts/build_hours.py" >&2
        exit 1
    fi
    echo ""
    echo "Databases you can measure:"
    # -----------------------------------------------------------------
    # Un menú numerado.
    #   "${!DATABASES[@]}"   los ÍNDICES del array: 0 1 2 ... (el ! pide
    #                        las posiciones, no los valores)
    #   ${DATABASES[$i]}     el elemento de la posición i
    #   $((i + 1))           ARITMÉTICA: bash calcula i + 1, para que el
    #                        menú empiece en 1 y no en 0, como cuenta la
    #                        gente.
    # -----------------------------------------------------------------
    for i in "${!DATABASES[@]}"; do
        echo "  $((i + 1))) ${DATABASES[$i]}"
    done
    # -----------------------------------------------------------------
    # read -r -p "pregunta " CHOICE
    #   Muestra la pregunta (-p: "prompt") y espera a que escribas algo y
    #   pulses Intro; lo que hayas escrito va a CHOICE.
    #   -r conserva las barras invertidas tal como se escriben (siempre es
    #   un buen hábito con read).
    # -----------------------------------------------------------------
    read -r -p "Which one? (number) " CHOICE
    # -----------------------------------------------------------------
    # COMPROBAR LA RESPUESTA antes de usarla.
    #
    # [[ "$CHOICE" =~ ^[0-9]+$ ]] — una comprobación con una EXPRESIÓN
    # REGULAR (la forma [[ ]] de bash; =~ significa "coincide con el
    # patrón"):
    #   ^       el principio del texto
    #   [0-9]+  uno o más dígitos
    #   $       el final del texto
    # es decir, "solo dígitos, nada más". El `!` delante lo invierte: "NO
    # es un número". Esta comprobación va primero porque -lt / -gt, más
    # adelante, darían un error si CHOICE fuera, por ejemplo, "abc".
    #
    # || significa O, entre tres comprobaciones: no es un número, O es
    # menor que 1 (-lt: "less than", menor que), O es mayor que el número
    # de bases de datos. Si se cumple cualquiera: rechazar, sin hacer nada.
    # -----------------------------------------------------------------
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#DATABASES[@]} ]; then
        echo "Not a number from the list; nothing done." >&2
        exit 1
    fi
    # El menú mostraba 1, 2, 3..., el array cuenta 0, 1, 2...: de ahí el - 1.
    DATABASE="${DATABASES[$((CHOICE - 1))]}"
fi

# ---------------------------------------------------------------------
# LA MEDICIÓN, a través de run.sh.
#
# measure.py se encarga de todo lo demás: elige (o reutiliza) los actores
# de partida, mide el recorrido en los dos lados y escribe UN archivo CSV
# para esta medición, results/<base de datos>_<fecha>_<hora>.csv (una
# línea = una pregunta respondida por las dos bases de datos; las
# columnas se explican en el README y en docs_spanish/measure.py). Un
# análisis = un archivo, fácil de abrir y de entender por sí solo.
#
# "$DATABASE" va siempre entre comillas dobles: el valor se pasa como UN
# solo argumento, tal cual. \" dentro de "..." imprime un carácter "
# literal.
#
# "${MEASURE_OPTIONS[@]}" — se expande a todos los elementos del array,
# CADA UNO como un argumento separado: --max-depth 4 --timeout 60. Si el
# array está vacío no se expande a nada, y measure.py usa sus propios
# valores por defecto.
#
# Gracias a set -e, si measure.py falla, la línea "Done" no se muestra
# nunca.
# ---------------------------------------------------------------------
echo ""
echo "== 1. Measure \"$DATABASE\""
./run.sh scripts/measure.py --database "$DATABASE" "${MEASURE_OPTIONS[@]}"

echo "Done. The results are in results/ (one CSV per measurement; its columns are explained in the README)."
