"""
Pipeline Scheduler & Orchestrator
====================================
Monitors for new imagery and orchestrates the full processing pipeline.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def run_pipeline(image_path: str = None) -> dict:
    """
    Execute the full pipeline: ingest → NDVI → classify → store.

    Args:
        image_path: Path to input GeoTIFF. If None, fetches new imagery.

    Returns:
        dict with pipeline results and timing.
    """
    from database.db_manager import DatabaseManager
    from data_ingestion.sentinel_fetcher import fetch_sentinel_imagery
    from data_ingestion.weather_fetcher import fetch_weather
    from processing.ndvi_calculator import calculate_ndvi, ndvi_to_rgb
    from processing.geo_processor import create_rgb_composite
    from ai_models.health_classifier import classify_health
    from ai_models.segmentation import segment_plots, plots_to_geojson
    import json

    db = DatabaseManager()
    run_id = db.start_pipeline_run()
    start_time = time.time()

    try:
        # Step 1: Ingest
        if image_path:
            metadata = {
                "file_path": image_path,
                "source": "upload",
                "timestamp": datetime.utcnow().isoformat(),
                "bbox": config.FIELD_BBOX,
                "crs": "EPSG:4326",
                "bands": ["B02", "B03", "B04", "B08"],
                "size_px": config.IMAGE_SIZE_PX,
            }
        else:
            metadata = fetch_sentinel_imagery()
        img_id = db.insert_imagery(metadata)

        # Step 2: Weather
        weather = fetch_weather()
        db.insert_weather(weather)

        # Step 3: NDVI
        ndvi_result = calculate_ndvi(metadata["file_path"])
        ndvi_id = db.insert_ndvi_result(img_id, ndvi_result)
        ndvi_to_rgb(ndvi_result["output_file"])
        create_rgb_composite(metadata["file_path"])

        # Step 4: Classify & Segment
        classification = classify_health(ndvi_result["output_file"], weather)
        db.insert_health_assessment(ndvi_id, classification)

        segmentation = segment_plots(ndvi_result["output_file"])
        geojson = plots_to_geojson(segmentation)
        geojson_path = config.PROCESSED_DIR / "plots.geojson"
        with open(geojson_path, "w") as f:
            json.dump(geojson, f, indent=2)

        # Complete
        elapsed = time.time() - start_time
        db.complete_pipeline_run(
            run_id, imagery_id=img_id,
            processing_time=elapsed,
            steps="ingest,weather,ndvi,classify,segment",
        )

        logger.info(f"Pipeline completed in {elapsed:.1f}s")
        return {
            "status": "completed",
            "run_id": run_id,
            "processing_time_s": round(elapsed, 1),
            "ndvi_mean": ndvi_result["statistics"]["mean"],
            "overall_health": classification["overall_health"],
            "plots_found": segmentation["total_plots"],
            "alerts": classification.get("alerts", []),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        db.complete_pipeline_run(run_id, processing_time=elapsed, error=str(e))
        logger.error(f"Pipeline failed: {e}")
        return {"status": "failed", "error": str(e), "run_id": run_id}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    result = run_pipeline()
    print(f"\nPipeline result: {result}")
