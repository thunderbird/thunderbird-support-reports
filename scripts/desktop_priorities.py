#!/usr/bin/env python3
"""
Generate a desktop-engineering prioritization drill-down from SUMO data.

Pulls the monthly questions CSV from thunderbird-metrics-and-reports and
classifies each question against three themes the desktop team should care
about based on April community signal:

  1. Authentication / OAuth fragility
  2. Update regressions
  3. Data loss / folder integrity

A question can hit more than one theme. Each theme is split into sub-themes
grounded in real title patterns seen in the data.

Usage:
    python3 scripts/desktop_priorities.py <month-name> <year>
    python3 scripts/desktop_priorities.py april 2026

Output:
    lisa/<year>/<month>_desktop_priorities.md
"""

import base64
import csv
import io
import json
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

csv.field_size_limit(sys.maxsize)

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

GH_PATH = (
    'repos/thunderbird/thunderbird-metrics-and-reports/contents/'
    'CONCATENATED_FILES/DESKTOP/'
    '{year}-{month:02d}-sumo-desktop-questions.csv'
)

AUTH_TAGS = {
    'passwords-and-sign-in', 'save-passwords', 'reset-passwords',
    'accounts', 'account-management',
}
AUTH_TITLE_RE = re.compile(
    r'\b(oauth|password|passwd|sign[- ]?in|signin|sign[- ]?on|login|log[- ]?in|'
    r'authentic\w*|authoriz\w*|2fa|two[- ]factor|mfa|app[- ]password|'
    r'certificate|cert\s+error|primary password|imap.*fail|smtp.*fail|'
    r'connection.*reset|connection.*fail|cannot connect|can.?t connect|'
    r'account.*setup|setup hub|new account|add (a|an)?\s*(gmail|outlook|hotmail|yahoo|comcast|aol|icloud)\s*account)\b',
    re.I,
)
PROVIDER_RE = re.compile(
    r'\b(gmail|google|outlook|hotmail|live\.de|live\.com|office\s*365|microsoft|'
    r'yahoo|aol|icloud|comcast|charter|spectrum|att|sbcglobal|cox|verizon|'
    r'orange|primus|centurylink|infomaniak|gmx|t-online|web\.de|bt|zoho)\b',
    re.I,
)

UPDATE_TITLE_RE = re.compile(
    r'\b(after (the )?(update|upgrade|install)|since (the )?(update|upgrade)|'
    r'since v?\d+|after v?\d+|after\s+(tb|thunderbird)\s+(update|upgrade|\d)|'
    r'broke(n)?\s+(after|since)|stopped (working|sending|receiving)\s+(after|since)|'
    r'used to (work|show|display)|no longer (work|show|display|see|able|asking|drag|able)|'
    r'used to be|grayed out|greyed out|disappeared|missing.*after.*update|'
    r'regression|now.*broken)\b',
    re.I,
)
UPDATE_VERSION_RE = re.compile(
    r'\b(140|140\.\d+|140\.\d+\.\d+|149|149\.\d+|149\.\d+\.\d+|150|150\.\d+|151|151\.\d+)\b',
)

DATA_LOSS_TITLE_RE = re.compile(
    r'\b(lost|missing|disappear\w*|vanish\w*|wiped|gone|removed|deleted|delete\s+all|'
    r'recover\w*|restor\w*|undelete|expunge|empty\s+(inbox|folder|trash)|'
    r'can(?:no|.?)t\s+find|where\s+(are|is)\s+my|cant locate|lose\s+\w+|'
    r'folder.*not\s+(display|show|visible|appear)|subfolder\w*\s+(disappear|gone|missing|invisible)|'
    r'emails?\s+(invisible|gone|removed))\b',
    re.I,
)
DATA_LOSS_ENTITY_RE = re.compile(
    r'\b(folder|subfolder|email|message|mail|inbox|local folder|sent|drafts|trash|profile)s?\b',
    re.I,
)


def is_english(locale):
    return (locale or '').startswith('en')


def question_text(q):
    return f"{q.get('title','')}\n{q.get('content','')}"


