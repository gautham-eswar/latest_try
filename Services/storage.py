import os
import logging
from typing import Optional

from Services.database import get_db

# Initialize logger
logger = logging.getLogger(__name__)

def upload_pdf_to_supabase(local_pdf_path: str, user_id: str, enhanced_resume_id: str) -> Optional[str]:
    """
    Uploads a PDF file to Supabase Storage.

    Args:
        local_pdf_path: The local path to the PDF file to upload.
        user_id: The ID of the user.
        enhanced_resume_id: The ID of the enhanced resume.

    Returns:
        The Supabase storage path if upload is successful, None otherwise.
    """
    try:
        db = get_db()
        if db is None:
            logger.error("Failed to get database client for PDF upload.")
            return None

        bucket_name = "resume-pdfs"
        storage_path = f"{user_id}/{enhanced_resume_id}/enhanced_resume_{enhanced_resume_id}.pdf"

        logger.info(f"Attempting to upload {local_pdf_path} to Supabase Storage at path: {storage_path}")

        with open(local_pdf_path, 'rb') as file_obj:
            # Assuming supabase-py v2 style for upsert, or a version that supports boolean True.
            # If an error occurs related to 'upsert', this might need to be "true" (string).
            response = db.storage.from_(bucket_name).upload(
                path=storage_path,
                file=file_obj,
                file_options={"cacheControl": "3600", "upsert": "true"}
            )
        
        # Supabase client typically raises an exception on failure, 
        # but checking response status explicitly can be good for non-exception error cases.
        # For supabase-py version 2.x, a successful upload returns a dict like {'id': '...', 'path': '...', ...}
        # or raises an StorageException.
        # Let's assume if it doesn't raise, it's a success. The actual response content might vary.
        # In supabase-py v1, response.status_code was checked. In v2, it's more about exceptions.

        logger.info(f"Successfully uploaded {local_pdf_path} to Supabase Storage. Path: {storage_path}")
        return storage_path

    except Exception as e:
        # Catching a general exception, but specific Supabase storage exceptions could be caught if known
        # e.g., from supabase.lib.client_options import StorageException (or similar depending on version)
        logger.error(f"Failed to upload {local_pdf_path} to Supabase Storage at {storage_path}: {e}", exc_info=True)
        return None

if __name__ == '__main__':
    # Example Usage (requires Supabase running and configured via get_db)
    # This is for testing purposes and might not run directly in the agent environment
    # without proper Supabase setup and a dummy file.
    
    # Configure basic logging for testing
    logging.basicConfig(level=logging.INFO)
    
    # Create a dummy PDF file for testing
    dummy_pdf_path = "dummy_resume.pdf"
    if not os.path.exists(dummy_pdf_path):
        with open(dummy_pdf_path, "wb") as f:
            f.write(b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\nxref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000059 00000 n\n0000000112 00000 n\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n178\n%%EOF")

    logger.info("Attempting to test PDF upload function...")
    # Replace with actual user_id and enhanced_resume_id for a real test
    test_user_id = "test-user-id"
    test_enhanced_resume_id = "test-enhanced-resume-id"
    
    # Ensure get_db() is configured to connect to your Supabase instance
    # For local testing, you might need to set SUPABASE_URL and SUPABASE_KEY environment variables
    # or have a working database.py setup.
    
    # The test below will likely fail if Supabase is not configured or reachable.
    # It's here for structural illustration.
    try:
        # Check if db can be initialized
        if get_db():
            uploaded_path = upload_pdf_to_supabase(dummy_pdf_path, test_user_id, test_enhanced_resume_id)
            if uploaded_path:
                logger.info(f"Test upload successful. Supabase path: {uploaded_path}")
            else:
                logger.error("Test upload failed.")
        else:
            logger.warning("Supabase client could not be initialized. Skipping upload test.")
            
    except Exception as e:
        logger.error(f"Error during test setup or execution: {e}")
    finally:
        # Clean up dummy file
        if os.path.exists(dummy_pdf_path):
            os.remove(dummy_pdf_path)
            logger.info(f"Cleaned up {dummy_pdf_path}")
