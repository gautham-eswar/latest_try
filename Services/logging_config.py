"""
Centralized Logging Configuration for the Resume Optimizer Application.

This module sets up the root logger for the entire application. It should be
imported at the very top of the main application file (working_app.py) before
any other application modules are imported. This ensures that all subsequent
loggers inherit this configuration.
"""

import logging
from collections import deque
from datetime import datetime
import os

# --- In-Memory Log Handler ---
# This handler captures logs in a rotating buffer for viewing via an API endpoint.

log_buffer = deque(maxlen=1000)  # Keep the last 1000 log entries

class MemoryLogHandler(logging.Handler):
    """Custom log handler that stores logs in memory."""
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'message': self.format(record),
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'process': record.process,
            }
            log_buffer.append(log_entry)
        except Exception:
            # Avoid letting logging errors crash the application
            pass

def get_log_buffer():
    """Returns the global log buffer."""
    return log_buffer

# --- Root Logger Configuration ---

def setup_logging():
    """
    Configures the root logger for the application.
    This function should be called only once when the application starts.
    """
    # Get the root logger. All other loggers will inherit this configuration.
    root_logger = logging.getLogger()

    # If the in-memory handler is already attached, avoid reconfiguring
    for handler in root_logger.handlers:
        if isinstance(handler, MemoryLogHandler):
            return

    # Determine if running under Gunicorn by checking environment or process
    # Gunicorn sets the 'gunicorn' logger, which is a reliable check.
    is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "") or 'gunicorn.error' in logging.Logger.manager.loggerDict

    if is_gunicorn:
        # When running under Gunicorn, inherit its handlers and level.
        gunicorn_logger = logging.getLogger('gunicorn.error')
        if gunicorn_logger.handlers:
            root_logger.handlers = gunicorn_logger.handlers
        root_logger.setLevel(gunicorn_logger.level)
    else:
        # For local development, configure a basic console logger.
        # Clear any existing handlers to avoid duplicates
        if root_logger.hasHandlers():
            root_logger.handlers.clear()
        
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(levelname)s - [%(name)s] - %(message)s (%(funcName)s:%(lineno)d)"
        )

    # Add our custom in-memory handler to the root logger.
    # This ensures it captures logs from ALL modules.
    memory_handler = MemoryLogHandler()
    memory_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(memory_handler)

    # Ensure the root logger's level is at least INFO to capture everything.
    root_logger.setLevel(logging.INFO)

    # Log a confirmation message that the new system is in place.
    root_logger.info("Centralized logging configured successfully.")

# --- Run the setup immediately upon import ---
setup_logging() 