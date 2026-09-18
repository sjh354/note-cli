# TODO

Ranked by what bites first, not by what is interesting. Each item says what
was actually observed, not what might go wrong.

Done since the last pass, both shipped in 0.3.0: stale scores are now
detected and surfaced, and a superseded attempt no longer wins the rollup.

Item 1 is done (unreleased): the store is its own git repo, and `note sync`
commits and pushes it once a remote is set.

Item 2 is done (unreleased): `heads`/`tails` take `--branch`/`--limit`, and
`graph` defaults to the newest 50 nodes instead of the whole store.

Item 3 is done (unreleased): `note unlink` tombstones a wrong edge, and
`note goal --set-weight`/`--set-rubric` edit one criterion field without
retyping the rest.

---

## 3. Homebrew formula — now unblocked

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
