#!/usr/bin/env python3
"""Build a Thunderbird-brand DEEP-DIVE dashboard for a friction theme (prototype).

Reads the Play Store review CSVs in data/input/, filters to a theme (default: push),
categorises each review (A core failure / B regression / C UX friction), decodes device
codenames, computes star-rating scenario math, and renders an interactive dashboard in the
same brand system as the drill-downs: light tokens, DEFAULT DARK with a sun/moon toggle.

Output: lisa/2026/june_push_deep_dive_sample.html  (June prototype — does NOT touch
published march_push_deep_dive.html, generate.py, or june.html.)

Usage:  uv run scripts/build_deep_dive_dashboard.py [month]
        uv run scripts/build_deep_dive_dashboard.py june
"""
import csv, re, html, json, sys
from pathlib import Path

from pii_redact import paraphrase_review, safe_play_link

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "input"
MONTH = (sys.argv[1] if len(sys.argv) > 1 else "june").lower()
MONTH_NUM = {"january":"01","february":"02","march":"03","april":"04","may":"05",
             "june":"06","july":"07","august":"08","september":"09","october":"10",
             "november":"11","december":"12"}[MONTH]
OUT = ROOT / "lisa" / "2026" / f"{MONTH}_push_deep_dive_sample.html"

CSVS = [
    ("TB",  f"reviews_net.thunderbird.android_2026{MONTH_NUM}.csv"),
    ("TB",  f"reviews_net.thunderbird.android.beta_2026{MONTH_NUM}.csv"),
    ("K9",  f"reviews_com.fsck.k9_2026{MONTH_NUM}.csv"),
]

THEME_NAME = "Push / Notification Sync"
THEME_RE = re.compile(r'notif|push|sync|synchroni|fetch|delayed|15.?min|benachrichtig|nachricht', re.I)
# categorisation (B regression → C UX → else A core)
RE_B = re.compile(r'update|aktualisier|since|seit|version|1[78]\.|banner|stays?|delete|clear|mark.*read|gelesen|löschen|no longer|nicht mehr', re.I)
RE_C = re.compile(r'poll|interval|15.?min|battery|akku|setup|einricht|enable|frequenc|häufig|push.?service', re.I)

DEVICE_MAP = {
    "e3q": "Samsung Galaxy S24 Ultra", "pa3q": "Samsung Galaxy S25 Ultra",
    "e1s": "Samsung Galaxy S24", "e1q": "Samsung Galaxy S24+",
    "a12s": "Samsung Galaxy A12s", "a16x": "Samsung Galaxy A16 5G",
    "OP611FL1": "OnePlus 11", "shiba": "Google Pixel 8", "lynx": "Google Pixel 8a",
    "sweet": "Xiaomi Redmi Note 10 Pro", "cancunf": "Motorola Moto G52",
    "m1s": "Samsung Galaxy S22 Ultra", "a55x": "Samsung Galaxy A55",
    "scout": "Fairphone 5", "cuscoi": "Google Pixel 9",
}
CAT = {
    "a": {"label": "Core delivery failure", "tag": "A", "color": "var(--error)",
          "note": "Notifications simply don't arrive, or arrive badly late — the core promise of the app is broken. Highest churn risk and lowest ratings."},
    "b": {"label": "Version regression", "tag": "B", "color": "var(--warning)",
          "note": "Worked before, broke after an update — notification state, banners, or read-status behaviour changed. A release-process and regression-detection problem."},
    "c": {"label": "UX friction (not a bug)", "tag": "C", "color": "var(--info)",
          "note": "Poll interval, battery-optimisation setup, or discoverability. The mechanism works but the experience frustrates. Often fixable with docs + better defaults."},
}
ENGLISH = {"en", "en-US", "en-GB", "en-CA", "en-AU", "en-IN"}


