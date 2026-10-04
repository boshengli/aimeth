"""Enqueue gene co-expression knowledge-prior jobs (fast, thinking disabled) for a GLM pool.
Usage: python tools/enqueue_knowledge.py ANNOT OUT_DIR QUEUE_FILE --specs glm-5.3:nothink:3 glm-5.3-flash:nothink:3 glm-5.3:think:1
Each job asks for the panel genes most positively / negatively co-expressed with one target gene in tomato callus cells.
Answers are later scored against measured Xenium co-expression; no measured data is shown to the model.
"""
import argparse, csv, json
from pathlib import Path

SYSTEM = "You are an expert in plant developmental biology, regeneration and tomato gene function."
PROMPT = """Context: single-cell spatial transcriptomics (Xenium, 480-gene targeted panel) of tomato (Solanum lycopersicum)
callus during shoot regeneration, sampled 3 to 15 days after callus induction, wild type.

Target gene: {gid} ({sym}; group: {grp}; category: {cat})

Using only your biological knowledge (regulatory relationships, shared pathways, cell-type programs), choose from the panel
below the 10 genes whose expression across individual callus cells is most likely POSITIVELY correlated with the target,
and the 10 most likely NEGATIVELY correlated. Use the Solyc IDs exactly as listed. Do not include the target itself.

Panel (ID, symbol, category):
{panel}

Answer with JSON only: {{"positive": ["Solyc...", ...], "negative": ["Solyc...", ...], "confidence": <0-1>}}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("annot"); ap.add_argument("out"); ap.add_argument("queue")
    ap.add_argument("--specs", nargs="+", required=True)
    a = ap.parse_args()
    rows = list(csv.reader(open(a.annot, encoding="utf-8-sig")))[1:]
    genes = [(r[0], r[1], r[2].strip(), r[3].strip()) for r in rows]
    panel = "\n".join(f"{g}\t{s}\t{c}" for g, s, _, c in genes)
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(a.queue, "a") as q:
        for gid, sym, grp, cat in genes:
            prompt = PROMPT.format(gid=gid, sym=sym, grp=grp or "-", cat=cat or "-", panel=panel)
            for spec in a.specs:
                model, mode, k = spec.split(":")
                extra = {"thinking": {"type": "disabled"}} if mode == "nothink" else {}
                max_tok = 2048 if mode == "nothink" else 32768
                for s in range(int(k)):
                    path = out / f"{gid}__{model}__{mode}__s{s}.json"
                    if path.exists():
                        continue
                    q.write(json.dumps({"job_id": f"kn:{gid}:{model}:{mode}:s{s}", "workload": "gene_knowledge", "model": model,
                                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                                        "max_tokens": max_tok, "extra": extra, "out_path": str(path),
                                        "meta": {"gene": gid, "symbol": sym, "mode": mode, "sample": s}}, ensure_ascii=False) + "\n")
                    n += 1
    print("enqueued", n)


if __name__ == "__main__":
    main()
