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

## Why `.gitignore` and `README.md` Matter

- **`README.md`** is the entry point to the project for anyone (including future
  you) who opens the repository. It should explain what the project is, why it
  exists, and what question it's answering — this project's `README.md` currently
  states its core research question up front. A clear README turns a folder of
  files into a legible project.
- **`.gitignore`** tells git which files and folders to *never* track — build
  artifacts, caches, virtual environments, logs, credentials, and other files that
  are either regenerable or environment-specific. Without it, these files clutter
  commit history, bloat the repository size, and risk accidentally leaking
  machine-specific paths or secrets. It also prevents noisy diffs where
  irrelevant generated files show up as "changes" on every commit.

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

`scripts/peek_data.py` reads the first few events from the file and prints
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

The overall pipeline so far is: **download_gharchive.py → peek_data.py** —
first fetch and decompress the fixed dataset hour, then inspect it, before
moving on to actually extracting and loading records into the relational and
graph models being compared.
