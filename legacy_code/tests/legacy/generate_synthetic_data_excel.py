#!/usr/bin/env python3
"""
Generate Synthetic Data Excel Template for Strategy Developers

This test script uses the existing synthetic data generation logic from
load_strategies_from_folder.py to create an Excel template showing sample
data format that strategy developers should provide.

Usage: python tests/generate_synthetic_data_excel.py
"""
import sys
import os
import pandas as pd
from datetime import datetime, timedelta
import random

# Add project root to path to import existing functions
PROJECT_ROOT = "/Users/vandanchopra/Vandan_Personal_Folder/CODE_STUFF/Projects/MathematricksTrader"
sys.path.append(PROJECT_ROOT)

def generate_sample_synthetic_data_formulas(strategy_id, days=90, starting_capital=1_000_000):
    """
    Generate sample data with Excel formulas showing synthetic data calculations

    Args:
        strategy_id: Strategy identifier (determines parameters)
        days: Number of days of sample data to generate
        starting_capital: Starting capital for equity curve

    Returns:
        List of daily data points with formula strings
    """

    # Strategy-specific parameters (copied from load_strategies_from_folder.py)
    DEFAULT_PARAMS = {
        'base_notional': 1_000_000,
        'base_margin': 100_000,
        'typical_contracts': 10
    }

    STRATEGY_PARAMS = {
        'SPY': {'base_notional': 500_000, 'base_margin': 250_000, 'typical_contracts': 5},
        'TLT': {'base_notional': 300_000, 'base_margin': 150_000, 'typical_contracts': 3},
        'SPX_0DTE_Opt': {'base_notional': 5_000_000, 'base_margin': 50_000, 'typical_contracts': 10},
        'SPX_1-D_Opt': {'base_notional': 4_000_000, 'base_margin': 40_000, 'typical_contracts': 10},
        'Forex': {'base_notional': 200_000, 'base_margin': 20_000, 'typical_contracts': 10},
        'Com1-Met': {'base_notional': 800_000, 'base_margin': 80_000, 'typical_contracts': 10},
        'Com2-Ag': {'base_notional': 600_000, 'base_margin': 60_000, 'typical_contracts': 10},
        'Com3-Mkt': {'base_notional': 900_000, 'base_margin': 90_000, 'typical_contracts': 10},
        'Com4-Misc': {'base_notional': 400_000, 'base_margin': 40_000, 'typical_contracts': 5}
    }

    # Get strategy parameters
    params = STRATEGY_PARAMS.get(strategy_id, DEFAULT_PARAMS)

    # Generate sample data with formulas
    data = []
    start_date = datetime.now() - timedelta(days=days)

    for i in range(days):
        current_date = start_date + timedelta(days=i)
        row_num = i + 2  # Excel row number (header is row 1, data starts row 2)

        # Daily Return %: Random between -0.5% and 1.5%
        daily_return_formula = '=RANDBETWEEN(-50,150)/100'

        # Account Equity:
        # - Put the starting capital into C2
        # - For rows >=3: Cn = C(n-1) * (1 + (B(n-1)/100))
        if i == 0:
            account_equity_formula = f'={starting_capital}'
        else:
            # Use previous row's equity and previous row's return
            prev_row = row_num - 1
            account_equity_formula = f'=C{prev_row}*(1+(B{prev_row}/100))'

        # Daily P&L: D2 = 0, for others Dn = Cn - C(n-1)
        if i == 0:
            daily_pnl_formula = '=0'
        else:
            prev_row = row_num - 1
            daily_pnl_formula = f'=C{row_num}-C{prev_row}'

        # Max Notional Value as requested:
        # ABS(Bn / MAX(ABS(B2:B91))) * $C$2 * 0.8
        # Use absolute references for the MAX range and starting equity $C$2
        max_row = days + 1
        notional_formula = f'=IF(B{row_num}=0,0,ABS(B{row_num}/MAX(ABS($B$2:$B${max_row})))*$C$2*0.8)'

        # Max Margin Used: = Max Notional / 3
        margin_formula = f'=IF(E{row_num}=0,0,E{row_num}/3)'

        data.append({
            'Date': current_date.strftime('%Y-%m-%d'),
            'Daily_Return_Pct': daily_return_formula,
            'Account_Equity': account_equity_formula,
            'Daily_PnL': daily_pnl_formula,
            'Max_Notional_Value': notional_formula,
            'Max_Margin_Used': margin_formula
        })

    return data

