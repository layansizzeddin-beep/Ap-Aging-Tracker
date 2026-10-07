# groups suppliers with k-means -> outputs/supplier_clusters.csv

import os

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ap_utils import load_data, get_as_of, add_aging

os.makedirs("outputs", exist_ok=True)
OUTPUT_FILE = "outputs/supplier_clusters.csv"
N_CLUSTERS = 4

df = load_data()
df = add_aging(df, get_as_of(df))
df["size"] = df["owed_sar"].abs()
df["days_old"] = df["days_old"].clip(lower=0)   # future-dated invoices count as 0 days


# describe each supplier with a few numbers ("features")
def share(rows, mask):
    """What fraction of this supplier's money is in rows matching mask."""
    total = rows["size"].sum()
    return rows.loc[mask, "size"].sum() / total if total > 0 else 0


def supplier_features(rows):
    total = rows["size"].sum()
    return pd.Series({
        "supplier_name": rows["supplier_name"].iloc[0],
        "invoices": len(rows),
        "owed_sar": rows["owed_sar"].sum(),
        "total_size_sar": total,
        # average age, where bigger invoices count more
        "avg_age_days": np.average(rows["days_old"], weights=rows["size"]) if total > 0 else 0,
        "share_over_180": share(rows, rows["days_old"] > 180),
        "share_adv_ret": share(rows, rows["item_category"] != "Other"),
    })


suppliers = df.groupby("supplier_id").apply(supplier_features, include_groups=False)

# log10 on size and count, otherwise the one giant supplier squashes everyone else
features = pd.DataFrame({
    "log_size": np.log10(suppliers["total_size_sar"].astype(float) + 1),
    "log_invoices": np.log10(suppliers["invoices"].astype(float)),
    "avg_age_days": suppliers["avg_age_days"].astype(float),
    "share_over_180": suppliers["share_over_180"].astype(float),
    "share_adv_ret": suppliers["share_adv_ret"].astype(float),
})

# standardise so days (0-1000) don't outweigh shares (0-1)
X = StandardScaler().fit_transform(features)

# run k-means
model = KMeans(n_clusters=N_CLUSTERS, n_init=20, random_state=0).fit(X)
suppliers["cluster"] = model.labels_

# silhouette score: -1 to 1, higher = groups more clearly separated
print(f"Silhouette score for {N_CLUSTERS} groups: {silhouette_score(X, model.labels_):.2f}")
for k in range(2, 8):
    labels = KMeans(n_clusters=k, n_init=20, random_state=0).fit_predict(X)
    print(f"  k={k}: {silhouette_score(X, labels):.2f}")


# name each group from its average profile
profile = features.groupby(suppliers["cluster"]).mean()
biggest = profile["log_size"].idxmax()


def name_group(c):
    p = profile.loc[c]
    if p["share_over_180"] > 0.5:
        return "Old balances to chase"
    if c == biggest:
        return "Key suppliers"
    if p["share_adv_ret"] > 0.5:
        return "Advances and retentions"
    return "Small and up to date"


names = {c: name_group(c) for c in profile.index}
# make names unique if two groups end up with the same one
seen = {}
for c, n in names.items():
    seen[n] = seen.get(n, 0) + 1
    if seen[n] > 1:
        names[c] = f"{n} ({seen[n]})"
suppliers["group"] = suppliers["cluster"].map(names)

# save and print a summary of each group
suppliers = suppliers.sort_values(["group", "total_size_sar"], ascending=[True, False])
suppliers.round(3).to_csv(OUTPUT_FILE)

summary = suppliers.groupby("group").agg(
    suppliers=("supplier_name", "size"),
    owed_sar=("owed_sar", "sum"),
    median_invoices=("invoices", "median"),
    avg_age_days=("avg_age_days", "mean"),
    share_over_180=("share_over_180", "mean"),
    share_adv_ret=("share_adv_ret", "mean"),
)
print()
print(summary.to_string(formatters={
    "owed_sar": "{:,.0f}".format, "avg_age_days": "{:.0f}".format,
    "share_over_180": "{:.0%}".format, "share_adv_ret": "{:.0%}".format}))
print(f"\nSaved {OUTPUT_FILE}")
