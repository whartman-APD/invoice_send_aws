# Quick Start Guide - Docker is Ready! ✅

## Build Status: SUCCESS ✅

Your Docker image has been successfully built and tested!

```
IMAGE NAME              TAG       IMAGE ID       SIZE
qbo-invoice-processor   latest    6c223e2359c1   560MB
```

## Next Steps

### 1. Verify AWS Credentials

Before running the container, ensure your AWS credentials are configured:

```bash
# Test AWS CLI access
aws sts get-caller-identity

# Test Secrets Manager access
aws secretsmanager get-secret-value --secret-id QBO/10000

# Test DynamoDB access
aws dynamodb describe-table --table-name Robocorp_Client_Org_Workspace_IDs
```

If any of these fail, see **[README.DOCKER.md](README.DOCKER.md)** section "AWS Permissions Required".

---

### 2. Run Your First Test (Recommended: Single Client)

Before processing all clients, test with one client to verify everything works:

**Option A: Edit the limits temporarily**

1. Open `send_qbo_invoices/shared/task_minutes_to_clickup_and_qbo.py`
2. Find lines 30-31 and change to:
   ```python
   LOWER_CLIENT_ID = 10001  # Start with a single test client
   UPPER_CLIENT_ID = 10002  # Process only one client
   ```
3. Rebuild: `docker build -t qbo-invoice-processor .`
4. Run: `docker-compose run --rm invoice-processor --create-invoices`
5. After successful test, restore original values and rebuild

**Option B: Run with full client range**

If you're confident in your setup:
```bash
docker-compose run --rm invoice-processor --create-invoices
```

---

### 3. Run Send Invoices Function

Once create-invoices works successfully:

```bash
docker-compose run --rm invoice-processor --send-invoices
```

This sends today's QuickBooks invoices to clients and emails a summary to the bookkeeper.

---

## Common Commands

### Build Image
```bash
cd send_qbo_invoices
docker build -t qbo-invoice-processor .
```

### Run - Create Monthly Invoices
```bash
docker-compose run --rm invoice-processor --create-invoices
```

### Run - Send Today's Invoices
```bash
docker-compose run --rm invoice-processor --send-invoices
```

### View Help
```bash
docker run --rm qbo-invoice-processor --help
```

### Check Image Details
```bash
docker images qbo-invoice-processor
```

---

## Expected Output

When you run the container, you should see:

```
============================================================
Starting: Create Monthly Invoices from Usage Data
============================================================
INFO: Starting task minutes to ClickUp and QBO process...
INFO: Processing client number: 10001
INFO: Total runtime for 10001 for prior month: XXX minutes
...
============================================================
COMPLETED SUCCESSFULLY
============================================================
```

Logs stream directly to your terminal in real-time!

---

## Troubleshooting

### AWS Credentials Not Found
```
Error: botocore.exceptions.NoCredentialsError
```
**Solution**: Verify `~/.aws/credentials` exists and contains valid credentials

### Secrets Manager Access Denied
```
Error: AccessDeniedException when calling GetSecretValue
```
**Solution**: Your AWS profile needs Secrets Manager permissions (see README.DOCKER.md)

### DynamoDB Access Denied
```
Error: ResourceNotFoundException or AccessDeniedException
```
**Solution**: Your AWS profile needs DynamoDB read permissions (see README.DOCKER.md)

### Module Not Found
```
Error: ModuleNotFoundError: No module named 'apd_quickbooksonline'
```
**Solution**: Rebuild the image - PYTHONPATH may not be set correctly

---

## Full Documentation

- **[README.DOCKER.md](README.DOCKER.md)** - Complete local setup guide with troubleshooting
- **[README.ECS-DEPLOYMENT.md](README.ECS-DEPLOYMENT.md)** - Deploy to AWS ECS Fargate (future)
- **[.env.template](.env.template)** - Environment variable reference

---

## Success Criteria

Before considering the migration complete:

- [x] Docker image builds successfully ✅
- [x] Container starts and shows help message ✅
- [ ] Single client test completes without errors
- [ ] Full client processing completes successfully
- [ ] Send invoices function works correctly
- [ ] All AWS API calls succeed (Secrets Manager, DynamoDB, QBO, etc.)

---

## Support

If you encounter issues:

1. Check [README.DOCKER.md](README.DOCKER.md) troubleshooting section (7 common issues)
2. Verify AWS permissions with the test commands in README.DOCKER.md
3. Run with `-it` flag to see detailed logs: `docker run -it ...`

---

**You're ready to test!** 🚀

Start with the single-client test, then proceed to full processing once that succeeds.
