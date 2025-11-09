"""
Position Sizing Module - Pure Functions
Contains position sizing calculation logic without side effects.
Can be imported and tested without triggering service initialization.
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def calculate_position_size_legacy(
    signal: Dict[str, Any],
    account_state: Dict[str, Any],
    strategy_allocation_pct: float,
    mvp_config: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Calculate position size based on portfolio allocation and risk limits.

    LEGACY FUNCTION - Kept for backwards compatibility.
    New code should use process_signal_with_constructor() instead.

    Args:
        signal: Signal dictionary with instrument, price, quantity, etc.
        account_state: Account state with equity, margin_used, margin_available
        strategy_allocation_pct: Percentage of portfolio allocated to this strategy
        mvp_config: Configuration dict with max_margin_utilization_pct, default_position_size_pct

    Returns:
        Dict with:
            - approved: bool
            - reason: str
            - original_quantity: float
            - final_quantity: float
            - margin_required: float
            - allocated_capital: float (if approved)
            - margin_utilization_before_pct: float (if approved)
            - margin_utilization_after_pct: float (if approved)
    """
    strategy_id = signal.get('strategy_id')
    account_equity = account_state.get('equity', 0)
    margin_used = account_state.get('margin_used', 0)
    margin_available = account_state.get('margin_available', 0)

    logger.info(f"\n{'='*70}")
    logger.info(f"📊 POSITION SIZING CALCULATION for {signal.get('instrument')}")
    logger.info(f"{'='*70}")
    logger.info(f"Strategy: {strategy_id}")
    logger.info(f"Account State:")
    logger.info(f"  • Equity: ${account_equity:,.2f}")
    logger.info(f"  • Margin Used: ${margin_used:,.2f}")
    logger.info(f"  • Margin Available: ${margin_available:,.2f}")

    # Calculate current margin utilization
    current_margin_util_pct = (margin_used / account_equity * 100) if account_equity > 0 else 100
    logger.info(f"  • Current Margin Utilization: {current_margin_util_pct:.2f}%")

    # Check hard margin limit
    max_margin_pct = mvp_config.get('max_margin_utilization_pct', 40)
    if current_margin_util_pct >= max_margin_pct:
        logger.warning(f"❌ Margin utilization {current_margin_util_pct:.1f}% exceeds limit {max_margin_pct}%")
        logger.info(f"{'='*70}\n")
        return {
            "approved": False,
            "reason": "MARGIN_LIMIT_EXCEEDED",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "margin_required": 0
        }

    # Use provided allocation or fallback
    if strategy_allocation_pct == 0:
        logger.warning(f"⚠️  No allocation found for strategy {strategy_id}")
        logger.warning(f"   Using fallback: {mvp_config.get('default_position_size_pct', 5)}% default allocation")
        strategy_allocation_pct = mvp_config.get('default_position_size_pct', 5)

    # Calculate position size based on strategy allocation
    allocated_capital = account_equity * (strategy_allocation_pct / 100)
    logger.info(f"\nPortfolio Allocation:")
    logger.info(f"  • Strategy Allocation: {strategy_allocation_pct:.2f}% of portfolio")
    logger.info(f"  • Allocated Capital: ${account_equity:,.2f} × {strategy_allocation_pct:.2f}% = ${allocated_capital:,.2f}")

    # Calculate quantity based on price and allocated capital
    signal_price = signal.get('price', 0)
    if signal_price <= 0:
        logger.error(f"❌ Invalid price {signal_price} for signal {signal['signal_id']}")
        logger.info(f"{'='*70}\n")
        return {
            "approved": False,
            "reason": "INVALID_PRICE",
            "original_quantity": signal.get('quantity', 0),
            "final_quantity": 0,
            "margin_required": 0
        }

    # Simplified quantity calculation
    final_quantity = allocated_capital / signal_price
    logger.info(f"\nQuantity Calculation:")
    logger.info(f"  • Price per share: ${signal_price:.2f}")
    logger.info(f"  • Quantity: ${allocated_capital:,.2f} / ${signal_price:.2f} = {final_quantity:.2f} shares")

    # Estimate margin required (simplified: assume 50% margin requirement for stocks)
    estimated_margin = allocated_capital * 0.5
    logger.info(f"\nMargin Requirements:")
    logger.info(f"  • Margin Requirement: 50% (stocks)")
    logger.info(f"  • Margin Required: ${allocated_capital:,.2f} × 0.5 = ${estimated_margin:,.2f}")

    # Check if we have enough available margin
    margin_after = margin_used + estimated_margin
    margin_util_after = (margin_after / account_equity * 100) if account_equity > 0 else 100
    logger.info(f"\nMargin Check:")
    logger.info(f"  • Current Margin Used: ${margin_used:,.2f}")
    logger.info(f"  • New Position Margin: ${estimated_margin:,.2f}")
    logger.info(f"  • Total Margin After: ${margin_after:,.2f}")
    logger.info(f"  • Margin Utilization After: {margin_util_after:.2f}%")
    logger.info(f"  • Max Allowed: {max_margin_pct}%")

    if margin_util_after > max_margin_pct:
        logger.info(f"\n⚠️  Position too large, reducing to fit margin limit...")
        # Reduce position size to fit within margin limit
        max_additional_margin = (max_margin_pct / 100 * account_equity) - margin_used
        if max_additional_margin <= 0:
            logger.warning(f"❌ Insufficient margin available")
            logger.info(f"{'='*70}\n")
            return {
                "approved": False,
                "reason": "INSUFFICIENT_MARGIN",
                "original_quantity": signal.get('quantity', 0),
                "final_quantity": 0,
                "margin_required": 0
            }

        # Reduce quantity proportionally
        reduction_factor = max_additional_margin / estimated_margin
        logger.info(f"  • Reduction Factor: {reduction_factor:.2%}")
        final_quantity = final_quantity * reduction_factor
        estimated_margin = max_additional_margin
        logger.info(f"  • Reduced Quantity: {final_quantity:.2f} shares")
        logger.info(f"  • Reduced Margin: ${estimated_margin:,.2f}")

    logger.info(f"\n✅ DECISION: APPROVED")
    logger.info(f"  • Final Quantity: {final_quantity:.2f} shares")
    logger.info(f"  • Capital Allocated: ${allocated_capital:,.2f}")
    logger.info(f"  • Margin Required: ${estimated_margin:,.2f}")
    logger.info(f"  • Final Margin Utilization: {margin_util_after:.2f}%")
    logger.info(f"{'='*70}\n")

    return {
        "approved": True,
        "reason": "APPROVED",
        "original_quantity": signal.get('quantity', 0),
        "final_quantity": final_quantity,
        "margin_required": estimated_margin,
        "allocated_capital": allocated_capital,
        "margin_utilization_before_pct": current_margin_util_pct,
        "margin_utilization_after_pct": margin_util_after
    }


