#!/usr/bin/env python3
"""
Resume Optimizer Runtime Script
This script handles running the Resume Optimizer application with proper port configuration.
"""

import os
import sys
import argparse
import logging
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Resume Optimizer Runtime Script')
    parser.add_argument('--app', choices=['app', 'working_app', 'simple_app', 'very_simple'], 
                      default='working_app', help='Application module to run')
    parser.add_argument('--port', type=int, help='Port to listen on (overrides PORT env var)')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    parser.add_argument('--env-file', help='Path to .env file')
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    # Load environment variables
    if args.env_file:
        if os.path.exists(args.env_file):
            logger.info(f"Loading environment from {args.env_file}")
            load_dotenv(args.env_file)
        else:
            logger.warning(f"Environment file {args.env_file} not found, using default")
            load_dotenv()
    else:
        load_dotenv()
    
    # Determine port
    port = None
    
    # First check command line args
    if args.port:
        port = args.port
        logger.info(f"Using port {port} from command line arguments")
    
    # Then check PORT environment variable
    if port is None:
        env_port = os.environ.get('PORT')
        if env_port:
            try:
                port = int(env_port)
                logger.info(f"Using port {port} from PORT environment variable")
            except ValueError:
                logger.warning(f"Invalid PORT environment variable: {env_port}")
    
    # Use default port if none specified
    if port is None:
        # Default to 8080 (avoid 5000 on macOS which is used by AirPlay)
        port = 8080
        logger.info(f"Using default port {port}")
    
    # Set PORT environment variable for app to use
    os.environ['PORT'] = str(port)
    
    # Determine debug mode
    debug = args.debug or os.environ.get('DEBUG', 'false').lower() in ('true', '1', 'yes')
    
    # Select the app module to run
    if args.app == 'app':
        logger.info("Running full application (app.py)")
        from app import create_app
        app = create_app()
        app.run(host=args.host, port=port, debug=debug)
    
    elif args.app == 'working_app':
        logger.info("Running working application (working_app.py)")
        from working_app import create_app
        app = create_app()
        logger.info(f"Starting Flask server on {args.host}:{port} (debug: {debug})")
        app.run(host=args.host, port=port, debug=debug)
    
    elif args.app == 'simple_app':
        logger.info("Running simple application (simple_app.py)")
        from simple_app import app
        logger.info(f"Starting Flask server on {args.host}:{port} (debug: {debug})")
        app.run(host=args.host, port=port, debug=debug)
    
    elif args.app == 'very_simple':
        logger.info("Running very simple application (very_simple.py)")
        from very_simple import app
        logger.info(f"Starting Flask server on {args.host}:{port} (debug: {debug})")
        app.run(host=args.host, port=port, debug=debug)
    
    else:
        logger.error(f"Unknown application: {args.app}")
        sys.exit(1)

if __name__ == '__main__':
    main() 