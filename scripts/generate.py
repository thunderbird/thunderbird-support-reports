"""
Monthly report generator — month-agnostic.
Usage: uv run scripts/generate.py <month> <year>
Example: uv run scripts/generate.py april 2026

Reads data/<month>_<year>.yaml for manual inputs.
Analyzes Play Store CSVs automatically.
Generates: lisa/<year>/<month>.md, .html, .csv, _analysis.json
"""
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///

import sys, json, csv, re, os, math, ssl, html, urllib.request, urllib.error, urllib.parse
from pathlib import Path
from collections import Counter, defaultdict


def _esc(s):
    """HTML-escape a value before embedding it in the dashboard. Used for any
    externally-sourced text (forum usernames, Mozilla Connect idea titles, etc.)
    to prevent stored XSS on the published GitHub Pages dashboard."""
    return html.escape(str(s), quote=True)

try:
    import yaml
except ImportError:
    sys.exit("PyYAML not found. Run: uv add pyyaml")

MONTH_NUMS = {
    'january':'01','february':'02','march':'03','april':'04',
    'may':'05','june':'06','july':'07','august':'08',
    'september':'09','october':'10','november':'11','december':'12',
}

THEMES = {
    'Push / Notification Sync':    r'notif|push|sync|synchroni|fetch|delayed|15.min',
    'Crashes & Freezes':           r'crash|absturz|crasha|force.close|freeze|app.*stop|angehalten',
    'Stuck Outbox / Send Failure': r'outbox|stuck.*send|send.*fail|sending.*error|cannot.*send',
    'Spam Filter Absent':          r'spam|junk|no.*filter|missing.*filter',
    'Calendar Missing':            r'calend|kalend|agenda|ical|caldav',
    'QR / Settings Import':        r'qr.cod|import.*sett|setting.*import',
    'Email Headers / Print':       r'header|kopf|mail.*head|drucken|print.*mail',
}

WIN_THEMES = {
    'UI / Design Praise':      r'beauti|clean|design|ui|interface|look.*great|nice.*look|modern',
    'Speed / Performance':     r'fast|quick|speed|snappy|light|perform|responsive',
    'Privacy / Open Source':   r'privacy|open.source|foss|no.*track|respect.*privacy',
    'Setup / Ease of Use':     r'easy.*setup|easy to use|simple.*setup|quick.*setup|intuitive',
    'Reliability / Stability': r'reliable|stable|solid|works.*great|never.*crash|dependable',
}

K9_DISCOURSE_THEMES = {
    'Crashes & Freezes':  r'crash|restart|freeze|hang|stop',
    'Sync / Fetch':       r'sync|fetch|imap|receive|deliver',
    'Notifications':      r'notif|push|alert|badge',
    'Attachments':        r'attach|file|download|upload',
    'Setup / Accounts':   r'setup|account|password|cert|login|configur',
    'Update regression':  r'v17|v18|v\d\d|after.*update|new.*version|since.*update',
}

LANG_NAMES = {
    'en':'English','de':'German','it':'Italian','es':'Spanish','fr':'French',
    'ru':'Russian','ja':'Japanese','pl':'Polish','pt':'Portuguese','nl':'Dutch',
    'el':'Greek','zh-Hans':'Chinese (Simplified)','tr':'Turkish','ar':'Arabic','id':'Indonesian',
}

DEVICE_MAP = {
    'e3q':'Samsung Galaxy S24 Ultra','pa3q':'Samsung Galaxy S25 Ultra',
    'e1s':'Samsung Galaxy S24','e1q':'Samsung Galaxy S24+',
    'a12s':'Samsung Galaxy A12s','a16x':'Samsung Galaxy A16 5G',
    'OP611FL1':'OnePlus 11','shiba':'Google Pixel 8','cuscoi':'Google Pixel 9',
    'sweet':'Xiaomi Redmi Note 10 Pro','cancunf':'Motorola Moto G52',
    'm1s':'Samsung Galaxy S22 Ultra','a55x':'Samsung Galaxy A55','scout':'Fairphone 5',
    'panther':'Google Pixel 7','cheetah':'Google Pixel 7 Pro',
    'bluejay':'Google Pixel 6a','oriole':'Google Pixel 6',
}

def _decode_device(codename):
    return DEVICE_MAP.get(codename, codename) if codename else None

from pii_redact import paraphrase_review


def _best_quote(rows, pattern, max_len=160):
    """Pick the most on-topic negative review — scored by keyword density, 1-2★ preferred."""
    pool = [r for r in rows if r['_rating'] <= 2 and len(r['_raw_text']) > 40] \
        or [r for r in rows if r['_rating'] <= 3 and len(r['_raw_text']) > 40]
    if not pool:
        return None
    def score(r):
        hits = len(re.findall(pattern, r['_text']))
        return hits / math.sqrt(max(len(r['_text'].split()), 1))
    pool.sort(key=score, reverse=True)
    return paraphrase_review(pool[0]['_raw_text'], max_len=max_len)

def deep_analyze_themes(all_rows, themes):
    """Qualitative detail per friction theme: best quote, top devices, top languages."""
    result = {}
    for theme, pattern in themes.items():
        matches = [r for r in all_rows if re.search(pattern, r['_text'])]
        neg = [r for r in matches if r['_rating'] <= 3]
        pool = neg or matches

        quote = _best_quote(pool, pattern)

        devices = Counter(
            _decode_device(r['_device']) for r in pool if r.get('_device')
        ).most_common(3)
        device_str = ', '.join(f'{d} ({c})' for d, c in devices if d) or None

        langs = Counter(
            r['_lang'] for r in pool if r['_lang'] and r['_lang'] != 'unknown'
        ).most_common(3)
        lang_str = ', '.join(LANG_NAMES.get(l, l) for l, _ in langs) or None

        result[theme] = {'quote': quote, 'devices': device_str, 'languages': lang_str}
    return result

# ── Mozilla Connect Android ideas ────────────────────────────────────────────

def fetch_connect_android_ideas():
    """Scrape top Thunderbird Android ideas from Mozilla Connect (sorted by kudos)."""
    import re as _re
    url = ('https://connect.mozilla.org/t5/ideas/idb-p/ideas/'
           'label-name/thunderbird%20android/tab/most-kudoed')
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            html = r.read().decode('utf-8', errors='replace')
    except Exception as e:
        print(f'  Mozilla Connect Android fetch failed: {e}')
        return []
    blocks = _re.findall(
        r'data-lia-message-uid=\"\d+\".*?'
        r'href=\"(/t5/ideas/[^\"]+/idi-p/\d+)\"[^>]*>\s*([^\n<]+?)\s*\n.*?'
        r'itemprop=\"upvoteCount\"[^>]*>\s*(\d+)\s*<',
        html, _re.DOTALL
    )
    ideas = []
    for path, title, kudos in blocks:
        title = title.strip()
        for ent, rep in [('&quot;','"'),('&amp;','&'),('&lt;','<'),('&gt;','>'),('&#39;',"'")]:
            title = title.replace(ent, rep)
        ideas.append({'url': f'https://connect.mozilla.org{path}', 'title': title, 'kudos': int(kudos)})
    ideas.sort(key=lambda x: -x['kudos'])
    return ideas[:15]


# ── SUMO top contributors ─────────────────────────────────────────────────────

def fetch_sumo_contributors(year, month_num, product='desktop', top_n=5):
    """Fetch top answer contributors from Roland's concatenated SUMO answers CSV."""
    import base64 as _b64, io as _io, subprocess as _sp, urllib.request as _ur
    fname = f'{year}-{month_num}-sumo-{product}-answers.csv'
    path = f'repos/thunderbird/thunderbird-metrics-and-reports/contents/CONCATENATED_FILES/{product.upper()}/{fname}'
    try:
        result = _sp.run(['gh', 'api', path], capture_output=True, text=True, check=True)
        payload = json.loads(result.stdout)
        if payload.get('content'):
            data = _b64.b64decode(payload['content']).decode('utf-8', errors='replace')
        else:
            # File too large for contents API — fall back to raw download URL
            raw_url = payload['download_url']
            with _ur.urlopen(raw_url) as resp:
                data = resp.read().decode('utf-8', errors='replace')
        rows = list(csv.DictReader(_io.StringIO(data)))
    except Exception as e:
        print(f'  SUMO {product} contributors fetch failed: {e}')
        return []
    valid = [r for r in rows if r.get('is_spam', 'True') == 'False' and r.get('creator')]
    counts = Counter(r['creator'] for r in valid)
    # Only include contributors with 3+ answers
    return [(u, c) for u, c in counts.most_common(top_n * 3) if c >= 3][:top_n]


# ── K-9 Discourse ────────────────────────────────────────────────────────────

def fetch_k9_discourse(month_prefix):
    """Fetch K-9 Discourse Support topics for the given month from the public API."""
    import json as _json
    year, mon = month_prefix.split('-')
    start = f"{year}-{mon}-01"
    m = int(mon)
    end = f"{year}-{m+1:02d}-01" if m < 12 else f"{int(year)+1}-01-01"
    url = (f"https://forum.k9mail.app/search.json"
           f"?q=after%3A{start}+before%3A{end}+order%3Acreated")
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
            data = _json.loads(r.read())
    except Exception as e:
        print(f"  K-9 Discourse fetch failed: {e}")
        return None
    topics = data.get('topics') or []
    total = len(topics)
    if total == 0:
        return None
    solved     = sum(1 for t in topics if t.get('has_accepted_answer'))
    unanswered = sum(1 for t in topics if t.get('reply_count', 1) == 0)
    themes = {}
    for name, pat in K9_DISCOURSE_THEMES.items():
        hits = [t for t in topics if re.search(pat, t.get('title', '').lower())]
        if hits:
            themes[name] = len(hits)
    top_themes = sorted(themes.items(), key=lambda x: -x[1])
    # Top contributors: only count reply posts (post_number > 1); skip bots and question askers
    SYSTEM_USERS = {'system', 'discobot'}
    contrib_counts = Counter(
        p.get('username') for p in data.get('posts', [])
        if p.get('username') and p.get('username') not in SYSTEM_USERS
        and p.get('post_number', 1) > 1
    )
    top_contributors = contrib_counts.most_common(5)
    return {
        'total_topics': total,
        'solved': solved,
        'solved_pct': round(solved / total * 100),
        'unanswered': unanswered,
        'unanswered_pct': round(unanswered / total * 100),
        'top_themes': top_themes,
        'top_contributors': top_contributors,
    }


# ── History ───────────────────────────────────────────────────────────────────

def load_history(base):
    path = base / 'data' / 'history.json'
    if not path.exists():
        return {}
    return json.loads(path.read_text())

def _month_keys(history):
    return sorted(k for k in history if re.match(r'^\d{4}-\d{2}$', k))

def prev_from_history(history, month_prefix):
    """Return the most recent month's data before month_prefix."""
    keys = [k for k in _month_keys(history) if k < month_prefix]
    if not keys:
        return {}
    return history[keys[-1]]

def history_neg_from_history(history, month_prefix, themes):
    """Return the 2 most recent prior months' negative counts; caller appends current month."""
    keys = [k for k in _month_keys(history) if k < month_prefix][-2:]
    result = {}
    for theme in themes:
        result[theme] = [history[k]['friction_neg'].get(theme, 0) for k in keys]
    return result

def idea_votes_snapshot(config):
    """Return {title: votes} for all ideas in the YAML."""
    ideas = config.get('tbpro_ideas', {})
    snapshot = {}
    for key in ('new_this_month', 'top_alltime', 'in_flight', 'landed'):
        for idea in ideas.get(key, []):
            snapshot[idea['title']] = idea['votes']
    return snapshot

def idea_mom_delta(title, votes, prev_snapshot):
    """Return MoM vote delta string, or '' if no prior data."""
    if not prev_snapshot or title not in prev_snapshot:
        return ''
    delta = votes - prev_snapshot[title]
    if delta > 0:
        return f' (+{delta} this month)'
    if delta < 0:
        return f' ({delta} this month)'
    return ''

def idea_status_class(status):
    """Map FeatureOS custom_status.title to a CSS modifier class."""
    if not status:
        return 'idea-status'
    s = status.strip()
    if s == 'In flight':
        return 'idea-status idea-status--flight'
    if s == 'On the roadmap':
        return 'idea-status idea-status--roadmap'
    if s in {'Landed!', 'Landed'}:
        return 'idea-status idea-status--landed'
    if s in {'No for now', 'By design', 'Off-topic'}:
        return 'idea-status idea-status--declined'
    if s == 'Exploring the Idea':
        return 'idea-status idea-status--exploring'
    if s == 'Great idea; not yet':
        return 'idea-status idea-status--review'
    return 'idea-status idea-status--review'

def idea_status_html(status):
    """Return HTML span for FeatureOS status, or em dash if missing."""
    if not status:
        return '<span class="tbl-muted">—</span>'
    cls = idea_status_class(status)
    return f'<span class="{cls}">{_esc(status)}</span>'

