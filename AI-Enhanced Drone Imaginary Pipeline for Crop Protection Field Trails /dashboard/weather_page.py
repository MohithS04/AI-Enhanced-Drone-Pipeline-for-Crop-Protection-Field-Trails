"""
Weather Dashboard Page
=======================
Multi-state & international weather comparison,
local field conditions, and agricultural alerts.
"""

import json
import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def render():
    """Render the Weather page."""
    st.markdown("""
    <h1 style='background: linear-gradient(135deg, #60a5fa, #fbbf24);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800; font-size: 2rem; margin-bottom: 0;'>
    🌤️ Weather & Soil Conditions
    </h1>
    <p style='color: #64748b; margin-top: 0.2rem;'>
    Multi-region agricultural weather: US states &amp; international crop regions
    </p>
    """, unsafe_allow_html=True)

    from database.db_manager import DatabaseManager
    from data_ingestion.weather_fetcher import get_multi_location_weather, GLOBAL_LOCATIONS
    db = DatabaseManager()

    # ── Region Filter ────────────────────────────────────────
    filter_col, refresh_col = st.columns([3, 1])
    with filter_col:
        region_filter = st.selectbox(
            "🌍 Region",
            ["🌐 All Regions", "🇺🇸 US States", "🌏 International"],
            index=0,
        )
    with refresh_col:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Weather", use_container_width=True):
            from data_ingestion.weather_fetcher import fetch_multi_location_weather
            with st.spinner("Fetching weather for all locations..."):
                fetch_multi_location_weather()
                # Also update local field weather
                from data_ingestion.weather_fetcher import fetch_weather
                weather = fetch_weather()
                db.insert_weather(weather)
            st.success("✅ Weather updated for all locations!")
            st.rerun()

    # ── Load multi-location weather ──────────────────────────
    multi_wx = get_multi_location_weather()

    # Filter by region
    if region_filter == "🇺🇸 US States":
        multi_wx = {k: v for k, v in multi_wx.items() if v.get("region") == "US"}
    elif region_filter == "🌏 International":
        multi_wx = {k: v for k, v in multi_wx.items() if v.get("region") != "US"}

    if not multi_wx:
        st.warning("No weather data. Click 'Refresh Weather' to fetch!")
        return

    # ── Temperature Bar Chart (All Locations) ────────────────
    st.markdown('<div class="section-header">🌡️ Temperature Across Regions</div>',
                unsafe_allow_html=True)

    names = list(multi_wx.keys())
    temps = [multi_wx[n].get("current", {}).get("temperature_c", 0) for n in names]
    humids = [multi_wx[n].get("current", {}).get("humidity_pct", 0) for n in names]

    # Sort by temperature
    sorted_pairs = sorted(zip(names, temps, humids), key=lambda x: x[1], reverse=True)
    names_s = [p[0].split(",")[0] for p in sorted_pairs]  # Short names
    temps_s = [p[1] for p in sorted_pairs]
    humids_s = [p[2] for p in sorted_pairs]

    # Color scale: cold=blue, warm=green, hot=red
    colors = []
    for t in temps_s:
        if t > 35:
            colors.append("#ef4444")
        elif t > 25:
            colors.append("#f59e0b")
        elif t > 10:
            colors.append("#2ecc71")
        elif t > 0:
            colors.append("#3b82f6")
        else:
            colors.append("#8b5cf6")

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=names_s, y=temps_s,
        marker=dict(color=colors, line=dict(width=0)),
        text=[f"{t:.0f}°" for t in temps_s],
        textposition="outside",
        textfont=dict(color="white", size=11),
        name="Temperature °C",
        hovertemplate="%{x}: %{y:.1f}°C<extra></extra>",
    ), secondary_y=False)

    fig.add_trace(go.Scatter(
        x=names_s, y=humids_s,
        mode="lines+markers",
        line=dict(color="#3b82f6", width=2, dash="dot"),
        marker=dict(size=6),
        name="Humidity %",
        hovertemplate="%{x}: %{y:.0f}%<extra></extra>",
    ), secondary_y=True)

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(color="#64748b", showgrid=False, tickangle=-45),
        margin=dict(t=30, b=80, l=50, r=50),
        height=350,
        legend=dict(orientation="h", y=-0.3, x=0.5, xanchor="center",
                   font=dict(color="#94a3b8")),
        showlegend=True,
    )
    fig.update_yaxes(title_text="°C", color="#ef4444", showgrid=True,
                    gridcolor="rgba(100,116,139,0.1)", secondary_y=False)
    fig.update_yaxes(title_text="%", color="#3b82f6", showgrid=False, secondary_y=True)
    st.plotly_chart(fig, use_container_width=True)

    # ── Weather Cards Grid ───────────────────────────────────
    st.markdown('<div class="section-header">📋 Detailed Conditions by Location</div>',
                unsafe_allow_html=True)

    # Display in rows of 3
    items = list(multi_wx.items())
    for row_start in range(0, len(items), 3):
        row_items = items[row_start:row_start + 3]
        cols = st.columns(3)
        for idx, (name, wx) in enumerate(row_items):
            with cols[idx]:
                current = wx.get("current", {})
                soil = wx.get("soil", {})
                precip = wx.get("precipitation", {})
                alerts = wx.get("agricultural_alerts", [])
                crop = wx.get("crop", "")

                temp = current.get("temperature_c", 0)
                humidity = current.get("humidity_pct", 0)
                desc = current.get("description", "N/A")
                wind = current.get("wind_speed_ms", 0)
                clouds = current.get("cloud_cover_pct", 0)
                rain = precip.get("rain_mm", 0)
                soil_m = soil.get("moisture", 0)
                soil_t = soil.get("temperature_c", 0)

                # Weather icon
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
                    tc = "#ef4444"
                elif temp > 25:
                    tc = "#f59e0b"
                elif temp > 10:
                    tc = "#2ecc71"
                elif temp > 0:
                    tc = "#3b82f6"
                else:
                    tc = "#8b5cf6"

                # Alert badge
                alert_badge = ""
                if alerts:
                    top_alert = alerts[0]
                    atype = top_alert.get("type", "INFO")
                    acolor = "#ef4444" if atype == "CRITICAL" else "#f59e0b" if atype == "WARNING" else "#2ecc71"
                    alert_badge = f"""<span style='display:inline-block; background:{acolor}22;
                        color:{acolor}; padding: 2px 8px; border-radius:6px;
                        font-size: 0.7rem; margin-top: 4px;'>
                        {top_alert.get('category','').title()}</span>"""

                is_active = (name == "Iowa, USA")
                border_color = "#2ecc71" if is_active else "rgba(59,130,246,0.15)"
                active_tag = " 🟢 ACTIVE" if is_active else ""
                shadow = "box-shadow: 0 0 15px rgba(46,204,113,0.15);" if is_active else ""
                short_name = name.split(",")[0]
                soil_m_pct = f"{soil_m * 100:.0f}%"

                card_html = (
                    f"<div style='background: linear-gradient(145deg, #1a1f2e, #222838);"
                    f"border-radius: 14px; padding: 1rem; margin-bottom: 0.6rem;"
                    f"border: 1px solid {border_color}; {shadow}'>"
                    f"<table style='width:100%; border:none; border-collapse:collapse;'>"
                    f"<tr><td style='border:none; padding:2px;'>"
                    f"<strong style='color:#f0f4f8; font-size:0.95rem;'>{wx_icon} {short_name}{active_tag}</strong>"
                    f"<br><span style='color:#64748b; font-size:0.7rem;'>🌾 {crop}</span>"
                    f"</td>"
                    f"<td style='border:none; text-align:right; vertical-align:top; padding:2px;'>"
                    f"<span style='color:{tc}; font-size:1.6rem; font-weight:800;"
                    f"font-family:JetBrains Mono;'>{temp:.0f}°</span>"
                    f"</td></tr>"
                    f"</table>"
                    f"<table style='width:100%; border:none; border-collapse:collapse;"
                    f"margin-top:6px; font-size:0.78rem; color:#94a3b8;'>"
                    f"<tr>"
                    f"<td style='border:none; padding:2px;'>💧 {humidity:.0f}%</td>"
                    f"<td style='border:none; padding:2px;'>💨 {wind:.1f} m/s</td>"
                    f"</tr><tr>"
                    f"<td style='border:none; padding:2px;'>🌱 {soil_m_pct}</td>"
                    f"<td style='border:none; padding:2px;'>🌧️ {rain:.1f} mm</td>"
                    f"</tr><tr>"
                    f"<td style='border:none; padding:2px;'>🌍 {soil_t:.0f}°C soil</td>"
                    f"<td style='border:none; padding:2px;'>☁️ {desc}</td>"
                    f"</tr>"
                    f"</table>"
                    f"{alert_badge}"
                    f"</div>"
                )
                st.markdown(card_html, unsafe_allow_html=True)

    # ── Soil Moisture Comparison ─────────────────────────────
    st.markdown('<div class="section-header">🌱 Soil Moisture Comparison</div>',
                unsafe_allow_html=True)

    soil_names = [n.split(",")[0] for n in multi_wx.keys()]
    soil_vals = [multi_wx[n].get("soil", {}).get("moisture", 0) * 100 for n in multi_wx]

    soil_colors = []
    for s in soil_vals:
        if s < 20:
            soil_colors.append("#ef4444")
        elif s < 35:
            soil_colors.append("#f59e0b")
        else:
            soil_colors.append("#2ecc71")

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(
        x=soil_names, y=soil_vals,
        marker=dict(color=soil_colors, line=dict(width=0)),
        text=[f"{s:.0f}%" for s in soil_vals],
        textposition="outside",
        textfont=dict(color="white", size=11),
        hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
    ))

    fig2.add_hline(y=20, line_dash="dash", line_color="rgba(239,68,68,0.6)",
                  annotation_text="Drought Risk", annotation_font_color="#ef4444")
    fig2.add_hline(y=80, line_dash="dash", line_color="rgba(59,130,246,0.6)",
                  annotation_text="Waterlogged", annotation_font_color="#3b82f6")

    fig2.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(color="#64748b", showgrid=False, tickangle=-45),
        yaxis=dict(title="Soil Moisture %", color="#64748b",
                  showgrid=True, gridcolor="rgba(100,116,139,0.1)"),
        margin=dict(t=30, b=80, l=50, r=30),
        height=300,
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

    # ── Local Field History ──────────────────────────────────
    st.markdown('<div class="section-header">📈 Iowa Field — Historical Trends</div>',
                unsafe_allow_html=True)

    history = db.get_weather_history(limit=24)

    if history:
        chart_left, chart_right = st.columns(2)

        with chart_left:
            timestamps = [h.get("timestamp", "")[:16] for h in reversed(history)]
            temp_h = [h.get("temperature_c", 0) or 0 for h in reversed(history)]
            humid_h = [h.get("humidity_pct", 0) or 0 for h in reversed(history)]

            fig3 = make_subplots(specs=[[{"secondary_y": True}]])
            fig3.add_trace(go.Scatter(
                x=timestamps, y=temp_h, name="Temperature",
                line=dict(color="#ef4444", width=3), mode="lines",
                fill="tozeroy", fillcolor="rgba(239,68,68,0.08)",
            ), secondary_y=False)
            fig3.add_trace(go.Scatter(
                x=timestamps, y=humid_h, name="Humidity",
                line=dict(color="#3b82f6", width=2, dash="dot"), mode="lines",
            ), secondary_y=True)

            fig3.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=60, l=50, r=50), height=280,
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center",
                           font=dict(color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#64748b", tickangle=-45),
            )
            fig3.update_yaxes(title_text="°C", color="#ef4444", secondary_y=False,
                            showgrid=True, gridcolor="rgba(100,116,139,0.1)")
            fig3.update_yaxes(title_text="%", color="#3b82f6", secondary_y=True, showgrid=False)
            st.plotly_chart(fig3, use_container_width=True)

        with chart_right:
            soil_m_h = [h.get("soil_moisture", 0) or 0 for h in reversed(history)]
            soil_t_h = [h.get("soil_temp_c", 0) or 0 for h in reversed(history)]

            fig4 = make_subplots(specs=[[{"secondary_y": True}]])
            fig4.add_trace(go.Scatter(
                x=timestamps, y=[s * 100 for s in soil_m_h], name="Soil Moisture",
                line=dict(color="#2ecc71", width=3), mode="lines",
                fill="tozeroy", fillcolor="rgba(46,204,113,0.08)",
            ), secondary_y=False)
            fig4.add_trace(go.Scatter(
                x=timestamps, y=soil_t_h, name="Soil Temp",
                line=dict(color="#f59e0b", width=2, dash="dot"), mode="lines",
            ), secondary_y=True)
            fig4.add_hline(y=20, line_dash="dash", line_color="rgba(239,68,68,0.5)",
                         annotation_text="Drought", secondary_y=False)

            fig4.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=20, b=60, l=50, r=50), height=280,
                legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center",
                           font=dict(color="#94a3b8")),
                xaxis=dict(showgrid=False, color="#64748b", tickangle=-45),
            )
            fig4.update_yaxes(title_text="%", color="#2ecc71", secondary_y=False,
                            showgrid=True, gridcolor="rgba(100,116,139,0.1)")
            fig4.update_yaxes(title_text="°C", color="#f59e0b", secondary_y=True, showgrid=False)
            st.plotly_chart(fig4, use_container_width=True)

    # ── Agricultural Alerts (All Locations) ──────────────────
    st.markdown('<div class="section-header">🚜 Agricultural Advisories</div>',
                unsafe_allow_html=True)

    all_alerts = []
    for name, wx in multi_wx.items():
        for alert in wx.get("agricultural_alerts", []):
            if alert.get("type") != "INFO":
                all_alerts.append({"location": name.split(",")[0], **alert})

    if all_alerts:
        # Sort by severity
        all_alerts.sort(key=lambda a: a.get("severity", 0), reverse=True)
        for alert in all_alerts[:8]:
            atype = alert.get("type", "INFO")
            css = "alert-critical" if atype == "CRITICAL" else "alert-warning"
            icon = "🚨" if atype == "CRITICAL" else "⚠️"
            st.markdown(f"""
            <div class="{css}">
                <strong>{icon} {alert['location']} — {alert.get('category', '').title()}</strong><br>
                <span style='color: #94a3b8;'>{alert.get('message', '')}</span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="alert-info">
            <strong>✅ No Critical Advisories</strong><br>
            <span style='color: #94a3b8;'>
                Weather conditions are generally favorable across all monitored regions
            </span>
        </div>
        """, unsafe_allow_html=True)
