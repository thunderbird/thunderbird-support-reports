#!/usr/bin/env python3
"""TB Pro weekly executive summary.

Covers Mon 00:00 ET through Sun 23:59 ET of the completed week ending on
the most recent Sunday on or before --week-end (default: today). Running on
Friday covers Mon–Sun of the prior week, so weekend tickets are never lost.

Core question: "Is anything blocking the next wave of TB Pro invites?"

Output:
  reports/tbpro/weekly/YYYY-MM-DD.md    (filename = Sunday date)
  reports/tbpro/weekly/YYYY-MM-DD.html
  reports/tbpro/LATEST_WEEKLY.md
  reports/tbpro/LATEST_WEEKLY.html

Usage:
  python3 scripts/tbpro_weekly.py                       # prior completed week
  python3 scripts/tbpro_weekly.py --week-end 2026-05-18
  python3 scripts/tbpro_weekly.py --public --out-dir reports/tbpro/weekly
"""
import argparse
import datetime as dt
import html as _html
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

# Import helpers from tbpro_daily (safe: guarded by if __name__ == "__main__")
sys.path.insert(0, str(Path(__file__).parent))
import tbpro_daily as daily

ET  = daily.ET
UTC = daily.UTC

# ── Blocker / watch thresholds ────────────────────────────────────────────────
CSAT_BLOCK_PCT         = 70    # Hard BLOCK if CSAT falls below this
CSAT_WATCH_PCT         = 80    # WATCH if below this (but above BLOCK)
MIN_CSAT_SAMPLE        = 5     # Ignore CSAT verdict if fewer than this many responses
ESCALATION_BLOCK       = 3     # ≥ this many unresolved escalations = BLOCK
ESCALATION_WATCH       = 1     # ≥ 1 unresolved escalation = WATCH
OPEN_INCIDENTS_BLOCK   = 3     # ≥ open incidents on one known problem = BLOCK
OPEN_INCIDENTS_WATCH   = 2     # ≥ 2 = WATCH
REFUND_WATCH_PCT       = 8.0   # Refunds > this % of real subscriber tickets = WATCH
VOLUME_SURGE_WATCH     = 150   # TB Pro week volume > this % of prior week = WATCH
OTHER_BRAND_SURGE_PCT  = 40    # Other-brand open/new tickets > this % above prior week = WATCH
OTHER_BRAND_MIN_OPEN   = 15    # Minimum count before the other-brand signal fires

# ── Theme rollup for executive summary ────────────────────────────────────────
# Fine-grained daily themes → coarser weekly labels.
# All login-attempt sub-themes (SUMO redirect, email lookup, allowlist) are the
# same root cause: someone not on the allowlist tried to log in.
WEEKLY_THEME_ROLLUP = {
    "Login attempt — not on the allowlist yet":          "Not on allowlist yet",
    "Login attempt — wrong product, redirected to SUMO": "Not on allowlist yet",
    "Login attempt — email lookup required":             "Not on allowlist yet",
    "Login attempt — Account Hub login trouble triage":  "Not on allowlist yet",
    "Custom domain DNS":                                 "Custom domain / DKIM / DNS",
}


# ── Date helpers ──────────────────────────────────────────────────────────────

def week_bounds(anchor: dt.date):
    """Return (week_start, week_end, window_start_utc, window_end_utc).

    week_start is the Monday of anchor's ISO week, floored at LAUNCH_DATE
    so the first weekly always starts from when the flight launched,
    not from the prior Monday.
    """
    week_start_monday = anchor - dt.timedelta(days=anchor.weekday())  # Mon=0
    launch = dt.date.fromisoformat(daily.LAUNCH_DATE)
    week_start = max(week_start_monday, launch)
    start_utc = dt.datetime.combine(week_start, dt.time(0, 0, 0),   tzinfo=ET).astimezone(UTC)
    end_utc   = dt.datetime.combine(anchor,     dt.time(23, 59, 59), tzinfo=ET).astimezone(UTC)
    return week_start, anchor, start_utc, end_utc


# ── Blocker assessment ────────────────────────────────────────────────────────

