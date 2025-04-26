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

from flask import Flask, jsonify, request, render_template, g, Response
from flask_cors import CORS
from werkzeug.utils import secure_filename

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

app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24))
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB

# Track application start time
start_time = time.time()

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
    uptime_seconds = time.time() - start_time
    if uptime_seconds < 60:
        return f"{int(uptime_seconds)} seconds"
    elif uptime_seconds < 3600:
        return f"{int(uptime_seconds / 60)} minutes"
    elif uptime_seconds < 86400:
        return f"{int(uptime_seconds / 3600)} hours"
    else:
        return f"{uptime_seconds / 86400:.1f} days"

def handle_missing_api_key():
    """Return a standardized error response for missing API key"""
    if request.path == '/api/health':
        # Still allow health checks without API key
        return None
    
    error_response = {
        "error": "OpenAI API key not configured",
        "message": "The server is missing required API credentials. Please contact the administrator.",
        "status": "configuration_error",
        "timestamp": datetime.datetime.now().isoformat()
    }
    return jsonify(error_response), 503  # Service Unavailable

def create_app():
    """Create and configure a Flask application."""
    # Set up CORS
    CORS(app, resources={r"/api/*": {"origins": '*'}})
    
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
                "/diagnostic/diagnostics"
            ]
        })
    
    @app.route('/api/health', methods=['GET'])
    def health():
        """Health check endpoint."""
        try:
            # Get system metrics
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return jsonify({
                "status": "healthy",
                "uptime": int(time.time() - START_TIME),
                "memory": {
                    "total": memory.total,
                    "available": memory.available,
                    "percent": memory.percent
                },
                "disk": {
                    "total": disk.total,
                    "free": disk.free,
                    "percent": disk.percent
                },
                "timestamp": datetime.datetime.now().isoformat()
            }), 200
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return jsonify({
                "status": "error",
                "error": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }), 500
    
    @app.route('/api/upload', methods=['POST'])
    def upload_resume():
        """Upload and parse a resume file."""
        if 'file' not in request.files:
            return jsonify({
                "status": "error",
                "message": "No file part in the request"
            }), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({
                "status": "error",
                "message": "No file selected"
            }), 400
        
        # Check if the file has an allowed extension
        allowed_extensions = {'pdf', 'docx', 'txt'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        if file_ext not in allowed_extensions:
            return jsonify({
                "status": "error",
                "message": f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}"
            }), 400
        
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
            return jsonify({
                "status": "error",
                "message": f"Error processing resume: {str(e)}"
            }), 500
    
    @app.route('/api/optimize', methods=['POST'])
    def optimize_resume_endpoint():
        """Optimize a resume with a job description."""
        try:
            data = request.json
            
            if not data:
                return jsonify({
                    "status": "error",
                    "message": "No JSON data in request"
                }), 400
            
            resume_id = data.get('resume_id')
            job_description = data.get('job_description')
            
            if not resume_id:
                return jsonify({
                    "status": "error",
                    "message": "Missing required field: resume_id"
                }), 400
            
            if not job_description:
                return jsonify({
                    "status": "error",
                    "message": "Missing required field: job_description"
                }), 400
            
            # Check if the resume exists
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            resume_file = os.path.join(uploads_dir, f"{resume_id}.json")
            
            if not os.path.exists(resume_file):
                return jsonify({
                    "status": "error",
                    "message": f"Resume with ID {resume_id} not found"
                }), 404
            
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
            return jsonify({
                "status": "error",
                "message": f"Error optimizing resume: {str(e)}"
            }), 500
    
    @app.route('/api/download/<resume_id>/<format_type>', methods=['GET'])
    def download_resume(resume_id, format_type):
        """Download a resume in different formats."""
        if format_type not in ['json', 'pdf', 'latex']:
            return jsonify({
                "status": "error",
                "message": f"Unsupported format: {format_type}. Supported formats: json, pdf, latex"
            }), 400
        
        # Check if optimized resume exists
        outputs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')
        resume_file = os.path.join(outputs_dir, f"{resume_id}.json")
        
        if not os.path.exists(resume_file):
            # Check if original resume exists as fallback
            uploads_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
            resume_file = os.path.join(uploads_dir, f"{resume_id}.json")
            
            if not os.path.exists(resume_file):
                return jsonify({
                    "status": "error",
                    "message": f"Resume with ID {resume_id} not found"
                }), 404
        
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
                return jsonify({
                    "status": "error",
                    "message": f"Error generating PDF: {str(e)}"
                }), 500
    
    @app.route('/status')
    def status():
        """Display a simple status page"""
        components = get_component_status()
        
        # Determine overall system status based on component statuses
        overall_status = "healthy"
        for component in components.values():
            if component["status"] == "error":
                overall_status = "error"
                break
            elif component["status"] == "warning" and overall_status != "error":
                overall_status = "warning"
        
        return render_template('status.html', 
                              title="Resume Optimizer - Status",
                              system_status=overall_status,
                              timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              uptime=get_uptime(),
                              version="0.1.0",
                              components=components)
    
    @app.route('/diagnostic/diagnostics')
    def diagnostics():
        """Show diagnostic information."""
        # Get system information
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
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
                "timestamp": (datetime.datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "id": f"req-{uuid.uuid4().hex[:8]}",
                "method": "POST",
                "endpoint": "/api/optimize",
                "status": 200,
                "duration": 1.24,
                "timestamp": (datetime.datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        return render_template('diagnostics.html',
                            uptime=format_uptime(int(time.time() - START_TIME)),
                            memory_used=f"{memory.percent:.1f}%",
                            memory_available=format_size(memory.available),
                            memory_total=format_size(memory.total),
                            disk_used=f"{disk.percent:.1f}%",
                            disk_available=format_size(disk.free),
                            disk_total=format_size(disk.total),
                            resume_processing_times=resume_processing_times,
                            api_response_times=api_response_times,
                            recent_requests=recent_requests,
                            timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    @app.before_request
    def check_api_key():
        """Check if OpenAI API key is available for routes that need it"""
        api_routes = ['/api/upload', '/api/optimize', '/api/enhance']
        
        if request.path in api_routes and not os.environ.get("OPENAI_API_KEY"):
            error_response = handle_missing_api_key()
            if error_response:
                return error_response
    
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
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.exception(e)
        sys.exit(1) 
 