def matches_auth(q):
    tags = {t.strip().lower() for t in (q.get('tags') or '').split(';') if t.strip()}
    if tags & AUTH_TAGS:
        return True
    title = q.get('title') or ''
    if AUTH_TITLE_RE.search(title):
        return True
    return False


def matches_update_regression(q):
    title = q.get('title') or ''
    content = (q.get('content') or '')[:500]
    text = f'{title}\n{content}'
    if UPDATE_TITLE_RE.search(text):
        return True
    if re.search(r'\b(after|since)\b', text, re.I) and UPDATE_VERSION_RE.search(text):
        return True
    return False


def matches_data_loss(q):
    title = q.get('title') or ''
    if DATA_LOSS_TITLE_RE.search(title) and DATA_LOSS_ENTITY_RE.search(title):
        return True
    return False


AUTH_SUB = [
    ('OAuth / Google',
     re.compile(r'\b(oauth|google|gmail)\b', re.I)),
    ('Microsoft / Outlook (incl. 2FA)',
     re.compile(r'\b(outlook|hotmail|live\.de|microsoft|office\s*365|2fa|two[- ]factor|mfa)\b', re.I)),
    ('Yahoo / AOL',
     re.compile(r'\b(yahoo|ymail|aol|verizon\.net)\b', re.I)),
    ('After password change',
     re.compile(r'\b(after.*chang\w*\s+(my\s+)?password|changed.*password|new password|password.*chang\w*)\b', re.I)),
    ('After Thunderbird update',
     re.compile(r'\b(after.*(update|upgrade)|since.*(update|upgrade))\b', re.I)),
    ('Repeated password prompts',
     re.compile(r'\b(keeps?\s+asking|prompt\w*\s+for\s+password|enter.*password.*download|asking for (the )?password)\b', re.I)),
    ('Connection / server reset',
     re.compile(r'\b(connection.*reset|server.*reset|connection.*fail|cannot\s+connect|can.?t\s+connect)\b', re.I)),
    ('New Account Setup Hub',
     re.compile(r'\b(account.*setup.*hub|setup hub|new account.*hub|add.*account.*hub|account hub)\b', re.I)),
    ('Primary Password',
     re.compile(r'\bprimary\s+password\b', re.I)),
    ('Passkey / modern auth requests',
     re.compile(r'\b(passkey|webauthn|fido)\b', re.I)),
    ('Certificate errors',
     re.compile(r'\b(certificate|cert)\b.{0,40}\b(expired|trusted|invalid|error|untrusted|not\s+from|does\s+not\s+come)\b|'
                r'\b(expired|untrusted|invalid)\b.{0,40}\b(certificate|cert)\b', re.I)),
    ('New computer / reinstall auth',
     re.compile(r'\b(new\s+(computer|pc|laptop|machine|install)|reinstall\w*|re-install\w*|'
                r'moved?\s+(to|my)\s+(new|another|different)\s+(computer|pc|laptop|machine)|'
                r'after\s+(reinstall|moving|transferring|new\s+computer|new\s+laptop|new\s+install|windows\s+reset)|'
                r'set\s+up\s+(again|on\s+(a\s+)?new)|on\s+(a\s+)?new\s+(computer|pc|laptop))\b', re.I)),
]

UPDATE_SUB = [
    ('Send/Receive broke after update',
     re.compile(r'\b(send|receive|smtp|imap|pop)\b.*\b(after|since).*(update|upgrade|\d+\.\d+)|'
                r'\b(after|since).*(update|upgrade).*\b(send|receive|smtp|imap|pop)\b', re.I)),
    ('UI / layout change',
     re.compile(r'\b(layout|view|toolbar|column|pane|grayed|greyed|theme|dark|font|color|colour|threading|thread\s+(view|management))\b', re.I)),
    ('Drag-and-drop broken',
     re.compile(r'\b(drag\s*(and|&)?\s*drop|drag and drop|drag-?n-?drop|drag\s+(folder|message|email))\b', re.I)),
    ('Folder display / disappearance',
     re.compile(r'\b(folder|subfolder|local folder|sent|drafts|inbox)\b.*\b(disappear|missing|gone|empty|invisible|not\s+display|won.?t\s+display)|'
                r'\b(disappear|missing|gone|empty)\b.*\b(folder|subfolder|inbox|sent|drafts)\b', re.I)),
    ('Account auth broke after update',
     re.compile(r'\b(after|since).*(update|upgrade).*\b(password|sign[- ]?in|login|authenticat\w*|account)\b|'
                r'\b(password|sign[- ]?in|login|authenticat\w*)\b.*\b(after|since).*(update|upgrade)\b', re.I)),
    ('Specific version called out',
     re.compile(r'\b(140|149|150|151)\.\d+', re.I)),
]

