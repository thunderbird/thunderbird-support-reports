Trigger the Thundermail daily GH Actions workflow and wait for it to complete.

Steps:
1. Run: `gh workflow run tbpro-daily.yml --repo thunderbird/thunderbird-support-reports`
2. Wait 5 seconds, then get the run ID: `gh run list --repo thunderbird/thunderbird-support-reports --workflow tbpro-daily.yml --limit 1 --json databaseId --jq '.[0].databaseId'`
3. Watch until complete: `gh run watch <id> --repo thunderbird/thunderbird-support-reports 2>&1 | tail -4`
4. Report: "Done — Pages deploying, live in ~60 seconds." and include the live report link.

If the run fails, report the failure and show the last 10 lines of the run log.
