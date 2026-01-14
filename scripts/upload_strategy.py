#!/usr/bin/env python3
"""
CLI Script: Upload Strategy to MongoDB

This script allows you to upload strategy backtest data from the command line.
It replicates the public submission portal functionality for testing purposes.

Usage:
    python scripts/upload_strategy.py --file backtest.csv --name "John Doe" --email "john@example.com" --note "My strategy"

Options:
    --file PATH         Path to CSV backtest file (required)
    --name TEXT         Developer name (required)
    --email TEXT        Developer email (required)
    --note TEXT         Strategy description/notes (optional)
    --strategy-name TEXT Name of the strategy (optional, defaults to filename)
    --starting-capital FLOAT  Starting capital for synthetic data (default: 1000000)
    --api-url URL       Backend API URL (default: http://localhost:8003)
"""

import os
import sys
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ANSI color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^80}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'=' * 80}{Colors.ENDC}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.ENDC}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.ENDC}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.ENDC}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.ENDC}")


def format_number(num, decimals=2):
    """Format number with thousands separator"""
    return f"{num:,.{decimals}f}"


def print_metrics_tearsheet(metrics, submission_id, equity_curve_length):
    """Print formatted metrics tearsheet"""
    print_header("STRATEGY PERFORMANCE TEARSHEET")

    print(f"{Colors.BOLD}Submission Details:{Colors.ENDC}")
    print(f"  Submission ID: {Colors.CYAN}{submission_id}{Colors.ENDC}")
    print(f"  Status:        {Colors.YELLOW}PENDING_APPROVAL{Colors.ENDC}")
    print()

    print(f"{Colors.BOLD}Key Performance Metrics:{Colors.ENDC}")
    print(f"  CAGR:               {format_number(metrics['cagr'])}%")
    print(f"  Sharpe Ratio:       {format_number(metrics['sharpe_ratio'], 3)}")
    print(f"  Calmar Ratio:       {format_number(metrics['calmar_ratio'], 3)}")
    print(f"  Max Drawdown:       {format_number(metrics['max_drawdown'])}%")
    print(f"  Total Return:       {format_number(metrics['total_return'])}%")
    print()

    print(f"{Colors.BOLD}Risk Metrics:{Colors.ENDC}")
    print(f"  Volatility (Ann.):  {format_number(metrics.get('volatility_annual', 0))}%")
    print(f"  Sortino Ratio:      {format_number(metrics.get('sortino_ratio', 0), 3)}")
    print(f"  Win Rate:           {format_number(metrics.get('win_rate', 0))}%")
    print(f"  Profit Factor:      {format_number(metrics.get('profit_factor', 0), 3)}")
    print()

    print(f"{Colors.BOLD}Backtest Period:{Colors.ENDC}")
    print(f"  Start Date:         {metrics.get('start_date', 'N/A')}")
    print(f"  End Date:           {metrics.get('end_date', 'N/A')}")
    print(f"  Total Days:         {format_number(metrics.get('num_days', 0), 0)}")
    print(f"  Equity Curve Points: {format_number(equity_curve_length, 0)}")
    print()


