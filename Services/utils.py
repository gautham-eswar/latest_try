
from datetime import datetime
from pathlib import Path
import time
import uuid

from flask import current_app, g, jsonify
import requests

from Services.openai_interface import OPENAI_API_BASE, OPENAI_API_KEY

START_TIME = time.time()

def get_uptime():
    """Get application uptime in human readable format"""
    start_time = current_app.config.get("START_TIME", START_TIME)
    uptime_seconds = time.time() - start_time
    
    return format_uptime(uptime_seconds)

def format_uptime(seconds):
    """Format seconds to human readable uptime."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{int(days)}d {int(hours)}h {int(minutes)}m"
    elif hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

def format_size(size_bytes):
    """Format bytes to human readable size."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

# Utility function for creating error responses
def create_error_response(error_type, message, status_code):
    """Create a standardized error response following the error schema."""
    return (
        jsonify(
            {
        "error": error_type,
        "message": message,
        "status_code": status_code,
                "transaction_id": getattr(g, "transaction_id", None)
                or str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat(),
            }
        ),
        status_code,
    )


def get_component_status():
    """Get status of all system components"""
    components = {
        "system": {"status": "healthy", "message": "System is operating normally"},
        "database": {
            "status": "warning",
            "message": "Using in-memory database (no Supabase connection)",
        },
        "openai_api": {"status": "unknown", "message": "API key not tested"},
        "file_system": {"status": "healthy", "message": "File system is writable"},
    }
    
    # Test file system by attempting to write to a temp file
    try:
        temp_dir = Path("./temp")
        temp_dir.mkdir(exist_ok=True)
        test_file = temp_dir / "test_write.txt"
        test_file.write_text("Test write operation")
        test_file.unlink()
        components["file_system"]["status"] = "healthy"
    except Exception as e:
        components["file_system"]["status"] = "error"
        components["file_system"]["message"] = f"File system error: {str(e)}"
    
    # Test OpenAI API
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        }
        
        response = requests.get(f"{OPENAI_API_BASE}/models", headers=headers)
        
        if response.status_code == 200:
            components["openai_api"]["status"] = "healthy"
            components["openai_api"]["message"] = "API connection successful"
        else:
            components["openai_api"]["status"] = "error"
            components["openai_api"]["message"] = f"API error: {response.status_code}"
    except Exception as e:
        components["openai_api"]["status"] = "error"
        components["openai_api"]["message"] = f"API connection error: {str(e)}"
    
    return components