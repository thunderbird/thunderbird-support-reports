#!/usr/bin/env python3
"""Macro usage report for Thunderbird support.

Pulls macro definitions + ticket data from Zendesk and generates a
comprehensive local HTML dashboard covering usage, CSAT, agent breakdown,
trends, co-occurrence, and KB article opportunities.

Output: ~/Documents/Claude/macro_report/latest.html  (local only — not committed)

Usage:
  python3 scripts/macro_report.py               # last 90 days
  python3 scripts/macro_report.py --days 30
  python3 scripts/macro_report.py --out /tmp/macros.html
"""
import argparse, base64, datetime as dt, html as _html, json
import re, statistics, sys, urllib.parse, urllib.request
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from tbpro_daily import zd_creds

DEFAULT_DAYS = 90
DEFAULT_OUT  = Path.home() / "Documents" / "Claude" / "macro_report" / "latest.html"
ET = __import__('zoneinfo').ZoneInfo("America/New_York")

URL_RE = re.compile(r'https?://', re.I)


# ── Zendesk helpers ───────────────────────────────────────────────────────────

def zd_get(url, auth):
    req = urllib.request.Request(url, headers={"Authorization": auth, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.load(r)


def zd_paginate(url, auth, key, max_pages=10):
    results, page = [], 0
    while url and page < max_pages:
        d = zd_get(url, auth)
        results.extend(d.get(key, []))
        url = d.get("next_page")
        page += 1
    return results


# ── Fetch data ────────────────────────────────────────────────────────────────

def fetch_macros(creds):
    auth = "Basic " + base64.b64encode(f"{creds['email']}/token:{creds['token']}".encode()).decode()
    sub  = creds["subdomain"]
    macros = zd_paginate(
        f"https://{sub}.zendesk.com/api/v2/macros.json?per_page=100&active=true",
        auth, "macros"
    )
    result = {}
    for m in macros:
        tag = None
        has_url = False
        for a in (m.get("actions") or []):
            if a.get("field") == "current_tags":
                tag = a.get("value", "")
            v = str(a.get("value") or "")
            if URL_RE.search(v):
                has_url = True
        result[m["id"]] = {
            "title": m.get("title", ""),
            "tag": tag,
            "has_url": has_url,
            "raw": m,
        }
    return auth, sub, result


def fetch_tickets(auth, sub, since_iso):
    q = urllib.parse.urlencode({"query": f"type:ticket created>={since_iso}", "per_page": 100})
    tickets = zd_paginate(
        f"https://{sub}.zendesk.com/api/v2/search.json?{q}",
        auth, "results"
    )
    return [t for t in tickets if
            "closed_by_merge" not in (t.get("tags") or []) and
            (t.get("subject") or "").strip().lower() != "test" and
            t.get("submitter_id") == t.get("requester_id")]


def fetch_agent_names(auth, sub, agent_ids):
    names = {}
    for aid in agent_ids:
        try:
            u = zd_get(f"https://{sub}.zendesk.com/api/v2/users/{aid}.json", auth)
            names[aid] = u.get("user", {}).get("name", f"Agent {aid}")
        except Exception:
            names[aid] = f"Agent {aid}"
    return names


# ── Build stats ───────────────────────────────────────────────────────────────

def build(macros, tickets, days):
    # tag → macro info
    tag_to_macro = {m["tag"]: m for m in macros.values() if m["tag"]}

    # Per-ticket: which macros applied?
    ticket_data = []
    for t in tickets:
        tags = set(t.get("tags") or [])
        applied = [tag_to_macro[tg] for tg in tags if tg in tag_to_macro]
        csat = (t.get("satisfaction_rating") or {}).get("score")  # 'good'/'bad'/None
        created = t.get("created_at", "")
        updated = t.get("updated_at", "")
        try:
            aht = (dt.datetime.fromisoformat(updated.replace("Z","+00:00")) -
                   dt.datetime.fromisoformat(created.replace("Z","+00:00"))).total_seconds() / 3600
            aht = aht if 0 < aht < 24*90 else None
        except Exception:
            aht = None
        ticket_data.append({
            "id":      t["id"],
            "subject": t.get("subject",""),
            "status":  t.get("status",""),
            "csat":    csat,
            "aht":     aht,
            "assignee": t.get("assignee_id"),
            "brand":   t.get("brand_id"),
            "created": created[:10],
            "tags":    tags,
            "applied": applied,
            "n_macros": len(applied),
        })

    # Per-macro stats
    macro_stats = defaultdict(lambda: {
        "count":0,"good":0,"bad":0,"aht":[],"solved":0,"agents":Counter(),"weeks":Counter()
    })
    for td in ticket_data:
        for m in td["applied"]:
            key = m["title"]
            s = macro_stats[key]
            s["count"] += 1
            if td["csat"] == "good": s["good"] += 1
            if td["csat"] == "bad":  s["bad"]  += 1
            if td["aht"] is not None: s["aht"].append(td["aht"])
            if td["status"] == "solved": s["solved"] += 1
            if td["assignee"]: s["agents"][td["assignee"]] += 1
            if td["created"]:
                d = dt.date.fromisoformat(td["created"])
                ws = (d - dt.timedelta(days=d.weekday())).isoformat()
                s["weeks"][ws] += 1

    # Agent × macro matrix
    agent_macro = defaultdict(Counter)  # agent_id → {macro_title: count}
    for td in ticket_data:
        if td["assignee"]:
            for m in td["applied"]:
                agent_macro[td["assignee"]][m["title"]] += 1

    # Co-occurrence
    cooccur = Counter()
    for td in ticket_data:
        titles = sorted(m["title"] for m in td["applied"])
        for i in range(len(titles)):
            for j in range(i+1, len(titles)):
                cooccur[(titles[i], titles[j])] += 1

    # Uncovered tickets (no macro applied)
    uncovered = [td for td in ticket_data if not td["applied"]]

    # Multi-macro tickets (3+)
    multi = sorted([td for td in ticket_data if td["n_macros"] >= 3],
                   key=lambda x: -x["n_macros"])

    # Coverage rate
    coverage = sum(1 for td in ticket_data if td["applied"]) / len(ticket_data) * 100 if ticket_data else 0

    # KB flag: high-volume macros with no URL in reply
    kb_candidates = sorted(
        [(title, s["count"]) for title, s in macro_stats.items()
         if s["count"] >= 5 and not (
             tag_to_macro.get(
                 next((m["tag"] for m in macros.values() if m["title"]==title), None), {}
             ).get("has_url", True)
         )],
        key=lambda x: -x[1]
    )

    # All unique agents
    all_agents = set()
    for td in ticket_data:
        if td["assignee"]: all_agents.add(td["assignee"])

    return {
        "macro_stats": macro_stats,
        "agent_macro": agent_macro,
        "all_agents":  all_agents,
        "cooccur":     cooccur,
        "uncovered":   uncovered,
        "multi":       multi,
        "coverage":    coverage,
        "ticket_data": ticket_data,
        "kb_candidates": kb_candidates,
        "macros":      macros,
        "days":        days,
        "total":       len(ticket_data),
    }


# ── Render HTML ───────────────────────────────────────────────────────────────

def h(s): return _html.escape(str(s) if s is not None else "")


def pct(good, bad):
    n = good + bad
    return f"{good/n*100:.0f}%" if n else "—"


def render(data, agent_names, sub):
    ms     = data["macro_stats"]
    agents = data["all_agents"]
    gen    = dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")

    def zd_link(tid):
        return f"https://{sub}.zendesk.com/agent/tickets/{tid}"

    # ── Macro leaderboard ──
    macro_rows = ""
    for title, s in sorted(ms.items(), key=lambda x: -x[1]["count"]):
        aht  = f"{statistics.median(s['aht']):.1f}h" if s["aht"] else "—"
        csat = pct(s["good"], s["bad"])
        solved_pct = f"{s['solved']/s['count']*100:.0f}%" if s["count"] else "—"
        macro_rows += (
            f"<tr><td>{h(title)}</td>"
            f"<td class='num'>{s['count']}</td>"
            f"<td class='num'>{csat}</td>"
            f"<td class='num'>{aht}</td>"
            f"<td class='num'>{solved_pct}</td>"
            f"<td class='num'>{s['good']}</td>"
            f"<td class='num'>{s['bad']}</td></tr>\n"
        )

    # ── Agent × macro heatmap ──
    top_macros = [t for t, _ in sorted(ms.items(), key=lambda x: -x[1]["count"])[:15]]
    agent_rows = ""
    for aid in sorted(agents, key=lambda a: -sum(data["agent_macro"][a].values())):
        name = agent_names.get(aid, f"#{aid}")
        am = data["agent_macro"][aid]
        total_agent = sum(am.values())
        cells = "".join(
            f"<td class='num'>{am.get(m,0) or ''}</td>" for m in top_macros
        )
        agent_rows += f"<tr><td>{h(name)}</td><td class='num'>{total_agent}</td>{cells}</tr>\n"
    heatmap_headers = "".join(f"<th style='font-size:.65rem;writing-mode:vertical-rl;max-width:28px'>{h(m[:25])}</th>" for m in top_macros)

    # ── Co-occurrence ──
    cooccur_rows = ""
    for (a, b), n in data["cooccur"].most_common(20):
        cooccur_rows += f"<tr><td>{h(a)}</td><td>{h(b)}</td><td class='num'>{n}</td></tr>\n"

    # ── Multi-macro tickets ──
    multi_rows = ""
    for td in data["multi"][:30]:
        macros_str = " · ".join(m["title"] for m in td["applied"])
        multi_rows += (
            f"<tr><td><a href='{zd_link(td['id'])}' target='_blank' style='color:var(--accent)'>#{td['id']}</a></td>"
            f"<td style='font-size:.8rem'>{h(td['subject'][:60])}</td>"
            f"<td class='num'>{td['n_macros']}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{h(macros_str[:80])}</td></tr>\n"
        )

    # ── KB candidates ──
    kb_rows = ""
    for title, count in data["kb_candidates"]:
        kb_rows += (
            f"<tr><td>{h(title)}</td>"
            f"<td class='num'>{count}</td>"
            f"<td style='color:var(--orange);font-size:.8rem'>No URL in reply — add a link to support.thunderbird.net</td></tr>\n"
        )

    # ── Uncovered tickets sample ──
    uncov_rows = ""
    for td in data["uncovered"][:25]:
        uncov_rows += (
            f"<tr><td><a href='{zd_link(td['id'])}' target='_blank' style='color:var(--accent)'>#{td['id']}</a></td>"
            f"<td style='font-size:.8rem'>{h(td['subject'][:70])}</td>"
            f"<td class='num'>{td['created']}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{h(td['status'])}</td></tr>\n"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Macro Report — Thunderbird Support</title>
<style>
  :root{{--bg:#0f1117;--surface:#1a1d27;--border:#2a2d3a;--text:#e2e8f0;--muted:#94a3b8;
         --accent:#6366f1;--green:#22c55e;--red:#ef4444;--orange:#f59e0b;}}
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;padding:2rem;max-width:1300px;margin:0 auto}}
  h1{{font-size:1.4rem;margin-bottom:.2rem}}
  h2{{font-size:1rem;font-weight:600;margin:2rem 0 .75rem;color:var(--text)}}
  .subtitle{{color:var(--muted);font-size:.85rem;margin-bottom:2rem}}
  .stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:1rem;margin-bottom:2rem}}
  .card{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.1rem;border-top:3px solid var(--accent)}}
  .card .label{{font-size:.7rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;margin-bottom:.3rem}}
  .card .value{{font-size:1.6rem;font-weight:700}}
  .card .sub{{font-size:.75rem;color:var(--muted);margin-top:.2rem}}
  .box{{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:1.5rem;margin-bottom:1.5rem;overflow-x:auto}}
  .box h3{{font-size:.78rem;color:var(--muted);text-transform:uppercase;letter-spacing:.08em;margin-bottom:1rem}}
  table{{width:100%;border-collapse:collapse;font-size:.85rem}}
  th{{text-align:left;color:var(--muted);font-weight:500;padding:.45rem .6rem;border-bottom:1px solid var(--border);font-size:.73rem;text-transform:uppercase;white-space:nowrap}}
  td{{padding:.5rem .6rem;border-bottom:1px solid var(--border)}}
  tr:last-child td{{border-bottom:none}}
  .num{{text-align:right;font-variant-numeric:tabular-nums}}
  .sortable{{cursor:pointer}}
  .footer{{margin-top:2rem;font-size:.72rem;color:var(--muted);border-top:1px solid var(--border);padding-top:1rem}}
  .warn{{color:var(--orange)}}