def build_status_moves_html(status_moves_block, month_cap):
    """Thundermail status moves — YAML manual, auto snapshot diff, or both."""
    if not status_moves_block or not status_moves_block.get('moves'):
        return ''
    moves = sorted(status_moves_block['moves'], key=lambda m: m.get('date', ''), reverse=True)
    rows = []
    for m in moves:
        status_span = idea_status_html(m.get('status'))
        note = f' · <span class="tbl-muted">{_esc(m["note"])}</span>' if m.get('note') else ''
        rows.append(
            f'<li><span class="tbl-muted" style="font-variant-numeric:tabular-nums">{_esc(m.get("date", ""))}</span>'
            f' · {status_span} · <a href="{_esc(m["url"])}" target="_blank" style="color:var(--text)">'
            f'{_esc(m["title"])}</a> · <strong>{m.get("votes", "")}</strong> votes{note}</li>'
        )
    caveat = status_moves_block.get('caveat', '')
    caveat_html = f'<p class="footnote" style="margin-top:.75rem">{_esc(caveat)}</p>' if caveat else ''
    return f'''
<h3 style="margin-top:1.25rem">Status moves · {month_cap}</h3>
<ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.35rem;font-size:.82rem">
  {"".join(rows)}
</ul>
{caveat_html}
'''

_QUARTERLY_STATUS_ORDER = (
    'On the roadmap',
    'Exploring the Idea',
    'Great idea; not yet',
)

def build_quarterly_review_html(quarterly_review):
    """Jul quarterly review status moves — separate from inferrable monthly moves."""
    if not quarterly_review or not quarterly_review.get('moves'):
        return ''
    date_label = 'Jul 1'
    raw_date = quarterly_review.get('date', '')
    if raw_date and len(raw_date) >= 10:
        _MONTHS = ('Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec')
        try:
            y, m, d = (int(raw_date[:4]), int(raw_date[5:7]), int(raw_date[8:10]))
            date_label = f'{_MONTHS[m - 1]} {d}'
        except (ValueError, IndexError):
            date_label = raw_date

    by_status = {s: [] for s in _QUARTERLY_STATUS_ORDER}
    allowed = set(_QUARTERLY_STATUS_ORDER)
    for move in quarterly_review['moves']:
        status = move.get('status') or ''
        if status not in allowed:
            continue
        by_status[status].append(move)

    groups_html = []
    for status in _QUARTERLY_STATUS_ORDER:
        moves = by_status.get(status) or []
        if not moves:
            continue
        moves.sort(key=lambda m: (-(m.get('votes') or 0), m.get('title', '')))
        status_span = idea_status_html(status)
        items = []
        for m in moves:
            items.append(
                f'<li><a href="{_esc(m["url"])}" target="_blank" style="color:var(--text)">'
                f'{_esc(m["title"])}</a> · <strong>{m.get("votes", "")}</strong> votes</li>'
            )
        groups_html.append(f'''
  <div class="box" style="margin-bottom:.75rem">
    <h4 style="font-size:.82rem;margin:0 0 .5rem">{status_span} <span style="color:var(--muted);font-weight:400">({len(moves)})</span></h4>
    <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.35rem;font-size:.82rem">
      {"".join(items)}
    </ul>
  </div>''')

    footnote = quarterly_review.get('footnote', '')
    footnote_html = ''
    if footnote:
        footnote_html = (
            f'<p class="footnote" style="margin-top:.75rem">{_esc(footnote)} '
            f'See <a href="https://support.tb.pro/hc/en-us/articles/51206861883027-How-We-Handle-Ideas" '
            f'target="_blank">How We Handle Ideas</a>.</p>'
        )
    facilitator = quarterly_review.get('facilitator', 'Lisa (LJ)')
    move_count = sum(len(by_status.get(s) or []) for s in _QUARTERLY_STATUS_ORDER)
    intro = (
        f'First public quarterly ideas review — top {move_count} ideas by score on the launch overview agenda. '
        f'{facilitator} updated statuses from Open for discussion with public comments.'
    )
    return f'''
<h3 style="margin-top:1.25rem">Quarterly review · {date_label or "Jul 1"}</h3>
<p style="font-size:.82rem;color:var(--muted);margin:0 0 .75rem">{_esc(intro)}</p>
{"".join(groups_html)}
{footnote_html}
'''

def build_shipped_ideas_html(ideas):
    """Landed + in-flight FeatureOS ideas for the Thundermail dashboard section."""
    landed = ideas.get('landed', [])
    in_flight = ideas.get('in_flight', [])
    if not landed and not in_flight:
        return ''

    def _idea_li(idea):
        status_span = idea_status_html(idea.get('status'))
        return (
            f'<li>'
            f'<a class="idea-row__title" href="{_esc(idea["url"])}" target="_blank">{_esc(idea["title"])}</a>'
            f'<span class="idea-row__votes"><strong>{idea["votes"]}</strong> votes</span>'
            f'{status_span}'
            f'</li>'
        )

    landed_items = ''.join(_idea_li(i) for i in sorted(landed, key=lambda x: -x['votes']))
    flight_items = ''.join(_idea_li(i) for i in sorted(in_flight, key=lambda x: -x['votes']))
    return f'''
<h3 style="margin-top:1.25rem">Shipped &amp; in flight</h3>
<div class="two-col">
  <div class="box">
    <h3 style="font-size:.85rem;margin-bottom:.5rem">Landed ({len(landed)})</h3>
    <ul class="idea-row-list">
      {landed_items or '<li class="idea-row-list__empty">None</li>'}
    </ul>
  </div>
  <div class="box">
    <h3 style="font-size:.85rem;margin-bottom:.5rem">In flight ({len(in_flight)})</h3>
    <ul class="idea-row-list">
      {flight_items or '<li class="idea-row-list__empty">None</li>'}
    </ul>
  </div>
</div>
'''

def append_to_history(base, month_prefix, month_cap, year, analysis, config):
    path = base / 'data' / 'history.json'
    history = json.loads(path.read_text()) if path.exists() else {}
    z = config.get('zendesk', {})
    sumo = config.get('sumo', {})
    history[month_prefix] = {
        'month': month_cap,
        'year': int(year),
        'play_store': {
            'tb_count': analysis['tb_count'],
            'k9_count': analysis['k9_count'],
            'total_count': analysis['total_count'],
            'tb_avg_rating': analysis['tb_avg_rating'],
            'k9_avg_rating': analysis['k9_avg_rating'],
            'replies_to_low_star': analysis['replies_to_low_star'],
            'unique_languages': analysis['unique_languages'],
        },
        'friction_neg': {t: s['negative'] for t, s in analysis['friction'].items()},
        'zendesk': {
            'overall_csat':  z.get('overall_csat'),
            'donor_csat':    z.get('donor_csat'),
            'tbpro_csat':    z.get('tbpro_csat'),
            'total_tickets': z.get('total_tickets'),
            'donor_tickets': z.get('donor_tickets'),
            'tbpro_tickets': z.get('tbpro_tickets'),
        },
        'sumo': {
            'desktop_solved_rate':  sumo.get('desktop', {}).get('overall_solved_rate'),
            'desktop_ignored_pct':  sumo.get('desktop', {}).get('ignored_pct'),
            'desktop_tc_pct':       sumo.get('desktop', {}).get('trusted_contributor_pct'),
            'desktop_questions':    sumo.get('desktop', {}).get('total_questions'),
            'android_solved_rate':  sumo.get('android', {}).get('overall_solved_rate'),
            'android_ignored_pct':  sumo.get('android', {}).get('ignored_pct'),
            'android_tc_pct':       sumo.get('android', {}).get('trusted_contributor_pct'),
            'android_questions':    sumo.get('android', {}).get('total_questions'),
        },
        'tbpro_ideas': idea_votes_snapshot(config),
        'k9_discourse': None,  # filled in after fetch, patched by main()
    }
    _write_history_json(path, history)
    return history

def _write_history_json(path, history):
    month_keys = _month_keys(history)
    other_keys = sorted(k for k in history if k not in month_keys)
    ordered = {k: history[k] for k in month_keys + other_keys}
    path.write_text(json.dumps(ordered, indent=2) + '\n')

FRICTION_ANCHORS = {
    'Push / Notification Sync':    '#top-3-friction-points',
    'Spam Filter Absent':          '#top-3-friction-points',
    'Crashes & Freezes':           '#top-3-friction-points',
    'Calendar Missing':            '#android-reviews',
    'Stuck Outbox / Send Failure': '#android-reviews',
    'QR / Settings Import':        '#android-reviews',
    'Email Headers / Print':       '#android-reviews',
}


# ── CSV Analysis ──────────────────────────────────────────────────────────────

def load_csv(path, app_label, month_prefix):
    # Play Console monthly exports are scoped by last activity date (update or reply),
    # not by original submit date — use all rows, no date filtering needed.
    rows = []
    with open(path, encoding='utf-16') as f:
        for row in csv.DictReader(f):
            row['_app'] = app_label
            row['_rating'] = int(row.get('Star Rating', 0))
            row['_text'] = (row.get('Review Text', '') or '').lower()
            row['_raw_text'] = (row.get('Review Text', '') or '')
            row['_has_reply'] = bool(row.get('Developer Reply Text', '').strip())
            row['_lang'] = row.get('Reviewer Language', '') or 'unknown'
            row['_device'] = (row.get('Device', '') or '').split(':')[0].strip()
            rows.append(row)
    return rows


def match_themes(rows, themes):
    results = {}
    for theme, pattern in themes.items():
        matches = [r for r in rows if re.search(pattern, r['_text'])]
        neg = [r for r in matches if r['_rating'] <= 3]
        tb  = [r for r in matches if r['_app'] == 'TB']
        k9  = [r for r in matches if r['_app'] == 'K9']
        avg = sum(r['_rating'] for r in matches) / len(matches) if matches else 0
        results[theme] = {
            'total': len(matches), 'negative': len(neg),
            'avg_rating': round(avg, 2), 'tb_count': len(tb), 'k9_count': len(k9),
        }
    return results


def rating_distribution(rows):
    dist = defaultdict(int)
    for r in rows:
        dist[r['_rating']] += 1
    return {str(k): v for k, v in sorted(dist.items())}


def top_languages(rows, n=10):
    langs = Counter(r['_lang'] for r in rows if r['_lang'] and r['_lang'] != 'unknown')
    return langs.most_common(n)


def analyze_replies(rows):
    low = [r for r in rows if r['_rating'] <= 3]
    replied = [r for r in low if r['_has_reply']]
    return len(replied), len(low)


def compare_rating_changes(current_rows, prev_csv_paths):
    """Cross-reference current rows against previous month CSVs by Review Link.
    Only reviews present in both exports are counted — these are reviews with
    activity (reply or edit) in the current month. Returns None if no prev CSVs found.
    """
    prev_ratings = {}
    for path in prev_csv_paths:
        if not path or not path.exists():
            continue
        try:
            with open(path, encoding='utf-16') as f:
                for row in csv.DictReader(f):
                    link = row.get('Review Link', '').strip()
                    if link:
                        prev_ratings[link] = int(row.get('Star Rating', 0))
        except Exception:
            pass
    if not prev_ratings:
        return None
    improved = unchanged = decreased = 0
    for row in current_rows:
        link = row.get('Review Link', '').strip()
        if link in prev_ratings:
            delta = row['_rating'] - prev_ratings[link]
            if delta > 0:   improved  += 1
            elif delta < 0: decreased += 1
            else:           unchanged += 1
    matched = improved + unchanged + decreased
    return {'improved': improved, 'unchanged': unchanged, 'decreased': decreased, 'matched': matched}


