"""
NDVI (Normalized Difference Vegetation Index) Calculator
=========================================================
Processes multi-band GeoTIFF imagery to produce NDVI maps.
NDVI = (NIR - Red) / (NIR + Red)
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def calculate_ndvi(input_path: str, output_path: str = None) -> dict:
    """
    Calculate NDVI from a 4-band GeoTIFF (B02, B03, B04, B08).

    Args:
        input_path: Path to input multi-band GeoTIFF.
        output_path: Path for output NDVI GeoTIFF. Auto-generated if None.

    Returns:
        dict with NDVI statistics and file paths.
    """
    import rasterio

    input_path = Path(input_path)
    if output_path is None:
        output_path = config.PROCESSED_DIR / f"ndvi_{input_path.stem}.tif"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(input_path)) as src:
        # Band order: 1=Blue, 2=Green, 3=Red, 4=NIR
        red = src.read(3).astype(np.float32)
        nir = src.read(4).astype(np.float32)
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs

    # Calculate NDVI
    denominator = nir + red
    ndvi = np.where(
        denominator > 0,
        (nir - red) / denominator,
        0.0  # No-data where both bands are 0
    )
    ndvi = ndvi.clip(-1.0, 1.0).astype(np.float32)

    # Write NDVI GeoTIFF
    profile.update(
        dtype="float32",
        count=1,
        compress="deflate",
        nodata=-9999,
    )

    with rasterio.open(str(output_path), "w", **profile) as dst:
        dst.write(ndvi, 1)
        dst.set_band_description(1, "NDVI")
        dst.update_tags(
            ndvi_formula="(NIR - Red) / (NIR + Red)",
            source_file=str(input_path),
            processed=datetime.utcnow().isoformat(),
        )

    # Compute statistics
    valid = ndvi[ndvi > -9999]
    stats = {
        "min": float(np.min(valid)),
        "max": float(np.max(valid)),
        "mean": float(np.mean(valid)),
        "std": float(np.std(valid)),
        "median": float(np.median(valid)),
        "p25": float(np.percentile(valid, 25)),
        "p75": float(np.percentile(valid, 75)),
        "healthy_pct": float((valid > config.NDVI_HEALTHY).mean() * 100),
        "moderate_stress_pct": float(
            ((valid > config.NDVI_MODERATE) & (valid <= config.NDVI_HEALTHY)).mean() * 100
        ),
        "severe_stress_pct": float(
            ((valid > config.NDVI_SEVERE) & (valid <= config.NDVI_MODERATE)).mean() * 100
        ),
        "critical_pct": float((valid <= config.NDVI_SEVERE).mean() * 100),
        "total_pixels": int(valid.size),
    }

    result = {
        "input_file": str(input_path),
        "output_file": str(output_path),
        "timestamp": datetime.utcnow().isoformat(),
        "statistics": stats,
        "crs": str(crs),
    }

    logger.info(
        f"NDVI calculated: mean={stats['mean']:.3f}, "
        f"healthy={stats['healthy_pct']:.1f}%, "
        f"stressed={stats['moderate_stress_pct'] + stats['severe_stress_pct']:.1f}%"
    )
    return result


def ndvi_to_rgb(ndvi_path: str, output_path: str = None) -> str:
    """
    Convert NDVI GeoTIFF to a color-mapped RGB image for visualization.
    Uses a Red-Yellow-Green gradient matching health classification thresholds.
    """
    import rasterio
    from PIL import Image

    ndvi_path = Path(ndvi_path)
    if output_path is None:
        output_path = config.PROCESSED_DIR / f"ndvi_rgb_{ndvi_path.stem}.png"
    output_path = Path(output_path)

    with rasterio.open(str(ndvi_path)) as src:
        ndvi = src.read(1)

    # Define colormap: Critical → Severe → Moderate → Healthy
    height, width = ndvi.shape
    rgb = np.zeros((height, width, 3), dtype=np.uint8)

    # Critical (purple)
    mask = ndvi <= config.NDVI_SEVERE
    rgb[mask] = [142, 68, 173]

    # Severe stress (red-orange)
    mask = (ndvi > config.NDVI_SEVERE) & (ndvi <= config.NDVI_MODERATE)
    rgb[mask] = [231, 76, 60]

    # Moderate stress (yellow-orange)
    mask = (ndvi > config.NDVI_MODERATE) & (ndvi <= config.NDVI_HEALTHY)
    t = (ndvi[mask] - config.NDVI_MODERATE) / (config.NDVI_HEALTHY - config.NDVI_MODERATE + 1e-8)
    rgb[mask, 0] = (243 * (1 - t) + 46 * t).clip(0, 255).astype(np.uint8)
    rgb[mask, 1] = (156 * (1 - t) + 204 * t).clip(0, 255).astype(np.uint8)
    rgb[mask, 2] = (18 * (1 - t) + 113 * t).clip(0, 255).astype(np.uint8)

    # Healthy (green)
    mask = ndvi > config.NDVI_HEALTHY
    rgb[mask] = [46, 204, 113]

    img = Image.fromarray(rgb)
    img.save(str(output_path))
    logger.info(f"NDVI RGB saved: {output_path}")
    return str(output_path)


def get_ndvi_array(ndvi_path: str) -> np.ndarray:
    """Load NDVI values as a numpy array."""
    import rasterio
    with rasterio.open(str(ndvi_path)) as src:
        return src.read(1)
