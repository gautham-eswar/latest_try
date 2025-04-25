#!/usr/bin/env python3
"""
Validation Strategy Module

This module provides a set of validation strategies for the resume optimization system.
Each strategy implements a specific validation pattern that can be used to validate
various aspects of the system, from input files to configuration to output results.
"""

import os
import re
import json
import logging
import datetime
from typing import Dict, List, Any, Optional, Union, Tuple, Callable

# Configure logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ValidationStrategy:
    """Base class for all validation strategies."""
    
    def __init__(self, name: str, is_critical: bool = True):
        """
        Initialize the validation strategy.
        
        Args:
            name: The name of the validation strategy.
            is_critical: Whether this validation is critical for the system to function.
        """
        self.name = name
        self.is_critical = is_critical
        self.errors = []
        self.warnings = []
        
    def validate(self, *args, **kwargs) -> bool:
        """
        Execute the validation strategy.
        
        Returns:
            bool: True if validation passes, False otherwise.
        """
        raise NotImplementedError("Subclasses must implement validate()")
    
    def add_error(self, message: str):
        """Add an error message."""
        self.errors.append(message)
        logger.error(f"{self.name}: {message}")
        
    def add_warning(self, message: str):
        """Add a warning message."""
        self.warnings.append(message)
        logger.warning(f"{self.name}: {message}")
        
    def get_report(self) -> Dict:
        """Get a report of the validation results."""
        return {
            "name": self.name,
            "is_critical": self.is_critical,
            "passed": len(self.errors) == 0,
            "errors": self.errors,
            "warnings": self.warnings,
            "timestamp": datetime.datetime.now().isoformat()
        }


class FileExistenceValidator(ValidationStrategy):
    """Validates that required files exist."""
    
    def __init__(self, files: List[str], is_critical: bool = True):
        """
        Initialize the file existence validator.
        
        Args:
            files: List of file paths to validate.
            is_critical: Whether this validation is critical.
        """
        super().__init__("File Existence Validator", is_critical)
        self.files = files
        
    def validate(self, *args, **kwargs) -> bool:
        """
        Validate that all required files exist.
        
        Returns:
            bool: True if all files exist, False otherwise.
        """
        all_exist = True
        
        for file_path in self.files:
            if not os.path.exists(file_path):
                self.add_error(f"Required file does not exist: {file_path}")
                all_exist = False
                
        return all_exist


class FileFormatValidator(ValidationStrategy):
    """Validates that files are in the correct format."""
    
    def __init__(self, file_rules: Dict[str, List[str]], is_critical: bool = True):
        """
        Initialize the file format validator.
        
        Args:
            file_rules: Dictionary mapping file paths to lists of allowed extensions.
            is_critical: Whether this validation is critical.
        """
        super().__init__("File Format Validator", is_critical)
        self.file_rules = file_rules
        
    def validate(self, *args, **kwargs) -> bool:
        """
        Validate that files have the correct format/extension.
        
        Returns:
            bool: True if all files have correct format, False otherwise.
        """
        all_valid = True
        
        for file_path, allowed_extensions in self.file_rules.items():
            if not os.path.exists(file_path):
                self.add_warning(f"File does not exist: {file_path}")
                continue
                
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in allowed_extensions:
                self.add_error(
                    f"File has invalid extension: {file_path}. "
                    f"Expected one of: {', '.join(allowed_extensions)}"
                )
                all_valid = False
                
        return all_valid


