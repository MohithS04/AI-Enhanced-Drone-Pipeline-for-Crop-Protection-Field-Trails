"""
Overview Dashboard Page
========================
KPI cards, health summary, and recent activity log.
"""

import sys
from pathlib import Path
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))


def render():
    """Render the Overview page."""
    from database.db_manager import DatabaseManager
    db = DatabaseManager()

    st.markdown("""
    <h1 style='background: linear-gradient(135deg, #60a5fa, #34d399);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800; font-size: 2rem; margin-bottom: 0;'>
    📊 Field Overview
    </h1>
    <p style='color: #64748b; margin-top: 0.2rem;'>
    Real-time crop health monitoring powered by Sentinel-2 satellite imagery
    </p>
    """, unsafe_allow_html=True)

    # ── KPI Row ──────────────────────────────────────────────
    latest_ndvi = db.get_latest_ndvi()
    latest_health = db.get_latest_health()
    latest_weather = db.get_latest_weather()
    pipeline_stats = db.get_pipeline_stats()

    col1, col2, col3, col4, col5 = st.columns(5)

    ndvi_mean = latest_ndvi.get("ndvi_mean", 0) or 0
    healthy_pct = latest_ndvi.get("healthy_pct", 0) or 0
    temp = latest_weather.get("temperature_c", 0) or 0
    soil = latest_weather.get("soil_moisture", 0) or 0
    avg_latency = pipeline_stats.get("avg_processing_time_s", 0)

    with col1:
        _kpi_card("NDVI Mean", f"{ndvi_mean:.3f}",
                  _ndvi_color(ndvi_mean), "Vegetation Index")
    with col2:
        _kpi_card("Healthy Area", f"{healthy_pct:.0f}%",
                  "#2ecc71" if healthy_pct > 60 else "#f59e0b", "Field Coverage")
    with col3:
        _kpi_card("Temperature", f"{temp:.1f}°C",
                  "#3b82f6", "Current")
    with col4:
        _kpi_card("Soil Moisture", f"{soil:.0%}" if soil else "N/A",
                  "#8b5cf6", "Volumetric")
    with col5:
        _kpi_card("Avg Latency", f"{avg_latency:.1f}s",
                  "#f59e0b" if avg_latency > 10 else "#2ecc71", "Pipeline")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Health Distribution & NDVI Histogram ─────────────────
    left, right = st.columns([1, 1])

    with left:
        st.markdown('<div class="section-header">🏥 Health Distribution</div>',
                    unsafe_allow_html=True)

        h_pct = latest_ndvi.get("healthy_pct", 40) or 40
        m_pct = latest_ndvi.get("moderate_pct", 30) or 30
        s_pct = latest_ndvi.get("severe_pct", 20) or 20
        c_pct = latest_ndvi.get("critical_pct", 10) or 10

        fig = go.Figure(data=[go.Pie(
            labels=["Healthy", "Moderate Stress", "Severe Stress", "Critical"],
            values=[h_pct, m_pct, s_pct, c_pct],
            marker=dict(colors=["#2ecc71", "#f59e0b", "#e74c3c", "#8e44ad"]),
            hole=0.55,
            textinfo="label+percent",
            textfont=dict(size=13, color="white"),
            hovertemplate="<b>%{label}</b><br>%{percent}<extra></extra>",
        )])
        fig.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=20, b=20, l=20, r=20),
            height=320,
            annotations=[dict(
                text=f"<b>{h_pct:.0f}%</b><br><span style='font-size:11px;color:#64748b'>Healthy</span>",
                x=0.5, y=0.5, font_size=22, showarrow=False,
                font_color="#2ecc71",
            )],
        )
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown('<div class="section-header">📈 NDVI Trend</div>',
                    unsafe_allow_html=True)

        ndvi_history = db.get_ndvi_history(limit=20)
        if ndvi_history:
            timestamps = [r.get("timestamp", "")[:16] for r in reversed(ndvi_history)]
            means = [r.get("ndvi_mean", 0) or 0 for r in reversed(ndvi_history)]

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=timestamps, y=means,
                mode="lines+markers",
                line=dict(color="#3b82f6", width=3, shape="spline"),
                marker=dict(size=8, color="#3b82f6",
                            line=dict(width=2, color="#1e3a5f")),
                fill="tozeroy",
                fillcolor="rgba(59,130,246,0.1)",
                name="NDVI Mean",
            ))
            # Threshold lines
            fig.add_hline(y=0.6, line_dash="dash", line_color="#2ecc71",
                         annotation_text="Healthy", annotation_position="right")
            fig.add_hline(y=0.3, line_dash="dash", line_color="#f59e0b",
                         annotation_text="Moderate", annotation_position="right")
            fig.add_hline(y=0.1, line_dash="dash", line_color="#e74c3c",
                         annotation_text="Severe", annotation_position="right")

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False, color="#64748b", tickangle=-45),
                yaxis=dict(showgrid=True, gridcolor="rgba(100,116,139,0.15)",
                          color="#64748b", range=[-0.1, 1]),
                margin=dict(t=20, b=60, l=40, r=80),
                height=320,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No NDVI data yet. Run the pipeline first!")

    # ── Alerts & Recommendations ─────────────────────────────
    st.markdown('<div class="section-header">🚨 Alerts & Recommendations</div>',
                unsafe_allow_html=True)

    import json
    alerts_json = latest_health.get("alerts_json", "[]")
    recs_json = latest_health.get("recommendations_json", "[]")

    try:
        alerts = json.loads(alerts_json) if alerts_json else []
        recommendations = json.loads(recs_json) if recs_json else []
    except (json.JSONDecodeError, TypeError):
        alerts, recommendations = [], []

    acol, rcol = st.columns(2)
    with acol:
        if alerts:
            for alert in alerts:
                css_class = "alert-critical" if alert.get("type") == "CRITICAL" else \
                           "alert-warning" if alert.get("type") == "WARNING" else "alert-info"
                icon = alert.get("icon", "ℹ️")
                st.markdown(f"""
                <div class="{css_class}">
                    <strong>{icon} {alert.get('title', alert.get('category', 'Alert'))}</strong><br>
                    <span style='color: #94a3b8; font-size: 0.9rem;'>{alert.get('message', '')}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown("""
            <div class="alert-info">
                <strong>✅ No Active Alerts</strong><br>
                <span style='color: #94a3b8;'>All systems nominal</span>
            </div>
            """, unsafe_allow_html=True)

    with rcol:
        for rec in recommendations[:3]:
            priority_colors = {"HIGH": "#ef4444", "MEDIUM": "#f59e0b", "LOW": "#2ecc71"}
            color = priority_colors.get(rec.get("priority", "MEDIUM"), "#3b82f6")
            st.markdown(f"""
            <div style='background: rgba(26,31,46,0.8); border-radius: 12px;
            padding: 0.8rem 1rem; margin: 0.4rem 0; border-left: 3px solid {color};'>
                <div style='display: flex; justify-content: space-between;'>
                    <strong style='color: #f0f4f8;'>{rec.get('action', '')}</strong>
                    <span class="status-badge" style='background: {color}22; color: {color};'>
                        {rec.get('priority', '')}
                    </span>
                </div>
                <span style='color: #94a3b8; font-size: 0.85rem;'>{rec.get('detail', '')}</span>
            </div>
            """, unsafe_allow_html=True)

    # ── Recent Pipeline Activity ─────────────────────────────
    st.markdown('<div class="section-header">📋 Recent Pipeline Runs</div>',
                unsafe_allow_html=True)

    runs = db.get_pipeline_history(limit=5)
    if runs:
        for run in runs:
            status_color = "#2ecc71" if run.get("status") == "completed" else "#ef4444"
            status_icon = "✅" if run.get("status") == "completed" else "❌"
            time_str = run.get("processing_time_s", 0) or 0
            st.markdown(f"""
            <div style='background: rgba(26,31,46,0.6); border-radius: 10px;
            padding: 0.6rem 1rem; margin: 0.3rem 0; display: flex;
            justify-content: space-between; align-items: center;'>
                <span>{status_icon} Run #{run.get('id', '?')} — {run.get('start_time', '')[:16]}</span>
                <span style='color: {status_color}; font-family: JetBrains Mono;'>
                    {time_str:.1f}s
                </span>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info("No pipeline runs yet. Click '🔄 Run Pipeline' in the sidebar!")


def _kpi_card(label: str, value: str, color: str, subtitle: str):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color};">{value}</div>
        <div class="kpi-label" style="font-size: 0.7rem;">{subtitle}</div>
    </div>
    """, unsafe_allow_html=True)


def _ndvi_color(val: float) -> str:
    if val > 0.6:
        return "#2ecc71"
    elif val > 0.3:
        return "#f59e0b"
    elif val > 0.1:
        return "#e74c3c"
    return "#8e44ad"
