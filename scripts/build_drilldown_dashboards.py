#!/usr/bin/env python3
"""Build Thunderbird-brand drill-down DASHBOARDS from the monthly source-report markdown.

Turns the three flat "full report" markdown files into interactive light-mode dashboards
that follow the thunderbird.net / Bolt look & feel (Bolt tokens per DESIGN.md):

  lisa/2026/<month>_sumo_trending.md       -> <month>_sumo_trending.html
  lisa/2026/<month>_desktop_priorities.md  -> <month>_desktop_priorities.html
  lisa/2026/<month>_connect_ideas.md       -> <month>_connect_ideas.html

Design prototype — additive drill-downs. Does NOT touch generate.py, june.html, or any gated file.

Usage:  uv run scripts/build_drilldown_dashboards.py [month]
        uv run scripts/build_drilldown_dashboards.py june
"""
import re, html, json, sys
from pathlib import Path

from pii_redact import redact_sumo_title

BASE = Path(__file__).resolve().parent.parent / "lisa" / "2026"
MONTH = (sys.argv[1] if len(sys.argv) > 1 else "june").lower()
MONTH_LABEL = MONTH.capitalize()
LINK_RE = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+?)(?:\s+"([^"]*)")?\)')


# ── markdown helpers ────────────────────────────────────────────────────────
def table_rows(block_lines):
    """Parse a markdown table (lines starting with |) into a list of cell-lists."""
    rows = []
    for ln in block_lines:
        s = ln.strip()
        if not s.startswith('|'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if all(c and set(c) <= set('-: ') for c in cells):  # separator row
            continue
        rows.append(cells)
    return rows


def cell_links(cell):
    """Return [{'id','url','title'}] for every markdown link in a cell."""
    out = []
    for m in LINK_RE.finditer(cell):
        out.append({"text": m.group(1), "url": m.group(2), "title": m.group(3) or ""})
    return out


def esc(s):
    return html.escape(s or "", quote=True)


# ── shared chrome (Thunderbird-brand light) ─────────────────────────────────
HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script>(function(){{var t=localStorage.getItem('tb-theme')||'dark';if(t==='dark')document.documentElement.classList.add('dark');}})();</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/@phosphor-icons/web@2.1.1"></script>
<style>
/* ============================================================================
   CSS REGION: tokens — Thunderbird brand (light) · Bolt semantic tokens (DESIGN.md)
   thunderbird.net look: light, spacious, soft shadows, Thunderbird blue + teal.
   ============================================================================ */
:root{{
  --surface-page:#f5f6fb;
  --surface-card:#ffffff;
  --surface-sunken:#eef1f8;
  --border:#e4e6f0;
  --border-strong:#d2d5e4;
  --primary:#1373d9;            /* Thunderbird blue — links / active / accents */
  --primary-strong:#105399;     /* deeper blue — headings, hovered links */
  --primary-soft:#eaf3fd;
  --teal:#1a9c95;               /* Thunderbird teal — attention/accent */
  --teal-soft:#e6f6f4;
  --text:#16161e;
  --text-secondary:#494b5c;
  --text-muted:#73758a;
  --text-faint:#9a9cb0;
  /* Bolt semantic (light) — from DESIGN.md */
  --success:#194e2c; --success-c:#f4f9f4;
  --warning:#713f12; --warning-c:#fefae8;
  --error:#7f1d1d;   --error-c:#fef2f2;
  --info:#004f9b;    --info-c:#f0f8ff;
  /* spacing (4px base) */
  --s4:.25rem; --s8:.5rem; --s12:.75rem; --s16:1rem; --s24:1.5rem; --s32:2rem; --s48:3rem;
  --radius-sm:8px; --radius-md:12px; --radius-lg:16px;
  --shadow-sm:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.10);
  --shadow-md:0 4px 12px rgba(16,24,40,.08),0 2px 4px rgba(16,24,40,.06);
}}
/* CSS REGION: dark theme — Bolt dark tokens; default for these dashboards (team norm) */
html.dark{{
  --surface-page:#0d0c14; --surface-card:#15131e; --surface-sunken:#1c1a28;
  --border:#2b2845; --border-strong:#3e3b62;
  --primary:#6d8bff; --primary-strong:#9db4ff; --primary-soft:#0e1038;
  --teal:#2dd4bf; --teal-soft:#04201d;
  --text:#e8e6f5; --text-secondary:#b4b1d0; --text-muted:#8a87a6; --text-faint:#5d5a78;
  --success:#34d27b; --success-c:#06210f;
  --warning:#f5a623; --warning-c:#1f1500;
  --error:#ff5a5a;   --error-c:#270808;
  --info:#6d8bff;    --info-c:#0e1038;
  --shadow-sm:0 1px 2px rgba(0,0,0,.45); --shadow-md:0 6px 16px rgba(0,0,0,.5);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:var(--surface-page);color:var(--text);font-family:'Inter',system-ui,sans-serif;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:var(--primary);text-decoration:none}}
