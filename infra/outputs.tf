output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.invoice_send.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.invoice_send.arn
}

output "docker_image_uri" {
  description = "Full URI of the pushed Docker image"
  value       = "${aws_ecr_repository.invoice_send.repository_url}:${var.image_tag}"
}

output "aws_account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region"
  value       = data.aws_region.current.name
}
