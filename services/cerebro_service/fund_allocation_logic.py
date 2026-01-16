"""
Fund Allocation Logic (v5)
Helper functions for multi-fund capital allocation and account distribution
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def get_active_allocations_for_strategy(
    strategy_id: str,
    funds_collection,
    portfolio_tests_collection=None  # DEPRECATED: No longer needed, kept for backwards compatibility
) -> List[Dict]:
    """
    Get all ACTIVE fund allocations that include this strategy.
    Reads from funds.approved_allocation (v5.2 - allocation snapshot).

    Args:
        strategy_id: Strategy ID to search for
        funds_collection: MongoDB funds collection
        portfolio_tests_collection: DEPRECATED - No longer used (allocations stored in fund document)

    Returns:
        List of allocation documents with fund_id
    """
    try:
        # Get all active funds with approved allocations
        active_funds = list(funds_collection.find({
            "approved_allocation.allocations": {"$exists": True},
            "status": "ACTIVE"
        }))

        allocations = []
        for fund in active_funds:
            approved_allocation = fund.get('approved_allocation', {})
            allocations_dict = approved_allocation.get('allocations', {})
            portfolio_test_id = approved_allocation.get('portfolio_test_id', 'unknown')

            # Only include if strategy is allocated in this fund
            if strategy_id in allocations_dict:
                allocations.append({
                    'fund_id': fund['fund_id'],
                    'allocation_name': f"Test {portfolio_test_id}",
                    'allocations': allocations_dict,
                    'portfolio_test_id': portfolio_test_id
                })

        logger.info(f"Found {len(allocations)} ACTIVE allocations for strategy {strategy_id}")
        return allocations

    except Exception as e:
        logger.error(f"Error fetching active allocations: {str(e)}")
        return []


def get_strategy_allocation_for_fund(
    fund_id: str,
    strategy_id: str,
    portfolio_allocations_collection,  # DEPRECATED: Not used anymore
    trading_orders_collection,
    funds_collection,
    trading_accounts_collection,
    portfolio_tests_collection=None  # NEW: Required for reading allocations
) -> Dict[str, float]:
    """
    Calculate capital allocation for a strategy within a fund.
    
    Args:
        fund_id: Fund ID
        strategy_id: Strategy ID
        portfolio_allocations_collection: MongoDB collection
        trading_orders_collection: MongoDB collection
        funds_collection: MongoDB collection
        trading_accounts_collection: MongoDB collection
        
    Returns:
        {
            allocated_capital: float,   # How much $ this strategy has from this fund
            used_capital: float,         # How much $ is currently deployed
            available_capital: float     # How much $ is available for new signals
        }
    """
    try:
        # Get fund total equity from MongoDB (updated by account-data-service)
        fund_doc = funds_collection.find_one({"fund_id": fund_id})
        if not fund_doc:
            logger.warning(f"Fund {fund_id} not found in database")
            return {
                "allocated_capital": 0.0,
                "used_capital": 0.0,
                "available_capital": 0.0
            }
        
        fund_equity = fund_doc.get('total_equity', 0.0)

        if fund_equity <= 0:
            logger.warning(f"Fund {fund_id} has zero or negative equity: ${fund_equity:,.2f}")
            return {
                "allocated_capital": 0.0,
                "used_capital": 0.0,
                "available_capital": 0.0
            }

        # Get active allocation for this fund from approved_allocation snapshot (v5.2)
        approved_allocation = fund_doc.get('approved_allocation')

        if not approved_allocation:
            logger.warning(f"No approved allocation found for fund {fund_id}")
            return {
                "allocated_capital": 0.0,
                "used_capital": 0.0,
                "available_capital": 0.0
            }

        # Get strategy allocation percentage from snapshot
        allocations = approved_allocation.get('allocations', {})
        strategy_pct = allocations.get(strategy_id, 0.0)
        
        if strategy_pct <= 0:
            logger.warning(f"Strategy {strategy_id} has 0% allocation in fund {fund_id}")
            return {
                "allocated_capital": 0.0,
                "used_capital": 0.0,
                "available_capital": 0.0
            }
        
        # Calculate allocated capital
        allocated_capital = fund_equity * (strategy_pct / 100.0)
        
        # Calculate used capital (sum notional_value of FILLED and SUBMITTED orders)
        used_capital_docs = trading_orders_collection.aggregate([
            {
                "$match": {
                    "fund_id": fund_id,
                    "strategy_id": strategy_id,
                    "status": {"$in": ["FILLED", "SUBMITTED"]}
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total": {"$sum": "$notional_value"}
                }
            }
        ])
        
        used_capital = 0.0
        for doc in used_capital_docs:
            used_capital = doc.get('total', 0.0)
        
        # Calculate available capital
        available_capital = max(0.0, allocated_capital - used_capital)
        
        logger.info(
            f"Fund {fund_id} | Strategy {strategy_id}: "
            f"Allocated: ${allocated_capital:,.2f} ({strategy_pct}%) | "
            f"Used: ${used_capital:,.2f} | "
            f"Available: ${available_capital:,.2f}"
        )
        
        return {
            "allocated_capital": allocated_capital,
            "used_capital": used_capital,
            "available_capital": available_capital
        }
    
    except Exception as e:
        logger.error(f"Error calculating strategy allocation: {str(e)}")
        return {
            "allocated_capital": 0.0,
            "used_capital": 0.0,
            "available_capital": 0.0
        }


def get_available_accounts_for_strategy(
    strategy_id: str,
    fund_id: str,
    asset_class: str,
    strategies_collection,
    trading_accounts_collection
) -> List[Dict[str, Any]]:
    """
    Get accounts that:
    1. Strategy is allowed to use (in strategy.accounts)
    2. Belong to this fund (account.fund_id = fund_id)
    3. Support the asset class (asset_class in account.asset_classes)
    
    Args:
        strategy_id: Strategy ID
        fund_id: Fund ID
        asset_class: Asset class (equity, futures, crypto, forex)
        strategies_collection: MongoDB collection
        trading_accounts_collection: MongoDB collection
        
    Returns:
        List of accounts: [{account_id, available_margin, equity}, ...]
        Sorted by available_margin (descending)
    """
    try:
        # Get strategy
        strategy = strategies_collection.find_one({"strategy_id": strategy_id})
        if not strategy:
            logger.error(f"Strategy {strategy_id} not found")
            return []
        
        # Get allowed accounts for this strategy
        allowed_accounts = strategy.get('accounts', [])
        if not allowed_accounts:
            logger.warning(f"Strategy {strategy_id} has no allowed accounts")
            return []
        
        # Get accounts that match all criteria
        query = {
            "account_id": {"$in": allowed_accounts},
            "fund_id": fund_id,
            "status": "ACTIVE",
            f"asset_classes.{asset_class}": {"$exists": True, "$ne": []}
        }
        
        accounts = list(trading_accounts_collection.find(query))
        
        if not accounts:
            logger.warning(
                f"No accounts found for strategy {strategy_id} in fund {fund_id} "
                f"with asset class {asset_class}"
            )
            return []
        
        # Build result with relevant fields
        # Note: balances are nested under 'balances' subdocument
        result = []
        for acc in accounts:
            balances = acc.get('balances', {})
            result.append({
                "account_id": acc['account_id'],
                "available_margin": balances.get('margin_available', 0.0),
                "equity": balances.get('equity', 0.0),
                "broker": acc.get('broker', 'Unknown')
            })
        
        # Sort by available margin (descending)
        result.sort(key=lambda x: x['available_margin'], reverse=True)
        
        logger.info(
            f"Found {len(result)} available accounts for {strategy_id} in {fund_id}: "
            f"{[a['account_id'] for a in result]}"
        )
        
        return result
    
    except Exception as e:
        logger.error(f"Error getting available accounts: {str(e)}")
        return []


def distribute_capital_across_accounts(
    target_capital: float,
    accounts: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Distribute target_capital across accounts proportionally by available margin.
    
    Args:
        target_capital: Total capital to distribute
        accounts: List of account dicts with 'account_id' and 'available_margin'
        
    Returns:
        List of {account_id, allocated_capital} dicts
        
    Example:
        Input:
          target_capital = 15000
          accounts = [
            {account_id: "IBKR_Main", available_margin: 15000},
            {account_id: "IBKR_Futures", available_margin: 8000}
          ]
        
        Output:
          [
            {account_id: "IBKR_Main", allocated_capital: 9782.61},
            {account_id: "IBKR_Futures", allocated_capital: 5217.39}
          ]
    """
    try:
        if not accounts:
            logger.warning("No accounts provided for capital distribution")
            return []
        
        if target_capital <= 0:
            logger.warning(f"Invalid target capital: ${target_capital:,.2f}")
            return []
        
        # Calculate total available margin
        total_margin = sum(acc.get('available_margin', 0.0) for acc in accounts)
        
        if total_margin <= 0:
            logger.warning("Total available margin is zero across all accounts")
            return []
        
        # Distribute capital proportionally
        result = []
        remaining_capital = target_capital
        
        for i, acc in enumerate(accounts):
            available_margin = acc.get('available_margin', 0.0)
            
            # Last account gets remaining capital to avoid rounding errors
            if i == len(accounts) - 1:
                allocated = min(remaining_capital, available_margin)
            else:
                # Proportional allocation
                allocated = (available_margin / total_margin) * target_capital
                
                # Cap at available margin
                allocated = min(allocated, available_margin)
            
            if allocated > 0:
                result.append({
                    "account_id": acc['account_id'],
                    "allocated_capital": allocated,
                    "broker": acc.get('broker', 'Unknown')
                })
                
                remaining_capital -= allocated
        
        total_allocated = sum(r['allocated_capital'] for r in result)
        
        logger.info(
            f"Distributed ${target_capital:,.2f} across {len(result)} accounts "
            f"(Total: ${total_allocated:,.2f})"
        )
        for alloc in result:
            logger.info(f"  • {alloc['account_id']}: ${alloc['allocated_capital']:,.2f}")
        
        return result
    
    except Exception as e:
        logger.error(f"Error distributing capital: {str(e)}")
        return []
