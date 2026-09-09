#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
Capacity dashboard — aggregated by TEAM GROUP, never by individual agent. Anonymized
(no names or IDs written to disk — the ID→group mapping prints to the terminal only).
Approved for commit + GitHub Pages (finance-facing).

Generates capacity/overview.html with 4 tabs: Overview + one per brand/workstream
(Donor Support, Thundermail, Play Store). Always segmented by workstream — mixing an
outsourced team with an in-house team, or agents who work multiple brands, into one flat
table is confusing (confirmed 2026-09-09) even when anonymized. Anonymization and
workstream-separation are two separate requirements; this script does both.

Team structure (2026-09-09, update GROUPS below as the org changes):
  Donor Support   — 2 BPO agents, Donor Support brand only.
  Thundermail     — 2 in-house specialists (primary) + the same 3-person "Tier 2"
                    backup pool below (secondary coverage).
  Play Store      — the "Tier 2" pool again, primary there. Same 3 people show up in
                    both the Thundermail and Play Store tabs — real overlap, not a bug.
  Lisa (manager) and eng seats are excluded from every group — not steady-state capacity.

Per-agent breakdown (needed only for active hiring/staffing decisions) is a separate,
local-only, gitignored dashboard — see `--per-agent` flag.
"""

import sys, json, base64, urllib.request, urllib.parse, statistics, datetime as dt, time, argparse
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from tbpro_daily import zd_creds

LOOKBACK_WEEKS  = 4
AHT_WEEKS       = 4
OUT             = Path("capacity/overview.html")
OUT_PRIVATE     = Path("lisa/private/capacity_by_agent.html")
OLD_LOCATION    = Path("lisa/daily/capacity_dashboard.html")  # redirect stub only

# Assignee IDs to exclude entirely (eng seats, bots, the manager — not steady-state capacity)
LISA_ID = 42628517301011
EXCLUDE_AGENT_IDS = {51426647255187, LISA_ID}

# Custom field ID for Time Tracking app "Total time spent (sec)". Restricted to the Donor
# Support Zendesk group as of 2026-09-09 — disabled for Thundermail/Play Store because of a
# confirmed app bug (timer doesn't stop when the laptop is locked with a ticket open; also
# found overlapping timers across tabs). Donor Support's data checked out clean (BPO
# contracted-hours use case, single-session tickets) — safe to keep using there.
TIME_SPENT_FIELD_ID = 45345504704659

BRAND_TAGS = {
    "brand_thundermail":       "Thundermail",
    "brand_google_play_store": "Play Store",
    "brand_donor_support":     "Donor Support",
}
BRAND_COLORS = {
    "Thundermail":   "#6366f1",   # indigo, matches monthly dashboard's TB Pro section
    "Play Store":    "#f97316",   # orange, matches monthly dashboard's Android section
    "Donor Support": "#10b981",   # green, matches monthly dashboard's Donor Care section
}

# Team group → assignee_ids. Update when the roster changes (see module docstring).
GROUPS = {
    "Donor Support": {53841671102227, 54044160386195},               # Sofia, McGyver (BPO)
    "Specialists":   {54085832149907, 54085876291603},                # Amanda, Rocky (Thundermail primary)
    "Tier 2":        {45054637328147, 33975290937747, 38308537060499},# MadHatter, Roland, Monica
}
GROUP_OF_AGENT = {aid: label for label, ids in GROUPS.items() for aid in ids}
GROUP_ORDER = ["Specialists", "Tier 2", "Donor Support"]  # display order


# ── Zendesk helpers ───────────────────────────────────────────────────────────

def zd_auth(creds):
    return "Basic " + base64.b64encode(f"{creds['email']}/token:{creds['token']}".encode()).decode()

def zd_get(url, auth, retries=4):
    for i in range(retries):
        req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < retries - 1:
                time.sleep(int(e.headers.get("Retry-After", 5)) + 1)
                continue
            raise

def week_start(d):
    return d - dt.timedelta(days=d.weekday())

def brand_of(ticket):
    tags = ticket.get("tags", [])
    for tag, label in BRAND_TAGS.items():
        if tag in tags:
            return label
    return "Other"

def fetch_tickets(creds, since_date):
    """Fetch by ticket created date in 2-week chunks to stay under search API 1k limit."""
    auth = zd_auth(creds)
    sub  = creds["subdomain"]
    today = dt.date.today()
    results = []
    chunk_start = since_date
    print("Fetching tickets by created date…", flush=True)
    while chunk_start < today:
        chunk_end = min(chunk_start + dt.timedelta(weeks=2), today)
        since_str = chunk_start.isoformat()
        until_str = chunk_end.isoformat()
        page = 1
        while True:
            d = zd_get(
                f"https://{sub}.zendesk.com/api/v2/search.json"
                f"?query=type:ticket+created>={since_str}+created<{until_str}"
                f"&per_page=100&page={page}", auth)
            batch = d.get("results", [])
            results.extend(batch)
            if not d.get("next_page") or page >= 10:
                break
            page += 1
        print(f"  {since_str} → {until_str}: {len(results)} total so far", flush=True)
        chunk_start = chunk_end
    return results, auth, sub


def fetch_metrics(tickets, auth, sub, since_date):
    """Fetch first reply time for tickets. Returns {ticket_id: mins}.
    Full resolution time is not used — pending-first workflow (48h bump) inflates it
    to days and doesn't reflect actual agent work time."""
    cutoff = since_date.isoformat()
    candidates = [t for t in tickets if t.get("created_at", "") >= cutoff]
    print(f"Fetching first-reply time for {len(candidates)} tickets…", flush=True)
    frt = {}
    for i, t in enumerate(candidates):
        tid = str(t["id"])
        try:
            m = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{tid}/metrics.json", auth)
            mm = m.get("ticket_metric", {})
            v = (mm.get("reply_time_in_minutes") or {}).get("calendar")
            if v and v > 0:
                frt[tid] = v
        except Exception:
            pass
        if (i + 1) % 25 == 0:
            print(f"  {i+1}/{len(candidates)}", flush=True)
    return frt


