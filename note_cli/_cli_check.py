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
    print("cli: ok")


if __name__ == "__main__":
    main_check()
