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

## Step 2 — Ensure current and previous Play Store CSVs are in place

Run `uv run scripts/fetch_reviews.py $month $year`. It fetches both the report month and
the preceding calendar month into `data/input/`; required stable and K-9 failures are fatal.
This must run even when the preceding month's report was skipped, because improved /
unchanged / decreased ratings are paired by Review Link against that preceding export.

Required files for **both months**:
- `reviews_net.thunderbird.android_YYYYMM.csv`
- `reviews_com.fsck.k9_YYYYMM.csv`
- Optional beta: `reviews_net.thunderbird.android.beta_YYYYMM.csv`

CSVs are UTF-16 encoded. Use all rows — no date filtering. The export is scoped by last activity date, not submit date.
`generate.py` performs the same check and automatically runs the fetcher if a required file
is missing. A fetch failure must stop generation; do not publish rating changes as unavailable.

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

Before generation, put qualitative copy in `data/$month_$year.yaml`. The newsletter
generator refuses to publish a future month when required narrative fields are absent:

```yaml
methodology_notes:
  - "Source or comparison caveat."
zendesk:
  tbpro_csat_note: null  # or a short low-sample / product-policy note
narrative:
  dashboard_headline: "Short, specific newsletter headline."
  lede: "Two or three sentences for the report and newsletter."
  masthead_highlights:
    - "One scannable monthly signal."
  esr_framing:
    headline: "How donor demand and desktop release signals relate."
    donor_context: "Explain donor-brand volume without calling it ESR-topic volume."
    bullets: ["ESR summary signal."]
    scope_notes: ["What these numbers do and do not measure."]
  overlap_notes:
    intro: "How to compare the three Thunderbird for Android channels."
    rows:
      - signal: "Signal name"
        play_store: "review count/read"
        sumo_android: "question count/read"
        k9_forum: "topic count/read"
        read: "Interpretation; never sum channel counts."
    footnote: "Sample-size or source caveat."
  github_alignment:
    headline: "Feedback vs this month's GitHub work"
    assessment: "Overall alignment read."
    bullets: ["Specific gap or aligned work."]
  roland_desktop: "Desktop SUMO narrative from Roland's current reports."
  roland_android: "Android SUMO narrative, including low-volume caveats."
  receive_resolve_resound: |
    Monthly RRR copy.
```

```
uv run scripts/generate.py $month $year
```

This emits the approved August-style newsletter and auto-populates:
- Friction point quotes, devices, languages (from CSVs)
- K-9 Discourse forum data (fetched live)
- 3-month trends for friction points and SUMO metrics
- Android · TfA grouping, ESR, overlap, and GitHub work-vs-feedback sections
- Persistent month-scoped accordions and hash-aware filters
- History updated in `data/history.json`

For a side-effect-free HTML template test, including against frozen August:
```
uv run scripts/generate.py $month $year --preview-html /tmp/$month.html
```
Preview mode writes only the named path; it does not write reports, redirects, history,
`index.md`, or Notion. Normal August generation is blocked because its send copy is frozen.

---

## Step 5 — Review qualitative output

Review the generated HTML and Markdown against the YAML. Fix qualitative copy in YAML and
regenerate; do not hand-tune generated HTML. Check the K-9 Discourse and Play Store analysis
for signals worth calling out in the lede, overlap notes, or K-9 churn watch.

---

## Step 6 — Verify dashboard

Open `reports/monthly/$year/$month.html` and check:
- All stat cards show values (no `—` where data should be)
- Thundermail note renders as small italic, not a heading
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
  data/$month_$year.yaml reports/monthly/$year/$month.md reports/monthly/$year/$month.html \
  reports/monthly/$year/$month.csv data/history.json index.md
git push
```

Verify live at: `https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/$year/$month.html`

---

## Key links
- MoM spreadsheet: internal "Support Metrics MoM" Google Sheet (access-controlled; link kept out of this public repo)
- FeatureOS board: https://ideas.tb.pro
- Roland's reports: https://thunderbird.github.io/thunderbird-metrics-and-reports/
- K-9 Forum: https://forum.k9mail.app/c/support/5
- Published reports: https://thunderbird.github.io/thunderbird-support-reports/
