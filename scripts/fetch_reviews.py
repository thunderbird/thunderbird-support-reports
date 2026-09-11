#!/usr/bin/env python3
"""Fetch Play Store review CSVs from GCS into data/input/.

Play Console auto-exports monthly review CSVs to a GCS bucket. This pulls them directly —
no more manual downloads from the Play Console web UI.

Usage:
    uv run scripts/fetch_reviews.py                 # prior month (the usual case)
    uv run scripts/fetch_reviews.py march 2026      # month + preceding month
    uv run scripts/fetch_reviews.py --dry-run

Prereqs (one-time):
    gcloud auth login                               # refresh credentials if expired
    export PLAY_REVIEWS_BUCKET="gs://pubsite_prod_XXXXXXXXXXXXXXXXX/reviews"
"""

import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

# The Play Console review-export bucket name embeds our developer account ID, so
# keep it out of this public repo. Set it once in your shell, e.g.:
#   export PLAY_REVIEWS_BUCKET="gs://pubsite_prod_XXXXXXXXXXXXXXXXX/reviews"
BUCKET = os.environ.get("PLAY_REVIEWS_BUCKET")

APPS = [
    "net.thunderbird.android",
    "com.fsck.k9",
    "net.thunderbird.android.beta",
]

MONTH_NAMES = {
    "january": "01", "february": "02", "march": "03", "april": "04",
    "may": "05", "june": "06", "july": "07", "august": "08",
    "september": "09", "october": "10", "november": "11", "december": "12",
}
NUM_TO_NAME = {v: k for k, v in MONTH_NAMES.items()}

# METHODOLOGY CHANGE (2026-07): review data is now pulled directly from the Play Console
# GCS export bucket instead of downloaded by hand from the Play Console UI. The GCS export
# is Google's canonical monthly file (all rows, scoped by last-activity date — see CLAUDE.md).
# Counts can differ slightly from months fetched manually because the UI export and the bucket
# export scope/encode independently. Surface this note as a FOOTNOTE in any report whose
# month-over-month comparison spans the change, so discrepancies read as methodology, not signal.
METHODOLOGY_NOTE = (
    "Play Store review data is pulled directly from the Play Console GCS export bucket as of "
    "July 2026 (previously downloaded manually from the Play Console UI). Small differences in "
    "review counts versus earlier months may reflect this source change rather than real "
    "movement; cross-method month-over-month comparisons carry a methodology caveat."
)


def prior_month():
    """Return (month_name, year_str) for the calendar month before today."""
    first_of_this_month = dt.date.today().replace(day=1)
    last_of_prior = first_of_this_month - dt.timedelta(days=1)
    return NUM_TO_NAME[f"{last_of_prior.month:02d}"], str(last_of_prior.year)


def preceding_month(month_num, year):
    """Return (month_name, year_str) immediately before a report month."""
    first = dt.date(int(year), int(month_num), 1)
    previous = first - dt.timedelta(days=1)
    return NUM_TO_NAME[f"{previous.month:02d}"], str(previous.year)


def copy_cmd(src, dst):
    """Prefer modern `gcloud storage cp`; fall back to legacy `gsutil cp`."""
    if _has("gcloud"):
        return ["gcloud", "storage", "cp", src, dst]
    return ["gsutil", "cp", src, dst]


def _has(binary):
    from shutil import which
    return which(binary) is not None


def _auth_hint(stderr):
    """Return a friendly hint if the failure looks like an auth/token problem."""
    low = stderr.lower()
    if "reauth" in low or "auth" in low or "credential" in low or "login" in low:
        return ("\n  → Looks like a gcloud auth problem. Refresh credentials with:\n"
                "      gcloud auth login\n"
                "    (in Claude Code, type:  ! gcloud auth login )")
    return ""


def main():
    parser = argparse.ArgumentParser(description="Fetch Play Store review CSVs from GCS.")
    parser.add_argument("month", nargs="?", help="Month name (e.g. march). Default: prior month.")
    parser.add_argument("year", nargs="?", help="Four-digit year (e.g. 2026). Default: prior month's year.")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    args = parser.parse_args()

    # Default to the prior calendar month (Play Console exports are complete once the
    # month has closed, so the usual run in month N pulls month N-1).
    if args.month is None:
        month, year = prior_month()
        print(f"No month given — defaulting to prior month: {month} {year}")
    else:
        month, year = args.month, args.year
        if not year:
            sys.exit("Provide both month and year, or neither (to default to the prior month).")

    month_num = MONTH_NAMES.get(month.lower())
    if not month_num:
        sys.exit(f"Unknown month: {month}")

    dest_dir = Path(__file__).parent.parent / "data" / "input"
    dest_dir.mkdir(parents=True, exist_ok=True)

    fetched, skipped, missing = [], [], []
    prev_month, prev_year = preceding_month(month_num, year)
    periods = [(prev_month, prev_year), (month.lower(), str(year))]

    required_missing = [
        f"reviews_{app}_{period_year}{MONTH_NAMES[period_month]}.csv"
        for period_month, period_year in periods
        for app in APPS[:2]
        if not (dest_dir / f"reviews_{app}_{period_year}{MONTH_NAMES[period_month]}.csv").exists()
    ]
    if required_missing and not BUCKET:
        sys.exit(
            "Required Play Store CSVs are missing and PLAY_REVIEWS_BUCKET is not set:\n"
            + "\n".join(f"  {name}" for name in required_missing)
            + '\nExport PLAY_REVIEWS_BUCKET="gs://pubsite_prod_XXXXXXXXXXXXXXXXX/reviews"'
        )

    for period_month, period_year in periods:
        yyyymm = f"{period_year}{MONTH_NAMES[period_month]}"
        print(f"{period_month.title()} {period_year}:")
        for app in APPS:
            filename = f"reviews_{app}_{yyyymm}.csv"
            src = f"{BUCKET}/{filename}" if BUCKET else None
            dst = dest_dir / filename

            if dst.exists():
                print(f"  skip  {filename} (already exists)")
                skipped.append(filename)
                continue

            if not BUCKET and "beta" in app:
                print(f"  skip  {filename} (beta is optional; bucket not configured)")
                missing.append(filename)
                continue

            cmd = copy_cmd(src, str(dst))
            print(f"  fetch {filename}")
            if args.dry_run:
                print(f"    would run: {' '.join(cmd)}")
                continue

            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                fetched.append(filename)
            else:
                # Beta is optional — warn but don't fail
                if "beta" in app:
                    print(f"  warn  {filename} not found (beta is optional)")
                    missing.append(filename)
                else:
                    print(f"  ERROR fetching required {filename}: {result.stderr.strip()}"
                          f"{_auth_hint(result.stderr)}", file=sys.stderr)
                    sys.exit(1)

    if not args.dry_run:
        print()
        if fetched:
            print(f"Fetched: {', '.join(fetched)}")
        if skipped:
            print(f"Skipped (already present): {', '.join(skipped)}")
        if missing:
            print(f"Not found (optional): {', '.join(missing)}")
        if not fetched and not skipped:
            print("Nothing fetched. Check the bucket name and that the export for this month exists.")
        if BUCKET:
            print(f"\nSource: {BUCKET}  (direct GCS pull — no manual download)")
        print(f"FOOTNOTE: {METHODOLOGY_NOTE}")


if __name__ == "__main__":
    main()
