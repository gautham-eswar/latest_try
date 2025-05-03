import logging

from flask import jsonify, render_template
import psutil
from Services import diagnostic_system
from Services.database import get_db
from Services.utils import get_component_status, get_uptime


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_status():
    try:
        components = get_component_status()
    except Exception as e:
        logger.error(f"Failed to get component status: {str(e)}")
        components = {
            "database": {"status": "error", "message": str(e)},
            "system": {
                "status": "unknown",
                "message": "Could not retrieve system status",
            },
        }
    
    # Get system metrics with fallbacks
    try:
        memory = psutil.virtual_memory()
        cpu_percent = psutil.cpu_percent(interval=0.1)
    except Exception as e:
        logger.error(f"Failed to get system metrics: {str(e)}")
        memory = None
        cpu_percent = None
    
    # Determine overall system status based on component statuses
    overall_status = "healthy"
    for component in components.values():
        if component.get("status") == "error":
            overall_status = "error"
            break
        elif component.get("status") == "warning" and overall_status != "error":
            overall_status = "warning"
    
    # Create a database status object with fallbacks
    try:
        db = get_db()
        db_check = (
            db.health_check()
            if hasattr(db, "health_check")
            else {"status": "unknown"}
        )
        database_status = {
            "status": db_check.get("status", "unknown"),
            "message": db_check.get("message", "Database status unknown"),
            "tables": db_check.get(
                "tables", ["resumes", "optimizations", "users"]
            ),  # Example tables
        }
    except Exception as e:
        logger.error(f"Failed to check database status: {str(e)}")
        database_status = {
            "status": "error",
            "message": f"Database error: {str(e)}",
            "tables": [],
        }
    
    # System info with fallbacks
    system_info = {
        "uptime": get_uptime(),
        "memory_usage": f"{memory.percent:.1f}%" if memory else "Unknown",
        "cpu_usage": (
            f"{cpu_percent:.1f}%" if cpu_percent is not None else "Unknown"
        ),
    }
    
    # Recent transactions (placeholder) with fallbacks
    try:
        if diagnostic_system and hasattr(
            diagnostic_system, "transaction_history"
        ):
            recent_transactions = diagnostic_system.transaction_history[:5]
        else:
            recent_transactions = []
    except Exception as e:
        logger.error(f"Failed to get transaction history: {str(e)}")
        recent_transactions = []
    
    # Render the template with error handling
    try:
        return render_template(
            "status.html",
                            system_info=system_info,
                            database_status=database_status,
            recent_transactions=recent_transactions,
        )
    except Exception as e:
        logger.error(f"Error rendering status template: {str(e)}")
        # Fall back to JSON response on template error
        return (
            jsonify(
                {
            "status": overall_status,
            "system_info": system_info,
            "components": components,
                    "error": f"Template error: {str(e)}",
                }
            ),
            200,
        )  # Return 200 even for errors