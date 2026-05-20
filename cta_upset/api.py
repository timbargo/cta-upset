"""Integrations with external APIs: CTA, Chicago Traffic Tracker, Weather."""

import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import requests
import pytz
from .models import (
    PredictedArrival, BusRoute, BusStop, TrafficSegment, WeatherSnapshot
)


class CTABusTrackerAPI:
    """CTA Bus Tracker API integration."""

    BASE_URL = "http://www.ctabustracker.com/api/1.0"

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def get_predictions(self, stop_id: str, route_id: Optional[str] = None) -> List[PredictedArrival]:
        """
        Get predicted arrivals for a stop.

        Args:
            stop_id: CTA stop ID
            route_id: Optional route filter

        Returns:
            List of predicted arrivals
        """
        params = {
            "key": self.api_key,
            "stpid": stop_id,
            "format": "json"
        }
        if route_id:
            params["rt"] = route_id

        try:
            resp = self.session.get(f"{self.BASE_URL}/predictions.json", params=params)
            resp.raise_for_status()
            data = resp.json()

            predictions = []
            if "prd" in data:
                preds = data["prd"]
                if not isinstance(preds, list):
                    preds = [preds]

                for pred in preds:
                    predicted_time = datetime.fromisoformat(pred["prdtm"])
                    predicted_time = pytz.timezone("US/Central").localize(predicted_time)

                    predictions.append(PredictedArrival(
                        stop_id=stop_id,
                        stop_name=pred.get("stpNm", "Unknown"),
                        predicted_time=predicted_time,
                        vehicle_id=pred.get("vid", ""),
                        route_id=pred.get("rt", ""),
                        timestamp=datetime.now(pytz.timezone("US/Central"))
                    ))
            return predictions
        except requests.RequestException as e:
            print(f"CTA API error: {e}")
            return []

    def get_routes(self) -> List[BusRoute]:
        """Get all available bus routes."""
        params = {
            "key": self.api_key,
            "format": "json"
        }
        try:
            resp = self.session.get(f"{self.BASE_URL}/routes.json", params=params)
            resp.raise_for_status()
            data = resp.json()

            routes = []
            if "routes" in data:
                for route in data["routes"]:
                    routes.append(BusRoute(
                        route_id=route.get("rt", ""),
                        route_name=route.get("rtnm", ""),
                        route_color=route.get("rtclr")
                    ))
            return routes
        except requests.RequestException as e:
            print(f"CTA routes API error: {e}")
            return []

    def get_stops(self, route_id: str) -> List[BusStop]:
        """Get all stops for a route."""
        params = {
            "key": self.api_key,
            "rt": route_id,
            "format": "json"
        }
        try:
            resp = self.session.get(f"{self.BASE_URL}/stops.json", params=params)
            resp.raise_for_status()
            data = resp.json()

            stops = []
            if "stops" in data:
                for stop in data["stops"]:
                    stops.append(BusStop(
                        stop_id=stop.get("stpid", ""),
                        stop_name=stop.get("stpNm", ""),
                        lat=float(stop.get("lat", 0)),
                        lon=float(stop.get("lon", 0))
                    ))
            return stops
        except requests.RequestException as e:
            print(f"CTA stops API error: {e}")
            return []


class ChicagoTrafficTrackerAPI:
    """Chicago Traffic Tracker API (via Socrata SODA)."""

    BASE_URL = "https://data.cityofchicago.org/api/views/n4j6-wkkf/rows.json"

    def get_current_segments(self, limit: int = 100) -> List[TrafficSegment]:
        """
        Get current traffic data for Chicago arterial streets.

        Returns:
            List of traffic segments with estimated speeds
        """
        params = {
            "$limit": limit,
            "$order": "updated_at DESC"
        }
        try:
            resp = requests.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            segments = []
            for row in data.get("data", []):
                if len(row) >= 8:
                    try:
                        segments.append(TrafficSegment(
                            segment_id=row[8] or "",
                            street_name=row[9] or "Unknown",
                            direction=row[10] or "Unknown",
                            estimated_speed=float(row[11] or 0),
                            timestamp=datetime.fromisoformat(row[12]) if row[12] else datetime.now(),
                            traffic_level=_speed_to_level(float(row[11] or 0))
                        ))
                    except (ValueError, IndexError, TypeError):
                        continue
            return segments
        except requests.RequestException as e:
            print(f"Chicago Traffic Tracker API error: {e}")
            return []

    def get_segments_by_street(self, street_name: str) -> List[TrafficSegment]:
        """Get traffic segments for a specific street."""
        params = {
            "$where": f"street_name like '%{street_name}%'",
            "$limit": 50
        }
        try:
            resp = requests.get(self.BASE_URL, params=params)
            resp.raise_for_status()
            data = resp.json()

            segments = []
            for row in data.get("data", []):
                if len(row) >= 8:
                    try:
                        segments.append(TrafficSegment(
                            segment_id=row[8] or "",
                            street_name=row[9] or "Unknown",
                            direction=row[10] or "Unknown",
                            estimated_speed=float(row[11] or 0),
                            timestamp=datetime.fromisoformat(row[12]) if row[12] else datetime.now(),
                            traffic_level=_speed_to_level(float(row[11] or 0))
                        ))
                    except (ValueError, IndexError, TypeError):
                        continue
            return segments
        except requests.RequestException as e:
            print(f"Traffic by street API error: {e}")
            return []


class OpenWeatherMapAPI:
    """OpenWeatherMap API integration."""

    BASE_URL = "https://api.openweathermap.org/data/2.5"
    CHICAGO_LAT = 41.8781
    CHICAGO_LON = -87.6298

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_current_weather(self) -> Optional[WeatherSnapshot]:
        """Get current weather in Chicago."""
        params = {
            "lat": self.CHICAGO_LAT,
            "lon": self.CHICAGO_LON,
            "appid": self.api_key,
            "units": "metric"
        }
        try:
            resp = requests.get(f"{self.BASE_URL}/weather", params=params)
            resp.raise_for_status()
            data = resp.json()

            main = data.get("main", {})
            weather = data.get("weather", [{}])[0]

            return WeatherSnapshot(
                timestamp=datetime.now(pytz.timezone("US/Central")),
                temperature=main.get("temp", 0),
                condition=weather.get("main", "Unknown"),
                precipitation_mm=data.get("rain", {}).get("1h", 0),
                wind_speed=data.get("wind", {}).get("speed", 0)
            )
        except requests.RequestException as e:
            print(f"OpenWeatherMap API error: {e}")
            return None


def _speed_to_level(speed_mph: float) -> str:
    """Classify traffic level based on speed."""
    if speed_mph >= 20:
        return "free_flow"
    elif speed_mph >= 12:
        return "moderate"
    else:
        return "congested"