def group_agents(tickets):
    """Return {assignee_id: group_label} for known group members seen in this ticket set.
    Console-only mapping — never written to a file. Anyone not in GROUPS (Lisa, eng seats,
    an unrecognized assignee) is simply absent from the map and excluded from every rollup."""
    seen_ids = {t.get("assignee_id") for t in tickets if t.get("assignee_id")}
    return {aid: GROUP_OF_AGENT[aid] for aid in seen_ids if aid in GROUP_OF_AGENT}


def anonymize_agents(tickets):
    """Per-agent variant for the private/hiring dashboard only. 'Agent N' labels,
    never written with real names — console printout maps N back to a real person."""
    seen, counter = {}, 1
    for t in sorted(tickets, key=lambda x: x.get("created_at", "")):
        aid = t.get("assignee_id")
        if aid and aid not in seen and aid not in EXCLUDE_AGENT_IDS:
            seen[aid] = f"Agent {counter}"
            counter += 1
    return seen


def fetch_public_replies(auth, sub, since_date, agent_map):
    """Return (reply_data, nrt_data) in one incremental-events pass, keyed by whatever
    agent_map maps assignee_id to (group label or per-agent label — caller's choice).

    reply_data: {label: {week_iso: distinct_ticket_count}}
    nrt_data:   {label: [minutes]}  — customer public comment → next agent public reply.
    """
    start_ts = int(dt.datetime.combine(since_date, dt.time.min,
                                        tzinfo=dt.timezone.utc).timestamp())
    url = f"https://{sub}.zendesk.com/api/v2/incremental/ticket_events.json?start_time={start_ts}"

    touched = set()
    ticket_timeline = defaultdict(list)
    agent_ids = set(agent_map.keys())

    print("Fetching public reply events…", flush=True)
    page = 0
    while url:
        d = zd_get(url, auth)
        page += 1
        events = d.get("ticket_events", [])
        for event in events:
            ts = event.get("timestamp")
            if not ts:
                continue
            created = dt.datetime.fromtimestamp(ts, tz=dt.timezone.utc).date()
            if created < since_date:
                continue
            ticket_id  = event.get("ticket_id")
            updater_id = event.get("updater_id")
            w = week_start(created).isoformat()
            has_public = any(
                child.get("event_type") in ("Comment", "VoiceComment")
                and child.get("comment_public", False)
                for child in event.get("child_events", [])
            )
            if not has_public:
                continue
            if updater_id and updater_id in agent_ids:
                touched.add((updater_id, ticket_id, w))
            author = updater_id if updater_id in agent_ids else None
            ticket_timeline[ticket_id].append((ts, author, updater_id))
        print(f"  page {page}: {len(events)} events, {len(touched)} touches so far", flush=True)
        if d.get("end_of_stream"):
            break
        url = d.get("next_page")

    reply_data = defaultdict(lambda: defaultdict(int))
    for (author_id, _ticket_id, w) in touched:
        reply_data[agent_map[author_id]][w] += 1

    nrt_data = defaultdict(list)
    for tid, timeline in ticket_timeline.items():
        timeline.sort(key=lambda x: x[0])
        i = 0
        while i < len(timeline):
            ts_cust, agent, uid = timeline[i]
            if agent is not None:
                i += 1
                continue
            for j in range(i + 1, len(timeline)):
                ts_next, next_agent, next_uid = timeline[j]
                if next_agent is not None:
                    wait_mins = (ts_next - ts_cust) / 60
                    if 0 < wait_mins < 60 * 24 * 14:
                        nrt_data[agent_map[next_agent]].append(wait_mins)
                    break
            i += 1

    return reply_data, nrt_data


