You are summarizing merged pull requests for a weekly internal team digest.

Each PR entry below includes the PR title, the author, the reviewers, and the description.

Group the PRs by app or library. Infer the app/library name from the PR description text which will include a list of files changed. Ignore files such as documentation, tests, or configuration files that don't indicate the main app/library. Focus on the core code changes to determine the app/library.
Do NOT include "APD" in any app or library name — drop it and use only the core name (e.g. "apd_msgraph" becomes "MS Graph", "apd_quickbooksonline" becomes "QuickBooks Online").

Output a markdown table using this exact structure:

| App / Library | Author/Reviewer | Updates |
|---|---|---|
| Name | (A) name<br>(R) name | - capability<br>- capability |

Rules:
- One row per app/library, sorted alphabetically by app name.
- Author/Reviewer cell: unique author and reviewer names from the PR data only, one per line separated by <br> — do not infer or change names. If Author place (A) before the name, if Reviewer place (R) before the name, if both place (A/R) before the name. Leave blank if none.  I.E. (A) Alice Smith<br>(R) Bob Jones
- Updates cell: concise functional bullets separated by <br> describing what the code now does.
- Output only the markdown table — no prose, no code fences, no headings.

Week: {week_label}
Repository: {github_owner}/{github_repo}

Merged PRs this week:
{pr_text}
