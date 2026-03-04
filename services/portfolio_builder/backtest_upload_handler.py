"""
Backtest Upload Handler

This module handles CSV parsing, validation, synthetic data generation,
incremental updates, and hash tracking for strategy backtest data.
"""

import hashlib
import pandas as pd
from datetime import datetime
from typing import Dict, List, Tuple, Optional, Any
import numpy as np


class BacktestUploadError(Exception):
    """Custom exception for backtest upload errors"""
    pass


def parse_csv(file_content: bytes) -> pd.DataFrame:
    """
    Parse CSV file content into a pandas DataFrame.

    Args:
        file_content: Raw CSV file bytes

    Returns:
        DataFrame with parsed data

    Raises:
        BacktestUploadError: If file is empty, has invalid format, or missing required columns
    """
    try:
        # Try to read CSV
        df = pd.read_csv(pd.io.common.BytesIO(file_content))

        # Check if file is empty
        if len(df) == 0:
            raise BacktestUploadError("Cannot upload empty strategy. At least 1 data row required.")

        # Check for required columns
        required_columns = ['date', 'return']
        missing_columns = [col for col in required_columns if col not in df.columns]

        if missing_columns:
            raise BacktestUploadError(f"Required column(s) missing: {', '.join(missing_columns)}")

        # Parse dates
        try:
            df['date'] = pd.to_datetime(df['date'])
        except Exception as e:
            raise BacktestUploadError(f"Invalid date format. Expected YYYY-MM-DD. Error: {str(e)}")

        # Sort by date
        df = df.sort_values('date').reset_index(drop=True)

        return df

    except pd.errors.EmptyDataError:
        raise BacktestUploadError("CSV file is empty")
    except pd.errors.ParserError as e:
        raise BacktestUploadError(f"Invalid CSV format: {str(e)}")
    except BacktestUploadError:
        raise
    except Exception as e:
        raise BacktestUploadError(f"Failed to parse CSV: {str(e)}")


