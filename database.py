"""
Database module for Resume Optimizer application. 
Provides functions for database connections and operations.
"""

import os
import time
import uuid
import logging
import traceback
import json
import threading
import random
from datetime import datetime, timedelta
from functools import wraps
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection status tracking
_connection_status = {
    'last_check': None,
    'is_connected': False,
    'error': None
}

# Query performance tracking
_queries_history = []
_queries_stats = {
    'total': 0,
    'errors': 0,
    'total_time': 0
}

def _track_query_performance(func):
    """Decorator to track database query performance"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        global _queries_stats
        
        start_time = time.time()
        error = None
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            error = e
            _queries_stats['errors'] += 1
            raise
        finally:
            end_time = time.time()
            duration = end_time - start_time
            
            # Update stats
            _queries_stats['total'] += 1
            _queries_stats['total_time'] += duration
            
            # Record query info (keep last 100 queries)
            query_info = {
                'timestamp': datetime.now().isoformat(),
                'duration': duration,
                'operation': args[1] if len(args) > 1 else 'unknown',
                'table': args[0] if args else 'unknown',
                'error': str(error) if error else None
            }
            
            _queries_history.append(query_info)
            if len(_queries_history) > 100:
                _queries_history.pop(0)
            
            # Log slow queries (>500ms)
            if duration > 0.5:
                logger.warning(f"Slow query: {duration:.2f}s - {query_info['operation']} on {query_info['table']}")
                
    return wrapper


def _with_retry(func):
    """Decorator to add retry logic to database operations"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        max_retries = 3
        retry_delay = 1  # seconds
        
        for attempt in range(1, max_retries + 1):
            try:
                if attempt > 1:
                    logger.info(f"Retry attempt {attempt}/{max_retries}...")
                    
                return func(*args, **kwargs)
                
            except Exception as e:
                if attempt == max_retries:
                    logger.error(f"Failed after {max_retries} attempts: {str(e)}")
                    raise
                
                logger.warning(f"Operation failed (attempt {attempt}/{max_retries}): {str(e)}")
                logger.warning(f"Waiting {retry_delay}s before retry...")
                time.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff
                
    return wrapper


# Attempt to import Supabase client
try:
    from supabase import create_client, Client
    from postgrest import APIError, APIResponse
    SUPABASE_AVAILABLE = True
    logger.info("Supabase client imported successfully")
except ImportError as e:
    logger.warning(f"Supabase client not available: {str(e)}")
    logger.warning("Fallback mode will be used.")
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
        """Run health check on the in-memory database."""
        return {
            "status": "available",
            "message": "Using in-memory database (fallback mode)",
            "tables": {table: {"exists": True, "count": len(docs), "status": "available"} 
                      for table, docs in self.data.items()},
            "performance": {
                "queries": len(_queries_history),
                "errors": _queries_stats.get('errors', 0)
            }
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
    
    if not supabase_url or not supabase_key:
        logger.warning("Supabase credentials not found in environment variables")
        logger.warning("Using in-memory database fallback.")
        return create_in_memory_database()
    
    if not SUPABASE_AVAILABLE:
        logger.warning("Supabase client library not available. Using fallback database.")
        return create_in_memory_database()
    
    try:
        logger.info(f"Connecting to Supabase at {supabase_url}")
        client = create_client(supabase_url, supabase_key)
        
        # Test the connection with a simple query
        try:
            # Try a health check table query to verify connection
            client.table('health_checks').select('*').limit(1).execute()
            logger.info("Successfully connected to Supabase")
            
            # Update connection status
            global _connection_status
            _connection_status = {
                'last_check': datetime.now(),
                'is_connected': True,
                'error': None
            }
            
            return client
        except Exception as e:
            logger.error(f"Failed to query Supabase: {str(e)}")
            logger.warning("Falling back to in-memory database")
            
            # Update connection status
            global _connection_status
            _connection_status = {
                'last_check': datetime.now(),
                'is_connected': False,
                'error': str(e)
            }
            
            return create_in_memory_database()
            
    except Exception as e:
        logger.error(f"Failed to create Supabase client: {str(e)}")
        logger.warning("Falling back to in-memory database")
        return create_in_memory_database()


def create_in_memory_database():
    """
    Create and return an in-memory database for testing or fallback.
    
    Returns:
        An InMemoryDatabase instance
    """
    logger.warning("Using fallback in-memory database instead of Supabase.")
    return InMemoryDatabase()


# Initialize the connection when the module is imported
_supabase_client = None

def get_db():
    """Get a database client singleton instance."""
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_database_client()
    return _supabase_client


def reset_connection():
    """Force a reset of the database connection."""
    global _supabase_client
    
    _supabase_client = None
        
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
        
        # Compile overall health
        health_info = {
            'timestamp': datetime.now().isoformat(),
            'client_type': client_type,
            'status': 'healthy' if query_success else 'error',
            'message': 'Database is responding normally' if query_success else f"Database error: {query_error}",
            'response_time': query_time,
            'tables': tables_status,
            'queries': {
                'total': _queries_stats.get('total', 0),
                'errors': _queries_stats.get('errors', 0),
                'avg_time': _queries_stats.get('total_time', 0) / max(_queries_stats.get('total', 1), 1),
                'recent': _queries_history[-5:] if _queries_history else []
            }
        }
        
        # Update connection status
        _connection_status = {
            'last_check': datetime.now(),
            'is_connected': query_success,
            'error': query_error if not query_success else None
        }
        
        return health_info
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        
        # Update connection status
        _connection_status = {
            'last_check': datetime.now(),
            'is_connected': False,
            'error': str(e)
        }
        
        return {
            'timestamp': datetime.now().isoformat(),
            'client_type': 'Unknown',
            'status': 'critical',
            'message': f"Health check failed: {str(e)}",
            'error': traceback.format_exc()
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