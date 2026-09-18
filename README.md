# note-cli

A decision-graph and goal notebook for a git repo. One store per repo, shared
by every worktree, kept in `<repo>/.git/notes/` — so it never appears in the
working tree and needs no `.gitignore` entry.

    pipx install -e .        # or: python -m pip install -e .
    note init
    note goal --set "ship an education image generator" \
      --criterion "consistency:3:the reference style holds across seeds" \
      --criterion "legibility:1:rendered text is readable at 512px"

    note add "legible text at 512px" --type goal          # -> 1
    note add "arm B1_P2" --type attempt --tags p2         # -> 2
    note link 2 1 --rel targets
    note score 2 consistency=1.0 legibility=0.8 --note "best so far"
    note goals

    note status                                           # everything at a glance
    note check                                            # exit 1 if the loop is open
    note supersede 2 "arm B1_P2, corrected"               # append-only correction

Design: [`docs/superpowers/specs/2026-09-17-note-cli-design.md`](docs/superpowers/specs/2026-09-17-note-cli-design.md)

For an agent working in this repo: `note skill --install`, then follow the
`note` skill.