</style>
</head>
<body>
<h1>Macro Report — Thunderbird Support</h1>
<p class="subtitle">Last {data['days']} days · Generated {gen} · {data['total']} tickets analysed · Local only — not published</p>

<div class="stats">
  <div class="card">
    <div class="label">Total Tickets</div>
    <div class="value">{data['total']}</div>
    <div class="sub">in range</div>
  </div>
  <div class="card">
    <div class="label">Macro Coverage</div>
    <div class="value">{data['coverage']:.0f}%</div>
    <div class="sub">tickets with ≥1 macro</div>
  </div>
  <div class="card">
    <div class="label">Unique Macros Used</div>
    <div class="value">{len(ms)}</div>
    <div class="sub">of 162 defined</div>
  </div>
  <div class="card">
    <div class="label">No Macro Applied</div>
    <div class="value">{len(data['uncovered'])}</div>
    <div class="sub">{len(data['uncovered'])/data['total']*100:.0f}% uncovered</div>
  </div>
  <div class="card">
    <div class="label">KB Gaps</div>
    <div class="value">{len(data['kb_candidates'])}</div>
    <div class="sub">macros missing KB links</div>
  </div>
  <div class="card">
    <div class="label">Multi-macro (3+)</div>
    <div class="value">{len(data['multi'])}</div>
    <div class="sub">complex tickets</div>
  </div>
