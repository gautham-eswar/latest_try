import requests
import json

# Try the health endpoint first
print("Testing health endpoint...")
try:
    response = requests.get("http://localhost:5001/api/health", timeout=10)
    print(f"Health endpoint response: {response.status_code}")
    print(response.text)
except Exception as e:
    print(f"Error testing health endpoint: {e}")

# Now try the PDF download endpoint with a fake resume ID
print("\nTesting PDF download endpoint...")
try:
    fake_resume_id = "test_resume_id"
    response = requests.get(f"http://localhost:5001/api/download/{fake_resume_id}/pdf", timeout=10)
    print(f"PDF download endpoint response: {response.status_code}")
    print(response.text)
except Exception as e:
    print(f"Error testing PDF download endpoint: {e}") 