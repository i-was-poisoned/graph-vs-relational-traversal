# Guía de herramientas y conceptos: IA, Claude, VS Code, Python, y los fundamentos detrás de ellos

Esta guía existe con fines de aprendizaje: una explicación exhaustiva y
desde los primeros principios de las herramientas que usa este proyecto
(Claude, VS Code, Python) y los conceptos de informática que hay detrás,
escrita para que más adelante puedas explicar cualquiera de ellos a otra
persona con tus propias palabras. Está pensada para leerse junto con
[project-notes.md](project-notes.md) (el flujo de trabajo y el porqué) y
[gh-archive-guide.md](gh-archive-guide.md) (los detalles específicos del
conjunto de datos).

---

## Parte 1 — Inteligencia artificial y Claude

### 1.1 ¿Qué es la inteligencia artificial (IA)?

La **inteligencia artificial** es el campo general de construir sistemas
informáticos que realizan tareas que normalmente requieren inteligencia
humana: comprender el lenguaje, reconocer imágenes, tomar decisiones,
resolver problemas, aprender de la experiencia. "IA" es un término
paraguas muy amplio, no una sola tecnología — abarca desde un simple
programa de ajedrez con reglas codificadas a mano, hasta los grandes
modelos de lenguaje (como Claude) que escriben y mantienen conversaciones.

Una forma útil de imaginar el campo es como un conjunto de círculos
anidados, cada uno una técnica más específica dentro del anterior:

```
Inteligencia Artificial (IA)
  └── Machine Learning (aprendizaje automático, ML)
        └── Deep Learning (aprendizaje profundo)
              └── Grandes modelos de lenguaje (LLM)  <- Claude vive aquí
```

- **Inteligencia artificial** — el objetivo más amplio: máquinas que se
  comportan de forma inteligente, por cualquier método (reglas,
  búsqueda, estadística, aprendizaje).
- **Machine Learning (ML)** — un *enfoque* específico de la IA: en lugar
  de que un programador escriba reglas explícitas para cada situación
  ("si el correo contiene 'dinero gratis', márcalo como spam"), al
  sistema se le muestran muchos ejemplos (miles de correos ya etiquetados
  como spam o no spam) y aprende el patrón por sí mismo. El programa
  resultante se llama un **modelo**.
- **Deep Learning (aprendizaje profundo)** — una familia de técnicas de
  ML basadas en **redes neuronales**: estructuras matemáticas por capas,
  vagamente inspiradas en cómo se conectan las neuronas en un cerebro.
  "Profundo" hace referencia a tener muchas capas apiladas unas sobre
  otras. El deep learning es lo que hizo prácticos el reconocimiento de
  imágenes, el reconocimiento de voz, y los modelos de lenguaje modernos.
- **Grandes modelos de lenguaje (LLM)** — modelos de deep learning
  entrenados con enormes cantidades de texto, cuya habilidad central es
  predecir qué texto viene a continuación dado el texto ya escrito. Esa
  única habilidad — "predecir el siguiente fragmento de texto" — resulta
  ser lo bastante poderosa, a suficiente escala, como para producir algo
  capaz de responder preguntas, escribir código, razonar sobre problemas,
  y mantener una conversación. Claude es un LLM.

### 1.2 Entrenamiento (training) vs. inferencia — dos fases muy distintas

- El **entrenamiento** (*training*) es el proceso (extremadamente
  costoso, realizado una vez por Anthropic en enormes clústeres de
  cómputo) de mostrarle al modelo cantidades enormes de texto y ajustar
  millones/miles de millones de números internos (llamados
  **parámetros** o **pesos**, *weights*) para que sus predicciones
  mejoren cada vez más. Ahí es donde el modelo "aprende".
- La **inferencia** (*inference*) es lo que ocurre cada vez que realmente
  *usas* el modelo ya entrenado — como esta conversación. Durante la
  inferencia no ocurre ningún aprendizaje en el sentido habitual; los
  pesos del modelo están fijos, y simplemente está ejecutando su función
  matemática (muy grande) fija sobre tu entrada para producir una
  salida. Cada mensaje que le envías a Claude es una ejecución de
  inferencia, no una nueva ronda de entrenamiento.

### 1.3 ¿Qué es un "modelo", un "prompt", y un "token"?

- **Modelo** — la propia red neuronal entrenada: un conjunto enorme y
  fijo de números (los pesos) más el código que los ejecuta. "Claude"
  designa una familia de tales modelos (ha habido varias
  generaciones/tamaños).
- **Prompt** — el texto que le proporcionas al modelo como entrada. En
  una conversación, el "prompt" termina incluyendo efectivamente todo el
  historial de la conversación cada vez, lo cual explica por qué un
  modelo puede hacer referencia a algo dicho anteriormente.
- **Token** — el modelo no procesa el texto carácter por carácter ni
  palabra por palabra; lo divide en fragmentos llamados tokens (a menudo
  cercanos al tamaño de una palabra, a veces una palabra completa, a
  veces un fragmento de palabra, o un simple signo de puntuación). Los
  "tokens" son la unidad que el modelo realmente predice una a una al
  generar una respuesta, y la unidad usada para medir cuánto texto cabe
  en la **ventana de contexto** del modelo (la cantidad máxima de
  conversación/texto previo que el modelo puede "ver" a la vez). (No
  confundas esto con un *token de acceso* o *token de API*, un
  significado completamente distinto, relacionado con la seguridad, de
  la palabra "token" usado para la autenticación — ver §5.10.)

