# Changelog

## 0.4.1 — 2026-09-18

- **Fixed:** `note graph --limit 0` ignored the limit and rendered every node.
  `args.limit or DEFAULT_GRAPH_LIMIT` treated `0` as falsy and fell back to
  the default; `nodes[-limit:]` would have shown everything anyway since
  `-0 == 0` in Python. Found by an `open-code-review` delegation-mode review
  of the 0.4.0 diff.

## 0.4.0 — 2026-09-18

- **The store survives a dead disk.** `note init` now makes the store its own
  git repo (separate from the outer project's), and `note sync` commits and
  pushes it once a remote is added. Previously `<repo>/.git/notes/` lived and
  died with the outer repo's working copy — `git push` on the outer repo never
  touches it.
- **Orientation commands stop dumping the whole store.** `note heads` and
  `note tails` take `--branch <name>` and `--limit N` (newest first). `note
  graph` now defaults to the newest 50 nodes instead of every node ever
  recorded; `--all` opts back into everything, `--branch` narrows further.
- **A wrong edge or a typo'd rubric no longer means living with it.** `note
  unlink <from> <to> [--rel R]` appends a tombstone rather than rewriting
  `edges.jsonl`. `note goal --set-weight name=N` / `--set-rubric
  name="..."` copy the current goal forward with one criterion field changed,
  instead of retyping every `--criterion`. Both bump the goal revision like
  `--set` does, so freshly-scored attempts read `STALE` again.

## 0.3.0 — 2026-09-18

Two silent wrong-number bugs. In both, the tool reported a confident total
that was arithmetic rather than judgement, and every test passed.

- **Stale scores are now visible.** Totals have always been recomputed against
  the current goal, but nothing marked a score made against an older revision:
  renaming a criterion silently moved an attempt from `1.000` to `0.500` while
  `note check` still reported everything clean. Score lines now carry the goal
  revision they were judged against; `note check` fails on a stale one,
  `note goals` and `note show` mark it, and `note goal --set` reports how many
  scores it just invalidated. A score written before this release has no
  revision recorded and reads stale, which is the honest answer.
- **A corrected attempt stops competing.** `note supersede` created the new
  node but left the `targets` edge on the old one, which kept its score too —
  so `note goals` could report an attempt that had been corrected away as the
  best one. Corrections now inherit the goal links, and both the rollup and
  `note check` skip a superseded node. Found by the stale-score check added
  above, in this project's own end-to-end run.

## 0.2.0 — 2026-09-18

- `note supersede <id> "content"` — append-only has no edit, so a correction is
  a new node plus `old -superseded_by-> new`. That direction keeps the new node
  as the frontier and drops the corrected one out of `note tails`.
- `note check` — exits 1 naming every `attempt` node that targets no goal or
  carries no score, so a git hook or an agent's loop can gate on it.
- `note status` — goal, criteria, per-goal best attempt and the frontier in one
  screen.
- `note --version`.
- Fails fast with an explanation on non-POSIX systems instead of raising
  `ModuleNotFoundError: fcntl`.
- Packaging: MIT license, full PyPI metadata, CI across Python 3.9–3.13.
- Renamed the PyPI distribution to **notegraph**; PyPI rejects `note-cli` as
  too similar to the existing `notecli`. The import package (`note_cli`) and
  the command (`note`) are unchanged.

## 0.1.0 — 2026-09-18

First release.

- A decision graph (`note add` / `link` / `trace` / `heads` / `tails` / `graph`)
  and a goal layer (`note goal` / `score` / `goals`) in one store per repo.
- The store lives at `<repo>/.git/notes/`, so every git worktree of a repo
  shares it and it never appears in the working tree.
- Every write path takes an `fcntl.flock`; nodes are tagged with the branch
  they were written from.
- `note skill --install` installs the packaged agent skill.
