variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-west-2"
}

variable "repository_name" {
  description = "Name of the ECR repository (also used as the prefix for other resource names)"
  type        = string
  default     = "invoice-send-qbo"
}

variable "image_tag" {
  description = "Docker image tag. Leave empty to tag with a hash of the source files."
  type        = string
  default     = ""
}

variable "image_retention_count" {
  description = "Number of images to retain in ECR"
  type        = number
  default     = 10
}

variable "enable_image_scanning" {
  description = "Enable image scanning on push"
  type        = bool
  default     = true
}

variable "docker_context_path" {
  description = "Path to the Docker build context"
  type        = string
  default     = "../send_qbo_invoices"
}

# ------------------------------------------------------------------------------
# Task sizing
# ------------------------------------------------------------------------------

variable "task_cpu" {
  description = "Fargate task CPU units (1024 = 1 vCPU)"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate task memory in MB"
  type        = number
  default     = 2048
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

# ------------------------------------------------------------------------------
# Secrets Manager secret names (must already exist)
# ------------------------------------------------------------------------------

variable "secret_names" {
  description = "Secrets Manager secret names, keyed by the environment variable the app reads them from"
  type        = map(string)
  default = {
    QBO_SECRET_NAME          = "QBO/10000"
    MSGRAPH_SECRET_NAME      = "MsGraph/10000"
    CLICKUP_SECRET_NAME      = "ClickUp/10000"
    ROBOCORP_API_SECRET_NAME = "RoboCorp/10000/ClientAPIKeys"
    GITHUB_PAT_SECRET_NAME   = "GitHub/10000/PersonalAccessToken"
    AZURE_OPENAI_SECRET_NAME = "AzureOpenAI/10000"
  }
}

variable "dynamodb_table_robocorp_clients" {
  description = "DynamoDB table with client organization/workspace IDs"
  type        = string
  default     = "Robocorp_Client_Org_Workspace_IDs"
}

# ------------------------------------------------------------------------------
# App configuration (non-secret)
# ------------------------------------------------------------------------------

variable "bookkeeper_email" {
  description = "Recipient of the invoice creation summary"
  type        = string
  default     = "whartman@automatapracdev.com"
}

variable "sender_email" {
  description = "Mailbox used to send notification emails"
  type        = string
  default     = "robotarmy@automatapracdev.com"
}

variable "digest_email_from" {
  description = "Sender of the weekly GitHub digest"
  type        = string
  default     = "whartman@automatapracdev.com"
}

variable "digest_email_to" {
  description = "Recipients of the weekly GitHub digest (comma-separated)"
  type        = string
  default     = "whartman@automatapracdev.com"
}

variable "clickup_digest" {
  description = "ClickUp doc page the weekly digest is prepended to"
  type = object({
    workspace_id = string
    doc_id       = string
    page_id      = string
  })
  default = {
    workspace_id = "9009105550"
    doc_id       = "8cfr2me-7174"
    page_id      = "8cfr2me-19254"
  }
}

variable "ms_graph_hostname" {
  description = "SharePoint hostname for file uploads"
  type        = string
  default     = "automatapracdev.sharepoint.com"
}

# Safe defaults: a run with these values creates nothing and changes nothing.
# Set them to true in terraform.tfvars once a dry run looks right.
variable "create_invoice" {
  description = "Create invoices in QuickBooks Online"
  type        = bool
  default     = false
}

variable "update_clickup" {
  description = "Write usage back to ClickUp"
  type        = bool
  default     = false
}

variable "upload_to_sharepoint" {
  description = "Upload runtime reports to SharePoint"
  type        = bool
  default     = false
}

variable "lower_client_id" {
  description = "Lowest client number to process (inclusive)"
  type        = number
  default     = 10000
}

variable "upper_client_id" {
  description = "Highest client number to process (exclusive)"
  type        = number
  default     = 10040
}

variable "net_30_days_clients" {
  description = "Comma-separated client numbers with NET 30 terms"
  type        = string
  default     = "10020"
}

# ------------------------------------------------------------------------------
# Schedules (EventBridge Scheduler, evaluated in schedule_timezone)
# ------------------------------------------------------------------------------

variable "schedule_timezone" {
  description = "Time zone for all schedules"
  type        = string
  default     = "America/Los_Angeles"
}

variable "github_digest_schedule" {
  description = "When to run the GitHub digest (default: Mondays 1:00 AM)"
  type        = string
  default     = "cron(0 1 ? * MON *)"
}

variable "github_digest_schedule_enabled" {
  description = "Turn the GitHub digest schedule on"
  type        = bool
  default     = false
}

variable "create_invoices_schedule" {
  description = "When to run invoice creation (default: 2nd of the month, 6:00 AM)"
  type        = string
  default     = "cron(0 6 2 * ? *)"
}

variable "create_invoices_schedule_enabled" {
  description = "Turn the invoice creation schedule on (leave off to run it on demand)"
  type        = bool
  default     = false
}

# ------------------------------------------------------------------------------
# Alerts
# ------------------------------------------------------------------------------

variable "alert_email" {
  description = "Email address that receives failure alerts"
  type        = string
  default     = "whartman@automatapracdev.com"
}
