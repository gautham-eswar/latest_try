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
logger = logging.getLogger('working_app')

# Constants
APP_START_TIME = datetime.now()
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'output')

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

def call_openai_api(messages, temperature=0.3, max_tokens=1000):
    """Call OpenAI API with error handling and retries"""
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens
    }
    
    # Try up to 3 times with exponential backoff
    max_retries = 3
    retry_delay = 1
    
    for attempt in range(max_retries):
        try:
            logger.info(f"Making OpenAI API request (attempt {attempt+1}/{max_retries})")
            response = requests.post(
                f"{OPENAI_API_BASE}/chat/completions",
                headers=headers,
                json=data,
                timeout=30  # Set a reasonable timeout
            )
            
            logger.info(f"OpenAI API response status: {response.status_code}")
            
            if response.status_code == 200:
                return response.json()['choices'][0]['message']['content']
            elif response.status_code == 401:
                error_details = response.json() if response.text else {"error": "Authentication error"}
                logger.critical(f"OpenAI API authentication failed: {error_details}")
                raise Exception(f"OpenAI API key is invalid: {error_details.get('error', {}).get('message', 'Authentication error')}")
            elif response.status_code == 429:
                retry_delay = 2 ** attempt  # Exponential backoff
                logger.warning(f"Rate limited by OpenAI, retrying in {retry_delay}s")
                time.sleep(retry_delay)
                continue
            else:
                error_details = response.json() if response.text else {"error": "Unknown error"}
                logger.error(f"OpenAI API error ({response.status_code}): {error_details}")
                raise Exception(f"OpenAI API error ({response.status_code}): {error_details.get('error', {}).get('message', 'Unknown error')}")
                
        except requests.RequestException as e:
            logger.error(f"Request error: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                raise Exception(f"Failed to connect to OpenAI API after {max_retries} attempts: {str(e)}")
    
    raise Exception("Failed to get response from OpenAI API")

def parse_resume(resume_text):
    """Parse resume text and return structured data using OpenAI"""
    prompt = """
    Parse the following resume and extract structured data in JSON format with the following structure:
    {
        "contact": {
            "name": "Full Name",
            "email": "email@example.com",
            "phone": "phone number",
            "location": "City, State"
        },
        "summary": "Professional summary",
        "skills": ["Skill 1", "Skill 2", ...],
        "experience": [
            {
                "title": "Job Title",
                "company": "Company Name",
                "date_range": "Start Date - End Date",
                "description": ["Achievement 1", "Achievement 2", ...]
            },
            ...
        ],
        "education": [
            {
                "degree": "Degree Name",
                "institution": "Institution Name",
                "date_range": "Start Year - End Year"
            },
            ...
        ],
        "certifications": ["Certification 1", "Certification 2", ...]
    }
    
    Respond with ONLY the JSON object, no explanations or other text.
    """
    
    messages = [
        {"role": "system", "content": "You are a resume parsing assistant that extracts structured data from resumes."},
        {"role": "user", "content": f"{prompt}\n\n{resume_text}"}
    ]
    
    result = call_openai_api(messages)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
    if json_match:
        result = json_match.group(1)
    
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise Exception("Failed to parse structured data from resume")

def extract_keywords(job_description):
    """Extract keywords from job description using OpenAI API"""
    prompt = """
    Extract the most important skills, technologies, and qualifications from this job description.
    Return the result as a JSON array of strings with ONLY the keywords, no explanations or other text.
    Example: ["Python", "React", "AWS", "CI/CD", "Agile", "Team Leadership"]
    """
    
    messages = [
        {"role": "system", "content": "You are a job description analyzer that extracts key skills and requirements."},
        {"role": "user", "content": f"{prompt}\n\n{job_description}"}
    ]
    
    result = call_openai_api(messages)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
    if json_match:
        result = json_match.group(1)
    
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing keywords JSON from OpenAI: {e}")
        raise Exception("Failed to extract keywords from job description")

def optimize_resume(resume_data, job_description, keywords):
    """Use OpenAI to optimize a resume for a specific job"""
    prompt = f"""
    Optimize this resume for the following job description:
    
    JOB DESCRIPTION:
    {job_description}
    
    IMPORTANT KEYWORDS:
    {', '.join(keywords)}
    
    ORIGINAL RESUME:
    {json.dumps(resume_data, indent=2)}
    
    Return an optimized version of the resume as a JSON object with the same structure as the original.
    The optimization should:
    1. Tailor the summary to highlight relevant experience
    2. Reorder skills to prioritize job-relevant ones
    3. Enhance job descriptions to emphasize achievements relevant to the job
    
    Respond with ONLY the JSON object, no explanations or other text.
    """
    
    messages = [
        {"role": "system", "content": "You are a resume optimization assistant."},
        {"role": "user", "content": prompt}
    ]
    
    result = call_openai_api(messages, temperature=0.2, max_tokens=2000)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
    if json_match:
        result = json_match.group(1)
    
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from OpenAI optimization response: {e}")
        raise Exception("Failed to optimize resume")

def generate_analysis(resume_data, optimized_resume, job_description, keywords):
    """Generate analysis data comparing original and optimized resumes"""
    prompt = f"""
    Generate an analysis comparing the original resume to the optimized version with respect to the job description:
    
    JOB DESCRIPTION:
    {job_description}
    
    IMPORTANT KEYWORDS:
    {', '.join(keywords)}
    
    ORIGINAL RESUME:
    {json.dumps(resume_data, indent=2)}
    
    OPTIMIZED RESUME:
    {json.dumps(optimized_resume, indent=2)}
    
    Provide the analysis as a JSON object with the following structure:
    {{
      "keyword_match": {{
        "score": "Match score percentage (integer from 0-100)",
        "matched_keywords": ["list", "of", "matched", "keywords", "from", "resume"],
        "missing_keywords": ["list", "of", "keywords", "not", "in", "resume"]
      }},
      "skills_analysis": {{
        "relevant_skills": ["list", "of", "skills", "relevant", "to", "job"],
        "other_skills": ["list", "of", "other", "skills", "not", "directly", "relevant"]
      }},
      "improvement_suggestions": [
        "List of improvements made or suggested"
      ]
    }}
    
    Respond with ONLY the JSON object, no explanations or other text.
    """
    
    messages = [
        {"role": "system", "content": "You are a resume analysis assistant."},
        {"role": "user", "content": prompt}
    ]
    
    result = call_openai_api(messages)
    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
    if json_match:
        result = json_match.group(1)
    
    try:
        return json.loads(result)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse analysis JSON from OpenAI: {e}")
        raise Exception("Failed to generate resume analysis")

def generate_latex_resume(resume_data):
    """Generate LaTeX code for the resume using OpenAI"""
    prompt = f"""
    Generate professional LaTeX code for the following resume data:
    
    {json.dumps(resume_data, indent=2)}
    
    The LaTeX should:
    1. Use article class with appropriate packages
    2. Have a clear, professional layout
    3. Include all sections: contact, summary, skills, experience, education, certifications
    4. Use itemize environments for lists
    
    Respond with ONLY the LaTeX code, no explanations or other text.
    """
    
    messages = [
        {"role": "system", "content": "You are a LaTeX resume formatting assistant."},
        {"role": "user", "content": prompt}
    ]
    
    result = call_openai_api(messages)
    
    # Extract LaTeX from the result (might be wrapped in markdown code blocks)
    latex_match = re.search(r'```latex\s*(.*?)\s*```', result, re.DOTALL)
    if latex_match:
        return latex_match.group(1)
    
    return result

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
    
    @app.route('/api/health')
    def health():
        """Basic health check that always returns 200."""
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat()
        })
    
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
            optimized_resume = optimize_resume(resume_data, job_text, keywords)
            analysis = generate_analysis(resume_data, optimized_resume, job_text, keywords)
            
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
                              timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              uptime=get_uptime(),
                              version="0.1.0",
                              components=components)
    
    @app.route('/diagnostic/diagnostics')
    def diagnostics():
        """Display detailed system diagnostics"""
        system_info = get_system_info()
        components = get_component_status()
        
        # Determine overall system status
        overall_status = "healthy"
        for component in components.values():
            if component["status"] == "error":
                overall_status = "error"
                break
            elif component["status"] == "warning" and overall_status != "error":
                overall_status = "warning"
        
        # Mock transactions for display
        transactions = [
            {
                "id": "tx_001",
                "method": "GET",
                "path": "/api/health",
                "status_code": 200,
                "duration_ms": 5,
                "timestamp": (datetime.now() - timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "id": "tx_002",
                "method": "GET",
                "path": "/status",
                "status_code": 200,
                "duration_ms": 15,
                "timestamp": (datetime.now() - timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        
        # Environment variables for display (with sensitive data masked)
        env_vars = {
            "FLASK_DEBUG": os.environ.get("FLASK_DEBUG", "True"),
            "OPENAI_API_KEY": "sk-*********************" if OPENAI_API_KEY else "Not set",
            "SUPABASE_URL": os.environ.get("SUPABASE_URL", "Not set"),
            "SUPABASE_KEY": "sk-*********************" if os.environ.get("SUPABASE_KEY") else "Not set",
            "MAX_CONTENT_LENGTH": os.environ.get("MAX_CONTENT_LENGTH", "16777216"),
            "CORS_ORIGINS": os.environ.get("CORS_ORIGINS", "*"),
            "LOG_LEVEL": os.environ.get("LOG_LEVEL", "DEBUG")
        }
        
        return render_template('diagnostics.html',
                              title="Resume Optimizer - Diagnostics",
                              timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                              system_status=overall_status,
                              uptime=get_uptime(),
                              version="0.1.0",
                              components=components,
                              system_info=system_info,
                              transactions=transactions,
                              env_vars=env_vars)
    
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