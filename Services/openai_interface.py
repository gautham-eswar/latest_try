

import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests


# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# OpenAI API settings
load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logger.critical(
        "OPENAI_API_KEY environment variable is not set. Cannot proceed without API key."
    )
    sys.exit(1)

OPENAI_API_BASE = "https://api.openai.com/v1"

def call_openai_api(system_prompt, user_prompt, max_retries=3):
    """Call OpenAI API with retry logic and proper error handling."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        logger.critical(
            "OPENAI_API_KEY environment variable is not set. Cannot proceed without API key."
        )
        raise ValueError(
            "OpenAI API key is not configured. Please set the OPENAI_API_KEY environment variable."
        )
    
    base_url = "https://api.openai.com/v1/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.5,
    }
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Making OpenAI API request (attempt {attempt}/{max_retries})")
            response = requests.post(base_url, headers=headers, json=data, timeout=30)
            logger.info(f"OpenAI API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                raise ValueError("Invalid response format from OpenAI API")
            elif response.status_code == 401:
                raise ValueError("OpenAI API key is invalid")
            else:
                logger.error(
                    f"OpenAI API request failed with status {response.status_code}: {response.text}"
                )
                if attempt < max_retries:
                    time.sleep(2**attempt)  # Exponential backoff
                else:
                    raise ValueError(
                        f"OpenAI API request failed after {max_retries} attempts"
                    )
        except requests.exceptions.RequestException as e:
            logger.error(f"OpenAI API request error: {str(e)}")
            if attempt < max_retries:
                time.sleep(2**attempt)
            else:
                raise ValueError(f"OpenAI API request error: {str(e)}")
    
    # This should not be reached due to the raise in the loop, but just in case
    raise ValueError("Failed to get a response from OpenAI API")