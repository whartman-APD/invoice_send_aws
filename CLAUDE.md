# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

One Docker image with four jobs, selected by a command-line flag:

| Flag | What it does | Where it runs |
|---|---|---|
| `--create-invoices` | Creates monthly QBO invoices from Robocorp usage (ClickUp rates, runtime reports to SharePoint) | AWS ECS Fargate, started on demand |
| `--github-digest` | Weekly summary of merged PRs, emailed and prepended to a ClickUp doc | AWS ECS Fargate, EventBridge Scheduler (Mondays 1 AM PT) |
| `--sync-processes` | Syncs Robocorp processes/assistants to Azure SQL | Local Docker + Windows scheduled task (Azure SQL firewall allows only the local IP) |
| `--send-invoices` | Sends today's QBO invoices, emails summary | Local Docker + Windows scheduled task; **deprecated**, retiring end of Sept 2026 |

## Common Commands

### Local (from `send_qbo_invoices/`)

```bash
docker-compose build
docker-compose run --rm invoice-processor --create-invoices   # or --send-invoices, --sync-processes, --github-digest
```

The `run-*.ps1` scripts in the repo root wrap these for Windows Task Scheduler and log to `*.log` in the repo root.

### AWS (from repo root)

```powershell
aws sso login
.\deploy.ps1                                                   # terraform apply, then docker build + push the image it expects
.\run-aws-task.ps1 -Job create-invoices -DryRun               # forces CREATE_INVOICE/UPDATE_CLICKUP/UPLOAD_TO_SHAREPOINT=false
.\run-aws-task.ps1 -Job create-invoices -BillingReferenceDate 2026-10-01
.\run-aws-task.ps1 -Job github-digest
```

## Project Structure

```
infra/                        # Terraform: ECR, VPC, IAM, ECS, EventBridge Scheduler, SNS failure alerts
deploy.ps1                    # terraform apply + docker build/push
run-aws-task.ps1              # Start a job on Fargate and stream its logs
run-*.ps1                     # Local scheduled-task wrappers
send_qbo_invoices/
├── Dockerfile
├── docker-compose.yml        # Local only; mirrors the env vars in infra/ecs.tf
├── entrypoint.py             # Flag parsing -> job function
├── shared/
│   ├── task_minutes_to_clickup_and_qbo.py  # --create-invoices
│   ├── github_monthly_digest.py            # --github-digest
│   ├── sync_robocorp_processes.py          # --sync-processes
│   ├── process_and_send_qbo_invoices.py    # --send-invoices (deprecated)
│   ├── apd_quickbooksonline.py             # QBO API wrapper, OAuth refresh, retries
│   ├── apd_msgraph_v2.py                   # Microsoft Graph (email, SharePoint)
│   ├── apd_clickup.py                      # ClickUp API
│   └── apd_common.py                       # Secrets Manager/DynamoDB helpers, HTML templates
└── assets/                   # Email templates, digest prompts (assets/agents/)
```

## Configuration

- All credentials live in AWS Secrets Manager; env vars hold only the secret **names** (`QBO_SECRET_NAME`, `MSGRAPH_SECRET_NAME`, `CLICKUP_SECRET_NAME`, `ROBOCORP_API_SECRET_NAME`, `GITHUB_PAT_SECRET_NAME`, `AZURE_OPENAI_SECRET_NAME`, `AZURE_SQL_SECRET_NAME`).
- On AWS, env vars are set in `infra/ecs.tf` from `infra/variables.tf` / `terraform.tfvars`. Locally they come from `send_qbo_invoices/.env` via `docker-compose.yml`. Keep the two in sync when adding a variable.
- `CREATE_INVOICE`, `UPDATE_CLICKUP`, `UPLOAD_TO_SHAREPOINT` gate every side effect of `--create-invoices`; Terraform defaults them to `false`.
- `BILLING_REFERENCE_DATE` (YYYY-MM-DD) overrides the billing month; defaults to the prior month.

## Important Notes

- QBO refresh tokens rotate. Any job that constructs `QuickBooksOnline` must write `vault_values` back with `apd_common.update_secret("QBO_SECRET_NAME", ...)`.
- Never add retries to `--create-invoices` (scheduler or code): a rerun creates duplicate invoices.
- `datetime.now()` in the container is UTC.
- Code changes require an image rebuild: `docker-compose build` locally, `.\deploy.ps1` for AWS (the image tag is a hash of the source files, so any change produces a new task definition revision). Terraform does not build images; the kreuzwerker Docker provider hung on Windows.
- Terraform state is local (`infra/terraform.tfstate`, git-ignored) — back it up.
