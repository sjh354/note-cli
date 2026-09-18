"""Two processes adding under the lock must produce two distinct ids.

Separate from store.demo() because it forks; run it directly:
    python -m note_cli._concurrency_check
"""
import os
import subprocess
import tempfile

from note_cli import store


def main():
    d = tempfile.mkdtemp()
    os.chdir(d)
    subprocess.run(["git", "init", "-q"], check=True)
    store.init()

    reads, writes = zip(*(os.pipe() for _ in range(8)))
    for i, w in enumerate(writes):
        if os.fork() == 0:
            nid = store.add_node(f"child {i}")
            os.write(w, str(nid).encode())
            os._exit(0)
    for w in writes:
        os.close(w)
    ids = []
    for r in reads:
        ids.append(int(os.read(r, 16)))
        os.close(r)
    for _ in writes:
        os.wait()

    assert len(set(ids)) == len(ids), f"duplicate ids under concurrency: {sorted(ids)}"
    assert sorted(ids) == list(range(1, len(ids) + 1)), sorted(ids)
    print("concurrency: ok")


if __name__ == "__main__":
    main()
