
import datetime
import logging
import os
import uuid
from supabase import create_client, Client  # Import Supabase client


# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def get_db() -> Client:
    """Get database client with Supabase priority and fallback."""
    supabase_url = os.environ.get("SUPABASE_URL")
    supabase_key = os.environ.get("SUPABASE_KEY")

    # --- Start Replacement ---
    # --- Start Exact Code ---
    if supabase_url and supabase_key:
        try:
            # Attempt to create a Supabase client
            supabase: Client = create_client(supabase_url, supabase_key)
            logger.info("Supabase client created successfully.")
            # ... (Optional connection test commented out) ...
            return supabase
        except ImportError: # Aligned with try
            logger.warning("Supabase library not installed. Using fallback database.")
            return FallbackDatabase() # Indented  under except
        except Exception as e: # Aligned with try
            logger.error(
                f"Failed to create Supabase client: {str(e)}. Using fallback database.",
                exc_info=True,
            )
            return FallbackDatabase() # Indented under except
    else: # Aligned with if
        logger.warning("SUPABASE_URL or SUPABASE_KEY not set. Using fallback database.")
        return FallbackDatabase() # Indented under else
    

class FallbackDatabase:
    """In-memory fallback database for when the main database is unavailable."""
    
    def __init__(self):
        """Initialize the in-memory database."""
        self.data = {"resumes": {}, "optimizations": {}, "users": {}, "system_logs": []}
        logger.info("Initialized fallback in-memory database")
    
    def insert(self, collection, document):
        """Insert a document into a collection."""
        if collection not in self.data:
            self.data[collection] = {}
        
        # Use document id if provided, otherwise generate one
        doc_id = document.get("id") or str(uuid.uuid4())
        document["id"] = doc_id
        
        # Add timestamp if not present
        if "timestamp" not in document:
            document["timestamp"] = datetime.now().isoformat()
            
        self.data[collection][doc_id] = document
        return doc_id
    
    def find(self, collection, query=None):
        """Find documents in a collection matching a query."""
        if collection not in self.data:
            return []
            
        if query is None:
            return list(self.data[collection].values())
            
        # Simple query matching
        results = []
        for doc in self.data[collection].values():
            match = True
            for k, v in query.items():
                if k not in doc or doc[k] != v:
                    match = False
                    break
            if match:
                results.append(doc)
                
        return results
    
    def get(self, collection, doc_id):
        """Get a specific document by ID."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return None
        return self.data[collection][doc_id]
    
    def update(self, collection, doc_id, updates):
        """Update a document."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return False
            
        doc = self.data[collection][doc_id]
        for k, v in updates.items():
            doc[k] = v
            
        return True
    
    def delete(self, collection, doc_id):
        """Delete a document."""
        if collection not in self.data or doc_id not in self.data[collection]:
            return False
            
        del self.data[collection][doc_id]
        return True
    
    def health_check(self):
        """Perform a basic health check."""
        return {
            "status": "warning",
            "message": "Using fallback in-memory database",
            "tables": list(self.data.keys()),
        }
    
    def table(self, name):
        """Get a table/collection reference for chaining operations."""

        class TableQuery:
            def __init__(self, db, table_name):
                self.db = db
                self.table_name = table_name
                self._columns = "*"
                self._limit_val = None
                
            def select(self, columns="*"):
                self._columns = columns
                return self
                
            def limit(self, n):
                self._limit_val = n
                return self
                
            def execute(self):
                results = self.db.find(self.table_name)
                if self._limit_val:
                    results = results[: self._limit_val]
                return results
                
        return TableQuery(self, name)