def analyze_csvs(base, config, month_prefix):
    csv_tb  = base / config['csv_tb_stable']
    csv_k9  = base / config['csv_k9']

    if not csv_tb.exists():
        csv_tb = base / 'data' / 'input' / config['csv_tb_stable']
    if not csv_k9.exists():
        csv_k9 = base / 'data' / 'input' / config['csv_k9']

    if not csv_tb.exists():
        sys.exit(f"TB CSV not found: {config['csv_tb_stable']}")
    if not csv_k9.exists():
        sys.exit(f"K-9 CSV not found: {config['csv_k9']}")

    tb  = load_csv(csv_tb,  'TB',  month_prefix)
    k9  = load_csv(csv_k9,  'K9',  month_prefix)

    # Optional Beta CSV — merged into TB counts
    beta_count = 0
    if config.get('csv_tb_beta'):
        csv_beta = base / config['csv_tb_beta']
        if not csv_beta.exists():
            csv_beta = base / 'data' / 'input' / config['csv_tb_beta']
        if csv_beta.exists():
            beta = load_csv(csv_beta, 'TB', month_prefix)
            tb = tb + beta
            beta_count = len(beta)
            print(f"  TB Beta: {beta_count} reviews")
        else:
            print(f"  TB Beta CSV not found: {config['csv_tb_beta']} (skipping)")

    all_rows = tb + k9

    tb_avg  = sum(r['_rating'] for r in tb)  / len(tb)  if tb  else 0
    k9_avg  = sum(r['_rating'] for r in k9)  / len(k9)  if k9  else 0
    all_avg = sum(r['_rating'] for r in all_rows) / len(all_rows) if all_rows else 0

    replied, low_total = analyze_replies(all_rows)
    unique_langs = len(set(r['_lang'] for r in all_rows))

    pos_rows = [r for r in all_rows if r['_rating'] >= 4]
    friction = match_themes(all_rows, THEMES)
    friction_detail = deep_analyze_themes(all_rows, THEMES)
    wins     = match_themes(pos_rows, WIN_THEMES)
    top_langs = top_languages(all_rows)

    # Cross-month rating change comparison
    m = int(config['month_num'])
    y = int(config['year'])
    prev_yyyymm = f"{y}{m-1:02d}" if m > 1 else f"{y-1}12"
    def _find_csv(glob_pattern):
        import glob as _glob
        hits = _glob.glob(str(base / 'data' / 'input' / glob_pattern)) + \
               _glob.glob(str(base / glob_pattern))
        return Path(hits[0]) if hits else None
    prev_tb_path = _find_csv(f"reviews_reviews_net.thunderbird.android_{prev_yyyymm}*.csv")
    prev_k9_path = _find_csv(f"reviews_reviews_com.fsck.k9_{prev_yyyymm}*.csv")
    rating_changes = compare_rating_changes(all_rows, [prev_tb_path, prev_k9_path])
    if rating_changes:
        print(f"  Rating changes vs {prev_yyyymm}: +{rating_changes['improved']} ↑  {rating_changes['unchanged']} → {rating_changes['decreased']} ↓  ({rating_changes['matched']} matched)")

    return {
        'tb_count': len(tb), 'k9_count': len(k9), 'total_count': len(all_rows),
        'beta_count': beta_count,
        'tb_avg_rating': round(tb_avg, 2), 'k9_avg_rating': round(k9_avg, 2),
        'overall_avg_rating': round(all_avg, 2),
        'replies_to_low_star': replied, 'total_low_star': low_total,
        'unique_languages': unique_langs,
        'rating_dist_tb': rating_distribution(tb),
        'rating_dist_k9': rating_distribution(k9),
        'top_languages': top_langs,
        'friction': friction, 'friction_detail': friction_detail, 'wins': wins,
        'rating_changes': rating_changes,
    }


# ── Report Markdown ───────────────────────────────────────────────────────────

def mom_arrow(val, prev):
    if val is None or prev is None:
        return ''
    return '↑' if val > prev else ('↓' if val < prev else '→')

def mom_cls(val, prev):
    """CSS class for MoM delta — up/down/flat/muted."""
    if val is None or prev is None:
        return 'muted'
    return 'up' if val > prev else ('down' if val < prev else 'flat')

def mom_pts(val, prev):
    if val is None or prev is None:
        return 'N/A'
    diff = round(val - prev, 1)
    return f'+{diff}' if diff >= 0 else str(diff)

def mom_pct(val, prev):
    if val is None or prev is None:
        return 'N/A'
    diff = round((val - prev) / prev * 100, 1) if prev else 0
    return f'+{diff}%' if diff >= 0 else f'{diff}%'


def _extract_section(text, heading):
    """Extract content between `heading` and the next same-level heading or end."""
    pattern = re.escape(heading)
    m = re.search(pattern + r'\n(.*?)(?=\n#{1,3} |\Z)', text, re.DOTALL)
    return m.group(1).strip() if m else ''

PLACEHOLDER_PATTERNS = [
    r'^\[.*\]$',           # [fill in ...]
    r'^\[Priority \d\]',   # [Priority N]: ...
    r'^-\s*$',             # bare dash
]

def _is_placeholder(content):
    for line in content.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if not any(re.match(p, line) for p in PLACEHOLDER_PATTERNS):
            return False
    return True

PRESERVED_SECTIONS = [
    '### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do',
    "## What's Coming Up",
]

def _preserve_narrative(existing_md, new_md):
    """Splice manually-edited sections from existing_md into new_md."""
    for heading in PRESERVED_SECTIONS:
        existing_content = _extract_section(existing_md, heading)
        if existing_content and not _is_placeholder(existing_content):
            new_content = _extract_section(new_md, heading)
            if new_content is not None:
                new_md = new_md.replace(
                    heading + '\n' + new_content,
                    heading + '\n' + existing_content,
                    1
                )
    return new_md


def _impact_str(rc):
    if not rc:
        return '[X improved ratings, X unchanged, X decreased.]'
    return (f"{rc['improved']} improved · {rc['unchanged']} unchanged · {rc['decreased']} decreased "
            f"*(of {rc['matched']} reviews active in both months — see footnote)*.")


def build_report(config, analysis, month_cap, year, prev_idea_snapshot=None):
    z = config['zendesk']
    p = config['prev']
    tbpro_note_md = f"\n*{z['tbpro_csat_note']}*\n" if z.get('tbpro_csat_note') else ''
    donor_note_md = f"\n*{z['donor_csat_note']}*\n" if z.get('donor_csat_note') else ''
    sumo = config.get('sumo', {})
    ideas = config.get('tbpro_ideas', {})
    narrative = config.get('narrative', {})

    # Friction top 3
    friction_order = [
        'Push / Notification Sync', 'Spam Filter Absent', 'Crashes & Freezes',
        'Calendar Missing', 'Stuck Outbox / Send Failure',
        'QR / Settings Import', 'Email Headers / Print',
    ]
    history = config.get('history_neg', {})
    sorted_friction = sorted(
        [(t, analysis['friction'][t]) for t in friction_order if t in analysis['friction']],
        key=lambda x: -x[1]['negative']
    )
    top3 = sorted_friction[:3]

    def trend_label(hist):
        if len(hist) < 2:
            return ''
        if hist[-1] > hist[-2]:
            return '🔴 Accelerating'
        if hist[-1] == 0 and hist[-2] == 0:
            return '🆕 New signal' if (len(hist) > 2 and hist[-3] == 0) else ''
        return '📉 Improving' if hist[-1] < hist[-2] else '➡️ Stable'

    friction_detail = analysis.get('friction_detail', {})
    friction_md = ''
    for i, (theme, s) in enumerate(top3, 1):
        hist = list(history.get(theme, []))
        hist.append(s['negative'])
        trend_str = ' → '.join(str(x) for x in hist)
        label = trend_label(hist)
        detail = friction_detail.get(theme, {})
        quote_line = detail['quote'] if detail.get('quote') else '[No review text available]'
        flags_parts = []
        if detail.get('devices'):
            flags_parts.append(f'Devices: {detail["devices"]}')
        if detail.get('languages'):
            flags_parts.append(f'Languages: {detail["languages"]}')
        flags_line = ' · '.join(flags_parts) if flags_parts else '[No device/language data]'
        friction_md += f"""
**{i}. {theme}**
- {s['total']} mentions · {s['negative']} negative · avg rating {s['avg_rating']:.2f}★ · **TB:** {s['tb_count']} reviews, **K-9:** {s['k9_count']} reviews
- {quote_line}
- {flags_line}
- 3-month trend: {trend_str} negative mentions {label}
"""

    # TB Pro ideas
    new_ideas_md = ''
    for idea in ideas.get('new_this_month', []):
        delta = idea_mom_delta(idea['title'], idea['votes'], prev_idea_snapshot)
        new_ideas_md += f"- [{idea['title']}]({idea['url']}) — {idea['votes']} votes{delta} ({idea['tag']})\n"
    if not new_ideas_md:
        new_ideas_md = '- [Ideas not yet loaded — run FeatureOS pull]\n'

    top_ideas_md = ''
    for idea in ideas.get('top_alltime', []):
        delta = idea_mom_delta(idea['title'], idea['votes'], prev_idea_snapshot)
        status_note = f" · {idea['status']}" if idea.get('status') else ''
        top_ideas_md += f"- [{idea['title']}]({idea['url']}) — {idea['votes']} votes{delta} ({idea.get('tag','')}{status_note})\n"
    if not top_ideas_md:
        top_ideas_md = '- [Top ideas not yet loaded]\n'

    n_new_ideas = len(ideas.get('new_this_month', []))

    # SUMO
    d_sumo = sumo.get('desktop', {})
    a_sumo = sumo.get('android', {})
    d_solved = d_sumo.get('overall_solved_rate')
    a_solved = a_sumo.get('overall_solved_rate')
    d_mom = mom_pts(d_solved, p.get('desktop_solved_rate'))
    a_mom = mom_pts(a_solved, p.get('android_solved_rate'))
    d_total = d_sumo.get('total_questions', 'N/A')
    d_spam  = d_sumo.get('spam', 0)
    d_real  = (d_total - d_spam) if isinstance(d_total, int) else 'N/A'

    # Ratings MoM
    tb_rating_change = round(analysis['tb_avg_rating'] - p['tb_avg_rating'], 2) if p.get('tb_avg_rating') else 0
    k9_rating_change = round(analysis['k9_avg_rating'] - p['k9_avg_rating'], 2) if p.get('k9_avg_rating') else 0
    tb_arrow = mom_arrow(analysis['tb_avg_rating'], p.get('tb_avg_rating'))
    k9_arrow = mom_arrow(analysis['k9_avg_rating'], p.get('k9_avg_rating'))
    tb_change_str = f"+{tb_rating_change}" if tb_rating_change >= 0 else str(tb_rating_change)
    k9_change_str = f"+{k9_rating_change}" if k9_rating_change >= 0 else str(k9_rating_change)

    lede = narrative.get('lede') or f"[Draft lede for {month_cap} {year} — fill in after analysis is complete.]"
    experiments = narrative.get('whats_coming_up') or narrative.get('experiments') or "[What's coming up — fill in manually.]"

    report_url = f"https://thunderbird.github.io/thunderbird-support-reports/lisa/{year}/{month_cap.lower()}.html"
    gh_base    = f"https://github.com/thunderbird/thunderbird-support-reports"
    csv_url    = f"{gh_base}/blob/main/lisa/{year}/{month_cap.lower()}.csv"

    md = f"""# {month_cap} {year} — Monthly Support Report

> **[→ View dashboard]({report_url})**

{lede}

---
## Support Metrics
- **Overall CSAT:** {z['overall_csat'] or 'N/A'}% ({mom_pts(z['overall_csat'], p['overall_csat'])} pts MoM) {mom_arrow(z['overall_csat'], p['overall_csat'])}
- **CSAT — Donor Support:** {z['donor_csat'] or 'N/A'}% ({mom_pts(z['donor_csat'], p['donor_csat'])} pts MoM) {mom_arrow(z['donor_csat'], p['donor_csat'])}{'*' if z.get('donor_csat_note') else ''}
- **CSAT — Thundermail:** {z['tbpro_csat'] or 'N/A'}%{'*' if z.get('tbpro_csat_note') else ' ✅'}
- **Volume:** {z['total_tickets'] or 'N/A'} tickets ({mom_pct(z['total_tickets'], p['total_tickets'])} MoM) — Donor Support {z['donor_tickets'] or 'N/A'}, Thundermail {z['tbpro_tickets'] or 'N/A'}{(', App Store Reviews ' + str(z['appstore_tickets'])) if z.get('appstore_tickets') else ''}
{donor_note_md}{tbpro_note_md}
---
## Community Support

### Desktop Forum
- **Overall solved rate:** {d_solved or 'N/A'}% ({d_mom} pts MoM) · {d_real if d_sumo.get('spam') else d_total} questions · {narrative.get('sumo_desktop_signal') or '[Key signal from Roland\'s data]'}

### Android Forum
- **Overall solved rate:** {a_solved or 'N/A'}% ({a_mom} pts MoM) · {a_sumo.get('total_questions', '—')} questions · {narrative.get('sumo_android_signal') or '[Key signal]'}

---
## Android Reviews
- **Engagement:** {analysis['replies_to_low_star']} incoming Play Store review tickets ({'up' if analysis['replies_to_low_star'] > (p['replies_to_low_star'] or 0) else 'down'} from {p['replies_to_low_star']} in {config['prev_month']})
- **Impact:** {_impact_str(analysis.get('rating_changes'))} Average monthly rating — TB {analysis['tb_avg_rating']:.2f}★ ({tb_change_str} from {config['prev_month']} {tb_arrow}) · K-9 {analysis['k9_avg_rating']:.2f}★ ({k9_change_str} from {config['prev_month']} {k9_arrow}) · Combined {analysis['overall_avg_rating']:.2f}★ *(simple weighted mean: each review counts once regardless of app)*
- **Volume:** {analysis['total_count']} total reviews — TB {analysis['tb_count']}{ (' (' + str(analysis['tb_count'] - analysis['beta_count']) + ' stable + ' + str(analysis['beta_count']) + ' beta)') if analysis.get('beta_count') else ''}, K-9 {analysis['k9_count']}. {analysis['unique_languages']} languages.

### Top 3 Friction Points
*Sourced from {analysis['total_count']} Play Store reviews (TB{' + Beta' if config.get('csv_tb_beta') else ''} + K-9, same codebase). Analyzed with AI.*
{friction_md}
### Meeting Our ⭐⭐⭐⭐+ Goal: What We Need to Do
{narrative.get('goal_bullets') or "- [Priority 1]: [stat] · [trend] · [why it matters]\n- [Priority 2]: [stat] · [trend] · [why it matters]\n- [Priority 3]: [stat] · [trend] · [why it matters]"}

---
## What's Coming Up

{experiments}

---
## Data Access
Dashboard: [{month_cap.lower()}.html]({report_url})
Raw data (CSV): [{month_cap.lower()}.csv]({csv_url})

---
## Definitions
**Improved / unchanged / decreased** — ratings compared against the previous month's export by Review Link. Only reviews present in both exports are counted; these are reviews with activity (a reply or user edit) in the current month. Reviews with no activity in either month are excluded. Not a complete picture of all rating changes.

**Mentions** — count of Play Store reviews whose text matches a topic's keyword pattern, regardless of star rating. One review = one mention even if multiple keywords match.

**Negative** — mentions where the review is 1–3 stars.

**Avg rating** — mean star rating across all reviews matching that topic (1–5 scale).

**Overall solved rate (SUMO)** — percentage of questions that received any answer, including from the question creator, trusted contributors, and general members.

**Trusted contributor %** — share of answered questions where the last (or only) answer came from a trusted contributor.
"""
    return md


