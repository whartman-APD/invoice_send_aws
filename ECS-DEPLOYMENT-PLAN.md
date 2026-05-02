# AWS ECS Fargate Deployment Plan
## QuickBooks Invoice Automation

---

## Executive Summary

Deploy the Docker-based QuickBooks Online invoice automation system to AWS ECS Fargate with EventBridge scheduled execution. This plan creates all necessary infrastructure using Terraform and provides a Makefile for streamlined deployment.

**Deliverables:**
1. ECR repository (already exists - will reference)
2. Makefile with deployment automation
3. ECS Fargate task definitions
4. EventBridge scheduled rules for automated execution
5. Complete networking and IAM infrastructure

**Estimated Cost:** ~$2.25/month

---

## Architecture Overview

```
EventBridge Scheduler
    ├─ Daily @ 6 AM PST  → ECS Task (--send-invoices)
    └─ Monthly 4th @ 2 AM PST → ECS Task (--create-invoices)
           ↓
    ECS Fargate Task
           ├─ Docker Container (ECR)
           ├─ Secrets Manager (4 secrets)
           ├─ DynamoDB (client data)
           └─ CloudWatch Logs
```

---

## Implementation Steps

### Step 1: Create New Terraform Files

Create 5 new `.tf` files in the `infra/` directory:

#### 1.1 `infra/network.tf` (NEW FILE)
**Purpose:** VPC, subnets, internet gateway, security groups

**Key Resources:**
- VPC with CIDR `10.0.0.0/16`
- 2 public subnets across 2 AZs (us-west-2a, us-west-2b)
- Internet Gateway for outbound API calls
- Security group allowing egress HTTPS/HTTP only

**Design Decision:** Public subnets with IGW (no NAT Gateway) to save ~$32/month. Tasks get ephemeral public IPs but have no inbound access.

#### 1.2 `infra/iam.tf` (NEW FILE)
**Purpose:** IAM roles and policies for ECS tasks and EventBridge

**Key Resources:**
- **Task Execution Role:** Allows ECS to pull ECR images and write CloudWatch logs
- **Task Role:** Grants app permissions to Secrets Manager (read/update), DynamoDB (read)
- **EventBridge Role:** Allows EventBridge to run ECS tasks

**Critical IAM Permissions:**
- Secrets Manager: `GetSecretValue`, `UpdateSecret` on QBO/MsGraph/ClickUp/RoboCorp secrets
- DynamoDB: `GetItem`, `Query`, `Scan` on Robocorp_Client_Org_Workspace_IDs table
- Note: Use wildcard suffixes on secret ARNs (e.g., `QBO/10000*`) for version handling

#### 1.3 `infra/ecs.tf` (NEW FILE)
**Purpose:** ECS cluster and task definition

**Key Resources:**
- **ECS Cluster:** `invoice-send-qbo-cluster` with Container Insights enabled
- **Task Definition:**
  - Family: `invoice-send-qbo`
  - CPU: 2048 (2 vCPU)
  - Memory: 4096 MB (4 GB)
  - Network Mode: `awsvpc` (required for Fargate)
  - Platform: Linux/AMD64

**Container Configuration:**
- Image: References existing ECR repository
- Entrypoint: `python entrypoint.py` (command passed via EventBridge override)
- Environment Variables: 16 variables from `.env.template`
- Logs: CloudWatch Logs with `/ecs/invoice-send-qbo` log group

#### 1.4 `infra/eventbridge.tf` (NEW FILE)
**Purpose:** Scheduled rules for daily and monthly execution

**Key Resources:**

**Daily Schedule (Send Invoices):**
- Rule: `invoice-send-qbo-send-daily`
- Schedule: `cron(0 14 * * ? *)` = 6 AM PST / 2 PM UTC
- Container Override: `["--send-invoices"]`
- Network: Both public subnets, assign public IP

**Monthly Schedule (Create Invoices):**
- Rule: `invoice-send-qbo-create-monthly`
- Schedule: `cron(0 10 4 * ? *)` = 2 AM PST / 10 AM UTC on 4th of month
- Container Override: `["--create-invoices"]`
- Network: Same as daily

