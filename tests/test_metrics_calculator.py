"""
Unit tests for metrics_calculator module
"""

import pytest
import pandas as pd
import numpy as np
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../services/portfolio_builder'))

from metrics_calculator import (
    calculate_cagr,
    calculate_sharpe_ratio,
    calculate_max_drawdown,
    calculate_calmar_ratio,
    estimate_num_trades,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_sortino_ratio,
    calculate_all_metrics
)


class TestCalculateCAGR:
    """Tests for calculate_cagr function"""

    def test_calculate_cagr_positive_returns(self):
        """Test CAGR calculation with positive returns"""
        # 10% return over 365 days = 10% CAGR
        returns = pd.Series([10.0])  # Total 10% over period
        days = 365

        cagr = calculate_cagr(returns, days)

        assert cagr == pytest.approx(10.0, rel=0.1)

    def test_calculate_cagr_negative_returns(self):
        """Test CAGR calculation with negative returns"""
        # -10% return
        returns = pd.Series([-10.0])
        days = 365

        cagr = calculate_cagr(returns, days)

        assert cagr < 0

    def test_calculate_cagr_zero_days(self):
        """Test CAGR with zero days"""
        returns = pd.Series([10.0])
        days = 0

        cagr = calculate_cagr(returns, days)

        assert cagr == 0.0

    def test_calculate_cagr_multi_year(self):
        """Test CAGR over multiple years"""
        # 100% return over 2 years = ~41% CAGR
        # (2.0)^(1/2) - 1 = 0.414
        returns = pd.Series([100.0])
        days = 730

        cagr = calculate_cagr(returns, days)

        assert cagr == pytest.approx(41.4, rel=0.1)


class TestCalculateSharpeRatio:
    """Tests for calculate_sharpe_ratio function"""

    def test_calculate_sharpe_ratio_positive(self):
        """Test Sharpe ratio with positive returns"""
        # Consistent positive returns with some variance
        returns = pd.Series([1.0, 1.2, 0.8, 1.1, 0.9] * 50)  # ~1% daily average with variance

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe > 0

    def test_calculate_sharpe_ratio_volatile(self):
        """Test Sharpe ratio with volatile returns"""
        # High volatility should lower Sharpe
        returns = pd.Series([10.0, -10.0, 10.0, -10.0] * 63)  # 252 days

        sharpe = calculate_sharpe_ratio(returns)

        # With zero mean return, Sharpe should be ~0
        assert sharpe == pytest.approx(0, abs=0.5)

    def test_calculate_sharpe_ratio_zero_std(self):
        """Test Sharpe ratio with zero std dev"""
        returns = pd.Series([0.0] * 100)

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe == 0.0

    def test_calculate_sharpe_ratio_empty(self):
        """Test Sharpe ratio with empty returns"""
        returns = pd.Series([])

        sharpe = calculate_sharpe_ratio(returns)

        assert sharpe == 0.0


class TestCalculateMaxDrawdown:
    """Tests for calculate_max_drawdown function"""

    def test_calculate_max_drawdown_declining(self):
        """Test max drawdown with declining equity"""
        # 20% drawdown: 100k -> 80k
        equity = pd.Series([100000, 95000, 90000, 85000, 80000])

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 20.0

    def test_calculate_max_drawdown_recovery(self):
        """Test max drawdown with recovery"""
        # Drop 30% then recover
        equity = pd.Series([100000, 90000, 70000, 80000, 95000, 100000])

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 30.0

    def test_calculate_max_drawdown_no_drawdown(self):
        """Test max drawdown with only gains"""
        equity = pd.Series([100000, 105000, 110000, 115000])

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0

    def test_calculate_max_drawdown_empty(self):
        """Test max drawdown with empty series"""
        equity = pd.Series([])

        max_dd = calculate_max_drawdown(equity)

        assert max_dd == 0.0


