#!/usr/bin/env python3
"""
Render platform entrypoint script for Resume Optimizer application.
This handles command-line arguments and environment setup before starting the app.
"""

import os
import sys
import logging
import argparse
from dotenv import load_dotenv
import hashlib
import subprocess

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(name)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("render_entrypoint")

def _log_git_info():
    """Log current git branch and short commit hash if available."""
    branch = None
    sha_short = None
    try:
        branch = subprocess.check_output([
            "git", "rev-parse", "--abbrev-ref", "HEAD"
        ], stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        pass
    try:
        sha_short = subprocess.check_output([
            "git", "rev-parse", "--short", "HEAD"
        ], stderr=subprocess.STDOUT).decode().strip()
    except Exception:
        pass

    # Fallback to env if git metadata is unavailable in the container
    env_sha = os.getenv("RENDER_GIT_COMMIT") or os.getenv("GIT_COMMIT") or os.getenv("COMMIT_SHA")
    if not sha_short and env_sha:
        sha_short = (env_sha or "")[:7]

    logger.info(f"Code version: branch={branch or 'unknown'} commit={sha_short or 'unknown'}")

def _log_prompt_fingerprint():
    """Log a simple fingerprint of the keyword prompt file for traceability."""
    prompt_path = os.path.join("Pipeline", "prompts", "extract_keywords.txt")
    try:
        with open(prompt_path, "rb") as f:
            data = f.read()
        sha1 = hashlib.sha1(data).hexdigest()[:12]
        head_preview = data.decode(errors="ignore").splitlines()[0:1]
        preview = head_preview[0] if head_preview else ""
        logger.info(f"Prompt fingerprint: {prompt_path} sha1={sha1} head='{preview[:80]}'")
    except Exception as e:
        logger.info(f"Prompt fingerprint: {prompt_path} unavailable ({e})")

def main():
    """Main entry point for the application when run on Render."""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Resume Optimizer service")
    parser.add_argument("--port", type=int, default=8080, help="Port to run the service on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Run in debug mode")
    args, unknown = parser.parse_known_args()
    
    # Load environment variables
    load_dotenv()
    
    # Set environment variables from arguments
    os.environ["PORT"] = str(args.port)
    os.environ["RENDER"] = "true"
    
    logger.info(f"Starting Resume Optimizer service on {args.host}:{args.port}")
    _log_git_info()
    _log_prompt_fingerprint()
    
    try:
        # Import and create the Flask application
        try:
            from working_app import create_app
            logger.info("Using working_app.py")
        except ImportError as e:
            logger.critical(f"Could not import app: {str(e)}")
            raise ImportError("Failed to import application module")
        
        # Create the application
        app = create_app()
        
        # Run the application
        if args.debug:
            logger.info("Running in debug mode")
            app.run(host=args.host, port=args.port, debug=True)
        else:
            app.run(host=args.host, port=args.port)
            
    except Exception as e:
        logger.critical(f"Failed to start application: {str(e)}")
        logger.critical(f"Exception type: {type(e).__name__}")
        logger.critical(f"Exception args: {e.args}")
        sys.exit(1)

if __name__ == "__main__":
    main() 