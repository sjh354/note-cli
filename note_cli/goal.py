from note_cli import store

GOAL_FILE = "goal.jsonl"
SCORE_FILE = "scores.jsonl"


def history():
    return store.read(GOAL_FILE)


def current_goal():
    """Last line in FILE ORDER wins — appends are serialized by the write
    lock, so file order is a total order and timestamps are informational."""
    lines = history()
    return lines[-1] if lines else None


def set_goal(text, criteria):
    with store.write_lock():
        store.append(GOAL_FILE, {"goal": text, "criteria": criteria,
                                 "timestamp": store.now()})


SUPERSEDED = "superseded_by"


def superseded_ids(edges):
    """Nodes that have been corrected by a later one.

    Append-only never removes anything, so a superseded node keeps its goal
    link and its score. Both the rollup and the loop check have to skip them:
    otherwise a corrected-away attempt goes on competing for best, and a goal
    revision makes the check demand that it be re-judged.
    """
    return {e["from"] for e in edges if e["relation"] == SUPERSEDED}


def goal_revision(g):
    """Identity of a goal revision. `goal.jsonl` is append-only and written
    under the lock, so its timestamp identifies the revision."""
    return g["timestamp"] if g else None


def is_stale(score, g):
    """True when this score was judged against a different goal revision than
    the current one.

    Its total is still computed — against today's criteria — which is exactly
    why it has to be flagged: the number looks like a judgement and is
    arithmetic. A score line written before this field existed has no
    `goal_ts`, so it reads stale, which is the honest answer: we do not know
    what standard it was made against.
    """
    return score.get("goal_ts") != goal_revision(g)


def parse_criterion(s):
    parts = s.split(":", 2)          # first two colons only; rubrics contain colons
    if len(parts) != 3:
        raise SystemExit(f"--criterion wants name:weight:rubric, got {s!r}")
    name, weight, rubric = parts
    try:
        weight = float(weight)
    except ValueError:
        raise SystemExit(f"criterion {name!r}: weight {weight!r} is not a number")
    return {"name": name, "weight": weight, "rubric": rubric}


def weighted_total(scores, criteria):
    """Always computed against the CURRENT criteria. A score line that lacks a
    criterion contributes 0 for it and that criterion's weight still counts in
    the normalization, so an attempt judged under an older standard visibly
    drops — the bar moved and it has not been re-judged against it."""
    denom = sum(c["weight"] for c in criteria)
    if not denom:
        return 0.0
    return sum(c["weight"] * scores.get(c["name"], 0.0) for c in criteria) / denom


def latest_scores():
    """node id -> its last score line. A re-score replaces the previous
    judgement WHOLESALE; merging would make a node's real score depend on the
    order of every past line."""
    out = {}
    for line in store.read(SCORE_FILE):
        out[line["node"]] = line
    return out


def add_score(nid, scores, note=None):
    with store.write_lock():
        nodes = {n["id"]: n for n in store.read("nodes.jsonl")}
        if nid not in nodes:
            raise SystemExit(f"no node {nid}")
        if nodes[nid]["type"] == "goal":
            raise SystemExit(f"node {nid} is a goal — scores belong on attempts")
        g = current_goal()
        if not g:
            raise SystemExit("no goal set — run `note goal --set ...`")
        known = {c["name"] for c in g["criteria"]}
        unknown = sorted(set(scores) - known)
        if unknown:
            raise SystemExit(f"unknown criteria {unknown}; goal has {sorted(known)}")
        store.append(SCORE_FILE, {"node": nid, "scores": scores, "note": note,
                                  "goal_ts": goal_revision(g),
                                  "timestamp": store.now()})
        return weighted_total(scores, g["criteria"])


def rollup():
    """Per-goal best attempt, plus scored attempts that target nothing.

    Max, not mean or latest: the working pattern is "run several arms, adopt
    the best one". A mean would dilute a winning arm with its failed siblings.
    """
    nodes = store.read("nodes.jsonl")
    edges = store.read("edges.jsonl")
    g = current_goal()
    criteria = g["criteria"] if g else []
    latest = latest_scores()
    by_id = {n["id"]: n for n in nodes}

    corrected = superseded_ids(edges)
    targeted, assigned = {}, set()
    for e in edges:
        if e["relation"] == "targets":
            targeted.setdefault(e["to"], []).append(e["from"])
            assigned.add(e["from"])

    rows = []
    for n in nodes:
        if n["type"] != "goal":
            continue
        best = None
        for aid in targeted.get(n["id"], ()):
            if aid not in latest or aid in corrected:
                continue
            cand = (weighted_total(latest[aid]["scores"], criteria), aid,
                    latest[aid])
            if best is None or cand[0] > best[0]:
                best = cand
        rows.append((n, best))

    # a scored attempt with no goal is a linking mistake, not a category of
    # work — it must not simply vanish from the rollup
    unassigned = [(by_id[i], weighted_total(latest[i]["scores"], criteria),
                   latest[i])
                  for i in sorted(latest)
                  if i not in assigned and i in by_id and i not in corrected]
    return rows, unassigned


def unfinished():
    """Attempts that break the loop, as (untargeted, unscored, stale).

    Only `attempt` nodes are held to it — a decision or a plain note has
    nothing to score. This is what `note check` exits nonzero on, so a hook
    or an agent can gate on it instead of trusting itself to remember.

    `stale` is the one that used to pass silently: the attempt is linked and
    scored, but judged against a goal revision that is no longer current, so
    its total is arithmetic rather than judgement.
    """
    nodes = store.read("nodes.jsonl")
    edges = store.read("edges.jsonl")
    latest = latest_scores()
    g = current_goal()
    targeting = {e["from"] for e in edges if e["relation"] == "targets"}
    corrected = superseded_ids(edges)
    untargeted, unscored, stale = [], [], []
    for n in nodes:
        if n["type"] != "attempt" or n["id"] in corrected:
            continue
        if n["id"] not in targeting:
            untargeted.append(n)
        elif n["id"] not in latest:
            unscored.append(n)
        elif is_stale(latest[n["id"]], g):
            stale.append(n)
    return untargeted, unscored, stale


