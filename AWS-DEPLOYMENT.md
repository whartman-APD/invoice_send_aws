# AWS Deployment & Operations

How the AWS side works and how to deploy, run, watch, and recover it. Three jobs run here:
**create-invoices** (monthly), **github-digest** (weekly), and **sync-processes** (daily). send-invoices runs
locally until it's retired (see the [README](README.md)).

- **Account / region:** 739275469467 / us-west-2 (US West, Oregon)
- **Cost:** roughly $1–3/month (Fargate only bills while a task runs; sync-processes adds a little NAT data-processing on the existing n8n NAT gateway)

## How it fits together

```
EventBridge Scheduler (America/Los_Angeles)
  ├─ github-digest    Mondays 1:00 AM        ─┐
  ├─ create-invoices  4th of month 6:00 AM   ─┤  (retries: 0)
  └─ sync-processes   daily 4:00 AM          ─┤
                                              ▼
                    ECS Fargate task  (cluster invoice-send-qbo-cluster, 0.5 vCPU / 2 GB)
                      image: ECR invoice-send-qbo:<source hash>
                      runs as IAM task role → Secrets Manager + DynamoDB
                      digest/invoices: our public subnets, outbound HTTPS only
                      sync: n8n VPC private subnets → NAT 44.253.27.41 (allowed by Azure SQL), HTTPS + 1433
                      logs → CloudWatch /ecs/invoice-send-qbo (30 days)
                                              │
       task exits non-zero / fails to start ──┴─► EventBridge rule ─► SNS ─► email alert
       scheduler can't start the task ──────────► CloudWatch alarm ─► SNS ─► email alert
```

- **One task definition** serves every job; the schedule (or `run-aws-task.ps1`) picks the job with a command override.
- **No AWS keys in the container.** The task role can read only the seven app secrets, update only the QBO secret (rotated refresh tokens), and read the `Robocorp_Client_Org_Workspace_IDs` table.
- **sync-processes borrows the n8n network.** Azure SQL's firewall allows the n8n NAT gateway's IP, so that job runs in the n8n VPC's private subnets (`vpc-087a5bdbc7e01ed60`). Terraform only references those subnets and adds its own security group there; it never modifies the n8n VPC. If that NAT gateway or its IP changes, sync-processes loses access to Azure SQL.
- **Never retried automatically.** A retried create-invoices run would create duplicate invoices.

## Prerequisites (one time)

1. **Terraform** — `winget install Hashicorp.Terraform`, then open a new terminal.
2. **AWS CLI logged in** — `aws sso login`. The VS Code AWS Toolkit login is separate and does *not* work for the CLI or Terraform.
3. **Docker Desktop** running (only needed by `deploy.ps1` when the code changed).
4. **`infra/terraform.tfvars`** (git-ignored) with production values:
   ```hcl
   create_invoice       = true
   upload_to_sharepoint = true
   update_clickup       = false

   digest_email_from = "robotarmy@automatapracdev.com"
   digest_email_to   = "allstaff@automatapracdev.com"

   github_digest_schedule_enabled   = true
   create_invoices_schedule_enabled = true
   sync_processes_schedule_enabled  = true
   ```
   Anything not listed uses the default in [infra/variables.tf](infra/variables.tf). The three `create_invoice`/`upload`/`update` flags default to `false` there, so a missing tfvars file can't create invoices.
5. **Confirm the alert subscription** — after the first deploy, click the link in the "AWS Notification – Subscription Confirmation" email.

## Deploying changes

```powershell
.\deploy.ps1
```

1. Runs `terraform apply` — review the plan, type `yes`.
2. Builds and pushes the image **only if the code changed**. The tag is a hash of `Dockerfile`, `requirements.txt`, `entrypoint.py`, `shared/**/*.py`, and `assets/**`; otherwise it prints *"already in ECR … Nothing to build"*.

Deploying never starts a job. Run it after changing code **or** `terraform.tfvars`.

**Reading the plan:**
- Changing an app setting or the image replaces `aws_ecs_task_definition.app` (`1 to add, 1 to destroy`). That's normal: task definitions are immutable and the schedules always use the latest revision.
- Anything else being destroyed is unexpected — stop and investigate.

## Running a job by hand

