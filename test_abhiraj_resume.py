#!/usr/bin/env python3
import json
import os
import subprocess
from Pipeline.latex_resume.templates.classic_template import generate_latex_content

print("Testing LaTeX generation with Abhiraj's resume data...")

# Set up output directory
output_dir = 'output_resumes'
if not os.path.exists(output_dir):
    os.makedirs(output_dir)
    print(f"Created output directory: {output_dir}")

# Load the JSON file
try:
    with open('abhiraj_resume.json', 'r', encoding='utf-8') as f:
        resume_data = json.load(f)
    print("Successfully loaded resume data.")
except Exception as e:
    print(f"Error loading JSON file: {e}")
    exit(1)

# Try different page heights to find one that fits the content on a single page
page_heights = [11.0, 12.0, 13.0, 14.0, 15.0]

for height in page_heights:
    print(f"\n--- Testing with page height: {height} inches ---")
    
    # Generate LaTeX content with specific page height
    try:
        latex_content = generate_latex_content(resume_data, page_height=height)
        print(f"Successfully generated LaTeX content for height {height}in.")
    except Exception as e:
        print(f"Error generating LaTeX content: {e}")
        continue

    # Save the LaTeX output
    tex_file = os.path.join(output_dir, f'abhiraj_resume_{height}in.tex')
    try:
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(latex_content)
        print(f"Saved LaTeX output to {tex_file}")
    except Exception as e:
        print(f"Error saving output file: {e}")
        continue

    # Generate PDF from LaTeX
    print(f"Generating PDF with {height}in height...")
    try:
        # Change to output directory to keep auxiliary files contained
        original_dir = os.getcwd()
        os.chdir(output_dir)
        
        # Run pdflatex (twice to resolve references)
        tex_filename = os.path.basename(tex_file)
        
        # Redirect stdout to null to reduce output clutter
        with open(os.devnull, 'w') as devnull:
            subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_filename], 
                          check=True, stdout=devnull)
            subprocess.run(['pdflatex', '-interaction=nonstopmode', tex_filename], 
                          check=True, stdout=devnull)
        
        # Return to original directory
        os.chdir(original_dir)
        
        pdf_file = os.path.join(output_dir, f'abhiraj_resume_{height}in.pdf')
        if os.path.exists(pdf_file):
            print(f"Generated PDF: {pdf_file}")
            
            # Check number of pages in the PDF (requires pdfinfo from poppler)
            try:
                result = subprocess.run(['pdfinfo', pdf_file], 
                                      capture_output=True, text=True, check=True)
                for line in result.stdout.split('\n'):
                    if line.startswith('Pages:'):
                        num_pages = int(line.split(':')[1].strip())
                        print(f"PDF has {num_pages} page(s)")
                        if num_pages == 1:
                            print("✅ SUCCESS: Resume fits on a single page!")
                        else:
                            print("❌ Resume still spans multiple pages.")
                        break
            except (subprocess.SubprocessError, FileNotFoundError):
                print("Could not determine number of pages (pdfinfo not available)")
        else:
            print("PDF file not found. Check for LaTeX errors.")
    except subprocess.CalledProcessError as e:
        print(f"Error during PDF generation: {e}")
    except Exception as e:
        print(f"Unexpected error during PDF generation: {e}")
    finally:
        # Ensure we return to the original directory even if there's an error
        if 'original_dir' in locals():
            os.chdir(original_dir)

print("\nDone! Generated PDFs with different page heights.") 