def upload_strategy(args):
    """
    Upload strategy backtest to backend API

    Returns:
        dict: Response data from server
    """
    # Validate file exists
    file_path = Path(args.file)
    if not file_path.exists():
        raise FileNotFoundError(f"CSV file not found: {args.file}")

    # Determine strategy name
    strategy_name = args.strategy_name or file_path.stem

    print_header("STRATEGY UPLOAD")

    print(f"{Colors.BOLD}Upload Details:{Colors.ENDC}")
    print(f"  File:           {file_path.name}")
    print(f"  Strategy Name:  {strategy_name}")
    print(f"  Developer:      {args.name} <{args.email}>")
    print(f"  Note:           {args.note or '(none)'}")
    print(f"  Starting Capital: ${format_number(args.starting_capital, 0)}")
    print(f"  API URL:        {args.api_url}")
    print()

    # Prepare multipart form data
    files = {
        'file': (file_path.name, open(file_path, 'rb'), 'text/csv')
    }

    data = {
        'strategy_name': strategy_name,
        'developer_name': args.name,
        'developer_email': args.email,
        'developer_note': args.note,
        'starting_capital': args.starting_capital
    }

    # Upload to API
    api_endpoint = f"{args.api_url}/api/v1/public/submit-strategy"

    print_info(f"Uploading to {api_endpoint}...")

    try:
        response = requests.post(
            api_endpoint,
            files=files,
            data=data,
            timeout=60
        )

        # Close file
        files['file'][1].close()

        # Check response
        response.raise_for_status()

        result = response.json()

        if result['status'] == 'success':
            print_success("Strategy uploaded successfully!")
            return result
        else:
            print_error(f"Upload failed: {result.get('message', 'Unknown error')}")
            return None

    except requests.exceptions.ConnectionError:
        print_error(f"Cannot connect to API at {args.api_url}")
        print_info("Make sure the PortfolioBuilder service is running on port 8003")
        print_info("Start it with: python services/portfolio_builder/main.py")
        return None
    except requests.exceptions.Timeout:
        print_error("Request timed out (60 seconds)")
        return None
    except requests.exceptions.HTTPError as e:
        print_error(f"HTTP Error: {e.response.status_code}")
        try:
            error_detail = e.response.json()
            print_error(f"Details: {error_detail.get('detail', 'Unknown error')}")
        except:
            print_error(f"Details: {e.response.text}")
        return None
    except Exception as e:
        print_error(f"Unexpected error: {str(e)}")
        return None


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Upload strategy backtest data to MongoDB via API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic upload
  python scripts/upload_strategy.py --file backtest.csv --name "John Doe" --email "john@example.com"

  # With strategy name and note
  python scripts/upload_strategy.py \\
    --file data/my_strategy.csv \\
    --name "Jane Smith" \\
    --email "jane@example.com" \\
    --strategy-name "SPX Momentum V2" \\
    --note "Updated with trailing stops"

  # With custom starting capital
  python scripts/upload_strategy.py \\
    --file backtest.csv \\
    --name "John Doe" \\
    --email "john@example.com" \\
    --starting-capital 500000
        """
    )

    parser.add_argument(
        '--file',
        required=True,
        help='Path to CSV backtest file'
    )

    parser.add_argument(
        '--name',
        required=True,
        help='Developer name (e.g., "John Doe")'
    )

    parser.add_argument(
        '--email',
        required=True,
        help='Developer email address'
    )

    parser.add_argument(
        '--note',
        default='',
        help='Strategy description/notes (optional)'
    )

    parser.add_argument(
        '--strategy-name',
        default=None,
        help='Name of the strategy (defaults to filename)'
    )

    parser.add_argument(
        '--starting-capital',
        type=float,
        default=1000000.0,
        help='Starting capital for synthetic data generation (default: 1000000)'
    )

    parser.add_argument(
        '--api-url',
        default='http://localhost:8003',
        help='Backend API URL (default: http://localhost:8003)'
    )

    args = parser.parse_args()

    # Upload strategy
    result = upload_strategy(args)

    if not result:
        sys.exit(1)

    # Print tearsheet
    print_metrics_tearsheet(
        result['metrics'],
        result['submission_id'],
        len(result['equity_curve'])
    )

    # Print warnings
    if result.get('warnings'):
        print(f"{Colors.BOLD}Warnings:{Colors.ENDC}")
        for warning in result['warnings']:
            print_warning(warning)
        print()

    # Print synthetic columns
    if result.get('synthetic_columns'):
        print(f"{Colors.BOLD}Synthetic Columns Generated:{Colors.ENDC}")
        for col in result['synthetic_columns']:
            print(f"  • {col}")
        print()

    # Print next steps
    print_header("NEXT STEPS")
    print(f"1. Your submission ID: {Colors.CYAN}{result['submission_id']}{Colors.ENDC}")
    print(f"2. Status: {Colors.YELLOW}PENDING_APPROVAL{Colors.ENDC}")
    print(f"3. Check status at: {args.api_url}/api/v1/public/submission/{result['submission_id']}")
    print(f"4. Admin will review and approve/reject your strategy")
    print()

    print_success("Upload complete! Check your email for updates.")
    print()


if __name__ == "__main__":
    main()
