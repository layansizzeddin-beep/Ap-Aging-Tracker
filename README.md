# AP Aging Tracker

During my accounting internship one of my daily jobs was making the accounts payable aging summary: taking a raw SAP export of ~7,500 open supplier invoice lines and working out in Excel how much we owe each supplier and how long it's been unpaid.

This project does that in Python instead, and then uses the same data for a few things the Excel version couldn't do: flagging suspicious invoices, grouping suppliers with k-means, and an interactive dashboard.

The data in this repo is anonymised (see bottom).

## What I found

![aging](charts/aging_by_bucket.png)

About 60% of the balance is more than 180 days old.

![top suppliers](charts/top_suppliers.png)

The debt is really concentrated: one supplier is around 80% of the total and the top 10 are over 90%.

![clusters](charts/supplier_groups.png)

k-means split the suppliers into 4 groups. The useful one is "old balances to chase", around 70 suppliers with small balances that have been sitting there for 6+ months.

![audit flags](charts/audit_flags.png)

The audit checks flagged 851 lines. Not all of them are mistakes, but things like possible duplicates and reversals that were never cleared are worth looking at.

## How it works

**Cleaning** (`clean_ap_data.py`): the export had empty columns, amounts stored as text like `- 159,404.44 SAR`, a few dates with the year typed as 2206, and one wrong company code. This fixes all that and also makes the anonymised copy.

**Aging summary** (`build_aging_summary.py`): age is counted from the document date to the last month end, using the same buckets my team uses (0-30, 31-60, 61-180, 180+). To check I had the logic right, I compared my buckets with the Aging column already in the file. It didn't match at first, so the script tries every date in the past year to see when that column was last calculated. One date (30 June) matched 100% of rows, so the method is the same and the old column was just out of date.

**Audit checks** (`audit_checks.py`):
- possible duplicates: same supplier + same amount within 7 days
- uncleared reversals: an entry and its exact opposite both still open
- due date before the invoice date
- payment terms over a year
- invoice dated after the report date
- unusually large amounts for that supplier (robust z-score using median/MAD on log amounts, so one huge invoice doesn't hide itself)

**Clustering** (`cluster_suppliers.py`): each supplier gets 5 features (balance size, number of invoices, average age weighted by amount, % over 180 days, % advances/retentions). These get standardised and put through k-means with k=4. k=2 had a slightly higher silhouette score but 4 groups were much more useful to actually act on.

**Charts + dashboard** (`make_charts.py`, `make_dashboard.py`): the charts above, plus `dashboard.html` which you can open in a browser to hover over the charts, switch between supplier groups and filter the audit flags.

## Running it

```
pip install -r requirements.txt
python run_all.py
```

Settings (which file, report date, etc.) are at the top of `ap_utils.py`. `clean_ap_data.py` isn't in `run_all.py` because it needs the original export, which isn't public.

## Data / privacy

The real file stays private. In `ap_anonymised.csv` supplier names, IDs, company codes, profit centers, users and journal entries are replaced with fake labels, all amounts are multiplied by one hidden factor and all dates are shifted by the same hidden number of days. Free text and invoice numbers are removed. Percentages and patterns are the same as the real data.

## What I'd do next

- get the paid (cleared) invoices too, so I can predict how long an invoice takes to get paid
- measure concentration properly with the HHI
- look at foreign currency exposure (some invoices are in USD, EUR, GBP, QAR etc.)
