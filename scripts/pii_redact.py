"""Shared PII redaction for all repo output — committed or local.

Every generator that writes customer-facing text must import from here and
redact/paraphrase BEFORE writing files. PII must never exist in any repo file.
"""
from __future__ import annotations

import re

# Infrastructure-only — never block these in redact() domain pass
_INFRA_DOMAINS = (
    "thunderbird", "mozilla", "mzla", "zendesk", "github", "support",
    "connect", "fonts", "googleapis", "gstatic", "cdnjs", "unpkg",
    "chartjs", "phosphor-icons",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
PARTIAL_EMAIL_RE = re.compile(
    r"(\[(?:edited|redacted|email\s*removed|removed)\]|[^\s\[\]@]+)@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}",
    re.I,
)
URL_RE = re.compile(r"https?://[^\s<>\"']+", re.I)
SOCIAL_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:facebook|fb|instagram|twitter|x|linkedin)\.com/[^\s<>\"']+",
    re.I,
)
# Play Console developer account IDs and internal console URLs — never in repo
PLAY_CONSOLE_RE = re.compile(
    r"play\.google\.com/console|8696262544613553264|developers/\d+/app|pubsite_prod_\d+",
    re.I,
)

PII_PATTERNS = [
    (EMAIL_RE, "[email]"),
    (PARTIAL_EMAIL_RE, "[email]"),
    (
        re.compile(
            r"(?<!\w)(?!(?:"
            + "|".join(_INFRA_DOMAINS)
            + r")\b)"
            r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.){1,}"
            r"(?:com|net|org|io|co|de|fr|uk|nl|eu|me|app|mail|email|pro|biz|info|ca|day)\b",
            re.I,
        ),
        "[domain]",
    ),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), "[ip]"),
    (
        re.compile(
            r"(?<!\w)(?:\+?\d{1,3}[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?!\w)"
        ),
        "[phone]",
    ),
    (re.compile(r"(?<!\w)\d{7,}(?!\w)"), "[number]"),
    (SOCIAL_URL_RE, "[social link]"),
    (URL_RE, "[link]"),
    (re.compile(r"\bOn\b[^\n]{0,80}?\bwrote:", re.I), "[quoted message]"),
    (re.compile(r"(?m)^\s*[A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2}\s+wrote:"), "[name] wrote:"),
    (re.compile(r"From:\s+[^<\n]+<[^>]+>"), "From: [sender]"),
    (
        re.compile(
            r"((?i:Thanks|Thank you|Sincerely|Best regards|Best wishes|Kind regards|"
            r"Warm regards|Regards|Cheers|Yours sincerely|Yours truly|"
            r"Cordialement|Cordialmente|Saludos|Un saludo|Atentamente|"
            r"Mit freundlichen Grüßen|Viele Grüße|Mit besten Grüßen|Liebe Grüße|"
            r"Grazie|Cordiali saluti|Distinti saluti|"
            r"Atenciosamente|Abraços|Met vriendelijke groet))"
            r"\s*[,.!]?\s*\n?\s*([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"
        ),
        r"\1, [name]",
    ),
    (
        re.compile(
            r"((?i:Hi|Hello|Hey|Dear|Bonjour|Salut|Hola|Hallo|Liebe[rn]?|Ciao|Olá|Beste))"
            r"\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"
        ),
        r"\1 [name]",
    ),
    (
        re.compile(r"((?i:my name is))\s+([A-Z][\w'-]+(?:\s+[A-Z][\w'-]+){0,2})"),
        r"\1 [name]",
    ),
]

