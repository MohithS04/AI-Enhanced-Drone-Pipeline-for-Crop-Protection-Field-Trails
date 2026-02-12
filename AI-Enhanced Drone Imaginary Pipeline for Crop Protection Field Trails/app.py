"""
🌾 AI-Enhanced Crop Health Monitoring Pipeline
================================================
Real-Time Geospatial Dashboard with Satellite Imagery Analysis
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import streamlit as st

# ── Page config (must be first Streamlit call) ───────────────
st.set_page_config(
    page_title="🌾 Crop Health Pipeline",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS for Premium Dark Theme ────────────────────────
st.markdown("""
<style>
    /* Import Google Fonts */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    /* Root Variables */
    :root {
        --bg-primary: #0a0e17;
        --bg-secondary: #111827;
        --bg-card: #1a1f2e;
        --bg-card-hover: #222838;
        --border: #2a3040;
        --text-primary: #f0f4f8;
        --text-secondary: #94a3b8;
        --accent-green: #2ecc71;
        --accent-blue: #3b82f6;
        --accent-purple: #8b5cf6;
        --accent-orange: #f59e0b;
        --accent-red: #ef4444;
        --gradient-1: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        --gradient-2: linear-gradient(135deg, #2ecc71 0%, #27ae60 100%);
        --gradient-3: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
    }

    /* Global Styles */
    .stApp {
        font-family: 'Inter', -apple-system, sans-serif;
    }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f1724 0%, #1a1f2e 100%) !important;
        border-right: 1px solid rgba(59, 130, 246, 0.2);
    }

    section[data-testid="stSidebar"] .stMarkdown h1 {
        background: linear-gradient(135deg, #60a5fa, #a78bfa);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
        font-size: 1.4rem;
    }

    /* KPI Cards */
    .kpi-card {
        background: linear-gradient(145deg, #1a1f2e, #222838);
        border: 1px solid rgba(59, 130, 246, 0.15);
        border-radius: 16px;
        padding: 1.5rem;
        text-align: center;
        transition: all 0.3s ease;
        box-shadow: 0 4px 24px rgba(0,0,0,0.2);
    }
    .kpi-card:hover {
        border-color: rgba(59, 130, 246, 0.4);
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(59, 130, 246, 0.1);
    }
    .kpi-value {
        font-size: 2.2rem;
        font-weight: 800;
        font-family: 'JetBrains Mono', monospace;
        margin: 0.3rem 0;
    }
    .kpi-label {
        color: #94a3b8;
        font-size: 0.85rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .kpi-delta {
        font-size: 0.8rem;
        margin-top: 0.3rem;
    }

    /* Alert Cards */
    .alert-critical {
        background: linear-gradient(135deg, rgba(239,68,68,0.15), rgba(239,68,68,0.05));
        border-left: 4px solid #ef4444;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }
    .alert-warning {
        background: linear-gradient(135deg, rgba(245,158,11,0.15), rgba(245,158,11,0.05));
        border-left: 4px solid #f59e0b;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }
    .alert-info {
        background: linear-gradient(135deg, rgba(59,130,246,0.15), rgba(59,130,246,0.05));
        border-left: 4px solid #3b82f6;
        border-radius: 12px;
        padding: 1rem 1.2rem;
        margin: 0.5rem 0;
    }

    /* Status Badge */
    .status-badge {
        display: inline-block;
        padding: 0.25rem 0.8rem;
        border-radius: 20px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .status-good { background: rgba(46,204,113,0.2); color: #2ecc71; }
    .status-fair { background: rgba(245,158,11,0.2); color: #f59e0b; }
    .status-poor { background: rgba(231,76,60,0.2); color: #e74c3c; }
    .status-critical { background: rgba(142,68,173,0.2); color: #8e44ad; }

    /* Section Headers */
    .section-header {
        font-size: 1.1rem;
        font-weight: 700;
        color: #f0f4f8;
        margin: 1.5rem 0 0.8rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(59,130,246,0.3);
    }

    /* Hide Streamlit defaults */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
</style>
""", unsafe_allow_html=True)

# ── Sidebar Navigation ──────────────────────────────────────
with st.sidebar:
    st.markdown("# 🛰️ CropWatch AI")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["📊 Overview", "🗺️ Live Map", "🌿 NDVI Analysis",
         "🌤️ Weather", "⚙️ Pipeline Metrics"],
        label_visibility="collapsed",
    )

    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #64748b; font-size: 0.75rem;'>
        <p>🌾 AI-Enhanced Crop Health</p>
        <p>Monitoring Pipeline v1.0</p>
        <p style='margin-top: 0.5rem;'>Powered by Sentinel-2 🛰️</p>
    </div>
    """, unsafe_allow_html=True)

    # Run pipeline button
    st.markdown("---")
    if st.button("🔄 Run Pipeline", use_container_width=True, type="primary"):
        with st.spinner("Running pipeline..."):
            from data_ingestion.pipeline_scheduler import run_pipeline
            result = run_pipeline()
            if result["status"] == "completed":
                st.success(f"✅ Complete in {result['processing_time_s']}s")
            else:
                st.error(f"❌ {result.get('error', 'Unknown error')}")

# ── Page Routing ─────────────────────────────────────────────
if page == "📊 Overview":
    from dashboard.overview_page import render
    render()
elif page == "🗺️ Live Map":
    from dashboard.map_page import render
    render()
elif page == "🌿 NDVI Analysis":
    from dashboard.ndvi_page import render
    render()
elif page == "🌤️ Weather":
    from dashboard.weather_page import render
    render()
elif page == "⚙️ Pipeline Metrics":
    from dashboard.metrics_page import render
    render()
