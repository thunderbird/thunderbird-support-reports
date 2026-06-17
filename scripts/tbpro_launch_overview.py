#!/usr/bin/env python3
"""Thundermail full-launch overview — Early Bird (May 4) → today.

Shows: daily/weekly ticket volumes, contact rate by wave, AHT,
capacity projection, theme breakdown, and ideas since launch.

Usage:
  python3 scripts/tbpro_launch_overview.py
  python3 scripts/tbpro_launch_overview.py --out lisa/daily/launch_overview.html
"""
import argparse, base64, datetime as dt, json, os, re, subprocess, sys, urllib.parse, urllib.request
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


def fetch_aht(auth, sub, tickets, sample=None):
    """Fetch ticket metrics for all solved tickets.
    Returns (aht_calendar_mins, first_reply_mins, aht_by_id).
    aht_by_id: {str(ticket_id): {"mins": int, "week": str}}
    """
    solved = [t for t in tickets if t.get("status") == "solved"]
    aht_list, frt_list = [], []
    aht_by_id = {}
    for t in solved:
        tid = str(t["id"])
        try:
            m = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{tid}/metrics.json", auth)
            mm = m.get("ticket_metric", {})
            v = (mm.get("full_resolution_time_in_minutes") or {}).get("calendar")
            r = (mm.get("reply_time_in_minutes") or {}).get("calendar")
            if v and v > 0:
                aht_list.append(v)
                solved_at = mm.get("solved_at") or t.get("updated_at", "")
                week = ""
                if solved_at:
                    d = dt.date.fromisoformat(solved_at[:10])
                    week = (d - dt.timedelta(days=d.weekday())).isoformat()
                aht_by_id[tid] = {"mins": v, "week": week}
            if r is not None:
                frt_list.append(r)
        except Exception:
            pass
    return aht_list, frt_list, aht_by_id


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
    OMIT_STATUSES = {"Off-topic"}
    filtered = [p for p in posts
                if (p.get("custom_status") or {}).get("title", p.get("status","")) not in OMIT_STATUSES]
    filtered.sort(key=lambda p: p.get("votes_count", 0) + p.get("comments_count", 0), reverse=True)
    return filtered, filtered[:10]


# ── Active blockers ──────────────────────────────────────────────────────────

# Problems tracked in daily report but NOT shown as blockers on launch overview
LAUNCH_WATCH_ONLY = {5679}  # DKIM — tracked but not a launch blocker

# Problems where a fix has been deployed — show in amber "monitoring" state
# Format: {ticket_id: "fix deployed <date>"}
MONITORING_FIXED = {
    6126: "fix deployed June 9",
}

# Manual blockers — not backed by a Zendesk problem ticket.
# Add static_gh_links when GitHub links are available:
#   {"url": "https://github.com/...", "repo": "owner/repo", "number": "123"}
STATIC_BLOCKERS = [
    {
        "id": None,
        "subject": "Updates to signup page blocking invites this week",
        "status": "open",
        "open_incidents": [],
        "all_incident_ids": [],
        "url": None,
        "manual": True,
        "static_gh_links": [{"url": "https://github.com/thunderbird/thunderbird-accounts/issues/970", "repo": "thunderbird/thunderbird-accounts", "number": "970"}],
    },
]


def fetch_blockers(auth, sub):
    """Fetch WATCH_PROBLEMS (minus LAUNCH_WATCH_ONLY) as launch blockers.
    A blocker is active if the problem ticket itself is not solved/closed,
    regardless of whether individual incidents are currently open."""
    blockers = []
    for pid in sorted(WATCH_PROBLEMS - LAUNCH_WATCH_ONLY):
        try:
            prob = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{pid}.json", auth).get("ticket", {})
            inc_data = zd_get(f"https://{sub}.zendesk.com/api/v2/tickets/{pid}/incidents.json", auth)
            all_incidents = [i for i in inc_data.get("tickets", [])
                             if int(i.get("id", 0)) not in _DAILY_EXCLUDE]
            open_incidents = [i for i in all_incidents
                              if i.get("status") not in ("solved", "closed")]
            blockers.append({
                "id": pid,
                "subject": prob.get("subject", ""),
                "status": prob.get("status", ""),
                "open_incidents": open_incidents,
                "all_incident_ids": [i["id"] for i in all_incidents],
                "url": f"https://{sub}.zendesk.com/agent/tickets/{pid}",
            })
        except Exception as e:
            print(f"WARN: couldn't fetch blocker #{pid}: {e}", file=sys.stderr)
    blockers.extend(STATIC_BLOCKERS)
    return blockers


# ── Build data ────────────────────────────────────────────────────────────────

def fetch_csat_stats(auth, sub):
    """Fetch accurate CSAT counts via dedicated Zendesk searches."""
    import datetime as _dt
    F2_LAUNCH  = "2026-06-03"
    EB_LAUNCH  = LAUNCH_DATE
    week_ago   = (_dt.date.today() - _dt.timedelta(days=7)).isoformat()

    def _count(query):
        q = urllib.parse.urlencode({"query": query, "per_page": 1})
        d = zd_get(f"https://{sub}.zendesk.com/api/v2/search.json?{q}", auth)
        return d.get("count", 0)

    def _stats(since):
        g = _count(f'type:ticket brand:"Thunderbird Pro" status:solved satisfaction:good created>={since}')
        b = _count(f'type:ticket brand:"Thunderbird Pro" status:solved satisfaction:bad created>={since}')
        return {"good": g, "bad": b, "n": g+b, "pct": f"{g/(g+b)*100:.0f}%" if g+b else "—"}

    return {
        "eb":   _stats(EB_LAUNCH),
        "f2":   _stats(F2_LAUNCH),
        "week": _stats(week_ago),
    }


def _weekly_csat(tickets):
    """Returns list of {week, volume, good, bad, pct} dicts sorted by week."""
    by_week = defaultdict(lambda: {"volume":0,"good":0,"bad":0})
    for t in tickets:
        d = dt.date.fromisoformat((t.get("created_at","")[:10]) or "2000-01-01")
        ws = (d - dt.timedelta(days=d.weekday())).isoformat()
        by_week[ws]["volume"] += 1
        score = (t.get("satisfaction_rating") or {}).get("score")
        if score == "good": by_week[ws]["good"] += 1
        if score == "bad":  by_week[ws]["bad"]  += 1
    result = []
    for ws, s in sorted(by_week.items()):
        n = s["good"] + s["bad"]
        result.append({
            "week": ws, "volume": s["volume"],
            "good": s["good"], "bad": s["bad"],
            "pct": round(s["good"]/n*100) if n else None
        })
    return result


def build(tickets, aht_mins, frt_mins, ideas_all, ideas_top10, gh_links=None, blockers=None, csat_all=None, aht_by_id=None):
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

    csat_launch = csat_all.get("eb", {})
    csat_week   = csat_all.get("week", {})

    # Themes
    theme_counts = Counter()
    theme_tickets = defaultdict(list)
    for t in tickets:
        theme = classify_ticket(t)
        theme_counts[theme] += 1
        theme_tickets[theme].append(t)

    # AHT distribution buckets
    aht_buckets = {}
    if aht_mins:
        thresholds = [
            ("< 1h",  0,     60),
            ("1–4h",  60,    240),
            ("4–12h", 240,   720),
            ("12–24h",720,   1440),
            ("1–3d",  1440,  4320),
            ("3–7d",  4320,  10080),
            ("7d+",   10080, float("inf")),
        ]
        total_aht = len(aht_mins)
        aht_buckets = {
            label: round(sum(1 for m in aht_mins if lo <= m < hi) / total_aht * 100)
            for label, lo, hi in thresholds
        }

    # GitHub-linked tickets (zd-gh tag)
    gh_tickets = [t for t in tickets if "zd-gh" in (t.get("tags") or [])]
    gh_by_repo = defaultdict(list)
    for t in gh_tickets:
        # Repo inferred from subject prefix "Repo Issue: ..." or just group all
        gh_by_repo["linked"].append(t)

    # Per-theme AHT (for "What drives the long closes")
    BIZ_MINS = 720  # 12h/day × 60 min

    # Merge Pricing sub-themes into a single "Pricing" bucket
    PRICING_CANONICAL = "Pricing"
    PRICING_MERGE = {"Pricing — monthly plan request", "Pricing — annual-only inquiry",
                     "Pricing — discount inquiry", "Pricing — payment issue"}
    for _sub in PRICING_MERGE:
        if _sub in theme_tickets:
            theme_tickets[PRICING_CANONICAL] = (
                list(theme_tickets.get(PRICING_CANONICAL, [])) + theme_tickets.pop(_sub)
            )
            theme_counts[PRICING_CANONICAL] += theme_counts.pop(_sub, 0)

    theme_aht_data = {}
    if aht_by_id:
        for theme, t_list in theme_tickets.items():
            mins_list = [aht_by_id[str(t["id"])]["mins"]
                         for t in t_list if str(t["id"]) in aht_by_id]
            if len(mins_list) >= 2:
                gh = any("zd-gh" in (t.get("tags") or []) for t in t_list)
                med = statistics.median(mins_list)
                biz_days = med / BIZ_MINS
                theme_aht_data[theme] = {
                    "median_mins": med,
                    "biz_days": round(biz_days, 1),
                    "n": len(mins_list),
                    "gh": gh,
                }

    # Weekly AHT trend
    aht_weekly_data = {}
    if aht_by_id:
        aht_week_groups = defaultdict(list)
        for v in aht_by_id.values():
            if v.get("week") and v.get("mins"):
                aht_week_groups[v["week"]].append(v["mins"])
        aht_weekly_data = {
            week: {
                "median_mins": statistics.median(mins),
                "biz_days": round(statistics.median(mins) / BIZ_MINS, 1),
                "cal_days": round(statistics.median(mins) / 1440, 1),
                "n": len(mins),
            }
            for week, mins in sorted(aht_week_groups.items())
        }

    return {
        "dates": dates, "daily": daily,
        "cumulative": cumulative, "cum_contact": cum_contact,
        "weekly": dict(sorted(by_week.items())),
        "total": len(tickets),
        "wave_stats": wave_stats,
        "aht": aht_data, "frt": frt_data,
        "avg_rate": avg_rate, "surge_pct": surge_pct,
        "themes": dict(theme_counts.most_common(12)),
        "theme_tickets": dict(theme_tickets),
        "aht_buckets": aht_buckets,
        "ideas": ideas_top10,
        "ideas_count": len(ideas_all),
        "ideas_all": ideas_all,
        "gh_tickets": gh_tickets,
        "gh_links":     gh_links or {},
        "csat_launch":  csat_launch,
        "csat_week":    csat_week,
        "csat_weekly":  _weekly_csat([t for t in tickets if str(t.get("brand_id","")) == "38173138875795" and (t.get("created_at","") or "") >= "2026-06-03"]),
        "blockers": blockers or [],
        "today": today.isoformat(),
        "theme_aht": theme_aht_data,
        "aht_weekly": aht_weekly_data,
    }


# ── Render HTML ───────────────────────────────────────────────────────────────

