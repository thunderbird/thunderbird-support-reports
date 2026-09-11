# August 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html)**

> July full dashboard skipped; MoM uses Lisa's 8/31 KPI baseline.

Donor tickets jumped 212→350 (+65%) because extra donation appeals ran during the ESR period — the 8/31 spoiler was ~95% — while overall volume eased 767→755 (−1.6%). CSAT held at 90.9% (−0.8 vs July); Donor hit 92.7% (+7.0). Thundermail 85.7% (−9.8) is pricing DSATs (no monthly / no à la carte / 100 CAD), not support — adjusted support satisfaction 100%. TB Play Store recovered to 3.74★ (+0.16); push/sync is still #1 friction (34 negative, rising).

---
## Support Metrics
- **Overall CSAT:** 90.9% (-0.8 pts MoM) ↓
- **CSAT — Donor Support:** 92.7% (+7.0 pts MoM) ↑
- **CSAT — Thundermail:** 85.7%*
- **Volume:** 755 tickets (-1.6% MoM) — Donor Support 350, Thundermail 187, App Store Reviews 218

*DSATs: no monthly plan, no à la carte, price too high (100 CAD). Support satisfaction excluding those: 100%.*

---
## Desktop ESR — donors and forum in one place

> **[→ ESR tab on the dashboard](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#esr)**

- **Donor volume during the ESR period:** 350 tickets, up from 212 (+65%) · CSAT 92.7% (+7.0 pts). More donation appeals ran during ESR, so more donors were asked to give and more donation-support questions arrived. The 8/31 note previewed roughly 95% growth; the closed month landed at +65%.
- **Labeling caveat:** 350 is donor-brand ticket volume, not ESR-product tickets — the tickets themselves are not about ESR. There is also no ESR-tagged SUMO figure — Roland tags a Thunderbird major version (153, 154) with no channel column, so the forum numbers below are desktop-build signals rather than a measured ESR slice.
- **Build regressions (one-off, arrive and leave with a release):** printing blank pages on 154 — 36 questions at 8.0× baseline, 37% resolved, **fixed in Thunderbird 155 on Sept 1** ([Bugzilla 2065922](https://bugzilla.mozilla.org/show_bug.cgi?id=2065922)); Compose Send button and toolbar missing after 153 — 8 → 28 questions, 89% resolved ([Bugzilla 1989214](https://bugzilla.mozilla.org/show_bug.cgi?id=1989214)); drag-and-drop to the file system broken after 153 — 1 → 16, 56% resolved.
- **Standing, not ESR:** Spectrum / Charter / Roadrunner — 34 questions, 3.2× baseline, 31 of the 34 lost mail access. Provider-side, and Roland notes it recurs a few times a year. Yahoo / AT&T / AOL app-specific passwords (29% resolved) and repeated password prompts (42% unanswered) are KB gaps that do not move with the ESR version.
- **Support owns:** printing macro and KB update (155 shipped, so every remaining report has the same answer), a standing Spectrum article refreshed at each recurrence, and an app-specific-password KB. **Engineering owns:** the Send button, drag-and-drop, and recurring v153 POP retrieval spikes.
- Desktop only — Android reviews, K-9 forum, and Thundermail are a different codebase and release channel.

---
## Community Support

### Desktop Forum
- **Overall solved rate:** 58% (-6 pts MoM) · 955 questions (751 in July) · two headline clusters, and both of Roland's methods name the same pair
- **Printing broke in 154:** 36 tagged questions at 8.0× normal, peaking 24.3× on Aug 20. Only 37% resolved while it was unfixed. **Fixed in Thunderbird 155, released Sept 1** ([Bugzilla 2065922](https://bugzilla.mozilla.org/show_bug.cgi?id=2065922)) — users still reporting it are on 154.
- **Spectrum / Charter / Roadrunner:** 34 questions (3 in July), 3.2× baseline, weekly peak 11.0× in the week of Aug 17. 31 of the 34 lost mail access entirely. Provider-side, not a Thunderbird build issue — and Roland notes Spectrum has issues a few times a year, so this is recurring rather than new.
- **Also up:** Yahoo 55 questions (+83%), Microsoft 53 (+47%), POP 46 with recurring v153 daily spikes, attachments drag-and-drop broken after 153 (1 → 16).
- **Where the solved rate went:** Yahoo/AT&T/AOL app-specific passwords 29% resolved (worst of the month), printing 37%, repeated password prompts 42% (42% got no reply at all), blank message body 47%. Two of those are KB gaps we can close ourselves.
- Desktop only — printing and Spectrum do not appear in Play Store reviews or the Android app backlog.
- Sources: [August spikes, non-AI](https://thunderbird.github.io/thunderbird-metrics-and-reports/PROJECT1/REPORTS/desktop/exec-summary-latest.html) · [LLM insights, engineering](https://thunderbird.github.io/thunderbird-metrics-and-reports/LLM_INSIGHTS/REPORTS/desktop/monthly-summary-latest.html)

### Android Forum
- **Overall solved rate:** 61% (+1 pts MoM) · 51 questions (55 in July) · ignored 27%
- **Non-AI report is quiet because volume is too low, not because nothing happened.** Zero spikes cleared the threshold: the detectors need 8 questions of one kind in a month and Roland's 40-question August corpus averaged about one a day. Only 2% of Android questions record a Thunderbird version, so the version-and-cause detector cannot fire at all — that zero is missing data.
- **Five new clusters, two questions each:** stored password reverts or cannot be updated (sev 4.0), crash when opening a downloaded email (sev 4.0), AOL/Yahoo login loop then mail stops arriving (sev 3.5), contact autocomplete not suggesting addresses (sev 2.0, **50% resolved — the only cluster support could not answer**), no OpenPGP/S-MIME on Android (sev 3.0). Imported account showing only an Outbox grew 1 → 3.
- **Read as a list, not a trend:** 40 questions across 33 clusters means a change of one question is noise, and "new this month" can mean only that nobody worded it that way in July.
- **Cross-channel:** the three credential/import clusters look like one shared credential or migration path, and they plus crash-on-open also appear in Play Store reviews and K-9 forum topics — same app (K-9 is Thunderbird for Android), three entry points, small n on each. See [Cross-channel overlap](#cross-channel-overlap--strongest-signals).
- **One channel only:** spam sits at 18 negative Play Store mentions with zero Android forum questions and zero K-9 forum topics — those users rate and leave rather than ask. Encryption asks appear on the forum but not in reviews.
- Sources: [August spikes, non-AI](https://thunderbird.github.io/thunderbird-metrics-and-reports/PROJECT1/REPORTS/android/exec-summary-latest.html) · [LLM insights, engineering](https://thunderbird.github.io/thunderbird-metrics-and-reports/LLM_INSIGHTS/REPORTS/android/monthly-summary-latest.html)

*Question counts differ by corpus: the SUMO KPI export holds 955 desktop / 51 Android; Roland's spike detector and AI read cover 941 / 940 desktop and 40 Android. Same month, different corpus filters — percentages are quoted against their own source.*

---
## Android Reviews
- **Engagement:** 218 incoming Play Store review tickets (down from 272 in July)
- **Impact:** Improved / unchanged / decreased not available this month — July had no full Play Store export to pair by Review Link. Average monthly rating — TB 3.74★ (+0.16 from July ↑) · K-9 3.60★ (-0.04 from July ↓) · Combined 3.71★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** 564 total reviews — TB 456 (415 stable + 41 beta), K-9 108. 27 languages.

*Methodology: June onward uses Play Console GCS exports (Jan–May were manual UI downloads). August vs July is GCS-to-GCS; July averages come from Lisa's 8/31 KPI snapshot, not a full July dashboard.*

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

### Cross-channel overlap — strongest signals
*K-9 is Thunderbird for Android (same codebase), so Play Store reviews (TB + K-9), the Android SUMO forum, and the K-9 Discourse forum are three entry points to one product. A signal on more than one channel outranks a bigger number on one. Desktop forum signals are never compared here.*

| Signal | Play Store (TB+K-9) | Android SUMO | K-9 forum | Overlap read |
|---|---|---|---|---|
| Push / notification sync | 34 neg · 51 mentions | — | 5 topics · 2→1→5 | **Strongest — two of three channels.** Biggest review theme and top K-9 forum theme; sync/fetch adds 2 more forum topics. No SUMO cluster, where 51 questions is too small to expect one. |
| Account credentials & setup import | 5 mentions · 3 neg (25→3) | 7 questions · 3 clusters | 3 topics · 5→5→3 | **All three channels — same gap, different entry point.** Small n on each. |
| Crash on open | 5 mentions · 4 neg · 2.00★ | 2 questions · sev 4.0 | 2 topics · 2→0→2 | **All three channels, n too small to rank.** Consistent shape, not a measured trend. |
| Stuck outbox / send path | 5 mentions · all 1–3★ | 3 questions | — | **Two channels, read cautiously** — the SUMO cluster is an import artifact (imported account shows only an Outbox), not a confirmed send failure. |

- **Play Store only (absence is the signal):** spam filter absent — 18 negative of 35 mentions, zero Android SUMO questions, zero K-9 forum topics.
- **Forum only:** OpenPGP/S-MIME encryption (2 SUMO questions); attachments (3 K-9 topics).
- Counts come from different systems and are compared side by side, never summed.

### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
- **Push / Notification Sync — still #1, still rising:** 34 negative (31→34) · 51 mentions · avg 2.76★ · 3-mo 20→31→34 · no product fix in market
- **Spam Filter Absent — #2, fewer mentions:** 18 negative (22→18) · still no junk-filter build · July QR spike (25 neg) cooled to 3 — not a current 4★ lever
- **Rating gap:** TB 3.74★ needs +0.26★ to 4★ (K-9 3.60★, −0.04). Converting push 1–3★ reviewers is still the primary path

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound

**🕊 Receive**
- 755 Zendesk tickets (−1.6% vs July) — Donor 350 (+65%, ESR-period donation appeals), Thundermail 187 (−34%), App Store Reviews 218 (−20%)
- 564 Play Store reviews across 27 languages; 218 incoming review tickets
- Push/sync still #1 friction (34 negative, 31→34 — rising, no fix shipped). July QR/Settings Import spike cooled (25→3 negative)
- 955 desktop forum questions (751 in July) — printing broke in 154 (36 qs, 8× normal) and Spectrum/Charter mail access failed (34 qs)

**🪽 Resolve**
- Donor CSAT 92.7% (+7.0 pts) through the donation-appeal spike
- Thundermail CSAT 85.7% is product/pricing DSATs; support satisfaction excluding those 100%
- Android forum solved rate 61% (+1 pt) on 51 questions
- Desktop printing regression is fixed in Thunderbird 155 (Sept 1) — the one August desktop cluster where we have an answer to give

**✨ Resound**
- **48% of TB reviews are 5★** (220 of 456) — TB monthly average 3.74★ (+0.16 vs July)
- July QR/Settings Import spike (25 neg, mostly 1★) dropped to 3 negative
- Spam-filter negative mentions 22→18 — fewer mentions, not a shipped junk filter
- Thundermail **Webmail** and **MFA** show as Landed on the ideas board

*Receive / Resolve / Resound is Thunderbird Support's CX action framework. [Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## What's Coming Up

[Lisa fills — experiments, iterations, what's launching next.]

*Parked idea, not scoped: watch Zendesk volume against Roland's SUMO keyword spikes to see whether desktop provider and regression clusters show up in tickets first.*

---
## Data Access
Dashboard: [august.html](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html)
Raw data (CSV): [august.csv](https://github.com/thunderbird/thunderbird-support-reports/blob/main/reports/monthly/2026/august.csv)

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Resolved (Roland's AI read)** — a question counts as resolved when it has an accepted solution or a trusted contributor gave the last answer. Stricter than the SUMO solved rate above, so the two figures are not interchangeable.

**Monthly rise (Roland's spike detector)** — the month's count for one cause tag divided by the normal count for that tag. A rise of 3.0× means three times as many questions as usual. Spike dates are when users posted, not when the problem began.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
