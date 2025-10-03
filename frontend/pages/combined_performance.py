#!/usr/bin/env python3
"""
Combined Performance Page
Show overall system performance with metrics and equity curve
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import sys
from pathlib import Path
import os

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.reporting import DataStore, MetricsCalculator


def show():
    st.title("📊 Combined Performance")

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

    # Get overall performance
    performance = metrics_calc.get_strategy_performance()

    # Metrics cards
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

    # Get strategy returns for overlay
    strategy_returns = metrics_calc.get_all_strategy_returns()

    # Multi-select for strategy overlay
    strategies_to_show = st.multiselect(
        "Overlay Strategies",
        options=list(strategy_returns.keys()),
        default=[]
    )

    # Plot equity curve
    fig = go.Figure()

    # Main equity curve
    if 'equity_curve' in performance and performance['equity_curve']:
        equity_data = performance['equity_curve']
        dates = list(equity_data.keys())
        values = list(equity_data.values())

        fig.add_trace(go.Scatter(
            x=dates,
            y=values,
            mode='lines',
            name='Combined',
            line=dict(color='blue', width=2)
        ))

    # Overlay selected strategies
    for strategy in strategies_to_show:
        perf = metrics_calc.get_strategy_performance(strategy)
        if 'equity_curve' in perf and perf['equity_curve']:
            equity_data = perf['equity_curve']
            dates = list(equity_data.keys())
            values = list(equity_data.values())

            fig.add_trace(go.Scatter(
                x=dates,
                y=values,
                mode='lines',
                name=strategy
            ))

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Equity ($)",
        hovermode='x unified',
        height=500
    )

    st.plotly_chart(fig, use_container_width=True)

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
