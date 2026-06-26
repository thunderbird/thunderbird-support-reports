# Email DNS Debugging — Support Runbook (DKIM · SPF · DMARC · MX · MTA-STS)

A field guide for the Thunderbird / Thundermail support team for triaging
deliverability and custom-domain tickets in Zendesk. Drop this in as a
`CLAUDE.md` (or open it in any Claude Code session in this repo) and Claude can
walk a ticket with you using the steps below.

> **Golden rule:** Most "my email goes to spam / isn't signed" tickets are a
> **customer DNS** problem you can confirm in 60 seconds with `dig`. A small but
> important minority are **our server side** (see §6). This runbook tells you
> which is which *before* you escalate.

---

## 0. What "good" looks like for a Thundermail custom domain

When a customer adds a custom domain (e.g. `example.com`) to Thundermail Pro,
these records must exist. Memorize this table — it's the answer key for every
DKIM/SPF ticket.

| Purpose | Record name | Type | Expected value |
|---|---|---|---|
| DKIM (RSA) | `tm1._domainkey.example.com` | CNAME | `tm1.example.com.dkim.thunderhosted.com.` |
| DKIM (Ed25519) | `tm2._domainkey.example.com` | CNAME | `tm2.example.com.dkim.thunderhosted.com.` |
| DKIM (spare) | `tm3._domainkey.example.com` | CNAME | `tm3.example.com.dkim.thunderhosted.com.` |
| SPF | `example.com` | TXT | `v=spf1 include:spf.thundermail.com ~all` |
| MX | `example.com` | MX | `mail.thundermail.com` |
| DMARC | `_dmarc.example.com` | TXT | `v=DMARC1; p=none; …` (or stricter) |
| MTA-STS (optional) | `_mta-sts.example.com` | TXT | `v=STSv1; id=…` |
| TLS-RPT (optional) | `_smtp._tls.example.com` | TXT | `v=TLSRPTv1; rua=…` |

Key facts that explain *why* it's built this way:

- **DKIM is CNAME-based, not TXT.** The customer publishes a CNAME that points
  into our `dkim.thunderhosted.com` zone. We host the actual public key there.
  This lets us **rotate keys without the customer touching their DNS again**.
- **`tm1` = RSA, `tm2` = Ed25519, `tm3` = spare.** Some receivers still want
  RSA; that's why both exist. `tm3` may not resolve to a key yet — that's normal.
- DKIM records **never live at the apex domain.** They're always at the
  `tmN._domainkey` host. If you query `example.com` for DKIM you'll find nothing —
  that's expected, not a bug.

---

## 1. The 60-second triage (run these first, every time)

> **Shortcut:** in this repo, just run `scripts/dns/tbpro-dns-check.sh <domain>`
> (or the `/dns-check <domain>` skill) to grade all of the below at once. The
> manual commands here are for when you need to see a specific record yourself.

Paste the customer's domain in place of `example.com`. `@1.1.1.1` forces a public
resolver so you see what the *internet* sees, not a stale local cache.

```bash
d=example.com

# DKIM — all three selectors should return a CNAME into dkim.thunderhosted.com
for s in tm1 tm2 tm3; do
  echo "== $s =="; dig +short ${s}._domainkey.$d CNAME @1.1.1.1
done

# SPF — must include spf.thundermail.com
dig +short $d TXT @1.1.1.1 | grep -i spf1

# MX — must be mail.thundermail.com
dig +short $d MX @1.1.1.1

# DMARC
dig +short _dmarc.$d TXT @1.1.1.1
```

Read the results against the table in §0. **>90% of tickets are solved here** —
one of the records is missing, misspelled, or wrong (see §2).

---

## 2. The four mistakes customers actually make

These are the real root causes we've seen on tickets. Check for them in order.

### 2a. The domain is appended twice (the #1 mistake)

Symptom — the lookup returns nothing, but a query with the domain doubled works:

```bash
dig +short tm1._domainkey.example.com CNAME @1.1.1.1            # empty
dig +short tm1._domainkey.example.com.example.com CNAME @1.1.1.1 # resolves!
```

