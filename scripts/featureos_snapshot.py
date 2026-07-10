"""
FeatureOS Thundermail idea status snapshots for month-over-month diffing.

Used by generate.py on each run. Can also backfill a month standalone:

  uv run scripts/featureos_snapshot.py 2026-06
"""
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

FEATUREOS_QUERY = 'sort=votes_count&order=desc&per_page=100&status=all'
IDEA_URL = 'https://ideas.tb.pro/p/{slug}'

DEFAULT_STATUS_CAVEAT = (
    'FeatureOS exposes created_at and updated_at only — no status-change audit log. '
    'Dates reflect last board activity or submission; vote/comment edits also bump updated_at. '
    'Automated moves compare monthly snapshots; append quarterly review entries via '
    'status_moves_manual in YAML.'
)


def prior_month_prefix(month_prefix):
    """Return YYYY-MM for the calendar month before month_prefix."""
    year, month = month_prefix.split('-')
    year, month = int(year), int(month)
    month -= 1
    if month == 0:
        month = 12
        year -= 1
    return f'{year}-{month:02d}'


def fetch_featureos_ideas():
    """Fetch board 17437 via featureos-cli; return normalized idea dicts."""
    try:
        proc = subprocess.run(
            ['featureos-cli', 'posts', 'list', '--query', FEATUREOS_QUERY, '--json'],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError:
        print('  FeatureOS: featureos-cli not found (skipping snapshot)', file=sys.stderr)
        return None
    except subprocess.CalledProcessError as exc:
        print(f'  FeatureOS: CLI failed — {exc.stderr or exc}', file=sys.stderr)
        return None

    raw = proc.stdout.strip()
    if raw.startswith('\r'):
        raw = raw.lstrip('\r\n')
    data = json.loads(raw)
    posts = data.get('feature_requests', [])
    posts.sort(key=lambda p: p.get('votes_count') or 0, reverse=True)

    ideas = []
    for post in posts:
        slug = post.get('slug') or ''
        if not slug:
            continue
        custom = post.get('custom_status') or {}
        status = custom.get('title') if isinstance(custom, dict) else None
        ideas.append({
            'slug': slug,
            'title': post.get('title') or slug,
            'votes': int(post.get('votes_count') or 0),
            'status': status,
            'updated_at': post.get('updated_at') or '',
        })
    return ideas


def diff_status_moves(current, prior):
    """Compare two idea lists by slug; return move dicts for status changes."""
    prior_by_slug = {i['slug']: i for i in (prior or [])}
    moves = []
    for idea in current or []:
        slug = idea['slug']
        old = prior_by_slug.get(slug)
        if not old or old.get('status') == idea.get('status'):
            continue
        date = (idea.get('updated_at') or '')[:10]
        moves.append({
            'date': date,
            'status': idea.get('status') or '',
            'title': idea.get('title') or slug,
            'votes': idea.get('votes', 0),
            'url': IDEA_URL.format(slug=slug),
            'note': f'was {old.get("status") or "—"} (snapshot diff)',
        })
    moves.sort(key=lambda m: m.get('date', ''), reverse=True)
    return moves


def _move_key(move):
    return (move.get('url') or move.get('title'), move.get('status'), move.get('date'))


def _move_duplicate(candidate, existing):
    key = _move_key(candidate)
    return any(_move_key(m) == key for m in existing)


def resolve_status_moves(ideas_config, auto_moves, has_prior_snapshot):
    """
    Build the status_moves block for the dashboard.

    No prior snapshot (e.g. June baseline): keep YAML status_moves unchanged.
    With prior snapshot: auto diff + optional status_moves_manual from YAML.
    """
    yaml_block = ideas_config.get('status_moves') or {}
    manual_block = ideas_config.get('status_moves_manual') or {}

    if not has_prior_snapshot:
        if yaml_block.get('moves'):
            return yaml_block
        return None

    moves = list(auto_moves or [])
    for m in manual_block.get('moves', []):
        if not _move_duplicate(m, moves):
            moves.append(m)

    if not moves:
        return None

    caveat = manual_block.get('caveat') or yaml_block.get('caveat') or DEFAULT_STATUS_CAVEAT
    moves.sort(key=lambda m: m.get('date', ''), reverse=True)
    return {'caveat': caveat, 'moves': moves}


def capture_featureos_snapshot(base, month_prefix, ideas=None, captured_at=None):
    """
    Fetch (if needed) and store ideas under history['featureos_status'][month_prefix].
    Returns (history, ideas, captured_at) or (history, None, None) on fetch failure.
    """
    path = Path(base) / 'data' / 'history.json'
    history = json.loads(path.read_text()) if path.exists() else {}

    if ideas is None:
        ideas = fetch_featureos_ideas()
    if ideas is None:
        return history, None, None

    ts = captured_at or datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace('+00:00', 'Z')
    block = history.setdefault('featureos_status', {})
    block[month_prefix] = {
        'captured_at': ts,
        'ideas': ideas,
    }
    _write_history(path, history)
    return history, ideas, ts


def prior_featureos_snapshot(history, month_prefix):
    """Return prior month's idea list from featureos_status, or None."""
    prior_key = prior_month_prefix(month_prefix)
    return (history.get('featureos_status') or {}).get(prior_key, {}).get('ideas')


def _write_history(path, history):
    month_keys = sorted(k for k in history if re.match(r'^\d{4}-\d{2}$', k))
    other_keys = sorted(k for k in history if k not in month_keys)
    ordered = {k: history[k] for k in month_keys + other_keys}
    path.write_text(json.dumps(ordered, indent=2) + '\n')


def main():
    if len(sys.argv) != 2 or not re.match(r'^\d{4}-\d{2}$', sys.argv[1]):
        sys.exit('Usage: uv run scripts/featureos_snapshot.py YYYY-MM')

    month_prefix = sys.argv[1]
    base = Path(__file__).resolve().parent.parent
    history, ideas, ts = capture_featureos_snapshot(base, month_prefix)
    if ideas is None:
        sys.exit(1)
    print(f'✓ FeatureOS snapshot: {month_prefix} — {len(ideas)} ideas at {ts}')


if __name__ == '__main__':
    main()
