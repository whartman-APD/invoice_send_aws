"""
GitHub Monthly Digest
- Secrets via AWS Secrets Manager
- Commits from GitHub REST API
- AI summary via Azure OpenAI
- Email via Microsoft Graph API (apd_msgraph_v2 wrapper)

Schedule: Last day of each month via Windows Task Scheduler.
"""

import logging
import os
import requests
import boto3
import apd_common
import apd_msgraph_v2 as msgraph
from datetime import datetime, timezone
from dateutil.relativedelta import relativedelta


# ── GitHub Config ─────────────────────────────────────────────────────────────
GITHUB_OWNER  = "AutomataPracDevClients"
GITHUB_REPO   = "APD_Code_Libraries"
GITHUB_BRANCH = "main"

# ── Email Config ──────────────────────────────────────────────────────────────
EMAIL_FROM = "whartman@automatapracdev.com"
EMAIL_TO   = "whartman@automatapracdev.com"
# ─────────────────────────────────────────────────────────────────────────────


def get_commits_last_month(pat: str) -> list[dict]:
    """Fetch commits to main branch from the past calendar month."""
    now = datetime.now(timezone.utc)
    since = (now - relativedelta(months=1)).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    until = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/commits"
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    params = {
        "sha": GITHUB_BRANCH,
        "since": since.isoformat(),
        "until": until.isoformat(),
        "per_page": 100,
    }

    commits = []
    page = 1
    while True:
        params["page"] = page
        resp = requests.get(url, headers=headers, params=params)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        commits.extend(batch)
        page += 1

    return commits


def resolve_display_names(pat: str, commits: list[dict]) -> dict[str, str]:
    """Resolve GitHub logins to display names via the Users API. Returns {login: display_name}."""
    headers = {
        "Authorization": f"Bearer {pat}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    logins: set[str] = set()
    for c in commits:
        author_obj = c.get("author")
        if author_obj and author_obj.get("login"):
            logins.add(author_obj["login"])

    name_map: dict[str, str] = {}
    for login in logins:
        try:
            resp = requests.get(f"https://api.github.com/users/{login}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            name_map[login] = data.get("name") or login
        except Exception:
            name_map[login] = login
    return name_map


def build_commit_text(commits: list[dict[str, str]], name_map: dict[str, str]) -> str:
    lines = []
    for c in commits:
        login = c.get("author", {}).get("login", "") if c.get("author") else ""
        author = name_map.get(login) or c["commit"]["author"]["name"]
        date   = c["commit"]["author"]["date"][:10]
        msg    = c["commit"]["message"].split("\n")[0]
        lines.append(f"- [{date}] {author}: {msg}")
    return "\n".join(lines)


def generate_summary(openai_vault: dict[str, str], commit_text: str, month_label: str) -> str:
    """Call Azure OpenAI to write a non-technical monthly summary."""
    endpoint    = openai_vault["AZURE_OPENAI_ENDPOINT"].rstrip("/")
    deployment  = openai_vault["AZURE_OPENAI_DEPLOYMENT"]
    api_version = openai_vault["AZURE_OPENAI_API_VERSION"]
    api_key     = openai_vault["AZURE_OPENAI_API_KEY"]

    url = f"{endpoint}/openai/deployments/{deployment}/chat/completions?api-version={api_version}"

    prompt = f"""You are summarizing a month of software development commits for an internal team digest email.

Analyze the commits and group them by the app or library that was changed (e.g. "Canopy", "MS Graph", "QBO", etc.).
Infer the app/library name from the commit messages. Do NOT include "APD" in any app or library name — drop it and use only the core name (e.g. "apd_msgraph" becomes "MS Graph", "apd_quickbooksonline" becomes "QuickBooks Online").

Output the email as HTML using this exact structure:

<p>Here are the changes that were made to the APD Code Library.</p>

Then for each app or library, sorted alphabetically by name:

<p><strong>{{App or Library Name}}</strong><br>
<em>{{Comma-separated list of all unique author display names who committed to this app}}</em></p>
<ul>
  <li>{{Capability statement — what the code now does. Focus on new method calls, new features, or new behaviors. Be concise and functional.}}</li>
</ul>

Do not include a subject line, greeting, sign-off, or any prose outside this structure. Output only valid HTML — no markdown, no code fences.

Month: {month_label}
Repository: {GITHUB_OWNER}/{GITHUB_REPO}

Commits this month:
{commit_text}"""

    resp = requests.post(
        url,
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 1024,
            "temperature": 0.7,
        },
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


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

    logging.info(f"Fetching commits for {month_label}...")
    commits = get_commits_last_month(github_vault["GITHUB_PAT"])
    if not commits:
        logging.info(f"No commits found for {month_label}. Skipping email.")
        return True

    logging.info(f"Found {len(commits)} commits. Resolving author names...")
    name_map = resolve_display_names(github_vault["GITHUB_PAT"], commits)
    logging.info("Generating summary...")
    commit_text = build_commit_text(commits, name_map)
    summary = generate_summary(openai_vault, commit_text, month_label)

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
    return True


if __name__ == "__main__":
    github_monthly_digest()
