# Tools & Concepts Guide: AI, Claude, VS Code, Python, and the Fundamentals Behind Them

This guide exists for learning purposes: a thorough, from-first-principles
explanation of the tools this project uses (Claude, VS Code, Python) and
the computer-science concepts underneath them, written so you could later
explain any of it to someone else in your own words. It's meant to be read
alongside [project-notes.md](project-notes.md) (the workflow/why) and
[gh-archive-guide.md](gh-archive-guide.md) (the dataset specifics).

---

## Part 1 — Artificial Intelligence and Claude

### 1.1 What is Artificial Intelligence (AI)?

**Artificial Intelligence** is the general field of building computer
systems that perform tasks which normally require human intelligence:
understanding language, recognizing images, making decisions, solving
problems, learning from experience. "AI" is a broad umbrella term, not one
single technology — it covers everything from a simple chess-playing
program with hand-coded rules, to the large language models (like Claude)
that write and hold conversations.

A useful way to picture the field is as a set of nested circles, each one
a more specific technique inside the one before it:

```
Artificial Intelligence (AI)
  └── Machine Learning (ML)
        └── Deep Learning
              └── Large Language Models (LLMs)  <- Claude lives here
```

- **Artificial Intelligence** — the broadest goal: machines that behave
  intelligently, by any method (rules, search, statistics, learning).
- **Machine Learning (ML)** — a specific *approach* to AI: instead of a
  programmer writing explicit rules for every situation ("if the email
  contains 'free money', mark it as spam"), the system is shown many
  examples (thousands of emails already labeled spam or not-spam) and
  learns the pattern itself. The program that results is called a
  **model**.
- **Deep Learning** — a family of ML techniques based on **neural
  networks**: layered mathematical structures loosely inspired by how
  neurons connect in a brain. "Deep" refers to having many layers stacked
  on top of each other. Deep learning is what made modern image
  recognition, speech recognition, and language models practical.
- **Large Language Models (LLMs)** — deep learning models trained on huge
  amounts of text, whose core skill is predicting what text comes next
  given some text so far. That one skill — "predict the next piece of
  text" — turns out to be powerful enough, at large enough scale, to
  produce something that can answer questions, write code, reason through
  problems, and hold a conversation. Claude is an LLM.

### 1.2 Training vs. inference — two very different phases

- **Training** is the (extremely expensive, done once by Anthropic on huge
  computing clusters) process of showing the model enormous amounts of
  text and adjusting millions/billions of internal numbers (called
  **parameters** or **weights**) so its predictions get better and better.
  This is where the model "learns."
- **Inference** is what happens every time you actually *use* the already-
  trained model — like this conversation. No learning happens during
  inference in the usual sense; the model's weights are fixed, and it's
  just running its (very large) fixed mathematical function on your input
  to produce output. Every message you send to Claude is one inference
  run, not a new round of training.

### 1.3 What is a "model," a "prompt," and a "token"?

- **Model** — the trained neural network itself: a huge, fixed set of
  numbers (weights) plus the code that runs them. "Claude" refers to a
  family of such models (there have been several generations/sizes).
- **Prompt** — the text you feed into the model as input. In a
  conversation, the "prompt" effectively grows to include the whole
  conversation history each time, which is why a model can refer back to
  something said earlier.
- **Token** — the model doesn't process text one character or one word at
  a time; it breaks text into chunks called tokens (often close to
  word-sized, sometimes a whole word, sometimes a word-fragment or a
  single punctuation mark). "Tokens" are the unit the model actually
  predicts one at a time when generating a reply, and the unit used to
  measure how much text fits in the model's **context window** (the
  maximum amount of prior conversation/text the model can "see" at once).
  (Don't confuse this with an *API token* or *access token*, an unrelated,
  security-related meaning of "token" used for authentication — see
  §5.10.)

### 1.4 What is Claude, specifically?

**Claude** is the family of large language models built by **Anthropic**,
an AI safety-focused company. Claude is accessed in a few different ways,
which matters for understanding what's actually happening in this project:

- **claude.ai** — a chat website/app, similar in spirit to a messaging app,
  where you type messages and Claude replies with text.
- **The Claude API** — a way for *developers* to send prompts to Claude
  programmatically from their own code/apps, instead of through a chat
  website. This is how companies build Claude into their own products.
