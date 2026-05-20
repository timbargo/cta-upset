"""
Example usage of CTA Upset library.

Before running, set your API keys:
  export CTA_API_KEY="your_cta_api_key"
  export OPENWEATHER_API_KEY="your_weather_api_key"
"""

import os
from datetime import datetime, timedelta
import pytz
from cta_upset.api import CTABusTrackerAPI, ChicagoTrafficTrackerAPI, OpenWeatherMapAPI
from cta_upset.analyzer import DelayAnalyzer
from cta_upset.storage import DelayAlmanac
from cta_upset.models import DelayRecord


def example_1_basic_api_usage():
    """Example 1: Query the CTA API and traffic data."""
    print("=" * 60)
    print("Example 1: Basic API Usage")
    print("=" * 60)

    cta_key = os.getenv("CTA_API_KEY")
    if not cta_key:
        print("⚠️  CTA_API_KEY not set. Skipping this example.")
        return

    # Get available routes
    cta = CTABusTrackerAPI(cta_key)
    routes = cta.get_routes()
    print(f"\n📍 Found {len(routes)} routes")
    print(f"   Examples: {', '.join([r.route_id for r in routes[:5]])}")

    # Get Route 56 stops
    route_56_stops = cta.get_stops("56")
    print(f"\n🚌 Route 56 has {len(route_56_stops)} stops")
    print(f"   First few: {', '.join([s.stop_name for s in route_56_stops[:3]])}")

    # Get predictions for a specific stop
    if route_56_stops:
        stop = route_56_stops[0]
        predictions = cta.get_predictions(stop.stop_id, "56")
        print(f"\n⏰ Predictions for {stop.stop_name}:")
        for pred in predictions[:3]:
            print(f"   Vehicle {pred.vehicle_id}: {pred.predicted_time.strftime('%H:%M')}")


def example_2_traffic_and_weather():
    """Example 2: Get current traffic and weather data."""
    print("\n" + "=" * 60)
    print("Example 2: Traffic and Weather")
    print("=" * 60)

    # Get Chicago traffic data
    traffic = ChicagoTrafficTrackerAPI()
    segments = traffic.get_current_segments(limit=20)

    print(f"\n🚗 Current traffic on Chicago arterials:")
    for seg in segments[:5]:
        print(f"   {seg.street_name} ({seg.direction}): {seg.estimated_speed:.1f} mph")

    # Get weather if API key available
    weather_key = os.getenv("OPENWEATHER_API_KEY")
    if weather_key:
        weather = OpenWeatherMapAPI(weather_key)
        w = weather.get_current_weather()
        if w:
            print(f"\n🌤️  Current weather in Chicago:")
            print(f"   Condition: {w.condition}")
            print(f"   Temperature: {w.temperature:.1f}°C")
            print(f"   Precipitation: {w.precipitation_mm}mm")
    else:
        print("\n⚠️  OPENWEATHER_API_KEY not set. Skipping weather example.")


def example_3_building_almanac():
    """Example 3: Create delay records and build an almanac."""
    print("\n" + "=" * 60)
    print("Example 3: Building Historical Almanac")
    print("=" * 60)

    almanac = DelayAlmanac()
    analyzer = DelayAnalyzer(almanac)
    chicago_tz = pytz.timezone("US/Central")

    # Simulate some historical delay records
    base_time = datetime.now(chicago_tz)

    for day_offset in range(7):  # 7 days of data
        current_date = base_time - timedelta(days=day_offset)

        # Morning rush (9am)
        scheduled = current_date.replace(hour=9, minute=0, second=0)
        predicted = scheduled + timedelta(minutes=2)
        actual = scheduled + timedelta(minutes=7)  # Typically 7 min late

        record = analyzer.compute_delay_record(
            route_id="56",
            stop_id="2834",
            stop_name="Clark & Division",
            scheduled_time=scheduled,
            predicted_time=predicted,
            actual_time=actual,
            prediction_made_at=scheduled,
        )
        almanac.add_record(record)

        # Afternoon (2pm)
        scheduled = current_date.replace(hour=14, minute=0, second=0)
        predicted = scheduled + timedelta(minutes=1)
        actual = scheduled + timedelta(minutes=3)  # Usually on-time-ish

        record = analyzer.compute_delay_record(
            route_id="56",
            stop_id="2834",
            stop_name="Clark & Division",
            scheduled_time=scheduled,
            predicted_time=predicted,
            actual_time=actual,
            prediction_made_at=scheduled,
        )
        almanac.add_record(record)

    print(f"✅ Created almanac with simulated data")
    print(f"   Total records: {len(almanac.almanac)}")

    # Show baseline for Route 56, Monday, 9am
    baseline = almanac.get_baseline(route_id="56", day_of_week=0, hour_of_day=9)
    if baseline:
        print(f"\n📊 Baseline for Route 56, Monday 9am:")
        print(f"   Avg delay: {baseline['avg_scheduled_delay_sec']/60:.1f} minutes")
        print(f"   Samples: {baseline['samples']}")


