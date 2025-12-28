# Docker Setup Guide - QuickBooks Online Invoice Processor

This guide covers running the QBO invoice processor in Docker locally on your machine.

## Table of Contents
- [Prerequisites](#prerequisites)
- [AWS Permissions Required](#aws-permissions-required)
- [Initial Setup](#initial-setup)
- [Building the Docker Image](#building-the-docker-image)
- [Running the Container](#running-the-container)
- [Troubleshooting](#troubleshooting)
- [Testing Strategy](#testing-strategy)

---

## Prerequisites

### 1. Docker Desktop
- **Download**: [https://www.docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
- **Verify Installation**:
  ```bash
  docker --version
  docker-compose --version
  ```

### 2. AWS CLI Configured
- **Install AWS CLI**: [https://aws.amazon.com/cli/](https://aws.amazon.com/cli/)
- **Configure Credentials**:
  ```bash
  aws configure
  ```
  This creates `~/.aws/credentials` and `~/.aws/config` files

- **Verify Configuration**:
  ```bash
  aws sts get-caller-identity
  ```
  You should see your AWS account ID and user ARN

### 3. Docker Desktop Memory Allocation
- Open Docker Desktop → Settings → Resources
- Set Memory to **at least 4GB** (recommended for 2+ hour processing runs)
- Apply & Restart

---

## AWS Permissions Required

### Critical: Your AWS credentials MUST have the following permissions

The AWS CLI profile you configure must have access to:

#### 1. AWS Secrets Manager (Read/Update)
Your application needs to read and update secrets for:

- `QBO/10000*` - QuickBooks Online credentials (refresh tokens are automatically updated)
- `MsGraph/10000*` - Microsoft Graph API credentials
- `ClickUp/10000*` - ClickUp API credentials
- `RoboCorp/10000/ClientAPIKeys*` - Robocorp Control Room API keys (multiple clients)

**IAM Policy Example**:
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
        "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:QBO/10000*",
        "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:MsGraph/10000*",
        "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:ClickUp/10000*",
        "arn:aws:secretsmanager:us-west-2:YOUR_ACCOUNT_ID:secret:RoboCorp/10000/ClientAPIKeys*"
      ]
    }
  ]
}
```

#### 2. DynamoDB (Read)
Your application reads client organization and workspace IDs from DynamoDB:

- Table: `Robocorp_Client_Org_Workspace_IDs`

**IAM Policy Example**:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "dynamodb:Scan",
        "dynamodb:GetItem",
        "dynamodb:Query"
      ],
      "Resource": "arn:aws:dynamodb:us-west-2:YOUR_ACCOUNT_ID:table/Robocorp_Client_Org_Workspace_IDs"
    }
  ]
}
```

### Verify Your Permissions

Before running the container, verify you have access to all required resources:

```bash
# Test Secrets Manager access
aws secretsmanager get-secret-value --secret-id QBO/10000
aws secretsmanager get-secret-value --secret-id MsGraph/10000
aws secretsmanager get-secret-value --secret-id ClickUp/10000
aws secretsmanager get-secret-value --secret-id RoboCorp/10000/ClientAPIKeys

# Test DynamoDB access
aws dynamodb describe-table --table-name Robocorp_Client_Org_Workspace_IDs
aws dynamodb scan --table-name Robocorp_Client_Org_Workspace_IDs --limit 1
```

If any of these commands fail, you don't have the necessary permissions. Contact your AWS administrator.

---

## Initial Setup

### 1. Navigate to the Project Directory
```bash
cd send_qbo_invoices
```

### 2. Create Environment Configuration
```bash
# Copy the template
cp .env.template .env

# Edit the .env file (optional - defaults are usually correct)
# nano .env  # or use your preferred text editor
```

**Important**: The `.env` file is optional if you're using the AWS CLI profile named `default` and all other default values are correct. The `docker-compose.yml` has sensible defaults.

### 3. Verify AWS Credentials File Location
```bash
# Windows
dir %USERPROFILE%\.aws

# Mac/Linux
ls ~/.aws
```

You should see `credentials` and `config` files.

---

## Building the Docker Image

### Build the Image
```bash
docker build -t qbo-invoice-processor .
```

**Expected Output**:
```
[+] Building 45.2s (12/12) FINISHED
 => [internal] load build definition from Dockerfile
 => => transferring dockerfile: 456B
 => [internal] load .dockerignore
 => [1/6] FROM docker.io/library/python:3.11-slim
 => [2/6] WORKDIR /app
 => [3/6] COPY requirements.txt .
 => [4/6] RUN pip install --no-cache-dir -r requirements.txt
 => [5/6] COPY shared/ ./shared/
 => [6/6] COPY entrypoint.py .
 => exporting to image
 => => writing image sha256:abc123...
 => => naming to docker.io/library/qbo-invoice-processor:latest
```

### Verify the Image Was Created
```bash
docker images | grep qbo-invoice-processor
```

You should see:
```
qbo-invoice-processor   latest    abc123def456   2 minutes ago   500MB
```

---

## Running the Container

### Option 1: Using Docker Compose (Recommended)

Docker Compose automatically loads environment variables from `.env` and mounts AWS credentials.

#### Send Today's Invoices
```bash
docker-compose run --rm invoice-processor --send-invoices
```

#### Create Monthly Invoices from Usage Data
```bash
docker-compose run --rm invoice-processor --create-invoices
```

**Flags Explained**:
- `--rm`: Automatically remove container when it exits
- `invoice-processor`: Service name from docker-compose.yml
- `--send-invoices` or `--create-invoices`: Command-line argument passed to entrypoint.py

---

### Option 2: Direct Docker Run (Without Compose)

Useful if you need to customize environment variables without editing `.env`:

#### Send Invoices
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  -e AWS_REGION=us-west-2 \
  -e QBO_SECRET_NAME=QBO/10000 \
  -e MSGRAPH_SECRET_NAME=MsGraph/10000 \
  -e CLICKUP_SECRET_NAME=ClickUp/10000 \
  -e ROBOCORP_API_SECRET_NAME=RoboCorp/10000/ClientAPIKeys \
  -e DYNAMODB_TABLE_ROBOCORP_CLIENTS=Robocorp_Client_Org_Workspace_IDs \
  -e BOOKKEEPER_EMAIL=whartman@automatapracdev.com \
  -e EXCLUDED_CUSTOMERS="10001 - AICPA" \
  -e SENDER_EMAIL=robotarmy@automatapracdev.com \
  -e MS_GRAPH_HOSTNAME=automatapracdev.sharepoint.com \
  qbo-invoice-processor --send-invoices
```

#### Create Invoices
```bash
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  -e AWS_REGION=us-west-2 \
  -e QBO_SECRET_NAME=QBO/10000 \
  -e MSGRAPH_SECRET_NAME=MsGraph/10000 \
  -e CLICKUP_SECRET_NAME=ClickUp/10000 \
  -e ROBOCORP_API_SECRET_NAME=RoboCorp/10000/ClientAPIKeys \
  -e DYNAMODB_TABLE_ROBOCORP_CLIENTS=Robocorp_Client_Org_Workspace_IDs \
  -e BOOKKEEPER_EMAIL=whartman@automatapracdev.com \
  -e EXCLUDED_CUSTOMERS="10001 - AICPA" \
  -e SENDER_EMAIL=robotarmy@automatapracdev.com \
  -e MS_GRAPH_HOSTNAME=automatapracdev.sharepoint.com \
  qbo-invoice-processor --create-invoices
```

**Flags Explained**:
- `--rm`: Remove container after exit
- `-v ~/.aws:/root/.aws:ro`: Mount AWS credentials (read-only)
- `-e VAR=value`: Set environment variables
- `qbo-invoice-processor`: Docker image name
- `--create-invoices`: Command to run

---

## Troubleshooting

### 1. AWS Credentials Not Found

**Error**:
```
botocore.exceptions.NoCredentialsError: Unable to locate credentials
```

**Solution**:
```bash
# Verify AWS credentials are configured
aws sts get-caller-identity

# Check if ~/.aws directory exists
ls ~/.aws

# If using Windows, ensure path is correct
docker run --rm -v %USERPROFILE%\.aws:/root/.aws:ro amazon/aws-cli sts get-caller-identity
```

---

### 2. Secrets Manager Access Denied

**Error**:
```
botocore.exceptions.ClientError: An error occurred (AccessDeniedException) when calling the GetSecretValue operation
```

**Solution**:
```bash
# Test access to each secret
aws secretsmanager get-secret-value --secret-id QBO/10000
aws secretsmanager get-secret-value --secret-id MsGraph/10000
aws secretsmanager get-secret-value --secret-id ClickUp/10000

# If access denied, contact your AWS administrator to add the IAM policy shown in the "AWS Permissions Required" section
```

---

### 3. DynamoDB Table Not Found or Access Denied

**Error**:
```
botocore.exceptions.ClientError: An error occurred (ResourceNotFoundException) when calling the DescribeTable operation
```

**Solution**:
```bash
# Verify table exists
aws dynamodb describe-table --table-name Robocorp_Client_Org_Workspace_IDs

# Test scan permission
aws dynamodb scan --table-name Robocorp_Client_Org_Workspace_IDs --limit 1

# If access denied, add the DynamoDB IAM policy shown above
```

---

### 4. Container Crashes Immediately

**Error**: Container exits immediately without logs

**Solution**:
```bash
# Run with interactive terminal to see error messages
docker run -it \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  -e AWS_REGION=us-west-2 \
  qbo-invoice-processor --create-invoices

# Check Docker logs
docker logs <container_id>

# Verify entrypoint.py has correct imports
docker run --rm qbo-invoice-processor python -c "import process_and_send_qbo_invoices; import task_minutes_to_clickup_and_qbo"
```

---

### 5. Import Errors (Module Not Found)

**Error**:
```
ModuleNotFoundError: No module named 'apd_quickbooksonline'
```

**Solution**:
This means PYTHONPATH is not set correctly. Verify Dockerfile has:
```dockerfile
ENV PYTHONPATH="/app/shared:${PYTHONPATH}"
```

Rebuild the image:
```bash
docker build -t qbo-invoice-processor .
```

---

### 6. Verify AWS Credentials Are Mounted Correctly

Test that AWS credentials are accessible inside the container:

```bash
# Using AWS CLI image (this should work if credentials are mounted correctly)
docker run --rm -v ~/.aws:/root/.aws:ro amazon/aws-cli sts get-caller-identity

# Using your image
docker run --rm \
  -v ~/.aws:/root/.aws:ro \
  -e AWS_PROFILE=default \
  qbo-invoice-processor python -c "import boto3; print(boto3.client('sts').get_caller_identity())"
```

---

### 7. Long Running Process Times Out

If processing 20+ clients takes over 2 hours and your AWS credentials use SSO or temporary tokens:

**Solution**:
- Use long-lived IAM user credentials (not SSO)
- Or implement credential refresh logic in the code
- Or run with smaller client batches by modifying `LOWER_CLIENT_ID` and `UPPER_CLIENT_ID` in `task_minutes_to_clickup_and_qbo.py`

---

## Testing Strategy

### Phase 1: Verify Container Starts
```bash
docker-compose run --rm invoice-processor --help
```

You should see the help message with usage instructions.

---

### Phase 2: Test with Single Client

Before processing all clients, test with a single client to verify everything works:

1. **Edit** `send_qbo_invoices/shared/task_minutes_to_clickup_and_qbo.py`
2. **Temporarily modify** lines 30-31:
   ```python
   LOWER_CLIENT_ID = 10001  # Start with a single test client
   UPPER_CLIENT_ID = 10002  # Process only one client
   ```
3. **Rebuild** the Docker image:
   ```bash
   docker build -t qbo-invoice-processor .
   ```
4. **Run** the create-invoices function:
   ```bash
   docker-compose run --rm invoice-processor --create-invoices
   ```
5. **Verify** the output shows processing for only one client
6. **Restore** original values after testing

---

### Phase 3: Run Full Processing

Once single-client testing succeeds:

1. **Restore** the original client ID range in `task_minutes_to_clickup_and_qbo.py`:
   ```python
   LOWER_CLIENT_ID = 10000  # Include this client ID
   UPPER_CLIENT_ID = 10030  # Exclude this client ID
   ```
2. **Rebuild** the image:
   ```bash
   docker build -t qbo-invoice-processor .
   ```
3. **Run** with all clients:
   ```bash
   docker-compose run --rm invoice-processor --create-invoices
   ```

---

### Phase 4: Test Send Invoices Function

After create-invoices works successfully:

```bash
docker-compose run --rm invoice-processor --send-invoices
```

This sends today's QuickBooks invoices to clients and emails a summary to the bookkeeper.

---

### Phase 5: Monitor AWS Costs

Running locally still makes AWS API calls. Monitor your costs:

- **Secrets Manager**: ~$0.40 per 10,000 API calls
- **DynamoDB**: On-demand pricing or free tier
- **CloudWatch Logs**: Not used (logs go to Docker stdout)

Check your AWS billing console after test runs.

---

## Next Steps

Once local Docker testing is successful, see [README.ECS-DEPLOYMENT.md](README.ECS-DEPLOYMENT.md) for deploying to AWS ECS Fargate.

---

## Quick Reference

### Build
```bash
docker build -t qbo-invoice-processor .
```

### Run - Send Invoices
```bash
docker-compose run --rm invoice-processor --send-invoices
```

### Run - Create Invoices
```bash
docker-compose run --rm invoice-processor --create-invoices
```

### View Logs in Real-Time
Logs are automatically streamed to your terminal. No separate command needed.

### Clean Up
```bash
# Remove stopped containers
docker container prune

# Remove unused images
docker image prune

# Remove everything (use with caution)
docker system prune -a
```
