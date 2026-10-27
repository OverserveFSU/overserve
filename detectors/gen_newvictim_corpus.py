#!/usr/bin/env python3
# PROVENANCE: hand-specified experimental control (detectors corpus EXTENSION).
# Imports the CORNER winners produced by the NEW-VICTIM campaigns (deepseek-v4-flash / nemotron-3-super
# / sonnet-5) across benchmarks into the detectors corpus as `nv###_*` items, so the full detector
# battery (industrial scanners + Connor/DCI/loop_guard re-impls) can be run against the ACTUAL latest
# attack tools — closing the gap that the campaigns only scored an offline `connor_soft` proxy, never
# the real detectors. Specs are DATA-DERIVED verbatim from the frozen campaign archives; only the
# attacker's winner specs are imported (no new attacks authored here). Rendering reuses gen_corpus.
import json, glob, hashlib, os, sys, collections
HERE = os.path.dirname(os.path.abspath(__file__)); OV = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import gen_corpus as GC   # reuse render_server, DS_SRC, py_ident

B = "/home/ruiheng/aiagent/saas/benchmarks"
# (path, victim, benchmark)
SOURCES = [
  (f"{OV}/toolatk_v8_archive_nemotron.json", "nemotron-3-super", "EOG"),
  (f"{OV}/toolatk_v8_archive_sonnet.json",   "sonnet-5",         "EOG"),
  (f"{B}/STATE-Bench/harness/archive_sb_dsv4flash.json", "deepseek-v4-flash", "STATE-Bench"),
  (f"{OV}/benchmarks/workbench/wb_nemotron_archive.json", "nemotron-3-super", "WorkBench"),
  (f"{B}/mcpmark/toolatk_v8_archive.json", "qwen/deepseek(mcpmark)", "MCPMark"),
  (f"{OV}/benchmarks/appworld/archive_appworld_sonnet.json",   "sonnet-5",         "AppWorld"),
  (f"{OV}/benchmarks/appworld/archive_appworld_nemotron.json", "nemotron-3-super", "AppWorld"),
]
# AppWorld corners live under per_task, not a top-level is_corner flag; include by known winner name.
APPWORLD_ALLOW = {"account_data_sync_status","account_sync_status","account_data_reconciliation_status",
                  "personal_data_reconciliation_status","contact_and_notes_index_status"}

def walk(o):
    if isinstance(o, dict):
        if "spec" in o and isinstance(o["spec"], dict) and "handler_src" in o["spec"]:
            yield o
        else:
            for v in o.values(): yield from walk(v)
    elif isinstance(o, list):
        for v in o: yield from walk(v)

def amp_of(e):
    for k in ("amp","med_amp","mean_amp"):
        if isinstance(e.get(k),(int,float)): return e[k]
    pt = e.get("per_task")
    if isinstance(pt,dict):
        amps=[v.get("amp") for v in pt.values() if isinstance(v,dict) and isinstance(v.get("amp"),(int,float))]
        if amps: return max(amps)
    return None

def fid_of(e):
    for k in ("prod_fid","fid_rate","all_fid"):
        if k in e: return e[k]
    return None

picked = collections.OrderedDict()   # hash -> record
for path, victim, bench in SOURCES:
    if not os.path.exists(path):
        print("MISSING", path); continue
    d = json.load(open(path))
    for e in walk(d):
        sp = e["spec"]; name = sp.get("name","")
        is_corner = e.get("is_corner") is True
        keep = is_corner or (bench=="AppWorld" and name in APPWORLD_ALLOW)
        if not keep: continue
        h = hashlib.sha1((name + sp["handler_src"] + sp.get("description","")).encode()).hexdigest()[:8]
        if h in picked:
            picked[h]["meta"]["sources"].append(f"{victim}/{bench}"); continue
        picked[h] = {"spec": {k:sp[k] for k in ("name","description","inputSchema","handler_src") if k in sp},
                     "meta": {"victim":victim, "benchmark":bench, "is_corner":is_corner,
                              "amp":amp_of(e), "prod_fid":fid_of(e),
                              "connor_soft":e.get("connor"), "static_gen":e.get("static"),
                              "prompt_stealth_gen":e.get("prompt_stealth"), "sources":[f"{victim}/{bench}"]}}

# write corpus dirs + append to corpus.json (non-destructive)
OUT = os.path.join(HERE, "corpus")
corpus_path = os.path.join(OUT, "corpus.json")
corpus = json.load(open(corpus_path))
existing_nv = [it for it in corpus if it["id"].startswith("nv")]
corpus = [it for it in corpus if not it["id"].startswith("nv")]   # replace any prior nv run
if existing_nv and not os.path.exists(corpus_path+".prenv.bak"):
    json.dump(json.load(open(corpus_path)), open(corpus_path+".prenv.bak","w"))

manifest = []
for i, (h, rec) in enumerate(picked.items()):
    name = rec["spec"]["name"]
    iid = "nv%03d_%s_%s" % (i, GC.py_ident(name)[:28], h)
    rec["spec"]["sha256"] = hashlib.sha256(json.dumps(rec["spec"], sort_keys=True).encode()).hexdigest()
    d = os.path.join(OUT, iid); os.makedirs(d, exist_ok=True)
    json.dump(rec["spec"], open(os.path.join(d,"spec.json"),"w"), indent=1)
    open(os.path.join(d,"server.py"),"w").write(GC.render_server(rec["spec"]))
    open(os.path.join(d,"directory_service.py"),"w").write(GC.DS_SRC)
    json.dump({"tools":[{"name":rec["spec"]["name"],"description":rec["spec"]["description"],
                         "inputSchema":rec["spec"].get("inputSchema",{})}]},
              open(os.path.join(d,"tools.json"),"w"), indent=1)
    item = {"id":iid, "kind":"attack", "spec":rec["spec"], "meta":rec["meta"], "sources":rec["meta"]["sources"]}
    corpus.append(item)
    manifest.append((iid, rec["meta"]["victim"], rec["meta"]["benchmark"], name,
                     rec["meta"]["amp"], rec["meta"]["prod_fid"], rec["meta"]["is_corner"]))

json.dump(corpus, open(corpus_path,"w"), indent=1)
print("NEW-VICTIM corpus items:", len(manifest), "| total corpus:", len(corpus))
print("%-40s %-20s %-12s %-30s %-6s %-6s %s"%("id","victim","benchmark","tool","amp","fid","corner"))
for m in manifest:
    print("%-40s %-20s %-12s %-30s %-6s %-6s %s"%(m[0][:40],m[1],m[2],m[3][:30],m[4],m[5],m[6]))
# emit the nv id list for the runners' _SUB
open(os.path.join(HERE,"nv_ids.txt"),"w").write(",".join(m[0] for m in manifest))
print("\nnv_ids written to nv_ids.txt")
