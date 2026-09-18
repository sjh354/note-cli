# Changelog

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
