# Thundermail — Flight 3 Live Report · 2026-07-07

_Updated: **2026-07-07 23:14 ET** · refreshes hourly_  
_24h window: 2026-07-06T16:00 → 2026-07-07T16:00 ET · Flight 3 launch: 2026-06-22 · 6500 invitees_

## TL;DR

Flight 3 is **day 16** of rollout — **6,500 invitees**, **98 tickets** so far (1.5% contact rate). CSAT since launch: **100%**. Top theme: **Account access issues**. **1 known problem(s)** being tracked.

## At a glance

- **13** new tickets in last 24h · **7** solved in last 24h
- **98** tickets total since launch · contact rate **2%** of 6500 invitees
- **CSAT (24h)**: 100%  (1 good / 0 bad)
- **CSAT (since launch)**: 100%  (18 good / 0 bad)
- **New FeatureOS ideas (24h)**: 0 · **since launch**: 20
- **Median AHT**: 51.8h · mean 84.2h (proxy: updated_at − created_at, 64 solved tickets)

## 🔎 Emerging patterns to investigate

_Phrases appearing in 24h tickets at significantly above-baseline rates. If a row points at multiple new tickets and the phrase doesn't match an existing known problem, it's a candidate for a new one._

- **"early bird"** — 3 tickets in 24h (15.0× baseline; baseline 3 cum) — [#6664](https://tbpro.zendesk.com/agent/tickets/6664), [#6680](https://tbpro.zendesk.com/agent/tickets/6680), [#6685](https://tbpro.zendesk.com/agent/tickets/6685)
- **"received invitation"** — 2 tickets in 24h (15.0× baseline; baseline 2 cum) — [#6675](https://tbpro.zendesk.com/agent/tickets/6675), [#6685](https://tbpro.zendesk.com/agent/tickets/6685)

## Known problems — 1 problem(s), 2 incident(s)

### [#6512](https://tbpro.zendesk.com/agent/tickets/6512) · [hold] · [Accounts PR1023] Custom-domain outbound mail not being DKIM-signed
- 2 incident(s):
  - [#6496](https://tbpro.zendesk.com/agent/tickets/6496) · [hold] · 2026-06-30 · _Custom Domain DKIM not working_
  - [#6598](https://tbpro.zendesk.com/agent/tickets/6598) · [hold] · 2026-07-03 · _DKIM keys not published for lund.to — CNAME targets return NXDOMAIN_

## Other tickets linked to GitHub — 1 ticket(s) → 1 issue(s)

- 🔧 [zd #6606](https://tbpro.zendesk.com/agent/tickets/6606) → [thunderbird/appointment#580](https://github.com/thunderbird/appointment/issues/580) · _All day events bleed into the next day _

## Negative CSAT (since launch)

_No negative ratings since launch._

## Refund & cancellation tickets (last 24h) — 1

- [6690](https://tbpro.zendesk.com/agent/tickets/6690) · [pending] · _Refund_
  > Hello. I changed my mind and canceled my subscription and would like to refund and close my account.

## New ideas on FeatureOS

**Last 24h** — 0 new:

- _(none)_

## Status breakdown (cumulative)

- **solved**: 64
- **pending**: 24
- **hold**: 6
- **open**: 4

## Service (cumulative)

- **Account Hub**: 46
- **Thundermail**: 42
- **Appointment**: 5
- **Send**: 2

## Why × How (cumulative)

_How the user arrived (why) and how we resolved it (how) — agent-assigned per ticket._

- **curious** + **explained**: 22
- **blocked** + **explained**: 14
- **request** + **redirected**: 9
- **confused** + **explained**: 8
- **change request** + **actioned**: 8
- **blocked** + **investigated**: 6
- **blocked** + **escalated**: 3
- **change request** + **escalated**: 2
- **concerned** + **explained**: 2
- **curious** + **investigated**: 1
- **request** + **informed**: 1
- **telling us** + **—**: 1
- **blocked** + **redirected**: 1
- **blocked** + **actioned**: 1
- **curious** + **informed**: 1
- **concerned** + **investigated**: 1
- **request** + **actioned**: 1
- **blocked** + **n/a**: 1

## Tickets in last 24h — by theme

### Account access issues — 3 tickets

- **[#6678](https://tbpro.zendesk.com/agent/tickets/6678)** · no confirmation email
  > Yesterday I received my email to signup for Thundermail. I filled out the fields, but when I got to the confirmation email, I never received it despite trying the resend multiple…
- **[#6675](https://tbpro.zendesk.com/agent/tickets/6675)** · I have been invited but cannot login — why: **blocked** · how: **investigated**
  > Hello, I received an invitation for Thundermail but when I try to login using the email rudy@kameereddy, I have to reset the password, but no email is received on the recovery…
- **[#6663](https://tbpro.zendesk.com/agent/tickets/6663)** · Can't access my Thunderbird pro account? — why: **blocked** · how: **explained**
  > Hello, very excited today as I received my invite for Thunderbird Pro! I've tried signing up but I had some weirdness using Firefox and the signup portal and for some reason my @…

### Account access issues — Account Hub trouble — 2 tickets

- **[#6682](https://tbpro.zendesk.com/agent/tickets/6682)** · Email confirmations not received — why: **blocked** · how: **escalated**
  > Have a pattern of email confirmations not received by the end user (some customers, some not yet subscribed). Being investigated by Mel:…
- **[#6680](https://tbpro.zendesk.com/agent/tickets/6680)** · locked out of early bird access account — why: **blocked** · how: **explained**
  > Oof. Must have typo'd my password to my earlybird account. Confirmed username, verified email. Tried to login. Error: Invalid username or password. Can't receive reset because…

### Custom domain / DKIM / DNS — 2 tickets

- **[#6672](https://tbpro.zendesk.com/agent/tickets/6672)** · Difficulties configuring my custom domain's DNS records
  > Hi, I'm trying to configure my custom domain's DNS records as defined in Thundermail. Unfortunately, several days later the verification fails. Refer attached…
- **[#6668](https://tbpro.zendesk.com/agent/tickets/6668)** · smtp — why: **curious** · how: **investigated**
  > I have a homelab and it needs to send mails to me for notifications. I use my custom domain to send the mails to my other mail address. Can i use thundermail smtp to send the…

### Pre-purchase / documentation gap — 1 tickets

- **[#6686](https://tbpro.zendesk.com/agent/tickets/6686)** · Thundermail vs Fastmail — why: **curious** · how: **explained**
  > Hello — I love Mozilla and use Firefox religiously. I'm trying to grok how Thundermail will compare to Fastmail, which I've already used for years and have multiple custom domains…

### Request or complaint — 1 tickets

- **[#6688](https://tbpro.zendesk.com/agent/tickets/6688)** · I'd like an option to make my @[domain] address my primary & subscription address, and turn @[domain] into an alias — why: **request** · how: **redirected**
  > There's more character input when providing my new thundermail address than there is for the gmail account I'm leaving - I'd like to be able to switch my subscription, login info,…

### App setup / configuration — 1 tickets

- **[#6687](https://tbpro.zendesk.com/agent/tickets/6687)** · Gmail flagged my outgoing test email as spam -_- — why: **concerned** · how: **explained**
  > Hey [name], Gmail has flagged an outgoing test email from my primary account [email] as spam

### Early bird / invite / waitlist — 1 tickets

- **[#6685](https://tbpro.zendesk.com/agent/tickets/6685)** · Invitation early bird plan — why: **curious** · how: **explained**
  > Dear [name], I have received am invitation to subscribe and I would like to do so with my own domain. However I see in the early bird plan that I will get 1 mailbox with 15…

### Early bird signup — 1 tickets

- **[#6664](https://tbpro.zendesk.com/agent/tickets/6664)** · Question About the Early Bird Sign Up — why: **confused** · how: **explained**
  > Dear [name], I’ve been waiting since early last year to sign up, and I received today’s email about completing payment. I noticed that only @[domain] is currently available.…

### MFA / two-factor — 1 tickets

- **[#6662](https://tbpro.zendesk.com/agent/tickets/6662)** · 2FA or passkey? — why: **curious** · how: **explained**
  > As far as I can tell, Thunderbird Pro only uses a username and password. Am I missing settings for more robust security like 2FA or a passkey?

## New tickets — last 24h

- [6662](https://tbpro.zendesk.com/agent/tickets/6662) · [pending] · 2026-07-06T20:30 · 2FA or passkey?
- [6663](https://tbpro.zendesk.com/agent/tickets/6663) · [pending] · 2026-07-06T20:58 · Can't access my Thunderbird pro account?
- [6664](https://tbpro.zendesk.com/agent/tickets/6664) · [pending] · 2026-07-06T22:20 · Question About the Early Bird Sign Up
- [6668](https://tbpro.zendesk.com/agent/tickets/6668) · [pending] · 2026-07-07T07:29 · smtp
- [6672](https://tbpro.zendesk.com/agent/tickets/6672) · [pending] · 2026-07-07T10:04 · Difficulties configuring my custom domain's DNS records
- [6675](https://tbpro.zendesk.com/agent/tickets/6675) · [pending] · 2026-07-07T12:09 · I have been invited but cannot login
- [6678](https://tbpro.zendesk.com/agent/tickets/6678) · [pending] · 2026-07-07T14:26 · no confirmation email
- [6680](https://tbpro.zendesk.com/agent/tickets/6680) · [pending] · 2026-07-07T15:18 · locked out of early bird access account
- [6682](https://tbpro.zendesk.com/agent/tickets/6682) · [solved] · 2026-07-07T15:38 · Email confirmations not received
- [6685](https://tbpro.zendesk.com/agent/tickets/6685) · [pending] · 2026-07-07T17:43 · Invitation early bird plan
- [6686](https://tbpro.zendesk.com/agent/tickets/6686) · [open] · 2026-07-07T18:22 · Thundermail vs Fastmail
- [6687](https://tbpro.zendesk.com/agent/tickets/6687) · [pending] · 2026-07-07T19:02 · Gmail flagged my outgoing test email as spam -_-
- [6688](https://tbpro.zendesk.com/agent/tickets/6688) · [pending] · 2026-07-07T19:09 · I'd like an option to make my @[domain] address my primary & subscription address, and turn @[domain

## Solved — last 24h

- · [6401](https://tbpro.zendesk.com/agent/tickets/6401) · 2026-07-07T06:08 · Outgoing messages with custom domain not being signed with DKIM
- · [6579](https://tbpro.zendesk.com/agent/tickets/6579) · 2026-07-07T14:02 · Request to remove PII from Thundermail Ideas page
- 👍 [6610](https://tbpro.zendesk.com/agent/tickets/6610) · 2026-07-07T14:17 · no way to recreate the original Thundermail calendar.
- · [6461](https://tbpro.zendesk.com/agent/tickets/6461) · 2026-07-07T16:02 · Calender
- · [6682](https://tbpro.zendesk.com/agent/tickets/6682) · 2026-07-07T16:29 · Email confirmations not received
- · [6624](https://tbpro.zendesk.com/agent/tickets/6624) · 2026-07-07T17:02 · Refund
- · [6555](https://tbpro.zendesk.com/agent/tickets/6555) · 2026-07-07T19:41 · Adding custom domain

---
_**Legend:** 🔎 emerging pattern · 🔧 open GitHub issue · ✅ closed GitHub issue · 🔗 linked issue · 👍 positive CSAT · 👎 negative CSAT_
