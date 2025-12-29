# QuickBooks Online Invoice Automation

Docker-based application for automating QuickBooks Online invoice operations.

## Overview

This application provides two main functions:
- **Send Invoices** - Queries QBO for today's invoices, sends them to clients, and emails a summary to the bookkeeper
- **Create Invoices** - Creates monthly invoices from recurring transactions (ClickUp task minutes)

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- AWS credentials (for Secrets Manager access)
- QuickBooks Online API credentials
- Microsoft Graph API credentials (for email)
- ClickUp API credentials (for create-invoices function)

### Setup

1. **Configure environment variables**

```bash
# Copy the template
cp .env.template .env

# Edit .env with your credentials
# At minimum, set:
# - AWS_REGION
# - QBO_SECRET_NAME
# - MSGRAPH_SECRET_NAME
# - BOOKKEEPER_EMAIL
# - SENDER_EMAIL
```

2. **Build the Docker image**

```bash
docker-compose build
```

3. **Run a function**

```bash
# Send today's invoices
docker-compose run --rm send-invoices

# Create invoices from ClickUp task minutes
docker-compose run --rm create-invoices
```

## Project Structure

```
send_qbo_invoices/
├── Dockerfile                 # Docker container definition
├── docker-compose.yml         # Docker Compose services
├── entrypoint.py             # Main entry point
├── requirements.txt          # Python dependencies
├── .env.template            # Environment variable template
├── shared/                  # Shared modules
│   ├── process_and_send_qbo_invoices.py
│   ├── task_minutes_to_clickup_and_qbo.py
│   ├── apd_quickbooksonline.py
│   ├── apd_msgraph_v2.py
│   └── apd_common.py
└── assets/
    └── sent_invoices_email_template.html
```

## Usage

### Send Invoices

Queries QuickBooks Online for all invoices created today, sends them to customers via email, and sends a summary report to the bookkeeper.

```bash
docker-compose run --rm send-invoices
```

### Create Invoices

Creates invoices from ClickUp task minutes for the current billing period.

```bash
docker-compose run --rm create-invoices
```

### Local Development

For development without Docker:

```bash
# Install dependencies
pip install -r requirements.txt

# Run functions directly
python entrypoint.py send-invoices
python entrypoint.py create-invoices
```

## Configuration

Environment variables are configured in the `.env` file:

### Required Variables

- `AWS_REGION` - AWS region for Secrets Manager (default: us-west-2)
- `QBO_SECRET_NAME` - AWS Secrets Manager path for QBO credentials
- `MSGRAPH_SECRET_NAME` - AWS Secrets Manager path for Microsoft Graph credentials
- `BOOKKEEPER_EMAIL` - Email address for summary reports
- `SENDER_EMAIL` - Email address used as sender

### Optional Variables

- `EXCLUDED_CUSTOMERS` - Comma-separated list of customer names to exclude from invoice sending
- `LOG_LEVEL` - Logging level (default: INFO)

## AWS Secrets Manager

Credentials are stored in AWS Secrets Manager with the following structure:

### QBO Secret
```json
{
  "client_id": "...",
  "client_secret": "...",
  "realm_id": "...",
  "refresh_token": "...",
  "access_token": "..."
}
```

### Microsoft Graph Secret
```json
{
  "tenant_id": "...",
  "client_id": "...",
  "client_secret_value": "...",
  "sharepoint_hostname": "..."
}
```

## Making Code Changes

After modifying Python code:

```bash
# Rebuild the Docker image
docker-compose build

# Run the updated function
docker-compose run --rm send-invoices
```

## Logs

Logs are written to:
- Console (stdout/stderr)
- `logs/` directory (if configured)

View Docker logs:
```bash
docker-compose logs
```

## Deployment

For production deployment to AWS ECS, see [README.ECS-DEPLOYMENT.md](README.ECS-DEPLOYMENT.md)

## Architecture

### Core Modules

- **process_and_send_qbo_invoices.py** - Orchestrates querying and sending invoices
- **task_minutes_to_clickup_and_qbo.py** - Creates invoices from ClickUp task minutes
- **apd_quickbooksonline.py** - QBO API wrapper with OAuth and retry logic
- **apd_msgraph_v2.py** - Microsoft Graph API wrapper for email
- **apd_common.py** - HTML template processor

### External Services

- **QuickBooks Online API** - Invoice queries and operations
- **Microsoft Graph API** - Email delivery
- **ClickUp API** - Task minutes data
- **AWS Secrets Manager** - Credential storage

## Troubleshooting

### Docker Issues

```bash
# Clean up containers and images
docker-compose down
docker system prune -a

# Rebuild from scratch
docker-compose build --no-cache
```

### Credential Issues

Verify your `.env` file has all required variables and that AWS credentials have access to Secrets Manager.

### Log Files

Check the `logs/` directory for detailed execution logs.

## Additional Documentation

- [README.DOCKER.md](README.DOCKER.md) - Detailed Docker setup and usage
- [README.ECS-DEPLOYMENT.md](README.ECS-DEPLOYMENT.md) - AWS ECS deployment guide
- [QUICK-START.md](QUICK-START.md) - Quick start guide