def fetch_backlog_flow(auth, sub, weeks, today, brand_tag=None):
    """Return {week_iso: solved_count} and current_open count, optionally scoped to one
    brand tag (e.g. 'brand_thundermail'). Uses search count queries — one per week."""
    sub_url = f"https://{sub}.zendesk.com/api/v2/search/count.json"
    tag_filter = f"+tags:{brand_tag}" if brand_tag else ""

    solved_by_week = {}
    for w in weeks:
        w_start = dt.date.fromisoformat(w)
        w_end   = min(w_start + dt.timedelta(weeks=1), today)
        q = f"type:ticket+solved>={w_start.isoformat()}+solved<{w_end.isoformat()}{tag_filter}"
        d = zd_get(f"{sub_url}?query={q}", auth)
        solved_by_week[w] = d.get("count", 0)

    open_count = 0
    for status in ("open", "pending", "hold"):
        d = zd_get(f"{sub_url}?query=type:ticket+status:{status}{tag_filter}", auth)
        open_count += d.get("count", 0)

    return solved_by_week, open_count


# ── Aggregation ────────────────────────────────────────────────────────────────

def aggregate(tickets, aht_by_id, agent_map, today):
    """Bucket everything by (week, group, brand). Shared by overview + per-brand tabs."""
    this_week = week_start(today)
    weeks = [(this_week - dt.timedelta(weeks=i)).isoformat()
             for i in range(LOOKBACK_WEEKS - 1, -1, -1)]

    incoming_by_week   = defaultdict(lambda: defaultdict(int))          # [week][brand]
    throughput_by_week = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # [week][group][brand]
    time_spent_group_brand = defaultdict(lambda: defaultdict(list))     # [group][brand] -> [mins]
    frt_group_brand = defaultdict(lambda: defaultdict(list))
    frt_brand = defaultdict(list)
    time_spent_brand = defaultdict(list)

    def get_time_spent(ticket):
        for cf in ticket.get("custom_fields", []):
            if cf.get("id") == TIME_SPENT_FIELD_ID and cf.get("value"):
                return int(cf["value"]) / 60
        return None

    for t in tickets:
        created_d = dt.date.fromisoformat(t["created_at"][:10])
        w = week_start(created_d).isoformat()
        brand = brand_of(t)
        if w in weeks:
            incoming_by_week[w][brand] += 1
            group = agent_map.get(t.get("assignee_id"))
            if group:
                throughput_by_week[w][group][brand] += 1

        group = agent_map.get(t.get("assignee_id"))
        mins = get_time_spent(t)
        if mins is not None and mins > 0 and brand != "Other":
            time_spent_brand[brand].append(mins)
            if group:
                time_spent_group_brand[group][brand].append(mins)

        tid = str(t["id"])
        if tid in aht_by_id and brand != "Other":
            frt_brand[brand].append(aht_by_id[tid])
            if group:
                frt_group_brand[group][brand].append(aht_by_id[tid])

    return {
        "weeks": weeks,
        "incoming_by_week": incoming_by_week,
        "throughput_by_week": throughput_by_week,
        "time_spent_group_brand": time_spent_group_brand,
        "time_spent_brand": time_spent_brand,
        "frt_group_brand": frt_group_brand,
        "frt_brand": frt_brand,
    }


