"""Generate a minimal black-and-white academic slide deck (OverServe) as a .pptx."""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

INK = RGBColor(0x14, 0x14, 0x14)
MUT = RGBColor(0x66, 0x66, 0x66)
FAINT = RGBColor(0x9A, 0x9A, 0x9A)
LINE = RGBColor(0xD7, 0xD7, 0xD7)
PANEL = RGBColor(0xF3, 0xF3, 0xF3)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
SERIF, SANS, MONO = "Georgia", "Arial", "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]
W, H = prs.slide_width, prs.slide_height
MX = Inches(0.85)


def slide():
    s = prs.slides.add_slide(BLANK)
    bg = s.background.fill; bg.solid(); bg.fore_color.rgb = WHITE
    return s


def box(s, l, t, w, h, anchor=MSO_ANCHOR.TOP):
    tb = s.shapes.add_textbox(l, t, w, h); tf = tb.text_frame
    tf.word_wrap = True; tf.vertical_anchor = anchor
    tf.margin_left = 0; tf.margin_right = 0; tf.margin_top = 0; tf.margin_bottom = 0
    return tf


def para(tf, runs, size=18, font=SANS, color=INK, bold=False, align=PP_ALIGN.LEFT,
         space_after=6, space_before=0, line=1.15, first=False):
    p = tf.paragraphs[0] if first and not tf.paragraphs[0].runs else tf.add_paragraph()
    p.alignment = align; p.space_after = Pt(space_after); p.space_before = Pt(space_before)
    p.line_spacing = line
    if isinstance(runs, str): runs = [(runs, {})]
    for text, o in runs:
        r = p.add_run(); r.text = text
        r.font.size = Pt(o.get("size", size)); r.font.name = o.get("font", font)
        r.font.bold = o.get("bold", bold); r.font.color.rgb = o.get("color", color)
    return p


def rule(s, l, t, w=Inches(0.62), color=INK, weight=2.2):
    ln = s.shapes.add_connector(2, l, t, l + w, t)
    ln.line.color.rgb = color; ln.line.width = Pt(weight)
    return ln


def kicker(s, txt):
    tf = box(s, MX, Inches(0.6), Inches(11.5), Inches(0.4))
    para(tf, txt.upper(), size=12, font=MONO, color=MUT, first=True)


def title(s, txt, size=34, top=1.05):
    tf = box(s, MX, Inches(top), Inches(11.6), Inches(1.5))
    for i, ln in enumerate(txt.split("\n")):
        para(tf, ln, size=size, font=SERIF, color=INK, bold=True, line=1.04, first=(i == 0), space_after=0)
    rule(s, MX, Inches(top + 0.05 + 0.62 * len(txt.split("\n")) * (size / 34)))


def panel(s, l, t, w, h, fill=None):
    sp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, l, t, w, h)
    sp.fill.solid(); sp.fill.fore_color.rgb = fill if fill else WHITE
    if not fill: sp.fill.background()
    sp.line.color.rgb = LINE; sp.line.width = Pt(1.4)
    sp.shadow.inherit = False
    try: sp.adjustments[0] = 0.04
    except Exception: pass
    return sp


# ---------------- 1 TITLE ----------------
s = slide()
tf = box(s, MX, Inches(1.0), Inches(11.6), Inches(0.4))
para(tf, "AGENTIC SAAS SECURITY", size=13, font=MONO, color=MUT, first=True)
tf = box(s, MX, Inches(1.7), Inches(11.6), Inches(3.0))
for i, ln in enumerate(["OverServe: Cross-Layer", "Resource Amplification", "in SaaS Agents"]):
    para(tf, ln, size=46, font=SERIF, color=INK, bold=True, line=1.03, first=(i == 0), space_after=0)
rule(s, MX, Inches(4.55), w=Inches(0.9))
tf = box(s, MX, Inches(4.85), Inches(9.6), Inches(1.4))
para(tf, "A small, legitimate-looking prompt cascades down the agent stack into a "
        "denial-of-service. Amplification is the mechanism; resource exhaustion is the attack.",
     size=19, color=MUT, line=1.4, first=True)
tf = box(s, MX, Inches(6.5), Inches(11.6), Inches(0.5))
para(tf, "victim: Qwen3.5-122B  ·  70-tool Microsoft-Teams MCP (EnterpriseOps-Gym)",
     size=13, font=MONO, color=FAINT, first=True)

