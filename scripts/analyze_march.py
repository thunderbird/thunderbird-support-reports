"""
March 2026 Play Store Review Analysis
Thunderbird Android + K-9 Mail
"""

import csv
import re
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent.parent
TB_CSV = BASE / "reviews_reviews_net.thunderbird.android_202603.csv"
K9_CSV = BASE / "reviews_reviews_com.fsck.k9_202603.csv"

MONTH = "2026-03"

# Historical negative mention counts for 3-month trend (Jan, Feb, March)
HISTORY = {
    'Push / Notification Sync': [19, 23, None],
    'Crashes & Freezes':        [0,  0,  None],
    'Stuck Outbox / Send Failure': [0, 0, None],
    'Spam Filter Absent':       [0,  0,  None],
    'Calendar Missing':         [0,  0,  None],
    'QR / Settings Import':     [0,  0,  None],
    'Email Headers / Print':    [0,  0,  None],
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
    'Privacy / Open Source':   r'privacy|open.source|foss|no.*track|respect.*privacy|open source',
    'Setup / Ease of Use':     r'easy.*setup|easy to use|simple.*setup|quick.*setup|intuitive',
    'Reliability / Stability': r'reliable|stable|solid|works.*great|never.*crash|dependable',
}

K9_CHURN_PATTERNS = {
    'FairEmail mentions': r'fairemail|fair.*email',
    'Switching away':     r'switch.*to|moving.*to|going.*to|changed.*to|replaced.*with|uninstall',
    'Long-term users leaving': r'year[s]?.*(use|using|user)|longtime|long.time|used.*for.*year',
    'Abandonment language': r'goodbye|bye|farewell|last.*review|giving.*up|gave.*up|done.*with|quit',
}


def load_csv(path, app_label):
    rows = []
    with open(path, encoding='utf-16') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row.get('Review Submit Date and Time', '')
            if not date.startswith(MONTH):
                continue
            row['_app'] = app_label
            row['_rating'] = int(row.get('Star Rating', 0))
            row['_text'] = (row.get('Review Text', '') or '').lower()
            row['_has_reply'] = bool(row.get('Developer Reply Text', '').strip())
            rows.append(row)
    return rows


def match_themes(rows, themes):
    results = {}
    for theme, pattern in themes.items():
        matches = [r for r in rows if re.search(pattern, r['_text'])]
        neg = [r for r in matches if r['_rating'] <= 3]
        pos = [r for r in matches if r['_rating'] >= 4]
        tb = [r for r in matches if r['_app'] == 'TB']
        k9 = [r for r in matches if r['_app'] == 'K9']
        avg = sum(r['_rating'] for r in matches) / len(matches) if matches else 0
        results[theme] = {
            'total': len(matches),
            'negative': len(neg),
            'positive': len(pos),
            'avg_rating': round(avg, 2),
            'tb_count': len(tb),
            'k9_count': len(k9),
        }
    return results


def analyze_replies(rows):
    low_star = [r for r in rows if r['_rating'] <= 3]
    replied = [r for r in low_star if r['_has_reply']]
    return len(replied), len(low_star)


def rating_distribution(rows):
    dist = defaultdict(int)
    for r in rows:
        dist[r['_rating']] += 1
    return dict(sorted(dist.items()))


def top_languages(rows, n=10):
    langs = defaultdict(int)
    for r in rows:
        lang = r.get('Reviewer Language', 'unknown') or 'unknown'
        langs[lang] += 1
    return sorted(langs.items(), key=lambda x: -x[1])[:n]


def k9_churn(k9_rows):
    results = {}
    for label, pattern in K9_CHURN_PATTERNS.items():
        matches = [r for r in k9_rows if re.search(pattern, r['_text'])]
        results[label] = {
            'count': len(matches),
            'samples': [r.get('Review Text', '')[:120] for r in matches[:2]],
        }
    # K-9 share of top friction points
    return results


