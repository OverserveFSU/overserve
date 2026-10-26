"""Run a bounded causal probe; no network, external writes, or victim calls.

Example:
    python3 overserve/run_self_induced_sync.py --output /tmp/self_induced_probe
"""

import argparse
from self_induced_sync import causal_probe


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="new artifact directory")
    parser.add_argument("--cap", type=int, default=12)
    args = parser.parse_args()
    summary = causal_probe(args.output, cap=args.cap)
    for r in summary["results"]:
        print("%s: checks=%d stop=%s state=%s settled_after_stop=%s external_writes=%d" % (
            r["condition"], r["status_checks"], r["stopping_reason"],
            r["original_state_pass"], r["after_checks_stop"]["complete"],
            r["external_writer_events"]))
    print("Scripted causal probe only; victim amplification and review acceptance are unmeasured.")


if __name__ == "__main__":
    main()