def _has_non_ascii(s):
    """Heuristic: subject contains non-ASCII → likely non-English."""
    return bool(s) and any(ord(c) > 127 for c in s)


_PII_PATTERNS = [
    (re.compile(r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b'), '[email]'),
    (re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'), '[IP]'),
]

def _redact(s):
    """Strip email addresses and IPs from a subject line."""
    for pattern, replacement in _PII_PATTERNS:
        s = pattern.sub(replacement, s)
    return s


def _ticket_li(t, sub, gh_links):
    """Build a <li> for a ticket in a theme-tickets list.
    Shows redacted subject — PII stripped, non-English flagged."""
    tid = t["id"]
    subj_raw = (t.get("subject") or "").strip()
    subj = _redact(subj_raw) or classify_ticket(t)
    non_en = _has_non_ascii(subj_raw)
    lang_note = " *(Non-English)*" if non_en else ""
    issues = gh_links.get(tid, [])
    gh_html = ""
    if issues:
        links = " · ".join(
            f'<a href="{i["url"]}" target="_blank">'
            f'{i["repo"].split("/")[1]}#{i["number"]}</a>'
            for i in issues
        )
        gh_html = f'<span class="theme-tickets__gh">{links}</span>'
    return (
        f'<li><a href="https://{sub}.zendesk.com/agent/tickets/{tid}"'
        f' target="_blank">#{tid}</a>'
        f'<span class="theme-tickets__subj"> — {subj}{lang_note}</span>'
        f'{gh_html}</li>\n'
    )


def _theme_row_wrap(theme, n, total, tickets_list, sub, gh_links, extra_class=""):
    """Render a .theme-row-wrap with expandable ticket list."""
    pct = int(n / total * 100) if total else 0
    max_pct = 100  # caller normalises if needed
    bar_w = pct  # bar width = pct of total; caller may override
    cls = f"theme-row {extra_class}".strip()
    li_items = "".join(_ticket_li(t, sub, gh_links) for t in tickets_list)
    count_label = f'{n}<span class="theme-row__pct">{pct}%</span>'
    return f"""<div class="theme-row-wrap">
  <div class="{cls}"><span class="theme-row__name">{theme}</span><span class="theme-row__count">{count_label}</span><div class="theme-row__bar-wrap"><div class="theme-row__bar" style="width:{bar_w}%"></div></div></div>
  <details class="theme-tickets">
    <summary>{n} ticket{"s" if n != 1 else ""}</summary>
    <ul class="theme-tickets__list">
{li_items}    </ul>
  </details>
</div>
"""


def _eng_card(t, sub, gh_links):
    """Render an .eng-card for a GH-linked ticket."""
    tid = t["id"]
    status = t.get("status", "open")
    modifier = "solved" if status in ("solved", "closed") else ("hold" if status == "hold" else "open")
    theme = classify_ticket(t)
    subj_raw = (t.get("subject") or "").strip()
    non_en = _has_non_ascii(subj_raw)
    lang_note = " *(Non-English)*" if non_en else ""
    issues = gh_links.get(tid, [])
    gh_html = " ".join(
        f'<a href="{i["url"]}" target="_blank">'
        f'{i["repo"].split("/")[1]}#{i["number"]}</a>'
        for i in issues
    )
    date = (t.get("created_at") or "")[:10]
    return (
        f'<div class="eng-card eng-card--{modifier}">'
        f'<div>'
        f'<div class="eng-card__id eng-card__id--{modifier}">'
        f'<a href="https://{sub}.zendesk.com/agent/tickets/{tid}" target="_blank">#{tid}</a></div>'
        + (f'<div class="eng-card__gh">{gh_html}</div>' if gh_html else "")
        + f'</div>'
        f'<div class="eng-card__subject">{theme}{lang_note}</div>'
        f'<div class="eng-card__date">{date}</div>'
        f'</div>\n'
    )


def render(data):
    gen = dt.datetime.now().strftime("%Y-%m-%d %H:%M ET")
    total = data["total"]
    aht   = data["aht"]
    frt   = data["frt"]
    avg_rate = data["avg_rate"]
    surge    = data["surge_pct"]
    sub      = "tbpro"  # Zendesk subdomain for link building
    gh_links = data.get("gh_links", {})

    # ── derived stats ──────────────────────────────────────────────────────
    overall_rate  = round(total / TOTAL_INVITEES * 100, 1)
    aht_median    = f"{aht.get('median_h','—')}h" if aht else "—"
    frt_median    = f"{frt.get('median_h','—')}h" if frt else "—"
    csat_launch   = data.get("csat_launch", {})
    csat_week     = data.get("csat_week", {})
    gh_pct        = round(len(data["gh_tickets"]) / total * 100) if total else 0

    # ── rail stats (sidebar quick-view) ───────────────────────────────────
    rail_csat_pct = csat_launch.get("pct", "—")
    rail_csat_cls = "rail-stat--success" if csat_launch.get("n", 0) and int((csat_launch.get("pct") or "0").rstrip("%")) >= 80 else ""

    # ── blocker chips / alert panels ──────────────────────────────────────
    status_chips = ""
    alert_panels = ""
    active_blockers = [b for b in data.get("blockers", []) if b.get("status") not in ("solved", "closed")]
    has_monitoring = any(MONITORING_FIXED.get(b.get("id")) for b in active_blockers)
    has_block      = any(not MONITORING_FIXED.get(b.get("id")) for b in active_blockers)

    if has_monitoring:
        status_chips += '<span class="chip chip--warn"><span class="chip__dot"></span> Monitoring</span>\n'
    if has_block:
        status_chips += '<span class="chip chip--warn"><span class="chip__dot"></span> Active block</span>\n'
    if csat_launch.get("n", 0) and int((csat_launch.get("pct") or "0").rstrip("%")) >= 80:
        status_chips += f'<span class="chip chip--ok"><span class="chip__dot"></span> CSAT {csat_launch["pct"]}</span>\n'

    for b in active_blockers:
        monitoring = MONITORING_FIXED.get(b.get("id"))
        all_gh = list({i["url"]: i for issues in [
            gh_links.get(b.get("id"), []),
            *(gh_links.get(iid, []) for iid in b.get("all_incident_ids", [])),
            b.get("static_gh_links", []),
        ] for i in issues}.values())
        gh_refs = " · ".join(
            f'<a href="{i["url"]}" target="_blank">{i["repo"].split("/")[1]}#{i["number"]}</a>'
            for i in all_gh
        )
        if b.get("manual"):
            head_html = f'{b["subject"]}'
            if gh_refs:
                head_html += f' · {gh_refs}'
            else:
                head_html += ' <span class="alert-panel__meta">— GitHub links pending</span>'
            sub_html = ""
        else:
            zd_url  = b.get("url", f"https://{sub}.zendesk.com/agent/tickets/{b['id']}")
            head_html = f'Known problem <a href="{zd_url}" target="_blank">#{b["id"]}</a>'
            if gh_refs:
                head_html += f' · {gh_refs}'
            if monitoring:
                head_html += f'<span class="alert-panel__meta"> ({monitoring})</span>'
            n_open = len(b.get("open_incidents", []))
            inc_links = ", ".join(
                f'<a href="https://{sub}.zendesk.com/agent/tickets/{i["id"]}" target="_blank">#{i["id"]}</a>'
                for i in b.get("open_incidents", [])
            ) if b.get("open_incidents") else "<em>problem ticket still open — monitoring for new incidents</em>"
            sub_html = f'<div class="alert-panel__sub">{n_open} open incident(s): {inc_links}</div>'

        alert_panels += f"""<div class="alert-panel" role="status">
  <div class="alert-panel__head">{head_html}</div>
  {sub_html}
</div>
"""

    # ── rail watch entries ─────────────────────────────────────────────────
    rail_watch_html = ""
    for b in active_blockers:
        monitoring = MONITORING_FIXED.get(b.get("id"))
        all_gh = list({i["url"]: i for issues in [
            gh_links.get(b.get("id"), []),
            *(gh_links.get(iid, []) for iid in b.get("all_incident_ids", [])),
            b.get("static_gh_links", []),
        ] for i in issues}.values())
        if b.get("manual"):
            issue_label = b["subject"]
            refs_html = " ".join(
                f'<a href="{i["url"]}" target="_blank">{i["repo"].split("/")[1]}#{i["number"]}</a>'
                for i in all_gh
            )
            note_html = ""
        else:
            zd_url = b.get("url", f"https://{sub}.zendesk.com/agent/tickets/{b['id']}")
            issue_label = b.get("subject", f"Problem #{b['id']}")[:60]
            refs_parts = [f'<a href="{zd_url}" target="_blank">#{b["id"]}</a>']
            for i in all_gh:
                refs_parts.append(f'<a href="{i["url"]}" target="_blank">{i["repo"].split("/")[1]}#{i["number"]}</a>')
            refs_html = " · ".join(refs_parts)
            if monitoring:
                refs_html += f'<span class="rail-watch__meta"> · {monitoring}</span>'
            n_open = len(b.get("open_incidents", []))
            note_html = f'<div class="rail-watch__note">{n_open} new incidents — problem ticket still open</div>'
        rail_watch_html += f"""<div class="rail-watch">
  <div class="rail-watch__lbl">Watching</div>
  <div class="rail-watch__issue">{issue_label}</div>
  <div class="rail-watch__refs">{refs_html}</div>
  {note_html}
</div>
"""

    # ── timeline nodes ────────────────────────────────────────────────────
    wave_mods = ["early", "w1", "w2"]
    timeline_html = ""
    for i, w in enumerate(data["wave_stats"]):
        mod   = wave_mods[i] if i < len(wave_mods) else "w2"
        rate  = w["rate"]
        rate_cls = "timeline__stat-val--high" if rate > 5 else "timeline__stat-val--low"
        note  = ""
        if i == 0:
            note = '<p class="timeline__note">~35 misdirects (routing issue, fixed) inflated this rate — not subscriber demand</p>'
        connector = '<div class="timeline__connector" aria-hidden="true"></div>\n' if i < len(data["wave_stats"]) - 1 else ""
        timeline_html += f"""<div class="timeline__node timeline__node--{mod}">
  <div class="timeline__label">{w["label"]}</div>
  <div class="timeline__date">{w["date"]} · {w["invites"]:,} invites</div>
  <div class="timeline__stat"><span>Tickets</span><span class="timeline__stat-val">{w["tickets"]}</span></div>
  <div class="timeline__stat"><span>Contact rate</span><span class="timeline__stat-val {rate_cls}">{rate}%</span></div>
  {note}
</div>
{connector}"""

    # ── weekly volume table ────────────────────────────────────────────────
    weekly_rows = ""
    for ws, n in data["weekly"].items():
        we = (dt.date.fromisoformat(ws) + dt.timedelta(days=6)).isoformat()
        weekly_rows += f"<tr><td>{ws} → {we}</td><td class='num'>{n}</td></tr>\n"

    # ── capacity insight numbers ───────────────────────────────────────────
    per_1k = round(1000 * avg_rate / 100)
    day2   = max(1, round(per_1k * surge))

    # ── projection table ──────────────────────────────────────────────────
    proj_rows = ""
    for batch in [500, 1000, 2000, 5000, 10000]:
        expected = round(batch * avg_rate / 100)
        peak_day = max(1, round(expected * surge))
        proj_rows += (
            f"<tr><td class='num'>{batch:,}</td>"
            f"<td class='num'>{expected}</td>"
            f"<td class='num'>{peak_day}/day</td></tr>\n"
        )

    # wave age note
    wave2_age = (dt.date.today() - dt.date(2026, 6, 4)).days

    # ── wave contact-rate table rows ──────────────────────────────────────
    wave_rows = ""
    for w in data["wave_stats"]:
        wave_rows += (
            f"<tr><td>{w['label']}</td><td>{w['date']}</td>"
            f"<td class='num'>{w['invites']:,}</td>"
            f"<td class='num'>{w['tickets']}</td>"
            f"<td class='num'>{w['rate']}%</td></tr>\n"
        )

    # ── ideas table rows (top 10) ─────────────────────────────────────────
    ideas_all = data.get("ideas_all", data["ideas"])
    _OMIT = {"On the roadmap", "In flight", "Landed!", "No for now", "By design", "Off-topic"}
    _STATUS = lambda p: (p.get("custom_status") or {}).get("title") or p.get("status", "")
    unhandled = [p for p in ideas_all if _STATUS(p) not in _OMIT]

    idea_rows = ""
    for p in unhandled[:10]:
        _product_tags = {"Thundermail", "Appointment", "Send"}
        _all_tags = [tg.get("name", "") for tg in (p.get("tags") or []) if tg.get("name")]
        _sorted_tags = sorted(_all_tags, key=lambda x: (0 if x in _product_tags else 1, x))
        tags_str = ", ".join(_sorted_tags)[:50] or "—"
        votes    = p.get("votes_count", 0)
        comments = p.get("comments_count", 0)
        score    = votes + comments
        hot_badge = (' <span class="flag-hot" title="Comments exceed votes — high discussion">🔥</span>'
                     if comments > votes else "")
        idea_rows += (
            f"<tr>"
            f"<td class='num tbl-strong'>{votes}</td>"
            f"<td class='num tbl-muted'>{comments}</td>"
            f"<td class='num tbl-strong'>{score}</td>"
            f"<td><a href='{p.get('url','')}' target='_blank'>"
            f"{p.get('title','')[:65]}</a>{hot_badge}</td>"
            f"<td class='tbl-tags'>{tags_str}</td>"
            f"</tr>\n"
        )

    # ── kanban columns ─────────────────────────────────────────────────────
    def _kanban_col(label, ideas_list, col_cls):
        if not ideas_list:
            return ""
        items = ""
        for p in ideas_list:
            v = p.get("votes_count", 0)
            hot = p.get("comments_count", 0) > v
            hot_html = ' <span class="flag-hot" title="Comments exceed votes">🔥</span>' if hot else ""
            items += (
                f'<div class="kanban-item">'
                f'<span class="kanban-item__votes">{v}▲</span>'
                f'<a class="kanban-item__link" href="{p.get("url","")}" target="_blank">'
                f'{p.get("title","")[:80]}</a>{hot_html}</div>\n'
            )
        return (
            f'<div class="kanban-col {col_cls}">\n'
            f'  <div class="kanban-col__head">{label} ({len(ideas_list)})</div>\n'
            f'{items}</div>\n'
        )

    roadmap   = [p for p in ideas_all if _STATUS(p) == "On the roadmap"]
    in_flight = [p for p in ideas_all if _STATUS(p) == "In flight"]
    landed    = [p for p in ideas_all if _STATUS(p) == "Landed!"]
    wont_do   = [p for p in ideas_all if _STATUS(p) in {"No for now", "By design"}]

    kanban_html = (
        _kanban_col("On the roadmap", roadmap, "kanban-col--roadmap") +
        _kanban_col("In flight", in_flight, "kanban-col--flight") +
        _kanban_col("Landed", landed, "kanban-col--landed") +
        _kanban_col("No for now", wont_do, "kanban-col--declined")
    )

    # ── theme section HTML ─────────────────────────────────────────────────
    theme_tickets_map = data.get("theme_tickets", {})
    MISDIRECT_KEY = "Misdirected — wrong product / non-subscriber"
    F2_START = "2026-06-03"

    # Flight 2 tickets (subscriber themes, no misdirects)
    f2_tickets = [t for t in (theme_tickets_map.get(MISDIRECT_KEY) or [])
                  if t.get("created_at", "")[:10] >= F2_START]  # misdirects in F2
    f2_all     = [t for t in sum(theme_tickets_map.values(), [])
                  if t.get("created_at", "")[:10] >= F2_START]
    f2_subscriber = [t for t in f2_all
                     if classify_ticket(t) != MISDIRECT_KEY]
    f2_total = len(f2_subscriber)

    # Build Flight 2 subscriber theme rows
    f2_theme_counts = Counter(classify_ticket(t) for t in f2_subscriber)
    f2_theme_tickets = defaultdict(list)
    for t in f2_subscriber:
        f2_theme_tickets[classify_ticket(t)].append(t)

    f2_theme_html = ""
    for theme, n in f2_theme_counts.most_common(20):
        tlist = f2_theme_tickets[theme]
        f2_theme_html += _theme_row_wrap(theme, n, f2_total, tlist, sub, gh_links)

    f2_misdirect_count = len([t for t in f2_all if classify_ticket(t) == MISDIRECT_KEY])
    misdirect_callout = ""
    if f2_misdirect_count:
        misdirect_callout = (
            f'<div class="insight insight--routing insight--spaced insight--spaced-top">'
            f'<strong>Misdirected volume was an Early Bird routing issue — resolved.</strong> '
            f'Flight 2 saw only <strong>{f2_misdirect_count} misdirect{"s" if f2_misdirect_count != 1 else ""}</strong> '
            f'in {len(f2_all)} tickets. Full ticket list in the historical panel below.</div>\n'
        )
    else:
        misdirect_callout = (
            '<div class="insight insight--routing insight--spaced insight--spaced-top">'
            '<strong>Misdirected volume was an Early Bird routing issue — resolved.</strong> '
            'Flight 2 saw 0 misdirects. Full historical list in the collapsed panel below.</div>\n'
        )

    # All-launch subscriber themes (excl. misdirects)
    all_sub_tickets = [t for t in sum(theme_tickets_map.values(), [])
                       if classify_ticket(t) != MISDIRECT_KEY]
    all_sub_total = len(all_sub_tickets)
    all_sub_theme_counts = Counter(classify_ticket(t) for t in all_sub_tickets)
    all_sub_theme_tickets = defaultdict(list)
    for t in all_sub_tickets:
        all_sub_theme_tickets[classify_ticket(t)].append(t)

    all_sub_theme_html = ""
    for theme, n in all_sub_theme_counts.most_common(20):
        tlist = all_sub_theme_tickets[theme]
        all_sub_theme_html += _theme_row_wrap(theme, n, all_sub_total, tlist, sub, gh_links)

    # Historical misdirects
    misdirect_tickets = theme_tickets_map.get(MISDIRECT_KEY, [])
    misdirect_count = len(misdirect_tickets)
    misdirect_pct = int(misdirect_count / total * 100) if total else 0
    misdirect_theme_html = _theme_row_wrap(
        f'{MISDIRECT_KEY} <span class="theme-tag theme-tag--fixed">Fixed — historical only</span>',
        misdirect_count, total, misdirect_tickets, sub, gh_links, "theme-row--historical"
    )

    # ── engineering cards ──────────────────────────────────────────────────
    gh_sorted = sorted(data["gh_tickets"], key=lambda x: x.get("created_at", ""), reverse=True)
    eng_open  = [t for t in gh_sorted if t.get("status") not in ("solved", "closed")]
    eng_done  = [t for t in gh_sorted if t.get("status") in ("solved", "closed")]

    eng_open_html = "".join(_eng_card(t, sub, gh_links) for t in eng_open)
    if not eng_open_html:
        eng_open_html = "<p style='color:var(--color-text-muted);font-size:.8rem'>No open escalations.</p>"

    eng_done_html = ""
    if eng_done:
        cards = "".join(_eng_card(t, sub, gh_links) for t in eng_done)
        eng_done_html = (
            f'<details class="eng-expand">\n'
            f'  <summary>{len(eng_done)} solved / closed ticket{"s" if len(eng_done) != 1 else ""}</summary>\n'
            f'  <div class="eng-list wait-grid--spaced">{cards}</div>\n'
            f'</details>\n'
        )

    # ── AHT distribution bars ─────────────────────────────────────────────
    aht_buckets = data.get("aht_buckets", {})
    def _bar_cls(label):
        if label in ("< 1h", "1–4h"):   return "dist-row__bar--fast"
        if label in ("4–12h", "12–24h"): return "dist-row__bar--mid"
        if label == "1–3d":              return "dist-row__bar--slow"
        return "dist-row__bar--tail"

    aht_dist_html = ""
    labels_display = {
        "< 1h": "Same business day (≤ 1h)", "1–4h": "1–4 hours",
        "4–12h": "4–12 hours", "12–24h": "12–24 hours",
        "1–3d": "1–3 days", "3–7d": "3–7 days", "7d+": "7+ days",
    }
    for lbl, pct in aht_buckets.items():
        display = labels_display.get(lbl, lbl)
        bar_cls = _bar_cls(lbl)
        aht_dist_html += (
            f'<div class="dist-row">'
            f'<span class="dist-row__lbl">{display}</span>'
            f'<span class="dist-row__pct">{pct}%</span>'
            f'<div class="dist-row__bar-wrap">'
            f'<div class="dist-row__bar {bar_cls}" style="width:{pct}%"></div></div></div>\n'
        )

    aht_n = aht.get("n", "—") if aht else "—"
    aht_mean = f"{aht.get('mean_h','—')}h" if aht else "—"
    aht_p75  = f"{aht.get('p75_h','—')}h" if aht else "—"

    # ── AHT trend chart data ──────────────────────────────────────────────────
    aht_weekly = data.get("aht_weekly", {})
    aht_trend_weeks = list(aht_weekly.keys())
    aht_trend_biz   = [v["biz_days"] for v in aht_weekly.values()]
    aht_trend_cal   = [v["cal_days"] for v in aht_weekly.values()]
    # Cumulative median (running average of weekly biz_days as an approximation)
    cum_aht_biz = []
    all_so_far = []
    for v in aht_weekly.values():
        all_so_far.append(v["biz_days"])
        cum_aht_biz.append(round(sum(all_so_far) / len(all_so_far), 1))

    # ── "What drives the long closes" rows ───────────────────────────────────
    theme_aht = data.get("theme_aht", {})
    sorted_theme_aht = sorted(theme_aht.items(), key=lambda x: x[1]["median_mins"], reverse=True)
    max_biz = sorted_theme_aht[0][1]["biz_days"] if sorted_theme_aht else 1

    wdl_rows = ""
    for theme, td in sorted_theme_aht:
        bar_pct = int(td["biz_days"] / max_biz * 100)
        _bd = td["biz_days"]
        biz_label = f"~{_bd:.0f} biz day{'s' if _bd != 1 else ''}" if _bd >= 1 else "<1 biz day"
        gh_badge = ' <span class="wdl-gh">GH-linked</span>' if td["gh"] else ""
        n_tickets = td["n"]
        ticket_items = "".join(_ticket_li(t, sub, gh_links) for t in data["theme_tickets"].get(theme, [])[:20])
        wdl_rows += f"""<div class="wdl-row">
  <div class="wdl-header">
    <span class="wdl-name">{theme}</span>
    <span class="wdl-meta">{biz_label} <span class="wdl-n">n={n_tickets}</span>{gh_badge}</span>
  </div>
  <div class="wdl-bar-wrap"><div class="wdl-bar" style="width:{bar_pct}%"></div></div>
  <details class="theme-tickets"><summary>{n_tickets} ticket{"s" if n_tickets != 1 else ""}</summary>
    <ul class="theme-tickets__list">
      {ticket_items}
    </ul>
  </details>
</div>
"""

    aht_trend_html = ""
    if aht_trend_weeks:
        aht_trend_html = f"""
  <div class="panel panel--spaced">
    <div class="panel__title">Median AHT Trend &middot; Business Hours</div>
    <p class="panel__note" style="margin-bottom:.75rem">Schedule: 8am&ndash;8pm Eastern (12h/day). Dashed line = calendar days (inflated by nights/weekends) &mdash; shown for reference only.</p>
    <canvas id="ahtTrendChart" style="max-height:260px"></canvas>
  </div>"""

    wdl_html = ""
    if wdl_rows:
        wdl_html = f"""
  <div class="panel panel--spaced">
    <div class="panel__title">What drives the long closes</div>
    {wdl_rows}
  </div>"""

    milestones_js = json.dumps([
        {"date": w["date"], "label": w["label"], "color": w["color"]} for w in WAVES
    ])

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thundermail Launch — Support Briefing</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/chartjs-plugin-annotation/3.0.1/chartjs-plugin-annotation.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600;700&display=swap" rel="stylesheet">

<style>
/* CSS REGION: tokens — Bolt dark palette; edit colors/spacing here only */
:root {{
  --color-surface-base:          #0d0c14;
  --color-surface-lower:         #060618;
  --color-surface-raised:        #15131e;
  --color-surface-overlay:       #1c1a28;
  --color-surface-border:        #2b2845;
  --color-surface-border-strong: #3e3b62;
  --color-primary:               #4d7bf8;
  --color-primary-soft:          #0e1038;
  --color-secondary:             #7c3aed;
  --color-text-base:             #e2e0f0;
  --color-text-secondary:        #b0aece;
  --color-text-muted:            #9492b0;
  --color-success:               #22c55e;
  --color-success-soft:          #041d0e;
  --color-warning:               #f59e0b;
  --color-warning-soft:          #1c1200;
  --color-warning-text:          #fcd34d;
  --color-critical:              #ef4444;
  --color-critical-soft:         #2a0808;
  --color-teal:                  #00d4a0;
  --color-orange:                #f97316;
  --color-on-inverse:            #ffffff;
  --color-wave-early:            #6366f1;
  --color-wave-w1:               #f97316;
  --color-wave-w2:               #ef4444;
  --space-4:  0.25rem;
  --space-8:  0.5rem;
  --space-12: 0.75rem;
  --space-16: 1rem;
  --space-24: 1.5rem;
  --space-32: 2rem;
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
  --font-mono: 'JetBrains Mono', 'SF Mono', ui-monospace, monospace;
}}

*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{
  background:var(--color-surface-base);
  color:var(--color-text-base);
  font-family:'Inter',system-ui,sans-serif;
  font-size:14px;line-height:1.5;
  min-height:100vh;
}}
a{{color:var(--color-primary);text-decoration:none}}
a:hover{{text-decoration:underline}}
a:focus-visible,button:focus-visible,summary:focus-visible{{
  outline:2px solid var(--color-primary);outline-offset:2px;
}}
code{{font-family:var(--font-mono);font-size:.85em;background:var(--color-surface-border);padding:.1em .35em;border-radius:4px}}

/* CSS REGION: layout — shell, rail, main */
.shell{{display:grid;grid-template-columns:200px 1fr;min-height:100vh}}
@media(max-width:960px){{.shell{{grid-template-columns:1fr}}}}
.rail{{
  background:var(--color-surface-lower);
  border-right:1px solid var(--color-surface-border);
  padding:var(--space-16) var(--space-12);
  position:sticky;top:0;
  align-self:start;
  display:flex;flex-direction:column;gap:var(--space-12);
}}
@media(max-width:960px){{
  .rail{{position:relative;align-self:stretch;border-right:none;border-bottom:1px solid var(--color-surface-border);padding:var(--space-16)}}
}}
.rail__brand{{display:flex;align-items:center;gap:var(--space-8)}}
.rail__logo{{width:32px;height:32px}}
.rail__title{{font-size:.88rem;font-weight:700;line-height:1.25}}
.rail__tag{{font-size:.625rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--color-teal)}}
.rail__nav{{list-style:none;display:flex;flex-direction:column;gap:2px}}
@media(max-width:960px){{.rail__nav{{flex-direction:row;flex-wrap:wrap;gap:var(--space-4)}}}}
.rail__nav a{{
  display:block;padding:5px var(--space-8);
  font-size:.74rem;font-weight:500;color:var(--color-text-muted);
  border-radius:var(--radius-sm);transition:background .15s,color .15s;
}}
.rail__nav a:hover,.rail__nav a.is-active{{
  background:var(--color-surface-raised);color:var(--color-text-base);text-decoration:none;
}}
.rail__stats{{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-8)}}
.rail-stat{{
  padding:var(--space-8);
  background:var(--color-surface-raised);border:1px solid var(--color-surface-border);
  border-radius:var(--radius-sm);
}}
.rail-stat__val{{font-size:1.05rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}}
.rail-stat__lbl{{font-size:.625rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin-top:3px;line-height:1.3}}
.rail-stat--success .rail-stat__val{{color:var(--color-success)}}
.rail-watch{{
  padding:var(--space-8);
  background:var(--color-warning-soft);border:1px solid var(--color-warning);
  border-radius:var(--radius-sm);font-size:.68rem;line-height:1.45;
}}
.rail-watch__lbl{{font-size:.625rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--color-warning);margin-bottom:3px}}
.rail-watch__issue{{font-weight:600;color:var(--color-text-base)}}
.rail-watch__refs{{color:var(--color-warning-text);margin-top:2px}}
.rail-watch__refs a{{color:var(--color-warning)}}
.rail-watch__note{{color:var(--color-text-muted);font-size:.62rem;margin-top:3px;font-style:italic}}
.rail-watch__meta{{font-weight:400}}
.main{{padding:var(--space-24) var(--space-32) var(--space-32);max-width:960px}}
@media(max-width:640px){{.main{{padding:var(--space-16)}}}}

