# note-cli design

## Purpose

A CLI research-notebook tool for recording project decisions and their
branching/merging history as a graph. Complements, does not replace,
existing memory systems (`MEMORY.md`, `claude-mem`) — this tool is scoped
specifically to decision provenance: what was decided, why, what it
branched from, what it merged into.

On top of provenance it holds the project's **goal and priorities**: one
final goal per repo with weighted, rubric-bearing criteria, and per-branch
goals as graph nodes that attempts point at. Attempts carry scores against
those criteria, so "which arm is winning, and against what standard" is
answerable from the store rather than from memory.

## Architecture

- Standalone git repo at `~/projects/note-cli/`, packaged as a Python
  package with `pyproject.toml` and a console-script entry point.
- Installed globally via `pipx install -e .`, exposing a `note` command
  on `$PATH`.
- Data is NOT global, and NOT in the working tree. Each invocation
  resolves the store as:

      realpath(`git rev-parse --git-common-dir`) / "notes"

  i.e. `<repo>/.git/notes/`. Every linked worktree of a repo shares one
  `.git`, so all worktrees see **one store** — the central goal, the
  experiment graph and the current scores stay shared while six parallel
  branches are in flight.
- Because the store lives inside `.git/`, git never considers it for
  tracking. **No `.gitignore` entry is needed or wanted.**
- `git rev-parse --git-common-dir` prints a *relative* path from the main
  worktree (`../.git` from a subdirectory) and an *absolute* one from a
  linked worktree. `os.path.realpath()` against the process cwd absorbs
  both. (`--path-format=absolute` would be cleaner but needs git ≥ 2.31;
  the target machine runs 2.25.1.)
- Outside a git repo, `git rev-parse` fails and the CLI exits with that
  message. That is the whole "are we somewhere valid" guard.
- **Cost accepted**: the store does not survive a re-clone and is not
  carried by `git push`. This is a single-machine personal tool; backup,
  if ever wanted, is a separate problem and not solved here.
- Chosen over standalone (PyInstaller) binaries: python3 is already
  present on macOS/Linux, so a bundled runtime buys little. `pyproject.toml`
  structure keeps a Homebrew-formula or PyInstaller path open later without
  restructuring.

## Data model & storage

Four append-only JSONL files under `<repo>/.git/notes/`:

- `nodes.jsonl` — one JSON object per line:
  `{"id": 1, "content": "...", "type": "decision", "tags": ["a","b"], "branch": "exp/grade-style", "timestamp": "2026-09-17T12:00:00"}`
- `edges.jsonl` — one JSON object per line:
  `{"from": 1, "to": 2, "relation": "leads_to"}`
- `goal.jsonl` — the repo's final goal and its criteria; **last line wins**.
- `scores.jsonl` — one JSON object per line:
  `{"node": 7, "scores": {"consistency": 0.8, "legibility": 0.6}, "note": "...", "timestamp": "..."}`;
  the last line for a given node wins **wholesale** — a re-score replaces
  the previous judgement rather than merging into it, so a criterion left
  out of the newer line counts as 0, not as its old value. Partial merges
  would make a node's real score depend on the order of every past score
  line, which is unreadable. Kept out of `nodes.jsonl` so that file
  stays append-only-and-never-revisited — a re-score is a new line here, not
  a rewritten node.

"Last line wins" everywhere means **last in file order**, not latest by
timestamp. Appends are serialized by the write lock, so file order is a
total order; timestamps are informational and two writes inside the same
second need no tiebreak rule.

`type` and `relation` are free-form strings, not enums. A short list of
suggested relation names (e.g. `leads_to`, `supersedes`, `merged_from`,
`conflicts_with`) is documented but not enforced. `targets` is the one
relation with behavior attached (see *Goals*).

### Concurrency

Sharing the store across worktrees breaks the original "single-user,
sequential, no locking" assumption: two agents running `note add` in
parallel both read the same last id and write it twice. Every write takes
an `fcntl.flock` on `<store>/.lock`. Stdlib, a handful of lines. IDs stay
sequential integers so `note link 3 7` stays typable by hand.

The lock covers **every write path, not just `add`** — each one is a
read-then-append that a concurrent write can invalidate: `add` reads the
last id, `link` validates both endpoints exist, `score` reads `goal.jsonl`
and validates the node. Locking `add` alone leaves `link` validating
against a snapshot that a mid-flight `add` is still changing.

Each node is auto-tagged with `git branch --show-current` in a `branch`
field. In a shared store, "which arm is this from" is otherwise lost. On a
detached HEAD — a worktree mid-rebase, for one — that command prints
nothing, so the field falls back to `git rev-parse --short HEAD`.