a:hover{{color:var(--primary-strong);text-decoration:underline}}
a:focus-visible,button:focus-visible,summary:focus-visible,input:focus-visible{{outline:2px solid var(--primary);outline-offset:2px;border-radius:4px}}

/* topbar */
.topbar{{background:var(--surface-card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:20}}
.topbar__in{{max-width:1080px;margin:0 auto;padding:var(--s12) var(--s32);display:flex;align-items:center;gap:var(--s16)}}
.brand{{display:flex;align-items:center;gap:var(--s8);font-weight:700;color:var(--text);font-size:.95rem}}
.brand:hover{{text-decoration:none;color:var(--text)}}
.brand svg{{width:26px;height:26px}}
.crumbs{{margin-left:auto;font-size:.8rem;color:var(--text-muted)}}
.crumbs a{{color:var(--text-muted)}}
.crumbs b{{color:var(--text-secondary);font-weight:600}}
.theme-toggle{{background:var(--surface-sunken);border:1px solid var(--border);color:var(--text-secondary);border-radius:999px;width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.05rem;flex-shrink:0}}
.theme-toggle:hover{{color:var(--text);border-color:var(--border-strong)}}
.theme-toggle .ph-sun{{display:none}}
html.dark .theme-toggle .ph-moon{{display:none}}
html.dark .theme-toggle .ph-sun{{display:inline}}

.wrap{{max-width:1080px;margin:0 auto;padding:var(--s32)}}
@media(max-width:640px){{.wrap,.topbar__in{{padding-left:var(--s16);padding-right:var(--s16)}}}}

/* page head */
.page-head{{margin-bottom:var(--s32)}}
.eyebrow{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--primary);margin-bottom:var(--s8);display:flex;align-items:center;gap:var(--s8)}}
.page-head h1{{font-size:clamp(1.7rem,4vw,2.4rem);font-weight:700;letter-spacing:-.02em;line-height:1.1;margin-bottom:var(--s12)}}
.dek{{font-size:1rem;color:var(--text-secondary);line-height:1.65;max-width:70ch}}
.meta-pills{{display:flex;flex-wrap:wrap;gap:var(--s8);margin-top:var(--s16)}}
.pill{{background:var(--surface-card);border:1px solid var(--border);border-radius:999px;padding:var(--s4) var(--s12);font-size:.78rem;font-weight:600;color:var(--text-secondary);box-shadow:var(--shadow-sm)}}
.pill i{{color:var(--primary);margin-right:4px}}

/* stat row */
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--s16);margin-bottom:var(--s24)}}
.stat{{background:var(--surface-card);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--s16) var(--s24);box-shadow:var(--shadow-sm)}}
.stat__val{{font-size:2rem;font-weight:700;letter-spacing:-.02em;line-height:1;font-variant-numeric:tabular-nums}}
.stat__lbl{{font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);margin-top:var(--s8)}}
.stat--primary .stat__val{{color:var(--primary-strong)}}
.stat--teal .stat__val{{color:var(--teal)}}

/* card */
.card{{background:var(--surface-card);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm);margin-bottom:var(--s24);overflow:hidden}}
.card__head{{padding:var(--s24) var(--s24) var(--s12);display:flex;align-items:baseline;justify-content:space-between;gap:var(--s12);flex-wrap:wrap}}
.card__title{{font-size:1.05rem;font-weight:700;letter-spacing:-.01em}}
.card__sub{{font-size:.8rem;color:var(--text-muted)}}
.card__body{{padding:0 var(--s24) var(--s24)}}
.chart-box{{padding:var(--s16) var(--s24) var(--s24);position:relative;min-height:280px}}

/* search */
.toolbar{{display:flex;gap:var(--s12);align-items:center;margin-bottom:var(--s16);flex-wrap:wrap}}
.search{{flex:1;min-width:220px;position:relative}}
.search i{{position:absolute;left:12px;top:50%;transform:translateY(-50%);color:var(--text-faint)}}
.search input{{width:100%;padding:var(--s12) var(--s12) var(--s12) 38px;border:1px solid var(--border-strong);border-radius:var(--radius-sm);font:inherit;font-size:.9rem;background:var(--surface-card);color:var(--text)}}
.search input::placeholder{{color:var(--text-faint)}}
.count-note{{font-size:.8rem;color:var(--text-muted)}}