class TestCalculateCalmarRatio:
    """Tests for calculate_calmar_ratio function"""

    def test_calculate_calmar_ratio_positive(self):
        """Test Calmar ratio with positive CAGR"""
        cagr = 25.5
        max_dd = 10.0

        calmar = calculate_calmar_ratio(cagr, max_dd)

        assert calmar == 2.55

    def test_calculate_calmar_ratio_zero_drawdown(self):
        """Test Calmar ratio with zero drawdown"""
        cagr = 25.5
        max_dd = 0.0

        calmar = calculate_calmar_ratio(cagr, max_dd)

        assert calmar == 0.0

    def test_calculate_calmar_ratio_negative_cagr(self):
        """Test Calmar ratio with negative CAGR"""
        cagr = -10.0
        max_dd = 20.0

        calmar = calculate_calmar_ratio(cagr, max_dd)

        assert calmar == -0.5


class TestEstimateNumTrades:
    """Tests for estimate_num_trades function"""

    def test_estimate_num_trades_from_margin(self):
        """Test trade estimation from margin data"""
        margin = pd.Series([0, 50000, 0, 60000, 0])

        num_trades = estimate_num_trades(margin_data=margin)

        assert num_trades == 2  # Two days with margin > 0

    def test_estimate_num_trades_from_returns(self):
        """Test trade estimation from returns"""
        returns = pd.Series([0, 2.5, 0, -1.2, 0.8])

        num_trades = estimate_num_trades(returns=returns)

        assert num_trades == 3  # Three days with non-zero returns

    def test_estimate_num_trades_no_data(self):
        """Test trade estimation with no data"""
        num_trades = estimate_num_trades()

        assert num_trades == 0


class TestCalculateWinRate:
    """Tests for calculate_win_rate function"""

    def test_calculate_win_rate_50_percent(self):
        """Test win rate with 50% wins"""
        returns = pd.Series([1.0, -1.0, 2.0, -2.0])

        win_rate = calculate_win_rate(returns)

        assert win_rate == 50.0

    def test_calculate_win_rate_100_percent(self):
        """Test win rate with all wins"""
        returns = pd.Series([1.0, 2.0, 3.0, 4.0])

        win_rate = calculate_win_rate(returns)

        assert win_rate == 100.0

    def test_calculate_win_rate_0_percent(self):
        """Test win rate with no wins"""
        returns = pd.Series([-1.0, -2.0, -3.0])

        win_rate = calculate_win_rate(returns)

        assert win_rate == 0.0

    def test_calculate_win_rate_empty(self):
        """Test win rate with empty returns"""
        returns = pd.Series([])

        win_rate = calculate_win_rate(returns)

        assert win_rate == 0.0


class TestCalculateProfitFactor:
    """Tests for calculate_profit_factor function"""

    def test_calculate_profit_factor_2to1(self):
        """Test profit factor of 2:1"""
        # Gains: 4, Losses: 2 = PF 2.0
        returns = pd.Series([2.0, -1.0, 2.0, -1.0])

        pf = calculate_profit_factor(returns)

        assert pf == 2.0

    def test_calculate_profit_factor_no_losses(self):
        """Test profit factor with no losses"""
        returns = pd.Series([1.0, 2.0, 3.0])

        pf = calculate_profit_factor(returns)

        assert pf == float('inf')

    def test_calculate_profit_factor_no_gains(self):
        """Test profit factor with no gains"""
        returns = pd.Series([-1.0, -2.0, -3.0])

        pf = calculate_profit_factor(returns)

        assert pf == 0.0

    def test_calculate_profit_factor_empty(self):
        """Test profit factor with empty returns"""
        returns = pd.Series([])

        pf = calculate_profit_factor(returns)

        assert pf == 0.0


class TestCalculateSortinoRatio:
    """Tests for calculate_sortino_ratio function"""

    def test_calculate_sortino_ratio_positive(self):
        """Test Sortino ratio with positive returns"""
        # More gains than losses
        returns = pd.Series([2.0, 1.0, -0.5, 1.5, -0.3] * 50)

        sortino = calculate_sortino_ratio(returns)

        assert sortino > 0

    def test_calculate_sortino_ratio_no_downside(self):
        """Test Sortino ratio with no negative returns"""
        returns = pd.Series([1.0, 2.0, 0.5, 1.5])

        sortino = calculate_sortino_ratio(returns)

        assert sortino == 0.0  # No downside deviation

    def test_calculate_sortino_ratio_empty(self):
        """Test Sortino ratio with empty returns"""
        returns = pd.Series([])

        sortino = calculate_sortino_ratio(returns)

        assert sortino == 0.0


