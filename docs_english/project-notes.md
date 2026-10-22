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

### New concept: recursion (a function that calls itself)

`profile_schema.py` introduces a programming idea that hasn't appeared in
the earlier scripts: **recursion**. Its function `find_actor_refs()` calls
*itself* inside its own body. (This isn't "nesting" a function — nesting
means *defining* one function inside another. Here there's a single
function that *calls* itself.)

**Why it's possible.** Every time a function is called, Python creates a
fresh, separate copy of its parameters and variables for that call. The
new call works with its own values, and the call that started it waits,
paused, until it gets the answer back, then carries on.

**An analogy.** Russian nesting dolls: to find a note hidden somewhere in
a set of dolls, the instructions are the same at every level — *"open the
doll; if the note is here, take it; otherwise, apply these same
instructions to each doll inside."* The instructions refer to themselves.

**Why this script needs it.** An event's `payload` is a dictionary that
can contain dictionaries, which can contain lists of dictionaries, and so
on, and we don't know in advance how many levels there are. A normal
`for` loop only looks at one level. A recursive function handles one
level and then asks *itself* to handle the next, however many there are:

```
payload = {"action": "created", "issue": {"user": {"login": "luis"}}}

find_actor_refs(payload)               -> a dict without "login": look inside
  find_actor_refs("created")           -> plain text: nothing inside -> []
  find_actor_refs({"user": {...}})     -> a dict without "login": look inside
    find_actor_refs({"login": "luis"}) -> a user! -> ["payload.issue.user"]
result: ["payload.issue.user"]
```

**The two rules every recursive function needs:**

1. **A base case:** a situation where it answers *without* calling itself
   (here: it found a user, reached a plain value, or hit the depth limit).
   Without one, it would call itself forever.
2. **Each call must get closer to a base case** (here: each call goes one
   level deeper into the data, and the `depth` counter goes down by 1,
   with `MAX_SEARCH_DEPTH = 3` as the limit).

Recursion is the natural tool whenever the data looks like *boxes inside
boxes*: folders inside folders, JSON inside JSON, and — later in this
project — exploring a graph hop by hop. The
[annotated copy](profile_schema.py) walks through `find_actor_refs()` line
by line, and the next section follows a full example call by call.

### Worked example: a step-by-step walk through `find_actor_refs()`

This example goes through **every** branch of the function: a dictionary
without `login`, a dictionary with `login`, a list, plain values, and the
depth limit. You can read it with the function's code alongside:

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

#### 1. The example data

A `payload` similar to an `IssuesEvent`'s:

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

`profile()` starts everything with a single call:
`find_actor_refs(payload, "payload", 3)`.

#### 2. The rule that creates the next calls

Every new call is **born from the loop of an earlier call**. To understand
how, you first need five basic pieces of Python. Then we put them
together.

##### 2.1 Background knowledge

**a) A dictionary stores *key → value* pairs.**
It's like an address book: you look up by name (the **key**) and get the
information (the **value**). Our `payload` is a dictionary with **two**
keys:

```python
payload = {
    "action": "opened",       # key "action" → value "opened"
    "issue":  {...}           # key "issue"  → value: another dictionary
}

payload["action"]   # → "opened"
payload["issue"]    # → {...} (the issue's dictionary)
```

**b) `.items()` gives you every pair, one after another.**
If you want to go through a whole dictionary, `.items()` gives you each
entry as a **pair** `(key, value)`:

```python
list(payload.items())
# → [("action", "opened"), ("issue", {...})]
#      └─ 1st pair ──┘     └── 2nd pair ──┘
```

**c) `for` takes one pair on each pass and splits it into two variables.**
When you write two names separated by a comma after `for`, Python takes
each pair and puts its first part in the first variable and its second
part in the second:

```python
for key, sub_value in payload.items():
    print(key, "→", sub_value)

# 1st pass:  key = "action"   sub_value = "opened"
# 2nd pass:  key = "issue"    sub_value = {...}
```

`key` and `sub_value` are just names we chose. They change value on each
pass: first they hold the 1st pair, then the 2nd.

**d) When you call a function, each argument goes to its parameter, in
order.**
The function is defined with three parameters:

```python
def find_actor_refs(value, path, depth):
```

So in a call like this one:

```python
find_actor_refs("opened", "payload.action", 2)
#               │         │                 │
#               ▼         ▼                 ▼
#             value     path              depth
```

inside that call, `value` is `"opened"`, `path` is `"payload.action"` and
`depth` is `2`. The **first** value goes to the **first** parameter, the
second to the second, and the third to the third. And each call has **its
own** copies of those variables (see the recursion section).

**e) An f-string builds a piece of text out of variables.**
A string with an `f` in front can contain variables inside curly braces
`{}`, and Python replaces them with their values:

```python
path = "payload"
key = "action"
f"{path}.{key}"     # → "payload" + "." + "action" → "payload.action"
```

The dot in the middle is just an ordinary dot, part of the text. That's
why the result looks like an "address" inside the data: `payload.action`
means "the `action` key inside the `payload`".

##### 2.2 Putting the pieces together

Now, the function's loop line:

```python
for key, sub_value in value.items():
    refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
```

> **Loop, iteration and pass.** A **loop** is the block of code that
> repeats as a whole: the `for ...:` with everything inside it. Each of
> its repetitions is an **iteration**, or, more informally, a **pass**:
> in these notes, "pass" and "iteration" mean the same thing. The verb
> **to iterate** means going through something item by item, which is
> exactly what a loop does. For example, the `issue` has 4 keys, so call
> 3's loop makes **4 iterations** (`number`, `user`, `assignees` and
> `milestone`).

Let's follow it inside **call 1**. When that call starts, its three
parameters hold (piece *d*):

| Parameter | Value in call 1 |
|---|---|
| `value` | the whole `payload` |
| `path` | `"payload"` |
| `depth` | `3` |

`value` is a dictionary with two keys, so `value.items()` gives two pairs
(piece *b*) and the loop makes **two passes** (piece *c*). On each pass,
Python works out the three arguments for the new call:

| | 1st pass | 2nd pass |
|---|---|---|
| `key` (piece *c*) | `"action"` | `"issue"` |
| `sub_value` (piece *c*) | `"opened"` | the `issue` dictionary |
| 1st argument: `sub_value` | `"opened"` | the `issue` dictionary |
| 2nd argument: `f"{path}.{key}"` (piece *e*) | `"payload" + "." + "action"` = `"payload.action"` | `"payload" + "." + "issue"` = `"payload.issue"` |
| 3rd argument: `depth - 1` | `3 - 1` = `2` | `3 - 1` = `2` |
| **Call that's born** | `find_actor_refs("opened", "payload.action", 2)` → **call 2** | `find_actor_refs({...issue...}, "payload.issue", 2)` → **call 3** |

And when call 2 starts, its parameters receive those three values in order
(piece *d*): `value = "opened"`, `path = "payload.action"` and
`depth = 2`. **What were `sub_value`, the built-up text and `depth - 1` in
call 1 become `value`, `path` and `depth` in call 2.**

What `refs.extend(...)` does with each call's answer is explained further
down, in part 6.

##### 2.3 The general rule

The same thing happens in every call of the example:

- **Dictionary →** one call per key. The **value** becomes the new
  `value`, the **key** is added to `path`, and `depth` drops by 1.
- **List →** one call per item. The item becomes the new `value`; since
  there's no key, `path` **doesn't change**, and `depth` drops by 1.
- **User** (dictionary with `login`) **or plain value →** no more calls:
  the function answers directly. These are the **base cases**.

That's why there are so many calls: **every container generates one call
for each thing it holds**.

#### 3. The call tree

```
CALL 1   payload (dict with 2 keys)
├── CALL 2   action    → "opened", text            → []
└── CALL 3   issue     → dict with 4 keys
    ├── CALL 4   number    → 7, a number           → []
    ├── CALL 5   user      → user luis!            → ["payload.issue.user"]
    ├── CALL 6   assignees → list with 2 items
    │   ├── CALL 7   ana    → user!                → ["payload.issue.assignees"]
    │   └── CALL 8   marta  → user!                → ["payload.issue.assignees"]
    └── CALL 9   milestone → dict with 1 key
        └── CALL 10  creator → user pedro!         → ["payload.issue.milestone.creator"]
```

Each branch ends when it reaches a **user** or a **plain value**.

#### 4. Every call, one by one

| Call | Comes from | `value` | `path` | `depth` | What it does | Returns |
|---|---|---|---|---|---|---|
| 1 | `profile()` | the whole `payload` | `"payload"` | 3 | dict without `login` → looks at its 2 keys | 4 paths |
| 2 | call 1, pass 1 (`action`) | `"opened"` | `"payload.action"` | 2 | text, nothing inside | `[]` |
| 3 | call 1, pass 2 (`issue`) | the `issue` | `"payload.issue"` | 2 | dict without `login` → looks at its 4 keys | 4 paths |
| 4 | call 3, pass 1 (`number`) | `7` | `"payload.issue.number"` | 1 | number, nothing inside | `[]` |
| 5 | call 3, pass 2 (`user`) | `{"login": "luis", "id": 1}` | `"payload.issue.user"` | 1 | user! | `["payload.issue.user"]` |
| 6 | call 3, pass 3 (`assignees`) | the list `[ana, marta]` | `"payload.issue.assignees"` | 1 | list → looks at its 2 items | 2 paths |
| 7 | call 6, item 1 | `{"login": "ana"}` | `"payload.issue.assignees"` (same) | 0 | user! | `["payload.issue.assignees"]` |
| 8 | call 6, item 2 | `{"login": "marta"}` | `"payload.issue.assignees"` (same) | 0 | user! | `["payload.issue.assignees"]` |
| 9 | call 3, pass 4 (`milestone`) | `{"creator": {...}}` | `"payload.issue.milestone"` | 1 | dict without `login` → looks at its only key | 1 path |
| 10 | call 9, pass 1 (`creator`) | `{"login": "pedro"}` | `"payload.issue.milestone.creator"` | 0 | user! | `["payload.issue.milestone.creator"]` |

Look at the `depth` column: it drops by 1 at each level (3 → 2 → 1 → 0).
Calls 7, 8 and 10 arrive with `depth = 0`, which is still allowed because
the check is `depth < 0`, and zero isn't less than zero.

#### 5. The order in time: why 6, 7, 8 and then 9

Calls are numbered in the order they **happen**, and Python **finishes a
call completely, with all its "children", before going back to the
previous one**. The outer call stays paused in the meantime:

1. Call 1 launches **call 2** (key `action`). Call 2 returns `[]` straight
   away.
2. Call 1 launches **call 3** (key `issue`) and pauses.
3. Call 3 launches **call 4** (`number`), which returns `[]`, then **call
   5** (`user`), which finds luis.
4. Call 3 launches **call 6** (`assignees`) and pauses.
5. Call 6 launches **call 7** (ana) and then **call 8** (marta). When call
   8 finishes, call 6 has gone through its whole list and **returns** its
   result to call 3.
6. **Only then** does call 3 resume and take its last pass: it launches
   **call 9** (`milestone`), which in turn launches **call 10**
   (`creator`).
7. Call 10 answers call 9, call 9 answers call 3, and call 3, having
   finished its loop, answers call 1.

It's like opening Russian dolls: before moving on to the next doll on the
same level, you fully open the one in your hand and every doll inside it.

#### 6. How the `refs` list fills up

Each call has **its own** `refs` list, and fills it with what its child
calls return, using `refs.extend(...)`. This is how **call 3**'s `refs`
grows:

| After this call answers... | What it returns | Call 3's `refs` |
|---|---|---|
| (at the start) | — | `[]` |
| call 4 | `[]` | `[]` (unchanged) |
| call 5 | `["payload.issue.user"]` | `["payload.issue.user"]` |
| call 6 | `["payload.issue.assignees", "payload.issue.assignees"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees"]` |
| call 9 | `["payload.issue.milestone.creator"]` | `["payload.issue.user", "payload.issue.assignees", "payload.issue.assignees", "payload.issue.milestone.creator"]` |

**When a call finds nothing,** it returns an empty list (`[]`).
`.extend([])` adds to `refs` every item in that list, which is none, so
**there's nothing to add and the list stays as it was**. That happens with
calls 2 and 4. Only the calls that *do* find a user (5, 7, 8 and 10) make
the lists grow.

**Call 1**'s `refs` receives `[]` from call 2 and the 4 paths from call 3,
so the final result is:

```python
['payload.issue.user',
 'payload.issue.assignees',
 'payload.issue.assignees',
 'payload.issue.milestone.creator']
```

#### 7. Two more details

**The depth limit in action.** If a user were one level deeper than
`MAX_SEARCH_DEPTH = 3` allows:

```python
deep = {"a": {"b": {"c": {"d": {"login": "x"}}}}}
find_actor_refs(deep, "payload", 3)   # -> []
```

by the time it reached `{"login": "x"}`, `depth` would be **-1**, and the
first check (`if depth < 0: return []`) would stop there: it **doesn't find
it**. That's the price of the safety net; since GH Archive payloads are
shallow, nothing is lost in practice.

**Why `profile()` uses `set(...)` afterwards.** The result contains
`payload.issue.assignees` **twice**, once for ana and once for marta.
`profile()` calls `set(...)`, which keeps each path only once:

```python
{'payload.issue.user', 'payload.issue.assignees', 'payload.issue.milestone.creator'}
```

So this event counts as **one** event that has assignees, not two: what's
being counted is *in how many events* each path appears, not how many users
there are.

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

### Summary: what we know about this hour's data

This section brings together in one place what `peek_data.py`,
`summarize_data.py` and `profile_schema.py` have found about the project's
fixed hour (2026-08-27, 15:00 UTC, 69,429 events).

#### 1. How to read an event's data

Each line of the file is a separate JSON. `json.loads(line)` turns it into
a Python **dictionary**, and from there each piece of data is reached by
its key. Some data sits in a **dictionary inside another dictionary**,
which is why it takes **two sets of square brackets**: the first goes into
the inner dictionary, and the second picks the value.

| What you want to know | How to get it | Example |
|---|---|---|
| Who did the action | `event["actor"]["login"]` | `"octocat"` |
| Their numeric identifier | `event["actor"]["id"]` | `583231` |
| Which repo it happened in | `event["repo"]["name"]` | `"octocat/Hello-World"` |
| The repo's numeric identifier | `event["repo"]["id"]` | `1296269` |
| What kind of action it was | `event["type"]` | `"PushEvent"` |
| When it happened | `event["created_at"]` | `"2026-08-27T15:00:01Z"` |
| The action's details | `event["payload"]` | depends on the event type |

For example, `event["actor"]["login"]` reads as: "inside the event, take
the `actor` dictionary; inside that, take the value of `login`".

The first five are present in **every** event (checked: all 69,429 have
`actor.id` and `repo.id`). They're exactly what the benchmark's minimal
schema needs: who (Actor), where (Repo), and the connection between them.
For table and node keys it's better to use the numeric `id`s, not the
names: a user can change their `login`, but their `id` never changes.

#### 2. Other people inside the `payload`

The `payload` can contain more users, shaped like the actor (a dictionary
with `login`). `profile_schema.py` finds them by looking for `login` at any
level of the `payload`, thanks to recursion.

But **finding a user doesn't mean finding another person**. When each user
found is compared with the event's actor, most turn out to be the actor
themself (see "Second check" above). Only **178 of 69,429 events (0.26%)**
really name a different person, and only **76** once bots are removed.

#### 3. What each event type holds in this hour

| Event type | Events | % of total | What the `payload` holds | Users inside the `payload` | Does it name another person? |
|---|---|---|---|---|---|
| `PushEvent` | 66,174 | 95.3% | The branch (`ref`), the commit before and after the push (`before`, `head`), `push_id` and `repository_id` | None | No |
| `CreateEvent` | 1,290 | 1.9% | What was created: in this hour, always a branch (`ref_type = "branch"`). Also the main branch and a `description`, which is empty in 633 of 1,290 | None | No |
| `DeleteEvent` | 615 | 0.9% | What was deleted: 586 branches and 29 tags | None | No |
| `PullRequestEvent` | 532 | 0.8% | The action (`opened`, `closed`...), the PR number, a trimmed `pull_request` **without its author**, and sometimes labels (25%) | `assignee`/`assignees` (2.1%) | Very rarely: 7 events |
| `IssueCommentEvent` | 194 | 0.3% | The commented issue and the comment | `comment.user` (100%), `issue.user` (100%), app owner (63%), assignees (16.5%), milestone creator (3.6%) | **Yes, the most:** `issue.user` is someone else 66% of the time (131 events) |
| `IssuesEvent` | 189 | 0.3% | The issue and its action; sometimes labels (45%) and assignees (7.4%) | `issue.user` (100%), assignees (20%), app owner (11%) and others | Sometimes: 35 events (`issue.user` is the actor 87% of the time) |
| `PullRequestReviewCommentEvent` | 134 | 0.2% | The comment and the PR | `comment.user` (100%) | No: it's the actor |
| `PullRequestReviewEvent` | 131 | 0.2% | The review and the PR | `review.user` (100%) | Almost never: 1 event |
| `WatchEvent` | 96 | 0.1% | Only the action: always `started`, i.e. someone **starred** the repo | None | No |
| `ReleaseEvent` | 44 | 0.1% | The published release | `release.author` (100%), mentions (6.8%) | Almost never: 2 events |
| `ForkEvent` | 18 | 0.03% | The new copy of the repo (`forkee`) | `forkee.owner` (100%) | No: the fork's owner is whoever forks it |
| `CommitCommentEvent` | 7 | 0.01% | The comment on a commit | `comment.user` (100%) | No: it's the actor |
| `MemberEvent` | 5 | 0.01% | The person added to the repo (`member`) | `member` (100%) | Sometimes: 2 events |