def assess_blockers(week_tickets, prior_tickets, csat_pct, csat_n,
                    refunds_week, incidents_by_problem, problems,
                    other_open_week=0, other_open_prior=0,
                    gh_linked_open=None):
    """Return (verdict, blockers, cautions).

    verdict:  'CLEAR' | 'WATCH' | 'BLOCK'
    blockers: list of str — hard-stop signals
    cautions: list of str — watch signals
    """
    blockers = []
    cautions = []

    # 1. CSAT
    if csat_n >= MIN_CSAT_SAMPLE and csat_pct is not None:
        if csat_pct < CSAT_BLOCK_PCT:
            blockers.append(
                f"CSAT {csat_pct:.0f}% ({csat_n} responses) — below {CSAT_BLOCK_PCT}% threshold"
            )
        elif csat_pct < CSAT_WATCH_PCT:
            cautions.append(
                f"CSAT {csat_pct:.0f}% ({csat_n} responses) — below {CSAT_WATCH_PCT}% watch threshold"
            )

    # 2. Unresolved escalations this week
    escalated_open = [
        t for t in week_tickets
        if "how_escalated" in (t.get("tags") or [])
        and t.get("status") not in ("solved", "closed")
    ]
    if len(escalated_open) >= ESCALATION_BLOCK:
        blockers.append(f"{len(escalated_open)} unresolved escalated tickets this week")
    elif len(escalated_open) >= ESCALATION_WATCH:
        cautions.append(f"{len(escalated_open)} unresolved escalated ticket(s) this week")

    # 3. Known problems with open reports (regardless of when created)
    for pid, incidents in incidents_by_problem.items():
        open_inc = [i for i in incidents if i.get("status") not in ("solved", "closed")]
        if not open_inc:
            continue
        prob = problems.get(pid, {})
        prob_resolved = prob.get("status", "open") in ("solved", "closed")
        subj  = _trunc((prob.get("subject") or f"problem #{pid}").strip(), 80)
        n     = len(open_inc)
        n_all = len(incidents)
        count_str = (
            f"{n_all} linked report{'s' if n_all != 1 else ''} ({n} open)"
            if n < n_all else
            f"{n} open report{'s' if n != 1 else ''}"
        )
        suffix = " — bug fixed, remediation in progress" if prob_resolved else ""
        msg = f"1 known problem with {count_str} — \"{subj}\"{suffix}"
        # Known problems are always WATCH (never auto-BLOCK) — Lisa flags blockers manually
        if n >= OPEN_INCIDENTS_WATCH:
            cautions.append(msg)

    # 4. Refund rate vs real subscriber tickets this week
    real_week = [t for t in week_tickets if not daily.matches_fix_834(t)]
    if real_week:
        refund_pct = 100 * len(refunds_week) / len(real_week)
        if refund_pct > REFUND_WATCH_PCT:
            cautions.append(
                f"Refund/cancel rate {refund_pct:.0f}% of real subscriber tickets"
                f" ({len(refunds_week)} / {len(real_week)})"
            )

    # 5. Volume surge week-over-week
    if prior_tickets:
        wow = 100 * len(week_tickets) / max(1, len(prior_tickets))
        if wow > VOLUME_SURGE_WATCH:
            delta = len(week_tickets) - len(prior_tickets)
            cautions.append(
                f"Volume {len(week_tickets)} tickets this week vs {len(prior_tickets)} prior week"
                f" (+{delta}, +{wow - 100:.0f}% WoW)"
            )

    # 6. Critical-urgency tickets still open
    critical_open = [
        t for t in week_tickets
        if daily.urgency_for(t) == "critical"
        and t.get("status") not in ("solved", "closed")
    ]
    if critical_open:
        cautions.append(f"{len(critical_open)} ticket(s) with user urgency: critical still open")

    # 7. Other-brand open/new ticket volume — high queue = reduced capacity for wave expansion
    if other_open_week >= OTHER_BRAND_MIN_OPEN:
        if other_open_prior > 0:
            surge = (other_open_week / other_open_prior - 1) * 100
            if surge > OTHER_BRAND_SURGE_PCT:
                cautions.append(
                    f"Other-brand queue high: {other_open_week} open/new tickets"
                    f" (+{surge:.0f}% vs prior week) — team capacity may be stretched"
                )
        else:
            cautions.append(
                f"Other-brand queue: {other_open_week} open/new tickets this week"
                f" — team capacity may be stretched"
            )

    # 8. Open tickets linked to GitHub issues — product bugs regardless of volume
    # Skip issues already surfaced in a known-problem signal (avoids duplicate entries)
    known_problem_text = " ".join(
        (p.get("subject") or "").lower()
        for p in problems.values()
    )
    for item in (gh_linked_open or []):
        iss    = item["issue"]
        num    = str(iss.get("number") or "")
        repo   = iss.get("repo") or ""
        ref    = f"{repo}#{num}"
        title  = _trunc(iss.get("title") or ref, 80)
        # Don't emit a separate signal when the same issue is already a known problem
        if num and num in known_problem_text:
            continue
        cautions.append(f"Open bug report linked to {ref}: {title}")

    verdict = "BLOCK" if blockers else ("WATCH" if cautions else "CLEAR")
    return verdict, blockers, cautions


# ── Data assembly ─────────────────────────────────────────────────────────────

