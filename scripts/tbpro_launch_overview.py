#!/usr/bin/env python3
"""Thundermail full-launch overview — May 4 → today.

Generates a standalone HTML dashboard showing daily + weekly ticket volumes,
invite milestones, and theme breakdown across the full Early Bird launch.

Usage:
  python3 scripts/tbpro_launch_overview.py
  python3 scripts/tbpro_launch_overview.py --out lisa/daily/launch_overview.html
"""
import argparse, base64, datetime as dt, json, re, sys, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from brand_summary import classify

LAUNCH_DATE    = "2026-05-04"
INVITEES_TOTAL = 2066   # ~66 Early Bird + 500 Wave 1 + 1500 Wave 2

MILESTONES = [
    {"date": "2026-05-04", "label": "Early Bird (~66 invites)", "color": "#6366f1"},
    {"date": "2026-06-03", "label": "Flight 2 Wave 1 (500)",    "color": "#f97316"},
    {"date": "2026-06-04", "label": "Flight 2 Wave 2 (1,500)",  "color": "#ef4444"},
]

EXCLUDE_IDS = {5441, 5866}

DEFAULT_OUT = Path("lisa/daily/launch_overview.html")


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
            f"&per_page=100&page={page}",
            auth
        )
        results.extend(d.get("results", []))
        if not d.get("next_page") or page >= 10:
            break
        page += 1
    return [
        t for t in results
        if "closed_by_merge" not in (t.get("tags") or [])
        and (t.get("subject") or "").strip().lower() != "test"
        and t.get("submitter_id") == t.get("requester_id")
        and int(t.get("id", 0)) not in EXCLUDE_IDS
        and int(t.get("problem_id") or 0) not in EXCLUDE_IDS
    ]


def build(tickets):
    today     = dt.date.today()
    start     = dt.date.fromisoformat(LAUNCH_DATE)
    all_dates = []
    d = start
    while d <= today:
        all_dates.append(d.isoformat())
        d += dt.timedelta(days=1)

    by_date  = Counter(t["created_at"][:10] for t in tickets)
    daily    = [by_date.get(d, 0) for d in all_dates]

    by_week  = defaultdict(int)
    for date, count in by_date.items():
        dd = dt.date.fromisoformat(date)
        ws = (dd - dt.timedelta(days=dd.weekday())).isoformat()
        by_week[ws] += count
    weekly = dict(sorted(by_week.items()))

    theme_counts = Counter()
    for t in tickets:
        text = f"{t.get('subject','')}\n{t.get('description','')}"
        primary, _ = classify(text)
        theme_counts[primary] += 1

    return {
        "dates":   all_dates,
        "daily":   daily,
        "weekly":  weekly,
        "total":   len(tickets),
        "themes":  dict(theme_counts.most_common(10)),
        "today":   today.isoformat(),
    }


