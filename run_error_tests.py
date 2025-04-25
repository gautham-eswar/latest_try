#!/usr/bin/env python3
"""
Run Error Handling Tests for Resume Optimizer

This script starts the resume processor application in the background,
then runs the error handling tests against it.
"""

import os
import sys
import subprocess
import time
import logging
import signal
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run_error_tests')

def parse_args():
    parser = argparse.ArgumentParser(description='Run error handling tests for Resume Optimizer')
    parser.add_argument('--port', type=int, default=8085, help='Port for the test server (default: 8085)')
    parser.add_argument('--app', type=str, default='working_app', help='App module to run (default: working_app)')
    parser.add_argument('--wait', type=int, default=3, help='Seconds to wait for server startup (default: 3)')
    parser.add_argument('--skip-server', action='store_true', help='Skip starting server (use if already running)')
    return parser.parse_args()

def start_server(app_module, port):
    """Start the Flask server"""
    logger.info(f"Starting {app_module} on port {port}")
    
    # Use a separate process to run the server
    cmd = [
        "python3", 
        f"{app_module}.py", 
        f"--port={port}",
        "--debug"
    ]
    
    # Start the server process
    try:
        process = subprocess.Popen(cmd)
        logger.info(f"Server process started with PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return None

def run_tests(port):
    """Run the error handling tests"""
    logger.info("Running error handling tests")
    
    # Use a separate process to run the tests
    cmd = [
        "python3",
        "test_error_handling.py"
    ]
    
    # Set the environment variables for the test
    env = os.environ.copy()
    env["TEST_SERVER_URL"] = f"http://localhost:{port}"
    env["SKIP_SERVER_START"] = "true"  # Skip starting server in the test since we already started it
    env["SERVER_WAIT_TIME"] = "0"  # No need to wait since server is already running
    
    # Run the tests
    try:
        result = subprocess.run(cmd, env=env)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        return False

def stop_server(process):
    """Stop the Flask server"""
    if process:
        logger.info(f"Stopping server process (PID {process.pid})")
        try:
            # Try to terminate gracefully
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate
            logger.warning("Server did not terminate gracefully, force killing")
            process.kill()
            process.wait()

def cleanup_on_exit(process):
    """Make sure to clean up the server process on exit"""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, cleaning up")
        stop_server(process)
        sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

if __name__ == "__main__":
    args = parse_args()
    server_process = None
    
    try:
        if not args.skip_server:
            # Start the server
            server_process = start_server(args.app, args.port)
            if not server_process:
                logger.error("Failed to start server, exiting")
                sys.exit(1)
            
            # Register cleanup handler
            cleanup_on_exit(server_process)
            
            # Wait for the server to start
            logger.info(f"Waiting {args.wait} seconds for server to start")
            time.sleep(args.wait)
        else:
            logger.info("Skipping server startup as requested")
        
        # Run the tests
        success = run_tests(args.port)
        
        # Clean up
        if not args.skip_server and server_process:
            stop_server(server_process)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        if not args.skip_server and server_process:
            stop_server(server_process)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if not args.skip_server and server_process:
            stop_server(server_process)
        sys.exit(1) 
"""
Run Error Handling Tests for Resume Optimizer

This script starts the resume processor application in the background,
then runs the error handling tests against it.
"""

import os
import sys
import subprocess
import time
import logging
import signal
import argparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('run_error_tests')

def parse_args():
    parser = argparse.ArgumentParser(description='Run error handling tests for Resume Optimizer')
    parser.add_argument('--port', type=int, default=8085, help='Port for the test server (default: 8085)')
    parser.add_argument('--app', type=str, default='working_app', help='App module to run (default: working_app)')
    parser.add_argument('--wait', type=int, default=3, help='Seconds to wait for server startup (default: 3)')
    parser.add_argument('--skip-server', action='store_true', help='Skip starting server (use if already running)')
    return parser.parse_args()

def start_server(app_module, port):
    """Start the Flask server"""
    logger.info(f"Starting {app_module} on port {port}")
    
    # Use a separate process to run the server
    cmd = [
        "python3", 
        f"{app_module}.py", 
        f"--port={port}",
        "--debug"
    ]
    
    # Start the server process
    try:
        process = subprocess.Popen(cmd)
        logger.info(f"Server process started with PID {process.pid}")
        return process
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        return None

def run_tests(port):
    """Run the error handling tests"""
    logger.info("Running error handling tests")
    
    # Use a separate process to run the tests
    cmd = [
        "python3",
        "test_error_handling.py"
    ]
    
    # Set the environment variables for the test
    env = os.environ.copy()
    env["TEST_SERVER_URL"] = f"http://localhost:{port}"
    env["SKIP_SERVER_START"] = "true"  # Skip starting server in the test since we already started it
    env["SERVER_WAIT_TIME"] = "0"  # No need to wait since server is already running
    
    # Run the tests
    try:
        result = subprocess.run(cmd, env=env)
        return result.returncode == 0
    except Exception as e:
        logger.error(f"Failed to run tests: {e}")
        return False

def stop_server(process):
    """Stop the Flask server"""
    if process:
        logger.info(f"Stopping server process (PID {process.pid})")
        try:
            # Try to terminate gracefully
            process.terminate()
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # Force kill if it doesn't terminate
            logger.warning("Server did not terminate gracefully, force killing")
            process.kill()
            process.wait()

def cleanup_on_exit(process):
    """Make sure to clean up the server process on exit"""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}, cleaning up")
        stop_server(process)
        sys.exit(1)
    
    # Register signal handlers
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

if __name__ == "__main__":
    args = parse_args()
    server_process = None
    
    try:
        if not args.skip_server:
            # Start the server
            server_process = start_server(args.app, args.port)
            if not server_process:
                logger.error("Failed to start server, exiting")
                sys.exit(1)
            
            # Register cleanup handler
            cleanup_on_exit(server_process)
            
            # Wait for the server to start
            logger.info(f"Waiting {args.wait} seconds for server to start")
            time.sleep(args.wait)
        else:
            logger.info("Skipping server startup as requested")
        
        # Run the tests
        success = run_tests(args.port)
        
        # Clean up
        if not args.skip_server and server_process:
            stop_server(server_process)
        
        # Exit with appropriate code
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        if not args.skip_server and server_process:
            stop_server(server_process)
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        if not args.skip_server and server_process:
            stop_server(server_process)
        sys.exit(1) 