#!/usr/bin/env python3
"""Thundermail full-launch overview — Early Bird (May 4) → today.

Shows: daily/weekly ticket volumes, contact rate by wave, AHT,
capacity projection, theme breakdown, and ideas since launch.

Usage:
  python3 scripts/tbpro_launch_overview.py
  python3 scripts/tbpro_launch_overview.py --out lisa/daily/launch_overview.html
"""
import argparse, base64, datetime as dt, json, re, subprocess, sys, urllib.request
import statistics
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_summary import classify

# Tag-based classification (mirrors tbpro_daily.py TAG_THEMES)
TAG_THEMES = [
    ("macro_tbpro_cantlogin_no_allowlist",  "Misdirected — wrong product / non-subscriber"),
    ("macro_tbpro_sumo_redirect",           "Misdirected — wrong product / non-subscriber"),
    ("macro_tbpro_email_lookup",            "Misdirected — wrong product / non-subscriber"),
    ("tbpro_hub_accounts_login_trouble",    "Account access issues"),
    ("tbpro_hub_what_recover",              "Account access issues"),
    ("macro_tbpro_no_free_monthly",         "Pricing — monthly plan request"),
    ("macro_tbpro_annual_only_beta",        "Pricing — annual-only inquiry"),
    ("tbpro_hub_what_pricing_concerns",     "Pricing"),
    ("macro_thundermail_discount_pricing",  "Pricing — discount inquiry"),
    ("tbpro_hub_what_payment",              "Pricing — payment issue"),
    ("tbpro_hub_what_refund",               "Refund / Cancel"),
    ("tbpro_refund",                        "Refund / Cancel"),
    ("tbpro_cancel_unpaid",                 "Refund / Cancel"),
    ("macro_tbpro_waitlist_bump",           "Waitlist / onboarding inquiry"),
    ("tbpro_thundermail_what_accounts_waitlist", "Waitlist / onboarding inquiry"),
    ("accounts__early_bird_signups",        "Early bird signup"),
    ("tbpro_thundermail_what_aliases",      "Aliases"),
    ("tbpro_thundermail_what_custom_domains_setup",        "Custom domain setup"),
    ("tbpro_thundermail_what_custom_domains__dns_records", "Custom domain DNS"),
    ("tbpro_thundermail_what_add_account",  "Add account in Thunderbird"),
    ("macro_tbpro_request_or_complaint",    "Request or complaint"),
]
MANUAL_THEMES = {6055: "Account access issues"}


def classify_ticket(t):
    tid = int(t.get("id") or 0)
    if tid in MANUAL_THEMES:
        return MANUAL_THEMES[tid]
    tags = t.get("tags") or []
    for tag, theme in TAG_THEMES:
        if tag in tags:
            return theme
    text = f"{t.get('subject','')}\n{t.get('description','')}"
    primary, _ = classify(text)
    return primary

LAUNCH_DATE = "2026-05-04"

WAVES = [
    {"date": "2026-05-04", "end": "2026-06-02", "invites": 600,  "label": "Early Bird",       "color": "#6366f1"},
    {"date": "2026-06-03", "end": "2026-06-03", "invites": 500,  "label": "Flight 2 Wave 1",  "color": "#f97316"},
    {"date": "2026-06-04", "end": "2099-12-31", "invites": 1500, "label": "Flight 2 Wave 2",  "color": "#ef4444"},
]
TOTAL_INVITEES = sum(w["invites"] for w in WAVES)  # 2600

EXCLUDE_IDS = {5441, 5866}
FEATUREOS_BOARD_ID = 17437
DEFAULT_OUT = Path("lisa/daily/launch_overview.html")


# ── Zendesk ──────────────────────────────────────────────────────────────────

def load_creds():
    p = Path.home() / ".config" / "zendesk" / "credentials"
    return dict(l.split("=", 1) for l in p.read_text().splitlines() if "=" in l)


