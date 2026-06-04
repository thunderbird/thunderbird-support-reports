"""Build HTML dashboard and CSV export for March 2026."""

import json, csv
from pathlib import Path

BASE = Path(__file__).parent.parent
ANALYSIS = BASE / 'lisa' / '2026' / 'march_analysis.json'
data = json.loads(ANALYSIS.read_text())

# ── CSV Export ────────────────────────────────────────────────────────────────

rows = [
    # Support Metrics
    ('March','2026','Support Metrics','Private Support','Overall CSAT',None,75.0,None,6.0,'up',None,None,None,'Zendesk',''),
    ('March','2026','Support Metrics','Private Support','CSAT Donor Support',None,69.0,None,5.7,'up',None,None,None,'Zendesk',''),
    ('March','2026','Support Metrics','Private Support','CSAT TB Pro',None,100.0,None,0.0,'flat',None,None,None,'Zendesk',''),
    ('March','2026','Support Metrics','Private Support','Total Tickets',267,None,-99,-27.0,'down',None,None,None,'Zendesk',''),
    ('March','2026','Support Metrics','Private Support','Donor Support Tickets',246,None,-91,-27.0,'down',None,None,None,'Zendesk',''),
    ('March','2026','Support Metrics','Private Support','TB Pro Tickets',21,None,-8,-27.6,'down',None,None,None,'Zendesk',''),
    # Community - Desktop
    ('March','2026','Community Support','Desktop SUMO','Total Questions',960,None,-49,-4.9,'down',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Desktop SUMO','Solved %',None,18.0,None,-2.0,'down',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Desktop SUMO','Ignored %',None,49.0,None,29.0,'up',None,None,None,'SUMO','Spike from 20% in Feb'),
    ('March','2026','Community Support','Desktop SUMO','Trusted Contributor %',None,49.0,None,1.0,'flat',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Desktop SUMO','Overall Solved Rate',None,67.0,None,-1.0,'down',None,None,None,'SUMO',''),
    # Community - Android
    ('March','2026','Community Support','Android SUMO','Total Questions',66,None,6,10.0,'up',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Android SUMO','Solved %',None,17.0,None,-1.0,'down',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Android SUMO','Ignored %',None,24.0,None,-6.0,'down',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Android SUMO','Trusted Contributor %',None,55.0,None,20.0,'up',None,None,None,'SUMO',''),
    ('March','2026','Community Support','Android SUMO','Overall Solved Rate',None,72.0,None,19.0,'up',None,None,None,'SUMO',''),
    # Android Reviews - Overview
    ('March','2026','Android Reviews','Overview','Total Reviews',451,None,42,10.3,'up',3.81,374,77,'Play Store',''),
    ('March','2026','Android Reviews','Overview','TB Reviews',374,None,None,None,None,3.87,374,None,'Play Store',''),
    ('March','2026','Android Reviews','Overview','K-9 Reviews',77,None,None,None,None,3.52,None,77,'Play Store','First full month'),
    ('March','2026','Android Reviews','Overview','Replies to 1-3 Star',215,None,74,52.5,'up',None,None,None,'Play Store',''),
    ('March','2026','Android Reviews','Overview','Improved Ratings',9,None,5,125.0,'up',None,None,None,'Play Store',''),
    ('March','2026','Android Reviews','Overview','Unchanged Ratings',4,None,3,300.0,'up',None,None,None,'Play Store',''),
    ('March','2026','Android Reviews','Overview','Decreased Ratings',1,None,1,None,'up',None,None,None,'Play Store',''),
    # Friction points
]

friction_order = ['Push / Notification Sync','Spam Filter Absent','Crashes & Freezes',
                  'Calendar Missing','Stuck Outbox / Send Failure','QR / Settings Import','Email Headers / Print']
history_neg = {'Push / Notification Sync':[19,23,31],'Spam Filter Absent':[0,0,10],
               'Crashes & Freezes':[0,0,6],'Calendar Missing':[0,0,6],
               'Stuck Outbox / Send Failure':[0,0,4],'QR / Settings Import':[0,0,4],
               'Email Headers / Print':[0,0,2]}

for theme in friction_order:
    s = data['friction'][theme]
    rows.append(('March','2026','Android Reviews','Friction',theme,
                 s['total'],None,None,None,None,s['avg_rating'],s['tb_count'],s['k9_count'],'Play Store',
                 f"neg:{s['negative']}"))

csv_path = BASE / 'lisa' / '2026' / 'march.csv'
with open(csv_path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(['month','year','section','category','metric','value_number','value_percent',
                'mom_change_number','mom_change_percent','mom_direction','avg_rating',
                'tb_count','k9_count','source','notes'])
    w.writerows(rows)
print(f'✓ CSV saved: {csv_path}')

# ── HTML Dashboard ────────────────────────────────────────────────────────────

REPORT_BASE = 'https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/march.md'
FRICTION_ANCHORS = {
    'Push / Notification Sync':    '#top-3-friction-points',
    'Spam Filter Absent':          '#top-3-friction-points',
    'Crashes & Freezes':           '#top-3-friction-points',
    'Calendar Missing':            '#android-reviews',
    'Stuck Outbox / Send Failure': '#android-reviews',
    'QR / Settings Import':        '#android-reviews',
    'Email Headers / Print':       '#android-reviews',
}
CROSS_CHANNEL_NOTES = {
    'Crashes & Freezes':       'confirmed in Android Forum — volunteers directing users to older F-Droid build as workaround',
    'Spam Filter Absent':      'related: "Filters like Desktop" surfacing in Android Forum (3 questions) — same gap, different entry point',
    'Push / Notification Sync':'not surfacing in Android Forum — users leaving reviews rather than asking for help',
}

friction_rows_html = ''
for theme in friction_order:
    s = data['friction'][theme]
    hist = history_neg[theme]
    trend_str = f"{hist[0]} → {hist[1]} → {hist[2]}"
    arrow = '📈' if hist[2] > hist[1] else ('📉' if hist[2] < hist[1] else '➡️')
    neg_class = 'high' if s['negative'] >= 10 else ('med' if s['negative'] >= 5 else 'low')
    anchor = FRICTION_ANCHORS.get(theme, '')
    link = f'{REPORT_BASE}{anchor}'
    note = CROSS_CHANNEL_NOTES.get(theme, '')
    note_html = f'<br><span style="font-size:.72rem;color:var(--muted)">↔ {note}</span>' if note else ''
    friction_rows_html += f"""
      <tr>
        <td><a href="{link}" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)"><strong>{theme}</strong></a>{note_html}</td>
        <td class="num">{s['total']}</td>
        <td class="num neg-{neg_class}">{s['negative']}</td>
        <td class="num">{s['avg_rating']:.2f}★</td>
        <td class="num">{s['tb_count']}</td>
        <td class="num">{s['k9_count']}</td>
        <td class="trend">{trend_str} {arrow}</td>
      </tr>"""

LANG_NAMES = {
    'en':'English','de':'German','it':'Italian','es':'Spanish','fr':'French',
    'ru':'Russian','ja':'Japanese','pl':'Polish','pt':'Portuguese','nl':'Dutch',
    'el':'Greek','zh-Hans':'Chinese (Simplified)','tr':'Turkish','ar':'Arabic','id':'Indonesian',
}
top_langs = [('en',172),('de',90),('it',30),('es',25),('fr',23),('ru',20),('ja',16),('pl',13),('pt',9),('nl',7)]
lang_rows_html = ''
for code, count in top_langs:
    pct = count / 451 * 100
    name = LANG_NAMES.get(code, code)
    lang_rows_html += f'<tr><td>{name}</td><td class="num">{count}</td><td><div class="bar" style="width:{pct*3:.0f}px"></div></td></tr>'

dist_tb = data['rating_dist_tb']
dist_k9 = data['rating_dist_k9']
tb_labels = [str(k) for k in range(1,6)]
tb_vals = [dist_tb.get(str(k),0) for k in range(1,6)]
k9_vals = [dist_k9.get(str(k),0) for k in range(1,6)]

wins_html = ''
wins_data = [
    ('UI / Design Praise', data['wins']['UI / Design Praise']),
    ('Speed / Performance', data['wins']['Speed / Performance']),
    ('Privacy / Open Source', data['wins']['Privacy / Open Source']),
]
for name, s in wins_data:
    wins_html += f"""
    <div class="win-card">
      <h3>{name}</h3>
      <p class="win-stat">{s['total']} mentions &nbsp;·&nbsp; avg {s['avg_rating']:.2f}★ &nbsp;·&nbsp; TB: {s['tb_count']} &nbsp; K-9: {s['k9_count']}</p>
    </div>"""

html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>March 2026 — Thunderbird Support Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #6366f1;
    --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
    --orange: #f97316; --sky: #38bdf8;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding: 2rem; max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
  .subtitle {{ color: var(--muted); font-size: .9rem; margin-bottom: 2rem; }}
  /* Section headers */
  .section-header {{ display: flex; align-items: center; gap: .75rem; margin: 2.5rem 0 1rem; padding-bottom: .6rem; border-bottom: 2px solid var(--sc); }}
  .section-header h2 {{ font-size: 1.1rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--sc); }}
  .section-header .sh-meta {{ font-size: .8rem; color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; }}
  /* Cards */
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; border-top: 3px solid var(--sc, var(--border)); }}
  .card .label {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .4rem; }}
  .card .value {{ font-size: 2rem; font-weight: 700; }}
  .card .change {{ font-size: .8rem; color: var(--muted); margin-top: .25rem; }}
  /* Colour helpers */
  .up {{ color: var(--green); }} .down {{ color: var(--red); }} .flat {{ color: var(--yellow); }} .muted {{ color: var(--muted); }}
  /* Inner sections */
  .box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
  .box h3 {{ font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 1rem; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
  @media(max-width:700px){{ .two-col {{ grid-template-columns: 1fr; }} }}
  /* Tables */
  table {{ width: 100%; border-collapse: collapse; font-size: .875rem; }}
  th {{ text-align: left; color: var(--muted); font-weight: 500; padding: .5rem .75rem; border-bottom: 1px solid var(--border); font-size: .75rem; text-transform: uppercase; }}
  td {{ padding: .6rem .75rem; border-bottom: 1px solid var(--border); }}
  tr:last-child td {{ border-bottom: none; }}
  .num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .trend {{ color: var(--muted); font-size: .8rem; }}
  .neg-high {{ color: var(--red); font-weight: 700; }}
  .neg-med {{ color: var(--yellow); font-weight: 600; }}
  .neg-low {{ color: var(--text); }}
  .bar {{ height: 8px; background: var(--accent); border-radius: 4px; display: inline-block; }}
  canvas {{ max-height: 260px; }}
  /* Alerts / callouts */
  .alert {{ background: #2d1a1a; border: 1px solid #7f1d1d; border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }}
  .alert-title {{ color: var(--red); font-weight: 700; margin-bottom: .35rem; }}
  .alert p {{ font-size: .9rem; color: #fca5a5; }}
  .experiment {{ background: #1a1f2d; border: 1px solid #3730a3; border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }}
  .experiment-title {{ color: #818cf8; font-weight: 700; margin-bottom: .35rem; }}
  .experiment p {{ font-size: .9rem; color: var(--muted); }}
  /* Filter bar */
  .filter-bar {{ display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .filter-btn {{ background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: .35rem .9rem; font-size: .8rem; cursor: pointer; color: var(--muted); transition: all .15s; }}
  .filter-btn:hover {{ border-color: var(--text); color: var(--text); }}
  .filter-btn.active {{ color: var(--bg); font-weight: 600; }}
  .filter-section {{ transition: opacity .15s; }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.5rem;margin-bottom:.25rem">
  <h1>March 2026 — Thunderbird Support Dashboard</h1>
  <a href="https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/2026/march.md" style="font-size:.85rem;color:var(--accent);text-decoration:none;">← Full report on GitHub</a>
</div>
<p class="subtitle">Generated 2026-04-14</p>

<div class="filter-bar">
  <button class="filter-btn active" style="background:var(--accent);border-color:var(--accent)" onclick="filterSection('all', this)">All</button>
  <button class="filter-btn" onclick="filterSection('donor', this)">Donor Care</button>
  <button class="filter-btn" onclick="filterSection('tbpro', this)">TB Pro</button>
  <button class="filter-btn" onclick="filterSection('android', this)">Android Reviews</button>
  <button class="filter-btn" onclick="filterSection('sumo', this)">Community Support</button>
</div>

<div class="filter-section" data-section="donor">
<!-- ═══════════════════════════════════════════════
     DONOR CARE
═══════════════════════════════════════════════ -->
<div class="section-header" style="--sc: var(--green)">
  <h2>Donor Care</h2>
  <span class="sh-meta">246 tickets · Zendesk</span>
</div>
<div class="grid" style="--sc: var(--green)">
  <div class="card">
    <div class="label">Donor CSAT</div>
    <div class="value up">69%</div>
    <div class="change up">+5.7 pts MoM ↑</div>
  </div>
  <div class="card">
    <div class="label">Overall CSAT</div>
    <div class="value up">75%</div>
    <div class="change up">+6.0 pts MoM ↑</div>
  </div>
  <div class="card">
    <div class="label">Donor Tickets</div>
    <div class="value">246</div>
    <div class="change down">-27% MoM ↓</div>
  </div>
  <div class="card">
    <div class="label">Total Tickets</div>
    <div class="value">267</div>
    <div class="change down">-27% MoM ↓</div>
  </div>
</div>
<div class="box">
  <h3>Donor Ticket Topics</h3>
  <table>
    <thead><tr><th>Topic</th><th class="num">Tickets</th><th class="num">CSAT</th></tr></thead>
    <tbody>
      <tr><td>Misdirected tech support</td><td class="num">52</td><td class="num muted">experiment ↗</td></tr>
      <tr><td>Recurring cancellations</td><td class="num">~50</td><td class="num flat">50%</td></tr>
      <tr><td>Fundraising opt-out requests</td><td class="num">19</td><td class="num down">33% ⚠️</td></tr>
      <tr><td>Email / contact updates</td><td class="num">8</td><td class="num up">100%</td></tr>
      <tr><td>Refunds &amp; receipts</td><td class="num">~15</td><td class="num up">67%</td></tr>
    </tbody>
  </table>
</div>
</div><!-- /donor -->

<div class="filter-section" data-section="tbpro">
<!-- ═══════════════════════════════════════════════
     TB PRO
═══════════════════════════════════════════════ -->
<div class="section-header" style="--sc: var(--accent)">
  <h2>TB Pro</h2>
  <span class="sh-meta">21 tickets · Zendesk</span>
</div>
<div class="grid" style="--sc: var(--accent)">
  <div class="card">
    <div class="label">TB Pro CSAT</div>
    <div class="value up">100%</div>
    <div class="change up">Perfect score ✅</div>
  </div>
  <div class="card">
    <div class="label">TB Pro Tickets</div>
    <div class="value">21</div>
    <div class="change down">-28% MoM ↓</div>
  </div>
</div>
<div class="two-col">
  <div class="box">
    <h3>New Ideas — March (13 total)</h3>
    <table>
      <thead><tr><th>Idea</th><th class="num">Votes</th><th>Tag</th></tr></thead>
      <tbody>
        <tr><td><a href="https://ideas.tb.pro/p/sign-in-with-thunderbirdd" target="_blank" style="color:var(--text)">Sign-in with Thunderbird</a></td><td class="num">8</td><td style="color:var(--muted);font-size:.8rem">Accounts &amp; Subscriptions</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/unlimited-aliases" target="_blank" style="color:var(--text)">Unlimited aliases</a></td><td class="num">6</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/agency-plan" target="_blank" style="color:var(--text)">Agency Plan</a></td><td class="num">4</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/server-side-email-filtering" target="_blank" style="color:var(--text)">Server Side Email Filtering</a></td><td class="num">3</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/events-should-be-able-to-end-on-the-next-calendar-day" target="_blank" style="color:var(--text)">Events should end on next calendar day</a></td><td class="num">2</td><td style="color:var(--muted);font-size:.8rem">Appointment</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/gmail-is-ending-pop3-support-you-guys-need-to-get-this-done" target="_blank" style="color:var(--text)">Gmail ending POP3 support</a></td><td class="num">2</td><td style="color:var(--muted);font-size:.8rem">New Feature</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/managed-calendar-with-calendar-managed-availability-phrases" target="_blank" style="color:var(--text)">Managed Calendar availability phrases</a></td><td class="num">2</td><td style="color:var(--muted);font-size:.8rem">Appointment</td></tr>
        <tr><td style="color:var(--muted);font-size:.8rem" colspan="3">+ 6 more at 1 vote each</td></tr>
      </tbody>
    </table>
  </div>
  <div class="box">
    <h3>Top Ideas All-Time</h3>
    <table>
      <thead><tr><th>Idea</th><th class="num">Votes</th><th>Tag</th></tr></thead>
      <tbody>
        <tr><td><a href="https://ideas.tb.pro/p/increase-custom-domains-limit" target="_blank" style="color:var(--text)">Increase custom domains limit</a></td><td class="num">19</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/import-email-calendar-and-contacts-feature" target="_blank" style="color:var(--text)">Import email, calendar &amp; contacts</a></td><td class="num">13</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/appointment-do-not-require-calendar-connection" target="_blank" style="color:var(--text)">Appointment: no calendar required</a></td><td class="num">9</td><td style="color:var(--muted);font-size:.8rem">Appointment</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/sign-in-with-thunderbirdd" target="_blank" style="color:var(--text)">Sign-in with Thunderbird</a></td><td class="num">8</td><td style="color:var(--muted);font-size:.8rem">Accounts &amp; Subscriptions</td></tr>
        <tr><td><a href="https://ideas.tb.pro/p/unlimited-aliases" target="_blank" style="color:var(--text)">Unlimited aliases</a></td><td class="num">6</td><td style="color:var(--muted);font-size:.8rem">Thundermail</td></tr>
      </tbody>
    </table>
  </div>
</div>

</div><!-- /tbpro -->

<div class="filter-section" data-section="android">
<!-- ═══════════════════════════════════════════════
     ANDROID REVIEWS
═══════════════════════════════════════════════ -->
<div class="section-header" style="--sc: var(--orange)">
  <h2>Android Reviews</h2>
  <span class="sh-meta">451 Play Store reviews · TB 374 · K-9 77 · 31 languages</span>
</div>
<div class="alert">
  <div class="alert-title">⚠️ Play Store Rating Drifting Away from 4★ Annual Goal</div>
  <p>Q1 trend: <strong>3.95 → 3.91 → 3.81★</strong> (TB-only). Push notification failures are the primary driver — 19 → 23 → 31 negative mentions across Q1 and still accelerating. Two new friction signals entered the top issues list this month: spam filtering and v17.0 crashes.</p>
</div>
<div class="grid" style="--sc: var(--orange)">
  <div class="card">
    <div class="label">TB Avg Rating</div>
    <div class="value">3.87★</div>
    <div class="change down">-0.04 from Feb ↓</div>
  </div>
  <div class="card">
    <div class="label">K-9 Avg Rating</div>
    <div class="value">3.52★</div>
    <div class="change up">+0.05 from Feb ↑</div>
  </div>
  <div class="card">
    <div class="label">1–3★ Replies</div>
    <div class="value">215</div>
    <div class="change up">Up from 141 ↑</div>
  </div>
  <div class="card">
    <div class="label">Improved Ratings</div>
    <div class="value up">9</div>
    <div class="change">4 unchanged · 1 decreased</div>
  </div>
</div>
<div class="two-col">
  <div class="box">
    <h3>Star Distribution — TB (374 reviews)</h3>
    <canvas id="tbChart"></canvas>
  </div>
  <div class="box">
    <h3>Star Distribution — K-9 (77 reviews)</h3>
    <canvas id="k9Chart"></canvas>
  </div>
</div>
<div class="box">
  <h3>Friction Points <span style="font-weight:400;text-transform:none;font-size:.75rem;color:var(--muted)">&nbsp;— click a theme to see the full story in the report</span></h3>
  <table>
    <thead><tr>
      <th>Theme</th>
      <th class="num">Mentions</th>
      <th class="num">Neg. mentions<br><span style="font-weight:400;font-size:.7rem">1–3★ reviews</span></th>
      <th class="num">Avg ★</th><th class="num">TB</th><th class="num">K-9</th>
      <th>Neg. mentions trend<br><span style="font-weight:400;font-size:.7rem">Jan → Feb → Mar</span></th>
    </tr></thead>
    <tbody>{friction_rows_html}</tbody>
  </table>
</div>
<div class="box">
  <h3>Top 10 Languages — Play Store</h3>
  <table>
    <thead><tr><th>Language</th><th class="num">Reviews</th><th></th></tr></thead>
    <tbody>{lang_rows_html}</tbody>
  </table>
</div>

<div class="box">
  <h3>Definitions</h3>
  <table>
    <tbody>
      <tr><td style="width:160px;color:var(--muted);font-weight:600">Mentions</td><td>Count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.</td></tr>
      <tr><td style="color:var(--muted);font-weight:600">Neg. mentions</td><td>Mentions where the review is 1–3 stars. This is a count of reviews, not a count of star ratings.</td></tr>
      <tr><td style="color:var(--muted);font-weight:600">Avg ★</td><td>Mean star rating (1–5) across all reviews matching that topic — both positive and negative.</td></tr>
      <tr><td style="color:var(--muted);font-weight:600">Neg. mentions trend</td><td>Count of negative mentions (1–3★) for that topic in January, February, and March.</td></tr>
    </tbody>
  </table>
</div>

</div><!-- /android -->

<div class="filter-section" data-section="sumo">
<!-- ═══════════════════════════════════════════════
     COMMUNITY SUPPORT (SUMO)
═══════════════════════════════════════════════ -->
<div class="section-header" style="--sc: var(--sky)">
  <h2>Community Support</h2>
  <span class="sh-meta">SUMO forums</span>
</div>
<div class="two-col">
  <div class="box">
    <h3>Desktop Forum</h3>
    <table>
      <thead><tr><th>Metric</th><th class="num">Value</th><th class="num">MoM</th></tr></thead>
      <tbody>
        <tr><td>Questions (excl. spam)</td><td class="num">931</td><td class="num muted">960 total</td></tr>
        <tr><td>Overall Solved Rate</td><td class="num">67%</td><td class="num down">-1 pt</td></tr>
        <tr><td>Ignored %</td><td class="num down">49%</td><td class="num down">+29 pts ⚠️</td></tr>
        <tr><td>Trusted Contributor %</td><td class="num">49%</td><td class="num flat">flat</td></tr>
        <tr><td>Trusted contributors</td><td class="num">29</td><td class="num"></td></tr>
      </tbody>
    </table>
  </div>
  <div class="box">
    <h3>Android Forum</h3>
    <table>
      <thead><tr><th>Metric</th><th class="num">Value</th><th class="num">MoM</th></tr></thead>
      <tbody>
        <tr><td>Questions (excl. spam)</td><td class="num">54</td><td class="num muted">66 total</td></tr>
        <tr><td>Overall Solved Rate</td><td class="num up">72%</td><td class="num up">+19 pts ↑</td></tr>
        <tr><td>Ignored %</td><td class="num">24%</td><td class="num up">-6 pts</td></tr>
        <tr><td>Trusted Contributor %</td><td class="num up">55%</td><td class="num up">+20 pts</td></tr>
        <tr><td>Trusted contributors</td><td class="num">3</td><td class="num muted">platform34, wsmwk, Yu5tiqX9og</td></tr>
      </tbody>
    </table>
  </div>
</div>
<div class="box" style="margin-top:1rem">
  <h3>Desktop Forum — Top Signals <span style="font-weight:400;text-transform:none;font-size:.75rem;color:var(--muted)">&nbsp;— click a signal to read the full story in the report</span></h3>
  <table>
    <thead><tr>
      <th>Signal</th>
      <th class="num">Questions</th>
      <th class="num">MoM</th>
      <th>Context</th>
    </tr></thead>
    <tbody>
      <tr>
        <td><a href="{REPORT_BASE}#desktop-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">Gmail / Google</a></td>
        <td class="num">69</td>
        <td class="num up">+23%</td>
        <td style="font-size:.8rem;color:var(--muted)">POP3 issues, cert errors, antivirus conflicts, folder repair — highest-volume provider</td>
      </tr>
      <tr>
        <td><a href="{REPORT_BASE}#desktop-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">Yahoo / AOL / AT&amp;T OAuth2</a></td>
        <td class="num">55</td>
        <td class="num up">+38%</td>
        <td style="font-size:.8rem;color:var(--muted)">Yahoo's change broke TB &lt; v148, forcing upgrades; users confused by OAuth2 browser redirect</td>
      </tr>
      <tr>
        <td><a href="{REPORT_BASE}#desktop-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">GMX server incident</a></td>
        <td class="num">7</td>
        <td class="num muted">+250%</td>
        <td style="font-size:.8rem;color:var(--muted)">Provider outage — not a TB issue; resolved when GMX fixed their infrastructure</td>
      </tr>
    </tbody>
  </table>
  <p style="margin:.75rem 0 0;font-size:.8rem;color:var(--muted)">Recurring theme: lack of in-app troubleshooting tools (opt-in telemetry, crash logs) makes diagnosis hard for volunteers and staff.</p>
</div>
<div class="box" style="margin-top:1rem">
  <h3>Android Forum — Top Signals <span style="font-weight:400;text-transform:none;font-size:.75rem;color:var(--muted)">&nbsp;— click a signal to read the full story in the report</span></h3>
  <table>
    <thead><tr>
      <th>Signal</th>
      <th class="num">Questions</th>
      <th>Context</th>
    </tr></thead>
    <tbody>
      <tr>
        <td><a href="{REPORT_BASE}#android-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">Desktop parity (font size, unified folders, scheduled send)</a></td>
        <td class="num">4</td>
        <td style="font-size:.8rem;color:var(--muted)">Font size control removed in UI revamp; unified folders and scheduled send missing</td>
      </tr>
      <tr>
        <td><a href="{REPORT_BASE}#android-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">Filters like Desktop</a><br><span style="font-size:.72rem;color:var(--muted)">↔ Play Store: Spam Filter Absent — #2 friction point, 10 neg mentions</span></td>
        <td class="num">3</td>
        <td style="font-size:.8rem;color:var(--muted)">Message filtering rules ask; Play Store users hit the same gap as a spam problem — same missing feature, different entry point</td>
      </tr>
      <tr>
        <td><a href="{REPORT_BASE}#android-forum" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)">Crash on v17.0 (Android 8 + images)</a><br><span style="font-size:.72rem;color:var(--muted)">↔ Play Store: #3 friction point, 6 neg mentions · K-9 44% of crash reviews</span></td>
        <td class="num" style="color:var(--red)">confirmed</td>
        <td style="font-size:.8rem;color:var(--muted)">~80% of image emails on Android 8; works on Android 12+; fix expected v17.1/v18 · Forum volunteers have workaround (older F-Droid build) that Play Store reviewers never received</td>
      </tr>
    </tbody>
  </table>
  <div class="alert" style="margin-top:1rem">
    <div class="alert-title">⚠️ Push / Notification Sync — absent from this forum</div>
    <p>The #1 Play Store friction point (31 negative mentions, accelerating all Q1) is not surfacing as forum questions. Users hitting push failures appear to be leaving reviews rather than seeking support — no resolution path, higher churn risk.</p>
  </div>
  <p style="margin:.75rem 0 0;font-size:.8rem;color:var(--muted)">Recurring theme: no Troubleshooting Information equivalent on Android; SUMO is hard to use on mobile, keeping question volume low.</p>
</div>
<p style="margin:1rem 0 0;padding:.5rem .9rem;background:#f8fafc;border-left:3px solid #94a3b8;border-radius:4px;font-size:.8rem;color:#6b7280;">⚠️ Community support numbers are under review — methodology may shift slightly next month as we iterate on data collection.</p>

</div><!-- /sumo -->

<script>
function filterSection(key, btn) {{
  document.querySelectorAll('.filter-btn').forEach(b => {{
    b.classList.remove('active');
    b.style.background = '';
    b.style.borderColor = '';
    b.style.color = '';
  }});
  btn.classList.add('active');
  btn.style.background = 'var(--accent)';
  btn.style.borderColor = 'var(--accent)';
  btn.style.color = 'var(--bg)';
  document.querySelectorAll('.filter-section').forEach(s => {{
    s.style.display = (key === 'all' || s.dataset.section === key) ? '' : 'none';
  }});
  history.replaceState(null, '', key === 'all' ? '#' : '#' + key);
}}

window.addEventListener('DOMContentLoaded', () => {{
  const hash = window.location.hash.replace('#', '');
  if (hash) {{
    const btn = document.querySelector(`.filter-btn[onclick*="${{hash}}"]`);
    if (btn) filterSection(hash, btn);
  }}
}});
</script>
<script>
const tbCtx = document.getElementById('tbChart').getContext('2d');
const k9Ctx = document.getElementById('k9Chart').getContext('2d');
const chartDefaults = {{
  type: 'bar',
  options: {{
    responsive: true,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2a2d3a' }} }},
      y: {{ ticks: {{ color: '#94a3b8' }}, grid: {{ color: '#2a2d3a' }} }}
    }}
  }}
}};
new Chart(tbCtx, {{ ...chartDefaults, data: {{
  labels: {json.dumps(tb_labels)},
  datasets: [{{ label: 'Reviews', data: {json.dumps(tb_vals)},
    backgroundColor: ['#ef4444','#f97316','#f59e0b','#22c55e','#6366f1'] }}]
}}}});
new Chart(k9Ctx, {{ ...chartDefaults, data: {{
  labels: {json.dumps(tb_labels)},
  datasets: [{{ label: 'Reviews', data: {json.dumps(k9_vals)},
    backgroundColor: ['#ef4444','#f97316','#f59e0b','#22c55e','#6366f1'] }}]
}}}});
</script>
</body>
</html>"""

html_path = BASE / 'lisa' / '2026' / 'march.html'
html_path.write_text(html)
print(f'✓ Dashboard saved: {html_path}')
