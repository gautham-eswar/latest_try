import json
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from Pipeline.latex_resume.templates.classic_template import generate_latex_content

# Configure logging
logger = logging.getLogger(__name__)

# Constants for page sizing
DEFAULT_START_HEIGHT = 11.0  # Standard letter size
MAX_HEIGHT = 16.0  # Maximum reasonable height
HEIGHT_INCREMENT = 0.5  # How much to increase height on each attempt

def generate_latex_resume(resume_data: Dict[str, Any]) -> str:
    """
    Generate LaTeX content for a resume.
    
    Args:
        resume_data: The parsed resume data as a dictionary.
        
    Returns:
        String containing the LaTeX content.
    """
    # Use the template generator with default height
    return generate_latex_content(resume_data)

def generate_pdf_from_latex(resume_data: Dict[str, Any], output_path: Optional[str] = None) -> Tuple[str, bool]:
    """
    Generate a PDF from resume data with adaptive page sizing.
    
    This function will attempt to generate a single-page PDF by 
    incrementally adjusting the page height until the content fits on one page
    or the maximum height is reached.
    
    Args:
        resume_data: The parsed resume data as a dictionary
        output_path: Optional path to save the PDF. If None, a temporary file is used.
        
    Returns:
        Tuple of (pdf_path, success) where:
        - pdf_path is the path to the generated PDF
        - success is True if the PDF was successfully generated as a single page
    """
    logger.info("Starting PDF generation with adaptive page sizing")
    
    # Create a temporary directory for LaTeX compilation
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_dir_path = Path(temp_dir)
        tex_file_path = temp_dir_path / "resume.tex"
        
        # Initial height to try
        current_height = DEFAULT_START_HEIGHT
        single_page = False
        final_pdf_path = None
        
        # Try increasing heights until we get a single page or reach max height
        while current_height <= MAX_HEIGHT and not single_page:
            logger.info(f"Attempting PDF generation with height: {current_height} inches")
            
            # Generate LaTeX with specific height
            try:
                current_latex = generate_latex_content(resume_data, page_height=current_height)
                
                # Write to temporary .tex file
                with open(tex_file_path, 'w', encoding='utf-8') as f:
                    f.write(current_latex)
                
                # Compile LaTeX to PDF (run twice for references)
                os.chdir(temp_dir)
                subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_file_path.name], 
                              check=True, stdout=subprocess.DEVNULL)
                subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_file_path.name], 
                              check=True, stdout=subprocess.DEVNULL)
                
                # Check if PDF is single page
                pdf_path = temp_dir_path / "resume.pdf"
                if pdf_path.exists():
                    try:
                        # Try to use pdfinfo if available
                        result = subprocess.run(['pdfinfo', pdf_path], 
                                              capture_output=True, text=True, check=True)
                        for line in result.stdout.split('\n'):
                            if line.startswith('Pages:'):
                                num_pages = int(line.split(':')[1].strip())
                                if num_pages == 1:
                                    single_page = True
                                    logger.info(f"Success! PDF fits on one page with height {current_height}in")
                                else:
                                    logger.info(f"PDF has {num_pages} pages with height {current_height}in")
                                break
                    except (subprocess.SubprocessError, FileNotFoundError):
                        # Fall back to checking log file if pdfinfo isn't available
                        log_path = temp_dir_path / "resume.log"
                        if log_path.exists():
                            with open(log_path, 'r', encoding='utf-8') as log_file:
                                log_content = log_file.read()
                                page_match = None
                                for line in log_content.split('\n'):
                                    if 'Output written on' in line and 'page' in line:
                                        page_match = line
                                
                                if page_match:
                                    if '(1 page' in page_match:
                                        single_page = True
                                        logger.info(f"Success! PDF fits on one page with height {current_height}in")
                                    else:
                                        logger.info(f"PDF still multi-page with height {current_height}in")
                    
                    # If we've found a single page solution or reached max height, copy to final destination
                    if single_page or current_height >= MAX_HEIGHT:
                        if output_path:
                            import shutil
                            output_pdf_path = Path(output_path)
                            # Create parent directories if they don't exist
                            os.makedirs(output_pdf_path.parent, exist_ok=True)
                            # Copy the PDF to the specified output path
                            shutil.copy2(pdf_path, output_path)
                            final_pdf_path = output_path
                        else:
                            # Without an output path, we create a new temporary file
                            import shutil
                            temp_pdf_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
                            temp_pdf_file.close()
                            shutil.copy2(pdf_path, temp_pdf_file.name)
                            final_pdf_path = temp_pdf_file.name
                
            except Exception as e:
                logger.error(f"Error during PDF generation attempt: {e}")
                # Continue to try the next height
            
            # Increment height for next attempt if needed
            if not single_page:
                current_height += HEIGHT_INCREMENT
    
    # Return results
    if final_pdf_path:
        logger.info(f"PDF generation complete. File saved to: {final_pdf_path}")
        return final_pdf_path, single_page
    else:
        logger.error("PDF generation failed after all attempts")
        return "", False

def generate_resume_pdf(resume_data: Dict[str, Any], output_path: Optional[str] = None) -> Tuple[str, bool]:
    """
    End-to-end function to generate a PDF resume from resume data.
    
    This is the main entry point that should be called from other parts of the application.
    
    Args:
        resume_data: The parsed resume data as a dictionary
        output_path: Optional path to save the PDF
        
    Returns:
        Tuple of (pdf_path, success)
    """
    logger.info("Starting end-to-end resume PDF generation")
    
    try:
        return generate_pdf_from_latex(resume_data, output_path)
    except Exception as e:
        logger.error(f"Error in end-to-end PDF generation: {e}")
        return "", False