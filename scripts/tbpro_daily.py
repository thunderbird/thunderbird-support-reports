#!/usr/bin/env python3
"""TB Pro daily support report.

Aggregates from Zendesk (brand: Thunderbird Pro) and FeatureOS (board 17437):
  - Cumulative + 24-hour ticket volume and status
  - Theme breakdown (reuses brand_summary categorizer)
  - CSAT: today (last 24h solves) + since-launch
  - New FeatureOS ideas in the last 24h + since launch

Output:
  ~/Documents/Claude/tbpro_daily/tbpro_daily_<YYYY-MM-DD>.md

Usage:
  python3 scripts/tbpro_daily.py              # today, ET
  python3 scripts/tbpro_daily.py --date 2026-05-18
  python3 scripts/tbpro_daily.py --post-to-notion   # also POSTs to Notion (requires creds)
"""
import argparse
import base64
import datetime as dt
import html as _html
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

# Reuse the regex categorizer as a fallback
sys.path.insert(0, str(Path(__file__).parent))
from brand_summary import THEMES, classify, short_excerpt  # noqa: E402

# Tag-based theme classification. Tags reflect the *agent's* triage decision
# (via macros applied and admin-defined trees), so they are more accurate than
# regex on raw user text. Order matters: the first matching tag wins.
TAG_THEMES = [
    # ── Account access issues (login + password reset = same journey) ────────
    ("macro_tbpro_cantlogin_no_allowlist",  "Account access issues — not on allowlist yet"),
    ("macro_tbpro_sumo_redirect",           "Account access issues — wrong product, redirected to SUMO"),
    ("macro_tbpro_email_lookup",            "Account access issues — email lookup required"),
    ("tbpro_hub_accounts_login_trouble",    "Account access issues — Account Hub trouble"),
    ("tbpro_hub_what_recover",              "Account access issues — account recovery"),

    # ── Pricing & plans ──────────────────────────────────────────────────────
    ("macro_tbpro_no_free_monthly",         "Pricing — wanted free / monthly plan"),
    ("macro_tbpro_annual_only_beta",        "Pricing — annual-only inquiry"),
    ("tbpro_hub_what_pricing_concerns",     "Pricing — general pricing concern"),
    ("macro_thundermail_discount_pricing",  "Pricing — discount / pricing question"),
    ("tbpro_hub_what_payment",              "Pricing — payment issue"),

    # ── Refund / cancel ──────────────────────────────────────────────────────
    ("tbpro_hub_what_refund",               "Refund / Cancel"),
    ("tbpro_refund",                        "Refund / Cancel"),
    ("tbpro_cancel_unpaid",                 "Refund / Cancel — unpaid"),

    # ── Waitlist / onboarding ────────────────────────────────────────────────
    ("macro_tbpro_waitlist_bump",           "Waitlist / onboarding inquiry"),
    ("tbpro_thundermail_what_accounts_waitlist", "Waitlist / onboarding inquiry"),
    ("accounts__early_bird_signups",        "Early bird signup"),

    # ── Thundermail features ─────────────────────────────────────────────────
    ("tbpro_thundermail_what_aliases",                     "Aliases"),
    ("tbpro_thundermail_what_custom_domains_setup",        "Custom domain setup"),
    ("tbpro_thundermail_what_custom_domains__dns_records", "Custom domain DNS"),
    ("tbpro_thundermail_what_add_account",                 "Add account in Thunderbird"),

    # ── General ──────────────────────────────────────────────────────────────
    ("macro_tbpro_request_or_complaint",    "Request or complaint"),
]
TAG_THEME_SET = {t for t, _ in TAG_THEMES}

# Known fix issues (GitHub issues addressing high-volume root causes).
# Use a *predicate function* on the ticket rather than a theme-label map,
# because: (1) agents are inconsistent about retagging pro_service_*, (2) some
# tickets bear multiple macros, (3) some haven't been macrod yet but match the
# pattern via subject keywords on channel=api.
FIX_ISSUES = {
    "thunderbird/thunderbird-accounts#834": {
        "title": "Non-subscriber login attempts on the Account Hub form",
        # Tense-agnostic so it reads correctly in both historical and post-deploy
        # reports. A date-aware status line is added below at render time.
        "blurb": "The fix changes Account Hub to check the allowlist before "
                 "prompting login, and adds a warning on the Zendesk contact "
                 "form for non-subscribers (\"You don't have an account with "
                 "us yet — join the waitlist\"). Both are intended to stop the "
                 "high-volume mis-directed tickets from people who aren't TB "
                 "Pro subscribers.",
        # First full ET day with the fix in production. Tickets before this
        # date are the pre-fix baseline; tickets on/after are post-fix.
        "deployed_et": "2026-05-19",
    },
}


def fix_status_line(deployed_et, report_date):
    """Date-aware deploy status, so historical reports don't imply a future fix
    was already live."""
    if not deployed_et or not report_date:
        return None
    if report_date < deployed_et:
        return f"_📅 Status as of {report_date}: **not yet deployed** — target {deployed_et}_"
    if report_date == deployed_et:
        return f"_📅 Status: **deployed today** ({deployed_et}) — first post-fix day_"
    rd = dt.date.fromisoformat(report_date)
    dd = dt.date.fromisoformat(deployed_et)
    days = (rd - dd).days
    return f"_📅 Status: **deployed {deployed_et}** ({days} day(s) post-fix)_"


# Hard signals that a ticket came from the non-subscriber Account Hub login form
LOGIN_FORM_MACROS = {
    "macro_tbpro_cantlogin_no_allowlist",
    "macro_tbpro_sumo_redirect",
    "macro_tbpro_email_lookup",
}

# Tags that mean the ticket is from a known/active subscriber (so exclude
# from the #834 bucket even if subject keywords match)
SUBSCRIBER_TAGS = {
    "pro_service_appointment",
    "pro_service_send",
    "tbpro_thundermail_what_aliases",
    "tbpro_thundermail_what_custom_domains_setup",
    "tbpro_thundermail_what_custom_domains__dns_records",
    "tbpro_thundermail_what_add_account",
    "tbpro_refund",
    "tbpro_cancel_unpaid",
}

# Subject-substring heuristics for "looks like a non-subscriber login attempt"
# (multilingual to catch the international ticket flow)
LOGIN_FORM_KEYWORDS = (
    "hack", "stolen", "compromis", "phish",
    "can't log", "cant log", "can't access", "cannot log", "cannot access", "can not log",
    "log in", "login", "sign in", "sign-in", "signin",
    "old thunderbird", "password", "passwort", "mot de passe", "contraseña", "senha",
    "account access", "account creation", "create.*account",
    "acessar", "iniciar", "anmelden", "connexion", "connecter",
    "servidor", "server",
    "verify account", "recovery",
)


def matches_fix_834(ticket):
    """Did this ticket come from the non-subscriber Account Hub login form?"""
    tags = set(ticket.get("tags") or [])
    # Macros agents apply to these tickets — strongest signal
    if LOGIN_FORM_MACROS & tags:
        return True
    # Agent triaged via Account Hub login trouble path
    if "tbpro_hub_accounts_login_trouble" in tags:
        return True
    # Heuristic for tickets without a macro yet (or where the user picked the
    # wrong product on the form and the macros didn't fire)
    via = ticket.get("via") or {}
    if via.get("channel") != "api":
        return False
    # Bail if any subscriber-confirming tag is set — they're a real customer
    if SUBSCRIBER_TAGS & tags:
        return False
    # Bail if this is purely a waitlist status inquiry (no login attempt)
    if ("macro_tbpro_waitlist_bump" in tags
            and "macro_tbpro_cantlogin_no_allowlist" not in tags
            and "tbpro_hub_accounts_login_trouble" not in tags):
        return False
    subject = (ticket.get("subject") or "").lower()
    return any(k in subject for k in LOGIN_FORM_KEYWORDS)


def fix_for(ticket):
    """Return the fix-issue ref this ticket falls under, or None."""
    if matches_fix_834(ticket):
        return "thunderbird/thunderbird-accounts#834"
    return None

SERVICE_TAGS = {
    "pro_service_account_hub": "Account Hub",
    "pro_service_thundermail": "Thundermail",
    "pro_service_appointment": "Appointment",
    "pro_service_send":        "Send",
}

URGENCY_TAGS = {
    "fields_user_urgency_critical": "critical",
    "fields_user_urgency_high":     "high",
    "fields_user_urgency_medium":   "medium",
    "fields_user_urgency_low":      "low",
}

# Agent-set ticket fields capturing user state and our response.
# Order matters — first hit wins (most signal-rich first).
WHY_TAGS = [
    ("why_blocked",   "blocked"),
    ("why_confused",  "confused"),
    ("why_curious",   "curious"),
    ("why_change",    "change request"),
    ("why_request",   "request"),
    ("why_concerned", "concerned"),
    ("why_tell",      "telling us"),
    ("why_praise",    "praise"),
    ("why_other",     "other"),
]
HOW_TAGS = [
    ("how_actioned",     "actioned"),
    ("how_explained",    "explained"),
    ("how_redirected",   "redirected"),
    ("how_escalated",    "escalated"),
    ("how_investigated", "investigated"),
    ("how_informed",     "informed"),
    ("how_na",           "n/a"),
]


def why_for(ticket):
    for tag, label in WHY_TAGS:
        if tag in (ticket.get("tags") or []):
            return label
    return None


def how_for(ticket):
    for tag, label in HOW_TAGS:
        if tag in (ticket.get("tags") or []):
            return label
    return None