How to read the table: the "Users inside the `payload`" column is what
`profile_schema.py` shows, and the last column is the result of comparing
those users with the actor.

#### 4. What this means for the project

- **The essentials are in every event and easy to read:**
  `actor.id`/`actor.login`, `repo.id`/`repo.name`, `type` and
  `created_at`. That's enough to build the minimal schema (Actor, Repo,
  and the connection between them).
- **Almost everything is a push (95.3%), and a push names nobody else.**
  People connect to each other through the **repos they share**, not
  directly.
- **Direct person → person connections are almost nonexistent** (0.26% of
  events, 76 without bots), so the benchmark can't rely on them. That's
  why the schema has no actor → actor edge.
- **A field that looks like another person isn't necessarily one.**
  Before using any user from the `payload`, check it against the actor,
  and drop paths like `performed_via_github_app.owner`, which is an app's
  owner, not a participant.
- **This hour on its own is small and fragmented** (see "Connectivity
  findings" in the Summary Stage). The next step is to download more hours
  and measure again.

The overall pipeline so far is: **download_gharchive.py → peek_data.py →
summarize_data.py → profile_schema.py** — first fetch and decompress the
fixed dataset hour, then inspect a handful of raw events, then get an
aggregate read on volume and connectivity, then profile the payload shape
and locate second-actor references, before moving on to actually
extracting and loading records into the relational and graph models being
compared.


## Installing the software (PostgreSQL, Neo4j and the Python connectors)

With the minimal schema decided (tables `actor`, `repo` and `actor_repo`
in the relational database; nodes `Actor` and `Repo` with an edge between
them in the graph database), the next step is to install both databases
and what Python needs to talk to them.

### Before you start

**What we'll install** (all free):

| Software | What it's for | Cost |
|---|---|---|
| **PostgreSQL** (with **pgAdmin**) | The relational database. pgAdmin is a graphical interface to look at it and run queries | Free, open source |
| **Neo4j Desktop** | Manages Neo4j graph databases on your computer, with a graphical interface | Free for local development use |
| **`psycopg`** (Python package) | The connector that lets Python talk to PostgreSQL | Free |
| **`neo4j`** (Python package) | The official connector that lets Python talk to Neo4j | Free |

**Both databases go on the same computer.** That way neither gets an
advantage from being on another machine or behind a network: it's part of
controlling everything except what's being measured (see the section on
what a benchmark is).

**If you're on a work laptop:** installing software may need IT's
permission or be restricted by company policy. Check before you start.

**Passwords never go into the repository.** During installation you'll
choose two passwords: one for PostgreSQL and one for Neo4j. Keep them in a
password manager. Don't write them in the code, in these notes, or in any
file that gets pushed to GitHub. Further down there's a safe way to pass
them to Python.

### Step 1: install PostgreSQL

1. **Download the installer.** Go to
   <https://www.postgresql.org/download/windows/> and click *Download the
   installer*. Pick the **latest version** for **Windows x86-64**.
2. **Run the installer** and accept the defaults, with these details:
   - **Components:** keep *PostgreSQL Server*, *pgAdmin 4* and *Command
     Line Tools* ticked. *Stack Builder* isn't needed (you can untick it).
   - **Password:** it will ask for a password for the `postgres` superuser.
     Choose one and save it in your password manager.
   - **Port:** keep the default, **5432**.
   - **Locale:** keep the default.
   - At the end, if it offers to launch *Stack Builder*, untick it.
3. **Add `psql` to the PATH** (so you can use it from Git Bash). `psql` is
   PostgreSQL's command-line program. The installer doesn't add it to the
   PATH, so:
   - Search Windows for *"Edit environment variables for your account"*.
   - Under *Path*, click *Edit* → *New* and add
     `C:\Program Files\PostgreSQL\<version>\bin` (replace `<version>` with
     the folder number that was created, e.g. `18`).
   - Close and reopen Git Bash so it picks it up.
   - If you'd rather not touch the PATH, you can use *SQL Shell (psql)* from
     the Start menu, which does the same thing.
4. **Check that it works** (with Git Bash; to do it with pgAdmin 4, see
   the next section):

   ```bash
   psql -U postgres -c "SELECT version();"
   ```

   It will ask for the `postgres` password and should show the installed
   version.
5. **Create the project's database** (with Git Bash; with pgAdmin 4, see
   the next section):

   ```bash
   psql -U postgres -c "CREATE DATABASE gharchive;"
   psql -U postgres -d gharchive -c "SELECT 1;"
   ```

   The second command checks that you can connect to the new database: it
   should show a small table with a `1`.

PostgreSQL is installed as a **Windows service**: it starts on its own when
the computer boots and keeps running in the background. If you want to stop
it when you're not using it, search Windows for *Services* and stop the
`postgresql-x64-<version>` service.

### Two ways to work with PostgreSQL: Git Bash (`psql`) or pgAdmin 4

Everything done with `psql` in Git Bash can also be done with **pgAdmin
4**, the graphical interface installed alongside PostgreSQL. **You can use
whichever you prefer, or both**: they work on the same database, so
whatever you create with one you'll see with the other.

| Task | With Git Bash (`psql`) | With pgAdmin 4 |
|---|---|---|
| Open | A Git Bash terminal (with `psql` on the PATH, step 1.3) | Search for **pgAdmin 4** in the Start menu |
| Connect | Each command includes `-U postgres` and asks for the password (or reads it from `PGPASSWORD`) | Left panel: **Servers** → **PostgreSQL** → enter the `postgres` password |
| See the version | `psql -U postgres -c "SELECT version();"` | Open the Query Tool (see below), type `SELECT version();` and press **F5** |
| Create the `gharchive` database | `psql -U postgres -c "CREATE DATABASE gharchive;"` | Right-click **Databases** → **Create** → **Database...** → name `gharchive` → **Save** |
| Run a query | `psql -U postgres -d gharchive -c "..."` | Select `gharchive` in the tree → **Tools** menu → **Query Tool** → type the query → **F5** (or ▶) |
| See the tables | `psql -U postgres -d gharchive -c "\dt"` | Tree: **gharchive** → **Schemas** → **public** → **Tables** |
| See a table's data | `psql -U postgres -d gharchive -c "SELECT * FROM actor LIMIT 10;"` | Right-click the table → **View/Edit Data** |

**Checking that PostgreSQL works with pgAdmin 4 (no Git Bash):**

1. **Open pgAdmin 4** from the Windows Start menu. The first time, it will
   ask for a *master password*: a password just for pgAdmin, which
   protects the passwords it stores. Choose one and save it in your
   password manager.
2. **Connect to the server:** in the left panel, expand **Servers** (the
   little arrow) and click **PostgreSQL** (shown with its version number,
   e.g. *PostgreSQL 18*). It will ask for the **`postgres`** user's
   password, the one you chose during installation.

   ✅ **First check:** if the server expands and you see **Databases**,
   **Login/Group Roles** and **Tablespaces** under it, PostgreSQL is
   running and accepting connections.
3. **Check the version with a query:** expand **Databases** and click
   **postgres** (the database that comes by default). Go to the **Tools**
   menu → **Query Tool**, type `SELECT version();` and press **F5** (or
   the ▶ *Execute* button).

   ✅ **Second check:** below, under *Data Output*, a row appears with text
   like `PostgreSQL 18.x on x86_64-windows...`.
4. **Create the project's database:** right-click **Databases** →
   **Create** → **Database...**, type `gharchive` under **Database** and
   click **Save**.

   ✅ **Third check:** `gharchive` appears in the **Databases** list.
   Select it, open **Tools** → **Query Tool** again, run `SELECT 1;`, and
   you should get a `1`.

**If something goes wrong:**

- **Password error:** use the `postgres` user's password (the one from the
  installation), not pgAdmin's *master password*. They're two different
  passwords.
- **"Could not connect to server" or a connection error:** the PostgreSQL
  service isn't running. Search Windows for **Services**, find
  `postgresql-x64-<version>` and click **Start**.

**When each one is handy:**

- **pgAdmin 4** is more comfortable for **exploring**: seeing which tables
  there are, looking at their data, and trying out queries at your own
  pace. If you use it, step 1.3 (adding `psql` to the PATH) is optional.
- **Git Bash** is still needed to **run the project's Python scripts**
  (the ones that will create the CSVs, load the data and measure the
  times). And `psql` is handy when you want to repeat a command exactly the
  same way, copying it from these notes.

Another option, if you'd rather not leave the editor, is Microsoft's
**PostgreSQL** extension for VS Code, which also lets you connect and run
queries.

### Step 2: install Neo4j Desktop

1. **Download Neo4j Desktop.** Go to <https://neo4j.com/download/>. It will
   ask for some details in a form before the download. If the page shows an
   **activation key**, copy it: Neo4j Desktop will ask for it the first time
   you open it.
2. **Install it and open it.**
3. **Create a local database** (Neo4j Desktop calls it an *instance* or a
   *DBMS*, depending on the version):
   - **Name:** `gharchive`.
   - **Version:** the latest one it offers.
   - **Password:** choose one for the `neo4j` user and save it in your
     password manager.
4. **Start it** with the *Start* button. Neo4j listens on two ports:
   - **7474**, for the browser (Neo4j Browser);
   - **7687**, for programs, including Python (the *Bolt* protocol).
5. **Check that it works** (quick check; the full one is in the next
   section). Open Neo4j Browser (the *Open* button, or
   <http://localhost:7474> in your web browser), log in with the `neo4j`
   user and your password, and run:

   ```cypher
   RETURN 1;
   ```

   It should return `1`.

Unlike PostgreSQL, the Neo4j database **only runs while it's started** in
Neo4j Desktop. Before working with it, open Neo4j Desktop and check that
it's running.

### Checking that Neo4j works from the interface

Neo4j is almost always handled through a graphical interface, so you
**don't need Git Bash** to check it. There are two visual tools:

| Tool | What it's for | PostgreSQL equivalent |
|---|---|---|
| **Neo4j Desktop** | Creating, starting and stopping databases | pgAdmin's **Servers** panel |
| **Neo4j Browser** | Writing queries and seeing the results, even drawn as nodes and edges | pgAdmin's **Query Tool** |

**Step by step:**

1. **Open Neo4j Desktop** and find the `gharchive` database. Depending on
   the Desktop version, it appears in the *Instances* list or inside a
   *Project*.

   ✅ **First check:** its status says **Running** or **Active** (usually
   with a green dot). If it says *Stopped*, click **Start** and wait a few
   seconds.
2. **Open Neo4j Browser:** click **Open** (or *Query*, depending on the
   version) next to the database, or go to <http://localhost:7474> in your
   web browser. If it asks you to connect:
   - **Connect URL:** `neo4j://localhost:7687`
   - **Username:** `neo4j`
   - **Password:** the one you chose when creating the database

   ✅ **Second check:** the connection is accepted and a bar for typing
   queries appears at the top, with the `neo4j$` prompt.
3. **Check the version.** Type this in the top bar and press
   **Ctrl + Enter** (or the ▶ button):

   ```cypher
   CALL dbms.components() YIELD name, versions, edition
   RETURN name, versions, edition;
   ```

   ✅ **Third check:** a row appears with `Neo4j Kernel`, the version
   number and the edition.
4. **Try writing and reading**, to confirm it can really store data:

   ```cypher
   CREATE (p:Test {message: "hello"}) RETURN p;
   ```

   ✅ **Fourth check:** a **circle** appears in the result: it's a node,
   in Neo4j's graph view. If you click it, you'll see its property
   `message: "hello"`.

   Then delete it, to leave the database empty:

   ```cypher
   MATCH (p:Test) DELETE p;
   ```

   It should say *Deleted 1 node*.

**The database's name.** In Neo4j Desktop, `gharchive` is the name of the
**instance** (the "server"). Inside it, the database you work in is called
**`neo4j`**: it's the default one, and it's the one we'll use. There's no
need to create another; the `neo4j$` in the query bar shows that's exactly
where you are.

**If something goes wrong:**

| Problem | Likely cause | Fix |
|---|---|---|
| The database won't go to *Running* | Another program is using port 7474 or 7687 | Read the error message in Desktop; close the other program or change the port in the settings |
| *Authentication failure* | Wrong password | Use the one you chose when **creating the database** in Neo4j Desktop (not the PostgreSQL one) |
| Neo4j Browser won't connect | The database is stopped | Go back to Desktop and click **Start** |
| The graph view shows nothing | The query returns no nodes | Normal for queries like `RETURN 1`; try the one in point 4 |

**And from the terminal?** Neo4j comes with **`cypher-shell`**, the
equivalent of `psql`, and Neo4j Desktop can open a terminal already set up
to use it. For this project, Neo4j Browser is enough.

### Checkpoint: both databases are ready

At this point, both of the project's databases are **installed, running
and checked**:

| Database | Where it's managed | What's inside it now | How it was checked |
|---|---|---|---|
| **PostgreSQL** (relational) | pgAdmin 4 or `psql` | The `gharchive` database, empty: no tables yet | Connection accepted, version visible, and `SELECT 1;` in `gharchive` |
| **Neo4j** (graph) | Neo4j Desktop and Neo4j Browser | The `gharchive` instance, with its empty `neo4j` database: no nodes yet | *Running* status, connection accepted, version visible, and a write-and-read test |

Both are **empty on purpose**. The tables (`actor`, `repo`, `actor_repo`)
and the nodes (`Actor`, `Repo`) will be created later, from Python
scripts, out of the same data files for both sides. For that, first you
need to set up the place where those scripts will run: a small Python
environment of the project's own.

### Step 3: set up Python (a virtual environment for the project)

#### 3.1 The problem a virtual environment solves

Until now, the project's scripts (`download_gharchive.py`, `peek_data.py`,
`summarize_data.py`, `profile_schema.py`) only used Python's **standard
library**: modules like `json`, `argparse` or `collections`, which come
included with Python. That's why they worked without installing anything.

From now on, Python has to talk to PostgreSQL and Neo4j, and for that it
needs two **external packages**, which don't come with Python and have to
be installed: `psycopg` and `neo4j`. The question is *where* to install
them.

If they're installed "into the computer's Python" (the general
installation, shared by every project), three problems appear:

1. **Conflicts between projects.** If another project needs a different
   version of the same package, only one can be installed at a time, and
   one of the two projects breaks.
2. **Nobody knows what the project needs.** Over time, the general
   installation piles up packages from many projects, and it's no longer
   clear which ones this project needs.
3. **It isn't reproducible.** To repeat the experiment on another
   computer, you need to know exactly which packages and versions were
   used. In a benchmark, that's part of the experiment's conditions, just
   like the database versions.

A **virtual environment** solves all three: it's an **isolated Python just
for this project**, with its own packages.

#### 3.2 What a virtual environment physically is

It's simply a **folder** inside the project, which we'll call `.venv`.
Inside, it contains:

```
.venv/
├── Scripts/
│   ├── python.exe        ← a Python that only uses .venv's packages
│   ├── pip.exe           ← this environment's package installer
│   └── activate          ← the script that "activates" the environment in Git Bash
└── Lib/
    └── site-packages/    ← where the installed packages are stored
```

An analogy: the computer's general Python is the **shared kitchen** in a
shared flat, where everyone leaves their things and they end up mixed. The
virtual environment is **a box with your name on it** inside that kitchen:
what you put in it is yours alone, you know exactly what's there, and if
one day you want to start over, you throw the box away and make a new one.

A few important details:

- **It doesn't contain a full copy of Python.** It uses the Python 3.14
  you already have installed, but with its own packages folder.
- **It doesn't contain your code.** The scripts stay in `scripts/` as
  always; the environment only provides the Python and the packages they
  run with.
- **It isn't pushed to GitHub.** The `.venv` folder is already in
  `.gitignore`. What does get pushed is the *list* of packages
  (`requirements.txt`, in point 3.6), so anyone can recreate the
  environment.
- **It can be deleted without worry.** If something goes wrong, delete the
  `.venv` folder and create it again in a minute.

#### 3.3 Create the environment (once only)

```bash
cd /c/dev/Research
python -m venv .venv
```

- `cd /c/dev/Research` puts you in the project's folder. The environment is
  created inside whichever folder you're in.
- `python -m venv .venv` means: "Python, run your `venv` module and create
  a virtual environment in a folder called `.venv`". The leading dot in the
  name is a convention: on many systems, folders starting with a dot are
  treated as "configuration" folders.

It takes a few seconds and prints nothing if all goes well. You can check
it was created with `ls -a`, which should list `.venv` among the folders.

**This is done only once.** The environment stays saved in the folder and
works for good (or until you delete it).

