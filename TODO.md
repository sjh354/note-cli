# TODO

## The store dies with the machine

`<repo>/.git/notes/` is not carried by `git push` and does not survive a
re-clone. The spec accepts that as a cost, and append-only means nothing is
ever *overwritten* — but neither fact survives a dead disk, and the whole
point of the store is that months of decisions accumulate in it.

Options, in order of preference:

- Make the store its own git repo and add `note sync` (commit + push). Real
  backup and machine-to-machine sharing. The spec rejected a nested git on the
  grounds that "append-only already loses nothing" — that argument does not
  cover hardware failure, which is why this is still open.
- `note export` / `note import` over a single rolled-up JSONL. Lazier, but
  backup becomes a thing a human has to remember.

**Do it when:** the store holds enough that losing it would hurt — call it 50
nodes. Not before.

## `note next` — loop engineering

Suggest what to try next: the lowest-scoring criterion, a goal with no attempts,
an arm that was never followed up.

**Do it when:** a few dozen scored attempts exist. The rules have to be derived
from what the scores actually look like; inventing them now means inventing
them blind. Until then `SKILL.md` carries the loop and `note check` enforces it.

## Smaller, unranked

- `note graph --depth` only walks downward. Upward depth would need `--up`.
- `note search` is substring-only. Deferred in the spec pending evidence that
  it actually fails to find things.