/* CSS REGION: components — status bar, hero, charts, AHT, ideas, engineering */
.status-bar{{display:flex;flex-wrap:wrap;align-items:flex-start;gap:var(--space-12);margin-bottom:var(--space-24)}}
.chip{{display:inline-flex;align-items:center;gap:var(--space-8);padding:var(--space-8) var(--space-12);border-radius:999px;font-size:.75rem;font-weight:600}}
.chip--warn{{background:var(--color-warning-soft);border:1px solid var(--color-warning);color:var(--color-warning)}}
.chip--ok{{background:var(--color-success-soft);border:1px solid var(--color-success);color:var(--color-success)}}
.chip__dot{{width:7px;height:7px;border-radius:50%;background:currentColor;flex-shrink:0}}
.alert-panel{{
  flex:1 1 100%;background:var(--color-warning-soft);
  border:1px solid var(--color-warning);border-radius:var(--radius-md);
  padding:var(--space-12) var(--space-16);font-size:.84rem;line-height:1.6;
}}
.alert-panel__head{{font-weight:700;color:var(--color-warning);margin-bottom:var(--space-4)}}
.alert-panel__head a{{color:var(--color-warning)}}
.alert-panel__sub{{color:var(--color-warning-text);font-size:.8rem}}
.alert-panel__meta{{font-weight:400;font-size:.78rem;color:var(--color-warning-text)}}
.hero{{
  background:linear-gradient(135deg,var(--color-surface-raised) 0%,var(--color-surface-overlay) 100%);
  border:1px solid var(--color-surface-border);border-radius:var(--radius-lg);
  padding:var(--space-24) var(--space-24) var(--space-24) var(--space-32);
  margin-bottom:var(--space-32);position:relative;overflow:hidden;
}}
.hero::before{{content:'';position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(180deg,var(--color-primary),var(--color-teal))}}
.hero__eyebrow{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--color-text-muted);margin-bottom:var(--space-8)}}
.hero__headline{{font-size:clamp(1.25rem,3vw,1.65rem);font-weight:700;line-height:1.3;margin-bottom:var(--space-12);max-width:38ch}}
.hero__headline em{{font-style:normal;color:var(--color-teal)}}
.hero__meta{{font-size:.78rem;color:var(--color-text-secondary)}}
.hero__meta span{{color:var(--color-text-muted)}}
.section{{margin-bottom:var(--space-32);scroll-margin-top:var(--space-24)}}
.section__head{{display:flex;align-items:baseline;gap:var(--space-12);margin-bottom:var(--space-16);padding-bottom:var(--space-8);border-bottom:1px solid var(--color-surface-border)}}
.section__num{{font-family:var(--font-mono);font-size:.72rem;font-weight:700;color:var(--color-primary);opacity:.7}}
.section__title{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.1em;color:var(--color-text-muted)}}
.timeline{{display:grid;grid-template-columns:1fr auto 1fr auto 1fr;align-items:start;gap:0;margin-bottom:var(--space-24)}}
@media(max-width:640px){{.timeline{{grid-template-columns:1fr;gap:var(--space-12)}}}}
.timeline__node{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);padding:var(--space-16);position:relative}}
.timeline__node::before{{content:'';position:absolute;top:0;left:0;right:0;height:3px;background:var(--node-color);border-radius:var(--radius-md) var(--radius-md) 0 0}}
.timeline__node--early{{--node-color:var(--color-wave-early)}}
.timeline__node--w1{{--node-color:var(--color-wave-w1)}}
.timeline__node--w2{{--node-color:var(--color-wave-w2)}}
.timeline__label{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-muted);margin-bottom:var(--space-4)}}
.timeline__date{{font-size:.72rem;color:var(--color-text-secondary);margin-bottom:var(--space-8)}}
.timeline__stat{{display:flex;justify-content:space-between;align-items:baseline;padding:var(--space-4) 0;border-top:1px solid var(--color-surface-border);font-size:.78rem}}
.timeline__stat-val{{font-weight:700;font-variant-numeric:tabular-nums}}
.timeline__stat-val--high{{color:var(--color-warning)}}
.timeline__stat-val--low{{color:var(--color-success)}}
.timeline__connector{{align-self:center;width:24px;height:2px;background:var(--color-surface-border-strong);margin-top:2rem}}
@media(max-width:640px){{.timeline__connector{{display:none}}}}
.timeline__note{{font-size:.65rem;color:var(--color-text-muted);margin-top:var(--space-8);line-height:1.45;border-top:1px solid var(--color-surface-border);padding-top:var(--space-8)}}
.bento{{display:grid;grid-template-columns:repeat(12,1fr);gap:var(--space-12);margin-bottom:var(--space-24)}}
.tile{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);padding:var(--space-16);display:flex;flex-direction:column;justify-content:flex-end;min-height:88px}}
.tile__val{{font-size:1.75rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}}
.tile__lbl{{font-size:.62rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--color-text-muted);margin-top:var(--space-4)}}
.tile__sub{{font-size:.68rem;color:var(--color-text-secondary);margin-top:var(--space-4)}}
.tile--span4{{grid-column:span 4}}
.tile--span3{{grid-column:span 3}}
.tile--span6{{grid-column:span 6}}
.tile--accent{{border-color:var(--color-primary);background:var(--color-primary-soft)}}
.tile--accent .tile__val{{color:var(--color-primary)}}
.tile--success .tile__val{{color:var(--color-success)}}
.tile--warn .tile__val{{color:var(--color-warning)}}
@media(max-width:640px){{.tile--span3,.tile--span4,.tile--span6{{grid-column:span 6}}}}
@media(max-width:420px){{.tile--span3,.tile--span4,.tile--span6{{grid-column:span 12}}}}
.chart-panel{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-lg);overflow:hidden;margin-bottom:var(--space-24)}}
.chart-tabs{{display:flex;border-bottom:1px solid var(--color-surface-border);background:var(--color-surface-lower)}}
.chart-tab{{flex:1;padding:var(--space-12) var(--space-16);font-size:.72rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-muted);background:none;border:none;cursor:pointer;border-bottom:2px solid transparent;margin-bottom:-1px;transition:color .15s,border-color .15s}}
.chart-tab:hover{{color:var(--color-text-base)}}
.chart-tab.is-active{{color:var(--color-primary);border-bottom-color:var(--color-primary)}}
.chart-body{{padding:var(--space-16) var(--space-16) var(--space-8);position:relative;min-height:260px}}
.chart-body--compact{{min-height:0;padding-bottom:var(--space-16)}}
.chart-pane{{display:none}}
.chart-pane.is-active{{display:block}}
.chart-pane canvas{{max-height:240px}}
.chart-canvas--md{{max-height:240px}}
.insight{{background:var(--color-primary-soft);border:1px solid var(--color-surface-border-strong);border-left:4px solid var(--color-primary);border-radius:var(--radius-md);padding:var(--space-16);margin-bottom:var(--space-24);font-size:.84rem;line-height:1.65}}
.insight strong{{font-weight:700;color:var(--color-text-base)}}
.insight__nums{{display:flex;flex-wrap:wrap;gap:var(--space-16);margin-top:var(--space-12)}}
.insight__num{{text-align:center}}
.insight__num-val{{font-size:1.25rem;font-weight:700;color:var(--color-teal);font-variant-numeric:tabular-nums}}
.insight__num-lbl{{font-size:.62rem;color:var(--color-text-muted);text-transform:uppercase;letter-spacing:.05em}}
.insight--spaced{{margin-bottom:var(--space-16)}}
.insight--spaced-top{{margin-top:var(--space-16)}}
.insight--primary{{border-left-color:var(--color-primary);background:var(--color-primary-soft)}}
.insight--routing{{border-left-color:var(--color-text-muted);background:var(--color-surface-lower)}}
.insight__body{{margin-top:var(--space-8);color:var(--color-text-secondary);font-size:.84rem;line-height:1.65}}
.aht-hero{{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-12);margin-bottom:var(--space-16)}}
@media(max-width:700px){{.aht-hero{{grid-template-columns:repeat(2,1fr)}}}}
.aht-stat{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);padding:var(--space-12);text-align:center}}
.aht-stat__val{{font-size:1.4rem;font-weight:700;color:var(--color-teal);line-height:1}}
.dist-row{{display:flex;align-items:center;gap:var(--space-8);margin-bottom:var(--space-8);font-size:.78rem}}
.dist-row__lbl{{flex:1;color:var(--color-text-secondary)}}
.dist-row__pct{{font-weight:700;font-variant-numeric:tabular-nums;min-width:2.5rem;text-align:right}}
.dist-row__bar-wrap{{flex:0 0 100px;height:8px;background:var(--color-surface-border);border-radius:4px;overflow:hidden}}
.dist-row__bar{{height:100%;border-radius:4px}}
.dist-row__bar--fast{{background:var(--color-success)}}
.dist-row__bar--mid{{background:var(--color-primary)}}
.dist-row__bar--slow{{background:var(--color-warning)}}
.dist-row__bar--tail{{background:var(--color-critical)}}
.wdl-row{{margin-bottom:var(--space-12)}}
.wdl-header{{display:flex;justify-content:space-between;align-items:baseline;margin-bottom:4px;flex-wrap:wrap;gap:var(--space-4)}}
.wdl-name{{font-size:.78rem;font-weight:600;color:var(--color-text-secondary)}}
.wdl-meta{{font-size:.72rem;color:var(--color-text-muted)}}
.wdl-n{{color:var(--color-text-muted);margin-left:var(--space-4)}}
.wdl-gh{{display:inline-block;font-size:.62rem;font-weight:700;text-transform:uppercase;letter-spacing:.04em;padding:.1em .35em;border-radius:3px;background:var(--color-primary-soft);border:1px solid var(--color-primary);color:var(--color-primary);margin-left:var(--space-4)}}
.wdl-bar-wrap{{height:8px;background:var(--color-surface-border);border-radius:4px;overflow:hidden;margin-bottom:4px}}
.wdl-bar{{height:100%;background:linear-gradient(90deg,var(--color-primary),var(--color-teal));border-radius:4px}}
.dual{{display:grid;grid-template-columns:1fr 1fr;gap:var(--space-16);margin-bottom:var(--space-24)}}
@media(max-width:700px){{.dual{{grid-template-columns:1fr}}}}
.panel{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);padding:var(--space-16)}}
.panel__title{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--color-text-muted);margin-bottom:var(--space-12)}}
.panel__note{{font-size:.68rem;color:var(--color-text-muted);margin-top:var(--space-12);line-height:1.55}}
.panel--spaced{{margin-bottom:var(--space-16)}}
.panel-intro{{font-size:.75rem;color:var(--color-text-muted);margin-bottom:var(--space-12);line-height:1.5}}