def build_weekly(week_end_et: dt.date) -> dict:
    """Pull and aggregate a full week of TB Pro support data."""
    week_start_et, week_end_et, window_start_utc, window_end_utc = week_bounds(week_end_et)
    prior_start_utc = window_start_utc - dt.timedelta(days=7)

    print(
        f"Building Thundermail weekly summary for {week_start_et} → {week_end_et} (ET)…",
        file=sys.stderr,
    )

    # Reuse tbpro_daily.build() — fetches all cumulative data from Zendesk + FeatureOS
    d = daily.build(week_end_et)
    cumulative = d["cumulative"]

    # Slice to the current week and prior week
    week_tickets = [
        t for t in cumulative
        if window_start_utc <= daily.parse_iso(t["created_at"]) < window_end_utc
    ]
    prior_tickets = [
        t for t in cumulative
        if prior_start_utc <= daily.parse_iso(t["created_at"]) < window_start_utc
    ]

    misdirected_week = [t for t in week_tickets if daily.matches_fix_834(t)]
    real_week        = [t for t in week_tickets if not daily.matches_fix_834(t)]

    # Build dynamic rollup: extend static map with any prefix-sharing clusters
    # detected in this week's data (e.g. "X — A" + "X — B" → both become "X")
    def _build_rollup():
        raw_counts: Counter = Counter()
        for t in week_tickets:
            raw, _ = daily.classify_ticket(t)
            raw_counts[raw] += 1
        prefix_groups: dict[str, list[str]] = defaultdict(list)
        for raw in raw_counts:
            if " — " in raw:
                prefix_groups[raw.split(" — ")[0]].append(raw)
        dynamic: dict[str, str] = {}
        for prefix, subs in prefix_groups.items():
            # Only auto-group when 2+ sub-themes AND none already have an explicit rollup
            if len(subs) >= 2 and not any(s in WEEKLY_THEME_ROLLUP for s in subs):
                for sub in subs:
                    dynamic[sub] = prefix
        return {**WEEKLY_THEME_ROLLUP, **dynamic}

    rollup_map = _build_rollup()

    def _rollup(raw_theme: str) -> str:
        return rollup_map.get(raw_theme, raw_theme)

    # Theme breakdown: counter, tickets, and sub-theme counts for drilldown
    theme_counter: Counter = Counter()
    theme_tickets: dict[str, list] = defaultdict(list)
    theme_subs: dict[str, Counter] = defaultdict(Counter)   # rolled → {raw: n}
    for t in week_tickets:
        raw, _ = daily.classify_ticket(t)
        theme  = _rollup(raw)
        theme_counter[theme] += 1
        theme_tickets[theme].append(t)
        if raw != theme:
            theme_subs[theme][raw] += 1

    # Prior-week theme counts for WoW delta in drilldown
    prior_theme_counter: Counter = Counter()
    for t in prior_tickets:
        raw, _ = daily.classify_ticket(t)
        prior_theme_counter[_rollup(raw)] += 1

    # GitHub-linked tickets this week (product bugs — surface regardless of volume)
    gh_links     = d.get("gh_links") or {}
    week_id_map  = {t["id"]: t for t in week_tickets}
    gh_linked_week = []
    seen_issues    = set()
    for tid, issues in gh_links.items():
        if tid not in week_id_map:
            continue
        ticket = week_id_map[tid]
        for iss in issues:
            key = f"{iss.get('repo')}#{iss.get('number')}"
            if key not in seen_issues:
                seen_issues.add(key)
                gh_linked_week.append({"ticket": ticket, "issue": iss})

    gh_linked_open = [
        item for item in gh_linked_week
        if item["ticket"].get("status") not in ("solved", "closed")
    ]

    # CSAT for the week (ratings received, not tickets created)
    good_week = [
        t for t in d["good_cum"]
        if window_start_utc <= daily.parse_iso(t["updated_at"]) < window_end_utc
    ]
    bad_week = [
        t for t in d["bad_cum"]
        if window_start_utc <= daily.parse_iso(t["updated_at"]) < window_end_utc
    ]
    csat_n   = len(good_week) + len(bad_week)
    csat_pct = (100 * len(good_week) / csat_n) if csat_n else None

    # Refunds / cancels this week
    refunds_week = [
        t for t in d["refunds"]
        if window_start_utc <= daily.parse_iso(t["created_at"]) < window_end_utc
    ]

    # Solved this week
    solved_week = [
        t for t in cumulative
        if t.get("status") in ("solved", "closed")
        and window_start_utc <= daily.parse_iso(t.get("updated_at") or "") < window_end_utc
    ]

    # FeatureOS ideas submitted this week
    fos_week = [
        p for p in d["fos_since_launch"]
        if window_start_utc <= daily.parse_iso(p.get("created_at")) < window_end_utc
    ]

    # Daily volume for the sparkline
    daily_vol = Counter()
    for t in week_tickets:
        day = (t.get("created_at") or "")[:10]
        if day:
            daily_vol[day] += 1

    # Other-brand open/new ticket counts (2 API calls each week/prior).
    # Strategy: count all-brand new+open, then subtract TB Pro's open/new from
    # the same window so we don't need Zendesk's -brand: negation syntax.
    week_start_iso  = week_start_et.isoformat()
    week_end_iso    = week_end_et.isoformat()
    prior_start_iso = (window_start_utc - dt.timedelta(days=7)).astimezone(ET).date().isoformat()
    prior_end_iso   = (window_start_utc - dt.timedelta(seconds=1)).astimezone(ET).date().isoformat()

    def _other_open(start_iso, end_iso, tbpro_tickets):
        all_new  = daily.zd_search_count(f"type:ticket status:new  created>={start_iso} created<={end_iso}")
        all_open = daily.zd_search_count(f"type:ticket status:open created>={start_iso} created<={end_iso}")
        tbpro_open_new = sum(1 for t in tbpro_tickets if t.get("status") in ("new", "open"))
        return max(0, all_new + all_open - tbpro_open_new)

    other_open_week  = _other_open(week_start_iso, week_end_iso, week_tickets)
    other_open_prior = _other_open(prior_start_iso, prior_end_iso, prior_tickets)

    # Per-problem incident counts for this week and prior week (new incidents only, for WoW trend)
    week_incidents_by_problem:  dict[int, int] = {}
    prior_incidents_by_problem: dict[int, int] = {}
    for pid, incidents in d["incidents_by_problem"].items():
        week_incidents_by_problem[pid] = sum(
            1 for i in incidents
            if window_start_utc <= daily.parse_iso(i.get("created_at") or "") < window_end_utc
        )
        prior_incidents_by_problem[pid] = sum(
            1 for i in incidents
            if prior_start_utc <= daily.parse_iso(i.get("created_at") or "") < window_start_utc
        )

    verdict, blockers, cautions = assess_blockers(
        week_tickets, prior_tickets, csat_pct, csat_n,
        refunds_week, d["incidents_by_problem"], d["problems"],
        other_open_week=other_open_week,
        other_open_prior=other_open_prior,
        gh_linked_open=gh_linked_open,
    )

    critical_open = [
        t for t in week_tickets
        if daily.urgency_for(t) == "critical"
        and t.get("status") not in ("solved", "closed")
    ]

    escalated_open = [
        t for t in week_tickets
        if "how_escalated" in (t.get("tags") or [])
        and t.get("status") not in ("solved", "closed")
    ]

    # Map caution string → problem ticket ID so renders can inject Zendesk links
    kp_caution_to_pid: dict[str, int] = {}
    for _kpid, _kp_incs in d["incidents_by_problem"].items():
        _open = [i for i in _kp_incs if i.get("status") not in ("solved", "closed")]
        if not _open:
            continue
        _prob = d["problems"].get(_kpid, {})
        _resolved = _prob.get("status", "open") in ("solved", "closed")
        _subj = _trunc((_prob.get("subject") or f"problem #{_kpid}").strip(), 80)
        _n, _n_all = len(_open), len(_kp_incs)
        _count = (
            f"{_n_all} linked report{'s' if _n_all != 1 else ''} ({_n} open)"
            if _n < _n_all else f"{_n} open report{'s' if _n != 1 else ''}"
        )
        _suffix = " — bug fixed, remediation in progress" if _resolved else ""
        _msg = f"1 known problem with {_count} — \"{_subj}\"{_suffix}"
        if _n >= OPEN_INCIDENTS_WATCH:
            kp_caution_to_pid[_msg] = _kpid

    return {
        "week_start":           week_start_et.isoformat(),
        "week_end":             week_end_et.isoformat(),
        "week_tickets":         week_tickets,
        "prior_tickets":        prior_tickets,
        "real_week":            real_week,
        "misdirected_week":     misdirected_week,
        "solved_week":          solved_week,
        "theme_counter":        theme_counter,
        "good_week":            good_week,
        "bad_week":             bad_week,
        "csat_pct":             csat_pct,
        "csat_n":               csat_n,
        "refunds_week":         refunds_week,
        "fos_week":             fos_week,
        "fos_since_launch":     d["fos_since_launch"],
        "daily_vol":            daily_vol,
        "verdict":              verdict,
        "blockers":             blockers,
        "cautions":             cautions,
        "theme_tickets":        dict(theme_tickets),
        "theme_subs":           {k: dict(v) for k, v in theme_subs.items()},
        "prior_theme_counter":  prior_theme_counter,
        "gh_linked_week":       gh_linked_week,
        "gh_linked_open":       gh_linked_open,
        "other_open_week":      other_open_week,
        "other_open_prior":     other_open_prior,
        "incidents_by_problem":        d["incidents_by_problem"],
        "week_incidents_by_problem":   week_incidents_by_problem,
        "prior_incidents_by_problem":  prior_incidents_by_problem,
        "problems":                    d["problems"],
        "cumulative":                  cumulative,
        "critical_open":               critical_open,
        "escalated_open":              escalated_open,
        "kp_caution_to_pid":           kp_caution_to_pid,
        "subdomain":                   daily.zd_creds().get("subdomain", "tbpro"),
    }


