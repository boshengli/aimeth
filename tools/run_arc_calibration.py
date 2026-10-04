"""Calibrate ARC-AGI-1 using safe environment-injected public API keys."""

import argparse
import json
from pathlib import Path

from aimeth_arc.calibration import calibrate
from aimeth_arc.data import load_arc1_evaluation


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=("deepseek", "zhipu"), required=True)
    p.add_argument("--archive", type=Path, required=True)
    p.add_argument("--root", type=Path, required=True)
    p.add_argument("--max-requests", type=int)
    args = p.parse_args()
    tasks = load_arc1_evaluation(args.archive)
    print(json.dumps(calibrate(tasks, args.provider, args.root, args.max_requests)), flush=True)


if __name__ == "__main__":
    main()