def render(data):
    dates_js   = json.dumps(data["dates"])
    counts_js  = json.dumps(data["daily"])
    milestones_js = json.dumps(MILESTONES)

    weekly_rows = ""
    for ws, n in data["weekly"].items():
        we = (dt.date.fromisoformat(ws) + dt.timedelta(days=6)).isoformat()
        weekly_rows += f'<tr><td>{ws} → {we}</td><td class="num">{n}</td></tr>\n'

    theme_rows = ""
    total = data["total"]
    for theme, n in data["themes"].items():
        pct = int(n / total * 100) if total else 0
        theme_rows += (
            f'<tr><td>{theme}</td><td class="num">{n}</td>'
            f'<td><div style="height:6px;background:#6366f1;border-radius:3px;width:{pct}%"></div></td></tr>\n'
        )

    contact_rate = f"{total / INVITEES_TOTAL * 100:.1f}%"
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M ET")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thundermail — Launch Overview · Early Bird → Today</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.0.1/chartjs-plugin-annotation.min.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;
    --text:#e2e8f0;--muted:#94a3b8;--accent:#6366f1;
    --green:#22c55e;--red:#ef4444;--orange:#f97316;
  }}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:'Inter',sans-serif;padding:2rem;max-width:1100px;margin:0 auto}}
  h1{{font-size:1.5rem;margin-bottom:.25rem}}
  .subtitle{{color:var(--muted);font-size:.85rem;margin-bottom:2rem}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:1rem;margin-bottom:2rem}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.25rem;border-top:3px solid var(--accent)}}
  .card .label{{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.4rem}}
  .card .value{{font-size:1.8rem;font-weight:700}}
  .card .sub{{font-size:.78rem;color:var(--muted);margin-top:.2rem}}
  .box{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem}}
  .box h2{{font-size:.85rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem}}
  canvas{{max-height:320px}}
  table{{width:100%;border-collapse:collapse;font-size:.875rem}}
  th{{text-align:left;color:var(--muted);font-weight:500;padding:.5rem .75rem;border-bottom:1px solid var(--border);font-size:.75rem;text-transform:uppercase}}
  td{{padding:.55rem .75rem;border-bottom:1px solid var(--border)}}
  tr:last-child td{{border-bottom:none}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .legend{{display:flex;flex-wrap:wrap;gap:1rem;margin-bottom:1.5rem}}
  .legend-item{{display:flex;align-items:center;gap:.4rem;font-size:.8rem;color:var(--muted)}}
  .legend-dot{{width:10px;height:10px;border-radius:2px;flex-shrink:0}}
  .footer{{margin-top:2rem;font-size:.72rem;color:var(--muted);border-top:1px solid var(--border);padding-top:1rem}}
</style>
</head>
<body>
<h1>Thundermail — Launch Overview</h1>
<p class="subtitle">Early Bird (May 4) → today ({data["today"]}) &nbsp;·&nbsp; Generated {generated} &nbsp;·&nbsp; PII-redacted</p>

<div class="stats">
  <div class="card">
    <div class="label">Total Tickets</div>
    <div class="value">{total}</div>
    <div class="sub">since May 4, 2026</div>
  </div>
  <div class="card">
    <div class="label">Total Invitees</div>
    <div class="value">{INVITEES_TOTAL:,}</div>
    <div class="sub">Early Bird + Flight 2</div>
  </div>
  <div class="card">
    <div class="label">Contact Rate</div>
    <div class="value">{contact_rate}</div>
    <div class="sub">tickets / invitees</div>
  </div>
</div>

<div class="legend">
  {''.join(f'<div class="legend-item"><div class="legend-dot" style="background:{m["color"]}"></div>{m["label"]}</div>' for m in MILESTONES)}
</div>

<div class="box">
  <h2>Daily ticket volume</h2>
  <canvas id="dailyChart"></canvas>
</div>

<div style="display:grid;grid-template-columns:1fr 1fr;gap:1.5rem;margin-bottom:1.5rem">
  <div class="box">
    <h2>Weekly volumes</h2>
    <table>
      <thead><tr><th>Week</th><th class="num">Tickets</th></tr></thead>
      <tbody>{weekly_rows}</tbody>
    </table>
  </div>
  <div class="box">
    <h2>Theme breakdown (all tickets)</h2>
    <table>
      <thead><tr><th>Theme</th><th class="num">Count</th><th style="width:80px"></th></tr></thead>
      <tbody>{theme_rows}</tbody>
    </table>
  </div>
</div>

<div class="footer">
  Data: Zendesk · Thunderbird Pro brand · May 4, 2026 → {data["today"]} ·
  Excludes: closed_by_merge, test, agent-created, and known infrastructure tickets (5441, 5866 + linked incidents).
  <a href="latest.html" style="color:var(--accent)">→ Flight 2 live report</a>
</div>

<script>
const dates     = {dates_js};
const counts    = {counts_js};
const milestones= {milestones_js};

const annotations = {{}};
milestones.forEach((m, i) => {{
  const idx = dates.indexOf(m.date);
  if (idx < 0) return;
  annotations['line' + i] = {{
    type: 'line',
    xMin: idx, xMax: idx,
    borderColor: m.color,
    borderWidth: 2,
    borderDash: [4, 3],
    label: {{
      display: true,
      content: m.label,
      position: 'start',
      backgroundColor: m.color,
      color: '#fff',
      font: {{ size: 10 }},
      padding: 4,
    }}
  }};
}});

new Chart(document.getElementById('dailyChart'), {{
  type: 'bar',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'Tickets',
      data: counts,
      backgroundColor: dates.map(d => {{
        if (d === '2026-06-04') return '#ef444480';
        if (d === '2026-06-03') return '#f9731680';
        if (d === '2026-05-04') return '#6366f180';
        return '#6366f140';
      }}),
      borderColor: dates.map(d => {{
        if (d === '2026-06-04') return '#ef4444';
        if (d === '2026-06-03') return '#f97316';
        if (d === '2026-05-04') return '#6366f1';
        return '#6366f1';
      }}),
      borderWidth: 1,
      borderRadius: 3,
    }}]
  }},
  options: {{
    responsive: true,
    plugins: {{
      legend: {{ display: false }},
      annotation: {{ annotations }},
      tooltip: {{
        callbacks: {{
          title: ctx => ctx[0].label,
          afterLabel: ctx => {{
            const m = milestones.find(m => m.date === ctx.label);
            return m ? '⚡ ' + m.label : '';
          }}
        }}
      }}
    }},
    scales: {{
      x: {{
        ticks: {{ color: '#94a3b8', maxTicksLimit: 12, maxRotation: 45 }},
        grid: {{ color: '#2a2d3a' }}
      }},
      y: {{
        beginAtZero: true,
        ticks: {{ color: '#94a3b8', stepSize: 1 }},
        grid: {{ color: '#2a2d3a' }}
      }}
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

    print("Fetching tickets since launch…", file=sys.stderr)
    creds   = load_creds()
    tickets = fetch_tickets(creds)
    print(f"  {len(tickets)} tickets after exclusions", file=sys.stderr)

    data = build(tickets)
    html = render(data)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