# ── HTML building blocks (shared by all tabs) ───────────────────────────────────

CSS = """
  :root {
    --bg: #0f172a; --surface: #1e293b; --border: #334155;
    --text: #e2e8f0; --muted: #94a3b8;
    --indigo: #6366f1; --orange: #f97316; --green: #10b981; --red: #f43f5e;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font: 14px/1.6 system-ui, sans-serif; padding: 24px; }
  h1 { font-size: 1.3rem; margin-bottom: 4px; }
  .eyebrow { color: var(--muted); font-size: 0.8rem; margin-bottom: 20px; }
  h2 { font-size: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
       margin: 28px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }
  .cards { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
          padding: 14px 18px; min-width: 160px; flex: 1; }
  .card__label { font-size: 0.75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .05em; margin-bottom: 4px; }
  .card__value { font-size: 1.8rem; font-weight: 700; line-height: 1; }
  .card__sub { font-size: 0.75rem; color: var(--muted); margin-top: 4px; }
  table { width: 100%; border-collapse: collapse; margin-bottom: 24px; }
  th { text-align: left; padding: 8px 12px; background: var(--surface); color: var(--muted);
       font-size: 0.75rem; text-transform: uppercase; border-bottom: 1px solid var(--border); }
  td { padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tr:last-child td { border-bottom: none; }
  .num { font-variant-numeric: tabular-nums; }
  small { color: var(--muted); font-size: 0.75rem; }
  .incoming-row { background: rgba(99,102,241,.08); }
  .note { color: var(--muted); font-size: 0.8rem; margin-bottom: 10px; }
  .caveat { background: #451a03; border: 1px solid #b45309; border-radius: 6px;
            padding: 10px 14px; margin-bottom: 16px; font-size: 0.85rem; color: #fed7aa; }
  .filter-btn { background: var(--surface); border: 1px solid var(--border); border-radius: 20px;
                padding: .4rem 1rem; font-size: .85rem; cursor: pointer; color: var(--muted);
                transition: all .15s; margin-right: 8px; }
  .filter-btn:hover { border-color: var(--text); color: var(--text); }
  .filter-btn.active { color: #0f172a; font-weight: 600; }
  .filter-tabs { margin-bottom: 24px; }
  .tab-section { display: none; }
  .tab-section.active { display: block; }
"""


