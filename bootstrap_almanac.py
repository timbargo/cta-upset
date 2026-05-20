"""
Bootstrap your almanac with 3-6 months of historic CTA data in minutes.

Usage:
    python bootstrap_almanac.py                  # Load 3 months (default)
    python bootstrap_almanac.py --months 6      # Load 6 months
    python bootstrap_almanac.py --months 1      # Load 1 month (quick test)

This downloads from the Active Transportation Alliance archive:
https://github.com/ActiveTransportationAlliance/cta-bus-archive
"""

import argparse
import sys
from datetime import datetime
import pytz

from cta_upset.historic_loader import bootstrap_almanac_from_archive


def main():
    parser = argparse.ArgumentParser(
        description="Bootstrap CTA Upset almanac with historic data"
    )
    parser.add_argument(
        "--months",
        type=int,
        default=3,
        help="How many months of historic data to load (default: 3)",
    )

    args = parser.parse_args()

    if args.months < 1 or args.months > 60:
        print("❌ Error: months must be between 1 and 60")
        sys.exit(1)

    try:
        almanac = bootstrap_almanac_from_archive(months_back=args.months)

        print(f"\n✅ Success! Almanac bootstrapped.")
        print(f"   Location: ./data/delay_almanac.json")
        print(f"   Records: ./data/delay_records.jsonl")
        print(f"\n   Next steps:")
        print(f"     python -m cta_upset.main summary 56")
        print(f"     python -m cta_upset.main forecast 56 0 9")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