#### 3.4 Activate the environment (every time you open a terminal)

```bash
source .venv/Scripts/activate
```

**What "activating" does:** it changes, in that terminal only, which
Python the word `python` refers to. Before activating, `python` is the
computer's general Python; afterwards, it's `.venv`'s. The same goes for
`pip`. That way, everything you install or run goes to the project's
environment.

**How to tell it's active:**

- The Git Bash prompt starts with `(.venv)`:

  ```
  (.venv) NB30006@LT301102 MINGW64 /c/dev/Research (main)
  ```

- And this command shows the path of the Python being used, which should
  be inside `.venv`:

  ```bash
  which python
  # → /c/dev/Research/.venv/Scripts/python
  ```

**Activation only lasts as long as the terminal.** If you close Git Bash
and open another one, the environment is no longer active and you need to
run `source .venv/Scripts/activate` again. The environment still exists
(the folder isn't deleted); you just need to "step back in".

**Deactivate:** if you want to go back to the general Python without
closing the terminal, type `deactivate`.

**If you use another terminal** (the command depends on the type):

| Terminal | Command to activate |
|---|---|
| Git Bash | `source .venv/Scripts/activate` |
| PowerShell | `.venv\Scripts\Activate.ps1` |
| Command Prompt (CMD) | `.venv\Scripts\activate.bat` |

In PowerShell, Windows may block activation because of its script
execution policy, and on a work laptop you may not be allowed to change it.
That doesn't happen with Git Bash, so it's the recommended option.

#### 3.5 Make VS Code use the environment

VS Code also needs to know which Python to use, so its terminal and its
error checking work with the environment's packages:

1. Open the `c:\dev\Research` folder in VS Code.
2. Press **Ctrl + Shift + P**, type **Python: Select Interpreter** and
   choose it.
3. In the list, pick the one with the path `.\.venv\Scripts\python.exe`
   (it's usually marked as *Recommended*).

From then on, new terminals you open inside VS Code usually activate the
environment on their own: you'll see `(.venv)` at the start of the line. If
it doesn't appear, activate it by hand with the command from point 3.4.

#### 3.6 Install the project's packages

With the environment **active** (check for the `(.venv)`):

```bash
python -m pip install "psycopg[binary]" neo4j
```

What each part means:

- `python -m pip` uses the active Python's `pip`, i.e. the environment's.
  It's safer than typing just `pip`, because it guarantees the packages go
  to the same Python that will run the scripts.
- `install` downloads the packages from **PyPI** (the public repository of
  Python packages) and saves them in `.venv/Lib/site-packages`.
- `psycopg` is the connector for **PostgreSQL**. The `[binary]` part is an
  *extra*: it asks for the version that already includes the compiled
  pieces it needs, so nothing else has to be installed on Windows. It's in
  quotes because Git Bash might otherwise interpret the square brackets.
- `neo4j` is the official connector for **Neo4j**.

`pip` also automatically installs those packages' **dependencies** (other
packages they need), so you'll see more names in the output than the ones
you asked for. That's normal.

**Record the dependencies.** In the project's root folder there's a
`requirements.txt` file with both packages and **their exact version**:

```
psycopg[binary]==3.3.6
neo4j==6.4.1
```

(Lines starting with `#` in the real file are comments, and `pip` ignores
them.)

It's the project's "shopping list": it says which packages it needs. This
file **does** get pushed to GitHub. On another computer (or if you ever
recreate the environment), all it takes is:

```bash
python -m pip install -r requirements.txt
```

These two packages' dependencies (`psycopg-binary`, `tzdata` and `pytz`)
don't need to be listed: `pip` installs them automatically.

**Why `==`: in a benchmark, the conditions always have to be the same.**
`==` means "exactly this version". Without it, `pip` installs the **latest**
version available at install time, so the same `requirements.txt` would
give different versions today and six months from now.

In an ordinary project that usually doesn't matter. In this one it does,
because the goal is to **compare two tools**, and a comparison is only fair
if the only thing that changes is what's being measured (see "What
'benchmark' means, for this project"). The connectors are part of the path
every query takes: Python → connector → database → connector → Python. If a
new connector version is faster or slower, the times change, and not
because of PostgreSQL or Neo4j. Pinning the versions avoids three
problems:

1. **Contaminated comparisons.** If the Neo4j connector gets updated
   halfway through the project but the PostgreSQL one doesn't, the later
   measurements no longer compare the same thing as the earlier ones.
2. **Results that can't be repeated.** Anyone wanting to check the
   results, or you yourself a few months from now, needs to rebuild
   exactly the same environment. With `==`, `pip install -r
   requirements.txt` always does that.
3. **Changes that go unnoticed.** If a time changes from one measurement
   to the next, you need to be able to rule out an update as the cause.
   With pinned versions, you know it wasn't.

For the same reason, you need to write down **every** version involved, not
just the Python ones: PostgreSQL's, Neo4j's, Python's (3.14), and the
connectors'. This command shows the exact versions of every package in the
environment, dependencies included:

```bash
python -m pip freeze
```

If you ever decide to update a connector, change its version in
`requirements.txt`, note the change, and **repeat every measurement** with
the new version, so all the results were obtained under the same
conditions.

#### 3.7 Check that the environment is fine

```bash
python -m pip list
```

should show `psycopg`, `psycopg-binary` and `neo4j` (among others). And
this command confirms that Python can **import** them and shows their
versions:

```bash
python -c "import psycopg, neo4j; print('psycopg', psycopg.__version__); print('neo4j', neo4j.__version__)"
```

If both versions appear, the environment is ready.

#### 3.8 If something goes wrong

| Problem | Likely cause | Fix |
|---|---|---|
| `bash: .venv/Scripts/activate: No such file or directory` | You're not in the project folder, or the environment wasn't created | Run `cd /c/dev/Research` and check with `ls -a` that `.venv` exists; if not, create it (point 3.3) |
| `ModuleNotFoundError: No module named 'psycopg'` (or `'neo4j'`) | The environment isn't active, or the packages went into another Python | Activate the environment (point 3.4), check with `which python`, and reinstall (point 3.6) |
| No `(.venv)` in VS Code | VS Code isn't using the environment | Pick `.venv`'s interpreter (point 3.5) and open a new terminal |
| PowerShell won't let you activate the environment | Windows' script execution policy | Use Git Bash (point 3.4) |
| The environment is broken | Packages in a bad state or mixed up | Deactivate it (`deactivate`), delete the folder (`rm -rf .venv`), and start again from point 3.3 |

#### 3.9 Summary: the daily routine

**Once only** (already done if you followed the points above):

```bash
cd /c/dev/Research
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

**Every time you open a terminal to work on the project:**

```bash
cd /c/dev/Research
source .venv/Scripts/activate
```

And check the line starts with `(.venv)` before running any script. The
older scripts, which only use the standard library, work just the same
inside the environment, so you can always work with it active.

### Step 4: pass the passwords to Python without writing them in the code

#### 4.1 The idea: environment variables

Passwords aren't written in the Python code. They're kept in **environment
variables**: values that live in the terminal while it's open, outside the
code. The project uses two:

| Variable | Password of | Who reads it |
|---|---|---|
| `PGPASSWORD` | PostgreSQL's `postgres` user | PostgreSQL and `psycopg`, **automatically**: it's a standard name, so the code doesn't even mention it |
| `NEO4J_PASSWORD` | Neo4j's `neo4j` user | Our scripts, with `os.environ["NEO4J_PASSWORD"]` |

They could be set by hand with `export` every time a terminal is opened,
but that's tedious and easy to forget. Instead, they're kept in a small
bash script that's loaded with a single command.

#### 4.2 Why it works: variables are inherited

When one program starts another, the new one **receives a copy of the
environment variables** of the one that launched it. If the terminal has
`NEO4J_PASSWORD` set, any Python script run from it inherits it and can
read it.

But the script has to be loaded the right way:

| Command | What happens |
|---|---|
| `source secrets.sh` | The script runs **inside your terminal**. The variables stay set in it, and everything you run afterwards inherits them, until you close the terminal. **This is the right way.** |
| `bash secrets.sh` | The script runs in **a separate bash**, which sets the variables and exits straight away. Your terminal doesn't see them, and neither does Python. |

#### 4.3 The two files

| File | What it contains | Pushed to GitHub? |
|---|---|---|
| `secrets.example.sh` | A **template** with both variables and placeholder values, no real passwords | **Yes**: so it's clear which variables are needed |
| `secrets.sh` | The **real passwords** | **Never**: it's in `.gitignore` |

#### 4.4 Create your `secrets.sh` (once only)

1. Copy the template:

   ```bash
   cp secrets.example.sh secrets.sh
   ```

   > ⚠️ **Don't edit or rename `secrets.example.sh`.** It's the template,
   > and it's pushed to GitHub on purpose, with no passwords, so it's clear
   > which variables are needed. The real passwords go **only in the copy**,
   > `secrets.sh`. `.gitignore` blocks exactly that name (`/secrets.sh`),
   > not everything starting with `secrets`: that's why the template is
   > pushed and the copy isn't.

2. Open `secrets.sh` in VS Code and replace both placeholder values with
   your real passwords, keeping the single quotes:

   ```bash
   export PGPASSWORD='...'
   export NEO4J_PASSWORD='...'
   ```

3. Check that git ignores it:

   ```bash
   git check-ignore -v secrets.sh
   ```

   It should answer with the `.gitignore` line that ignores it
   (`/secrets.sh`). And `git status` should **not** list `secrets.sh` as a
   new file.

#### 4.5 Password precautions

- **Type them straight into `secrets.sh`.** Don't paste them into chats,
  emails, notes or any other project file. A password that has been written
  down somewhere else should no longer be considered secret: if that
  happens, change it.
- **Use a different password for each database**, long and hard to guess,
  and keep them in a password manager.
- **If `secrets.sh` ever got pushed to GitHub,** it stays in the git
  history even if it's deleted afterwards. In that case, change both
  passwords.
- **To change them:** in PostgreSQL, from pgAdmin (**Login/Group Roles** →
  **postgres** → **Properties** → **Definition**); in Neo4j, from Neo4j
  Browser, with `:use system` and then
  `ALTER CURRENT USER SET PASSWORD FROM '...' TO '...';`. Then update
  `secrets.sh`.

#### 4.6 The full daily routine

Every time you open a terminal to work on the project:

```bash
cd /c/dev/Research
source .venv/Scripts/activate     # the project's Python
source secrets.sh                 # the passwords
```

To check the passwords are loaded **without printing them on screen**:

```bash
[ -n "$PGPASSWORD" ] && echo "PGPASSWORD loaded"
[ -n "$NEO4J_PASSWORD" ] && echo "NEO4J_PASSWORD loaded"
```

(`-n` checks that the variable isn't empty, so its value is never written
to the terminal.)

#### 4.7 A shortcut: `run.sh`, which sets everything up and runs Python

The routine in point 4.6 works, but it's three commands every time, and if
one is forgotten (activating `.venv` or loading `secrets.sh`), the Python
script fails with an unclear error. That's why the project has a small
bash script, **`run.sh`**, in the root folder, that does it all at once:

```bash
./run.sh scripts/check_connections.py
```

Inside, `run.sh` does this, in order:

1. **Moves to the project folder**, wherever you call it from.
2. **Checks everything is in place** and, if not, stops with a clear
   message:
   - if you didn't say which script to run, it shows how to use it;
   - if `.venv` doesn't exist, it says how to create it (step 3);
   - if `secrets.sh` doesn't exist, it says how to create it (point 4.4);
   - if `secrets.sh` still has the template's placeholder passwords, it
     warns that they need replacing.
3. **Activates the virtual environment** (`source .venv/Scripts/activate`).
4. **Loads the passwords** (`source secrets.sh`).
5. **Runs Python** with the script you passed and its options, if any.
   Python **inherits** the passwords from `run.sh` (point 4.2).

**Why it's better than loading the passwords into your terminal:**

| | Routine from point 4.6 | `./run.sh` |
|---|---|---|
| Commands each time | 3 | 1 |
| If something is forgotten | Python fails with a confusing error | `run.sh` stops and explains what's missing |
| Where the passwords live | In your terminal, until you close it | Only while the script runs; they're gone when it finishes |

**How the passwords reach Python without going through your terminal.**
That last point is the original idea: the passwords stay **outside the
Python code**, in a bash script, and Python **inherits** them by being
launched from it. To understand it properly, it helps to see which programs
start, and in what order, when you type
`./run.sh scripts/check_connections.py`:

```
Your terminal (Git Bash)                ← never has the passwords, before or after
 └── launches run.sh  → a NEW bash, a child of your terminal
       ├── source .venv/Scripts/activate  → activates the environment INSIDE this child bash
       ├── source secrets.sh              → loads the passwords INSIDE this child bash
       └── exec python scripts/check_connections.py
             └── Python takes the child bash's place and INHERITS its variables:
                 the activated environment and both passwords
                       ↓
             Python finishes → the process disappears, and the passwords with it
```

Step by step:

1. **Your terminal launches `run.sh` as a new program**, a *child* bash.
   The child receives a copy of your terminal's variables (point 4.2), but
   your terminal never gets anything back: inheritance only flows from
   parent to child, never the other way round.
2. **Inside the child, `run.sh` does use `source`**, twice: to activate
   `.venv` and to load `secrets.sh`. With `source`, those scripts run
   *inside* the child bash, so the passwords end up set in it (not in a
   separate bash that closes straight away).
3. **Finally, `run.sh` launches Python with `exec`.** `exec` makes Python
   **take the place** of the child bash, instead of creating yet another
   process. Python inherits everything the child had set: the activated
   virtual environment and both passwords. That's why `psycopg` finds
   `PGPASSWORD` and the script finds `NEO4J_PASSWORD`.
4. **When Python finishes, its process disappears**, and the passwords
   with it. Your terminal is just as it was: if you type
   `echo "$NEO4J_PASSWORD"`, nothing comes out.

**Why you don't need to type `source run.sh` here.** In point 4.2 we saw
that `bash secrets.sh` doesn't work: the separate bash loads the passwords
and closes **without launching anything**, so nobody gets to use them.
With `run.sh` it's exactly the opposite: the separate bash loads the
passwords **and then launches Python from inside**, so Python inherits them
before that bash ends. `source` is still there, but *inside* `run.sh`, not
in your terminal.

**Why it's the safest of the options we've seen:** the passwords only
exist in memory **while the script runs**, and only in that process. No
other command you run in your terminal can see them, and they don't stay
loaded when you're done.

**It works for any project script,** present or future. Whatever you type
after the script's name is passed on as-is:

```bash
./run.sh scripts/check_connections.py
./run.sh scripts/summarize_data.py --top 10
```

(The older scripts don't need the passwords, but they work just the same
through `run.sh`.)

**If `./run.sh` doesn't work:** in Git Bash, a file starting with
`#!/usr/bin/env bash` can be run directly. If it still says *Permission
denied*, use `bash run.sh scripts/check_connections.py`, which does
exactly the same thing.

#### 4.8 And why not keep the passwords inside `.venv`?

It sounds logical: if the project already has its own virtual environment,
why not put the passwords there too? For example, by adding the two
`export` lines to the end of `.venv/Scripts/activate`, so they load when the
environment is activated. It would work, but it's worse than what we have,
for two reasons.

**1. A virtual environment isolates packages, not secrets.** `.venv` is
there so the project has its own versions of `psycopg` and `neo4j`. It
doesn't protect anything: it's a folder of ordinary files on your disk,
readable by any program running under your Windows user, exactly like
`secrets.sh`. Moving the passwords there doesn't make them safer; it only
changes which file they're in.

**2. It has practical drawbacks:**

| | Passwords in `.venv/Scripts/activate` | What we use (`secrets.sh` + `run.sh`) |
|---|---|---|
| Kept out of GitHub? | Yes (`.venv` is in `.gitignore`) | Yes (`secrets.sh` is in `.gitignore`) |
| Survive recreating the environment? | **No.** The environment is disposable (point 3.8: "delete `.venv` and create it again"), and the passwords would go with it | **Yes.** `secrets.sh` doesn't depend on the environment |
| How long are they loaded? | As long as the environment is active in the terminal, available to **any** command you run there | **Only while one script runs:** `run.sh` loads them, Python inherits them, and they're gone when it finishes |
| Easy to find and understand? | No: hidden inside a generated file nobody normally touches | Yes: one obvious file, with a template that documents it |

The last two rows are the ones that matter. `run.sh` already gives the
**narrowest exposure**: the passwords only exist while a script is running.

**Rule:** each tool for its own job. `.venv` for packages; `secrets.sh` +
`run.sh` for passwords.

**And in real projects?** In professional projects, or with sensitive
data, the usual step up is a **secret manager**: a service that keeps the
passwords **encrypted** and hands them only to the authorised program,
without them sitting in any readable file. Windows has one built in, the
**Credential Manager**, which Python can access with the `keyring`
package; cloud providers offer their own. It isn't needed here: it's a
personal project, with public data, and both databases only accept
connections from your own computer. But it's the option to consider if the
project ever handled anything sensitive.

### Step 5: check that Python can reach both databases

The project has a script for this: **`scripts/check_connections.py`** (with
its line-by-line explanation in [check_connections.py](check_connections.py),
the annotated copy). It connects to PostgreSQL and Neo4j with the passwords
from the environment variables and prints each server's version.

**How to run it**, with both databases running and your `secrets.sh`
already filled in:

```bash
./run.sh scripts/check_connections.py
```

**If all goes well**, you'll see something like this (this is the real
output on this project):

