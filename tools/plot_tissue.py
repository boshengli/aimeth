import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
d = "/data/libs/aimeth/p1-tissue-v1/out"
cmap = ListedColormap(["#f4f4f2", "#8c8c8c", "#3b7dd8", "#e0533a", "#cfd8c4"])
arms = [("full", "Full development"), ("shuffled_signal", "Shuffled signal"), ("task_blind", "Task-blind"), ("full+lesion", "Full + lesion (1,000 steps after)")]
fig, axes = plt.subplots(1, 4, figsize=(16, 4.6))
for ax, (a, t) in zip(axes, arms):
    ty = np.load(f"{d}/types-{a}-seed1.npz")["types"].astype(int) + 1
    ax.imshow(ty, cmap=cmap, vmin=0, vmax=4, interpolation="nearest")
    ax.set_title(t, fontsize=11); ax.set_xticks([]); ax.set_yticks([])
from matplotlib.patches import Patch
fig.legend(handles=[Patch(color=c, label=l) for c, l in zip(["#8c8c8c", "#3b7dd8", "#e0533a", "#cfd8c4"], ["border", "worker", "large-model gene on", "other"])], loc="lower center", ncol=4, frameon=False)
fig.tight_layout(rect=(0, 0.07, 1, 1))
fig.savefig(f"{d}/tissue-seed1.png", dpi=110)
# zoom on a lesion front
ty = np.load(f"{d}/types-full+lesion-seed1.npz")["types"].astype(int) + 1
ys, xs = np.nonzero(ty == 4)
cy, cx = int(np.median(ys)), int(np.median(xs))
fig, ax = plt.subplots(figsize=(5, 5))
ax.imshow(ty[max(cy-120,0):cy+120, max(cx-120,0):cx+120], cmap=cmap, vmin=0, vmax=4, interpolation="nearest")
ax.set_title("Lesion front (zoom, 240 x 240 cells)"); ax.set_xticks([]); ax.set_yticks([])
fig.savefig(f"{d}/tissue-lesion-zoom.png", dpi=110, bbox_inches="tight")
print("ok")