**Important:** Cron schedules use UTC. PST = UTC-8, PDT = UTC-7 (adjust for daylight saving if needed).

#### 1.5 `infra/cloudwatch.tf` (NEW FILE)
**Purpose:** Log groups and monitoring

**Key Resources:**
- Log Group: `/ecs/invoice-send-qbo` with 30-day retention
- Alarm: Task failures (threshold: >= 1 failed task)

---

### Step 2: Update Existing Terraform Files

#### 2.1 Update `infra/variables.tf`
**Action:** Add 25+ new variables

**Variable Categories:**
1. Network configuration (VPC CIDR, AZs)
2. ECS configuration (CPU, memory)
3. Application environment variables (all from `.env.template`)
4. Schedule configuration (cron expressions, enable/disable flags)
5. CloudWatch configuration (log retention)

**See Appendix A for complete variable definitions.**

#### 2.2 Update `infra/outputs.tf`
**Action:** Add 10+ new outputs

**New Outputs:**
- ECS cluster name and ARN
- Task definition ARN
- VPC and subnet IDs
- Security group ID
- IAM role ARNs
- CloudWatch log group name
- EventBridge rule ARNs

**Purpose:** These outputs are used by Makefile test targets.

---

### Step 3: Create Makefile

#### 3.1 Create `Makefile` in Project Root
**Purpose:** Automate Docker build, push, and Terraform deployment

**Key Targets:**

```makefile
make init           # Initialize Terraform
make plan           # Preview Terraform changes
make apply          # Apply Terraform changes
make build          # Build Docker image locally
make push           # Push image to ECR
make deploy         # Full deployment (build + push + apply)
make test-send-invoices    # Manually trigger send-invoices task
make test-create-invoices  # Manually trigger create-invoices task
make logs           # Tail CloudWatch logs
```

**See Appendix B for complete Makefile.**

---

### Step 4: Configure User-Specific Values

#### 4.1 Create `infra/terraform.tfvars` (git-ignored)
**Action:** Copy from template and populate with actual values

**See CONFIGURATION PUNCH LIST below for required values.**

#### 4.2 Create `infra/terraform.tfvars.example`
**Action:** Provide template for other developers

---

### Step 5: Deploy Infrastructure

#### 5.1 Initial Deployment Workflow

```bash
# 1. Navigate to project root
cd c:\Users\WesleyHartman\Documents\APD Repos\invoice_send_aws

# 2. Initialize Terraform (download providers)
make init

# 3. Review planned infrastructure changes
make plan

# 4. Deploy everything (build Docker + apply Terraform)
make deploy

# 5. Manually test send-invoices function
make test-send-invoices

# 6. Monitor logs in real-time
make logs
```

#### 5.2 Verify Deployment

```bash
# Check ECS cluster exists
aws ecs describe-clusters --clusters invoice-send-qbo-cluster --region us-west-2

# Check task definition registered
aws ecs describe-task-definition --task-definition invoice-send-qbo --region us-west-2

# Check scheduled rules enabled
aws events list-rules --region us-west-2 | grep invoice-send-qbo
```

---

## File Structure After Implementation

```
invoice_send_aws/
├── Makefile                          # NEW - Deployment automation
├── infra/
│   ├── main.tf                       # EXISTS - Provider config
│   ├── variables.tf                  # MODIFY - Add 25+ variables
│   ├── outputs.tf                    # MODIFY - Add 10+ outputs
│   ├── ecr.tf                        # EXISTS - ECR repository
│   ├── network.tf                    # NEW - VPC, subnets, security groups
│   ├── iam.tf                        # NEW - IAM roles and policies
│   ├── ecs.tf                        # NEW - ECS cluster and task definition
│   ├── eventbridge.tf                # NEW - Scheduled rules
│   ├── cloudwatch.tf                 # NEW - Log groups and alarms
│   ├── terraform.tfvars              # NEW - User config (git-ignored)
│   └── terraform.tfvars.example      # NEW - Config template
└── send_qbo_invoices/
    └── (existing Docker app files)
```

