import os
import uuid
import time
import logging
import traceback
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Dict, List, Any, Tuple, Union, Optional

# Import core algorithm modules
try:
    from resume_parser import parse as parse_resume_core
    from keyword_extractor import extract as extract_keywords_core
    from semantic_matcher import match as perform_semantic_matching_core
    from resume_enhancer import enhance as enhance_resume_core
    from classic_template_adapter import generate as generate_pdf_core
except ImportError as e:
    logging.error(f"Failed to import core algorithm modules: {str(e)}")
    # Define stub functions for the core modules that we failed to import
    # This allows the application to at least partially function
    def parse_resume_core(*args, **kwargs): 
        raise NotImplementedError("Resume parser module not available")
    def extract_keywords_core(*args, **kwargs): 
        raise NotImplementedError("Keyword extractor module not available")
    def perform_semantic_matching_core(*args, **kwargs): 
        raise NotImplementedError("Semantic matcher module not available")
    def enhance_resume_core(*args, **kwargs): 
        raise NotImplementedError("Resume enhancer module not available")
    def generate_pdf_core(*args, **kwargs): 
        raise NotImplementedError("PDF generator module not available")

# Import pipeline modules
try:
    from resume_parser import parse_resume_file
    from keyword_extractor import extract_keywords_from_text
    from embeddings import create_embeddings, calculate_similarity
    from enhancer import enhance_resume_with_keywords
    from pdf_generator import create_pdf_generator
except ImportError as e:
    # These will fail when imported from test modules
    logging.warning(f"Some modules could not be imported: {e}")

# Global diagnostic system reference
diagnostic_system = None

def init_api_adapter(app_diagnostic_system=None):
    """Initialize the API adapter with a reference to the diagnostic system."""
    global diagnostic_system
    diagnostic_system = app_diagnostic_system
    logging.info("API adapter initialized with diagnostic system")

def _track_pipeline_stage(job_id, stage_name, func, *args, **kwargs):
    """Wrapper to track a pipeline stage execution with the diagnostic system."""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        
        # Record stage completion status
        status = 'healthy' if result.get('success', False) else 'error'
        message = result.get('error', {}).get('message') if not result.get('success', False) else None
        
        if diagnostic_system:
            diagnostic_system.record_pipeline_stage(job_id, stage_name, status, duration, message)
        
        return result
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        
        # Record failure
        if diagnostic_system:
            diagnostic_system.record_pipeline_stage(job_id, stage_name, 'error', duration, str(e))
        
        # Re-raise the exception
        raise

# Configure logging
logger = logging.getLogger('api_adapter')

# Constants
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Create necessary directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Standard response structure
def create_response(success=True, data=None, error=None, metrics=None):
    """Create a standardized response structure."""
    return {
        'success': success,
        'timestamp': datetime.now().isoformat(),
        'data': data or {},
        'error': error,
        'metrics': metrics or {}
    }

