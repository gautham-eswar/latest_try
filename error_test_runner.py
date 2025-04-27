#!/usr/bin/env python3
import argparse
import json
import os
import time
import requests
import logging
import datetime
import uuid
import jsonschema
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field, asdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("error_tests.log")
    ]
)
logger = logging.getLogger("ErrorTestRunner")

# Define error response schema
ERROR_RESPONSE_SCHEMA = {
    "type": "object",
    "required": ["error", "message", "status_code", "transaction_id", "timestamp"],
    "properties": {
        "error": {"type": "string"},
        "message": {"type": "string"},
        "status_code": {"type": "integer"},
        "transaction_id": {"type": "string"},
        "timestamp": {"type": "string", "format": "date-time"}
    },
    "additionalProperties": False
}

@dataclass
class TestResult:
    """Represents the result of a single test."""
    scenario: str
    success: bool
    expected_code: int
    actual_code: Optional[int] = None
    response_time: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None

@dataclass
class TestSummary:
    """Summarizes the results of all tests."""
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    base_url: str = ""
    scenarios: List[TestResult] = field(default_factory=list)
    
    @property
    def total_tests(self) -> int:
        return len(self.scenarios)
    
    @property
    def passed_tests(self) -> int:
        return sum(1 for result in self.scenarios if result.success)
    
    @property
    def failed_tests(self) -> int:
        return self.total_tests - self.passed_tests
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "base_url": self.base_url,
            "scenarios": [asdict(scenario) for scenario in self.scenarios],
            "summary": {
                "total_tests": self.total_tests,
                "passed": self.passed_tests,
                "failed": self.failed_tests
            }
        }

