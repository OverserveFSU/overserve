#!/usr/bin/env python3
"""Collect the audit/prod rollout run_*.json under an ablation output dir into one grading dir,
then invoke the benchmark's own grader (evaluate_run.py, Qwen3-14B local vLLM) once."""
import shutil, subprocess, sys
from pathlib import Path

BC = Path("/home/ruiheng/aiagent/saas/benchmarks/BrowseComp-Plus")


def main():
    out = Path(sys.argv[1]).resolve()
    grade_dir = out / "grade_inputs"
    grade_dir.mkdir(exist_ok=True)
    n = 0
    for rj in sorted((out / "rollouts").glob("*/run_*.json")):
        label = rj.parent.name
        dst = grade_dir / ("%s__%s" % (label, rj.name))
        shutil.copy(rj, dst)
        n += 1
    print("collected %d run files into %s" % (n, grade_dir))
    cmd = [str(BC / ".venv/bin/python"), "scripts_evaluation/evaluate_run.py",
           "--input_dir", str(grade_dir), "--eval_dir", str(out / "evals"),
           "--model", "Qwen/Qwen3-14B", "--tensor_parallel_size", "1"]
    print("RUN", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=str(BC), check=True)


if __name__ == "__main__":
    main()
