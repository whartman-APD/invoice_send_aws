# Create ECR repository
resource "aws_ecr_repository" "invoice_send" {
  name                 = var.repository_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = var.enable_image_scanning
  }

  encryption_configuration {
    encryption_type = "AES256"
  }

  tags = {
    Name        = var.repository_name
    ManagedBy   = "Terraform"
    Project     = "InvoiceSendQBO"
  }
}

# Lifecycle policy to retain only N images
resource "aws_ecr_lifecycle_policy" "invoice_send_policy" {
  repository = aws_ecr_repository.invoice_send.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus     = "any"
          countType     = "imageCountMoreThan"
          countNumber   = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# Build and push Docker image
resource "docker_image" "invoice_send" {
  name = "${aws_ecr_repository.invoice_send.repository_url}:${var.image_tag}"

  build {
    context    = var.docker_context_path
    dockerfile = "Dockerfile"
    platform   = "linux/amd64"
  }

  triggers = {
    # Rebuild when Dockerfile or source code changes
    dockerfile_hash = filemd5("${var.docker_context_path}/Dockerfile")
    requirements_hash = filemd5("${var.docker_context_path}/requirements.txt")
    entrypoint_hash = filemd5("${var.docker_context_path}/entrypoint.py")
    # Add hash of shared directory to trigger rebuilds on code changes
    shared_dir_hash = sha256(join("", [
      for f in fileset("${var.docker_context_path}/shared", "**/*.py") :
      filemd5("${var.docker_context_path}/shared/${f}")
    ]))
  }
}

# Push image to ECR
resource "docker_registry_image" "invoice_send" {
  name = docker_image.invoice_send.name

  keep_remotely = true # Keep image in registry when destroying Terraform resources
}
