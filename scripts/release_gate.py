from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.release_gate import run_release_gate


def main():
    parser = argparse.ArgumentParser(description="Verify a BarcodeBuddy release using fresh native checks.")
    parser.add_argument("--report-dir", required=True)
    parser.add_argument("--acquisition-repo")
    parser.add_argument("--customer-config")
    parser.add_argument("--customer-manifest")
    parser.add_argument("--timeout-seconds", type=float, default=600)
    parser.add_argument("--product-only", action="store_true",
        help="Release the installable product without requiring the Built To Own repository gate. "
             "The receipt records release_kind=product-only.")
    args = parser.parse_args()
    try:
        receipt = run_release_gate(ROOT, Path(args.report_dir),
            acquisition_repo=Path(args.acquisition_repo) if args.acquisition_repo else None,
            customer_config=Path(args.customer_config) if args.customer_config else None,
            customer_manifest=Path(args.customer_manifest) if args.customer_manifest else None,
            timeout_s=args.timeout_seconds, product_only=args.product_only)
    except (OSError, ValueError) as error:
        print(json.dumps({"ready": False, "error": str(error)}), file=sys.stderr)
        return 1
    print(json.dumps({"ready": receipt["ready"], "failed_gates": receipt["failed_gates"],
                     "receipt": str(Path(args.report_dir).resolve()/"release-receipt.json")}, indent=2))
    return 0 if receipt["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
