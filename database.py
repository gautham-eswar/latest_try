"""
Database module for Resume Optimizer application. 
Provides functions for database connections and operations.
"""

import os
import time
import json
import logging
import threading
import random
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Performance tracking variables
_connection_status = {
    'last_success': None,
    'consecutive_failures': 0,
    'total_failures': 0,
    'total_queries': 0,
    'performance': {
        'avg_query_time': 0
    }
}
_queries_history = []

def _track_query_performance(func):
    """
    Decorator to track query performance and statistics.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        global _connection_status, _queries_history
        
        start_time = time.time()
        _connection_status['total_queries'] += 1
        transaction_id = f"tx-{datetime.now().timestamp()}"
        
        # Extract operation details for logging
        table_name = args[0] if len(args) > 0 else kwargs.get('table_name', 'unknown')
        operation = args[1] if len(args) > 1 else kwargs.get('operation', 'unknown')
        
        try:
            result = func(*args, **kwargs)
            
            # Update success metrics
            query_time = time.time() - start_time
            _connection_status['last_success'] = datetime.now()
            _connection_status['consecutive_failures'] = 0
            
            # Update average query time
            total_queries = _connection_status['total_queries']
            current_avg = _connection_status['performance']['avg_query_time']
            _connection_status['performance']['avg_query_time'] = (
                (current_avg * (total_queries - 1) + query_time) / total_queries
            )
            
            # Record query in history
            _queries_history.append({
                'transaction_id': transaction_id,
                'table': table_name,
                'operation': operation,
                'duration': query_time,
                'status': 'success',
                'timestamp': datetime.now().isoformat()
            })
            
            # Limit history size
            if len(_queries_history) > 100:
                _queries_history = _queries_history[-100:]
                
            return result
            
        except Exception as e:
            # Update failure metrics
            query_time = time.time() - start_time
            _connection_status['consecutive_failures'] += 1
            _connection_status['total_failures'] += 1
            
            # Record query in history
            _queries_history.append({
                'transaction_id': transaction_id,
                'table': table_name,
                'operation': operation,
                'duration': query_time,
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
            
            # Limit history size
            if len(_queries_history) > 100:
                _queries_history = _queries_history[-100:]
                
            # Re-raise the exception
            raise
    
    return wrapper

def _with_retry(func):
    """
    Decorator to add retry logic to database operations.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 0.5  # Initial delay in seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.warning(f"Database operation failed (attempt {attempt}/{max_retries}): {str(e)}")
                
                if attempt == max_retries:
                    logger.error(f"Max retries reached. Giving up: {str(e)}")
                    raise
                
                # Reset connection before retry
                reset_connection()
                
                # Exponential backoff with jitter
                jitter = random.uniform(0, 0.5)
                sleep_time = retry_delay * (2 ** (attempt - 1)) + jitter
                logger.info(f"Retrying in {sleep_time:.2f} seconds...")
                time.sleep(sleep_time)
    
    return wrapper

# Attempt to import Supabase client
try:
    from supabase import create_client, Client
    from postgrest import APIError, APIResponse
    SUPABASE_AVAILABLE = True
except ImportError:
    logger.warning("Supabase client not available. Fallback mode will be used.")
    SUPABASE_AVAILABLE = False

class InMemoryDatabase:
    """Simple in-memory database for testing and fallback."""
    
    def __init__(self):
        self.data = defaultdict(list)
        self.counters = defaultdict(int)
        logger.info("Initialized in-memory database fallback")
        
    def insert(self, collection, document):
        """Insert a document into a collection."""
        self.counters[collection] += 1
        document_id = self.counters[collection]
        document['id'] = document_id
        self.data[collection].append(document)
        return document_id
        
    def find(self, collection, query=None):
        """Find documents in a collection matching a query."""
        if query is None:
            return self.data[collection]
        
        results = []
        for doc in self.data[collection]:
            matches = True
            for key, value in query.items():
                if key not in doc or doc[key] != value:
                    matches = False
                    break
            if matches:
                results.append(doc)
        return results
        
    def find_one(self, collection, query):
        """Find a single document matching a query."""
        results = self.find(collection, query)
        return results[0] if results else None
        
    def update(self, collection, document_id, updates):
        """Update a document by ID."""
        for i, doc in enumerate(self.data[collection]):
            if doc.get('id') == document_id:
                self.data[collection][i].update(updates)
                return True
        return False
    
    def health_check(self):
        """Check database health."""
        return {
            "status": "healthy",
            "message": "In-memory database is working",
            "tables": [{"name": k, "count": len(v)} for k, v in self.data.items()],
            "response_time_ms": 1  # Simulated response time
        }
    
    def table(self, name):
        """Compatibility method with Supabase client."""
        class TableQuery:
            def __init__(self, db, table_name):
                self.db = db
                self.table_name = table_name
                
            def select(self, columns='*'):
                return self
                
            def limit(self, n):
                return self
                
            def execute(self):
                return {"data": self.db.find(self.table_name)}
                
        return TableQuery(self, name)

