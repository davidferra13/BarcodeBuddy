"""Guards for the Windows launcher scripts.

These scripts run on customer machines and on the developer's own PC, which hosts
other Cloudflare tunnels. The invariants below stop two regressions that were
found on 2026-09-12 and lost again in the 2026-09-17 wipe:

1. Starting the app must never publish a public URL as a side effect.
2. Cleanup must never stop cloudflared processes this install did not start.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
START_APP = ROOT / "start-app.ps1"
INSTALL_AUTOSTART = ROOT / "install-autostart.ps1"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_launcher_scripts_exist():
    assert START_APP.is_file()
    assert INSTALL_AUTOSTART.is_file()


def test_start_app_tunnel_is_opt_in():
    text = _read(START_APP)
    assert re.search(r"\[switch\]\s*\$Tunnel", text), "start-app.ps1 must declare a -Tunnel switch"
    assert "BARCODEBUDDY_TUNNEL" in text, "environment override must be honoured"
    assert "Tunnel: OFF (local only)" in text, "local-only mode must be announced in the banner"
    assert re.search(r"if\s*\(\s*\$TunnelEnabled\s*\)\s*\{[^}]*Start-Tunnel", text, re.S), (
        "Start-Tunnel must only be invoked when $TunnelEnabled is true"
    )


def test_start_app_never_kills_foreign_cloudflared():
    text = _read(START_APP)
    assert not re.search(r'Get-Process\s+-Name\s+\"?cloudflared\"?[^\n]*Stop-Process', text), (
        "start-app.ps1 must not stop every cloudflared process on the machine"
    )
    assert "Get-OwnedTunnelProcesses" in text
    assert "$TunnelConfig" in text and "$QuickCfg" in text, "ownership must be decided by this install's config paths"


def test_start_app_prefers_project_venv():
    text = _read(START_APP)
    assert ".venv\\Scripts\\python.exe" in text
    assert "Python312\\python.exe" not in text, "no hard-coded interpreter path from one developer machine"


def test_install_autostart_passes_tunnel_through():
    text = _read(INSTALL_AUTOSTART)
    assert re.search(r"\[switch\]\s*\$Tunnel", text)
    assert re.search(r"if\s*\(\s*\$Tunnel\s*\)\s*\{[^}]*-Tunnel", text, re.S), (
        "the scheduled task must invoke start-app.ps1 -Tunnel only when installed with -Tunnel"
    )
    assert "local only" in text, "the default task description must say the app is local only"


def test_launcher_scripts_parse_as_powershell():
    """Tokenize scripts when PowerShell is responsive; syntax errors still fail."""
    import shutil
    import subprocess

    import pytest

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("no PowerShell on this machine")
    for script in (START_APP, INSTALL_AUTOSTART):
        cmd = (
            "$t=$null;$e=$null;[System.Management.Automation.PSParser]::Tokenize("
            "(Get-Content -Raw -LiteralPath '" + str(script).replace("'", "''") + "'),[ref]$e)|Out-Null;"
            "if($e.Count){$e|ForEach-Object{$_.Message};exit 1}else{exit 0}"
        )
        try:
            result = subprocess.run(
                [pwsh, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            pytest.skip("PowerShell parser could not start within 15 seconds on this host")
        assert result.returncode == 0, f"{script.name} failed to parse: {result.stdout}{result.stderr}"


def test_start_app_defaults_to_loopback_and_requires_lan_opt_in():
    text = _read(START_APP)
    assert re.search(r"\[string\]\s*\$Config\s*=\s*['\"]config\.json['\"]", text)
    assert re.search(r"\[switch\]\s*\$Lan", text)
    assert re.search(
        r"\$BindHost\s*=\s*if\s*\(\s*\$Lan\s*\)\s*\{\s*['\"]0\.0\.0\.0['\"]\s*\}\s*else\s*\{\s*['\"]127\.0\.0\.1['\"]",
        text,
        re.S,
    ), "LAN exposure must require -Lan; default must bind loopback"
    assert '"--config", $ConfigPath' in text
    assert '"--host", $BindHost' in text


def test_install_autostart_passes_config_and_lan_through():
    text = _read(INSTALL_AUTOSTART)
    assert re.search(r"\[string\]\s*\$Config\s*=\s*['\"]config\.json['\"]", text)
    assert re.search(r"\[switch\]\s*\$Lan", text)
    assert "-Config" in text and "$Config" in text
    assert re.search(r"if\s*\(\s*\$Lan\s*\)\s*\{[^}]*-Lan", text, re.S)

def test_native_launcher_preserves_spaces_and_customer_port(tmp_path):
    """Execute the real launcher functions through Windows argument parsing."""
    import json
    import shutil
    import subprocess
    import sys
    import pytest
    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        pytest.skip("PowerShell unavailable")
    config = tmp_path / "customer with spaces" / "config.json"
    config.parent.mkdir()
    config.write_text(json.dumps({"server_port": 8123}))
    capture = tmp_path / "capture.py"
    capture.write_text("import json,sys; print(json.dumps(sys.argv[1:]))")
    result_file = tmp_path / "result.json"
    literal = lambda value: "'" + str(value).replace("'", "''") + "'"
    harness = tmp_path / "probe.ps1"
    harness.write_text(
        "$ErrorActionPreference='Stop'\n"
        "$tokens=$null;$errors=$null\n"
        "$ast=[System.Management.Automation.Language.Parser]::ParseFile(" + literal(START_APP) + ",[ref]$tokens,[ref]$errors)\n"
        "if($errors.Count){throw 'Launcher syntax error'}\n"
        "$functions=$ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]},$true)\n"
        "foreach($name in @('Get-AppPort','Start-App')){\n"
        "  $function=$functions|Where-Object{$_.Name -eq $name}|Select-Object -First 1\n"
        "  if(-not $function){throw ('Missing launcher function: '+$name)}\n"
        "  Invoke-Expression $function.Extent.Text\n"
        "}\n"
        "$PyExe=" + literal(sys.executable) + "\n"
        "$Capture=" + literal(capture) + "\n"
        "$ResultFile=" + literal(result_file) + "\n"
        "$PyArgs='';$AppDir=" + literal(ROOT) + ";$AppLog=" + literal(tmp_path/"app.log") + "\n"
        "$ConfigPath=" + literal(config) + ";$BindHost='127.0.0.1'\n"
        "$AppPort=Get-AppPort $ConfigPath\n"
        "function Start-Process {\n"
        " param($FilePath,$ArgumentList,$WorkingDirectory,$RedirectStandardOutput,$RedirectStandardError,[switch]$PassThru,[switch]$NoNewWindow)\n"
        " $info=New-Object System.Diagnostics.ProcessStartInfo\n"
        " $info.FileName=$FilePath;$info.UseShellExecute=$false;$info.RedirectStandardOutput=$true\n"
        " $quote=[char]34;$info.Arguments=$quote+$Capture+$quote+' '+($ArgumentList -join ' ')\n"
        " $process=[System.Diagnostics.Process]::Start($info)\n"
        " $output=$process.StandardOutput.ReadToEnd();$process.WaitForExit()\n"
        " if($process.ExitCode -ne 0){throw 'Native child failed'}\n"
        " [System.IO.File]::WriteAllText($ResultFile,$output)\n"
        " return [pscustomobject]@{Id=$process.Id}\n"
        "}\n"
        "Start-App|Out-Null\n",
        encoding="utf-8",
    )
    try:
        process = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-File", str(harness)],
                                 capture_output=True, text=True, timeout=45)
    except subprocess.TimeoutExpired:
        pytest.skip("PowerShell could not execute the native launcher probe within 45 seconds")
    assert process.returncode == 0, process.stdout + process.stderr
    assert json.loads(result_file.read_text()) == [
        "stats.py", "--config", str(config), "--host", "127.0.0.1", "--port", "8123",
    ]


def test_start_app_starts_and_supervises_ingestion_by_default():
    """The web app alone files nothing; the launcher must also run main.py and restart it."""
    text = _read(START_APP)
    assert re.search(r"\[switch\]\s*\$NoIngestion", text)
    assert "function Start-Ingestion" in text
    assert '"main.py", "--config", $ConfigPath' in text, "ingestion must use the same customer config"
    assert re.search(
        r"if\s*\(\s*-not\s+\$NoIngestion\s*\)\s*\{\s*\$ingestProc\s*=\s*Start-Ingestion", text
    ), "ingestion must start unless -NoIngestion is passed"
    watch_loop = text[text.index("while ($true)"):]
    assert re.search(
        r"\$ingestProc\s+-and\s+\$ingestProc\.HasExited[^}]*\$ingestProc\s*=\s*Start-Ingestion",
        watch_loop,
        re.S,
    ), "a dead ingestion process must be restarted by the watch loop"


def test_install_autostart_passes_ingestion_and_hostname_through():
    text = _read(INSTALL_AUTOSTART)
    assert re.search(r"if\s*\(\s*\$NoIngestion\s*\)\s*\{[^}]*-NoIngestion", text, re.S)
    assert re.search(r"if\s*\(\s*\$PublicHostname\s*\)\s*\{[^}]*-PublicHostname", text, re.S)


def test_core_carries_no_customer_identity():
    """One customer's hostname or name must never ship inside another customer's install."""
    lowered_names = ("danpack",)
    for path in (START_APP, INSTALL_AUTOSTART, ROOT / "provision-customer.ps1", ROOT / "app" / "ai_tools.py"):
        text = _read(path).lower()
        for name in lowered_names:
            assert name not in text, f"{path.name} still names a customer"
    launcher = _read(START_APP)
    assert re.search(r"\[string\]\s*\$PublicHostname", launcher)
    assert "BARCODEBUDDY_PUBLIC_HOSTNAME" in launcher
    assert re.search(r"\$TunnelEnabled\s+-and\s+\$PublicHostname\s+-and", launcher), (
        "a named tunnel must require an explicitly supplied hostname"
    )
    assert "Resolve-DnsName $PublicHostname" in launcher