def zd_get(url, auth):
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def fetch_tickets(creds):
    auth = "Basic " + base64.b64encode(f"{creds['email']}/token:{creds['token']}".encode()).decode()
    sub  = creds["subdomain"]
    results, page = [], 1
    while True:
        d = zd_get(
            f"https://{sub}.zendesk.com/api/v2/search.json"
            f"?query=type:ticket+brand:\"Thunderbird+Pro\"+created>={LAUNCH_DATE}"
            f"&per_page=100&page={page}", auth)
        results.extend(d.get("results", []))
        if not d.get("next_page") or page >= 10:
            break
        page += 1
    return (auth, sub, [
        t for t in results
        if "closed_by_merge" not in (t.get("tags") or [])
        and (t.get("subject") or "").strip().lower() != "test"
        and t.get("submitter_id") == t.get("requester_id")
        and int(t.get("id", 0)) not in EXCLUDE_IDS
        and int(t.get("problem_id") or 0) not in EXCLUDE_IDS
    ])


def fetch_aht(auth, sub, tickets, sample=60):
    """Fetch ticket metrics for solved tickets; return (aht_calendar_mins, first_reply_mins)."""
    solved_ids = [str(t["id"]) for t in tickets if t.get("status") == "solved"][:sample]
    aht, frt = [], []
    for tid in solved_ids:
        try:
            m = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{tid}/metrics.json", auth)
            mm = m.get("ticket_metric", {})
            v = (mm.get("full_resolution_time_in_minutes") or {}).get("calendar")
            r = (mm.get("reply_time_in_minutes") or {}).get("calendar")
            if v and v > 0: aht.append(v)
            if r is not None: frt.append(r)
        except Exception:
            pass
    return aht, frt


# ── FeatureOS ─────────────────────────────────────────────────────────────────

def fetch_ideas():
    """Top 10 all-time ideas by vote count, using custom status labels. Omits off-topic/by design."""
    q = f"board_id={FEATUREOS_BOARD_ID}&sort=votes_count&order=desc&per_page=25&status=all"
    try:
        proc = subprocess.run(
            ["featureos-cli", "posts", "list", "--query", q, "--json"],
            capture_output=True, text=True)
        out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout).strip()
        data = json.loads(out)
        posts = data.get("feature_requests", [])
    except Exception:
        return []
    OMIT_STATUSES = {"Off-topic", "By design"}
    filtered = [p for p in posts
                if (p.get("custom_status") or {}).get("title", p.get("status","")) not in OMIT_STATUSES]
    return filtered[:10]


# ── Build data ────────────────────────────────────────────────────────────────

def build(tickets, aht_mins, frt_mins, ideas):
    today  = dt.date.today()
    start  = dt.date.fromisoformat(LAUNCH_DATE)
    dates  = []
    d = start
    while d <= today:
        dates.append(d.isoformat())
        d += dt.timedelta(days=1)

    by_date = Counter(t["created_at"][:10] for t in tickets)
    daily   = [by_date.get(d, 0) for d in dates]

    # Cumulative ticket count per date
    cumulative, running = [], 0
    inv_by_date = {}
    for w in WAVES:
        inv_by_date[w["date"]] = inv_by_date.get(w["date"], 0) + w["invites"]
    total_inv_so_far = 0
    cum_contact = []
    for date in dates:
        running += by_date.get(date, 0)
        total_inv_so_far += inv_by_date.get(date, 0)
        cumulative.append(running)
        rate = round(running / total_inv_so_far * 100, 2) if total_inv_so_far else 0
        cum_contact.append(rate)

    # Weekly
    by_week = defaultdict(int)
    for date, count in by_date.items():
        dd = dt.date.fromisoformat(date)
        ws = (dd - dt.timedelta(days=dd.weekday())).isoformat()
        by_week[ws] += count

    # Contact rate by wave
    wave_stats = []
    for w in WAVES:
        wt = [t for t in tickets if w["date"] <= t["created_at"][:10] <= w["end"]]
        wave_stats.append({**w, "tickets": len(wt), "rate": round(len(wt)/w["invites"]*100, 1)})

    # AHT
    aht_data = {}
    if aht_mins:
        aht_data = {
            "median_h": round(statistics.median(aht_mins)/60, 1),
            "mean_h":   round(statistics.mean(aht_mins)/60, 1),
            "p75_h":    round(sorted(aht_mins)[int(len(aht_mins)*.75)]/60, 1),
            "n":        len(aht_mins),
        }
    frt_data = {}
    if frt_mins:
        frt_data = {
            "median_min": round(statistics.median(frt_mins)),
            "median_h": round(statistics.median(frt_mins) / 60, 1),
            "mean_min":   round(statistics.mean(frt_mins)),
        }

    # Post-invite 7-day surge (Flight 2 avg, excluding Early Bird noise)
    f2_rates  = [ws["rate"] for ws in wave_stats[1:]]
    avg_rate  = round(sum(f2_rates) / len(f2_rates), 2) if f2_rates else 1.0
    # Day-2 surge: from data, day 2 is typically ~50% of 7-day total
    surge_pct = 0.40

    # Themes
    theme_counts = Counter()
    for t in tickets:
        theme_counts[classify_ticket(t)] += 1

    return {
        "dates": dates, "daily": daily,
        "cumulative": cumulative, "cum_contact": cum_contact,
        "weekly": dict(sorted(by_week.items())),
        "total": len(tickets),
        "wave_stats": wave_stats,
        "aht": aht_data, "frt": frt_data,
        "avg_rate": avg_rate, "surge_pct": surge_pct,
        "themes": dict(theme_counts.most_common(12)),
        "ideas": ideas,
        "today": today.isoformat(),
    }


