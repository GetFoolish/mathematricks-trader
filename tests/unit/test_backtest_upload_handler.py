"""
Unit tests for backtest_upload_handler module
"""

import pytest
import pandas as pd
from datetime import datetime
import sys
import os

# Add services directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../services/portfolio_builder'))

from backtest_upload_handler import (
    parse_csv,
    normalize_returns,
    detect_columns,
    generate_synthetic_columns,
    merge_backtest_data,
    calculate_backtest_hash,
    get_synthetic_warnings,
    BacktestUploadError
)


class TestParseCSV:
    """Tests for parse_csv function"""

    def test_parse_csv_full_data(self):
        """Test parsing CSV with all columns"""
        csv_content = b"""Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2025-01-01,2.5,100000,2500,80000,240000
2025-01-02,-1.2,98800,-1200,47520,142560"""

        df = parse_csv(csv_content)

        assert len(df) == 2
        assert 'Date' in df.columns
        assert 'Daily_Return_Pct' in df.columns
        assert df['Daily_Return_Pct'].iloc[0] == 2.5

    def test_parse_csv_minimal_data(self):
        """Test parsing CSV with only required columns"""
        csv_content = b"""Date,Daily_Return_Pct
2025-01-01,2.5
2025-01-02,-1.2"""

        df = parse_csv(csv_content)

        assert len(df) == 2
        assert 'Date' in df.columns
        assert 'Daily_Return_Pct' in df.columns

    def test_parse_csv_empty_file(self):
        """Test parsing empty CSV file"""
        csv_content = b"""Date,Daily_Return_Pct
"""

        with pytest.raises(BacktestUploadError, match="Cannot upload empty strategy"):
            parse_csv(csv_content)

    def test_parse_csv_missing_required_column(self):
        """Test parsing CSV missing required column"""
        csv_content = b"""Date,Account_Equity
2025-01-01,100000"""

        with pytest.raises(BacktestUploadError, match="Required column.*Daily_Return_Pct"):
            parse_csv(csv_content)

    def test_parse_csv_invalid_date_format(self):
        """Test parsing CSV with invalid date format"""
        csv_content = b"""Date,Daily_Return_Pct
INVALID,2.5"""

        with pytest.raises(BacktestUploadError, match="Invalid date format"):
            parse_csv(csv_content)

    def test_parse_csv_sorts_by_date(self):
        """Test that CSV is sorted by date"""
        csv_content = b"""Date,Daily_Return_Pct
2025-01-03,0.8
2025-01-01,2.5
2025-01-02,-1.2"""

        df = parse_csv(csv_content)

        dates = df['Date'].tolist()
        assert dates[0] == pd.Timestamp('2025-01-01')
        assert dates[1] == pd.Timestamp('2025-01-02')
        assert dates[2] == pd.Timestamp('2025-01-03')


