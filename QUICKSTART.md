# CTA Upset: Quick Start Guide

Predict CTA bus delays before you board.

## Problem This Solves

You're waiting for Route 56 to the Loop. The CTA app says 5 minutes. You wait 18 minutes. By then, you're late for your meeting.

**CTA Upset** learns from history: "Route 56 to Clark & Division typically takes 7 minutes during morning rush, but when there's rain, add 4 more minutes. Today it's raining and traffic is heavy, so expect 14 minutes, not 5."

## 60-Second Setup

```bash
# 1. Clone and install
git clone <repo>
cd cta-upset
uv sync

# 2. Get your CTA API key (5 min)
# Go to https://www.transitchicago.com/developers/bustracker/
# Register, get your free API key

# 3. Configure
cp .env.example .env
# Edit .env, paste your CTA API key

# 4. Run
python -m cta_upset.main check 56 2834
```

## What It Does

### Real-time Check
```bash
python -m cta_upset.main check 56 2834
```

```
📍 Checking Route 56, Stop Clark & Division...
  Predicted arrival: 09:15
  Current traffic: 14.2 mph (heavy)
  Weather: Rainy, 15.3°C

🔮 Forecast:
  Expected delay: 12.1 minutes (confidence: high)
  ⚠️  Above normal - expect longer wait
```

### Forecast Delays
```bash
python -m cta_upset.main forecast 56 0 9  # Monday 9am
```

```
🔮 Forecasting Route 56
   Day: Monday (0=Mon, 6=Sun)
   Hour: 09:00

  09:00 - 8.5 min delay (high) 📈
  10:00 - 4.2 min delay (high) ✅
  11:00 - 3.1 min delay (high) ✅
  12:00 - 2.8 min delay (high) ✅
```

### View Route Statistics (Your Almanac)
```bash
python -m cta_upset.main summary 56
```

```
📊 Route 56 Summary
   Average delay: 5.8 minutes
   Worst hour: 09:00 (9.2 min)
   Best hour: 14:00 (2.1 min)
   Total observations: 847

   By day of week:
     Mon: 7.1 min (rush hour)
     Tue: 6.2 min
     Wed: 5.5 min
     Thu: 6.8 min
     Fri: 8.3 min (end of week)
     Sat: 2.9 min
     Sun: 2.4 min
```

## How It Works (In Plain English)

### 1. **The Almanac**
System learns: "Over the last month, Route 56 at 9am on Mondays was late by an average of 7 minutes."

### 2. **Real-time Signals**
Checks: "Right now, traffic is heavy (8 mph), it's raining, and it's Monday 9am."

### 3. **Anomaly Detection**
Compares: "Expected 7 min, but given heavy traffic + rain, I predict 14 min. That's 2x normal!"

### 4. **Forecast**
Returns: "Expect a longer wait than usual."

## Data Sources

- **CTA Bus Tracker API** - Current predictions from CTA
- **Chicago Traffic Tracker** - Real-time traffic on Chicago streets
- **OpenWeatherMap** (optional) - Weather conditions
- **Your Local Almanac** - Builds automatically as you use the tool

## Common Routes & Stop IDs

To use this effectively, you need your route and stop IDs:

```bash
# See all available routes
python -m cta_upset.main routes
```

**Popular Examples:**
- Route 56 (Clark), Stop 2834 (Clark & Division)
- Route 151 (Sheridan), Stop 945 (Sheridan & Diversey)
- Route 36 (Broadway), Stop 5318 (Broadway & Irving)

Find your stop on Google Maps or the CTA website. Stop IDs appear in their URLs.

## Real-World Example

**Your scenario:** Morning commute, Route 56, Clark & Division stop.

```bash
# Monday 8:45am - you're about to leave home
python -m cta_upset.main check 56 2834

# Output says: "⚠️ Expected delay: 12.1 minutes"
# Decision: Take Uber instead OR leave earlier
```

**Versus without CTA Upset:**
- "App says 5 min, I'll wait 5 min, actually wait 18 min" → late for work

**With CTA Upset:**
- "Forecast says 12 min, plan accordingly" → on time

## How the Almanac Grows

**Day 1:** Limited data, low confidence
```
Monday 9am on Route 56: 1 sample
Forecast: 8 min (low confidence)
```

**After 2 weeks:**
```
Monday 9am on Route 56: 10 samples
Forecast: 7.8 min (medium confidence)
Worst case: 12 min
```

**After 2 months:**
```
Monday 9am on Route 56: 50 samples
Forecast: 8.1 min (high confidence)
Variation: normally 6-10 min
Pattern: 2-3x worse in rain
```

## Using Programmatically

Instead of the CLI, you can import and use directly:

```python
from cta_upset.api import CTABusTrackerAPI
from cta_upset.analyzer import DelayAnalyzer
from cta_upset.storage import DelayAlmanac

cta = CTABusTrackerAPI(api_key)
analyzer = DelayAnalyzer(DelayAlmanac())

# Get current predictions
predictions = cta.get_predictions(stop_id="2834", route_id="56")

# Forecast
forecast, confidence = analyzer.forecast_delay(
    route_id="56",
    current_hour=9,
    day_of_week=0,  # Monday
)
print(f"Expected {forecast:.1f} min ({confidence})")
```

See `examples.py` for more.

## Limitations

- **Limited initial data:** Predictions are weak with <10 historical samples
- **No special events:** Doesn't predict impact of concerts, road construction, etc.
- **No holidays:** School calendar and holidays aren't factored in yet
- **Requires CTA predictions:** Uses CTA's own predictions as input (they're sometimes wrong)

## Troubleshooting

### "No predictions available"
- Stop ID is wrong
- Route doesn't serve that stop
- CTA API is down

### "Low confidence"
- Not enough data collected yet
- Use the tool regularly for 2+ weeks to build almanac
- Every trip adds to the baseline

### "API key error"
- Check `CTA_API_KEY` in `.env` is correct
- Run `echo $CTA_API_KEY` to verify it's set

## Next Steps

1. **Set up** — Get your CTA API key
2. **Run for 2 weeks** — Build baseline data
3. **Check forecasts** — Use before commuting
4. **Integrate** — Use programmatically if building a dashboard

## See Also

- `README.md` - Full technical documentation
- `examples.py` - Code examples for developers
- CTA Developer Portal: https://www.transitchicago.com/developers/
- Chicago Data Portal: https://data.cityofchicago.org/
