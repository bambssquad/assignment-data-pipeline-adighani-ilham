"""Membuat documentation/data-flow-diagram.png (Data Flow Diagram ETL)."""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

OUT = Path(__file__).resolve().parent / "data-flow-diagram.png"
steps = [
    ("Raw Dataset", "data/raw/\nautomobileEDA_\ndirty_training.csv", "#e8eaf6"),
    ("Load Data", "load_data()\nExtract", "#e3f2fd"),
    ("Data Inspection", "inspect_data()\nshape, dtypes,\nNaN, duplikat", "#e0f7fa"),
    ("Data Cleaning", "clean_data()\nformat, dedup,\nimputasi", "#e8f5e9"),
    ("Data Transformation", "transform_data()\nMin-Max scaling\n+ encoding", "#fff8e1"),
    ("Processed Dataset", "save_data() - Load\ndata/processed/\nautomobileEDA_processed.csv", "#fce4ec"),
]
fig, ax = plt.subplots(figsize=(15.6, 3.6))
ax.set_xlim(0, 15.5)
ax.set_ylim(0, 3.6)
ax.axis("off")
w, h, gap = 2.25, 1.7, 0.35
for i, (t, s, c) in enumerate(steps):
    x = 0.15 + i * (w + gap)
    y = 1.0
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.04,rounding_size=0.12", fc=c, ec="#37474f", lw=1.4))
    ax.text(x + w / 2, y + h * 0.76, t, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#263238")
    ax.text(x + w / 2, y + h * 0.36, s, ha="center", va="center", fontsize=7.5, color="#455a64", linespacing=1.4)
    if i < len(steps) - 1:
        ax.add_patch(FancyArrowPatch((x + w + 0.04, y + h / 2), (x + w + gap - 0.04, y + h / 2), arrowstyle="-|>", mutation_scale=16, color="#37474f", lw=1.6))
for a, b, label in [(0, 1, "EXTRACT"), (2, 4, "TRANSFORM"), (5, 5, "LOAD")]:
    xa = 0.15 + a * (w + gap)
    xb = 0.15 + b * (w + gap) + w
    ax.plot([xa, xb], [0.72, 0.72], color="#78909c", lw=2)
    ax.text((xa + xb) / 2, 0.4, label, ha="center", fontsize=10, fontweight="bold", color="#78909c")
ax.text(7.75, 3.3, "Data Flow Diagram - ETL Pipeline Automobile Dataset", ha="center", fontsize=13, fontweight="bold", color="#263238")
fig.savefig(OUT, dpi=150, bbox_inches="tight", facecolor="white")
print(f"tersimpan: {OUT}")
