# March 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/march.html)**

March closed with our strongest CSAT score yet (75%), a meaningful drop in ticket volume (-27% MoM), and a milestone jump in Android community support (solved rate up 19 points to 72%). The news isn't all positive: Play Store ratings continued their Q1 slide, push/notification sync complaints accelerated for the third consecutive month, and two new friction signals—spam filtering and crashes—entered the top issues list for the first time. With K-9 now fully integrated into our dataset, we have a clearer picture of where codebase-level issues are landing across both apps.

---
## Support Metrics
- **Overall CSAT:** 75.0% (+6.0 pts MoM) ↑
- **CSAT — Donor Support:** 69.0% (+5.7 pts MoM) ↑
- **CSAT — TB Pro:** 100.0% ✅
- **Volume:** 267 tickets (-27.0% MoM) — Donor Support 246, TB Pro 21

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 67% (-1 pt MoM) · 931 real questions (960 minus 29 spam) · 29 trusted contributors · 97.4% of answers from trusted contributors or question creators
- **Yahoo/AOL/AT&T OAuth2:** 55 questions (+37.5% MoM) — Yahoo's change broke Thunderbird versions older than 148, forcing users to upgrade. Expected signal; users confused by the OAuth2 login flow and browser redirect behavior.
- **GMX server incident:** 7 questions (+250% MoM) — GMX had a server outage that generated a spike. Not a Thunderbird issue; resolved when GMX fixed their infrastructure.
- **Gmail/Google:** 69 questions (+23.2% MoM) — Highest-volume provider. Mix of POP3 issues, certificate errors, antivirus conflicts, and folder repair. POP3 problems appearing more than expected given most users are on IMAP.
- **Recurring theme:** Lack of in-app troubleshooting tools (opt-in telemetry, crash logs, etc.) makes it hard for volunteers and staff to diagnose issues. Desktop has ☰ > Help > Troubleshooting Information but it's limited.

### Android Forum
- **Overall solved rate:** 72% (+19 pts MoM) · 54 real questions (66 minus 12 spam) · 91.3% of answers from trusted contributors (platform34, wsmwk, Yu5tiqX9og)
- **Crash on v17.0:** App crashes reliably on Android 8 when fetching or displaying image emails (affects ~80% of image emails). Works on Android 12+. Confirmed known issue; contributors directed users to older F-Droid build as workaround. Fix expected in 17.1 or v18.
- **Filters like Desktop:** 3 questions requesting message filtering rules equivalent to Thunderbird Desktop. Consistent ask.
- **Desktop parity — other:** Font size control removed in the UI revamp and users want it back · unified folders beyond inbox · scheduled send.
- **Recurring theme:** No equivalent of Desktop's Troubleshooting Information on Android makes diagnosis harder. SUMO is also hard to use on mobile, keeping question volume low.

---
## Android Reviews
- **Engagement:** 215 replies to 1-3 star reviews (up from 141 in February)
- **Impact:** 9 improved ratings, 4 unchanged, 1 decreased. Average monthly rating 3.81 stars (down from 3.91 in February, TB-only). ⚠️ Rating has drifted -0.14 across Q1 (3.95 → 3.91 → 3.81) — moving away from our 4★+ annual goal.
- **Volume:** 451 total reviews — TB 374, K-9 77. 31 languages.

### Top 3 Friction Points
*Sourced from 451 Play Store reviews (TB + K-9, same codebase). Analyzed with AI.*

**1. Push notifications unreliable**
- 46 mentions · 31 negative · avg rating 2.83★ · **TB:** 37 reviews, **K-9:** 9 reviews
- Users report no alerts even after correct setup; background sync silently stops and manual refresh is required. Several confirm the push toggle reverts on its own after being enabled.
- The 15-min poll interval is indistinguishable from a bug — users report both identically and rate them the same
- Devices: Samsung S25 Ultra, Samsung A12s, OnePlus · Languages: EN, DE, IT, PT, FR
- 3-month trend: 19 → 23 → 31 negative mentions across Q1 🔴 Accelerating