def classify_ticket(ticket):
    """Return primary theme. Manual override first, then tag-based, then regex fallback."""
    tid = int(ticket.get("id") or 0)
    if tid in MANUAL_THEMES:
        return MANUAL_THEMES[tid], "manual"
    tags = ticket.get("tags") or []
    for tag, theme in TAG_THEMES:
        if tag in tags:
            return theme, "tag"
    # Fallback to keyword regex on subject+description
    text = f"{ticket.get('subject') or ''}\n{ticket.get('description') or ''}"
    primary, _ = classify(text)
    return primary, "regex"


def services_for(ticket):
    return [name for tag, name in SERVICE_TAGS.items() if tag in (ticket.get("tags") or [])]


def urgency_for(ticket):
    for tag, name in URGENCY_TAGS.items():
        if tag in (ticket.get("tags") or []):
            return name
    return None

BRAND = "Thunderbird Pro"
LAUNCH_DATE     = "2026-06-22"   # Flight 3 Wave 1 start (ticket counts, themes, contact rate)
CSAT_START_DATE = "2026-05-04"   # Early Bird launch — CSAT tracks all-time from here
INVITEE_COUNT = 6500         # Flight 3 · Wave 1 (2026-06-22) + Wave 2 (2026-06-23) + Wave 3 (2026-06-24)
FEATUREOS_BOARD_ID = 17437
EXCLUDE_IDS = {5441, 5866}   # Known infrastructure problems — exclude from all counts
WATCH_PROBLEMS = set()  # No active blockers
MANUAL_THEMES = {            # Force-assign theme for tickets that can't be auto-categorized
    6055: "Account access issues",  # follow-up ticket, no useful subject/tags
}

ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

ZD_CREDS_PATH = Path.home() / ".config" / "zendesk" / "credentials"
NOTION_CREDS_PATH = Path.home() / ".config" / "notion" / "credentials"
DEFAULT_OUT_DIR = Path.home() / "Documents" / "Claude" / "tbpro_daily"


# --- PII redaction (applied when --public) -----------------------------------

