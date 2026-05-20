"""Core delay detection, analysis, and anomaly identification."""

import statistics
from datetime import datetime
from typing import List, Optional, Tuple
import pytz
from .models import (
    PredictedArrival, DelayRecord, DelayAnomaly, WeatherSnapshot, TrafficSegment
)
from .storage import DelayAlmanac


class DelayAnalyzer:
    """Analyzes bus delays and detects anomalies."""

    def __init__(self, almanac: DelayAlmanac):
        self.almanac = almanac
        self.chicago_tz = pytz.timezone("US/Central")

    def compute_delay_record(
        self,
        route_id: str,
        stop_id: str,
        stop_name: str,
        scheduled_time: datetime,
        predicted_time: datetime,
        actual_time: datetime,
        prediction_made_at: datetime,
        weather: Optional[WeatherSnapshot] = None,
        traffic_segments: Optional[List[TrafficSegment]] = None,
    ) -> DelayRecord:
        """
        Create a delay record from timing data.

        Args:
            scheduled_time: When the bus was supposed to arrive
            predicted_time: What the CTA API predicted
            actual_time: When it actually arrived
            prediction_made_at: When the prediction was made
            weather: Current weather snapshot
            traffic_segments: Traffic data for analysis
        """
        if not scheduled_time.tzinfo:
            scheduled_time = self.chicago_tz.localize(scheduled_time)
        if not predicted_time.tzinfo:
            predicted_time = self.chicago_tz.localize(predicted_time)
        if not actual_time.tzinfo:
            actual_time = self.chicago_tz.localize(actual_time)

        scheduled_delay_sec = int((actual_time - scheduled_time).total_seconds())
        prediction_error_sec = int((actual_time - predicted_time).total_seconds())

        day_of_week = actual_time.weekday()
        hour_of_day = actual_time.hour

        traffic_speed = None
        traffic_level = None
        if traffic_segments:
            speeds = [s.estimated_speed for s in traffic_segments if s.estimated_speed > 0]
            if speeds:
                traffic_speed = statistics.mean(speeds)
                traffic_level = _classify_traffic_level(traffic_speed)

        return DelayRecord(
            route_id=route_id,
            stop_id=stop_id,
            stop_name=stop_name,
            scheduled_time=scheduled_time,
            predicted_time=predicted_time,
            actual_time=actual_time,
            prediction_made_at=prediction_made_at,
            scheduled_delay_sec=scheduled_delay_sec,
            prediction_error_sec=prediction_error_sec,
            day_of_week=day_of_week,
            hour_of_day=hour_of_day,
            weather_condition=weather.condition if weather else None,
            traffic_speed=traffic_speed,
            ambient_traffic_level=traffic_level,
        )

    def detect_anomaly(
        self,
        record: DelayRecord,
        tolerance_sec: int = 120,
    ) -> Optional[DelayAnomaly]:
        """
        Detect if a delay is anomalous compared to baseline.

        Args:
            record: The delay record to analyze
            tolerance_sec: Seconds above baseline to trigger anomaly (default 2 min)

        Returns:
            DelayAnomaly if detected, None otherwise
        """
        baseline = self.almanac.get_baseline(
            record.route_id,
            record.day_of_week,
            record.hour_of_day
        )

        if not baseline or baseline["samples"] < 5:
            # Not enough baseline data
            return None

        expected_delay = baseline["avg_scheduled_delay_sec"]
        actual_delay = record.scheduled_delay_sec

        excess_delay = actual_delay - expected_delay
        if excess_delay <= tolerance_sec:
            return None

        # Anomaly detected
        magnitude = excess_delay / max(1, expected_delay) if expected_delay > 0 else 0

        factors = self._identify_factors(record, baseline)

        confidence = min(1.0, baseline["samples"] / 100)  # More samples = more confident

        return DelayAnomaly(
            route_id=record.route_id,
            detected_at=record.actual_time,
            delay_minutes=actual_delay // 60,
            expected_delay_minutes=int(expected_delay) // 60,
            anomaly_magnitude=magnitude,
            potential_factors=factors,
            confidence=confidence,
        )

    def _identify_factors(self, record: DelayRecord, baseline: dict) -> List[str]:
        """Identify potential factors contributing to the delay."""
        factors = []

        # Weather analysis
        if record.weather_condition:
            bad_weather = {"rainy", "snowy", "thunderstorm", "heavy rain"}
            if any(w.lower() in record.weather_condition.lower() for w in bad_weather):
                factors.append("bad_weather")

        # Traffic analysis
        if record.traffic_speed:
            if record.traffic_speed < 8:
                factors.append("heavy_traffic")
            elif record.traffic_speed < 15:
                factors.append("moderate_traffic")

        # Day/time patterns
        if record.day_of_week < 5:  # Weekday
            if record.hour_of_day in (7, 8, 9) or record.hour_of_day in (16, 17, 18):
                factors.append("rush_hour")

        # Prediction accuracy
        if abs(record.prediction_error_sec) > 300:
            factors.append("prediction_inaccuracy")

        if not factors:
            factors.append("unknown")

        return factors

    def forecast_delay(
        self,
        route_id: str,
        current_hour: int,
        day_of_week: int,
        traffic_condition: Optional[str] = None,
        weather_condition: Optional[str] = None,
    ) -> Tuple[float, str]:
        """
        Forecast expected delay for a specific route/time.

        Returns:
            Tuple of (expected_delay_minutes, confidence_level)
        """
        baseline = self.almanac.get_baseline(route_id, day_of_week, current_hour)

        if not baseline:
            return 0.0, "low"

        expected_delay_min = baseline["avg_scheduled_delay_sec"] / 60

        # Adjust based on traffic
        adjustment = 0.0
        if traffic_condition == "heavy":
            adjustment += 3.0
        elif traffic_condition == "moderate":
            adjustment += 1.0

        # Adjust based on weather
        if weather_condition and any(
            w in weather_condition.lower() for w in ["rain", "snow", "storm"]
        ):
            adjustment += 2.0

        expected_delay_min += adjustment

        confidence = "high" if baseline["samples"] >= 50 else "medium" if baseline["samples"] >= 10 else "low"

        return expected_delay_min, confidence

    def get_route_summary(self, route_id: str) -> dict:
        """Get summary statistics for a route."""
        stats = self.almanac.get_route_stats(route_id)

        if not stats:
            return {
                "route_id": route_id,
                "avg_delay_min": 0,
                "worst_hour": None,
                "best_hour": None,
                "samples": 0,
            }

        delays = [s["avg_scheduled_delay_sec"] for s in stats]
        avg_delay = statistics.mean(delays) / 60 if delays else 0

        worst = max(stats, key=lambda s: s["avg_scheduled_delay_sec"])
        best = min(stats, key=lambda s: s["avg_scheduled_delay_sec"])

        return {
            "route_id": route_id,
            "avg_delay_min": round(avg_delay, 1),
            "worst_hour": f"{worst['hour_of_day']:02d}:00 ({worst['avg_scheduled_delay_sec']/60:.1f} min)",
            "best_hour": f"{best['hour_of_day']:02d}:00 ({best['avg_scheduled_delay_sec']/60:.1f} min)",
            "samples": sum(s["samples"] for s in stats),
            "day_breakdown": self._day_breakdown(stats),
        }

    def _day_breakdown(self, stats: List[dict]) -> dict:
        """Break down stats by day of week."""
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        breakdown = {}

        for day_num in range(7):
            day_stats = [s for s in stats if s["day_of_week"] == day_num]
            if day_stats:
                avg = statistics.mean([s["avg_scheduled_delay_sec"] for s in day_stats]) / 60
                breakdown[days[day_num]] = round(avg, 1)

        return breakdown


def _classify_traffic_level(speed_mph: float) -> str:
    """Classify traffic level based on speed."""
    if speed_mph >= 20:
        return "light"
    elif speed_mph >= 12:
        return "moderate"
    else:
        return "heavy"
