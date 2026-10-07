# BarcodeBuddy customer provisioning wrapper.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$WorkflowKey,
    [string]$ConfigPath = "config.customer.json",
    [string]$RuntimeRoot = ".\data\customer",
    [int]$ServerPort = 8080,
    [string[]]$BarcodePattern = @(),
    [ValidateSet("timestamp","reject")]
    [string]$DuplicateHandling = "timestamp",
    [switch]$InstallDependencies,
    [switch]$Overwrite
)

$ErrorActionPreference = "Stop"
$AppDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$VenvDir = Join-Path $AppDir ".venv"
$VenvPy = Join-Path $VenvDir "Scripts\python.exe"
$CreatedVenv = $false
if (-not (Test-Path $VenvPy)) {
    $PyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if (-not $PyLauncher) {
        throw "Python launcher 'py' is required to create the BarcodeBuddy environment."
    }
    & $PyLauncher.Source -3.12 -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) { throw "Failed to create Python 3.12 virtual environment." }
    $CreatedVenv = $true
}

if ($CreatedVenv -or $InstallDependencies) {
    # constraints.txt pins the exact versions this release was tested with.
    & $VenvPy -m pip install -r (Join-Path $AppDir "requirements.txt") -c (Join-Path $AppDir "constraints.txt")
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }
}
$Cli = Join-Path $AppDir "scripts\provision_customer.py"
$Args = @(
    $Cli,
    "--workflow-key", $WorkflowKey,
    "--config", $ConfigPath,
    "--runtime-root", $RuntimeRoot,
    "--server-port", "$ServerPort",
    "--duplicate-handling", $DuplicateHandling
)
foreach ($Pattern in $BarcodePattern) {
    $Args += @("--barcode-pattern", $Pattern)
}
if ($Overwrite) { $Args += "--overwrite" }

Push-Location $AppDir
try {
    & $VenvPy @Args
    if ($LASTEXITCODE -ne 0) { throw "Customer provisioning failed." }
} finally {
    Pop-Location
}
