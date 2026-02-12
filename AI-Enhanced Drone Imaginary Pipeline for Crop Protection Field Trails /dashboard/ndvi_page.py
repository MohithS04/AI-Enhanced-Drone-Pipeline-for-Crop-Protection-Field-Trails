"""
NDVI Analysis Dashboard Page
==============================
NDVI histogram, time-series comparison, and image viewer.
"""

import sys
from pathlib import Path

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))
import config


def render():
    """Render the NDVI Analysis page."""
    st.markdown("""
    <h1 style='background: linear-gradient(135deg, #34d399, #2ecc71);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    font-weight: 800; font-size: 2rem; margin-bottom: 0;'>
    🌿 NDVI Analysis
    </h1>
    <p style='color: #64748b; margin-top: 0.2rem;'>
    Vegetation index analysis: NDVI = (NIR - Red) / (NIR + Red)
    </p>
    """, unsafe_allow_html=True)

    from database.db_manager import DatabaseManager
    db = DatabaseManager()
    ndvi_history = db.get_ndvi_history(limit=20)

    if not ndvi_history:
        st.warning("No NDVI data available. Run the pipeline first!")
        return

    latest = ndvi_history[0]

    # ── NDVI Statistics Cards ────────────────────────────────
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        _stat_card("Mean NDVI", f"{latest.get('ndvi_mean', 0) or 0:.3f}", "#3b82f6")
    with c2:
        _stat_card("Max NDVI", f"{latest.get('ndvi_max', 0) or 0:.3f}", "#2ecc71")
    with c3:
        _stat_card("Min NDVI", f"{latest.get('ndvi_min', 0) or 0:.3f}", "#ef4444")
    with c4:
        _stat_card("Std Dev", f"{latest.get('ndvi_std', 0) or 0:.3f}", "#8b5cf6")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── NDVI Distribution Histogram ──────────────────────────
    left, right = st.columns([1, 1])

    with left:
        st.markdown('<div class="section-header">📊 NDVI Distribution</div>',
                    unsafe_allow_html=True)

        # Try to load actual NDVI data for histogram
        ndvi_file = latest.get("file_path", "")
        ndvi_values = None

        if ndvi_file and Path(ndvi_file).exists():
            try:
                import rasterio
                with rasterio.open(ndvi_file) as src:
                    ndvi_arr = src.read(1).flatten()
                    ndvi_values = ndvi_arr[ndvi_arr > -9999]
            except Exception:
                pass

        if ndvi_values is not None and len(ndvi_values) > 0:
            fig = go.Figure()

            # Create histogram with color-coded bins
            bins = np.linspace(-0.2, 1.0, 60)
            counts, edges = np.histogram(ndvi_values, bins=bins)

            colors = []
            for edge in edges[:-1]:
                if edge > config.NDVI_HEALTHY:
                    colors.append("#2ecc71")
                elif edge > config.NDVI_MODERATE:
                    colors.append("#f59e0b")
                elif edge > config.NDVI_SEVERE:
                    colors.append("#e74c3c")
                else:
                    colors.append("#8e44ad")

            fig.add_trace(go.Bar(
                x=edges[:-1], y=counts,
                marker_color=colors,
                width=0.018,
                hovertemplate="NDVI: %{x:.2f}<br>Pixels: %{y}<extra></extra>",
            ))

            # Add threshold lines
            for thresh, label, color in [
                (config.NDVI_HEALTHY, "Healthy", "#2ecc71"),
                (config.NDVI_MODERATE, "Moderate", "#f59e0b"),
                (config.NDVI_SEVERE, "Severe", "#e74c3c"),
            ]:
                fig.add_vline(x=thresh, line_dash="dash", line_color=color,
                             annotation_text=label, annotation_font_color=color)

            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(title="NDVI Value", color="#64748b",
                          showgrid=False, range=[-0.2, 1.05]),
                yaxis=dict(title="Pixel Count", color="#64748b",
                          showgrid=True, gridcolor="rgba(100,116,139,0.15)"),
                margin=dict(t=30, b=50, l=50, r=30),
                height=350,
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("NDVI data file not available for histogram")

    with right:
        st.markdown('<div class="section-header">📈 Health Class Breakdown</div>',
                    unsafe_allow_html=True)

        h = latest.get("healthy_pct", 40) or 40
        m = latest.get("moderate_pct", 30) or 30
        s = latest.get("severe_pct", 20) or 20
        c = latest.get("critical_pct", 10) or 10

        fig = go.Figure()
        categories = ["Healthy", "Moderate\nStress", "Severe\nStress", "Critical"]
        values = [h, m, s, c]
        colors = ["#2ecc71", "#f59e0b", "#e74c3c", "#8e44ad"]

        fig.add_trace(go.Bar(
            x=categories, y=values,
            marker=dict(
                color=colors,
                line=dict(width=0),
                opacity=0.9,
            ),
            text=[f"{v:.1f}%" for v in values],
            textposition="outside",
            textfont=dict(color="white", size=14, family="JetBrains Mono"),
            hovertemplate="%{x}: %{y:.1f}%<extra></extra>",
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(color="#64748b", showgrid=False),
            yaxis=dict(color="#64748b", showgrid=True,
                      gridcolor="rgba(100,116,139,0.15)",
                      title="Percentage (%)"),
            margin=dict(t=30, b=50, l=50, r=30),
            height=350,
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)

    # ── Image Comparison ─────────────────────────────────────
    st.markdown('<div class="section-header">🖼️ Imagery Comparison</div>',
                unsafe_allow_html=True)

    img_col1, img_col2, img_col3 = st.columns(3)

    processed_dir = config.PROCESSED_DIR

    with img_col1:
        st.markdown("**True Color (RGB)**")
        rgb_files = sorted(processed_dir.glob("rgb_*.png"), reverse=True)
        if rgb_files:
            st.image(str(rgb_files[0]), use_container_width=True)
        else:
            st.info("Run pipeline to generate")

    with img_col2:
        st.markdown("**NDVI Heatmap**")
        ndvi_files = sorted(processed_dir.glob("ndvi_rgb_*.png"), reverse=True)
        if ndvi_files:
            st.image(str(ndvi_files[0]), use_container_width=True)
        else:
            st.info("Run pipeline to generate")

    with img_col3:
        st.markdown("**False Color (NIR)**")
        fc_files = sorted(processed_dir.glob("false_color_*.png"), reverse=True)
        if fc_files:
            st.image(str(fc_files[0]), use_container_width=True)
        else:
            st.info("Run pipeline to generate")

    # ── NDVI Time Series ────────────────────────────────────
    st.markdown('<div class="section-header">📉 NDVI Time Series</div>',
                unsafe_allow_html=True)

    if len(ndvi_history) > 1:
        timestamps = [r.get("timestamp", "")[:16] for r in reversed(ndvi_history)]
        means = [r.get("ndvi_mean", 0) or 0 for r in reversed(ndvi_history)]
        healthy = [r.get("healthy_pct", 0) or 0 for r in reversed(ndvi_history)]

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=timestamps, y=means, mode="lines+markers",
            name="NDVI Mean",
            line=dict(color="#3b82f6", width=3),
            marker=dict(size=8),
        ))
        fig.add_trace(go.Scatter(
            x=timestamps, y=[h/100 for h in healthy], mode="lines+markers",
            name="Healthy %",
            line=dict(color="#2ecc71", width=2, dash="dot"),
            marker=dict(size=6),
            yaxis="y2",
        ))

        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(color="#64748b", showgrid=False, tickangle=-45),
            yaxis=dict(title="NDVI", color="#3b82f6",
                      showgrid=True, gridcolor="rgba(100,116,139,0.15)"),
            yaxis2=dict(title="Healthy %", color="#2ecc71",
                       overlaying="y", side="right",
                       tickformat=".0%"),
            margin=dict(t=20, b=60, l=50, r=60),
            height=300,
            legend=dict(orientation="h", y=-0.2, x=0.5, xanchor="center",
                       font=dict(color="#94a3b8")),
        )
        st.plotly_chart(fig, use_container_width=True)


def _stat_card(label, value, color):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value" style="color: {color}; font-size: 1.8rem;">{value}</div>
    </div>
    """, unsafe_allow_html=True)
