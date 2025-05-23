#!/usr/bin/env python3
"""
Test Deployment Script for Resume Optimizer

This script tests various endpoints of the deployed Resume Optimizer API to verify
that deployment was successful and all features are working correctly.
"""

import sys
import os
import argparse
import requests
import json
import time
from datetime import datetime
import logging
import tempfile
import random
import string

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s - %(message)s'
)
logger = logging.getLogger('test_deployment')

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Test the Resume Optimizer API deployment')
    parser.add_argument('--url', type=str, default='http://localhost:8080',
                        help='Base URL of the deployed API')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('--skip', type=str, nargs='+', choices=['health', 'upload', 'optimize', 'download'],
                        help='Skip specific tests')
    parser.add_argument('--resume', type=str, default='test_files/sample_resume.pdf',
                        help='Path to test resume file')
    parser.add_argument('--job-description', type=str, default='Software Engineer with Python and Flask experience',
                        help='Job description to use for testing')
    return parser.parse_args()

def test_health_endpoint(base_url, verbose=False):
    """Test the health endpoint."""
    logger.info(f"Testing health endpoint at {base_url}/api/health")
    start_time = time.time()
    try:
        response = requests.get(f"{base_url}/api/health", timeout=10)
        elapsed = time.time() - start_time
        
        if verbose:
            logger.info(f"Response time: {elapsed:.2f}s")
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response body: {response.text}")
        
        if response.status_code == 200:
            logger.info("✅ Health check passed")
            return True, response.json()
        else:
            logger.error(f"❌ Health check failed with status {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"❌ Health check failed with error: {str(e)}")
        return False, None

def test_upload_endpoint(base_url, resume_path, verbose=False):
    """Test the upload endpoint with a resume file."""
    if not os.path.exists(resume_path):
        logger.error(f"❌ Resume file not found: {resume_path}")
        return False, None
    
    logger.info(f"Testing upload endpoint with file: {resume_path}")
    
    try:
        with open(resume_path, 'rb') as f:
            files = {'file': (os.path.basename(resume_path), f, 'application/octet-stream')}
            start_time = time.time()
            response = requests.post(f"{base_url}/api/upload", files=files, timeout=30)
            elapsed = time.time() - start_time
        
        if verbose:
            logger.info(f"Response time: {elapsed:.2f}s")
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response body: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            resume_id = data.get('resume_id')
            if resume_id:
                logger.info(f"✅ Upload successful. Resume ID: {resume_id}")
                return True, data
            else:
                logger.error("❌ Upload response missing resume_id")
                return False, data
        else:
            logger.error(f"❌ Upload failed with status {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"❌ Upload failed with error: {str(e)}")
        return False, None

def test_optimize_endpoint(base_url, resume_id, job_description, verbose=False):
    """Test the optimize endpoint with a resume ID and job description."""
    logger.info(f"Testing optimize endpoint with resume ID: {resume_id}")
    
    payload = {
        'resume_id': resume_id,
        'job_description': job_description
    }
    
    try:
        start_time = time.time()
        response = requests.post(f"{base_url}/api/optimize", json=payload, timeout=60)
        elapsed = time.time() - start_time
        
        if verbose:
            logger.info(f"Response time: {elapsed:.2f}s")
            logger.info(f"Status code: {response.status_code}")
            logger.info(f"Response body: {response.text[:500]}...")  # Truncate long responses
        
        if response.status_code == 200:
            data = response.json()
            logger.info("✅ Optimization successful")
            return True, data
        else:
            logger.error(f"❌ Optimization failed with status {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"❌ Optimization failed with error: {str(e)}")
        return False, None

def test_download_endpoint(base_url, resume_id, format_type='json', verbose=False):
    """Test the download endpoint with a resume ID and format type."""
    logger.info(f"Testing download endpoint for resume ID: {resume_id}, format: {format_type}")
    
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/api/download/{resume_id}/{format_type}", timeout=30)
        elapsed = time.time() - start_time
        
        if verbose:
            logger.info(f"Response time: {elapsed:.2f}s")
            logger.info(f"Status code: {response.status_code}")
            if format_type == 'json':
                logger.info(f"Response body: {response.text[:500]}...")  # Truncate long responses
        
        if response.status_code == 200:
            logger.info(f"✅ Download successful for format: {format_type}")
            
            # Save the downloaded file for verification
            if format_type != 'json':
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                random_suffix = ''.join(random.choices(string.ascii_lowercase + string.digits, k=6))
                filename = f"download_test_{timestamp}_{random_suffix}.{format_type}"
                
                with open(filename, 'wb') as f:
                    f.write(response.content)
                logger.info(f"📄 Downloaded file saved as: {filename}")
            
            return True, filename if format_type != 'json' else response.json()
        else:
            logger.error(f"❌ Download failed with status {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"❌ Download failed with error: {str(e)}")
        return False, None

def test_system_diagnostics(base_url, verbose=False):
    """Test the system diagnostics endpoint."""
    logger.info(f"Testing system diagnostics at {base_url}/status")
    
    try:
        start_time = time.time()
        response = requests.get(f"{base_url}/status", timeout=10)
        elapsed = time.time() - start_time
        
        if verbose:
            logger.info(f"Response time: {elapsed:.2f}s")
            logger.info(f"Status code: {response.status_code}")
        
        if response.status_code == 200:
            logger.info("✅ System diagnostics check passed")
            return True, "System diagnostics available"
        else:
            logger.error(f"❌ System diagnostics failed with status {response.status_code}")
            return False, None
    except Exception as e:
        logger.error(f"❌ System diagnostics failed with error: {str(e)}")
        return False, None

def run_tests(base_url, resume_path, job_description, skip=None, verbose=False):
    """Run all tests and report results."""
    skip = skip or []
    results = {}
    start_time = time.time()
    
    # Print deployment information
    logger.info("=" * 60)
    logger.info(f"RESUME OPTIMIZER DEPLOYMENT TEST")
    logger.info(f"Base URL: {base_url}")
    logger.info(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)
    
    # Test health endpoint
    if 'health' not in skip:
        results['health'] = test_health_endpoint(base_url, verbose)
    
    # Test upload endpoint
    if 'upload' not in skip:
        results['upload'] = test_upload_endpoint(base_url, resume_path, verbose)
        if not results['upload'][0]:
            logger.error("Upload failed. Skipping optimize and download tests.")
            skip.extend(['optimize', 'download'])
        else:
            resume_id = results['upload'][1]['resume_id']
    
    # Test optimize endpoint
    if 'optimize' not in skip:
        results['optimize'] = test_optimize_endpoint(base_url, resume_id, job_description, verbose)
    
    # Test download endpoint for different formats
    if 'download' not in skip:
        results['download_json'] = test_download_endpoint(base_url, resume_id, 'json', verbose)
        results['download_latex'] = test_download_endpoint(base_url, resume_id, 'latex', verbose)
        results['download_pdf'] = test_download_endpoint(base_url, resume_id, 'pdf', verbose)
    
    # Test system diagnostics
    results['diagnostics'] = test_system_diagnostics(base_url, verbose)
    
    # Report summary
    elapsed = time.time() - start_time
    logger.info("=" * 60)
    logger.info(f"TEST SUMMARY (completed in {elapsed:.2f}s)")
    logger.info("=" * 60)
    
    all_passed = True
    for test_name, (passed, _) in results.items():
        status = "✅ PASSED" if passed else "❌ FAILED"
        logger.info(f"{test_name}: {status}")
        all_passed = all_passed and passed
    
    logger.info("=" * 60)
    if all_passed:
        logger.info("🎉 ALL TESTS PASSED! Deployment is successful.")
    else:
        logger.info("⚠️ SOME TESTS FAILED. See above for details.")
    
    return all_passed, results

if __name__ == "__main__":
    args = parse_args()
    success, results = run_tests(
        args.url, 
        args.resume, 
        args.job_description,
        args.skip,
        args.verbose
    )
    sys.exit(0 if success else 1) 