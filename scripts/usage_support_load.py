#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
Thundermail usage vs. support load — v1.

"Unique active users" = distinct PostHog person_id firing the activity event
in a window, not raw event count. 15 events from 3 people counts as 3, not 45
— otherwise one chatty account inflates the denominator and understates the
real ticket-to-usage ratio.

Two outputs, deliberately split by sensitivity:

Public  → lisa/daily/usage_support_load.html
  Ticket volume + unique submitters vs. PostHog active users (today / 7d / 30d),
  plus a 14-day trend. No agent-level or per-person data — safe for the public
  repo / GitHub Pages.

Private → lisa/private/thundermail_agent_load.html (gitignored — never commit)
  Per-agent tickets/day + AHT for the Thundermail brand only, agents
  anonymized (Agent 1, 2, …). AHT is the Time Tracking app custom field
  (actual logged work time), NOT ticket status durations — status-based
  timers are inflated by the pending-first workflow's 48h bump.

  Volume = tickets where Zendesk `updated_at` falls in the lookback window
  (any field change — comment, status, tag, macro), grouped by *current*
  assignee. This is Zendesk Explore's own definition (verified against a
  Lisa-pulled Explore export, 2026-09-02 — matched to within 1-2 tickets on
  every agent). An earlier version of this script counted tickets by
  *creation* date instead, which undercounted anyone working backlog/
  reopened/escalated tickets by 2-4x — don't reintroduce that.

Usage: uv run scripts/usage_support_load.py

