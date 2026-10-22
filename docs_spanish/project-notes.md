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

### Concepto nuevo: las tuplas, y cómo se combinan con diccionarios y conjuntos

`extract_csv.py` usa por primera vez **tuplas**, y además metidas dentro
de diccionarios, de conjuntos y de otra tupla. Su anotación de tipo
(`tuple[dict[int, tuple[str, str]], ...]`) parece un trabalenguas, pero
son solo tres piezas pequeñas.

**Qué es una tupla.** Un grupo fijo de valores que van juntos, entre
paréntesis. Se puede pensar como una **ficha con casillas**: el número de
casillas no cambia, y cada casilla significa algo por su **posición**:

```python
ficha = ("2026-08-27T15:35:35Z", "peitongshi")
ficha[0]    # "2026-08-27T15:35:35Z"  ← la fecha
ficha[1]    # "peitongshi"            ← el nombre
```

Se parece a una lista, pero **no se puede cambiar** después de crearla.

**Las tres estructuras del script, con datos reales:**

| Estructura | Qué es | Ejemplo | Anotación de tipo |
|---|---|---|---|
| `actors` | Diccionario: `id` → ficha *(fecha, nombre)* | `{321725054: ("2026-08-27T15:35:35Z", "peitongshi"), ...}` | `dict[int, tuple[str, str]]` |
| `repos` | Igual que `actors`, con repos | `{1348625135: ("...", "peitongshi/niulai-chinese"), ...}` | `dict[int, tuple[str, str]]` |
| `pairs` | Conjunto de fichas *(actor_id, repo_id)*: **una ficha = una conexión** | `{(321725054, 1348625135), (19, 1310070394), ...}` | `set[tuple[int, int]]` |

- En `actors` y `repos` se guarda la **fecha** junto al nombre para poder
  quedarse con el nombre más reciente.
- En `pairs`, el **conjunto** es lo que impide repetir conexiones: si se
  añade diez veces la misma ficha, se guarda una sola vez.
- ¿Por qué fichas-tupla y no listas dentro del conjunto? Un conjunto solo
  acepta elementos que **no pueden cambiar** (si cambiaran después de
  entrar, ya no podría saber si están repetidos). Las tuplas no cambian;
  las listas sí. Por eso `(19, 1310070394)` vale y `[19, 1310070394]` no.

**La ficha grande.** Una función solo puede devolver **una** cosa. Para
devolver cuatro, `extract()` las mete en una tupla de cuatro casillas, y
`main()` la abre y reparte las casillas en cuatro variables:

```python
return actors, repos, pairs, skipped_bot_events                    # en extract()
actors, repos, pairs, skipped_bot_events = extract(args.file)      # en main()
```

**La anotación de tipo, leída por partes:**

```python
-> tuple[                               # devuelve una ficha de 4 casillas:
    dict[int, tuple[str, str]],         #   1. actors: id → (fecha, nombre)
    dict[int, tuple[str, str]],         #   2. repos:  id → (fecha, nombre)
    set[tuple[int, int]],               #   3. pairs:  conjunto de (actor_id, repo_id)
    int,                                #   4. skipped_bot_events: un número
]
```

En resumen: solo hay **dos tipos de ficha pequeña**, *(fecha, nombre)* y
*(actor, repo)*, y **una ficha grande** que agrupa las cuatro cosas para
devolverlas juntas. La [copia anotada](extract_csv.py) tiene el mismo
dibujo justo encima de `extract()`.


## Etapa de carga (load_postgres.py y load_neo4j.py)

Con los tres CSV preparados por `extract_csv.py`, el siguiente paso es
**llenar las dos bases de datos** con ellos. Lo hacen dos scripts, uno por
base de datos, que leen **exactamente los mismos archivos**:

| Script | Carga los CSV en | Con qué lenguaje |
|---|---|---|
| `load_postgres.py` | PostgreSQL, base `gharchive` | SQL |
| `load_neo4j.py` | Neo4j, base `gharchive` | Cypher |

Van separados porque cada base de datos tiene su propio lenguaje y su
propia forma de cargar datos, y porque así, si una carga falla, se puede
repetir solo esa.

### Lo que se crea en cada base de datos

| Concepto | PostgreSQL | Neo4j |
|---|---|---|
| Actor | tabla `actor` (`id` BIGINT, `login` TEXT) | nodos `:Actor` (`id`, `login`) |
| Repo | tabla `repo` (`id` BIGINT, `name` TEXT) | nodos `:Repo` (`id`, `name`) |
| Conexión | tabla `actor_repo` (`actor_id`, `repo_id`) | aristas `(:Actor)-[:INTERACTED_WITH]->(:Repo)` |
| Identificador único | `PRIMARY KEY` en `actor.id` y `repo.id` | restricción `UNIQUE` en `Actor.id` y `Repo.id` |
| Sin conexiones repetidas | `PRIMARY KEY (actor_id, repo_id)` | Garantizado por el CSV, que ya no tiene pares repetidos |
| Conexiones que apuntan a algo que existe | `REFERENCES` (claves foráneas) | Cada arista se crea **buscando** antes sus dos nodos |

Algunos detalles:

- **Los `id` son números en los dos lados:** `BIGINT` en PostgreSQL y
  enteros en Neo4j. Un CSV es texto, así que `load_neo4j.py` convierte los
  `id` a números antes de enviarlos. Si un lado los guardara como texto y
  el otro como números, los datos no serían realmente idénticos.
- **`BIGINT` y no `INTEGER`:** un `INTEGER` llega hasta unos 2.100
  millones, y los `id` de GitHub ya superan esa cifra en algunos casos.
- **El `login` no es único**, por las dos cuentas `Copilot` que vimos en
  la etapa de extracción.
- **Por qué la arista se llama `INTERACTED_WITH`** ("interactuó con") y no
  algo como "contribuyó a": las conexiones salen de cualquier tipo de
  evento (push, comentarios, estrellas...), y dar una estrella o comentar
  no es contribuir. Un nombre neutro es más exacto.

### Los índices: la "ayuda normal" de cada lado

**Qué es un índice.** Un índice es una estructura extra que la base de
datos guarda **junto a** una tabla, para encontrar filas **sin tener que
leerlas todas**. Funciona como el índice alfabético al final de un libro:
para encontrar la palabra "recursividad" en un libro de 800 páginas, en
lugar de leer las 800 páginas, la buscas en el índice (que está ordenado
alfabéticamente, así que se encuentra enseguida) y ves que está en la
página 312. El índice no contiene el libro: contiene **cada palabra y
dónde encontrarla**.

En una base de datos es igual. Por ejemplo, el índice de `actor.id` guarda
**cada `id`, ordenado, y dónde está su fila** en el disco:

- **Sin índice**, para encontrar el actor `321725054`, PostgreSQL tendría
  que leer las 14.515 filas de `actor` una a una y comparar cada `id`. Se
  llama **recorrido secuencial** (*sequential scan*).
- **Con índice**, va directamente a la fila. Se llama **recorrido por
  índice** (*index scan*).

Por dentro, PostgreSQL organiza sus índices como un **árbol B**
(*B-tree*), una estructura que permite encontrar un valor en **muy pocos
pasos** aunque la tabla tenga millones de filas. Cómo funciona
exactamente, con un ejemplo paso a paso, está explicado más abajo, en
"Qué es un índice, más a fondo".

**Lo que cuesta un índice:** ocupa espacio en el disco, y cada vez que se
inserta una fila hay que actualizar también los índices de esa tabla, así
que las cargas son un poco más lentas. Por eso no se pone un índice en
todas las columnas, sino solo en las que se usan para **buscar** o para
**unir tablas**. (La parte "Conceptos clave", justo debajo, lo
explica con más detalle, con ejemplos de `EXPLAIN`.)

En el principio de diseño ("la consulta primero") se fijó una regla: dar a
cada lado **sus ayudas normales, ni más ni menos**. Para PostgreSQL, eso
son estos índices:

| Índice | Cómo se crea | Para qué sirve en el recorrido |
|---|---|---|
| `actor.id` | Automáticamente, por la `PRIMARY KEY` | Encontrar un actor por su `id` al instante |
| `repo.id` | Automáticamente, por la `PRIMARY KEY` | Encontrar un repo por su `id` al instante |
| `(actor_id, repo_id)` | Automáticamente, por la `PRIMARY KEY` de `actor_repo` | **Actor → sus repos**: como `actor_id` va primero, sirve para buscar por actor |
| `repo_id` | A mano: `CREATE INDEX actor_repo_repo_id_idx` | **Repo → sus actores**: el sentido contrario, que el índice anterior no cubre |

**Por qué el índice de la clave primaria no sirve para los dos sentidos, y
hace falta un segundo índice: paso a paso**

**1. El recorrido usa `actor_repo` en dos sentidos distintos.** El recorrido
del benchmark, `actor → repo → actor → repo`, alterna dos preguntas
diferentes en cada salto:

| Salto | Pregunta | Búsqueda en `actor_repo` |
|---|---|---|
| actor → repo | "¿En qué repos ha hecho eventos **este actor**?" | Las filas con `actor_id = X` |
| repo → actor | "¿Qué actores han hecho eventos en **este repo**?" | Las filas con `repo_id = Y` |

Son dos búsquedas **por columnas distintas** de la misma tabla. La primera
busca por `actor_id`; la segunda, por `repo_id`.

**2. Un índice es una lista ordenada, y solo está ordenada de una forma.**
Como se explica más abajo ("Qué es un índice, más a fondo"), un índice es
una copia **ordenada** de los valores, y gracias a ese orden se puede
buscar "por la mitad", en muy pocos pasos. El índice de la clave primaria,
`(actor_id, repo_id)`, guarda **parejas** ordenadas **primero por
`actor_id`** y, cuando el `actor_id` es igual, por `repo_id`. Visto con
datos reales del benchmark, el índice se parece a esto (cada línea es una
fila de `actor_repo`, en el orden del índice):

