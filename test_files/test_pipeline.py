#!/usr/bin/env python3
"""
Manual Testing Script for Resume Optimization Pipeline

This script provides a CLI interface to manually test each stage of the resume
optimization pipeline with detailed output.
"""

import os
import json
import time
import argparse
import requests
from pathlib import Path
from pprint import pprint

# Configure API endpoints
BASE_URL = "http://localhost:8085"
UPLOAD_ENDPOINT = f"{BASE_URL}/api/upload"
OPTIMIZE_ENDPOINT = f"{BASE_URL}/api/optimize"
DOWNLOAD_ENDPOINT = f"{BASE_URL}/api/download"
HEALTH_ENDPOINT = f"{BASE_URL}/api/health"

# Configure directories
SCRIPT_DIR = Path(__file__).parent
TEST_FILES_DIR = SCRIPT_DIR
OUTPUT_DIR = SCRIPT_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

def check_server():
    """Check if the server is running"""
    try:
        response = requests.get(HEALTH_ENDPOINT, timeout=5)
        if response.status_code == 200:
            print(f"✅ Server is running at {BASE_URL}")
            return True
        else:
            print(f"❌ Server returned status code {response.status_code}")
            return False
    except requests.RequestException as e:
        print(f"❌ Failed to connect to server: {e}")
        return False

def upload_resume(resume_path):
    """Upload a resume and return the resume_id"""
    print("\n🔄 STAGE 1: RESUME UPLOAD")
    print(f"Uploading resume from: {resume_path}")
    
    start_time = time.time()
    
    try:
        with open(resume_path, 'rb') as f:
            files = {'file': (resume_path.name, f)}
            response = requests.post(UPLOAD_ENDPOINT, files=files)
        
        execution_time = time.time() - start_time
        print(f"⏱️  Upload completed in {execution_time:.2f} seconds")
        
        if response.status_code == 200:
            response_data = response.json()
            resume_id = response_data.get('resume_id')
            print(f"✅ Upload successful! Resume ID: {resume_id}")
            print("\n📄 Parsed Resume Data:")
            if 'data' in response_data:
                pprint(response_data['data'])
            else:
                print("No parsed data returned")
            
            # Save the response for reference
            output_file = OUTPUT_DIR / "1_upload_response.json"
            with open(output_file, 'w') as f:
                json.dump(response_data, f, indent=2)
            print(f"💾 Response saved to {output_file}")
            
            return resume_id
        else:
            print(f"❌ Upload failed with status code {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception during upload: {e}")
        return None

def optimize_resume(resume_id, job_description_path):
    """Optimize a resume with a job description"""
    print("\n🔄 STAGE 2: RESUME OPTIMIZATION")
    print(f"Optimizing resume {resume_id} with job description from: {job_description_path}")
    
    try:
        # Read job description
        with open(job_description_path, 'r') as f:
            job_description_text = f.read()
        
        # Prepare optimization request
        job_description = {
            "title": "Software Engineer",
            "description": job_description_text
        }
        
        request_data = {
            "resume_id": resume_id,
            "job_description": job_description
        }
        
        print("\n📄 Job Description:")
        print(f"Title: {job_description['title']}")
        print(f"Description (first 100 chars): {job_description['description'][:100]}...")
        
        start_time = time.time()
        response = requests.post(OPTIMIZE_ENDPOINT, json=request_data)
        execution_time = time.time() - start_time
        
        print(f"⏱️  Optimization completed in {execution_time:.2f} seconds")
        
        if response.status_code == 200:
            response_data = response.json()
            print("✅ Optimization successful!")
            
            print("\n📊 Optimization Analysis:")
            if 'analysis' in response_data:
                pprint(response_data['analysis'])
            
            print("\n📄 Optimized Resume Data:")
            if 'data' in response_data:
                pprint(response_data['data'])
            
            # Save the response for reference
            output_file = OUTPUT_DIR / "2_optimize_response.json"
            with open(output_file, 'w') as f:
                json.dump(response_data, f, indent=2)
            print(f"💾 Response saved to {output_file}")
            
            return response_data
        else:
            print(f"❌ Optimization failed with status code {response.status_code}")
            try:
                error_data = response.json()
                print(f"Error: {error_data.get('message', 'Unknown error')}")
            except:
                print(f"Error: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception during optimization: {e}")
        return None

