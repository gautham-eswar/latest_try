import os
import requests
import json
from supabase import create_client
from dotenv import load_dotenv
from urllib.parse import urlparse

# Load environment variables from .env file
load_dotenv()

# --- Configuration ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:5000") # Default to Flask's dev server

# --- Helper Functions ---
def get_supabase_client():
    print("\n--- Initializing Supabase Client ---")
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Error: SUPABASE_URL and SUPABASE_KEY must be set in environment variables or .env file.")
        return None
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("Supabase client initialized successfully.")
        return supabase
    except Exception as e:
        print(f"Error initializing Supabase client: {e}")
        return None

def get_test_resume_and_user_id(supabase):
    print("\n--- Fetching Test Resume ID and User ID from Supabase ---")
    try:
        # Fetch the first resume entry to get a valid resume_id and user_id
        # Adjust if you have a specific test entry in mind
        response = supabase.table("resumes").select("id, user_id").limit(1).execute()
        if response.data:
            resume_id = response.data[0].get("id")
            user_id = response.data[0].get("user_id")
            if resume_id and user_id:
                print(f"Found test data: resume_id='{resume_id}', user_id='{user_id}'")
                return str(resume_id), str(user_id)
            else:
                print("Error: Fetched data missing 'id' or 'user_id'.")
                return None, None
        else:
            print("Error: No resumes found in the 'resumes' table to use for testing.")
            print("Please ensure there is at least one resume entry in your Supabase 'resumes' table.")
            return None, None
    except Exception as e:
        print(f"Error fetching test data from Supabase: {e}")
        return None, None

def test_pdf_download_endpoint(resume_id, user_id):
    print(f"\n--- Testing PDF Download Endpoint for resume_id: {resume_id} ---")
    endpoint_url = f"{API_BASE_URL}/api/download/{resume_id}/pdf"
    print(f"Target endpoint: {endpoint_url}")

    try:
        response = requests.get(endpoint_url, timeout=30) # Increased timeout for potentially long PDF generation
        print(f"Response Status Code: {response.status_code}")
        
        response_json = response.json()
        print(f"Response JSON: {json.dumps(response_json, indent=2)}")

        # 1. Verify JSON response structure
        assert "success" in response_json, "Missing 'success' field in response."
        assert response_json["success"] is True, "'success' field is not True."
        assert "resume_id" in response_json, "Missing 'resume_id' field in response."
        assert response_json["resume_id"] == resume_id, f"Returned 'resume_id' ({response_json['resume_id']}) does not match expected ({resume_id})."
        assert "pdf_url" in response_json, "Missing 'pdf_url' field in response."
        
        pdf_url = response_json["pdf_url"]
        print("JSON response structure and basic content verified successfully.")

        # 2. Verify pdf_url path structure
        print(f"\n--- Verifying PDF URL Structure: {pdf_url} ---")
        parsed_url = urlparse(pdf_url)
        expected_path_segment = f"resume-pdfs/{user_id}/{resume_id}/enhanced_resume_{resume_id}.pdf"
        
        # The signed URL path will look like /storage/v1/object/sign/resume-pdfs/...
        # We need to check if our expected segment is part of this path
        assert expected_path_segment in parsed_url.path, \
            f"PDF URL path does not match expected structure.\nExpected segment: '{expected_path_segment}'\nActual path: '{parsed_url.path}'"
        print(f"PDF URL path structure verified successfully: contains '{expected_path_segment}'.")

        # 3. Perform HTTP GET against the signed URL
        print(f"\n--- Testing Signed PDF URL: {pdf_url} ---")
        pdf_response = requests.get(pdf_url, timeout=20)
        print(f"Signed URL GET request Status Code: {pdf_response.status_code}")
        assert pdf_response.status_code == 200, \
            f"Failed to download PDF from signed URL. Status code: {pdf_response.status_code}. Content: {pdf_response.text[:200]}"
        print("Successfully fetched content from signed PDF URL (Status 200 OK).")
        print("PDF content length:", len(pdf_response.content))

        print(f"\n--- Test for resume_id: {resume_id} PASSED ---")

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
        print(f"\n--- Test for resume_id: {resume_id} FAILED ---")
    except AssertionError as e:
        print(f"Assertion Error: {e}")
        print(f"\n--- Test for resume_id: {resume_id} FAILED ---")
    except json.JSONDecodeError:
        print(f"Error: Response is not valid JSON. Response text: {response.text}")
        print(f"\n--- Test for resume_id: {resume_id} FAILED ---")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        print(f"\n--- Test for resume_id: {resume_id} FAILED ---")

# --- Main Execution ---
if __name__ == "__main__":
    print("======== Starting Supabase PDF Integration Test ========")
    
    if not SUPABASE_URL or not SUPABASE_KEY:
        print("Critical Error: SUPABASE_URL and/or SUPABASE_KEY environment variables are not set.")
        print("Please create a .env file or set them in your environment.")
        exit(1)
        
    if not API_BASE_URL:
        print("Warning: API_BASE_URL environment variable not set. Using default: http://localhost:5000")
        # API_BASE_URL is already defaulted, so this is just a user message.

    supabase_client = get_supabase_client()
    if not supabase_client:
        exit(1)

    test_resume_id, test_user_id = get_test_resume_and_user_id(supabase_client)

    if test_resume_id and test_user_id:
        test_pdf_download_endpoint(test_resume_id, test_user_id)
    else:
        print("\nExiting test due to failure to retrieve test data.")
    
    print("\n======== Supabase PDF Integration Test Finished ========") 