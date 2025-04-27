"""
Resume Optimizer API - Flask Application
Handles resume parsing, optimization, and generation.
"""

import os
import sys
import logging
import uuid
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import re
import io
import argparse
import requests
from functools import wraps
import psutil
import platform

from flask import Flask, request, jsonify, send_file, g, render_template, after_this_request
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# Import database functions or define fallbacks if import fails
try:
    from database import create_database_client, create_in_memory_database
except ImportError:
    logging.warning("database module could not be imported, using inline fallbacks")
    from collections import defaultdict
    
    class InMemoryDatabase:
        """Simple in-memory database fallback implementation."""
        
        def __init__(self):
            self.data = defaultdict(list)
            self.counters = defaultdict(int)
            logging.info("Initialized in-memory database fallback")
            
        def insert(self, collection, document):
            """Insert a document into a collection."""
            self.counters[collection] += 1
            document_id = self.counters[collection]
            document['id'] = document_id
            self.data[collection].append(document)
            return document_id
            
        def find(self, collection, query=None):
            """Find documents in a collection matching a query."""
            if query is None:
                return self.data[collection]
            
            results = []
            for doc in self.data[collection]:
                matches = True
                for key, value in query.items():
                    if key not in doc or doc[key] != value:
                        matches = False
                        break
                if matches:
                    results.append(doc)
            return results
            
        def table(self, name):
            """Compatibility method with Supabase client."""
            class TableQuery:
                def __init__(self, db, table_name):
                    self.db = db
                    self.table_name = table_name
                    
                def select(self, columns='*'):
                    return self
                    
                def limit(self, n):
                    return self
                    
                def execute(self):
                    return {"data": self.db.find(self.table_name)}
                    
            return TableQuery(self, name)
    
    def create_database_client():
        """Fallback database client creator."""
        logging.warning("Using inline fallback database client")
        return create_in_memory_database()
        
    def create_in_memory_database():
        """Create an in-memory database instance."""
        return InMemoryDatabase()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('app')

# Constants
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}
MAX_CONTENT_LENGTH = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB default

# OpenAI API settings
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY environment variable is not set")

OPENAI_API_BASE = "https://api.openai.com/v1"

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Transaction tracking
def get_transaction_id():
    """Get current transaction ID from Flask g object"""
    if not hasattr(g, 'transaction_id'):
        g.transaction_id = str(uuid.uuid4())
    return g.transaction_id