def download_resume(resume_id, format_type):
    """Download a resume in the specified format"""
    print(f"\n🔄 STAGE 3: RESUME DOWNLOAD ({format_type.upper()})")
    print(f"Downloading resume {resume_id} in {format_type} format")
    
    start_time = time.time()
    response = requests.get(f"{DOWNLOAD_ENDPOINT}/{resume_id}/{format_type}")
    execution_time = time.time() - start_time
    
    print(f"⏱️  Download completed in {execution_time:.2f} seconds")
    
    if response.status_code == 200:
        content_type = response.headers.get('Content-Type', '')
        print(f"✅ Download successful! Content-Type: {content_type}")
        
        # Save the downloaded file
        extension = format_type
        if format_type == 'json':
            output_file = OUTPUT_DIR / f"3_download_resume_{format_type}.json"
            with open(output_file, 'w') as f:
                json.dump(response.json(), f, indent=2)
        else:
            output_file = OUTPUT_DIR / f"3_download_resume.{extension}"
            with open(output_file, 'wb') as f:
                f.write(response.content)
        
        print(f"💾 Downloaded file saved to {output_file}")
        return output_file
    else:
        print(f"❌ Download failed with status code {response.status_code}")
        try:
            error_data = response.json()
            print(f"Error: {error_data.get('message', 'Unknown error')}")
        except:
            print(f"Error: {response.text}")
        return None

def full_pipeline(resume_path, job_description_path, format_type):
    """Run the full pipeline from upload to download"""
    print("\n🚀 Starting full resume optimization pipeline")
    
    if not check_server():
        return False
    
    # Stage 1: Upload Resume
    resume_id = upload_resume(resume_path)
    if not resume_id:
        print("❌ Pipeline failed at upload stage")
        return False
    
    # Stage 2: Optimize Resume
    optimize_result = optimize_resume(resume_id, job_description_path)
    if not optimize_result:
        print("❌ Pipeline failed at optimization stage")
        return False
    
    # Stage 3: Download Resume
    download_result = download_resume(resume_id, format_type)
    if not download_result:
        print("❌ Pipeline failed at download stage")
        return False
    
    print("\n✅ Full pipeline completed successfully!")
    return True

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Test resume optimization pipeline")
    parser.add_argument('--resume', type=str, default='sample_resume.txt',
                      help='Path to resume file')
    parser.add_argument('--job', type=str, default='job_description.txt',
                      help='Path to job description file')
    parser.add_argument('--format', type=str, default='json', choices=['json', 'pdf', 'latex'],
                      help='Output format')
    parser.add_argument('--stage', type=int, choices=[1, 2, 3],
                      help='Run only a specific stage (1=upload, 2=optimize, 3=download)')
    parser.add_argument('--resume-id', type=str,
                      help='Resume ID for stage 2 or 3 (required if not running from stage 1)')
    
    return parser.parse_args()

if __name__ == '__main__':
    args = parse_args()
    
    # Resolve paths
    resume_path = Path(args.resume)
    if not resume_path.is_absolute():
        resume_path = TEST_FILES_DIR / resume_path
    
    job_description_path = Path(args.job)
    if not job_description_path.is_absolute():
        job_description_path = TEST_FILES_DIR / job_description_path
    
    if args.stage:
        # Run specific stage
        if args.stage == 1:
            # Upload only
            upload_resume(resume_path)
        elif args.stage == 2:
            # Optimize only
            if not args.resume_id:
                print("❌ Resume ID is required for optimization stage")
                exit(1)
            optimize_resume(args.resume_id, job_description_path)
        elif args.stage == 3:
            # Download only
            if not args.resume_id:
                print("❌ Resume ID is required for download stage")
                exit(1)
            download_resume(args.resume_id, args.format)
    else:
        # Run full pipeline
        full_pipeline(resume_path, job_description_path, args.format) 