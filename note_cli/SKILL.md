---
name: note
description: Use when working on a repo that has a note store — record each attempt in the decision graph and score it against the project's goal criteria before moving on.
---

# note

`note` keeps one decision graph and one goal per repo, in `<repo>/.git/notes/`.
Every git worktree of the repo shares that store, so what you record is visible
to agents working other branches in parallel.

## The loop

1. **Read the standard.** `note goal` prints the final goal and its weighted
   criteria, each with a one-line rubric. Score against those rubrics, never
   against a standard you invent.
2. **Do the work.**
3. **Record the attempt.** `note add "what you tried" --type attempt --tags arm-b1`
   prints its id. The current branch is tagged automatically.
4. **Point it at a goal.** `note link <attempt> <goal> --rel targets`. A scored
   attempt that targets nothing shows up under `(unassigned)` in `note goals` —
   that is a linking mistake, not a category of work.
5. **Score it.** `note score <attempt> consistency=0.8 legibility=0.6 --note "why"`.
   Each criterion is 0.0–1.0. The `--note` is where the justification goes;
   a score with no stated reason cannot be argued with later.

6. **Confirm the loop closed.** `note check` exits nonzero while any attempt
   targets no goal or carries no score, and names them. Run it before you
   consider a piece of work done.

## Rules

- **Never score a goal node.** Scores go on attempts. A goal's score is derived
  as the maximum over the attempts that target it.
- **Re-scoring replaces wholesale.** A criterion left out of a new score line
  counts as 0, not as its previous value. Submit the full set every time.
- **Only criteria named in the current goal are accepted.** If a rubric no
  longer fits the work, change the goal (`note goal --set ... --criterion ...`)
  rather than inventing a criterion at score time.
- **Totals are recomputed against the current goal**, so when the goal moves,
  every earlier score is marked `STALE` and `note check` fails until you
  re-score. A stale total is arithmetic, not judgement — do not compare arms
  on one. `note goal --set` tells you how many scores it just invalidated.

## Correcting a node

Nothing is ever edited in place. `note supersede <id> "corrected content"`
appends a new node and an edge `old -superseded_by-> new`, which moves the
frontier to the new node and takes the old one out of `note tails`. Type and
tags are inherited unless you pass new ones.

## Orientation

- `note status` — goal, criteria, per-goal best and the frontier, in one screen
- `note check` — what still breaks the loop (exit 1 if anything does)
- `note goals` — per-goal best attempt and which one set it
- `note tails` — the working frontier (goal nodes excluded)
- `note trace <id>` — what an attempt ultimately feeds
- `note trace <goal-id> --up` — which attempts feed a goal
- `note search <keyword>` — find a node to start from