def normalize_returns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize return values to percentage format.
    Handles both decimal (0.025) and percentage (2.5) formats.

    Args:
        df: DataFrame with 'return' column

    Returns:
        DataFrame with normalized returns

    Raises:
        BacktestUploadError: If return values are invalid
    """
    try:
        # Validate all returns are numeric
        if not pd.api.types.is_numeric_dtype(df['return']):
            # Try to convert to numeric, will raise error if fails
            df['return'] = pd.to_numeric(df['return'], errors='coerce')

            # Check for any NaN values (failed conversions)
            invalid_rows = df[df['return'].isna()]
            if len(invalid_rows) > 0:
                first_invalid = invalid_rows.iloc[0]
                raise BacktestUploadError(
                    f"Invalid return value on row {invalid_rows.index[0] + 2}. Must be numeric."
                )

        # Detect if values are in decimal format (all values between -1 and 1)
        if df['return'].abs().max() <= 1.0:
            # Convert decimal to percentage (0.025 -> 2.5)
            df['return'] = df['return'] * 100

        return df

    except BacktestUploadError:
        raise
    except Exception as e:
        raise BacktestUploadError(f"Failed to normalize returns: {str(e)}")


def detect_columns(df: pd.DataFrame) -> Dict[str, bool]:
    """
    Detect which optional columns are present/missing.

    Args:
        df: DataFrame to check

    Returns:
        Dictionary mapping column names to presence (True/False)
    """
    optional_columns = [
        'account_equity',
        'pnl',
        'margin_used',
        'notional_value'
    ]

    return {col: col in df.columns for col in optional_columns}


def generate_synthetic_columns(
    df: pd.DataFrame,
    starting_capital: float = 100000.0
) -> Tuple[pd.DataFrame, List[str]]:
    """
    Generate synthetic columns for missing data using formulas.

    Formulas:
    - account_equity: equity[i] = equity[i-1] * (1 + return[i] / 100)
    - pnl: equity[i] - equity[i-1]
    - margin_used: (|return[i]| / max_return) * equity[i] * 0.8
    - notional_value: margin[i] * 3

    Args:
        df: DataFrame with at least date and return
        starting_capital: Starting equity value (default: $100,000)

    Returns:
        Tuple of (DataFrame with synthetic columns, list of generated column names)
    """
    df = df.copy()
    generated_columns = []

    # Generate account_equity if missing
    if 'account_equity' not in df.columns:
        equity = [starting_capital]
        for i in range(1, len(df)):
            prev_equity = equity[i-1]
            return_pct = df.iloc[i]['return']
            new_equity = prev_equity * (1 + return_pct / 100)
            equity.append(new_equity)

        df['account_equity'] = equity
        generated_columns.append('account_equity')

    # Generate pnl if missing
    if 'pnl' not in df.columns:
        pnl = [0]  # First day has no previous equity
        for i in range(1, len(df)):
            pnl.append(df.iloc[i]['account_equity'] - df.iloc[i-1]['account_equity'])

        # For first day, calculate from return
        pnl[0] = df.iloc[0]['account_equity'] * (df.iloc[0]['return'] / 100)

        df['pnl'] = pnl
        generated_columns.append('pnl')

    # Generate margin_used if missing
    if 'margin_used' not in df.columns:
        max_return = df['return'].abs().max()

        # Avoid division by zero
        if max_return == 0:
            df['margin_used'] = 0
        else:
            df['margin_used'] = (
                df['return'].abs() / max_return
            ) * df['account_equity'] * 0.8

        generated_columns.append('margin_used')

    # Generate notional_value if missing
    if 'notional_value' not in df.columns:
        df['notional_value'] = df['margin_used'] * 3
        generated_columns.append('notional_value')

    return df, generated_columns


def merge_backtest_data(
    existing_data: Optional[List[Dict[str, Any]]],
    new_df: pd.DataFrame,
    force_replace: bool = False
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Merge new backtest data with existing data, handling overlaps and new columns.

    Args:
        existing_data: Existing backtest data as list of dicts (or None if new strategy)
        new_df: New data to merge
        force_replace: If True, replace overlapping dates; if False, raise error on overlap

    Returns:
        Tuple of (merged data as list of dicts, merge info dict)

    Raises:
        BacktestUploadError: If dates overlap and force_replace is False
    """
    merge_info = {
        'dates_added': 0,
        'dates_replaced': 0,
        'columns_added': [],
        'overlapping_dates': []
    }

    # If no existing data, just convert new data
    if existing_data is None or len(existing_data) == 0:
        merge_info['dates_added'] = len(new_df)
        return new_df.to_dict('records'), merge_info

    # Convert existing data to DataFrame
    existing_df = pd.DataFrame(existing_data)
    existing_df['date'] = pd.to_datetime(existing_df['date'])

    # Detect new columns
    existing_cols = set(existing_df.columns)
    new_cols = set(new_df.columns)
    added_cols = new_cols - existing_cols

    if added_cols:
        merge_info['columns_added'] = list(added_cols)

        # For new columns, backfill existing data with synthetic values
        for col in added_cols:
            if col not in ['date', 'return']:
                # Generate synthetic data for existing rows for this column
                temp_df = existing_df.copy()
                temp_df[col] = None  # Add column as None

                # Generate synthetic value based on column type
                if col == 'account_equity' and 'account_equity' not in existing_df.columns:
                    # Generate equity curve
                    equity = [100000]
                    for i in range(1, len(temp_df)):
                        prev_equity = equity[i-1]
                        return_pct = temp_df.iloc[i]['return']
                        equity.append(prev_equity * (1 + return_pct / 100))
                    existing_df[col] = equity

                elif col == 'pnl':
                    if 'account_equity' in existing_df.columns:
                        pnl = [0]
                        for i in range(1, len(existing_df)):
                            pnl.append(existing_df.iloc[i]['account_equity'] - existing_df.iloc[i-1]['account_equity'])
                        existing_df[col] = pnl
                    else:
                        existing_df[col] = 0

                elif col == 'margin_used':
                    if 'account_equity' in existing_df.columns:
                        max_return = existing_df['return'].abs().max()
                        if max_return > 0:
                            existing_df[col] = (
                                existing_df['return'].abs() / max_return
                            ) * existing_df['account_equity'] * 0.8
                        else:
                            existing_df[col] = 0
                    else:
                        existing_df[col] = 0

                elif col == 'notional_value':
                    if 'margin_used' in existing_df.columns:
                        existing_df[col] = existing_df['margin_used'] * 3
                    else:
                        existing_df[col] = 0

    # Check for overlapping dates
    existing_dates = set(existing_df['date'])
    new_dates = set(new_df['date'])
    overlapping = existing_dates.intersection(new_dates)

    if overlapping:
        merge_info['overlapping_dates'] = sorted([d.strftime('%Y-%m-%d') for d in overlapping])

        if not force_replace:
            overlap_str = ', '.join(merge_info['overlapping_dates'][:5])
            if len(merge_info['overlapping_dates']) > 5:
                overlap_str += f" (+{len(merge_info['overlapping_dates']) - 5} more)"
            raise BacktestUploadError(
                f"Dates already exist: {overlap_str}. Enable 'Force Replace' to overwrite."
            )

        # Replace overlapping dates
        merge_info['dates_replaced'] = len(overlapping)
        existing_df = existing_df[~existing_df['date'].isin(overlapping)]

    # Merge dataframes
    merged_df = pd.concat([existing_df, new_df], ignore_index=True)
    merged_df = merged_df.sort_values('date').reset_index(drop=True)

    # Count new dates added
    merge_info['dates_added'] = len(new_dates - overlapping)

    return merged_df.to_dict('records'), merge_info


