# TODO

Ranked by what bites first, not by what is interesting. Each item says what
was actually observed, not what might go wrong.

---

## 1. A stale score is silently wrong, and `note check` calls it clean

**The worst one, because it corrupts the tool's whole claim.** Totals are
recomputed against the *current* goal — that is the design and it is correct —
but nothing marks a score that predates a goal revision.

Observed: an attempt scored `a=1.0 b=1.0` under a two-criterion goal reads
`best 1.000`. Rename `b` to `c` in the goal and the same attempt silently reads
`best 0.500`. `note check` then reports **`clean: every attempt targets a goal
and carries a score`** — the number is wrong and the one command whose job is
to catch an open loop says everything is fine.

Anyone comparing arms after a goal revision is reading arithmetic, not
judgement, and has no way to tell which is which.

**Fix:** stamp each score line with the goal revision it was made against
(`goal.jsonl` already has a `timestamp` — use it as the revision id), then:

- `note check` reports attempts scored against an older goal revision and
  exits nonzero, the same as an unscored one.
- `note goals` marks a stale row rather than printing a confident number.
- `note goal --set` says how many scores it just invalidated.

**Do it:** next. The failure is silent and the data is already there.

---

## 2. The store dies with the machine

`<repo>/.git/notes/` is not carried by `git push` and does not survive a
re-clone. The spec accepts that as a cost, and append-only means nothing is
ever *overwritten* — but neither fact survives a dead disk, and the point of
the store is that months of decisions accumulate in it.

- **Preferred:** make the store its own git repo, add `note sync` (commit +
  push). Real backup plus machine-to-machine sharing. The spec rejected a
  nested git because "append-only already loses nothing" — that argument does
  not cover hardware failure, which is why this is still open.
- **Lazier:** `note export` / `note import` over one rolled-up JSONL. Backup
  becomes something a human has to remember.

**Do it when:** losing the store would hurt — call it 50 nodes.

---

## 3. Every listing dumps the whole store

Observed at 205 nodes: `note tails` printed 201 lines and `note graph` emitted
a 203-node DOT file. No pagination, no filter, no limit.

Disk is not the problem — 205 nodes is 40K. **Legibility is.** The commands
meant for orientation are the first to stop orienting.

**Fix, cheapest first:**

- `--branch <name>` on the listing commands. The field is already on every
  node and is the filter that matches how the work is actually split.
- `--limit N` with newest first.
- `note graph` defaulting to a bounded subgraph instead of everything.

**Do it when:** a real store passes ~50 nodes, which is the same threshold as
item 2.

---

## 4. Append-only has an escape hatch for nodes, none for edges or criteria

- **A wrong edge is permanent.** `note link 2 1 --rel oops` is accepted and
  there is no `note unlink`. `note supersede` covers nodes only.
- **A goal cannot be edited in part.** Changing one weight means re-typing
  every `--criterion`, and a rubric typed slightly differently silently
  changes the standard everything is measured against — see item 1 for what
  that costs.

**Fix:** `note unlink <from> <to> [--rel R]` appending a tombstone (stay
append-only — do not rewrite `edges.jsonl`), and `note goal --set-weight
name=N` / `--set-rubric name="..."` that copy the current goal forward with
one field changed.

**Do it when:** the first wrong edge or fat-fingered rubric actually happens.
Both are cheap then and speculative now.

---

## 5. Homebrew formula — now unblocked

`0.2.0` is on PyPI, so the sdist URL and sha256 that a formula needs exist.
With zero runtime dependencies there are no `resource` blocks to generate, so
`virtualenv_install_with_resources` is nearly trivial.

Worth asking first whether it earns its keep: `pipx install notegraph` already
works everywhere, and a formula is a second thing to bump on every release.

A standalone binary (PyInstaller) stays deferred for the spec's reason —
python3 is already present on macOS and Linux, so a bundled runtime buys
little.

---

## Still correctly deferred

**`note next` — loop engineering.** Suggest what to try next: the
lowest-scoring criterion, a goal with no attempts, an arm never followed up.
The rules have to be *derived* from what real scores look like; inventing them
now means inventing them blind. `SKILL.md` carries the loop and `note check`
enforces it meanwhile.

**Do it when:** a few dozen scored attempts exist.

**Semantic search.** `note search` is substring-only. The spec deferred it
pending evidence that grep-style search actually fails to find things. No such
evidence yet.

---

## Small and unranked

- `note graph --depth` only walks downward; upward depth would need `--up`.
- The wheel ships `_cli_check.py`, `_concurrency_check.py` and every `demo()`.
  Harmless (underscore-prefixed, tiny) and unavoidable while the spec's test
  vehicle is `__main__` self-checks — but it is why the package is not as lean
  as its line count suggests.
- `requires-python = ">=3.9"` is conservative: the self-checks also pass on
  3.8. 3.8 is EOL, so the floor stays where it is; noted so nobody re-derives
  it.
- No shell completion.
