#!/usr/bin/env python3
import os
import sys
import unittest
import json
import time
import tempfile
import shutil
import requests
import subprocess
import threading
import socket
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# Add script directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import application modules
try:
    from app import create_app
    from diagnostic_system import DiagnosticSystem, create_diagnostic_system
    import database
    modules_imported = True
except ImportError as e:
    print(f"Failed to import modules: {e}")
    modules_imported = False

# Constants
TEST_PORT = 5050
TEST_SERVER_URL = f"http://localhost:{TEST_PORT}"
TEST_TIMEOUT = 10  # Seconds

# Helper function to find an available port
def find_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# Flask server for testing
class FlaskServerThread(threading.Thread):
    def __init__(self, app, port=None, use_reloader=False):
        threading.Thread.__init__(self, daemon=True)
        self.port = port or find_available_port()
        self.app = app
        self.use_reloader = use_reloader
        self.is_running = threading.Event()
        self.server_started = threading.Event()

    def run(self):
        try:
            # Signal that the thread is running
            self.is_running.set()
            # Start Flask server
            self.app.run(host='localhost', port=self.port, use_reloader=self.use_reloader)
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.is_running.clear()

    def start(self):
        super().start()
        # Wait for server to start
        time.sleep(1)  # Give Flask time to start
        self.server_started.set()

    def stop(self):
        self.is_running.clear()

@contextmanager
def run_flask_app(app, port=None):
    """Context manager to run Flask app in a separate thread"""
    server = FlaskServerThread(app, port)
    try:
        server.start()
        server.server_started.wait(TEST_TIMEOUT)
        if not server.is_running.is_set():
            raise RuntimeError("Failed to start Flask server")
        yield server
    finally:
        server.stop()

# Utility for measuring execution time
@contextmanager
def timer():
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time
        print(f"Execution time: {duration:.3f} seconds")

