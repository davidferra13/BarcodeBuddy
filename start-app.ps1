# BarcodeBuddy — Self-healing startup script
# Starts the stats/web app and a Cloudflare Tunnel for public access.
# Both processes are watched and restarted automatically if they crash.
# Run this once; it loops forever. Ctrl+C to stop.
#
# TUNNEL MODES:
#   Named tunnel (permanent URL) — uses app.danpack.com when danpack.com is on Cloudflare
#   Quick tunnel (temporary URL)  — fallback *.trycloudflare.com URL, changes on restart
#
# The script auto-detects which mode to use. To switch to the permanent URL,
# add danpack.com to Cloudflare and run:
#   cloudflared tunnel route dns barcodebuddy app.danpack.com

$AppDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$PyExe        = "C:\Users\david\AppData\Local\Programs\Python\Launcher\py.exe"
$PyArgs       = "-3.12"
$AppPort      = 8080
$LogDir       = Join-Path $AppDir "data\logs"
$AppLog       = Join-Path $LogDir "app-stdout.log"
$TunnelLog    = Join-Path $LogDir "tunnel.log"
$UrlFile      = Join-Path $LogDir "tunnel-url.txt"
$TunnelConfig = "$env:USERPROFILE\.cloudflared\barcodebuddy.yml"
$PermanentUrl = "https://app.danpack.com"

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# Detect whether the named tunnel config + DNS are ready
$UseNamedTunnel = $false
if (Test-Path $TunnelConfig) {
    # Check if danpack.com zone exists on Cloudflare by testing DNS for the CNAME
    try {
        $dns = Resolve-DnsName "app.danpack.com" -Type CNAME -ErrorAction Stop 2>$null
        if ($dns -and ($dns.NameHost -match 'cfargotunnel\.com')) {
            $UseNamedTunnel = $true
        }
    } catch { }
}

function Start-App {
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting BarcodeBuddy app on port $AppPort..." -ForegroundColor Cyan
    $proc = Start-Process -FilePath $PyExe `
        -ArgumentList "$PyArgs stats.py --host 0.0.0.0 --port $AppPort" `
        -WorkingDirectory $AppDir `
        -RedirectStandardOutput $AppLog `
        -RedirectStandardError  "$AppLog.err" `
        -PassThru -NoNewWindow
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] App started (PID $($proc.Id))" -ForegroundColor Green
    return $proc
}

function Start-Tunnel {
    # Clear old tunnel logs
    Remove-Item "$TunnelLog", "$TunnelLog.err" -Force -ErrorAction SilentlyContinue

    if ($UseNamedTunnel) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting named tunnel -> $PermanentUrl ..." -ForegroundColor Cyan
        $proc = Start-Process -FilePath "cloudflared" `
            -ArgumentList "tunnel --no-autoupdate --config `"$TunnelConfig`" run barcodebuddy" `
            -WorkingDirectory $AppDir `
            -RedirectStandardOutput $TunnelLog `
            -RedirectStandardError  "$TunnelLog.err" `
            -PassThru -NoNewWindow

        Start-Sleep -Seconds 4
        $PermanentUrl | Out-File -FilePath $UrlFile -Encoding utf8 -Force
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel started (PID $($proc.Id))" -ForegroundColor Green
        Write-Host ""
        Write-Host "  *** PUBLIC URL: $PermanentUrl ***" -ForegroundColor Green
        Write-Host "  (permanent — this URL never changes)" -ForegroundColor DarkGray
        Write-Host ""
    } else {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting quick tunnel on port $AppPort ..." -ForegroundColor Cyan
        Write-Host "  (temporary URL — add danpack.com to Cloudflare for a permanent one)" -ForegroundColor DarkGray

        # Write a minimal ingress config so the default ~/.cloudflared/config.yml
        # (which may have a catch-all http_status:404 for named tunnels) does not
        # swallow quick-tunnel traffic.
        $QuickCfg = Join-Path $LogDir "quick-tunnel.yml"
        "ingress:`n  - service: http://localhost:$AppPort" | Out-File -FilePath $QuickCfg -Encoding utf8 -Force

        $proc = Start-Process -FilePath "cloudflared" `
            -ArgumentList "tunnel --url http://localhost:$AppPort --no-autoupdate --config `"$QuickCfg`"" `
            -WorkingDirectory $AppDir `
            -RedirectStandardOutput $TunnelLog `
            -RedirectStandardError  "$TunnelLog.err" `
            -PassThru -NoNewWindow

        # Wait for cloudflared to negotiate and print the URL
        $publicUrl = $null
        $attempts = 0
        while ($attempts -lt 30 -and -not $publicUrl) {
            Start-Sleep -Seconds 1
            $attempts++
            if (Test-Path "$TunnelLog.err") {
                $logContent = Get-Content "$TunnelLog.err" -Raw -ErrorAction SilentlyContinue
                if ($logContent -match '(https://[a-z0-9-]+\.trycloudflare\.com)') {
                    $publicUrl = $Matches[1]
                }
            }
        }

        if ($publicUrl) {
            $publicUrl | Out-File -FilePath $UrlFile -Encoding utf8 -Force
            Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel started (PID $($proc.Id))" -ForegroundColor Green
            Write-Host ""
            Write-Host "  *** PUBLIC URL: $publicUrl ***" -ForegroundColor Green
            Write-Host "  (saved to $UrlFile)" -ForegroundColor DarkGray
            Write-Host ""
        } else {
            Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel started (PID $($proc.Id)) but could not detect URL yet." -ForegroundColor Yellow
            Write-Host "  Check $TunnelLog.err for the URL." -ForegroundColor DarkGray
        }
    }

    return $proc
}

# Kill any leftover cloudflared / localtunnel instances before starting fresh
Get-Process -Name "cloudflared" -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process | Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'localtunnel' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Host "=== BarcodeBuddy Startup ===" -ForegroundColor Magenta
Write-Host "Working directory: $AppDir"
if ($UseNamedTunnel) {
    Write-Host "Tunnel mode: NAMED (permanent URL: $PermanentUrl)" -ForegroundColor Green
} else {
    Write-Host "Tunnel mode: QUICK (temporary *.trycloudflare.com URL)" -ForegroundColor Yellow
}

$appProc    = Start-App
Start-Sleep -Seconds 3   # let the app bind its port before the tunnel tries to reach it
$tunnelProc = Start-Tunnel

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
