# Entendiendo GH Archive

Esta guía se construye desde los primeros principios: qué son los eventos
de GitHub, qué hace GH Archive con ellos, qué contienen realmente los
archivos y cómo convertir eso en datos utilizables para este proyecto.

> La fecha/hora específica que este proyecto realmente usa como su
> conjunto de datos está registrada en el [README](../README.md) del
> proyecto, no aquí — este archivo trata de entender GH Archive en sí
> mismo, no de la elección específica hecha para este proyecto.

## 1. ¿Qué es un "evento de GitHub"?

Cada vez que sucede algo en un repositorio *público* de GitHub — alguien
envía (push) commits, abre un issue, abre un pull request, comenta, hace
fork de un repositorio, marca con estrella (star) un repositorio, crea una
rama, etc. — GitHub lo registra como un **evento** discreto.
Conceptualmente, esto es solo una entrada de registro: "en este instante,
este usuario hizo esta acción sobre este repositorio."

GitHub expone un feed en vivo de estos eventos como su API pública de
Events. Pero un feed en vivo no es útil para la investigación — no puedes
retroceder en el tiempo y preguntar "qué pasó el martes pasado." Necesitas
algo que haya estado registrando de forma continua y que te permita
obtener una porción específica del pasado.

## 2. Qué es GH Archive

GH Archive es un proyecto de larga duración (comenzó en 2011 y sigue
funcionando) que se sitúa sobre el feed público de eventos de GitHub y
hace un solo trabajo: registrar continuamente cada evento público,
agruparlos **por hora** y publicar cada hora como un archivo descargable,
de forma permanente, en una URL predecible. No está afiliado a GitHub
propiamente dicho — es un proyecto de archivo independiente — pero usa los
propios datos públicos de GitHub, por lo que es un registro histórico
fiel de la actividad pública en GitHub.

El resultado práctico: para *cualquier* hora desde 2011, puedes obtener un
archivo que contiene cada evento público que ocurrió en GitHub durante esa
hora, en todo el mundo.

## 3. Por qué esto importa para tu proyecto

Tu pregunta de investigación trata sobre cuándo un modelo de grafo supera
a un modelo relacional en consultas multi-salto. Para comprobarlo,
necesitas un conjunto de datos real con relaciones genuinas — no datos
sintéticos inventados por ti, que corren el riesgo de tener una forma
artificial que favorezca a uno de los dos modelos.

Los eventos de GH Archive codifican naturalmente un grafo:

```
User --[pushed to]--> Repository
User --[starred]-----> Repository
User --[forked]-------> Repository
User --[opened PR on]-> Repository
```

Un "repo" también puede conectar de vuelta hacia otros usuarios (p. ej.
todos los que le dieron estrella), así que seguir cadenas de estas
relaciones — "usuarios que dieron estrella a repositorios que fueron
forkeados por usuarios que también hicieron push a..." — es precisamente
el tipo de recorrido multi-salto del que trata tu pregunta de
investigación. Los mismos registros de eventos pueden aplanarse en tablas
relacionales (una tabla `users`, una tabla `repos`, una tabla `events` con
claves foráneas) o cargarse como nodos y aristas en una base de datos de
grafos, lo que te da una comparación equivalente sobre datos del mundo
real.

## 4. La estructura de la URL

Cada archivo por hora vive en:

```
https://data.gharchive.org/{YYYY-MM-DD}-{H}.json.gz
```

- `{YYYY-MM-DD}` — la fecha, p. ej. `2026-08-27`.
- `{H}` — la hora **en UTC**, de `0` a `23`, escrita **sin** cero inicial
  (`5`, no `05`; `15` se queda como `15`).

Así que `https://data.gharchive.org/2026-08-27-15.json.gz` sería cada
evento público de GitHub ocurrido entre las 15:00:00 y las 15:59:59 UTC
del 27 de agosto de 2026 — usado aquí puramente como ejemplo de la forma
de la URL.

No hay clave de API, autenticación ni límite de peticiones para descargar
estos archivos — son archivos estáticos en un servidor, obtenidos como
cualquier otra descarga.

## 5. Actualidad y disponibilidad — por qué no puedes usar "ahora mismo"

GH Archive solo puede publicar un archivo para una hora que haya
**terminado completamente**, porque necesita todos los eventos desde
`:00` hasta `:59` de esa hora antes de poder agruparla y publicarla. Dos
consecuencias prácticas:

- **No puedes elegir la hora actual, aún en curso** — todavía no existe
  como archivo, porque todavía no ha terminado de suceder.
