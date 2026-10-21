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

### `README.md`: la puerta de entrada al proyecto

Un archivo `README.md` es, en esencia, un documento de texto con
formato — y el `.md` es la clave para entender qué es realmente. `.md`
significa **Markdown**: un lenguaje de marcado ligero (no un lenguaje de
programación) que te deja escribir texto con formato — títulos, **negrita**,
*cursiva*, listas, enlaces, bloques de código — usando solo símbolos
sencillos de teclado (`#` para un título, `**...**` para negrita,
`` `...` `` para código en línea) en lugar de necesitar un editor visual
tipo Word. Escribes el texto plano con esos símbolos, y cualquier programa
que "entienda" Markdown (GitHub, VS Code, este mismo documento) lo
convierte en texto formateado y bonito al mostrarlo. Todos los `.md` de
este proyecto (este mismo `project-notes.md`, el `README.md`, la
`gh-archive-guide.md`) están escritos en Markdown por esta razón: es
legible incluso como texto plano sin procesar, y se renderiza bien en
cualquier sitio que lo entienda.

`README` (en mayúsculas, sin extensión ni con `.md`/`.txt`) es, además,
una **convención** muy antigua en el mundo del software: por tradición,
es el primer archivo que alguien nuevo en un proyecto debería leer
("LÉEME"). GitHub (y GitLab, Bitbucket, y casi cualquier otro alojador de
repositorios) construye sobre esa convención de forma automática: si un
repositorio contiene un archivo llamado `README.md` (o `README`,
`README.txt`, etc.) en su carpeta raíz, la plataforma lo detecta y lo
muestra ya renderizado, justo debajo de la lista de archivos, en la
página principal del repositorio. Esto no es una función especial de
git en sí — git no le da ningún trato especial a ningún archivo llamado
`README`; es puramente un comportamiento que GitHub (y plataformas
similares) añaden por encima de git, basándose en ese nombre de archivo
convencional. Por eso un `README.md` bien escrito es tan valioso: es
literalmente lo primero que ve cualquiera (incluido tu propio yo, dentro
de seis meses, sin memoria fresca del proyecto) al visitar el
repositorio, así que debería responder de inmediato "¿qué es esto, por
qué existe, y qué pregunta intenta responder?" — que es exactamente lo
que hace el `README.md` de este proyecto con su pregunta de investigación
en la parte superior.

### `.gitignore`: qué significa "rastrear" en git, y por qué hace falta decirle qué ignorar

Para entender `.gitignore`, primero hace falta entender que git no ve
automáticamente cada archivo de tu carpeta como "parte del proyecto".
Cuando trabajas en un repositorio, cada archivo está en uno de estos
estados:

- **Sin rastrear (untracked)** — git ve que el archivo existe en la
  carpeta, pero nunca se le ha dicho que lo vigile; no forma parte del
  historial del proyecto y `git status` lo señala como "nuevo".
- **Preparado / en el área de staging (staged)** — con `git add`, le
  dices a git "quiero que este archivo, en su estado actual, forme parte
  del próximo commit".
- **Confirmado (committed)** — con `git commit`, ese estado preparado
  queda guardado permanentemente en el historial del repositorio.

Sin un `.gitignore`, cada archivo nuevo que aparece en la carpeta —
incluidos los que Python genera automáticamente, como los cachés de
`__pycache__/`, o los datos descargados en `data/` — aparece como "sin
rastrear" en `git status`, y un `git add .` descuidado lo arrastraría al
próximo commit sin que te dieras cuenta. `.gitignore` es, literalmente,
una lista de patrones de nombres de archivo/carpeta que le dice a git
"ni siquiera me muestres estos como 'sin rastrear'; ignóralos por
completo". Usa patrones tipo comodín (*wildcard*) — por ejemplo, en el
`.gitignore` real de este proyecto:

- `/data/` — ignora toda la carpeta `data/` (la barra inicial la fija a la
  raíz del proyecto, no a cualquier carpeta `data/` en cualquier nivel).
- `__pycache__/` — ignora cualquier carpeta llamada así, en cualquier
  parte del proyecto (sin la barra inicial, aplica a todos los niveles).
- `*.py[codz]` — el `*` es un comodín que significa "cualquier texto
  aquí"; esto ignora archivos como `algo.pyc`, `algo.pyo`, etc.
- Líneas que empiezan con `#` son comentarios, solo para humanos —
  git los ignora al analizar el archivo.

¿Por qué molestarse en excluir estos archivos en lugar de simplemente no
hacer `git add` de ellos a mano cada vez? Porque sin `.gitignore`, esos
archivos **regenerables** o **específicos de la máquina** (cachés de
compilación, entornos virtuales, credenciales, archivos de configuración
del sistema operativo o del editor) ensuciarían el historial de commits,
inflarían el tamaño del repositorio con contenido que no aporta nada
útil para nadie más, y — el riesgo más serio — podrían filtrar
accidentalmente rutas propias de tu máquina o, peor, secretos como
contraseñas o claves de API si alguna vez terminan en un archivo que se
sube sin querer. `.gitignore` automatiza esa disciplina de una vez, en
lugar de depender de que un humano recuerde nunca cometer ese error.

### Compilación: de código fuente a código máquina

Para entender por qué tantas de las líneas del `.gitignore` de este
proyecto tienen que ver con "artefactos de compilación", primero hace
falta entender qué es realmente **compilar**.

Un procesador de ordenador (la CPU) no entiende Python, ni C, ni ningún
otro lenguaje de programación tal como los escribe un humano — solo
entiende un conjunto muy limitado y muy específico de instrucciones
binarias (secuencias de unos y ceros) llamado **código máquina**,
propio de cada arquitectura de procesador. El **código fuente** que
escribimos (legible, con nombres de variables, comentarios, estructura)
existe exclusivamente para que los humanos podamos leerlo y razonar
sobre él; el ordenador, tal cual, no puede ejecutarlo directamente.

Un **compilador** es un programa cuyo único trabajo es traducir código
fuente, escrito en un lenguaje de alto nivel, a código máquina (u otra
representación intermedia) antes de que el programa se ejecute. Ese
proceso de traducción se llama **compilar** (o "hacer un *build*"), y el
resultado — el archivo o los archivos ya traducidos — son lo que se
llama, en general, un **artefacto de compilación** (ver la siguiente
sección). En lenguajes compilados como C o Rust, este paso ocurre de
forma explícita, una sola vez, antes de ejecutar el programa; el
resultado es un archivo ejecutable independiente.

