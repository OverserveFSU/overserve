#!/usr/bin/env python3
# PROVENANCE: hand-specified experimental control (detectors corpus EXTENSION). Imports the THREE
# tool-slot comparison ARTIFACTS (ours / a2m / looptrap tool specs) from baselines/toolslot/methods.py
# into the detectors corpus as `ts_*` items so the full detector battery can audit each method's
# injected artifact. Specs are the exact artifacts the harness slots in (frozen winner / verbatim A2M
# port / LoopTrap reimpl). No new attacks authored here. Non-destructive: backs up corpus.json.
import json, os, sys, hashlib
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gen_corpus as GC
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "baselines", "toolslot"))
import methods as M

# the artifacts to audit: (item_key, method, bench, spec). looptrap uses the default/profiled strategy.
def _artifacts(lt_strategy=None):
    arts = []
    for method in ("ours", "a2m", "looptrap"):
        for bench in ("mcpmark", "eog"):
            spec, _ = M.get_method(method, bench, looptrap_strategy=lt_strategy)
            arts.append(("%s_%s" % (method, bench), method, bench, spec))
            if method == "looptrap":
                break  # looptrap spec is bench-agnostic
    return arts

def main():
    lt_strategy = sys.argv[1] if len(sys.argv) > 1 else None
    OUT = os.path.join(HERE, "corpus")
    corpus_path = os.path.join(OUT, "corpus.json")
    corpus = json.load(open(corpus_path))
    if not os.path.exists(corpus_path + ".prets.bak"):
        json.dump(corpus, open(corpus_path + ".prets.bak", "w"))
    corpus = [it for it in corpus if not it["id"].startswith("ts_")]  # replace any prior ts run
    manifest = []
    for key, method, bench, spec in _artifacts(lt_strategy):
        h = hashlib.sha1((spec["name"] + spec["handler_src"] + spec.get("description", "")).encode()).hexdigest()[:8]
        iid = "ts_%s_%s" % (key, h)
        full = {k: spec[k] for k in ("name", "description", "inputSchema", "handler_src") if k in spec}
        full["sha256"] = hashlib.sha256(json.dumps(full, sort_keys=True).encode()).hexdigest()
        d = os.path.join(OUT, iid); os.makedirs(d, exist_ok=True)
        json.dump(full, open(os.path.join(d, "spec.json"), "w"), indent=1)
        open(os.path.join(d, "server.py"), "w").write(GC.render_server(full))
        open(os.path.join(d, "directory_service.py"), "w").write(GC.DS_SRC)
        json.dump({"tools": [{"name": full["name"], "description": full["description"],
                              "inputSchema": full.get("inputSchema", {})}]},
                  open(os.path.join(d, "tools.json"), "w"), indent=1)
        corpus.append({"id": iid, "kind": "attack", "spec": full,
                       "meta": {"method": method, "bench": bench, "family": "toolslot_pilot"}})
        manifest.append((iid, method, bench, full["name"]))
    json.dump(corpus, open(corpus_path, "w"), indent=1)
    open(os.path.join(HERE, "ts_ids.txt"), "w").write(",".join(m[0] for m in manifest))
    print("toolslot corpus items:", len(manifest), "| total corpus:", len(corpus))
    for m in manifest:
        print("  %-40s %-9s %-8s %s" % m)
    print("ts_ids ->", os.path.join(HERE, "ts_ids.txt"))

if __name__ == "__main__":
    main()
