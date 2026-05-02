# Infrastructure - Terraform for AWS ECR

This directory contains Terraform configuration to create an AWS ECR repository and automatically build and push the Docker container.

## Prerequisites

1. **AWS CLI** configured with credentials
   ```bash
   aws configure
   ```

2. **Terraform** installed (>= 1.0)
   ```bash
   terraform --version
   ```

3. **Docker** running locally
   ```bash
   docker --version
   ```

## Quick Start

### Initialize Terraform
```bash
cd infra
terraform init
```

### Preview Changes
```bash
terraform plan
```

### Apply Configuration (Create ECR and Push Image)
```bash
terraform apply
```

### Destroy Resources
```bash
terraform destroy
```

## Configuration

### Variables

You can customize the deployment by creating a `terraform.tfvars` file:

```hcl
aws_region             = "us-west-2"
repository_name        = "invoice-send-qbo"
image_tag              = "latest"
image_retention_count  = 10
enable_image_scanning  = true
docker_context_path    = "../send_qbo_invoices"
```

Or pass variables via command line:
```bash
terraform apply -var="aws_region=us-east-1" -var="image_tag=v1.0.0"
```

### Environment Variables

Alternatively, use environment variables:
```bash
export TF_VAR_aws_region="us-west-2"
export TF_VAR_image_tag="v1.0.0"
terraform apply
```

## Files

- **main.tf** - Provider configuration and AWS data sources
- **variables.tf** - Input variable definitions
- **ecr.tf** - ECR repository, lifecycle policy, and Docker image build/push
- **outputs.tf** - Output values (repository URL, image URI, etc.)

## Features

### ECR Repository
- Mutable image tags (can update `latest` tag)
- AES256 encryption
- Automatic image scanning on push
- Lifecycle policy to retain only N images (default: 10)

### Docker Image Build
- Automatically builds Docker image from `../send_qbo_invoices/Dockerfile`
- Builds for `linux/amd64` platform (compatible with ECS/Fargate)
- Automatic rebuild triggers when files change:
  - Dockerfile
  - requirements.txt
  - entrypoint.py
  - Any Python files in `shared/` directory

### Outputs
After applying, Terraform outputs:
- ECR repository URL
- Full Docker image URI (for use in ECS task definitions)
- AWS account ID and region

## Usage Examples

### Deploy with specific tag
```bash
terraform apply -var="image_tag=v1.2.3"
```

### Use different AWS region
```bash
terraform apply -var="aws_region=us-east-1"
```

### Change retention policy
```bash
terraform apply -var="image_retention_count=20"
```

## Outputs

After successful apply, you'll see outputs like:
```
aws_account_id = "123456789012"
aws_region = "us-west-2"
docker_image_uri = "123456789012.dkr.ecr.us-west-2.amazonaws.com/invoice-send-qbo:latest"
ecr_repository_arn = "arn:aws:ecr:us-west-2:123456789012:repository/invoice-send-qbo"
ecr_repository_url = "123456789012.dkr.ecr.us-west-2.amazonaws.com/invoice-send-qbo"
```

Use the `docker_image_uri` output in your ECS task definitions or other AWS services.

## Manual Docker Operations

If you need to manually push images:

```bash
# Get ECR login command
aws ecr get-login-password --region us-west-2 | docker login --username AWS --password-stdin $(terraform output -raw ecr_repository_url)

# Build image
cd ../send_qbo_invoices
docker build -t invoice-send-qbo:latest .

# Tag image
docker tag invoice-send-qbo:latest $(cd ../infra && terraform output -raw docker_image_uri)

# Push image
docker push $(cd ../infra && terraform output -raw docker_image_uri)
```

## Troubleshooting

### Docker daemon not running
Ensure Docker Desktop (Windows) or Docker service (Linux) is running:
```bash
docker ps
```

### AWS credentials not configured
```bash
aws configure
# or
export AWS_ACCESS_KEY_ID="..."
export AWS_SECRET_ACCESS_KEY="..."
export AWS_REGION="us-west-2"
```

### Permission denied when accessing Docker
On Windows with Docker Desktop, ensure your user has permission to use Docker.

### Image build fails
Check the Docker build context path is correct and all required files exist:
```bash
ls -la ../send_qbo_invoices/
```

## Integration with ECS

After pushing your image to ECR, you can use it in ECS task definitions:

```json
{
  "containerDefinitions": [
    {
      "name": "invoice-send",
      "image": "<docker_image_uri from terraform output>",
      "essential": true,
      ...
    }
  ]
}
```

## Next Steps

After setting up ECR, consider:
1. Creating ECS cluster and task definitions
2. Setting up ECS Scheduled Tasks for automated runs
3. Configuring CloudWatch Logs for container logging
4. Adding IAM roles for ECS task execution and task roles

See the main project README for deployment instructions.