def read_reviews(app, fname):
    path = INPUT / fname
    if not path.exists():
        print(f"  (skip — missing {fname})")
        return []
    rows = []
    for enc in ("utf-8-sig", "utf-16"):
        try:
            with open(path, encoding=enc, newline="") as f:
                rows = list(csv.DictReader(f))
            if rows and "Star Rating" in rows[0]:
                break
        except Exception:
            rows = []
    out = []
    for r in rows:
        out.append({
            "app": app,
            "lang": (r.get("Reviewer Language") or "").strip(),
            "device": (r.get("Device") or "").strip(),
            "stars": int((r.get("Star Rating") or "0").strip() or 0),
            "title": (r.get("Review Title") or "").strip(),
            "text": (r.get("Review Text") or "").strip(),
            "reply": (r.get("Developer Reply Text") or "").strip(),
            "date": (r.get("Review Submit Date and Time") or "")[:10],
            "ver": (r.get("App Version Name") or "").strip(),
            "link": (r.get("Review Link") or "").strip(),
        })
    return out


def categorise(r):
    blob = f"{r['title']} {r['text']}".lower()
    if RE_B.search(blob):
        return "b"
    if RE_C.search(blob):
        return "c"
    return "a"


def esc(s):
    return html.escape(s or "", quote=True)


def stars_html(n):
    return '<span class="stars">' + "★" * n + '<span class="stars--off">' + "★" * (5 - n) + "</span></span>"