/* topic rows (expandable) */
.topic{{border:1px solid var(--border);border-radius:var(--radius-md);margin-bottom:var(--s12);background:var(--surface-card);box-shadow:var(--shadow-sm);overflow:hidden}}
.topic > summary{{list-style:none;cursor:pointer;padding:var(--s16);display:grid;grid-template-columns:auto 1fr auto;gap:var(--s16);align-items:center}}
.topic > summary::-webkit-details-marker{{display:none}}
.topic__rank{{font-size:.85rem;font-weight:700;color:var(--text-faint);font-variant-numeric:tabular-nums;width:1.5rem;text-align:right}}
.topic__main{{min-width:0}}
.topic__name{{font-weight:700;font-size:.95rem;display:flex;align-items:center;gap:var(--s8)}}
.topic__name .caret{{color:var(--text-faint);transition:transform .15s}}
.topic[open] .topic__name .caret{{transform:rotate(90deg)}}
.topic__bar-wrap{{height:8px;background:var(--surface-sunken);border-radius:999px;margin-top:var(--s8);overflow:hidden;max-width:520px}}
.topic__bar{{height:100%;border-radius:999px;background:linear-gradient(90deg,var(--primary),var(--teal))}}
.topic__fig{{text-align:right;white-space:nowrap}}
.topic__count{{font-size:1.25rem;font-weight:700;font-variant-numeric:tabular-nums;line-height:1}}
.topic__pct{{font-size:.74rem;color:var(--text-muted);font-variant-numeric:tabular-nums}}
.topic__qs{{padding:0 var(--s16) var(--s16);border-top:1px solid var(--border)}}
.q-list{{list-style:none;display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:var(--s4) var(--s16);margin-top:var(--s12)}}
.q-list li{{font-size:.84rem;line-height:1.5;padding:var(--s4) 0;border-bottom:1px solid var(--surface-sunken)}}
.q-list li a{{color:var(--text-secondary)}}
.q-list li a:hover{{color:var(--primary-strong)}}
.q-id{{font-size:.72rem;color:var(--text-faint);font-variant-numeric:tabular-nums;margin-right:6px}}

/* tables */
table{{width:100%;border-collapse:collapse;font-size:.88rem}}
th{{text-align:left;color:var(--text-muted);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;padding:var(--s8) var(--s12);border-bottom:2px solid var(--border-strong);cursor:pointer;user-select:none;white-space:nowrap}}
th .so{{display:inline-flex;align-items:center;gap:4px}}
th .so i{{color:var(--text-faint);font-size:.9em}}
td{{padding:var(--s8) var(--s12);border-bottom:1px solid var(--border);vertical-align:top}}
tbody tr:hover{{background:var(--surface-sunken)}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.tag{{display:inline-block;font-size:.7rem;font-weight:600;padding:1px 8px;border-radius:999px;background:var(--info-c);color:var(--info);border:1px solid var(--info)}}
.kudos{{font-weight:700;color:var(--primary-strong);font-variant-numeric:tabular-nums}}

/* theme cards (priorities) */
.theme{{border:1px solid var(--border);border-left:4px solid var(--accent,var(--primary));border-radius:var(--radius-md);background:var(--surface-card);box-shadow:var(--shadow-sm);margin-bottom:var(--s16);overflow:hidden}}
.theme > summary{{list-style:none;cursor:pointer;padding:var(--s24);display:grid;grid-template-columns:1fr auto;gap:var(--s16);align-items:center}}
.theme > summary::-webkit-details-marker{{display:none}}
.theme__name{{font-size:1.1rem;font-weight:700;display:flex;align-items:center;gap:var(--s8)}}
.theme__name .caret{{color:var(--text-faint);transition:transform .15s}}
.theme[open] .theme__name .caret{{transform:rotate(90deg)}}
.theme__desc{{font-size:.85rem;color:var(--text-muted);margin-top:var(--s4)}}
.theme__fig{{text-align:right;white-space:nowrap}}
.theme__count{{font-size:1.6rem;font-weight:700;color:var(--accent,var(--primary));line-height:1;font-variant-numeric:tabular-nums}}
.theme__pct{{font-size:.78rem;color:var(--text-muted)}}
.theme__body{{padding:0 var(--s24) var(--s24);border-top:1px solid var(--border)}}
.subhead{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.06em;color:var(--text-muted);margin:var(--s16) 0 var(--s8)}}
.mini-bars{{display:flex;flex-direction:column;gap:6px;max-width:420px}}
.mini-row{{display:grid;grid-template-columns:120px 32px 1fr;align-items:center;gap:var(--s8);font-size:.82rem}}
.mini-row__bar{{height:7px;background:var(--teal);border-radius:999px;opacity:.8}}

