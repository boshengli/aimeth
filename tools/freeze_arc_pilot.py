"""Create the immutable ARC P2 pilot manifest after complete calibration."""

import argparse
import json
from pathlib import Path

from aimeth_arc.pilot import freeze_pilot


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    print(json.dumps(freeze_pilot(args.csv, args.archive, args.output)))


if __name__ == "__main__":
    main()