Python, como ya cubre
[tools-and-concepts-guide.md](tools-and-concepts-guide.md#33-lenguajes-compilados-vs-interpretados)
con más detalle, es un lenguaje **interpretado**: no compilas
manualmente los scripts de este proyecto antes de ejecutarlos — se
ejecutan directamente con `python scripts/peek_data.py`. Pero, detrás de
escena, el propio intérprete de Python igualmente compila cada archivo
`.py` a una forma intermedia llamada **bytecode** (instrucciones más
simples que el código Python original, aunque todavía no código máquina
puro) la primera vez que se importa o ejecuta, y guarda ese bytecode en
caché en archivos `.pyc` dentro de una carpeta `__pycache__/`, para no
tener que repetir ese trabajo de traducción en cada ejecución futura si
el archivo fuente no ha cambiado. Esos archivos `.pyc` son, exactamente,
un artefacto de compilación — solo que generado automáticamente por
Python mismo, en segundo plano, en lugar de por un paso manual de build.

### ¿Qué es un "artefacto" (*build artifact*)?

Un **artefacto de compilación** (o simplemente "artefacto", *build
artifact* o *build output*) es cualquier archivo que se **genera** a
partir del código fuente mediante algún proceso automático — compilar,
empaquetar, minimizar, renderizar — en lugar de haber sido escrito a
mano por una persona. La distinción clave para este proyecto es:

- El **código fuente** (los archivos `.py` en `scripts/`, los `.md` en
  `docs_*/`) es la **única fuente de verdad** — lo que una persona
  realmente escribió y lo único que realmente hace falta guardar en el
  historial del proyecto.
- Un **artefacto** es *derivado* de ese código fuente — siempre se puede
  volver a generar ejecutando el mismo proceso sobre el mismo código
  fuente, así que guardarlo en git es, en el mejor de los casos,
  redundante, y en el peor, activamente perjudicial.

Ejemplos de artefactos de compilación más allá de los `.pyc` de Python ya
mencionados (para tener el concepto bien generalizado, no solo atado a
este proyecto): un archivo `.exe` o `.dll` compilado a partir de código
C/C++; un `.jar` compilado a partir de código Java; el HTML/CSS/
JavaScript final "empaquetado" (*bundled*) y minimizado que produce una
herramienta de build de una aplicación web moderna a partir de su código
fuente; un archivo `.whl` (*wheel*) que empaqueta una librería de Python
lista para instalar; incluso la documentación HTML generada
automáticamente a partir de comentarios en el código fuente.

Por qué casi nunca se comitean artefactos a un repositorio git (y por
qué el propio `.gitignore` de este proyecto excluye tantos de ellos —
`__pycache__/`, `*.py[codz]`, `build/`, `dist/`, `*.egg-info/`, entre
otros):

1. **Son regenerables.** Si el código fuente está en el repositorio,
   cualquiera puede regenerar el artefacto exacto en cualquier momento —
   guardarlo también sería duplicar información sin necesidad.
2. **A menudo son específicos del entorno.** Un `.pyc` compilado con la
   versión de Python instalada en esta máquina (Python 3.14, según
   aparece en las rutas de `__pycache__/` de este proyecto) podría no
   funcionar igual, o ni siquiera cargarse, en la máquina de otra
   persona con una versión distinta de Python.
3. **Ensucian el historial y los diffs.** Los artefactos suelen ser
   archivos binarios (no texto legible línea a línea), así que git no
   puede mostrar diffs útiles línea por línea para ellos como sí hace
   con código fuente — cada cambio aparece como "el archivo cambió por
   completo", sin ninguna información de qué cambió realmente.
4. **Inflan el tamaño del repositorio** con contenido que no aporta
   nada al entendimiento del proyecto — nadie necesita leer un `.pyc`
   para entender qué hace `peek_data.py`; el `.py` ya se lo dice.

(Nota aparte, para que el panorama quede completo: hay excepciones
deliberadas a esta regla general — por ejemplo, cuando un proyecto
*publica* un artefacto final terminado, como adjuntar un ejecutable
compilado a un "Release" de GitHub para que la gente lo descargue
directamente, sin tener que compilar el código fuente ellos mismos. Eso
es distinto de comitear el artefacto al *historial de commits* del
repositorio, que es lo que `.gitignore` está evitando aquí.)

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

`scripts/peek_data.py` ([copia anotada](peek_data.py)) lee los primeros eventos del archivo e imprime sus
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

`scripts/summarize_data.py` ([copia anotada](summarize_data.py)) lee el archivo JSON Lines completo una sola vez
y muestra tres secciones:

1. **General:** el total de eventos, de actores únicos y de repos únicos,
   cada uno separado en bots y no bots (incluido cuántos repos *solo*
   tuvieron eventos de bots).
2. **Análisis con bots:** todos los eventos.
3. **Análisis sin bots:** el mismo análisis, quitando todas las cuentas
   cuyo login termina en `[bot]`.

Las secciones 2 y 3 muestran exactamente lo mismo, para poder compararlas
una al lado de la otra:

- el desglose por tipo de evento (conteo y porcentaje, del más frecuente al
  menos frecuente)
- los N actores y repos más activos por número de eventos
- la conectividad: cuántos repos tienen 2 o más actores diferentes, cuántos
  actores han hecho eventos en 2 o más repos, y cuántos actores comparten
  un repo con al menos otro actor
- los N actores que han hecho eventos en más repos *diferentes*, y los N
  repos con más actores *diferentes*

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

**Únicos vs. total — cómo leer estas cifras.** "Actores únicos" y "total de
eventos" responden a preguntas distintas. Si `ana` hace 3 eventos y `luis`
hace 2, hay 5 eventos pero solo 2 actores únicos. El script lleva un
`Counter` por cada cosa que cuenta — un diccionario *nombre → número de
eventos* — y `len()` de ese diccionario da el número de nombres
*distintos*, mientras que sumar todos sus valores volvería a dar el total
de eventos (la [copia anotada](summarize_data.py) lo explica con un ejemplo
concreto). La diferencia importa en este proyecto porque los actores únicos
y los repos únicos son lo que se convertirá en los **nodos** del grafo (y
en las filas de las tablas Actor y Repo) — unos 14,7k + 16,5k ≈ 31k nodos
para esta hora — mientras que los eventos son lo que los *conecta*. De
media, cada actor produjo unos 4,7 eventos (69.429 ÷ 14.728), pero esa
media esconde un reparto muy desigual, con bots en lo más alto de la lista;
por eso la decisión sobre filtrar bots de arriba afecta directamente a lo
conectado que estará el grafo.

### Resultados de conectividad: con y sin bots

Contar eventos y nombres únicos no basta para saber si los datos sirven
para el benchmark. El benchmark recorre `actor → repo → actor → repo`, y
cada paso de un repo a *otro* actor solo es posible si ese repo lo han
tocado al menos dos actores distintos. Por eso `summarize_data.py` también
mide la conectividad, una vez con todos los eventos y otra sin las cuentas
cuyo login termina en `[bot]`:

| Medida | Todos los eventos | Sin bots |
|---|---|---|
| Eventos | 69.429 | 67.459 (1.970 eventos de bots eliminados, 2,8 %) |
| Actores únicos | 14.728 | 14.515 (213 actores bot eliminados, 1,4 %) |
| Repos únicos | 16.497 | 14.995 (1.502 repos que solo tuvieron eventos de bots eliminados, 9,1 %) |
| Repos con 2+ actores distintos | 145 (0,9 % de los repos) | 49 (0,3 %) |
| Actores que tocaron 2+ repos | 256 (1,7 % de los actores) | 211 (1,5 %) |
| Actores que comparten un repo con otro actor | 234 (1,6 % de los actores) | 101 (0,7 %) |

**Conclusiones:**

1. **Los push dominan.** `PushEvent` es el 95,3 % de todos los eventos (el
   96,3 % sin bots). Los tipos de evento que *podrían* conectar
   directamente a dos personas (comentarios, revisiones, issues) suman
   alrededor del 1 %, y solo el 0,26 % de los eventos nombra de verdad a
   una segunda persona, distinta del actor. Las
   conexiones entre actores vendrán casi siempre de *repos compartidos*,
   lo que coincide con lo que encontró `profile_schema.py` (ver la etapa
   de diseño del esquema más abajo).
2. **Que haya más repos que actores significa que algunos actores tocan
   varios repos.** Si cada actor hubiera tocado un solo repo, habría como
   mucho tantos repos como actores. Hay más repos (16.497 frente a
   14.728), así que algunos actores tienen que haber trabajado en varios
   — pero solo el 1,7 % lo hizo.
3. **El grafo está extremadamente fragmentado.** El 99 % de los repos lo
   tocó un único actor, y alrededor del 98 % de los actores no comparte
   ningún repo con nadie. El evento típico es una persona haciendo push a
   su propio repo. El repo más "compartido" tiene 12 actores distintos con
   bots, y solo 4 sin ellos. Para un benchmark de recorridos este es el
   resultado clave: la mayoría de los recorridos se pararían después del
   primer salto.
4. **Los bots pesan poco en volumen pero mucho en conectividad.** Los bots
   son solo el 2,8 % de los eventos, pero `github-actions[bot]` por sí solo
   toca 785 repos distintos. Al quitar los bots desaparecen unas dos
   terceras partes de los repos compartidos (145 → 49) y más de la mitad
   de los actores conectados (234 → 101): la mayoría de las conexiones de
   esta hora vienen de bots. Actúan
   como centros artificiales que unen repos que no tienen nada que ver
   entre sí. Un benchmark con estos datos mediría sobre todo "todo se
   conecta a través de github-actions", así que los bots deben quedar
   fuera de los datos del benchmark.
5. **El filtro `[bot]` no es completo.** Algunas cuentas automáticas no
   usan ese sufijo: `Copilot` toca 41 repos. Y sin bots, las cuentas más
   activas tienen nombres que parecen generados (`beckjulie09`,
   `hayeshenry6`, ...), cada una haciendo entre 35 y 39 push a su propio
   repo con un nombre aleatorio (`hpmxym`, `eznfko`, ...): probablemente
   cuentas automáticas o spam. No añaden conexiones (cada una solo toca su
   propio repo), pero sí inflan el volumen de eventos.

**Qué significa esto para el proyecto:**

- **Una hora de datos no basta para un benchmark de varios saltos.** Con
  solo unos 100 actores conectados una vez quitados los bots, un recorrido
  de 3 o 4 saltos casi no tiene adónde ir. El siguiente paso es descargar
  más horas (por ejemplo, un día completo o varios días) y volver a
  ejecutar `summarize_data.py` para ver si crece el número de repos
  compartidos. La pregunta de investigación también trata del *volumen*
  de datos, así que de todas formas harán falta varios tamaños de datos.
- **Política sobre bots:** excluir las cuentas `[bot]` de los datos del
  benchmark, y plantearse una lista de exclusión explícita para cuentas
  automáticas conocidas que no llevan el sufijo (como `Copilot`).
- **Comprobar la conectividad antes de cada benchmark.** Volver a calcular
  estas medidas para cada tamaño de datos antes de cronometrar ninguna
  consulta, para no lanzar nunca el benchmark sobre un grafo en el que no
  hay nada que recorrer.

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

**De dónde viene esta sección.** Hasta aquí, todas las etapas han servido
para *conocer los datos*: qué contiene un evento (`peek_data.py`), cuántos
eventos, actores y repos hay y cómo se conectan (`summarize_data.py`). El
siguiente paso del proyecto es *diseñar los esquemas*: las tablas de la
base de datos relacional y los nodos y aristas de la base de datos de
grafo. Antes de dibujar una sola tabla hay que decidir **con qué criterio**
se van a diseñar, y esta sección fija ese criterio.

Viene directamente de la sección anterior sobre qué es un benchmark: una
prueba justa en la que todo está controlado salvo lo que se mide. El
esquema forma parte de "todo lo demás" que hay que controlar. Si los dos
esquemas no son equivalentes, el benchmark ya no compara un modelo
relacional con uno de grafo, sino dos diseños distintos.

**Dos palabras clave**

- **Esquema:** la "forma" de los datos dentro de la base de datos. En la
  relacional: qué tablas, qué columnas y qué claves. En la de grafo: qué
  tipos de nodo, qué tipos de arista y qué propiedades.
- **Consulta:** la pregunta concreta que se le hace a la base de datos y
  cuyo tiempo se mide. Por ejemplo: "partiendo del actor X, ¿a qué repos
  se llega en 3 saltos?".

**Dos maneras de diseñar un esquema**

| | Campos primero | Consulta primero |
|---|---|---|
| Por dónde empiezas | Mirando el JSON de GH Archive | Escribiendo la consulta del benchmark |
| Qué te preguntas | "¿Qué campos hay?" | "¿Qué necesita esta consulta para funcionar?" |
| Resultado | Decenas de tablas o tipos de nodo (commits, mensajes, PR, comentarios, etiquetas...), la mayoría nunca consultados | Solo lo mínimo: Actor, Repo y la conexión entre ellos |

"Campos primero" es tentador porque parece más completo: GH Archive ofrece
mensajes de commit, títulos de PR, texto de revisiones, etiquetas de
issues... y da la impresión de que cuanto más se modele, mejor. Pero el
benchmark de recorrido nunca lee nada de eso. Todo ese detalle se
construiría, se cargaría y se mantendría sin que influyera en la medición,
o peor, influyendo de forma no deseada (ver abajo).

**Ejemplo con este proyecto.** La consulta del benchmark es un recorrido
`actor → repo → actor → repo`. Para responderla solo hace falta saber tres
cosas: quién es cada actor, qué es cada repo, y qué actor ha hecho eventos
en qué repo. Por tanto, el esquema mínimo es el mismo en los dos lados:

| Concepto | Relacional | Grafo |
|---|---|---|
| Actor | tabla `actor` (id, login) | nodo `Actor` (id, login) |
| Repo | tabla `repo` (id, name) | nodo `Repo` (id, name) |
| Conexión | tabla `actor_repo` (actor_id, repo_id) | arista `Actor → Repo` |

¿Por qué el recorrido tiene que pasar por los repos, en lugar de ir
directamente de un actor a otro? Porque los datos casi nunca conectan a
dos personas directamente. `PushEvent` (el 95,3 % de los eventos) no
nombra a ningún segundo actor (ver la etapa de diseño del esquema más
abajo), y la conectividad medida por `summarize_data.py` muestra que las
conexiones entre actores vienen de los *repos compartidos*.

**Por qué es importante seguir este principio**

1. **Mides lo que quieres medir.** El tiempo de una consulta depende de
   cuántos datos tiene que leer la base de datos. Si cada fila arrastra
   columnas que la consulta no usa (por ejemplo, mensajes de commit
   largos), la base de datos lee más datos del disco, y el tiempo medido
   incluye ese ruido además del coste real del recorrido.
2. **La comparación es justa.** Si un lado tiene más detalle que el otro,
   el resultado refleja la diferencia de diseño, no la diferencia entre
   modelos. Por ejemplo: si en la relacional guardas una fila por cada
   evento (69.429 filas) y en el grafo una sola arista por cada par
   actor–repo (muchas menos), el grafo "gana" porque tiene menos datos, no
   porque sea mejor recorriendo. Eso respondería mal a la pregunta de
   investigación.
3. **Puedes demostrar que los dos lados son equivalentes.** Con un esquema
   pequeño es fácil comprobar que las dos bases de datos contienen
   exactamente lo mismo: el mismo número de actores, de repos y de
   conexiones. Con decenas de tablas, esa comprobación se vuelve difícil.
4. **Menos trabajo y menos errores.** Menos tablas significa menos código
   de carga, cargas más rápidas y menos sitios donde equivocarse. El
   tiempo ahorrado se puede dedicar a lo importante: repetir las
   mediciones con distintos tamaños de datos.
5. **Es reproducible y fácil de explicar.** En el informe final, el
   esquema se describe en tres líneas, y cualquier persona puede
   reconstruirlo y repetir el experimento.

**Medidas concretas a seguir**

1. **Escribir primero la consulta** (o consultas) del benchmark, en
   palabras, antes de crear ninguna tabla ni ningún nodo.
2. **Hacer la lista de los datos que lee esa consulta.** Solo eso entra en
   el esquema. Si un campo no aparece en la consulta, se queda fuera.
3. **Construir el mismo modelo en los dos lados**, como en la tabla de
   arriba: las mismas entidades y la misma conexión.
4. **Cargar los dos lados desde los mismos datos de origen** (los mismos
   archivos y el mismo filtro de bots) y comprobar que los conteos
   coinciden antes de medir nada.
5. **Decidir una sola vez cómo se guarda la conexión** (una por evento o
   una por par actor–repo) y usar esa misma decisión en los dos lados.
6. **Dar a cada lado sus ayudas normales, ni más ni menos.** En la
   relacional, eso significa índices sobre las columnas que se usan para
   unir tablas (`actor_id`, `repo_id`); el grafo ya guarda las conexiones
   directamente. Medir la relacional sin índices sería compararla con una
   versión deliberadamente lenta.
7. **Si se añade algo, añadirlo en los dos lados a la vez, o en ninguno.**
   Una propiedad nueva, un índice o otro tipo de conexión: siempre en los
   dos, para que la comparación siga siendo equivalente.

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
más allá de "otro repo que ese mismo actor tocó". `scripts/profile_schema.py` ([copia anotada](profile_schema.py))
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

### Concepto nuevo: la recursividad (una función que se llama a sí misma)

`profile_schema.py` introduce una idea de programación que no aparecía en
los scripts anteriores: la **recursividad** (o recursión). Su función
`find_actor_refs()` se llama *a sí misma* dentro de su propio cuerpo. (No
es "anidar" una función: anidar significa *definir* una función dentro de
otra. Aquí hay una sola función que se *llama* a sí misma.)

**Por qué se puede hacer.** Cada vez que se llama a una función, Python
crea una copia nueva y separada de sus parámetros y variables para esa
llamada. La nueva llamada trabaja con sus propios valores, y la llamada
que la lanzó espera, en pausa, hasta recibir la respuesta, y luego sigue.

**Una analogía.** Las muñecas rusas (matrioskas): para encontrar una nota
escondida en algún lugar de un juego de muñecas, las instrucciones son las
mismas en cada nivel: *"abre la muñeca; si la nota está aquí, cógela; si
no, aplica estas mismas instrucciones a cada muñeca que haya dentro"*. Las
instrucciones se refieren a sí mismas.

**Por qué la necesita este script.** El `payload` de un evento es un
diccionario que puede contener diccionarios, que pueden contener listas de
diccionarios, y así sucesivamente, y no sabemos de antemano cuántos
niveles tiene. Un bucle `for` normal solo mira un nivel. Una función
recursiva se ocupa de un nivel y luego se pide *a sí misma* que se ocupe
del siguiente, haya los que haya:

```
payload = {"action": "created", "issue": {"user": {"login": "luis"}}}

find_actor_refs(payload)               -> un dict sin "login": mira dentro
  find_actor_refs("created")           -> un texto: no hay nada dentro -> []
  find_actor_refs({"user": {...}})     -> un dict sin "login": mira dentro
    find_actor_refs({"login": "luis"}) -> ¡un usuario! -> ["payload.issue.user"]
resultado: ["payload.issue.user"]
```

**Las dos reglas que necesita toda función recursiva:**

1. **Un caso base:** una situación en la que responde *sin* llamarse a sí
   misma (aquí: ha encontrado un usuario, ha llegado a un valor simple, o
   ha llegado al límite de profundidad). Sin él, se llamaría a sí misma
   para siempre.
2. **Cada llamada tiene que acercarse a un caso base** (aquí: cada llamada
   baja un nivel más en los datos, y el contador `depth` baja en 1, con
   `MAX_SEARCH_DEPTH = 3` como límite).

La recursividad es la herramienta natural siempre que los datos son como
*cajas dentro de cajas*: carpetas dentro de carpetas, JSON dentro de JSON
y, más adelante en este proyecto, explorar un grafo salto a salto. La
[copia anotada](profile_schema.py) explica `find_actor_refs()` línea a
línea, y el apartado siguiente sigue un ejemplo completo llamada a
llamada.

### Ejemplo completo: el recorrido de `find_actor_refs()` paso a paso

Este ejemplo pasa por **todas** las ramas de la función: un diccionario sin
`login`, un diccionario con `login`, una lista, valores simples y el límite
de profundidad. Puedes leerlo con el código de la función al lado:

```python
def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    if depth < 0:
        return []

    if isinstance(value, dict):
        if isinstance(value.get("login"), str):
            return [path]
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    return []
```

#### 1. Los datos de ejemplo

Un `payload` parecido al de un `IssuesEvent`:

```python
payload = {
    "action": "opened",
    "issue": {
        "number": 7,
        "user": {"login": "luis", "id": 1},
        "assignees": [{"login": "ana"}, {"login": "marta"}],
        "milestone": {"creator": {"login": "pedro"}}
    }
}
```

`profile()` empieza todo con una sola llamada:
`find_actor_refs(payload, "payload", 3)`.

#### 2. La regla que crea las llamadas siguientes

Cada llamada nueva **nace del bucle de una llamada anterior**. Para
entender cómo, primero hacen falta cinco piezas básicas de Python. Después
las juntamos.

##### 2.1 Conocimientos base

**a) Un diccionario guarda parejas *clave → valor*.**
Es como una agenda: buscas por el nombre (la **clave**) y obtienes el dato
(el **valor**). Nuestro `payload` es un diccionario con **dos** claves:

