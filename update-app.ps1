# BarcodeBuddy — Update Script
# Pulls the latest code from the repository and restarts the service.
#
# Usage:  .\update-app.ps1
# Run from the BarcodeBuddy project directory.

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$TaskName = "BarcodeBuddy"

Write-Host ""
Write-Host "=== BarcodeBuddy Update ===" -ForegroundColor Magenta
Write-Host "Working directory: $AppDir"
Write-Host ""

# ── Step 1: Check for uncommitted changes ────────────────────────────
Set-Location $AppDir
$status = git status --porcelain 2>&1
if ($status) {
    Write-Host "[!] Warning: uncommitted local changes detected." -ForegroundColor Yellow
    Write-Host "    These will be preserved (git pull uses merge)." -ForegroundColor DarkGray
    Write-Host ""
}

# ── Step 2: Record current version ───────────────────────────────────
$oldVersion = python -c "from app import __version__; print(__version__)" 2>$null
if (-not $oldVersion) { $oldVersion = "unknown" }

# ── Step 3: Stop the service if running as scheduled task ────────────
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task -and $task.State -eq "Running") {
    Write-Host "[1/5] Stopping $TaskName scheduled task..." -ForegroundColor Cyan
    Stop-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 3
    Write-Host "      Stopped." -ForegroundColor Green
} else {
    Write-Host "[1/5] No running scheduled task found — skipping stop." -ForegroundColor DarkGray
}

# ── Step 4: Pull latest code ─────────────────────────────────────────
Write-Host "[2/5] Pulling latest code from repository..." -ForegroundColor Cyan
$pullResult = git pull 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] git pull failed:" -ForegroundColor Red
    Write-Host $pullResult
    Write-Host ""
    Write-Host "Update aborted. Please resolve any conflicts and try again." -ForegroundColor Red
    exit 1
}
Write-Host "      $pullResult" -ForegroundColor Green

# ── Step 5: Update dependencies ──────────────────────────────────────
Write-Host "[3/5] Updating dependencies..." -ForegroundColor Cyan
pip install -r requirements.txt --quiet 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] pip install failed. Check requirements.txt." -ForegroundColor Red
    exit 1
}
Write-Host "      Dependencies up to date." -ForegroundColor Green

# ── Step 6: Verify compilation ───────────────────────────────────────
Write-Host "[4/5] Verifying code integrity..." -ForegroundColor Cyan
python -m compileall app tests main.py stats.py -q 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[!] Compilation check failed. The update may contain errors." -ForegroundColor Red
    Write-Host "    Contact the developer before restarting." -ForegroundColor Red
    exit 1
}
Write-Host "      Compilation check passed." -ForegroundColor Green

# ── Step 7: Report version change ────────────────────────────────────
$newVersion = python -c "from app import __version__; print(__version__)" 2>$null
if (-not $newVersion) { $newVersion = "unknown" }

# ── Step 8: Restart the service ──────────────────────────────────────
Write-Host "[5/5] Restarting service..." -ForegroundColor Cyan
if ($task) {
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 5
    $task = Get-ScheduledTask -TaskName $TaskName
    if ($task.State -eq "Running") {
        Write-Host "      Service restarted successfully." -ForegroundColor Green
    } else {
        Write-Host "      Task registered but not yet running. Check Task Scheduler." -ForegroundColor Yellow
    }
} else {
    Write-Host "      No scheduled task found. Start manually with: .\start-app.ps1" -ForegroundColor Yellow
}

# ── Done ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Update Complete ===" -ForegroundColor Green
Write-Host "  Previous version: $oldVersion"
Write-Host "  Current version:  $newVersion"
if ($oldVersion -ne $newVersion) {
    Write-Host "  Version changed!" -ForegroundColor Cyan
}
Write-Host ""
