# October 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/october.html)**

Overall CSAT 94.1% (+8.1 pts).

- Donor CSAT 76.5% (−0.6 pts)
- Thundermail CSAT 100% (+5.2 pts) on 51 ratings. Contact rate 6.2% among PostHog-visible users (320 of 5,164, −1.1 pts)
- Push still leads Play Store friction (17 negative). Crashes 6, spam filter 5

---
## Support Metrics
- **Overall CSAT:** 94.1% (+8.1 pts MoM) ↑
- **CSAT — Donor Support:** 76.5% (-0.6 pts MoM) ↓
- **CSAT — Thundermail:** 100%*
- **Volume:** 991 tickets (-1.0% MoM) — Donor Support 417, Thundermail 421, App Store Reviews 153
- **Thundermail contact rate:** 320 unique requesters / 5164 PostHog-visible users = 6.2% · 1.16 requester-eligible tickets per requester. *Unique people (`uniq(person_id)`), never event totals; not an all-subscriber rate.*

*100% on 51 ratings (52% response rate). All 51 are Good. 29 left no comment. 10 said the issue was resolved. 9 said the agent was kind. No single topic.*

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 57% (+6 pts MoM) · 1054 questions · 1,054 desktop questions (September 1,002); synthetic solved rate 57% (September 51%). Attach button does nothing, 169 questions, fixed in 158.0.1, 159.0, and ESR 153.5.0.
- Attach button does nothing — 169 questions, new this month.
  - Fixed in [158.0.1](https://www.thunderbird.net/en-US/thunderbird/158.0.1/releasenotes/), [159.0](https://www.thunderbird.net/en-US/thunderbird/159.0/releasenotes/), and [ESR 153.5.0](https://www.thunderbird.net/en-US/thunderbird/153.5.0esr/releasenotes/). [Bugzilla 2077590](https://bugzilla.mozilla.org/show_bug.cgi?id=2077590).
- Gmail problems that cannot be diagnosed: 13 → 29.
- Cannot receive new mail, no error given: 53 → 22.
- AT&T POP certificate: 1 → 15. Fixed by AT&T.
- Account setup wizard failures: 39 → 28.

### Android Forum
- **Overall solved rate:** 65% (-1 pts MoM) · 62 questions · 62 questions (September 47). Solved 65%. The SUMO forum gets too few Thunderbird for Android questions to give much useful signal. The labeled set is 56 questions.

---
## Android Reviews
- **Engagement:** 153 incoming Play Store review tickets (down from 168 in September)
- **Impact:** 3 improved · 5 unchanged · 1 decreased *(of 9 reviews active in both months — see footnote)*. Average monthly rating — TB 4.07★ (+0.31 from September ↑) · K-9 3.58★ (-0.05 from September ↓) · Combined 3.99★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 530 total reviews — TB 444 (409 stable + 35 beta), K-9 86. 33 languages.

### Top 3 Friction Points
*Sourced from 530 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 29 mentions · 17 negative · avg rating 2.97★ · **TB:** 28 reviews, **K-9:** 1 reviews
- Reports delayed or missing notifications; sync often requires manual refresh.
- Devices: p3s (1), pa1q (1), a32 (1) · Languages: English, Italian, Spanish
- 3-month trend: 34 → 25 → 17 negative mentions 📉 Improving

**2. Crashes & Freezes**
- 10 mentions · 6 negative · avg rating 2.80★ · **TB:** 7 reviews, **K-9:** 3 reviews
- Reports app crashes or freezes, especially on startup or when deleting mail.
- Devices: venice (1), dm3q (1), j4primelte (1) · Languages: English, German
- 3-month trend: 4 → 6 → 6 negative mentions ➡️ Stable

**3. Spam Filter Absent**
- 16 mentions · 5 negative · avg rating 3.69★ · **TB:** 12 reviews, **K-9:** 4 reviews
- Reports no way to mark mail as spam or junk.
- Devices: Google Pixel 7 (1), OP5D3BL1 (1), Motorola Moto G52 (1) · Languages: English, German
- 3-month trend: 18 → 7 → 5 negative mentions 📉 Improving

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Thunderbird for Android 4.07★:** Maintaining a 4.0 Play Store rating for Thunderbird for Android is one of our annual goals. This is the first month we hit it. Up from 3.76★. 250 of 444 reviews are 5★.
- **Push / Notification Sync:** 17 negative. Later lever. A lower mention count is not a shipped notification fix.
- **Crashes:** 6 negative. Later lever.


---
## Data Access
Dashboard: [october.html](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/october.html)
Raw data (CSV): [october.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/reports/monthly/2026/october.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.

**CSAT** — share of rated tickets marked Good. Measured on tickets solved in the previous month (October for this report), not tickets created. After a ticket is solved, the customer answers "Did you get the help you needed?" with Good or Bad. A follow-up asks, "Please tell us more about your support experience." Comments are optional. CSAT = Good ÷ (Good + Bad). Donor 13 Good ÷ 17 ratings = 76.5%.

**CSAT response rate** — ratings received ÷ solved tickets surveyed. Low response rates mean a few ratings carry the whole percentage.

**Thundermail contact rate** — unique Zendesk requesters divided by unique people (`uniq(person_id)`, never Total count of events) on PostHog `accounts.activity` in the calendar month. That denominator is PostHog-visible users, not all subscribers, not the mail series, and not Stalwart-only IMAP users who never hit PostHog. Mail people are unique people who fired ham ingest, spam ingest, or outbound sent. Surfaces overlap and are never summed.

**Webmail sign-ins** — unique people with `accounts.login` and clientId `thunderbird-stormbox`. Long-lived sessions may not require a new sign-in, so this is a floor rather than a complete count of webmail users. Webmail tickets are tagged Thundermail what: UI::Webmail (`thundermail_what_ui__webmail`) or intelligent-triage webmail (`thundermail_entity_area_webmail`) — union, counted once. They can also sit on Account Hub / Thundermail service tags.

**Internal users** — we cannot omit staff the way the PostHog UI does. This project has 0 people with an email property and those events have no usable `$host`, so unique-people counts include staff.