.footer{{font-size:.78rem;color:var(--text-muted);line-height:1.6;border-top:1px solid var(--border);padding-top:var(--s16);margin-top:var(--s32)}}
.proto{{background:var(--info-c);border:1px solid var(--info);color:var(--info);border-radius:var(--radius-sm);padding:var(--s8) var(--s16);font-size:.78rem;margin-bottom:var(--s24)}}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar__in">
    <a class="brand" href="june_sample.html">
      <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <circle cx="16" cy="16" r="15" fill="#1373d9"/>
        <path d="M8 13h16M8 17h11M8 21h7" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
      </svg>
      Thunderbird Support
    </a>
    <nav class="crumbs"><a href="june_sample.html">Monthly Report</a> &rsaquo; <b>{crumb}</b></nav>
    <button class="theme-toggle" onclick="localStorage.setItem('tb-theme',document.documentElement.classList.contains('dark')?'light':'dark');location.reload();" aria-label="Toggle light / dark theme" title="Toggle light / dark"><i class="ph ph-moon"></i><i class="ph ph-sun"></i></button>
  </div>
</header>
<main class="wrap">
<div class="proto"><b>Drill-down dashboard prototype</b> — generated from {source}. Brand: thunderbird.net + Bolt (light). Data: {month_label} 2026.</div>
"""

FOOT = """
<div class="footer">{footer}</div>
</main>
{script}
</body>
</html>
"""


# ── SUMO trending dashboard ─────────────────────────────────────────────────
def build_trending():
    src = f"{MONTH}_sumo_trending.md"
    text = (BASE / src).read_text(encoding="utf-8")
    rows = table_rows(text.splitlines())
    # header row first
    header, *data = rows
    topics = []
    for r in data:
        if len(r) < 5:
            continue
        rank, topic, count, pct, qids = r[0], r[1], r[2], r[3], r[4]
        qs = cell_links(qids)
        topics.append({"rank": rank, "topic": topic, "count": int(count.replace(',', '')),
                       "pct": pct, "qs": qs})
    topics.sort(key=lambda t: t["count"], reverse=True)
    total = sum(t["count"] for t in topics)
    top = topics[0]
    maxc = top["count"]

    chart_labels = [t["topic"] for t in topics]
    chart_data = [t["count"] for t in topics]

    rows_html = ""
    for i, t in enumerate(topics, 1):
        w = round(t["count"] / maxc * 100, 1)
        qlis = "".join(
            f'<li><a href="{esc(q["url"])}" target="_blank"><span class="q-id">#{esc(q["text"])}</span>{esc(redact_sumo_title(q["title"]) or "(no title)")}</a></li>'
            for q in t["qs"]
        )
        rows_html += f"""<details class="topic">
  <summary>
    <span class="topic__rank">{i}</span>
    <span class="topic__main">
      <span class="topic__name"><i class="ph ph-caret-right caret"></i>{esc(t["topic"])}</span>
      <span class="topic__bar-wrap"><span class="topic__bar" style="width:{w}%"></span></span>
    </span>
    <span class="topic__fig"><span class="topic__count">{t["count"]:,}</span><br><span class="topic__pct">{esc(t["pct"])}</span></span>
  </summary>
  <div class="topic__qs">
    <ul class="q-list">{qlis}</ul>
  </div>
</details>
"""

    body = f"""
<div class="page-head">
  <p class="eyebrow"><i class="ph-fill ph-chart-bar"></i> Desktop Forum · SUMO</p>
  <h1>Trending Topics</h1>
  <p class="dek">What desktop users asked about this month, rolled up from SUMO tags into topic buckets. Click any topic to read the actual question titles behind the number — the real signal under the summary.</p>
  <div class="meta-pills">
    <span class="pill"><i class="ph ph-question"></i>{total:,} questions</span>
    <span class="pill"><i class="ph ph-stack"></i>{len(topics)} topics</span>
    <span class="pill"><i class="ph ph-calendar-dots"></i>{MONTH_LABEL} 2026</span>
  </div>
