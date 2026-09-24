# BarcodeBuddy - Self-healing startup script
# Starts the stats/web app and watches it, restarting it if it crashes.
# Run this once; it loops forever. Ctrl+C to stop.
#
# PUBLIC ACCESS IS OPT-IN. By default the app is LOCAL ONLY (http://localhost:8080).
# A Cloudflare Tunnel is started only when you ask for it:
#   .\start-app.ps1 -Tunnel            (or set BARCODEBUDDY_TUNNEL=1 in the environment)
#
# TUNNEL MODES (only when -Tunnel is given):
#   Named tunnel (permanent URL) - uses the customer hostname when its zone is on Cloudflare
#   Quick tunnel (temporary URL)  - fallback *.trycloudflare.com URL, changes on restart
#
# The script auto-detects which mode to use. To switch to the permanent URL,
# add the customer domain to Cloudflare and run:
#   cloudflared tunnel route dns barcodebuddy app.danpack.com
#
# SAFETY: this script never stops cloudflared processes it does not own. Only tunnels
# started with this install's config files or pointed at this app's port are cleaned up.

[CmdletBinding()]
param(
    [switch]$Tunnel
)

$AppDir       = Split-Path -Parent $MyInvocation.MyCommand.Definition
$AppPort      = 8080
$LogDir       = Join-Path $AppDir "data\logs"
$AppLog       = Join-Path $LogDir "app-stdout.log"
$TunnelLog    = Join-Path $LogDir "tunnel.log"
$UrlFile      = Join-Path $LogDir "tunnel-url.txt"
$QuickCfg     = Join-Path $LogDir "quick-tunnel.yml"
$TunnelConfig = "$env:USERPROFILE\.cloudflared\barcodebuddy.yml"
$PermanentUrl = "https://app.danpack.com"

$TunnelEnabled = [bool]$Tunnel -or ($env:BARCODEBUDDY_TUNNEL -eq '1')

# Python: prefer this install's own venv, then the py launcher, then python on PATH.
$VenvPy = Join-Path $AppDir ".venv\Scripts\python.exe"
if (Test-Path $VenvPy) {
    $PyExe  = $VenvPy
    $PyArgs = ""
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PyExe  = (Get-Command py).Source
    $PyArgs = "-3"
} else {
    $PyExe  = "python"
    $PyArgs = ""
}

# Ensure log directory exists
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

# Import preflight: fail fast with a readable message instead of a crash loop.
& $PyExe $PyArgs -c "import stats" 2>&1 | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Python preflight failed using $PyExe $PyArgs. Install requirements first:" -ForegroundColor Red
    Write-Host "  $PyExe -m pip install -r requirements.txt" -ForegroundColor Yellow
    exit 1
}

# Detect whether the named tunnel config + DNS are ready (only matters with -Tunnel)
$UseNamedTunnel = $false
if ($TunnelEnabled -and (Test-Path $TunnelConfig)) {
    try {
        $dns = Resolve-DnsName "app.danpack.com" -Type CNAME -ErrorAction Stop 2>$null
        if ($dns -and ($dns.NameHost -match 'cfargotunnel\.com')) {
            $UseNamedTunnel = $true
        }
    } catch { }
}

function Start-App {
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting BarcodeBuddy app on port $AppPort..." -ForegroundColor Cyan
    $argList = @()
    if ($PyArgs) { $argList += $PyArgs }
    $argList += @("stats.py", "--host", "0.0.0.0", "--port", "$AppPort")
    $proc = Start-Process -FilePath $PyExe `
        -ArgumentList $argList `
        -WorkingDirectory $AppDir `
        -RedirectStandardOutput $AppLog `
        -RedirectStandardError  "$AppLog.err" `
        -PassThru -NoNewWindow
    Write-Host "[$(Get-Date -f 'HH:mm:ss')] App started (PID $($proc.Id))" -ForegroundColor Green
    return $proc
}

function Get-OwnedTunnelProcesses {
    # Only cloudflared processes that belong to THIS install: started with this install's
    # named-tunnel config, its quick-tunnel config, or pointed at this app's port.
    $needles = @($TunnelConfig, $QuickCfg, "localhost:$AppPort")
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'cloudflared.exe' -and $_.CommandLine } |
        Where-Object { $cl = $_.CommandLine; ($needles | Where-Object { $cl -like "*$_*" }).Count -gt 0 }
}

function Stop-OwnedTunnels {
    $owned = @(Get-OwnedTunnelProcesses)
    foreach ($p in $owned) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Stopping leftover tunnel from this install (PID $($p.ProcessId))" -ForegroundColor DarkGray
        Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    }
    # localtunnel (node) instances pointed at this port only
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq 'node.exe' -and $_.CommandLine -match 'localtunnel' -and $_.CommandLine -match "$AppPort" } |
        ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
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
        Write-Host "  (permanent - this URL never changes)" -ForegroundColor DarkGray
        Write-Host ""
    } else {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Starting quick tunnel on port $AppPort ..." -ForegroundColor Cyan
        Write-Host "  (temporary URL - add the customer domain to Cloudflare for a permanent one)" -ForegroundColor DarkGray

        # Write a minimal ingress config so the default ~/.cloudflared/config.yml
        # (which may have a catch-all http_status:404 for named tunnels) does not
        # swallow quick-tunnel traffic.
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

Write-Host "=== BarcodeBuddy Startup ===" -ForegroundColor Magenta
Write-Host "Working directory: $AppDir"
Write-Host "Python: $PyExe $PyArgs"
if (-not $TunnelEnabled) {
    Write-Host "Tunnel: OFF (local only) -> http://localhost:$AppPort" -ForegroundColor Yellow
    Write-Host "  Pass -Tunnel (or set BARCODEBUDDY_TUNNEL=1) to publish a public URL." -ForegroundColor DarkGray
    Remove-Item $UrlFile -Force -ErrorAction SilentlyContinue
} elseif ($UseNamedTunnel) {
    Write-Host "Tunnel mode: NAMED (permanent URL: $PermanentUrl)" -ForegroundColor Green
} else {
    Write-Host "Tunnel mode: QUICK (temporary *.trycloudflare.com URL)" -ForegroundColor Yellow
}

if ($TunnelEnabled) {
    if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
        Write-Host "cloudflared is not installed; cannot publish a tunnel. Starting local only." -ForegroundColor Red
        $TunnelEnabled = $false
    } else {
        Stop-OwnedTunnels
    }
}

$appProc    = Start-App
$tunnelProc = $null
if ($TunnelEnabled) {
    Start-Sleep -Seconds 3   # let the app bind its port before the tunnel tries to reach it
    $tunnelProc = Start-Tunnel
}

# Watch loop: restart whichever process dies
while ($true) {
    Start-Sleep -Seconds 10

    if ($appProc.HasExited) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] App exited (code $($appProc.ExitCode)). Restarting..." -ForegroundColor Red
        $appProc = Start-App
    }

    if ($TunnelEnabled -and $tunnelProc -and $tunnelProc.HasExited) {
        Write-Host "[$(Get-Date -f 'HH:mm:ss')] Tunnel exited. Restarting..." -ForegroundColor Red
        $tunnelProc = Start-Tunnel
    }
}
