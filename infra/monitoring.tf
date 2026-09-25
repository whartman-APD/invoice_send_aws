# Failure alerts by email. After the first apply, AWS emails var.alert_email a
# "Subscription Confirmation" link that must be clicked before alerts are delivered.

resource "aws_sns_topic" "alerts" {
  name = "${var.repository_name}-alerts"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

data "aws_iam_policy_document" "alerts_topic" {
  statement {
    sid       = "AllowEventBridge"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }

  statement {
    sid       = "AllowCloudWatchAlarms"
    actions   = ["sns:Publish"]
    resources = [aws_sns_topic.alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["cloudwatch.amazonaws.com"]
    }
  }
}

resource "aws_sns_topic_policy" "alerts" {
  arn    = aws_sns_topic.alerts.arn
  policy = data.aws_iam_policy_document.alerts_topic.json
}

# ------------------------------------------------------------------------------
# Alert 1: a job ran and exited non-zero, or the task never started (bad image, etc.)
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_event_rule" "task_failed" {
  name        = "${var.repository_name}-task-failed"
  description = "Invoice automation task stopped with an error"

  event_pattern = jsonencode({
    source        = ["aws.ecs"]
    "detail-type" = ["ECS Task State Change"]
    detail = {
      clusterArn = [aws_ecs_cluster.main.arn]
      lastStatus = ["STOPPED"]
      "$or" = [
        { containers = { exitCode = [{ "anything-but" = 0 }] } },
        { stopCode = ["TaskFailedToStart"] },
      ]
    }
  })
}

resource "aws_cloudwatch_event_target" "task_failed_email" {
  rule = aws_cloudwatch_event_rule.task_failed.name
  arn  = aws_sns_topic.alerts.arn

  input_transformer {
    input_paths = {
      command  = "$.detail.overrides.containerOverrides[0].command[0]"
      reason   = "$.detail.stoppedReason"
      exitCode = "$.detail.containers[0].exitCode"
      task     = "$.detail.taskArn"
      time     = "$.time"
    }
    input_template = <<-EOT
      "Invoice automation job FAILED: <command> (exit code <exitCode>) at <time> UTC."
      "Reason: <reason>"
      "Task: <task>"
      "Logs: https://${var.aws_region}.console.aws.amazon.com/cloudwatch/home?region=${var.aws_region}#logsV2:log-groups/log-group/${replace(aws_cloudwatch_log_group.app.name, "/", "$252F")}"
    EOT
  }
}

# ------------------------------------------------------------------------------
# Alert 2: the scheduler could not start the task at all (permissions, capacity, etc.)
# ------------------------------------------------------------------------------

resource "aws_cloudwatch_metric_alarm" "schedule_dropped" {
  alarm_name          = "${var.repository_name}-schedule-dropped"
  alarm_description   = "EventBridge Scheduler failed to start an invoice automation task"
  namespace           = "AWS/Scheduler"
  metric_name         = "InvocationDroppedCount"
  dimensions          = { ScheduleGroup = aws_scheduler_schedule_group.main.name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 0
  comparison_operator = "GreaterThanThreshold"
  treat_missing_data  = "notBreaching"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}
