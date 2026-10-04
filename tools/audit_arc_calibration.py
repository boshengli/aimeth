"""Run independent ledger/score consistency checks without publishing responses."""

import argparse
import json
from pathlib import Path

from aimeth_arc.audit import audit_calibration


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-root", type=Path, required=True)
    parser.add_argument("--csv", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    result = audit_calibration(args.private_root, args.csv,
                               require_complete=not args.allow_incomplete)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"complete": result["complete"], "output": str(args.output)}))


if __name__ == "__main__":
    main()