# Test Case for the whole system
class SystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        print("\n=== Setting up test environment ===")
        # Create temp directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="resume_optimizer_test_")
        
        # Save original environment variables
        cls.original_env = os.environ.copy()
        
        # Setup test environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SUPABASE_URL'] = 'https://example-test.supabase.co'
        os.environ['SUPABASE_KEY'] = 'test_key'
        os.environ['OPENAI_API_KEY'] = 'test_key'
        
        # Create test directories
        cls.upload_dir = os.path.join(cls.test_dir, 'uploads')
        cls.output_dir = os.path.join(cls.test_dir, 'outputs')
        os.makedirs(cls.upload_dir, exist_ok=True)
        os.makedirs(cls.output_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        print("\n=== Cleaning up test environment ===")
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(cls.original_env)
        
        # Clean up test directory
        try:
            shutil.rmtree(cls.test_dir)
        except Exception as e:
            print(f"Warning: Failed to clean up test directory: {e}")

    def setUp(self):
        """Set up before each test"""
        # Create a test client
        if modules_imported:
            self.app = create_app()
            self.app.config['TESTING'] = True
            self.app.config['SERVER_NAME'] = f'localhost:{TEST_PORT}'
            self.app.config['UPLOAD_FOLDER'] = self.upload_dir
            self.app.config['OUTPUT_FOLDER'] = self.output_dir
            self.client = self.app.test_client()
            
    def test_01_application_startup(self):
        """Test basic application startup"""
        print("\n=== Test: Application Startup ===")
        with timer():
            self.assertTrue(modules_imported, "Modules should be importable")
            self.assertIsNotNone(self.app, "App should be created")
            self.assertIsInstance(self.app.config, dict, "App config should be a dictionary")
            
            # Verify essential config settings
            self.assertEqual(self.app.config['TESTING'], True, "App should be in testing mode")
            self.assertEqual(self.app.config['UPLOAD_FOLDER'], self.upload_dir, "Upload folder should be set")
            
            print("✅ Application startup test passed")

    def test_02_environment_variables(self):
        """Test environment variable loading"""
        print("\n=== Test: Environment Variables ===")
        with timer():
            # Check essential environment variables
            self.assertEqual(os.environ.get('FLASK_ENV'), 'testing', "FLASK_ENV should be 'testing'")
            self.assertIsNotNone(os.environ.get('SUPABASE_URL'), "SUPABASE_URL should be set")
            self.assertIsNotNone(os.environ.get('SUPABASE_KEY'), "SUPABASE_KEY should be set")
            self.assertIsNotNone(os.environ.get('OPENAI_API_KEY'), "OPENAI_API_KEY should be set")
            
            # Test environment variable loading in app
            with self.app.app_context():
                secret_key = self.app.config.get('SECRET_KEY')
                self.assertIsNotNone(secret_key, "SECRET_KEY should be set")
            
            print("✅ Environment variables test passed")

    def test_03_file_system_operations(self):
        """Test file system operations"""
        print("\n=== Test: File System Operations ===")
        with timer():
            # Test directory creation
            test_subdir = os.path.join(self.test_dir, 'test_subdir')
            os.makedirs(test_subdir, exist_ok=True)
            self.assertTrue(os.path.exists(test_subdir), "Test subdirectory should be created")
            
            # Test file writing
            test_file = os.path.join(test_subdir, 'test_file.txt')
            with open(test_file, 'w') as f:
                f.write('Test content')
            self.assertTrue(os.path.exists(test_file), "Test file should be created")
            
            # Test file reading
            with open(test_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, 'Test content', "File content should match what was written")
            
            # Clean up
            os.remove(test_file)
            os.rmdir(test_subdir)
            
            # Verify upload and output directories
            self.assertTrue(os.path.exists(self.upload_dir), "Upload directory should exist")
            self.assertTrue(os.path.exists(self.output_dir), "Output directory should exist")
            
            print("✅ File system operations test passed")

    def test_04_diagnostic_system(self):
        """Test diagnostic system functionality"""
        print("\n=== Test: Diagnostic System ===")
        with timer():
            # Create diagnostic system
            diagnostic = create_diagnostic_system()
            self.assertIsNotNone(diagnostic, "Diagnostic system should be created")
            self.assertIsInstance(diagnostic, DiagnosticSystem, "Diagnostic system should be an instance of DiagnosticSystem")
            
            # Check system information
            system_info = diagnostic._get_system_info()
            self.assertIsInstance(system_info, dict, "System info should be a dictionary")
            self.assertIn('python_version', system_info, "System info should include Python version")
            
            # Check memory information
            memory_info = diagnostic._get_memory_info()
            self.assertIsInstance(memory_info, dict, "Memory info should be a dictionary")
            self.assertIn('process', memory_info, "Memory info should include process info")
            self.assertIn('system', memory_info, "Memory info should include system info")
            
            # Check file system
            fs_info = diagnostic.check_file_system()
            self.assertIsInstance(fs_info, dict, "File system info should be a dictionary")
            self.assertIn('status', fs_info, "File system info should include status")
            
            # Test transaction tracking
            tx_id = 'test-transaction'
            path = '/test/path'
            method = 'GET'
            status_code = 200
            
            # Start transaction
            result = diagnostic.start_transaction(tx_id, path, method)
            self.assertTrue(result, "Start transaction should return True")
            
            # Add transaction step
            step_result = diagnostic.add_transaction_step(tx_id, 'test_component', 'ok', 'Test message')
            self.assertTrue(step_result, "Add transaction step should return True")
            
            # Complete transaction
            complete_result = diagnostic.complete_transaction(tx_id, status_code)
            self.assertTrue(complete_result, "Complete transaction should return True")
            
            # Check transaction history
            self.assertGreater(len(diagnostic.transaction_history), 0, "Transaction history should not be empty")
            
            print("✅ Diagnostic system test passed")

    def test_05_api_endpoints(self):
        """Test API endpoints"""
        print("\n=== Test: API Endpoints ===")
        with timer():
            with self.app.test_client() as client:
                # Test root endpoint
                response = client.get('/')
                self.assertEqual(response.status_code, 200, "Root endpoint should return 200")
                
                # Test health endpoint
                response = client.get('/api/health')
                self.assertEqual(response.status_code, 200, "Health endpoint should return 200")
                data = json.loads(response.data)
                self.assertEqual(data['status'], 'healthy', "Health status should be 'healthy'")
                
                # Test test endpoint
                response = client.get('/api/test')
                self.assertEqual(response.status_code, 200, "Test endpoint should return 200")
                
                # Test diagnostic endpoint
                response = client.get('/api/diagnostic')
                self.assertEqual(response.status_code, 200, "Diagnostic endpoint should return 200")
                data = json.loads(response.data)
                self.assertIn('status', data, "Diagnostic response should include status")
                self.assertIn('components', data, "Diagnostic response should include components")
            
            print("✅ API endpoints test passed")

    def test_06_database_module(self):
        """Test database module functionality"""
        print("\n=== Test: Database Module ===")
        with timer():
            # Test getting DB (likely fallback in test environment)
            db = database.get_db()
            self.assertIsNotNone(db, "Database client should be provided")
            
            # Test health check
            health_check = database.health_check()
            self.assertIsInstance(health_check, dict, "Health check should return a dictionary")
            self.assertIn('status', health_check, "Health check should include status")
            
            # Test connection test
            connection_test = database.test_connection()
            self.assertIsInstance(connection_test, dict, "Connection test should return a dictionary")
            self.assertIn('status', connection_test, "Connection test should include status")
            
            # Test connection with invalid credentials
            original_url = os.environ.get('SUPABASE_URL')
            os.environ['SUPABASE_URL'] = 'https://invalid-url.supabase.co'
            
            # Reset connection to force a reconnect
            database._supabase_client = None
            
            # This should fall back to in-memory DB
            fallback_db = database.get_db()
            self.assertIsNotNone(fallback_db, "Should get fallback DB with invalid credentials")
            
            # Restore original URL
            if original_url:
                os.environ['SUPABASE_URL'] = original_url
            else:
                del os.environ['SUPABASE_URL']
            
            # Reset database client
            database._supabase_client = None
            
            # Check tables
            tables_result = database.create_tables()
            self.assertIsInstance(tables_result, dict, "Create tables should return a dictionary")
            
            print("✅ Database module test passed")

    def test_07_httpx_monkey_patch(self):
        """Test httpx monkey patch"""
        print("\n=== Test: HTTPX Monkey Patch ===")
        with timer():
            import httpx
            
            # Test that our monkey patch is applied
            self.assertTrue(hasattr(httpx, 'request'), "httpx should have request method")
            
            # Test with a dictionary response that has no headers
            dict_response = {'key': 'value'}
            
            # Simulate the monkey patch operation
            from app import patched_request
            patched_result = patched_request(dict_response)
            
            # Verify patch added headers to the dict
            self.assertTrue(hasattr(patched_result, 'headers'), "Patched response should have headers attribute")
            
            print("✅ HTTPX monkey patch test passed")

    def test_08_error_handling(self):
        """Test error handling"""
        print("\n=== Test: Error Handling ===")
        with timer():
            with self.app.test_client() as client:
                # Test 404 handling
                response = client.get('/nonexistent-path')
                self.assertEqual(response.status_code, 404, "Nonexistent path should return 404")
                
                # Test database error handling
                try:
                    # Force a database error
                    result = database.run_query('nonexistent_table', 'select')
                    # This should not be reached
                    self.fail("Database query to nonexistent table should raise an exception")
                except Exception as e:
                    # Exception was correctly raised
                    self.assertIsInstance(e, Exception, "Exception should be raised for invalid table")
                
                # Test fallback mechanisms
                # Mock a service being unavailable
                diagnostic = create_diagnostic_system()
                diagnostic_check = diagnostic.check_system()
                
                # Even if some components fail, we should still get a result
                self.assertIsInstance(diagnostic_check, dict, "System check should return a dictionary even if components fail")
                
            print("✅ Error handling test passed")

    def test_09_diagnostic_dashboard(self):
        """Test diagnostic dashboard accessibility"""
        print("\n=== Test: Diagnostic Dashboard ===")
        
        # This test requires running a real server to check HTML responses
        test_port = TEST_PORT
        
        with timer():
            # Initialize app with proper settings
            app = create_app()
            app.config['TESTING'] = True
            app.config['DEBUG'] = False
            app.config['UPLOAD_FOLDER'] = self.upload_dir
            app.config['OUTPUT_FOLDER'] = self.output_dir
            
            # Run app in a separate thread
            with run_flask_app(app, test_port):
                time.sleep(2)  # Give Flask time to fully start
                
                try:
                    # Test diagnostics dashboard
                    response = requests.get(f"{TEST_SERVER_URL}/diagnostic/diagnostics")
                    self.assertEqual(response.status_code, 200, "Diagnostics dashboard should return 200")
                    self.assertIn('text/html', response.headers['Content-Type'], "Diagnostics dashboard should return HTML")
                    
                    # Test status page
                    response = requests.get(f"{TEST_SERVER_URL}/diagnostic/status")
                    self.assertEqual(response.status_code, 200, "Status page should return 200")
                    self.assertIn('text/html', response.headers['Content-Type'], "Status page should return HTML")
                    
                    print("✅ Diagnostic dashboard test passed")
                except requests.RequestException as e:
                    self.fail(f"Failed to connect to diagnostic dashboard: {e}")

    def test_10_end_to_end(self):
        """End-to-end test of the diagnostic system"""
        print("\n=== Test: End-to-End ===")
        with timer():
            # Test creating app, initializing diagnostic system, and running system check
            app = create_app()
            diagnostic = None
            
            # Look for diagnostic blueprint among registered blueprints
            for blueprint in app.blueprints:
                if blueprint.startswith('diagnostic'):
                    diagnostic_blueprint = app.blueprints[blueprint]
                    self.assertIsNotNone(diagnostic_blueprint, "Diagnostic blueprint should be registered")
            
            # Test DB initialization
            db = database.get_db()
            self.assertIsNotNone(db, "Database should be initialized")
            
            # Test system check via in-app endpoint
            with app.test_client() as client:
                response = client.get('/api/diagnostic')
                self.assertEqual(response.status_code, 200, "Diagnostic API should return 200")
                data = json.loads(response.data)
                self.assertIn('components', data, "Diagnostic response should include components")
                
                # Check all critical components are reported
                critical_components = ['system', 'database', 'file_system']
                for component in critical_components:
                    self.assertIn(component, data['components'], f"{component} should be in diagnostic components")
            
            print("✅ End-to-end test passed")


def run_tests():
    """Run all tests and return exit code"""
    print(f"=== Resume Optimizer System Tests ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Running tests from: {script_dir}\n")
    
    # Run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromTestCase(SystemTestCase)
    
    # Run tests with verbosity=2 for more detailed output
    result = unittest.TextTestRunner(verbosity=2).run(test_suite)
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code) 
import os
import sys
import unittest
import json
import time
import tempfile
import shutil
import requests
import subprocess
import threading
import socket
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# Add script directory to path
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)