- **Claude Code** — an *agentic* command-line tool (and, as used in this
  project, a VS Code extension built on top of it) that doesn't just chat
  with you in plain text — it can read and write real files on your
  computer, run real terminal commands, search your codebase, and so on,
  in order to actually carry out software engineering tasks. This is what
  wrote and ran every script in this project's `scripts/` folder.

### 1.5 "Agentic" — what makes Claude Code different from a chatbot

A plain chat AI takes your message and gives back a text reply — it has no
way to actually *do* anything in the world. An **agent** (in this sense)
is an AI system that has been given access to **tools** — concrete
actions it's allowed to perform, like "read this file," "run this shell
command," "search for this text across the project" — and can decide,
step by step, which tool to use next based on what it learns from the
result of the previous one. "Agentic" describes this loop of
observe → decide → act → observe the result → decide again. Every time
you've seen a command actually run against this repository in this
project (downloading data, running `peek_data.py`, editing a `.md` file),
that was Claude Code using a tool as part of this agentic loop — not just
describing what you should do, but doing it.

---

## Part 2 — IDEs, VS Code, and Extensions

### 2.1 What is an IDE?

**IDE** stands for **Integrated Development Environment**. It's a single
application that bundles together the tools a programmer needs, instead of
using separate, disconnected programs for each one:

- a **code editor** (for writing and reading source code, usually with
  syntax highlighting — coloring code by its grammatical role — and
  autocomplete)
- a **terminal** (a text-based command line, see §5.8) built right in
- **debugging tools** (running code one step at a time, inspecting
  variables, to find bugs)
- **version control integration** (git — see
  [git-commands-guide.md](git-commands-guide.md) — built in, rather than
  needing a separate program)
- often, **build/compile tools**, project/file management, and extension
  systems

The word "Integrated" is the key part: all of this lives in one place,
so you're not constantly switching between a text editor, a separate
terminal window, and a separate git tool. Other well-known IDEs include
PyCharm (Python-focused), IntelliJ IDEA (Java-focused), and Xcode
(Apple platforms).

An IDE is a step up from a **plain text editor** (like Notepad, or even a
simpler code editor without IDE features) — a plain text editor just lets
you type and save text, with none of the integrated tooling above.

### 2.2 What is VS Code?

**VS Code** (Visual Studio Code) is a free, popular IDE-style code editor
made by Microsoft. Despite the similar name, it is a *different product*
from "Visual Studio" (a much older, heavier, Windows-centric IDE mostly
for C#/.NET) — VS Code is lighter weight, cross-platform (runs the same
way on Windows, macOS, and Linux), and its core is open source.

Key properties that explain why it's become so widely used:

- **Lightweight but capable** — starts fast, doesn't demand much from the
  computer, yet still has a real debugger, git integration, and an
  integrated terminal built in.
- **Cross-platform** — the exact same editor, same shortcuts, same
  extensions, whether you're on Windows, macOS, or Linux.
- **Extensible** — see §2.3. Almost every specialized feature (Python
  support, this very Claude integration, etc.) is added via extensions
  rather than being baked permanently into the core program.
- **Built on Electron** — a framework that lets developers build desktop
  applications using web technologies (the same HTML/CSS/JavaScript used
  to build websites). This is *why* VS Code can look and feel similar
  across every operating system, and why its interface can be customized
  extensively — it's fundamentally a specialized web-page-like application
  running in its own window in place of a browser tab.

### 2.3 What is an "extension"?

An **extension** (also called a plugin or add-on, depending on the
software) is a separate, smaller piece of software that plugs into a
larger "host" application to add a specific capability, without the host
application's original developers having had to build that capability
themselves. This is an extremely common software pattern, not unique to
VS Code — web browsers have extensions (ad blockers, password managers),
and many IDEs have them too.

VS Code was deliberately designed around this idea: its core only does the
basics (open files, edit text, show a file tree), and essentially
everything else — full Python language support, spell-checkers, themes,
linters, AI coding assistants — is delivered as an extension, installed
from Microsoft's public **Extension Marketplace**. This keeps the base
program small and fast for people who don't need every feature, while
still letting it do almost anything for people who install the extensions
they want.

### 2.4 How does Claude work *inside* VS Code, specifically?

