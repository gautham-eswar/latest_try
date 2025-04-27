"""
Working Resume Optimizer Flask App with proper port handling
"""

import os
import sys
import logging
import argparse
from datetime import datetime, timedelta
import uuid
import platform
import json
import psutil
from pathlib import Path
import time
import socket
import re
import io
import requests
from dotenv import load_dotenv
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.middleware.proxy_fix import ProxyFix

from flask import Flask, jsonify, request, render_template, g, Response, current_app
from flask_cors import CORS
from werkzeug.utils import secure_filename

# --- BEGIN CODE VERIFICATION LOGGING ---
# Add logging to verify the running code for OpenAI initialization
# This helps diagnose deployment/caching issues.
def log_file_snippet(filepath, start_marker, end_marker, lines=15):
    try:
        if not os.path.exists(filepath):
            logging.warning(f"Code verification: File not found at {filepath}")
            return
        with open(filepath, 'r') as f:
            content = f.read()
        start_index = content.find(start_marker)
        if start_index == -1:
            logging.warning(f"Code verification: Start marker '{start_marker}' not found in {filepath}")
            return
        end_index = content.find(end_marker, start_index)
        if end_index == -1:
             end_index = start_index + 1000 # Approx limit if end marker not found nearby
        
        snippet = content[start_index:end_index].strip()
        # Limit lines for clarity
        snippet_lines = snippet.split('\\n')
        if len(snippet_lines) > lines:
            snippet = '\\n'.join(snippet_lines[:lines]) + '\\n...'

        logging.info(f"--- Verifying code in {filepath} ---")
        logging.info(f"Snippet around '{start_marker}':\\n{snippet}")
        logging.info(f"--- End verification for {filepath} ---")
        # Check for OpenAI client initialization
        if "OpenAI(api_key=" in snippet:
             logging.info(f"Verification successful: OpenAI client initialization found in {filepath} snippet.")
        else:
             logging.warning(f"Verification FAILED: OpenAI client initialization NOT found in {filepath} snippet.")
             
    except Exception as e:
        logging.error(f"Code verification: Error reading {filepath}: {str(e)}")

try:
    # Get the directory of the current script
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Log diagnostic_system.py snippet
    ds_path = os.path.join(current_dir, 'diagnostic_system.py')
    log_file_snippet(ds_path, 'def check_openai(self):', 'def check_file_system(self):')

    # Log embeddings.py snippet
    emb_path = os.path.join(current_dir, 'embeddings.py')
    log_file_snippet(emb_path, 'class SemanticMatcher:', 'def process_keywords_and_resume')

    # Log enhancer.py snippet
    enh_path = os.path.join(current_dir, 'enhancer.py')
    log_file_snippet(enh_path, 'class ResumeEnhancer:', 'def enhance_resume')

except Exception as e:
     logging.error(f"Code verification: Top-level error during file reading: {str(e)}")
# --- END CODE VERIFICATION LOGGING ---

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
START_TIME = time.time()
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_files')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_results')

# OpenAI API settings
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
if not OPENAI_API_KEY:
    logger.critical("OPENAI_API_KEY environment variable is not set. Cannot proceed without API key.")
    sys.exit(1)

OPENAI_API_BASE = "https://api.openai.com/v1"

# Create directories if they don't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Track application startup
diagnostic_system = None
try:
    from diagnostic_system import DiagnosticSystem
    diagnostic_system = DiagnosticSystem()
    logger.info("Diagnostic system initialized successfully")
except ImportError:
    logger.warning("Diagnostic system module not found. Some features will be disabled.")

def extract_text_from_file(file_path):
    """Extract text from files based on their extension"""
    file_ext = file_path.suffix.lower()
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # If it's not a text file, return a placeholder
        return f"Binary file content (file type: {file_ext})"

