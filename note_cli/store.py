import fcntl
import json
import os
import subprocess
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache
from pathlib import Path

FILES = ("nodes.jsonl", "edges.jsonl", "goal.jsonl", "scores.jsonl")


def _git(*args):
    """Run a git command, returning stripped stdout; SystemExit on failure."""
    r = subprocess.run(["git", *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(r.stderr.strip() or f"git {' '.join(args)} failed")
    return r.stdout.strip()


@lru_cache(maxsize=1)
def store_dir():
    """<repo>/.git/notes — one store shared by every worktree of the repo.

    `--git-common-dir` prints a relative path from the main worktree and an
    absolute one from a linked worktree; realpath against cwd absorbs both.
    (`--path-format=absolute` would be cleaner but needs git >= 2.31.)
    """
    return Path(os.path.realpath(_git("rev-parse", "--git-common-dir"))) / "notes"


def require_store():
    d = store_dir()
    if not d.is_dir():
        raise SystemExit(f"no note store at {d} — run `note init`")
    return d


def init():
    """Create the store. Idempotent: existing files are never truncated.

    Six worktrees share one store, so a second agent's `init` is a re-entry
    into a store that already holds everyone's work, not a fresh start.
    """
    d = store_dir()
    d.mkdir(parents=True, exist_ok=True)
    created = []
    for name in FILES:
        f = d / name
        if not f.exists():
            f.touch()
            created.append(name)
    return d, created


@contextmanager
def write_lock():
    """Serialize every write path — each is a read-then-append that a
    concurrent write can invalidate."""
    d = require_store()
    with open(d / ".lock", "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield d
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def read(name):
    with open(require_store() / name) as fh:
        return [json.loads(line) for line in fh if line.strip()]


def append(name, obj):
    with open(require_store() / name, "a") as fh:
        fh.write(json.dumps(obj, ensure_ascii=False) + "\n")


def now():
    return datetime.now().isoformat(timespec="seconds")



def current_branch():
    """The branch this node was written from. In a shared store, "which arm
    is this" is otherwise lost. Detached HEAD (a worktree mid-rebase, for
    one) prints nothing, so fall back to the short SHA."""
    b = _git("branch", "--show-current")
    return b or _git("rev-parse", "--short", "HEAD")


def add_node(content, type="note", tags=()):
    with write_lock():
        nodes = read("nodes.jsonl")
        # max, not last: immune to a hand-edited file, same cost
        nid = max((n["id"] for n in nodes), default=0) + 1
        append("nodes.jsonl", {
            "id": nid,
            "content": content,
            "type": type,
            "tags": list(tags),
            "branch": current_branch(),
            "timestamp": now(),
        })
    return nid


def add_edge(src, dst, relation):
    with write_lock():
        ids = {n["id"] for n in read("nodes.jsonl")}
        for i in (src, dst):
            if i not in ids:
                raise SystemExit(f"no node {i}")
        append("edges.jsonl", {"from": src, "to": dst, "relation": relation})


def supersede(old, content, type=None, tags=()):
    """Correct a node. Append-only has no edit, so a correction is a new node
    plus an edge `old -superseded_by-> new`.

    That direction is deliberate. With `new -supersedes-> old` the old node
    would have out-degree 0 and surface in `tails` as the working frontier,
    which is backwards. This way the NEW node is the frontier and the
    corrected one drops out of it. Type and tags are inherited unless given.
    """
    with write_lock():
        nodes = read("nodes.jsonl")
        by_id = {n["id"]: n for n in nodes}
        if old not in by_id:
            raise SystemExit(f"no node {old}")
        nid = max((n["id"] for n in nodes), default=0) + 1
        append("nodes.jsonl", {
            "id": nid,
            "content": content,
            "type": type or by_id[old]["type"],
            "tags": list(tags) or list(by_id[old].get("tags") or []),
            "branch": current_branch(),
            "timestamp": now(),
        })
        append("edges.jsonl", {"from": old, "to": nid, "relation": "superseded_by"})
    return nid


def demo():
    import tempfile
    d = tempfile.mkdtemp()
    os.chdir(d)                      # chdir BEFORE any store call: store_dir is cached
    subprocess.run(["git", "init", "-q"], check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "config", "user.name", "t"], check=True)

    path, created = init()
    assert path == Path(os.path.realpath(".git")) / "notes", path
    assert sorted(created) == sorted(FILES), created

    # idempotent and non-truncating: the second init must preserve content
    append("nodes.jsonl", {"id": 1, "content": "survivor"})
    path2, created2 = init()
    assert path2 == path
    assert created2 == [], created2
    assert read("nodes.jsonl") == [{"id": 1, "content": "survivor"}]

    with write_lock() as locked:
        assert locked == path

    assert "T" in now()

    a = add_node("first attempt", type="attempt", tags=["arm-b1"])
    g = add_node("legible text at 512px", type="goal")
    assert (a, g) == (2, 3), (a, g)          # id 1 was written by hand above

    rows = {n["id"]: n for n in read("nodes.jsonl")}
    assert rows[a]["type"] == "attempt"
    assert rows[a]["tags"] == ["arm-b1"]
    assert rows[a]["branch"], "branch must never be empty"   # name varies by git config
    assert "timestamp" in rows[a]

    add_edge(a, g, "targets")
    assert read("edges.jsonl") == [{"from": a, "to": g, "relation": "targets"}]

    try:
        add_edge(a, 999, "leads_to")
        raise AssertionError("expected SystemExit for a nonexistent node")
    except SystemExit as e:
        assert "999" in str(e), e

    # detached HEAD must not produce an empty branch field
    subprocess.run(["git", "commit", "-q", "--allow-empty", "-m", "x"], check=True)
    head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "checkout", "-q", head], check=True)
    assert current_branch(), "detached HEAD must fall back to a short SHA"

    # a correction is a new node plus old -superseded_by-> new, so the NEW one
    # is the frontier and the old one drops out of tails
    new_id = supersede(a, "first attempt, corrected")
    rows = {n["id"]: n for n in read("nodes.jsonl")}
    assert rows[new_id]["content"] == "first attempt, corrected"
    assert rows[new_id]["type"] == rows[a]["type"], "type is inherited"
    assert rows[new_id]["tags"] == rows[a]["tags"], "tags are inherited"
    assert {"from": a, "to": new_id, "relation": "superseded_by"} in read("edges.jsonl")
    try:
        supersede(999, "nope")
        raise AssertionError("expected SystemExit")
    except SystemExit as e:
        assert "999" in str(e), e

    print("store: ok")


if __name__ == "__main__":
    demo()
