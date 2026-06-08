Add a ticket to EXCLUDE_IDS or MANUAL_THEMES in scripts/tbpro_daily.py, then regenerate and push.

Usage:
  /exclude <ticket_id> [reason]          — add to EXCLUDE_IDS (full suppression)
  /exclude theme <ticket_id> <"theme">   — add to MANUAL_THEMES (force-assign a category)

Steps:
1. Read scripts/tbpro_daily.py to find the EXCLUDE_IDS or MANUAL_THEMES constant
2. Add the ticket ID with a comment showing the reason/subject
3. Write the file
4. Run: `uv run scripts/tbpro_daily.py`
5. Commit and push using the standard git commit pattern from CLAUDE.md
6. Confirm done.

EXCLUDE_IDS = full suppression (ticket + linked incidents removed from all counts)
MANUAL_THEMES = force-assign a theme for tickets that can't be auto-classified (e.g. follow-up tickets where the subject gives no signal)

Example: /exclude 5441 infrastructure test ticket
Example: /exclude theme 6055 "Account access issues"