class TestCalculateAllMetrics:
    """Tests for calculate_all_metrics function"""

    def test_calculate_all_metrics_full_data(self):
        """Test calculating all metrics with full data"""
        raw_data = [
            {
                'Date': '2025-01-01',
                'Daily_Return_Pct': 2.5,
                'Account_Equity': 100000,
                'Max_Margin_Used': 80000
            },
            {
                'Date': '2025-01-02',
                'Daily_Return_Pct': -1.2,
                'Account_Equity': 98800,
                'Max_Margin_Used': 47520
            },
            {
                'Date': '2025-01-03',
                'Daily_Return_Pct': 0.8,
                'Account_Equity': 99590,
                'Max_Margin_Used': 31836
            }
        ]

        metrics = calculate_all_metrics(raw_data)

        # Check all metrics are present
        assert 'cagr' in metrics
        assert 'sharpe_ratio' in metrics
        assert 'calmar_ratio' in metrics
        assert 'max_drawdown' in metrics
        assert 'num_trades' in metrics
        assert 'win_rate' in metrics
        assert 'profit_factor' in metrics
        assert 'sortino_ratio' in metrics
        assert 'total_return' in metrics
        assert 'num_days' in metrics
        assert 'start_date' in metrics
        assert 'end_date' in metrics

        # Verify some values
        assert metrics['num_days'] == 3
        assert metrics['start_date'] == '2025-01-01'
        assert metrics['end_date'] == '2025-01-03'
        assert metrics['num_trades'] == 3  # All days have margin
        assert metrics['win_rate'] == pytest.approx(66.67, rel=0.1)  # 2 wins out of 3

    def test_calculate_all_metrics_minimal_data(self):
        """Test calculating metrics with minimal data"""
        raw_data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800}
        ]

        metrics = calculate_all_metrics(raw_data)

        assert metrics['num_days'] == 2
        assert 'cagr' in metrics
        assert 'sharpe_ratio' in metrics

    def test_calculate_all_metrics_empty_data(self):
        """Test calculating metrics with empty data"""
        metrics = calculate_all_metrics([])

        assert metrics['cagr'] == 0.0
        assert metrics['sharpe_ratio'] == 0.0
        assert metrics['num_days'] == 0
        assert metrics['start_date'] is None
        assert metrics['end_date'] is None

    def test_calculate_all_metrics_realistic_strategy(self):
        """Test with realistic strategy data"""
        # Simulate 1 year of trading with 60% win rate
        np.random.seed(42)
        dates = pd.date_range('2024-01-01', periods=252, freq='D')
        returns = []
        equity = [100000]

        for i in range(252):
            # 60% chance of win
            if np.random.random() < 0.6:
                ret = np.random.uniform(0.5, 2.0)  # Win: 0.5% to 2%
            else:
                ret = np.random.uniform(-1.5, -0.3)  # Loss: -1.5% to -0.3%

            returns.append(ret)
            new_equity = equity[-1] * (1 + ret / 100)
            equity.append(new_equity)

        equity = equity[1:]  # Remove initial value

        raw_data = [
            {
                'Date': dates[i].strftime('%Y-%m-%d'),
                'Daily_Return_Pct': returns[i],
                'Account_Equity': equity[i],
                'Max_Margin_Used': equity[i] * 0.5
            }
            for i in range(252)
        ]

        metrics = calculate_all_metrics(raw_data)

        # Verify reasonable values
        assert metrics['num_days'] == 252
        assert -50 < metrics['cagr'] < 500  # Reasonable CAGR range (allowing for lucky runs)
        assert 0 < metrics['max_drawdown'] < 100  # Some drawdown expected
        assert 0 < metrics['win_rate'] <= 100
        assert metrics['num_trades'] == 252


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