def calculate_backtest_hash(data: List[Dict[str, Any]]) -> str:
    """
    Calculate SHA256 hash of backtest data for version tracking.
    Only hashes the raw_data_backtest_full, not metrics.

    Args:
        data: List of dictionaries containing backtest data

    Returns:
        SHA256 hash as hex string
    """
    # Convert to DataFrame and sort by date for consistency
    df = pd.DataFrame(data)
    df = df.sort_values('date').reset_index(drop=True)

    # Convert to JSON string (sorted columns for consistency)
    data_str = df.to_json(orient='records', date_format='iso')

    # Calculate SHA256 hash
    hash_obj = hashlib.sha256(data_str.encode('utf-8'))
    return hash_obj.hexdigest()


def invalidate_allocations_for_strategy(
    db,
    strategy_id: str,
    new_hash: str,
    reason: str = "Strategy backtest data updated"
) -> int:
    """
    Mark all ACTIVE allocations for a strategy as OUTDATED.

    Args:
        db: MongoDB database connection
        strategy_id: ID of the strategy
        new_hash: New hash value for the strategy
        reason: Reason for invalidation

    Returns:
        Number of allocations invalidated
    """
    from datetime import datetime

    # Find all ACTIVE allocations using this strategy
    result = db.portfolio_allocations.update_many(
        {
            'strategy_id': strategy_id,
            'approval_status': 'ACTIVE'
        },
        {
            '$set': {
                'approval_status': 'OUTDATED',
                'outdated_reason': reason,
                'outdated_at': datetime.utcnow(),
                'new_strategy_hash': new_hash
            }
        }
    )

    return result.modified_count


def get_synthetic_warnings(generated_columns: List[str]) -> List[Dict[str, str]]:
    """
    Generate user-friendly warning messages for synthetic columns.

    Args:
        generated_columns: List of column names that were generated synthetically

    Returns:
        List of warning dictionaries with column name and formula
    """
    formulas = {
        'Account_Equity': 'equity[i] = equity[i-1] × (1 + return/100) starting at $100,000',
        'Daily_PnL': 'pnl[i] = equity[i] - equity[i-1]',
        'Max_Margin_Used': 'margin[i] = (|return[i]| / max_return) × equity[i] × 0.8',
        'Max_Notional_Value': 'notional[i] = margin[i] × 3'
    }

    warnings = []
    for col in generated_columns:
        warnings.append({
            'column': col,
            'formula': formulas.get(col, 'Unknown formula'),
            'message': f"⚠️ Generated synthetic {col} using formula: {formulas.get(col, 'Unknown')}"
        })

    return warnings