This project's setup is a concrete example of an extension in action: the
Claude Code agent (§1.5) is available as a **VS Code extension**. Once
installed, it adds a Claude-specific panel/interface directly inside the
VS Code window, so instead of switching to a separate terminal window to
run Claude Code as a standalone command-line program, you interact with it
right next to the files it's editing — and it can see IDE-specific
context, such as which file you currently have open (you've likely
noticed messages in this project noting "The user opened the file...").
Under the hood, the extension is still the same agentic tool described in
§1.5 — reading/writing files, running terminal commands — the extension
is simply the VS Code-integrated "front door" to it, instead of a
separate terminal window.

---

## Part 3 — Python and Programming Language Concepts

### 3.1 What is Python?

**Python** is a high-level, general-purpose programming language, created
by Guido van Rossum and first released in 1991. Every script in this
project's `scripts/` folder is written in Python.

What "high-level" and "general-purpose" mean, precisely:

- **High-level** — Python code reads close to plain English/math, and
  handles a lot of low-level detail automatically (memory management,
  for instance) so the programmer doesn't have to think about it. This is
  the opposite of a **low-level language** (like C or assembly), which
  gives you fine-grained, explicit control over the computer's hardware
  at the cost of far more code and complexity for the same task.
- **General-purpose** — it isn't built for one narrow job (unlike, say, a
  language purpose-built only for styling web pages). Python is used for
  web backends, data science, automation/scripting (like this project's
  scripts), AI/ML, scientific computing, and more.

### 3.2 Why Python is (by many measures) the most-used language today

A few concrete, reinforcing reasons, rather than just "it's popular":

1. **Readability by design** — Python's creator deliberately optimized the
   language's syntax for being easy to read, even enforcing consistent
   indentation as part of the language's actual grammar (most languages
   treat indentation as just a style preference; Python requires it).
2. **A huge ecosystem of pre-built libraries** — for nearly any task
   (downloading a file, parsing JSON, building a neural network), someone
   has almost certainly already published a well-tested Python library
   for it (see §3.7), so you rarely start from scratch.
3. **Gentle learning curve, high ceiling** — genuinely easy to pick up as
   a first language, yet powerful enough to be the dominant language in
   AI/ML research and production systems today.
4. **Interpreted, so fast to iterate** — see §3.3; you can run a script
   and see the result immediately, without a separate, slow "build" step.

### 3.3 Compiled vs. interpreted languages

This is a fundamental distinction in how code written by a human actually
gets turned into something the computer's processor can run:

- **Compiled languages** (e.g. C, C++, Rust, Go) — before you can run the
  program, a separate tool called a **compiler** translates the entire
  source code into **machine code** (raw instructions the processor
  understands directly) ahead of time, producing an executable file. This
  extra step ("compiling" or "building") can take real time, but the
  resulting program then tends to run very fast, since the translation
  work is already done.
- **Interpreted languages** (e.g. Python, JavaScript, Ruby) — there is no
  separate compile-to-machine-code step you run yourself. Instead, an
  **interpreter** program (for Python, this is what's literally invoked
  when you type `python scripts/peek_data.py`) reads and executes the
  source code directly, translating and running it on the fly, line by
  line, each time the program runs. This makes the write → run → see the
  result loop faster (no waiting on a build step), at some cost to raw
  execution speed compared to a compiled language.

(In reality, Python's interpreter does quietly compile code to an
intermediate form called **bytecode** first, cached in those
`__pycache__/*.pyc` files you may have noticed being generated locally —
but that bytecode still isn't machine code, and it's still executed by
the Python interpreter rather than run directly by the processor, so
Python is still correctly described as interpreted from a user's
perspective.)

### 3.4 Statically vs. dynamically typed languages

A **type** is what *kind* of value something is — a whole number (`int`),
text (`str`), a list, and so on (you've already seen this concept directly
in this project's scripts, e.g. `Counter[str]`, `type=Path` in
`argparse`).

- **Statically typed languages** (e.g. Java, C, Rust) require you to
  declare a variable's type up front, and the compiler checks — before
  the program ever runs — that you never, say, try to add a number to a
  piece of text.
- **Dynamically typed languages** (e.g. Python, JavaScript) figure out a
  variable's type automatically at the moment the code actually runs, and
  the same variable name can even hold a different type of value at
  different points in a program. This is more flexible and faster to
  write, at the cost of some errors only surfacing when that exact line
  of code finally runs, instead of being caught earlier.

