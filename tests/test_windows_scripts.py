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
    assert re.search(r"param\s*\(\s*\[switch\]\s*\$Tunnel", text), "start-app.ps1 must declare a -Tunnel switch"
    assert "BARCODEBUDDY_TUNNEL" in text, "environment override must be honoured"
    assert "Tunnel: OFF (local only)" in text, "local-only mode must be announced in the banner"
    # The tunnel may only be started inside a guard on $TunnelEnabled.
    assert re.search(r"if\s*\(\s*\$TunnelEnabled\s*\)\s*\{[^}]*Start-Tunnel", text, re.S), (
        "Start-Tunnel must only be invoked when $TunnelEnabled is true"
    )


def test_start_app_never_kills_foreign_cloudflared():
    text = _read(START_APP)
    # The exact regression: a blanket kill of every cloudflared on the machine.
    assert not re.search(r"Get-Process\s+-Name\s+\"?cloudflared\"?[^\n]*Stop-Process", text), (
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
    assert re.search(r"param\s*\(\s*\[switch\]\s*\$Tunnel", text)
    assert re.search(r"if\s*\(\s*\$Tunnel\s*\)\s*\{[^}]*-Tunnel", text, re.S), (
        "the scheduled task must invoke start-app.ps1 -Tunnel only when installed with -Tunnel"
    )
    assert "local only" in text, "the default task description must say the app is local only"


def test_launcher_scripts_parse_as_powershell():
    """Every script must at least tokenize. Uses PowerShell's own parser when available."""
    import shutil
    import subprocess

    pwsh = shutil.which("pwsh") or shutil.which("powershell")
    if not pwsh:
        import pytest

        pytest.skip("no PowerShell on this machine")
    for script in (START_APP, INSTALL_AUTOSTART):
        cmd = (
            "$t=$null;$e=$null;[System.Management.Automation.PSParser]::Tokenize("
            "(Get-Content -Raw -LiteralPath '" + str(script).replace("'", "''") + "'),[ref]$e)|Out-Null;"
            "if($e.Count){$e|ForEach-Object{$_.Message};exit 1}else{exit 0}"
        )
        result = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command", cmd], capture_output=True, text=True, timeout=60)
        assert result.returncode == 0, f"{script.name} failed to parse: {result.stdout}{result.stderr}"
