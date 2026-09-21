# Understanding GH Archive

This guide builds up from first principles: what GitHub events are, what GH
Archive does with them, what the files actually contain, and how to turn that
into usable data for this project.

> The specific date/hour this project actually uses as its dataset is recorded
> in the project [README](../README.md), not here — this file is about
> understanding GH Archive itself, not about the specific choice made for this
> project.

## 1. What is a "GitHub event"?

Every time something happens on a *public* GitHub repository — someone pushes
commits, opens an issue, opens a pull request, comments, forks a repo, stars a
repo, creates a branch, and so on — GitHub records that as a discrete **event**.
Conceptually, this is just a log entry: "at this timestamp, this user did this
action to this repository."

GitHub exposes a live feed of these as its public Events API. But a live feed
is not useful for research — you can't go back in time and ask "what happened
last Tuesday." You need something that has been recording continuously and
lets you fetch a specific slice of the past.

## 2. What GH Archive is

GH Archive is a long-running project (started in 2011, still running) that sits
on top of GitHub's public event feed and does one job: continuously record
every public event, bundle them up **by hour**, and publish each hour as a
downloadable file, permanently, at a predictable URL. It is not affiliated with
GitHub itself — it's an independent archival project — but it uses GitHub's own
public data, so it is a faithful historical record of public GitHub activity.

The practical result: for *any* hour since 2011, you can fetch a file
containing every public event that happened on GitHub during that hour,
worldwide.

## 3. Why this matters for your project

Your research question is about when a graph model outperforms a relational
model for multi-hop queries. To test that, you need a real dataset with
genuine relationships in it — not synthetic data you invented, which risks
having an artificial shape that flatters one model or the other.

GH Archive events naturally encode a graph:

```
User --[pushed to]--> Repository
User --[starred]-----> Repository
User --[forked]-------> Repository
User --[opened PR on]-> Repository
```

A "repo" can also connect back out to other users (e.g. everyone who starred
it), so following chains of these relationships — "users who starred repos
that were forked by users who also pushed to..." — is precisely the kind of
multi-hop traversal your research question is about. The same event records
can be flattened into relational tables (a `users` table, a `repos` table, an
`events` table with foreign keys) or loaded as nodes and edges in a graph
database, giving you a like-for-like comparison on real-world data.

## 4. The URL structure

Every hourly file lives at:

```
https://data.gharchive.org/{YYYY-MM-DD}-{H}.json.gz
```

- `{YYYY-MM-DD}` — the date, e.g. `2026-08-27`.
- `{H}` — the hour **in UTC**, from `0` to `23`, written **without** a leading
  zero (`5`, not `05`; `15` stays `15`).

So `https://data.gharchive.org/2026-08-27-15.json.gz` would be every public
GitHub event that occurred between 15:00:00 and 15:59:59 UTC on August 27,
2026 — used here purely as an example of the URL shape.

There is no API key, authentication, or rate limit for downloading these files
— they are static files on a server, fetched like any other download.

## 5. Recency and availability — why you can't use "right now"

GH Archive can only publish a file for an hour that has **fully finished**,
because it needs every event from `:00` to `:59` of that hour before it can
bundle and publish it. Two practical consequences:

- **You can't pick the current, still-in-progress hour** — it doesn't exist as
  a file yet, because it hasn't finished happening.
- **There's a short publishing lag after an hour ends.** GH Archive needs a
  little time to collect and package the just-finished hour, so even the most
  recently completed hour may not be available for download immediately. In
  practice this delay is generally short (well under an hour), but there's no
  hard guarantee on exactly when a given hour's file will appear.

For research purposes there's a second, more important reason to avoid "the
present moment" regardless of publishing lag: **reproducibility**. Your
project's whole point is a measurable, comparable result — if the dataset were
defined as "whatever hour it is when you run this," the input would be
different every time the pipeline runs, and nobody (including future you)
could reproduce your results. The fix is simple: pick one specific, fixed
date and hour, safely in the past (a few hours old is already more than
enough margin), and record that exact value once — that becomes a constant
input, not something computed at run time.

## 6. What's inside the file

The filename ends in `.json.gz`. That name tells you two things are stacked:

1. **`.gz`** — the outer layer is gzip compression, the same compression used
   by `.zip`-adjacent tools. You must decompress this before you can read
   anything.
