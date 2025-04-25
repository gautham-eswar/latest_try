"""
Simple Flask application for testing Resume Optimizer endpoints
"""

import os
import sys
import logging
import json
import uuid
from datetime import datetime

from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('simple_app')

# Load environment variables
load_dotenv()

def create_app():
    """Create and configure a minimalist Flask application."""
    app = Flask(__name__)
    
    # Configure application
    app.config['DEBUG'] = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    
    # Set up CORS
    CORS(app, resources={r"/api/*": {"origins": os.environ.get('CORS_ORIGINS', '*')}})
    
    # Basic routes
    @app.route('/')
    def index():
        """Root endpoint with basic API documentation."""
        return jsonify({
            'name': 'Resume Optimizer API',
            'version': '0.1.0',
            'status': 'healthy',
            'endpoints': {
                '/': 'API documentation (this endpoint)',
                '/api/health': 'Basic health check',
                '/api/diagnostic': 'System diagnostics in JSON format'
            }
        })
    
    @app.route('/api/health')
    def health_check():
        """Basic health check that always returns 200."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'request_id': str(uuid.uuid4())
        })
    
    @app.route('/api/diagnostic')
    def api_diagnostic():
        """System diagnostics in JSON format."""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'request_id': str(uuid.uuid4()),
            'components': {
                'system': 'healthy',
                'database': 'in_memory',
                'file_system': 'available'
            },
            'version': '0.1.0'
        })
    
    return app

if __name__ == '__main__':
    try:
        # Parse command line arguments for port
        port = 5000
        print(f"Default port: {port}")
        debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
        
        # Check for --port argument
        for i, arg in enumerate(sys.argv):
            print(f"Checking arg: {arg}")
            if arg == '--port' and i + 1 < len(sys.argv):
                port = int(sys.argv[i + 1])
                print(f"Port set from --port arg to: {port}")
            elif arg.startswith('--port='):
                port = int(arg.split('=')[1])
                print(f"Port set from --port= arg to: {port}")
        
        # Also check environment variable (takes precedence)
        if 'PORT' in os.environ:
            port = int(os.environ.get('PORT'))
            print(f"Port set from PORT env var to: {port}")
        
        print(f"Final port value: {port}")
        app = create_app()
        logger.info(f"Starting Flask server on port {port} (debug: {debug})")
        app.run(host='0.0.0.0', port=port, debug=debug)
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.exception(e)
        sys.exit(1) 