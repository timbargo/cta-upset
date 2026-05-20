"""CLI for CTA delay prediction and anomaly detection."""

import os
import sys
from datetime import datetime
from typing import Optional
import pytz

from dotenv import load_dotenv
from .api import CTABusTrackerAPI, ChicagoTrafficTrackerAPI, OpenWeatherMapAPI
from .analyzer import DelayAnalyzer
from .storage import DelayAlmanac


load_dotenv()


def main():
    """Main CLI entry point."""
    if len(sys.argv) < 2:
        print_usage()
        sys.exit(1)

    command = sys.argv[1]

    # Initialize APIs
    cta_api_key = os.getenv("CTA_API_KEY")
    weather_api_key = os.getenv("OPENWEATHER_API_KEY")

    if not cta_api_key:
        print("Error: CTA_API_KEY not set. Set it in .env file or export it.")
        sys.exit(1)

    cta = CTABusTrackerAPI(cta_api_key)
    traffic = ChicagoTrafficTrackerAPI()
    weather = OpenWeatherMapAPI(weather_api_key) if weather_api_key else None
    almanac = DelayAlmanac()
    analyzer = DelayAnalyzer(almanac)

    if command == "check":
        check_route(cta, traffic, weather, analyzer, almanac)
    elif command == "forecast":
        forecast_route(analyzer)
    elif command == "summary":
        show_route_summary(analyzer)
    elif command == "recent":
        show_recent_delays(analyzer)
    elif command == "routes":
        list_routes(cta)
    else:
        print(f"Unknown command: {command}")
        print_usage()
        sys.exit(1)


def check_route(cta, traffic, weather, analyzer, almanac):
    """Check current delay for a route/stop."""
    if len(sys.argv) < 4:
        print("Usage: cta-upset check <route_id> <stop_id>")
        sys.exit(1)

    route_id = sys.argv[2]
    stop_id = sys.argv[3]

    print(f"\n📍 Checking Route {route_id}, Stop {stop_id}...")

    # Get current predictions
    predictions = cta.get_predictions(stop_id, route_id)
    if not predictions:
        print("❌ No predictions available")
        return

    pred = predictions[0]
    print(f"  Predicted arrival: {pred.predicted_time.strftime('%H:%M')}")

    # Get traffic data
    traffic_segments = traffic.get_current_segments(limit=50)
    congestion = "N/A"
    if traffic_segments:
        avg_speed = sum(s.estimated_speed for s in traffic_segments) / len(traffic_segments)
        congestion = f"{avg_speed:.1f} mph"

    print(f"  Current traffic: {congestion}")

    # Get weather
    if weather:
        w = weather.get_current_weather()
        if w:
            print(f"  Weather: {w.condition}, {w.temperature:.1f}°C")

    # Forecast delay
    chicago_tz = pytz.timezone("US/Central")
    now = datetime.now(chicago_tz)
    forecast, confidence = analyzer.forecast_delay(
        route_id,
        now.hour,
        now.weekday(),
        traffic_condition=_speed_to_traffic(
            sum(s.estimated_speed for s in traffic_segments) / len(traffic_segments)
            if traffic_segments else 0
        ),
        weather_condition=w.condition if weather and w else None,
    )

    print(f"\n🔮 Forecast:")
    print(f"  Expected delay: {forecast:.1f} minutes (confidence: {confidence})")

    if forecast > 5:
        print(f"  ⚠️  Above normal - expect longer wait")
    else:
        print(f"  ✅ Normal delay")


def forecast_route(analyzer):
    """Forecast delays for a route."""
    if len(sys.argv) < 2:
        print("Usage: cta-upset forecast <route_id> [day] [hour]")
        sys.exit(1)

    route_id = sys.argv[2]

    chicago_tz = pytz.timezone("US/Central")
    now = datetime.now(chicago_tz)

    day = int(sys.argv[3]) if len(sys.argv) > 3 else now.weekday()
    hour = int(sys.argv[4]) if len(sys.argv) > 4 else now.hour

    print(f"\n🔮 Forecasting Route {route_id}")
    print(f"   Day: {_day_name(day)} (0=Mon, 6=Sun)")
    print(f"   Hour: {hour:02d}:00\n")

    for h in range(hour, hour + 4):
        h_adj = h % 24
        forecast, confidence = analyzer.forecast_delay(route_id, h_adj, day)
        status = "📈" if forecast > 5 else "✅"
        print(f"  {h_adj:02d}:00 - {forecast:.1f} min delay ({confidence}) {status}")


def show_route_summary(analyzer):
    """Show summary for a route."""
    if len(sys.argv) < 3:
        print("Usage: cta-upset summary <route_id>")
        sys.exit(1)

    route_id = sys.argv[2]
    summary = analyzer.get_route_summary(route_id)

    print(f"\n📊 Route {route_id} Summary")
    print(f"   Average delay: {summary['avg_delay_min']:.1f} minutes")
    print(f"   Worst hour: {summary['worst_hour']}")
    print(f"   Best hour: {summary['best_hour']}")
    print(f"   Total observations: {summary['samples']}")

    if summary["day_breakdown"]:
        print(f"\n   By day of week:")
        for day, delay in summary["day_breakdown"].items():
            print(f"     {day}: {delay:.1f} min")


def show_recent_delays(analyzer):
    """Show recent detected anomalies."""
    records = analyzer.almanac.get_recent_records(hours=24)

    print(f"\n📋 Recent Anomalies (last 24 hours)")
    print(f"   Total records: {len(records)}\n")

    # Group by route
    by_route = {}
    for record in records:
        if record.route_id not in by_route:
            by_route[record.route_id] = []
        by_route[record.route_id].append(record)

    for route_id in sorted(by_route.keys())[:10]:  # Top 10 routes
        records_for_route = by_route[route_id]
        avg_delay = sum(r.scheduled_delay_sec for r in records_for_route) / len(records_for_route)
        print(f"  Route {route_id}: {len(records_for_route)} samples, {avg_delay/60:.1f} min avg")


def list_routes(cta):
    """List available routes."""
    print("\n📍 Available CTA Routes\n")
    routes = cta.get_routes()

    if not routes:
        print("  No routes found")
        return

    for route in sorted(routes, key=lambda r: int(r.route_id) if r.route_id.isdigit() else 999)[:20]:
        print(f"  {route.route_id}: {route.route_name}")

    if len(routes) > 20:
        print(f"  ... and {len(routes) - 20} more")


def print_usage():
    """Print CLI usage."""
    print("""
CTA Delay Prediction Tool

Usage:
  cta-upset check <route_id> <stop_id>     Check current delay for a route/stop
  cta-upset forecast <route_id> [day] [hr] Forecast delays for upcoming hours
  cta-upset summary <route_id>              Show route delay summary & almanac
  cta-upset recent                          Show recent detected anomalies
  cta-upset routes                          List available routes

Examples:
  cta-upset check 56 2834                   Check Route 56 at Clark/Division
  cta-upset forecast 56 0 9                 Forecast Route 56 on Monday at 9am
  cta-upset summary 56                      Show Route 56 statistics

Set environment variables:
  CTA_API_KEY           Required - from CTA Developer Center
  OPENWEATHER_API_KEY   Optional - for weather data
    """)


def _speed_to_traffic(speed: float) -> str:
    """Convert speed to traffic level."""
    if speed >= 20:
        return "light"
    elif speed >= 12:
        return "moderate"
    else:
        return "heavy"


def _day_name(day_num: int) -> str:
    """Convert day number to name."""
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    return days[day_num % 7]


if __name__ == "__main__":
    main()
