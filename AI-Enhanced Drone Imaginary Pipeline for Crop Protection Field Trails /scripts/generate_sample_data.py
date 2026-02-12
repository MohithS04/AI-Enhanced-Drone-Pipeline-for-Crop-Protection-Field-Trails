"""
Sample Data Generator
======================
Creates synthetic satellite imagery, weather data, and populates the database
for a complete working demo without any API keys.
"""

import json
import logging
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def generate_all():
    """Generate a complete set of demo data."""
    logger.info("=" * 60)
    logger.info("Generating sample data for the Crop Health Pipeline")
    logger.info("=" * 60)

    start = time.time()

    # Initialize database
    from database.db_manager import DatabaseManager
    db = DatabaseManager()

    # Step 1: Generate multiple satellite images (simulating time series)
    logger.info("\n📡 Step 1/5: Generating Sentinel-2 satellite imagery...")
    from data_ingestion.sentinel_fetcher import fetch_sentinel_imagery

    imagery_records = []
    for i in range(5):
        seed = 42 + i * 100
        metadata = fetch_sentinel_imagery()
        img_id = db.insert_imagery(metadata)
        imagery_records.append({"id": img_id, "metadata": metadata})
        logger.info(f"  ✅ Image {i+1}/5 generated: {metadata['file_path']}")

    # Step 2: Calculate NDVI for each image
    logger.info("\n🌿 Step 2/5: Computing NDVI indices...")
    from processing.ndvi_calculator import calculate_ndvi, ndvi_to_rgb

    ndvi_records = []
    for rec in imagery_records:
        result = calculate_ndvi(rec["metadata"]["file_path"])
        ndvi_id = db.insert_ndvi_result(rec["id"], result)
        ndvi_records.append({"id": ndvi_id, "result": result})
        # Also create RGB visualization
        ndvi_to_rgb(result["output_file"])
        logger.info(
            f"  ✅ NDVI computed: mean={result['statistics']['mean']:.3f}, "
            f"healthy={result['statistics']['healthy_pct']:.1f}%"
        )

    # Step 3: Create visual composites
    logger.info("\n🎨 Step 3/5: Creating visual composites...")
    from processing.geo_processor import create_rgb_composite, create_false_color_composite

    latest_img = imagery_records[-1]["metadata"]["file_path"]
    rgb_path = create_rgb_composite(latest_img)
    fc_path = create_false_color_composite(latest_img)
    logger.info(f"  ✅ RGB composite: {rgb_path}")
    logger.info(f"  ✅ False-color composite: {fc_path}")

    # Step 4: Run health classification and segmentation
    logger.info("\n🔬 Step 4/5: Running AI health classification & segmentation...")
    from ai_models.health_classifier import classify_health
    from ai_models.segmentation import segment_plots, plots_to_geojson

    for ndvi_rec in ndvi_records:
        # Classify health
        classification = classify_health(ndvi_rec["result"]["output_file"])
        db.insert_health_assessment(ndvi_rec["id"], classification)
        logger.info(
            f"  ✅ Health: {classification['overall_health']} | "
            f"Healthy: {classification['percentages']['healthy']:.0f}% | "
            f"Stressed: {classification['percentages']['moderate_stress']:.0f}%"
        )

    # Segment the latest image
    latest_ndvi = ndvi_records[-1]["result"]["output_file"]
    segmentation = segment_plots(latest_ndvi)
    geojson = plots_to_geojson(segmentation)

    # Save GeoJSON
    geojson_path = config.PROCESSED_DIR / "plots.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2)
    logger.info(f"  ✅ Segmented {segmentation['total_plots']} plots → {geojson_path}")

    # Step 5: Generate weather history
    logger.info("\n🌤️  Step 5/5: Generating weather time series...")
    from data_ingestion.weather_fetcher import fetch_weather

    for i in range(24):
        weather = fetch_weather(save=True)
        db.insert_weather(weather)

    logger.info(f"  ✅ Generated 24 weather records")

    # Record pipeline run
    run_id = db.start_pipeline_run()
    elapsed = time.time() - start
    db.complete_pipeline_run(
        run_id,
        imagery_id=imagery_records[-1]["id"],
        processing_time=elapsed,
        steps="ingest,ndvi,composite,classify,segment,weather",
    )

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("✅ Sample data generation complete!")
    logger.info(f"⏱  Total time: {elapsed:.1f}s")
    logger.info(f"📂 Data directory: {config.DATA_DIR}")
    logger.info(f"🗃  Database: {config.DB_PATH}")
    logger.info(f"🖼  Images: {len(imagery_records)} GeoTIFFs")
    logger.info(f"🌿 NDVI maps: {len(ndvi_records)}")
    logger.info(f"🔬 Plots segmented: {segmentation['total_plots']}")
    logger.info("=" * 60)
    logger.info("\n🚀 Run the dashboard with: streamlit run app.py")

    return {
        "imagery_count": len(imagery_records),
        "ndvi_count": len(ndvi_records),
        "plots_segmented": segmentation["total_plots"],
        "weather_records": 24,
        "processing_time_s": round(elapsed, 1),
    }


if __name__ == "__main__":
    generate_all()
