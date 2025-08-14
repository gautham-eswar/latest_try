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
from Pipeline.latex_generation import proactively_generate_pdf # Added for proactive PDF generation
from Services.openai_interface import call_openai_api

# logging.basicConfig(level=logging.INFO, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

diagnostic_system = get_diagnostic_system()


def enhance_resume(job_id, resume_id, user_id, job_description_text):

    logger.info(f"--- Pipeline Start: Enhance Resume for Job {job_id} ---")
    logger.info(f"Received User ID: {user_id}, Resume ID: {resume_id}")

    # Initialize Supabase client
    db = get_db()

    
    # --- Stage: Fetching Original Resume ---
    logger.info(f"--- Stage 1/5: Fetching Original Resume ---")
    original_resume_info = fetch_resume_data(resume_id, user_id)
    original_resume_parsed = original_resume_info["data"]
    logger.info(f"--- Stage 1/5: Completed ---")


    # --- Stage: Keyword Extraction ---
    logger.info(f"--- Stage 2/5: Extracting Keywords ---")
    keywords_data = extract_keywords(job_description_text)
    kw_count = len(keywords_data.get("keywords", []))
    logger.info(f"Job {job_id}: Detailed keyword extraction yielded {kw_count} keywords.")
    update_optimization_job(job_id, {
        "status": "Semantic Matching",
        "keywords_extracted": keywords_data,
    })
    logger.info(f"--- Stage 2/5: Completed ---")

    # --- Stage: Semantic Matching ---
    logger.info(f"--- Stage 3/5: Performing Semantic Matching ---")
    match_results = None
    matches_by_bullet = {}
    matcher = SemanticMatcher()
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
    logger.info(f"--- Stage 3/5: Completed ---")

    # --- Stage: Resume Enhancement ---
    logger.info(f"--- Stage 4/5: Enhancing Resume Content ---")
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
    logger.info(f"--- Stage 4/5: Completed ---")

    # --- Stage: Save Enhanced Resume & Analysis ---
    logger.info(f"--- Stage 5/5: Saving Enhanced Resume to Database ---")
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
    logger.info(f"--- Stage 5/5: Completed ---")
    
    # --- Post-Processing: Proactive PDF Generation ---
    logger.info(f"--- Post-Processing: Starting Proactive PDF Generation ---")
    
    logger.info(f"Job {job_id}: Starting proactive PDF generation and upload for enhanced_resume_id: {enhanced_resume_id}")
    # 'enhanced_resume_parsed' holds the actual content needed for PDF generation.
    # 'user_id' and 'enhanced_resume_id' are available in this scope.
    
    supabase_pdf_path = proactively_generate_pdf(
        user_id=user_id,
        enhanced_resume_id=enhanced_resume_id,
        enhanced_resume_content=enhanced_resume_parsed # This is the direct output from enhancer
    )

    if supabase_pdf_path:
        logger.info(f"Job {job_id}: Proactive PDF successfully generated and uploaded to Supabase Storage: {supabase_pdf_path}")
        # Optionally, update the optimization_jobs table again with the PDF path
        # Note: Commenting out for now since the 'proactive_pdf_storage_path' column doesn't exist in Supabase
        # try:
        #     update_optimization_job(job_id, {
        #         "proactive_pdf_storage_path": supabase_pdf_path
        #     })
        #     logger.info(f"Job {job_id}: Updated optimization_jobs table with PDF storage path: {supabase_pdf_path}")
        # except Exception as e_update_pdf_path:
        #     logger.error(f"Job {job_id}: Failed to update optimization_jobs table with PDF path {supabase_pdf_path}. Error: {e_update_pdf_path}", exc_info=True)
        logger.info(f"Job {job_id}: PDF path stored in Supabase Storage: {supabase_pdf_path} (database column update skipped)")
    else:
        logger.warning(f"Job {job_id}: Proactive PDF generation/upload failed for enhanced_resume_id: {enhanced_resume_id}")

    logger.info(f"--- Post-Processing: Completed ---")

    # --- Fit scoring and brief summary (minimal, safe) ---
    fit_scores = None
    fit_summary = None
    try:
        # Collect JD hard skills
        jd_hard: set = {
            kw.get("keyword", "").strip().lower()
            for kw in (keywords_data or {}).get("keywords", [])
            if isinstance(kw, dict) and kw.get("skill_type") == "hard skill" and kw.get("keyword")
        }

        def _collect_texts(resume_json: dict) -> list:
            texts = []
            if not isinstance(resume_json, dict):
                return texts
            # Experience bullets
            for exp in resume_json.get("Experience", []) or []:
                if isinstance(exp, dict):
                    for b in exp.get("responsibilities/achievements", []) or []:
                        if isinstance(b, str):
                            texts.append(b)
            # Projects descriptions
            for proj in resume_json.get("Projects", []) or []:
                if isinstance(proj, dict):
                    desc = proj.get("description")
                    if isinstance(desc, list):
                        texts.extend([d for d in desc if isinstance(d, str)])
                    elif isinstance(desc, str):
                        texts.append(desc)
            return texts

        def _collect_skill_strings(resume_json: dict) -> list:
            skills_texts = []
            skills_section = resume_json.get("Skills")
            if isinstance(skills_section, dict):
                for _, val in skills_section.items():
                    if isinstance(val, list):
                        for item in val:
                            if isinstance(item, str):
                                skills_texts.append(item)
                            elif isinstance(item, dict):
                                for _sub, sub_list in item.items():
                                    if isinstance(sub_list, list):
                                        for s in sub_list:
                                            if isinstance(s, str):
                                                skills_texts.append(s)
                    elif isinstance(val, dict):
                        for _sub, sub_list in val.items():
                            if isinstance(sub_list, list):
                                for s in sub_list:
                                    if isinstance(s, str):
                                        skills_texts.append(s)
            return skills_texts

        def _present_skills(resume_json: dict, hard_terms: set) -> set:
            present = set()
            haystack = ("\n".join(_collect_texts(resume_json) + _collect_skill_strings(resume_json))).lower()
            for term in hard_terms:
                if term and term in haystack:
                    present.add(term)
            return present

        # Compute initial/enhanced presence
        initial_present = _present_skills(original_resume_parsed, jd_hard)
        enhanced_present = _present_skills(enhanced_resume_parsed, jd_hard)
        # Ensure monotonicity: enhancement should not reduce matched coverage
        enhanced_present = enhanced_present | initial_present

        denom = max(1, len(jd_hard))
        initial_score = int(round(100 * len(initial_present) / denom))
        enhanced_score = int(round(100 * len(enhanced_present) / denom))
        if enhanced_score < initial_score:
            enhanced_score = initial_score
        fit_scores = {
            "initial": initial_score,
            "enhanced": enhanced_score,
            "delta": enhanced_score - initial_score,
        }

        # Build concise skill lists
        top_matched = sorted(list(enhanced_present))[:6]
        newly_added = sorted(list(enhanced_present - initial_present))[:6]
        top_missing = sorted(list(jd_hard - enhanced_present))[:6]

        # Deterministic concise summary (fallback or cap)
        base_show = ", ".join(sorted(list(initial_present))[:3]) or "your existing strengths"
        added_show = ", ".join(newly_added[:3]) or "key role-specific keywords"
        simple_summary = (
            f"Your resume aligns with {base_show}; we strengthened it by highlighting {added_show}."
        )

        # Brief, specific summary using a very small GPT call (best-effort)
        system_prompt = "You are a concise resume reviewer for ATS alignment. Return 1-2 short sentences, plain text, no bullets."
        user_prompt = (
            "Context: scoring resume vs. job hard skills.\n"
            f"Initial score: {initial_score}/100; Enhanced score: {enhanced_score}/100.\n"
            f"Matched: {top_matched}\nAdded: {newly_added}\nMissing: {top_missing}\n"
            "Write 1-2 sentences (<= 180 characters) explaining alignment and what was improved; do not exceed 180 characters."
        )
        try:
            fit_summary = call_openai_api(system_prompt, user_prompt, max_retries=2)
        except Exception:
            fit_summary = None

        # Enforce brevity and fall back to simple deterministic summary if needed
        if not fit_summary or len(fit_summary.strip()) > 200:
            fit_summary = simple_summary

        # Persist to optimization_jobs for direct-link page loads
        try:
            update_optimization_job(job_id, {
                "fit_scores": fit_scores,
                "fit_summary": fit_summary,
            })
        except Exception:
            pass
    except Exception:
        # Non-critical; proceed without scores/summary
        pass

    # --- Return Success Response ---
    logger.info(f"--- Pipeline End: Enhancement for Job {job_id} Completed Successfully ---")
    res =  {
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
                    "modifications_summary": modifications, # Summary of changes made
                    **({"fit_scores": fit_scores} if fit_scores else {}),
                    **({"fit_summary": fit_summary} if fit_summary else {}),
                },
            }
        }
    jsonified_res = jsonify(res)
    logger.info(f"[TZ] --- RESPONSE TO RETURN: {jsonified_res} ---")
    return jsonified_res
    