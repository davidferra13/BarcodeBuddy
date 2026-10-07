from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.acceptance import run_acceptance


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run BarcodeBuddy against customer-supplied acceptance samples."
    )
    parser.add_argument("--config", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--report-dir", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = run_acceptance(
        Path(args.config),
        Path(args.manifest),
        Path(args.report_dir),
    )
    print(json.dumps({
        "passed": report["passed"],
        "summary": report["summary"],
        "report_dir": str(Path(args.report_dir).resolve()),
    }, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
