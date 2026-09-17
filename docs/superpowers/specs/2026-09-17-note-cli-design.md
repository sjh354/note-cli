# note-cli design

## Purpose

A CLI research-notebook tool for recording project decisions and their
branching/merging history as a graph. Complements, does not replace,
existing memory systems (`MEMORY.md`, `claude-mem`) — this tool is scoped
specifically to decision provenance: what was decided, why, what it
branched from, what it merged into.

## Architecture

- Standalone git repo at `~/projects/note-cli/`, packaged as a Python
  package with `pyproject.toml` and a console-script entry point.
- Installed globally via `pipx install -e .`, exposing a `note` command
  on `$PATH`.
- Data is NOT global: each invocation looks for a `.notes/` directory
  relative to the current working directory. Data lives in and is
  committed to the project repo being worked on, not in the tool's own
  repo.
- Chosen over standalone (PyInstaller) binaries: python3 is already
  present on macOS/Linux, so a bundled runtime buys little. `pyproject.toml`
  structure keeps a Homebrew-formula or PyInstaller path open later without
  restructuring.

## Data model & storage

- `.notes/nodes.jsonl` — one JSON object per line:
  `{"id": 1, "content": "...", "type": "decision", "tags": ["a","b"], "timestamp": "2026-09-17T12:00:00"}`
- `.notes/edges.jsonl` — one JSON object per line:
  `{"from": 1, "to": 2, "relation": "leads_to"}`
- `type` and `relation` are free-form strings, not enums. A short list of
  suggested relation names (e.g. `leads_to`, `supersedes`, `merged_from`,
  `conflicts_with`) is documented but not enforced.
- IDs are sequential integers, assigned as `(last id in nodes.jsonl) + 1`.
  No locking: single-user, sequential CLI usage is assumed.
- HEAD/TAIL and merge points are never stored explicitly. Every command
  that needs them loads `edges.jsonl`, builds an adjacency dict, and
  derives head nodes (in-degree 0) / tail nodes (out-degree 0) on the
  fly. A node with in-degree > 1 is a merge point — no separate concept
  needed.
- `note init` creates `.notes/` plus the two empty `.jsonl` files.
- JSONL (not SQLite) was chosen specifically so `.notes/` stays
  git-diffable and grep-able, since it's meant to be committed alongside
  the project and reviewed in PRs.

## CLI commands

| Command | Behavior |
|---|---|
| `note init` | Create `.notes/` + empty `nodes.jsonl`/`edges.jsonl` |
| `note add "content" [--type T] [--tags a,b]` | Append a node, print its id |
| `note link <from> <to> --rel <relation>` | Append an edge; errors if either id doesn't exist |
| `note show <id>` | Print node content plus its incoming/outgoing edges |
| `note search <keyword>` | Case-insensitive substring match over content/tags |
| `note trace <id> [--up\|--down\|--both]` (default `--down`) | DFS from `<id>`, printed as an indented text tree; visited-set guards against cycles |
| `note heads` / `note tails` | List derived in-degree-0 / out-degree-0 nodes |
| `note graph [--from <id>] [--depth N]` | Emit Graphviz DOT to `.notes/graph.dot`; if the `dot` binary is present, also render `.svg`, otherwise just leave the `.dot` file and print a note about installing graphviz |

Running any command other than `init` outside a directory with `.notes/`
errors out telling the user to run `note init`.

## Error handling & testing

- Only defends against realistic mistakes: missing `.notes/`, a `link`
  referencing a nonexistent id, and a missing `dot` binary (a warning,
  not an error). Everything else surfaces Python's normal exceptions —
  this is a personal tool, not defending a trust boundary.
- Cycle *creation* is not prevented at `link` time (would require a full
  graph walk on every link for a case that's very unlikely to happen by
  accident). Cycle *traversal* is always safe because `trace`/`graph` use
  a visited-set.
- No pytest, no fixtures. Each command module carries a minimal
  `if __name__ == "__main__"` self-check exercising the
  add → link → trace → graph happy path with `assert`.

## Out of scope (deliberately deferred)

- Embedding/RAG-based semantic search — plain keyword search is enough
  to find a DFS seed node at this scale; revisit only if grep-style
  search actually fails to find things in practice.
- PyPI publication and PyInstaller/Homebrew binary distribution — the
  packaging structure supports both later without rework, but neither is
  built now.
- Explicit HEAD/TAIL storage or a separate "merge event" node type —
  both are fully derivable from the edge list.
