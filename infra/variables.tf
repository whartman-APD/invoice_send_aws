variable "aws_region" {
  description = "AWS region for ECR repository"
  type        = string
  default     = "us-west-2"
}

variable "repository_name" {
  description = "Name of the ECR repository"
  type        = string
  default     = "invoice-send-qbo"
}

variable "image_tag" {
  description = "Docker image tag"
  type        = string
  default     = "latest"
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