/* CSS REGION: tables — .tbl, sort headers (.tbl-sort__inner, never flex on th/td) */
.tbl{{width:100%;border-collapse:collapse;font-size:.8rem}}
.tbl th{{text-align:left;font-size:.65rem;font-weight:600;text-transform:uppercase;letter-spacing:.06em;color:var(--color-text-muted);padding:var(--space-8);border-bottom:1px solid var(--color-surface-border);vertical-align:middle}}
.tbl td{{padding:var(--space-8);border-bottom:1px solid var(--color-surface-border);vertical-align:middle}}
.tbl tr:last-child td{{border-bottom:none}}
.tbl .num{{text-align:right;font-variant-numeric:tabular-nums;width:1%;white-space:nowrap}}
.tbl th.tbl-sort{{vertical-align:middle;white-space:nowrap;cursor:pointer;user-select:none}}
.tbl th.tbl-sort:hover{{color:var(--color-text-base)}}
.tbl-sort__inner{{display:inline-flex;align-items:center;gap:.2em}}
.tbl-sort__icon{{font-size:.85em;opacity:.55;line-height:1}}
.tbl-muted{{color:var(--color-text-muted)}}
.tbl-strong{{font-weight:600}}
.tbl-tags{{font-size:.72rem;color:var(--color-text-muted)}}
#ideasTable th:last-child,#ideasTable td:last-child{{width:14%;padding-left:var(--space-12);font-size:.72rem;color:var(--color-text-muted)}}

