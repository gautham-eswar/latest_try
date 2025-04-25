#!/usr/bin/env python3
"""
Resume Optimizer Example Client
This script demonstrates how to use the Resume Optimizer API.
"""

import os
import sys
import requests
import json
import time
from pprint import pprint

# Configuration
API_BASE_URL = os.environ.get('API_BASE_URL', 'http://localhost:8080')

def check_health():
    """Check if the API is running"""
    print("Checking API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/api/health")
        response.raise_for_status()
        print(f"API is running. Status: {response.json()['status']}")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error: API is not running or not accessible: {e}")
        return False

def upload_resume(file_path):
    """Upload a resume file to the API"""
    print(f"Uploading resume: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"Error: File {file_path} not found")
        return None
    
    with open(file_path, 'rb') as f:
        files = {'resume': (os.path.basename(file_path), f)}
        response = requests.post(f"{API_BASE_URL}/api/upload", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print(f"Upload successful. Resume ID: {result['resume_id']}")
        return result['resume_id']
    else:
        print(f"Error uploading resume: {response.text}")
        return None

def optimize_resume(resume_id, job_description):
    """Optimize a resume for a specific job description"""
    print(f"Optimizing resume {resume_id} for job description...")
    
    data = {
        'resume_id': resume_id,
        'job_description': job_description
    }
    
    response = requests.post(
        f"{API_BASE_URL}/api/optimize",
        json=data
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"Optimization successful. Optimized resume ID: {result['optimized_resume_id']}")
        return result['optimized_resume_id']
    else:
        print(f"Error optimizing resume: {response.text}")
        return None

def download_resume(resume_id, format_type='json'):
    """Download a resume in the specified format"""
    print(f"Downloading resume {resume_id} in {format_type} format...")
    
    response = requests.get(f"{API_BASE_URL}/api/download/{resume_id}/{format_type}")
    
    if response.status_code == 200:
        filename = f"resume_{resume_id}.{format_type}"
        
        # For JSON, just display the content
        if format_type == 'json':
            print("Resume content:")
            pprint(response.json())
            return response.json()
        
        # For other formats, save to file
        else:
            with open(filename, 'wb') as f:
                f.write(response.content)
            print(f"Resume downloaded to {filename}")
            return filename
    else:
        print(f"Error downloading resume: {response.text}")
        return None

def run_full_example():
    """Run a complete example of the resume optimization workflow"""
    # Check if API is running
    if not check_health():
        sys.exit(1)
    
    # Example resume file path
    resume_file = "test_files/sample_resume.pdf"
    
    # Check if the file exists, if not, create a simple text file
    if not os.path.exists(resume_file):
        print(f"Test file {resume_file} not found. Creating a simple text resume...")
        os.makedirs("test_files", exist_ok=True)
        resume_file = "test_files/sample_resume.txt"
        with open(resume_file, "w") as f:
            f.write("""
John Doe
Software Engineer
john@example.com | (123) 456-7890

SKILLS
Python, JavaScript, React, Flask, Docker, AWS

EXPERIENCE
Senior Software Engineer - Tech Company (2020-Present)
- Developed scalable web applications using Python and Flask
- Implemented CI/CD pipelines with GitHub Actions
- Led team of 3 junior developers

Software Developer - Startup Inc. (2017-2020)
- Built responsive frontend using React and TypeScript
- Optimized database queries resulting in 30% performance improvement
- Collaborated with cross-functional teams to deliver features

EDUCATION
Bachelor of Science in Computer Science - University College (2013-2017)
            """)
    
    # Example job description
    job_description = """
    Senior Software Engineer
    
    We are looking for a Senior Software Engineer to join our team. The ideal candidate will have:
    
    - 5+ years of experience in software development
    - Strong proficiency in Python and JavaScript
    - Experience with web frameworks like Flask or Django
    - Knowledge of cloud platforms, preferably AWS
    - Experience with Docker and containerization
    - Excellent problem-solving skills
    
    Responsibilities include developing scalable web applications, mentoring junior developers,
    and collaborating with product managers to deliver high-quality features.
    """
    
    # Upload resume
    resume_id = upload_resume(resume_file)
    if not resume_id:
        sys.exit(1)
    
    # Wait a moment for processing
    time.sleep(1)
    
    # Optimize resume
    optimized_id = optimize_resume(resume_id, job_description)
    if not optimized_id:
        sys.exit(1)
    
    # Wait a moment for processing
    time.sleep(1)
    
    # Download in JSON format
    json_data = download_resume(optimized_id, 'json')
    
    # Download in PDF format if available
    pdf_file = download_resume(optimized_id, 'pdf')
    
    print("\nExample completed successfully!")

if __name__ == "__main__":
    run_full_example() 