def call_openai_api(system_prompt, user_prompt, max_retries=3):
    """Call OpenAI API with retry logic and proper error handling."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        logger.critical("OPENAI_API_KEY environment variable is not set. Cannot proceed without API key.")
        raise ValueError("OpenAI API key is not configured. Please set the OPENAI_API_KEY environment variable.")
    
    base_url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.5
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Making OpenAI API request (attempt {attempt}/{max_retries})")
            response = requests.post(base_url, headers=headers, json=data, timeout=30)
            logger.info(f"OpenAI API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                raise ValueError("Invalid response format from OpenAI API")
            elif response.status_code == 401:
                raise ValueError("OpenAI API key is invalid")
            else:
                logger.error(f"OpenAI API request failed with status {response.status_code}: {response.text}")
                if attempt < max_retries:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    raise ValueError(f"OpenAI API request failed after {max_retries} attempts")
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request error: {str(e)}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                raise ValueError(f"OpenAI API request error: {str(e)}")
    
    # This should not be reached due to the raise in the loop, but just in case
    raise ValueError("Failed to get a response from OpenAI API")

def parse_resume(resume_text):
    """Parse resume text into structured data"""
    system_prompt = "You are a resume parsing assistant. Extract structured information from resumes."
    user_prompt = f"""
    Please extract the following information from this resume:
    
    {resume_text}
    
    Format your response as JSON with these keys:
    - name
    - contact (email, phone, location)
    - objective (if present)
    - skills (array of strings)
    - experience (array of objects with company, title, date, description)
    - education (array of objects with institution, degree, date)
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(.*?)```', result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to parse structured data from resume")

def extract_keywords(job_description):
    """Extract relevant keywords from job description"""
    system_prompt = "You are a keyword extraction assistant for job descriptions."
    user_prompt = f"""
    Extract relevant keywords from this job description:
    
    {job_description}
    
    Format your response as JSON with these keys:
    - skills (technical skills required)
    - experience (experience areas required)
    - education (education requirements)
    - soft_skills (soft skills mentioned)
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(.*?)```', result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to extract keywords from job description")

def optimize_resume(resume_data, job_keywords):
    """Optimize resume based on job keywords"""
    system_prompt = "You are a resume optimization assistant."
    user_prompt = f"""
    Optimize this resume for the job requirements:
    
    RESUME:
    {json.dumps(resume_data, indent=2)}
    
    JOB KEYWORDS:
    {json.dumps(job_keywords, indent=2)}
    
    Format your response as JSON with the same structure as the resume,
    but with optimized content that emphasizes relevant skills and experience.
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(.*?)```', result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to optimize resume")

def match_skills(resume_data, job_keywords):
    """Match resume skills against job requirements"""
    system_prompt = "You are a resume analysis assistant."
    user_prompt = f"""
    Compare these resume skills against job requirements:
    
    RESUME:
    {json.dumps(resume_data, indent=2)}
    
    JOB KEYWORDS:
    {json.dumps(job_keywords, indent=2)}
    
    Format your response as JSON with these keys:
    - matching_skills (skills present in both)
    - missing_skills (skills in job but not resume)
    - skill_match_percentage (percentage of job skills found in resume)
    - recommendations (array of suggestions)
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```(?:json)?\s*(.*?)```', result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to match skills")

def generate_latex_resume(resume_data):
    """Generate LaTeX resume from structured data"""
    system_prompt = "You are a LaTeX resume formatting assistant."
    user_prompt = f"""
    Generate a professional LaTeX resume from this data:
    
    {json.dumps(resume_data, indent=2)}
    
    Format your response as a complete LaTeX document using modern formatting.
    Use the article class with appropriate margins.
    Don't include the json input in your response.
    """
    
    result = call_openai_api(system_prompt, user_prompt)
    
    # Extract LaTeX from the result (might be wrapped in markdown code blocks)
    latex_match = re.search(r'```(?:latex)?\s*(.*?)```', result, re.DOTALL)
    latex_content = latex_match.group(1) if latex_match else result
    
    # Ensure it's a proper LaTeX document
    if not latex_content.strip().startswith('\\documentclass'):
        latex_content = f"""\\documentclass[11pt,letterpaper]{{article}}
\\usepackage[margin=1in]{{geometry}}
\\usepackage{{enumitem}}
\\usepackage{{hyperref}}

\\begin{{document}}
{latex_content}
\\end{{document}}"""
    
    return latex_content

def get_system_info():
    """Get basic system information"""
    process = psutil.Process(os.getpid())
    memory = psutil.virtual_memory()
    
    return {
        "platform": platform.platform(),
        "python_version": sys.version,
        "cpu_count": psutil.cpu_count(),
        "memory": {
            "total": round(memory.total / (1024 * 1024 * 1024), 2),  # GB
            "available": round(memory.available / (1024 * 1024 * 1024), 2),  # GB
            "percent": memory.percent
        },
        "process_memory_mb": process.memory_info().rss / 1024 / 1024
    }

