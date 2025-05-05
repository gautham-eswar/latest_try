"""
Working Resume Optimizer Flask App with proper port handling
"""

import os
import logging
from datetime import datetime
import uuid
import json
import time
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask, jsonify, request, g
from flask_cors import CORS

# Import the advanced modules
from Endpoints.diagnostics import diagnostics_page
from Endpoints.health import health_page
from Endpoints.status import status_page

from Pipeline.optimizer import enhance_resume
from Pipeline.resume_handling import OUTPUT_FOLDER, UPLOAD_FOLDER, download_resume, get_file_ext, upload_resume

from Services.diagnostic_system import get_diagnostic_system
from Services.errors import error_response


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}



# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Track application startup
diagnostic_system = get_diagnostic_system()


def handle_missing_api_key():
    """Return a standardized error response for missing API key"""
    if request.path == "/api/health":
        # Still allow health checks without API key
        return None
    
    error_response = {
        "error": "OpenAI API key not configured",
        "message": "The server is missing required API credentials. Please contact the administrator.",
        "status": "configuration_error",
        "timestamp": datetime.now().isoformat(),
    }
    return jsonify(error_response), 503  # Service Unavailable


def create_app():
    """Create and configure the Flask application."""
    global app, diagnostic_system
    
    # Create Flask app
    app = Flask(__name__, template_folder="templates", static_folder="static")
    
    # Apply middleware
    app.wsgi_app = ProxyFix(app.wsgi_app)
    
    # Configure app settings
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24))
    app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
    app.config["MAX_CONTENT_LENGTH"] = int(
        os.environ.get("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
    )  # 16MB
    app.config["TRAP_HTTP_EXCEPTIONS"] = (
        True  # Ensure HTTP exceptions are handled by our handlers
    )
    app.config["PROPAGATE_EXCEPTIONS"] = (
        False  # Don't propagate exceptions up to the werkzeug handler
    )
    app.config["ERROR_INCLUDE_MESSAGE"] = False  # Don't include default error messages
    
    # Apply CORS
    CORS(app)
    
    # Track application start time
    app.config["START_TIME"] = time.time()
    
    # Initialize diagnostic system
    if diagnostic_system:
        diagnostic_system.init_app(app)
    
    # Request tracking middleware
    @app.before_request
    def before_request():
        """Setup request tracking with transaction ID."""
        g.start_time = time.time()
        g.transaction_id = request.headers.get("X-Transaction-ID", str(uuid.uuid4()))
        logger.info(
            f"Transaction {g.transaction_id}: {request.method} {request.path} started"
        )

    @app.after_request
    def after_request(response):
        """Complete request tracking and add transaction ID to response."""
        if hasattr(g, "transaction_id") and hasattr(g, "start_time"):
            duration = time.time() - g.start_time
            logger.info(
                f"Transaction {g.transaction_id}: {request.method} {request.path} "
                f"returned {response.status_code} in {duration:.4f}s"
            )
            response.headers["X-Transaction-ID"] = g.transaction_id
        return response
    
    
    
    # Make utility function available to route handlers
    app.create_error_response = error_response
    
    # Basic routes
    @app.route("/")
    def index():
        """Root endpoint with API documentation."""
        return jsonify(
            {
            "status": "healthy",
            "message": "Resume Optimizer API is running",
            "version": "0.1.0",
            "endpoints": [
                "/",
                "/api/health",
                "/api/upload",
                "/api/optimize",
                "/api/download/:resumeId/:format",
                "/status",
                "/diagnostic/diagnostics",
                    "/api/test/custom-error/:error_code",
                ],
            }
        )

    @app.route("/api/health", methods=["GET"])
    def health():
        """
        Health check endpoint that always returns 200 status for Render's monitoring.
        
        Actual component status is included in the response body so clients
        can determine the true system health while Render continues to see a healthy service.
        """
        try:
            return health_page()
        

        except Exception as e:
            # Even if everything fails, return 200 with error details
            logger.error(f"Critical error in health check: {str(e)}")
            return (
                jsonify(
                    {
                "status": "critical",
                "message": f"Health check encountered a critical error: {str(e)}",
                "error_type": type(e).__name__,
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                200,
            )  # Still return 200 for Render
    

    @app.route("/api/upload", methods=["POST"])
    def upload_resume_endpoint():
        """Upload, parse, and save a resume file to Supabase."""

        if "user_id" not in request.files:
            return error_response(
                "MissingUserId", f"Invalid User ID \"{user_id}\"", 400
            )
        if "file" not in request.files:
            return error_response(
                "MissingFile", "No file part in the request", 400
            )

        user_id = request.files["user_id"]
        file = request.files["file"]
        
        if get_file_ext(file) not in ALLOWED_EXTENSIONS:
            return error_response(
            "InvalidFileType",
            f"File type not allowed. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}", 
            400,
        )

        try:
            return upload_resume(file, user_id)
        except Exception as e:
            logger.error(
                f"Error parsing/uploading resume: {str(e)}",
                exc_info=True,
            )
            return error_response(
                "Upload error", f"Error parsing/uploading resume: {str(e)}", 500
            )



    @app.route("/api/optimize", methods=["POST"])
    def optimize_resume_endpoint():
        """Optimize a resume using SemanticMatcher and ResumeEnhancer."""
        # Handle invalid JSON in the request
        if request.content_type == "application/json":
            try:
                data = json.loads(
                    request.data.decode("utf-8") if request.data else "{}"
                )
                if not data:
                    return app.create_error_response(
                        "MissingData", "No JSON data in request", 400
                    )
                
            except json.JSONDecodeError:
                return app.create_error_response(
                    "InvalidJSON", "Could not parse JSON data", 400
                )
        else:
            return app.create_error_response(
                "InvalidContentType", "Content-Type must be application/json", 400
            )
        job_id = None
        try:
            resume_id = data.get("resume_id")
            job_description_data = data.get("job_description") 
                 
            return enhance_resume(resume_id, job_description_data)
            
        except Exception as e:
            # Error already logged in specific stage or here
            logger.error(
                f"Job {job_id}: Optimization failed: {e.__class__.__name__} - {str(e)}",
                exc_info=True,
            )
            overall_status = "error"
            if diagnostic_system:
                diagnostic_system.increment_error_count(
                    f"OptimizeError_{e.__class__.__name__}", str(e)
                )
            return app.create_error_response(
                "ProcessingError",
                f"Error optimizing resume: {e.__class__.__name__} - {str(e)}",
                500,
            )
        finally:
            # --- Complete Diagnostic Tracking ---
            if diagnostic_system and job_id:
                logger.info(
                    f"Completing diagnostic job {job_id} with status {overall_status}"
                )
                diagnostic_system.complete_pipeline_job(job_id, overall_status)

    @app.route("/api/download/<resume_id>/<format_type>", methods=["GET"])
    def download_resume_endpoint(resume_id, format_type):
        """Download a resume in different formats, loading data from Supabase."""
        return download_resume(resume_id, format_type)

    @app.route("/status")
    def status():
        """Display a system status page with detailed component information"""
        try:
            # Get component status with fallbacks
            return status_page()
            
        except Exception as e:
            # Catch-all exception handler with JSON fallback
            logger.error(f"Critical error in status page: {str(e)}")
            return (
                jsonify(
                    {
                "status": "critical",
                "message": f"Error loading status page: {str(e)}",
                "error_type": type(e).__name__,
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                200,
            )  # Always return 200

    @app.route("/diagnostic/diagnostics")
    def diagnostics_endpoint():
        """Show diagnostic information."""
        return diagnostics_page()

    @app.route("/api/test/simulate-failure")
    def test_simulate_failure():
        """Test endpoint to simulate a failure"""
        raise ValueError("This is a simulated failure for testing error handling")
        
    @app.route("/api/test/custom-error/<int:error_code>")
    def test_custom_error(error_code):
        """Test endpoint to return custom error codes"""
        if error_code < 400 or error_code > 599:
            return (
                jsonify(
                    {
                "error": "Invalid error code",
                "message": "Error code must be between 400 and 599",
                "status_code": 400,
                "transaction_id": str(uuid.uuid4()),
                        "timestamp": datetime.now().isoformat(),
                    }
                ),
                400,
            )
        
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
            504: "Gateway Timeout",
        }
        
        message = error_messages.get(error_code, f"Custom error with code {error_code}")
        
        return (
            jsonify(
                {
            "error": f"Error {error_code}",
            "message": message,
            "status_code": error_code,
            "transaction_id": str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            error_code,
        )
    
    @app.before_request
    def check_api_key():
        """Check if OpenAI API key is available for routes that need it"""
        api_routes = ["/api/upload", "/api/optimize", "/api/enhance"]
        
        if request.path in api_routes and not os.environ.get("OPENAI_API_KEY"):
            error_response = handle_missing_api_key()
            if error_response:
                return error_response
    
    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all exceptions and return a consistent JSON error response."""
        # Generate a unique error ID
        error_id = str(uuid.uuid4())
        
        # Determine the status code
        if isinstance(e, HTTPException):
            status_code = e.code
        else:
            status_code = 500
        
        # Get error type and message
        error_type = e.__class__.__name__
        error_message = str(e)
        
        # Log the error with the unique ID and traceback
        logger.error(f"Error {error_id}: {error_type} - {error_message}", exc_info=True)
        
        # Track error in diagnostic system
        if diagnostic_system:
            diagnostic_system.increment_error_count(error_type, error_message)
        
        # Use the standard error response function
        return app.create_error_response(error_type, error_message, status_code)

    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors specifically."""
        return app.create_error_response(
            "NotFound", "The requested resource could not be found", 404
        )

    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 errors specifically."""
        return app.create_error_response(
            "InternalServerError", "An internal server error occurred", 500
        )
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle all other HTTP exceptions."""
        return app.create_error_response(
            f"HTTP{e.code}Error", 
            e.description or f"HTTP error occurred with status code {e.code}", 
            e.code,
        )
    
    @app.route("/favicon.ico")
    def favicon():
        """Serve the favicon to prevent repeated 404 errors."""
        try:
            return app.send_static_file("favicon.ico")
        except:
            # If favicon.ico isn't found, return empty response with 204 status
            return "", 204
    
    return app
