"""Historical data storage and almanac building."""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import pytz
from .models import DelayRecord


class DelayAlmanac:
    """Builds and stores historical baseline delays (the "almanac")."""

    def __init__(self, data_dir: str = "./data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.almanac_file = self.data_dir / "delay_almanac.json"
        self.records_file = self.data_dir / "delay_records.jsonl"
        self._load_almanac()

    def _load_almanac(self):
        """Load existing almanac or create empty."""
        if self.almanac_file.exists():
            with open(self.almanac_file, "r") as f:
                self.almanac = json.load(f)
        else:
            self.almanac = {}

    def add_record(self, record: DelayRecord):
        """Add a delay record and update baselines."""
        # Append to raw records
        with open(self.records_file, "a") as f:
            record_dict = {
                "route_id": record.route_id,
                "stop_id": record.stop_id,
                "stop_name": record.stop_name,
                "scheduled_time": record.scheduled_time.isoformat(),
                "predicted_time": record.predicted_time.isoformat(),
                "actual_time": record.actual_time.isoformat(),
                "scheduled_delay_sec": record.scheduled_delay_sec,
                "prediction_error_sec": record.prediction_error_sec,
                "day_of_week": record.day_of_week,
                "hour_of_day": record.hour_of_day,
                "weather_condition": record.weather_condition,
                "traffic_speed": record.traffic_speed,
                "ambient_traffic_level": record.ambient_traffic_level,
            }
            f.write(json.dumps(record_dict) + "\n")

        # Update almanac stats
        self._update_baseline(record)

    def _update_baseline(self, record: DelayRecord):
        """Update baseline statistics for route/time/day combinations."""
        key = f"{record.route_id}_{record.day_of_week:02d}_{record.hour_of_day:02d}"

        if key not in self.almanac:
            self.almanac[key] = {
                "route_id": record.route_id,
                "day_of_week": record.day_of_week,
                "hour_of_day": record.hour_of_day,
                "samples": 0,
                "avg_scheduled_delay_sec": 0.0,
                "avg_prediction_error_sec": 0.0,
                "p50_scheduled_delay_sec": 0.0,
                "p95_scheduled_delay_sec": 0.0,
                "last_updated": datetime.now(pytz.timezone("US/Central")).isoformat(),
            }

        entry = self.almanac[key]
        entry["samples"] += 1

        # Running average (simple version - in production use more sophisticated stats)
        n = entry["samples"]
        entry["avg_scheduled_delay_sec"] = (
            (entry["avg_scheduled_delay_sec"] * (n - 1) + record.scheduled_delay_sec) / n
        )
        entry["avg_prediction_error_sec"] = (
            (entry["avg_prediction_error_sec"] * (n - 1) + record.prediction_error_sec) / n
        )
        entry["last_updated"] = datetime.now(pytz.timezone("US/Central")).isoformat()

        self.save()

    def get_baseline(self, route_id: str, day_of_week: int, hour_of_day: int) -> Optional[Dict]:
        """Get baseline delay stats for a route at a specific day/hour."""
        key = f"{route_id}_{day_of_week:02d}_{hour_of_day:02d}"
        return self.almanac.get(key)

    def get_route_stats(self, route_id: str) -> List[Dict]:
        """Get all baseline stats for a route."""
        return [v for v in self.almanac.values() if v.get("route_id") == route_id]

    def save(self):
        """Persist almanac to disk."""
        with open(self.almanac_file, "w") as f:
            json.dump(self.almanac, f, indent=2)

    def get_recent_records(self, hours: int = 24) -> List[DelayRecord]:
        """Get recent delay records."""
        records = []
        cutoff = datetime.now(pytz.timezone("US/Central")) - timedelta(hours=hours)

        if not self.records_file.exists():
            return records

        with open(self.records_file, "r") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    actual = datetime.fromisoformat(data["actual_time"])
                    if actual > cutoff:
                        record = DelayRecord(
                            route_id=data["route_id"],
                            stop_id=data["stop_id"],
                            stop_name=data["stop_name"],
                            scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
                            predicted_time=datetime.fromisoformat(data["predicted_time"]),
                            actual_time=actual,
                            prediction_made_at=datetime.fromisoformat(data["actual_time"]),
                            scheduled_delay_sec=data["scheduled_delay_sec"],
                            prediction_error_sec=data["prediction_error_sec"],
                            day_of_week=data["day_of_week"],
                            hour_of_day=data["hour_of_day"],
                            weather_condition=data.get("weather_condition"),
                            traffic_speed=data.get("traffic_speed"),
                            ambient_traffic_level=data.get("ambient_traffic_level"),
                        )
                        records.append(record)
                except (json.JSONDecodeError, ValueError):
                    continue

        return records
