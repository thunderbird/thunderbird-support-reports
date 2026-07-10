#!/usr/bin/env python3
"""
Generate a SUMO trending-topics report for Thunderbird Desktop.

Pulls the monthly questions CSV from Roland's repo
(thunderbird/thunderbird-metrics-and-reports) and rolls SUMO tags up into
topic buckets. A question can fall in multiple buckets. Environment-only
tags (OS, version) are ignored. Untagged questions get a small title-regex
fallback; remaining ones go to "Uncategorized".

Usage:
    uv run scripts/sumo_trending.py <month-name> <year>
    uv run scripts/sumo_trending.py april 2026

Outputs (written to lisa/<year>/):
    <month>_sumo_trending.md
    <month>_sumo_trending.csv
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

TAG_BUCKETS = {
    'Send/Receive issues': [
        'send-and-receive-email', 'connectivity', 'performance-and-connectivity',
    ],
    'Sign-in & Passwords': [
        'passwords-and-sign-in', 'reset-passwords', 'save-passwords',
    ],
    'Account setup & management': ['account-management', 'accounts', 'settings'],
    'Spam & Junk mail': ['junk-mail-and-spam'],
    'Import / Migration / Profiles': [
        'import-and-export-email', 'import-and-export-settings', 'profiles',
    ],
    'Calendar & Events': ['calendar', 'events'],
    'Crashes & Performance': [
        'crashing-and-slow-performance', 'app-crash', 'performance',
    ],
    'Install & Update': ['installation-and-updates', 'install', 'update'],
    'Customization & UI': ['customization'],
    'Attachments': ['attachments'],
    'Contacts / Address Book': ['contacts'],
    'Search & Tags': ['search', 'tags'],
    'Security & Encryption': ['security', 'encryption'],
    'Accessibility': ['accessibility'],
    'Extensions & Add-ons': ['extensions'],
    'General messaging (broad tag)': ['email-and-messaging'],
}

NON_TOPIC_TAGS = {
    'thunderbird', 'windows-11', 'windows-10', 'windows-1011', 'windows-7',
    'windows-81', 'windows', 'linux', 'android', 'mac-os-x-1015',
    'mac-os-x-1013', 'needsinfo', 'undefined', 'languages',
    'firefox-1490', 'firefox-14902', 'firefox-1500',
    'thunderbird-1500', 'thunderbird-1400', 'thunderbird-140100',
    'thunderbird-14010',
}

TITLE_FALLBACKS = [
    ('Donations & Billing',
     re.compile(r'\b(donat\w*|subscription|abonnement|nyugta|számla|kvitt\w*|recibo|ricevuta|billing|refund)\b', re.I)),
    ('Spam & Junk mail',
     re.compile(r'\b(illuminati|occult|join.*money|join.*power)\b', re.I)),
]


def classify(question):
    tags = {t.strip().lower() for t in (question.get('tags') or '').split(';') if t.strip()}
    tags -= NON_TOPIC_TAGS

    buckets = set()
    for bucket, tag_list in TAG_BUCKETS.items():
        if tags & set(tag_list):
            buckets.add(bucket)

    if not buckets:
        title = question.get('title') or ''
        for bucket, pattern in TITLE_FALLBACKS:
            if pattern.search(title):
                buckets.add(bucket)

    if not buckets:
        buckets.add('Uncategorized')

    return buckets


from pii_redact import redact_sumo_title


def make_link(qid, title):
    title = redact_sumo_title(title)
    return f'[{qid}](https://support.mozilla.org/questions/{qid} "{title}")'


def fetch_questions(year, month):
    import urllib.request
    path = GH_PATH.format(year=year, month=month)
    result = subprocess.run(
        ['gh', 'api', path],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get('content'):
        data = base64.b64decode(payload['content']).decode('utf-8')
    else:
        with urllib.request.urlopen(payload['download_url']) as resp:
            data = resp.read().decode('utf-8', errors='replace')
    return list(csv.DictReader(io.StringIO(data)))


def write_reports(rows, year, month, month_name):
    total = len(rows)
    bucket_qs = defaultdict(list)
    for r in rows:
        for b in classify(r):
            bucket_qs[b].append(r)

    ranked = sorted(bucket_qs.items(), key=lambda kv: len(kv[1]), reverse=True)

    out_dir = Path('lisa') / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f'{month_name}_sumo_trending.md'
    csv_path = out_dir / f'{month_name}_sumo_trending.csv'

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f'# Thunderbird Desktop — SUMO trending topics, {year}-{month:02d}\n\n')
        f.write(f'*Part of [{month_name.capitalize()} {year} Monthly Report]({month_name}.md) · '
                f'See also: [Desktop priorities drill-down]({month_name}_desktop_priorities.md) · '
                f'[Mozilla Connect ideas]({month_name}_connect_ideas.md)*\n\n')
        f.write(f'**Total questions analyzed:** {total} (all locales)  \n')
        f.write('**Source:** thunderbird-metrics-and-reports concatenated questions CSV  \n')
        f.write('**Method:** SUMO tags rolled up into topic buckets; environment-only tags '
                '(OS, version) ignored; untagged questions get a small title-regex fallback. '
                'Questions can appear in more than one topic.\n\n')
        f.write('| Rank | Topic | Count | % of total | Question IDs |\n')
        f.write('|-----:|-------|------:|-----------:|-------------|\n')
        for i, (bucket, qs) in enumerate(ranked, 1):
            pct = round(100 * len(qs) / total, 1)
            links = ', '.join(make_link(q['id'], q['title']) for q in qs)
            f.write(f'| {i} | {bucket} | {len(qs)} | {pct}% | {links} |\n')

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rank', 'topic', 'count', 'percent_of_total', 'question_ids'])
        for i, (bucket, qs) in enumerate(ranked, 1):
            pct = round(100 * len(qs) / total, 1)
            ids = ';'.join(q['id'] for q in qs)
            w.writerow([i, bucket, len(qs), pct, ids])

    print(f'Wrote {md_path}')
    print(f'Wrote {csv_path}')
    print(f'\nTotal questions: {total}')
    for i, (bucket, qs) in enumerate(ranked, 1):
        pct = round(100 * len(qs) / total, 1)
        print(f'  {i:2d}. {bucket:40s} {len(qs):4d}  ({pct}%)')


def main(argv):
    if len(argv) != 2:
        print('Usage: sumo_trending.py <month-name> <year>')
        sys.exit(2)
    month_name = argv[0].lower()
    year = int(argv[1])
    if month_name not in MONTHS:
        print(f'Unknown month: {month_name}')
        sys.exit(2)
    month = MONTHS[month_name]

    print(f'Fetching SUMO desktop questions for {year}-{month:02d}…')
    rows = fetch_questions(year, month)
    write_reports(rows, year, month, month_name)


if __name__ == '__main__':
    main(sys.argv[1:])
