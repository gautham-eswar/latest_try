#!/usr/bin/env python3
"""
Error Format Test Script for Resume Optimizer Application

This script tests that the error responses from the Resume Optimizer application
follow the expected format and contain all required fields.
"""
import argparse
import json
import logging
import sys
import time
from datetime import datetime

import jsonschema
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app_error_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("app-error-tester")

# Constants
DEFAULT_API_URL = "http://localhost:8080"
ENDPOINTS = {
    "health": "/api/health",
    "custom_error": "/api/test/custom-error/{error_code}",
    "invalid_endpoint": "/api/nonexistent-endpoint",
    "upload": "/api/upload",  # Expects POST but we'll use GET to test error handling
}

# Error response schema
ERROR_SCHEMA = {
    "type": "object",
    "required": ["error", "message", "status_code"],
    "properties": {
        "error": {"type": "string"},
        "message": {"type": "string"},
        "status_code": {"type": "number"},
        "transaction_id": {"type": "string"},
        "timestamp": {"type": "string"}
    }
}

class AppErrorTester:
    """Tests that application error responses conform to the expected format."""
    
    def __init__(self, base_url=DEFAULT_API_URL):
        """Initialize the tester with the given base URL."""
        self.base_url = base_url
        self.session = self._create_session_with_retries()
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "scenarios": {},
            "summary": {
                "total": 0,
                "passed": 0,
                "failed": 0,
                "errors": 0
            }
        }
        logger.info(f"Initialized AppErrorTester with base URL: {base_url}")
    
    def _create_session_with_retries(self, retries=2, backoff_factor=0.3):
        """Create a requests session with retry functionality."""
        session = requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=[500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def _check_server_available(self):
        """Check if the server is available before running tests."""
        try:
            response = self.session.get(f"{self.base_url}{ENDPOINTS['health']}", timeout=5)
            if response.status_code == 200:
                logger.info(f"Server is available at {self.base_url}")
                return True
            else:
                logger.error(f"Server returned status code {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            logger.error(f"Server is not available at {self.base_url}: {str(e)}")
            return False
    
    def test_custom_error(self, error_code=400):
        """Test that custom error responses follow the expected format."""
        scenario_name = f"custom_error_{error_code}"
        endpoint = ENDPOINTS["custom_error"].format(error_code=error_code)
        url = f"{self.base_url}{endpoint}"
        expected_code = error_code
        
        logger.info(f"Testing custom error {error_code} at: {url}")
        
        result = self._make_request("GET", url, expected_code)
        self._add_result(scenario_name, result)
        return result
    
    def test_invalid_endpoint(self):
        """Test that invalid endpoint responses follow the expected format."""
        scenario_name = "invalid_endpoint"
        endpoint = ENDPOINTS["invalid_endpoint"]
        url = f"{self.base_url}{endpoint}"
        expected_code = 404
        
        logger.info(f"Testing invalid endpoint at: {url}")
        
        result = self._make_request("GET", url, expected_code)
        self._add_result(scenario_name, result)
        return result
    
    def test_invalid_method(self):
        """Test that invalid method responses follow the expected format."""
        scenario_name = "invalid_method"
        endpoint = ENDPOINTS["upload"]  # This endpoint expects POST
        url = f"{self.base_url}{endpoint}"
        expected_code = 405  # Method Not Allowed
        
        logger.info(f"Testing invalid method (GET instead of POST) at: {url}")
        
        result = self._make_request("GET", url, expected_code)
        self._add_result(scenario_name, result)
        return result
    
    def _make_request(self, method, url, expected_code):
        """Make a request and validate the response format."""
        result = {
            "endpoint": url.replace(self.base_url, ""),
            "method": method,
            "expected_code": expected_code
        }
        
        try:
            start_time = time.time()
            response = self.session.request(method, url, timeout=10)
            elapsed = time.time() - start_time
            
            result["response_time"] = elapsed
            result["actual_code"] = response.status_code
            
            # Check if status code matches expected
            if response.status_code != expected_code:
                result["status"] = "failed"
                result["message"] = f"Expected status code {expected_code} but got {response.status_code}"
                if response.headers.get("Content-Type", "").startswith("application/json"):
                    try:
                        result["response"] = response.json()
                    except json.JSONDecodeError:
                        result["response_text"] = response.text[:200]
                else:
                    result["response_text"] = response.text[:200]
                return result
            
            # Try to parse response as JSON
            try:
                error_response = response.json()
                result["response"] = error_response
                
                # Validate against schema
                try:
                    jsonschema.validate(instance=error_response, schema=ERROR_SCHEMA)
                    result["status"] = "passed"
                    result["message"] = "Error response format matches expected schema"
                except jsonschema.exceptions.ValidationError as ve:
                    result["status"] = "failed"
                    result["message"] = f"Error response format does not match schema: {str(ve)}"
            except json.JSONDecodeError:
                result["status"] = "failed"
                result["message"] = "Error response is not valid JSON"
                result["response_text"] = response.text[:200]
        
        except requests.exceptions.RequestException as e:
            result["status"] = "error"
            result["error"] = str(e)
            result["message"] = f"Request exception: {str(e)}"
        
        return result
    
    def _add_result(self, scenario_name, result):
        """Add a test result to the results collection."""
        self.results["scenarios"][scenario_name] = result
        self.results["summary"]["total"] += 1
        
        if result["status"] == "passed":
            self.results["summary"]["passed"] += 1
        elif result["status"] == "failed":
            self.results["summary"]["failed"] += 1
        else:  # error
            self.results["summary"]["errors"] += 1
    
    def run_all_tests(self):
        """Run all error format tests."""
        if not self._check_server_available():
            logger.error("Server is not available. Aborting tests.")
            return False
        
        logger.info("Running all error format tests")
        
        # Test invalid endpoint (404)
        self.test_invalid_endpoint()
        
        # Test invalid method (405)
        self.test_invalid_method()
        
        # Test custom error codes
        for code in [400, 401, 403, 404, 500]:
            self.test_custom_error(code)
        
        # Save results
        self.save_results()
        
        # Log summary
        logger.info(f"Test summary: "
                   f"Total: {self.results['summary']['total']}, "
                   f"Passed: {self.results['summary']['passed']}, "
                   f"Failed: {self.results['summary']['failed']}, "
                   f"Errors: {self.results['summary']['errors']}")
        
        return self.results["summary"]["failed"] == 0 and self.results["summary"]["errors"] == 0
    
    def save_results(self, filename="app_error_test_results.json"):
        """Save test results to a JSON file."""
        try:
            with open(filename, 'w') as f:
                json.dump(self.results, f, indent=2)
            logger.info(f"Results saved to {filename}")
        except Exception as e:
            logger.error(f"Failed to save results: {str(e)}")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test application error response format")
    parser.add_argument("--url", default=DEFAULT_API_URL, 
                        help=f"Base URL of the API (default: {DEFAULT_API_URL})")
    parser.add_argument("--test", choices=["all", "invalid_endpoint", "invalid_method", "custom_error"],
                        default="all", help="Specific test to run (default: all)")
    parser.add_argument("--error-code", type=int, default=400,
                        help="Error code to test for custom error test (default: 400)")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    
    logger.info(f"Starting app error format test for {args.url}")
    tester = AppErrorTester(args.url)
    
    if args.test == "all":
        success = tester.run_all_tests()
    elif args.test == "invalid_endpoint":
        result = tester.test_invalid_endpoint()
        success = result["status"] == "passed"
        tester.save_results()
    elif args.test == "invalid_method":
        result = tester.test_invalid_method()
        success = result["status"] == "passed"
        tester.save_results()
    elif args.test == "custom_error":
        result = tester.test_custom_error(args.error_code)
        success = result["status"] == "passed"
        tester.save_results()
    
    # Print summary
    print("\n=== App Error Format Test Summary ===")
    print(f"Total tests: {tester.results['summary']['total']}")
    print(f"Passed: {tester.results['summary']['passed']}")
    print(f"Failed: {tester.results['summary']['failed']}")
    print(f"Errors: {tester.results['summary']['errors']}")
    
    if success:
        print("✓ All tests passed successfully!")
        return 0
    else:
        print("✗ Some tests failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 