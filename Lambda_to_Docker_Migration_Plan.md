# Lambda to Docker Migration Plan

## Overview
Convert the AWS SAM Lambda application to a Docker container that can run locally and eventually deploy to AWS ECS Fargate. This solves the Lambda timeout limitation (currently 2+ hours needed vs 15 min max).

## User Preferences
- **AWS Credentials**: Use AWS CLI credentials (~/.aws/credentials)
- **Scheduling**: Manual execution initially
- **Deployment Target**: AWS ECS Fargate (future)
- **Architecture**: Single container with command-line arguments

## Migration Strategy

### Phase 1: Create Docker Container for Local Execution

#### 1.1 Create Dockerfile
**File**: `send_qbo_invoices/Dockerfile`

- Base image: `python:3.11-slim` (matches Lambda runtime)
- Install system dependencies if needed
- Copy `requirements.txt` and install Python dependencies
- Copy application code (`shared/`, `send_invoices/`, `create_invoices/`)
- Set working directory
- Create entrypoint script that accepts command-line arguments

#### 1.2 Create Container Entrypoint Script
**File**: `send_qbo_invoices/entrypoint.py`

- Accept command-line arguments: `--send-invoices` or `--create-invoices`
- Import and call appropriate function:
  - `--send-invoices` → calls `send_qbo_invoices()` from `shared.process_and_send_qbo_invoices`
  - `--create-invoices` → calls `process_all_clients()` from `shared.task_minutes_to_clickup_and_qbo`
- Set up logging to stdout (Docker-friendly)
- Handle environment variables
- Exit with appropriate status codes

#### 1.3 Create Docker Compose Configuration
**File**: `send_qbo_invoices/docker-compose.yml`

- Define service with environment variables from `.env` file
- Mount AWS credentials from host: `~/.aws:/root/.aws:ro`
- Set AWS_REGION, AWS_PROFILE environment variables
- Map all required environment variables:
  - `QBO_SECRET_NAME=QBO/10000`
  - `MSGRAPH_SECRET_NAME=MsGraph/10000`
  - `CLICKUP_SECRET_NAME=ClickUp/10000`
  - `ROBOCORP_API_SECRET_NAME=RoboCorp/10000/ClientAPIKeys`
  - `DYNAMODB_TABLE_ROBOCORP_CLIENTS=Robocorp_Client_Org_Workspace_IDs`
  - `BOOKKEEPER_EMAIL=whartman@automatapracdev.com`
  - `EXCLUDED_CUSTOMERS=10001 - AICPA`
  - `SENDER_EMAIL=robotarmy@automatapracdev.com`
  - `MS_GRAPH_HOSTNAME=automatapracdev.sharepoint.com`

#### 1.4 Create Environment Template
**File**: `send_qbo_invoices/.env.template`

- Document all required environment variables
- Include instructions for AWS_PROFILE setup
- User copies to `.env` and fills in values

#### 1.5 Update .gitignore
**File**: `send_qbo_invoices/.gitignore`

- Add `.env` to prevent committing credentials
- Already has `.aws-sam` ignored

### Phase 2: Refactor Lambda Handlers (Minimal Changes)

#### 2.1 Keep Existing Functions Unchanged
**Files**:
- `send_qbo_invoices/send_invoices/app.py` (no changes needed)
- `send_qbo_invoices/create_invoices/app.py` (no changes needed)
- `send_qbo_invoices/shared/process_and_send_qbo_invoices.py` (no changes needed)
- `send_qbo_invoices/shared/task_minutes_to_clickup_and_qbo.py` (no changes needed)

**Rationale**: The core logic already returns boolean success indicators. Lambda handlers are just thin wrappers. No refactoring needed - the entrypoint script will call the same functions directly.

#### 2.2 No Changes to AWS SDK Usage
**Files**: All `shared/*.py` files using boto3