def stat_lists(weeks_data, brand, group=None):
    inc = sum(weeks_data["incoming_by_week"][w].get(brand, 0) for w in weeks_data["weeks"])
    if group:
        thru = sum(weeks_data["throughput_by_week"][w].get(group, {}).get(brand, 0) for w in weeks_data["weeks"])
    else:
        thru = sum(sum(weeks_data["throughput_by_week"][w].get(g, {}).get(brand, 0) for g in GROUP_ORDER)
                   for w in weeks_data["weeks"])
    return inc, thru


def med_h(lst):
    return f"{statistics.median(lst)/60:.1f}h" if lst else "—"

def mean_h(lst):
    return f"{statistics.mean(lst)/60:.1f}h" if lst else "—"


def backlog_table(weeks, incoming_by_brand_week, solved_by_week, current_open):
    ending = current_open
    rows_data = []
    for w in reversed(weeks):
        new_cnt    = incoming_by_brand_week.get(w, 0)
        solved_cnt = solved_by_week.get(w, 0)
        net        = new_cnt - solved_cnt
        opening    = ending - net
        rows_data.append((w, opening, new_cnt, solved_cnt, net, ending))
        ending = opening
    rows_data.reverse()

    def wlabel(w):
        return f"W{dt.date.fromisoformat(w).isocalendar()[1]}"

    rows_html = ""
    for w, opening, new_cnt, solved_cnt, net, end in rows_data:
        net_color = "var(--red)" if net > 0 else "var(--green)"
        net_str   = f"+{net}" if net > 0 else str(net)
        rows_html += (f"<tr><td>{wlabel(w)}</td><td class='num'>{opening}</td>"
                      f"<td class='num'>{new_cnt}</td><td class='num'>{solved_cnt}</td>"
                      f"<td class='num' style='color:{net_color}'>{net_str}</td>"
                      f"<td class='num'><strong>{end}</strong></td></tr>")
    return f"""<table>
      <thead><tr><th>Week</th><th>Opening</th><th>New</th><th>Closed</th><th>Net</th><th>Ending</th></tr></thead>
      <tbody>{rows_html}</tbody>
    </table>
    <p class="note">Ending backlog anchored to current open count ({current_open}); reconstructed backwards.</p>"""


def group_table(weeks_data, brand, groups_in_brand):
    """Tickets/wk + tickets/day by group, for one brand tab."""
    header = "<th>Group</th><th>Tickets/wk</th><th>Tickets/day</th>"
    rows = ""
    for group in groups_in_brand:
        total = sum(weeks_data["throughput_by_week"][w].get(group, {}).get(brand, 0) for w in weeks_data["weeks"])
        per_week = round(total / LOOKBACK_WEEKS, 1)
        per_day  = round(total / (LOOKBACK_WEEKS * 5), 1)
        rows += f"<tr><td><strong>{group}</strong></td><td class='num'>{per_week}</td><td class='num'>{per_day}</td></tr>"
    inc_total = sum(weeks_data["incoming_by_week"][w].get(brand, 0) for w in weeks_data["weeks"])
    inc_pw = round(inc_total / LOOKBACK_WEEKS, 1)
    inc_pd = round(inc_total / (LOOKBACK_WEEKS * 7), 1)
    rows = f"<tr class='incoming-row'><td><em>Incoming</em></td><td class='num'>{inc_pw}</td><td class='num'>{inc_pd}</td></tr>" + rows
    return f"<table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>"