/* CSS REGION: themes — leaderboard rows, ticket expansions */
.themes{{display:flex;flex-direction:column;gap:var(--space-8)}}
.theme-row{{display:grid;grid-template-columns:1fr auto;gap:var(--space-8);align-items:center;font-size:.78rem}}
.theme-row__name{{color:var(--color-text-secondary)}}
#themes .theme-row__name{{white-space:normal;overflow:visible;text-overflow:unset;max-width:none}}
.theme-row__count{{font-weight:700;font-variant-numeric:tabular-nums;min-width:2rem;text-align:right}}
.theme-row__bar-wrap{{grid-column:1/-1;height:6px;background:var(--color-surface-border);border-radius:3px;overflow:hidden}}
.theme-row__bar{{height:100%;background:linear-gradient(90deg,var(--color-primary),var(--color-teal));border-radius:3px}}
.theme-row__pct{{font-size:.65rem;color:var(--color-text-muted);margin-left:var(--space-4)}}
.theme-row--historical .theme-row__name{{color:var(--color-text-muted)}}
.theme-row--historical .theme-row__count{{color:var(--color-text-muted)}}
.theme-row--historical .theme-row__bar{{opacity:.4;background:repeating-linear-gradient(90deg,var(--color-text-muted) 0 6px,transparent 6px 10px);background-color:var(--color-surface-border-strong)}}
.theme-row-wrap{{display:flex;flex-direction:column;gap:0}}
.theme-tickets{{margin:0;padding:0}}
.theme-tickets>summary{{cursor:pointer;list-style:none;font-size:.65rem;color:var(--color-text-muted);padding:2px 0 var(--space-4);user-select:none}}
.theme-tickets>summary::-webkit-details-marker{{display:none}}
.theme-tickets>summary::before{{content:'▸ ';font-size:.6rem}}
.theme-tickets[open]>summary::before{{content:'▾ '}}
.theme-tickets>summary:hover{{color:var(--color-text-secondary)}}
.theme-tickets__list{{margin:0 0 var(--space-4);padding:var(--space-4) 0 var(--space-4) var(--space-12);list-style:none;border-left:2px solid var(--color-surface-border)}}
.theme-tickets__list li{{font-size:.72rem;line-height:1.45;padding:.15rem 0;color:var(--color-text-secondary)}}
.theme-tickets__list a{{font-weight:600;font-family:var(--font-mono);font-size:.68rem}}
.theme-tickets__subj{{color:var(--color-text-muted)}}
.theme-tickets__gh{{display:inline-block;margin-left:var(--space-4);font-size:.62rem;color:var(--color-text-muted)}}
.theme-block{{margin-bottom:var(--space-16)}}
.theme-block__head{{display:flex;flex-wrap:wrap;align-items:baseline;gap:var(--space-8);margin-bottom:var(--space-12)}}
.theme-block__title{{font-size:.78rem;font-weight:600;color:var(--color-text-base)}}
.theme-block__meta{{font-size:.68rem;color:var(--color-text-muted)}}
.theme-historical{{margin-top:var(--space-12)}}
.theme-historical>summary{{cursor:pointer;list-style:none;display:flex;align-items:center;gap:var(--space-8);padding:var(--space-12) var(--space-16);background:var(--color-surface-lower);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);font-size:.78rem;font-weight:600;color:var(--color-text-muted)}}
.theme-historical>summary::before{{content:'▸';font-size:.72rem;transition:transform .15s}}
.theme-historical[open]>summary::before{{transform:rotate(90deg)}}
.theme-historical>summary::-webkit-details-marker{{display:none}}
.theme-historical__body{{margin-top:var(--space-8);padding:var(--space-16);background:var(--color-surface-lower);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);border-left:3px dashed var(--color-text-muted)}}
.theme-tag{{display:inline-block;font-size:.625rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;padding:.15em .45em;border-radius:4px;vertical-align:middle;margin-left:var(--space-4)}}
.theme-tag--fixed{{background:var(--color-success-soft);border:1px solid var(--color-success);color:var(--color-success)}}
.ideas-header{{margin-bottom:var(--space-16)}}
.ideas-header h3{{font-size:.95rem;font-weight:600;margin-bottom:var(--space-4)}}
.ideas-header p{{font-size:.75rem;color:var(--color-text-muted)}}
.ideas-table{{margin-top:var(--space-12)}}
.kanban{{display:grid;grid-template-columns:repeat(4,1fr);gap:var(--space-12);margin-bottom:var(--space-24)}}
@media(max-width:900px){{.kanban{{grid-template-columns:repeat(2,1fr)}}}}
@media(max-width:480px){{.kanban{{grid-template-columns:1fr}}}}
.kanban-col{{background:var(--color-surface-lower);border:1px solid var(--color-surface-border);border-radius:var(--radius-md);padding:var(--space-12);min-height:120px}}
.kanban-col__head{{font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;margin-bottom:var(--space-12);padding-bottom:var(--space-8);border-bottom:2px solid var(--col-accent)}}
.kanban-col--roadmap{{--col-accent:var(--color-warning)}}
.kanban-col--flight{{--col-accent:var(--color-primary)}}
.kanban-col--landed{{--col-accent:var(--color-success)}}
.kanban-col--declined{{--col-accent:var(--color-text-muted)}}
.kanban-item{{display:flex;gap:var(--space-8);align-items:flex-start;padding:var(--space-8) 0;border-bottom:1px solid var(--color-surface-border);font-size:.76rem;line-height:1.4}}
.kanban-item:last-child{{border-bottom:none}}
.kanban-item__votes{{font-family:var(--font-mono);font-size:.65rem;font-weight:700;color:var(--color-text-muted);min-width:2rem;text-align:right;flex-shrink:0;padding-top:.1em}}
.kanban-item__link{{color:var(--color-text-base)}}
.kanban-item__link:hover{{color:var(--color-primary)}}
.flag-hot{{color:var(--color-orange);font-size:.65rem;cursor:help;white-space:nowrap}}
.eng-summary{{font-size:.78rem;color:var(--color-text-secondary);margin-bottom:var(--space-12)}}
.eng-list{{display:flex;flex-direction:column;gap:var(--space-8)}}
.eng-card{{display:grid;grid-template-columns:auto 1fr auto;gap:var(--space-12);align-items:center;background:var(--color-surface-lower);border:1px solid var(--color-surface-border);border-radius:var(--radius-sm);padding:var(--space-12);font-size:.78rem}}
.eng-card--open{{border-left:3px solid var(--color-orange)}}
.eng-card--hold{{border-left:3px solid var(--color-text-muted)}}
.eng-card--solved{{border-left:3px solid var(--color-success)}}
.eng-card__id{{font-family:var(--font-mono);font-weight:700;white-space:nowrap}}
.eng-card__id--open{{color:var(--color-orange)}}
.eng-card__id--hold{{color:var(--color-text-muted)}}
.eng-card__id--solved{{color:var(--color-success)}}
.eng-card__subject{{color:var(--color-text-secondary)}}
.eng-card__date{{font-size:.68rem;color:var(--color-text-muted);white-space:nowrap}}
.eng-card__gh{{font-size:.65rem;color:var(--color-text-muted)}}
.eng-expand summary{{cursor:pointer;font-size:.72rem;color:var(--color-text-muted);padding:var(--space-8) 0;list-style:none}}
.eng-expand summary::before{{content:'▸ ';display:inline-block;transition:transform .15s}}
.eng-expand[open] summary::before{{transform:rotate(90deg)}}
.wait-grid--spaced{{margin-top:var(--space-12)}}
.glossary{{display:flex;flex-direction:column;gap:var(--space-12)}}
.glossary details{{background:var(--color-surface-raised);border:1px solid var(--color-surface-border);border-radius:var(--radius-sm);overflow:hidden}}
.glossary summary{{padding:var(--space-12) var(--space-16);font-weight:600;font-size:.82rem;cursor:pointer;list-style:none;display:flex;justify-content:space-between;align-items:center}}
.glossary summary::after{{content:'+';color:var(--color-text-muted);font-weight:400}}
.glossary details[open] summary::after{{content:'−'}}
.glossary details[open] summary{{border-bottom:1px solid var(--color-surface-border)}}
.glossary__body{{padding:var(--space-12) var(--space-16);font-size:.8rem;color:var(--color-text-secondary);line-height:1.65}}
.footer{{margin-top:var(--space-32);padding-top:var(--space-16);border-top:1px solid var(--color-surface-border);font-size:.68rem;color:var(--color-text-muted);line-height:1.6}}
.footer a{{color:var(--color-primary)}}
@media(prefers-reduced-motion:reduce){{
  html{{scroll-behavior:auto}}
  *,*::before,*::after{{animation-duration:.01ms!important;animation-iteration-count:1!important;transition-duration:.01ms!important}}
}}
</style>
</head>
<body>
<div class="shell">