- **Hay un pequeño retraso de publicación tras el final de una hora.**
  GH Archive necesita algo de tiempo para recopilar y empaquetar la hora
  recién terminada, así que incluso la hora completada más reciente puede
  no estar disponible para descargar de inmediato. En la práctica este
  retraso suele ser corto (bastante menos de una hora), pero no hay
  garantía absoluta sobre exactamente cuándo aparecerá el archivo de una
  hora determinada.
- Para fines de investigación hay una segunda razón, más importante, para
  evitar "el momento presente" independientemente del retraso de
  publicación: la **reproducibilidad**. Todo el sentido de tu proyecto es
  un resultado medible y comparable — si el conjunto de datos se definiera
  como "la hora que sea en el momento en que ejecutas esto", la entrada
  sería diferente cada vez que se ejecutara el pipeline, y nadie (incluido
  tu yo futuro) podría reproducir tus resultados. La solución es simple:
  elegir una fecha y hora específicas y fijas, con suficiente margen en el
  pasado (unas pocas horas de antigüedad ya es más que suficiente margen),
  y registrar ese valor exacto una sola vez — eso se convierte en una
  entrada constante, no en algo calculado en tiempo de ejecución.

## 6. Qué hay dentro del archivo

El nombre del archivo termina en `.json.gz`. Ese nombre indica que hay dos
capas superpuestas:

1. **`.gz`** — la capa exterior es compresión gzip, la misma compresión
   usada por herramientas afines a `.zip`. Debes descomprimir esto antes
   de poder leer nada.
2. **`.json`** — tras descomprimir, obtienes texto. Pero a pesar de la
   extensión `.json`, **no es un único documento JSON grande**. Está en un
   formato llamado **JSON Lines** (a veces `.jsonl`): cada línea del
   archivo es un objeto JSON completo e independiente, y no hay comas ni
   corchetes uniendo las líneas entre sí. Un archivo con 60.000 eventos es
   un archivo de texto con 60.000 líneas, cada una analizable
   (parseable) de forma independiente.

Esto importa en la práctica: no puedes hacer `json.load()` (analizar el
archivo completo de una vez) sobre él en la mayoría de los lenguajes —
tienes que leerlo línea por línea y llamar al analizador (parser) JSON
sobre cada línea individualmente.

### Anatomía de un evento

Una única línea, una vez analizada, se ve aproximadamente así (campos
recortados para mayor claridad):

```json
{
  "id": "40123456789",
  "type": "PushEvent",
  "actor": {
    "id": 987654,
    "login": "some-user"
  },
  "repo": {
    "id": 111222,
    "name": "someorg/somerepo"
  },
  "payload": {
    "commits": [ { "sha": "...", "message": "..." } ]
  },
  "created_at": "2026-08-27T15:03:11Z"
}
```

Campos clave:

- **`type`** — el tipo de evento. Los comunes: `PushEvent` (código
  enviado con push), `WatchEvent` (este es el nombre interno que usa
  GitHub para dar **estrella** a un repositorio, no literalmente
  "vigilarlo"), `ForkEvent`, `PullRequestEvent`, `IssuesEvent`,
  `IssueCommentEvent`, `CreateEvent` (nueva rama/etiqueta/repositorio),
  `DeleteEvent`.
- **`actor`** — el usuario de GitHub que realizó la acción.
- **`repo`** — el repositorio sobre el que ocurrió la acción.
- **`payload`** — detalle adicional específico del tipo de evento (p. ej.
  para un `PushEvent`, los commits reales; para un `PullRequestEvent`,
  los detalles del PR).
- **`created_at`** — marca de tiempo (timestamp) del evento.

Para construir un grafo, los campos que casi siempre importan son `type`,
`actor.login`, `repo.name` y `created_at` — eso basta para construir
aristas `(user)-[ACTION]->(repo)`. El `payload` normalmente solo hace
falta si tu análisis se preocupa por el contenido de la acción, no solo
por el hecho de que ocurrió.

### Actores, repos y eventos

Estas tres palabras se usan constantemente en este proyecto, así que vale
la pena ser precisos sobre qué significa cada una:

- Un **evento** (*event*) es una acción registrada individual — una línea
  del archivo, etiquetada con un `type`, una marca de tiempo, y exactamente
  un actor y un repo. Es lo que se cuenta; el número "Total events" de
  `summarize_data.py` es un conteo de líneas.
- Un **actor** es la cuenta de GitHub (humana o bot) que realizó la acción,
  identificada por `actor.login`.
