"""
Lag Calculator Utility

Calculates processing lag for signal processing pipeline.
Tracks time spent in each service and computes total lag and discrepancies.
"""

from datetime import datetime
from typing import Dict, Any, Optional


def calculate_processing_lag(processing_timestamps: Dict[str, Any]) -> Dict[str, Any]:
    """
    Calculate processing lag from timestamps.
    
    Args:
        processing_timestamps: Dictionary with timestamps from each service:
            - signal_received: When signal was first received
            - signal_ingestion_processed: When signal_ingestion created the leg
            - cerebro_processed: When cerebro made the decision
            - execution_started: When execution service started processing
            - execution_completed: When execution service completed
    
    Returns:
        Dictionary with lag information:
        {
            "service_lags": {
                "signal_ingestion": <lag_ms>,
                "cerebro": <lag_ms>,
                "execution": <lag_ms>
            },
            "total_lag_ms": <total_lag_ms>,  # From signal_received to execution_completed
            "sum_of_service_lags_ms": <sum_ms>,  # Sum of individual service lags
            "unaccounted_lag_ms": <difference_ms>,  # Difference (network/queueing time)
            "stages": [
                {"service": "signal_ingestion", "lag_ms": <lag>, "timestamp": <iso>},
                {"service": "cerebro", "lag_ms": <lag>, "timestamp": <iso>},
                {"service": "execution", "lag_ms": <lag>, "timestamp": <iso>}
            ],
            "summary": "signal_ingestion (0.2ms) → cerebro (5.3ms) → execution (12.1ms) | Total: 20.5ms (unaccounted: 2.9ms)"
        }
    """
    if not processing_timestamps:
        return None
    
    # Extract timestamps (handle both datetime objects and strings)
    def to_datetime(ts):
        if ts is None:
            return None
        if isinstance(ts, datetime):
            return ts
        if isinstance(ts, str):
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        return None
    
    signal_received = to_datetime(processing_timestamps.get('signal_received'))
    ingestion_processed = to_datetime(processing_timestamps.get('signal_ingestion_processed'))
    cerebro_processed = to_datetime(processing_timestamps.get('cerebro_processed'))
    execution_started = to_datetime(processing_timestamps.get('execution_started'))
    execution_completed = to_datetime(processing_timestamps.get('execution_completed'))
    
    # If we don't have the minimum required timestamps, return None
    if not signal_received or not ingestion_processed:
        return None
    
    # Calculate individual service lags
    service_lags = {}
    stages = []
    
    # Signal Ingestion lag (from received to ingestion processed)
    ingestion_lag_ms = (ingestion_processed - signal_received).total_seconds() * 1000
    service_lags['signal_ingestion'] = round(ingestion_lag_ms, 2)
    stages.append({
        "service": "signal_ingestion",
        "lag_ms": round(ingestion_lag_ms, 2),
        "timestamp": ingestion_processed.isoformat()
    })
    
    # Cerebro lag (from ingestion processed to cerebro processed)
    cerebro_lag_ms = 0
    if cerebro_processed and ingestion_processed:
        cerebro_lag_ms = (cerebro_processed - ingestion_processed).total_seconds() * 1000
        service_lags['cerebro'] = round(cerebro_lag_ms, 2)
        stages.append({
            "service": "cerebro",
            "lag_ms": round(cerebro_lag_ms, 2),
            "timestamp": cerebro_processed.isoformat()
        })
    
    # Execution lag (from cerebro processed to execution completed)
    execution_lag_ms = 0
    if execution_completed and cerebro_processed:
        execution_lag_ms = (execution_completed - cerebro_processed).total_seconds() * 1000
        service_lags['execution'] = round(execution_lag_ms, 2)
        stages.append({
            "service": "execution",
            "lag_ms": round(execution_lag_ms, 2),
            "timestamp": execution_completed.isoformat()
        })
    elif execution_completed and execution_started:
        # Fallback: if no cerebro timestamp, use execution started
        execution_lag_ms = (execution_completed - execution_started).total_seconds() * 1000
        service_lags['execution'] = round(execution_lag_ms, 2)
        stages.append({
            "service": "execution",
            "lag_ms": round(execution_lag_ms, 2),
            "timestamp": execution_completed.isoformat()
        })
    
    # Calculate total lag (end-to-end)
    end_timestamp = execution_completed or cerebro_processed or ingestion_processed
    total_lag_ms = (end_timestamp - signal_received).total_seconds() * 1000
    
    # Calculate sum of service lags
    sum_of_service_lags_ms = sum(service_lags.values())
    
    # Calculate unaccounted lag (network, queueing, etc.)
    unaccounted_lag_ms = total_lag_ms - sum_of_service_lags_ms
    
    # Build summary string
    lag_parts = []
    for service, lag_ms in service_lags.items():
        lag_parts.append(f"{service} ({lag_ms:.1f}ms)")
    
    summary = " → ".join(lag_parts)
    summary += f" | Total: {total_lag_ms:.1f}ms"
    if abs(unaccounted_lag_ms) > 0.1:
        summary += f" (unaccounted: {unaccounted_lag_ms:.1f}ms)"
    
    return {
        "service_lags": service_lags,
        "total_lag_ms": round(total_lag_ms, 2),
        "sum_of_service_lags_ms": round(sum_of_service_lags_ms, 2),
        "unaccounted_lag_ms": round(unaccounted_lag_ms, 2),
        "stages": stages,
        "summary": summary
    }


def format_lag_summary(lag_data: Dict[str, Any]) -> str:
    """
    Format lag data into a human-readable summary string.
    
    Args:
        lag_data: Output from calculate_processing_lag()
    
    Returns:
        Formatted string like: "signal_ingestion (0.2ms) → cerebro (5.3ms) → execution (12.1ms) | Total: 20.5ms (unaccounted: 2.9ms)"
    """
    if not lag_data:
        return "No lag data available"
    
    return lag_data.get('summary', 'Unknown')