# ── Dashboard HTML ────────────────────────────────────────────────────────────

def build_dashboard(config, analysis, month_cap, year, today, prev_idea_snapshot=None, k9_discourse=None, history=None, connect_android_ideas=None, sumo_contributors=None, status_moves_block=None, quarterly_review=None):
    z = config['zendesk']
    p = config['prev']
    history_neg = config.get('history_neg', {})
    sumo = config.get('sumo', {})

    friction_order = [
        'Push / Notification Sync', 'Spam Filter Absent', 'Crashes & Freezes',
        'Calendar Missing', 'Stuck Outbox / Send Failure',
        'QR / Settings Import', 'Email Headers / Print',
    ]

    # Friction rows
    friction_rows_html = ''
    gh_report = f"https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/{year}/{month_cap.lower()}.md"
    for theme in friction_order:
        if theme not in analysis['friction']:
            continue
        s = analysis['friction'][theme]
        hist = list(history_neg.get(theme, []))
        hist.append(s['negative'])
        trend_str = ' → '.join(str(x) for x in hist)
        arrow = '📈' if (len(hist) > 1 and hist[-1] > hist[-2]) else ('📉' if (len(hist) > 1 and hist[-1] < hist[-2]) else '➡️')
        neg_class = 'high' if s['negative'] >= 10 else ('med' if s['negative'] >= 5 else 'low')
        anchor = FRICTION_ANCHORS.get(theme, '')
        link = f'{gh_report}{anchor}'
        friction_rows_html += f"""
      <tr>
        <td><a href="{link}" target="_blank" style="color:var(--text);text-decoration:none;border-bottom:1px dotted var(--border)"><strong>{theme}</strong></a></td>
        <td class="num">{s['total']}</td>
        <td class="num neg-{neg_class}">{s['negative']}</td>
        <td class="num">{s['avg_rating']:.2f}★</td>
        <td class="num">{s['tb_count']}</td>
        <td class="num">{s['k9_count']}</td>
        <td class="trend">{trend_str} {arrow}</td>
      </tr>"""

    # Language rows
    lang_rows_html = ''
    total_reviews = analysis['total_count']
    for code, count in analysis['top_languages']:
        pct = count / total_reviews * 100
        name = LANG_NAMES.get(code, code)
        lang_rows_html += f'<tr><td>{name}</td><td class="num">{count}</td><td><div class="bar" style="width:{pct*3:.0f}px"></div></td></tr>'

    # Rating charts
    dist_tb  = analysis['rating_dist_tb']
    dist_k9  = analysis['rating_dist_k9']
    tb_labels = [str(k) for k in range(1, 6)]
    tb_vals   = [dist_tb.get(str(k), 0) for k in range(1, 6)]
    k9_vals   = [dist_k9.get(str(k), 0) for k in range(1, 6)]

    # TB Pro ideas
    ideas = config.get('tbpro_ideas', {})
    new_ideas_html = ''
    for idea in ideas.get('new_this_month', []):
        delta = idea_mom_delta(idea['title'], idea['votes'], prev_idea_snapshot or {})
        delta_html = f' <span style="color:var(--green);font-size:.75rem">{delta}</span>' if delta else ''
        new_ideas_html += f'<tr><td><a href="{_esc(idea["url"])}" target="_blank" style="color:var(--text)">{_esc(idea["title"])}</a></td><td class="num">{idea["votes"]}{delta_html}</td><td style="color:var(--muted);font-size:.8rem">{_esc(idea.get("tag",""))}</td></tr>'
    if not new_ideas_html:
        new_ideas_html = '<tr><td colspan="3" style="color:var(--muted)">Not yet loaded</td></tr>'

    top_ideas_html = ''
    for idea in ideas.get('top_alltime', []):
        delta = idea_mom_delta(idea['title'], idea['votes'], prev_idea_snapshot or {})
        delta_html = f' <span style="color:var(--green);font-size:.75rem">{delta}</span>' if delta else ''
        status_html = idea_status_html(idea.get('status'))
        top_ideas_html += f'<tr><td><a href="{_esc(idea["url"])}" target="_blank" style="color:var(--text)">{_esc(idea["title"])}</a></td><td class="num">{idea["votes"]}{delta_html}</td><td>{status_html}</td><td style="color:var(--muted);font-size:.8rem">{_esc(idea.get("tag",""))}</td></tr>'
    if not top_ideas_html:
        top_ideas_html = '<tr><td colspan="4" style="color:var(--muted)">Not yet loaded</td></tr>'

    shipped_ideas_html = build_shipped_ideas_html(ideas)
    status_moves_html = build_status_moves_html(status_moves_block, month_cap)
    quarterly_review_html = build_quarterly_review_html(quarterly_review)

    n_new_ideas = len(ideas.get('new_this_month', []))

    # SUMO
    d_sumo = sumo.get('desktop', {})
    a_sumo = sumo.get('android', {})

    def val(v):
        return v if v is not None else '—'

    d_total = val(d_sumo.get('total_questions'))
    d_spam  = val(d_sumo.get('spam'))
    d_real  = (d_sumo['total_questions'] - d_sumo.get('spam', 0)) if d_sumo.get('total_questions') is not None else '—'
    d_solved = val(d_sumo.get('overall_solved_rate'))
    d_ignored = val(d_sumo.get('ignored_pct'))
    d_tc_pct = val(d_sumo.get('trusted_contributor_pct'))
    d_tc_n   = val(d_sumo.get('trusted_contributors'))

    a_total = val(a_sumo.get('total_questions'))
    a_spam  = val(a_sumo.get('spam'))
    a_real  = (a_sumo['total_questions'] - a_sumo.get('spam', 0)) if a_sumo.get('total_questions') is not None else '—'
    a_solved = val(a_sumo.get('overall_solved_rate'))
    a_ignored = val(a_sumo.get('ignored_pct'))
    a_tc_pct = val(a_sumo.get('trusted_contributor_pct'))
    a_contribs = ', '.join(a_sumo.get('contributors', [])) or '—'

    d_signals_html = ''
    for sig in d_sumo.get('top_signals', []):
        mom_val = sig.get('mom_pct')
        mom = f'+{mom_val}%' if (mom_val is not None and mom_val >= 0) else (f'{mom_val}%' if mom_val is not None else '—')
        d_signals_html += f'<tr><td>{sig["name"]}</td><td class="num">{sig["questions"]}</td><td class="num up">{mom}</td></tr>'

    a_signals_html = ''
    for sig in a_sumo.get('top_signals', []):
        a_signals_html += f'<tr><td>{sig["name"]}</td><td class="num">{sig.get("questions","—")}</td></tr>'

    # Trusted contributor count rows (conditional — only render if a count is set in yaml)
    d_tc_n_raw = d_sumo.get('trusted_contributors')
    a_tc_n_raw = a_sumo.get('trusted_contributors')
    d_tc_row = (
        f'<tr><td>Trusted contributors</td><td class="num">{d_tc_n_raw}</td>'
        f'<td class="num muted">—</td><td class="num muted">—</td></tr>'
    ) if isinstance(d_tc_n_raw, int) else ''
    a_tc_row = (
        f'<tr><td>Trusted contributors</td><td class="num">{a_tc_n_raw}</td>'
        f'<td class="num muted">—</td><td class="num muted">—</td></tr>'
    ) if isinstance(a_tc_n_raw, int) else ''

    # ── Desktop extras: SUMO trending, priorities, Connect ideas ──
    month_lower = month_cap.lower()
    extras_dir = Path(__file__).parent.parent / 'lisa' / str(year)
    gh_blob_base = f'https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/{year}'

    def _read_csv(name):
        path = extras_dir / name
        if not path.exists():
            return None
        with open(path, encoding='utf-8') as f:
            return list(csv.DictReader(f))

    trending_rows = _read_csv(f'{month_lower}_sumo_trending.csv') or []
    priorities_rows = _read_csv(f'{month_lower}_desktop_priorities.csv') or []
    connect_rows = _read_csv(f'{month_lower}_connect_ideas.csv') or []

    # Build 3-month rolling history for trending topics
    NUM_TO_MONTH = {v: k for k, v in MONTH_NUMS.items()}
    def _prior_month_name(mnum, yr):
        m = int(mnum)
        if m == 1:
            return NUM_TO_MONTH['12'], yr - 1
        return NUM_TO_MONTH[f'{m-1:02d}'], yr
    prev1_name, prev1_yr = _prior_month_name(config.get('month_num', '01'), year)
    prev2_name, prev2_yr = _prior_month_name(MONTH_NUMS[prev1_name], prev1_yr)
    trending_prev1 = _read_csv(f'{prev1_name}_sumo_trending.csv') or []
    trending_prev2 = _read_csv(f'{prev2_name}_sumo_trending.csv') or []

    def _trending_pct_map(rows):
        return {r['topic']: float(r['percent_of_total']) for r in rows if r.get('topic')}

    def _trending_count_map(rows):
        return {r['topic']: int(r['count']) for r in rows if r.get('topic')}

    pct_prev2 = _trending_pct_map(trending_prev2)
    pct_prev1 = _trending_pct_map(trending_prev1)
    cnt_prev2 = _trending_count_map(trending_prev2)
    cnt_prev1 = _trending_count_map(trending_prev1)

    if trending_rows:
        top10 = trending_rows[:10]
        has_history = bool(trending_prev1)

        if has_history:
            prev1_cap = prev1_name.capitalize()
            prev2_cap = prev2_name.capitalize() if trending_prev2 else None
            thead = (
                f'<thead><tr>'
                f'<th style="width:36px">#</th><th>Topic</th>'
                + (f'<th class="num muted" style="font-size:.75rem">{prev2_cap}</th>' if prev2_cap else '')
                + f'<th class="num muted" style="font-size:.75rem">{prev1_cap}</th>'
                f'<th class="num">{month_cap}</th>'
                f'<th class="num" style="font-size:.75rem">3-mo avg</th>'
                f'</tr></thead>'
            )
            rows_html = ''
            for r in top10:
                topic = r['topic']
                cur_pct = float(r['percent_of_total'])
                cur_cnt = int(r['count'])
                p1_pct  = pct_prev1.get(topic)
                p2_pct  = pct_prev2.get(topic)
                p1_cnt  = cnt_prev1.get(topic, 0)
                p2_cnt  = cnt_prev2.get(topic, 0)

                # Trend vs prior month
                if p1_pct is not None:
                    delta = cur_pct - p1_pct
                    if delta >= 1.5:   arrow = '<span style="color:var(--critical)">↑</span>'
                    elif delta <= -1.5: arrow = '<span style="color:var(--success)">↓</span>'
                    else:               arrow = '<span style="color:var(--muted)">→</span>'
                else:
                    arrow = ''

                # 3-mo avg
                avail = [x for x in [p2_pct, p1_pct, cur_pct] if x is not None]
                avg = sum(avail) / len(avail)

                p2_cell = (f'<td class="num muted" style="font-size:.8rem">{p2_cnt}<br>'
                           f'<span style="font-size:.7rem">{p2_pct:.1f}%</span></td>'
                           if prev2_cap else '')
                p1_cell = (f'<td class="num muted" style="font-size:.8rem">{p1_cnt}<br>'
                           f'<span style="font-size:.7rem">{p1_pct:.1f}%</span></td>'
                           if p1_pct is not None else
                           f'<td class="num muted" style="font-size:.7rem">—</td>')

                rows_html += (
                    f'<tr>'
                    f'<td class="muted" style="font-size:.8rem">{r["rank"]}</td>'
                    f'<td>{topic} {arrow}</td>'
                    + p2_cell
                    + p1_cell
                    + f'<td class="num"><strong>{cur_cnt}</strong><br>'
                    f'<span style="font-size:.7rem">{cur_pct:.1f}%</span></td>'
                    f'<td class="num muted" style="font-size:.8rem">{avg:.1f}%</td>'
                    f'</tr>'
                )
        else:
            thead = (
                f'<thead><tr><th style="width:50px">#</th><th>Topic</th>'
                f'<th class="num">Count</th><th class="num">% of total</th></tr></thead>'
            )
            rows_html = ''.join(
                f'<tr><td>{r["rank"]}</td><td>{r["topic"]}</td>'
                f'<td class="num">{r["count"]}</td>'
                f'<td class="num muted">{r["percent_of_total"]}%</td></tr>'
                for r in top10
            )

        desktop_trending_html = (
            f'<div class="subsection-header" style="--sc: var(--sky)" id="top-trending-topics">'
            f'<h3><a href="#top-trending-topics">Top Trending Topics<span class="anchor">#</span></a></h3>'
            f'<span class="sh-meta">SUMO tag rollup · top 10 of {len(trending_rows)} · '
            f'<a href="{gh_blob_base}/{month_lower}_sumo_trending.md" style="color:var(--sky)" target="_blank">full report →</a></span>'
            f'</div>'
            f'<div class="box"><table>{thead}<tbody>{rows_html}</tbody></table></div>'
        )
    else:
        desktop_trending_html = ''

    if priorities_rows:
        theme_descriptions = {
            'Authentication / OAuth fragility': (
                'Heavy on Gmail, Outlook, Yahoo, Comcast provider failures. '
                'Recurring patterns: "stopped working after password change," '
                '"broke after Thunderbird update," repeated password prompts, '
                'connection / server reset, and friction with the new Account Setup Hub.'
            ),
            'Update regressions': (
                'Visible across UI, send/receive, drag-and-drop, and folder display. '
                'Updates are breaking established workflows at scale — a release-process '
                'and regression-detection problem more than a feature problem.'
            ),
            'Data loss / folder integrity': (
                'Highest-emotional-charge bucket. Folders/emails disappearing, "wiped out '
                'all my folders," "Local Folders gone," "Recover Emails removed by Expunge." '
                'High urgency, high trust impact — these are the "I lost everything" tickets.'
            ),
        }
        rows_html = ''
        for r in priorities_rows:
            theme = r['theme']
            desc = theme_descriptions.get(theme, '')
            rows_html += (
                f'<tr><td><strong>{r["rank"]}.</strong> {theme}'
                f'<br><span style="font-size:.8rem;color:var(--muted)">{desc}</span></td>'
                f'<td class="num"><strong>{r["count"]}</strong></td>'
                f'<td class="num muted">{r["percent_of_total"]}%</td></tr>'
            )
        desktop_priorities_html = (
            f'<div class="subsection-header" style="--sc: var(--sky)" id="recommended-priorities">'
            f'<h3><a href="#recommended-priorities">Recommended Priorities — Community Signal<span class="anchor">#</span></a></h3>'
            f'<span class="sh-meta">3 themes · '
            f'<a href="{gh_blob_base}/{month_lower}_desktop_priorities.md" style="color:var(--sky)" target="_blank">full drill-down →</a></span>'
            f'</div>'
            f'<div class="box"><table>'
            f'<thead><tr><th>Theme</th><th class="num">Questions</th><th class="num">% of total</th></tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div>'
        )
    else:
        desktop_priorities_html = ''

    if connect_rows:
        top5 = connect_rows[:5]
        rows_html = ''.join(
            f'<tr><td class="num">{r["kudos"]}</td>'
            f'<td class="num muted">{int(r["views"]):,}</td>'
            f'<td>{r["status"]}</td>'
            f'<td><a href="{r["url"]}" target="_blank" style="color:var(--text)">{r["subject"]}</a></td></tr>'
            for r in top5
        )
        total_kudos = sum(int(r['kudos']) for r in connect_rows)
        total_views = sum(int(r['views']) for r in connect_rows)
        desktop_connect_html = (
            f'<div class="subsection-header" style="--sc: var(--sky)" id="mozilla-connect">'
            f'<h3><a href="#mozilla-connect">Mozilla Connect — Community Wishlist<span class="anchor">#</span></a></h3>'
            f'<span class="sh-meta">{len(connect_rows)} ideas · {total_kudos} kudos · '
            f'{total_views:,} views · '
            f'<a href="{gh_blob_base}/{month_lower}_connect_ideas.md" style="color:var(--sky)" target="_blank">full report →</a></span>'
            f'</div>'
            f'<div class="box"><table>'
            f'<thead><tr><th class="num">Kudos</th><th class="num">Views</th>'
            f'<th>Status</th><th>Idea</th></tr></thead>'
            f'<tbody>{rows_html}</tbody></table></div>'
        )
    else:
        desktop_connect_html = ''

    # Android Connect wishlist
    if connect_android_ideas:
        month_prefix_ca = f"{year}-{config['month_num']}"
        prev_ca = {}
        if history:
            prior_keys = sorted(k for k in history if k < month_prefix_ca)
            if prior_keys:
                prev_ca = (history[prior_keys[-1]].get('connect_android') or {})
        ca_rows_html = ''
        for i, idea in enumerate(connect_android_ideas[:10], 1):
            prev_kudos = prev_ca.get(idea['url'])
            if prev_kudos is not None:
                diff = idea['kudos'] - prev_kudos
                delta_html = f'<span style="color:var(--{"green" if diff > 0 else "muted"})">{("+" if diff > 0 else "")}{diff}</span>'
            else:
                delta_html = '<span class="muted">—</span>'
            ca_rows_html += (
                f'<tr><td class="num muted">{i}</td>'
                f'<td><a href="{_esc(idea["url"])}" target="_blank" style="color:var(--text)">{_esc(idea["title"])}</a></td>'
                f'<td class="num">{idea["kudos"]}</td>'
                f'<td class="num">{delta_html}</td></tr>'
            )
        android_connect_html = (
            f'<div class="subsection-header" style="--sc: var(--orange)" id="connect-android">'
            f'<h3><a href="#connect-android">Mozilla Connect — Community Wishlist<span class="anchor">#</span></a></h3>'
            f'<span class="sh-meta">{len(connect_android_ideas)} ideas · '
            f'<a href="https://connect.mozilla.org/t5/ideas/idb-p/ideas/label-name/thunderbird%20android/tab/most-kudoed" '
            f'style="color:var(--orange)" target="_blank">view all on Mozilla Connect →</a></span>'
            f'</div>'
            f'<div class="box"><table>'
            f'<thead><tr><th class="num">#</th><th>Idea</th><th class="num">Kudos</th><th class="num">MoM</th></tr></thead>'
            f'<tbody>{ca_rows_html}</tbody></table></div>'
        )
    else:
        android_connect_html = ''

    # SUMO top contributors HTML builders
    def _sumo_contribs_html(contribs, color):
        if not contribs:
            return ''
        rows = ''.join(
            f'<tr><td><a href="https://support.mozilla.org/en-US/user/{urllib.parse.quote(str(u), safe="")}" '
            f'target="_blank" style="color:var({color})">{_esc(u)}</a></td>'
            f'<td class="num">{c}</td></tr>'
            for u, c in contribs
        )
        return (
            f'<div class="box"><h3>Top Contributors — SUMO</h3>'
            f'<table><thead><tr><th>Username</th><th class="num">Answers</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>'
        )

    desktop_contribs = (sumo_contributors or {}).get('desktop', [])
    android_contribs = (sumo_contributors or {}).get('android', [])
    desktop_contribs_html = _sumo_contribs_html(desktop_contribs, '--sky')
    android_contribs_html = _sumo_contribs_html(android_contribs, '--teal')

    # 3-month SUMO trends from history
    def sumo_trend(metric_key, current_val):
        if not history:
            return ''
        month_prefix = f"{year}-{config['month_num']}"
        keys = sorted(k for k in history if k < month_prefix)[-2:]
        vals = [history[k]['sumo'].get(metric_key) for k in keys] + [current_val]
        vals = [v for v in vals if v is not None]
        if len(vals) < 2:
            return ''
        return ' → '.join(str(v) for v in vals)

    # K-9 Discourse section
    if k9_discourse:
        kd = k9_discourse
        # 3-month trends for K-9 Discourse
        month_prefix_local = f"{year}-{config['month_num']}"
        prior_k9_keys = sorted(k for k in (history or {}) if k < month_prefix_local and (history or {}).get(k, {}).get('k9_discourse'))[-2:]

        def k9d_trend(metric_key, current_val):
            vals = [(history or {})[k]['k9_discourse'].get(metric_key) for k in prior_k9_keys] + [current_val]
            vals = [v for v in vals if v is not None]
            return ' → '.join(str(v) for v in vals) if len(vals) >= 2 else ''

        def k9_theme_trend(theme_name, current_count):
            vals = [(history or {})[k]['k9_discourse'].get('themes', {}).get(theme_name, 0) for k in prior_k9_keys] + [current_count]
            prior_vals = vals[:-1]
            is_new = all(v == 0 for v in prior_vals) and prior_k9_keys
            trend_str = ' → '.join(str(v) for v in vals) if len(vals) >= 2 else ''
            return trend_str, is_new

        k9_themes_rows = []
        for name, count in kd['top_themes']:
            trend_str, is_new = k9_theme_trend(name, count)
            new_badge = ' <span style="font-size:.65rem;color:var(--k9);font-weight:600">NEW ↑</span>' if is_new else ''
            # Red if current count more than doubles vs. the oldest value in the 3-month window
            oldest = [(history or {})[k]['k9_discourse'].get('themes', {}).get(name, 0) for k in prior_k9_keys[:1]]
            is_doubling = oldest and oldest[0] > 0 and count >= oldest[0] * 2
            count_html = f'<span style="color:var(--red);font-weight:600">{count}</span>' if is_doubling else str(count)
            trend_cell = f'<td class="num muted" style="font-size:.75rem">{trend_str}</td>' if trend_str else '<td></td>'
            k9_themes_rows.append(f'<tr><td>{_esc(name)}{new_badge}</td><td class="num">{count_html}</td>{trend_cell}</tr>')
        k9_themes_html = ''.join(k9_themes_rows)
        k9_themes_header = '<tr><th>Theme</th><th class="num">Topics</th><th class="num">3-mo trend</th></tr>'
        k9_contrib_rows = ''.join(
            f'<tr><td><a href="https://forum.k9mail.app/u/{urllib.parse.quote(str(u), safe="")}" style="color:var(--k9)" target="_blank">{_esc(u)}</a></td><td class="num">{c}</td></tr>'
            for u, c in kd.get('top_contributors', [])
        )
        k9_contrib_html = (
            f'<div class="box"><h3>Top Contributors</h3>'
            f'<table><thead><tr><th>Username</th><th class="num">Posts</th></tr></thead>'
            f'<tbody>{k9_contrib_rows}</tbody></table></div>'
        ) if k9_contrib_rows else ''
        topics_trend  = k9d_trend('total_topics',   kd['total_topics'])
        solved_trend  = k9d_trend('solved_pct',     kd['solved_pct'])
        unans_trend   = k9d_trend('unanswered_pct', kd['unanswered_pct'])
        k9_forum_section_html = f'''<div class="subsection-header" style="--sc: var(--k9)" id="k9-mail-forum">
  <h3><a href="#k9-mail-forum">K-9 Mail Forum<span class="anchor">#</span></a></h3>
  <span class="sh-meta">forum.k9mail.app · all categories · {month_cap} {year}</span>
</div>
<div class="grid" style="--sc: var(--k9)">
  <div class="card">
    <div class="label">New Topics</div>
    <div class="value">{kd['total_topics']}</div>
    <div class="change muted">{f'3-mo: {topics_trend}' if topics_trend else 'first month tracked'}</div>
  </div>
  <div class="card">
    <div class="label">Accepted Answer</div>
    <div class="value {'up' if kd['solved_pct'] >= 30 else 'down'}">{kd['solved_pct']}%</div>
    <div class="change muted">{f'3-mo: {solved_trend}%' if solved_trend else 'first month tracked'}</div>
  </div>
  <div class="card">
    <div class="label">Unanswered</div>
    <div class="value {'down' if kd['unanswered_pct'] >= 30 else ''}">{kd['unanswered_pct']}%</div>
    <div class="change muted">{f'3-mo: {unans_trend}%' if unans_trend else 'first month tracked'}</div>
  </div>
</div>
{'<div class="box"><h3>Top Topic Themes</h3><table><thead>' + k9_themes_header + '</thead><tbody>' + k9_themes_html + '</tbody></table></div>' if k9_themes_html else ''}
{k9_contrib_html}
<div class="box" style="font-size:.75rem;color:var(--muted);margin-top:.5rem">
  <strong style="color:var(--text)">Methodology</strong> — Topics sourced from the K-9 Mail Discourse forum
  (<a href="https://forum.k9mail.app" style="color:var(--k9)" target="_blank">forum.k9mail.app</a>)
  via the public Discourse search API, across all forum categories, filtered to the report month.
  <em>Accepted answer %</em> counts topics where a reply was marked as the solution — this undercounts
  actual resolution since many resolved threads are never formally marked.
  <em>Unanswered %</em> counts topics with zero replies.
  Themes are matched by keyword pattern against topic titles only.
  Data is fetched automatically at report generation time.
</div>'''
    else:
        k9_forum_section_html = ''

    # MoM helpers
    def csat_change(cur, prev):
        if cur is None or prev is None: return '—'
        d = round(cur - prev, 1)
        return f'+{d} pts' if d >= 0 else f'{d} pts'

    def ticket_change(cur, prev):
        if cur is None or prev is None: return '—'
        d = round((cur - prev) / prev * 100, 1) if prev else 0
        return f'+{d}%' if d >= 0 else f'{d}%'

    tb_rc = round(analysis['tb_avg_rating'] - p['tb_avg_rating'], 2) if p.get('tb_avg_rating') else 0
    k9_rc = round(analysis['k9_avg_rating'] - p['k9_avg_rating'], 2) if p.get('k9_avg_rating') else 0
    tb_rc_str = f'+{tb_rc}' if tb_rc >= 0 else str(tb_rc)
    k9_rc_str = f'+{k9_rc}' if k9_rc >= 0 else str(k9_rc)
    tb_dir = 'up' if tb_rc > 0 else ('down' if tb_rc < 0 else 'flat')
    k9_dir = 'up' if k9_rc > 0 else ('down' if k9_rc < 0 else 'flat')

    prev_month = config['prev_month']
    report_url = f"https://github.com/thunderbird/thunderbird-support-reports/blob/main/lisa/{year}/{month_cap.lower()}.md"

    report_note = (config.get('narrative') or {}).get('report_note') or ''
    report_note_html = f'<div class="report-note"><strong>Note:</strong> {report_note}</div>' if report_note else ''

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{month_cap} {year} — Thunderbird Support Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{
    --bg: #0f1117; --surface: #1a1d27; --border: #2a2d3a;
    --text: #e2e8f0; --muted: #94a3b8; --accent: #6366f1;
    --green: #22c55e; --red: #ef4444; --yellow: #f59e0b;
    --orange: #f97316; --sky: #38bdf8; --teal: #2dd4bf; --k9: #a78bfa;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: var(--bg); color: var(--text); font-family: -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif; padding: 2rem; max-width: 1200px; margin: 0 auto; }}
  h1 {{ font-size: 1.6rem; margin-bottom: .25rem; }}
  .subtitle {{ color: var(--muted); font-size: .9rem; margin-bottom: 2rem; }}
  .section-header {{ display: flex; align-items: center; gap: .75rem; margin: 2.5rem 0 1rem; padding-bottom: .6rem; border-bottom: 2px solid var(--sc); }}
  .section-header h2 {{ font-size: 1.1rem; font-weight: 700; text-transform: uppercase; letter-spacing: .1em; color: var(--sc); }}
  .section-header .sh-meta {{ font-size: .8rem; color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; }}
  .subsection-header {{ display: flex; align-items: center; gap: .75rem; margin: 2rem 0 .75rem; padding-bottom: .4rem; border-bottom: 1px dashed var(--sc); scroll-margin-top: 1rem; }}
  .subsection-header h3 {{ font-size: .9rem; font-weight: 600; text-transform: uppercase; letter-spacing: .08em; color: var(--sc); }}
  .subsection-header h3 a {{ color: inherit; text-decoration: none; }}
  .subsection-header h3 a:hover .anchor {{ opacity: 1; }}
  .subsection-header .anchor {{ opacity: 0; margin-left: .35rem; color: var(--muted); font-weight: 400; transition: opacity .15s; }}
  .subsection-header .sh-meta {{ font-size: .75rem; color: var(--muted); font-weight: 400; text-transform: none; letter-spacing: 0; }}
  .subsection-header:target {{ background: rgba(99,102,241,.08); border-radius: 6px; padding: .4rem .75rem; margin-left: -.75rem; margin-right: -.75rem; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit,minmax(160px,1fr)); gap: 1rem; margin-bottom: 1.5rem; }}
  .card {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.25rem; border-top: 3px solid var(--sc, var(--border)); }}
  .card .label {{ font-size: .75rem; color: var(--muted); text-transform: uppercase; letter-spacing: .05em; margin-bottom: .4rem; }}
  .card .value {{ font-size: 2rem; font-weight: 700; }}
  .card .change {{ font-size: .8rem; color: var(--muted); margin-top: .25rem; }}
  .up {{ color: var(--green); }} .down {{ color: var(--red); }} .flat {{ color: var(--yellow); }} .muted {{ color: var(--muted); }}
  .box {{ background: var(--surface); border: 1px solid var(--border); border-radius: 10px; padding: 1.5rem; margin-bottom: 1.5rem; }}
  .box h3 {{ font-size: .8rem; color: var(--muted); text-transform: uppercase; letter-spacing: .08em; margin-bottom: 1rem; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1.5rem; margin-bottom: 1.5rem; }}
  @media(max-width:700px){{ .two-col {{ grid-template-columns: 1fr; }} }}
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
  .alert {{ background: #2d1a1a; border: 1px solid #7f1d1d; border-radius: 10px; padding: 1rem 1.5rem; margin-bottom: 1.5rem; }}
  .alert-title {{ color: var(--red); font-weight: 700; margin-bottom: .35rem; }}
  .alert p {{ font-size: .9rem; color: #fca5a5; }}
  .filter-bar {{ display: flex; gap: .5rem; flex-wrap: wrap; margin-bottom: 1.5rem; }}
  .filter-btn {{ background: var(--surface); border: 1px solid var(--border); border-radius: 20px; padding: .35rem .9rem; font-size: .8rem; cursor: pointer; color: var(--muted); transition: all .15s; }}
  .filter-btn:hover {{ border-color: var(--text); color: var(--text); }}
  .filter-btn.active {{ color: var(--bg); font-weight: 600; }}
  .filter-section {{ transition: opacity .15s; }}
  .report-note {{ background: #1a2333; border: 1px solid #2d3a5a; border-left: 3px solid var(--sky); border-radius: 8px; padding: .75rem 1rem; margin: 0 0 1.5rem; font-size: .9rem; color: #c8d4ec; }}
  .report-note strong {{ color: var(--sky); }}
  .idea-status {{ display:inline-block; font-size:.7rem; font-weight:600; line-height:1.35; padding:2px 8px; border-radius:99px; border:1px solid var(--border); color:var(--muted); white-space:nowrap; }}
  .idea-status--flight {{ color:var(--accent); border-color:var(--accent); background:#1a1d3a; }}
  .idea-status--roadmap {{ color:var(--yellow); border-color:var(--yellow); background:#2a2010; }}
  .idea-status--landed {{ color:var(--green); border-color:var(--green); background:#0f2a1a; }}
  .idea-status--declined {{ color:var(--muted); border-color:var(--border); }}
  .idea-status--review {{ color:#a78bfa; border-color:#a78bfa; background:#1a1530; }}
  .idea-status--exploring {{ color:var(--yellow); border-color:var(--yellow); background:#2a2010; }}
  .idea-row-list {{ list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:.5rem;font-size:.82rem; }}
  .idea-row-list li {{ display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:.25rem .75rem;align-items:baseline;line-height:1.45;color:var(--muted); }}
  .idea-row-list .idea-row__title {{ color:var(--text);min-width:0; }}
  .idea-row-list .idea-row__votes {{ white-space:nowrap;font-variant-numeric:tabular-nums; }}
  .idea-row-list .idea-status {{ justify-self:end; }}
  .idea-row-list__empty {{ display:block;color:var(--muted); }}
  .tbl-muted {{ color:var(--muted); }}
</style>
</head>
<body>
<div style="display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:.5rem;margin-bottom:.25rem">
  <h1>{month_cap} {year} — Thunderbird Support Dashboard</h1>
  <a href="{report_url}" style="font-size:.85rem;color:var(--accent);text-decoration:none;">Full report on GitHub →</a>
</div>
<p class="subtitle">{month_cap} {year} report · generated {today}</p>

<div class="filter-bar">
  <button class="filter-btn active" style="background:var(--accent);border-color:var(--accent)" onclick="filterSection('all', this)">All</button>
  <button class="filter-btn" onclick="filterSection('donor', this)">Donor Care</button>
  <button class="filter-btn" onclick="filterSection('tbpro', this)">Thundermail</button>
  <button class="filter-btn" onclick="filterSection('android', this)">Android</button>
  <button class="filter-btn" onclick="filterSection('desktop', this)">Desktop</button>
</div>

<div class="filter-section" data-section="donor">
<div class="section-header" style="--sc: var(--green)">
  <h2>Donor Care</h2>
  <span class="sh-meta">{z['donor_tickets'] or '—'} tickets · Zendesk</span>
</div>
{report_note_html}
<div class="grid" style="--sc: var(--green)">
  <div class="card">
    <div class="label">Donor CSAT</div>
    <div class="value {'up' if (z['donor_csat'] or 0) > p['donor_csat'] else 'down'}">{z['donor_csat'] or '—'}%</div>
    <div class="change {'up' if (z['donor_csat'] or 0) > p['donor_csat'] else 'down'}">{csat_change(z['donor_csat'], p['donor_csat'])} MoM</div>
    {'<p style="font-size:.75rem;color:var(--muted);margin-top:.25rem;margin-bottom:0">' + z["donor_csat_note"] + '</p>' if z.get("donor_csat_note") else ''}
  </div>
  <div class="card">
    <div class="label">Donor Tickets</div>
    <div class="value">{z['donor_tickets'] or '—'}</div>
    <div class="change down">{ticket_change(z['donor_tickets'], p['donor_tickets'])} MoM</div>
  </div>
</div>
<div class="grid" style="--sc: var(--muted);margin-top:.5rem">
  <div class="card" style="border-color:var(--border)">
    <div class="label" style="color:var(--muted)">Total Tickets (all brands)</div>
    <div class="value">{z['total_tickets'] or '—'}</div>
    <div class="change {'up' if (z['total_tickets'] or 0) > (p.get('total_tickets') or 0) else 'down'}">{ticket_change(z['total_tickets'], p['total_tickets'])} MoM</div>
  </div>
</div>
</div><!-- /donor -->

<div class="filter-section" data-section="tbpro">
<div class="section-header" style="--sc: var(--accent)">
  <h2>Thundermail</h2>
  <span class="sh-meta">{z['tbpro_tickets'] or '—'} tickets · Zendesk · FeatureOS board 17437</span>
</div>
<div class="grid" style="--sc: var(--accent)">
  <div class="card">
    <div class="label">Thundermail CSAT</div>
    <div class="value up">{z['tbpro_csat'] or '—'}%{'*' if z.get('tbpro_csat_note') else ''}</div>
    <div class="change {'up' if z['tbpro_csat'] == 100 else 'flat'}">{'Perfect score ✅' if z['tbpro_csat'] == 100 and not z.get('tbpro_csat_note') else ''}</div>
  </div>
  <div class="card">
    <div class="label">Thundermail Tickets</div>
    <div class="value">{z['tbpro_tickets'] or '—'}</div>
    <div class="change down">{ticket_change(z['tbpro_tickets'], p['tbpro_tickets'])} MoM</div>
  </div>
</div>
{'<p style="font-size:.75rem;color:var(--muted);margin-top:.25rem;margin-bottom:1rem">*' + z["tbpro_csat_note"] + '</p>' if z.get("tbpro_csat_note") else ''}
{shipped_ideas_html}
{status_moves_html}
{quarterly_review_html}
<div class="two-col">
  <div class="box">
    <h3>New Ideas — {month_cap} ({n_new_ideas} total)</h3>
    <table>
      <thead><tr><th>Idea</th><th class="num">Votes</th><th>Tag</th></tr></thead>
      <tbody>{new_ideas_html}</tbody>
    </table>
  </div>
  <div class="box">
    <h3>Top Ideas All-Time</h3>
    <table>
      <thead><tr><th>Idea</th><th class="num">Votes</th><th>Status</th><th>Tag</th></tr></thead>
      <tbody>{top_ideas_html}</tbody>
    </table>
  </div>
</div>
</div><!-- /tbpro -->

<div class="filter-section" data-section="android">
<div class="section-header" style="--sc: var(--orange)">
  <h2>Android</h2>
  <span class="sh-meta">Play Store reviews · SUMO Android forum · K-9 Mail Discourse · {month_cap} {year}</span>
</div>

<div class="subsection-header" style="--sc: var(--orange)" id="play-store-reviews">
  <h3><a href="#play-store-reviews">Play Store Reviews<span class="anchor">#</span></a></h3>
  <span class="sh-meta">{analysis['total_count']} reviews · TB {analysis['tb_count']}{ (' (' + str(analysis['tb_count'] - analysis['beta_count']) + ' stable + ' + str(analysis['beta_count']) + ' beta)') if analysis.get('beta_count') else ''} · K-9 {analysis['k9_count']} · {analysis['unique_languages']} languages</span>
</div>
<div class="alert">
  <div class="alert-title">⚠️ Play Store Rating — Q{(int(config['month_num']) - 1) // 3 + 1} Trend</div>
  <p>TB: {analysis['tb_avg_rating']:.2f}★ this month ({tb_rc_str} from {prev_month}). Track against 4★ annual goal.</p>
</div>
<div class="grid" style="--sc: var(--orange)">
  <div class="card">
    <div class="label">TB Avg Rating</div>
    <div class="value">{analysis['tb_avg_rating']:.2f}★</div>
    <div class="change {tb_dir}">{tb_rc_str} from {prev_month}</div>
  </div>
  <div class="card">
    <div class="label">K-9 Avg Rating</div>
    <div class="value">{analysis['k9_avg_rating']:.2f}★</div>
    <div class="change {k9_dir}">{k9_rc_str} from {prev_month}</div>
  </div>
  <div class="card">
    <div class="label">Play Store Tickets</div>
    <div class="value">{analysis['replies_to_low_star']}</div>
    <div class="change">{'Up' if analysis['replies_to_low_star'] > p['replies_to_low_star'] else 'Down'} from {p['replies_to_low_star']}</div>
  </div>
</div>
<div class="two-col">
  <div class="box">
    <h3>Star Distribution — TB ({analysis['tb_count']} reviews)</h3>
    <canvas id="tbChart"></canvas>
  </div>
  <div class="box">
    <h3>Star Distribution — K-9 ({analysis['k9_count']} reviews)</h3>
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
      <th>Neg. mentions trend<br><span style="font-weight:400;font-size:.7rem">rolling 3 months</span></th>
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
      <tr><td style="color:var(--muted);font-weight:600">Neg. mentions trend</td><td>Count of negative mentions (1–3★) for that topic over the rolling 3-month window.</td></tr>
    </tbody>
  </table>
</div>

<div class="subsection-header" style="--sc: var(--teal)" id="android-forum">
  <h3><a href="#android-forum">Android Forum<span class="anchor">#</span></a></h3>
  <span class="sh-meta">SUMO · thunderbird-android · {month_cap} {year}</span>
</div>
<div class="grid" style="--sc: var(--teal)">
  <div class="card">
    <div class="label">Questions</div>
    <div class="value">{a_real}</div>
    <div class="change {mom_cls(a_sumo.get('total_questions'), p.get('android_questions'))}">{mom_pts(a_sumo.get('total_questions'), p.get('android_questions'))} MoM</div>
  </div>
  <div class="card">
    <div class="label">Solved Rate</div>
    <div class="value {mom_cls(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))}">{a_solved}{'%' if a_solved != '—' else ''}</div>
    <div class="change {mom_cls(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))}">{mom_pts(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))} pts MoM</div>
  </div>
  <div class="card">
    <div class="label">Ignored %</div>
    <div class="value {mom_cls(p.get('android_ignored_pct'), a_sumo.get('ignored_pct'))}">{a_ignored}{'%' if a_ignored != '—' else ''}</div>
    <div class="change {mom_cls(p.get('android_ignored_pct'), a_sumo.get('ignored_pct'))}">{mom_pts(a_sumo.get('ignored_pct'), p.get('android_ignored_pct'))} pts MoM</div>
  </div>
</div>
<div class="box">
  <table>
    <thead><tr><th>Metric</th><th class="num">Value</th><th class="num">MoM</th><th class="num">3-mo trend</th></tr></thead>
    <tbody>
      <tr><td>Questions (excl. spam)</td><td class="num">{a_real}</td><td class="num muted">{mom_pts(a_sumo.get('total_questions'), p.get('android_questions'))}</td><td class="num muted" style="font-size:.75rem">{sumo_trend('android_questions', a_sumo.get('total_questions'))}</td></tr>
      <tr><td>Overall Solved Rate</td><td class="num {mom_cls(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))}">{a_solved}{'%' if a_solved != '—' else ''}</td><td class="num {mom_cls(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))}">{mom_pts(a_sumo.get('overall_solved_rate'), p.get('android_solved_rate'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('android_solved_rate', a_sumo.get('overall_solved_rate'))}</td></tr>
      <tr><td>Ignored %</td><td class="num">{a_ignored}{'%' if a_ignored != '—' else ''}</td><td class="num {mom_cls(p.get('android_ignored_pct'), a_sumo.get('ignored_pct'))}">{mom_pts(a_sumo.get('ignored_pct'), p.get('android_ignored_pct'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('android_ignored_pct', a_sumo.get('ignored_pct'))}</td></tr>
      <tr><td>Trusted Contributor %</td><td class="num">{a_tc_pct}{'%' if a_tc_pct != '—' else ''}</td><td class="num {mom_cls(a_sumo.get('trusted_contributor_pct'), p.get('android_tc_pct'))}">{mom_pts(a_sumo.get('trusted_contributor_pct'), p.get('android_tc_pct'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('android_tc_pct', a_sumo.get('trusted_contributor_pct'))}</td></tr>
      {a_tc_row}
    </tbody>
  </table>
</div>
{f'<div class="box"><h3>Top Signals</h3><table><thead><tr><th>Signal</th><th class="num">Questions</th></tr></thead><tbody>{a_signals_html}</tbody></table></div>' if a_signals_html else ''}
{android_contribs_html}

{android_connect_html}

{k9_forum_section_html}
</div><!-- /android -->

<div class="filter-section" data-section="desktop">
<div class="section-header" style="--sc: var(--sky)">
  <h2>Desktop</h2>
  <span class="sh-meta">SUMO forum · trending topics · engineering priorities · Mozilla Connect · {month_cap} {year}</span>
</div>

<div class="subsection-header" style="--sc: var(--sky)" id="sumo-forum">
  <h3><a href="#sumo-forum">SUMO Forum<span class="anchor">#</span></a></h3>
  <span class="sh-meta">SUMO · thunderbird · {month_cap} {year}</span>
</div>
<div class="grid" style="--sc: var(--sky)">
  <div class="card">
    <div class="label">Questions</div>
    <div class="value">{d_real}</div>
    <div class="change {mom_cls(d_sumo.get('total_questions'), p.get('desktop_questions'))}">{mom_pts(d_sumo.get('total_questions'), p.get('desktop_questions'))} MoM</div>
  </div>
  <div class="card">
    <div class="label">Solved Rate</div>
    <div class="value {mom_cls(d_sumo.get('overall_solved_rate'), p.get('desktop_solved_rate'))}">{d_solved}{'%' if d_solved != '—' else ''}</div>
    <div class="change {mom_cls(d_sumo.get('overall_solved_rate'), p.get('desktop_solved_rate'))}">{mom_pts(d_sumo.get('overall_solved_rate'), p.get('desktop_solved_rate'))} pts MoM</div>
  </div>
  <div class="card">
    <div class="label">Ignored %</div>
    <div class="value {mom_cls(p.get('desktop_ignored_pct'), d_sumo.get('ignored_pct'))}">{d_ignored}{'%' if d_ignored != '—' else ''}</div>
    <div class="change {mom_cls(p.get('desktop_ignored_pct'), d_sumo.get('ignored_pct'))}">{mom_pts(d_sumo.get('ignored_pct'), p.get('desktop_ignored_pct'))} pts MoM</div>
  </div>
</div>
<div class="box">
  <table>
    <thead><tr><th>Metric</th><th class="num">Value</th><th class="num">MoM</th><th class="num">3-mo trend</th></tr></thead>
    <tbody>
      <tr><td>Questions (excl. spam)</td><td class="num">{d_real}</td><td class="num muted">{mom_pts(d_sumo.get('total_questions'), p.get('desktop_questions'))}</td><td class="num muted" style="font-size:.75rem">{sumo_trend('desktop_questions', d_sumo.get('total_questions'))}</td></tr>
      <tr><td>Overall Solved Rate</td><td class="num">{d_solved}{'%' if d_solved != '—' else ''}</td><td class="num {mom_cls(d_sumo.get('overall_solved_rate'), p.get('desktop_solved_rate'))}">{mom_pts(d_sumo.get('overall_solved_rate'), p.get('desktop_solved_rate'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('desktop_solved_rate', d_sumo.get('overall_solved_rate'))}</td></tr>
      <tr><td>Ignored %</td><td class="num">{d_ignored}{'%' if d_ignored != '—' else ''}</td><td class="num {mom_cls(p.get('desktop_ignored_pct'), d_sumo.get('ignored_pct'))}">{mom_pts(d_sumo.get('ignored_pct'), p.get('desktop_ignored_pct'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('desktop_ignored_pct', d_sumo.get('ignored_pct'))}</td></tr>
      <tr><td>Trusted Contributor %</td><td class="num">{d_tc_pct}{'%' if d_tc_pct != '—' else ''}</td><td class="num {mom_cls(d_sumo.get('trusted_contributor_pct'), p.get('desktop_tc_pct'))}">{mom_pts(d_sumo.get('trusted_contributor_pct'), p.get('desktop_tc_pct'))} pts</td><td class="num muted" style="font-size:.75rem">{sumo_trend('desktop_tc_pct', d_sumo.get('trusted_contributor_pct'))}</td></tr>
      {d_tc_row}
    </tbody>
  </table>
</div>
{f'<div class="box"><h3>Top Signals</h3><table><thead><tr><th>Signal</th><th class="num">Questions</th><th class="num">MoM</th></tr></thead><tbody>{d_signals_html}</tbody></table></div>' if d_signals_html else ''}

{desktop_trending_html}

{desktop_priorities_html}

{desktop_connect_html}
{desktop_contribs_html}
</div><!-- /desktop -->

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
const subsectionToParent = {{
  'play-store-reviews': 'android',
  'android-forum': 'android',
  'connect-android': 'android',
  'k9-mail-forum': 'android',
  'sumo-forum': 'desktop',
  'top-trending-topics': 'desktop',
  'recommended-priorities': 'desktop',
  'mozilla-connect': 'desktop'
}};
function applyHash() {{
  const hash = window.location.hash.replace('#', '');
  if (!hash) return;
  const parent = subsectionToParent[hash];
  const filterKey = parent || hash;
  const btn = document.querySelector(`.filter-btn[onclick*="'${{filterKey}}'"]`);
  if (btn) filterSection(filterKey, btn);
  if (parent) {{
    const el = document.getElementById(hash);
    if (el) el.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
  }}
}}
window.addEventListener('DOMContentLoaded', applyHash);
window.addEventListener('hashchange', applyHash);
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
    return html


# ── CSV Export ────────────────────────────────────────────────────────────────

def build_csv(config, analysis, month_cap, year):
    z = config['zendesk']
    p = config['prev']

    def pct_change(cur, prev):
        if cur is None or prev is None or prev == 0: return None
        return round((cur - prev) / prev * 100, 1)

    rows = [
        (month_cap, year, 'Support Metrics', 'Private Support', 'Overall CSAT',
         None, z['overall_csat'], None, round(z['overall_csat'] - p['overall_csat'], 1) if z['overall_csat'] else None,
         'up' if (z['overall_csat'] or 0) > p['overall_csat'] else 'down', None, None, None, 'Zendesk', ''),
        (month_cap, year, 'Support Metrics', 'Private Support', 'CSAT Donor Support',
         None, z['donor_csat'], None, round(z['donor_csat'] - p['donor_csat'], 1) if z['donor_csat'] else None,
         'up' if (z['donor_csat'] or 0) > p['donor_csat'] else 'down', None, None, None, 'Zendesk', ''),
        (month_cap, year, 'Support Metrics', 'Private Support', 'CSAT Thundermail',
         None, z['tbpro_csat'], None, None, 'flat', None, None, None, 'Zendesk', ''),
        (month_cap, year, 'Support Metrics', 'Private Support', 'Total Tickets',
         z['total_tickets'], None,
         (z['total_tickets'] - p['total_tickets']) if z['total_tickets'] else None,
         pct_change(z['total_tickets'], p['total_tickets']),
         'down' if (z['total_tickets'] or 0) < p['total_tickets'] else 'up',
         None, None, None, 'Zendesk', ''),
        (month_cap, year, 'Android Reviews', 'Overview', 'Total Reviews',
         analysis['total_count'], None, None, None, None,
         analysis['overall_avg_rating'], analysis['tb_count'], analysis['k9_count'], 'Play Store', ''),
        (month_cap, year, 'Android Reviews', 'Overview', 'TB Reviews',
         analysis['tb_count'], None, None, None, None,
         analysis['tb_avg_rating'], analysis['tb_count'], None, 'Play Store', ''),
        (month_cap, year, 'Android Reviews', 'Overview', 'K-9 Reviews',
         analysis['k9_count'], None, None, None, None,
         analysis['k9_avg_rating'], None, analysis['k9_count'], 'Play Store', ''),
        (month_cap, year, 'Android Reviews', 'Overview', 'Play Store Tickets (incoming)',
         analysis['replies_to_low_star'], None, None, None, None, None, None, None, 'Play Store', ''),
    ]

    friction_order = [
        'Push / Notification Sync', 'Spam Filter Absent', 'Crashes & Freezes',
        'Calendar Missing', 'Stuck Outbox / Send Failure',
        'QR / Settings Import', 'Email Headers / Print',
    ]
    for theme in friction_order:
        if theme not in analysis['friction']:
            continue
        s = analysis['friction'][theme]
        rows.append((month_cap, year, 'Android Reviews', 'Friction', theme,
                     s['total'], None, None, None, None,
                     s['avg_rating'], s['tb_count'], s['k9_count'],
                     'Play Store', f"neg:{s['negative']}"))

    return rows


# ── Notion ────────────────────────────────────────────────────────────────────

NOTION_DATABASE_ID = '3412df5d-45ae-80f7-b05c-f1924937f82d'

def push_to_notion(config, analysis, month_cap, year):
    token = os.environ.get('NOTION_TOKEN')
    if not token:
        print("  NOTION_TOKEN not set — skipping Notion update")
        return

    z = config['zendesk']
    report_url = f"https://thunderbird.github.io/thunderbird-support-reports/lisa/{year}/{month_cap.lower()}.html"
    row_title  = f"{month_cap} in Support ({year})"

    def to_pct(v):
        return round(v / 100, 4) if v is not None else None

    properties = {
        "Name": {"title": [{"type": "text", "text": {
            "content": row_title,
            "link": {"url": report_url},
        }}]},
        "Posted Date": {"date": {"start": date.today().isoformat()}},
        "Overall CSAT": {"number": to_pct(z.get('overall_csat'))},
        "Thundermail CSAT":  {"number": to_pct(z.get('tbpro_csat'))},
        "TfA Rating":   {"number": analysis['tb_avg_rating'] or None},
        "K-9 Rating":   {"number": analysis['k9_avg_rating'] or None},
    }

    # Strip None-valued number properties — Notion API rejects {"number": null}
    properties = {
        k: v for k, v in properties.items()
        if not (v.get("number") is None and "number" in v)
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }

    def _notion_request(url, body, method):
        req = urllib.request.Request(
            url, data=json.dumps(body).encode(), headers=headers, method=method,
        )
        try:
            with urllib.request.urlopen(req) as resp:
                return json.loads(resp.read()), None
        except urllib.error.HTTPError as e:
            return None, (e.code, e.read().decode())

    # Look up existing row with this title
    existing_id = None
    query_body = {
        "filter": {"property": "Name", "title": {"equals": row_title}},
        "page_size": 1,
    }
    result, err = _notion_request(
        f"https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query",
        query_body, "POST",
    )
    if err:
        print(f"  Notion query failed ({err[0]}): {err[1]}")
        return
    if result.get('results'):
        existing_id = result['results'][0]['id']

    if existing_id:
        result, err = _notion_request(
            f"https://api.notion.com/v1/pages/{existing_id}",
            {"properties": properties}, "PATCH",
        )
        if err:
            print(f"  Notion update failed ({err[0]}): {err[1]}")
        else:
            print(f"✓ Notion row updated: {result['url']}")
    else:
        result, err = _notion_request(
            "https://api.notion.com/v1/pages",
            {"parent": {"database_id": NOTION_DATABASE_ID}, "properties": properties},
            "POST",
        )
        if err:
            print(f"  Notion create failed ({err[0]}): {err[1]}")
        else:
            print(f"✓ Notion row created: {result['url']}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 3:
        sys.exit("Usage: uv run scripts/generate.py <month> <year>\nExample: uv run scripts/generate.py april 2026")

    month = sys.argv[1].lower()
    year  = sys.argv[2]
    month_cap = month.capitalize()

    if month not in MONTH_NUMS:
        sys.exit(f"Unknown month: {month}")

    month_num    = MONTH_NUMS[month]
    month_prefix = f"{year}-{month_num}"

    BASE        = Path(__file__).parent.parent
    config_path = BASE / 'data' / f'{month}_{year}.yaml'
    out_dir     = BASE / 'lisa' / year
    out_dir.mkdir(parents=True, exist_ok=True)

    if not config_path.exists():
        sys.exit(f"Config not found: {config_path}\nCreate it from the template first.")

    config = yaml.safe_load(config_path.read_text())
    print(f"✓ Config loaded: {config_path}")

    # Load history and derive prev + history_neg automatically
    history = load_history(BASE)
    prev_entry = prev_from_history(history, month_prefix)
    if prev_entry:
        # History takes precedence; YAML prev is a fallback only
        config['prev'] = {
            'overall_csat':        prev_entry['zendesk'].get('overall_csat'),
            'donor_csat':          prev_entry['zendesk'].get('donor_csat'),
            'tbpro_csat':          prev_entry['zendesk'].get('tbpro_csat'),
            'total_tickets':       prev_entry['zendesk'].get('total_tickets'),
            'donor_tickets':       prev_entry['zendesk'].get('donor_tickets'),
            'tbpro_tickets':       prev_entry['zendesk'].get('tbpro_tickets'),
            'tb_avg_rating':       prev_entry['play_store'].get('tb_avg_rating'),
            'k9_avg_rating':       prev_entry['play_store'].get('k9_avg_rating'),
            'replies_to_low_star': prev_entry['play_store'].get('replies_to_low_star'),
            'desktop_solved_rate': prev_entry['sumo'].get('desktop_solved_rate'),
            'desktop_ignored_pct': prev_entry['sumo'].get('desktop_ignored_pct'),
            'desktop_tc_pct':      prev_entry['sumo'].get('desktop_tc_pct'),
            'desktop_questions':   prev_entry['sumo'].get('desktop_questions'),
            'android_solved_rate': prev_entry['sumo'].get('android_solved_rate'),
            'android_ignored_pct': prev_entry['sumo'].get('android_ignored_pct'),
            'android_tc_pct':      prev_entry['sumo'].get('android_tc_pct'),
            'android_questions':   prev_entry['sumo'].get('android_questions'),
        }
        config['history_neg'] = history_neg_from_history(history, month_prefix, list(THEMES.keys()))
        print(f"✓ History loaded: prev month = {prev_entry['month']} {prev_entry['year']}")
    else:
        print("  No history found — using YAML prev values")

    # Analyze CSVs
    print(f"  Analyzing Play Store CSVs ({month_prefix})…")
    analysis = analyze_csvs(BASE, config, month_prefix)
    # Allow YAML override for metrics that Zendesk tracks more accurately (e.g. includes Beta)
    if config.get('zendesk', {}).get('replies_to_low_star'):
        analysis['replies_to_low_star'] = config['zendesk']['replies_to_low_star']
    print(f"  TB: {analysis['tb_count']} reviews  K-9: {analysis['k9_count']} reviews")

    # Save analysis JSON
    json_path = out_dir / f'{month}_analysis.json'
    json_path.write_text(json.dumps(analysis, indent=2))
    print(f"✓ Analysis JSON: {json_path}")

    from datetime import date
    today = date.today().isoformat()

    # Generate outputs
    md_path   = out_dir / f'{month}.md'
    html_path = out_dir / f'{month}.html'
    csv_path  = out_dir / f'{month}.csv'

    prev_idea_snapshot = prev_entry.get('tbpro_ideas', {}) if prev_entry else {}

    from featureos_snapshot import (
        capture_featureos_snapshot,
        diff_status_moves,
        prior_featureos_snapshot,
        resolve_status_moves,
    )
    print('  Fetching FeatureOS Thundermail idea statuses…')
    history, fos_ideas, fos_captured = capture_featureos_snapshot(BASE, month_prefix)
    prior_fos = prior_featureos_snapshot(history, month_prefix)
    has_prior_fos = bool(prior_fos)
    auto_status_moves = diff_status_moves(fos_ideas, prior_fos) if has_prior_fos and fos_ideas else []
    if fos_ideas:
        print(f'  FeatureOS: {len(fos_ideas)} ideas snapshotted ({fos_captured})')
        if has_prior_fos:
            print(f'  FeatureOS status diff vs prior month: {len(auto_status_moves)} move(s)')
        else:
            print('  FeatureOS: no prior snapshot — using YAML status_moves if present')
    else:
        print('  FeatureOS: snapshot skipped (fetch failed)')
    status_moves_block = resolve_status_moves(
        config.get('tbpro_ideas', {}), auto_status_moves, has_prior_fos
    )

    print("  Fetching Mozilla Connect Android ideas…")
    connect_android_ideas = fetch_connect_android_ideas()
    if connect_android_ideas:
        print(f"  Mozilla Connect Android: {len(connect_android_ideas)} ideas · top kudos: {connect_android_ideas[0]['kudos']} ({connect_android_ideas[0]['title'][:50]})")
    else:
        print("  Mozilla Connect Android: fetch failed (skipping)")

    month_num_str = config.get('month_num', MONTH_NUMS.get(month.lower(), '01'))
    print("  Fetching SUMO top contributors (desktop + android)…")
    sumo_contributors = {
        'desktop': fetch_sumo_contributors(year, month_num_str, 'desktop'),
        'android': fetch_sumo_contributors(year, month_num_str, 'android'),
    }
    if sumo_contributors['desktop']:
        print(f"  Desktop SUMO top contributor: {sumo_contributors['desktop'][0][0]} ({sumo_contributors['desktop'][0][1]} answers)")

    print("  Fetching K-9 Discourse forum data…")
    k9_discourse = fetch_k9_discourse(month_prefix)
    if k9_discourse:
        print(f"  K-9 Forum: {k9_discourse['total_topics']} topics · {k9_discourse['solved_pct']}% resolved · {k9_discourse['unanswered_pct']}% unanswered")
    else:
        cached = (history or {}).get(month_prefix, {}).get('k9_discourse')
        if cached and cached.get('total_topics'):
            print(f"  K-9 Forum: using cached data from history.json ({cached['total_topics']} topics)")
            k9_discourse = {
                'total_topics':     cached['total_topics'],
                'solved':           round(cached['total_topics'] * cached.get('solved_pct', 0) / 100),
                'solved_pct':       cached.get('solved_pct', 0),
                'unanswered':       round(cached['total_topics'] * cached.get('unanswered_pct', 0) / 100),
                'unanswered_pct':   cached.get('unanswered_pct', 0),
                'top_themes':       list(cached.get('themes', {}).items()),
                'top_contributors': [],
            }
        else:
            print("  K-9 Discourse: no data (skipping tab)")

    new_md = build_report(config, analysis, month_cap, year, prev_idea_snapshot)
    # Preserve manually-edited narrative sections from an existing report
    if md_path.exists():
        new_md = _preserve_narrative(md_path.read_text(), new_md)
    md_path.write_text(new_md)
    print(f"✓ Report: {md_path}")

    html_path.write_text(build_dashboard(config, analysis, month_cap, year, today, prev_idea_snapshot, k9_discourse, history, connect_android_ideas, sumo_contributors, status_moves_block, config.get('tbpro_ideas', {}).get('quarterly_review')))
    print(f"✓ Dashboard: {html_path}")

    csv_rows = build_csv(config, analysis, month_cap, year)
    with open(csv_path, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['month','year','section','category','metric','value_number','value_percent',
                    'mom_change_number','mom_change_percent','mom_direction','avg_rating',
                    'tb_count','k9_count','source','notes'])
        w.writerows(csv_rows)
    print(f"✓ CSV: {csv_path}")

    # Append to history, then patch in k9_discourse data
    updated_history = append_to_history(BASE, month_prefix, month_cap, year, analysis, config)
    needs_history_write = False
    if k9_discourse:
        updated_history[month_prefix]['k9_discourse'] = {
            'total_topics':    k9_discourse['total_topics'],
            'solved_pct':      k9_discourse['solved_pct'],
            'unanswered_pct':  k9_discourse['unanswered_pct'],
            'themes':          {name: count for name, count in k9_discourse['top_themes']},
        }
        needs_history_write = True
    if connect_android_ideas:
        updated_history[month_prefix]['connect_android'] = {
            idea['url']: idea['kudos'] for idea in connect_android_ideas
        }
        needs_history_write = True
    if needs_history_write:
        path = BASE / 'data' / 'history.json'
        _write_history_json(path, updated_history)
    print(f"✓ History updated: data/history.json")

    # Push to Notion
    push_to_notion(config, analysis, month_cap, year)

    # Update index.md
    index_path = BASE / 'index.md'
    index = index_path.read_text()
    new_row = f"| {month_cap} | [{month_cap} {year}](lisa/{year}/{month}.md) | [Dashboard](https://thunderbird.github.io/thunderbird-support-reports/lisa/{year}/{month}.html) | [CSV](lisa/{year}/{month}.csv) |"
    if month.lower() not in index:
        index = index.rstrip() + f"\n{new_row}\n"
        index_path.write_text(index)
        print(f"✓ index.md updated")
    else:
        print(f"  index.md already has {month_cap} entry — skipped")

    print(f"\nDone. Next steps:")
    print(f"  1. Fill in narrative sections in {md_path.name}")
    print(f"  2. Review dashboard: open {html_path}")
    print(f"  3. Commit and push")


if __name__ == '__main__':
    main()
