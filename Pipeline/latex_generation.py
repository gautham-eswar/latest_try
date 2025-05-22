import json
import os
import subprocess
import tempfile
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import copy
import shutil

from Pipeline.latex_resume.templates.resume_generator import generate_latex_content, clear_api_cache_diagnostic

# Configure logging
logger = logging.getLogger(__name__)

# Constants for page sizing
DEFAULT_START_HEIGHT = 11.0  # Standard letter size
MIN_HEIGHT_INCHES = 11.0
MAX_HEIGHT_INCHES = 20.0  # Maximum page height (inches) before falling back to multi-page output
MAX_ITERATIONS_PER_HEIGHT = 2 # Max recompilations for a given height if bibtex is needed.
HEIGHT_INCREMENT = 0.5

# Helper for floating point range
def frange(start, stop, step):
    """Generate a range of floating point numbers."""
    current = start
    while current < stop:
        yield current
        current += step

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
    Tries to fit content on a single page by iteratively increasing page height.
    
    Args:
        resume_data: The parsed resume data as a dictionary
        output_path: Optional path to save the PDF. If None, a temporary file is used.
        
    Returns:
        Tuple of (pdf_path, success) where:
        - pdf_path is the path to the generated PDF
        - success is True if the PDF was successfully generated as a single page
    """
    logger.info("Starting PDF generation with adaptive page sizing")
    
    # Clear the API_CACHE from resume_generator module via its utility function
    clear_api_cache_diagnostic()
    logger.info("Called clear_api_cache_diagnostic() from resume_generator.")

    original_cwd = os.getcwd()  # Save current working directory
    final_pdf_path_str = ""
    success = False

    heights_to_try = list(frange(MIN_HEIGHT_INCHES, MAX_HEIGHT_INCHES + HEIGHT_INCREMENT, HEIGHT_INCREMENT))
    
    # Create a temporary directory for LaTeX processing
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir_path = Path(temp_dir_name)
        tex_file_name = "resume.tex"
        pdf_file_name = "resume.pdf"
        tex_file_path = temp_dir_path / tex_file_name
        
        for current_height in heights_to_try:
            logger.info(f"Attempting PDF generation with height: {current_height:.1f} inches")
            page_height_setting_tex = f"\\addtolength{{\\textheight}}{{{(current_height - MIN_HEIGHT_INCHES) * 72.27:.1f}pt}}"
            
            latex_content = generate_latex_content(resume_data, page_height_setting_tex=page_height_setting_tex)
            with open(tex_file_path, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            
            # Save .tex for inspection if output_path is provided (even if compilation fails for this height)
            if output_path:
                try:
                    base_name = Path(output_path).stem
                    tex_output_dir = Path(output_path).parent
                    inspection_tex_path = tex_output_dir / f"{base_name}_{current_height:.1f}in.tex"
                    # shutil.copy(tex_file_path, inspection_tex_path)
                    # logger.info(f"Saved .tex for inspection: {inspection_tex_path}")
                except Exception as e:
                    logger.warning(f"Could not save inspection .tex file: {e}")

            os.chdir(temp_dir_path) # Change to temp dir for latexmk
            
            compilation_successful_this_iteration = False
            for _ in range(MAX_ITERATIONS_PER_HEIGHT): #通常は1回、bibtexなどを使う場合は2回以上必要
                cmd = [
                    "pdflatex",  # Use pdflatex directly instead of latexmk for better error diagnostics
                    "-interaction=nonstopmode",
                    tex_file_name
                ]
                try:
                    process = subprocess.run(cmd, capture_output=True, text=True, check=False)
                    
                    # Print detailed output for debugging
                    print("\n--- PDFLATEX OUTPUT - START ---")
                    print(f"Command: {' '.join(cmd)}")
                    print(f"Return code: {process.returncode}")
                    
                    # Look for critical errors in the output
                    print("\n--- RELEVANT ERROR MESSAGES ---")
                    for line in process.stdout.splitlines():
                        if "Error:" in line or "Fatal error" in line or "Emergency stop" in line:
                            print(line)
                    
                    # Always save log file for debugging
                    log_file = temp_dir_path / "resume.log"
                    if log_file.exists():
                        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                            log_content = f.read()
                            print("\n--- LAST 50 LINES OF LATEX LOG ---")
                            log_lines = log_content.splitlines()
                            print('\n'.join(log_lines[-50:]))
                    
                    print("--- PDFLATEX OUTPUT - END ---\n")
                    
                    if process.returncode == 0:
                        compilation_successful_this_iteration = True
                        break # Successful compilation
                    else:
                        logger.warning(f"LaTeX compilation failed for height {current_height:.1f} inches. Return code: {process.returncode}")
                except subprocess.TimeoutExpired:
                    logger.error(f"LaTeX compilation timed out for height {current_height:.1f} inches.")
                except Exception as e:
                    logger.error(f"An unexpected error occurred during LaTeX compilation: {e}")
            
            os.chdir(original_cwd) # Change back to original dir

            if compilation_successful_this_iteration:
                pdf_file_in_temp = temp_dir_path / pdf_file_name
                if pdf_file_in_temp.exists():
                    num_pages = get_pdf_page_count(str(pdf_file_in_temp))
                    logger.info(f"Generated PDF has {num_pages} page(s) for height {current_height:.1f} inches.")
                    if num_pages == 1:
                        logger.info(f"Single-page PDF successfully generated with height: {current_height:.1f} inches.")
                        if output_path:
                            try:
                                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(pdf_file_in_temp, output_path)
                                final_pdf_path_str = output_path
                                logger.info(f"PDF saved to: {output_path}")
                            except Exception as e:
                                logger.error(f"Error copying PDF to output path: {e}")
                        else: # If no output_path, use the temp path (mainly for testing)
                            final_pdf_path_str = str(pdf_file_in_temp)
                        success = True
                        break # Exit height loop as we found a working height
                    elif num_pages > 1:
                        logger.info(f"Multi-page PDF ({num_pages} pages) generated with height {current_height:.1f} inches.")
                        # If we've reached the maximum allowed height, accept the multi-page PDF
                        if current_height >= MAX_HEIGHT_INCHES - 1e-6:  # float tolerance
                            logger.info("Reached maximum allowed page height. Accepting multi-page output.")
                            if output_path:
                                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(pdf_file_in_temp, output_path)
                                final_pdf_path_str = output_path
                                logger.info(f"PDF saved to: {output_path}")
                            else:
                                final_pdf_path_str = str(pdf_file_in_temp)
                            success = True
                            break  # Exit height loop - we accept multi-page
                        else:
                            logger.info("Trying next larger page height to see if content can fit on a single page...")
                    else: # num_pages is 0 or None
                        logger.warning(f"PDF page count was {num_pages} for height {current_height:.1f} inches. Treating as failure for this height.") 
                else:
                    logger.warning(f"PDF file {pdf_file_name} not found in {temp_dir_path} after supposed successful compilation at height {current_height:.1f} inches.")
            else:
                logger.warning(f"LaTeX compilation failed for height {current_height:.1f} inches. Not checking page count.")

        if not success:
            logger.error("PDF generation failed to produce a single-page document after trying all specified heights.")
            # If an output_path was specified, try to save the .tex file from the last attempt for debugging
            if output_path and tex_file_path.exists():
                 try:
                    base_name = Path(output_path).stem
                    tex_output_dir = Path(output_path).parent
                    debug_tex_path = tex_output_dir / f"{base_name}_FAILED_ALL_HEIGHTS.tex"
                    shutil.copy(tex_file_path, debug_tex_path)
                    logger.info(f"Saved last attempted .tex for debugging: {debug_tex_path}")
                 except Exception as e:
                    logger.warning(f"Could not save last attempted .tex file for debugging: {e}")
    
    return final_pdf_path_str, success

def get_pdf_page_count(pdf_path):
    """
    Get the number of pages in a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        int: Number of pages in the PDF file, defaulting to 2 if not determinable
    """
    logger.info(f"Checking page count for: {pdf_path}")
    
    # Method 1: Try using pdfinfo command (faster, less dependencies)
    try:
        result = subprocess.run(
            ["pdfinfo", str(pdf_path)],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        if result.returncode != 0:
            logger.warning(f"Error running pdfinfo: {result.stderr}")
        else:
            # Parse the output to get page count
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    try:
                        page_count = int(line.split(":", 1)[1].strip())
                        logger.info(f"PDF has {page_count} page(s)")
                        return page_count
                    except (IndexError, ValueError) as e:
                        logger.warning(f"Error parsing page count: {e}")
    except FileNotFoundError:
        logger.warning("pdfinfo command not found, trying alternative method...")
    except Exception as e:
        logger.warning(f"Unexpected error running pdfinfo: {e}")
    
    # Method 2: Use a simpler string search in the log file
    log_file = str(pdf_path).replace('.pdf', '.log')
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
                # Simple check for the single-page output indicator
                if "(1 page" in log_content:
                    logger.info("Found '(1 page' in log file. Assuming 1 page.")
                    return 1
                else:
                    # If "(1 page" isn't found, assume > 1 page
                    logger.info("Did not find '(1 page' pattern in log file. Assuming > 1 page.")
                    return 2
        except Exception as e:
            logger.warning(f"Error reading log file for simple check: {e}")

    # Method 3: Fallback - based on file size
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        logger.info(f"PDF file exists with size: {os.path.getsize(pdf_path)} bytes")
        # If file is larger than typical 1-page resume, assume it's multi-page
        if os.path.getsize(pdf_path) > 150000:  # Arbitrary threshold
            logger.info("PDF file is larger than expected for a single page, assuming 2 pages")
            return 2
        else:
            logger.info("Assuming 1 page for auto-sizing purposes")
            return 1
    
    # Couldn't determine page count
    logger.warning("Could not determine page count. Install pdfinfo (poppler-utils) for better results.")
    # Default to 2 pages if we can't determine to force height increases
    logger.warning("Defaulting to 2 pages to trigger page height increase")
    return 2

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