</div>

<div class="stats">
  <div class="stat stat--primary"><div class="stat__val">{total:,}</div><div class="stat__lbl">Questions analyzed</div></div>
  <div class="stat"><div class="stat__val">{len(topics)}</div><div class="stat__lbl">Topic buckets</div></div>
  <div class="stat stat--teal"><div class="stat__val">{top["pct"]}</div><div class="stat__lbl">Top: {esc(top["topic"])}</div></div>
</div>

<div class="card">
  <div class="card__head"><div class="card__title">Topic distribution</div><div class="card__sub">share of {total:,} questions</div></div>
  <div class="chart-box"><canvas id="topicChart"></canvas></div>
</div>

<div class="toolbar">
  <label class="search"><i class="ph ph-magnifying-glass"></i><input id="q" type="search" placeholder="Search question titles across all topics (e.g. gmail, password, calendar)"></label>
  <span class="count-note" id="countNote"></span>
</div>
<div id="topicList">
{rows_html}
</div>
"""

    script = f"""<script>
const PAL=(()=>{{const c=getComputedStyle(document.documentElement);return{{grid:c.getPropertyValue('--border').trim(),tick:c.getPropertyValue('--text-muted').trim(),txt:c.getPropertyValue('--text').trim(),pri:c.getPropertyValue('--primary').trim(),teal:c.getPropertyValue('--teal').trim()}};}})();
const TOPICS = {json.dumps([{"labels": chart_labels, "data": chart_data}])[1:-1]};
new Chart(document.getElementById('topicChart'),{{
  type:'bar',
  data:{{labels:TOPICS.labels,datasets:[{{data:TOPICS.data,backgroundColor:PAL.pri,borderRadius:6,maxBarThickness:22}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>c.parsed.x+' questions'}}}}}},
    scales:{{x:{{ticks:{{color:PAL.tick}},grid:{{color:PAL.grid}}}},y:{{ticks:{{color:PAL.txt,font:{{size:12}}}},grid:{{display:false}}}}}}}}
}});
// live search across question titles
const q=document.getElementById('q'),list=document.getElementById('topicList'),note=document.getElementById('countNote');
const topics=[...list.querySelectorAll('.topic')];
q.addEventListener('input',()=>{{
  const term=q.value.trim().toLowerCase();
  let shown=0,hits=0;
  topics.forEach(t=>{{
    const items=[...t.querySelectorAll('.q-list li')];
    let any=false;
    items.forEach(li=>{{const m=!term||li.textContent.toLowerCase().includes(term);li.style.display=m?'':'none';if(m&&term)hits++;any=any||m;}});
    const topicMatch=t.querySelector('.topic__name').textContent.toLowerCase().includes(term);
    const vis=!term||any||topicMatch;
    t.style.display=vis?'':'none';
    if(vis)shown++;
    t.open=!!term&&(any||topicMatch);
  }});
  note.textContent=term?`${{hits}} matching questions in ${{shown}} topics`:'';
}});
</script>"""

    footer = ("Source: thunderbird-metrics-and-reports concatenated SUMO questions CSV. "
              "SUMO tags rolled up into topic buckets; environment-only tags (OS, version) ignored; "
              "untagged questions use a small title-regex fallback. Questions can appear in more than one topic. "
              f"Generated from <code>{MONTH}_sumo_trending.md</code>.")
    out = (HEAD.format(title=f"SUMO Trending Topics — Thunderbird Support · {MONTH_LABEL} 2026",
                       crumb="Desktop · SUMO Trending", source=f"<code>{MONTH}_sumo_trending.md</code>",
                       month_label=f"{MONTH_LABEL} 2026")
           + body + FOOT.format(footer=footer, script=script))
    (BASE / f"{MONTH}_sumo_trending.html").write_text(out, encoding="utf-8")
    print(f"  wrote {MONTH}_sumo_trending.html — {len(topics)} topics, {total:,} questions")


# ── Mozilla Connect ideas dashboard ─────────────────────────────────────────
def build_connect():
    src = f"{MONTH}_connect_ideas.md"
    text = (BASE / src).read_text(encoding="utf-8")
    rows = table_rows(text.splitlines())
    header, *data = rows
    ideas = []
    for r in data:
        if len(r) < 6:
            continue
        rank, kudos, views, comments, status, idea = r[:6]
        link = cell_links(idea)
        title = link[0]["text"] if link else idea
        url = link[0]["url"] if link else "#"
        ideas.append({"rank": int(rank), "kudos": int(kudos), "views": int(views.replace(',', '')),
                      "comments": int(comments), "status": status, "title": title, "url": url})
    tot_k = sum(i["kudos"] for i in ideas)
    tot_v = sum(i["views"] for i in ideas)

    top = sorted(ideas, key=lambda i: i["kudos"], reverse=True)[:10]
    chart_labels = [i["title"][:38] + ("…" if len(i["title"]) > 38 else "") for i in top]
    chart_data = [i["kudos"] for i in top]

    body_rows = "".join(
        f'<tr data-k="{i["kudos"]}" data-v="{i["views"]}" data-c="{i["comments"]}">'
        f'<td class="num tbl-muted">{i["rank"]}</td>'
        f'<td><a href="{esc(i["url"])}" target="_blank">{esc(i["title"])}</a></td>'
        f'<td class="num kudos">{i["kudos"]}</td>'
        f'<td class="num">{i["views"]:,}</td>'
        f'<td class="num">{i["comments"]}</td>'
        f'<td><span class="tag">{esc(i["status"])}</span></td></tr>'
        for i in ideas
    )

    body = f"""
