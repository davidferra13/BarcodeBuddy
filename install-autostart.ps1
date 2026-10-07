# Registers BarcodeBuddy as a Windows scheduled task that runs at logon.
# Run this script once as Administrator.
#
# Defaults are customer-safe: loopback-only web access and no public tunnel.
# Pass -Lan to bind the web app to the LAN, and -Tunnel only when public
# Cloudflare access is explicitly intended.

[CmdletBinding()]
param(
    [string]$Config = "config.json",
    [switch]$Lan,
    [switch]$Tunnel,
    [string]$PublicHostname = "",
    [switch]$NoIngestion
)

$TaskName   = "BarcodeBuddy"
$ScriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Definition) "start-app.ps1"

$ScriptArgs = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File `"$ScriptPath`" -Config `"$Config`""
if ($Lan) {
    $ScriptArgs += " -Lan"
}
if ($Tunnel) {
    $ScriptArgs += " -Tunnel"
}
if ($PublicHostname) {
    $ScriptArgs += " -PublicHostname `"$PublicHostname`""
}
if ($NoIngestion) {
    $ScriptArgs += " -NoIngestion"
}

if ($Tunnel) {
    $Description = "BarcodeBuddy app + Cloudflare tunnel"
} elseif ($Lan) {
    $Description = "BarcodeBuddy app (LAN access enabled)"
} else {
    $Description = "BarcodeBuddy app (local only, loopback http://127.0.0.1:8080)"
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

$Action  = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $ScriptArgs
$Trigger = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -RestartCount 999 `
    -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Settings $Settings `
    -Description $Description `
    -RunLevel Highest

Write-Host ""
Write-Host "Scheduled task '$TaskName' registered: $Description" -ForegroundColor Green
Write-Host "Config: $Config" -ForegroundColor Green
Write-Host "It will auto-start at logon and restart if it crashes." -ForegroundColor Green
Write-Host ""
Write-Host "To remove: Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false" -ForegroundColor DarkGray