def reply_trend_table(weeks, reply_data, groups_in_brand, incoming_by_week_brand):
    full_weeks = weeks[:-1] or weeks  # exclude partial current week

    def wlabel(w):
        return f"W{dt.date.fromisoformat(w).isocalendar()[1]}"

    th_weeks = "".join(f"<th>{wlabel(w)}</th>" for w in full_weeks) + "<th>Avg/wk</th>"

    def row(label, wdata, css=""):
        cells = "".join(f"<td class='num {css}'>{wdata.get(w, 0)}</td>" for w in full_weeks)
        avg = round(sum(wdata.get(w, 0) for w in full_weeks) / max(len(full_weeks), 1), 1)
        cells += f"<td class='num {css}'><strong>{avg}</strong></td>"
        return f"<tr><td><strong>{label}</strong></td>{cells}</tr>"

    inc_row = row("Incoming", incoming_by_week_brand, "incoming-row")
    group_rows = "".join(row(g, reply_data.get(g, {})) for g in groups_in_brand)
    team_week = defaultdict(int)
    for g in groups_in_brand:
        for w, c in reply_data.get(g, {}).items():
            team_week[w] += c
    team_row = row("Team total", team_week)

    return f"""<table>
      <thead><tr><th>Group</th>{th_weeks}</tr></thead>
      <tbody>{inc_row}{group_rows}{team_row}</tbody>
    </table>
    <p class="note">Distinct tickets with ≥1 public reply that week (new + backlog) — actual output, not just assignment count.</p>"""


def nrt_table(nrt_data, groups_in_brand):
    rows = ""
    all_vals = []
    for g in groups_in_brand:
        lst = nrt_data.get(g, [])
        all_vals.extend(lst)
        rows += f"<tr><td><strong>{g}</strong></td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"
    if all_vals:
        rows = (f"<tr style='border-bottom:2px solid var(--border)'><td><strong>Team</strong></td>"
                f"<td>{med_h(all_vals)}</td><td>{mean_h(all_vals)}</td><td>{len(all_vals)}</td></tr>") + rows
    return f"""<table>
      <thead><tr><th>Group</th><th>Median NRT</th><th>Mean NRT</th><th>Samples</th></tr></thead>
      <tbody>{rows}</tbody></table>
    <p class="note">Time between a customer's follow-up and the next agent public reply. Outliers capped at 14 days.</p>"""


def donor_time_spent_table(weeks_data, brand, groups_in_brand):
    rows = ""
    for g in groups_in_brand:
        lst = weeks_data["time_spent_group_brand"].get(g, {}).get(brand, [])
        rows += f"<tr><td><strong>{g}</strong></td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"
    return f"""<table>
      <thead><tr><th>Group</th><th>Median AHT</th><th>Mean AHT</th><th>Tickets w/ timer</th></tr></thead>
      <tbody>{rows}</tbody></table>
    <p class="note">Time Tracking app — kept for Donor Support only (BPO contracted-hours use case; verified clean).</p>"""


def brand_tab(tab_id, brand, brand_tag, weeks_data, backlog, reply_data, nrt_data, groups_in_brand):
    color = BRAND_COLORS[brand]
    inc, thru = stat_lists(weeks_data, brand)
    cards = f"""
    <div class="card"><div class="card__label" style="color:{color}">Incoming/day</div>
      <div class="card__value">{round(inc/(LOOKBACK_WEEKS*7),1)}</div><div class="card__sub">{inc} total ({LOOKBACK_WEEKS}w)</div></div>
    <div class="card"><div class="card__label" style="color:{color}">Current open</div>
      <div class="card__value">{backlog[1]}</div><div class="card__sub">open + pending + hold</div></div>"""

    if brand == "Donor Support":
        aht_section = donor_time_spent_table(weeks_data, brand, groups_in_brand)
    else:
        aht_section = ('<div class="caveat">⚠️ Time Tracking app disabled here (2026-09-09) — '
                       'confirmed bug: timer doesn\'t stop when the laptop is locked with a ticket '
                       'open, and found overlapping timers across tabs. Replacement handle-time '
                       'metric (reply cadence + time-in-status) coming soon.</div>')

    incoming_by_week_brand = {w: weeks_data["incoming_by_week"][w].get(brand, 0) for w in weeks_data["weeks"]}

    return f"""
<div class="tab-section" data-tab="{tab_id}">
  <h2>{brand}</h2>
  <div class="cards">{cards}</div>

  <h2>Capacity by Group</h2>
  {group_table(weeks_data, brand, groups_in_brand)}

  <h2>Backlog Flow</h2>
  {backlog_table(weeks_data["weeks"], incoming_by_week_brand, backlog[0], backlog[1])}

  <h2>Output — Public Replies / Week</h2>
  {reply_trend_table(weeks_data["weeks"], reply_data, groups_in_brand, incoming_by_week_brand)}

  <h2>Next Reply Time</h2>
  {nrt_table(nrt_data, groups_in_brand)}

  <h2>Handle Time</h2>
  {aht_section}
</div>"""