# Performance tracking decorator
def track_performance(func):
    """Decorator to track execution time and other metrics."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = None
        try:
            # Execute the function
            result = func(*args, **kwargs)
            # If result is a dictionary with 'success' key, it's already our format
            if isinstance(result, dict) and 'success' in result:
                response = result
            else:
                response = create_response(success=True, data=result)
            
            # Add performance metrics
            duration = time.time() - start_time
            if 'metrics' not in response:
                response['metrics'] = {}
            response['metrics']['execution_time'] = duration
            response['metrics']['function'] = func.__name__
            
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # Create error response with metrics
            error_response = create_response(
                success=False,
                error={
                    'message': str(e),
                    'type': type(e).__name__,
                    'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
                },
                metrics={
                    'execution_time': duration,
                    'function': func.__name__
                }
            )
            return error_response
            
    return wrapper

# Input validation helpers
def validate_file_path(file_path: str) -> bool:
    """Validate that the file exists and is accessible."""
    if not file_path:
        raise ValueError("File path is required")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"No permission to read file: {file_path}")
    return True

def validate_job_description(job_description: str) -> bool:
    """Validate the job description."""
    if not job_description:
        raise ValueError("Job description is required")
    if len(job_description) < 10:
        raise ValueError("Job description is too short")
    return True

def validate_resume_data(resume_data: Dict) -> bool:
    """Validate the resume data structure."""
    required_fields = ['contact', 'education', 'experience']
    if not resume_data:
        raise ValueError("Resume data is required")
    
    for field in required_fields:
        if field not in resume_data:
            raise ValueError(f"Missing required field in resume data: {field}")
    return True

def validate_output_path(output_path: str) -> bool:
    """Validate that the output path is writable."""
    if not output_path:
        raise ValueError("Output path is required")
    
    # Check if the directory exists and is writable
    directory = os.path.dirname(output_path)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            raise PermissionError(f"Cannot create directory {directory}: {str(e)}")
    
    if not os.access(directory, os.W_OK):
        raise PermissionError(f"No permission to write to directory: {directory}")
    
    return True

# File management helpers
def create_temp_file(extension='.txt') -> str:
    """Create a temporary file and return its path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=TEMP_DIR)
    temp_file.close()
    return temp_file.name

def cleanup_temp_files(file_paths: List[str]) -> None:
    """Clean up temporary files."""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")