**Rationale**: boto3 automatically uses AWS CLI credentials when running outside Lambda. The existing code pattern already has this:
```python
aws_region = os.environ.get("AWS_REGION", "us-west-2")
aws_secretsmanager = boto3.client("secretsmanager", region_name=aws_region)
aws_dynamodb = boto3.resource('dynamodb', region_name=aws_region)
```

This works identically in Docker when AWS credentials are mounted.

### Phase 3: Local Testing Setup

#### 3.1 Create Testing Documentation
**File**: `send_qbo_invoices/README.DOCKER.md`

Include step-by-step instructions:

1. **Prerequisites**
   - Docker Desktop installed
   - AWS CLI configured (`aws configure`)
   - AWS credentials with permissions for Secrets Manager, DynamoDB

2. **Build the Image**
   ```bash
   cd send_qbo_invoices
   docker build -t qbo-invoice-processor .
   ```

3. **Configure Environment**
   ```bash
   cp .env.template .env
   # Edit .env and set AWS_PROFILE to your AWS CLI profile name
   ```

4. **Run Locally - Send Invoices**
   ```bash
   docker-compose run --rm invoice-processor --send-invoices
   ```

5. **Run Locally - Create Invoices**
   ```bash
   docker-compose run --rm invoice-processor --create-invoices
   ```

6. **Alternative: Direct Docker Run (without compose)**
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

7. **Troubleshooting**
   - Check AWS credentials: `docker run --rm -v ~/.aws:/root/.aws:ro amazon/aws-cli sts get-caller-identity`
   - Check container logs: Add `-it` flag to docker run
   - Verify environment variables are set correctly

### Phase 4: Future ECS Fargate Deployment (Documentation Only)

#### 4.1 Create ECS Deployment Guide
**File**: `send_qbo_invoices/README.ECS-DEPLOYMENT.md`

Document steps for future deployment:

1. **Push Image to ECR**
   ```bash
   aws ecr create-repository --repository-name qbo-invoice-processor
   docker tag qbo-invoice-processor:latest {account}.dkr.ecr.{region}.amazonaws.com/qbo-invoice-processor:latest
   aws ecr get-login-password | docker login --username AWS --password-stdin {account}.dkr.ecr.{region}.amazonaws.com
   docker push {account}.dkr.ecr.{region}.amazonaws.com/qbo-invoice-processor:latest
   ```

2. **Create ECS Task Definition**
   - Use Fargate launch type
   - Set appropriate CPU/Memory (2 vCPU, 4GB recommended for 2-hour runs)
   - Configure environment variables
   - Set task execution role with permissions for ECR, Secrets Manager, DynamoDB
   - Configure CloudWatch Logs for monitoring

3. **Create EventBridge Scheduled Rules**
   - **Send Invoices**: Daily at 5 AM Pacific (cron: `0 12 * * ? *`)
   - **Create Invoices**: Monthly on 4th at 9 AM Pacific (cron: `0 17 4 * ? *`)
   - Each rule triggers ECS RunTask with appropriate command override

4. **IAM Roles Required**
   - **Task Execution Role**: Pull images from ECR, write CloudWatch logs
   - **Task Role**: Access Secrets Manager, DynamoDB (same permissions as current Lambda)

5. **Monitoring**
   - CloudWatch Logs for application output
   - CloudWatch Alarms for task failures
   - ECS service metrics for resource utilization

## Critical Files to Create/Modify

### New Files
1. `send_qbo_invoices/Dockerfile` - Container definition
2. `send_qbo_invoices/entrypoint.py` - Application entrypoint with CLI args
3. `send_qbo_invoices/docker-compose.yml` - Local development orchestration
4. `send_qbo_invoices/.env.template` - Environment variable template
5. `send_qbo_invoices/README.DOCKER.md` - Local Docker usage instructions
6. `send_qbo_invoices/README.ECS-DEPLOYMENT.md` - Future ECS deployment guide