```powershell
.\run-aws-task.ps1 -Job create-invoices -DryRun           # reads everything, creates/uploads/updates nothing
.\run-aws-task.ps1 -Job create-invoices                   # REAL: creates invoices, uploads to SharePoint
.\run-aws-task.ps1 -Job create-invoices -LowerClientId 10018   # finish a crashed run (see Recovery)
.\run-aws-task.ps1 -Job github-digest                     # REAL: emails allstaff@, updates ClickUp
.\run-aws-task.ps1 -Job sync-processes                    # REAL: upserts into Azure SQL (same as the daily run; safe to repeat)
```

The script starts the task, prints a console link, and streams the log until the task stops. Closing the window does **not** stop the task — use **Stop** on the task page in the ECS console.

`-DryRun` forces `CREATE_INVOICE`, `UPDATE_CLICKUP`, and `UPLOAD_TO_SHAREPOINT` to `false` for that run. It still reads QBO/ClickUp/SharePoint/Robocorp and saves the refreshed QBO token, which is expected.

## Watching

| What | Where |
|---|---|
| Schedules, next run times | [EventBridge Scheduler → Schedules](https://us-west-2.console.aws.amazon.com/scheduler/home?region=us-west-2#schedules) → schedule group **invoice-send-qbo** |
| A running task | ECS → Clusters → **invoice-send-qbo-cluster** → Tasks (stopped tasks disappear after ~1 hour) |
| Logs for every run (30 days) | [CloudWatch → /ecs/invoice-send-qbo](https://us-west-2.console.aws.amazon.com/cloudwatch/home?region=us-west-2#logsV2:log-groups/log-group/$252Fecs$252Finvoice-send-qbo) → newest stream → **Start tailing** |
| From a terminal | `aws logs tail /ecs/invoice-send-qbo --follow --since 1h` |

A successful run ends with `COMPLETED SUCCESSFULLY`. Failures email **whartman@automatapracdev.com** with the exit code, reason, and a link to the logs.

## Changing schedules or settings

Edit `infra/terraform.tfvars`, then `.\deploy.ps1`.

| Change | Setting |
|---|---|
| Pause a job | `github_digest_schedule_enabled` / `create_invoices_schedule_enabled` / `sync_processes_schedule_enabled` = `false` |
| Run at a different time | `github_digest_schedule` / `create_invoices_schedule` / `sync_processes_schedule` (cron, evaluated in Pacific time) |
| Digest recipients | `digest_email_to` (comma-separated) |
| Client range | `lower_client_id` (inclusive) / `upper_client_id` (exclusive) |
| Alert recipient | `alert_email` (new address must confirm the subscription email) |

Don't toggle schedules in the console — the next deploy puts them back to what `terraform.tfvars` says.

## Recovery

**The CSV wasn't in SharePoint on the 4th.** The run stops immediately with `File account-usage-…csv not found in SharePoint` before creating anything. Upload it, then `.\run-aws-task.ps1 -Job create-invoices`.

**One client errored** (e.g. "has no billing email"). The run continues with the other clients and lists the error in the summary email. Fix the cause and create that one invoice in QBO by hand. Don't rerun the job — every other client would be invoiced again.

**The whole run crashed partway** ("job FAILED" email; log stops mid-run).
1. In the log, find the last `Processing client number: XXXXX`.
2. Check QBO for that client — the crash may have come after its invoice was created.
3. Rerun from the first client **without** an invoice: `.\run-aws-task.ps1 -Job create-invoices -LowerClientId <number>`. Add `-DryRun` first if you want to preview.

**Rollback to a previous image.** Set `image_tag = "<older tag>"` in `terraform.tfvars` (tags are listed in ECR → `invoice-send-qbo`; the last 10 are kept), `.\deploy.ps1`, and remove the line afterwards.

## Troubleshooting

- **`Error loading SSO Token` / `Token has expired`** — run `aws sso login` in a terminal.
- **`deploy.ps1` fails at `docker build`** — start Docker Desktop.
- **Task stops with `CannotPullContainerError`** — the task definition points at a tag that was never pushed; run `.\deploy.ps1` (it pushes the missing tag).
- **sync-processes: `Login timeout expired` / can't reach Azure SQL** — check the n8n NAT gateway still exists with IP 44.253.27.41 and that the Azure SQL firewall rule "n8n on AWS" still allows it.
- **`AccessDeniedException` on a secret** — a new secret must be added to `secret_names` in [infra/variables.tf](infra/variables.tf) so the task role can read it.

## Terraform state

State is local: `infra/terraform.tfstate` (git-ignored). **Back it up** — without it Terraform can't manage the existing resources. See [infra/README.md](infra/README.md) for what each file creates.
