"""
OpenWeatherMap & Agro API Weather Data Fetcher
================================================
Fetches real-time weather and soil data for field coordinates.
Falls back to synthetic weather generation when API key is unavailable.
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _generate_synthetic_weather(lat: float, lon: float) -> dict:
    """Generate realistic synthetic weather data for agricultural context."""
    np.random.seed(int(datetime.utcnow().timestamp()) % 100000)

    # Seasonal base temperature (Northern Hemisphere agriculture)
    month = datetime.utcnow().month
    seasonal_temp = {
        1: -2, 2: 1, 3: 8, 4: 14, 5: 20, 6: 26,
        7: 30, 8: 28, 9: 22, 10: 14, 11: 6, 12: 0
    }
    base_temp = seasonal_temp.get(month, 20) + np.random.normal(0, 3)

    # Wind and humidity correlated with temperature
    humidity = max(20, min(95, 70 - base_temp * 0.5 + np.random.normal(0, 10)))
    wind_speed = max(0, 3 + np.random.exponential(2))
    cloud_cover = max(0, min(100, np.random.beta(2, 3) * 100))

    # Soil moisture depends on recent "rain" probability
    rain_chance = 0.3 if humidity > 60 else 0.1
    rain = np.random.exponential(5) if np.random.random() < rain_chance else 0
    soil_moisture = max(0.05, min(0.95, 0.4 + rain * 0.02 + np.random.normal(0, 0.1)))

    # Calculate agricultural indices
    dew_point = base_temp - ((100 - humidity) / 5)
    heat_index = base_temp + 0.5 * (humidity / 100) * base_temp if base_temp > 26 else base_temp

    weather = {
        "timestamp": datetime.utcnow().isoformat(),
        "source": "synthetic",
        "coordinates": {"lat": lat, "lon": lon},
        "current": {
            "temperature_c": round(base_temp, 1),
            "feels_like_c": round(heat_index, 1),
            "humidity_pct": round(humidity, 1),
            "pressure_hpa": round(1013 + np.random.normal(0, 5), 1),
            "wind_speed_ms": round(wind_speed, 1),
            "wind_direction_deg": int(np.random.uniform(0, 360)),
            "cloud_cover_pct": round(cloud_cover, 1),
            "visibility_m": int(min(10000, max(1000, 10000 - cloud_cover * 50))),
            "uv_index": round(max(0, 8 - cloud_cover * 0.06 + np.random.normal(0, 0.5)), 1),
            "description": _weather_description(base_temp, humidity, cloud_cover, rain),
        },
        "precipitation": {
            "rain_mm": round(rain, 1),
            "rain_probability_pct": round(rain_chance * 100, 0),
        },
        "soil": {
            "moisture": round(soil_moisture, 3),
            "temperature_c": round(base_temp - 3 + np.random.normal(0, 1), 1),
        },
        "agricultural_alerts": _generate_ag_alerts(base_temp, humidity, soil_moisture, wind_speed),
        "dew_point_c": round(dew_point, 1),
    }

    return weather


def _weather_description(temp, humidity, clouds, rain) -> str:
    """Generate a human-readable weather description."""
    if rain > 5:
        return "Heavy rain"
    elif rain > 1:
        return "Light rain"
    elif clouds > 80:
        return "Overcast"
    elif clouds > 50:
        return "Partly cloudy"
    elif temp > 35:
        return "Hot and clear"
    elif temp < 0:
        return "Cold and clear"
    else:
        return "Clear sky"


def _generate_ag_alerts(temp, humidity, soil_moisture, wind) -> list:
    """Generate agricultural alerts based on weather conditions."""
    alerts = []

    if soil_moisture < 0.15:
        alerts.append({
            "type": "CRITICAL",
            "category": "irrigation",
            "message": "Critical soil moisture deficit — immediate irrigation recommended",
            "severity": 5,
        })
    elif soil_moisture < 0.25:
        alerts.append({
            "type": "WARNING",
            "category": "irrigation",
            "message": "Low soil moisture — schedule irrigation within 24 hours",
            "severity": 3,
        })

    if temp < 2:
        alerts.append({
            "type": "CRITICAL",
            "category": "frost",
            "message": f"Frost risk — temperature at {temp:.1f}°C",
            "severity": 5,
        })

    if humidity > 85 and temp > 15:
        alerts.append({
            "type": "WARNING",
            "category": "disease",
            "message": "High humidity may promote fungal disease — monitor closely",
            "severity": 3,
        })

    if wind > 10:
        alerts.append({
            "type": "WARNING",
            "category": "spray",
            "message": f"Wind speed {wind:.1f} m/s — unsuitable for pesticide application",
            "severity": 2,
        })

    if not alerts:
        alerts.append({
            "type": "INFO",
            "category": "general",
            "message": "Conditions favorable for crop growth",
            "severity": 0,
        })

    return alerts


def fetch_weather(
    lat: float = None,
    lon: float = None,
    save: bool = True,
) -> dict:
    """
    Fetch current weather and soil conditions for the field.

    Returns:
        dict with weather data including temperature, humidity, soil moisture, alerts.
    """
    lat = lat or config.FIELD_LAT
    lon = lon or config.FIELD_LON

    if not config.has_openweather_key():
        logger.info("OpenWeatherMap API key not configured — generating synthetic weather")
        weather = _generate_synthetic_weather(lat, lon)
    else:
        weather = _fetch_live_weather(lat, lon)

    if save:
        _save_weather(weather)

    return weather


def _fetch_live_weather(lat: float, lon: float) -> dict:
    """Fetch live weather from OpenWeatherMap API."""
    import requests

    try:
        # Current weather
        url = "https://api.openweathermap.org/data/2.5/weather"
        params = {
            "lat": lat, "lon": lon,
            "appid": config.OPENWEATHERMAP_API_KEY,
            "units": "metric",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        weather = {
            "timestamp": datetime.utcnow().isoformat(),
            "source": "openweathermap",
            "coordinates": {"lat": lat, "lon": lon},
            "current": {
                "temperature_c": data["main"]["temp"],
                "feels_like_c": data["main"]["feels_like"],
                "humidity_pct": data["main"]["humidity"],
                "pressure_hpa": data["main"]["pressure"],
                "wind_speed_ms": data["wind"]["speed"],
                "wind_direction_deg": data["wind"].get("deg", 0),
                "cloud_cover_pct": data["clouds"]["all"],
                "visibility_m": data.get("visibility", 10000),
                "uv_index": 0,  # Requires separate API call
                "description": data["weather"][0]["description"],
            },
            "precipitation": {
                "rain_mm": data.get("rain", {}).get("1h", 0),
                "rain_probability_pct": 0,
            },
            "soil": {
                "moisture": 0.4,  # Placeholder — requires Agro API polygon
                "temperature_c": data["main"]["temp"] - 3,
            },
            "agricultural_alerts": [],
            "dew_point_c": data["main"]["temp"] - ((100 - data["main"]["humidity"]) / 5),
        }

        # Generate alerts from real data
        weather["agricultural_alerts"] = _generate_ag_alerts(
            weather["current"]["temperature_c"],
            weather["current"]["humidity_pct"],
            weather["soil"]["moisture"],
            weather["current"]["wind_speed_ms"],
        )

        logger.info(f"Fetched live weather: {weather['current']['description']}")
        return weather

    except Exception as e:
        logger.warning(f"Weather API failed ({e}), falling back to synthetic")
        return _generate_synthetic_weather(lat, lon)


def _save_weather(weather: dict):
    """Save weather data to JSON file."""
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filepath = config.WEATHER_DIR / f"weather_{timestamp}.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(weather, f, indent=2)
    logger.info(f"Saved weather data: {filepath}")


def get_latest_weather() -> dict:
    """Load the most recent weather data from file."""
    weather_files = sorted(config.WEATHER_DIR.glob("weather_*.json"), reverse=True)
    if weather_files:
        with open(weather_files[0]) as f:
            return json.load(f)
    return fetch_weather()


# ── Multi-State & International Weather ─────────────────────
GLOBAL_LOCATIONS = {
    # US Agricultural States
    "Iowa, USA":            {"lat": 41.878, "lon": -93.098, "crop": "Corn, Soybeans", "region": "US"},
    "Illinois, USA":        {"lat": 40.35,  "lon": -89.0,   "crop": "Corn, Soybeans", "region": "US"},
    "Indiana, USA":         {"lat": 39.85,  "lon": -86.26,  "crop": "Corn, Soybeans", "region": "US"},
    "Nebraska, USA":        {"lat": 41.13,  "lon": -98.27,  "crop": "Corn, Cattle",   "region": "US"},
    "Minnesota, USA":       {"lat": 45.69,  "lon": -93.90,  "crop": "Corn, Sugar Beets", "region": "US"},
    "Kansas, USA":          {"lat": 38.50,  "lon": -98.43,  "crop": "Wheat, Sorghum", "region": "US"},
    "Ohio, USA":            {"lat": 40.42,  "lon": -82.91,  "crop": "Soybeans, Corn", "region": "US"},
    "Wisconsin, USA":       {"lat": 43.79,  "lon": -88.79,  "crop": "Dairy, Corn",    "region": "US"},
    "Missouri, USA":        {"lat": 38.57,  "lon": -92.60,  "crop": "Soybeans, Corn", "region": "US"},
    "North Dakota, USA":    {"lat": 47.53,  "lon": -99.78,  "crop": "Wheat, Canola",  "region": "US"},
    "South Dakota, USA":    {"lat": 43.97,  "lon": -99.90,  "crop": "Corn, Soybeans", "region": "US"},
    "California, USA":      {"lat": 36.78,  "lon": -119.42, "crop": "Fruits, Nuts, Vegetables", "region": "US"},
    "Texas, USA":           {"lat": 31.97,  "lon": -99.90,  "crop": "Cotton, Cattle", "region": "US"},
    # International agro regions
    "Punjab, India":        {"lat": 30.90,  "lon": 75.85,   "crop": "Wheat, Rice",    "region": "Asia"},
    "São Paulo, Brazil":    {"lat": -23.55, "lon": -46.63,  "crop": "Sugarcane, Coffee", "region": "S. America"},
    "Île-de-France, France":{"lat": 48.86,  "lon": 2.35,    "crop": "Wheat, Barley",  "region": "Europe"},
    "Heilongjiang, China":  {"lat": 45.75,  "lon": 126.65,  "crop": "Rice, Soybeans", "region": "Asia"},
    "New South Wales, AU":  {"lat": -33.87, "lon": 151.21,  "crop": "Wheat, Wool",    "region": "Oceania"},
}


def fetch_multi_location_weather() -> dict:
    """
    Fetch weather for all global agricultural locations.

    Returns:
        dict keyed by location name, each value is the full weather dict
        with an extra 'location_name', 'crop', and 'region' field.
    """
    results = {}
    for name, info in GLOBAL_LOCATIONS.items():
        weather = _generate_synthetic_weather(info["lat"], info["lon"])
        weather["location_name"] = name
        weather["crop"] = info["crop"]
        weather["region"] = info["region"]
        results[name] = weather

    # Try live API for all locations if key is available
    if config.has_openweather_key():
        import requests
        for name, info in GLOBAL_LOCATIONS.items():
            try:
                url = "https://api.openweathermap.org/data/2.5/weather"
                params = {
                    "lat": info["lat"], "lon": info["lon"],
                    "appid": config.OPENWEATHERMAP_API_KEY,
                    "units": "metric",
                }
                resp = requests.get(url, params=params, timeout=5)
                if resp.ok:
                    data = resp.json()
                    results[name]["current"]["temperature_c"] = data["main"]["temp"]
                    results[name]["current"]["humidity_pct"] = data["main"]["humidity"]
                    results[name]["current"]["wind_speed_ms"] = data["wind"]["speed"]
                    results[name]["current"]["description"] = data["weather"][0]["description"]
                    results[name]["current"]["cloud_cover_pct"] = data["clouds"]["all"]
                    results[name]["source"] = "openweathermap"
            except Exception:
                pass  # Keep synthetic for this location

    # Save the combined file
    filepath = config.WEATHER_DIR / "multi_state_weather.json"
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Generated weather for {len(results)} locations")

    return results


def get_multi_location_weather() -> dict:
    """Load or generate multi-location weather."""
    filepath = config.WEATHER_DIR / "multi_state_weather.json"
    if filepath.exists():
        with open(filepath) as f:
            return json.load(f)
    return fetch_multi_location_weather()
