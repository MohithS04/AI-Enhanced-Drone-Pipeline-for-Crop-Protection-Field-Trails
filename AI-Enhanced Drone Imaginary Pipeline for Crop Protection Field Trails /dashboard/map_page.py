"""
Live Map Dashboard Page
========================
Interactive Leaflet map with NDVI overlay, health polygons,
country/state boundaries, and multi-location weather.
"""

import json
import sys
from pathlib import Path

import streamlit as st
import folium
from streamlit_folium import st_folium
from folium.plugins import MiniMap
import numpy as np
import branca.colormap as cm

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def render():
    """Render the Live Map page."""
    st.markdown("""
    <h1 style='background: linear-gradient(135deg, #60a5fa, #34d399);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800; font-size: 2rem; margin-bottom: 0;'>
    🗺️ Live Field Map
    </h1>
    <p style='color: #64748b; margin-top: 0.2rem;'>
    Interactive geospatial view with country &amp; state boundaries, weather, NDVI overlay, and crop health
    </p>
    """, unsafe_allow_html=True)

    # ── Map Controls ─────────────────────────────────────────
    ctrl1, ctrl2, ctrl3, ctrl4, ctrl5 = st.columns(5)
    with ctrl1:
        zoom_level = st.selectbox(
            "🔍 View Scale",
            ["🌍 World", "🇺🇸 Country", "🏛️ State", "🌾 Field"],
            index=3,
        )
    with ctrl2:
        show_ndvi = st.toggle("🌿 NDVI Overlay", value=True)
    with ctrl3:
        show_plots = st.toggle("📐 Plot Boundaries", value=True)
    with ctrl4:
        show_weather = st.toggle("🌤️ Weather Markers", value=True)
    with ctrl5:
        show_field_wx = st.toggle("📍 Field Weather", value=True)

    # ── Determine zoom and center ────────────────────────────
    center_lat = config.FIELD_LAT
    center_lon = config.FIELD_LON

    if zoom_level == "🌍 World":
        zoom = 2
        center_lat, center_lon = 25.0, 10.0
    elif zoom_level == "🇺🇸 Country":
        zoom = 4
        center_lat, center_lon = 39.5, -98.35
    elif zoom_level == "🏛️ State":
        zoom = 7
        center_lat, center_lon = config.FIELD_LAT, config.FIELD_LON
    else:
        zoom = 14

    # ── Fetch multi-location weather ─────────────────────────
    from data_ingestion.weather_fetcher import get_multi_location_weather, GLOBAL_LOCATIONS
    multi_weather = get_multi_location_weather() if show_weather else {}

    # ── Create Folium Map ────────────────────────────────────
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom,
        tiles=None,
        control_scale=True,
    )

    # ── Base Tile Layers ─────────────────────────────────────
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
        attr="CartoDB Voyager",
        name="🗺️ Standard",
        max_zoom=19,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CartoDB Dark",
        name="🌑 Dark Mode",
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri Satellite",
        name="🛰️ Satellite",
    ).add_to(m)

    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/stamen_terrain/{z}/{x}/{y}{r}.png",
        attr="Stamen Terrain via Stadia",
        name="⛰️ Terrain",
    ).add_to(m)

    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="OpenStreetMap",
        name="🏘️ Street Map",
    ).add_to(m)

    # ── Boundary Overlays ────────────────────────────────────
    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/stamen_toner_lines/{z}/{x}/{y}{r}.png",
        attr="Stamen Toner Lines via Stadia",
        name="📐 Boundaries",
        overlay=True, control=True, opacity=0.4,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://tiles.stadiamaps.com/tiles/stamen_toner_labels/{z}/{x}/{y}{r}.png",
        attr="Stamen Toner Labels via Stadia",
        name="🏷️ Labels",
        overlay=True, control=True, opacity=0.7,
    ).add_to(m)

    # ── Weather Markers for All Locations ────────────────────
    if show_weather and multi_weather:
        # US weather group
        us_group = folium.FeatureGroup(name="🇺🇸 US Weather")
        intl_group = folium.FeatureGroup(name="🌍 Global Weather")

        for name, wx in multi_weather.items():
            loc_info = GLOBAL_LOCATIONS.get(name, {})
            lat = loc_info.get("lat", 0)
            lon = loc_info.get("lon", 0)
            region = wx.get("region", "US")
            crop = wx.get("crop", "")
            current = wx.get("current", {})

            temp = current.get("temperature_c", 0)
            humidity = current.get("humidity_pct", 0)
            wind = current.get("wind_speed_ms", 0)
            desc = current.get("description", "N/A")
            clouds = current.get("cloud_cover_pct", 0)
            soil = wx.get("soil", {})
            soil_m = soil.get("moisture", 0)
            soil_t = soil.get("temperature_c", 0)
            rain = wx.get("precipitation", {}).get("rain_mm", 0)
            alerts = wx.get("agricultural_alerts", [])

            # Choose icon based on conditions
            if rain > 1:
                wx_icon = "🌧️"
            elif clouds > 70:
                wx_icon = "☁️"
            elif clouds > 30:
                wx_icon = "⛅"
            elif temp > 35:
                wx_icon = "🔥"
            elif temp < 0:
                wx_icon = "❄️"
            else:
                wx_icon = "☀️"

            # Temperature color
            if temp > 35:
                temp_color = "#ef4444"
            elif temp > 25:
                temp_color = "#f59e0b"
            elif temp > 10:
                temp_color = "#2ecc71"
            elif temp > 0:
                temp_color = "#3b82f6"
            else:
                temp_color = "#8b5cf6"

            # Alert badges
            alert_html = ""
            for alert in alerts[:2]:
                atype = alert.get("type", "INFO")
                acolor = "#ef4444" if atype == "CRITICAL" else "#f59e0b" if atype == "WARNING" else "#2ecc71"
                alert_html += f"""<span style='display:inline-block; background:{acolor}22;
                    color:{acolor}; padding: 2px 6px; border-radius:4px;
                    font-size:10px; margin: 2px 1px;'>{alert.get('category','').title()}</span>"""

            # Build popup
            is_active = (name == "Iowa, USA")
            popup_html = f"""
            <div style='font-family: Inter, sans-serif; min-width: 260px; padding: 4px;'>
                <h3 style='margin: 0 0 4px 0; color: #1e3a5f; font-size: 15px;
                border-bottom: 2px solid {"#2ecc71" if is_active else "#3b82f6"};
                padding-bottom: 4px;'>
                    {wx_icon} {name} {'🟢' if is_active else ''}
                </h3>
                <p style='margin: 2px 0; color: #64748b; font-size: 11px;'>
                    🌾 {crop} &nbsp;|&nbsp; 📍 {lat:.2f}°, {lon:.2f}°
                </p>
                <table style='width:100%; font-size:12px; border-collapse:collapse; margin: 6px 0;'>
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding:3px;'>🌡️ <b>Temperature</b></td>
                        <td style='text-align:right; color:{temp_color}; font-weight:700;'>{temp:.1f}°C</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding:3px;'>💧 <b>Humidity</b></td>
                        <td style='text-align:right;'>{humidity:.0f}%</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding:3px;'>💨 <b>Wind</b></td>
                        <td style='text-align:right;'>{wind:.1f} m/s</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding:3px;'>🌧️ <b>Rain</b></td>
                        <td style='text-align:right;'>{rain:.1f} mm</td>
                    </tr>
                    <tr style='border-bottom: 1px solid #eee;'>
                        <td style='padding:3px;'>🌱 <b>Soil Moisture</b></td>
                        <td style='text-align:right;'>{soil_m:.0%}</td>
                    </tr>
                    <tr>
                        <td style='padding:3px;'>🌍 <b>Soil Temp</b></td>
                        <td style='text-align:right;'>{soil_t:.1f}°C</td>
                    </tr>
                </table>
                <div style='margin: 4px 0;'>{alert_html}</div>
                <p style='margin: 2px 0; color: #94a3b8; font-size: 10px;
                text-align:right;'>☁️ {desc.title()}</p>
            </div>
            """

            # Marker icon
            if is_active:
                icon = folium.Icon(color="green", icon="leaf", prefix="fa")
            else:
                icon = folium.Icon(color="cadetblue", icon="cloud", prefix="fa")

            marker = folium.Marker(
                location=[lat, lon],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{wx_icon} {name}: {temp:.0f}°C, {desc}",
                icon=icon,
            )

            if region == "US":
                marker.add_to(us_group)
            else:
                marker.add_to(intl_group)

        us_group.add_to(m)
        intl_group.add_to(m)

    # ── NDVI Image Overlay ───────────────────────────────────
    if show_ndvi:
        _add_ndvi_overlay(m)

    # ── Plot Boundaries from GeoJSON ─────────────────────────
    if show_plots:
        _add_plot_boundaries(m)

    # ── Field Weather Marker ─────────────────────────────────
    if show_field_wx:
        _add_weather_marker(m, config.FIELD_LAT, config.FIELD_LON)

    # ── Field boundary rectangle ─────────────────────────────
    bbox = config.FIELD_BBOX
    folium.Rectangle(
        bounds=[[bbox["south"], bbox["west"]], [bbox["north"], bbox["east"]]],
        color="#3b82f6", weight=2, fill=False, dash_array="10",
        tooltip="📐 Monitored Field Boundary (Iowa Corn Belt)",
    ).add_to(m)

    # ── NDVI Colorbar ────────────────────────────────────────
    colormap = cm.LinearColormap(
        colors=["#8e44ad", "#e74c3c", "#f59e0b", "#2ecc71"],
        vmin=-0.1, vmax=0.8,
        caption="NDVI (Vegetation Health Index)",
    )
    colormap.add_to(m)

    # ── Mini Map ─────────────────────────────────────────────
    minimap = MiniMap(
        tile_layer=folium.TileLayer(
            tiles="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
            attr="CartoDB",
        ),
        toggle_display=True, position="bottomleft",
        width=150, height=150, zoom_level_offset=-5,
    )
    m.add_child(minimap)

    # ── Layer Control ────────────────────────────────────────
    folium.LayerControl(collapsed=False).add_to(m)

    # ── Render Map ───────────────────────────────────────────
    map_data = st_folium(m, width=None, height=650, returned_objects=[])

    # ── Map Legend ───────────────────────────────────────────
    st.markdown("""
    <div style='display: flex; gap: 1.5rem; justify-content: center; flex-wrap: wrap;
    padding: 0.8rem 1rem; background: rgba(26,31,46,0.6); border-radius: 12px; margin-top: 0.5rem;'>
        <span>🟢 <strong style='color: #2ecc71;'>Healthy</strong> (NDVI > 0.6)</span>
        <span>🟡 <strong style='color: #f59e0b;'>Moderate</strong> (0.3-0.6)</span>
        <span>🔴 <strong style='color: #e74c3c;'>Severe</strong> (0.1-0.3)</span>
        <span>🟣 <strong style='color: #8e44ad;'>Critical</strong> (< 0.1)</span>
        <span>☀️ <strong style='color: #3b82f6;'>Weather</strong> — click markers</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Field Info Panel ─────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    i1, i2, i3, i4 = st.columns(4)
    with i1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Field Location</div>
            <div style='color: #3b82f6; font-size: 1rem; font-family: JetBrains Mono;'>Iowa, USA</div>
            <div style='color: #64748b; font-size: 0.7rem;'>{config.FIELD_LAT:.3f}°N, {abs(config.FIELD_LON):.3f}°W</div>
        </div>
        """, unsafe_allow_html=True)
    with i2:
        area_km2 = config.FIELD_BBOX_SIZE_KM ** 2
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Monitored Area</div>
            <div style='color: #8b5cf6; font-size: 1.3rem; font-family: JetBrains Mono;'>{area_km2:.1f} km²</div>
        </div>
        """, unsafe_allow_html=True)
    with i3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Weather Stations</div>
            <div style='color: #f59e0b; font-size: 1.3rem; font-family: JetBrains Mono;'>{len(multi_weather)}</div>
            <div style='color: #64748b; font-size: 0.7rem;'>Global locations</div>
        </div>
        """, unsafe_allow_html=True)
    with i4:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-label">Data Source</div>
            <div style='color: #2ecc71; font-size: 1rem; font-family: JetBrains Mono;'>Sentinel-2 L2A</div>
            <div style='color: #64748b; font-size: 0.7rem;'>10m multi-spectral</div>
        </div>
        """, unsafe_allow_html=True)


def _add_ndvi_overlay(m):
    """Add NDVI color-mapped overlay to map."""
    processed_dir = config.PROCESSED_DIR
    ndvi_rgbs = sorted(processed_dir.glob("ndvi_rgb_*.png"), reverse=True)
    if ndvi_rgbs:
        import base64
        with open(ndvi_rgbs[0], "rb") as f:
            img_data = base64.b64encode(f.read()).decode()
        bbox = config.FIELD_BBOX
        bounds = [[bbox["south"], bbox["west"]], [bbox["north"], bbox["east"]]]
        folium.raster_layers.ImageOverlay(
            image=f"data:image/png;base64,{img_data}",
            bounds=bounds, opacity=0.7, name="🌿 NDVI Heatmap",
        ).add_to(m)


def _add_plot_boundaries(m):
    """Add segmented plot boundaries to map."""
    geojson_path = config.PROCESSED_DIR / "plots.geojson"
    if geojson_path.exists():
        with open(geojson_path) as f:
            geojson = json.load(f)
        plot_group = folium.FeatureGroup(name="🔬 Plot Health Zones")
        for feature in geojson.get("features", []):
            props = feature.get("properties", {})
            color = props.get("health_color", "#3b82f6")
            ndvi = props.get("mean_ndvi", 0)
            tooltip = (
                f"<b>Plot #{props.get('plot_id', '?')}</b><br>"
                f"Health: {props.get('health_class', 'Unknown')}<br>"
                f"NDVI: {ndvi:.3f}<br>"
                f"Area: {props.get('area_pixels', 0)} px"
            )
            folium.GeoJson(
                feature,
                style_function=lambda x, c=color: {
                    "fillColor": c, "color": c, "weight": 2, "fillOpacity": 0.3,
                },
                tooltip=folium.Tooltip(tooltip),
            ).add_to(plot_group)
        plot_group.add_to(m)


def _add_weather_marker(m, lat, lon):
    """Add detailed field weather marker."""
    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    weather = db.get_latest_weather()
    if weather:
        temp = weather.get("temperature_c", "N/A")
        humidity = weather.get("humidity_pct", "N/A")
        desc = weather.get("description", "N/A")
        soil = weather.get("soil_moisture", 0)
        wind = weather.get("wind_speed_ms", 0) or 0
        popup_html = f"""
        <div style='font-family: Inter, sans-serif; min-width: 220px;'>
            <h4 style='margin:0 0 6px 0; color: #1e3a5f;
            border-bottom: 2px solid #2ecc71; padding-bottom: 4px;'>
                🟢 Field Weather Station
            </h4>
            <table style='width: 100%; font-size: 13px;'>
                <tr><td>🌡️ <b>Temp</b></td><td style='text-align:right;'>{temp}°C</td></tr>
                <tr><td>💧 <b>Humidity</b></td><td style='text-align:right;'>{humidity}%</td></tr>
                <tr><td>💨 <b>Wind</b></td><td style='text-align:right;'>{wind:.1f} m/s</td></tr>
                <tr><td>🌱 <b>Soil</b></td><td style='text-align:right;'>{soil:.0%}</td></tr>
                <tr><td>☁️ <b>Sky</b></td><td style='text-align:right;'>{desc}</td></tr>
            </table>
        </div>
        """
        folium.Marker(
            location=[lat, lon],
            popup=folium.Popup(popup_html, max_width=280),
            tooltip="🟢 Field Weather — Click for details",
            icon=folium.Icon(color="green", icon="home", prefix="fa"),
        ).add_to(m)