```
posición   actor_id     repo_id
     1           19     1310070394
     2           19     1347511170
   ...
   384      1247371      444497690   ← LedgerHQ/ledger-live
   ...
  1884     33897120      444497690   ← LedgerHQ/ledger-live
   ...
  4652    175728472      ...         ← Copilot: su 1.ª fila
  4653    175728472      ...         ← Copilot
   ...                                  (24 filas seguidas)
  4655    175728472      444497690   ← Copilot, en LedgerHQ/ledger-live
   ...
  4675    175728472      ...         ← Copilot: su última fila
   ...
  5653    224024782      444497690   ← LedgerHQ/ledger-live
   ...
 15053          ...      ...
```

**3. Buscar por actor: las filas están juntas.** Para "¿en qué repos ha
hecho eventos `Copilot` (`actor_id` 175728472)?", PostgreSQL busca en el
índice "por la mitad" hasta llegar a la **primera** fila de ese actor (la
4.652) y, a partir de ahí, **lee seguido** hasta que el `actor_id` cambia
(la 4.675). Como el índice está ordenado por `actor_id`, todas las filas
de un mismo actor están **juntas**: son 24 filas consecutivas. Bajar por el
árbol una vez y leer un trozo seguido: muy rápido.

**4. Buscar por repo: las filas están repartidas por todas partes.** Para
"¿qué actores han hecho eventos en `LedgerHQ/ledger-live` (`repo_id`
444497690)?", las filas buscadas están en las posiciones **384, 1.884,
4.655 y 5.653**: repartidas por toda la tabla, cada una al lado de otros
repos de su actor. El índice está ordenado por `actor_id`, **no** por
`repo_id`, así que:

- **no se puede buscar "por la mitad"**: si abres el índice por el medio y
  encuentras el `repo_id` 1347511170, eso no te dice si el 444497690 está
  antes o después, porque los `repo_id` no siguen ningún orden a lo largo
  del índice;
- **no se sabe cuándo parar**: aunque encuentres una fila del repo, puede
  haber otras en cualquier otra parte.

La única forma de encontrarlas todas es **leer las 15.053 filas** y quedarse
con las que tienen ese `repo_id`. Es la diferencia entre buscar en una
guía telefónica a todos los que se apellidan "García" (están juntos) y a
todos los que se llaman "Ana" (están repartidos por toda la guía, y hay
que leerla entera).

