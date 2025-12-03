#!/usr/bin/env python3
"""
Combined Performance Page
Show overall system performance using QuantStats tearsheet
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
    st.title("📊 Combined Performance")

    # Initialize
    mongodb_url = os.getenv('MONGODB_URI') or os.getenv('mongodbconnectionstring') or "mongodb://mathematricks_mongodb:27017/mathematricks_trader"

    if not mongodb_url:
        st.error("MongoDB connection string not found")
        return

    data_store = DataStore(mongodb_url)
    if not data_store.connect():
        st.error("Failed to connect to MongoDB")
        return

    metrics_calc = MetricsCalculator(data_store)

    # Get combined PnL history
    pnl_history = data_store.get_pnl_history()

    if not pnl_history or len(pnl_history) == 0:
        st.info("No performance data available. Load data using: `python tests/test_load_equity_curves.py tests/sample_equity_curves.csv`")
        data_store.disconnect()
        return

    # Calculate returns
    returns = metrics_calc.calculate_returns(pnl_history)

    if returns.empty:
        st.info("No returns data available")
        data_store.disconnect()
        return

    st.info(f"Displaying tearsheet for {len(returns)} days of trading data across all strategies")

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
        performance = metrics_calc.get_strategy_performance()

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Return", f"{performance.get('total_return', 0)}%")
        with col2:
            st.metric("Sharpe Ratio", f"{performance.get('sharpe_ratio', 0)}")
        with col3:
            st.metric("Max Drawdown", f"{performance.get('max_drawdown', 0)}%")
        with col4:
            st.metric("Win Rate", f"{performance.get('win_rate', 0)}%")

    # Recent Signals and Orders
    st.subheader("📋 Recent Signals & Orders")

    tab1, tab2 = st.tabs(["Signals", "Orders"])

    with tab1:
        signals = data_store.get_signals(limit=50)
        if signals:
            df_signals = pd.DataFrame([{
                'Signal ID': s.get('signal_id'),
                'Strategy': s.get('strategy_name'),
                'Type': s.get('signal_type'),
                'Timestamp': s.get('timestamp')
            } for s in signals])
            st.dataframe(df_signals, use_container_width=True)
        else:
            st.info("No signals found")

    with tab2:
        orders = data_store.get_orders(limit=50)
        if orders:
            df_orders = pd.DataFrame([{
                'Order ID': o.get('order_id'),
                'Ticker': o.get('ticker'),
                'Side': o.get('order_side'),
                'Quantity': o.get('quantity'),
                'Status': o.get('status')
            } for o in orders])
            st.dataframe(df_orders, use_container_width=True)
        else:
            st.info("No orders found")

    data_store.disconnect()
