# PROVENANCE: hand-specified experimental control (detectors). Runs Cisco mcp-scanner's
# BehavioralCodeAnalyzer (docstring-vs-implementation alignment, LLM-backed) through its own CLI
# helper so we get structured per-function results instead of the summary text.
import asyncio, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
os.environ.update(MCP_SCANNER_LLM_API_KEY='dummy', MCP_SCANNER_LLM_MODEL='openai/qwen3.5',
                  MCP_SCANNER_LLM_BASE_URL='http://127.0.0.1:8193/v1')
from mcpscanner.cli import _run_behavioral_analyzer_on_source
CORPUS = json.load(open(os.path.join(HERE, 'corpus', 'corpus.json')))
OUT = os.path.join(HERE, 'results', 'cisco_behavioral.jsonl')
done = {json.loads(l)['id'] for l in open(OUT)} if os.path.exists(OUT) else set()

async def main():
    for it in CORPUS:
        if it['id'] in done or 'handler_src' not in it['spec']: continue
        d = os.path.join(HERE, 'corpus', it['id'])
        try:
            res = await asyncio.wait_for(_run_behavioral_analyzer_on_source(os.path.join(d, 'server.py')), timeout=900)
            # res: list of tool-style dicts (one per analyzed function); flag if any is_safe False
            unsafe = [r for r in res if not r.get('is_safe', True)]
            det = [{'tool': r.get('tool_name'), 'sev': r.get('findings', {}).get('behavioral_analyzer', {}).get('severity'),
                    'summary': r.get('findings', {}).get('behavioral_analyzer', {}).get('threat_summary')} for r in res]
            row = {'id': it['id'], 'kind': it['kind'], 'name': it['spec']['name'], 'method': 'cisco_behavioral',
                   'flagged': bool(unsafe), 'severity': (unsafe[0]['findings']['behavioral_analyzer'].get('severity') if unsafe else 'SAFE'),
                   'details': {'functions': det}, 'ts': time.time()}
        except Exception as e:
            row = {'id': it['id'], 'kind': it['kind'], 'name': it['spec']['name'], 'method': 'cisco_behavioral',
                   'flagged': False, 'severity': 'ERR', 'details': {'error': str(e)[:300]}, 'ts': time.time()}
        with open(OUT, 'a') as f: f.write(json.dumps(row) + '\n')
        print('cisco_behavioral', it['id'], row['severity'], flush=True)

asyncio.run(main())
