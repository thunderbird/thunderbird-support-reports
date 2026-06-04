"""
Deep qualitative analysis of March 2026 reviews.
Extracts device names, languages, quotes, and behavioral patterns per friction point.
"""
import csv, re
from pathlib import Path
from collections import Counter

BASE = Path(__file__).parent.parent
TB_CSV  = BASE / 'reviews_reviews_net.thunderbird.android_202604.csv'
K9_CSV  = BASE / 'reviews_reviews_com.fsck.k9_202604.csv'
MONTH   = '2026-04'

THEMES = {
    'Push / Notification Sync':    r'notif|push|sync|synchroni|fetch|delayed|15.min',
    'Crashes & Freezes':           r'crash|absturz|crasha|force.close|freeze|app.*stop|angehalten',
    'Spam Filter Absent':          r'spam|junk|no.*filter|missing.*filter',
    'Calendar Missing':            r'calend|kalend|agenda|ical|caldav',
    'Stuck Outbox / Send Failure': r'outbox|stuck.*send|send.*fail|sending.*error|cannot.*send',
}

WIN_THEMES = {
    'UX satisfaction':      r'beauti|clean|design|easy.to.use|simple|intuitive|well.design|multi.account|love.*ui|great.*app|best.*mail',
    'Open source / no ads': r'open.source|foss|no.*ad|privacy|no.*track',
    'Desktop brand':        r'year[s]?.*(use|using|user)|longtime|long.time|desktop.*mobile|been using.*year',
}

def load_csv(path, label):
    rows = []
    with open(path, encoding='utf-16') as f:
        for row in csv.DictReader(f):
            row['_app']    = label
            row['_rating'] = int(row.get('Star Rating', 0))
            row['_text']   = (row.get('Review Text','') or '').strip()
            row['_lower']  = row['_text'].lower()
            row['_lang']   = row.get('Reviewer Language','')
            row['_device'] = row.get('Device','')
            rows.append(row)
    return rows

DEVICE_RE = re.compile(
    r'\b(samsung|xiaomi|huawei|pixel|oneplus|oppo|motorola|sony|nokia|lg|honor|'
    r's\d{2}|s\d{2}\s*ultra|s\d{2}\s*plus|mi\s*\d|redmi|p\d{2})\b', re.I)

def extract_devices(rows):
    devices = []
    for r in rows:
        # from Device column
        d = r['_device']
        if d: devices.append(d.split(':')[0].strip())
        # from review text
        for m in DEVICE_RE.findall(r['_lower']):
            devices.append(m.upper())
    return Counter(devices).most_common(6)

def top_langs(rows, n=6):
    return Counter(r['_lang'] for r in rows if r['_lang']).most_common(n)

def best_quotes(rows, n=3):
    # pick most informative negative reviews (1-2 star, with text)
    neg = [r for r in rows if r['_rating'] <= 2 and len(r['_text']) > 40]
    neg.sort(key=lambda r: -len(r['_text']))
    return [r['_text'][:200] for r in neg[:n]]

def analyze_theme(all_rows, pattern, name):
    matches  = [r for r in all_rows if re.search(pattern, r['_lower'])]
    neg      = [r for r in matches if r['_rating'] <= 3]
    tb       = [r for r in matches if r['_app'] == 'TB']
    k9       = [r for r in matches if r['_app'] == 'K9']
    avg      = sum(r['_rating'] for r in matches)/len(matches) if matches else 0
    print(f'\n{"─"*60}')
    print(f'THEME: {name}')
    print(f'  {len(matches)} mentions · {len(neg)} negative · avg {avg:.2f}★ · TB:{len(tb)} K9:{len(k9)}')
    print(f'  Top devices: {extract_devices(neg)}')
    print(f'  Top languages: {top_langs(matches)}')
    print(f'\n  Sample negative reviews:')
    for i, q in enumerate(best_quotes(neg), 1):
        print(f'  [{i}] "{q}"')
    # K-9 specific
    if k9:
        print(f'\n  K-9 specifics ({len(k9)} reviews):')
        for r in k9:
            if r['_rating'] <= 3:
                print(f'    [{r["_rating"]}★ · {r["_lang"]} · {r["_device"]}] {r["_text"][:160]}')

def main():
    tb = load_csv(TB_CSV, 'TB')
    k9 = load_csv(K9_CSV, 'K9')
    all_rows = tb + k9

    print('='*60)
    print('DEEP FRICTION ANALYSIS — APRIL 2026')
    print('='*60)
    for name, pattern in THEMES.items():
        analyze_theme(all_rows, pattern, name)

    print(f'\n\n{"="*60}')
    print('WINS — DEEP ANALYSIS')
    print('='*60)
    pos_rows = [r for r in all_rows if r['_rating'] >= 4]
    for name, pattern in WIN_THEMES.items():
        matches = [r for r in pos_rows if re.search(pattern, r['_lower'])]
        avg = sum(r['_rating'] for r in matches)/len(matches) if matches else 0
        print(f'\n── {name}: {len(matches)} mentions · avg {avg:.2f}★')
        print(f'  Languages: {top_langs(matches)}')
        for r in matches[:4]:
            print(f'  [{r["_rating"]}★ · {r["_lang"]} · {r["_app"]}] {r["_text"][:160]}')

    # K-9 churn deep dive
    print(f'\n\n{"="*60}')
    print('K-9 CHURN — DETAILED')
    print('='*60)
    churn_patterns = {
        'FairEmail':      r'fairemail|fair\s*email',
        'Switching away': r'switch.*to|moving.*to|changed.*to|replaced.*with|uninstall|goodbye|giving up',
        '10+ year users': r'(\d{1,2})\s*year[s]?\s*(using|user|ago)',
        'Huawei':         r'huawei|honor',
    }
    for label, pat in churn_patterns.items():
        hits = [r for r in k9 if re.search(pat, r['_lower'])]
        print(f'\n  {label}: {len(hits)} mentions')
        for r in hits:
            print(f'  [{r["_rating"]}★ · {r["_lang"]} · {r["_device"]}] {r["_text"][:200]}')

if __name__ == '__main__':
    main()
