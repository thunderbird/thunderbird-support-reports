Add a community signal entry to data/tbpro_community.json and regenerate the daily report.

Usage: /community <source> <note1> | <note2> | ...
  - source: channel name (e.g. "Early Birds Matrix Channel", "Reddit", "Discord")
  - notes: pipe-separated list of signals or questions

Steps:
1. Read data/tbpro_community.json
2. Add a new entry for today's date with the given source and notes. Split notes on " | " to get individual items.
   - If the note starts with "?" or sounds like a question, put it in "questions"
   - Otherwise put it in "signals"
   - If today already has an entry for this source, append to it rather than creating a duplicate
3. Write the updated file
4. Run: `uv run scripts/tbpro_daily.py`
5. Commit and push: use the standard git commit pattern from CLAUDE.md
6. Confirm done and give the live report link.

Example: /community "Early Birds Matrix Channel" Setup fails when cookies disabled | User found workaround for DKIM
