# Terraform state lives in S3 (bucket defined in state.tf). Backend settings can't use variables,
# so the bucket name is spelled out. use_lockfile stops two applies from running at once.

terraform {
  backend "s3" {
    bucket       = "invoice-send-qbo-tfstate-739275469467"
    key          = "invoice-send-qbo/terraform.tfstate"
    region       = "us-west-2"
    encrypt      = true
    use_lockfile = true
  }
}
