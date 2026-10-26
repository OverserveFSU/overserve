# -*- coding: utf-8 -*-
"""Render the object-centric provenance graph (72 benign traces) with edge weights and the
latent cycles highlighted. Plain matplotlib, circular layout, no graphviz."""
import json, math, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import ocg_motif as M
import glob, os

# recompute edge support so arrows can be weighted by #traces
files = sorted(glob.glob(os.path.join(M.RESULTS, "*/baseline/**/results_*.json"), recursive=True))
traces = [t for t in (M.load_trace(f) for f in files) if t and t["pass_rate"] == 1.0]
node_sup = collections.Counter()
edge_sup = collections.Counter()          # (a,b) -> #traces (max over object type)
etr = collections.defaultdict(set)
for t in traces:
    for e in t["events"]:
        node_sup[e["label"]] += 1
    _, pe = M.build_edges(t)
    for (a, b, ot) in pe:
        etr[(a, b)].add(t["file"])
for k, s in etr.items():
    edge_sup[k] = len(s)

# nodes present in the provenance graph, grouped by operation for colour/shade
nodes = sorted({n for e in edge_sup for n in e[:2]}, key=lambda n: (-node_sup[n], n))
OP = lambda n: n.split("(")[0]
op_order = ["READ", "CREATE", "UPDATE", "SEND", "DELETE"]
nodes.sort(key=lambda n: (op_order.index(OP(n)) if OP(n) in op_order else 9, -node_sup[n]))

N = len(nodes)
ang = {n: 2 * math.pi * i / N - math.pi / 2 for i, n in enumerate(nodes)}
Rad = 4.6
pos = {n: (Rad * math.cos(ang[n]), Rad * math.sin(ang[n])) for n in nodes}

# latent cycles to highlight (2 that survive hub removal are the interesting ones; but show the
# canonical 3-node one prominently)
CYCLE = ["CREATE(Channel)", "CREATE(Tab)", "UPDATE(Channel)"]
cyc_edges = set(zip(CYCLE, CYCLE[1:] + CYCLE[:1]))

fig, ax = plt.subplots(figsize=(15, 11))
ax.set_xlim(-6.6, 6.6); ax.set_ylim(-6.2, 6.2); ax.axis("off")

shade = {"READ": "#e8e8e8", "CREATE": "#c8c8c8", "UPDATE": "#9a9a9a",
         "SEND": "#b8b8b8", "DELETE": "#7a7a7a"}
txtcol = {"READ": "#111", "CREATE": "#111", "UPDATE": "#fff", "SEND": "#111", "DELETE": "#fff"}

# edges
maxw = max(edge_sup.values())
for (a, b), w in edge_sup.items():
    if a == b:
        continue
    x1, y1 = pos[a]; x2, y2 = pos[b]
    hot = (a, b) in cyc_edges
    lw = 0.6 + 4.2 * (w / maxw)
    col = "#111" if hot else "#c0c0c0"
    z = 5 if hot else 1
    arr = FancyArrowPatch((x1, y1), (x2, y2),
                          connectionstyle="arc3,rad=0.12",
                          arrowstyle="-|>", mutation_scale=11 + (9 if hot else 0),
                          lw=lw, color=col, alpha=1.0 if hot else 0.5, zorder=z)
    ax.add_patch(arr)

# self-loops as a small marker ring
selfloops = {a: w for (a, b), w in edge_sup.items() if a == b}
for n, w in selfloops.items():
    x, y = pos[n]
    ux, uy = x / Rad, y / Rad
    ax.plot([x + ux * 0.55], [y + uy * 0.55], "o", ms=6 + w, mfc="none",
            mec="#444", mew=1.4, zorder=6)

# nodes
for n in nodes:
    x, y = pos[n]
    op = OP(n)
    r = 0.30 + 0.42 * (node_sup[n] / max(node_sup.values())) ** 0.5
    circ = plt.Circle((x, y), r, facecolor=shade.get(op, "#ddd"),
                      edgecolor="#111",
                      lw=2.4 if n in CYCLE else 1.0, zorder=8)
    ax.add_patch(circ)
    # label outside
    lx, ly = x * 1.0 + (x / Rad) * (r + 0.42), y * 1.0 + (y / Rad) * (r + 0.42)
    ha = "left" if x > 0.3 else ("right" if x < -0.3 else "center")
    ax.text(lx, ly, n, ha=ha, va="center", fontsize=11,
            fontweight="bold" if n in CYCLE else "normal",
            family="monospace", zorder=9)
    ax.text(x, y, str(node_sup[n]), ha="center", va="center",
            fontsize=9, color=txtcol.get(op, "#111"), zorder=9)

# title + legend
ax.text(0, 5.9, "Object-centric provenance graph  ·  72 benign traces",
        ha="center", fontsize=17, fontweight="bold")
ax.text(0, 5.5, "node = OP(ObjectType), number = #events   ·   edge = provenance dependency, "
                "width = #traces   ·   black = latent cycle", ha="center", fontsize=11, color="#444")

# legend for op shades
lx0 = -6.3
for i, op in enumerate(op_order):
    yy = -5.6 + 0
    ax.add_patch(plt.Circle((lx0 + i * 2.2, -5.8), 0.16, facecolor=shade[op],
                            edgecolor="#111", lw=1.0))
    ax.text(lx0 + i * 2.2 + 0.28, -5.8, op, va="center", fontsize=10, family="monospace")

fig.savefig("trace_graph.png", dpi=140, bbox_inches="tight", facecolor="white")
print("saved trace_graph.png   nodes=%d edges=%d selfloops=%d" %
      (N, sum(1 for e in edge_sup if e[0] != e[1]), len(selfloops)))