### Versioning

`nodes.jsonl` and `edges.jsonl` are append-only with timestamps — that
*is* the history; nothing overwrites anything. The only mutable concept
introduced here is the goal, so `goal.jsonl` is append-only too and the
last line is the current goal. `note goal --history` prints the
progression for free.

A nested git repo inside the store (auto-commit per write, real
`diff`/`revert`) was considered and rejected for now: append-only already
loses nothing, and a git repo inside `.git/` is a structure that has to be
explained every time someone finds it. Revisit only if `revert` is
actually wanted in practice.

JSONL (not SQLite) was originally chosen so `.notes/` would be
git-diffable and reviewable in PRs. That rationale dies with the move into
`.git/`. The format stays anyway: grep-ability and atomic single-line
appends carry it on their own.

## Goals, priorities and scoring

### The final goal

One per repo, stored in `goal.jsonl`, deliberately **not** a graph node —
it is the fixed standard the graph is measured against, not a step in it:

```json
{"goal": "...", "criteria": [
  {"name": "consistency", "weight": 0.5, "rubric": "does the reference style hold across seeds"},
  {"name": "legibility",  "weight": 0.3, "rubric": "is rendered text readable at 512px"},
  {"name": "latency",     "weight": 0.2, "rubric": "single-image wall clock under 8s"}
], "timestamp": "..."}
```

Weights are not forced to sum to 1; they are normalized at scoring time.
Each criterion carries a one-line `rubric` — without it an agent scores by
its own invented standard, which is the failure mode this whole section
exists to prevent.

### Per-branch goals

An experiment's own objective is a graph node with `type: goal`. Attempt
nodes point at it with the `targets` relation, so goal nodes sit at the
**far end** of the graph (out-degree 0 in that layer).

That placement collides with two existing definitions: `tails` means
"out-degree 0 = the working frontier", and `in-degree > 1` means "merge
point". A goal with twenty attempts pointing at it would flood `tails` and
read as a giant merge.

**Resolution: two filters, not one.**

1. `targets` edges are excluded from all topology computation, so merge
   detection (`in-degree > 1`) sees only real convergence of work.
2. `heads`/`tails` additionally skip `type: goal` nodes. Filter 1 alone is
   not enough: a goal node whose only edges are inbound `targets` becomes
   *isolated* in the filtered graph — in-degree 0 and out-degree 0 — so it
   would show up in `heads` **and** `tails`. The type skip is the one line
   that actually keeps the frontier listing meaningful.