<aside class="rail">
  <div class="rail__brand">
    <img class="rail__logo" src="https://tb.pro/media/img/thunderbird/thunderbird-256.png" alt="">
    <div>
      <div class="rail__tag">Support Briefing</div>
      <div class="rail__title">Thundermail Launch</div>
    </div>
  </div>
  <nav aria-label="Sections">
    <ul class="rail__nav">
      <li><a href="#story" class="is-active">Story</a></li>
      <li><a href="#waves">Invite waves</a></li>
      <li><a href="#volume">Volume</a></li>
      <li><a href="#aht">Resolution time</a></li>
      <li><a href="#planning">Planning</a></li>
      <li><a href="#themes">Themes</a></li>
      <li><a href="#ideas">Ideas</a></li>
      <li><a href="#engineering">Engineering</a></li>
      <li><a href="#glossary">Glossary</a></li>
    </ul>
  </nav>
  <div class="rail__stats">
    <div class="rail-stat"><div class="rail-stat__val">{total}</div><div class="rail-stat__lbl">Tickets</div></div>
    <div class="rail-stat rail-stat--success"><div class="rail-stat__val">{avg_rate}%</div><div class="rail-stat__lbl">Flight 2 baseline</div></div>
    <div class="rail-stat {rail_csat_cls}"><div class="rail-stat__val">{rail_csat_pct}</div><div class="rail-stat__lbl">CSAT</div></div>
    <div class="rail-stat"><div class="rail-stat__val">{frt_median}</div><div class="rail-stat__lbl">First reply</div></div>
  </div>
  {rail_watch_html}
</aside>

<main class="main">

<div class="status-bar">
{status_chips}
{alert_panels}
</div>

<!-- SECTION: story -->
<section class="section" id="story">
  <div class="hero">
    <div class="hero__eyebrow">Early Bird May 4 → {data["today"]} · {TOTAL_INVITEES:,} invitees · Generated {gen}</div>
    <h1 class="hero__headline">Flight 2 complete at <em>{avg_rate}%</em> contact rate — use this baseline to staff the next flight.</h1>
    <p class="hero__meta">{total} tickets across all waves · <span>Early Bird inflated by misdirected non-subscribers; Flight 2 Waves 1+2 complete — historical baseline for next flight</span></p>
  </div>

  <div class="bento">
    <div class="tile tile--span4 tile--accent">
      <div class="tile__val">{total}</div>
      <div class="tile__lbl">Total tickets</div>
      <div class="tile__sub">since Early Bird launch</div>
    </div>
    <div class="tile tile--span4 tile--success">
      <div class="tile__val">{avg_rate}%</div>
      <div class="tile__lbl">Flight 2 contact rate</div>
      <div class="tile__sub">Waves 1+2 complete · historical baseline</div>
    </div>
    <div class="tile tile--span4 {"tile--success" if csat_launch.get("n",0) and int((csat_launch.get("pct") or "0").rstrip("%")) >= 80 else ""}">
      <div class="tile__val">{csat_launch.get("pct","—")}</div>
      <div class="tile__lbl">CSAT all-time</div>
      <div class="tile__sub">{csat_launch.get("good",0)} good · {csat_launch.get("bad",0)} bad · {csat_launch.get("n",0)} rated</div>
    </div>
    <div class="tile tile--span3">
      <div class="tile__val">{overall_rate}%</div>
      <div class="tile__lbl">Overall contact rate</div>
      <div class="tile__sub">{total} / {TOTAL_INVITEES:,} invitees</div>
    </div>
    <div class="tile tile--span3 tile--warn">
      <div class="tile__val">{aht_median}</div>
      <div class="tile__lbl">Median AHT</div>
      <div class="tile__sub">calendar time to resolve · {aht_n} solved</div>
    </div>
    <div class="tile tile--span3">
      <div class="tile__val">{frt_median}</div>
      <div class="tile__lbl">First reply</div>
      <div class="tile__sub">from ticket created to first reply</div>
    </div>
    <div class="tile tile--span3">
      <div class="tile__val">{data["ideas_count"]}</div>
      <div class="tile__lbl">FeatureOS ideas</div>
      <div class="tile__sub">excl. off-topic</div>
    </div>
    <div class="tile tile--span6">
      <div class="tile__val">{gh_pct}%</div>
      <div class="tile__lbl">GitHub escalations</div>
      <div class="tile__sub">{len(data["gh_tickets"])} of {total} tickets linked to a GitHub issue</div>
    </div>
    <div class="tile tile--span6 {"tile--success" if csat_week.get("n",0) and int((csat_week.get("pct") or "0").rstrip("%")) >= 80 else ""}">
      <div class="tile__val">{csat_week.get("pct","—")}</div>
      <div class="tile__lbl">CSAT last 7 days</div>
      <div class="tile__sub">{csat_week.get("good",0)} good · {csat_week.get("bad",0)} bad · {csat_week.get("n",0)} rated</div>
    </div>
  </div>
</section>

<!-- SECTION: waves -->
<section class="section" id="waves">
  <div class="section__head"><span class="section__num">01</span><h2 class="section__title">Invite waves</h2></div>
  <div class="timeline">
    {timeline_html}
  </div>
</section>

