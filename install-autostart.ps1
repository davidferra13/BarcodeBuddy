# Registers BarcodeBuddy as a Windows scheduled task that runs at logon.
# Run this script once as Administrator.
#
# By default the task starts the app LOCAL ONLY. Pass -Tunnel to register a task that
# also publishes a Cloudflare Tunnel (public URL) every time it starts:
#   .\install-autostart.ps1 -Tunnel

[CmdletBinding()]
param(
    [switch]$Tunnel
)

$TaskName   = "BarcodeBuddy"
$ScriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "start-app.ps1"

$ScriptArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`""
if ($Tunnel) {
    $ScriptArgs += " -Tunnel"
    $Description = "BarcodeBuddy app + Cloudflare tunnel (24/7 public access)"
} else {
    $Description = "BarcodeBuddy app (local only, http://localhost:8080)"
}

# Remove existing task if present
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument $ScriptArgs

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
    -Description $Description `
    -RunLevel Highest

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered: $Description" -ForegroundColor Green
Write-Host "It will auto-start at logon and restart if it crashes." -ForegroundColor Green
Write-Host ""
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