Goals are an overlay on the work graph, not a stage in it. Traversal
ignores both filters: `trace --down` follows `targets` forward ("what is
this attempt ultimately for"), and `trace --up` from a goal node follows
them backward, which is the free "which attempts feed this goal" view.

### Scoring

The CLI does not judge. Rubrics are natural language and the artifacts are
images; any scoring logic inside the tool would be a number pretending to
be a judgement. The division is:

- The agent (or the user) reads `note goal`, evaluates, and submits
  per-criterion scores.
- The CLI appends them to `scores.jsonl` against that node and computes the
  weighted sum from the current `goal.jsonl` criteria.

Scores attach to **attempt nodes**, never to goal nodes. A goal node's
score is derived as the **maximum** over the attempts that `target` it,
printed together with which attempt produced it. This repo's actual pattern
is "run several arms, adopt the best one", so max is the right reduction —
a mean would dilute a winning arm with its failed siblings, and latest
would hide it.

An attempt that is scored but `targets` nothing rolls up nowhere and would
otherwise be invisible, so `note goals` ends with an `(unassigned)` group
listing them — a scored attempt with no goal is a linking mistake, not a
category of work.

Each criterion is scored **0.0–1.0**.

Totals are always recomputed against the *current* `goal.jsonl`. If the
goal moves — a criterion renamed, added, or reweighted — a score line that
lacks the new criterion contributes 0 for it, and that criterion's weight
still counts in the normalization. Attempts judged under an older standard
therefore visibly drop, which is correct: the bar moved and they have not
been re-judged against it. `note goals` prints each score's timestamp so a
stale one is identifiable rather than merely suspicious.

## CLI commands

| Command | Behavior |
|---|---|
| `note init` | Create `<repo>/.git/notes/` + the four empty JSONL files. Idempotent: existing files are left untouched, never truncated |
| `note goal [--set "..." --criterion name:weight:rubric ...]` | With no args, print the current goal and criteria; with args, append a new line to `goal.jsonl`. Split on the **first two** colons only — rubric text routinely contains one |
| `note goal --history` | Print every goal revision, oldest first |
| `note add "content" [--type T] [--tags a,b]` | Append a node (auto-tagging current branch), print its id |
| `note link <from> <to> --rel <relation>` | Append an edge; errors if either id doesn't exist |
| `note score <id> name=0.8 name=0.6 ... [--note "why"]` | Append a score line for that node; print the normalized weighted total |
| `note goals` | List `type: goal` nodes with their derived max score and the attempt that set it |
| `note show <id>` | Print node content, its latest scores, and its incoming/outgoing edges |
| `note search <keyword>` | Case-insensitive substring match over content/tags |
| `note trace <id> [--up\|--down\|--both]` (default `--down`) | DFS from `<id>`, printed as an indented text tree; follows `targets`; visited-set guards against cycles |
| `note heads` / `note tails` | List derived in-degree-0 / out-degree-0 nodes, ignoring `targets` edges and skipping `type: goal` nodes |
| `note skill --install` | Copy the packaged `SKILL.md` to `~/.claude/skills/note/SKILL.md`, overwriting; print the path written |
| `note graph [--from <id>] [--depth N]` | Emit Graphviz DOT to `<store>/graph.dot`; if the `dot` binary is present, also render `.svg`, otherwise just leave the `.dot` file and print a note about installing graphviz |

`note graph` draws the final goal from `goal.jsonl` as a **virtual node at
the far right**, with every `type: goal` node pointing into it. It is not
stored — the file stays the single source of truth — but the rendering
shows the intended shape: attempts converge on branch goals, branch goals
converge on the one final goal.

Running any command other than `init` before `note init` has run errors
out telling the user to run it.

`note init` is **idempotent and never truncates**. With six worktrees on one
store, a second agent running `init` in its own worktree is not a fresh
start — it is a re-entry into a store that already holds everyone's work.
Truncating there would silently destroy the shared graph, which is the one
irreversible failure this design can produce. `init` creates only what is
missing and says so.

## Agent skill

A single `SKILL.md` documents the loop an agent follows: read `note goal`
→ do the work → `note add` the attempt → `note link ... --rel targets` to
the branch goal → `note score` with a stated justification per criterion.
The skill is the loop's script; the CLI is only its storage and arithmetic.

**It ships inside the Python package**, and `note skill --install` copies
it to `~/.claude/skills/note/SKILL.md`. Keeping it in the package means the
skill and the commands it describes move in the same commit — a renamed
flag cannot leave the skill describing a CLI that no longer exists. A
hand-copied file in the repo would drift the first time a command changed;
a `pipx` post-install hook would write to the home directory unasked.
`--install` overwrites, and reports the path it wrote.

## Error handling & testing

- Only defends against realistic mistakes: not being in a git repo, a
  store that hasn't been `init`ed, a `link` referencing a nonexistent id,
  a `score` naming a criterion absent from the current goal, a `score`
  aimed at a `type: goal` node (scores belong on attempts; an agent will
  try this), and a missing `dot` binary (a warning, not an error). Everything else surfaces
  Python's normal exceptions — this is a personal tool, not defending a
  trust boundary.
- Cycle *creation* is not prevented at `link` time (would require a full
  graph walk on every link for a case that's very unlikely to happen by
  accident). Cycle *traversal* is always safe because `trace`/`graph` use
  a visited-set.
- No pytest, no fixtures. Each command module carries a minimal
  `if __name__ == "__main__"` self-check exercising the
  goal → add → link → score → trace → graph happy path with `assert`.
  The concurrency path gets one check of its own: two forked processes
  each running `note add` under the lock must yield two distinct ids.

## Out of scope (deliberately deferred)

- **Loop engineering** (`note next` — suggesting the next thing to try
  from low-scoring or unexplored branches). The suggestion rules can only
  be invented right now, not derived; there is no score data to derive
  them from. Revisit once a few dozen scored attempts exist and the
  pattern is visible rather than imagined. Until then the agent skill
  carries the loop.
- **Sub-goals per worktree as separate files.** Rejected: it recreates
  exactly the six-divergent-copies problem that moving the store into
  `.git/` solved. Per-branch objectives are graph nodes instead.
- **A nested git repo inside the store.** See *Versioning* — append-only
  already loses nothing.
- Embedding/RAG-based semantic search — plain keyword search is enough
  to find a DFS seed node at this scale; revisit only if grep-style
  search actually fails to find things in practice.
- PyPI publication and PyInstaller/Homebrew binary distribution — the
  packaging structure supports both later without rework, but neither is
  built now.
- Explicit HEAD/TAIL storage or a separate "merge event" node type —
  both are fully derivable from the edge list.