PII_PATTERNS = [
    # Emails (includes alias@domain — catches both parts)
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[email]"),
    # Standalone personal domain names and subdomains (e.g. "mycompany.com", "mail.myco.net")
    # Conservative: skip known safe domains
    (re.compile(
        r"(?<!\w)(?!(?:thunderbird|mozilla|mzla|zendesk|github|google|apple|microsoft|"
        r"yahoo|aol|gmail|outlook|hotmail|icloud|fastmail|proton|tutanota)\b)"
        r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,}"
        r"(?:com|net|org|io|co|de|fr|uk|nl|eu|me|app|mail|email|pro|biz|info)\b",
        re.IGNORECASE,
    ), "[domain]"),
    # IP addresses
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[ip]"),
    # Phone numbers (US/intl rough heuristic)
    (re.compile(r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"), "[phone]"),
    # Long digit runs — account / order / case / card numbers (ticket IDs are 4 digits)
    (re.compile(r"(?<!\w)\d{7,}(?!\w)"), "[number]"),
    # Forwarded/quoted email headers inside ticket bodies
    (re.compile(r"\bOn\b[^\n]{0,80}?\bwrote:", re.IGNORECASE), "[quoted message]"),
    (re.compile(r"(?m)^\s*[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2}\s+wrote:"), "[name] wrote:"),
    # Lone "From: Name <email>" headers
    (re.compile(r"From:\s+[^<\n]+<[^>]+>"), "From: [sender]"),
    # Name-after-signoff (multilingual); name may be on the same OR next line. The
    # keyword is case-insensitive (scoped) but the NAME must be Capitalized, so we
    # don't eat ordinary words ("Thanks for your help" stays intact).
    (re.compile(
        r"((?i:Thanks|Thank you|Sincerely|Best regards|Best wishes|Kind regards|"
        r"Warm regards|Regards|Cheers|Yours sincerely|Yours truly|"
        r"Cordialement|Cordialmente|Saludos|Un saludo|Atentamente|"
        r"Mit freundlichen Grüßen|Viele Grüße|Mit besten Grüßen|Liebe Grüße|"
        r"Grazie|Cordiali saluti|Distinti saluti|"
        r"Atenciosamente|Abraços|Met vriendelijke groet))"
        r"\s*[,.!]?\s*\n?\s*([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"
    ), r"\1, [name]"),
    # Greeting-then-name patterns (multilingual)
    (re.compile(
        r"((?i:Hi|Hello|Hey|Dear|Bonjour|Salut|Hola|Hallo|Liebe[rn]?|Ciao|Olá|Beste))"
        r"\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"
    ), r"\1 [name]"),
    # Self-identification: "my name is X"
    (re.compile(r"((?i:my name is))\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"), r"\1 [name]"),
]


def redact(text):
    if not text:
        return text
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    return text


# --- Zendesk -----------------------------------------------------------------

def zd_creds():
    """Read Zendesk creds: env vars first (for CI), then ~/.config file."""
    env_email = os.environ.get("ZENDESK_EMAIL")
    env_token = os.environ.get("ZENDESK_TOKEN")
    env_sub = os.environ.get("ZENDESK_SUBDOMAIN")
    if env_email and env_token and env_sub:
        return {"email": env_email, "token": env_token, "subdomain": env_sub}
    data = {}
    if ZD_CREDS_PATH.exists():
        for line in ZD_CREDS_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                data[k.strip()] = v.strip()
    missing = [k for k in ("email", "token", "subdomain") if k not in data]
    if missing:
        sys.exit(f"Missing Zendesk creds ({', '.join(missing)}). Set ZENDESK_EMAIL/ZENDESK_TOKEN/ZENDESK_SUBDOMAIN env vars or {ZD_CREDS_PATH}")
    return data


def zd_get(path, params=None):
    creds = zd_creds()
    base = f"https://{creds['subdomain']}.zendesk.com/api/v2"
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    auth = f"{creds['email']}/token:{creds['token']}"
    hdr = "Basic " + base64.b64encode(auth.encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": hdr, "Accept": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode())


def zd_search_all(query):
    results = []
    page = 1
    while True:
        d = zd_get("/search.json", {"query": query, "per_page": 100, "page": page})
        results.extend(d.get("results", []))
        if not d.get("next_page"):
            break
        page += 1
        if page > 20:
            break
    return results


def zd_search_count(query):
    """Return result count for a query (single API call, no ticket data returned)."""
    data = zd_get("/search/count.json", {"query": query})
    return data.get("count", 0)


# --- FeatureOS ---------------------------------------------------------------

def github_zendesk_links():
    """Return {zendesk_ticket_id: [{repo,number,title,state,url}]} by parsing
    'gz#<id>' Git-Zen markers in GitHub issue bodies across the thunderbird org.
    Uses GITHUB_TOKEN env (CI) or `gh auth token` (local)."""
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        try:
            token = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True).stdout.strip()
        except FileNotFoundError:
            token = ""
    if not token:
        print("WARN: no GITHUB_TOKEN/gh auth token; skipping GitHub link lookup", file=sys.stderr)
        return {}

    items = []
    for page in range(1, 6):  # cap at 500 results
        url = "https://api.github.com/search/issues?" + urllib.parse.urlencode({
            "q": "gz# org:thunderbird",
            "per_page": 100,
            "page": page,
        })
        req = urllib.request.Request(url, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })
        try:
            with urllib.request.urlopen(req) as r:
                data = json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            print(f"WARN: github search HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
            return {}
        batch = data.get("items", [])
        items.extend(batch)
        if len(batch) < 100:
            break

    mapping = defaultdict(list)
    for i in items:
        body = i.get("body") or ""
        # repo path from html_url: https://github.com/<owner>/<repo>/issues/<n>
        m = re.match(r"https://github\.com/([^/]+/[^/]+)/", i.get("html_url", ""))
        repo = m.group(1) if m else "?"
        for tid in set(re.findall(r"gz#(\d+)", body)):
            mapping[int(tid)].append({
                "repo": repo,
                "number": i.get("number"),
                "title": i.get("title"),
                "state": i.get("state"),
                "url": i.get("html_url"),
            })
    return dict(mapping)


def featureos_posts(board_id=FEATUREOS_BOARD_ID, per_page=100):
    """Pull recent FeatureOS posts via featureos-cli. Returns list of dicts.
    Loud on failure — we'd rather see an error than silently report 0 ideas."""
    q = f"board_id={board_id}&sort=created_at&order=desc&per_page={per_page}&status=all"
    try:
        proc = subprocess.run(
            ["featureos-cli", "posts", "list", "--query", q, "--json"],
            capture_output=True, text=True,
        )
    except FileNotFoundError as e:
        print(f"WARN: featureos-cli not found: {e}", file=sys.stderr)
        return []
    if proc.returncode != 0:
        print(f"WARN: featureos-cli exit {proc.returncode}", file=sys.stderr)
        print(f"  stdout: {proc.stdout[:500]}", file=sys.stderr)
        print(f"  stderr: {proc.stderr[:500]}", file=sys.stderr)
        return []
    out = re.sub(r"\x1b\[[0-9;]*m", "", proc.stdout).strip()
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        idx = out.find("{")
        try:
            data = json.loads(out[idx:]) if idx >= 0 else {}
        except json.JSONDecodeError as e:
            print(f"WARN: featureos-cli returned non-JSON output: {e}", file=sys.stderr)
            print(f"  raw: {out[:500]}", file=sys.stderr)
            return []
    if not data.get("success", True):
        print(f"WARN: featureos-cli API error: {data.get('message')}", file=sys.stderr)
        print(f"  full response: {json.dumps(data)[:500]}", file=sys.stderr)
        return []
    posts = data.get("feature_requests", [])
    if not posts:
        print(f"WARN: featureos-cli returned 0 posts. Response keys: {list(data.keys())}", file=sys.stderr)
        print(f"  raw stdout (first 400): {proc.stdout[:400]!r}", file=sys.stderr)
        print(f"  raw stderr (first 400): {proc.stderr[:400]!r}", file=sys.stderr)
    return posts


# --- Emerging-pattern detection ----------------------------------------------

# Common stop words + Thunderbird/TB-Pro terms that always appear and would
# otherwise dominate any n-gram analysis
STOP_WORDS = {
    # English stop words
    "the","and","you","your","have","with","from","that","this","for","not","but","are",
    "was","were","will","can","cant","cannot","into","there","they","them","their","than",
    "also","just","when","what","where","who","why","how","does","doesnt","didnt","wont",
    "would","could","should","about","ive","its","been","being","more","some","any","all",
    "out","get","got","one","two","like","want","need","please","help","thank","thanks",
    "hello","hi","email","emails","account","accounts","password","login","mail","mails",
    # Multilingual filler
    "que","con","para","mais","mes","mon","ma","der","die","das","ich","ist","est","une",
    "non","sono","della","sehr","auf","mit","aus","una","del","por","para",
    # Thunderbird/product terms (always present)
    "thunderbird","thundermail","tbpro","mozilla","mzla","support",
}


def _tokenize(text):
    text = (text or "").lower()
    text = re.sub(r"https?://\S+", " ", text)
    text = re.sub(r"\[email\]|\[name\]|\[phone\]|\[ip\]|\[sender\]", " ", text)
    text = re.sub(r"[^a-zà-ÿ\s]", " ", text)
    return [w for w in text.split() if len(w) >= 4 and w not in STOP_WORDS]


def _ngrams(words, n):
    return [" ".join(words[i:i+n]) for i in range(len(words) - n + 1)]


def detect_emerging_patterns(cumulative, new_24h, min_new_count=2, min_lift=3.0):
    """Find n-grams that appear in 24h tickets much more than the cumulative
    baseline rate. These are candidate signals for emerging problems.

    Returns list of dicts: {ngram, new_count, older_count, lift, ticket_ids}
    """
    if not new_24h:
        return []

    new_ids = {t["id"] for t in new_24h}
    older = [t for t in cumulative if t["id"] not in new_ids]

    # Compute baseline rate as "older tickets per day since launch"
    launch = dt.date.fromisoformat(LAUNCH_DATE)
    today = dt.date.today()
    older_days = max(1, (today - launch).days)

    def text_of(t):
        return f"{t.get('subject') or ''} {t.get('description') or ''}"

    new_counts = Counter()
    new_ticket_map = defaultdict(set)
    for t in new_24h:
        words = _tokenize(text_of(t))
        seen = set()
        for ng in set(_ngrams(words, 2)) | set(_ngrams(words, 3)):
            new_counts[ng] += 1
            new_ticket_map[ng].add(t["id"])
            seen.add(ng)

    older_counts = Counter()
    for t in older:
        words = _tokenize(text_of(t))
        for ng in set(_ngrams(words, 2)) | set(_ngrams(words, 3)):
            older_counts[ng] += 1

    findings = []
    for ng, new_n in new_counts.items():
        if new_n < min_new_count:
            continue
        older_n = older_counts.get(ng, 0)
        older_rate = older_n / older_days  # tickets-per-day baseline
        if older_rate == 0:
            lift = float("inf")
        else:
            lift = new_n / older_rate
        if lift < min_lift:
            continue
        findings.append({
            "ngram": ng,
            "new_count": new_n,
            "older_count": older_n,
            "older_rate": older_rate,
            "lift": lift,
            "ticket_ids": sorted(new_ticket_map[ng]),
        })

    # Prefer high-count then high-lift; collapse near-duplicates (a 3-gram
    # subsuming a 2-gram with same ticket set)
    findings.sort(key=lambda f: (-f["new_count"], -f["lift"]))
    deduped = []
    seen_ticket_sets = []
    for f in findings:
        ts = set(f["ticket_ids"])
        if any(ts == other for other in seen_ticket_sets):
            continue
        if any(ts.issubset(other) for other in seen_ticket_sets):
            continue
        seen_ticket_sets.append(ts)
        deduped.append(f)
        if len(deduped) >= 8:
            break
    return deduped


# --- Helpers -----------------------------------------------------------------

def parse_iso(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def in_window(ts_str, start_utc):
    ts = parse_iso(ts_str)
    return ts is not None and ts >= start_utc


# --- Report ------------------------------------------------------------------

def build(report_date_et):
    """Generate the report for `report_date_et` (date object in ET)."""
    # Window: the 24h ending at the report date's 4pm ET (i.e. "today's update covers since yesterday 4pm ET")
    window_end_et = dt.datetime.combine(report_date_et, dt.time(16, 0), tzinfo=ET)
    window_start_et = window_end_et - dt.timedelta(hours=24)
    window_start_utc = window_start_et.astimezone(UTC)
    window_end_utc = window_end_et.astimezone(UTC)

    # Zendesk: all tickets since launch.
    # Exclude tickets merged into another (closed_by_merge tag) — they're
    # duplicates of a canonical ticket and would inflate every count.
    cumulative = zd_search_all(f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE}')
    merged_count = sum(1 for t in cumulative if "closed_by_merge" in (t.get("tags") or []))
    cumulative = [t for t in cumulative if "closed_by_merge" not in (t.get("tags") or [])]
    if merged_count:
        print(f"Excluded {merged_count} closed_by_merge tickets (duplicates of canonical)", file=sys.stderr)
    test_count = sum(1 for t in cumulative if (t.get("subject") or "").strip().lower() == "test")
    cumulative = [t for t in cumulative if (t.get("subject") or "").strip().lower() != "test"]
    if test_count:
        print(f"Excluded {test_count} test ticket(s) (subject = 'test')", file=sys.stderr)
    agent_count = sum(1 for t in cumulative if t.get("submitter_id") != t.get("requester_id"))
    cumulative = [t for t in cumulative if t.get("submitter_id") == t.get("requester_id")]
    if agent_count:
        print(f"Excluded {agent_count} agent-created ticket(s) (submitter ≠ requester)", file=sys.stderr)
    excl_count = sum(1 for t in cumulative if int(t.get("id", 0)) in EXCLUDE_IDS)
    cumulative = [t for t in cumulative if int(t.get("id", 0)) not in EXCLUDE_IDS]
    if excl_count:
        print(f"Excluded {excl_count} known-problem ticket(s) {sorted(EXCLUDE_IDS)}", file=sys.stderr)
    inc_excl_count = sum(1 for t in cumulative if int(t.get("problem_id") or 0) in EXCLUDE_IDS)
    cumulative = [t for t in cumulative if int(t.get("problem_id") or 0) not in EXCLUDE_IDS]
    if inc_excl_count:
        print(f"Excluded {inc_excl_count} incident(s) linked to excluded KP(s)", file=sys.stderr)

    # Last 24h slice
    new_24h = [t for t in cumulative if window_start_utc <= parse_iso(t["created_at"]) < window_end_utc]
    solved_24h = [
        t for t in cumulative
        if t.get("status") == "solved" and window_start_utc <= parse_iso(t["updated_at"]) < window_end_utc
    ]

    # Status breakdown
    status_counts = Counter(t.get("status") or "unknown" for t in cumulative)

    # Themes — tag-based first (agent triage decision), regex fallback
    def categorize(tickets):
        primary = defaultdict(list)
        for t in tickets:
            theme, _src = classify_ticket(t)
            primary[theme].append(t)
        return primary

    cumulative_themes = categorize(cumulative)
    new_themes = categorize(new_24h)

    # Service cross-cut (cumulative)
    service_counts = Counter()
    why_how_24h = Counter()
    why_how_cum = Counter()
    for t in cumulative:
        for svc in services_for(t):
            service_counts[svc] += 1
        why = why_for(t)
        how = how_for(t)
        if why or how:
            why_how_cum[(why or "—", how or "—")] += 1
    for t in new_24h:
        why = why_for(t)
        how = how_for(t)
        if why or how:
            why_how_24h[(why or "—", how or "—")] += 1

    # Known problems — group incidents under their problem ticket
    problems = {t["id"]: t for t in cumulative if t.get("type") == "problem"}
    incidents_by_problem = defaultdict(list)
    for t in cumulative:
        pid = t.get("problem_id")
        if pid and t.get("type") == "incident":
            incidents_by_problem[pid].append(t)
    # Also fetch problem tickets the cumulative window doesn't include (so we
    # can render the problem's subject if all incidents reference an older problem)
    missing_pids = [pid for pid in incidents_by_problem if pid not in problems]
    for pid in missing_pids:
        try:
            data = zd_get(f"/tickets/{pid}.json")
            problems[pid] = data.get("ticket", {})
        except Exception as e:
            print(f"WARN: couldn't fetch problem #{pid}: {e}", file=sys.stderr)

    # WATCH_PROBLEMS — always fetch incidents for these problem IDs regardless of LAUNCH_DATE
    for pid in WATCH_PROBLEMS:
        if pid in EXCLUDE_IDS:
            continue
        try:
            if pid not in problems:
                data = zd_get(f"/tickets/{pid}.json")
                problems[pid] = data.get("ticket", {})
            inc_data = zd_get(f"/tickets/{pid}/incidents.json")
            for inc in inc_data.get("tickets", []):
                inc_id = inc.get("id")
                if inc_id and int(inc_id) not in EXCLUDE_IDS:
                    # Avoid duplicates already in cumulative
                    existing_ids = {t["id"] for t in incidents_by_problem[pid]}
                    if inc_id not in existing_ids:
                        incidents_by_problem[pid].append(inc)
        except Exception as e:
            print(f"WARN: couldn't fetch incidents for watch problem #{pid}: {e}", file=sys.stderr)

    # CSAT — cumulative (since launch) and 24h
    good_cum = zd_search_all(f'type:ticket brand:"{BRAND}" status:solved satisfaction:good created>={CSAT_START_DATE}')
    bad_cum = zd_search_all(f'type:ticket brand:"{BRAND}" status:solved satisfaction:bad created>={CSAT_START_DATE}')
    good_24h = [t for t in good_cum if window_start_utc <= parse_iso(t["updated_at"]) < window_end_utc]
    bad_24h = [t for t in bad_cum if window_start_utc <= parse_iso(t["updated_at"]) < window_end_utc]

    def csat_pct(g, b):
        n = len(g) + len(b)
        return (100 * len(g) / n) if n else None

    csat_cum_pct = csat_pct(good_cum, bad_cum)
    csat_24h_pct = csat_pct(good_24h, bad_24h)

    # AHT proxy — updated_at minus created_at for solved tickets (no extra API calls)
    import statistics as _stats
    _solved = [t for t in cumulative if t.get("status") == "solved"
               and t.get("created_at") and t.get("updated_at")]
    _aht_mins = []
    for t in _solved:
        try:
            delta = (parse_iso(t["updated_at"]) - parse_iso(t["created_at"])).total_seconds() / 60
            if 0 < delta < 60 * 24 * 90:  # sanity: between 0 and 90 days
                _aht_mins.append(delta)
        except Exception:
            pass
    aht_data = {
        "median_h": round(_stats.median(_aht_mins) / 60, 1) if _aht_mins else None,
        "mean_h":   round(_stats.mean(_aht_mins) / 60, 1) if _aht_mins else None,
        "n":        len(_aht_mins),
    } if _aht_mins else {}

    # FeatureOS — pull recent, split into "since launch" and "last 24h"
    fos = featureos_posts()
    launch_utc = dt.datetime.fromisoformat(LAUNCH_DATE + "T00:00:00+00:00")
    fos_since_launch = [p for p in fos if parse_iso(p.get("created_at")) and parse_iso(p["created_at"]) >= launch_utc]
    fos_24h = [p for p in fos_since_launch if window_start_utc <= parse_iso(p["created_at"]) < window_end_utc]

    # Emerging-pattern detection — n-grams unusually common in 24h vs baseline
    emerging = detect_emerging_patterns(cumulative, new_24h)

    # GitHub issue links via Git-Zen 'gz#<id>' markers
    gh_links = github_zendesk_links()

    # Refund / cancellation tickets — surface reasons. Zendesk search doesn't
    # honor parenthesized OR groups well, so run each query separately and
    # dedupe by ticket ID.
    refund_queries = [
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} subject:refund',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} subject:cancel',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} subject:cancellation',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} subject:cancelation',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} tags:refund',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} tags:cancellation',
        f'type:ticket brand:"{BRAND}" created>={LAUNCH_DATE} tags:cancel',
    ]
    refunds_by_id = {}
    for q in refund_queries:
        for t in zd_search_all(q):
            if "closed_by_merge" in (t.get("tags") or []):
                continue
            refunds_by_id[t["id"]] = t
    refunds = list(refunds_by_id.values())

    return {
        "report_date": report_date_et.isoformat(),
        "window_start_et": window_start_et.isoformat(),
        "window_end_et": window_end_et.isoformat(),
        "cumulative": cumulative,
        "new_24h": new_24h,
        "solved_24h": solved_24h,
        "status_counts": status_counts,
        "cumulative_themes": cumulative_themes,
        "new_themes": new_themes,
        "good_cum": good_cum,
        "bad_cum": bad_cum,
        "good_24h": good_24h,
        "bad_24h": bad_24h,
        "csat_cum_pct": csat_cum_pct,
        "csat_24h_pct": csat_24h_pct,
        "aht": aht_data,
        "fos_since_launch": fos_since_launch,
        "fos_24h": fos_24h,
        "refunds": refunds,
        "gh_links": gh_links,
        "service_counts": service_counts,
        "problems": problems,
        "incidents_by_problem": dict(incidents_by_problem),
        "why_how_24h": why_how_24h,
        "why_how_cum": why_how_cum,
        "emerging": emerging,
    }


