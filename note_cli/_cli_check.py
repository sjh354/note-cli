"""End-to-end drive of every command. Run: python -m note_cli._cli_check"""
import os
import subprocess
import tempfile

from note_cli.cli import main


def run(*args):
    main(list(args))


def main_check():
    os.chdir(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], check=True)

    try:
        run("heads")
        raise AssertionError("expected SystemExit before init")
    except SystemExit as e:
        assert "note init" in str(e), e

    run("init")
    run("init")                                   # idempotent, must not raise
    run("goal", "--set", "ship it",
        "--criterion", "consistency:3:style holds: across seeds",
        "--criterion", "legibility:1:readable")
    run("goal")
    run("goal", "--history")

    run("add", "legible text", "--type", "goal")           # id 1
    run("add", "arm B1_P1", "--type", "attempt", "--tags", "p1,ref")   # id 2
    run("add", "arm B1_P2", "--type", "attempt")           # id 3
    run("link", "2", "1", "--rel", "targets")
    run("link", "3", "1", "--rel", "targets")
    run("link", "2", "3", "--rel", "leads_to")
    run("score", "2", "consistency=0.4")
    run("score", "3", "consistency=1.0", "legibility=0.8", "--note", "best so far")
    run("goals")
    run("show", "3")        # 2 -leads_to-> 3 and nothing else: not yet a merge
    run("add", "arm B1_P3", "--type", "attempt")           # id 4
    run("link", "4", "3", "--rel", "leads_to")
    run("show", "3")        # now in-degree 2: must print the merge-point line
    run("search", "B1")
    run("trace", "2")
    run("trace", "1", "--up")
    run("heads")
    run("tails")
    run("graph")
    run("graph", "--from", "2", "--depth", "1")

    from note_cli import store
    assert (store.store_dir() / "graph.dot").exists()

    # `check` must exit nonzero while an attempt is untargeted or unscored
    run("add", "unlinked try", "--type", "attempt")         # id 5
    try:
        run("check")
        raise AssertionError("expected SystemExit(1) with a loose attempt")
    except SystemExit as e:
        assert e.code == 1, e.code
    run("link", "5", "1", "--rel", "targets")
    try:
        run("check")
        raise AssertionError("expected SystemExit(1) with an unscored attempt")
    except SystemExit as e:
        assert e.code == 1, e.code
    run("score", "5", "consistency=0.1")
    # node 4 was added earlier as a merge-point helper and never targeted a
    # goal — `check` caught that, which is the point of the command
    run("link", "4", "1", "--rel", "targets")
    run("score", "4", "consistency=0.5")
    run("check")                                            # now clean: must not raise

    # supersede: the new node becomes the frontier, the old drops out
    before = {n["id"] for n in graphtails()}
    run("supersede", "5", "unlinked try, corrected")         # id 6
    after = {n["id"] for n in graphtails()}
    assert 5 not in after and 6 in after, (before, after)

    run("status")

    # --version must report what the package metadata says, so a bug report
    # names a real release
    from note_cli import __version__
    try:
        run("--version")
        raise AssertionError("argparse should exit after --version")
    except SystemExit as e:
        assert e.code == 0, e.code
    import importlib.metadata as md
    assert __version__ == md.version("notegraph"), (__version__, md.version("notegraph"))

    print("cli: ok")


def graphtails():
    from note_cli import graph as g, store
    return g.tails(store.read("nodes.jsonl"), store.read("edges.jsonl"))


if __name__ == "__main__":
    main_check()
