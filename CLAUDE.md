# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS SAM Lambda application that automatically sends QuickBooks Online invoices to clients and emails a summary to the bookkeeper via Microsoft Graph.

## Common Commands

All commands run from `send_qbo_invoices/` directory:

```bash
# Build
sam build --use-container

# Deploy (first time)
sam deploy --guided

# Deploy (subsequent)
sam deploy

# Local invoke
sam local invoke HelloWorldFunction --event events/event.json

# Local API
sam local start-api
curl http://localhost:3000/hello

# View logs
sam logs -n HelloWorldFunction --stack-name "send_qbo_invoices" --tail

# Delete stack
sam delete --stack-name "send_qbo_invoices"
```

### Testing

```bash
# Install test dependencies
pip install -r tests/requirements.txt

# Run unit tests
python -m pytest tests/unit -v

# Run single test file
python -m pytest tests/unit/test_handler.py -v

# Integration tests (requires deployed stack)
AWS_SAM_STACK_NAME="send_qbo_invoices" python -m pytest tests/integration -v
```

## Architecture

### Entry Flow
`API Gateway → app.lambda_handler → send_qbo_invoices()`

### Core Modules (in `hello_world/`)

- **app.py** - Lambda handler entry point
- **send_qbo_invoices.py** - Main orchestration: queries QBO for today's invoices, sends them, generates summary email
- **apd_quickbooksonline.py** - QuickBooks Online API wrapper with OAuth token refresh, retry logic, and custom exceptions (QBOError, QBOAuthError, etc.)
- **apd_msgraph_v2.py** - Microsoft Graph API wrapper for sending emails via Office 365
- **apd_common.py** - HTML template processor (`APD_Html_Template` class)

### External Dependencies

- **AWS Secrets Manager** - Stores credentials at paths defined by `QBO_SECRET_NAME` and `MSGRAPH_SECRET_NAME` environment variables
- **QuickBooks Online API** - Invoice queries and sending
- **Microsoft Graph API** - Email delivery

### Configuration

Environment variables in `template.yaml`:
- `QBO_SECRET_NAME`: AWS Secrets Manager path for QBO credentials (client_id, client_secret, realm_id, refresh_token)
- `MSGRAPH_SECRET_NAME`: AWS Secrets Manager path for Microsoft Graph credentials (tenant, client_id, client_secret, username)