```
PostgreSQL OK: PostgreSQL 18.6 on x86_64-windows, compiled by msvc-19.44.35229, 64-bit
Neo4j OK: Neo4j Kernel 2026.10.0 (enterprise edition)
Neo4j OK: Cypher 5 ( edition)
Both databases are reachable.
```

Neo4j shows **two lines** because, in recent versions, the version query
returns two components: the database engine (*Neo4j Kernel*) and the query
language version (*Cypher 5*). The second has no edition, which is why the
brackets are empty. It isn't an error.

**How the script works, in short:**

1. It checks that `PGPASSWORD` and `NEO4J_PASSWORD` exist. If either is
   missing, it stops and says to run it through `run.sh`.
2. **PostgreSQL:** it connects to the `gharchive` database as `postgres`
   and runs `SELECT version();`. `psycopg` reads the password from
   `PGPASSWORD` on its own.
3. **Neo4j:** it reads `NEO4J_PASSWORD`, connects to
   `neo4j://localhost:7687` as `neo4j`, and runs the same version query as
   in Neo4j Browser (`CALL dbms.components() ...`).
4. It runs **both checks even if one fails** (with `try`/`except`), so an
   error in one doesn't hide the result of the other.

**If something goes wrong**, the script says which one and why:

| Message | Likely cause | Fix |
|---|---|---|
| `Missing environment variable(s): ...` | It was run with `python` directly, without `run.sh` | Run it with `./run.sh scripts/check_connections.py` |
| `PostgreSQL FAILED: ... password authentication failed` | The password in `secrets.sh` isn't the `postgres` one | Fix `PGPASSWORD` in `secrets.sh` |
| `PostgreSQL FAILED: ... Connection refused` | The PostgreSQL service is stopped | Start it from Windows *Services* (see the pgAdmin section) |
| `PostgreSQL FAILED: ... database "gharchive" does not exist` | The project's database wasn't created | Create it (step 1, point 5, or from pgAdmin) |
| `Neo4j FAILED: ... Unauthorized` | The password in `secrets.sh` isn't the `neo4j` one | Fix `NEO4J_PASSWORD` in `secrets.sh` |
| `Neo4j FAILED: ... Couldn't connect` / `Unable to retrieve routing information` | The Neo4j instance isn't started | Start it in Neo4j Desktop (*Start*) |
| `ModuleNotFoundError: No module named 'psycopg'` | The virtual environment or its packages are missing | Go over step 3 (`run.sh` already activates `.venv`) |

Once `Both databases are reachable.` appears, **the whole chain works**: the
virtual environment, the passwords, the connectors, and both databases.
It's the starting point for creating the tables and the nodes.

### How Python knows where each database is

Once `check_connections.py` works, a natural question comes up: how does
Python know where each database is? Does it search the computer for them?
How does it tell which one is PostgreSQL and which one is Neo4j?

**The short answer: it doesn't search for anything. We tell it**, with an
exact address for each one, written at the top of the script:

```python
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
```

#### The three parts of an address

Connecting to a database takes three things, just like reaching a shop
inside a shopping centre:

| Part | In the shopping centre | For the database | PostgreSQL | Neo4j |
|---|---|---|---|---|
| **Machine** (*host*) | The building | The computer the server runs on | `localhost` | `localhost` |
| **Port** | The shop number | The "door" that server listens on | `5432` | `7687` |
| **Protocol** | The language spoken inside | The "language" client and server use to talk | PostgreSQL's | *Bolt* (Neo4j's) |

**1. The machine: `localhost`.** It's a special name that always means
**"this same computer"** (its numeric address is `127.0.0.1`, the one shown
in Neo4j Desktop as the *Connection URI*). That's why the connection never
goes out to the internet: Python and both databases are on your laptop.

**2. The port: the door number.** A computer can have many programs
waiting for connections at the same time; each one "listens" on a different
port number, so they don't get mixed up. When installed, each server took
its own:

- **PostgreSQL** listens on **5432** (the one you accepted in the
  installer).
- **Neo4j** listens on **7687** for programs (the *Bolt* protocol) and on
  **7474** for the browser (Neo4j Browser).

The PostgreSQL settings don't mention `5432`: when no port is given,
`psycopg` uses that one by default. The Neo4j one does, inside the address
`neo4j://localhost:7687`.

**3. The protocol: each connector speaks only one language.** Here's the
answer to "how does it know whether it's PostgreSQL or Neo4j?": **it's
decided by which connector we use**.

- `psycopg.connect(...)` only speaks PostgreSQL's language, so it can only
  connect to a PostgreSQL server.
- `GraphDatabase.driver(...)` only speaks *Bolt*, Neo4j's language. The
  `neo4j://` at the start of the address says so.

If `psycopg` were pointed at Neo4j's port by mistake, it wouldn't "find"
something else: the connection would fail, because the server on the other
side doesn't understand the language.

#### What has to be running on your computer

For the connection to work, **the server has to be running and listening
on its port**:

| Server | What keeps it running | If it isn't running |
|---|---|---|
| PostgreSQL | A **Windows service**, which starts on its own when the computer boots | `Connection refused` (nobody answers on 5432) |
| Neo4j | The `gharchive` instance, started in **Neo4j Desktop** | `Couldn't connect` (nobody answers on 7687) |

#### The rest of the connection details

Once inside the server, two more things are needed:

- **Which user** to log in as: `postgres` in PostgreSQL and `neo4j` in
  Neo4j. Each one's password arrives through the environment variables
  (step 4).
- **Which database** to use, because a server can hold several:
  - In PostgreSQL, `dbname="gharchive"` says so.
  - In Neo4j, the script doesn't say yet, so the instance's default
    database (`neo4j`) is used. Your instance also has a `gharchive`
    database; once it's decided which one to work in, it will be set in
    the scripts that load the data.

#### If the databases were ever somewhere else

Only the address would change: for example, another computer's name
instead of `localhost`, or the port that server uses. Nothing else in the
code would change. That's why the addresses are kept together, as
constants, at the top of the script.

`check_connections.py`'s output confirms all of this: the PostgreSQL line
says `on x86_64-windows` (that's your Windows computer), and the Neo4j one
shows the version of the instance you have running in Neo4j Desktop.

### Checklist

| Check | How | Expected result |
|---|---|---|
| PostgreSQL installed | `psql -U postgres -c "SELECT version();"`, or `SELECT version();` in pgAdmin's Query Tool | PostgreSQL's version |
| `gharchive` database created | `psql -U postgres -d gharchive -c "SELECT 1;"`, or `SELECT 1;` in pgAdmin's Query Tool with `gharchive` selected | A table with a `1` |
| Neo4j running | `RETURN 1;` in Neo4j Browser | `1` |
| Virtual environment active | The Git Bash prompt starts with `(.venv)` | — |
| Connectors installed | `python -m pip show psycopg neo4j` | Details for both packages |
| Python reaches both | `./run.sh scripts/check_connections.py` | `PostgreSQL OK: ...`, `Neo4j OK: ...` and `Both databases are reachable.` |

**Write down the installed versions** (of PostgreSQL, Neo4j, and both
Python packages). They're part of the benchmark's conditions: for someone
to repeat the experiment, they need to know which versions it was run
with.


## Extraction Stage (extract_csv.py)

With both databases installed and checked, the next step is to fill them.
Before loading anything, the data they'll receive has to be prepared.

### Two decisions made before starting

1. **Both databases are called `gharchive`:** the PostgreSQL database and,
   inside the Neo4j instance, the `gharchive` database (not the default
   `neo4j` one). That way it's always clear where the project's data is,
   on both sides.
2. **One connection per actor–repo pair, no repeats.** If ana pushes 10
   times to the same repo, the connections table has **a single row** with
   ana's `id` and the repo's. What matters for walking the graph is
   *whether* ana is connected to that repo, not *how many times*. This
   decision applies identically on both sides (see the "query-first" design
   principle).

### Why a separate extraction step: one source for both sides

The work is split across three scripts:

| Script | What it does |
|---|---|
| `extract_csv.py` (this one) | Reads the JSON **once** and writes three CSV files |
| `load_postgres.py` (next) | Loads those CSVs into PostgreSQL |
| `load_neo4j.py` (next) | Loads **the same** CSVs into Neo4j |

Extraction is separate because it's what guarantees a fair comparison:
**both databases are loaded from the same files**, so neither can end up
with different data from the other. If each load read the JSON on its own,
any difference between the two scripts (a different bot filter, an edge
case handled another way) would change the data on one side only.

### What a CSV file is

**CSV** (*comma-separated values*) is a table in plain text: each line is a
row, commas separate the columns, and the first line (the **header**) gives
the column names:

```
id,login
19,brynary
452,yrashk
```

It's the simplest format for passing tables between programs, and both
PostgreSQL (with `COPY`) and Neo4j (with `LOAD CSV`) load it directly.

### The three files

| File | Columns | One row per | Will become |
|---|---|---|---|
| `actors.csv` | `id`, `login` | actor | the `actor` table / the `:Actor` nodes |
| `repos.csv` | `id`, `name` | repo | the `repo` table / the `:Repo` nodes |
| `actor_repo.csv` | `actor_id`, `repo_id` | actor–repo pair, no repeats | the `actor_repo` table / the edges between `:Actor` and `:Repo` |

They're saved in `data/csv/`. Like everything in `data/`, they **aren't
pushed to GitHub** (`data/` is in `.gitignore`): they can be regenerated at
any time by running the script.

### What the script does

1. **Reads each event** from the JSON file, one line at a time.
2. **Drops bots** (logins ending in `[bot]`), with the same rule as
   `summarize_data.py`.
3. **Keeps each actor and each repo once, by `id`**, with its most recent
   name (see below).
4. **Keeps each `(actor_id, repo_id)` pair in a `set`**. A set doesn't
   allow duplicates, so the same pair added ten times is kept only once:
   that's how the no-repeated-connections decision is enforced.
5. **Writes the three CSVs sorted by `id`**, so the same JSON always
   produces exactly the same files.

### What we found in the data: why ids and not names

Before writing the script we checked whether any `id` appeared with more
than one name. It happens in three cases, and one name appears with two
`id`s:

| Case | What happens | What the script does |
|---|---|---|
| Actor `321725054` | Changed their login during that hour: `lucky521-png` → `peitongshi` | One row, with the most recent name: `peitongshi` |
| Repo `1348625135` | Renamed along with its owner: `lucky521-png/niulai-chinese` → `peitongshi/niulai-chinese` | One row: `peitongshi/niulai-chinese` |
| Repo `1348068959` | Renamed: `xuange520/HyperArmor` → `xuange520/HyperArmor-skill` | One row: `xuange520/HyperArmor-skill` |
| Login `Copilot` | Two different accounts with the same name (`175728472` and `198982749`) | Two rows, one per `id` |

If names were used as keys, the first case would count as two people, the
renamed repos as two repos each, and the two `Copilot` accounts would be
merged into one. With `id`s, all four cases come out right. For the same
reason, **`login` can't be unique** in the `actor` table: two rows can
share it.

### How to run it

```bash
./run.sh scripts/extract_csv.py
```

(This script doesn't use the databases or the passwords, so
`python scripts/extract_csv.py` with the virtual environment active works
too. Going through `run.sh` is simplest: always the same.)

Result for the project's fixed hour:

```
Skipped 1970 bot events. Writing to C:\dev\Research\data\csv:
  actors.csv         14515 rows
  repos.csv          14995 rows
  actor_repo.csv     15053 rows
```

### What these numbers say

- **The actors (14,515) and repos (14,995) match exactly** the "analysis
  without bots" from `summarize_data.py`. That's a good check: both
  scripts apply the same rule and reach the same result.
- **67,459 non-bot events become only 15,053 connections.** Most events are
  the same person pushing several times to their own repo; since
  connections aren't repeated, all those events count as one. That's the
  data the benchmark actually needs.
- **There are barely more connections than actors** (15,053 vs 14,515):
  almost every actor is connected to a single repo. It's the
  fragmentation already seen in "Connectivity findings", now as data ready
  to load.

**Checks done:** the numbers above; the most recent names for the special
cases; the two `Copilot` rows; that running the script twice produces
**byte-for-byte identical** files; and that git ignores the `data/csv/`
folder.

The line-by-line explanation is in the [annotated copy](extract_csv.py).
New in this script: the `csv` module, tuples inside sets and dicts, keeping
the most recent value while reading, and why the output is sorted.

### New concept: tuples, and how they combine with dicts and sets

`extract_csv.py` uses **tuples** for the first time, and puts them inside
dicts, sets and another tuple. Its type hint
(`tuple[dict[int, tuple[str, str]], ...]`) looks like a tongue-twister, but
it's only three small pieces.

**What a tuple is.** A fixed group of values that belong together, in
brackets. Think of it as a **card with boxes**: the number of boxes never
changes, and each box means something by its **position**:

```python
card = ("2026-08-27T15:35:35Z", "peitongshi")
card[0]    # "2026-08-27T15:35:35Z"  ← the time
card[1]    # "peitongshi"            ← the name
```

It's like a list, but it **can't be changed** once created.

**The script's three structures, with real data:**

| Structure | What it is | Example | Type hint |
|---|---|---|---|
| `actors` | Dict: `id` → *(time, name)* card | `{321725054: ("2026-08-27T15:35:35Z", "peitongshi"), ...}` | `dict[int, tuple[str, str]]` |
| `repos` | Same as `actors`, for repos | `{1348625135: ("...", "peitongshi/niulai-chinese"), ...}` | `dict[int, tuple[str, str]]` |
| `pairs` | Set of *(actor_id, repo_id)* cards: **one card = one connection** | `{(321725054, 1348625135), (19, 1310070394), ...}` | `set[tuple[int, int]]` |

- In `actors` and `repos`, the **time** is kept next to the name so the
  most recent name can be chosen.
- In `pairs`, the **set** is what stops connections from repeating: if the
  same card is added ten times, it's kept only once.
- Why tuple-cards and not lists inside the set? A set only accepts items
  that **can't change** (if they changed after going in, it couldn't tell
  whether they're duplicates). Tuples don't change; lists do. That's why
  `(19, 1310070394)` works and `[19, 1310070394]` doesn't.

**The big card.** A function can only return **one** thing. To return
four, `extract()` puts them in a four-box tuple, and `main()` opens it and
spreads the boxes into four variables:

```python
return actors, repos, pairs, skipped_bot_events                    # in extract()
actors, repos, pairs, skipped_bot_events = extract(args.file)      # in main()
```

**The type hint, read piece by piece:**

```python
-> tuple[                               # returns a card with 4 boxes:
    dict[int, tuple[str, str]],         #   1. actors: id → (time, name)
    dict[int, tuple[str, str]],         #   2. repos:  id → (time, name)
    set[tuple[int, int]],               #   3. pairs:  set of (actor_id, repo_id)
    int,                                #   4. skipped_bot_events: a number
]
```

In short: there are only **two kinds of small card**, *(time, name)* and
*(actor, repo)*, and **one big card** that groups the four things so they
can be returned together. The [annotated copy](extract_csv.py) has the same
picture right above `extract()`.


## Loading Stage (load_postgres.py and load_neo4j.py)

With the three CSVs prepared by `extract_csv.py`, the next step is to **fill
both databases** with them. Two scripts do it, one per database, reading
**exactly the same files**:

| Script | Loads the CSVs into | In which language |
|---|---|---|
| `load_postgres.py` | PostgreSQL, `gharchive` database | SQL |
| `load_neo4j.py` | Neo4j, `gharchive` database | Cypher |

They're separate because each database has its own language and its own
way of loading data, and so that if one load fails, just that one can be
repeated.

### What gets created in each database

| Concept | PostgreSQL | Neo4j |
|---|---|---|
| Actor | `actor` table (`id` BIGINT, `login` TEXT) | `:Actor` nodes (`id`, `login`) |
| Repo | `repo` table (`id` BIGINT, `name` TEXT) | `:Repo` nodes (`id`, `name`) |
| Connection | `actor_repo` table (`actor_id`, `repo_id`) | `(:Actor)-[:INTERACTED_WITH]->(:Repo)` edges |
| Unique identifier | `PRIMARY KEY` on `actor.id` and `repo.id` | `UNIQUE` constraint on `Actor.id` and `Repo.id` |
| No repeated connections | `PRIMARY KEY (actor_id, repo_id)` | Guaranteed by the CSV, which already has no repeated pairs |
| Connections point at something that exists | `REFERENCES` (foreign keys) | Each edge is created by first **finding** its two nodes |

A few details:

- **Ids are numbers on both sides:** `BIGINT` in PostgreSQL and integers in
  Neo4j. A CSV is text, so `load_neo4j.py` converts the ids to numbers
  before sending them. If one side stored them as text and the other as
  numbers, the data wouldn't be truly identical.
- **`BIGINT`, not `INTEGER`:** an `INTEGER` goes up to about 2,100 million,
  and some GitHub ids already go beyond that.
- **`login` isn't unique**, because of the two `Copilot` accounts seen in
  the Extraction Stage.
- **Why the edge is called `INTERACTED_WITH`** and not something like
  "contributed to": connections come from every kind of event (pushes,
  comments, stars...), and starring or commenting isn't contributing. A
  neutral name is more accurate.

### Indexes: each side's "normal aids"

**What an index is.** An index is an extra structure the database keeps
**alongside** a table, to find rows **without reading them all**. It works
like the alphabetical index at the back of a book: to find the word
"recursion" in an 800-page book, instead of reading all 800 pages, you look
it up in the index (it's sorted alphabetically, so it's found at once) and
see it's on page 312. The index doesn't contain the book: it contains
**each word and where to find it**.

A database works the same way. For example, the index on `actor.id` keeps
**every `id`, sorted, and where its row is** on disk:

- **Without an index**, to find actor `321725054`, PostgreSQL would have to
  read all 14,515 rows of `actor` one by one and compare each `id`. That's
  a **sequential scan**.
- **With an index**, it goes straight to the row. That's an **index scan**.

Internally, PostgreSQL organises its indexes as a **B-tree**, a structure
that finds a value in **very few steps** even when the table has millions
of rows. Exactly how it works, with a step-by-step example, is explained
further down, in "What an index is, in more depth".

**What an index costs:** it takes up disk space, and every time a row is
inserted the table's indexes have to be updated too, so loads are a bit
slower. That's why not every column gets an index — only the ones used to
**look things up** or to **join tables**. (The "Key concepts" part just
below explains it in more detail, with `EXPLAIN`
examples.)

The design principle ("query-first") set a rule: give each side **its
normal aids, no more and no less**. For PostgreSQL, that means these
indexes:

| Index | How it's created | What it's for in the walk |
|---|---|---|
| `actor.id` | Automatically, by the `PRIMARY KEY` | Finding an actor by id instantly |
| `repo.id` | Automatically, by the `PRIMARY KEY` | Finding a repo by id instantly |
| `(actor_id, repo_id)` | Automatically, by `actor_repo`'s `PRIMARY KEY` | **Actor → their repos**: since `actor_id` comes first, it works for looking up by actor |
| `repo_id` | By hand: `CREATE INDEX actor_repo_repo_id_idx` | **Repo → its actors**: the opposite direction, which the previous index doesn't cover |

**Why the primary key's index doesn't work in both directions, and a
second index is needed: step by step**

**1. The traversal uses `actor_repo` in two different directions.** The
benchmark's traversal, `actor → repo → actor → repo`, alternates two
different questions at each hop:

| Hop | Question | Lookup in `actor_repo` |
|---|---|---|
| actor → repo | "Which repos has **this actor** made events in?" | The rows with `actor_id = X` |
| repo → actor | "Which actors have made events in **this repo**?" | The rows with `repo_id = Y` |

They're two lookups **by different columns** of the same table. The first
searches by `actor_id`; the second, by `repo_id`.

**2. An index is a sorted list, and it's only sorted one way.**
As explained further down ("What an index is, in more depth"), an index is
a **sorted** copy of the values, and thanks to that order you can search
"by halving", in very few steps. The primary key's index,
`(actor_id, repo_id)`, stores **pairs** sorted **first by
`actor_id`** and, when the `actor_id` is the same, by `repo_id`. Seen with
real data from the benchmark, the index looks like this (each line is a
row of `actor_repo`, in the index's order):

```
position   actor_id     repo_id
     1           19     1310070394
     2           19     1347511170
   ...
   384      1247371      444497690   ← LedgerHQ/ledger-live
   ...
  1884     33897120      444497690   ← LedgerHQ/ledger-live
   ...
  4652    175728472      ...         ← Copilot: its 1st row
  4653    175728472      ...         ← Copilot
   ...                                  (24 consecutive rows)
  4655    175728472      444497690   ← Copilot, in LedgerHQ/ledger-live
   ...
  4675    175728472      ...         ← Copilot: its last row
   ...
  5653    224024782      444497690   ← LedgerHQ/ledger-live
   ...
 15053          ...      ...
```

**3. Searching by actor: the rows are together.** For "which repos has
`Copilot` (`actor_id` 175728472) made events in?", PostgreSQL searches the
index "by halving" until it reaches that actor's **first** row (number
4,652) and, from there, **reads straight through** until the `actor_id`
changes (number 4,675). Since the index is sorted by `actor_id`, all the
rows of the same actor are **together**: 24 consecutive rows. Going down
the tree once and reading one continuous chunk: very fast.

**4. Searching by repo: the rows are scattered everywhere.** For
"which actors have made events in `LedgerHQ/ledger-live` (`repo_id`
444497690)?", the rows you're after are at positions **384, 1,884,
4,655 and 5,653**: scattered across the whole table, each one next to other
repos of its actor. The index is sorted by `actor_id`, **not** by
`repo_id`, so:

- **you can't search "by halving"**: if you open the index in the middle and
  find `repo_id` 1347511170, that doesn't tell you whether 444497690 is
  before or after, because the `repo_id`s don't follow any order along
  the index;
- **you don't know when to stop**: even if you find one row of the repo,
  there may be others anywhere else.

The only way to find them all is to **read all 15,053 rows** and keep
the ones with that `repo_id`. It's the difference between looking up in a
phone book everyone with the surname "Smith" (they're together) and
everyone named "Ana" (they're scattered throughout the book, and you
have to read the whole thing).

**5. The leftmost-prefix rule.** This is a general rule of
composite indexes: an index on `(A, B)` works for searching by `A`, or
by `A` and `B` together, but **not** for searching by `B` alone. It only
works if the search starts with the index's **first column** (its "leftmost
prefix"). That's why the order of the columns in a composite index
matters.

**6. The solution: a second index, sorted by `repo_id`.** The index
`actor_repo_repo_id_idx` is another sorted list of the same table, this
time by `repo_id`. In it, the 4 rows of `LedgerHQ/ledger-live` are
**together**, just as the rows of `Copilot` were together in the first one:

```
index actor_repo_repo_id_idx (sorted by repo_id)
   ...
   444497690   → row with actor_id 1247371     ┐
   444497690   → row with actor_id 33897120    │ the 4 rows of LedgerHQ/ledger-live,
   444497690   → row with actor_id 175728472   │ now together
   444497690   → row with actor_id 224024782   ┘
   ...
```

With the two indexes, **each direction of the traversal has its own sorted
list**, and both hops are equally fast. It's like having two phone
books for the same city: one sorted by surname and the other by first
name.

**7. How to see it with your own eyes.** With `EXPLAIN` in front of a
query, PostgreSQL shows which index it uses:

```sql
-- An actor's repos: uses the primary key's index
EXPLAIN SELECT repo_id FROM actor_repo WHERE actor_id = 175728472;
--   ... Index ... using actor_repo_pkey on actor_repo ...

-- A repo's actors: uses the index created by hand
EXPLAIN SELECT actor_id FROM actor_repo WHERE repo_id = 444497690;
--   ... Index ... using actor_repo_repo_id_idx on actor_repo ...
```

Without the second index, the second query would show `Seq Scan on
actor_repo`: a sequential scan, that is, reading the whole table.

**8. Why it matters so much in the benchmark.** In a multi-hop
traversal, the repo → actor lookup isn't done once, but **once for
each repo** coming from the previous hop. Without the second index, each
of those lookups would read the whole table: with 100 repos in a hop, that
would be 100 reads of the 15,053 rows (or of the 424,098 rows of the 24-hour
pipeline). PostgreSQL would come off far, far worse, but not because the
relational model is worse, but because **it would be missing a normal aid**
that any sensible design would have.

**What about Neo4j?** It doesn't have this problem, and it doesn't need an
index for either direction: each edge is stored **next to its two nodes**,
so a `Repo` node already knows which edges come into it, just as an `Actor`
node knows which ones go out of it. Following an edge "forwards" or
"backwards" costs the same. Giving PostgreSQL its second index is what makes
the comparison **fair**: each database, with its normal tools.

**Why not a single index on `repo_id`, instead of the primary key's
one?** Because then the problem would be the reverse: an actor's rows
would be scattered, and the actor → repo hop would be the slow one. Besides,
the primary key is needed anyway, to prevent repeated pairs. With one index
for each direction, both hops are covered.

**In Neo4j**, the uniqueness constraints on `Actor.id` and `Repo.id` build
their index, just like primary keys. The edges, on the other hand, **don't
need an index**: in a graph, every node already stores direct links to its
own edges (*index-free adjacency*).

> 🎯 **The central idea of the whole project:** that difference — **indexes
> to join tables** (PostgreSQL) versus **direct links between nodes**
> (Neo4j) — is **exactly what the benchmark wants to measure**. At heart,
> the research question asks at what number of hops, and at what data
> volume, one way of finding connections starts to beat the other.

**`ANALYZE`.** At the end of the load, `load_postgres.py` runs `ANALYZE` on
the three tables. Before running each query, PostgreSQL decides *how* to do
it (use an index or read the whole table? which table first?), and to
decide well it uses statistics about the data. Right after a bulk load
those statistics are out of date, and `ANALYZE` refreshes them. It's also
part of the relational side's normal aids.

### Key concepts: indexes, primary keys, foreign keys, and why a graph doesn't need them

This part expands on the **"What gets created in each database"** table
and the explanation of indexes just above: what exactly each thing is,
whether there are indexes or not, and why the graph works differently.
These are the project's core concepts, because the research question is
precisely **how each database finds the connections**.

#### First, the short answer: are there indexes, or are primary keys enough?

**There are indexes.** A `PRIMARY KEY` isn't an alternative to an index:
**PostgreSQL automatically creates an index** for every primary key,
because it needs one to check, on every insert, that the value isn't
repeated. But primary keys **don't cover every lookup**, and foreign keys
**don't create any index** in PostgreSQL. That's why there's one more
index, created by hand.

This is everything that exists in each database (it's the same in
`gharchive` and in `gharchive24h`):

| Structure | Database | How it's created | Does it create an index? | What it's for |
|---|---|---|---|---|
| `actor`'s `PRIMARY KEY` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Yes, automatically:** `actor_pkey` | No two actors with the same `id`, and finding an actor by its `id` instantly |
| `repo`'s `PRIMARY KEY` (`id`) | PostgreSQL | `id BIGINT PRIMARY KEY` | **Yes, automatically:** `repo_pkey` | The same, for repos |
| `actor_repo`'s `PRIMARY KEY` (`actor_id`, `repo_id`) | PostgreSQL | `PRIMARY KEY (actor_id, repo_id)` | **Yes, automatically:** `actor_repo_pkey` (composite, two columns) | No pair is repeated, and looking up **an actor's repos** |
| Foreign key `actor_repo.actor_id` → `actor.id` | PostgreSQL | `REFERENCES actor (id)` | **No** | Every connection points at an actor that exists |
| Foreign key `actor_repo.repo_id` → `repo.id` | PostgreSQL | `REFERENCES repo (id)` | **No** | Every connection points at a repo that exists |
| Index on `actor_repo.repo_id` | PostgreSQL | `CREATE INDEX actor_repo_repo_id_idx` (by hand) | **Yes:** it is the index itself | Looking up **a repo's actors**: the direction the primary key doesn't cover |
| `UNIQUE` constraint on `Actor.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE a.id IS UNIQUE` | **Yes, automatically** | No two actors with the same `id`, and finding an actor by its `id` instantly |
| `UNIQUE` constraint on `Repo.id` | Neo4j | `CREATE CONSTRAINT ... REQUIRE r.id IS UNIQUE` | **Yes, automatically** | The same, for repos |
| The `INTERACTED_WITH` edges | Neo4j | `CREATE (a)-[:INTERACTED_WITH]->(r)` | **Don't need an index** | Every node stores direct links to its edges (see below) |

**Summary:** PostgreSQL has **4 indexes** (three automatic ones from the
primary keys and one by hand), and Neo4j has **2** (the constraints' ones).
The graph's connections have no index because they don't need one: that
difference is the heart of the benchmark.

**How to check it yourself:**

```sql
-- PostgreSQL (pgAdmin Query Tool, gharchive database): the indexes of the three tables
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE tablename IN ('actor', 'repo', 'actor_repo')
ORDER BY tablename, indexname;
```

```cypher
// Neo4j (Query, gharchive database): the constraints and the indexes
SHOW CONSTRAINTS;
SHOW INDEXES;
```

In pgAdmin you can also see them in the tree: inside each table, **Indexes**
(the indexes) and **Constraints** (the primary and foreign keys). In Neo4j,
`SHOW INDEXES` also shows two indexes that Neo4j always creates on its own
(of type `LOOKUP`), which are used to quickly find "all nodes with a label"
or "all edges of a type".

#### What an index is, in more depth

The basics (the book analogy, and sequential scan versus index scan) are
explained just above, in "Indexes". This goes one step further: how an
index is built inside, what it costs, and how PostgreSQL decides whether to
use it.

**First, the basics: the warehouse and the boxes.** To understand how an
index works inside, you need a few very basic concepts. They're all
explained with **a single picture** that doesn't change: **a warehouse full
of boxes**. We'll go up one step at a time.

**Step 1: memory and disk.** A computer keeps data in two places:

| | **Memory (RAM)** | **Disk** |
|---|---|---|
| Speed | Very fast | Much slower |
| Is it erased when you power off? | **Yes** | **No**: it's permanent |
| In the warehouse it would be... | **Your desk**: what you have in front of you, at hand | **The warehouse**: where everything is stored, but you have to go and fetch it |

A database keeps its data **on disk**, so it isn't lost when the power
goes off. But to work with it, it has to **bring it into memory**, like
taking something out of the warehouse and putting it on your desk.

**Step 2: data lives in files.** On disk, everything is stored in
**files**, just like the project's CSVs or scripts. A PostgreSQL table,
for example `actor`, **is a file** on disk, with all its rows. In the
warehouse it would be **a shelf**: the "actor" shelf, with all the actors.

**Step 3: the disk is read box by box.** Going to the warehouse is
**slow**. So when you go, you don't bring back a single sheet of paper:
**you bring back the whole box** it's in, because the trip costs the same.
That's why PostgreSQL doesn't read rows one at a time: it splits each file
into **fixed-size blocks** (8 KB) and always reads or writes **a whole
block**. That block is called a **page**.

> **Page = a box in the warehouse.** They're all the same size. Each one
> holds several rows (in `actor`, about 150).

The `actor` table, with 14,515 rows, takes up about **a hundred boxes**.
What's slow, and what needs saving, is **the number of boxes you have to
bring from the warehouse**.

**Step 4: searching without an index.** To find actor `321725054`: the
boxes on the "actor" shelf **aren't sorted**, so there's no way to know
which one it's in. You have to **bring all hundred boxes, one by one**, and
look inside each one. That's the **sequential scan** (*Seq Scan*).

**Step 5: the index is ANOTHER shelf.** To avoid having to look at every
box, **another shelf** is created: the one for the `actor_pkey` index. Its
boxes don't hold the full rows, only **a sorted list of the `id`s**, and
next to each one, **which box on the "actor" shelf holds its row**:

```
INDEX shelf (sorted)                         TABLE shelf "actor" (unsorted)
   index box:                                   box 93:
   ...                                          ...
   321,725,054 → "box 93 of the table" ──────►  id=321725054, login='peitongshi'
   ...                                          ...
```

The index **is also made of boxes** (pages). That's why there are "index
pages" and "table pages": **they're boxes on two different shelves**.

**Step 6: the index has a "guide" box on top.** The sorted list of the
14,515 `id`s doesn't fit in a single box: it takes up about 37. How do you
know **which of those 37** to open without looking at them all? **One more
box is added, the guide box**, which only says what each of the others
contains:

```
GUIDE BOX (top)
   "ids up to 300,000,000               → box 24 of the index"
   "ids from 300,000,001 to 330,000,000 → box 25 of the index"
   ...
            │
            ▼
LIST BOXES (bottom): box 24, box 25, box 26...  (37 boxes)
   box 25:  "321,725,054 → box 93 of the table"
```

**Step 7: the technical names.** Now, and only now, the names used in the
rest of this section:

| What we've seen | Technical name |
|---|---|
| A box (on any shelf) | **page** |
| The guide box on top, in the index | **root** |
| The list boxes, at the bottom, in the index | **leaves** |
| The boxes on the table's shelf | **table pages** |

So looking up `321725054` means **bringing 3 boxes**: the guide box (the
root), box 25 of the index (a leaf) and box 93 of the table. Instead of
bringing all hundred boxes of the table.

**To see it for real.** PostgreSQL can tell you how many boxes each shelf
takes up. In pgAdmin's Query Tool, with the `gharchive` database:

```sql
SELECT pg_relation_size('actor')      / 8192 AS boxes_in_table,
       pg_relation_size('actor_pkey') / 8192 AS boxes_in_index;
```

(`pg_relation_size` gives the size in bytes; divided by 8,192, which is
8 KB, it gives the number of pages.)

With this foundation, the rest of the section explains the same tree in
more detail: why it works so fast, how it grows and what it costs.

**How it's built inside: the B-tree.** To understand it you need three
ideas, one after another.

**Idea 1: searching in something sorted is much, much faster.** Think of
the "guess the number from 1 to 100" game, where the only answers you get
are "higher" or "lower". If you ask number by number (1, 2, 3...), you may
need 100 questions. But if you always ask for the middle
("50?" → "higher"; "75?" → "lower"; "62?"...), each question
**rules out half** of what's left, and you find it in **7 questions
at most**. That only works because the numbers are **sorted**.

| Sorted values | "Halving" questions, at most |
|---|---|
| 100 | 7 |
| 1,000 | 10 |
| 1,000,000 | 20 |

A table without an index is like an **unsorted** list: there's no choice
but to look row by row. An index is, above all, **a sorted copy of the
values of a column**, each one with the address of its row.

**Idea 2: the disk is read in pages, not in values.** A database doesn't
read data one value at a time: it reads it from disk in fixed-size blocks
called **pages** (in PostgreSQL, 8 KB each). Reading a page from disk is
much, much slower than comparing two numbers in memory. So what really
needs saving isn't comparisons, but **pages read**. A page can hold
**hundreds** of numbers like our `id`s (roughly 400).

**Idea 3: the B-tree combines the two ideas.** It's a sorted list
spread across pages and organized **in levels**, like an upside-down
tree:

- **The leaves** (the bottom level): pages with the sorted values and,
  next to each one, **the address of its row** in the table (which page
  of the table it's on). Each leaf is linked to the next one, so ranges
  can be read in sequence.
- **The root** (at the top) **and the intermediate levels**: pages that
  don't store rows, but **"signposts"**, like the signs in an airport:
  "`id`s up to 300,000,000, this way; from 300,000,001 to 330,000,000,
  that way".

Looking up a value means **going down** from the root, following the
signposts, to the right leaf. An example with the benchmark's `actor`
table (14,515 `id`s, about 37 leaves of about 400 `id`s each; the signpost
and page numbers are made up, just to illustrate it):

```
Look up actor 321725054:

  1. Root (1 page read):
     [ ... | up to 300,000,000 → leaf 24 | up to 330,000,000 → leaf 25 | ... ]
                                              │
                                              ▼
  2. Leaf 25 (1 page read):
     [ ... 321,700,991 → row on page 81 | 321,725,054 → row on page 93 | ... ]
                                                        │
                                                        ▼
  3. Table actor, page 93 (1 page read):
     id = 321725054, login = 'peitongshi'
```

**Three pages read**, versus reading every page of the table
(around a hundred for 14,515 rows) without an index. And inside each page, the
search for the exact value is done by "halving", like in the game.

**Pages and leaves, with the warehouse picture.** The diagram shows
"root", "leaf 25" and "page 93". All three are **boxes** (pages) that have
to be brought from the warehouse; the only thing that changes is **which
shelf they're on and what they hold**, as seen in "First, the basics":

| Page type | Which shelf is it on? | What does it hold? |
|---|---|---|
| **Root** (the guide box) | The **index**'s (there's only one, on top) | Signposts: "up to 300,000,000 → leaf 24..." |
| **Intermediate page** | The **index**'s (between the root and the leaves; only in trees with 3 or more levels) | More signposts, more detailed |
| **Leaf** (a list box) | The **index**'s (at the bottom) | Each value, sorted, with the address of its row: "321,725,054 → row in page 93" |
| **Table page** | The **table**'s | The **full rows**: `id = 321725054, login = 'peitongshi'` |

The first three make up the **index**; the last one is the **table**.

**They're two separate "files".** PostgreSQL stores two separate things
on disk, and both are made of pages:

```
THE INDEX (actor_pkey)                       THE TABLE (actor)
made of pages, organized as a tree           made of pages, with the rows
                                             (in no particular order)
  [ root ]            ← index page
     │
  [ leaf 24 ][ leaf 25 ][ leaf 26 ]...       [ page 1 ][ page 2 ]...[ page 93 ]...
              ← index pages                       ← table pages
              (the bottom-level ones)
                   │                                                     ▲
                   └── "321,725,054 → row on page 93" ───────────────────┘
```

So, in the lookup drawing:

- **"Root"** is a page **of the index** (the top one).
- **"Leaf 25"** is another page **of the index**: number 25 of the ones at
  the bottom of the tree.
- **"Page 93"** is a page **of the table**: it's not part of the tree, and
  it's where the actual row is.

All three are 8 KB pages, which is why they count as "three pages
read". What changes is **what's inside each one and what it's for**.

**Why the index doesn't store the complete row.** The leaf only stores the
**value** (`321725054`) and **where its row is**, not the whole row (the
`login` and the rest of the columns), for two reasons: that way the index
is **small** (about 400 values fit per leaf, and the tree has few
levels), and the row is already in the table, so repeating it would
duplicate the data. That's why, after reaching the leaf, **one more step**
is needed: going to page 93 of the table to fetch the row.

**When that last step isn't needed: `Index Only Scan`.** If everything the
query asks for is already **inside the index**, PostgreSQL answers without
opening any page of the table. For example,
`SELECT repo_id FROM actor_repo WHERE actor_id = 175728472` only asks for
`repo_id` and filters by `actor_id`, and both columns are already in the
leaves of the `(actor_id, repo_id)` index. With `EXPLAIN`, PostgreSQL shows
it as `Index Only Scan using actor_repo_pkey`: the "Only" means "only the
index". An index that contains everything a query needs is called a
**covering index** (it **covers the query**).

**Why the number of steps grows so slowly.** This is the most
important part of the B-tree, and it's easiest to understand with a miniature tree.

**Step 1: a small, toy tree.** Imagine that each page can only hold
**3 values** (in reality about 400 fit, but with 3 it can be
drawn). Each slot in the root is a signpost that leads to a page on the
level below:

```
Level 1 (root):        [  A  |  B  |  C  ]                       1 page
                         │     │     │
                ┌────────┘     │     └────────┐
                ▼              ▼              ▼
Level 2:   [ 1 | 2 | 3 ]  [ 4 | 5 | 6 ]  [ 7 | 8 | 9 ]           3 pages
```

- With **1 level** (just the root), **3** values fit.
- With **2 levels**, each of the root's 3 signposts leads to a page
  with 3 values: **3 × 3 = 9** values fit.
- With **3 levels**, each of those 9 slots would lead to another page of 3:
  **9 × 3 = 27** fit.
- With 4 levels, **27 × 3 = 81**. With 5, **243**...

Each new level **multiplies** what fits by 3, because each slot on the
level above "opens" a whole page on the level below. It's like a
family tree: each generation multiplies the number of people.

**Step 2: looking up a value costs "one page per level".** To find
the 8 in the drawing, you read the root (1 page), pick the signpost `C` and
read that level-2 page (another page). **Two levels, two pages
read**, even though there are 9 values. With 3 levels it would be three pages, even though
there are 27 values. The number of pages you have to read **is the number of
levels**, not the number of values.

**Step 3: the same thing, with real pages.** A real PostgreSQL page
holds about **400** `id`s, not 3. So each level multiplies by
**400**:

| Tree levels | How many values fit | Calculation | In this project |
|---|---|---|---|
| 1 (just the root) | about 400 | 400 | — |
| 2 | about 160,000 | 400 × 400 | the benchmark's `actor`: 14,515 rows → **fit in 2 levels** |
| 3 | about 64 million | 160,000 × 400 | the 24-hour pipeline's `actor_repo`: 424,098 rows → **3 levels** |
| 4 | about 25.6 billion | 64 million × 400 | more than everyone on the planet |

And since each lookup reads **one page per level**:

| Table rows | Pages read **without** an index (reading the whole table) | **Index** pages read (one per level) |
|---|---|---|
| 14,515 (benchmark) | every page of the table: around a hundred | **2** |
| 424,098 (24-hour pipeline) | every page of the table: about two thousand | **3** |
| 64 million | hundreds of thousands | **3** |
| 25 billion | more than a hundred million | **4** |

(On top of that comes one more page, to read the row in the table, as in the
earlier drawing: **3 pages in total** for the benchmark.)

**Step 4: the conclusion.** Going from the benchmark (14,515 rows) to the
24-hour pipeline (424,098 rows) means having **almost 30 times more data**,
but looking up a value only costs **one more level**: one more page to
read, from 2 to 3. Without an index, on the other hand, the work would be multiplied by 30.

**Linear versus logarithmic (the two ways of growing).** There are two ways
for the work to grow when the data grows:

- **Linear:** if the data is multiplied by 30, the work is also
  multiplied by 30. That's what happens when reading the whole table (without an index): twice
  the rows, twice the work.
- **Logarithmic:** if the data is multiplied by 400, the work only
  **adds 1** (one more level). That's what happens with the B-tree. The
  **logarithm** answers the question "how many times do I have to
  multiply by 400 to reach this number of rows?", and that is
  exactly the number of levels: for 14,515, 2 times is enough (400 ×
  400 is already more than 14,515); for 424,098, it takes 3.

That's why indexes are so powerful on large tables: the data can
grow enormously, and the cost of finding a value barely changes.

**One more detail: memory.** Reading from **disk** is slow; reading from
**memory** (RAM) is much, much faster. The root and the upper levels
are used in **every** lookup, so PostgreSQL usually keeps them
**in memory** (this is called **caching**). In practice,
many lookups only have to go to disk for the leaf and the row, or not
even that, if those were also in memory.

**Why it's called "B" and why it's always "balanced":** the "B" doesn't
stand for "binary" (each page has hundreds of branches, not two). What
matters is that the tree is always **balanced**: all the leaves are at
the **same depth**, so every lookup costs the same. To keep it that way,
when a value is inserted into a leaf that's already full, the database
**splits it in two** and adds a new signpost to the level above. That
extra work on every insert is one of the reasons why indexes make loads
slower (see the next section).

**A composite index is the same thing, sorted by pairs.** The index
`(actor_id, repo_id)` is just the same kind of B-tree, but its values are
**pairs**, sorted first by `actor_id` and, when those are equal, by
`repo_id`. That's why all the rows of the same actor end up **together in
the leaves** (you find them by going down once and reading in sequence),
while those of the same repo end up **scattered** across all the leaves.
It's the phone book from above, seen from the inside.

**What an index costs.** It isn't free:

- **Space:** it's one more structure, stored on disk.
- **Slower writes:** every time a row is inserted, the database also has to
  update every index on that table. That's why, in the 24-hour pipeline (further down in these notes),
  loading `actor_repo` (with two indexes and two foreign keys) took 27
  seconds, and `actor` or `repo` (with a single index) barely one.

That's why you don't put an index on every column: only on the ones used to
**look things up** or to **join tables**. It's the "query-first" principle
applied to indexes: `login` and `name` have no index because the benchmark
queries don't look things up by them.

**The planner decides whether to use the index.** An index existing doesn't
force it to be used. Before running each query, PostgreSQL works out what's
cheaper (hence the importance of `ANALYZE`, which gives it the statistics to
work it out). To see what it decided, put `EXPLAIN` in front of the query:

```sql
EXPLAIN SELECT * FROM actor WHERE id = 321725054;
-- Index Scan using actor_pkey on actor ...     <- uses the primary key's index

EXPLAIN SELECT * FROM actor WHERE login = 'peitongshi';
-- Seq Scan on actor ... Filter: (login = ...)  <- no index: reads the whole table
```

(In Neo4j, the equivalent is putting `EXPLAIN` or `PROFILE` in front of a
Cypher query.)

#### What a primary key is

The **primary key** is the column (or group of columns) that **uniquely
identifies each row**, like a person's ID card number. It has three rules
that the database itself enforces:

1. **Unique:** there can't be two rows with the same value.
2. **Never empty** (`NOT NULL`): every row has to have one.
3. **Only one per table**, although it can be made up of several columns.

**In this project:**

- In `actor` and `repo`, the primary key is the GitHub `id`. It's a
  **natural key**: an identifier that already comes in the data, not one we
  invented (that would be a *surrogate key*, like a running number 1, 2,
  3...). The `id` was chosen instead of the name because the name can
  change (the `lucky521-png` → `peitongshi` case) and isn't unique (the two
  `Copilot` accounts).
- In `actor_repo`, the primary key is **composite**: the **pair**
  `(actor_id, repo_id)`. Neither column is unique on its own (an actor can
  be in many repos, and a repo can have many actors), but the pair is. It's
  the database itself that enforces the "only one connection per
  actor–repo pair" decision.

**Why it matters:**

- **Identity:** every row can be pointed at without ambiguity.
- **No duplicates:** the database rejects any insert that repeats a key,
  even if the mistake is in our code.
- **Target of the foreign keys:** it's the value the connections point at
  (see below).
- **Fast lookup:** its automatic index lets you find a row by its key
  instantly.

**The composite index** on `actor_repo` is sorted by `actor_id` first and
then by `repo_id`. That's why it works for finding an actor's repos but not
a repo's actors, and the extra index on `repo_id` was needed (see the table
of the walk's two directions and the phone-book analogy, above).

#### What a foreign key is

A **foreign key** is a column that **points at another table's primary
key**. In `actor_repo`:

- `actor_id` points at `actor.id`;
- `repo_id` points at `repo.id`.

This is how a relational database **represents relationships**:
`actor_repo` doesn't store the actor or the repo, only their `id`s, as
"references". It's a **junction table**, the standard way to represent a
**many-to-many** relationship (an actor can have many repos, and a repo
many actors).

**What it's for: referential integrity.** The database guarantees that
**every reference points at something that exists**:

- You can't insert a connection into `actor_repo` with an `actor_id` that
  isn't in `actor`: PostgreSQL rejects it. (That's why `load_postgres.py`
  loads `actor` and `repo` **before** `actor_repo`.)
