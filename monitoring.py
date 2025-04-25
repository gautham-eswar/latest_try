#!/usr/bin/env python3
"""
Monitoring - Production monitoring module for Resume Optimizer API

This module implements comprehensive production monitoring capabilities for the
Resume Optimizer API, including request tracking, system resource monitoring,
component health checking, log analysis, metrics tracking, dashboard generation,
alerting, and custom diagnostic endpoints.
"""

import os
import json
import time
import logging
import datetime
import threading
import traceback
import statistics
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from collections import defaultdict, deque
from functools import wraps

import psutil
from flask import Flask, request, jsonify, g, current_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitoring.log')
    ]
)
logger = logging.getLogger('monitoring')

# Monitoring data storage
class MonitoringData:
    """Centralized storage for monitoring data with thread safety."""
    
    def __init__(self, max_history: int = 1000):
        self.lock = threading.RLock()
        self.max_history = max_history
        
        # Request monitoring
        self.requests = deque(maxlen=max_history)
        self.responses = deque(maxlen=max_history)
        self.errors = deque(maxlen=max_history)
        
        # System resources
        self.system_metrics = deque(maxlen=max_history)
        
        # Component health
        self.health_checks = {}
        self.component_uptime = {}
        
        # Application metrics
        self.processing_times = defaultdict(lambda: deque(maxlen=max_history))
        self.queue_lengths = defaultdict(lambda: deque(maxlen=max_history))
        self.success_rates = defaultdict(lambda: deque(maxlen=max_history))
        
        # Alerts
        self.alerts = deque(maxlen=max_history)
        self.alert_thresholds = {
            'error_rate': 0.05,  # 5% error rate
            'response_time': 1000,  # 1000ms
            'memory_usage': 90,  # 90% memory usage
            'cpu_usage': 90,  # 90% CPU usage
            'disk_usage': 90,  # 90% disk usage
        }
        
        # Start time
        self.start_time = time.time()

# Global monitoring data instance
monitoring_data = MonitoringData()

# Request monitoring
def track_request(request_id: str, method: str, path: str, **kwargs) -> None:
    """Track incoming request details."""
    timestamp = time.time()
    with monitoring_data.lock:
        monitoring_data.requests.append({
            'id': request_id,
            'method': method,
            'path': path,
            'timestamp': timestamp,
            'source_ip': kwargs.get('source_ip'),
            'user_agent': kwargs.get('user_agent'),
            'content_length': kwargs.get('content_length', 0),
        })

def record_response(request_id: str, status: int, response_time: float, **kwargs) -> None:
    """Record response metrics."""
    timestamp = time.time()
    with monitoring_data.lock:
        response_data = {
            'request_id': request_id,
            'status': status,
            'response_time': response_time,
            'timestamp': timestamp,
            'content_length': kwargs.get('content_length', 0),
        }
        monitoring_data.responses.append(response_data)
        
        # Track errors for 4xx and 5xx responses
        if status >= 400:
            monitoring_data.errors.append({
                'request_id': request_id,
                'status': status,
                'error': kwargs.get('error'),
                'timestamp': timestamp,
                'path': kwargs.get('path'),
            })

def calculate_error_rate(timeframe: int = 3600) -> float:
    """Calculate error percentage over the specified timeframe in seconds."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        # Count total responses in timeframe
        total_responses = sum(1 for r in monitoring_data.responses 
                             if r['timestamp'] >= start_time)
        
        # Count error responses in timeframe
        error_responses = sum(1 for r in monitoring_data.responses 
                             if r['timestamp'] >= start_time and r['status'] >= 400)
        
        if total_responses == 0:
            return 0.0
            
        return error_responses / total_responses

def identify_slow_endpoints(timeframe: int = 3600, threshold: float = 500.0) -> List[Dict[str, Any]]:
    """Find performance bottlenecks (endpoints with average response time above threshold)."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        # Group responses by path
        endpoints = defaultdict(list)
        for response in monitoring_data.responses:
            if response['timestamp'] >= start_time:
                request = next((r for r in monitoring_data.requests if r['id'] == response['request_id']), None)
                if request:
                    endpoints[request['path']].append(response['response_time'])
        
        # Calculate average response time for each endpoint
        slow_endpoints = []
        for path, times in endpoints.items():
            avg_time = sum(times) / len(times) if times else 0
            if avg_time > threshold:
                slow_endpoints.append({
                    'path': path,
                    'avg_response_time': avg_time,
                    'request_count': len(times),
                    'max_response_time': max(times) if times else 0,
                })
        
        return sorted(slow_endpoints, key=lambda x: x['avg_response_time'], reverse=True)

