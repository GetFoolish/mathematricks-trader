# DEVELOPMENT PLAN

The system has a major flaw. It doesn't take into account

1. Fund Architecture
    - There is a 'Funds' db, which has FundName: Mathematricks-1
    - Then there is an "Accounts" db: which has accounts in it. Each account is associated to one Parent Fund: FundName. and account balance. and open positions.
    - Then there are strategies db: A strategy will have which accounts it's allowed to trade

2. Account Data Services:
    - Updates account balances and open positions to each account in accounts db.
    - Logs details of account balances and open positions, by fund.