def render_md(d, subdomain="tbpro", public=False):
    """Render markdown. If public=True, scrub PII from all user-supplied text
    (subjects, descriptions, CSAT comments, refund reasons). Counts, ticket
    IDs, FeatureOS titles (already public), themes, and structural fields are
    not redacted — staff need them to act on the report."""
    R = redact if public else (lambda s: s)
    o = []
    gen_time_et = dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    o.append(f"# Thundermail — Flight 3 Live Report · {d['report_date']}")
    o.append("")
    o.append(f"_Updated: **{gen_time_et}** · refreshes hourly_  ")
    o.append(f"_24h window: {d['window_start_et'][:16]} → {d['window_end_et'][:16]} ET · Flight 3 launch: {LAUNCH_DATE} · {INVITEE_COUNT} invitees_")
    o.append("")

    # TL;DR — evergreen summary
    cum = len(d["cumulative"])
    contact_rate = cum / INVITEE_COUNT * 100 if INVITEE_COUNT else 0
    csat_str = f"{d['csat_cum_pct']:.0f}%" if d['csat_cum_pct'] is not None else "no ratings yet"
    top_theme = max(d["cumulative_themes"], key=lambda k: len(d["cumulative_themes"][k])) if d["cumulative_themes"] else None
    n_kp = len(d.get("incidents_by_problem") or {})
    days_since = (dt.date.fromisoformat(str(d["report_date"])) - dt.date.fromisoformat(LAUNCH_DATE)).days + 1
    o.append("## TL;DR")
    o.append("")
    o.append(f"Flight 3 is **day {days_since}** of rollout — **{INVITEE_COUNT:,} invitees**, "
             f"**{cum} tickets** so far ({contact_rate:.1f}% contact rate). "
             f"CSAT since launch: **{csat_str}**. "
             + (f"Top theme: **{top_theme}**. " if top_theme else "")
             + (f"**{n_kp} known problem(s)** being tracked." if n_kp else "No known problems open."))
    o.append("")
    o.append("## At a glance")
    o.append("")
    o.append(f"- **{len(d['new_24h'])}** new tickets in last 24h · **{len(d['solved_24h'])}** solved in last 24h")
    o.append(f"- **{cum}** tickets total since launch · contact rate **{cum/INVITEE_COUNT*100:.0f}%** of {INVITEE_COUNT} invitees")
    csat24 = f"{d['csat_24h_pct']:.0f}%" if d['csat_24h_pct'] is not None else "—"
    csatc = f"{d['csat_cum_pct']:.0f}%" if d['csat_cum_pct'] is not None else "—"
    o.append(f"- **CSAT (24h)**: {csat24}  ({len(d['good_24h'])} good / {len(d['bad_24h'])} bad)")
    o.append(f"- **CSAT (since launch)**: {csatc}  ({len(d['good_cum'])} good / {len(d['bad_cum'])} bad)")
    o.append(f"- **New FeatureOS ideas (24h)**: {len(d['fos_24h'])} · **since launch**: {len(d['fos_since_launch'])}")
    if d.get("aht") and d["aht"].get("median_h") is not None:
        o.append(f"- **Median AHT**: {d['aht']['median_h']}h · mean {d['aht']['mean_h']}h (proxy: updated_at − created_at, {d['aht']['n']} solved tickets)")
    o.append("")

    # =========================================================================
    # STORY — themes, problems, bugs, satisfaction, refunds, ideas
    # =========================================================================

    gh_links = d.get("gh_links") or {}
    cum_ids = {t["id"] for t in d["cumulative"]}

    # Emerging-pattern detection — n-grams unusually frequent in 24h vs baseline
    emerging = d.get("emerging") or []
    if emerging:
        o.append("## 🔎 Emerging patterns to investigate")
        o.append("")
        o.append("_Phrases appearing in 24h tickets at significantly above-baseline rates. "
                 "If a row points at multiple new tickets and the phrase doesn't match an "
                 "existing known problem, it's a candidate for a new one._")
        o.append("")
        for f in emerging:
            ids_str = ", ".join(f"[#{tid}](https://{subdomain}.zendesk.com/agent/tickets/{tid})" for tid in f["ticket_ids"])
            lift_str = "new" if f["lift"] == float("inf") else f"{f['lift']:.1f}× baseline"
            base = f["older_count"]
            o.append(f"- **\"{f['ngram']}\"** — {f['new_count']} tickets in 24h ({lift_str}; baseline {base} cum) — {ids_str}")
        o.append("")

    # Known problems — Zendesk problem-type tickets with their linked incidents
    incidents_by_problem = d.get("incidents_by_problem") or {}
    problems_meta = d.get("problems") or {}
    if incidents_by_problem:
        total_incidents = sum(len(v) for v in incidents_by_problem.values())
        o.append(f"## Known problems — {len(incidents_by_problem)} problem(s), {total_incidents} incident(s)")
        o.append("")
        for pid in sorted(incidents_by_problem.keys()):
            p = problems_meta.get(pid, {})
            p_link = f"https://{subdomain}.zendesk.com/agent/tickets/{pid}"
            p_status = p.get("status", "?")
            p_subj = R(p.get("subject") or "(no subject)")
            o.append(f"### [#{pid}]({p_link}) · [{p_status}] · {p_subj}")
            # Collect GH issues from the problem itself + any of its incidents
            incidents = sorted(incidents_by_problem[pid], key=lambda x: x["created_at"])
            related_gh = {}
            for src_id in [pid] + [inc["id"] for inc in incidents]:
                for issue in gh_links.get(src_id, []):
                    related_gh[issue["url"]] = issue
            for issue in related_gh.values():
                state_tag = "✅" if issue["state"] == "closed" else "🔧"
                o.append(f"- {state_tag} GitHub: [{issue['repo']}#{issue['number']}]({issue['url']}) · _{(issue.get('title') or '')[:80]}_")
            o.append(f"- {len(incidents)} incident(s):")
            for inc in incidents:
                inc_link = f"https://{subdomain}.zendesk.com/agent/tickets/{inc['id']}"
                o.append(f"  - [#{inc['id']}]({inc_link}) · [{inc.get('status')}] · {inc.get('created_at','')[:10]} · _{R(inc.get('subject') or '')}_")
            o.append("")

    # GitHub-linked tickets (everything else not already shown under a problem)
    problem_ids = set(incidents_by_problem.keys())
    incident_ids = {inc["id"] for v in incidents_by_problem.values() for inc in v}
    linked_remaining = {
        tid: issues for tid, issues in gh_links.items()
        if tid in cum_ids and tid not in problem_ids and tid not in incident_ids
    }
    if linked_remaining:
        unique_issues = {issue["url"]: issue for issues in linked_remaining.values() for issue in issues}
        o.append(f"## Other tickets linked to GitHub — {len(linked_remaining)} ticket(s) → {len(unique_issues)} issue(s)")
        o.append("")
        for tid in sorted(linked_remaining.keys(), reverse=True):
            zd_link = f"https://{subdomain}.zendesk.com/agent/tickets/{tid}"
            for issue in linked_remaining[tid]:
                state_tag = "✅" if issue["state"] == "closed" else "🔧"
                o.append(f"- {state_tag} [zd #{tid}]({zd_link}) → [{issue['repo']}#{issue['number']}]({issue['url']}) · _{(issue.get('title') or '')[:80]}_")
        o.append("")

    # Negative CSAT — story-worthy escalations
    o.append("## Negative CSAT (since launch)")
    o.append("")
    bad_total = len(d["bad_cum"])
    if bad_total:
        for t in d["bad_cum"]:
            rating = t.get("satisfaction_rating") or {}
            reason = rating.get("reason") or "—"
            comment = R((rating.get("comment") or "").strip()) or "—"
            link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            o.append(f"- 👎 [{t['id']}]({link}) · _{R(t.get('subject') or '')}_  ")
            o.append(f"  - Reason: **{reason}** · Comment: _{comment}_")
        o.append("")
    else:
        o.append("_No negative ratings since launch._")
        o.append("")

    # Refund / cancellation tickets — scoped to report date
    report_date = d.get("report_date", "")[:10]
    refunds_all = d.get("refunds") or []
    refunds = [t for t in refunds_all if (t.get("created_at") or "")[:10] == report_date]
    o.append(f"## Refund & cancellation tickets (last 24h) — {len(refunds)}")
    o.append("")
    if not refunds:
        o.append("_(none in last 24h)_")
        o.append("")
    else:
        for t in sorted(refunds, key=lambda x: x["created_at"]):
            link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            o.append(f"- [{t['id']}]({link}) · [{t.get('status')}] · _{R(t.get('subject') or '')}_")
            reason = short_excerpt(R(t.get("description")), 220)
            if reason:
                o.append(f"  > {reason}")
        o.append("")

    # Community questions (manual — from data/tbpro_community.json)
    _community_path = Path(__file__).parent.parent / "data" / "tbpro_community.json"
    if _community_path.exists():
        _comm = json.loads(_community_path.read_text()) or {}
        _entries = _comm.get("entries") or []
        _today_entries = [e for e in _entries if str(e.get("date", "")) == str(d["report_date"])]
        if _today_entries:
            o.append("## Community")
            o.append("")
            for e in _today_entries:
                src = e.get("source", "Community")
                qs = e.get("questions") or []
                sigs = e.get("signals") or []
                if qs:
                    o.append(f"**{src}** — {len(qs)} question(s):")
                    for q in qs:
                        o.append(f"- {q}")
                if sigs:
                    if qs:
                        o.append("")
                    o.append(f"**{src}** — signals:")
                    for s in sigs:
                        o.append(f"- {s}")
            o.append("")

    # FeatureOS new ideas
    o.append("## New ideas on FeatureOS")
    o.append("")
    o.append(f"**Last 24h** — {len(d['fos_24h'])} new:")
    o.append("")
    if not d["fos_24h"]:
        o.append("- _(none)_")
    else:
        for p in d["fos_24h"]:
            tags = ", ".join(t.get("name", "") for t in (p.get("tags") or [])) or "untagged"
            votes = p.get("votes_count", 0)
            o.append(f"- [{p.get('title')}]({p.get('url')}) · {votes} votes · _{tags}_")
            preview = (p.get("preview") or "").strip().replace("\n", " ")
            if preview:
                o.append(f"  > {short_excerpt(preview, 200)}")
    o.append("")

    # =========================================================================
    # DRILL-INS — full ticket lists, status/service breakdowns
    # =========================================================================

    o.append("## Status breakdown (cumulative)")
    o.append("")
    for s, n in d["status_counts"].most_common():
        o.append(f"- **{s}**: {n}")
    o.append("")

    if d.get("service_counts"):
        o.append("## Service (cumulative)")
        o.append("")
        for svc, n in d["service_counts"].most_common():
            o.append(f"- **{svc}**: {n}")
        o.append("")

    # Why × How cross-cut (cumulative) — the user state × our response pattern
    why_how_cum = d.get("why_how_cum") or Counter()
    if why_how_cum:
        o.append("## Why × How (cumulative)")
        o.append("")
        o.append("_How the user arrived (why) and how we resolved it (how) — agent-assigned per ticket._")
        o.append("")
        for (why, how), n in why_how_cum.most_common():
            o.append(f"- **{why}** + **{how}**: {n}")
        o.append("")

    # Per-ticket detail grouped by theme (moved here from story section as drill-in)
    o.append("## Tickets in last 24h — by theme")
    o.append("")
    if not d["new_themes"]:
        o.append("_(no new tickets)_")
        o.append("")
    else:
        for theme, ts in sorted(d["new_themes"].items(), key=lambda kv: -len(kv[1])):
            o.append(f"### {theme} — {len(ts)} tickets")
            o.append("")
            for t in ts:
                excerpt = short_excerpt(R(t.get("description")), 180)
                tid_link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
                gh_note = ""
                if t["id"] in gh_links:
                    gh_note = " · 🔗 " + ", ".join(f"[{i['repo']}#{i['number']}]({i['url']})" for i in gh_links[t["id"]])
                why = why_for(t)
                how = how_for(t)
                wh_bits = []
                if why: wh_bits.append(f"why: **{why}**")
                if how: wh_bits.append(f"how: **{how}**")
                wh_note = " — " + " · ".join(wh_bits) if wh_bits else ""
                o.append(f"- **[#{t['id']}]({tid_link})** · {R(t.get('subject') or '(no subject)')}{wh_note}{gh_note}")
                if excerpt:
                    o.append(f"  > {excerpt}")
            o.append("")

    o.append("## New tickets — last 24h")
    o.append("")
    if not d["new_24h"]:
        o.append("_(none)_")
    else:
        for t in sorted(d["new_24h"], key=lambda x: x["created_at"]):
            link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            gh_note = ""
            if t["id"] in gh_links:
                gh_note = " 🔗 " + ", ".join(f"[{i['repo']}#{i['number']}]({i['url']})" for i in gh_links[t["id"]])
            o.append(f"- [{t['id']}]({link}) · [{t.get('status')}] · {t.get('created_at','')[:16]} · {R((t.get('subject') or ''))[:100]}{gh_note}")
    o.append("")

    o.append("## Solved — last 24h")
    o.append("")
    if not d["solved_24h"]:
        o.append("_(none)_")
    else:
        good_ids = {t["id"] for t in d["good_24h"]}
        bad_ids = {t["id"] for t in d["bad_24h"]}
        for t in sorted(d["solved_24h"], key=lambda x: x["updated_at"]):
            tag = "👍" if t["id"] in good_ids else ("👎" if t["id"] in bad_ids else "·")
            link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            o.append(f"- {tag} [{t['id']}]({link}) · {t.get('updated_at','')[:16]} · {R((t.get('subject') or ''))[:100]}")
    o.append("")

    o.append("---")
    o.append("_**Legend:** 🔎 emerging pattern · 🔧 open GitHub issue · ✅ closed GitHub issue · 🔗 linked issue · 👍 positive CSAT · 👎 negative CSAT_")
    o.append("")

    return "\n".join(o)


