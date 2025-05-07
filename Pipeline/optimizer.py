
# Configure logging
import json
import logging
import os
import time
import uuid

from flask import jsonify
from postgrest import APIError as PostgrestAPIError
from supabase import Client  # Import Supabase error type

from Pipeline.job_tracking import create_optimization_job, update_optimization_job
from Pipeline.keyword_extraction import extract_keywords
from Pipeline.resume_loading import OUTPUT_FOLDER, UPLOAD_FOLDER, fetch_resume_data
from Pipeline.resume_uploader import generate_resume_id, upload_resume
from Services.database import FallbackDatabase, get_db
from Services.diagnostic_system import get_diagnostic_system
from Services.utils import create_error_response
from Pipeline.embeddings import SemanticMatcher
from Pipeline.enhancer import ResumeEnhancer


logging.basicConfig(
    level=logging.INFO, format="%(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

diagnostic_system = get_diagnostic_system()


def enhance_resume(resume_id, user_id, job_description_text):

    logger.info(f"Starting resume enhancement: User ID: {user_id} \
                Resume ID: {resume_id} Job Description: {job_description_text[:40]}")

    # Initialize Supabase client
    db = get_db()

    # Create optimization task in supabase (for tracking purposes)
    job_id = create_optimization_job(db, resume_id, user_id, job_description_text)
    
    # Get the original parsed resume
    original_resume_info = fetch_resume_data(db, resume_id, user_id)
    original_resume_parsed = original_resume_info["data"]

    # Extract Keywords from Job description
    keywords_data = extract_keywords(job_description_text)
    kw_count = len(keywords_data.get("keywords", []))
    logger.info(
        f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords."
    )
    update_optimization_job(db, job_id, {
        "status": "Semantic Matching",
        "keywords_extracted": keywords_data,
    })

    # --- Semantic Matching ---
    match_results = None
    matches_by_bullet = {}
    logger.info(f"Job {job_id}: Initializing SemanticMatcher...")
    matcher = SemanticMatcher()
    logger.info(f"Job {job_id}: Running semantic matching process...")
    match_results = matcher.process_keywords_and_resume(
        keywords_data, original_resume_parsed
    )
    matches_by_bullet = match_results.get("matches_by_bullet", {})
    bullets_matched = len(matches_by_bullet)
    logger.info(
        f"Job {job_id}: Semantic matching complete. \
        Found matches for {bullets_matched} bullets."
    )
    update_optimization_job(db, job_id, {
        "status": "Resume Enhancement",
        "matches": bullets_matched,
        "match_details": matches_by_bullet
    })

    # --- Resume Enhancement ---
    enhanced_resume_data = None
    modifications = []

    logger.info(f"Job {job_id}: Initializing ResumeEnhancer...")
    enhancer = ResumeEnhancer()
    logger.info(f"Job {job_id}: Running resume enhancement process...")
    enhanced_resume_data, modifications = enhancer.enhance_resume(
        original_resume_parsed, matches_by_bullet
    )
    logger.info(
        f"Job {job_id}: Resume enhancement complete. {len(modifications)} modifications made."
    )
    update_optimization_job(db, job_id, {
        "status": "Enhanced resume Upload",
        "modifications": modifications,
    })

    # --- Save Enhanced Resume & Analysis (to Supabase) ---
    logger.info(
        f"Attempting to save enhanced resume in Supabase table   ..."
    )
    upload_resume(db, {
        "user_id": user_id,
        "data": enhanced_resume_data,
        "file_name": f"Enhanced - {original_resume_info['file_name']}",
        "enhancement_id": job_id,
        "original_resume_id": original_resume_info["id"],
    })
    update_optimization_job(db, job_id, {
        "status": "Completed",
        "modifications": modifications,
    })


    # --- Return Success Response ---
    logger.info(f"Job {job_id}: Optimization completed successfully.")
    return jsonify(
        {
        "status": "success",
            "message": "Resume optimized successfully using advanced workflow",
        "resume_id": resume_id,
            "data": enhanced_resume_data,  # The enhanced resume content
            # "analysis": analysis_data,  # The analysis/match details
        }
    )