import json
import logging
import os
from pathlib import Path
import time
import uuid

from flask import Response, jsonify
from postgrest import APIError as PostgrestAPIError  # Import Supabase error type
from werkzeug.utils import secure_filename

from Pipeline.latex_generation import generate_latex_resume
from Pipeline.resume_parsing import extract_text_from_file, parse_resume
from Services.database import FallbackDatabase, get_db
from Services.diagnostic_system import get_diagnostic_system


ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

diagnostic_system = get_diagnostic_system()

logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def upload_resume(app, file):

    if file.filename == "":
        return app.create_error_response("EmptyFile", "No file selected", 400)
    
    # Check if the file has an allowed extension
    allowed_extensions = ALLOWED_EXTENSIONS
    file_ext = (
        file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    )
    if file_ext not in allowed_extensions:
        return app.create_error_response(
            "InvalidFileType",
            f"File type not allowed. Allowed types: {', '.join(allowed_extensions)}", 
            400,
        )
    
    # Generate a unique ID for the resume
    resume_id = f"resume_{ int(time.time()) }_{ uuid.uuid4().hex[:8] }"
    file_ext = (
        file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    )
    filename = secure_filename(f"{resume_id}.{file_ext}")
    file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)

    db = None  # Initialize db to None
    try:
        # 1. Save the uploaded file locally (optional, could upload directly to Supabase storage)
        file.save(file_path)
        logger.info(f"Saved uploaded file locally to: {file_path}")
        
        # 2. Extract text from the file
        logger.info("Extracting text from uploaded file...")
        resume_text = extract_text_from_file(Path(file_path))
        logger.info(f"Extracted {len(resume_text)} characters.")
        
        # 3. Parse the resume text using OpenAI
        logger.info("Parsing resume text using OpenAI...")
        parsed_resume = parse_resume(resume_text)
        logger.info("Resume parsed successfully.")

        # 4. Save parsed data to Supabase
        logger.info(f"Attempting to save parsed resume {resume_id} to Supabase...")
        db = get_db()

        if isinstance(db, FallbackDatabase):
            logger.warning(
                f"Using FallbackDatabase for resume {resume_id}. Data will not be persisted."
            )
            output_file = os.path.join(
                app.config["UPLOAD_FOLDER"], f"{resume_id}.json"
            )
            with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(parsed_resume, f, indent=2)
            logger.info(
                f"Saved parsed resume JSON locally (fallback): {output_file}"
            )
        else:
            # Insert into Supabase 'resumes_new' table
            logger.info(f"Inserting into Supabase table: resumes_new")
            data_to_insert = {
                "id": resume_id,
                "parsed_data": parsed_resume,
                "original_filename": file.filename,  # Store original filename
            }
            try:
                response = db.table("resumes_new").insert(data_to_insert).execute()
                # More specific error check
                # Note: Supabase Python V1 might not populate .error correctly on insert,
                # checking for non-empty data is often more reliable for success.
                if not (hasattr(response, "data") and response.data):
                    logger.error(
                        f"Supabase insert for {resume_id} into resumes_new returned no data, assuming failure."
                    )
                    # Attempt to get potential error details if possible (structure might vary)
                    error_details = getattr(response, "error", None) or getattr(
                        response, "message", "Unknown insert error"
                    )
                    raise Exception(
                        f"Database error: Failed to confirm insert. Details: {error_details}"
                    )
                else:
                    logger.info(
                        f"Successfully saved parsed resume {resume_id} to Supabase (resumes_new)."
                    )
            except PostgrestAPIError as db_e:
                logger.error(
                    f"Supabase insert error for {resume_id} (Code: {db_e.code}): {db_e.message}",
                    exc_info=True,
                )
                logger.error(
                    f"DB Error Details: {db_e.details} | Hint: {db_e.hint}"
                )
                raise Exception(f"Database error ({db_e.code}): {db_e.message}")
            except Exception as db_e:
                logger.error(
                    f"Unexpected error during Supabase insert for {resume_id}: {db_e}",
                    exc_info=True,
                )
                raise  # Re-raise unexpected errors

        # 5. Return success response
        return jsonify(
            {
            "status": "success",
            "message": "Resume uploaded and parsed successfully",
            "resume_id": resume_id,
                "data": parsed_resume,
            }
        )

    except Exception as e:
        # Log the full error with traceback for debugging
        logger.error(
            f"Error processing uploaded resume {resume_id}: {str(e)}", exc_info=True
        )
        # Track error in diagnostic system
        if diagnostic_system:
            diagnostic_system.increment_error_count(
                f"UploadError_{e.__class__.__name__}", str(e)
            )
        # Attempt to clean up the saved local file if it exists
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                logger.info(f"Cleaned up local file on error: {file_path}")
            except OSError as rm_err:
                logger.warning(
                    f"Could not clean up local file {file_path} on error: {rm_err}"
                )

        return app.create_error_response(
            "ProcessingError", 
            f"Error processing resume: {e.__class__.__name__} - {str(e)}",
            500,
        )
    

