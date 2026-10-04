"""Export post-hoc length-truncation sensitivity without private response text."""

import argparse
import json
from pathlib import Path

from aimeth_arc.sensitivity import summarize_truncation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", required=True, type=Path)
    parser.add_argument("--pilot", required=True, type=Path)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    args = parser.parse_args()
    result = summarize_truncation(args.scores, args.pilot, args.csv,
                                  args.output_json, args.output_csv)
    print(json.dumps({"providers": result["providers"],
                      "selected_pilot_length_majority_failure_count":
                      result["selected_pilot_length_majority_failure_count"]}))


if __name__ == "__main__":
    main()
