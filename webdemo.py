"""OverServe live demo — a LOCAL web app: type a prompt, watch the victim agent's tool calls tick up
in real time, and see whether it completed the goal (verifier pass rate).

Runs entirely on localhost against your own qwen tunnel + MCP (a hosted page can't reach them).
Pure stdlib (no Flask). One run at a time (the shared MCP DB must not be hit concurrently).

    OPENROUTER_API_KEY=... EOG_LLM_ENDPOINT=http://127.0.0.1:8192/v1 \
        /home/ruiheng/aiagent/saas/EnterpriseOps-Gym/.venv/bin/python webdemo.py
    # then open http://127.0.0.1:7860

Live step count comes from tailing the agent log ("Tool result success" = one tool call, "--- Iteration"
= one reasoning turn); the final named trace + fidelity come from the run's result JSON.
"""
import os, sys, json, glob, time, queue, shutil, tempfile, threading, subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from overserve import config
from overserve.agent_fit import _resolve_llm_cfg

PILOT = config.PILOT_TASKS
REFAC = os.path.join(os.path.dirname(PILOT), "refactored_tasks")   # single-objective units
ALL70 = json.load(open(config.ALLTOOLS_JSON))["selected_tools"]
PORT = int(os.environ.get("OVERSERVE_PORT", 7860))


def _resolve_task(task_id):
    for d in (REFAC, PILOT):
        p = os.path.join(d, task_id)
        if os.path.exists(p):
            return p
    return os.path.join(PILOT, task_id)

_lock = threading.Lock()          # one agent run at a time (shared MCP DB)
_runs = {}                        # run_id -> {"q": Queue, "done": bool}
_baseline = {}                    # task_id -> baseline calls (cached after first benign run)


def tasks():
    out = []
    # single-objective units first (the good use cases: tag_with_members, etc.), tagged by level
    for fp in sorted(glob.glob(f"{REFAC}/*.json")):
        if os.path.basename(fp).startswith("_"):
            continue
        j = json.load(open(fp)); meta = j.get("_meta", {})
        out.append({"id": os.path.basename(fp),
                    "name": "[%s] %s" % (meta.get("level", "?")[:4], meta.get("objective", os.path.basename(fp))[:30]),
                    "benign": j["user_prompt"], "n_verifiers": len(j.get("verifiers", []))})
    # original compound tasks after
    for fp in sorted(glob.glob(f"{PILOT}/oracle__teams__*.json")):
        j = json.load(open(fp))
        out.append({"id": os.path.basename(fp), "name": "[cmpd] " + os.path.basename(fp).replace("oracle__teams__task_", "")[:26],
                    "benign": j["user_prompt"], "n_verifiers": len(j.get("verifiers", []))})
    return out