# System resource monitoring
def monitor_system_resources() -> Dict[str, Any]:
    """Monitor system resources (CPU, memory, disk, network)."""
    metrics = {
        'timestamp': time.time(),
        'cpu': {
            'percent': psutil.cpu_percent(interval=0.1),
            'count': psutil.cpu_count(),
        },
        'memory': {
            'percent': psutil.virtual_memory().percent,
            'available_mb': psutil.virtual_memory().available / (1024 * 1024),
            'total_mb': psutil.virtual_memory().total / (1024 * 1024),
        },
        'disk': {
            'percent': psutil.disk_usage('/').percent,
            'free_gb': psutil.disk_usage('/').free / (1024 * 1024 * 1024),
            'total_gb': psutil.disk_usage('/').total / (1024 * 1024 * 1024),
        },
        'network': {
            'connections': len(psutil.net_connections()),
        },
        'process': {
            'memory_mb': psutil.Process().memory_info().rss / (1024 * 1024),
            'threads': psutil.Process().num_threads(),
            'open_files': len(psutil.Process().open_files()),
        }
    }
    
    with monitoring_data.lock:
        monitoring_data.system_metrics.append(metrics)
        
    return metrics

# Component health monitoring
def check_component_health(component: str, check_function: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Test specific component health."""
    try:
        start_time = time.time()
        result = check_function()
        response_time = time.time() - start_time
        
        # Default result structure if check_function doesn't provide it
        if not isinstance(result, dict):
            result = {'status': 'healthy' if result else 'unhealthy'}
            
        health_data = {
            'status': result.get('status', 'healthy'),
            'response_time': response_time,
            'timestamp': time.time(),
            'details': result,
        }
        
        with monitoring_data.lock:
            if component not in monitoring_data.health_checks:
                monitoring_data.health_checks[component] = deque(maxlen=monitoring_data.max_history)
                monitoring_data.component_uptime[component] = {
                    'start_time': time.time(),
                    'last_failure': None,
                    'total_downtime': 0,
                    'failure_count': 0,
                }
                
            monitoring_data.health_checks[component].append(health_data)
            
            # Update uptime tracking
            if health_data['status'] != 'healthy' and health_data['status'] != 'degraded':
                monitoring_data.component_uptime[component]['last_failure'] = time.time()
                monitoring_data.component_uptime[component]['failure_count'] += 1
                
        return health_data
    except Exception as e:
        logger.error(f"Health check failed for {component}: {e}")
        error_data = {
            'status': 'error',
            'error': str(e),
            'timestamp': time.time(),
            'traceback': traceback.format_exc(),
        }
        
        with monitoring_data.lock:
            if component not in monitoring_data.health_checks:
                monitoring_data.health_checks[component] = deque(maxlen=monitoring_data.max_history)
                monitoring_data.component_uptime[component] = {
                    'start_time': time.time(),
                    'last_failure': None,
                    'total_downtime': 0,
                    'failure_count': 0,
                }
                
            monitoring_data.health_checks[component].append(error_data)
            monitoring_data.component_uptime[component]['last_failure'] = time.time()
            monitoring_data.component_uptime[component]['failure_count'] += 1
            
        return error_data

def calculate_uptime(component: str) -> Dict[str, Any]:
    """Calculate availability percentage for a component."""
    with monitoring_data.lock:
        if component not in monitoring_data.component_uptime:
            return {
                'uptime_percent': 100.0,
                'status': 'unknown',
                'message': f"No uptime data for component: {component}",
            }
            
        uptime_data = monitoring_data.component_uptime[component]
        total_time = time.time() - uptime_data['start_time']
        
        if total_time <= 0:
            return {
                'uptime_percent': 100.0,
                'status': 'healthy',
                'message': f"Component {component} just started",
            }
            
        downtime = uptime_data['total_downtime']
        uptime_percent = 100.0 * (1 - downtime / total_time)
        
        status = 'healthy'
        if uptime_percent < 99.9:
            status = 'degraded'
        if uptime_percent < 95.0:
            status = 'critical'
            
        return {
            'uptime_percent': uptime_percent,
            'uptime_seconds': total_time - downtime,
            'downtime_seconds': downtime,
            'total_time_seconds': total_time,
            'failure_count': uptime_data['failure_count'],
            'last_failure': uptime_data['last_failure'],
            'status': status,
        }

# Application metrics
def track_processing_time(stage: str, duration: float) -> None:
    """Record pipeline processing metrics."""
    with monitoring_data.lock:
        monitoring_data.processing_times[stage].append({
            'duration': duration,
            'timestamp': time.time(),
        })

def calculate_success_rate(component: str = None, timeframe: int = 3600) -> float:
    """Measure successful operations rate."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        if component:
            if component not in monitoring_data.success_rates:
                return 1.0  # Default to 100% if no data
                
            # Filter by timeframe
            success_data = [
                s for s in monitoring_data.success_rates[component]
                if s['timestamp'] >= start_time
            ]
            
            if not success_data:
                return 1.0
                
            # Calculate success rate
            success_count = sum(1 for s in success_data if s['success'])
            total_count = len(success_data)
            
            return success_count / total_count if total_count > 0 else 1.0
        else:
            # Calculate overall success rate across all components
            all_success_data = []
            for component_data in monitoring_data.success_rates.values():
                all_success_data.extend([
                    s for s in component_data
                    if s['timestamp'] >= start_time
                ])
                
            if not all_success_data:
                return 1.0
                
            # Calculate success rate
            success_count = sum(1 for s in all_success_data if s['success'])
            total_count = len(all_success_data)
            
            return success_count / total_count if total_count > 0 else 1.0

# Alerting
def configure_alert_thresholds(thresholds: Dict[str, Any]) -> None:
    """Set alert trigger points."""
    with monitoring_data.lock:
        monitoring_data.alert_thresholds.update(thresholds)

def detect_alert_conditions() -> List[Dict[str, Any]]:
    """Check for alert conditions."""
    alerts = []
    
    # Check error rate
    error_rate = calculate_error_rate(timeframe=900)  # 15 minutes
    if error_rate > monitoring_data.alert_thresholds['error_rate']:
        alerts.append({
            'type': 'error_rate',
            'severity': 'critical' if error_rate > 0.1 else 'warning',
            'message': f"Error rate is {error_rate:.2%}, threshold is {monitoring_data.alert_thresholds['error_rate']:.2%}",
            'value': error_rate,
            'threshold': monitoring_data.alert_thresholds['error_rate'],
            'timestamp': time.time(),
        })
    
    # Check system resources
    system_metrics = monitor_system_resources()
    
    # Check CPU usage
    cpu_percent = system_metrics['cpu']['percent']
    if cpu_percent > monitoring_data.alert_thresholds['cpu_usage']:
        alerts.append({
            'type': 'cpu_usage',
            'severity': 'critical' if cpu_percent > 95 else 'warning',
            'message': f"CPU usage is {cpu_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['cpu_usage']}%",
            'value': cpu_percent,
            'threshold': monitoring_data.alert_thresholds['cpu_usage'],
            'timestamp': time.time(),
        })
    
    # Check memory usage
    memory_percent = system_metrics['memory']['percent']
    if memory_percent > monitoring_data.alert_thresholds['memory_usage']:
        alerts.append({
            'type': 'memory_usage',
            'severity': 'critical' if memory_percent > 95 else 'warning',
            'message': f"Memory usage is {memory_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['memory_usage']}%",
            'value': memory_percent,
            'threshold': monitoring_data.alert_thresholds['memory_usage'],
            'timestamp': time.time(),
        })
    
    # Check disk usage
    disk_percent = system_metrics['disk']['percent']
    if disk_percent > monitoring_data.alert_thresholds['disk_usage']:
        alerts.append({
            'type': 'disk_usage',
            'severity': 'critical' if disk_percent > 95 else 'warning',
            'message': f"Disk usage is {disk_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['disk_usage']}%",
            'value': disk_percent,
            'threshold': monitoring_data.alert_thresholds['disk_usage'],
            'timestamp': time.time(),
        })
    
    # Record alerts
    with monitoring_data.lock:
        for alert in alerts:
            monitoring_data.alerts.append(alert)
    
    return alerts

def send_alert(alert_type: str, details: Dict[str, Any]) -> bool:
    """Send appropriate alerts based on configuration."""
    # Log the alert
    logger.warning(f"ALERT [{alert_type}]: {details.get('message', '')}")
    
    # In a real implementation, we would send alerts via email, Slack, PagerDuty, etc.
    
    with monitoring_data.lock:
        monitoring_data.alerts.append({
            'type': alert_type,
            'timestamp': time.time(),
            'details': details,
        })
    
    return True

# Flask middleware and integration
def init_app(app: Flask) -> None:
    """Initialize monitoring for a Flask application."""
    # Add request monitoring middleware
    @app.before_request
    def before_request():
        # Start timer
        g.start_time = time.time()
        
        # Track request
        request_id = request.headers.get('X-Request-ID', f"req_{time.time()}_{id(request)}")
        g.request_id = request_id
        
        track_request(
            request_id=request_id,
            method=request.method,
            path=request.path,
            source_ip=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            content_length=request.content_length or 0
        )
    
    @app.after_request
    def after_request(response):
        # Calculate response time
        response_time = (time.time() - g.start_time) * 1000  # in milliseconds
        
        # Record response
        record_response(
            request_id=g.request_id,
            status=response.status_code,
            response_time=response_time,
            content_length=len(response.get_data()) if hasattr(response, 'get_data') else 0,
            path=request.path,
            error=response.json.get('error') if (response.status_code >= 400 and hasattr(response, 'json')) else None
        )
        
        # Add request ID to response headers
        response.headers['X-Request-ID'] = g.request_id
        
        return response
    
    # Add monitoring endpoints
    @app.route('/api/monitoring/health')
    def monitoring_health():
        """System health status endpoint."""
        # Collect health data
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.datetime.now().isoformat(),
            'uptime': time.time() - monitoring_data.start_time,
            'components': {},
        }
        
        # Check component status
        for component, checks in monitoring_data.health_checks.items():
            if not checks:
                health_data['components'][component] = {
                    'status': 'unknown',
                    'message': 'No health checks recorded',
                }
                continue
                
            latest_check = checks[-1]
            health_data['components'][component] = {
                'status': latest_check['status'],
                'last_check': latest_check['timestamp'],
                'response_time': latest_check.get('response_time'),
            }
            
            # If any component is not healthy, update overall status
            if latest_check['status'] == 'critical':
                health_data['status'] = 'critical'
            elif latest_check['status'] != 'healthy' and health_data['status'] != 'critical':
                health_data['status'] = 'degraded'
                
        # Add system metrics
        system_metrics = monitor_system_resources()
        health_data['system'] = {
            'cpu_percent': system_metrics['cpu']['percent'],
            'memory_percent': system_metrics['memory']['percent'],
            'disk_percent': system_metrics['disk']['percent'],
        }
        
        return jsonify(health_data)
    
    @app.route('/api/monitoring/metrics')
    def monitoring_metrics():
        """Performance metrics endpoint."""
        # Collect metrics data
        metrics_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'request_count': len(monitoring_data.requests),
            'error_count': len(monitoring_data.errors),
            'error_rate': calculate_error_rate(),
            'slow_endpoints': identify_slow_endpoints(),
            'system': monitor_system_resources(),
            'processing_times': {},
        }
        
        # Add processing time stats
        for stage, times in monitoring_data.processing_times.items():
            if times:
                durations = [t['duration'] for t in times]
                metrics_data['processing_times'][stage] = {
                    'avg_ms': statistics.mean(durations) if durations else 0,
                    'min_ms': min(durations) if durations else 0,
                    'max_ms': max(durations) if durations else 0,
                    'p95_ms': sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 20 else None,
                    'count': len(durations),
                }
                
        return jsonify(metrics_data)
    
    @app.route('/api/monitoring/errors')
    def monitoring_errors():
        """Recent error information endpoint."""
        # Collect error data
        error_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'error_count': len(monitoring_data.errors),
            'error_rate': calculate_error_rate(),
            'errors': [
                {
                    'request_id': error['request_id'],
                    'status': error['status'],
                    'path': error.get('path', 'unknown'),
                    'timestamp': error['timestamp'],
                    'error': error.get('error'),
                }
                for error in list(monitoring_data.errors)[-50:]  # Last 50 errors
            ],
            'alerts': [
                {
                    'type': alert['type'],
                    'severity': alert.get('severity', 'warning'),
                    'message': alert.get('message'),
                    'timestamp': alert['timestamp'],
                }
                for alert in list(monitoring_data.alerts)[-10:]  # Last 10 alerts
            ],
        }
        
        return jsonify(error_data)
    
    @app.route('/api/monitoring/logs')
    def monitoring_logs():
        """Access to application logs endpoint."""
        log_file = 'app.log'
        lines = request.args.get('lines', 100)
        try:
            lines = int(lines)
        except ValueError:
            lines = 100
            
        # Read log file
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            return jsonify({
                'error': f"Could not read log file: {str(e)}",
                'timestamp': datetime.datetime.now().isoformat(),
            }), 500
            
        return jsonify({
            'timestamp': datetime.datetime.now().isoformat(),
            'log_file': log_file,
            'line_count': len(log_lines),
            'lines': log_lines,
        })
    
    # Add scheduled tasks
    def scheduled_health_checks():
        while True:
            try:
                # Check components
                check_component_health('database', lambda: {'status': 'healthy'})  # Replace with actual DB check
                check_component_health('api', lambda: {'status': 'healthy'})  # Replace with actual API check
                
                # Check for alert conditions
                alerts = detect_alert_conditions()
                for alert in alerts:
                    send_alert(alert['type'], alert)
                    
                # Monitor system resources
                monitor_system_resources()
                
            except Exception as e:
                logger.error(f"Scheduled health check error: {e}")
                
            time.sleep(60)  # Run checks every minute
            
    # Start background thread for health checks
    health_check_thread = threading.Thread(target=scheduled_health_checks, daemon=True)
    health_check_thread.start()
    
    logger.info("Monitoring initialized for Flask application")