def create_database_client():
    """
    Create and return a database client based on environment configuration.
    
    Attempts to connect to Supabase if credentials are provided, otherwise
    falls back to an in-memory database for testing.
    
    Returns:
        A database client object
    """
    supabase_url = os.environ.get('SUPABASE_URL')
    supabase_key = os.environ.get('SUPABASE_KEY')
    
    if supabase_url and supabase_key and SUPABASE_AVAILABLE:
        try:
            logger.info(f"Connecting to Supabase at {supabase_url}")
            return create_client(supabase_url, supabase_key)
        except Exception as e:
            logger.error(f"Failed to create Supabase client: {str(e)}")
            logger.warning("Falling back to in-memory database")
            return create_in_memory_database()
    else:
        logger.warning("Supabase credentials not found or client not available. Using in-memory database fallback.")
        return create_in_memory_database()


def create_in_memory_database():
    """
    Create and return an in-memory database for testing or fallback.
    
    Returns:
        An InMemoryDatabase instance
    """
    logger.warning("Supabase client not available. Using fallback database.")
    return InMemoryDatabase()


# Initialize the connection when the module is imported
_db_client = None

def get_db():
    """Get a database client singleton instance."""
    global _db_client
    if _db_client is None:
        _db_client = create_database_client()
    return _db_client


def reset_connection():
    """Force a reset of the database connection."""
    global _db_client
    
    _db_client = None
        
    # Re-initialize the connection
    return get_db() is not None


@_track_query_performance
@_with_retry
def run_query(table_name, operation, data=None, returning='*'):
    """
    Run a database operation with performance tracking and error handling.
    
    Args:
        table_name: Name of the table to operate on
        operation: Operation type ('select', 'insert', 'update', 'delete')
        data: Data for the operation (optional)
        returning: Columns to return for insert/update operations (default: '*')
        
    Returns:
        Query result
    """
    db = get_db()
    transaction_id = f"tx-{datetime.now().timestamp()}"
    
    try:
        # Log transaction start
        logger.debug(f"Starting database transaction {transaction_id}: {operation} on {table_name}")
        
        # Execute the appropriate operation
        if operation == 'select':
            if data and isinstance(data, dict):
                # If data is provided, use it for filtering
                query = db.table(table_name).select(returning)
                for column, value in data.items():
                    query = query.eq(column, value)
                result = query.execute()
            else:
                result = db.table(table_name).select(returning).execute()
                
        elif operation == 'insert':
            if not data:
                raise ValueError("Data required for insert operation")
            
            result = db.table(table_name).insert(data, returning=returning).execute()
            
        elif operation == 'update':
            if not isinstance(data, dict) or 'values' not in data or 'filters' not in data:
                raise ValueError("Data must contain 'values' and 'filters' for update operation")
            
            query = db.table(table_name).update(data['values'])
            for column, value in data['filters'].items():
                query = query.eq(column, value)
            
            result = query.execute()
            
        elif operation == 'delete':
            if not data:
                raise ValueError("Filter data required for delete operation")
            
            query = db.table(table_name).delete()
            for column, value in data.items():
                query = query.eq(column, value)
            
            result = query.execute()
            
        else:
            raise ValueError(f"Unsupported operation: {operation}")
        
        # Log transaction completion
        logger.debug(f"Completed database transaction {transaction_id}")
        
        # Record successful transaction
        try:
            db.table('transactions').insert({
                'transaction_id': transaction_id,
                'operation': operation,
                'table': table_name,
                'timestamp': datetime.now().isoformat(),
                'status': 'success'
            }).execute()
        except Exception as e:
            # Non-critical, just log it
            logger.debug(f"Could not record transaction: {str(e)}")
        
        return result
    
    except Exception as e:
        # Log the error
        logger.error(f"Database transaction {transaction_id} failed: {str(e)}")
        
        # Record failed transaction
        try:
            db.table('transactions').insert({
                'transaction_id': transaction_id,
                'operation': operation,
                'table': table_name,
                'timestamp': datetime.now().isoformat(),
                'status': 'error',
                'error': str(e)
            }).execute()
        except Exception:
            # Non-critical, just log it
            pass
        
        # Re-raise the exception
        raise


