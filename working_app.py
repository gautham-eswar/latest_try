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

    @app.route("/api/download/<resume_id>/<format_type>", methods=["GET"])
    def download_resume_endpoint(resume_id, format_type):
        """Download a resume in different formats, loading data from Supabase."""
        if format_type.lower() == 'pdf':
            output_path = None # Initialize for cleanup in finally block
            try:
                db_client = get_db()
                if not db_client:
                    current_app.logger.error(f"Supabase client not available for PDF generation of {resume_id}.")
                    return error_response("DatabaseError", "Database client not available.", 500)

                # 1. Fetch user_id associated with the resume
                user_id_data = db_client.table("resumes").select("user_id").eq("id", resume_id).maybe_single().execute()
                if not user_id_data.data or not user_id_data.data.get("user_id"):
                    current_app.logger.error(f"User ID not found for resume_id {resume_id}.")
                    return error_response("NotFound", f"User ID not found for resume ID {resume_id}", 404)
                user_id = user_id_data.data["user_id"]
                current_app.logger.info(f"Fetched user_id '{user_id}' for resume_id '{resume_id}'.")

                # 2. Fetch resume data (try enhanced_resumes, then resumes)
                resume_data = None
                response = db_client.table("enhanced_resumes").select("*").eq("resume_id", resume_id).maybe_single().execute()
                if response.data:
                    resume_data = response.data
                    current_app.logger.info(f"Fetched data for {resume_id} from enhanced_resumes.")
                else:
                    response = db_client.table("resumes").select("*").eq("id", resume_id).maybe_single().execute()
                    if response.data:
                        resume_data = response.data
                        current_app.logger.info(f"Fetched data for {resume_id} from resumes table.")
                
                if not resume_data:
                    current_app.logger.error(f"No resume data found for {resume_id} in enhanced_resumes or resumes table.")
                    return error_response("NotFound", f"Resume data not found for ID {resume_id}", 404)
                current_app.logger.info(f"Fetched resume data for {resume_id}: {list(resume_data.keys())}")

                # 3. Flatten skills if necessary
                if "Skills" in resume_data and isinstance(resume_data["Skills"], dict):
                    flattened_skills = []
                    for category, skills_list in resume_data["Skills"].items():
                        if isinstance(skills_list, list):
                            for skill in skills_list:
                                if skill not in flattened_skills:
                                    flattened_skills.append(skill)
                    resume_data["Skills"] = flattened_skills
                    current_app.logger.info(f"Flattened skills for LaTeX rendering for resume {resume_id}.")
                elif "Skills" in resume_data and isinstance(resume_data["Skills"], list):
                    resume_data["Skills"] = list(set(resume_data["Skills"])) # Ensure uniqueness
                    current_app.logger.info(f"Ensured skills list uniqueness for resume {resume_id}.")

                # 4. Get PDF generator and generate PDF
                pdf_generator = current_app.config.get('pdf_generator')
                if not pdf_generator:
                    current_app.logger.error(f"PDF generator not available in app config for {resume_id}.")
                    return error_response("ServerError", "PDF generator not configured.", 500)

                output_filename = f"enhanced_resume_{resume_id}.pdf"
                output_path = os.path.join(OUTPUT_FOLDER, output_filename) # OUTPUT_FOLDER should be defined globally
                os.makedirs(OUTPUT_FOLDER, exist_ok=True) # Ensure output folder exists

                current_app.logger.info(f"Calling PDF generator for resume {resume_id} to output at {output_path}")
                generation_success = pdf_generator.generate_pdf(resume_data, output_path)

                if not generation_success or not os.path.exists(output_path):
                    current_app.logger.error(f"PDF generation failed for {resume_id}. Output file not found at {output_path}.")
                    return error_response("PDFGenerationError", "Failed to generate PDF document.", 500)
                current_app.logger.info(f"PDF generated at path: {output_path}")

                # 5. Upload to Supabase
                upload_path = f"{user_id}/{resume_id}/{output_filename}"
                current_app.logger.info(f"Uploading {output_path} to Supabase bucket 'resume-pdfs' at path {upload_path}")
                
                with open(output_path, 'rb') as f:
                    # The Supabase client's upload method throws an exception on failure.
                    db_client.storage.from_("resume-pdfs").upload(
                        path=upload_path, 
                        file=f, 
                        file_options={"content-type": "application/pdf", "upsert": "true"}
                    )
                current_app.logger.info(f"Successfully uploaded {output_filename} to Supabase at {upload_path}.")

                # 6. Get signed URL
                signed_url_response = db_client.storage.from_("resume-pdfs").create_signed_url(upload_path, 3600) # 1 hour expiry
                pdf_url = signed_url_response.get('signedURL') # Correct key based on Supabase response
                
                if not pdf_url:
                    current_app.logger.error(f"Failed to create signed URL for {upload_path}. Response: {signed_url_response}")
                    return error_response("StorageError", "Failed to create signed URL for PDF.", 500)
                current_app.logger.info(f"Generated signed URL for {upload_path}: {pdf_url}")

                return jsonify({
                    "success": True,
                    "resume_id": resume_id,
                    "pdf_url": pdf_url
                })

            except Exception as e:
                current_app.logger.error(f"PDF generation/upload failed for {resume_id}: {str(e)}", exc_info=True)
                # Ensure the error message from e is passed to the client for better debugging
                return error_response("ServerError", f"An unexpected error occurred during PDF processing: {str(e)}", 500)
            finally:
                # Cleanup local PDF file
                if output_path and os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        current_app.logger.info(f"Cleaned up local PDF file: {output_path}")
                    except Exception as e:
                        current_app.logger.error(f"Error cleaning up local PDF file {output_path}: {str(e)}", exc_info=True)
        
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

import os

if __name__ == "__main__":
    app = create_app() # Ensure create_app has been called to initialize the 'app' instance
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