# Performance monitoring decorators
def monitor_function(component: str):
    """Decorator to monitor function execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                # Record processing time
                track_processing_time(component, duration * 1000)  # Convert to ms
                
                # Record success/failure
                with monitoring_data.lock:
                    if component not in monitoring_data.success_rates:
                        monitoring_data.success_rates[component] = deque(maxlen=monitoring_data.max_history)
                        
                    monitoring_data.success_rates[component].append({
                        'success': success,
                        'duration': duration,
                        'timestamp': time.time(),
                    })
        return wrapper
    return decorator 
"""
Monitoring - Production monitoring module for Resume Optimizer API

This module implements comprehensive production monitoring capabilities for the
Resume Optimizer API, including request tracking, system resource monitoring,
component health checking, log analysis, metrics tracking, dashboard generation,
alerting, and custom diagnostic endpoints.
"""

import os
import json
import time
import logging
import datetime
import threading
import traceback
import statistics
from typing import Dict, List, Any, Optional, Union, Tuple, Callable
from collections import defaultdict, deque
from functools import wraps

import psutil
from flask import Flask, request, jsonify, g, current_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('monitoring.log')
    ]
)
logger = logging.getLogger('monitoring')

# Monitoring data storage
class MonitoringData:
    """Centralized storage for monitoring data with thread safety."""
    
    def __init__(self, max_history: int = 1000):
        self.lock = threading.RLock()
        self.max_history = max_history
        
        # Request monitoring
        self.requests = deque(maxlen=max_history)
        self.responses = deque(maxlen=max_history)
        self.errors = deque(maxlen=max_history)
        
        # System resources
        self.system_metrics = deque(maxlen=max_history)
        
        # Component health
        self.health_checks = {}
        self.component_uptime = {}
        
        # Application metrics
        self.processing_times = defaultdict(lambda: deque(maxlen=max_history))
        self.queue_lengths = defaultdict(lambda: deque(maxlen=max_history))
        self.success_rates = defaultdict(lambda: deque(maxlen=max_history))
        
        # Alerts
        self.alerts = deque(maxlen=max_history)
        self.alert_thresholds = {
            'error_rate': 0.05,  # 5% error rate
            'response_time': 1000,  # 1000ms
            'memory_usage': 90,  # 90% memory usage
            'cpu_usage': 90,  # 90% CPU usage
            'disk_usage': 90,  # 90% disk usage
        }
        
        # Start time
        self.start_time = time.time()

# Global monitoring data instance
monitoring_data = MonitoringData()

# Request monitoring
def track_request(request_id: str, method: str, path: str, **kwargs) -> None:
    """Track incoming request details."""
    timestamp = time.time()
    with monitoring_data.lock:
        monitoring_data.requests.append({
            'id': request_id,
            'method': method,
            'path': path,
            'timestamp': timestamp,
            'source_ip': kwargs.get('source_ip'),
            'user_agent': kwargs.get('user_agent'),
            'content_length': kwargs.get('content_length', 0),
        })

def record_response(request_id: str, status: int, response_time: float, **kwargs) -> None:
    """Record response metrics."""
    timestamp = time.time()
    with monitoring_data.lock:
        response_data = {
            'request_id': request_id,
            'status': status,
            'response_time': response_time,
            'timestamp': timestamp,
            'content_length': kwargs.get('content_length', 0),
        }
        monitoring_data.responses.append(response_data)
        
        # Track errors for 4xx and 5xx responses
        if status >= 400:
            monitoring_data.errors.append({
                'request_id': request_id,
                'status': status,
                'error': kwargs.get('error'),
                'timestamp': timestamp,
                'path': kwargs.get('path'),
            })

def calculate_error_rate(timeframe: int = 3600) -> float:
    """Calculate error percentage over the specified timeframe in seconds."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        # Count total responses in timeframe
        total_responses = sum(1 for r in monitoring_data.responses 
                             if r['timestamp'] >= start_time)
        
        # Count error responses in timeframe
        error_responses = sum(1 for r in monitoring_data.responses 
                             if r['timestamp'] >= start_time and r['status'] >= 400)
        
        if total_responses == 0:
            return 0.0
            
        return error_responses / total_responses

