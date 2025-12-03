#!/usr/bin/env python3
"""
Strategy Deepdive Page
Detailed analysis of a single strategy using QuantStats tearsheet
"""

import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sys
from pathlib import Path
import os
from dotenv import load_dotenv
import quantstats as qs
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')

# Load environment variables
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.reporting import DataStore, MetricsCalculator


def show():
    st.title("🔍 Strategy Deepdive")

    # Initialize
    mongodb_url = os.getenv('MONGODB_URI') or os.getenv('mongodbconnectionstring') or "mongodb://mathematricks_mongodb:27017/mathematricks_trader"

    if not mongodb_url:
        st.error("MongoDB connection string not found")
        return

    data_store = DataStore(mongodb_url)
    if not data_store.connect():
        st.error("Failed to connect to MongoDB")
        return

    # Strategy selection
    strategies = data_store.get_strategy_list()

    if not strategies:
        st.info("No strategies found in database")
        data_store.disconnect()
        return

    selected_strategy = st.selectbox("Select Strategy", strategies)

    if selected_strategy:
        metrics_calc = MetricsCalculator(data_store)

        # Get PnL history for selected strategy
        pnl_history = data_store.get_pnl_history(strategy_name=selected_strategy)

        if not pnl_history or len(pnl_history) == 0:
            st.info(f"No performance data available for {selected_strategy}")
            data_store.disconnect()
            return

        # Calculate returns
        returns = metrics_calc.calculate_returns(pnl_history)

        if returns.empty:
            st.info("No returns data available")
            data_store.disconnect()
            return

        st.info(f"Displaying tearsheet for {selected_strategy} ({len(returns)} days of data)")

        # Generate QuantStats HTML tearsheet
        try:
            # Create HTML report
            html_report = qs.reports.html(returns, output=None, download_filename=None)

            # Display in Streamlit
            components.html(html_report, height=3000, scrolling=True)

        except Exception as e:
            st.error(f"Error generating tearsheet: {e}")
            st.info("Showing basic metrics instead...")

            # Fallback to basic metrics
            performance = metrics_calc.get_strategy_performance(selected_strategy)

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Return", f"{performance.get('total_return', 0)}%")
            with col2:
                st.metric("Sharpe Ratio", f"{performance.get('sharpe_ratio', 0)}")
            with col3:
                st.metric("Max Drawdown", f"{performance.get('max_drawdown', 0)}%")
            with col4:
                st.metric("Win Rate", f"{performance.get('win_rate', 0)}%")

        # Signals for this strategy
        st.subheader("📡 Signals")

        signals = data_store.get_signals(strategy_name=selected_strategy, limit=100)

        if signals:
            df_signals = pd.DataFrame([{
                'Signal ID': s.get('signal_id'),
                'Type': s.get('signal_type'),
                'Timestamp': s.get('timestamp'),
                'Executed': 'Yes' if s.get('execution_results') else 'No'
            } for s in signals])

            st.dataframe(df_signals, use_container_width=True)
        else:
            st.info("No signals found for this strategy")

    data_store.disconnect()
