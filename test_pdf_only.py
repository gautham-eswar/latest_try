#!/usr/bin/env python3
import json
import os
import logging
import time
import sys
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Import the PDF generation function
from Pipeline.latex_generation import generate_resume_pdf

def run_pdf_test():
    """
    Test the PDF generation functionality directly with Abhiraj's resume data.
    """
    logger.info("Starting PDF generation test")
    
    # Load Abhiraj's resume data
    try:
        with open("abhiraj_resume.json", "r") as f:
            resume_data = json.load(f)
        logger.info("Successfully loaded resume data")

        # --- DIRECT PRINT DIAGNOSTIC AFTER LOAD ---
        print("--- PRINT DIAGNOSTIC (test_pdf_only.py): Data loaded from abhiraj_resume.json ---", flush=True)
        experience_direct = resume_data.get("Experience")
        skills_direct = resume_data.get("Skills")
        if experience_direct:
            print("Experience section (direct from load):", flush=True)
            try: print(json.dumps(experience_direct, indent=2), flush=True)
            except: print(str(experience_direct), flush=True)
        if skills_direct:
            print("Skills section (direct from load):", flush=True)
            try: print(json.dumps(skills_direct, indent=2), flush=True)
            except: print(str(skills_direct), flush=True)
        print("--- END PRINT DIAGNOSTIC (test_pdf_only.py) ---", flush=True)
        # --- END DIRECT PRINT DIAGNOSTIC ---

    except Exception as e:
        logger.error(f"Error loading resume data: {e}")
        return False

    # Create output directory if it doesn't exist
    output_dir = os.path.abspath("output_resumes")
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate a unique output filename with timestamp
    timestamp = int(time.time())
    output_pdf_path = os.path.join(output_dir, f"abhiraj_direct_test_{timestamp}.pdf")
    
    # Generate the PDF
    pdf_path, success = generate_resume_pdf(resume_data, output_pdf_path)
    
    # Check results
    if success:
        logger.info(f"PDF generation successful! Single page PDF created at: {pdf_path}")
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            logger.info(f"PDF file size: {file_size} bytes")
            logger.info(f"You can view the PDF at: {pdf_path}")
            return True
        else:
            logger.error(f"PDF file not found at expected location: {pdf_path}")
            return False
    else:
        logger.error("PDF generation failed or resulted in multi-page output")
        if os.path.exists(pdf_path):
            logger.info(f"PDF file was generated but may have multiple pages: {pdf_path}")
            return False
        else:
            logger.error("No PDF file was generated")
            return False

if __name__ == "__main__":
    result = run_pdf_test()
    logger.info(f"Test completed with result: {'Success' if result else 'Failure'}")
    sys.exit(0 if result else 1) 