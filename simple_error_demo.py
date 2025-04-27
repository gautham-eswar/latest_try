from flask import Flask, jsonify, request
import datetime
import uuid
import logging
import os
import argparse
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_error_demo.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("error-demo-server")

app = Flask(__name__)

def get_transaction_id():
    """Generate a unique transaction ID."""
    return str(uuid.uuid4())

@app.route('/api/health')
def health():
    """Health check endpoint."""
    logger.info("Health check requested")
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().isoformat(),
        "version": "1.0.0"
    })

@app.route('/api/test/custom-error/<int:error_code>')
def test_custom_error(error_code):
    """Test endpoint to return custom error codes."""
    logger.info(f"Custom error requested with code: {error_code}")
    
    if error_code < 400 or error_code > 599:
        logger.warning(f"Invalid error code requested: {error_code}")
        return jsonify({
            "error": "Invalid error code",
            "message": "Error code must be between 400 and 599",
            "status_code": 400,
            "transaction_id": get_transaction_id(),
            "timestamp": datetime.datetime.now().isoformat()
        }), 400
    
    # Define some standard error messages for common codes
    error_messages = {
        400: "Bad Request",
        401: "Unauthorized",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        408: "Request Timeout",
        418: "I'm a teapot",
        429: "Too Many Requests",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Timeout"
    }
    
    message = error_messages.get(error_code, f"Custom error with code {error_code}")
    logger.info(f"Returning error response with code {error_code}: {message}")
    
    return jsonify({
        "error": f"Error {error_code}",
        "message": message,
        "status_code": error_code,
        "transaction_id": get_transaction_id(),
        "timestamp": datetime.datetime.now().isoformat()
    }), error_code

@app.route('/api/test/simulate-failure')
def simulate_failure():
    """Endpoint that always returns a 500 error."""
    logger.info("Simulating server failure")
    return jsonify({
        "error": "InternalServerError",
        "message": "This is a simulated server error",
        "status_code": 500,
        "transaction_id": get_transaction_id(),
        "timestamp": datetime.datetime.now().isoformat()
    }), 500

# Global error handler
@app.errorhandler(Exception)
def handle_exception(e):
    """Handle all exceptions and return a consistent JSON error response."""
    # Determine the status code
    try:
        status_code = e.code if hasattr(e, 'code') else 500
    except:
        status_code = 500
    
    # Get error type and message
    error_type = e.__class__.__name__
    error_message = str(e)
    
    # Log the error
    transaction_id = get_transaction_id()
    logger.error(f"Error {transaction_id}: {error_type} - {error_message}", exc_info=True)
    
    # Return standardized error response
    return jsonify({
        "error": error_type,
        "message": error_message,
        "status_code": status_code,
        "transaction_id": transaction_id,
        "timestamp": datetime.datetime.now().isoformat()
    }), status_code

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Simple Error Demo Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=5001, help="Port to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    return parser.parse_args()

def main():
    """Main entry point for the server."""
    args = parse_args()
    
    logger.info(f"Starting Simple Error Demo Server on {args.host}:{args.port}")
    logger.info(f"Debug mode: {'enabled' if args.debug else 'disabled'}")
    
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0

if __name__ == '__main__':
    sys.exit(main()) 