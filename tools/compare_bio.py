import json, collections, numpy as np
V = "/data/libs/aimeth/p2-bio/v1"
base = collections.defaultdict(dict)
for r in json.load(open(V + "/results/baseline_summary.json")):
    base[r["task_id"]][r["solver"]] = r["pattern_r_mean"]
best = {t: max(v.values()) for t, v in base.items()}
ridge_pg = {}
import glob
for f in glob.glob(V + "/results/*__ridge.json"):
    tid = f.split("/")[-1].rsplit("__ridge.json", 1)[0]
    ridge_pg[tid] = {g: d["pattern_r"] for g, d in json.load(open(f))["per_gene"].items() if d["informative"]}
ann = {}
for s in json.load(open(V + "/mask_sets.json")).values():
    for g in s: ann[g["id"]] = g.get("symbol", g["id"])
rows = []
for run in ["calib-v2", "calib-v2-glm"]:
    for r in json.load(open(f"/data/libs/aimeth/p2-bio/runs/{run}/eval_results.json")):
        model = r["program"].split("__")[5]
        rows.append((model, r["task_id"], r["status"], r.get("pattern_r_mean")))
by = collections.defaultdict(list)
for m, t, st, sc in rows: by[m].append((t, st, sc))
for m, lst in by.items():
    ok = [(t, sc) for t, st, sc in lst if st == "ok"]
    d = [sc - best[t] for t, sc in ok]
    win = sum(x > 0 for x in d)
    print(f"{m}: programs {len(lst)}, valid {len(ok)} ({100*len(ok)/len(lst):.0f}%), mean score {np.mean([s for _, s in ok]):.3f}, "
          f"mean(score - best baseline) {np.mean(d):+.3f}, beats best baseline {win}/{len(ok)}")
    tiers = collections.defaultdict(list)
    for t, sc in ok:
        tier, _, _, mask = t.split("__"); tiers[(tier, mask)].append(sc - best[t])
    for k in sorted(tiers): print(f"    {k}: n={len(tiers[k])} delta={np.mean(tiers[k]):+.3f}")
# best program per task (oracle over samples) vs baseline
ob = collections.defaultdict(lambda: -9)
for m, t, st, sc in rows:
    if st == "ok": ob[(m, t)] = max(ob[(m, t)], sc)
print("best-of-samples beats baseline:", {m: f"{sum(ob[(m,t)] > best[t] for (mm,t) in ob if mm==m)}/{sum(1 for (mm,t) in ob if mm==m)}" for m in by})
# hard chain genes: per-gene comparison with ridge
chain = {"PI-II", "PI-2a", "SYR1", "PRS", "PORK1"}
pg = collections.defaultdict(list)
for run in ["calib-v2", "calib-v2-glm"]:
    for r in json.load(open(f"/data/libs/aimeth/p2-bio/runs/{run}/eval_results.json")):
        if r["status"] != "ok" or "immunity" not in r["task_id"]: continue
        for g, v in r["per_gene"].items():
            if ann.get(g) in chain and g in ridge_pg[r["task_id"]]:
                pg[ann[g]].append(v - ridge_pg[r["task_id"]][g])
print("chain genes (program - ridge, pattern r):", {k: (round(float(np.mean(v)), 3), len(v)) for k, v in pg.items()})
err = collections.Counter()
for run in ["calib-v2", "calib-v2-glm"]:
    for r in json.load(open(f"/data/libs/aimeth/p2-bio/runs/{run}/eval_results.json")):
        if r["status"] != "ok": err[(r["status"], (r.get("detail") or "").strip().splitlines()[-1][:90] if r.get("detail") else "")] += 1
for k, v in err.most_common(8): print("  ", v, k)
