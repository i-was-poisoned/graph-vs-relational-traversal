# Project Notes: Graph vs. Relational Databases

## Topic

This project investigates a practical question: **at what traversal depth, and at
what data volume, does a property graph model outperform an equivalent normalized
relational model for the same query?**

Relational databases (e.g. PostgreSQL, MySQL) store data in tables and express
relationships through foreign keys. Querying a relationship means performing a
`JOIN`, and the database engine has to compute that join at query time — matching
rows across tables based on key equality. For a single relationship (e.g. "find a
user's orders"), this is fast and well-optimized by decades of relational query
planning. The problem shows up with **multi-hop relationship queries** — e.g. "find
friends-of-friends-of-friends who follow a person that liked a post I liked." Each
additional hop means another `JOIN`, and each `JOIN` multiplies the rows the engine
has to scan and match, so cost tends to grow rapidly with traversal depth.

Graph databases (e.g. Neo4j, ArangoDB) store relationships as first-class,
pre-materialized pointers between nodes ("index-free adjacency"). Traversing a
relationship means following a direct pointer rather than recomputing a join, so
query cost for a multi-hop traversal tends to scale with the size of the
*traversed subgraph*, not the size of the entire dataset. This is the theoretical
basis for the claim that graph databases "win" on deep, relationship-heavy queries,
while relational databases tend to win (or tie) on shallow queries, aggregations,
and workloads that are naturally tabular.

The open, project-specific question is *where the crossover point actually is* —
at what join depth and what data volume does the relational approach's cost start
exceeding the graph approach's cost, for a like-for-like schema and query. That
crossover point, rather than a general "graphs are better" claim, is what this
project aims to measure empirically.

## Resources in Use

- **Claude AI** — used as a research and writing assistant: exploring the
  literature and concepts around graph vs. relational performance, drafting and
  reviewing code, and helping structure documentation.
- **GitHub** — remote hosting for the project repository. Provides version
  history, backup, and (later) a place to collaborate or share the work.
- **VS Code** — the local code editor used for writing and running the project's
  code and managing the git repository day to day.
- **Overleaf** — used for writing up the project in LaTeX (e.g. a report or
  paper), separate from the code repository.
- **GH Archive** — the dataset source. Publishes hourly dumps of every public
  GitHub event as gzip-compressed JSON Lines files, with naturally
  graph-shaped relationships (actor → repo → event). The specific date/hour
  this project uses is recorded in the [README](../README.md) (kept there,
  not here, since it's reproducibility-critical project config rather than a
  learning note). See [gh-archive-guide.md](gh-archive-guide.md) for a full
  explanation of what GH Archive is and how it works.

For a thorough, from-first-principles explanation of what AI/Claude/an
"agent" actually are, what an IDE/VS Code/an "extension" are, what Python
is and how it compares to other languages, and JSON pretty-printing vs.
JSON Lines, see
[tools-and-concepts-guide.md](tools-and-concepts-guide.md).

## Why `.gitignore` and `README.md` Matter

### `README.md`: the project's front door

A `README.md` file is, at its core, just a plain-text document with
formatting — and the `.md` is the key to understanding what that actually
means. `.md` stands for **Markdown**: a lightweight markup language (not a
programming language) that lets you write formatted text — headings,
**bold**, *italics*, lists, links, code blocks — using nothing but plain
keyboard symbols (`#` for a heading, `**...**` for bold, `` `...` `` for
inline code) instead of needing a visual, Word-style editor. You write
plain text with those symbols scattered through it, and any program that
"understands" Markdown (GitHub, VS Code, this very document) renders it as
nicely formatted text. Every `.md` file in this project (this
`project-notes.md`, `README.md`, `gh-archive-guide.md`) is written in
Markdown for exactly that reason: it's readable even as raw, unrendered
text, and it renders cleanly anywhere that understands it.

`README` (capitalized, with no extension, or as `.md`/`.txt`) is also a
very old **convention** in software: by tradition, it's the first file
anyone new to a project is expected to read. GitHub (and GitLab,
Bitbucket, and virtually every other repository host) builds on that
convention automatically: if a repository has a file literally named
`README.md` (or `README`, `README.txt`, etc.) at its root, the platform
detects it and displays it already rendered, right below the file
listing, on the repository's main page. This isn't some special behavior
built into git itself — git gives no special treatment whatsoever to any
file named `README`; it's purely a behavior GitHub (and similar
platforms) layer on top of git, based on that conventional filename.
That's exactly why a well-written `README.md` is so valuable: it's
literally the first thing anyone (including your own future self, six
months from now with no fresh memory of the project) sees on visiting the
repository, so it should immediately answer "what is this, why does it
exist, and what question is it trying to answer?" — which is precisely
what this project's `README.md` does by leading with its research
question.