---

## CONFIGURATION PUNCH LIST

### ⚠️ REQUIRED: Values You Must Provide

**File:** `infra/terraform.tfvars`

#### Email Configuration (REQUIRED)
- [ ] **bookkeeper_email**
  - Description: Email address to receive daily invoice summary
  - Example: `"whartman@automatapracdev.com"`
  - Location to find: Already in `.env.template` line 51

- [ ] **sender_email**
  - Description: From address for outgoing emails
  - Example: `"robotarmy@automatapracdev.com"`
  - Location to find: Already in `.env.template` line 54

#### Customer Configuration (REQUIRED)
- [ ] **excluded_customers**
  - Description: Customers to skip when sending invoices (comma-separated)
  - Example: `"10001 - AICPA"` or `""` if none
  - Location to find: Already in `.env.template` line 57

- [ ] **net_30_days_clients**
  - Description: Client IDs with NET 30 payment terms (comma-separated)
  - Example: `"10020"` or `""` if none
  - Location to find: Already in `.env.template` line 77

---

### ✅ VERIFY: AWS Resources Exist

**Before deployment, confirm these resources exist in AWS:**

- [ ] **Secrets Manager Secret:** `QBO/10000`
  - Verify: `aws secretsmanager describe-secret --secret-id QBO/10000 --region us-west-2`

- [ ] **Secrets Manager Secret:** `MsGraph/10000`
  - Verify: `aws secretsmanager describe-secret --secret-id MsGraph/10000 --region us-west-2`

- [ ] **Secrets Manager Secret:** `ClickUp/10000`
  - Verify: `aws secretsmanager describe-secret --secret-id ClickUp/10000 --region us-west-2`

- [ ] **Secrets Manager Secret:** `RoboCorp/10000/ClientAPIKeys`
  - Verify: `aws secretsmanager describe-secret --secret-id RoboCorp/10000/ClientAPIKeys --region us-west-2`

- [ ] **DynamoDB Table:** `Robocorp_Client_Org_Workspace_IDs`
  - Verify: `aws dynamodb describe-table --table-name Robocorp_Client_Org_Workspace_IDs --region us-west-2`

---

### 🔧 OPTIONAL: Override Defaults (if needed)

**File:** `infra/terraform.tfvars`

These have sensible defaults but can be customized:

- [ ] **aws_region** (default: `us-west-2`)
- [ ] **ecs_task_cpu** (default: `2048` = 2 vCPU)
- [ ] **ecs_task_memory** (default: `4096` = 4 GB)
- [ ] **upload_to_sharepoint** (default: `"false"`, set `"true"` for production)
- [ ] **create_invoice** (default: `"false"`, set `"true"` for production)
- [ ] **update_clickup** (default: `"false"`, set `"true"` for production)
- [ ] **send_invoices_schedule** (default: `cron(0 14 * * ? *)` = 6 AM PST)
- [ ] **create_invoices_schedule** (default: `cron(0 10 4 * ? *)` = 2 AM PST on 4th)

---

### 🔑 AWS Credentials

- [ ] **AWS CLI configured**
  - Run: `aws configure` if not already set up
  - Required permissions: ECR, ECS, VPC, IAM, EventBridge, CloudWatch, Secrets Manager, DynamoDB

- [ ] **AWS Account ID**
  - Get: `aws sts get-caller-identity --query Account --output text`
  - Used automatically by Terraform (no manual input needed)

---

## Detailed Design Specifications

### Network Architecture

**VPC Design:**
- CIDR: `10.0.0.0/16` (65,536 IPs)
- DNS hostnames: Enabled
- DNS support: Enabled

**Subnet Design:**
- Public Subnet A: `10.0.1.0/24` in `us-west-2a` (256 IPs)
- Public Subnet B: `10.0.2.0/24` in `us-west-2b` (256 IPs)
- Both subnets have `map_public_ip_on_launch = true`

**Routing:**
- Single route table for public subnets
- Default route: `0.0.0.0/0` → Internet Gateway