# ---------------- 2 PROBLEM ----------------
s = slide(); kicker(s, "01 / The problem"); title(s, "A prompt is not one request — it is a cascade")
tf = box(s, MX, Inches(2.35), Inches(11.4), Inches(1.0))
para(tf, [("Classic LLM DoS ends at compute. An agentic SaaS request keeps walking the stack, and ", {}),
          ("every hop spends a different, un-cached resource.", {"bold": True})],
     size=20, line=1.4, first=True)
# cascade
labels = ["1 prompt", "LLM turns", "tool calls", "SaaS quota · DB", "worker time"]
x = MX; y = Inches(3.9)
for i, lab in enumerate(labels):
    w = Inches(2.15 if i >= 3 else 1.55)
    sp = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, Inches(0.62))
    sp.fill.background(); sp.line.color.rgb = INK; sp.line.width = Pt(2.5 if i >= 3 else 1.6)
    sp.shadow.inherit = False
    t = sp.text_frame; t.word_wrap = True; t.margin_top = Pt(2); t.margin_bottom = Pt(2)
    para(t, lab, size=14, font=MONO, color=INK, bold=True, align=PP_ALIGN.CENTER, first=True)
    x = x + w
    if i < len(labels) - 1:
        ar = box(s, x, y, Inches(0.42), Inches(0.62), anchor=MSO_ANCHOR.MIDDLE)
        para(ar, "→", size=18, font=MONO, color=FAINT, bold=True, align=PP_ALIGN.CENTER, first=True)
        x = x + Inches(0.42)
tf = box(s, MX, Inches(5.1), Inches(11.0), Inches(1.4))
para(tf, [("Run it until a bottleneck resource is spent — API quota, worker pool, rate limit, queue — "
           "and the service's other tenants inherit latency, failures, lost availability. ", {"color": MUT}),
          ("That is the DoS.", {"bold": True})], size=17, line=1.45, first=True)

# ---------------- 3 KEY IDEA ----------------
s = slide(); kicker(s, "02 / Key idea"); title(s, "Measure the whole cost vector, not the token count", size=30)
tf = box(s, MX, Inches(2.4), Inches(5.6), Inches(2.6))
para(tf, [("Prefix caching flattens the victim's own token/GPU cost to ", {}), ("~1.3×", {"bold": True}), (".", {})],
     size=20, line=1.4, first=True)
para(tf, "But caching does nothing for the resources that actually run out. Those amplify at the full rate.",
     size=16, color=MUT, line=1.4, space_before=8)
# table panel
p = panel(s, Inches(7.0), Inches(2.4), Inches(5.5), Inches(2.7), fill=PANEL)
rows = [("cached tokens / GPU", "1.3×", False), ("tool / API calls", "2–13×", True),
        ("write quota", "up to 71× / op", True), ("wall-clock / worker", "up to 7 min", True)]
ty = Inches(2.65)
lab = box(s, Inches(7.3), Inches(2.55), Inches(5.0), Inches(0.35))
para(lab, "AMPLIFICATION BY LAYER", size=11, font=MONO, color=MUT, first=True)
for i, (k, v, hi) in enumerate(rows):
    row = box(s, Inches(7.3), Inches(3.05 + i * 0.48), Inches(4.9), Inches(0.42))
    para(row, [(k, {"size": 15, "color": INK}),
               ("   " + v, {"size": 15, "font": MONO, "bold": hi, "color": INK})], first=True)
tf = box(s, MX, Inches(5.7), Inches(11.4), Inches(1.0))
para(tf, [("Amplification = vulnerability.  Resource exhaustion = impact.", {"bold": True}),
          ("  Stating the chain end-to-end answers “why is 3× calls a DoS?”", {"color": MUT})],
     size=17, line=1.4, first=True)

# ---------------- 4 METHOD ----------------
s = slide(); kicker(s, "03 / Method"); title(s, "Profile every layer, then optimize a target resource", size=30)
steps = [("1", "Cross-layer profiler",
          "Run any task; record the full cost vector — tool, write, read, objects, LLM turns, tokens, wall-clock, fidelity."),
         ("2", "Motif × resource matrix",
          "Profile a library of task structures — different shapes exhaust different bottlenecks. Amplification is steerable per resource."),
         ("3", "Structure optimizer",
          "Pick a target resource; a generator searches solvable, plausible task structures that maximize it, with feedback — an optimizable attack.")]
