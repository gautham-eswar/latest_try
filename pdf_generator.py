import os
import logging
import tempfile
import shutil
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union

# Import existing template adapter if available
try:
    from classic_template_adapter import format_resume_data_for_template, generate_resume_latex
except ImportError:
    # Fallback implementations if the actual modules aren't available
    def format_resume_data_for_template(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback format function when the real one isn't available."""
        logging.warning("Using fallback format_resume_data_for_template function")
        return resume_data
    
    def generate_resume_latex(template_data: Dict[str, Any]) -> str:
        """Fallback LaTeX generator when the real one isn't available."""
        logging.warning("Using fallback generate_resume_latex function")
        return "% Fallback LaTeX template\n\\documentclass{article}\n\\begin{document}\nUnable to generate proper resume.\n\\end{document}"

# Configure logging
logger = logging.getLogger('pdf_generator')

class ResumePDFGenerator:
    """
    A class to generate PDF resumes from resume data using LaTeX templates.
    
    This class handles the entire process of:
    1. Formatting resume data for the template
    2. Generating LaTeX source code
    3. Compiling LaTeX to PDF
    4. Managing temporary files and cleanup
    """
    
    def __init__(self, template_dir: Optional[str] = None, temp_dir: Optional[str] = None):
        """
        Initialize the PDF generator with template directory and temp directory.
        
        Args:
            template_dir: Directory containing LaTeX templates
            temp_dir: Directory for temporary files (created automatically if None)
        """
        self.template_dir = template_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.temp_dir = temp_dir
        
        # Ensure template directory exists
        if not os.path.exists(self.template_dir):
            try:
                os.makedirs(self.template_dir, exist_ok=True)
                logger.info(f"Created template directory: {self.template_dir}")
            except Exception as e:
                logger.error(f"Failed to create template directory: {e}")
        
        # Check for required executables
        self.pdflatex_available = self._check_pdflatex_available()
        if not self.pdflatex_available:
            logger.warning("pdflatex not found in system path. PDF generation will be limited.")
    
    def _check_pdflatex_available(self) -> bool:
        """Check if pdflatex is available in the system path."""
        try:
            # Different command syntax for Windows vs Unix-like systems
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['where', 'pdflatex'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    ['which', 'pdflatex'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5
                )
            
            available = result.returncode == 0
            logger.info(f"pdflatex {'available' if available else 'not available'} in system path")
            return available
        
        except Exception as e:
            logger.warning(f"Error checking for pdflatex: {e}")
            return False
    
    def generate_pdf(self, resume_data: Dict[str, Any], output_path: str, 
                     cleanup: bool = True) -> Dict[str, Any]:
        """
        Generate a PDF resume from resume data and save it to the specified path.
        
        Args:
            resume_data: Dictionary containing resume data
            output_path: Path where the output PDF should be saved
            cleanup: Whether to clean up temporary files (default: True)
            
        Returns:
            Dictionary with result status, PDF path, and any error information
        """
        logger.info(f"Starting PDF generation for output: {output_path}")
        temp_dir = None
        latex_path = None
        log_path = None
        
        start_time = datetime.now()
        
        try:
            # Input validation
            if not resume_data:
                raise ValueError("Resume data cannot be empty")
            
            if not output_path:
                raise ValueError("Output path cannot be empty")
            
            # Create temp directory for LaTeX files
            temp_dir = self._create_temp_directory()
            logger.debug(f"Created temporary directory: {temp_dir}")
            
            # Generate LaTeX source
            latex_result = self.generate_latex(resume_data)
            if not latex_result['success']:
                raise RuntimeError(f"Failed to generate LaTeX: {latex_result.get('error', 'Unknown error')}")
            
            latex_content = latex_result['latex_content']
            
            # Write LaTeX content to file
            latex_filename = f"resume_{start_time.strftime('%Y%m%d_%H%M%S')}.tex"
            latex_path = os.path.join(temp_dir, latex_filename)
            
            with open(latex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            logger.debug(f"LaTeX source written to: {latex_path}")
            
            # If pdflatex is available, compile to PDF
            if self.pdflatex_available:
                compile_result = self.compile_latex_to_pdf(latex_path, output_path)
                
                if not compile_result['success']:
                    logger.error(f"PDF compilation failed: {compile_result.get('error', 'Unknown error')}")
                    
                    # Copy LaTeX file and log file as fallback
                    output_dir = os.path.dirname(output_path)
                    latex_fallback_path = os.path.join(output_dir, os.path.basename(latex_path))
                    shutil.copy2(latex_path, latex_fallback_path)
                    
                    # Also copy log file if it exists
                    log_path = os.path.splitext(latex_path)[0] + '.log'
                    if os.path.exists(log_path):
                        log_fallback_path = os.path.join(output_dir, os.path.basename(log_path))
                        shutil.copy2(log_path, log_fallback_path)
                    
                    return {
                        'success': False,
                        'latex_path': latex_fallback_path,
                        'log_path': log_fallback_path if os.path.exists(log_path) else None,
                        'error': compile_result.get('error', 'PDF compilation failed'),
                        'execution_time': (datetime.now() - start_time).total_seconds()
                    }
                
                logger.info(f"Successfully generated PDF at: {output_path}")
                
                return {
                    'success': True,
                    'pdf_path': output_path,
                    'latex_path': latex_path if not cleanup else None,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            else:
                # If pdflatex isn't available, save the LaTeX as a fallback
                output_dir = os.path.dirname(output_path)
                latex_fallback_path = os.path.join(output_dir, os.path.basename(latex_path))
                shutil.copy2(latex_path, latex_fallback_path)
                
                logger.warning(f"pdflatex not available, output written to: {latex_fallback_path}")
                
                return {
                    'success': False,
                    'latex_path': latex_fallback_path,
                    'error': "pdflatex not available on system",
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"PDF generation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'latex_path': latex_path,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
            
        finally:
            # Clean up temporary directory if requested
            if cleanup and temp_dir and os.path.exists(temp_dir):
                try:
                    self._cleanup_temp_files(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary directory: {e}")
    
    def generate_latex(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate LaTeX source for a resume without compiling to PDF.
        
        Args:
            resume_data: Dictionary containing resume data
            
        Returns:
            Dictionary with result status, LaTeX content, and any error information
        """
        start_time = datetime.now()
        
        try:
            # Input validation
            if not resume_data:
                raise ValueError("Resume data cannot be empty")
            
            # Format resume data for the template
            logger.debug("Formatting resume data for template")
            template_data = format_resume_data_for_template(resume_data)
            
            # Generate LaTeX source
            logger.debug("Generating LaTeX source from template data")
            latex_content = generate_resume_latex(template_data)
            
            if not latex_content:
                raise ValueError("Generated LaTeX content is empty")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully generated LaTeX in {execution_time:.3f}s")
            
            return {
                'success': True,
                'latex_content': latex_content,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"LaTeX generation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
    
    def compile_latex_to_pdf(self, latex_path: str, output_path: str, 
                            max_runs: int = 2) -> Dict[str, Any]:
        """
        Compile a LaTeX file to PDF using pdflatex.
        
        Args:
            latex_path: Path to LaTeX file
            output_path: Path where the output PDF should be saved
            max_runs: Maximum number of pdflatex runs (for references)
            
        Returns:
            Dictionary with result status, paths, and any error information
        """
        start_time = datetime.now()
        
        try:
            # Input validation
            if not latex_path or not os.path.exists(latex_path):
                raise FileNotFoundError(f"LaTeX file not found: {latex_path}")
            
            if not output_path:
                raise ValueError("Output path cannot be empty")
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.debug(f"Created output directory: {output_dir}")
            
            # Get directory and filename
            work_dir = os.path.dirname(latex_path)
            filename = os.path.basename(latex_path)
            
            # Compile with pdflatex
            logger.debug(f"Compiling {latex_path} with pdflatex")
            
            for run in range(max_runs):
                logger.debug(f"pdflatex run {run+1}/{max_runs}")
                
                process = subprocess.run(
                    [
                        'pdflatex', 
                        '-interaction=nonstopmode',
                        '-halt-on-error',
                        filename
                    ],
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # Timeout after 30 seconds
                )
                
                log_path = os.path.join(work_dir, os.path.splitext(filename)[0] + '.log')
                
                if process.returncode != 0:
                    error_message = process.stderr.decode('utf-8', errors='replace')
                    logger.error(f"pdflatex compilation failed with code {process.returncode}: {error_message}")
                    
                    # Check if log file exists and extract more detailed error
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                                log_content = f.read()
                                # Extract error message - typically after "! "
                                error_lines = [line for line in log_content.split('\n') if line.startswith('!')]
                                if error_lines:
                                    error_message = '\n'.join(error_lines)
                        except Exception as log_e:
                            logger.warning(f"Error reading log file: {log_e}")
                    
                    return {
                        'success': False,
                        'error': f"LaTeX compilation error: {error_message}",
                        'log_path': log_path if os.path.exists(log_path) else None,
                        'execution_time': (datetime.now() - start_time).total_seconds()
                    }
            
            # Get the generated PDF path
            pdf_path = os.path.join(work_dir, os.path.splitext(filename)[0] + '.pdf')
            
            if not os.path.exists(pdf_path):
                return {
                    'success': False,
                    'error': "PDF file was not generated",
                    'log_path': log_path if os.path.exists(log_path) else None,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Move the generated PDF to the desired output path
            shutil.copy2(pdf_path, output_path)
            logger.debug(f"Copied PDF from {pdf_path} to {output_path}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully compiled PDF in {execution_time:.3f}s")
            
            return {
                'success': True,
                'pdf_path': output_path,
                'log_path': log_path if os.path.exists(log_path) else None,
                'execution_time': execution_time
            }
            
        except subprocess.TimeoutExpired:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"pdflatex process timed out after {execution_time:.3f}s")
            
            return {
                'success': False,
                'error': "LaTeX compilation timed out",
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"PDF compilation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
    
    def _create_temp_directory(self) -> str:
        """
        Create a temporary directory for LaTeX files.
        
        Returns:
            Path to the created temporary directory
        """
        try:
            if self.temp_dir and not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                logger.debug(f"Created configured temp directory: {self.temp_dir}")
                
            # Create a temporary directory
            if self.temp_dir:
                # Create a subdirectory in the configured temp dir
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                temp_dir = os.path.join(self.temp_dir, f"resume_latex_{timestamp}")
                os.makedirs(temp_dir, exist_ok=True)
            else:
                # Use system temp directory
                temp_dir = tempfile.mkdtemp(prefix="resume_latex_")
            
            return temp_dir
            
        except Exception as e:
            logger.exception(f"Failed to create temporary directory: {e}")
            raise
    
    def _cleanup_temp_files(self, temp_dir: str) -> bool:
        """
        Clean up temporary files and directory.
        
        Args:
            temp_dir: Path to temporary directory to clean up
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            if not temp_dir or not os.path.exists(temp_dir):
                logger.warning(f"Temp directory does not exist: {temp_dir}")
                return False
            
            # Remove all files in the directory
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    else:
                        shutil.rmtree(item_path)
                except Exception as e:
                    logger.warning(f"Failed to remove {item_path}: {e}")
            
            # Remove the directory itself
            shutil.rmtree(temp_dir)
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to clean up temporary directory {temp_dir}: {e}")
            return False

    def check_environment(self) -> Dict[str, Any]:
        """
        Check the PDF generation environment and return status information.
        
        Returns:
            Dictionary with environment status information
        """
        status = {
            'pdflatex_available': self.pdflatex_available,
            'template_dir_exists': os.path.exists(self.template_dir),
            'temp_dir_exists': self.temp_dir is None or os.path.exists(self.temp_dir),
            'template_dir': self.template_dir,
            'temp_dir': self.temp_dir,
            'system': platform.system()
        }
        
        # Check for pdflatex version if available
        if self.pdflatex_available:
            try:
                process = subprocess.run(
                    ['pdflatex', '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                version_output = process.stdout.decode('utf-8', errors='replace')
                # Extract version from first line
                version = version_output.split('\n')[0] if version_output else "Unknown"
                status['pdflatex_version'] = version
            except Exception as e:
                logger.warning(f"Failed to get pdflatex version: {e}")
                status['pdflatex_version'] = "Error checking version"
        
        return status


def create_pdf_generator(template_dir: Optional[str] = None, 
                         temp_dir: Optional[str] = None) -> ResumePDFGenerator:
    """
    Factory function to create a PDF generator instance.
    
    Args:
        template_dir: Directory containing LaTeX templates
        temp_dir: Directory for temporary files
        
    Returns:
        ResumePDFGenerator instance
    """
    return ResumePDFGenerator(template_dir=template_dir, temp_dir=temp_dir)


# Example usage
if __name__ == '__main__':
    # Configure logging for the example
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a PDF generator
    generator = create_pdf_generator()
    
    # Check environment
    env_status = generator.check_environment()
    print(f"PDF Generation Environment:")
    for key, value in env_status.items():
        print(f"  {key}: {value}")
    
    # Sample resume data (would come from your resume parser)
    sample_resume = {
        'contact': {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'phone': '(555) 123-4567',
            'address': '123 Main St, Anytown, USA'
        },
        'education': [
            {
                'degree': 'Bachelor of Science in Computer Science',
                'school': 'University of Technology',
                'year': '2015-2019',
                'gpa': '3.8/4.0'
            }
        ],
        'experience': [
            {
                'title': 'Software Engineer',
                'company': 'Tech Solutions Inc.',
                'duration': 'Jan 2020 - Present',
                'description': [
                    'Developed web applications using React and Node.js',
                    'Improved system performance by 40%'
                ]
            }
        ]
    }
    
    # Generate PDF example
    if generator.pdflatex_available:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'example_resume.pdf')
        result = generator.generate_pdf(sample_resume, output_path)
        
        if result['success']:
            print(f"PDF generated successfully at {result['pdf_path']}")
        else:
            print(f"PDF generation failed: {result['error']}")
    else:
        print("PDF generation not available (pdflatex not found)")
        
        # Generate LaTeX only
        latex_result = generator.generate_latex(sample_resume)
        if latex_result['success']:
            print("LaTeX generated successfully:")
            print(latex_result['latex_content'][:100] + "...")  # Show first 100 chars
        else:
            print(f"LaTeX generation failed: {latex_result['error']}") 
import logging
import tempfile
import shutil
import subprocess
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List, Union

# Import existing template adapter if available
try:
    from classic_template_adapter import format_resume_data_for_template, generate_resume_latex
except ImportError:
    # Fallback implementations if the actual modules aren't available
    def format_resume_data_for_template(resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback format function when the real one isn't available."""
        logging.warning("Using fallback format_resume_data_for_template function")
        return resume_data
    
    def generate_resume_latex(template_data: Dict[str, Any]) -> str:
        """Fallback LaTeX generator when the real one isn't available."""
        logging.warning("Using fallback generate_resume_latex function")
        return "% Fallback LaTeX template\n\\documentclass{article}\n\\begin{document}\nUnable to generate proper resume.\n\\end{document}"

# Configure logging
logger = logging.getLogger('pdf_generator')

class ResumePDFGenerator:
    """
    A class to generate PDF resumes from resume data using LaTeX templates.
    
    This class handles the entire process of:
    1. Formatting resume data for the template
    2. Generating LaTeX source code
    3. Compiling LaTeX to PDF
    4. Managing temporary files and cleanup
    """
    
    def __init__(self, template_dir: Optional[str] = None, temp_dir: Optional[str] = None):
        """
        Initialize the PDF generator with template directory and temp directory.
        
        Args:
            template_dir: Directory containing LaTeX templates
            temp_dir: Directory for temporary files (created automatically if None)
        """
        self.template_dir = template_dir or os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
        self.temp_dir = temp_dir
        
        # Ensure template directory exists
        if not os.path.exists(self.template_dir):
            try:
                os.makedirs(self.template_dir, exist_ok=True)
                logger.info(f"Created template directory: {self.template_dir}")
            except Exception as e:
                logger.error(f"Failed to create template directory: {e}")
        
        # Check for required executables
        self.pdflatex_available = self._check_pdflatex_available()
        if not self.pdflatex_available:
            logger.warning("pdflatex not found in system path. PDF generation will be limited.")
    
    def _check_pdflatex_available(self) -> bool:
        """Check if pdflatex is available in the system path."""
        try:
            # Different command syntax for Windows vs Unix-like systems
            if platform.system() == 'Windows':
                result = subprocess.run(
                    ['where', 'pdflatex'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5
                )
            else:
                result = subprocess.run(
                    ['which', 'pdflatex'], 
                    stdout=subprocess.PIPE, 
                    stderr=subprocess.PIPE,
                    check=False,
                    timeout=5
                )
            
            available = result.returncode == 0
            logger.info(f"pdflatex {'available' if available else 'not available'} in system path")
            return available
        
        except Exception as e:
            logger.warning(f"Error checking for pdflatex: {e}")
            return False
    
    def generate_pdf(self, resume_data: Dict[str, Any], output_path: str, 
                     cleanup: bool = True) -> Dict[str, Any]:
        """
        Generate a PDF resume from resume data and save it to the specified path.
        
        Args:
            resume_data: Dictionary containing resume data
            output_path: Path where the output PDF should be saved
            cleanup: Whether to clean up temporary files (default: True)
            
        Returns:
            Dictionary with result status, PDF path, and any error information
        """
        logger.info(f"Starting PDF generation for output: {output_path}")
        temp_dir = None
        latex_path = None
        log_path = None
        
        start_time = datetime.now()
        
        try:
            # Input validation
            if not resume_data:
                raise ValueError("Resume data cannot be empty")
            
            if not output_path:
                raise ValueError("Output path cannot be empty")
            
            # Create temp directory for LaTeX files
            temp_dir = self._create_temp_directory()
            logger.debug(f"Created temporary directory: {temp_dir}")
            
            # Generate LaTeX source
            latex_result = self.generate_latex(resume_data)
            if not latex_result['success']:
                raise RuntimeError(f"Failed to generate LaTeX: {latex_result.get('error', 'Unknown error')}")
            
            latex_content = latex_result['latex_content']
            
            # Write LaTeX content to file
            latex_filename = f"resume_{start_time.strftime('%Y%m%d_%H%M%S')}.tex"
            latex_path = os.path.join(temp_dir, latex_filename)
            
            with open(latex_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            logger.debug(f"LaTeX source written to: {latex_path}")
            
            # If pdflatex is available, compile to PDF
            if self.pdflatex_available:
                compile_result = self.compile_latex_to_pdf(latex_path, output_path)
                
                if not compile_result['success']:
                    logger.error(f"PDF compilation failed: {compile_result.get('error', 'Unknown error')}")
                    
                    # Copy LaTeX file and log file as fallback
                    output_dir = os.path.dirname(output_path)
                    latex_fallback_path = os.path.join(output_dir, os.path.basename(latex_path))
                    shutil.copy2(latex_path, latex_fallback_path)
                    
                    # Also copy log file if it exists
                    log_path = os.path.splitext(latex_path)[0] + '.log'
                    if os.path.exists(log_path):
                        log_fallback_path = os.path.join(output_dir, os.path.basename(log_path))
                        shutil.copy2(log_path, log_fallback_path)
                    
                    return {
                        'success': False,
                        'latex_path': latex_fallback_path,
                        'log_path': log_fallback_path if os.path.exists(log_path) else None,
                        'error': compile_result.get('error', 'PDF compilation failed'),
                        'execution_time': (datetime.now() - start_time).total_seconds()
                    }
                
                logger.info(f"Successfully generated PDF at: {output_path}")
                
                return {
                    'success': True,
                    'pdf_path': output_path,
                    'latex_path': latex_path if not cleanup else None,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            else:
                # If pdflatex isn't available, save the LaTeX as a fallback
                output_dir = os.path.dirname(output_path)
                latex_fallback_path = os.path.join(output_dir, os.path.basename(latex_path))
                shutil.copy2(latex_path, latex_fallback_path)
                
                logger.warning(f"pdflatex not available, output written to: {latex_fallback_path}")
                
                return {
                    'success': False,
                    'latex_path': latex_fallback_path,
                    'error': "pdflatex not available on system",
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
        
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"PDF generation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'latex_path': latex_path,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
            
        finally:
            # Clean up temporary directory if requested
            if cleanup and temp_dir and os.path.exists(temp_dir):
                try:
                    self._cleanup_temp_files(temp_dir)
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    logger.warning(f"Failed to clean up temporary directory: {e}")
    
    def generate_latex(self, resume_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate LaTeX source for a resume without compiling to PDF.
        
        Args:
            resume_data: Dictionary containing resume data
            
        Returns:
            Dictionary with result status, LaTeX content, and any error information
        """
        start_time = datetime.now()
        
        try:
            # Input validation
            if not resume_data:
                raise ValueError("Resume data cannot be empty")
            
            # Format resume data for the template
            logger.debug("Formatting resume data for template")
            template_data = format_resume_data_for_template(resume_data)
            
            # Generate LaTeX source
            logger.debug("Generating LaTeX source from template data")
            latex_content = generate_resume_latex(template_data)
            
            if not latex_content:
                raise ValueError("Generated LaTeX content is empty")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully generated LaTeX in {execution_time:.3f}s")
            
            return {
                'success': True,
                'latex_content': latex_content,
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"LaTeX generation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
    
    def compile_latex_to_pdf(self, latex_path: str, output_path: str, 
                            max_runs: int = 2) -> Dict[str, Any]:
        """
        Compile a LaTeX file to PDF using pdflatex.
        
        Args:
            latex_path: Path to LaTeX file
            output_path: Path where the output PDF should be saved
            max_runs: Maximum number of pdflatex runs (for references)
            
        Returns:
            Dictionary with result status, paths, and any error information
        """
        start_time = datetime.now()
        
        try:
            # Input validation
            if not latex_path or not os.path.exists(latex_path):
                raise FileNotFoundError(f"LaTeX file not found: {latex_path}")
            
            if not output_path:
                raise ValueError("Output path cannot be empty")
            
            # Ensure output directory exists
            output_dir = os.path.dirname(output_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)
                logger.debug(f"Created output directory: {output_dir}")
            
            # Get directory and filename
            work_dir = os.path.dirname(latex_path)
            filename = os.path.basename(latex_path)
            
            # Compile with pdflatex
            logger.debug(f"Compiling {latex_path} with pdflatex")
            
            for run in range(max_runs):
                logger.debug(f"pdflatex run {run+1}/{max_runs}")
                
                process = subprocess.run(
                    [
                        'pdflatex', 
                        '-interaction=nonstopmode',
                        '-halt-on-error',
                        filename
                    ],
                    cwd=work_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=30  # Timeout after 30 seconds
                )
                
                log_path = os.path.join(work_dir, os.path.splitext(filename)[0] + '.log')
                
                if process.returncode != 0:
                    error_message = process.stderr.decode('utf-8', errors='replace')
                    logger.error(f"pdflatex compilation failed with code {process.returncode}: {error_message}")
                    
                    # Check if log file exists and extract more detailed error
                    if os.path.exists(log_path):
                        try:
                            with open(log_path, 'r', encoding='utf-8', errors='replace') as f:
                                log_content = f.read()
                                # Extract error message - typically after "! "
                                error_lines = [line for line in log_content.split('\n') if line.startswith('!')]
                                if error_lines:
                                    error_message = '\n'.join(error_lines)
                        except Exception as log_e:
                            logger.warning(f"Error reading log file: {log_e}")
                    
                    return {
                        'success': False,
                        'error': f"LaTeX compilation error: {error_message}",
                        'log_path': log_path if os.path.exists(log_path) else None,
                        'execution_time': (datetime.now() - start_time).total_seconds()
                    }
            
            # Get the generated PDF path
            pdf_path = os.path.join(work_dir, os.path.splitext(filename)[0] + '.pdf')
            
            if not os.path.exists(pdf_path):
                return {
                    'success': False,
                    'error': "PDF file was not generated",
                    'log_path': log_path if os.path.exists(log_path) else None,
                    'execution_time': (datetime.now() - start_time).total_seconds()
                }
            
            # Move the generated PDF to the desired output path
            shutil.copy2(pdf_path, output_path)
            logger.debug(f"Copied PDF from {pdf_path} to {output_path}")
            
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.info(f"Successfully compiled PDF in {execution_time:.3f}s")
            
            return {
                'success': True,
                'pdf_path': output_path,
                'log_path': log_path if os.path.exists(log_path) else None,
                'execution_time': execution_time
            }
            
        except subprocess.TimeoutExpired:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.error(f"pdflatex process timed out after {execution_time:.3f}s")
            
            return {
                'success': False,
                'error': "LaTeX compilation timed out",
                'execution_time': execution_time
            }
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            logger.exception(f"PDF compilation failed after {execution_time:.3f}s: {str(e)}")
            
            return {
                'success': False,
                'error': {
                    'message': str(e),
                    'type': type(e).__name__
                },
                'execution_time': execution_time
            }
    
    def _create_temp_directory(self) -> str:
        """
        Create a temporary directory for LaTeX files.
        
        Returns:
            Path to the created temporary directory
        """
        try:
            if self.temp_dir and not os.path.exists(self.temp_dir):
                os.makedirs(self.temp_dir, exist_ok=True)
                logger.debug(f"Created configured temp directory: {self.temp_dir}")
                
            # Create a temporary directory
            if self.temp_dir:
                # Create a subdirectory in the configured temp dir
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                temp_dir = os.path.join(self.temp_dir, f"resume_latex_{timestamp}")
                os.makedirs(temp_dir, exist_ok=True)
            else:
                # Use system temp directory
                temp_dir = tempfile.mkdtemp(prefix="resume_latex_")
            
            return temp_dir
            
        except Exception as e:
            logger.exception(f"Failed to create temporary directory: {e}")
            raise
    
    def _cleanup_temp_files(self, temp_dir: str) -> bool:
        """
        Clean up temporary files and directory.
        
        Args:
            temp_dir: Path to temporary directory to clean up
            
        Returns:
            True if cleanup was successful, False otherwise
        """
        try:
            if not temp_dir or not os.path.exists(temp_dir):
                logger.warning(f"Temp directory does not exist: {temp_dir}")
                return False
            
            # Remove all files in the directory
            for item in os.listdir(temp_dir):
                item_path = os.path.join(temp_dir, item)
                try:
                    if os.path.isfile(item_path):
                        os.unlink(item_path)
                    else:
                        shutil.rmtree(item_path)
                except Exception as e:
                    logger.warning(f"Failed to remove {item_path}: {e}")
            
            # Remove the directory itself
            shutil.rmtree(temp_dir)
            
            return True
            
        except Exception as e:
            logger.exception(f"Failed to clean up temporary directory {temp_dir}: {e}")
            return False

    def check_environment(self) -> Dict[str, Any]:
        """
        Check the PDF generation environment and return status information.
        
        Returns:
            Dictionary with environment status information
        """
        status = {
            'pdflatex_available': self.pdflatex_available,
            'template_dir_exists': os.path.exists(self.template_dir),
            'temp_dir_exists': self.temp_dir is None or os.path.exists(self.temp_dir),
            'template_dir': self.template_dir,
            'temp_dir': self.temp_dir,
            'system': platform.system()
        }
        
        # Check for pdflatex version if available
        if self.pdflatex_available:
            try:
                process = subprocess.run(
                    ['pdflatex', '--version'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5
                )
                version_output = process.stdout.decode('utf-8', errors='replace')
                # Extract version from first line
                version = version_output.split('\n')[0] if version_output else "Unknown"
                status['pdflatex_version'] = version
            except Exception as e:
                logger.warning(f"Failed to get pdflatex version: {e}")
                status['pdflatex_version'] = "Error checking version"
        
        return status


def create_pdf_generator(template_dir: Optional[str] = None, 
                         temp_dir: Optional[str] = None) -> ResumePDFGenerator:
    """
    Factory function to create a PDF generator instance.
    
    Args:
        template_dir: Directory containing LaTeX templates
        temp_dir: Directory for temporary files
        
    Returns:
        ResumePDFGenerator instance
    """
    return ResumePDFGenerator(template_dir=template_dir, temp_dir=temp_dir)


# Example usage
if __name__ == '__main__':
    # Configure logging for the example
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create a PDF generator
    generator = create_pdf_generator()
    
    # Check environment
    env_status = generator.check_environment()
    print(f"PDF Generation Environment:")
    for key, value in env_status.items():
        print(f"  {key}: {value}")
    
    # Sample resume data (would come from your resume parser)
    sample_resume = {
        'contact': {
            'name': 'John Doe',
            'email': 'john.doe@example.com',
            'phone': '(555) 123-4567',
            'address': '123 Main St, Anytown, USA'
        },
        'education': [
            {
                'degree': 'Bachelor of Science in Computer Science',
                'school': 'University of Technology',
                'year': '2015-2019',
                'gpa': '3.8/4.0'
            }
        ],
        'experience': [
            {
                'title': 'Software Engineer',
                'company': 'Tech Solutions Inc.',
                'duration': 'Jan 2020 - Present',
                'description': [
                    'Developed web applications using React and Node.js',
                    'Improved system performance by 40%'
                ]
            }
        ]
    }
    
    # Generate PDF example
    if generator.pdflatex_available:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'example_resume.pdf')
        result = generator.generate_pdf(sample_resume, output_path)
        
        if result['success']:
            print(f"PDF generated successfully at {result['pdf_path']}")
        else:
            print(f"PDF generation failed: {result['error']}")
    else:
        print("PDF generation not available (pdflatex not found)")
        
        # Generate LaTeX only
        latex_result = generator.generate_latex(sample_resume)
        if latex_result['success']:
            print("LaTeX generated successfully:")
            print(latex_result['latex_content'][:100] + "...")  # Show first 100 chars
        else:
            print(f"LaTeX generation failed: {latex_result['error']}") 