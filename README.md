# APD Invoice & Operations Automation

A single Docker image that runs Automata Practice Development's scheduled back-office jobs:
QuickBooks Online invoicing from Robocorp usage, a weekly GitHub digest, and a Robocorp → Azure SQL sync.

## Jobs

| Job | Flag | What it does | Where / when it runs |
|---|---|---|---|
| Create invoices | `--create-invoices` | Bills each client for the **prior calendar month**: unattended minutes from the Robocorp usage CSV in SharePoint + attended (assistant) minutes from the Robocorp API. Creates the QBO invoice, attaches a runtime report (billing month vs. comparison month), uploads reports to SharePoint, emails a summary. | **AWS** ECS Fargate — 4th of the month, 6:00 AM Pacific |
| GitHub digest | `--github-digest` | Summarizes the last 7 days of merged PRs in `AutomataPracDevClients/APD_Code_Libraries` with Azure OpenAI; emails allstaff@ and prepends it to a ClickUp doc. | **AWS** ECS Fargate — Mondays, 1:00 AM Pacific |
| Sync processes | `--sync-processes` | Upserts Robocorp processes/assistants into Azure SQL (`dbo.dim_processes`). | **AWS** ECS Fargate — daily 4:00 AM Pacific, in the n8n VPC's private subnets so it reaches Azure SQL through the allowed NAT IP (44.253.27.41). |
| Send invoices | `--send-invoices` | Sends today's QBO invoices and emails a summary. | **Local** — **retired after 2026-09-30**; invoices are now sent from QBO in bulk |

### Monthly billing cadence
1. **1st:** download the prior month's Robocorp usage CSV into SharePoint → *APDClientFiles / 10000 - Automata Practice Development / Minutes / CSV Data*.
2. **4th, 6 AM:** create-invoices runs on AWS (billing month = prior month, comparison month = the month before).
3. Review the summary email, then send the invoices from QBO in bulk.

## Repository layout

```
infra/                 Terraform for AWS (ECR, VPC, IAM, ECS, EventBridge Scheduler, alerts)
deploy.ps1             Deploy to AWS: terraform apply, then build + push the image
run-aws-task.ps1       Start a job on AWS by hand and stream its logs
run-*.ps1              Wrappers used by the local Windows scheduled tasks (log to *.log here)
send_qbo_invoices/     The application (Dockerfile, entrypoint, shared/ modules, assets/)
tests/                 Unit tests (APIs mocked; safe to run anywhere)
```

## Documentation

- **[AWS-DEPLOYMENT.md](AWS-DEPLOYMENT.md)** — deploying, running, monitoring, and recovering the AWS jobs
- **[send_qbo_invoices/README.md](send_qbo_invoices/README.md)** — local Docker, configuration, secrets, tests
- **[infra/README.md](infra/README.md)** — what the Terraform creates and how to change it

## Quick reference

```powershell
# AWS (from the repo root; Docker Desktop running)
aws sso login
.\deploy.ps1                                              # after any code or terraform.tfvars change
.\run-aws-task.ps1 -Job create-invoices -DryRun           # full run that creates/uploads/updates nothing
.\run-aws-task.ps1 -Job github-digest

# Local (from send_qbo_invoices/)
docker-compose build
docker-compose run --rm invoice-processor --sync-processes   # development only; the real runs are on AWS

# Tests (from the repo root)
.venv\Scripts\python -m unittest discover -s tests
```
