"""
Sentinel-2 Satellite Imagery Fetcher
=====================================
Connects to Sentinel Hub Process API for multi-spectral data.
Falls back to synthetic imagery generation when API keys are unavailable.
"""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def _generate_synthetic_sentinel(output_path: Path, seed: int = 42) -> dict:
    """
    Generate a realistic synthetic 4-band GeoTIFF simulating Sentinel-2.
    Bands: Blue (B02), Green (B03), Red (B04), NIR (B08)
    """
    import rasterio
    from rasterio.transform import from_bounds
    from rasterio.crs import CRS

    np.random.seed(seed)
    size = config.IMAGE_SIZE_PX

    # Create realistic crop field patterns using Perlin-like noise
    def _fractal_noise(shape, octaves=5, persistence=0.5):
        """Generate fractal noise for realistic terrain patterns."""
        result = np.zeros(shape)
        freq = 1.0
        amp = 1.0
        for _ in range(octaves):
            # Simple interpolated noise
            grid_h = max(2, int(shape[0] * freq / shape[0] * 8))
            grid_w = max(2, int(shape[1] * freq / shape[1] * 8))
            noise = np.random.randn(grid_h, grid_w)
            # Bilinear upsample
            from scipy.ndimage import zoom
            zoomed = zoom(noise, (shape[0] / grid_h, shape[1] / grid_w), order=1)
            result += zoomed[:shape[0], :shape[1]] * amp
            freq *= 2.0
            amp *= persistence
        # Normalize to [0, 1]
        result = (result - result.min()) / (result.max() - result.min() + 1e-8)
        return result

    base_pattern = _fractal_noise((size, size))

    # Create crop row patterns
    row_pattern = np.zeros((size, size))
    row_spacing = 12  # pixels between rows
    for i in range(0, size, row_spacing):
        row_width = 6
        start = max(0, i - row_width // 2)
        end = min(size, i + row_width // 2)
        row_pattern[start:end, :] = 1.0

    # Add some random "plots" with varying health
    plot_health = np.ones((size, size))
    n_plots = np.random.randint(4, 8)
    for _ in range(n_plots):
        cx, cy = np.random.randint(50, size - 50, 2)
        radius = np.random.randint(30, 80)
        Y, X = np.ogrid[:size, :size]
        mask = ((X - cx) ** 2 + (Y - cy) ** 2) < radius ** 2
        health_factor = np.random.uniform(0.3, 1.0)
        plot_health[mask] = health_factor

    # Combine patterns for vegetation density
    vegetation = base_pattern * 0.4 + row_pattern * 0.3 + 0.3
    vegetation *= plot_health
    vegetation = np.clip(vegetation, 0, 1)

    # Generate reflectance bands (simulating real Sentinel-2 values)
    # Healthy vegetation: low red, high NIR
    blue = (0.03 + 0.05 * (1 - vegetation) + np.random.normal(0, 0.005, (size, size))).clip(0.01, 0.3)
    green = (0.05 + 0.08 * vegetation + np.random.normal(0, 0.005, (size, size))).clip(0.01, 0.3)
    red = (0.03 + 0.12 * (1 - vegetation) + np.random.normal(0, 0.005, (size, size))).clip(0.01, 0.3)
    nir = (0.15 + 0.45 * vegetation + np.random.normal(0, 0.01, (size, size))).clip(0.05, 0.7)

    # Scale to uint16 (0-10000 like Sentinel-2 L2A)
    scale = 10000
    bands = np.stack([
        (blue * scale).astype(np.uint16),
        (green * scale).astype(np.uint16),
        (red * scale).astype(np.uint16),
        (nir * scale).astype(np.uint16),
    ])

    # Create GeoTIFF
    bbox = config.FIELD_BBOX
    transform = from_bounds(
        bbox["west"], bbox["south"], bbox["east"], bbox["north"],
        size, size
    )

    profile = {
        "driver": "GTiff",
        "dtype": "uint16",
        "width": size,
        "height": size,
        "count": 4,
        "crs": CRS.from_epsg(4326),
        "transform": transform,
        "compress": "deflate",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(str(output_path), "w", **profile) as dst:
        dst.write(bands)
        dst.set_band_description(1, "Blue (B02)")
        dst.set_band_description(2, "Green (B03)")
        dst.set_band_description(3, "Red (B04)")
        dst.set_band_description(4, "NIR (B08)")
        dst.update_tags(
            source="synthetic",
            generated=datetime.utcnow().isoformat(),
            satellite="Sentinel-2_Synthetic",
            field_lat=str(config.FIELD_LAT),
            field_lon=str(config.FIELD_LON),
        )

    metadata = {
        "source": "synthetic",
        "timestamp": datetime.utcnow().isoformat(),
        "bbox": bbox,
        "crs": "EPSG:4326",
        "resolution_m": config.SENTINEL_RESOLUTION,
        "bands": ["B02_Blue", "B03_Green", "B04_Red", "B08_NIR"],
        "size_px": size,
        "file_path": str(output_path),
    }

    logger.info(f"Generated synthetic Sentinel-2 imagery: {output_path}")
    return metadata


def fetch_sentinel_imagery(
    bbox: dict = None,
    date_from: str = None,
    date_to: str = None,
    output_dir: Path = None,
) -> dict:
    """
    Fetch Sentinel-2 imagery from Sentinel Hub API.
    Falls back to synthetic data if API keys are not configured.

    Returns:
        dict with metadata about the fetched/generated imagery.
    """
    bbox = bbox or config.FIELD_BBOX
    output_dir = output_dir or config.RAW_DIR
    date_to = date_to or datetime.utcnow().strftime("%Y-%m-%d")
    date_from = date_from or (datetime.utcnow() - timedelta(days=10)).strftime("%Y-%m-%d")

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"sentinel2_{timestamp}.tif"

    if not config.has_sentinel_key():
        logger.info("Sentinel Hub API keys not configured — generating synthetic data")
        return _generate_synthetic_sentinel(output_path, seed=hash(timestamp) % 10000)

    # ── Live Sentinel Hub API fetch ──────────────────────────
    import requests

    try:
        # Step 1: Get OAuth2 token
        token_url = "https://services.sentinel-hub.com/oauth/token"
        token_resp = requests.post(token_url, data={
            "grant_type": "client_credentials",
            "client_id": config.SENTINEL_HUB_CLIENT_ID,
            "client_secret": config.SENTINEL_HUB_CLIENT_SECRET,
        })
        token_resp.raise_for_status()
        access_token = token_resp.json()["access_token"]

        # Step 2: Process API request for 4-band data
        evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: [{bands: ["B02", "B03", "B04", "B08"], units: "DN"}],
                output: {bands: 4, sampleType: "UINT16"}
            };
        }
        function evaluatePixel(sample) {
            return [sample.B02, sample.B03, sample.B04, sample.B08];
        }
        """

        process_url = "https://services.sentinel-hub.com/api/v1/process"
        request_body = {
            "input": {
                "bounds": {
                    "bbox": [bbox["west"], bbox["south"], bbox["east"], bbox["north"]],
                    "properties": {"crs": "http://www.opengis.net/def/crs/EPSG/0/4326"},
                },
                "data": [{
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {"from": f"{date_from}T00:00:00Z", "to": f"{date_to}T23:59:59Z"},
                        "maxCloudCoverage": config.SENTINEL_MAX_CLOUD_COVER,
                    },
                }],
            },
            "output": {
                "width": config.IMAGE_SIZE_PX,
                "height": config.IMAGE_SIZE_PX,
                "responses": [{"identifier": "default", "format": {"type": "image/tiff"}}],
            },
            "evalscript": evalscript,
        }

        resp = requests.post(
            process_url,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
            json=request_body,
        )
        resp.raise_for_status()

        # Save the response as GeoTIFF
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(str(output_path), "wb") as f:
            f.write(resp.content)

        metadata = {
            "source": "sentinel-hub",
            "timestamp": datetime.utcnow().isoformat(),
            "bbox": bbox,
            "crs": "EPSG:4326",
            "resolution_m": config.SENTINEL_RESOLUTION,
            "bands": ["B02_Blue", "B03_Green", "B04_Red", "B08_NIR"],
            "size_px": config.IMAGE_SIZE_PX,
            "file_path": str(output_path),
            "date_range": {"from": date_from, "to": date_to},
        }
        logger.info(f"Fetched Sentinel-2 imagery from API: {output_path}")
        return metadata

    except Exception as e:
        logger.warning(f"Sentinel Hub API failed ({e}), falling back to synthetic data")
        return _generate_synthetic_sentinel(output_path, seed=hash(timestamp) % 10000)