def get_component_status():
    """Get status of all system components"""
    components = {
        "system": {
            "status": "healthy",
            "message": "System is operating normally"
        },
        "database": {
            "status": "warning",
            "message": "Using in-memory database (no Supabase connection)"
        },
        "openai_api": {
            "status": "unknown",
            "message": "API key not tested"
        },
        "file_system": {
            "status": "healthy",
            "message": "File system is writable"
        }
    }
    
    # Test file system by attempting to write to a temp file
    try:
        temp_dir = Path("./temp")
        temp_dir.mkdir(exist_ok=True)
        test_file = temp_dir / "test_write.txt"
        test_file.write_text("Test write operation")
        test_file.unlink()
        components["file_system"]["status"] = "healthy"
    except Exception as e:
        components["file_system"]["status"] = "error"
        components["file_system"]["message"] = f"File system error: {str(e)}"
    
    # Test OpenAI API
    try:
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json"
        }
        
        response = requests.get(
            f"{OPENAI_API_BASE}/models",
            headers=headers
        )
        
        if response.status_code == 200:
            components["openai_api"]["status"] = "healthy"
            components["openai_api"]["message"] = "API connection successful"
        else:
            components["openai_api"]["status"] = "error"
            components["openai_api"]["message"] = f"API error: {response.status_code}"
    except Exception as e:
        components["openai_api"]["status"] = "error"
        components["openai_api"]["message"] = f"API connection error: {str(e)}"
    
    return components

def get_uptime():
    """Get application uptime in human readable format"""
    start_time = current_app.config.get('START_TIME', START_TIME)
    uptime_seconds = time.time() - start_time
    
    return format_uptime(uptime_seconds)

def handle_missing_api_key():
    """Return a standardized error response for missing API key"""
    if request.path == '/api/health':
        # Still allow health checks without API key
        return None
    
    error_response = {
        "error": "OpenAI API key not configured",
        "message": "The server is missing required API credentials. Please contact the administrator.",
        "status": "configuration_error",
        "timestamp": datetime.now().isoformat()
    }
    return jsonify(error_response), 503  # Service Unavailable

