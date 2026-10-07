# fills dashboard_template.html with the numbers -> dashboard.html

import json

import pandas as pd

from ap_utils import BUCKETS, load_data, get_as_of, add_aging

TEMPLATE = "dashboard_template.html"
OUTPUT_FILE = "dashboard.html"

GROUP_MEANING = {
    "Key suppliers": "Big, active suppliers with lots of invoices. Most of the balance sits here.",
    "Old balances to chase": "Mostly small balances unpaid for 6+ months. Could be paid, disputed or written off.",
    "Advances and retentions": "Mostly advances paid out or retention held on contracts, not normal invoices.",
    "Small and up to date": "Small suppliers with a few recent invoices.",
}


def build_data():
    df = load_data()
    as_of = get_as_of(df)
    df = add_aging(df, as_of)

    total = df["owed_sar"].sum()
    by_bucket = df.groupby("aging_bucket").agg(owed=("owed_sar", "sum"),
                                               invoices=("owed_sar", "size")).reindex(BUCKETS)

    pivot = (df.pivot_table(index="supplier_name", columns="aging_bucket",
                            values="owed_sar", aggfunc="sum", fill_value=0)
               .reindex(columns=BUCKETS, fill_value=0))
    pivot["total"] = pivot.sum(axis=1)
    pivot = pivot.sort_values("total", ascending=False)
    top = pivot.head(10)

    clusters = pd.read_csv("outputs/supplier_clusters.csv")
    flags = pd.read_csv("outputs/audit_flags.csv", parse_dates=["document_date"])

    groups = (clusters.groupby("group")
              .agg(suppliers=("supplier_id", "size"), owed=("owed_sar", "sum"),
                   avg_age=("avg_age_days", "mean"), share_over_180=("share_over_180", "mean"),
                   share_adv_ret=("share_adv_ret", "mean"))
              .sort_values("owed", ascending=False).reset_index())
    groups["meaning"] = groups["group"].map(GROUP_MEANING).fillna("")

    flag_counts = (flags.groupby(["check", "reason"]).size().rename("rows")
                   .reset_index().sort_values("rows", ascending=False))

    return {
        "as_of": f"{as_of:%d %b %Y}",
        "kpis": {
            "total_owed": total,
            "invoices": len(df),
            "over_180": by_bucket.loc["Above 180 Days", "owed"],
            "share_over_180": by_bucket.loc["Above 180 Days", "owed"] / total,
            "top1_share": pivot["total"].iloc[0] / total,
            "top10_share": top["total"].sum() / total,
            "flag_rows": len(flags),
            "flag_checks": flags["check"].nunique(),
        },
        "bucket_names": BUCKETS,
        "buckets": [{"bucket": b, "owed": r.owed, "invoices": int(r.invoices), "share": r.owed / total}
                    for b, r in by_bucket.iterrows()],
        "top": [{"name": name, "total": r["total"], "parts": [r[b] for b in BUCKETS]}
                for name, r in top.iterrows()],
        "groups": groups.to_dict("records"),
        "suppliers": [{"name": r.supplier_name, "size": r.total_size_sar, "age": r.avg_age_days,
                       "invoices": int(r.invoices), "group": r.group}
                      for r in clusters.itertuples()],
        "flag_counts": flag_counts.to_dict("records"),
        "flags": [{"check": r.check, "supplier": r.supplier_name, "je": str(r.journal_entry),
                   "date": f"{r.document_date:%d %b %Y}", "owed": r.owed_sar, "bucket": r.aging_bucket}
                  for r in flags.itertuples()],
    }


def build_page():
    """The page content with the data filled in."""
    data = json.dumps(build_data(), default=float).replace("</", "<\\/")
    with open(TEMPLATE, encoding="utf-8") as f:
        return f.read().replace("/*DATA*/", data)


if __name__ == "__main__":
    page = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '<style>body{margin:0}[hidden]{display:none!important}</style>\n</head>\n<body>\n'
            + build_page() + "\n</body>\n</html>\n")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(page)
    print("Saved", OUTPUT_FILE)