<div class="page-head">
  <p class="eyebrow"><i class="ph-fill ph-lightbulb"></i> Community Wishlist · Mozilla Connect</p>
  <h1>Connect Ideas</h1>
  <p class="dek">The Thunderbird community wishlist from Mozilla Connect — what users are asking for, complementing the SUMO signal of what they're blocked on. Sort by any column; search to filter.</p>
  <div class="meta-pills">
    <span class="pill"><i class="ph ph-lightbulb"></i>{len(ideas)} ideas</span>
    <span class="pill"><i class="ph ph-thumbs-up"></i>{tot_k} kudos</span>
    <span class="pill"><i class="ph ph-eye"></i>{tot_v:,} views</span>
  </div>
</div>

<div class="stats">
  <div class="stat stat--primary"><div class="stat__val">{len(ideas)}</div><div class="stat__lbl">Ideas posted</div></div>
  <div class="stat stat--teal"><div class="stat__val">{tot_k}</div><div class="stat__lbl">Total kudos</div></div>
  <div class="stat"><div class="stat__val">{tot_v:,}</div><div class="stat__lbl">Total views</div></div>
</div>

<div class="card">
  <div class="card__head"><div class="card__title">Top 10 by kudos</div><div class="card__sub">community upvotes</div></div>
  <div class="chart-box"><canvas id="ideaChart"></canvas></div>
</div>

<div class="toolbar">
  <label class="search"><i class="ph ph-magnifying-glass"></i><input id="q" type="search" placeholder="Search ideas"></label>
  <span class="count-note" id="countNote"></span>
</div>
<div class="card"><div class="card__body" style="padding-top:var(--s16)">
<table id="ideaTable">
  <thead><tr>
    <th data-sort="rank" class="num">#</th>
    <th>Idea</th>
    <th data-sort="k" class="num"><span class="so">Kudos <i class="ph ph-arrows-down-up"></i></span></th>
    <th data-sort="v" class="num"><span class="so">Views <i class="ph ph-arrows-down-up"></i></span></th>
    <th data-sort="c" class="num"><span class="so">Comments <i class="ph ph-arrows-down-up"></i></span></th>
    <th>Status</th>
  </tr></thead>
  <tbody>{body_rows}</tbody>
</table>
</div></div>
"""

    script = f"""<script>
