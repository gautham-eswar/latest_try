import argparse
import os
import sys
import importlib
import glob
import re
import subprocess
import json
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
from templates import get_available_templates, load_template

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
                print(f"Error during LaTeX compilation (attempt {attempt+1}):")
                print(result.stderr or result.stdout)
                
                # Try once more with the second attempt
                if attempt == 0:
                    print("Retrying compilation...")
                    continue
                
                print("LaTeX compilation failed. Please check the .tex file and LaTeX installation.")
                # Show path to .log file for debugging
                log_file = os.path.join(output_dir, f"{filename}.log")
                if os.path.exists(log_file):
                    print(f"LaTeX log file available at: {log_file}")
                return False
            
            # Success on this attempt - if it's the first, continue to the second run
            if attempt == 0:
                print("First pass successful, running second pass...")
        
        # If we reached here, both compilations were successful
        pdf_path = os.path.join(output_dir, f"{filename}.pdf")
        if os.path.exists(pdf_path):
            print(f"PDF successfully created: {pdf_path}")
            return True
        else:
            print(f"Expected PDF file not found at {pdf_path} despite successful compilation.")
            return False
    
    except FileNotFoundError:
        print("Error: LaTeX compiler (pdflatex) not found. Please ensure LaTeX is installed and in your PATH.")
        print("On most systems, you can install LaTeX through:")
        print("  - macOS: 'brew install --cask mactex' or install MacTeX from https://tug.org/mactex/")
        print("  - Linux: 'sudo apt-get install texlive-full' (Ubuntu/Debian) or 'sudo dnf install texlive-scheme-full' (Fedora)")
        print("  - Windows: Install MiKTeX from https://miktex.org/download")
        return False
    
    except Exception as e:
        print(f"Unexpected error during LaTeX compilation: {e}")
        return False

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