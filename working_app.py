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
# We'll use the dynamic LaTeX generator directly
pdf_service_factory = create_pdf_generator


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
        pdf_gen = create_pdf_generator(no_auto_size=True)
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

        # Step 1: Load main resume data (resume_data_to_use) and user_id (from resume_record)
        # This part is assumed to be similar to previous logic, adapted for the new needs.
        # The user's new block expects 'resume_data' and 'resume_record["user_id"]'.
        try:
            # Fetching both 'data' and 'user_id' from the 'resumes' table now,
            # as 'resume_record' is used in the new block.
            response = db.table("resumes").select("data, user_id").eq("id", resume_id).maybe_single().execute()

            if not response.data:
                logger.warning(f"No resume data found in 'resumes' table for resume_id: {resume_id}")
                return app.create_error_response("NotFound", "Resume data not found", 404)
            
            resume_record = response.data # This is the dictionary containing 'data' and 'user_id'
            resume_data = resume_record.get("data") # Get the nested JSON data

            if not resume_data: 
                logger.error(f"'data' field is empty for resume_id: {resume_id} in 'resumes' table.")
                return app.create_error_response("ProcessError", "Resume content is empty", 400)
            
            if not resume_record.get("user_id"):
                 logger.warning(f"'user_id' field is missing for resume_id: {resume_id} in 'resumes' table. Upload might use default path.")
            
            logger.info(f"Successfully loaded resume_data and resume_record for {resume_id}")

        except Exception as e_load:
            logger.exception(f"Error loading resume data for {resume_id} from 'resumes' table: {e_load}")
            return app.create_error_response("DatabaseError", "Failed to load resume data", 500)

        # --- USER'S PROVIDED BLOCK STARTS HERE ---
        try:
            # 1️⃣ Generate PDF via your dynamic LaTeX code
            latex_service = pdf_service_factory()
            
            # Define a temporary path for the generated PDF
            output_dir = "/tmp/resume_pdfs"
            os.makedirs(output_dir, exist_ok=True)
            temp_pdf_path = os.path.join(output_dir, f"temp_resume_{resume_id}_{uuid.uuid4().hex[:8]}.pdf")
            
            current_app.logger.info(f"Attempting to generate PDF at: {temp_pdf_path}")
            
            # Call the correct method: generate_pdf(self, resume_data, output_path_target_pdf)
            # It returns the output_path_target_pdf on success, or None/raises error on failure.
            # We will wrap this in a try-except to catch errors from generate_pdf itself.
            generated_pdf_output_path = None
            pdf_generation_error_detail = "Unknown PDF generation error"
            try:
                # Ensure resume_data is passed as the first argument after self
                generated_pdf_output_path = latex_service.generate_pdf(resume_data, temp_pdf_path)
            except Exception as e_gen:
                pdf_generation_error_detail = str(e_gen)
                current_app.logger.error(f"Error during latex_service.generate_pdf: {pdf_generation_error_detail}", exc_info=True)
                # generated_pdf_output_path remains None

            if not generated_pdf_output_path or not os.path.exists(generated_pdf_output_path):
                current_app.logger.error(f"PDF gen failed. Method did not return a valid path or file does not exist. Error detail: {pdf_generation_error_detail}")
                # Attempt to clean up if a file was partially created but is invalid
                if generated_pdf_output_path and os.path.exists(generated_pdf_output_path):
                    try: os.remove(generated_pdf_output_path) 
                    except: pass
                elif os.path.exists(temp_pdf_path): # Check original temp path too
                    try: os.remove(temp_pdf_path)
                    except: pass
                return jsonify({"success": False, "error": "PDF generation error", "details": pdf_generation_error_detail}), 500
            
            current_app.logger.info(f"PDF successfully generated at: {generated_pdf_output_path}")

            # 2️⃣ Upload to Supabase - Re-integrating direct Supabase client logic
            db_client_for_upload = get_db() # Ensure db client is available
            user_id = resume_record.get("user_id")
            if not user_id:
                current_app.logger.error(f"User ID missing in resume_record for resume {resume_id} during Supabase upload.")
                if os.path.exists(generated_pdf_output_path):
                    try: os.remove(generated_pdf_output_path)
                    except Exception as e_clean: current_app.logger.warning(f"Could not cleanup {generated_pdf_output_path}: {e_clean}")
                return jsonify({"success": False, "error": "User ID missing for upload"}), 500

            storage_path_prefix = f"{user_id}/{resume_id}"
            pdf_filename_on_storage = f"enhanced_resume_{resume_id}_{uuid.uuid4().hex[:8]}.pdf" # Unique filename for storage
            storage_path = f"{storage_path_prefix}/{pdf_filename_on_storage}"
            bucket_name = "resume-pdfs"
            bucket = db_client_for_upload.storage.from_(bucket_name)

            current_app.logger.info(f"Uploading {generated_pdf_output_path} to Supabase at {storage_path}")
            upload_response_obj = None # To store the response from execute()
            upload_error_details = "Unknown upload error"

            try:
                # Using with open for file handling is safer
                with open(generated_pdf_output_path, 'rb') as f:
                    # Standard Supabase upload, .execute() is for query builder, not directly on upload for supabase-py v1/v2 style here.
                    # For supabase-py v2, the structure is typically bucket.upload(...) then check response.
                    # The user's prior working_app.py had bucket.upload(...).execute(), let's align with that if it was working
                    # However, common usage is often direct result or an execute on a builder. Reverting to a more common direct upload check.
                    raw_upload_response = bucket.upload(
                        path=storage_path,
                        file=f,
                        file_options={"content-type": "application/pdf", "upsert": "true"} # Upsert true to overwrite if same name
                    )
                # Check response from Supabase. For supabase-py v2, this might be a Response object or raise an APIError.
                # A common pattern is to check for a status code or error attribute if it doesn't raise.
                # Given previous logs, let's assume a direct response object for now that might have .error
                # If raw_upload_response is the executed response:
                upload_response_obj = raw_upload_response # If it doesn't .execute(), this is the response.
                                                        # If .execute() was indeed needed and part of a builder, this would change.

                # Check for error based on common Supabase client library patterns (v1 or v2)
                # supabase-py v2 might raise an APIError or return a Response object with error details
                # supabase-py v1 might return a dict with an error key or raise
                if hasattr(upload_response_obj, 'error') and upload_response_obj.error:
                    upload_error_details = str(upload_response_obj.error)
                    current_app.logger.error(f"Supabase upload error (direct response): {upload_error_details} for {storage_path}")
                    raise Exception(f"Supabase upload failed: {upload_error_details}") # Trigger general catch
                
                # If it's a requests.Response like object from a successful HTTP call (common in v2 without APIError)
                if hasattr(upload_response_obj, 'status_code') and upload_response_obj.status_code >= 400:
                    upload_error_details = upload_response_obj.text if hasattr(upload_response_obj, 'text') else f"HTTP status {upload_response_obj.status_code}"
                    current_app.logger.error(f"Supabase upload HTTP error: {upload_error_details} for {storage_path}")
                    raise Exception(f"Supabase upload failed with HTTP status: {upload_error_details}")
                
                # If no error attribute and status code is fine, or if it raises APIError on failure (which is caught below)
                current_app.logger.info(f"Successfully uploaded to {storage_path}")

            except Exception as e_upload:
                current_app.logger.error(f"Supabase upload failed for {storage_path}: {str(e_upload)}", exc_info=True)
                if os.path.exists(generated_pdf_output_path):
                    try: os.remove(generated_pdf_output_path)
                    except Exception as e_clean: current_app.logger.warning(f"Could not cleanup {generated_pdf_output_path}: {e_clean}")
                return jsonify({"success": False, "error": "Upload error", "details": str(e_upload)}), 500

            # 3️⃣ Generate a signed URL for the uploaded PDF
            signed_url = None
            try:
                expires_in_seconds = 60 * 60 * 24 # 24 hours
                # For supabase-py v2, create_signed_url(...).execute() is not typical.
                # It's usually bucket.create_signed_url(path, expires_in) directly returns the URL or raises.
                # Let's try the direct call first as it's cleaner for v2.
                signed_url_data = bucket.create_signed_url(storage_path, expires_in=expires_in_seconds)
                
                # The response structure for signed URL varies between supabase-py v1 and v2.
                # v2 often returns a dict with 'signedURL' or might have it nested in response.data.
                if isinstance(signed_url_data, dict) and signed_url_data.get('signedURL'):
                    signed_url = signed_url_data['signedURL']
                elif isinstance(signed_url_data, str): # some versions might return string directly
                    signed_url = signed_url_data
                # Add more checks if necessary based on your specific supabase-py version's return format
                else:
                    current_app.logger.warning(f"Could not directly extract signed URL. Response was: {signed_url_data}")
                    # Fallback to a common older pattern if using .execute() was indeed how it worked before
                    try:
                        signed_response_executed = db_client_for_upload.storage.from_(bucket_name).create_signed_url(storage_path, expires_in_seconds).execute()
                        if hasattr(signed_response_executed, "link"):
                            signed_url = signed_response_executed.link
                        elif hasattr(signed_response_executed, "data") and signed_response_executed.data and isinstance(signed_response_executed.data, dict):
                            signed_url = signed_response_executed.data.get("signedURL") or signed_response_executed.data.get("publicURL")
                    except Exception as e_fallback_url:
                        current_app.logger.error(f"Fallback signed URL generation with .execute() also failed: {e_fallback_url}")
                
                if not signed_url:
                    current_app.logger.error(f"Failed to generate signed URL for {storage_path}. Last attempt response: {signed_url_data}")
                    raise Exception("Failed to obtain signed URL")

            except Exception as e_url_gen:
                current_app.logger.error(f"Error generating signed URL for {storage_path}: {str(e_url_gen)}", exc_info=True)
                # No need to clean up remote file here, but local should be gone if upload was successful before this point
                return jsonify({"success": False, "error": "Signed URL generation error", "details": str(e_url_gen)}), 500
            
            current_app.logger.info(f"PDF uploaded successfully. Signed URL: {signed_url}")
            
            # Clean up local PDF file AFTER successful upload and URL generation
            if os.path.exists(generated_pdf_output_path):
                try:
                    os.remove(generated_pdf_output_path)
                    current_app.logger.info(f"Successfully cleaned up temporary file: {generated_pdf_output_path}")
                except Exception as e_clean:
                    current_app.logger.warning(f"Could not clean up temporary file {generated_pdf_output_path}: {e_clean}")
            
            return jsonify({"success": True, "resume_id": resume_id, "pdf_url": signed_url}), 200

        except Exception as e:
            current_app.logger.exception(f"Unexpected PDF pipeline error for {resume_id}")
            return jsonify({"success": False, "error": "Server error"}), 500
        # --- USER'S PROVIDED BLOCK ENDS HERE ---

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
