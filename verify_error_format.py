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
            "message": "Error response format matches expected schema",
            "response": error_response
        }
        logger.info("Validation PASSED: Error format is valid")
        
    except json.JSONDecodeError as je:
        result = {
            "status": "failed",
            "message": f"Invalid JSON format: {str(je)}"
        }
        logger.error(f"Validation FAILED: Invalid JSON - {str(je)}")
        
    except jsonschema.exceptions.ValidationError as ve:
        result = {
            "status": "failed",
            "message": f"Schema validation error: {str(ve)}",
            "response": error_response
        }
        logger.error(f"Validation FAILED: Schema validation error - {str(ve)}")
        
    except Exception as e:
        result = {
            "status": "error",
            "error": str(e),
            "message": f"Exception occurred during validation: {str(e)}"
        }
        logger.error(f"Validation ERROR: {str(e)}")
    
    # Save result to file
    with open("validation_result.json", 'w') as f:
        json.dump(result, f, indent=2)
    logger.info("Results saved to validation_result.json")
    
    return result

if __name__ == "__main__":
    logger.info("Starting error format validation")
    result = validate_error_format("error_response.json")
    
    # Print summary
    print("\n=== Error Format Validation Summary ===")
    print(f"Status: {result['status'].upper()}")
    if 'message' in result:
        print(f"Message: {result['message']}")
    if 'error' in result:
        print(f"Error: {result['error']}")
    print("Results saved to: validation_result.json") 