def overview_tab(weeks_data, backlogs, today):
    gen = today.strftime("%Y-%m-%d")
    cards = ""
    for brand in ["Thundermail", "Play Store", "Donor Support"]:
        inc, _ = stat_lists(weeks_data, brand)
        color = BRAND_COLORS[brand]
        open_count = backlogs[brand][1]
        cards += f"""
        <div class="card"><div class="card__label" style="color:{color}">{brand}</div>
          <div class="card__value">{round(inc/(LOOKBACK_WEEKS*7),1)}/day</div>
          <div class="card__sub">{inc} incoming ({LOOKBACK_WEEKS}w) · {open_count} open now</div></div>"""

    # Staffing map: group × brand
    all_brands = ["Thundermail", "Play Store", "Donor Support"]
    header = "<th>Group</th>" + "".join(f"<th style='color:{BRAND_COLORS[b]}'>{b}</th>" for b in all_brands)
    rows = ""
    for g in GROUP_ORDER:
        role = {"Specialists": "primary", "Tier 2": "backup / Play Store primary",
                "Donor Support": "primary"}.get(g, "")
        cells = ""
        for b in all_brands:
            total = sum(weeks_data["throughput_by_week"][w].get(g, {}).get(b, 0) for w in weeks_data["weeks"])
            cells += f"<td class='num'>{round(total/LOOKBACK_WEEKS,1)}/wk</td>" if total else "<td class='num'>—</td>"
        rows += f"<tr><td><strong>{g}</strong><br><small>{role}</small></td>{cells}</tr>"

    return f"""
<div class="tab-section active" data-tab="overview">
  <h2>Support Volume by Workstream</h2>
  <div class="cards">{cards}</div>

  <h2>Staffing Map — Group × Brand</h2>
  <p class="note">Tier 2 covers Thundermail backup and Play Store primary — same three people, different roles per brand. That overlap is real, not a data error.</p>
  <table><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>
</div>"""


def build_html(weeks_data, backlogs, reply_data, nrt_data, groups_by_brand, today):
    gen = today.strftime("%Y-%m-%d")
    tabs = [("overview", "Overview", "#94a3b8")] + [
        (b.lower().replace(" ", "-"), b, BRAND_COLORS[b]) for b in ["Thundermail", "Play Store", "Donor Support"]
    ]
    tab_buttons = "".join(
        f'<button class="filter-btn{" active" if i==0 else ""}" data-color="{color}" '
        f'style="{"background:"+color+";border-color:"+color if i==0 else ""}" '
        f'onclick="showTab(\'{tid}\', this)">{label}</button>'
        for i, (tid, label, color) in enumerate(tabs)
    )

    seen = set()
    brand_sections = ""
    for tag, b in BRAND_TAGS.items():
        if b in seen:
            continue
        seen.add(b)
        brand_sections += brand_tab(b.lower().replace(" ", "-"), b, tag, weeks_data, backlogs[b], reply_data, nrt_data, groups_by_brand[b])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Capacity Overview</title>
<style>{CSS}</style>
</head>
<body>
<h1>Capacity Overview</h1>
<div class="eyebrow">Generated {gen} · {LOOKBACK_WEEKS}-week lookback · Aggregated by team group — no individual agent data</div>

<div class="filter-tabs">{tab_buttons}</div>

{overview_tab(weeks_data, backlogs, today)}
{brand_sections}

