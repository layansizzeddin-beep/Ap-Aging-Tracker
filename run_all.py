# runs everything in order (not clean_ap_data.py, that needs the private raw file)

import runpy

STEPS = [
    "build_aging_summary.py",
    "audit_checks.py",
    "cluster_suppliers.py",
    "make_charts.py",
    "make_dashboard.py",
]

for step in STEPS:
    print(f"\n===== {step} =====")
    runpy.run_path(step, run_name="__main__")

print("\nAll done. Open dashboard.html in your browser.")
