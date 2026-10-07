from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.release_backup import create_backup, verify_backup, verified_extract


def main():
    parser = argparse.ArgumentParser(description="Create, verify or safely extract a BarcodeBuddy backup.")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--config", required=True)
    create.add_argument("--archive", required=True)
    create.add_argument("--database")
    create.add_argument("--include-documents", action="store_true")
    verify = sub.add_parser("verify")
    verify.add_argument("--archive", required=True)
    restore = sub.add_parser("extract")
    restore.add_argument("--archive", required=True)
    restore.add_argument("--destination", required=True)
    args = parser.parse_args()
    try:
        if args.command == "create":
            result = create_backup(Path(args.config), Path(args.archive),
                database_path=Path(args.database) if args.database else None,
                include_documents=args.include_documents)
        elif args.command == "verify":
            result = verify_backup(Path(args.archive))
        else:
            result = verified_extract(Path(args.archive), Path(args.destination))
        print(json.dumps({key: value for key, value in result.items() if key != "manifest"}, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"verified": False, "error": str(error)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
