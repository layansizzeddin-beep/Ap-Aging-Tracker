# flags invoice lines worth checking -> outputs/audit_flags.csv

import os

import numpy as np
import pandas as pd

from ap_utils import load_data, get_as_of, add_aging

os.makedirs("outputs", exist_ok=True)
OUTPUT_FILE = "outputs/audit_flags.csv"

DUPLICATE_WINDOW_DAYS = 7
MIN_AMOUNT = 100            # ignore tiny amounts for the duplicate checks
UNUSUAL_SCORE = 3.5         # how far from normal counts as "unusual" (see check 6)

df = load_data()
as_of = get_as_of(df)
df = add_aging(df, as_of)
df["row_id"] = df.index
flags = []


def add_flags(rows, check, reason):
    """Store flagged rows with the name of the check and a short reason."""
    out = rows.copy()
    out["check"] = check
    out["reason"] = reason
    flags.append(out)


# compare every invoice with every other invoice
# from the same supplier with the same amount
cand = df[df["owed_sar"].abs() >= MIN_AMOUNT].copy()
cand["abs_amount"] = cand["owed_sar"].abs().round(2)

pairs = cand.merge(cand, on=["supplier_id", "abs_amount"], suffixes=("_a", "_b"))
pairs = pairs[pairs["row_id_a"] < pairs["row_id_b"]]          # each pair once
# same journal entry = one document split into lines, skip those
pairs = pairs[pairs["journal_entry_a"] != pairs["journal_entry_b"]]
days_apart = (pairs["document_date_a"] - pairs["document_date_b"]).dt.days.abs()
pairs = pairs[days_apart <= DUPLICATE_WINDOW_DAYS]

same_sign = np.sign(pairs["owed_sar_a"]) == np.sign(pairs["owed_sar_b"])
# retention/advance lines get split into equal parts on purpose so only check normal invoices
normal = (pairs["item_category_a"] == "Other") & (pairs["item_category_b"] == "Other")

dupes = pairs[same_sign & normal]
reversals = pairs[~same_sign]

for name, found, reason in [
    ("POSSIBLE_DUPLICATE", dupes,
     "Same supplier and amount within 7 days"),
    ("UNCLEARED_REVERSAL", reversals,
     "Cancels out another open entry; could be cleared"),
]:
    ids = pd.unique(found[["row_id_a", "row_id_b"]].values.ravel())
    rows = df[df["row_id"].isin(ids)].copy()
    # rows with the same supplier and amount get the same group number,
    # so they can be checked side by side
    key = rows["supplier_id"] + "|" + rows["owed_sar"].abs().round(2).astype(str)
    rows["match_group"] = key.factorize()[0] + 1
    add_flags(rows, name, reason)

# dates that don't make sense
terms = (df["net_due_date"] - df["document_date"]).dt.days
add_flags(df[terms < 0], "DUE_BEFORE_DOCUMENT", "Due date is before invoice date")
add_flags(df[terms > 365], "VERY_LONG_TERMS", "Due more than 1 year after invoice date")
add_flags(df[df["document_date"] > as_of], "FUTURE_DATED", "Invoice date is after report date")

# unusually large amounts for that supplier
# robust z-score on log amounts: uses median + MAD instead of mean + std
# so one huge invoice can't drag the "normal" level up and hide itself
amt = df["owed_sar"].abs()
log_amt = np.log10(amt.clip(lower=1))
grp = log_amt.groupby(df["supplier_id"])
median = grp.transform("median")
mad = grp.transform(lambda s: (s - s.median()).abs().median())   # typical gap
count = grp.transform("size")
score = 0.6745 * (log_amt - median) / mad.replace(0, np.nan)
unusual = (count >= 5) & (score > UNUSUAL_SCORE) & (amt >= 10_000)
rows = df[unusual].copy()
rows["unusual_score"] = score[unusual].round(1)
add_flags(rows, "UNUSUAL_AMOUNT", "Much larger than this supplier's usual invoices")

# save + print summary
cols = ["check", "reason", "match_group", "unusual_score", "supplier_id",
        "supplier_name", "journal_entry", "document_date", "net_due_date",
        "owed_sar", "currency", "item_category", "days_old", "aging_bucket"]
result = pd.concat(flags, ignore_index=True).reindex(columns=cols)
result.to_csv(OUTPUT_FILE, index=False)

overview = result.groupby("check").agg(flagged_rows=("owed_sar", "size"),
                                       owed_sar=("owed_sar", lambda s: s.abs().sum()))
print(f"Report date: {as_of.date()}")
print(overview.sort_values("flagged_rows", ascending=False)
      .to_string(formatters={"owed_sar": "{:,.0f}".format}))
print(f"\nSaved {OUTPUT_FILE}")