</div>

<div class="box">
  <h3>Macro leaderboard — click headers to sort</h3>
  <table id="leaderboard">
    <thead><tr>
      <th class="sortable" onclick="sortTable('leaderboard',0,'str')">Macro ↕</th>
      <th class="num sortable" onclick="sortTable('leaderboard',1,'num')">Count ↕</th>
      <th class="num sortable" onclick="sortTable('leaderboard',2,'str')">CSAT ↕</th>
      <th class="num sortable" onclick="sortTable('leaderboard',3,'str')">Median AHT ↕</th>
      <th class="num sortable" onclick="sortTable('leaderboard',4,'str')">Solved % ↕</th>
      <th class="num sortable" onclick="sortTable('leaderboard',5,'num')">👍</th>
      <th class="num sortable" onclick="sortTable('leaderboard',6,'num')">👎</th>
    </tr></thead>
    <tbody>{macro_rows or "<tr><td colspan='7' style='color:var(--muted)'>No macro data</td></tr>"}</tbody>
  </table>
</div>

<div class="box">
  <h3>Agent × macro usage (top 15 macros by volume)</h3>
  <table>
    <thead><tr>
      <th>Agent</th><th class="num">Total</th>
      {heatmap_headers}
    </tr></thead>
    <tbody>{agent_rows or "<tr><td colspan='17' style='color:var(--muted)'>No agent data</td></tr>"}</tbody>
  </table>
