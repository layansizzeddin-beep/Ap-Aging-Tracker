# aging summary -> outputs/ap_aging_summary.xlsx (summary, by supplier, detail)

import os

import pandas as pd

from ap_utils import BUCKETS, AGE_FROM, load_data, get_as_of, add_aging

os.makedirs("outputs", exist_ok=True)
OUTPUT_FILE = "outputs/ap_aging_summary.xlsx"

# load the data and work out each invoice's age and bucket
df = load_data()
as_of = get_as_of(df)
df = add_aging(df, as_of)
print("Aging as of:", as_of.date())
print("Invoices included:", len(df))

# check the method against the team's original Aging column.
# That column was calculated on an older date, so try every day
# in the past year and see which one matches best.
has_bucket = df["aging_original"].isin(BUCKETS)
best_date, best_match = None, 0
for day in pd.date_range(as_of - pd.Timedelta(days=365), as_of):
    test = add_aging(df[has_bucket], day)
    match = (test["aging_bucket"] == test["aging_original"]).mean()
    if match > best_match:
        best_date, best_match = day, match
print(f"Check: original Aging column matches {best_match:.1%} "
      f"if aged as of {best_date.date()}")

# build the summary tables
summary = (df.groupby("aging_bucket")
             .agg(invoices=("owed_sar", "size"), owed_sar=("owed_sar", "sum"))
             .reindex(BUCKETS).fillna(0))
summary["share_of_total"] = summary["owed_sar"] / summary["owed_sar"].sum()
summary.loc["Total"] = [summary["invoices"].sum(), summary["owed_sar"].sum(), 1.0]

by_supplier = df.pivot_table(index=["supplier_id", "supplier_name"],
                             columns="aging_bucket", values="owed_sar",
                             aggfunc="sum", fill_value=0)
by_supplier = by_supplier.reindex(columns=BUCKETS, fill_value=0)
by_supplier["Total"] = by_supplier.sum(axis=1)
by_supplier = by_supplier.sort_values("Total", ascending=False)

detail_cols = ["supplier_id", "supplier_name", "company_code", AGE_FROM,
               "net_due_date", "currency", "amount_original", "owed_sar",
               "item_category", "payment_type", "days_old", "aging_bucket"]
detail = df[detail_cols].sort_values("days_old", ascending=False)

# save to Excel
with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as xl:
    summary.round(2).to_excel(xl, sheet_name="Summary")
    by_supplier.round(2).to_excel(xl, sheet_name="By Supplier")
    detail.to_excel(xl, sheet_name="Detail", index=False)

print(f"\nSaved {OUTPUT_FILE}\n")
print(summary.to_string(formatters={"invoices": "{:,.0f}".format,
                                    "owed_sar": "{:,.0f}".format,
                                    "share_of_total": "{:.0%}".format}))