```python
payload = {
    "action": "opened",       # clave "action" → valor "opened"
    "issue":  {...}           # clave "issue"  → valor: otro diccionario
}

payload["action"]   # → "opened"
payload["issue"]    # → {...} (el diccionario del issue)
```

**b) `.items()` da todas las parejas, una detrás de otra.**
Si quieres recorrer un diccionario entero, `.items()` te da cada pareja
como un **par** `(clave, valor)`:

```python
list(payload.items())
# → [("action", "opened"), ("issue", {...})]
#      └── 1er par ──┘     └─── 2º par ───┘
```

**c) El `for` coge un par en cada vuelta y lo reparte en dos variables.**
Cuando escribes dos nombres separados por una coma después de `for`,
Python coge cada par y pone su primera parte en la primera variable y su
segunda parte en la segunda:

```python
for key, sub_value in payload.items():
    print(key, "→", sub_value)

# 1ª vuelta:  key = "action"   sub_value = "opened"
# 2ª vuelta:  key = "issue"    sub_value = {...}
```

`key` y `sub_value` son solo nombres que elegimos. En cada vuelta cambian
de valor: primero valen lo del 1er par, después lo del 2º.

**d) Al llamar a una función, cada argumento va a su parámetro, en orden.**
La función está definida con tres parámetros:

```python
def find_actor_refs(value, path, depth):
```

Así que en una llamada como esta:

```python
find_actor_refs("opened", "payload.action", 2)
#               │         │                 │
#               ▼         ▼                 ▼
#             value     path              depth
```

dentro de esa llamada, `value` vale `"opened"`, `path` vale
`"payload.action"` y `depth` vale `2`. El **primer** valor va al
**primer** parámetro, el segundo al segundo y el tercero al tercero. Y
cada llamada tiene **sus propias** copias de esas variables (ver el
apartado de recursividad).

**e) Un f-string monta un texto con trozos de variables.**
Un texto con una `f` delante puede llevar variables entre llaves `{}`, y
Python las sustituye por su valor:

```python
path = "payload"
key = "action"
f"{path}.{key}"     # → "payload" + "." + "action" → "payload.action"
```

El punto del medio es un punto normal, que forma parte del texto. Por eso
el resultado parece una "dirección" dentro de los datos:
`payload.action` significa "la clave `action` dentro del `payload`".

##### 2.2 Juntando las piezas

Ahora sí, la línea del bucle de la función:

```python
for key, sub_value in value.items():
    refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
```

> **Bucle, iteración y vuelta.** Un **bucle** (en inglés *loop*) es el
> bloque de código que se repite entero: el `for ...:` con todo lo que
> tiene dentro. Cada una de sus repeticiones es una **iteración** (en
> inglés *iteration*), o, dicho de forma más coloquial, una **vuelta**:
> en estas notas, "vuelta" e "iteración" significan lo mismo. El verbo
> **iterar** (*to iterate*) significa recorrer algo elemento a elemento,
> que es justo lo que hace un bucle. Por ejemplo, el `issue` tiene 4
> claves, así que el bucle de la llamada 3 hace **4 iteraciones**
> (`number`, `user`, `assignees` y `milestone`).

Vamos a seguirla dentro de la **llamada 1**. Al empezar esa llamada, sus
tres parámetros valen (pieza *d*):

| Parámetro | Valor en la llamada 1 |
|---|---|
| `value` | todo el `payload` |
| `path` | `"payload"` |
| `depth` | `3` |

`value` es un diccionario con dos claves, así que `value.items()` da dos
pares (pieza *b*) y el bucle da **dos vueltas** (pieza *c*). En cada
vuelta, Python calcula los tres argumentos de la llamada nueva:

| | 1ª vuelta | 2ª vuelta |
|---|---|---|
| `key` (pieza *c*) | `"action"` | `"issue"` |
| `sub_value` (pieza *c*) | `"opened"` | el diccionario del `issue` |
| 1er argumento: `sub_value` | `"opened"` | el diccionario del `issue` |
| 2º argumento: `f"{path}.{key}"` (pieza *e*) | `"payload" + "." + "action"` = `"payload.action"` | `"payload" + "." + "issue"` = `"payload.issue"` |
| 3er argumento: `depth - 1` | `3 - 1` = `2` | `3 - 1` = `2` |
| **Llamada que nace** | `find_actor_refs("opened", "payload.action", 2)` → **llamada 2** | `find_actor_refs({...issue...}, "payload.issue", 2)` → **llamada 3** |

Y cuando la llamada 2 empieza, sus parámetros reciben esos tres valores en
orden (pieza *d*): `value = "opened"`, `path = "payload.action"` y
`depth = 2`. **Lo que en la llamada 1 eran `sub_value`, el texto montado y
`depth - 1`, en la llamada 2 pasan a ser `value`, `path` y `depth`.**

Lo que hace `refs.extend(...)` con la respuesta de cada llamada se explica
más abajo, en la parte 6.

##### 2.3 La regla general

Lo mismo pasa en todas las llamadas del ejemplo:

- **Diccionario →** una llamada por cada clave. El **valor** pasa a ser el
  nuevo `value`, la **clave** se añade al `path` y `depth` baja 1.
- **Lista →** una llamada por cada elemento. El elemento pasa a ser el
  nuevo `value`; como no hay clave, el `path` **no cambia**, y `depth`
  baja 1.
- **Usuario** (diccionario con `login`) **o valor simple →** ninguna
  llamada más: la función responde directamente. Son los **casos base**.

Por eso hay tantas llamadas: **cada contenedor genera una llamada por cada
cosa que tiene dentro**.

#### 3. El árbol de llamadas

```
LLAMADA 1   payload (dict con 2 claves)
├── LLAMADA 2   action    → "opened", un texto        → []
└── LLAMADA 3   issue     → dict con 4 claves
    ├── LLAMADA 4   number    → 7, un número          → []
    ├── LLAMADA 5   user      → ¡usuario luis!        → ["payload.issue.user"]
    ├── LLAMADA 6   assignees → lista con 2 elementos
    │   ├── LLAMADA 7   ana    → ¡usuario!            → ["payload.issue.assignees"]
    │   └── LLAMADA 8   marta  → ¡usuario!            → ["payload.issue.assignees"]
    └── LLAMADA 9   milestone → dict con 1 clave
        └── LLAMADA 10  creator → ¡usuario pedro!     → ["payload.issue.milestone.creator"]
```

Cada rama termina cuando llega a un **usuario** o a un **valor simple**.

#### 4. Todas las llamadas, una por una

| Llamada | Viene de | `value` | `path` | `depth` | Qué hace | Devuelve |
|---|---|---|---|---|---|---|
| 1 | `profile()` | todo el `payload` | `"payload"` | 3 | dict sin `login` → mira sus 2 claves | 4 rutas |
| 2 | llamada 1, vuelta 1 (`action`) | `"opened"` | `"payload.action"` | 2 | texto, nada dentro | `[]` |
| 3 | llamada 1, vuelta 2 (`issue`) | el `issue` | `"payload.issue"` | 2 | dict sin `login` → mira sus 4 claves | 4 rutas |
| 4 | llamada 3, vuelta 1 (`number`) | `7` | `"payload.issue.number"` | 1 | número, nada dentro | `[]` |
| 5 | llamada 3, vuelta 2 (`user`) | `{"login": "luis", "id": 1}` | `"payload.issue.user"` | 1 | ¡usuario! | `["payload.issue.user"]` |
| 6 | llamada 3, vuelta 3 (`assignees`) | la lista `[ana, marta]` | `"payload.issue.assignees"` | 1 | lista → mira sus 2 elementos | 2 rutas |
| 7 | llamada 6, elemento 1 | `{"login": "ana"}` | `"payload.issue.assignees"` (igual) | 0 | ¡usuario! | `["payload.issue.assignees"]` |
| 8 | llamada 6, elemento 2 | `{"login": "marta"}` | `"payload.issue.assignees"` (igual) | 0 | ¡usuario! | `["payload.issue.assignees"]` |
| 9 | llamada 3, vuelta 4 (`milestone`) | `{"creator": {...}}` | `"payload.issue.milestone"` | 1 | dict sin `login` → mira su única clave | 1 ruta |
| 10 | llamada 9, vuelta 1 (`creator`) | `{"login": "pedro"}` | `"payload.issue.milestone.creator"` | 0 | ¡usuario! | `["payload.issue.milestone.creator"]` |

Fíjate en la columna `depth`: baja 1 en cada nivel (3 → 2 → 1 → 0). Las
llamadas 7, 8 y 10 llegan con `depth = 0`, que todavía vale porque la
comprobación es `depth < 0`, y cero no es menor que cero.

#### 5. El orden en el tiempo: por qué 6, 7, 8 y después 9

Las llamadas se numeran en el orden en que **ocurren**, y Python **termina
por completo una llamada, con todas sus "hijas", antes de volver a la
anterior**. La llamada de fuera se queda en pausa mientras tanto:

1. La llamada 1 lanza la **2** (clave `action`). La 2 devuelve `[]` al
   momento.
2. La llamada 1 lanza la **3** (clave `issue`) y se queda en pausa.
3. La llamada 3 lanza la **4** (`number`), que devuelve `[]`, y luego la
   **5** (`user`), que encuentra a luis.
4. La llamada 3 lanza la **6** (`assignees`) y se queda en pausa.
5. La llamada 6 lanza la **7** (ana) y luego la **8** (marta). Cuando
   termina la 8, la 6 ya ha recorrido su lista y **devuelve** su resultado
   a la 3.
6. **Solo entonces** la llamada 3 sale de la pausa y da su última vuelta:
   lanza la **9** (`milestone`), que a su vez lanza la **10** (`creator`).
7. La 10 le responde a la 9, la 9 a la 3, y la 3, que ya ha terminado su
   bucle, le responde a la 1.

Es como abrir muñecas rusas: antes de pasar a la siguiente muñeca del mismo
nivel, abres por completo la que tienes en la mano y todas las que lleva
dentro.

#### 6. Cómo se va llenando la lista `refs`

Cada llamada tiene **su propia** lista `refs`, y la llena con lo que le
devuelven sus llamadas hijas mediante `refs.extend(...)`. Así crece la
`refs` de la **llamada 3**:

| Después de que responda... | Lo que devuelve | `refs` de la llamada 3 |
|---|---|---|
| (al empezar) | — | `[]` |
| la llamada 4 | `[]` | `[]` (no cambia) |
| la llamada 5 | `["payload.issue.user"]` | `["payload.issue.user"]` |
| la llamada 6 | `["payload.issue.assignees", "payload.issue.assignees"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees"]` |
| la llamada 9 | `["payload.issue.milestone.creator"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees", "payload.issue.milestone.creator"]` |

**Cuando una llamada no encuentra nada,** devuelve una lista vacía (`[]`).
`.extend([])` añade a `refs` todos los elementos de esa lista, que son
ninguno, así que **no hay nada que añadir y la lista se queda como estaba**.
Eso pasa con las llamadas 2 y 4. Solo las llamadas que *sí* encuentran un
usuario (5, 7, 8 y 10) hacen crecer las listas.

La `refs` de la **llamada 1** recibe `[]` de la llamada 2 y las 4 rutas de
la llamada 3, así que el resultado final es:

```python
['payload.issue.user',
 'payload.issue.assignees',
 'payload.issue.assignees',
 'payload.issue.milestone.creator']
```

#### 7. Dos detalles más

**El límite de profundidad en acción.** Si un usuario estuviera un nivel
más abajo de lo que permite `MAX_SEARCH_DEPTH = 3`:

```python
deep = {"a": {"b": {"c": {"d": {"login": "x"}}}}}
find_actor_refs(deep, "payload", 3)   # -> []
```

al llegar a `{"login": "x"}` el `depth` ya valdría **-1**, y la primera
comprobación (`if depth < 0: return []`) cortaría ahí: **no lo encuentra**.
Es el precio de la red de seguridad; como los payloads de GH Archive son
poco profundos, en la práctica no se pierde nada.

**Por qué `profile()` usa `set(...)` después.** El resultado tiene
`payload.issue.assignees` **dos veces**, una por ana y otra por marta.
`profile()` hace `set(...)`, que deja cada ruta una sola vez:

```python
{'payload.issue.user', 'payload.issue.assignees', 'payload.issue.milestone.creator'}
```

Así este evento cuenta como **un** evento que tiene asignados, no como dos:
lo que se cuenta es *en cuántos eventos* aparece cada ruta, no cuántos
usuarios hay.

### Para qué sirve el resultado

