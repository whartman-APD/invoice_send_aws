# AWS ECS Fargate Deployment Guide

This guide covers deploying the QuickBooks Online Invoice Processor to AWS ECS Fargate for production use.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Step 1: Push Image to ECR](#step-1-push-image-to-ecr)
- [Step 2: Create IAM Roles](#step-2-create-iam-roles)
- [Step 3: Create ECS Task Definition](#step-3-create-ecs-task-definition)
- [Step 4: Create EventBridge Scheduled Rules](#step-4-create-eventbridge-scheduled-rules)
- [Step 5: Configure Monitoring](#step-5-configure-monitoring)
- [Testing Deployment](#testing-deployment)
- [Cost Estimation](#cost-estimation)

---

## Overview

**Why ECS Fargate?**
- No timeout limits (unlike Lambda's 15 min max)
- Serverless container platform (no EC2 management)
- Integrates with EventBridge for scheduling
- Same IAM permissions model as Lambda
- CloudWatch Logs for monitoring

**Architecture**:
```
EventBridge Schedule → ECS Run Task (Fargate) → Docker Container → AWS Resources
```

---

## Prerequisites

- [x] Docker image tested locally (see [README.DOCKER.md](README.DOCKER.md))
- [x] AWS CLI configured with administrator or ECS deployment permissions
- [x] AWS account with ECS and ECR enabled

---

## Step 1: Push Image to ECR

### 1.1 Create ECR Repository

```bash
# Create repository
aws ecr create-repository \
  --repository-name qbo-invoice-processor \
  --region us-west-2

# Expected output:
# {
#   "repository": {
#     "repositoryArn": "arn:aws:ecr:us-west-2:123456789012:repository/qbo-invoice-processor",
#     "registryId": "123456789012",
#     "repositoryName": "qbo-invoice-processor",
#     "repositoryUri": "123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor"
#   }
# }
```

**Save the `repositoryUri` - you'll need it later.**

---

### 1.2 Authenticate Docker to ECR

```bash
# Get login password and authenticate
aws ecr get-login-password --region us-west-2 | \
  docker login --username AWS --password-stdin \
  123456789012.dkr.ecr.us-west-2.amazonaws.com
```

**Replace `123456789012` with your AWS account ID.**

---

### 1.3 Tag and Push Image

```bash
# Tag your local image for ECR
docker tag qbo-invoice-processor:latest \
  123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor:latest

# Push to ECR
docker push 123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor:latest
```

**This may take 5-10 minutes depending on image size and upload speed.**

---

### 1.4 Verify Image in ECR

```bash
# List images in repository
aws ecr describe-images \
  --repository-name qbo-invoice-processor \
  --region us-west-2
```

---

## Step 2: Create IAM Roles

You need **two separate IAM roles**:

### 2.1 Task Execution Role

**Purpose**: Allows ECS to pull images from ECR and write logs to CloudWatch.

**Create Role**:
```bash
aws iam create-role \
  --role-name ecsTaskExecutionRole-QBOInvoiceProcessor \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

**Attach AWS Managed Policy**:
```bash
aws iam attach-role-policy \
  --role-name ecsTaskExecutionRole-QBOInvoiceProcessor \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy
```

---

### 2.2 Task Role (Application Permissions)

**Purpose**: Gives your application access to Secrets Manager and DynamoDB.

**Create Policy Document** (`task-role-policy.json`):
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
        "arn:aws:secretsmanager:us-west-2:123456789012:secret:QBO/10000*",
        "arn:aws:secretsmanager:us-west-2:123456789012:secret:MsGraph/10000*",
        "arn:aws:secretsmanager:us-west-2:123456789012:secret:ClickUp/10000*",
        "arn:aws:secretsmanager:us-west-2:123456789012:secret:RoboCorp/10000/ClientAPIKeys*"
      ]
    },
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:GetItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:123456789012:table/Robocorp_Client_Org_Workspace_IDs"
    }
  ]
}
```

**Replace `123456789012` with your AWS account ID.**

**Create Role**:
```bash
aws iam create-role \
  --role-name ecsTaskRole-QBOInvoiceProcessor \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "ecs-tasks.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'
```

**Create and Attach Custom Policy**:
```bash
# Create policy
aws iam create-policy \
  --policy-name QBOInvoiceProcessorTaskPolicy \
  --policy-document file://task-role-policy.json

# Attach to role
aws iam attach-role-policy \
  --role-name ecsTaskRole-QBOInvoiceProcessor \
  --policy-arn arn:aws:iam::123456789012:policy/QBOInvoiceProcessorTaskPolicy
```

---

## Step 3: Create ECS Task Definition

### 3.1 Create Task Definition JSON

**File**: `task-definition.json`

```json
{
  "family": "qbo-invoice-processor",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "executionRoleArn": "arn:aws:iam::123456789012:role/ecsTaskExecutionRole-QBOInvoiceProcessor",
  "taskRoleArn": "arn:aws:iam::123456789012:role/ecsTaskRole-QBOInvoiceProcessor",
  "containerDefinitions": [
    {
      "name": "invoice-processor",
      "image": "123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor:latest",
      "essential": true,
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/qbo-invoice-processor",
          "awslogs-region": "us-west-2",
          "awslogs-stream-prefix": "ecs",
          "awslogs-create-group": "true"
        }
      },
      "environment": [
        {"name": "AWS_REGION", "value": "us-west-2"},
        {"name": "QBO_SECRET_NAME", "value": "QBO/10000"},
        {"name": "MSGRAPH_SECRET_NAME", "value": "MsGraph/10000"},
        {"name": "CLICKUP_SECRET_NAME", "value": "ClickUp/10000"},
        {"name": "ROBOCORP_API_SECRET_NAME", "value": "RoboCorp/10000/ClientAPIKeys"},
        {"name": "DYNAMODB_TABLE_ROBOCORP_CLIENTS", "value": "Robocorp_Client_Org_Workspace_IDs"},
        {"name": "BOOKKEEPER_EMAIL", "value": "whartman@automatapracdev.com"},
        {"name": "SENDER_EMAIL", "value": "robotarmy@automatapracdev.com"},
        {"name": "EXCLUDED_CUSTOMERS", "value": "10001 - AICPA"},
        {"name": "MS_GRAPH_HOSTNAME", "value": "automatapracdev.sharepoint.com"}
      ]
    }
  ]
}
```

**Note**: Update all ARNs with your AWS account ID.

**CPU/Memory Settings**:
- `cpu: "2048"` = 2 vCPU
- `memory: "4096"` = 4 GB RAM
- Adjust based on actual usage (monitor CloudWatch metrics after deployment)

---

### 3.2 Register Task Definition

```bash
aws ecs register-task-definition \
  --cli-input-json file://task-definition.json \
  --region us-west-2
```

---

### 3.3 Create ECS Cluster

```bash
aws ecs create-cluster \
  --cluster-name qbo-invoice-processor-cluster \
  --region us-west-2
```

---

## Step 4: Create EventBridge Scheduled Rules

### 4.1 Create IAM Role for EventBridge

**Purpose**: Allows EventBridge to run ECS tasks.

```bash
# Create role
aws iam create-role \
  --role-name EventBridgeECSRole-QBOInvoiceProcessor \
  --assume-role-policy-document '{
    "Version": "2012-10-17",
    "Statement": [{
      "Effect": "Allow",
      "Principal": {"Service": "events.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }]
  }'

# Attach policy
aws iam attach-role-policy \
  --role-name EventBridgeECSRole-QBOInvoiceProcessor \
  --policy-arn arn:aws:iam::aws:policy/service-role/AmazonEC2ContainerServiceEventsRole
```

---

### 4.2 Create Rule: Send Invoices (Daily at 5 AM Pacific)

**Note**: Pacific Time is UTC-8 (standard) or UTC-7 (daylight). Schedule runs at **12:00 UTC** (5 AM Pacific Standard Time).

```bash
aws events put-rule \
  --name qbo-send-invoices-daily \
  --description "Send QuickBooks Online invoices daily at 5 AM Pacific" \
  --schedule-expression "cron(0 12 * * ? *)" \
  --region us-west-2
```

**Add ECS Task as Target**:

First, create target configuration JSON (`send-invoices-target.json`):
```json
{
  "Id": "1",
  "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/qbo-invoice-processor-cluster",
  "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeECSRole-QBOInvoiceProcessor",
  "EcsParameters": {
    "TaskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/qbo-invoice-processor:1",
    "TaskCount": 1,
    "LaunchType": "FARGATE",
    "NetworkConfiguration": {
      "awsvpcConfiguration": {
        "Subnets": ["subnet-xxxxxxxxx"],
        "SecurityGroups": ["sg-xxxxxxxxx"],
        "AssignPublicIp": "ENABLED"
      }
    },
    "PlatformVersion": "LATEST"
  },
  "Input": "{\"containerOverrides\": [{\"name\": \"invoice-processor\", \"command\": [\"--send-invoices\"]}]}"
}
```

**Update**:
- Subnet ID (get from VPC console)
- Security Group ID (create one that allows outbound HTTPS)
- Task Definition ARN (from step 3.2)

```bash
aws events put-targets \
  --rule qbo-send-invoices-daily \
  --targets file://send-invoices-target.json \
  --region us-west-2
```

---

### 4.3 Create Rule: Create Invoices (Monthly on 4th at 9 AM Pacific)

**Note**: 9 AM Pacific = **17:00 UTC**

```bash
aws events put-rule \
  --name qbo-create-invoices-monthly \
  --description "Create QuickBooks Online invoices monthly on 4th at 9 AM Pacific" \
  --schedule-expression "cron(0 17 4 * ? *)" \
  --region us-west-2
```

**Add ECS Task as Target** (`create-invoices-target.json`):
```json
{
  "Id": "1",
  "Arn": "arn:aws:ecs:us-west-2:123456789012:cluster/qbo-invoice-processor-cluster",
  "RoleArn": "arn:aws:iam::123456789012:role/EventBridgeECSRole-QBOInvoiceProcessor",
  "EcsParameters": {
    "TaskDefinitionArn": "arn:aws:ecs:us-west-2:123456789012:task-definition/qbo-invoice-processor:1",
    "TaskCount": 1,
    "LaunchType": "FARGATE",
    "NetworkConfiguration": {
      "awsvpcConfiguration": {
        "Subnets": ["subnet-xxxxxxxxx"],
        "SecurityGroups": ["sg-xxxxxxxxx"],
        "AssignPublicIp": "ENABLED"
      }
    },
    "PlatformVersion": "LATEST"
  },
  "Input": "{\"containerOverrides\": [{\"name\": \"invoice-processor\", \"command\": [\"--create-invoices\"]}]}"
}
```

```bash
aws events put-targets \
  --rule qbo-create-invoices-monthly \
  --targets file://create-invoices-target.json \
  --region us-west-2
```

---

## Step 5: Configure Monitoring

### 5.1 Create CloudWatch Log Group

This is automatically created by the task definition, but you can create it manually:

```bash
aws logs create-log-group \
  --log-group-name /ecs/qbo-invoice-processor \
  --region us-west-2
```

**Set Retention**:
```bash
aws logs put-retention-policy \
  --log-group-name /ecs/qbo-invoice-processor \
  --retention-in-days 30 \
  --region us-west-2
```

---

### 5.2 Create CloudWatch Alarms

#### Task Failure Alarm

```bash
aws cloudwatch put-metric-alarm \
  --alarm-name qbo-invoice-processor-task-failures \
  --alarm-description "Alert when ECS task fails" \
  --metric-name TasksFailed \
  --namespace ECS/ContainerInsights \
  --statistic Sum \
  --period 300 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --evaluation-periods 1 \
  --dimensions Name=ClusterName,Value=qbo-invoice-processor-cluster \
  --region us-west-2
```

**TODO**: Add SNS topic ARN for email notifications

---

## Testing Deployment

### Manual Task Execution

Test your ECS task manually before relying on scheduled execution:

```bash
aws ecs run-task \
  --cluster qbo-invoice-processor-cluster \
  --task-definition qbo-invoice-processor:1 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-xxxxxxxxx],securityGroups=[sg-xxxxxxxxx],assignPublicIp=ENABLED}" \
  --overrides '{"containerOverrides": [{"name": "invoice-processor", "command": ["--create-invoices"]}]}' \
  --region us-west-2
```

**Monitor Logs**:
```bash
# Get task ID from run-task output, then:
aws logs tail /ecs/qbo-invoice-processor --follow --region us-west-2
```

---

## Cost Estimation

### ECS Fargate Costs (us-west-2)

**Configuration**: 2 vCPU, 4 GB RAM

**Pricing** (as of 2025):
- vCPU: $0.04048 per vCPU per hour
- Memory: $0.004445 per GB per hour

**Example Monthly Cost**:

#### Send Invoices (Daily)
- Runs: 30 times/month
- Duration: ~5 minutes = 0.083 hours
- vCPU Cost: 2 × $0.04048 × 0.083 × 30 = **$0.20/month**
- Memory Cost: 4 × $0.004445 × 0.083 × 30 = **$0.04/month**
- **Total per month: ~$0.24**

#### Create Invoices (Monthly, 2 hours)
- Runs: 1 time/month
- Duration: ~2 hours
- vCPU Cost: 2 × $0.04048 × 2 = **$0.16**
- Memory Cost: 4 × $0.004445 × 2 = **$0.04**
- **Total per month: ~$0.20**

**Combined Fargate Cost**: ~$0.44/month

**Other AWS Costs**:
- Secrets Manager: ~$0.40 per 10,000 API calls
- DynamoDB: On-demand or free tier
- CloudWatch Logs: $0.50/GB ingested
- Data Transfer: Minimal (outbound to APIs)

**Estimated Total Monthly Cost**: **$1-3/month** (far less than running EC2 24/7)

---

## Updating the Deployment

### Update Docker Image

1. Make code changes locally
2. Build new image: `docker build -t qbo-invoice-processor .`
3. Tag for ECR: `docker tag qbo-invoice-processor:latest 123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor:latest`
4. Push: `docker push 123456789012.dkr.ecr.us-west-2.amazonaws.com/qbo-invoice-processor:latest`
5. Update task definition (increment revision number)
6. Scheduled tasks will automatically use the new revision

---

## Decommissioning Lambda Functions

Once ECS deployment is stable:

1. Disable Lambda EventBridge triggers (already `Enabled: false` in template.yaml)
2. Monitor ECS execution for 1-2 months
3. Delete Lambda functions: `sam delete --stack-name send_qbo_invoices`
4. Keep `template.yaml` for reference

---

## Support & Troubleshooting

### View ECS Task Logs
```bash
aws logs tail /ecs/qbo-invoice-processor --follow --region us-west-2
```

### List Running Tasks
```bash
aws ecs list-tasks --cluster qbo-invoice-processor-cluster --region us-west-2
```

### Describe Task (Get Details)
```bash
aws ecs describe-tasks \
  --cluster qbo-invoice-processor-cluster \
  --tasks <task-arn> \
  --region us-west-2
```

### Common Issues
- **Task fails immediately**: Check IAM task role permissions
- **Cannot pull image**: Verify ECR permissions in execution role
- **No logs**: Check CloudWatch Logs permissions
- **Network timeout**: Verify security group allows outbound HTTPS
