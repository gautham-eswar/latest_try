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


def enhance_resume(job_id, resume_id, user_id, job_description_text):

    logger.info(f"Starting resume enhancement: User ID: {user_id} \
                Resume ID: {resume_id} Job Description: {job_description_text[:40]}")

    # Initialize Supabase client
    db = get_db()

    
    # Get the original parsed resume
    original_resume_info = fetch_resume_data(resume_id, user_id)
    original_resume_parsed = original_resume_info["data"]

    # Extract Keywords from Job description
    keywords_data = extract_keywords(job_description_text)
    kw_count = len(keywords_data.get("keywords", []))
    logger.info(
        f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords."
    )
    update_optimization_job(job_id, {
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
        keywords_data, 
        original_resume_parsed,
        # TODO: Consider making similarity_threshold, relevance_threshold, overall_skill_limit configurable per job or globally
        similarity_threshold=0.75, # For bullet matching
        relevance_threshold=0.5,   # For JD hard skills to be considered for skills section
        overall_skill_limit=20     # Target total technical skills in skills section
    )
    matches_by_bullet = match_results.get("matches_by_bullet", {})
    final_technical_skills = match_results.get("final_technical_skills", {})
    skill_selection_log = match_results.get("skill_selection_process_log", {})

    bullets_matched_count = len(matches_by_bullet)
    final_skills_count = sum(len(sks) for sks in final_technical_skills.values())

    logger.info(
        f"Job {job_id}: Semantic matching complete. "
        f"Found matches for {bullets_matched_count} bullets. "
        f"Selected {final_skills_count} final technical skills."
    )
    update_optimization_job(job_id, {
        "status": "Resume Enhancement",
        "match_count": bullets_matched_count,
        "match_details": matches_by_bullet, # Contains keywords for bullets
        "new_skills_section": final_technical_skills, # The new skills section structure
        "skills_selection_log": skill_selection_log
    })

    # --- Resume Enhancement ---
    enhanced_resume_parsed = None
    modifications = []

    logger.info(f"Job {job_id}: Initializing ResumeEnhancer...")
    enhancer = ResumeEnhancer()
    logger.info(f"Job {job_id}: Running resume enhancement process...")
    enhanced_resume_parsed, modifications = enhancer.enhance_resume(
        original_resume_parsed, 
        matches_by_bullet,
        final_technical_skills=final_technical_skills # Pass the selected skills here
    )
    logger.info(
        f"Job {job_id}: Resume enhancement complete. {len(modifications)} modifications made."
    )
    update_optimization_job(job_id, {
        "status": "Enhanced resume Upload",
        "modifications": modifications,
    })

    # --- Save Enhanced Resume & Analysis (to Supabase) ---
    logger.info(
        f"Attempting to save enhanced resume in Supabase table   ..."
    )
    enhanced_resume_data = upload_resume({
        "user_id": user_id,
        "data": enhanced_resume_parsed,
        "file_name": f"Enhanced - {original_resume_info['file_name']}",
        "enhancement_id": job_id,
        "original_resume_id": original_resume_info["id"],
    })
    enhanced_resume_id = enhanced_resume_data["id"]
    update_optimization_job(job_id, {
        "status": "Completed",
        "modifications": modifications,
        "enhanced_resume_id": enhanced_resume_id
    })
    


    # --- Return Success Response ---
    logger.info(f"Job {job_id}: Optimization completed successfully.")
    return jsonify(
        {
            "status": "success",
            "message": "Resume optimized successfully using advanced workflow",
            "resume_id": resume_id,
            "data": {
                "job_id": job_id,
                "enhanced_resume_id": enhanced_resume_data["id"],
                "enhanced_resume_parsed": enhanced_resume_data["data"],  # The enhanced resume content
                "analysis": { # Consolidating analysis data here
                    "matches_by_bullet": matches_by_bullet,
                    "skill_selection_log": skill_selection_log,
                    "modifications_summary": modifications # Summary of changes made
                },
            }
            
        }
    )