El resultado de `profile_schema.py` es largo y, a primera vista, parece una
lista de campos técnicos. Pero responde a una pregunta muy concreta del
proyecto: **además del actor que hizo el evento, ¿el evento nombra a otra
persona?** Si la respuesta fuera "sí, a menudo", el grafo podría tener
conexiones directas persona → persona (por ejemplo, "Ana comentó en el
issue de Luis"), y los recorridos del benchmark podrían usarlas. Si la
respuesta es "casi nunca", las personas solo se conectan a través de los
repos que comparten, y el esquema tiene que reflejarlo.

Además de eso, el resultado sirve para tres cosas prácticas a la hora de
diseñar el esquema:

1. **Saber qué datos hay en cada tipo de evento.** Cada tipo de evento
   guarda cosas distintas en su `payload`. Un `PushEvent` guarda la rama y
   los commits; un `IssueCommentEvent` guarda el issue y el comentario.
2. **Saber si un campo es fiable.** "present in 100%" significa que el
   campo está siempre; un porcentaje bajo significa que solo aparece a
   veces. En una tabla, eso sería una columna opcional (que puede quedar
   vacía).
3. **Saber qué tipo de dato es.** `str` (texto), `int` (número), `dict`
   (un objeto con más campos dentro), `list` (una lista) o `NoneType`
   (vacío). Por ejemplo, en `CreateEvent` el campo `description` está
   vacío (`NoneType`) en 633 de 1.290 eventos: si se guardara, tendría que
   ser una columna que admite valores vacíos.

### Cómo leer un bloque del resultado

```
IssueCommentEvent (194 events)
  payload.action               present in 100.0% (194/194) - types: str x194
  payload.issue                present in 100.0% (194/194) - types: dict x194
  payload.comment              present in 100.0% (194/194) - types: dict x194
  actor references (nested 'login' fields):
    payload.issue.user                  present in 100.0% (194/194)
    payload.comment.user                present in 100.0% (194/194)
```

- **Primera línea:** el tipo de evento y cuántos eventos de ese tipo hay
  (194 comentarios en issues).
- **Líneas `payload.…`:** cada campo del `payload`, en qué porcentaje de
  esos eventos aparece y qué tipo de dato tiene. Aquí, los tres campos
  aparecen siempre: `action` es texto, e `issue` y `comment` son objetos
  con más datos dentro.
- **`actor references`:** las rutas dentro del `payload` donde hay un
  objeto con forma de usuario de GitHub (un diccionario con `login`), y en
  qué porcentaje de eventos aparece. `payload.issue.user` es quien abrió el
  issue; `payload.comment.user` es quien escribió el comentario.

### Segunda comprobación: ¿es de verdad otra persona?

Hay una trampa. `profile_schema.py` solo comprueba que **existe** un
usuario en esa ruta, no **quién** es. Y muchas veces es el propio actor:
en un `IssueCommentEvent`, quien escribe el comentario (`comment.user`) es
exactamente la persona que hizo el evento. Para saberlo hay que comparar
cada usuario encontrado con el `actor` del evento. Esa comparación, hecha
sobre los datos de este proyecto, da esto:

| Tipo de evento y ruta | Quién es | ¿Es el propio actor? |
|---|---|---|
| `IssueCommentEvent` `comment.user` | autor del comentario | Sí, el 100 % |
| `IssueCommentEvent` `issue.user` | quien abrió el issue | Solo el 34 %: **en el 66 % es otra persona** |
| `IssuesEvent` `issue.user` | quien abrió el issue | El 87 % (normalmente cada uno gestiona su propio issue) |
| `PullRequestReviewEvent` `review.user` | autor de la revisión | El 99 % |
| `PullRequestReviewCommentEvent` `comment.user` | autor del comentario | El 100 % |
| `ReleaseEvent` `release.author` | autor de la release | El 100 % |
| `ForkEvent` `forkee.owner` | dueño de la copia nueva (el fork) | El 100 %: quien hace el fork es el dueño de la copia |
| `assignee` / `assignees` (varios tipos) | personas asignadas | Entre el 30 % y el 70 %, según el caso |
| `performed_via_github_app.owner` | dueño de la aplicación que publicó el evento | Nunca, pero tampoco es un participante: suele ser una empresa |

**Resultado:** de los 69.429 eventos, solo **178 (el 0,26 %)** nombran a
una persona realmente distinta del actor (sin contar los dueños de
aplicaciones), y solo **76** de ellos los hacen actores que no son bots.
Casi todos son comentarios en el issue de otra persona
(`IssueCommentEvent`, 131) o acciones sobre el issue de otra persona
(`IssuesEvent`, 35).

**Hallazgo clave:** `PushEvent` —el 95,3 % de todos los eventos— no nombra
a ninguna otra persona en su `payload`: solo tiene `ref`, `before`/`head`
(identificadores de commits) y `repository_id`. El `payload.pull_request`
de `PullRequestEvent` es además una referencia recortada que no incluye al
autor del PR (a diferencia de la respuesta completa de la API REST de
GitHub). Y en el resto de eventos, la mayoría de los usuarios anidados son
el propio actor. Una versión anterior de estas notas decía que las
referencias a un segundo actor estaban en el ~4,7 % de eventos que no son
`PushEvent`; eso era solo un límite superior. La cifra real, tras comparar
con el actor, es el **0,26 %** (desglose en
[gh-archive-guide.md](gh-archive-guide.md#dónde-aparece-un-segundo-actor-referencias-anidadas)).

**Qué significa para el esquema:** las conexiones directas persona →
persona son prácticamente inexistentes en estos datos. Con 76 conexiones
entre personas (sin bots) no se puede construir un recorrido de varios
saltos. Por eso el esquema del benchmark es **Actor, Repo y la conexión
entre ellos**, sin arista actor → actor: las personas se conectan a través
de los repos que comparten, tal como mide `summarize_data.py`. Y una
lección general: un campo que *parece* otra persona no tiene por qué
serlo; siempre hay que comprobarlo contra el actor.

### Resumen: lo que sabemos de los datos de esta hora

Este apartado reúne en un solo sitio lo que han descubierto `peek_data.py`,
`summarize_data.py` y `profile_schema.py` sobre la hora fija del proyecto
(2026-08-27, 15:00 UTC, 69.429 eventos).

#### 1. Cómo se leen los datos de un evento

Cada línea del archivo es un JSON independiente. `json.loads(line)` lo
convierte en un **diccionario** de Python, y a partir de ahí se accede a
cada dato por su clave. Algunos datos están en un **diccionario dentro de
otro diccionario**, y por eso llevan **dos corchetes**: el primero entra en
el diccionario de dentro y el segundo coge el dato.

| Qué quieres saber | Cómo se obtiene | Ejemplo |
|---|---|---|
| Quién hizo la acción | `event["actor"]["login"]` | `"octocat"` |
| Su identificador numérico | `event["actor"]["id"]` | `583231` |
| En qué repo se hizo | `event["repo"]["name"]` | `"octocat/Hello-World"` |
| El identificador numérico del repo | `event["repo"]["id"]` | `1296269` |
| Qué tipo de acción fue | `event["type"]` | `"PushEvent"` |
| Cuándo ocurrió | `event["created_at"]` | `"2026-08-27T15:00:01Z"` |
| Los detalles de la acción | `event["payload"]` | depende del tipo de evento |

Por ejemplo, `event["actor"]["login"]` se lee así: "dentro del evento,
coge el diccionario `actor`; dentro de él, coge el valor de `login`".

Los cinco primeros datos están en **todos** los eventos (comprobado: los
69.429 tienen `actor.id` y `repo.id`). Son exactamente lo que necesita el
esquema mínimo del benchmark: quién (Actor), dónde (Repo) y la conexión
entre los dos. Para las claves de las tablas y los nodos conviene usar los
`id` numéricos, no los nombres: un usuario puede cambiar su `login`, pero
su `id` no cambia.

#### 2. Otras personas dentro del `payload`

El `payload` puede contener más usuarios, con la misma forma que el actor
(un diccionario con `login`). `profile_schema.py` los encuentra buscando
`login` en cualquier nivel del `payload`, gracias a la recursividad.

Pero **encontrar un usuario no significa encontrar a otra persona**. Al
comparar cada usuario encontrado con el actor del evento, la mayoría
resultan ser el propio actor (ver "Segunda comprobación" más arriba). Solo
**178 eventos de 69.429 (el 0,26 %)** nombran de verdad a una persona
distinta, y solo **76** si se quitan los bots.

#### 3. Qué contiene cada tipo de evento en esta hora

| Tipo de evento | Eventos | % del total | Qué guarda el `payload` | Usuarios dentro del `payload` | ¿Nombra a otra persona? |
|---|---|---|---|---|---|
| `PushEvent` | 66.174 | 95,3 % | La rama (`ref`), el commit antes y después del push (`before`, `head`), `push_id` y `repository_id` | Ninguno | No |
| `CreateEvent` | 1.290 | 1,9 % | Lo creado: en esta hora, siempre una rama (`ref_type = "branch"`). También la rama principal y una `description`, que está vacía en 633 de 1.290 | Ninguno | No |
| `DeleteEvent` | 615 | 0,9 % | Lo borrado: 586 ramas y 29 tags | Ninguno | No |
| `PullRequestEvent` | 532 | 0,8 % | La acción (`opened`, `closed`...), el número del PR, un `pull_request` recortado **sin su autor**, y a veces etiquetas (25 %) | `assignee`/`assignees` (2,1 %) | Muy poco: 7 eventos |
| `IssueCommentEvent` | 194 | 0,3 % | El issue comentado y el comentario | `comment.user` (100 %), `issue.user` (100 %), dueño de la app (63 %), asignados (16,5 %), creador del milestone (3,6 %) | **Sí, el que más:** `issue.user` es otra persona en el 66 % de los casos (131 eventos) |
| `IssuesEvent` | 189 | 0,3 % | El issue y su acción; a veces etiquetas (45 %) y asignados (7,4 %) | `issue.user` (100 %), asignados (20 %), dueño de la app (11 %) y otros | A veces: 35 eventos (`issue.user` es el actor en el 87 %) |
| `PullRequestReviewCommentEvent` | 134 | 0,2 % | El comentario y el PR | `comment.user` (100 %) | No: es el propio actor |
| `PullRequestReviewEvent` | 131 | 0,2 % | La revisión y el PR | `review.user` (100 %) | Casi nunca: 1 evento |
| `WatchEvent` | 96 | 0,1 % | Solo la acción: siempre `started`, es decir, alguien **dio una estrella** al repo | Ninguno | No |
| `ReleaseEvent` | 44 | 0,1 % | La release publicada | `release.author` (100 %), menciones (6,8 %) | Casi nunca: 2 eventos |
| `ForkEvent` | 18 | 0,03 % | La copia nueva del repo (`forkee`) | `forkee.owner` (100 %) | No: el dueño del fork es quien lo hace |
| `CommitCommentEvent` | 7 | 0,01 % | El comentario sobre un commit | `comment.user` (100 %) | No: es el propio actor |
| `MemberEvent` | 5 | 0,01 % | La persona añadida al repo (`member`) | `member` (100 %) | A veces: 2 eventos |

Cómo leer la tabla: la columna "Usuarios dentro del `payload`" es lo que
muestra `profile_schema.py`, y la última columna es el resultado de
comparar esos usuarios con el actor.

#### 4. Lo que esto significa para el proyecto

- **Lo esencial está en todos los eventos y es fácil de leer:**
  `actor.id`/`actor.login`, `repo.id`/`repo.name`, `type` y `created_at`.
  Con eso se construye el esquema mínimo (Actor, Repo y la conexión entre
  ellos).
- **Casi todo son pushes (95,3 %), y un push no nombra a nadie más.** Las
  personas se conectan entre sí a través de los **repos que comparten**, no
  directamente.
- **Las conexiones directas persona → persona son casi inexistentes**
  (0,26 % de los eventos, 76 sin bots), así que el benchmark no puede
  basarse en ellas. Por eso el esquema no tiene arista actor → actor.
- **Un campo que parece otra persona no tiene por qué serlo.** Antes de usar
  cualquier usuario del `payload` hay que comprobarlo contra el actor, y
  descartar rutas como `performed_via_github_app.owner`, que es el dueño
  de una aplicación y no un participante.
- **Esta hora sola es pequeña y fragmentada** (ver "Resultados de
  conectividad" en la etapa de resumen). El siguiente paso es descargar más
  horas y volver a medir.

El pipeline general hasta ahora es: **download_gharchive.py →
peek_data.py → summarize_data.py → profile_schema.py** — primero obtener
y descomprimir la hora fija del conjunto de datos, luego inspeccionar un
puñado de eventos en bruto, después obtener una lectura agregada del
volumen y la conectividad, luego perfilar la forma del payload y localizar
referencias a un segundo actor, antes de pasar a extraer y cargar
realmente los registros en los modelos relacional y de grafo que se están
comparando.


## Instalación del software (PostgreSQL, Neo4j y los conectores de Python)

Con el esquema mínimo decidido (tablas `actor`, `repo` y `actor_repo` en
la base de datos relacional; nodos `Actor` y `Repo` con una arista entre
ellos en la de grafo), el siguiente paso es instalar las dos bases de datos
y lo necesario para que Python hable con ellas.

### Antes de empezar

**Qué vamos a instalar** (todo gratuito):

| Software | Para qué sirve | Coste |
|---|---|---|
| **PostgreSQL** (con **pgAdmin**) | La base de datos relacional. pgAdmin es una interfaz gráfica para verla y hacer consultas | Gratis, software libre |
| **Neo4j Desktop** | Gestiona bases de datos de grafo Neo4j en tu ordenador, con interfaz gráfica | Gratis para uso local de desarrollo |
| **`psycopg`** (paquete de Python) | El conector para que Python se comunique con PostgreSQL | Gratis |
| **`neo4j`** (paquete de Python) | El conector oficial para que Python se comunique con Neo4j | Gratis |

**Las dos bases de datos van en el mismo ordenador.** Así ninguna tiene
ventaja por estar en otra máquina o detrás de una red: es parte de
controlarlo todo salvo lo que se mide (ver la sección sobre qué es un
benchmark).

**Si usas un portátil de empresa:** instalar software puede necesitar
permiso de IT o estar limitado por las políticas de la empresa.
Compruébalo antes de empezar.

**Las contraseñas nunca van al repositorio.** Durante la instalación
elegirás dos contraseñas: una para PostgreSQL y otra para Neo4j. Guárdalas
en un gestor de contraseñas. No las escribas en el código, en estas notas
ni en ningún archivo que se suba a GitHub. Más abajo se explica cómo
pasárselas a Python de forma segura.

### Paso 1: instalar PostgreSQL

1. **Descargar el instalador.** Ve a
   <https://www.postgresql.org/download/windows/> y pulsa *Download the
   installer*. Elige la **versión más reciente** para **Windows x86-64**.
2. **Ejecutar el instalador** y aceptar las opciones por defecto, con
   estos detalles:
   - **Componentes:** deja marcados *PostgreSQL Server*, *pgAdmin 4* y
     *Command Line Tools*. *Stack Builder* no hace falta (puedes
     desmarcarlo).
   - **Contraseña:** te pedirá una contraseña para el superusuario
     `postgres`. Elígela y guárdala en tu gestor de contraseñas.
   - **Puerto:** deja el que viene, **5432**.
   - **Locale:** deja el que viene por defecto.
   - Al terminar, si te ofrece abrir *Stack Builder*, desmárcalo.
3. **Añadir `psql` al PATH** (para poder usarlo desde Git Bash). `psql` es
   el programa de línea de comandos de PostgreSQL. El instalador no lo
   añade al PATH, así que:
   - Busca en Windows *"Editar las variables de entorno de esta cuenta"*.
   - En *Path*, pulsa *Editar* → *Nuevo* y añade
     `C:\Program Files\PostgreSQL\<versión>\bin` (cambia `<versión>` por
     el número de carpeta que se haya creado, por ejemplo `18`).
   - Cierra y vuelve a abrir Git Bash para que lo vea.
   - Si prefieres no tocar el PATH, puedes usar *SQL Shell (psql)* desde el
     menú Inicio, que hace lo mismo.
4. **Comprobar que funciona** (con Git Bash; para hacerlo con pgAdmin 4,
   ver el apartado siguiente):

   ```bash
   psql -U postgres -c "SELECT version();"
   ```

   Te pedirá la contraseña de `postgres` y debería mostrar la versión
   instalada.
5. **Crear la base de datos del proyecto** (con Git Bash; con pgAdmin 4,
   ver el apartado siguiente):

   ```bash
   psql -U postgres -c "CREATE DATABASE gharchive;"
   psql -U postgres -d gharchive -c "SELECT 1;"
   ```

   El segundo comando comprueba que puedes conectarte a la base nueva:
   debería mostrar una pequeña tabla con un `1`.

PostgreSQL se instala como un **servicio de Windows**: arranca solo al
encender el ordenador y se queda funcionando en segundo plano. Si quieres
pararlo cuando no lo uses, busca *Servicios* en Windows y detén el
servicio `postgresql-x64-<versión>`.

### Dos formas de trabajar con PostgreSQL: Git Bash (`psql`) o pgAdmin 4

Todo lo que se hace con `psql` en Git Bash también se puede hacer con
**pgAdmin 4**, la interfaz gráfica que se instala junto con PostgreSQL.
**Puedes usar la que prefieras, o las dos**: trabajan sobre la misma base
de datos, así que lo que crees con una lo verás con la otra.

| Tarea | Con Git Bash (`psql`) | Con pgAdmin 4 |
|---|---|---|
| Abrir | Una terminal de Git Bash (con `psql` en el PATH, paso 1.3) | Buscar **pgAdmin 4** en el menú Inicio |
| Conectarse | Cada comando lleva `-U postgres` y pide la contraseña (o la lee de `PGPASSWORD`) | Panel izquierdo: **Servers** → **PostgreSQL** → escribir la contraseña de `postgres` |
| Ver la versión | `psql -U postgres -c "SELECT version();"` | Abrir el Query Tool (ver abajo), escribir `SELECT version();` y pulsar **F5** |
| Crear la base `gharchive` | `psql -U postgres -c "CREATE DATABASE gharchive;"` | Clic derecho en **Databases** → **Create** → **Database...** → nombre `gharchive` → **Save** |
| Ejecutar una consulta | `psql -U postgres -d gharchive -c "..."` | Seleccionar `gharchive` en el árbol → menú **Tools** → **Query Tool** → escribir la consulta → **F5** (o ▶) |
| Ver las tablas | `psql -U postgres -d gharchive -c "\dt"` | Árbol: **gharchive** → **Schemas** → **public** → **Tables** |
| Ver los datos de una tabla | `psql -U postgres -d gharchive -c "SELECT * FROM actor LIMIT 10;"` | Clic derecho en la tabla → **View/Edit Data** |

**Comprobar que PostgreSQL funciona con pgAdmin 4 (sin Git Bash):**

1. **Abrir pgAdmin 4** desde el menú Inicio de Windows. La primera vez te
   pedirá una *master password*: es una contraseña solo para pgAdmin, que
   protege las contraseñas que guarde. Elígela y guárdala en tu gestor de
   contraseñas.
2. **Conectarte al servidor:** en el panel izquierdo, despliega
   **Servers** (la flechita) y haz clic en **PostgreSQL** (aparece con su
   número de versión, por ejemplo *PostgreSQL 18*). Te pedirá la
   contraseña del usuario **`postgres`**, la que elegiste al instalar.

   ✅ **Primera comprobación:** si el servidor se despliega y debajo ves
   **Databases**, **Login/Group Roles** y **Tablespaces**, PostgreSQL está
   funcionando y acepta conexiones.
3. **Comprobar la versión con una consulta:** despliega **Databases** y haz
   clic en **postgres** (la base que viene por defecto). Ve al menú
   **Tools** → **Query Tool**, escribe `SELECT version();` y pulsa **F5**
   (o el botón ▶ *Execute*).

   ✅ **Segunda comprobación:** abajo, en *Data Output*, aparece una fila
   con un texto parecido a `PostgreSQL 18.x on x86_64-windows...`.
4. **Crear la base del proyecto:** clic derecho en **Databases** →
   **Create** → **Database...**, escribe `gharchive` en **Database** y
   pulsa **Save**.

   ✅ **Tercera comprobación:** `gharchive` aparece en la lista de
   **Databases**. Selecciónala, abre de nuevo **Tools** → **Query Tool**,
   ejecuta `SELECT 1;` y debería salir un `1`.

**Si algo falla:**

- **Error de contraseña:** usa la del usuario `postgres` (la de la
  instalación), no la *master password* de pgAdmin. Son dos contraseñas
  distintas.
- **"Could not connect to server" o un error de conexión:** el servicio de
  PostgreSQL no está arrancado. Busca **Servicios** en Windows, localiza
  `postgresql-x64-<versión>` y pulsa **Iniciar**.

**Cuándo conviene cada una:**

- **pgAdmin 4** es más cómodo para **explorar**: ver qué tablas hay, mirar
  sus datos y probar consultas con calma. Si lo usas, el paso 1.3 (añadir
  `psql` al PATH) es opcional.
- **Git Bash** sigue siendo necesario para **ejecutar los scripts de
  Python** del proyecto (los que crearán los CSV, cargarán los datos y
  medirán los tiempos). Y `psql` es útil cuando un comando se quiere
  repetir siempre igual, copiándolo de estas notas.

Otra opción, si se prefiere no salir del editor, es la extensión
**PostgreSQL** de Microsoft para VS Code, que también permite conectarse y
ejecutar consultas.

### Paso 2: instalar Neo4j Desktop

1. **Descargar Neo4j Desktop.** Ve a <https://neo4j.com/download/>. Te
   pedirá algunos datos en un formulario antes de la descarga. Si en la
   página aparece una **clave de activación**, cópiala: Neo4j Desktop te la
   pedirá la primera vez que lo abras.
2. **Instalarlo y abrirlo.**
3. **Crear una base de datos local** (Neo4j Desktop la llama *instance* o
   *DBMS*, según la versión):
   - **Nombre:** `gharchive`.
   - **Versión:** la más reciente que ofrezca.
   - **Contraseña:** elige una para el usuario `neo4j` y guárdala en tu
     gestor de contraseñas.
4. **Arrancarla** con el botón *Start*. Neo4j escucha en dos puertos:
   - **7474**, para el navegador (Neo4j Browser);
   - **7687**, para los programas, entre ellos Python (protocolo *Bolt*).
5. **Comprobar que funciona** (comprobación rápida; la completa está en
   el apartado siguiente). Abre Neo4j Browser (botón *Open*, o
   <http://localhost:7474> en el navegador), conéctate con el usuario
   `neo4j` y tu contraseña, y ejecuta:

   ```cypher
   RETURN 1;
   ```

   Debería devolver `1`.

A diferencia de PostgreSQL, la base de datos de Neo4j **solo funciona
mientras esté arrancada** en Neo4j Desktop. Antes de trabajar con ella,
abre Neo4j Desktop y comprueba que está en marcha.

### Comprobar que Neo4j funciona desde la interfaz

Neo4j se maneja casi siempre con interfaz gráfica, así que para
comprobarlo **no hace falta Git Bash**. Hay dos herramientas visuales:

| Herramienta | Para qué sirve | Equivalente en PostgreSQL |
|---|---|---|
| **Neo4j Desktop** | Crear, arrancar y parar las bases de datos | El panel **Servers** de pgAdmin |
| **Neo4j Browser** | Escribir consultas y ver los resultados, incluso dibujados como nodos y aristas | El **Query Tool** de pgAdmin |

**Paso a paso:**

1. **Abrir Neo4j Desktop** y buscar la base de datos `gharchive`. Según la
   versión de Desktop, aparece en la lista de *Instances* o dentro de un
   *Project*.

   ✅ **Primera comprobación:** su estado indica **Running** o **Active**
   (normalmente con un punto verde). Si pone *Stopped*, pulsa **Start** y
   espera unos segundos.
2. **Abrir Neo4j Browser:** pulsa **Open** (o *Query*, según la versión)
   junto a la base de datos, o escribe <http://localhost:7474> en el
   navegador. Si pide conectarse:
   - **Connect URL:** `neo4j://localhost:7687`
   - **Username:** `neo4j`
   - **Password:** la que elegiste al crear la base de datos

   ✅ **Segunda comprobación:** la conexión se acepta y arriba aparece una
   barra para escribir consultas, con el símbolo `neo4j$`.
3. **Comprobar la versión.** Escribe en la barra de arriba y pulsa
   **Ctrl + Enter** (o el botón ▶):

   ```cypher
   CALL dbms.components() YIELD name, versions, edition
   RETURN name, versions, edition;
   ```

   ✅ **Tercera comprobación:** aparece una fila con `Neo4j Kernel`, el
   número de versión y la edición.
4. **Probar a escribir y leer**, para confirmar que puede guardar datos de
   verdad:

   ```cypher
   CREATE (p:Prueba {mensaje: "hola"}) RETURN p;
   ```

   ✅ **Cuarta comprobación:** en el resultado aparece un **círculo**: es
   un nodo, en la vista de grafo de Neo4j. Si haces clic en él, verás su
   propiedad `mensaje: "hola"`.

   Después bórralo, para dejar la base de datos vacía:

   ```cypher
   MATCH (p:Prueba) DELETE p;
   ```

   Debería decir *Deleted 1 node*.

**El nombre de la base de datos.** En Neo4j Desktop, `gharchive` es el
nombre de la **instancia** (el "servidor"). Dentro, la base de datos donde
se trabaja se llama **`neo4j`**: es la que viene por defecto, y es la que
usaremos. No hace falta crear otra; el `neo4j$` de la barra de consultas
indica justamente que estás en ella.

**Si algo falla:**

| Problema | Causa probable | Solución |
|---|---|---|
| La base no pasa a *Running* | Otro programa usa el puerto 7474 o 7687 | Mira el mensaje de error en Desktop; cierra el otro programa o cambia el puerto en la configuración |
| *Authentication failure* | Contraseña equivocada | Usa la que elegiste al **crear la base** en Neo4j Desktop (no la de PostgreSQL) |
| Neo4j Browser no se conecta | La base está parada | Vuelve a Desktop y pulsa **Start** |
| La vista de grafo no muestra nada | La consulta no devuelve nodos | Es normal en consultas como `RETURN 1`; prueba la del punto 4 |

**¿Y desde la terminal?** Neo4j trae **`cypher-shell`**, el equivalente de
`psql`, y Neo4j Desktop puede abrir una terminal ya preparada para usarlo.
Para este proyecto, Neo4j Browser es suficiente.

### Punto de control: las dos bases de datos están listas

Llegados aquí, las dos bases de datos del proyecto están **instaladas,
arrancadas y comprobadas**:

| Base de datos | Dónde se gestiona | Qué hay dentro ahora | Cómo se comprobó |
|---|---|---|---|
| **PostgreSQL** (relacional) | pgAdmin 4 o `psql` | La base de datos `gharchive`, vacía: todavía sin tablas | Conexión aceptada, versión visible y `SELECT 1;` en `gharchive` |
| **Neo4j** (grafo) | Neo4j Desktop y Neo4j Browser | La instancia `gharchive`, con su base de datos `neo4j` vacía: todavía sin nodos | Estado *Running*, conexión aceptada, versión visible y prueba de escritura y lectura |

Las dos están **vacías a propósito**. Las tablas (`actor`, `repo`,
`actor_repo`) y los nodos (`Actor`, `Repo`) se crearán más adelante, desde
scripts de Python, a partir de los mismos archivos de datos para los dos
lados. Para eso, primero hay que preparar el sitio donde van a funcionar
esos scripts: un pequeño entorno de Python propio del proyecto.

### Paso 3: preparar Python (un entorno virtual para el proyecto)

#### 3.1 El problema que resuelve un entorno virtual

Hasta ahora, los scripts del proyecto (`download_gharchive.py`,
`peek_data.py`, `summarize_data.py`, `profile_schema.py`) solo usaban la
**biblioteca estándar** de Python: módulos como `json`, `argparse` o
`collections`, que vienen incluidos con Python. Por eso funcionaban sin
instalar nada.

A partir de ahora, Python tiene que hablar con PostgreSQL y con Neo4j, y
para eso necesita dos **paquetes externos**, que no vienen con Python y hay
que instalar: `psycopg` y `neo4j`. La pregunta es *dónde* instalarlos.

Si se instalan "en el Python del ordenador" (la instalación general,
compartida por todos los proyectos), aparecen tres problemas:

1. **Conflictos entre proyectos.** Si otro proyecto necesita una versión
   distinta del mismo paquete, solo puede haber una instalada a la vez, y
   uno de los dos proyectos se rompe.
2. **No se sabe qué necesita el proyecto.** Con el tiempo, la instalación
   general acumula paquetes de muchos proyectos, y ya no queda claro cuáles
   hacen falta para este.
3. **No es reproducible.** Para repetir el experimento en otro ordenador
   hay que saber exactamente qué paquetes y qué versiones se usaron. En
   un benchmark, eso forma parte de las condiciones del experimento, igual
   que las versiones de las bases de datos.

Un **entorno virtual** resuelve los tres: es un **Python aislado solo para
este proyecto**, con sus propios paquetes.

#### 3.2 Qué es, físicamente, un entorno virtual

Es simplemente una **carpeta** dentro del proyecto, que llamaremos
`.venv`. Dentro contiene:

```
.venv/
├── Scripts/
│   ├── python.exe        ← un Python que usa solo los paquetes de .venv
│   ├── pip.exe           ← el instalador de paquetes de este entorno
│   └── activate          ← el script que "activa" el entorno en Git Bash
└── Lib/
    └── site-packages/    ← aquí se guardan los paquetes instalados
```

Una analogía: el Python general del ordenador es la **cocina común** de un
piso compartido, donde cada uno deja sus cosas y acaban mezcladas. El
entorno virtual es **una caja con tu nombre** dentro de esa cocina: lo que
metes ahí es solo tuyo, sabes exactamente qué hay, y si un día quieres
empezar de cero, tiras la caja y haces otra.

Algunos detalles importantes:

- **No contiene una copia completa de Python.** Usa el Python 3.14 que ya
  tienes instalado, pero con su propia carpeta de paquetes.
- **No contiene tu código.** Los scripts siguen en `scripts/`, como
  siempre; el entorno solo aporta el Python y los paquetes con los que se
  ejecutan.
- **No se sube a GitHub.** La carpeta `.venv` ya está en el `.gitignore`.
  Lo que sí se sube es la *lista* de paquetes (`requirements.txt`, en el
  punto 3.6), para que cualquiera pueda recrear el entorno.
- **Se puede borrar sin miedo.** Si algo va mal, se borra la carpeta
  `.venv` y se vuelve a crear en un minuto.

#### 3.3 Crear el entorno (solo una vez)

```bash
cd /c/dev/Research
python -m venv .venv
```

- `cd /c/dev/Research` te sitúa en la carpeta del proyecto. El entorno se
  crea dentro de la carpeta en la que estés.
- `python -m venv .venv` significa: "Python, ejecuta tu módulo `venv` y
  crea un entorno virtual en una carpeta llamada `.venv`". El punto
  inicial del nombre es una convención: en muchos sistemas, las carpetas
  que empiezan por punto se consideran "de configuración".

Tarda unos segundos y no muestra nada si todo va bien. Puedes comprobar que
se ha creado con `ls -a`, que debería listar `.venv` entre las carpetas.

**Esto se hace una sola vez.** El entorno queda guardado en la carpeta y
sirve para siempre (o hasta que lo borres).

#### 3.4 Activar el entorno (cada vez que abras una terminal)

```bash
source .venv/Scripts/activate
```

**Qué hace "activar":** cambia, solo en esa terminal, a qué Python se
refiere la palabra `python`. Antes de activar, `python` es el Python
general del ordenador; después, es el de `.venv`. Lo mismo pasa con `pip`.
Así, todo lo que instales o ejecutes va al entorno del proyecto.

**Cómo saber que está activo:**

- La línea de Git Bash empieza por `(.venv)`:

  ```
  (.venv) NB30006@LT301102 MINGW64 /c/dev/Research (main)
  ```

- Y este comando muestra la ruta del Python que se está usando, que debe
  estar dentro de `.venv`:

  ```bash
  which python
  # → /c/dev/Research/.venv/Scripts/python
  ```

**La activación solo dura lo que dura la terminal.** Si cierras Git Bash y
abres otra, el entorno ya no está activo y hay que volver a ejecutar
`source .venv/Scripts/activate`. El entorno sigue existiendo (la carpeta no
se borra); solo hay que "volver a entrar".

**Desactivar:** si quieres volver al Python general sin cerrar la
terminal, escribe `deactivate`.

**Si usas otra terminal** (el comando cambia según el tipo):

| Terminal | Comando para activar |
|---|---|
| Git Bash | `source .venv/Scripts/activate` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Símbolo del sistema (CMD) | `.venv\Scripts\activate.bat` |

En PowerShell, Windows puede bloquear la activación por su política de
ejecución de scripts; en un portátil de empresa puede que no se permita
cambiarla. Con Git Bash no pasa, así que es la opción recomendada.

#### 3.5 Que VS Code use el entorno

VS Code también tiene que saber qué Python usar, para que su terminal y su
detección de errores trabajen con los paquetes del entorno:

1. Abre la carpeta `c:\dev\Research` en VS Code.
2. Pulsa **Ctrl + Shift + P**, escribe **Python: Select Interpreter** y
   elígelo.
3. En la lista, elige el que tiene la ruta `.\.venv\Scripts\python.exe`
   (suele aparecer marcado como *Recommended*).

A partir de ahí, las terminales nuevas que abras dentro de VS Code suelen
activar el entorno solas: verás el `(.venv)` al principio de la línea. Si
no aparece, actívalo a mano con el comando del punto 3.4.

#### 3.6 Instalar los paquetes del proyecto

Con el entorno **activo** (comprueba el `(.venv)`):

```bash
python -m pip install "psycopg[binary]" neo4j
```

Qué significa cada parte:

- `python -m pip` usa el `pip` del Python activo, es decir, el del entorno.
  Es más seguro que escribir solo `pip`, porque garantiza que los paquetes
  van al mismo Python que ejecutará los scripts.
- `install` descarga los paquetes de **PyPI** (el repositorio público de
  paquetes de Python) y los guarda en `.venv/Lib/site-packages`.
- `psycopg` es el conector para **PostgreSQL**. Lo de `[binary]` es un
  *extra*: pide la versión que trae ya incluidas las piezas compiladas que
  necesita, para no tener que instalar nada más en Windows. Va entre
  comillas porque Git Bash podría interpretar los corchetes.
- `neo4j` es el conector oficial para **Neo4j**.

`pip` también instala automáticamente las **dependencias** de esos
paquetes (otros paquetes que ellos necesitan), así que verás más nombres en
la salida de los que has pedido. Es normal.

**Anotar las dependencias.** En la raíz del proyecto hay un archivo
`requirements.txt` con los dos paquetes y **su versión exacta**:

```
psycopg[binary]==3.3.6
neo4j==6.4.1
```

(Las líneas que empiezan por `#` en el archivo real son comentarios, y
`pip` las ignora.)

Es la "lista de la compra" del proyecto: dice qué paquetes necesita. Este
archivo **sí** se sube a GitHub. En otro ordenador (o si un día recreas el
entorno), basta con:

```bash
python -m pip install -r requirements.txt
```

Las dependencias de estos dos paquetes (`psycopg-binary`, `tzdata` y
`pytz`) no hace falta escribirlas: `pip` las instala solo.

**Por qué `==`: en un benchmark, las condiciones tienen que ser siempre
las mismas.** `==` significa "exactamente esta versión". Sin él, `pip`
instala la versión **más reciente** que exista en el momento de instalar,
así que el mismo `requirements.txt` daría versiones distintas hoy y dentro
de seis meses.

En un proyecto normal eso suele dar igual. En este, no, porque el objetivo
es **comparar dos herramientas**, y una comparación solo es justa si lo
único que cambia es lo que se mide (ver "Qué significa *benchmark* para
este proyecto"). Los conectores forman parte del camino que recorre cada
consulta: Python → conector → base de datos → conector → Python. Si una
versión nueva de un conector es más rápida o más lenta, los tiempos
cambian, y no por PostgreSQL ni por Neo4j. Fijar las versiones evita tres
problemas:

1. **Comparaciones contaminadas.** Si a mitad del proyecto se actualiza el
   conector de Neo4j pero no el de PostgreSQL, las mediciones posteriores
   ya no comparan lo mismo que las anteriores.
2. **Resultados que no se pueden repetir.** Quien quiera comprobar los
   resultados, o tú mismo dentro de unos meses, necesita reconstruir
   exactamente el mismo entorno. Con `==`, `pip install -r
   requirements.txt` lo consigue siempre.
3. **Cambios que pasan desapercibidos.** Si un tiempo cambia de una
   medición a otra, hay que poder descartar que haya sido por una
   actualización. Con las versiones fijadas, se sabe que no.

Por la misma razón hay que anotar **todas** las versiones que intervienen,
no solo las de Python: la de PostgreSQL, la de Neo4j, la de Python (3.14)
y las de los conectores. Este comando muestra las versiones exactas de
todos los paquetes del entorno, dependencias incluidas:

```bash
python -m pip freeze
```

Si algún día se decide actualizar un conector, se cambia su versión en
`requirements.txt`, se anota el cambio, y **se repiten todas las
mediciones** con la versión nueva, para que todos los resultados se hayan
obtenido en las mismas condiciones.

#### 3.7 Comprobar que el entorno está bien

```bash
python -m pip list
```

debería mostrar `psycopg`, `psycopg-binary` y `neo4j` (entre otros). Y este
comando confirma que Python puede **importarlos** y muestra sus versiones:

```bash
python -c "import psycopg, neo4j; print('psycopg', psycopg.__version__); print('neo4j', neo4j.__version__)"
```

Si aparecen las dos versiones, el entorno está listo.

#### 3.8 Si algo falla

| Problema | Causa probable | Solución |
|---|---|---|
| `bash: .venv/Scripts/activate: No such file or directory` | No estás en la carpeta del proyecto, o el entorno no se creó | Ejecuta `cd /c/dev/Research` y comprueba con `ls -a` que existe `.venv`; si no, créalo (punto 3.3) |
| `ModuleNotFoundError: No module named 'psycopg'` (o `'neo4j'`) | El entorno no está activo, o los paquetes se instalaron en otro Python | Activa el entorno (punto 3.4), comprueba con `which python` y vuelve a instalar (punto 3.6) |
| No aparece el `(.venv)` en VS Code | VS Code no está usando el entorno | Elige el intérprete de `.venv` (punto 3.5) y abre una terminal nueva |
| PowerShell no deja activar el entorno | La política de ejecución de scripts de Windows | Usa Git Bash (punto 3.4) |
| El entorno se ha estropeado | Paquetes en mal estado o mezclados | Desactívalo (`deactivate`), borra la carpeta (`rm -rf .venv`) y vuelve a empezar desde el punto 3.3 |

#### 3.9 Resumen: la rutina de cada día

**Solo una vez** (ya hecho si has seguido los puntos anteriores):

```bash
cd /c/dev/Research
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

**Cada vez que abras una terminal para trabajar en el proyecto:**

```bash
cd /c/dev/Research
source .venv/Scripts/activate
```

Y comprobar que la línea empieza por `(.venv)` antes de ejecutar cualquier
script. Los scripts antiguos, que solo usan la biblioteca estándar,
funcionan igual dentro del entorno, así que puedes trabajar siempre con él
activo.

### Paso 4: pasar las contraseñas a Python sin escribirlas en el código

#### 4.1 La idea: variables de entorno

Las contraseñas no se escriben en el código de Python. Se guardan en
**variables de entorno**: valores que viven en la terminal mientras está
abierta, fuera del código. El proyecto usa dos:

| Variable | Contraseña de | Quién la lee |
|---|---|---|
| `PGPASSWORD` | el usuario `postgres` de PostgreSQL | PostgreSQL y `psycopg`, **automáticamente**: es un nombre estándar, así que el código ni siquiera la menciona |
| `NEO4J_PASSWORD` | el usuario `neo4j` de Neo4j | Nuestros scripts, con `os.environ["NEO4J_PASSWORD"]` |

Se podrían definir a mano con `export` cada vez que se abre una terminal,
pero es incómodo y fácil de olvidar. En su lugar, se guardan en un pequeño
script de bash que se carga con un solo comando.

#### 4.2 Por qué funciona: las variables se heredan

Cuando un programa arranca otro, el nuevo **recibe una copia de las
variables de entorno** del que lo lanzó. Si la terminal tiene definida
`NEO4J_PASSWORD`, cualquier script de Python que se ejecute desde ella la
hereda y puede leerla.

Pero hay que cargar el script de la forma correcta:

| Comando | Qué pasa |
|---|---|
| `source secrets.sh` | El script se ejecuta **dentro de tu terminal**. Las variables quedan definidas en ella, y todo lo que ejecutes después las hereda, hasta que cierres la terminal. **Esta es la forma correcta.** |
| `bash secrets.sh` | El script se ejecuta en **otro bash aparte**, que define las variables y termina enseguida. Tu terminal no las ve, y Python tampoco. |

#### 4.3 Los dos archivos

| Archivo | Qué contiene | ¿Se sube a GitHub? |
|---|---|---|
| `secrets.example.sh` | Una **plantilla** con las dos variables y valores de ejemplo, sin contraseñas reales | **Sí**: así se sabe qué variables hacen falta |
| `secrets.sh` | Las **contraseñas reales** | **Nunca**: está en el `.gitignore` |

#### 4.4 Crear tu `secrets.sh` (solo una vez)

1. Copia la plantilla:

   ```bash
   cp secrets.example.sh secrets.sh
   ```

   > ⚠️ **No edites ni renombres `secrets.example.sh`.** Es la plantilla, y
   > se sube a GitHub a propósito, sin contraseñas, para que se sepa qué
   > variables hacen falta. Las contraseñas reales van **solo en la copia**,
   > `secrets.sh`. El `.gitignore` bloquea exactamente ese nombre
   > (`/secrets.sh`), no todo lo que empiece por `secrets`: por eso la
   > plantilla sí se sube y la copia no.

2. Abre `secrets.sh` en VS Code y cambia los dos valores de ejemplo por
   tus contraseñas reales, dejando las comillas simples:

   ```bash
   export PGPASSWORD='...'
   export NEO4J_PASSWORD='...'
   ```

3. Comprueba que git lo ignora:

   ```bash
   git check-ignore -v secrets.sh
   ```

   Debería responder con la línea del `.gitignore` que lo ignora
   (`/secrets.sh`). Y `git status` **no** debería mostrar `secrets.sh` como
   archivo nuevo.

#### 4.5 Precauciones con las contraseñas

- **Escríbelas directamente en `secrets.sh`.** No las pegues en chats,
  correos, notas ni en ningún otro archivo del proyecto. Una contraseña que
  ha quedado escrita en otro sitio ya no se debe considerar secreta: si
  pasa, cámbiala.
- **Usa una contraseña distinta para cada base de datos**, larga y difícil
  de adivinar, y guárdalas en un gestor de contraseñas.
- **Si `secrets.sh` llegara a subirse a GitHub,** aunque se borre después,
  queda en el historial de git. En ese caso, hay que cambiar las dos
  contraseñas.
- **Para cambiarlas:** en PostgreSQL, desde pgAdmin (**Login/Group Roles**
  → **postgres** → **Properties** → **Definition**); en Neo4j, desde Neo4j
  Browser, con `:use system` y después
  `ALTER CURRENT USER SET PASSWORD FROM '...' TO '...';`. Luego actualiza
  `secrets.sh`.

#### 4.6 La rutina de cada día, completa

Cada vez que abras una terminal para trabajar en el proyecto:

```bash
cd /c/dev/Research
source .venv/Scripts/activate     # el Python del proyecto
source secrets.sh                 # las contraseñas
```

Para comprobar que las contraseñas están cargadas **sin mostrarlas en
pantalla**:

```bash
[ -n "$PGPASSWORD" ] && echo "PGPASSWORD cargada"
[ -n "$NEO4J_PASSWORD" ] && echo "NEO4J_PASSWORD cargada"
```

(`-n` comprueba que la variable no está vacía; así no se escribe su valor
en la terminal.)

#### 4.7 Un atajo: `run.sh`, que lo prepara todo y ejecuta Python

La rutina del punto 4.6 funciona, pero son tres comandos cada vez, y si se
olvida uno (activar `.venv` o cargar `secrets.sh`), el script de Python
falla con un error poco claro. Por eso el proyecto tiene un pequeño script
de bash, **`run.sh`**, en la raíz, que hace todo de una vez:

```bash
./run.sh scripts/check_connections.py
```

Por dentro, `run.sh` hace esto, en orden:

1. **Se sitúa en la carpeta del proyecto**, la llames desde donde la
   llames.
2. **Comprueba que todo está en su sitio** y, si no, se para con un
   mensaje claro:
   - si no le has dicho qué script ejecutar, muestra cómo usarlo;
   - si no existe `.venv`, dice cómo crearlo (paso 3);
   - si no existe `secrets.sh`, dice cómo crearlo (punto 4.4);
   - si `secrets.sh` todavía tiene las contraseñas de ejemplo de la
     plantilla, avisa de que hay que cambiarlas.
3. **Activa el entorno virtual** (`source .venv/Scripts/activate`).
4. **Carga las contraseñas** (`source secrets.sh`).
5. **Ejecuta Python** con el script que le hayas pasado y sus opciones, si
   las tiene. Python **hereda** las contraseñas de `run.sh` (punto 4.2).

**Por qué es mejor que cargar las contraseñas en tu terminal:**

| | Rutina del punto 4.6 | `./run.sh` |
|---|---|---|
| Comandos cada vez | 3 | 1 |
| Si se olvida algo | Python falla con un error confuso | `run.sh` para y explica qué falta |
| Dónde viven las contraseñas | En tu terminal, hasta que la cierres | Solo mientras corre el script; al terminar, desaparecen |

**Cómo llegan las contraseñas a Python sin pasar por tu terminal.** Este
último punto es el de la idea original: las contraseñas se quedan **fuera
del código de Python**, en un script de bash, y Python las **hereda** al
ser lanzado desde él. Para entenderlo bien hay que ver qué programas se
ponen en marcha, y en qué orden, cuando escribes
`./run.sh scripts/check_connections.py`:

```
Tu terminal (Git Bash)                  ← no tiene las contraseñas, ni antes ni después
 └── lanza run.sh  → un bash NUEVO, hijo de tu terminal
       ├── source .venv/Scripts/activate  → activa el entorno DENTRO de este bash hijo
       ├── source secrets.sh              → carga las contraseñas DENTRO de este bash hijo
       └── exec python scripts/check_connections.py
             └── Python ocupa el lugar del bash hijo y HEREDA sus variables:
                 el entorno activado y las dos contraseñas
                       ↓
             Python termina → el proceso desaparece, y con él las contraseñas
```

Paso a paso:

1. **Tu terminal lanza `run.sh` como un programa nuevo**, un bash *hijo*.
   El hijo recibe una copia de las variables de tu terminal (punto 4.2),
   pero tu terminal no recibirá nunca nada de vuelta: la herencia solo va
   de padre a hijo, nunca al revés.
2. **Dentro del hijo, `run.sh` sí usa `source`**, dos veces: para activar
   `.venv` y para cargar `secrets.sh`. Con `source`, esos scripts se
   ejecutan *dentro* del bash hijo, así que las contraseñas quedan
   definidas en él (no en un bash aparte que se cierra enseguida).
3. **Al final, `run.sh` lanza Python con `exec`.** `exec` hace que Python
   **ocupe el lugar** del bash hijo, en vez de crear un proceso más. Python
   hereda todo lo que el hijo tenía definido: el entorno virtual activado y
   las dos contraseñas. Por eso `psycopg` encuentra `PGPASSWORD` y el
   script encuentra `NEO4J_PASSWORD`.
4. **Cuando Python termina, su proceso desaparece**, y con él las
   contraseñas. Tu terminal sigue igual que antes: si escribes
   `echo "$NEO4J_PASSWORD"`, no sale nada.

**Por qué aquí no hace falta escribir `source run.sh`.** En el punto 4.2
vimos que `bash secrets.sh` no sirve: el bash aparte carga las contraseñas
y se cierra **sin lanzar nada**, así que nadie las aprovecha. Con `run.sh`
pasa justo lo contrario: el bash aparte carga las contraseñas **y además
lanza Python desde dentro**, así que Python las hereda antes de que ese
bash termine. El `source` sigue existiendo, pero está *dentro* de
`run.sh`, no en tu terminal.

**Por qué es la opción más segura de las que hemos visto:** las
contraseñas solo existen en la memoria **mientras corre el script**, y
solo en ese proceso. Ningún otro comando que ejecutes en tu terminal puede
verlas, y no se quedan cargadas cuando terminas.

**Sirve para cualquier script del proyecto,** presente o futuro. Lo que
escribas después del nombre del script se le pasa tal cual:

```bash
./run.sh scripts/check_connections.py
./run.sh scripts/summarize_data.py --top 10
```

(Los scripts antiguos no necesitan las contraseñas, pero funcionan igual
a través de `run.sh`.)

**Si `./run.sh` no funciona:** en Git Bash, un archivo que empieza por
`#!/usr/bin/env bash` se puede ejecutar directamente. Si aun así te dice
*Permission denied*, usa `bash run.sh scripts/check_connections.py`, que
hace exactamente lo mismo.

#### 4.8 ¿Y por qué no guardar las contraseñas dentro de `.venv`?

Es una idea que parece lógica: si el proyecto ya tiene su propio entorno
virtual, ¿por qué no meter ahí también las contraseñas? Por ejemplo,
añadiendo las dos líneas `export` al final de `.venv/Scripts/activate`, para
que se carguen al activar el entorno. Funcionaría, pero es peor que lo que
tenemos, por dos razones.

**1. Un entorno virtual aísla paquetes, no secretos.** `.venv` sirve para
que el proyecto tenga sus propias versiones de `psycopg` y `neo4j`. No
protege nada: es una carpeta de archivos normales en tu disco, que puede
leer cualquier programa que se ejecute con tu usuario de Windows,
exactamente igual que `secrets.sh`. Mover las contraseñas ahí no las hace
más seguras; solo cambia el archivo donde están.

**2. Tiene inconvenientes prácticos:**

| | Contraseñas en `.venv/Scripts/activate` | Lo que usamos (`secrets.sh` + `run.sh`) |
|---|---|---|
| ¿Fuera de GitHub? | Sí (`.venv` está en el `.gitignore`) | Sí (`secrets.sh` está en el `.gitignore`) |
| ¿Sobreviven si se recrea el entorno? | **No.** El entorno es desechable (punto 3.8: "borra `.venv` y vuelve a crearlo"), y las contraseñas se irían con él | **Sí.** `secrets.sh` no depende del entorno |
| ¿Cuánto tiempo están cargadas? | Mientras el entorno esté activo en la terminal, al alcance de **cualquier** comando que ejecutes en ella | **Solo mientras corre un script:** `run.sh` las carga, Python las hereda y desaparecen al terminar |
| ¿Fáciles de encontrar y entender? | No: escondidas dentro de un archivo generado, que nadie suele tocar | Sí: un archivo evidente, con una plantilla que lo documenta |

Las dos últimas filas son las importantes. `run.sh` ya ofrece la
**exposición mínima**: las contraseñas solo existen durante la ejecución de
un script.

**Regla:** cada herramienta, para lo suyo. `.venv` para los paquetes;
`secrets.sh` + `run.sh` para las contraseñas.

**¿Y en proyectos reales?** En proyectos profesionales, o con datos
sensibles, lo habitual es dar un paso más y usar un **gestor de secretos**
(*secret manager*): un servicio que guarda las contraseñas **cifradas** y
se las entrega solo al programa autorizado, sin que estén en ningún archivo
legible. En Windows existe uno incorporado, el **Administrador de
credenciales**, al que Python puede acceder con el paquete `keyring`; en la
nube, los proveedores ofrecen los suyos. Aquí no hace falta: es un proyecto
personal, con datos públicos, y las dos bases de datos solo aceptan
conexiones desde tu propio ordenador. Pero es la opción a considerar si el
proyecto llegara a manejar algo sensible.

### Paso 5: comprobar que Python llega a las dos bases de datos

El proyecto tiene un script para esto: **`scripts/check_connections.py`**
(con su explicación línea a línea en
[check_connections.py](check_connections.py), la copia anotada). Se conecta
a PostgreSQL y a Neo4j con las contraseñas de las variables de entorno y
muestra la versión de cada servidor.

**Cómo ejecutarlo**, con las dos bases de datos en marcha y tu
`secrets.sh` ya rellenado:

```bash
./run.sh scripts/check_connections.py
```

**Si todo va bien**, verás algo así (esta es la salida real de este
proyecto):

```
PostgreSQL OK: PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit
Neo4j OK: Neo4j Kernel 2026.10.0 (enterprise edition)
Neo4j OK: Cypher 5 ( edition)
Both databases are reachable.
```

Neo4j muestra **dos líneas** porque, en sus versiones recientes, la
consulta de versión devuelve dos componentes: el motor de la base de datos
(*Neo4j Kernel*) y la versión del lenguaje de consultas (*Cypher 5*). Esta
segunda no tiene edición, y por eso aparece el paréntesis vacío. No es un
error.

**Cómo funciona el script, en resumen:**

1. Comprueba que existen `PGPASSWORD` y `NEO4J_PASSWORD`. Si falta alguna,
   para y dice que hay que ejecutarlo a través de `run.sh`.
2. **PostgreSQL:** se conecta a la base `gharchive` como `postgres` y
   ejecuta `SELECT version();`. La contraseña la lee `psycopg` solo, de
   `PGPASSWORD`.
3. **Neo4j:** lee `NEO4J_PASSWORD`, se conecta a `neo4j://localhost:7687`
   como `neo4j` y ejecuta la misma consulta de versión que en Neo4j
   Browser (`CALL dbms.components() ...`).
4. Hace **las dos comprobaciones aunque una falle** (con `try`/`except`),
   para que un error en una no esconda el resultado de la otra.

**Si algo falla**, el script dice cuál de las dos y por qué:

| Mensaje | Causa probable | Solución |
|---|---|---|
| `Missing environment variable(s): ...` | Se ejecutó con `python` directamente, sin `run.sh` | Ejecútalo con `./run.sh scripts/check_connections.py` |
| `PostgreSQL FAILED: ... password authentication failed` | La contraseña de `secrets.sh` no es la de `postgres` | Corrige `PGPASSWORD` en `secrets.sh` |
| `PostgreSQL FAILED: ... Connection refused` | El servicio de PostgreSQL está parado | Arráncalo desde *Servicios* de Windows (ver el apartado de pgAdmin) |
| `PostgreSQL FAILED: ... database "gharchive" does not exist` | No se creó la base del proyecto | Créala (paso 1, punto 5, o desde pgAdmin) |
| `Neo4j FAILED: ... Unauthorized` | La contraseña de `secrets.sh` no es la de `neo4j` | Corrige `NEO4J_PASSWORD` en `secrets.sh` |
| `Neo4j FAILED: ... Couldn't connect` / `Unable to retrieve routing information` | La instancia de Neo4j no está arrancada | Arráncala en Neo4j Desktop (*Start*) |
| `ModuleNotFoundError: No module named 'psycopg'` | Falta el entorno virtual o sus paquetes | Revisa el paso 3 (`run.sh` ya activa `.venv`) |

Cuando aparezca `Both databases are reachable.`, **toda la cadena
funciona**: el entorno virtual, las contraseñas, los conectores y las dos
bases de datos. Es el punto de partida para crear las tablas y los nodos.

### Cómo sabe Python dónde está cada base de datos

Cuando `check_connections.py` funciona, surge una pregunta natural: ¿cómo
sabe Python dónde está cada base de datos? ¿Las busca solo por el
ordenador? ¿Cómo distingue cuál es PostgreSQL y cuál Neo4j?

**La respuesta corta: no busca nada. Se lo decimos nosotros**, con una
dirección exacta para cada una, escrita al principio del script:

```python
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
```

#### Las tres piezas de una dirección

Para conectarse a una base de datos hacen falta tres cosas, igual que para
llegar a una tienda dentro de un centro comercial:

| Pieza | En el centro comercial | En la base de datos | PostgreSQL | Neo4j |
|---|---|---|---|---|
| **Máquina** (*host*) | El edificio | El ordenador donde corre el servidor | `localhost` | `localhost` |
| **Puerto** | El número del local | La "puerta" por la que escucha ese servidor | `5432` | `7687` |
| **Protocolo** | El idioma que hablan dentro | El "idioma" con el que se comunican cliente y servidor | El de PostgreSQL | *Bolt* (el de Neo4j) |

**1. La máquina: `localhost`.** Es un nombre especial que siempre
significa **"este mismo ordenador"** (su dirección numérica es
`127.0.0.1`, la que aparece en Neo4j Desktop como *Connection URI*). Por
eso la conexión nunca sale a internet: Python y las dos bases de datos
están en tu portátil.

**2. El puerto: el número de la puerta.** Un ordenador puede tener muchos
programas esperando conexiones a la vez; cada uno "escucha" en un número de
puerto distinto, y así no se mezclan. Al instalar, cada servidor ocupó el
suyo:

- **PostgreSQL** escucha en el **5432** (el que aceptaste en el
  instalador).
- **Neo4j** escucha en el **7687** para los programas (protocolo *Bolt*) y
  en el **7474** para el navegador (Neo4j Browser).

En el script de PostgreSQL no aparece el `5432`: cuando no se indica,
`psycopg` usa ese puerto por defecto. En el de Neo4j sí aparece, dentro de
la dirección `neo4j://localhost:7687`.

**3. El protocolo: cada conector habla un solo idioma.** Aquí está la
respuesta a "¿cómo sabe si es PostgreSQL o Neo4j?": **lo decide qué
conector usamos**.

- `psycopg.connect(...)` solo sabe hablar el idioma de PostgreSQL, así que
  solo puede conectarse a un servidor PostgreSQL.
- `GraphDatabase.driver(...)` solo sabe hablar *Bolt*, el idioma de Neo4j.
  El `neo4j://` del principio de la dirección lo indica.

Si por error se apuntara `psycopg` al puerto de Neo4j, no "encontraría"
otra cosa: la conexión fallaría, porque el servidor del otro lado no
entiende el idioma.

#### Qué tiene que estar funcionando en tu ordenador

Para que la conexión funcione, **el servidor tiene que estar en marcha y
escuchando en su puerto**:

| Servidor | Qué lo mantiene en marcha | Si no está en marcha |
|---|---|---|
| PostgreSQL | Un **servicio de Windows**, que arranca solo al encender el ordenador | `Connection refused` (nadie contesta en el 5432) |
| Neo4j | La instancia `gharchive`, arrancada en **Neo4j Desktop** | `Couldn't connect` (nadie contesta en el 7687) |

#### El resto de los datos de conexión

Una vez dentro del servidor, faltan dos datos más:

- **Con qué usuario** se entra: `postgres` en PostgreSQL y `neo4j` en
  Neo4j. La contraseña de cada uno llega por las variables de entorno
  (paso 4).
- **Qué base de datos** se usa, porque un servidor puede tener varias:
  - En PostgreSQL lo dice `dbname="gharchive"`.
  - En Neo4j, el script todavía no lo indica, así que se usa la base por
    defecto de la instancia (`neo4j`). Tu instancia también tiene una base
    `gharchive`; cuando se decida en cuál se trabaja, se indicará en los
    scripts que carguen los datos.

#### Si un día las bases de datos estuvieran en otro sitio

Solo habría que cambiar la dirección: por ejemplo, poner el nombre de otro
ordenador en lugar de `localhost`, o el puerto que use ese servidor. Nada
más del código cambiaría. Por eso las direcciones están juntas, como
constantes, al principio del script.

La salida de `check_connections.py` confirma todo esto: la línea de
PostgreSQL dice `on x86_64-windows` (es tu ordenador con Windows), y la de
Neo4j muestra la versión de la instancia que tienes arrancada en Neo4j
Desktop.

### Lista de comprobación

| Comprobación | Cómo | Resultado esperado |
|---|---|---|
| PostgreSQL instalado | `psql -U postgres -c "SELECT version();"`, o `SELECT version();` en el Query Tool de pgAdmin | La versión de PostgreSQL |
| Base `gharchive` creada | `psql -U postgres -d gharchive -c "SELECT 1;"`, o `SELECT 1;` en el Query Tool de pgAdmin con `gharchive` seleccionada | Una tabla con un `1` |
| Neo4j en marcha | `RETURN 1;` en Neo4j Browser | `1` |
| Entorno virtual activo | La línea de Git Bash empieza por `(.venv)` | — |
| Conectores instalados | `python -m pip show psycopg neo4j` | Información de los dos paquetes |
| Python llega a las dos | `./run.sh scripts/check_connections.py` | `PostgreSQL OK: ...`, `Neo4j OK: ...` y `Both databases are reachable.` |

**Anota las versiones instaladas** (de PostgreSQL, de Neo4j y de los dos
paquetes de Python). Forman parte de las condiciones del benchmark: para
que alguien pueda repetir el experimento, tiene que saber con qué versiones
se hizo.


## Etapa de extracción (extract_csv.py)

Con las dos bases de datos instaladas y comprobadas, el siguiente paso es
llenarlas. Antes de cargar nada, hay que preparar los datos que van a
recibir.

### Dos decisiones tomadas antes de empezar

1. **Las dos bases de datos se llaman `gharchive`:** la base de PostgreSQL
   y, dentro de la instancia de Neo4j, la base de datos `gharchive` (no la
   `neo4j` que viene por defecto). Así queda claro dónde están siempre los
   datos del proyecto, en los dos lados.
2. **Una sola conexión por par actor–repo, sin repetir.** Si ana hace 10
   push al mismo repo, la tabla de conexiones tiene **una sola fila** con
   el `id` de ana y el del repo. Lo que importa para recorrer el grafo es
   *si* ana está conectada con ese repo, no *cuántas veces*. Esta decisión
   se aplica igual en los dos lados (ver el principio de diseño "la
   consulta primero").

### Por qué un paso de extracción aparte: una sola fuente para los dos lados

El trabajo se reparte en tres scripts:

| Script | Qué hace |
|---|---|
| `extract_csv.py` (este) | Lee el JSON **una sola vez** y escribe tres archivos CSV |
| `load_postgres.py` (siguiente) | Carga esos CSV en PostgreSQL |
| `load_neo4j.py` (siguiente) | Carga **los mismos** CSV en Neo4j |

La extracción va aparte porque es la garantía de una comparación justa:
**las dos bases de datos se cargan desde los mismos archivos**, así que es
imposible que una acabe con datos distintos de la otra. Si cada carga
leyera el JSON por su cuenta, cualquier diferencia entre los dos scripts
(un filtro de bots distinto, un caso especial tratado de otra forma)
cambiaría los datos de un solo lado.

### Qué es un archivo CSV

**CSV** (*comma-separated values*, "valores separados por comas") es una
tabla en texto plano: cada línea es una fila, las comas separan las
columnas, y la primera línea (la **cabecera**) da los nombres de las
columnas:

```
id,login
19,brynary
452,yrashk
```

Es el formato más sencillo para pasar tablas entre programas, y tanto
PostgreSQL (con `COPY`) como Neo4j (con `LOAD CSV`) lo cargan directamente.

### Los tres archivos

| Archivo | Columnas | Una fila por | Se convertirá en |
|---|---|---|---|
| `actors.csv` | `id`, `login` | cada actor | la tabla `actor` / los nodos `:Actor` |
| `repos.csv` | `id`, `name` | cada repo | la tabla `repo` / los nodos `:Repo` |
| `actor_repo.csv` | `actor_id`, `repo_id` | cada par actor–repo, sin repetir | la tabla `actor_repo` / las aristas entre `:Actor` y `:Repo` |

Se guardan en `data/csv/`. Como todo lo que hay en `data/`, **no se suben a
GitHub** (`data/` está en el `.gitignore`): se pueden volver a generar en
cualquier momento ejecutando el script.

### Qué hace el script

1. **Lee cada evento** del archivo JSON, una línea cada vez.
2. **Descarta los bots** (logins que terminan en `[bot]`), con la misma
   regla que `summarize_data.py`.
3. **Guarda cada actor y cada repo una sola vez, por su `id`**, con su
   nombre más reciente (ver abajo).
4. **Guarda cada par `(actor_id, repo_id)` en un conjunto (`set`)**. Un
   conjunto no admite repetidos, así que el mismo par añadido diez veces
   se queda una sola vez: así se cumple la decisión de no repetir
   conexiones.
5. **Escribe los tres CSV ordenados por `id`**, para que el mismo JSON
   produzca siempre exactamente los mismos archivos.

### Lo que encontramos en los datos: por qué los `id` y no los nombres

Antes de escribir el script comprobamos si algún `id` aparecía con más de
un nombre. Pasa en tres casos, y un mismo nombre aparece con dos `id`:

| Caso | Qué pasa | Qué hace el script |
|---|---|---|
| Actor `321725054` | Cambió su login durante esa hora: `lucky521-png` → `peitongshi` | Una sola fila, con el nombre más reciente: `peitongshi` |
| Repo `1348625135` | Se renombró junto con su dueño: `lucky521-png/niulai-chinese` → `peitongshi/niulai-chinese` | Una sola fila: `peitongshi/niulai-chinese` |
| Repo `1348068959` | Se renombró: `xuange520/HyperArmor` → `xuange520/HyperArmor-skill` | Una sola fila: `xuange520/HyperArmor-skill` |
| Login `Copilot` | Dos cuentas distintas con el mismo nombre (`175728472` y `198982749`) | Dos filas, una por `id` |

Si se usaran los nombres como claves, el primer caso contaría como dos
personas, los renombrados como dos repos, y las dos cuentas `Copilot` se
mezclarían en una. Con los `id`, los cuatro casos se tratan bien. Por la
misma razón, **el `login` no puede ser único** en la tabla `actor`: dos
filas pueden compartirlo.

### Cómo ejecutarlo

```bash
./run.sh scripts/extract_csv.py
```

(Este script no usa las bases de datos ni las contraseñas, así que
también funciona con `python scripts/extract_csv.py` y el entorno virtual
activo. Pasar por `run.sh` es lo más cómodo: siempre igual.)

Resultado para la hora fija del proyecto:

```
Skipped 1970 bot events. Writing to C:\dev\Research\data\csv:
  actors.csv         14515 rows
  repos.csv          14995 rows
  actor_repo.csv     15053 rows
```

### Qué dicen estas cifras

- **Los actores (14.515) y los repos (14.995) coinciden exactamente** con
  el "análisis sin bots" de `summarize_data.py`. Es una buena
  comprobación: los dos scripts aplican la misma regla y llegan al mismo
  resultado.
- **67.459 eventos sin bots se convierten en solo 15.053 conexiones.** La
  mayoría de los eventos son la misma persona haciendo push varias veces
  a su propio repo; al no repetir conexiones, todos esos eventos cuentan
  como una sola. Son los datos que de verdad necesita el benchmark.
- **Hay apenas un poco más de conexiones que actores** (15.053 frente a
  14.515): casi cada actor está conectado con un solo repo. Es la
  fragmentación que ya vimos en "Resultados de conectividad", ahora en
  forma de datos listos para cargar.

**Comprobaciones hechas:** las cifras anteriores; los nombres más
recientes de los casos especiales; las dos filas de `Copilot`; que
ejecutar el script dos veces produce archivos **idénticos byte a byte**; y
que git ignora la carpeta `data/csv/`.

La explicación línea a línea está en la
[copia anotada](extract_csv.py). Lo nuevo en este script: el módulo `csv`,
las tuplas dentro de conjuntos y diccionarios, cómo quedarse con el valor
más reciente mientras se lee, y por qué se ordena la salida.
