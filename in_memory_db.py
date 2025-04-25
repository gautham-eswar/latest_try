"""
In-memory database module for Resume Optimizer application.
Provides fallback storage when Supabase is unavailable.
"""

import logging
import time
from datetime import datetime
from collections import defaultdict, OrderedDict
import uuid
import threading
from typing import Dict, List, Any, Optional, Union

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class InMemoryDatabase:
    """Simple in-memory database for testing and fallback."""
    
    def __init__(self, app=None):
        self.data = defaultdict(list)
        self.id_maps = defaultdict(dict)  # Maps IDs to indices in data lists
        self.locks = defaultdict(threading.RLock)
        self.app = app
        logger.info("In-memory database initialized")
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app context."""
        self.app = app
        app.extensions = getattr(app, 'extensions', {})
        app.extensions['in_memory_db'] = self
        logger.info("Initialized in-memory database with Flask app")
        
    def insert(self, collection: str, document: Dict[str, Any]) -> str:
        """Insert a document into a collection and return its ID."""
        with self.locks[collection]:
            # Generate ID if not provided
            if 'id' not in document:
                document['id'] = f"{collection}_{int(time.time())}_{uuid.uuid4().hex[:8]}"
            
            # Add timestamps
            if 'created_at' not in document:
                document['created_at'] = datetime.now().isoformat()
            
            document['updated_at'] = datetime.now().isoformat()
            
            # Store document
            self.data[collection].append(document.copy())
            idx = len(self.data[collection]) - 1
            self.id_maps[collection][document['id']] = idx
            
            return document['id']
        
    def find(self, collection: str, query: Optional[Dict] = None) -> List[Dict]:
        """Find documents in a collection matching a query."""
        with self.locks[collection]:
            if collection not in self.data:
                return []
                
            if query is None:
                return self.data[collection].copy()
            
            results = []
            for doc in self.data[collection]:
                if self._matches_query(doc, query):
                    results.append(doc.copy())
            
            return results
        
    def find_one(self, collection: str, query: Dict) -> Optional[Dict]:
        """Find a single document matching a query."""
        with self.locks[collection]:
            if 'id' in query and query['id'] in self.id_maps[collection]:
                # Fast path for ID lookups
                idx = self.id_maps[collection][query['id']]
                return self.data[collection][idx].copy()
            
            # Slower path for other queries
            for doc in self.data[collection]:
                if self._matches_query(doc, query):
                    return doc.copy()
            
            return None
        
    def update(self, collection: str, document_id: str, updates: Dict) -> bool:
        """Update a document by ID."""
        with self.locks[collection]:
            if document_id not in self.id_maps[collection]:
                return False
                
            idx = self.id_maps[collection][document_id]
            
            # Update document
            updates['updated_at'] = datetime.now().isoformat()
            self.data[collection][idx].update(updates)
            
            return True
    
    def delete(self, collection: str, document_id: str) -> bool:
        """Delete a document by ID."""
        with self.locks[collection]:
            if document_id not in self.id_maps[collection]:
                return False
                
            idx = self.id_maps[collection][document_id]
            
            # Remove document
            del self.data[collection][idx]
            del self.id_maps[collection][document_id]
            
            # Rebuild id_maps for this collection since indices changed
            self.id_maps[collection] = {
                doc['id']: i for i, doc in enumerate(self.data[collection])
            }
            
            return True
    
    def health_check(self) -> Dict:
        """Check database health."""
        return {
            "status": "healthy",
            "message": "In-memory database is working",
            "tables": [{"name": k, "count": len(v)} for k, v in self.data.items()],
            "response_time_ms": 1  # Simulated response time
        }
    
    def _matches_query(self, document: Dict, query: Dict) -> bool:
        """Check if document matches query conditions."""
        for key, value in query.items():
            # Handle dot notation for nested fields
            if '.' in key:
                parts = key.split('.')
                current = document
                for part in parts[:-1]:
                    if part not in current:
                        return False
                    current = current[part]
                
                if parts[-1] not in current or current[parts[-1]] != value:
                    return False
            
            # Handle simple field matching
            elif key not in document or document[key] != value:
                return False
        
        return True

# Global in-memory database instance
_db_instance = None

def get_db(app=None):
    """Get or create the in-memory database instance."""
    global _db_instance
    
    if _db_instance is None:
        _db_instance = InMemoryDatabase(app)
    
    return _db_instance

def create_in_memory_database(app=None):
    """Create and initialize in-memory database."""
    return get_db(app) 