# PROVENANCE: hand-specified experimental control (detectors). Unified runner: applies each
# detection METHOD to every corpus item and writes results/<method>.jsonl rows
# {id, kind, method, flagged, severity, details}. Methods here are the off-the-shelf / deterministic
# ones; LLM-reproduction methods (DCI, Connor, loop-guard) live in run_repro.py.
import json, os, re, subprocess, sys, time, glob
HERE = os.path.dirname(os.path.abspath(__file__))
CORPUS = json.load(open(os.path.join(HERE, 'corpus', 'corpus.json')))
_SUB = os.environ.get('ITEMS')
if _SUB:
    _ids = set(_SUB.split(','))
    CORPUS = [it for it in CORPUS if it['id'] in _ids or it['kind'] in _ids]
RES = os.path.join(HERE, 'results'); os.makedirs(RES, exist_ok=True)
VENV = os.path.join(HERE, '.venv', 'bin')
PROXY = os.environ.get('NV_PROXY', 'http://127.0.0.1:8194/v1')
ENV_LLM = dict(os.environ, MCP_SCANNER_LLM_API_KEY='dummy', MCP_SCANNER_LLM_MODEL='openai/qwen3.5',
               MCP_SCANNER_LLM_BASE_URL=PROXY)

def cdir(it): return os.path.join(HERE, 'corpus', it['id'])

def done_ids(method):
    p = os.path.join(RES, method + '.jsonl')
    if not os.path.exists(p): return set()
    return {json.loads(l)['id'] for l in open(p) if l.strip()}

def emit(method, it, flagged, severity, details):
    row = {'id': it['id'], 'kind': it['kind'], 'name': it['spec']['name'], 'method': method,
           'flagged': bool(flagged), 'severity': severity, 'details': details, 'ts': time.time()}
    with open(os.path.join(RES, method + '.jsonl'), 'a') as f: f.write(json.dumps(row) + '\n')
    return row

def has_code(it): return 'handler_src' in it['spec']

# ---------------- 1. Cisco mcp-scanner: static (yara / llm) ----------------
def cisco_static(analyzer):
    method = 'cisco_' + analyzer
    skip = done_ids(method)
    for it in CORPUS:
        if it['id'] in skip: continue
        cmd = [os.path.join(VENV, 'mcp-scanner'), '--analyzers', analyzer, '--raw', 'static', '--tools', os.path.join(cdir(it), 'tools.json')]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=ENV_LLM).stdout
            i = out.find('['); d = json.loads(out[i:]) if i >= 0 else []
            r = d[0] if d else {}
            f = r.get('findings', {}).get(analyzer + '_analyzer', {})
            sev = f.get('severity', 'ERR'); flagged = (not r.get('is_safe', True)) or sev not in ('SAFE', 'ERR')
            emit(method, it, flagged, sev, {'threats': f.get('threat_names'), 'summary': f.get('threat_summary')})
        except Exception as e:
            emit(method, it, False, 'ERR', {'error': str(e)[:300]})
        print(method, it['id'], flush=True)

# ---------------- 2. Cisco behavioral (code vs docstring alignment) ----------------
def cisco_behavioral():
    method = 'cisco_behavioral'; skip = done_ids(method)
    for it in CORPUS:
        if it['id'] in skip or not has_code(it): continue
        cmd = [os.path.join(VENV, 'mcp-scanner'), '--format', 'raw', 'behavioral', cdir(it)]
        try:
            p = subprocess.run(cmd, capture_output=True, text=True, timeout=900, env=ENV_LLM)
            out = p.stdout
            i = out.find('['); d = json.loads(out[i:]) if i >= 0 else None
            if d is None:
                # fall back to summary text
                unsafe = re.search(r'Unsafe items:\s*(\d+)', out)
                flagged = bool(unsafe and int(unsafe.group(1)) > 0)
                emit(method, it, flagged, 'UNSAFE' if flagged else 'SAFE', {'raw': out[-600:]})
            else:
                r = d[0] if d else {}
                f = r.get('findings', {}).get('behavioral_analyzer', {})
                sev = f.get('severity', '?'); flagged = not r.get('is_safe', True)
                emit(method, it, flagged, sev, {'threats': f.get('threat_names'), 'summary': f.get('threat_summary'), 'all': r.get('findings')})
        except Exception as e:
            emit(method, it, False, 'ERR', {'error': str(e)[:300]})
        print(method, it['id'], flush=True)

# ---------------- 3. Lasso mcp-gateway regex tool-poisoning analyzer ----------------
def lasso_regex():
    method = 'lasso_regex'; skip = done_ids(method)
    sys.path.insert(0, glob.glob(os.path.join(HERE, '.venv/lib/python3.*/site-packages'))[0])
    import logging; logging.disable(logging.CRITICAL)
    from mcp_gateway.security_scanner.tool_poisoning_analyzer import ToolAnalyzer
    ta = ToolAnalyzer()
    for it in CORPUS:
        if it['id'] in skip: continue
        r = ta.analyze_tool_description(it['spec']['description'])
        flagged = any(r.values())
        emit(method, it, flagged, 'FLAG' if flagged else 'SAFE', r)