**Security Group Rules:**
- Ingress: None (tasks don't accept connections)
- Egress: HTTPS (443) and HTTP (80) to `0.0.0.0/0`

**Rationale:** Public subnets with IGW avoid NAT Gateway costs (~$32/month). Tasks only make outbound API calls, so no inbound security needed.

---

### ECS Task Definition

**Container Specification:**
```json
{
  "name": "invoice-processor",
  "image": "<ECR_REPO_URL>:latest",
  "cpu": 2048,
  "memory": 4096,
  "essential": true,
  "logConfiguration": {
    "logDriver": "awslogs",
    "options": {
      "awslogs-group": "/ecs/invoice-send-qbo",
      "awslogs-region": "us-west-2",
      "awslogs-stream-prefix": "ecs"
    }
  },
  "environment": [ /* 16 variables */ ]
}
```

**Environment Variables (from `.env.template`):**
1. AWS_REGION
2. QBO_SECRET_NAME
3. MSGRAPH_SECRET_NAME
4. CLICKUP_SECRET_NAME
5. ROBOCORP_API_SECRET_NAME
6. DYNAMODB_TABLE_ROBOCORP_CLIENTS
7. BOOKKEEPER_EMAIL
8. SENDER_EMAIL
9. EXCLUDED_CUSTOMERS
10. MS_GRAPH_HOSTNAME
11. UPLOAD_TO_SHAREPOINT
12. CREATE_INVOICE
13. UPDATE_CLICKUP
14. LOWER_CLIENT_ID
15. UPPER_CLIENT_ID
16. NET_30_DAYS_CLIENTS

**Note:** No `command` in base task definition. Commands passed via EventBridge container overrides.

---

### EventBridge Schedule Design

**Daily Send Invoices:**
```json
{
  "schedule": "cron(0 14 * * ? *)",
  "description": "6 AM PST = 14:00 UTC",
  "containerOverrides": [{
    "name": "invoice-processor",
    "command": ["--send-invoices"]
  }]
}
```

**Monthly Create Invoices:**
```json
{
  "schedule": "cron(0 10 4 * ? *)",
  "description": "2 AM PST = 10:00 UTC on 4th",
  "containerOverrides": [{
    "name": "invoice-processor",
    "command": ["--create-invoices"]
  }]
}
```

**Timezone Handling:**
- EventBridge uses UTC
- PST = UTC-8 (standard time, Nov-Mar)
- PDT = UTC-7 (daylight time, Mar-Nov)
- Current schedules use standard time (PST)
- If you want to handle daylight saving automatically, consider two separate schedule variables with enable/disable flags

---

### IAM Policy Details

**Task Execution Role Policy (AWS Managed):**
- `AmazonECSTaskExecutionRolePolicy`
  - ECR: `GetAuthorizationToken`, `BatchCheckLayerAvailability`, `GetDownloadUrlForLayer`, `BatchGetImage`
  - CloudWatch Logs: `CreateLogStream`, `PutLogEvents`

**Task Role Custom Policy:**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:UpdateSecret"
      ],
      "Resource": [
        "arn:aws:secretsmanager:us-west-2:<ACCOUNT>:secret:QBO/10000*",
        "arn:aws:secretsmanager:us-west-2:<ACCOUNT>:secret:MsGraph/10000*",
        "arn:aws:secretsmanager:us-west-2:<ACCOUNT>:secret:ClickUp/10000*",
        "arn:aws:secretsmanager:us-west-2:<ACCOUNT>:secret:RoboCorp/10000/ClientAPIKeys*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:Query",
        "dynamodb:Scan"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:<ACCOUNT>:table/Robocorp_Client_Org_Workspace_IDs"
    }
  ]
}
```

**EventBridge Role Policy (AWS Managed):**
- `AmazonEC2ContainerServiceEventsRole`
  - ECS: `RunTask`
  - IAM: `PassRole`

---

## Cost Analysis

### Monthly Cost Breakdown (Estimated)

**ECS Fargate Compute:**
- Daily task (send-invoices): 30 runs × 5 min × (2 vCPU + 4 GB)
  - vCPU: 30 × (5/60) × 2 × $0.04048 = $0.20
  - Memory: 30 × (5/60) × 4 × $0.004445 = $0.04
- Monthly task (create-invoices): 1 run × 2 hr × (2 vCPU + 4 GB)
  - vCPU: 1 × 2 × 2 × $0.04048 = $0.16
  - Memory: 1 × 2 × 4 × $0.004445 = $0.04
- **Fargate Subtotal: $0.44/month**

**AWS Services:**
- VPC: $0.00 (no NAT Gateway)
- ECR storage: $0.10/GB × 1 GB = $0.10
- Secrets Manager: $0.40/secret × 4 = $1.60
- DynamoDB: On-demand reads ~$0.05
- CloudWatch Logs: $0.50/GB × 0.1 GB = $0.05
- **Services Subtotal: $1.80/month**

**Total: ~$2.25/month**

**Cost Optimization:**
- Use Fargate Spot for monthly task (70% savings, low interruption risk)
- Reduce CPU/memory if monitoring shows under-utilization
- Implement log filtering to reduce CloudWatch ingestion

---

## Testing Strategy

### Pre-Deployment Testing
- [x] Local Docker testing (already done via `docker-compose`)
- [ ] Terraform validation: `make plan`

### Post-Deployment Testing

**Phase 1: Infrastructure Validation**
```bash
# Verify all resources created
terraform show

