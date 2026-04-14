#!/usr/bin/env python3
"""
Sovereign Solar Sales Intelligence Engine — CLI entry point.

Usage:
    python main.py                          # report from default sample data
    python main.py --data path/to/calls.json
    python main.py --json                   # output structured JSON instead of text
"""

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from src.sales_intelligence import load_calls_from_json, generate_report, generate_report_dict

DEFAULT_DATA = Path(__file__).parent / "data" / "sample_calls.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Training Intelligence Report from solar sales call data."
    )
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_DATA,
        help="Path to a JSON file containing sales call records.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output structured JSON instead of the formatted text report.",
    )
    parser.add_argument(
        "--week-of",
        type=date.fromisoformat,
        default=None,
        metavar="YYYY-MM-DD",
        help="The Monday of the reporting week (default: most recent Monday).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if not args.data.exists():
        print(f"Error: data file not found: {args.data}", file=sys.stderr)
        sys.exit(1)

    calls = load_calls_from_json(args.data)

    if args.as_json:
        report = generate_report_dict(calls, week_of=args.week_of)
        print(json.dumps(report, indent=2))
    else:
        report = generate_report(calls, week_of=args.week_of)
        print(report)


if __name__ == "__main__":
    main()