<!-- SECTION: volume -->
<section class="section" id="volume">
  <div class="section__head"><span class="section__num">02</span><h2 class="section__title">Volume &amp; satisfaction</h2></div>

  <div class="chart-panel">
    <div class="chart-tabs" role="tablist">
      <button class="chart-tab is-active" role="tab" aria-selected="true" aria-controls="pane-daily" data-chart="daily">Daily volume</button>
      <button class="chart-tab" role="tab" aria-selected="false" aria-controls="pane-rate" data-chart="rate">Contact rate</button>
      <button class="chart-tab" role="tab" aria-selected="false" aria-controls="pane-csat" data-chart="csat">CSAT vs volume</button>
    </div>
    <div class="chart-body">
      <div class="chart-pane is-active" id="pane-daily"><canvas id="dailyChart"></canvas></div>
      <div class="chart-pane" id="pane-rate"><canvas id="rateChart"></canvas></div>
      <div class="chart-pane" id="pane-csat"><canvas id="csatChart"></canvas></div>
    </div>
  </div>

  <div class="insight">
    <strong>Capacity projection — next flight</strong> — using Flight 2's {avg_rate}% contact rate, {round(surge*100,0):.0f}% of weekly tickets land on day 2.
    <div class="insight__nums">
      <div class="insight__num"><div class="insight__num-val">~{per_1k}</div><div class="insight__num-lbl">tickets / 1k invites</div></div>
      <div class="insight__num"><div class="insight__num-val">~{day2}</div><div class="insight__num-lbl">day-2 peak</div></div>
      <div class="insight__num"><div class="insight__num-val">{aht_median}</div><div class="insight__num-lbl">median resolution</div></div>
    </div>
  </div>

  <div class="dual">
    <div class="panel">
      <div class="panel__title">Weekly volumes</div>
      <table class="tbl">
        <thead><tr><th>Week</th><th class="num">Tickets</th></tr></thead>
        <tbody>
          {weekly_rows}
        </tbody>
      </table>
    </div>
    <div class="panel">
      <div class="panel__title">Wave legend</div>
      <div style="display:flex;flex-direction:column;gap:var(--space-12)">
        <div style="display:grid;grid-template-columns:auto 1fr;align-items:center;gap:var(--space-8)"><span style="width:12px;height:12px;border-radius:2px;background:var(--color-wave-early);display:inline-block" aria-hidden="true"></span><span>Early Bird (600)</span></div>
        <div style="display:grid;grid-template-columns:auto 1fr;align-items:center;gap:var(--space-8)"><span style="width:12px;height:12px;border-radius:2px;background:var(--color-wave-w1);display:inline-block" aria-hidden="true"></span><span>Flight 2 Wave 1 (500)</span></div>
        <div style="display:grid;grid-template-columns:auto 1fr;align-items:center;gap:var(--space-8)"><span style="width:12px;height:12px;border-radius:2px;background:var(--color-wave-w2);display:inline-block" aria-hidden="true"></span><span>Flight 2 Wave 2 (1,500)</span></div>
      </div>
    </div>
  </div>
</section>

<!-- SECTION: aht -->
<section class="section" id="aht">
  <div class="section__head"><span class="section__num">02a</span><h2 class="section__title">Resolution time (AHT)</h2></div>

  <div class="aht-hero">
    <div class="aht-stat"><div class="aht-stat__val">{aht_median}</div><div class="aht-stat__lbl">Median AHT · calendar hours</div></div>
    <div class="aht-stat"><div class="aht-stat__val">{aht_mean}</div><div class="aht-stat__lbl">Mean AHT · calendar hours</div></div>
    <div class="aht-stat"><div class="aht-stat__val">{aht_p75}</div><div class="aht-stat__lbl">75th percentile</div></div>
    <div class="aht-stat"><div class="aht-stat__val">{frt_median}</div><div class="aht-stat__lbl">Median first reply · calendar</div></div>
  </div>

  <div class="panel panel--spaced">
    <div class="panel__title">How long to close? ({aht_n} solved · calendar hours)</div>
    {aht_dist_html}
    <p class="panel__note">AHT measured in calendar time (creation → solved). Nights and weekends are included — business-hours figures run shorter. DNS setup and GH-linked bugs drive the long tail.</p>
  </div>
{aht_trend_html}
{wdl_html}
</section>

<!-- SECTION: planning -->
<section class="section" id="planning">
  <div class="section__head"><span class="section__num">03</span><h2 class="section__title">Staffing planner</h2></div>
  <div class="dual">
    <div class="panel">
      <div class="panel__title">Projection — next flight</div>
      <table class="tbl">
        <thead><tr><th class="num">Batch size</th><th class="num">Expected tickets</th><th class="num">Day-2 peak</th></tr></thead>
        <tbody>
          {proj_rows}
        </tbody>
      </table>
      <p class="panel__note">Flight 2 Waves 1+2 are complete (2,000 invites). Projections for the next flight use their {avg_rate}% average. <strong>Note:</strong> Wave 2 is only {wave2_age} days old — its true rate may be higher as tickets arrive over 7–14 days. Early Bird rate ({data["wave_stats"][0]["rate"] if data["wave_stats"] else "—"}%) was inflated by misdirected non-subscribers, not a reliable baseline.</p>
    </div>
    <div class="panel">
      <div class="panel__title">Contact rate by wave</div>
      <table class="tbl">
        <thead><tr><th>Wave</th><th>Date</th><th class="num">Invites</th><th class="num">Tickets</th><th class="num">Rate</th></tr></thead>
        <tbody>
          {wave_rows}
        </tbody>
      </table>
    </div>
  </div>
</section>

<!-- SECTION: themes -->
<section class="section" id="themes">
  <div class="section__head"><span class="section__num">04</span><h2 class="section__title">What people ask about</h2></div>

  <div class="panel">
    <div class="theme-block">
      <div class="theme-block__head">
        <div class="theme-block__title">Subscriber themes · Flight 2 era</div>
        <div class="theme-block__meta">Jun 3+ · {f2_total} subscriber tickets · baseline for next flight</div>
      </div>
      <div class="themes">
        {f2_theme_html}
      </div>
      <p class="panel__note">Flight 2 subscriber tickets only (excl. misdirects). Use this for staffing the next flight.</p>
    </div>

    {misdirect_callout}

    <details class="theme-historical">
      <summary>All launch · subscriber-only (excl. misdirected) — {all_sub_total} tickets since May 4</summary>
      <div class="theme-historical__body">
        <div class="themes">
          {all_sub_theme_html}
        </div>
        <p class="panel__note" style="margin-top:var(--space-12)">Blends Early Bird subscriber work with Flight 2 — useful for volume context, but Early Bird waitlist/onboarding themes skew the picture. Prefer Flight 2 era above for staffing the next flight.</p>
      </div>
    </details>

    <details class="theme-historical">
      <summary>Historical — Early Bird misdirects · {misdirect_count} tickets · {misdirect_pct}% of all themes · fixed</summary>
      <div class="theme-historical__body">
        <div class="themes">
          {misdirect_theme_html}
        </div>
        <p class="panel__note" style="margin-top:var(--space-12)">Pre-fix routing (May 4–Jun 2): desktop Thunderbird users and search traffic hit the Thundermail form. Team redirected each ticket and shipped routing fixes — not recurring subscriber demand.</p>
      </div>
    </details>
  </div>
</section>

<!-- SECTION: ideas -->
<section class="section" id="ideas">
  <div class="section__head"><span class="section__num">05</span><h2 class="section__title">Community ideas · {data["ideas_count"]} total</h2></div>

  <div class="panel ideas-header">
    <h3>Top 10 open for discussion</h3>
    <p>Sortable columns · <span class="flag-hot" title="Comments exceed votes on FeatureOS">🔥</span> high discussion (comments &gt; votes)</p>
    <table class="tbl ideas-table" id="ideasTable">
      <thead><tr>
        <th class="num tbl-sort" onclick="sortTable('ideasTable',0,'num')"><span class="tbl-sort__inner"><span>Votes</span><span class="tbl-sort__icon" aria-hidden="true">↕</span></span></th>
        <th class="num tbl-sort" onclick="sortTable('ideasTable',1,'num')"><span class="tbl-sort__inner"><span>Comments</span><span class="tbl-sort__icon" aria-hidden="true">↕</span></span></th>
        <th class="num tbl-sort" onclick="sortTable('ideasTable',2,'num')"><span class="tbl-sort__inner"><span>Score</span><span class="tbl-sort__icon" aria-hidden="true">↕</span></span></th>
        <th class="tbl-sort" onclick="sortTable('ideasTable',3,'str')"><span class="tbl-sort__inner"><span>Idea</span><span class="tbl-sort__icon" aria-hidden="true">↕</span></span></th>
        <th>Tags</th>
      </tr></thead>
      <tbody>
        {idea_rows}
      </tbody>
    </table>
  </div>

  <div class="kanban">
    {kanban_html}
  </div>
</section>

<!-- SECTION: engineering -->
<section class="section" id="engineering">
  <div class="section__head"><span class="section__num">06</span><h2 class="section__title">Engineering escalations · {len(data["gh_tickets"])} of {total} ({gh_pct}%)</h2></div>
  <p class="eng-summary">Tickets tagged <code>zd-gh</code> — linked to a GitHub issue in the thunderbird org via gz# marker.</p>
  <div class="eng-list">
    {eng_open_html}
  </div>
  {eng_done_html}
</section>