### `.gitignore`: what "tracking" even means in git, and why you have to tell it what to skip

Understanding `.gitignore` requires first understanding that git doesn't
automatically treat every file in your folder as "part of the project."
While you work in a repository, every file sits in one of these states:

- **Untracked** — git sees the file exists in the folder, but has never
  been told to watch it; it isn't part of the project's history, and
  `git status` flags it as "new."
- **Staged** — running `git add` tells git "I want this file, in its
  current state, to be part of the next commit."
- **Committed** — running `git commit` locks that staged state
  permanently into the repository's history.

Without a `.gitignore`, every new file that shows up in the folder —
including ones Python generates on its own, like `__pycache__/` caches,
or downloaded data in `data/` — would show up as "untracked" in `git
status`, and a careless `git add .` would sweep it into the next commit
without you noticing. `.gitignore` is, literally, a list of file/folder
name patterns that tells git "don't even show me these as 'untracked';
ignore them entirely." It uses wildcard-style patterns — for example, in
this project's own `.gitignore`:

- `/data/` — ignores the entire `data/` folder (the leading slash pins it
  to the project root, not any `data/` folder at any nesting level).
- `__pycache__/` — ignores any folder with that exact name, anywhere in
  the project (no leading slash, so it applies at every level).
- `*.py[codz]` — `*` is a wildcard meaning "any text here"; this ignores
  files like `something.pyc`, `something.pyo`, and so on.
- Lines starting with `#` are comments, for humans only — git skips them
  entirely when reading the file.

Why bother excluding these rather than just never running `git add` on
them by hand each time? Because without `.gitignore`, these
**regenerable** or **machine-specific** files (build caches, virtual
environments, credentials, OS- or editor-specific configuration) would
clutter commit history, bloat the repository's size with content that's
useless to anyone else, and — the more serious risk — could accidentally
leak your own machine's file paths or, worse, secrets like passwords or
API keys if one ever ends up in a file that gets committed by mistake.
`.gitignore` automates that discipline once, instead of relying on a
human never forgetting to make that mistake.

### Compilation: from source code to machine code

Understanding why so many lines in this project's `.gitignore` are about
"build artifacts" first requires understanding what **compiling** actually
is.

A computer's processor (the CPU) doesn't understand Python, or C, or any
other programming language the way a human writes it — it only
understands a very narrow, very specific set of binary instructions
(sequences of ones and zeros) called **machine code**, specific to each
processor architecture. The human-readable **source code** we write
(with meaningful variable names, comments, structure) exists purely so
humans can read and reason about it; the computer, as-is, can't run it
directly.

A **compiler** is a program whose sole job is translating source code,
written in a high-level language, into machine code (or some other
intermediate representation) before the program ever runs. That
translation process is called **compiling** (or "building"), and the
result — the already-translated file or files — is what's generally
called a **build artifact** (see the next section). In compiled languages
like C or Rust, this step happens explicitly, once, before the program
is ever run; the result is a standalone executable file.

