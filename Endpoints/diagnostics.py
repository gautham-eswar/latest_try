from datetime import datetime, timedelta
import logging
import os
import platform
import sys
import time
import uuid

from flask import jsonify, render_template
import psutil

from Services.utils import START_TIME, format_size, format_uptime, get_component_status

# Basic logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def diagnostics_page():
    # Get system information
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    # Fetch component status
    try:
        components = get_component_status()
    except Exception as e:
        logger.error(f"Failed to get component status for diagnostics: {str(e)}")
        components = {
            "system": {"status": "error", "message": "Failed to retrieve status"},
            "database": {"status": "error", "message": str(e)},
            "openai_api": {"status": "error", "message": str(e)},
            "file_system": {"status": "error", "message": str(e)},
        }

    # Determine overall system status based on components
    overall_status = "healthy"
    for component_status in components.values():
        if component_status.get("status") == "error":
            overall_status = "error"
            break
        elif (
            component_status.get("status") == "warning"
            and overall_status != "error"
        ):
            overall_status = "warning"

    # Placeholder for other variables (adjust as needed)
    active_connections = 0  # Replace with actual logic if available
    version = "0.1.0"  # Replace with actual version logic
    title = "System Diagnostics"
    env_vars_filtered = {
        k: "***" if "key" in k.lower() or "token" in k.lower() else v
        for k, v in os.environ.items()
    }
    
    # Sample metrics
    resume_processing_times = [1.2, 0.9, 1.5, 1.1, 1.3]
    api_response_times = [0.2, 0.3, 0.1, 0.2, 0.1]
    
    # Sample requests
    recent_requests = [
        {
            "id": f"req-{uuid.uuid4().hex[:8]}",
            "method": "POST",
            "endpoint": "/api/upload",
            "status": 200,
            "duration": 0.35,
            "timestamp": (datetime.now() - timedelta(minutes=2)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        },
        {
            "id": f"req-{uuid.uuid4().hex[:8]}",
            "method": "POST",
            "endpoint": "/api/optimize",
            "status": 200,
            "duration": 1.24,
            "timestamp": (datetime.now() - timedelta(minutes=1)).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
        },
    ]
    
    # Prepare diagnostic info in structured format for template
    system_info = {
        "uptime": format_uptime(int(time.time() - START_TIME)),
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total": format_size(memory.total),
            "available": format_size(memory.available),
            "percent": memory.percent,
        },
        "disk": {
            "total": format_size(disk.total),
            "free": format_size(disk.free),
            "percent": disk.percent,
        },
    }
    
    # Gracefully handle template rendering
    try:
        current_uptime = format_uptime(int(time.time() - START_TIME))
        return render_template(
            "diagnostics.html",
            title=title,
            system_status=overall_status,
            active_connections=active_connections,
            version=version,
            components=components,
                            system_info=system_info,
            uptime=current_uptime,
                            resume_processing_times=resume_processing_times,
                            api_response_times=api_response_times,
                            recent_requests=recent_requests,
            transactions=[],
            env_vars=env_vars_filtered,
            pipeline_status={
                "status": "unknown",
                "message": "No pipeline data available",
            },
                            pipeline_stages=[],
                            pipeline_history=[],
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
    except Exception as e:
        logger.error(
            f"Error rendering diagnostics template: {str(e)}", exc_info=True
        )
        return (
            jsonify(
                {
            "status": "error",
                    "error_type": type(e).__name__,
                    "message": f"Error rendering diagnostics page: {str(e)}",
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            500,
        )