**Subject: Data Request for Portfolio Allocation & Risk Modeling**

Hi [Strategy Owner's Name],

I hope this message finds you well.

I am constructing a multi-strategy portfolio and am very impressed with the performance of your strategy. I'd love to integrate it into my portfolio using proper risk management and position sizing.

**I can work with whatever data you have available** - even just daily returns is helpful!

---

## **What I Need (In Order of Priority)**

### **MINIMUM: Daily Returns (%)**
A CSV with your daily returns - I'll estimate the rest.

```csv
Date,Daily Returns (%)
2024-01-15,0.5%
2024-01-16,-0.3%
2024-01-17,0.8%
```

### **RECOMMENDED: Returns + Position Data** ⭐
This gives me accurate risk metrics without needing assumptions.

```csv
Date,Daily Returns (%),Maximum Daily Notional Value,Maximum Daily Margin Utilization ($)
2024-01-15,0.5%,5500000,50000
2024-01-16,-0.3%,6200000,55000
2024-01-17,0.8%,4800000,45000
```

**What these mean:**
- **Daily Returns (%)**: Your daily P&L as % of account equity
- **Maximum Daily Notional Value**: Total market value of all positions that day
- **Maximum Daily Margin Utilization ($)**: Total margin requirement that day

### **BONUS: Position Sizing Rules** (Provide Once)
This helps me scale your strategy correctly in my portfolio:

- **Minimum Position Size**: Smallest tradeable unit (e.g., "1 contract", "0.01 lots", "100 shares")
- **Position Increment**: How positions scale (e.g., "1 contract", "0.1 lots", "100 shares")

**Examples:**
- **Options**: Min: 1 contract, Increment: 1 contract
- **Forex**: Min: 0.01 lot, Increment: 0.1 lot
- **Futures**: Min: 1 contract, Increment: 1 contract
- **Stocks**: Min: 1 share, Increment: 1 share (or 100 if round lots)

**SPX Options Example:**
- Notional: 10 contracts × 5500 strike × $100 = $5,500,000
- Margin: $50,000 (broker requirement for that position)

**Commodities Example:**
- Notional: 5 CL contracts × 1,000 barrels × $85 = $425,000
- Margin: $41,000 (CME initial margin for 5 contracts)

**Forex Example:**
- Notional: 8.5 lots × $100,000 = $850,000
- Margin: $17,000 (at 50:1 leverage)

---

## **Why These 3 Columns?**

With Date, Returns%, Notional, and Margin, I can calculate everything else automatically:
- ✅ Daily P&L ($) = calculated from returns and equity curve
- ✅ Return on Notional (%) = calculated from P&L ÷ Notional

**Key point:** I cannot accurately estimate margin from returns alone, because daily returns don't tell me how many positions you had open. That's why the Margin column is particularly valuable!

---

I appreciate any data you can share - whether it's just the basic returns or the full historical dataset!

Best regards,

[Your Name]