# Check ECS cluster
aws ecs describe-clusters --clusters invoice-send-qbo-cluster --region us-west-2

# Check task definition
aws ecs list-task-definitions --family-prefix invoice-send-qbo --region us-west-2
```

**Phase 2: Manual Task Execution**
```bash
# Test send-invoices
make test-send-invoices

# Watch logs
make logs

# Test create-invoices
make test-create-invoices
```

**Phase 3: Schedule Validation**
```bash
# List EventBridge rules
aws events list-rules --name-prefix invoice-send-qbo --region us-west-2

# Describe rule targets
aws events list-targets-by-rule --rule invoice-send-qbo-send-daily --region us-west-2
```

**Phase 4: Permissions Testing**
- Verify task can read Secrets Manager secrets (check logs)
- Verify task can update QBO secret (refresh token rotation)
- Verify task can read DynamoDB table (check logs)

**Phase 5: End-to-End**
- Wait for next scheduled execution
- Verify task completes successfully
- Check email notification received (send-invoices only)

---

## Rollback Plan

### Scenario 1: Terraform Apply Fails
- Review error messages
- Fix configuration
- Re-run `make apply`
- Terraform is atomic per resource (no partial state)

### Scenario 2: Task Fails at Runtime
```bash
# Check CloudWatch logs
make logs

# Verify environment variables in task definition
aws ecs describe-task-definition --task-definition invoice-send-qbo --region us-west-2

# Test secret access manually
aws secretsmanager get-secret-value --secret-id QBO/10000 --region us-west-2
```

### Scenario 3: Disable Schedules
```bash
# Disable via Terraform
cd infra
terraform apply -var="enable_send_invoices_schedule=false" -var="enable_create_invoices_schedule=false"

# Or disable via AWS CLI
aws events disable-rule --name invoice-send-qbo-send-daily --region us-west-2
```

### Scenario 4: Complete Teardown
```bash
make destroy
# Confirm destruction
# Note: ECR images retained (keep_remotely = true)
```

---

## Security Considerations

### Secrets Management
- ✅ Secrets stored in AWS Secrets Manager (encrypted at rest)
- ✅ QBO refresh tokens automatically updated via app code
- ✅ IAM policies use least-privilege principle
- ⚠️ **CRITICAL:** Add `terraform.tfvars` to `.gitignore` (contains sensitive values)

### Network Security
- ✅ Security group allows egress only (no inbound)
- ✅ Tasks use ephemeral public IPs (no persistent endpoints)
- ⚠️ Public IPs visible to external APIs (acceptable for API client use case)
- 📌 For enhanced security: Use private subnets + NAT Gateway (+$32/month)

### IAM Security
- ✅ Separate roles for task execution vs task runtime
- ✅ Wildcard suffixes on secret ARNs handle version rotation
- ✅ DynamoDB policy grants read-only access

### Audit Trail
- ✅ CloudWatch Logs retain 30 days of execution history
- ✅ All infrastructure changes tracked in Terraform state
- ✅ EventBridge execution history available in AWS Console

---

## Troubleshooting Guide

### Issue: Task Fails with "Permission Denied" on Secrets Manager
**Diagnosis:**
```bash
# Check IAM role attached to task
aws ecs describe-task-definition --task-definition invoice-send-qbo --query 'taskDefinition.taskRoleArn'