DATA_LOSS_SUB = [
    ('Folders / subfolders disappeared',
     re.compile(r'\b(folder|subfolder|local folder|inbox|sent|drafts)\b.*\b(disappear|missing|gone|invisible|not\s+display|wiped)\b|'
                r'\b(disappear|missing|gone|wiped|lost)\b.*\b(folder|subfolder|local folder)\b', re.I)),
    ('Emails missing / disappeared',
     re.compile(r'\b(email|emails|message|messages|mail|mails)\b.*\b(disappear|missing|gone|vanish|removed|deleted)\b|'
                r'\b(lost|missing|deleted)\b.*\b(email|emails|message|messages|mail|mails)\b', re.I)),
    ('Recovery / undelete asks',
     re.compile(r'\b(recover\w*|restor\w*|undelete|retriev\w*|get.*back|bring.*back)\b', re.I)),
    ('Expunge / accidental delete',
     re.compile(r'\b(expung\w*|empty.*trash|emptied.*trash|delete.*all|removed by)\b', re.I)),
    ('Profile loss / migration loss',
     re.compile(r'\b(profile)\b.*\b(lost|missing|gone|mia|disappear|not\s+found)\b|'
                r'\b(lost|missing|gone)\b.*\b(profile|account|setup)\b', re.I)),
]


def classify_subthemes(questions, sub_patterns):
    sub_map = defaultdict(list)
    for q in questions:
        text = (q.get('title') or '') + ' ' + (q.get('content') or '')[:400]
        hit = False
        for name, pat in sub_patterns:
            if pat.search(text):
                sub_map[name].append(q)
                hit = True
        if not hit:
            sub_map['Other / unclassified'].append(q)
    return sub_map


from pii_redact import redact_sumo_title


def make_link(qid, title):
    title = redact_sumo_title(title)
    return f'[{qid}](https://support.mozilla.org/questions/{qid} "{title}")'


def provider_breakdown(questions):
    counts = defaultdict(int)
    for q in questions:
        m = PROVIDER_RE.search((q.get('title') or '') + ' ' + (q.get('content') or '')[:300])
        if m:
            counts[m.group(1).lower()] += 1
    return sorted(counts.items(), key=lambda x: -x[1])


def write_theme(f, label, questions, total, sub_patterns, extra_section=None):
    pct = round(100 * len(questions) / total, 1)
    f.write(f'## {label}\n\n')
    f.write(f'**{len(questions)} questions ({pct}% of {total} total April questions)**\n\n')

    if extra_section:
        f.write(extra_section)
        f.write('\n')

    sub_map = classify_subthemes(questions, sub_patterns)
    ranked = sorted(sub_map.items(),
                    key=lambda kv: (kv[0] == 'Other / unclassified', -len(kv[1])))

    f.write('| Sub-theme | Count | Question IDs |\n')
    f.write('|-----------|------:|-------------|\n')
    for name, qs in ranked:
        if not qs:
            continue
        links = ', '.join(make_link(q['id'], q['title']) for q in qs)
        f.write(f'| {name} | {len(qs)} | {links} |\n')
    f.write('\n')


def fetch_questions(year, month):
    import urllib.request
    path = GH_PATH.format(year=year, month=month)
    result = subprocess.run(['gh', 'api', path], capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout)
    if payload.get('content'):
        data = base64.b64decode(payload['content']).decode('utf-8')
    else:
        with urllib.request.urlopen(payload['download_url']) as resp:
            data = resp.read().decode('utf-8', errors='replace')
    return list(csv.DictReader(io.StringIO(data)))


