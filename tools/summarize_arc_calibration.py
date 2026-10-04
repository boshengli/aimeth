"""Build the public, secret-free ARC P2 calibration evidence summary."""

import argparse
import json
from pathlib import Path

from aimeth_arc.summary import summarize


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--private-root", type=Path, required=True)
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--pilot-manifest", type=Path)
    p.add_argument("--audit", type=Path)
    p.add_argument("--sensitivity", type=Path)
    args = p.parse_args()
    s = summarize(args.private_root, args.csv, args.output, args.pilot_manifest,
                  args.audit, args.sensitivity)
    print(json.dumps({"complete": s["complete"], "providers": {
        key: {"settled": val["settled"], "sample_successes": val["sample_successes"]}
        for key, val in s["providers"].items()}}))


if __name__ == "__main__":
    main()
