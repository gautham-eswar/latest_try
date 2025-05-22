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