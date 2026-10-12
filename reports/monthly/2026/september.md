# September 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/september.html)**

Overall CSAT 86% (−4.9 pts).

- Donor CSAT 77.1% (−15.6 pts)
- Thundermail CSAT 94.8% (+9.1 pts). Contact rate 7.3% among PostHog-visible users (400 of 5,509, +2.4 pts)
- Play Store review tickets (1–3 stars): 168
- Desktop forum: 1,002 questions, 51% solved (−7 pts). Receive-mail failures (50), TB 155 blank filters (35, fixed in 155.0.1), Alice.it/TIM (21)

---
## Support Metrics
- **Overall CSAT:** 86% (-4.9 pts MoM) ↓
- **CSAT — Donor Support:** 77.1% (-15.6 pts MoM) ↓*
- **CSAT — Thundermail:** 94.8% ✅
- **Volume:** 1001 tickets (+32.6% MoM) — Donor Support 344, Thundermail 489, App Store Reviews 168
- **Thundermail contact rate:** 400 unique requesters / 5509 PostHog-visible users = 7.3% · 1.12 requester-eligible tickets per requester. *Unique people (`uniq(person_id)`), never event totals; not an all-subscriber rate.*

*Donor CSAT 77.1% on 48 ratings (37 Good, 11 Bad), down 15.6 pts from August’s 92.7%. The 11 Bad ratings were spread across topics with no single driver, consistent with normal variation on a small sample.*

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 51% (-7 pts MoM) · 1002 questions · 1,002 desktop questions (August 955); synthetic solved rate 51% (August 58%). LLM names receive-mail failures (50), TB 155 blank filters (35, fixed 155.0.1), and Alice.it/TIM (21).

### Android Forum
- **Overall solved rate:** 66% (+5 pts MoM) · 47 questions · 47 questions (August 51) 66% solved (+5 pts) Push/sync: 3 Blank bodies: 3 QR import: 3 No spikes in the 41-question set

---
## Android Reviews
- **Engagement:** 168 incoming Play Store review tickets (down from 218 in August)
- **Impact:** 7 improved · 11 unchanged · 2 decreased *(of 20 reviews active in both months — see footnote)*. Average monthly rating — TB 3.76★ (+0.02 from August ↑) · K-9 3.63★ (+0.03 from August ↑) · Combined 3.74★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 402 total reviews — TB 335 (306 stable + 29 beta), K-9 67. 30 languages.

### Top 3 Friction Points
*Sourced from 402 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 38 mentions · 25 negative · avg rating 2.58★ · **TB:** 32 reviews, **K-9:** 6 reviews
- Reports delayed or missing notifications; sync often requires manual refresh.
- Devices: Google Pixel 7 (1), warhol (1), Samsung Galaxy A55 (1) · Languages: English, German, Italian
- 3-month trend: 31 → 34 → 25 negative mentions 📉 Improving

**2. QR / Settings Import**
- 11 mentions · 8 negative · avg rating 2.18★ · **TB:** 11 reviews, **K-9:** 0 reviews
- Reports difficulty importing settings or using QR setup.
- Devices: Samsung Galaxy S25 Ultra (1), mustang (1), a57x (1) · Languages: German, English, Dutch
- 3-month trend: 25 → 3 → 8 negative mentions 🔴 Accelerating

**3. Spam Filter Absent**
- 12 mentions · 7 negative · avg rating 3.33★ · **TB:** 10 reviews, **K-9:** 2 reviews
- Reports no way to mark mail as spam or junk.
- Devices: grizzly (1), warhol (1), r0s (1) · Languages: Dutch, English, Italian
- 3-month trend: 22 → 18 → 7 negative mentions 📉 Improving

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Push / Notification Sync — still #1:** 25 negative (34→25) · 38 mentions · avg 2.58★ · 3-mo 31→34→25. Mention-count drop is not a shipped notification fix.
- **QR / Settings Import — back in the top 3:** 8 negative (3→8) · 11 mentions · avg 2.18★ · 3-mo 25→3→8
- **Rating gap:** TB 3.76★ needs +0.24★ to 4★ (K-9 3.63★, +0.03). Converting push 1–3★ reviewers is still the primary path.

---
## What's Coming Up

**What's new: Thundermail plan + External ID on /contact tickets.** Logged-in users who file via /contact now send plan data and External ID into Zendesk, so we can triage, route, and report Thundermail customer vs non-customer tickets.

- **Phase 2** is the same payload on every other intake path (email and unsigned forms), so we can segment customer vs non-customer everywhere.
- **Donors:** the same approach is in progress.
- **Constraints:** login is never required to file; email-direct stays.


---
## Data Access
Dashboard: [september.html](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/september.html)
Raw data (CSV): [september.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/reports/monthly/2026/september.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.

**Thundermail contact rate** — unique Zendesk requesters divided by unique people (`uniq(person_id)`, never Total count of events) on PostHog `accounts.activity` in the calendar month. That denominator is PostHog-visible users, not all subscribers, not the mail series, and not Stalwart-only IMAP users who never hit PostHog. Mail people are unique people who fired ham ingest, spam ingest, or outbound sent. Surfaces overlap and are never summed.

**Webmail sign-ins** — unique people with `accounts.login` and clientId `thunderbird-stormbox`. Long-lived sessions may not require a new sign-in, so this is a floor rather than a complete count of webmail users. Webmail tickets are tagged Thundermail what: UI::Webmail (`thundermail_what_ui__webmail`) or intelligent-triage webmail (`thundermail_entity_area_webmail`) — union, counted once. They can also sit on Account Hub / Thundermail service tags.

**Internal users** — we cannot omit staff the way the PostHog UI does. This project has 0 people with an email property and those events have no usable `$host`, so unique-people counts include staff.
