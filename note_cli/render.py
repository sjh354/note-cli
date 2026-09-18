import shutil
import subprocess

MAX_LABEL = 40


def _label(text):
    """DOT string literals cannot hold a double quote; swap for a single."""
    t = text[:MAX_LABEL].replace('"', "'").replace("\n", " ")
    return t + ("\u2026" if len(text) > MAX_LABEL else "")


def dot_source(nodes, edges, goal):
    """The final goal is drawn as a VIRTUAL node at the far right — it is
    never stored, so goal.jsonl stays the single source of truth, but the
    rendering shows the intended shape: attempts converge on branch goals,
    branch goals converge on the one final goal."""
    out = ["digraph notes {", "  rankdir=LR;"]
    for n in nodes:
        shape = "box" if n["type"] == "goal" else "ellipse"
        out.append(f'  n{n["id"]} [label="{n["id"]}: {_label(n["content"])}" shape={shape}];')
    for e in edges:
        attrs = f'label="{e["relation"]}"'
        if e["relation"] == "targets":
            attrs += ", style=dashed"
        out.append(f'  n{e["from"]} -> n{e["to"]} [{attrs}];')
    if goal:
        out.append(f'  FINAL [label="{_label(goal["goal"])}" shape=doubleoctagon];')
        for n in nodes:
            if n["type"] == "goal":
                out.append(f'  n{n["id"]} -> FINAL [style=dashed];')
    out.append("}")
    return "\n".join(out) + "\n"


def write_graph(store_path, source):
    """Always write the .dot. Render the .svg only if `dot` is on PATH —
    a missing graphviz is a warning, not an error."""
    dot_file = store_path / "graph.dot"
    dot_file.write_text(source)
    if shutil.which("dot") is None:
        return dot_file, None
    svg = store_path / "graph.svg"
    subprocess.run(["dot", "-Tsvg", str(dot_file), "-o", str(svg)], check=True)
    return dot_file, svg


def demo():
    import tempfile
    from pathlib import Path

    nodes = [{"id": 1, "content": "arm B1_P2", "type": "attempt"},
             {"id": 2, "content": "legible text", "type": "goal"}]
    edges = [{"from": 1, "to": 2, "relation": "targets"}]
    src = dot_source(nodes, edges, {"goal": "ship it"})

    assert src.startswith("digraph notes {")
    assert src.rstrip().endswith("}")
    assert 'n1 [label="1: arm B1_P2"' in src
    assert "shape=doubleoctagon" in src        # the virtual final goal
    assert "n2 -> FINAL" in src
    assert "n1 -> n2" in src and "style=dashed" in src
    assert "FINAL" not in dot_source(nodes, edges, None)

    # a quote in content must not break the DOT string
    assert '\\"' not in dot_source([{"id": 9, "content": 'say "hi"', "type": "note"}], [], None)

    d = Path(tempfile.mkdtemp())
    dot_file, svg = write_graph(d, src)
    assert dot_file == d / "graph.dot" and dot_file.read_text() == src
    assert svg is None or svg == d / "graph.svg"
    print("render: ok")


if __name__ == "__main__":
    demo()
