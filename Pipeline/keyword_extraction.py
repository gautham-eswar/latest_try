import json
import logging
import re
from typing import Any, Dict

from Services.openai_interface import call_openai_api


# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)



def extract_keywords(
    job_description_text: str, max_retries=3
) -> Dict[str, Any]:
    """
    Extract detailed keywords from job description using OpenAI,
    attempting to get context, relevance, and skill type.
    Includes validation for non-JSON responses and fallback logic
    to repair slightly malformed JSON responses.
    Returns a dictionary structured for SemanticMatcher.
    """
    logger.info("Extracting detailed keywords using OpenAI...")
    # Add input validation check
    if not job_description_text or len(job_description_text) < 20: # Arbitrary minimum length
        logger.warning(f"Job description text is too short or empty. Skipping OpenAI call.")
        return {"keywords": []} # Return empty structure

    system_prompt = """
    You are an expert HR analyst specializing in extracting structured keywords from job descriptions.
    Focus on identifying distinct skills (hard and soft), experiences, tools, qualifications, and responsibilities.
    """
    # NOTE: Using the original prompt structure, not the simplified one with markers.
    # Added instruction for failure case.
    with open("prompts/extract_keywords.txt") as file:
        user_prompt = file.read().replace("@job_description_txt", job_description_text)


    # Log the input being sent (first 100 chars)
    logger.debug(f"Sending JD to OpenAI: {job_description_text[:100]}...")
    raw_result = call_openai_api(system_prompt, user_prompt, max_retries=max_retries)

    # Check if the response looks like JSON before trying to parse
    raw_result_stripped = raw_result.strip()
    if not raw_result_stripped.startswith('{'):
        logger.error(f"OpenAI did not return JSON format. Response: {raw_result_stripped[:500]}...")
        # Raise specific error for non-JSON response
        raise ValueError(f"OpenAI returned non-JSON response: {raw_result_stripped[:200]}...")

    # Attempt to extract JSON block if present (e.g., within markdown)
    logger.debug(f"Raw keyword extraction result from OpenAI (Passed initial '{'{'} check'): {raw_result[:500]}...")
    json_match = re.search(
        r"```(?:json)?\s*({.*?})\s*```", raw_result, re.DOTALL | re.IGNORECASE
    )
    if not json_match:
        # Fallback: Check if the raw result itself is the JSON object (already validated startswith('{'))
        if raw_result_stripped.endswith('}'):
             structured_data_str = raw_result_stripped
             logger.info("Using raw API response as JSON object (no markdown found).")
        else:
            # If it starts with { but isn't wrapped and doesn't end with }, it's likely incomplete/malformed
            # Log this case and let the repair logic try to handle it
            logger.warning("Response starts with '{' but not clearly identifiable as complete JSON object or markdown block. Proceeding to parsing/repair attempt.")
            structured_data_str = raw_result_stripped
    else:
        structured_data_str = json_match.group(1) # Use the content inside the markdown block
        logger.info("Extracted JSON object from within markdown block.")


    # --- START OF JSON Parsing and Repair Block ---
    try:
        # Attempt to parse the extracted JSON string
        parsed_data = json.loads(structured_data_str)

        # Validate the structure
        if (
            isinstance(parsed_data, dict)
            and "keywords" in parsed_data
            and isinstance(parsed_data["keywords"], list)
        ):
            # Further validation could check individual keyword objects
            logger.info(
                f"Successfully extracted {len(parsed_data['keywords'])} detailed keywords (initial parse)."
            )
            return parsed_data
        else:
            logger.error(f"Parsed keyword JSON has incorrect structure (initial parse): {parsed_data}")
            # If structure is wrong even if JSON is valid, trigger repair attempt
            raise json.JSONDecodeError("Incorrect structure, attempting repair", structured_data_str, 0)

    except json.JSONDecodeError as e:
        original_error_msg = str(e)
        logger.warning(f"Initial JSON parsing failed: {original_error_msg}. Attempting robust repair...")
        repaired_keywords = []
        parsed_data = None # Initialize to None

        # Try to extract content within the "keywords": [...] list first for focused search
        # This regex tries to find the list content, handling potential whitespace
        list_content_match = re.search(r'"keywords"\s*:\s*\[(.*?)\]', structured_data_str, re.DOTALL)
        content_to_search = structured_data_str # Default to searching the whole string

        if list_content_match:
            content_to_search = list_content_match.group(1)
            logger.info("Repair attempt: Found keywords list structure, searching within its content.")
        else:
            logger.warning("Repair attempt: Could not find standard 'keywords': [...] structure, searching entire response string.")

        # Regex to find potential JSON objects: starts with '{', ends with '}' non-greedily.
        # It attempts to capture complete objects even if commas are missing between them.
        # Matches { ... } pairs, being careful about nested braces might be complex,
        # this simpler approach targets top-level objects assuming keywords aren't deeply nested.
        object_pattern = re.compile(r'(\{.*?\})(?=\s*\{|\s*$|\s*,?\s*\])', re.DOTALL)

        potential_objects = object_pattern.findall(content_to_search)
        logger.info(f"Repair attempt: Found {len(potential_objects)} potential keyword objects using regex.")

        for i, obj_str in enumerate(potential_objects):
            obj_str = obj_str.strip()
            if not obj_str: continue # Skip empty matches

            try:
                # Clean up potential trailing comma JUST IN CASE the regex included it accidentally
                obj_str_cleaned = obj_str.rstrip(',')
                keyword_obj = json.loads(obj_str_cleaned)

                # Basic validation of the parsed object's structure
                if isinstance(keyword_obj, dict) and all(k in keyword_obj for k in ["keyword", "context", "relevance_score", "skill_type"]):
                    repaired_keywords.append(keyword_obj)
                    # logger.debug(f"Repair successful for object {i+1}.") # Optional: too verbose?
                else:
                    logger.warning(f"Repaired object {i+1} lacks expected keys or is not dict: {obj_str_cleaned[:100]}...")

            except json.JSONDecodeError as repair_e:
                logger.warning(f"Could not parse potential object {i+1} during repair: {obj_str_cleaned[:100]}... Error: {repair_e}")
            except Exception as general_repair_e:
                 logger.warning(f"Unexpected error parsing potential object {i+1} during repair: {obj_str_cleaned[:100]}... Error: {general_repair_e}")

        # Check if repair was successful
        if repaired_keywords:
            parsed_data = {"keywords": repaired_keywords}
            logger.info(f"JSON repair successful. Salvaged {len(repaired_keywords)} keyword objects.")
            # Return the successfully repaired data
            return parsed_data
        else:
            # If repair fails, raise the original error message for clarity, including raw data snippet
            logger.error(f"JSON repair failed. Could not salvage any valid keyword objects from raw data: {structured_data_str[:500]}...")
            # Raise a ValueError containing the original error and context
            raise ValueError(f"Failed to parse keywords JSON from OpenAI response, and repair attempt failed. Original error: {original_error_msg}. Raw data snippet: {structured_data_str[:500]}...")

    except Exception as e:
        # Catch any other unexpected errors during the process
        logger.error(
            f"Unexpected error during keyword extraction processing: {e}", exc_info=True
        )
        # Ensure the original exception type and message are propagated if possible
        raise ValueError(f"Unexpected error during keyword processing: {str(e)}") from e
    # --- END OF JSON Parsing and Repair Block ---
# --- End Replacement (Whole Function) ---