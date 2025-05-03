
import time

from flask import current_app


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