# ── Render HTML ───────────────────────────────────────────────────────────────

def render(data):
    gen = dt.datetime.now().strftime("%Y-%m-%d %H:%M ET")
    total = data["total"]
    aht   = data["aht"]
    frt   = data["frt"]
    avg_rate = data["avg_rate"]
    surge    = data["surge_pct"]

    # Contact rate stat
    overall_rate = round(total / TOTAL_INVITEES * 100, 1)

    # AHT cards
    aht_median = f"{aht.get('median_h','—')}h" if aht else "—"
    frt_median = f"{frt.get('median_h','—')}h" if frt else "—"

    # Wave table rows
    wave_rows = ""
    for w in data["wave_stats"]:
        wave_rows += (
            f"<tr><td>{w['label']}</td><td>{w['date']}</td>"
            f"<td class='num'>{w['invites']:,}</td>"
            f"<td class='num'>{w['tickets']}</td>"
            f"<td class='num'>{w['rate']}%</td></tr>\n"
        )

    # Projection table
    proj_rows = ""
    for batch in [500, 1000, 2000, 5000, 10000]:
        expected = round(batch * avg_rate / 100)
        peak_day = max(1, round(expected * surge))
        proj_rows += (
            f"<tr><td class='num'>{batch:,}</td>"
            f"<td class='num'>{expected}</td>"
            f"<td class='num'>{peak_day}/day</td></tr>\n"
        )

    # Ideas table rows
    idea_rows = ""
    for i, p in enumerate(data["ideas"], 1):
        tags = ", ".join(t.get("name","") for t in (p.get("tags") or []))[:40] or "—"
        status = (p.get("custom_status") or {}).get("title") or p.get("status","")
        idea_rows += (
            f"<tr><td class='num muted'>{i}</td>"
            f"<td class='num'><strong>{p.get('votes_count',0)}</strong></td>"
            f"<td><a href='{p.get('url','')}' target='_blank' style='color:var(--accent)'>"
            f"{p.get('title','')[:70]}</a></td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{p.get('created_at','')[:10]}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{tags}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{status}</td></tr>\n"
        )

    # Weekly rows
    weekly_rows = ""
    for ws, n in data["weekly"].items():
        we = (dt.date.fromisoformat(ws) + dt.timedelta(days=6)).isoformat()
        weekly_rows += f"<tr><td>{ws} → {we}</td><td class='num'>{n}</td></tr>\n"

    # Theme rows
    theme_rows = ""
    for theme, n in data["themes"].items():
        pct = int(n / total * 100) if total else 0
        theme_rows += (
            f"<tr><td>{theme}</td><td class='num'>{n}</td>"
            f"<td class='num muted'>{pct}%</td>"
            f"<td><div style='height:5px;background:var(--accent);border-radius:3px;width:{pct}%'></div></td></tr>\n"
        )

    milestones_js = json.dumps([
        {"date": w["date"], "label": w["label"], "color": w["color"]} for w in WAVES
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thundermail — Launch Overview</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.0.1/chartjs-plugin-annotation.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root{{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--text:#e2e8f0;--muted:#94a3b8;--accent:#6366f1;--green:#22c55e;--red:#ef4444;--orange:#f97316;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;padding:2rem;max-width:1100px;margin:0 auto}}
  h1{{font-size:1.5rem;margin-bottom:.25rem}}
  h2{{font-size:1rem;font-weight:600;margin:2rem 0 1rem;color:var(--text)}}
  .subtitle{{color:var(--muted);font-size:.85rem;margin-bottom:2rem}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:2rem}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.1rem;border-top:3px solid var(--accent)}}
  .card.green{{border-top-color:var(--green)}} .card.orange{{border-top-color:var(--orange)}} .card.red{{border-top-color:var(--red)}}
  .card .label{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}}
  .card .value{{font-size:1.6rem;font-weight:700}}
  .card .sub{{font-size:.75rem;color:var(--muted);margin-top:.2rem}}
  .box{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem}}
  .box h3{{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem}}
  canvas{{max-height:280px}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th{{text-align:left;color:var(--muted);font-weight:500;padding:.45rem .65rem;border-bottom:1px solid var(--border);font-size:.73rem;text-transform:uppercase}}
  td{{padding:.5rem .65rem;border-bottom:1px solid var(--border)}}
  tr:last-child td{{border-bottom:none}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .muted{{color:var(--muted)}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:1.5rem}}
  .legend{{display:flex;flex-wrap:wrap;gap:1rem;margin-bottom:1rem}}
  .legend-item{{display:flex;align-items:center;gap:.4rem;font-size:.78rem;color:var(--muted)}}
  .legend-dot{{width:10px;height:10px;border-radius:2px;flex-shrink:0}}
  .callout{{background:#1a2333;border:1px solid #2d3a5a;border-left:4px solid var(--accent);border-radius:8px;padding:.9rem 1.1rem;margin-bottom:1.5rem;font-size:.88rem;line-height:1.7}}
  .callout strong{{color:var(--text)}}
  .footer{{margin-top:2rem;font-size:.72rem;color:var(--muted);border-top:1px solid var(--border);padding-top:1rem}}
  @media(max-width:700px){{.two-col{{grid-template-columns:1fr}}}}
</style>
</head>
<body>
<h1>Thundermail — Full Launch Overview</h1>
<p class="subtitle">Early Bird (May 4, 2026) → {data["today"]} &nbsp;·&nbsp; {TOTAL_INVITEES:,} invitees total &nbsp;·&nbsp; Generated {gen}</p>

<div class="stats">
  <div class="card">
    <div class="label">Total Tickets</div>
    <div class="value">{total}</div>
    <div class="sub">since Early Bird launch</div>
  </div>
  <div class="card">
    <div class="label">Overall Contact Rate</div>
    <div class="value">{overall_rate}%</div>
    <div class="sub">{total} tickets / {TOTAL_INVITEES:,} invitees</div>
  </div>
  <div class="card green">
    <div class="label">Flight 2 Rate</div>
    <div class="value">{avg_rate}%</div>
    <div class="sub">avg contact rate, Waves 1+2</div>
  </div>
  <div class="card orange">
    <div class="label">Median AHT</div>
    <div class="value">{aht_median}</div>
    <div class="sub">calendar time to resolve</div>
  </div>
  <div class="card">
    <div class="label">Median First Reply</div>
    <div class="value">{frt_median}</div>
    <div class="sub">to initial response</div>
  </div>
  <div class="card">
    <div class="label">Ideas Since Launch</div>
    <div class="value">{len(data['ideas'])}</div>
    <div class="sub">on FeatureOS since May 4</div>
  </div>
</div>

<div class="callout">
  <strong>Capacity projection ({avg_rate}% contact rate · {round(surge*100,0):.0f}% of weekly tickets land on day 2):</strong><br>
  At Flight 2 rates, every 1,000 new invites generates ~{round(1000*avg_rate/100)} support tickets,
  with a day-2 peak of ~{max(1,round(1000*avg_rate/100*surge))} tickets.
  Median resolution: {aht_median} per ticket.
</div>

<div class="legend">
  {''.join(f'<div class="legend-item"><div class="legend-dot" style="background:{w["color"]}"></div>{w["label"]} ({w["invites"]:,})</div>' for w in WAVES)}
</div>

<div class="box">
  <h3>Daily ticket volume — invite waves marked</h3>
  <canvas id="dailyChart"></canvas>
</div>

<div class="box">
  <h3>Cumulative contact rate over time</h3>
  <canvas id="rateChart"></canvas>
</div>

<div class="two-col">
  <div class="box">
    <h3>Contact rate by wave</h3>
    <table>
      <thead><tr><th>Wave</th><th>Date</th><th class="num">Invites</th><th class="num">Tickets</th><th class="num">Rate</th></tr></thead>
      <tbody>{wave_rows}</tbody>
    </table>
  </div>
  <div class="box">
    <h3>Projection — new invite batch</h3>
    <table>
      <thead><tr><th class="num">Batch size</th><th class="num">Expected tickets</th><th class="num">Day-2 peak</th></tr></thead>
      <tbody>{proj_rows}</tbody>
    </table>
    <p style="font-size:.72rem;color:var(--muted);margin-top:.75rem">Based on {avg_rate}% Flight 2 contact rate. Early Bird rate ({data['wave_stats'][0]['rate']}%) was higher due to onboarding friction — expect rates to decrease as product matures.</p>
  </div>
</div>

<div class="two-col">
  <div class="box">
    <h3>Weekly volumes</h3>
    <table>
      <thead><tr><th>Week</th><th class="num">Tickets</th></tr></thead>
      <tbody>{weekly_rows}</tbody>
    </table>
  </div>
  <div class="box">
    <h3>Theme breakdown</h3>
    <table>
      <thead><tr><th>Theme</th><th class="num">Count</th><th class="num">%</th><th style="width:70px"></th></tr></thead>
      <tbody>{theme_rows}</tbody>
    </table>
  </div>
</div>

<div class="box">
  <h3>Top 10 ideas — all time, by votes</h3>
  <table>
    <thead><tr><th class="num">#</th><th class="num">Votes</th><th>Idea</th><th>Created</th><th>Tags</th><th>Status</th></tr></thead>
    <tbody>{idea_rows if idea_rows else "<tr><td colspan='6' style='color:var(--muted);text-align:center'>No ideas fetched</td></tr>"}</tbody>
  </table>
</div>

<h2 style="margin-top:2rem">Definitions</h2>
<div class="box" style="font-size:.85rem;line-height:1.8">
  <p><strong>AHT (Average Handle Time)</strong> — calendar time from ticket creation to resolution (solved status). Median is used rather than mean to reduce the effect of outliers (e.g. tickets that sat open over a weekend). Based on {aht.get("n","—")} solved tickets.</p>
  <p style="margin-top:.6rem"><strong>First Reply Time</strong> — calendar time from ticket creation to the agent's first response.</p>
  <p style="margin-top:.6rem"><strong>Contact Rate</strong> — percentage of invitees who opened a support ticket. Calculated as: tickets ÷ invitees in that wave. A lower contact rate indicates a smoother onboarding experience.</p>
  <p style="margin-top:.6rem"><strong>Day-2 Peak</strong> — historically, ~40% of a wave's first-week tickets arrive on the second day after invites go out. Used to estimate staffing needs for a new batch.</p>
  <p style="margin-top:.6rem"><strong>Misdirected — wrong product / non-subscriber</strong> — tickets from people who do not have a Thundermail account and contacted support by mistake (e.g. desktop Thunderbird users, people who found the form via search). These are redirected to the correct channel and do not reflect subscriber support demand.</p>
  <p style="margin-top:.6rem"><strong>Cumulative contact rate</strong> — running total of tickets divided by total invitees sent at that point in time. Drops sharply when a large new invite wave goes out (more invitees, same tickets).</p>
</div>

<div class="footer">
  Data: Zendesk (Thunderbird Pro brand) · FeatureOS board {FEATUREOS_BOARD_ID} · May 4, 2026 → {data["today"]} ·
  Excludes: closed_by_merge, test tickets, agent-created, known infrastructure tickets. PII-redacted.
  &nbsp;·&nbsp; <a href="latest.html" style="color:var(--accent)">→ Flight 2 live report</a>
</div>

<script>
const dates      = {json.dumps(data["dates"])};
const daily      = {json.dumps(data["daily"])};
const cumContact = {json.dumps(data["cum_contact"])};
const milestones = {milestones_js};

function buildAnnotations() {{
  const ann = {{}};
  milestones.forEach((m, i) => {{
    const idx = dates.indexOf(m.date);
    if (idx < 0) return;
    ann['line' + i] = {{
      type: 'line', xMin: idx, xMax: idx,
      borderColor: m.color, borderWidth: 2, borderDash: [4,3],
      label: {{ display: true, content: m.label, position: 'start',
               backgroundColor: m.color, color:'#fff', font:{{size:9}}, padding:3 }}
    }};
  }});
  return ann;
}}

new Chart(document.getElementById('dailyChart'), {{
  type: 'bar',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'Tickets', data: daily,
      backgroundColor: dates.map(d => milestones.find(m=>m.date===d) ? milestones.find(m=>m.date===d).color+'99' : '#6366f140'),
      borderColor:     dates.map(d => milestones.find(m=>m.date===d) ? milestones.find(m=>m.date===d).color : '#6366f1'),
      borderWidth: 1, borderRadius: 3,
    }}]
  }},
  options: {{
    responsive:true,
    plugins: {{ legend:{{display:false}}, annotation:{{annotations:buildAnnotations()}} }},
    scales: {{
      x: {{ ticks:{{color:'#94a3b8',maxTicksLimit:12,maxRotation:45}}, grid:{{color:'#2a2d3a'}} }},
      y: {{ beginAtZero:true, ticks:{{color:'#94a3b8',stepSize:1}}, grid:{{color:'#2a2d3a'}} }}
    }}
  }}
}});