# ── Shared text helpers ───────────────────────────────────────────────────────

def _trunc(s: str, n: int = 80) -> str:
    """Truncate at a word boundary, appending ellipsis, so we never cut mid-word."""
    if len(s) <= n:
        return s
    cut = s[:n].rsplit(" ", 1)[0]
    return cut + "…"


# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_weekly_md(d: dict, public: bool = False) -> str:
    verdict     = d["verdict"]
    icon        = {"CLEAR": "✅", "WATCH": "🟡", "BLOCK": "🔴"}[verdict]
    w_start     = d["week_start"]
    w_end       = d["week_end"]
    n_week      = len(d["week_tickets"])
    n_prior     = len(d["prior_tickets"])
    n_real      = len(d["real_week"])
    n_mis       = len(d["misdirected_week"])
    n_solved    = len(d["solved_week"])
    n_refund    = len(d["refunds_week"])
    subdomain   = d.get("subdomain", "tbpro")
    contact_rate = 100 * n_real / daily.INVITEE_COUNT if daily.INVITEE_COUNT else 0
    R = daily.redact if public else (lambda x: x)

    o = []
    o.append(f"# TB Pro — Weekly Executive Summary · {w_start} → {w_end}")
    o.append("")
    o.append(
        f"_{daily.LAUNCH_DATE} launch · {daily.INVITEE_COUNT} invitees"
        f" · {contact_rate:.1f}% contact rate"
        f" · generated {dt.date.today().isoformat()}_"
    )
    o.append("")

    # Verdict banner
    o.append(f"## {icon} Wave invite status: **{verdict}**")
    o.append("")
    if d["blockers"]:
        o.append("**Hard blockers:**")
        for b in d["blockers"]:
            o.append(f"- 🔴 {R(b)}")
        o.append("")
    if d["cautions"]:
        o.append("**Watch signals:**")
        for c in d["cautions"]:
            disp = R(c)  # redact embedded problem subjects when public
            if "user urgency: critical" in c:
                subjects = "; ".join(
                    f"[#{t['id']}](https://{subdomain}.zendesk.com/agent/tickets/{t['id']}) {_trunc(R(t.get('subject') or ''), 55)}".strip()
                    for t in (d.get("critical_open") or [])
                )
                o.append(f"- 🟡 {disp}: {subjects}" if subjects else f"- 🟡 {disp}")
            elif "unresolved escalated" in c:
                subjects = "; ".join(
                    f"[#{t['id']}](https://{subdomain}.zendesk.com/agent/tickets/{t['id']}) {_trunc(R(t.get('subject') or ''), 55)}".strip()
                    for t in (d.get("escalated_open") or [])
                )
                o.append(f"- 🟡 {disp}: {subjects}" if subjects else f"- 🟡 {disp}")
            elif "known problem" in c and c in (d.get("kp_caution_to_pid") or {}):
                pid = d["kp_caution_to_pid"][c]
                url = f"https://{subdomain}.zendesk.com/agent/tickets/{pid}"
                linked = re.sub(r'"([^"]+)"', f'[\\1]({url})', disp, count=1)
                o.append(f"- 🟡 {linked}")
            else:
                o.append(f"- 🟡 {disp}")
        o.append("")
    if not d["blockers"] and not d["cautions"]:
        o.append("_No blockers or watch signals this week._")
        o.append("")

    o.append("---")
    o.append("")

    # Week at a glance table
    wow_str = ""
    if n_prior:
        delta = n_week - n_prior
        pct   = delta / n_prior * 100
        wow_str = f" ({'+' if delta >= 0 else ''}{delta}, {'+' if pct >= 0 else ''}{pct:.0f}% WoW)"

    csat_str = (
        f"{d['csat_pct']:.0f}% ({d['csat_n']} responses)"
        if d["csat_pct"] is not None
        else f"— ({d['csat_n']} responses)"
    )

    o.append("## Week at a glance")
    o.append("")
    o.append("| Metric | Value |")
    o.append("|--------|-------|")
    o.append(f"| New tickets | **{n_week}**{wow_str} |")
    o.append(f"| Real subscriber issues | **{n_real}** |")
    o.append(f"| Misdirected (non-subscribers) | **{n_mis}** |")
    o.append(f"| Solved this week | **{n_solved}** |")
    o.append(f"| CSAT | **{csat_str}** |")
    o.append(f"| Refunds / cancels | **{n_refund}** |")
    other_open = d.get("other_open_week", 0)
    other_prior = d.get("other_open_prior", 0)
    other_str = str(other_open)
    if other_prior:
        surge = (other_open / other_prior - 1) * 100
        other_str += f" ({'+' if surge >= 0 else ''}{surge:.0f}% WoW)"
    o.append(f"| Other-brand open/new tickets | **{other_str}** |")
    o.append(f"| New ideas this week | **{len(d['fos_week'])}** |")
    o.append("")

    # Daily sparkline
    if d["daily_vol"]:
        o.append("**Daily ticket volume:**")
        for day in sorted(d["daily_vol"]):
            n   = d["daily_vol"][day]
            bar = "█" * min(n, 30)
            o.append(f"- `{day}` {bar} {n}")
        o.append("")

    # Theme breakdown
    o.append("## What we heard")
    o.append("")
    total = sum(d["theme_counter"].values())
    prior_tc = d.get("prior_theme_counter") or Counter()
    for theme, n in d["theme_counter"].most_common(8):
        pct    = 100 * n / total if total else 0
        prior_n = prior_tc.get(theme, 0)
        wow    = f" ({"+" if n - prior_n >= 0 else ""}{n - prior_n} WoW)" if prior_n or n else ""
        o.append(f"- **{theme}**: {n} ({pct:.0f}%){wow}")
    o.append("")

    # GitHub-linked open bugs — build map for cross-referencing Known problems
    gh_open = d.get("gh_linked_open") or []
    gh_by_number_md = {
        str(item["issue"].get("number") or ""): item
        for item in gh_open
        if item["issue"].get("number")
    }

    # Known problems (with GitHub issue link merged in when numbers match)
    open_problems = _open_problems(d)
    prior_inc_map = d.get("prior_incidents_by_problem", {})
    absorbed_md: set[str] = set()
    if open_problems:
        o.append("## Known problems")
        o.append("")
        week_inc_map = d.get("week_incidents_by_problem", {})
        for _pid, prob, all_inc, open_inc in open_problems:
            subj   = _trunc(R((prob.get("subject") or f"#{_pid}").strip()))
            n_all  = len(all_inc)
            n_open = len(open_inc)
            if n_open < n_all:
                label = f"{n_all} linked report{'s' if n_all != 1 else ''} ({n_open} open)"
            else:
                label = f"{n_all} open report{'s' if n_all != 1 else ''}"
            n_week  = week_inc_map.get(_pid, 0)
            n_prior = prior_inc_map.get(_pid, 0)
            delta   = n_week - n_prior
            wow     = f" (+{delta} new this wk)" if delta > 0 else (f" ({delta} new this wk)" if delta < 0 else "")
            prob_subj_lower = (prob.get("subject") or "").lower()
            gh_suffix = ""
            for num, gh_item in gh_by_number_md.items():
                if num in prob_subj_lower:
                    iss = gh_item["issue"]
                    gh_url = iss.get("url") or ""
                    gh_ref = f"{iss.get('repo','?')}#{num}"
                    gh_st  = iss.get("state") or "open"
                    gh_suffix = f" · [{gh_ref}]({gh_url}) _{gh_st}_"
                    absorbed_md.add(num)
                    break
            o.append(f"- **{subj}** — {label}{wow}{gh_suffix}")

    # Reported bugs — only GitHub issues NOT already shown in Known problems
    unabsorbed_md = [
        item for item in gh_open
        if str(item["issue"].get("number") or "") not in absorbed_md
    ]
    if unabsorbed_md:
        o.append("")
        o.append("## Reported bugs")
        o.append("")
        for item in unabsorbed_md:
            iss   = item["issue"]
            ref   = f"{iss.get('repo', '?')}#{iss.get('number', '?')}"
            url   = iss.get("url") or ""
            title = _trunc(iss.get("title") or ref)
            state = iss.get("state") or "open"
            o.append(f"- [{ref}]({url}) — {title} _{state}_")
        o.append("")

    # New ideas this week
    if d["fos_week"]:
        o.append("## New ideas this week")
        o.append("")
        for p in d["fos_week"]:
            title = p.get("title") or "Untitled"
            votes = p.get("votes_count", 0)
            url   = p.get("url") or ""
            o.append(f"- [{title}]({url}) · {votes} vote(s)")
        o.append("")

    o.append("---")
    o.append("_**Legend:** ✅ CLEAR — no blockers, proceed · 🟡 WATCH — monitor before acting · 🔴 BLOCK — hold invites_")
    o.append("")
    o.append(
        f"_Auto-generated · {daily.INVITEE_COUNT} TB Pro Wave 1 invitees"
        f" · [Daily reports](../LATEST.md)_"
    )
    return "\n".join(o)


