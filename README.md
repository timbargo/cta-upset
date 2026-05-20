# CTA Upset: Chicago Bus Delay Prediction & Anomaly Detection

Predictive tool to detect when CTA buses will take longer than usual, before you board.

## Problem

CTA buses rarely run on schedule. Route 56 to the Loop that the API says takes 5 minutes might actually take 18 minutes. You want to know this discrepancy **ahead of time**, not after waiting 15 minutes at the stop.

## Solution

**CTA Upset** builds an "almanac" of historical delays and correlates them with:
- **Real-time traffic** (Chicago's arterial streets)
- **Weather patterns** (rain/snow increase delays)
- **Time/day patterns** (rush hour vs midday, weekday vs weekend)
- **CTA prediction accuracy** (how well the API predicts)

Then it:
1. **Detects anomalies** - When current delays exceed historical baselines
2. **Forecasts delays** - Predicts how long you'll actually wait
3. **Identifies factors** - Shows why delays happen (traffic, weather, rush hour)

## Architecture

```
CTA APIs (predictions)  ──┐
Chicago Traffic Tracker ──┼──> Analyzer ──> Delay Detection
OpenWeatherMap ──────────┤      & 
Historical Almanac ──────┘    Forecasting
```

### Data Sources

| Source | Purpose | Update Freq | Cost |
|--------|---------|-------------|------|
| **CTA Bus Tracker API** | Predicted arrivals, bus positions | 1 min | Free |
| **Chicago Traffic Tracker** | Real-time arterial street speeds | 10 min | Free |
| **OpenWeatherMap** | Current weather + forecasts | Real-time | Free tier |
| **Almanac** (historical) | Baseline delays by route/time/day | Continuous | Built locally |

## Quick Start

### 1. Setup

```bash
# Install dependencies
uv sync

# Copy and fill config
cp .env.example .env
# Edit .env with your API keys
```

### 2. Get API Keys

**CTA API Key** (required):
- Register at https://www.transitchicago.com/developers/bustracker/
- Takes ~5 minutes, free tier provides 10k requests/day

**OpenWeatherMap** (optional, for weather analysis):
- Sign up at https://openweathermap.org/api
- Free tier is sufficient

### 3. Run

```bash
# Check current delay for a route/stop
python -m cta_upset.main check 56 2834

# Forecast delays for upcoming hours
python -m cta_upset.main forecast 56 0 9   # Route 56, Monday at 9am

# View route statistics
python -m cta_upset.main summary 56

# List available routes
python -m cta_upset.main routes
```

## How It Works

### Building the Almanac

The system collects delay data over time. For each trip, it records:

```python
DelayRecord(
    route_id="56",
    stop_id="2834",
    scheduled_time="09:00",
    predicted_time="09:02",      # What CTA API said
    actual_time="09:18",          # What actually happened
    
    scheduled_delay_sec=1080,     # 18 minutes late
    prediction_error_sec=960,     # API was off by 16 minutes
    
    day_of_week=0,                # Monday
    hour_of_day=9,                # 9am
    
    weather_condition="rainy",
    traffic_speed=8.5,            # mph
)
```

The **Almanac** aggregates these into baselines:

```json
{
  "56_00_09": {
    "route_id": "56",
    "day_of_week": 0,
    "hour_of_day": 9,
    "samples": 42,
    "avg_scheduled_delay_sec": 420,     // 7 minutes typical
    "p95_scheduled_delay_sec": 900,     // Worst case ~15 min
    "last_updated": "2026-05-20T09:30:00"
  }
}
```

### Anomaly Detection

When a bus is delayed more than expected:

```python
# Your Route 56 trip on Monday 9am:
actual_delay = 1080 sec (18 min)

# Historical baseline:
expected_delay = 420 sec (7 min)

# Anomaly magnitude:
excess = 1080 - 420 = 660 sec
confidence = 0.95 (high, 42 historical samples)

# Identified factors:
- rain detected → weather factor
- traffic 8.5 mph → heavy traffic
- 9am on weekday → rush hour
```

### Forecasting

Uses baseline + current conditions:

```python
# For Route 56, Monday 9am:
base_delay = 7 min (from almanac)

# Adjustments:
+ 3 min (heavy traffic detected now)
+ 2 min (rain in forecast)

# Forecast: 12 minutes expected (confidence: high)
```

## Data Structure

```
data/
├── delay_records.jsonl      # Raw trip records (append-only)
│   └── {route, stop, times, delays, weather, traffic...}
│
└── delay_almanac.json       # Aggregated baselines by route/time/day
    └── {route_day_hour: {samples, avg_delay, p95...}}
```

The almanac builds automatically as you use the tool. Historical records persist across sessions.

## Key Insights You Get

### 1. Route Almanac
```
Route 56 Summary:
  Average delay: 8.3 minutes
  Worst hour: 09:00 (14.2 min)
  Best hour: 14:00 (2.1 min)
  
  By day:
    Mon: 9.1 min (rush hour)
    Tue: 8.5 min
    Wed: 7.8 min
    Thu: 9.3 min
    Fri: 11.2 min (end of week)
    Sat: 3.2 min
    Sun: 2.8 min
```

### 2. Real-Time Anomalies
```
Route 56 at 09:15am on Monday:
  Typical delay: 7 min
  Current delay: 18 min  ⚠️ Anomaly!
  Magnitude: 2.6x normal
  
  Factors:
    ✓ Heavy traffic (8 mph vs 15 mph typical)
    ✓ Rain reducing speeds
    ✓ Rush hour effect
    
  Forecast: 20 min wait (high confidence)
```

### 3. Weather Impact
```
Route 56 on rainy days:
  Clear: 7 min avg
  Rainy: 11 min avg (+4 min)
  Snowy: 18 min avg (+11 min)
```

## Advanced Usage

### Batch Processing

Monitor multiple routes over time:

```python
from cta_upset.api import CTABusTrackerAPI
from cta_upset.analyzer import DelayAnalyzer
from cta_upset.storage import DelayAlmanac

cta = CTABusTrackerAPI(api_key)
analyzer = DelayAnalyzer(DelayAlmanac())

# Collect data for several routes
for route_id in ["56", "151", "36"]:
    for stop in cta.get_stops(route_id):
        predictions = cta.get_predictions(stop.stop_id, route_id)
        # ... process and store in almanac
```

### Integration with Other Tools

The `DelayRecord` and `DelayAnomaly` dataclasses are designed to be JSON-serializable for integration with dashboards, alerts, etc.

### Building Custom Models

The raw `delay_records.jsonl` file contains all historical data for custom ML models:

```python
import pandas as pd

records = pd.read_json("data/delay_records.jsonl", lines=True)

# Analyze: What factors predict >10 min delays?
heavy_delays = records[records["scheduled_delay_sec"] > 600]
weather_correlation = heavy_delays["weather_condition"].value_counts()
```

## Interpretation Guide

### When to Trust Forecasts

- **High confidence**: 50+ historical samples for that route/time/day
- **Medium confidence**: 10-50 samples
- **Low confidence**: <10 samples (build more data)

### Traffic Speed → Delay Mapping

Based on Chicago arterial speeds:
- **>20 mph**: Light traffic, minimal impact
- **12-20 mph**: Moderate congestion, +1-2 min
- **<12 mph**: Heavy congestion, +3-5 min

### Weather Impact Multipliers

- **Rain**: ~50% increase in delays
- **Snow**: ~150% increase in delays
- **Extreme heat/cold**: Moderate increase (vehicle performance)

## Limitations & Future Work

### Current
- Uses CTA predicted times (which are themselves sometimes inaccurate)
- Traffic data from arterial streets only (limited freeway coverage)
- Doesn't predict special events (concerts, transit changes)
- Doesn't factor in school calendar or holidays

### Future Enhancements
- **ML model**: LSTM trained on seasonal patterns
- **WAZE integration**: Incident detection (accidents, construction)
- **Event calendar**: Automatically detect impact from special events
- **Network effects**: Detect cascade delays (one delayed bus causes next one)
- **Geospatial**: Map delay patterns across stops on same route
- **Mobile app**: Real-time alerts before you board

## Files

- `cta_upset/models.py` - Data class definitions
- `cta_upset/api.py` - External API integrations
- `cta_upset/analyzer.py` - Core delay detection & forecasting
- `cta_upset/storage.py` - Historical almanac management
- `cta_upset/main.py` - CLI interface

## License

MIT