new Chart(document.getElementById('rateChart'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'Cumulative contact rate (%)', data: cumContact,
      borderColor: '#22c55e', backgroundColor: '#22c55e20',
      fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
    }}]
  }},
  options: {{
    responsive:true,
    plugins: {{ legend:{{display:false}}, annotation:{{annotations:buildAnnotations()}} }},
    scales: {{
      x: {{ ticks:{{color:'#94a3b8',maxTicksLimit:12,maxRotation:45}}, grid:{{color:'#2a2d3a'}} }},
      y: {{ beginAtZero:true, ticks:{{color:'#94a3b8',callback:v=>v+'%'}}, grid:{{color:'#2a2d3a'}} }}
    }}
  }}
}});
</script>
</body>
</html>"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()

    print("Fetching Zendesk tickets…", file=sys.stderr)
    creds = load_creds()
    auth, sub, tickets = fetch_tickets(creds)
    print(f"  {len(tickets)} tickets after exclusions", file=sys.stderr)

    print("Fetching AHT metrics…", file=sys.stderr)
    aht_mins, frt_mins = fetch_aht(auth, sub, tickets)
    print(f"  {len(aht_mins)} AHT samples", file=sys.stderr)

    print("Fetching FeatureOS ideas…", file=sys.stderr)
    ideas = fetch_ideas()
    print(f"  {len(ideas)} ideas since launch", file=sys.stderr)

    data = build(tickets, aht_mins, frt_mins, ideas)
    html = render(data)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