# Core API functions
@track_performance
def parse_resume(file_path: str, resume_id: str = None, job_id=None) -> Dict:
    """
    Safely invoke resume parser with proper error handling.
    
    Args:
        file_path: Path to the resume file
        resume_id: Optional resume ID
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure
    """
    try:
        # Validate inputs
        validate_file_path(file_path)
        
        # Generate a resume ID if not provided
        if not resume_id:
            resume_id = f"resume_{str(uuid.uuid4())[:8]}"
            
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Resume Parser', parse_resume_file, file_path, resume_id)
        
        # Standard execution
        logger.info(f"Parsing resume from {file_path} with ID {resume_id}")
        result = parse_resume_file(file_path, resume_id)
        return result
    except Exception as e:
        logger.error(f"Resume parsing failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to parse resume: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def extract_keywords(job_description: str, job_id=None) -> Dict:
    """
    Safely invoke keyword extractor with proper error handling.
    
    Args:
        job_description: Text of the job description
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing extracted keywords
    """
    try:
        # Validate inputs
        validate_job_description(job_description)
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Keyword Extractor', extract_keywords_from_text, job_description)
        
        # Standard execution
        logger.info(f"Extracting keywords from job description ({len(job_description)} chars)")
        result = extract_keywords_from_text(job_description)
        return result
    except Exception as e:
        logger.error(f"Keyword extraction failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to extract keywords: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def perform_semantic_matching(resume_data: Dict, keywords_data: Dict, job_id=None) -> Dict:
    """
    Safely invoke the semantic matcher with proper error handling.
    
    Args:
        resume_data: Structured resume data
        keywords_data: Extracted keywords data
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing matches
    """
    try:
        # Validate inputs
        if not resume_data:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data",
                    'details': "Resume data must be provided"
                }
            }
        
        # Extract necessary information for matching
        keywords = keywords_data.get('keywords', [])
        if not keywords:
            return {
                'success': False,
                'error': {
                    'message': "No keywords available for matching",
                    'details': "Keyword extraction did not produce any keywords"
                }
            }
            
        # Function to perform the actual matching
        def do_semantic_matching(resume_data, keywords):
            # Create embeddings for resume content
            resume_text = ""
            
            # Extract skills
            skills = resume_data.get('skills', [])
            if skills:
                resume_text += "Skills: " + ", ".join(skills) + "\n\n"
                
            # Extract experience
            experiences = resume_data.get('experience', [])
            for exp in experiences:
                resume_text += f"Position: {exp.get('title')} at {exp.get('company')}\n"
                if 'description' in exp and isinstance(exp['description'], list):
                    resume_text += "Responsibilities:\n"
                    for item in exp['description']:
                        resume_text += f"- {item}\n"
                resume_text += "\n"
                
            # Extract education
            education = resume_data.get('education', [])
            for edu in education:
                resume_text += f"Education: {edu.get('degree')} from {edu.get('school')}\n"
                
            # Calculate matches using embeddings
            resume_embedding = create_embeddings(resume_text)
            
            matches = {}
            matched_keywords = []
            unmatched_keywords = []
            
            for keyword in keywords:
                keyword_embedding = create_embeddings(keyword)
                similarity = calculate_similarity(resume_embedding, keyword_embedding)
                
                matches[keyword] = {
                    'score': similarity,
                    'present': similarity > 0.7  # Threshold for considering a match
                }
                
                if similarity > 0.7:
                    matched_keywords.append(keyword)
                else:
                    unmatched_keywords.append(keyword)
                    
            return {
                'success': True,
                'data': {
                    'matches': matches,
                    'matched_keywords': matched_keywords,
                    'unmatched_keywords': unmatched_keywords,
                    'match_rate': len(matched_keywords) / len(keywords) if keywords else 0
                }
            }
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Semantic Matcher', do_semantic_matching, resume_data, keywords)
            
        # Standard execution
        logger.info(f"Performing semantic matching with {len(keywords)} keywords")
        result = do_semantic_matching(resume_data, keywords)
        return result
    except Exception as e:
        logger.error(f"Semantic matching failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to perform semantic matching: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def enhance_resume(resume_data: Dict, matches: Dict, job_id=None) -> Dict:
    """
    Safely invoke the resume enhancer with proper error handling.
    
    Args:
        resume_data: Structured resume data
        matches: Keyword matches from semantic matching
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing enhanced resume
    """
    try:
        # Validate inputs
        if not resume_data or not matches:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data or keyword matches",
                    'details': "Both resume data and keyword matches must be provided"
                }
            }
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Resume Enhancer', enhance_resume_with_keywords, resume_data, matches)
            
        # Standard execution
        logger.info(f"Enhancing resume with {len(matches)} matched keywords")
        result = enhance_resume_with_keywords(resume_data, matches)
        return result
    except Exception as e:
        logger.error(f"Resume enhancement failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to enhance resume: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def generate_pdf(resume_data: Dict, output_path: str, job_id=None) -> Dict:
    """
    Safely use classic_template_adapter to generate PDF with proper error handling.
    
    Args:
        resume_data: Enhanced resume data
        output_path: Path to save the output PDF
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing PDF path
    """
    try:
        # Validate inputs
        if not resume_data:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data",
                    'details': "Resume data must be provided"
                }
            }
        
        validate_output_path(output_path)
        
        # Create the PDF generator
        pdf_generator = create_pdf_generator()
        
        # Function to generate the PDF
        def do_generate_pdf(resume_data, output_path):
            result = pdf_generator.generate_pdf(resume_data, output_path)
            if result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'output_path': output_path,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                return result
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'PDF Generator', do_generate_pdf, resume_data, output_path)
            
        # Standard execution
        logger.info(f"Generating PDF at {output_path}")
        result = do_generate_pdf(resume_data, output_path)
        return result
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to generate PDF: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def run_pipeline(resume_id: str, file_path: str, job_description: str) -> Dict:
    """
    Run the full resume optimization pipeline from parsing to enhancement.
    
    Args:
        resume_id: Resume ID
        file_path: Path to resume file
        job_description: Job description text
        
    Returns:
        Dict with standard response structure containing pipeline results
    """
    try:
        job_id = None
        if diagnostic_system:
            # Start a new pipeline job
            job_id = diagnostic_system.start_pipeline_job(
                resume_id, 
                Path(file_path).suffix[1:],
                job_description[:100] + '...' if len(job_description) > 100 else job_description
            )
        
        logger.info(f"Starting pipeline for resume {resume_id}")
        
        # Step 1: Parse resume
        parse_result = parse_resume(file_path, resume_id, job_id)
        if not parse_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', parse_result.get('error', {}).get('message'))
            return parse_result
        
        resume_data = parse_result.get('data', {})
        
        # Step 2: Extract keywords
        keywords_result = extract_keywords(job_description, job_id)
        if not keywords_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', keywords_result.get('error', {}).get('message'))
            return keywords_result
        
        keyword_data = keywords_result.get('data', {})
        
        # Step 3: Perform semantic matching
        matching_result = perform_semantic_matching(resume_data, keyword_data, job_id)
        if not matching_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', matching_result.get('error', {}).get('message'))
            return matching_result
        
        matches = matching_result.get('data', {}).get('matches', {})
        
        # Step 4: Enhance resume
        enhancement_result = enhance_resume(resume_data, matches, job_id)
        if not enhancement_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', enhancement_result.get('error', {}).get('message'))
            return enhancement_result
        
        enhanced_resume = enhancement_result.get('data', {}).get('enhanced_resume', {})
        
        # Mark pipeline job as completed
        if diagnostic_system and job_id:
            diagnostic_system.complete_pipeline_job(job_id, 'healthy', "Pipeline completed successfully")
        
        logger.info(f"Pipeline completed successfully for resume {resume_id}")
        return {
            'success': True,
            'data': {
                'original_resume': resume_data,
                'keywords': keyword_data,
                'matches': matching_result.get('data', {}),
                'enhanced_resume': enhanced_resume,
                'timestamp': datetime.now().isoformat()
            }
        }
    except Exception as e:
        if diagnostic_system and job_id:
            diagnostic_system.complete_pipeline_job(job_id, 'error', str(e))
            
        logger.error(f"Pipeline execution failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Pipeline execution failed: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

# Optional helper function for simple tasks
def get_resume_status(resume_id: str) -> Dict:
    """
    Get the status of a previously processed resume.
    
    Args:
        resume_id: Unique identifier for the resume
        
    Returns:
        Status information including file paths and processing state
    """
    try:
        if not resume_id:
            raise ValueError("Resume ID is required")
        
        output_path = os.path.join(OUTPUT_DIR, f"{resume_id}.pdf")
        
        if os.path.exists(output_path):
            return create_response(success=True, data={
                'resume_id': resume_id,
                'status': 'completed',
                'output_path': output_path,
                'file_size': os.path.getsize(output_path),
                'creation_time': datetime.fromtimestamp(os.path.getctime(output_path)).isoformat()
            })
        else:
            return create_response(success=True, data={
                'resume_id': resume_id,
                'status': 'not_found'
            })
            
    except Exception as e:
        logger.error(f"Error checking resume status: {str(e)}")
        return create_response(
            success=False,
            error={
                'message': str(e),
                'type': type(e).__name__,
                'resume_id': resume_id
            }
        ) 
import uuid
import time
import logging
import traceback
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from functools import wraps
from typing import Dict, List, Any, Tuple, Union, Optional

# Import core algorithm modules
try:
    from resume_parser import parse as parse_resume_core
    from keyword_extractor import extract as extract_keywords_core
    from semantic_matcher import match as perform_semantic_matching_core
    from resume_enhancer import enhance as enhance_resume_core
    from classic_template_adapter import generate as generate_pdf_core
except ImportError as e:
    logging.error(f"Failed to import core algorithm modules: {str(e)}")
    # Define stub functions for the core modules that we failed to import
    # This allows the application to at least partially function
    def parse_resume_core(*args, **kwargs): 
        raise NotImplementedError("Resume parser module not available")
    def extract_keywords_core(*args, **kwargs): 
        raise NotImplementedError("Keyword extractor module not available")
    def perform_semantic_matching_core(*args, **kwargs): 
        raise NotImplementedError("Semantic matcher module not available")
    def enhance_resume_core(*args, **kwargs): 
        raise NotImplementedError("Resume enhancer module not available")
    def generate_pdf_core(*args, **kwargs): 
        raise NotImplementedError("PDF generator module not available")

# Import pipeline modules
try:
    from resume_parser import parse_resume_file
    from keyword_extractor import extract_keywords_from_text
    from embeddings import create_embeddings, calculate_similarity
    from enhancer import enhance_resume_with_keywords
    from pdf_generator import create_pdf_generator
except ImportError as e:
    # These will fail when imported from test modules
    logging.warning(f"Some modules could not be imported: {e}")

# Global diagnostic system reference
diagnostic_system = None

def init_api_adapter(app_diagnostic_system=None):
    """Initialize the API adapter with a reference to the diagnostic system."""
    global diagnostic_system
    diagnostic_system = app_diagnostic_system
    logging.info("API adapter initialized with diagnostic system")

def _track_pipeline_stage(job_id, stage_name, func, *args, **kwargs):
    """Wrapper to track a pipeline stage execution with the diagnostic system."""
    start_time = time.time()
    try:
        result = func(*args, **kwargs)
        end_time = time.time()
        duration = end_time - start_time
        
        # Record stage completion status
        status = 'healthy' if result.get('success', False) else 'error'
        message = result.get('error', {}).get('message') if not result.get('success', False) else None
        
        if diagnostic_system:
            diagnostic_system.record_pipeline_stage(job_id, stage_name, status, duration, message)
        
        return result
    except Exception as e:
        end_time = time.time()
        duration = end_time - start_time
        
        # Record failure
        if diagnostic_system:
            diagnostic_system.record_pipeline_stage(job_id, stage_name, 'error', duration, str(e))
        
        # Re-raise the exception
        raise

# Configure logging
logger = logging.getLogger('api_adapter')

# Constants
TEMP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'temp')
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'outputs')
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

