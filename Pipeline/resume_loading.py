import json
import logging
import os
from pathlib import Path
import time
import uuid

from flask import Response, jsonify
from postgrest import APIError as PostgrestAPIError  # Import Supabase error type
from supabase import Client
from werkzeug.utils import secure_filename

from Pipeline.latex_generation import generate_latex_resume, generate_resume_pdf
from Services.database import FallbackDatabase, get_db
from Services.diagnostic_system import get_diagnostic_system
from Services.errors import error_response


ALLOWED_EXTENSIONS = {"txt", "pdf", "docx"}
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
OUTPUT_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")


logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

def get_file_ext(file):
    file_ext = (
        file.filename.rsplit(".", 1)[1].lower() if "." in file.filename else ""
    )
    return file_ext

def fetch_resume_data(resume_id, user_id):

    logger.info(f"Fetching resume. Resume ID: {resume_id}")
    db = get_db()

    response = (
        db.table("resumes")
        .select("*")
        .eq("id", resume_id)
        .single()
        .execute()
    )

    if not (hasattr(response, "data") and response.data):
        error_text = getattr(response, "error", "Unknown error")
        logger.error(
            f"Error fetching resume: {error_text}",
            exc_info=True,
        )
        raise Exception(f"Error fetching resume with Resume ID: \
                        {resume_id}. Error message: {error_text}")
    
    if not response.data["user_id"] == user_id:
        error_msg = f"Error fetching resume with Resume ID: \
                    {resume_id}. Invalid user"
        logger.error(
            error_msg,
            exc_info=True,
        )
        raise Exception(error_msg)

    logger.info(f"Fetched successfully: resume with ID: {resume_id}")
    return response.data


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

    # --- Determine which data to load ---
    if isinstance(db, FallbackDatabase):
        logger.warning(
            f"Using FallbackDatabase for loading download data for resume_id: {resume_id}."
        )
        # Try loading local "enhanced" version first (e.g., {resume_id}_enhanced.json)
        # Then local "original" version (e.g., {resume_id}.json)
        # This naming convention for fallback is kept for simplicity.
        enhanced_fallback_filename = f"{resume_id}_enhanced.json"
        original_fallback_filename = f"{resume_id}.json"

        enhanced_file_path = os.path.join(
            app.config.get("OUTPUT_FOLDER", OUTPUT_FOLDER), enhanced_fallback_filename
        ) # Use app.config if available, else default
        original_file_path = os.path.join(
            app.config.get("UPLOAD_FOLDER", UPLOAD_FOLDER), original_fallback_filename
        )

        if os.path.exists(enhanced_file_path):
            try:
                with open(enhanced_file_path, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    # Fallback "enhanced" files might have a different structure
                    resume_data_to_use = saved_data.get("enhanced_data", saved_data) 
                    data_source = f"enhanced (local fallback: {enhanced_fallback_filename})"
                    logger.info(
                        f"Loaded data from local enhanced fallback file: {enhanced_file_path}"
                    )
            except Exception as e:
                logger.error(
                    f"Error loading local enhanced fallback file {enhanced_file_path}: {e}"
                )
        elif os.path.exists(original_file_path):
            try:
                with open(original_file_path, "r", encoding="utf-8") as f:
                    resume_data_to_use = json.load(f) # Original fallback assumed to be direct JSON
                    data_source = f"original (local fallback: {original_fallback_filename})"
                    logger.info(
                        f"Loaded data from local original fallback file: {original_file_path}"
                    )
            except Exception as e:
                logger.error(
                    f"Error loading local original fallback file {original_file_path}: {e}"
                )
        # If neither local file found with fallback DB, resume_data_to_use remains None

    else:
        # Supabase path
        actual_resume_id_being_served = None # The ID of the record actually served
        try:
            # 1. Try to fetch the latest enhanced version using input resume_id as original_resume_id
            logger.info(f"Attempting to load latest enhanced version for original_id: {resume_id} from 'resumes' table.")
            response_enhanced = (
                db.table("resumes")
                .select("data, id, created_at")  # Assuming created_at for ordering
                .eq("original_resume_id", resume_id)
                .not_.is_("enhancement_id", "null") # Ensure it's an enhanced version
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

            if response_enhanced.data:
                resume_data_to_use = response_enhanced.data[0]["data"]
                actual_resume_id_being_served = response_enhanced.data[0]["id"]
                data_source = f"enhanced (Supabase, original_id: {resume_id}, actual_id: {actual_resume_id_being_served})"
                logger.info(f"Loaded latest enhanced version. Original ID: {resume_id}, Actual ID served: {actual_resume_id_being_served}")
            else:
                # 2. If not found, try to fetch by input resume_id as the direct ID
                logger.info(f"No enhanced version found for original_id: {resume_id}. Attempting to load by direct id: {resume_id} from 'resumes' table.")
                response_direct = (
                    db.table("resumes")
                    .select("data, id")
                    .eq("id", resume_id)
                    .limit(1)
                    .execute()
                )
                if response_direct.data:
                    resume_data_to_use = response_direct.data[0]["data"]
                    actual_resume_id_being_served = response_direct.data[0]["id"]
                    # Check if this "direct" hit was actually an enhanced resume itself
                    # (e.g., user directly provided an ID of an enhanced record)
                    # This is implicitly handled as we don't need to distinguish its 'type' beyond it being a valid resume.
                    data_source = f"direct (Supabase, id: {actual_resume_id_being_served})"
                    logger.info(f"Loaded resume by direct ID: {actual_resume_id_being_served}")
                else:
                    logger.warning(f"No resume data found for ID {resume_id} in 'resumes' table using any method.")
                    # resume_data_to_use remains None

        except PostgrestAPIError as db_e:
            logger.error(
                f"Supabase API Error loading data for ID {resume_id} (Code: {getattr(db_e, 'code', 'N/A')}): {getattr(db_e, 'message', str(db_e))}",
                exc_info=True,
            )
            # More detailed error logging if available
            if hasattr(db_e, 'details'): logger.error(f"DB Error Details: {db_e.details}")
            if hasattr(db_e, 'hint'): logger.error(f"DB Error Hint: {db_e.hint}")
            # resume_data_to_use remains None
            logger.warning("Proceeding as if data not found due to Supabase API error.")
        except Exception as e: # Catch other potential errors like network issues, unexpected response structure
            logger.error(
                f"Unexpected error loading resume {resume_id} from Supabase: {e}",
                exc_info=True,
            )
            # resume_data_to_use remains None
            logger.warning("Proceeding as if data not found due to unexpected error.")


    # Check if we successfully loaded data from any source
    if resume_data_to_use is None:
        logger.error(f"Could not find or load any resume data for ID: {resume_id} (from Supabase or fallback).")
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
            logger.info(f"Generating PDF for resume ID: {resume_id}")
            
            # Use temp file for PDF output
            import tempfile
            output_pdf = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
            output_pdf.close()
            
            # Use our adaptive PDF generation logic
            pdf_path, success = generate_resume_pdf(resume_data_to_use, output_pdf.name)
            
            if success and os.path.exists(pdf_path):
                logger.info(f"Successfully generated PDF for resume ID: {resume_id}")
                
                # Serve the PDF file
                with open(pdf_path, 'rb') as pdf_file:
                    pdf_content = pdf_file.read()
                
                # Clean up temp file after reading
                try:
                    os.unlink(pdf_path)
                except:
                    pass  # Ignore deletion errors
                
                response = Response(
                    pdf_content,
                    mimetype="application/pdf",
                    headers={
                        "Content-Disposition": f"attachment; filename={resume_id}.pdf"
                    },
                )
                return response
            else:
                raise Exception("PDF generation failed or file not found")
                
        except Exception as e:
            logger.error(
                f"Error generating PDF for resume {resume_id}: {str(e)}",
                exc_info=True,
            )
            return app.create_error_response(
                "PdfGenerationError", f"Error generating PDF: {str(e)}", 500
            )