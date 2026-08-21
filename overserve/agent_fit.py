"""Victim-agent fitness: run ONE benchmark task through the tool-using SaaS agent (EOG / qwen3.5),
capped at `cap` turns, and return the observable cost — tool calls, turns, and tokens (both the
naive Σ(in+out) count and the cache-aware proxy).

This is the ground-truth measurement layer. Every OverServe number (calls, ∆steps, matched_amp,
naive/cached tokens, fidelity, coverage) comes from here.
"""
import os
import json
import glob
import shutil
import tempfile
import subprocess

from . import config


def _resolve_llm_cfg(dst_dir):
    """Resolve the victim LLM config, applying the endpoint override (repo config points at a dead
    tunnel). Writes a patched copy so we never edit the benchmark repo in place."""
    base = config.EOG_LLM_CFG
    ep = config.EOG_LLM_ENDPOINT
    key = os.environ.get("EOG_LLM_KEY")
    if not ep and not key:
        return base
    cfg = json.load(open(base))
    if ep:
        cfg["llm_api_endpoint"] = ep
    if key:
        cfg["llm_api_key"] = key
    p = os.path.join(dst_dir, "_llm.json")
    json.dump(cfg, open(p, "w"))
    return p


def _sum_naive_tokens(run):
    """naive = Σ(input+output) per turn — re-counts the cached prefix each turn, so it OVERSTATES
    real compute. This is the 'total tokens processed, no cache credit' convention used by prior work."""
    return sum(int((m.get("usage_metadata") or {}).get("total_tokens") or 0)
               for m in run.get("conversation_flow", []) if m.get("type") == "ai_message")


def run_agent_fitness(rider="", task_src=None, cap=None):
    """Run the agent on `task_src` (a benchmark task JSON) with `rider` appended to the prompt,
    capped at `cap` turns. Returns a dict of observable cost, or None on failure.

    Keys: turns, n_calls, n_unique, tokens (naive), tokens_cached, in_last, out_sum,
          chkpt (fidelity = verifier pass rate), cover / cover_total, tool_seq, tool_trace, reasoning.
    """
    cap = config.CAP if cap is None else cap
    task_src = task_src or os.environ.get("EOG_TASK_SRC")
    if not task_src:
        raise ValueError("run_agent_fitness needs task_src (a benchmark task JSON path).")

    tmp = tempfile.mkdtemp(prefix="osfit_")
    shutil.copy(task_src, tmp)
    out = tempfile.mkdtemp(prefix="osfitout_")
    llm_cfg = _resolve_llm_cfg(out)
    env = dict(os.environ, EOG_RIDER=rider, EOG_MAX_ITERS=str(cap))
    subprocess.run([config.EOG_PYTHON, "evaluate.py", "--configs_folder", tmp,
                    "--llm_config", llm_cfg, "--output_folder", out, "--orchestrator", "react",
                    "--concurrency", "1", "--num_runs", "1"], cwd=config.EOG_HOME, env=env,
                   stdout=open(os.path.join(out, "_log"), "w"), stderr=subprocess.STDOUT)

    fs = glob.glob(os.path.join(out, "run_*", "*.json"))
    res = None
    if fs:
        try:
            j = json.load(open(fs[0]))
            r = (j.get("runs") or [{}])[0]
            if "conversation_flow" in r:
                cf = r["conversation_flow"]
                ai = [m for m in cf if m.get("type") == "ai_message"]
                turns = len(ai)
                tool_seq = [t.get("name") for m in ai for t in (m.get("tool_calls") or [])]

                def _arg(a):
                    for k, v in (a or {}).items():
                        if isinstance(v, str) and v:
                            return "%s=%s" % (k, v[:24])
                    return ""
                tool_trace = ["%s(%s)" % (t.get("name"), _arg(t.get("args")))
                              for m in ai for t in (m.get("tool_calls") or [])]
                ins = [int((m.get("usage_metadata") or {}).get("input_tokens") or 0) for m in ai]
                outs = [int((m.get("usage_metadata") or {}).get("output_tokens") or 0) for m in ai]

                # COVERAGE: distinct entity ids the agent actually touched (from tool-call args).
                ids = {"channel": set(), "team": set(), "user": set(), "group": set(), "chat": set()}
                for m in ai:
                    for tc in (m.get("tool_calls") or []):
                        for k, v in (tc.get("args") or {}).items():
                            if not isinstance(v, str):
                                continue
                            kl = k.lower().replace("_", "")
                            if "id" not in kl and kl not in ("channel", "team", "user", "group", "chat"):
                                continue
                            if "channel" in kl: ids["channel"].add(v)
                            elif "team" in kl: ids["team"].add(v)
                            elif "user" in kl or "principal" in kl: ids["user"].add(v)
                            elif "group" in kl: ids["group"].add(v)
                            elif "chat" in kl: ids["chat"].add(v)
                cover = {k: len(s) for k, s in ids.items()}

                # naive re-counts the cached prefix each turn; cached-proxy counts each history token
                # once (last input) + all outputs -> approximates real compute under ideal KV caching.
                naive = _sum_naive_tokens(r)
                cached = (ins[-1] if ins else 0) + sum(outs)
                reasoning = "\n---\n".join((m.get("reasoning") or "").strip() for m in ai
                                           if (m.get("reasoning") or "").strip())
                res = {"turns": turns, "tokens": naive, "tokens_cached": cached,
                       "chkpt": float(j["statistics"].get("verifier_level_pass_rate", 0)),
                       "n_calls": len(tool_seq), "n_unique": len(set(tool_seq)),
                       "in_last": (ins[-1] if ins else 0), "out_sum": sum(outs),
                       "cover": cover, "cover_total": sum(cover.values()),
                       "reasoning": reasoning, "tool_seq": tool_seq, "tool_trace": tool_trace}
        except Exception:
            pass
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)
    return res