def track_request(f):
    """Decorator to track API requests with transaction ID"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Generate transaction ID
        transaction_id = get_transaction_id()
        
        # Log request
        logger.info(f"Transaction {transaction_id}: {request.method} {request.path}")
        
        # Track timing
        start_time = time.time()
        
        try:
            # Execute the function
            result = f(*args, **kwargs)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Log successful completion
            logger.info(f"Transaction {transaction_id} completed in {duration:.4f}s")
            
            return result
        except Exception as e:
            # Calculate duration
            duration = time.time() - start_time
            
            # Log error
            logger.error(f"Transaction {transaction_id} failed after {duration:.4f}s: {str(e)}")
            
            # Re-raise the exception
            raise
    
    return decorated_function

def allowed_file(filename):
    """Check if file has an allowed extension"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_app():
    """Create and configure the Flask application"""
    app = Flask(__name__, template_folder='templates')
    
    # Apply CORS settings
    cors_origins = os.environ.get('CORS_ORIGINS', '*')
    CORS(app, resources={r"/api/*": {"origins": cors_origins}})
    
    # Configure app settings
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
    app.config['JSON_SORT_KEYS'] = False
    
    # Middleware to log request info
    @app.before_request
    def before_request():
        g.start_time = time.time()
        transaction_id = get_transaction_id()
        logger.info(f"Transaction {transaction_id}: {request.method} {request.path} started")
    
    # Middleware to log response info
    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            transaction_id = get_transaction_id()
            logger.info(f"Transaction {transaction_id}: {request.method} {request.path} "
                       f"returned {response.status_code} in {duration:.4f}s")
        return response
    
    # Error handling middleware
    @app.errorhandler(Exception)
    def handle_exception(e):
        transaction_id = get_transaction_id()
        logger.error(f"Transaction {transaction_id}: Error processing request: {str(e)}")
        
        if isinstance(e, (RuntimeError, ValueError, KeyError)):
            # Client errors
            return jsonify({
                "error": str(e),
                "transaction_id": transaction_id
            }), 400
        else:
            # Server errors
            return jsonify({
                "error": "Internal server error",
                "transaction_id": transaction_id
            }), 500
    
    # Initialize database
    try:
        db_client = create_database_client()
        logger.info("Database client initialized")
    except Exception as e:
        logger.warning(f"Failed to initialize database client: {str(e)}")
        logger.warning("Falling back to in-memory database")
        try:
            db_client = create_in_memory_database()
            logger.info("In-memory database initialized")
        except Exception as e:
            logger.critical(f"Failed to start application: {str(e)}")
            logger.error(str(e))
            raise
    
    # Store database client in app config
    app.config['db_client'] = db_client
    
    # Initialize diagnostic system
    try:
        import diagnostic_system
        diagnostic = diagnostic_system.DiagnosticSystem()
        diagnostic.init_app(app)
        app.config['diagnostic'] = diagnostic
        logger.info("Diagnostic system initialized successfully")
    except ImportError:
        logger.warning("Diagnostic system not available")
    
    # Initialize PDF generator
    try:
        import pdf_generator
        pdf_gen = pdf_generator.create_pdf_generator()
        app.config['pdf_generator'] = pdf_gen
        
        # Check if pdflatex is available
        env_status = pdf_gen.check_environment()
        logger.info(f"PDF generator initialized with {env_status['latex_version']}")
    except ImportError:
        logger.error("Failed to import PDF generator")
        app.config['pdf_generator'] = None
    except Exception as e:
        logger.error(f"Failed to initialize PDF generator: {str(e)}")
        logger.warning("PDF generator initialized in fallback mode (pdflatex not available)")
    
    logger.warning("Using fallback in-memory database")
    logger.info("Database tables initialized: using_fallback")
    
    # Define routes
    @app.route('/')
    def index():
        return jsonify({
            "name": "Resume Optimizer API",
            "status": "running",
            "endpoints": {
                "api/health": "System health check",
                "api/upload": "Upload resume",
                "api/optimize": "Optimize resume",
                "api/download/:id/:format": "Download optimized resume"
            },
            "version": "1.0.0"
        })
    
    @app.route('/api/health')
    def health():
        """Health check endpoint"""
        return jsonify({
            "status": "ok",
            "uptime": str(datetime.now() - app.config.get('start_time', datetime.now())),
            "timestamp": datetime.now().isoformat(),
            "components": {
                "database": db_client.health_check() if db_client else {"status": "not_available"},
                "pdf_generator": {"status": "available" if app.config.get('pdf_generator') else "not_available"},
                "diagnostic": {"status": "available" if app.config.get('diagnostic') else "not_available"}
            }
        })
    
    @app.route('/api/upload', methods=['POST'])
    @track_request
    def upload_resume():
        """Upload a resume file"""
        # Check if the post request has the file part
        if 'resume' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['resume']
        
        # Check if the file is empty
        if file.filename == '':
            return jsonify({"error": "No file selected"}), 400
        
        # Check if the file type is allowed
        if not allowed_file(file.filename):
            return jsonify({
                "error": f"File type not allowed, only {', '.join(ALLOWED_EXTENSIONS)} formats are supported"
            }), 400
        
        # Save the file
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        
        # TODO: Process the file with resume_parser
        # For now, just return success with the file path
        
        # Generate a unique ID for the resume
        resume_id = f"resume_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Store resume details in database
        db_client.insert('resumes', {
            'id': resume_id,
            'filename': filename,
            'path': file_path,
            'status': 'uploaded',
            'file_type': filename.rsplit('.', 1)[1].lower(),
            'raw_text': "Sample text from resume"  # Placeholder
        })
        
        return jsonify({
            "resume_id": resume_id,
            "message": "Resume uploaded successfully",
            "transaction_id": get_transaction_id()
        })
    
    @app.route('/api/optimize', methods=['POST'])
    @track_request
    def optimize_resume_endpoint():
        """Optimize a resume for a job description"""
        data = request.json
        
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400
        
        # Required fields
        resume_id = data.get('resume_id')
        job_description = data.get('job_description')
        
        if not resume_id:
            return jsonify({"error": "resume_id is required"}), 400
        
        if not job_description:
            return jsonify({"error": "job_description is required"}), 400
        
        # Check if resume exists
        resume = db_client.find_one('resumes', {'id': resume_id})
        if not resume:
            return jsonify({"error": f"Resume with ID {resume_id} not found"}), 404
        
        # Generate a unique ID for the optimized resume
        optimized_id = f"resume_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        # Store optimization details
        db_client.insert('optimizations', {
            'id': optimized_id,
            'resume_id': resume_id,
            'job_description': job_description,
            'status': 'completed',
            'optimization_data': {
                'score': 0.85,  # Placeholder
                'improvements': ['Added keywords', 'Restructured experience']  # Placeholder
            }
        })
        
        return jsonify({
            "resume_id": resume_id,
            "optimized_resume_id": optimized_id,
            "message": "Resume optimization completed",
            "transaction_id": get_transaction_id()
        })
    
    @app.route('/api/download/<resume_id>/<format_type>', methods=['GET'])
    @track_request
    def download_resume(resume_id, format_type):
        """Download a resume in specified format"""
        # Check if resume exists
        resume = db_client.find_one('resumes', {'id': resume_id})
        if not resume:
            # Check if it's an optimized resume
            optimization = db_client.find_one('optimizations', {'id': resume_id})
            if not optimization:
                return jsonify({"error": f"Resume with ID {resume_id} not found"}), 404
            
            # Use the optimized resume data
            resume = db_client.find_one('resumes', {'id': optimization.get('resume_id')})
            if not resume:
                return jsonify({"error": f"Original resume for optimized ID {resume_id} not found"}), 404
        
        # Create a simple file for the requested format
        if format_type == 'json':
            # Return resume data as JSON
            return jsonify(resume)
        
        elif format_type == 'pdf':
            # Create a simple PDF
            pdf_path = os.path.join(OUTPUT_FOLDER, f"{resume_id}.pdf")
            
            # Check if PDF generator is available
            if app.config.get('pdf_generator'):
                # Use PDF generator to create PDF
                app.config['pdf_generator'].generate_pdf({
                    'name': 'John Doe',  # Placeholder
                    'email': 'john@example.com',  # Placeholder
                    'experience': [
                        {'title': 'Software Engineer', 'company': 'Tech Co', 'years': '2018-2022'}
                    ]
                }, pdf_path)
            else:
                # Create a simple text file as fallback
                with open(pdf_path, 'w') as f:
                    f.write(f"Resume ID: {resume_id}\nFormat: PDF (placeholder)")
            
            return send_file(pdf_path, as_attachment=True, download_name=f"resume_{resume_id}.pdf")
        
        elif format_type == 'latex':
            # Create a simple LaTeX file
            latex_path = os.path.join(OUTPUT_FOLDER, f"{resume_id}.tex")
            with open(latex_path, 'w') as f:
                f.write(r"""
\documentclass{article}
\begin{document}
\section{Resume}
This is a placeholder LaTeX document for resume ID: %s
\end{document}
""" % resume_id)
            
            return send_file(latex_path, as_attachment=True, download_name=f"resume_{resume_id}.tex")
        
        else:
            # Invalid format type
            return jsonify({"error": f"Unsupported format: {format_type}"}), 400
    
    @app.route('/status')
    def status():
        """System status endpoint with more details"""
        return render_template('status.html', {
            "system_info": {
                "uptime": str(datetime.now() - app.config.get('start_time', datetime.now())),
                "memory_usage": "N/A",  # Placeholder
                "cpu_usage": "N/A",  # Placeholder
                "active_connections": "N/A"  # Placeholder
            },
            "database_status": db_client.health_check() if db_client else {"status": "not_available"},
            "recent_transactions": []  # Placeholder
        })
    
    @app.route('/diagnostic/diagnostics')
    def diagnostics():
        """Diagnostic dashboard"""
        if not app.config.get('diagnostic'):
            return jsonify({"error": "Diagnostic system not available"}), 404
        
        # Get system metrics from diagnostic system
        metrics = app.config['diagnostic'].get_metrics()
        
        # Get recent transactions
        transactions = []
        
        # Render the diagnostics template
        return render_template('diagnostics.html', 
                             metrics=metrics,
                             transactions=transactions,
                             uptime=str(datetime.now() - app.config.get('start_time', datetime.now())),
                             timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             timestamp_5_min_ago=(datetime.now() - timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
                             env_vars={k: "***" if k.lower().find("key") >= 0 else v for k, v in os.environ.items()})
    
    @app.route('/api/test')
    def test_endpoint():
        """Test endpoint for diagnostics"""
        return jsonify({
            "status": "ok",
            "message": "Test endpoint",
            "transaction_id": get_transaction_id(),
            "timestamp": datetime.now().isoformat()
        })
    
    @app.route('/api/test/simulate-failure')
    def test_simulate_failure():
        """Test endpoint to simulate a failure"""
        raise ValueError("This is a simulated failure for testing error handling")
    
    # Store app start time
    app.config['start_time'] = datetime.now()
    
    # Return the app
    return app

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Resume Optimizer API')
    parser.add_argument('--port', type=int, help='Port to listen on')
    parser.add_argument('--debug', action='store_true', help='Run in debug mode')
    parser.add_argument('--host', default='0.0.0.0', help='Host to bind to')
    return parser.parse_args()

if __name__ == '__main__':
    # Parse arguments
    args = parse_args()
    
    # Determine port
    default_port = int(os.environ.get('PORT', 5000))
    port = args.port if args.port else default_port
    
    # Debug mode
    debug = args.debug or (os.environ.get('DEBUG', 'false').lower() == 'true')
    
    # Start the app
    app = create_app()
    logger.info(f"Starting Flask server on port {port} (debug: {debug})")
    app.run(host=args.host, port=port, debug=debug) 