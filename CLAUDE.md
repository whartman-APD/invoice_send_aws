# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AWS SAM Lambda application with two functions for QuickBooks Online invoice automation:
1. **SendInvoicesFunction** - Sends today's invoices to clients daily and emails summary to bookkeeper
2. **CreateInvoicesFunction** - Creates monthly invoices from recurring transactions (implementation pending)

## Common Commands

All commands run from `send_qbo_invoices/` directory:

```bash
# Build both Lambda functions
sam build --use-container

# Deploy (first time)
sam deploy --guided

# Deploy (subsequent)
sam deploy

# Local invoke - Send Invoices Function
sam local invoke SendInvoicesFunction --event events/event.json

# Local invoke - Create Invoices Function
sam local invoke CreateInvoicesFunction --event events/event.json

# Local API
sam local start-api
# Then test endpoints:
curl -X POST http://localhost:3000/send-invoices
curl -X POST http://localhost:3000/create-invoices

# View logs for Send Invoices
sam logs -n SendInvoicesFunction --stack-name "send_qbo_invoices" --tail

# View logs for Create Invoices
sam logs -n CreateInvoicesFunction --stack-name "send_qbo_invoices" --tail

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

## Project Structure

```
send_qbo_invoices/
├── template.yaml              # SAM template defining both Lambda functions
├── requirements.txt           # Python dependencies
├── send_invoices/            # Lambda 1: Daily invoice sending
│   └── app.py                # Handler: send_invoices.app.lambda_handler
├── create_invoices/          # Lambda 2: Monthly invoice creation
│   └── app.py                # Handler: create_invoices.app.lambda_handler
├── shared/                   # Shared modules used by both functions
│   ├── process_and_send_qbo_invoices.py  # Main orchestration logic
│   ├── apd_quickbooksonline.py           # QBO API wrapper
│   ├── apd_msgraph_v2.py                 # Microsoft Graph API wrapper
│   └── apd_common.py                     # HTML template processor
└── assets/                   # Shared assets
    └── sent_invoices_email_template.html
```

## Architecture

### Lambda Functions

#### SendInvoicesFunction
- **Trigger**: Daily at 5 PM Pacific (EventBridge Schedule) + API Gateway
- **Handler**: `send_invoices.app.lambda_handler`
- **Purpose**: Queries QBO for today's invoices, sends them, emails summary to bookkeeper

#### CreateInvoicesFunction
- **Trigger**: Monthly on 8th at 9 AM Pacific (EventBridge Schedule) + API Gateway
- **Handler**: `create_invoices.app.lambda_handler`
- **Purpose**: Creates invoices from recurring transactions (implementation pending)

### Core Modules (in `shared/`)

- **process_and_send_qbo_invoices.py** - Main orchestration: queries QBO for today's invoices, sends them, generates summary email
- **apd_quickbooksonline.py** - QuickBooks Online API wrapper with OAuth token refresh, retry logic, and custom exceptions (QBOError, QBOAuthError, etc.)
- **apd_msgraph_v2.py** - Microsoft Graph API wrapper for sending emails via Office 365
- **apd_common.py** - HTML template processor (`APD_Html_Template` class)

### External Dependencies

- **AWS Secrets Manager** - Stores credentials at paths defined by `QBO_SECRET_NAME` and `MSGRAPH_SECRET_NAME` environment variables
  - QBO credentials are automatically updated when refresh tokens are rotated
- **QuickBooks Online API** - Invoice queries and sending
- **Microsoft Graph API** - Email delivery

### Configuration

Environment variables in `template.yaml`:
- `QBO_SECRET_NAME`: AWS Secrets Manager path for QBO credentials (client_id, client_secret, realm_id, refresh_token, access_token)
- `MSGRAPH_SECRET_NAME`: AWS Secrets Manager path for Microsoft Graph credentials (tenant_id, client_id, client_secret_value, sharepoint_hostname)

## Important Notes

- Both functions use `CodeUri: .` (root directory) with shared modules
- Scheduled triggers are disabled by default (`Enabled: false`)
- Manual triggering available via API Gateway endpoints
- QBO refresh tokens are automatically saved back to Secrets Manager after rotation
