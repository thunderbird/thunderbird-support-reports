#!/usr/bin/env python3
"""Zendesk CLI for querying ticket details.

Credentials: ~/.config/zendesk/credentials
    email=you@example.com
    token=your_api_token
    subdomain=tbpro
"""
import argparse
import base64
import json
import os
import sys
import textwrap
import urllib.parse
import urllib.request
from pathlib import Path

CREDS_PATH = Path.home() / ".config" / "zendesk" / "credentials"


def load_creds():
    if not CREDS_PATH.exists():
        sys.exit(
            f"Missing {CREDS_PATH}. Create it with:\n"
            "  email=you@thunderbird.net\n"
            "  token=YOUR_API_TOKEN\n"
            "  subdomain=tbpro\n"
            f"Then: chmod 600 {CREDS_PATH}"
        )
    data = {}
    for line in CREDS_PATH.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip()
    for required in ("email", "token", "subdomain"):
        if required not in data:
            sys.exit(f"{CREDS_PATH} missing '{required}=' line")
    return data


def api_get(path, creds, params=None):
    base = f"https://{creds['subdomain']}.zendesk.com/api/v2"
    url = base + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    auth = f"{creds['email']}/token:{creds['token']}"
    header = "Basic " + base64.b64encode(auth.encode()).decode()
    req = urllib.request.Request(url, headers={"Authorization": header, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        sys.exit(f"HTTP {e.code} on {url}\n{body}")


def fmt_ticket(t):
    requester = t.get("requester_id")
    tags = ", ".join(t.get("tags") or []) or "—"
    return textwrap.dedent(f"""\
        Ticket #{t['id']}  [{t.get('status')}]  {t.get('priority') or 'no priority'}
        Subject:    {t.get('subject')}
        Created:    {t.get('created_at')}
        Updated:    {t.get('updated_at')}
        Requester:  {requester}
        Assignee:   {t.get('assignee_id')}
        Group:      {t.get('group_id')}
        Channel:    {(t.get('via') or {}).get('channel')}
        Tags:       {tags}
        URL:        {t.get('url')}
        Description:
        {textwrap.indent((t.get('description') or '').strip(), '  ')}
        """)


def cmd_ticket(args, creds):
    data = api_get(f"/tickets/{args.id}.json", creds)
    t = data["ticket"]
    if args.json:
        print(json.dumps(t, indent=2))
        return
    print(fmt_ticket(t))


def cmd_comments(args, creds):
    data = api_get(f"/tickets/{args.id}/comments.json", creds)
    comments = data.get("comments", [])
    if args.json:
        print(json.dumps(comments, indent=2))
        return
    for c in comments:
        kind = "public" if c.get("public") else "internal"
        print(f"\n— {c['created_at']}  author={c['author_id']}  [{kind}] —")
        print((c.get("body") or "").strip())


def cmd_search(args, creds):
    query = args.query
    data = api_get("/search.json", creds, {"query": query})
    results = data.get("results", [])
    if args.json:
        print(json.dumps(results, indent=2))
        return
    if not results:
        print("(no results)")
        return
    for r in results:
        if r.get("result_type") == "ticket":
            print(f"#{r['id']:>7}  [{r.get('status'):>7}]  {r.get('subject')}")
        else:
            print(f"{r.get('result_type'):>10}  {r.get('id')}  {r.get('name') or r.get('subject') or ''}")
    print(f"\n{data.get('count', len(results))} result(s)")


def main():
    p = argparse.ArgumentParser(prog="zd", description="Zendesk CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("ticket", help="Show one ticket")
    t.add_argument("id", type=int)
    t.add_argument("--json", action="store_true")

    c = sub.add_parser("comments", help="Show ticket comments/conversation")
    c.add_argument("id", type=int)
    c.add_argument("--json", action="store_true")

    s = sub.add_parser("search", help="Zendesk search query")
    s.add_argument("query", help='e.g. "status:open priority:high"')
    s.add_argument("--json", action="store_true")

    args = p.parse_args()
    creds = load_creds()
    {"ticket": cmd_ticket, "comments": cmd_comments, "search": cmd_search}[args.cmd](args, creds)


if __name__ == "__main__":
    main()