def main():
    print("Building push deep-dive dashboard (prototype)…")
    all_rows, tb_rows = [], []
    for app, fname in CSVS:
        rows = read_reviews(app, fname)
        all_rows += rows
        if app == "TB":
            tb_rows += rows

    theme = [r for r in all_rows if THEME_RE.search(f"{r['title']} {r['text']}")]
    for r in theme:
        r["cat"] = categorise(r)
    # sort 1★→5★ then by date
    theme.sort(key=lambda r: (r["stars"], r["date"]))

    n_total = len(theme)
    negs = [r for r in theme if r["stars"] <= 3]
    n_neg = len(negs)
    avg = sum(r["stars"] for r in theme) / n_total if n_total else 0
    replied = sum(1 for r in negs if r["reply"])
    by_cat = {k: [r for r in theme if r["cat"] == k] for k in ("a", "b", "c")}

    def catavg(k):
        rs = by_cat[k]
        return sum(r["stars"] for r in rs) / len(rs) if rs else 0

    # star math against ALL TB reviews
    tb_sum = sum(r["stars"] for r in tb_rows)
    tb_n = len(tb_rows) or 1
    tb_avg = tb_sum / tb_n
    tb_neg_in_theme = [r for r in negs if r["app"] == "TB"]

    def scenario(target):
        delta = sum(target - r["stars"] for r in tb_neg_in_theme)
        return (tb_sum + delta) / tb_n

    sc4, sc5 = scenario(4), scenario(5)

    # ── review cards ─────────────────────────────────────────────────────────
    def card(r):
        dev = DEVICE_MAP.get(r["device"], r["device"] or "—")
        appcls = "badge--tb" if r["app"] == "TB" else "badge--k9"
        applbl = "TB" if r["app"] == "TB" else "K-9"
        noneng = r["lang"] and r["lang"] not in ENGLISH
        lang_badge = f'<span class="rc__lang">{esc(r["lang"])}</span>' if r["lang"] else ""
        safe_title = paraphrase_review(r["title"], max_len=120) if r["title"] else None
        safe_text = paraphrase_review(r["text"], max_len=480) or "(no text)"
        safe_reply = paraphrase_review(r["reply"], max_len=480) if r["reply"] else None
        title = f'<div class="rc__title">{esc(safe_title)}</div>' if safe_title else ""
        reply = (f'<div class="rc__reply"><span class="rc__reply-lbl">Developer reply</span>{esc(safe_reply)}</div>'
                 if safe_reply else "")
        # honest translation slot — AI translation is added by the analyst, not fabricated here
        trans = ('<div class="rc__xlate">Non-English review — AI translation added during analyst review.</div>'
                 if noneng else "")
        play_link = safe_play_link(r["link"])
        link = f'<a class="rc__link" href="{esc(play_link)}" target="_blank">Open in Play Store ↗</a>' if play_link else ""
        cat = CAT[r["cat"]]
        return f"""<article class="rc rc--{r['cat']}" data-cat="{r['cat']}">
  <div class="rc__head">
    <span class="badge {appcls}">{applbl}</span>
    {stars_html(r['stars'])}
    {lang_badge}
    <span class="rc__cat" style="--cc:{cat['color']}">{cat['tag']}</span>
    <span class="rc__meta">{esc(r['date'])} · {esc(dev)} · v{esc(r['ver']) or '—'}</span>
  </div>
  {title}
  <div class="rc__text">{esc(safe_text)}</div>
  {trans}
  {reply}
  {link}
</article>"""

    sections = ""
    for k in ("a", "b", "c"):
        rs = by_cat[k]
        c = CAT[k]
        cards = "".join(card(r) for r in rs)
        sections += f"""<section class="dd-sec" data-section="{k}">
  <div class="analysis" style="--cc:{c['color']}">
    <div class="analysis__head"><span class="tag" style="--cc:{c['color']}">{c['tag']}</span>{c['label']} · {len(rs)} reviews · avg {catavg(k):.2f}★</div>
    <p>{c['note']}</p>
  </div>
  {cards}
</section>"""

    # ── recommendations ────────────────────────────────────────────────────
    actions = [
        ("LOW", "var(--success)", "Publish an OEM battery-optimisation KB article",
         "Most Category A failures trace to aggressive battery management (Samsung, Xiaomi, OnePlus). A single illustrated KB article linked from dev replies addresses the largest bucket."),
        ("MED", "var(--warning)", "Fix notification read/clear state regression",
         "Category B reviews report banners that stay after reading, or notifications that won't clear, since a recent version. A targeted regression fix recovers users who rated down after an update."),
        ("HIGH", "var(--error)", "Re-architect background sync reliability",
         "The core delivery failures need work on push delivery / fetch scheduling so notifications arrive on time without manual battery exemptions. Highest effort, highest rating ceiling."),
    ]
    act_rows = "".join(
        f'<tr><td><span class="effort" style="--cc:{c}">{eff}</span></td><td><strong>{esc(t)}</strong><div class="tbl-sub">{esc(d)}</div></td></tr>'
        for eff, c, t, d in actions
    )

    body = f"""
<div class="page-head">
  <p class="eyebrow"><i class="ph-fill ph-magnifying-glass-plus"></i> Android Reviews · Deep Dive</p>
  <h1>{THEME_NAME}</h1>
  <p class="dek">Every push/notification-related Play Store review this month, split into three problem categories and sorted worst-first. Each card decodes the device, flags the language, and shows the developer reply inline. Use this to see exactly what's behind the friction number on the monthly report.</p>
  <div class="meta-pills">
    <span class="pill"><i class="ph ph-chat-text"></i>{n_total} reviews</span>
    <span class="pill"><i class="ph ph-star"></i>{avg:.2f}★ avg</span>
    <span class="pill"><i class="ph ph-calendar-dots"></i>{MONTH.capitalize()} 2026 data</span>
  </div>
</div>

<div class="jump">
  <i class="ph ph-arrow-bend-down-right"></i> The fixes and star-rating math are at the bottom — <a href="#recommendations">jump to recommendations ↓</a>
</div>

<div class="stats">
  <div class="stat stat--primary"><div class="stat__val">{n_total}</div><div class="stat__lbl">Push reviews</div></div>
  <div class="stat"><div class="stat__val" style="color:var(--error)">{n_neg}</div><div class="stat__lbl">Negative (1–3★)</div></div>
  <div class="stat"><div class="stat__val" style="color:var(--warning)">{avg:.2f}★</div><div class="stat__lbl">Avg rating</div></div>
  <div class="stat stat--teal"><div class="stat__val">{(replied/n_neg*100) if n_neg else 0:.0f}%</div><div class="stat__lbl">Negatives replied to</div></div>
</div>
<div class="stats">
  <div class="stat" style="border-top:3px solid var(--error)"><div class="stat__val" style="color:var(--error)">{len(by_cat['a'])}</div><div class="stat__lbl">A · core failure · {catavg('a'):.2f}★</div></div>
  <div class="stat" style="border-top:3px solid var(--warning)"><div class="stat__val" style="color:var(--warning)">{len(by_cat['b'])}</div><div class="stat__lbl">B · regression · {catavg('b'):.2f}★</div></div>
  <div class="stat" style="border-top:3px solid var(--info)"><div class="stat__val" style="color:var(--info)">{len(by_cat['c'])}</div><div class="stat__lbl">C · UX friction · {catavg('c'):.2f}★</div></div>
</div>

<div class="tabs" role="tablist">
  <button class="tab is-active" data-tab="all">All {n_total}</button>
  <button class="tab" data-tab="a"><span class="tag" style="--cc:var(--error)">A</span> Core failure <span class="tcount">{len(by_cat['a'])}</span></button>
  <button class="tab" data-tab="b"><span class="tag" style="--cc:var(--warning)">B</span> Regression <span class="tcount">{len(by_cat['b'])}</span></button>
  <button class="tab" data-tab="c"><span class="tag" style="--cc:var(--info)">C</span> UX friction <span class="tcount">{len(by_cat['c'])}</span></button>
</div>

{sections}

<section id="recommendations" class="recs">
  <h2 class="recs__title">Recommendations &amp; star-rating math</h2>
  <p class="dek">Thunderbird's all-review average is <strong>{tb_avg:.2f}★</strong>. If the {len(tb_neg_in_theme)} negative TB push reviewers upgraded their ratings, here's where the average lands:</p>
  <div class="card"><div class="card__body" style="padding-top:var(--s16)">
  <table>
    <thead><tr><th>Scenario</th><th class="num">Reviews moved</th><th class="num">New TB avg</th></tr></thead>
    <tbody>
      <tr><td>Push negatives → 4★ (conservative)</td><td class="num">{len(tb_neg_in_theme)}</td><td class="num"><strong>{sc4:.2f}★</strong></td></tr>
      <tr><td>Push negatives → 5★ (optimistic)</td><td class="num">{len(tb_neg_in_theme)}</td><td class="num"><strong>{sc5:.2f}★</strong></td></tr>
    </tbody>
  </table>
  <p class="tbl-sub" style="margin-top:var(--s12)">Goal is 4.00★. Fixing this one theme moves the all-review average from {tb_avg:.2f}★ toward {sc5:.2f}★ — the single highest-leverage lever on the Play Store rating.</p>
  </div></div>
  <div class="card"><div class="card__head"><div class="card__title">Actions by effort</div></div><div class="card__body">
  <table><tbody>{act_rows}</tbody></table>
  </div></div>
</section>
"""

    footer = ("Categorisation: B (regression) → C (UX) → else A (core failure), matched by keyword pattern on "
              "title + text. Device codenames decoded where known. Translations of non-English reviews are added "
              "by the analyst (AI-assisted) during review and are not auto-generated here. "
              f"Prototype data: {MONTH.capitalize()} 2026 CSVs in <code>data/input/</code>. Review text paraphrased; PII redacted before write.")
    out = HEAD.format(title=f"{THEME_NAME} — Deep Dive · Thunderbird Support",
                      crumb="Android · Push Deep Dive",
                      month_label=f"{MONTH.capitalize()} 2026") + body + FOOT.format(footer=footer)
    OUT.write_text(out, encoding="utf-8")
    print(f"  wrote {OUT.name} — {n_total} reviews (A {len(by_cat['a'])} · B {len(by_cat['b'])} · C {len(by_cat['c'])})")
    print("Done.")


