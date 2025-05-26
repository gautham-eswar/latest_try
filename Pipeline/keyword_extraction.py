import json
import logging
import re
from typing import Any, Dict, Optional
import os # For OPENAI_API_KEY and prompt path
import asyncio
import httpx

try:
    from openai import OpenAI
except ImportError:
    raise ImportError("OpenAI Python package is required. Install with: pip install openai")


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Define constants for model and max tokens
OPENAI_MODEL = "gpt-4.1-mini"  # Updated model to gpt-4.1-mini
KEYWORD_EXTRACTION_MAX_TOKENS = 2000 # Retained from original, adjust if needed for new model

async def extract_keywords(
    job_description_text: str, 
    api_key: Optional[str] = None,
    model: str = OPENAI_MODEL,
    max_tokens_response: int = KEYWORD_EXTRACTION_MAX_TOKENS
) -> Dict[str, Any]:
    """
    Extract detailed keywords from job description using OpenAI asynchronously,
    attempting to get context, relevance, and skill type.
    Includes validation for non-JSON responses and fallback logic
    to repair slightly malformed JSON responses.
    Returns a dictionary structured for SemanticMatcher.
    """
    logger.info(f"Extracting keywords for JD: '{job_description_text[:40]}...' using model {model}")
    if not job_description_text or len(job_description_text) < 20:
        logger.warning("Job description text is too short or empty. Skipping OpenAI call.")
        return {"keywords": []}

    used_api_key = api_key or os.environ.get('OPENAI_API_KEY')
    if not used_api_key:
        logger.error("OpenAI API key not provided or found in environment variables.")
        raise ValueError("OpenAI API key is required")

    # System prompt content (can be loaded from a file or defined here)
    system_prompt_content = """
    You are an expert HR analyst specializing in extracting structured keywords from job descriptions.
    Focus on identifying distinct skills (hard and soft), experiences, tools, qualifications, and responsibilities.
    Ensure your output is a valid JSON object with a single key "keywords", which is a list of objects.
    Each object in the "keywords" list must have the following keys: "keyword" (string), "context" (string), "relevance_score" (float, 0.0 to 1.0), and "skill_type" (string, e.g., "hard skill", "soft skill", "experience").
    If the job description is too short, vague, or completely irrelevant for keyword extraction (e.g., just "test"), return {"keywords": []}.
    """
    
    # Load user prompt template
    prompt_template_path = os.path.join(os.path.dirname(__file__), "prompts", "extract_keywords.txt")
    try:
        with open(prompt_template_path, "r", encoding="utf-8") as file:
            user_prompt_template = file.read()
    except FileNotFoundError:
        logger.error(f"Keyword extraction prompt template not found at {prompt_template_path}")
        raise RuntimeError(f"Keyword extraction prompt template not found at {prompt_template_path}")

    user_prompt = user_prompt_template.replace("@job_description_txt", job_description_text)

    logger.info(f"Sending JD to OpenAI (async): {job_description_text[:40]}... using model {model}")
    
    raw_response_content = "" 

    try:
        async with httpx.AsyncClient(trust_env=False) as httpx_async_client:
            client = OpenAI(api_key=used_api_key, http_client=httpx_async_client)
            
            response = await client.chat.completions.create(
                model=model, # Uses OPENAI_MODEL by default due to function signature
                response_format={"type": "json_object"}, 
                messages=[
                    {"role": "system", "content": system_prompt_content},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2, # For more deterministic output
                max_tokens=max_tokens_response
            )
            raw_response_content = response.choices[0].message.content
            if raw_response_content is None:
                 logger.error("OpenAI returned an empty response for keyword extraction.")
                 raise ValueError("OpenAI returned an empty response.")
                 
    except Exception as e:
        logger.error(f"OpenAI API call failed during keyword extraction: {e}", exc_info=True)
        raise RuntimeError(f"OpenAI API call failed: {e}") from e

    raw_result_stripped = raw_response_content.strip()
    # The following JSON parsing and repair logic is adapted from the original synchronous version.
    # It will operate on raw_result_stripped (derived from raw_response_content).

    if not raw_result_stripped.startswith('{'):
        logger.error(f"OpenAI did not return JSON format. Response: {raw_result_stripped[:500]}...")
        raise ValueError(f"OpenAI returned non-JSON response: {raw_result_stripped[:200]}...")

    logger.info(f"Raw keyword extraction result from OpenAI (Passed initial '{{' check'): {raw_response_content[:500]}...")
    
    structured_data_str = raw_result_stripped # Default if no markdown
    # Attempt to extract JSON block if present (e.g., within markdown)
    # Using raw_response_content for regex search as it contains the original full response
    json_match = re.search(
        r"```(?:json)?\s*({.*?})\s*```", raw_response_content, re.DOTALL | re.IGNORECASE
    )
    if json_match:
        structured_data_str = json_match.group(1)
        logger.info("Extracted JSON object from within markdown block.")
    elif not raw_result_stripped.endswith('}'):
        # If it starts with { but isn't wrapped and doesn't end with }, it's likely incomplete/malformed
        logger.warning("Response starts with '{' but not clearly identifiable as complete JSON object or markdown block. Proceeding to parsing/repair attempt.")
        # structured_data_str is already raw_result_stripped which will be used in repair
    else: # Starts with { and ends with }
        logger.info("Using raw API response as JSON object (no markdown found, direct parse).")
        # structured_data_str is already raw_result_stripped

    try:
        parsed_data = json.loads(structured_data_str)
        if isinstance(parsed_data, dict) and "keywords" in parsed_data and isinstance(parsed_data["keywords"], list):
            logger.info(f"Successfully extracted {len(parsed_data['keywords'])} detailed keywords (initial parse).")
            return parsed_data
        else:
            logger.error(f"Parsed keyword JSON has incorrect structure (initial parse): {parsed_data}")
            raise json.JSONDecodeError("Incorrect structure, attempting repair", structured_data_str, 0)
    except json.JSONDecodeError as e:
        original_error_msg = str(e)
        logger.warning(f"Initial JSON parsing failed: {original_error_msg}. Attempting robust repair on: {structured_data_str[:200]}...")
        repaired_keywords = []
        
        list_content_match = re.search(r'"keywords"\s*:\s*\[(.*?)\]', structured_data_str, re.DOTALL)
        content_to_search = structured_data_str 
        if list_content_match:
            content_to_search = list_content_match.group(1)
            logger.info("Repair attempt: Found keywords list structure, searching within its content.")
        else:
            logger.warning("Repair attempt: Could not find standard 'keywords': [...] structure, searching entire response string.")

        object_pattern = re.compile(r'(\{.*?\})(?=\s*\{|\s*$|\s*,?\s*\])', re.DOTALL)
        potential_objects = object_pattern.findall(content_to_search)
        logger.info(f"Repair attempt: Found {len(potential_objects)} potential keyword objects using regex.")

        for i, obj_str in enumerate(potential_objects):
            obj_str = obj_str.strip()
            if not obj_str: continue
            try:
                obj_str_cleaned = obj_str.rstrip(',')
                keyword_obj = json.loads(obj_str_cleaned)
                if isinstance(keyword_obj, dict) and all(k in keyword_obj for k in ["keyword", "context", "relevance_score", "skill_type"]):
                    repaired_keywords.append(keyword_obj)
                else:
                    logger.warning(f"Repaired object {i+1} lacks expected keys or is not dict: {obj_str_cleaned[:100]}...")
            except json.JSONDecodeError as repair_e:
                logger.warning(f"Could not parse potential object {i+1} during repair: {obj_str_cleaned[:100]}... Error: {repair_e}")
            except Exception as general_repair_e:
                 logger.warning(f"Unexpected error parsing potential object {i+1} during repair: {obj_str_cleaned[:100]}... Error: {general_repair_e}")

        if repaired_keywords:
            parsed_data = {"keywords": repaired_keywords}
            logger.info(f"JSON repair successful. Salvaged {len(repaired_keywords)} keyword objects.")
            return parsed_data
        else:
            logger.error(f"JSON repair failed. Could not salvage any valid keyword objects from raw data: {structured_data_str[:500]}...")
            raise ValueError(f"Failed to parse keywords JSON from OpenAI response, and repair attempt failed. Original error: {original_error_msg}. Raw data snippet: {structured_data_str[:500]}...")
    except Exception as e:
        logger.error(f"Unexpected error during keyword extraction processing: {e}", exc_info=True)
        raise ValueError(f"Unexpected error during keyword processing: {str(e)}") from e

# Example usage (async)
async def main_example():
    # This example assumes OPENAI_API_KEY is set in the environment
    example_jd = """
    We are seeking a Senior Software Engineer with expertise in Python, Django, and AWS. 
    The ideal candidate will have experience with microservices, Docker, and Kubernetes. 
    Strong problem-solving skills and communication are essential.
    Responsibilities include designing, developing, and deploying scalable applications.
    Experience with Agile methodologies and CI/CD pipelines is a plus.
    Familiarity with PostgreSQL and RESTful APIs is also desired.
    """
    try:
        # No need to pass api_key if OPENAI_API_KEY env var is set
        keywords_result = await extract_keywords(job_description_text=example_jd)
        
        print("Extracted Keywords (Async):")
        if keywords_result and "keywords" in keywords_result:
            for i, keyword_info in enumerate(keywords_result.get("keywords", [])):
                print(f"  {i+1}. Keyword: {keyword_info.get('keyword')}")
                print(f"     Context: {keyword_info.get('context')}")
                print(f"     Relevance: {keyword_info.get('relevance_score')}")
                print(f"     Type: {keyword_info.get('skill_type')}")
            
            output_path = "extracted_keywords_example_async.json" # Changed filename for clarity
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(keywords_result, f, indent=2)
            print(f"\nAsync results saved to {output_path}")
        else:
            print("No keywords were extracted or result format is unexpected.")
            
    except Exception as e:
        print(f"Error during async example usage: {e}")

if __name__ == "__main__":
    asyncio.run(main_example())