def _run_agent(run_id, task_id, prompt, cap):
    """Spawn evaluate.py, tail its log for live steps, then parse the result. Emits SSE events to the queue."""
    q = _runs[run_id]["q"]
    def emit(ev):
        q.put(ev)
    try:
        src = _resolve_task(task_id)
        tj = json.load(open(src))
        benign = tj["user_prompt"]                 # remember the task's own benign prompt
        tj["selected_tools"] = ALL70
        tj["user_prompt"] = prompt
        tmp = tempfile.mkdtemp(prefix="oswebcfg_")
        json.dump(tj, open(os.path.join(tmp, "t.json"), "w"))
        out = tempfile.mkdtemp(prefix="oswebout_")
        llm_cfg = _resolve_llm_cfg(out)
        logpath = os.path.join(out, "_log")
        env = dict(os.environ, EOG_RIDER="", EOG_MAX_ITERS=str(cap))
        emit({"type": "status", "msg": "starting agent…"})
        proc = subprocess.Popen(
            [config.EOG_PYTHON, "evaluate.py", "--configs_folder", tmp, "--llm_config", llm_cfg,
             "--output_folder", out, "--orchestrator", "react", "--concurrency", "1", "--num_runs", "1"],
            cwd=config.EOG_HOME, env=env, stdout=open(logpath, "w"), stderr=subprocess.STDOUT)
        # tail the log for live progress
        steps, iters = 0, 0
        pos = 0
        while proc.poll() is None or True:
            if os.path.exists(logpath):
                with open(logpath) as f:
                    f.seek(pos)
                    for line in f:
                        if "--- Iteration" in line:
                            iters += 1; emit({"type": "iter", "n": iters})
                        elif "Tool result success" in line:
                            steps += 1; emit({"type": "step", "n": steps})
                        elif "Seeding database" in line or "seed-database" in line:
                            emit({"type": "status", "msg": "loading world state…"})
                    pos = f.tell()
            if proc.poll() is not None:
                break
            time.sleep(0.4)
        # parse result
        fs = glob.glob(os.path.join(out, "run_*", "*.json"))
        res = {"calls": steps, "turns": iters, "fidelity": None, "trace": [], "naive": 0, "cached": 0, "nverif": 0}
        if fs:
            j = json.load(open(fs[0])); r = (j.get("runs") or [{}])[0]
            cf = r.get("conversation_flow", [])
            ai = [m for m in cf if m.get("type") == "ai_message"]
            def _arg(a):
                for k, v in (a or {}).items():
                    if isinstance(v, str) and v: return "%s=%s" % (k, v[:22])
                return ""
            trace = ["%s(%s)" % (t.get("name"), _arg(t.get("args"))) for m in ai for t in (m.get("tool_calls") or [])]
            ins = [int((m.get("usage_metadata") or {}).get("input_tokens") or 0) for m in ai]
            outs = [int((m.get("usage_metadata") or {}).get("output_tokens") or 0) for m in ai]
            st = j.get("statistics", {})
            res = {"calls": len(trace), "turns": len(ai),
                   "fidelity": float(st.get("verifier_level_pass_rate", 0)),
                   "nverif": int(st.get("total_verifiers_checked", 0)),
                   "npassed": int(st.get("total_verifiers_passed", 0)),
                   "trace": trace,
                   "naive": sum(int((m.get("usage_metadata") or {}).get("total_tokens") or 0) for m in ai),
                   "cached": (ins[-1] if ins else 0) + sum(outs)}
        # baseline bookkeeping: running the task's own benign prompt sets/updates the baseline
        if prompt.strip() == benign.strip() and res["calls"] > 0:
            _baseline[task_id] = res["calls"]
        res["baseline"] = _baseline.get(task_id)
        emit({"type": "done", **res})
        shutil.rmtree(tmp, ignore_errors=True); shutil.rmtree(out, ignore_errors=True)
    except Exception as e:
        emit({"type": "error", "msg": str(e)[:200]})
    finally:
        _runs[run_id]["done"] = True
        _lock.release()


