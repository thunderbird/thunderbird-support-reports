#!/usr/bin/env python3
"""Fetch Play Store review CSVs from GCS into data/input/.

Usage:
    uv run scripts/fetch_reviews.py may 2026
    uv run scripts/fetch_reviews.py may 2026 --dry-run
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(description="Fetch Play Store review CSVs from GCS.")
    parser.add_argument("month", help="Month name (e.g. may)")
    parser.add_argument("year", help="Four-digit year (e.g. 2026)")
    parser.add_argument("--dry-run", action="store_true", help="Print commands without running them")
    args = parser.parse_args()

    if not BUCKET:
        sys.exit(
            "PLAY_REVIEWS_BUCKET is not set. Export the Play Console review bucket first:\n"
            '  export PLAY_REVIEWS_BUCKET="gs://pubsite_prod_XXXXXXXXXXXXXXXXX/reviews"'
        )

    month_num = MONTH_NAMES.get(args.month.lower())
    if not month_num:
        sys.exit(f"Unknown month: {args.month}")

    yyyymm = f"{args.year}{month_num}"
    dest_dir = Path(__file__).parent.parent / "data" / "input"
    dest_dir.mkdir(parents=True, exist_ok=True)

    fetched, skipped, missing = [], [], []

    for app in APPS:
        filename = f"reviews_{app}_{yyyymm}.csv"
        src = f"{BUCKET}/{filename}"
        dst = dest_dir / filename

        if dst.exists():
            print(f"  skip  {filename} (already exists)")
            skipped.append(filename)
            continue

        cmd = ["gsutil", "cp", src, str(dst)]
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
                print(f"  ERROR fetching {filename}:", result.stderr.strip(), file=sys.stderr)
                sys.exit(1)

    if not args.dry_run:
        print()
        if fetched:
            print(f"Fetched: {', '.join(fetched)}")
        if skipped:
            print(f"Skipped (already present): {', '.join(skipped)}")
        if missing:
            print(f"Not found (optional): {', '.join(missing)}")


if __name__ == "__main__":
    main()
