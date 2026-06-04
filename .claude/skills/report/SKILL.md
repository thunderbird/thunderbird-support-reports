---
name: report
description: Build the monthly Thunderbird support report. Usage: /report <month> <year> (e.g. /report may 2026)
arguments: [month, year]
---

# Monthly Support Report — $month $year

Run the full report cycle for **$month $year**. Follow every step in order.

---

## Step 1 — Re-fetch all live data sources

Do NOT use YAML values from a prior session. Always fetch fresh.

**FeatureOS ideas** (board 17437):
```
featureos-cli posts list --query "sort=votes_count&order=desc&per_page=25&status=all" --json
```
Update both `new_this_month` and `top_alltime` in `data/$month_$year.yaml`.
- `new_this_month`: cross-reference with Lisa's FeatureOS board filtered by creation date for this month
- `top_alltime`: top 5 by votes_count from CLI output
- JSON key is `feature_requests`, not `posts`
- Ideas can be removed from the board between sessions — verify all entries still exist

**SUMO data** (Roland's reports):
- Desktop: `https://thunderbird.github.io/thunderbird-metrics-and-reports/html_reports/desktop/$year-$month_num-sumo-desktop-report.html`
- Android: `https://thunderbird.github.io/thunderbird-metrics-and-reports/html_reports/android/$year-$month_num-sumo-android-report.html`
- Fetch both pages and update `sumo:` section in the YAML

---

## Step 2 — Confirm Play Store CSVs are in place

Required files in project root or `data/input/`:
- `reviews_reviews_net.thunderbird.android_$year$month_num.csv`
- `reviews_reviews_com.fsck.k9_$year$month_num.csv`
- Optional beta: `reviews_reviews_net.thunderbird.android.beta_$year$month_num.csv`

CSVs are UTF-16 encoded. Use all rows — no date filtering. The export is scoped by last activity date, not submit date.

If a file has a `(1)` suffix (macOS duplicate), update `csv_tb_stable` in the YAML.

---

## Step 3 — Confirm Zendesk metrics are in the YAML

These come from Lisa's MoM spreadsheet. If `overall_csat` is `null`, ask Lisa before proceeding.

Check for:
- `zendesk.overall_csat`, `donor_csat`, `tbpro_csat`
- `zendesk.total_tickets`, `donor_tickets`, `tbpro_tickets`
- `zendesk.replies_to_low_star` (Zendesk is authoritative — covers all 3 apps)
- `zendesk.tbpro_csat_note` if TB Pro sample is low

---

## Step 4 — Run the generator

```
uv run scripts/generate.py $month $year
```

This auto-populates:
- Friction point quotes, devices, languages (from CSVs)
- K-9 Discourse forum data (fetched live)
- 3-month trends for friction points and SUMO metrics
- History updated in `data/history.json`

---

## Step 5 — Fill in remaining narrative sections

These cannot be auto-populated — fill in `lisa/$year/$month.md`:

1. **Lede** — 2-3 sentences. What's the headline story? CSAT trend, volume surge, K-9 signal, etc.
2. **Community Support key signals** — `[Key signal from Roland's data]` and `[Key signal]` placeholders
3. **Meeting 4★+ Goal bullets** — 3 priorities with stats, trends, and why they matter
4. **Receive / Resolve / Resound** — what came in, what worked, what to celebrate
5. **Experiments & Iterations** — Lisa fills in manually

Check the K-9 Discourse data and Play Store K-9 analysis for signals worth calling out in the lede or K-9 Churn Watch section.

---

## Step 6 — Verify dashboard

Open `lisa/$year/$month.html` and check:
- All stat cards show values (no `—` where data should be)
- TB Pro note renders as small italic, not a heading
- Quarter label on rating trend is correct (Q1=Jan-Mar, Q2=Apr-Jun, etc.)
- K-9 Forum tab shows topics, resolved %, unanswered %, top themes with 3-month trends and NEW ↑ badges, top contributors
- Theme count that more than doubles vs. the start of the 3-month window renders in red
- SUMO tables show MoM deltas and 3-month trends

---

## Step 7 — Commit and push

Stage only report files — never the raw CSV exports:
```
GIT_COMMITTER_EMAIL="lisajill@users.noreply.github.com" GIT_COMMITTER_NAME="Moment" \
  git commit --author="Moment <lisajill@users.noreply.github.com>" \
  -m "Add $month $year support report" \
  data/$month_$year.yaml lisa/$year/$month.md lisa/$year/$month.html \
  lisa/$year/$month.csv data/history.json index.md
git push
```

Verify live at: `https://thunderbird.github.io/thunderbird-support-reports/lisa/$year/$month.html`

---

## Key links
- MoM spreadsheet: internal "Support Metrics MoM" Google Sheet (access-controlled; link kept out of this public repo)
- FeatureOS board: https://ideas.tb.pro
- Roland's reports: https://thunderbird.github.io/thunderbird-metrics-and-reports/
- K-9 Forum: https://forum.k9mail.app/c/support/5
- Published reports: https://thunderbird.github.io/thunderbird-support-reports/