const PAL=(()=>{{const c=getComputedStyle(document.documentElement);return{{grid:c.getPropertyValue('--border').trim(),tick:c.getPropertyValue('--text-muted').trim(),txt:c.getPropertyValue('--text').trim(),teal:c.getPropertyValue('--teal').trim()}};}})();
const TOP={{labels:{json.dumps(chart_labels)},data:{json.dumps(chart_data)}}};
new Chart(document.getElementById('ideaChart'),{{
  type:'bar',
  data:{{labels:TOP.labels,datasets:[{{data:TOP.data,backgroundColor:PAL.teal,borderRadius:6,maxBarThickness:20}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>c.parsed.x+' kudos'}}}}}},
    scales:{{x:{{ticks:{{color:PAL.tick,precision:0}},grid:{{color:PAL.grid}}}},y:{{ticks:{{color:PAL.txt,font:{{size:11}}}},grid:{{display:false}}}}}}}}
}});
// sort + search
const tbl=document.getElementById('ideaTable'),tb=tbl.querySelector('tbody');
const rows=[...tb.rows];let dir=1,lastKey=null;
tbl.querySelectorAll('th[data-sort]').forEach(th=>th.addEventListener('click',()=>{{
  const k=th.dataset.sort;dir=(lastKey===k)?-dir:-1;lastKey=k;
  rows.sort((a,b)=>{{
    const av=k==='rank'?+a.cells[0].textContent:+a.dataset[k];
    const bv=k==='rank'?+b.cells[0].textContent:+b.dataset[k];
    return (av-bv)*dir;
  }});
  rows.forEach(r=>tb.appendChild(r));
}}));
const q=document.getElementById('q'),note=document.getElementById('countNote');
q.addEventListener('input',()=>{{
  const t=q.value.trim().toLowerCase();let n=0;
  rows.forEach(r=>{{const m=!t||r.cells[1].textContent.toLowerCase().includes(t);r.style.display=m?'':'none';if(m)n++;}});
  note.textContent=t?`${{n}} of {len(ideas)} ideas`:'';
}});
</script>"""

    footer = ("Mozilla Connect is the product feedback / ideation channel; every Thunderbird-labeled post "
              f"lands in the ideas board. Generated from <code>{MONTH}_connect_ideas.md</code>.")
    out = (HEAD.format(title=f"Mozilla Connect Ideas — Thunderbird Support · {MONTH_LABEL} 2026",
                       crumb="Connect Ideas", source=f"<code>{MONTH}_connect_ideas.md</code>",
                       month_label=f"{MONTH_LABEL} 2026")
           + body + FOOT.format(footer=footer, script=script))
    (BASE / f"{MONTH}_connect_ideas.html").write_text(out, encoding="utf-8")
    print(f"  wrote {MONTH}_connect_ideas.html — {len(ideas)} ideas")


# ── Desktop priorities dashboard ────────────────────────────────────────────
def build_priorities():
    src = f"{MONTH}_desktop_priorities.md"
    text = (BASE / src).read_text(encoding="utf-8")
    # split into theme sections by "## " headings
    sections = re.split(r'\n## ', text)
    # exec summary table -> themes (lives in its own "## Executive summary" section)
    exec_sec = next((s for s in sections if s.lstrip().startswith('Executive summary')), "")
    exec_rows = table_rows(exec_sec.splitlines())
    themes = []
    for r in exec_rows:
        if len(r) >= 3 and re.match(r'\d', r[0]):
            name = re.sub(r'^\d+\.\s*', '', r[0])
            themes.append({"name": name.strip(), "count": int(r[1]), "pct": r[2], "providers": [], "subs": []})

    # per-theme sections (## 1. ..., ## 2. ...)
    theme_secs = [s for s in sections[1:] if re.match(r'\d+\.', s)]
    for idx, sec in enumerate(theme_secs):
        if idx >= len(themes):
            break
        lines = sec.splitlines()
        # provider table: header "Provider | Count"
        provs, subs = [], []
        # collect all tables in section
        tbl = table_rows(lines)
        for row in tbl:
            if len(row) == 2 and row[0].lower() != 'provider' and not set(row[1]) <= set('-: '):
                # could be provider row (name,count)
                if row[1].isdigit():
                    provs.append({"name": row[0], "count": int(row[1])})
            elif len(row) >= 3 and 'http' in row[-1]:
                subname = row[0]
                cnt = row[1]
                qs = cell_links(row[-1])
                if subname.lower() != 'sub-theme':
                    subs.append({"name": subname, "count": cnt, "qs": qs})
        themes[idx]["providers"] = provs
        themes[idx]["subs"] = subs

    accents = ["var(--error)", "var(--warning)", "var(--info)"]
    total_q = sum(t["count"] for t in themes) or int(re.search(r'from (\d+)', text).group(1)) if re.search(r'from (\d+)', text) else 0
    if not total_q:
        m = re.search(r'Total questions analyzed:\*\* (\d+)', (BASE / f"{MONTH}_sumo_trending.md").read_text(encoding="utf-8"))
        total_q = int(m.group(1)) if m else 0
    cards = ""
    for i, th in enumerate(themes):
        acc = accents[i % len(accents)]
        prov_max = max((p["count"] for p in th["providers"]), default=1)
        prov_html = "".join(
            f'<div class="mini-row"><span>{esc(p["name"])}</span><span class="num">{p["count"]}</span>'
            f'<span class="mini-row__bar" style="width:{round(p["count"]/prov_max*100)}%"></span></div>'
            for p in th["providers"]
        )
        subs_html = ""
        for s in th["subs"]:
            qlis = "".join(
                f'<li><a href="{esc(q["url"])}" target="_blank"><span class="q-id">#{esc(q["text"])}</span>{esc(redact_sumo_title(q["title"]) or "(no title)")}</a></li>'
                for q in s["qs"]
            )
            subs_html += f"""<div class="subhead">{esc(s["name"])} · {esc(str(s["count"]))}</div>