def demo():
    import os, subprocess, tempfile
    os.chdir(tempfile.mkdtemp())
    subprocess.run(["git", "init", "-q"], check=True)
    store.init()

    # rubric text routinely contains a colon: split on the first two only
    c = parse_criterion("legibility:0.3:readable at 512px: no clipping")
    assert c == {"name": "legibility", "weight": 0.3,
                 "rubric": "readable at 512px: no clipping"}, c
    try:
        parse_criterion("badinput")
        raise AssertionError("expected SystemExit")
    except SystemExit:
        pass

    crit = [{"name": "consistency", "weight": 3.0, "rubric": "style holds"},
            {"name": "legibility", "weight": 1.0, "rubric": "readable"}]
    set_goal("ship an education image generator", crit)
    assert current_goal()["goal"] == "ship an education image generator"

    # weights need not sum to 1 — they are normalized
    assert weighted_total({"consistency": 1.0, "legibility": 1.0}, crit) == 1.0
    assert weighted_total({"consistency": 1.0}, crit) == 0.75
    assert weighted_total({}, crit) == 0.0

    g = store.add_node("legible text", type="goal")
    a1 = store.add_node("arm B1_P1", type="attempt")
    a2 = store.add_node("arm B1_P2", type="attempt")
    orphan = store.add_node("unlinked try", type="attempt")
    store.add_edge(a1, g, "targets")
    store.add_edge(a2, g, "targets")

    assert round(add_score(a1, {"consistency": 0.4}), 9) == 0.3   # 3*0.4/4 is not exact
    assert add_score(a2, {"consistency": 1.0, "legibility": 1.0}) == 1.0
    add_score(orphan, {"legibility": 1.0})

    # re-score replaces wholesale: the omitted criterion counts 0, not its old value
    assert add_score(a2, {"legibility": 1.0}) == 0.25
    assert latest_scores()[a2]["scores"] == {"legibility": 1.0}

    try:
        add_score(g, {"consistency": 1.0})
        raise AssertionError("expected SystemExit for scoring a goal node")
    except SystemExit as e:
        assert "goal" in str(e), e
    try:
        add_score(a1, {"nonesuch": 1.0})
        raise AssertionError("expected SystemExit for an unknown criterion")
    except SystemExit as e:
        assert "nonesuch" in str(e), e

    rows, unassigned = rollup()
    assert len(rows) == 1
    node, best = rows[0]
    assert node["id"] == g
    assert round(best[0], 9) == 0.3 and best[1] == a1, best   # max; a2 fell on re-score
    assert [u[0]["id"] for u in unassigned] == [orphan], unassigned

    # orphan targets nothing; a1/a2 target g and are scored
    untargeted, unscored, stale = unfinished()
    assert [n["id"] for n in untargeted] == [orphan], untargeted
    assert unscored == [] and stale == [], (unscored, stale)

    fresh = store.add_node("just tried, not judged yet", type="attempt")
    store.add_edge(fresh, g, "targets")
    untargeted, unscored, stale = unfinished()
    assert [n["id"] for n in untargeted] == [orphan], untargeted
    assert [n["id"] for n in unscored] == [fresh], unscored
    assert stale == [], stale

    # a score carries the goal revision it was judged against
    assert latest_scores()[a1]["goal_ts"] == current_goal()["timestamp"]
    assert not is_stale(latest_scores()[a1], current_goal())

    # renaming a criterion must NOT silently leave a confident-looking number
    import time
    time.sleep(1)                       # timestamps are second-resolution
    set_goal("moved the bar", [{"name": "consistency", "weight": 3.0, "rubric": "x"},
                               {"name": "renamed", "weight": 1.0, "rubric": "y"}])
    assert is_stale(latest_scores()[a1], current_goal())
    untargeted, unscored, stale = unfinished()
    assert [n["id"] for n in stale] == [a1, a2], stale   # orphan is untargeted, fresh unscored

    # a re-score under the new goal clears it
    add_score(a1, {"consistency": 1.0})
    assert not is_stale(latest_scores()[a1], current_goal())
    _, _, stale = unfinished()
    assert [n["id"] for n in stale] == [a2], stale

    # a score line predating this feature has no goal_ts and must read stale
    assert is_stale({"scores": {}}, current_goal())

    # --- a corrected attempt must stop competing ---
    add_score(a2, {"consistency": 1.0, "renamed": 1.0})     # a2 is now the best
    rows, _ = rollup()
    assert rows[0][1][1] == a2, rows[0]

    fixed = store.supersede(a2, "arm B1_P2, corrected")
    rows, _ = rollup()
    best_id = rows[0][1][1] if rows[0][1] else None
    assert best_id != a2, "a superseded attempt must not win the rollup"
    assert best_id == a1, (best_id, a1)          # fixed is unscored, so a1 wins

    # and it must not be demanded back by the loop check either
    _, unscored, stale = unfinished()
    assert a2 not in [n["id"] for n in unscored] + [n["id"] for n in stale]
    assert fixed in [n["id"] for n in unscored], "the correction still needs judging"

    print("goal: ok")


if __name__ == "__main__":
    demo()
