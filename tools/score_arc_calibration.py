"""Generate small public calibration table from private receipts."""

import argparse
import json
from pathlib import Path

from aimeth_arc.data import load_arc1_evaluation
from aimeth_arc.scoring import score_all


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(score_all(load_arc1_evaluation(args.archive), args.private_root, args.csv)))


if __name__ == "__main__":
    main()
