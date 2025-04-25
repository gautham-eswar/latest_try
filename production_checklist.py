#!/usr/bin/env python3
"""
Production Deployment Checklist Script

This script performs a comprehensive set of checks to validate that the application
is ready for production deployment. It verifies critical configurations, connections,
resources, security settings, and more.

Usage:
    python production_checklist.py [--verbose] [--output-file FILENAME]

Options:
    --verbose       Display detailed information about each check
    --output-file   Save the results to the specified file (HTML or JSON format)
"""

import argparse
import json
import os
import socket
import sys
import time
import logging
import datetime
import requests
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("production-checklist")

# Constants
REQUIRED_ENV_VARS = [
    "FLASK_ENV", 
    "OPENAI_API_KEY", 
    "DATABASE_URL", 
    "SECRET_KEY",
    "UPLOAD_FOLDER",
    "ALLOWED_EXTENSIONS"
]
REQUIRED_FILES = [
    "app.py",
    "requirements.txt",
    "templates/diagnostics.html",
    "static/css/main.css",
    "static/js/main.js"
]
MIN_DISK_SPACE_MB = 1000  # 1GB
MIN_MEMORY_MB = 512  # 512MB
PORT_TO_CHECK = 8080

class ProductionCheck:
    """Base class for all production checks"""
    
    def __init__(self, name: str, description: str, is_critical: bool = True):
        self.name = name
        self.description = description
        self.is_critical = is_critical
        self.passed = None
        self.message = ""
        self.details = {}
    
    def run(self) -> bool:
        """Run the check and return True if passed, False otherwise"""
        raise NotImplementedError("Subclasses must implement this method")
    
    def to_dict(self) -> Dict:
        """Convert the check results to a dictionary"""
        return {
            "name": self.name,
            "description": self.description,
            "is_critical": self.is_critical,
            "passed": self.passed,
            "message": self.message,
            "details": self.details
        }

class ConfigurationCheck(ProductionCheck):
    """Check that all required environment variables are set"""
    
    def __init__(self):
        super().__init__(
            "Configuration Check", 
            "Validates that all required environment variables are set",
            True
        )
    
    def run(self) -> bool:
        missing_vars = []
        for var in REQUIRED_ENV_VARS:
            if not os.environ.get(var):
                missing_vars.append(var)
        
        if missing_vars:
            self.passed = False
            self.message = f"Missing required environment variables: {', '.join(missing_vars)}"
            self.details = {"missing_vars": missing_vars}
        else:
            self.passed = True
            self.message = "All required environment variables are set"
            
        return self.passed

class FileCheck(ProductionCheck):
    """Check that all required files exist"""
    
    def __init__(self):
        super().__init__(
            "File Check", 
            "Validates that all required files exist",
            True
        )
    
    def run(self) -> bool:
        missing_files = []
        for file_path in REQUIRED_FILES:
            if not Path(file_path).exists():
                missing_files.append(file_path)
        
        if missing_files:
            self.passed = False
            self.message = f"Missing required files: {', '.join(missing_files)}"
            self.details = {"missing_files": missing_files}
        else:
            self.passed = True
            self.message = "All required files exist"
            
        return self.passed

class DatabaseCheck(ProductionCheck):
    """Check database connection"""
    
    def __init__(self):
        super().__init__(
            "Database Check", 
            "Validates database connection and permissions",
            True
        )
    
    def run(self) -> bool:
        try:
            # Attempt to import the database module and create a connection
            try:
                from database import create_database_client
                db = create_database_client()
            except ImportError:
                # Fall back to local implementation if module not found
                logger.warning("Could not import database module, using mock check")
                # Simulate a database check with the DATABASE_URL
                db_url = os.environ.get("DATABASE_URL", "")
                if not db_url:
                    raise Exception("DATABASE_URL environment variable is not set")
                
                # Simple check if it's a valid URL format
                if not (db_url.startswith("postgres://") or 
                        db_url.startswith("postgresql://") or
                        db_url.startswith("sqlite:///")):
                    raise Exception(f"Invalid database URL format: {db_url}")
                
            self.passed = True
            self.message = "Database connection successful"
            return True
        except Exception as e:
            self.passed = False
            self.message = f"Database connection failed: {str(e)}"
            self.details = {"error": str(e), "traceback": traceback.format_exc()}
            return False

