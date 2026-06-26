#!/bin/bash
# tbpro-dns-check.sh <domain>
# One-shot PASS/FAIL audit of a Thundermail custom domain's email DNS.
# Checks DKIM (tm1/tm2 CNAMEs), SPF, MX, and DMARC against the expected values.
# Companion to mta-sts-check.sh. See EMAIL-DNS-DEBUGGING.md for what to do on FAIL.

set -u

D="${1:-}"
if [[ -z "$D" ]]; then
  echo "usage: $0 <domain>" >&2
  exit 2
fi

R="@1.1.1.1"            # public resolver — see what the internet sees
fail=0

row() { printf "%-34s  %-7s  %s\n" "$1" "$2" "$3"; }
row "CHECK" "RESULT" "VALUE / NOTE"
row "-----" "------" "------------"

check_cname() {  # name  expected-substring
  local got; got=$(dig +short "$1" CNAME $R | sed 's/\.$//')
  if [[ "$got" == *"$2"* ]]; then row "$1" "PASS" "$got"
  else row "$1" "FAIL" "${got:-<empty>} (want *$2*)"; fail=1; fi
}

check_cname "tm1._domainkey.$D" "dkim.thunderhosted.com"
check_cname "tm2._domainkey.$D" "dkim.thunderhosted.com"

# SPF: exactly one v=spf1 record, must include spf.thundermail.com
spf_all=$(dig +short "$D" TXT $R | tr -d '"' | grep -i 'v=spf1')
spf_n=$(printf '%s\n' "$spf_all" | grep -c 'v=spf1')
if [[ -z "$spf_all" ]]; then
  row "SPF" "FAIL" "<no v=spf1 record>"; fail=1
elif [[ "$spf_n" -gt 1 ]]; then
  row "SPF" "FAIL" "$spf_n SPF records (must be exactly 1)"; fail=1
elif [[ "$spf_all" == *"spf.thundermail.com"* ]]; then
  row "SPF" "PASS" "$spf_all"
else
  row "SPF" "FAIL" "$spf_all (missing include:spf.thundermail.com)"; fail=1
fi

# MX: should point at mail.thundermail.com
mx=$(dig +short "$D" MX $R | awk '{print $2}' | sed 's/\.$//')
if [[ "$mx" == *"mail.thundermail.com"* ]]; then row "MX" "PASS" "$mx"
else row "MX" "FAIL" "${mx:-<empty>} (want mail.thundermail.com)"; fail=1; fi

# DMARC: present, starts v=DMARC1 (policy strength is informational)
dmarc=$(dig +short "_dmarc.$D" TXT $R | tr -d '"')
if [[ "$dmarc" == v=DMARC1* ]]; then row "DMARC" "PASS" "$dmarc"
else row "DMARC" "FAIL" "${dmarc:-<none>}"; fail=1; fi

echo
if [[ "$fail" -eq 0 ]]; then
  echo "All DNS checks PASS. If mail is still unsigned, see EMAIL-DNS-DEBUGGING.md §6 (escalate)."
else
  echo "One or more FAIL. See EMAIL-DNS-DEBUGGING.md §2 for the common customer fixes."
fi
exit $fail