class ErrorTestRunner:
    """Runs tests to verify API error handling behavior."""
    
    def __init__(self, base_url: str = "http://localhost:8080", timeout: int = 10):
        self.base_url = base_url
        self.timeout = timeout
        self.summary = TestSummary(base_url=base_url)
        logger.info(f"Initialized ErrorTestRunner with base URL: {self.base_url}")
    
    def run_all_tests(self) -> TestSummary:
        """Run all defined test scenarios."""
        # Test various error scenarios
        self.test_invalid_endpoint()
        self.test_invalid_method()
        self.test_custom_error_codes()
        self.test_error_format()
        self.test_missing_required_fields()
        self.test_file_upload_errors()
        
        # Save and report results
        self.save_results()
        self.report_results()
        
        return self.summary
    
    def report_results(self) -> None:
        """Print a summary of the test results to the console."""
        passed = self.summary.passed_tests
        total = self.summary.total_tests
        
        logger.info(f"=== Error Test Results ===")
        logger.info(f"Passed: {passed}/{total} ({passed/total*100:.1f}%)")
        
        if self.summary.failed_tests > 0:
            logger.warning("Failed scenarios:")
            for result in self.summary.scenarios:
                if not result.success:
                    logger.warning(f"  - {result.scenario}: Expected {result.expected_code}, got {result.actual_code}")
                    if result.error:
                        logger.warning(f"    Error: {result.error}")
    
    def save_results(self, filename: str = "error_simulation_results.json") -> None:
        """Save test results to a JSON file."""
        with open(filename, 'w') as f:
            json.dump(self.summary.to_dict(), f, indent=2)
        logger.info(f"Results saved to {filename}")
    
    def make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                    files: Optional[Dict] = None, headers: Optional[Dict] = None) -> Tuple[Optional[requests.Response], float, Optional[str]]:
        """
        Make an HTTP request and return the response along with timing information.
        """
        url = f"{self.base_url}{endpoint}"
        standard_headers = {"Content-Type": "application/json"}
        if headers:
            standard_headers.update(headers)
        
        error = None
        response = None
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=standard_headers, timeout=self.timeout)
            elif method.upper() == "POST":
                if files:
                    # Don't set Content-Type for multipart/form-data (files)
                    response = requests.post(url, data=data, files=files, timeout=self.timeout)
                else:
                    response = requests.post(url, json=data, headers=standard_headers, timeout=self.timeout)
            elif method.upper() == "PUT":
                response = requests.put(url, json=data, headers=standard_headers, timeout=self.timeout)
            elif method.upper() == "DELETE":
                response = requests.delete(url, headers=standard_headers, timeout=self.timeout)
            else:
                error = f"Unsupported HTTP method: {method}"
        except requests.RequestException as e:
            error = f"Request failed: {str(e)}"
        
        elapsed_time = time.time() - start_time
        return response, elapsed_time, error
    
    def test_invalid_endpoint(self) -> None:
        """Test that invalid endpoints return a 404 error."""
        endpoint = f"/api/nonexistent-endpoint-{uuid.uuid4()}"
        response, elapsed_time, error = self.make_request("GET", endpoint)
        
        result = TestResult(
            scenario="invalid_endpoint",
            expected_code=404,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            result.success = response.status_code == 404
            try:
                result.details = response.json()
            except ValueError:
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Invalid endpoint test: {'PASS' if result.success else 'FAIL'}")
    
    def test_invalid_method(self) -> None:
        """Test that using an invalid HTTP method returns a 405 error."""
        endpoint = "/api/health"  # This should only accept GET
        response, elapsed_time, error = self.make_request("POST", endpoint)
        
        result = TestResult(
            scenario="invalid_method",
            expected_code=405,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            result.success = response.status_code == 405
            try:
                result.details = response.json()
            except ValueError:
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Invalid method test: {'PASS' if result.success else 'FAIL'}")
    
    def test_custom_error_codes(self) -> None:
        """Test various custom error codes via the test endpoint."""
        error_codes = [400, 401, 403, 404, 408, 429, 500, 502, 503]
        
        for code in error_codes:
            endpoint = f"/api/test/custom-error/{code}"
            response, elapsed_time, error = self.make_request("GET", endpoint)
            
            result = TestResult(
                scenario=f"custom_error_{code}",
                expected_code=code,
                success=False,
                response_time=elapsed_time
            )
            
            if error:
                result.error = error
            elif response:
                result.actual_code = response.status_code
                result.success = response.status_code == code
                try:
                    result.details = response.json()
                except ValueError:
                    result.details = {"raw_response": response.text[:1000]}
            
            self.summary.scenarios.append(result)
            logger.info(f"Custom error {code} test: {'PASS' if result.success else 'FAIL'}")
    
    def test_error_format(self) -> None:
        """Test that error responses conform to the defined schema."""
        # Test schema conformance on a 404 error
        endpoint = f"/api/nonexistent-endpoint-{uuid.uuid4()}"
        response, elapsed_time, error = self.make_request("GET", endpoint)
        
        result = TestResult(
            scenario="error_format",
            expected_code=404,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            
            try:
                response_json = response.json()
                result.details = {"response": response_json}
                
                # Validate against schema
                try:
                    jsonschema.validate(instance=response_json, schema=ERROR_RESPONSE_SCHEMA)
                    
                    # Additional checks
                    timestamp_valid = self._validate_timestamp(response_json.get("timestamp", ""))
                    transaction_id_valid = self._validate_uuid(response_json.get("transaction_id", ""))
                    
                    if timestamp_valid and transaction_id_valid:
                        result.success = True
                    else:
                        result.error = f"Schema validation issues: "
                        if not timestamp_valid:
                            result.error += "Invalid timestamp format. "
                        if not transaction_id_valid:
                            result.error += "Invalid transaction_id format."
                
                except jsonschema.exceptions.ValidationError as e:
                    result.error = f"Schema validation error: {str(e)}"
            
            except ValueError:
                result.error = "Response is not valid JSON"
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Error format test: {'PASS' if result.success else 'FAIL'}")
    
    def _validate_timestamp(self, timestamp: str) -> bool:
        """Validate that a timestamp string is in ISO format."""
        try:
            datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            return True
        except (ValueError, TypeError):
            return False
    
    def _validate_uuid(self, uuid_str: str) -> bool:
        """Validate that a string is a valid UUID."""
        try:
            uuid.UUID(uuid_str)
            return True
        except (ValueError, TypeError, AttributeError):
            return False
    
    def test_missing_required_fields(self) -> None:
        """Test that omitting required fields results in appropriate error responses."""
        endpoint = "/api/optimize"
        
        # Test with empty body
        response, elapsed_time, error = self.make_request("POST", endpoint, data={})
        
        result = TestResult(
            scenario="missing_required_fields",
            expected_code=400,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            result.success = response.status_code == 400
            try:
                result.details = response.json()
            except ValueError:
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Missing required fields test: {'PASS' if result.success else 'FAIL'}")
    
    def test_file_upload_errors(self) -> None:
        """Test error handling for file uploads with different error scenarios."""
        endpoint = "/api/upload"
        
        # Test 1: Empty file
        empty_file = {"resume": ("empty.pdf", b"", "application/pdf")}
        response, elapsed_time, error = self.make_request("POST", endpoint, files=empty_file)
        
        result = TestResult(
            scenario="empty_file_upload",
            expected_code=400,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            result.success = response.status_code == 400
            try:
                result.details = response.json()
            except ValueError:
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Empty file upload test: {'PASS' if result.success else 'FAIL'}")
        
        # Test 2: Wrong file type
        text_file = {"resume": ("wrong.txt", b"This is not a PDF", "text/plain")}
        response, elapsed_time, error = self.make_request("POST", endpoint, files=text_file)
        
        result = TestResult(
            scenario="wrong_file_type",
            expected_code=400,
            success=False,
            response_time=elapsed_time
        )
        
        if error:
            result.error = error
        elif response:
            result.actual_code = response.status_code
            result.success = response.status_code == 400
            try:
                result.details = response.json()
            except ValueError:
                result.details = {"raw_response": response.text[:1000]}
        
        self.summary.scenarios.append(result)
        logger.info(f"Wrong file type test: {'PASS' if result.success else 'FAIL'}")

def main():
    parser = argparse.ArgumentParser(description="Run error handling tests for the Resume Optimizer API")
    parser.add_argument("--url", default="http://localhost:8080", help="Base URL of the API to test")
    parser.add_argument("--timeout", type=int, default=10, help="Request timeout in seconds")
    parser.add_argument("--output", default="error_simulation_results.json", help="Output file for test results")
    parser.add_argument("--scenario", help="Run only a specific test scenario")
    
    args = parser.parse_args()
    
    runner = ErrorTestRunner(base_url=args.url, timeout=args.timeout)
    
    if args.scenario:
        # Run only the specified scenario
        method_name = f"test_{args.scenario}"
        if hasattr(runner, method_name) and callable(getattr(runner, method_name)):
            getattr(runner, method_name)()
            runner.save_results(args.output)
            runner.report_results()
        else:
            logger.error(f"Unknown scenario: {args.scenario}")
            logger.info("Available scenarios:")
            for attr in dir(runner):
                if attr.startswith("test_") and callable(getattr(runner, attr)):
                    logger.info(f"  - {attr[5:]}")
    else:
        # Run all tests
        runner.run_all_tests()
    
    # Return appropriate exit code based on test results
    return 0 if runner.summary.failed_tests == 0 else 1

if __name__ == "__main__":
    exit(main()) 