# Check IAM policy
aws iam get-role-policy --role-name ecsTaskRole-InvoiceProcessor --policy-name InvoiceProcessorTaskPolicy
```

**Solution:** Verify secret ARNs in IAM policy include wildcard suffix (`QBO/10000*`)

---

### Issue: Task Cannot Reach External APIs
**Diagnosis:**
```bash
# Check security group rules
aws ec2 describe-security-groups --group-ids <SG_ID> --region us-west-2

# Check task network configuration
aws ecs describe-tasks --cluster invoice-send-qbo-cluster --tasks <TASK_ARN> --region us-west-2
```

**Solution:** Ensure security group allows egress HTTPS (443), task has public IP

---

### Issue: Scheduled Rules Not Triggering
**Diagnosis:**
```bash
# Check rule status
aws events describe-rule --name invoice-send-qbo-send-daily --region us-west-2

# Check rule targets
aws events list-targets-by-rule --rule invoice-send-qbo-send-daily --region us-west-2
```

**Solution:** Verify rule is `ENABLED`, check EventBridge IAM role has `ecs:RunTask` permission

---

### Issue: Docker Build Fails in Terraform
**Error:** `docker_image.invoice_send: Error building image`

**Solution:**
```bash
# Build Docker image manually to see full error
cd send_qbo_invoices
docker build -t test .

# Check requirements.txt for incompatible dependencies
# Verify Dockerfile syntax
```

---

## Next Steps After Deployment

### Week 1: Monitoring and Validation
- [ ] Monitor daily scheduled executions in CloudWatch Logs
- [ ] Verify email notifications received
- [ ] Check Secrets Manager for updated QBO refresh token
- [ ] Review CloudWatch Container Insights metrics

### Week 2: Optimization
- [ ] Review CPU/memory utilization in Container Insights
- [ ] Adjust `ecs_task_cpu` and `ecs_task_memory` if needed
- [ ] Consider Fargate Spot for monthly task
- [ ] Set up CloudWatch alarms with SNS notifications

### Week 3: Production Hardening
- [ ] Update feature flags in `terraform.tfvars`:
  - `upload_to_sharepoint = "true"`
  - `create_invoice = "true"`
  - `update_clickup = "true"`
- [ ] Run `make apply` to update environment variables
- [ ] Test end-to-end with production flags enabled

### Week 4: Documentation
- [ ] Document actual deployment experience
- [ ] Update CLAUDE.md with production deployment section
- [ ] Create runbook for common operations
- [ ] Share Makefile targets with team

---

## Critical Files to Create/Modify

### New Files (5)
1. `infra/network.tf` - VPC, subnets, security groups (~120 lines)
2. `infra/iam.tf` - IAM roles and policies (~200 lines)
3. `infra/ecs.tf` - ECS cluster and task definition (~100 lines)
4. `infra/eventbridge.tf` - Scheduled rules (~120 lines)
5. `infra/cloudwatch.tf` - Log groups and alarms (~40 lines)

### Modified Files (2)
6. `infra/variables.tf` - Add 25+ variables (~150 lines added)
7. `infra/outputs.tf` - Add 10+ outputs (~50 lines added)

### Configuration Files (3)
8. `Makefile` - Deployment automation (project root, ~100 lines)
9. `infra/terraform.tfvars` - User configuration (git-ignored)
10. `infra/terraform.tfvars.example` - Configuration template

---

## Appendix A: Complete Variable Definitions

**Add to `infra/variables.tf`:**

```hcl
# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b"]
}