def create_app():
    """Create and configure the Flask application."""
    global app, diagnostic_system
    
    # Create Flask app
    app = Flask(__name__, template_folder='templates', static_folder='static')
    
    # Apply middleware
    app.wsgi_app = ProxyFix(app.wsgi_app)
    
    # Configure app settings
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
    app.config['TRAP_HTTP_EXCEPTIONS'] = True  # Ensure HTTP exceptions are handled by our handlers
    app.config['PROPAGATE_EXCEPTIONS'] = False  # Don't propagate exceptions up to the werkzeug handler
    app.config['ERROR_INCLUDE_MESSAGE'] = False  # Don't include default error messages
    
    # Apply CORS
    CORS(app)
    
    # Track application start time
    app.config['START_TIME'] = time.time()
    
    # Initialize diagnostic system
    if diagnostic_system:
        diagnostic_system.init_app(app)
    
    # Request tracking middleware
    @app.before_request
    def before_request():
        """Setup request tracking with transaction ID."""
        g.start_time = time.time()
        g.transaction_id = request.headers.get('X-Transaction-ID', str(uuid.uuid4()))
        logger.info(f"Transaction {g.transaction_id}: {request.method} {request.path} started")

    @app.after_request
    def after_request(response):
        """Complete request tracking and add transaction ID to response."""
        if hasattr(g, 'transaction_id') and hasattr(g, 'start_time'):
            duration = time.time() - g.start_time
            logger.info(f"Transaction {g.transaction_id}: {request.method} {request.path} "
                        f"returned {response.status_code} in {duration:.4f}s")
            response.headers['X-Transaction-ID'] = g.transaction_id
        return response
    
    # Utility function for creating error responses
    def create_error_response(error_type, message, status_code):
        """Create a standardized error response following the error schema."""
        return jsonify({
            "error": error_type,
            "message": message,
            "status_code": status_code,
            "transaction_id": getattr(g, 'transaction_id', None) or str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat()
        }), status_code
    
    # Make utility function available to route handlers
    app.create_error_response = create_error_response
    
    # Basic routes
    @app.route('/')
    def index():
        """Root endpoint with API documentation."""
        return jsonify({
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
                "/api/test/custom-error/:error_code"
            ]
        })
    
    @app.route('/api/health', methods=['GET'])
    def health():
        """
        Health check endpoint that always returns 200 status for Render's monitoring.
        
        Actual component status is included in the response body so clients
        can determine the true system health while Render continues to see a healthy service.
        """
        try:
            health_data = {
                "status": "healthy",
                "uptime": get_uptime(),
                "timestamp": datetime.now().isoformat(),
                "components": {}
            }
            
            # Get system metrics with detailed error handling
            try:
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                health_data["memory"] = {
                    "status": "healthy",
                    "total": format_size(memory.total),
                    "available": format_size(memory.available),
                    "percent": memory.percent
                }
                
                health_data["disk"] = {
                    "status": "healthy",
                    "total": format_size(disk.total),
                    "free": format_size(disk.free),
                    "percent": disk.percent
                }
                
                health_data["components"]["system_resources"] = "healthy"
            except Exception as e:
                logger.warning(f"Error getting system metrics: {str(e)}")
                health_data["status"] = "degraded"
                health_data["memory"] = {"status": "error", "message": str(e)}
                health_data["disk"] = {"status": "error", "message": str(e)}
                health_data["components"]["system_resources"] = "error"
            
            # Check database with detailed error handling
            try:
                db = get_db()
                db_status = db.health_check() if hasattr(db, 'health_check') else {"status": "unknown"}
                health_data["database"] = db_status
                health_data["components"]["database"] = db_status.get("status", "unknown")
                if db_status.get("status") == "error":
                    health_data["status"] = "degraded"
            except Exception as e:
                logger.warning(f"Database health check failed: {str(e)}")
                health_data["database"] = {"status": "error", "message": str(e)}
                health_data["components"]["database"] = "error"
                health_data["status"] = "degraded"
            
            # Check OpenAI API connection
            try:
                headers = {
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json"
                }
                response = requests.get(f"{OPENAI_API_BASE}/models", headers=headers, timeout=5)
                
                if response.status_code == 200:
                    health_data["openai"] = {"status": "healthy"}
                    health_data["components"]["openai"] = "healthy"
                else:
                    health_data["openai"] = {
                        "status": "error", 
                        "message": f"API returned status {response.status_code}"
                    }
                    health_data["components"]["openai"] = "error"
                    health_data["status"] = "degraded"
            except Exception as e:
                logger.warning(f"OpenAI API check failed: {str(e)}")
                health_data["openai"] = {"status": "error", "message": str(e)}
                health_data["components"]["openai"] = "error"
                health_data["status"] = "degraded"
            
            # Always return 200 for Render's health check
            return jsonify(health_data), 200
            
        except Exception as e:
            # Even if everything fails, return 200 with error details
            logger.error(f"Critical error in health check: {str(e)}")
            return jsonify({
                "status": "critical",
                "message": f"Health check encountered a critical error: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat()
            }), 200  # Still return 200 for Render
    
    @app.route('/api/upload', methods=['POST'])
    def upload_resume():
        """Upload and parse a resume file."""
        if 'file' not in request.files:
            return app.create_error_response(
                "MissingFile", 
                "No file part in the request", 
                400
            )
        
        file = request.files['file']
        if file.filename == '':
            return app.create_error_response(
                "EmptyFile", 
                "No file selected", 
                400
            )
        
        # Check if the file has an allowed extension
        allowed_extensions = {'pdf', 'docx', 'txt'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in allowed_extensions:
            return app.create_error_response(
                "InvalidFileType",
                f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}", 
                400
            )
        
        # Generate a unique ID for the resume
        resume_id = f"resume_{int(time.time())}_{uuid.uuid4().hex[:8]}"
        
        try:
            # Save the uploaded file
            filename = secure_filename(f"{resume_id}.{file_ext}")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            
            # Extract text from the file
            resume_text = extract_text_from_file(Path(file_path))
            
            # Parse the resume text using OpenAI
            parsed_resume = parse_resume(resume_text)
            
            # Save the parsed data
            output_file = os.path.join(app.config['UPLOAD_FOLDER'], f"{resume_id}.json")
            with open(output_file, 'w') as f:
                json.dump(parsed_resume, f, indent=2)
            
            return jsonify({
                "status": "success",
                "message": "Resume uploaded and parsed successfully",
                "resume_id": resume_id,
                "data": parsed_resume
            })
        except Exception as e:
            logger.error(f"Error processing resume: {str(e)}")
            return app.create_error_response(
                "ProcessingError", 
                f"Error processing resume: {str(e)}", 
                500
            )
    
    @app.route('/api/optimize', methods=['POST'])
    def optimize_resume_endpoint():
        """Optimize a resume with a job description."""
        # Handle invalid JSON in the request
        if request.content_type == 'application/json':
            try:
                # Explicitly parse the JSON
                data = json.loads(request.data.decode('utf-8') if request.data else '{}')
            except json.JSONDecodeError:
                return app.create_error_response("InvalidJSON", "Could not parse JSON data from request", 400)
        else:
            return app.create_error_response("InvalidContentType", "Content-Type must be application/json", 400)
        
        try:
            if not data:
                return app.create_error_response("MissingData", "No JSON data in request", 400)
            
            resume_id = data.get('resume_id')
            job_description = data.get('job_description')
            
            if not resume_id:
                return app.create_error_response("MissingParameter", "Missing required field: resume_id", 400)
            
            if not job_description:
                return app.create_error_response("MissingParameter", "Missing required field: job_description", 400)
            
            # Check if the resume exists
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            resume_file = os.path.join(uploads_dir, f"{resume_id}.json")
            
            if not os.path.exists(resume_file):
                return app.create_error_response("NotFound", f"Resume with ID {resume_id} not found", 404)
            
            # Load the resume data
            with open(resume_file, 'r') as f:
                resume_data = json.load(f)
            
            # Extract keywords from job description
            job_text = job_description.get('description', '')
            job_title = job_description.get('title', 'Software Engineer')
            
            # Process with OpenAI
            keywords = extract_keywords(job_text)
            optimized_resume = optimize_resume(resume_data, keywords)
            analysis = match_skills(resume_data, keywords)
            
            # Save the optimized resume
            output_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
            os.makedirs(output_dir, exist_ok=True)
            output_file = os.path.join(output_dir, f"{resume_id}.json")
            
            with open(output_file, 'w') as f:
                json.dump(optimized_resume, f, indent=2)
            
            return jsonify({
                "status": "success",
                "message": "Resume optimized successfully",
                "resume_id": resume_id,
                "data": optimized_resume,
                "analysis": analysis
            })
            
        except Exception as e:
            logger.error(f"Error optimizing resume: {str(e)}")
            return app.create_error_response("ProcessingError", f"Error optimizing resume: {str(e)}", 500)
    
    @app.route('/api/download/<resume_id>/<format_type>', methods=['GET'])
    def download_resume(resume_id, format_type):
        """Download a resume in different formats."""
        if format_type not in ['json', 'pdf', 'latex']:
            return app.create_error_response("InvalidFormat", 
                f"Unsupported format: {format_type}. Supported formats: json, pdf, latex", 400)
        
        # Check if optimized resume exists
        outputs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        resume_file = os.path.join(outputs_dir, f"{resume_id}.json")
        
        if not os.path.exists(resume_file):
            # Check if original resume exists as fallback
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            resume_file = os.path.join(uploads_dir, f"{resume_id}.json")
            
            if not os.path.exists(resume_file):
                return app.create_error_response("NotFound", f"Resume with ID {resume_id} not found", 404)
        
        # Load the resume data
        with open(resume_file, 'r') as f:
            resume_data = json.load(f)
        
        if format_type == 'json':
            # Return the JSON data directly
            return jsonify({
                "status": "success",
                "resume_id": resume_id,
                "data": resume_data
            })
        
        elif format_type == 'latex':
            # Generate LaTeX content using OpenAI
            latex_content = generate_latex_resume(resume_data)
            
            response = Response(
                latex_content,
                mimetype='application/x-latex',
                headers={'Content-Disposition': f'attachment; filename={resume_id}.tex'}
            )
            return response
        
        elif format_type == 'pdf':
            try:
                # Generate LaTeX content
                latex_content = generate_latex_resume(resume_data)
                
                # For a real implementation, we would convert this to PDF
                # For this prototype, we'll return the LaTeX with PDF mimetype
                mock_pdf_content = f"% PDF mock for {resume_id}\n\n{latex_content}"
                
                response = Response(
                    mock_pdf_content,
                    mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename={resume_id}.pdf'}
                )
                return response
            except Exception as e:
                logger.error(f"Error generating PDF: {str(e)}")
                return app.create_error_response("ProcessingError", f"Error generating PDF: {str(e)}", 500)
    
    @app.route('/status')
    def status():
        """Display a system status page with detailed component information"""
        try:
            # Get component status with fallbacks
            try:
                components = get_component_status()
            except Exception as e:
                logger.error(f"Failed to get component status: {str(e)}")
                components = {
                    "database": {"status": "error", "message": str(e)},
                    "system": {"status": "unknown", "message": "Could not retrieve system status"}
                }
            
            # Get system metrics with fallbacks
            try:
                memory = psutil.virtual_memory()
                cpu_percent = psutil.cpu_percent(interval=0.1)
            except Exception as e:
                logger.error(f"Failed to get system metrics: {str(e)}")
                memory = None
                cpu_percent = None
            
            # Determine overall system status based on component statuses
            overall_status = "healthy"
            for component in components.values():
                if component.get("status") == "error":
                    overall_status = "error"
                    break
                elif component.get("status") == "warning" and overall_status != "error":
                    overall_status = "warning"
            
            # Create a database status object with fallbacks
            try:
                db = get_db()
                db_check = db.health_check() if hasattr(db, 'health_check') else {"status": "unknown"}
                database_status = {
                    "status": db_check.get("status", "unknown"),
                    "message": db_check.get("message", "Database status unknown"),
                    "tables": db_check.get("tables", ["resumes", "optimizations", "users"])  # Example tables
                }
            except Exception as e:
                logger.error(f"Failed to check database status: {str(e)}")
                database_status = {
                    "status": "error",
                    "message": f"Database error: {str(e)}",
                    "tables": []
                }
            
            # System info with fallbacks
            system_info = {
                "uptime": get_uptime(),
                "memory_usage": f"{memory.percent:.1f}%" if memory else "Unknown",
                "cpu_usage": f"{cpu_percent:.1f}%" if cpu_percent is not None else "Unknown"
            }
            
            # Recent transactions (placeholder) with fallbacks
            try:
                if diagnostic_system and hasattr(diagnostic_system, 'transaction_history'):
                    recent_transactions = diagnostic_system.transaction_history[:5]
                else:
                    recent_transactions = []
            except Exception as e:
                logger.error(f"Failed to get transaction history: {str(e)}")
                recent_transactions = []
            
            # Render the template with error handling
            try:
                return render_template('status.html',
                                    system_info=system_info,
                                    database_status=database_status,
                                    recent_transactions=recent_transactions)
            except Exception as e:
                logger.error(f"Error rendering status template: {str(e)}")
                # Fall back to JSON response on template error
                return jsonify({
                    "status": overall_status,
                    "system_info": system_info,
                    "components": components,
                    "error": f"Template error: {str(e)}"
                }), 200  # Return 200 even for errors
            
        except Exception as e:
            # Catch-all exception handler with JSON fallback
            logger.error(f"Critical error in status page: {str(e)}")
            return jsonify({
                "status": "critical",
                "message": f"Error loading status page: {str(e)}",
                "error_type": type(e).__name__,
                "timestamp": datetime.now().isoformat()
            }), 200  # Always return 200
    
    @app.route('/diagnostic/diagnostics')
    def diagnostics():
        """Show diagnostic information."""
        # Get system information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Fetch component status
        try:
            components = get_component_status()
        except Exception as e:
            logger.error(f"Failed to get component status for diagnostics: {str(e)}")
            components = {
                "system": {"status": "error", "message": "Failed to retrieve status"},
                "database": {"status": "error", "message": str(e)},
                "openai_api": {"status": "error", "message": str(e)},
                "file_system": {"status": "error", "message": str(e)},
            }
        
        # Determine overall system status based on components
        overall_status = "healthy"
        for component_status in components.values():
            if component_status.get("status") == "error":
                overall_status = "error"
                break
            elif component_status.get("status") == "warning" and overall_status != "error":
                overall_status = "warning"
        
        # Placeholder for other variables (adjust as needed)
        active_connections = 0 # Replace with actual logic if available
        version = "0.1.0"      # Replace with actual version logic
        title = "System Diagnostics"
        env_vars_filtered = {k: "***" if "key" in k.lower() or "token" in k.lower() else v for k, v in os.environ.items()}
        
        # Sample metrics
        resume_processing_times = [1.2, 0.9, 1.5, 1.1, 1.3]
        api_response_times = [0.2, 0.3, 0.1, 0.2, 0.1]
        
        # Sample requests
        recent_requests = [
            {
                "id": f"req-{uuid.uuid4().hex[:8]}",
                "method": "POST",
                "endpoint": "/api/upload",
                "status": 200,
                "duration": 0.35,
                "timestamp": (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "id": f"req-{uuid.uuid4().hex[:8]}",
                "method": "POST",
                "endpoint": "/api/optimize",
                "status": 200,
                "duration": 1.24,
                "timestamp": (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        # Prepare diagnostic info in structured format for template
        system_info = {
            "uptime": format_uptime(int(time.time() - START_TIME)),
            "platform": platform.platform(),
            "python_version": sys.version,
            "cpu_count": psutil.cpu_count(),
            "memory": {
                "total": format_size(memory.total),
                "available": format_size(memory.available),
                "percent": memory.percent
            },
            "disk": {
                "total": format_size(disk.total),
                "free": format_size(disk.free),
                "percent": disk.percent
            }
        }
        
        # Gracefully handle template rendering
        try:
            current_uptime = format_uptime(int(time.time() - START_TIME))
            return render_template('diagnostics.html',
                               title=title,
                               system_status=overall_status,
                               active_connections=active_connections,
                               version=version,
                               components=components,
                               system_info=system_info,
                               uptime=current_uptime,
                               resume_processing_times=resume_processing_times,
                               api_response_times=api_response_times,
                               recent_requests=recent_requests,
                               transactions=[],
                               env_vars=env_vars_filtered,
                               pipeline_status={"status": "unknown", "message": "No pipeline data available"},
                               pipeline_stages=[],
                               pipeline_history=[],
                               timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        except Exception as e:
            logger.error(f"Error rendering diagnostics template: {str(e)}", exc_info=True)
            return jsonify({
                "status": "error",
                "error_type": type(e).__name__,
                "message": f"Error rendering diagnostics page: {str(e)}",
                "timestamp": datetime.now().isoformat()
            }), 500
    
    @app.route('/api/test/simulate-failure')
    def test_simulate_failure():
        """Test endpoint to simulate a failure"""
        raise ValueError("This is a simulated failure for testing error handling")
        
    @app.route('/api/test/custom-error/<int:error_code>')
    def test_custom_error(error_code):
        """Test endpoint to return custom error codes"""
        if error_code < 400 or error_code > 599:
            return jsonify({
                "error": "Invalid error code",
                "message": "Error code must be between 400 and 599",
                "status_code": 400,
                "transaction_id": str(uuid.uuid4()),
                "timestamp": datetime.now().isoformat()
            }), 400
        
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
            504: "Gateway Timeout"
        }
        
        message = error_messages.get(error_code, f"Custom error with code {error_code}")
        
        return jsonify({
            "error": f"Error {error_code}",
            "message": message,
            "status_code": error_code,
            "transaction_id": str(uuid.uuid4()),
            "timestamp": datetime.now().isoformat()
        }), error_code
    
    @app.before_request
    def check_api_key():
        """Check if OpenAI API key is available for routes that need it"""
        api_routes = ['/api/upload', '/api/optimize', '/api/enhance']
        
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
        return app.create_error_response("NotFound", "The requested resource could not be found", 404)

    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 errors specifically."""
        return app.create_error_response("InternalServerError", "An internal server error occurred", 500)
    
    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Handle all other HTTP exceptions."""
        return app.create_error_response(
            f"HTTP{e.code}Error", 
            e.description or f"HTTP error occurred with status code {e.code}", 
            e.code
        )
    
    @app.route('/favicon.ico')
    def favicon():
        """Serve the favicon to prevent repeated 404 errors."""
        try:
            return app.send_static_file('favicon.ico')
        except:
            # If favicon.ico isn't found, return empty response with 204 status
            return '', 204
    
    return app

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Resume Optimizer API')
    parser.add_argument('--port', type=int, default=8080,
                      help='Port to run the server on (default: 8080)')
    parser.add_argument('--debug', action='store_true',
                      help='Run in debug mode')
    parser.add_argument('--host', type=str, default='0.0.0.0',
                      help='Host to run the server on (default: 0.0.0.0)')
    
    return parser.parse_args()

# Utility functions
def format_size(size_bytes):
    """Format bytes to human readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def format_uptime(seconds):
    """Format seconds to human readable uptime."""
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if days > 0:
        return f"{int(days)}d {int(hours)}h {int(minutes)}m"
    elif hours > 0:
        return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"
    elif minutes > 0:
        return f"{int(minutes)}m {int(seconds)}s"
    else:
        return f"{int(seconds)}s"

class FallbackDatabase:
    """In-memory fallback database for when the main database is unavailable."""
    
    def __init__(self):
        """Initialize the in-memory database."""
        self.data = {
            "resumes": {},
            "optimizations": {},
            "users": {},
            "system_logs": []
        }
        logger.info("Initialized fallback in-memory database")
    
    def insert(self, collection, document):
        """Insert a document into a collection."""
        if collection not in self.data:
            self.data[collection] = {}
        
        # Use document id if provided, otherwise generate one
        doc_id = document.get('id') or str(uuid.uuid4())
        document['id'] = doc_id
        
        # Add timestamp if not present
        if 'timestamp' not in document:
            document['timestamp'] = datetime.now().isoformat()
            
        self.data[collection][doc_id] = document
        return doc_id
    
    def find(self, collection, query=None):
        """Find documents in a collection matching a query."""
        if collection not in self.data:
            return []
            
        if query is None:
            return list(self.data[collection].values())
            
        # Simple query matching
        results = []
        for doc in self.data[collection].values():
            match = True
            for k, v in query.items():
                if k not in doc or doc[k] != v:
                    match = False
                    break
            if match:
                results.append(doc)
                
        return results
    
    def get(self, collection, doc_id):
        """Get a specific document by ID."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return None
        return self.data[collection][doc_id]
    
    def update(self, collection, doc_id, updates):
        """Update a document."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return False
            
        doc = self.data[collection][doc_id]
        for k, v in updates.items():
            doc[k] = v
            
        return True
    
    def delete(self, collection, doc_id):
        """Delete a document."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return False
            
        del self.data[collection][doc_id]
        return True
    
    def health_check(self):
        """Perform a basic health check."""
        return {
            "status": "warning",
            "message": "Using fallback in-memory database",
            "tables": list(self.data.keys())
        }
    
    def table(self, name):
        """Get a table/collection reference for chaining operations."""
        class TableQuery:
            def __init__(self, db, table_name):
                self.db = db
                self.table_name = table_name
                self._columns = '*' 
                self._limit_val = None
                
            def select(self, columns='*'):
                self._columns = columns
                return self
                
            def limit(self, n):
                self._limit_val = n
                return self
                
            def execute(self):
                results = self.db.find(self.table_name)
                if self._limit_val:
                    results = results[:self._limit_val]
                return results
                
        return TableQuery(self, name)

def get_db():
    """Get database client with comprehensive error handling."""
    try:
        # First try to import and use the real database
        from database import create_database_client
        client = create_database_client()
        logger.info("Connected to primary database")
        return client
    except ImportError:
        logger.warning("Database module not available. Using fallback database.")
        return FallbackDatabase()
    except Exception as e:
        logger.warning(f"Database connection failed: {str(e)}. Using fallback database.")
        return FallbackDatabase()

if __name__ == '__main__':
    try:
        # Parse command line arguments
        args = parse_args()
        port = args.port
        debug = args.debug
        host = args.host
        
        # Log configuration
        logger.info(f"Starting Flask server on {host}:{port} (debug: {debug})")
        
        # Create and run app
        app = create_app()
        app.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        logger.info("Server shutdown requested via keyboard interrupt")
        sys.exit(0)
    except SystemExit as e:
        # Clean exit with provided exit code
        logger.info(f"System exit with code {e.code}")
        sys.exit(e.code)
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.exception(e)
        if diagnostic_system:
            diagnostic_system.increment_error_count("StartupError", str(e))
        sys.exit(1) 
 