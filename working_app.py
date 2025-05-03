"""
Working Resume Optimizer Flask App with proper port handling
"""

import os
import sys
import logging
from datetime import datetime, timedelta
import uuid
import platform
import json
import psutil
from pathlib import Path
import time
import requests
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.proxy_fix import ProxyFix
from postgrest import APIError as PostgrestAPIError  # Import Supabase error type

from flask import Flask, jsonify, request, render_template, g, Response, current_app
from flask_cors import CORS
from werkzeug.utils import secure_filename

# Import the advanced modules
from Endpoints.status import get_status
from Pipeline.keyword_extraction import extract_keywords
from Pipeline.latex_generation import generate_latex_resume
from Pipeline.resume_handling import download_resume, upload_resume
from Pipeline.resume_parsing import extract_text_from_file, parse_resume
from Services.database import FallbackDatabase, get_db
from Endpoints.health import health_analysis
from Services.openai_interface import OPENAI_API_BASE, OPENAI_API_KEY, call_openai_api
from Services.utils import format_size, format_uptime, get_component_status, get_uptime, START_TIME
from Services.diagnostic_system import get_diagnostic_system
from embeddings import SemanticMatcher
from enhancer import ResumeEnhancer


# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Constants
ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


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
    
    # Utility function for creating error responses
    def create_error_response(error_type, message, status_code):
        """Create a standardized error response following the error schema."""
        return (
            jsonify(
                {
            "error": error_type,
            "message": message,
            "status_code": status_code,
                    "transaction_id": getattr(g, "transaction_id", None)
                    or str(uuid.uuid4()),
                    "timestamp": datetime.now().isoformat(),
                }
            ),
            status_code,
        )
    
    # Make utility function available to route handlers
    app.create_error_response = create_error_response
    
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
        return health_analysis()

    @app.route("/api/upload", methods=["POST"])
    def upload_resume_endpoint():
        """Upload, parse, and save a resume file to Supabase."""
        if "file" not in request.files:
            return app.create_error_response(
                "MissingFile", "No file part in the request", 400
            )

        file = request.files["file"]
        return upload_resume(app, file)

    @app.route("/api/optimize", methods=["POST"])
    def optimize_resume_endpoint():
        """Optimize a resume using SemanticMatcher and ResumeEnhancer."""
        # Handle invalid JSON in the request
        if request.content_type == "application/json":
            try:
                data = json.loads(
                    request.data.decode("utf-8") if request.data else "{}"
                )
            except json.JSONDecodeError:
                return app.create_error_response(
                    "InvalidJSON", "Could not parse JSON data", 400
                )
        else:
            return app.create_error_response(
                "InvalidContentType", "Content-Type must be application/json", 400
            )
        
        job_id = None  # Initialize job_id for diagnostics
        overall_status = "error"  # Default status
        try:
            if not data:
                return app.create_error_response(
                    "MissingData", "No JSON data in request", 400
                )

            resume_id = data.get("resume_id")
            job_description_data = data.get(
                "job_description"
            )  # Expecting {"description": "..."}
            
            if not resume_id:
                return app.create_error_response(
                    "MissingParameter", "Missing: resume_id", 400
                )

            if (
                not job_description_data
                or not isinstance(job_description_data, dict)
                or "description" not in job_description_data
            ):
                return app.create_error_response(
                    "MissingParameter",
                    "Missing or invalid: job_description (must be an object with a 'description' key)",
                    400,
                )

            job_description_text = job_description_data["description"]
            if not job_description_text:
                return app.create_error_response(
                    "MissingParameter", "Job description text cannot be empty", 400
                )

            # --- Start Diagnostic Tracking ---
            if diagnostic_system:
                # Use resume_id and maybe part of job desc for job identifier
                job_desc_snippet = job_description_text[:50].replace("\n", " ") + "..."
                job_id = diagnostic_system.start_pipeline_job(
                    resume_id, "api_optimize", job_desc_snippet
                )
                if not job_id:
                    logger.warning(
                        f"Failed to start diagnostic pipeline job for resume {resume_id}"
                    )
                    job_id = None  # Ensure it's None if failed

            logger.info(
                f"Starting optimization for resume_id: {resume_id} (Job ID: {job_id})"
            )

            # --- Load Original Parsed Resume Data (from Supabase) ---
            logger.info(
                f"Loading original parsed resume {resume_id} from Supabase (table: resumes_new)..."
            )
            db = get_db()
            original_resume_data = None

            if isinstance(db, FallbackDatabase):
                logger.warning(
                    f"Using FallbackDatabase for loading resume {resume_id}."
                )
                # Attempt to load from local file as fallback (if saved by upload)
                resume_file_path = os.path.join(
                    app.config["UPLOAD_FOLDER"], f"{resume_id}.json"
                )
                if os.path.exists(resume_file_path):
                    with open(resume_file_path, "r", encoding="utf-8") as f:
                        original_resume_data = json.load(f)
                    logger.info(f"Loaded resume {resume_id} from local fallback file.")
                else:
                    logger.error(
                        f"FallbackDatabase active and local file for {resume_id} not found."
                    )
                    return app.create_error_response(
                        "NotFound", f"Resume {resume_id} not found (fallback).", 404
                    )
            else:
                # Fetch from Supabase 'resumes_new' table
                try:
                    response = (
                        db.table("resumes_new")
                        .select("parsed_data")
                        .eq("id", resume_id)
                        .limit(1)
                        .execute()
                    )
                    if response.data:
                        original_resume_data = response.data[0]["parsed_data"]
                        logger.info(
                            f"Successfully loaded resume {resume_id} from Supabase."
                        )
                    else:
                        logger.error(f"Resume {resume_id} not found in Supabase.")
                        return app.create_error_response(
                            "NotFound", f"Resume {resume_id} not found.", 404
                        )
                except PostgrestAPIError as db_e:
                    logger.error(
                        f"Error loading resume {resume_id} from Supabase (Code: {db_e.code}): {db_e.message}",
                        exc_info=True,
                    )
                    logger.error(
                        f"DB Error Details: {db_e.details} | Hint: {db_e.hint}"
                    )
                    raise Exception(
                        f"Database error loading resume ({db_e.code}): {db_e.message}"
                    )
                except Exception as db_e:
                    logger.error(
                        f"Unexpected error loading resume {resume_id} from Supabase: {db_e}",
                        exc_info=True,
                    )
                    raise  # Re-raise unexpected errors

            # Ensure we have data before proceeding
            if not original_resume_data:
                logger.error(
                    f"Failed to load original_resume_data for {resume_id} after DB/fallback checks."
                )
                return app.create_error_response(
                    "ProcessingError",
                    f"Could not load data for resume {resume_id}",
                    500,
                )

            # --- Keyword Extraction ---
            stage_name = "Keyword Extractor"
            start_time = time.time()
            keywords_data = None
            stage_status = "error"
            stage_message = "Extraction failed"
            try:
                logger.info(f"Job {job_id}: Extracting detailed keywords...")
                keywords_data = extract_keywords(job_description_text)
                kw_count = len(keywords_data.get("keywords", []))
                logger.info(
                    f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords."
                )
                stage_status = "healthy"
                stage_message = f"Extracted {kw_count} keywords"
            except Exception as e:
                logger.error(
                    f"Job {job_id}: Keyword Extraction failed: {e}", exc_info=True
                )
                stage_message = f"Extraction failed: {e.__class__.__name__}"
                # Re-raise to stop processing
                raise
            finally:
                duration = time.time() - start_time
                if diagnostic_system and job_id:
                    diagnostic_system.record_pipeline_stage(
                        job_id, stage_name, stage_status, duration, stage_message
                    )

            # --- Semantic Matching ---
            stage_name = "Semantic Matcher"
            start_time = time.time()
            match_results = None
            matches_by_bullet = {}
            stage_status = "error"
            stage_message = "Matching failed"
            try:
                logger.info(f"Job {job_id}: Initializing SemanticMatcher...")
                matcher = SemanticMatcher()
                logger.info(f"Job {job_id}: Running semantic matching process...")
                match_results = matcher.process_keywords_and_resume(
                    keywords_data, original_resume_data
                )
                matches_by_bullet = match_results.get("matches_by_bullet", {})
                bullets_matched = len(matches_by_bullet)
                logger.info(
                    f"Job {job_id}: Semantic matching complete. Found matches for {bullets_matched} bullets."
                )
                stage_status = "healthy"
                stage_message = f"Matched {bullets_matched} bullets"
            except Exception as e:
                logger.error(
                    f"Job {job_id}: Semantic Matching failed: {e}", exc_info=True
                )
                stage_message = f"Matching failed: {e.__class__.__name__}"
                raise
            finally:
                duration = time.time() - start_time
                if diagnostic_system and job_id:
                    diagnostic_system.record_pipeline_stage(
                        job_id, stage_name, stage_status, duration, stage_message
                    )

            # --- Resume Enhancement ---
            stage_name = "Resume Enhancer"
            start_time = time.time()
            enhanced_resume_data = None
            modifications = []
            stage_status = "error"
            stage_message = "Enhancement failed"
            try:
                logger.info(f"Job {job_id}: Initializing ResumeEnhancer...")
                enhancer = ResumeEnhancer()
                logger.info(f"Job {job_id}: Running resume enhancement process...")
                enhanced_resume_data, modifications = enhancer.enhance_resume(
                    original_resume_data, matches_by_bullet
                )
                mods_count = len(modifications)
                logger.info(
                    f"Job {job_id}: Resume enhancement complete. {mods_count} modifications made."
                )
                stage_status = "healthy"
                stage_message = f"Made {mods_count} modifications"
            except Exception as e:
                logger.error(
                    f"Job {job_id}: Resume Enhancement failed: {e}", exc_info=True
                )
                stage_message = f"Enhancement failed: {e.__class__.__name__}"
                raise
            finally:
                duration = time.time() - start_time
                if diagnostic_system and job_id:
                    diagnostic_system.record_pipeline_stage(
                        job_id, stage_name, stage_status, duration, stage_message
                    )

            # --- Prepare Analysis Data ---
            # Construct a basic analysis object (can be refined)
            analysis_data = {
                "matched_keywords_by_bullet": matches_by_bullet,
                "enhancement_modifications": modifications,
                "statistics": match_results.get("statistics", {}),
                "job_keywords_used": keywords_data.get(
                    "keywords", []
                ),  # Include the keywords extracted
            }
            logger.info(f"Job {job_id}: Prepared analysis data.")

            # --- Save Enhanced Resume & Analysis (to Supabase) ---
            logger.info(
                f"Attempting to save/update enhanced resume {resume_id} in Supabase table enhanced_resumes..."
            )
            if isinstance(db, FallbackDatabase):
                logger.warning(
                    f"Using FallbackDatabase for saving enhanced resume {resume_id}. Data will not be persisted."
                )
                # Optionally save locally if using fallback
                output_file_path = os.path.join(
                    app.config["OUTPUT_FOLDER"], f"{resume_id}_enhanced.json"
                )
                with open(output_file_path, "w", encoding="utf-8") as f:
                    json.dump(
                        {
                            "enhanced_data": enhanced_resume_data,
                            "analysis_data": analysis_data,
                        },
                        f,
                        indent=2,
                    )
                logger.info(
                    f"Job {job_id}: Saved enhanced resume locally (fallback): {output_file_path}"
                )
            else:
                # Upsert into Supabase 'enhanced_resumes' table
                # Assuming table `enhanced_resumes` exists with columns:
                # resume_id (text, primary key, fk->resumes.id),
                # enhanced_data (jsonb),
                # analysis_data (jsonb),
                # created_at (timestamp)
                data_to_upsert = {
                    "resume_id": resume_id,
                    "enhanced_data": enhanced_resume_data,
                    "analysis_data": analysis_data,
                }
                try:
                    response = (
                        db.table("enhanced_resumes").upsert(data_to_upsert).execute()
                    )
                    # More specific error check
                    if not (hasattr(response, "data") and response.data):
                        logger.error(
                            f"Supabase upsert for enhanced {resume_id} returned no data, assuming failure."
                        )
                        error_details = getattr(response, "error", None) or getattr(
                            response, "message", "Unknown upsert error"
                        )
                        # Don't raise here, just warn as per previous logic
                        logger.warning(
                            f"Failed to confirm enhanced data save in Supabase. Details: {error_details}"
                        )
                    else:
                        logger.info(
                            f"Successfully saved/updated enhanced resume {resume_id} to Supabase."
                        )
                except PostgrestAPIError as db_e:
                    logger.error(
                        f"Supabase upsert error for enhanced {resume_id} (Code: {db_e.code}): {db_e.message}",
                        exc_info=True,
                    )
                    logger.error(
                        f"DB Error Details: {db_e.details} | Hint: {db_e.hint}"
                    )
                    # Don't fail the request, just log the error.
                    logger.warning(
                        "Proceeding with response despite database save error for enhanced data."
                    )
                except Exception as db_save_e:
                    logger.error(
                        f"Job {job_id}: Error saving enhanced resume {resume_id} to Supabase: {db_save_e}",
                        exc_info=True,
                    )
                    # Don't fail the request, but log the error. Frontend still gets results.
                    logger.warning(
                        "Proceeding with response despite database save error for enhanced data."
                    )

            # --- Return Success Response ---
            overall_status = "healthy"  # Mark as healthy if we reach here
            logger.info(f"Job {job_id}: Optimization completed successfully.")
            return jsonify(
                {
                "status": "success",
                    "message": "Resume optimized successfully using advanced workflow",
                "resume_id": resume_id,
                    "data": enhanced_resume_data,  # The enhanced resume content
                    "analysis": analysis_data,  # The analysis/match details
                }
            )
            
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
            return get_status()
            
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
        return 

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
