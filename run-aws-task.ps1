# Start an invoice automation job on AWS ECS Fargate and stream its logs.
#
# Examples:
#   .\run-aws-task.ps1 -Job github-digest
#   .\run-aws-task.ps1 -Job sync-processes
#   .\run-aws-task.ps1 -Job create-invoices -DryRun
#   .\run-aws-task.ps1 -Job create-invoices -BillingReferenceDate 2026-10-01
#   .\run-aws-task.ps1 -Job create-invoices -LowerClientId 10018
#
# -DryRun forces CREATE_INVOICE, UPDATE_CLICKUP and UPLOAD_TO_SHAREPOINT to false for this run only.
# -LowerClientId starts at that client number (inclusive), skipping clients below it. Use it to finish
#   a run that failed partway: pass the first client that did NOT get an invoice, so the clients that
#   already have one aren't invoiced twice.
# Requires: AWS CLI logged in (aws sso login) and Terraform state in .\infra.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet("create-invoices", "github-digest", "sync-processes")]
    [string]$Job,

    [switch]$DryRun,

    [string]$BillingReferenceDate,

    [ValidateRange(10000, 99999)]
    [int]$LowerClientId,

    [switch]$NoFollow
)

$ErrorActionPreference = "Stop"

$InfraDir = Join-Path $PSScriptRoot "infra"
$Config = terraform -chdir="$InfraDir" output -json run_task_config | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) { throw "Could not read Terraform outputs. Run 'terraform apply' in .\infra first." }

$Environment = @()
if ($DryRun) {
    $Environment += @{ name = "CREATE_INVOICE"; value = "false" }
    $Environment += @{ name = "UPDATE_CLICKUP"; value = "false" }
    $Environment += @{ name = "UPLOAD_TO_SHAREPOINT"; value = "false" }
}
if ($BillingReferenceDate) {
    $Environment += @{ name = "BILLING_REFERENCE_DATE"; value = $BillingReferenceDate }
}
if ($LowerClientId) {
    if ($Job -ne "create-invoices") { throw "-LowerClientId only applies to create-invoices" }
    $Environment += @{ name = "LOWER_CLIENT_ID"; value = "$LowerClientId" }
}

$ContainerOverride = @{ name = $Config.container_name; command = @("--$Job") }
if ($Environment.Count -gt 0) { $ContainerOverride.environment = $Environment }

$OverridesFile = New-TemporaryFile
$NetworkFile = New-TemporaryFile
try {
    @{ containerOverrides = @($ContainerOverride) } | ConvertTo-Json -Depth 5 | Set-Content -Path $OverridesFile -Encoding ascii
    # sync-processes runs in the n8n VPC's private subnets (NAT IP allowed by the Azure SQL firewall)
    if ($Job -eq "sync-processes") {
        $Network = @{ subnets = @($Config.sync_subnets); securityGroups = @($Config.sync_security_group); assignPublicIp = "DISABLED" }
    } else {
        $Network = @{ subnets = @($Config.subnets); securityGroups = @($Config.security_group); assignPublicIp = "ENABLED" }
    }
    @{ awsvpcConfiguration = $Network } | ConvertTo-Json -Depth 5 | Set-Content -Path $NetworkFile -Encoding ascii

    Write-Host "Starting $Job$(if ($DryRun) { ' (dry run)' })$(if ($LowerClientId) { " from client $LowerClientId" })..."
    $TaskArn = aws ecs run-task `
        --region $Config.region `
        --cluster $Config.cluster `
        --task-definition $Config.task_definition `
        --launch-type FARGATE `
        --network-configuration "file://$NetworkFile" `
        --overrides "file://$OverridesFile" `
        --query "tasks[0].taskArn" --output text
    if ($LASTEXITCODE -ne 0 -or -not $TaskArn -or $TaskArn -eq "None") { throw "run-task failed" }
}
finally {
    Remove-Item $OverridesFile, $NetworkFile -ErrorAction SilentlyContinue
}

$TaskId = $TaskArn.Split("/")[-1]
Write-Host "Task started: $TaskId"
Write-Host "Console: https://$($Config.region).console.aws.amazon.com/ecs/v2/clusters/$($Config.cluster)/tasks/$TaskId"

if ($NoFollow) { exit 0 }

Write-Host "Waiting for the container to start (usually under a minute)..."
aws ecs wait tasks-running --region $Config.region --cluster $Config.cluster --tasks $TaskArn 2>$null

# Stream logs in the background until the task stops
$Stream = "job/$($Config.container_name)/$TaskId"
$LogJob = Start-Job -ScriptBlock {
    param($Region, $Group, $Stream)
    aws logs tail $Group --region $Region --log-stream-names $Stream --follow --format short
} -ArgumentList $Config.region, $Config.log_group, $Stream

# Print log lines as they arrive; check whether the task has stopped every 30 seconds
$LastStatusCheck = Get-Date
while ($true) {
    Receive-Job $LogJob
    if (((Get-Date) - $LastStatusCheck).TotalSeconds -ge 30) {
        $LastStatusCheck = Get-Date
        $Status = aws ecs describe-tasks --region $Config.region --cluster $Config.cluster --tasks $TaskArn `
            --query "tasks[0].lastStatus" --output text
        if ($Status -eq "STOPPED") { break }
    }
    Start-Sleep -Seconds 2
}
Start-Sleep -Seconds 10
Receive-Job $LogJob
Stop-Job $LogJob; Remove-Job $LogJob

$ExitCode = aws ecs describe-tasks --region $Config.region --cluster $Config.cluster --tasks $TaskArn `
    --query "tasks[0].containers[0].exitCode" --output text
Write-Host "Task finished with exit code $ExitCode"
if ($ExitCode -ne "0") { exit 1 }
