# April 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/april.html)**

> **Note:** April was an appeals month — donor outreach drove the volume spike and shapes the comparisons throughout this report.

April was Donor Support's strongest month of the year — **77% CSAT (+8 pts MoM)** on a 500-ticket month that nearly doubled volume versus March. Overall CSAT followed to 77.7% (+2.7).

Mobile community signal continues to concentrate on **push / notification sync** (37 negative Play Store mentions, trending 23 → 31 → 37 over the quarter). The Android team's pivot to notifications work this month addresses the loudest community pain head-on.

Desktop, by contrast, has three competing themes pulled from 733 April SUMO questions: **authentication / OAuth fragility** (121 questions, 16.5%), **update regressions** (55, 7.5%), and **folder / data loss** (41, 5.6%). The desktop equivalent of mobile's notifications problem is the auth-and-connectivity layer — both are the always-on plumbing users assume just works, and both are where loss of trust accumulates fastest.

---
## Support Metrics
- **Overall CSAT:** 77.7% (+2.7 pts MoM) ↑
- **CSAT — Donor Support:** 77.0% (+8.0 pts MoM) ↑
- **CSAT — TB Pro:** 62.5%*
- **Volume:** 516 tickets (+93.3% MoM) — Donor Support 500, TB Pro 16

*3 ratings only — not statistically significant. One dissatisfied rating from a contributor checkout error.*

---
## Android

### Forum
- **Overall solved rate:** 65% (-7 pts MoM) · 73 questions · Send/Receive dominant (21 questions, 29%); crashes (8) and passwords/sign-in (6) follow.

### Play Store Reviews
- **Engagement:** 205 replies to 1-3 star reviews (down from 215 in March)
- **Impact:** 0 improved · 3 unchanged · 1 decreased *(of 4 reviews active in both months — see footnote)*. Average monthly rating — TB 3.81★ (-0.06 from March ↓) · K-9 2.96★ (-0.56 from March ↓) · Combined 3.66★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 596 total reviews — TB 495, K-9 101. 29 languages.

#### Top 3 Friction Points
*Sourced from 596 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI.*

**1. Push / Notification Sync**
- 52 mentions · 37 negative · avg rating 2.73★ · **TB:** 42 reviews, **K-9:** 10 reviews
- "used to use this mail client for years, they have broken imap sync somehow. only every like 1 in 10 messages is getting synced now. had to switch to a…"
- Devices: Samsung Galaxy S25 Ultra (2), pa1q (2), a32x (2) · Languages: English, German, French
- 3-month trend: 23 → 31 → 37 negative mentions 🔴 Accelerating

**2. Spam Filter Absent**
- 23 mentions · 12 negative · avg rating 3.09★ · **TB:** 21 reviews, **K-9:** 2 reviews
- "not spam button absent need entering pass for multi account when switching to mobile from desktop refresh is slow"
- Devices: sapphiren (1), GX4 (1), Google Pixel 7 (1) · Languages: French, German, English
- 3-month trend: 0 → 10 → 12 negative mentions 🔴 Accelerating

**3. Crashes & Freezes**
- 11 mentions · 9 negative · avg rating 2.00★ · **TB:** 9 reviews, **K-9:** 2 reviews
- "The app has begun crashing constantly. It crashes on opening the app. I did an update uninstall/reinstall, And It is still crashing. I have no access to any of…"
- Devices: OnePlus (2), t1lte (1), ASUS_Z01KDA (1) · Languages: English, Spanish, German
- 3-month trend: 0 → 6 → 9 negative mentions 🔴 Accelerating

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Fix Push / Notification Sync:** 37 negative mentions · 2.73★ avg · 23→31→37 (accelerating) · highest-volume, lowest-rated theme — biggest per-fix rating impact
- **Stabilize K-9 post-update:** K-9 dropped to 2.96★ (-0.56) · v17/v18 regression cluster · 33×1★ but also 33×5★ — loyal base is recoverable if regressions ship fast
- **Address Spam Filter gap:** 12 negative · 0→10→12 (new and accelerating) · not on the Android roadmap — users have no visibility into whether this is planned. Consider a public position or reply template so the team isn't fielding it ad hoc.

---
## Desktop

### SUMO Forum
- **Overall solved rate:** 64% (-3 pts MoM) · 733 questions · Send/Receive dominates (191 questions, 26%); auth/OAuth fragility is the largest cross-cutting theme — see Recommended Priorities below.

### Top Trending Topics
*All April SUMO questions (733, all locales), rolled up from SUMO tags. Full table: [april_sumo_trending.md](april_sumo_trending.md) · [CSV](april_sumo_trending.csv).*

