#!/usr/bin/env python3
"""
Test Error Handling for Resume Optimizer

This script tests various error scenarios in the resume processing pipeline
to ensure proper error handling and appropriate responses.
"""

import os
import unittest
import tempfile
import requests
import json
import time
import random
import string
from pathlib import Path
import logging
import sys
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_error_handling')

# Adjust these settings based on your test environment
TEST_SERVER_URL = os.environ.get("TEST_SERVER_URL", "http://localhost:8085")  # Get from env or use default
UPLOAD_ENDPOINT = f"{TEST_SERVER_URL}/api/upload"
OPTIMIZE_ENDPOINT = f"{TEST_SERVER_URL}/api/optimize"
DOWNLOAD_ENDPOINT = f"{TEST_SERVER_URL}/api/download"
HEALTH_ENDPOINT = f"{TEST_SERVER_URL}/api/health"

class FlaskServerThread(threading.Thread):
    """Run the Flask server in a separate thread for testing"""
    
    def __init__(self, app_module="working_app", port=8085, skip_start=None):
        threading.Thread.__init__(self)
        self.daemon = True
        self.port = port
        self.app_module = app_module
        self.process = None
        # Check if we should skip starting the server (for when it's already running)
        self.skip_start = skip_start or os.environ.get("SKIP_SERVER_START", "").lower() in ("1", "true", "yes")
        
    def run(self):
        """Start the Flask server"""
        if self.skip_start:
            logger.info("Skipping server startup as requested")
            return
            
        import subprocess
        cmd = [
            "python3", 
            f"{self.app_module}.py", 
            f"--port={self.port}",
            "--debug"
        ]
        self.process = subprocess.Popen(cmd)
        
    def stop(self):
        """Stop the Flask server"""
        if self.process and not self.skip_start:
            self.process.terminate()
            self.process.wait()