<!-- SECTION: glossary -->
<section class="section" id="glossary">
  <div class="section__head"><span class="section__num">07</span><h2 class="section__title">Glossary</h2></div>
  <div class="glossary">
    <details><summary>AHT (Average Handle Time)</summary><div class="glossary__body">Calendar time from ticket creation to resolution (Solved status). Median is used rather than mean to reduce outlier impact. Based on {aht_n} solved tickets.</div></details>
    <details><summary>First Reply Time</summary><div class="glossary__body">Time from ticket creation to the agent's first response. Reported in calendar hours.</div></details>
    <details><summary>Contact Rate</summary><div class="glossary__body">Percentage of invitees who opened a support ticket. Calculated as: tickets ÷ invitees in that wave. A lower contact rate indicates a smoother onboarding experience.</div></details>
    <details><summary>Day-2 Peak</summary><div class="glossary__body">Historically, ~40% of a wave's first-week tickets arrive on the second day after invites go out. Used to estimate staffing needs for a new batch.</div></details>
    <details><summary>Misdirected — wrong product / non-subscriber</summary><div class="glossary__body">Tickets from people who do not have a Thundermail account and contacted support by mistake (e.g. desktop Thunderbird users, people who found the form via search). These are redirected to the correct channel and do not reflect subscriber support demand. A routing issue fixed May 19 (<a href="https://github.com/thunderbird/thunderbird-accounts/issues/834" target="_blank">accounts#834</a>). Flight 2: 0 misdirects. Shown in a collapsed historical section on the themes panel, not in the Flight 2 baseline.</div></details>
    <details><summary>Cumulative contact rate</summary><div class="glossary__body">Running total of tickets divided by total invitees sent at that point in time. Drops sharply when a large new invite wave goes out (more invitees, same tickets).</div></details>
  </div>
</section>

<!-- DATA: last-updated {data["today"]} -->
<footer class="footer">
  Data: Zendesk (Thunderbird Pro brand) · FeatureOS board {FEATUREOS_BOARD_ID} · May 4, 2026 → {data["today"]} ·
  Excludes: closed_by_merge, test tickets, agent-created, known infrastructure tickets.
  Ticket subjects shown with PII redacted; non-English quotes include AI translations.
  · <a href="latest.html">Flight 2 live report</a>
</footer>
</main>
</div>

<!-- GENERATOR: chart/nav JS -->
<script>
Chart.defaults.animation = window.matchMedia('(prefers-reduced-motion: reduce)').matches ? false : Chart.defaults.animation;
const root = getComputedStyle(document.documentElement);
const P = {{
  muted:   root.getPropertyValue('--color-text-muted').trim()  || '#9492b0',
  border:  root.getPropertyValue('--color-surface-border').trim() || '#2b2845',
  primary: root.getPropertyValue('--color-primary').trim()     || '#4d7bf8',
  success: root.getPropertyValue('--color-success').trim()     || '#22c55e',
  onInverse: root.getPropertyValue('--color-on-inverse').trim() || '#ffffff',
  waveEarly: root.getPropertyValue('--color-wave-early').trim() || '#6366f1',
  waveW1:    root.getPropertyValue('--color-wave-w1').trim()   || '#f97316',
  waveW2:    root.getPropertyValue('--color-wave-w2').trim()   || '#ef4444',
}};

const dates      = {json.dumps(data["dates"])};
const daily      = {json.dumps(data["daily"])};
const cumContact = {json.dumps(data["cum_contact"])};
const milestones = [
  {{"date": "{WAVES[0]["date"]}", "label": "{WAVES[0]["label"]}", "color": P.waveEarly}},
  {{"date": "{WAVES[1]["date"]}", "label": "{WAVES[1]["label"]}", "color": P.waveW1}},
  {{"date": "{WAVES[2]["date"]}", "label": "{WAVES[2]["label"]}", "color": P.waveW2}},
];

function buildAnnotations() {{
  const ann = {{}};
  milestones.forEach((m, i) => {{
    const idx = dates.indexOf(m.date);
    if (idx < 0) return;
    ann['line' + i] = {{
      type: 'line', xMin: idx, xMax: idx,
      borderColor: m.color, borderWidth: 2, borderDash: [4,3],
      label: {{ display: true, content: m.label, position: 'start',
               backgroundColor: m.color, color: P.onInverse, font:{{size:9}}, padding:3 }}
    }};
  }});
  return ann;
}}

const gridOpts = {{
  x: {{ ticks:{{color:P.muted,maxTicksLimit:12,maxRotation:45}}, grid:{{color:P.border}} }},
  y: {{ beginAtZero:true, ticks:{{color:P.muted}}, grid:{{color:P.border}} }}
}};

new Chart(document.getElementById('dailyChart'), {{
  type: 'bar',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'Tickets', data: daily,
      backgroundColor: dates.map(d => milestones.find(m=>m.date===d) ? milestones.find(m=>m.date===d).color+'99' : P.primary+'40'),
      borderColor:     dates.map(d => milestones.find(m=>m.date===d) ? milestones.find(m=>m.date===d).color : P.primary),
      borderWidth: 1, borderRadius: 3,
    }}]
  }},
  options: {{
    responsive:true, maintainAspectRatio:true,
    plugins: {{ legend:{{display:false}}, annotation:{{annotations:buildAnnotations()}} }},
    scales: {{ ...gridOpts, y: {{ ...gridOpts.y, ticks:{{...gridOpts.y.ticks, stepSize:1}} }} }}
  }}
}});

new Chart(document.getElementById('rateChart'), {{
  type: 'line',
  data: {{
    labels: dates,
    datasets: [{{
      label: 'Cumulative contact rate (%)', data: cumContact,
      borderColor: P.success, backgroundColor: P.success+'20',
      fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 5,
      pointHoverBackgroundColor: P.success, pointHoverBorderColor: P.onInverse,
      borderWidth: 2,
    }}]
  }},
  options: {{
    responsive:true,
    plugins: {{ legend:{{display:false}}, annotation:{{annotations:buildAnnotations()}} }},
    scales: {{
      x: gridOpts.x,
      y: {{ beginAtZero:true, ticks:{{color:P.muted,callback:v=>v+'%'}}, grid:{{color:P.border}} }}
    }}
  }}
}});

const csatWeekly = {json.dumps(data["csat_weekly"])};
if (csatWeekly.length && document.getElementById('csatChart')) {{
  new Chart(document.getElementById('csatChart'), {{
    data: {{
      labels: csatWeekly.map(w => w.week),
      datasets: [
        {{ type: 'bar', label: 'Tickets', data: csatWeekly.map(w => w.volume),
           backgroundColor: P.primary+'40', borderColor: P.primary, borderWidth: 1,
           borderRadius: 3, yAxisID: 'yVol' }},
        {{ type: 'line', label: 'CSAT %', data: csatWeekly.map(w => w.pct),
           borderColor: P.success, backgroundColor: 'transparent',
           tension: 0.3, pointRadius: 7, pointHoverRadius: 10,
           pointBackgroundColor: P.success, borderWidth: 2, yAxisID: 'yCsat', spanGaps: true }},
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{ legend: {{ labels: {{ color: P.muted, font: {{ size: 11 }} }} }} }},
      scales: {{
        x: {{ ticks: {{ color: P.muted, maxRotation: 45 }}, grid: {{ color: P.border }} }},
        yVol: {{ position: 'left', beginAtZero: true, ticks: {{ color: P.primary, stepSize: 1 }}, grid: {{ color: P.border }}, title: {{ display: true, text: 'Tickets', color: P.primary, font: {{ size: 10 }} }} }},
        yCsat: {{ position: 'right', min: 0, max: 100, ticks: {{ color: P.success, callback: v => v + '%' }}, grid: {{ drawOnChartArea: false }}, title: {{ display: true, text: 'CSAT', color: P.success, font: {{ size: 10 }} }} }},
      }}
    }}
  }});
}}

/* Chart tabs */
document.querySelectorAll('.chart-panel').forEach(panel => {{
  const tabs = panel.querySelectorAll('.chart-tab');
  const panes = panel.querySelectorAll('.chart-pane');
  tabs.forEach(tab => {{
    tab.addEventListener('click', () => {{
      tabs.forEach(t => {{ t.classList.remove('is-active'); t.setAttribute('aria-selected','false'); }});
      panes.forEach(p => p.classList.remove('is-active'));
      tab.classList.add('is-active');
      tab.setAttribute('aria-selected','true');
      const pane = panel.querySelector('#pane-' + tab.dataset.chart);
      if (pane) pane.classList.add('is-active');
    }});
  }});
}});

/* Section nav scroll spy */
const navLinks = document.querySelectorAll('.rail__nav a');
const sectionIds = [...navLinks].map(a => a.getAttribute('href').slice(1));
const sections = sectionIds.map(id => document.getElementById(id)).filter(Boolean);
function setActiveNav(id) {{
  if (!id) return;
  navLinks.forEach(a => a.classList.toggle('is-active', a.getAttribute('href') === '#' + id));
}}
let scrollSpyPaused = false, scrollSpyTimer = null;
function pauseScrollSpy(ms = 800) {{
  scrollSpyPaused = true;
  clearTimeout(scrollSpyTimer);
  scrollSpyTimer = setTimeout(() => {{ scrollSpyPaused = false; }}, ms);
}}
navLinks.forEach(link => {{
  link.addEventListener('click', () => {{
    pauseScrollSpy(1000);
    setActiveNav(link.getAttribute('href').slice(1));
  }});
}});
window.addEventListener('hashchange', () => {{
  pauseScrollSpy(500);
  setActiveNav(location.hash.slice(1));
}});
const observer = new IntersectionObserver(entries => {{
  if (scrollSpyPaused) return;
  const visible = entries.filter(e => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
  if (!visible.length) return;
  const id = visible[0].target.id;
  setActiveNav(id);
  const hash = '#' + id;
  if (location.hash !== hash) history.replaceState(null, '', hash);
}}, {{ rootMargin: '-15% 0px -60% 0px', threshold: [0, 0.15, 0.4] }});
sections.forEach(s => observer.observe(s));
pauseScrollSpy(location.hash ? 1200 : 400);
const initialId = location.hash.slice(1);
setActiveNav(initialId && sectionIds.includes(initialId) ? initialId : 'story');

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

// AHT trend chart
const ahtTrendWeeks = {json.dumps(aht_trend_weeks)};
const ahtTrendBiz   = {json.dumps(aht_trend_biz)};
const ahtTrendCal   = {json.dumps(aht_trend_cal)};
const ahtTrendCum   = {json.dumps(cum_aht_biz)};
if (ahtTrendWeeks.length && document.getElementById('ahtTrendChart')) {{
  new Chart(document.getElementById('ahtTrendChart'), {{
    data: {{
      labels: ahtTrendWeeks,
      datasets: [
        {{
          type: 'bar', label: 'Median (week solved, biz days)',
          data: ahtTrendBiz,
          backgroundColor: P.primary + '55', borderColor: P.primary, borderWidth: 1,
          borderRadius: 3, yAxisID: 'y',
        }},
        {{
          type: 'line', label: 'Cumulative median (biz days)',
          data: ahtTrendCum,
          borderColor: P.success, backgroundColor: 'transparent',
          tension: 0.3, pointRadius: 6, pointHoverRadius: 9,
          pointBackgroundColor: P.success, borderWidth: 2, yAxisID: 'y', spanGaps: true,
        }},
        {{
          type: 'line', label: 'Calendar days (reference)',
          data: ahtTrendCal,
          borderColor: P.muted, backgroundColor: 'transparent',
          borderDash: [5, 4], tension: 0.3, pointRadius: 0, borderWidth: 1.5,
          yAxisID: 'y', spanGaps: true,
        }},
      ]
    }},
    options: {{
      responsive: true,
      interaction: {{ mode: 'index', intersect: false }},
      plugins: {{
        legend: {{ labels: {{ color: P.muted, font: {{ size: 11 }}, boxWidth: 20 }} }},
        annotation: {{ annotations: buildAnnotations() }},
      }},
      scales: {{
        x: {{ ticks: {{ color: P.muted, maxRotation: 45 }}, grid: {{ color: P.border }} }},
        y: {{
          beginAtZero: true,
          ticks: {{ color: P.muted, callback: v => v + ' biz d' }},
          grid: {{ color: P.border }},
          title: {{ display: true, text: 'Business days (12h/day · 8am–8pm ET)', color: P.muted, font: {{ size: 10 }} }},
        }},
      }}
    }}
  }});
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
    aht_mins, frt_mins, aht_by_id = fetch_aht(auth, sub, tickets)
    print(f"  {len(aht_mins)} AHT samples, {len(aht_by_id)} ticket-keyed", file=sys.stderr)

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

    print("Fetching CSAT stats…", file=sys.stderr)
    csat_all = fetch_csat_stats(auth, sub)
    print(f"  Since launch: {csat_all['eb']['pct']} ({csat_all['eb']['n']} rated)", file=sys.stderr)

    data = build(tickets, aht_mins, frt_mins, ideas_all, ideas_top10, gh_links, blockers, csat_all, aht_by_id=aht_by_id)
    html = render(data)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html)
    print(f"Wrote {out}", file=sys.stderr)


if __name__ == "__main__":
    main()
