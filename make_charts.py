# charts for the README -> charts/*.png

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import FuncFormatter

from ap_utils import BUCKETS, load_data, get_as_of, add_aging

os.makedirs("charts", exist_ok=True)

# colours (checked for colour-blind safety) + style
BLUE = "#2a78d6"
GREY = "#c3c2b7"
AGE_RAMP = ["#86b6ef", "#3987e5", "#256abf", "#104281"]   # light = new, dark = old
INK, INK_2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"

plt.rcParams.update({
    "font.family": "sans-serif", "font.size": 10,
    "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "axes.titlecolor": INK,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "xtick.color": MUTED, "ytick.color": MUTED,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.grid": True, "axes.axisbelow": True, "grid.color": GRID, "grid.linewidth": 0.6,
})


def millions(x, _):
    return f"{x / 1e6:,.0f}M"


def save(fig, name):
    fig.tight_layout()
    fig.savefig(f"charts/{name}.png", dpi=160)
    plt.close(fig)
    print("Saved", f"charts/{name}.png")


df = load_data()
as_of = get_as_of(df)
df = add_aging(df, as_of)

# how much is owed in each age bucket
by_bucket = df.groupby("aging_bucket")["owed_sar"].sum().reindex(BUCKETS)
share = by_bucket / by_bucket.sum()

fig, ax = plt.subplots(figsize=(8, 4.5))
ax.grid(axis="x", visible=False)
bars = ax.bar(BUCKETS, by_bucket, color=AGE_RAMP, width=0.6)
for bar, s in zip(bars, share):
    ax.annotate(f"{s:.0%}", (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4), textcoords="offset points", ha="center", color=INK_2)
ax.yaxis.set_major_formatter(FuncFormatter(millions))
ax.set_ylabel("Amount owed (SAR)")
ax.set_title("Balance owed by age", pad=24)
ax.text(0, 1.02, f"as of {as_of:%d %b %Y}",
        transform=ax.transAxes, color=INK_2)
save(fig, "aging_by_bucket")

# top 10 suppliers, split by age
pivot = (df.pivot_table(index="supplier_name", columns="aging_bucket",
                        values="owed_sar", aggfunc="sum", fill_value=0)
           .reindex(columns=BUCKETS, fill_value=0))
pivot["Total"] = pivot.sum(axis=1)
top = pivot.sort_values("Total", ascending=False).head(10).iloc[::-1]
top_share = top["Total"].sum() / pivot["Total"].sum()
top1_share = top["Total"].iloc[-1] / pivot["Total"].sum()

fig, ax = plt.subplots(figsize=(8, 5))
ax.grid(axis="y", visible=False)
left = np.zeros(len(top))
for bucket, colour in zip(BUCKETS, AGE_RAMP):
    vals = top[bucket].clip(lower=0)
    ax.barh(top.index, vals, left=left, color=colour, height=0.6,
            edgecolor=SURFACE, linewidth=1.5, label=bucket)
    left += vals
ax.xaxis.set_major_formatter(FuncFormatter(millions))
ax.set_xlabel("Amount owed (SAR)")
ax.set_title("Top 10 suppliers by balance", pad=24)
ax.text(0, 1.02, f"biggest supplier = {top1_share:.0%} of total, top 10 = {top_share:.0%}",
        transform=ax.transAxes, color=INK_2)
ax.legend(frameon=False, loc="lower right", fontsize=9)
save(fig, "top_suppliers")

# supplier groups from the clustering model (one panel per group)
clusters = pd.read_csv("outputs/supplier_clusters.csv")
n_suppliers = len(clusters)
clusters = clusters[clusters["total_size_sar"] >= 100]   # hide near-zero balances
groups = sorted(clusters["group"].unique())

fig, axes = plt.subplots(2, 2, figsize=(9, 7), sharex=True, sharey=True)
for ax, g in zip(axes.flat, groups):
    others = clusters[clusters["group"] != g]
    mine = clusters[clusters["group"] == g]
    ax.scatter(others["avg_age_days"], others["total_size_sar"], s=14, color=GREY,
               alpha=0.6, linewidths=0)
    ax.scatter(mine["avg_age_days"], mine["total_size_sar"], s=22, color=BLUE,
               edgecolors=SURFACE, linewidths=0.8)
    ax.set_yscale("log")
    ax.yaxis.set_major_formatter(FuncFormatter(
        lambda y, _: f"{y/1e6:,.0f}M" if y >= 1e6 else f"{y/1e3:,.0f}K" if y >= 1e3 else f"{y:,.0f}"))
    ax.set_title(f"{g} ({len(mine)})", fontsize=11)
for ax in axes[1]:
    ax.set_xlabel("Average age (days)")
for ax in axes[:, 0]:
    ax.set_ylabel("Total balance (SAR, log scale)")
fig.suptitle(f"Supplier clusters (k-means, {n_suppliers} suppliers)", x=0.02, ha="left",
             fontsize=13, fontweight="bold", color=INK)
save(fig, "supplier_groups")

# audit flags found
flags = pd.read_csv("outputs/audit_flags.csv")
counts = flags["check"].value_counts().sort_values()
labels = counts.index.str.replace("_", " ").str.capitalize()

fig, ax = plt.subplots(figsize=(8, 4))
ax.grid(axis="y", visible=False)
ax.barh(labels, counts, color=BLUE, height=0.55)
for y, v in enumerate(counts):
    ax.annotate(f"{v}", (v, y), xytext=(4, 0), textcoords="offset points",
                va="center", color=INK_2)
ax.set_xlabel("Invoice lines flagged")
ax.set_title(f"Audit flags ({len(flags):,} lines)")
save(fig, "audit_flags")
