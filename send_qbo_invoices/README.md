# Application: `send_qbo_invoices`

The Docker image used for every job, locally and on AWS. For what each job does and where it runs, see the
[project README](../README.md); for AWS, see [AWS-DEPLOYMENT.md](../AWS-DEPLOYMENT.md).

## Running locally

Local Docker is used for **send-invoices** through 2026-09-30 and for **sync-processes** until its AWS cutover
("Azure Update Process Names" scheduled task). After that, local runs are for development only. Commands run from this folder:

```powershell
copy .env.template .env        # first time only, then fill it in
docker-compose build           # after any code change
docker-compose run --rm invoice-processor --sync-processes
```

`--create-invoices`, `--github-digest`, and `--send-invoices` work the same way, but **they are real runs**:
they create invoices, send email, and write to SharePoint/ClickUp/Azure SQL. create-invoices and
github-digest normally run on AWS — don't also run them locally.

The `run-*.ps1` scripts in the repo root wrap these commands for Windows Task Scheduler and append output to
`*.log` in the repo root.

### Checking configuration without running a job

Override the entrypoint to run plain Python. Example — confirm the Azure SQL secret and connection, writing nothing:

```powershell
docker-compose run --rm --entrypoint python invoice-processor -c "import boto3, sync_robocorp_processes as s; c = s._get_sql_config(boto3.client('secretsmanager', region_name='us-west-2')); print('Secret OK, keys:', sorted(c)); s._connect_to_azure_sql(c).close(); print('Azure SQL connection OK')"
```

## Configuration

Env vars hold settings and secret **names**; every credential lives in AWS Secrets Manager (us-west-2).
Locally they come from `.env` via `docker-compose.yml`; on AWS from [infra/ecs.tf](../infra/ecs.tf) +
`infra/terraform.tfvars`. **When adding a variable, add it to both.**

| Variable | Used by | Notes |
|---|---|---|
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | local only | IAM user key (see permissions below). Not used on AWS — the task role replaces it. |
| `AWS_REGION` | all | `us-west-2` |
| `QBO_SECRET_NAME` | create, send | `QBO/10000` |
| `MSGRAPH_SECRET_NAME` | create, send, digest | `MsGraph/10000` |
| `CLICKUP_SECRET_NAME` | create, digest | `ClickUp/10000` |
| `ROBOCORP_API_SECRET_NAME` | create, sync | `RoboCorp/10000/ClientAPIKeys` |
| `GITHUB_PAT_SECRET_NAME` | digest | `GitHub/10000/PersonalAccessToken` |
| `AZURE_OPENAI_SECRET_NAME` | digest | `AzureOpenAI/10000` |
| `AZURE_SQL_SECRET_NAME` | sync | `AzureSQLServer/10000` |
| `DYNAMODB_TABLE_ROBOCORP_CLIENTS` | create, sync | `Robocorp_Client_Org_Workspace_IDs` (client number → Robocorp org/workspace IDs) |
| `CREATE_INVOICE` / `UPLOAD_TO_SHAREPOINT` / `UPDATE_CLICKUP` | create | Gate every write create-invoices makes. `false` = read-only dry run. |
| `LOWER_CLIENT_ID` / `UPPER_CLIENT_ID` | create | Client range, lower inclusive / upper exclusive |
| `NET_30_DAYS_CLIENTS` | create | Comma-separated client numbers due at month end instead of on receipt |
| `BILLING_REFERENCE_DATE` | create | Leave unset. Billing month defaults to the prior calendar month. |
| `BOOKKEEPER_EMAIL` / `SENDER_EMAIL` | create, send | Summary recipient / sending mailbox |
| `EXCLUDED_CUSTOMERS` | send | QBO customer names never sent invoices |
| `MONTHLY_DIGEST_EMAIL_FROM` / `_TO` | digest | robotarmy@ → allstaff@ (the digest is weekly despite the name) |
| `CLICKUP_DIGEST_WORKSPACE_ID` / `_DOC_ID` / `_PAGE_ID` | digest | ClickUp page the digest is prepended to |
| `MS_GRAPH_HOSTNAME` | create | `automatapracdev.sharepoint.com` |

### Secrets (JSON keys)

| Secret | Keys |
|---|---|
| `QBO/10000` | `client_id`, `client_secret`, `realm_id`, `refresh_token`, `access_token` — tokens are rewritten after every run that refreshes them |
| `MsGraph/10000` | `tenant_id`, `client_id`, `client_secret_value`, `hostname` |
| `ClickUp/10000` | `token` |
| `RoboCorp/10000/ClientAPIKeys` | one key per client number → Robocorp workspace API key |
| `GitHub/10000/PersonalAccessToken` | `GITHUB_PAT` |
| `AzureOpenAI/10000` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` |
| `AzureSQLServer/10000` | `AZURE_SQL_SERVER`, `AZURE_SQL_DATABASE`, `AZURE_SQL_USERNAME`, `AZURE_SQL_PASSWORD` |

### Local IAM key permissions

The key in `.env` needs `secretsmanager:GetSecretValue` on each secret the local jobs use, plus
`dynamodb:Scan` on the client table. For sync-processes alone that's `RoboCorp/10000/ClientAPIKeys` and
`AzureSQLServer/10000`. Until send-invoices is retired it also needs `QBO/10000` (get **and**
`secretsmanager:UpdateSecret`) and `MsGraph/10000`.

## Code map

| Module | Role |
|---|---|
| `entrypoint.py` | Parses the job flag, calls the job, exits 0/1 |
| `shared/task_minutes_to_clickup_and_qbo.py` | create-invoices: usage → ClickUp rate lookup → QBO invoice + runtime report → SharePoint → summary email |
| `shared/github_monthly_digest.py` | github-digest |
| `shared/sync_robocorp_processes.py` | sync-processes |
| `shared/process_and_send_qbo_invoices.py` | send-invoices (retiring) |
| `shared/apd_quickbooksonline.py` | QBO API: OAuth refresh, retries, `QBOError` family |
| `shared/apd_msgraph_v2.py` | Microsoft Graph: email, SharePoint |
| `shared/apd_clickup.py` | ClickUp API |
| `shared/apd_common.py` | Secrets Manager / DynamoDB helpers, HTML email templates |
| `assets/` | Email templates; `assets/agents/` holds the digest prompts |

### create-invoices terms
- **Billing month** — the month being invoiced (`BILLING_CONFIG.billing_period_*`). Unattended minutes come from that month's Robocorp usage CSV in SharePoint (`account-usage-…-YYYY-M.csv`, month zero-indexed); attended minutes from the Robocorp assistant-runs API.
- **Comparison month** — the month before, shown next to the billing month in the runtime report attached to each invoice (Usage Pivot, Two Month Run Compare, Run Data, Overage Calculation). Never billed.
- The invoice is dated the 1st of the month the job runs.

## Tests

Unit tests mock every external API, so they're safe to run anywhere:

```powershell
# from the repo root
.venv\Scripts\python -m unittest discover -s tests
```

## Troubleshooting

- **`Environment variable 'X_SECRET_NAME' not set`** — add it to `.env` (and `docker-compose.yml` if it's new).
- **`AccessDeniedException` on a secret or the table** — the local IAM key lacks that permission (see above).
- **`Missing required keys in Azure SQL secret`** — the secret's JSON keys don't match the table above.
- **Azure SQL connection fails locally** — Azure SQL's firewall must allow this machine's public IP. (On AWS the job reaches it through the n8n NAT IP.)
- **Code change not taking effect** — `docker-compose build` again; the image contains the code.
