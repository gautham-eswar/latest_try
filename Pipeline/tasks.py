import logging
import json
import datetime # Added import for datetime
from working_app import celery # Import the Celery app instance from working_app.py

from Pipeline.job_tracking import update_optimization_job
from Pipeline.resume_loading import fetch_resume_data
from Pipeline.keyword_extraction import extract_keywords
from Pipeline.embeddings import SemanticMatcher
from Pipeline.enhancer import ResumeEnhancer
from Pipeline.resume_uploader import upload_resume
from Pipeline.latex_generation import proactively_generate_pdf # For the actual PDF task

logger = logging.getLogger(__name__)

@celery.task(bind=True, name='pipeline.process_single_job_description', acks_late=True, reject_on_worker_lost=True, max_retries=3, default_retry_delay=60)
def process_single_job_description_task(self, job_id: str, resume_id: str, user_id: str, job_description_text: str):
    """
    Celery task to process a single job description through the optimization pipeline.
    This task will call the PDF generation task asynchronously.
    """
    task_id_log = self.request.id if self.request and self.request.id else 'Unknown'
    logger.info(f"[Task ID: {task_id_log}, Job ID: {job_id}] Starting task.")

    try:
        # ---- NEW CODE ----
        if self.request and self.request.id:
            try:
                update_optimization_job(job_id, {"celery_task_id": self.request.id})
                logger.info(f"[Task ID: {self.request.id}, Job ID: {job_id}] Celery task ID updated in job record.")
            except Exception as e_update_task_id:
                logger.warning(f"[Task ID: {self.request.id}, Job ID: {job_id}] Failed to update celery_task_id in job record: {str(e_update_task_id)}")
        # ---- END NEW CODE ----

        # Stage 1: Fetching Original Resume
        update_optimization_job(job_id, {"status": "Processing - Fetching Original Resume"})
        logger.info(f"Job {job_id}: Fetching original resume for resume_id: {resume_id}")
        original_resume_info = fetch_resume_data(resume_id, user_id)
        original_resume_parsed = original_resume_info["data"]
        logger.info(f"Job {job_id}: Original resume fetched.")

        # Stage 2: Keyword Extraction
        update_optimization_job(job_id, {"status": "Processing - Keyword Extraction"})
        logger.info(f"Job {job_id}: Extracting keywords.")
        keywords_data = extract_keywords(job_description_text)
        update_optimization_job(job_id, {"keywords_extracted": keywords_data.get("keywords", [])})
        logger.info(f"Job {job_id}: Keywords extracted ({len(keywords_data.get('keywords', []))} keywords).")

        # Stage 3: Semantic Matching
        update_optimization_job(job_id, {"status": "Processing - Semantic Matching"})
        logger.info(f"Job {job_id}: Performing semantic matching.")
        matcher = SemanticMatcher()
        match_results = matcher.process_keywords_and_resume(keywords_data, original_resume_parsed)
        update_optimization_job(job_id, {
            "match_count": match_results.get("statistics", {}).get("total_bullet_matches"),
            "match_details": match_results.get("matches_by_bullet"),
            "new_skills_section": match_results.get("final_technical_skills"),
            "skills_selection_log": match_results.get("skill_selection_process_log")
        })
        logger.info(f"Job {job_id}: Semantic matching complete.")

        # Stage 4: Resume Enhancement (LLM)
        update_optimization_job(job_id, {"status": "Processing - Resume Enhancement (LLM)"})
        logger.info(f"Job {job_id}: Enhancing resume content.")
        enhancer = ResumeEnhancer()
        enhanced_resume_parsed, modifications = enhancer.enhance_resume(
            original_resume_parsed,
            match_results.get("matches_by_bullet", {}),
            final_technical_skills=match_results.get("final_technical_skills")
        )
        update_optimization_job(job_id, {"modifications": modifications})
        logger.info(f"Job {job_id}: Resume enhancement complete.")

        # Stage 5: Save Enhanced Resume (structured data)
        update_optimization_job(job_id, {"status": "Processing - Saving Enhanced Resume Data"})
        logger.info(f"Job {job_id}: Saving enhanced resume data to database.")
        enhanced_resume_db_entry = upload_resume({
            "user_id": user_id,
            "data": enhanced_resume_parsed,
            "file_name": f"Enhanced - {original_resume_info.get('file_name', 'resume.json')}",
            "enhancement_id": job_id,
            "original_resume_id": original_resume_info["id"],
        })
        enhanced_resume_id_val = enhanced_resume_db_entry["id"]
        update_optimization_job(job_id, {"enhanced_resume_id": enhanced_resume_id_val})
        logger.info(f"Job {job_id}: Enhanced resume data saved with ID: {enhanced_resume_id_val}.")

        # Stage 6: Queue PDF Generation Task
        update_optimization_job(job_id, {"status": "Queuing PDF Generation"})
        enhanced_resume_content_json_string = json.dumps(enhanced_resume_parsed)

        generate_pdf_task.delay(job_id, enhanced_resume_id_val, user_id, enhanced_resume_content_json_string)
        logger.info(f"Job {job_id}: PDF generation task queued for enhanced_resume_id: {enhanced_resume_id_val}.")

        update_optimization_job(job_id, {"status": "Processing Complete, PDF Queued"})
        logger.info(f"[Task ID: {task_id_log}, Job ID: {job_id}] Task finished. PDF task queued.")
        return {"job_id": job_id, "status": "Processing Complete, PDF Queued", "enhanced_resume_id": enhanced_resume_id_val}

    except Exception as e:
        task_id_log = self.request.id if self.request and self.request.id else 'Unknown'
        logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] Error: {str(e)}", exc_info=True)
        error_message_for_db = f"Task Error: {type(e).__name__} - {str(e)}"
        try:
            update_optimization_job(job_id, {"status": "Failed", "error_message": error_message_for_db[:1000]}) # Ensure message is not too long for DB
        except Exception as db_e:
            logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] CRITICAL: Failed to update job status to Failed: {str(db_e)}", exc_info=True)

        current_retries = self.request.retries if self.request else 0
        max_retries_for_task = self.max_retries if hasattr(self, 'max_retries') else 0

        if self.request and current_retries < max_retries_for_task:
             logger.info(f"[Task ID: {task_id_log}, Job ID: {job_id}] Retrying task, attempt {current_retries + 1} of {max_retries_for_task}")
             raise self.retry(exc=e, countdown=int(getattr(self, 'default_retry_delay', 60)) * (current_retries + 1))
        else:
             logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] Max retries reached or retry not possible. Task failed permanently.")
             raise # Re-raise the original exception


