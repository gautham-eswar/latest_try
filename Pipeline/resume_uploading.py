
import json
import logging
import os
from pathlib import Path
import re
import time
import uuid

from PyPDF2 import PdfReader
import docx2txt
from flask import jsonify
from Pipeline.resume_loading import UPLOAD_FOLDER, get_file_ext
from werkzeug.utils import secure_filename

from Services.database import get_db
from Services.openai_interface import call_openai_api


logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_and_upload_resume(file, user_id):

    # Generate a unique ID for the resume
    resume_id = f"resume_{ int(time.time()) }_{ uuid.uuid4().hex[:8] }"

    # Save file temporarily
    file_ext = get_file_ext(file)
    temp_filename = secure_filename(f"{resume_id}.{file_ext}")
    file_path = os.path.join(UPLOAD_FOLDER, temp_filename)
    file.save(file_path)

    # Parse the resume
    resume_text = extract_text_from_file(Path(file_path))
    parsed_resume = parse_resume(resume_text)

    # Upload resume to database
    db = get_db()
    response = db.table("resumes").insert({
        "id": resume_id,
        "user_id": user_id,
        "data": parsed_resume,
        "file_name": file.filename, 
    }).execute()

    # Error or return
    if not (hasattr(response, "data") and response.data):
        error_text = getattr(response, "error", "Unknown error")
        logger.error(
            f"Error parsing/uploading resume: {error_text}",
            exc_info=True,
        )
        raise Exception(
            f"Database error: Failed to confirm insert. Details: {error_text}"
        )
    return jsonify(
        {
        "status": "success",
        "message": "Resume uploaded and parsed successfully",
        "resume_id": resume_id,
            "data": parsed_resume,
        }
    )

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
    with open("Pipeline/prompts/parse_resume.txt") as file:
        user_prompt = file.read().replace("@resume_text", resume_text)
    
    result = call_openai_api(system_prompt, user_prompt)

    
    # Extract JSON from the result (might be wrapped in markdown code blocks)
    json_match = re.search(r"```(?:json)?\s*(.*?)```", result, re.DOTALL)
    structured_data = json_match.group(1) if json_match else result
    
    try:
        return json.loads(structured_data)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON from OpenAI: {e}")
        raise ValueError("Failed to parse structured data from resume")
