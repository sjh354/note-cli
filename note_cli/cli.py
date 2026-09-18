import argparse
import shutil
import sys
from pathlib import Path

if not hasattr(__import__("os"), "fork"):
    # store.py locks with fcntl.flock, which Windows has no equivalent of.
    # pip installs regardless of the POSIX classifier, so say so plainly
    # instead of letting `import fcntl` raise ModuleNotFoundError.
    sys.exit("note requires a POSIX system (Linux, macOS, WSL): it locks the "
             "store with fcntl.flock, which Windows does not provide.")

from note_cli import __version__
from note_cli import goal as goalmod
from note_cli import graph as graphmod
from note_cli import render, store


def _nodes_edges():
    return store.read("nodes.jsonl"), store.read("edges.jsonl")


def _line(n):
    tags = f" [{','.join(n['tags'])}]" if n.get("tags") else ""
    return f"  {n['id']:>4}  {n['type']:<10} {n['content']}{tags}  ({n.get('branch')})"


def _filter_nodes(nodes, branch=None, limit=None):
    if branch:
        nodes = [n for n in nodes if n.get("branch") == branch]
    if limit is not None:
        nodes = list(reversed(nodes))[:limit]     # newest first
    return nodes


def _print_nodes(title, nodes):
    print(title)
    for n in nodes:
        print(_line(n))
    if not nodes:
        print("  (none)")


def cmd_init(args):
    path, created = store.init()
    print(f"store: {path}")
    print(f"created: {', '.join(created)}" if created else "already initialized")


def cmd_goal(args):
    if args.history:
        for i, g in enumerate(goalmod.history(), 1):
            print(f"{i}. [{g['timestamp']}] {g['goal']}")
            for c in g["criteria"]:
                print(f"     {c['weight']:<5} {c['name']}: {c['rubric']}")
        return
    if args.set is not None:
        criteria = [goalmod.parse_criterion(c) for c in (args.criterion or [])]
        if not criteria:
            raise SystemExit("--set needs at least one --criterion name:weight:rubric")
        was_fresh = [s for s in goalmod.latest_scores().values()
                     if not goalmod.is_stale(s, goalmod.current_goal())]
        goalmod.set_goal(args.set, criteria)
        print(f"goal set, {len(criteria)} criteria")
        if was_fresh:
            print(f"{len(was_fresh)} score(s) now judged against an older goal — "
                  f"`note check` lists them")
        return
    g = goalmod.current_goal()
    if not g:
        raise SystemExit("no goal set — run `note goal --set ... --criterion ...`")
    print(g["goal"])
    denom = sum(c["weight"] for c in g["criteria"])
    for c in g["criteria"]:
        print(f"  {c['weight'] / denom:>5.0%}  {c['name']}: {c['rubric']}")


def cmd_add(args):
    tags = args.tags.split(",") if args.tags else []
    print(store.add_node(args.content, type=args.type, tags=tags))


def cmd_link(args):
    store.add_edge(args.src, args.dst, args.rel)
    print(f"{args.src} -{args.rel}-> {args.dst}")


def cmd_score(args):
    scores = {}
    for pair in args.pairs:
        if "=" not in pair:
            raise SystemExit(f"want name=value, got {pair!r}")
        k, v = pair.split("=", 1)
        try:
            scores[k] = float(v)
        except ValueError:
            raise SystemExit(f"{k}: {v!r} is not a number")
        if not 0.0 <= scores[k] <= 1.0:
            raise SystemExit(f"{k}: scores are 0.0-1.0, got {scores[k]}")
    print(f"{goalmod.add_score(args.id, scores, args.note):.3f}")


def _stale_mark(score, g):
    return "  STALE — judged against an older goal" if goalmod.is_stale(score, g) else ""


def cmd_goals(args):
    rows, unassigned = goalmod.rollup()
    g = goalmod.current_goal()
    for n, best in rows:
        if best:
            total, aid, score = best
            mark = _stale_mark(score, g)
            print(f"{n['id']:>4}  {n['content']}\n"
                  f"        best {total:.3f} from #{aid} ({score['timestamp']}){mark}")
        else:
            print(f"{n['id']:>4}  {n['content']}\n        (no scored attempts)")
    if unassigned:
        print("\n(unassigned) — scored but targeting no goal:")
        for n, total, score in unassigned:
            print(f"{n['id']:>4}  {total:.3f}  {n['content']} "
                  f"({score['timestamp']}){_stale_mark(score, g)}")


def cmd_supersede(args):
    tags = args.tags.split(",") if args.tags else []
    print(store.supersede(args.id, args.content, type=args.type, tags=tags))