<script>
function showTab(tab, btn) {{
  document.querySelectorAll('.tab-section').forEach(s => s.classList.toggle('active', s.dataset.tab === tab));
  document.querySelectorAll('.filter-btn').forEach(b => {{ b.classList.remove('active'); b.style.background=''; b.style.borderColor=''; }});
  btn.classList.add('active');
  btn.style.background = btn.dataset.color;
  btn.style.borderColor = btn.dataset.color;
  history.replaceState(null, '', '#' + tab);
}}
(function() {{
  const hash = window.location.hash.replace('#', '');
  if (hash) {{
    const btn = document.querySelector(`.filter-btn[onclick*="'${{hash}}'"]`);
    if (btn) showTab(hash, btn);
  }}
}})();
</script>
</body>
</html>"""


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--per-agent", action="store_true",
                   help="Build the private, per-agent breakdown instead (for active hiring/staffing decisions only)")
    args = p.parse_args()

    creds    = zd_creds()
    today    = dt.date.today()
    since    = today - dt.timedelta(weeks=LOOKBACK_WEEKS)
    aht_since = today - dt.timedelta(weeks=AHT_WEEKS)

    tickets, auth, sub = fetch_tickets(creds, since)
    print(f"Total tickets: {len(tickets)}")

    aht_by_id = fetch_metrics(tickets, auth, sub, aht_since)
    print(f"FRT samples: {len(aht_by_id)}")

    if args.per_agent:
        agent_map = anonymize_agents(tickets)
        print(f"Agents: {len(agent_map)}")
        for aid, label in sorted(agent_map.items(), key=lambda x: x[1]):
            print(f"  {label}: assignee_id={aid}")
    else:
        agent_map = group_agents(tickets)
        print(f"Groups seen: {sorted(set(agent_map.values()))}")
        for aid, label in sorted(agent_map.items(), key=lambda x: x[1]):
            print(f"  {label}: assignee_id={aid}")

    reply_data, nrt_data = fetch_public_replies(auth, sub, since, agent_map)
    print(f"Reply data: {sum(sum(v.values()) for v in reply_data.values())} agent/group-week entries")
    print(f"NRT samples: {sum(len(v) for v in nrt_data.values())}")

    weeks_data = aggregate(tickets, aht_by_id, agent_map, today)

    if args.per_agent:
        # Private dashboard keeps the old flat, single-page shape — per-agent detail is
        # only ever needed ad hoc for hiring/staffing, not a standing published view.
        print("Per-agent private dashboard: TODO — reuse aggregate() output with agent_map "
              "labels; not built yet (ask for it when actively hiring).", file=sys.stderr)
        return

    print("Fetching backlog flow per brand…", flush=True)
    this_week = week_start(today)
    weeks = weeks_data["weeks"]
    backlogs = {}
    for tag, brand in BRAND_TAGS.items():
        solved_by_week, open_count = fetch_backlog_flow(auth, sub, weeks, today, brand_tag=tag)
        backlogs[brand] = (solved_by_week, open_count)
        print(f"  {brand}: {open_count} open now", flush=True)

    groups_by_brand = {
        "Thundermail":   ["Specialists", "Tier 2"],
        "Play Store":    ["Tier 2"],
        "Donor Support": ["Donor Support"],
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(weeks_data, backlogs, reply_data, nrt_data, groups_by_brand, today)
    OUT.write_text(html)
    print(f"Written → {OUT.resolve()}")

    # Redirect stub at the old location
    OLD_LOCATION.parent.mkdir(parents=True, exist_ok=True)
    OLD_LOCATION.write_text(f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<meta http-equiv="refresh" content="0; url=../../{OUT}">
<link rel="canonical" href="../../{OUT}">
<title>Moved</title></head>
<body><p>This report moved to <a href="../../{OUT}">{OUT}</a>.</p></body></html>""")
    print(f"Redirect stub written → {OLD_LOCATION.resolve()}")


if __name__ == "__main__":
    main()
