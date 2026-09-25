resource "aws_scheduler_schedule_group" "main" {
  name = var.repository_name
}

locals {
  public_network = {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.task.id]
    assign_public_ip = true
  }
  sync_network = {
    subnets          = var.sync_subnet_ids
    security_groups  = [aws_security_group.sync.id]
    assign_public_ip = false
  }

  jobs = {
    github-digest = {
      command    = "--github-digest"
      expression = var.github_digest_schedule
      enabled    = var.github_digest_schedule_enabled
      network    = local.public_network
    }
    create-invoices = {
      command    = "--create-invoices"
      expression = var.create_invoices_schedule
      enabled    = var.create_invoices_schedule_enabled
      network    = local.public_network
    }
    sync-processes = {
      command    = "--sync-processes"
      expression = var.sync_processes_schedule
      enabled    = var.sync_processes_schedule_enabled
      network    = local.sync_network
    }
  }
}

resource "aws_scheduler_schedule" "job" {
  for_each = local.jobs

  name                         = each.key
  group_name                   = aws_scheduler_schedule_group.main.name
  schedule_expression          = each.value.expression
  schedule_expression_timezone = var.schedule_timezone
  state                        = each.value.enabled ? "ENABLED" : "DISABLED"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_ecs_cluster.main.arn
    role_arn = aws_iam_role.scheduler.arn

    ecs_parameters {
      # Unversioned ARN = always run the latest revision
      task_definition_arn = aws_ecs_task_definition.app.arn_without_revision
      launch_type         = "FARGATE"

      network_configuration {
        subnets          = each.value.network.subnets
        security_groups  = each.value.network.security_groups
        assign_public_ip = each.value.network.assign_public_ip
      }
    }

    input = jsonencode({
      containerOverrides = [{
        name    = local.container_name
        command = [each.value.command]
      }]
    })

    # Never retry: a retried create-invoices run would create duplicate invoices
    retry_policy {
      maximum_retry_attempts = 0
    }
  }
}