class JsonSchemaValidator(ValidationStrategy):
    """Validates JSON data against a schema."""
    
    def __init__(self, schema: Dict, is_critical: bool = True):
        """
        Initialize the JSON schema validator.
        
        Args:
            schema: The JSON schema to validate against.
            is_critical: Whether this validation is critical.
        """
        super().__init__("JSON Schema Validator", is_critical)
        self.schema = schema
        
    def validate(self, data: Dict, *args, **kwargs) -> bool:
        """
        Validate JSON data against the schema.
        
        Args:
            data: The JSON data to validate.
            
        Returns:
            bool: True if data is valid against schema, False otherwise.
        """
        try:
            # Simple schema validation implementation
            # In production, you would use a library like jsonschema
            if "type" in self.schema and self.schema["type"] == "object":
                if not isinstance(data, dict):
                    self.add_error(f"Expected object, got {type(data).__name__}")
                    return False
                
                if "required" in self.schema:
                    for field in self.schema["required"]:
                        if field not in data:
                            self.add_error(f"Missing required field: {field}")
                            return False
                
                if "properties" in self.schema:
                    for field, field_schema in self.schema["properties"].items():
                        if field in data:
                            field_type = field_schema.get("type")
                            if field_type == "string" and not isinstance(data[field], str):
                                self.add_error(f"Field {field} should be a string")
                                return False
                            elif field_type == "number" and not isinstance(data[field], (int, float)):
                                self.add_error(f"Field {field} should be a number")
                                return False
                            elif field_type == "array" and not isinstance(data[field], list):
                                self.add_error(f"Field {field} should be an array")
                                return False
            
            return True
        except Exception as e:
            self.add_error(f"Schema validation error: {str(e)}")
            return False


class ResumeValidator(ValidationStrategy):
    """Validates resume data structure."""
    
    def __init__(self, is_critical: bool = True):
        """
        Initialize the resume validator.
        
        Args:
            is_critical: Whether this validation is critical.
        """
        super().__init__("Resume Validator", is_critical)
        
    def validate(self, resume_data: Dict, *args, **kwargs) -> bool:
        """
        Validate resume data structure.
        
        Args:
            resume_data: The resume data to validate.
            
        Returns:
            bool: True if resume data is valid, False otherwise.
        """
        if not isinstance(resume_data, dict):
            self.add_error("Resume data must be a dictionary")
            return False
            
        # Required sections
        required_sections = ["personal_info", "education", "experience", "skills"]
        for section in required_sections:
            if section not in resume_data:
                self.add_error(f"Missing required resume section: {section}")
                return False
                
        # Validate personal info
        personal_info = resume_data.get("personal_info", {})
        if not personal_info.get("name"):
            self.add_error("Resume must include a name in personal_info")
            return False
            
        # Validate contact information
        if not (personal_info.get("email") or personal_info.get("phone")):
            self.add_warning("Resume should include either email or phone in personal_info")
            
        # Validate experience
        experience = resume_data.get("experience", [])
        if not isinstance(experience, list):
            self.add_error("Experience section must be a list")
            return False
            
        for i, job in enumerate(experience):
            if not isinstance(job, dict):
                self.add_error(f"Experience item {i} must be a dictionary")
                return False
                
            if not job.get("title"):
                self.add_error(f"Experience item {i} missing job title")
                return False
                
            if not job.get("company"):
                self.add_error(f"Experience item {i} missing company")
                return False
                
        # Validate skills
        skills = resume_data.get("skills", [])
        if not isinstance(skills, list) and not isinstance(skills, dict):
            self.add_error("Skills section must be a list or dictionary")
            return False
            
        if isinstance(skills, list) and len(skills) == 0:
            self.add_warning("Resume should include at least one skill")
            
        return True


class JobDescriptionValidator(ValidationStrategy):
    """Validates job description data structure."""
    
    def __init__(self, is_critical: bool = True):
        """
        Initialize the job description validator.
        
        Args:
            is_critical: Whether this validation is critical.
        """
        super().__init__("Job Description Validator", is_critical)
        
    def validate(self, job_data: Dict, *args, **kwargs) -> bool:
        """
        Validate job description data structure.
        
        Args:
            job_data: The job description data to validate.
            
        Returns:
            bool: True if job description data is valid, False otherwise.
        """
        if not isinstance(job_data, dict):
            self.add_error("Job description data must be a dictionary")
            return False
            
        # Required sections
        required_sections = ["title", "description"]
        for section in required_sections:
            if section not in job_data:
                self.add_error(f"Missing required job description section: {section}")
                return False
                
        # Validate description content
        if not job_data.get("description") or len(job_data.get("description", "")) < 50:
            self.add_warning("Job description is too short for optimal matching")
            
        # Validate requirements if present
        requirements = job_data.get("requirements", [])
        if requirements and not isinstance(requirements, list):
            self.add_error("Requirements section must be a list")
            return False
            
        # Additional validations could check keyword quality, job title formatting, etc.
            
        return True


