"""
Tearsheet Generator using QuantStats
"""
import pandas as pd
import quantstats as qs
from typing import Optional


def generate_tearsheet(
    returns_series: pd.Series,
    output_path: str,
    title: str = 'Portfolio Performance',
    benchmark: Optional[pd.Series] = None
):
    """
    Generate QuantStats HTML tearsheet.
    
    Args:
        returns_series: Pandas Series of returns with datetime index
        output_path: Path to save HTML file
        title: Title for the tearsheet
        benchmark: Optional benchmark returns series
    """
    print(f"\nGenerating tearsheet: {title}")
    print(f"  Returns: {len(returns_series)} data points")
    print(f"  Output: {output_path}")
    
    # Ensure returns_series has proper datetime index
    if not isinstance(returns_series.index, pd.DatetimeIndex):
        print("  ⚠️  Converting index to DatetimeIndex")
        returns_series.index = pd.to_datetime(returns_series.index)
    
    # Generate HTML report
    qs.reports.html(
        returns_series,
        benchmark=benchmark,
        output=output_path,
        title=title,
        download_filename=output_path
    )
    
    print(f"  ✓ Tearsheet generated successfully")