Python, as covered in more depth in
[tools-and-concepts-guide.md](tools-and-concepts-guide.md#33-compiled-vs-interpreted-languages),
is an **interpreted** language — you don't manually compile this
project's scripts before running them; they run directly via `python
scripts/peek_data.py`. But behind the scenes, Python's own interpreter
still compiles each `.py` file into an intermediate form called
**bytecode** (simpler instructions than the original Python code, though
still not raw machine code) the first time it's imported or run, and
caches that bytecode in `.pyc` files inside a `__pycache__/` folder, so
it doesn't have to redo that translation work on every future run if the
source file hasn't changed. Those `.pyc` files are exactly a build
artifact — just one Python generates automatically, in the background,
rather than through a manual build step.

### What is a "build artifact"?

A **build artifact** (or just "artifact," or "build output") is any file
that's **generated** from source code by some automated process —
compiling, packaging, minifying, rendering — rather than being written by
hand by a person. The key distinction for this project:

- **Source code** (the `.py` files in `scripts/`, the `.md` files in
  `docs_*/`) is the **single source of truth** — what a person actually
  wrote, and the only thing that genuinely needs to live in the project's
  history.
- An **artifact** is *derived* from that source code — it can always be
  regenerated by running the same process against the same source code
  again, which makes committing it to git redundant at best, and actively
  harmful at worst.

Examples of build artifacts beyond Python's `.pyc` files already
mentioned (to make the concept fully general, not tied only to this
project): a `.exe` or `.dll` compiled from C/C++ source; a `.jar`
compiled from Java source; the final, minified, "bundled" HTML/CSS/
JavaScript a modern web app's build tool produces from its source code; a
`.whl` (wheel) file packaging a ready-to-install Python library; even
HTML documentation auto-generated from comments in source code.

Why build artifacts are almost never committed to a git repository (and
why this project's own `.gitignore` excludes so many of them —
`__pycache__/`, `*.py[codz]`, `build/`, `dist/`, `*.egg-info/`, among
others):

1. **They're regenerable.** If the source code is in the repository,
   anyone can regenerate the exact same artifact at any time — storing it
   too would just be duplicating information for no benefit.
2. **They're often environment-specific.** A `.pyc` compiled against the
   Python version installed on this machine (Python 3.14, per the
   `__pycache__/` paths seen in this project) might not work the same
   way, or might not even load at all, on someone else's machine running
   a different Python version.
3. **They clutter history and diffs.** Artifacts are usually binary files
   (not line-by-line-readable text), so git can't show a useful
   line-by-line diff for them the way it can for source code — every
   change just shows up as "the whole file changed," with no information
   about what actually changed.
4. **They bloat repository size** with content that adds nothing to
   understanding the project — nobody needs to read a `.pyc` to
   understand what `peek_data.py` does; the `.py` file already tells
   them.

(One caveat worth knowing, for completeness: there are deliberate
exceptions to this general rule — for instance, when a project
*publishes* a finished artifact, like attaching a compiled executable to
a GitHub "Release" so people can download it directly without compiling
the source themselves. That's different from committing the artifact
into the repository's *commit history*, which is what `.gitignore` is
preventing here.)

## Repository Workflow So Far

1. Created the repository on GitHub first (remote).
2. Cloned it locally with `git clone` into `C:\dev\Research` — deliberately
   **outside** any OneDrive-synced folder (e.g. avoiding a path containing
   `OneDrive - Pedro`), since OneDrive syncing the same folder git is managing can
   cause file-locking conflicts, hit Windows' path length limits, and slow down
   both git and OneDrive. GitHub (remote) and OneDrive (local sync) are unrelated
   systems, but both would be fighting over the same local files if the repo
   lived inside a OneDrive folder.
3. At this stage, code is being written and committed locally; pushing to the
   GitHub remote is deferred until later.

## Testing Phase

First, let's go to the project root and start looking at the dataset for the
specific hour by running:

```bash
python scripts/download_gharchive.py
```

Important points before running this:

- **You must be inside the project root** (`C:\dev\Research`) when you run
  this command. It's run as `scripts/download_gharchive.py` (a relative path),
  so the shell needs to be sitting in the folder that contains the `scripts/`
  directory — otherwise it won't find the file.
- **Python needs to be on your PATH.** This means your system knows where the
  `python` program lives so it can be run by name from any terminal, instead
  of needing the full install path typed out every time. If running `python
  scripts/download_gharchive.py` gives a "command not found" style error, try
  `python3` instead — some installs only register that name. (This is
  different from the `PYTHONPATH` environment variable, which is about where
  Python looks for importable modules, not about finding the `python`
  executable itself — not something this script needs.)
- The script creates a `data/` folder automatically on first run — no need to
  create it yourself. It's excluded from git via `.gitignore` since it's raw,
  regenerable data, not project code.
- A successful run prints progress for the download and decompression, ending
  with a line like `Done: data/2026-08-27-15.json` — that file is the
  decompressed dataset, ready to be read line by line (see
  [gh-archive-guide.md](gh-archive-guide.md), section 8).

Note: the first run hit an `HTTP Error 403: Forbidden` from GH Archive's
server, caused by `urllib`'s default `User-Agent` header looking like a
script rather than a browser. Fixed by building the request manually with a
browser-like `User-Agent` header instead of using `urlretrieve` directly (see
the script for the fix and [download_gharchive.py](download_gharchive.py),
the annotated copy, for the full explanation).

## Version Control Workflow (git add → commit → push)

With the download/peek scripts and docs in place, the next routine step was
committing and pushing this work to GitHub. The commands used, in order:

```bash
git add .
git commit -m "Exploration stage set up"
git push
```

This first push failed with an HTTP 403, because Windows' cached GitHub
login belonged to a different account (a work account) than the one that
owns this repo. Fixed by repointing the remote at the correct account
without touching the cached work credential:

```bash
git remote -v
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
git push -u origin main
```

See [git-commands-guide.md](git-commands-guide.md) for a full explanation of
what each of these commands actually does, the staging-area concept behind
`add`/`commit`, and why the account mix-up happened.

## Exploration Stage (download_gharchive.py --> peek_data.py)

Now that we have a dataset downloaded and decompressed into JSON Lines format
(`data/2026-08-27-15.json`), the next step is to actually look at what's in
it, before trying to model it relationally or as a graph.

`scripts/peek_data.py` ([annotated copy](peek_data.py)) reads the first few events from the file and prints
their key fields (`type`, `actor`, `repo`, `created_at`) — a quick sanity
check that the data looks like what [gh-archive-guide.md](gh-archive-guide.md)
described, before writing any real parsing/loading logic against it.

Run it with:

```bash
python scripts/peek_data.py
```

This prints the first 5 events by default. Useful variations:

```bash
# Print more events
python scripts/peek_data.py --lines 20

# Point at a different downloaded file
python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
```

## Summary Stage (summarize_data.py)

With the shape of a single event confirmed by `peek_data.py`, the next step
is to get a sense of *volume and connectivity* across the whole downloaded
hour, before picking a schema: how many events, how they break down by
type, and how many distinct actors/repos are involved.

`scripts/summarize_data.py` ([annotated copy](summarize_data.py)) reads the full JSON Lines file once and prints three sections:

1. **General:** total events, unique actors and unique repos, each split
   into bots and non-bots (including how many repos *only* bots made
   events in).
2. **Analysis with bots:** every event.
3. **Analysis without bots:** the same analysis, with every account whose
   login ends in `[bot]` removed.

Sections 2 and 3 show exactly the same things, so they can be compared
side by side:

- event type breakdown (count and percentage, most common first)
- the top N most active actors and repos by event count
- connectivity: how many repos have 2+ different actors, how many actors
  made events in 2+ repos, and how many actors share a repo with at least
  one other actor
- the top N actors by number of *different* repos they made events in, and
  the top N repos by number of *different* actors who made events in them

Run it with:

```bash
python scripts/summarize_data.py

# Show more top actors/repos
python scripts/summarize_data.py --top 10
```

For the fixed 2026-08-27 15:00 UTC hour, this showed 69,429 events across
14,728 unique actors and 16,497 unique repos, with `PushEvent` alone
accounting for 95.3% of all events. The most active actors are all bots
(`github-actions[bot]`, `dependabot[bot]`, `pull[bot]`, `renovate[bot]`,
`cursor[bot]`) — worth deciding on a bot-filtering policy before this data
is used to build the relational/graph models, since bot-driven `PushEvent`s
would otherwise dominate the connectivity being measured.

**Unique vs. total — how to read these numbers.** "Unique actors" and
"total events" answer different questions. If `ana` makes 3 events and
`luis` makes 2, there are 5 events but only 2 unique actors. The script
keeps a `Counter` per thing it tallies — a dictionary of *name → number of
events* — and `len()` of that dictionary gives the number of *distinct*
names, while adding up all its values would just give the total event
count again (the [annotated copy](summarize_data.py) walks through this
with a worked example). The distinction matters for this project because
the unique actors and unique repos are what become the **nodes** of the
graph (and the rows of the Actor and Repo tables) — roughly 14.7k + 16.5k
≈ 31k nodes for this hour — while the events are what *connect* them. On
average each actor produced about 4.7 events (69,429 ÷ 14,728), but that
average hides a very uneven spread, with bots at the top of the list,
which is why the bot-filtering decision above directly affects how
connected the graph will be.

### Connectivity findings: with and without bots

Counting events and unique names isn't enough to know whether the data
supports the benchmark. The benchmark walks `actor → repo → actor → repo`,
and each step from a repo to *another* actor only works if that repo was
touched by at least two different actors. So `summarize_data.py` also
measures connectivity, once with every event and once without the
accounts whose login ends in `[bot]`:

| Metric | All events | Without bots |
|---|---|---|
| Events | 69,429 | 67,459 (1,970 bot events removed, 2.8%) |
| Unique actors | 14,728 | 14,515 (213 bot actors removed, 1.4%) |
| Unique repos | 16,497 | 14,995 (1,502 repos that only bots made events in removed, 9.1%) |
| Repos with 2+ distinct actors | 145 (0.9% of repos) | 49 (0.3%) |
| Actors who touched 2+ repos | 256 (1.7% of actors) | 211 (1.5%) |
| Actors sharing a repo with another actor | 234 (1.6% of actors) | 101 (0.7%) |

**Conclusions:**

1. **Pushes dominate.** `PushEvent` is 95.3% of all events (96.3% without
   bots). The event types that *could* link two people directly
   (comments, reviews, issues) add up to around 1%, and only 0.26% of
   events actually name a second, different person. Connections between actors will
   come almost entirely from *shared repos*, which matches what
   `profile_schema.py` found (see the Schema Design Stage below).
2. **More repos than actors means some actors touch several repos.** If
   every actor had touched only one repo, there could be at most as many
   repos as actors. There are more repos (16,497 vs. 14,728), so some
   actors must have worked on several — but only 1.7% of them did.
3. **The graph is extremely fragmented.** 99% of repos were touched by a
   single actor, and about 98% of actors share no repo with anyone else.
   The typical event is one person pushing to their own repo. The most
   "shared" repo has 12 distinct actors with bots, and only 4 without.
   For a traversal benchmark this is the key finding: most walks would
   stop after the first hop.
4. **Bots are small in volume but large in connectivity.** Bots are only
   2.8% of events, but `github-actions[bot]` alone touches 785 different
   repos. Removing bots removes about two-thirds of the shared repos
   (145 → 49) and more than half of the connected actors (234 → 101), so
   most of the connections in this hour come from bots. They act as artificial hubs,
   linking repos that have nothing to do with each other. A benchmark
   run on this data would mostly measure "everything connects through
   github-actions", so bots should be excluded from the benchmark data.
5. **The `[bot]` filter isn't complete.** Some automated accounts don't
   use the suffix: `Copilot` touches 41 repos. And with bots removed, the
   most active accounts have generated-looking names (`beckjulie09`,
   `hayeshenry6`, ...), each pushing 35–39 times to its own repo with a
   random-looking name (`hpmxym`, `eznfko`, ...), probably automated or
   spam accounts. They don't add connections (each one only touches its
   own repo), but they do inflate the event volume.

**What this means for the project:**

- **One hour of data is not enough for a multi-hop benchmark.** With only
  about 100 connected actors once bots are removed, a 3- or 4-hop walk
  has almost nowhere to go. The next step is to download more hours
  (e.g. a full day, or several days) and re-run `summarize_data.py` to see
  whether the number of shared repos grows. The research question asks
  about data *volume* too, so several dataset sizes are needed anyway.
- **Bot policy:** exclude `[bot]` accounts from the benchmark data, and
  consider an explicit exclusion list for known automated accounts
  without the suffix (such as `Copilot`).
- **Check connectivity before every benchmark.** Re-run these metrics on
  each dataset size before timing any query, so the benchmark is never run
  on a graph where there is nothing to traverse.

## What "benchmark" means, for this project

Before going further, it's worth being precise about a word this project
uses constantly. A **benchmark** is a fair, repeatable, *timed* test used to
compare two or more things under the same conditions — not just "run it
once and see," but deliberately controlling everything except the one
thing being measured, so the result is a genuine comparison rather than a
fluke caused by, say, the laptop doing something else in the background
during one of the two runs.

For this project specifically: a benchmark run means taking the *same*
multi-hop query (e.g. "starting from actor X, find all repos reachable
within 3 hops") and running it against the relational database and the
graph database, on the *same* underlying data, timing how long each takes.
That gets repeated across different hop-depths and data volumes to find
the crossover point the README asks about.

## Schema Design Principle: Query-First, Not Field-First

**Where this section comes from.** Up to this point, every stage has been
about *getting to know the data*: what a single event contains
(`peek_data.py`), and how many events, actors and repos there are and how
they connect (`summarize_data.py`). The project's next step is *designing
the schemas*: the tables of the relational database and the nodes and
edges of the graph database. Before drawing a single table, you have to
decide **by what rule** they will be designed, and this section sets that
rule.

It follows directly from the previous section on what a benchmark is: a
fair test where everything is controlled except the thing being measured.
The schema is part of the "everything else" that has to be controlled. If
the two schemas aren't equivalent, the benchmark no longer compares a
relational model with a graph model — it compares two different designs.

**Two key terms**

- **Schema:** the "shape" of the data inside the database. Relational:
  which tables, which columns, which keys. Graph: which node types, which
  edge types, and which properties.
- **Query:** the specific question asked of the database, and whose time
  is measured. For example: "starting from actor X, which repos can be
  reached in 3 hops?".

**Two ways to design a schema**

| | Field-first | Query-first |
|---|---|---|
| Where you start | Looking at GH Archive's JSON | Writing the benchmark query |
| What you ask | "Which fields exist?" | "What does this query need in order to work?" |
| Result | Dozens of tables or node types (commits, messages, PRs, comments, labels...), most never queried | Only the minimum: Actor, Repo, and the connection between them |

Field-first is tempting because it feels more complete: GH Archive offers
commit messages, PR titles, review text, issue labels... and it seems
that the more you model, the better. But the traversal benchmark never
reads any of that. All that detail would be built, loaded and maintained
without affecting the measurement — or worse, affecting it in ways you
don't want (see below).

**Example from this project.** The benchmark query is an
`actor → repo → actor → repo` walk. To answer it you only need to know
three things: who each actor is, what each repo is, and which actor made
events in which repo. So the minimal schema is the same on both sides:

| Concept | Relational | Graph |
|---|---|---|
| Actor | table `actor` (id, login) | node `Actor` (id, login) |
| Repo | table `repo` (id, name) | node `Repo` (id, name) |
| Connection | table `actor_repo` (actor_id, repo_id) | edge `Actor → Repo` |

Why does the walk have to go through repos instead of going straight from
one actor to another? Because the data almost never connects two people
directly. `PushEvent` (95.3% of events) names no second actor at all (see
the Schema Design Stage below), and the connectivity measured by
`summarize_data.py` shows that connections between actors come from
*shared repos*.

**Why following this principle matters**

1. **You measure what you mean to measure.** A query's time depends on how
   much data the database has to read. If every row carries columns the
   query doesn't use (long commit messages, for example), the database
   reads more data from disk, and the measured time includes that noise on
   top of the real cost of the traversal.
2. **The comparison is fair.** If one side has more detail than the other,
   the result reflects the difference in design, not the difference
   between models. For example: if the relational side stores one row per
   event (69,429 rows) and the graph side stores one edge per actor–repo
   pair (far fewer), the graph "wins" because it holds less data, not
   because it traverses better. That would answer the research question
   wrongly.
3. **You can prove the two sides are equivalent.** With a small schema
   it's easy to check that both databases hold exactly the same thing: the
   same number of actors, repos and connections. With dozens of tables,
   that check becomes hard.
4. **Less work and fewer mistakes.** Fewer tables means less loading code,
   faster loads, and fewer places to get something wrong. The time saved
   can go to what matters: repeating the measurements at different data
   sizes.
5. **It's reproducible and easy to explain.** In the final write-up, the
   schema fits in three lines, and anyone can rebuild it and repeat the
   experiment.

**Concrete rules to follow**

1. **Write the benchmark query (or queries) first**, in words, before
   creating any table or node.
2. **List the data that query reads.** Only that goes into the schema. If
   a field doesn't appear in the query, it stays out.
3. **Build the same model on both sides**, as in the table above: the same
   entities and the same connection.
4. **Load both sides from the same source data** (the same files and the
   same bot filter) and check that the counts match before measuring
   anything.
5. **Decide once how the connection is stored** (one per event, or one
   per actor–repo pair) and use that same decision on both sides.
6. **Give each side its normal aids, no more and no less.** On the
   relational side, that means indexes on the columns used to join tables
   (`actor_id`, `repo_id`); the graph already stores connections directly.
   Measuring the relational side without indexes would be comparing
   against a deliberately slow version.
7. **If you add something, add it to both sides at once, or to neither.**
   A new property, an index, or another kind of connection: always on
   both, so the comparison stays equivalent.

## Schema Design Stage (profile_schema.py)

The data is inherently **bipartite**: every event connects one `actor` to
one `repo` (see [gh-archive-guide.md](gh-archive-guide.md#actors-repos-and-events)
for the full actor/repo/event distinction). That means a "multi-hop
traversal" here can't be the classic friends-of-friends example from this
project's opening research question — there's no direct actor-to-actor
edge in the raw data by default. A traversal has to alternate
`actor → repo → actor → repo`, hopping through *shared repos* (or, where
available, through a second actor named inside an event's `payload`).

To design that schema well — following the query-first principle above —
the next step was finding out *where in the data a second actor actually
appears*, since without one, there's nothing to hop to beyond "another repo
this same actor touched." `scripts/profile_schema.py` ([annotated copy](profile_schema.py)) reads the full file
and reports, per event type:

- which `payload` fields exist, how often, and what type they hold
- any nested object shaped like a GitHub user reference (`{"id": ...,
  "login": "..."}`) found anywhere inside `payload`, and the path to it
  (e.g. `payload.pull_request.user`)

Run it with:

```bash
python scripts/profile_schema.py

# Focus on one event type
python scripts/profile_schema.py --type PushEvent
```

### What the output is for

The output of `profile_schema.py` is long and, at first glance, looks like
a list of technical fields. But it answers one very specific question for
this project: **besides the actor who made the event, does the event name
another person?** If the answer were "yes, often", the graph could have
direct person → person connections (e.g. "Ana commented on Luis's issue"),
and the benchmark's walks could use them. If the answer is "almost never",
people only connect through the repos they share, and the schema has to
reflect that.

On top of that, the output is useful for three practical things when
designing the schema:

1. **Knowing what data each event type holds.** Each event type stores
   different things in its `payload`. A `PushEvent` stores the branch and
   the commits; an `IssueCommentEvent` stores the issue and the comment.
2. **Knowing whether a field is reliable.** "present in 100%" means the
   field is always there; a low percentage means it only appears
   sometimes. In a table, that would be an optional column (one that can
   be empty).
3. **Knowing what kind of data it is.** `str` (text), `int` (number),
   `dict` (an object with more fields inside), `list` (a list) or
   `NoneType` (empty). For example, in `CreateEvent` the `description`
   field is empty (`NoneType`) in 633 of 1,290 events: if it were stored,
   it would need a column that allows empty values.

### How to read one block of the output

```
IssueCommentEvent (194 events)
  payload.action               present in 100.0% (194/194) - types: str x194
  payload.issue                present in 100.0% (194/194) - types: dict x194
  payload.comment              present in 100.0% (194/194) - types: dict x194
  actor references (nested 'login' fields):
    payload.issue.user                  present in 100.0% (194/194)
    payload.comment.user                present in 100.0% (194/194)
```

- **First line:** the event type and how many events of that type there
  are (194 comments on issues).
- **`payload.…` lines:** each field of the `payload`, in what percentage
  of those events it appears, and what type of data it holds. Here all
  three fields are always present: `action` is text, and `issue` and
  `comment` are objects with more data inside.
- **`actor references`:** the paths inside the `payload` where there's an
  object shaped like a GitHub user (a dict with `login`), and in what
  percentage of events it appears. `payload.issue.user` is whoever opened
  the issue; `payload.comment.user` is whoever wrote the comment.

### Second check: is it really another person?

There's a catch. `profile_schema.py` only checks that a user **exists** at
that path, not **who** it is. And often it's the actor themself: in an
`IssueCommentEvent`, whoever wrote the comment (`comment.user`) is exactly
the person who made the event. To find out, each user found has to be
compared with the event's `actor`. That comparison, run on this project's
data, gives this:

| Event type and path | Who it is | Is it the actor themself? |
|---|---|---|
| `IssueCommentEvent` `comment.user` | the comment's author | Yes, 100% |
| `IssueCommentEvent` `issue.user` | whoever opened the issue | Only 34%: **66% of the time it's someone else** |
| `IssuesEvent` `issue.user` | whoever opened the issue | 87% (people usually manage their own issues) |
| `PullRequestReviewEvent` `review.user` | the review's author | 99% |
| `PullRequestReviewCommentEvent` `comment.user` | the comment's author | 100% |
| `ReleaseEvent` `release.author` | the release's author | 100% |
| `ForkEvent` `forkee.owner` | owner of the new copy (the fork) | 100%: whoever forks owns the copy |
| `assignee` / `assignees` (several types) | assigned people | Between 30% and 70%, depending on the case |
| `performed_via_github_app.owner` | owner of the app that posted the event | Never, but not a participant either: usually an organisation |

**Result:** of the 69,429 events, only **178 (0.26%)** name a person who
is really different from the actor (not counting app owners), and only
**76** of those come from non-bot actors. Almost all are comments on
someone else's issue (`IssueCommentEvent`, 131) or actions on someone
else's issue (`IssuesEvent`, 35).

**Key finding:** `PushEvent` — 95.3% of all events — names no other person
anywhere in its `payload`: it only has `ref`, `before`/`head` (commit
identifiers) and `repository_id`. `PullRequestEvent`'s
`payload.pull_request` is also a trimmed reference that omits the PR's
author (unlike GitHub's full REST API response). And in the remaining
events, most nested users are the actor themself. An earlier version of
these notes said second-actor references lived in the ~4.7% of events
that aren't `PushEvent`; that was only an upper bound. The real figure,
after comparing with the actor, is **0.26%** (breakdown in
[gh-archive-guide.md](gh-archive-guide.md#where-a-second-actor-appears-nested-references)).

**What this means for the schema:** direct person → person connections
are practically nonexistent in this data. With 76 connections between
people (without bots), no multi-hop walk can be built. That's why the
benchmark schema is **Actor, Repo, and the connection between them**, with
no actor → actor edge: people connect through the repos they share, as
measured by `summarize_data.py`. And a general lesson: a field that
*looks like* another person isn't necessarily one; always check it
against the actor.

The overall pipeline so far is: **download_gharchive.py → peek_data.py →
summarize_data.py → profile_schema.py** — first fetch and decompress the
fixed dataset hour, then inspect a handful of raw events, then get an
aggregate read on volume and connectivity, then profile the payload shape
and locate second-actor references, before moving on to actually
extracting and loading records into the relational and graph models being
compared.
