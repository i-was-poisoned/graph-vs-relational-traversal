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