class ErrorHandlingTestCase(unittest.TestCase):
    """Test case for verifying error handling in the resume optimizer"""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment"""
        # Start the Flask server
        cls.server_thread = FlaskServerThread()
        cls.server_thread.start()
        
        # Wait for the server to start
        wait_time = int(os.environ.get("SERVER_WAIT_TIME", "2"))
        time.sleep(wait_time)
        
        # Check if the server is running
        cls.server_running = False
        try:
            response = requests.get(HEALTH_ENDPOINT)
            if response.status_code == 200:
                cls.server_running = True
                logger.info("Test server is up and running")
            else:
                logger.error(f"Test server returned status code {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to connect to test server: {e}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment"""
        # Stop the Flask server
        if cls.server_thread:
            cls.server_thread.stop()
            logger.info("Test server stopped")
    
    def setUp(self):
        """Set up before each test"""
        if not self.server_running:
            self.skipTest("Test server is not running")
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create test data
        self.create_test_data()
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up temporary directory
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()
    
    def create_test_data(self):
        """Create test data for the tests"""
        # Create a valid sample text file as a minimal resume
        self.valid_resume_path = self.test_dir / "valid_resume.txt"
        self.valid_resume_path.write_text("Sample resume content with skills and experience")
        
        # Create an invalid file (not a resume)
        self.invalid_file_path = self.test_dir / "invalid_file.xyz"
        self.invalid_file_path.write_text("This is not a valid resume file format")
        
        # Create a valid job description
        self.valid_job_desc = {
            "title": "Software Engineer",
            "description": "Looking for Python developers with experience in Flask, API development, and testing."
        }
        
        # Create a malformed job description (missing required fields)
        self.malformed_job_desc = {
            "invalid_field": "This job description is missing required fields"
        }
        
        # Generate a non-existent resume ID
        self.non_existent_resume_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    
    def test_upload_invalid_file_format(self):
        """Test uploading a file with an invalid format"""
        logger.info("Testing upload of invalid file format")
        
        start_time = time.time()
        with open(self.invalid_file_path, 'rb') as f:
            files = {'file': (self.invalid_file_path.name, f)}
            response = requests.post(UPLOAD_ENDPOINT, files=files)
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept invalid file format")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_missing_resume_id_optimize(self):
        """Test submitting a missing resumeId to the optimize endpoint"""
        logger.info("Testing optimize with missing resume ID")
        
        start_time = time.time()
        # Submit request without resumeId
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={"job_description": self.valid_job_desc}
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept missing resume ID")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_non_existent_resume_download(self):
        """Test requesting a non-existent resume for download"""
        logger.info(f"Testing download of non-existent resume ID: {self.non_existent_resume_id}")
        
        formats = ['pdf', 'json', 'latex']
        for format_type in formats:
            with self.subTest(format=format_type):
                start_time = time.time()
                response = requests.get(f"{DOWNLOAD_ENDPOINT}/{self.non_existent_resume_id}/{format_type}")
                
                execution_time = time.time() - start_time
                logger.info(f"Response received for {format_type} in {execution_time:.2f}s with status code {response.status_code}")
                
                # Verify the response indicates an error
                self.assertNotEqual(response.status_code, 200, f"Should not find non-existent resume in {format_type} format")
                self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
                
                # For JSON responses, verify the error message
                if 'application/json' in response.headers.get('Content-Type', ''):
                    response_data = response.json()
                    self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
                    self.assertIn('message', response_data, "Response should contain error message")
                    logger.info(f"Error message for {format_type}: {response_data.get('message')}")
    
    def test_malformed_job_description(self):
        """Test optimizing with a malformed job description"""
        logger.info("Testing optimization with malformed job description")
        
        # First upload a valid resume to get a resume ID
        with open(self.valid_resume_path, 'rb') as f:
            files = {'file': (self.valid_resume_path.name, f)}
            upload_response = requests.post(UPLOAD_ENDPOINT, files=files)
        
        # Skip if upload fails (already tested in another test)
        if upload_response.status_code != 200:
            self.skipTest("Resume upload failed, skipping malformed job description test")
        
        upload_data = upload_response.json()
        resume_id = upload_data.get('resume_id')
        self.assertIsNotNone(resume_id, "Failed to get resume ID from upload response")
        
        # Now test optimization with malformed job description
        start_time = time.time()
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={
                "resume_id": resume_id,
                "job_description": self.malformed_job_desc
            }
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept malformed job description")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_validation_reporting(self):
        """Test that error responses contain validation information"""
        logger.info("Testing validation reporting in error responses")
        
        # Create a request with multiple errors
        start_time = time.time()
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={
                # Missing resume_id
                "job_description": {
                    # Invalid job description format
                    "invalid_field": "value",
                    "another_invalid": 123
                },
                "invalid_param": "should not be here"
            }
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should reject invalid request")
        
        # Verify the response contains validation details
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        
        # Check for detailed validation information
        # This could be in various formats depending on the implementation
        detailed_validation = False
        for field in ['errors', 'validation_errors', 'details', 'validation']:
            if field in response_data:
                detailed_validation = True
                logger.info(f"Validation details found in field '{field}': {response_data[field]}")
                break
        
        # Some implementations might include validation details in the main message
        if not detailed_validation and len(response_data.get('message', '')) > 30:
            logger.info(f"Potentially detailed error message: {response_data['message']}")

if __name__ == '__main__':
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_suite = unittest.TestLoader().loadTestsFromTestCase(ErrorHandlingTestCase)
    test_results = test_runner.run(test_suite)
    
    # Return non-zero exit code if tests failed
    sys.exit(0 if test_results.wasSuccessful() else 1) 
"""
Test Error Handling for Resume Optimizer

This script tests various error scenarios in the resume processing pipeline
to ensure proper error handling and appropriate responses.
"""

import os
import unittest
import tempfile
import requests
import json
import time
import random
import string
from pathlib import Path
import logging
import sys
import threading
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_error_handling')

# Adjust these settings based on your test environment
TEST_SERVER_URL = os.environ.get("TEST_SERVER_URL", "http://localhost:8085")  # Get from env or use default
UPLOAD_ENDPOINT = f"{TEST_SERVER_URL}/api/upload"
OPTIMIZE_ENDPOINT = f"{TEST_SERVER_URL}/api/optimize"
DOWNLOAD_ENDPOINT = f"{TEST_SERVER_URL}/api/download"
HEALTH_ENDPOINT = f"{TEST_SERVER_URL}/api/health"

