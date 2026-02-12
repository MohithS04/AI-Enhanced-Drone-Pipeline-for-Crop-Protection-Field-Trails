"""
Geospatial Processing Utilities
=================================
CRS management, tile generation, and metadata extraction.
"""

import logging
import sys
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def get_bounds(tiff_path: str) -> dict:
    """Extract geographic bounds from a GeoTIFF."""
    import rasterio
    with rasterio.open(str(tiff_path)) as src:
        bounds = src.bounds
        return {
            "west": bounds.left,
            "south": bounds.bottom,
            "east": bounds.right,
            "north": bounds.top,
            "center_lat": (bounds.top + bounds.bottom) / 2,
            "center_lon": (bounds.left + bounds.right) / 2,
            "crs": str(src.crs),
        }


def create_rgb_composite(tiff_path: str, output_path: str = None) -> str:
    """
    Create a true-color RGB composite from a 4-band GeoTIFF.
    Bands: 1=Blue, 2=Green, 3=Red, 4=NIR
    """
    import rasterio
    from PIL import Image

    tiff_path = Path(tiff_path)
    if output_path is None:
        output_path = config.PROCESSED_DIR / f"rgb_{tiff_path.stem}.png"
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with rasterio.open(str(tiff_path)) as src:
        red = src.read(3).astype(np.float32)
        green = src.read(2).astype(np.float32)
        blue = src.read(1).astype(np.float32)

    # Normalize to 0-255 with contrast stretch (2-98 percentile)
    def _normalize(band):
        p2, p98 = np.percentile(band[band > 0], [2, 98])
        clipped = np.clip((band - p2) / (p98 - p2 + 1e-8), 0, 1)
        return (clipped * 255).astype(np.uint8)

    r = _normalize(red)
    g = _normalize(green)
    b = _normalize(blue)

    rgb = np.stack([r, g, b], axis=-1)
    img = Image.fromarray(rgb)
    img.save(str(output_path))
    logger.info(f"RGB composite saved: {output_path}")
    return str(output_path)


def create_false_color_composite(tiff_path: str, output_path: str = None) -> str:
    """
    Create a false-color composite emphasizing vegetation.
    Maps NIR → Red, Red → Green, Green → Blue.
    """
    import rasterio
    from PIL import Image

    tiff_path = Path(tiff_path)
    if output_path is None:
        output_path = config.PROCESSED_DIR / f"false_color_{tiff_path.stem}.png"
    output_path = Path(output_path)

    with rasterio.open(str(tiff_path)) as src:
        nir = src.read(4).astype(np.float32)
        red = src.read(3).astype(np.float32)
        green = src.read(2).astype(np.float32)

    def _normalize(band):
        p2, p98 = np.percentile(band[band > 0], [2, 98])
        clipped = np.clip((band - p2) / (p98 - p2 + 1e-8), 0, 1)
        return (clipped * 255).astype(np.uint8)

    rgb = np.stack([_normalize(nir), _normalize(red), _normalize(green)], axis=-1)
    img = Image.fromarray(rgb)
    img.save(str(output_path))
    logger.info(f"False-color composite saved: {output_path}")
    return str(output_path)


def extract_metadata(tiff_path: str) -> dict:
    """Extract comprehensive metadata from a GeoTIFF."""
    import rasterio

    with rasterio.open(str(tiff_path)) as src:
        return {
            "file_path": str(tiff_path),
            "width": src.width,
            "height": src.height,
            "count": src.count,
            "dtype": str(src.dtypes[0]),
            "crs": str(src.crs),
            "bounds": {
                "west": src.bounds.left,
                "south": src.bounds.bottom,
                "east": src.bounds.right,
                "north": src.bounds.top,
            },
            "transform": list(src.transform)[:6],
            "resolution": {
                "x": abs(src.transform[0]),
                "y": abs(src.transform[4]),
            },
            "tags": dict(src.tags()),
            "band_descriptions": [src.descriptions[i] for i in range(src.count)],
        }


def ndvi_to_folium_overlay(ndvi_path: str) -> dict:
    """
    Prepare NDVI data for Folium overlay.
    Returns bounds and color-mapped image path.
    """
    from processing.ndvi_calculator import ndvi_to_rgb

    bounds = get_bounds(ndvi_path)
    rgb_path = ndvi_to_rgb(ndvi_path)

    return {
        "image_path": rgb_path,
        "bounds": [[bounds["south"], bounds["west"]], [bounds["north"], bounds["east"]]],
        "center": [bounds["center_lat"], bounds["center_lon"]],
    }
