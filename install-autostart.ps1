# Registers BarcodeBuddy as a Windows scheduled task that runs at logon.
# Run this script once as Administrator.

$TaskName   = "BarcodeBuddy"
$ScriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "start-app.ps1"

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""

$Trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 999 `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)  # no time limit

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description "BarcodeBuddy app + Cloudflare tunnel (24/7 public access)" `
    -RunLevel Highest

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered." -ForegroundColor Green
Write-Host "It will auto-start at logon and restart if it crashes." -ForegroundColor Green
Write-Host ""
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
