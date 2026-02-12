"""
Crop Segmentation Engine
=========================
NDVI-threshold-based segmentation for crop boundary delineation.
Uses morphological operations to identify individual plots and crop rows.
"""

import logging
import sys
import json
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def segment_plots(ndvi_path: str, min_plot_area: int = 100) -> dict:
    """
    Segment individual crop plots from an NDVI image.

    Uses connected component analysis on vegetation mask
    to identify discrete plot regions.

    Args:
        ndvi_path: Path to NDVI GeoTIFF.
        min_plot_area: Minimum plot size in pixels.

    Returns:
        dict with plot geometries and statistics.
    """
    import rasterio
    from scipy import ndimage
    from skimage.morphology import opening, closing, disk
    from skimage.measure import regionprops, label

    with rasterio.open(str(ndvi_path)) as src:
        ndvi = src.read(1)
        transform = src.transform
        crs = str(src.crs)

    # Create vegetation mask (NDVI > threshold for any vegetation)
    veg_mask = (ndvi > config.NDVI_SEVERE).astype(np.uint8)

    # Morphological cleaning
    selem = disk(3)
    cleaned = closing(opening(veg_mask, selem), selem)

    # Label connected components
    labeled, n_features = ndimage.label(cleaned)

    # Extract region properties
    regions = regionprops(labeled, intensity_image=ndvi)

    plots = []
    for region in regions:
        if region.area < min_plot_area:
            continue

        # Get bounding box in pixel coordinates
        minr, minc, maxr, maxc = region.bbox

        # Convert to geo coordinates
        geo_min = rasterio.transform.xy(transform, maxr, minc, offset="center")
        geo_max = rasterio.transform.xy(transform, minr, maxc, offset="center")

        # Health classification based on mean NDVI
        mean_ndvi = region.mean_intensity
        health_class = _classify_ndvi(mean_ndvi)

        plot = {
            "id": int(region.label),
            "area_pixels": int(region.area),
            "bbox_geo": {
                "south": geo_min[1] if isinstance(geo_min, tuple) else geo_min,
                "west": geo_min[0] if isinstance(geo_min, tuple) else geo_min,
                "north": geo_max[1] if isinstance(geo_max, tuple) else geo_max,
                "east": geo_max[0] if isinstance(geo_max, tuple) else geo_max,
            },
            "centroid_pixel": {
                "row": int(region.centroid[0]),
                "col": int(region.centroid[1]),
            },
            "ndvi_stats": {
                "mean": float(mean_ndvi),
                "min": float(region.min_intensity),
                "max": float(region.max_intensity),
            },
            "health_class": health_class["class"],
            "health_color": health_class["color"],
            "eccentricity": float(region.eccentricity),
            "solidity": float(region.solidity),
        }
        plots.append(plot)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "source_file": str(ndvi_path),
        "crs": crs,
        "total_plots": len(plots),
        "plots": plots,
        "summary": _summarize_plots(plots),
        "segmentation_mask_shape": list(labeled.shape),
    }

    logger.info(f"Segmented {len(plots)} crop plots from {ndvi_path}")
    return result


def _classify_ndvi(ndvi_value: float) -> dict:
    """Classify a single NDVI value into a health category."""
    if ndvi_value > config.NDVI_HEALTHY:
        return {"class": "Healthy", "color": "#2ecc71"}
    elif ndvi_value > config.NDVI_MODERATE:
        return {"class": "Moderate Stress", "color": "#f39c12"}
    elif ndvi_value > config.NDVI_SEVERE:
        return {"class": "Severe Stress", "color": "#e74c3c"}
    else:
        return {"class": "Critical", "color": "#8e44ad"}


def _summarize_plots(plots: list) -> dict:
    """Generate summary statistics across all plots."""
    if not plots:
        return {"total": 0}

    classes = [p["health_class"] for p in plots]
    ndvi_values = [p["ndvi_stats"]["mean"] for p in plots]

    return {
        "total_plots": len(plots),
        "healthy_count": classes.count("Healthy"),
        "moderate_stress_count": classes.count("Moderate Stress"),
        "severe_stress_count": classes.count("Severe Stress"),
        "critical_count": classes.count("Critical"),
        "overall_mean_ndvi": float(np.mean(ndvi_values)),
        "overall_health": _classify_ndvi(np.mean(ndvi_values))["class"],
    }


def plots_to_geojson(segmentation_result: dict) -> dict:
    """Convert segmentation results to GeoJSON for map display."""
    features = []
    for plot in segmentation_result.get("plots", []):
        bbox = plot["bbox_geo"]
        # Create a bounding box polygon
        coords = [[
            [bbox["west"], bbox["south"]],
            [bbox["east"], bbox["south"]],
            [bbox["east"], bbox["north"]],
            [bbox["west"], bbox["north"]],
            [bbox["west"], bbox["south"]],
        ]]
        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Polygon",
                "coordinates": coords,
            },
            "properties": {
                "plot_id": plot["id"],
                "health_class": plot["health_class"],
                "health_color": plot["health_color"],
                "mean_ndvi": plot["ndvi_stats"]["mean"],
                "area_pixels": plot["area_pixels"],
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
    }
