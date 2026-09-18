import argparse
import shutil
from pathlib import Path

from note_cli import goal as goalmod
from note_cli import graph as graphmod
from note_cli import render, store


def _nodes_edges():
    return store.read("nodes.jsonl"), store.read("edges.jsonl")


def _line(n):
    tags = f" [{','.join(n['tags'])}]" if n.get("tags") else ""
    return f"  {n['id']:>4}  {n['type']:<10} {n['content']}{tags}  ({n.get('branch')})"


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
        goalmod.set_goal(args.set, criteria)
        print(f"goal set, {len(criteria)} criteria")
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


def cmd_goals(args):
    rows, unassigned = goalmod.rollup()
    for n, best in rows:
        if best:
            total, aid, ts = best
            print(f"{n['id']:>4}  {n['content']}\n        best {total:.3f} from #{aid} ({ts})")
        else:
            print(f"{n['id']:>4}  {n['content']}\n        (no scored attempts)")
    if unassigned:
        print("\n(unassigned) — scored but targeting no goal:")
        for n, total, ts in unassigned:
            print(f"{n['id']:>4}  {total:.3f}  {n['content']} ({ts})")


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
        print(f"  score: {total:.3f}  {s['scores']}  ({s['timestamp']})")
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
    _print_nodes("heads:", graphmod.heads(nodes, edges))


def cmd_tails(args):
    nodes, edges = _nodes_edges()
    _print_nodes("tails:", graphmod.tails(nodes, edges))


def cmd_graph(args):
    nodes, edges = _nodes_edges()
    if args.frm is not None:
        keep = graphmod.subgraph(args.frm, edges, args.depth)
        nodes = [n for n in nodes if n["id"] in keep]
        edges = [e for e in edges if e["from"] in keep and e["to"] in keep]
    src = render.dot_source(nodes, edges, goalmod.current_goal())
    dot_file, svg = render.write_graph(store.require_store(), src)
    print(f"wrote {dot_file}")
    if svg:
        print(f"wrote {svg}")
    else:
        print("graphviz `dot` not found — install it to also render an .svg")


def cmd_skill(args):
    src = Path(__file__).parent / "SKILL.md"
    dst = Path.home() / ".claude" / "skills" / "note" / "SKILL.md"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    print(f"wrote {dst}")


def build_parser():
    p = argparse.ArgumentParser(prog="note", description=__doc__)
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

    sub.add_parser("heads", help="in-degree-0 work nodes").set_defaults(fn=cmd_heads)
    sub.add_parser("tails", help="the working frontier").set_defaults(fn=cmd_tails)

    gr = sub.add_parser("graph", help="emit Graphviz DOT")
    gr.add_argument("--from", dest="frm", type=int)
    gr.add_argument("--depth", type=int)
    gr.set_defaults(fn=cmd_graph)

    sk = sub.add_parser("skill", help="install the agent skill")
    sk.add_argument("--install", action="store_true", required=True)
    sk.set_defaults(fn=cmd_skill)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.fn(args)