@celery.task(bind=True, name='pipeline.generate_pdf',acks_late=True, reject_on_worker_lost=True, max_retries=2, default_retry_delay=120)
def generate_pdf_task(self, job_id: str, enhanced_resume_id: str, user_id: str, enhanced_resume_content_json_string: str):
    """
    Celery task to generate PDF from enhanced resume content.
    This task is called by process_single_job_description_task.
    """
    task_id_log = self.request.id if self.request and self.request.id else 'Unknown'
    logger.info(f"[Task ID: {task_id_log}, Job ID: {job_id}] generate_pdf_task started for enhanced_resume_id: {enhanced_resume_id}.")

    try:
        update_optimization_job(job_id, {"status": "Processing - PDF Generation"})
        enhanced_resume_content = json.loads(enhanced_resume_content_json_string) # Deserialize

        supabase_pdf_path = proactively_generate_pdf(
            user_id=user_id,
            enhanced_resume_id=enhanced_resume_id,
            enhanced_resume_content=enhanced_resume_content
        )

        if supabase_pdf_path:
            logger.info(f"Job {job_id}: PDF generated and uploaded to Supabase: {supabase_pdf_path}")
            update_optimization_job(job_id, {
                "status": "Completed",
                "pdf_generation_status": "Success",
                "enhanced_resume_pdf_path": supabase_pdf_path,
                "final_status_timestamp": datetime.datetime.utcnow().isoformat()
            })
            return {"job_id": job_id, "pdf_status": "Success", "pdf_path": supabase_pdf_path}
        else:
            logger.error(f"Job {job_id}: PDF generation or upload failed for enhanced_resume_id: {enhanced_resume_id}.")
            update_optimization_job(job_id, {
                "status": "Failed", # Or "Completed_With_PDF_Error" to be more specific
                "pdf_generation_status": "Failed",
                "error_message": "PDF generation or upload failed.", # Specific error from proactively_generate_pdf might be better if available
                "final_status_timestamp": datetime.datetime.utcnow().isoformat()
            })
            raise ValueError("PDF generation/upload failed")

    except Exception as e:
        task_id_log = self.request.id if self.request and self.request.id else 'Unknown'
        logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] Error in generate_pdf_task: {str(e)}", exc_info=True)
        error_message_for_db = f"PDF Task Error: {type(e).__name__} - {str(e)}"
        try:
            update_optimization_job(job_id, {
                "status": "Failed",
                "pdf_generation_status": "Failed",
                "error_message": error_message_for_db[:1000], # Ensure message is not too long
                "final_status_timestamp": datetime.datetime.utcnow().isoformat()
            })
        except Exception as db_e:
            logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] CRITICAL: Failed to update job status to Failed during PDF task error: {str(db_e)}", exc_info=True)

        current_retries = self.request.retries if self.request else 0
        max_retries_for_task = self.max_retries if hasattr(self, 'max_retries') else 0

        if self.request and current_retries < max_retries_for_task:
             logger.info(f"[Task ID: {task_id_log}, Job ID: {job_id}] Retrying PDF task, attempt {current_retries + 1} of {max_retries_for_task}")
             raise self.retry(exc=e, countdown=int(getattr(self, 'default_retry_delay', 120)) * (current_retries + 1))
        else:
             logger.error(f"[Task ID: {task_id_log}, Job ID: {job_id}] Max retries reached for PDF task or retry not possible. PDF task failed permanently.")
             raise # Re-raise
