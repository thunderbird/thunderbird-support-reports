# June 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/june.html)**

June was a strong CSAT month — every satisfaction score rose. Overall hit 83.6% (+6.9 pts), Donor Support rebounded to 80.0%, and Thundermail held at 95.0% while volume eased 12% with the seasonal lull. The Play Store rating is the one metric still moving the wrong way: TB slipped to 3.68★, with push/sync still the top friction.

---
## Support Metrics
- **Overall CSAT:** 83.6% (+6.9 pts MoM) ↑
- **CSAT — Donor Support:** 80.0% (+13.3 pts MoM) ↑
- **CSAT — Thundermail:** 95.0% ✅
- **Volume:** 534 tickets (-11.9% MoM) — Donor Support 215, Thundermail 117, App Store Reviews 202

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 60% (-10 pts MoM) · 750 questions · Ignored %: 21% · Trusted contributor %: 43%
- **Startup freeze/crash spike:** 24 → 60 questions MoM (2.5×) while total volume fell — strongest regression signal in Roland's June analysis (severity 3.6, 57% resolved)
- **Spectrum/Charter invalid-certificate spike:** 7 questions at 21.5× baseline (Jun 9), new this month — ISP certificate change hitting desktop IMAP users. Recommended: KB coverage for ISP cert expiry, plus clearer in-product untrusted-cert handling; engineering priority TBD
- **v152 provider regressions (hypothesis):** Gmail (4 qs, 4.7× lift) and Microsoft/Outlook (6 qs, 4.4× lift) clusters flagged by PROJECT1 in late June — watching, not confirmed
- Sources: [PROJECT1 spike report](https://thunderbird.github.io/thunderbird-metrics-and-reports/PROJECT1/REPORTS/desktop/monthly-summary-latest.html) · [LLM insights](https://thunderbird.github.io/thunderbird-metrics-and-reports/LLM_INSIGHTS/REPORTS/desktop/monthly-summary-latest.html)

### Android Forum
- **Overall solved rate:** 68% (+4 pts MoM) · 50 questions · Roland LLM flags delivery/notify pain (#6 stopped receiving mail, severity 4.0; #2 notifications despite sync) and QR transfer friction (#7) — [LLM Insights](https://thunderbird.github.io/thunderbird-metrics-and-reports/LLM_INSIGHTS/REPORTS/android/monthly-summary-latest.html)

*Methodology: SUMO figures use Roland's new concatenation method (Mozilla gated the SUMO API behind JS). May is not restated — MoM deltas carry a methodology caveat; compare like-for-like against Roland's current figures, not the originally-published May numbers.*

---
## Android Reviews
- **Engagement:** 202 incoming Play Store review tickets (down from 209 in May)
- **Impact:** Average monthly rating — TB 3.68★ (-0.05 from May ↓) · K-9 3.55★ (+0.02 from May ↑) · Combined 3.66★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 360 total reviews — TB 295 (276 stable + 19 beta), K-9 65. 30 languages.

*Methodology: June is the first month with review CSVs fetched from the Play Console GCS export bucket (Jan–May used manual Play Console UI downloads; mobile manager approved the shift, July 2026). May 493 → June 360 spans that boundary — count differences may reflect the source change, not necessarily real volume movement.*

### Top 3 Friction Points
*Sourced from 360 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 33 mentions · 20 negative · avg rating 3.00★ · **TB:** 28 reviews, **K-9:** 5 reviews
- Reports delayed or missing notifications; sync often requires manual refresh.
- Devices: a32x (2), Samsung Galaxy S24 (1), tegu (1) · Languages: English, German, French
- 3-month trend: 37 → 34 → 20 negative mentions 📉 Fewer mentions (not attributed to fixes)

**2. Spam Filter Absent**
- 20 mentions · 13 negative · avg rating 3.00★ · **TB:** 18 reviews, **K-9:** 2 reviews
- Reports no way to mark mail as spam or junk.
- Devices: zircon (1), tegu (1), e2s (1) · Languages: English, German, French
- 3-month trend: 12 → 8 → 13 negative mentions 🔴 Accelerating

**3. Crashes & Freezes**
- 8 mentions · 5 negative · avg rating 2.50★ · **TB:** 7 reviews, **K-9:** 1 review
- Reports app crashes or freezes, especially on startup or when deleting mail.
- Devices: OnePlus (1), a53x (1), a5ulte (1) · Languages: English, Spanish, Italian
- 3-month trend: 9 → 5 → 5 negative mentions ➡️ Stable

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Push / Notification Sync — primary product ask:** 20 negative mentions (down from 34) · still #1 by volume · 3-mo trend shows fewer mentions (37→34→20) — not attributed to shipped fixes · no product fix in market yet
- **Spam Filter Absent — rising user pain, lower product priority:** 13 negative (up from 8) · only top-3 theme still rising MoM · now #2. Users feel it; mobile leadership has other work ahead. No fix in market
- **Rating gap:** TB at 3.68★ needs +0.32★ to reach the 4★ goal; K-9 held at 3.55★. Converting push 1–3★ reviewers is the primary path

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound

**🕊 Receive**
- 534 Zendesk tickets (−12% MoM) — seasonal lull; Donor Support 215, Thundermail 117, App Store Reviews 202
- 360 Play Store reviews across 30 languages
- Push/sync remained #1 friction (20 negative, 34→20 — fewer mentions, no fix shipped); spam-filter mentions rising (13 negative, 8→13)
- 750 desktop forum questions (new SUMO methodology)

**🪽 Resolve**
- CSAT rose across every brand: Overall 83.6% (+6.9 pts) · Thundermail 95.0% (+2.1) · Donor 80.0% (+13.3)
- Android forum solved rate 68% (+4 pts)
- 202 Play Store review tickets received

**✨ Resound**
- **47% of TB reviews are 5★** (139 of 295) — a loyal base actively showing up; the drag is concentrated in a fixable low-star slice
- **Push negative mentions down 46% over Q2** (37→20) — quieting without a fix shipped; the trend is moving in the right direction
- **Crashes flat two months straight** (9→5→5 negative) — stopped getting worse
- **K-9 stabilized** — 3.55★ (+0.02 MoM) after the sharp April regression
- **Desktop cert spike: 100% answered** — novel ISP-driven issue (Spectrum/Charter), fully served by the community
- Thundermail CSAT 95.0% (+2.1 pts) · Donor 80.0% (+13.3 pts)

*Receive / Resolve / Resound is Thunderbird Support's CX action framework. [Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## Data Access
Dashboard: [june.html](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/june.html)
Raw data (CSV): [june.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/june.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