2. **`.json`** — after decompressing, you get text. But despite the `.json`
   extension, it is **not one big JSON document**. It's in a format called
   **JSON Lines** (sometimes `.jsonl`): every line of the file is a complete,
   independent JSON object, and there are no commas or brackets joining lines
   together. A file with 60,000 events is a text file with 60,000 lines, each
   one independently parseable.

This matters practically: you cannot do `json.load()` (parse-the-whole-file)
on it in most languages — you read it line by line and call the JSON parser on
each line individually.

### Anatomy of one event

A single line, once parsed, looks approximately like this (fields trimmed for
clarity):

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

Key fields:

- **`type`** — the kind of event. Common ones: `PushEvent` (code pushed),
  `WatchEvent` (this is GitHub's internal name for **starring** a repo, not
  literally "watching"), `ForkEvent`, `PullRequestEvent`, `IssuesEvent`,
  `IssueCommentEvent`, `CreateEvent` (new branch/tag/repo), `DeleteEvent`.
- **`actor`** — the GitHub user who performed the action.
- **`repo`** — the repository the action happened on.
- **`payload`** — extra detail specific to the event type (e.g. for a
  `PushEvent`, the actual commits; for a `PullRequestEvent`, PR details).
- **`created_at`** — timestamp of the event.

For building a graph, the fields you almost always care about are `type`,
`actor.login`, `repo.name`, and `created_at` — that's enough to construct
`(user)-[ACTION]->(repo)` edges. The `payload` is usually only needed if your
analysis cares about the content of the action, not just that it happened.

### Actors, repos, and events

These three words get used constantly in this project, so it's worth being
precise about what each one means:

- An **event** is a single recorded action — one line in the archive file,
  tagged with a `type`, a timestamp, and exactly one actor and one repo. It's
  the thing you count; `summarize_data.py`'s "Total events" number is a count
  of lines.
- An **actor** is the GitHub account (human or bot) that performed the
  action, identified by `actor.login`.
- A **repo** is the GitHub repository the action happened on or to,
  identified by `repo.name`.

An event always connects exactly one actor to exactly one repo at one point
in time — it's the *edge*, while actors and repos are the two *node* types it
connects. Running `scripts/summarize_data.py` against this project's fixed
hour shows 69,429 events but only 14,728 unique actors and 16,497 unique
repos: most actors and repos appear in more than one event (the busiest
actor, `github-actions[bot]`, alone accounts for 994 of them). That's the
`(user)-[ACTION]->(repo)` shape from above, at scale — a many-to-many web of
edges between a smaller set of actor-nodes and repo-nodes.

### Event type glossary

`scripts/summarize_data.py` prints a breakdown by `type`. Here's what each
type appearing in this project's fixed hour actually represents:

- **`PushEvent`** — one or more commits were pushed to a branch.
- **`CreateEvent`** — a new branch, tag, or repository was created.
- **`DeleteEvent`** — a branch or tag was deleted.
- **`PullRequestEvent`** — a pull request was opened, closed, merged,
  reopened, or edited.
- **`IssueCommentEvent`** — a comment was posted on an issue *or* a pull
  request's main conversation thread (GitHub treats a PR's conversation as an
  issue internally, so PR comments show up as this type too, not as
  `PullRequestReviewCommentEvent`).
- **`IssuesEvent`** — an issue was opened, closed, reopened, assigned, or
  labeled.
- **`PullRequestReviewCommentEvent`** — a comment was left on a specific
  line of a pull request's diff (a line-level review comment, distinct from a
  general conversation comment).
- **`PullRequestReviewEvent`** — a full pull request review was submitted
  (approve / request changes / comment).
- **`WatchEvent`** — a repo was starred. (GitHub's internal name for
  starring, not "watching" — see the `type` bullet above.)
- **`ReleaseEvent`** — a new release (tagged version) was published.
- **`ForkEvent`** — a repository was forked.
- **`CommitCommentEvent`** — a comment was left directly on a commit,
  outside of any pull request.
- **`MemberEvent`** — a user was added as a collaborator on a repo.

GitHub's event schema has a few more types (e.g. `PublicEvent` for a private
repo turning public, `GollumEvent` for wiki edits) that simply didn't occur
during this project's fixed hour, so they're omitted here.

### Where a second actor appears (nested references)

