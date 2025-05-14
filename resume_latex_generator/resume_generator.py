import argparse
import os
import sys
import importlib
import glob
import re
import subprocess
import json
import tempfile
import shutil # For moving the file
from typing import Dict, Any, Optional, List

# Default directory names
DATA_DIR = "data"
TEMPLATES_DIR = "templates"
OUTPUT_DIR = "output"

# Default page sizing parameters
DEFAULT_INITIAL_PAGE_HEIGHT_INCHES = 11.0
MAX_AUTO_SIZE_ATTEMPTS = 5
PAGE_HEIGHT_INCREMENT_INCHES = 1.0

# Import template loading functions
from .templates import get_available_templates, load_template
from .templates.classic_template import generate_latex_content

def load_json_data(file_path: str) -> Optional[Dict[str, Any]]:
    """Loads JSON data from the specified file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: JSON file not found at {file_path}", file=sys.stderr)
        return None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from {file_path}", file=sys.stderr)
        return None

def get_output_filenames(base_name: str, output_dir: str) -> tuple[str, str, str, int]:
    """Determines unique output filenames for .tex, .pdf, and .json."""
    i = 1
    while True:
        tex_filename = os.path.join(output_dir, f"{base_name}{i}.tex")
        pdf_filename = os.path.join(output_dir, f"{base_name}{i}.pdf")
        json_filename = os.path.join(output_dir, f"{base_name}{i}.json")
        if not os.path.exists(tex_filename) and not os.path.exists(pdf_filename):
            return tex_filename, pdf_filename, json_filename, i
        i += 1

def compile_latex(tex_filepath: str) -> bool:
    """
    Compiles a .tex file into a PDF using pdflatex.
    
    Args:
        tex_filepath: The path to the .tex file to compile.
        
    Returns:
        True if compilation was successful, False otherwise.
    """
    # Output directory for the PDF (same as the tex file directory)
    output_dir = os.path.dirname(tex_filepath)
    
    # Extract the file name (without path and extension)
    filename = os.path.splitext(os.path.basename(tex_filepath))[0]
    
    # Build the pdflatex command with appropriate options
    cmd = [
        "pdflatex",
        "-interaction=nonstopmode",  # Don't stop for errors
        f"-output-directory={output_dir}",
        tex_filepath
    ]
    
    print(f"Compiling LaTeX file: {tex_filepath}")
    sys.stdout.flush() # Force flush
    
    detailed_error = None
    
    try:
        # Run pdflatex twice to handle references, TOC, etc. (may not be needed for resumes)
        for attempt in range(2):
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            # Check if compilation was successful
            if result.returncode != 0:
                error_output = result.stderr or result.stdout
                print(f"Error during LaTeX compilation (attempt {attempt+1}):")
                sys.stdout.flush() # Force flush
                print(error_output)
                sys.stdout.flush() # Force flush
                
                # Save the detailed error for later failure reporting
                detailed_error = f"LaTeX Error (attempt {attempt+1}): {error_output[:500]}..."
                
                # Try once more with the second attempt
                if attempt == 0:
                    print("Retrying compilation...")
                    sys.stdout.flush() # Force flush
                    continue
                
                print("LaTeX compilation failed. Please check the .tex file and LaTeX installation.")
                sys.stdout.flush() # Force flush
                
                # Show path to .log file for debugging
                log_file = os.path.join(output_dir, f"{filename}.log")
                if os.path.exists(log_file):
                    print(f"LaTeX log file available at: {log_file}")
                    sys.stdout.flush() # Force flush
                    
                    # Try to extract key error info from the log
                    try:
                        with open(log_file, 'r', errors='ignore') as f:
                            log_content = f.read()
                            # Look for common error markers in LaTeX logs
                            error_markers = ["! LaTeX Error:", "! Undefined control sequence", "! Missing", "! Too many"]
                            for marker in error_markers:
                                if marker in log_content:
                                    idx = log_content.find(marker)
                                    error_context = log_content[idx:idx+500].replace('\n', ' ')
                                    detailed_error = f"From log file: {error_context}..."
                                    break
                    except Exception as e:
                        print(f"Error reading log file: {e}")
                        sys.stdout.flush()
                
                # Raise a more detailed exception instead of just returning False
                raise Exception(detailed_error or "LaTeX compilation failed. No detailed error available.")
            
            # Success on this attempt - if it's the first, continue to the second run
            if attempt == 0:
                print("First pass successful, running second pass...")
                sys.stdout.flush() # Force flush
        
        # If we reached here, both compilations were successful
        pdf_path = os.path.join(output_dir, f"{filename}.pdf")
        if os.path.exists(pdf_path):
            print(f"PDF successfully created: {pdf_path}")
            sys.stdout.flush() # Force flush
            return True
        else:
            error_msg = f"Expected PDF file not found at {pdf_path} despite successful compilation."
            print(error_msg)
            sys.stdout.flush() # Force flush
            raise Exception(error_msg)
    
    except FileNotFoundError:
        error_msg = "ERROR: LaTeX compiler (pdflatex) not found in PATH. Is it installed?"
        print(error_msg)
        sys.stdout.flush() # Force flush
        raise Exception(error_msg)
    
    except Exception as e:
        # If it's our own exception with details, re-raise it
        if isinstance(e, Exception) and detailed_error:
            raise
        
        # Otherwise wrap in a new exception
        error_msg = f"Unexpected error during LaTeX compilation: {e}"
        print(error_msg)
        sys.stdout.flush() # Force flush
        raise Exception(error_msg)

def get_pdf_page_count(pdf_path):
    """
    Get the number of pages in a PDF file.
    
    Args:
        pdf_path (str): Path to the PDF file
        
    Returns:
        int or None: Number of pages in the PDF file, or None if not determinable
    """
    print(f"Checking page count for: {pdf_path}")
    
    # Method 1: Try using pdfinfo command (faster, less dependencies)
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path],
            capture_output=True,
            text=True,
            check=False  # Don't raise exception on non-zero exit
        )
        
        if result.returncode != 0:
            print(f"Error running pdfinfo: {result.stderr}")
        else:
            # Parse the output to get page count
            for line in result.stdout.splitlines():
                if line.startswith("Pages:"):
                    try:
                        page_count = int(line.split(":", 1)[1].strip())
                        print(f"PDF has {page_count} page(s)")
                        return page_count
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing page count: {e}")
    except FileNotFoundError:
        print("pdfinfo command not found, trying alternative method...")
    except Exception as e:
        print(f"Unexpected error running pdfinfo: {e}")
    
    # Method 2: Use grep to search for "Page" in the LaTeX log file
    log_file = pdf_path.replace('.pdf', '.log')
    if os.path.exists(log_file):
        try:
            with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                log_content = f.read()
                # Look for patterns like "Output written on filename.pdf (2 pages"
                match = re.search(r'Output written on .+?\.pdf \((\d+) pages', log_content)
                if match:
                    page_count = int(match.group(1))
                    print(f"Found page count in log file: {page_count} page(s)")
                    return page_count
                
                # Alternative pattern search
                if "Overfull \hbox" in log_content and "Float too large" in log_content:
                    print("Warning: Log file indicates content overflow issues")
                
        except Exception as e:
            print(f"Error reading log file: {e}")
    
    # Method 3: Fallback - just check if the file exists and parse filename for clues
    if os.path.exists(pdf_path) and os.path.getsize(pdf_path) > 0:
        print(f"PDF file exists with size: {os.path.getsize(pdf_path)} bytes")
        # If file is larger than typical 1-page resume, assume it's multi-page
        # This is a very crude heuristic and should be improved
        if os.path.getsize(pdf_path) > 150000:  # Arbitrary threshold
            print("PDF file is larger than expected for a single page, assuming 2 pages")
            return 2
        else:
            print("Assuming 1 page for auto-sizing purposes")
            return 1
    
    # Couldn't determine page count
    print("Could not determine page count. Install pdfinfo (poppler-utils) for better results.")
    print("On most systems, you can install it through:")
    print("  - macOS: 'brew install poppler'")
    print("  - Linux: 'apt-get install poppler-utils' (Ubuntu/Debian)")
    # Default to 2 pages if we can't determine to force height increases
    print("Defaulting to 2 pages to trigger page height increase")
    return 2

def main():
    # Ensure required directories exist
    for dirname in [DATA_DIR, TEMPLATES_DIR, OUTPUT_DIR]:
        os.makedirs(dirname, exist_ok=True)

    parser = argparse.ArgumentParser(description="Generates professional-looking resumes in PDF format from JSON data.")

    parser.add_argument(
        "--json",
        type=str,
        help="Path to the input JSON file."
    )
    parser.add_argument(
        "--template",
        type=str,
        help="Name of the template to use. Use --list-templates to see available options."
    )
    parser.add_argument(
        "--output",
        type=str,
        default="resume",
        help="Base name for output files (e.g., \"my_resume\")."
    )
    parser.add_argument(
        "--list-templates",
        action="store_true",
        help="List discovered template names and exit."
    )
    parser.add_argument(
        "--list-data-files",
        action="store_true",
        help="List JSON files in the data/ directory and exit."
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Trigger interactive prompts if --json or --template are missing."
    )
    parser.add_argument(
        "--no-save-json",
        action="store_true",
        help="Prevent saving a copy of the input JSON to the output directory."
    )
    parser.add_argument(
        "--page-height",
        type=float,
        help="Specify an initial page height in inches. Auto-sizing might start from this or be disabled if --no-auto-size is also used."
    )
    parser.add_argument(
        "--no-auto-size",
        action="store_true",
        help="Disable the automatic page height adjustment feature."
    )

    args = parser.parse_args()

    if args.list_templates:
        # Placeholder for listing templates
        print("Listing templates...")
        available_templates = get_available_templates()
        if available_templates:
            print("Available templates:")
            for t_name in available_templates:
                print(f"  - {t_name}")
        else:
            print(f"No templates found in '{TEMPLATES_DIR}/'. Ensure template files end with '{TEMPLATE_FILE_SUFFIX}'.")
        sys.exit(0)

    if args.list_data_files:
        print(f"Listing JSON files in '{DATA_DIR}/':")
        json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
        if json_files:
            for f_path in json_files:
                print(f"  - {os.path.basename(f_path)}")
        else:
            print(f"No JSON files found in '{DATA_DIR}/'.")
        sys.exit(0)

    # --- Interactive Mode ---
    input_json_path = args.json
    selected_template_name = args.template

    if args.interactive and (not input_json_path or not selected_template_name):
        if not input_json_path:
            json_files = glob.glob(os.path.join(DATA_DIR, "*.json"))
            if not json_files:
                print(f"No JSON files found in '{DATA_DIR}/'. Please create a data file or specify one with --json.", file=sys.stderr)
                sys.exit(1)
            print("Available data files:")
            for i, f_path in enumerate(json_files):
                print(f"  {i+1}. {os.path.basename(f_path)}")
            while True:
                try:
                    choice = int(input(f"Select a data file (1-{len(json_files)}): ")) - 1
                    if 0 <= choice < len(json_files):
                        input_json_path = json_files[choice]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
        
        if not selected_template_name:
            available_templates = get_available_templates()
            if not available_templates:
                print(f"No templates found in '{TEMPLATES_DIR}/'.", file=sys.stderr)
                sys.exit(1)
            print("Available templates:")
            for i, t_name in enumerate(available_templates):
                print(f"  {i+1}. {t_name}")
            while True:
                try:
                    choice = int(input(f"Select a template (1-{len(available_templates)}): ")) - 1
                    if 0 <= choice < len(available_templates):
                        selected_template_name = available_templates[choice]
                        break
                    else:
                        print("Invalid choice.")
                except ValueError:
                    print("Invalid input. Please enter a number.")

    # Validate required arguments after interactive mode
    if not input_json_path:
        parser.error("the following arguments are required: --json (or use --interactive)")
    if not selected_template_name:
        parser.error("the following arguments are required: --template (or use --interactive)")

    # --- Load JSON Data ---
    print(f"Loading JSON data from: {input_json_path}")
    resume_data = load_json_data(input_json_path)
    if resume_data is None:
        sys.exit(1)

    # --- Load Template ---
    print(f"Loading template: '{selected_template_name}'")
    try:
        template_module = load_template(selected_template_name)
    except ImportError as e:
        print(f"Error loading template: {e}", file=sys.stderr)
        # Suggest valid templates if the one chosen is bad
        available_templates = get_available_templates()
        if available_templates:
            print("Available templates are:", ", ".join(available_templates))
        else:
            print(f"No templates found in '{TEMPLATES_DIR}/'.")
        sys.exit(1)

    # --- Determine Output Filenames ---
    base_output_name = args.output
    tex_filepath, pdf_filepath, json_copy_filepath, file_num = get_output_filenames(base_output_name, OUTPUT_DIR)
    print(f"Output .tex will be: {tex_filepath}")
    print(f"Output .pdf will be: {pdf_filepath}")


    # --- Page Sizing Loop / LaTeX Generation / Compilation ---
    initial_page_height = args.page_height if args.page_height is not None else DEFAULT_INITIAL_PAGE_HEIGHT_INCHES
    
    if hasattr(template_module, 'generate_latex_content'):
        print(f"Generating LaTeX content with initial page height: {initial_page_height} inches (auto-sizing: {'disabled' if args.no_auto_size else 'enabled'})")
        
        # Handle the case when auto-sizing is disabled
        if args.no_auto_size:
            page_height_to_use = args.page_height # Can be None, template handles default
            latex_content = template_module.generate_latex_content(resume_data, page_height=page_height_to_use)
            
            # Save .tex file
            with open(tex_filepath, 'w', encoding='utf-8') as f:
                f.write(latex_content)
            print(f"LaTeX content saved to {tex_filepath}")
            
            # Compile .tex file
            if compile_latex(tex_filepath):
                print(f"Resume PDF generated successfully: {pdf_filepath}")
            else:
                print("Failed to compile the LaTeX content.")
        else:
            # Auto-sizing loop implementation
            print("Starting auto-sizing process to fit content on one page...")
            current_page_height = initial_page_height
            attempts_remaining = MAX_AUTO_SIZE_ATTEMPTS
            success = False
            
            while attempts_remaining > 0:
                print(f"Attempt {MAX_AUTO_SIZE_ATTEMPTS - attempts_remaining + 1}/{MAX_AUTO_SIZE_ATTEMPTS}: Using page height of {current_page_height:.2f} inches")
                
                # Generate LaTeX with current height
                latex_content = template_module.generate_latex_content(resume_data, page_height=current_page_height)
                
                # Save .tex file
                with open(tex_filepath, 'w', encoding='utf-8') as f:
                    f.write(latex_content)
                print(f"LaTeX content saved to {tex_filepath}")
                
                # Compile .tex file
                if not compile_latex(tex_filepath):
                    print("LaTeX compilation failed. Aborting auto-sizing.")
                    break
                
                # Check page count
                page_count = get_pdf_page_count(pdf_filepath)
                if page_count is None or page_count > 1:
                    if page_count is None:
                        # If we can't determine page count, assume it needs more space
                        print("Could not determine page count. Assuming multiple pages and increasing height.")
                        page_count = 2  # Default to assume it needs more space
                    
                    # Need to increase page height and try again
                    if attempts_remaining > 1:  # Still have more attempts
                        print(f"Content currently spans {page_count} pages. Increasing page height...")
                        current_page_height += PAGE_HEIGHT_INCREMENT_INCHES
                        print(f"New page height: {current_page_height:.2f} inches")
                        attempts_remaining -= 1
                    else:
                        print(f"Maximum attempts reached. Content still spans {page_count} pages.")
                        break
                else:
                    print("Success! Content fits on a single page.")
                    success = True
                    break
            
            if success:
                print(f"Auto-sizing successful. Final page height: {current_page_height:.2f} inches.")
            else:
                print("Auto-sizing completed without achieving one-page layout.")
                print("You may need to:")
                print("  1. Edit the input data to reduce content")
                print("  2. Try with a larger initial page height")
                print("  3. Try with a larger height increment")
                print("  4. Disable auto-sizing (--no-auto-size) and manually adjust the content")
    else:
        print(f"Error: Template module '{selected_template_name}' does not have 'generate_latex_content' function.", file=sys.stderr)
        sys.exit(1)
        
    # --- Optionally Save JSON Copy ---
    if not args.no_save_json:
        try:
            with open(json_copy_filepath, 'w') as f:
                json.dump(resume_data, f, indent=2)
            print(f"Copied input JSON to {json_copy_filepath}")
        except Exception as e:
            print(f"Error saving JSON copy: {e}", file=sys.stderr)


    print(f"Resume generation process initiated for {input_json_path} using {selected_template_name}.")
    # print(f"Arguments: {args}") # Already printed at the start

if __name__ == "__main__":
    main()

# Function to be called from working_app.py
def create_pdf_generator():
    """
    Creates and returns a PDF generator object that can be used by the Flask application.
    This serves as an adapter between the Flask app and the PDF generation logic.
    
    Returns:
        A PDF generator object with methods for generating PDFs.
    """
    class PDFGenerator:
        def __init__(self):
            # Ensure required directories exist
            for dirname in [DATA_DIR, TEMPLATES_DIR, OUTPUT_DIR]:
                os.makedirs(dirname, exist_ok=True)
            
            # Default template
            self.template_name = "classic"
        
        def check_environment(self):
            """
            Check if the required tools are available in the environment.
            
            Returns:
                str: Status message about the environment.
            """
            # Check for LaTeX
            try:
                result = subprocess.run(
                    ["pdflatex", "--version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                if result.returncode == 0:
                    return "LaTeX environment is properly configured."
                else:
                    return f"LaTeX is not properly configured. Error: {result.stderr}"
            except FileNotFoundError:
                return "LaTeX (pdflatex) is not installed or not in PATH."
            except Exception as e:
                return f"Error checking LaTeX environment: {str(e)}"
        
        def generate_pdf(self, resume_data, output_path, template_name=None):
            """
            Generate a PDF from resume data.
            
            Args:
                resume_data (dict): Resume data in dictionary format.
                output_path (str): Path where the PDF should be saved.
                template_name (str, optional): Name of the template to use. Defaults to 'classic'.
                
            Returns:
                bool: True if PDF generation was successful, False otherwise.
            """
            try:
                # Use specified template or default
                template_name = template_name or self.template_name
                
                # Get the template module
                try:
                    template_module = load_template(template_name)
                except ImportError as e:
                    raise Exception(f"Template error: {str(e)}")
                
                # Set up paths
                output_dir = os.path.dirname(output_path)
                os.makedirs(output_dir, exist_ok=True)
                
                # Base filename without extension
                base_name = os.path.splitext(os.path.basename(output_path))[0]
                
                # Define tex filepath
                tex_filepath = os.path.join(output_dir, f"{base_name}.tex")
                
                # Generate LaTeX content
                try:
                    page_height = DEFAULT_INITIAL_PAGE_HEIGHT_INCHES
                    latex_content = template_module.generate_latex_content(resume_data, page_height)
                except Exception as e:
                    raise Exception(f"LaTeX content generation error: {str(e)}")
                
                # Write LaTeX content to file
                try:
                    with open(tex_filepath, 'w') as f:
                        f.write(latex_content)
                except Exception as e:
                    raise Exception(f"Error writing LaTeX file to {tex_filepath}: {str(e)}")
                
                # Compile LaTeX to PDF
                compile_result = compile_latex(tex_filepath)
                if not compile_result:
                    raise Exception(f"LaTeX compilation failed for {tex_filepath}. Check if pdflatex is installed and accessible.")
                
                # If successful, the PDF should be at output_path
                if not os.path.exists(output_path):
                    raise Exception(f"PDF file was not created at expected path: {output_path}")
                
                return True
            
            except Exception as e:
                print(f"Error generating PDF: {e}")
                sys.stdout.flush()
                # Re-raise the exception for the caller to handle
                raise
    
    return PDFGenerator()

class LatexPdfGenerator:
    def __init__(self, template_name='classic', no_auto_size=False):
        self.template_name = template_name
        self.no_auto_size = no_auto_size # This will be True based on working_app.py changes
        # Dynamically load the template generation function from classic_template.py
        # This aligns with the design of generate_latex_content being the core logic.
        from .templates.classic_template import generate_latex_content as classic_generate_func
        self.template_generate_func = classic_generate_func
        # We also need fix_latex_special_chars if we were to apply it here, 
        # but it's assumed to be handled within template_generate_func.
        # from .templates.classic_template import fix_latex_special_chars 

    def check_environment(self):
        try:
            subprocess.run(["pdflatex", "-version"], capture_output=True, check=True, text=True)
            return {"status": "OK", "message": "pdflatex found."}
        except FileNotFoundError:
            return {"status": "Error", "message": "pdflatex not found. Please ensure LaTeX is installed."}
        except subprocess.CalledProcessError as e:
            return {"status": "Error", "message": f"pdflatex found but error on version check: {e.stdout} {e.stderr}"}
        except Exception as e_gen:
            return {"status": "Error", "message": f"An unexpected error occurred during pdflatex check: {str(e_gen)}"}

    def _compile_latex(self, tex_filepath: str, output_dir_for_pdf: str) -> Optional[str]:
        # This method is now effectively replaced by the logic in the new generate_pdf, 
        # but keeping it for structure if other parts of the class (not visible here) might use it.
        # For the purpose of this refactor, it's largely unused by the new generate_pdf.
        # However, the user's new generate_pdf has its own compilation logic.
        # To avoid confusion, I will keep the old _compile_latex and _get_pdf_page_count 
        # and the new generate_pdf will have its own self-contained compilation logic.
        # The existing _compile_latex and _get_pdf_page_count will NOT be used by the new generate_pdf body.
        tex_filepath_abs = os.path.abspath(tex_filepath)
        temp_compile_dir = os.path.dirname(tex_filepath_abs)
        filename_no_ext = os.path.splitext(os.path.basename(tex_filepath_abs))[0]

        cmd = [
            "pdflatex",
            "-interaction=nonstopmode",
            f"-output-directory={temp_compile_dir}",
            tex_filepath_abs
        ]
        
        print(f"OLD _compile_latex: Compiling LaTeX file: {tex_filepath_abs} into {temp_compile_dir}")
        # ... (keeping the rest of the old _compile_latex as is for now)
        compilation_succeeded = False
        for attempt in range(2):
            try:
                result = subprocess.run(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                if result.returncode != 0:
                    print(f"Error during LaTeX compilation (attempt {attempt+1}):")
                    print(result.stderr or result.stdout)
                    if attempt == 0:
                        print("Retrying compilation...")
                        continue
                    log_file = os.path.join(temp_compile_dir, f"{filename_no_ext}.log")
                    if os.path.exists(log_file):
                        print(f"LaTeX log file available at: {log_file}")
                    return None
                
                if attempt == 0:
                    print("First LaTeX pass successful, running second pass...")
                else:
                    compilation_succeeded = True
            except FileNotFoundError:
                print("Error: LaTeX compiler (pdflatex) not found. Please ensure LaTeX is installed.")
                return None
            except Exception as e:
                print(f"Unexpected error during LaTeX compilation: {e}")
                return None

        if compilation_succeeded:
            temp_pdf_path = os.path.join(temp_compile_dir, f"{filename_no_ext}.pdf")
            if os.path.exists(temp_pdf_path):
                if os.path.abspath(output_dir_for_pdf) == os.path.abspath(temp_compile_dir):
                    print(f"PDF successfully created in temp dir: {temp_pdf_path}")
                    return temp_pdf_path
                else:
                    os.makedirs(output_dir_for_pdf, exist_ok=True)
                    final_pdf_path = os.path.join(output_dir_for_pdf, f"{filename_no_ext}.pdf")
                    try:
                        shutil.move(temp_pdf_path, final_pdf_path)
                        print(f"PDF successfully created and moved to: {final_pdf_path}")
                        return final_pdf_path
                    except Exception as e:
                        print(f"Error moving PDF from {temp_pdf_path} to {final_pdf_path}: {e}")
                        return None
            else:
                print(f"Expected PDF file not found at {temp_pdf_path} despite compilation success signal.")
                return None
        return None

    def _get_pdf_page_count(self, pdf_path: str) -> Optional[int]:
        # This method will not be used by the new generate_pdf logic
        print(f"OLD _get_pdf_page_count: Checking page count for: {pdf_path}")
        # ... (keeping the rest of the old _get_pdf_page_count as is for now)
        if not os.path.exists(pdf_path):
            print(f"PDF file not found at {pdf_path} for page count check.")
            return None
        try:
            result = subprocess.run(
                ["pdfinfo", pdf_path],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    if line.startswith("Pages:"):
                        try:
                            page_count = int(line.split(":", 1)[1].strip())
                            print(f"PDF has {page_count} page(s) via pdfinfo.")
                            return page_count
                        except (IndexError, ValueError) as e:
                            print(f"Error parsing page count from pdfinfo: {e}")
            else:
                print(f"pdfinfo command failed or returned non-zero: {result.stderr or result.stdout}")
        except FileNotFoundError:
            print("pdfinfo command not found. Consider installing poppler-utils.")
        except Exception as e:
            print(f"Unexpected error running pdfinfo: {e}")

        log_file = pdf_path.replace('.pdf', '.log')
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    log_content = f.read()
                    match = re.search(r'Output written on .+?\.pdf \((\d+) pages', log_content)
                    if match:
                        page_count = int(match.group(1))
                        print(f"Found page count in log file: {page_count} page(s)")
                        return page_count
            except Exception as e:
                print(f"Error reading log file for page count: {e}")
        
        print("Could not determine page count from old method.")
        return 2 # Default from old method

    def generate_pdf(self, resume_data: dict, output_path: str) -> str:
        """
        1. Build raw LaTeX using the configured template function.
        2. Escaping of text is handled *within* the template_generate_func.
        3. Compile via pdflatex into output_path.
        """
        # Use a fixed page height as auto-sizing is controlled by self.no_auto_size (True in this flow)
        # The template function (generate_latex_content) uses DEFAULT_TEMPLATE_PAGE_HEIGHT_INCHES if page_height is None.
        # Or, if we want to strictly adhere to disabling auto-size, pass a specific height. 
        # User's new method body implies a fixed height (e.g., 11 inches).
        page_height_to_use = DEFAULT_INITIAL_PAGE_HEIGHT_INCHES # Using the module-level default, consistent with no_auto_size=True

        latex_source = self.template_generate_func(resume_data, page_height=page_height_to_use)

        # Create a temporary directory for compilation
        tempdir = tempfile.mkdtemp()
        tex_filename = "resume.tex" # Fixed name for temp .tex file
        tex_path = os.path.join(tempdir, tex_filename)
        
        final_pdf_name = os.path.basename(output_path)
        final_output_dir = os.path.dirname(output_path)
        os.makedirs(final_output_dir, exist_ok=True)

        try:
            with open(tex_path, "w", encoding="utf-8") as f:
                f.write(latex_source)
            print(f"Temporary LaTeX file written to: {tex_path}")

            # Compile LaTeX
            # Change current working directory to tempdir for pdflatex to find the file easily
            # and to keep auxiliary files contained.
            cmd = ["pdflatex", "-interaction=nonstopmode", "-output-directory", tempdir, tex_filename]
            # Run twice for references etc.
            for i in range(2):
                print(f"Running pdflatex command (Pass {i+1}/2): {' '.join(cmd)}")
                compile_process = subprocess.run(cmd, cwd=tempdir, capture_output=True, text=True)
                
                # Check for errors after each pass, but only raise critical error after final pass if still failing
                if compile_process.returncode != 0:
                    print(f"LaTeX Compilation Failed (Pass {i+1}/2) for {tex_path}.")
                    print("Stdout:", compile_process.stdout)
                    print("Stderr:", compile_process.stderr)
                    if i == 1: # If error on second pass
                        log_file_path = os.path.join(tempdir, tex_filename.replace(".tex", ".log"))
                        if os.path.exists(log_file_path):
                            try:
                                with open(log_file_path, "r", encoding="utf-8") as log_f:
                                    print("--- LaTeX Log File ---")
                                    print(log_f.read(2000)) # Print first 2000 chars of log
                                    print("--- End LaTeX Log File ---")
                            except Exception as e_log:
                                print(f"Error reading log file {log_file_path}: {e_log}")
                        raise Exception(f"LaTeX compilation failed after 2 passes. Error: {compile_process.stderr[:1000]}")
                else:
                    print(f"pdflatex Pass {i+1}/2 successful.")

            # After successful compilation (2 passes)
            compiled_pdf_in_tempdir = os.path.join(tempdir, tex_filename.replace(".tex", ".pdf"))

            if not os.path.exists(compiled_pdf_in_tempdir):
                raise Exception(f"Compiled PDF not found at {compiled_pdf_in_tempdir} after 2 successful pdflatex passes.")

            print(f"LaTeX compiled successfully, PDF at: {compiled_pdf_in_tempdir}")

            # Move the successfully compiled PDF to the final output_path
            shutil.move(compiled_pdf_in_tempdir, output_path)
            print(f"PDF moved to: {output_path}")

            return output_path
        finally:
            # Clean up the temporary directory
            if os.path.exists(tempdir):
                shutil.rmtree(tempdir)
                print(f"Cleaned up temporary directory: {tempdir}")

# This function is what working_app.py will import and call
def create_pdf_generator(template_name='classic', no_auto_size=False):
    return LatexPdfGenerator(template_name=template_name, no_auto_size=no_auto_size)


# Minimal main for CLI testing if this file is run directly (optional)
if __name__ == '__main__':
    # This is a placeholder for potential CLI testing of this module
    # The main CLI logic is in the user's original resume_generator.py
    print("Testing PDF Generation Module...")
    
    # Create a dummy resume_data for testing
    dummy_data = {
        "Personal Information": {"name": "Test User CLI", "email": "test@example.com"},
        "Summary/Objective": "This is a test summary.",
        "Education": [{"university": "Test Uni", "degree": "BS CS", "start_date": "2020", "end_date": "2024"}]
    }
    
    # Ensure output directory exists for testing
    cli_output_dir = "cli_test_output"
    os.makedirs(cli_output_dir, exist_ok=True)
    test_output_path = os.path.join(cli_output_dir, "test_resume_cli.pdf")

    # Test with auto-sizing enabled
    print("\n--- Test with auto-sizing ENABLED ---")
    generator_auto = create_pdf_generator(no_auto_size=False)
    env_status = generator_auto.check_environment()
    print(f"Environment Check: {env_status}")
    if env_status["status"] == "OK":
        pdf_path_auto = generator_auto.generate_pdf(dummy_data, test_output_path)
        if pdf_path_auto:
            print(f"CLI Test (auto-size): PDF generated at {pdf_path_auto}")
        else:
            print("CLI Test (auto-size): PDF generation failed.")
    else:
        print("CLI Test: Environment check failed, cannot generate PDF.")

    # Test with auto-sizing disabled
    # print("\n--- Test with auto-sizing DISABLED ---")
    # test_output_path_no_auto = os.path.join(cli_output_dir, "test_resume_cli_no_auto.pdf")
    # generator_no_auto = create_pdf_generator(no_auto_size=True)
    # env_status_no_auto = generator_no_auto.check_environment()
    # if env_status_no_auto["status"] == "OK":
    #     pdf_path_no_auto = generator_no_auto.generate_pdf(dummy_data, test_output_path_no_auto)
    #     if pdf_path_no_auto:
    #         print(f"CLI Test (no-auto-size): PDF generated at {pdf_path_no_auto}")
    #     else:
    #         print("CLI Test (no-auto-size): PDF generation failed.")
    # else:
    #      print("CLI Test: Environment check failed for no-auto-size, cannot generate PDF.") 