#!/usr/bin/env python3
"""
Pull Mozilla Connect ideas tagged with the 'thunderbird' label for a month.

Mozilla Connect uses the Khoros LiQL JSON API; it's unauthenticated but
requires a browser User-Agent. Every Thunderbird-labeled post lands in the
'ideas' board, so this gives us the community wishlist signal (kudos =
upvotes, status = product team disposition).

Usage:
    python3 scripts/connect_thunderbird.py <month-name> <year>
    python3 scripts/connect_thunderbird.py april 2026

Outputs:
    lisa/<year>/<month>_connect_ideas.md
    lisa/<year>/<month>_connect_ideas.csv
"""

import calendar
import csv
import json
import subprocess
import sys
import urllib.parse
from pathlib import Path

MONTHS = {
    'january': 1, 'february': 2, 'march': 3, 'april': 4,
    'may': 5, 'june': 6, 'july': 7, 'august': 8,
    'september': 9, 'october': 10, 'november': 11, 'december': 12,
}

API_BASE = 'https://connect.mozilla.org/api/2.0/search'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15'

LIQL_TEMPLATE = (
    "SELECT id, subject, view_href, kudos.sum(weight), post_time, "
    "conversation.messages_count, conversation.last_post_time, "
    "metrics.views, status "
    "FROM messages "
    "WHERE labels.text = 'thunderbird' "
    "AND post_time > {start}T00:00:00.000-00:00 "
    "AND post_time < {end}T00:00:00.000-00:00"
)


def month_bounds(year, month):
    start = f'{year:04d}-{month:02d}-01'
    last_day = calendar.monthrange(year, month)[1]
    end_day = last_day + 1
    if end_day > last_day:
        if month == 12:
            end = f'{year+1:04d}-01-01'
        else:
            end = f'{year:04d}-{month+1:02d}-01'
    else:
        end = f'{year:04d}-{month:02d}-{end_day:02d}'
    return start, end


def fetch_ideas(year, month):
    start, end = month_bounds(year, month)
    liql = LIQL_TEMPLATE.format(start=start, end=end)
    qs = urllib.parse.urlencode({'q': liql, 'restapi.response_format': 'json'})
    url = f'{API_BASE}?{qs}'
    result = subprocess.run(
        ['curl', '-sS', '-H', f'User-Agent: {UA}', url],
        capture_output=True, text=True, check=True,
    )
    payload = json.loads(result.stdout)
    if payload.get('status') != 'success':
        raise RuntimeError(f'API error: {payload}')
    return payload['data']['items']


def kudos(item):
    return item.get('kudos', {}).get('sum', {}).get('weight', 0) or 0


def views(item):
    m = item.get('metrics') or {}
    return m.get('views', 0) or 0


def comments(item):
    c = item.get('conversation') or {}
    return c.get('messages_count', 0) or 0


def status_key(item):
    s = item.get('status') or {}
    return s.get('key') or s.get('name') or 'new'


def write_reports(items, year, month, month_name):
    ranked = sorted(items, key=lambda x: -kudos(x))
    total = len(ranked)
    total_kudos = sum(kudos(i) for i in ranked)
    total_views = sum(views(i) for i in ranked)
    status_counts = {}
    for i in ranked:
        s = status_key(i)
        status_counts[s] = status_counts.get(s, 0) + 1

    out_dir = Path('lisa') / str(year)
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / f'{month_name}_connect_ideas.md'
    csv_path = out_dir / f'{month_name}_connect_ideas.csv'

    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f'# Thunderbird — Mozilla Connect ideas, {year}-{month:02d}\n\n')
        f.write(f'*Part of [{month_name.capitalize()} {year} Monthly Report]({month_name}.md) · '
                f'See also: [SUMO trending topics]({month_name}_sumo_trending.md) · '
                f'[Desktop priorities drill-down]({month_name}_desktop_priorities.md)*\n\n')
        f.write(f'**Total Thunderbird-labeled ideas posted:** {total}  \n')
        f.write(f'**Total kudos (upvotes):** {total_kudos}  \n')
        f.write(f'**Total views:** {total_views:,}  \n')
        f.write(f'**Status mix:** {", ".join(f"{n} {s}" for s, n in sorted(status_counts.items(), key=lambda x: -x[1]))}\n\n')
        f.write('Mozilla Connect is the product feedback / ideation channel. '
                'Every Thunderbird-labeled post lands in the *ideas* board, so this is '
                'the community wishlist (what users want), complementing the SUMO forum '
                'signal (what users are blocked on).\n\n')
        f.write('| Rank | Kudos | Views | Comments | Status | Idea |\n')
        f.write('|-----:|------:|------:|---------:|--------|------|\n')
        for i, item in enumerate(ranked, 1):
            title = (item.get('subject') or '').replace('|', '¦')
            href = item.get('view_href', '')
            f.write(f'| {i} | {kudos(item)} | {views(item):,} | {comments(item)} | '
                    f'{status_key(item)} | [{title}]({href}) |\n')

    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(['rank', 'kudos', 'views', 'comments', 'status', 'subject', 'url', 'post_time'])
        for i, item in enumerate(ranked, 1):
            w.writerow([
                i, kudos(item), views(item), comments(item),
                status_key(item),
                item.get('subject', ''),
                item.get('view_href', ''),
                item.get('post_time', ''),
            ])

    print(f'Wrote {md_path}')
    print(f'Wrote {csv_path}')
    print(f'\nTotal ideas: {total}  |  kudos: {total_kudos}  |  views: {total_views:,}')
    print(f'Top 5:')
    for item in ranked[:5]:
        title = (item.get('subject') or '')[:70]
        print(f'  k={kudos(item):3d}  v={views(item):5d}  {status_key(item):12s}  {title}')


def main(argv):
    if len(argv) != 2:
        print('Usage: connect_thunderbird.py <month-name> <year>')
        sys.exit(2)
    month_name = argv[0].lower()
    year = int(argv[1])
    if month_name not in MONTHS:
        print(f'Unknown month: {month_name}')
        sys.exit(2)
    month = MONTHS[month_name]
    print(f'Fetching Mozilla Connect Thunderbird ideas for {year}-{month:02d}…')
    items = fetch_ideas(year, month)
    write_reports(items, year, month, month_name)


if __name__ == '__main__':
    main(sys.argv[1:])
