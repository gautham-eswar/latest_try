#!/usr/bin/env python3
import requests
import json
import time
import logging
from datetime import datetime
import jsonschema
import argparse
import sys
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("simple_error_test.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("error-tester")

# Constants
DEFAULT_API_URL = "http://localhost:5001"
ERROR_ENDPOINT = "/api/test/custom-error/{error_code}"

def create_session_with_retries(retries=3, backoff_factor=0.3):
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

def check_server_available(base_url):
    """Check if the server is available before running tests."""
    session = create_session_with_retries()
    try:
        response = session.get(f"{base_url}/api/health", timeout=5)
        if response.status_code == 200:
            logger.info(f"Server is available at {base_url}")
            return True
        else:
            logger.error(f"Server returned status code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        logger.error(f"Server is not available at {base_url}: {str(e)}")
        return False

def test_error_format(base_url=DEFAULT_API_URL):
    """Test that error responses follow the expected format"""
    # Define expected error response schema
    error_schema = {
        "type": "object",
        "required": ["error", "message", "status_code"],
        "properties": {
            "error": {"type": "string"},
            "message": {"type": "string"},
            "status_code": {"type": "number"}
        }
    }
    
    # Test with the custom error endpoint which returns a formatted error
    error_code = 400  # Use 400 Bad Request for testing
    endpoint = ERROR_ENDPOINT.format(error_code=error_code)
    url = f"{base_url}{endpoint}"
    
    logger.info(f"Testing error format at: {url}")
    
    # Create result structure
    result = {
        "timestamp": datetime.now().isoformat(),
        "base_url": base_url,
        "scenario": "error_format",
        "endpoint": endpoint
    }
    
    # Check if server is available
    if not check_server_available(base_url):
        result.update({
            "status": "error",
            "message": f"Server not available at {base_url}",
            "error": "ConnectionError"
        })
        save_results(result)
        return result
    
    session = create_session_with_retries()
    
    try:
        start_time = time.time()
        response = session.get(url, timeout=10)
        elapsed = time.time() - start_time
        
        result.update({
            "response_code": response.status_code,
            "response_time": elapsed
        })
        
        if response.status_code != error_code:
            result.update({
                "status": "failed",
                "message": f"Expected status code {error_code} but got {response.status_code}",
                "response_text": response.text[:200] + "..." if len(response.text) > 200 else response.text
            })
            logger.error(f"Test FAILED: {result['message']}")
        else:
            try:
                # Attempt to parse response as JSON
                error_response = response.json()
                result["response"] = error_response
                
                # Validate against schema
                try:
                    jsonschema.validate(instance=error_response, schema=error_schema)
                    result.update({
                        "status": "passed",
                        "message": "Error response format matches expected schema"
                    })
                    logger.info("Test PASSED: Error response format is valid")
                except jsonschema.exceptions.ValidationError as ve:
                    result.update({
                        "status": "failed",
                        "message": f"Error response format does not match schema: {str(ve)}"
                    })
                    logger.error(f"Test FAILED: {result['message']}")
            
            except json.JSONDecodeError:
                result.update({
                    "status": "failed",
                    "message": "Error response is not valid JSON",
                    "response_text": response.text[:200] + "..." if len(response.text) > 200 else response.text
                })
                logger.error(f"Test FAILED: {result['message']}")
                
    except requests.exceptions.RequestException as e:
        result.update({
            "status": "error",
            "error": str(e),
            "message": f"Exception occurred while testing error response format: {str(e)}"
        })
        logger.error(f"Test ERROR: {str(e)}")
    
    # Save result to file
    save_results(result)
    
    return result

def save_results(result, filename="simple_error_test_result.json"):
    """Save test results to JSON file."""
    try:
        with open(filename, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"Results saved to {filename}")
    except Exception as e:
        logger.error(f"Failed to save results to {filename}: {str(e)}")

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Test error response format")
    parser.add_argument("--url", default=DEFAULT_API_URL, 
                        help=f"Base URL of the API (default: {DEFAULT_API_URL})")
    return parser.parse_args()

def main():
    """Main entry point."""
    args = parse_args()
    logger.info(f"Starting simple error format test using API at {args.url}")
    result = test_error_format(args.url)
    
    # Print summary
    print("\n=== Error Format Test Summary ===")
    print(f"Status: {result['status'].upper()}")
    if 'message' in result:
        print(f"Message: {result['message']}")
    if 'error' in result:
        print(f"Error: {result['error']}")
    if result['status'] == 'passed':
        print("✓ Test passed successfully!")
        return 0
    else:
        print("✗ Test failed!")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 