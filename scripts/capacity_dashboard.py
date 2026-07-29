#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["requests"]
# ///
"""
Private capacity dashboard — output is gitignored, never commit.
Generates lisa/private/capacity_dashboard.html.

Sections:
  1. Incoming vs throughput (tickets/day — team total and per brand)
  2. Capacity by agent (tickets/week and tickets/day, by brand, agents anonymized)
  3. AHT (median handle time) by brand and by agent
  4. Contact timeline (days from wave invite to first Thundermail ticket)
"""

import sys, json, base64, urllib.request, statistics, datetime as dt
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))
from tbpro_daily import zd_creds

LOOKBACK_WEEKS  = 4
AHT_WEEKS       = 4
OUT             = Path("lisa/daily/capacity_dashboard.html")

# Assignee IDs to exclude from capacity view (eng seats, bots, etc.)
EXCLUDE_AGENT_IDS = {51426647255187}

# Custom field ID for Time Tracking app "Total time spent (sec)"
TIME_SPENT_FIELD_ID = 45345504704659

BRAND_TAGS = {
    "brand_thundermail":       "Thundermail",
    "brand_google_play_store": "Mobile",
    "brand_donor_support":     "Donor",
}
BRAND_COLORS = {
    "Thundermail": "#6366f1",
    "Mobile":      "#f97316",
    "Donor":       "#10b981",
}


def zd_auth(creds):
    return "Basic " + base64.b64encode(
        f"{creds['email']}/token:{creds['token']}".encode()).decode()

def zd_get(url, auth):
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)

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

def anonymize_agents(tickets):
    """Return {assignee_id: 'Agent N'} sorted by first appearance, excluding eng seats."""
    seen = {}
    counter = 1
    for t in sorted(tickets, key=lambda x: x.get("created_at", "")):
        aid = t.get("assignee_id")
        if aid and aid not in seen and aid not in EXCLUDE_AGENT_IDS:
            seen[aid] = f"Agent {counter}"
            counter += 1
    return seen


def build_html(tickets, aht_by_id, agent_map, today):
    brands     = list(BRAND_TAGS.values())
    all_agents = sorted(set(agent_map.values()))
    gen        = today.strftime("%Y-%m-%d")

    # ── weekly buckets ───────────────────────────────────────────────────────
    # Build 8 ISO weeks (Mon–Sun) ending this week
    this_week = week_start(today)
    weeks = [(this_week - dt.timedelta(weeks=i)).isoformat()
             for i in range(LOOKBACK_WEEKS - 1, -1, -1)]

    # tickets_by_week[week_iso][brand] = count
    # throughput_by_week[week_iso][agent][brand] = count  (solved)
    incoming_by_week  = defaultdict(lambda: defaultdict(int))
    throughput_by_week = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    for t in tickets:
        created_d = dt.date.fromisoformat(t["created_at"][:10])
        w = week_start(created_d).isoformat()
        if w not in weeks:
            continue
        brand = brand_of(t)
        incoming_by_week[w][brand] += 1

        # Count all assigned tickets by creation week (matches Zendesk Analytics).
        # Solved-only would exclude pending tickets and undercount by ~50%.
        agent = agent_map.get(t.get("assignee_id"))
        if agent:
            throughput_by_week[w][agent][brand] += 1

    # ── Time spent per ticket (Time Tracking app field) ──────────────────────
    def get_time_spent(ticket):
        for cf in ticket.get("custom_fields", []):
            if cf.get("id") == TIME_SPENT_FIELD_ID and cf.get("value"):
                return int(cf["value"]) / 60  # seconds → minutes
        return None

    time_spent_brand = defaultdict(list)
    time_spent_agent = defaultdict(list)
    for t in tickets:
        mins = get_time_spent(t)
        if mins is None or mins <= 0:
            continue
        brand = brand_of(t)
        agent = agent_map.get(t.get("assignee_id"))
        if brand != "Other":
            time_spent_brand[brand].append(mins)
        if agent:
            time_spent_agent[agent].append(mins)

    # ── First reply time by brand and agent ──────────────────────────────────
    frt_brand  = defaultdict(list)   # brand → [mins]
    frt_agent  = defaultdict(list)   # agent → [mins]

    for t in tickets:
        tid = str(t["id"])
        if tid not in aht_by_id:
            continue
        mins  = aht_by_id[tid]
        brand = brand_of(t)
        agent = agent_map.get(t.get("assignee_id"))
        if brand != "Other":
            frt_brand[brand].append(mins)
        if agent:
            frt_agent[agent].append(mins)

    def med_h(lst):
        if not lst: return "—"
        return f"{statistics.median(lst)/60:.1f}h"

    def mean_h(lst):
        if not lst: return "—"
        return f"{statistics.mean(lst)/60:.1f}h"

    # ── day-of-week pattern ──────────────────────────────────────────────────
    DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    dow_incoming   = defaultdict(int)   # 0=Mon … 6=Sun
    dow_throughput = defaultdict(int)
    dow_week_counts = defaultdict(set)  # track how many distinct weeks had data per dow

    for t in tickets:
        created_d = dt.date.fromisoformat(t["created_at"][:10])
        w = week_start(created_d).isoformat()
        if w not in weeks:
            continue
        dow = created_d.weekday()
        dow_incoming[dow] += 1
        dow_week_counts[dow].add(w)

    for t in tickets:
        created_d = dt.date.fromisoformat(t["created_at"][:10])
        w = week_start(created_d).isoformat()
        if w not in weeks:
            continue
        if agent_map.get(t.get("assignee_id")):
            dow_throughput[created_d.weekday()] += 1

