TARGETS = "targets"
GOAL_TYPE = "goal"


def adjacency(edges):
    """Work-graph adjacency. `targets` edges are excluded so that merge
    detection (in-degree > 1) sees only real convergence of work."""
    out, inn = {}, {}
    for e in edges:
        if e["relation"] == TARGETS:
            continue
        out.setdefault(e["from"], []).append(e["to"])
        inn.setdefault(e["to"], []).append(e["from"])
    return out, inn


def heads(nodes, edges):
    _, inn = adjacency(edges)
    return [n for n in nodes if n["type"] != GOAL_TYPE and not inn.get(n["id"])]


def tails(nodes, edges):
    """The working frontier.

    Two filters, not one. Dropping `targets` edges is not enough: a goal node
    whose only edges are inbound `targets` becomes isolated in the filtered
    graph — in-degree 0 AND out-degree 0 — so it would surface in heads and
    tails both. Skipping goal-typed nodes is what keeps this list meaningful.
    """
    out, _ = adjacency(edges)
    return [n for n in nodes if n["type"] != GOAL_TYPE and not out.get(n["id"])]


def merges(nodes, edges):
    _, inn = adjacency(edges)
    return [n for n in nodes if len(inn.get(n["id"], ())) > 1]


def _directed(edges, direction):
    """Neighbour map over ALL edges — traversal ignores the topology filters."""
    fwd, bwd = {}, {}
    for e in edges:
        fwd.setdefault(e["from"], []).append((e["to"], e["relation"]))
        bwd.setdefault(e["to"], []).append((e["from"], e["relation"]))
    if direction == "down":
        return [fwd]
    if direction == "up":
        return [bwd]
    return [fwd, bwd]


def trace(root, edges, direction="down"):
    """DFS from root, as nested (node_id, [(relation, child), ...]).

    The seen-set is per path, not global: it stops cycles from recursing
    forever while still letting a node legitimately reachable by two routes
    show under both.
    """
    maps = _directed(edges, direction)

    def walk(nid, seen):
        if nid in seen:
            return (nid, [])
        seen = seen | {nid}
        kids = [(rel, walk(m, seen)) for mp in maps for m, rel in mp.get(nid, ())]
        return (nid, kids)

    return walk(root, frozenset())


def subgraph(root, edges, depth):
    """Node ids reachable downward from root within `depth` hops (None = all).
    Follows every relation, `targets` included."""
    (fwd,) = _directed(edges, "down")
    seen, frontier, hops = {root}, [root], 0
    while frontier and (depth is None or hops < depth):
        nxt = []
        for nid in frontier:
            for m, _rel in fwd.get(nid, ()):
                if m not in seen:
                    seen.add(m)
                    nxt.append(m)
        frontier, hops = nxt, hops + 1
    return seen


def demo():
    nodes = [
        {"id": 1, "type": "note"},
        {"id": 2, "type": "note"},
        {"id": 3, "type": "note"},
        {"id": 4, "type": "goal"},
    ]
    edges = [
        {"from": 1, "to": 3, "relation": "leads_to"},
        {"from": 2, "to": 3, "relation": "leads_to"},
        {"from": 3, "to": 4, "relation": "targets"},
        {"from": 1, "to": 4, "relation": "targets"},
    ]

    out, inn = adjacency(edges)
    assert out == {1: [3], 2: [3]}, out          # targets edges excluded
    assert inn == {3: [1, 2]}, inn

    assert [n["id"] for n in heads(nodes, edges)] == [1, 2]
    # 4 is a goal and is isolated once targets are dropped: it must appear in
    # NEITHER heads nor tails, which edge-filtering alone would not achieve
    assert [n["id"] for n in tails(nodes, edges)] == [3]
    assert [n["id"] for n in merges(nodes, edges)] == [3]

    # trace follows targets; topology filters do not apply to traversal
    assert trace(1, edges) == (1, [("leads_to", (3, [("targets", (4, []))])),
                                   ("targets", (4, []))])
    assert trace(4, edges, "up") == (4, [("targets", (3, [("leads_to", (1, [])),
                                                         ("leads_to", (2, []))])),
                                        ("targets", (1, []))])

    cyc = [{"from": 1, "to": 2, "relation": "r"}, {"from": 2, "to": 1, "relation": "r"}]
    assert trace(1, cyc) == (1, [("r", (2, [("r", (1, []))]))])   # terminates

    assert subgraph(1, edges, None) == {1, 3, 4}
    assert subgraph(1, edges, 1) == {1, 3, 4}
    assert subgraph(1, edges, 0) == {1}
    print("graph: ok")


if __name__ == "__main__":
    demo()
