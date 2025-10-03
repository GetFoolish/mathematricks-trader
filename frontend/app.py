#!/usr/bin/env python3
"""
Mathematricks Trader Frontend
Streamlit app for viewing trading performance and signals
"""

import streamlit as st
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="Mathematricks Trader",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        padding-bottom: 1rem;
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Main header
st.markdown('<div class="main-header">📈 Mathematricks Trader V1</div>', unsafe_allow_html=True)

# Sidebar navigation
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Signals History", "Combined Performance", "Strategy Deepdive",
     "Correlation Matrix", "Strategy Onboarding"]
)

# Display selected page
if page == "Signals History":
    from pages import signals_history
    signals_history.show()

elif page == "Combined Performance":
    from pages import combined_performance
    combined_performance.show()

elif page == "Strategy Deepdive":
    from pages import strategy_deepdive
    strategy_deepdive.show()

elif page == "Correlation Matrix":
    from pages import correlation_matrix
    correlation_matrix.show()

elif page == "Strategy Onboarding":
    from pages import onboarding
    onboarding.show()
