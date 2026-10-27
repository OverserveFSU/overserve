# PROVENANCE: hand-specified experimental control (Bedrock connectivity probe).
# Reproduces the verified working call: us.anthropic.claude-fable-5-1 via inference
# profile in us-east-1, using the bedrock-api-key bearer token from amazonapi.txt.
# NOTE: amazonapi.txt holds a live secret -- never commit it, never send the key anywhere but AWS Bedrock.
import os, sys, json, urllib.request, urllib.error

KEY_FILE = os.environ.get("BEDROCK_KEY_FILE", os.path.join(os.path.dirname(__file__), "..", "amazonapi.txt"))
REGION   = os.environ.get("BEDROCK_REGION", "us-east-1")         # key is region-bound; us-west-2 -> 403
MODEL    = os.environ.get("BEDROCK_MODEL", "us.anthropic.claude-fable-5-1")  # inference-profile id, NOT bare model id
PROMPT   = os.environ.get("BEDROCK_PROMPT", "Who made you? Reply in one short sentence, then say OK.")


def load_key():
    # amazonapi.txt: first non-empty line is the bare token; a later line may be
    # "export AWS_BEARER_TOKEN_BEDROCK=<token>". Take the first line that looks like a key.
    for ln in open(KEY_FILE):
        ln = ln.strip()
        if not ln:
            continue
        if "AWS_BEARER_TOKEN_BEDROCK=" in ln:
            ln = ln.split("AWS_BEARER_TOKEN_BEDROCK=", 1)[1].strip()
        if ln.startswith("bedrock-api-key-"):
            return ln
    raise ValueError("no bedrock-api-key- token found in %s" % KEY_FILE)


def converse(model, region, key, prompt):
    url = "https://bedrock-runtime.%s.amazonaws.com/model/%s/converse" % (region, model)
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": 128},  # fable-5-1 rejects temperature (deprecated for this model)
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": "Bearer " + key, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def main():
    key = load_key()
    print("region=%s model=%s keylen=%d" % (REGION, MODEL, len(key)), flush=True)
    status, resp = converse(MODEL, REGION, key, PROMPT)
    print("HTTP", status, flush=True)
    if status == 200 and isinstance(resp, dict):
        txt = resp["output"]["message"]["content"][0]["text"]
        u = resp.get("usage", {})
        print("TEXT:", txt.strip())
        print("USAGE: in=%s out=%s total=%s  stop=%s"
              % (u.get("inputTokens"), u.get("outputTokens"), u.get("totalTokens"), resp.get("stopReason")))
    else:
        print("BODY:", resp)
        sys.exit(1)


if __name__ == "__main__":
    main()
