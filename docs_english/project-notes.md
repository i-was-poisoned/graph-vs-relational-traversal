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
5. **Check that it works.** Open Neo4j Browser (the *Open* button, or
   <http://localhost:7474> in your web browser), log in with the `neo4j`
   user and your password, and run:

   ```cypher
   RETURN 1;
   ```

   It should return `1`.

Unlike PostgreSQL, the Neo4j database **only runs while it's started** in
Neo4j Desktop. Before working with it, open Neo4j Desktop and check that
it's running.

### Step 3: set up Python

1. **Create a virtual environment.** A virtual environment is a folder
   (`.venv`) with a copy of Python just for this project. What you install
   inside it doesn't affect the rest of the computer, and each project can
   have its own package versions. The `.venv` folder is already in
   `.gitignore`, so it isn't pushed to GitHub.

   ```bash
   cd /c/dev/Research
   python -m venv .venv
   source .venv/Scripts/activate
   ```

   When the environment is active, the Git Bash prompt starts with
   `(.venv)`. You need to activate it (the last line) every time you open
   a new terminal to work on the project.
2. **Install both connectors:**

   ```bash
   python -m pip install "psycopg[binary]" neo4j
   ```

   `psycopg[binary]` includes everything needed to connect to PostgreSQL
   without installing anything else.
3. **Record the dependencies.** In the project's root folder, create a
   `requirements.txt` file with these two lines:

   ```
   psycopg[binary]
   neo4j
   ```

   That way anyone (or you, on another computer) can install the same
   thing with `python -m pip install -r requirements.txt`. This file
   **does** get pushed to GitHub.

### Step 4: pass the passwords to Python without writing them in the code

Passwords go in **environment variables**: values that live in the
terminal while it's open, outside any file. In Git Bash:

```bash
export PGPASSWORD='the-postgres-password'
export NEO4J_PASSWORD='the-neo4j-password'
```

- `PGPASSWORD` is a standard name: PostgreSQL (and `psycopg`) read it
  automatically, so the code doesn't even need to mention it.
- `NEO4J_PASSWORD` is one we'll read ourselves from Python with
  `os.environ["NEO4J_PASSWORD"]`.
- These variables disappear when you close the terminal. You need to set
  them again each time, just like activating the virtual environment.

### Step 5: check that Python can reach both databases

With the virtual environment active, both databases running, and the
environment variables set, this code should print PostgreSQL's version and
a `1` from Neo4j:

```python
import os

import psycopg
from neo4j import GraphDatabase

# PostgreSQL: the password is read automatically from PGPASSWORD
with psycopg.connect(host="localhost", dbname="gharchive", user="postgres") as conn:
    print(conn.execute("SELECT version();").fetchone()[0])

# Neo4j: the password is read from NEO4J_PASSWORD
driver = GraphDatabase.driver("neo4j://localhost:7687",
                              auth=("neo4j", os.environ["NEO4J_PASSWORD"]))
with driver.session() as session:
    print(session.run("RETURN 1 AS ok").single()["ok"])
driver.close()
```

This code can be saved as `scripts/check_connections.py` and run with
`python scripts/check_connections.py`.

### Checklist

| Check | How | Expected result |
|---|---|---|
| PostgreSQL installed | `psql -U postgres -c "SELECT version();"`, or `SELECT version();` in pgAdmin's Query Tool | PostgreSQL's version |
| `gharchive` database created | `psql -U postgres -d gharchive -c "SELECT 1;"`, or `SELECT 1;` in pgAdmin's Query Tool with `gharchive` selected | A table with a `1` |
| Neo4j running | `RETURN 1;` in Neo4j Browser | `1` |
| Virtual environment active | The Git Bash prompt starts with `(.venv)` | — |
| Connectors installed | `python -m pip show psycopg neo4j` | Details for both packages |
| Python reaches both | `python scripts/check_connections.py` | PostgreSQL's version and a `1` |

**Write down the installed versions** (of PostgreSQL, Neo4j, and both
Python packages). They're part of the benchmark's conditions: for someone
to repeat the experiment, they need to know which versions it was run
with.
