import json
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import os

# Load the JSON file
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, '1379840802-summary.json')

with open(json_path, 'r') as f:
    data = json.load(f)

# Extract equity data
equity_values = data['charts']['Strategy Equity']['series']['Equity']['values']

# Parse timestamps and equity values (using close price - index 4)
timestamps = [datetime.fromtimestamp(row[0]) for row in equity_values]
equity = [row[4] for row in equity_values]  # Close price

# Create the plot
plt.figure(figsize=(14, 7))
plt.plot(timestamps, equity, linewidth=1.5, color='#2E86AB')
plt.fill_between(timestamps, equity, alpha=0.3, color='#2E86AB')

# Formatting
plt.title('Strategy Equity Curve', fontsize=16, fontweight='bold', pad=20)
plt.xlabel('Date', fontsize=12)
plt.ylabel('Equity ($)', fontsize=12)
plt.grid(True, alpha=0.3, linestyle='--')

# Format y-axis to show currency
ax = plt.gca()
ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'${x:,.0f}'))

# Rotate x-axis labels for better readability
plt.xticks(rotation=45, ha='right')

# Add statistics box
stats_text = f"""
Start Equity: ${equity[0]:,.0f}
End Equity: ${equity[-1]:,.0f}
Total Return: {((equity[-1] - equity[0]) / equity[0] * 100):.2f}%
Sharpe Ratio: 2.057
Max Drawdown: 14.0%
Win Rate: 79%
"""

plt.text(0.02, 0.98, stats_text.strip(), transform=ax.transAxes,
         fontsize=10, verticalalignment='top',
         bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

plt.tight_layout()
output_path = os.path.join(script_dir, 'strategy_equity_curve.png')
plt.savefig(output_path, dpi=300, bbox_inches='tight')
plt.show()

print(f"Chart saved as '{output_path}'")
print(f"Start: ${equity[0]:,.2f} ({timestamps[0].strftime('%Y-%m-%d')})")
print(f"End: ${equity[-1]:,.2f} ({timestamps[-1].strftime('%Y-%m-%d')})")
print(f"Total Return: {((equity[-1] - equity[0]) / equity[0] * 100):.2f}%")
