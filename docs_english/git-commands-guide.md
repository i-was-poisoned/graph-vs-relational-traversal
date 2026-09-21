# Understanding Git Commands

This guide builds up from first principles: what Git actually is, how a
commit gets from your laptop to GitHub, and what each command you've used so
far (`add`, `commit`, `push`, `pull`, `remote`, and more) actually does under
the hood — including the real credential problem you hit today and how it
was solved.

## 1. What Git actually is

Git is a **version control system**: it takes snapshots of your project's
files over time, so you can see history, undo mistakes, and — crucially for
this project — sync those snapshots between your laptop and a remote server
(GitHub). Git itself runs entirely on your machine; GitHub is just one place
you can *also* store a copy of your Git history, so you can back it up,
share it, or open it from another computer.

## 2. The three-stage model: working directory, staging area, repository

This is the single most important mental model for understanding every
command below. A file in your project can be in one of three "places" as far
as Git is concerned:

```
Working Directory  --git add-->  Staging Area  --git commit-->  Repository (local history)
(your actual files                (files marked                  (permanent snapshots,
 on disk, as you                   ready for the                  each one identified
 edit them)                        next commit)                   by a commit hash)
```

- **Working directory** — the actual files on your disk, exactly as you see
  them in VS Code right now. Editing a file only changes this stage.
- **Staging area** (also called "the index") — a holding area for changes
  you've decided *should* go into the next commit. You build up the staging
  area with `git add`.
- **Repository** — the permanent, named history of snapshots ("commits").
  `git commit` takes whatever is currently staged and seals it into a new
  permanent snapshot in this history.

Why the extra staging step, instead of just committing everything directly?
It lets you commit only *some* of your changes at a time — e.g. you edited
three files but only two of them are related to what you want this commit to
represent. `git add` chooses what's included; `git commit` seals that choice.

## 3. `git status` — where do things stand?

Before doing anything else, `git status` tells you: which files are staged,
which are modified-but-not-staged, and which are untracked (new files Git
doesn't know about yet). It's read-only — it changes nothing, so it's always
safe to run and worth running often, especially before `add`/`commit`/`push`.

## 4. `git add` — moving changes into the staging area

```bash
git add .
```

`git add <path>` stages a specific file or folder. `git add .` stages
*everything* changed or new in the current directory and below — which is
what you ran, and is fine for a small personal project where you're
reviewing everything yourself. On larger/shared projects, staging specific
files by name is safer, since `.` can accidentally include files you didn't
mean to commit.

This step is purely local — nothing leaves your machine yet.

## 5. `git commit` — sealing a snapshot

```bash
git commit -m "Exploration stage set up"
```

Takes everything currently in the staging area and permanently records it as
a new snapshot in your local repository's history, labeled with the message
given after `-m`. Each commit gets a unique identifier (a "hash") and
remembers exactly what changed and when. This is still entirely local — a
commit exists only on your laptop until you push it somewhere.

A good commit message says *why*/*what* changed at a glance — which is why
we settled on something like `"Exploration stage set up"` earlier, rather
than something vague like `"updates"`.

## 6. `git remote` — where does "elsewhere" even mean?

A **remote** is just a saved nickname for another copy of the repository
somewhere else — almost always a URL pointing at a GitHub (or similar)
repository. The default nickname Git uses is `origin`, but that's only a
convention, not a requirement.

```bash
git remote -v
```

Lists every remote this local repo knows about, with their URLs, for both
`fetch` (downloading) and `push` (uploading) directions — normally identical.
This is a read-only, purely informational command. Running it is what
revealed today that `origin` was pointing at
`https://github.com/Winteroc18pedro/graph-vs-relational-traversal.git`.

### `git remote set-url` — changing where a remote points

```bash
git remote set-url origin https://i-was-poisoned@github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

Changes the URL stored under an existing remote nickname (`origin`), without
touching your commit history at all — it only affects where future
`push`/`pull` commands talk to. This is stored in this repo's own local
`.git/config` file, so it only affects *this* repository, never any other
repo on your machine.

**Why we needed this today:** your Windows machine had a GitHub login cached
in Credential Manager for your Celfocus work account
(`NB30006_celfocus`), and `git push` was silently using that cached login
because the remote URL (`https://github.com/...`) didn't specify *which*
account to authenticate as. GitHub correctly refused the push with a 403,
because that work account has no permission on your personal repo.

Embedding your actual username directly in the URL
(`https://i-was-poisoned@github.com/...`) tells Git's credential manager to
look up (and cache) credentials under a *separate* key specific to that
username, rather than reusing whatever was last cached for plain
`github.com`. That's what let the next `git push` prompt a fresh login for
the correct account, without disturbing the cached work credential used by
your Celfocus repos.

## 7. `git push` — sending local commits to a remote

```bash
git push
```

Uploads any commits that exist in your local repository but not yet in the
remote's copy, for the current branch. This is the step that actually
requires authentication, since you're writing to someone else's server
(GitHub) — hence this being where the permission error showed up.

### `git push -u origin main` (a.k.a. `--set-upstream`)

```bash
git push -u origin main
```

`-u` (short for `--set-upstream`) does one extra thing beyond a normal push:
it tells your local `main` branch to "track" `origin`'s `main` branch,
remembering that association. After running this **once**, plain `git push`
and `git pull` (with no extra arguments) automatically know which remote and
branch to talk to, since that link is now remembered. Without it, Git would
ask you to specify the remote and branch by name every single time.

You need `-u` the *first* time you push a given local branch to a given
remote branch; after that, plain `git push` is enough.

## 8. `git pull` — bringing remote commits down to you

```bash
git pull
```

The reverse direction of `git push`: fetches any commits that exist on the
remote but not yet in your local repository, and merges them into your
current branch. Not used yet in this project (since you're the only
contributor so far and nothing exists on the remote that isn't already
local), but this is what you'd run before starting new work if you were
collaborating with someone else, or working from a second machine, to make
sure you're building on the latest version.

## 9. `git clone` — getting a remote repository for the first time

```bash
git clone https://github.com/i-was-poisoned/graph-vs-relational-traversal.git
```

This is how the local `C:\dev\Research` copy was created in the first place
(as covered in the "Repository Workflow So Far" section of
[project-notes.md](project-notes.md)): it downloads the entire history of a
remote repository and sets it up as a new local repository, automatically
configuring `origin` to point back at the URL you cloned from. You only run
this once, at the very start — after that, `pull`/`push` handle keeping the
two in sync.

## 10. Other commands worth knowing

- **`git log`** — shows the commit history (message, author, date, hash) for
  the current branch. Add `--oneline` for a compact one-line-per-commit view.
- **`git diff`** — shows the exact line-by-line changes that are staged or
  unstaged but not yet committed. Useful for reviewing exactly what you're
  about to `add`/`commit` before you do it.
- **`git branch`** — lists local branches (this project has only used
  `main` so far); also used to create new ones (`git branch <name>`) when
  you want to work on something without affecting `main` directly.

## 11. Quick reference

| Command | What it does | Touches the remote? |
|---|---|---|
| `git status` | Show what's changed/staged | No |
| `git add .` | Stage all changes | No |
| `git commit -m "..."` | Save a snapshot locally | No |
| `git remote -v` | List configured remotes | No (read-only) |
| `git remote set-url origin <url>` | Change where a remote points | No |
| `git push` | Upload local commits | Yes |
| `git push -u origin main` | Upload + link local/remote branches (first time only) | Yes |
| `git pull` | Download + merge remote commits | Yes |
| `git clone <url>` | Get a full copy of a remote repo (one-time) | Yes |
