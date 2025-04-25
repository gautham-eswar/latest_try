#!/usr/bin/env python3
"""
Simple script to run the Resume Optimizer Flask app
"""

import os
import sys
import logging
import argparse
from app import create_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run_app')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Resume Optimizer API')
    parser.add_argument('--port', type=int, default=5000,
                      help='Port to run the server on (default: 5000)')
    parser.add_argument('--debug', action='store_true',
                      help='Run in debug mode')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                      help='Host to run the server on (default: 0.0.0.0)')
    
    return parser.parse_args()

if __name__ == '__main__':
    try:
        # Parse command line arguments
        args = parse_args()
        port = args.port
        debug = args.debug
        host = args.host
        
        # Check if port is already in PORT environment variable
        if 'PORT' in os.environ:
            port = int(os.environ['PORT'])
            logger.info(f"Using port from environment variable: {port}")
        
        # Log configuration
        logger.info(f"Starting Flask server on {host}:{port} (debug: {debug})")
        
        # Create and run app
        app = create_app()
        app.run(host=host, port=port, debug=debug)
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.exception(e)
        sys.exit(1) 