# Create necessary directories
os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Standard response structure
def create_response(success=True, data=None, error=None, metrics=None):
    """Create a standardized response structure."""
    return {
        'success': success,
        'timestamp': datetime.now().isoformat(),
        'data': data or {},
        'error': error,
        'metrics': metrics or {}
    }

# Performance tracking decorator
def track_performance(func):
    """Decorator to track execution time and other metrics."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = None
        try:
            # Execute the function
            result = func(*args, **kwargs)
            # If result is a dictionary with 'success' key, it's already our format
            if isinstance(result, dict) and 'success' in result:
                response = result
            else:
                response = create_response(success=True, data=result)
            
            # Add performance metrics
            duration = time.time() - start_time
            if 'metrics' not in response:
                response['metrics'] = {}
            response['metrics']['execution_time'] = duration
            response['metrics']['function'] = func.__name__
            
            logger.info(f"{func.__name__} completed in {duration:.3f}s")
            return response
            
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"{func.__name__} failed after {duration:.3f}s: {str(e)}")
            logger.debug(traceback.format_exc())
            
            # Create error response with metrics
            error_response = create_response(
                success=False,
                error={
                    'message': str(e),
                    'type': type(e).__name__,
                    'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
                },
                metrics={
                    'execution_time': duration,
                    'function': func.__name__
                }
            )
            return error_response
            
    return wrapper

# Input validation helpers
def validate_file_path(file_path: str) -> bool:
    """Validate that the file exists and is accessible."""
    if not file_path:
        raise ValueError("File path is required")
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
    if not path.is_file():
        raise ValueError(f"Not a file: {file_path}")
    if not os.access(file_path, os.R_OK):
        raise PermissionError(f"No permission to read file: {file_path}")
    return True

def validate_job_description(job_description: str) -> bool:
    """Validate the job description."""
    if not job_description:
        raise ValueError("Job description is required")
    if len(job_description) < 10:
        raise ValueError("Job description is too short")
    return True

def validate_resume_data(resume_data: Dict) -> bool:
    """Validate the resume data structure."""
    required_fields = ['contact', 'education', 'experience']
    if not resume_data:
        raise ValueError("Resume data is required")
    
    for field in required_fields:
        if field not in resume_data:
            raise ValueError(f"Missing required field in resume data: {field}")
    return True

def validate_output_path(output_path: str) -> bool:
    """Validate that the output path is writable."""
    if not output_path:
        raise ValueError("Output path is required")
    
    # Check if the directory exists and is writable
    directory = os.path.dirname(output_path)
    if not os.path.exists(directory):
        try:
            os.makedirs(directory, exist_ok=True)
        except Exception as e:
            raise PermissionError(f"Cannot create directory {directory}: {str(e)}")
    
    if not os.access(directory, os.W_OK):
        raise PermissionError(f"No permission to write to directory: {directory}")
    
    return True

# File management helpers
def create_temp_file(extension='.txt') -> str:
    """Create a temporary file and return its path."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=TEMP_DIR)
    temp_file.close()
    return temp_file.name

