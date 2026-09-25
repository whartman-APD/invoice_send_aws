# Deploy to AWS: update infrastructure with Terraform, then build and push the image it expects.
#
# Usage (from the repo root, with Docker Desktop running and `aws sso login` done):
#   .\deploy.ps1
#
# Running this does NOT start any job. Terraform shows its plan and waits for you to type "yes".
# The image tag is a hash of the source files, so an unchanged codebase skips the build.

$ErrorActionPreference = "Stop"

$InfraDir = Join-Path $PSScriptRoot "infra"
$ContextDir = Join-Path $PSScriptRoot "send_qbo_invoices"

Write-Host "=== Step 1 of 2: Terraform ===" -ForegroundColor Cyan
terraform -chdir="$InfraDir" apply
if ($LASTEXITCODE -ne 0) { throw "terraform apply failed or was cancelled" }

$Region = terraform -chdir="$InfraDir" output -json run_task_config | ConvertFrom-Json | Select-Object -ExpandProperty region
$RepoUrl = terraform -chdir="$InfraDir" output -raw ecr_repository_url
$Tag = terraform -chdir="$InfraDir" output -raw image_tag
$RepoName = $RepoUrl.Split("/")[-1]
$Registry = $RepoUrl.Split("/")[0]
$Image = "${RepoUrl}:${Tag}"

Write-Host "=== Step 2 of 2: Image $Tag ===" -ForegroundColor Cyan
aws ecr describe-images --region $Region --repository-name $RepoName --image-ids imageTag=$Tag *> $null
if ($LASTEXITCODE -eq 0) {
    Write-Host "Image $Tag is already in ECR (no code changes). Nothing to build."
    exit 0
}

aws ecr get-login-password --region $Region | docker login --username AWS --password-stdin $Registry
if ($LASTEXITCODE -ne 0) { throw "ECR login failed" }

docker build --platform linux/amd64 -t $Image $ContextDir
if ($LASTEXITCODE -ne 0) { throw "docker build failed" }

docker push $Image
if ($LASTEXITCODE -ne 0) { throw "docker push failed" }

Write-Host "Deployed $Image" -ForegroundColor Green
