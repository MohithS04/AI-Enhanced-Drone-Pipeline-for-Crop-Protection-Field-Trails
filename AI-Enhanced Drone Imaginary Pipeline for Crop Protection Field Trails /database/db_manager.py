"""
Database Manager — SQLite Backend
===================================
Stores pipeline metadata, NDVI results, health assessments, and weather data.
Schema mirrors PostGIS for easy migration.
"""

import json
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


class DatabaseManager:
    """SQLite manager for the pipeline's metadata store."""

    def __init__(self, db_path: str = None):
        self.db_path = str(db_path or config.DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _conn(self):
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS imagery (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    source TEXT DEFAULT 'synthetic',
                    timestamp TEXT NOT NULL,
                    bbox_west REAL, bbox_south REAL, bbox_east REAL, bbox_north REAL,
                    crs TEXT DEFAULT 'EPSG:4326',
                    width INTEGER, height INTEGER,
                    bands INTEGER DEFAULT 4,
                    metadata_json TEXT
                );

                CREATE TABLE IF NOT EXISTS ndvi_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    imagery_id INTEGER REFERENCES imagery(id),
                    file_path TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    ndvi_mean REAL, ndvi_std REAL,
                    ndvi_min REAL, ndvi_max REAL,
                    healthy_pct REAL, moderate_pct REAL,
                    severe_pct REAL, critical_pct REAL,
                    stats_json TEXT
                );

                CREATE TABLE IF NOT EXISTS health_assessments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ndvi_result_id INTEGER REFERENCES ndvi_results(id),
                    timestamp TEXT NOT NULL,
                    overall_health TEXT,
                    plot_count INTEGER,
                    healthy_count INTEGER,
                    stressed_count INTEGER,
                    critical_count INTEGER,
                    alerts_json TEXT,
                    recommendations_json TEXT
                );

                CREATE TABLE IF NOT EXISTS weather_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    source TEXT DEFAULT 'synthetic',
                    temperature_c REAL, humidity_pct REAL,
                    wind_speed_ms REAL, pressure_hpa REAL,
                    cloud_cover_pct REAL, soil_moisture REAL,
                    soil_temp_c REAL, rain_mm REAL,
                    description TEXT,
                    alerts_json TEXT,
                    full_json TEXT
                );

                CREATE TABLE IF NOT EXISTS pipeline_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    imagery_id INTEGER REFERENCES imagery(id),
                    processing_time_s REAL,
                    steps_completed TEXT,
                    error_message TEXT
                );
            """)
        logger.info("Database initialized")

    # ── Imagery ──────────────────────────────────────────────

    def insert_imagery(self, metadata: dict) -> int:
        bbox = metadata.get("bbox", {})
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO imagery (file_path, source, timestamp,
                    bbox_west, bbox_south, bbox_east, bbox_north,
                    crs, width, height, bands, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                metadata.get("file_path", ""),
                metadata.get("source", "synthetic"),
                metadata.get("timestamp", datetime.utcnow().isoformat()),
                bbox.get("west"), bbox.get("south"),
                bbox.get("east"), bbox.get("north"),
                metadata.get("crs", "EPSG:4326"),
                metadata.get("size_px", 512), metadata.get("size_px", 512),
                len(metadata.get("bands", [])),
                json.dumps(metadata),
            ))
            return cursor.lastrowid

    def get_latest_imagery(self) -> dict:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM imagery ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}

    def get_all_imagery(self, limit: int = 50) -> list:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM imagery ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    # ── NDVI Results ─────────────────────────────────────────

    def insert_ndvi_result(self, imagery_id: int, result: dict) -> int:
        stats = result.get("statistics", {})
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO ndvi_results (imagery_id, file_path, timestamp,
                    ndvi_mean, ndvi_std, ndvi_min, ndvi_max,
                    healthy_pct, moderate_pct, severe_pct, critical_pct, stats_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                imagery_id,
                result.get("output_file", ""),
                result.get("timestamp", datetime.utcnow().isoformat()),
                stats.get("mean"), stats.get("std"),
                stats.get("min"), stats.get("max"),
                stats.get("healthy_pct"), stats.get("moderate_stress_pct"),
                stats.get("severe_stress_pct"), stats.get("critical_pct"),
                json.dumps(stats),
            ))
            return cursor.lastrowid

    def get_ndvi_history(self, limit: int = 30) -> list:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM ndvi_results ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_ndvi(self) -> dict:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM ndvi_results ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}

    # ── Health Assessments ───────────────────────────────────

    def insert_health_assessment(self, ndvi_result_id: int, assessment: dict) -> int:
        summary = assessment.get("percentages", {})
        seg_summary = {}
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO health_assessments (ndvi_result_id, timestamp,
                    overall_health, plot_count, healthy_count,
                    stressed_count, critical_count,
                    alerts_json, recommendations_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ndvi_result_id,
                assessment.get("timestamp", datetime.utcnow().isoformat()),
                assessment.get("overall_health", "Unknown"),
                0,  # plot_count from segmentation
                int(assessment.get("pixel_counts", {}).get("healthy", 0)),
                int(assessment.get("pixel_counts", {}).get("moderate_stress", 0) +
                    assessment.get("pixel_counts", {}).get("severe_stress", 0)),
                int(assessment.get("pixel_counts", {}).get("critical", 0)),
                json.dumps(assessment.get("alerts", [])),
                json.dumps(assessment.get("recommendations", [])),
            ))
            return cursor.lastrowid

    def get_latest_health(self) -> dict:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM health_assessments ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}

    # ── Weather ──────────────────────────────────────────────

    def insert_weather(self, weather: dict) -> int:
        current = weather.get("current", {})
        soil = weather.get("soil", {})
        precip = weather.get("precipitation", {})
        with self._conn() as conn:
            cursor = conn.execute("""
                INSERT INTO weather_data (timestamp, source,
                    temperature_c, humidity_pct, wind_speed_ms, pressure_hpa,
                    cloud_cover_pct, soil_moisture, soil_temp_c, rain_mm,
                    description, alerts_json, full_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                weather.get("timestamp", datetime.utcnow().isoformat()),
                weather.get("source", "synthetic"),
                current.get("temperature_c"), current.get("humidity_pct"),
                current.get("wind_speed_ms"), current.get("pressure_hpa"),
                current.get("cloud_cover_pct"),
                soil.get("moisture"), soil.get("temperature_c"),
                precip.get("rain_mm"),
                current.get("description", ""),
                json.dumps(weather.get("agricultural_alerts", [])),
                json.dumps(weather),
            ))
            return cursor.lastrowid

    def get_weather_history(self, limit: int = 48) -> list:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM weather_data ORDER BY timestamp DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_weather(self) -> dict:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM weather_data ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else {}

    # ── Pipeline Runs ────────────────────────────────────────

    def start_pipeline_run(self) -> int:
        with self._conn() as conn:
            cursor = conn.execute(
                "INSERT INTO pipeline_runs (start_time, status) VALUES (?, 'running')",
                (datetime.utcnow().isoformat(),),
            )
            return cursor.lastrowid

    def complete_pipeline_run(self, run_id: int, imagery_id: int = None,
                               processing_time: float = 0, steps: str = "",
                               error: str = None):
        status = "failed" if error else "completed"
        with self._conn() as conn:
            conn.execute("""
                UPDATE pipeline_runs
                SET end_time=?, status=?, imagery_id=?,
                    processing_time_s=?, steps_completed=?, error_message=?
                WHERE id=?
            """, (
                datetime.utcnow().isoformat(), status, imagery_id,
                processing_time, steps, error, run_id,
            ))

    def get_pipeline_history(self, limit: int = 20) -> list:
        with self._conn() as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM pipeline_runs ORDER BY start_time DESC LIMIT ?",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_pipeline_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
            completed = conn.execute(
                "SELECT COUNT(*) FROM pipeline_runs WHERE status='completed'"
            ).fetchone()[0]
            avg_time = conn.execute(
                "SELECT AVG(processing_time_s) FROM pipeline_runs WHERE status='completed'"
            ).fetchone()[0]
            return {
                "total_runs": total,
                "completed": completed,
                "failed": total - completed,
                "avg_processing_time_s": round(avg_time, 2) if avg_time else 0,
                "success_rate": round(completed / total * 100, 1) if total > 0 else 0,
            }