class FlaskServerThread(threading.Thread):
    """Run the Flask server in a separate thread for testing"""
    
    def __init__(self, app_module="working_app", port=8085, skip_start=None):
        threading.Thread.__init__(self)
        self.daemon = True
        self.port = port
        self.app_module = app_module
        self.process = None
        # Check if we should skip starting the server (for when it's already running)
        self.skip_start = skip_start or os.environ.get("SKIP_SERVER_START", "").lower() in ("1", "true", "yes")
        
    def run(self):
        """Start the Flask server"""
        if self.skip_start:
            logger.info("Skipping server startup as requested")
            return
            
        import subprocess
        cmd = [
            "python3", 
            f"{self.app_module}.py", 
            f"--port={self.port}",
            "--debug"
        ]
        self.process = subprocess.Popen(cmd)
        
    def stop(self):
        """Stop the Flask server"""
        if self.process and not self.skip_start:
            self.process.terminate()
            self.process.wait()

class ErrorHandlingTestCase(unittest.TestCase):
    """Test case for verifying error handling in the resume optimizer"""
    
    @classmethod
    def setUpClass(cls):
        """Set up the test environment"""
        # Start the Flask server
        cls.server_thread = FlaskServerThread()
        cls.server_thread.start()
        
        # Wait for the server to start
        wait_time = int(os.environ.get("SERVER_WAIT_TIME", "2"))
        time.sleep(wait_time)
        
        # Check if the server is running
        cls.server_running = False
        try:
            response = requests.get(HEALTH_ENDPOINT)
            if response.status_code == 200:
                cls.server_running = True
                logger.info("Test server is up and running")
            else:
                logger.error(f"Test server returned status code {response.status_code}")
        except requests.RequestException as e:
            logger.error(f"Failed to connect to test server: {e}")
    
    @classmethod
    def tearDownClass(cls):
        """Clean up the test environment"""
        # Stop the Flask server
        if cls.server_thread:
            cls.server_thread.stop()
            logger.info("Test server stopped")
    
    def setUp(self):
        """Set up before each test"""
        if not self.server_running:
            self.skipTest("Test server is not running")
        
        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)
        
        # Create test data
        self.create_test_data()
    
    def tearDown(self):
        """Clean up after each test"""
        # Clean up temporary directory
        if hasattr(self, 'temp_dir'):
            self.temp_dir.cleanup()
    
    def create_test_data(self):
        """Create test data for the tests"""
        # Create a valid sample text file as a minimal resume
        self.valid_resume_path = self.test_dir / "valid_resume.txt"
        self.valid_resume_path.write_text("Sample resume content with skills and experience")
        
        # Create an invalid file (not a resume)
        self.invalid_file_path = self.test_dir / "invalid_file.xyz"
        self.invalid_file_path.write_text("This is not a valid resume file format")
        
        # Create a valid job description
        self.valid_job_desc = {
            "title": "Software Engineer",
            "description": "Looking for Python developers with experience in Flask, API development, and testing."
        }
        
        # Create a malformed job description (missing required fields)
        self.malformed_job_desc = {
            "invalid_field": "This job description is missing required fields"
        }
        
        # Generate a non-existent resume ID
        self.non_existent_resume_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=20))
    
    def test_upload_invalid_file_format(self):
        """Test uploading a file with an invalid format"""
        logger.info("Testing upload of invalid file format")
        
        start_time = time.time()
        with open(self.invalid_file_path, 'rb') as f:
            files = {'file': (self.invalid_file_path.name, f)}
            response = requests.post(UPLOAD_ENDPOINT, files=files)
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept invalid file format")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_missing_resume_id_optimize(self):
        """Test submitting a missing resumeId to the optimize endpoint"""
        logger.info("Testing optimize with missing resume ID")
        
        start_time = time.time()
        # Submit request without resumeId
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={"job_description": self.valid_job_desc}
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept missing resume ID")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_non_existent_resume_download(self):
        """Test requesting a non-existent resume for download"""
        logger.info(f"Testing download of non-existent resume ID: {self.non_existent_resume_id}")
        
        formats = ['pdf', 'json', 'latex']
        for format_type in formats:
            with self.subTest(format=format_type):
                start_time = time.time()
                response = requests.get(f"{DOWNLOAD_ENDPOINT}/{self.non_existent_resume_id}/{format_type}")
                
                execution_time = time.time() - start_time
                logger.info(f"Response received for {format_type} in {execution_time:.2f}s with status code {response.status_code}")
                
                # Verify the response indicates an error
                self.assertNotEqual(response.status_code, 200, f"Should not find non-existent resume in {format_type} format")
                self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
                
                # For JSON responses, verify the error message
                if 'application/json' in response.headers.get('Content-Type', ''):
                    response_data = response.json()
                    self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
                    self.assertIn('message', response_data, "Response should contain error message")
                    logger.info(f"Error message for {format_type}: {response_data.get('message')}")
    
    def test_malformed_job_description(self):
        """Test optimizing with a malformed job description"""
        logger.info("Testing optimization with malformed job description")
        
        # First upload a valid resume to get a resume ID
        with open(self.valid_resume_path, 'rb') as f:
            files = {'file': (self.valid_resume_path.name, f)}
            upload_response = requests.post(UPLOAD_ENDPOINT, files=files)
        
        # Skip if upload fails (already tested in another test)
        if upload_response.status_code != 200:
            self.skipTest("Resume upload failed, skipping malformed job description test")
        
        upload_data = upload_response.json()
        resume_id = upload_data.get('resume_id')
        self.assertIsNotNone(resume_id, "Failed to get resume ID from upload response")
        
        # Now test optimization with malformed job description
        start_time = time.time()
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={
                "resume_id": resume_id,
                "job_description": self.malformed_job_desc
            }
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should not accept malformed job description")
        self.assertTrue(400 <= response.status_code < 500, f"Expected client error code, got {response.status_code}")
        
        # Verify the response contains an error message
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        logger.info(f"Error message: {response_data.get('message')}")
    
    def test_validation_reporting(self):
        """Test that error responses contain validation information"""
        logger.info("Testing validation reporting in error responses")
        
        # Create a request with multiple errors
        start_time = time.time()
        response = requests.post(
            OPTIMIZE_ENDPOINT,
            json={
                # Missing resume_id
                "job_description": {
                    # Invalid job description format
                    "invalid_field": "value",
                    "another_invalid": 123
                },
                "invalid_param": "should not be here"
            }
        )
        
        execution_time = time.time() - start_time
        logger.info(f"Response received in {execution_time:.2f}s with status code {response.status_code}")
        
        # Verify the response indicates an error
        self.assertNotEqual(response.status_code, 200, "Should reject invalid request")
        
        # Verify the response contains validation details
        response_data = response.json()
        self.assertEqual(response_data.get('status'), 'error', "Response should indicate error status")
        self.assertIn('message', response_data, "Response should contain error message")
        
        # Check for detailed validation information
        # This could be in various formats depending on the implementation
        detailed_validation = False
        for field in ['errors', 'validation_errors', 'details', 'validation']:
            if field in response_data:
                detailed_validation = True
                logger.info(f"Validation details found in field '{field}': {response_data[field]}")
                break
        
        # Some implementations might include validation details in the main message
        if not detailed_validation and len(response_data.get('message', '')) > 30:
            logger.info(f"Potentially detailed error message: {response_data['message']}")

if __name__ == '__main__':
    # Run the tests
    test_runner = unittest.TextTestRunner(verbosity=2)
    test_suite = unittest.TestLoader().loadTestsFromTestCase(ErrorHandlingTestCase)
    test_results = test_runner.run(test_suite)
    
    # Return non-zero exit code if tests failed
    sys.exit(0 if test_results.wasSuccessful() else 1) 