# ECS Configuration
variable "ecs_task_cpu" {
  description = "CPU units for ECS task (1024 = 1 vCPU)"
  type        = number
  default     = 2048
}

variable "ecs_task_memory" {
  description = "Memory for ECS task in MB"
  type        = number
  default     = 4096
}

# Application Environment Variables
variable "qbo_secret_name" {
  description = "AWS Secrets Manager path for QBO credentials"
  type        = string
  default     = "QBO/10000"
}

variable "msgraph_secret_name" {
  description = "AWS Secrets Manager path for Microsoft Graph credentials"
  type        = string
  default     = "MsGraph/10000"
}

variable "clickup_secret_name" {
  description = "AWS Secrets Manager path for ClickUp credentials"
  type        = string
  default     = "ClickUp/10000"
}

variable "robocorp_api_secret_name" {
  description = "AWS Secrets Manager path for Robocorp API keys"
  type        = string
  default     = "RoboCorp/10000/ClientAPIKeys"
}

variable "dynamodb_table_name" {
  description = "DynamoDB table for Robocorp client data"
  type        = string
  default     = "Robocorp_Client_Org_Workspace_IDs"
}

variable "bookkeeper_email" {
  description = "Email address for invoice summary notifications"
  type        = string
  # NO DEFAULT - User must provide
}

variable "sender_email" {
  description = "From address for email notifications"
  type        = string
  # NO DEFAULT - User must provide
}

variable "excluded_customers" {
  description = "Comma-separated list of customers to exclude"
  type        = string
  default     = ""
}

variable "ms_graph_hostname" {
  description = "Microsoft Graph hostname for SharePoint"
  type        = string
  default     = "automatapracdev.sharepoint.com"
}

variable "upload_to_sharepoint" {
  description = "Enable SharePoint upload"
  type        = string
  default     = "false"
}

variable "create_invoice" {
  description = "Enable invoice creation in QuickBooks"
  type        = string
  default     = "false"
}

variable "update_clickup" {
  description = "Enable ClickUp updates"
  type        = string
  default     = "false"
}

variable "lower_client_id" {
  description = "Lower bound of client ID range"
  type        = string
  default     = "10000"
}

variable "upper_client_id" {
  description = "Upper bound of client ID range"
  type        = string
  default     = "20030"
}

variable "net_30_days_clients" {
  description = "Comma-separated list of NET 30 client IDs"
  type        = string
  default     = ""
}

# CloudWatch Configuration
variable "log_retention_days" {
  description = "CloudWatch Logs retention period"
  type        = number
  default     = 30
}

# Schedule Configuration
variable "send_invoices_schedule" {
  description = "Cron expression for send invoices (UTC) - Default: 6 AM PST = 14:00 UTC"
  type        = string
  default     = "cron(0 14 * * ? *)"
}

variable "create_invoices_schedule" {
  description = "Cron expression for create invoices (UTC) - Default: 2 AM PST on 4th = 10:00 UTC"
  type        = string
  default     = "cron(0 10 4 * ? *)"
}

variable "enable_send_invoices_schedule" {
  description = "Enable daily send invoices schedule"
  type        = bool
  default     = true
}

variable "enable_create_invoices_schedule" {
  description = "Enable monthly create invoices schedule"
  type        = bool
  default     = true
}
```

---

## Appendix B: Complete Makefile

**Create `Makefile` in project root:**

```makefile
.PHONY: help init plan apply destroy build push deploy test clean logs

# Variables
AWS_REGION ?= us-west-2
AWS_ACCOUNT_ID ?= $(shell aws sts get-caller-identity --query Account --output text)
ECR_REPO_NAME = invoice-send-qbo
IMAGE_TAG ?= latest
DOCKER_CONTEXT = send_qbo_invoices
INFRA_DIR = infra

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Available targets:'
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Terraform targets
init: ## Initialize Terraform
	cd $(INFRA_DIR) && terraform init

