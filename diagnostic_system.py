import os
import sys
import platform
import psutil
import json
import asyncio
import tempfile
from datetime import datetime
from functools import wraps
import logging
from pathlib import Path
import traceback
import uuid
from collections import deque

import httpx
from flask import Blueprint, jsonify, render_template, current_app, request

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('diagnostic_system')

class DiagnosticSystem:
    """Comprehensive diagnostic system for monitoring application health."""
    
    def __init__(self):
        """Initialize the diagnostic system with a Blueprint."""
        self.blueprint = Blueprint('diagnostic', __name__, 
                                  template_folder='templates',
                                  static_folder='static')
        self._register_routes()
        self.start_time = datetime.now()
        self.transactions = {}
        self.transaction_history = []
        self.max_transaction_history = 100
        
        # Pipeline monitoring data
        self.pipeline_jobs = {}
        self.pipeline_history = deque(maxlen=20)
        self.pipeline_stages = [
            {'name': 'Resume Parser', 'icon': 'bi-file-earmark-text', 'status': 'unknown', 'success_rate': 0, 'avg_time': 0, 'count': 0},
            {'name': 'Keyword Extractor', 'icon': 'bi-tags', 'status': 'unknown', 'success_rate': 0, 'avg_time': 0, 'count': 0},
            {'name': 'Semantic Matcher', 'icon': 'bi-link-45deg', 'status': 'unknown', 'success_rate': 0, 'avg_time': 0, 'count': 0},
            {'name': 'Resume Enhancer', 'icon': 'bi-magic', 'status': 'unknown', 'success_rate': 0, 'avg_time': 0, 'count': 0},
            {'name': 'PDF Generator', 'icon': 'bi-file-earmark-pdf', 'status': 'unknown', 'success_rate': 0, 'avg_time': 0, 'count': 0}
        ]
        self.pipeline_status = {
            'status': 'unknown',
            'message': 'Pipeline has not been tested yet',
            'last_run': None,
            'success_rate': 0,
            'total_jobs': 0,
            'successful_jobs': 0
        }
        
        self.error_stats = {
            'count': 0,
            'by_type': {},
            'recent_errors': []
        }
        
    def init_app(self, app):
        """Register the diagnostic Blueprint with the Flask app."""
        app.register_blueprint(self.blueprint, url_prefix='/diagnostic')
        logger.info("Diagnostic system initialized for Flask application")
        
    def start_transaction(self, transaction_id, path, method):
        """Start tracking a transaction through the system."""
        try:
            self.transactions[transaction_id] = {
                'id': transaction_id,
                'path': path,
                'method': method,
                'start_time': datetime.now(),
                'steps': [],
                'status': 'in_progress'
            }
            logger.debug(f"Transaction started: {transaction_id} - {path} [{method}]")
            return True
        except Exception as e:
            logger.error(f"Failed to start transaction: {str(e)}")
            return False
        
    def add_transaction_step(self, transaction_id, component, status, message=None):
        """Add a step to an ongoing transaction."""
        try:
            if transaction_id in self.transactions:
                self.transactions[transaction_id]['steps'].append({
                    'component': component,
                    'status': status,
                    'timestamp': datetime.now(),
                    'message': message
                })
                logger.debug(f"Transaction step added: {transaction_id} - {component} ({status})")
                return True
            else:
                logger.warning(f"Attempt to add step to unknown transaction: {transaction_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to add transaction step: {str(e)}")
            return False
        
    def complete_transaction(self, transaction_id, status_code):
        """Complete a transaction and record its outcome."""
        try:
            if transaction_id in self.transactions:
                transaction = self.transactions[transaction_id]
                transaction['end_time'] = datetime.now()
                transaction['duration'] = (transaction['end_time'] - transaction['start_time']).total_seconds()
                transaction['status_code'] = status_code
                transaction['status'] = 'completed'
                
                # Move to history and remove from active transactions
                self.transaction_history.append(transaction)
                del self.transactions[transaction_id]
                
                # Keep history within size limit
                if len(self.transaction_history) > self.max_transaction_history:
                    self.transaction_history.pop(0)
                
                logger.info(f"Transaction completed: {transaction_id} - Status: {status_code}, Duration: {transaction['duration']:.3f}s")
                return True
            else:
                logger.warning(f"Attempt to complete unknown transaction: {transaction_id}")
                return False
        except Exception as e:
            logger.error(f"Failed to complete transaction: {str(e)}")
            return False
    
    def start_pipeline_job(self, resume_id, resume_type, job_description=None):
        """Start tracking a pipeline job for resume processing."""
        try:
            job_id = str(uuid.uuid4())
            self.pipeline_jobs[job_id] = {
                'id': job_id,
                'resume_id': resume_id,
                'resume_type': resume_type,
                'job_description': job_description[:100] + '...' if job_description and len(job_description) > 100 else job_description,
                'start_time': datetime.now(),
                'stages': [],
                'stages_completed': 0,
                'total_stages': len(self.pipeline_stages),
                'status': 'in_progress',
                'duration': 0
            }
            logger.info(f"Pipeline job started: {job_id} for resume {resume_id}")
            return job_id
        except Exception as e:
            logger.error(f"Failed to start pipeline job: {str(e)}")
            return None
        
    def record_pipeline_stage(self, job_id, stage_name, status, duration, message=None):
        """Record a stage completion in the resume processing pipeline."""
        try:
            if job_id not in self.pipeline_jobs:
                logger.warning(f"Attempt to record stage for unknown pipeline job: {job_id}")
                return False
                
            job = self.pipeline_jobs[job_id]
            
            # Find the stage index
            stage_index = next((i for i, s in enumerate(self.pipeline_stages) if s['name'] == stage_name), None)
            if stage_index is None:
                logger.warning(f"Unknown pipeline stage: {stage_name}")
                return False
                
            # Record the stage completion
            job['stages'].append({
                'name': stage_name,
                'status': status,
                'duration': duration,
                'timestamp': datetime.now(),
                'message': message
            })
            
            job['stages_completed'] += 1
            
            # Update pipeline stage metrics
            stage = self.pipeline_stages[stage_index]
            stage['count'] += 1
            stage['avg_time'] = ((stage['avg_time'] * (stage['count'] - 1)) + duration) / stage['count']
            if status == 'healthy':
                stage_success_count = sum(1 for s in job['stages'] if s['name'] == stage_name and s['status'] == 'healthy')
                stage['success_rate'] = (stage_success_count / stage['count']) * 100
                
            # Update stage status based on recent performance
            if stage['count'] >= 5:
                if stage['success_rate'] >= 90:
                    stage['status'] = 'healthy'
                elif stage['success_rate'] >= 70:
                    stage['status'] = 'warning'
                else:
                    stage['status'] = 'error'
            else:
                stage['status'] = status
                
            logger.debug(f"Pipeline stage recorded: {job_id} - {stage_name} ({status})")
            return True
        except Exception as e:
            logger.error(f"Failed to record pipeline stage: {str(e)}")
            return False
        
    def complete_pipeline_job(self, job_id, status, message=None):
        """Complete a pipeline job and record its outcome."""
        try:
            if job_id not in self.pipeline_jobs:
                logger.warning(f"Attempt to complete unknown pipeline job: {job_id}")
                return False
                
            job = self.pipeline_jobs[job_id]
            job['end_time'] = datetime.now()
            job['duration'] = (job['end_time'] - job['start_time']).total_seconds()
            job['status'] = status
            job['message'] = message
            
            # Move to history and remove from active jobs
            self.pipeline_history.append(job)
            del self.pipeline_jobs[job_id]
            
            # Update overall pipeline status
            self.pipeline_status['last_run'] = datetime.now()
            self.pipeline_status['total_jobs'] += 1
            if status == 'healthy':
                self.pipeline_status['successful_jobs'] += 1
                
            self.pipeline_status['success_rate'] = (self.pipeline_status['successful_jobs'] / self.pipeline_status['total_jobs']) * 100
            
            # Determine overall pipeline status
            if self.pipeline_status['total_jobs'] >= 5:
                if self.pipeline_status['success_rate'] >= 90:
                    self.pipeline_status['status'] = 'healthy'
                    self.pipeline_status['message'] = 'Pipeline is functioning normally'
                elif self.pipeline_status['success_rate'] >= 70:
                    self.pipeline_status['status'] = 'warning'
                    self.pipeline_status['message'] = 'Pipeline has decreased success rate'
                else:
                    self.pipeline_status['status'] = 'error'
                    self.pipeline_status['message'] = 'Pipeline has critical failure rate'
            else:
                self.pipeline_status['status'] = status
                self.pipeline_status['message'] = 'Pipeline has limited run history'
                
            logger.info(f"Pipeline job completed: {job_id} - Status: {status}, Duration: {job['duration']:.3f}s")
            return True
        except Exception as e:
            logger.error(f"Failed to complete pipeline job: {str(e)}")
            return False
    
    def check_system(self):
        """Run a comprehensive system check."""
        try:
            # Run component checks
            file_system_check = self.check_file_system()
            supabase_check = self.check_supabase()
            openai_check = self.check_openai()
            
            # Assemble components dictionary
            components = {
                'System': {
                    'status': 'healthy',
                    'message': f'Running on {platform.system()} {platform.release()}'
                },
                'Database': {
                    'status': supabase_check['status'],
                    'message': supabase_check['message']
                },
                'OpenAI API': {
                    'status': openai_check['status'],
                    'message': openai_check['message']
                },
                'File System': {
                    'status': file_system_check['status'],
                    'message': file_system_check['message']
                },
                'Pipeline': {
                    'status': self.pipeline_status['status'],
                    'message': self.pipeline_status['message']
                }
            }
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'uptime': (datetime.now() - self.start_time).total_seconds(),
                'components': components,
                'system': self._get_system_info(),
                'memory': self._get_memory_info(),
                'environment': self._get_environment_info(),
                'file_system': file_system_check,
                'supabase': supabase_check,
                'openai': openai_check,
                'pipeline': {
                    'status': self.pipeline_status['status'],
                    'message': self.pipeline_status['message'],
                    'success_rate': self.pipeline_status['success_rate'],
                    'total_jobs': self.pipeline_status['total_jobs'],
                    'stages': self.pipeline_stages,
                    'recent_jobs': list(self.pipeline_history)
                },
                'overall_status': 'healthy'
            }
            
            # Determine overall status based on component checks
            critical_services = ['file_system', 'supabase', 'openai', 'pipeline']
            failing_services = [s for s in critical_services if result[s]['status'] not in ['healthy', 'unknown']]
            
            if failing_services:
                if 'file_system' in failing_services:
                    result['overall_status'] = 'critical'
                elif len(failing_services) > 1:
                    result['overall_status'] = 'warning'
                else:
                    result['overall_status'] = 'warning'
            
            logger.info(f"System check completed: {result['overall_status']}")
            return result
        except Exception as e:
            logger.error(f"System check failed: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
        
    def check_supabase(self):
        """Check Supabase connection and functionality."""
        try:
            supabase_url = os.environ.get('SUPABASE_URL')
            supabase_key = os.environ.get('SUPABASE_KEY')
            if not (supabase_url and supabase_key):
                return {
                    'status': 'warning',
                    'message': 'Supabase credentials not configured',
                    'tables': None,
                    'ping': None
                }
            
            # We'll import here to isolate potential import errors
            try:
                from supabase import create_client
                supabase = create_client(supabase_url, supabase_key)
                
                # Check connection with a simple ping
                start_time = datetime.now()
                response = supabase.table('healthcheck').select('*').limit(1).execute()
                ping_time = (datetime.now() - start_time).total_seconds()
                
                # Check if critical tables exist
                tables_to_check = ['resumes', 'users', 'jobs']
                tables_status = {}
                for table in tables_to_check:
                    try:
                        res = supabase.table(table).select('count').limit(1).execute()
                        tables_status[table] = {
                            'exists': True,
                            'count': res.count if hasattr(res, 'count') else None,
                            'status': 'healthy'
                        }
                    except Exception as table_error:
                        tables_status[table] = {
                            'exists': False,
                            'error': str(table_error),
                            'status': 'error'
                        }
                
                # Determine overall Supabase status
                if all(t['status'] == 'healthy' for t in tables_status.values()):
                    status = 'healthy'
                    message = 'Supabase connection successful'
                else:
                    status = 'degraded'
                    message = 'Some tables are not accessible'
                
                return {
                    'status': status,
                    'message': message,
                    'ping': ping_time,
                    'tables': tables_status
                }
                
            except ImportError as e:
                return {
                    'status': 'error',
                    'message': f'Supabase library not available: {str(e)}',
                    'tables': None,
                    'ping': None
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'Supabase connection failed: {str(e)}',
                    'tables': None,
                    'ping': None
                }
                
        except Exception as e:
            logger.error(f"Supabase check failed: {str(e)}")
            return {
                'status': 'error',
                'message': f'Supabase check error: {str(e)}',
                'tables': None,
                'ping': None,
                'error': traceback.format_exc()
            }
        
    def check_openai(self):
        """Verify OpenAI API connection and status."""
        try:
            api_key = os.environ.get('OPENAI_API_KEY')
            if not api_key:
                return {
                    'status': 'warning',
                    'message': 'OpenAI API key not configured',
                    'models': None,
                    'ping': None
                }
            
            # We'll import here to isolate potential import errors
            try:
                from openai import OpenAI
                client = OpenAI(api_key=api_key)
                
                # Check connection with a simple ping
                start_time = datetime.now()
                models = client.models.list()
                ping_time = (datetime.now() - start_time).total_seconds()
                
                # Check if required models are available
                required_models = ['gpt-4-turbo', 'gpt-3.5-turbo']
                available_models = [model.id for model in models.data]
                
                model_status = {
                    model: model in available_models
                    for model in required_models
                }
                
                # Check rate limit information from headers
                rate_limit_info = {
                    'requests_remaining': 'unknown',
                    'request_limit': 'unknown',
                    'tokens_remaining': 'unknown',
                    'token_limit': 'unknown'
                }
                
                # Determine overall OpenAI status
                if all(model_status.values()):
                    status = 'healthy'
                    message = 'OpenAI API connection successful'
                else:
                    status = 'degraded'
                    message = 'Some required models are not available'
                
                return {
                    'status': status,
                    'message': message,
                    'ping': ping_time,
                    'models': model_status,
                    'rate_limits': rate_limit_info
                }
                
            except ImportError as e:
                return {
                    'status': 'error',
                    'message': f'OpenAI library not available: {str(e)}',
                    'models': None,
                    'ping': None
                }
            except Exception as e:
                return {
                    'status': 'error',
                    'message': f'OpenAI API connection failed: {str(e)}',
                    'models': None,
                    'ping': None
                }
                
        except Exception as e:
            logger.error(f"OpenAI check failed: {str(e)}")
            return {
                'status': 'error',
                'message': f'OpenAI check error: {str(e)}',
                'models': None,
                'ping': None,
                'error': traceback.format_exc()
            }
        
    def check_file_system(self):
        """Check if necessary directories exist and are writable."""
        try:
            result = {
                'status': 'healthy',
                'message': 'File system checks passed',
                'directories': {}
            }
            
            # Directories to check
            app_root = os.path.abspath(os.path.dirname(__file__))
            dirs_to_check = {
                'app_root': app_root,
                'templates': os.path.join(app_root, 'templates'),
                'static': os.path.join(app_root, 'static'),
                'tmp': tempfile.gettempdir()
            }
            
            # Check each directory
            for name, path in dirs_to_check.items():
                dir_status = {
                    'path': path,
                    'exists': os.path.exists(path),
                    'is_dir': os.path.isdir(path) if os.path.exists(path) else False,
                    'readable': os.access(path, os.R_OK) if os.path.exists(path) else False,
                    'writable': os.access(path, os.W_OK) if os.path.exists(path) else False,
                    'status': 'checking'
                }
                
                # Test write capability
                if dir_status['exists'] and dir_status['writable']:
                    try:
                        if name == 'tmp':  # Only actually write to temp dir
                            test_file = os.path.join(path, f'diagnostic_test_{datetime.now().timestamp()}.tmp')
                            with open(test_file, 'w') as f:
                                f.write('test')
                            os.remove(test_file)
                            dir_status['write_test'] = 'passed'
                        else:
                            dir_status['write_test'] = 'skipped'
                    except Exception as e:
                        dir_status['write_test'] = 'failed'
                        dir_status['write_error'] = str(e)
                else:
                    dir_status['write_test'] = 'skipped'
                
                # Set status based on checks
                if not dir_status['exists']:
                    dir_status['status'] = 'error'
                elif not dir_status['readable']:
                    dir_status['status'] = 'error'
                elif name == 'tmp' and (not dir_status['writable'] or dir_status['write_test'] == 'failed'):
                    dir_status['status'] = 'error'
                else:
                    dir_status['status'] = 'healthy'
                
                result['directories'][name] = dir_status
                
                # Update overall status if any directory has issues
                if dir_status['status'] == 'error':
                    if name == 'tmp':  # temp dir is critical
                        result['status'] = 'critical'
                        result['message'] = f'Critical directory {name} check failed'
                    else:
                        result['status'] = 'warning'
                        result['message'] = f'Directory {name} check failed'
            
            return result
            
        except Exception as e:
            logger.error(f"File system check failed: {str(e)}")
            return {
                'status': 'error',
                'message': f'File system check error: {str(e)}',
                'error': traceback.format_exc()
            }
    
    async def async_check_system(self):
        """Run system checks asynchronously."""
        try:
            # Run checks concurrently
            file_system_task = asyncio.create_task(self._async_check_file_system())
            supabase_task = asyncio.create_task(self._async_check_supabase())
            openai_task = asyncio.create_task(self._async_check_openai())
            
            # Wait for all checks to complete
            file_system_result = await file_system_task
            supabase_result = await supabase_task
            openai_result = await openai_task
            
            result = {
                'timestamp': datetime.now().isoformat(),
                'uptime': (datetime.now() - self.start_time).total_seconds(),
                'system': self._get_system_info(),
                'memory': self._get_memory_info(),
                'environment': self._get_environment_info(),
                'file_system': file_system_result,
                'supabase': supabase_result,
                'openai': openai_result,
                'pipeline': {
                    'status': self.pipeline_status['status'],
                    'message': self.pipeline_status['message'],
                    'success_rate': self.pipeline_status['success_rate'],
                    'total_jobs': self.pipeline_status['total_jobs'],
                    'stages': self.pipeline_stages,
                    'recent_jobs': list(self.pipeline_history)
                },
                'overall_status': 'healthy'
            }
            
            # Determine overall status based on component checks
            critical_services = ['file_system', 'supabase', 'openai', 'pipeline']
            failing_services = [s for s in critical_services if result[s]['status'] not in ['healthy', 'unknown']]
            
            if failing_services:
                if 'file_system' in failing_services:
                    result['overall_status'] = 'critical'
                elif len(failing_services) > 1:
                    result['overall_status'] = 'warning'
                else:
                    result['overall_status'] = 'warning'
            
            logger.info(f"Async system check completed: {result['overall_status']}")
            return result
            
        except Exception as e:
            logger.error(f"Async system check failed: {str(e)}")
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'error',
                'error': str(e),
                'traceback': traceback.format_exc()
            }
    
    async def _async_check_file_system(self):
        """Async version of file system check."""
        return self.check_file_system()
    
    async def _async_check_supabase(self):
        """Async version of Supabase check."""
        return self.check_supabase()
    
    async def _async_check_openai(self):
        """Async version of OpenAI check."""
        return self.check_openai()
    
    def _get_system_info(self):
        """Get detailed system information."""
        return {
            'platform': platform.platform(),
            'python_version': platform.python_version(),
            'python_implementation': platform.python_implementation(),
            'processor': platform.processor(),
            'cpu_count': os.cpu_count(),
            'hostname': platform.node(),
            'machine': platform.machine()
        }
    
    def _get_memory_info(self):
        """Get detailed memory usage information."""
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        sys_mem = psutil.virtual_memory()
        
        return {
            'process': {
                'rss': mem_info.rss,
                'rss_mb': mem_info.rss / (1024 * 1024),
                'vms': mem_info.vms,
                'vms_mb': mem_info.vms / (1024 * 1024)
            },
            'system': {
                'total': sys_mem.total,
                'total_gb': sys_mem.total / (1024 * 1024 * 1024),
                'available': sys_mem.available,
                'available_gb': sys_mem.available / (1024 * 1024 * 1024),
                'percent_used': sys_mem.percent
            }
        }
    
    def _get_environment_info(self):
        """Get environment information relevant to the application."""
        env_vars = [
            'FLASK_ENV', 'FLASK_DEBUG', 'PYTHONPATH', 
            'PORT', 'HOST', 'SERVER_NAME', 'SUPABASE_URL'
        ]
        
        return {
            'env_vars': {var: os.environ.get(var, '(not set)') 
                         for var in env_vars},
            'cwd': os.getcwd(),
            'user': os.getlogin() if hasattr(os, 'getlogin') else '(unknown)'
        }
        
    def _register_routes(self):
        """Register diagnostic endpoints with the Blueprint."""
        @self.blueprint.route('/health')
        def health():
            """Basic health check that always succeeds."""
            return jsonify({
                'status': 'healthy',
                'timestamp': datetime.now().isoformat(),
                'uptime': (datetime.now() - self.start_time).total_seconds()
            })
        
        @self.blueprint.route('/diagnostic')
        def diagnostic():
            """Detailed system information in JSON format."""
            result = self.check_system()
            return jsonify(result)
        
        @self.blueprint.route('/diagnostic/async')
        async def async_diagnostic():
            """Asynchronous detailed system information in JSON format."""
            result = await self.async_check_system()
            return jsonify(result)
        
        @self.blueprint.route('/supabase-test')
        def supabase_test():
            """Test Supabase connection."""
            result = self.check_supabase()
            return jsonify(result)
        
        @self.blueprint.route('/openai-test')
        def openai_test():
            """Test OpenAI connection."""
            result = self.check_openai()
            return jsonify(result)
        
        @self.blueprint.route('/test-pipeline')
        def test_pipeline():
            """Run a test of the resume processing pipeline."""
            try:
                # Create a simple test job
                job_id = self.start_pipeline_job('test-resume', 'pdf', 'This is a test job description')
                
                # Simulate pipeline stages with random success/failure
                import random
                import time
                
                overall_status = 'healthy'
                stages = [s['name'] for s in self.pipeline_stages]
                
                for stage in stages:
                    # Simulate processing time
                    duration = random.uniform(0.5, 3.0)
                    time.sleep(random.uniform(0.1, 0.5))  # Short sleep to be responsive
                    
                    # Random success rate for demonstration
                    status = random.choices(
                        ['healthy', 'warning', 'error'],
                        weights=[0.8, 0.15, 0.05],
                        k=1
                    )[0]
                    
                    if status != 'healthy':
                        overall_status = status
                    
                    self.record_pipeline_stage(job_id, stage, status, duration)
                
                # Complete the job
                self.complete_pipeline_job(job_id, overall_status)
                
                return jsonify({
                    'status': 'success',
                    'message': 'Pipeline test completed',
                    'job_id': job_id,
                    'overall_status': overall_status
                })
                
            except Exception as e:
                logger.error(f"Pipeline test failed: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'message': f"Pipeline test failed: {str(e)}"
                }), 500
        
        @self.blueprint.route('/diagnostics')
        def diagnostics_page():
            """HTML dashboard with comprehensive system information."""
            try:
                result = self.check_system()
                
                # Ensure all required template variables are present
                system_info = {
                    "uptime": result.get('uptime', 'Unknown'),
                    "platform": result.get('system', {}).get('platform', 'Unknown'),
                    "memory": {
                        "total": result.get('system', {}).get('memory', {}).get('total', 0),
                        "available": result.get('system', {}).get('memory', {}).get('available', 0),
                        "percent": result.get('system', {}).get('memory', {}).get('percent', 0),
                    },
                    "cpu_usage": result.get('system', {}).get('cpu_percent', 0)
                }
                
                # Ensure transactions is a list
                transactions = list(self.transaction_history[:20]) if hasattr(self, 'transaction_history') else []
                
                # Ensure environment vars is a dict
                env_vars = result.get('environment', {})
                
                # Ensure pipeline data is present
                pipeline_status = getattr(self, 'pipeline_status', {"status": "unknown", "message": "No pipeline data"})
                pipeline_stages = getattr(self, 'pipeline_stages', [])
                pipeline_history = list(getattr(self, 'pipeline_history', []))
                
                return render_template('diagnostics.html', 
                                      title="System Diagnostics",
                                      diagnostic=result,
                                      system_status=result['overall_status'],
                                      version=result.get('version', '1.0.0'),
                                      active_connections=len(self.transactions),
                                      uptime=result['uptime'],
                                      timestamp=result['timestamp'],
                                      components=result['components'],
                                      system_info=system_info,
                                      env_vars=env_vars,
                                      transactions=transactions,
                                      pipeline_status=pipeline_status,
                                      pipeline_stages=pipeline_stages,
                                      pipeline_history=pipeline_history)
            except Exception as e:
                logger.error(f"Error rendering diagnostics page: {str(e)}")
                # Fallback to a simple JSON response
                return jsonify({
                    "status": "error",
                    "message": f"Error rendering diagnostics page: {str(e)}",
                    "error_type": type(e).__name__,
                    "timestamp": datetime.now().isoformat()
                }), 500
        
        @self.blueprint.route('/status')
        def status_page():
            """Simple status page with essential health information."""
            result = self.check_system()
            return render_template('status.html', 
                                  status=result['overall_status'],
                                  uptime=result['uptime'],
                                  timestamp=result['timestamp'],
                                  components={
                                      'System': result['system']['platform'],
                                      'Supabase': result['supabase']['status'],
                                      'OpenAI': result['openai']['status'],
                                      'File System': result['file_system']['status']
                                  })

    def increment_error_count(self, error_type, message):
        """Increment the count of errors by type and store recent errors."""
        try:
            self.error_stats['count'] += 1
            
            # Initialize counter for this error type if needed
            if error_type not in self.error_stats['by_type']:
                self.error_stats['by_type'][error_type] = 0
            
            # Increment the counter for this error type
            self.error_stats['by_type'][error_type] += 1
            
            # Add to recent errors list (keep last 20)
            timestamp = datetime.now().isoformat()
            self.error_stats['recent_errors'].append({
                'error_type': error_type,
                'message': message,
                'timestamp': timestamp
            })
            
            # Keep only the 20 most recent errors
            if len(self.error_stats['recent_errors']) > 20:
                self.error_stats['recent_errors'] = self.error_stats['recent_errors'][-20:]
            
            logger.info(f"Error recorded: {error_type} - {message}")
            return True
        except Exception as e:
            logger.error(f"Failed to record error: {str(e)}")
            return False


def create_diagnostic_system():
    """Create and configure a diagnostic system instance."""
    diagnostic = DiagnosticSystem()
    return diagnostic

# Function to be used as a decorator for transaction tracking
def track_transaction(diagnostic_system):
    """Decorator to track Flask request as a transaction."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            transaction_id = request.headers.get('X-Request-ID', f"tx-{datetime.now().timestamp()}")
            diagnostic_system.start_transaction(transaction_id, request.path, request.method)
            
            try:
                response = f(*args, **kwargs)
                status_code = response.status_code if hasattr(response, 'status_code') else 200
                diagnostic_system.complete_transaction(transaction_id, status_code)
                return response
            except Exception as e:
                diagnostic_system.add_transaction_step(transaction_id, 'request_handler', 'error', str(e))
                diagnostic_system.complete_transaction(transaction_id, 500)
                raise
                
        return decorated_function
    return decorator 