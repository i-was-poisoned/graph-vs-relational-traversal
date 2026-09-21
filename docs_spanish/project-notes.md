# Notas del Proyecto: Bases de Datos de Grafos vs. Relacionales

## Tema

Este proyecto investiga una pregunta práctica: **¿a qué profundidad de
recorrido (traversal) y a qué volumen de datos un modelo de grafo de
propiedades supera a un modelo relacional normalizado equivalente para la
misma consulta?**

Las bases de datos relacionales (p. ej. PostgreSQL, MySQL) almacenan los
datos en tablas y expresan las relaciones mediante claves foráneas. Consultar
una relación implica realizar un `JOIN`, y el motor de la base de datos tiene
que calcular ese join en el momento de la consulta, emparejando filas entre
tablas según la igualdad de claves. Para una única relación (p. ej. "buscar
los pedidos de un usuario"), esto es rápido y está muy bien optimizado
gracias a décadas de planificación de consultas relacionales. El problema
aparece con las **consultas de relaciones multi-salto (multi-hop)** — por
ejemplo, "buscar amigos-de-amigos-de-amigos que siguen a una persona que dio
me gusta a una publicación que a mí también me gustó." Cada salto adicional
implica otro `JOIN`, y cada `JOIN` multiplica las filas que el motor tiene
que escanear y emparejar, por lo que el coste tiende a crecer rápidamente
con la profundidad del recorrido.

Las bases de datos de grafos (p. ej. Neo4j, ArangoDB) almacenan las
relaciones como punteros de primera clase, pre-materializados entre nodos
("adyacencia libre de índices" o *index-free adjacency*). Recorrer una
relación implica seguir un puntero directo en lugar de recalcular un join,
por lo que el coste de una consulta multi-salto tiende a escalar con el
tamaño del *subgrafo recorrido*, no con el tamaño de todo el conjunto de
datos. Esta es la base teórica de la afirmación de que las bases de datos de
grafos "ganan" en consultas profundas y con muchas relaciones, mientras que
las bases de datos relacionales suelen ganar (o empatar) en consultas poco
profundas, agregaciones y cargas de trabajo naturalmente tabulares.

La pregunta abierta y específica de este proyecto es *dónde está realmente
el punto de cruce* — a qué profundidad de join y a qué volumen de datos el
coste del enfoque relacional empieza a superar al del enfoque de grafo, para
un esquema y una consulta comparables entre sí. Ese punto de cruce, más que
una afirmación general de "los grafos son mejores", es lo que este proyecto
pretende medir de forma empírica.

## Recursos en Uso

- **Claude AI** — usado como asistente de investigación y redacción:
  explorando la literatura y los conceptos en torno al rendimiento de
  grafos vs. relacional, redactando y revisando código, y ayudando a
  estructurar la documentación.
- **GitHub** — alojamiento remoto del repositorio del proyecto. Provee
  historial de versiones, copia de seguridad y (más adelante) un lugar
  para colaborar o compartir el trabajo.
- **VS Code** — el editor de código local usado para escribir y ejecutar
  el código del proyecto y para gestionar el repositorio git día a día.
- **Overleaf** — usado para redactar el proyecto en LaTeX (p. ej. un
  informe o artículo), separado del repositorio de código.
- **GH Archive** — la fuente del conjunto de datos. Publica volcados por
  hora de cada evento público de GitHub como archivos JSON Lines
  comprimidos con gzip, con relaciones que naturalmente tienen forma de
  grafo (actor → repositorio → evento). La fecha/hora específica que
  usa este proyecto está registrada en el [README](../README.md)
  (se mantiene allí, no aquí, ya que es configuración del proyecto
  crítica para la reproducibilidad, no una nota de aprendizaje). Ver
  [gh-archive-guide.md](gh-archive-guide.md) para una explicación
  completa de qué es GH Archive y cómo funciona.

Para una explicación exhaustiva y desde los primeros principios de qué
son realmente la IA/Claude/un "agente", qué son un IDE/VS Code/una
"extensión", qué es Python y cómo se compara con otros lenguajes, y el
JSON pretty-printed vs. JSON Lines, ver
[tools-and-concepts-guide.md](tools-and-concepts-guide.md).

## Por Qué Importan `.gitignore` y `README.md`

- **`README.md`** es el punto de entrada al proyecto para cualquiera
  (incluido tu yo futuro) que abra el repositorio. Debería explicar qué es
  el proyecto, por qué existe y qué pregunta está respondiendo — el
  `README.md` de este proyecto actualmente indica su pregunta de
  investigación principal desde el principio. Un README claro convierte
  una carpeta de archivos en un proyecto legible.
- **`.gitignore`** le indica a git qué archivos y carpetas *nunca* debe
  rastrear — artefactos de compilación, cachés, entornos virtuales,
  registros (logs), credenciales y otros archivos que son regenerables o
  específicos del entorno. Sin él, estos archivos ensucian el historial de
  commits, aumentan el tamaño del repositorio y corren el riesgo de filtrar
  accidentalmente rutas específicas de la máquina o secretos. También evita
  diffs ruidosos donde archivos generados irrelevantes aparecen como
  "cambios" en cada commit.

## Flujo de Trabajo del Repositorio Hasta Ahora

1. Se creó el repositorio en GitHub primero (remoto).
2. Se clonó localmente con `git clone` en `C:\dev\Research` —
   deliberadamente **fuera** de cualquier carpeta sincronizada con
   OneDrive (p. ej. evitando una ruta que contenga `OneDrive - Pedro`), ya
   que tener OneDrive sincronizando la misma carpeta que gestiona git
   puede provocar conflictos de bloqueo de archivos, alcanzar los límites
   de longitud de ruta de Windows y ralentizar tanto a git como a
   OneDrive. GitHub (remoto) y OneDrive (sincronización local) son
   sistemas no relacionados, pero ambos competirían por los mismos
   archivos locales si el repositorio estuviera dentro de una carpeta de
   OneDrive.
3. En esta etapa, el código se está escribiendo y confirmando (commit)
   localmente; el envío (push) al remoto de GitHub se pospone para más
   adelante.

## Fase de Pruebas

Primero, vayamos a la raíz del proyecto y empecemos a examinar el conjunto
de datos de la hora específica ejecutando:

```bash
python scripts/download_gharchive.py
```

Puntos importantes antes de ejecutar esto:

- **Debes estar dentro de la raíz del proyecto** (`C:\dev\Research`)
  cuando ejecutes este comando. Se ejecuta como
  `scripts/download_gharchive.py` (una ruta relativa), así que la shell
  necesita estar situada en la carpeta que contiene el directorio
  `scripts/` — de lo contrario no encontrará el archivo.
- **Python debe estar en tu PATH.** Esto significa que tu sistema sabe
  dónde vive el programa `python` para poder ejecutarlo por su nombre
  desde cualquier terminal, en lugar de necesitar escribir la ruta
  completa de instalación cada vez. Si ejecutar `python
  scripts/download_gharchive.py` da un error tipo "comando no
  encontrado", prueba con `python3` en su lugar — algunas instalaciones
  solo registran ese nombre. (Esto es distinto de la variable de entorno
  `PYTHONPATH`, que trata sobre dónde busca Python los módulos
  importables, no sobre encontrar el propio ejecutable `python` — algo
  que este script no necesita.)
- El script crea automáticamente una carpeta `data/` en la primera
  ejecución — no hace falta crearla tú mismo. Está excluida de git
  mediante `.gitignore` ya que son datos crudos y regenerables, no
  código del proyecto.
- Una ejecución exitosa muestra el progreso de la descarga y la
  descompresión, terminando con una línea como `Done:
  data/2026-08-27-15.json` — ese archivo es el conjunto de datos
  descomprimido, listo para leerse línea por línea (ver
  [gh-archive-guide.md](gh-archive-guide.md), sección 8).

Nota: la primera ejecución produjo un `HTTP Error 403: Forbidden` del
servidor de GH Archive, causado por el encabezado `User-Agent` por defecto
de `urllib`, que parece un script en lugar de un navegador. Se solucionó
construyendo la petición manualmente con un encabezado `User-Agent` que
imita a un navegador, en lugar de usar `urlretrieve` directamente (ver el
script para la solución y [download_gharchive.py](download_gharchive.py),
la copia anotada, para la explicación completa).

## Flujo de Control de Versiones (git add → commit → push)

Con los scripts de descarga/inspección (download/peek) y la documentación ya
en su lugar, el siguiente paso rutinario fue confirmar (commit) y enviar
(push) este trabajo a GitHub. Los comandos usados, en orden:

```bash
git add .
git commit -m "Exploration stage set up"
git push
```

Este primer push falló con un HTTP 403, porque el inicio de sesión de GitHub
guardado en Windows pertenecía a una cuenta diferente (una cuenta de
trabajo) de la que es dueña de este repositorio. Se solucionó redirigiendo
el remoto a la cuenta correcta sin tocar la credencial de trabajo guardada:

```bash
git remote -v
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
git push -u origin main
```

Consulta [git-commands-guide.md](git-commands-guide.md) para una explicación
completa de qué hace realmente cada uno de estos comandos, el concepto de
área de preparación detrás de `add`/`commit`, y por qué ocurrió la confusión
de cuentas.

## Etapa de Exploración (download_gharchive.py --> peek_data.py)

Ahora que tenemos un conjunto de datos descargado y descomprimido en
formato JSON Lines (`data/2026-08-27-15.json`), el siguiente paso es
observar realmente qué contiene, antes de intentar modelarlo de forma
relacional o como grafo.

`scripts/peek_data.py` lee los primeros eventos del archivo e imprime sus
campos clave (`type`, `actor`, `repo`, `created_at`) — una comprobación
rápida de sanidad para verificar que los datos se ven como lo descrito en
[gh-archive-guide.md](gh-archive-guide.md), antes de escribir cualquier
lógica real de parseo/carga sobre ellos.

Ejecútalo con:

```bash
python scripts/peek_data.py
```

Esto imprime los primeros 5 eventos por defecto. Variantes útiles:

```bash
# Imprimir más eventos
python scripts/peek_data.py --lines 20

# Apuntar a un archivo descargado diferente
python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
```

## Etapa de resumen (summarize_data.py)

Con la forma de un solo evento ya confirmada por `peek_data.py`, el
siguiente paso es hacerse una idea del *volumen y la conectividad* en toda
la hora descargada, antes de elegir un esquema: cuántos eventos, cómo se
reparten por tipo, y cuántos actores/repos distintos están involucrados.

`scripts/summarize_data.py` lee el archivo JSON Lines completo una sola vez
y reporta:

- el número total de eventos
- el desglose por tipo de evento (conteo y porcentaje, del más frecuente al
  menos frecuente)
- el número de actores y repos únicos
- los N actores y repos más activos por número de eventos

Ejecútalo con:

```bash
python scripts/summarize_data.py

# Mostrar más actores/repos más activos
python scripts/summarize_data.py --top 10
```

Para la hora fija del 2026-08-27 15:00 UTC, esto mostró 69.429 eventos
repartidos entre 14.728 actores únicos y 16.497 repos únicos, con
`PushEvent` representando por sí solo el 95,3 % de todos los eventos. Los
actores más activos son todos bots (`github-actions[bot]`,
`dependabot[bot]`, `pull[bot]`, `renovate[bot]`, `cursor[bot]`) — vale la
pena decidir una política de filtrado de bots antes de usar estos datos
para construir los modelos relacional/de grafo, ya que los `PushEvent`
generados por bots dominarían la conectividad medida si no se filtran.

## Qué significa "benchmark" para este proyecto

Antes de seguir, vale la pena ser precisos sobre una palabra que este
proyecto usa constantemente. Un **benchmark** es una prueba justa,
repetible y *cronometrada*, usada para comparar dos o más cosas bajo las
mismas condiciones — no solo "ejecutarlo una vez y ver", sino controlar
deliberadamente todo excepto la única cosa que se mide, para que el
resultado sea una comparación real y no una casualidad causada, por
ejemplo, porque el portátil estaba haciendo otra cosa en segundo plano
durante una de las dos ejecuciones.

Para este proyecto en concreto: un run de benchmark significa tomar la
*misma* consulta multi-salto (p. ej. "empezando desde el actor X,
encontrar todos los repos alcanzables en 3 saltos") y ejecutarla contra la
base de datos relacional y contra la base de datos de grafo, sobre los
*mismos* datos subyacentes, cronometrando cuánto tarda cada una. Eso se
repite en distintas profundidades de salto y volúmenes de datos para
encontrar el punto de cruce que plantea el README.

## Principio de diseño del esquema: la consulta primero, no los campos

Un atajo tentador sería mirar cada campo que provee GH Archive y construir
una tabla o un tipo de nodo para cada uno. Ese es el orden equivocado. El
diseño del esquema para un benchmark debe estar guiado por la *consulta*
que se está probando, no por "los campos que resultan existir":

- **Campos primero** significa recorrer los datos, ver campos como
  mensajes de commit, texto de revisiones de PR, y etiquetas de issues, y
  modelizarlo todo. Esto produce un esquema grande y detallado — la mayor
  parte del cual el benchmark de recorrido nunca llega a tocar realmente.
- **Consulta primero** significa decidir *primero* exactamente qué se está
  midiendo (para este proyecto: un recorrido `actor → repo → actor →
  repo` — ver más abajo por qué tiene que tener esa forma, y no una arista
  directa actor-a-actor), y luego construir solo la estructura mínima que
  ese recorrido necesita: una cosa Actor, una cosa Repo, y una conexión
  entre ambas.

Por qué importa esto más allá de la prolijidad: tablas/columnas (o tipos
de nodo/arista) adicionales y sin usar no hacen que ninguno de los dos
lados de la comparación sea "más correcto" — solo añaden complejidad que
no forma parte de la medición. Peor aún, si ese detalle adicional se
construye de forma desigual (más del lado relacional que del lado de
grafo, o viceversa), la comparación deja de ser equivalente, que es
precisamente el objetivo de la pregunta de investigación de este proyecto.

## Etapa de diseño del esquema (profile_schema.py)

Los datos son intrínsecamente **bipartitos**: cada evento conecta un
`actor` con un `repo` (ver
[gh-archive-guide.md](gh-archive-guide.md#actores-repos-y-eventos) para la
distinción completa actor/repo/evento). Eso significa que un "recorrido
multi-salto" aquí no puede ser el ejemplo clásico de amigos-de-amigos de
la pregunta de investigación inicial de este proyecto — no hay una arista
directa actor-a-actor en los datos crudos por defecto. Un recorrido tiene
que alternar `actor → repo → actor → repo`, saltando a través de *repos
compartidos* (o, cuando esté disponible, a través de un segundo actor
nombrado dentro del `payload` de un evento).

Para diseñar bien ese esquema — siguiendo el principio de "consulta
primero" de arriba — el siguiente paso fue averiguar *dónde en los datos
aparece realmente un segundo actor*, porque sin eso, no hay a dónde saltar
más allá de "otro repo que ese mismo actor tocó". `scripts/profile_schema.py`
lee el archivo completo y reporta, por tipo de evento:

- qué campos de `payload` existen, con qué frecuencia, y de qué tipo son
- cualquier objeto anidado con la forma de una referencia a un usuario de
  GitHub (`{"id": ..., "login": "..."}`) encontrado en cualquier parte
  dentro de `payload`, y la ruta para llegar a él (p. ej.
  `payload.pull_request.user`)

Ejecútalo con:

```bash
python scripts/profile_schema.py

# Centrarse en un solo tipo de evento
python scripts/profile_schema.py --type PushEvent
```

**Hallazgo clave:** `PushEvent` — el 95,3 % de todos los eventos de la
hora fija de este proyecto — no lleva ningún segundo actor en ninguna
parte de su payload; solo tiene `ref`, `before`/`head` (SHA de commits), y
`repository_id`. El `payload.pull_request` de `PullRequestEvent` también
es una referencia recortada que omite al autor del PR (a diferencia de la
respuesta completa de la API REST de GitHub). Las referencias reales a un
segundo actor viven casi por completo en el ~4,7 % de eventos restante —
comentarios, revisiones, issues, releases, forks, y cambios de membresía
(desglose completo en
[gh-archive-guide.md](gh-archive-guide.md#dónde-aparece-un-segundo-actor-referencias-anidadas)).
Esto moldea directamente la decisión de esquema: una arista actor-a-actor,
si se modela, será escasa y proveniente de una pequeña porción de los
tipos de evento — la mayor parte de la conectividad del grafo vendrá de
las propias aristas actor→repo (muchos actores compartiendo un repo), no
de enlaces directos actor→actor.

El pipeline general hasta ahora es: **download_gharchive.py →
peek_data.py → summarize_data.py → profile_schema.py** — primero obtener
y descomprimir la hora fija del conjunto de datos, luego inspeccionar un
puñado de eventos en bruto, después obtener una lectura agregada del
volumen y la conectividad, luego perfilar la forma del payload y localizar
referencias a un segundo actor, antes de pasar a extraer y cargar
realmente los registros en los modelos relacional y de grafo que se están
comparando.