# ── tickets/day figures ──────────────────────────────────────────────────
    days_in_range = LOOKBACK_WEEKS * 7 or 1
    work_days     = LOOKBACK_WEEKS * 5 or 1

    total_incoming = sum(sum(bv.values()) for bv in incoming_by_week.values())
    incoming_per_day = round(total_incoming / days_in_range, 1)

    agent_totals = defaultdict(lambda: defaultdict(int))
    for wk, agents in throughput_by_week.items():
        for agent, brands_d in agents.items():
            for brand, cnt in brands_d.items():
                agent_totals[agent][brand] += cnt
                agent_totals[agent]["Total"] += cnt

    # ── HTML ─────────────────────────────────────────────────────────────────
    brand_cols = brands + ["Total"]

    # Section 1: incoming vs throughput summary cards
    inc_brand_totals = defaultdict(int)
    for wv in incoming_by_week.values():
        for b, c in wv.items():
            inc_brand_totals[b] += c

    def summary_cards():
        cards = ""
        for brand in brands + ["All brands"]:
            if brand == "All brands":
                total = total_incoming
                tpd   = incoming_per_day
                color = "#94a3b8"
            else:
                total = inc_brand_totals.get(brand, 0)
                tpd   = round(total / days_in_range, 1)
                color = BRAND_COLORS.get(brand, "#94a3b8")
            cards += f"""
        <div class="card">
          <div class="card__label" style="color:{color}">{brand}</div>
          <div class="card__value">{tpd}</div>
          <div class="card__sub">tickets/day incoming · {total} total ({LOOKBACK_WEEKS}w)</div>
        </div>"""
        return cards

    # Section 2: agent capacity table
    def agent_cap_table():
        header = "<th>Agent</th>" + "".join(f"<th>{b}</th>" for b in brand_cols)
        rows = ""
        for agent in sorted(all_agents):
            td = f"<td><strong>{agent}</strong></td>"
            for brand in brand_cols:
                total = agent_totals[agent].get(brand, 0)
                per_day  = round(total / work_days, 1)
                per_week = round(total / LOOKBACK_WEEKS, 1)
                td += f"<td><span class='num'>{per_week}/wk</span><br><small>{per_day}/day</small></td>"
            rows += f"<tr>{td}</tr>"
        # Incoming row for comparison
        td = "<td><em>Incoming</em></td>"
        for brand in brand_cols:
            if brand == "Total":
                total = total_incoming
            else:
                total = inc_brand_totals.get(brand, 0)
            per_day  = round(total / days_in_range, 1)
            per_week = round(total / LOOKBACK_WEEKS, 1)
            td += f"<td class='incoming-row'><span class='num'>{per_week}/wk</span><br><small>{per_day}/day</small></td>"
        rows = f"<tr>{td}</tr>" + rows
        return f"<table class='cap-tbl'><thead><tr>{header}</tr></thead><tbody>{rows}</tbody></table>"

    # Section 3: AHT table
    def time_spent_table():
        # Team summary by brand
        brand_rows = ""
        for brand in brands:
            lst = time_spent_brand.get(brand, [])
            color = BRAND_COLORS[brand]
            brand_rows += f"<tr><td style='color:{color}'><strong>{brand}</strong></td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"

        # Per-agent × per-brand breakdown (anonymized)
        time_spent_agent_brand = defaultdict(lambda: defaultdict(list))
        for t in tickets:
            mins = get_time_spent(t)
            if mins is None or mins <= 0:
                continue
            agent = agent_map.get(t.get("assignee_id"))
            brand = brand_of(t)
            if agent and brand != "Other":
                time_spent_agent_brand[agent][brand].append(mins)

        agent_rows = ""
        for agent in sorted(all_agents):
            first = True
            for brand in brands:
                lst = time_spent_agent_brand[agent].get(brand, [])
                agent_cell = f"<td rowspan='{len(brands)}'><strong>{agent}</strong></td>" if first else ""
                first = False
                color = BRAND_COLORS[brand]
                agent_rows += f"<tr>{agent_cell}<td style='color:{color}'>{brand}</td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"
            # Agent total row
            all_lst = time_spent_agent.get(agent, [])
            agent_rows += f"<tr><td></td><td><em>All brands</em></td><td>{med_h(all_lst)}</td><td>{mean_h(all_lst)}</td><td>{len(all_lst)}</td></tr>"

        return f"""
        <p style="color:var(--muted);font-size:0.8rem;margin-bottom:8px">Team medians — long-tail means are sensitive to timers left running.</p>
        <table>
          <thead><tr><th>Brand</th><th>Median</th><th>Mean</th><th>Tickets with timer</th></tr></thead>
          <tbody>{brand_rows}</tbody>
        </table>
        <p style="color:var(--muted);font-size:0.8rem;margin:16px 0 8px">Per agent × brand — higher medians indicate ticket complexity, not just timer issues.</p>
        <table>
          <thead><tr><th>Agent</th><th>Brand</th><th>Median</th><th>Mean</th><th>Tickets with timer</th></tr></thead>
          <tbody>{agent_rows}</tbody>
        </table>"""

    def frt_table():
        rows = ""
        for brand in brands:
            lst = frt_brand.get(brand, [])
            rows += f"<tr><td style='color:{BRAND_COLORS[brand]}'><strong>{brand}</strong></td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"
        rows += "<tr><td colspan='4' class='section-divider'>By agent (all brands)</td></tr>"
        for agent in sorted(all_agents):
            lst = frt_agent.get(agent, [])
            rows += f"<tr><td>{agent}</td><td>{med_h(lst)}</td><td>{mean_h(lst)}</td><td>{len(lst)}</td></tr>"
        return f"""<table>
          <thead><tr><th>Segment</th><th>Median FRT</th><th>Mean FRT</th><th>Tickets</th></tr></thead>
          <tbody>{rows}</tbody></table>"""

    def dow_section():
        max_inc = max((dow_incoming[d] for d in range(7)), default=1)
        rows = ""
        for d in range(7):
            inc   = dow_incoming[d]
            thru  = dow_throughput[d]
            weeks_n = max(len(dow_week_counts[d]), 1)
            avg_inc  = round(inc / weeks_n, 1)
            avg_thru = round(thru / weeks_n, 1)
            bar_w    = round(inc / max_inc * 100)
            gap_cls  = " style='color:var(--red)'" if thru < inc * 0.7 else ""
            note = ""
            if d == 0:  # Monday
                note = " <span style='color:var(--orange);font-size:0.75rem'>← weekend backlog lands here</span>"
            elif d == 4:  # Friday
                note = " <span style='color:var(--muted);font-size:0.75rem'>← lighter close day</span>"
            rows += f"""<tr>
              <td><strong>{DOW_NAMES[d]}</strong>{note}</td>
              <td>
                <div style="display:flex;align-items:center;gap:8px">
                  <div style="flex:1;background:var(--surface);border:1px solid var(--border);
                              border-radius:3px;height:14px;overflow:hidden">
                    <div style="width:{bar_w}%;height:100%;background:var(--indigo)"></div>
                  </div>
                  <span class="num" style="min-width:28px">{avg_inc}</span>
                </div>
              </td>
              <td class="num"{gap_cls}>{avg_thru}</td>
              <td class="num" style="color:{'var(--red)' if thru < inc * 0.7 else 'var(--green)'}">
                {"▼ gap" if thru < inc * 0.7 else "✓"}
              </td>
            </tr>"""
        return f"""<table>
          <thead><tr>
            <th>Day</th>
            <th>Avg incoming/day ({LOOKBACK_WEEKS}w)</th>
            <th>Avg solved/day</th>
            <th>Balance</th>
          </tr></thead>
          <tbody>{rows}</tbody>
        </table>
        <p style="color:var(--muted);font-size:0.75rem;margin-top:4px">
          Monday carries weekend inflow (Sat+Sun reviews + email replies queued overnight).
          Gap rows (▼) = throughput under 70% of incoming that day.
        </p>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Team Capacity — Private</title>
<style>
  :root {{
    --bg:      #0f172a;
    --surface: #1e293b;
    --border:  #334155;
    --text:    #e2e8f0;
    --muted:   #94a3b8;
    --indigo:  #6366f1;
    --orange:  #f97316;
    --green:   #10b981;
    --red:     #f43f5e;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font: 14px/1.6 system-ui, sans-serif; padding: 24px; }}
  h1 {{ font-size: 1.3rem; margin-bottom: 4px; }}
  .eyebrow {{ color: var(--muted); font-size: 0.8rem; margin-bottom: 32px; }}
  .warning {{ background: #7c2d12; border: 1px solid #ea580c; border-radius: 6px;
              padding: 10px 16px; margin-bottom: 28px; font-size: 0.85rem; color: #fed7aa; }}
  h2 {{ font-size: 1rem; color: var(--muted); text-transform: uppercase; letter-spacing: .06em;
        margin: 32px 0 12px; border-bottom: 1px solid var(--border); padding-bottom: 6px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px;
           padding: 14px 18px; min-width: 160px; flex: 1; }}
  .card__label {{ font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
                  letter-spacing: .05em; margin-bottom: 4px; }}
  .card__value {{ font-size: 1.8rem; font-weight: 700; line-height: 1; }}
  .card__sub {{ font-size: 0.75rem; color: var(--muted); margin-top: 4px; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 24px; }}
  th {{ text-align: left; padding: 8px 12px; background: var(--surface);
        color: var(--muted); font-size: 0.75rem; text-transform: uppercase;
        border-bottom: 1px solid var(--border); }}
  td {{ padding: 8px 12px; border-bottom: 1px solid var(--border); vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  .num {{ font-variant-numeric: tabular-nums; }}
  small {{ color: var(--muted); font-size: 0.75rem; }}
  .incoming-row {{ background: rgba(99,102,241,.08); }}
  .section-divider {{ color: var(--muted); font-style: italic; font-size: 0.8rem;
                      padding: 12px 12px 4px; border-top: 1px solid var(--border); }}
</style>
</head>
<body>
<h1>Team Capacity Dashboard</h1>
<div class="eyebrow">Generated {gen} · {LOOKBACK_WEEKS}-week lookback · Local only — do not share</div>

<div class="warning">
  ⚠️ Agent data is anonymized — agents appear as capacity units only. Do not share agent ID mappings.
</div>

<h2>Incoming Tickets / Day</h2>
<div class="cards">{summary_cards()}</div>

<h2>Day-of-Week Pattern — Incoming vs Throughput</h2>
{dow_section()}

<h2>Agent Throughput vs Incoming — {LOOKBACK_WEEKS}w ({gen})</h2>
<p style="color:var(--muted);font-size:0.8rem;margin-bottom:10px">
  Agent rows = tickets assigned to that agent (all statuses), by creation week. Matches Zendesk Analytics. Incoming = all tickets created. Work days = 5/wk.
</p>
{agent_cap_table()}

<h2>Avg Time Spent / Ticket (Time Tracking app)</h2>
<p style="color:var(--muted);font-size:0.8rem;margin-bottom:10px">
  Total agent time logged per ticket via the Time Tracking app. Averaged across all agents, by brand.
</p>
{time_spent_table()}

<h2>First Reply Time by Brand & Agent</h2>
<p style="color:var(--muted);font-size:0.8rem;margin-bottom:10px">
  Calendar time from ticket creation to first agent reply. Not handle time — full resolution time
  is not used because the pending-first workflow (48h bump) inflates it to days.
</p>
{frt_table()}

</body>
</html>"""


def main():
    creds    = zd_creds()
    today    = dt.date.today()
    since    = today - dt.timedelta(weeks=LOOKBACK_WEEKS)
    aht_since = today - dt.timedelta(weeks=AHT_WEEKS)

    tickets, auth, sub = fetch_tickets(creds, since)
    print(f"Total tickets: {len(tickets)}")

    aht_by_id = fetch_metrics(tickets, auth, sub, aht_since)
    print(f"AHT samples: {len(aht_by_id)}")

    agent_map = anonymize_agents(tickets)
    print(f"Agents: {len(agent_map)}")
    for aid, label in sorted(agent_map.items(), key=lambda x: x[1]):
        print(f"  {label}: assignee_id={aid}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    html = build_html(tickets, aht_by_id, agent_map, today)
    OUT.write_text(html)
    print(f"Written → {OUT.resolve()}")


if __name__ == "__main__":
    main()
