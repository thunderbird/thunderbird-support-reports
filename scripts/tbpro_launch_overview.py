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
from tbpro_daily import github_zendesk_links, zd_creds, WATCH_PROBLEMS, EXCLUDE_IDS as _DAILY_EXCLUDE

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
    # Read Zendesk creds via the shared loader: env vars first (for CI, where
    # there is no creds file), then ~/.config/zendesk/credentials for local use.
    return zd_creds()


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
    """Fetch all non-off-topic ideas. Returns (all_ideas, top10) tuple.
    CLI sort param is unreliable — sort client-side."""
    # Ensure credentials file exists — write from env vars if running in CI
    creds_path = Path.home() / ".featureos.yaml"
    if not creds_path.exists():
        api_key = os.environ.get("FEATUREOS_API_KEY", "")
        jwt = os.environ.get("FEATUREOS_JWT", "")
        if api_key:
            creds_path.write_text(f"api_key: {api_key}\njwt: {jwt}\n")

    q = f"board_id={FEATUREOS_BOARD_ID}&per_page=100&status=all"
    try:
        proc = subprocess.run(
            ["featureos-cli", "posts", "list", "--query", q, "--json"],
            capture_output=True, text=True)
        # featureos-cli sometimes writes JSON to stderr instead of stdout
        raw = proc.stdout or proc.stderr or ""
        out = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", raw).strip()
        idx = out.find("{")
        if idx < 0:
            print(f"WARN: featureos-cli no JSON in output. rc={proc.returncode} raw={raw[:200]!r}", file=sys.stderr)
            return [], []
        out = out[idx:]
        data = json.loads(out)
        if not data.get("success", True):
            print(f"WARN: featureos-cli error: {data.get('message')}", file=sys.stderr)
            return [], []
        posts = data.get("feature_requests", [])
        if not posts:
            print(f"WARN: featureos-cli returned 0 posts. Keys: {list(data.keys())}", file=sys.stderr)
    except Exception as e:
        print(f"WARN: featureos-cli fetch failed: {e}", file=sys.stderr)
        return [], []
    OMIT_STATUSES = {"Off-topic", "By design"}
    filtered = [p for p in posts
                if (p.get("custom_status") or {}).get("title", p.get("status","")) not in OMIT_STATUSES]
    filtered.sort(key=lambda p: p.get("votes_count", 0) + p.get("comments_count", 0), reverse=True)
    return filtered, filtered[:10]


# ── Active blockers ──────────────────────────────────────────────────────────

# Problems tracked in daily report but NOT shown as blockers on launch overview
LAUNCH_WATCH_ONLY = {5679}  # DKIM — tracked but not a launch blocker


def fetch_blockers(auth, sub):
    """Fetch WATCH_PROBLEMS (minus LAUNCH_WATCH_ONLY) as launch blockers.
    A blocker is active if the problem ticket itself is not solved/closed,
    regardless of whether individual incidents are currently open."""
    blockers = []
    for pid in sorted(WATCH_PROBLEMS - LAUNCH_WATCH_ONLY):
        try:
            prob = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{pid}.json", auth).get("ticket", {})
            inc_data = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{pid}/incidents.json", auth)
            incidents = [i for i in inc_data.get("tickets", [])
                         if i.get("status") not in ("solved", "closed")
                         and int(i.get("id", 0)) not in _DAILY_EXCLUDE]
            blockers.append({
                "id": pid,
                "subject": prob.get("subject", ""),
                "status": prob.get("status", ""),
                "open_incidents": incidents,
                "url": f"https://{sub}.zendesk.com/agent/tickets/{pid}",
            })
        except Exception as e:
            print(f"WARN: couldn't fetch blocker #{pid}: {e}", file=sys.stderr)
    return blockers


# ── Build data ────────────────────────────────────────────────────────────────

