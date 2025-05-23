#!/usr/bin/env python3
import json
import os
import logging
import time

from Pipeline.latex_generation import generate_resume_pdf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def main():
    print("Testing adaptive page sizing for PDF generation...")
    
    # Set up output directory
    output_dir = 'output_resumes'
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")
    
    # Load Abhiraj's resume data
    try:
        with open('abhiraj_resume.json', 'r', encoding='utf-8') as f:
            resume_data = json.load(f)
        print("Successfully loaded resume data.")
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return
    
    # Generate PDF with adaptive sizing
    timestamp = int(time.time())
    output_path = os.path.join(output_dir, f'abhiraj_resume_adaptive_{timestamp}.pdf')
    
    print(f"Generating PDF with adaptive sizing...")
    pdf_path, success = generate_resume_pdf(resume_data, output_path)
    
    if success:
        print(f"✅ SUCCESS: Resume fits on a single page!")
        if os.path.exists(pdf_path):
            print(f"PDF saved to: {os.path.abspath(pdf_path)}")
        else:
            print(f"PDF path returned: {pdf_path}, but file not found.")
    else:
        print(f"❌ Could not generate a single-page PDF.")
        if os.path.exists(pdf_path):
            print(f"Multi-page PDF saved to: {os.path.abspath(pdf_path)}")
    
    print("\nTest completed.")

if __name__ == "__main__":
    main() 