def estimate_ibkr_margin(
    signal: Dict[str, Any],
    quantity: float,
    price: float
) -> Dict[str, Any]:
    """
    Estimate IBKR margin requirements for a given position.

    Simplified calculation for MVP. Full implementation would query IBKR API.

    Args:
        signal: Signal dictionary with instrument, instrument_type, etc.
        quantity: Number of shares/contracts
        price: Price per unit

    Returns:
        Dict with:
            - margin_required: float (estimated margin in dollars)
            - margin_requirement_pct: float (percentage)
            - notional_value: float (total position value)
    """
    instrument_type = signal.get('instrument_type', 'STOCK')
    notional_value = quantity * price

    # Simplified margin requirements by instrument type
    margin_requirements = {
        'STOCK': 0.50,  # 50% margin for stocks (Reg T)
        'FUTURE': 1.00,  # 100% for futures (simplified)
        'OPTION': 1.00,  # 100% for options (simplified, actual is complex)
        'FOREX': 0.02,  # 2% for forex (50:1 leverage)
    }

    margin_req_pct = margin_requirements.get(instrument_type, 0.50)
    margin_required = notional_value * margin_req_pct

    return {
        'margin_required': margin_required,
        'margin_requirement_pct': margin_req_pct,
        'notional_value': notional_value
    }