| Rank | Topic | Count | % |
|-----:|-------|------:|--:|
| 1 | Send/Receive issues | 191 | 26.1% |
| 2 | General messaging (broad SUMO tag) | 99 | 13.5% |
| 3 | Customization & UI | 82 | 11.2% |
| 4 | Import / Migration / Profiles | 58 | 7.9% |
| 5 | Sign-in & Passwords | 56 | 7.6% |
| 6 | Account setup & management | 46 | 6.3% |
| 7 | Install & Update | 36 | 4.9% |
| 8 | Spam & Junk mail | 30 | 4.1% |
| 9 | Crashes & Performance | 26 | 3.5% |
| 10 | Calendar & Events | 25 | 3.4% |

### Recommended Priorities — Community Signal
Three themes drawn from the April SUMO corpus. Full drill-down with question links: [april_desktop_priorities.md](april_desktop_priorities.md).

**1. Authentication / OAuth fragility** — **121 questions (16.5%)**
The single loudest desktop signal. Heavy concentration on Gmail (14), Outlook (10), Google (7) provider failures. Common patterns: "stopped working after password change," "broke after Thunderbird update," repeated password prompts, connection/server reset, and friction with the new Account Setup Hub (specific reports for @live.de, outlook.com, gmail). Maps to the always-on auth/connectivity layer — the desktop equivalent of mobile's notifications reliability.

**2. Update regressions** — **55 questions (7.5%)**
Visible across UI, send/receive, drag-and-drop, and folder display. Recurring patterns: "no SEND field available after TB update 03/27/26," "View Layout Classic grayed out," "drag and drop no longer works in 150," "Sent items folder disappeared after update to 149.0.2," "composition formatting toolbar has disappeared." Updates are breaking established workflows at scale — a release-process and regression-detection problem more than a feature problem.

**3. Data loss / folder integrity** — **41 questions (5.6%)**
The highest-emotional-charge bucket. Recurring patterns: "Thunderbird wiped out all my folders," "subfolders disappeared," "Local Folders gone," "Sent items folder disappeared," "Are missing emails recoverable?", "Recover Emails removed by Expunge." High urgency, high trust impact — these are the "I lost everything" tickets.

*Auth ∩ Update overlap: 5 questions — auth that breaks specifically after an update. Small in count, large in narrative.*

### Community Wishlist — Mozilla Connect
*20 Thunderbird-labeled ideas posted in April (57 kudos · 3,875 views · all status `new`). Connect is the ideation channel: SUMO tells us what's broken, Connect tells us what users want. Full table: [april_connect_ideas.md](april_connect_ideas.md) · [CSV](april_connect_ideas.csv).*

| Kudos | Views | Status | Idea |
|------:|------:|--------|------|
| 10 | 379 | new | [Streamline New Email Notifications](https://connect.mozilla.org/t5/ideas/streamline-new-email-notifications/idi-p/122954) |
| 8 | 399 | new | [Warning when sending from the wrong account (multi-account)](https://connect.mozilla.org/t5/ideas/feature-request-warning-when-sending-from-the-wrong-account/idi-p/122426) |
| 6 | 177 | new | [Right-click → show all messages from this sender / domain](https://connect.mozilla.org/t5/ideas/right-click-gt-gt-gt-show-all-messages-from-this-sender-or/idi-p/123327) |
| 4 | 219 | new | [Restore Find Bar Match Count (regression)](https://connect.mozilla.org/t5/ideas/request-for-restoration-of-find-bar-match-count-functional/idi-p/122349) |
| 4 | 226 | new | [Bring Firefox VPN to Thunderbird (Win / Android / iOS)](https://connect.mozilla.org/t5/ideas/bring-firefox-vpn-functionality-to-thunderbird-for-windows/idi-p/121808) |

---
## Data Access
- Dashboard: [april.html](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/april.html)
- Support metrics export (CSV): [april.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/april.csv)
- Play Store raw data: monthly CSV exports from Google Play Console — TB Android, TB Beta, and K-9 Mail (separate CSV per app, not checked in)
- Desktop SUMO trending topics: [april_sumo_trending.md](april_sumo_trending.md) · [CSV](april_sumo_trending.csv)
- Desktop community-driven priorities (drill-down): [april_desktop_priorities.md](april_desktop_priorities.md)
- Mozilla Connect Thunderbird ideas: [april_connect_ideas.md](april_connect_ideas.md) · [CSV](april_connect_ideas.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
