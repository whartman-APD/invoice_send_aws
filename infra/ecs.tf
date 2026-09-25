resource "aws_ecs_cluster" "main" {
  name = "${var.repository_name}-cluster"
}

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.repository_name}"
  retention_in_days = var.log_retention_days
}

locals {
  container_name = "invoice-processor"

  # Mirrors docker-compose.yml, minus AWS keys (the task role replaces them)
  app_environment = merge(
    var.secret_names,
    {
      AWS_REGION                      = var.aws_region
      DYNAMODB_TABLE_ROBOCORP_CLIENTS = var.dynamodb_table_robocorp_clients
      BOOKKEEPER_EMAIL                = var.bookkeeper_email
      SENDER_EMAIL                    = var.sender_email
      MONTHLY_DIGEST_EMAIL_FROM       = var.digest_email_from
      MONTHLY_DIGEST_EMAIL_TO         = var.digest_email_to
      CLICKUP_DIGEST_WORKSPACE_ID     = var.clickup_digest.workspace_id
      CLICKUP_DIGEST_DOC_ID           = var.clickup_digest.doc_id
      CLICKUP_DIGEST_PAGE_ID          = var.clickup_digest.page_id
      MS_GRAPH_HOSTNAME               = var.ms_graph_hostname
      CREATE_INVOICE                  = tostring(var.create_invoice)
      UPDATE_CLICKUP                  = tostring(var.update_clickup)
      UPLOAD_TO_SHAREPOINT            = tostring(var.upload_to_sharepoint)
      LOWER_CLIENT_ID                 = tostring(var.lower_client_id)
      UPPER_CLIENT_ID                 = tostring(var.upper_client_id)
      NET_30_DAYS_CLIENTS             = var.net_30_days_clients
    }
  )
}

# One task definition; the schedule (or a manual run) picks the job with a command override
resource "aws_ecs_task_definition" "app" {
  family                   = var.repository_name
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }

  container_definitions = jsonencode([{
    name      = local.container_name
    image     = local.image_uri
    essential = true
    command   = ["--github-digest"]

    environment = [for k, v in local.app_environment : { name = k, value = v }]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "job"
      }
    }
  }])
}
