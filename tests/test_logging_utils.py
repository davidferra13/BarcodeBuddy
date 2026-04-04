from __future__ import annotations

import gzip
import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from app.logging_utils import append_jsonl, iter_jsonl_log_files


class LoggingUtilsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tempdir.cleanup)
        self.root = Path(self._tempdir.name)
        self.log_file = self.root / "logs" / "processing_log.jsonl"

    def test_append_jsonl_rotates_prior_day_log_before_appending(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        prior_payload = {
            "timestamp": "2026-04-02T23:59:30+00:00",
            "processing_id": "proc-old",
            "stage": "processing",
            "status": "success",
        }
        self.log_file.write_text(json.dumps(prior_payload, ensure_ascii=True) + "\n", encoding="utf-8")
        prior_mtime = datetime(2026, 4, 2, 23, 59, 30, tzinfo=timezone.utc).timestamp()
        os.utime(self.log_file, (prior_mtime, prior_mtime))

        new_payload = {
            "timestamp": "2026-04-03T04:00:05+00:00",
            "processing_id": "proc-new",
            "stage": "output",
            "status": "success",
        }

        append_jsonl(self.log_file, new_payload)

        archive_path = self.log_file.with_name("processing_log.2026-04-02.jsonl.gz")
        self.assertTrue(archive_path.exists())
        with gzip.open(archive_path, "rt", encoding="utf-8") as f:
            archive_lines = f.read().splitlines()
        self.assertEqual(
            archive_lines,
            [json.dumps(prior_payload, ensure_ascii=True)],
        )
        self.assertEqual(
            self.log_file.read_text(encoding="utf-8").splitlines(),
            [json.dumps(new_payload, ensure_ascii=True)],
        )

    def test_iter_jsonl_log_files_returns_archives_before_active_log(self) -> None:
        self.log_file.parent.mkdir(parents=True, exist_ok=True)
        archive_one = self.log_file.with_name("processing_log.2026-04-01.jsonl")
        archive_two = self.log_file.with_name("processing_log.2026-04-02.jsonl.gz")
        archive_one.write_text("", encoding="utf-8")
        with gzip.open(archive_two, "wt", encoding="utf-8") as f:
            f.write("")
        self.log_file.write_text("", encoding="utf-8")

        files = iter_jsonl_log_files(self.log_file)

        self.assertEqual(files, [archive_one, archive_two, self.log_file])


if __name__ == "__main__":
    unittest.main()
