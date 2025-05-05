# Utility function for creating error responses
from datetime import datetime
import uuid
from flask import g, jsonify


def error_response(error_type, message, status_code):
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