- Un **repo** es el repositorio de GitHub sobre el que ocurrió la acción,
  identificado por `repo.name`.

Un evento siempre conecta exactamente un actor con exactamente un repo en
un momento dado — es la *arista*, mientras que los actores y los repos son
los dos tipos de *nodo* que conecta. Ejecutar `scripts/summarize_data.py`
sobre la hora fija de este proyecto muestra 69.429 eventos pero solo
14.728 actores únicos y 16.497 repos únicos: la mayoría de los actores y
repos aparecen en más de un evento (el actor más activo,
`github-actions[bot]`, representa él solo 994 de ellos). Esa es
precisamente la forma `(user)-[ACTION]->(repo)` mencionada arriba, pero a
escala — una red de aristas muchos-a-muchos entre un conjunto más pequeño
de nodos-actor y nodos-repo.

### Glosario de tipos de evento

`scripts/summarize_data.py` imprime un desglose por `type`. Esto es lo que
representa realmente cada tipo que aparece durante la hora fija de este
proyecto:

- **`PushEvent`** — se enviaron uno o más commits a una rama.
- **`CreateEvent`** — se creó una nueva rama, etiqueta (tag) o repositorio.
- **`DeleteEvent`** — se eliminó una rama o etiqueta.
- **`PullRequestEvent`** — un pull request fue abierto, cerrado, fusionado
  (merged), reabierto, o editado.
- **`IssueCommentEvent`** — se publicó un comentario en un issue *o* en el
  hilo de conversación principal de un pull request (internamente, GitHub
  trata la conversación de un PR como un issue, así que los comentarios de
  PR también aparecen bajo este tipo, no bajo
  `PullRequestReviewCommentEvent`).
- **`IssuesEvent`** — un issue fue abierto, cerrado, reabierto, asignado, o
  etiquetado (label).
- **`PullRequestReviewCommentEvent`** — se dejó un comentario en una línea
  específica del diff de un pull request (un comentario de revisión a
  nivel de línea, distinto de un comentario de conversación general).
- **`PullRequestReviewEvent`** — se envió una revisión completa de un pull
  request (aprobar / solicitar cambios / comentar).
- **`WatchEvent`** — se le dio estrella a un repo. (Es el nombre interno
  que usa GitHub para dar estrella, no "vigilar" — ver la viñeta `type` de
  arriba.)
- **`ReleaseEvent`** — se publicó una nueva release (versión etiquetada).
- **`ForkEvent`** — se hizo un fork de un repositorio.
- **`CommitCommentEvent`** — se dejó un comentario directamente en un
  commit, fuera de cualquier pull request.
- **`MemberEvent`** — se añadió un usuario como colaborador de un repo.

El esquema de eventos de GitHub tiene algunos tipos más (p. ej.
`PublicEvent` para un repo privado que se vuelve público, `GollumEvent`
para ediciones de la wiki) que simplemente no ocurrieron durante la hora
fija de este proyecto, así que no se listan aquí.

### Dónde aparece un segundo actor (referencias anidadas)

El `actor` de nivel superior de cada evento es *un solo* usuario de
GitHub — el que disparó el evento. Pero varios tipos de evento también
referencian a un *segundo* usuario en algún lugar dentro de `payload`, lo
cual importa mucho para este proyecto: un recorrido actor-repo-actor-repo
necesita más de un actor por evento para tener a dónde "saltar".

`scripts/profile_schema.py` busca dentro del `payload` de cada evento
objetos anidados con la forma `{"id": ..., "login": "..."}` — la misma
forma que el `actor` de nivel superior — y reporta dónde los encuentra.
Ejecutarlo sobre la hora fija de este proyecto muestra:

- **`PushEvent` (95,3 % de todos los eventos) no tiene ningún segundo
  actor en ninguna parte de su payload.** Solo lleva `ref`, `before`/`head`
  (SHA de commits), y `repository_id` — sin autor, sin objeto committer.
  Este es el hallazgo más importante para el diseño del esquema: la
  inmensa mayoría de los eventos de este conjunto de datos no puede
  aportar ninguna arista actor-a-actor, solo una arista actor-a-repo.
- **El `payload.pull_request` de `PullRequestEvent` es una referencia
  *recortada*** (solo `id`, `number`, `url`, `head`, `base`) — **no**
  incluye al autor del PR como sí lo haría la respuesta completa de la API
  REST de GitHub. Las únicas referencias a un segundo actor en este tipo
  de evento son los campos opcionales `assignee`/`assignees`, presentes en
  solo ~2 % de los eventos de PR.
