
# Configure logging
import json
import logging
import os
import time

from flask import jsonify
from postgrest import APIError as PostgrestAPIError  # Import Supabase error type

from Pipeline.keyword_extraction import extract_keywords
from Pipeline.resume_handling import OUTPUT_FOLDER, UPLOAD_FOLDER
from Services.database import FallbackDatabase, get_db
from Services.diagnostic_system import get_diagnostic_system
from Services.utils import create_error_response
from embeddings import SemanticMatcher
from enhancer import ResumeEnhancer


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

diagnostic_system = get_diagnostic_system()


def enhance_resume(data):

    job_id = None  # Initialize job_id for diagnostics
    overall_status = "error"  # Default status
    
    resume_id = data.get("resume_id")
    job_description_data = data.get(
        "job_description"
    )  
    
    if not resume_id:
        return create_error_response(
            "MissingParameter", "Missing: resume_id", 400
        )

    if (
        not job_description_data
        or not isinstance(job_description_data, dict)
        or "description" not in job_description_data
    ):
        return create_error_response(
            "MissingParameter",
            "Missing or invalid: job_description (must be an object with a 'description' key)",
            400,
        )

    job_description_text = job_description_data["description"]
    if not job_description_text:
        return create_error_response(
            "MissingParameter", "Job description text cannot be empty", 400
        )

    # --- Start Diagnostic Tracking ---
    if diagnostic_system:
        # Use resume_id and maybe part of job desc for job identifier
        job_desc_snippet = job_description_text[:50].replace("\n", " ") + "..."
        job_id = diagnostic_system.start_pipeline_job(
            resume_id, "api_optimize", job_desc_snippet
        )
        if not job_id:
            logger.warning(
                f"Failed to start diagnostic pipeline job for resume {resume_id}"
            )
            job_id = None  # Ensure it's None if failed

    logger.info(
        f"Starting optimization for resume_id: {resume_id} (Job ID: {job_id})"
    )

    # --- Load Original Parsed Resume Data (from Supabase) ---
    logger.info(
        f"Loading original parsed resume {resume_id} from Supabase (table: resumes_new)..."
    )
    db = get_db()
    original_resume_data = None

    if isinstance(db, FallbackDatabase):
        logger.warning(
            f"Using FallbackDatabase for loading resume {resume_id}."
        )
        # Attempt to load from local file as fallback (if saved by upload)
        resume_file_path = os.path.join(
            UPLOAD_FOLDER, f"{resume_id}.json"
        )
        if os.path.exists(resume_file_path):
            with open(resume_file_path, "r", encoding="utf-8") as f:
                original_resume_data = json.load(f)
            logger.info(f"Loaded resume {resume_id} from local fallback file.")
        else:
            logger.error(
                f"FallbackDatabase active and local file for {resume_id} not found."
            )
            return create_error_response(
                "NotFound", f"Resume {resume_id} not found (fallback).", 404
            )
    else:
        # Fetch from Supabase 'resumes_new' table
        try:
            response = (
                db.table("resumes_new")
                .select("parsed_data")
                .eq("id", resume_id)
                .limit(1)
                .execute()
            )
            if response.data:
                original_resume_data = response.data[0]["parsed_data"]
                logger.info(
                    f"Successfully loaded resume {resume_id} from Supabase."
                )
            else:
                logger.error(f"Resume {resume_id} not found in Supabase.")
                return create_error_response(
                    "NotFound", f"Resume {resume_id} not found.", 404
                )
        except PostgrestAPIError as db_e:
            logger.error(
                f"Error loading resume {resume_id} from Supabase (Code: {db_e.code}): {db_e.message}",
                exc_info=True,
            )
            logger.error(
                f"DB Error Details: {db_e.details} | Hint: {db_e.hint}"
            )
            raise Exception(
                f"Database error loading resume ({db_e.code}): {db_e.message}"
            )
        except Exception as db_e:
            logger.error(
                f"Unexpected error loading resume {resume_id} from Supabase: {db_e}",
                exc_info=True,
            )
            raise  # Re-raise unexpected errors

    # Ensure we have data before proceeding
    if not original_resume_data:
        logger.error(
            f"Failed to load original_resume_data for {resume_id} after DB/fallback checks."
        )
        return create_error_response(
            "ProcessingError",
            f"Could not load data for resume {resume_id}",
            500,
        )

    # --- Keyword Extraction ---
    stage_name = "Keyword Extractor"
    start_time = time.time()
    keywords_data = None
    stage_status = "error"
    stage_message = "Extraction failed"
    try:
        logger.info(f"Job {job_id}: Extracting detailed keywords...")
        keywords_data = extract_keywords(job_description_text)
        kw_count = len(keywords_data.get("keywords", []))
        logger.info(
            f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords."
        )
        stage_status = "healthy"
        stage_message = f"Extracted {kw_count} keywords"
    except Exception as e:
        logger.error(
            f"Job {job_id}: Keyword Extraction failed: {e}", exc_info=True
        )
        stage_message = f"Extraction failed: {e.__class__.__name__}"
        # Re-raise to stop processing
        raise
    finally:
        duration = time.time() - start_time
        if diagnostic_system and job_id:
            diagnostic_system.record_pipeline_stage(
                job_id, stage_name, stage_status, duration, stage_message
            )

    # --- Semantic Matching ---
    stage_name = "Semantic Matcher"
    start_time = time.time()
    match_results = None
    matches_by_bullet = {}
    stage_status = "error"
    stage_message = "Matching failed"
    try:
        logger.info(f"Job {job_id}: Initializing SemanticMatcher...")
        matcher = SemanticMatcher()
        logger.info(f"Job {job_id}: Running semantic matching process...")
        match_results = matcher.process_keywords_and_resume(
            keywords_data, original_resume_data
        )
        matches_by_bullet = match_results.get("matches_by_bullet", {})
        bullets_matched = len(matches_by_bullet)
        logger.info(
            f"Job {job_id}: Semantic matching complete. Found matches for {bullets_matched} bullets."
        )
        stage_status = "healthy"
        stage_message = f"Matched {bullets_matched} bullets"
    except Exception as e:
        logger.error(
            f"Job {job_id}: Semantic Matching failed: {e}", exc_info=True
        )
        stage_message = f"Matching failed: {e.__class__.__name__}"
        raise
    finally:
        duration = time.time() - start_time
        if diagnostic_system and job_id:
            diagnostic_system.record_pipeline_stage(
                job_id, stage_name, stage_status, duration, stage_message
            )

    # --- Resume Enhancement ---
    stage_name = "Resume Enhancer"
    start_time = time.time()
    enhanced_resume_data = None
    modifications = []
    stage_status = "error"
    stage_message = "Enhancement failed"
    try:
        logger.info(f"Job {job_id}: Initializing ResumeEnhancer...")
        enhancer = ResumeEnhancer()
        logger.info(f"Job {job_id}: Running resume enhancement process...")
        enhanced_resume_data, modifications = enhancer.enhance_resume(
            original_resume_data, matches_by_bullet
        )
        mods_count = len(modifications)
        logger.info(
            f"Job {job_id}: Resume enhancement complete. {mods_count} modifications made."
        )
        stage_status = "healthy"
        stage_message = f"Made {mods_count} modifications"
    except Exception as e:
        logger.error(
            f"Job {job_id}: Resume Enhancement failed: {e}", exc_info=True
        )
        stage_message = f"Enhancement failed: {e.__class__.__name__}"
        raise
    finally:
        duration = time.time() - start_time
        if diagnostic_system and job_id:
            diagnostic_system.record_pipeline_stage(
                job_id, stage_name, stage_status, duration, stage_message
            )

    # --- Prepare Analysis Data ---
    # Construct a basic analysis object (can be refined)
    analysis_data = {
        "matched_keywords_by_bullet": matches_by_bullet,
        "enhancement_modifications": modifications,
        "statistics": match_results.get("statistics", {}),
        "job_keywords_used": keywords_data.get(
            "keywords", []
        ),  # Include the keywords extracted
    }
    logger.info(f"Job {job_id}: Prepared analysis data.")

    # --- Save Enhanced Resume & Analysis (to Supabase) ---
    logger.info(
        f"Attempting to save/update enhanced resume {resume_id} in Supabase table enhanced_resumes..."
    )
    if isinstance(db, FallbackDatabase):
        logger.warning(
            f"Using FallbackDatabase for saving enhanced resume {resume_id}. Data will not be persisted."
        )
        # Optionally save locally if using fallback
        output_file_path = os.path.join(
            OUTPUT_FOLDER, f"{resume_id}_enhanced.json"
        )
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "enhanced_data": enhanced_resume_data,
                    "analysis_data": analysis_data,
                },
                f,
                indent=2,
            )
        logger.info(
            f"Job {job_id}: Saved enhanced resume locally (fallback): {output_file_path}"
        )
    else:
        # Upsert into Supabase 'enhanced_resumes' table
        # Assuming table `enhanced_resumes` exists with columns:
        # resume_id (text, primary key, fk->resumes.id),
        # enhanced_data (jsonb),
        # analysis_data (jsonb),
        # created_at (timestamp)
        data_to_upsert = {
            "resume_id": resume_id,
            "enhanced_data": enhanced_resume_data,
            "analysis_data": analysis_data,
        }
        try:
            response = (
                db.table("enhanced_resumes").upsert(data_to_upsert).execute()
            )
            # More specific error check
            if not (hasattr(response, "data") and response.data):
                logger.error(
                    f"Supabase upsert for enhanced {resume_id} returned no data, assuming failure."
                )
                error_details = getattr(response, "error", None) or getattr(
                    response, "message", "Unknown upsert error"
                )
                # Don't raise here, just warn as per previous logic
                logger.warning(
                    f"Failed to confirm enhanced data save in Supabase. Details: {error_details}"
                )
            else:
                logger.info(
                    f"Successfully saved/updated enhanced resume {resume_id} to Supabase."
                )
        except PostgrestAPIError as db_e:
            logger.error(
                f"Supabase upsert error for enhanced {resume_id} (Code: {db_e.code}): {db_e.message}",
                exc_info=True,
            )
            logger.error(
                f"DB Error Details: {db_e.details} | Hint: {db_e.hint}"
            )
            # Don't fail the request, just log the error.
            logger.warning(
                "Proceeding with response despite database save error for enhanced data."
            )
        except Exception as db_save_e:
            logger.error(
                f"Job {job_id}: Error saving enhanced resume {resume_id} to Supabase: {db_save_e}",
                exc_info=True,
            )
            # Don't fail the request, but log the error. Frontend still gets results.
            logger.warning(
                "Proceeding with response despite database save error for enhanced data."
            )

    # --- Return Success Response ---
    overall_status = "healthy"  # Mark as healthy if we reach here
    logger.info(f"Job {job_id}: Optimization completed successfully.")
    return jsonify(
        {
        "status": "success",
            "message": "Resume optimized successfully using advanced workflow",
        "resume_id": resume_id,
            "data": enhanced_resume_data,  # The enhanced resume content
            "analysis": analysis_data,  # The analysis/match details
        }
    )