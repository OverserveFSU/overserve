"""Phase 0a: harvest OBSERVED guard-violation signals from the archived agent runs.

Pure measurement, no hand-authored semantics: scans every archived results_*.json, pulls the
structured isError flag + message text from each tool_result (reusing ocg_motif._payload), and
tallies the distinct error strings per tool. The output is the empirical source for each tool's
precondition Γ — replacing the observed-Nx evidence strings that were previously hand-copied into
motif_semantics.py.

Output: observed_guards.json  { tool: { normalized_error: count, ... }, ... }
"""
import os, sys, json, glob, re, collections

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ocg_motif as M  # reuse _payload for identical parsing

RESULTS = M.RESULTS  # EnterpriseOps-Gym/results


def normalize(txt):
    """Collapse concrete ids so the same guard reads as one bucket."""
    t = re.sub(r"'[^']{6,}'", "'<ID>'", txt)
    t = re.sub(r"\b[0-9a-f]{8,}\b", "<HEX>", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:160]


def harvest():
    files = sorted(glob.glob(os.path.join(RESULTS, "**", "results_*.json"), recursive=True))
    per_tool = collections.defaultdict(collections.Counter)
    n_files = n_err = 0
    for f in files:
        try:
            j = json.load(open(f))
        except Exception:
            continue
        for r in (j.get("runs") or []):
            for t in (r.get("tool_results") or []):
                # _payload returns (parsed_json_or_None, raw_text, is_error)
                _, raw, is_err = M._payload(t)
                if not is_err:
                    continue
                n_err += 1
                per_tool[t.get("tool_name")][normalize(raw)] += 1
        n_files += 1
    return per_tool, n_files, n_err


if __name__ == "__main__":
    per_tool, n_files, n_err = harvest()
    out = {tool: dict(c.most_common()) for tool, c in
           sorted(per_tool.items(), key=lambda kv: -sum(kv[1].values()))}
    json.dump(out, open("observed_guards.json", "w"), indent=1, ensure_ascii=False)
    print("scanned %d archived files, %d error tool_results, %d tools with guards"
          % (n_files, n_err, len(out)))
    print()
    for tool, errs in list(out.items())[:12]:
        total = sum(errs.values())
        top, n = next(iter(errs.items()))
        print("  %-30s %4d errs :: %s (%d)" % (tool, total, top[:70], n))
    print("\n-> observed_guards.json")