validate: ## Validate Terraform configuration
	cd $(INFRA_DIR) && terraform validate

plan: ## Plan Terraform changes
	cd $(INFRA_DIR) && terraform plan

apply: ## Apply Terraform changes
	cd $(INFRA_DIR) && terraform apply

destroy: ## Destroy Terraform resources
	cd $(INFRA_DIR) && terraform destroy

# Docker targets
build: ## Build Docker image locally
	cd $(DOCKER_CONTEXT) && docker build --platform linux/amd64 -t $(ECR_REPO_NAME):$(IMAGE_TAG) .

ecr-login: ## Authenticate Docker to ECR
	aws ecr get-login-password --region $(AWS_REGION) | \
		docker login --username AWS --password-stdin $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

tag: ## Tag image for ECR
	docker tag $(ECR_REPO_NAME):$(IMAGE_TAG) \
		$(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

push: ecr-login tag ## Push image to ECR
	docker push $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG)

# Combined targets
build-and-push: build push ## Build and push Docker image

deploy: build-and-push apply ## Full deployment (build + push + Terraform apply)

# Testing targets
test-send-invoices: ## Run manual test of send-invoices task
	aws ecs run-task \
		--cluster $(shell cd $(INFRA_DIR) && terraform output -raw ecs_cluster_name) \
		--task-definition $(shell cd $(INFRA_DIR) && terraform output -raw ecs_task_definition_arn) \
		--launch-type FARGATE \
		--network-configuration "awsvpcConfiguration={subnets=[$(shell cd $(INFRA_DIR) && terraform output -json public_subnet_ids | jq -r '.[0]')],securityGroups=[$(shell cd $(INFRA_DIR) && terraform output -raw security_group_id)],assignPublicIp=ENABLED}" \
		--overrides '{"containerOverrides": [{"name": "invoice-processor", "command": ["--send-invoices"]}]}' \
		--region $(AWS_REGION)

test-create-invoices: ## Run manual test of create-invoices task
	aws ecs run-task \
		--cluster $(shell cd $(INFRA_DIR) && terraform output -raw ecs_cluster_name) \
		--task-definition $(shell cd $(INFRA_DIR) && terraform output -raw ecs_task_definition_arn) \
		--launch-type FARGATE \
		--network-configuration "awsvpcConfiguration={subnets=[$(shell cd $(INFRA_DIR) && terraform output -json public_subnet_ids | jq -r '.[0]')],securityGroups=[$(shell cd $(INFRA_DIR) && terraform output -raw security_group_id)],assignPublicIp=ENABLED}" \
		--overrides '{"containerOverrides": [{"name": "invoice-processor", "command": ["--create-invoices"]}]}' \
		--region $(AWS_REGION)

logs: ## Tail CloudWatch logs
	aws logs tail $(shell cd $(INFRA_DIR) && terraform output -raw cloudwatch_log_group) --follow --region $(AWS_REGION)

# Cleanup
clean: ## Clean local Docker images
	docker rmi $(ECR_REPO_NAME):$(IMAGE_TAG) || true
	docker rmi $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com/$(ECR_REPO_NAME):$(IMAGE_TAG) || true
```

---

## Summary

This plan provides complete infrastructure-as-code deployment for your QuickBooks invoice automation system to AWS ECS Fargate with scheduled execution. The implementation creates:

1. ✅ Complete networking infrastructure (VPC, subnets, security groups)
2. ✅ IAM roles with least-privilege permissions
3. ✅ ECS cluster and Fargate task definition
4. ✅ EventBridge scheduled rules (daily @ 6 AM PST, monthly 4th @ 2 AM PST)
5. ✅ CloudWatch logging and monitoring
6. ✅ Makefile for streamlined deployment
7. ✅ Configuration management with Terraform variables

**Total Infrastructure:** 30+ AWS resources managed by Terraform
**Estimated Cost:** ~$2.25/month
**Deployment Time:** ~30 minutes (initial setup + testing)

**Next Action:** Complete the Configuration Punch List above, then run `make deploy` to deploy all infrastructure.
