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
    print("store: ok")


if __name__ == "__main__":
    demo()
