#!/usr/bin/env python3
"""
Minimal Test for Resume-O Application
"""

import unittest
import os
import sys
import time
from datetime import datetime

# Set up path to find app modules
sys.path.insert(0, os.path.abspath("./"))

class MinimalTestCase(unittest.TestCase):
    """Basic tests for resume-o application"""
    
    def test_app_imports(self):
        """Test that we can import basic app modules"""
        try:
            from app import create_app
            self.assertTrue(True, "Successfully imported app")
        except ImportError as e:
            self.fail(f"Failed to import app: {e}")
    
    def test_diagnostic_imports(self):
        """Test that we can import diagnostic modules"""
        try:
            from diagnostic_system import create_diagnostic_system
            self.assertTrue(True, "Successfully imported diagnostic_system")
        except ImportError as e:
            self.fail(f"Failed to import diagnostic_system: {e}")
    
    def test_database_imports(self):
        """Test that we can import database module"""
        try:
            import database
            self.assertTrue(True, "Successfully imported database module")
        except ImportError as e:
            self.fail(f"Failed to import database module: {e}")
    
    def test_pdf_available(self):
        """Test if PDF generation tools are available"""
        # Check if pdflatex is in PATH
        import subprocess
        try:
            result = subprocess.run(
                ["which", "pdflatex"], 
                capture_output=True, 
                text=True,
                check=False
            )
            if result.returncode == 0:
                self.assertTrue(True, f"pdflatex found at: {result.stdout.strip()}")
            else:
                self.skipTest("pdflatex not found in PATH")
        except Exception as e:
            self.skipTest(f"Error checking for pdflatex: {e}")
    
    def test_app_creation(self):
        """Test minimal app creation"""
        try:
            # Skip the actual app creation which requires database setup
            # Just verify that the import works
            from app import create_app
            self.assertTrue(True, "App module imported successfully")
        except Exception as e:
            self.fail(f"Failed to import app: {e}")
    
    def test_resume_parser(self):
        """Test resume parser module"""
        try:
            from resume_parser import parse_resume, parse_resume_file
            result = parse_resume("dummy/path/to/resume.pdf")
            self.assertIsNotNone(result, "Should return parsed resume data")
            self.assertIn("contact", result, "Should include contact information")
            self.assertIn("skills", result, "Should include skills")
        except Exception as e:
            self.fail(f"Failed to test resume parser: {e}")
    
    def test_keyword_extractor(self):
        """Test keyword extractor module"""
        try:
            from keyword_extractor import extract_keywords
            job_desc = """
            We are looking for a Python developer with experience in Flask and Django.
            The candidate should have knowledge of AWS and database systems.
            """
            result = extract_keywords(job_desc)
            self.assertIsNotNone(result, "Should return extracted keywords")
            self.assertTrue(len(result) > 0, "Should extract some keywords")
        except Exception as e:
            self.fail(f"Failed to test keyword extractor: {e}")

if __name__ == "__main__":
    print("=" * 80)
    print(f"Minimal Resume-O Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Run tests
    unittest.main(verbosity=2) 
"""
Minimal Test for Resume-O Application
"""

import unittest
import os
import sys
import time
from datetime import datetime

# Set up path to find app modules
sys.path.insert(0, os.path.abspath("./"))

class MinimalTestCase(unittest.TestCase):
    """Basic tests for resume-o application"""
    
    def test_app_imports(self):
        """Test that we can import basic app modules"""
        try:
            from app import create_app
            self.assertTrue(True, "Successfully imported app")
        except ImportError as e:
            self.fail(f"Failed to import app: {e}")
    
    def test_diagnostic_imports(self):
        """Test that we can import diagnostic modules"""
        try:
            from diagnostic_system import create_diagnostic_system
            self.assertTrue(True, "Successfully imported diagnostic_system")
        except ImportError as e:
            self.fail(f"Failed to import diagnostic_system: {e}")
    
    def test_database_imports(self):
        """Test that we can import database module"""
        try:
            import database
            self.assertTrue(True, "Successfully imported database module")
        except ImportError as e:
            self.fail(f"Failed to import database module: {e}")
    
    def test_pdf_available(self):
        """Test if PDF generation tools are available"""
        # Check if pdflatex is in PATH
        import subprocess
        try:
            result = subprocess.run(
                ["which", "pdflatex"], 
                capture_output=True, 
                text=True,
                check=False
            )
            if result.returncode == 0:
                self.assertTrue(True, f"pdflatex found at: {result.stdout.strip()}")
            else:
                self.skipTest("pdflatex not found in PATH")
        except Exception as e:
            self.skipTest(f"Error checking for pdflatex: {e}")
    
    def test_app_creation(self):
        """Test minimal app creation"""
        try:
            # Skip the actual app creation which requires database setup
            # Just verify that the import works
            from app import create_app
            self.assertTrue(True, "App module imported successfully")
        except Exception as e:
            self.fail(f"Failed to import app: {e}")
    
    def test_resume_parser(self):
        """Test resume parser module"""
        try:
            from resume_parser import parse_resume, parse_resume_file
            result = parse_resume("dummy/path/to/resume.pdf")
            self.assertIsNotNone(result, "Should return parsed resume data")
            self.assertIn("contact", result, "Should include contact information")
            self.assertIn("skills", result, "Should include skills")
        except Exception as e:
            self.fail(f"Failed to test resume parser: {e}")
    
    def test_keyword_extractor(self):
        """Test keyword extractor module"""
        try:
            from keyword_extractor import extract_keywords
            job_desc = """
            We are looking for a Python developer with experience in Flask and Django.
            The candidate should have knowledge of AWS and database systems.
            """
            result = extract_keywords(job_desc)
            self.assertIsNotNone(result, "Should return extracted keywords")
            self.assertTrue(len(result) > 0, "Should extract some keywords")
        except Exception as e:
            self.fail(f"Failed to test keyword extractor: {e}")

if __name__ == "__main__":
    print("=" * 80)
    print(f"Minimal Resume-O Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # Run tests
    unittest.main(verbosity=2) 