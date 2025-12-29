#
# Knosi Sync - Windows Auto-start Setup
# Creates a scheduled task to run knosi-sync.py at login
#
# Run this script in PowerShell as Administrator (for Task Scheduler)
# Or run without admin to use Startup folder instead
#

param(
    [string]$ServerUrl,
    [string]$VaultPath,
    [string]$ApiKey = "",
    [switch]$UseStartupFolder,
    [switch]$Uninstall
)

$ErrorActionPreference = "Stop"
$TaskName = "KnosiSync"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$SyncScript = Join-Path (Split-Path -Parent $ScriptDir) "knosi-sync.py"

Write-Host "Knosi Sync - Windows Auto-start Setup" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host

# Handle uninstall
if ($Uninstall) {
    Write-Host "Uninstalling..."
    
    # Remove scheduled task
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($task) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed scheduled task: $TaskName" -ForegroundColor Green
    }
    
    # Remove startup shortcut
    $startupPath = [Environment]::GetFolderPath("Startup")
    $shortcutPath = Join-Path $startupPath "KnosiSync.bat"
    if (Test-Path $shortcutPath) {
        Remove-Item $shortcutPath -Force
        Write-Host "Removed startup script: $shortcutPath" -ForegroundColor Green
    }
    
    Write-Host "`nUninstall complete!" -ForegroundColor Green
    exit 0
}

# Verify knosi-sync.py exists
if (-not (Test-Path $SyncScript)) {
    Write-Host "Error: knosi-sync.py not found at $SyncScript" -ForegroundColor Red
    exit 1
}

# Get Python path
$PythonPath = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonPath) {
    $PythonPath = (Get-Command python3 -ErrorAction SilentlyContinue).Source
}
if (-not $PythonPath) {
    Write-Host "Error: Python not found in PATH" -ForegroundColor Red
    exit 1
}
Write-Host "Found Python: $PythonPath"

# Get configuration interactively if not provided
if (-not $ServerUrl) {
    $ServerUrl = Read-Host "Server URL (e.g., http://your-server:48550)"
}

if (-not $VaultPath) {
    $VaultPath = Read-Host "Vault path (e.g., C:\Users\You\Documents\vault)"
}

# Expand environment variables in path
$VaultPath = [Environment]::ExpandEnvironmentVariables($VaultPath)

# Verify vault path exists
if (-not (Test-Path $VaultPath)) {
    Write-Host "Error: Vault path does not exist: $VaultPath" -ForegroundColor Red
    exit 1
}

if (-not $ApiKey) {
    $ApiKey = Read-Host "API key (leave empty if not required)"
}

# Build arguments
$Arguments = "-u `"$SyncScript`" --server `"$ServerUrl`" --vault `"$VaultPath`""
if ($ApiKey) {
    $Arguments += " --api-key `"$ApiKey`""
}

# Check for admin rights
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)

if ($UseStartupFolder -or -not $isAdmin) {
    if (-not $UseStartupFolder -and -not $isAdmin) {
        Write-Host "`nNot running as Administrator. Using Startup folder instead." -ForegroundColor Yellow
        Write-Host "(Run as Administrator to use Task Scheduler)`n"
    }
    
    # Create batch file in Startup folder
    $startupPath = [Environment]::GetFolderPath("Startup")
    $batchPath = Join-Path $startupPath "KnosiSync.bat"
    
    $batchContent = @"
@echo off
:: Knosi Sync - Auto-start script
:: Runs in background, logs to %TEMP%\knosi-sync.log

start /min "" "$PythonPath" $Arguments > "%TEMP%\knosi-sync.log" 2>&1
"@
    
    Set-Content -Path $batchPath -Value $batchContent
    Write-Host "Created startup script: $batchPath" -ForegroundColor Green
    
    Write-Host "`nInstallation complete!" -ForegroundColor Green
    Write-Host "`nThe sync service will:"
    Write-Host "  - Start automatically at login"
    Write-Host "  - Run minimized in background"
    Write-Host "  - Log to %TEMP%\knosi-sync.log"
    Write-Host "`nTo start now, run: $batchPath"
    Write-Host "To uninstall: .\setup-windows.ps1 -Uninstall"
}
else {
    # Use Task Scheduler (requires admin)
    Write-Host "`nCreating scheduled task..."
    
    # Remove existing task if present
    $existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($existingTask) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Host "Removed existing task"
    }
    
    # Create task
    $action = New-ScheduledTaskAction -Execute $PythonPath -Argument $Arguments
    $trigger = New-ScheduledTaskTrigger -AtLogon
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Description "Knosi document sync service"
    
    Write-Host "Created scheduled task: $TaskName" -ForegroundColor Green
    
    Write-Host "`nInstallation complete!" -ForegroundColor Green
    Write-Host "`nThe sync service will:"
    Write-Host "  - Start automatically at login"
    Write-Host "  - Restart on failure (up to 3 times)"
    Write-Host "`nUseful commands:"
    Write-Host "  Start now:    Start-ScheduledTask -TaskName $TaskName"
    Write-Host "  Stop:         Stop-ScheduledTask -TaskName $TaskName"
    Write-Host "  View status:  Get-ScheduledTask -TaskName $TaskName"
    Write-Host "  Uninstall:    .\setup-windows.ps1 -Uninstall"
    
    # Offer to start now
    $startNow = Read-Host "`nStart the sync service now? (y/n)"
    if ($startNow -eq "y") {
        Start-ScheduledTask -TaskName $TaskName
        Write-Host "Service started!" -ForegroundColor Green
    }
}
