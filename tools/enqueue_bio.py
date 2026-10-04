"""Enqueue callus-imputation program-writing jobs for the GLM pool.
Usage: python tools/enqueue_bio.py BENCH ANNOT RUN QUEUE_FILE --models glm-5.3-flash glm-5.3 glm-5.3-flashx --samples 4
"""
import argparse, json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.bench import gene_annotation  # noqa: E402
from tools.bio_generate import build_prompt, SYSTEM  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("bench"); ap.add_argument("annot"); ap.add_argument("run"); ap.add_argument("queue")
ap.add_argument("--models", nargs="+", required=True); ap.add_argument("--samples", type=int, default=4)
ap.add_argument("--max-tokens", type=int, default=65536)
a = ap.parse_args()
bench, run = Path(a.bench), Path(a.run)
ann = gene_annotation(Path(a.annot))
(run / "programs").mkdir(parents=True, exist_ok=True)
(run / "gene_info.json").write_text(json.dumps(ann, ensure_ascii=False))
masks = {k: [d["id"] for d in v] for k, v in json.load(open(bench / "mask_sets.json")).items()}
n = 0
with open(a.queue, "a") as q:
    for jf in sorted((bench / "tasks").glob("*.json")):
        info = json.load(open(jf))
        prompt = build_prompt(info, ann, masks[info["mask_set"]])
        for m in a.models:
            for k in range(a.samples):
                out = run / "programs" / f"{info['task_id']}__zhipu_coding__{m}__s{k}.py"
                if out.exists():
                    continue
                q.write(json.dumps({"job_id": f"bio:{info['task_id']}:{m}:s{k}", "workload": "bio_calib", "model": m,
                                    "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                    "max_tokens": a.max_tokens, "out_path": str(out), "extract": "python",
                                    "meta": {"task_id": info["task_id"], "sample": k}}, ensure_ascii=False) + "\n")
                n += 1
print("enqueued", n)
