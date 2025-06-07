import logging
from collections import deque
from datetime import datetime
import os
import sys # Added sys for StreamHandler

# --- In-Memory Log Handler ---
log_buffer = deque(maxlen=1000)

class MemoryLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_entry = {
                'timestamp': datetime.fromtimestamp(record.created).isoformat(),
                'level': record.levelname,
                'message': self.format(record), # Use formatter for the message
                'module': record.module,
                'function': record.funcName,
                'line': record.lineno,
                'process': record.process,
            }
            log_buffer.append(log_entry)
        except Exception:
            pass

def get_log_buffer():
    return log_buffer

# --- Root Logger Configuration ---
def setup_logging():
    root_logger = logging.getLogger()
    # Clear any existing handlers first to prevent duplicates, especially in reloads
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    # Set a default level for the root logger. Gunicorn might override this for its logs.
    # Handlers can have their own levels if needed.
    root_logger.setLevel(logging.INFO)

    is_gunicorn = "gunicorn" in os.environ.get("SERVER_SOFTWARE", "") or 'gunicorn.error' in logging.Logger.manager.loggerDict

    if is_gunicorn:
        # Gunicorn is active.
        # Gunicorn's own logs (access, error) will be handled by Gunicorn's logging setup.
        # We primarily need to ensure our application's logs (which go to the root logger)
        # are also output to the console in a way Gunicorn captures.
        gunicorn_logger = logging.getLogger('gunicorn.error')
        root_logger.setLevel(gunicorn_logger.level) # Respect Gunicorn's level for the root logger

        # Add a stream handler that Gunicorn will capture
        # Gunicorn typically captures stdout/stderr.
        console_handler = logging.StreamHandler(sys.stdout) # Explicitly use stdout
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s (%(funcName)s:%(lineno)d)"
        ))
        root_logger.addHandler(console_handler)
        
        # Gunicorn already logs its own messages. We don't need to copy its handlers.
        # Our goal is that messages logged via `logging.getLogger(__name__)`
        # get to the console (for Gunicorn/Render) AND our MemoryHandler.
        logging.getLogger().info("Logging configured for Gunicorn environment.")

    else:
        # Not running under Gunicorn (e.g., local development).
        # Configure a basic console logger.
        console_handler = logging.StreamHandler(sys.stdout) # Use stdout for consistency
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(levelname)s - [%(name)s] - %(message)s (%(funcName)s:%(lineno)d)"
        ))
        root_logger.addHandler(console_handler)
        logging.getLogger().info("Logging configured for local development environment.")

    # Add the custom in-memory handler to the root logger.
    # This will capture logs from all modules using the standard logging system.
    memory_handler = MemoryLogHandler()
    # Ensure the message passed to the buffer is the fully formatted string
    memory_handler.setFormatter(logging.Formatter('%(message)s'))
    root_logger.addHandler(memory_handler)

    # Log a confirmation message that the new system is in place.
    # This message should now go to both console and memory_handler.
    root_logger.info("Centralized logging configured successfully (MemoryHandler added).")

# --- Run the setup immediately upon import ---
setup_logging()