- You can't delete an actor from `actor` while some connection points at
  it, unless you say explicitly what to do with those connections (for
  example, `ON DELETE CASCADE`, which would delete them too). That's why
  `load_postgres.py` drops `actor_repo` **before** the other two.

Without foreign keys, a bug in the code could leave "orphaned" connections,
pointing at actors or repos that don't exist, and the walks would give
false results without anyone noticing.

**What it costs:** on every insert into `actor_repo`, PostgreSQL checks
that the actor **and** the repo exist, that is, **two lookups per row**.
It's another of the reasons that table takes longer to load.

**Watch out: a foreign key doesn't create an index** (in PostgreSQL). It's
a very common mistake to think it does. The foreign key checks that the
reference exists, but it **doesn't** speed up lookups on that column. If a
column is used to join tables, it has to be indexed separately, as we did
with `repo_id`. (`actor_id` doesn't need it because it already comes first
in the composite primary key's index.)

#### Primary key, normal index and foreign key: three tools, three jobs

When reading the schema in `load_postgres.py` it's easy to mix up these
three pieces, because they sometimes show up on the same column. Each one
does **a different job**:

| | Primary key (`PRIMARY KEY`) | Normal index (`CREATE INDEX`) | Foreign key (`REFERENCES`) |
|---|---|---|---|
| Does it find rows fast? | ✅ Yes: it creates an index automatically | ✅ Yes: **that's what it's for** | ❌ No: **it doesn't create any index** |
| Does it force the value to be unique? | ✅ Yes | ❌ No: **it allows repeated values** | ❌ No |
| Does it force the value not to be empty? | ✅ Yes (`NOT NULL` included) | ❌ No | ❌ No (on our columns the separate `NOT NULL` does it) |
| Does it check that the value exists in another table? | ❌ No | ❌ No | ✅ Yes: **that's what it's for** |
| How many per table? | Only **one** (though it can span several columns) | As many as needed | As many as needed |

In one sentence: **the primary key identifies and finds; the index only
finds; the foreign key only checks**.

**All three on `actor_repo`, column by column:**

| Column | Foreign key | Primary key | Index that makes it fast |
|---|---|---|---|
| `actor_id` | ✅ Points at `actor.id` | **Part** of the pair `(actor_id, repo_id)` | The primary key's (`actor_id` comes first) |
| `repo_id` | ✅ Points at `repo.id` | **Part** of the pair `(actor_id, repo_id)` | `actor_repo_repo_id_idx`, the normal index created by hand |

Neither of the two columns is a primary key **on its own**. The primary
key is the **pair**, and what can't be repeated is the whole pair:

| `actor_id` | `repo_id` | Allowed? |
|---|---|---|
| 175728472 (Copilot) | 444497690 (LedgerHQ/ledger-live) | ✅ |
| 1247371 | 444497690 (LedgerHQ/ledger-live) | ✅ The `repo_id` repeats, but it's a different pair |
| 175728472 (Copilot) | 873328 (getsentry/sentry) | ✅ The `actor_id` repeats, but it's a different pair |
| 175728472 (Copilot) | 444497690 (LedgerHQ/ledger-live) | ❌ **The pair already exists**: it would be a repeated connection |

**Why the `repo_id` index is a normal index and not a unique one.** The
same `repo_id` appears **many times** in `actor_repo`, once for each actor
that has made events in that repo (`LedgerHQ/ledger-live` appears 4
times). An index that forced `repo_id` to be unique would reject the
second row of every shared repo. That's why it's a **normal** index: it
only helps **find fast**, without imposing any rule. It's exactly what the
repo → actor hop needs.

**Why all three are needed at once.** Each one covers a gap the others
leave:

- Without the **primary key**, nothing would stop the same connection from
  being stored twice.
- Without the **foreign key**, nothing would stop a connection from being
  stored with an actor or a repo that doesn't exist.
- Without the **`repo_id` index**, the repo → actor hop would have to read
  the whole table.

(In Neo4j, as explained further down, these three needs are covered
differently: uniqueness constraints play the role of primary keys, and an
edge can't exist without its two nodes, so neither a foreign key nor an
index is needed to walk it.)

#### How a relationship is walked in a relational database: the JOIN

In a relational database, the connections **aren't stored as paths**:
they're **computed at query time**, with a **JOIN**, which pairs up rows
from two tables by a matching value.

For one hop (an actor's repos), the query is:

```sql
SELECT r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id     -- 1st join
JOIN repo r        ON r.id = ar.repo_id      -- 2nd join
WHERE a.id = 321725054;
```

What PostgreSQL does, step by step (thanks to the indexes):

1. It looks up actor `321725054` in the `actor_pkey` index.
2. It looks up all the rows with that `actor_id` in the `actor_repo_pkey`
   index: it gets their `repo_id`s.
3. For each `repo_id`, it looks up the repo in the `repo_pkey` index.

Every arrow in the walk is an **index lookup**, and every lookup has a cost
that depends (though only slightly, thanks to the B-tree) on the total size
of the table. For the benchmark walk (`actor → repo → actor → repo`), every
hop adds **more JOINs**, and every JOIN is done for **all** the rows coming
from the previous hop. If the number of rows grows at each hop, the work
grows very fast.

#### Why a graph has no primary or foreign keys

A graph database stores things differently:

| Relational concept | Equivalent in the Neo4j graph |
|---|---|
| Table (`actor`, `repo`) | **Label**: `:Actor`, `:Repo`. Groups nodes of the same kind |
| Row | **Node** |
| Column | **Property** (`id`, `login`, `name`) |
| Junction table + foreign keys (`actor_repo`) | **Edge** (*relationship*): `-[:INTERACTED_WITH]->`, stored as an object of its own that joins the two nodes |
| Primary key | Doesn't exist as such. You create a **uniqueness constraint** on a property (`id`) |
| JOIN | **Following the edge**: going from a node to its neighbors |

**Why foreign keys aren't needed:** in the graph, the connection **isn't a
value that points at another value** (an `actor_id` you have to look up in
another table). **It's an object of its own that directly joins the two
nodes**. An edge can't exist without its two ends: Neo4j doesn't allow
creating a "dangling" edge or deleting a node that still has edges (hence
the `DETACH DELETE` in `load_neo4j.py`, which deletes the edges first). In
other words, **referential integrity is built into the structure itself**,
with no need to declare it.

**Why there's no "real" primary key:** Neo4j identifies every node
internally with its own identifier (the *element id*), which **isn't** our
data and shouldn't be used as a business key, because it can be reused if
nodes are deleted. That's why we added the **uniqueness constraint** on our
`id` property: it plays the role of the primary key (no duplicates, fast
lookup by index), but it's optional and our choice.

**And most importantly: in the graph, the index is only used to find the
starting point.** Once the first node has been found (for example, actor
`321725054`, thanks to the uniqueness constraint), **no index is used any
more**: the walk follows the edges directly.

#### What's there instead: index-free adjacency

In Neo4j, **every node stores where its own edges are**, and every edge
stores **where its two nodes are**. Conceptually:

- a node's record points at its edges;
- an edge's record points at its start node, its end node, and the next
  edge of each of them.

(Recent versions of Neo4j physically organize the data differently,
grouping each node's edges together, but the idea is the same: a node's
connections are stored **with the node**.)

So going from an actor to their repos isn't "searching a table for all the
rows whose `actor_id` is X", but **"reading the list of edges the node
already has"**. It's like the difference between:

- **Relational:** searching the whole city's phone book for Ana's friends
  (a lookup, however fast, in a list of everyone).
- **Graph:** opening Ana's address book, which already has her friends
  written down (following links that are already there).

#### Why that optimizes (and why it has to be measured)

| | PostgreSQL (relational) | Neo4j (graph) |
|---|---|---|
| Finding the starting point | An index lookup (B-tree) | An index lookup (the constraint) |
| Each hop | A JOIN: one **index lookup** for every incoming row | **Following pointers** the node already has |
| Does a hop's cost depend on the **total** size of the database? | A little: the index grows with the table (though very slowly) | No: it depends only on **how many edges that node has** |
| What grows as hops are added | The number of JOINs and index lookups | The number of edges followed |

**The theory:** on **short** walks (one or two hops), PostgreSQL is very
fast, because its indexes are very efficient and it has spent decades
optimizing JOINs. On **long** walks, the graph should win, because its cost
depends only on the part of the graph being walked, not on the total size
of the tables.

**But it's only a hypothesis.** The B-tree needs very few steps even on
huge tables, both databases keep the most-used data in memory, and
PostgreSQL's planner is very good. **At what number of hops and with what
volume of data the winner changes** is exactly what this project wants to
**measure**, instead of taking it for granted.

#### Other concepts worth knowing

**Normalization.** It's the way of organizing tables so the same piece of
data isn't stored twice. For example, an actor's `login` is **only** in
`actor`, not repeated in every row of `actor_repo`. If it changed, it would
only have to be changed in one place. That's why the research question
talks about a **normalized** relational model: it's the "correct" way to
design the relational side, the one that would be used in practice.

**Cardinality of a relationship.** How many items on one side can be
related to how many on the other:

| Type | Example | How it's stored in relational |
|---|---|---|
| One-to-one | A person and their ID card | A unique foreign key |
| One-to-many | A repo and its *issues* (each issue belongs to a single repo) | A foreign key on the "many" side |
| **Many-to-many** | **Actors and repos (this project)** | **A junction table** (`actor_repo`) with two foreign keys |

In the graph, all three types are stored the same way: with edges.

**Constraint versus index.** A **constraint** is a **rule** the database
enforces (unique, not empty, the reference exists). An **index** is a
**structure for fast lookups**. They often go together (a primary key or a
uniqueness constraint creates an index so it can be checked), but they're
different things: a foreign key is a constraint **without** an index, and
`actor_repo_repo_id_idx` is an index **without** a constraint.

**Transactions and ACID.** A **transaction** is a group of changes that are
applied **all or nothing**. Both databases meet the **ACID** properties:
*Atomicity* (all or nothing), *Consistency* (the rules always hold),
*Isolation* (transactions don't step on each other) and *Durability* (what's
saved isn't lost even if the computer is switched off). That's why the
PostgreSQL load, which is a single transaction, never leaves data
half-loaded.

**The schema in each database.** PostgreSQL requires the tables, columns
and types to be defined **before** storing data (*schema-on-write*). Neo4j
is more flexible: you can create nodes with any property without declaring
it first; the constraints are optional and we add them ourselves to ensure
data quality and fast lookups.

**`EXPLAIN` and `PROFILE`: seeing how a query runs.** They'll matter in the
benchmark: it's not enough to know **how long** a query takes, but also
**why**.

- PostgreSQL: `EXPLAIN` shows the plan without running it; `EXPLAIN ANALYZE`
  runs it and shows the real time of each step (for example, whether it
  used an `Index Scan` or a `Seq Scan`).
- Neo4j: `EXPLAIN` shows the plan; `PROFILE` runs it and counts, step by
  step, how much data was touched (*db hits*).

### How each script loads

**`load_postgres.py`:**

1. **Drops and re-creates the tables** (`DROP TABLE IF EXISTS` and
   `CREATE TABLE`). That way every run starts from scratch, and running it
   twice gives the same result. Order matters: `actor_repo` is dropped
   first and created last, because it depends on the other two.
2. **Loads each CSV with `COPY`**, PostgreSQL's **bulk-loading** mechanism:
   much faster than inserting row by row, because the data goes in as one
   continuous stream. With `COPY ... FROM STDIN`, Python sends the file's
   contents over the connection, so the server doesn't need access to your
   files. First `actor` and `repo`, then `actor_repo`, because of the
   foreign keys.
3. **Runs `ANALYZE`** (see above).
4. **Saves everything with `COMMIT`.** Everything above forms a single
   **transaction**: a group of changes that are applied all together or
   not at all. If the script failed halfway, PostgreSQL would undo
   everything, so a half-finished load can never be left behind.
5. **Checks the counts**: counts each table's rows and compares them with
   the CSV's.

**`load_neo4j.py`:**

1. **Reads the three CSVs into Python** and converts the ids to numbers.
2. **Empties the database** (`MATCH (n) DETACH DELETE n`: deletes every
   node along with its edges) and creates the **uniqueness constraints**,
   if they don't exist.
3. **Creates the nodes and then the edges, in batches of 5,000 rows.**
   Instead of sending all 15,053 connections in one huge request, it sends
   them in parts. Each batch uses `UNWIND`, which turns the list into one
   row per element inside the database itself, like a `for` loop. For each
   edge, Neo4j **finds** the actor and the repo by id (fast, thanks to the
   constraints) and creates the edge between them. That's why the nodes
   have to exist before the edges.
4. **Checks the node and edge counts** against the CSVs.

The line-by-line explanations are in the annotated copies:
[load_postgres.py](load_postgres.py) and [load_neo4j.py](load_neo4j.py).

### How to run them

With both databases running and after `extract_csv.py`:

```bash
./run.sh scripts/extract_csv.py      # if the CSVs don't exist yet
./run.sh scripts/load_postgres.py
./run.sh scripts/load_neo4j.py
```

Both go through `run.sh`, because they need the passwords.

### Result

Both loads worked first time, and **all six checks say OK**:

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

Both databases now hold **exactly the same data**: 14,515 actors, 14,995
repos and 15,053 connections. That's the precondition for starting to
compare queries.

### The load timer

Both scripts show how long **each step** takes and the **total load
time**, measured with `time.perf_counter()`: Python's clock for measuring
durations, the most precise one, and unaffected if the computer's time of
day changes.

- **Included in the total:** everything that writes to the database, from
  creating or emptying through to saving (in PostgreSQL, the `COMMIT` is
  done just before stopping the clock).
- **Not included:** connecting, the final count check and, in Neo4j,
  reading the CSVs into Python (shown separately).

**Important: these times don't compare the two databases.** They tell you
how long the process takes (e.g. how long to expect once more hours of data
are loaded), but they're **not a benchmark result**, for three reasons:

1. **Each one loads differently:** PostgreSQL with `COPY`, its bulk-loading
   mechanism; Neo4j in batches through the driver, finding both nodes of
   every edge.
2. **It's a single run.** A serious benchmark repeats each measurement
   several times and discards the first, because at first the database has
   nothing in memory yet.
3. **It isn't what the project asks.** The research question is about
   **multi-hop traversals**, not about how long loading takes.

### Seeing the loaded data

**In pgAdmin 4**, the tables are under: **gharchive** → **Schemas** →
**public** → **Tables**. (`public` is the default schema: a kind of folder
inside the database where tables are created unless told otherwise.) The
**Catalogs** further up are PostgreSQL's internal tables, not the project's
data.

- If the tables don't show up, it's because they were created after pgAdmin
  was opened: right-click **Tables** → **Refresh**.
- **Seeing the data:** right-click a table → **View/Edit Data** → **First
  100 Rows**, or a query in the Query Tool. The `id` column's header shows
  **`[PK] bigint`**: `[PK]` means it's the primary key.
- **Seeing the indexes:** inside each table, **Indexes**. `actor_repo` has
  two: `actor_repo_pkey` (the primary key's) and `actor_repo_repo_id_idx`.

Useful queries in the Query Tool:

```sql
-- How many rows each table has
SELECT (SELECT count(*) FROM actor)      AS actors,
       (SELECT count(*) FROM repo)       AS repos,
       (SELECT count(*) FROM actor_repo) AS connections;

-- An actor's repos: one "hop" of the walk
SELECT a.login, r.name
FROM actor a
JOIN actor_repo ar ON ar.actor_id = a.id
JOIN repo r        ON r.id = ar.repo_id
WHERE a.login = 'peitongshi';
```

**In Neo4j**, from **Query** in Neo4j Desktop, in the `gharchive` database
(with the database selector or `:use gharchive`):

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

The result is **drawn**: a circle for the actor, another for their repo,
and an arrow between them. It's the same query as PostgreSQL's second one,
written in the graph's language: in SQL it takes two `JOIN`s to go from the
actor to the repo through `actor_repo`; in Cypher, the arrow *is* the
connection.


## Viewing and querying the graph in Neo4j Desktop (Query)

PostgreSQL has pgAdmin for looking at its tables. Neo4j's equivalent is the
**Query** tool in Neo4j Desktop: an editor where you write Cypher queries
and see the results, even **drawn** as nodes and arrows. This section
covers how to use it with the version installed in this project (Neo4j
Desktop 2.2.1), including the stumbling blocks that came up along the way.

### Step 1: check the instance is running

In the left-hand menu, **Local instances**. The `gharchive` card must show
**RUNNING**; if it doesn't, click **Start**.

Below it is the **Databases** list, which should show three: `gharchive`,
`neo4j` and `system`.

- **If it says *Databases (0)* and *Refreshing...*:** Neo4j Desktop couldn't
  read the list. It tends to happen right after starting, or after
  **changing the Neo4j password**, if Desktop kept the old one. Wait a few
  seconds or click the refresh button (⟳); if nothing changes, reconnect
  with the new password. **The data isn't lost**: it's only the list that
  hasn't loaded.

### Step 2: open Query and connect it to the instance

1. In the left-hand menu, under **Studio**, click **Query**.
2. If the top says **No instance connected**, click **Connect to instance**
   (in the middle) or the **No instance connected ∨** dropdown (top left),
   and choose the **`gharchive`** instance.
3. If it asks for credentials: user **`neo4j`** and the password from
   `secrets.sh` (`NEO4J_PASSWORD`).

Three indicators appear at the top, worth checking every time:

| Indicator | What it should say | What it means |
|---|---|---|
| **Instance** | `gharchive`, with a green dot | The instance (the "server") you're connected to |
| **Database** | **`gharchive`** | The database inside the instance where queries run |
| **User** | `neo4j` | Which user you're connected as |

### Step 3: choose the `gharchive` database (the most common stumble)

On connecting, Query opens the **`neo4j`** database, the default one. That
database is **empty**: the project's data was loaded into `gharchive`. The
sign you're in the wrong database is that the left-hand panel says **Nodes
(0)** and **Relationships (0)**.

To switch, use the **Database ∨** dropdown at the top, or type this in the
query bar and press **Ctrl + Enter**:

```cypher
:use gharchive
```

The bar changes from `neo4j$` to **`gharchive$`**. Commands starting with
`:` (like `:use`) aren't Cypher: they're commands for the tool itself.

### Step 4: the "Database information" panel

With `gharchive` selected, the left-hand panel summarises what's in the
database, and it's the quickest way to check the load:

| In the panel | Value | Where it comes from |
|---|---|---|
| **Nodes** | 29,510 | 14,515 `Actor` + 14,995 `Repo` |
| **Relationships** | 15,053 | The `INTERACTED_WITH` connections |
| **Labels** | `Actor`, `Repo` | The two node types |
| **Relationship type** | `INTERACTED_WITH` | The edge type |
| **Property keys** | `id`, `login`, `name`... | The nodes' properties |

The numbers match exactly what `load_neo4j.py` checked. *Property keys* also
lists other names (`data`, `nodes`, `relationships`, `style`,
`visualisation`): names Neo4j has registered internally, not properties of
our nodes.

**Clicking a label** (e.g. `Actor`) makes Query run a query that shows a
few nodes of that type.

### Step 5: writing queries and reading the result

Queries are typed in the top bar (`gharchive$`) and run with **Ctrl +
Enter** or the ▶ button. Each result appears below, in its own box, with
earlier ones further down.

**The project's first query:** an actor and their repo.

```cypher
MATCH (a:Actor {login: 'peitongshi'})-[e:INTERACTED_WITH]->(r:Repo)
RETURN a, e, r;
```

It reads almost like a drawing: "find (`MATCH`) an `Actor` node with login
`peitongshi`, connected by an `INTERACTED_WITH` arrow to a `Repo` node, and
return (`RETURN`) all three". `a`, `e` and `r` are names we give them so
they can be returned.

**What you see:**

- **Two circles:** the actor (green) and the repo (blue). Each label has
  its own colour.
- **An arrow** from the actor to the repo, labelled `INTERACTED_WITH`. The
  arrow's direction is the one set during loading: from `Actor` to `Repo`.
- **The text inside each circle** is one of its properties, which Neo4j
  picks to display. The actor shows its `id` (`321725054`) and the repo its
  `name` (`peitongshi/niulai-chinese`). Clicking a node shows all its
  properties.
- **Results overview**, on the right: how many nodes and relationships are
  in the result, by type (here, 1 `Actor`, 1 `Repo` and 1
  `INTERACTED_WITH`).

This actor is one of the special cases from the Extraction Stage: the one
who changed their login during that hour (from `lucky521-png` to
`peitongshi`). Since the script kept the most recent name, they show up
here as `peitongshi`.

**The result's three tabs:**

| Tab | What it shows |
|---|---|
| **Graph** | The drawing of nodes and arrows |
| **Table** | The same results as a table, row by row |
| **Raw** | The answer exactly as the server sends it (JSON text) |

Below the box there are controls to zoom, fit the drawing, and select or
move nodes.

**The time shown at the bottom** (e.g. *Started streaming 1 record after
388 ms and completed after 550 ms*) is how long that query took. As with
the load times, **it isn't a benchmark measurement**: it's a single run,
the first one (with nothing in memory yet), and it includes the tool's own
work. Also, this query searches by `login`, and `login` **has no index**
(only `id` does), so Neo4j had to check the actors one by one to find it.
The benchmark queries will always search by `id`.

### More useful queries

```cypher
// How many nodes and relationships there are (14515, 14995 and 15053)
MATCH (a:Actor) WITH count(a) AS actors
MATCH (r:Repo)  WITH actors, count(r) AS repos
MATCH ()-[e:INTERACTED_WITH]->() RETURN actors, repos, count(e) AS connections;
```

```cypher
// A few repos (always with LIMIT when drawing)
MATCH (r:Repo) RETURN r LIMIT 25;
```

```cypher
// The repo with the most different actors: a "meeting point" in the graph
MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo)
WITH r, count(a) AS actors ORDER BY actors DESC LIMIT 1
MATCH (a:Actor)-[e:INTERACTED_WITH]->(r)
RETURN a, e, r;
```

The last result is worth seeing: a repo in the middle with several arrows
coming in from its actors. It's exactly one of the few points through
which a multi-hop walk can get from one actor to another.

**Always use `LIMIT` when drawing.** Drawing all ~30,000 nodes at once
would make the tool very slow, and nothing would be readable.

### What to avoid in Neo4j Desktop

While looking for how to open Query, some menus turned up with options that
are dangerous or not meant for this:

| Where | Option | Watch out |
|---|---|---|
| A **database's** `···` in the *Databases* list | **Delete** | **Deletes the database with all its data.** That menu is only for managing the database (exporting, deleting...), not for viewing it |
| The **instance's** `···` (the card) | **Upgrade** | Upgrades Neo4j to another version: it would change the benchmark's conditions. **Don't use** |
| The **instance's** `···` | **Open ›** | Only opens files (the instance folder, the log and the configuration), not query tools |

**If the `gharchive` database is ever deleted by accident,** it's quick to
recover: **Create database** named `gharchive`, then
`./run.sh scripts/load_neo4j.py`. Another advantage of having the CSVs and
the scripts: the databases can always be rebuilt from scratch.

### Summary: the steps every time

1. **Local instances** → `gharchive` **RUNNING**.
2. **Query** → **Connect to instance** → `gharchive` → user `neo4j`.
3. **Database** → **`gharchive`** (or `:use gharchive`). Check the panel
   shows **Nodes (29,510)**.
4. Type the query in the `gharchive$` bar → **Ctrl + Enter**.


## The 24-hour pipeline (pipeline.py): a data-engineering perspective

Up to now, the whole project worked with **a single hand-picked hour**
(2026-08-27, 15:00 UTC). It's perfect for the benchmark, because it never
changes, but it isn't how real data is handled: in data engineering, data
keeps arriving, and what matters is having a **repeatable process**. This
stage adds that process: a **pipeline** (an automatic chain of steps) that
rebuilds a database with the **last 24 hours** of GH Archive.

### Two processes, each with its own database

From now on, the project has **two separate processes**:

| | Benchmark | 24-hour pipeline |
|---|---|---|
| **Data** | One fixed hour: 2026-08-27, 15:00 UTC | The last 24 hours, with a one-day delay |
| **Database** (in PostgreSQL and in Neo4j) | `gharchive` | `gharchive24h` |
| **How it's loaded** | By hand: `extract_csv.py`, `load_postgres.py`, `load_neo4j.py` | Automatically: `pipeline.py` |
| **Does it change?** | **Never.** It's frozen | It's rebuilt on every run |
| **What it's for** | Measuring and comparing queries under repeatable conditions | Having recent, plentiful data, with a data-engineering process |

In total there are **four databases**, two on each server:

```
PostgreSQL (port 5432)                 Neo4j (instance "gharchive", port 7687)
├── gharchive      ← benchmark          ├── gharchive      ← benchmark
└── gharchive24h   ← pipeline           └── gharchive24h   ← pipeline
```

**Why separate:** if the pipeline used `gharchive`, every run would wipe
the benchmark's data, and the measurements would no longer be repeatable.
That's why `pipeline.py` **refuses** to work on `gharchive`, even if asked
to by mistake.

**Why `gharchive24h` and not `gharchive_24h`:** Neo4j doesn't allow
underscores in database names (only letters, numbers, dots and hyphens).
So that the name is the same on both sides, `gharchive24h` is used.

### The window: a rolling 24 hours, one day behind, in UTC

Every time it runs, the pipeline works out which 24 hours to load:

1. It takes the current time **in UTC** and rounds it down to the hour.
2. It subtracts **24 hours of delay**: that's where the window **ends**.
3. It subtracts another **24 hours**: that's where it **starts**.

**Example:** on 22 October at 11:15 UTC, the window runs from **20/10 at
11:00 to 21/10 at 11:00**. That's 24 GH Archive files, from
`2026-10-20-11.json.gz` to `2026-10-21-10.json.gz` (the last one covers
10:00 to 11:00).

- **Why UTC:** GH Archive names its files by UTC time. In Portugal the
  clock is ahead of UTC (one hour in summer), so using local time would
  shift the window.
- **Why the one-day delay:** GH Archive publishes each hour shortly after
  it ends, but sometimes it runs late. With a day's margin, every hour in
  the window is sure to be published. The delay is a parameter
  (`--lag-hours`), so it can be reduced later on.
- **"Rolling":** every hour, the window moves forward one hour. The oldest
  hour drops out and a new one comes in.

### Rebuilding everything on every run

On every run, the pipeline **empties and refills** both `gharchive24h`
databases from the 24 hours. It sounds like a lot of work, but it's simpler
and more reliable than adding the new hour and removing the old one: with
the current schema (one connection per actor–repo pair, with no date),
there'd be no way of knowing which connections appeared *only* in the hour
that drops out.

What *is* done incrementally is the **download**: the files are kept in
`data/live/raw/`, and each run only downloads the new hour and deletes the
one that has left the window.

### A scheduled task every hour, not an always-running process

| | Always-running process | Scheduled task every hour |
|---|---|---|
| How it works | A program that never ends: it processes, waits an hour, starts again | A normal program that does its job and **ends**; the system launches it every hour |
| If it fails once | It stays stopped until someone restarts it | The next hour it tries again on its own |
| Where it's used | *Streaming* (e.g. Kafka) | *Batch* processes (cron, Airflow, Windows Task Scheduler) |

Since GH Archive publishes data **by the hour**, a scheduled *batch*
process is the natural choice. On Windows, the one that launches it is
**Task Scheduler**. As long as the pipeline lives on the laptop, it will
only run with the computer switched on and **Neo4j Desktop open**
(PostgreSQL starts on its own, as a service). To make it work without the
laptop, it would have to move to an always-on server; the options are at
the end of this section.

### What each run does

1. **Works out the window** (see above).
2. **Syncs the files:** deletes from `data/live/raw/` the ones that have
   left the window and downloads only the missing ones.
3. **Extracts the CSVs** for the 24 hours into `data/live/csv/`, with the
   same code as the benchmark (`extract_csv.py`): no bots, no repeated
   connections, and the most recent name for each `id`.
4. **Checks the servers and creates the databases if they don't exist:** if
   either one doesn't respond, it stops here, **before emptying anything**.
5. **Rebuilds PostgreSQL and then Neo4j** with the same loading scripts as
   the benchmark, but in `gharchive24h`, and compares the counts with the
   CSVs.
6. **Records the result:** everything that happened goes into
   `logs/pipeline.log`; and, if everything went well, the loaded window goes
   into `data/live/current_window.txt`.

| Folder or file | What it contains | On GitHub? |
|---|---|---|
| `data/live/raw/` | The window's 24 `.json.gz` files | No (`data/` is in `.gitignore`) |
| `data/live/csv/` | The window's three CSVs | No |
| `data/live/current_window.txt` | The last successfully loaded window, with its counts | No |
| `data/live/pipeline.lock` | Only exists while a run is in progress | No |
| `logs/pipeline.log` | The history of every run | No (`logs/` is in `.gitignore`) |

### Data-engineering practices the pipeline uses

| Practice | What it means | How it's applied here |
|---|---|---|
| **Idempotence** | Running something once or ten times leaves the same result | The databases are only created if they don't exist (`IF NOT EXISTS`); the content is always rebuilt the same way from the same window |
| **Pre-flight check** | Verifying everything is ready before changing anything | Downloads, extraction and connecting to both servers all happen **before** any database is emptied |
| **Atomic write** | A file is either complete or doesn't exist; never half-written | Downloads are saved as `.part` and only renamed once finished |
| **Retries** | A passing network glitch shouldn't bring the process down | Each download is tried up to 3 times, waiting a little longer each time |
| **Failing clearly** | A real problem gets noticed, not hidden | If an hour doesn't exist (404 error), the pipeline says so and doesn't load incomplete data |
| **Lock** | Two runs can't step on each other | A `pipeline.lock` file; if a run takes more than an hour, the next one is skipped |
| **Logging** | Every run leaves a trace, with a timestamp and level | `logs/pipeline.log`, with times in UTC, so they can be compared directly with the window |
| **Exit codes** | The program says whether it finished well (0) or badly (1) | Task Scheduler shows that code as the result of the last run |
| **Data quality** | Don't discard data silently | Events without an `id` are counted and flagged in the log |
| **Reuse, don't copy** | A single version of each piece of logic | The pipeline **imports** the benchmark scripts (`import extract_csv`...) instead of copying their code |
| **Protection** | Impossible to break what matters by mistake | The pipeline refuses to touch the benchmark's `gharchive` database |

### This stage's scripts

| Script | What it does now | Changes in this stage |
|---|---|---|
| **`pipeline.py`** (new) | Coordinates the whole pipeline: window, downloads, extraction, loads, log | New. [Annotated copy](pipeline.py) |
| `download_gharchive.py` | Downloads GH Archive hours | New `fetch_gz()` function: downloads without decompressing, with retries, atomic writing and a clear warning if the hour doesn't exist. By default it does the same as before. [Annotated copy](download_gharchive.py) |
| `extract_csv.py` | Creates the three CSVs | Accepts **several files**, including `.json.gz` without decompressing; discards and counts events without an `id`; writing the CSVs moves into a function (`write_all()`) that the pipeline reuses. [Annotated copy](extract_csv.py) |
| `load_postgres.py` | Loads the CSVs into PostgreSQL | New `--database` option (default `gharchive`). [Annotated copy](load_postgres.py) |
| `load_neo4j.py` | Loads the CSVs into Neo4j | New `--database` option (default `gharchive`). [Annotated copy](load_neo4j.py) |

**The benchmark hasn't changed:** it was checked that `extract_csv.py`
produces the benchmark CSVs **byte-for-byte identical** to before, and the
loads still use `gharchive` by default.

**How `import` works between our scripts:** every `.py` file is also a
**module** that another script can import. Importing it loads its
functions, but does **not** run its `main()`, thanks to the
`if __name__ == "__main__":` guard they all have. That way `pipeline.py`
can call `extract_csv.extract()` or `load_postgres.load()` as if they were
its own.

### How to run it

With PostgreSQL and Neo4j running:

```bash
./run.sh scripts/pipeline.py --dry-run    # shows the window and what it would download; changes nothing
./run.sh scripts/pipeline.py              # the real run
```

Options (all have a default value):

| Option | Default | What for |
|---|---|---|
| `--window-hours` | 24 | Window size (e.g. 6 for a quick test) |
| `--lag-hours` | 24 | How far back the window ends |
| `--database` | `gharchive24h` | Which database to rebuild on both sides (never `gharchive`) |
| `--dry-run` | — | Only show the plan |

### The first real run: a data-quality problem

The first run downloaded the 24 hours (about 240 MB) in **28 seconds**, but
failed during extraction:

```
KeyError: 'id'
    remember_latest(repos, repo["id"], ...)
```

In other words: some event had a `repo` **without the `id` key**. Searching
the data: **2 events out of 1,250,059** had `"repo": {}`, a completely empty
repo. Both were `ForkEvent`s; probably forks of repos that were later
deleted or made private, and whose data GH Archive couldn't save. In the
benchmark hour (69,429 events) there were none.

**Lesson:** a rare case that doesn't show up in a small sample shows up
when processing real, plentiful data. That's why pipelines are tested with
real data.

**Fix:** extraction **discards events without an actor or repo `id`**
(without an `id` neither the node nor the connection can be created), but
**counts them and flags it**, and the warning stays in the log:

```
WARNING  Skipped 2 event(s) without an actor or repo id
```

### Result of the first complete run

`Status: SUCCESS` in **160 seconds** in total, with all **six checks OK**:

| Step | Time |
|---|---|
| Download (all 24 hours were already there) | 0.0 s (the first time: 28 s) |
| Extraction of 1,250,059 events | 25.3 s |
| Load into PostgreSQL | 31.5 s |
| Load into Neo4j | 90.0 s |

**The 24 hours compared with the benchmark hour:**

| | Benchmark hour (27/08, 15:00) | 24 hours (20/10 12:00 → 21/10 12:00) |
|---|---|---|
| Events | 69,429 | **1,250,059** |
| Bot events discarded | 1,970 (**2.8%**) | 297,733 (**23.8%**) |
| Events without `id` discarded | 0 | 2 |
| Actors | 14,515 | **362,730** |
| Repos | 14,995 | **406,603** |
| Connections | 15,053 | **424,098** |
| Nodes in Neo4j | 29,510 | **769,333** |

**What these figures say:**

- **Bots weigh much more in these 24 hours:** almost a quarter of the
  events, compared with 2.8% in the benchmark hour. A single hand-picked
  hour can give a misleading picture: that's exactly the reason this
  pipeline exists.
- **The volume is about 26 times larger:** useful for the "data volume"
  axis of the research question.
- **There's still just over one connection per actor** (424,098 for
  362,730 actors): the graph is still very fragmented, although there will
  be more shared repos than in a single hour. It can be measured with
  `summarize_data.py`.

**About the load times** (which, like the benchmark's, are informative, not
benchmark results):

- In PostgreSQL, `actor_repo` took **27 seconds**, compared with 1 second
  for `actor` and `repo`. That's to be expected: for each row, PostgreSQL
  checks the two **foreign keys** (that the actor and the repo exist) and
  updates **two indexes**.
- In Neo4j, creating the edges (45 s) is the slowest part, because each
  edge first **looks up** its two nodes.

**A message that isn't an error:** during this run a long Neo4j line
appeared on screen, `Received notification from DBMS server ... has
caught up`, right after the `gharchive24h` database was created. It's an
**informational** notice from the driver: the new database is ready. To
keep it from cluttering the log, the pipeline now only records warnings and
errors from the Neo4j driver.

### Viewing the `gharchive24h` data

- **pgAdmin 4:** under **Databases**, `gharchive24h` appears next to
  `gharchive` (if not, right-click → **Refresh**). The tables are in
  **gharchive24h** → **Schemas** → **public** → **Tables**.
- **Neo4j Desktop (Query):** in the **Database** selector, choose
  **`gharchive24h`** (or `:use gharchive24h`). The panel should show
  **Nodes (769,333)** and **Relationships (424,098)**. With this many nodes
  it's even more important to use `LIMIT` when drawing.
- **The log:** `logs/pipeline.log` keeps every run, and
  `data/live/current_window.txt` the last successfully loaded window.

### What's left

1. **Schedule it every hour** in Windows Task Scheduler.
2. **Make it work without the laptop switched on.** The pipeline and both
   `gharchive24h` databases would have to move somewhere that's always on:

   | Option | What it is | Cost | Bear in mind |
   |---|---|---|---|
   | Cloud server | An always-on Linux machine, with PostgreSQL, Neo4j and the pipeline scheduled with cron | Free (Oracle Cloud *Always Free*) or about €5/month | It has to be maintained and secured; it's the closest thing to a real job |
   | GitHub Actions + cloud databases | GitHub runs the pipeline every hour; PostgreSQL on Neon or Supabase | Largely free | Neo4j AuraDB Free allows about 200,000 nodes, and these 24 hours have **769,333**: not enough |
   | Stay on the laptop | Task Scheduler | Free | Only works with the laptop switched on and Neo4j Desktop open |

   The benchmark would stay on the laptop in any case, because measuring
   times calls for a controlled machine with no network in between.
3. **A possible improvement: *blue-green* switching.** Right now, during a
   rebuild, PostgreSQL shows the previous data until the end (because the
   load is a single transaction), but Neo4j is visible half-filled for a
   minute and a half. In real systems the data is loaded into a new
   database and, once finished, the switch from one to the other happens
   all at once.