y = 2.5
for num, h, body in steps:
    ni = box(s, MX, Inches(y), Inches(0.6), Inches(0.7))
    para(ni, num, size=26, font=SERIF, color=FAINT, bold=True, first=True)
    tf = box(s, Inches(1.55), Inches(y), Inches(10.8), Inches(1.4))
    para(tf, h, size=20, color=INK, bold=True, first=True, space_after=2)
    para(tf, body, size=15, color=MUT, line=1.35)
    y += 1.5

# ---------------- 5 MECHANISM ----------------
s = slide(); kicker(s, "04 / Mechanism"); title(s, "A plausible frame around a combinatorial structure", size=30)
tf = box(s, MX, Inches(2.4), Inches(11.4), Inches(1.2))
para(tf, [("The prompt never says “make twenty channels.” It states a ", {}), ("structure", {"bold": True}),
          ("; the agent ", {}), ("decompresses", {"bold": True}),
          (" it into the concrete workload — short description, deep execution.", {})],
     size=19, line=1.4, first=True)
recipe = [("frame", "a credible admin goal a reviewer waves through — “incident-response framework”"),
          ("× fan-out", "“for each incident category…” — an implicit multiplier the agent enumerates"),
          ("× phases", "“triage, investigation, stakeholder, post-mortem” — 4 objects each"),
          ("× membership", "“dynamic membership” — a lookup + a write per member, per channel")]
y = 3.7
for k, v in recipe:
    kk = box(s, MX, Inches(y), Inches(1.9), Inches(0.5))
    para(kk, k, size=15, font=MONO, color=INK, bold=True, first=True)
    vv = box(s, Inches(2.9), Inches(y), Inches(9.6), Inches(0.5))
    para(vv, v, size=15, color=MUT, first=True)
    rule(s, MX, Inches(y + 0.5), w=Inches(9.6), color=LINE, weight=1.0)
    y += 0.72

# ---------------- 6 RESULT comparison ----------------
s = slide(); kicker(s, "05 / Result — same register, 12.8× cost")
title(s, "Two ordinary Teams requests, one tenant", size=28)
# benign panel
panel(s, MX, Inches(2.35), Inches(5.55), Inches(2.75))
lb = box(s, Inches(1.05), Inches(2.5), Inches(5.0), Inches(0.35))
para(lb, "BENIGN BASELINE", size=11, font=MONO, color=MUT, first=True)
pb = box(s, Inches(1.05), Inches(2.9), Inches(5.1), Inches(1.3))
para(pb, "In the TechCorp Solutions team, create a teamwork tag “Beta Testers” and add John Davis, "
         "Dave Brown, and Sophia Bennett.", size=12, font=MONO, color=INK, line=1.35, first=True)
for i, (n, l) in enumerate([("6", "tool"), ("1", "write"), ("65s", "wall")]):
    vb = box(s, Inches(1.05 + i * 1.5), Inches(4.35), Inches(1.4), Inches(0.7))
    para(vb, n, size=25, font=MONO, color=INK, bold=True, first=True, space_after=0)
    para(vb, l.upper(), size=10, font=MONO, color=MUT)
# attack panel
panel(s, Inches(7.0), Inches(2.35), Inches(5.5), Inches(2.75), fill=PANEL)
lb = box(s, Inches(7.25), Inches(2.5), Inches(5.0), Inches(0.35))
para(lb, "AMPLIFYING REQUEST", size=11, font=MONO, color=MUT, first=True)
pb = box(s, Inches(7.25), Inches(2.9), Inches(5.0), Inches(1.3))
para(pb, "Implement a comprehensive incident-response framework … each incident category requires "
         "dedicated channels for triage, investigation, stakeholder, post-mortem, with dynamic membership.",
     size=12, font=MONO, color=INK, line=1.32, first=True)
for i, (n, l) in enumerate([("77", "tool"), ("71", "write"), ("7min", "wall")]):
    vb = box(s, Inches(7.25 + i * 1.5), Inches(4.35), Inches(1.4), Inches(0.7))
    para(vb, n, size=25, font=MONO, color=INK, bold=True, first=True, space_after=0)
    para(vb, l.upper(), size=10, font=MONO, color=MUT)
# big amp
ab = box(s, MX, Inches(5.25), Inches(5.5), Inches(1.7), anchor=MSO_ANCHOR.MIDDLE)
para(ab, "12.8×", size=90, font=SERIF, color=INK, bold=True, first=True)
ac = box(s, Inches(5.6), Inches(5.5), Inches(6.8), Inches(1.6), anchor=MSO_ANCHOR.MIDDLE)
para(ac, "tool / API calls, fidelity preserved.", size=16, color=INK, first=True, space_after=2)
para(ac, "Attacker cost: 400 characters.", size=15, color=MUT)