def cmd_check(args):
    """Exit nonzero while any attempt is loose, so a hook or an agent can gate
    on it rather than trusting itself to remember the loop."""
    untargeted, unscored, stale = goalmod.unfinished()
    if not untargeted and not unscored and not stale:
        print("clean: every attempt targets a goal and is scored against the current one")
        return
    if untargeted:
        print("attempts targeting no goal — `note link <id> <goal> --rel targets`:")
        for n in untargeted:
            print(_line(n))
    if unscored:
        print("attempts with no score — `note score <id> name=0.0-1.0`:")
        for n in unscored:
            print(_line(n))
    if stale:
        print("attempts judged against an older goal — their totals are "
              "arithmetic, not judgement. Re-score them:")
        for n in stale:
            print(_line(n))
    raise SystemExit(1)


def cmd_status(args):
    g = goalmod.current_goal()
    if not g:
        print("no goal set — run `note goal --set ... --criterion ...`")
    else:
        print(g["goal"])
        denom = sum(c["weight"] for c in g["criteria"])
        for c in g["criteria"]:
            print(f"  {c['weight'] / denom:>5.0%}  {c['name']}: {c['rubric']}")
    print()
    cmd_goals(args)
    nodes, edges = _nodes_edges()
    _print_nodes("\nfrontier:", graphmod.tails(nodes, edges))


def cmd_show(args):
    nodes, edges = _nodes_edges()
    by_id = {n["id"]: n for n in nodes}
    if args.id not in by_id:
        raise SystemExit(f"no node {args.id}")
    n = by_id[args.id]
    print(f"#{n['id']} [{n['type']}] {n['content']}")
    print(f"  tags: {', '.join(n.get('tags') or []) or '-'}")
    print(f"  branch: {n.get('branch')}   {n['timestamp']}")
    s = goalmod.latest_scores().get(args.id)
    if s:
        g = goalmod.current_goal()
        total = goalmod.weighted_total(s["scores"], g["criteria"] if g else [])
        print(f"  score: {total:.3f}  {s['scores']}  ({s['timestamp']})"
              f"{_stale_mark(s, g)}")
        if s.get("note"):
            print(f"         {s['note']}")
    if args.id in {m["id"] for m in graphmod.merges(nodes, edges)}:
        print("  (merge point: two or more lines of work converge here)")
    for e in edges:
        if e["from"] == args.id:
            print(f"  -> {e['to']:<4} {e['relation']}")
        if e["to"] == args.id:
            print(f"  <- {e['from']:<4} {e['relation']}")


def cmd_search(args):
    k = args.keyword.lower()
    nodes, _ = _nodes_edges()
    _print_nodes(f"matches for {args.keyword!r}:",
                 [n for n in nodes
                  if k in n["content"].lower()
                  or any(k in t.lower() for t in n.get("tags") or [])])


def cmd_trace(args):
    nodes, edges = _nodes_edges()
    by_id = {n["id"]: n for n in nodes}
    if args.id not in by_id:
        raise SystemExit(f"no node {args.id}")

    def show(tree, depth, rel=None):
        nid, kids = tree
        n = by_id.get(nid)
        arrow = f"-{rel}-> " if rel else ""
        print("  " * depth + f"{arrow}#{nid} {n['content'] if n else '?'}")
        for r, kid in kids:
            show(kid, depth + 1, r)

    show(graphmod.trace(args.id, edges, args.direction), 0)


def cmd_heads(args):
    nodes, edges = _nodes_edges()
    heads = _filter_nodes(graphmod.heads(nodes, edges), args.branch, args.limit)
    _print_nodes("heads:", heads)


def cmd_tails(args):
    nodes, edges = _nodes_edges()
    tails = _filter_nodes(graphmod.tails(nodes, edges), args.branch, args.limit)
    _print_nodes("tails:", tails)


DEFAULT_GRAPH_LIMIT = 50


def cmd_graph(args):
    nodes, edges = _nodes_edges()
    if args.frm is not None:
        keep = graphmod.subgraph(args.frm, edges, args.depth)
    elif args.all:
        keep = None
    else:
        limit = args.limit or DEFAULT_GRAPH_LIMIT
        keep = {n["id"] for n in nodes[-limit:]}
    if args.branch:
        branch_ids = {n["id"] for n in nodes if n.get("branch") == args.branch}
        keep = branch_ids if keep is None else keep & branch_ids
    if keep is not None:
        kept_nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges if e["from"] in keep and e["to"] in keep]
        if len(kept_nodes) < len(nodes):
            print(f"{len(kept_nodes)} of {len(nodes)} nodes — "
                  f"--all for everything, --branch/--from/--limit to narrow further")
        nodes = kept_nodes
    src = render.dot_source(nodes, edges, goalmod.current_goal())
    dot_file, svg = render.write_graph(store.require_store(), src)
    print(f"wrote {dot_file}")
    if svg:
        print(f"wrote {svg}")
    else:
        print("graphviz `dot` not found — install it to also render an .svg")


