"""Isolated EOG rollout for the tool-slot harness. Wraps toolatk_run.run_attack with OUR OWN spec
file + unique attack-server port + per-victim endpoint, so it never races other sessions' v8/sibling
spec files. Pure plumbing (no prompts). Invoked as a subprocess by harness.py (one cell per call) to
keep each EOG victim episode in a clean process (the qwen VM flaps; serial + fresh-process is safest).

Usage:  python3 eog_runner.py <cell_json>
  cell_json = {"spec":{...},"prompt":"...","churn":"0"|"1","tag":"...","endpoint":"...","model":"...",
               "port":8233,"cap":40}
Prints one JSON record to stdout (last line).
"""
import os, sys, json, time, signal, subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OVERSERVE = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, OVERSERVE)


def run_one(cell):
    os.environ["ATK_CAP"] = str(cell.get("cap", 40))
    os.environ["EOG_LLM_MODEL"] = cell["model"]
    os.environ.setdefault("EOG_LLM_KEY", "dummy-shim-key")
    import toolatk_run as RUN
    port = int(cell.get("port", 8233))
    RUN.ATK_PORT = port
    RUN.ATK_URL = "http://localhost:%d" % port
    RUN.SPEC = os.path.join(HERE, "specs", "eog_live_spec.json")
    RUN.CAP = int(cell.get("cap", 40))
    RUN.LLM_EP = cell["endpoint"]
    os.makedirs(os.path.join(HERE, "specs"), exist_ok=True)
    json.dump(cell["spec"], open(RUN.SPEC, "w"), indent=2)

    srv = subprocess.Popen(
        [sys.executable, os.path.join(OVERSERVE, "mcp_attack_server_v7.py")],
        env=dict(os.environ, ATK_SPEC=RUN.SPEC, ATK_PORT=str(port), ATK_DS="churn",
                 ATK_CHURN=str(cell["churn"]), ATK_V7_ENTRIES="120"),
        stdout=open(os.path.join(HERE, "logs", "eog_srv.log"), "w"), stderr=subprocess.STDOUT)
    time.sleep(2)
    try:
        r = RUN.run_attack(cell["prompt"], cell["tag"])
    finally:
        srv.send_signal(signal.SIGTERM)
        time.sleep(1)
    return r


if __name__ == "__main__":
    cell = json.loads(sys.argv[1])
    r = run_one(cell) or {"error": "no_result"}
    print("RESULT " + json.dumps(r))