# Import application modules
try:
    from app import create_app
    from diagnostic_system import DiagnosticSystem, create_diagnostic_system
    import database
    modules_imported = True
except ImportError as e:
    print(f"Failed to import modules: {e}")
    modules_imported = False

# Constants
TEST_PORT = 5050
TEST_SERVER_URL = f"http://localhost:{TEST_PORT}"
TEST_TIMEOUT = 10  # Seconds

# Helper function to find an available port
def find_available_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

# Flask server for testing
class FlaskServerThread(threading.Thread):
    def __init__(self, app, port=None, use_reloader=False):
        threading.Thread.__init__(self, daemon=True)
        self.port = port or find_available_port()
        self.app = app
        self.use_reloader = use_reloader
        self.is_running = threading.Event()
        self.server_started = threading.Event()

    def run(self):
        try:
            # Signal that the thread is running
            self.is_running.set()
            # Start Flask server
            self.app.run(host='localhost', port=self.port, use_reloader=self.use_reloader)
        except Exception as e:
            print(f"Server error: {e}")
        finally:
            self.is_running.clear()

    def start(self):
        super().start()
        # Wait for server to start
        time.sleep(1)  # Give Flask time to start
        self.server_started.set()

    def stop(self):
        self.is_running.clear()

@contextmanager
def run_flask_app(app, port=None):
    """Context manager to run Flask app in a separate thread"""
    server = FlaskServerThread(app, port)
    try:
        server.start()
        server.server_started.wait(TEST_TIMEOUT)
        if not server.is_running.is_set():
            raise RuntimeError("Failed to start Flask server")
        yield server
    finally:
        server.stop()