**Cause:** the DNS provider (Cloudflare, Namecheap, GoDaddy, Squarespace…)
auto-appends the zone name. The customer pasted the **full** host
`tm1._domainkey.example.com` into the "name" field, so the provider stored
`tm1._domainkey.example.com.example.com`.

**Fix for the customer:** in the record *name/host* field, enter only the part
**before** the domain — i.e. `tm1._domainkey` (not the full FQDN). Some panels
want a bare `@` for apex records (SPF/MX). Same applies to `_dmarc`.

### 2b. Cloudflare proxy ("orange cloud") on a mail record

Cloudflare's proxy only makes sense for HTTP. If the customer proxies the MX or a
mail-related record, it breaks. **MX, SPF (TXT), DKIM (CNAME), and `_dmarc` must
all be "DNS only" (grey cloud).** Tell the customer to click the orange cloud to
turn it grey on those records. (DKIM CNAMEs especially — a proxied CNAME returns a
Cloudflare IP instead of the key.)

### 2c. Old / conflicting records

A pre-existing `v=spf1` TXT from a previous provider, or a second SPF record.
**There must be exactly one SPF TXT record.** Two SPF records = automatic fail at
the receiver. Merge them: `v=spf1 include:spf.thundermail.com include:_their_old_provider ~all`.

### 2d. TTL / not-yet-propagated

If the records look right but the customer *just* added them, propagation can lag
by the TTL (often 300–3600s, sometimes longer on slow providers). Confirm with
`@1.1.1.1` **and** `@8.8.8.8`; if one resolver sees it and another doesn't, it's
still propagating. Ask them to wait, don't escalate.

---

## 3. SPF deep-dive

```bash
dig +short example.com TXT @1.1.1.1 | grep spf1
```

What to check:
- **Exactly one** record starting `v=spf1`.
- Contains `include:spf.thundermail.com`.
- If the customer also sends from their own webhost/CRM, those includes must be
  present too (e.g. `include:relay.theirwebhost.example ip4:203.0.113.10`).
- Ends in `~all` (softfail) or `-all` (hardfail). `+all` is dangerous — flag it.
- **10-lookup limit:** SPF allows max 10 DNS lookups (each `include` counts).
  Too many includes → `permerror` → SPF fails even though it "looks" fine.

---

## 4. DMARC deep-dive

```bash
dig +short _dmarc.example.com TXT @1.1.1.1
```

- Must start `v=DMARC1`.
- `p=none` = monitor only (mail still delivered; good default while setting up).
- `p=quarantine` = failing mail → spam folder. `p=reject` = failing mail bounced.
- **If a customer reports mail bouncing and they have `p=reject`,** a *single*
  failing auth check (often the double-appended DKIM record from §2a) is enough to
  hard-bounce. Fix DKIM/SPF first, or temporarily relax to `p=none`.
- DMARC passes if **either** SPF **or** DKIM passes *and* is aligned. So a working
  DKIM CNAME usually rescues a domain even if SPF is imperfect.

---

## 5. MTA-STS / TLS-RPT and the `.well-known` redirects

Thundermail publishes an MTA-STS policy and expects the autoconfig
`.well-known` endpoints to redirect to `mail.thundermail.com`.

```bash
# Policy DNS records
dig +short TXT _mta-sts.example.com @1.1.1.1
dig +short TXT _smtp._tls.example.com @1.1.1.1
dig +short CNAME mta-sts.example.com @1.1.1.1     # → mta-sts.thundermail.com.

# Autoconfig redirects — see the mta-sts-check.sh helper (kept with infra tooling)
# which verifies https://{tb.pro,thundermail.com}/.well-known/{caldav,carddav,jmap}
# redirect to mail.thundermail.com (a 200 with the wrong Location is still a FAIL).
```

---

## 6. When it's **us**, not the customer (escalation triggers)

Sometimes the customer's DNS is *perfect* and mail still isn't signed. We have hit
this for real — don't make the customer chase a phantom DNS bug.

