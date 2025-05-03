from datetime import datetime
import logging
import time

from flask import current_app, jsonify
import psutil
import requests

from Services.database import get_db
from Services.openai_interface import OPENAI_API_BASE, OPENAI_API_KEY
from Services.utils import format_size, get_uptime



logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



def health_analysis():
    try:
        health_data = {
            "status": "healthy",
            "uptime": get_uptime(),
            "timestamp": datetime.now().isoformat(),
            "components": {},
        }
        
        # Get system metrics with detailed error handling
        try:
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage("/")
            
            health_data["memory"] = {
                "status": "healthy",
                "total": format_size(memory.total),
                "available": format_size(memory.available),
                "percent": memory.percent,
            }
            
            health_data["disk"] = {
                "status": "healthy",
                "total": format_size(disk.total),
                "free": format_size(disk.free),
                "percent": disk.percent,
            }
            
            health_data["components"]["system_resources"] = "healthy"
        except Exception as e:
            logger.warning(f"Error getting system metrics: {str(e)}")
            health_data["status"] = "degraded"
            health_data["memory"] = {"status": "error", "message": str(e)}
            health_data["disk"] = {"status": "error", "message": str(e)}
            health_data["components"]["system_resources"] = "error"
        
        # Check database with detailed error handling
        try:
            db = get_db()
            db_status = (
                db.health_check()
                if hasattr(db, "health_check")
                else {"status": "unknown"}
            )
            health_data["database"] = db_status
            health_data["components"]["database"] = db_status.get(
                "status", "unknown"
            )
            if db_status.get("status") == "error":
                health_data["status"] = "degraded"
        except Exception as e:
            logger.warning(f"Database health check failed: {str(e)}")
            health_data["database"] = {"status": "error", "message": str(e)}
            health_data["components"]["database"] = "error"
            health_data["status"] = "degraded"
        
        # Check OpenAI API connection
        try:
            headers = {
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            }
            response = requests.get(
                f"{OPENAI_API_BASE}/models", headers=headers, timeout=5
            )
            
            if response.status_code == 200:
                health_data["openai"] = {"status": "healthy"}
                health_data["components"]["openai"] = "healthy"
            else:
                health_data["openai"] = {
                    "status": "error", 
                    "message": f"API returned status {response.status_code}",
                }
                health_data["components"]["openai"] = "error"
                health_data["status"] = "degraded"
        except Exception as e:
            logger.warning(f"OpenAI API check failed: {str(e)}")
            health_data["openai"] = {"status": "error", "message": str(e)}
            health_data["components"]["openai"] = "error"
            health_data["status"] = "degraded"
        
        # Always return 200 for Render's health check
        return jsonify(health_data), 200
        
    except Exception as e:
        # Even if everything fails, return 200 with error details
        logger.error(f"Critical error in health check: {str(e)}")
        return (
            jsonify(
                {
            "status": "critical",
            "message": f"Health check encountered a critical error: {str(e)}",
            "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            200,
        )  # Still return 200 for Render
    