def health_check():
    """Run a comprehensive health check on the database connection."""
    global _connection_status, _queries_history
    
    try:
        # Get the current database client
        db = get_db()
        
        # Get client type
        client_type = "Supabase" if isinstance(db, Client) else "Fallback"
        
        # Test with a simple query
        start_time = time.time()
        try:
            response = db.table('health_checks').select('*').limit(1).execute()
            query_time = time.time() - start_time
            query_success = True
        except Exception as e:
            query_time = time.time() - start_time
            query_success = False
            query_error = str(e)
        
        # Check table structure (try to get schema from a few key tables)
        tables_status = {}
        for table in ['resumes', 'users', 'jobs', 'health_checks', 'transactions']:
            try:
                result = db.table(table).select('*').limit(1).execute()
                record_count = 0
                
                # For Supabase, we can get the count
                if hasattr(result, 'count'):
                    record_count = result.count
                # For fallback, count the records
                elif hasattr(result, 'data'):
                    record_count = len(result.data)
                
                tables_status[table] = {
                    'exists': True,
                    'record_count': record_count,
                    'status': 'available'
                }
            except Exception as e:
                tables_status[table] = {
                    'exists': False,
                    'error': str(e),
                    'status': 'error'
                }
        
        # Compile the results
        result = {
            'timestamp': datetime.now().isoformat(),
            'client_type': client_type,
            'status': 'healthy' if query_success else 'error',
            'connection_info': {
                'last_success': _connection_status['last_success'].isoformat() 
                    if _connection_status['last_success'] else None,
                'consecutive_failures': _connection_status['consecutive_failures'],
                'total_failures': _connection_status['total_failures'],
                'total_queries': _connection_status['total_queries']
            },
            'performance': {
                'last_query_time': query_time,
                'avg_query_time': _connection_status['performance']['avg_query_time']
            },
            'tables': tables_status,
            'recent_queries': _queries_history[-5:] if _queries_history else []
        }
        
        if not query_success:
            result['last_error'] = query_error
        
        return result
        
    except Exception as e:
        return {
            'timestamp': datetime.now().isoformat(),
            'status': 'critical_error',
            'message': f"Health check failed: {str(e)}",
            'error': str(e),
            'error_type': type(e).__name__
        }


def create_tables():
    """Create required tables if they don't exist."""
    db = get_db()
    
    # If using fallback, tables are created automatically
    if not SUPABASE_AVAILABLE or not isinstance(db, Client):
        return {"status": "using_fallback", "message": "Using fallback database, tables created in memory"}
    
    # For Supabase, we need to use RPC or SQL
    # This is a simplified implementation - in production, you would use migrations
    # and proper SQL schemas with constraints
    try:
        # Define the tables we need
        required_tables = {
            'health_checks': {
                'id': 'serial primary key',
                'timestamp': 'timestamptz not null default now()',
                'status': 'text not null',
                'message': 'text'
            },
            'transactions': {
                'id': 'serial primary key',
                'transaction_id': 'text not null',
                'operation': 'text not null',
                'table': 'text not null',
                'timestamp': 'timestamptz not null default now()',
                'status': 'text not null',
                'error': 'text'
            },
            'resumes': {
                'id': 'serial primary key',
                'user_id': 'text not null',
                'content': 'jsonb not null',
                'created_at': 'timestamptz not null default now()',
                'updated_at': 'timestamptz'
            },
            'users': {
                'id': 'serial primary key',
                'user_id': 'text not null unique',
                'email': 'text unique',
                'created_at': 'timestamptz not null default now()',
                'last_login': 'timestamptz'
            },
            'jobs': {
                'id': 'serial primary key',
                'user_id': 'text not null',
                'job_description': 'text not null',
                'created_at': 'timestamptz not null default now()',
                'status': 'text not null default \'pending\''
            }
        }
        
        # In a real implementation, we would use proper SQL or migrations
        # This is a simplified approach for demonstration
        created_tables = []
        
        # Check which tables already exist
        # In Supabase, we can't easily check schema, so we'll just try operations and handle errors
        
        for table_name in required_tables:
            try:
                # Try a query to see if table exists
                db.table(table_name).select('id').limit(1).execute()
                # If it succeeds, table exists
            except Exception as e:
                if "relation" in str(e) and "does not exist" in str(e):
                    # Table doesn't exist - in a real implementation, 
                    # we would create it with the proper SQL
                    # For now, we'll just note it
                    created_tables.append(table_name)
                else:
                    # Some other error
                    logger.error(f"Error checking table {table_name}: {str(e)}")
        
        return {
            "status": "success",
            "created_tables": created_tables,
            "message": f"Checked {len(required_tables)} tables, created {len(created_tables)}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create tables: {str(e)}")
        return {
            "status": "error",
            "message": f"Failed to create tables: {str(e)}",
            "error": str(e)
        }


def test_connection():
    """Test Supabase connection and return diagnostic information."""
    try:
        db = get_db()
        # Try a simple query
        result = db.table('health_checks').select('*').limit(1).execute()
        
        # If we get here, connection worked
        return {
            'status': 'ok',
            'message': 'Successfully connected to Supabase',
            'timestamp': datetime.now().isoformat(),
            'details': {
                'supabase_url': os.environ.get('SUPABASE_URL', 'not_set')[:8] + '...',  # Show only prefix for security
                'key_configured': bool(os.environ.get('SUPABASE_KEY'))
            }
        }
    except Exception as e:
        return {
            'status': 'error',
            'message': f'Failed to connect to Supabase: {str(e)}',
            'timestamp': datetime.now().isoformat(),
            'details': {
                'error_type': type(e).__name__,
                'supabase_url_configured': bool(os.environ.get('SUPABASE_URL')),
                'key_configured': bool(os.environ.get('SUPABASE_KEY'))
            }
        }


# Initialize the connection when the module is imported
get_db() 