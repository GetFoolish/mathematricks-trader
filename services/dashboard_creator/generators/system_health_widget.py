"""
System Health Widget Generator

Checks health status of all system services and returns overall health metrics.
"""
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Any
import requests
from pymongo import MongoClient

logger = logging.getLogger(__name__)

# Service URLs (Docker network names)
# Only include services with HTTP endpoints
SERVICES = [
    {"name": "MongoDB", "url": "mongodb://mongodb:27017", "type": "database"},
    {"name": "Account Data Service", "url": "http://account-data-service:8082/api/v1/accounts", "type": "http"},
    {"name": "Portfolio Builder", "url": "http://portfolio-builder:8003/health", "type": "http"},
    {"name": "Dashboard Creator", "url": "http://dashboard-creator:8004/health", "type": "http"},
    {"name": "Frontend API", "url": "http://frontend:8000/health", "type": "http"},
]


def check_service_health(service: Dict[str, str], mongo_client: MongoClient = None) -> Dict[str, Any]:
    """
    Check health of a single service.
    
    Returns:
        {
            "name": str,
            "status": "healthy" | "degraded" | "unhealthy",
            "message": str (optional),
            "response_time": float (ms),
            "uptime": int (seconds, optional)
        }
    """
    start_time = time.time()
    
    try:
        if service["type"] == "http":
            response = requests.get(service["url"], timeout=2)
            response_time = (time.time() - start_time) * 1000
            
            # Accept 200, 404, 405 as healthy (service is responding)
            # 404/405 just means the endpoint doesn't exist, but service is alive
            if response.status_code in [200, 404, 405]:
                return {
                    "name": service["name"],
                    "status": "healthy",
                    "response_time": response_time
                }
            elif response.status_code in [500, 502, 503, 504]:
                return {
                    "name": service["name"],
                    "status": "unhealthy",
                    "message": f"HTTP {response.status_code}",
                    "response_time": response_time
                }
            else:
                return {
                    "name": service["name"],
                    "status": "degraded",
                    "message": f"HTTP {response.status_code}",
                    "response_time": response_time
                }
                
        elif service["type"] == "database":
            # MongoDB health check using mongo client
            if mongo_client is None:
                return {
                    "name": service["name"],
                    "status": "unhealthy",
                    "message": "No mongo client provided"
                }
            
            # Test MongoDB connection with a simple ping
            mongo_client.admin.command('ping')
            response_time = (time.time() - start_time) * 1000
            return {
                "name": service["name"],
                "status": "healthy",
                "response_time": response_time
            }
            
    except requests.exceptions.Timeout:
        return {
            "name": service["name"],
            "status": "unhealthy",
            "message": "Request timeout (>2s)",
            "response_time": 2000
        }
    except requests.exceptions.ConnectionError:
        return {
            "name": service["name"],
            "status": "unhealthy",
            "message": "Connection refused"
        }
    except Exception as e:
        return {
            "name": service["name"],
            "status": "unhealthy",
            "message": str(e)[:100]
        }


def get_system_metrics(mongo_client: MongoClient) -> Dict[str, int]:
    """
    Get system-wide metrics.
    
    Returns:
        {
            "active_strategies": int,
            "active_accounts": int,
            "pending_orders": int,
            "signals_today": int
        }
    """
    db = mongo_client['mathematricks_trading']
    
    try:
        # Active strategies
        active_strategies = db['strategy_configurations'].count_documents({"status": "ACTIVE"})
        
        # Active trading accounts
        active_accounts = db['trading_accounts'].count_documents({"is_active": True})
        
        # Pending orders (status PENDING or SUBMITTED)
        pending_orders = db['trading_orders'].count_documents({
            "status": {"$in": ["PENDING", "SUBMITTED"]}
        })
        
        # Signals today (from signal_store)
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        signals_today = db['signal_store'].count_documents({
            "created_at": {"$gte": today_start}
        })
        
        return {
            "active_strategies": active_strategies,
            "active_accounts": active_accounts,
            "pending_orders": pending_orders,
            "signals_today": signals_today
        }
        
    except Exception as e:
        logger.error(f"Error getting system metrics: {e}")
        return {}


def generate_system_health_widget(mongo_client: MongoClient, fund_id: str = None) -> Dict[str, Any]:
    """
    Generate system health widget data.
    
    Returns:
        {
            "overall_status": "healthy" | "degraded" | "unhealthy",
            "timestamp": str (ISO format),
            "services": [
                {
                    "name": str,
                    "status": "healthy" | "degraded" | "unhealthy",
                    "message": str (optional),
                    "response_time": float (ms),
                    "uptime": int (seconds, optional)
                }
            ],
            "metrics": {
                "active_strategies": int,
                "active_accounts": int,
                "pending_orders": int,
                "signals_today": int
            }
        }
    """
    logger.info("Generating system health widget...")
    
    # Check all services
    service_statuses = []
    for service in SERVICES:
        status = check_service_health(service, mongo_client)
        service_statuses.append(status)
        logger.info(f"  {service['name']}: {status['status']}")
    
    # Determine overall status
    unhealthy_count = sum(1 for s in service_statuses if s["status"] == "unhealthy")
    degraded_count = sum(1 for s in service_statuses if s["status"] == "degraded")
    
    if unhealthy_count > 0:
        overall_status = "unhealthy"
    elif degraded_count > 0:
        overall_status = "degraded"
    else:
        overall_status = "healthy"
    
    # Get system metrics
    metrics = get_system_metrics(mongo_client)
    
    result = {
        "overall_status": overall_status,
        "timestamp": datetime.utcnow().isoformat(),
        "services": service_statuses,
        "metrics": metrics
    }
    
    logger.info(f"System health: {overall_status} ({unhealthy_count} unhealthy, {degraded_count} degraded)")
    
    # Store in widget_data collection
    db = mongo_client['mathematricks_trading']
    db['widget_data'].update_one(
        {
            "widget_type": "SystemHealth",
            "fund_id": fund_id,
            "filters_hash": "99914b932bd37a50b983c5e7c90ae93b"  # MD5 hash of empty filters {}
        },
        {
            "$set": {
                "data": result,
                "computed_at": datetime.utcnow(),
                "ttl": 30  # 30 seconds TTL (refresh every 30s)
            }
        },
        upsert=True
    )
    
    return result
