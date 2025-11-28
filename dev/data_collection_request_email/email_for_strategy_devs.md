**Subject: Data Request for Portfolio Allocation & Risk Modeling**

Hi [Strategy Owner's Name],

I hope this message finds you well. We're obviously very excited to have you on board. 
As part of our due-dilligence and risk management, there's some additional data i'd require you to share with me.

A sample Excel file of what we're looking for is attached with this email. It's fairly straight forward.


**What to do if you don't have data for one of the columns?** - Every column adds value, but if there's something you don't have, or can't get, please let us know 'why', and we'll make arrangements to work with synthetic data as a work around. It's not ideal to work with synthetic data, but being flexible keeps the conversation moving in the right direction.

---


**CSV Format:**
```csv
Date,Daily_Return_Pct,Account_Equity,Daily_PnL,Max_Margin_Used,Max_Notional_Value
2024-01-15,0.5,1050000,5000,50000,5500000
2024-01-16,-0.3,1046850,-3150,55000,6200000
2024-01-17,0.8,1055226,8376,45000,4800000
```

**What these mean:**
- **Daily_Return_Pct**: Your daily P&L as % of account equity
- **Account_Equity**: Account balance at end of day
- **Daily_PnL**: Dollar P&L for that day
- **Max_Margin_Used**: Maximum margin requirement that day (broker requirement)
- **Max_Notional_Value**: Total market value of all positions that day


**An Explaination of Notional and Margin (Just in case)**
Notional: 10 contracts × 5500 strike × $100 multiplier = $5,500,000
Margin: $50,000 (broker requirement for that specific position)
```

### **Commodities Futures (Crude Oil):**
```
Notional: 5 CL contracts × 1,000 barrels × $85/barrel = $425,000
Margin: $41,000 (CME initial margin requirement for 5 contracts)
```

### **Forex (EUR/USD):**
```
Notional: 8.5 lots × $100,000 per lot = $850,000
Margin: $17,000 (at 50:1 leverage)
```

### **Equities (SPY shares):**
```
Notional: 1,000 shares × $450 = $450,000
Margin: $225,000 (at 2:1 margin, or $450,000 if cash account)
```

---


I appreciate any data you can share - even just Date + Returns gives me enough to start modeling your strategy in the portfolio!

Best regards,

[Your Name]
