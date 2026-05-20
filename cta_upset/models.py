from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List


@dataclass
class BusStop:
    """Represents a CTA bus stop."""
    stop_id: str
    stop_name: str
    lat: float
    lon: float


@dataclass
class BusRoute:
    """Represents a CTA bus route."""
    route_id: str
    route_name: str
    route_color: Optional[str] = None


@dataclass
class ScheduledStop:
    """Expected/scheduled arrival at a stop."""
    stop_id: str
    stop_name: str
    scheduled_time: datetime
    distance_from_start: float


@dataclass
class PredictedArrival:
    """CTA's predicted arrival time (from API)."""
    stop_id: str
    stop_name: str
    predicted_time: datetime
    vehicle_id: str
    route_id: str
    timestamp: datetime  # when we got this prediction


@dataclass
class ActualArrival:
    """Recorded actual arrival at a stop."""
    stop_id: str
    stop_name: str
    actual_time: datetime
    vehicle_id: str
    route_id: str


@dataclass
class DelayRecord:
    """Records the gap between predicted and actual arrival."""
    route_id: str
    stop_id: str
    stop_name: str
    scheduled_time: datetime
    predicted_time: datetime
    actual_time: datetime
    prediction_made_at: datetime

    # Delay metrics
    scheduled_delay_sec: int  # actual - scheduled
    prediction_error_sec: int  # actual - predicted

    # Context
    day_of_week: int  # 0=Monday, 6=Sunday
    hour_of_day: int
    weather_condition: Optional[str] = None
    traffic_speed: Optional[float] = None  # mph on route
    ambient_traffic_level: Optional[str] = None  # "light", "moderate", "heavy"


@dataclass
class TrafficSegment:
    """Chicago Traffic Tracker data for a street segment."""
    segment_id: str
    street_name: str
    direction: str
    estimated_speed: float  # mph
    timestamp: datetime
    traffic_level: str  # "free flow", "congested", etc


@dataclass
class WeatherSnapshot:
    """Weather at a point in time."""
    timestamp: datetime
    temperature: float  # Celsius
    condition: str  # "clear", "rainy", "snowy", etc
    precipitation_mm: float
    wind_speed: float  # m/s


@dataclass
class DelayAnomaly:
    """Identified anomaly in bus delays."""
    route_id: str
    detected_at: datetime
    delay_minutes: int
    expected_delay_minutes: int
    anomaly_magnitude: float  # how far from baseline
    potential_factors: List[str] = field(default_factory=list)
    confidence: float = 0.0  # 0-1, how confident in this anomaly
