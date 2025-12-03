#!/usr/bin/env python3
"""
Signals History Page
Display and filter historical trading signals
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

sys.path.append(str(Path(__file__).parent.parent.parent))

from src.reporting import DataStore
import os


def show():
    st.title("📡 Signals History")

    # Initialize data store
    mongodb_url = os.getenv('MONGODB_URI') or os.getenv('mongodbconnectionstring') or "mongodb://mathematricks_mongodb:27017/mathematricks_trader"

    if not mongodb_url:
        st.error("MongoDB connection string not found in environment variables")
        return

    data_store = DataStore(mongodb_url)

    if not data_store.connect():
        st.error("Failed to connect to MongoDB")
        return

    # Filters
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        strategies = ['All'] + data_store.get_strategy_list()
        selected_strategy = st.selectbox("Strategy", strategies)

    with col2:
        signal_types = ['All', 'stock', 'options', 'multi_leg', 'stop_loss']
        selected_type = st.selectbox("Signal Type", signal_types)

    with col3:
        date_range = st.date_input(
            "Date Range",
            value=(datetime.now() - timedelta(days=7), datetime.now())
        )

    with col4:
        limit = st.number_input("Limit", min_value=10, max_value=1000, value=100)

    # Fetch signals
    strategy_filter = None if selected_strategy == 'All' else selected_strategy
    signals = data_store.get_signals(strategy_name=strategy_filter, limit=limit)

    # Filter by type
    if selected_type != 'All':
        signals = [s for s in signals if s.get('signal_type') == selected_type]

    # Display signals
    if signals:
        st.success(f"Found {len(signals)} signals")

        # Convert to DataFrame
        df_data = []
        for sig in signals:
            df_data.append({
                'Signal ID': sig.get('signal_id', 'N/A'),
                'Strategy': sig.get('strategy_name', 'N/A'),
                'Type': sig.get('signal_type', 'N/A'),
                'Timestamp': sig.get('timestamp', 'N/A'),
                'Signal': str(sig.get('signal_data', 'N/A'))[:100] + '...',
                'Executed': 'Yes' if sig.get('execution_results') else 'No'
            })

        df = pd.DataFrame(df_data)
        st.dataframe(df, use_container_width=True)

        # Export option
        if st.button("Export to CSV"):
            csv = df.to_csv(index=False)
            st.download_button(
                label="Download CSV",
                data=csv,
                file_name=f"signals_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )

    else:
        st.info("No signals found matching the filters")

    data_store.disconnect()
