"""
Margin Calculation Module

Provides asset-specific margin calculators that fetch real-time prices
and margin requirements from brokers.
"""

from .factory import MarginCalculatorFactory

__all__ = ['MarginCalculatorFactory']