Python is dynamically typed by default, but supports optional **type
hints** (like `def peek(file_path: Path, num_lines: int) -> None:` in
this project's own `peek_data.py`) that don't change how the code runs,
but let tools/editors (and human readers) catch type mistakes before
running the code, and serve as inline documentation of what a function
expects.

### 3.5 What is Object-Oriented Programming (OOP)?

**Object-Oriented Programming** is a way of organizing code around
**objects** — bundles that combine data and the actions that operate on
that data into one unit — rather than around a plain sequence of
instructions. The core vocabulary:

- **Class** — a blueprint/template that defines what kind of data an
  object of this kind holds, and what actions (methods) it can perform.
  Think of it like a cookie cutter.
- **Object** (or **instance**) — one actual thing made from that
  blueprint. If `Actor` were a class, `github-actions[bot]` would be one
  *instance* of it. Think of it like one actual cookie cut from the
  cutter.
- **Attribute** (or property/field) — a piece of data stored on an
  object, e.g. an `Actor` object might have a `.login` attribute.
- **Method** — a function that belongs to a class, describing something
  objects of that class can *do*, e.g. an `Actor` object might have a
  `.push(repo)` method.
- **Encapsulation** — bundling an object's data together with the methods
  that operate on it, and hiding its internal details from the rest of
  the program so other code interacts with it through a clean interface.
- **Inheritance** — letting one class be defined as a more specific
  version of another (e.g. a `Bot` class could *inherit* from `Actor`,
  automatically getting everything `Actor` has, plus its own extras).
  You've actually already seen inheritance used directly in this
  project's own code: `Counter[str]` in `summarize_data.py` /
  `profile_schema.py` is a class that **inherits** from Python's built-in
  `dict` class, which is why it supports normal dict features (like
  `len()` and key lookups) while adding its own extra behavior
  (auto-incrementing missing keys, `.most_common()`).
- **Polymorphism** — different classes responding to the "same" method
  call in their own appropriate way (e.g. many different classes might
  each define their own `.describe()` method that behaves differently
  per class, but can all be called the same way from other code that
  doesn't need to know which exact class it's dealing with).

**A worthwhile honest note for your own learning:** none of the four
Python scripts written for this project so far (`download_gharchive.py`,
`peek_data.py`, `summarize_data.py`, `profile_schema.py`) actually define
a single class of their own — they're written as plain functions
operating on plain built-in types (`dict`, `list`, `str`, `Counter`). That
was a deliberate, reasonable choice for scripts this size and purpose (see
§3.6) — not a sign that OOP is being avoided as "wrong." If this project
grows into something with real persistent concepts to model — an `Actor`,
a `Repo`, a graph `Node` — that's usually the point where introducing
actual classes starts paying off.

### 3.6 Other programming paradigms (OOP is only one option)

A **paradigm** is a general style/philosophy for structuring code. OOP is
one; here are the others most worth knowing:

- **Procedural programming** — code organized as a straightforward
  sequence of instructions and function calls that operate on data passed
  between them, without bundling data and behavior into objects. This is
  the style this project's scripts are actually written in so far: plain
  functions (`peek()`, `summarize()`, `profile()`) called one after
  another from `main()`, each taking data in as parameters and returning
  results, no classes involved.
- **Functional programming** (e.g. Haskell, and a style usable within
  Python/JavaScript too) — code built around calling pure functions
  (functions whose output depends only on their input, with no hidden
  state changed elsewhere) and avoiding mutable data wherever possible.
- **Declarative programming** — you describe *what result you want*, and
  let the underlying system figure out *how* to get there, rather than
  spelling out every step yourself. SQL (database query language) is a
  classic example: `SELECT * FROM actors WHERE login = 'octocat'`
  describes the desired result; the database engine decides how to
  actually go find it. This is contrasted with **imperative
  programming** (Python, including this project's scripts, is normally
  imperative), where you write out the explicit step-by-step "how."
- Python is a genuinely **multi-paradigm** language — it supports
  procedural, object-oriented, and (to a good extent) functional styles,
  and lets a project pick whichever fits a given piece of code best,
  rather than forcing one paradigm throughout.

### 3.7 Library, module, package, and framework — related but distinct

These four words are often used loosely, but have a real distinction:

- **Module** — a single file of Python code that can be imported and
  reused elsewhere, e.g. this project's own `json` and `pathlib` come
  from Python's built-in modules.
- **Library** — a collection of modules, usually built and published by
  someone else, that provides reusable functionality for a general
  category of task (e.g. a library for talking to databases). `Counter`
  in this project's scripts comes from `collections`, a library that
  ships built into Python itself (part of what's called the **standard
  library** — the large set of libraries that come with Python
  automatically, no installation needed).
- **Package** — technically, a specific way of organizing multiple
  related modules together (a folder with an `__init__.py` file, in
  Python's case) — but in everyday conversation, "package" is often used
  interchangeably with "library," especially when talking about
  installing one (see §5.6, package managers).
- **Framework** — a larger, more opinionated piece of reusable software
  that doesn't just provide tools *your* code calls, but actually
  structures the whole application and calls *your* code at the points
  it needs to (sometimes summarized as "a library, you call; a framework
  calls you"). Django (for Python web apps) is a well-known example. None
  of this project's scripts use a framework — they're small enough that a
  handful of standard-library modules are all that's needed.

---

## Part 4 — JSON: Pretty-Printed vs. JSON Lines

This project's dataset ([gh-archive-guide.md](gh-archive-guide.md)) is
delivered as JSON Lines specifically, which makes this comparison directly
relevant, not just theoretical.

### 4.1 What is JSON, again, briefly

**JSON** (JavaScript Object Notation) is a lightweight, text-based format
for representing structured data — objects (like Python dicts, using
`{ "key": value }`), arrays/lists (`[value, value]`), strings, numbers,
booleans (`true`/`false`), and `null` — that both humans and machines can
read reasonably easily. Despite the name, it's now used by virtually every
programming language, not just JavaScript, as a universal way to exchange
structured data between programs, files, and over the internet.

### 4.2 Pretty-printed JSON

**Pretty-printed** (or "formatted"/"indented") JSON is JSON text that's
been laid out for human readability: each key gets its own line, nested
objects are indented further than their parent, and there's consistent
spacing. Example — one single event, pretty-printed:

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

This is exactly how the "Anatomy of one event" example in
[gh-archive-guide.md](gh-archive-guide.md) is shown — deliberately, since
that section's whole purpose is for a human to read and understand the
shape of one event. The whitespace (line breaks, indentation) carries
*zero* meaning to a program parsing this — `json.loads()` (see
`peek_data.py`'s annotated copy) parses pretty-printed JSON and
single-line JSON into the exact same Python dict either way. Pretty-
printing exists purely for humans, not for the parser.

### 4.3 JSON Lines (JSONL / NDJSON)

**JSON Lines** (sometimes called **JSONL** or **NDJSON**, for
"Newline-Delimited JSON") is a different *file-level* convention: instead
of one big, possibly-pretty-printed JSON structure spanning the whole
file, the file contains many *separate, independent* JSON objects, each
one written entirely on its own single line, with no commas or enclosing
`[ ]` brackets joining them together. This is exactly the format GH
Archive's hourly dumps use — see the compact, single-line style of the
raw file if you look at `data/2026-08-27-15.json` directly, versus the
deliberately pretty-printed illustrative example above.

### 4.4 Side-by-side: the same three events, both ways

**Pretty-printed JSON, as one array (NOT how GH Archive stores it):**

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

**The same three events as JSON Lines (this IS how GH Archive stores
them):**

```
{"type": "PushEvent", "actor": {"login": "alice"}, "repo": {"name": "alice/project"}}
{"type": "WatchEvent", "actor": {"login": "bob"}, "repo": {"name": "alice/project"}}
{"type": "ForkEvent", "actor": {"login": "carol"}, "repo": {"name": "alice/project"}}
```

### 4.5 Why JSON Lines is the right choice for a dataset like this one

This isn't an arbitrary style choice — JSON Lines has real, practical
advantages for exactly the kind of data GH Archive publishes:

1. **Streamable, one record at a time.** A single pretty-printed JSON
   array containing 69,429 events is, technically, *one* JSON value —
   many parsers need to read the *entire* file into memory before they
   can give you even the first event out of it, because they need to find
   the matching closing `]` to know the structure is even valid. JSON
   Lines can be read and processed one line — one event — at a time,
   which is exactly what every script in this project does (`for line in
   f:` in `peek_data.py`, `summarize_data.py`, and `profile_schema.py`),
   without ever needing the whole 47+ MB file in memory simultaneously.
2. **Naturally appendable.** A new event can be added to a JSON Lines
   file just by writing one more line at the end — no need to find and
   rewrite a closing bracket, or worry about a missing/extra comma
   between array elements, both real risks when appending to a
   pretty-printed JSON array.
3. **A single bad line doesn't break the whole file.** If one line is
   corrupted, every other line is still independently parseable; a
   single syntax error in a giant pretty-printed JSON array can make the
   *entire* file unparseable, since it's all technically one JSON value.
4. **Smaller file size.** No indentation whitespace to store for millions
   of records — this matters at GH Archive's scale (every hour, every
   day, forever).

The trade-off is exactly the flip side of §4.2: a raw JSON Lines file is
noticeably harder for a *human* to read directly by eye than a
pretty-printed version, since everything is crammed onto single, often
very long lines — which is precisely why `peek_data.py` and this guide's
"Anatomy of one event" section exist: to show a human-friendly,
pretty-printed *view* of what's structurally the same data.

---

## Part 5 — More Fundamental Concepts Worth Knowing

A grab-bag of further concepts that come up constantly once you're working
with any of the tools above, grouped loosely by theme.

### 5.1 Source code, program, script, and application

- **Source code** — the human-written/readable text of a program, before
  any compiling/interpreting happens.
- **Program** — the general term for a set of instructions a computer
  executes.
- **Script** — usually refers to a smaller, often single-purpose program,
  typically run via an interpreted language, meant to automate a task
  (exactly what this project's four `scripts/*.py` files are).
- **Application** (or "app") — usually implies something larger, more
  full-featured, and often with a user interface, meant for repeated,
  general use (VS Code itself is an application; `peek_data.py` is a
  script).

### 5.2 CLI vs. GUI

- **CLI (Command-Line Interface)** — you interact with software by typing
  text commands into a terminal and reading text output (e.g. running
  `python scripts/peek_data.py`, or using `git` commands).
- **GUI (Graphical User Interface)** — you interact with software visually,
  via windows, buttons, and a mouse/touch (e.g. VS Code's editor window
  itself, or clicking around a website).
Many tools, including this project's own toolchain, offer both: you can
use `git` entirely from the command line, or through VS Code's built-in,
graphical git panel; Claude Code itself is usable as a pure CLI tool *or*
through the VS Code extension's GUI panel (§2.4) — same underlying agent,
two different interfaces onto it.

### 5.3 Terminal, shell, and command line

- **Terminal** — the window/program that lets you type text commands and
  see text output (this project uses Git Bash on Windows, per the
  environment notes you'll have seen).
- **Shell** — the actual program *inside* the terminal that reads the
  commands you type, interprets them, and runs them (e.g. `bash`, or
  Windows' `cmd`/PowerShell). "Terminal" and "shell" are often used
  interchangeably in casual conversation, but strictly, the terminal is
  the window/interface, and the shell is the program running inside it
  doing the actual interpreting.
- **Command line** — the general term for interacting with a shell by
  typing individual commands (like `python scripts/peek_data.py` or
  `git status`).

### 5.4 Repository, working directory, and file system basics

- **Repository ("repo")** — as covered in
  [gh-archive-guide.md](gh-archive-guide.md) in the GitHub sense, and used
  throughout [project-notes.md](project-notes.md) in the git sense: a
  folder that git is tracking the history of (this whole `Research`
  folder is one).
- **Working directory** (or "current directory") — whichever folder a
  terminal or program is currently "standing in," which matters because
  many commands (like `python scripts/peek_data.py`, run as a *relative*
  path) only work correctly if run from the right working directory — see
  the explanation already in [project-notes.md](project-notes.md)'s
  Testing Phase section.
- **Path** — the address of a file or folder in the file system, either
  **absolute** (the full route from the very top, e.g.
  `C:\dev\Research\scripts\peek_data.py`) or **relative** (the route from
  wherever you currently are, e.g. just `scripts/peek_data.py` when
  standing in `C:\dev\Research`). This project's scripts use Python's
  `pathlib.Path` (see the annotated `download_gharchive.py`) specifically
  to handle both kinds correctly and portably across operating systems.

### 5.5 Data structures used constantly in this project

- **String (`str`)** — text.
- **Integer (`int`)** / **Float** — whole numbers / decimal numbers.
- **Boolean (`bool`)** — `True` or `False`.
- **List / array** — an ordered collection of values (Python calls this a
  `list`; JSON calls the equivalent an *array*, written `[ ]`).
- **Dictionary / map / hash map / object** — a collection of `key: value`
  pairs, letting you look a value up by its key instead of its position
  (Python calls this a `dict`; JSON calls the equivalent an *object*,
  written `{ }`). This project's events are, once parsed, exactly this:
  Python dicts, looked up by key (`event["type"]`, `event["actor"]
  ["login"]`).
- **`None` / `null`** — the explicit absence of a value (Python spells it
  `None`; JSON spells the same concept `null` — you've seen this directly
  in this project's own `profile_schema.py` output, e.g.
  `payload.description ... types: str x657, NoneType x633`).

### 5.6 Package managers and virtual environments

- **Package manager** — a tool that automates finding, downloading, and
  installing libraries other people have published (and their own
  dependencies, recursively), instead of you doing it by hand. Python's
  standard one is **pip**; it downloads packages from a public index
  called **PyPI** (the Python Package Index). This project hasn't needed
  pip yet, since every import used so far (`argparse`, `json`,
  `collections`, `pathlib`) is part of Python's built-in standard library
  — no installation required.
- **Virtual environment** — an isolated, self-contained copy of a Python
  installation and its installed packages, kept separate per-project, so
  that Project A needing version 1 of some library and Project B needing
  version 2 of the same library don't conflict with each other on the
  same computer. Worth knowing about even though this project hasn't
  needed one yet (again, precisely because it's only used the standard
  library so far) — it becomes necessary the moment a project needs its
  first *external* package.

### 5.7 API, HTTP, and URLs

- **API (Application Programming Interface)** — broadly, any defined way
  for one piece of software to talk to another. This is a general term —
  Python's `json` module has an API (the functions/behavior it exposes
  for other code to call); Claude also has an API (§1.4).
- **Web API / HTTP API** — the specific, extremely common case of an API
  accessed over the internet using **HTTP** (HyperText Transfer Protocol —
  the same underlying protocol web browsers use to load web pages),
  identified by a **URL** (the web address). This project's
  `download_gharchive.py` is a concrete example: it makes an HTTP request
  to `https://data.gharchive.org/2026-08-27-15.json.gz` — the exact same
  kind of request a browser makes when you visit a page, just made by a
  Python script instead of by clicking a link.

### 5.8 Open source vs. proprietary software

- **Open source** — the software's source code is publicly available for
  anyone to read, modify, and often redistribute, usually under a
  specific license (this project itself uses the **MIT License**,
  recorded in [LICENSE](../LICENSE) — one of the most permissive, common
  open-source licenses). Python itself, VS Code's core, and much of what
  this project depends on are open source.
- **Proprietary software** — the source code is kept private by whoever
  owns it; you can typically only use the finished, compiled program, not
  see or modify how it works internally.
These aren't strictly opposites in practice — e.g. VS Code's core editor
is open source, but the official Microsoft-built version also bundles
some proprietary telemetry/branding on top of that open-source core.

### 5.9 Syntax vs. semantics

- **Syntax** — the grammatical *rules* of how code must be written to be
  valid at all (e.g. Python requires a colon `:` before an indented
  block, as in `def peek(file_path: Path, num_lines: int) -> None:`). A
  syntax error means the code isn't even structured in a way the language
  can parse, regardless of what it was trying to do.
- **Semantics** — the actual *meaning*/behavior of correctly-written code.
  Code can be perfectly valid syntax and still do the wrong thing (a
  "logic error" or "semantic error") — e.g. accidentally counting
  `event["repo"]["name"]` when you meant to count `event["actor"]
  ["login"]` would run without crashing, but produce a wrong answer.

### 5.10 A note on the word "token" (to avoid confusing two unrelated meanings)

This word gets reused for two genuinely different concepts, both relevant
to this project:

- The **LLM token** described in §1.3 — a chunk of text (part of how
  Claude reads and generates language).
- An **access token** / **API token** / **credential** — a secret string
  used to prove *who you are* to a service (e.g. what actually
  authenticates a `git push` to GitHub, or a call to Claude's API). These
  are sensitive and must never be committed to a git repository or shared
  — notably different from the LLM sense above, despite the shared name.
