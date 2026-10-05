"""Compare graded ARC arms on a task list (descriptive; paired by task).
Usage: python tools/arc_compare.py TASKS.json NAME=GRADED.jsonl [NAME=GRADED.jsonl ...]
"""
import json
import sys

import numpy as np


def main():
    tasks = json.load(open(sys.argv[1]))
    tasks = tasks.get("task_ids", tasks) if isinstance(tasks, dict) else tasks
    arms = {}
    for spec in sys.argv[2:]:
        name, path = spec.split("=", 1)
        arms[name] = {json.loads(l)["task_id"]: json.loads(l) for l in open(path)}
    solved = lambda a, t: bool(arms[a].get(t, {}).get("final") and arms[a][t]["final"].get("solved"))  # noqa: E731
    print(f"tasks: {len(tasks)}")
    for a, g in arms.items():
        have = [t for t in tasks if t in g]
        tok = [g[t].get("completion_tokens") or 0 for t in have]
        print(f"{a:16s} solved {sum(solved(a, t) for t in have):3d}/{len(have):3d}   "
              f"mean completion tokens {np.mean(tok):9.0f}")
    names = list(arms)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            both = [t for t in tasks if t in arms[a] and t in arms[b]]
            wa = sum(solved(a, t) and not solved(b, t) for t in both)
            wb = sum(solved(b, t) and not solved(a, t) for t in both)
            print(f"  {a} vs {b}: only {a} {wa}, only {b} {wb}, n {len(both)}")


if __name__ == "__main__":
    main()
