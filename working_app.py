"""
Working Resume Optimizer Flask App with proper port handling
"""

import logging
from datetime import datetime
import uuid
import json
import time
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask, jsonify, request, g, current_app
from flask_cors import CORS

# Import the advanced modules
from Endpoints.diagnostics import diagnostics_page
from Endpoints.health import health_page
from Endpoints.status import status_page

from Pipeline.job_tracking import create_optimization_job, update_optimization_job
from Pipeline.resume_uploader import parse_and_upload_resume
from Pipeline.optimizer import enhance_resume
from Pipeline.resume_loading import OUTPUT_FOLDER, UPLOAD_FOLDER, download_resume, get_file_ext


from Services.database import get_db
from Services.diagnostic_system import get_diagnostic_system
from Services.errors import error_response

from resume_latex_generator.resume_generator import create_pdf_generator
from pdf_generator import ResumePDFGenerator
from classic_template_adapter import generate_resume_latex


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}

# Ensure 'os' is imported before it's used for makedirs
import os

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
    
    # Initialize PDF Generator
    try:
        pdf_gen = create_pdf_generator()
        app.config['pdf_generator'] = pdf_gen
        env_check_result = pdf_gen.check_environment()
        logger.info(f"PDF Generator Environment Check: {env_check_result}")
    except Exception as e:
        logger.error(f"Failed to initialize PDF Generator: {e}", exc_info=True)
        # Optionally, you might want to set a flag in app.config or handle this error more gracefully
        # For now, just logging the error.
    
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
        current_app.logger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        current_app.logger.info("!!!!!! ROOT ENDPOINT '/' WAS HIT !!!!!!")
        current_app.logger.info("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
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
        logger.info(f"Files: {request.form.keys()}")

        if "user_id" not in request.form.keys():
            return error_response(
                "MissingUserId", f"No User ID provided in the request", 400
            )
        if "file" not in request.files:
            return error_response(
                "MissingFile", "No file in the request", 400
            )

        user_id = request.form["user_id"]
        file = request.files["file"]

        try:
            return parse_and_upload_resume(file, user_id)
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

        if "resume_id" not in request.form.keys():
            return error_response(
                "MissingResumeId", f"No Resume ID provided in the request", 400
            )
        if "user_id" not in request.form.keys():
            return error_response(
                "MissingUserId", f"No User ID provided in the request", 400
            )
        if "job_description" not in request.form.keys():
            return error_response(
                "MissingJobDescription", f"No job description provided", 400
            )
        
        try:
            resume_id = request.form["resume_id"]
            user_id = request.form["user_id"]
            job_description = request.form["job_description"]
            
            # Create optimization task in supabase (for tracking purposes)
            job_id = create_optimization_job(resume_id, user_id, job_description)

            return enhance_resume(job_id, resume_id, user_id, job_description)
        
        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Error enhancing resume: {error_msg}",
                exc_info=True,
            )
            update_optimization_job(job_id, {
                "status": "Error",
                "error_message": error_msg,
            })
            return error_response(
                "Optimization error", 
                f"""Error optimizing resume: {error_msg}. Resume ID:{resume_id}""",
                500)

    @app.route("/api/download/<resume_id>/pdf", methods=["GET"])
    def download_resume_pdf(resume_id):
        db = get_db()
        logger.info(f"Attempting to generate PDF for resume_id: {resume_id}")

        # Step 1: Load main resume data (resume_data_to_use)
        # Assuming this comes from the 'resumes' table as per "done for JSON format"
        try:
            resp_main_data = db.table("resumes").select("data").eq("id", resume_id).execute()
            if not resp_main_data.data:
                logger.warning(f"No resume data found in 'resumes' table for resume_id: {resume_id}")
                return app.create_error_response("NotFound", "Resume data not found", 404)
            
            resume_data_to_use = resp_main_data.data[0].get("data")
            if not resume_data_to_use: 
                logger.error(f"'data' field is empty for resume_id: {resume_id} in 'resumes' table.")
                return app.create_error_response("ProcessError", "Resume content is empty", 400)
            logger.info(f"Successfully loaded resume_data_to_use for {resume_id}")

        except Exception as e_load:
            logger.exception(f"Error loading resume data for {resume_id} from 'resumes' table: {e_load}")
            return app.create_error_response("DatabaseError", "Failed to load resume data", 500)

        try:
            logger.info(f"Generating PDF via LaTeX for resume {resume_id}")
            # 1. Build LaTeX content from resume data using dynamic template logic
            latex_content = generate_resume_latex(resume_data_to_use)
            
            # 2. Compile the LaTeX content to PDF
            pdf_generator = ResumePDFGenerator()
            
            output_dir = "/tmp/resume_pdfs" 
            os.makedirs(output_dir, exist_ok=True) 
            output_path = os.path.join(output_dir, f"enhanced_resume_{resume_id}.pdf")

            # generate_pdf takes resume_data_to_use and output_path as per user's specific instructions
            result = pdf_generator.generate_pdf(resume_data_to_use, output_path) 

            if not result["success"]:
                error_msg = result.get("error", "Unknown LaTeX compilation error")
                detailed_error = result.get("details", "") 
                logger.error(f"PDF generation failed for {resume_id}: {error_msg}. Details: {detailed_error}")
                return app.create_error_response("PdfGenerationError", "Error generating PDF (see logs)", 500)
            
            logger.info(f"PDF generated for resume {resume_id} at {output_path}")

            # 3. Upload PDF to Supabase Storage
            user_id_for_storage = None
            try:
                resp_user_id = db.table("resumes_new").select("user_id").eq("id", resume_id).execute()
                if resp_user_id.data:
                    user_id_for_storage = resp_user_id.data[0]["user_id"]
                else:
                    logger.warning(f"No user_id found in 'resumes_new' for resume_id {resume_id}. Using 'unknown-user'.")
            except Exception as e_user_fetch:
                logger.warning(f"Could not fetch user_id from 'resumes_new' for resume {resume_id}: {e_user_fetch}. Using 'unknown-user'.")
            
            storage_path_prefix = f"{user_id_for_storage or 'unknown-user'}/{resume_id}"
            pdf_filename = f"enhanced_resume_{resume_id}.pdf"
            storage_path = f"{storage_path_prefix}/{pdf_filename}"
            
            bucket_name = "resume-pdfs"
            bucket = db.storage.from_(bucket_name)
            
            if not os.path.exists(output_path):
                logger.error(f"Generated PDF file not found at {output_path} for resume {resume_id}")
                return app.create_error_response("PdfGenerationError", "Generated PDF file missing", 500)

            # Using user's specified upload call structure
            upload_response = bucket.upload(storage_path, output_path).execute()

            # Using user's specified error checking for upload_response
            if hasattr(upload_response, 'error') and upload_response.error is not None:
                error_details = str(upload_response.error)
                logger.error(f"Supabase upload error for {resume_id}: {error_details}")
                return app.create_error_response("StorageUploadError", f"Failed to upload PDF to storage: {error_details}", 500)
            
            # Fallback check for other types of errors if the above doesn't catch it
            if hasattr(upload_response, 'status_code') and upload_response.status_code >= 400:
                logger.error(f"Supabase upload error for {resume_id}. Status: {upload_response.status_code}, Response: {getattr(upload_response, 'text', 'No text')}")
                return app.create_error_response("StorageUploadError", "Failed to upload PDF to storage", 500)

            logger.info(f"PDF for resume {resume_id} uploaded to Supabase at {storage_path}")
            
            # 4. Generate a signed URL for the uploaded PDF
            expires_in_seconds = 60 * 60 * 24 # 24 hours
            signed_url = None
            try:
                # Using user's specified signed URL call structure and attribute checking
                signed_response_after_execute = bucket.create_signed_url(storage_path, expires_in=expires_in_seconds).execute()

                if hasattr(signed_response_after_execute, "link"):
                    signed_url = signed_response_after_execute.link
                elif hasattr(signed_response_after_execute, "data") and signed_response_after_execute.data and isinstance(signed_response_after_execute.data, dict):
                    signed_url = signed_response_after_execute.data.get("signedURL") or signed_response_after_execute.data.get("publicURL")
                elif isinstance(signed_response_after_execute, dict) and "signedURL" in signed_response_after_execute: # Common v2 direct dict
                     signed_url = signed_response_after_execute["signedURL"]
                else:
                    signed_url = getattr(signed_response_after_execute, "url", None)

                if not signed_url:
                    logger.error(f"Failed to extract signed URL for {resume_id}. Response from execute: {signed_response_after_execute}")
                    return app.create_error_response("StorageError", "Failed to generate signed URL", 500)

            except Exception as e_url:
                logger.exception(f"Error generating signed URL for {resume_id}: {e_url}")
                return app.create_error_response("StorageError", f"Error generating signed URL: {str(e_url)}", 500)

            logger.info(f"Generated signed URL for resume PDF: {signed_url}")
            
            try:
                if os.path.exists(output_path):
                    os.remove(output_path)
                    logger.info(f"Cleaned up temporary PDF file: {output_path}")
            except Exception as e_clean:
                logger.warning(f"Could not clean up temporary PDF file {output_path}: {e_clean}")
            
            return jsonify({"status": "success", "signedUrl": signed_url}), 200

        except Exception as e:
            logger.exception(f"Unexpected error generating PDF for {resume_id}: {e}")
            return app.create_error_response("PdfGenerationError", f"Error generating PDF: {str(e)}", 500)

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

# Create the Flask app instance at the module level for Gunicorn and other WSGI servers
app = create_app()

if __name__ == "__main__":
    # The 'app' instance is already created and configured by the module-level call.
    # We can use it directly here for local development runs.
    # The PORT environment variable is standard for web apps.
    # Default to 5000 if PORT is not set, suitable for local development.
    port = int(os.environ.get("PORT", 5000)) 
    # For local development, you might want to enable debug mode:
    # app.run(host="0.0.0.0", port=port, debug=True)
    # For production-like testing without Gunicorn, run without debug mode:
    app.run(host="0.0.0.0", port=port)
