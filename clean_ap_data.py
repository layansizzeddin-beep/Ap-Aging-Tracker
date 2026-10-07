# cleans the raw SAP export -> ap_clean.csv (private) and ap_anonymised.csv (for github)

import numpy as np
import pandas as pd

RAW_FILE = "python raw data.csv"

# load the file (cp1252 is the encoding Excel used when saving)
df = pd.read_csv(RAW_FILE, encoding="cp1252", dtype=str)
print("Rows loaded:", len(df))

# drop columns that are completely empty (the Unnamed ones, clearing entry/date)
df = df.dropna(axis=1, how="all")

# tidy column names (fix spelling, no spaces or brackets)
df = df.rename(columns={
    "Company Code": "company_code",
    "Supplier": "supplier_id",
    "Supplier Name": "supplier_name",
    "Journal Entry": "journal_entry",
    "Invoice Reference": "invoice_reference",
    "Posting Date": "posting_date",
    "Journal Entry Date": "document_date",
    "Assignment": "assignment",
    "Profit Center": "profit_center",
    "Profit Center Txt": "profit_center_text",
    "Reference": "reference",
    "Amount (Tran Cur.)": "amount_original",
    "Amount (CoCode Crcy)": "amount_sar",
    "Item Text": "item_text",
    "Clearing Status": "clearing_status",
    "Net Due Date": "net_due_date",
    "created by": "created_by",
    "Special G/L Ind": "special_gl_ind",
    "Currancy Transaction": "currency",
    "Comment": "payment_type",       # RP / Non RP / Petty Cash
    "S": "item_category",            # Advance / Retention / Other ...
    "Comments": "review_flag",       # ok / Remove
    "Month": "month",
    "DATA": "take_data",
    "Aging": "aging_original",
})

# turn amount text into real numbers
# "- 159,404.44    SAR"  ->  -159404.44
def to_number(text):
    text = str(text).replace(",", "")
    text = "".join(ch for ch in text if ch.isdigit() or ch in ".-")
    return float(text)

for col in ["amount_original", "amount_sar"]:
    df[col] = df[col].apply(to_number)

# fix year typos (2206 / 2202 -> 2026) then convert to dates
date_cols = ["posting_date", "document_date", "net_due_date"]
for col in date_cols:
    df[col] = df[col].str.replace(r"/220[26]$", "/2026", regex=True)
    df[col] = pd.to_datetime(df[col], format="%m/%d/%Y")

df["month"] = pd.to_datetime(df["month"], format="%b-%Y").dt.to_period("M").astype(str)

# one row has company code "C001", profit center says it's 2190
df.loc[df["company_code"] == "C001", "company_code"] = "2190"

# small text clean-ups
df["take_data"] = df["take_data"].notna()                    # True / False
df["review_flag"] = df["review_flag"].str.strip().str.lower()  # "ok" / "remove"
df["payment_type"] = df["payment_type"].fillna("Unknown")
for col in df.columns:
    if pd.api.types.is_string_dtype(df[col]):
        df[col] = df[col].str.strip()

# clearing status is 2 (open) on every row so it tells us nothing
df = df.drop(columns=["clearing_status"])

# flag exact duplicates but keep them, SAP sometimes exports identical lines on purpose
df["possible_duplicate"] = df.duplicated(keep="first")

df = df.sort_values(["supplier_id", "posting_date"]).reset_index(drop=True)
df.to_csv("ap_clean.csv", index=False)
print("Saved ap_clean.csv (PRIVATE):", df.shape)

# anonymised copy for GitHub
rng = np.random.default_rng(42)
anon = df.copy()

def code_map(series, prefix, width=3):
    """Give every unique value a fake label like Supplier_001."""
    uniques = series.dropna().unique()
    shuffled = rng.permutation(uniques)
    return series.map({v: f"{prefix}_{i+1:0{width}d}" for i, v in enumerate(shuffled)})

anon["supplier_id"] = code_map(anon["supplier_id"], "SUP")
anon["supplier_name"] = anon["supplier_id"].str.replace("SUP_", "Supplier ")
anon["company_code"] = code_map(anon["company_code"], "CO", 1)
anon["profit_center"] = code_map(anon["profit_center"], "PC")
anon["created_by"] = code_map(anon["created_by"], "USER", 2)
anon["journal_entry"] = code_map(anon["journal_entry"], "JE", 5)

# drop free text + document numbers
anon = anon.drop(columns=["invoice_reference", "assignment", "reference",
                          "item_text", "profit_center_text"])

# scale all amounts by one hidden factor
scale = rng.uniform(0.55, 0.85)
anon["amount_original"] = (anon["amount_original"] * scale).round(2)
anon["amount_sar"] = (anon["amount_sar"] * scale).round(2)

# shift all dates by one hidden number of days
shift = pd.Timedelta(days=int(rng.integers(-60, -20)))
for col in date_cols:
    anon[col] = anon[col] + shift
anon["month"] = anon["posting_date"].dt.to_period("M").astype(str)

anon.to_csv("ap_anonymised.csv", index=False)
print("Saved ap_anonymised.csv (safe for GitHub):", anon.shape)