PAGE = """<!doctype html><html><head><meta charset=utf-8><title>OverServe Live</title>
<meta name=viewport content="width=device-width,initial-scale=1">
<style>
:root{--bg:#0e1116;--card:#171b22;--fg:#e6edf3;--mut:#8b949e;--acc:#58a6ff;--ok:#3fb950;--bad:#f85149;--bd:#30363d}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif}
.wrap{max-width:960px;margin:0 auto;padding:24px}
h1{font-size:20px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 20px;font-size:13px}
.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:16px;margin-bottom:16px}
label{display:block;color:var(--mut);font-size:12px;text-transform:uppercase;letter-spacing:.04em;margin-bottom:6px}
select,textarea,input{width:100%;background:#0d1117;color:var(--fg);border:1px solid var(--bd);border-radius:8px;padding:10px;font:inherit}
textarea{min-height:120px;resize:vertical;font-size:14px}
.row{display:flex;gap:12px;align-items:end;margin-top:12px}.row>div{flex:1}
button{background:var(--acc);color:#04101f;border:0;border-radius:8px;padding:11px 20px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:not-allowed}button.ghost{background:#21262d;color:var(--fg);border:1px solid var(--bd)}
.live{display:flex;gap:24px;align-items:center}
.big{font-size:52px;font-weight:700;line-height:1;font-variant-numeric:tabular-nums}
.big small{font-size:13px;color:var(--mut);font-weight:400;display:block;text-transform:uppercase;letter-spacing:.05em}
.dot{width:9px;height:9px;border-radius:50%;background:var(--mut);display:inline-block;margin-right:6px}
.dot.run{background:var(--acc);animation:p 1s infinite}@keyframes p{50%{opacity:.3}}
.verdict{font-size:17px;font-weight:600;margin-top:4px}.ok{color:var(--ok)}.bad{color:var(--bad)}
.trace{max-height:260px;overflow:auto;background:#0d1117;border:1px solid var(--bd);border-radius:8px;padding:10px;font:12px/1.6 ui-monospace,Menlo,monospace;color:#a5d6ff}
.trace div{white-space:nowrap}.trace .i{color:var(--mut)}
.trace .rd{color:#f0a020}.trace .wr{color:#a5d6ff}
.pill{display:inline-block;background:#21262d;border:1px solid var(--bd);border-radius:20px;padding:3px 10px;font-size:12px;color:var(--mut);margin-right:8px}
.stat{display:flex;gap:20px;flex-wrap:wrap;margin:8px 0 0}.stat b{font-size:22px;font-variant-numeric:tabular-nums}.stat small{color:var(--mut);display:block;font-size:11px;text-transform:uppercase}
.hint{color:var(--mut);font-size:12px;margin-top:8px}
</style></head><body><div class=wrap>
<h1>OverServe — Live Step Counter</h1>
<p class=sub>Type a prompt → watch the victim agent (qwen3.5) issue tool calls in real time → see whether it completed the goal (its verifiers). A short prompt that burns many steps for the same result = a denial-of-engineering attack.</p>

<div class=card>
  <label>Task (sets the world + the completion verifiers)</label>
  <select id=task></select>
  <div style="margin-top:12px"><label>Prompt sent to the agent</label><textarea id=prompt placeholder="Type or edit the prompt…"></textarea></div>
  <div class=row>
    <div style="flex:0 0 120px"><label>Turn cap</label><input id=cap type=number value=36 min=1 max=60></div>
    <div style="flex:0 0 auto"><button class=ghost id=loadbenign>Load benign prompt</button></div>
    <div style="flex:0 0 auto"><button id=run>▶ Run agent</button></div>
  </div>
  <div class=hint id=hint>One run at a time · a run takes ~1–3 min on the shared GPU.</div>
</div>

<div class=card>
  <div class=live>
    <div class=big><span id=steps>0</span><small>tool calls (steps)</small></div>
    <div class=big><span id=turns>0</span><small>reasoning turns</small></div>
    <div style="flex:1"><span class=dot id=dot></span><span id=status>idle</span><div class=verdict id=verdict></div></div>
  </div>
  <div class=stat id=stat></div>
</div>

<div class=card><label>Tool-call trace <span class=pill id=readpill style="float:right"></span></label><div class=trace id=trace><div class=i>(runs appear here)</div></div></div>

<script>
let ev=null;
async function loadTasks(){
  const r=await fetch('/api/tasks'); const ts=await r.json();
  const sel=document.getElementById('task'); window._tasks={};
  ts.forEach(t=>{window._tasks[t.id]=t; const o=document.createElement('option');o.value=t.id;o.textContent=t.name+'  ('+t.n_verifiers+' verifiers)';sel.appendChild(o);});
  loadBenign();
}
function loadBenign(){const t=window._tasks[document.getElementById('task').value];document.getElementById('prompt').value=t.benign;}
document.getElementById('task').onchange=loadBenign;
document.getElementById('loadbenign').onclick=loadBenign;
function set(id,v){document.getElementById(id).textContent=v;}
document.getElementById('run').onclick=async()=>{
  const btn=document.getElementById('run');btn.disabled=true;
  set('steps','0');set('turns','0');set('verdict','');document.getElementById('verdict').className='verdict';
  document.getElementById('stat').innerHTML='';document.getElementById('trace').innerHTML='<div class=i>running…</div>';
  document.getElementById('dot').className='dot run';set('status','starting…');
  const body={task_id:document.getElementById('task').value,prompt:document.getElementById('prompt').value,cap:+document.getElementById('cap').value};
  const r=await fetch('/api/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const j=await r.json();
  if(j.busy){set('status','busy — another run in progress');btn.disabled=false;document.getElementById('dot').className='dot';return;}
  if(ev)ev.close(); ev=new EventSource('/api/stream?run_id='+j.run_id);
  ev.onmessage=(m)=>{const d=JSON.parse(m.data);
    if(d.type==='step')set('steps',d.n);
    else if(d.type==='iter'){set('turns',d.n);set('status','reasoning turn '+d.n+'…');}
    else if(d.type==='status')set('status',d.msg);
    else if(d.type==='error'){set('status','error: '+d.msg);document.getElementById('dot').className='dot';btn.disabled=false;ev.close();}
    else if(d.type==='done'){done(d);btn.disabled=false;document.getElementById('dot').className='dot';ev.close();}
  };
};
function done(d){
  set('steps',d.calls);set('turns',d.turns);set('status','done');
  const v=document.getElementById('verdict');
  const fid=d.fidelity;
  if(fid>=0.999){v.textContent='✓ GOAL COMPLETED — all '+d.nverif+' verifiers passed';v.className='verdict ok';}
  else if(fid>0){v.textContent='◐ PARTIAL — '+d.npassed+'/'+d.nverif+' verifiers passed ('+Math.round(fid*100)+'%)';v.className='verdict bad';}
  else{v.textContent='✗ NOT COMPLETED — 0/'+d.nverif+' verifiers passed';v.className='verdict bad';}
  const amp=d.baseline?(' · '+(d.calls/d.baseline).toFixed(2)+'× vs benign baseline '+d.baseline):'';
  document.getElementById('stat').innerHTML=
    '<div><b>'+d.calls+'</b><small>tool calls'+amp+'</small></div>'+
    '<div><b>'+d.turns+'</b><small>turns</small></div>'+
    '<div><b>'+(d.naive||0).toLocaleString()+'</b><small>naive tokens</small></div>'+
    '<div><b>'+(d.cached||0).toLocaleString()+'</b><small>cached tokens</small></div>';
  const tr=document.getElementById('trace');tr.innerHTML='';
  let reads=0;
  (d.trace||[]).forEach((t,i)=>{const el=document.createElement('div');
    const isRead=/^(list_|get_|search_|find_)/.test(t); if(isRead)reads++;
    el.innerHTML='<span class=i>'+(i+1).toString().padStart(2)+'</span>  <span class="'+(isRead?'rd':'wr')+'">'+t+'</span>';
    tr.appendChild(el);});
  if(!d.trace||!d.trace.length)tr.innerHTML='<div class=i>(no tool calls)</div>';
  const rp=document.getElementById('readpill'); if(rp)rp.textContent=reads+' read/lookup (detour signal) · '+((d.trace||[]).length-reads)+' write';
}
loadTasks();
</script></div></body></html>"""