### 1.4 ¿Qué es Claude, en concreto?

**Claude** es la familia de grandes modelos de lenguaje construidos por
**Anthropic**, una empresa centrada en la seguridad de la IA. Se accede a
Claude de varias formas distintas, lo cual importa para entender qué está
pasando realmente en este proyecto:

- **claude.ai** — un sitio web/aplicación de chat, en el espíritu de una
  app de mensajería, donde escribes mensajes y Claude responde con texto.
- **La API de Claude** — una forma para que los *desarrolladores* envíen
  prompts a Claude de manera programática desde su propio código/sus
  propias aplicaciones, en lugar de a través de un sitio de chat. Así es
  como las empresas integran Claude en sus propios productos.
- **Claude Code** — una herramienta de línea de comandos *agéntica* (y,
  tal como se usa en este proyecto, una extensión de VS Code construida
  sobre ella) que no se limita a chatear contigo en texto plano — puede
  leer y escribir archivos reales en tu ordenador, ejecutar comandos de
  terminal reales, buscar en tu código, etc., para llevar a cabo
  realmente tareas de ingeniería de software. Esto es lo que escribió y
  ejecutó cada script de la carpeta `scripts/` de este proyecto.

### 1.5 "Agéntico" — qué diferencia a Claude Code de un simple chatbot

Una IA de chat normal toma tu mensaje y devuelve una respuesta de
texto — no tiene forma de *hacer* nada realmente en el mundo. Un
**agente** (en este sentido) es un sistema de IA al que se le ha dado
acceso a **herramientas** (*tools*) — acciones concretas que tiene
permitido realizar, como "leer este archivo", "ejecutar este comando de
shell", "buscar este texto en todo el proyecto" — y que puede decidir,
paso a paso, qué herramienta usar a continuación según lo que aprende del
resultado de la anterior. "Agéntico" describe este bucle de
observar → decidir → actuar → observar el resultado → decidir de nuevo.
Cada vez que has visto un comando ejecutarse realmente contra este
repositorio en este proyecto (descargar datos, ejecutar `peek_data.py`,
editar un archivo `.md`), eso era Claude Code usando una herramienta como
parte de este bucle agéntico — no solo describiendo lo que deberías
hacer, sino haciéndolo.

---

## Parte 2 — Los IDE, VS Code, y las extensiones

### 2.1 ¿Qué es un IDE?

**IDE** significa **Integrated Development Environment** (entorno de
desarrollo integrado). Es una única aplicación que agrupa las
herramientas que necesita un programador, en lugar de usar programas
separados y desconectados para cada una:

- un **editor de código** (para escribir y leer código fuente,
  normalmente con resaltado de sintaxis — colorear el código según su
  función gramatical — y autocompletado)
- un **terminal** (una línea de comandos basada en texto, ver §5.8)
  integrado directamente
- **herramientas de depuración** (*debugging*, ejecutar el código paso a
  paso, inspeccionar variables, para encontrar errores)
- **integración de control de versiones** (git — ver
  [git-commands-guide.md](git-commands-guide.md) — integrado, en lugar de
  necesitar un programa separado)
- a menudo, **herramientas de build/compilación**, gestión de
  proyectos/archivos, y sistemas de extensiones

La palabra "Integrado" es la parte clave: todo esto vive en un mismo
lugar, así que no estás cambiando constantemente entre un editor de
texto, una ventana de terminal separada, y una herramienta git separada.
Otros IDE conocidos incluyen PyCharm (enfocado en Python), IntelliJ IDEA
(enfocado en Java), y Xcode (plataformas de Apple).

Un IDE es un paso por encima de un **editor de texto plano** (como el
Bloc de notas, o incluso un editor de código más simple sin funciones de
IDE) — un editor de texto plano solo te deja escribir y guardar texto,
sin ninguna de las herramientas integradas anteriores.

### 2.2 ¿Qué es VS Code?