class ValidationChain:
    """Chain of validation strategies to execute in sequence."""
    
    def __init__(self, name: str):
        """
        Initialize the validation chain.
        
        Args:
            name: The name of the validation chain.
        """
        self.name = name
        self.validators = []
        self.results = []
        
    def add_validator(self, validator: ValidationStrategy):
        """
        Add a validator to the chain.
        
        Args:
            validator: The validator to add.
        """
        self.validators.append(validator)
        
    def validate(self, *args, **kwargs) -> bool:
        """
        Execute all validators in the chain.
        
        Returns:
            bool: True if all validations pass, False otherwise.
        """
        all_valid = True
        self.results = []
        
        for validator in self.validators:
            result = validator.validate(*args, **kwargs)
            self.results.append(validator.get_report())
            
            if not result and validator.is_critical:
                all_valid = False
                if kwargs.get("fail_fast", False):
                    break
                
        return all_valid
        
    def get_report(self) -> Dict:
        """Get a report of all validation results."""
        return {
            "name": self.name,
            "passed": all(result["passed"] for result in self.results),
            "results": self.results,
            "timestamp": datetime.datetime.now().isoformat()
        }


class ValidationFactory:
    """Factory for creating validation strategies."""
    
    @staticmethod
    def create_resume_validation_chain() -> ValidationChain:
        """
        Create a validation chain for resume data.
        
        Returns:
            ValidationChain: A validation chain for resume data.
        """
        chain = ValidationChain("Resume Validation Chain")
        
        # Add validators to the chain
        chain.add_validator(ResumeValidator())
        
        # Additional validators could be added here
        
        return chain
        
    @staticmethod
    def create_job_description_validation_chain() -> ValidationChain:
        """
        Create a validation chain for job description data.
        
        Returns:
            ValidationChain: A validation chain for job description data.
        """
        chain = ValidationChain("Job Description Validation Chain")
        
        # Add validators to the chain
        chain.add_validator(JobDescriptionValidator())
        
        # Additional validators could be added here
        
        return chain
        
    @staticmethod
    def create_file_validation_chain(file_path: str, allowed_extensions: List[str]) -> ValidationChain:
        """
        Create a validation chain for file validation.
        
        Args:
            file_path: The path to the file to validate.
            allowed_extensions: List of allowed file extensions.
            
        Returns:
            ValidationChain: A validation chain for file validation.
        """
        chain = ValidationChain(f"File Validation Chain: {os.path.basename(file_path)}")
        
        # Add validators to the chain
        chain.add_validator(FileExistenceValidator([file_path]))
        chain.add_validator(FileFormatValidator({file_path: allowed_extensions}))
        
        return chain


# Example usage:
if __name__ == "__main__":
    # Create a file validation chain
    file_chain = ValidationFactory.create_file_validation_chain(
        "example.pdf", [".pdf", ".docx", ".txt"]
    )
    
    # Execute the validation chain
    is_valid = file_chain.validate()
    
    # Get the validation report
    report = file_chain.get_report()
    print(json.dumps(report, indent=2))
    
    # Create and validate a resume
    resume_chain = ValidationFactory.create_resume_validation_chain()
    sample_resume = {
        "personal_info": {
            "name": "John Doe",
            "email": "john@example.com"
        },
        "education": [
            {
                "degree": "Bachelor of Science",
                "field": "Computer Science",
                "institution": "Example University",
                "year": 2020
            }
        ],
        "experience": [
            {
                "title": "Software Developer",
                "company": "Tech Corp",
                "start_date": "2020-01",
                "end_date": "2022-12",
                "description": "Developed web applications using modern frameworks."
            }
        ],
        "skills": [
            "Python", "JavaScript", "React", "Node.js"
        ]
    }
    
    is_valid = resume_chain.validate(sample_resume)
    report = resume_chain.get_report()
    print(json.dumps(report, indent=2)) 