def cmd_sync(args):
    changed = store.sync()
    print("synced" + (" (committed local changes)" if changed else " (nothing new)"))


def cmd_skill(args):
    src = Path(__file__).parent / "SKILL.md"
    dst = Path.home() / ".claude" / "skills" / "note" / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"wrote {dst}")


def build_parser():
    p = argparse.ArgumentParser(prog="note", description=__doc__)
    p.add_argument("--version", action="version", version=f"note {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init", help="create the store").set_defaults(fn=cmd_init)

    g = sub.add_parser("goal", help="show or set the final goal")
    g.add_argument("--set")
    g.add_argument("--criterion", action="append", metavar="name:weight:rubric")
    g.add_argument("--history", action="store_true")
    g.set_defaults(fn=cmd_goal)

    a = sub.add_parser("add", help="append a node")
    a.add_argument("content")
    a.add_argument("--type", default="note")
    a.add_argument("--tags")
    a.set_defaults(fn=cmd_add)

    ln = sub.add_parser("link", help="append an edge")
    ln.add_argument("src", type=int)
    ln.add_argument("dst", type=int)
    ln.add_argument("--rel", required=True)
    ln.set_defaults(fn=cmd_link)

    sc = sub.add_parser("score", help="score an attempt against the goal criteria")
    sc.add_argument("id", type=int)
    sc.add_argument("pairs", nargs="+", metavar="name=0.0-1.0")
    sc.add_argument("--note")
    sc.set_defaults(fn=cmd_score)

    sub.add_parser("goals", help="per-goal best attempt").set_defaults(fn=cmd_goals)
    sub.add_parser("status", help="goal, criteria, best attempts and frontier"
                   ).set_defaults(fn=cmd_status)
    sub.add_parser("check", help="exit 1 if any attempt is untargeted or unscored"
                   ).set_defaults(fn=cmd_check)

    sp = sub.add_parser("supersede", help="correct a node with a new one")
    sp.add_argument("id", type=int)
    sp.add_argument("content")
    sp.add_argument("--type")
    sp.add_argument("--tags")
    sp.set_defaults(fn=cmd_supersede)

    sh = sub.add_parser("show", help="one node in full")
    sh.add_argument("id", type=int)
    sh.set_defaults(fn=cmd_show)

    se = sub.add_parser("search", help="substring match over content and tags")
    se.add_argument("keyword")
    se.set_defaults(fn=cmd_search)

    tr = sub.add_parser("trace", help="DFS from a node")
    tr.add_argument("id", type=int)
    tr.add_argument("--up", dest="direction", action="store_const", const="up")
    tr.add_argument("--down", dest="direction", action="store_const", const="down")
    tr.add_argument("--both", dest="direction", action="store_const", const="both")
    tr.set_defaults(fn=cmd_trace, direction="down")

    hd = sub.add_parser("heads", help="in-degree-0 work nodes")
    hd.add_argument("--branch")
    hd.add_argument("--limit", type=int)
    hd.set_defaults(fn=cmd_heads)

    tl = sub.add_parser("tails", help="the working frontier")
    tl.add_argument("--branch")
    tl.add_argument("--limit", type=int)
    tl.set_defaults(fn=cmd_tails)

    gr = sub.add_parser("graph", help="emit Graphviz DOT")
    gr.add_argument("--from", dest="frm", type=int)
    gr.add_argument("--depth", type=int)
    gr.add_argument("--branch")
    gr.add_argument("--limit", type=int,
                     help=f"newest N nodes (default {DEFAULT_GRAPH_LIMIT} unless --from/--all)")
    gr.add_argument("--all", action="store_true", help="no bound — the whole store")
    gr.set_defaults(fn=cmd_graph)

    sub.add_parser("sync", help="commit and push the store's own git repo"
                   ).set_defaults(fn=cmd_sync)

    sk = sub.add_parser("skill", help="install the agent skill")
    sk.add_argument("--install", action="store_true", required=True)
    sk.set_defaults(fn=cmd_skill)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)


if __name__ == "__main__":
    main()
