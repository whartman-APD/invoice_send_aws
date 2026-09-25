# Infrastructure (Terraform)

Everything AWS runs on. Apply it with `..\deploy.ps1` from the repo root, which runs `terraform apply` and
then builds/pushes the image the task definition expects. Operating guide: [AWS-DEPLOYMENT.md](../AWS-DEPLOYMENT.md).

## Files

| File | Creates |
|---|---|
| `main.tf` | Providers (AWS only), default tags, account/region lookups |
| `variables.tf` | Every setting, with safe defaults (all write flags `false`, schedules disabled) |
| `terraform.tfvars` | **Git-ignored.** Production values that override the defaults |
| `ecr.tf` | ECR repo `invoice-send-qbo` (keeps the last 10 images); computes the image tag from a hash of the app source |
| `network.tf` | VPC `10.20.0.0/16`, 2 public subnets, internet gateway, outbound-HTTPS-only security group (digest, invoices). Plus a security group in the **n8n VPC** (outbound 443 + 1433) for sync-processes. |
| `iam.tf` | Execution role (pull image, write logs), task role (app permissions), scheduler role (run the task) |
| `ecs.tf` | Cluster, CloudWatch log group (30 days), task definition with the app's env vars |
| `scheduler.tf` | EventBridge Scheduler group + `github-digest`, `create-invoices`, `sync-processes` schedules (Pacific time, 0 retries); each job picks its network |
| `monitoring.tf` | SNS email topic, rule for failed/unstartable tasks, alarm for dropped schedule invocations |
| `outputs.tf` | Values read by `deploy.ps1` and `run-aws-task.ps1` |

## Common changes

| Change | Where |
|---|---|
| New app env var | `local.app_environment` in `ecs.tf` (+ a variable if it varies), and `send_qbo_invoices/docker-compose.yml` |
| New secret the app reads | Add it to `secret_names` in `variables.tf` — that also grants the task role read access |
| Bigger task | `task_cpu` / `task_memory` |
| Schedule time / on-off | `*_schedule` / `*_schedule_enabled` in `terraform.tfvars` |

## Notes

- **The image isn't built by Terraform.** The Terraform Docker provider hung for 18+ minutes on Windows, so `deploy.ps1` builds with the normal `docker build` (cached, shows progress). The task definition references `repo:<source hash>`; ECS only pulls it when a task starts.
- **sync-processes uses the n8n VPC's private subnets** (`sync_vpc_id`, `sync_subnet_ids`) because their NAT gateway IP (44.253.27.41) is on the Azure SQL firewall. They're referenced by ID only; this Terraform never changes the n8n VPC.
- **State is local** (`terraform.tfstate`, git-ignored). Back it up.
- `terraform validate` / `plan` are read-only; `apply` changes AWS but never starts a job.
