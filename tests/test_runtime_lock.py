from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from app.runtime_lock import ServiceLock


class ServiceLockTests(unittest.TestCase):
    def test_second_process_cannot_acquire_same_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_file = Path(temp_dir) / "service.lock"
            with ServiceLock(lock_file, metadata={"workflow": "test", "pid": 1}):
                script = """
from pathlib import Path
import sys
from app.runtime_lock import ServiceLock, ServiceLockError

lock_file = Path(sys.argv[1])
try:
    with ServiceLock(lock_file, metadata={"workflow": "child", "pid": 2}):
        raise SystemExit(0)
except ServiceLockError:
    raise SystemExit(17)
"""
                result = subprocess.run(
                    [sys.executable, "-c", script, str(lock_file)],
                    capture_output=True,
                    text=True,
                    check=False,
                )

            self.assertEqual(result.returncode, 17, msg=result.stderr)

    def test_lock_can_be_reacquired_after_release(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_file = Path(temp_dir) / "service.lock"

            with ServiceLock(lock_file, metadata={"workflow": "first", "pid": 1}):
                pass

            with ServiceLock(lock_file, metadata={"workflow": "second", "pid": 2}):
                pass

            payload = json.loads(lock_file.read_text(encoding="utf-8"))

            self.assertEqual(payload["workflow"], "second")
            self.assertEqual(payload["pid"], 2)


if __name__ == "__main__":
    unittest.main()