### Modified Files
1. `send_qbo_invoices/.gitignore` - Add `.env` exclusion
2. `send_qbo_invoices/requirements.txt` - May need to remove Lambda-specific stubs

### No Changes Needed
- All `shared/*.py` files (boto3 code works as-is)
- `send_invoices/app.py` (keep for reference, not used by Docker)
- `create_invoices/app.py` (keep for reference, not used by Docker)
- `template.yaml` (keep for reference, may decommission Lambda later)

## Key Advantages of This Approach

1. **Minimal Code Changes**: Core business logic unchanged
2. **AWS Credential Simplicity**: Leverages existing AWS CLI setup
3. **Local Testing**: Full AWS access without Lambda deployment
4. **No Timeout Limits**: Can run for hours without restrictions
5. **Easy Transition to ECS**: Same container works locally and in Fargate
6. **Backward Compatible**: Can keep Lambda functions running during transition
7. **Better Logging**: Direct stdout/stderr vs CloudWatch parsing

## Potential Issues & Mitigations

### Issue 1: AWS Credential Expiration
- **Problem**: If using SSO/temporary credentials, they expire during long runs
- **Mitigation**: Use long-lived IAM user credentials for batch jobs, or implement credential refresh in code

### Issue 2: Network Reliability
- **Problem**: 2-hour runs vulnerable to network interruptions
- **Mitigation**: Add retry logic at client-level iteration (already partially exists), implement checkpointing to resume from failure

### Issue 3: Resource Limits on Local Machine
- **Problem**: Docker Desktop memory limits may impact processing
- **Mitigation**: Increase Docker Desktop memory allocation (Recommended: 4GB+), or test smaller client ranges initially

### Issue 4: DynamoDB Permissions
- **Problem**: Current template doesn't explicitly grant DynamoDB permissions
- **Mitigation**: Ensure AWS profile has DynamoDB read permissions for `Robocorp_Client_Org_Workspace_IDs` table

## Testing Strategy

1. **Phase 1**: Build container and verify it starts
2. **Phase 2**: Test with single client (modify `LOWER_CLIENT_ID` and `UPPER_CLIENT_ID` in code temporarily)
3. **Phase 3**: Run full `--create-invoices` with all clients
4. **Phase 4**: Test `--send-invoices` function
5. **Phase 5**: Monitor AWS costs during testing (Secrets Manager, DynamoDB calls)

## Estimated Timeline
- **Container Setup**: 1-2 hours
- **Local Testing**: 2-3 hours
- **Documentation**: 1 hour
- **Total**: 4-6 hours for complete local Docker setup

ECS deployment can be done later after local testing is successful.

---

## REVIEW NOTES (Added by Review Claude - 2025-12-27)

### ✅ VALIDATED ITEMS

1. **CodeUri and Module Structure**: Confirmed that `template.yaml` uses `CodeUri: .` (root directory), so all shared modules are already accessible. The entrypoint script can import from `shared/` without issues.

2. **Lambda Handler Functions**: Verified both Lambda handlers are thin wrappers:
   - `send_invoices/app.py` calls `shared.process_and_send_qbo_invoices.send_qbo_invoices()`
   - `create_invoices/app.py` calls `shared.task_minutes_to_clickup_and_qbo.process_all_clients()`
   - Both return boolean success indicators - perfect for direct Docker usage

3. **Import Pattern Validation**: Confirmed that shared modules use relative imports within the `shared/` directory:
   - `import apd_quickbooksonline as quickbooks_online`
   - `import apd_msgraph_v2 as msgraph`
   - `import apd_common`
   - `import apd_clickup as clickup`

   These imports work because Lambda handlers use `sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))`. Docker entrypoint will need similar path setup OR use proper Python package imports.

