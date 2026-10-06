from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.customer_provisioning import provision_customer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Provision a BarcodeBuddy customer workflow.")
    parser.add_argument("--workflow-key", required=True)
    parser.add_argument("--config", default="config.customer.json")
    parser.add_argument("--runtime-root", default="./data/customer")
    parser.add_argument("--server-port", type=int, default=8080)
    parser.add_argument("--barcode-pattern", action="append", default=[])
    parser.add_argument("--duplicate-handling", choices=("timestamp", "reject"), default="timestamp")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = provision_customer(
        config_path=Path(args.config),
        workflow_key=args.workflow_key,
        runtime_root=Path(args.runtime_root),
        server_port=args.server_port,
        barcode_value_patterns=tuple(args.barcode_pattern),
        duplicate_handling=args.duplicate_handling,
        overwrite=args.overwrite,
    )
    print(json.dumps({
        "config_path": str(result.config_path),
        "workflow": result.settings.workflow_key,
        "input_path": str(result.settings.input_path),
        "output_path": str(result.settings.output_path),
        "server_host": result.settings.server_host,
        "server_port": result.settings.server_port,
        "config_version": result.settings.config_version,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
