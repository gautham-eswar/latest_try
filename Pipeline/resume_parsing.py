import json
import logging
from pathlib import Path
import re
from PyPDF2 import PdfReader
import docx2txt

from Services.openai_interface import call_openai_api

# Configure logging
logging.basicConfig(
    level=logging.WARNING, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)




def extract_text_from_file(file_path: Path) -> str:
    """Extract text from TXT, PDF, and DOCX files."""
    file_ext = file_path.suffix.lower()
    logger.info(f"Attempting to extract text from {file_path} (extension: {file_ext})")

    text = ""
    try:
        if file_ext == ".txt":
            with open(file_path, "r", encoding="utf-8") as f:
                text = f.read()
        elif file_ext == ".pdf":
            try:
                reader = PdfReader(file_path)
                for page in reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                if not text:
                    logger.warning(
                        f"PyPDF2 extracted no text from {file_path}. File might be image-based or empty."
                    )
            except Exception as pdf_err:
                logger.error(
                    f"Error extracting PDF text using PyPDF2 from {file_path}: {pdf_err}",
                    exc_info=True,
                )
                # Optionally, could try pdfminer.six here as a fallback
                raise IOError(
                    f"Could not extract text from PDF: {pdf_err}"
                ) from pdf_err
        elif file_ext == ".docx":
            try:
                text = docx2txt.process(file_path)
            except Exception as docx_err:
                logger.error(
                    f"Error extracting DOCX text using docx2txt from {file_path}: {docx_err}",
                    exc_info=True,
                )
                raise IOError(
                    f"Could not extract text from DOCX: {docx_err}"
                ) from docx_err
        else:
            logger.error(f"Unsupported file type for text extraction: {file_ext}")
            raise ValueError(f"Unsupported file type: {file_ext}")

        logger.info(
            f"Successfully extracted ~{len(text)} characters from {file_path.name}"
        )
        return text

    except FileNotFoundError:
        logger.error(f"File not found during text extraction: {file_path}")
        raise
    except Exception as e:
        logger.error(
            f"General error during text extraction for {file_path}: {e}", exc_info=True
        )
        # Re-raise as a more specific error or a generic one
        raise IOError(f"Failed to process file {file_path.name}: {e}") from e




def parse_resume(resume_text):
    """Parse resume text into structured data"""
    system_prompt = "You are a resume parsing assistant. Extract structured information from resumes."
        # Inside parse_resume function
    # --- Start Replacement for user_prompt ---
    user_prompt = f"""
    Parse the following resume text into a structured JSON format. Include the following sections:
    1. Personal Information (name, email, phone, location, website/LinkedIn)
    2. Summary/Objective
    3. Skills - categorize skills into:
       - Technical Skills: Programming languages, tools, software, technical methodologies
       - Soft Skills: Communication, leadership, teamwork, etc.
    4. Experience - For each position, extract:
       - company
       - title
       - location (city, state, country, and if remote work is mentioned)
       - employment_type (full-time, part-time, contract, internship)
       - dates (start_date, end_date or "Present") (If there's only one date, it's the end_date)
       - responsibilities/achievements (as an array of bullet points)
    5. Education - For each entry, extract:
       - university (institution name)
       - location (city, state, country)
       - degree (type of degree: BA, BS, MS, PhD, etc.)
       - specialization (major/field of study)
       - honors (any honors, distinctions, awards)
       - start_date (year)
       - end_date (year or "Present")
       - gpa (if available)
       - additional_info (courses, activities, or any other relevant information)
    6. Projects (title, description, technologies used) (if the description has multiple bullet points, make sure to include them all in a structured manner)
    7. Certifications/Awards
    8. Languages
    9. Publications - For each publication:
       - title
       - authors
       - journal/conference
       - date
       - url (if available)
    10. Volunteer Experience - For each position:
        - organization
        - role
        - location
        - dates
        - description
    11. Misc (other sections that don't fit above)

    For the Skills section, be very careful to correctly categorize technical vs soft skills.
    Technical skills include specific tools, technologies, programming languages, and technical methodologies.
    Soft skills include interpersonal abilities, communication skills, character traits, and other leadership skills.

    RESUME TEXT TO PARSE:
    ---RESUME_START---
    {resume_text}
    ---RESUME_END---

    Return ONLY the JSON object.
    """


    result = call_openai_api(system_prompt, user_prompt)

    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*(.*?)```", result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to parse structured data from resume")
