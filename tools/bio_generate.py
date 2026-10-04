"""Stage 1 (login node, network): ask models to write imputation programs.

Usage: python tools/bio_generate.py BENCH_DIR ANNOTATION_CSV RUN_DIR --models deepseek:deepseek-flash zhipu:glm-5.3-flash --samples 2
Writes RUN_DIR/programs/<task>__<provider>__<model>__s<k>.py and RUN_DIR/receipts.jsonl.
No answer key is read here.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from aimeth_bio.llm_client import chat  # noqa: E402
from aimeth_bio.bench import gene_annotation  # noqa: E402

LABEL = {"WT-3D": "wild-type callus, 3 days", "WT-12D": "wild-type callus, 12 days",
         "WT-15D": "wild-type callus, 15 days", "pi2-3D": "pi2 mutant callus, 3 days"}

SYSTEM = "You are an expert in plant developmental biology, spatial transcriptomics and scientific Python."

PROMPT = """Task: impute masked genes in a spatial transcriptomics section of tomato (Solanum lycopersicum) callus.

Data (Xenium, 480-gene targeted panel, single cells with 2-D centroids in microns):
- Reference section: {ref_label}. All genes are measured.
- Target section: {tgt_label}. {n_masked} genes are masked (hidden); the other {n_visible} genes are measured.
Expression values are log1p(count / visible_total * 100), where visible_total is each cell's total count over the visible genes only.

Write a Python function

    def predict(ref_visible, ref_masked, tgt_visible, tgt_xy, visible_genes, masked_genes, gene_info):
        ...
        return pred  # numpy array, shape (n_target_cells, n_masked), same value space as ref_masked

Inputs: ref_visible (n_ref x n_visible), ref_masked (n_ref x n_masked), tgt_visible (n_tgt x n_visible), tgt_xy (n_tgt x 2),
visible_genes / masked_genes (arrays of Solyc gene IDs, column order), gene_info (dict: gene ID -> {{"symbol","group","category"}}).
Allowed imports: numpy, scipy, math only. No file, network or system access. Must finish within 120 s for 30,000 target cells.

Scoring: for each masked gene, Pearson correlation between your prediction and the measured values across target cells,
after smoothing both over each cell's 10 nearest spatial neighbours; the score is the mean over genes.
Use statistical structure in the data and your biological knowledge of these genes (regulatory relationships, pathways,
how the target condition differs from the reference) wherever it helps.

Masked genes (ID, symbol, group, category):
{masked_table}

Return only one Python code block containing the full program."""


def build_prompt(info: dict, ann: dict, masked: list[str]) -> str:
    ref_l = LABEL[info["reference"].rsplit("-", 1)[0]]
    tgt_l = LABEL[info["target"].rsplit("-", 1)[0]]
    rows = "\n".join(f"{g}\t{ann.get(g, {}).get('symbol', '')}\t{ann.get(g, {}).get('group', '')}\t{ann.get(g, {}).get('category', '')}"
                     for g in masked)
    return PROMPT.format(ref_label=ref_l, tgt_label=tgt_l, n_masked=info["n_masked"], n_visible=info["n_visible"],
                         masked_table=rows)


def extract_code(text: str) -> str | None:
    m = re.findall(r"```(?:python)?\s*\n(.*?)```", text, flags=re.S)
    if m:
        return max(m, key=len)
    return text if "def predict" in text else None


def parse_spec(spec: str, default_max: int):
    """provider:model[:max_tokens[:key=value,key=value]]"""
    parts = spec.split(":")
    prov, model = parts[0], parts[1]
    max_tok = int(parts[2]) if len(parts) > 2 and parts[2] else default_max
    extra = {}
    if len(parts) > 3 and parts[3]:
        for kv in parts[3].split(","):
            k, v = kv.split("=", 1)
            extra[k] = v
    return prov, model, max_tok, extra


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("bench"), ap.add_argument("annotation"), ap.add_argument("run")
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--samples", type=int, default=2)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-tokens", type=int, default=16384)
    ap.add_argument("--only", default=None, help="substring filter on task_id")
    a = ap.parse_args()
    bench, run = Path(a.bench), Path(a.run)
    (run / "programs").mkdir(parents=True, exist_ok=True)
    ann = gene_annotation(Path(a.annotation))
    (run / "gene_info.json").write_text(json.dumps(ann, ensure_ascii=False))
    masks = {k: [d["id"] for d in v] for k, v in json.load(open(bench / "mask_sets.json")).items()}
    jobs = []
    for jf in sorted((bench / "tasks").glob("*.json")):
        info = json.load(open(jf))
        if a.only and a.only not in info["task_id"]:
            continue
        prompt = build_prompt(info, ann, masks[info["mask_set"]])
        for spec in a.models:
            prov, model, max_tok, extra = parse_spec(spec, a.max_tokens)
            for k in range(a.samples):
                out = run / "programs" / f"{info['task_id']}__{prov}__{model}__s{k}.py"
                if not out.exists():
                    jobs.append((info["task_id"], prov, model, k, prompt, out, max_tok, extra))
    (run / "prompt_example.txt").write_text(jobs[0][4] if jobs else "")
    print(f"{len(jobs)} calls", flush=True)

    def work(j):
        tid, prov, model, k, prompt, out, max_tok, extra = j
        rec = chat(prov, model, [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}],
                   str(run / "receipts.jsonl"), max_tokens=max_tok, extra=extra,
                   tag={"task_id": tid, "sample": k})
        code = extract_code(rec.get("content", "")) if rec.get("ok") else None
        if code:
            out.write_text(code)
        return tid, prov, k, rec.get("ok"), rec.get("finish_reason"), bool(code), (rec.get("usage") or {}).get("total_tokens")

    with ThreadPoolExecutor(a.workers) as ex:
        for r in ex.map(work, jobs):
            print(*r, flush=True)


if __name__ == "__main__":
    main()
