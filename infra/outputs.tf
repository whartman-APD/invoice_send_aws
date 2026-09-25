output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.invoice_send.repository_url
}

output "image_tag" {
  description = "Image tag the task definition expects (deploy.ps1 builds and pushes it)"
  value       = local.image_tag
}

output "docker_image_uri" {
  description = "Full URI of the image the task definition runs"
  value       = local.image_uri
}

output "aws_account_id" {
  description = "AWS Account ID"
  value       = data.aws_caller_identity.current.account_id
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}

output "log_group_name" {
  value = aws_cloudwatch_log_group.app.name
}

# Values used by ../run-aws-task.ps1
output "run_task_config" {
  description = "Settings for starting a task by hand"
  value = {
    region              = var.aws_region
    cluster             = aws_ecs_cluster.main.name
    task_definition     = aws_ecs_task_definition.app.family
    container_name      = local.container_name
    subnets             = aws_subnet.public[*].id
    security_group      = aws_security_group.task.id
    sync_subnets        = var.sync_subnet_ids
    sync_security_group = aws_security_group.sync.id
    log_group           = aws_cloudwatch_log_group.app.name
  }
}
