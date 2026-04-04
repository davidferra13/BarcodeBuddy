# Barcode Buddy — Self-healing startup script
# Starts the stats/web app and a localtunnel public tunnel.
# Both processes are watched and restarted automatically if they crash.
# Run this once; it loops forever. Ctrl+C to stop.
#
# PUBLIC URL (stable subdomain): https://barcodebuddy-global.loca.lt
# This subdomain is reserved as long as this script is running.

$AppDir     = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PyExe      = "C:\Users\david\AppData\Local\Programs\Python\Launcher\py.exe"
$AppPort    = 8080
$Subdomain  = "barcodebuddy-global"
$PublicUrl  = "https://$Subdomain.loca.lt"
$LogDir     = Join-Path $AppDir "data\logs"
$AppLog     = Join-Path $LogDir "app-stdout.log"
$TunnelLog  = Join-Path $LogDir "tunnel.log"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

function Start-App {
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting Barcode Buddy app on port $AppPort..." -ForegroundColor Cyan
    $proc = Start-Process -FilePath $PyExe `
        -ArgumentList "stats.py --host 0.0.0.0 --port $AppPort" `
        -WorkingDirectory $AppDir `
        -RedirectStandardOutput $AppLog `
        -RedirectStandardError  "$AppLog.err" `
        -PassThru -NoNewWindow
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] App started (PID $($proc.Id))" -ForegroundColor Green
    return $proc
}

function Start-Tunnel {
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting tunnel -> $PublicUrl ..." -ForegroundColor Cyan
    $npxArgs = "--yes localtunnel --port $AppPort --subdomain $Subdomain"
    $proc = Start-Process -FilePath "npx" `
        -ArgumentList $npxArgs `
        -WorkingDirectory $AppDir `
        -RedirectStandardOutput $TunnelLog `
        -RedirectStandardError  "$TunnelLog.err" `
        -PassThru -NoNewWindow
    Start-Sleep -Seconds 4
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel started (PID $($proc.Id)). Public URL: $PublicUrl" -ForegroundColor Yellow
    return $proc
}

# Kill any leftover instances before starting fresh
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'localtunnel' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "=== Barcode Buddy Startup ===" -ForegroundColor Magenta
Write-Host "Working directory: $AppDir"
Write-Host "Public URL will be: $PublicUrl" -ForegroundColor Yellow

$appProc    = Start-App
Start-Sleep -Seconds 3   # let the app bind its port before the tunnel tries to reach it
$tunnelProc = Start-Tunnel

Write-Host "`n  *** PUBLIC URL: $PublicUrl ***`n" -ForegroundColor Green

# Watch loop: restart whichever process dies
while ($true) {
    Start-Sleep -Seconds 10

    if ($appProc.HasExited) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] App exited (code $($appProc.ExitCode)). Restarting..." -ForegroundColor Red
        $appProc = Start-App
    }

    if ($tunnelProc.HasExited) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel exited. Restarting..." -ForegroundColor Red
        $tunnelProc = Start-Tunnel
    }
}
