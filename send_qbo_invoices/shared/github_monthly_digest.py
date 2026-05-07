"""
GitHub Monthly Digest
- Secrets via AWS Secrets Manager
- PRs merged last month from GitHub REST API
- AI summary via Azure OpenAI
- Email via Microsoft Graph API (apd_msgraph_v2 wrapper)

Schedule: Last day of each month via Windows Task Scheduler.
"""

import logging
import os
import requests
import boto3
import apd_common
import apd_clickup as clickup
import apd_msgraph_v2 as msgraph
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta


# ── GitHub Config ─────────────────────────────────────────────────────────────
GITHUB_OWNER  = "AutomataPracDevClients"
GITHUB_REPO   = "APD_Code_Libraries"
GITHUB_BRANCH = "main"

# ── Email Config ──────────────────────────────────────────────────────────────
EMAIL_FROM = os.environ.get("MONTHLY_DIGEST_EMAIL_FROM", "whartman@automatapracdev.com")
EMAIL_TO   = os.environ.get("MONTHLY_DIGEST_EMAIL_TO", "whartman@automatapracdev.com")
# ─────────────────────────────────────────────────────────────────────────────


def _gh_headers(pat: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def resolve_login(pat: str, login: str, cache: dict[str, str]) -> str:
    if login in cache:
        return cache[login]
    try:
        resp = requests.get(f"https://api.github.com/users/{login}", headers=_gh_headers(pat))
        resp.raise_for_status()
        name = resp.json().get("name") or login
    except Exception:
        name = login
    cache[login] = name
    return name


def get_prs_last_month(pat: str) -> list[dict[str, str]]:
    """Fetch PRs merged into main during the past calendar month, with reviewer info."""
    now = datetime.now(timezone.utc)
    since = (now - relativedelta(months=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    until = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    headers = _gh_headers(pat)
    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls"
    params = {"state": "closed", "base": GITHUB_BRANCH, "per_page": 100}

    prs = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for pr in batch:
            merged_at = pr.get("merged_at")
            if not merged_at:
                continue
            merged_dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
            if since <= merged_dt < until:
                prs.append(pr)
            elif merged_dt < since:
                return prs
        page += 1

    return prs


def build_pr_text(pat: str, prs: list[dict[str, str]]) -> str:
    """Build structured PR text for the AI prompt, with resolved display names."""
    name_cache: dict[str, str] = {}
    lines = []

    for pr in prs:
        title = pr["title"]
        number = pr["number"]
        author_login = pr["user"]["login"]
        author_name = resolve_login(pat, author_login, name_cache)

        # Fetch approved reviewers
        reviews_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/pulls/{number}/reviews"
        try:
            rev_resp = requests.get(reviews_url, headers=_gh_headers(pat))
            rev_resp.raise_for_status()
            reviewed_logins: set[str] = {
                r["user"]["login"]
                for r in rev_resp.json()
                if r.get("state") == "APPROVED" and r["user"]["login"] != author_login
            }
            reviewer_names = [
                resolve_login(pat, login, name_cache)
                for login in sorted(reviewed_logins)
            ]
        except Exception:
            reviewer_names = []

        reviewers_str = ", ".join(reviewer_names) if reviewer_names else ""
        body = (pr.get("body") or "").strip()
        lines.append(f"PR #{number}: {title} | Author: {author_name} | Reviewers: {reviewers_str} | Description: {body}")

    return "\n".join(lines)


def generate_summary(openai_vault: dict[str, str], pr_text: str, month_label: str) -> str:
    """Call Azure OpenAI to produce an HTML table summary from PR data."""
    endpoint    = openai_vault["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment  = openai_vault["AZURE_OPENAI_DEPLOYMENT"]
    api_version = openai_vault["AZURE_OPENAI_API_VERSION"]
    api_key     = openai_vault["AZURE_OPENAI_API_KEY"]

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    prompt = f"""You are summarizing merged pull requests for a monthly internal team digest email.

Each PR entry below includes the PR title, the author, and the reviewers as separate fields.

Group the PRs by app or library. Infer the app/library name from the PR description text which will include a list of files changed. Ignore files such as documentation, tests, or configuration files that don't indicate the main app/library. Focus on the core code changes to determine the app/library.
Do NOT include "APD" in any app or library name — drop it and use only the core name (e.g. "apd_msgraph" becomes "MS Graph", "apd_quickbooksonline" becomes "QuickBooks Online").

Output the email as HTML using this exact structure:

<p>Here are the changes that were made to the APD Code Library.</p>

<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;">
  <thead>
    <tr style="background-color:#f2f2f2;">
      <th style="text-align:left;">App / Library</th>
      <th style="text-align:left;">Author</th>
      <th style="text-align:left;">Reviewer</th>
      <th style="text-align:left;">Updates</th>
    </tr>
  </thead>
  <tbody>
    <!-- One <tr> per app/library, sorted alphabetically by app name.
         Author cell: unique author names from the PR data, one per line separated by <br> — do not infer or change names.
         Reviewer cell: unique reviewer names from the PR data, one per line separated by <br> — do not infer or change names. Leave blank if none.
         Updates cell: bullet list of what the code now does based on the PR titles. Be concise and functional. -->
  </tbody>
</table>

Do not include a subject line, greeting, sign-off, or any prose outside this structure. Output only valid HTML — no markdown, no code fences.

Month: {month_label}
Repository: {GITHUB_OWNER}/{GITHUB_REPO}

Merged PRs this month:
{pr_text}"""

    resp = requests.post(
        url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0,
        },
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


def generate_markdown_summary(openai_vault: dict[str, str], pr_text: str, month_label: str) -> str:
    """Call Azure OpenAI to produce a markdown table summary from PR data."""
    endpoint    = openai_vault["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment  = openai_vault["AZURE_OPENAI_DEPLOYMENT"]
    api_version = openai_vault["AZURE_OPENAI_API_VERSION"]
    api_key     = openai_vault["AZURE_OPENAI_API_KEY"]

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    prompt = f"""You are summarizing merged pull requests for a monthly internal team digest.

Each PR entry below includes the PR title, the author, the reviewers, and the description.

Group the PRs by app or library. Infer the app/library name from the PR description text which will include a list of files changed. Ignore files such as documentation, tests, or configuration files that don't indicate the main app/library. Focus on the core code changes to determine the app/library.
Do NOT include "APD" in any app or library name — drop it and use only the core name (e.g. "apd_msgraph" becomes "MS Graph", "apd_quickbooksonline" becomes "QuickBooks Online").

Output markdown blocks using this exact structure for each app/library, sorted alphabetically by name:

**{{App / Library Name}}**
Author: {{unique author names, comma-separated}}
Reviewer: {{unique reviewer names, comma-separated — omit this line if none}}
- {{Capability bullet — what the code now does. Be concise and functional.}}

Rules:
- One block per app/library, sorted alphabetically by app name.
- Author: unique author names from the PR data only — do not infer or change names.
- Reviewer: unique reviewer names from the PR data only — omit the line entirely if there are no reviewers.
- Bullets: one per distinct capability, concise and functional.
- Separate each block with a blank line.
- Output only the markdown blocks — no prose, no table, no code fences, no headings.

Month: {month_label}
Repository: {GITHUB_OWNER}/{GITHUB_REPO}

Merged PRs this month:
{pr_text}"""

    resp = requests.post(
        url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0,
        },
    )
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"].strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[-1]
    if content.endswith("```"):
        content = content.rsplit("```", 1)[0]
    return content.strip()


def github_monthly_digest() -> bool:
    logging.basicConfig(
        level=logging.INFO,
        format='%(levelname)s: %(message)s',
        force=True
    )
    aws_region = os.environ.get("AWS_REGION", "us-west-2")

    try:
        aws_secretsmanager = boto3.client("secretsmanager", region_name=aws_region)
        github_vault  = apd_common.get_secrets("GITHUB_PAT_SECRET_NAME", aws_secretsmanager)
        openai_vault  = apd_common.get_secrets("AZURE_OPENAI_SECRET_NAME", aws_secretsmanager)
        msgraph_vault = apd_common.get_secrets("MSGRAPH_SECRET_NAME", aws_secretsmanager)
        msgraph_instance = msgraph.MsGraph(
            tenant=msgraph_vault["tenant_id"],
            client_id=msgraph_vault["client_id"],
            client_secret=msgraph_vault["client_secret_value"],
            hostname=msgraph_vault["hostname"]
        )
    except Exception as e:
        logging.error(f"Failed to initialize: {e}")
        return False

    now = datetime.now(timezone.utc)
    last_month = now - relativedelta(months=1)
    month_label = last_month.strftime("%B %Y")

    logging.info(f"Fetching PRs merged in {month_label}...")
    pat = github_vault["GITHUB_PAT"]
    prs = get_prs_last_month(pat)
    if not prs:
        logging.info(f"No merged PRs found for {month_label}. Skipping email.")
        return True

    logging.info(f"Found {len(prs)} PRs. Resolving authors and reviewers...")
    pr_text = build_pr_text(pat, prs)
    logging.info("Generating summary...")
    summary = generate_summary(openai_vault, pr_text, month_label)

    subject = f"Monthly Code Update - {month_label} | {GITHUB_REPO}"
    email_payload = {
        "message": {
            "subject": subject,
            "body": {"contentType": "HTML", "content": summary},
            "toRecipients": [
                {"emailAddress": {"address": addr.strip()}}
                for addr in EMAIL_TO.split(",")
            ],
        },
        "saveToSentItems": "true"
    }
    logging.info(f"Sending email to {EMAIL_TO}...")
    issues, _ = msgraph_instance.send_email(
        email_payload,
        alternate_email_username_for_sending=EMAIL_FROM
    )
    if issues:
        logging.warning("Issues encountered sending email.")
        return False
    logging.info("Email sent successfully.")

    try:
        clickup_vault = apd_common.get_secrets("CLICKUP_SECRET_NAME", aws_secretsmanager)
        workspace_id  = os.environ.get("CLICKUP_DIGEST_WORKSPACE_ID", "9009105550")
        doc_id        = os.environ.get("CLICKUP_DIGEST_DOC_ID", "8cfr2me-7174")
        page_id       = os.environ.get("CLICKUP_DIGEST_PAGE_ID", "8cfr2me-19254")

        logging.info("Generating markdown summary for ClickUp...")
        clickup_summary = generate_markdown_summary(openai_vault, pr_text, month_label)

        logging.info("Updating ClickUp page...")
        page = clickup.get_doc_page(clickup_vault, workspace_id, doc_id, page_id)
        existing_content = page.get("content", "")
        new_section = f"## {month_label}\n\n{clickup_summary}\n\n---\n\n"
        clickup.update_doc_page(clickup_vault, workspace_id, doc_id, page_id, new_section + existing_content)
        logging.info("ClickUp page updated successfully.")
    except Exception as e:
        logging.warning(f"Failed to update ClickUp page: {e}")

    return True


if __name__ == "__main__":
    github_monthly_digest()
