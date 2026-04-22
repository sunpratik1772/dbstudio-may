#!/usr/bin/env python3
"""dbSherpa CLI — run a workflow DAG from the command line."""
import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

# Allow running as `python main.py` from the backend/ directory
sys.path.insert(0, str(Path(__file__).parent))

from engine import load_and_run


def main() -> None:
    parser = argparse.ArgumentParser(description="dbSherpa workflow runner")
    parser.add_argument("dag", help="Path to DAG JSON file")
    parser.add_argument(
        "--payload",
        default='{"trader_id":"T001","book":"FX-SPOT","alert_date":"2024-01-15","currency_pair":"EUR/USD","alert_id":"ALT-001"}',
        help="Alert payload as JSON string",
    )
    parser.add_argument("--payload-file", help="Path to JSON file containing alert payload")
    args = parser.parse_args()

    if args.payload_file:
        with open(args.payload_file) as f:
            payload = json.load(f)
    else:
        payload = json.loads(args.payload)

    ctx = load_and_run(args.dag, payload)

    print("\n" + "=" * 60)
    print("  dbSherpa Run Complete")
    print("=" * 60)
    print(f"  Disposition : {ctx.disposition}")
    print(f"  Flag count  : {ctx.get('flag_count', 0)}")
    print(f"  Report path : {ctx.report_path}")
    print(f"  Datasets    : {list(ctx.datasets.keys())}")
    print(f"  Sections    : {list(ctx.sections.keys())}")
    print("=" * 60)


if __name__ == "__main__":
    main()