**Signature:** all `tmN._domainkey` CNAMEs resolve correctly, SPF/MX/DMARC are
correct, the domain shows **Verified** in Thundermail — but outgoing mail has **no
`DKIM-Signature` header** (confirm at https://learndmarc.com or by viewing raw
headers of a test message).

**Known root cause (fixed):** Thundermail's mail server (Stalwart) selects the
signing key by a constructed ID like `rsa-<domain>` / `ed25519-<domain>`. Custom-
domain signatures were once created with a mismatched/empty ID, so the signer
couldn't find them and silently signed nothing.
- Fix: [thunderbird/thunderbird-accounts#1023](https://github.com/thunderbird/thunderbird-accounts/pull/1023)
- Tracking: [thunderbird/platform-infrastructure#591](https://github.com/thunderbird/platform-infrastructure/issues/591)
- Domains onboarded *before* the fix may need their signatures backfilled
  (re-created) — that's a platform task, not something the customer can fix.

**What to do:** if DNS checks all pass but there's no signature, **escalate to the
platform team** with the domain name, a raw copy of a test message's headers, and
a note that DNS is verified clean. Reference #591.

**Other server-side / receiver-side cases we've seen:**
- **Telekom / Magenta rejection** (`mx00.magenta.de rejected…`) —
  [thunderbird/mailstrom#226](https://github.com/thunderbird/mailstrom/issues/226).
  Strict receiver; verify SPF+DKIM+DMARC all pass and check sending-IP reputation.
- **SES-backed senders** (internal apps, not customer custom domains) live in the
  `mzla-workloads` AWS account, **`eu-central-1`**. Check with:
  ```bash
  aws ses get-identity-dkim-attributes --identities thunderbird.net \
    --region eu-central-1   # want "DkimStatus": "SUCCESS"
  aws ses get-account-sending-enabled --region eu-central-1
  ```
  A domain can be `Verified: true` but `DkimStatus: PENDING/FAILED` — always check
  DKIM status explicitly, and remember verification is **per-region**.

---

## 7. Decision tree (tl;dr)

```
Customer: "mail from my custom domain goes to spam / isn't signed"
│
├─ Run §1 triage.
│
├─ Any tmN._domainkey CNAME missing/wrong?
│   ├─ Doubled domain (§2a)? → tell them to enter just "tm1._domainkey"
│   ├─ Orange cloud (§2b)?   → tell them to set DNS-only
│   └─ Otherwise             → have them re-add the exact CNAME from §0
│
├─ SPF missing / duplicated / >10 lookups? → §3
├─ DMARC p=reject + a failing check?       → fix auth or relax to p=none (§4)
│
└─ ALL DNS correct + Verified, but NO DKIM-Signature header?
    → NOT a customer issue. Escalate to platform, ref #591 (§6).
```

---

## 8. Quick reference — copy/paste lookups

```bash
d=example.com
dig +short tm1._domainkey.$d CNAME @1.1.1.1      # DKIM RSA
dig +short tm2._domainkey.$d CNAME @1.1.1.1      # DKIM Ed25519
dig +short $d TXT @1.1.1.1 | grep spf1           # SPF
dig +short $d MX @1.1.1.1                         # MX
dig +short _dmarc.$d TXT @1.1.1.1                 # DMARC
dig +short TXT _mta-sts.$d @1.1.1.1              # MTA-STS
dig +noall +answer tm1._domainkey.$d CNAME       # full record w/ TTL
```

External validators to share with customers:
- https://learndmarc.com — step-by-step SPF/DKIM/DMARC of a sent message
- https://www.mail-tester.com — send a test, get a deliverability score
- https://mxtoolbox.com/SuperTool.aspx — one-off DNS/blacklist checks

---

*Maintainers: keep §0 in sync with whatever Thundermail's onboarding UI shows the
customer. If the selectors (`tm1/tm2/tm3`), the `spf.thundermail.com` include, the
`mail.thundermail.com` MX, or the `dkim.thunderhosted.com` CNAME target ever
change, this file is wrong until you update it.*
