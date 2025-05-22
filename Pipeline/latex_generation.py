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
DEFAULT_MIN_HEIGHT_INCHES = 11.0  # Default minimum page height (inches)
MAX_HEIGHT_INCHES = 15.0  # Maximum page height (inches) before falling back to multi-page output
MAX_ITERATIONS_PER_HEIGHT = 2 # Max recompilations for a given height if bibtex is needed.
HEIGHT_INCREMENT_INCHES = 0.5  # Increment for trying different page heights

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

    heights_to_try = list(frange(DEFAULT_MIN_HEIGHT_INCHES, MAX_HEIGHT_INCHES + HEIGHT_INCREMENT_INCHES, HEIGHT_INCREMENT_INCHES))
    
    # Create a temporary directory for LaTeX processing
    with tempfile.TemporaryDirectory() as temp_dir_name:
        temp_dir_path = Path(temp_dir_name)
        tex_file_name = "resume.tex"
        pdf_file_name = "resume.pdf"
        tex_file_path = temp_dir_path / tex_file_name
        
        font_size_reduced_attempted = False # Flag to track if we've tried reducing font size

        for attempt_count in range(2): # Max 2 attempts: 1 normal, 1 with reduced font size
            if attempt_count == 1 and not success: # If first attempt failed (not single page)
                logger.info("First attempt failed to produce a single page. Attempting with reduced font size (10.5pt).")
                font_size_reduced_attempted = True
            elif attempt_count == 1 and success: # First attempt succeeded
                break # No need for a second attempt

            current_best_pdf_path_this_attempt = None
            current_best_page_count_this_attempt = float('inf')

            for current_height in heights_to_try:
                logger.info(f"Attempting PDF generation with height: {current_height:.1f} inches. Reduced font: {font_size_reduced_attempted}")
                
                latex_content = generate_latex_content(
                    resume_data, 
                    target_paper_height_value_str=f"{current_height:.2f}",
                    reduce_font_size=font_size_reduced_attempted
                )
                with open(tex_file_path, 'w', encoding='utf-8') as f:
                    f.write(latex_content)
                
                # Save .tex for inspection if output_path is provided
                if output_path:
                    try:
                        base_name = Path(output_path).stem
                        tex_output_dir = Path(output_path).parent
                        font_suffix = "_10.5pt" if font_size_reduced_attempted else "_11pt"
                        inspection_tex_path = tex_output_dir / f"{base_name}_{current_height:.1f}in{font_suffix}.tex"
                        # shutil.copy(tex_file_path, inspection_tex_path) # Keep this commented for now
                        # logger.info(f"Saved .tex for inspection: {inspection_tex_path}")
                    except Exception as e:
                        logger.warning(f"Could not save inspection .tex file: {e}")

                os.chdir(temp_dir_path) # Change to temp dir for latexmk
                
                compilation_successful_this_iteration = False
                for _ in range(MAX_ITERATIONS_PER_HEIGHT): 
                    cmd = [
                        "pdflatex",
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
                            break 
                        else:
                            logger.warning(f"LaTeX compilation failed for height {current_height:.1f} inches (Reduced font: {font_size_reduced_attempted}). RC: {process.returncode}")
                            # Save log on failure
                            log_file_path = temp_dir_path / "resume.log"
                            if output_path and log_file_path.exists():
                                try:
                                    base_name = Path(output_path).stem
                                    log_output_dir = Path(output_path).parent
                                    font_suffix = "_10.5pt" if font_size_reduced_attempted else "_11pt"
                                    failed_log_path = log_output_dir / f"{base_name}_{current_height:.1f}in{font_suffix}_FAILED.log"
                                    shutil.copy(log_file_path, failed_log_path)
                                    logger.info(f"Saved FAILED log: {failed_log_path}")
                                except Exception as e_log:
                                    logger.warning(f"Could not save FAILED log: {e_log}")
                    except Exception as e:
                        logger.error(f"Unexpected error during LaTeX compilation (Height: {current_height:.1f}, Reduced: {font_size_reduced_attempted}): {e}")
                
                os.chdir(original_cwd) 

                if compilation_successful_this_iteration:
                    pdf_file_in_temp = temp_dir_path / pdf_file_name
                    if pdf_file_in_temp.exists():
                        num_pages = get_pdf_page_count(str(pdf_file_in_temp))
                        logger.info(f"Generated PDF has {num_pages} page(s) for height {current_height:.1f} inches (Reduced font: {font_size_reduced_attempted}).")
                        
                        # Track the best PDF (fewest pages) for this attempt (normal or reduced font)
                        if num_pages < current_best_page_count_this_attempt:
                            current_best_page_count_this_attempt = num_pages
                            # Save this PDF to a temporary location within the loop if it's the best so far for this font size attempt
                            # This is important because we might overwrite it in the next height iteration
                            temp_best_pdf_for_font_attempt = temp_dir_path / f"best_so_far_font_attempt_{attempt_count}.pdf"
                            shutil.copy(pdf_file_in_temp, temp_best_pdf_for_font_attempt)
                            current_best_pdf_path_this_attempt = str(temp_best_pdf_for_font_attempt)


                        if num_pages == 1:
                            logger.info(f"Single-page PDF successfully generated with height: {current_height:.1f} inches (Reduced font: {font_size_reduced_attempted}).")
                            if output_path:
                                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                                shutil.copy(pdf_file_in_temp, output_path)
                                final_pdf_path_str = output_path
                                logger.info(f"PDF saved to: {output_path}")
                            else:
                                final_pdf_path_str = str(pdf_file_in_temp) # Should be copied to a persistent temp if needed outside
                            success = True
                            break # Exit height loop for this font size attempt
                        elif num_pages > 1 and current_height >= MAX_HEIGHT_INCHES - 1e-6: 
                            logger.info(f"Reached max height ({current_height:.1f}in) with {num_pages} pages (Reduced font: {font_size_reduced_attempted}). This is a candidate for final output if single page not achieved.")
                            # Don't break yet, let the outer loop decide if this is the final one
                    else:
                        logger.warning(f"PDF file not found after supposed success (Height: {current_height:.1f}, Reduced: {font_size_reduced_attempted}).")
                else:
                    logger.warning(f"Compilation failed (Height: {current_height:.1f}, Reduced: {font_size_reduced_attempted}).")
            
            # After trying all heights for the current font size attempt:
            if success: # Single page was found
                break # Exit the main attempt_count loop

            # If no single-page PDF was found in this attempt (either normal or reduced font size)
            # And if we have a multi-page PDF from this attempt (e.g., from MAX_HEIGHT)
            # this becomes the current candidate for the final output if the other attempt also fails or if this is the reduced font attempt.
            if not success and current_best_pdf_path_this_attempt and current_best_page_count_this_attempt > 1:
                 logger.info(f"Font attempt {attempt_count+1} (Reduced: {font_size_reduced_attempted}) did not yield a single page. Best was {current_best_page_count_this_attempt} pages.")
                 # If this is the reduced font attempt OR if it's the first attempt and no better solution is found
                 # then this multi-page PDF is our fallback.
                 if font_size_reduced_attempted or (attempt_count == 0 and not final_pdf_path_str): # Prioritize reduced font if both are multi-page
                    if output_path and current_best_pdf_path_this_attempt:
                        logger.info(f"Setting multi-page PDF from this attempt ({current_best_pdf_path_this_attempt}) as fallback.")
                        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy(current_best_pdf_path_this_attempt, output_path)
                        final_pdf_path_str = output_path
                        # success remains False if it's multi-page, but we have a path
                        success = False # Explicitly false for multi-page, even if it's "accepted"
                        logger.info(f"Multi-page PDF ({current_best_page_count_this_attempt} pages) saved to: {output_path}")
                    elif not output_path and current_best_pdf_path_this_attempt:
                        # If no output_path, the caller needs to handle this temp file
                        final_pdf_path_str = current_best_pdf_path_this_attempt
                        success = False
                        logger.info(f"Multi-page PDF ({current_best_page_count_this_attempt} pages) available at temp path: {final_pdf_path_str}")


        if not success and not final_pdf_path_str: # If loop finishes and no PDF was ever successfully made and saved
            logger.error("PDF generation failed to produce any document after trying all specified heights and font sizes.")
            # Save last attempted .tex for debugging if output_path is specified
            if output_path and tex_file_path.exists():
                 try:
                    base_name = Path(output_path).stem
                    tex_output_dir = Path(output_path).parent
                    font_suffix = "_10.5pt" if font_size_reduced_attempted else "_11pt" # Suffix from last attempt
                    debug_tex_path = tex_output_dir / f"{base_name}_FAILED_ALL_ATTEMPTS{font_suffix}.tex"
                    shutil.copy(tex_file_path, debug_tex_path)
                    logger.info(f"Saved last attempted .tex for debugging: {debug_tex_path}")
                 except Exception as e:
                    logger.warning(f"Could not save last attempted .tex file for debugging: {e}")
        elif not success and final_pdf_path_str:
             logger.info(f"PDF generation resulted in a multi-page document saved at: {final_pdf_path_str}")
             # success is already False, path is set. This is an "accepted multi-page" scenario.


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

def generate_resume_pdf(
    json_data: dict, 
    output_pdf_path: str,
    min_height_inches: float = DEFAULT_MIN_HEIGHT_INCHES,
    max_height_inches: float = MAX_HEIGHT_INCHES,
    target_paper_height_value_str: Optional[str] = None
) -> Tuple[str, bool]:
    """
    End-to-end function to generate a PDF resume from resume data.
    
    This is the main entry point that should be called from other parts of the application.
    
    Args:
        json_data: The parsed resume data as a dictionary
        output_pdf_path: Optional path to save the PDF
        min_height_inches: Minimum height in inches to start trying
        max_height_inches: Maximum height in inches to stop trying
        target_paper_height_value_str: Optional target paper height value string
        
    Returns:
        Tuple of (pdf_path, success)
    """
    logger.info("Starting end-to-end resume PDF generation")
    
    try:
        return generate_pdf_from_latex(json_data, output_pdf_path)
    except Exception as e:
        logger.error(f"Error in end-to-end PDF generation: {e}")
        return "", False

# --- Example Usage (for direct testing of this module) ---
if __name__ == "__main__":
    # Create a dummy JSON data for testing
    sample_json_data = {
        "Personal Information": {"name": "John Doe", "email": "john.doe@example.com"},
        "Experience": [
            {
                "company": "Tech Corp",
                "title": "Software Engineer",
                "dates": "2020-Present",
                "responsibilities/achievements": ["Developed new features."] * 30 # Make it long
            }
        ] * 3 # More sections to force multi-page
    }

    # Test with default adaptive sizing
    output_pdf_default = "test_resume_default_adaptive.pdf"
    print(f"\n--- Testing adaptive PDF generation (default settings) --> {output_pdf_default} ---")
    # Call the main wrapper function generate_resume_pdf, not generate_pdf_from_latex directly for testing adaptive
    final_pdf_path, success = generate_resume_pdf(sample_json_data, output_pdf_default) 
    if success:
        print(f"Adaptive PDF generation successful: {final_pdf_path}")
    else:
        print(f"Adaptive PDF generation failed. Check logs and .tex files in output_resumes/")

    # Test with a fixed height (simulating if single page was desired at specific height)
    # To do this, we directly call generate_latex_content then pdflatex
    fixed_height_tex = "test_resume_fixed_H12.tex"
    fixed_height_pdf = "test_resume_fixed_H12.pdf"
    print(f"\n--- Testing fixed height PDF generation (12 inches) --> {fixed_height_pdf} ---")
    latex_fixed = generate_latex_content(sample_json_data, target_paper_height_value_str="12.00")
    with open(fixed_height_tex, "w", encoding="utf-8") as f:
        f.write(latex_fixed)
    # Compile it (simplified, no error checking like in main function)
    import subprocess
    subprocess.run(["pdflatex", "-interaction=nonstopmode", fixed_height_tex], check=False)
    print(f"Fixed height TeX saved to {fixed_height_tex}, PDF attempted: {fixed_height_pdf}")
    
    # Test fallback to multi-page (by setting max_height very low)
    output_pdf_fallback = "test_resume_forced_fallback.pdf"
    print(f"\n--- Testing forced fallback to multi-page PDF --> {output_pdf_fallback} ---")
    # Call the main wrapper function generate_resume_pdf for testing fallback
    final_pdf_path_fallback, success_fallback = generate_resume_pdf( 
        sample_json_data, 
        output_pdf_fallback,
        min_height_inches=10.0, # Start low
        max_height_inches=10.5  # Max low to force fallback
    )
    if success_fallback:
        print(f"Forced fallback PDF generation successful: {final_pdf_path_fallback}")
    else:
        print(f"Forced fallback PDF generation failed.")