# Utility for measuring execution time
@contextmanager
def timer():
    start_time = time.time()
    try:
        yield
    finally:
        end_time = time.time()
        duration = end_time - start_time
        print(f"Execution time: {duration:.3f} seconds")

# Test Case for the whole system
class SystemTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        """Set up test environment"""
        print("\n=== Setting up test environment ===")
        # Create temp directory for testing
        cls.test_dir = tempfile.mkdtemp(prefix="resume_optimizer_test_")
        
        # Save original environment variables
        cls.original_env = os.environ.copy()
        
        # Setup test environment variables
        os.environ['FLASK_ENV'] = 'testing'
        os.environ['SUPABASE_URL'] = 'https://example-test.supabase.co'
        os.environ['SUPABASE_KEY'] = 'test_key'
        os.environ['OPENAI_API_KEY'] = 'test_key'
        
        # Create test directories
        cls.upload_dir = os.path.join(cls.test_dir, 'uploads')
        cls.output_dir = os.path.join(cls.test_dir, 'outputs')
        os.makedirs(cls.upload_dir, exist_ok=True)
        os.makedirs(cls.output_dir, exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        """Clean up test environment"""
        print("\n=== Cleaning up test environment ===")
        # Restore original environment variables
        os.environ.clear()
        os.environ.update(cls.original_env)
        
        # Clean up test directory
        try:
            shutil.rmtree(cls.test_dir)
        except Exception as e:
            print(f"Warning: Failed to clean up test directory: {e}")

    def setUp(self):
        """Set up before each test"""
        # Create a test client
        if modules_imported:
            self.app = create_app()
            self.app.config['TESTING'] = True
            self.app.config['SERVER_NAME'] = f'localhost:{TEST_PORT}'
            self.app.config['UPLOAD_FOLDER'] = self.upload_dir
            self.app.config['OUTPUT_FOLDER'] = self.output_dir
            self.client = self.app.test_client()
            
    def test_01_application_startup(self):
        """Test basic application startup"""
        print("\n=== Test: Application Startup ===")
        with timer():
            self.assertTrue(modules_imported, "Modules should be importable")
            self.assertIsNotNone(self.app, "App should be created")
            self.assertIsInstance(self.app.config, dict, "App config should be a dictionary")
            
            # Verify essential config settings
            self.assertEqual(self.app.config['TESTING'], True, "App should be in testing mode")
            self.assertEqual(self.app.config['UPLOAD_FOLDER'], self.upload_dir, "Upload folder should be set")
            
            print("✅ Application startup test passed")

    def test_02_environment_variables(self):
        """Test environment variable loading"""
        print("\n=== Test: Environment Variables ===")
        with timer():
            # Check essential environment variables
            self.assertEqual(os.environ.get('FLASK_ENV'), 'testing', "FLASK_ENV should be 'testing'")
            self.assertIsNotNone(os.environ.get('SUPABASE_URL'), "SUPABASE_URL should be set")
            self.assertIsNotNone(os.environ.get('SUPABASE_KEY'), "SUPABASE_KEY should be set")
            self.assertIsNotNone(os.environ.get('OPENAI_API_KEY'), "OPENAI_API_KEY should be set")
            
            # Test environment variable loading in app
            with self.app.app_context():
                secret_key = self.app.config.get('SECRET_KEY')
                self.assertIsNotNone(secret_key, "SECRET_KEY should be set")
            
            print("✅ Environment variables test passed")

    def test_03_file_system_operations(self):
        """Test file system operations"""
        print("\n=== Test: File System Operations ===")
        with timer():
            # Test directory creation
            test_subdir = os.path.join(self.test_dir, 'test_subdir')
            os.makedirs(test_subdir, exist_ok=True)
            self.assertTrue(os.path.exists(test_subdir), "Test subdirectory should be created")
            
            # Test file writing
            test_file = os.path.join(test_subdir, 'test_file.txt')
            with open(test_file, 'w') as f:
                f.write('Test content')
            self.assertTrue(os.path.exists(test_file), "Test file should be created")
            
            # Test file reading
            with open(test_file, 'r') as f:
                content = f.read()
            self.assertEqual(content, 'Test content', "File content should match what was written")
            
            # Clean up
            os.remove(test_file)
            os.rmdir(test_subdir)
            
            # Verify upload and output directories
            self.assertTrue(os.path.exists(self.upload_dir), "Upload directory should exist")
            self.assertTrue(os.path.exists(self.output_dir), "Output directory should exist")
            
            print("✅ File system operations test passed")

    def test_04_diagnostic_system(self):
        """Test diagnostic system functionality"""
        print("\n=== Test: Diagnostic System ===")
        with timer():
            # Create diagnostic system
            diagnostic = create_diagnostic_system()
            self.assertIsNotNone(diagnostic, "Diagnostic system should be created")
            self.assertIsInstance(diagnostic, DiagnosticSystem, "Diagnostic system should be an instance of DiagnosticSystem")
            
            # Check system information
            system_info = diagnostic._get_system_info()
            self.assertIsInstance(system_info, dict, "System info should be a dictionary")
            self.assertIn('python_version', system_info, "System info should include Python version")
            
            # Check memory information
            memory_info = diagnostic._get_memory_info()
            self.assertIsInstance(memory_info, dict, "Memory info should be a dictionary")
            self.assertIn('process', memory_info, "Memory info should include process info")
            self.assertIn('system', memory_info, "Memory info should include system info")
            
            # Check file system
            fs_info = diagnostic.check_file_system()
            self.assertIsInstance(fs_info, dict, "File system info should be a dictionary")
            self.assertIn('status', fs_info, "File system info should include status")
            
            # Test transaction tracking
            tx_id = 'test-transaction'
            path = '/test/path'
            method = 'GET'
            status_code = 200
            
            # Start transaction
            result = diagnostic.start_transaction(tx_id, path, method)
            self.assertTrue(result, "Start transaction should return True")
            
            # Add transaction step
            step_result = diagnostic.add_transaction_step(tx_id, 'test_component', 'ok', 'Test message')
            self.assertTrue(step_result, "Add transaction step should return True")
            
            # Complete transaction
            complete_result = diagnostic.complete_transaction(tx_id, status_code)
            self.assertTrue(complete_result, "Complete transaction should return True")
            
            # Check transaction history
            self.assertGreater(len(diagnostic.transaction_history), 0, "Transaction history should not be empty")
            
            print("✅ Diagnostic system test passed")

    def test_05_api_endpoints(self):
        """Test API endpoints"""
        print("\n=== Test: API Endpoints ===")
        with timer():
            with self.app.test_client() as client:
                # Test root endpoint
                response = client.get('/')
                self.assertEqual(response.status_code, 200, "Root endpoint should return 200")
                
                # Test health endpoint
                response = client.get('/api/health')
                self.assertEqual(response.status_code, 200, "Health endpoint should return 200")
                data = json.loads(response.data)
                self.assertEqual(data['status'], 'healthy', "Health status should be 'healthy'")
                
                # Test test endpoint
                response = client.get('/api/test')
                self.assertEqual(response.status_code, 200, "Test endpoint should return 200")
                
                # Test diagnostic endpoint
                response = client.get('/api/diagnostic')
                self.assertEqual(response.status_code, 200, "Diagnostic endpoint should return 200")
                data = json.loads(response.data)
                self.assertIn('status', data, "Diagnostic response should include status")
                self.assertIn('components', data, "Diagnostic response should include components")
            
            print("✅ API endpoints test passed")

    def test_06_database_module(self):
        """Test database module functionality"""
        print("\n=== Test: Database Module ===")
        with timer():
            # Test getting DB (likely fallback in test environment)
            db = database.get_db()
            self.assertIsNotNone(db, "Database client should be provided")
            
            # Test health check
            health_check = database.health_check()
            self.assertIsInstance(health_check, dict, "Health check should return a dictionary")
            self.assertIn('status', health_check, "Health check should include status")
            
            # Test connection test
            connection_test = database.test_connection()
            self.assertIsInstance(connection_test, dict, "Connection test should return a dictionary")
            self.assertIn('status', connection_test, "Connection test should include status")
            
            # Test connection with invalid credentials
            original_url = os.environ.get('SUPABASE_URL')
            os.environ['SUPABASE_URL'] = 'https://invalid-url.supabase.co'
            
            # Reset connection to force a reconnect
            database._supabase_client = None
            
            # This should fall back to in-memory DB
            fallback_db = database.get_db()
            self.assertIsNotNone(fallback_db, "Should get fallback DB with invalid credentials")
            
            # Restore original URL
            if original_url:
                os.environ['SUPABASE_URL'] = original_url
            else:
                del os.environ['SUPABASE_URL']
            
            # Reset database client
            database._supabase_client = None
            
            # Check tables
            tables_result = database.create_tables()
            self.assertIsInstance(tables_result, dict, "Create tables should return a dictionary")
            
            print("✅ Database module test passed")

    def test_07_httpx_monkey_patch(self):
        """Test httpx monkey patch"""
        print("\n=== Test: HTTPX Monkey Patch ===")
        with timer():
            import httpx
            
            # Test that our monkey patch is applied
            self.assertTrue(hasattr(httpx, 'request'), "httpx should have request method")
            
            # Test with a dictionary response that has no headers
            dict_response = {'key': 'value'}
            
            # Simulate the monkey patch operation
            from app import patched_request
            patched_result = patched_request(dict_response)
            
            # Verify patch added headers to the dict
            self.assertTrue(hasattr(patched_result, 'headers'), "Patched response should have headers attribute")
            
            print("✅ HTTPX monkey patch test passed")

    def test_08_error_handling(self):
        """Test error handling"""
        print("\n=== Test: Error Handling ===")
        with timer():
            with self.app.test_client() as client:
                # Test 404 handling
                response = client.get('/nonexistent-path')
                self.assertEqual(response.status_code, 404, "Nonexistent path should return 404")
                
                # Test database error handling
                try:
                    # Force a database error
                    result = database.run_query('nonexistent_table', 'select')
                    # This should not be reached
                    self.fail("Database query to nonexistent table should raise an exception")
                except Exception as e:
                    # Exception was correctly raised
                    self.assertIsInstance(e, Exception, "Exception should be raised for invalid table")
                
                # Test fallback mechanisms
                # Mock a service being unavailable
                diagnostic = create_diagnostic_system()
                diagnostic_check = diagnostic.check_system()
                
                # Even if some components fail, we should still get a result
                self.assertIsInstance(diagnostic_check, dict, "System check should return a dictionary even if components fail")
                
            print("✅ Error handling test passed")

    def test_09_diagnostic_dashboard(self):
        """Test diagnostic dashboard accessibility"""
        print("\n=== Test: Diagnostic Dashboard ===")
        
        # This test requires running a real server to check HTML responses
        test_port = TEST_PORT
        
        with timer():
            # Initialize app with proper settings
            app = create_app()
            app.config['TESTING'] = True
            app.config['DEBUG'] = False
            app.config['UPLOAD_FOLDER'] = self.upload_dir
            app.config['OUTPUT_FOLDER'] = self.output_dir
            
            # Run app in a separate thread
            with run_flask_app(app, test_port):
                time.sleep(2)  # Give Flask time to fully start
                
                try:
                    # Test diagnostics dashboard
                    response = requests.get(f"{TEST_SERVER_URL}/diagnostic/diagnostics")
                    self.assertEqual(response.status_code, 200, "Diagnostics dashboard should return 200")
                    self.assertIn('text/html', response.headers['Content-Type'], "Diagnostics dashboard should return HTML")
                    
                    # Test status page
                    response = requests.get(f"{TEST_SERVER_URL}/diagnostic/status")
                    self.assertEqual(response.status_code, 200, "Status page should return 200")
                    self.assertIn('text/html', response.headers['Content-Type'], "Status page should return HTML")
                    
                    print("✅ Diagnostic dashboard test passed")
                except requests.RequestException as e:
                    self.fail(f"Failed to connect to diagnostic dashboard: {e}")

    def test_10_end_to_end(self):
        """End-to-end test of the diagnostic system"""
        print("\n=== Test: End-to-End ===")
        with timer():
            # Test creating app, initializing diagnostic system, and running system check
            app = create_app()
            diagnostic = None
            
            # Look for diagnostic blueprint among registered blueprints
            for blueprint in app.blueprints:
                if blueprint.startswith('diagnostic'):
                    diagnostic_blueprint = app.blueprints[blueprint]
                    self.assertIsNotNone(diagnostic_blueprint, "Diagnostic blueprint should be registered")
            
            # Test DB initialization
            db = database.get_db()
            self.assertIsNotNone(db, "Database should be initialized")
            
            # Test system check via in-app endpoint
            with app.test_client() as client:
                response = client.get('/api/diagnostic')
                self.assertEqual(response.status_code, 200, "Diagnostic API should return 200")
                data = json.loads(response.data)
                self.assertIn('components', data, "Diagnostic response should include components")
                
                # Check all critical components are reported
                critical_components = ['system', 'database', 'file_system']
                for component in critical_components:
                    self.assertIn(component, data['components'], f"{component} should be in diagnostic components")
            
            print("✅ End-to-end test passed")


def run_tests():
    """Run all tests and return exit code"""
    print(f"=== Resume Optimizer System Tests ===")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python version: {sys.version}")
    print(f"Running tests from: {script_dir}\n")
    
    # Run tests
    test_loader = unittest.TestLoader()
    test_suite = test_loader.loadTestsFromTestCase(SystemTestCase)
    
    # Run tests with verbosity=2 for more detailed output
    result = unittest.TextTestRunner(verbosity=2).run(test_suite)
    
    # Print summary
    print("\n=== Test Summary ===")
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    
    # Return exit code based on test results
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    exit_code = run_tests()
    sys.exit(exit_code) 