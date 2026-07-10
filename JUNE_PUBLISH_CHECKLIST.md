# June 2026 — Publish Readiness Checklist

**Target:** Email + Notion + GitHub Pages publish  
**Canonical dashboard:** `lisa/2026/june_sample.html` (restrained design, Lisa-approved ship target)  
**Primary URL after publish:** https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/june.html

---

## Status at a glance

| Area | Status | Owner |
|------|--------|-------|
| Zendesk / MoM data in YAML | ✅ Complete | — |
| Play Store analysis (360 reviews) | ✅ Complete | — |
| FeatureOS ideas | ✅ Complete | — |
| SUMO desktop/android stats | ✅ Complete (methodology caveat) | — |
| Restrained dashboard (`june_sample.html`) | ✅ Content complete | Lisa final read |
| Markdown report (`june.md`) | ✅ Drafted (Lisa edit pass) | Lisa |
| Live dashboard (`june.html`) | ⚠️ Old `generate.py` layout — not restrained | Agent on publish |
| Push deep dive | ✅ PII fix applied (Play Console IDs removed) | — |
| SUMO / Connect drill-downs | ✅ Ship as-is | — |
| Rating impact line (improved/unchanged/decreased) | ⚠️ Null — needs prev-month CSVs + regenerate | Agent |
| Experiments & What's Coming Up | ⚠️ Lisa fills manually | Lisa |
| Formal sample-gate sign-off | ⚠️ Remove proto banner before publish | Lisa |

---

## Tomorrow morning — 30-minute workflow (Lisa)

1. **Open local dashboard (5 min)**  
   `file:///Users/lwess/Documents/Thunderbird-Support-Reports/lisa/2026/june_sample.html`  
   Spot-check: GCS methodology banner, push/spam copy (no “improving” on unshipped fixes), drill-down links, RRR section.

2. **Edit `june.md` (10 min)**  
   - Lede + RRR are drafted — adjust voice, add experiments / what's coming up.  
   - Confirm MoM spreadsheet link in Data Access (internal URL — not in repo).  
   - Optional: add rating-impact numbers once agent regenerates (see below).

3. **Approve ship path (2 min)**  
   **Recommended (path of least resistance):** copy `june_sample.html` → `june.html`, rename deep dive to `june_push_deep_dive.html`, update deep-dive link in dashboard, remove proto banner.  
   **Do not** port full CSS to `generate.py` before tomorrow — that's a multi-day task.

4. **Agent pre-push (10 min)**  
   - `cp lisa/2026/june_sample.html lisa/2026/june.html` (+ strip proto banner, fix title)  
   - `cp lisa/2026/june_push_deep_dive_sample.html lisa/2026/june_push_deep_dive.html`  
   - Update friction deep-dive href in `june.html`  
   - Re-run `uv run scripts/generate.py june 2026` only if Play Store CSVs are present (for rating-impact line in `.md`)  
   - Grep PII (zero matches required):
     ```bash
     rg '@|8696262544613553264|play\.google\.com/console|\[edited\]@|@msn\.com' lisa/2026/june*
     ```

5. **Commit + push (3 min)**  
   Lisa says "commit and push" — use repo commit pattern from `CLAUDE.md`.  
   GitHub Pages updates within ~2 min of push to `main`.

6. **Send (5 min)**  
   - Paste `june.md` into Notion + email  
   - Dashboard link: https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/june.html

---

## Commit vs keep local

### Commit to repo (public)

- `data/june_2026.yaml`, `data/history.json` (if changed)
- `lisa/2026/june.md`, `june.html`, `june.csv`, `june_analysis.json`
- `lisa/2026/june_push_deep_dive.html` (renamed from sample at publish)
- Drill-downs: `june_sumo_trending.*`, `june_desktop_priorities.*`, `june_connect_ideas.*`
- `index.md` (June row — already correct URL)
- `JUNE_PUBLISH_CHECKLIST.md` (this file)
- Compare/archive files optional — they now redirect to `june_sample.html`

### Keep local (do NOT commit)

- `Support Metrics MoM - 2026.csv` — internal spreadsheet
- `CSAT Survey updates.pdf`, `March Donor Reprot.pdf`, `Vision.pdf`
- `tbpro_waitlist_wave1.csv`
- Play Store raw CSVs in `data/input/` (if fetched locally — bucket path not in repo)
- `.claude/` lock files

---

## PII audit notes (June deliverables only)

| Finding | Severity | Action |
|---------|----------|--------|
| Play Console URLs with developer account ID in push deep dive | **P0 — fixed** | Removed all `play.google.com/console/developers/…` links; `safe_play_link()` blocks at source |
| SUMO question titles with emails/domains/raw subjects | **P0 — fixed** | `redact_sumo_title()` paraphrases to generic labels; MD tooltips scrubbed |
| Play Store friction quotes in `june.md` / deep dive | **P0 — fixed** | `paraphrase_review()` emits thematic one-liners only — no verbatim review text |
| Raw review text in push deep dive | **P0 — fixed** | All review cards use paraphrased summaries |

### Pre-commit PII grep (run every time)

```bash
rg '@|8696262544613553264|play\.google\.com/console|\[edited\]@|@msn\.com' lisa/2026/june*
```

Zero matches required before commit. Also verify no raw review paragraphs remain in deep dive or report quotes.

---

## Methodology footnotes (must stay visible)

1. **Play Store GCS shift (June 2026+):** May 493 (manual UI) vs June 360 (GCS auto-export) — MoM volume comparisons carry a caveat. Mobile manager approved July 2026.
2. **SUMO concatenation method:** Desktop solved rate MoM (−10 pts) compares Roland's new figures — May not restated.

Both are in `june_sample.html`, `june.md`, and YAML `methodology_notes`.

---

## Post-publish (next sprint)

- Port restrained layout to `scripts/generate.py` so future months regenerate correctly
- Create `monthly-report-sample.mdc` maintenance rule
- Rename/remove `*_sample.html` / compare prototypes or mark archived in `index.md`
