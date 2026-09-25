data "aws_iam_policy_document" "ecs_tasks_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# ------------------------------------------------------------------------------
# Execution role: used by ECS itself to pull the image and write logs
# ------------------------------------------------------------------------------

resource "aws_iam_role" "task_execution" {
  name               = "${var.repository_name}-task-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy_attachment" "task_execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# ------------------------------------------------------------------------------
# Task role: what the Python code runs as (replaces the access key in .env)
# ------------------------------------------------------------------------------

locals {
  # Secrets Manager appends a random 6-character suffix to secret ARNs
  secret_arn_prefix = "arn:aws:secretsmanager:${var.aws_region}:${data.aws_caller_identity.current.account_id}:secret"
  secret_arns       = { for env, name in var.secret_names : env => "${local.secret_arn_prefix}:${name}-??????" }
}

data "aws_iam_policy_document" "task" {
  statement {
    sid       = "ReadAppSecrets"
    actions   = ["secretsmanager:GetSecretValue"]
    resources = values(local.secret_arns)
  }

  statement {
    sid       = "SaveRotatedQboTokens"
    actions   = ["secretsmanager:UpdateSecret"]
    resources = [local.secret_arns["QBO_SECRET_NAME"]]
  }

  statement {
    sid     = "ReadClientTable"
    actions = ["dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan", "dynamodb:DescribeTable"]
    resources = [
      "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.dynamodb_table_robocorp_clients}"
    ]
  }
}

resource "aws_iam_role" "task" {
  name               = "${var.repository_name}-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_tasks_assume.json
}

resource "aws_iam_role_policy" "task" {
  name   = "app-permissions"
  role   = aws_iam_role.task.id
  policy = data.aws_iam_policy_document.task.json
}

# ------------------------------------------------------------------------------
# Scheduler role: lets EventBridge Scheduler start the task
# ------------------------------------------------------------------------------

resource "aws_iam_role" "scheduler" {
  name = "${var.repository_name}-scheduler"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Action    = "sts:AssumeRole"
      Principal = { Service = "scheduler.amazonaws.com" }
      Condition = {
        StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
      }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler" {
  name = "run-task"
  role = aws_iam_role.scheduler.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "ecs:RunTask"
        Resource = "${aws_ecs_task_definition.app.arn_without_revision}:*"
        Condition = {
          ArnEquals = { "ecs:cluster" = aws_ecs_cluster.main.arn }
        }
      },
      {
        Effect   = "Allow"
        Action   = "iam:PassRole"
        Resource = [aws_iam_role.task_execution.arn, aws_iam_role.task.arn]
      },
    ]
  })
}