4. **Environment Variables**: All required env vars from `template.yaml` are correctly listed in plan (QBO_SECRET_NAME, MSGRAPH_SECRET_NAME, CLICKUP_SECRET_NAME, ROBOCORP_API_SECRET_NAME, DYNAMODB_TABLE_ROBOCORP_CLIENTS, BOOKKEEPER_EMAIL, EXCLUDED_CUSTOMERS, SENDER_EMAIL, MS_GRAPH_HOSTNAME).

5. **Boto3 Credential Handling**: Confirmed the code pattern already supports AWS CLI credentials:
   ```python
   aws_region = os.environ.get("AWS_REGION", "us-west-2")
   aws_secretsmanager = boto3.client("secretsmanager", region_name=aws_region)
   aws_dynamodb = boto3.resource('dynamodb', region_name=aws_region)
   ```
   No code changes needed - boto3 will automatically use mounted credentials.

6. **Assets Directory Structure**: Verified that `assets/sent_invoices_email_template.html` exists and is referenced correctly in the code using relative path from shared module.

7. **.gitignore Already Has .env**: Confirmed line 190 of `.gitignore` already excludes `.env` files, so no modification needed.

### ⚠️ CRITICAL ISSUES FOUND

1. **MISSING DYNAMODB PERMISSIONS IN LAMBDA IAM POLICY**

   **Problem**: The `template.yaml` Lambda function policies only grant Secrets Manager permissions. However, `task_minutes_to_clickup_and_qbo.py` (CreateInvoicesFunction) uses DynamoDB:
   ```python
   aws_dynamodb = boto3.resource('dynamodb', region_name=aws_region)
   client_orgs_table = apd_common.get_dynamodb_table("DYNAMODB_TABLE_ROBOCORP_CLIENTS", aws_dynamodb)
   ```

   **Current Template Policies** (lines 36-44, 69-75):
   ```yaml
   Policies:
     - Statement:
         - Effect: Allow
           Action:
             - secretsmanager:GetSecretValue
             - secretsmanager:UpdateSecret
           Resource:
             - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:10000/QBO*"
             - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:10000/MsGraph*"
   ```

   **Impact on Docker Migration**: The plan correctly identifies this in Issue 4 (line 229), but it's buried in "Potential Issues" instead of being a critical blocker. The AWS profile used for Docker must have DynamoDB read permissions for the `Robocorp_Client_Org_Workspace_IDs` table.

   **Recommendation**:
   - Update plan to emphasize that AWS credentials MUST have DynamoDB permissions
   - Add DynamoDB policy example to documentation
   - Consider if ClickUp secret access is also needed (CLICKUP_SECRET_NAME is in env vars but no IAM permissions granted)

2. **SECRETS MANAGER PERMISSIONS SCOPE**

   **Problem**: The Lambda policies use wildcard patterns `10000/QBO*` and `10000/MsGraph*`, but the actual secret names are:
   - `QBO/10000` (not `10000/QBO`)
   - `MsGraph/10000` (not `10000/MsGraph`)
   - `ClickUp/10000` (not in IAM policy at all)
   - `RoboCorp/10000/ClientAPIKeys` (not in IAM policy at all)

   **Current Template** (line 43-44):
   ```yaml
   Resource:
     - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:10000/QBO*"
     - !Sub "arn:aws:secretsmanager:${AWS::Region}:${AWS::AccountId}:secret:10000/MsGraph*"
   ```

   **Actual Env Vars** (lines 18-21):
   ```yaml
   QBO_SECRET_NAME: QBO/10000
   MSGRAPH_SECRET_NAME: MsGraph/10000
   CLICKUP_SECRET_NAME: ClickUp/10000
   ROBOCORP_API_SECRET_NAME: RoboCorp/10000/ClientAPIKeys
   ```

   **Impact**: The IAM policy pattern doesn't match the actual secret paths. This might be working due to AWS Secrets Manager appending random suffixes to secret ARNs (e.g., `QBO/10000-AbCdEf`), making the wildcard match.

   **For Docker**: AWS credentials must have access to ALL four secrets. Update plan documentation to include correct secret ARN patterns.

