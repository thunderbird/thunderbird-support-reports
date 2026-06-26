---
name: dns-check
description: Triage a Thundermail custom-domain email DNS ticket (DKIM/SPF/MX/DMARC) and draft the customer reply. Usage: /dns-check <domain> (e.g. /dns-check example.com)
arguments: [domain]
---

# Email DNS triage — $domain

Diagnose why mail from the custom domain **$domain** isn't signing or is landing
in spam, then hand back a clear PASS/FAIL plus a paste-ready Zendesk reply.

Read `docs/EMAIL-DNS-DEBUGGING.md` for the full reasoning behind every step
below — this skill is the fast path through it.

---

## Step 1 — Run the automated audit

```
scripts/dns/tbpro-dns-check.sh $domain
```

This grades DKIM (`tm1`/`tm2` CNAMEs), SPF, MX, and DMARC against the expected
Thundermail values in one shot. If `dig` isn't available, fall back to the manual
lookups in §1/§8 of the runbook.

## Step 2 — If anything FAILed, identify which customer mistake it is

Check the four common causes (runbook §2), in order:

1. **Domain appended twice** — re-query with the domain doubled
   (`dig +short tm1._domainkey.$domain.$domain CNAME @1.1.1.1`). If *that*
   resolves, the customer pasted the full host into a panel that auto-appends the
   zone. Fix: enter only `tm1._domainkey` in the name field (and `@` for apex).
2. **Cloudflare orange-cloud** — a proxied MX/CNAME/TXT. Fix: set those records to
   "DNS only" (grey cloud).
3. **Duplicate / old SPF** — there must be exactly one `v=spf1` TXT. Merge them.
4. **Not yet propagated** — just-added records; compare `@1.1.1.1` vs `@8.8.8.8`
   and have them wait out the TTL.

## Step 3 — If everything PASSed but mail is still unsigned → escalate, don't loop

All DNS correct + domain **Verified** but no `DKIM-Signature` header on a test
message is **our** server-side bug, not the customer's DNS (runbook §6). Do **not**
send the customer back to their DNS. Escalate to the platform team with: the
domain, raw headers of a test message, a note that DNS is verified clean, and a
reference to `platform-infrastructure#591` / `thunderbird-accounts#1023`.

## Step 4 — Draft the customer reply

Produce a short, friendly Zendesk reply. Rules:
- **Redact PII** — do not echo the customer's real domain back in anything that
  gets committed or shared outside the ticket. In the ticket reply itself the
  domain is fine; in any summary saved to this repo, use `example.com`.
- Give the **exact** record(s) to fix, copied from the runbook §0 answer-key table,
  with the customer's domain substituted in.
- One ask at a time. If multiple records are wrong, lead with DKIM (it's what
  rescues DMARC alignment).
- If Step 3 applies, the reply is "we've found this on our side and are fixing it —
  no change needed from you," **not** a request to edit DNS.

Output format:
```
RESULT: <PASS | FAIL: which records>
ROOT CAUSE: <one line>
NEXT ACTION: <customer fix | escalate to platform ref #591>

--- suggested Zendesk reply ---
<reply text>
```
