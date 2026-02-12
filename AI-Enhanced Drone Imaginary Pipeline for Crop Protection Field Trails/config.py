"""
Central configuration for the AI-Enhanced Drone Imagery Pipeline.
Loads settings from .env file with sensible defaults.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ── Project Paths ────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
WEATHER_DIR = DATA_DIR / "weather"
TILES_DIR = DATA_DIR / "tiles"
DB_PATH = DATA_DIR / "pipeline.db"
MODELS_DIR = PROJECT_ROOT / "models"

# Create directories
for d in [RAW_DIR, PROCESSED_DIR, WEATHER_DIR, TILES_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── API Keys ─────────────────────────────────────────────────
OPENWEATHERMAP_API_KEY = os.getenv("OPENWEATHERMAP_API_KEY", "")
SENTINEL_HUB_CLIENT_ID = os.getenv("SENTINEL_HUB_CLIENT_ID", "")
SENTINEL_HUB_CLIENT_SECRET = os.getenv("SENTINEL_HUB_CLIENT_SECRET", "")

# ── Field Coordinates ────────────────────────────────────────
FIELD_LAT = float(os.getenv("FIELD_LAT", "41.878"))
FIELD_LON = float(os.getenv("FIELD_LON", "-93.098"))
FIELD_BBOX_SIZE_KM = float(os.getenv("FIELD_BBOX_SIZE_KM", "2.0"))

# Compute bounding box (approx degrees per km at mid-latitudes)
_DEG_PER_KM_LAT = 1 / 111.0
_DEG_PER_KM_LON = 1 / (111.0 * 0.75)  # ~cos(42°)
HALF_SIZE = FIELD_BBOX_SIZE_KM / 2.0

FIELD_BBOX = {
    "west": FIELD_LON - HALF_SIZE * _DEG_PER_KM_LON,
    "south": FIELD_LAT - HALF_SIZE * _DEG_PER_KM_LAT,
    "east": FIELD_LON + HALF_SIZE * _DEG_PER_KM_LON,
    "north": FIELD_LAT + HALF_SIZE * _DEG_PER_KM_LAT,
}

# ── NDVI Thresholds ──────────────────────────────────────────
NDVI_HEALTHY = float(os.getenv("NDVI_HEALTHY_THRESHOLD", "0.6"))
NDVI_MODERATE = float(os.getenv("NDVI_MODERATE_THRESHOLD", "0.3"))
NDVI_SEVERE = float(os.getenv("NDVI_SEVERE_THRESHOLD", "0.1"))

HEALTH_CLASSES = {
    "Healthy":         {"min": NDVI_HEALTHY, "max": 1.0,           "color": "#2ecc71"},
    "Moderate Stress": {"min": NDVI_MODERATE, "max": NDVI_HEALTHY, "color": "#f39c12"},
    "Severe Stress":   {"min": NDVI_SEVERE,  "max": NDVI_MODERATE, "color": "#e74c3c"},
    "Critical":        {"min": -1.0,         "max": NDVI_SEVERE,   "color": "#8e44ad"},
}

# ── Processing Settings ──────────────────────────────────────
AUTO_REFRESH_SECONDS = int(os.getenv("AUTO_REFRESH_SECONDS", "300"))
CRS_TARGET = "EPSG:4326"
SENTINEL_BANDS = {"B02": "Blue", "B03": "Green", "B04": "Red", "B08": "NIR"}
IMAGE_SIZE_PX = 512  # Default output image dimension

# ── Sentinel-2 Defaults ─────────────────────────────────────
SENTINEL_RESOLUTION = 10  # meters per pixel
SENTINEL_MAX_CLOUD_COVER = 20  # percent

def has_openweather_key() -> bool:
    return bool(OPENWEATHERMAP_API_KEY) and OPENWEATHERMAP_API_KEY != "your_api_key_here"

def has_sentinel_key() -> bool:
    return (bool(SENTINEL_HUB_CLIENT_ID) and SENTINEL_HUB_CLIENT_ID != "your_client_id_here"
            and bool(SENTINEL_HUB_CLIENT_SECRET) and SENTINEL_HUB_CLIENT_SECRET != "your_client_secret_here")
