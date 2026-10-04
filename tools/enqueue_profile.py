"""Enqueue gene expression-profile prior jobs (time trend in WT callus; pi2 mutant effect) for a GLM pool.
Usage: python tools/enqueue_profile.py ANNOT OUT_DIR QUEUE_FILE --specs glm-5.3:nothink:3 glm-5.3-flash:nothink:3 glm-5.3:think:1
Answers are scored against pseudo-bulk Xenium changes (WT 3 -> 15 days; pi2 vs WT at 3 days); no data is shown.
"""
import argparse, csv, json
from pathlib import Path

SYSTEM = "You are an expert in plant developmental biology, regeneration and tomato gene function."
PROMPT = """Context: tomato (Solanum lycopersicum) callus induced for shoot regeneration, profiled by single-cell spatial
transcriptomics with a 480-gene targeted panel. Samples: wild type at 3, 12 and 15 days after callus induction, and the pi2
mutant (loss of function of PI-2, a Proteinase Inhibitor II family gene) at 3 days.

Gene: {gid} ({sym}; group: {grp}; category: {cat})

Using only your biological knowledge, predict for this gene, in whole-callus average expression:
1. time_trend: wild type 15 days relative to 3 days: "up", "down" or "flat"
2. pi2_effect: pi2 mutant relative to wild type at 3 days: "up", "down" or "unchanged"
Give a probability (0-1) that each prediction is right.

Answer with JSON only: {{"time_trend": "...", "time_conf": <0-1>, "pi2_effect": "...", "pi2_conf": <0-1>}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("annot"); ap.add_argument("out"); ap.add_argument("queue")
    ap.add_argument("--specs", nargs="+", required=True)
    ap.add_argument("--provider", default="zhipu_coding", help="zhipu_coding (direct) or glm_cc (through Claude Code)")
    ap.add_argument("--prefix", default="", help="job_id prefix to keep runs apart")
    a = ap.parse_args()
    rows = [r for r in csv.reader(open(a.annot, encoding="utf-8-sig")) if r and r[0].startswith("Solyc")]
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(a.queue, "a") as q:
        for r in rows:
            gid, sym, grp, cat = r[0], r[1], r[2].strip(), r[3].strip()
            prompt = PROMPT.format(gid=gid, sym=sym, grp=grp or "-", cat=cat or "-")
            for spec in a.specs:
                model, mode, k = spec.split(":")
                extra = {"thinking": {"type": "disabled"}} if mode == "nothink" else {}
                cc = {"think_budget": 32000, "effort": "high"} if mode == "cchigh" else {}
                max_tok = 1024 if mode == "nothink" else (16000 if mode == "cc" else 16384)
                for s in range(int(k)):
                    path = out / f"{gid}__{model}__{mode}__s{s}.json"
                    if path.exists():
                        continue
                    q.write(json.dumps({"job_id": f"{a.prefix}pf:{gid}:{model}:{mode}:s{s}", "workload": "gene_profile", "model": model,
                                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                        "max_tokens": max_tok, "extra": extra, "out_path": str(path),
                                        "provider": a.provider, "cc": cc,
                                        "meta": {"gene": gid, "symbol": sym, "mode": mode, "sample": s}}, ensure_ascii=False) + "\n")
                    n += 1
    print("enqueued", n)


if __name__ == "__main__":
    main()