# ---------------- 7 RESULT matrix ----------------
s = slide(); kicker(s, "06 / Result — the matrix"); title(s, "Different structures exhaust different resources", size=28)
data = [["Task structure", "tool", "write", "read", "wall", "Bottleneck exhausted"],
        ["create-and-reconcile", "9", "7", "2", "106s", "write quota"],
        ["large-object read", "12", "0", "12", "130s", "memory · wall-clock"],
        ["fan-out", "7", "4", "3", "54s", "state / concurrency"],
        ["shared-object mutation", "8", "4", "4", "89s", "retry loops"],
        ["optimized (incident)", "77", "71", "5", "417s", "write quota + worker"]]
rows_n, cols_n = len(data), len(data[0])
gt = s.shapes.add_table(rows_n, cols_n, MX, Inches(2.35), Inches(11.6), Inches(3.1)).table
widths = [Inches(3.3), Inches(1.0), Inches(1.0), Inches(1.0), Inches(1.2), Inches(4.1)]
for c, wdt in enumerate(widths): gt.columns[c].width = wdt
for r in range(rows_n):
    for c in range(cols_n):
        cell = gt.cell(r, c); cell.fill.solid(); cell.fill.fore_color.rgb = WHITE
        cell.margin_left = Pt(6); cell.margin_right = Pt(6); cell.margin_top = Pt(3); cell.margin_bottom = Pt(3)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        tfc = cell.text_frame; p = tfc.paragraphs[0]; run = p.add_run(); run.text = data[r][c]
        hdr = (r == 0); last = (r == rows_n - 1); numc = 0 < c < 5
        run.font.size = Pt(11 if hdr else 14); run.font.name = MONO if (hdr or numc) else SANS
        run.font.color.rgb = MUT if hdr else INK
        run.font.bold = hdr or last or (numc and last)
        p.alignment = PP_ALIGN.RIGHT if numc else PP_ALIGN.LEFT
tf = box(s, MX, Inches(5.7), Inches(11.4), Inches(1.2))
para(tf, [("Baseline 6 tool / 1 write / 65s. And the LLM bill stays flat: the agent batches ", {"color": MUT}),
          ("up to 5.7 tool calls per LLM turn", {"bold": True}),
          (" — one model invocation fanning out into many downstream requests.", {"color": MUT})],
     size=15, line=1.4, first=True)

# ---------------- 8 CONTRIBUTIONS ----------------
s = slide(); kicker(s, "07 / Contributions"); title(s, "What OverServe establishes", size=32)
takes = [("An agentic-DoS threat model", "A task-shaping attacker who only shapes the request — no system-prompt, tool, or environment tampering."),
         ("Cross-layer amplification metric", "The full cost vector, past the token count that caching flattens to 1.3×."),
         ("A resource → structure map", "Which task shape attacks which bottleneck, made an optimization objective."),
         ("The branching amplifier", "One LLM call → 5–7 downstream calls: model cost flat, API/quota cost exploded.")]
for i, (h, b) in enumerate(takes):
    col = i % 2; row = i // 2
    l = MX + Emu(int(col * Inches(5.9)))
    t = Inches(2.5 + row * 1.55)
    rule(s, l, t + Inches(0.02), w=Inches(0.0), color=INK)  # placeholder
    bar = s.shapes.add_connector(2, l, t, l, t + Inches(1.05)); bar.line.color.rgb = INK; bar.line.width = Pt(2.5)
    tf = box(s, l + Inches(0.25), t, Inches(5.4), Inches(1.3))
    para(tf, h, size=17, color=INK, bold=True, first=True, space_after=2)
    para(tf, b, size=14, color=MUT, line=1.32)
tf = box(s, MX, Inches(6.15), Inches(11.6), Inches(1.0))
para(tf, [("Stated honestly: ", {"bold": True}),
          ("amplification scales with the fan-out the request implies (a plausible request decompressed "
           "into a large workload, not a fixed tiny task inflated) — which is exactly why the model is "
           "task-shaping, not strict prompt-only.", {"color": MUT})], size=13, line=1.4, first=True)

out = "/home/ruiheng/aiagent/saas/overserve/OverServe_deck.pptx"
prs.save(out)
print("saved", out)
