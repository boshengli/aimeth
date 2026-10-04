"""Enqueue ARC program-writing jobs for the GLM pool (test outputs are never included).
Usage: python tools/enqueue_arc.py ARC_DIR RUN QUEUE_FILE --models glm-5.3-flashx:3 glm-5.3:1
"""
import argparse, json
from pathlib import Path

SYSTEM = "You are an expert at abstract reasoning puzzles and Python programming."
PROMPT = """Solve this ARC (Abstraction and Reasoning Corpus) task by writing a program.

Each grid is a list of rows; cells are integers 0-9 (colours). The training pairs show input -> output.
Find the single transformation rule that maps every training input to its output, then write

    def transform(grid: list[list[int]]) -> list[list[int]]:
        ...

that applies the rule to any input of this task (including the test input shown below).
Allowed imports: numpy, math, collections, itertools, functools only. No file, network or system access.
Return only one Python code block containing the full program.

Training pairs:
{train}

Test input:
{test}"""


def fmt(g):
    return "\n".join(" ".join(str(v) for v in row) for row in g)


ap = argparse.ArgumentParser()
ap.add_argument("arc_dir"); ap.add_argument("run"); ap.add_argument("queue")
ap.add_argument("--models", nargs="+", required=True); ap.add_argument("--max-tokens", type=int, default=32768)
a = ap.parse_args()
run = Path(a.run); (run / "programs").mkdir(parents=True, exist_ok=True)
n = 0
with open(a.queue, "a") as q:
    for tf in sorted(Path(a.arc_dir).glob("*.json")):
        t = json.load(open(tf)); tid = tf.stem
        train = "\n\n".join(f"Example {i+1}\nInput:\n{fmt(p['input'])}\nOutput:\n{fmt(p['output'])}" for i, p in enumerate(t["train"]))
        test = "\n\n".join(fmt(p["input"]) for p in t["test"])
        prompt = PROMPT.format(train=train, test=test)
        for spec in a.models:
            m, k = spec.split(":"); k = int(k)
            for s in range(k):
                out = run / "programs" / f"{tid}__{m}__s{s}.py"
                if out.exists():
                    continue
                q.write(json.dumps({"job_id": f"arc:{tid}:{m}:s{s}", "workload": "arc_calib", "model": m,
                                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                    "max_tokens": a.max_tokens, "out_path": str(out), "extract": "python",
                                    "meta": {"task": tid, "sample": s}}) + "\n")
                n += 1
print("enqueued", n)