# --- HTML renderer (Bolt design system) --------------------------------------

_BOLT_CSS = """
:root {
  --bg:          #0d0c14;
  --bg-lower:    #060618;
  --bg-card:     #15131e;
  --border:      #2b2845;
  --border-ia:   #3e3b62;
  --primary:     #4d7bf8;
  --primary-bg:  #0e1038;
  --secondary:   #7c3aed;
  --text:        #e2e0f0;
  --text-2:      #b0aece;
  --text-3:      #7a7898;
  --success:     #22c55e;
  --success-bg:  #041d0e;
  --warning:     #f59e0b;
  --warning-bg:  #1c1200;
  --critical:    #ef4444;
  --critical-bg: #2a0808;
  --teal:        #00d4a0;
  --orange:      #f97316;
}
*{box-sizing:border-box;margin:0;padding:0;}
body{background:var(--bg);color:var(--text);font-family:'Inter',system-ui,-apple-system,'Segoe UI',sans-serif;font-size:15px;line-height:1.5;padding:2rem;max-width:920px;margin:0 auto;}
a{color:var(--primary);text-decoration:none;}
a:hover{text-decoration:underline;}
.header{padding-bottom:1.25rem;border-bottom:1px solid var(--border);margin-bottom:1.75rem;}
.header-badge{display:inline-flex;align-items:center;gap:.35rem;font-size:.68rem;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--primary);background:var(--primary-bg);border:1px solid var(--border-ia);border-radius:5px;padding:.2rem .55rem;margin-bottom:.65rem;}
.header-title{font-size:1.4rem;font-weight:700;margin-bottom:.3rem;}
.header-meta{font-size:.8rem;color:var(--text-2);}
h2{font-size:.9rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-3);margin:1.75rem 0 .75rem;padding-bottom:.4rem;border-bottom:1px solid var(--border);}
h3{font-size:.875rem;font-weight:600;color:var(--text-2);margin:.9rem 0 .35rem;}
.metrics{display:grid;grid-template-columns:repeat(auto-fill,minmax(152px,1fr));gap:.65rem;margin-bottom:1.5rem;}
.metric{background:var(--bg-card);border:1px solid var(--border);border-radius:8px;padding:.875rem 1rem;}
.metric.blue{border-left:3px solid var(--primary);}
.metric.green{border-left:3px solid var(--success);}
.metric.teal{border-left:3px solid var(--teal);}
.metric.orange{border-left:3px solid var(--orange);}
.metric-val{font-size:1.55rem;font-weight:700;line-height:1;margin-bottom:.15rem;}
.metric-label{font-size:.68rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--text-3);}
.metric-sub{font-size:.7rem;color:var(--text-2);margin-top:.15rem;}
.csat-bar{height:5px;border-radius:3px;background:var(--border);overflow:hidden;margin:.35rem 0;}
.csat-fill{height:100%;background:var(--success);border-radius:3px;}
.card{background:var(--bg-card);border:1px solid var(--border);border-radius:10px;padding:1.1rem 1.35rem;margin-bottom:.75rem;}
.fix-card{background:var(--bg-lower);border:1px solid var(--border-ia);border-left:3px solid var(--warning);border-radius:8px;padding:1rem 1.25rem;margin-bottom:.75rem;}
.fix-card-header{display:flex;align-items:baseline;justify-content:space-between;gap:.75rem;margin-bottom:.4rem;}
.fix-card-title{font-size:.875rem;font-weight:600;}
.fix-counts{font-size:.75rem;color:var(--text-2);}
.fix-status{font-size:.75rem;color:var(--text-2);font-style:italic;margin-bottom:.45rem;padding:.3rem .6rem;background:var(--border);border-radius:4px;display:inline-block;}
.fix-blurb{font-size:.78rem;color:var(--text-3);line-height:1.65;margin:.45rem 0;}
.chart{font-family:'JetBrains Mono','Fira Mono',monospace;font-size:.75rem;line-height:1.8;margin:.6rem 0;}
.chart-row{display:flex;align-items:center;gap:.5rem;flex-wrap:nowrap;}
.chart-d{width:5.5rem;color:var(--text-3);flex-shrink:0;}
.chart-n{width:3.5rem;font-size:.68rem;color:var(--text-2);flex-shrink:0;text-align:right;}
.chart-b{flex:1;white-space:pre;}
.chart-note{color:var(--primary);font-size:.7rem;font-style:italic;}
.chart-legend{font-size:.72rem;color:var(--text-3);margin-bottom:.3rem;}
.pattern-item{background:var(--bg-lower);border-left:2px solid var(--teal);border-radius:5px;padding:.5rem .75rem;margin-bottom:.4rem;}
.pattern-phrase{font-weight:700;color:var(--teal);font-size:.82rem;}
.pattern-meta{font-size:.72rem;color:var(--text-2);margin-top:.15rem;}
.badge{display:inline-block;font-size:.62rem;font-weight:700;padding:.1rem .4rem;border-radius:4px;letter-spacing:.04em;}
.badge-blue{background:var(--primary-bg);color:var(--primary);border:1px solid var(--border-ia);}
.badge-green{background:var(--success-bg);color:var(--success);}
.badge-red{background:var(--critical-bg);color:var(--critical);}
.badge-yellow{background:var(--warning-bg);color:var(--warning);}
.badge-muted{background:var(--border);color:var(--text-2);}
.ideas-list{list-style:none;padding:0;}
.idea-item{display:flex;justify-content:space-between;align-items:flex-start;gap:.75rem;padding:.4rem 0;border-bottom:1px solid var(--border);}
.idea-item:last-child{border-bottom:none;}
.idea-title{font-size:.82rem;}
.idea-meta{font-size:.68rem;color:var(--text-3);white-space:nowrap;margin-top:.1rem;}
.neg-item{background:var(--critical-bg);border:1px solid #4a1010;border-radius:6px;padding:.6rem .8rem;margin-bottom:.4rem;}
.neg-reason{font-size:.72rem;font-weight:700;color:var(--critical);}
.neg-comment{font-size:.77rem;color:var(--text-2);margin-top:.2rem;}
.refund-item{padding:.45rem 0;border-bottom:1px solid var(--border);font-size:.8rem;}
.refund-excerpt{font-size:.73rem;color:var(--text-3);margin-top:.2rem;padding-left:.65rem;border-left:2px solid var(--border-ia);line-height:1.55;}
.theme-row{display:block;padding:.3rem 0;border-bottom:1px solid var(--border);}
.theme-row summary{display:flex;align-items:center;gap:.75rem;}
.theme-name{flex:1;font-size:.8rem;}
.theme-count{font-size:.78rem;font-weight:600;color:var(--primary);width:2rem;text-align:right;flex-shrink:0;}
.theme-bar-wrap{width:6rem;height:4px;background:var(--border);border-radius:2px;overflow:hidden;flex-shrink:0;}
.theme-bar-fill{height:100%;background:var(--primary);border-radius:2px;}
.footer{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--border);font-size:.72rem;color:var(--text-3);}
ul.report-list{list-style:none;padding:0;}
ul.report-list li{font-size:.82rem;padding:.2rem 0;border-bottom:1px solid var(--border);}
ul.report-list li:last-child{border-bottom:none;}
"""


