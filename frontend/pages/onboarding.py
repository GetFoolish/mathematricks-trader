#!/usr/bin/env python3
"""
Strategy Onboarding Page
Placeholder for future strategy onboarding functionality
"""

import streamlit as st


def show():
    st.title("🚀 Strategy Onboarding")

    st.markdown("""
    <div style="text-align: center; padding: 3rem;">
        <h1 style="font-size: 4rem;">🚧</h1>
        <h2>Coming Soon</h2>
        <p style="font-size: 1.2rem; color: #666;">
            Strategy onboarding functionality is under development.
        </p>
        <p style="color: #888;">
            This feature will allow you to:
        </p>
        <ul style="text-align: left; max-width: 600px; margin: 2rem auto;">
            <li>Register new trading strategies</li>
            <li>Configure strategy parameters</li>
            <li>Set risk limits and allocation</li>
            <li>Test strategies in paper trading mode</li>
            <li>Deploy strategies to live trading</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # Placeholder form (disabled)
    with st.expander("Preview: Strategy Registration Form (Coming Soon)", expanded=False):
        st.text_input("Strategy Name", disabled=True, placeholder="e.g., Momentum Strategy v1")
        st.text_area("Description", disabled=True, placeholder="Describe your strategy...")
        st.selectbox("Asset Class", ["Stocks", "Options", "Crypto", "Forex"], disabled=True)
        st.number_input("Max Position Size (%)", min_value=1, max_value=100, disabled=True)
        st.button("Register Strategy", disabled=True)