<ul class="q-list">{qlis}</ul>"""
        prov_block = f'<div class="subhead">Provider distribution</div><div class="mini-bars">{prov_html}</div>' if prov_html else ""
        cards += f"""<details class="theme" style="--accent:{acc}">
  <summary>
    <div><div class="theme__name"><i class="ph ph-caret-right caret"></i>{esc(th["name"])}</div></div>
    <div class="theme__fig"><div class="theme__count">{th["count"]}</div><div class="theme__pct">{esc(th["pct"])}</div></div>
  </summary>
  <div class="theme__body">
    {prov_block}
    {subs_html}
  </div>
</details>
"""

    chart_labels = [t["name"] for t in themes]
    chart_data = [t["count"] for t in themes]

    body = f"""
<div class="page-head">
  <p class="eyebrow"><i class="ph-fill ph-target"></i> Desktop Forum · Community Signal</p>
  <h1>Recommended Priorities</h1>
  <p class="dek">Three themes drawn from {total_q} {MONTH_LABEL} SUMO questions, ranked by volume. Each theme expands into its provider distribution and the real user questions behind it. Headline theme totals are the load-bearing number; sub-theme counts are illustrative.</p>
  <div class="meta-pills">
    <span class="pill"><i class="ph ph-target"></i>{len(themes)} priority themes</span>
    <span class="pill"><i class="ph ph-question"></i>{total_q} questions</span>
    <span class="pill"><i class="ph ph-calendar-dots"></i>{MONTH_LABEL} 2026</span>
  </div>
</div>

<div class="card">
  <div class="card__head"><div class="card__title">Priority themes by volume</div><div class="card__sub">questions per theme</div></div>
  <div class="chart-box" style="min-height:200px"><canvas id="themeChart"></canvas></div>
</div>

{cards}
"""

    script = f"""<script>
const PAL=(()=>{{const c=getComputedStyle(document.documentElement);return{{grid:c.getPropertyValue('--border').trim(),tick:c.getPropertyValue('--text-muted').trim(),txt:c.getPropertyValue('--text').trim(),err:c.getPropertyValue('--error').trim(),warn:c.getPropertyValue('--warning').trim(),info:c.getPropertyValue('--info').trim()}};}})();
new Chart(document.getElementById('themeChart'),{{
  type:'bar',
  data:{{labels:{json.dumps(chart_labels)},datasets:[{{data:{json.dumps(chart_data)},backgroundColor:[PAL.err,PAL.warn,PAL.info],borderRadius:6,maxBarThickness:28}}]}},
  options:{{indexAxis:'y',responsive:true,maintainAspectRatio:false,
    plugins:{{legend:{{display:false}},tooltip:{{callbacks:{{label:c=>c.parsed.x+' questions'}}}}}},
    scales:{{x:{{ticks:{{color:PAL.tick}},grid:{{color:PAL.grid}}}},y:{{ticks:{{color:PAL.txt,font:{{size:12}}}},grid:{{display:false}}}}}}}}
}});</script>"""

    footer = (f"Themes derived from title patterns in the {MONTH_LABEL} SUMO question set; questions can appear under more "
              "than one theme. Headline theme totals are load-bearing; sub-theme counts are illustrative. "
              f"Generated from <code>{MONTH}_desktop_priorities.md</code>.")
    out = (HEAD.format(title=f"Desktop Priorities — Thunderbird Support · {MONTH_LABEL} 2026",
                       crumb="Desktop · Priorities", source=f"<code>{MONTH}_desktop_priorities.md</code>",
                       month_label=f"{MONTH_LABEL} 2026")
           + body + FOOT.format(footer=footer, script=script))
    (BASE / f"{MONTH}_desktop_priorities.html").write_text(out, encoding="utf-8")
    print(f"  wrote {MONTH}_desktop_priorities.html — {len(themes)} themes")


if __name__ == "__main__":
    print(f"Building Thunderbird-brand drill-down dashboards ({MONTH} 2026)…")
    build_trending()
    build_connect()
    build_priorities()
    print("Done.")
