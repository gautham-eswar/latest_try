"""
WSGI entry point for the Resume Optimizer application.
This file is used by Gunicorn to run the application.
"""

import os
import sys
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("wsgi")

# Load environment variables from .env file if it exists
load_dotenv()

try:
    # Set default port if not provided
    if not os.environ.get("PORT"):
        os.environ["PORT"] = "8080"
        
    # Set render flag for render-specific handling
    if os.environ.get("RENDER"):
        logger.info("Running on Render platform")
    
    # Allow missing API key in development mode
    if os.environ.get("FLASK_ENV") == "development" and not os.environ.get("OPENAI_API_KEY"):
        os.environ["ALLOW_MISSING_API_KEY"] = "true"
        logger.warning("Running in development mode without API key")

    # Try importing from working_app first (preferred)
    try:
        logger.info("Attempting to import from working_app...")
        from working_app import create_app
        logger.info("Successfully imported from working_app")
    except ImportError as e:
        logger.warning(f"Failed to import from working_app: {str(e)}")
        logger.info("Falling back to app.py...")
        try:
            from app import create_app
            logger.info("Successfully imported from app")
        except ImportError as e:
            logger.critical(f"Failed to import from app.py: {str(e)}")
            raise ImportError("Could not import application from either working_app or app")
    
    # Create the application
    app = create_app()
    
    logger.info(f"WSGI application initialized successfully on port {os.environ.get('PORT')}")
    
except Exception as e:
    logger.critical(f"Failed to initialize application: {str(e)}")
    
    # Create a minimal flask app for error reporting
    from flask import Flask, jsonify
    app = Flask(__name__)
    
    @app.route('/')
    def error_home():
        return jsonify({
            "status": "error",
            "message": "Application failed to initialize",
            "error": str(e)
        }), 500
    
    @app.route('/api/health')
    def error_health():
        return jsonify({
            "status": "critical_error",
            "message": "Application failed to initialize",
            "error": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port) 