def check_margin_limits(
    current_margin: float,
    new_position_margin: float,
    account_equity: float,
    max_margin_pct: float
) -> Dict[str, Any]:
    """
    Check if adding a new position would exceed margin limits.

    Args:
        current_margin: Current margin used
        new_position_margin: Margin required for new position
        account_equity: Total account equity
        max_margin_pct: Maximum allowed margin utilization percentage

    Returns:
        Dict with:
            - approved: bool
            - current_util_pct: float
            - after_util_pct: float
            - max_util_pct: float
            - reason: str (if not approved)
    """
    current_util_pct = (current_margin / account_equity * 100) if account_equity > 0 else 100
    margin_after = current_margin + new_position_margin
    after_util_pct = (margin_after / account_equity * 100) if account_equity > 0 else 100

    approved = after_util_pct <= max_margin_pct
    reason = "" if approved else f"Margin utilization after trade ({after_util_pct:.1f}%) would exceed limit ({max_margin_pct}%)"

    return {
        'approved': approved,
        'current_util_pct': current_util_pct,
        'after_util_pct': after_util_pct,
        'max_util_pct': max_margin_pct,
        'reason': reason
    }


def calculate_slippage(signal: Dict[str, Any]) -> float:
    """
    Calculate expected slippage as percentage based on order type and market conditions.

    Args:
        signal: Signal dictionary with order_type, instrument_type, etc.

    Returns:
        float: Expected slippage percentage (e.g., 0.001 = 0.1%)
    """
    order_type = signal.get('order_type', 'MARKET')
    instrument_type = signal.get('instrument_type', 'STOCK')

    # Simplified slippage estimation
    base_slippage = {
        'MARKET': 0.001,  # 0.1% for market orders
        'LIMIT': 0.0,     # No slippage for limit orders (might not fill)
        'STOP': 0.002,    # 0.2% for stop orders
    }

    # Adjust for instrument type (futures/options tend to have tighter spreads)
    instrument_multiplier = {
        'STOCK': 1.0,
        'FUTURE': 0.5,
        'OPTION': 1.5,
        'FOREX': 0.3,
    }

    slippage = base_slippage.get(order_type, 0.001) * instrument_multiplier.get(instrument_type, 1.0)
    return slippage


def check_slippage_rule(signal: Dict[str, Any], expected_alpha: float, slippage_threshold: float = 0.30) -> bool:
    """
    Check if expected slippage is acceptable relative to expected alpha.

    Args:
        signal: Signal dictionary
        expected_alpha: Expected return/alpha from the trade (e.g., 0.02 = 2%)
        slippage_threshold: Maximum acceptable slippage as fraction of alpha

    Returns:
        bool: True if slippage is acceptable, False otherwise
    """
    slippage = calculate_slippage(signal)

    if expected_alpha <= 0:
        logger.warning(f"Signal has non-positive expected alpha: {expected_alpha}")
        return False

    slippage_pct_of_alpha = slippage / expected_alpha

    if slippage_pct_of_alpha > slippage_threshold:
        logger.warning(
            f"Slippage ({slippage:.4f}) is {slippage_pct_of_alpha:.1%} of expected alpha ({expected_alpha:.4f}), "
            f"exceeds threshold ({slippage_threshold:.1%})"
        )
        return False

    return True


def validate_order_size(quantity: float, min_size: float = 1.0, max_size: float = 1_000_000) -> Dict[str, Any]:
    """
    Validate order quantity is within acceptable bounds.

    Args:
        quantity: Order quantity
        min_size: Minimum allowed quantity
        max_size: Maximum allowed quantity

    Returns:
        Dict with:
            - valid: bool
            - quantity: float (rounded if needed)
            - reason: str (if not valid)
    """
    # Round to whole shares (IBKR doesn't support fractional shares for most stocks)
    rounded_quantity = round(quantity)

    if rounded_quantity < min_size:
        return {
            'valid': False,
            'quantity': rounded_quantity,
            'reason': f"Quantity {rounded_quantity} below minimum {min_size}"
        }

    if rounded_quantity > max_size:
        return {
            'valid': False,
            'quantity': rounded_quantity,
            'reason': f"Quantity {rounded_quantity} exceeds maximum {max_size}"
        }

    return {
        'valid': True,
        'quantity': rounded_quantity,
        'reason': ""
    }
