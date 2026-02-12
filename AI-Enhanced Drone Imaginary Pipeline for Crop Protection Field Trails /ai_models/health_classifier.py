"""
Crop Health Classifier
=======================
Classifies crop health per-plot using NDVI ranges and weather context.
Generates actionable recommendations based on combined analysis.
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def classify_health(ndvi_path: str, weather_data: dict = None) -> dict:
    """
    Classify overall field health from NDVI image and weather context.

    Args:
        ndvi_path: Path to NDVI GeoTIFF.
        weather_data: Optional weather dict for cross-reference alerts.

    Returns:
        dict with per-class statistics, alerts, and recommendations.
    """
    import rasterio

    with rasterio.open(str(ndvi_path)) as src:
        ndvi = src.read(1)

    valid = ndvi[ndvi > -9999]

    # Per-class pixel counts
    healthy = (valid > config.NDVI_HEALTHY).sum()
    moderate = ((valid > config.NDVI_MODERATE) & (valid <= config.NDVI_HEALTHY)).sum()
    severe = ((valid > config.NDVI_SEVERE) & (valid <= config.NDVI_MODERATE)).sum()
    critical = (valid <= config.NDVI_SEVERE).sum()
    total = valid.size

    classification = {
        "timestamp": datetime.utcnow().isoformat(),
        "source_file": str(ndvi_path),
        "pixel_counts": {
            "healthy": int(healthy),
            "moderate_stress": int(moderate),
            "severe_stress": int(severe),
            "critical": int(critical),
            "total": int(total),
        },
        "percentages": {
            "healthy": round(healthy / total * 100, 1) if total > 0 else 0,
            "moderate_stress": round(moderate / total * 100, 1) if total > 0 else 0,
            "severe_stress": round(severe / total * 100, 1) if total > 0 else 0,
            "critical": round(critical / total * 100, 1) if total > 0 else 0,
        },
        "overall_ndvi": {
            "mean": float(np.mean(valid)),
            "std": float(np.std(valid)),
            "min": float(np.min(valid)),
            "max": float(np.max(valid)),
        },
        "overall_health": _overall_health(healthy, moderate, severe, critical, total),
        "alerts": [],
        "recommendations": [],
    }

    # Weather-correlated alerts
    if weather_data:
        classification["alerts"] = _weather_correlated_alerts(
            classification, weather_data
        )

    # Actionable recommendations
    classification["recommendations"] = _generate_recommendations(classification)

    logger.info(
        f"Health classified: {classification['overall_health']} "
        f"(healthy={classification['percentages']['healthy']}%)"
    )
    return classification


def _overall_health(healthy, moderate, severe, critical, total) -> str:
    """Determine overall field health label."""
    if total == 0:
        return "No Data"
    healthy_pct = healthy / total
    if healthy_pct > 0.7:
        return "Good"
    elif healthy_pct > 0.5:
        return "Fair"
    elif healthy_pct > 0.3:
        return "Poor"
    else:
        return "Critical"


def _weather_correlated_alerts(classification: dict, weather: dict) -> list:
    """Cross-reference vegetation health with weather for smarter alerts."""
    alerts = []
    soil = weather.get("soil", {})
    current = weather.get("current", {})
    pcts = classification["percentages"]

    # Drought + low NDVI
    soil_moisture = soil.get("moisture", 0.5)
    if soil_moisture < 0.2 and pcts["severe_stress"] + pcts["critical"] > 30:
        alerts.append({
            "type": "CRITICAL",
            "title": "Drought Stress Detected",
            "message": (
                f"Soil moisture at {soil_moisture:.0%} combined with "
                f"{pcts['severe_stress'] + pcts['critical']:.0f}% stressed vegetation. "
                "Immediate irrigation required."
            ),
            "icon": "🚨",
        })

    # High humidity + stressed plants = disease risk
    humidity = current.get("humidity_pct", 50)
    temp = current.get("temperature_c", 20)
    if humidity > 80 and temp > 18 and pcts["moderate_stress"] > 20:
        alerts.append({
            "type": "WARNING",
            "title": "Disease Risk Elevated",
            "message": (
                f"Humidity at {humidity:.0f}% and temp at {temp:.1f}°C with "
                f"{pcts['moderate_stress']:.0f}% moderately stressed vegetation. "
                "Scout for fungal pathogens."
            ),
            "icon": "⚠️",
        })

    # Frost after green-up
    if temp < 2 and pcts["healthy"] > 30:
        alerts.append({
            "type": "WARNING",
            "title": "Frost Damage Risk",
            "message": (
                f"Temperature at {temp:.1f}°C with active vegetation. "
                "Risk of frost damage to growing crop."
            ),
            "icon": "🥶",
        })

    return alerts


def _generate_recommendations(classification: dict) -> list:
    """Generate actionable recommendations based on classification results."""
    recs = []
    pcts = classification["percentages"]

    if pcts["critical"] > 15:
        recs.append({
            "priority": "HIGH",
            "action": "Field Inspection",
            "detail": (
                f"{pcts['critical']:.0f}% of field is in critical condition. "
                "Deploy ground crew for immediate visual inspection."
            ),
        })

    if pcts["severe_stress"] > 25:
        recs.append({
            "priority": "HIGH",
            "action": "Soil & Nutrient Test",
            "detail": (
                "Significant stress detected. Recommend soil sampling to "
                "identify possible nutrient deficiency or pH imbalance."
            ),
        })

    if pcts["moderate_stress"] > 30:
        recs.append({
            "priority": "MEDIUM",
            "action": "Targeted Treatment",
            "detail": (
                "Apply variable-rate fertilizer or irrigation to "
                "moderately stressed zones to prevent further decline."
            ),
        })

    if pcts["healthy"] > 70:
        recs.append({
            "priority": "LOW",
            "action": "Routine Monitoring",
            "detail": (
                "Field is predominantly healthy. Continue scheduled "
                "monitoring and maintain current management practices."
            ),
        })

    if not recs:
        recs.append({
            "priority": "MEDIUM",
            "action": "Schedule Next Scan",
            "detail": "Re-scan in 3-5 days to track vegetation trends.",
        })

    return recs