# ── brand chrome (light tokens, default DARK + toggle) ──────────────────────
HEAD = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<script>(function(){{var t=localStorage.getItem('tb-theme')||'dark';if(t==='dark')document.documentElement.classList.add('dark');}})();</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<script src="https://unpkg.com/@phosphor-icons/web@2.1.1"></script>
<style>
:root{{
  --surface-page:#f5f6fb; --surface-card:#ffffff; --surface-sunken:#eef1f8;
  --border:#e4e6f0; --border-strong:#d2d5e4;
  --primary:#1373d9; --primary-strong:#105399; --primary-soft:#eaf3fd;
  --teal:#1a9c95; --teal-soft:#e6f6f4;
  --text:#16161e; --text-secondary:#494b5c; --text-muted:#73758a; --text-faint:#9a9cb0;
  --success:#194e2c; --success-c:#f4f9f4;
  --warning:#713f12; --warning-c:#fefae8;
  --error:#7f1d1d; --error-c:#fef2f2;
  --info:#004f9b; --info-c:#f0f8ff;
  --star:#e8a317;
  --s4:.25rem; --s8:.5rem; --s12:.75rem; --s16:1rem; --s24:1.5rem; --s32:2rem; --s48:3rem;
  --radius-sm:8px; --radius-md:12px; --radius-lg:16px;
  --shadow-sm:0 1px 2px rgba(16,24,40,.06),0 1px 3px rgba(16,24,40,.10);
}}
html.dark{{
  --surface-page:#0d0c14; --surface-card:#15131e; --surface-sunken:#1c1a28;
  --border:#2b2845; --border-strong:#3e3b62;
  --primary:#6d8bff; --primary-strong:#9db4ff; --primary-soft:#0e1038;
  --teal:#2dd4bf; --teal-soft:#04201d;
  --text:#e8e6f5; --text-secondary:#b4b1d0; --text-muted:#8a87a6; --text-faint:#5d5a78;
  --success:#34d27b; --success-c:#06210f;
  --warning:#f5a623; --warning-c:#1f1500;
  --error:#ff6a6a; --error-c:#270808;
  --info:#6d8bff; --info-c:#0e1038;
  --star:#fcd34d;
  --shadow-sm:0 1px 2px rgba(0,0,0,.45);
}}
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
html{{scroll-behavior:smooth}}
body{{background:var(--surface-page);color:var(--text);font-family:'Inter',system-ui,sans-serif;font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}}
a{{color:var(--primary);text-decoration:none}} a:hover{{color:var(--primary-strong);text-decoration:underline}}
a:focus-visible,button:focus-visible{{outline:2px solid var(--primary);outline-offset:2px;border-radius:4px}}
.topbar{{background:var(--surface-card);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:20}}
.topbar__in{{max-width:1080px;margin:0 auto;padding:var(--s12) var(--s32);display:flex;align-items:center;gap:var(--s16)}}
.brand{{display:flex;align-items:center;gap:var(--s8);font-weight:700;color:var(--text);font-size:.95rem}}
.brand:hover{{text-decoration:none;color:var(--text)}} .brand svg{{width:26px;height:26px}}
.crumbs{{margin-left:auto;font-size:.8rem;color:var(--text-muted)}} .crumbs a{{color:var(--text-muted)}} .crumbs b{{color:var(--text-secondary);font-weight:600}}
.theme-toggle{{background:var(--surface-sunken);border:1px solid var(--border);color:var(--text-secondary);border-radius:999px;width:34px;height:34px;display:inline-flex;align-items:center;justify-content:center;cursor:pointer;font-size:1.05rem;flex-shrink:0}}
.theme-toggle:hover{{color:var(--text);border-color:var(--border-strong)}}
.theme-toggle .ph-sun{{display:none}} html.dark .theme-toggle .ph-moon{{display:none}} html.dark .theme-toggle .ph-sun{{display:inline}}
.wrap{{max-width:1080px;margin:0 auto;padding:var(--s32)}}
@media(max-width:640px){{.wrap,.topbar__in{{padding-left:var(--s16);padding-right:var(--s16)}}}}
.proto{{background:var(--info-c);border:1px solid var(--info);color:var(--info);border-radius:var(--radius-sm);padding:var(--s8) var(--s16);font-size:.78rem;margin-bottom:var(--s24)}}
.page-head{{margin-bottom:var(--s24)}}
.eyebrow{{font-size:.72rem;font-weight:700;text-transform:uppercase;letter-spacing:.12em;color:var(--primary);margin-bottom:var(--s8);display:flex;align-items:center;gap:var(--s8)}}
.page-head h1{{font-size:clamp(1.7rem,4vw,2.4rem);font-weight:700;letter-spacing:-.02em;line-height:1.1;margin-bottom:var(--s12)}}
.dek{{font-size:1rem;color:var(--text-secondary);line-height:1.65;max-width:72ch}}
.meta-pills{{display:flex;flex-wrap:wrap;gap:var(--s8);margin-top:var(--s16)}}
.pill{{background:var(--surface-card);border:1px solid var(--border);border-radius:999px;padding:var(--s4) var(--s12);font-size:.78rem;font-weight:600;color:var(--text-secondary);box-shadow:var(--shadow-sm)}}
.pill i{{color:var(--primary);margin-right:4px}}
.jump{{background:var(--primary-soft);border:1px solid var(--primary);border-radius:var(--radius-md);padding:var(--s12) var(--s16);font-size:.9rem;color:var(--primary-strong);margin-bottom:var(--s24)}}
.jump i{{margin-right:6px}} html.dark .jump{{color:var(--primary)}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:var(--s16);margin-bottom:var(--s16)}}
.stat{{background:var(--surface-card);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--s16) var(--s24);box-shadow:var(--shadow-sm)}}
.stat__val{{font-size:2rem;font-weight:700;letter-spacing:-.02em;line-height:1;font-variant-numeric:tabular-nums}}
.stat__lbl{{font-size:.74rem;font-weight:600;text-transform:uppercase;letter-spacing:.04em;color:var(--text-muted);margin-top:var(--s8)}}
.stat--primary .stat__val{{color:var(--primary-strong)}} html.dark .stat--primary .stat__val{{color:var(--primary)}}
.stat--teal .stat__val{{color:var(--teal)}}
.tabs{{display:flex;gap:var(--s8);flex-wrap:wrap;margin:var(--s24) 0 var(--s16);position:sticky;top:54px;background:var(--surface-page);padding:var(--s8) 0;z-index:10}}
.tab{{background:var(--surface-card);border:1px solid var(--border-strong);border-radius:999px;padding:var(--s8) var(--s16);font:inherit;font-size:.82rem;font-weight:600;color:var(--text-secondary);cursor:pointer;display:inline-flex;align-items:center;gap:6px}}
.tab:hover{{color:var(--text);border-color:var(--text-muted)}}
.tab.is-active{{background:var(--text);color:var(--surface-card);border-color:var(--text)}}
.tcount{{font-variant-numeric:tabular-nums;opacity:.7}}
.tag{{display:inline-flex;align-items:center;justify-content:center;min-width:18px;height:18px;font-size:.66rem;font-weight:700;border-radius:5px;background:var(--cc);color:#fff;padding:0 4px}}
.analysis{{background:var(--surface-card);border:1px solid var(--border);border-left:4px solid var(--cc);border-radius:var(--radius-md);padding:var(--s16) var(--s24);margin:var(--s16) 0;box-shadow:var(--shadow-sm)}}
.analysis__head{{font-weight:700;font-size:1rem;display:flex;align-items:center;gap:var(--s8);margin-bottom:var(--s4)}}
.analysis p{{font-size:.86rem;color:var(--text-secondary);line-height:1.6}}
.rc{{background:var(--surface-card);border:1px solid var(--border);border-radius:var(--radius-md);padding:var(--s16);margin-bottom:var(--s12);box-shadow:var(--shadow-sm)}}
.rc__head{{display:flex;align-items:center;gap:var(--s8);flex-wrap:wrap;margin-bottom:var(--s8)}}
.badge{{font-size:.66rem;font-weight:700;padding:2px 7px;border-radius:5px}}
.badge--tb{{background:var(--primary-soft);color:var(--primary-strong)}} html.dark .badge--tb{{color:var(--primary)}}
.badge--k9{{background:var(--teal-soft);color:var(--teal)}}
.stars{{color:var(--star);font-size:.9rem;letter-spacing:1px}} .stars--off{{color:var(--border-strong)}}
.rc__lang{{font-size:.66rem;font-weight:600;text-transform:uppercase;color:var(--text-muted);border:1px solid var(--border);border-radius:4px;padding:1px 5px}}
.rc__cat{{font-size:.66rem;font-weight:700;color:#fff;background:var(--cc);border-radius:5px;width:18px;height:18px;display:inline-flex;align-items:center;justify-content:center}}
.rc__meta{{margin-left:auto;font-size:.72rem;color:var(--text-muted)}}
.rc__title{{font-weight:700;font-size:.92rem;margin-bottom:var(--s4)}}
.rc__text{{font-size:.9rem;color:var(--text-secondary);line-height:1.6}}
.rc__xlate{{font-size:.74rem;color:var(--text-muted);font-style:italic;margin-top:var(--s8);padding-left:var(--s12);border-left:2px solid var(--border-strong)}}
.rc__reply{{margin-top:var(--s12);background:var(--surface-sunken);border-radius:var(--radius-sm);padding:var(--s12);font-size:.84rem;color:var(--text-secondary);line-height:1.55}}
.rc__reply-lbl{{display:block;font-size:.64rem;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--text-muted);margin-bottom:var(--s4)}}
.rc__link{{display:inline-block;margin-top:var(--s8);font-size:.76rem}}
.recs{{margin-top:var(--s48);scroll-margin-top:70px}}
.recs__title{{font-size:1.4rem;font-weight:700;letter-spacing:-.01em;margin-bottom:var(--s12)}}
.card{{background:var(--surface-card);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow-sm);margin-bottom:var(--s16);overflow:hidden}}
.card__head{{padding:var(--s24) var(--s24) var(--s12)}} .card__title{{font-size:1.05rem;font-weight:700}}
.card__body{{padding:0 var(--s24) var(--s24)}}
table{{width:100%;border-collapse:collapse;font-size:.88rem}}
th{{text-align:left;color:var(--text-muted);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em;padding:var(--s8) var(--s12);border-bottom:2px solid var(--border-strong)}}
td{{padding:var(--s8) var(--s12);border-bottom:1px solid var(--border);vertical-align:top}}
.num{{text-align:right;font-variant-numeric:tabular-nums}}
.tbl-sub{{font-size:.78rem;color:var(--text-muted);font-weight:400;line-height:1.5}}
.effort{{font-size:.68rem;font-weight:700;color:#fff;background:var(--cc);border-radius:5px;padding:2px 8px}}
.muted{{color:var(--text-muted)}}
.footer{{font-size:.78rem;color:var(--text-muted);line-height:1.6;border-top:1px solid var(--border);padding-top:var(--s16);margin-top:var(--s32)}}
.dd-sec{{margin-bottom:var(--s24)}}
</style>
</head>
<body>
<header class="topbar">
  <div class="topbar__in">
    <a class="brand" href="june_sample.html">
      <svg viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <circle cx="16" cy="16" r="15" fill="#1373d9"/><path d="M8 13h16M8 17h11M8 21h7" stroke="#fff" stroke-width="2.4" stroke-linecap="round"/>
      </svg>
      Thunderbird Support
    </a>
    <nav class="crumbs"><a href="june_sample.html">Monthly Report</a> &rsaquo; <b>{crumb}</b></nav>
    <button class="theme-toggle" onclick="localStorage.setItem('tb-theme',document.documentElement.classList.contains('dark')?'light':'dark');location.reload();" aria-label="Toggle light / dark theme" title="Toggle light / dark"><i class="ph ph-moon"></i><i class="ph ph-sun"></i></button>
  </div>
</header>
<main class="wrap">
<div class="proto"><b>Deep-dive dashboard prototype</b> — new design, default dark (toggle top-right). Data: {month_label} Play Store review CSVs.</div>
"""

FOOT = """
<div class="footer">{footer}</div>
</main>
<script>
const tabs=[...document.querySelectorAll('.tab')],secs=[...document.querySelectorAll('.dd-sec')];
tabs.forEach(t=>t.addEventListener('click',()=>{{
  tabs.forEach(x=>x.classList.remove('is-active'));t.classList.add('is-active');
  const k=t.dataset.tab;
  secs.forEach(s=>s.style.display=(k==='all'||s.dataset.section===k)?'':'none');
}}));
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
