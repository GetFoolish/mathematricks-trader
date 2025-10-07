import pandas as pd
import sys
import os

def analyze_margin_utilization(filepath):
    """
    Loads a CSV file and calculates the min, max, and median
    for all columns ending in '_Margin_Util_%'.

    Args:
        filepath (str): The path to the CSV file.
    """
    # --- 1. Input Validation ---
    if not os.path.exists(filepath):
        print(f"Error: The file '{filepath}' was not found.")
        return

    print(f"Loading data from '{filepath}'...")

    try:
        # --- 2. Load the CSV into a pandas DataFrame ---
        df = pd.read_csv(filepath)
    except Exception as e:
        print(f"Error: Failed to read the CSV file. Reason: {e}")
        return

    # --- 3. Identify the Margin Utilization Columns ---
    # Find all column names that contain the string '_Margin_Util_%'
    margin_util_cols = [col for col in df.columns if '_Margin_Util_%' in col]

    if not margin_util_cols:
        print("Error: No columns with '_Margin_Util_%' found in the CSV file.")
        return

    print("\n--- Margin Utilization Analysis ---")

    # --- 4. Loop Through Each Column and Calculate Stats ---
    for col_name in margin_util_cols:
        # Extract the account name from the column title (e.g., 'IBKR Main')
        account_name = col_name.replace('_Margin_Util_%', '')

        # Select the column data
        margin_data = df[col_name]

        # Calculate min, max, and median
        min_val = margin_data.min()
        max_val = margin_data.max()
        median_val = margin_data.median()

        # --- 5. Print the Results ---
        print(f"\nAccount: {account_name}")
        print(f"  - Minimum Margin Util %: {min_val:.2f}%")
        print(f"  - Maximum Margin Util %: {max_val:.2f}%")
        print(f"  - Median  Margin Util %: {median_val:.2f}%")

    print("\nAnalysis complete.")

# ==============================================================================
# --- Main Execution Block ---
# ==============================================================================
if __name__ == "__main__":
    # Check if a filename was provided as a command-line argument
    if len(sys.argv) < 2:
        print("Usage: python analyze_margin.py <filename.csv>")
        sys.exit(1) # Exit with an error code

    # The first argument (index 0) is the script name, the second (index 1) is the filename
    csv_filename = sys.argv[1]

    # Run the analysis function
    analyze_margin_utilization(csv_filename)