</div>

<div class="box">
  <h3>🔗 KB article opportunities — high-volume macros with no support.thunderbird.net link in reply</h3>
  <p style="font-size:.78rem;color:var(--muted);margin-bottom:.75rem">These macros are used frequently but the reply text contains no URL. Adding a KB link would reduce follow-up questions.</p>
  <table>
    <thead><tr><th>Macro</th><th class="num">Uses</th><th>Suggestion</th></tr></thead>
    <tbody>{kb_rows or "<tr><td colspan='3' style='color:var(--muted)'>All high-volume macros have URLs — nice work.</td></tr>"}</tbody>
  </table>
</div>

<div class="box">
  <h3>Macro co-occurrence — top 20 pairs applied together</h3>
  <table>
    <thead><tr><th>Macro A</th><th>Macro B</th><th class="num">Times together</th></tr></thead>
    <tbody>{cooccur_rows or "<tr><td colspan='3' style='color:var(--muted)'>No co-occurrence data</td></tr>"}</tbody>
  </table>
</div>

<div class="box">
  <h3>Multi-macro tickets (3+ macros applied) — potential workflow gaps</h3>
  <table>
    <thead><tr><th>Ticket</th><th>Subject</th><th class="num">Macros</th><th>Applied</th></tr></thead>
    <tbody>{multi_rows or "<tr><td colspan='4' style='color:var(--muted)'>No multi-macro tickets</td></tr>"}</tbody>
  </table>
