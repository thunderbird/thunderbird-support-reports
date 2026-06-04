# May 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html)**

Thundermail support matured significantly in May — 118 tickets at 92.9% CSAT, signaling the wave is landing well with subscribers. K-9 Mail staged a notable Play Store recovery, climbing from 2.96★ to 3.53★ as v17/v18 regression reports faded. Donor Support CSAT dipped to 66.7% (-10.3 pts MoM), but ticket-level review shows most bad ratings were misdirected contacts, wrong-channel requests, and measurement noise — with one actionable gap: German-language bank transfer documentation.

---
## Support Metrics
- **Overall CSAT:** 76.7% (-1.0 pts MoM) ↓
- **CSAT — Donor Support:** 66.7% (-10.3 pts MoM) ↓*
- **CSAT — Thundermail:** 92.9%*
- **Volume:** 606 tickets (+17.4% MoM) — Donor Support 279, Thundermail 118, App Store Reviews 209

*Seven of nine bad ratings were noise — wrong channel, misdirected tickets, a donor who went quiet after asking about donation numbers. The one that matters: a real gap in our German-language donor KB.*

*Both dissatisfied ratings (DSATs) were misdirected emails to Thundermail, remediated via thunderbird-accounts#834.*

---
## Community Support

### [Desktop Forum](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html#sumo-forum)
- **Overall solved rate:** 70% (+6 pts MoM) · 802 questions · Ignored %: 17% (-6 pts) · Trusted contributor %: 49% (+4 pts)
- **[Top issue](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html#top-trending-topics):** Send/Receive problems dominated at 31% of volume (250 questions) — up from 26% in April, largest single-month share in 3 months
- **[Recommended priorities](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html#recommended-priorities):**
  - **Authentication / OAuth fragility** — 145 questions (18.1%) · Gmail, Outlook, Yahoo, Comcast provider failures; repeated password prompts; friction with new Account Setup Hub
  - **Data loss / folder integrity** — 54 questions (6.7%) · highest emotional charge; "wiped out all my folders," emails disappeared, Local Folders gone
  - **Update regressions** — 43 questions (5.4%) · UI, send/receive, drag-and-drop, folder display all affected; updates breaking established workflows at scale

### [Android Forum](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html#android-forum)
- **Overall solved rate:** 64% (-1 pts MoM) · 55 questions · ignored rate jumped to 31% (from 22% in April)

---
## [Android Reviews](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html#play-store-reviews)
- **Engagement:** 209 incoming Play Store review tickets (up from 205 in April) — tickets are opened only for low-star reviews (1–3★) that we reply to, not every review
- **Impact:** 2 improved · 12 unchanged · 2 decreased *(of 16 reviews active in both months — see footnote)*. Average monthly rating — TB 3.73★ (-0.08 from April ↓) · K-9 3.53★ (+0.57 from April ↑) · Combined 3.68★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 493 total reviews — TB 385 (348 stable + 37 beta), K-9 108. 32 languages.

### Top 3 Friction Points
*Sourced from 493 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 51 mentions · 34 negative · avg rating 2.94★ · **TB:** 35 reviews, **K-9:** 16 reviews
- "Notifications are still broken. Even though it's the most privileged app on my phone, still refuses to send me any. Manage folders > Inbox > Enable…"
- Devices: klimt (2), bogota (2), itel-P663LN (2) · Languages: English, German, Spanish
- 3-month trend: 31 → 37 → 34 negative mentions 📉 Improving

**2. Spam Filter Absent**
- 11 mentions · 8 negative · avg rating 2.82★ · **TB:** 11 reviews, **K-9:** 0 reviews
- "ik kan niet zelf mail adressen blokkeren. ds ik krijg steeds dezelfde spam (waar ook niet-spam tussendoor staat), minstens 100 per dag van dezelfde spammert.…" *(Dutch — "I can't block email addresses myself. That's why I keep getting the same spam (mixed in with non-spam messages), at least 100 a day from the same spammer...")*
- Devices: e2s (2), gts7l (1), apollo (1) · Languages: German, French, Dutch
- 3-month trend: 10 → 12 → 8 negative mentions 📉 Improving

**3. Crashes & Freezes**
- 5 mentions · 5 negative · avg rating 1.80★ · **TB:** 4 reviews, **K-9:** 1 reviews
- "Crashea en Android 6. Es imposible entrar al correo. No pasa nada si no es compatible. Indica lo y ya está" *(Spanish — "It crashes on Android 6. I can't access my email. It's no big deal if it's not compatible. Just say so and that's it.")*
- Devices: cancunn (1), dew (1), grandpplte (1) · Languages: English, Italian, vi
- 3-month trend: 6 → 9 → 5 negative mentions 📉 Improving

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Push / Notification Sync:** 32 negative mentions (down from 37) · improving for 2nd straight month · still the single largest drag on rating; TB at 3.74★, needs +0.26★ to reach goal
- **Stuck Outbox / Send Failure:** 4 negative (up from 1 in April) · accelerating · K-9 now matching TB volume on this theme; watch for continuation in June
- **K-9 rating baseline:** 3.53★ (recovered +0.57★ MoM) · sustaining this through the next release cycle is essential to maintaining combined rating progress

---
## What's Coming Up

**Support team headcount (as of May 2026):**
- 1 dedicated support agent focused on Thundermail subscriber tickets
- Donor Support handled by an outsourced team


---
## Data Access
Dashboard: [may.html](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/may.html)
Raw data (CSV): [may.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/may.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.

**Non-English quotes** — translated inline by AI. Translations are provided for readability and may not be exact.
