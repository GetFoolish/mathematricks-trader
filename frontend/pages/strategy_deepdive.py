#!/usr/bin/env python3
"""
Strategy Deepdive Page
Detailed analysis of a single strategy
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import sys
from pathlib import Path
import os

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.reporting import DataStore, MetricsCalculator


def show():
    st.title("🔍 Strategy Deepdive")

    # Initialize
    mongodb_url = os.getenv('mongodbconnectionstring', '')

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
        performance = metrics_calc.get_strategy_performance(selected_strategy)

        # Metrics
        st.subheader(f"📊 {selected_strategy} Performance")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Return", f"{performance.get('total_return', 0)}%")

        with col2:
            st.metric("Sharpe Ratio", f"{performance.get('sharpe_ratio', 0)}")

        with col3:
            st.metric("Max Drawdown", f"{performance.get('max_drawdown', 0)}%")

        with col4:
            st.metric("Win Rate", f"{performance.get('win_rate', 0)}%")

        # Equity Curve
        st.subheader("📈 Equity Curve")

        if 'equity_curve' in performance and performance['equity_curve']:
            equity_data = performance['equity_curve']
            dates = list(equity_data.keys())
            values = list(equity_data.values())

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines',
                name=selected_strategy,
                fill='tozeroy'
            ))

            fig.update_layout(
                xaxis_title="Date",
                yaxis_title="Equity ($)",
                height=400
            )

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No equity curve data available")

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

        # Orders for this strategy
        st.subheader("📋 Orders")

        orders = data_store.get_orders(strategy_name=selected_strategy, limit=100)

        if orders:
            df_orders = pd.DataFrame([{
                'Order ID': o.get('order_id'),
                'Ticker': o.get('ticker'),
                'Side': o.get('order_side'),
                'Quantity': o.get('quantity'),
                'Broker': o.get('broker'),
                'Status': o.get('status')
            } for o in orders])

            st.dataframe(df_orders, use_container_width=True)
        else:
            st.info("No orders found for this strategy")

    data_store.disconnect()