Requires a PostHog personal API key with query:read scope on the
"TB Pro - Production" project (id 82711). Env var POSTHOG_API_KEY (CI), or
api_key=... in ~/.config/posthog/credentials (local), same shape as the
Zendesk creds file.
"""

import sys, os, json, urllib.request
import datetime as dt
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from tbpro_daily import zd_search_all, BRAND_ID, EXCLUDE_IDS

PUBLIC_OUT  = Path("lisa/daily/usage_support_load.html")
PRIVATE_OUT = Path("lisa/private/thundermail_agent_load.html")

# --- PostHog -----------------------------------------------------------------
POSTHOG_PROJECT_ID   = 82711  # "TB Pro - Production"
POSTHOG_BASE_URL     = "https://us.posthog.com"
# Broadest genuine-usage signal (4,605 unique people / 30d vs. 938 for
# message-sending, 2,708 for ham ingest, 4,009 for login-only) — NOT $pageview.
POSTHOG_ACTIVE_EVENT = "accounts.activity"
PH_CREDS_PATH        = Path.home() / ".config" / "posthog" / "credentials"

# --- Zendesk / capacity --------------------------------------------------------
TIME_SPENT_FIELD_ID = 45345504704659   # Time Tracking app "Total time spent (sec)"
EXCLUDE_AGENT_IDS   = {51426647255187}  # eng seats, bots — matches capacity_dashboard.py
PRIVATE_LOOKBACK_WEEKS = 4


def posthog_api_key():
    key = os.environ.get("POSTHOG_API_KEY")
    if key:
        return key.strip()
    if PH_CREDS_PATH.exists():
        for line in PH_CREDS_PATH.read_text().splitlines():
            line = line.strip()
            if line.startswith("api_key="):
                return line.split("=", 1)[1].strip()
    sys.exit(
        f"Missing PostHog personal API key. Set POSTHOG_API_KEY env var or "
        f"add api_key=... to {PH_CREDS_PATH}"
    )


def posthog_hogql(query):
    key = posthog_api_key()
    url = f"{POSTHOG_BASE_URL}/api/projects/{POSTHOG_PROJECT_ID}/query/"
    body = json.dumps({"query": {"kind": "HogQLQuery", "query": query}}).encode()
    req = urllib.request.Request(url, data=body, headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    })
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def unique_active_users(start, end):
    """Distinct persons firing POSTHOG_ACTIVE_EVENT in [start, end)."""
    q = f"""
        SELECT uniq(person_id)
        FROM events
        WHERE event = '{POSTHOG_ACTIVE_EVENT}'
          AND timestamp >= toDateTime('{start.isoformat()}')
          AND timestamp < toDateTime('{end.isoformat()}')
    """
    d = posthog_hogql(q)
    rows = d.get("results", [])
    return int(rows[0][0]) if rows else 0


def daily_active_users(start, end):
    """{date: unique_person_count} for each UTC day in [start, end)."""
    q = f"""
        SELECT toDate(timestamp) AS day, uniq(person_id) AS dau
        FROM events
        WHERE event = '{POSTHOG_ACTIVE_EVENT}'
          AND timestamp >= toDateTime('{start.isoformat()}')
          AND timestamp < toDateTime('{end.isoformat()}')
        GROUP BY day
        ORDER BY day
    """
    d = posthog_hogql(q)
    out = {}
    for row in d.get("results", []):
        out[dt.date.fromisoformat(str(row[0])[:10])] = int(row[1])
    return out


# --- Zendesk -------------------------------------------------------------------

def clean_thundermail_tickets(tickets):
    """Same exclusion chain as tbpro_daily.build(): closed_by_merge (duplicate
    of a canonical ticket), test subject, agent-created (submitter != requester),
    and known-problem/incident IDs."""
    tickets = [t for t in tickets if "closed_by_merge" not in (t.get("tags") or [])]
    tickets = [t for t in tickets if (t.get("subject") or "").strip().lower() != "test"]
    tickets = [t for t in tickets if t.get("submitter_id") == t.get("requester_id")]
    tickets = [t for t in tickets if int(t.get("id", 0)) not in EXCLUDE_IDS]
    tickets = [t for t in tickets if int(t.get("problem_id") or 0) not in EXCLUDE_IDS]
    return tickets


def fetch_window_tickets(start_date, end_date):
    tickets = zd_search_all(
        f"type:ticket brand_id:{BRAND_ID} "
        f"created>={start_date.isoformat()} created<{end_date.isoformat()}"
    )
    return clean_thundermail_tickets(tickets)


def anonymize_agents(tickets):
    seen, counter = {}, 1
    for t in sorted(tickets, key=lambda x: x.get("created_at", "")):
        aid = t.get("assignee_id")
        if aid and aid not in seen and aid not in EXCLUDE_AGENT_IDS:
            seen[aid] = f"Agent {counter}"
            counter += 1
    return seen


def time_spent_minutes(ticket):
    for cf in ticket.get("custom_fields", []):
        if cf.get("id") == TIME_SPENT_FIELD_ID and cf.get("value"):
            return int(cf["value"]) / 60
    return None


def fetch_touched_tickets(start_date, end_date):
    """Tickets with ANY update (comment, status, tag, macro...) in
    [start_date, end_date) — Zendesk Explore's own 'ticket updated' definition.
    Grouping these by *current* assignee, verified against a Lisa-pulled
    Explore export (2026-09-02), matches to within 1-2 tickets per agent.
    Creation-date-based counting does not — see module docstring."""
    tickets = zd_search_all(
        f"type:ticket brand_id:{BRAND_ID} "
        f"updated>={start_date.isoformat()} updated<{end_date.isoformat()}"
    )
    return clean_thundermail_tickets(tickets)


# --- Public dashboard: usage vs. ticket load -----------------------------------

CSS = """
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8;
    --indigo: #6366f1; --orange: #f97316; --green: #10b981; --red: #f43f5e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font: 14px/1.6 system-ui, sans-serif; padding: 24px; }
  h1 { font-size: 1.3rem; margin-bottom: 4px; }
  .eyebrow { color: var(--muted); font-size: 0.8rem; margin-bottom: 28px; }
  .warning { background: #7c2d12; border: 1px solid #ea580c; border-radius: 6px;
             padding: 10px 16px; margin-bottom: 28px; font-size: 0.85rem; color: #fed7aa; }
  h2 { font-size: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
       margin: 32px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 14px 18px; min-width: 190px; flex: 1; }
  .card__label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                 letter-spacing: .05em; margin-bottom: 4px; color: var(--indigo); }
  .card__value { font-size: 1.8rem; font-weight: 700; line-height: 1; }
  .card__sub { font-size: 0.75rem; color: var(--muted); margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
  th { text-align: left; padding: 8px 12px; background: var(--surface);
       color: var(--muted); font-size: 0.75rem; text-transform: uppercase;
       border-bottom: 1px solid var(--border); }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  .num { font-variant-numeric: tabular-nums; }
  small { color: var(--muted); font-size: 0.75rem; }
  .incoming-row { background: rgba(99,102,241,.08); }
  .panel { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
           padding: 16px; margin-bottom: 14px; }
  .panel__title { font-size: 0.78rem; color: var(--muted); margin-bottom: 8px; }
  .panel__title strong { color: var(--text); }
  svg { display: block; width: 100%; height: auto; }
  .gridline { stroke: #2b3a55; stroke-width: 1; }
  .axis-label { fill: var(--muted); font-size: 10px; font-family: system-ui, sans-serif; }
"""


def build_line_chart_svg(values, color, w=640, h=160, pad_x=8, pad_top=30, pad_bottom=8):
    """Single-hue line+area chart from oldest->newest values. Top padding leaves
    headroom for the peak's end-label so it doesn't clip against the chart edge."""
    n = len(values)
    lo, hi = min(values), max(values)
    span = hi - lo or 1
    usable = h - pad_top - pad_bottom
    pts = []
    for i, v in enumerate(values):
        x = pad_x + (i * (w - 2 * pad_x) / (n - 1) if n > 1 else 0)
        y = pad_top + usable * (1 - (v - lo) / span)
        pts.append((round(x, 1), round(y, 1), v))
    path_d = "M " + " L ".join(f"{x},{y}" for x, y, _ in pts)
    area_d = path_d + f" L {pts[-1][0]},{h} L {pts[0][0]},{h} Z"
    circles = "".join(
        f'<circle class="pt" cx="{x}" cy="{y}" r="3" fill="{color}" '
        f'stroke="#1e293b" stroke-width="1.5"><title>{v:,}</title></circle>'
        for x, y, v in pts
    )
    end_x, end_y, end_v = pts[-1]
    return f"""<svg viewBox="0 0 {w} {h}" preserveAspectRatio="none">
      <line class="gridline" x1="{pad_x}" y1="{pad_top}" x2="{w-pad_x}" y2="{pad_top}"/>
      <line class="gridline" x1="{pad_x}" y1="{h-pad_bottom}" x2="{w-pad_x}" y2="{h-pad_bottom}"/>
      <text class="axis-label" x="{pad_x+4}" y="{pad_top+12}">{hi:,}</text>
      <text class="axis-label" x="{pad_x+4}" y="{h-pad_bottom-4}">{lo:,}</text>
      <path d="{path_d}" fill="none" stroke="{color}" stroke-width="2"
            stroke-linejoin="round" stroke-linecap="round"/>
      <path d="{area_d}" fill="{color}" opacity="0.1" stroke="none"/>
      {circles}
      <text x="{end_x-4}" y="{end_y-8}" text-anchor="end" font-size="11" font-weight="700"
            fill="{color}" font-family="system-ui,sans-serif">{end_v:,}</text>
    </svg>"""


def build_indexed_chart_svg(series, w=640, h=200, pad_x=8, pad_top=30, pad_bottom=24):
    """series = [(label, color, values)], oldest->newest, same length.
    Indexes each series to its own first-3-day average = 100, so two
    differently-scaled metrics (DAU in the thousands, tickets in the tens)
    can share one axis meaningfully -- a plain shared axis would flatten
    the smaller series to a line at the bottom; a second y-axis lets two
    unrelated lines cross wherever you want, so neither is used here.
    Legend required since color is now the only series-identity channel."""
    n = len(series[0][2])
    indexed = []
    for label, color, values in series:
        base = sum(values[:3]) / min(3, len(values))
        base = base or 1
        indexed.append((label, color, [v / base * 100 for v in values]))

    all_vals = [v for _, _, vals in indexed for v in vals]
    lo, hi = min(all_vals), max(all_vals)
    span = hi - lo or 1
    usable = h - pad_top - pad_bottom

    def xy(i, v):
        x = pad_x + (i * (w - 2 * pad_x) / (n - 1) if n > 1 else 0)
        y = pad_top + usable * (1 - (v - lo) / span)
        return round(x, 1), round(y, 1)

    paths, circles, end_labels, legend = "", "", "", ""
    for label, color, vals in indexed:
        pts = [xy(i, v) for i, v in enumerate(vals)]
        path_d = "M " + " L ".join(f"{x},{y}" for x, y in pts)
        paths += (f'<path d="{path_d}" fill="none" stroke="{color}" stroke-width="2" '
                   f'stroke-linejoin="round" stroke-linecap="round"/>')
        circles += "".join(
            f'<circle class="pt" cx="{x}" cy="{y}" r="3" fill="{color}" '
            f'stroke="#1e293b" stroke-width="1.5"><title>{label}: {v:,.0f} (index)</title></circle>'
            for (x, y), v in zip(pts, vals)
        )
        end_x, end_y = pts[-1]
        end_labels += (f'<text x="{end_x-4}" y="{end_y-8}" text-anchor="end" font-size="11" '
                        f'font-weight="700" fill="{color}" font-family="system-ui,sans-serif">'
                        f'{vals[-1]:,.0f}</text>')
        legend += (f'<span style="display:inline-flex;align-items:center;gap:6px;margin-right:16px">'
                    f'<span style="width:10px;height:10px;border-radius:50%;background:{color};'
                    f'display:inline-block"></span>{label}</span>')

    return f"""
    <div style="font-size:0.78rem;color:var(--muted);margin-bottom:8px">{legend}</div>
    <svg viewBox="0 0 {w} {h}" preserveAspectRatio="none">
      <line class="gridline" x1="{pad_x}" y1="{pad_top}" x2="{w-pad_x}" y2="{pad_top}"/>
      <line class="gridline" x1="{pad_x}" y1="{h-pad_bottom}" x2="{w-pad_x}" y2="{h-pad_bottom}"/>
      <text class="axis-label" x="{pad_x+4}" y="{pad_top+12}">{hi:,.0f}</text>
      <text class="axis-label" x="{pad_x+4}" y="{h-pad_bottom-4}">{lo:,.0f}</text>
      {paths}
      {circles}
      {end_labels}
    </svg>
    <p style="color:var(--muted);font-size:0.72rem;margin-top:4px">
      Index = % of each series' own first-3-day average, not raw counts — the two metrics
      have very different scales (DAU in the thousands, tickets in the tens), so this is the
      only way to show them on one shared axis without a second y-axis. Use the table below
      for exact values.
    </p>"""


def build_public_html(windows, trend, today):
    gen = today.strftime("%Y-%m-%d")

    def ratio(n, d):
        return f"{n/d:.3f} ({n/d*100:.1f}%)" if d else "—"

    def pct(n, d):
        return f"{n/d*100:.1f}%" if d else "—"

    cards = ""
    labels = {"today": "Today", "7d": "Trailing 7d", "30d": "Trailing 30d"}
    for key in ("today", "7d", "30d"):
        w = windows[key]
        cards += f"""
        <div class="card">
          <div class="card__label">{labels[key]}</div>
          <div class="card__value">{w['tickets']}</div>
          <div class="card__sub">
            tickets · {w['unique_submitters']} unique submitters<br>
            {w['active_users']} unique active users (PostHog)<br>
            <strong>{ratio(w['tickets'], w['active_users'])}</strong> tickets/active user ·
            <strong>{ratio(w['unique_submitters'], w['active_users'])}</strong> unique submitters/active user
          </div>
        </div>"""

    trend_rows = ""
    for day in sorted(trend.keys(), reverse=True):
        row = trend[day]
        r = pct(row['tickets'], row['dau'])
        trend_rows += f"""<tr>
          <td>{day.isoformat()}</td>
          <td class="num">{row['dau']}</td>
          <td class="num">{row['tickets']}</td>
          <td class="num">{row['unique_submitters']}</td>
          <td class="num"><strong>{r}</strong></td>
        </tr>"""

    days_sorted = sorted(trend.keys())
    combined_chart = build_indexed_chart_svg([
        ("Active users (DAU)", "#6366f1", [trend[d]["dau"] for d in days_sorted]),
        ("Tickets/day", "#f97316", [trend[d]["tickets"] for d in days_sorted]),
    ])
    span_note = f"{days_sorted[0].isoformat()} → {days_sorted[-1].isoformat()}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thundermail — Usage vs. Support Load</title>
<style>{CSS}</style>
</head>
<body>
<h1>Thundermail — Usage vs. Support Load</h1>
<div class="eyebrow">Generated {gen} · Thundermail brand only · v1</div>

<h2>Tickets Relative to Active Usage</h2>
<div class="cards">{cards}</div>
<p style="color:var(--muted);font-size:0.78rem;margin:8px 0 0">
  "Unique active users" = distinct PostHog people firing an activity event in the window,
  not raw event count — a person hitting the product 15 times counts once, not 15 times.
  "Unique submitters" = distinct Zendesk requesters, so one chatty account can't be mistaken
  for a broad issue. Ticket counts exclude merged, test, and agent-created tickets and known
  infrastructure incidents (same rules as the daily/weekly reports).
</p>

<h2>14-Day Trend</h2>
<div class="panel">
  <div class="panel__title">Active users vs. tickets/day <strong>— indexed, {span_note}</strong></div>
  {combined_chart}
</div>
<table>
  <thead><tr><th>Day</th><th>Unique active users (DAU)</th><th>Tickets</th>
  <th>Unique submitters</th><th>Tickets/active user</th></tr></thead>
  <tbody>{trend_rows}</tbody>
</table>

</body>
</html>"""


# --- Private dashboard: per-agent load + AHT -----------------------------------

def build_private_html(tickets, agent_map, today):
    gen = today.strftime("%Y-%m-%d")
    all_agents = sorted(set(agent_map.values()))
    cal_days = PRIVATE_LOOKBACK_WEEKS * 7 or 1

    # tickets here = touched (updated_at in window), grouped by current
    # assignee — see fetch_touched_tickets docstring. Divide by calendar
    # days, not work_days: updates land on weekends/off-hours too.
    by_agent = defaultdict(int)
    for t in tickets:
        agent = agent_map.get(t.get("assignee_id"))
        if agent:
            by_agent[agent] += 1

    time_by_agent = defaultdict(list)
    for t in tickets:
        mins = time_spent_minutes(t)
        agent = agent_map.get(t.get("assignee_id"))
        if mins and agent:
            time_by_agent[agent].append(mins)

    def med_h(lst):
        if not lst:
            return "—"
        import statistics
        return f"{statistics.median(lst)/60:.1f}h"

    def mean_h(lst):
        if not lst:
            return "—"
        import statistics
        return f"{statistics.mean(lst)/60:.1f}h"

    rows = ""
    for agent in all_agents:
        total = by_agent.get(agent, 0)
        per_day = round(total / cal_days, 1)
        per_week = round(total / PRIVATE_LOOKBACK_WEEKS, 1)
        lst = time_by_agent.get(agent, [])
        rows += f"""<tr>
          <td><strong>{agent}</strong></td>
          <td class="num"><strong>{per_day}/day</strong> <small>({per_week}/wk, {total} tickets)</small></td>
          <td class="num">{med_h(lst)}</td>
          <td class="num">{mean_h(lst)}</td>
          <td class="num">{len(lst)}</td>
        </tr>"""

    total_all = sum(by_agent.values())
    all_time = [m for lst in time_by_agent.values() for m in lst]
    rows = f"""<tr style="border-top:2px solid var(--border)">
      <td><strong>Team</strong></td>
      <td class="num"><strong>{round(total_all/cal_days,1)}/day</strong> <small>({round(total_all/PRIVATE_LOOKBACK_WEEKS,1)}/wk, {total_all} tickets)</small></td>
      <td class="num">{med_h(all_time)}</td>
      <td class="num">{mean_h(all_time)}</td>
      <td class="num">{len(all_time)}</td>
    </tr>""" + rows

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Thundermail Agent Load — Private</title>
<style>{CSS}</style>
</head>
<body>
<h1>Thundermail Agent Load</h1>
<div class="eyebrow">Generated {gen} · {PRIVATE_LOOKBACK_WEEKS}-week lookback · Local only — do not share</div>

<div class="warning">
  ⚠️ Agent data is anonymized — agents appear as capacity units only. Do not share agent ID mappings.
  This file is gitignored (lisa/private/) — never commit.
</div>

<div class="warning" style="background:#1e2a4a;border-color:#3b4d7a;color:#c7d2fe">
  📈 Not a steady-state baseline right now: (1) two agents started Aug 4 — their tickets/day
  is still ramping through onboarding, not representative of long-run capacity; (2) an
  accidental 19k-invite send is driving an active ticket spike. Don't use this window alone
  for the 50k staffing/budget model — wait for volume to normalize or bracket this period out.
</div>

<h2>Tickets/Day and AHT by Agent (Thundermail brand only)</h2>
<p style="color:var(--muted);font-size:0.8rem;margin-bottom:10px">
  Volume = tickets with any update (comment, status, tag, macro…) in the window, grouped by
  current assignee — Zendesk Explore's own "ticket updated" definition, verified against a
  Lisa-pulled Explore export. AHT = Time Tracking app "Total time spent" custom field (actual
  logged work time), not status-based durations — the pending-first workflow's 48h bump
  inflates those to days. Divided by calendar days (7/wk) since updates land on weekends too.
</p>
<table>
  <thead><tr><th>Agent</th><th>Tickets touched/day</th>
  <th>Median AHT</th><th>Mean AHT</th><th>Tickets with timer</th></tr></thead>
  <tbody>{rows}</tbody>
</table>

</body>
</html>"""


def main():
    today = dt.date.today()

    print("Fetching PostHog active users…", flush=True)
    window_bounds = {
        "today": (today, today + dt.timedelta(days=1)),
        "7d":    (today - dt.timedelta(days=7), today + dt.timedelta(days=1)),
        "30d":   (today - dt.timedelta(days=30), today + dt.timedelta(days=1)),
    }
    windows = {}
    for key, (start, end) in window_bounds.items():
        active_users = unique_active_users(start, end)
        print(f"Fetching Zendesk tickets for {key}…", flush=True)
        tickets = fetch_window_tickets(start, end)
        unique_submitters = len({t.get("requester_id") for t in tickets if t.get("requester_id")})
        windows[key] = {
            "active_users": active_users,
            "tickets": len(tickets),
            "unique_submitters": unique_submitters,
        }
        print(f"  {key}: {active_users} active users, {len(tickets)} tickets, "
              f"{unique_submitters} unique submitters", flush=True)

    print("Fetching 14-day daily trend…", flush=True)
    trend_start = today - dt.timedelta(days=13)
    trend_end = today + dt.timedelta(days=1)
    dau_by_day = daily_active_users(trend_start, trend_end)
    trend_tickets = fetch_window_tickets(trend_start, trend_end)
    tickets_by_day = defaultdict(list)
    for t in trend_tickets:
        d = dt.date.fromisoformat(t["created_at"][:10])
        tickets_by_day[d].append(t)

    trend = {}
    for i in range(14):
        d = trend_start + dt.timedelta(days=i)
        day_tickets = tickets_by_day.get(d, [])
        trend[d] = {
            "dau": dau_by_day.get(d, 0),
            "tickets": len(day_tickets),
            "unique_submitters": len({t.get("requester_id") for t in day_tickets if t.get("requester_id")}),
        }

    PUBLIC_OUT.parent.mkdir(parents=True, exist_ok=True)
    PUBLIC_OUT.write_text(build_public_html(windows, trend, today))
    print(f"Written → {PUBLIC_OUT.resolve()}")

    print(f"Fetching Thundermail tickets touched in the last {PRIVATE_LOOKBACK_WEEKS} weeks…", flush=True)
    private_start = today - dt.timedelta(weeks=PRIVATE_LOOKBACK_WEEKS)
    private_tickets = fetch_touched_tickets(private_start, today + dt.timedelta(days=1))
    agent_map = anonymize_agents(private_tickets)
    print(f"  {len(private_tickets)} tickets touched, {len(agent_map)} agents", flush=True)
    # Console-only (never written to the HTML) — lets you map "Agent N" back to
    # a real assignee_id/name in Zendesk to cross-check against Explore.
    for aid, label in sorted(agent_map.items(), key=lambda x: x[1]):
        print(f"  {label}: assignee_id={aid}", flush=True)

    PRIVATE_OUT.parent.mkdir(parents=True, exist_ok=True)
    PRIVATE_OUT.write_text(build_private_html(private_tickets, agent_map, today))
    print(f"Written → {PRIVATE_OUT.resolve()}")


if __name__ == "__main__":
    main()
