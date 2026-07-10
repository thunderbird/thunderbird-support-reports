# Claude Code Project — Thunderbird Support Reports
# Lisa Wess · lwess@thunderbird.net
# Repo: github.com/thunderbird/thunderbird-support-reports

## Who I am
I'm Lisa Wess, Support Operations Manager at MZLA (Thunderbird). Every month
I produce a support operations report that I email to my team and post to Notion.
This project automates that report.

## What this project does
Each month Claude fetches Play Store CSVs automatically and Lisa provides Zendesk metrics. Claude Code
analyzes them and produces:
1. A paste-ready report (markdown) I copy into Notion and email
2. An HTML dashboard with section filters, published to GitHub Pages
3. A CSV data export my manager uses for pivot tables

## Monthly workflow — how to run it

### What Lisa does
1. Provide Zendesk metrics (CSAT, ticket counts, donor topic breakdown) from the MoM spreadsheet

### What Claude does (Play Store CSVs)
Run `uv run scripts/fetch_reviews.py <month> <year>` — fetches all three apps from GCS into `data/input/` automatically.
GCS bucket: read from `$PLAY_REVIEWS_BUCKET` (kept out of this public repo — it embeds our developer account ID).
Requires gcloud CLI installed and authenticated (`gcloud auth login` with Lisa's Google account).
Beta is optional — script warns but does not fail if missing.
**Run this in the following month** (e.g. fetch May's CSVs in June) — Play Console exports are only complete once the month has closed.

### What Claude does
1. **Re-fetch all live data sources** before touching the YAML — do not rely on values from a prior session, which may be days or weeks stale:
   - FeatureOS: run `featureos-cli posts list --query "sort=votes_count&order=desc&per_page=25&status=all" --json` and update both `new_this_month` and `top_alltime`
   - SUMO: pull Roland's latest report via `gh api`
2. Fill in `data/<month>_<year>.yaml` — Zendesk data, SUMO data (from Roland's repo), FeatureOS ideas
3. Run `uv run scripts/generate.py <month> <year>` (e.g. `uv run scripts/generate.py april 2026`)
   — friction point quotes, devices, and languages are auto-populated from the CSVs
4. Draft the narrative lede and qualitative sections (K-9 churn watch, goals, Receive/Resolve/Resound)
5. Lisa reviews, edits, approves
6. Optionally run `uv run scripts/deep_analysis.py` for fuller per-review detail if a theme warrants deeper investigation
7. Commit and push to GitHub

### Local review links — always include full `file://` paths

When pointing Lisa to a report, sample, drill-down, or publish-readiness review, **proactively include full `file://` URLs** (not relative paths alone). Lisa opens these locally in the browser.

Templates (replace `YYYY` / `month` as needed):

- Monthly sample: `file:///Users/lwess/Documents/Thunderbird-Support-Reports/lisa/YYYY/month_sample.html`
- Launch overview sample: `file:///Users/lwess/Documents/Thunderbird-Support-Reports/lisa/daily/launch_overview_sample.html`
- Drill-downs: `file:///Users/lwess/Documents/Thunderbird-Support-Reports/lisa/YYYY/month_*.html` (e.g. `june_sumo_trending.html`, `june_push_deep_dive_sample.html`)
- After publish: GitHub Pages — `https://thunderbird.github.io/thunderbird-support-reports/lisa/YYYY/month.html`

Apply whenever the topic is monthly report review, publish readiness, "open locally", or Lisa asks for full links — do not wait for her to repeat the request.

### Creating the next month's YAML
Copy the previous month's YAML, update `month`, `year`, `month_num`, `prev_month`,
CSV filenames, and move all `zendesk` values into `prev`. Leave `zendesk` fields as `null`.
Update `history_neg` by appending last month's negative mention counts.

### Planned — monthly report redesign *(direction chosen — sample gate still active)*

**Lisa chose restrained (Jun 2026):** Inter-only operational dashboard layout — easier to scan than the editorial/magazine serif variant. Working prototype: `lisa/2026/june_sample_restrained.html`. When Fable starts, consolidate that file → `lisa/2026/june_sample.html` (single sample-gate file; review deadline **June 23** per `DESIGN.md`). Editorial compare files (`june_compare_editorial.html`, etc.) are **reference only**.

Same playbook as the launch overview sample (`lisa/daily/launch_overview_sample.html`):
- **Bolt tokens**, dark mode, accessible hierarchy
- **Paraphrase / redact PII** in all customer-facing quotes and ticket text
- **Scannable copy** — no essay blocks in masthead/lede; use `.masthead__highlights` + `.scan-list` (see `.cursor/rules/tbpro-copy-tone.mdc` → *Scannable copy*)
- **Reimagined layout from scratch** — not an incremental patch on `generate.py` output

**Sample gate:** edit **only** the `*_sample.html` file until Lisa approves. Do **not** modify `scripts/generate.py` or live output (`lisa/YYYY/month.html`, e.g. `june.html`) until then.

**Never modify archived monthly reports.** Prior months in `lisa/YYYY/` are frozen once published — read-only references for voice, layout, and drill-down patterns. Do not edit:
- Published dashboards: `march.html`, `april.html`, `may.html`, … (any month before the current reporting cycle)
- Frozen deep dives and working docs: `march_push_deep_dive.html`, `march_push_followup.html`, `march_push_kb_recommendations.html`, `march_support_ops_index.html`, prior-month `*_sumo_trending.html`, etc.
- Matching `.md`, `.csv`, and analysis JSON for those months

When the current sample needs a drill-down link, create or link to **current-month** artifacts (`june_push_deep_dive.html`, `june_sumo_trending.html`, …) — never patch archived HTML to fix a broken link from the sample. See `DESIGN.md` scope.

**Pattern references:** `launch_overview_sample.html` + the five TB Pro Cursor rules (`tbpro-launch-sample.mdc`, `tbpro-theme-tickets.mdc`, `tbpro-table-patterns.mdc`, `tbpro-copy-tone.mdc`, `tbpro-sonnet-maintenance.mdc`). Adapt for monthly dashboard sections: Donor Care, TB Pro, Android Reviews, Desktop/Android SUMO forums, K-9 Forum (see Dashboard structure below).

**When Fable starts:** read `tbpro-sonnet-maintenance.mdc` principles (section comments, no `display:flex` on `th`, etc.) and create `.cursor/rules/monthly-report-sample.mdc` for ongoing maintenance.

## Privacy — PII policy
When showing any customer content, **never store PII in any repo file — committed or local.** This includes: email addresses, last names, domain names, aliases, IP addresses, phone numbers, Play Console developer account IDs, or any other personally identifiable information. This applies to all data sources: Zendesk tickets (subjects, excerpts, comments), Play Store reviews, FeatureOS, SUMO.

**All generators redact before write.** Import `scripts/pii_redact.py` (`redact`, `redact_sumo_title`, `paraphrase_review`) — never write raw customer text to `lisa/`, `data/`, or any tracked path. TB Pro daily/weekly scripts still accept `--public` for CI; local runs must also produce redacted output when writing into this repo.

When in doubt, redact.

### Git commit pattern (always use this — privacy requirement)
```
GIT_COMMITTER_EMAIL="lisajill@users.noreply.github.com" GIT_COMMITTER_NAME="Moment" \
  git commit --author="Moment <lisajill@users.noreply.github.com>" -m "message"
```

## Data sources

### Play Store CSVs
Fetched automatically via `uv run scripts/fetch_reviews.py <month> <year>`.
GCS bucket: read from `$PLAY_REVIEWS_BUCKET` (see fetch step above).
Two apps (required) + one optional:
- Thunderbird Android: `reviews_net.thunderbird.android_YYYYMM.csv`
- K-9 Mail: `reviews_com.fsck.k9_YYYYMM.csv`
- TB Beta (optional): `reviews_net.thunderbird.android.beta_YYYYMM.csv`
  *(note: `.beta` with a dot, not `_beta` with underscore)*

Files are UTF-16 encoded. **Do not filter by date — use all rows.**
Play Console monthly exports are scoped by **last activity date** (user update or developer
reply), not by original submit date. A review submitted in 2011 that received a reply in
April 2026 will appear in the April export. All rows in the file are legitimately part of
that month's dataset. Filtering on `Review Submit Date and Time` drops valid rows.
K-9 was added to the dataset in March 2026.
Beta is merged into TB counts when its CSV is present.

**GCS vs manual export (from June 2026):** June 2026 is the first month using the GCS bucket fetch; Jan–May used manual Play Console UI downloads. Review counts and monthly averages may differ when MoM comparisons span that boundary — always surface the methodology caveat in the report/dashboard (mobile manager approved the shift, July 2026).

**Engagement count (incoming Play Store review tickets):** The number of Play Store review
tickets received in Zendesk that month (all star ratings, all three apps). Source: the
"Thunderbird App Store Reviews" brand ticket count from Zendesk. Set
`zendesk.replies_to_low_star` in the YAML (field name is legacy; value is the ticket count).

### MoM spreadsheet
Lisa provides metrics from the internal "Support Metrics MoM" Google Sheet (access-controlled; link kept out of this public repo).
Contains: Zendesk CSAT/volume, SUMO solved rates, trusted contributor %

### SUMO data (Roland's repo)
Roland does SUMO analysis at github.com/thunderbird/thunderbird-metrics-and-reports.
Pull via GitHub API — no local clone needed:
```
gh api repos/thunderbird/thunderbird-metrics-and-reports/contents/REPORTS/<filename>
```

### Thundermail Ideas (FeatureOS)
Board ID: 17437 on FeatureOS. Pull via featureos-cli (credentials in ~/.featureos.yaml).
Need: new ideas this month + top 5 all-time by votes.
Idea URLs follow the pattern: https://ideas.tb.pro/p/{slug}

**Always re-fetch at the start of each session** — never carry over vote counts or idea lists
from a prior session. Ideas get removed, vote counts change, and the board evolves between
reporting cycles. Stale data from even a few days ago can be wrong.

**Important:** default posts list only returns "Incoming" status and misses high-vote ideas.
Always use `status=all` to get the full list:
```
featureos-cli posts list --query "sort=votes_count&order=desc&per_page=100&status=all" --json
```
Tags come from the `tags` array on each post. Use the first tag as the category label.

**New this month:** filter by `created_at` falling within the report month. The featureos-cli
does not support date filtering — cross-reference with the FeatureOS board UI filtered by
creation date (as Lisa does), or ask Lisa to confirm the list.

**Parsing the CLI response:** the JSON key is `feature_requests`, not `posts` or `data`.

**Status snapshots (automated):** Each `generate.py` run fetches all ideas and stores a
monthly snapshot in `data/history.json` under `featureos_status`:

```json
"featureos_status": {
  "2026-06": {
    "captured_at": "2026-07-01T…Z",
    "ideas": [
      {"slug": "…", "title": "…", "votes": N, "status": "In flight", "updated_at": "…"}
    ]
  }
}
```

On the next month's run, `generate.py` diffs the live fetch against the prior month's snapshot
(by slug) and auto-populates **Status moves** in the Thundermail dashboard section. The first
month with a snapshot (e.g. June 2026) has no prior baseline — keep manual `status_moves` in
YAML until July.

**Manual status moves:** FeatureOS has no status-change audit log. For quarterly product review
or other moves not captured by snapshot diff, append entries under optional `status_moves_manual`
in the month YAML (same shape as `status_moves.moves`). Auto-detected and manual entries merge
on generate.

Standalone backfill: `uv run scripts/featureos_snapshot.py 2026-06`

**Vote MoM deltas** (separate from status): per-month `tbpro_ideas` title→votes map still lives
under each month key in `history.json` (written by `append_to_history`).

## Scripts

### `scripts/generate.py <month> <year>` — MAIN ENTRY POINT
Reads `data/<month>_<year>.yaml`, analyzes Play Store CSVs, generates:
- `lisa/<year>/<month>_analysis.json`
- `lisa/<year>/<month>.md` (report draft)
- `lisa/<year>/<month>.html` (dashboard)
- `lisa/<year>/<month>.csv` (data export)
- Updates `index.md`

Friction point detail (representative quote, top devices, top languages) is
**auto-populated from the CSVs** on every run — no manual step needed. The quote
is scored by keyword density against the theme pattern so it stays on-topic.

### `scripts/deep_analysis.py`
**Supplemental only** — no longer a required step. generate.py auto-populates
the friction point quote, devices, and languages in the report. Use deep_analysis.py
when you need fuller detail: multiple quotes per theme, K-9-specific review text,
raw per-review breakdown for investigation.

**Must update each month if used:** change `TB_CSV`, `K9_CSV`, `MONTH`, and the
header print statement at the top of the file to match the current month's filenames.

### `scripts/analyze_march.py` / `scripts/build_march.py`
March 2026 specific. `build_march.py` is the reference implementation for dashboard
patterns — consult it when building new months. `analyze_march.py` is frozen.

## Thundermail live reporting

Launch overview redesign lives in `launch_overview_sample.html`; see maintenance block below.

Three scripts track the Thundermail (TB Pro) subscriber launch. All output goes to
`lisa/daily/` and is published to GitHub Pages. GH Actions runs the daily script hourly.

### `scripts/tbpro_daily.py` — Flight 2 live report
Generates `lisa/daily/latest.html` + `latest.md`. Run locally or via GH Actions.

```
uv run scripts/tbpro_daily.py                    # today
uv run scripts/tbpro_daily.py --date 2026-06-03  # specific date
uv run scripts/tbpro_daily.py --public           # PII-redacted (used in CI)
```

**Key config constants at the top of the file — update per flight:**
- `LAUNCH_DATE` — flight start date (currently `"2026-06-03"` for Flight 2)
- `INVITEE_COUNT` — total invites sent so far this flight
- `EXCLUDE_IDS` — ticket IDs to suppress entirely (known infrastructure problems + their incidents)
- `WATCH_PROBLEMS` — Zendesk problem-type ticket IDs to always track regardless of LAUNCH_DATE (e.g. DKIM #5679)
- `MANUAL_THEMES` — dict of `{ticket_id: "Theme name"}` for tickets that can't be auto-classified (subject gives no signal)

**Community signals:** Add entries to `data/tbpro_community.json` to include manual observations (Matrix channel, Reddit, etc.). Format:
```json
{"entries": [{"date": "YYYY-MM-DD", "source": "Early Birds Matrix Channel",
              "questions": ["..."], "signals": ["..."]}]}
```

**Zendesk auth:** Always use `zd_creds()` imported from `tbpro_daily` — reads env vars first (CI), falls back to `~/.config/zendesk/credentials` (local). Never read the credentials file directly.

**Theme classification:** Two layers — tag-based (`TAG_THEMES`) first, regex fallback (`brand_summary.py` `THEMES`). For one-off corrections use `MANUAL_THEMES`. The `brand_summary.py` file is shared with the monthly report.

### `scripts/tbpro_weekly.py` — weekly executive summary
Runs every Friday via GH Actions. Covers **launch date → today** (not Mon–Sun calendar week).
The `week_bounds()` function floors the start at `LAUNCH_DATE` automatically.
Output: `reports/tbpro/weekly/YYYY-MM-DD.html` + `reports/tbpro/LATEST_WEEKLY.html`

### `scripts/tbpro_launch_overview.py` — full-launch overview
Covers Early Bird (May 4) through today. Run manually to refresh.
```
uv run scripts/tbpro_launch_overview.py
```
Also runs in GH Actions daily alongside `tbpro_daily.py`.

**Invitee counts (update per wave):**
- Early Bird: 600 (May 4, 2026)
- Flight 2 Wave 1: 500 (June 3, 2026)
- Flight 2 Wave 2: 1,500 (June 4, 2026)

### TB Pro reports — maintenance for any model

**All support report HTML** (daily, launch overview, weekly, monthly) must follow Sonnet-safe patterns when redesigned or maintained. Daily and weekly redesigns are **pending** — use `launch_overview_sample.html` as the reference implementation until their samples exist.

**Before any edit** to TB Pro report HTML or generators (`latest.html`, `launch_overview_sample.html`, `launch_overview.html`, `LATEST_WEEKLY.html`, `*_sample.html`, `tbpro_daily.py`, `tbpro_launch_overview.py`, `tbpro_weekly.py`, and eventually `generate.py`): **read** `.cursor/rules/tbpro-sonnet-maintenance.mdc` — mandatory for all models (Sonnet included), not optional.

**Cursor rules** (detail lives in each file):
- `tbpro-launch-sample.mdc` — sample gate; what's omitted from live until Lisa approves
- `tbpro-theme-tickets.mdc` — `.theme-row-wrap` expansions; paraphrased subjects, never raw Zendesk text
- `tbpro-table-patterns.mdc` — sortable headers via `.tbl-sort__inner`; never `display:flex` on `th`/`td`
- `tbpro-copy-tone.mdc` — business hours first; explain WHY time accumulates; no defensive agent framing; scannable copy (no essay blocks)
- `tbpro-sonnet-maintenance.mdc` — section map, safe vs forbidden edits, HTML templates, update workflow

**Essentials (inline — don't skip even if rules unread):**
- **Sample only** until Lisa approves — do not edit `launch_overview.html`, `tbpro_launch_overview.py`, or `latest.html`
- **Theme rows:** `.theme-row-wrap` + `<details class="theme-tickets">`; each line `#ID` link + paraphrased description (not raw subject); same for `.eng-card__subject`; footer *"Ticket subjects paraphrased; non-English quotes include AI translations."*
- **Still open panel:** omitted — do not re-add (blocker-column pattern also removed)
- **Misdirect:** 35 tickets / 28% of Flight 2 volume; callout **under** Flight 2 subscriber themes; exclude `#5470` from TB Pro counts
- **Sidebar anchors:** `#story` `#waves` `#volume` `#aht` `#planning` `#themes` `#ideas` `#engineering` `#glossary`
- **Edit by section:** jump via `<!-- SECTION: name -->` comments (and matching CSS region markers) — one section per change
- **Re-fetch Zendesk** via `fetch_tickets()` / `classify_ticket()` — never hardcode stale ticket IDs from a prior session
- **Scannable copy:** max ~2 short sentences per block or scan-list — masthead = headline + metrics + one line per theme; applies to monthly samples too (see `tbpro-copy-tone.mdc` → *Scannable copy*)

**Update workflow:** fetch live data → paraphrase subjects → grep for PII (`@`, phone patterns) → edit **sample only** → Lisa approves → port to generator. See `DESIGN.md` for sample-gate pattern.

**Monthly archives — never modify:** same rule as monthly sample gate — do not edit prior months' HTML, MD, CSV, or deep dives in `lisa/YYYY/` (`march.html`, `april.html`, `may.html`, frozen `*_deep_dive.html`, etc.). Fix links in the current `*_sample.html` instead; port new drill-downs via `generate.py` after approval.

### FeatureOS CLI caveats
- `sort=votes_count` parameter is **unreliable** — always sort client-side after fetching
- JSON key is `feature_requests`, not `posts` or `data`
- Custom status labels are in `custom_status.title`, not `status`
- Credentials: `~/.featureos.yaml` (api_key + jwt)

## GitHub issue links

Whenever `#NNNN` refers to a GitHub issue in report HTML or markdown, link it: `<a href="https://github.com/thunderbird/{repo}/issues/{n}" target="_blank">#NNNN</a>`. Default repo: `thunderbird-android`. See `.cursor/rules/github-issue-links.mdc` for repo disambiguation and exceptions (rankings, SUMO IDs, Zendesk tickets, CSS).

## The report format
The report follows this exact structure — do not change it:

```
# [Month YYYY] — Monthly Support Report

> **[→ View dashboard]([GitHub Pages URL])**

[2-3 sentence narrative lede]

---
## Support Metrics
- **Overall CSAT:** X% (+/- X pts MoM) ↑/↓
- **CSAT — Donor Support:** X% (+/- X pts MoM) ↑/↓
- **CSAT — TB Pro:** X% ✅
- **Volume:** XXX tickets (+/-X% MoM) — Donor Support XXX, TB Pro XX

---
## Community Support

### Desktop Forum
- **Overall solved rate:** X% (+/- X pts MoM) · XXX real questions · [key signal]

### Android Forum
- **Overall solved rate:** X% (+/- X pts MoM) · [key signal]

---
## Android Reviews
- **Engagement:** XXX incoming Play Store review tickets (up/down from XXX in [prior month])
- **Impact:** X improved ratings, X unchanged, X decreased. Average monthly
  rating — TB X.XX★ (+/-X.XX from [prior month]) · K-9 X.XX★ (+/-X.XX) · Combined X.XX★
- **Volume:** XXX total reviews — TB XXX, K-9 XX. XX languages.

### Top 3 Friction Points
*Sourced from XXX Play Store reviews (TB + K-9, same codebase). Analyzed with AI.*

**1. [Name]**
- XX mentions · XX negative · avg rating X.XX★ · **TB:** XX reviews, **K-9:** XX reviews
- [What users report]
- [Device/language flags]
- 3-month trend: XX → XX → XX negative mentions [trend emoji] [Label]

[repeat for #2 and #3]

### K-9 Churn Watch
- [Signal]: [stat + context]
[4-5 bullets, each with a specific number — only include signals with 3+ mentions]

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- [Priority]: [stat] · [trend] · [why it matters]
[3 bullets]

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound

**🕊 Receive**
- [Volume + notable context]

**🪽 Resolve**
- [CSAT highlights, what worked]

**✨ Resound**
- [Positive signals worth noting]

*Receive / Resolve / Resound is Thunderbird Support's CX action framework.
[Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## Experiments & Iterations
[Lisa fills this in — active experiments, results, what's launching next]

---
## Data Access
Full MoM spreadsheet: [Support Metrics MoM YYYY](URL)
Dashboard: [month.html](GitHub Pages URL)
Raw data (CSV): [month.csv](GitHub raw URL)

---
## Definitions
[Standard definitions block — included by generate.py automatically]
```

## Dashboard structure
Five sections with colored filter buttons (linkable via URL hash):
- **Donor Care** (#donor) — green
- **TB Pro** (#tbpro) — indigo. Includes: new ideas this month + top all-time ideas tables
  with MoM vote deltas. Ideas live here only — not in the report.
- **Android Reviews** (#android) — orange. Includes: Q[N] rating drift alert (quarter
  auto-calculated), stat cards, TB+K-9 star distribution charts, friction points table
  (linked to report with ↔ cross-channel notes), top 10 Play Store languages, definitions
- **Desktop Forum** (#sumo-desktop) — sky blue. Stat card grid (Questions / Solved Rate /
  Ignored % with MoM deltas), then SUMO metrics table with MoM deltas and 3-month trends.
  Signal tables when Roland's report includes them.
- **Android Forum** (#sumo-android) — teal. Same structure as Desktop Forum.
- **K-9 Forum** (#k9-forum) — purple. Auto-fetched from forum.k9mail.app Discourse API
  each run across **all forum categories** (not filtered to Support). Shows: stat cards
  (new topics / accepted-answer rate / unanswered rate) with 3-month trends, top topic
  themes table with 3-month trend column and NEW ↑ badge for themes absent in prior 2
  months, top contributors (bot accounts filtered). No manual data needed — runs
  automatically. History is stored in `data/history.json` under `k9_discourse.themes`.
  Prior months can be backfilled retroactively via the Discourse search API using date ranges.

Dashboard URL pattern: `https://thunderbird.github.io/thunderbird-support-reports/lisa/YYYY/month.html`

## Cross-channel analysis
Each month, compare Play Store friction signals against Android Forum signals and call
out crossover in both directions on the dashboard. Three patterns to look for:

1. **Same issue, both channels** — e.g. v17.0 crashes appeared in Play Store reviews
   and Android Forum. Note in both places; flag if one channel has a workaround the
   other doesn't.
2. **Same gap, different entry point** — e.g. Spam Filter Absent (Play Store) and
   Filters like Desktop (Forum) are the same missing feature hit differently.
3. **Present in Play Store, absent from Forum** — the absence is itself a signal.
   Users who don't seek help just leave reviews and churn. Render these as `.alert`
   blocks in the Community Support section, not table rows.

## Friction point detection
Run on lowercased Play Store review text. Calculate: total mentions, negative (1-3★),
avg rating, TB count, K-9 count.

```python
THEMES = {
    'Push / Notification Sync':    r'notif|push|sync|synchroni|fetch|delayed|15.min',
    'Crashes & Freezes':           r'crash|absturz|crasha|force.close|freeze|app.*stop|angehalten',
    'Stuck Outbox / Send Failure': r'outbox|stuck.*send|send.*fail|sending.*error|cannot.*send',
    'Spam Filter Absent':          r'spam|junk|no.*filter|missing.*filter',
    'Calendar Missing':            r'calend|kalend|agenda|ical|caldav',
    'QR / Settings Import':        r'qr.cod|import.*sett|setting.*import',
    'Email Headers / Print':       r'header|kopf|mail.*head|drucken|print.*mail',
}
```

Top 3 = highest negative mention count.
K-9 churn signals: FairEmail mentions, long-term users leaving,
disproportionate K-9 share of any friction point. Only include if 3+ mentions.

## History
| Month | Reviews | TB Avg | K-9 Avg | Top friction (neg mentions) |
|-------|---------|--------|---------|----------------------------|
| Jan 2026 | 378 | 3.95★ | — | Push sync (19) |
| Feb 2026 | 409 | 3.91★ | 3.47★ | Push sync (23) |
| Mar 2026 | 451 | 3.87★ | 3.52★ | Push sync (31), Spam (10), Crashes (6) |
| Apr 2026 | 596 (TB 495 incl. beta, K-9 101) | 3.81★ | 2.96★ | Push sync (37), Spam (12), Crashes (9) |

K-9 added to dataset March 2026. Beta added (merged into TB count) April 2026.
Q1 TB rating drift: 3.95 → 3.91 → 3.87. April: 3.81★ (continued decline).
K-9 rating dropped sharply in April (-0.56): v17/v18 update regressions + identity churn.
Annual goal: 4★+ Play Store rating.

**Rating source:** Always use the monthly average calculated from the CSV export (that month's
reviews only). The Play Store Console displays a cumulative all-time rolling average, which
differs and moves more slowly — do not use it for MoM comparisons.

## GitHub setup
- Repo: github.com/thunderbird/thunderbird-support-reports
- My GitHub username: lisajill
- My email: lwess@thunderbird.net
- Pages URL: https://thunderbird.github.io/thunderbird-support-reports/

## Friction point deep dives

When a friction point needs more investigation than the main dashboard provides, produce a
standalone deep-dive HTML file alongside the monthly dashboard.

### File naming and location
`lisa/<year>/<month>_<theme>_deep_dive.html` — e.g. `lisa/2026/march_push_deep_dive.html`

### What a deep dive contains
1. **Overview stat cards** — total reviews, negative count, avg rating, reply rate, per-problem breakdown
2. **Jump-to callout** — indigo banner above the filter tabs linking to the recommendations section (always include this)
3. **Filter tabs** — one per problem category (see categorisation below)
4. **Per-section analysis box** — appears *above* the review list in each section, left-border coloured by severity
5. **Review cards** — every matching review, sorted 1★→5★ then by date. Each card shows: app badge (TB/K9), star rating, language badge, date, device (decoded from codename — see DEVICE_MAP below), version, full review text, dev reply inline
6. **Translations** — non-English reviews show original text with a pre-expanded `<details open>` block labelled TRANSLATED + "click to hide". Translations are machine-generated by Claude; note this in the methodology. Two Play Store edge cases to watch: language codes are sometimes wrong (Croatian filed as English, Greek-locale users writing in English) — detect by text content.
7. **Recommendations & star rating math** — anchored section (`id="recommendations"`) at the bottom with: a scenario table showing new avg★ under each fix, an "uncomfortable truth" callout if the easy fixes don't reach the goal, and an actions table ordered by effort (LOW / MED / HIGH)
8. **Analysis notes** — methodology, categorisation logic, translation disclosure

### Problem categorisation pattern (push example — adapt themes per month)
Categorise each review by priority:
1. **B (regression)** — match specific new-version behaviour change (e.g. notification delete/clear/mark-read broken)
2. **C (UX friction, not a bug)** — match poll interval frustration, setup complexity, discoverability
3. **A (core failure)** — everything else

Apply translations before categorising — some keyword signals only appear in the translated text.

### Star rating math
```python
current_sum = sum(int(r['Star Rating']) for r in month_reviews)
current_avg = current_sum / len(month_reviews)
# For each fix scenario:
delta = sum(target_star - int(r['Star Rating']) for r in affected_subset)
new_avg = (current_sum + delta) / len(month_reviews)
```
Always show: conservative (→4★) and optimistic (→5★) variants. Call out the deficit in star-points to the annual goal.

### Device codename map
CSVs contain internal Android codenames, not marketing names. Common ones:
```
e3q → Samsung Galaxy S24 Ultra    pa3q → Samsung Galaxy S25 Ultra
e1s → Samsung Galaxy S24          e1q  → Samsung Galaxy S24+
a12s → Samsung Galaxy A12s        a16x → Samsung Galaxy A16 5G
OP611FL1 → OnePlus 11             shiba → Google Pixel 8
sweet → Xiaomi Redmi Note 10 Pro  cancunf → Motorola Moto G52
m1s → Samsung Galaxy S22 Ultra    a55x → Samsung Galaxy A55
scout → Fairphone 5               cuscoi → Google Pixel 9
```
Unknown codenames: leave as-is, don't guess.

### Linking from the main dashboard
After creating the deep dive, add a `→ deep dive` link (orange, `var(--orange)`) in the friction
table cell for the relevant theme in the main monthly dashboard. Edit the `<td>` that contains
the theme name — append the link after the `<strong>` tag, before the `<br>`.

### CSV encoding note (updated)
CSVs uploaded to GitHub are re-encoded as **UTF-8 with BOM** during the commit process.
Always use `encoding='utf-8-sig'` when reading from the repo. The `encoding='utf-16'` note
in the technical notes below applies only to the raw export from Google Play Console.

## Important technical notes
- YAML `spam` fields must be `0` (not `null`) — the script does integer subtraction and
  `null` causes a TypeError even though `get('spam', 0)` would default to 0 for missing keys
- `spam: 0` is falsy in Python — always check `is not None` rather than truthiness when
  testing whether a value is present. Use `d_sumo.get('total_questions') is not None` pattern.
- Optional `zendesk.tbpro_csat_note` field: when set, shows as a footnote in the report
  and a muted subtext in the dashboard TB Pro CSAT card (use for low-sample months)
- Play Store CSVs exported from Play Console are UTF-16 encoded — `encoding='utf-16'`
- CSVs already committed to the repo: use `encoding='utf-8-sig'` (BOM-prefixed UTF-8)
- Filter to target month before analysis — files contain historical data
- Use `uv run` for Python scripts
- PyYAML required for generate.py — installed automatically via uv inline deps
- Dashboard is built in generate.py (not a separate script like March's build_march.py)
- march-specific scripts are frozen — do not modify them
