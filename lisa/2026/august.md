# August 2026 — Monthly Support Report

> **WIP — numbers under team validation.** July full dashboard skipped; MoM uses Lisa's 8/31 KPI baseline.

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/august.html)**

Donor tickets jumped 212→350 (+65%) on ESR appeals — the 8/31 spoiler was ~95% — while overall volume eased 767→755 (−1.6%). CSAT held at 90.9% (−0.8 vs July); Donor hit 92.7% (+7.0). Thundermail 85.7% (−9.8) is pricing DSATs (no monthly / no à la carte / 100 CAD), not support — adjusted support satisfaction 100%. TB Play Store recovered to 3.74★ (+0.16); push/sync is still #1 friction (34 negative, rising).

---
## Support Metrics
- **Overall CSAT:** 90.9% (-0.8 pts MoM) ↓
- **CSAT — Donor Support:** 92.7% (+7.0 pts MoM) ↑
- **CSAT — Thundermail:** 85.7%*
- **Volume:** 755 tickets (-1.6% MoM) — Donor Support 350, Thundermail 187, App Store Reviews 218

*DSATs: no monthly plan, no à la carte, price too high (100 CAD). Support satisfaction excluding those: 100%.*

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 58% (-6 pts MoM) · 955 questions · 955 questions vs July 751; solved rate 58% (July 64%). Spectrum/Charter cause surge 34 qs (3.24×). Yahoo +83%, Microsoft +47%. v153 POP spikes recurring; v154 × Spectrum monthly cluster (13 qs, 3.1×). Attachments topic mix +206%.

### Android Forum
- **Overall solved rate:** 61% (+1 pts MoM) · 51 questions · 51 questions vs July 55; 61% solved (July 60%). Ignored 27%. No August LLM cluster report yet.

---
## Android Reviews
- **Engagement:** 218 incoming Play Store review tickets (down from 272 in July)
- **Impact:** [X improved ratings, X unchanged, X decreased.] Average monthly rating — TB 3.74★ (+0.16 from July ↑) · K-9 3.60★ (-0.04 from July ↓) · Combined 3.71★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 564 total reviews — TB 456 (415 stable + 41 beta), K-9 108. 27 languages.

### Top 3 Friction Points
*Sourced from 564 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 51 mentions · 34 negative · avg rating 2.76★ · **TB:** 44 reviews, **K-9:** 7 reviews
- Reports delayed or missing notifications; sync often requires manual refresh.
- Devices: tegu (2), pa1q (2), b5q (2) · Languages: English, German, French
- 3-month trend: 20 → 31 → 34 negative mentions 🔴 Accelerating

**2. Spam Filter Absent**
- 35 mentions · 18 negative · avg rating 3.26★ · **TB:** 28 reviews, **K-9:** 7 reviews
- Reports no way to mark mail as spam or junk.
- Devices: a53x (2), o1s (1), warhol (1) · Languages: English, German, Italian
- 3-month trend: 13 → 22 → 18 negative mentions 📉 Improving

**3. Stuck Outbox / Send Failure**
- 5 mentions · 5 negative · avg rating 1.20★ · **TB:** 4 reviews, **K-9:** 1 reviews
- Reports mail stuck in Outbox or send failures (small n — generator reused a push/sync paraphrase; treat as send-path pain, not notify).
- Devices: OnePlus 11 (2), vienna (1), Google Pixel 6a (1) · Languages: English, Dutch
- 3-month trend: 2 → 0 → 5 negative mentions 🔴 Accelerating *(July count not in the 8/31 email — middle 0 is a gap, not a measured zero)*

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Push / Notification Sync — still #1, still rising:** 34 negative (31→34) · 51 mentions · avg 2.76★ · 3-mo 20→31→34 · no product fix in market
- **Spam Filter Absent — #2, fewer mentions:** 18 negative (22→18) · still no junk-filter build · July QR spike (25 neg) cooled to 3 — not a current 4★ lever
- **Rating gap:** TB 3.74★ needs +0.26★ to 4★ (K-9 3.60★, −0.04). Converting push 1–3★ reviewers is still the primary path

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound

**🕊 Receive**
- 755 Zendesk tickets (−1.6% vs July) — Donor 350 (+65%, ESR appeals), Thundermail 187 (−34%), App Store Reviews 218 (−20%)
- 564 Play Store reviews across 27 languages; 218 incoming review tickets
- Push/sync still #1 friction (34 negative, 31→34 — rising, no fix shipped). July QR/Settings Import spike cooled (25→3 negative)
- 955 desktop forum questions (751 in July) — Spectrum/Charter cluster 34 qs

**🪽 Resolve**
- Donor CSAT 92.7% (+7.0 pts) on the ESR-appeal spike
- Thundermail CSAT 85.7% is product/pricing DSATs; support satisfaction excluding those 100%
- Android forum solved rate 61% (+1 pt) on 51 questions

**✨ Resound**
- **48% of TB reviews are 5★** (220 of 456) — TB monthly average 3.74★ (+0.16 vs July)
- July QR/Settings Import spike (25 neg, mostly 1★) dropped to 3 negative
- Spam-filter negative mentions 22→18 — fewer mentions, not a shipped junk filter
- Thundermail **Webmail** and **MFA** show as Landed on the ideas board

*Receive / Resolve / Resound is Thunderbird Support's CX action framework. [Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## What's Coming Up

[Lisa fills — experiments, iterations, what's launching next.]

---
## Data Access
Dashboard: [august.html](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/august.html)
Raw data (CSV): [august.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/august.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
