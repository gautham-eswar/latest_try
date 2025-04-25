#!/usr/bin/env python
import os
import sys
import time
import json
import unittest
import logging
import requests
import subprocess
import tempfile
import shutil
from io import BytesIO
from typing import Dict, List, Any, Tuple, Optional
from pathlib import Path
from unittest.mock import patch, MagicMock

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('test_resume_processing')

# Constants for testing
BASE_URL = os.environ.get('TEST_API_URL', 'http://localhost:8080')
TEST_FILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_files')
RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'test_results')

# Create directories if they don't exist
os.makedirs(TEST_FILES_DIR, exist_ok=True)
os.makedirs(RESULTS_DIR, exist_ok=True)

class TestResumeProcessing(unittest.TestCase):
    """Test suite for resume processing functionality"""
    
    @classmethod
    def setUpClass(cls):
        """Setup test environment before all tests"""
        cls.server_process = None
        cls.generate_test_data()
        cls.start_server()
        
    @classmethod
    def tearDownClass(cls):
        """Clean up test environment after all tests"""
        cls.stop_server()
        
    @classmethod
    def generate_test_data(cls):
        """Generate sample test data for testing"""
        # Create minimal PDF resume
        cls.create_minimal_pdf()
        
        # Create minimal DOCX resume
        cls.create_minimal_docx()
        
        # Create sample job description
        cls.create_sample_job_description()
        
    @classmethod
    def create_minimal_pdf(cls):
        """Create a minimal PDF resume for testing"""
        try:
            from reportlab.pdfgen import canvas
            
            pdf_path = os.path.join(TEST_FILES_DIR, 'minimal_resume.pdf')
            c = canvas.Canvas(pdf_path)
            c.drawString(100, 750, "Sample Resume")
            c.drawString(100, 730, "John Doe")
            c.drawString(100, 710, "Software Engineer")
            c.drawString(100, 690, "Skills: Python, JavaScript, Machine Learning")
            c.drawString(100, 670, "Experience: 5 years at Tech Company")
            c.save()
            logger.info(f"Created minimal PDF resume at {pdf_path}")
            return pdf_path
        except ImportError:
            logger.warning("ReportLab not installed, skipping PDF generation")
            # Create a test file indicating PDF would be here
            with open(os.path.join(TEST_FILES_DIR, 'minimal_resume.txt'), 'w') as f:
                f.write("This is a placeholder for a PDF resume")
            return None
            
    @classmethod
    def create_minimal_docx(cls):
        """Create a minimal DOCX resume for testing"""
        try:
            from docx import Document
            
            docx_path = os.path.join(TEST_FILES_DIR, 'minimal_resume.docx')
            document = Document()
            document.add_heading('Sample Resume', 0)
            document.add_paragraph('John Doe')
            document.add_paragraph('Software Engineer')
            document.add_paragraph('Skills: Python, JavaScript, Machine Learning')
            document.add_paragraph('Experience: 5 years at Tech Company')
            document.save(docx_path)
            logger.info(f"Created minimal DOCX resume at {docx_path}")
            return docx_path
        except ImportError:
            logger.warning("python-docx not installed, skipping DOCX generation")
            # Create a test file indicating DOCX would be here
            with open(os.path.join(TEST_FILES_DIR, 'minimal_resume.txt'), 'w') as f:
                f.write("This is a placeholder for a DOCX resume")
            return None
            
    @classmethod
    def create_sample_job_description(cls):
        """Create a sample job description with relevant keywords"""
        job_desc_path = os.path.join(TEST_FILES_DIR, 'sample_job_description.txt')
        with open(job_desc_path, 'w') as f:
            f.write("""
            Senior Software Engineer
            
            Requirements:
            - 5+ years of experience in software development
            - Proficient in Python and JavaScript
            - Experience with machine learning and AI
            - Strong problem-solving skills
            - Experience with cloud platforms (AWS, GCP)
            
            Responsibilities:
            - Develop and maintain high-quality software
            - Work with cross-functional teams to design and implement features
            - Optimize code for performance and scalability
            - Mentor junior engineers
            """)
        logger.info(f"Created sample job description at {job_desc_path}")
        return job_desc_path
        
    @classmethod
    def start_server(cls):
        """Start the resume processing server for testing"""
        if os.environ.get('SKIP_SERVER_START', '0') == '1':
            logger.info("Skipping server start as requested by environment variable")
            return
            
        try:
            logger.info("Starting server...")
            # Start server with subprocess
            cls.server_process = subprocess.Popen(
                ["python", "app.py", "--port", "8080", "--test-mode"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            # Wait for server to start
            time.sleep(3)
            # Check if server is running
            try:
                response = requests.get(f"{BASE_URL}/api/health")
                if response.status_code == 200:
                    logger.info("Server started successfully")
                else:
                    logger.warning(f"Server health check returned status code {response.status_code}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Server health check failed: {e}")
        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            
    @classmethod
    def stop_server(cls):
        """Stop the resume processing server after testing"""
        if cls.server_process is not None:
            logger.info("Stopping server...")
            cls.server_process.terminate()
            cls.server_process.wait(timeout=5)
            logger.info("Server stopped")
            
    def setUp(self):
        """Set up test environment before each test"""
        self.start_time = time.time()
        self.test_results = {}
        
    def tearDown(self):
        """Clean up test environment after each test"""
        duration = time.time() - self.start_time
        test_name = self._testMethodName
        self.test_results[test_name] = {
            'duration': duration,
            'status': 'PASS' if not self._outcome.errors[-1][1] else 'FAIL'
        }
        logger.info(f"Test {test_name} completed in {duration:.2f} seconds with status {self.test_results[test_name]['status']}")
        
    def test_health_endpoint(self):
        """Test the health endpoint is working"""
        try:
            response = requests.get(f"{BASE_URL}/api/health")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('status', data)
            self.assertEqual(data['status'], 'ok')
        except requests.exceptions.RequestException as e:
            self.fail(f"Health endpoint check failed: {e}")
            
    def test_file_upload(self):
        """Test file upload functionality"""
        # Get resume file
        resume_path = os.path.join(TEST_FILES_DIR, 'minimal_resume.txt')
        if not os.path.exists(resume_path):
            resume_path = self._find_available_resume()
            
        if not resume_path:
            self.skipTest("No resume file available for testing")
            
        try:
            with open(resume_path, 'rb') as f:
                files = {'resume': (os.path.basename(resume_path), f, self._get_mime_type(resume_path))}
                response = requests.post(f"{BASE_URL}/api/upload", files=files)
                
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('resume_id', data)
            self.assertIsNotNone(data['resume_id'])
            return data['resume_id']
        except requests.exceptions.RequestException as e:
            self.fail(f"File upload failed: {e}")
            
    def test_resume_parser(self):
        """Test resume parser component"""
        resume_id = self.test_file_upload()
        
        try:
            response = requests.get(f"{BASE_URL}/api/parse/{resume_id}")
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('parsed_data', data)
            self.assertIsNotNone(data['parsed_data'])
            parsed_data = data['parsed_data']
            
            # Verify basic resume structure
            self.assertIn('contact_info', parsed_data)
            self.assertIn('skills', parsed_data)
            
            return resume_id, parsed_data
        except requests.exceptions.RequestException as e:
            self.fail(f"Resume parsing failed: {e}")
            
    def test_keyword_extraction(self):
        """Test keyword extraction component"""
        # Upload job description
        job_desc_path = os.path.join(TEST_FILES_DIR, 'sample_job_description.txt')
        
        try:
            with open(job_desc_path, 'rb') as f:
                files = {'job_description': (os.path.basename(job_desc_path), f, 'text/plain')}
                response = requests.post(f"{BASE_URL}/api/extract-keywords", files=files)
                
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('keywords', data)
            self.assertIsInstance(data['keywords'], list)
            self.assertGreater(len(data['keywords']), 0)
            
            return data['keywords']
        except requests.exceptions.RequestException as e:
            self.fail(f"Keyword extraction failed: {e}")
            
    def test_semantic_matching(self):
        """Test semantic matching component"""
        resume_id, _ = self.test_resume_parser()
        keywords = self.test_keyword_extraction()
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/match/{resume_id}",
                json={'keywords': keywords}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('matching_score', data)
            self.assertIsInstance(data['matching_score'], (int, float))
            self.assertGreaterEqual(data['matching_score'], 0)
            self.assertLessEqual(data['matching_score'], 1)
            
            return resume_id, data['matching_score']
        except requests.exceptions.RequestException as e:
            self.fail(f"Semantic matching failed: {e}")
            
    def test_resume_enhancement(self):
        """Test resume enhancement component"""
        resume_id, _ = self.test_semantic_matching()
        
        try:
            response = requests.post(
                f"{BASE_URL}/api/optimize/{resume_id}",
                json={'target_score': 0.9}
            )
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('optimized_resume_id', data)
            self.assertIsNotNone(data['optimized_resume_id'])
            
            return data['optimized_resume_id']
        except requests.exceptions.RequestException as e:
            self.fail(f"Resume enhancement failed: {e}")
            
    def test_pdf_generation(self):
        """Test PDF generation component"""
        optimized_resume_id = self.test_resume_enhancement()
        
        try:
            response = requests.get(f"{BASE_URL}/api/download/{optimized_resume_id}/pdf")
            
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Content-Type'], 'application/pdf')
            
            # Save the PDF to a file for manual inspection
            pdf_path = os.path.join(RESULTS_DIR, f"{optimized_resume_id}.pdf")
            with open(pdf_path, 'wb') as f:
                f.write(response.content)
                
            logger.info(f"Generated PDF saved to {pdf_path}")
            
            return pdf_path
        except requests.exceptions.RequestException as e:
            self.fail(f"PDF generation failed: {e}")
            
    def test_integrated_pipeline(self):
        """Test the entire resume processing pipeline"""
        # 1. Upload resume
        resume_path = self._find_available_resume()
        if not resume_path:
            self.skipTest("No resume file available for testing")
            
        try:
            # Upload resume
            with open(resume_path, 'rb') as f:
                files = {'resume': (os.path.basename(resume_path), f, self._get_mime_type(resume_path))}
                upload_response = requests.post(f"{BASE_URL}/api/upload", files=files)
                
            self.assertEqual(upload_response.status_code, 200)
            resume_id = upload_response.json()['resume_id']
            
            # Upload job description
            job_desc_path = os.path.join(TEST_FILES_DIR, 'sample_job_description.txt')
            with open(job_desc_path, 'rb') as f:
                files = {'job_description': (os.path.basename(job_desc_path), f, 'text/plain')}
                keywords_response = requests.post(f"{BASE_URL}/api/extract-keywords", files=files)
                
            self.assertEqual(keywords_response.status_code, 200)
            keywords = keywords_response.json()['keywords']
            
            # Match keywords with resume
            match_response = requests.post(
                f"{BASE_URL}/api/match/{resume_id}",
                json={'keywords': keywords}
            )
            
            self.assertEqual(match_response.status_code, 200)
            match_score = match_response.json()['matching_score']
            
            # Optimize resume
            optimize_response = requests.post(
                f"{BASE_URL}/api/optimize/{resume_id}",
                json={'target_score': 0.9, 'keywords': keywords}
            )
            
            self.assertEqual(optimize_response.status_code, 200)
            optimized_resume_id = optimize_response.json()['optimized_resume_id']
            
            # Download in different formats
            formats = ['pdf', 'docx', 'txt', 'json']
            for fmt in formats:
                download_response = requests.get(f"{BASE_URL}/api/download/{optimized_resume_id}/{fmt}")
                
                self.assertEqual(download_response.status_code, 200)
                
                # Save the file
                output_path = os.path.join(RESULTS_DIR, f"{optimized_resume_id}.{fmt}")
                with open(output_path, 'wb') as f:
                    f.write(download_response.content)
                    
                logger.info(f"Generated {fmt.upper()} saved to {output_path}")
                
            return {
                'resume_id': resume_id,
                'optimized_resume_id': optimized_resume_id,
                'match_score': match_score
            }
        except requests.exceptions.RequestException as e:
            self.fail(f"Integrated pipeline failed: {e}")
            
    def test_error_handling_invalid_file(self):
        """Test error handling for invalid file formats"""
        # Create a temporary invalid file
        with tempfile.NamedTemporaryFile(suffix='.xyz') as tmp:
            tmp.write(b"This is an invalid file format")
            tmp.flush()
            
            try:
                with open(tmp.name, 'rb') as f:
                    files = {'resume': (os.path.basename(tmp.name), f, 'application/octet-stream')}
                    response = requests.post(f"{BASE_URL}/api/upload", files=files)
                    
                self.assertNotEqual(response.status_code, 200)
                data = response.json()
                self.assertIn('error', data)
            except requests.exceptions.RequestException as e:
                self.fail(f"Request failed: {e}")
                
    def test_error_handling_missing_file(self):
        """Test error handling for missing files"""
        try:
            response = requests.post(f"{BASE_URL}/api/upload")
            self.assertNotEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('error', data)
        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")
            
    def test_error_handling_invalid_resume_id(self):
        """Test error handling for invalid resume ID"""
        invalid_id = "non_existent_id_12345"
        
        try:
            response = requests.get(f"{BASE_URL}/api/parse/{invalid_id}")
            self.assertNotEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('error', data)
        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")
            
    def test_error_handling_broken_component(self):
        """Test error handling for broken component simulation"""
        # Use a special endpoint that simulates a component failure
        try:
            response = requests.get(f"{BASE_URL}/api/test/simulate-failure")
            self.assertNotEqual(response.status_code, 200)
            data = response.json()
            self.assertIn('error', data)
        except requests.exceptions.RequestException as e:
            self.fail(f"Request failed: {e}")
            
    def _find_available_resume(self) -> Optional[str]:
        """Find an available resume file for testing"""
        file_types = ['.pdf', '.docx', '.txt']
        for ext in file_types:
            path = os.path.join(TEST_FILES_DIR, f'minimal_resume{ext}')
            if os.path.exists(path):
                return path
        return None
        
    def _get_mime_type(self, filepath: str) -> str:
        """Get MIME type for a file"""
        ext = os.path.splitext(filepath)[1].lower()
        if ext == '.pdf':
            return 'application/pdf'
        elif ext == '.docx':
            return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif ext == '.txt':
            return 'text/plain'
        else:
            return 'application/octet-stream'
            
    def export_test_results(self):
        """Export test results to a JSON file"""
        output_path = os.path.join(RESULTS_DIR, f"test_results_{int(time.time())}.json")
        with open(output_path, 'w') as f:
            json.dump(self.test_results, f, indent=4)
        logger.info(f"Test results exported to {output_path}")
        return output_path
        
def main():
    """Run the test suite and generate a report"""
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description='Test resume processing functionality')
    parser.add_argument('--skip-server', action='store_true', help='Skip starting the server')
    parser.add_argument('--generate-data-only', action='store_true', help='Only generate test data without running tests')
    parser.add_argument('--test-file', type=str, help='Run a specific test file')
    args = parser.parse_args()
    
    if args.skip_server:
        os.environ['SKIP_SERVER_START'] = '1'
        
    if args.generate_data_only:
        TestResumeProcessing.generate_test_data()
        logger.info("Test data generation completed")
        return
        
    # Run the tests
    suite = unittest.TestLoader().loadTestsFromTestCase(TestResumeProcessing)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # Export test results
    test_case = TestResumeProcessing()
    test_case.test_results = {
        'summary': {
            'tests': result.testsRun,
            'failures': len(result.failures),
            'errors': len(result.errors),
            'skipped': len(result.skipped),
            'success_rate': (result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun if result.testsRun > 0 else 0
        }
    }
    test_case.export_test_results()
    
if __name__ == '__main__':
    main() 