class TestNormalizeReturns:
    """Tests for normalize_returns function"""

    def test_normalize_returns_percentage(self):
        """Test normalizing already percentage format"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2]
        })

        result = normalize_returns(df)

        assert result['Daily_Return_Pct'].iloc[0] == 2.5
        assert result['Daily_Return_Pct'].iloc[1] == -1.2

    def test_normalize_returns_decimal(self):
        """Test normalizing decimal format to percentage"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [0.025, -0.012]
        })

        result = normalize_returns(df)

        assert result['Daily_Return_Pct'].iloc[0] == 2.5
        assert result['Daily_Return_Pct'].iloc[1] == -1.2

    def test_normalize_returns_invalid_value(self):
        """Test normalizing with invalid (non-numeric) value"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': ['INVALID', 2.5]
        })

        with pytest.raises(BacktestUploadError, match="Invalid return value"):
            normalize_returns(df)


class TestDetectColumns:
    """Tests for detect_columns function"""

    def test_detect_columns_all_present(self):
        """Test detection when all columns present"""
        df = pd.DataFrame({
            'Date': [],
            'Daily_Return_Pct': [],
            'Account_Equity': [],
            'Daily_PnL': [],
            'Max_Margin_Used': [],
            'Max_Notional_Value': []
        })

        result = detect_columns(df)

        assert result['Account_Equity'] == True
        assert result['Daily_PnL'] == True
        assert result['Max_Margin_Used'] == True
        assert result['Max_Notional_Value'] == True

    def test_detect_columns_missing_margin(self):
        """Test detection when margin columns missing"""
        df = pd.DataFrame({
            'Date': [],
            'Daily_Return_Pct': [],
            'Account_Equity': [],
            'Daily_PnL': []
        })

        result = detect_columns(df)

        assert result['Account_Equity'] == True
        assert result['Daily_PnL'] == True
        assert result['Max_Margin_Used'] == False
        assert result['Max_Notional_Value'] == False

    def test_detect_columns_minimal(self):
        """Test detection with only required columns"""
        df = pd.DataFrame({
            'Date': [],
            'Daily_Return_Pct': []
        })

        result = detect_columns(df)

        assert result['Account_Equity'] == False
        assert result['Daily_PnL'] == False
        assert result['Max_Margin_Used'] == False
        assert result['Max_Notional_Value'] == False


class TestGenerateSyntheticColumns:
    """Tests for generate_synthetic_columns function"""

    def test_generate_synthetic_account_equity(self):
        """Test generating synthetic Account_Equity"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03']),
            'Daily_Return_Pct': [2.5, -1.2, 0.8]
        })

        result_df, generated = generate_synthetic_columns(df, starting_capital=100000)

        assert 'Account_Equity' in result_df.columns
        assert 'Account_Equity' in generated
        # Day 1: Starting equity
        assert result_df['Account_Equity'].iloc[0] == 100000
        # Day 2: equity[0] * (1 + return[1]/100) = 100000 * (1 - 0.012) = 98800
        assert result_df['Account_Equity'].iloc[1] == pytest.approx(98800, rel=0.01)

    def test_generate_synthetic_daily_pnl(self):
        """Test generating synthetic Daily_PnL"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2]
        })

        result_df, generated = generate_synthetic_columns(df)

        assert 'Daily_PnL' in result_df.columns
        assert 'Daily_PnL' in generated
        # First day PnL should be 2.5% of starting equity
        assert result_df['Daily_PnL'].iloc[0] == pytest.approx(2500, rel=0.01)

    def test_generate_synthetic_margin(self):
        """Test generating synthetic Max_Margin_Used"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02', '2025-01-03']),
            'Daily_Return_Pct': [2.5, -1.2, 0.8]
        })

        result_df, generated = generate_synthetic_columns(df)

        assert 'Max_Margin_Used' in result_df.columns
        assert 'Max_Margin_Used' in generated

        # Day with highest return (2.5%) should have highest margin
        max_margin_day = result_df.loc[result_df['Daily_Return_Pct'].abs().idxmax(), 'Max_Margin_Used']
        assert max_margin_day > 0

    def test_generate_synthetic_notional(self):
        """Test generating synthetic Max_Notional_Value"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2]
        })

        result_df, generated = generate_synthetic_columns(df)

        assert 'Max_Notional_Value' in result_df.columns
        assert 'Max_Notional_Value' in generated

        # Notional should be 3x margin
        assert result_df['Max_Notional_Value'].iloc[0] == pytest.approx(
            result_df['Max_Margin_Used'].iloc[0] * 3,
            rel=0.01
        )

    def test_generate_synthetic_all_columns(self):
        """Test generating all synthetic columns"""
        df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2]
        })

        result_df, generated = generate_synthetic_columns(df)

        assert len(generated) == 4
        assert 'Account_Equity' in generated
        assert 'Daily_PnL' in generated
        assert 'Max_Margin_Used' in generated
        assert 'Max_Notional_Value' in generated


class TestMergeBacktestData:
    """Tests for merge_backtest_data function"""

    def test_merge_backtest_new_dates(self):
        """Test merging with new dates (no overlap)"""
        existing_data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800}
        ]

        new_df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-03', '2025-01-04']),
            'Daily_Return_Pct': [0.8, 1.5],
            'Account_Equity': [99590, 101084]
        })

        merged_data, info = merge_backtest_data(existing_data, new_df, force_replace=False)

        assert len(merged_data) == 4
        assert info['dates_added'] == 2
        assert info['dates_replaced'] == 0
        assert len(info['overlapping_dates']) == 0

    def test_merge_backtest_overlap_without_force(self):
        """Test merging with overlapping dates without force_replace"""
        existing_data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800},
            {'Date': '2025-01-03', 'Daily_Return_Pct': 0.8, 'Account_Equity': 99590}
        ]

        new_df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-03', '2025-01-04']),
            'Daily_Return_Pct': [1.2, 1.5],
            'Account_Equity': [99800, 101297]
        })

        with pytest.raises(BacktestUploadError, match="Dates already exist.*2025-01-03"):
            merge_backtest_data(existing_data, new_df, force_replace=False)

    def test_merge_backtest_overlap_with_force(self):
        """Test merging with overlapping dates with force_replace"""
        existing_data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800},
            {'Date': '2025-01-03', 'Daily_Return_Pct': 0.8, 'Account_Equity': 99590}
        ]

        new_df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-03', '2025-01-04']),
            'Daily_Return_Pct': [1.2, 1.5],
            'Account_Equity': [99800, 101297]
        })

        merged_data, info = merge_backtest_data(existing_data, new_df, force_replace=True)

        assert len(merged_data) == 4  # 3 existing - 1 replaced + 2 new = 4
        assert info['dates_replaced'] == 1
        assert info['dates_added'] == 1
        assert '2025-01-03' in info['overlapping_dates']

        # Verify 2025-01-03 was replaced with new value
        jan_03_data = [d for d in merged_data if d['Date'].strftime('%Y-%m-%d') == '2025-01-03'][0]
        assert jan_03_data['Daily_Return_Pct'] == 1.2  # New value, not old 0.8

    def test_merge_backtest_new_columns(self):
        """Test merging with new columns added"""
        existing_data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800}
        ]

        new_df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2],
            'Account_Equity': [100000, 98800],
            'Max_Margin_Used': [78000, 48000]  # New column
        })

        merged_data, info = merge_backtest_data(existing_data, new_df, force_replace=True)

        assert 'Max_Margin_Used' in info['columns_added']
        # Old rows should be backfilled with synthetic Max_Margin_Used

    def test_merge_backtest_no_existing_data(self):
        """Test merging when no existing data (first upload)"""
        new_df = pd.DataFrame({
            'Date': pd.to_datetime(['2025-01-01', '2025-01-02']),
            'Daily_Return_Pct': [2.5, -1.2],
            'Account_Equity': [100000, 98800]
        })

        merged_data, info = merge_backtest_data(None, new_df, force_replace=False)

        assert len(merged_data) == 2
        assert info['dates_added'] == 2


class TestCalculateBacktestHash:
    """Tests for calculate_backtest_hash function"""

    def test_calculate_backtest_hash(self):
        """Test hash calculation"""
        data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800}
        ]

        hash_val = calculate_backtest_hash(data)

        assert isinstance(hash_val, str)
        assert len(hash_val) == 64  # SHA256 produces 64 hex characters

    def test_calculate_backtest_hash_consistency(self):
        """Test that same data produces same hash"""
        data = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000},
            {'Date': '2025-01-02', 'Daily_Return_Pct': -1.2, 'Account_Equity': 98800}
        ]

        hash1 = calculate_backtest_hash(data)
        hash2 = calculate_backtest_hash(data)

        assert hash1 == hash2

    def test_calculate_backtest_hash_different_data(self):
        """Test that different data produces different hash"""
        data1 = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.5, 'Account_Equity': 100000}
        ]

        data2 = [
            {'Date': '2025-01-01', 'Daily_Return_Pct': 2.6, 'Account_Equity': 100000}
        ]

        hash1 = calculate_backtest_hash(data1)
        hash2 = calculate_backtest_hash(data2)

        assert hash1 != hash2


class TestGetSyntheticWarnings:
    """Tests for get_synthetic_warnings function"""

    def test_get_synthetic_warnings(self):
        """Test generating synthetic warnings"""
        generated_columns = ['Account_Equity', 'Max_Margin_Used']

        warnings = get_synthetic_warnings(generated_columns)

        assert len(warnings) == 2
        assert warnings[0]['column'] == 'Account_Equity'
        assert '⚠️' in warnings[0]['message']
        assert 'formula' in warnings[0]

    def test_get_synthetic_warnings_empty(self):
        """Test with no generated columns"""
        warnings = get_synthetic_warnings([])

        assert len(warnings) == 0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
