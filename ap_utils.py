# shared settings + helpers so every script loads/ages the data the same way

import pandas as pd

# settings
INPUT_FILE = "ap_anonymised.csv"   # use "ap_clean.csv" for the real data (keep private)
AGE_FROM = "document_date"         # the date the team counts age from
AS_OF_DATE = None                  # e.g. "2026-09-30". None = last month end in the data
EXCLUDE_REMOVED = True             # leave out rows marked "remove"
DROP_DUPLICATES = False            # True = delete rows flagged as exact duplicates

BUCKETS = ["0-30 Days", "31-60 Days", "61-180 Days", "Above 180 Days"]
EDGES = [-10**6, 30, 60, 180, 10**6]   # bucket boundaries in days

DATE_COLS = ["posting_date", "document_date", "net_due_date"]


def load_data(path=INPUT_FILE):
    """Load the cleaned file and apply the settings above."""
    df = pd.read_csv(path, parse_dates=DATE_COLS)
    if EXCLUDE_REMOVED:
        df = df[df["review_flag"] != "remove"]
    if DROP_DUPLICATES:
        df = df[~df["possible_duplicate"]]
    # SAP shows money we owe as negative. Flip it so "owed" is positive.
    # (Negative "owed" = the supplier owes us, e.g. an advance we paid.)
    df["owed_sar"] = -df["amount_sar"]
    return df.reset_index(drop=True)


def get_as_of(df):
    """The report date: AS_OF_DATE, or the last month end before the newest posting."""
    if AS_OF_DATE is not None:
        return pd.Timestamp(AS_OF_DATE)
    newest = df["posting_date"].max()
    return newest.replace(day=1) - pd.Timedelta(days=1)


def add_aging(df, as_of):
    """Add days_old and aging_bucket columns."""
    df = df.copy()
    df["days_old"] = (as_of - df[AGE_FROM]).dt.days
    df["aging_bucket"] = pd.cut(df["days_old"], EDGES, labels=BUCKETS).astype(str)
    return df
