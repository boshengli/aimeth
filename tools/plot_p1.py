import json, sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
d = sys.argv[1] if len(sys.argv) > 1 else "runs/p1-offline-v1"
S = json.load(open(f"{d}/p1-snapshots-seed1.json"))
cmap = ListedColormap(["#f4f4f2", "#8c8c8c", "#3b7dd8", "#e0533a", "#cfd8c4"])  # empty, border, worker, expensive, other
panels = [("full", "100", "完整发育 · 第100步"), ("full", "200", "完整发育 · 第200步"), ("full", "300", "完整发育 · 第300步"),
          ("full+lesion", "201", "完整发育 · 切除右半后"), ("full+lesion", "300", "完整发育 · 切除后100步"),
          ("shuffled_signal", "300", "打乱信号 · 第300步"), ("fixed_population", "300", "固定群体 · 第300步"),
          ("fixed_population+lesion", "300", "固定群体 · 切除后100步")]
plt.rcParams["font.sans-serif"] = ["Noto Sans CJK SC", "WenQuanYi Zen Hei", "Arial Unicode MS", "DejaVu Sans"]
fig, axes = plt.subplots(2, 4, figsize=(13, 7.4))
for ax, (arm, step, title) in zip(axes.flat, panels):
    t = np.array(S[arm][step]) + 1
    ax.imshow(t, cmap=cmap, vmin=0, vmax=4, interpolation="nearest")
    ax.set_title(title, fontsize=11); ax.set_xticks([]); ax.set_yticks([])
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(["#8c8c8c", "#3b7dd8", "#e0533a", "#cfd8c4"], ["边界细胞", "工作细胞", "大模型基因表达细胞", "其他"])],
           loc="lower center", ncol=4, frameon=False, fontsize=11)
fig.tight_layout(rect=(0, 0.06, 1, 1), h_pad=2.2)
fig.savefig(f"{d}/p1-type-maps-seed1.png", dpi=150)
print("ok")