**VS Code** (Visual Studio Code) es un editor de código gratuito y
popular, de estilo IDE, hecho por Microsoft. A pesar del nombre similar,
es un *producto distinto* de "Visual Studio" (un IDE mucho más antiguo,
más pesado, centrado en Windows, principalmente para C#/.NET) — VS Code
es más ligero, multiplataforma (funciona igual en Windows, macOS, y
Linux), y su núcleo es de código abierto.

Propiedades clave que explican por qué se ha vuelto tan ampliamente
usado:

- **Ligero pero capaz** — arranca rápido, no exige mucho del ordenador,
  y aun así tiene un depurador real, integración con git, y un terminal
  integrado.
- **Multiplataforma** — exactamente el mismo editor, los mismos atajos,
  las mismas extensiones, ya sea en Windows, macOS, o Linux.
- **Extensible** — ver §2.3. Casi cada función especializada (el soporte
  de Python, esta misma integración con Claude, etc.) se añade mediante
  extensiones en lugar de estar integrada de forma permanente en el
  programa base.
- **Construido sobre Electron** — un framework que permite a los
  desarrolladores construir aplicaciones de escritorio usando
  tecnologías web (el mismo HTML/CSS/JavaScript usado para construir
  sitios web). Esto es *por qué* VS Code puede verse y sentirse igual en
  cada sistema operativo, y por qué su interfaz se puede personalizar
  ampliamente — es fundamentalmente una aplicación especializada,
  parecida a una página web, que se ejecuta en su propia ventana en
  lugar de una pestaña de navegador.

### 2.3 ¿Qué es una "extensión"?

Una **extensión** (también llamada plugin o complemento, según el
software) es una pieza de software separada y más pequeña que se conecta
a una aplicación "anfitriona" más grande para añadirle una capacidad
específica, sin que los desarrolladores originales de la aplicación
anfitriona hayan tenido que construir ellos mismos esa capacidad. Este es
un patrón de software extremadamente común, no exclusivo de VS Code — los
navegadores web tienen extensiones (bloqueadores de anuncios, gestores de
contraseñas), y muchos IDE también las tienen.

VS Code fue deliberadamente diseñado en torno a esta idea: su núcleo solo
hace lo básico (abrir archivos, editar texto, mostrar un árbol de
archivos), y esencialmente todo lo demás — soporte completo del lenguaje
Python, correctores ortográficos, temas, linters, asistentes de
programación con IA — se entrega como una extensión, instalada desde el
**Marketplace de extensiones** público de Microsoft. Esto mantiene el
programa base pequeño y rápido para quienes no necesitan cada función, a
la vez que le permite hacer casi cualquier cosa para quienes instalan las
extensiones que quieren.

### 2.4 ¿Cómo funciona Claude *dentro* de VS Code, en concreto?

La configuración de este proyecto es un ejemplo concreto de una extensión
en acción: el agente Claude Code (§1.5) está disponible como **extensión
de VS Code**. Una vez instalada, añade un panel/una interfaz específica
de Claude directamente dentro de la ventana de VS Code, así que en lugar
de cambiar a una ventana de terminal separada para ejecutar Claude Code
como un programa de línea de comandos independiente, interactúas con él
justo al lado de los archivos que está editando — y puede ver contexto
específico del IDE, como qué archivo tienes actualmente abierto
(probablemente hayas notado mensajes en este proyecto indicando "The user
opened the file..."). Por debajo, la extensión sigue siendo la misma
herramienta agéntica descrita en §1.5 — leyendo/escribiendo archivos,
ejecutando comandos de terminal — la extensión es simplemente la "puerta
de entrada" integrada en VS Code hacia ella, en lugar de una ventana de
terminal separada.

---

## Parte 3 — Python y conceptos de lenguajes de programación

### 3.1 ¿Qué es Python?

**Python** es un lenguaje de programación de alto nivel y de propósito
general, creado por Guido van Rossum y publicado por primera vez en 1991.
Cada script de la carpeta `scripts/` de este proyecto está escrito en
Python.

Qué significan exactamente "alto nivel" y "de propósito general":

- **Alto nivel** — el código Python se lee casi como inglés/matemáticas
  corrientes, y gestiona automáticamente mucho detalle de bajo nivel (la
  gestión de memoria, por ejemplo) para que el programador no tenga que
  pensar en ello. Esto es lo opuesto a un **lenguaje de bajo nivel**
  (como C o ensamblador), que te da un control explícito y detallado
  sobre el hardware del ordenador, a costa de mucho más código y
  complejidad para la misma tarea.
- **De propósito general** — no está construido para una única tarea
  estrecha (a diferencia, por ejemplo, de un lenguaje diseñado solo para
  dar estilo a páginas web). Python se usa para backends web, ciencia de
  datos, automatización/scripts (como los scripts de este proyecto),
  IA/ML, computación científica, y más.

### 3.2 Por qué Python es (según muchas métricas) el lenguaje más usado hoy en día

Algunas razones concretas y que se refuerzan entre sí, en lugar de
simplemente "es popular":

1. **Legibilidad por diseño** — el creador de Python optimizó
   deliberadamente la sintaxis del lenguaje para que fuera fácil de
   leer, llegando incluso a exigir una indentación consistente como
   parte de la gramática real del lenguaje (la mayoría de los lenguajes
   tratan la indentación como una mera preferencia de estilo; Python la
   exige).
2. **Un enorme ecosistema de bibliotecas ya construidas** — para casi
   cualquier tarea (descargar un archivo, analizar JSON, construir una
   red neuronal), casi con certeza alguien ya ha publicado una
   biblioteca de Python bien probada para ello (ver §3.7), así que rara
   vez se empieza desde cero.
3. **Curva de aprendizaje suave, techo alto** — genuinamente fácil de
   aprender como primer lenguaje, pero lo bastante potente como para ser
   el lenguaje dominante hoy en la investigación y los sistemas de
   producción de IA/ML.
4. **Interpretado, así que rápido para iterar** — ver §3.3; puedes
   ejecutar un script y ver el resultado de inmediato, sin un paso de
   "compilación" separado y lento.

### 3.3 Lenguajes compilados vs. interpretados

Esta es una distinción fundamental en cómo el código escrito por un
humano se convierte realmente en algo que el procesador del ordenador
puede ejecutar:

- **Lenguajes compilados** (p. ej. C, C++, Rust, Go) — antes de poder
  ejecutar el programa, una herramienta separada llamada **compilador**
  traduce todo el código fuente a **código máquina** (instrucciones
  crudas que el procesador entiende directamente) por adelantado,
  produciendo un archivo ejecutable. Este paso adicional ("compilar" o
  "build") puede llevar tiempo real, pero el programa resultante tiende
  luego a ejecutarse muy rápido, ya que el trabajo de traducción ya está
  hecho.
- **Lenguajes interpretados** (p. ej. Python, JavaScript, Ruby) — no hay
  un paso separado de compilación a código máquina que ejecutes tú
  mismo. En su lugar, un programa **intérprete** (para Python, esto es
  literalmente lo que se invoca cuando escribes
  `python scripts/peek_data.py`) lee y ejecuta el código fuente
  directamente, traduciéndolo y ejecutándolo sobre la marcha, línea por
  línea, cada vez que se ejecuta el programa. Esto hace que el ciclo
  escribir → ejecutar → ver el resultado sea más rápido (sin esperar un
  paso de build), a costa de algo de velocidad de ejecución en bruto en
  comparación con un lenguaje compilado.

(En realidad, el intérprete de Python compila discretamente el código a
una forma intermedia llamada **bytecode** primero, guardada en caché en
esos archivos `__pycache__/*.pyc` que quizá hayas notado que se generan
localmente — pero ese bytecode todavía no es código máquina, y sigue
siendo ejecutado por el intérprete de Python en lugar de directamente por
el procesador, así que Python se sigue describiendo correctamente como
interpretado desde la perspectiva del usuario.)

### 3.4 Lenguajes de tipado estático vs. dinámico

Un **tipo** es *qué clase* de valor es algo — un número entero (`int`),
texto (`str`), una lista, etc. (ya has visto este concepto directamente
en los scripts de este proyecto, p. ej. `Counter[str]`, `type=Path` en
`argparse`).

- Los **lenguajes de tipado estático** (p. ej. Java, C, Rust) requieren
  que declares el tipo de una variable de antemano, y el compilador
  comprueba — antes de que el programa siquiera se ejecute — que nunca
  intentas, por ejemplo, sumar un número a un fragmento de texto.
- Los **lenguajes de tipado dinámico** (p. ej. Python, JavaScript)
  averiguan automáticamente el tipo de una variable en el momento en que
  el código realmente se ejecuta, y el mismo nombre de variable puede
  incluso contener un tipo de valor distinto en diferentes puntos de un
  programa. Esto es más flexible y más rápido de escribir, a costa de
  que algunos errores solo salgan a la luz cuando esa línea exacta de
  código finalmente se ejecuta, en lugar de detectarse antes.

Python es de tipado dinámico por defecto, pero admite **anotaciones de
tipo** (*type hints*) opcionales (como
`def peek(file_path: Path, num_lines: int) -> None:` en el propio
`peek_data.py` de este proyecto) que no cambian cómo se ejecuta el
código, pero permiten que las herramientas/editores (y los lectores
humanos) detecten errores de tipo antes de ejecutar el código, y sirven
como documentación en línea de lo que espera una función.

### 3.5 ¿Qué es la Programación Orientada a Objetos (POO)?

La **Programación Orientada a Objetos** (POO, u OOP en inglés) es una
forma de organizar el código en torno a **objetos** — conjuntos que
combinan datos y las acciones que operan sobre esos datos en una sola
unidad — en lugar de en torno a una simple secuencia de instrucciones. El
vocabulario central:

- **Clase** (*class*) — un plano/plantilla que define qué tipo de datos
  contiene un objeto de este tipo, y qué acciones (métodos) puede
  realizar. Piénsalo como un molde de galletas.
- **Objeto** (o **instancia**) — una cosa real hecha a partir de ese
  plano. Si `Actor` fuera una clase, `github-actions[bot]` sería una
  *instancia* de ella. Piénsalo como una galleta real cortada con el
  molde.
- **Atributo** (o propiedad/campo) — un dato almacenado en un objeto,
  p. ej. un objeto `Actor` podría tener un atributo `.login`.
- **Método** — una función que pertenece a una clase, describiendo algo
  que los objetos de esa clase pueden *hacer*, p. ej. un objeto `Actor`
  podría tener un método `.push(repo)`.
- **Encapsulación** — agrupar los datos de un objeto junto con los
  métodos que operan sobre ellos, y ocultar sus detalles internos del
  resto del programa para que el resto del código interactúe con él a
  través de una interfaz limpia.
- **Herencia** (*inheritance*) — permitir que una clase se defina como
  una versión más específica de otra (p. ej. una clase `Bot` podría
  *heredar* de `Actor`, obteniendo automáticamente todo lo que tiene
  `Actor`, más sus propios añadidos). De hecho, ya has visto la herencia
  usada directamente en el propio código de este proyecto:
  `Counter[str]` en `summarize_data.py` / `profile_schema.py` es una
  clase que **hereda** de la clase `dict` integrada de Python, lo cual
  explica por qué admite las funciones normales de un dict (como
  `len()` y las búsquedas por clave) mientras añade su propio
  comportamiento adicional (incremento automático de claves ausentes,
  `.most_common()`).
- **Polimorfismo** — distintas clases que responden a la "misma" llamada
  a método cada una a su manera apropiada (p. ej. varias clases
  diferentes podrían cada una definir su propio método `.describe()` que
  se comporta de forma distinta según la clase, pero todas pueden
  llamarse de la misma manera desde otro código que no necesita saber
  con qué clase exacta está tratando).

**Una nota honesta y útil para tu propio aprendizaje:** ninguno de los
cuatro scripts de Python escritos para este proyecto hasta ahora
(`download_gharchive.py`, `peek_data.py`, `summarize_data.py`,
`profile_schema.py`) define en realidad ni una sola clase — están
escritos como simples funciones que operan sobre tipos integrados
ordinarios (`dict`, `list`, `str`, `Counter`). Esa fue una elección
deliberada y razonable para scripts de este tamaño y propósito (ver
§3.6) — no una señal de que se esté evitando la POO por ser "incorrecta".
Si este proyecto crece hacia algo con conceptos persistentes reales que
modelar — un `Actor`, un `Repo`, un `Node` de grafo — ese suele ser el
momento en que introducir clases reales empieza a valer la pena.

### 3.6 Otros paradigmas de programación (la POO es solo una opción)

Un **paradigma** es un estilo/una filosofía general para estructurar el
código. La POO es uno; estos son los otros más importantes de conocer:

- **Programación procedural** — código organizado como una secuencia
  directa de instrucciones y llamadas a funciones que operan sobre datos
  pasados entre ellas, sin agrupar datos y comportamiento en objetos.
  Este es, de hecho, el estilo en que están escritos los scripts de este
  proyecto hasta ahora: simples funciones (`peek()`, `summarize()`,
  `profile()`) llamadas una tras otra desde `main()`, cada una recibiendo
  datos como parámetros y devolviendo resultados, sin ninguna clase
  involucrada.
- **Programación funcional** (p. ej. Haskell, y un estilo también
  utilizable dentro de Python/JavaScript) — código construido en torno a
  llamar funciones puras (funciones cuya salida depende solo de su
  entrada, sin estado oculto modificado en otro lugar) y evitando datos
  mutables siempre que sea posible.
- **Programación declarativa** — describes *qué resultado quieres*, y
  dejas que el sistema subyacente determine *cómo* llegar ahí, en lugar
  de detallar cada paso tú mismo. SQL (el lenguaje de consulta de bases
  de datos) es un ejemplo clásico: `SELECT * FROM actors WHERE login =
  'octocat'` describe el resultado deseado; el motor de la base de datos
  decide cómo ir realmente a buscarlo. Esto se contrasta con la
  **programación imperativa** (Python, incluyendo los scripts de este
  proyecto, es normalmente imperativo), donde escribes explícitamente el
  "cómo" paso a paso.
- Python es genuinamente un lenguaje **multiparadigma** — admite los
  estilos procedural, orientado a objetos, y (en buena medida) funcional,
  y permite que un proyecto elija el que mejor encaje para una parte
  concreta del código, en lugar de imponer un único paradigma en todas
  partes.

### 3.7 Biblioteca, módulo, paquete, y framework — relacionados pero distintos

Estas cuatro palabras se usan a menudo de forma laxa, pero tienen una
distinción real:

- **Módulo** — un único archivo de código Python que se puede importar y
  reutilizar en otro lugar, p. ej. los propios `json` y `pathlib` de este
  proyecto provienen de los módulos integrados de Python.
- **Biblioteca** (*library*) — una colección de módulos, normalmente
  construida y publicada por otra persona, que ofrece funcionalidad
  reutilizable para una categoría general de tarea (p. ej. una biblioteca
  para hablar con bases de datos). `Counter` en los scripts de este
  proyecto proviene de `collections`, una biblioteca que viene integrada
  en el propio Python (forma parte de lo que se llama la **biblioteca
  estándar**, *standard library* — el amplio conjunto de bibliotecas que
  vienen con Python automáticamente, sin necesidad de instalación).
- **Paquete** (*package*) — técnicamente, una forma específica de
  organizar varios módulos relacionados juntos (una carpeta con un
  archivo `__init__.py`, en el caso de Python) — pero en la conversación
  cotidiana, "paquete" se usa a menudo de forma intercambiable con
  "biblioteca", especialmente al hablar de instalar uno (ver §5.6,
  gestores de paquetes).
- **Framework** — un software reutilizable más grande y con más
  convicciones propias, que no se limita a ofrecer herramientas que *tu*
  código llama, sino que en realidad estructura toda la aplicación y
  llama a *tu* código en los puntos donde lo necesita (a veces resumido
  como "una biblioteca, tú la llamas; un framework te llama a ti").
  Django (para aplicaciones web en Python) es un ejemplo bien conocido.
  Ninguno de los scripts de este proyecto usa un framework — son lo
  bastante pequeños como para que baste con un puñado de módulos de la
  biblioteca estándar.

---

## Parte 4 — JSON: impresión formateada (pretty-printed) vs. JSON Lines

El conjunto de datos de este proyecto
([gh-archive-guide.md](gh-archive-guide.md)) se entrega específicamente
en formato JSON Lines, lo que hace que esta comparación sea directamente
relevante, y no solo teórica.

### 4.1 Qué es JSON, de nuevo, brevemente

**JSON** (JavaScript Object Notation) es un formato ligero, basado en
texto, para representar datos estructurados — objetos (como los dict de
Python, con `{ "clave": valor }`), arreglos/listas (`[valor, valor]`),
cadenas, números, booleanos (`true`/`false`), y `null` — que tanto
humanos como máquinas pueden leer con razonable facilidad. A pesar del
nombre, ahora lo usan prácticamente todos los lenguajes de programación,
no solo JavaScript, como una forma universal de intercambiar datos
estructurados entre programas, archivos, y a través de internet.

### 4.2 JSON "pretty-printed" (formateado para humanos)

El JSON **pretty-printed** (o "formateado"/"indentado") es texto JSON que
se ha diseñado para la legibilidad humana: cada clave tiene su propia
línea, los objetos anidados se indentan más que su padre, y el espaciado
es consistente. Ejemplo — un único evento, pretty-printed:

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
  "created_at": "2026-08-27T15:03:11Z"
}
```

Así es exactamente como se muestra el ejemplo "Anatomía de un evento" en
[gh-archive-guide.md](gh-archive-guide.md) — deliberadamente, ya que todo
el propósito de esa sección es que un humano lea y entienda la forma de
un evento. El espacio en blanco (saltos de línea, indentación) no tiene
*ningún* significado para un programa que analiza esto — `json.loads()`
(ver la copia anotada de `peek_data.py`) analiza el JSON pretty-printed y
el JSON en una sola línea exactamente de la misma manera, produciendo el
mismo dict de Python en ambos casos. El pretty-print existe puramente
para los humanos, no para el analizador (*parser*).

### 4.3 JSON Lines (JSONL / NDJSON)

**JSON Lines** (a veces llamado **JSONL** o **NDJSON**, por
"Newline-Delimited JSON", JSON delimitado por saltos de línea) es una
convención distinta, a nivel de *archivo*: en lugar de una sola
estructura JSON grande, posiblemente pretty-printed, que abarca todo el
archivo, el archivo contiene muchos objetos JSON *separados e
independientes*, cada uno escrito enteramente en su propia línea única,
sin comas ni corchetes `[ ]` envolventes que los conecten entre sí. Este
es exactamente el formato que usan los volcados horarios de GH Archive —
observa el estilo compacto, de una sola línea, del archivo en bruto si
miras directamente `data/2026-08-27-15.json`, frente al ejemplo
ilustrativo deliberadamente pretty-printed de arriba.

### 4.4 Lado a lado: los mismos tres eventos, de las dos formas

**JSON pretty-printed, como un arreglo (NO es así como GH Archive lo
almacena):**

```json
[
  {
    "type": "PushEvent",
    "actor": { "login": "alice" },
    "repo": { "name": "alice/project" }
  },
  {
    "type": "WatchEvent",
    "actor": { "login": "bob" },
    "repo": { "name": "alice/project" }
  },
  {
    "type": "ForkEvent",
    "actor": { "login": "carol" },
    "repo": { "name": "alice/project" }
  }
]
```

**Los mismos tres eventos como JSON Lines (así SÍ es como GH Archive los
almacena):**

```
{"type": "PushEvent", "actor": {"login": "alice"}, "repo": {"name": "alice/project"}}
{"type": "WatchEvent", "actor": {"login": "bob"}, "repo": {"name": "alice/project"}}
{"type": "ForkEvent", "actor": {"login": "carol"}, "repo": {"name": "alice/project"}}
```

### 4.5 Por qué JSON Lines es la elección correcta para un conjunto de datos como este

Esto no es una elección de estilo arbitraria — JSON Lines tiene ventajas
prácticas reales para exactamente el tipo de datos que publica GH
Archive:

1. **Transmisible en flujo, un registro a la vez** (*streamable*). Un
   único arreglo JSON pretty-printed que contiene 69.429 eventos es,
   técnicamente, *un solo* valor JSON — muchos analizadores necesitan
   leer el archivo *completo* en memoria antes de poder darte siquiera
   el primer evento, porque necesitan encontrar el `]` de cierre
   correspondiente para saber si la estructura es siquiera válida. JSON
   Lines se puede leer y procesar una línea — un evento — a la vez, que
   es exactamente lo que hace cada script de este proyecto
   (`for line in f:` en `peek_data.py`, `summarize_data.py`, y
   `profile_schema.py`), sin necesitar nunca todo el archivo de más de
   47 MB en memoria a la vez.
2. **De forma natural, se puede añadir al final** (*appendable*). Se
   puede agregar un nuevo evento a un archivo JSON Lines simplemente
   escribiendo una línea más al final — sin necesidad de encontrar y
   reescribir un corchete de cierre, ni preocuparse por una coma
   faltante/sobrante entre elementos del arreglo, ambos riesgos reales
   al añadir a un arreglo JSON pretty-printed.
3. **Una sola línea defectuosa no rompe todo el archivo.** Si una línea
   está corrupta, todas las demás líneas siguen siendo analizables de
   forma independiente; un único error de sintaxis en un enorme arreglo
   JSON pretty-printed puede hacer que el archivo *entero* no se pueda
   analizar, ya que técnicamente es todo un único valor JSON.
4. **Un tamaño de archivo más pequeño.** No hay espacio en blanco de
   indentación que almacenar para millones de registros — esto importa a
   la escala de GH Archive (cada hora, cada día, para siempre).

El compromiso es exactamente lo opuesto del §4.2: un archivo JSON Lines
en bruto es notablemente más difícil de leer directamente a simple vista
para un *humano* que una versión pretty-printed, ya que todo está
apiñado en líneas únicas, a menudo muy largas — que es precisamente por
qué existen `peek_data.py` y la sección "Anatomía de un evento" de esta
guía: para mostrar una *vista* pretty-printed y amigable para el humano
de lo que estructuralmente son los mismos datos.

---

## Parte 5 — Más conceptos fundamentales que vale la pena conocer

Un conjunto de otros conceptos que aparecen constantemente en cuanto se
trabaja con cualquiera de las herramientas anteriores, agrupados
vagamente por tema.

### 5.1 Código fuente, programa, script, y aplicación

- **Código fuente** — el texto escrito/legible por un humano de un
  programa, antes de cualquier compilación/interpretación.
- **Programa** — el término general para un conjunto de instrucciones que
  ejecuta un ordenador.
- **Script** — normalmente se refiere a un programa más pequeño, a menudo
  de propósito único, típicamente ejecutado mediante un lenguaje
  interpretado, pensado para automatizar una tarea (exactamente lo que
  son los cuatro archivos `scripts/*.py` de este proyecto).
- **Aplicación** (o "app") — normalmente implica algo más grande, más
  completo, y a menudo con una interfaz de usuario, pensado para un uso
  repetido y general (VS Code en sí es una aplicación; `peek_data.py` es
  un script).

### 5.2 CLI vs. GUI

- **CLI (Command-Line Interface, interfaz de línea de comandos)** —
  interactúas con el software escribiendo comandos de texto en un
  terminal y leyendo una salida de texto (p. ej. ejecutar
  `python scripts/peek_data.py`, o usar comandos `git`).
- **GUI (Graphical User Interface, interfaz gráfica de usuario)** —
  interactúas con el software visualmente, mediante ventanas, botones, y
  un ratón/pantalla táctil (p. ej. la propia ventana del editor de VS
  Code, o hacer clic en un sitio web).
Muchas herramientas, incluida la propia cadena de herramientas de este
proyecto, ofrecen ambas: puedes usar `git` completamente desde la línea
de comandos, o a través del panel gráfico de git integrado en VS Code;
el propio Claude Code se puede usar como una herramienta CLI pura *o* a
través del panel gráfico de la extensión de VS Code (§2.4) — el mismo
agente subyacente, dos interfaces distintas hacia él.

### 5.3 Terminal, shell, y línea de comandos

- **Terminal** — la ventana/programa que te permite escribir comandos de
  texto y ver una salida de texto (este proyecto usa Git Bash en
  Windows, según las notas de entorno que hayas podido ver).
- **Shell** — el programa real *dentro* del terminal que lee los comandos
  que escribes, los interpreta, y los ejecuta (p. ej. `bash`, o
  `cmd`/PowerShell en Windows). "Terminal" y "shell" se usan a menudo de
  forma intercambiable en la conversación informal, pero estrictamente,
  el terminal es la ventana/interfaz, y el shell es el programa que se
  ejecuta dentro haciendo la interpretación real.
- **Línea de comandos** — el término general para interactuar con un
  shell escribiendo comandos individuales (como
  `python scripts/peek_data.py` o `git status`).

### 5.4 Repositorio, directorio de trabajo, y conceptos básicos del sistema de archivos

- **Repositorio ("repo")** — como se cubre en
  [gh-archive-guide.md](gh-archive-guide.md) en el sentido de GitHub, y
  usado a lo largo de [project-notes.md](project-notes.md) en el sentido
  de git: una carpeta cuyo historial rastrea git (toda esta carpeta
  `Research` es una de ellas).
- **Directorio de trabajo** (o "directorio actual") — la carpeta en la
  que un terminal o programa se encuentra "parado" actualmente, lo cual
  importa porque muchos comandos (como `python scripts/peek_data.py`,
  ejecutado como una ruta *relativa*) solo funcionan correctamente si se
  ejecutan desde el directorio de trabajo correcto — ver la explicación
  que ya aparece en la sección "Testing Phase" de
  [project-notes.md](project-notes.md).
- **Ruta (path)** — la dirección de un archivo o carpeta en el sistema de
  archivos, ya sea **absoluta** (la ruta completa desde el nivel más
  alto, p. ej. `C:\dev\Research\scripts\peek_data.py`), o **relativa**
  (la ruta desde donde te encuentras actualmente, p. ej. simplemente
  `scripts/peek_data.py` estando parado en `C:\dev\Research`). Los
  scripts de este proyecto usan el `pathlib.Path` de Python (ver la
  copia anotada de `download_gharchive.py`) específicamente para
  manejar correctamente y de forma portable ambos tipos de rutas, en
  cualquier sistema operativo.

### 5.5 Estructuras de datos usadas constantemente en este proyecto

- **Cadena de texto (`str`)** — texto.
- **Entero (`int`)** / **Flotante (float)** — números enteros / números
  decimales.
- **Booleano (`bool`)** — `True` o `False`.
- **Lista / arreglo** — una colección ordenada de valores (Python llama a
  esto una `list`; JSON llama al equivalente un *arreglo* (*array*),
  escrito `[ ]`).
- **Diccionario / mapa / tabla hash / objeto** — una colección de pares
  `clave: valor`, que permite buscar un valor por su clave en lugar de
  por su posición (Python llama a esto un `dict`; JSON llama al
  equivalente un *objeto*, escrito `{ }`). Los eventos de este proyecto
  son, una vez analizados, exactamente esto: dict de Python, consultados
  por clave (`event["type"]`, `event["actor"]["login"]`).
- **`None` / `null`** — la ausencia explícita de un valor (Python lo
  escribe `None`; JSON escribe el mismo concepto `null` — has visto esto
  directamente en la propia salida de `profile_schema.py` de este
  proyecto, p. ej.
  `payload.description ... types: str x657, NoneType x633`).

### 5.6 Gestores de paquetes y entornos virtuales

- **Gestor de paquetes** (*package manager*) — una herramienta que
  automatiza la búsqueda, descarga, e instalación de bibliotecas
  publicadas por otras personas (y sus propias dependencias, de forma
  recursiva), en lugar de que lo hagas tú a mano. El estándar de Python
  es **pip**; descarga paquetes desde un índice público llamado **PyPI**
  (el Python Package Index). Este proyecto aún no ha necesitado pip, ya
  que cada import usado hasta ahora (`argparse`, `json`, `collections`,
  `pathlib`) forma parte de la biblioteca estándar integrada de
  Python — no se requiere instalación.
- **Entorno virtual** (*virtual environment*) — una copia aislada y
  autocontenida de una instalación de Python y sus paquetes instalados,
  mantenida separada por proyecto, para que el Proyecto A que necesita
  la versión 1 de alguna biblioteca y el Proyecto B que necesita la
  versión 2 de la misma biblioteca no entren en conflicto entre sí en el
  mismo ordenador. Vale la pena conocerlo aunque este proyecto aún no lo
  haya necesitado (de nuevo, precisamente porque solo ha usado la
  biblioteca estándar hasta ahora) — se vuelve necesario en el momento en
  que un proyecto necesita su primer paquete *externo*.

### 5.7 API, HTTP, y URL

- **API (Application Programming Interface, interfaz de programación de
  aplicaciones)** — en términos generales, cualquier forma definida para
  que una pieza de software hable con otra. Este es un término
  general — el módulo `json` de Python tiene una API (las
  funciones/el comportamiento que expone para que otro código las
  llame); Claude también tiene una API (§1.4).
- **API web / API HTTP** — el caso específico, extremadamente común, de
  una API accesible a través de internet usando **HTTP** (HyperText
  Transfer Protocol — el mismo protocolo subyacente que usan los
  navegadores web para cargar páginas web), identificada por una **URL**
  (la dirección web). El `download_gharchive.py` de este proyecto es un
  ejemplo concreto: hace una solicitud HTTP a
  `https://data.gharchive.org/2026-08-27-15.json.gz` — exactamente el
  mismo tipo de solicitud que hace un navegador cuando visitas una
  página, solo que hecha por un script de Python en lugar de haciendo
  clic en un enlace.

### 5.8 Software de código abierto vs. propietario

- **Código abierto (open source)** — el código fuente del software está
  disponible públicamente para que cualquiera lo lea, lo modifique, y a
  menudo lo redistribuya, normalmente bajo una licencia específica (este
  mismo proyecto usa la **licencia MIT**, registrada en
  [LICENSE](../LICENSE) — una de las licencias de código abierto más
  permisivas y comunes). El propio Python, el núcleo de VS Code, y gran
  parte de aquello de lo que depende este proyecto, son de código
  abierto.
- **Software propietario** — el código fuente lo mantiene privado quien
  lo posee; normalmente solo puedes usar el programa terminado y
  compilado, sin poder ver ni modificar cómo funciona internamente.
Estos no son estrictamente opuestos en la práctica — p. ej. el núcleo del
editor de VS Code es de código abierto, pero la versión oficial
construida por Microsoft también agrupa telemetría/branding propietario
encima de ese núcleo de código abierto.

### 5.9 Sintaxis vs. semántica

- **Sintaxis** — las *reglas* gramaticales de cómo debe escribirse el
  código para siquiera ser válido (p. ej. Python exige dos puntos `:`
  antes de un bloque indentado, como en
  `def peek(file_path: Path, num_lines: int) -> None:`). Un error de
  sintaxis significa que el código ni siquiera está estructurado de una
  forma que el lenguaje pueda analizar, sin importar qué intentaba
  hacer.
- **Semántica** — el *significado*/comportamiento real del código escrito
  correctamente. El código puede tener una sintaxis perfectamente válida
  y aun así hacer lo incorrecto (un "error lógico" o "error semántico")
  — p. ej. contar accidentalmente `event["repo"]["name"]` cuando querías
  contar `event["actor"]["login"]` se ejecutaría sin fallar, pero
  produciría una respuesta incorrecta.

### 5.10 Una nota sobre la palabra "token" (para evitar confundir dos significados sin relación)

Esta palabra se reutiliza para dos conceptos genuinamente distintos,
ambos relevantes para este proyecto:

- El **token de LLM** descrito en §1.3 — un fragmento de texto (parte de
  cómo Claude lee y genera lenguaje).
- Un **token de acceso** / **token de API** / **credencial** — una cadena
  secreta usada para demostrar *quién eres* ante un servicio (p. ej. lo
  que realmente autentica un `git push` hacia GitHub, o una llamada a la
  API de Claude). Estos son sensibles y nunca deben incluirse en un
  commit de un repositorio git ni compartirse — un significado
  notablemente distinto del sentido de LLM de arriba, a pesar del nombre
  compartido.
