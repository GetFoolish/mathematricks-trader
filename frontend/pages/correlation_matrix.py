#!/usr/bin/env python3
"""
Correlation Matrix Page
Show correlation between strategy returns
"""

import streamlit as st
import plotly.graph_objects as go
import sys
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.reporting import DataStore, MetricsCalculator


def show():
    st.title("🔗 Strategy Correlation Matrix")

    # Initialize
    mongodb_url = os.getenv('mongodbconnectionstring', '')

    if not mongodb_url:
        st.error("MongoDB connection string not found")
        return

    data_store = DataStore(mongodb_url)
    if not data_store.connect():
        st.error("Failed to connect to MongoDB")
        return

    metrics_calc = MetricsCalculator(data_store)

    # Get all strategy returns
    strategy_returns = metrics_calc.get_all_strategy_returns()

    if not strategy_returns:
        st.info("No strategy data available for correlation analysis")
        data_store.disconnect()
        return

    # Calculate correlation
    correlation_df = metrics_calc.calculate_strategy_correlation(strategy_returns)

    if correlation_df.empty:
        st.info("Unable to calculate correlation matrix")
        data_store.disconnect()
        return

    # Display matrix info
    st.write(f"Analyzing correlation between {len(strategy_returns)} strategies")

    # Plot heatmap
    fig = go.Figure(data=go.Heatmap(
        z=correlation_df.values,
        x=correlation_df.columns,
        y=correlation_df.index,
        colorscale='RdBu',
        zmid=0,
        text=correlation_df.values,
        texttemplate='%{text:.2f}',
        textfont={"size": 10},
        colorbar=dict(title="Correlation")
    ))

    fig.update_layout(
        title="Strategy Returns Correlation Matrix",
        xaxis_title="Strategy",
        yaxis_title="Strategy",
        height=600
    )

    st.plotly_chart(fig, use_container_width=True)

    # Interpretation
    st.subheader("📖 Interpretation")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("""
        **Correlation Values:**
        - **+1.0**: Perfect positive correlation
        - **0.0**: No correlation
        - **-1.0**: Perfect negative correlation
        """)

    with col2:
        st.markdown("""
        **Portfolio Diversification:**
        - Lower correlations indicate better diversification
        - Negative correlations can reduce portfolio risk
        - High correlations (>0.7) suggest similar strategies
        """)

    # Show correlation table
    st.subheader("📊 Correlation Table")
    st.dataframe(correlation_df.style.background_gradient(cmap='RdBu', vmin=-1, vmax=1),
                 use_container_width=True)

    data_store.disconnect()