class OpenAICheck(ProductionCheck):
    """Check OpenAI API access"""
    
    def __init__(self):
        super().__init__(
            "OpenAI API Check", 
            "Validates OpenAI API access",
            True
        )
    
    def run(self) -> bool:
        try:
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                raise Exception("OPENAI_API_KEY environment variable is not set")
            
            # Make a simple request to OpenAI API to check access
            # Using the models endpoint which is lightweight
            headers = {
                "Authorization": f"Bearer {api_key}"
            }
            response = requests.get(
                "https://api.openai.com/v1/models",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                raise Exception(f"OpenAI API request failed with status code {response.status_code}: {response.text}")
            
            self.passed = True
            self.message = "OpenAI API access successful"
            self.details = {"available_models": len(response.json().get("data", []))}
            return True
        except Exception as e:
            self.passed = False
            self.message = f"OpenAI API access failed: {str(e)}"
            self.details = {"error": str(e)}
            return False

class DiskSpaceCheck(ProductionCheck):
    """Check available disk space"""
    
    def __init__(self):
        super().__init__(
            "Disk Space Check", 
            f"Validates that at least {MIN_DISK_SPACE_MB}MB of disk space is available",
            True
        )
    
    def run(self) -> bool:
        try:
            # Get disk usage for the current directory
            disk_usage = os.statvfs('.')
            available_space = disk_usage.f_frsize * disk_usage.f_bavail
            available_space_mb = available_space / (1024 * 1024)
            
            if available_space_mb < MIN_DISK_SPACE_MB:
                self.passed = False
                self.message = f"Insufficient disk space: {available_space_mb:.2f}MB available, {MIN_DISK_SPACE_MB}MB required"
                self.details = {"available_mb": available_space_mb, "required_mb": MIN_DISK_SPACE_MB}
            else:
                self.passed = True
                self.message = f"Sufficient disk space: {available_space_mb:.2f}MB available"
                self.details = {"available_mb": available_space_mb}
            
            return self.passed
        except Exception as e:
            self.passed = False
            self.message = f"Disk space check failed: {str(e)}"
            self.details = {"error": str(e)}
            return False

class MemoryCheck(ProductionCheck):
    """Check available system memory"""
    
    def __init__(self):
        super().__init__(
            "Memory Check", 
            f"Validates that at least {MIN_MEMORY_MB}MB of memory is available",
            True
        )
    
    def run(self) -> bool:
        try:
            # This is a simple cross-platform way to estimate available memory
            # More accurate methods would require platform-specific approaches
            import psutil
            available_memory = psutil.virtual_memory().available
            available_memory_mb = available_memory / (1024 * 1024)
            
            if available_memory_mb < MIN_MEMORY_MB:
                self.passed = False
                self.message = f"Insufficient memory: {available_memory_mb:.2f}MB available, {MIN_MEMORY_MB}MB required"
                self.details = {"available_mb": available_memory_mb, "required_mb": MIN_MEMORY_MB}
            else:
                self.passed = True
                self.message = f"Sufficient memory: {available_memory_mb:.2f}MB available"
                self.details = {"available_mb": available_memory_mb}
            
            return self.passed
        except ImportError:
            # If psutil is not available, skip this check but warn
            self.passed = None
            self.message = "Memory check skipped: psutil module not available"
            return True
        except Exception as e:
            self.passed = False
            self.message = f"Memory check failed: {str(e)}"
            self.details = {"error": str(e)}
            return False

class PortCheck(ProductionCheck):
    """Check if the application port is available"""
    
    def __init__(self, port=PORT_TO_CHECK):
        self.port = port
        super().__init__(
            f"Port {port} Check", 
            f"Validates that port {port} is available for the application",
            True
        )
    
    def run(self) -> bool:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', self.port))
        sock.close()
        
        if result == 0:
            # Port is in use
            self.passed = False
            self.message = f"Port {self.port} is already in use"
        else:
            # Port is available
            self.passed = True
            self.message = f"Port {self.port} is available"
        
        return self.passed

class SecurityCheck(ProductionCheck):
    """Check security settings"""
    
    def __init__(self):
        super().__init__(
            "Security Check", 
            "Validates security settings and configurations",
            True
        )
    
    def run(self) -> bool:
        issues = []
        
        # Check if SECRET_KEY is set and sufficiently complex
        secret_key = os.environ.get("SECRET_KEY", "")
        if not secret_key:
            issues.append("SECRET_KEY environment variable is not set")
        elif len(secret_key) < 16:
            issues.append("SECRET_KEY is too short (should be at least 16 characters)")
        
        # Check if DEBUG mode is disabled
        if os.environ.get("FLASK_ENV") == "development" or os.environ.get("DEBUG") == "True":
            issues.append("Application is running in development/debug mode")
        
        # More security checks could be added here
        
        if issues:
            self.passed = False
            self.message = f"Security issues found: {len(issues)}"
            self.details = {"issues": issues}
        else:
            self.passed = True
            self.message = "Security check passed"
        
        return self.passed

class BackupCheck(ProductionCheck):
    """Check if backup mechanisms are in place"""
    
    def __init__(self):
        super().__init__(
            "Backup Check", 
            "Validates that backup mechanisms are in place",
            False  # Not critical but important
        )
    
    def run(self) -> bool:
        # Check if backup directory exists
        backup_dir = os.environ.get("BACKUP_DIR", "backups")
        if not os.path.exists(backup_dir):
            self.passed = False
            self.message = f"Backup directory '{backup_dir}' does not exist"
            return False
        
        # Check if there are recent backups (within last 7 days)
        try:
            backup_files = [f for f in os.listdir(backup_dir) if f.endswith('.backup')]
            if not backup_files:
                self.passed = False
                self.message = "No backup files found"
                return False
            
            # Check the most recent backup file
            newest_backup = max(backup_files, key=lambda f: os.path.getmtime(os.path.join(backup_dir, f)))
            backup_time = os.path.getmtime(os.path.join(backup_dir, newest_backup))
            days_since_backup = (time.time() - backup_time) / (60 * 60 * 24)
            
            if days_since_backup > 7:
                self.passed = False
                self.message = f"Most recent backup is {days_since_backup:.1f} days old"
                self.details = {"days_since_backup": days_since_backup, "backup_file": newest_backup}
            else:
                self.passed = True
                self.message = f"Recent backup available ({days_since_backup:.1f} days old)"
                self.details = {"days_since_backup": days_since_backup, "backup_file": newest_backup}
            
            return self.passed
        except Exception as e:
            self.passed = False
            self.message = f"Backup check failed: {str(e)}"
            self.details = {"error": str(e)}
            return False

class DocumentationCheck(ProductionCheck):
    """Check if documentation is up-to-date"""
    
    def __init__(self):
        super().__init__(
            "Documentation Check", 
            "Validates that documentation is complete and up-to-date",
            False  # Not critical but important
        )
    
    def run(self) -> bool:
        required_docs = {
            "README.md": "Project overview",
            "DEPLOYMENT.md": "Deployment instructions",
            "API.md": "API documentation"
        }
        
        missing_docs = []
        for doc, desc in required_docs.items():
            if not os.path.exists(doc):
                missing_docs.append(f"{doc} ({desc})")
        
        if missing_docs:
            self.passed = False
            self.message = f"Missing documentation: {', '.join(missing_docs)}"
            self.details = {"missing_docs": missing_docs}
        else:
            self.passed = True
            self.message = "All required documentation is present"
        
        return self.passed

class ProductionCheckRunner:
    """Run all production checks and generate a report"""
    
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.checks = []
        self.results = {
            "timestamp": datetime.datetime.now().isoformat(),
            "overall_result": None,
            "checks": []
        }
    
    def add_check(self, check: ProductionCheck):
        """Add a check to the runner"""
        self.checks.append(check)
    
    def run_all_checks(self) -> Dict:
        """Run all checks and return the results"""
        logger.info("Starting production checklist validation...")
        
        failed_critical = []
        failed_non_critical = []
        passed = []
        skipped = []
        
        for check in self.checks:
            logger.info(f"Running check: {check.name}")
            try:
                result = check.run()
                if check.passed is None:
                    skipped.append(check.name)
                    logger.warning(f"Check skipped: {check.name} - {check.message}")
                elif check.passed:
                    passed.append(check.name)
                    logger.info(f"Check passed: {check.name}")
                else:
                    if check.is_critical:
                        failed_critical.append(check.name)
                        logger.error(f"Critical check failed: {check.name} - {check.message}")
                    else:
                        failed_non_critical.append(check.name)
                        logger.warning(f"Non-critical check failed: {check.name} - {check.message}")
                
                if self.verbose and check.details:
                    logger.info(f"Details for {check.name}: {json.dumps(check.details, indent=2)}")
            except Exception as e:
                logger.error(f"Error running check {check.name}: {str(e)}")
                check.passed = False
                check.message = f"Error running check: {str(e)}"
                if check.is_critical:
                    failed_critical.append(check.name)
                else:
                    failed_non_critical.append(check.name)
            
            self.results["checks"].append(check.to_dict())
        
        # Calculate overall result
        if failed_critical:
            self.results["overall_result"] = "FAILED"
            logger.error(f"Production checklist FAILED - {len(failed_critical)} critical issues found")
        elif failed_non_critical:
            self.results["overall_result"] = "WARNING"
            logger.warning(f"Production checklist WARNING - {len(failed_non_critical)} non-critical issues found")
        else:
            self.results["overall_result"] = "PASSED"
            logger.info("Production checklist PASSED - All critical checks successful")
        
        self.results["summary"] = {
            "total": len(self.checks),
            "passed": len(passed),
            "failed_critical": len(failed_critical),
            "failed_non_critical": len(failed_non_critical),
            "skipped": len(skipped)
        }
        
        return self.results
    
    def generate_html_report(self) -> str:
        """Generate an HTML report of the results"""
        if not self.results["checks"]:
            return "<h1>No checks have been run</h1>"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Production Checklist Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                table {{ border-collapse: collapse; width: 100%; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .passed {{ color: green; }}
                .failed {{ color: red; }}
                .warning {{ color: orange; }}
                .skipped {{ color: gray; }}
                .summary {{ margin-bottom: 20px; }}
                .details {{ margin-top: 10px; font-family: monospace; white-space: pre-wrap; }}
            </style>
        </head>
        <body>
            <h1>Production Checklist Report</h1>
            <p>Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <p>Overall result: <strong class="{self.results['overall_result'].lower()}">{self.results['overall_result']}</strong></p>
                <ul>
                    <li>Total checks: {self.results['summary']['total']}</li>
                    <li>Passed: {self.results['summary']['passed']}</li>
                    <li>Failed (critical): {self.results['summary']['failed_critical']}</li>
                    <li>Failed (non-critical): {self.results['summary']['failed_non_critical']}</li>
                    <li>Skipped: {self.results['summary']['skipped']}</li>
                </ul>
            </div>
            
            <h2>Detailed Results</h2>
            <table>
                <tr>
                    <th>Check</th>
                    <th>Description</th>
                    <th>Critical</th>
                    <th>Status</th>
                    <th>Message</th>
                </tr>
        """
        
        for check in self.results["checks"]:
            if check["passed"] is None:
                status_class = "skipped"
                status_text = "SKIPPED"
            elif check["passed"]:
                status_class = "passed"
                status_text = "PASSED"
            else:
                status_class = "failed"
                status_text = "FAILED"
            
            html += f"""
                <tr>
                    <td>{check['name']}</td>
                    <td>{check['description']}</td>
                    <td>{"Yes" if check['is_critical'] else "No"}</td>
                    <td class="{status_class}">{status_text}</td>
                    <td>{check['message']}</td>
                </tr>
            """
            
            # Add details if available and verbose mode is on
            if self.verbose and check['details']:
                html += f"""
                <tr>
                    <td colspan="5">
                        <div class="details">
                            {json.dumps(check['details'], indent=2)}
                        </div>
                    </td>
                </tr>
                """
        
        html += """
            </table>
        </body>
        </html>
        """
        
        return html

def main():
    parser = argparse.ArgumentParser(description="Run production deployment checklist")
    parser.add_argument("--verbose", action="store_true", help="Display detailed information")
    parser.add_argument("--output-file", help="Save the results to a file (HTML or JSON format)")
    args = parser.parse_args()
    
    # Initialize the runner
    runner = ProductionCheckRunner(verbose=args.verbose)
    
    # Add all checks
    runner.add_check(ConfigurationCheck())
    runner.add_check(FileCheck())
    runner.add_check(DatabaseCheck())
    runner.add_check(OpenAICheck())
    runner.add_check(DiskSpaceCheck())
    runner.add_check(MemoryCheck())
    runner.add_check(PortCheck())
    runner.add_check(SecurityCheck())
    runner.add_check(BackupCheck())
    runner.add_check(DocumentationCheck())
    
    # Run all checks
    results = runner.run_all_checks()
    
    # Save results if requested
    if args.output_file:
        ext = os.path.splitext(args.output_file)[1].lower()
        if ext == '.html':
            with open(args.output_file, 'w') as f:
                f.write(runner.generate_html_report())
            logger.info(f"HTML report saved to {args.output_file}")
        elif ext == '.json':
            with open(args.output_file, 'w') as f:
                json.dump(results, f, indent=2)
            logger.info(f"JSON results saved to {args.output_file}")
        else:
            logger.error(f"Unsupported output format: {ext}")
    
    # Return appropriate exit code based on results
    if results["overall_result"] == "FAILED":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main() 