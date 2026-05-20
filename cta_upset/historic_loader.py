"""
Load historic CTA data from Active Transportation Alliance archive.

Archive: https://github.com/ActiveTransportationAlliance/cta-bus-archive
S3 Data: https://s3.us-east-2.amazonaws.com/chibus/

This lets you bootstrap 3-6 months of almanac data in minutes instead of waiting weeks.
"""

import os
import csv
import gzip
import lzma
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
from pathlib import Path
import requests
import pytz

from .models import DelayRecord
from .storage import DelayAlmanac


class CTAHistoricDataLoader:
    """Downloads and processes historic CTA vehicle position data from S3."""

    BASE_S3_URL = "https://s3.us-east-2.amazonaws.com/chibus"
    CHICAGO_TZ = pytz.timezone("US/Central")

    def __init__(self, cache_dir: str = "./data/historic_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_date(self, date: datetime) -> bool:
        """
        Download and parse data for a single date.

        Returns True if successful, False otherwise.
        """
        date_str = date.strftime("%Y-%m-%d")
        print(f"\n📥 Downloading {date_str}...")

        # Three files per day: patterns, pattern_stops, positions
        files = ["patterns", "pattern_stops", "positions"]
        downloaded = []

        for filename in files:
            url = (
                f"{self.BASE_S3_URL}/{date.year:04d}/{date.month:02d}/"
                f"{date_str}-{filename}.csv.xz"
            )

            local_path = self.cache_dir / f"{date_str}-{filename}.csv.xz"

            if local_path.exists():
                print(f"  ✓ {filename} (cached)")
                downloaded.append(local_path)
                continue

            try:
                response = requests.get(url, timeout=30)
                response.raise_for_status()
                with open(local_path, "wb") as f:
                    f.write(response.content)
                print(f"  ✓ {filename}")
                downloaded.append(local_path)
            except requests.RequestException as e:
                print(f"  ✗ {filename} - {e}")
                return False

        return len(downloaded) == 3

    def extract_delays_from_positions(
        self,
        positions_file: Path,
        patterns_file: Path,
        pattern_stops_file: Path,
    ) -> List[DelayRecord]:
        """
        Extract delay records from position data.

        This reconstructs actual stop arrivals by tracking when vehicles
        pass stops, comparing to predicted times in the data.
        """
        delays = []

        # Load pattern/stop metadata
        patterns = self._load_patterns(patterns_file)
        pattern_stops = self._load_pattern_stops(pattern_stops_file)

        # Parse positions to find stop visits
        print("  Analyzing vehicle positions...")

        with lzma.open(positions_file, "rt") as f:
            reader = csv.DictReader(f)

            prev_positions = {}  # Track previous position of each vehicle

            for row in reader:
                try:
                    vehicle_id = row.get("vid")
                    route_id = row.get("rt")
                    stop_id = row.get("stpid")
                    predicted_time = row.get("prdtm")
                    timestamp = row.get("tmstmp")

                    if not all([vehicle_id, route_id, stop_id, timestamp]):
                        continue

                    # When a vehicle appears at a stop, that's an arrival
                    key = (vehicle_id, route_id, stop_id)

                    if key in prev_positions:
                        prev_stop, prev_time = prev_positions[key]
                        if prev_stop != stop_id:
                            # Vehicle moved to new stop - arrival event
                            delay_record = self._create_delay_record(
                                route_id=route_id,
                                stop_id=stop_id,
                                timestamp=timestamp,
                                predicted_time=predicted_time,
                                pattern_stops=pattern_stops,
                            )
                            if delay_record:
                                delays.append(delay_record)

                    prev_positions[key] = (stop_id, timestamp)

                except (KeyError, ValueError):
                    continue

        print(f"  Found {len(delays)} potential delay records")
        return delays

    def _load_patterns(self, patterns_file: Path) -> dict:
        """Load route pattern metadata."""
        patterns = {}
        try:
            with lzma.open(patterns_file, "rt") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pattern_id = row.get("pid")
                    if pattern_id:
                        patterns[pattern_id] = row
        except Exception as e:
            print(f"  Warning: Could not load patterns: {e}")
        return patterns

    def _load_pattern_stops(self, pattern_stops_file: Path) -> dict:
        """Load stop sequence and scheduled times for patterns."""
        pattern_stops = {}
        try:
            with lzma.open(pattern_stops_file, "rt") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    pattern_id = row.get("pid")
                    stop_id = row.get("stpid")
                    sequence = row.get("seq")

                    if pattern_id and stop_id:
                        if pattern_id not in pattern_stops:
                            pattern_stops[pattern_id] = {}
                        pattern_stops[pattern_id][stop_id] = {
                            "sequence": sequence,
                            "row": row,
                        }
        except Exception as e:
            print(f"  Warning: Could not load pattern stops: {e}")
        return pattern_stops

    def _create_delay_record(
        self,
        route_id: str,
        stop_id: str,
        timestamp: str,
        predicted_time: Optional[str],
        pattern_stops: dict,
    ) -> Optional[DelayRecord]:
        """
        Attempt to create a delay record from position data.

        Limited accuracy - position data shows vehicle locations, not exact
        stop arrivals. This is approximate.
        """
        try:
            actual_time = datetime.fromisoformat(timestamp)
            if not actual_time.tzinfo:
                actual_time = self.CHICAGO_TZ.localize(actual_time)

            # Without schedule data easily accessible, we can't compute
            # scheduled vs actual. This is a limitation of the position data.
            # In practice, we'd need to cross-reference with GTFS schedule data.

            if not predicted_time:
                return None

            pred_time = datetime.fromisoformat(predicted_time)
            if not pred_time.tzinfo:
                pred_time = self.CHICAGO_TZ.localize(pred_time)

            # Approximate: use predicted time as proxy for scheduled
            # (CTA predictions are usually within a few minutes)
            record = DelayRecord(
                route_id=route_id,
                stop_id=stop_id,
                stop_name=f"Stop {stop_id}",
                scheduled_time=pred_time,  # Approximation
                predicted_time=pred_time,
                actual_time=actual_time,
                prediction_made_at=actual_time,
                scheduled_delay_sec=int((actual_time - pred_time).total_seconds()),
                prediction_error_sec=0,  # Can't calculate without true schedule
                day_of_week=actual_time.weekday(),
                hour_of_day=actual_time.hour,
            )

            return record

        except (ValueError, AttributeError):
            return None

    def load_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        almanac: DelayAlmanac,
    ):
        """
        Download and load data for a date range into almanac.

        Args:
            start_date: First date to load
            end_date: Last date to load (inclusive)
            almanac: DelayAlmanac to populate
        """
        current = start_date
        total_records = 0

        while current <= end_date:
            if not self.download_date(current):
                print(f"  ⚠️  Failed to download {current.date()}, skipping")
                current += timedelta(days=1)
                continue

            # Parse the downloaded files
            date_str = current.strftime("%Y-%m-%d")
            positions_file = self.cache_dir / f"{date_str}-positions.csv.xz"
            patterns_file = self.cache_dir / f"{date_str}-patterns.csv.xz"
            pattern_stops_file = self.cache_dir / f"{date_str}-pattern_stops.csv.xz"

            print(f"  Parsing {date_str}...")

            delays = self.extract_delays_from_positions(
                positions_file, patterns_file, pattern_stops_file
            )

            for record in delays:
                almanac.add_record(record)

            total_records += len(delays)

            current += timedelta(days=1)

        print(
            f"\n✅ Loaded {total_records} delay records from {start_date.date()} to {end_date.date()}"
        )
        print(f"   Almanac now has {len(almanac.almanac)} route/day/hour combinations")


def bootstrap_almanac_from_archive(
    months_back: int = 3,
) -> DelayAlmanac:
    """
    Quick start: Bootstrap almanac with 3 months of historic data (default).

    Args:
        months_back: How many months of history to download (default 3)

    Returns:
        Populated DelayAlmanac
    """
    almanac = DelayAlmanac()
    loader = CTAHistoricDataLoader()

    chicago_tz = pytz.timezone("US/Central")
    end_date = datetime.now(chicago_tz)

    # Go back N months
    year = end_date.year
    month = end_date.month - months_back

    while month <= 0:
        year -= 1
        month += 12

    start_date = datetime(year, month, 1, tzinfo=chicago_tz)

    print(f"\n🚌 CTA Upset: Bootstrapping Almanac")
    print(f"   Downloading {months_back} months of historic data...")
    print(f"   Date range: {start_date.date()} to {end_date.date()}\n")

    loader.load_date_range(start_date, end_date, almanac)

    return almanac