def main():
    tb = load_csv(TB_CSV, 'TB')
    k9 = load_csv(K9_CSV, 'K9')
    all_rows = tb + k9

    print(f"\n{'='*60}")
    print(f"MARCH 2026 — PLAY STORE REVIEW ANALYSIS")
    print(f"{'='*60}")

    # Volume
    print(f"\n## VOLUME")
    print(f"  TB:    {len(tb)} reviews")
    print(f"  K-9:   {len(k9)} reviews")
    print(f"  Total: {len(all_rows)} reviews")

    # Ratings
    tb_avg = sum(r['_rating'] for r in tb) / len(tb) if tb else 0
    k9_avg = sum(r['_rating'] for r in k9) / len(k9) if k9 else 0
    all_avg = sum(r['_rating'] for r in all_rows) / len(all_rows) if all_rows else 0
    print(f"\n## AVERAGE RATINGS")
    print(f"  TB:      {tb_avg:.2f} stars  (Feb: 3.91)")
    print(f"  K-9:     {k9_avg:.2f} stars  (Feb: 3.47)")
    print(f"  Overall: {all_avg:.2f} stars  (Feb: 3.91 TB-only)")

    # Rating distribution
    print(f"\n## RATING DISTRIBUTION")
    for app_label, rows in [('TB', tb), ('K-9', k9), ('Combined', all_rows)]:
        dist = rating_distribution(rows)
        print(f"  {app_label}: " + "  ".join(f"{k}★:{v}" for k,v in dist.items()))

    # Developer replies
    replied, low_total = analyze_replies(all_rows)
    tb_replied, tb_low = analyze_replies(tb)
    k9_replied, k9_low = analyze_replies(k9)
    print(f"\n## DEVELOPER REPLIES (1-3 star)")
    print(f"  Replied: {replied} of {low_total} low-star reviews")
    print(f"  TB:  {tb_replied}/{tb_low}   K-9: {k9_replied}/{k9_low}")

    # Languages
    print(f"\n## TOP LANGUAGES")
    for lang, count in top_languages(all_rows):
        print(f"  {lang}: {count}")
    unique_langs = len(set(r.get('Reviewer Language','') for r in all_rows))
    print(f"  Total unique languages: {unique_langs}")

    # Friction points
    print(f"\n## FRICTION POINTS")
    friction = match_themes(all_rows, THEMES)
    sorted_friction = sorted(friction.items(), key=lambda x: -x[1]['negative'])
    for theme, stats in sorted_friction:
        hist = HISTORY.get(theme, [0, 0, None])
        hist[2] = stats['negative']
        trend = ' → '.join(str(x) for x in hist)
        print(f"\n  [{theme}]")
        print(f"    Total: {stats['total']}  Neg: {stats['negative']}  Avg: {stats['avg_rating']}★")
        print(f"    TB: {stats['tb_count']}  K-9: {stats['k9_count']}")
        print(f"    3-month neg trend: {trend}")

    # Top 3 friction points
    top3 = sorted_friction[:3]
    print(f"\n## TOP 3 FRICTION POINTS (by negative mentions)")
    for i, (theme, stats) in enumerate(top3, 1):
        print(f"  {i}. {theme} — {stats['negative']} negative mentions")

    # Wins
    print(f"\n## WINS (positive themes in 4-5 star reviews)")
    pos_rows = [r for r in all_rows if r['_rating'] >= 4]
    wins = match_themes(pos_rows, WIN_THEMES)
    sorted_wins = sorted(wins.items(), key=lambda x: -x[1]['total'])
    for theme, stats in sorted_wins:
        print(f"  [{theme}]  Total: {stats['total']}  Avg: {stats['avg_rating']}★  TB:{stats['tb_count']} K9:{stats['k9_count']}")

    # K-9 churn signals
    print(f"\n## K-9 CHURN SIGNALS")
    churn = k9_churn(k9)
    for label, data in churn.items():
        print(f"  {label}: {data['count']} mentions")
        for s in data['samples']:
            print(f"    → \"{s}\"")

    # K-9 share of friction
    print(f"\n## K-9 SHARE OF TOP FRICTION POINTS")
    for theme, stats in top3:
        if stats['total'] > 0:
            pct = stats['k9_count'] / stats['total'] * 100
            print(f"  {theme}: K-9 = {stats['k9_count']}/{stats['total']} ({pct:.0f}%)")

    # Save JSON for dashboard/CSV generation
    output = {
        'month': 'March',
        'year': 2026,
        'tb_count': len(tb),
        'k9_count': len(k9),
        'total_count': len(all_rows),
        'tb_avg_rating': round(tb_avg, 2),
        'k9_avg_rating': round(k9_avg, 2),
        'overall_avg_rating': round(all_avg, 2),
        'replies_to_low_star': replied,
        'total_low_star': low_total,
        'unique_languages': unique_langs,
        'rating_dist_tb': rating_distribution(tb),
        'rating_dist_k9': rating_distribution(k9),
        'friction': {k: v for k, v in friction.items()},
        'wins': {k: v for k, v in wins.items()},
        'k9_churn': {k: v['count'] for k, v in churn.items()},
    }
    out_path = BASE / 'lisa' / '2026' / 'march_analysis.json'
    out_path.write_text(json.dumps(output, indent=2))
    print(f"\n✓ Analysis saved to {out_path}")


if __name__ == '__main__':
    main()