def create_excel_template():
    """
    Create Excel template with sample synthetic data for multiple strategy types
    """

    print("🔧 Generating synthetic data Excel template...")
    print("="*60)

    # Generate sample data for different strategy types
    sample_strategies = [
        'SPY',           # Equity
        'TLT',           # Bonds
        'SPX_0DTE_Opt',  # Options
        'Forex',         # Currency
        'Com1-Met'       # Commodities
    ]

    # Create Excel writer
    output_file = os.path.join(PROJECT_ROOT, 'strategy_data_template.xlsx')
    with pd.ExcelWriter(output_file, engine='openpyxl') as writer:

        # Create instructions sheet
        instructions_data = {
            'Field': [
                'Date',
                'Daily_Return_Pct',
                'Account_Equity',
                'Daily_PnL',
                'Max_Notional_Value',
                'Max_Margin_Used'
            ],
            'Description': [
                'Trading date (YYYY-MM-DD format)',
                'Daily return as percentage (e.g., 0.5 for 0.5%)',
                'Account equity at end of day ($)',
                'Profit/Loss for the day ($)',
                'Maximum notional value held during day ($)',
                'Maximum margin used during day ($)'
            ],
            'Required': ['Yes', 'Yes', 'Yes', 'Yes', 'Yes', 'Yes'],
            'Formula_Example': [
                'Static date',
                '=RANDBETWEEN(-50,150)/100',
                '=Previous_Equity*(1+Daily_Return_Pct/100)',
                '=Account_Equity-Previous_Account_Equity',
                '=IF(Daily_Return_Pct=0,0,Account_Equity*RANDBETWEEN(10,100)/1000)',
                '=IF(Notional_Value=0,0,Notional_Value*0.5)'
            ],
            'Notes': [
                'Must be chronological, no gaps',
                'Random: -0.5% to 1.5% range',
                'Running total from returns',
                'Difference from previous day',
                '1-10% of equity when trading',
                '50% of notional (typical margin)'
            ]
        }

        instructions_df = pd.DataFrame(instructions_data)
        instructions_df.to_excel(writer, sheet_name='Instructions', index=False)

        # Create sample data sheets for each strategy type
        for strategy_id in sample_strategies:
            print(f"   📊 Generating sample data for {strategy_id}...")

            # Generate 90 days of sample data with formulas
            sample_data = generate_sample_synthetic_data_formulas(strategy_id, days=90)

            # Convert to DataFrame
            df = pd.DataFrame(sample_data)

            # Write to Excel (formulas will be preserved)
            df.to_excel(writer, sheet_name=strategy_id, index=False)

    print(f"\n✅ Excel template created: {output_file}")
    print("\n📋 Template includes:")
    print("   • Instructions sheet with field descriptions and formula examples")
    print("   • Sample data sheets with Excel formulas for different strategy types:")
    for strategy in sample_strategies:
        print(f"     - {strategy}")
    print("\n📝 Notes:")
    print("   • Press F9 in Excel to recalculate random values")
    print("   • Formulas show how synthetic data is calculated")
    print("   • Daily_Return_Pct uses RANDBETWEEN for realistic ranges")
    print("   • Account_Equity builds cumulatively from returns")
    print("   • Notional/Margin only generated on trading days (non-zero returns)")
    print("   • Replace formulas with your real trading data")

if __name__ == "__main__":
    create_excel_template()