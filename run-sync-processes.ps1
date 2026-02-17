# Robocorp Process Sync - Scheduled Task Script
# This script runs the Docker container to sync Robocorp processes to Azure SQL

# Set up logging
$LogFile = "C:\Users\WesleyHartman\Documents\APD Repos\invoice_send_aws\sync-processes.log"
$Timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

# Log start
Add-Content -Path $LogFile -Value ""
Add-Content -Path $LogFile -Value "=========================================="
Add-Content -Path $LogFile -Value "$Timestamp - Starting sync-processes task"
Add-Content -Path $LogFile -Value "=========================================="

try {
    # Change to the project directory
    $ProjectDir = "C:\Users\WesleyHartman\Documents\APD Repos\invoice_send_aws\send_qbo_invoices"
    Set-Location $ProjectDir
    Add-Content -Path $LogFile -Value "$Timestamp - Changed to directory: $ProjectDir"

    # Check if Docker is running
    $DockerStatus = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Add-Content -Path $LogFile -Value "$Timestamp - ERROR: Docker is not running!"
        Add-Content -Path $LogFile -Value "$Timestamp - Docker error: $DockerStatus"
        exit 1
    }
    Add-Content -Path $LogFile -Value "$Timestamp - Docker is running"

    # Run the Docker command and capture output
    Add-Content -Path $LogFile -Value "$Timestamp - Executing: docker-compose run --rm invoice-processor --sync-processes"

    $Output = docker-compose run --rm invoice-processor --sync-processes 2>&1
    $ExitCode = $LASTEXITCODE

    # Log all output
    Add-Content -Path $LogFile -Value "$Timestamp - Docker output:"
    Add-Content -Path $LogFile -Value $Output

    # Log completion status
    if ($ExitCode -eq 0) {
        Add-Content -Path $LogFile -Value "$Timestamp - SUCCESS: Task completed successfully (exit code: $ExitCode)"
    } else {
        Add-Content -Path $LogFile -Value "$Timestamp - ERROR: Task failed with exit code: $ExitCode"
    }

} catch {
    # Log any exceptions
    Add-Content -Path $LogFile -Value "$Timestamp - EXCEPTION: $($_.Exception.Message)"
    Add-Content -Path $LogFile -Value "$Timestamp - Stack trace: $($_.ScriptStackTrace)"
    exit 1
}

Add-Content -Path $LogFile -Value "$Timestamp - Script execution completed"
Add-Content -Path $LogFile -Value "=========================================="