def _h(s):
    return _html.escape(str(s) if s is not None else "")


def render_html(d, subdomain="tbpro", public=False):
    """Render a self-contained HTML report using Bolt design system tokens."""
    R = redact if public else (lambda s: s)

    def hR(s):
        return _h(R(s) if s else "")

    p = []

    p.append(f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Thundermail · Flight 3 Live Report · {_h(d['report_date'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>{_BOLT_CSS}</style>
</head>
<body>
""")

    # --- Header ---
    window_start = (d.get("window_start_et") or "")[:16]
    window_end   = (d.get("window_end_et")   or "")[:16]
    p.append(f"""<div class="header">
  <div class="header-badge">&#9889; Thundermail</div>
  <div class="header-title">Flight 3 &mdash; Live Support Report &middot; {_h(d['report_date'])}</div>
  <div class="header-meta">Updated: <strong>{_h(dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET"))}</strong> &nbsp;&middot;&nbsp; refreshes hourly &nbsp;&middot;&nbsp; 24h window: {_h(window_start)} &rarr; {_h(window_end)} ET
    &nbsp;&middot;&nbsp; Flight 3 launch: {_h(LAUNCH_DATE)} &nbsp;&middot;&nbsp; {_h(INVITEE_COUNT)} invitees</div>
</div>
""")

    # --- TL;DR banner ---
    cum = len(d["cumulative"])
    _cr = f"{cum / INVITEE_COUNT * 100:.1f}%" if INVITEE_COUNT else "—"
    _csat_tl = f"{d['csat_cum_pct']:.0f}%" if d.get("csat_cum_pct") is not None else "no ratings yet"
    _top_theme = max(d["cumulative_themes"], key=lambda k: len(d["cumulative_themes"][k])) if d.get("cumulative_themes") else None
    _n_kp = len(d.get("incidents_by_problem") or {})
    _days = (dt.date.fromisoformat(str(d["report_date"])) - dt.date.fromisoformat(LAUNCH_DATE)).days + 1
    _kp_str = f" &nbsp;·&nbsp; <strong>{_n_kp} known problem(s)</strong> tracked" if _n_kp else " &nbsp;·&nbsp; No known problems open"
    _theme_str = f" &nbsp;·&nbsp; Top theme: <strong>{_h(_top_theme)}</strong>" if _top_theme else ""
    p.append(f'<div style="background:var(--surface-2);border:1px solid var(--border);border-left:4px solid var(--primary);'
             f'border-radius:8px;padding:.9rem 1.25rem;margin-bottom:1.5rem;font-size:.88rem;line-height:1.6">'
             f'<strong>Flight 3 · Day {_days}</strong> &nbsp;·&nbsp; '
             f'<strong>{INVITEE_COUNT:,}</strong> invitees &nbsp;·&nbsp; '
             f'<strong>{cum}</strong> tickets ({_cr} contact rate) &nbsp;·&nbsp; '
             f'CSAT: <strong>{_csat_tl}</strong>'
             f'{_theme_str}{_kp_str}'
             f'</div>\n')

    # --- At a glance metrics ---
    contact_rate = f"{cum / INVITEE_COUNT * 100:.0f}%"
    csat24_pct  = d.get("csat_24h_pct")
    csatc_pct   = d.get("csat_cum_pct")
    csat24_str  = f"{csat24_pct:.0f}%" if csat24_pct is not None else "—"
    csatc_str   = f"{csatc_pct:.0f}%" if csatc_pct is not None else "—"
    g24, b24    = len(d["good_24h"]), len(d["bad_24h"])
    gc, bc      = len(d["good_cum"]), len(d["bad_cum"])
    fos24       = len(d["fos_24h"])
    fos_tot     = len(d["fos_since_launch"])
    new_n       = len(d["new_24h"])
    sol_n       = len(d["solved_24h"])

    p.append('<h2>At a Glance</h2>\n<div class="metrics">\n')
    p.append(f'<div class="metric blue"><div class="metric-val">{new_n}</div>'
             f'<div class="metric-label">New (24h)</div>'
             f'<div class="metric-sub">{sol_n} solved</div></div>\n')
    p.append(f'<div class="metric blue"><div class="metric-val">{cum}</div>'
             f'<div class="metric-label">Total since launch</div>'
             f'<div class="metric-sub">Contact rate: {contact_rate}</div></div>\n')

    csat24_fill = f"{csat24_pct:.0f}" if csat24_pct is not None else "0"
    p.append(f'<div class="metric green"><div class="metric-val">{csat24_str}</div>'
             f'<div class="metric-label">CSAT 24h</div>'
             f'<div class="csat-bar"><div class="csat-fill" style="width:{csat24_fill}%"></div></div>'
             f'<div class="metric-sub">{g24} good / {b24} bad</div></div>\n')

    csatc_fill = f"{csatc_pct:.0f}" if csatc_pct is not None else "0"
    p.append(f'<div class="metric green"><div class="metric-val">{csatc_str}</div>'
             f'<div class="metric-label">CSAT since launch</div>'
             f'<div class="csat-bar"><div class="csat-fill" style="width:{csatc_fill}%"></div></div>'
             f'<div class="metric-sub">{gc} good / {bc} bad</div></div>\n')

    p.append(f'<div class="metric teal"><div class="metric-val">{fos24}</div>'
             f'<div class="metric-label">FeatureOS ideas (24h)</div>'
             f'<div class="metric-sub">{fos_tot} since launch</div></div>\n')
    _aht = d.get("aht") or {}
    if _aht.get("median_h") is not None:
        p.append(f'<div class="metric"><div class="metric-val">{_aht["median_h"]}h</div>'
                 f'<div class="metric-label">Median AHT</div>'
                 f'<div class="metric-sub" title="AHT proxy: updated_at − created_at for {_aht["n"]} solved tickets">mean {_aht["mean_h"]}h · {_aht["n"]} solved</div></div>\n')
    p.append('</div>\n')

    gh_links = d.get("gh_links") or {}

    # --- Emerging patterns ---
    emerging = d.get("emerging") or []
    if emerging:
        p.append('<h2>&#128270; Emerging Patterns</h2>\n')
        p.append('<p style="font-size:.78rem;color:var(--text-3);margin-bottom:.65rem">'
                 'Phrases appearing in 24h tickets at significantly above-baseline rates.</p>\n')
        for f in emerging:
            ids_html = ", ".join(
                f'<a href="https://{subdomain}.zendesk.com/agent/tickets/{tid}">#{_h(str(tid))}</a>'
                for tid in f["ticket_ids"]
            )
            lift_str = "new" if f["lift"] == float("inf") else f"{f['lift']:.1f}&times; baseline"
            p.append(f'<div class="pattern-item">'
                     f'<div class="pattern-phrase">"{_h(f["ngram"])}"</div>'
                     f'<div class="pattern-meta">{_h(str(f["new_count"]))} tickets in 24h &mdash; {lift_str} (baseline {_h(str(f["older_count"]))} cum) &mdash; {ids_html}</div>'
                     f'</div>\n')

    # --- CSAT detail ---
    if bc:
        p.append('<h2>&#128078; Negative CSAT (since launch)</h2>\n')
        for t in d["bad_cum"]:
            rating  = t.get("satisfaction_rating") or {}
            reason  = rating.get("reason") or "—"
            comment = hR((rating.get("comment") or "").strip()) or "—"
            link    = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            subj    = hR(t.get("subject") or "")
            p.append(f'<div class="neg-item">'
                     f'<a href="{_h(link)}">#{_h(str(t["id"]))}</a>'
                     f' &middot; <em>{subj}</em><br>'
                     f'<span class="neg-reason">{_h(reason)}</span>'
                     f'<div class="neg-comment">{comment}</div>'
                     f'</div>\n')

    # --- Community questions ---
    _community_path2 = Path(__file__).parent.parent / "data" / "tbpro_community.json"
    if _community_path2.exists():
        _comm2 = json.loads(_community_path2.read_text()) or {}
        _entries2 = _comm2.get("entries") or []
        _today2 = [e for e in _entries2 if str(e.get("date", "")) == str(d["report_date"])]
        if _today2:
            p.append('<h2>&#128172; Community</h2>\n')
            for e in _today2:
                src = _h(e.get("source", "Community"))
                qs = e.get("questions") or []
                sigs = e.get("signals") or []
                if qs:
                    p.append(f'<h3>{src} &mdash; {len(qs)} question(s)</h3>\n<ul class="report-list">\n')
                    for q in qs:
                        p.append(f'<li>{_h(q)}</li>\n')
                    p.append('</ul>\n')
                if sigs:
                    p.append(f'<h3>{src} &mdash; signals</h3>\n<ul class="report-list">\n')
                    for s in sigs:
                        p.append(f'<li>{_h(s)}</li>\n')
                    p.append('</ul>\n')

    # --- FeatureOS ideas ---
    p.append('<h2>&#128161; FeatureOS Ideas</h2>\n')
    p.append(f'<h3>Last 24h &mdash; {fos24} new</h3>\n')
    if d["fos_24h"]:
        p.append('<ul class="ideas-list">\n')
        for post in d["fos_24h"]:
            tags  = ", ".join(t.get("name", "") for t in (post.get("tags") or [])) or "untagged"
            votes = post.get("votes_count", 0)
            url   = _h(post.get("url") or "")
            title = _h(post.get("title") or "")
            preview = (post.get("preview") or "").strip().replace("\n", " ")
            p.append(f'<li class="idea-item">'
                     f'<div><div class="idea-title"><a href="{url}">{title}</a></div>'
                     f'{"<div class=idea-meta>" + _h(short_excerpt(preview, 160)) + "</div>" if preview else ""}'
                     f'</div>'
                     f'<div class="idea-meta">{votes} &#9651; &middot; {_h(tags)}</div>'
                     f'</li>\n')
        p.append('</ul>\n')
    else:
        p.append('<p style="font-size:.8rem;color:var(--text-3)">(none)</p>\n')

    # --- Drill-ins ---
    p.append('<h2>&#128202; Drill-ins</h2>\n')

    # Theme breakdown (cumulative) — expandable ticket list per theme
    _cum_raw = d.get("cumulative_themes") or {}
    cum_themes = Counter({k: len(v) for k, v in _cum_raw.items()}) if _cum_raw else Counter()
    if cum_themes:
        p.append('<h3>Theme breakdown (cumulative) <span style="font-size:.75rem;font-weight:400;color:var(--text-3)">— click a theme to expand tickets</span></h3>\n')
        max_n = max(cum_themes.values())
        for theme, n in cum_themes.most_common():
            pct = int(n / max_n * 100) if max_n else 0
            tickets = sorted(_cum_raw.get(theme, []), key=lambda t: t.get("created_at", ""), reverse=True)
            ticket_list = "".join(
                f'<li style="font-size:.82rem;padding:.2rem 0">'
                f'<a href="https://{subdomain}.zendesk.com/agent/tickets/{t["id"]}" '
                f'target="_blank" style="color:var(--accent-2);font-weight:600">#{t["id"]}</a>'
                f' — {_h(R((t.get("subject") or "").strip())[:80])}'
                f'</li>'
                for t in tickets
            )
            p.append(
                f'<details class="theme-row">'
                f'<summary style="cursor:pointer;list-style:none;display:flex;align-items:center;gap:.5rem">'
                f'<span style="font-size:.8rem;color:var(--text-3);margin-right:.25rem">▶</span>'
                f'<div class="theme-name">{_h(theme)}</div>'
                f'<div class="theme-count">{n}</div>'
                f'<div class="theme-bar-wrap"><div class="theme-bar-fill" style="width:{pct}%"></div></div>'
                f'</summary>'
                f'<ul style="margin:.4rem 0 .5rem 1.5rem;padding:0;list-style:none">{ticket_list}</ul>'
                f'</details>\n'
            )

    # Status breakdown
    p.append('<h3>Status breakdown (cumulative)</h3>\n')
    p.append('<ul class="report-list">\n')
    for s, n in d["status_counts"].most_common():
        p.append(f'<li><strong>{_h(s)}</strong>: {n}</li>\n')
    p.append('</ul>\n')

    # Known problems
    incidents_by_problem = d.get("incidents_by_problem") or {}
    problems_meta        = d.get("problems") or {}
    if incidents_by_problem:
        total_inc = sum(len(v) for v in incidents_by_problem.values())
        p.append(f'<h3>Known problems &mdash; {len(incidents_by_problem)} problem(s), {total_inc} incident(s)</h3>\n')
        for pid in sorted(incidents_by_problem.keys()):
            prob   = problems_meta.get(pid, {})
            p_link = f"https://{subdomain}.zendesk.com/agent/tickets/{pid}"
            subj   = hR(prob.get("subject") or "(no subject)")
            status = _h(prob.get("status") or "?")
            all_gh  = {}
            for src in [prob] + incidents_by_problem[pid]:
                for iss in gh_links.get(src.get("id"), []):
                    all_gh[iss["url"]] = iss
            gh_html = " ".join(
                f'<a href="{_h(i["url"])}">{_h(i["repo"])}#{_h(str(i["number"]))}</a>'
                for i in all_gh.values()
            )
            inc_ids = ", ".join(
                f'<a href="https://{subdomain}.zendesk.com/agent/tickets/{inc["id"]}">#{inc["id"]}</a>'
                for inc in incidents_by_problem[pid]
            )
            p.append(f'<div class="card" style="margin-bottom:.5rem">'
                     f'<strong><a href="{_h(p_link)}">#{pid}</a></strong>'
                     f' <span class="badge badge-muted">{status}</span>'
                     f' &mdash; {subj}')
            if all_gh:
                p.append(f'<br><span style="font-size:.72rem;color:var(--text-3)">GH: {gh_html}</span>')
            p.append(f'<br><span style="font-size:.72rem;color:var(--text-3)">Incidents: {inc_ids}</span>'
                     f'</div>\n')

    # Refunds — scoped to report date
    report_date = d.get("report_date", "")[:10]
    refunds = [t for t in (d.get("refunds") or []) if (t.get("created_at") or "")[:10] == report_date]
    if refunds:
        p.append(f'<h3>Refund &amp; cancellation tickets (last 24h) &mdash; {len(refunds)}</h3>\n')
        for t in sorted(refunds, key=lambda x: x["created_at"]):
            link = f"https://{subdomain}.zendesk.com/agent/tickets/{t['id']}"
            subj = hR(t.get("subject") or "")
            excerpt = hR(short_excerpt(R(t.get("description") or ""), 200))
            status = _h(t.get("status") or "")
            p.append(f'<div class="refund-item">'
                     f'<a href="{_h(link)}">#{_h(str(t["id"]))}</a>'
                     f' <span class="badge badge-muted">{status}</span>'
                     f' &middot; <em>{subj}</em>')
            if excerpt:
                p.append(f'<div class="refund-excerpt">{excerpt}</div>')
            p.append('</div>\n')

    # Why × How
    why_how_cum = d.get("why_how_cum") or Counter()
    if why_how_cum:
        p.append('<h3>Why &times; How (cumulative)</h3>\n')
        p.append('<ul class="report-list">\n')
        for (why, how), n in why_how_cum.most_common():
            p.append(f'<li><strong>{_h(why)}</strong> + <strong>{_h(how)}</strong>: {n}</li>\n')
        p.append('</ul>\n')

    # Footer
    p.append(
        '<div style="font-size:.72rem;color:var(--text-3);margin:1.5rem 0 .5rem;padding-top:.75rem;'
        'border-top:1px solid var(--border)">'
        '<strong>Legend:</strong> '
        '🔎 emerging pattern &nbsp;&middot;&nbsp; '
        '🔧 open GitHub issue &nbsp;&middot;&nbsp; '
        '✅ closed GitHub issue &nbsp;&middot;&nbsp; '
        '🔗 linked issue &nbsp;&middot;&nbsp; '
        '👍 positive CSAT &nbsp;&middot;&nbsp; '
        '👎 negative CSAT'
        '</div>\n'
    )
    gen_time = dt.datetime.now(ET).strftime("%Y-%m-%d %H:%M ET")
    p.append(f'<div class="footer">Generated {_h(gen_time)} &nbsp;&middot;&nbsp; '
             f'Thundermail · MZLA Technologies'
             f'{"&nbsp;&middot;&nbsp; PII redacted" if public else ""}'
             f'</div>\n')
    p.append('</body>\n</html>\n')

    return "".join(p)


# --- Notion posting ----------------------------------------------------------

def post_to_notion(title, markdown):
    """POST the report as a new child page under the parent configured in
    ~/.config/notion/credentials. File format:
        token=secret_xxx
        parent_page_id=<32-char-id>
    """
    if not NOTION_CREDS_PATH.exists():
        print(f"SKIP Notion: missing {NOTION_CREDS_PATH}", file=sys.stderr)
        return None
    cfg = {}
    for line in NOTION_CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip()
    if "token" not in cfg or "parent_page_id" not in cfg:
        print(f"SKIP Notion: {NOTION_CREDS_PATH} needs token= and parent_page_id=", file=sys.stderr)
        return None

    # Convert markdown to a list of Notion blocks. Keep it simple: each line of
    # the markdown becomes a paragraph or heading block; preserve headings,
    # bullets, and quotes. For full fidelity, Notion's API limits 100 blocks
    # per request, so chunk if needed.
    blocks = md_to_notion_blocks(markdown)

    payload = {
        "parent": {"page_id": cfg["parent_page_id"]},
        "properties": {"title": [{"text": {"content": title}}]},
        "children": blocks[:100],
    }
    req = urllib.request.Request(
        "https://api.notion.com/v1/pages",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {cfg['token']}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as r:
            page = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        print(f"Notion POST failed: HTTP {e.code}\n{e.read().decode()}", file=sys.stderr)
        return None

    page_id = page["id"].replace("-", "")
    # Append any overflow blocks
    if len(blocks) > 100:
        for i in range(100, len(blocks), 100):
            chunk = blocks[i:i + 100]
            req2 = urllib.request.Request(
                f"https://api.notion.com/v1/blocks/{page_id}/children",
                data=json.dumps({"children": chunk}).encode(),
                headers={
                    "Authorization": f"Bearer {cfg['token']}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json",
                },
                method="PATCH",
            )
            urllib.request.urlopen(req2).read()

    return page.get("url")


def _rt(text):
    """Build Notion rich_text from a plain string, max 2000 chars per object."""
    if not text:
        return []
    return [{"type": "text", "text": {"content": text[:2000]}}]


def md_to_notion_blocks(md):
    blocks = []
    in_table = False
    for line in md.split("\n"):
        s = line.rstrip()
        if s.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": _rt(s[2:])}})
        elif s.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rt(s[3:])}})
        elif s.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rt(s[4:])}})
        elif s.startswith("> "):
            blocks.append({"object": "block", "type": "quote", "quote": {"rich_text": _rt(s[2:])}})
        elif s.startswith("- ") or s.startswith("* "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rt(s[2:])}})
        elif s.startswith("|") and "---" not in s:
            # Render table rows as plain paragraphs (Notion table API is heavyweight)
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(s)}})
        elif s.strip() == "":
            continue
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rt(s)}})
    return blocks


# --- Main --------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--date", default=None, help="Report date in ET (YYYY-MM-DD); default = today")
    p.add_argument("--public", action="store_true", help="Redact PII for shared/committed reports")
    p.add_argument("--out-dir", default=None, help=f"Output directory (default: {DEFAULT_OUT_DIR})")
    p.add_argument("--post-to-notion", action="store_true")
    args = p.parse_args()

    # Defense in depth: this script is for TB Pro only. Never donors.
    assert BRAND == "Thunderbird Pro", "This script is hard-coded to the Thunderbird Pro brand only."

    today_et = dt.datetime.now(ET).date()
    report_date = dt.date.fromisoformat(args.date) if args.date else today_et

    print(f"Building Thundermail live report for {report_date} (ET){' [PUBLIC/redacted]' if args.public else ''}…", file=sys.stderr)
    d = build(report_date)
    md   = render_md(d,   public=args.public)
    html = render_html(d, public=args.public)

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else DEFAULT_OUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{report_date.isoformat()}.md"
    out_path.write_text(md)
    print(f"Wrote {out_path}", file=sys.stderr)

    html_path = out_dir / f"{report_date.isoformat()}.html"
    html_path.write_text(html)
    print(f"Wrote {html_path}", file=sys.stderr)

    # Always overwrite latest.* for hourly refresh
    (out_dir / "latest.md").write_text(md)
    (out_dir / "latest.html").write_text(html)
    print(f"Wrote {out_dir}/latest.{{md,html}}", file=sys.stderr)

    # Keep reports/tbpro/LATEST.html in sync (legacy URL shared with team)
    legacy_dir = Path(__file__).parent.parent / "reports" / "tbpro"
    legacy_dir.mkdir(parents=True, exist_ok=True)
    (legacy_dir / "LATEST.html").write_text(html)
    (legacy_dir / "LATEST.md").write_text(md)

    if args.post_to_notion:
        title = f"Thundermail · Flight 3 · {report_date.isoformat()}"
        url = post_to_notion(title, md)
        if url:
            print(f"Posted to Notion: {url}", file=sys.stderr)


if __name__ == "__main__":
    main()
