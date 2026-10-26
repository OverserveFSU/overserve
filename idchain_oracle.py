# PROVENANCE: hand-specified experimental instrument (fixed-point oracle for the interf2-idchain
# calibration environment). Mechanical state reconstruction + distance metric, NOT a data-derived
# result. The fixed-point definition is the interf2 task's two stated requirements.
"""interf2-idchain fixed-point oracle: reconstruct the (description, latest_msg) state from the
executed (tool, args, observation) trace and compute D_FP(s_t) = # of the two requirements violated.

interf2 requirements (both must hold):
  (a) description ENDS WITH "LATEST: <id>", <id> = id of the most recently posted message
  (b) the most recently posted message's content == the channel description (verbatim quote)

D_FP in {0,1,2}. 0 = fixed point. We reconstruct from the trace (no DB dependency, works after the
run) by tracking, per channel: current description, ordered list of (msg_id, content).

Tool effects modeled:
  send_channel_message(body.content=X)        -> append new message (id from observation), content=X
  update_channel(description=D)               -> set description=D
  update_channel_message(messageId=m, body=X) -> set that message's content=X (in place, no new id)
  soft_delete/undo etc. -> ignored for idchain state (out of scope for this task)
"""
import json, re


def _msg_id_from_obs(obs_text):
    """extract the created message id from a send_channel_message observation."""
    try:
        j = json.loads(obs_text)
        return j.get("id")
    except Exception:
        m = re.search(r'"id"\s*:\s*"([^"]+)"', obs_text or "")
        return m.group(1) if m else None


def reconstruct(tool_results):
    """tool_results: list of {tool_name, arguments, result}. Returns per-step D_FP list and final."""
    desc = None                      # current channel description
    msgs = []                        # ordered [(msg_id, content)]
    dfp_series = []

    def dfp():
        if not msgs:
            return 2                 # no message yet: (a) and (b) both unmet
        last_id, last_content = msgs[-1]
        a_ok = bool(desc) and desc.rstrip().endswith("LATEST: %s" % last_id)
        b_ok = (last_content is not None) and (desc is not None) and (last_content == desc)
        return (0 if a_ok else 1) + (0 if b_ok else 1)

    for t in tool_results:
        name = t.get("tool_name"); a = t.get("arguments") or {}
        inner = (t.get("result") or {}).get("result") or {}
        obs = (inner.get("content") or [{}])[0].get("text", "") if not inner.get("isError") else ""
        if name == "send_channel_message" and not inner.get("isError"):
            body = a.get("body") or {}
            content = body.get("content") if isinstance(body, dict) else a.get("content")
            mid = _msg_id_from_obs(obs)
            if mid:
                msgs.append((mid, content))
        elif name == "update_channel" and not inner.get("isError"):
            if "description" in a:
                desc = a["description"]
        elif name == "update_channel_message" and not inner.get("isError"):
            mid = a.get("messageId")
            body = a.get("body") or {}
            content = body.get("content") if isinstance(body, dict) else a.get("content")
            for i, (m, _) in enumerate(msgs):
                if m == mid:
                    msgs[i] = (mid, content)
        dfp_series.append({"after": name, "D_FP": dfp()})
    return {"D_FP_series": [s["D_FP"] for s in dfp_series],
            "D_FP_final": dfp_series[-1]["D_FP"] if dfp_series else 2,
            "reached_fixed_point": any(s["D_FP"] == 0 for s in dfp_series),
            "first_fp_step": next((i for i, s in enumerate(dfp_series) if s["D_FP"] == 0), None),
            "detail": dfp_series}


if __name__ == "__main__":
    # self-test: a converging trace (with in-place edit) vs a cycling trace (no edit tool).
    conv = [
        {"tool_name": "create_channel", "arguments": {}, "result": {"result": {"isError": False, "content": [{"text": "{}"}]}}},
        {"tool_name": "send_channel_message", "arguments": {"body": {"content": "hello"}},
         "result": {"result": {"isError": False, "content": [{"text": '{"id":"m1"}'}]}}},
        {"tool_name": "update_channel", "arguments": {"description": "Review. LATEST: m1"},
         "result": {"result": {"isError": False, "content": [{"text": "{}"}]}}},
        {"tool_name": "update_channel_message", "arguments": {"messageId": "m1", "body": {"content": "Review. LATEST: m1"}},
         "result": {"result": {"isError": False, "content": [{"text": "{}"}]}}},
    ]
    print("converging (with edit):", reconstruct(conv))
    cyc = [
        {"tool_name": "send_channel_message", "arguments": {"body": {"content": "d0"}},
         "result": {"result": {"isError": False, "content": [{"text": '{"id":"m1"}'}]}}},
        {"tool_name": "update_channel", "arguments": {"description": "d0 LATEST: m1"},
         "result": {"result": {"isError": False, "content": [{"text": "{}"}]}}},
        {"tool_name": "send_channel_message", "arguments": {"body": {"content": "d0 LATEST: m1"}},
         "result": {"result": {"isError": False, "content": [{"text": '{"id":"m2"}'}]}}},
        {"tool_name": "update_channel", "arguments": {"description": "d0 LATEST: m2"},
         "result": {"result": {"isError": False, "content": [{"text": "{}"}]}}},
    ]
    print("cycling (no edit):", reconstruct(cyc))
