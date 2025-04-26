#!/usr/bin/env python3
"""
Render platform entrypoint script for Resume Optimizer application.
This handles command-line arguments and environment setup before starting the app.
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("render_entrypoint")

def main():
    """Main entry point for the application when run on Render."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Resume Optimizer service")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the service on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args, unknown = parser.parse_known_args()
    
    # Load environment variables
    load_dotenv()
    
    # Set environment variables from arguments
    os.environ["PORT"] = str(args.port)
    os.environ["RENDER"] = "true"
    
    logger.info(f"Starting Resume Optimizer service on {args.host}:{args.port}")
    
    try:
        # Import and create the Flask application
        try:
            from working_app import create_app
            logger.info("Using working_app.py")
        except ImportError as e:
            logger.warning(f"Could not import working_app: {str(e)}")
            try:
                from app import create_app
                logger.info("Using app.py")
            except ImportError as e2:
                logger.critical(f"Could not import app: {str(e2)}")
                raise ImportError("Failed to import application module")
        
        # Create the application
        app = create_app()
        
        # Run the application
        if args.debug:
            logger.info("Running in debug mode")
            app.run(host=args.host, port=args.port, debug=True)
        else:
            app.run(host=args.host, port=args.port)
            
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.critical(f"Exception type: {type(e).__name__}")
        logger.critical(f"Exception args: {e.args}")
        sys.exit(1)

if __name__ == "__main__":
    main() 