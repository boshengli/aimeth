"""Score language-model gene co-expression priors against measured Xenium co-expression.

Usage: python tools/kn_score.py REF.npz ANNOT.csv MASK_SETS.json ANSWER_DIR OUT_DIR

Each answer names 10 panel genes predicted to be most positively and 10 most negatively co-expressed
with one target gene. Primary read-out (fixed before any answer was scored): on the cell-level reference,
gap = mean percentile of the predicted positives minus mean percentile of the predicted negatives among
the target's 479 measured partners (0 for a random guess, 1 for perfect). Secondary: the same on the
spatially smoothed reference, hit rates in the measured top/bottom 20 (random 0.042), and mean measured r.
Comparators: (a) annotation baseline - positives drawn from the target's own functional group, negatives
from other groups (50 draws); (b) split-half data bound - top/bottom 10 from four slices, scored on the
other four. Summaries average samples within a gene, then genes; 95% intervals bootstrap genes.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import rankdata

K, TOPN = 10, 20
SPLIT_A = ["WT-3D-1", "WT-12D-1", "WT-15D-1", "WT-15D-3"]
WATCH = ["WIND1", "PI-2a", "PI-2b", "PI-II", "MYC2", "PORK1", "SYR1", "PRS", "PRP", "PIN2"]


def parse(text: str, panel: set[str], target: str):
    text = text or ""
    obj = None
    for m in re.finditer(r"\{.*\}", text, flags=re.S):
        try:
            obj = json.loads(m.group(0))
            break
        except Exception:
            continue
    if obj is None:
        pos_txt, _, neg_txt = text.partition("negative")
        obj = {"positive": re.findall(r"Solyc\w+", pos_txt), "negative": re.findall(r"Solyc\w+", neg_txt)}
    out, invalid = {}, 0
    for side in ("positive", "negative"):
        seen = []
        for g in obj.get(side) or []:
            g = str(g).strip()
            if g in panel and g != target and g not in seen:
                seen.append(g)
            elif g not in panel:
                invalid += 1
        out[side] = seen[:K]
    both = set(out["positive"]) & set(out["negative"])
    out["positive"] = [g for g in out["positive"] if g not in both]
    out["negative"] = [g for g in out["negative"] if g not in both]
    return out, invalid, obj.get("confidence")


class Ref:
    def __init__(self, R: np.ndarray, genes: list[str]):
        self.R, self.ix = R, {g: i for i, g in enumerate(genes)}
        self.pct = np.full_like(R, np.nan)
        n = len(genes)
        for i in range(n):
            row = R[i].copy()
            row[i] = np.nan
            ok = ~np.isnan(row)
            self.pct[i, ok] = (rankdata(row[ok]) - 1) / max(ok.sum() - 1, 1)
        self.top = {}
        for i in range(n):
            row = R[i].copy()
            row[i] = np.nan
            o = np.argsort(np.where(np.isnan(row), -np.inf, row))
            valid = o[~np.isnan(row[o])]
            self.top[i] = (set(valid[-TOPN:]), set(valid[:TOPN]))

    def score(self, target: str, pos: list[str], neg: list[str]) -> dict:
        i = self.ix[target]
        p = [self.ix[g] for g in pos]
        q = [self.ix[g] for g in neg]
        f = lambda a, idx: float(np.nanmean(a[i, idx])) if idx else float("nan")  # noqa: E731
        top, bot = self.top[i]
        d = {"pos_pct": f(self.pct, p), "neg_pct": f(self.pct, q), "pos_r": f(self.R, p), "neg_r": f(self.R, q),
             "pos_hit": len(top & set(p)) / K, "neg_hit": len(bot & set(q)) / K}
        d["gap"] = d["pos_pct"] - d["neg_pct"] if p and q else float("nan")
        return d


def boot(x: np.ndarray, n: int = 2000, seed: int = 0):
    x = x[~np.isnan(x)]
    if len(x) == 0:
        return [float("nan")] * 3
    rng = np.random.default_rng(seed)
    m = rng.choice(x, size=(n, len(x))).mean(1)
    return [float(x.mean()), float(np.quantile(m, 0.025)), float(np.quantile(m, 0.975))]


def main(ref_path, annot, masks, ans_dir, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    z = np.load(ref_path)
    genes = [str(g) for g in z["genes"]]
    panel = set(genes)
    refs = {"cell": Ref(z["R_cell"], genes), "smooth": Ref(z["R_smooth"], genes)}
    rows = list(csv.reader(open(annot, encoding="utf-8-sig")))[1:]
    ann = {r[0]: {"symbol": r[1], "group": r[2].strip(), "category": r[3].strip()} for r in rows if r and r[0] in panel}
    mask = json.load(open(masks))
    mask = mask.get("sets", mask) if isinstance(mask, dict) else mask
    sets = {k: {d["id"] if isinstance(d, dict) else d for d in v} for k, v in mask.items() if isinstance(v, list)}

    # model answers
    per = []
    for fp in sorted(Path(ans_dir).glob("*.json")):
        gid, model, mode, s = fp.stem.split("__")
        if gid not in panel:
            continue
        parsed, invalid, conf = parse(fp.read_text(), panel, gid)
        rec = {"gene": gid, "arm": f"{model}:{mode}", "sample": s, "n_pos": len(parsed["positive"]),
               "n_neg": len(parsed["negative"]), "invalid_ids": invalid, "confidence": conf,
               "pos": parsed["positive"], "neg": parsed["negative"]}
        for rn, ref in refs.items():
            for k, v in ref.score(gid, parsed["positive"], parsed["negative"]).items():
                rec[f"{rn}_{k}"] = v
        per.append(rec)

    # ensemble per gene x arm: majority vote across samples
    groups = defaultdict(list)
    for r in per:
        groups[(r["gene"], r["arm"])].append(r)
    for (gid, arm), rs in list(groups.items()):
        if len(rs) < 2:
            continue
        rec = {"gene": gid, "arm": arm + ":vote", "sample": "vote"}
        for side, key in (("positive", "pos"), ("negative", "neg")):
            cnt = defaultdict(float)
            for r in rs:
                for rank, g in enumerate(r[key]):
                    cnt[g] += 1 + (K - rank) / (10 * K)
            rec[key] = [g for g, _ in sorted(cnt.items(), key=lambda t: -t[1])[:K]]
        overlap = set(rec["pos"]) & set(rec["neg"])
        rec["pos"] = [g for g in rec["pos"] if g not in overlap]
        rec["neg"] = [g for g in rec["neg"] if g not in overlap]
        jac = [len(set(a["pos"]) & set(b["pos"])) / max(len(set(a["pos"]) | set(b["pos"])), 1)
               for ia, a in enumerate(rs) for b in rs[ia + 1:]]
        rec["self_jaccard_pos"] = float(np.mean(jac))
        for rn, ref in refs.items():
            for k, v in ref.score(gid, rec["pos"], rec["neg"]).items():
                rec[f"{rn}_{k}"] = v
        per.append(rec)

    # comparators
    rng = np.random.default_rng(0)
    by_group = defaultdict(list)
    for g, a in ann.items():
        by_group[a["group"]].append(g)
    for gid in genes:
        if gid not in ann:
            continue
        same = [g for g in by_group[ann[gid]["group"]] if g != gid]
        other = [g for g in genes if g in ann and ann[g]["group"] != ann[gid]["group"]]
        if len(same) >= 2:
            acc = defaultdict(list)
            for _ in range(50):
                pos = list(rng.choice(same, size=min(K, len(same)), replace=False))
                neg = list(rng.choice(other, size=K, replace=False))
                for rn, ref in refs.items():
                    for k, v in ref.score(gid, pos, neg).items():
                        acc[f"{rn}_{k}"].append(v)
            per.append({"gene": gid, "arm": "baseline:annotation_group", "sample": "mean50",
                        **{k: float(np.nanmean(v)) for k, v in acc.items()}})
    sl = [str(s) for s in z["slices"]]
    a_ix = [sl.index(s) for s in SPLIT_A]
    b_ix = [i for i in range(len(sl)) if i not in a_ix]
    for rn, key in (("cell", "R_cell_slices"), ("smooth", "R_smooth_slices")):
        RA = np.nanmean(z[key][a_ix], 0)
        RB = Ref(np.nanmean(z[key][b_ix], 0), genes)
        for i, gid in enumerate(genes):
            row = RA[i].copy()
            row[i] = np.nan
            o = [j for j in np.argsort(np.where(np.isnan(row), np.inf, row)) if not np.isnan(row[j])]
            neg, pos = [genes[j] for j in o[:K]], [genes[j] for j in o[-K:]]
            rec = next((r for r in per if r["gene"] == gid and r["arm"] == "bound:split_half_data"), None)
            if rec is None:
                rec = {"gene": gid, "arm": "bound:split_half_data", "sample": "A->B"}
                per.append(rec)
            for k, v in RB.score(gid, pos, neg).items():
                rec[f"{rn}_{k}"] = v

    with open(out_dir / "per_answer.jsonl", "w") as fh:
        for r in per:
            fh.write(json.dumps(r) + "\n")

    # summaries
    metrics = ["cell_gap", "smooth_gap", "cell_pos_pct", "cell_neg_pct", "cell_pos_hit", "cell_neg_hit",
               "cell_pos_r", "cell_neg_r", "smooth_pos_hit", "smooth_neg_hit"]
    scopes = {"all": None, **{f"mask:{k}": v for k, v in sets.items()}}
    summary = {}
    arms = sorted({r["arm"] for r in per})
    for scope, members in scopes.items():
        summary[scope] = {}
        for arm in arms:
            g2 = defaultdict(lambda: defaultdict(list))
            extra = defaultdict(list)
            for r in per:
                if r["arm"] != arm or (members is not None and r["gene"] not in members):
                    continue
                for m in metrics:
                    if m in r:
                        g2[r["gene"]][m].append(r[m])
                for m in ("invalid_ids", "n_pos", "n_neg", "self_jaccard_pos"):
                    if r.get(m) is not None:
                        extra[m].append(r[m])
            if not g2:
                continue
            s = {"genes": len(g2), "answers": sum(len(v.get("cell_gap", [])) for v in g2.values())}
            for m in metrics:
                s[m] = boot(np.array([np.nanmean(v[m]) if v.get(m) else np.nan for v in g2.values()]))
            for m, v in extra.items():
                s["mean_" + m] = float(np.mean(v))
            summary[scope][arm] = s
    sym2id = {a["symbol"]: g for g, a in ann.items()}
    watch = {}
    for a in WATCH:
        if a in sym2id:
            watch[a] = sym2id[a]
    pairs = {}
    if "WIND1" in watch:
        w = watch["WIND1"]
        for a, g in watch.items():
            if g == w:
                continue
            i, j = genes.index(w), genes.index(g)
            pairs[f"WIND1~{a}"] = {"cell_r": float(z["R_cell"][i, j]), "smooth_r": float(z["R_smooth"][i, j]),
                                   "cell_r_by_slice": dict(zip(sl, map(float, z["R_cell_slices"][:, i, j]))),
                                   "smooth_r_by_slice": dict(zip(sl, map(float, z["R_smooth_slices"][:, i, j])))}
    json.dump({"summary": summary, "watch_ids": watch, "measured_pairs": pairs}, open(out_dir / "summary.json", "w"),
              indent=1)
    lines = ["| scope | arm | genes | answers | gap cell [95% CI] | gap smooth | pos hit@20 | neg hit@20 | invalid ids/answer |",
             "|---|---|---|---|---|---|---|---|---|"]
    for scope, d in summary.items():
        for arm, s in d.items():
            g, gs = s["cell_gap"], s["smooth_gap"]
            lines.append(f"| {scope} | {arm} | {s['genes']} | {s['answers']} | {g[0]:.3f} [{g[1]:.3f}, {g[2]:.3f}] | "
                         f"{gs[0]:.3f} | {s['cell_pos_hit'][0]:.3f} | {s['cell_neg_hit'][0]:.3f} | "
                         f"{s.get('mean_invalid_ids', float('nan')):.2f} |")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(json.dumps(pairs, indent=1)[:3000])


if __name__ == "__main__":
    main(*sys.argv[1:6])