# Thematic one-liners — never emit verbatim review text in public files
_REVIEW_THEMES: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"notif|push|sync|synchroni|fetch|delayed|15.?min|benachrichtig|"
            r"abruf|poll|background|refresh|neu laden|receiv",
            re.I,
        ),
        "Reports delayed or missing notifications; sync often requires manual refresh.",
    ),
    (
        re.compile(r"spam|junk|filter|no way to add mail as spam", re.I),
        "Reports no way to mark mail as spam or junk.",
    ),
    (
        re.compile(r"crash|freeze|force.?close|absturz|won.?t start|angehalten", re.I),
        "Reports app crashes or freezes, especially on startup or when deleting mail.",
    ),
    (
        re.compile(r"outbox|stuck.*send|send.*fail|cannot.*send|sending.*error", re.I),
        "Reports outgoing mail stuck in outbox or send failures.",
    ),
    (
        re.compile(r"calendar|kalend|agenda|ical|caldav", re.I),
        "Reports missing calendar support or calendar sync issues.",
    ),
    (
        re.compile(r"qr.?cod|import.*sett|setting.*import", re.I),
        "Reports difficulty importing settings or using QR setup.",
    ),
    (
        re.compile(r"header|kopf|print.*mail|drucken", re.I),
        "Reports missing email headers or print capability.",
    ),
    (
        re.compile(r"oauth|authentic|password|login|sign.?in", re.I),
        "Reports authentication failures or repeated password prompts.",
    ),
    (
        re.compile(r"battery|akku|optimi", re.I),
        "Reports background sync blocked by battery optimisation settings.",
    ),
    (
        re.compile(r"update|aktualisier|since.*version|regression|broke.*after", re.I),
        "Reports feature worked before but broke after an app update.",
    ),
]

_SUMO_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(
            r"recover|restore|undelete|deleted.*email|missing.*email|disappeared|"
            r"lost.*email|emails.*gone|profile.*deleted",
            re.I,
        ),
        "Recover missing or deleted mail",
    ),
    (
        re.compile(
            r"oauth|password|sign.?in|login|authentic|2fa|app.?password|"
            r"credential|authoriz",
            re.I,
        ),
        "Account sign-in or authentication issue",
    ),
    (
        re.compile(
            r"update|upgrade|since.*version|after.*update|regression|"
            r"stopped working|no longer",
            re.I,
        ),
        "Problem started after an update",
    ),
    (
        re.compile(r"imap|smtp|server|connect|connection|cannot connect", re.I),
        "Mail server connection issue",
    ),
    (
        re.compile(r"calendar|caldav|ical|schedule", re.I),
        "Calendar or scheduling issue",
    ),
    (
        re.compile(r"filter|spam|junk", re.I),
        "Mail filtering or spam handling",
    ),
    (
        re.compile(r"send|outbox|outgoing|sent folder", re.I),
        "Outgoing mail or send failure",
    ),
    (
        re.compile(r"profile|folder|archive|import|export|backup", re.I),
        "Profile, folder, or local data issue",
    ),
    (
        re.compile(r"menu|toolbar|display|layout|theme|font", re.I),
        "UI layout or display question",
    ),
    (
        re.compile(r"attach|msg file|open.*file", re.I),
        "Attachment or file format question",
    ),
]


def redact(text: str | None) -> str:
    """Strip PII from arbitrary customer-facing text."""
    if not text:
        return text or ""
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    text = PLAY_CONSOLE_RE.sub("[play-console-id]", text)
    return text


def redact_sumo_title(title: str | None, max_len: int = 80) -> str:
    """Return a generic paraphrase of a SUMO question title — never raw subject text."""
    if not title or not str(title).strip():
        return "Support question"
    blob = redact(str(title))
    for pat, label in _SUMO_PATTERNS:
        if pat.search(blob):
            return label[:max_len]
    return "Support question (details redacted)"[:max_len]


def paraphrase_review(text: str | None, max_len: int = 160, **_kw) -> str | None:
    """Return a thematic one-line paraphrase — never verbatim review text."""
    if not text or not str(text).strip():
        return None
    blob = str(text)
    for pat, summary in _REVIEW_THEMES:
        if pat.search(blob):
            return summary[:max_len]
    return "Reports a negative experience with this feature area."[:max_len]


def safe_play_link(link: str | None) -> str:
    """Return Play Store link only if it contains no Play Console developer account IDs."""
    if not link:
        return ""
    if PLAY_CONSOLE_RE.search(link):
        return ""
    return link