def main(argv):
    if len(argv) != 2:
        print('Usage: desktop_priorities.py <month-name> <year>')
        sys.exit(2)
    month_name = argv[0].lower()
    year = int(argv[1])
    month = MONTHS[month_name]

    print(f'Fetching SUMO desktop questions for {year}-{month:02d}…')
    rows = fetch_questions(year, month)
    total = len(rows)

    auth = [q for q in rows if matches_auth(q)]
    updates = [q for q in rows if matches_update_regression(q)]
    dataloss = [q for q in rows if matches_data_loss(q)]

    overlap_auth_update = [q for q in rows if matches_auth(q) and matches_update_regression(q)]

    out_dir = Path('lisa') / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'{month_name}_desktop_priorities.md'
    csv_path = out_dir / f'{month_name}_desktop_priorities.csv'

    with open(csv_path, 'w', encoding='utf-8', newline='') as cf:
        w = csv.writer(cf)
        w.writerow(['rank', 'theme', 'count', 'percent_of_total'])
        for rank, (label, qs) in enumerate(
            [('Authentication / OAuth fragility', auth),
             ('Update regressions', updates),
             ('Data loss / folder integrity', dataloss)], 1):
            w.writerow([rank, label, len(qs), round(100 * len(qs) / total, 1)])

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f'# Thunderbird Desktop — Community-driven priorities, {year}-{month:02d}\n\n')
        f.write(f'*Part of [{month_name.capitalize()} {year} Monthly Report]({month_name}.md) · '
                f'See also: [SUMO trending topics]({month_name}_sumo_trending.md) · '
                f'[Mozilla Connect ideas]({month_name}_connect_ideas.md)*\n\n')
        f.write(
            f'Three themes drawn from {total} {month_name.capitalize()} SUMO questions. '
            'Questions can appear under more than one theme. Sub-themes inside each theme are '
            'derived from title patterns seen in the data, so counts within a theme are '
            'illustrative (some questions hit multiple sub-themes; some land in "Other"). '
            'The headline theme totals are the load-bearing number.\n\n'
        )

        f.write('## Executive summary\n\n')
        f.write('| Theme | Count | % of all April questions |\n')
        f.write('|-------|------:|-------------------------:|\n')
        f.write(f'| 1. Authentication / OAuth fragility | {len(auth)} | {round(100*len(auth)/total,1)}% |\n')
        f.write(f'| 2. Update regressions               | {len(updates)} | {round(100*len(updates)/total,1)}% |\n')
        f.write(f'| 3. Data loss / folder integrity     | {len(dataloss)} | {round(100*len(dataloss)/total,1)}% |\n')
        f.write(f'\n*Overlap between Auth and Update regressions: {len(overlap_auth_update)} questions — '
                'auth that breaks specifically after an update.*\n\n')

        prov = provider_breakdown(auth)
        provider_md = '**Provider distribution inside Auth/OAuth (top 12):**\n\n'
        provider_md += '| Provider | Count |\n|----------|------:|\n'
        for name, n in prov[:12]:
            provider_md += f'| {name} | {n} |\n'
        write_theme(f, '1. Authentication / OAuth fragility', auth, total,
                    AUTH_SUB, extra_section=provider_md)

        write_theme(f, '2. Update regressions', updates, total, UPDATE_SUB)
        write_theme(f, '3. Data loss / folder integrity', dataloss, total, DATA_LOSS_SUB)

        f.write('---\n\n')
        f.write('*Source: thunderbird-metrics-and-reports SUMO concatenated CSVs. '
                'Generated by `scripts/desktop_priorities.py`.*\n')

    print(f'Wrote {out_path}')
    print(f'\nTotal April questions: {total}')
    print(f'  Theme 1 — Auth/OAuth:        {len(auth):4d}  ({round(100*len(auth)/total,1)}%)')
    print(f'  Theme 2 — Update regressions:{len(updates):4d}  ({round(100*len(updates)/total,1)}%)')
    print(f'  Theme 3 — Data loss/folders: {len(dataloss):4d}  ({round(100*len(dataloss)/total,1)}%)')
    print(f'  Overlap (Auth ∩ Update):     {len(overlap_auth_update):4d}')


if __name__ == '__main__':
    main(sys.argv[1:])