def identify_slow_endpoints(timeframe: int = 3600, threshold: float = 500.0) -> List[Dict[str, Any]]:
    """Find performance bottlenecks (endpoints with average response time above threshold)."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        # Group responses by path
        endpoints = defaultdict(list)
        for response in monitoring_data.responses:
            if response['timestamp'] >= start_time:
                request = next((r for r in monitoring_data.requests if r['id'] == response['request_id']), None)
                if request:
                    endpoints[request['path']].append(response['response_time'])
        
        # Calculate average response time for each endpoint
        slow_endpoints = []
        for path, times in endpoints.items():
            avg_time = sum(times) / len(times) if times else 0
            if avg_time > threshold:
                slow_endpoints.append({
                    'path': path,
                    'avg_response_time': avg_time,
                    'request_count': len(times),
                    'max_response_time': max(times) if times else 0,
                })
        
        return sorted(slow_endpoints, key=lambda x: x['avg_response_time'], reverse=True)

# System resource monitoring
def monitor_system_resources() -> Dict[str, Any]:
    """Monitor system resources (CPU, memory, disk, network)."""
    metrics = {
        'timestamp': time.time(),
        'cpu': {
            'percent': psutil.cpu_percent(interval=0.1),
            'count': psutil.cpu_count(),
        },
        'memory': {
            'percent': psutil.virtual_memory().percent,
            'available_mb': psutil.virtual_memory().available / (1024 * 1024),
            'total_mb': psutil.virtual_memory().total / (1024 * 1024),
        },
        'disk': {
            'percent': psutil.disk_usage('/').percent,
            'free_gb': psutil.disk_usage('/').free / (1024 * 1024 * 1024),
            'total_gb': psutil.disk_usage('/').total / (1024 * 1024 * 1024),
        },
        'network': {
            'connections': len(psutil.net_connections()),
        },
        'process': {
            'memory_mb': psutil.Process().memory_info().rss / (1024 * 1024),
            'threads': psutil.Process().num_threads(),
            'open_files': len(psutil.Process().open_files()),
        }
    }
    
    with monitoring_data.lock:
        monitoring_data.system_metrics.append(metrics)
        
    return metrics

# Component health monitoring
def check_component_health(component: str, check_function: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    """Test specific component health."""
    try:
        start_time = time.time()
        result = check_function()
        response_time = time.time() - start_time
        
        # Default result structure if check_function doesn't provide it
        if not isinstance(result, dict):
            result = {'status': 'healthy' if result else 'unhealthy'}
            
        health_data = {
            'status': result.get('status', 'healthy'),
            'response_time': response_time,
            'timestamp': time.time(),
            'details': result,
        }
        
        with monitoring_data.lock:
            if component not in monitoring_data.health_checks:
                monitoring_data.health_checks[component] = deque(maxlen=monitoring_data.max_history)
                monitoring_data.component_uptime[component] = {
                    'start_time': time.time(),
                    'last_failure': None,
                    'total_downtime': 0,
                    'failure_count': 0,
                }
                
            monitoring_data.health_checks[component].append(health_data)
            
            # Update uptime tracking
            if health_data['status'] != 'healthy' and health_data['status'] != 'degraded':
                monitoring_data.component_uptime[component]['last_failure'] = time.time()
                monitoring_data.component_uptime[component]['failure_count'] += 1
                
        return health_data
    except Exception as e:
        logger.error(f"Health check failed for {component}: {e}")
        error_data = {
            'status': 'error',
            'error': str(e),
            'timestamp': time.time(),
            'traceback': traceback.format_exc(),
        }
        
        with monitoring_data.lock:
            if component not in monitoring_data.health_checks:
                monitoring_data.health_checks[component] = deque(maxlen=monitoring_data.max_history)
                monitoring_data.component_uptime[component] = {
                    'start_time': time.time(),
                    'last_failure': None,
                    'total_downtime': 0,
                    'failure_count': 0,
                }
                
            monitoring_data.health_checks[component].append(error_data)
            monitoring_data.component_uptime[component]['last_failure'] = time.time()
            monitoring_data.component_uptime[component]['failure_count'] += 1
            
        return error_data

def calculate_uptime(component: str) -> Dict[str, Any]:
    """Calculate availability percentage for a component."""
    with monitoring_data.lock:
        if component not in monitoring_data.component_uptime:
            return {
                'uptime_percent': 100.0,
                'status': 'unknown',
                'message': f"No uptime data for component: {component}",
            }
            
        uptime_data = monitoring_data.component_uptime[component]
        total_time = time.time() - uptime_data['start_time']
        
        if total_time <= 0:
            return {
                'uptime_percent': 100.0,
                'status': 'healthy',
                'message': f"Component {component} just started",
            }
            
        downtime = uptime_data['total_downtime']
        uptime_percent = 100.0 * (1 - downtime / total_time)
        
        status = 'healthy'
        if uptime_percent < 99.9:
            status = 'degraded'
        if uptime_percent < 95.0:
            status = 'critical'
            
        return {
            'uptime_percent': uptime_percent,
            'uptime_seconds': total_time - downtime,
            'downtime_seconds': downtime,
            'total_time_seconds': total_time,
            'failure_count': uptime_data['failure_count'],
            'last_failure': uptime_data['last_failure'],
            'status': status,
        }

# Application metrics
def track_processing_time(stage: str, duration: float) -> None:
    """Record pipeline processing metrics."""
    with monitoring_data.lock:
        monitoring_data.processing_times[stage].append({
            'duration': duration,
            'timestamp': time.time(),
        })

def calculate_success_rate(component: str = None, timeframe: int = 3600) -> float:
    """Measure successful operations rate."""
    now = time.time()
    start_time = now - timeframe
    
    with monitoring_data.lock:
        if component:
            if component not in monitoring_data.success_rates:
                return 1.0  # Default to 100% if no data
                
            # Filter by timeframe
            success_data = [
                s for s in monitoring_data.success_rates[component]
                if s['timestamp'] >= start_time
            ]
            
            if not success_data:
                return 1.0
                
            # Calculate success rate
            success_count = sum(1 for s in success_data if s['success'])
            total_count = len(success_data)
            
            return success_count / total_count if total_count > 0 else 1.0
        else:
            # Calculate overall success rate across all components
            all_success_data = []
            for component_data in monitoring_data.success_rates.values():
                all_success_data.extend([
                    s for s in component_data
                    if s['timestamp'] >= start_time
                ])
                
            if not all_success_data:
                return 1.0
                
            # Calculate success rate
            success_count = sum(1 for s in all_success_data if s['success'])
            total_count = len(all_success_data)
            
            return success_count / total_count if total_count > 0 else 1.0

# Alerting
def configure_alert_thresholds(thresholds: Dict[str, Any]) -> None:
    """Set alert trigger points."""
    with monitoring_data.lock:
        monitoring_data.alert_thresholds.update(thresholds)

def detect_alert_conditions() -> List[Dict[str, Any]]:
    """Check for alert conditions."""
    alerts = []
    
    # Check error rate
    error_rate = calculate_error_rate(timeframe=900)  # 15 minutes
    if error_rate > monitoring_data.alert_thresholds['error_rate']:
        alerts.append({
            'type': 'error_rate',
            'severity': 'critical' if error_rate > 0.1 else 'warning',
            'message': f"Error rate is {error_rate:.2%}, threshold is {monitoring_data.alert_thresholds['error_rate']:.2%}",
            'value': error_rate,
            'threshold': monitoring_data.alert_thresholds['error_rate'],
            'timestamp': time.time(),
        })
    
    # Check system resources
    system_metrics = monitor_system_resources()
    
    # Check CPU usage
    cpu_percent = system_metrics['cpu']['percent']
    if cpu_percent > monitoring_data.alert_thresholds['cpu_usage']:
        alerts.append({
            'type': 'cpu_usage',
            'severity': 'critical' if cpu_percent > 95 else 'warning',
            'message': f"CPU usage is {cpu_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['cpu_usage']}%",
            'value': cpu_percent,
            'threshold': monitoring_data.alert_thresholds['cpu_usage'],
            'timestamp': time.time(),
        })
    
    # Check memory usage
    memory_percent = system_metrics['memory']['percent']
    if memory_percent > monitoring_data.alert_thresholds['memory_usage']:
        alerts.append({
            'type': 'memory_usage',
            'severity': 'critical' if memory_percent > 95 else 'warning',
            'message': f"Memory usage is {memory_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['memory_usage']}%",
            'value': memory_percent,
            'threshold': monitoring_data.alert_thresholds['memory_usage'],
            'timestamp': time.time(),
        })
    
    # Check disk usage
    disk_percent = system_metrics['disk']['percent']
    if disk_percent > monitoring_data.alert_thresholds['disk_usage']:
        alerts.append({
            'type': 'disk_usage',
            'severity': 'critical' if disk_percent > 95 else 'warning',
            'message': f"Disk usage is {disk_percent:.1f}%, threshold is {monitoring_data.alert_thresholds['disk_usage']}%",
            'value': disk_percent,
            'threshold': monitoring_data.alert_thresholds['disk_usage'],
            'timestamp': time.time(),
        })
    
    # Record alerts
    with monitoring_data.lock:
        for alert in alerts:
            monitoring_data.alerts.append(alert)
    
    return alerts

def send_alert(alert_type: str, details: Dict[str, Any]) -> bool:
    """Send appropriate alerts based on configuration."""
    # Log the alert
    logger.warning(f"ALERT [{alert_type}]: {details.get('message', '')}")
    
    # In a real implementation, we would send alerts via email, Slack, PagerDuty, etc.
    
    with monitoring_data.lock:
        monitoring_data.alerts.append({
            'type': alert_type,
            'timestamp': time.time(),
            'details': details,
        })
    
    return True

# Flask middleware and integration
def init_app(app: Flask) -> None:
    """Initialize monitoring for a Flask application."""
    # Add request monitoring middleware
    @app.before_request
    def before_request():
        # Start timer
        g.start_time = time.time()
        
        # Track request
        request_id = request.headers.get('X-Request-ID', f"req_{time.time()}_{id(request)}")
        g.request_id = request_id
        
        track_request(
            request_id=request_id,
            method=request.method,
            path=request.path,
            source_ip=request.remote_addr,
            user_agent=request.user_agent.string if request.user_agent else None,
            content_length=request.content_length or 0
        )
    
    @app.after_request
    def after_request(response):
        # Calculate response time
        response_time = (time.time() - g.start_time) * 1000  # in milliseconds
        
        # Record response
        record_response(
            request_id=g.request_id,
            status=response.status_code,
            response_time=response_time,
            content_length=len(response.get_data()) if hasattr(response, 'get_data') else 0,
            path=request.path,
            error=response.json.get('error') if (response.status_code >= 400 and hasattr(response, 'json')) else None
        )
        
        # Add request ID to response headers
        response.headers['X-Request-ID'] = g.request_id
        
        return response
    
    # Add monitoring endpoints
    @app.route('/api/monitoring/health')
    def monitoring_health():
        """System health status endpoint."""
        # Collect health data
        health_data = {
            'status': 'healthy',
            'timestamp': datetime.datetime.now().isoformat(),
            'uptime': time.time() - monitoring_data.start_time,
            'components': {},
        }
        
        # Check component status
        for component, checks in monitoring_data.health_checks.items():
            if not checks:
                health_data['components'][component] = {
                    'status': 'unknown',
                    'message': 'No health checks recorded',
                }
                continue
                
            latest_check = checks[-1]
            health_data['components'][component] = {
                'status': latest_check['status'],
                'last_check': latest_check['timestamp'],
                'response_time': latest_check.get('response_time'),
            }
            
            # If any component is not healthy, update overall status
            if latest_check['status'] == 'critical':
                health_data['status'] = 'critical'
            elif latest_check['status'] != 'healthy' and health_data['status'] != 'critical':
                health_data['status'] = 'degraded'
                
        # Add system metrics
        system_metrics = monitor_system_resources()
        health_data['system'] = {
            'cpu_percent': system_metrics['cpu']['percent'],
            'memory_percent': system_metrics['memory']['percent'],
            'disk_percent': system_metrics['disk']['percent'],
        }
        
        return jsonify(health_data)
    
    @app.route('/api/monitoring/metrics')
    def monitoring_metrics():
        """Performance metrics endpoint."""
        # Collect metrics data
        metrics_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'request_count': len(monitoring_data.requests),
            'error_count': len(monitoring_data.errors),
            'error_rate': calculate_error_rate(),
            'slow_endpoints': identify_slow_endpoints(),
            'system': monitor_system_resources(),
            'processing_times': {},
        }
        
        # Add processing time stats
        for stage, times in monitoring_data.processing_times.items():
            if times:
                durations = [t['duration'] for t in times]
                metrics_data['processing_times'][stage] = {
                    'avg_ms': statistics.mean(durations) if durations else 0,
                    'min_ms': min(durations) if durations else 0,
                    'max_ms': max(durations) if durations else 0,
                    'p95_ms': sorted(durations)[int(len(durations) * 0.95)] if len(durations) >= 20 else None,
                    'count': len(durations),
                }
                
        return jsonify(metrics_data)
    
    @app.route('/api/monitoring/errors')
    def monitoring_errors():
        """Recent error information endpoint."""
        # Collect error data
        error_data = {
            'timestamp': datetime.datetime.now().isoformat(),
            'error_count': len(monitoring_data.errors),
            'error_rate': calculate_error_rate(),
            'errors': [
                {
                    'request_id': error['request_id'],
                    'status': error['status'],
                    'path': error.get('path', 'unknown'),
                    'timestamp': error['timestamp'],
                    'error': error.get('error'),
                }
                for error in list(monitoring_data.errors)[-50:]  # Last 50 errors
            ],
            'alerts': [
                {
                    'type': alert['type'],
                    'severity': alert.get('severity', 'warning'),
                    'message': alert.get('message'),
                    'timestamp': alert['timestamp'],
                }
                for alert in list(monitoring_data.alerts)[-10:]  # Last 10 alerts
            ],
        }
        
        return jsonify(error_data)
    
    @app.route('/api/monitoring/logs')
    def monitoring_logs():
        """Access to application logs endpoint."""
        log_file = 'app.log'
        lines = request.args.get('lines', 100)
        try:
            lines = int(lines)
        except ValueError:
            lines = 100
            
        # Read log file
        try:
            with open(log_file, 'r') as f:
                all_lines = f.readlines()
                log_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        except Exception as e:
            return jsonify({
                'error': f"Could not read log file: {str(e)}",
                'timestamp': datetime.datetime.now().isoformat(),
            }), 500
            
        return jsonify({
            'timestamp': datetime.datetime.now().isoformat(),
            'log_file': log_file,
            'line_count': len(log_lines),
            'lines': log_lines,
        })
    
    # Add scheduled tasks
    def scheduled_health_checks():
        while True:
            try:
                # Check components
                check_component_health('database', lambda: {'status': 'healthy'})  # Replace with actual DB check
                check_component_health('api', lambda: {'status': 'healthy'})  # Replace with actual API check
                
                # Check for alert conditions
                alerts = detect_alert_conditions()
                for alert in alerts:
                    send_alert(alert['type'], alert)
                    
                # Monitor system resources
                monitor_system_resources()
                
            except Exception as e:
                logger.error(f"Scheduled health check error: {e}")
                
            time.sleep(60)  # Run checks every minute
            
    # Start background thread for health checks
    health_check_thread = threading.Thread(target=scheduled_health_checks, daemon=True)
    health_check_thread.start()
    
    logger.info("Monitoring initialized for Flask application")

# Performance monitoring decorators
def monitor_function(component: str):
    """Decorator to monitor function execution time."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                # Record processing time
                track_processing_time(component, duration * 1000)  # Convert to ms
                
                # Record success/failure
                with monitoring_data.lock:
                    if component not in monitoring_data.success_rates:
                        monitoring_data.success_rates[component] = deque(maxlen=monitoring_data.max_history)
                        
                    monitoring_data.success_rates[component].append({
                        'success': success,
                        'duration': duration,
                        'timestamp': time.time(),
                    })
        return wrapper
    return decorator 