</div>

<div class="box">
  <h3>Uncovered tickets — no macro applied (sample of 25)</h3>
  <p style="font-size:.78rem;color:var(--muted);margin-bottom:.75rem">These tickets were handled without any macro. Review for new macro candidates.</p>
  <table>
    <thead><tr><th>Ticket</th><th>Subject</th><th class="num">Created</th><th>Status</th></tr></thead>
    <tbody>{uncov_rows or "<tr><td colspan='4' style='color:var(--muted)'>All tickets had macros — great coverage!</td></tr>"}</tbody>
  </table>
</div>

<div class="footer">
  Data: Zendesk · all brands · last {data['days']} days · {data['total']} tickets
  (excl. closed_by_merge, test, agent-created) · Local only — never published.
</div>

<script>
function sortTable(id, col, type) {{
  const t = document.getElementById(id);
  const tb = t.querySelector('tbody');
  const rows = Array.from(tb.querySelectorAll('tr'));
  const dir = t.dataset.sortCol==col && t.dataset.sortDir=='asc' ? 'desc' : 'asc';
  t.dataset.sortCol=col; t.dataset.sortDir=dir;
  rows.sort((a,b)=>{{
    const av=(a.cells[col]||{{}}).innerText.trim()||'';
    const bv=(b.cells[col]||{{}}).innerText.trim()||'';
    const c=type==='num'?(parseFloat(av)||0)-(parseFloat(bv)||0):av.localeCompare(bv);
    return dir==='asc'?c:-c;
  }});
  rows.forEach(r=>tb.appendChild(r));
}}
</script>
</body>
</html>"""


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--days", type=int, default=DEFAULT_DAYS)
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()

    since = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()

    print("Fetching macro definitions…", file=sys.stderr)
    creds = zd_creds()
    auth, sub, macros = fetch_macros(creds)
    print(f"  {len(macros)} active macros", file=sys.stderr)

    print(f"Fetching tickets since {since}…", file=sys.stderr)
    tickets = fetch_tickets(auth, sub, since)
    print(f"  {len(tickets)} tickets", file=sys.stderr)

    print("Building stats…", file=sys.stderr)
    data = build(macros, tickets, args.days)

    print(f"Fetching {len(data['all_agents'])} agent names…", file=sys.stderr)
    agent_names = fetch_agent_names(auth, sub, data["all_agents"])

    print("Rendering…", file=sys.stderr)
    html = render(data, agent_names, sub)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out}", file=sys.stderr)
    print(f"\nOpen: open '{out}'", file=sys.stderr)


if __name__ == "__main__":
    main()