Every event's top-level `actor` is *one* GitHub user — the one who triggered
the event. But several event types also reference a *second* user somewhere
inside `payload`, which matters a lot for this project: an
actor-repo-actor-repo traversal needs more than one actor per event to have
anywhere to "hop" to.

`scripts/profile_schema.py` searches each event's `payload` for nested
objects shaped like `{"id": ..., "login": "..."}` — the same shape as the
top-level `actor` — and reports where it finds them. Running it against
this project's fixed hour shows:

- **`PushEvent` (95.3% of all events) has no second actor anywhere in its
  payload.** It only carries `ref`, `before`/`head` (commit SHAs), and
  `repository_id` — no author, no committer object. This is the single
  most important finding for schema design: the overwhelming majority of
  events in this dataset cannot contribute an actor-to-actor edge, only an
  actor-to-repo one.
- **`PullRequestEvent`'s `payload.pull_request` is a *trimmed* reference**
  (just `id`, `number`, `url`, `head`, `base`) — it does **not** include the
  PR's author the way GitHub's full REST API response would. The only
  second-actor references on this event type are the optional `assignee`/
  `assignees` fields, present on just ~2% of PR events.
- **Richer, comment/review-style events reliably carry a second actor:**
  `IssueCommentEvent` (`payload.comment.user`, `payload.issue.user`),
  `IssuesEvent` (`payload.issue.user`), `PullRequestReviewCommentEvent`
  (`payload.comment.user`), `PullRequestReviewEvent` (`payload.review.user`),
  `CommitCommentEvent` (`payload.comment.user`), `ReleaseEvent`
  (`payload.release.author`), `ForkEvent` (`payload.forkee.owner`), and
  `MemberEvent` (`payload.member` itself) — all present on 100% of their
  respective event type's events.

Practical takeaway: if the benchmarked traversal needs real actor-to-actor
edges (not just actor-to-repo, with "shared repo" as the only connection
between actors), those edges come almost entirely from the ~4.7% of events
that aren't `PushEvent` — mainly comments, reviews, issues, releases, forks,
and membership changes. Run `python scripts/profile_schema.py` yourself
(optionally with `--type <EventType>`) to see the full, current breakdown
before finalizing the schema.

## 7. Getting the data onto your machine

Since it's a plain HTTPS file, any of these work (substitute the actual
date/hour this project uses, as recorded in the README):

```bash
# curl
curl -O https://data.gharchive.org/YYYY-MM-DD-H.json.gz

# wget
wget https://data.gharchive.org/YYYY-MM-DD-H.json.gz
```

Or simply paste the URL into a browser — it downloads like any file.

Then decompress it:

```bash
gunzip YYYY-MM-DD-H.json.gz
# produces: YYYY-MM-DD-H.json
```

(Many programming languages can also read `.gz` files directly, streaming the
decompression, without a separate manual unzip step — e.g. Python's `gzip`
module.)

## 8. Reading it into code

A minimal Python example, reading line by line so the whole file never has to
sit in memory at once:

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

From there, the same extracted `(actor, type, repo, timestamp)` records can be:

- Inserted into relational tables (`users`, `repos`, `events` with foreign
  keys to both), or
- Inserted as nodes (`User`, `Repo`) and edges (`PUSHED`, `STARRED`, `FORKED`)
  in a graph database.

Because both models are built from the *identical* extracted records, any
performance difference you measure between them is attributable to the
storage/query model — not to differences in the underlying data.

## 9. Scaling up later

A single hour typically contains tens of thousands of events — enough to
build a real graph with meaningful multi-hop structure. If later experiments
need more volume (e.g. to push traversal depth further before hitting
diminishing returns), you can repeat the same download-and-parse process for
additional hours or days — GH Archive files are addressed individually, so
scaling up just means fetching more of them and merging the extracted
records, no format changes needed.

## 10. Alternative: querying without downloading files

GH Archive's data is also mirrored into Google BigQuery as public tables
(`githubarchive.hour.YYYYMMDD_HH`, and daily/yearly rollups). If you have (or
set up) Google Cloud access, you can run SQL directly against these tables in
a browser — useful for quick exploratory questions ("how many `ForkEvent`s
happened in this hour?") without writing any download/parsing code. This is
entirely optional for this project; downloading and parsing a single hourly
file directly, as described above, is sufficient and keeps the dependency list
smaller.
