# TODO

Ranked by what bites first, not by what is interesting. Each item says what
was actually observed, not what might go wrong.

Done since the last pass, both shipped in 0.3.0: stale scores are now
detected and surfaced, and a superseded attempt no longer wins the rollup.
Item 3 below has lost its node half — `supersede` works properly now — and
keeps only the edge and goal-criterion halves.

Item 1 is done (unreleased): the store is its own git repo, and `note sync`
commits and pushes it once a remote is set.

---

## 2. Every listing dumps the whole store

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
item 1.

---

## 3. Append-only has an escape hatch for nodes, none for edges or criteria

- **A wrong edge is permanent.** `note link 2 1 --rel oops` is accepted and
  there is no `note unlink`. `note supersede` covers nodes only.
- **A goal cannot be edited in part.** Changing one weight means re-typing
  every `--criterion`, and a rubric typed slightly differently silently
  changes the standard everything is measured against. That now shows up as
  `STALE` rather than as a quietly wrong number (0.3.0), but it still means
  re-scoring everything over a typo.

**Fix:** `note unlink <from> <to> [--rel R]` appending a tombstone (stay
append-only — do not rewrite `edges.jsonl`), and `note goal --set-weight
name=N` / `--set-rubric name="..."` that copy the current goal forward with
one field changed.

**Do it when:** the first wrong edge or fat-fingered rubric actually happens.
Both are cheap then and speculative now.

---

## 4. Homebrew formula — now unblocked

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
