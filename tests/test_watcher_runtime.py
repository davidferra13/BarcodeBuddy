"""Exercise the actual ingestion process, native watcher and file-stability checks."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest

from app.barcode_generator import generate_code128
from app.config import DEFAULT_CONFIG
from app.runtime_lock import ServiceLock

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("poll_ms,stability_ms", [(100, 500), (500, 2000)])
def test_native_watcher_routes_a_completed_file_without_false_lock(tmp_path, poll_ms, stability_ms):
    config = dict(DEFAULT_CONFIG, workflow_key="watcher_runtime", barcode_types=["code128"],
                  barcode_value_patterns=[r"^PO-[0-9]+$"], duplicate_handling="reject",
                  poll_interval_ms=poll_ms, file_stability_delay_ms=stability_ms)
    for folder in ("input", "processing", "output", "rejected", "log"):
        path = tmp_path / folder
        path.mkdir()
        config[folder + "_path"] = str(path)
    config_path = tmp_path / "customer with spaces" / "config.json"
    config_path.parent.mkdir()
    config_path.write_text(json.dumps(config), encoding="utf-8")
    original = tmp_path / "original.pdf"
    image = generate_code128("PO-930001", scale=5).convert("RGB")
    try:
        image.save(original, "PDF")
    finally:
        image.close()
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("BB_") and key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX")}
    env["PYTHONUTF8"] = "1"
    log = tmp_path / "worker.log"
    with log.open("wb") as output:
        job = None
        arguments = [sys.executable, "-B", str(ROOT / "main.py"), "--config", str(config_path)]
        options = {}
        if os.name == "nt":
            # The venv launcher creates another Python process. Its worker joins
            # an inherited job before running main.py, so cleanup owns every child.
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
            kernel.CreateJobObjectW.restype = wintypes.HANDLE
            kernel.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
            kernel.TerminateJobObject.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            kernel.CloseHandle.restype = wintypes.BOOL
            job = kernel.CreateJobObjectW(None, None)
            assert job, ctypes.WinError(ctypes.get_last_error())
            os.set_handle_inheritable(job, True)
            startup = subprocess.STARTUPINFO()
            startup.lpAttributeList = {"handle_list": [job]}
            options["startupinfo"] = startup
            bootstrap = (
                "import ctypes,runpy,sys\n"
                "from ctypes import wintypes\n"
                "k=ctypes.WinDLL('kernel32',use_last_error=True)\n"
                "k.AssignProcessToJobObject.argtypes=[wintypes.HANDLE,wintypes.HANDLE]\n"
                "k.AssignProcessToJobObject.restype=wintypes.BOOL\n"
                "k.GetCurrentProcess.restype=wintypes.HANDLE\n"
                "k.CloseHandle.argtypes=[wintypes.HANDLE]\n"
                "h=int(sys.argv[1])\n"
                "if not k.AssignProcessToJobObject(h,k.GetCurrentProcess()):\n"
                " raise ctypes.WinError(ctypes.get_last_error())\n"
                "k.CloseHandle(h)\n"
                "sys.argv=sys.argv[2:]\n"
                "runpy.run_path(sys.argv[0],run_name='__main__')\n"
            )
            arguments = [sys.executable, "-B", "-c", bootstrap, str(job), *arguments[2:]]
        process = None
        try:
            process = subprocess.Popen(arguments, cwd=ROOT, env=env, **options,
                                       stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT)
            journal = tmp_path / "log" / "processing_log.jsonl"
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                if journal.exists() and '"startup"' in journal.read_text(encoding="utf-8"):
                    break
                assert process.poll() is None, log.read_text(encoding="utf-8", errors="replace")
                time.sleep(0.1)
            else:
                pytest.fail("Native ingestion did not start")
            # Drop the document after startup so the real watcher must revisit it.
            shutil.copyfile(original, tmp_path / "input" / "document.pdf")
            deadline = time.monotonic() + 25
            routed = None
            routed_bytes = None
            while time.monotonic() < deadline:
                routed = next((tmp_path / "output").rglob("PO-930001.pdf"), None)
                rejected = next((tmp_path / "rejected").glob("*.meta.json"), None)
                completed = False
                for line in journal.read_text(encoding="utf-8").splitlines():
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue  # The writer may still be appending its latest record.
                    if (event.get("original_filename") == "document.pdf"
                            and event.get("stage") == "output" and event.get("status") == "success"):
                        completed = True
                if rejected:
                    break
                if routed and completed:
                    try:
                        routed_bytes = routed.read_bytes()
                    except OSError:
                        pass  # Windows may still be releasing the completed file handle.
                    else:
                        break
                assert process.poll() is None, log.read_text(encoding="utf-8", errors="replace")
                time.sleep(0.1)
            records = journal.read_text(encoding="utf-8")
            assert routed is not None, "Completed file was not routed: " + records
            assert not list((tmp_path / "rejected").glob("*.pdf")), records
            assert routed_bytes is not None, "Output did not finish: " + records
            assert hashlib.sha256(routed_bytes).digest() == hashlib.sha256(original.read_bytes()).digest()
        finally:
            if job is not None:
                try:
                    assert kernel.TerminateJobObject(job, 0), ctypes.WinError(ctypes.get_last_error())
                finally:
                    kernel.CloseHandle(job)
            if process is not None:
                if job is None and process.poll() is None:
                    process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
            # Launcher exit alone does not prove ingestion released ownership.
            with ServiceLock(tmp_path / "log" / ".service.lock", metadata={"test_cleanup": True}):
                pass