class H(BaseHTTPRequestHandler):
    def _send(self, code, ctype, body):
        self.send_response(code); self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-cache"); self.end_headers()
        if isinstance(body, str): body = body.encode()
        self.wfile.write(body)

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/":
            self._send(200, "text/html; charset=utf-8", PAGE)
        elif u.path == "/api/tasks":
            self._send(200, "application/json", json.dumps(tasks()))
        elif u.path == "/api/stream":
            rid = parse_qs(u.query).get("run_id", [""])[0]
            if rid not in _runs:
                self._send(404, "text/plain", "no run"); return
            self.send_response(200); self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache"); self.end_headers()
            q = _runs[rid]["q"]
            while True:
                try:
                    ev = q.get(timeout=30)
                except queue.Empty:
                    try: self.wfile.write(b": ping\n\n"); self.wfile.flush(); continue
                    except Exception: break
                try:
                    self.wfile.write(("data: " + json.dumps(ev) + "\n\n").encode()); self.wfile.flush()
                except Exception:
                    break
                if ev.get("type") in ("done", "error"): break
        else:
            self._send(404, "text/plain", "not found")

    def do_POST(self):
        if urlparse(self.path).path == "/api/run":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or "{}")
            if not _lock.acquire(blocking=False):
                self._send(200, "application/json", json.dumps({"busy": True})); return
            rid = "r%d" % (time.time() * 1000)
            _runs[rid] = {"q": queue.Queue(), "done": False}
            threading.Thread(target=_run_agent, args=(rid, body["task_id"], body["prompt"],
                             int(body.get("cap", 36))), daemon=True).start()
            self._send(200, "application/json", json.dumps({"run_id": rid}))
        else:
            self._send(404, "text/plain", "not found")

    def log_message(self, *a): pass


if __name__ == "__main__":
    print(f"OverServe live demo → http://127.0.0.1:{PORT}", flush=True)
    print(f"  victim endpoint: {config.EOG_LLM_ENDPOINT} | tasks: {len(tasks())}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