def example_4_anomaly_detection():
    """Example 4: Detect anomalies."""
    print("\n" + "=" * 60)
    print("Example 4: Anomaly Detection")
    print("=" * 60)

    almanac = DelayAlmanac()
    analyzer = DelayAnalyzer(almanac)
    chicago_tz = pytz.timezone("US/Central")

    # Setup baseline data (same as example 3)
    base_time = datetime.now(chicago_tz)
    for day_offset in range(7):
        current_date = base_time - timedelta(days=day_offset)
        scheduled = current_date.replace(hour=9, minute=0, second=0)
        predicted = scheduled + timedelta(minutes=2)
        actual = scheduled + timedelta(minutes=7)

        record = analyzer.compute_delay_record(
            route_id="56",
            stop_id="2834",
            stop_name="Clark & Division",
            scheduled_time=scheduled,
            predicted_time=predicted,
            actual_time=actual,
            prediction_made_at=scheduled,
        )
        almanac.add_record(record)

    # Now create a new record with excessive delay
    print("\n🔍 Checking current trip for anomalies...")
    scheduled = base_time.replace(hour=9, minute=0, second=0)
    predicted = scheduled + timedelta(minutes=2)
    actual = scheduled + timedelta(minutes=18)  # 18 min late!

    current_record = analyzer.compute_delay_record(
        route_id="56",
        stop_id="2834",
        stop_name="Clark & Division",
        scheduled_time=scheduled,
        predicted_time=predicted,
        actual_time=actual,
        prediction_made_at=scheduled,
    )

    anomaly = analyzer.detect_anomaly(current_record, tolerance_sec=300)

    if anomaly:
        print(f"   ⚠️  ANOMALY DETECTED!")
        print(f"   Expected: {anomaly.expected_delay_minutes} minutes")
        print(f"   Actual: {anomaly.delay_minutes} minutes")
        print(f"   Magnitude: {anomaly.anomaly_magnitude:.1f}x normal")
        print(f"   Factors: {', '.join(anomaly.potential_factors)}")
    else:
        print(f"   ✅ Within normal parameters")


def example_5_forecasting():
    """Example 5: Forecast future delays."""
    print("\n" + "=" * 60)
    print("Example 5: Delay Forecasting")
    print("=" * 60)

    almanac = DelayAlmanac()
    analyzer = DelayAnalyzer(almanac)
    chicago_tz = pytz.timezone("US/Central")

    # Build baseline
    base_time = datetime.now(chicago_tz)
    for day_offset in range(7):
        current_date = base_time - timedelta(days=day_offset)
        for hour in range(6, 22):
            scheduled = current_date.replace(hour=hour, minute=0, second=0)
            predicted = scheduled + timedelta(minutes=2)

            # Realistic delay pattern: rush hour has more delay
            if hour in (8, 9) or hour in (17, 18):
                delay_min = 10
            elif hour in range(10, 15):
                delay_min = 3
            else:
                delay_min = 6

            actual = scheduled + timedelta(minutes=delay_min)

            record = analyzer.compute_delay_record(
                route_id="56",
                stop_id="2834",
                stop_name="Clark & Division",
                scheduled_time=scheduled,
                predicted_time=predicted,
                actual_time=actual,
                prediction_made_at=scheduled,
            )
            almanac.add_record(record)

    # Forecast
    print("\n🔮 Forecasting Route 56 on Monday:")
    now = datetime.now(chicago_tz)
    for hour in range(7, 20):
        forecast, confidence = analyzer.forecast_delay(
            route_id="56",
            current_hour=hour,
            day_of_week=0,  # Monday
        )
        status = "🔴" if forecast > 8 else "🟡" if forecast > 5 else "🟢"
        print(f"   {hour:02d}:00 - {forecast:.1f} min ({confidence}) {status}")


def example_6_route_summary():
    """Example 6: Get route summary statistics."""
    print("\n" + "=" * 60)
    print("Example 6: Route Summary Statistics")
    print("=" * 60)

    almanac = DelayAlmanac()
    analyzer = DelayAnalyzer(almanac)
    chicago_tz = pytz.timezone("US/Central")

    # Build comprehensive data
    base_time = datetime.now(chicago_tz)
    for day_offset in range(30):  # 30 days of data
        current_date = base_time - timedelta(days=day_offset)
        for hour in range(6, 22):
            scheduled = current_date.replace(hour=hour, minute=0, second=0)
            predicted = scheduled + timedelta(minutes=2)

            # Realistic pattern
            if hour in (8, 9):
                delay_min = 8 + (current_date.weekday() % 3)
            elif hour in (17, 18):
                delay_min = 7 + (current_date.weekday() // 2)
            else:
                delay_min = 3

            actual = scheduled + timedelta(minutes=delay_min)

            record = analyzer.compute_delay_record(
                route_id="56",
                stop_id="2834",
                stop_name="Clark & Division",
                scheduled_time=scheduled,
                predicted_time=predicted,
                actual_time=actual,
                prediction_made_at=scheduled,
            )
            almanac.add_record(record)

    summary = analyzer.get_route_summary("56")

    print(f"\n📊 Route 56 Summary Statistics:")
    print(f"   Average delay: {summary['avg_delay_min']} minutes")
    print(f"   Worst hour: {summary['worst_hour']}")
    print(f"   Best hour: {summary['best_hour']}")
    print(f"   Total observations: {summary['samples']}")

    if summary["day_breakdown"]:
        print(f"\n   By day of week:")
        for day, delay in summary["day_breakdown"].items():
            print(f"     {day}: {delay} min")


if __name__ == "__main__":
    print("\n🚌 CTA Upset - Example Usage\n")

    example_1_basic_api_usage()
    example_2_traffic_and_weather()
    example_3_building_almanac()
    example_4_anomaly_detection()
    example_5_forecasting()
    example_6_route_summary()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60 + "\n")