3. **PYTHON PATH SETUP IN DOCKERFILE**

   **Problem**: The plan mentions copying `shared/` directory but doesn't address how Python will find these modules. Current Lambda handlers use:
   ```python
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
   ```

   **Solution Needed**: The Dockerfile and entrypoint.py need one of these approaches:

   **Option A** - Add shared/ to PYTHONPATH in Dockerfile:
   ```dockerfile
   ENV PYTHONPATH="/app/shared:${PYTHONPATH}"
   ```

   **Option B** - Use sys.path.insert in entrypoint.py:
   ```python
   import sys
   import os
   sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'shared'))
   ```

   **Option C** - Make shared a proper package and install it:
   ```dockerfile
   COPY shared/ /app/shared/
   RUN pip install -e /app/shared
   ```

   **Recommendation**: Option A (PYTHONPATH) is simplest and most Docker-idiomatic.

### 📝 RECOMMENDED PLAN UPDATES

1. **Section 1.1 - Dockerfile Updates**

   Add after line 24:
   ```
   - Set PYTHONPATH environment variable: `ENV PYTHONPATH="/app/shared:${PYTHONPATH}"`
   - Ensure working directory is set to `/app`
   ```

2. **Section 1.3 - docker-compose.yml Updates**

   Add after line 52:
   ```yaml
   - AWS_PROFILE=${AWS_PROFILE:-default}
   ```

   Note: The plan should clarify that `.env` file is optional if using default AWS profile.

3. **Section 3.1 - Testing Documentation Updates**

   Add new subsection after Prerequisites (line 101):
   ```markdown
   **AWS Permissions Required**:
   - Secrets Manager: Read/Update access to:
     - `QBO/10000*`
     - `MsGraph/10000*`
     - `ClickUp/10000*`
     - `RoboCorp/10000/ClientAPIKeys*`
   - DynamoDB: Read access to table `Robocorp_Client_Org_Workspace_IDs`

   Verify permissions:
   ```bash
   aws secretsmanager get-secret-value --secret-id QBO/10000
   aws dynamodb describe-table --table-name Robocorp_Client_Org_Workspace_IDs
   ```
   ```

4. **Section 1.5 - .gitignore Updates**

   Update lines 61-65:
   ```
   #### 1.5 Update .gitignore
   **File**: `send_qbo_invoices/.gitignore`

   - .env already excluded (line 190)
   - No changes needed
   ```

### 🔍 ADDITIONAL OBSERVATIONS

1. **Requirements.txt Dependencies**: The file includes boto3 stubs (`boto3-stubs`, `mypy-boto3-dynamodb`, `mypy-boto3-secretsmanager`) which are development dependencies. These can be removed from the Docker image to reduce size, or kept if type checking is desired in the container.

2. **Lambda Timeout**: Current timeout is 120 seconds (2 minutes) per `template.yaml` line 12. The plan mentions 2+ hour runs are needed - this confirms the Lambda timeout is indeed the blocker.

3. **Assets Path Reference**: The code uses `os.path.join(os.path.dirname(__file__), '..', 'assets', 'sent_invoices_email_template.html')` from shared modules. In Docker, ensure assets directory is copied and accessible from the working directory structure.

4. **Excluded Customers Format**: Environment variable uses comma-separated format, but template.yaml shows single value `"10001 - AICPA"`. Verify if multiple exclusions are needed and document the format clearly.

### ✅ CONCLUSION

The migration plan is fundamentally sound and well-structured. The main issues are:

1. **CRITICAL**: Add DynamoDB permissions documentation (already partially addressed in Issue 4)
2. **CRITICAL**: Document all four Secrets Manager secret access requirements
3. **IMPORTANT**: Specify Python path configuration in Dockerfile (PYTHONPATH env var)
4. **MINOR**: Clarify .gitignore already has .env excluded

With these updates, the plan will be complete and ready for implementation.