def build(tickets, aht_mins, frt_mins, ideas_all, ideas_top10, gh_links=None, blockers=None):
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

    # GitHub-linked tickets (zd-gh tag)
    gh_tickets = [t for t in tickets if "zd-gh" in (t.get("tags") or [])]
    gh_by_repo = defaultdict(list)
    for t in gh_tickets:
        # Repo inferred from subject prefix "Repo Issue: ..." or just group all
        gh_by_repo["linked"].append(t)

    return {
        "dates": dates, "daily": daily,
        "cumulative": cumulative, "cum_contact": cum_contact,
        "weekly": dict(sorted(by_week.items())),
        "total": len(tickets),
        "wave_stats": wave_stats,
        "aht": aht_data, "frt": frt_data,
        "avg_rate": avg_rate, "surge_pct": surge_pct,
        "themes": dict(theme_counts.most_common(12)),
        "ideas": ideas_top10,
        "ideas_count": len(ideas_all),
        "gh_tickets": gh_tickets,
        "gh_links": gh_links or {},
        "blockers": blockers or [],
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
        _product_tags = {"Thundermail", "Appointment", "Send"}
        _all_tags = [t.get("name","") for t in (p.get("tags") or []) if t.get("name")]
        _sorted_tags = sorted(_all_tags, key=lambda x: (0 if x in _product_tags else 1, x))
        tags = ", ".join(_sorted_tags)[:50] or "—"
        status = (p.get("custom_status") or {}).get("title") or p.get("status","")
        votes = p.get("votes_count", 0)
        comments = p.get("comments_count", 0)
        score = votes + comments
        # Flag when discussion outpaces votes — hidden demand signal
        hot = comments > votes
        hot_badge = " <span title='Comments exceed votes — high discussion signal' style='color:var(--orange);font-size:.7rem'>🔥</span>" if hot else ""
        idea_rows += (
            f"<tr>"
            f"<td class='num'><strong>{votes}</strong></td>"
            f"<td class='num' style='color:var(--muted)'>{comments}</td>"
            f"<td class='num' style='font-weight:600'>{score}</td>"
            f"<td><a href='{p.get('url','')}' target='_blank' style='color:var(--accent)'>"
            f"{p.get('title','')[:65]}</a>{hot_badge}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{tags}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{status}</td></tr>\n"
        )

    # GitHub-linked ticket rows — open/pending visible, solved collapsed
    def gh_row(t, sub="tbpro"):
        sc = {"solved": "var(--green)", "open": "var(--accent)", "pending": "var(--orange)"}.get(t.get("status",""), "var(--muted)")
        tid = t["id"]
        issues = data.get("gh_links", {}).get(tid, [])
        issue_links = " ".join(
            f'<a href="{i["url"]}" target="_blank" style="color:var(--muted);font-size:.75rem">'
            f'{i["repo"].split("/")[1]}#{i["number"]}</a>'
            for i in issues
        )
        status = t.get("status","")
        return (
            f"<tr title='Status: {status}'>"
            f"<td><a href='https://{sub}.zendesk.com/agent/tickets/{tid}' target='_blank' style='color:{sc}'>#{tid}</a>"
            f"{(' &nbsp;' + issue_links) if issue_links else ''}</td>"
            f"<td style='font-size:.8rem'>{t.get('subject','')[:70]}</td>"
            f"<td style='font-size:.75rem;color:var(--muted)'>{t.get('created_at','')[:10]}</td>"
            f"</tr>\n"
        )

    gh_sorted  = sorted(data["gh_tickets"], key=lambda x: x["created_at"], reverse=True)
    gh_open    = [t for t in gh_sorted if t.get("status") not in ("solved", "closed")]
    gh_done    = ([t for t in gh_sorted if t.get("status") == "solved"] +
                  [t for t in gh_sorted if t.get("status") == "closed"])

    gh_open_rows = "".join(gh_row(t) for t in gh_open) or "<tr><td colspan='3' style='color:var(--muted)'>None</td></tr>"
    gh_done_rows = "".join(gh_row(t) for t in gh_done)

    gh_solved_block = ""
    if gh_done:
        gh_solved_block = (
            f"<tr><td colspan='3' style='padding:0'>"
            f"<details style='padding:.5rem .65rem'>"
            f"<summary style='cursor:pointer;font-size:.78rem;color:var(--muted);list-style:none'>"
            f"▶ {len(gh_done)} solved / closed ticket(s) — click to expand"
            f"</summary>"
            f"<table style='width:100%;margin-top:.5rem'>"
            f"<tbody>{gh_done_rows}</tbody>"
            f"</table>"
            f"</details>"
            f"</td></tr>"
        )

    gh_rows = gh_open_rows + gh_solved_block

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
<div style="display:flex;align-items:center;gap:1rem;margin-bottom:.25rem">
  <img src="https://tb.pro/media/img/thunderbird/thunderbird-256.png" alt="Thunderbird" style="width:48px;height:48px">
  <h1>Thundermail — Full Launch Overview</h1>
</div>
<p class="subtitle">Early Bird (May 4, 2026) → {data["today"]} &nbsp;·&nbsp; {TOTAL_INVITEES:,} invitees total &nbsp;·&nbsp; Generated {gen}</p>

{"".join(
    f'<div style="background:#2d1a1a;border:1px solid #7f1d1d;border-left:4px solid #ef4444;border-radius:8px;'
    f'padding:.9rem 1.25rem;margin-bottom:1rem;font-size:.9rem;line-height:1.7">'
    f'<span style="color:#ef4444;font-weight:700">🔴 BLOCK — Known problem #{b["id"]}: '
    f'<a href="{b["url"]}" target="_blank" style="color:#ef4444">{b["subject"][:80]}</a></span>'
    f'<br><span style="color:#fca5a5">{len(b["open_incidents"])} open incident(s): '
    + (", ".join(f'<a href="https://tbpro.zendesk.com/agent/tickets/{i["id"]}" target="_blank" style="color:#fca5a5">#{i["id"]}</a>' for i in b["open_incidents"])
       if b["open_incidents"] else "<em>problem ticket still open — monitoring for new incidents</em>")
    + "</span></div>"
    for b in data.get("blockers", []) if b.get("status") not in ("solved", "closed")
)}

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
    <div class="sub">from ticket created to first reply</div>
  </div>
  <div class="card">
    <div class="label">Ideas Since Launch</div>
    <div class="value">{data['ideas_count']}</div>
    <div class="sub">on FeatureOS (excl. off-topic)</div>
  </div>
  <div class="card orange">
    <div class="label">GitHub Escalation Rate</div>
    <div class="value">{round(len(data['gh_tickets'])/total*100) if total else 0}%</div>
    <div class="sub">{len(data['gh_tickets'])} of {total} tickets linked to a GitHub issue</div>
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
    <p style="font-size:.72rem;color:var(--muted);margin-top:.75rem">Based on {avg_rate}% average across Flight 2 Waves 1+2 (0.6% and 1.3% respectively). <strong>Note:</strong> Wave 2 is only {(dt.date.today() - dt.date(2026,6,4)).days} days old — its true rate may be higher as tickets arrive over 7–14 days. Early Bird rate ({data['wave_stats'][0]['rate']}%) was inflated by misdirected non-subscribers, not a reliable baseline.</p>
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
  <h3>Top 10 ideas — all time, sorted by votes + comments · 🔥 = comments exceed votes (high-discussion signal)</h3>
  <table id="ideasTable">
    <thead><tr>
      <th class="num" onclick="sortTable('ideasTable',0,'num')" style="cursor:pointer;white-space:nowrap">Votes ↕</th>
      <th class="num" onclick="sortTable('ideasTable',1,'num')" style="cursor:pointer;white-space:nowrap">Comments ↕</th>
      <th class="num" onclick="sortTable('ideasTable',2,'num')" style="cursor:pointer;white-space:nowrap">Score ↕</th>
      <th onclick="sortTable('ideasTable',3,'str')" style="cursor:pointer;white-space:nowrap">Idea ↕</th>
      <th>Tags</th>
      <th onclick="sortTable('ideasTable',5,'str')" style="cursor:pointer;white-space:nowrap">Status ↕</th>
    </tr></thead>
    <tbody>{idea_rows if idea_rows else "<tr><td colspan='7' style='color:var(--muted);text-align:center'>No ideas fetched</td></tr>"}</tbody>
  </table>
</div>

<div class="box" style="margin-top:1.5rem">
  <h3>Tickets linked to GitHub — {len(data['gh_tickets'])} of {total} ({round(len(data['gh_tickets'])/total*100) if total else 0}%)</h3>
  <p style="font-size:.8rem;color:var(--muted);margin-bottom:.75rem">Tickets tagged <code>zd-gh</code> — linked to a GitHub issue in the thunderbird org via gz# marker.</p>
  <table>
    <thead><tr><th>Ticket</th><th>Subject</th><th>Created</th></tr></thead>
    <tbody>{gh_rows if gh_rows else "<tr><td colspan='4' style='color:var(--muted)'>None</td></tr>"}</tbody>
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
      fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5,
      pointHoverBackgroundColor: '#22c55e', pointHoverBorderColor: '#fff',
      borderWidth: 2,
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

function sortTable(tableId, colIdx, type) {{
  const table = document.getElementById(tableId);
  const tbody = table.querySelector('tbody');
  const rows  = Array.from(tbody.querySelectorAll('tr'));
  const dir   = table.dataset.sortCol == colIdx && table.dataset.sortDir == 'asc' ? 'desc' : 'asc';
  table.dataset.sortCol = colIdx;
  table.dataset.sortDir = dir;
  rows.sort((a, b) => {{
    const av = a.cells[colIdx]?.innerText.trim() || '';
    const bv = b.cells[colIdx]?.innerText.trim() || '';
    const cmp = type === 'num'
      ? (parseFloat(av.replace(/[^0-9.-]/g,'')) || 0) - (parseFloat(bv.replace(/[^0-9.-]/g,'')) || 0)
      : av.localeCompare(bv);
    return dir === 'asc' ? cmp : -cmp;
  }});
  rows.forEach(r => tbody.appendChild(r));
}}
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
    ideas_all, ideas_top10 = fetch_ideas()
    print(f"  {len(ideas_all)} total ideas (excl. off-topic), top 10 in table", file=sys.stderr)

    print("Fetching GitHub issue links…", file=sys.stderr)
    gh_links = github_zendesk_links()
    print(f"  {sum(len(v) for v in gh_links.values())} GitHub links across {len(gh_links)} tickets", file=sys.stderr)

    print("Fetching active blockers…", file=sys.stderr)
    blockers = fetch_blockers(auth, sub)
    active = sum(1 for b in blockers if b.get("status") not in ("solved", "closed"))
    print(f"  {active} active blocker(s) with open incidents", file=sys.stderr)

    data = build(tickets, aht_mins, frt_mins, ideas_all, ideas_top10, gh_links, blockers)
    html = render(data)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
