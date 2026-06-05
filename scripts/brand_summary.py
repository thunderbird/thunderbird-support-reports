#!/usr/bin/env python3
"""Summarize Zendesk tickets for a brand since a given date.

Categorizes tickets by theme using keyword matching and writes a markdown report.
Raw ticket data and reports default to a private path OUTSIDE this (public) repo.

Usage:
  python3 scripts/brand_summary.py --brand "Thunderbird Pro" --since 2026-05-04
  python3 scripts/brand_summary.py --brand "Thunderbird Pro" --since 2026-05-04 \\
      --out ~/Documents/Claude/tbpro_launch_summary.md
"""
import argparse
import base64
import datetime as dt
import json
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

CREDS_PATH = Path.home() / ".config" / "zendesk" / "credentials"
DEFAULT_OUT_DIR = Path.home() / "Documents" / "Claude"


def load_creds():
    data = {}
    for line in CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    return data


def api_get(path, creds, params=None):
    base = f"https://{creds['subdomain']}.zendesk.com/api/v2"
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    auth = f"{creds['email']}/token:{creds['token']}"
    header = "Basic " + base64.b64encode(auth.encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": header, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def fetch_all_tickets(brand, since, creds):
    """Paginate through search until exhausted."""
    query = f'type:ticket brand:"{brand}" created>={since}'
    results = []
    page = 1
    while True:
        data = api_get("/search.json", creds, {"query": query, "per_page": 100, "page": page})
        results.extend(data.get("results", []))
        if not data.get("next_page"):
            break
        page += 1
        if page > 10:
            break
    return results


# Theme detection — regex matched against subject+description (case-insensitive).
# Order matters: first match wins for a ticket's *primary* theme; we also tag
# secondary themes for reporting.
THEMES = [
    # --- Security ---
    ("Security / hacked",
     r"\b(hack(ed|ing)?|compromis|breach|phish|stolen|unauthorized|suspicious activity|fraud)\b"),

    # --- Auth / access (merged: password reset + login issues = same journey) ---
    ("Account access issues",
     r"\b(forgot|reset|recover|recovery|cannot remember|don'?t remember|new password|neues passwort|olvid|passwort vergessen|mot de passe oubli)\b.*\bpassword\b"
     r"|\bpassword\b.*\b(forgot|reset|recover|recovery|reset link)\b"
     r"|\b(forget password|password recovery|password vergessen)\b"
     r"|\b(can'?t (log ?in|sign ?in|access)|unable to (log ?in|sign ?in|access)|login (error|issue|problem|fail)|sign[- ]?in (error|issue|problem|fail)|locked out|access (denied|issue)|won'?t let me (in|log)|login\b|signin\b|wrong (account|username|email)|noted.{0,15}wrong|used (wrong|incorrect).{0,15}(email|username|account))\b"),

    # --- Onboarding / signup ---
    ("Early bird / invite / waitlist",
     r"\b(early bird|early access|invite|invitation|waitlist|join the (beta|program)|when.{0,15}(get|will).{0,15}(in|access)|got (an )?invite)\b"),
    ("Account creation / signup confusion",
     r"\b(sign ?up|signed up|signup|create.{0,20}account|new account)\b"),

    # --- Pricing & plans ---
    ("Pricing / monthly plan / free tier",
     r"\b(month(ly)?[ -]?(plan|subscription|billing)|free (plan|tier|trial|version)|how much|what.{0,10}cost|pricing|price (per|of)|per month|annual (only|plan)|no free|free monthly|pay monthly|monthly fee)\b"),
    ("Subscription / billing / refund / cancel",
     r"\b(subscri|billing|charged|refund|cancel|payment|invoice|cost|plan|tier|upgrade|downgrade|paid|non[- ]?profit|educational|student|discount|charity|free for|nonprofit)\b"),

    # --- Privacy & data ---
    ("Privacy / data / jurisdiction concerns",
     r"\b(privacy|gdpr|dsgvo|data protect|delete (my )?(data|account)|right to erasure|eu (host|based|law|server)|us (law|based|server|jurisdiction)|where.{0,20}(store|host|data)|jurisdiction|data residency|eu only)\b"),

    # --- Thundermail-specific features ---
    ("Webmail",
     r"\b(webmail|web.{0,5}(interface|app|client|access)|browser.{0,10}(access|login|mail)|access.{0,10}browser|web version)\b"),
    ("Thunderbird for Android + Thundermail",
     r"\b(android|mobile|phone|fcm|wns|push notif|mobile (app|client|sync)|thunderbird (for |on )?android|sync.{0,10}(mobile|phone)|android.{0,10}(sync|push|notif))\b"),
    ("Aliases",
     r"\b(alias(es)?|send as|send from|multiple (address|email)|secondary (address|email)|from address|identity)\b"),
    ("Custom domain / DKIM / DNS",
     r"\b(custom domain|dkim|spf|dmarc|dns|mx record|cname|domain setup|own domain|my domain|domain (not|fail|error))\b"),
    ("Send (file sharing)",
     r"\b(thunderbird send|tb send|send\.thunderbird|file (send|upload|share|transfer)|storage (used|space|quota)|upload (fail|error|stuck|progress))\b"),
    ("Appointment / calendar",
     r"\b(appointment|calendar|caldav|carddav|invite|ical|schedule|booking)\b"),

    # --- Pre-purchase & docs ---
    ("Pre-purchase / documentation gap",
     r"\b(document(ation)?|docs|readme|how does it work|before (I |i )(buy|pay|subscribe|sign)|want to know|more info|feature list|what.{0,20}include|what do (I|you) get)\b"),

    # --- Technical setup ---
    ("Email sending / receiving / SMTP / IMAP",
     r"\b(smtp|imap|send(ing)? (email|mail|message)|receiv(e|ing) (email|mail|message)|server (down|caido|caída|caduto)|server (error|issue)|can'?t send|not (sending|receiving)|delivery|outbox)\b"),
    ("App setup / configuration",
     r"\b(set ?up|setup|configur|install|migrat|import|sync|gmail|yahoo|exchange.{0,20}account|3rd party|third[- ]party|connect.{0,20}account|add.{0,20}account|thunderbird desktop)\b"),
    ("Drafts / sending failures / lost mail",
     r"\b(draft|lost (email|mail|message)|disappear|missing (email|mail|message)|attach(ment|ing) (fail|not|lost)|saving draft)\b"),

    # --- Bugs ---
    ("Bug report / app crash / not working",
     r"\b(bug|crash|not work|doesn'?t work|broken|error message|stops? working|freeze|hang|glitch)\b"),

    # --- Misc ---
    ("App Store review (low stars)", r"★[★☆]{0,4}(?![★])|\bstar.{0,5}rating\b"),
]


def classify(text):
    """Return (primary_theme, [all_matched_themes])."""
    matched = []
    for name, pat in THEMES:
        if re.search(pat, text, re.IGNORECASE | re.DOTALL):
            matched.append(name)
    primary = matched[0] if matched else "Other / uncategorized"
    return primary, matched


def short_excerpt(text, limit=240):
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "…"


def build_report(tickets, brand, since, subdomain):
    by_primary = defaultdict(list)
    status_counts = Counter()
    secondary_counts = Counter()
    tag_counts = Counter()
    for t in tickets:
        text = f"{t.get('subject') or ''}\n{t.get('description') or ''}"
        primary, all_themes = classify(text)
        by_primary[primary].append(t)
        status_counts[t.get("status") or "unknown"] += 1
        for th in all_themes[1:]:
            secondary_counts[th] += 1
        for tag in t.get("tags") or []:
            tag_counts[tag] += 1

    total = len(tickets)
    today = dt.date.today().isoformat()
    out = []
    out.append(f"# {brand} — Ticket Summary Since {since}\n")
    out.append(f"_Generated {today} · {total} tickets_\n")

    out.append("## Status breakdown\n")
    for status, n in status_counts.most_common():
        out.append(f"- **{status}**: {n}")
    out.append("")

    out.append("## Themes (primary category per ticket)\n")
    primaries_sorted = sorted(by_primary.items(), key=lambda kv: -len(kv[1]))
    for theme, ts in primaries_sorted:
        pct = 100 * len(ts) / total
        out.append(f"### {theme} — {len(ts)} tickets ({pct:.0f}%)\n")
        # 3 exemplars
        for t in ts[:3]:
            out.append(f"- **#{t['id']}** [{t.get('status')}] · {t.get('created_at','')[:10]} · {t.get('subject') or '(no subject)'}")
            excerpt = short_excerpt(t.get("description"))
            if excerpt:
                out.append(f"  > {excerpt}")
        if len(ts) > 3:
            ids = ", ".join(f"#{t['id']}" for t in ts[3:])
            out.append(f"- _Other {len(ts)-3}: {ids}_")
        out.append("")

    if secondary_counts:
        out.append("## Secondary themes (co-occurring tags)\n")
        for th, n in secondary_counts.most_common(10):
            out.append(f"- {th}: {n}")
        out.append("")

    if tag_counts:
        out.append("## Top Zendesk tags\n")
        for tag, n in tag_counts.most_common(15):
            out.append(f"- `{tag}`: {n}")
        out.append("")

    out.append("## Full ticket list\n")
    out.append("| ID | Status | Created | Subject |")
    out.append("|---:|:------:|:--------|:--------|")
    for t in sorted(tickets, key=lambda x: x.get("created_at") or ""):
        subj = (t.get("subject") or "").replace("|", "\\|")[:90]
        out.append(f"| [{t['id']}](https://{subdomain}.zendesk.com/agent/tickets/{t['id']}) | {t.get('status')} | {t.get('created_at','')[:10]} | {subj} |")

    return "\n".join(out)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--brand", required=True)
    p.add_argument("--since", required=True, help="YYYY-MM-DD")
    p.add_argument("--out", default=None, help=f"Output .md path (default: {DEFAULT_OUT_DIR}/<brand>_summary_<date>.md)")
    p.add_argument("--raw", default=None, help="Path to also save raw JSON dump")
    args = p.parse_args()

    creds = load_creds()
    print(f"Fetching {args.brand} tickets since {args.since}…", file=sys.stderr)
    tickets = fetch_all_tickets(args.brand, args.since, creds)
    print(f"Got {len(tickets)} tickets", file=sys.stderr)

    slug = re.sub(r"[^a-z0-9]+", "_", args.brand.lower()).strip("_")
    out_path = Path(args.out) if args.out else DEFAULT_OUT_DIR / f"{slug}_summary_{dt.date.today().isoformat()}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(tickets, args.brand, args.since, creds["subdomain"])
    out_path.write_text(report)
    print(f"Wrote {out_path}", file=sys.stderr)

    if args.raw:
        raw_path = Path(args.raw)
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(tickets, indent=2))
        print(f"Wrote raw JSON to {raw_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