- **Los eventos más ricos, del tipo comentario/revisión, llevan de forma
  fiable un segundo actor:** `IssueCommentEvent` (`payload.comment.user`,
  `payload.issue.user`), `IssuesEvent` (`payload.issue.user`),
  `PullRequestReviewCommentEvent` (`payload.comment.user`),
  `PullRequestReviewEvent` (`payload.review.user`), `CommitCommentEvent`
  (`payload.comment.user`), `ReleaseEvent` (`payload.release.author`),
  `ForkEvent` (`payload.forkee.owner`), y `MemberEvent`
  (`payload.member` mismo) — todos presentes en el 100 % de los eventos de
  su tipo respectivo.

Conclusión práctica: si el recorrido que se va a medir necesita aristas
actor-a-actor reales (no solo actor-a-repo, con "repo compartido" como
única conexión entre actores), esas aristas provienen casi por completo
del ~4,7 % de eventos que no son `PushEvent` — principalmente
comentarios, revisiones, issues, releases, forks, y cambios de membresía.
Ejecuta tú mismo `python scripts/profile_schema.py` (opcionalmente con
`--type <EventType>`) para ver el desglose completo y actualizado antes
de finalizar el esquema.

## 7. Cómo llevar los datos a tu máquina

Como es un archivo HTTPS plano, cualquiera de estas opciones funciona
(sustituye por la fecha/hora real que use este proyecto, según lo
registrado en el README):

```bash
# curl
curl -O https://data.gharchive.org/YYYY-MM-DD-H.json.gz

# wget
wget https://data.gharchive.org/YYYY-MM-DD-H.json.gz
```

O simplemente pega la URL en un navegador — se descarga como cualquier
archivo.

Luego descomprímelo:

```bash
gunzip YYYY-MM-DD-H.json.gz
# produce: YYYY-MM-DD-H.json
```

(Muchos lenguajes de programación también pueden leer archivos `.gz`
directamente, transmitiendo la descompresión sobre la marcha, sin un paso
manual de descompresión separado — p. ej. el módulo `gzip` de Python.)

## 8. Leyéndolo desde código

Un ejemplo mínimo en Python, leyendo línea por línea para que el archivo
completo nunca tenga que caber en memoria de una sola vez:

```python
import gzip
import json

with gzip.open("YYYY-MM-DD-H.json.gz", "rt", encoding="utf-8") as f:
    for line in f:
        event = json.loads(line)
        if event["type"] in ("PushEvent", "ForkEvent", "WatchEvent"):
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]
            # record (actor, event["type"], repo, event["created_at"])
```

A partir de ahí, los mismos registros extraídos `(actor, type, repo,
timestamp)` pueden:

- Insertarse en tablas relacionales (`users`, `repos`, `events` con
  claves foráneas hacia ambas), o
- Insertarse como nodos (`User`, `Repo`) y aristas (`PUSHED`, `STARRED`,
  `FORKED`) en una base de datos de grafos.

Como ambos modelos se construyen a partir de los *mismos* registros
extraídos, cualquier diferencia de rendimiento que midas entre ellos es
atribuible al modelo de almacenamiento/consulta, no a diferencias en los
datos subyacentes.

## 9. Escalando más adelante

Una sola hora típicamente contiene decenas de miles de eventos — suficiente
para construir un grafo real con una estructura multi-salto significativa.
Si experimentos posteriores necesitan más volumen (p. ej. para empujar más
la profundidad del recorrido antes de encontrar rendimientos decrecientes),
puedes repetir el mismo proceso de descarga y análisis (parseo) para horas
o días adicionales — los archivos de GH Archive se direccionan
individualmente, así que escalar simplemente significa obtener más de
ellos y combinar los registros extraídos, sin necesidad de cambios de
formato.

## 10. Alternativa: consultar sin descargar archivos

Los datos de GH Archive también están replicados en Google BigQuery como
tablas públicas (`githubarchive.hour.YYYYMMDD_HH`, y resúmenes
diarios/anuales). Si tienes (o configuras) acceso a Google Cloud, puedes
ejecutar SQL directamente contra estas tablas desde un navegador — útil
para preguntas exploratorias rápidas ("¿cuántos `ForkEvent` ocurrieron en
esta hora?") sin escribir código de descarga/análisis. Esto es totalmente
opcional para este proyecto; descargar y analizar un único archivo por
hora directamente, como se describió arriba, es suficiente y mantiene la
lista de dependencias más reducida.
