# August 2026 — Monthly Support Report

> **[→ View dashboard](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html)** — every table, per-cluster breakdown, and methodology note lives there.

> July's full dashboard was skipped; all MoM comparisons use Lisa's 8/31 KPI note as the July baseline.

Volume eased to 755 tickets (−1.6%) while donor tickets jumped 212 → 350 (+65%) — extra donation appeals ran during the ESR window, so more donors were asked to give. CSAT held at 90.9%. Push/sync is still the #1 Play Store friction at 34 negative mentions and rising, and August engineering shipped nothing that targets it.

---
## Support Metrics
- **Overall CSAT:** 90.9% (−0.8 pts MoM) ↓
- **CSAT — Donor Support:** 92.7% (+7.0 pts MoM) ↑
- **CSAT — Thundermail:** 85.7% (−9.8 pts MoM)*
- **Volume:** 755 tickets (−1.6% MoM) — Donor Support 350, Thundermail 187, App Store Reviews 218

*Every Thundermail DSAT was about pricing — no monthly plan, no à la carte, 100 CAD too high. Satisfaction with support itself: 100%.*

---
## Desktop ESR
> **[→ ESR tab](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#esr)** — cluster table, Bugzilla links, and who owns each fix.

- **Donor 350 tickets (+65%), CSAT 92.7% (+7.0).** The lift is donation appeals that ran during the ESR window, **not** tickets about ESR — 350 is donor-brand volume, and no ESR-tagged forum figure exists to compare it against.
- **Printing broke in 154 and is fixed in Thunderbird 155, released Sept 1** ([Bugzilla 2065922](https://bugzilla.mozilla.org/show_bug.cgi?id=2065922)). Anyone still reporting it is on 154, so every remaining ticket has the same answer.
- **Spectrum / Charter is a recurrence, not an ESR regression** — 34 questions, and 31 of those users lost mail access entirely. Provider-side, and it comes back a few times a year, so we keep a standing article rather than writing a new one.
- Desktop only — Android and Thundermail are a different codebase and release channel.

---
## Community Support

### Desktop Forum
> **[→ Desktop forum tab](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#sumo-desktop)** — full cluster table, spike math, and both of Roland's sources.

- **Overall solved rate:** 58% (−6 pts MoM) · 955 questions (751 in July)
- Two clusters carried the month: printing on 154 (36 questions, 8× the usual rate, now fixed in 155) and Spectrum/Charter mail access (34 questions). Yahoo, Microsoft, and POP setup questions rose behind them.
- The solved rate fell where we have KB gaps, not where the build broke — app-specific passwords and repeated password prompts are ours to close.

### Android Forum
> **[→ Android forum tab](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#sumo-android)** · **[→ K-9 forum](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#k9-forum)**

- **Overall solved rate:** 61% (+1 pt MoM) · 51 questions · ignored 27%
- **Quiet because volume is too low, not because the month was calm.** Roland's detectors need 8 questions of one kind before they fire, and August averaged about one Android question a day — zero spikes is missing signal, not good news.
- Five new clusters at two questions each: credentials, crash on open, login loop, contact autocomplete, encryption. Read them as a list — at this size a change of one question is noise.

**Cross-channel:** push/sync and credential/import pain show up in Play Store reviews, the Android forum, and the K-9 forum — one app, three entry points. Spam appears in reviews only, which is its own signal: those users rate and leave rather than ask. **[→ Overlap table](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#overlap)**

---
## Android Reviews
> **[→ Android tab](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#android)** — star distributions, devices, languages, and the K-9 churn watch.

- **Engagement:** 218 incoming Play Store review tickets (down from 272 in July)
- **Impact:** 0 improved · 0 unchanged · 1 decreased — only one review was active in both months. Average monthly rating: TB 3.74★ (+0.16 ↑) · K-9 3.60★ (−0.04 ↓) · Combined 3.71★
- **Volume:** 564 total reviews — TB 456 (415 stable + 41 beta), K-9 108. 27 languages.

*Methodology: June onward uses Play Console GCS exports; July's headline averages come from the 8/31 KPI snapshot because no July dashboard was produced.*

### Top 3 Friction Points
*Sourced from 564 Play Store reviews (TB + Beta + K-9, same codebase). Analyzed with AI. Devices, languages, and quotes on the [friction table](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#android).*

1. **Push / Notification Sync** — 34 negative of 51 mentions · avg 2.76★ · 3-month trend 20 → 31 → 34 🔴 rising. Delayed or missing notifications; sync often needs a manual refresh.
2. **Spam Filter Absent** — 18 negative of 35 mentions · avg 3.26★ · 3-month trend 13 → 22 → 18 📉 fewer mentions, but no junk filter has shipped.
3. **Stuck Outbox / Send Failure** — 5 negative of 5 mentions · avg 1.20★. Small n; read it as send-path pain, not a measured trend.

July's QR / Settings Import spike cooled from 25 negative mentions to 3.

### Meeting Our ⭐⭐⭐⭐+ Goal
- **Push is the lever.** 34 negative and rising, no fix in market. TB needs +0.26★ to reach 4★, and converting push 1–3★ reviewers is the shortest path there.
- **August engineering shipped QR feedback and a narrow camera-crash fix — nothing aimed at push, spam, or outbox.** [→ Engineering priority alignment](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#eng-priority-alignment)
- Spam holds at #2 with no junk filter built; QR is no longer a 4★ lever.

---
## 🕊 Receive / 🪽 Resolve / ✨ Resound
> **[→ Full panel](https://thunderbird.github.io/thunderbird-support-reports/reports/monthly/2026/august.html#rrr)**

**🕊 Receive** — 755 Zendesk tickets (Donor 350, Thundermail 187, App Store Reviews 218) · 564 Play Store reviews across 27 languages · 955 desktop forum questions.

**🪽 Resolve** — Donor CSAT 92.7% (+7.0 pts) through the appeal spike · Thundermail's dip is pricing, with support satisfaction at 100% · desktop printing finally has a shipped answer in 155.

**✨ Resound** — 48% of TB reviews are 5★ (220 of 456) and TB recovered to 3.74★ · QR negatives fell 25 → 3 · Thundermail **Webmail** and **MFA** both show as Landed on the ideas board.

*Receive / Resolve / Resound is Thunderbird Support's CX action framework. [Support Vision →](https://www.notion.so/mzthunderbird/Support-Vision-2392df5d45ae80b89e28fa02db27cd77)*

---
## What's Coming Up

**AI support, in progress — not in front of customers yet.**

- **Reps stay on the customer.** Conversation, judgment, and tone stay human.
- **AI takes the research layer:** lookup, context, and the background a rep needs before they reply.
- **Thunderbolt is the notable piece:** it will use confidential compute for that research layer — privacy-preserving compute, so ticket context stays protected while AI does the lookup. Working with the Thunderbolt team.

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

**Monthly rise (Roland's spike detector)** — the month's count for one cause tag divided by the normal count for that tag. A rise of 8× means eight times as many questions as usual.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
