#!/usr/bin/env python3
import json
import jsonschema
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("format-validator")

def validate_error_format(json_file_path):
    """Validate that the error response in the JSON file follows the expected format"""
    # Define expected error response schema
    error_schema = {
        "type": "object",
        "required": ["error", "message", "status_code", "transaction_id", "timestamp"],
        "properties": {
            "error": {"type": "string"},
            "message": {"type": "string"},
            "status_code": {"type": "number"},
            "transaction_id": {"type": "string", "pattern": "^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"},
            "timestamp": {"type": "string", "format": "date-time"}
        }
    }
    
    logger.info(f"Validating error format in file: {json_file_path}")
    
    try:
        # Read JSON file
        with open(json_file_path, 'r') as f:
            error_response = json.load(f)
        
        logger.info(f"JSON content: {json.dumps(error_response, indent=2)}")
        
        # Validate against schema
        jsonschema.validate(instance=error_response, schema=error_schema)
        
        result = {
            "status": "passed",
            "file": json_file_path,
            "message": "Error response format matches expected schema",
            "response": error_response
        }
        logger.info(f"Validation PASSED for {json_file_path}: Error format is valid")
        
    except json.JSONDecodeError as je:
        result = {
            "status": "failed",
            "file": json_file_path,
            "message": f"Invalid JSON format: {str(je)}"
        }
        logger.error(f"Validation FAILED for {json_file_path}: Invalid JSON - {str(je)}")
        
    except jsonschema.exceptions.ValidationError as ve:
        result = {
            "status": "failed",
            "file": json_file_path,
            "message": f"Schema validation error: {str(ve)}",
            "response": error_response
        }
        logger.error(f"Validation FAILED for {json_file_path}: Schema validation error - {str(ve)}")
        
    except Exception as e:
        result = {
            "status": "error",
            "file": json_file_path,
            "error": str(e),
            "message": f"Exception occurred during validation: {str(e)}"
        }
        logger.error(f"Validation ERROR for {json_file_path}: {str(e)}")
    
    return result

def main():
    """Run validation on both valid and invalid error formats"""
    logger.info("Starting error format validations")
    
    # Files to validate
    files = {
        "valid": "error_response.json",
        "invalid": "invalid_error_response.json"
    }
    
    # Run validations
    results = {}
    for test_type, file_path in files.items():
        logger.info(f"Testing {test_type} format with file {file_path}")
        results[test_type] = validate_error_format(file_path)
    
    # Save results to file
    with open("validation_results.json", 'w') as f:
        json.dump(results, f, indent=2)
    logger.info("Results saved to validation_results.json")
    
    # Print summary
    print("\n=== Error Format Validation Summary ===")
    for test_type, result in results.items():
        print(f"\nTest: {test_type.upper()}")
        print(f"Status: {result['status'].upper()}")
        if 'message' in result:
            print(f"Message: {result['message']}")
        if 'error' in result:
            print(f"Error: {result['error']}")
    
    print("\nAll results saved to: validation_results.json")

if __name__ == "__main__":
    main() 