def download_resume(app, resume_id, format_type):
    if format_type not in ["json", "pdf", "latex"]:
        return app.create_error_response(
            "InvalidFormat",
            f"Unsupported format: {format_type}. Supported formats: json, pdf, latex",
            400,
        )

    logger.info(
        f"Download request for resume ID: {resume_id}, format: {format_type}"
    )
    db = get_db()
    resume_data_to_use = None
    data_source = "unknown"

    # --- Determine which data to load (enhanced first, fallback to original from DB) ---
    if isinstance(db, FallbackDatabase):
        logger.warning(
            f"Using FallbackDatabase for loading download data for {resume_id}."
        )
        # Try loading local enhanced, then local original as fallback
        enhanced_file = os.path.join(
            app.config["OUTPUT_FOLDER"], f"{resume_id}_enhanced.json"
        )
        original_file = os.path.join(
            app.config["UPLOAD_FOLDER"], f"{resume_id}.json"
        )
        if os.path.exists(enhanced_file):
            try:
                with open(enhanced_file, "r", encoding="utf-8") as f:
                    # The enhanced file now contains both enhanced_data and analysis_data
                    saved_data = json.load(f)
                    resume_data_to_use = saved_data.get("enhanced_data")
                    data_source = "enhanced (local fallback)"
                    logger.info(
                        f"Loaded enhanced data from local fallback: {enhanced_file}"
                    )
            except Exception as e:
                logger.error(
                    f"Error loading local enhanced file {enhanced_file}: {e}"
                )
        elif os.path.exists(original_file):
            try:
                with open(original_file, "r", encoding="utf-8") as f:
                    resume_data_to_use = json.load(f)
                    data_source = "original (local fallback)"
                    logger.info(
                        f"Loaded original data from local fallback: {original_file}"
                    )
            except Exception as e:
                logger.error(
                    f"Error loading local original file {original_file}: {e}"
                )
        # If neither local file found with fallback DB, resume_data_to_use remains None

    else:
        # Try loading from Supabase 'enhanced_resumes' first
        try:
            logger.info(
                f"Attempting to load enhanced data for {resume_id} from Supabase..."
            )
            response_enh = (
                db.table("enhanced_resumes")
                .select("enhanced_data")
                .eq("resume_id", resume_id)
                .limit(1)
                .execute()
            )
            if response_enh.data:
                resume_data_to_use = response_enh.data[0]["enhanced_data"]
                data_source = "enhanced (Supabase)"
                logger.info(f"Loaded enhanced data for {resume_id} from Supabase.")
            else:
                # If not found, try loading from original 'resumes_new' table
                logger.info(
                    f"Enhanced data not found for {resume_id}, trying original from Supabase (table: resumes_new)..."
                )
                response_orig = (
                    db.table("resumes_new")
                    .select("parsed_data")
                    .eq("id", resume_id)
                    .limit(1)
                    .execute()
                )
                if response_orig.data:
                    resume_data_to_use = response_orig.data[0]["parsed_data"]
                    data_source = "original (Supabase)"
                    logger.info(
                        f"Loaded original data for {resume_id} from Supabase."
                    )
                else:
                    logger.warning(
                        f"No data found for {resume_id} in enhanced_resumes or resumes_new tables."
                    )
                    # resume_data_to_use remains None
        except PostgrestAPIError as db_e:
            logger.error(
                f"Error loading data for {resume_id} from Supabase (Code: {db_e.code}): {db_e.message}",
                exc_info=True,
            )
            logger.error(f"DB Error Details: {db_e.details} | Hint: {db_e.hint}")
            # Allow fallback to local files if DB error occurs?
            # For now, treat DB error as data not found
            resume_data_to_use = None
            logger.warning("Proceeding as if data not found due to DB error.")
        except Exception as db_e:
            logger.error(
                f"Unexpected error loading resume {resume_id} from Supabase: {db_e}",
                exc_info=True,
            )
            raise  # Re-raise unexpected errors

    # Check if we successfully loaded data from any source
    if resume_data_to_use is None:
        logger.error(f"Could not find or load any resume data for ID: {resume_id}")
        return app.create_error_response(
            "NotFound", f"No resume data found for ID {resume_id}", 404
        )

    logger.info(f"Using resume data from source: {data_source}")

    # --- Generate requested format ---
    if format_type == "json":
        logger.info(f"Serving JSON for resume ID: {resume_id}")
        return jsonify(
            {
            "status": "success",
            "resume_id": resume_id,
                "source": data_source,
                "data": resume_data_to_use,  # Use the loaded data
            }
        )

    elif format_type == "latex":
        try:
            logger.info(f"Generating LaTeX for resume ID: {resume_id}")
            latex_content = generate_latex_resume(resume_data_to_use)
            response = Response(
                latex_content,
                mimetype="application/x-latex",
                headers={
                    "Content-Disposition": f"attachment; filename={resume_id}.tex"
                },
            )
            logger.info(f"Successfully generated LaTeX for resume ID: {resume_id}")
            return response
    
        except Exception as e:
            logger.error(
                f"Error generating LaTeX for resume {resume_id}: {str(e)}",
                exc_info=True,
            )
        return app.create_error_response(
                "LatexGenerationError", f"Error generating LaTeX: {str(e)}", 500
            )

    elif format_type == "pdf":
        try:
            logger.info(f"Generating PDF (via LaTeX) for resume ID: {resume_id}")
            latex_content = generate_latex_resume(resume_data_to_use)
            # ... (PDF generation logic remains the same - still placeholder) ...
        except Exception as e:
            logger.error(
                f"Error generating PDF for resume {resume_id}: {str(e)}",
                exc_info=True,
            )
            return app.create_error_response(
                "PdfGenerationError", f"Error generating PDF: {str(e)}", 500
            )