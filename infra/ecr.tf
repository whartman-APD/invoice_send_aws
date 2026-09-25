locals {
  # Hash of everything that goes into the image. Used as the image tag so every code change
  # produces a new tag, a new task definition revision, and an easy rollback target.
  source_files = concat(
    ["Dockerfile", "requirements.txt", "entrypoint.py"],
    [for f in fileset("${var.docker_context_path}/shared", "**/*.py") : "shared/${f}"],
    [for f in fileset("${var.docker_context_path}/assets", "**") : "assets/${f}"],
  )
  source_hash = sha256(join("", [
    for f in local.source_files : filemd5("${var.docker_context_path}/${f}")
  ]))
  image_tag = var.image_tag != "" ? var.image_tag : substr(local.source_hash, 0, 12)

  # Built and pushed by ../deploy.ps1 (ECS only pulls it when a task starts)
  image_uri = "${aws_ecr_repository.invoice_send.repository_url}:${local.image_tag}"
}

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
    Name      = var.repository_name
    ManagedBy = "Terraform"
    Project   = "InvoiceSendQBO"
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
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}