# ── HTML renderer ─────────────────────────────────────────────────────────────

def render_weekly_html(d: dict, public: bool = False) -> str:
    from tbpro_daily import _BOLT_CSS, _h  # noqa: PLC0415
    R = daily.redact if public else (lambda s: s)

    verdict      = d["verdict"]
    v_color      = {"CLEAR": "var(--success)", "WATCH": "var(--warning)", "BLOCK": "var(--critical)"}[verdict]
    v_bg         = {"CLEAR": "var(--success-bg)", "WATCH": "var(--warning-bg)", "BLOCK": "var(--critical-bg)"}[verdict]
    v_icon       = {"CLEAR": "✅", "WATCH": "🟡", "BLOCK": "🔴"}[verdict]

    n_week        = len(d["week_tickets"])
    n_prior       = len(d["prior_tickets"])
    n_real        = len(d["real_week"])
    n_mis         = len(d["misdirected_week"])
    subdomain     = d.get("subdomain", "tbpro")
    contact_rate  = 100 * n_real / daily.INVITEE_COUNT if daily.INVITEE_COUNT else 0
    n_solved = len(d["solved_week"])
    n_refund = len(d["refunds_week"])
    csat_str = f"{d['csat_pct']:.0f}%" if d["csat_pct"] is not None else "—"
    csat_sub = f"{d['csat_n']} response{'s' if d['csat_n'] != 1 else ''}"
    wow_str  = ""
    if n_prior:
        delta = n_week - n_prior
        pct   = delta / n_prior * 100
        wow_str = f"{'+' if delta >= 0 else ''}{delta} ({'+' if pct >= 0 else ''}{pct:.0f}% WoW)"

    p = []
    p.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thundermail · Weekly Summary · {_h(d["week_start"])} → {_h(d["week_end"])}</title>