# ---------------- 4. MCPInspect-style heuristic metadata filter (Li & Gao, DSN'26) ----------------
INSTR = [r'ignore (all |any )?(previous|prior|above|earlier) (instructions?|prompts?|messages?)', r'disregard (the )?(previous|prior|above)',
         r'forget (all |your )?(previous|prior) (instructions?|rules?)', r'do not (tell|inform|alert|notify|mention|reveal|disclose)',
         r'(keep|remain) (this |it )?(secret|hidden|confidential)', r'<\s*/?\s*(important|attention|system|secret|instructions?|hidden|note)\s*>',
         r'\bIMPORTANT\b\s*[:!]', r'you (must|should) (always|never)', r'before (using|calling) (any|other|the) tool', r'(read|cat|open|send|upload) .{0,40}(~/\.ssh|id_rsa|\.env|passwd|api[_ ]?key|credential|token)']
def mcpinspect_heur():
    method = 'mcpinspect_heur'; skip = done_ids(method)
    rx = [re.compile(p, re.I) for p in INSTR]
    for it in CORPUS:
        if it['id'] in skip: continue
        txt = it['spec']['description'] + ' ' + json.dumps(it['spec'].get('inputSchema', {}))
        hits = [p.pattern for p in rx if p.search(txt)]
        emit(method, it, bool(hits), 'FLAG' if hits else 'SAFE', {'hits': hits})

# ---------------- 5. mcp-shield (regex on live tools/list over stdio) ----------------
def mcpshield():
    method = 'mcpshield'; skip = done_ids(method)
    items = [it for it in CORPUS if it['id'] not in skip]
    if not items: return
    cfgdir = os.path.join(HERE, 'results', 'shield_cfg'); os.makedirs(cfgdir, exist_ok=True)
    for chunk_start in range(0, len(items), 20):
        chunk = items[chunk_start:chunk_start + 20]
        cfg = {'mcpServers': {it['id']: {'command': 'python3', 'args': [os.path.join(HERE, 'spec_server.py'), '--stdio'],
                                          'env': {'ATK_SPEC': os.path.join(cdir(it), 'spec.json')}} for it in chunk}}
        cp = os.path.join(cfgdir, 'claude_desktop_config.json'); json.dump(cfg, open(cp, 'w'))
        env = dict(os.environ, PATH=os.path.join(HERE, 'ext/node20/bin') + ':' + os.environ['PATH'])
        out = subprocess.run(['npx', '-y', 'mcp-shield', '--path', cp], capture_output=True, text=True, timeout=1800, env=env).stdout
        out = re.sub(r'\x1b\[[0-9;?]*[a-zA-Z]', '', out)
        # parse final tree: lines like "✓ tool — Verified" or "✗ tool — ... [HIGH Risk]"; use the vulnerability list at the end
        vul = {}
        for m in re.finditer(r'Server:\s*(\S+)\s*\n\s*Tool:\s*(\S+)\s*\n\s*Risk Level:\s*(\w+)\s*\n\s*Issues:\s*\n((?:\s*[–-] .*\n?)*)', out):
            vul[m.group(1)] = {'risk': m.group(3), 'issues': [l.strip(' –-') for l in m.group(4).strip().splitlines()]}
        connected = set(re.findall(r'● (\S+) \(', out))
        for it in chunk:
            if it['id'] in vul: emit(method, it, True, vul[it['id']]['risk'], vul[it['id']])
            elif it['id'] in connected: emit(method, it, False, 'SAFE', {})
            else: emit(method, it, False, 'ERR', {'note': 'not connected', 'tail': out[-300:]})
        print(method, chunk_start, flush=True)

# ---------------- 6. Ant Group MCPScan (semgrep taint + LLM desc + LLM code flow) ----------------
def ant_mcpscan():
    method = 'ant_mcpscan'; skip = done_ids(method)
    env = dict(os.environ, PATH=VENV + ':' + os.environ['PATH'], DEEPSEEK_API_KEY='dummy',
               MCPSCAN_LLM_BASE_URL=PROXY, MCPSCAN_LLM_MODEL='qwen3.5')
    for it in CORPUS:
        if it['id'] in skip or not has_code(it): continue
        outp = os.path.join(RES, 'mcpscan_%s.json' % it['id'])
        try:
            p = subprocess.run([os.path.join(VENV, 'mcpscan'), 'scan', cdir(it), '--save', '--out', outp],
                               capture_output=True, text=True, timeout=1800, env=env)
            d = json.load(open(outp)) if os.path.exists(outp) else None
            if d is None:
                emit(method, it, False, 'ERR', {'tail': (p.stdout + p.stderr)[-400:]})
            else:
                high = [r for r in d if str(r.get('risk', '')).upper() == 'HIGH']
                emit(method, it, bool(high), 'HIGH' if high else ('LOW' if d else 'SAFE'),
                     {'n_findings': len(d), 'findings': [{k: r.get(k) for k in ('rule_id', 'class', 'severity', 'risk', 'explanation')} for r in d][:8]})
        except Exception as e:
            emit(method, it, False, 'ERR', {'error': str(e)[:300]})
        print(method, it['id'], flush=True)

METHODS = {'cisco_yara': lambda: cisco_static('yara'), 'cisco_llm': lambda: cisco_static('llm'),
           'cisco_behavioral': cisco_behavioral, 'lasso_regex': lasso_regex, 'mcpinspect_heur': mcpinspect_heur,
           'mcpshield': mcpshield, 'ant_mcpscan': ant_mcpscan}

if __name__ == '__main__':
    for m in sys.argv[1:]:
        METHODS[m]()