def cleanup_temp_files(file_paths: List[str]) -> None:
    """Clean up temporary files."""
    for file_path in file_paths:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            logger.warning(f"Failed to remove temporary file {file_path}: {str(e)}")

# Core API functions
@track_performance
def parse_resume(file_path: str, resume_id: str = None, job_id=None) -> Dict:
    """
    Safely invoke resume parser with proper error handling.
    
    Args:
        file_path: Path to the resume file
        resume_id: Optional resume ID
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure
    """
    try:
        # Validate inputs
        validate_file_path(file_path)
        
        # Generate a resume ID if not provided
        if not resume_id:
            resume_id = f"resume_{str(uuid.uuid4())[:8]}"
            
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Resume Parser', parse_resume_file, file_path, resume_id)
        
        # Standard execution
        logger.info(f"Parsing resume from {file_path} with ID {resume_id}")
        result = parse_resume_file(file_path, resume_id)
        return result
    except Exception as e:
        logger.error(f"Resume parsing failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to parse resume: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def extract_keywords(job_description: str, job_id=None) -> Dict:
    """
    Safely invoke keyword extractor with proper error handling.
    
    Args:
        job_description: Text of the job description
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing extracted keywords
    """
    try:
        # Validate inputs
        validate_job_description(job_description)
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Keyword Extractor', extract_keywords_from_text, job_description)
        
        # Standard execution
        logger.info(f"Extracting keywords from job description ({len(job_description)} chars)")
        result = extract_keywords_from_text(job_description)
        return result
    except Exception as e:
        logger.error(f"Keyword extraction failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to extract keywords: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def perform_semantic_matching(resume_data: Dict, keywords_data: Dict, job_id=None) -> Dict:
    """
    Safely invoke the semantic matcher with proper error handling.
    
    Args:
        resume_data: Structured resume data
        keywords_data: Extracted keywords data
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing matches
    """
    try:
        # Validate inputs
        if not resume_data:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data",
                    'details': "Resume data must be provided"
                }
            }
        
        # Extract necessary information for matching
        keywords = keywords_data.get('keywords', [])
        if not keywords:
            return {
                'success': False,
                'error': {
                    'message': "No keywords available for matching",
                    'details': "Keyword extraction did not produce any keywords"
                }
            }
            
        # Function to perform the actual matching
        def do_semantic_matching(resume_data, keywords):
            # Create embeddings for resume content
            resume_text = ""
            
            # Extract skills
            skills = resume_data.get('skills', [])
            if skills:
                resume_text += "Skills: " + ", ".join(skills) + "\n\n"
                
            # Extract experience
            experiences = resume_data.get('experience', [])
            for exp in experiences:
                resume_text += f"Position: {exp.get('title')} at {exp.get('company')}\n"
                if 'description' in exp and isinstance(exp['description'], list):
                    resume_text += "Responsibilities:\n"
                    for item in exp['description']:
                        resume_text += f"- {item}\n"
                resume_text += "\n"
                
            # Extract education
            education = resume_data.get('education', [])
            for edu in education:
                resume_text += f"Education: {edu.get('degree')} from {edu.get('school')}\n"
                
            # Calculate matches using embeddings
            resume_embedding = create_embeddings(resume_text)
            
            matches = {}
            matched_keywords = []
            unmatched_keywords = []
            
            for keyword in keywords:
                keyword_embedding = create_embeddings(keyword)
                similarity = calculate_similarity(resume_embedding, keyword_embedding)
                
                matches[keyword] = {
                    'score': similarity,
                    'present': similarity > 0.7  # Threshold for considering a match
                }
                
                if similarity > 0.7:
                    matched_keywords.append(keyword)
                else:
                    unmatched_keywords.append(keyword)
                    
            return {
                'success': True,
                'data': {
                    'matches': matches,
                    'matched_keywords': matched_keywords,
                    'unmatched_keywords': unmatched_keywords,
                    'match_rate': len(matched_keywords) / len(keywords) if keywords else 0
                }
            }
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Semantic Matcher', do_semantic_matching, resume_data, keywords)
            
        # Standard execution
        logger.info(f"Performing semantic matching with {len(keywords)} keywords")
        result = do_semantic_matching(resume_data, keywords)
        return result
    except Exception as e:
        logger.error(f"Semantic matching failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to perform semantic matching: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def enhance_resume(resume_data: Dict, matches: Dict, job_id=None) -> Dict:
    """
    Safely invoke the resume enhancer with proper error handling.
    
    Args:
        resume_data: Structured resume data
        matches: Keyword matches from semantic matching
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing enhanced resume
    """
    try:
        # Validate inputs
        if not resume_data or not matches:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data or keyword matches",
                    'details': "Both resume data and keyword matches must be provided"
                }
            }
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'Resume Enhancer', enhance_resume_with_keywords, resume_data, matches)
            
        # Standard execution
        logger.info(f"Enhancing resume with {len(matches)} matched keywords")
        result = enhance_resume_with_keywords(resume_data, matches)
        return result
    except Exception as e:
        logger.error(f"Resume enhancement failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to enhance resume: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def generate_pdf(resume_data: Dict, output_path: str, job_id=None) -> Dict:
    """
    Safely use classic_template_adapter to generate PDF with proper error handling.
    
    Args:
        resume_data: Enhanced resume data
        output_path: Path to save the output PDF
        job_id: Optional pipeline job ID for diagnostics tracking
        
    Returns:
        Dict with standard response structure containing PDF path
    """
    try:
        # Validate inputs
        if not resume_data:
            return {
                'success': False,
                'error': {
                    'message': "Missing resume data",
                    'details': "Resume data must be provided"
                }
            }
        
        validate_output_path(output_path)
        
        # Create the PDF generator
        pdf_generator = create_pdf_generator()
        
        # Function to generate the PDF
        def do_generate_pdf(resume_data, output_path):
            result = pdf_generator.generate_pdf(resume_data, output_path)
            if result.get('success'):
                return {
                    'success': True,
                    'data': {
                        'output_path': output_path,
                        'timestamp': datetime.now().isoformat()
                    }
                }
            else:
                return result
        
        # If we have a diagnostic system and job_id, use pipeline tracking
        if diagnostic_system and job_id:
            return _track_pipeline_stage(job_id, 'PDF Generator', do_generate_pdf, resume_data, output_path)
            
        # Standard execution
        logger.info(f"Generating PDF at {output_path}")
        result = do_generate_pdf(resume_data, output_path)
        return result
    except Exception as e:
        logger.error(f"PDF generation failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Failed to generate PDF: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

@track_performance
def run_pipeline(resume_id: str, file_path: str, job_description: str) -> Dict:
    """
    Run the full resume optimization pipeline from parsing to enhancement.
    
    Args:
        resume_id: Resume ID
        file_path: Path to resume file
        job_description: Job description text
        
    Returns:
        Dict with standard response structure containing pipeline results
    """
    try:
        job_id = None
        if diagnostic_system:
            # Start a new pipeline job
            job_id = diagnostic_system.start_pipeline_job(
                resume_id, 
                Path(file_path).suffix[1:],
                job_description[:100] + '...' if len(job_description) > 100 else job_description
            )
        
        logger.info(f"Starting pipeline for resume {resume_id}")
        
        # Step 1: Parse resume
        parse_result = parse_resume(file_path, resume_id, job_id)
        if not parse_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', parse_result.get('error', {}).get('message'))
            return parse_result
        
        resume_data = parse_result.get('data', {})
        
        # Step 2: Extract keywords
        keywords_result = extract_keywords(job_description, job_id)
        if not keywords_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', keywords_result.get('error', {}).get('message'))
            return keywords_result
        
        keyword_data = keywords_result.get('data', {})
        
        # Step 3: Perform semantic matching
        matching_result = perform_semantic_matching(resume_data, keyword_data, job_id)
        if not matching_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', matching_result.get('error', {}).get('message'))
            return matching_result
        
        matches = matching_result.get('data', {}).get('matches', {})
        
        # Step 4: Enhance resume
        enhancement_result = enhance_resume(resume_data, matches, job_id)
        if not enhancement_result.get('success'):
            if diagnostic_system and job_id:
                diagnostic_system.complete_pipeline_job(job_id, 'error', enhancement_result.get('error', {}).get('message'))
            return enhancement_result
        
        enhanced_resume = enhancement_result.get('data', {}).get('enhanced_resume', {})
        
        # Mark pipeline job as completed
        if diagnostic_system and job_id:
            diagnostic_system.complete_pipeline_job(job_id, 'healthy', "Pipeline completed successfully")
        
        logger.info(f"Pipeline completed successfully for resume {resume_id}")
        return {
            'success': True,
            'data': {
                'original_resume': resume_data,
                'keywords': keyword_data,
                'matches': matching_result.get('data', {}),
                'enhanced_resume': enhanced_resume,
                'timestamp': datetime.now().isoformat()
            }
        }
    except Exception as e:
        if diagnostic_system and job_id:
            diagnostic_system.complete_pipeline_job(job_id, 'error', str(e))
            
        logger.error(f"Pipeline execution failed: {str(e)}")
        return {
            'success': False,
            'error': {
                'message': f"Pipeline execution failed: {str(e)}",
                'details': str(e),
                'traceback': traceback.format_exc() if logger.level <= logging.DEBUG else None
            }
        }

# Optional helper function for simple tasks
def get_resume_status(resume_id: str) -> Dict:
    """
    Get the status of a previously processed resume.
    
    Args:
        resume_id: Unique identifier for the resume
        
    Returns:
        Status information including file paths and processing state
    """
    try:
        if not resume_id:
            raise ValueError("Resume ID is required")
        
        output_path = os.path.join(OUTPUT_DIR, f"{resume_id}.pdf")
        
        if os.path.exists(output_path):
            return create_response(success=True, data={
                'resume_id': resume_id,
                'status': 'completed',
                'output_path': output_path,
                'file_size': os.path.getsize(output_path),
                'creation_time': datetime.fromtimestamp(os.path.getctime(output_path)).isoformat()
            })
        else:
            return create_response(success=True, data={
                'resume_id': resume_id,
                'status': 'not_found'
            })
            
    except Exception as e:
        logger.error(f"Error checking resume status: {str(e)}")
        return create_response(
            success=False,
            error={
                'message': str(e),
                'type': type(e).__name__,
                'resume_id': resume_id
            }
        ) 