**2. Spam filter absent**
- 13 mentions · 10 negative · avg rating 2.69★ · **TB:** 12 reviews, **K-9:** 1 review
- Desktop TB users transitioning to mobile and expecting spam filtering to carry over; several note they can't view spam folder contents — only empty it. Multiple reviews cite this as reason to uninstall.
- Languages: EN, DE · almost entirely TB-specific
- 3-month trend: 0 → 0 → 10 negative mentions 🆕 New signal

**3. Crashes on v17.0**
- 9 mentions · 6 negative · avg rating 2.56★ · **TB:** 5 reviews, **K-9:** 4 reviews
- Clean regression spike coinciding with v17.0. One K-9 reviewer explicitly names v17.0 and notes there is no way to send a crash log — users can't submit diagnostics. K-9 is disproportionately represented at 44% of crash mentions.
- Devices: Huawei (HWWAS-H), Samsung Galaxy A5, OnePlus · Languages: EN, DE, NL
- 3-month trend: 0 → 0 → 6 negative mentions 🆕 Release-linked spike

### K-9 Churn Watch
- **v17.0 crashes:** K-9 accounts for 4 of 9 crash mentions despite being 17% of review volume · Huawei device confirmed (HWWAS-H) · no crash log path means users can't submit diagnostics
- **Push failure:** 9 of 46 push mentions are K-9 · S25 Ultra reported
- **Switching away:** 0 explicit mentions detected
- **Long-term user sentiment:** 4 reviews (2 Croatian, 1 Slovak, 1 English) describe years of desktop TB use followed by mobile disappointment — two cite "decades" on desktop, one cites 20 years; all 1–2 star, all push or sync failures
- **Rating gap:** K-9 avg 3.52★ vs TB 3.87★ — 0.35 gap persistent; calendar and push failures land disproportionately in K-9 reviews

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Fix push notifications:** the single biggest driver of 1-star reviews, worsening throughout Q1 (19 → 23 → 31 negative mentions) · the 15-min poll floor needs to be addressed and push reliability improved — this will keep pulling the rating down until it is
- **Address the spam filter gap:** new signal in March but 10 negative mentions immediately · desktop users expect feature parity · confirmed uninstalls · avg 2.69★ among complainants
- **Stabilize K-9 post-v17.0:** 4 of 9 crash mentions are K-9 despite 17% of review volume · no crash log path means diagnostic dead-end for users · Huawei devices flagged

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound

**🕊 Receive**
- 246 donor tickets handled. Top topic: misdirected TB app tech support (52 tickets, 21% of volume) — donors writing in because they donated and assumed it came with a support channel. We showed up anyway.

**🪽 Resolve**
- Donor CSAT 69% (+5.7 pts MoM) — consistent upward trend.
- Email/contact updates resolved cleanly: 100% satisfaction on 8 tickets.
- Fundraising opt-out requests (19 tickets) sitting at 33% satisfaction on a 16% response rate — worth watching as the April appeal ramps up. Donors asking not to be contacted who leave with an unsatisfying experience are a retention and reputation risk.
- Recurring cancellations: 50% satisfaction, equal positives and negatives. Donors choosing to leave deserve a frictionless exit.

**✨ Resound**
- Refunds and receipts handled with care: 67% satisfaction on both, response rates low but positive skew.
- Misdirected tech support: we are continuing our experiment offering light technical support to verified donors. More data in April.

*Receive / Resolve / Resound is Thunderbird Support's CX action framework. [Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## Experiments & Iterations

**CSAT survey redesign — live April 1**

We overhauled the post-ticket CSAT survey. The old 1–5 scale had 3 negative ratings and only 2 positive ones — the math was stacked against us before a single response came in. The new version asks one direct question: "Did you get the help you needed?" (yes/no). Negative responses trigger a short follow-up dropdown to capture the reason.

Now live in 8 languages: EN, DE, FR, ES, IT, NL, DA, JP — Danish and Spanish are new additions. Timed ahead of Spring Appeal to get cleaner data during our highest-volume period. April will be the first full month on the new survey; we'll report before/after in the April report.

---
## Data Access
Full MoM spreadsheet: internal "Support Metrics MoM 2026" Google Sheet (access-controlled, Thunderbird staff only)
Dashboard: [march.html](https://thunderbird.github.io/thunderbird-support-reports/lisa/2026/march.html)
Raw data (CSV): [march.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/march.csv)

---
## Definitions
**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