**5. La regla del prefijo izquierdo.** Esto es una regla general de los
índices compuestos: un índice sobre `(A, B)` sirve para buscar por `A`, o
por `A` y `B` juntos, pero **no** para buscar solo por `B`. Solo sirve si
la búsqueda empieza por la **primera columna** del índice (su "prefijo
izquierdo"). Por eso el orden de las columnas de un índice compuesto
importa.

**6. La solución: un segundo índice, ordenado por `repo_id`.** El índice
`actor_repo_repo_id_idx` es otra lista ordenada de la misma tabla, esta
vez por `repo_id`. En él, las 4 filas de `LedgerHQ/ledger-live` están
**juntas**, igual que estaban juntas las de `Copilot` en el primero:

```
índice actor_repo_repo_id_idx (ordenado por repo_id)
   ...
   444497690   → fila con actor_id 1247371     ┐
   444497690   → fila con actor_id 33897120    │ las 4 filas de LedgerHQ/ledger-live,
   444497690   → fila con actor_id 175728472   │ ahora juntas
   444497690   → fila con actor_id 224024782   ┘
   ...
```

Con los dos índices, **cada sentido del recorrido tiene su propia lista
ordenada**, y los dos saltos son igual de rápidos. Es como tener dos guías
telefónicas de la misma ciudad: una ordenada por apellido y otra por
nombre.

**7. Cómo verlo con tus propios ojos.** Con `EXPLAIN` delante de una
consulta, PostgreSQL muestra qué índice usa:

```sql
-- Los repos de un actor: usa el índice de la clave primaria
EXPLAIN SELECT repo_id FROM actor_repo WHERE actor_id = 175728472;
--   ... Index ... using actor_repo_pkey on actor_repo ...

-- Los actores de un repo: usa el índice creado a mano
EXPLAIN SELECT actor_id FROM actor_repo WHERE repo_id = 444497690;
--   ... Index ... using actor_repo_repo_id_idx on actor_repo ...
```

Sin el segundo índice, la segunda consulta mostraría `Seq Scan on
actor_repo`: un recorrido secuencial, es decir, leer la tabla entera.

**8. Por qué importa tanto en el benchmark.** En un recorrido de varios
saltos, la búsqueda repo → actor no se hace una vez, sino **una vez por
cada repo** que llega del salto anterior. Sin el segundo índice, cada una
de esas búsquedas leería la tabla entera: con 100 repos en un salto, serían
100 lecturas de las 15.053 filas (o de las 424.098 de la pipeline de 24
horas). PostgreSQL saldría muchísimo peor parado, pero no porque el
modelo relacional sea peor, sino porque **le faltaría una ayuda normal**
que cualquier diseño sensato tendría.

**¿Y Neo4j?** No tiene este problema, y no necesita un índice para ningún
sentido: cada arista está guardada **junto a sus dos nodos**, así que un
nodo `Repo` ya sabe qué aristas le llegan, igual que un nodo `Actor` sabe
cuáles salen de él. Seguir una arista "hacia delante" o "hacia atrás"
cuesta lo mismo. Dar a PostgreSQL su segundo índice es lo que hace que la
comparación sea **justa**: cada base de datos, con sus herramientas
normales.

**¿Por qué no un solo índice sobre `repo_id`, en lugar del de la clave
primaria?** Porque entonces el problema sería el contrario: las filas de un
actor quedarían repartidas, y el salto actor → repo sería el lento. Además,
la clave primaria hace falta de todas formas, para impedir pares
repetidos. Con un índice para cada sentido, los dos saltos quedan
cubiertos.

**En Neo4j**, las restricciones de unicidad sobre `Actor.id` y `Repo.id`
crean su índice, igual que las claves primarias. Las aristas, en cambio,
**no necesitan índice**: en un grafo, cada nodo ya guarda enlaces directos
a sus propias aristas (*index-free adjacency*, "adyacencia sin índices").

> 🎯 **La idea central de todo el proyecto:** esa diferencia, **índices
> para unir tablas** (PostgreSQL) frente a **enlaces directos entre nodos**
> (Neo4j), es **justo lo que el benchmark quiere medir**. La pregunta de
> investigación es, en el fondo, en qué número de saltos y con qué volumen
> de datos una forma de encontrar las conexiones empieza a ser más rápida
> que la otra.

**`ANALYZE`.** Al terminar la carga, `load_postgres.py` ejecuta `ANALYZE`
sobre las tres tablas. Antes de ejecutar cada consulta, PostgreSQL decide
*cómo* hacerlo (¿usar un índice o leer la tabla entera?, ¿qué tabla
primero?), y para decidir bien usa estadísticas sobre los datos. Justo
después de una carga masiva esas estadísticas no están al día, y `ANALYZE`
las actualiza. También forma parte de las ayudas normales del lado
relacional.

### Conceptos clave: índices, claves primarias, claves foráneas y por qué un grafo no las necesita

Esta parte amplía la tabla **"Lo que se crea en cada base de datos"** y
la explicación de los índices de justo arriba: qué es exactamente cada
cosa, si hay índices o no, y por qué el grafo funciona de otra manera.
Son los conceptos centrales del proyecto, porque la pregunta de
investigación es justamente **cómo encuentra cada base de datos las
conexiones**.

#### Primero, la respuesta corta: ¿hay índices, o basta con las claves primarias?

**Hay índices.** Una `PRIMARY KEY` no es una alternativa a un índice:
**PostgreSQL crea automáticamente un índice** para cada clave primaria,
porque lo necesita para comprobar en cada inserción que el valor no está
repetido. Pero las claves primarias **no cubren todas las búsquedas**, y
las claves foráneas **no crean ningún índice** en PostgreSQL. Por eso hay
un índice más, creado a mano.

Esto es todo lo que existe en cada base de datos (en `gharchive` y en
`gharchive24h` es igual):

| Estructura | Base | Cómo se crea | ¿Crea un índice? | Para qué sirve |
|---|---|---|---|---|
| `PRIMARY KEY` de `actor` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Sí, automático:** `actor_pkey` | Que no haya dos actores con el mismo `id`, y encontrar un actor por su `id` al instante |
| `PRIMARY KEY` de `repo` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Sí, automático:** `repo_pkey` | Lo mismo, para los repos |
| `PRIMARY KEY` de `actor_repo` (`actor_id`, `repo_id`) | PostgreSQL | `PRIMARY KEY (actor_id, repo_id)` | **Sí, automático:** `actor_repo_pkey` (compuesto, de dos columnas) | Que no se repita ningún par, y buscar **los repos de un actor** |
| Clave foránea `actor_repo.actor_id` → `actor.id` | PostgreSQL | `REFERENCES actor (id)` | **No** | Que cada conexión apunte a un actor que existe |
| Clave foránea `actor_repo.repo_id` → `repo.id` | PostgreSQL | `REFERENCES repo (id)` | **No** | Que cada conexión apunte a un repo que existe |
| Índice sobre `actor_repo.repo_id` | PostgreSQL | `CREATE INDEX actor_repo_repo_id_idx` (a mano) | **Sí:** es el propio índice | Buscar **los actores de un repo**: el sentido que la clave primaria no cubre |
| Restricción `UNIQUE` en `Actor.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE a.id IS UNIQUE` | **Sí, automático** | Que no haya dos actores con el mismo `id`, y encontrar un actor por su `id` al instante |
| Restricción `UNIQUE` en `Repo.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE r.id IS UNIQUE` | **Sí, automático** | Lo mismo, para los repos |
| Las aristas `INTERACTED_WITH` | Neo4j | `CREATE (a)-[:INTERACTED_WITH]->(r)` | **No necesitan índice** | Cada nodo guarda enlaces directos a sus aristas (ver más abajo) |

**Resumen:** PostgreSQL tiene **4 índices** (tres automáticos por las
claves primarias y uno a mano), y Neo4j tiene **2** (los de las
restricciones). Las conexiones del grafo no tienen índice porque no lo
necesitan: esa diferencia es el corazón del benchmark.

**Cómo comprobarlo tú mismo:**

```sql
-- PostgreSQL (Query Tool de pgAdmin, base gharchive): los índices de las tres tablas
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('actor', 'repo', 'actor_repo')
ORDER BY tablename, indexname;
```

```cypher
// Neo4j (Query, base gharchive): las restricciones y los índices
SHOW CONSTRAINTS;
SHOW INDEXES;
```

En pgAdmin también se ven en el árbol: dentro de cada tabla, **Indexes**
(los índices) y **Constraints** (las claves primarias y foráneas). En
Neo4j, `SHOW INDEXES` muestra además dos índices que Neo4j crea siempre por
su cuenta (de tipo `LOOKUP`), que sirven para encontrar rápido "todos los
nodos con una etiqueta" o "todas las aristas de un tipo".

#### Qué es un índice, más a fondo

Lo básico (la analogía del libro, y el recorrido secuencial frente al
recorrido por índice) está explicado justo arriba, en "Los índices". Aquí
se va un paso más allá: cómo está hecho un índice por dentro, lo que
cuesta y cómo decide PostgreSQL si lo usa.

**Cómo está hecho por dentro: el árbol B (*B-tree*).** Para entenderlo
hacen falta tres ideas, una detrás de otra.

**Idea 1: buscar en algo ordenado es muchísimo más rápido.** Piensa en el
juego de "adivina el número del 1 al 100", en el que solo te responden
"más alto" o "más bajo". Si preguntas número a número (1, 2, 3...),
puedes necesitar 100 preguntas. Pero si preguntas siempre por la mitad
("¿50?" → "más alto"; "¿75?" → "más bajo"; "¿62?"...), cada pregunta
**descarta la mitad** de lo que queda, y lo encuentras en **7 preguntas
como mucho**. Eso solo funciona porque los números están **ordenados**.

| Valores ordenados | Preguntas "por la mitad", como mucho |
|---|---|
| 100 | 7 |
| 1.000 | 10 |
| 1.000.000 | 20 |

Una tabla sin índice es como una lista **desordenada**: no queda más
remedio que mirar fila por fila. Un índice es, ante todo, **una copia
ordenada de los valores de una columna**, cada uno con la dirección de su
fila.

**Idea 2: el disco se lee por páginas, no por valores.** Una base de datos
no lee los datos uno a uno: los lee del disco en bloques de tamaño fijo
llamados **páginas** (en PostgreSQL, de 8 KB). Leer una página del disco
es muchísimo más lento que comparar dos números en memoria. Así que lo que
de verdad hay que ahorrar no son comparaciones, sino **páginas leídas**. En
una página caben **cientos** de números como nuestros `id` (más o menos
unos 400).

**Idea 3: el árbol B junta las dos ideas.** Es una lista ordenada
repartida en páginas y organizada **en niveles**, como un árbol puesto
boca abajo:

- **Las hojas** (el nivel de abajo): páginas con los valores ordenados y,
  junto a cada uno, **la dirección de su fila** en la tabla (en qué página
  de la tabla está). Cada hoja está enlazada con la siguiente, para poder
  leer rangos seguidos.
- **La raíz** (arriba) **y los niveles intermedios**: páginas que no
  guardan filas, sino **"señales"**, como los carteles de un aeropuerto:
  "los `id` hasta 300.000.000, por aquí; del 300.000.001 al 330.000.000,
  por allá".

Buscar un valor es **bajar** desde la raíz siguiendo las señales hasta la
hoja correcta. Un ejemplo con la tabla `actor` del benchmark (14.515 `id`,
unas 37 hojas de unos 400 `id` cada una; los números de las señales y de
las páginas son inventados, solo para ilustrarlo):

```
Buscar el actor 321725054:

  1. Raíz (1 página leída):
     [ ... | hasta 300.000.000 → hoja 24 | hasta 330.000.000 → hoja 25 | ... ]
                                              │
                                              ▼
  2. Hoja 25 (1 página leída):
     [ ... 321.700.991 → fila en la página 81 | 321.725.054 → fila en la página 93 | ... ]
                                                              │
                                                              ▼
  3. Tabla actor, página 93 (1 página leída):
     id = 321725054, login = 'peitongshi'
```

**Tres páginas leídas**, frente a leer todas las páginas de la tabla
(alrededor de un centenar para 14.515 filas) sin índice. Y dentro de cada página, la
búsqueda del valor exacto se hace "por la mitad", como en el juego.

**Por qué el número de pasos crece tan despacio.** Esta es la parte más
importante del árbol B, y se entiende mejor con un árbol en miniatura.

**Paso 1: un árbol pequeño, de juguete.** Imagina que en cada página solo
cabe **3 valores** (en la realidad caben unos 400, pero con 3 se puede
dibujar). Cada casilla de la raíz es una señal que lleva a una página del
nivel de abajo:

```
Nivel 1 (raíz):        [  A  |  B  |  C  ]                       1 página
                         │     │     │
                ┌────────┘     │     └────────┐
                ▼              ▼              ▼
Nivel 2:   [ 1 | 2 | 3 ]  [ 4 | 5 | 6 ]  [ 7 | 8 | 9 ]           3 páginas
```

- Con **1 nivel** (solo la raíz) caben **3** valores.
- Con **2 niveles**, cada una de las 3 señales de la raíz lleva a una página
  con 3 valores: caben **3 × 3 = 9** valores.
- Con **3 niveles**, cada una de esas 9 casillas llevaría a otra página de 3:
  caben **9 × 3 = 27**.
- Con 4 niveles, **27 × 3 = 81**. Con 5, **243**...

Cada nivel nuevo **multiplica** por 3 lo que cabe, porque cada casilla del
nivel de arriba "abre" una página entera en el nivel de abajo. Es como un
árbol genealógico: cada generación multiplica el número de personas.

**Paso 2: buscar un valor cuesta "una página por nivel".** Para encontrar
el 8 en el dibujo, se lee la raíz (1 página), se elige la señal `C` y se
lee esa página del nivel 2 (otra página). **Dos niveles, dos páginas
leídas**, aunque haya 9 valores. Con 3 niveles serían tres páginas, aunque
haya 27 valores. El número de páginas que hay que leer **es el número de
niveles**, no el número de valores.

**Paso 3: lo mismo, con páginas de verdad.** En una página real de
PostgreSQL caben unos **400** `id`, no 3. Así que cada nivel multiplica por
**400**:

| Niveles del árbol | Cuántos valores caben | Cálculo | En este proyecto |
|---|---|---|---|
| 1 (solo la raíz) | unos 400 | 400 | — |
| 2 | unos 160.000 | 400 × 400 | `actor` del benchmark: 14.515 filas → **caben en 2 niveles** |
| 3 | unos 64 millones | 160.000 × 400 | `actor_repo` de la pipeline de 24 horas: 424.098 filas → **3 niveles** |
| 4 | unos 25.600 millones | 64 millones × 400 | más que todas las personas del planeta |

Y como cada búsqueda lee **una página por nivel**:

| Filas de la tabla | Páginas leídas **sin** índice (leer toda la tabla) | Páginas **del índice** leídas (una por nivel) |
|---|---|---|
| 14.515 (benchmark) | todas las de la tabla: un centenar | **2** |
| 424.098 (pipeline de 24 horas) | todas las de la tabla: unas dos mil | **3** |
| 64 millones | cientos de miles | **3** |
| 25.000 millones | más de cien millones | **4** |

(A eso se suma una página más, para leer la fila en la tabla, como en el
dibujo de antes: **3 páginas en total** para el benchmark.)

**Paso 4: la conclusión.** Pasar del benchmark (14.515 filas) a la
pipeline de 24 horas (424.098 filas) es tener **casi 30 veces más datos**,
pero buscar un valor solo cuesta **un nivel más**: una página más que
leer, de 2 a 3. Sin índice, en cambio, el trabajo se multiplicaría por 30.

**Lineal frente a logarítmico (las dos formas de crecer).** Hay dos formas
de que el trabajo crezca cuando crecen los datos:

- **Lineal:** si los datos se multiplican por 30, el trabajo también se
  multiplica por 30. Es lo que pasa al leer toda la tabla (sin índice): el
  doble de filas, el doble de trabajo.
- **Logarítmico:** si los datos se multiplican por 400, el trabajo solo
  **suma 1** (un nivel más). Es lo que pasa con el árbol B. El
  **logaritmo** responde a la pregunta "¿cuántas veces tengo que
  multiplicar por 400 para llegar a este número de filas?", y esa es
  justamente la cantidad de niveles: para 14.515 basta con 2 veces (400 ×
  400 ya es más que 14.515); para 424.098 hacen falta 3.

Por eso los índices son tan potentes en tablas grandes: los datos pueden
crecer muchísimo, y el coste de encontrar un valor apenas cambia.

**Un detalle más: la memoria.** Leer del **disco** es lento; leer de la
**memoria** (RAM) es muchísimo más rápido. La raíz y los niveles de arriba
se usan en **todas** las búsquedas, así que PostgreSQL los mantiene
normalmente **en memoria** (a esto se le llama **caché**). En la práctica,
muchas búsquedas solo tienen que ir al disco a por la hoja y la fila, o ni
siquiera eso, si también estaban en memoria.

**Por qué se llama "B" y por qué está siempre "equilibrado":** la "B" no
viene de "binario" (cada página tiene cientos de ramas, no dos). Lo
importante es que el árbol está siempre **equilibrado** (*balanced*):
todas las hojas están a la **misma profundidad**, así que cualquier
búsqueda cuesta lo mismo. Para mantenerlo así, cuando se inserta un valor
en una hoja que ya está llena, la base de datos la **parte en dos** y
añade una señal nueva en el nivel de arriba. Ese trabajo extra en cada
inserción es una de las razones por las que los índices hacen las cargas
más lentas (ver el siguiente apartado).

**El índice compuesto es lo mismo, ordenado por parejas.** El índice
`(actor_id, repo_id)` es un árbol B igual, pero sus valores son
**parejas**, ordenadas primero por `actor_id` y, a igualdad, por `repo_id`.
Por eso todas las filas de un mismo actor quedan **juntas en las hojas**
(se encuentran bajando una vez y leyendo seguido), mientras que las de un
mismo repo quedan **repartidas** por todas las hojas. Es la guía
telefónica de más arriba, vista por dentro.

**Lo que cuesta un índice.** No es gratis:

- **Espacio:** es una estructura más, guardada en el disco.
- **Escrituras más lentas:** cada vez que se inserta una fila, la base de
  datos tiene que actualizar también todos los índices de esa tabla. Por
  eso, en la pipeline de 24 horas (más abajo en estas notas), cargar `actor_repo` (con dos índices y
  dos claves foráneas) tardó 27 segundos, y `actor` o `repo` (con un solo
  índice) apenas uno.

Por eso no se pone un índice en cada columna: solo en las que se usan para
**buscar** o para **unir tablas**. Es el principio de "la consulta
primero" aplicado a los índices: `login` y `name` no tienen índice porque
las consultas del benchmark no buscan por ellos.

**El planificador decide si usa el índice.** Que exista un índice no
obliga a usarlo. Antes de ejecutar cada consulta, PostgreSQL calcula qué
es más barato (de ahí la importancia de `ANALYZE`, que le da las
estadísticas para calcularlo). Para ver qué ha decidido, se pone `EXPLAIN`
delante de la consulta:

```sql
EXPLAIN SELECT * FROM actor WHERE id = 321725054;
-- Index Scan using actor_pkey on actor ...     <- usa el índice de la clave primaria

EXPLAIN SELECT * FROM actor WHERE login = 'peitongshi';
-- Seq Scan on actor ... Filter: (login = ...)  <- no hay índice: lee la tabla entera
```

(En Neo4j, el equivalente es poner `EXPLAIN` o `PROFILE` delante de una
consulta Cypher.)

#### Qué es una clave primaria (*primary key*)

La **clave primaria** es la columna (o el grupo de columnas) que
**identifica cada fila de forma única**, como el número del documento de
identidad de una persona. Tiene tres reglas que la propia base de datos
hace cumplir:

1. **Única:** no puede haber dos filas con el mismo valor.
2. **Nunca vacía** (`NOT NULL`): toda fila tiene que tenerla.
3. **Solo una por tabla**, aunque puede estar formada por varias columnas.

**En este proyecto:**

- En `actor` y `repo`, la clave primaria es el `id` de GitHub. Es una
  **clave natural**: un identificador que ya viene en los datos, no uno
  inventado por nosotros (eso sería una *clave subrogada*, como un número
  correlativo 1, 2, 3...). Se eligió el `id` y no el nombre porque el
  nombre puede cambiar (el caso `lucky521-png` → `peitongshi`) y no es
  único (las dos cuentas `Copilot`).
- En `actor_repo`, la clave primaria es **compuesta**: el **par**
  `(actor_id, repo_id)`. Ninguna de las dos columnas es única por
  separado (un actor puede estar en muchos repos, y un repo puede tener
  muchos actores), pero el par sí. Es la propia base de datos la que hace
  cumplir la decisión de "una sola conexión por par actor–repo".

**Por qué es importante:**

- **Identidad:** cada fila se puede señalar sin ambigüedad.
- **Sin duplicados:** la base de datos rechaza cualquier inserción que
  repita una clave, aunque el error esté en nuestro código.
- **Destino de las claves foráneas:** es el valor al que apuntan las
  conexiones (ver abajo).
- **Búsqueda rápida:** su índice automático permite encontrar una fila por
  su clave al instante.

**El índice compuesto** de `actor_repo` está ordenado primero por
`actor_id` y después por `repo_id`. Por eso sirve para buscar los repos de
un actor, pero no los actores de un repo, y hizo falta el índice extra
sobre `repo_id` (ver, más arriba, la tabla de los dos sentidos del
recorrido y la analogía de la guía telefónica).

#### Qué es una clave foránea (*foreign key*)

Una **clave foránea** es una columna que **apunta a la clave primaria de
otra tabla**. En `actor_repo`:

- `actor_id` apunta a `actor.id`;
- `repo_id` apunta a `repo.id`.

Así es como una base de datos relacional **representa las relaciones**:
`actor_repo` no guarda el actor ni el repo, solo sus `id`, como
"referencias". Es una **tabla de unión** (*junction table*), la forma
estándar de representar una relación **muchos a muchos** (un actor puede
tener muchos repos, y un repo muchos actores).

**Para qué sirve: la integridad referencial.** La base de datos garantiza
que **toda referencia apunta a algo que existe**:

- No se puede insertar en `actor_repo` una conexión con un `actor_id` que no
  está en `actor`: PostgreSQL la rechaza. (Por eso `load_postgres.py` carga
  `actor` y `repo` **antes** que `actor_repo`.)
- No se puede borrar un actor de `actor` mientras alguna conexión lo
  señale, salvo que se diga explícitamente qué hacer con esas conexiones
  (por ejemplo, `ON DELETE CASCADE`, que las borraría también). Por eso
  `load_postgres.py` borra `actor_repo` **antes** que las otras dos.

Sin claves foráneas, un error en el código podría dejar conexiones
"huérfanas", que apuntan a actores o repos inexistentes, y los recorridos
darían resultados falsos sin que nadie lo notara.

**Lo que cuesta:** en cada inserción en `actor_repo`, PostgreSQL comprueba
que el actor **y** el repo existen, es decir, **dos búsquedas por fila**.
Es otra de las razones por las que esa tabla tarda más en cargarse.

**Ojo: una clave foránea no crea un índice** (en PostgreSQL). Es un error
muy común pensar que sí. La clave foránea comprueba que la referencia
existe, pero **no** acelera las búsquedas por esa columna. Si una columna
se usa para unir tablas, hay que indexarla aparte, como hicimos con
`repo_id`. (`actor_id` no lo necesita porque ya va primero en el índice de
la clave primaria compuesta.)

#### Clave primaria, índice normal y clave foránea: tres herramientas, tres trabajos

Al leer el esquema de `load_postgres.py` es fácil confundir estas tres
piezas, porque a veces aparecen en la misma columna. Cada una hace **un
trabajo distinto**:

| | Clave primaria (`PRIMARY KEY`) | Índice normal (`CREATE INDEX`) | Clave foránea (`REFERENCES`) |
|---|---|---|---|
| ¿Encuentra filas rápido? | ✅ Sí: crea un índice automáticamente | ✅ Sí: **para eso existe** | ❌ No: **no crea ningún índice** |
| ¿Obliga a que el valor sea único? | ✅ Sí | ❌ No: **permite valores repetidos** | ❌ No |
| ¿Obliga a que no esté vacío? | ✅ Sí (`NOT NULL` incluido) | ❌ No | ❌ No (en nuestras columnas lo hace el `NOT NULL` aparte) |
| ¿Comprueba que el valor existe en otra tabla? | ❌ No | ❌ No | ✅ Sí: **para eso existe** |
| ¿Cuántas por tabla? | Solo **una** (aunque puede tener varias columnas) | Todas las que haga falta | Todas las que haga falta |

En una frase: **la clave primaria identifica y encuentra; el índice solo
encuentra; la clave foránea solo comprueba**.

**Las tres en `actor_repo`, columna a columna:**

| Columna | Clave foránea | Clave primaria | Índice que la hace rápida |
|---|---|---|---|
| `actor_id` | ✅ Apunta a `actor.id` | **Parte** de la pareja `(actor_id, repo_id)` | El de la clave primaria (`actor_id` va primero) |
| `repo_id` | ✅ Apunta a `repo.id` | **Parte** de la pareja `(actor_id, repo_id)` | `actor_repo_repo_id_idx`, el índice normal creado a mano |

Ninguna de las dos columnas es clave primaria **por sí sola**. La clave
primaria es la **pareja**, y lo que no se puede repetir es la pareja
entera:

| `actor_id` | `repo_id` | ¿Se permite? |
|---|---|---|
| 175728472 (Copilot) | 444497690 (LedgerHQ/ledger-live) | ✅ |
| 1247371 | 444497690 (LedgerHQ/ledger-live) | ✅ Se repite el `repo_id`, pero la pareja es otra |
| 175728472 (Copilot) | 873328 (getsentry/sentry) | ✅ Se repite el `actor_id`, pero la pareja es otra |
| 175728472 (Copilot) | 444497690 (LedgerHQ/ledger-live) | ❌ **La pareja ya existe**: sería una conexión repetida |

**Por qué el índice de `repo_id` es un índice normal y no único.** El mismo
`repo_id` aparece **muchas veces** en `actor_repo`, una por cada actor que
ha hecho eventos en ese repo (`LedgerHQ/ledger-live` aparece 4 veces). Un
índice que obligara a que `repo_id` fuera único rechazaría la segunda fila
de cada repo compartido. Por eso es un índice **normal**: solo ayuda a
**encontrar rápido**, sin imponer ninguna regla. Es exactamente lo que
hace falta para el salto repo → actor.

**Por qué hacen falta las tres a la vez.** Cada una cubre un hueco que las
otras dejan:

- Sin la **clave primaria**, nada impediría guardar dos veces la misma
  conexión.
- Sin la **clave foránea**, nada impediría guardar una conexión con un
  actor o un repo que no existe.
- Sin el **índice de `repo_id`**, el salto repo → actor tendría que leer la
  tabla entera.

(En Neo4j, como se explica más abajo, las tres necesidades se cubren de
otra forma: las restricciones de unicidad hacen el papel de las claves
primarias, y una arista no puede existir sin sus dos nodos, así que no
hace falta ni clave foránea ni índice para recorrerla.)

#### Cómo se recorre una relación en una base de datos relacional: el JOIN

En una base relacional, las conexiones **no están guardadas como
caminos**: se **calculan en el momento de la consulta**, con un **JOIN**
("unión"), que empareja filas de dos tablas por un valor igual.

Para un salto (los repos de un actor), la consulta es:

```sql
SELECT r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id     -- 1.ª unión
JOIN repo r        ON r.id = ar.repo_id      -- 2.ª unión
WHERE a.id = 321725054;
```

Lo que hace PostgreSQL, paso a paso (gracias a los índices):

1. Busca el actor `321725054` en el índice `actor_pkey`.
2. Busca en el índice `actor_repo_pkey` todas las filas con ese
   `actor_id`: obtiene sus `repo_id`.
3. Por cada `repo_id`, busca el repo en el índice `repo_pkey`.

Cada flecha del recorrido es una **búsqueda en un índice**, y cada búsqueda
tiene un coste que depende (aunque poco, gracias al árbol B) del tamaño
total de la tabla. Para el recorrido del benchmark
(`actor → repo → actor → repo`), cada salto añade **más JOIN**, y cada JOIN
se hace para **todas** las filas que llegan del salto anterior. Si en cada
salto el número de filas crece, el trabajo crece muy deprisa.

#### Por qué en un grafo no hay claves primarias ni foráneas

Una base de datos de grafos guarda las cosas de otra manera:

| Concepto relacional | Equivalente en el grafo de Neo4j |
|---|---|
| Tabla (`actor`, `repo`) | **Etiqueta** (*label*): `:Actor`, `:Repo`. Agrupa nodos del mismo tipo |
| Fila | **Nodo** |
| Columna | **Propiedad** (`id`, `login`, `name`) |
| Tabla de unión + claves foráneas (`actor_repo`) | **Arista** (*relationship*): `-[:INTERACTED_WITH]->`, guardada como un objeto propio que une los dos nodos |
| Clave primaria | No existe como tal. Se crea una **restricción de unicidad** sobre una propiedad (`id`) |
| JOIN | **Seguir la arista**: ir de un nodo a sus vecinos |

**Por qué no hacen falta claves foráneas:** en el grafo, la conexión **no
es un valor que apunta a otro valor** (un `actor_id` que hay que buscar en
otra tabla). **Es un objeto propio que une directamente los dos nodos**.
Una arista no puede existir sin sus dos extremos: Neo4j no permite crear
una arista "colgando" ni borrar un nodo que todavía tiene aristas (de ahí
el `DETACH DELETE` de `load_neo4j.py`, que borra primero las aristas). Es
decir, **la integridad referencial va incluida en la propia estructura**,
sin necesidad de declararla.

**Por qué no hay clave primaria "de verdad":** Neo4j identifica cada nodo
internamente con su propio identificador (el *element id*), que **no** es
un dato nuestro y no conviene usar como clave del negocio, porque puede
reutilizarse si se borran nodos. Por eso añadimos la **restricción de
unicidad** sobre nuestra propiedad `id`: hace el papel de la clave
primaria (sin duplicados, búsqueda rápida por índice), pero es opcional y
la decidimos nosotros.

**Y lo más importante: en el grafo, el índice solo sirve para encontrar
el punto de partida.** Una vez encontrado el primer nodo (por ejemplo, el
actor `321725054`, gracias a la restricción de unicidad), **ya no se usa
ningún índice**: el recorrido sigue las aristas directamente.

#### Qué hay en su lugar: la adyacencia sin índices (*index-free adjacency*)

En Neo4j, **cada nodo guarda dónde están sus propias aristas**, y cada
arista guarda **dónde están sus dos nodos**. Conceptualmente:

- el registro de un nodo apunta a sus aristas;
- el registro de una arista apunta a su nodo de inicio, a su nodo final y
  a la siguiente arista de cada uno de ellos.

(Las versiones recientes de Neo4j organizan físicamente los datos de otra
forma, agrupando las aristas de cada nodo, pero la idea es la misma: las
conexiones de un nodo están guardadas **con el nodo**.)

Así, ir de un actor a sus repos no es "buscar en una tabla todas las filas
cuyo `actor_id` es X", sino **"leer la lista de aristas que el nodo ya
tiene"**. Es como la diferencia entre:

- **Relacional:** buscar en la guía telefónica de toda la ciudad a los
  amigos de Ana (una búsqueda, aunque sea rápida, en una lista de todos).
- **Grafo:** abrir la agenda de Ana, que ya tiene apuntados a sus amigos
  (seguir enlaces que ya están ahí).

#### Por qué eso optimiza (y por qué hay que medirlo)

| | PostgreSQL (relacional) | Neo4j (grafo) |
|---|---|---|
| Encontrar el punto de partida | Búsqueda en un índice (árbol B) | Búsqueda en un índice (la restricción) |
| Cada salto | Un JOIN: una **búsqueda en un índice** por cada fila que llega | **Seguir punteros** que el nodo ya tiene |
| ¿El coste de un salto depende del tamaño **total** de la base? | Un poco: el índice crece con la tabla (aunque muy despacio) | No: depende solo de **cuántas aristas tiene ese nodo** |
| Lo que crece al añadir saltos | El número de JOIN y de búsquedas en índices | El número de aristas que se siguen |

**La teoría:** en recorridos **cortos** (uno o dos saltos), PostgreSQL es
muy rápido, porque sus índices son muy eficientes y lleva décadas
optimizando los JOIN. En recorridos **largos**, el grafo debería ganar,
porque su coste depende solo de la parte del grafo que se recorre, no del
tamaño total de las tablas.

**Pero es solo una hipótesis.** El árbol B necesita muy pocos pasos
incluso en tablas enormes, las dos bases guardan en memoria los datos que
más se usan, y el planificador de PostgreSQL es muy bueno. **En qué número
de saltos y con qué volumen de datos cambia el ganador** es exactamente lo
que este proyecto quiere **medir**, en lugar de darlo por supuesto.

#### Otros conceptos que conviene conocer

**Normalización.** Es la forma de organizar las tablas para no guardar el
mismo dato dos veces. Por ejemplo, el `login` de un actor está **solo** en
`actor`, no repetido en cada fila de `actor_repo`. Si cambiara, solo
habría que cambiarlo en un sitio. Por eso la pregunta de investigación
habla de un modelo relacional **normalizado**: es la forma "correcta" de
diseñar el lado relacional, la que se usaría en la práctica.

**Cardinalidad de una relación.** Cuántos elementos de un lado se pueden
relacionar con cuántos del otro:

| Tipo | Ejemplo | Cómo se guarda en relacional |
|---|---|---|
| Uno a uno | Una persona y su documento de identidad | Una clave foránea única |
| Uno a muchos | Un repo y sus *issues* (cada issue es de un solo repo) | Una clave foránea en el lado "muchos" |
| **Muchos a muchos** | **Actores y repos (este proyecto)** | **Una tabla de unión** (`actor_repo`) con dos claves foráneas |

En el grafo, los tres tipos se guardan igual: con aristas.

**Restricción frente a índice.** Una **restricción** (*constraint*) es una
**regla** que la base de datos hace cumplir (único, no vacío, la
referencia existe). Un **índice** es una **estructura para buscar rápido**.
A menudo van juntos (una clave primaria o una restricción de unicidad
crean un índice para poder comprobarse), pero son cosas distintas: una
clave foránea es una restricción **sin** índice, y `actor_repo_repo_id_idx`
es un índice **sin** restricción.

**Transacciones y ACID.** Una **transacción** es un grupo de cambios que se
aplican **todos o ninguno**. Las dos bases de datos cumplen las
propiedades **ACID**: *Atomicidad* (todo o nada), *Consistencia* (las
reglas se cumplen siempre), *Aislamiento* (las transacciones no se pisan
entre sí) y *Durabilidad* (lo guardado no se pierde aunque se apague el
ordenador). Por eso la carga de PostgreSQL, que es una sola transacción,
nunca deja datos a medias.

**El esquema en cada base de datos.** PostgreSQL exige definir las tablas,
columnas y tipos **antes** de guardar datos (*schema-on-write*). Neo4j es
más flexible: se pueden crear nodos con cualquier propiedad sin declararla
antes; las restricciones son opcionales y las añadimos nosotros para
garantizar la calidad de los datos y que las búsquedas sean rápidas.

**`EXPLAIN` y `PROFILE`: ver cómo se ejecuta una consulta.** Serán
importantes en el benchmark: no basta con saber **cuánto** tarda una
consulta, también **por qué**.

- PostgreSQL: `EXPLAIN` muestra el plan sin ejecutarlo; `EXPLAIN ANALYZE`
  lo ejecuta y muestra el tiempo real de cada paso (por ejemplo, si usó un
  `Index Scan` o un `Seq Scan`).
- Neo4j: `EXPLAIN` muestra el plan; `PROFILE` lo ejecuta y cuenta, paso a
  paso, cuántos datos se tocaron (*db hits*).

### Cómo carga cada script

**`load_postgres.py`:**

1. **Borra y vuelve a crear las tablas** (`DROP TABLE IF EXISTS` y
   `CREATE TABLE`). Así cada ejecución empieza de cero, y ejecutarlo dos
   veces da el mismo resultado. El orden importa: `actor_repo` se borra
   primero y se crea la última, porque depende de las otras dos.
2. **Carga cada CSV con `COPY`**, el mecanismo de **carga masiva** de
   PostgreSQL: mucho más rápido que insertar fila a fila, porque los datos
   entran como un flujo continuo. Con `COPY ... FROM STDIN`, Python envía
   el contenido del archivo por la conexión, así que el servidor no
   necesita acceder a tus archivos. Primero `actor` y `repo`, después
   `actor_repo`, por las claves foráneas.
3. **Ejecuta `ANALYZE`** (ver arriba).
4. **Guarda todo con `COMMIT`.** Todo lo anterior forma una sola
   **transacción**: un grupo de cambios que se aplican todos o ninguno. Si
   el script fallara a mitad, PostgreSQL desharía todo, y nunca quedaría
   una carga a medias.
5. **Comprueba los conteos**: cuenta las filas de cada tabla y las compara
   con las del CSV.

**`load_neo4j.py`:**

1. **Lee los tres CSV en Python** y convierte los `id` en números.
2. **Vacía la base de datos** (`MATCH (n) DETACH DELETE n`: borra cada
   nodo junto con sus aristas) y crea las **restricciones de unicidad**,
   si no existen.
3. **Crea los nodos y después las aristas, en lotes de 5.000 filas.** En
   lugar de enviar las 15.053 conexiones en una sola petición enorme, las
   envía por partes. Cada lote usa `UNWIND`, que convierte la lista en una
   fila por elemento dentro de la propia base de datos, como un bucle
   `for`. Para cada arista, Neo4j **busca** el actor y el repo por su `id`
   (rápido, gracias a las restricciones) y crea la arista entre ellos. Por
   eso los nodos tienen que existir antes que las aristas.
4. **Comprueba los conteos** de nodos y aristas frente a los CSV.

Las explicaciones línea a línea están en las copias anotadas:
[load_postgres.py](load_postgres.py) y [load_neo4j.py](load_neo4j.py).

### Cómo ejecutarlos

Con las dos bases de datos en marcha y después de `extract_csv.py`:

```bash
./run.sh scripts/extract_csv.py      # si los CSV todavía no existen
./run.sh scripts/load_postgres.py
./run.sh scripts/load_neo4j.py
```

Los dos usan `run.sh`, porque necesitan las contraseñas.

### Resultado

Las dos cargas funcionaron a la primera, y **las seis comprobaciones dicen
OK**:

```
Rows loaded (database vs. CSV file):
  actor          14515   actors.csv         14515   OK
  repo           14995   repos.csv          14995   OK
  actor_repo     15053   actor_repo.csv     15053   OK

Loaded (database vs. CSV file):
  Actor nodes              14515   actors.csv         14515   OK
  Repo nodes               14995   repos.csv          14995   OK
  INTERACTED_WITH edges    15053   actor_repo.csv     15053   OK
```

Las dos bases de datos tienen ahora **exactamente los mismos datos**:
14.515 actores, 14.995 repos y 15.053 conexiones. Es la condición
necesaria para empezar a comparar consultas.

### El cronómetro de la carga

Los dos scripts muestran cuánto tarda **cada paso** y el **total de la
carga**, medidos con `time.perf_counter()`: el reloj de Python pensado
para medir duraciones, el más preciso y que no se ve afectado si cambia la
hora del ordenador.

- **Entra en el total:** todo lo que escribe en la base de datos, desde
  crear o vaciar hasta guardar (en PostgreSQL, el `COMMIT` se hace justo
  antes de parar el reloj).
- **No entra:** conectarse, la comprobación final de conteos y, en Neo4j,
  leer los CSV en Python (que se muestra aparte).

**Importante: estos tiempos no comparan las dos bases de datos.** Sirven
para saber cuánto tarda el proceso (por ejemplo, cuánto esperar cuando se
carguen más horas de datos), pero **no son un resultado del benchmark**,
por tres razones:

1. **Cada una carga de forma distinta:** PostgreSQL con `COPY`, su
   mecanismo de carga masiva; Neo4j por lotes a través del driver,
   buscando los dos nodos de cada arista.
2. **Es una sola ejecución.** Un benchmark serio repite cada medición
   varias veces y descarta la primera, porque al principio la base de
   datos todavía no tiene nada en memoria.
3. **No es lo que pregunta el proyecto.** La pregunta de investigación
   trata de **recorridos de varios saltos**, no de cuánto tarda la carga.

### Ver los datos cargados

**En pgAdmin 4**, las tablas están en: **gharchive** → **Schemas** →
**public** → **Tables**. (`public` es el esquema por defecto: una especie
de carpeta dentro de la base de datos donde se crean las tablas cuando no
se indica otra.) Los **Catalogs** que aparecen más arriba son las tablas
internas de PostgreSQL, no los datos del proyecto.

- Si no aparecen las tablas, es porque se crearon después de abrir
  pgAdmin: clic derecho en **Tables** → **Refresh**.
- **Ver los datos:** clic derecho en una tabla → **View/Edit Data** →
  **First 100 Rows**, o una consulta en el Query Tool. En la cabecera de
  la columna `id` aparece **`[PK] bigint`**: `[PK]` indica que es la clave
  primaria.
- **Ver los índices:** dentro de cada tabla, **Indexes**. En `actor_repo`
  aparecen dos: `actor_repo_pkey` (el de la clave primaria) y
  `actor_repo_repo_id_idx`.

Consultas útiles en el Query Tool:

```sql
-- Cuántas filas hay en cada tabla
SELECT (SELECT count(*) FROM actor)      AS actors,
       (SELECT count(*) FROM repo)       AS repos,
       (SELECT count(*) FROM actor_repo) AS connections;

-- Los repos de un actor: un "salto" del recorrido
SELECT a.login, r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id
JOIN repo r        ON r.id = ar.repo_id
WHERE a.login = 'peitongshi';
```

**En Neo4j**, desde **Query** en Neo4j Desktop, en la base `gharchive`
(con el selector de base de datos o con `:use gharchive`):

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

El resultado aparece **dibujado**: un círculo para el actor, otro para su
repo y una flecha entre los dos. Es la misma consulta que la segunda de
PostgreSQL, escrita en el lenguaje del grafo: en SQL hacen falta dos
`JOIN` para ir del actor al repo pasando por `actor_repo`; en Cypher, la
flecha ya *es* la conexión.


## Ver y consultar el grafo en Neo4j Desktop (Query)

PostgreSQL tiene pgAdmin para ver sus tablas. El equivalente en Neo4j es
la herramienta **Query** de Neo4j Desktop: un editor donde se escriben
consultas en Cypher y se ven los resultados, incluso **dibujados** como
nodos y flechas. Esta sección recoge cómo se usa con la versión instalada
en este proyecto (Neo4j Desktop 2.2.1), incluidos los tropiezos que
aparecieron por el camino.

### Paso 1: comprobar que la instancia está en marcha

En el menú de la izquierda, **Local instances**. La tarjeta `gharchive`
tiene que mostrar **RUNNING**; si no, pulsa **Start**.

Debajo aparece la lista **Databases**, que debería mostrar tres:
`gharchive`, `neo4j` y `system`.

- **Si pone *Databases (0)* y *Refreshing...*:** Neo4j Desktop no ha podido
  leer la lista. Suele pasar justo después de arrancar, o después de
  **cambiar la contraseña** de Neo4j, si Desktop se quedó con la antigua.
  Espera unos segundos o pulsa el botón de refrescar (⟳); si sigue igual,
  vuelve a conectar con la contraseña nueva. **Los datos no se han
  perdido**: es solo la lista, que no se ha cargado.

### Paso 2: abrir Query y conectarlo a la instancia

1. En el menú de la izquierda, en **Studio**, pulsa **Query**.
2. Si arriba pone **No instance connected**, pulsa **Connect to
   instance** (en el centro) o el desplegable **No instance connected ∨**
   (arriba a la izquierda), y elige la instancia **`gharchive`**.
3. Si pide credenciales: usuario **`neo4j`** y la contraseña de
   `secrets.sh` (`NEO4J_PASSWORD`).

Arriba aparecen tres datos que conviene mirar siempre:

| Indicador | Qué debe decir | Qué significa |
|---|---|---|
| **Instance** | `gharchive`, con punto verde | La instancia (el "servidor") a la que estás conectado |
| **Database** | **`gharchive`** | La base de datos dentro de la instancia donde se ejecutan las consultas |
| **User** | `neo4j` | Con qué usuario estás conectado |

### Paso 3: elegir la base de datos `gharchive` (el tropiezo más habitual)

Al conectar, Query abre la base **`neo4j`**, la que viene por defecto. Esa
base está **vacía**: los datos del proyecto se cargaron en `gharchive`. La
señal de que estás en la base equivocada es que el panel de la izquierda
dice **Nodes (0)** y **Relationships (0)**.

Para cambiar de base, usa el desplegable **Database ∨** de arriba, o
escribe en la barra de consultas y pulsa **Ctrl + Enter**:

```cypher
:use gharchive
```

La barra pasa de `neo4j$` a **`gharchive$`**. Los comandos que empiezan
por `:` (como `:use`) no son Cypher: son comandos de la propia
herramienta.

### Paso 4: el panel "Database information"

Con `gharchive` elegida, el panel de la izquierda resume lo que hay en la
base, y es la forma más rápida de comprobar la carga:

| En el panel | Valor | De dónde sale |
|---|---|---|
| **Nodes** | 29.510 | 14.515 `Actor` + 14.995 `Repo` |
| **Relationships** | 15.053 | Las conexiones `INTERACTED_WITH` |
| **Etiquetas** | `Actor`, `Repo` | Los dos tipos de nodo |
| **Tipo de relación** | `INTERACTED_WITH` | El tipo de arista |
| **Property keys** | `id`, `login`, `name`... | Las propiedades de los nodos |

Las cifras coinciden exactamente con las que comprobó `load_neo4j.py`. En
*Property keys* también aparecen otros nombres (`data`, `nodes`,
`relationships`, `style`, `visualisation`): son nombres que Neo4j tiene
registrados internamente, no propiedades de nuestros nodos.

**Si haces clic en una etiqueta** (por ejemplo `Actor`), Query ejecuta una
consulta que muestra unos cuantos nodos de ese tipo.

### Paso 5: escribir consultas y leer el resultado

Las consultas se escriben en la barra de arriba (`gharchive$`) y se
ejecutan con **Ctrl + Enter** o el botón ▶. Cada resultado aparece debajo,
en su propio recuadro, y los anteriores se quedan más abajo.

**La primera consulta del proyecto:** un actor y su repo.

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

Se lee casi como un dibujo: "busca (`MATCH`) un nodo `Actor` con login
`peitongshi`, conectado por una flecha `INTERACTED_WITH` a un nodo `Repo`,
y devuelve (`RETURN`) los tres". `a`, `e` y `r` son nombres que les damos
para poder devolverlos.

**Qué se ve:**

- **Dos círculos:** el actor (verde) y el repo (azul). Cada etiqueta
  tiene su color.
- **Una flecha** del actor al repo, con el texto `INTERACTED_WITH`. La
  dirección de la flecha es la que se definió al cargar: de `Actor` a
  `Repo`.
- **El texto dentro de cada círculo** es una de sus propiedades, que Neo4j
  elige para mostrar. En el actor aparece su `id` (`321725054`) y en el
  repo su `name` (`peitongshi/niulai-chinese`). Haciendo clic en un nodo
  se ven todas sus propiedades.
- **Results overview**, a la derecha: cuántos nodos y relaciones hay en el
  resultado, por tipo (aquí, 1 `Actor`, 1 `Repo` y 1 `INTERACTED_WITH`).

Este actor es uno de los casos especiales de la etapa de extracción: el
que cambió su login durante esa hora (de `lucky521-png` a `peitongshi`).
Como el script guardó el nombre más reciente, aquí aparece como
`peitongshi`.

**Las tres pestañas del resultado:**

| Pestaña | Qué muestra |
|---|---|
| **Graph** | El dibujo de nodos y flechas |
| **Table** | Los mismos resultados como una tabla, fila a fila |
| **Raw** | La respuesta tal como la envía el servidor (texto JSON) |

Abajo del recuadro aparecen controles para hacer zoom, encuadrar el
dibujo y seleccionar o mover nodos.

**El tiempo que aparece abajo** (por ejemplo, *Started streaming 1 record
after 388 ms and completed after 550 ms*) es lo que tardó esa consulta.
Como con los tiempos de carga, **no es una medición del benchmark**: es
una sola ejecución, la primera (sin nada en memoria todavía), e incluye
el trabajo de la herramienta. Además, esta consulta busca por `login`, y
`login` **no tiene índice** (solo `id` lo tiene), así que Neo4j tuvo que
revisar los actores uno a uno para encontrarlo. Las consultas del
benchmark buscarán siempre por `id`.

### Más consultas útiles

```cypher
// Cuántos nodos y relaciones hay (14515, 14995 y 15053)
MATCH (a:Actor) WITH count(a) AS actors
MATCH (r:Repo)  WITH actors, count(r) AS repos
MATCH ()-[e:INTERACTED_WITH]->() RETURN actors, repos, count(e) AS connections;
```

```cypher
// Unos cuantos repos (siempre con LIMIT al dibujar)
MATCH (r:Repo) RETURN r LIMIT 25;
```

```cypher
// El repo con más actores distintos: un "punto de encuentro" del grafo
MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo)
WITH r, count(a) AS actors ORDER BY actors DESC LIMIT 1
MATCH (a:Actor)-[e:INTERACTED_WITH]->(r)
RETURN a, e, r;
```

El último resultado es interesante de ver: un repo en el centro con
varias flechas que llegan desde sus actores. Es justo uno de los pocos
puntos por los que un recorrido de varios saltos puede pasar de un actor a
otro.

**Pon siempre `LIMIT` cuando vayas a dibujar.** Dibujar los casi 30.000
nodos de golpe haría la herramienta muy lenta, y no se vería nada.

### Lo que hay que evitar en Neo4j Desktop

Al buscar cómo abrir Query aparecieron menús con opciones peligrosas o que
no sirven para esto:

| Dónde | Opción | Cuidado |
|---|---|---|
| `···` de una **base de datos** en la lista *Databases* | **Delete** | **Borra la base de datos con todos sus datos.** Ese menú solo sirve para gestionar la base (exportarla, borrarla...), no para verla |
| `···` de la **instancia** (la tarjeta) | **Upgrade** | Actualiza Neo4j a otra versión: cambiaría las condiciones del benchmark. **No usar** |
| `···` de la **instancia** | **Open ›** | Solo abre archivos (la carpeta de la instancia, el log y la configuración), no herramientas de consulta |

**Si algún día se borra la base `gharchive` sin querer,** se recupera en
un momento: **Create database** con el nombre `gharchive`, y después
`./run.sh scripts/load_neo4j.py`. Es otra ventaja de tener los CSV y los
scripts: las bases de datos siempre se pueden reconstruir desde cero.

### Resumen: los pasos de cada vez

1. **Local instances** → `gharchive` en **RUNNING**.
2. **Query** → **Connect to instance** → `gharchive` → usuario `neo4j`.
3. **Database** → **`gharchive`** (o `:use gharchive`). Comprobar que el
   panel muestra **Nodes (29,510)**.
4. Escribir la consulta en la barra `gharchive$` → **Ctrl + Enter**.


## La pipeline de 24 horas (pipeline.py): una perspectiva de ingeniería de datos

Hasta aquí, todo el proyecto trabajaba con **una sola hora elegida a mano**
(2026-08-27, 15:00 UTC). Es perfecta para el benchmark, porque nunca
cambia, pero no es como se trabaja con datos de verdad: en ingeniería de
datos, los datos llegan continuamente, y lo que importa es tener un
**proceso que se pueda repetir**. Esta etapa añade ese proceso: una
**pipeline** (una cadena de pasos automática) que reconstruye una base de
datos con las **últimas 24 horas** de GH Archive.

### Dos procesos, cada uno con su base de datos

Desde ahora, el proyecto tiene **dos procesos separados**:

| | Benchmark | Pipeline de 24 horas |
|---|---|---|
| **Datos** | Una hora fija: 2026-08-27, 15:00 UTC | Las últimas 24 horas, con un día de retraso |
| **Base de datos** (en PostgreSQL y en Neo4j) | `gharchive` | `gharchive24h` |
| **Cómo se carga** | A mano: `extract_csv.py`, `load_postgres.py`, `load_neo4j.py` | Automáticamente: `pipeline.py` |
| **¿Cambia?** | **Nunca.** Está congelada | Se reconstruye en cada ejecución |
| **Para qué sirve** | Medir y comparar consultas en condiciones que se pueden repetir | Tener datos recientes y abundantes, con un proceso de ingeniería de datos |

En total hay **cuatro bases de datos**, dos en cada servidor:

```
PostgreSQL (puerto 5432)               Neo4j (instancia "gharchive", puerto 7687)
├── gharchive      ← benchmark          ├── gharchive      ← benchmark
└── gharchive24h   ← pipeline           └── gharchive24h   ← pipeline
```

**Por qué separadas:** si la pipeline usara `gharchive`, cada ejecución
borraría los datos del benchmark, y las mediciones dejarían de poder
repetirse. Por eso `pipeline.py` **se niega** a trabajar sobre `gharchive`,
aunque se le pida por error.

**Por qué `gharchive24h` y no `gharchive_24h`:** Neo4j no admite el guion
bajo en los nombres de base de datos (solo letras, números, puntos y
guiones). Para que el nombre sea el mismo en los dos lados, se usa
`gharchive24h`.

### La ventana: 24 horas móviles, con un día de retraso, en UTC

Cada vez que se ejecuta, la pipeline calcula qué 24 horas cargar:

1. Toma la hora actual **en UTC** y la redondea hacia abajo a la hora en
   punto.
2. Le resta **24 horas de retraso**: ahí **termina** la ventana.
3. Le resta otras **24 horas**: ahí **empieza**.

**Ejemplo:** el 22 de octubre a las 11:15 UTC, la ventana va del **20/10 a
las 11:00 al 21/10 a las 11:00**. Son 24 archivos de GH Archive, del
`2026-10-20-11.json.gz` al `2026-10-21-10.json.gz` (el último cubre de
10:00 a 11:00).

- **Por qué UTC:** GH Archive nombra sus archivos en hora UTC. En Portugal
  la hora va por delante de UTC (una hora en verano), así que usar la hora
  local desplazaría la ventana.
- **Por qué el día de retraso:** GH Archive publica cada hora poco después
  de que termine, pero a veces se retrasa. Con un día de margen, todas las
  horas de la ventana están seguro publicadas. El retraso es un parámetro
  (`--lag-hours`), así que se puede reducir más adelante.
- **"Móvil":** cada hora, la ventana avanza una hora. Sale la más antigua
  y entra una nueva.

### Reconstruir todo en cada ejecución

En cada ejecución, la pipeline **vacía y vuelve a llenar** las dos bases
`gharchive24h` desde las 24 horas. Parece mucho trabajo, pero es más
sencillo y más fiable que ir añadiendo la hora nueva y quitando la
antigua: con el esquema actual (una conexión por par actor–repo, sin
fecha), no se sabría qué conexiones aparecían *solo* en la hora que sale.

Lo que sí se hace de forma incremental es la **descarga**: los archivos se
guardan en `data/live/raw/`, y en cada ejecución solo se descarga la hora
nueva y se borra la que ha salido de la ventana.

### Tarea programada cada hora, no un proceso que corre siempre

| | Proceso que corre siempre | Tarea programada cada hora |
|---|---|---|
| Cómo funciona | Un programa que no termina nunca: procesa, espera una hora, vuelve a empezar | Un programa normal que hace su trabajo y **termina**; el sistema lo lanza cada hora |
| Si falla una vez | Se queda parado hasta que alguien lo vuelva a arrancar | La siguiente hora vuelve a intentarlo solo |
| Dónde se usa | *Streaming* (por ejemplo, Kafka) | Procesos *batch* (cron, Airflow, el Programador de tareas de Windows) |

Como GH Archive publica los datos **por horas**, lo natural es un proceso
*batch* programado. En Windows, el que lo lanza es el **Programador de
tareas** (*Task Scheduler*). Mientras la pipeline viva en el portátil,
solo se ejecutará con el ordenador encendido y **Neo4j Desktop abierto**
(PostgreSQL arranca solo, como servicio). Para que funcione sin el
portátil habría que llevarla a un servidor siempre encendido; las opciones
están al final de esta sección.

### Qué hace cada ejecución

1. **Calcula la ventana** (ver arriba).
2. **Sincroniza los archivos:** borra de `data/live/raw/` los que han salido
   de la ventana y descarga solo los que faltan.
3. **Extrae los CSV** de las 24 horas a `data/live/csv/`, con el mismo
   código que el benchmark (`extract_csv.py`): sin bots, sin repetir
   conexiones y con el nombre más reciente de cada `id`.
4. **Comprueba los servidores y crea las bases si no existen:** si alguno
   no responde, se para aquí, **antes de vaciar nada**.
5. **Reconstruye PostgreSQL y después Neo4j** con los mismos scripts de
   carga que el benchmark, pero en `gharchive24h`, y compara los conteos
   con los CSV.
6. **Anota el resultado:** en `logs/pipeline.log`, todo lo que ha pasado; y,
   si todo fue bien, la ventana cargada en `data/live/current_window.txt`.

| Carpeta o archivo | Qué contiene | ¿En GitHub? |
|---|---|---|
| `data/live/raw/` | Los 24 archivos `.json.gz` de la ventana | No (`data/` está en el `.gitignore`) |
| `data/live/csv/` | Los tres CSV de la ventana | No |
| `data/live/current_window.txt` | La última ventana cargada con éxito, con sus conteos | No |
| `data/live/pipeline.lock` | Existe solo mientras una ejecución está en marcha | No |
| `logs/pipeline.log` | El historial de todas las ejecuciones | No (`logs/` está en el `.gitignore`) |

### Prácticas de ingeniería de datos que usa la pipeline

| Práctica | Qué significa | Cómo se aplica aquí |
|---|---|---|
| **Idempotencia** | Ejecutar algo una vez o diez veces deja el mismo resultado | Las bases se crean solo si no existen (`IF NOT EXISTS`); el contenido se reconstruye siempre igual a partir de la misma ventana |
| **Comprobación previa** (*pre-flight check*) | Verificar que todo está listo antes de cambiar nada | Descargas, extracción y conexión a los dos servidores van **antes** de vaciar ninguna base |
| **Escritura atómica** | Un archivo está completo o no existe; nunca a medias | Las descargas se guardan como `.part` y solo se renombran al terminar |
| **Reintentos** | Un fallo pasajero de red no debe tumbar el proceso | Cada descarga se intenta hasta 3 veces, esperando cada vez un poco más |
| **Fallar claramente** | Un problema real se nota, no se esconde | Si una hora no existe (error 404), la pipeline lo dice y no carga datos incompletos |
| **Bloqueo** (*lock*) | Dos ejecuciones no pueden pisarse | Un archivo `pipeline.lock`; si una ejecución dura más de una hora, la siguiente se salta |
| **Registro** (*logging*) | Cada ejecución deja rastro, con fecha y nivel | `logs/pipeline.log`, con la hora en UTC, para compararla directamente con la ventana |
| **Códigos de salida** | El programa dice si terminó bien (0) o mal (1) | El Programador de tareas muestra ese código como resultado de la última ejecución |
| **Calidad de datos** | No descartar datos en silencio | Los eventos sin `id` se cuentan y se avisa en el log |
| **Reutilizar, no copiar** | Una sola versión de cada lógica | La pipeline **importa** los scripts del benchmark (`import extract_csv`...) en lugar de copiar su código |
| **Protección** | Imposible romper lo importante por error | La pipeline se niega a tocar la base `gharchive` del benchmark |

### Los scripts de esta etapa

| Script | Qué hace ahora | Cambios de esta etapa |
|---|---|---|
| **`pipeline.py`** (nuevo) | Coordina toda la pipeline: ventana, descargas, extracción, cargas, log | Nuevo. [Copia anotada](pipeline.py) |
| `download_gharchive.py` | Descarga horas de GH Archive | Nueva función `fetch_gz()`: descarga sin descomprimir, con reintentos, escritura atómica y aviso claro si la hora no existe. Por defecto hace lo mismo que antes. [Copia anotada](download_gharchive.py) |
| `extract_csv.py` | Crea los tres CSV | Acepta **varios archivos**, también `.json.gz` sin descomprimir; descarta y cuenta los eventos sin `id`; la escritura de los CSV pasa a una función (`write_all()`) que la pipeline reutiliza. [Copia anotada](extract_csv.py) |
| `load_postgres.py` | Carga los CSV en PostgreSQL | Nueva opción `--database` (por defecto, `gharchive`). [Copia anotada](load_postgres.py) |
| `load_neo4j.py` | Carga los CSV en Neo4j | Nueva opción `--database` (por defecto, `gharchive`). [Copia anotada](load_neo4j.py) |

**El benchmark no ha cambiado:** se comprobó que `extract_csv.py` produce
los CSV del benchmark **idénticos byte a byte** que antes, y las cargas
siguen usando `gharchive` por defecto.

**Cómo funciona `import` entre nuestros scripts:** cada archivo `.py`
también es un **módulo** que otro script puede importar. Al importarlo se
cargan sus funciones, pero **no** se ejecuta su `main()`, gracias a la
protección `if __name__ == "__main__":` que tienen todos. Así
`pipeline.py` puede llamar a `extract_csv.extract()` o a
`load_postgres.load()` como si fueran suyas.

### Cómo ejecutarla

Con PostgreSQL y Neo4j en marcha:

```bash
./run.sh scripts/pipeline.py --dry-run    # muestra la ventana y qué descargaría; no cambia nada
./run.sh scripts/pipeline.py              # la ejecución real
```

Opciones (todas tienen un valor por defecto):

| Opción | Por defecto | Para qué |
|---|---|---|
| `--window-hours` | 24 | Tamaño de la ventana (por ejemplo, 6 para una prueba rápida) |
| `--lag-hours` | 24 | Cuánto tiempo atrás termina la ventana |
| `--database` | `gharchive24h` | Qué base reconstruir en los dos lados (nunca `gharchive`) |
| `--dry-run` | — | Solo enseñar el plan |

### La primera ejecución real: un problema de calidad de datos

La primera ejecución descargó las 24 horas (unos 240 MB) en **28
segundos**, pero falló en la extracción:

```
KeyError: 'id'
    remember_latest(repos, repo["id"], ...)
```

Es decir: algún evento tenía un `repo` **sin la clave `id`**. Buscándolo
en los datos: **2 eventos de 1.250.059** tenían `"repo": {}`, un repo
completamente vacío. Los dos eran `ForkEvent`; probablemente forks de repos
que después se borraron o pasaron a privados, y de los que GH Archive no
pudo guardar los datos. En la hora del benchmark (69.429 eventos) no había
ninguno.

**Lección:** un caso raro que no aparece en una muestra pequeña aparece al
procesar datos reales y abundantes. Por eso las pipelines se prueban con
datos reales.

**Solución:** la extracción **descarta los eventos sin `id` de actor o de
repo** (sin `id` no se puede crear el nodo ni la conexión), pero **los
cuenta y lo avisa**, y el aviso queda en el log:

```
WARNING  Skipped 2 event(s) without an actor or repo id
```

### Resultado de la primera ejecución completa

`Status: SUCCESS` en **160 segundos** en total, y las **seis comprobaciones
en OK**:

| Paso | Tiempo |
|---|---|
| Descarga (las 24 horas ya estaban) | 0,0 s (la primera vez: 28 s) |
| Extracción de 1.250.059 eventos | 25,3 s |
| Carga en PostgreSQL | 31,5 s |
| Carga en Neo4j | 90,0 s |

**Las 24 horas frente a la hora del benchmark:**

| | Hora del benchmark (27/08, 15:00) | 24 horas (20/10 12:00 → 21/10 12:00) |
|---|---|---|
| Eventos | 69.429 | **1.250.059** |
| Eventos de bots descartados | 1.970 (**2,8 %**) | 297.733 (**23,8 %**) |
| Eventos sin `id` descartados | 0 | 2 |
| Actores | 14.515 | **362.730** |
| Repos | 14.995 | **406.603** |
| Conexiones | 15.053 | **424.098** |
| Nodos en Neo4j | 29.510 | **769.333** |

**Lo que dicen estas cifras:**

- **Los bots pesan mucho más en estas 24 horas:** casi una cuarta parte de
  los eventos, frente al 2,8 % de la hora del benchmark. Una sola hora
  elegida a mano puede dar una imagen engañosa: es justo la razón de ser
  de esta pipeline.
- **El volumen es unas 26 veces mayor:** útil para el eje de "volumen de
  datos" de la pregunta de investigación.
- **Sigue habiendo poco más de una conexión por actor** (424.098 para
  362.730 actores): el grafo sigue muy fragmentado, aunque habrá más repos
  compartidos que en una hora. Se podrá medir con `summarize_data.py`.

**Sobre los tiempos de carga** (que, como los del benchmark, son
informativos, no resultados del benchmark):

- En PostgreSQL, `actor_repo` tardó **27 segundos**, frente a 1 segundo de
  `actor` y `repo`. Es lo esperable: por cada fila, PostgreSQL comprueba las
  dos **claves foráneas** (que el actor y el repo existen) y actualiza **dos
  índices**.
- En Neo4j, crear las aristas (45 s) es lo más lento, porque cada arista
  **busca** antes sus dos nodos.

**Un mensaje que no es un error:** en esta ejecución apareció en pantalla
una línea larga de Neo4j, `Received notification from DBMS server ... has
caught up`, justo después de crear la base `gharchive24h`. Es un aviso
**informativo** del driver: la base nueva ya está lista. Para que no
ensucie el log, la pipeline ahora solo registra los avisos y errores del
driver de Neo4j.

### Ver los datos de `gharchive24h`

- **pgAdmin 4:** en **Databases** aparece `gharchive24h` junto a
  `gharchive` (si no, clic derecho → **Refresh**). Las tablas están en
  **gharchive24h** → **Schemas** → **public** → **Tables**.
- **Neo4j Desktop (Query):** en el selector **Database**, elegir
  **`gharchive24h`** (o `:use gharchive24h`). El panel debería mostrar
  **Nodes (769,333)** y **Relationships (424,098)**. Con tantos nodos es
  todavía más importante usar `LIMIT` al dibujar.
- **El log:** `logs/pipeline.log` guarda todas las ejecuciones, y
  `data/live/current_window.txt` la última ventana cargada con éxito.

### Lo que falta

1. **Programarla cada hora** en el Programador de tareas de Windows.
2. **Que funcione sin el portátil encendido.** Habría que llevar la
   pipeline y las dos bases `gharchive24h` a un sitio siempre encendido:

   | Opción | Qué es | Coste | A tener en cuenta |
   |---|---|---|---|
   | Servidor en la nube | Una máquina Linux siempre encendida, con PostgreSQL, Neo4j y la pipeline programada con cron | Gratis (Oracle Cloud *Always Free*) o unos 5 €/mes | Hay que mantenerlo y protegerlo; es lo más parecido a un trabajo real |
   | GitHub Actions + bases en la nube | GitHub ejecuta la pipeline cada hora; PostgreSQL en Neon o Supabase | Gratis en gran parte | Neo4j AuraDB Free admite unos 200.000 nodos, y estas 24 horas tienen **769.333**: no basta |
   | Seguir en el portátil | El Programador de tareas | Gratis | Solo funciona con el portátil encendido y Neo4j Desktop abierto |

   El benchmark se quedaría en el portátil en cualquier caso, porque para
   medir tiempos conviene una máquina controlada y sin red de por medio.
3. **Una mejora posible: cambio *blue-green*.** Ahora, mientras se
   reconstruye, PostgreSQL muestra los datos anteriores hasta el final
   (porque la carga es una sola transacción), pero Neo4j se ve a medio
   llenar durante un minuto y medio. En sistemas reales se carga en una
   base nueva y, al terminar, se cambia de una a otra de golpe.
