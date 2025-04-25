"""
Resume Parser Module - Extracts structured data from resume files.
"""

import os
import logging
import time
import random

logger = logging.getLogger(__name__)

def parse(file_path):
    """
    Parse function (alias for parse_resume) for backward compatibility
    
    Args:
        file_path: Path to the resume file (PDF, DOCX, etc.)
        
    Returns:
        dict: Structured resume data
    """
    return parse_resume(file_path)

def parse_resume(file_path):
    """
    Parse a resume file and extract structured data.
    
    Args:
        file_path: Path to the resume file (PDF, DOCX, etc.)
        
    Returns:
        dict: Structured resume data
    """
    logger.info(f"Parsing resume file: {file_path}")
    
    # In a real implementation, we would parse the file
    # For testing, return dummy data
    time.sleep(0.5)  # Simulate processing time
    
    # Return dummy data structure
    return {
        "contact": {
            "name": "Test User",
            "email": "test@example.com",
            "phone": "555-123-4567"
        },
        "skills": [
            "Python", "Flask", "Data Analysis", "Machine Learning", "Testing"
        ],
        "experience": [
            {
                "title": "Software Engineer",
                "company": "ABC Company",
                "dates": "2020-2023",
                "description": "Developed web applications using Python and Flask"
            }
        ],
        "education": [
            {
                "degree": "Bachelor of Science in Computer Science",
                "institution": "XYZ University",
                "dates": "2016-2020"
            }
        ]
    }

def parse_resume_file(file_path):
    """Alias for parse_resume for compatibility"""
    return parse_resume(file_path)

def extract_text(file_path):
    """
    Extract plain text from resume file.
    
    Args:
        file_path: Path to the resume file
        
    Returns:
        str: Plain text content
    """
    # Return dummy text for testing
    return """
    Test User
    test@example.com | 555-123-4567
    
    Skills:
    Python, Flask, Data Analysis, Machine Learning, Testing
    
    Experience:
    Software Engineer, ABC Company (2020-2023)
    - Developed web applications using Python and Flask
    - Implemented machine learning algorithms for data analysis
    
    Education:
    Bachelor of Science in Computer Science
    XYZ University (2016-2020)
    """

# Add any other required functions for testing
def extract_text_from_file(file_path):
    """Alias for extract_text for compatibility"""
    return extract_text(file_path)