<style>
{_BOLT_CSS}
/* ── Verdict banner ── */
.verdict-banner{{border-radius:10px;overflow:hidden;margin-bottom:1.5rem;border:1px solid {v_color};}}
.verdict-head{{background:{v_color};padding:.8rem 1.25rem;display:flex;align-items:center;gap:.9rem;}}
.verdict-pill{{font-size:.75rem;font-weight:800;text-transform:uppercase;letter-spacing:.1em;color:#0d0c14;flex-shrink:0;}}
.verdict-title{{font-size:.82rem;color:#0d0c14;opacity:.8;font-weight:500;}}
.verdict-body{{background:var(--bg-card);padding:.65rem 1.25rem;}}
.verdict-signal{{display:flex;align-items:baseline;gap:.5rem;font-size:.8rem;color:var(--text-2);padding:.2rem 0;}}
.verdict-signal-arrow{{color:{v_color};font-weight:700;flex-shrink:0;font-size:.75rem;}}
.verdict-clear{{font-size:.8rem;color:var(--text-3);font-style:italic;padding:.25rem 0;}}
/* ── Theme drilldown ── */
.theme-details{{border-bottom:1px solid var(--border);}}
.theme-details:last-child{{border-bottom:none;}}
.theme-summary{{display:flex;align-items:center;gap:.75rem;padding:.35rem .25rem;cursor:pointer;list-style:none;user-select:none;}}
.theme-summary::-webkit-details-marker{{display:none;}}
.theme-summary::before{{content:"›";color:var(--text-3);font-size:.8rem;width:.75rem;flex-shrink:0;transition:transform .15s;}}
.theme-details[open] .theme-summary::before{{transform:rotate(90deg);}}
.theme-drill{{padding:.45rem .25rem .65rem 1.5rem;border-top:1px solid var(--border);background:var(--bg-lower);}}
.theme-drill-meta{{font-size:.7rem;color:var(--text-3);margin-bottom:.3rem;}}
.theme-sample{{font-size:.73rem;color:var(--text-2);padding:.1rem 0;}}
.theme-sample::before{{content:"·";margin-right:.4rem;color:var(--text-3);}}
/* ── Bug reports ── */
.bug-item{{display:flex;flex-wrap:wrap;align-items:baseline;gap:.35rem .65rem;padding:.4rem 0;border-bottom:1px solid var(--border);font-size:.82rem;}}
.bug-item:last-child{{border-bottom:none;}}
.bug-ref{{font-weight:600;color:var(--warning);white-space:nowrap;flex-shrink:0;}}
.bug-title{{color:var(--text-2);flex:1 1 auto;min-width:0;word-break:break-word;}}
.bug-state{{font-size:.68rem;color:var(--text-3);white-space:nowrap;flex-shrink:0;}}
/* ── Sparkline ── */
.spark{{font-family:'JetBrains Mono','Fira Mono',monospace;font-size:.72rem;line-height:1.9;}}
.spark-row{{display:flex;align-items:center;gap:.5rem;}}
.spark-date{{width:5.5rem;color:var(--text-3);flex-shrink:0;}}
.spark-bar{{color:var(--primary);}}
.spark-n{{color:var(--text-2);font-size:.68rem;}}
</style>
</head>
<body>
<div class="header">
  <div class="header-badge">Thundermail · Weekly</div>
  <div class="header-title">Weekly Executive Summary — Flight 2</div>
  <div class="header-meta">{_h(d["week_start"])} → {_h(d["week_end"])} &nbsp;·&nbsp; Flight 2 launch: {_h(daily.LAUNCH_DATE)} &nbsp;·&nbsp; {_h(str(daily.INVITEE_COUNT))} invitees &nbsp;·&nbsp; {contact_rate:.1f}% contact rate</div>
</div>
""")

    # Verdict banner — header row + subordinate signal list
    p.append(
        f'<div class="verdict-banner">'
        f'<div class="verdict-head">'
        f'<span class="verdict-pill">{_h(verdict)}</span>'
        f'<span class="verdict-title">Wave invite status</span>'
        f'</div>'
    )
    if d["blockers"] or d["cautions"]:
        p.append('<div class="verdict-body">')
        def _zd_ticket_link(t):
            url = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            subj = _h(_trunc(R(t.get("subject") or ""), 55))
            return f'<a href="{url}">#{t["id"]}</a> <em style="color:var(--text-2)">{subj}</em>'
        for b in d["blockers"]:
            if "unresolved escalated" in b:
                subjects = "; ".join(_zd_ticket_link(t) for t in (d.get("escalated_open") or []))
                blabel = _h(R(b)) + (f": {subjects}" if subjects else "")
            else:
                blabel = _h(R(b))
            p.append(
                f'<div class="verdict-signal">'
                f'<span class="verdict-signal-arrow">→</span>'
                f'<span style="color:var(--critical)">{blabel}</span></div>'
            )
        for c in d["cautions"]:
            disp = R(c)  # redact embedded problem subjects when public
            if "user urgency: critical" in c:
                subjects = "; ".join(_zd_ticket_link(t) for t in (d.get("critical_open") or []))
                label = _h(disp) + (f": {subjects}" if subjects else "")
            elif "unresolved escalated" in c:
                subjects = "; ".join(_zd_ticket_link(t) for t in (d.get("escalated_open") or []))
                label = _h(disp) + (f": {subjects}" if subjects else "")
            elif "known problem" in c and c in (d.get("kp_caution_to_pid") or {}):
                pid = d["kp_caution_to_pid"][c]
                url = _h(f"https://{subdomain}.zendesk.com/agent/tickets/{pid}")
                m = re.match(r'^(.*?)"([^"]+)"(.*)$', disp)
                if m:
                    label = f'{_h(m.group(1))}<a href="{url}">{_h(m.group(2))}</a>{_h(m.group(3))}'
                else:
                    label = _h(disp)
            else:
                label = _h(disp)
            p.append(
                f'<div class="verdict-signal">'
                f'<span class="verdict-signal-arrow">→</span>'
                f'<span>{label}</span></div>'
            )
        p.append('</div>')
    else:
        p.append('<div class="verdict-body"><span class="verdict-clear">No blockers or watch signals this week.</span></div>')
    p.append('</div>\n')

    # Metrics grid
    other_open   = d.get("other_open_week", 0)
    other_prior  = d.get("other_open_prior", 0)
    other_wow    = ""
    if other_prior:
        surge = (other_open / other_prior - 1) * 100
        other_wow = f"{'+' if surge >= 0 else ''}{surge:.0f}% WoW"

    p.append('<h2>Week at a glance</h2>\n<div class="metrics">')
    for cls, val, label, sub in [
        ("blue",   str(n_week),             "New tickets",              wow_str),
        ("blue",   str(n_real),             "Real subscriber issues",   ""),
        ("blue",   str(n_mis),              "Misdirected",              "non-subscribers"),
        ("green",  str(n_solved),           "Solved",                   ""),
        ("green",  csat_str,                "CSAT",                     csat_sub),
        ("orange", str(n_refund),           "Refunds / cancels",        ""),
        ("orange", str(other_open),         "Other-brand open/new",     other_wow),
        ("teal",   str(len(d["fos_week"])), "New ideas this week",      ""),
    ]:
        p.append(
            f'<div class="metric {cls}">'
            f'<div class="metric-val">{_h(val)}</div>'
            f'<div class="metric-label">{_h(label)}</div>'
            + (f'<div class="metric-sub">{_h(sub)}</div>' if sub else "")
            + "</div>"
        )
    p.append("</div>\n")

    # CSAT bar
    if d["csat_pct"] is not None and d["csat_n"] >= MIN_CSAT_SAMPLE:
        pct = int(d["csat_pct"])
        p.append(f'<div class="csat-bar"><div class="csat-fill" style="width:{pct}%"></div></div>\n')

    # Daily sparkline
    if d["daily_vol"]:
        p.append('<h2>Daily volume</h2>\n<div class="spark">')
        max_n = max(d["daily_vol"].values()) or 1
        scale = max(1, (max_n + 19) // 20)
        for day in sorted(d["daily_vol"]):
            n    = d["daily_vol"][day]
            bars = "█" * max(1, n // scale)
            p.append(
                f'<div class="spark-row">'
                f'<span class="spark-date">{_h(day)}</span>'
                f'<span class="spark-bar">{_h(bars)}</span>'
                f'<span class="spark-n">{n}</span></div>'
            )
        p.append("</div>\n")

    # Theme breakdown with collapsible drilldown
    prior_tc      = d.get("prior_theme_counter") or {}
    theme_tickets = d.get("theme_tickets") or {}

    p.append('<h2>What we heard</h2>\n')
    if d["theme_counter"]:
        max_n = max(d["theme_counter"].values())
        for theme, n in d["theme_counter"].most_common(8):
            bar_pct  = int(n / max_n * 100)
            prior_n  = prior_tc.get(theme, 0)
            wow_delta = n - prior_n
            wow_html  = (
                f'<span style="font-size:.68rem;color:{"var(--success)" if wow_delta > 0 else "var(--text-3)"};margin-left:.35rem">'
                f'{"+" if wow_delta >= 0 else ""}{wow_delta} WoW</span>'
            ) if prior_n is not None else ""

            subs    = d.get("theme_subs", {}).get(theme) or {}  # {raw_theme: count}
            tickets = theme_tickets.get(theme) or []

            p.append(f'<details class="theme-details">')
            p.append(
                f'<summary class="theme-summary">'
                f'<span class="theme-name">{_h(theme)}{wow_html}</span>'
                f'<span class="theme-count">{n}</span>'
                f'<span class="theme-bar-wrap"><span class="theme-bar-fill" style="width:{bar_pct}%"></span></span>'
                f'</summary>'
            )
            p.append('<div class="theme-drill">')
            p.append(f'<div class="theme-drill-meta">{n} ticket(s) this theme</div>')
            if len(subs) >= 2:
                # Sub-theme breakdown: strip shared prefix to get short labels
                sub_items = sorted(subs.items(), key=lambda x: -x[1])
                # Find common prefix (part before " — ") if all subs share one
                parts = [raw.split(" — ", 1) for raw in subs]
                common_prefix = parts[0][0] if all(p2[0] == parts[0][0] for p2 in parts if len(p2) > 1) and len(parts[0]) > 1 else None
                for raw_sub, cnt in sub_items:
                    if common_prefix and raw_sub.startswith(common_prefix + " — "):
                        label = raw_sub[len(common_prefix) + 3:].capitalize()
                    else:
                        label = raw_sub
                    p.append(f'<div class="theme-sample"><span style="color:var(--text-3);min-width:2rem;display:inline-block;text-align:right;margin-right:.4rem">{cnt}</span>{_h(label)}</div>')
                # Ticket IDs for all tickets in this theme
                if tickets:
                    id_links = "  ".join(
                        f'<a href="https://{subdomain}.zendesk.com/agent/tickets/{t["id"]}">#{t["id"]}</a>'
                        for t in tickets if t.get("id")
                    )
                    p.append(f'<div style="font-size:.65rem;color:var(--text-3);padding:.25rem 0 0 .3rem">{id_links}</div>')
            else:
                for t in tickets[:5]:
                    s = R(t.get("subject") or "")
                    if not s.strip():
                        continue
                    tid = t.get("id")
                    id_link = f'<a href="https://{subdomain}.zendesk.com/agent/tickets/{tid}">#{tid}</a> ' if tid else ""
                    p.append(f'<div class="theme-sample">{id_link}{_h(s)}</div>')
            p.append('</div>')
            p.append('</details>')
    p.append("\n")

    # Build map: GitHub issue number → issue item, for cross-referencing Known problems
    gh_open = d.get("gh_linked_open") or []
    gh_by_number = {
        str(item["issue"].get("number") or ""): item
        for item in gh_open
        if item["issue"].get("number")
    }

    # Known problems (merged with GitHub bug link when the issue number matches)
    open_problems = _open_problems(d)
    prior_inc_map = d.get("prior_incidents_by_problem", {})
    absorbed_gh_numbers: set[str] = set()
    if open_problems:
        p.append('<h2>Known problems</h2>\n')
        week_inc_map = d.get("week_incidents_by_problem", {})
        for _pid, prob, all_inc, open_inc in open_problems:
            subj_raw = R((prob.get("subject") or f"#{_pid}").strip())
            subj     = _h(subj_raw)
            n_all  = len(all_inc)
            n_open = len(open_inc)
            color  = "var(--critical)" if n_open >= OPEN_INCIDENTS_BLOCK else "var(--warning)"
            if n_open < n_all:
                reports_label = f"{n_all} linked report{'s' if n_all != 1 else ''} ({n_open} open)"
            else:
                reports_label = f"{n_all} open report{'s' if n_all != 1 else ''}"
            n_week  = week_inc_map.get(_pid, 0)
            n_prior = prior_inc_map.get(_pid, 0)
            delta   = n_week - n_prior
            delta_color = "var(--critical)" if delta > 0 else "var(--success)" if delta < 0 else "var(--text-3)"
            wow_html = (
                f' <span style="font-size:.72rem;color:{delta_color};font-weight:600">'
                f'{"+" if delta >= 0 else ""}{delta} new this wk</span>'
            ) if (n_week > 0 or n_prior > 0) else ""
            # Check if any GitHub issue number appears in this problem's subject
            prob_subj_lower = (prob.get("subject") or "").lower()
            gh_link_html = ""
            for num, gh_item in gh_by_number.items():
                if num in prob_subj_lower:
                    iss    = gh_item["issue"]
                    gh_url = _h(iss.get("url") or "")
                    gh_ref = _h(f"{iss.get('repo','?')}#{num}")
                    gh_st  = _h(iss.get("state") or "open")
                    gh_link_html = (
                        f' &mdash; <a href="{gh_url}" style="color:var(--warning);font-size:.8rem">'
                        f'{gh_ref}</a>'
                        f' <span style="font-size:.68rem;color:var(--text-3)">{gh_st}</span>'
                    )
                    absorbed_gh_numbers.add(num)
                    break
            zd_url = _h(f"https://{subdomain}.zendesk.com/agent/tickets/{_pid}")
            subj_linked = f'<a href="{zd_url}" style="color:inherit">{subj}</a>'
            p.append(
                f'<div class="card" style="border-left:3px solid {color};padding:.5rem 1rem;margin-bottom:.4rem">'
                f"<strong>{subj_linked}</strong>{gh_link_html} &mdash; "
                f'<span style="color:var(--text-2);font-size:.85rem">{reports_label}{wow_html}</span></div>'
            )
        p.append("\n")

    # Reported bugs — GitHub-linked open tickets NOT already shown in Known problems
    unabsorbed = [
        item for item in gh_open
        if str(item["issue"].get("number") or "") not in absorbed_gh_numbers
    ]
    if unabsorbed:
        p.append('<h2>Reported bugs</h2>\n<div class="card">')
        for item in unabsorbed:
            iss   = item["issue"]
            ref   = _h(f"{iss.get('repo', '?')}#{iss.get('number', '?')}")
            url   = _h(iss.get("url") or "")
            title = _h(iss.get("title") or "")
            state = _h(iss.get("state") or "open")
            p.append(
                f'<div class="bug-item">'
                f'<span class="bug-ref"><a href="{url}" style="color:var(--warning)">{ref}</a></span>'
                f'<span class="bug-title">{title}</span>'
                f'<span class="bug-state">{state}</span>'
                f'</div>'
            )
        p.append('</div>\n')

    # FeatureOS ideas this week
    if d["fos_week"]:
        p.append('<h2>New ideas this week</h2>\n<ul class="ideas-list">')
        for post in d["fos_week"]:
            title = _h(post.get("title") or "Untitled")
            votes = post.get("votes_count", 0)
            url   = _h(post.get("url") or "")
            p.append(
                f'<li class="idea-item">'
                f'<div class="idea-title"><a href="{url}">{title}</a></div>'
                f'<div class="idea-meta">{votes} &#9651;</div></li>'
            )
        p.append("</ul>\n")

    p.append(
        '<div style="font-size:.72rem;color:var(--text-3);margin:1.5rem 0 .5rem;padding-top:.75rem;'
        'border-top:1px solid var(--border)">'
        '<strong>Legend:</strong> '
        '✅ CLEAR — no blockers, proceed &nbsp;&middot;&nbsp; '
        '🟡 WATCH — monitor before acting &nbsp;&middot;&nbsp; '
        '🔴 BLOCK — hold invites'
        '</div>\n'
    )
    p.append(
        f'<div class="footer">Auto-generated &nbsp;·&nbsp; {_h(str(daily.INVITEE_COUNT))} TB Pro Wave 1 invitees'
        f' &nbsp;·&nbsp; <a href="LATEST.html">Latest daily &rarr;</a></div>'
    )
    p.append("</body>\n</html>")
    return "\n".join(p)


# ── Shared helper ─────────────────────────────────────────────────────────────

def _open_problems(d: dict):
    """Return [(pid, prob_dict, all_incidents, open_incidents)] sorted by all-incident count desc.

    Surfaces the problem if any incident is not solved/closed.
    all_incidents = every linked incident; open_incidents = just the active ones.
    """
    result = []
    for pid, incidents in d["incidents_by_problem"].items():
        open_inc = [i for i in incidents if i.get("status") not in ("solved", "closed")]
        if open_inc:
            result.append((pid, d["problems"].get(pid, {}), incidents, open_inc))
    return sorted(result, key=lambda x: -len(x[2]))


# ── Entry point ───────────────────────────────────────────────────────────────

DEFAULT_OUT_DIR = Path("reports/tbpro/weekly")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--week-end", default=None,
        help="ISO date of the last day to include (default: today). "
             "Script always anchors to the Monday of that week.",
    )
    parser.add_argument("--public", action="store_true",
                        help="Redact PII (for committed / shared reports)")
    parser.add_argument("--out-dir", default=None,
                        help=f"Output directory (default: {DEFAULT_OUT_DIR})")
    args = parser.parse_args()

    today_et = dt.datetime.now(ET).date()
    week_end = dt.date.fromisoformat(args.week_end) if args.week_end else today_et

    d   = build_weekly(week_end)
    md  = render_weekly_md(d,   public=args.public)
    htm = render_weekly_html(d, public=args.public)

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    out_path  = out_dir / f"{d['week_end']}.md"
    html_path = out_dir / f"{d['week_end']}.html"
    out_path.write_text(md)
    print(f"Wrote {out_path}", file=sys.stderr)
    html_path.write_text(htm)
    print(f"Wrote {html_path}", file=sys.stderr)

    # Update latest pointers one level up (reports/tbpro/)
    latest_dir = out_dir.parent
    (latest_dir / "LATEST_WEEKLY.md").write_text(md)
    (latest_dir / "LATEST_WEEKLY.html").write_text(htm)
    print("Updated LATEST_WEEKLY.*", file=sys.stderr)


if __name__ == "__main__":
    main()
